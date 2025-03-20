from dataclasses import dataclass
from typing import List, Dict
from pathlib import Path

from src.core.generator import ContentGenerator
from src.core.client import ResponseFormat
from src.utils.csv_handler import CSVHandler


@dataclass
class AdventureData:
    name: str
    result: str
    chapters: List[str]

class AdventureGenerator(ContentGenerator):
    def __init__(self, client, template_path: Path, areas_csv_path: Path, config_manager):
        super().__init__(client, template_path)
        self.csv_handler = CSVHandler()
        self.areas_csv_path = areas_csv_path
        self.config_manager = config_manager
        self.areas = self._load_area_data()

    def _load_area_data(self) -> Dict[str, Dict]:
        return {row["エリア名"]: row for row in self.csv_handler.read_rows(self.areas_csv_path)}

    def generate_new_adventure(self, name: str, result: str, area_name: str) -> AdventureData:
        area_info = self._get_area_info(area_name)
        
        response = self.generate(
            response_format=ResponseFormat.JSON,
            result=result,
            adventure_name=name,
            **self._prepare_area_prompt_data(area_info)
        )
        content = self.extract_json(response)
        self.validate_content(content)
        return self.create_data(name, result, content)

    def _get_area_info(self, area_name: str) -> Dict:
        if area_name not in self.areas:
            raise ValueError(f"Area not found: {area_name}")
        return self.areas[area_name]

    def _prepare_area_prompt_data(self, area_info: Dict) -> Dict:
        return {
            key.lower(): area_info[self.config_manager.csv_headers_area[i]]
            for i, key in enumerate(self.config_manager.area_info_keys_for_prompt)
        }

    def create_data(self, name: str, result: str, content: Dict) -> AdventureData:
        return AdventureData(
            name=name,
            result=result,
            chapters=self._parse_listcontent(content["chapters"])
        )

    def _parse_listcontent(self, listcontent: List):
        return [f"{c["title"]}:{c["content"]}" for c in listcontent]

    def validate_content(self, content: Dict) -> None:
        root_keys = {"result", "chapters"}
        if not root_keys.issubset(content.keys()):
            raise ValueError(f"ルートキーが不足しています。必須キー: {root_keys}")
        chapters = content.get("chapters", [])
        if len(chapters) != len(self.config_manager.chapter_settings):
            raise ValueError(f"章の数が無効です: {len(chapters)}/8")
        for i, chapter in enumerate(chapters, 1):
            if not isinstance(chapter, dict):
                raise ValueError(f"第{i}章はオブジェクトである必要があります。")
            required_keys = {"number", "title", "content"}
            missing_keys = required_keys - chapter.keys()
            if missing_keys:
                raise ValueError(f"第{i}章にキーが不足しています: {missing_keys}")
            if chapter.get("number") != f"{i}章":
                raise ValueError(f"第{i}章の番号が一致しません: {chapter.get('number')}")
            content = chapter.get("content")
            if self.config_manager.ng_words.intersection(content.split()):
                raise ValueError(f"第{i}章にNGワードが含まれています: {content}")

    def save(self, adventure_data: AdventureData, csv_path: Path) -> None:
        row = [
            adventure_data.name,
            adventure_data.result,
            *adventure_data.chapters
        ]
        self.csv_handler.write_row(csv_path, row, headers=self.config_manager.csv_headers_adventure)
        self.csv_handler.sort_by_result(csv_path)
