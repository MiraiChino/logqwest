import argparse
import csv
from pathlib import Path
from typing import List, Dict, Any

from llm import GeminiChat, GroqChat
from config import AREAS_CSV_FILE, CHAPTER_SETTINGS
from checkers import LogChecker, AdventureChecker
from generators import AreaGenerator, AdventureGenerator, LogGenerator
from common import get_area_csv_path, get_adventure_path, get_data_path, get_check_log_csv_path, get_check_adv_csv_path


# 定数
MAX_RETRIES = 5
ADVENTURE_TYPES = [
    {"result": "失敗", "nums": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]},
    {"result": "成功", "nums": [1, 2, 3, 4, 5, 6, 7, 8, 9]},
    {"result": "大成功", "nums": [1]},
]


def parse_arguments() -> argparse.Namespace:
    """コマンドライン引数を解析する。"""
    parser = argparse.ArgumentParser(description="エリア、冒険、ログジェネレータ")
    parser.add_argument(
        "--client",
        choices=["gemini", "groq"],
        default="gemini",
        help="使用するチャットクライアント (gemini または groq, デフォルト: gemini)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="使用するモデル名 (指定しない場合はクライアントのデフォルトモデルを使用)",
    )
    parser.add_argument(
        "--debug", action="store_true", help="デバッグモード (各処理で最初の1件のみ実行、またプロンプト/レスポンスを表示)"
    )
    subparsers = parser.add_subparsers(dest="type", required=True)

    # エリア生成サブコマンド
    area_parser = subparsers.add_parser("area", help="エリアを生成")
    area_parser.add_argument(
        "count", type=int, nargs="?", default=1, help="エリア生成の実行回数 (デフォルト: 1)"
    )

    # 冒険生成サブコマンド
    adventures_parser = subparsers.add_parser("adventures", help="冒険を生成")
    adventures_parser.add_argument(
        "result", nargs="?", default=None, help="生成する冒険の結果フィルター (例: 大成功)"
    )

    # ログ生成サブコマンド
    subparsers.add_parser("logs", help="ログを生成")
    return parser.parse_args()


def initialize_chat_client(client_name: str, model_name: str = None) -> Any:
    """チャットクライアントを初期化する。"""
    if client_name == "gemini":
        default_model = "models/gemini-2.0-flash-001"
        model = model_name if model_name else default_model
        return GeminiChat(model)
    elif client_name == "groq":
        default_model = "gemma2-9b-it"
        model = model_name if model_name else default_model
        return GroqChat(model)
    else:
        raise ValueError(f"不明なチャットクライアント: {client_name}")


def generate_area_content(area_generator: AreaGenerator, count: int, debug_mode: bool = False) -> None:
    """エリアコンテンツを生成する。"""
    limit_count = 1 if debug_mode else count
    for _ in range(limit_count):
        new_area_csv = area_generator.generate_new_area()
        new_area_name = new_area_csv[0]
        print(f"✅ エリア: {new_area_name}")


def process_adventures_content(
    adventure_generator: AdventureGenerator, adv_checker: AdventureChecker, result_filter: str = None, debug_mode: bool = False
) -> None:
    """冒険コンテンツを処理する。"""
    areas = adventure_generator._load_areas()
    for area_name in areas:
        debug_breaked = process_area_adventures(adventure_generator, adv_checker, area_name, result_filter, debug_mode) # debug_breaked を取得
        if debug_breaked: # debug_breaked が True なら break
            break  # デバッグモード時は最初の1エリアのみ実行


def process_area_adventures(
    adventure_generator: AdventureGenerator, adv_checker: AdventureChecker, area_name: str, result_filter: str = None, debug_mode: bool = False
) -> bool: # 戻り値の型を bool に変更
    """特定のエリアの冒険を処理する。デバッグモードの場合は最初の冒険生成後に True を返す。"""
    adventure_types = ADVENTURE_TYPES
    if result_filter:
        adventure_types = [at for at in adventure_types if at["result"] == result_filter]

    areas = load_areas_from_csv()
    if area_name not in areas:
        print(f"エラー：エリア '{area_name}' が areas.csv に存在しません。")
        return False # エラー時は False を返す

    area_data = ",".join(areas[area_name])
    area_csv_path = get_area_csv_path(area_name)
    existing_adventures = load_existing_adventures_for_area(area_csv_path)
    check_adv_csv_path = get_check_adv_csv_path(area=area_name)

    for adventure_type in adventure_types:
        for num in adventure_type["nums"]:
            adventure_name = f"{adventure_type['result']}{num}_{area_name}"
            if adventure_name not in existing_adventures:
                debug_breaked = generate_adventure_with_retry(
                    adventure_generator, adv_checker, area_name, area_data, area_csv_path, check_adv_csv_path, adventure_name, adventure_type["result"], debug_mode
                )
                if debug_breaked:
                    return True  # デバッグモード時は True を返す

    return False # デバッグモードでない場合は False を返す


def load_areas_from_csv() -> Dict[str, List[str]]:
    """areas.csv ファイルからエリアデータをロードする。"""
    areas = {}
    if AREAS_CSV_FILE.exists():
        with AREAS_CSV_FILE.open("r", encoding="utf-8") as file:
            reader = csv.reader(file)
            next(reader, None)  # ヘッダー行をスキップ
            for row in reader:
                areas[row[0]] = row
    return areas


def generate_adventure_with_retry(
    adventure_generator: AdventureGenerator,
    adv_checker: AdventureChecker,
    area_name: str,
    area_data: str,
    area_csv_path: str,
    check_adv_csv_path: str,
    adventure_name: str,
    adventure_result: str,
    debug_mode: bool,
) -> None:
    """冒険生成をリトライ付きで実行する。"""
    retry_count = 0
    is_all_checked = False
    while retry_count <= MAX_RETRIES:
        try:
            csv_contents = adventure_generator.generate_new_adventure(adventure_name, adventure_result, area_name)
            check_result_json = adv_checker.check_adventure(area_data, ",".join(csv_contents))
            print(f"✅ 冒険: {adventure_name}")
            is_all_checked = adv_checker.is_all_checked(check_result_json)

            if is_all_checked:
                adventure_generator._add_to_csv(area_csv_path, csv_contents)
                adventure_generator.sort_csv(file_path=area_csv_path)
                adv_checker.save_check_result_csv(check_result_json, adventure_name, check_adv_csv_path)
                adv_checker.sort_csv(check_adv_csv_path)
                print(f"✅ チェック: {adventure_name}")
                break  # チェックOKならリトライループを抜ける
            else:
                print(check_result_json)
                print(f"❌ チェック {retry_count}/{MAX_RETRIES}: {adventure_name}")
                retry_count += 1  # チェックNGの場合はリトライ回数を増やす
        except Exception as e:  # ログ生成処理内で例外が発生した場合
            print(f"冒険生成中にエラーが発生しました (リトライ回数: {retry_count}/{MAX_RETRIES}): {e}")
            retry_count += 1  # エラー発生時もリトライ回数を増やす

    if not is_all_checked:  # リトライ回数上限を超えても is_all_checked が False の場合
        print(f"🔥 リトライ回数上限に達しました。冒険生成に失敗しました: {adventure_name}")
    if debug_mode:
        return True

def load_existing_adventures_for_area(area_csv_path: str) -> List[str]:
    """エリアの CSV ファイルから既存の冒険名をロードする。"""
    path = Path(area_csv_path)
    if path.exists():
        with path.open("r", encoding="utf-8") as file:
            reader = csv.reader(file)
            next(reader, None)  # ヘッダー行をスキップ
            return [row[0] for row in reader if row]
    return []


def process_logs_content(log_generator: LogGenerator, log_checker: LogChecker, debug_mode: bool = False) -> None:
    """ログコンテンツを処理する。"""
    areas_dir = get_data_path()
    area_dirs = [d for d in areas_dir.iterdir() if d.is_dir()]
    for area_dir in area_dirs:
        area_name = area_dir.name
        area_csv_path = get_area_csv_path(area_name)
        if area_csv_path.exists():
            generate_logs_for_area(log_generator, log_checker, area_name, area_csv_path, debug_mode)
        if debug_mode:
            break  # デバッグモード時は最初の1エリアのみ実行


def generate_logs_for_area(
    log_generator: LogGenerator, log_checker: LogChecker, area_name: str, area_csv_path: str, debug_mode: bool = False
) -> None:
    """特定のエリアのログを生成する。"""
    path = Path(area_csv_path)
    check_results_csv_path = get_check_log_csv_path(area=area_name)
    if not path.exists():
        return

    with path.open("r", encoding="utf-8") as file:
        reader = csv.reader(file)
        next(reader, None)  # ヘッダー行をスキップ

        for row in reader:
            if not row:
                continue
            adventure_name, result, *chapters = row
            adventure_txt_path = get_adventure_path(area_name, adventure_name)

            if adventure_txt_path.exists():
                # print(f"⏩ ログ: {adventure_txt_path} 既に存在するためスキップしました。")
                continue  # ログファイルが既に存在する場合はスキップ

            generate_log_with_retry(log_generator, log_checker, area_name, area_csv_path, check_results_csv_path, adventure_name, row, adventure_txt_path, debug_mode)
            if debug_mode:
                break


def generate_log_with_retry(log_generator: LogGenerator, log_checker: LogChecker, area_name: str, area_csv_path: str, check_results_csv_path: str, adventure_name: str, row: List[str], adventure_txt_path: Path, debug_mode: bool) -> None:
    """ログ生成をリトライ付きで実行する。"""
    retry_count = 0
    is_all_checked = False
    current_adventure_txt_path = None

    while retry_count <= MAX_RETRIES:
        try:
            temp_adventure_txt_path = adventure_txt_path.with_suffix(".temp.txt")
            current_adventure_txt_path = temp_adventure_txt_path

            # 前回のログファイルが残っている場合は削除
            if temp_adventure_txt_path.exists():
                temp_adventure_txt_path.unlink()
                print(f"🔥 一時ログ: {temp_adventure_txt_path}")

            pre_log = None

            try:  # ログ生成処理をtryブロックで囲む
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
                check_result_json = log_checker.check_log(summary_text, log_text)
                is_all_checked = log_checker.is_all_checked(check_result_json)

                if is_all_checked:
                    temp_adventure_txt_path.replace(adventure_txt_path)  # 正常終了時のみ一時ファイルを本ファイルにリネーム
                    log_checker.save_check_result_csv(check_result_json, adventure_name, check_results_csv_path)
                    log_checker.sort_csv(check_results_csv_path)
                    print(f"✅ チェック: {adventure_txt_path}")
                    break  # チェックOKならリトライループを抜ける
                else:
                    print(check_result_json)
                    print(f"❌ チェック {retry_count}/{MAX_RETRIES}: {adventure_txt_path}")
                    retry_count += 1  # チェックNGの場合はリトライ回数を増やす
            except Exception as e:  # ログ生成処理内で例外が発生した場合
                print(f"ログ生成中にエラーが発生しました (リトライ回数: {retry_count}/{MAX_RETRIES}): {e}")
                retry_count += 1  # エラー発生時もリトライ回数を増やす

        except Exception as e:  # for row ループ内で例外が発生した場合 (ログ生成処理以外)
            print(f"ログ生成処理全体でエラーが発生しました: {e}")
        finally:
            if current_adventure_txt_path is not None and Path(current_adventure_txt_path).exists():  # current_adventure_txt_path が定義されているか確認
                if not is_all_checked:  # チェックNGまたはエラーの場合のみ削除 (リトライループ内で削除処理は実施済みだが、念のため)
                    Path(current_adventure_txt_path).unlink(missing_ok=True)  # エラー発生時はログファイルを削除
                    print(f"🔥 ログファイルを削除しました: {current_adventure_txt_path}")
        if is_all_checked or debug_mode: # チェックOKまたはデバッグモードの場合はループを抜ける
            break

    if not is_all_checked:  # リトライ回数上限を超えても is_all_checked が False の場合
        print(f"🔥 リトライ回数上限に達しました。ログ生成に失敗しました: {temp_adventure_txt_path}")


def main() -> None:
    """メイン関数"""
    args = parse_arguments()
    debug_mode = args.debug

    # デバッグモードをジェネレータモジュールに設定 (必要に応じて)
    import generators
    generators.DEBUG_MODE = debug_mode  #  <- この行は削除を検討してください。

    chat_client = initialize_chat_client(args.client, args.model)

    if args.type == "area":
        area_generator = AreaGenerator(chat_client, all_areas_csv_path=AREAS_CSV_FILE)
        generate_area_content(area_generator, args.count, debug_mode)
    elif args.type == "adventures":
        adventure_generator = AdventureGenerator(chat_client, all_areas_csv_path=AREAS_CSV_FILE)
        adv_checker = AdventureChecker(chat_client)
        process_adventures_content(adventure_generator, adv_checker, args.result, debug_mode)
    elif args.type == "logs":
        log_generator = LogGenerator(chat_client, all_areas_csv_path=AREAS_CSV_FILE)
        log_checker = LogChecker(chat_client)
        process_logs_content(log_generator, log_checker, debug_mode)


if __name__ == "__main__":
    main()