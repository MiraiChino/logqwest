from typing import Dict, List
from src.core.checker import ContentChecker

class AdventureChecker(ContentChecker):

    def validate_content(self, content: Dict) -> None:
        for section, keys in self.config.check_keys.items():
            if section not in content:
                raise ValueError(f"JSONレスポンスに'{section}' がありません。")
            if not isinstance(content[section], dict):
                raise ValueError(f"'{section}' は辞書型である必要があります。")
            for key in keys:
                if key not in content[section]:
                    raise ValueError(f"'{section}' に'{key}' がありません。")
                if not content[section][key]: # 値が空かどうかチェック
                    raise ValueError(f"'{section}' の'{key}' の値が空です。")
        if "総合評価" not in content:
            raise ValueError("JSONレスポンスに'総合評価' がありません。")
        if not content["総合評価"]: # 総合評価の値が空かどうかチェック
            raise ValueError("JSONレスポンスの'総合評価' の値が空です。")
        return True

    def check_adventure(self, area: str, summary: str, adventure_name: str) -> Dict:
        content = self.generate(area=area, summary=summary, adventure_name=adventure_name)
        if self.validate_content(content):
            pass
        if self.is_all_checked(content):
            pass
        return content

    def is_all_checked(self, check_result: Dict) -> bool:
        """
        check_result を引数に、check_result[section_name][key]["評価"] がすべて問題ないかどうかを返す関数
        """
        for section_name, keys in self.config.check_keys.items():
            if section_name not in check_result:
                raise ValueError(f"'{section_name}' が check_result に存在しません。")
            if not isinstance(check_result[section_name], dict):
                raise ValueError(f"'{section_name}' は辞書型である必要があります。")
            for key in keys:
                if key not in check_result[section_name]:
                    raise ValueError(f"'{section_name}' に'{key}' が存在しません。")
                if "評価" not in check_result[section_name][key]:
                    raise ValueError(f"'{section_name}' の'{key}' に '評価' フィールドが存在しません。")
                if check_result[section_name][key]["評価"] != self.config.check_mark:
                    raise ValueError(f"{section_name} - {key}: {check_result[section_name][key]["評価"]}{check_result[section_name][key]["理由"]}")
        return True

    def _format_csv_row(self, adventure_name: str, content: Dict) -> List[str]:
        row = [adventure_name]
        for section, checks in self.config.check_keys.items():
            for check in checks:
                row.append(f"{content[section][check]['評価']}{content[section][check]['理由']}")
        row.append(content["総合評価"])
        return row