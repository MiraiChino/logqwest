import argparse
import csv
import json
import random
import re
import time
import traceback
from functools import wraps
from pathlib import Path

import requests
import json5
from groq import Groq
import google.generativeai as genai

# グローバル定数としてのデバッグフラグ（デフォルトは False）
DEBUG_MODE = False

# 設定ファイルとパスの定義
CONFIG_FILE = "prompt/config.json"
DATA_DIR = Path("data")
PROMPT_DIR = Path("prompt")
AREAS_CSV_FILE = DATA_DIR / "areas.csv"
NEW_AREA_TEMPLATE_FILE = PROMPT_DIR / "new_area.txt"
NEW_ADVENTURE_TEMPLATE_FILE = PROMPT_DIR / "new_adventure.txt"
NEW_LOG_TEMPLATE_FILE = PROMPT_DIR / "new_log.txt"

# 設定ファイルのロード
def load_config(config_file):
    config_path = Path(config_file)
    if not config_path.exists():
        raise FileNotFoundError(f"{config_file} が見つかりません。")
    with config_path.open(encoding="utf-8") as f:
        return json.load(f)

config = load_config(CONFIG_FILE)

# 設定値の定義
RESULT_TEMPLATE = config["RESULT_TEMPLATE"]
NG_WORDS = set(config["NG_WORDS"])
CSV_HEADERS_AREA = config["CSV_HEADERS_AREA"]
NEW_AREA_NAME_PROMPT = config["NEW_AREA_NAME_PROMPT"]
CSV_HEADERS_ADVENTURE = config["CSV_HEADERS_ADVENTURE"]
CHAPTER_SETTINGS = config["CHAPTER_SETTINGS"]
BEFORE_LOG_TEMPLATE = config["BEFORE_LOG_TEMPLATE"]
DEFAULT_WAIT_TIME = config.get("DEFAULT_WAIT_TIME", 10)
MAX_RETRIES = config.get("MAX_RETRIES", 30)
AREA_INFO_KEYS_FOR_PROMPT = config["AREA_INFO_KEYS_FOR_PROMPT"]

# 型定義
TYPE_JSON = {"type": "json_object"}
TYPE_TEXT = {"type": "text"}


# ファイルパス生成関数
def get_area_csv_path(area_name):
    """エリア CSV ファイルのパスを生成する。"""
    return DATA_DIR / area_name / f"{area_name}.csv"


def get_adventure_txt_path(area_name, adventure_name):
    """冒険ログテキストファイルのパスを生成する。"""
    return DATA_DIR / area_name / f"{adventure_name}.txt"


def retry_on_failure(max_retries=MAX_RETRIES, wait_time=DEFAULT_WAIT_TIME, logger=None):
    if logger is None:
        logger = print
    if max_retries <= 0 or wait_time < 0:
        raise ValueError("max_retries は 0 より大きく、wait_time は 0 以上である必要があります。")
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_retries + 1):
                try:
                    response = func(*args, **kwargs)
                    if response:
                        return response
                    logger(f"[Attempt {attempt}/{max_retries}] 空または無効なレスポンスを受信しました。")
                except requests.RequestException as e:
                    logger(f"[Attempt {attempt}/{max_retries}] RequestException: {e}")
                except Exception as e:
                    logger(f"[Attempt {attempt}/{max_retries}] エラー: {traceback.format_exc()}")
                    if any(err_msg in str(e) for err_msg in ["429", "Rate limit", "RESOURCE_EXHAUSTED"]):
                        logger("レート制限超過。60分間スリープします...")
                        time.sleep(60 * 60)
                if attempt < max_retries:
                    logger(f"[Attempt {attempt}/{max_retries}] {wait_time}秒後にリトライします...")
                    time.sleep(wait_time)
            raise ValueError(f"[Attempt {max_retries}/{max_retries}] 最大リトライ回数に達しました。")
        return wrapper
    return decorator


class ChatClient:
    def __init__(self, model):
        self.model = model

    def get_response(self, user_prompt, temperature, max_tokens, response_format):
        raise NotImplementedError("サブクラスで実装してください。")


class GeminiChat(ChatClient):
    def __init__(self, model="models/gemini-2.0-flash-exp"):
        super().__init__(model)
        self.client = genai.GenerativeModel(model)

    def get_response(self, user_prompt, temperature=1.5, max_tokens=8192, response_format=TYPE_TEXT):
        response = self.client.generate_content(
            user_prompt,
            generation_config=genai.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
        )
        return response.text


class GroqChat(ChatClient):
    def __init__(self, model="gemma2-9b-it"):
        super().__init__(model)
        self.client = Groq()

    def get_response(self, user_prompt, temperature=0.6, max_tokens=8192, response_format=TYPE_TEXT):
        chat_completion = self.client.chat.completions.create(
            messages=[{"role": "user", "content": user_prompt}],
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
        self.template = self._load_template(template_file)

    def _load_template(self, template_file):
        if not template_file:
            return None
        template_path = Path(template_file)
        if not template_path.exists():
            raise ValueError(f"テンプレートファイルが見つかりません: {template_file}")
        with template_path.open(encoding="utf-8") as f:
            return f.read()

    def generate(self, response_format, **kwargs):
        if not self.template:
            raise ValueError("テンプレートがロードされていません。")
        prompt = self.template.format(**kwargs)
        if DEBUG_MODE:
            print("=== DEBUG: Prompt ===")
            print(prompt)
            print("=====================")
        time.sleep(DEFAULT_WAIT_TIME)
        response = self.chat_client.get_response(
            prompt, temperature=1.5, max_tokens=8192, response_format=response_format
        )
        if DEBUG_MODE:
            print("=== DEBUG: Response ===")
            print(response)
            print("=======================")
        contents = self.extract(response)
        if DEBUG_MODE:
            print("=== DEBUG: Contents ===")
            print(contents)
            print("=======================")
        return contents

    def extract(self, response):
        raise NotImplementedError("サブクラスで extract メソッドを実装してください。")

    def _add_to_csv(self, csv_path, csv_contents, headers=None):
        csv_path = Path(csv_path)
        file_exists = csv_path.exists()
        with csv_path.open("a", encoding="utf-8", newline="") as file:
            writer = csv.writer(file, delimiter=',')
            if not file_exists and headers:
                writer.writerow(headers)
            writer.writerow(csv_contents)

    def _add_to_txt(self, txt_path, txt_contents):
        txt_path = Path(txt_path)
        txt_path.parent.mkdir(parents=True, exist_ok=True)
        with txt_path.open("a", encoding="utf-8") as file:
            file.write(txt_contents)


class AreaGenerator(BaseGenerator):
    def __init__(self, chat_client, all_areas_csv_path, template_file=NEW_AREA_TEMPLATE_FILE):
        super().__init__(chat_client, template_file)
        self.all_areas_csv_path = all_areas_csv_path
        self.areas = self._load_existing_areas()

    def _load_existing_areas(self):
        areas = {}
        areas_csv_path = Path(self.all_areas_csv_path)
        if areas_csv_path.exists():
            with areas_csv_path.open("r", encoding="utf-8") as file:
                reader = csv.reader(file)
                next(reader, None)
                for row in reader:
                    if len(row) == len(CSV_HEADERS_AREA):
                        area_data = dict(zip(CSV_HEADERS_AREA, row))
                        areas[area_data["エリア名"]] = area_data
        return areas

    def _get_referenced_areas_csv(self, num_refered_areas):
        if not Path(self.all_areas_csv_path).exists():
            Path(self.all_areas_csv_path).parent.mkdir(parents=True, exist_ok=True)
            self._add_to_csv(self.all_areas_csv_path, [], headers=CSV_HEADERS_AREA)
            return ""
        area_names = list(self.areas.keys())
        selected_areas = area_names
        # selected_areas = random.sample(area_names, min(num_refered_areas, len(area_names))) if area_names else []
        # print("参照エリア:", selected_areas)
        return "\n".join(area_names)

    @retry_on_failure()
    def generate_new_area(self, num_refered_areas=0, area_name=None):
        existing_areas_csv = self._get_referenced_areas_csv(num_refered_areas)
        area_name_prompt = area_name if area_name else NEW_AREA_NAME_PROMPT
        area_data = self.generate(
            response_format=TYPE_TEXT,
            existing_areas=existing_areas_csv,
            area_name=area_name_prompt
        )
        self._add_to_csv(self.all_areas_csv_path, area_data)
        self.areas[area_data[0]] = dict(zip(CSV_HEADERS_AREA, area_data))
        return area_data

    def extract(self, response):
        try:
            json_str = self._extract_json_string(response)
            data = json5.loads(json_str)
            self._validate_area_data(data)
            csv_contents = [str(data.get(header, '')) for header in CSV_HEADERS_AREA]
            return csv_contents
        except json.JSONDecodeError as e:
            print("JSONデコードエラー:", response)
            raise ValueError(f"無効なJSON形式: {str(e)}") from e

    def _extract_json_string(self, response):
        pattern = r"```json\n(.*?)```"
        match = re.search(pattern, response, re.DOTALL)
        if not match:
            raise ValueError("レスポンスに```json ```形式のJSONが見つかりません。")
        return match.group(1).strip()

    def _validate_area_data(self, data):
        for field in CSV_HEADERS_AREA:
            if field not in data:
                raise ValueError(f"必須フィールドがありません: {field}")
            value = data[field]
            if isinstance(value, list):
                if all(isinstance(item, str) for item in value):
                    data[field] = ''.join(value)
                elif all(isinstance(item, dict) for item in value):
                    data[field] = ' '.join(": ".join(d.values()) for d in value)
                else:
                    raise ValueError(f"'{field}'はlist型かstring型かdictのlist型である必要があります {type(value)}")
            elif isinstance(value, dict):
                data[field] = ": ".join(value.values())
            elif isinstance(value, str):
                pass
            else:
                raise ValueError(f"'{field}'はstring型かlist型である必要があります {type(value)}")

        for field, value in data.items():
            if NG_WORDS & set(value):
                raise ValueError(f"NGワードが含まれています: {value}")

        treasure_name = data["財宝"].split(":")[0]
        if treasure_name in [area_data["財宝"].split(":")[0] for area_data in self.areas.values()]:
            raise ValueError(f"既存の財宝と重複しています: {treasure_name}")
        area_name = data["エリア名"]
        if area_name in self.areas:
            raise ValueError(f"既存のエリア名と重複しています: {area_name}")


class AdventureGenerator(BaseGenerator):
    def __init__(self, chat_client, all_areas_csv_path, template_file=NEW_ADVENTURE_TEMPLATE_FILE):
        super().__init__(chat_client, template_file)
        self.all_areas_csv_path = all_areas_csv_path
        self.areas = self._load_areas()

    def _load_areas(self):
        areas = {}
        areas_csv_path = Path(self.all_areas_csv_path)
        if areas_csv_path.exists():
            with areas_csv_path.open("r", encoding="utf-8") as file:
                reader = csv.reader(file)
                next(reader, None)
                for row in reader:
                    if len(row) == len(CSV_HEADERS_AREA):
                        area_data = dict(zip(CSV_HEADERS_AREA, row))
                        areas[row[0]] = area_data
        return areas

    @retry_on_failure()
    def generate_new_adventure(self, adventure_name, result, area_name):
        """新しい冒険概要を生成し、CSVに追加する。"""
        area_info = self.areas.get(area_name)
        if not area_info:
            raise ValueError(f"エリア '{area_name}' が見つかりません。")

        area_dir = DATA_DIR / area_name
        area_dir.mkdir(parents=True, exist_ok=True)
        area_csv_path = get_area_csv_path(area_name)

        if not area_csv_path.exists():
            self._add_to_csv(area_csv_path, [], headers=CSV_HEADERS_ADVENTURE)

        prompt_kwargs = {
            "area_name": area_name,
            "result": RESULT_TEMPLATE[result],
            "adventure_name": adventure_name,
        }

        # AREA_INFO_KEYS_FOR_PROMPT を利用して area_data から値を取得
        for i, key in enumerate(AREA_INFO_KEYS_FOR_PROMPT):
            prompt_kwargs[key.lower()] = area_info[CSV_HEADERS_AREA[i]]

        contents = self.generate(
            response_format=TYPE_JSON,
            **prompt_kwargs
        )
        csv_contents = [adventure_name, result] + contents
        self._add_to_csv(area_csv_path, csv_contents)
        return csv_contents

    def extract(self, response):
        try:
            json_str = self._extract_json_string(response)
            data = json5.loads(json_str)
            self._validate_adventure_data(data)
            contents = [f"{chapter_data['title']}:{chapter_data['content']}" for chapter_data in data.get("chapters", [])]
            return contents
        except json.JSONDecodeError as e:
            print("JSONデコードエラー:", response)
            raise ValueError(f"無効なJSON形式: {str(e)}") from e

    def _extract_json_string(self, response):
        pattern = r"```json\n(.*?)```"
        match = re.search(pattern, response, re.DOTALL)
        if match:
            return match.group(1).strip()
        else:
            return response

    def _validate_adventure_data(self, data):
        root_keys = {"result", "chapters"}
        if not root_keys.issubset(data.keys()):
            raise ValueError(f"ルートキーが不足しています。必須キー: {root_keys}")
        chapters = data.get("chapters", [])
        if len(chapters) != 8:
            raise ValueError(f"章の数が無効です: {len(chapters)}/8")
        for i, chapter in enumerate(chapters, 1):
            if not isinstance(chapter, dict):
                raise ValueError(f"第{i}章はオブジェクトである必要があります。")
            required_keys = {"number", "title", "content"}
            missing_keys = required_keys - chapter.keys()
            if missing_keys:
                raise ValueError(f"第{i}章にキーが不足しています: {missing_keys}")
            if chapter.get("number") != f"{i}章":
                raise ValueError(f"第{i}章の番号が一致しません: {chapter.get('number')}")
            content = chapter.get("content")
            if NG_WORDS.intersection(content.split()):
                raise ValueError(f"第{i}章にNGワードが含まれています: {content}")

    def sort_csv(self, file_path):
        def sort_key(row):
            match = re.match(r'^(失敗|成功|大成功)(\d+)_', row[0])
            if match:
                prefix, number = match.groups()
                number = int(number)
            else:
                prefix, number = '', 0
            prefix_order = {
                '失敗': 0,
                '成功': 1,
                '大成功': 2
            }
            return (prefix_order.get(prefix, 3), number)
        with open(file_path, 'r', encoding='utf-8') as file:
            reader = csv.reader(file)
            headers = next(reader)
            rows = [row for row in reader if row]
        rows.sort(key=sort_key)
        with open(file_path, 'w', encoding='utf-8', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(headers)
            writer.writerows(rows)


class LogGenerator(BaseGenerator):
    CHAPTER_SETTINGS = CHAPTER_SETTINGS

    def __init__(self, chat_client, all_areas_csv_path):
        super().__init__(chat_client)
        self.all_areas_csv_path = all_areas_csv_path
        self.area_header_keywords = self._generate_area_header_keywords() # ヘッダーごとのキーワード抽出設定
        self.areas = self._load_areas()

    def _generate_area_header_keywords(self):
        return {
            CSV_HEADERS_AREA[4]: r"([^:]+):", # "生物名:" 形式
            CSV_HEADERS_AREA[6]: r"([^:]+):", # "生物名:" 形式
            CSV_HEADERS_AREA[7]: r"([^:]+):", # "アイテム名:" 形式
            CSV_HEADERS_AREA[8]: r"([^:]+)", # 財宝名 (シンプルな名詞)
        }

    def _load_areas(self):
        areas = {}
        areas_csv_path = Path(self.all_areas_csv_path)
        if areas_csv_path.exists():
            with areas_csv_path.open("r", encoding="utf-8") as file:
                reader = csv.reader(file)
                next(reader, None)
                for row in reader:
                    if len(row) == len(CSV_HEADERS_AREA):
                        area_data = dict(zip(CSV_HEADERS_AREA, row))
                        for header, keyword_regex in self.area_header_keywords.items(): # 各ヘッダーに対してキーワード抽出
                            header_text = area_data.get(header, "")
                            keywords = [name.strip() for name in re.findall(keyword_regex, header_text)] # 正規表現でキーワード抽出
                            area_data[f"{header}_keywords"] = keywords # キーワードリストをarea_dataに追加 (例: "生息する無害な生物_keywords")
                        areas[row[0]] = area_data # エリア名をキーとして辞書を保存
        return areas

    def _load_chapters(self, area_csv_path, adventure_name):
        area_csv_path = Path(area_csv_path)
        if not area_csv_path.exists():
            raise ValueError(f"ファイルが見つかりません: {area_csv_path}")
        with area_csv_path.open("r", encoding="utf-8") as file:
            reader = csv.reader(file)
            next(reader, None)
            for row in reader:
                if row and row[0] == adventure_name:
                    return row[2:]
            raise ValueError(f"冒険 '{adventure_name}' が見つかりません。")

    @retry_on_failure()
    def generate_log(self, area_name, adventure_name, i_chapter, pre_log=None):
        area_info = self.areas.get(area_name)
        if not area_info:
            raise ValueError(f"エリア '{area_name}' が見つかりません。")
        
        setting = self.CHAPTER_SETTINGS[i_chapter]
        template_file = setting.get("template_file", NEW_LOG_TEMPLATE_FILE)
        area_csv_path = get_area_csv_path(area_name)
        adventure_txt_path = get_adventure_txt_path(area_name, adventure_name)
        chapters = self._load_chapters(area_csv_path, adventure_name)
        chapter_text = chapters[i_chapter]
        kwargs = {
            "before_chapter": setting.get("before_chapter", ""),
            "chapter": chapter_text,
            "after_chapter": setting.get("after_chapter", ""),
            "before_log": BEFORE_LOG_TEMPLATE["with_pre_log"].format(pre_log=pre_log) if i_chapter != 0 and pre_log else BEFORE_LOG_TEMPLATE["default"]
        }

        # 章テキストに含まれるエリア情報に基づいてarea_info_textを生成
        area_info_text = "- **エリア情報の活用：**  \n  エリア情報を、**物語の背景、イベント、オブジェクト、登場人物、会話などに自然に組み込んでください。**  冒険者がエリア情報を直接的に語るのではなく、**体験を通して**エリア情報が**間接的に**読者に伝わるように工夫してください。\n"
        are_info_added = False
        if area_name in chapter_text.lower():
            area_info_text += f"  - {CSV_HEADERS_AREA[0].lower()}: {area_info[CSV_HEADERS_AREA[0]]}\n"
            area_info_text += f"  - {CSV_HEADERS_AREA[2].lower()}: {area_info[CSV_HEADERS_AREA[2]]}\n"
            are_info_added = True
        for header in CSV_HEADERS_AREA: # すべてのヘッダーをチェック
            keywords = area_info.get(f"{header}_keywords", []) # キーワードリストを取得 (例: "生息する無害な生物_keywords")
            if keywords: # キーワードリストが存在する場合のみチェック
                for keyword in keywords:
                    if keyword.lower() in chapter_text.lower(): # 章テキストにキーワードが含まれているか確認 (小文字で比較)
                        area_value = area_info.get(header) # ヘッダーに対応するテキスト全体を取得
                        if area_value:
                            area_info_text += f"  - {header}: {area_value}\n" # 文字列として整形
                            are_info_added = True

        if are_info_added: # 何か情報が追加された場合のみarea_infoをkwargsに追加
            kwargs["area_info"] = area_info_text.strip() # 余分な改行を削除
        else:
            kwargs["area_info"] = ""

        self.template = self._load_template(template_file)
        log_contents = self.generate(response_format=TYPE_TEXT, **kwargs)
        self._add_to_txt(adventure_txt_path, log_contents)
        return log_contents

    def extract(self, response):
        filtered_lines = []
        for line in response.strip().splitlines():
            stripped_line = line.strip()
            if stripped_line.startswith('##'):
                continue
            match = re.match(r'^\d+\.\s(.*)', stripped_line)
            if match:
                content_line = match.group(1)
                if not NG_WORDS.intersection(content_line.split()):
                    filtered_lines.append(content_line)
                else:
                    raise ValueError(f"NGワードが含まれています: {content_line}")
        if not filtered_lines:
            raise ValueError("抽出されたコンテンツが空です。")
        if len(filtered_lines) < 20:
            raise ValueError("抽出されたコンテンツの行数が20行未満です。")
        return '\n'.join(filtered_lines) + '\n'


def parse_arguments():
    parser = argparse.ArgumentParser(description="エリア、冒険、ログジェネレータ")
    parser.add_argument(
        "--client",
        choices=["gemini", "groq"],
        default="gemini",
        help="使用するチャットクライアント (gemini または groq, デフォルト: gemini)"
    )
    parser.add_argument(
        "--model",
        default=None,
        help="使用するモデル名 (指定しない場合はクライアントのデフォルトモデルを使用)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="デバッグモード (各処理で最初の1件のみ実行、またプロンプト/レスポンスを表示)"
    )
    subparsers = parser.add_subparsers(dest="type", required=True)

    # エリア生成サブコマンド
    area_parser = subparsers.add_parser("area", help="エリアを生成")
    area_parser.add_argument(
        "count",
        type=int,
        nargs='?',
        default=1,
        help="エリア生成の実行回数 (デフォルト: 1)"
    )

    # 冒険生成サブコマンド（オプションで result 指定可能）
    adventures_parser = subparsers.add_parser("adventures", help="冒険を生成")
    adventures_parser.add_argument(
        "result",
        nargs="?",
        default=None,
        help="生成する冒険の結果フィルター (例: 大成功)"
    )

    # ログ生成サブコマンド
    subparsers.add_parser("logs", help="ログを生成")
    return parser.parse_args()


def generate_area_content(area_generator, count):
    # DEBUG_MODE が True の場合、実行回数を 1 に制限
    if DEBUG_MODE:
        count = 1
    for _ in range(count):
        new_area_csv = area_generator.generate_new_area()
        new_area_name = new_area_csv[0]
        print(f"✅ エリア: {new_area_name}")


def process_adventures_content(adventure_generator, result_filter=None):
    areas = adventure_generator._load_areas()
    for area_name in areas:
        add_adventures_for_area(adventure_generator, area_name, result_filter=result_filter)
        area_csv_path = get_area_csv_path(area_name)
        adventure_generator.sort_csv(file_path=area_csv_path)
        if DEBUG_MODE:
            break  # DEBUG_MODE 時は最初の1エリアのみ実行


def add_adventures_for_area(adventure_generator, area_name, result_filter=None):
    adventure_types = [
        {"result": "失敗", "nums": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]},
        {"result": "成功", "nums": [1, 2, 3, 4, 5, 6, 7, 8, 9]},
        {"result": "大成功", "nums": [1]},
    ]
    # result フィルターが指定された場合、対象の結果のみ実行
    if result_filter:
        adventure_types = [at for at in adventure_types if at["result"] == result_filter]

    area_csv_path = get_area_csv_path(area_name)
    already_exist_adventures_in_area = load_existing_adventures_for_area(area_csv_path)
    for adventure_type in adventure_types:
        for idx, num in enumerate(adventure_type["nums"]):
            adventure_name = f"{adventure_type['result']}{num}_{area_name}"
            if adventure_name not in already_exist_adventures_in_area:
                adventure_generator.generate_new_adventure(adventure_name, adventure_type["result"], area_name)
                print(f"✅ 冒険: {adventure_name}")
            if DEBUG_MODE:
                break  # DEBUG_MODE 時は1件のみ実行
        if DEBUG_MODE:
            break


def load_existing_adventures_for_area(area_csv_path):
    area_csv_path = Path(area_csv_path)
    if area_csv_path.exists():
        with area_csv_path.open("r", encoding="utf-8") as file:
            reader = csv.reader(file)
            next(reader, None)
            return [row[0] for row in reader if row]
    return []


def process_logs_content(log_generator):
    areas_dir = DATA_DIR
    area_dirs = [d for d in areas_dir.iterdir() if d.is_dir()]
    for area_dir in area_dirs:
        area_name = area_dir.name
        area_csv_path = get_area_csv_path(area_name)
        if area_csv_path.exists():
            generate_logs_for_area(log_generator, area_name, area_csv_path)
        if DEBUG_MODE:
            break  # DEBUG_MODE 時は最初の1エリアのみ実行


def generate_logs_for_area(log_generator, area_name, area_csv_path):
    area_csv_path = Path(area_csv_path)
    if not area_csv_path.exists():
        return
    with area_csv_path.open("r", encoding="utf-8") as file:
        reader = csv.reader(file)
        next(reader, None)
        for row in reader:
            if not row:
                continue
            adventure_name, result, *chapters = row
            adventure_txt_path = get_adventure_txt_path(area_name, adventure_name)
            if not adventure_txt_path.exists():
                pre_log = None
                for i in range(len(CHAPTER_SETTINGS)):
                    pre_log = log_generator.generate_log(
                        area_name=area_name,
                        adventure_name=adventure_name,
                        i_chapter=i,
                        pre_log=pre_log,
                    )
                    print(f"✅ ログ {i+1}/{len(CHAPTER_SETTINGS)}: {adventure_txt_path}")
                    # if DEBUG_MODE:
                    #     # DEBUG_MODE 時は各冒険で1チャプターのみ生成し、ファイルを削除して確認可能にする
                    #     adventure_txt_path.unlink(missing_ok=True)
                    #     print(f"🔥 ログ : {adventure_txt_path}")
                    #     break
            else:
                continue
            if DEBUG_MODE:
                break


def main():
    global DEBUG_MODE
    args = parse_arguments()
    DEBUG_MODE = args.debug  # グローバルにデバッグフラグを設定

    if args.client == "gemini":
        model_name = args.model if args.model else "models/gemini-2.0-flash-001"
        chat_client = GeminiChat(model_name)
    elif args.client == "groq":
        model_name = args.model if args.model else "gemma2-9b-it"
        chat_client = GroqChat(model_name)
    else:
        raise ValueError(f"不明なチャットクライアント: {args.client}")

    area_generator = AreaGenerator(chat_client, all_areas_csv_path=AREAS_CSV_FILE)
    adventure_generator = AdventureGenerator(chat_client, all_areas_csv_path=AREAS_CSV_FILE)
    log_generator = LogGenerator(chat_client, all_areas_csv_path=AREAS_CSV_FILE)

    if args.type == "area":
        generate_area_content(area_generator, args.count)
    elif args.type == "adventures":
        process_adventures_content(adventure_generator, result_filter=args.result)
    elif args.type == "logs":
        process_logs_content(log_generator)


if __name__ == "__main__":
    main()
