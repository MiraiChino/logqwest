import duckdb
import pandas as pd
from pathlib import Path
import json

from config import CHECK_RESULT_DIR, DATA_DIR, LOGCHECK_HEADERS, ADVCHECK_HEADERS, LOCATIONCHECK_HEADERS

ADVENTURE_DETAIL_LINE_THRESHOLD = 160  # 冒険詳細ファイルの完了行数閾値
CHECK_MARK = "✅"
SUCCESS_EMOJI = "❗"

def get_check_log_csv_path(area: str) -> Path:
    """指定されたエリア名のログチェックCSVファイルパスを返す。"""
    return CHECK_RESULT_DIR / area / f"log_{area}.csv"

def get_check_adv_csv_path(area: str) -> Path:
    """指定されたエリア名の冒険チェックCSVファイルパスを返す。"""
    return CHECK_RESULT_DIR / area / f"adv_{area}.csv"

def get_check_loc_csv_path(area: str) -> Path:
    """指定されたエリア名の位置情報チェックCSVファイルパスを返す。"""
    return CHECK_RESULT_DIR / area / f"loc_{area}.csv"

def get_data_path() -> Path:
    return DATA_DIR

def get_area_csv_path(area: str) -> Path:
    """指定されたエリア名のCSVファイルパスを返す。"""
    return DATA_DIR / area / f"{area}.csv"

def get_adventure_path(area: str, adv: str) -> Path:
    """指定されたエリア内の冒険テキストファイルのパスを返す。"""
    return DATA_DIR / area / f"{adv}.txt"

def get_location_path(area: str, adv: str) -> Path:
    """指定されたエリア内の冒険テキストの位置ファイルのパスを返す。"""
    return DATA_DIR / area / f"loc_{adv}.txt"

def is_adventure_complete(area: str, adventure_name: str) -> bool:
    """冒険詳細ファイルが存在し、内容が指定行数以上の場合にTrueを返す。"""
    adventure_path = get_adventure_path(area, adventure_name)
    if not adventure_path.exists():
        return False
    try:
        with open(adventure_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return len(lines) >= ADVENTURE_DETAIL_LINE_THRESHOLD
    except Exception:
        return False

def is_area_complete(area: str) -> bool:
    """
    エリア内の全ての冒険が完了し、かつチェック結果CSVの行数も一致するか判定する。
    完了とは、冒険詳細ファイルが存在し、内容が指定行数以上であること。
    """
    area_csv_path = get_area_csv_path(area)
    df_area = load_csv(area_csv_path)
    check_log_csv_path = get_check_log_csv_path(area)
    df_check_logs = load_csv(check_log_csv_path)
    check_adv_csv_path = get_check_adv_csv_path(area)
    df_check_advs = load_csv(check_adv_csv_path)
    check_loc_csv_path = get_check_loc_csv_path(area)
    df_check_locs = load_csv(check_loc_csv_path)

    if (df_area is None or "冒険名" not in df_area.columns or df_area.empty):
        return False

    total_adventures = len(df_area)
    completed_adventures_count = sum(1 for adv in df_area["冒険名"] if is_adventure_complete(area, adv))
    checked_logs_count = len(df_check_logs) if df_check_logs is not None else 0 # チェック結果CSVがない場合は0
    checked_advs_count = len(df_check_advs) if df_check_advs is not None else 0 # チェック結果CSVがない場合は0
    checked_locs_count = len(df_check_locs) if df_check_locs is not None else 0 # チェック結果CSVがない場合は0

    return total_adventures == completed_adventures_count == checked_logs_count == checked_advs_count == checked_locs_count

def is_area_all_checked(area: str) -> bool:
    """
    エリアの check_logs_csv, check_advs_csv のチェック内容が全て✅で始まっているか確認する。
    冒険の完了状態やチェック結果CSVの行数は見ない。
    """
    check_log_csv_path = get_check_log_csv_path(area)
    df_check_logs = load_csv(check_log_csv_path)

    if df_check_logs is None or df_check_logs.empty:
        return False
    
    check_columns = LOGCHECK_HEADERS[1:-1] # '冒険名', '総合評価' 以外の列をチェック
    for _, row in df_check_logs.iterrows():
        for col in check_columns:
            if not isinstance(row[col], str) or not row[col].startswith(CHECK_MARK):
                return False

    check_adv_csv_path = get_check_adv_csv_path(area)
    df_check_advs = load_csv(check_adv_csv_path)

    if df_check_advs is None or df_check_advs.empty:
        return False
    
    check_columns = ADVCHECK_HEADERS[1:-1] # '冒険名', '総合評価' 以外の列をチェック
    for _, row in df_check_advs.iterrows():
        for col in check_columns:
            if not isinstance(row[col], str) or not row[col].startswith(CHECK_MARK):
                return False

    check_loc_csv_path = get_check_loc_csv_path(area)
    df_check_locs = load_csv(check_loc_csv_path)

    if df_check_locs is None or df_check_locs.empty:
        return False

    check_columns = LOCATIONCHECK_HEADERS[1:-1] # '冒険名', '総合評価' 以外の列をチェック
    for _, row in df_check_locs.iterrows():
        for col in check_columns:
            if col not in row or not isinstance(row[col], str) or not row[col].startswith(CHECK_MARK): # 列が存在しない場合も考慮
                return False
    return True # 全ての項目が✅で始まっていればTrueを返す

def delete_locations(area: str, advs_to_delete: list):
    """
    指定された area に対して、
    ・get_check_loc_csv_path の「冒険名」列に該当する行を削除
    ・get_location_path の「冒険名」列に該当する行を削除
    """
    # get_check_adv_csv_path の処理
    check_results_path = Path(get_check_loc_csv_path(area))
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

    # get_location_path の処理
    for adv in advs_to_delete:
        txt_path = Path(get_location_path(area, adv))
        if txt_path.exists():
            txt_path.unlink()
            yield f"🔥 削除: {txt_path}"
        else:
            yield f"❌ 見つかりません: {txt_path}"

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
    ・
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

    yield from delete_locations(area, advs_to_delete)
    
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