import csv
import json
import re

import json5
from config import CHECK_LOG_TEMPLATE_FILE, LOGCHECK_KEYS, LOGCHECK_HEADERS
from generators import BaseGenerator
from llm import TYPE_TEXT, retry_on_failure


class LogChecker(BaseGenerator):
    def __init__(self, chat_client, template_file=CHECK_LOG_TEMPLATE_FILE):
        super().__init__(chat_client, template_file)
        self.json_pattern = re.compile(r"```json\n(.*?)\n```", re.DOTALL)
        self.expected_keys = LOGCHECK_KEYS
        self.csv_headers = LOGCHECK_HEADERS

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
        csv_row = []
        csv_row.append(adv_name)
        for section_keys in self.expected_keys.values(): # セクションごとのキーを処理
            for key in section_keys:
                section_name = list(self.expected_keys.keys())[list(self.expected_keys.values()).index(section_keys)] # セクション名を取得
                value = json_data[section_name][key]["評価"] + json_data[section_name][key]["理由"]
                csv_row.append(value)
        csv_row.append(json_data["総合評価"])
        return csv_row

    def save_check_result_csv(self, json_data, adv_name, csv_path):
        csv_row = self._json_to_csv_row(adv_name, json_data)
        try:
            self._add_to_csv(csv_path, csv_row, headers=self.csv_headers) # CSV保存処理を呼び出し
        except Exception as e:
            print(f"CSVファイルへの保存中にエラーが発生しました: {e}")

    @retry_on_failure()
    def check_log(self, summary, log, adv_name, csv_path=None):
        check_result_json = self.generate(
            response_format=TYPE_TEXT,
            summary=summary,
            log=log,
            temperature=0
        )
        return check_result_json
    
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
                return False  # セクションが存在しない場合は False
            if not isinstance(check_result_json[section_name], dict):
                print(f"セクション '{section_name}' は辞書型である必要があります。")
                return False  # セクションが辞書型でない場合は False
            for key in keys:
                if key not in check_result_json[section_name]:
                    print(f"セクション '{section_name}' にキー '{key}' が存在しません。")
                    return False  # キーが存在しない場合は False
                if "評価" not in check_result_json[section_name][key]:
                    print(f"セクション '{section_name}' のキー '{key}' に '評価' フィールドが存在しません。")
                    return False  # 評価フィールドが存在しない場合は False
                if check_result_json[section_name][key]["評価"] != "✅":
                    return False  # 評価が "✅" でない場合は False
        return True  # すべての評価が "✅" の場合は True