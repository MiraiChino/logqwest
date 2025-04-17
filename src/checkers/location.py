from typing import Dict

from src.core.checker import ContentChecker

class LocationChecker(ContentChecker):

    def check_location(self, log_with_location: str, location_candidates: Dict, adventure_name: str, debug: bool = False) -> Dict:
        content = self.generate(
            log=log_with_location,
            area=location_candidates["area"],
            waypoint=location_candidates["waypoint"],
            city=location_candidates["city"],
            route=location_candidates["route"],
            restpoint=location_candidates["restpoint"],
            adventure_name=adventure_name,
            debug=debug,
        )
        if self.validate_content(content):
            pass
        if self.is_all_checked(content):
            pass
        return content
