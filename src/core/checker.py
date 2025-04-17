import re
from abc import ABC
from typing import Dict, List, Optional
from pathlib import Path
import json
import json5

from src.core.client import BaseClient, ResponseFormat
from src.utils.csv_handler import CSVHandler

class ContentChecker(ABC):
    def __init__(self, client: BaseClient, template_path: Optional[Path], check_keys: List, check_marks: str):
        self.client = client
        self.json_pattern = re.compile(r"```json\n(.*?)```", re.DOTALL)
        self.template = self._load_template(template_path)
        self.check_keys = check_keys
        self.check_marks = check_marks
        self.csv_handler = CSVHandler()

    def _load_template(self, template_path: Optional[Path]) -> Optional[str]:
        if not template_path:
            return None
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")
        return template_path.read_text(encoding="utf-8")

    def extract_json(self, response: str) -> Dict:
        match = self.json_pattern.search(response)
        if match:
            json_text = match.group(1).strip()
            try:
                contents = json5.loads(json_text)
                return contents
            except json.JSONDecodeError as e:
                raise ValueError(f"JSONデコードエラーが発生しました:\n{e}\nレスポンスから抽出されたJSONテキスト:\n", json_text)
        else:
            raise ValueError("レスポンスからJSONコードブロックを抽出できませんでした。\nレスポンス:\n", response)

    def validate_content(self, content: Dict) -> bool:
        for key in self.check_keys:
            if key not in content:
                raise ValueError(f"JSONレスポンスに必須キー '{key}' がありません。")
            if not content[key]: # 値が空かどうかチェック
                raise ValueError(f"キー '{key}' の値が空です。")
        return True

    def is_all_checked(self, check_result: Dict) -> bool:
        for key in self.check_keys:
            if key not in check_result:
                raise ValueError(f"キー '{key}' が存在しません。")
            if "評価" not in check_result[key]:
                raise ValueError(f"キー '{key}' に '評価' フィールドが存在しません。")
            if check_result[key]["評価"] not in self.check_marks:
                raise ValueError(f"{key}: {check_result[key]["評価"]}{check_result[key]["理由"]}")
        return True

    def generate(self, response_format: Dict = ResponseFormat.TEXT, temperature: float = 0, 
                max_tokens: int = 8192, debug: bool = False, **kwargs) -> Dict:
        if not self.template:
            raise ValueError("Template not loaded")
            
        prompt = self.template.format(**kwargs)
        if debug:
            print(prompt)
        response = self.client.generate_response(
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format
        )
        if debug:
            print(response)
        # 生成時に渡された冒険名、エリア名があれば結果に含める
        result = self.extract_json(response)
        if "adventure_name" not in result and "adventure_name" in kwargs:
            result["adventure_name"] = kwargs["adventure_name"]
        if "area_name" not in result and "area_name" in kwargs:
            result["area_name"] = kwargs["area_name"]
        return result

    def save(self, results: Dict, csv_path: Path) -> None:
        # resultsに冒険名が含まれていることを前提とする
        if "adventure_name" not in results:
            raise ValueError("resultsに 'adventure_name' キーが含まれている必要があります。")
        adventure_name = results["adventure_name"]
        csv_row = self._format_csv_row(adventure_name, results)
        self.csv_handler.write_row(csv_path, csv_row, headers=["冒険名"] + self.check_keys)
        self.csv_handler.sort_by_result(csv_path)

    def _format_csv_row(self, name: str, content: Dict) -> List[str]:
        row = [name]
        for key in self.check_keys:
            value = content[key]["評価"] + content[key]["理由"]
            row.append(value)
        return row