from pathlib import Path
from typing import List, Dict
import csv

class CSVHandler:
    def __init__(self):
        self.current_path = None
    def read_rows(self, file_path: Path) -> List[Dict]:
        self.current_path = file_path
        if not file_path.exists():
            return []
            
        with file_path.open('r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            return [row for row in reader]

    def write_row(self, file_path: Path, row: List[str], headers: List[str] = None):
        self.current_path = file_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_exists = file_path.exists()
        with file_path.open("a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            if not file_exists and headers:
                writer.writerow(headers)
            writer.writerow(row)

    def sort_by_result(self, file_path: Path):
        self.current_path = file_path
        rows = self.read_rows(file_path)
        sorted_rows = sorted(
            rows,
            key=lambda x: (
                {'失敗': 0, '成功': 1, '大成功': 2}.get(x.get('結果', ''), 3),
                int(x.get('番号', 0))
            )
        )
        self._write_sorted_rows(sorted_rows)

    def _write_sorted_rows(self, rows: List[Dict]) -> None:
        if not rows:
            return
            
        headers = list(rows[0].keys())
        with self.current_path.open('w', encoding='utf-8', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)
