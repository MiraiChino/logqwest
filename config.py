import json
from pathlib import Path

CONFIG_FILE = "prompt/config.json"
CHECK_RESULT_DIR = Path("check_results")
PROMPT_DIR = Path("prompt")
DATA_DIR = Path("data") # generate.py で DATA_DIR を使うため、ここにも定義
AREAS_CSV_FILE = DATA_DIR / "areas.csv"
NEW_AREA_TEMPLATE_FILE = PROMPT_DIR / "new_area.txt"
NEW_ADVENTURE_TEMPLATE_FILE = PROMPT_DIR / "new_adventure.txt"
NEW_LOG_TEMPLATE_FILE = PROMPT_DIR / "new_log.txt"
CHECK_LOG_TEMPLATE_FILE = PROMPT_DIR / "check_log.txt"

# 設定ファイルのロード
def load_config(config_file):
    config_path = Path(config_file)
    if not config_path.exists():
        raise FileNotFoundError(f"{config_file} が見つかりません。")
    with config_path.open(encoding="utf-8") as f:
        return json.load(f)

config = load_config(CONFIG_FILE)

# 設定値のエクスポート
RESULT_TEMPLATE = config["RESULT_TEMPLATE"]
NG_WORDS = set(config["NG_WORDS"])
CSV_HEADERS_AREA = config["CSV_HEADERS_AREA"]
NEW_AREA_NAME_PROMPT = config["NEW_AREA_NAME_PROMPT"]
CSV_HEADERS_ADVENTURE = config["CSV_HEADERS_ADVENTURE"]
CHAPTER_SETTINGS = config["CHAPTER_SETTINGS"]
BEFORE_LOG_TEMPLATE = config["BEFORE_LOG_TEMPLATE"]
DEFAULT_WAIT_TIME = config.get("DEFAULT_WAIT_TIME", 10)
MAX_RETRIES = config.get("MAX_RETRIES", 30)
AREA_INFO_KEYS_FOR_PROMPT = config["AREA_INFO_KEYS_FOR_PROMPT"]
LOGCHECK_KEYS = config["LOGCHECK_KEYS"]
LOGCHECK_HEADERS = config["LOGCHECK_HEADERS"]