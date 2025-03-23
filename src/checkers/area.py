from typing import Dict, List
from src.core.checker import ContentChecker
from src.generators.area import AreaData

class AreaChecker(ContentChecker):

    def check_area(self, area_data: AreaData, existing_df) -> Dict:
        content = self.generate(
            area_name=area_data.name,
            difficulty=area_data.difficulty,
            geography=area_data.geographic_features,
            history=area_data.history_legend,
            risk=area_data.risks_challenges,
            treasure=area_data.treasure,
            treasure_location=area_data.treasure_location,
            collectibles=self._parse_dict_to_bullet_items(area_data.items),
            dangerous_creatures=self._parse_dict_to_bullet_items(area_data.dangerous_creatures),
            harmless_creatures=self._parse_dict_to_bullet_items(area_data.harmless_creatures),
            waypoint=self._parse_dict_to_bullet_items(area_data.waypoints),
            city=self._parse_dict_to_bullet_items(area_data.cities),
            route=self._parse_dict_to_bullet_items(area_data.routes),
            restpoint=self._parse_dict_to_bullet_items(area_data.rest_points),
            existing_areas=self._parse_bullet_items(existing_df["エリア名"].tolist() if len(existing_df["エリア名"].to_list()) > 0 else ["既存のデータは未だありません"]),
            existing_treasures=self._parse_parsed_list_to_bullet_items(existing_df["財宝"].tolist()),
            existing_collectibles=self._parse_parsed_list_to_bullet_items(existing_df["採取できるアイテム"].tolist()),
            existing_harmless_creatures=self._parse_parsed_list_to_bullet_items(existing_df["生息する無害な生物"].tolist()),
            existing_dangerous_creatures=self._parse_parsed_list_to_bullet_items(existing_df["生息する危険な生物"].tolist()),
        )
        if self.validate_content(content):
            pass
        if self.is_all_checked(content):
            pass
        return content

    def _parse_parsed_list_to_bullet_items(self, parsed_list: List) -> List[str]:
        if len(parsed_list) == 0:
            unparse_listcontent = ["既存のデータは未だありません"]
        else:
            unparse_listcontent = [self._unparse_listcontent(parsed) for parsed in parsed_list]
            
        return self._parse_bullet_items(unparse_listcontent)

    def _unparse_listcontent(self, parsed: str) -> List[str]:
        result = []
        if not parsed:
            return result
        # セミコロンで分割
        items = parsed.split(";")
        for item in items:
            # 空文字列が含まれている場合はスキップ
            if not item.strip():
                continue
            # ": " を区切り文字として分割
            try:
                name, feature = item.split(": ", 1)
            except ValueError:
                # フォーマットに沿っていない場合はスキップまたは例外を投げる
                continue
            result.append(name)
        return result

    def _parse_dict_to_bullet_items(self, listcontent: List) -> str:
        return self._parse_bullet_items(self._parse_dict(listcontent))

    def _parse_dict(self, listcontent: List) -> List[str]:
        return [f"{c["名称"]}: {c["特徴"]}" for c in listcontent]

    def _parse_bullet_items(self, listcontent: List) -> str:
        return '\n'.join(f"  * {c}" for c in listcontent)

    def save(self, results: Dict, csv_path) -> None:
        if "area_name" not in results:
            raise ValueError("resultsに 'area_name' キーが含まれている必要があります。")
        area_name = results["area_name"]
        csv_row = self._format_csv_row(area_name, results)
        self.csv_handler.write_row(csv_path, csv_row, headers=["エリア名"] + self.check_keys)
        self.csv_handler.sort_by_result(csv_path)