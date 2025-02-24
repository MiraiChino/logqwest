import duckdb
import pandas as pd
from pathlib import Path
import json

from config import CHECK_RESULT_DIR, DATA_DIR

def get_check_log_csv_path(area: str) -> Path:
    """指定されたエリア名のログチェックCSVファイルパスを返す。"""
    return CHECK_RESULT_DIR / area / f"log_{area}.csv"

def get_check_adv_csv_path(area: str) -> Path:
    """指定されたエリア名の冒険チェックCSVファイルパスを返す。"""
    return CHECK_RESULT_DIR / area / f"adv_{area}.csv"

def get_data_path() -> Path:
    return DATA_DIR

def get_area_csv_path(area: str) -> Path:
    """指定されたエリア名のCSVファイルパスを返す。"""
    return DATA_DIR / area / f"{area}.csv"

def get_adventure_path(area: str, adv: str) -> Path:
    """指定されたエリア内の冒険テキストファイルのパスを返す。"""
    return DATA_DIR / area / f"{adv}.txt"

def delete_adventures(area: str, advs_to_delete: list):
    """
    指定された area に対して、
    ・get_check_adv_csv_path の「冒険名」列に該当する行を削除
    ・get_area_csv_path の「冒険名」列に該当する行を削除
    """
    # get_check_adv_csv_path の処理
    check_results_path = Path(get_check_adv_csv_path(area))
    if check_results_path.exists():
        df_check = pd.read_csv(check_results_path)
        if "冒険名" in df_check.columns:
            df_check = df_check[~df_check["冒険名"].isin(advs_to_delete)]
            df_check.to_csv(check_results_path, index=False)
            yield f"🔥 削除: {advs_to_delete} from {check_results_path}"
        else:
            yield f"❗ エラー: {check_results_path} に '冒険名' 列が見つかりません"
    else:
        yield f"❌ 見つかりません: {check_results_path}"

    # get_area_csv_path の処理
    area_csv_path = Path(get_area_csv_path(area))
    if area_csv_path.exists():
        df_area = pd.read_csv(area_csv_path)
        if "冒険名" in df_area.columns:
            df_area = df_area[~df_area["冒険名"].isin(advs_to_delete)]
            df_area.to_csv(area_csv_path, index=False)
            yield f"🔥 削除: {advs_to_delete} from {area_csv_path}"
        else:
            yield f"❗ エラー: {area_csv_path} に '冒険名' 列が見つかりません"
    else:
        yield f"❌ 見つかりません: {area_csv_path}"

    yield from delete_logs(area, advs_to_delete)


def delete_logs(area: str, advs_to_delete: list):
    """
    指定された area に対して、
    ・get_check_log_csv_path の「冒険名」列に該当する行を削除
    ・get_adventure_path ファイルを削除
    """
    # get_check_log_csv_path の処理
    check_results_path = Path(get_check_log_csv_path(area))
    if check_results_path.exists():
        df_check = pd.read_csv(check_results_path)
        df_check = df_check[~df_check["冒険名"].isin(advs_to_delete)]
        df_check.to_csv(check_results_path, index=False)
        yield f"🔥 削除: {advs_to_delete} from {check_results_path}"
    else:
        yield f"❌ 見つかりません: {check_results_path}"
    
    # get_adventure_path の処理
    for adv in advs_to_delete:
        txt_path = Path(get_adventure_path(area, adv))
        if txt_path.exists():
            txt_path.unlink()
            yield f"🔥 削除: {txt_path}"
        else:
            yield f"❌ 見つかりません: {txt_path}"
    
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
    DuckDBを使ってSQLクエリでCSVファイルを読み込みDataFrameを返す。
    ファイルが存在しない場合は None を返す。
    """
    if not csv_path.exists():
        return None
    try:
        con = duckdb.connect(database=':memory:', read_only=False)
        sql_query = f"SELECT * FROM read_csv_auto('{str(csv_path)}', header = true)"
        df = con.execute(sql_query).fetchdf()
        con.close()
        return df
    except Exception as e:
        print(f"DuckDBでCSV読み込みエラー: {e}")
        return None

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