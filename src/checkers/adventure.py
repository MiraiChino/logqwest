from typing import Dict
from src.core.checker import ContentChecker

class AdventureChecker(ContentChecker):

    def check_adventure(self, area: str, summary: str, adventure_name: str) -> Dict:
        content = self.generate(area=area, summary=summary, adventure_name=adventure_name)
        if self.validate_content(content):
            pass
        if self.is_all_checked(content):
            pass
        return content
