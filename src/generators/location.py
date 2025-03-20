from dataclasses import dataclass
from typing import Dict, List
from pathlib import Path

from src.core.generator import ContentGenerator
from src.core.client import ResponseFormat
from src.utils.csv_handler import CSVHandler

@dataclass
class LocationInfo:
    area: str
    waypoints: List[str]
    cities: List[str]
    routes: List[str]
    rest_points: List[str]

class LocationGenerator(ContentGenerator):
    def __init__(self, client, template_path: Path, areas_csv_path: Path):
        super().__init__(client, template_path)
        self.csv_handler = CSVHandler()
        self.areas_csv_path = areas_csv_path
        self.areas = self._load_area_locations()

    def _load_area_locations(self) -> Dict[str, LocationInfo]:
        return {
            row["エリア名"]: LocationInfo(
                area=f"  - {row['エリア名']}:{row['地理的特徴']}",
                waypoints=self._parse_locations(row["経由地候補"]),
                cities=self._parse_locations(row["近くの街"]),
                routes=self._parse_locations(row["移動路"]),
                rest_points=self._parse_locations(row["休憩ポイント"])
            )
            for row in self.csv_handler.read_rows(self.areas_csv_path)
        }

    def _parse_locations(self, location_text: str) -> List[str]:
        return [
            f"  - {entry.strip()}"
            for entry in location_text.split(';')
            if entry.strip()
        ]

    def generate_location(self, area_name: str, log_content: str, location_candidates: Dict = None) -> str:
        numbered_log_text, len_lines = self._format_log_content(log_content)
        if location_candidates is None:
            location_candidates = self.get_location_candidates(area_name)
        response = self.generate(
            response_format=ResponseFormat.JSON,
            log=numbered_log_text,
            **location_candidates
        )
        content = self.extract_json(response)
        self.validate_content(content, len_lines)
        return self.create_data(content)
        
    def _format_log_content(self, log_content: str) -> str:
        lines = log_content.splitlines()
        # 各行の先頭に行番号を付ける
        numbered_lines = [f"{i+1}: {line}" for i, line in enumerate(lines)]
        len_lines = len(numbered_lines)
        numbered_log_text = '\n'.join(numbered_lines)
        return numbered_log_text, len_lines

    def get_location_candidates(self, area_name: str) -> Dict[str, str]:
        if area_name not in self.areas:
            raise ValueError(f"Area not found: {area_name}")
        location_info = self.areas[area_name]
        return self._format_location_candidates(location_info)

    def _format_location_candidates(self, location_info: LocationInfo) -> Dict[str, str]:
        return {
            "area": location_info.area,
            "waypoint": "\n".join(location_info.waypoints),
            "city": "\n".join(location_info.cities),
            "route": "\n".join(location_info.routes),
            "restpoint": "\n".join(location_info.rest_points)
        }

    def validate_content(self, content: str, len_lines: int):
        if len(content) != len_lines:
            raise ValueError(f"テキストの長さが異なります: {len(content)} != {len_lines}")

        if not content:
            raise ValueError("抽出されたコンテンツが空です。")

        if len(content) < 20:
            raise ValueError("抽出されたコンテンツの行数が20行未満です。")

    def create_data(self, content: str) -> str:
        return '\n'.join(content.values())
