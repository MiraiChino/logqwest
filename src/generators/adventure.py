from dataclasses import dataclass
from typing import List, Dict, Optional
from pathlib import Path

from src.core.generator import ContentGenerator
from src.core.client import ResponseFormat
from src.generators.extract import ImpactData
from src.utils.csv_handler import CSVHandler


@dataclass
class AdventureData:
    name: str
    result: str
    chapters: List[str]
    previous: Optional[str] = "なし"
    next_: Optional[str] = "なし"

class AdventureGenerator(ContentGenerator):
    def __init__(self, client, template_path: Path, areas_csv_paths: List[Path], config_manager):
        super().__init__(client, template_path)
        self.csv_handler = CSVHandler()
        self.areas_csv_paths = areas_csv_paths
        self.config = config_manager
        self.areas = self._load_area_data()

    def _load_area_data(self) -> Dict[str, Dict]:
        area_data = {}
        for areas_csv_path in self.areas_csv_paths:
            for row in self.csv_handler.read_rows(areas_csv_path):
                area_name = row["エリア名"]
                area_data[area_name] = row
        return area_data

    def generate_new_adventure(self, name: str, result: str, area_name: str, debug: bool = False) -> AdventureData:
        area_info = self._get_area_info(area_name)
        
        response = self.generate(
            response_format=ResponseFormat.JSON,
            result=self.config.result_template[result],
            simple_result=result,
            adventure_name=name,
            debug=debug,
            **self._prepare_area_prompt_data(area_info)
        )
        content = self.extract_json(response)
        self.validate_content(content)
        return self.create_data(name, result, content)

    def generate_new_locked_adventure(self, name: str, result: str, area_name: str, impact_data: ImpactData, prev_adventure_name: str, debug: bool = False) -> AdventureData:
        area_info = self._get_area_info(area_name)
        response = self.generate(
            response_format=ResponseFormat.JSON,
            result=self.config.result_template[result],
            simple_result=result,
            precursor_traces=self._parse_traces_to_bullet_items(impact_data.traces),
            precursor_impacts=self._parse_impacts_to_bullet_items(impact_data.world_impacts),
            adventure_name=name,
            debug=debug,
            **self._prepare_area_prompt_data(area_info)
        )
        content = self.extract_json(response)
        self.validate_content(content)
        return self.create_data(name, result, content, previous=prev_adventure_name)

    def _get_area_info(self, area_name: str) -> Dict:
        if area_name not in self.areas:
            raise ValueError(f"Area not found: {area_name}")
        return self.areas[area_name]

    def _prepare_area_prompt_data(self, area_info: Dict) -> Dict:
        return {
            key.lower(): area_info[self.config.csv_headers_area[i]]
            for i, key in enumerate(self.config.area_info_keys_for_prompt)
        }

    def create_data(self, name: str, result: str, content: Dict, previous: str = "なし", next_: str = "なし") -> AdventureData:
        return AdventureData(
            name=name,
            result=result,
            chapters=self._parse_listcontent(content["chapters"]),
            previous=previous,
            next_=next_
        )

    def _parse_traces_to_bullet_items(self, traces: List[Dict]) -> str:
        def trace_to_str(trace):
            id = trace["id"]
            name = trace["trace_name"]
            desc = trace["trace_description"]
            location = trace["location_details"]
            reason = trace["reasoning"]
            return self._parse_nested_bullet_items(f"痕跡{id}: {name}", [f"詳細: {desc}", f"場所: {location}", f"経緯: {reason}"])
        return '\n'.join(trace_to_str(trace) for trace in traces)

    def _parse_impacts_to_bullet_items(self, impacts: List[Dict]) -> str:
        def impact_to_str(impact):
            id = impact["impact_id"]
            name = impact["impact_name"]
            desc = impact["impact_description"]
            scope = impact["affected_scope"]
            reason = impact["reasoning"]
            return self._parse_nested_bullet_items(f"影響{id}: {name}", [f"詳細: {desc}", f"影響範囲: {scope}", f"経緯: {reason}"])
        return '\n'.join(impact_to_str(impact) for impact in impacts)

    def _parse_nested_bullet_items(self, name:str, listcontent: List[str]) -> str:
        result = f"    * {name}\n"
        result += '\n'.join(f"      * {c}" for c in listcontent)
        return result

    def _parse_listcontent(self, listcontent: List):
        return [f"{c["title"]}:{c["content"]}" for c in listcontent]

    def validate_content(self, content: Dict) -> None:
        root_keys = {"result", "chapters"}
        if not root_keys.issubset(content.keys()):
            raise ValueError(f"ルートキーが不足しています。必須キー: {root_keys}")
        chapters = content.get("chapters", [])
        if len(chapters) != len(self.config.chapter_settings):
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
            if set(self.config.ng_words).intersection(content.split()):
                raise ValueError(f"第{i}章にNGワードが含まれています: {content}")

    def save(self, adventure_data: AdventureData, csv_path: Path) -> None:
        row = [
            adventure_data.name,
            adventure_data.previous,
            adventure_data.next_,
            adventure_data.result,
            *adventure_data.chapters
        ]
        self.csv_handler.write_row(csv_path, row, headers=self.config.csv_headers_adventure)
        self.csv_handler.sort_by_result(csv_path)

    def update_previous_adventure(self, csv_path: str, adventure_name: str, next_adventure_name: str) -> None:
        self.csv_handler.update_col2_if_col1_equals_value(
            file_path=csv_path,
            col1_name="冒険名",
            col2_name="次の冒険",
            target_value=adventure_name,
            new_value=next_adventure_name
        )