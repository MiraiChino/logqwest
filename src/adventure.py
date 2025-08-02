import time
import traceback
import random
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

from src.utils.file_handler import FileHandler, FileStructure
from src.utils.config import ConfigManager

config_manager = ConfigManager(Path("prompt/config.json"))
file_structure = FileStructure(
    data_dir=config_manager.paths.data_dir,
    check_result_dir=config_manager.paths.check_result_dir,
    prompt_dir=config_manager.paths.prompt_dir
)
file_handler = FileHandler(file_structure)

ADVENTURE_COST = 100
DEBUG_MODE = True
DEFAULT_NAME = "アーサー"
INTERVAL_MINUTES = 5
LONG_INTERVAL_MINUTES = 60

def select_result(results: dict) -> str:
    """指定された確率情報に基づき、結果（キー）をランダムに選択する。"""
    result_names = list(results.keys())
    weights = [info["chance"] for info in results.values()]
    return random.choices(result_names, weights=weights, k=1)[0]

def select_adventurer_name(names_file: Path, adventure_history: list) -> str:
    """
    names.txtから冒険者の名前一覧を読み込み、ランダムに1つ返す。
    """
    # 過去成功していたら、その冒険者名を返す
    if adventure_history:
        prev_adv_name = adventure_history[0]["adventure"]
        result = file_handler.get_result(prev_adv_name)
        if result == "成功" or result == "大成功":
            return adventure_history[0]["adventurer"]
    # それ以外の場合は、ランダムに選ぶ
    with names_file.open("r", encoding="utf-8") as f:
        names = [line.strip() for line in f if line.strip()]
    prev_names = [h["adventurer"] for h in adventure_history if h and "adventurer" in h]
    names = [name for name in names if name not in prev_names]
    return random.choice(names) if names else DEFAULT_NAME

def get_adv_candidates(adventure_history: list, result: str) -> dict:
    prev_adv_and_precursor = {h["adventure"]: h["adventurer"] for h in adventure_history if h and "adventure" in h}
    adv_candidates = {}
    for area_name in file_handler.load_valid_areas():
        for adventure_name, r, prev_adventure_name in file_handler.load_area_adventures_with_result_and_prevadv(area_name):
            if r == result:
                # 履歴を考慮して、開放された冒険を含めて候補とする
                if prev_adventure_name == "なし" or prev_adventure_name in prev_adv_and_precursor.keys():
                    adv_candidates[adventure_name] = {
                        "count": 0,
                        "prev_adventure": prev_adventure_name,
                        "precursor": prev_adv_and_precursor.get(prev_adventure_name, None)
                    }
    return adv_candidates

def select_adventure(adventure_history: list, selected_result: str) -> str:
    """
    有効なエリアのリストを返す。lv1の有効エリア+履歴から次のエリアも含める。
    """
    adv_candidates = get_adv_candidates(adventure_history, selected_result)
    if len(adv_candidates) == 0:
        return None, None, None

    # 過去の履歴に入っているものをカウント
    for adv in adventure_history:
        adv_name = adv["adventure"]
        if adv_name in adv_candidates.keys():
            adv_candidates[adv_name]["count"] += 1

    # 使用回数が最も少ないものを選択
    min_count = min((v["count"] for v in adv_candidates.values()), default=0) # 一度も使われていない場合は 0
    min_adventures = [adv for adv, v in adv_candidates.items() if v["count"] == min_count]
    selected_adventure = random.choice(min_adventures)
    precursor = adv_candidates[selected_adventure]["precursor"]
    prev_adventure = adv_candidates[selected_adventure]["prev_adventure"]
    return selected_adventure, precursor, prev_adventure, min_count

def run_adventure_streaming():
    """
    冒険の一連の処理をジェネレーターとして実行し、各ステップの情報を辞書で yield する。
    yield されるイベントは以下の type を持ちます。
      - "header": 冒険開始時の基本情報
      - "message": 冒険シナリオの各行の出力メッセージ
      - "summary": 最終結果のサマリ
      - "error": エラー発生時のメッセージ
    """
    results = {
        "大成功": {"chance": 5, "prize": 1000},
        "成功": {"chance": 45, "prize": 110},
        "失敗": {"chance": 50, "prize": 0}
    }
    usage_data = file_handler.load_usage_data()
    adventure_history = usage_data.get("adventure_history", []) # 冒険履歴をロード
    selected_result = select_result(results)
    prize = results[selected_result]["prize"]

    selected_adventure, precursor, prev_adventure, count = select_adventure(adventure_history, selected_result)

    if not selected_adventure:
        yield {"type": "error", "error": "有効な冒険がありません"}
        return

    selected_area = file_handler.get_area_name(selected_adventure)
    if not selected_area:
        yield {"type": "error", "error": f"エリアが見つかりません: {selected_adventure}"}
        return

    adventure_file = file_handler.get_adventure_path(selected_area, selected_adventure)
    location_file = file_handler.get_location_path(selected_area, selected_adventure)
    if not adventure_file.exists():
        yield {"type": "error", "error": f"ファイルが見つかりません: {adventure_file}"}
        return
    if not location_file.exists():
        yield {"type": "error", "error": f"ファイルが見つかりません: {location_file}"}
        return

    names_file = file_structure.data_dir / "names.txt"
    adventurer_name = select_adventurer_name(names_file, adventure_history)

    # 雇用メッセージを追加
    yield {
        "type": "hiring",
        "adventurer": adventurer_name
    }

    # 冒険シナリオのシミュレーション
    total_time = timedelta()
    start_time = datetime.now().isoformat(timespec='seconds')
    current_time = datetime.now() if DEBUG_MODE else None
    try:
        adventure_log_content = file_handler.read_text(adventure_file)
        location_log_content = file_handler.read_text(location_file)
        if adventure_log_content is None or location_log_content is None:
            yield {"type": "error", "error": "冒険ファイルまたは位置情報ファイルの読み込みに失敗しました"}
            return

        adventure_lines = adventure_log_content.splitlines()
        location_lines = location_log_content.splitlines()

        last_location = None
        time_increment = timedelta(minutes=INTERVAL_MINUTES)
        long_time_increment = timedelta(minutes=LONG_INTERVAL_MINUTES)
        for i, (line_adv, line_loc) in enumerate(zip(adventure_lines, location_lines)):

            # 1. 前回のイベントからの経過時間を決定
            increment_this_step = timedelta(0) # 最初のイベントは経過時間なし
            is_location_change = False
            if i > 0: # 2番目以降のイベントの場合
                is_location_change = (line_loc != last_location)
                # 場所が変わったら長いインターバル、そうでなければ通常のインターバル
                increment_this_step = long_time_increment if is_location_change else time_increment

            # 2. 時間を経過させる (sleep と時間の更新)
            if increment_this_step > timedelta(0):
                sleep_seconds = increment_this_step.total_seconds()
                actual_sleep_duration = sleep_seconds / 3600
                actual_sleep_duration = sleep_seconds / 60
                # print(f"デバッグ: Step {i}, 場所変更: {is_location_change}, 増加時間: {increment_this_step}, sleep: {actual_sleep_duration:.2f}秒") # 必要ならコメント解除

                if actual_sleep_duration > 0:
                    time.sleep(actual_sleep_duration)

                # 時間カウンターを更新
                total_time += increment_this_step # シミュレーション時間を加算
                if DEBUG_MODE:
                    current_time += increment_this_step # デバッグ時はシミュレーション時刻を進める
                else:
                    # 通常モードではsleep後の実時間を反映
                    current_time = datetime.now()

            # 3. 現在のイベント情報をフォーマット
            time_str = current_time.strftime('%H:%M')
            location_text = line_loc.strip().format_map(defaultdict(str, name=adventurer_name, precursor=precursor))
            line_text = line_adv.strip().format_map(defaultdict(str, name=adventurer_name, precursor=precursor))

            # 4. イベントデータを yield する
            yield {
                "type": "message",
                "time": time_str,
                "text": line_text,
                "location": location_text
            }

            # 5. 次のループのために現在の場所を保存
            last_location = line_loc
    except Exception as e: # location_fileのopenに失敗した場合、エラーメッセージをyield
        print(traceback.format_exc())
        yield {"type": "error", "error": f"locationファイルの読み込みエラー: {e}、{adventure_file}の読み込みに失敗しました"}
        return

    # 履歴の追加
    adventure_entry = {
        "timestamp": start_time,
        "adventurer": adventurer_name,
        "area": selected_area,
        "adventure": selected_adventure,
        "result": selected_result,
        "prize": prize,
        "count": count,
        "prev_adventure": prev_adventure,
        "precursor": precursor
    }
    current_usage_data = file_handler.load_usage_data() # usage_dataをロード
    current_usage_data["adventure_history"].append(adventure_entry)
    file_handler.save_usage_data(current_usage_data) # usage_dataを保存

    hours, remainder = divmod(total_time.total_seconds(), 3600)
    minutes = remainder // 60
    summary_text = (
        f"- 結果: `{selected_result}`\n"
        f"- 獲得金額: `{prize}円`\n"
        f"- エリア: `{selected_area}`\n"
        f"- 冒険者: `{adventurer_name}`\n"
        f"- 経過時間: `{int(hours)}時間{int(minutes)}分`"
    )
    yield {"type": "summary", "text": summary_text}