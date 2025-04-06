import sys
import time
from dataclasses import dataclass
from typing import List, Dict, Optional, Any
from pathlib import Path

from src.checkers import AreaChecker, AdventureChecker, LogChecker, LocationChecker
from src.generators import AreaGenerator, AdventureGenerator, LogGenerator, LocationGenerator
from src.utils import FileHandler
from src.utils.csv_handler import CSVHandler
from src.utils.retry import retry_on_failure, RateLimitExeeded, RetryLimitExeeded
from src.utils.progress import ProgressTracker


@dataclass
class CommandContext:
    client: Any
    client_type: str
    model_name: Optional[str]
    debug_mode: bool

@dataclass
class Adventure:
    name: str
    result: str
    chapters: List[str]

class CommandHandler:
    def __init__(self, context: CommandContext, config_manager, logger):
        self.context = context
        self.config = config_manager
        self.logger = logger
        self.file_handler = FileHandler(self.config.paths)
        self.csv_handler = CSVHandler()
        self.progress_tracker = ProgressTracker(self.file_handler)

    def execute_area_command(self, difficulty: int = 1) -> None:
        area_generator = AreaGenerator(
            self.context.client,
            self.config.paths.prompt_dir / "new_area.txt",
            self.file_handler.get_lv_areas_csv_path(difficulty),
            self.config
        )
        area_checker = AreaChecker(
            self.context.client,
            self.config.paths.prompt_dir / "check_area.txt",
            self.config.area_check_keys,
            self.config.check_marks
        )
        for area_name in self.file_handler.load_nopast_area_names():
            if self.progress_tracker.is_area_complete(area_name) and self.progress_tracker.is_area_all_checked(area_name):
                pass
            else:
                self.logger.warning(f"未完了: {area_name}")
                if not self.context.debug_mode:
                    self.logger.warning("未完了エリアがあるため終了します")
                    return
        
        self._generate_and_check_area(area_generator, area_checker, difficulty)

    def execute_locked_area_command(self, difficulty: int = 1) -> None:
        area_checker = AreaChecker(
            self.context.client,
            self.config.paths.prompt_dir / "check_area.txt",
            self.config.area_check_keys,
            self.config.check_marks
        )
        
        for area_name in self.file_handler.load_all_area_names():
            if self.progress_tracker.is_area_complete(area_name) and self.progress_tracker.is_area_all_checked(area_name):
                pass
            else:
                self.logger.warning(f"未完了: {area_name}")
                if not self.context.debug_mode:
                    self.logger.warning("未完了エリアがあるため終了します")
                    return

        # まだ次のエリアが生成されていないエリアを抽出
        nonext_area_name, difficulty = self.file_handler.load_nonext_area_name_and_lv()

        area_generator = AreaGenerator(
            self.context.client,
            self.config.paths.prompt_dir / "new_locked_area.txt",
            self.file_handler.get_lv_areas_csv_path(difficulty + 1), # 次のレベルのエリアを生成する
            self.config,
            self.file_handler.get_lv_areas_csv_path(difficulty), #  前のレベルのエリアを参照する
        )
        self._generate_and_check_area(area_generator, area_checker, difficulty + 1, nonext_area_name)

    def execute_adventure_command(self, result_filter: Optional[str] = None) -> None:
        adventure_generator = AdventureGenerator(
            self.context.client,
            self.config.paths.prompt_dir / "new_adventure.txt",
            self.file_handler.get_lv_areas_csv_path(1),
            self.config
        )
        adventure_checker = AdventureChecker(
            self.context.client,
            self.config.paths.prompt_dir / "check_adventure.txt",
            self.config.adventure_check_keys,
            self.config.check_marks
        )

        for area_name in self.file_handler.load_nopast_area_names():
            try:
                debug_breaked = self._process_area_adventures(
                    adventure_generator,
                    adventure_checker,
                    area_name,
                    result_filter
                )
            except RateLimitExeeded:
                self.logger.warning(f"API制限: 15分待機します。モデル：{self.context.model_name}")
                time.sleep(60 * 15)
                sys.exit(1)
            if debug_breaked:
                break

    def execute_log_command(self) -> None:
        log_generator = LogGenerator(
            self.context.client,
            self.config.paths.prompt_dir / "new_log.txt",
            self.file_handler.get_lv_areas_csv_path(1),
            self.config
        )
        log_checker = LogChecker(
            self.context.client,
            self.config.paths.prompt_dir / "check_log.txt",
            self.config.log_check_keys,
            self.config.check_marks
        )
        
        for area_name in self.file_handler.load_nopast_area_names():
            try:
                debug_breaked = self._process_area_logs(log_generator, log_checker, area_name)
            except RateLimitExeeded:
                self.logger.warning(f"API制限: 15分待機します。モデル：{self.context.model_name}")
                time.sleep(60 * 15)
                sys.exit(1)
            if debug_breaked:
                break

    def execute_location_command(self) -> None:
        location_generator = LocationGenerator(
            self.context.client,
            self.config.paths.prompt_dir / "new_location.txt",
            self.file_handler.get_all_areas_csv_path()
        )
        location_checker = LocationChecker(
            self.context.client,
            self.config.paths.prompt_dir / "check_location.txt",
            self.config.location_check_keys,
            self.config.check_marks
        )
        
        for area_name in self.file_handler.load_all_area_names():
            try:
                debug_breaked = self._process_area_locations(location_generator, location_checker, area_name)
            except RateLimitExeeded:
                self.logger.warning(f"API制限: 15分待機します。モデル：{self.context.model_name}")
                time.sleep(60 * 15)
                sys.exit(1)
            if debug_breaked:
                break

    def _process_area_adventures(
        self,
        generator: AdventureGenerator,
        checker: AdventureChecker,
        area_name: str,
        result_filter: Optional[str]
    ) -> bool:
        try:
            area_data = self._load_area_data(area_name)
            existing_adventures = self._get_existing_adventures(area_name)
            for adventure_type in self._filter_adventure_types(result_filter):
                for num in adventure_type["nums"]:
                    adventure_name = f"{adventure_type['result']}{num}_{area_name}"
                    if adventure_name not in existing_adventures:
                        debug_breaked = self._generate_and_check_adventure(
                            generator, checker, area_name, area_data, adventure_name, 
                            adventure_type["result"]
                        )
                        if debug_breaked == "debug_breaked":
                            return True
        except RetryLimitExeeded as e:
            raise e

    def _process_area_logs(
        self,
        generator: LogGenerator,
        checker: LogChecker,
        area_name: str
    ) -> None:
        try:
            adventures = self._get_area_adventures(area_name)
            for adventure in adventures:
                if not self._is_log_generated(area_name, adventure.name):
                    debug_breaked = self._generate_and_check_log(
                        generator, checker, area_name, adventure
                    )
                    if debug_breaked == "debug_breaked":
                        return True
        except RetryLimitExeeded as e:
            self.logger.error("ログ: リトライ回数上限に達しました。")
            self.logger.delete(f"ログ: {adventure.name}の冒険を削除します。")
            for message in self.file_handler._delete_adventures(area_name, [adventure.name]):
                self.logger.simple(message)
            raise e

    def _process_area_locations(
        self,
        generator: LocationGenerator,
        checker: LocationChecker,
        area_name: str
    ) -> None:
        try:
            adventures = self._get_area_adventures(area_name)
            for adventure in adventures:
                if not self._is_location_generated(area_name, adventure.name) and self._is_log_generated(area_name, adventure.name):
                    debug_breaked = self._generate_and_check_location(
                        generator, checker, area_name, adventure
                    )
                    if debug_breaked == "debug_breaked":
                        return True
        except RetryLimitExeeded as e:
            self.logger.error("位置: リトライ回数上限に達しました。")
            self.logger.delete(f"位置: {adventure.name}の冒険ログを削除します。")
            for message in self.file_handler._delete_logs(area_name, [adventure.name]):
                self.logger.simple(message)
            raise e

    def _load_area_data(self, area_name: str) -> Dict:
        area_csvs = self.file_handler.get_all_areas_csv_path()
        for area_csv in area_csvs:
            for row in self.csv_handler.read_rows(area_csv):
                if row["エリア名"] == area_name: 
                    return row

    def _get_existing_adventures(self, area_name: str) -> List[str]:
        area_csv = self.file_handler.get_area_csv_path(area_name)
        return [row["冒険名"] for row in self.csv_handler.read_rows(area_csv) if row.get("冒険名", False)]

    def _filter_adventure_types(self, result_filter: Optional[str]) -> List[Dict]:
        adventure_types = [
            {"result": "失敗", "nums": range(1, 11)},
            {"result": "成功", "nums": range(1, 10)},
            {"result": "大成功", "nums": [1]}
        ]
        return [at for at in adventure_types if not result_filter or at["result"] == result_filter]

    def _get_area_adventures(self, area_name: str) -> List[Adventure]:
        area_csv = self.file_handler.get_area_csv_path(area_name)
        rows = self.csv_handler.read_rows(area_csv)
    
        adventures = []
        try:
            for row in rows:
                # Convert dict row to list and extract chapters
                row_values = list(row.values())
                adventures.append(Adventure(
                    name=row["冒険名"],
                    result=row["結果"],
                    chapters=row_values[2:]  # Everything after name and result
                ))
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            print(area_csv)
            print(row)
            raise e
        return adventures

    def _is_log_generated(self, area_name: str, adventure_name: str) -> bool:
        log_path = self.file_handler.get_adventure_path(area_name, adventure_name)
        return log_path.exists()

    def _is_location_generated(self, area_name: str, adventure_name: str) -> bool:
        location_path = self.file_handler.get_location_path(area_name, adventure_name)
        return location_path.exists()

    @retry_on_failure()
    def _generate_and_check_area(
        self,
        generator: AreaGenerator,
        checker: AreaChecker,
        difficulty: int,
        past_area_name: Optional[str] = None,
    ) -> None:
        try:
            if past_area_name:
                area_data = generator.generate_new_locked_area(past_area_name=past_area_name, difficulty=difficulty)
            else:
                area_data = generator.generate_new_area(difficulty=difficulty)
            if self.context.debug_mode:
                print(area_data)
            self.logger.generate(f"エリア: {area_data.name}")

            check_result = checker.check_area(
                area_data=area_data,
                existing_df=self.file_handler.load_areas_csv()
            )
            if self.context.debug_mode:
                print(check_result)
            self.logger.success(f"エリア: {area_data.name}")

            generator.save(area_data)
            checker.save(check_result, self.file_handler.get_lv_check_areas_csv_path(difficulty))
            return True
        except RateLimitExeeded:
            self.logger.warning(f"API制限: 15分待機します。モデル：{self.context.model_name}")
            time.sleep(60 * 15)
            sys.exit(1)
        except Exception as e:
            raise e

    @retry_on_failure()
    def _generate_and_check_adventure(
        self,
        generator: AdventureGenerator,
        checker: AdventureChecker,
        area_name: str,
        area_data: Dict,
        adventure_name: str,
        result: str,
    ) -> str:
        try:
            # 冒険 生成
            adventure = generator.generate_new_adventure(adventure_name, result, area_name)
            if self.context.debug_mode:
                print(adventure)
            self.logger.generate(f"冒険: {adventure_name}")

            # 冒険 チェック
            check_result = checker.check_adventure(
                area=','.join(area_data.values()),
                summary=','.join(adventure.chapters),
                adventure_name=adventure_name
            )
            if self.context.debug_mode:
                print(check_result)

            self.logger.success(f"冒険: {adventure_name}")
            generator.save(adventure, self.file_handler.get_area_csv_path(area_name))
            checker.save(check_result, self.file_handler.get_check_path(area_name, "adv"))

            if self.context.debug_mode:
                return "debug_breaked"
            return True
        except Exception as e:
            raise e

    @retry_on_failure()
    def _generate_and_check_log(
        self,
        generator: LogGenerator,
        checker: LogChecker,
        area_name: str,
        adventure: Adventure
    ) -> bool:
        adventure_txt_path = self.file_handler.get_adventure_path(area_name, adventure.name)
        temp_path = adventure_txt_path.with_suffix(".temp.txt")
        try:
            # ログ 生成
            log_content = self._generate_chapter_logs(generator, area_name, adventure, temp_path)
            if self.context.debug_mode:
                print(log_content)

            # ログ チェック
            summary = ','.join(adventure.chapters)
            check_result = checker.check_log(summary, log_content, adventure.name)
            if self.context.debug_mode:
                print(check_result)

            self.logger.success(f"ログ: {adventure.name}")
            temp_path.replace(adventure_txt_path)  # 正常終了時のみ一時ファイルを本ファイルにリネーム
            checker.save(check_result, self.file_handler.get_check_path(area_name, "log"))
            if self.context.debug_mode:
                return "debug_breaked"
            return True
        except Exception as e:
            raise e
        finally:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
                self.logger.delete(f"ログ削除: {temp_path}")

    @retry_on_failure()
    def _generate_and_check_location(
        self,
        generator: LocationGenerator,
        checker: LocationChecker,
        area_name: str,
        adventure: Adventure
    ) -> None:
        try:
            # 位置 生成
            log_content = self.file_handler.read_adventure_log(area_name, adventure.name)
            location_candidates = generator.get_location_candidates(area_name)
            location = generator.generate_location(area_name, log_content, location_candidates)
            if self.context.debug_mode:
                print(location)
            self.logger.generate(f"位置: {adventure.name}")

            # 位置 チェック
            log_with_location = "\n".join(f"[{loc}]: {text}" for text, loc in zip(log_content.splitlines(), location.splitlines()))
            check_result = checker.check_location(log_with_location, location_candidates, adventure.name)
            if self.context.debug_mode:
                print(check_result)

            location_path = self.file_handler.get_location_path(area_name, adventure.name)
            self.file_handler.write_text(location_path, location)
            checker.save(check_result, self.file_handler.get_check_path(area_name, "loc"))
            self.logger.success(f"位置: {adventure.name}")

            if self.context.debug_mode:
                return "debug_breaked"
            return True
        except Exception as e:
            raise e

    def _save_locations(self, area_name: str, adventure_name: str, locations: List[str], check_result: Dict, checker: LocationChecker) -> None:
        location_path = self.file_handler.get_location_path(area_name, adventure_name)
        check_csv_path = self.file_handler.get_check_path(area_name, "loc")
        
        self.file_handler.write_text(location_path, "\n".join(locations))
        checker.save_check_results(check_result, adventure_name, check_csv_path)

    @retry_on_failure()
    def _generate_chapter_logs(
        self,
        generator: LogGenerator,
        area_name: str,
        adventure: Adventure,
        temp_path: Path
    ) -> str:
        previous_log = None
        total = len(adventure.chapters)
        area_csv_path = self.file_handler.get_area_csv_path(area_name)
        for chapter_index, chapter in enumerate(adventure.chapters):
            # ログ 生成
            content = generator.generate_log(
                area_name=area_name,
                adventure_name=adventure.name,
                chapter_index=chapter_index,
                area_csv_path=area_csv_path,
                previous_log=previous_log,
            )
            
            if self.context.debug_mode:
                print(content)
            self.logger.generate(f"ログ {chapter_index+1}/{total}: {adventure.name}")

            self.file_handler.write_text(temp_path, content, append=True)
            previous_log = content
            
        return self.file_handler.read_text(temp_path)
