from typing import Dict

from src.core.checker import ContentChecker

class LogChecker(ContentChecker):

    def check_log(self, summary: str, result: str, log: str, adventure_name: str, debug: bool = False) -> Dict:
        content = self.generate(summary=summary, result=result, log=log, adventure_name=adventure_name, debug=debug)
        if self.validate_content(content):
            pass
        if self.is_all_checked(content):
            pass
        return content
