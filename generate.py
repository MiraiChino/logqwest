import argparse
import csv
import json
import random
import re
import time
from functools import wraps
from pathlib import Path

import requests
import json5
from groq import Groq
import google.generativeai as genai

TYPE_JSON = {"type": "json_object"}
TYPE_TEXT = {"type": "text"}
WAIT_TIME = 10

# config.json から設定を読み込む
config_path = Path("config.json")
if config_path.exists():
    with config_path.open(encoding="utf-8") as f:
        config = json.load(f)
    RESULT_TEMPLATE = config["RESULT_TEMPLATE"]
    NG_WORDS = set(config["NG_WORDS"])
    CSV_HEADERS_AREA = config["CSV_HEADERS_AREA"]
    NEW_AREA_NAME_PROMPT = config["NEW_AREA_NAME_PROMPT"]
    REQUIRED_FIELDS_AREA = config["REQUIRED_FIELDS_AREA"]
    CSV_HEADERS_ADVENTURE = config["CSV_HEADERS_ADVENTURE"]
    CHAPTER_SETTINGS = config["CHAPTER_SETTINGS"]
    BEFORE_LOG_TEMPLATE = config["BEFORE_LOG_TEMPLATE"]
else:
    raise FileNotFoundError("config.json が見つかりません。")

def retry_on_failure(max_retries=30, wait_time=WAIT_TIME, logger=None):
    """
    リトライデコレータ。
    特定の関数を指定回数リトライし、成功または失敗の状態に応じてログを記録する。

    Args:
        max_retries (int): リトライの最大回数 (デフォルト: 30)。
        wait_time (int): リトライ間の待機時間 (秒、デフォルト: 30)。
        logger (callable): ログ記録用の関数。デフォルトは `print` を使用。
    """
    if logger is None:
        logger = print  # デフォルトのロガー関数

    if max_retries <= 0 or wait_time < 0:
        raise ValueError("max_retries must be > 0 and wait_time must be >= 0.")

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_retries + 1):
                try:
                    response = func(*args, **kwargs)
                    if response:  # 成功したレスポンスを返す場合
                        # logger(f"[Attempt {attempt}] Success.")
                        return response
                    logger(f"[Attempt {attempt}] Empty or None response received.")
                except requests.RequestException as e:
                    logger(f"[Attempt {attempt}] RequestException: {e}")
                except Exception as e:
                    logger(f"[Attempt {attempt}] error: {e}")
                    if "429" in str(e) or "Rate limit" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                        logger("Rate limit exceeded. Sleeping for 60 minutes...")
                        time.sleep(60*60)  # 60分間スリープ

                if attempt < max_retries:
                    logger(f"[Attempt {attempt}] Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
            raise ValueError(f"[Attempt {max_retries}] Max retries reached.")
        return wrapper
    return decorator

class GeminiChat:
    def __init__(self, model="models/gemini-2.0-flash-exp"):
        self.client = genai.GenerativeModel(model)
        self.model = model

    def get_response(self, user_prompt, temperature=1.5, max_tokens=8192, response_format=TYPE_TEXT):
        response = self.client.generate_content(
            user_prompt,
            generation_config=genai.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
        )
        # json形式を定義する
        #     generation_config=genai.GenerationConfig(
        #     response_mime_type="application/json", response_schema=list[Recipe]
        # )
        return response.text

class GroqChat:
    def __init__(self, model="gemma2-9b-it"):
        self.client = Groq()
        self.model = model

    def get_response(self, user_prompt, temperature=0.6, max_tokens=8192, response_format=TYPE_TEXT):
        chat_completion = self.client.chat.completions.create(
            messages=[
                {"role": "user", "content": user_prompt},
            ],
            model=self.model,
            temperature=temperature,
            max_tokens=max_tokens,
            stop=None,
            response_format=response_format,
        )
        return chat_completion.choices[0].message.content
    
class BaseGenerator:
    def __init__(self, chat_client, template_file=None):
        self.chat_client = chat_client
        self.load_template(template_file)

    def load_template(self, template_file):
        if not template_file:
            return
        if Path(template_file).exists():
            with open(template_file) as f:
                self.template = f.read()
        else:
            raise ValueError(f"Not found template file: {template_file}")

    def extract(self, response):
        raise NotImplementedError("Subclasses should implement this method.")
    
    def generate(self, response_format, **kwargs):
        prompt = self.template.format(**kwargs)
        # print(prompt)
        # print("---")
        time.sleep(WAIT_TIME)
        response = self.chat_client.get_response(prompt, temperature=1.5, max_tokens=8192, response_format=response_format)
        # print(response)
        # print("---")
        contents = self.extract(response)
        # print(contents)
        return contents
    
    def add_to_csv(self, csv_path, csv_contents):
        """
        Append contents to the CSV file.
        """
        with open(csv_path, "a", encoding="utf-8") as file:
            writer = csv.writer(file, delimiter=',')
            writer.writerow(csv_contents)  # 1行だけ書き込む

    def add_to_txt(self, txt_path, txt_contents):
        """
        Append contents to the txt file.
        """
        with open(txt_path, mode='a', encoding="utf-8") as file:
            file.write(txt_contents)

class AreaGenerator(BaseGenerator):
    def __init__(self, chat_client, all_areas_csv_path, template_file="prompt/new_area.txt"):
        super().__init__(chat_client, template_file)
        self.all_areas_csv_path = all_areas_csv_path
        self.areas = {}

    def load_existing_areas(self, num_refered_areas=0):
        with open(self.all_areas_csv_path, "r", encoding="utf-8") as file:
            reader = csv.reader(file)
            headers = next(reader)  # Skip the headers
            area_csv_list = []
            for name, geography, history, risk, treasure, treasure_locations, \
                collectibles, dangerous_creatures, harmless_creatures, anomalies in reader:
                self.areas[name] = dict(
                    geography=geography,
                    history=history,
                    risk=risk,
                    treasure=treasure,
                    treasure_locations=treasure_locations,
                    collectibles=collectibles,
                    dangerous_creatures=dangerous_creatures,
                    harmless_creatures=harmless_creatures,
                    anomalies=anomalies,
                )
                area_csv_list.append(f"{name},{history}")
            # ランダムに選択
            selected_areas = random.sample(area_csv_list, min(num_refered_areas, len(area_csv_list)))
            print("refer:", [area.split(',')[0] for area in selected_areas])
            areas_csv = "\n".join(selected_areas)
        return areas_csv

    @retry_on_failure(max_retries=30, wait_time=WAIT_TIME)
    def generate_new_area(self, num_refered_areas=0, area_name=None):
        if Path(self.all_areas_csv_path).exists():
            existing_areas_csv = self.load_existing_areas(num_refered_areas)
        else:
            existing_areas_csv = ""
            with open(self.all_areas_csv_path, "w", encoding="utf-8") as file:
                writer = csv.writer(file, delimiter=',')
                writer.writerow(CSV_HEADERS_AREA)

        if not area_name:
            area_name = NEW_AREA_NAME_PROMPT
        new_area_csv = self.generate(
            response_format=TYPE_TEXT,
            existing_areas=existing_areas_csv,
            area_name=area_name
        )
        self.add_to_csv(csv_path=self.all_areas_csv_path, csv_contents=new_area_csv)
        return new_area_csv

    def extract(self, response):
        """
        JSONデータの抽出とバリデーションを実行
        """
        try:
            pattern = r"```json\n(.*?)```"
            match = re.search(pattern, response, re.DOTALL)
            if match:
                content = match.group(1).strip()
            else:
                raise ValueError(f"Invalid format: not fount ```json ```")

            # JSONデータのデコード
            
            data = json5.loads(content)
            
            # バリデーションの実施
            required_fields = REQUIRED_FIELDS_AREA
            
            # 必須フィールドの存在を確認
            for field in required_fields:
                if field not in data:
                    raise ValueError(f"Missing required field: {field}")
            
            # 各フィールドが文字列かリストであることを確認
            for field, value in data.items():
                if isinstance(value, list):
                    if all(isinstance(item, str) for item in value):
                        data[field] = ''.join(value)
                    elif all(isinstance(item, dict) for item in value):
                        data[field] = ' '.join(": ".join(d.values()) for d in value)
                    else:
                        raise ValueError(f"Field '{field}' must be a list on string or list on dict, but got {type(value)}")
                elif isinstance(value, dict):
                    data[field] = ": ".join(value.values())
                elif isinstance(value, str):
                    pass
                else:
                    raise ValueError(f"Field '{field}' must be a string or list, but got {type(value)}")

            for field, value in data.items():
                if NG_WORDS & set(value):
                    raise ValueError(f"Include NG time word: {value}")

            exsisting_treasures = [area["treasure"].split(":")[0] for area_name, area in self.areas.items()]
            treasure = data["財宝"].split(":")[0]
            if treasure in exsisting_treasures:
                raise ValueError(f"Already existing treasure: {treasure}")

            exsisting_areas = [area_name for area_name in self.areas.keys()]
            area = data["エリア名"]
            if area in exsisting_areas:
                raise ValueError(f"Already existing area: {area}")

            # リスト形式に変換
            csv_contents = list(data.values())
            return csv_contents
        
        except json.JSONDecodeError as e:
            print(response)
            import pdb; pdb.set_trace()
            raise ValueError(f"Invalid JSON format: {str(e)}") from e

class AdventureGenerator(BaseGenerator):
    def __init__(self, chat_client, all_areas_csv_path, template_file="prompt/new_adventure.txt"):
        super().__init__(chat_client, template_file)
        self.areas = self.load_areas(all_areas_csv_path)

    def load_areas(self, all_areas_csv_path):
        areas = {}
        if Path(all_areas_csv_path).exists():
            with open(all_areas_csv_path, "r", encoding="utf-8") as file:
                reader = csv.reader(file)
                headers = next(reader)  # Skip the headers
                areas = {name: [*descriptions] for name, *descriptions in reader}
        return areas

    @retry_on_failure(max_retries=30, wait_time=WAIT_TIME)
    def generate_new_adventure(self, adventure_name, result, area_name):
        """
        Generate new adventure summary and add them to the CSV.
        """
        geography, history, risk, treasures, treasure_locations, \
            collectibles, dangerous_creatures, harmless_creatures, anomalies = self.areas[area_name]
        area_csv = Path(f"data/{area_name}.csv")
        if not area_csv.exists():
            with open(area_csv, "w", encoding="utf-8") as file:
                writer = csv.writer(file, delimiter=',')
                writer.writerow(CSV_HEADERS_ADVENTURE)
        contents = self.generate(
            response_format=TYPE_JSON,
            area_name=area_name,
            geography=geography,
            history=history,
            risk=risk,
            treasures=treasures,
            treasure_locations=treasure_locations,
            collectibles=collectibles,
            dangerous_creatures=dangerous_creatures,
            harmless_creatures=harmless_creatures,
            anomalies=anomalies,
            result=RESULT_TEMPLATE[result],
        )
        csv_contents = [adventure_name] + [result] + contents
        self.add_to_csv(csv_path=area_csv, csv_contents=csv_contents)
        return csv_contents

    def extract(self, response):
        """
        JSONデータの抽出とバリデーションを実行
        """
        try:
            pattern = r"```json\n(.*?)```"
            match = re.search(pattern, response, re.DOTALL)
            if match:
                content = match.group(1).strip()
                # JSONデータのデコード
                data = json5.loads(content)
            else:
                # JSONデータのデコード
                data = json.loads(response)

            # バリデーションの実施
            root_keys = {"result", "chapters"}
            if not root_keys.issubset(data.keys()):
                raise ValueError(f"Missing root keys. Required: {root_keys}")
            
            # 章データの検証
            chapters = data.get("chapters", [])
            if len(chapters) != 8:
                raise ValueError(f"Invalid chapter count: {len(chapters)}/8")

            for i, chapter in enumerate(chapters, 1):
                if not isinstance(chapter, dict):
                    raise ValueError(f"Chapter {i} must be an object")
                
                required_keys = {"number", "title", "content"}
                missing_keys = required_keys - chapter.keys()
                if missing_keys:
                    raise ValueError(f"Chapter {i} missing keys: {missing_keys}")
                
                number = chapter.get("number")
                if number != f"{i}章":
                    raise ValueError(f"Chapter {i} number mismatch: {number}")
                
                content = chapter.get("content")
                if NG_WORDS & set(content):
                    raise ValueError(f"Chapter {i} include NG time word: {content}")
                
            contents = [data["title"]+":"+data["content"] for data in data.get("chapters", [])]
            return contents
            
        except json.JSONDecodeError as e:
            print(response)
            import pdb; pdb.set_trace()
            raise ValueError(f"Invalid JSON format: {str(e)}") from e

    def sort_csv(self, file_path):
        def sort_key(row):
            # 冒険名のプレフィックスと番号を抽出
            match = re.match(r'^(失敗|成功|大成功)(\d+)_', row[0])
            if match:
                prefix, number = match.groups()
                number = int(number)
            else:
                prefix, number = '', 0  # マッチしない場合のデフォルト値

            # 冒険名のプレフィックスに基づいて順序を指定
            prefix_order = {
                '失敗': 0,
                '成功': 1,
                '大成功': 2
            }

            # プレフィックスと番号に基づいて順序を決定
            return (prefix_order.get(prefix, 3), number)

        with open(file_path, 'r', encoding='utf-8') as file:
            reader = csv.reader(file)
            headers = next(reader)  # ヘッダーを読み込む
            rows = list(reader)  # 残りの行をリストとして読み込む

        # 冒険名の順にソート
        rows.sort(key=sort_key)

        with open(file_path, 'w', encoding='utf-8', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(headers)  # ヘッダーを書き込む
            writer.writerows(rows)  # ソートされた行を書き込む

class LogGenerator(BaseGenerator):
    CHAPTER_SETTINGS = CHAPTER_SETTINGS

    def __init__(self, chat_client):
        super().__init__(chat_client)

    def load_chapters(self, area_csv, adventure_name):
        if area_csv.exists():
            with open(area_csv, "r", encoding="utf-8") as file:
                reader = csv.reader(file)
                headers = next(reader)  # Skip the headers
                for title, result, *chapters in reader:
                    if title == adventure_name:
                        return [*chapters]
                raise ValueError(f"Not found adventure: {adventure_name}")
        else:
            raise ValueError(f"Not found file: {area_csv}")

    @retry_on_failure(max_retries=30, wait_time=WAIT_TIME)
    def generate_log(self, area_name, adventure_name, i_chapter, **kwargs):
        """
        Generate a new adventure log.
        """
        setting = self.CHAPTER_SETTINGS[i_chapter]
        template_file = setting.get("template_file", "prompt/new_log.txt")
        area_csv = Path(f"data/{area_name}.csv")
        chapters = self.load_chapters(area_csv, adventure_name)

        kwargs[f"before_chapter"] = setting.get("before_chapter", "")
        kwargs[f"chapter"] = chapters[i_chapter]
        kwargs[f"after_chapter"] = setting.get("after_chapter", "")

        if i_chapter != 0 and "pre_log" in kwargs and kwargs[f"pre_log"]:
            pre_log = kwargs["pre_log"]
            kwargs["before_log"] = BEFORE_LOG_TEMPLATE["with_pre_log"].format(pre_log=pre_log)
        else:
            kwargs["before_log"] = BEFORE_LOG_TEMPLATE["default"]
        
        self.load_template(template_file)
        log_contents = self.generate(response_format=TYPE_TEXT, **kwargs)
        area_directory = Path(f"data/{area_name}")
        area_directory.mkdir(parents=True, exist_ok=True)
        adventure_txt = area_directory / f"{adventure_name}.txt"
        self.add_to_txt(adventure_txt, log_contents)
        return log_contents

    def extract(self, response):
        # Split the response into lines
        lines = response.strip().split("\n")

        filtered_lines = []
        for line in lines:
            stripped = line.strip()
            # 先頭が##で始まる行をスキップ
            if stripped.startswith('##'):
                continue
            # 数字で始まる行をチェック (例: '51. xxx')
            match = re.match(r'^\d+\.\s(.*)', stripped)
            if match:
                filtered_line = match.group(1)
                filtered_lines.append(filtered_line)

                if NG_WORDS & set(filtered_line):
                    raise ValueError(f"Include NG time word: {filtered_line}")

        # 中身が空かチェック
        if not filtered_lines:
            raise ValueError("Extracted content is empty.")
        
        # 中身が20行以上あるかチェック
        if len(filtered_lines) < 20:
            raise ValueError("Extracted content has less than 20 lines.")

        return '\n'.join(filtered_lines) + '\n'

def parse_arguments():
    parser = argparse.ArgumentParser(description="Area and Adventure and Log Generator")
    # 追加：使用するチャットクライアントを指定する引数。geminiまたはgroqのどちらかを選べます。
    parser.add_argument(
        "--client",
        choices=["gemini", "groq"],
        default="gemini",
        help="使用するチャットクライアントを指定。'gemini' または 'groq' を選択できます。 (デフォルト: gemini)"
    )
    # 追加：使用するモデル名を指定する引数。指定しなかった場合、clientに合わせたデフォルト値を使用します。
    parser.add_argument(
        "--model",
        default=None,
        help="使用するモデル名を指定。指定しない場合、clientに合わせたデフォルト値が使用されます。"
    )

    subparsers = parser.add_subparsers(dest="type", required=True)

    # Area用のサブパーサー
    area_parser = subparsers.add_parser("area", help="Generate areas")
    area_parser.add_argument(
        "count",
        type=int,
        nargs='?',
        default=1,
        help="Number of times to run the area generation (default: 1)"
    )

    # Adventures用のサブパーサー
    subparsers.add_parser("adventures", help="Generate adventures")

    # Logs用のサブパーサー
    subparsers.add_parser("logs", help="Generate logs")

    return parser.parse_args()

def generate_area(area_generator, count):
    for _ in range(count):
        num_refered_areas = random.randint(0, 5)
        new_area_csv = area_generator.generate_new_area(num_refered_areas)
        new_area_name = new_area_csv[0]
        print(f"✅ {new_area_name}")

def process_adventures(adventure_generator, all_areas_csv_path):
    areas = load_areas(all_areas_csv_path)
    for area_name in areas.keys():
        area_csv = Path(f"data/{area_name}.csv")
        add_adventures(adventure_generator, area_name)
        adventure_generator.sort_csv(file_path=area_csv)

def process_logs(log_generator, all_areas_csv_path):
    areas = load_areas(all_areas_csv_path)
    for area_name in areas.keys():
        generate_log(log_generator, area_name)

def load_areas(all_areas_csv_path):
    if Path(all_areas_csv_path).exists():
        with open(all_areas_csv_path, "r", encoding="utf-8") as file:
            reader = csv.reader(file)
            headers = next(reader)  # Skip the headers
            return {name: [*descriptions] for name, *descriptions in reader}
    return {}

def add_adventures(adventure_generator, area_name):
    add_adventure_type(adventure_generator, area_name, "失敗", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    add_adventure_type(adventure_generator, area_name, "成功", [1, 2, 3, 4, 5, 6, 7, 8, 9])
    add_adventure_type(adventure_generator, area_name, "大成功", [1])

def add_adventure_type(adventure_generator, area_name, result, num_range):
    area_csv = Path(f"data/{area_name}.csv")
    already_exist_adventures = load_existing_adventures(area_csv)
    for num in num_range:
        adventure_name = f"{result}{num}_{area_name}"
        if adventure_name not in already_exist_adventures:
            adventure_generator.generate_new_adventure(adventure_name, result, area_name)
            print(f"✅ {adventure_name}")

def load_existing_adventures(area_csv):
    if area_csv.exists():
        with open(area_csv, "r", encoding="utf-8") as file:
            reader = csv.reader(file)
            headers = next(reader)  # Skip the headers
            return [adventure_name for adventure_name, result, *chapters in reader]
    return []

def generate_log(log_generator, area_name):
    area_csv = Path(f"data/{area_name}.csv")
    area_directory = Path(f"data/{area_name}")
    if not area_csv.exists():
        return

    with open(area_csv, "r", encoding="utf-8") as file:
        reader = csv.reader(file)
        headers = next(reader)  # Skip the headers
        for adventure_name, result, *chapters in reader:
            adventure_txt = area_directory / f"{adventure_name}.txt"
            if not Path(adventure_txt).exists():
                pre_log = None
                for i in range(8):
                    pre_log = log_generator.generate_log(
                        area_name=area_name,
                        adventure_name=adventure_name,
                        i_chapter=i,
                        pre_log=pre_log,
                    )
                    print(f"✅ {adventure_txt} {i+1}/8")

def main():
    args = parse_arguments()

    all_areas_csv_path = "data/areas.csv"
    # 引数で指定されたclientとmodelに応じてチャットクライアントを生成
    if args.client == "gemini":
        model_name = args.model if args.model else "models/gemini-2.0-flash-001"
        chat_client = GeminiChat(model_name)
    elif args.client == "groq":
        model_name = args.model if args.model else "gemma2-9b-it"
        chat_client = GroqChat(model_name)
    else:
        raise ValueError(f"不明なチャットクライアント: {args.client}")

    area_generator = AreaGenerator(
        chat_client,
        all_areas_csv_path=all_areas_csv_path,
        template_file="prompt/new_area.txt"
    )
    adventure_generator = AdventureGenerator(
        chat_client,
        all_areas_csv_path=all_areas_csv_path,
        template_file="prompt/new_adventure.txt"
    )
    log_generator = LogGenerator(chat_client)

    if args.type == "area":
        generate_area(area_generator, args.count)
    elif args.type == "adventures":
        process_adventures(adventure_generator, all_areas_csv_path)
    elif args.type == "logs":
        process_logs(log_generator, all_areas_csv_path)

if __name__ == "__main__":
    main()
