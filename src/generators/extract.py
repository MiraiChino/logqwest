from typing import List, Dict
from pathlib import Path
from dataclasses import dataclass

from src.core.generator import ContentGenerator
from src.generators.area import AreaData
from src.utils.csv_handler import CSVHandler

@dataclass
class ImpactData:
    traces: List[Dict]
    world_impacts: List[Dict]

class Extractor(ContentGenerator):
    def __init__(self, client, template_path: Path, areas_csv_paths: List[Path], config_manager):
        super().__init__(client, template_path)
        self.areas_csv_paths = areas_csv_paths
        self.config = config_manager
        self.csv_handler = CSVHandler()
        self.areas = self._load_area_data()

    def _load_area_data(self) -> Dict[str, Dict]:
        area_data = {}
        for areas_csv_path in self.areas_csv_paths:
            for row in self.csv_handler.read_rows(areas_csv_path):
                area_name = row["エリア名"]
                area_data[area_name] = row
        return area_data

    def extract_log(self, new_area_name: str, pre_area_name: str, adventure_log: str, debug: bool = False):
        new_area = self._get_area_info(new_area_name)
        pre_area = self._get_area_info(pre_area_name)
        response = self.generate(
            previous_area_name=pre_area.name,
            pre_geography=pre_area.geographic_features,
            pre_history=pre_area.history_legend,
            pre_risk=pre_area.risks_challenges,
            pre_treasure=pre_area.treasure,
            pre_treasure_location=pre_area.treasure_location,
            pre_collectibles=self._parse_bullet_items(pre_area.items),
            pre_dangerous_creatures=self._parse_bullet_items(pre_area.dangerous_creatures),
            pre_harmless_creatures=self._parse_bullet_items(pre_area.harmless_creatures),
            pre_waypoint=self._parse_bullet_items(pre_area.waypoints),
            pre_city=self._parse_bullet_items(pre_area.cities),
            pre_route=self._parse_bullet_items(pre_area.routes),
            pre_restpoint=self._parse_bullet_items(pre_area.rest_points),
            new_area_name=new_area.name,
            geography=new_area.geographic_features,
            history=new_area.history_legend,
            risk=new_area.risks_challenges,
            treasure=new_area.treasure,
            treasure_location=new_area.treasure_location,
            collectibles=self._parse_bullet_items(new_area.items),
            dangerous_creatures=self._parse_bullet_items(new_area.dangerous_creatures),
            harmless_creatures=self._parse_bullet_items(new_area.harmless_creatures),
            waypoint=self._parse_bullet_items(new_area.waypoints),
            city=self._parse_bullet_items(new_area.cities),
            route=self._parse_bullet_items(new_area.routes),
            restpoint=self._parse_bullet_items(new_area.rest_points),
            adventure_log=adventure_log,
            debug=debug
        )
        content = self.extract_json(response)
        self.validate_content(content)
        return self.create_data(content)

    def _unparse_listcontent(self, parsed: str) -> List[str]:
        if not parsed:
            return []
        return parsed.split(";")

    def _parse_bullet_items(self, listcontent: List) -> str:
        return '\n'.join(f"  * {c}" for c in listcontent)

    def _get_area_info(self, area_name: str) -> Dict:
        if area_name not in self.areas:
            raise ValueError(f"Area not found: {area_name}")
        return self.create_areadata(self.areas[area_name])

    def create_data(self, content: Dict) -> Dict:
        return ImpactData(
            traces=content["traces"],
            world_impacts=content["world_impacts"],
        )

    def create_areadata(self, content: Dict) -> AreaData:
        return AreaData(
            name=content["エリア名"],
            prev_area_name=content.get("前のエリア", "なし"),
            next_area_name=content.get("次のエリア", "なし"),
            difficulty=content["難易度"],
            geographic_features=content["地理的特徴"],
            history_legend=content["歴史や伝説"],
            risks_challenges=content["リスクや挑戦"],
            treasure=content["財宝"],
            treasure_location=content["財宝の隠し場所"],
            items=self._unparse_listcontent(content["採取できるアイテム"]),
            dangerous_creatures=self._unparse_listcontent(content["生息する危険な生物"]),
            harmless_creatures=self._unparse_listcontent(content["生息する無害な生物"]),
            waypoints=self._unparse_listcontent(content["経由地候補"]),
            cities=self._unparse_listcontent(content["近くの街"]),
            routes=self._unparse_listcontent(content["移動路"]),
            rest_points=self._unparse_listcontent(content["休憩ポイント"])
        )

    def validate_content(self, content: Dict) -> None:
        root_keys = {"traces", "world_impacts"}
        if not root_keys.issubset(content.keys()):
            raise ValueError(f"ルートキーが不足しています。必須キー: {root_keys}")
        
        # traces
        traces = content.get("traces", [])
        if len(traces) < 1:
            raise ValueError(f"traceの数が無効です: {len(traces)}")
        for i, item in enumerate(traces, 1):
            if not isinstance(item, dict):
                raise ValueError("traceはdict形式である必要があります。")
            required_keys = {"id", "trace_name", "location_details", "reasoning", "trace_description"}
            missing_keys = required_keys - item.keys()
            if missing_keys:
                raise ValueError(f"traceにキーが不足しています: {missing_keys}")
            for k, v in item.items():
                if not v:
                    raise ValueError(f"{k}が空です。")
            
        # world_impacts
        world_impacts = item.get("world_impacts", [])
        if len(world_impacts) >= 1:
            raise ValueError(f"world_impactsの数が無効です: {len(world_impacts)}")
        for j, impact in enumerate(world_impacts, 1):
            if not isinstance(impact, dict):
                raise ValueError("impactはdict形式である必要があります。")
            required_keys = {"impact_id", "impact_name", "reasoning", "affected_scope", "impact_description"}
            missing_keys = required_keys - impact.keys()
            if missing_keys:
                raise ValueError(f"impactにキーが不足しています: {missing_keys}")
            for k, v in impact.items():
                if not v:
                    raise ValueError(f"{k}が空です。")