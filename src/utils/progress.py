from dataclasses import dataclass
from typing import Dict
from pathlib import Path

@dataclass
class ProgressStatus:
    total: int
    completed: int
    checked: int
    
    @property
    def completion_ratio(self) -> float:
        return self.completed / self.total if self.total > 0 else 0.0

    @property
    def check_ratio(self) -> float:
        return self.checked / self.total if self.total > 0 else 0.0

class ProgressTracker:
    def __init__(self, file_handler):
        self.file_handler = file_handler

    def is_area_complete(self, area: str) -> bool:
        area_csv = self.file_handler.get_area_csv_path(area)
        if not area_csv.exists():
            return False
            
        adventures = self.file_handler.load_area_adventures(area)
        completed_count = sum(1 for adv in adventures 
                            if self._is_file_complete(self.file_handler.get_adventure_path(area, adv)))
        return completed_count == len(adventures)

    def is_area_all_checked(self, area: str) -> bool:
        check_log = self.file_handler.get_check_path(area, "log")
        check_adv = self.file_handler.get_check_path(area, "adv")
        check_loc = self.file_handler.get_check_path(area, "loc")
        
        return all(path.exists() for path in [check_log, check_adv, check_loc])

    def get_area_status(self, area_name: str) -> ProgressStatus:
        adventure_files = self._count_adventure_files(area_name)
        check_files = self._count_check_files(area_name)
        completed_files = self._count_completed_files(area_name)
        
        return ProgressStatus(
            total=adventure_files,
            completed=completed_files,
            checked=check_files
        )

    def get_all_areas_status(self) -> Dict[str, ProgressStatus]:
        return {
            area.name: self.get_area_status(area.name)
            for area in self.file_handler.get_area_path().iterdir()
            if area.is_dir()
        }

    def _count_adventure_files(self, area_name: str) -> int:
        area_path = self.file_handler.get_area_path(area_name)
        return len(list(area_path.glob("*.txt")))

    def _count_check_files(self, area_name: str) -> int:
        check_path = self.file_handler.get_check_path(area_name, "log")
        return len(list(check_path.parent.glob("*.csv")))

    def _count_completed_files(self, area_name: str) -> int:
        area_path = self.file_handler.get_area_path(area_name)
        return len([f for f in area_path.glob("*.txt") 
                   if self._is_file_complete(f)])

    def is_adventure_complete(self, area_name: str, adventure_name: str) -> bool:
        adventure_path = self.file_handler.get_adventure_path(area_name, adventure_name)
        return self._is_file_complete(adventure_path)

    def _is_file_complete(self, file_path: Path, min_lines: int = 160) -> bool:
        if not file_path.exists():
            return False
        with file_path.open('r', encoding='utf-8') as f:
            return len(f.readlines()) >= min_lines