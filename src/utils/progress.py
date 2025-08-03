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

        area_status = self.get_area_status(area)
        if all(path.exists() for path in [check_log, check_adv, check_loc]) and area_status.completion_ratio == 1.0 and area_status.check_ratio == 1.0:
            return True

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
        return len(list(f for f in area_path.glob("*.txt") if not f.name.startswith("loc_")))

    def _count_check_files(self, area_name: str) -> int:
        area_path = self.file_handler.get_area_path(area_name)
        return len(list(f for f in area_path.glob("*.txt") if f.name.startswith("loc_") and self._is_file_complete(f)))

    def _count_completed_files(self, area_name: str) -> int:
        area_path = self.file_handler.get_area_path(area_name)
        return len([f for f in area_path.glob("*.txt") 
                   if not f.name.startswith("loc_") and self._is_file_complete(f)])

    def is_adventure_complete(self, area_name: str, adventure_name: str) -> bool:
        adventure_path = self.file_handler.get_adventure_path(area_name, adventure_name)
        return self._is_file_complete(adventure_path)

    def is_adventure_checked(self, area_name: str, adventure_name: str, check_type: str) -> bool:
        check_df = self.file_handler.load_check_csv(area_name, check_type)
        return adventure_name in check_df['冒険名'].values if check_df is not None else False

    def is_adventure_all_checked(self, area_name: str, adventure_name: str) -> bool:
        if not self.is_adventure_checked(area_name, adventure_name, "adv"):
            return False
        if not self.is_adventure_checked(area_name, adventure_name, "log"):
            return False
        if not self.is_adventure_checked(area_name, adventure_name, "loc"):
            return False
        return True


    def _is_file_complete(self, file_path: Path, min_lines: int = 50) -> bool:
        if not file_path.exists():
            return False
        with file_path.open('r', encoding='utf-8') as f:
            return len(f.readlines()) >= min_lines