import csv
import json
import re
import time
from pathlib import Path

import json5
from llm import TYPE_JSON, TYPE_TEXT, retry_on_failure
from config import (
    NEW_AREA_TEMPLATE_FILE,
    NEW_ADVENTURE_TEMPLATE_FILE,
    NEW_LOG_TEMPLATE_FILE,
    RESULT_TEMPLATE,
    NG_WORDS,
    CSV_HEADERS_AREA,
    NEW_AREA_NAME_PROMPT,
    CSV_HEADERS_ADVENTURE,
    CHAPTER_SETTINGS,
    BEFORE_LOG_TEMPLATE,
    DEFAULT_WAIT_TIME,
    AREA_INFO_KEYS_FOR_PROMPT,
    DATA_DIR
)
from common import get_area_csv_path, get_adventure_path

# グローバル定数としてのデバッグフラグ（デフォルトは False）
DEBUG_MODE = False


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
        adventure_txt_path = get_adventure_path(area_name, adventure_name)
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