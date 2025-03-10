import argparse
import csv
from pathlib import Path

from llm import GeminiChat, GroqChat
from checkers import LogChecker, AdventureChecker
from config import AREAS_CSV_FILE
from common import get_area_csv_path, get_adventure_path, get_data_path, get_check_log_csv_path, get_check_adv_csv_path
from generate import load_existing_adventures_for_area

DEBUG_MODE = False


def parse_arguments():
    parser = argparse.ArgumentParser(description="冒険ログチェッカー")
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

    # ログチェックサブコマンド
    subparsers.add_parser("logs", help="ログファイルをチェック")

    # 冒険チェックサブコマンド
    subparsers.add_parser("adventures", help="冒険をチェック")
    return parser.parse_args()

def process_check_content(log_checker):
    global DEBUG_MODE
    areas_dir = get_data_path()
    area_dirs = [d for d in areas_dir.iterdir() if d.is_dir()]
    for area_dir in area_dirs:
        area_name = area_dir.name
        area_csv_path = get_area_csv_path(area_name)
        if area_csv_path.exists():
            check_logs_for_area(log_checker, area_name, area_csv_path)
            check_results_csv_path = get_check_log_csv_path(area=area_name)
            if check_results_csv_path.exists():
                log_checker.sort_csv(check_results_csv_path)
            if DEBUG_MODE:
                break  # DEBUG_MODE 時は最初の1エリアのみ実行

def process_check_adventures(adventure_checker):
    global DEBUG_MODE
    areas_dir = get_data_path()
    area_dirs = [d for d in areas_dir.iterdir() if d.is_dir()]
    for area_dir in area_dirs:
        area_name = area_dir.name
        area_csv_path = get_area_csv_path(area_name)
        if area_csv_path.exists():
            check_adventures_for_area(adventure_checker, area_name, area_csv_path)
            check_results_csv_path = get_check_adv_csv_path(area=area_name)
            if check_results_csv_path.exists():
                adventure_checker.sort_csv(check_results_csv_path)
            if DEBUG_MODE:
                break  # DEBUG_MODE 時は最初の1エリアのみ実行


def check_logs_for_area(log_checker, area_name, area_csv_path):
    global DEBUG_MODE
    area_csv_path = Path(area_csv_path)
    if not area_csv_path.exists():
        return
    check_results_csv_path = get_check_log_csv_path(area=area_name)
    already_exist_adventures_in_area = load_existing_adventures_for_area(check_results_csv_path)
    with area_csv_path.open("r", encoding="utf-8") as file:
        reader = csv.reader(file)
        _ = next(reader, None)

        # 全ての冒険ログをチェック
        for row in reader:
            if not row:
                continue
            adventure_name, result, *chapters = row
            if adventure_name in already_exist_adventures_in_area:
                continue
            adventure_txt_path = get_adventure_path(area_name, adventure_name)
            if adventure_txt_path.exists():
                summary_text = ",".join(row)
                log_text = adventure_txt_path.read_text(encoding="utf-8")
                check_result_json = log_checker.check_log(summary_text, log_text)
                if check_result_json and check_results_csv_path:
                    log_checker.save_check_result_csv(check_result_json, adventure_name, check_results_csv_path)
                    print(f"✅ ログチェック: {adventure_name}")
                if DEBUG_MODE:
                    break

def check_adventures_for_area(adventure_checker, area_name, area_csv_path):
    global DEBUG_MODE
    area_csv_path = Path(area_csv_path)
    if not area_csv_path.exists():
        return
    check_results_csv_path = get_check_adv_csv_path(area=area_name)
    already_exist_adventures_in_area = load_existing_adventures_for_area(check_results_csv_path)

    areas = {}
    if AREAS_CSV_FILE.exists():
        with AREAS_CSV_FILE.open("r", encoding="utf-8") as file:
            reader = csv.reader(file)
            _ = next(reader, None)
            for row in reader:
                areas[row[0]] = row

    with area_csv_path.open("r", encoding="utf-8") as file:
        reader = csv.reader(file)
        _ = next(reader, None)

        # 全ての冒険ログをチェック
        for row in reader:
            if not row:
                continue
            adventure_name, result, *chapters = row
            if adventure_name in already_exist_adventures_in_area:
                continue
            summary_text = ",".join(row) # AdventureCheckerに渡すのはrow全体
            area_data = ",".join(areas[area_name])
            check_result_json = adventure_checker.check_adventure(area_data, summary_text) # エリア名も渡す
            if check_result_json and check_results_csv_path:
                adventure_checker.save_check_result_csv(check_result_json, adventure_name, check_results_csv_path)
                print(f"✅ 冒険チェック: {adventure_name}")
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

    if args.type == "logs":
        log_checker = LogChecker(chat_client)
        process_check_content(log_checker)
    elif args.type == "adventures":
        adventure_checker = AdventureChecker(chat_client)
        process_check_adventures(adventure_checker)

if __name__ == "__main__":
    main()