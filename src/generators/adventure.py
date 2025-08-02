from dataclasses import dataclass
from typing import List, Dict, Optional
from pathlib import Path
import random

from src.core.generator import ContentGenerator
from src.core.client import ResponseFormat
from src.generators.extract import ImpactData
from src.utils.csv_handler import CSVHandler


@dataclass
class Item:
    name: str

@dataclass
class AdventureData:
    name: str
    result: str
    chapters: List[str]
    items: List[str]
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
        decided_item = self._decide_item(area_name, result)
        chapters_n = 8 if result == "大成功" else (random.randint(3, 8) if result == "成功" else random.randint(2, 8))
        response = self.generate(
            response_format=ResponseFormat.JSON,
            result=self.config.result_template[result],
            simple_result=result,
            item=decided_item,
            chapters_n=chapters_n,
            adventure_name=name,
            debug=debug,
            **self._prepare_area_prompt_data(area_info)
        )
        content = self.extract_json(response)
        self.validate_content(content)
        return self.create_data(name, result, content, decided_item=decided_item)

    def generate_new_locked_adventure(self, name: str, result: str, area_name: str, impact_data: ImpactData, prev_adventure_name: str, debug: bool = False) -> AdventureData:
        area_info = self._get_area_info(area_name)
        decided_item = self._decide_item(area_name, result)
        chapters_n = 8 if result == "大成功" else (random.randint(3, 8) if result == "成功" else random.randint(2, 8))
        response = self.generate(
            response_format=ResponseFormat.JSON,
            result=self.config.result_template[result],
            simple_result=result,
            item=decided_item,
            chapters_n=chapters_n,
            precursor_traces=self._parse_traces_to_bullet_items(impact_data.traces),
            precursor_impacts=self._parse_impacts_to_bullet_items(impact_data.world_impacts),
            adventure_name=name,
            debug=debug,
            **self._prepare_area_prompt_data(area_info)
        )
        content = self.extract_json(response)
        self.validate_content(content)
        return self.create_data(name, result, content, previous=prev_adventure_name, decided_item=decided_item)

    def _get_area_info(self, area_name: str) -> Dict:
        if area_name not in self.areas:
            raise ValueError(f"Area not found: {area_name}")
        return self.areas[area_name]

    def _prepare_area_prompt_data(self, area_info: Dict) -> Dict:
        return {
            key.lower(): area_info[self.config.csv_headers_area[i]]
            for i, key in enumerate(self.config.area_info_keys_for_prompt)
        }

    def create_data(self, name: str, result: str, content: Dict, previous: str = "なし", next_: str = "なし", decided_item: Optional[str] = None) -> AdventureData:
        item = None
        if result == "成功":
            item = decided_item
        elif result == "大成功":
            item = decided_item
        items = [item] if item else []
        return AdventureData(
            name=name,
            result=result,
            chapters=self._parse_listcontent(content["chapters"]),
            items=items,
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
        result = []
        for c in listcontent:
            title = (c.get("title") or "").strip() if isinstance(c, dict) else ""
            content = (c.get("content") or "").strip() if isinstance(c, dict) else ""
            if title and content:
                result.append(f"{title}:{content}")
        return result

    def _pick_success_item(self, area_name: Optional[str]) -> Optional[str]:
        if not area_name:
            return None
        items_cell = self.areas.get(area_name, {}).get("採取できるアイテム", "")
        candidates = []
        for token in str(items_cell).split(";"):
            token = token.strip()
            if not token:
                continue
            name = token.split(":", 1)[0].strip()
            if name:
                candidates.append(name)
        if not candidates:
            return None
        return random.choice(candidates)

    def _get_treasure_name(self, area_name: Optional[str]) -> Optional[str]:
        if not area_name:
            return None
        treasure_cell = self.areas.get(area_name, {}).get("財宝", "")
        if not treasure_cell:
            return None
        name = treasure_cell.split(":", 1)[0].strip()
        return name or None

    def _decide_item(self, area_name: str, result: str) -> Optional[str]:
        if result == "成功":
            return self._pick_success_item(area_name)
        if result == "大成功":
            return self._get_treasure_name(area_name)
        return None

    def validate_content(self, content: Dict) -> None:
        root_keys = {"result", "chapters"}
        if not root_keys.issubset(content.keys()):
            raise ValueError(f"ルートキーが不足しています。必須キー: {root_keys}")
        chapters = content.get("chapters", [])
        if not isinstance(chapters, list) or len(chapters) == 0:
            raise ValueError("章の配列が無効です")
        filtered = []
        for i, ch in enumerate(chapters, 1):
            if not isinstance(ch, dict):
                continue
            title = (ch.get("title") or "").strip()
            body = (ch.get("content") or "").strip()
            number = ch.get("number")
            if title and body and number:
                filtered.append(ch)
        n = len(filtered)
        res = content.get("result", "")
        if res == "大成功" and n != 8:
            raise ValueError("大成功は8章である必要があります")
        if res == "成功" and not (3 <= n <= 8):
            raise ValueError("成功は3〜8章の範囲である必要があります")
        if res == "失敗" and not (2 <= n <= 8):
            raise ValueError("失敗は2〜8章の範囲である必要があります")
        item = content.get("item")
        if res in ("成功", "大成功") and isinstance(item, list):
            raise ValueError("itemは配列ではなく文字列")
        if res == "失敗" and item != "None":
            raise ValueError("失敗ではitemは空である必要があります")
        for i, chapter in enumerate(filtered, 1):
            required_keys = {"number", "title", "content"}
            missing_keys = required_keys - chapter.keys()
            if missing_keys:
                raise ValueError(f"第{i}章にキーが不足しています: {missing_keys}")
            content_text = chapter.get("content")
            if set(self.config.ng_words).intersection(content_text.split()):
                raise ValueError(f"第{i}章にNGワードが含まれています: {content_text}")
        content["chapters"] = filtered


    def save(self, adventure_data: AdventureData, csv_path: Path) -> None:
        max_chapters = 8
        chapters = list(adventure_data.chapters)
        if len(chapters) < max_chapters:
            chapters += [""] * (max_chapters - len(chapters))
        row = [
            adventure_data.name,
            adventure_data.previous,
            adventure_data.next_,
            adventure_data.result,
            *chapters[:max_chapters],
            ";".join(adventure_data.items) if adventure_data.items else "None"
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