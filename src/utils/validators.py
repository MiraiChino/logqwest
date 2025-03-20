from typing import Dict, List, Set
from dataclasses import dataclass

@dataclass
class ValidationRules:
    forbidden_words: Set[str]
    required_area_fields: List[str]
    existing_area_names: List[str]
    existing_treasure_names: List[str]
    min_log_lines: int = 20
    min_chapter_count: int = 8

class ContentValidator:
    def __init__(self, rules: ValidationRules):
        self.rules = rules

    def validate_area_name(self, name: str) -> bool:
        invalid_chars = {'-', 'ー', '-', '~', '〜', '〰', '|', '[', ']', '「', '」', ':', ';', '@', '/', '>', '深', '裏'}
        return (
            not any(char in name for char in invalid_chars) and
            not any(area in name for area in self.rules.existing_area_names) and
            name not in self.rules.existing_area_names
        )

    def validate_treasure_name(self, treasure: str) -> bool:
        return not any(
            existing in treasure or treasure in existing
            for existing in self.rules.existing_treasure_names
        )

    def validate_log_content(self, content: List[str]) -> bool:
        return (
            len(content) >= self.rules.min_log_lines and
            not self.rules.forbidden_words.intersection(
                word for line in content for word in line.split()
            )
        )

    def validate_chapters(self, chapters: List[Dict]) -> bool:
        return (
            len(chapters) == self.rules.min_chapter_count and
            all(self._validate_chapter(chapter) for chapter in chapters)
        )

    def _validate_chapter(self, chapter: Dict) -> bool:
        required_keys = {"number", "title", "content"}
        return (
            all(key in chapter for key in required_keys) and
            not set(self.rules.forbidden_words).intersection(chapter["content"].split())
        )

    def validate_area_content(self, content: Dict) -> None:
        # 必須フィールドのチェック
        for field in self.rules.required_area_fields:
            if field not in content:
                raise ValueError(f"必須フィールドがありません: {field}")

        # NGワードチェック
        for field in self.rules.required_area_fields: # 全フィールドをチェック
            value = str(content.get(field, '')) # エラーを防ぐため get を使用し、文字列に変換
            if set(self.rules.forbidden_words).intersection(value.split()):
                raise ValueError(f"NGワードが含まれています: {field} - {value}")