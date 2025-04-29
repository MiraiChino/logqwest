import re
from typing import Dict, Optional
from pathlib import Path
from collections import defaultdict

from src.core.generator import ContentGenerator
from src.core.client import ResponseFormat
from src.utils.csv_handler import CSVHandler

class LogGenerator(ContentGenerator):
    def __init__(self, client, template_path: Path, areas_csv_paths: Path, config_manager):
        super().__init__(client, template_path)
        self.csv_handler = CSVHandler()
        self.areas_csv_paths = areas_csv_paths
        self.config_manager = config_manager
        self.areas = self._load_area_data()
        self.line_pattern = re.compile(r'^\d+\.\s(.*)', re.DOTALL)

    def _load_area_data(self) -> Dict[str, Dict]:
        area_data = {}
        for areas_csv_path in self.areas_csv_paths:
            for row in self.csv_handler.read_rows(areas_csv_path):
                area_data[row["エリア名"]] = row 
        return area_data

    def _load_chapters(self, area_csv_path: str, adventure_name: str):
        for adv_name, prev_adv, next_adv, result, chapters in self.csv_handler.read_adventures(area_csv_path):
            if adv_name == adventure_name:
                return chapters
        raise ValueError(f"冒険 '{adventure_name}' が見つかりません。")

    def _format_area_info_text(self, chapter_text: str, area_info: Dict):
        area_info_text = self.config_manager.area_info_text
        are_info_added = False

        for header in self.config_manager.csv_headers_area:
            # キーワードリストを取得 (例: "生息する無害な生物_keywords")
            keywords_dict = area_info.get(f"{header}_keywords", {})
            if keywords_dict:
                # キーワードが章テキストに含まれているかチェック
                for keyword, keyword_text in keywords_dict.items():
                    if keyword.lower() in chapter_text.lower():
                        area_info_text += f"  - {keyword}: {keyword_text}\n"
                        are_info_added = True

        return area_info_text, are_info_added

    def _get_chapter_texts(self, area_csv_path: str, adventure_name: str, chapter_index: int) -> tuple[str, str]:
        chapters = self._load_chapters(area_csv_path, adventure_name)
        chapter_text = chapters[chapter_index]
        if chapter_index + 1 < len(self.config_manager.chapter_settings):
            next_chapter_text = chapters[chapter_index + 1]
        else:
            next_chapter_text = "（次章はなく、物語はこの章で終わる。）"
        return chapter_text, next_chapter_text

    def _build_kwargs(self, chapter_text: str, next_chapter_text: str, previous_log: str,
                         chapter_index: int, area_info, precursor_log) -> dict:
        if chapter_index != 0 and previous_log:
            before_log = self.config_manager.before_log_template["with_pre_log"].format(pre_log=previous_log)
        else:
            before_log = self.config_manager.before_log_template["default"]
        area_info_text, are_info_added = self._format_area_info_text(chapter_text, area_info)
        thischapter_setting = self.config_manager.chapter_settings[chapter_index]
        kwargs = {
            "before_chapter": thischapter_setting.get("before_chapter", ""),
            "chapter": chapter_text,
            "after_chapter": thischapter_setting.get("after_chapter", ""),
            "next_chapter": next_chapter_text,
            "before_log": before_log,
            "area_info": area_info_text.strip() if are_info_added else "",
            "precursor_log": precursor_log
        }
        return kwargs

    def generate_log(self, area_name: str, adventure_name: str, chapter_index: int,
                    area_csv_path:str, previous_log: Optional[str] = None, precursor_log: str = None, debug: bool = False) -> str:
        area_info = self.areas.get(area_name)
        if not area_info:
            raise ValueError(f"エリア '{area_name}' が見つかりません。")

        # チャプターの取得
        chapter_text, next_chapter_text = self._get_chapter_texts(area_csv_path, adventure_name, chapter_index)
    
        # ログ生成用のkwargsを構築
        kwargs = self._build_kwargs(chapter_text, next_chapter_text, previous_log, chapter_index, area_info, precursor_log)

        response = self.generate(response_format=ResponseFormat.TEXT, debug=debug, **kwargs)
        content = self.extract_content(response)
        self.validate_content(content)
        return self.create_data(content)

    def extract_content(self, response: str) -> str:
        filtered_lines = []
        for line in response.strip().splitlines():
            stripped_line = line.strip()
            if stripped_line.startswith('##'):
                continue
            match = self.line_pattern.match(stripped_line)
            if match:
                content_line = match.group(1)
                filtered_lines.append(content_line.strip())
        return '\n'.join(filtered_lines) + '\n'

    def validate_placeholders(self, line):
        # プレースホルダーの一覧を抽出（例: {name}, {precursor}, {something_else}）
        placeholders = re.findall(r'{(.*?)}', line)

        # 許可されているプレースホルダー
        allowed = {"name", "precursor"}
        line.format_map(defaultdict(str, name="テスト", precursor="テスト"))

        # 許可されていないものが含まれていればエラーを出す
        for ph in placeholders:
            if ph not in allowed:
                raise ValueError(f"無効なプレースホルダー '{{{ph}}}' が含まれています: {line}")

    def validate_content(self, content: str):
        if not content:
            raise ValueError("抽出されたコンテンツが空です。")

        lines = content.splitlines()
        for line in lines:
            if set(self.config_manager.ng_words).intersection(line.strip()):
                raise ValueError(f"NGワードが含まれています: {line}")
            self.validate_placeholders(line)
        if len(lines) < 20:
            raise ValueError("抽出されたコンテンツの行数が20行未満です。")

    def create_data(self, content: str) -> str:
        return content
