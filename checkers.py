import csv
import json
import re

import json5
from config import CHECK_LOG_TEMPLATE_FILE, LOGCHECK_KEYS, LOGCHECK_HEADERS, CHECK_ADVENTURE_TEMPLATE_FILE, ADVCHECK_KEYS, ADVCHECK_HEADERS
from generators import BaseGenerator
from llm import TYPE_TEXT, retry_on_failure


class BaseChecker(BaseGenerator):
    def __init__(self, chat_client, template_file):
        super().__init__(chat_client, template_file)
        self.json_pattern = re.compile(r"```json\n(.*?)\n```", re.DOTALL)
        # expected_keys, csv_headers は子クラスで定義

    def extract(self, response):
        match = self.json_pattern.search(response)
        if match:
            json_text = match.group(1).strip()
            try:
                contents = json5.loads(json_text)
                if self.validate_json_structure(contents):
                    return contents
                else:
                    print("JSONレスポンスの構造が不正です。バリデーションに失敗しました。")
                    return None
            except json.JSONDecodeError as e:
                print(f"JSONデコードエラーが発生しました:\n{e}")
                print("レスポンスから抽出されたJSONテキスト:\n", json_text)
                return None
        else:
            print("レスポンスからJSONコードブロックを抽出できませんでした。")
            print("レスポンス:\n", response)
            return None

    def validate_json_structure(self, json_data):
        for section, keys in self.expected_keys.items():
            if section not in json_data:
                print(f"JSONレスポンスに必須セクション '{section}' がありません。")
                return False
            if not isinstance(json_data[section], dict):
                print(f"セクション '{section}' は辞書型である必要があります。")
                return False
            for key in keys:
                if key not in json_data[section]:
                    print(f"セクション '{section}' に必須キー '{key}' がありません。")
                    return False
                if not json_data[section][key]: # 値が空かどうかチェック
                    print(f"セクション '{section}' のキー '{key}' の値が空です。")
                    return False
        if "総合評価" not in json_data:
            print("JSONレスポンスに必須キー '総合評価' がありません。")
            return False
        if not json_data["総合評価"]: # 総合評価の値が空かどうかチェック
            print("JSONレスポンスの必須キー '総合評価' の値が空です。")
            return False
        return True

    def _json_to_csv_row(self, adv_name, json_data):
        csv_row = [adv_name]
        for section_name, keys in self.expected_keys.items():
            for key in keys:
                value = json_data[section_name][key]["評価"] + json_data[section_name][key]["理由"]
                csv_row.append(value)
        csv_row.append(json_data["総合評価"])
        return csv_row

    def save_check_result_csv(self, json_data, adv_name, csv_path):
        csv_row = self._json_to_csv_row(adv_name, json_data)
        try:
            self._add_to_csv(csv_path, csv_row, headers=self.csv_headers)
        except Exception as e:
            print(f"CSVファイルへの保存中にエラーが発生しました: {e}")

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

    def is_all_checked(self, check_result_json):
        """
        check_result_json を引数に、check_result_json[section_name][key]["評価"] がすべて✅かどうかを返す関数
        """
        for section_name, keys in self.expected_keys.items():
            if section_name not in check_result_json:
                print(f"セクション '{section_name}' が check_result_json に存在しません。")
                return False
            if not isinstance(check_result_json[section_name], dict):
                print(f"セクション '{section_name}' は辞書型である必要があります。")
                return False
            for key in keys:
                if key not in check_result_json[section_name]:
                    print(f"セクション '{section_name}' にキー '{key}' が存在しません。")
                    return False
                if "評価" not in check_result_json[section_name][key]:
                    print(f"セクション '{section_name}' のキー '{key}' に '評価' フィールドが存在しません。")
                    return False
                if check_result_json[section_name][key]["評価"] != "✅":
                    return False
        return True

    def get_generate_kwargs(self, area, summary):
        return {"area": area, "summary": summary}

    @retry_on_failure()
    def check(self, area, summary):
        generate_kwargs = self.get_generate_kwargs(area, summary)
        extracted_json = self.generate(
            response_format=TYPE_TEXT,
            temperature=0,
            **generate_kwargs
        )
        return extracted_json


class LogChecker(BaseChecker):
    def __init__(self, chat_client, template_file=CHECK_LOG_TEMPLATE_FILE):
        super().__init__(chat_client, template_file)
        self.expected_keys = LOGCHECK_KEYS
        self.csv_headers = LOGCHECK_HEADERS

    def get_generate_kwargs(self, summary, log):
        return {"summary": summary, "log": log}

    @retry_on_failure()
    def check_log(self, summary, log):
        return self.check(summary, log)


class AdventureChecker(BaseChecker):
    def __init__(self, chat_client, template_file=CHECK_ADVENTURE_TEMPLATE_FILE):
        super().__init__(chat_client, template_file)
        self.expected_keys = ADVCHECK_KEYS
        self.csv_headers = ADVCHECK_HEADERS

    def get_generate_kwargs(self, area, summary):
        return {"area": area, "summary": summary}

    @retry_on_failure()
    def check_adventure(self, area, summary):
        return self.check(area, summary)