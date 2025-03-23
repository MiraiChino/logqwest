from pathlib import Path
from typing import Optional, List, Iterator
from dataclasses import dataclass
import json

import pandas as pd

USER_DATA_FILE = Path("user_data") / "history.json"
@dataclass
class FileStructure:
    data_dir: Path
    check_result_dir: Path
    prompt_dir: Path

class FileHandler:
    def __init__(self, file_structure: FileStructure):
        self.structure = file_structure
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        for directory in [self.structure.data_dir, 
                         self.structure.check_result_dir, 
                         self.structure.prompt_dir]:
            directory.mkdir(parents=True, exist_ok=True)

    def get_all_areas_csv_path(self) -> Path:
        return self.structure.data_dir / "areas.csv"

    def get_areas_dir(self) -> Path:
        return self.structure.data_dir

    def get_area_path(self, area_name: str) -> Path:
        return self.structure.data_dir / area_name

    def get_area_csv_path(self, area_name: str) -> Path:
        return self.get_area_path(area_name) / f"{area_name}.csv"

    def get_adventure_path(self, area_name: str, adventure_name: str) -> Path:
        return self.get_area_path(area_name) / f"{adventure_name}.txt"

    def get_location_path(self, area_name: str, adventure_name: str) -> Path:
        return self.get_area_path(area_name) / f"loc_{adventure_name}.txt"

    def get_check_area_path(self, area_name: str) -> Path:
        return self.structure.check_result_dir / area_name

    def get_check_path(self, area_name: str, check_type: str) -> Path:
        return self.structure.check_result_dir / area_name / f"{check_type}_{area_name}.csv"

    def get_all_areas_check_path(self) -> Path:
        return self.structure.check_result_dir / "areas.csv"

    def load_areas_csv(self) -> pd.DataFrame:
        areas_csv_path = self.get_all_areas_csv_path()
        return pd.read_csv(areas_csv_path) if areas_csv_path.exists() else None

    def load_area_csv(self, area_name: str) -> pd.DataFrame:
        area_csv_path = self.get_area_csv_path(area_name)
        return pd.read_csv(area_csv_path) if area_csv_path.exists() else None

    def load_area_adventures(self, area_name: str) -> List[str]:
        area_csv = self.get_area_csv_path(area_name)
        if not area_csv.exists():
            return []
            
        df = pd.read_csv(area_csv)
        return df["冒険名"].tolist() if "冒険名" in df.columns else []

    def load_all_area_names(self) -> List[str]:
        df = self.load_areas_csv()
        if df is None:
            return []
        return df["エリア名"].tolist() if "エリア名" in df.columns else []

    def load_check_csv(self, area_name: str, check_type: str) -> pd.DataFrame:
        check_csv_path = self.get_check_path(area_name, check_type)
        return pd.read_csv(check_csv_path) if check_csv_path.exists() else None

    def load_all_areas_check_csv(self) -> pd.DataFrame:
        check_csv_path = self.get_all_areas_check_path()
        return pd.read_csv(check_csv_path, sep=',') if check_csv_path.exists() else None

    def read_adventure_log(self, area_name: str, adventure_name: str) -> Optional[str]:
        return self.read_text(self.get_adventure_path(area_name, adventure_name))

    def read_text(self, file_path: Path) -> Optional[str]:
        if not file_path.exists():
            return None
        return file_path.read_text(encoding='utf-8')

    def write_text(self, file_path: Path, content: str, append: bool = False) -> None:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open('a' if append else 'w', encoding='utf-8') as f:
            f.write(content)

    def delete_files(self, area_name: str, adventure_names: List[str]) -> List[str]:
        deletion_log = []
        for adventure_name in adventure_names:
            for file_path in self._get_adventure_files(area_name, adventure_name):
                if file_path.exists():
                    file_path.unlink()
                    deletion_log.append(f"Deleted: {file_path}")
        return deletion_log

    def _get_adventure_files(self, area_name: str, adventure_name: str) -> List[Path]:
        return [
            self.get_adventure_path(area_name, adventure_name),
            self.get_location_path(area_name, adventure_name),
            *[self.get_check_path(area_name, check_type) 
              for check_type in ['log', 'adv', 'loc']]
        ]

    def area_exists(self, area_name: str) -> bool:
        area_path = self.get_area_path(area_name)
        area_csv = self.get_area_csv_path(area_name)
        return area_path.exists() and area_csv.exists()

    def delete_content(self, area_name: str, targets: List[str], content_type: str) -> List[str]:
        if content_type == "areas":
            return list(self._delete_areas(targets))
        elif content_type == "adventures":
            return list(self._delete_adventures(area_name, targets))
        elif content_type == "logs":
            return list(self._delete_logs(area_name, targets))
        elif content_type == "locations":
            return list(self._delete_locations(area_name, targets))
        return []

    def delete_folder(self, pth):
        for sub in pth.iterdir():
            if sub.is_dir():
                self.delete_folder(sub)
            else:
                sub.unlink()
        pth.rmdir()

    def _delete_areas(self, areas: List[str]) -> Iterator[str]:
        # Delete from areas CSV
        areas_csv_path = self.get_all_areas_csv_path()
        if areas_csv_path.exists():
            df_areas = pd.read_csv(areas_csv_path)
            df_areas = df_areas[~df_areas["エリア名"].isin(areas)]
            df_areas.to_csv(areas_csv_path, index=False)
            yield f"🔥 エリア一覧: {areas}"

        # Delete from area CSV
        for area in areas:
            #  Delete adventures
            adventures = self.load_area_adventures(area)
            yield from self._delete_adventures(area, adventures)

            area_csv_path = self.get_area_csv_path(area)
            area_path = self.get_area_path(area)
            check_area_path = self.get_check_area_path(area)
            if area_csv_path.exists():
                area_csv_path.unlink()
            if area_path.exists():
                self.delete_folder(area_path)
            if check_area_path.exists():
                self.delete_folder(check_area_path)
            yield f"🔥 エリア: {area}"

    def _delete_adventures(self, area_name: str, adventures: List[str]) -> Iterator[str]:
        # Delete from area CSV
        area_csv_path = self.get_area_csv_path(area_name)
        if area_csv_path.exists():
            df_area = pd.read_csv(area_csv_path)
            df_area = df_area[~df_area["冒険名"].isin(adventures)]
            df_area.to_csv(area_csv_path, index=False)
            yield f"🔥 冒険一覧: {adventures}"

        # Delete from adventure check CSV
        check_adv_path = self.get_check_path(area_name, "adv")
        if check_adv_path.exists():
            df_check = pd.read_csv(check_adv_path)
            df_check = df_check[~df_check["冒険名"].isin(adventures)]
            df_check.to_csv(check_adv_path, index=False)
            yield f"🔥 冒険ﾁｪｯｸ: {adventures}"

        # Cascade delete logs and locations
        yield from self._delete_logs(area_name, adventures)

    def _delete_logs(self, area_name: str, adventures: List[str]) -> Iterator[str]:
        # Delete log files
        for adv in adventures:
            log_path = self.get_adventure_path(area_name, adv)
            if log_path.exists():
                log_path.unlink()
                yield f"🔥 ログ: {log_path}"

        # Delete from log check CSV
        check_log_path = self.get_check_path(area_name, "log")
        if check_log_path.exists():
            df_check = pd.read_csv(check_log_path)
            df_check = df_check[~df_check["冒険名"].isin(adventures)]
            df_check.to_csv(check_log_path, index=False)
            yield f"🔥 ログﾁｪｯｸ: {adventures}"

        # Cascade delete locations
        yield from self._delete_locations(area_name, adventures)

    def _delete_locations(self, area_name: str, adventures: List[str]) -> Iterator[str]:
        # Delete location files
        for adv in adventures:
            loc_path = self.get_location_path(area_name, adv)
            if loc_path.exists():
                loc_path.unlink()
                yield f"🔥 位置: {loc_path}"

        # Delete from location check CSV
        check_loc_path = self.get_check_path(area_name, "loc")
        if check_loc_path.exists():
            df_check = pd.read_csv(check_loc_path)
            df_check = df_check[~df_check["冒険名"].isin(adventures)]
            df_check.to_csv(check_loc_path, index=False)
            yield f"🔥 位置ﾁｪｯｸ: {adventures}"

    def load_usage_data(self) -> dict:
        """
        使用履歴と収支情報をJSONファイルから読み込む。
        """
        user_data_file = USER_DATA_FILE
        try:
            with user_data_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if "adventure_history" not in data: # 初回起動時などでキーが存在しない場合
                    return {"adventure_history": []} # 空のリストで初期化
                data["adventure_history"].sort(key=lambda item: item["timestamp"], reverse=True)
                return data
        except (FileNotFoundError, json.JSONDecodeError):
            return {"adventure_history": []}

    def save_usage_data(self, data: dict):
        """使用履歴と収支情報をJSONファイルへ保存する。"""
        user_data_file = USER_DATA_FILE
        user_data_file.parent.mkdir(parents=True, exist_ok=True)
        with user_data_file.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
