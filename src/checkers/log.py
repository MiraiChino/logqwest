from typing import Dict

from src.core.checker import ContentChecker

class LogChecker(ContentChecker):

    def check_log(self, summary: str, log: str, adventure_name: str) -> Dict:
        content = self.generate(summary=summary, log=log, adventure_name=adventure_name)
        if self.validate_content(content):
            pass
        if self.is_all_checked(content):
            pass
        return content
