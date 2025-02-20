import json
import re

import json5
from config import CHECK_LOG_TEMPLATE_FILE
from generators import BaseGenerator
from llm import TYPE_TEXT, retry_on_failure


class LogChecker(BaseGenerator):
    def __init__(self, chat_client, template_file=CHECK_LOG_TEMPLATE_FILE):
        super().__init__(chat_client, template_file)
        self.json_pattern = re.compile(r"```json\n(.*?)\n```", re.DOTALL)
        self.expected_keys = {
            "整合性チェック": ["ストーリー展開", "冒険結果", "冒険目的とアイテム", "登場人物と場所", "戦闘と障害"],
            "読みやすさチェック": ["言語と文体", "フォーマット", "内容"],
            "日本語の自然さ・言語チェック": ["日本語の自然さ", "他言語混入"],
            "時間表現チェック": ["現在進行形のストーリー", "絶対的な時間表現の排除"],
        }
        self.csv_headers = [ # CSVヘッダーを定義
            "冒険名",
            "ストーリー展開_評価", "ストーリー展開_理由",
            "冒険結果_評価", "冒険結果_理由",
            "冒険目的とアイテム_評価", "冒険目的とアイテム_理由",
            "登場人物と場所_評価", "登場人物と場所_理由",
            "戦闘と障害_評価", "戦闘と障害_理由",
            "言語と文体_評価", "言語と文体_理由",
            "フォーマット_評価", "フォーマット_理由",
            "内容_評価", "内容_理由",
            "日本語の自然さ_評価", "日本語の自然さ_理由",
            "他言語混入_評価", "他言語混入_理由",
            "現在進行形のストーリー_評価", "現在進行形のストーリー_理由",
            "絶対的な時間表現の排除_評価", "絶対的な時間表現の排除_理由",
            "総合評価"
        ]

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
                csv_row.append(json_data[section_name][key]["評価"])
                csv_row.append(json_data[section_name][key]["理由"])
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
        if check_result_json and csv_path:
            self.save_check_result_csv(check_result_json, adv_name, csv_path)
        return check_result_json
