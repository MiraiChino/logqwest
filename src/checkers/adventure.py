from typing import Dict
from src.core.checker import ContentChecker

class AdventureChecker(ContentChecker):

    def check_adventure(self, area: str, result: str, result_desc: str, summary: str, items_str: str, adventure_name: str, debug: bool = False) -> Dict:
        content = self.generate(
            area=area,
            result=result,
            result_desc=result_desc,
            summary=summary,
            items_str=items_str,
            adventure_name=adventure_name,
            debug=debug
        )
        if self.validate_content(content):
            pass
        if self.is_all_checked(content):
            pass
        return content
