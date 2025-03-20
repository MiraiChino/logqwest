from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

from src.core.generator import ContentGenerator
from src.core.client import ResponseFormat
from src.utils.csv_handler import CSVHandler
from src.utils.validators import ContentValidator, ValidationRules
from src.utils.retry import retry_on_failure


@dataclass
class AreaData:
    name: str
    geographic_features: str
    history_legend: str
    risks_challenges: str
    treasure: str
    treasure_location: str
    items: List[str]
    dangerous_creatures: List[str]
    harmless_creatures: List[str]
    waypoints: List[str]
    cities: List[str]
    routes: List[str]
    rest_points: List[str]

class AreaGenerator(ContentGenerator):
    def __init__(self, client, template_path: Path, areas_csv_path: Path, config_manager):
        super().__init__(client, template_path)
        self.csv_handler = CSVHandler()
        self.areas_csv_path = areas_csv_path
        self.config_manager = config_manager
        self.areas = self._load_existing_areas()
        self.validator_rules = ValidationRules(
            forbidden_words=self.config_manager.ng_words,
            required_area_fields=self.config_manager.csv_headers_area,
            existing_area_names=list(self.areas.keys()),
            existing_treasure_names=[area.treasure for area in self.areas.values()]
        )
        self.validator = ContentValidator(self.validator_rules)

    def _load_existing_areas(self) -> Dict[str, AreaData]:
        areas_data = {}
        for row in self.csv_handler.read_rows(self.areas_csv_path):
            area_data = AreaData(
                name=row["エリア名"],
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
            areas_data[area_data.name] = area_data
        return areas_data

    def _parse_semicolon_list(self, text: str) -> List[str]:
        return [item.split(":")[0].strip() for item in text.split(";") if ":" in item]

    @retry_on_failure()
    def generate_new_area(self, reference_count: int = 0, area_name: Optional[str] = None) -> AreaData:
        existing_areas = self._format_reference_areas(reference_count)
        response = self.generate(
            response_format=ResponseFormat.TEXT,
            existing_areas=existing_areas,
            area_name=area_name or "新エリアの名称を記載してください。ありがちな命名パターン（例:忘れられし~、星詠みの~、魂喰らいの~など）や既存エリアの命名規則から脱却し、全く新しい名前にしてください。"
        )
        content = self.extract_json(response)
        self.validate_content(content)
        return self.create_data(content)

    def _format_reference_areas(self, count: int) -> str:
        formatted_areas = []
        for area in list(self.areas.values())[:count]:
            formatted_areas.append(f"{area.name},{area.treasure},{';'.join(area.waypoints)},{';'.join(area.cities)}")
        return "\n".join(formatted_areas)

    def validate_content(self, content: Dict) -> None:
        try:
            self.validator.validate_area_content(content) # ContentValidator でバリデーション
            if not self.validator.validate_area_name(content["エリア名"]): # エリア名のバリデーション
                raise ValueError(f"エリア名が既存のエリア名と重複しているか、禁止文字が含まれています: {content['エリア名']}")
            if not self.validator.validate_treasure_name(content["財宝"]["名称"]): # 財宝名のバリデーション
                treasure_name = content["財宝"]["名称"]
                raise ValueError(f"財宝名が既存の財宝名と重複しています: {treasure_name}")
        except ValueError as e:
            print(f"バリデーションエラー: {e}")
            raise e # バリデーションエラーを再raise

    def _parse_listcontent(self, listcontent: List):
        return [f"{c["名称"]}: {c["特徴"]}" for c in listcontent]

    def create_data(self, content: Dict) -> AreaData:
        return AreaData(
            name=content["エリア名"],
            geographic_features=content["地理的特徴"],
            history_legend=content["歴史や伝説"],
            risks_challenges=content["リスクや挑戦"],
            treasure=f'{content["財宝"]["名称"]}: {content["財宝"]["特徴"]}',
            treasure_location=content["財宝の隠し場所"],
            items=self._parse_listcontent(content["採取できるアイテム"]),
            dangerous_creatures=self._parse_listcontent(content["生息する危険な生物"]),
            harmless_creatures=self._parse_listcontent(content["生息する無害な生物"]),
            waypoints=self._parse_listcontent(content["経由地候補"]),
            cities=self._parse_listcontent(content["近くの街"]),
            routes=self._parse_listcontent(content["移動路"]),
            rest_points=self._parse_listcontent(content["休憩ポイント"])
        )

    def save(self, area_data: AreaData) -> None:
        row = [
            area_data.name,
            area_data.geographic_features,
            area_data.history_legend,
            area_data.risks_challenges,
            area_data.treasure,
            area_data.treasure_location,
            ";".join(area_data.items),
            ";".join(area_data.dangerous_creatures),
            ";".join(area_data.harmless_creatures),
            ";".join(area_data.waypoints),
            ";".join(area_data.cities),
            ";".join(area_data.routes),
            ";".join(area_data.rest_points),
        ]
        self.csv_handler.write_row(self.areas_csv_path, row, headers=self.config_manager.csv_headers_area)
