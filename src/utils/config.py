from dataclasses import dataclass
from typing import Dict, List
from pathlib import Path
import json


@dataclass
class PathConfig:
    data_dir: Path
    check_result_dir: Path
    prompt_dir: Path
    config_file: Path

class ConfigManager:
    def __init__(self, config_path: Path):
        self.config = self._load_json(config_path)

    def _load_json(self, config_path: Path) -> Dict:
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
            
        with config_path.open(encoding="utf-8") as f:
            return json.load(f)

    @property
    def check_marks(self) -> List[str]:
        return self.config.get("CHECK_MARKS", ["✅"])

    @property
    def max_retries(self) -> int:
        return self.config.get("MAX_RETRIES", 10)

    @property
    def paths(self) -> PathConfig:
        return PathConfig(
            data_dir=Path(self.config["DATA_DIR"]),
            check_result_dir=Path(self.config["CHECK_RESULT_DIR"]),
            prompt_dir=Path(self.config["PROMPT_DIR"]),
            config_file=Path(self.config["CONFIG_FILE"])
        )

    @property
    def area_check_keys(self) -> List[str]:
        return self.config.get("AREACHECK_KEYS", [])

    @property
    def adventure_check_keys(self) -> List[str]:
        return self.config.get("ADVCHECK_KEYS", [])

    @property
    def locked_adventure_check_keys(self) -> List[str]:
        return self.config.get("LOCKED_ADVCHECK_KEYS", [])

    @property
    def log_check_keys(self) -> List[str]:
        return self.config.get("LOGCHECK_KEYS", [])


    @property
    def location_check_keys(self) -> List[str]:
        return self.config.get("LOCATIONCHECK_KEYS", [])

    @property
    def area_name_prompt(self) -> str:
        return self.config.get("AREA_NAME_PROMPT", "")

    @property
    def ng_words(self) -> List[str]:
        return self.config.get("NG_WORDS", [])

    @property
    def result_template(self) -> str:
        return self.config.get("RESULT_TEMPLATE", "")

    @property
    def area_info_text(self) -> str:
        return self.config.get("AREA_INFO_TEXT", "")

    @property
    def csv_headers_area(self) -> List[str]:
        return self.config.get("CSV_HEADERS_AREA", [])

    @property
    def csv_headers_adventure(self) -> List[str]:
        return self.config.get("CSV_HEADERS_ADVENTURE", [])

    @property
    def csv_headers_unlocks(self) -> List[str]:
        return self.config.get("CSV_HEADERS_UNLOCKS", [])

    @property
    def chapter_settings(self) -> List[Dict]:
        return self.config.get("CHAPTER_SETTINGS", [])

    @property
    def area_info_keys_for_prompt(self) -> List[str]:
        return self.config.get("AREA_INFO_KEYS_FOR_PROMPT", [])

    @property
    def before_log_template(self) -> Dict[str, str]:
        return self.config.get("BEFORE_LOG_TEMPLATE", {})

    @property
    def ending_line(self) -> str:
        return self.config.get("ENDING_LINE", "冒険は終了")

    @property
    def item_value_table(self) -> Dict[str, int]:
        return self.config.get("ITEM_VALUE_TABLE", {})
