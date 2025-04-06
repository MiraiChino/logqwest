from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

from src.core.generator import ContentGenerator
from src.core.client import ResponseFormat
from src.utils.csv_handler import CSVHandler
from src.utils.retry import retry_on_failure


@dataclass
class AreaData:
    name: str
    difficulty: str
    geographic_features: str
    history_legend: str
    risks_challenges: str
    treasure: str
    treasure_location: str
    items: List[Dict]
    dangerous_creatures: List[Dict]
    harmless_creatures: List[Dict]
    waypoints: List[Dict]
    cities: List[Dict]
    routes: List[Dict]
    rest_points: List[Dict]
    past_area_name: str = "なし"

class AreaGenerator(ContentGenerator):
    def __init__(self, client, template_path: Path, areas_csv_path: Path, config, past_areas_csv_path: Optional[Path] = None):
        super().__init__(client, template_path)
        self.csv_handler = CSVHandler()
        self.areas_csv_path = areas_csv_path
        self.past_areas_csv_path = past_areas_csv_path
        self.config = config
        self.areas = self._load_existing_areas()

    def _load_existing_areas(self) -> Dict[str, AreaData]:
        areas_data = {}
        if self.areas_csv_path.exists():
            for row in self.csv_handler.read_rows(self.areas_csv_path):
                area_data = self._row_to_areadata(row)
                areas_data[area_data.name] = area_data
        else:
            self.csv_handler.write_headers(self.areas_csv_path, self.config.csv_headers_area)
        
        if self.past_areas_csv_path is not None and self.past_areas_csv_path.exists():
            for row in self.csv_handler.read_rows(self.past_areas_csv_path):
                area_data = self._row_to_areadata(row)
                areas_data[area_data.name] = area_data
        else:
            self.csv_handler.write_headers(self.past_areas_csv_path, self.config.csv_headers_area)
        return areas_data

    def _row_to_areadata(self, row):
        return AreaData(
            name=row["エリア名"],
            past_area_name=row["過去エリア"],
            difficulty=row["難易度"].split(":")[0],
            geographic_features=row["地理的特徴"],
            history_legend=row["歴史や伝説"],
            risks_challenges=row["リスクや挑戦"],
            treasure=row["財宝"].split(":")[0],
            treasure_location=row["財宝の隠し場所"],
            items=row["採取できるアイテム"],
            dangerous_creatures=row["生息する危険な生物"],
            harmless_creatures=row["生息する無害な生物"],
            waypoints=self._parse_semicolon_list(row["経由地候補"]),
            cities=self._parse_semicolon_list(row["近くの街"]),
            routes=self._parse_semicolon_list(row["移動路"]),
            rest_points=self._parse_semicolon_list(row["休憩ポイント"])
        )

    def _parse_semicolon_list(self, text: str) -> List[str]:
        return [item.split(":")[0].strip() for item in text.split(";") if ":" in item]

    @retry_on_failure()
    def generate_new_area(self, reference_count: int = -1, area_name: Optional[str] = None, difficulty: int = 1) -> AreaData:
        existing_areas = self._format_reference_areas(reference_count)
        response = self.generate(
            response_format=ResponseFormat.TEXT,
            existing_areas=existing_areas,
            area_name=area_name or self.config.area_name_prompt,
            difficulty=difficulty
        )
        content = self.extract_json(response)
        content["過去エリア"] = "なし"
        self.validate_content(content, difficulty)
        return self.create_data(content)

    @retry_on_failure()
    def generate_new_locked_area(self, past_area_name, reference_count: int = -1, area_name: Optional[str] = None, difficulty: int = 1) -> AreaData:
        area_info = self._get_area_info(past_area_name)

        area_info.difficulty = difficulty
        response = self.generate(
            response_format=ResponseFormat.TEXT,
            new_area_name=area_name or self.config.area_name_prompt,
            **asdict(area_info)
        )
        content = self.extract_json(response)
        content["過去エリア"] = past_area_name
        self.validate_content(content, difficulty)
        return self.create_data(content)

    def _get_area_info(self, area_name: str) -> Dict:
        if area_name not in self.areas:
            raise ValueError(f"Area not found: {area_name}")
        return self.areas[area_name]

    def _format_reference_areas(self, count: int) -> str:
        formatted_areas = []
        if count == -1:
            count = len(self.areas)
        elif count > len(self.areas):
            count = len(self.areas)
        for area in list(self.areas.values())[:count]:
            formatted_areas.append(f"{area.name},{area.treasure},{';'.join(area.waypoints)},{';'.join(area.cities)}")
        return "\n".join(formatted_areas)

    def validate_content(self, content: Dict, difficulty) -> None:
        try:
            # 必須フィールドのチェック
            for field in self.config.csv_headers_area:
                if field not in content:
                    raise ValueError(f"必須フィールドがありません: {field}")
                if content[field] == "":
                    raise ValueError(f"必須フィールドが空です: {field}")

            # 難易度のチェック
            if str(difficulty) != str(content["難易度"]):
                raise ValueError(f"難易度が設定値と異なります: {difficulty} != {content['難易度']}")

            # NGワードチェック
            for field in self.config.csv_headers_area: # 全フィールドをチェック
                value = str(content.get(field, '')) # エラーを防ぐため get を使用し、文字列に変換
                if set(self.config.ng_words).intersection(value.split()):
                    raise ValueError(f"NGワードが含まれています: {field} - {value}")

            # エリア名のバリデーション
            areaname = content["エリア名"]
            for invalid_char in {'~', '〜', '〰', '|', '[', ']', '「', '」', '『', '』', ':', ';', '@', '/', '>'}:
                if invalid_char in areaname:
                    raise ValueError(f"エリア名に禁止文字{invalid_char}が含まれています: {areaname}")

            # エリア名の重複チェック
            existing_areas = list(self.areas.keys())
            for area in existing_areas:
                if area in areaname:
                    raise ValueError(f"エリア名が既存のエリア名と重複しています: {areaname}")
            if areaname in existing_areas:
                raise ValueError(f"エリア名が既存のエリア名と重複しています: {areaname}")

            # 財宝名のバリデーション
            treasure = content["財宝"]["名称"]
            for area in self.areas.values():
                existing_treasure = area.treasure
                if existing_treasure in treasure or treasure in existing_treasure:
                    raise ValueError(f"財宝名が既存の財宝名と重複しています: {treasure}")
        except ValueError as e:
            print(f"バリデーションエラー: {e}")
            raise e

    def _parse_listcontent(self, listcontent: List):
        return ";".join(f"{c["名称"]}: {c["特徴"]}" for c in listcontent)

    def create_data(self, content: Dict) -> AreaData:
        return AreaData(
            name=content["エリア名"],
            past_area_name=content.get("過去エリア", "なし"),
            difficulty=f'{content["難易度"]}: {content["難易度設定の根拠"]}',
            geographic_features=content["地理的特徴"],
            history_legend=content["歴史や伝説"],
            risks_challenges=content["リスクや挑戦"],
            treasure=f'{content["財宝"]["名称"]}: {content["財宝"]["特徴"]}',
            treasure_location=content["財宝の隠し場所"],
            items=content["採取できるアイテム"],
            dangerous_creatures=content["生息する危険な生物"],
            harmless_creatures=content["生息する無害な生物"],
            waypoints=content["経由地候補"],
            cities=content["近くの街"],
            routes=content["移動路"],
            rest_points=content["休憩ポイント"]
        )

    def save(self, area_data: AreaData) -> None:
        row = [
            area_data.name,
            area_data.past_area_name,
            area_data.difficulty,
            area_data.geographic_features,
            area_data.history_legend,
            area_data.risks_challenges,
            area_data.treasure,
            area_data.treasure_location,
            self._parse_listcontent(area_data.items),
            self._parse_listcontent(area_data.dangerous_creatures),
            self._parse_listcontent(area_data.harmless_creatures),
            self._parse_listcontent(area_data.waypoints),
            self._parse_listcontent(area_data.cities),
            self._parse_listcontent(area_data.routes),
            self._parse_listcontent(area_data.rest_points),
        ]
        self.csv_handler.write_row(self.areas_csv_path, row, headers=self.config.csv_headers_area)
