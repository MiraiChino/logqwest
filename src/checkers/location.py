from typing import Dict, List

from src.core.checker import ContentChecker

class LocationChecker(ContentChecker):
    def validate_content(self, content: Dict) -> bool:
        for key in self.config.check_keys:
            if key not in content:
                raise ValueError(f"JSONレスポンスに必須キー '{key}' がありません。")
            if not content[key]: # 値が空かどうかチェック
                raise ValueError(f"キー '{key}' の値が空です。")
        if "総合評価" not in content:
            raise ValueError("JSONレスポンスに必須キー '総合評価' がありません。")
        if not content["総合評価"]:
            raise ValueError("JSONレスポンスの必須キー '総合評価' の値が空です。")
        return True

    def check_location(self, log_with_location: str, location_candidates: Dict, adventure_name: str) -> Dict:
        content = self.generate(
            log=log_with_location,
            area=location_candidates["area"],
            waypoint=location_candidates["waypoint"],
            city=location_candidates["city"],
            route=location_candidates["route"],
            restpoint=location_candidates["restpoint"],
            adventure_name=adventure_name
        )
        if self.validate_content(content):
            pass
        if self.is_all_checked(content):
            pass
        return content
    
    def is_all_checked(self, check_result: Dict) -> bool:
        for key in self.config.check_keys:
            if key not in check_result:
                raise ValueError(f"キー '{key}' が存在しません。")
            if "評価" not in check_result[key]:
                raise ValueError(f"キー '{key}' に '評価' フィールドが存在しません。")
            if check_result[key]["評価"] != self.config.check_mark:
                raise ValueError(f"{key}: {check_result[key]["評価"]}{check_result[key]["理由"]}")
        return True
    
    def _format_csv_row(self, adventure_name: str, content: Dict) -> List[str]:
        row = [adventure_name]
        for key in self.config.check_keys:
            value = content[key]["評価"] + content[key]["理由"]
            row.append(value)
        row.append(content["総合評価"])
        return row
