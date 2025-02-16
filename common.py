from pathlib import Path
import pandas as pd
import json

DATA_DIR = Path("data")

def get_area_csv_path(area: str) -> Path:
    """指定されたエリア名のCSVファイルパスを返す。"""
    return DATA_DIR / area / f"{area}.csv"

def get_adventure_path(area: str, adv: str) -> Path:
    """指定されたエリア内の冒険テキストファイルのパスを返す。"""
    return DATA_DIR / area / f"{adv}.txt"

def get_outcome_emoji(outcome: str) -> str:
    """結果に応じて絵文字を返す"""
    outcome_emojis = {
        "大成功": "💎",
        "成功": "🎁",
        "失敗": "❌",
    }
    return outcome_emojis.get(outcome, "")

def load_csv(csv_path: Path) -> pd.DataFrame:
    """
    CSVファイルを読み込みDataFrameを返す。
    ファイルが存在しない場合は None を返す。
    """
    return pd.read_csv(csv_path) if csv_path.exists() else None

USER_DATA_FILE = Path("user_data") / "history.json"

def load_usage_data(user_data_file: Path = USER_DATA_FILE) -> dict:
    """
    使用履歴と収支情報をJSONファイルから読み込む。
    """
    try:
        with user_data_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if "adventure_history" not in data: # 初回起動時などでキーが存在しない場合
                return {"adventure_history": []} # 空のリストで初期化
            data["adventure_history"].sort(key=lambda item: item["timestamp"], reverse=True)
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {"adventure_history": []}

def save_usage_data(data: dict, user_data_file: Path = USER_DATA_FILE):
    """使用履歴と収支情報をJSONファイルへ保存する。"""
    user_data_file.parent.mkdir(parents=True, exist_ok=True)
    with user_data_file.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)