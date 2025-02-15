import csv
import json
import random
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

# 定数・設定
DATA_DIR = Path("data")
USER_DATA_FILE = Path("user_data") / "history.json"
ADVENTURE_COST = 100
DEBUG_MODE = True
# DEBUG時にエリアを強制指定する場合は値を設定（例："静寂の草原"）、通常はNone
DEBUG_OVERRIDE_AREA = None
DEFAULT_NAME = "アーサー"


def load_valid_areas(data_dir: Path = DATA_DIR) -> list[str]:
    """有効なエリア一覧をCSVから読み込み、対応するCSVファイルが存在するエリアのみ返す。"""
    areas_file = data_dir / "areas.csv"
    valid_areas = []
    with areas_file.open("r", encoding="utf-8") as f:
        for row in csv.reader(f):
            if row:
                area = row[0].strip()
                if (data_dir / f"{area}.csv").exists():
                    valid_areas.append(area)
    return valid_areas


def select_outcome(outcomes: dict) -> str:
    """指定された確率情報に基づき、結果（キー）をランダムに選択する。"""
    outcome_names = list(outcomes.keys())
    weights = [info["chance"] for info in outcomes.values()]
    return random.choices(outcome_names, weights=weights, k=1)[0]


def load_scenario_mappings(area: str, data_dir: Path = DATA_DIR) -> dict:
    """
    指定エリアのCSVからシナリオのマッピングを読み込み、
    結果毎にファイル名のリストを返す。
    """
    csv_path = data_dir / f"{area}.csv"
    mappings = {"大成功": [], "成功": [], "失敗": []}
    with csv_path.open("r", encoding="utf-8") as f:
        for row in csv.reader(f):
            if len(row) >= 2:
                filename = row[0].strip()
                result = row[1].strip()
                if result in mappings:
                    mappings[result].append(filename)
    return mappings

def load_usage_data(user_data_file: Path = USER_DATA_FILE) -> dict:
    """
    使用履歴と収支情報をJSONファイルから読み込む。
    """
    try:
        with user_data_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if "adventure_history" not in data: # 初回起動時などでキーが存在しない場合
                return {"adventure_history": []} # 空のリストで初期化
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {"adventure_history": []}

def save_usage_data(data: dict, user_data_file: Path = USER_DATA_FILE):
    """使用履歴と収支情報をJSONファイルへ保存する。"""
    user_data_file.parent.mkdir(parents=True, exist_ok=True)
    with user_data_file.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def select_unused_adventure(filenames: list[str], adventure_history: list) -> str:
    """
    使用回数が最も少ない冒険ファイルからランダムに選択する。
    adventure_history をもとにファイルごとの使用回数を集計し、
    """
    filename_counts = {}
    for entry in adventure_history:
        filename = entry["filename"]
        filename_counts[filename] = filename_counts.get(filename, 0) + 1

    def get_count(fn: str) -> int:
        return filename_counts.get(fn, 0)

    min_count = min((get_count(fn) for fn in filenames), default=0) # ファイルが一度も使われていない場合は 0
    candidates = [fn for fn in filenames if get_count(fn) == min_count]
    return random.choice(candidates)


def select_adventurer_name(names_file: Path) -> str:
    """
    names.txtから冒険者の名前一覧を読み込み、ランダムに1つ返す。
    """
    with names_file.open("r", encoding="utf-8") as f:
        names = [line.strip() for line in f if line.strip()]
    return random.choice(names) if names else DEFAULT_NAME


def run_adventure_streaming():
    """
    冒険の一連の処理をジェネレーターとして実行し、各ステップの情報を辞書で yield する。
    yield されるイベントは以下の type を持ちます。
      - "header": 冒険開始時の基本情報
      - "message": 冒険シナリオの各行の出力メッセージ
      - "summary": 最終結果のサマリ
      - "error": エラー発生時のメッセージ
    """
    outcomes = {
        "大成功": {"chance": 5, "prize": 1000},
        "成功": {"chance": 45, "prize": 110},
        "失敗": {"chance": 50, "prize": 0}
    }
    usage_data = load_usage_data()
    adventure_history = usage_data.get("adventure_history", []) # 冒険履歴をロード
    valid_areas = load_valid_areas()
    if not valid_areas:
        yield {"type": "error", "error": "有効なエリアがありません"}
        return

    selected_outcome = select_outcome(outcomes)
    prize = outcomes[selected_outcome]["prize"]

    selected_area = random.choice(valid_areas)
    if DEBUG_OVERRIDE_AREA:
        selected_area = DEBUG_OVERRIDE_AREA

    scenario_mappings = load_scenario_mappings(selected_area)
    target_files = scenario_mappings.get(selected_outcome, [])
    if not target_files:
        yield {"type": "error", "error": f"{selected_area}に{selected_outcome}用のシナリオがありません"}
        return

    selected_adventure = select_unused_adventure(target_files, adventure_history) # 冒険履歴を渡す
    adventure_file = DATA_DIR / selected_area / f"{selected_adventure}.txt"
    if not adventure_file.exists():
        yield {"type": "error", "error": f"ファイルが見つかりません: {adventure_file}"}
        return

    names_file = DATA_DIR / "names.txt"
    adventurer_name = select_adventurer_name(names_file)

    # 雇用メッセージを追加
    yield {
        "type": "hiring",
        "adventurer": adventurer_name
    }

    # 冒険シナリオのシミュレーション
    total_time = timedelta()
    current_time = datetime.now() if DEBUG_MODE else None
    with adventure_file.open("r", encoding="utf-8") as f:
        for line in f:
            time_increment = timedelta(minutes=2.5)
            if DEBUG_MODE:
                current_time += time_increment
                total_time += time_increment
            else:
                current_time = datetime.now()

            time_str = current_time.strftime('%H:%M') if current_time else datetime.now().strftime('%H:%M')
            line_text = line.strip().format_map(defaultdict(str, name=adventurer_name))
            # 各イベントで時刻とテキストを別々に yield する
            yield {"type": "message", "time": time_str, "text": line_text}

            if DEBUG_MODE:
                time.sleep(time_increment.total_seconds() / 60)
            else:
                time.sleep(time_increment.total_seconds())

    # 履歴の追加
    adventure_entry = {
        "timestamp": datetime.now().isoformat(timespec='seconds'),
        "area": selected_area,
        "outcome": selected_outcome,
        "prize": prize,
        "adventurer": adventurer_name,
        "filename": selected_adventure
    }
    usage_data["adventure_history"].append(adventure_entry)

    save_usage_data(usage_data)

    hours, remainder = divmod(total_time.total_seconds(), 3600)
    minutes = remainder // 60
    summary_text = (
        f"- 支出: `-{ADVENTURE_COST}円`\n"
        f"- 結果: `{selected_outcome}`\n"
        f"- 獲得金額: `{prize}円`\n"
        f"- エリア: `{selected_area}`\n"
        f"- 冒険: `{selected_adventure}`\n"
        f"- 冒険者: `{adventurer_name}`\n"
        f"- 経過時間: `{int(hours)}時間{int(minutes)}分`"
    )
    yield {"type": "summary", "text": summary_text}