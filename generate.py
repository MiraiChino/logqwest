import argparse
import csv
from pathlib import Path


from llm import GeminiChat, GroqChat
from config import (
    AREAS_CSV_FILE,
    CHAPTER_SETTINGS,
)
from checkers import LogChecker
from generators import AreaGenerator, AdventureGenerator, LogGenerator
from common import get_area_csv_path, get_adventure_path, get_data_path, get_check_results_csv_path


def parse_arguments():
    parser = argparse.ArgumentParser(description="エリア、冒険、ログジェネレータ")
    parser.add_argument(
        "--client",
        choices=["gemini", "groq"],
        default="gemini",
        help="使用するチャットクライアント (gemini または groq, デフォルト: gemini)"
    )
    parser.add_argument(
        "--model",
        default=None,
        help="使用するモデル名 (指定しない場合はクライアントのデフォルトモデルを使用)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="デバッグモード (各処理で最初の1件のみ実行、またプロンプト/レスポンスを表示)"
    )
    subparsers = parser.add_subparsers(dest="type", required=True)

    # エリア生成サブコマンド
    area_parser = subparsers.add_parser("area", help="エリアを生成")
    area_parser.add_argument(
        "count",
        type=int,
        nargs='?',
        default=1,
        help="エリア生成の実行回数 (デフォルト: 1)"
    )

    # 冒険生成サブコマンド（オプションで result 指定可能）
    adventures_parser = subparsers.add_parser("adventures", help="冒険を生成")
    adventures_parser.add_argument(
        "result",
        nargs="?",
        default=None,
        help="生成する冒険の結果フィルター (例: 大成功)"
    )

    # ログ生成サブコマンド
    subparsers.add_parser("logs", help="ログを生成")
    return parser.parse_args()


def generate_area_content(area_generator, count):
    # DEBUG_MODE が True の場合、実行回数を 1 に制限
    global DEBUG_MODE
    if DEBUG_MODE:
        count = 1
    for _ in range(count):
        new_area_csv = area_generator.generate_new_area()
        new_area_name = new_area_csv[0]
        print(f"✅ エリア: {new_area_name}")


def process_adventures_content(adventure_generator, result_filter=None):
    global DEBUG_MODE
    areas = adventure_generator._load_areas()
    for area_name in areas:
        add_adventures_for_area(adventure_generator, area_name, result_filter=result_filter)
        area_csv_path = get_area_csv_path(area_name)
        adventure_generator.sort_csv(file_path=area_csv_path)
        if DEBUG_MODE:
            break  # DEBUG_MODE 時は最初の1エリアのみ実行


def add_adventures_for_area(adventure_generator, area_name, result_filter=None):
    global DEBUG_MODE
    adventure_types = [
        {"result": "失敗", "nums": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]},
        {"result": "成功", "nums": [1, 2, 3, 4, 5, 6, 7, 8, 9]},
        {"result": "大成功", "nums": [1]},
    ]
    # result フィルターが指定された場合、対象の結果のみ実行
    if result_filter:
        adventure_types = [at for at in adventure_types if at["result"] == result_filter]

    area_csv_path = get_area_csv_path(area_name)
    already_exist_adventures_in_area = load_existing_adventures_for_area(area_csv_path)
    debug_done = False
    for adventure_type in adventure_types:
        for idx, num in enumerate(adventure_type["nums"]):
            adventure_name = f"{adventure_type['result']}{num}_{area_name}"
            if adventure_name not in already_exist_adventures_in_area:
                adventure_generator.generate_new_adventure(adventure_name, adventure_type["result"], area_name)
                print(f"✅ 冒険: {adventure_name}")
                if DEBUG_MODE:
                    debug_done = True
                    break  # DEBUG_MODE 時は1件のみ実行
        if debug_done:
            break


def load_existing_adventures_for_area(area_csv_path):
    area_csv_path = Path(area_csv_path)
    if area_csv_path.exists():
        with area_csv_path.open("r", encoding="utf-8") as file:
            reader = csv.reader(file)
            next(reader, None)
            return [row[0] for row in reader if row]
    return []

def process_logs_content(log_generator, log_checker):
    global DEBUG_MODE
    areas_dir = get_data_path()
    area_dirs = [d for d in areas_dir.iterdir() if d.is_dir()]
    for area_dir in area_dirs:
        area_name = area_dir.name
        area_csv_path = get_area_csv_path(area_name)
        if area_csv_path.exists():
            generate_logs_for_area(log_generator, log_checker, area_name, area_csv_path)
        if DEBUG_MODE:
            break  # DEBUG_MODE 時は最初の1エリアのみ実行

def generate_logs_for_area(log_generator, log_checker, area_name, area_csv_path):
    global DEBUG_MODE
    area_csv_path = Path(area_csv_path)
    check_results_csv_path = get_check_results_csv_path(area=area_name)
    if not area_csv_path.exists():
        return

    max_retries = 5 # 最大リトライ回数
    retry_count = 0

    with area_csv_path.open("r", encoding="utf-8") as file:
        reader = csv.reader(file)
        next(reader, None)

        # 全ての冒険に対してログを生成
        for row in reader:
            current_adventure_txt_path = None
            try:
                if not row:
                    continue
                adventure_name, result, *chapters = row
                adventure_txt_path = get_adventure_path(area_name, adventure_name)

                if adventure_txt_path.exists():
                    # print(f"⏩ ログ: {adventure_txt_path} 既に存在するためスキップしました。")
                    continue # ログファイルが既に存在する場合はスキップ

                while retry_count <= max_retries: # リトライループ開始
                    temp_adventure_txt_path = adventure_txt_path.with_suffix(".temp.txt")
                    current_adventure_txt_path = temp_adventure_txt_path

                    # 前回のログファイルが残っている場合は削除
                    if temp_adventure_txt_path.exists():
                        temp_adventure_txt_path.unlink()
                        print(f"🔥 一時ログ: {temp_adventure_txt_path}")

                    pre_log = None
                    is_all_checked = False # ループ内で初期化

                    try: # ログ生成処理をtryブロックで囲む
                        for i in range(len(CHAPTER_SETTINGS)):
                            pre_log = log_generator.generate_log(
                                area_name=area_name,
                                adventure_name=adventure_name,
                                i_chapter=i,
                                adventure_txt_path=temp_adventure_txt_path,
                                pre_log=pre_log,
                            )
                            print(f"✅ ログ {i+1}/{len(CHAPTER_SETTINGS)}: {adventure_txt_path}")

                        # チェック
                        summary_text = ",".join(row)
                        log_text = temp_adventure_txt_path.read_text(encoding="utf-8")
                        check_result_json = log_checker.check_log(summary_text, log_text, adventure_name, check_results_csv_path)
                        is_all_checked = log_checker.is_all_checked(check_result_json)

                        if is_all_checked:
                            temp_adventure_txt_path.replace(adventure_txt_path) # 正常終了時のみ一時ファイルを本ファイルにリネーム

                            log_checker.save_check_result_csv(check_result_json, adventure_name, check_results_csv_path)
                            log_checker.sort_csv(check_results_csv_path)
                            print(f"✅ チェック: {adventure_txt_path}")
                            break # チェックOKならリトライループを抜ける
                        else:
                            print(check_result_json)
                            print(f"❌ チェック {retry_count}/{max_retries}: {adventure_txt_path}")
                            retry_count += 1 # チェックNGの場合はリトライ回数を増やす
                            continue # チェックNGの場合は再試行

                    except Exception as e: # ログ生成処理内で例外が発生した場合
                        print(f"ログ生成中にエラーが発生しました (リトライ回数: {retry_count}/{max_retries}): {e}")
                        retry_count += 1 # エラー発生時もリトライ回数を増やす
                        continue # エラー発生時は再試行

                if not is_all_checked: # リトライ回数上限を超えても is_all_checked が False の場合
                    print(f"🔥 リトライ回数上限に達しました。ログ生成に失敗しました: {temp_adventure_txt_path}")


            except Exception as e: # for row ループ内で例外が発生した場合 (ログ生成処理以外)
                print(f"ログ生成処理全体でエラーが発生しました: {e}")
            finally:
                if current_adventure_txt_path is not None and Path(current_adventure_txt_path).exists(): # current_adventure_txt_path が定義されているか確認
                    if not is_all_checked: # チェックNGまたはエラーの場合のみ削除 (リトライループ内で削除処理は実施済みだが、念のため)
                        Path(current_adventure_txt_path).unlink(missing_ok=True) # エラー発生時はログファイルを削除
                        print(f"🔥 ログファイルを削除しました: {current_adventure_txt_path}")
            if DEBUG_MODE:
                break

def main():
    global DEBUG_MODE
    args = parse_arguments()
    DEBUG_MODE = args.debug  # グローバルにデバッグフラグを設定
    import generators
    generators.DEBUG_MODE = DEBUG_MODE

    if args.client == "gemini":
        model_name = args.model if args.model else "models/gemini-2.0-flash-001"
        chat_client = GeminiChat(model_name)
    elif args.client == "groq":
        model_name = args.model if args.model else "gemma2-9b-it"
        chat_client = GroqChat(model_name)
    else:
        raise ValueError(f"不明なチャットクライアント: {args.client}")


    if args.type == "area":
        area_generator = AreaGenerator(chat_client, all_areas_csv_path=AREAS_CSV_FILE)
        generate_area_content(area_generator, args.count)
    elif args.type == "adventures":
        adventure_generator = AdventureGenerator(chat_client, all_areas_csv_path=AREAS_CSV_FILE)
        process_adventures_content(adventure_generator, result_filter=args.result)
    elif args.type == "logs":
        log_generator = LogGenerator(chat_client, all_areas_csv_path=AREAS_CSV_FILE)
        log_checker = LogChecker(chat_client)
        process_logs_content(log_generator, log_checker)


if __name__ == "__main__":
    main()