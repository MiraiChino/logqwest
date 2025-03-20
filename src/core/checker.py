import re
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from pathlib import Path
import json
import json5

from src.core.client import BaseClient, ResponseFormat
from src.utils.csv_handler import CSVHandler
from src.utils.config import CheckerConfig

class ContentChecker(ABC):
    def __init__(self, client: BaseClient, template_path: Optional[Path], checker_config: CheckerConfig):
        self.client = client
        self.json_pattern = re.compile(r"```json\n(.*?)```", re.DOTALL)
        self.template = self._load_template(template_path)
        self.config = checker_config
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

    @abstractmethod
    def validate_content(self, content: Dict) -> None:
        raise NotImplementedError("validate_contentメソッドはサブクラスで実装する必要があります。")

    def generate(self, response_format: Dict = ResponseFormat.TEXT, temperature: float = 0, 
                max_tokens: int = 8192, **kwargs) -> Dict:
        if not self.template:
            raise ValueError("Template not loaded")
            
        prompt = self.template.format(**kwargs)
        response = self.client.generate_response(
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format
        )
        # 生成時に渡された冒険名があれば結果に含める
        result = self.extract_json(response)
        if "adventure_name" not in result and "adventure_name" in kwargs:
            result["adventure_name"] = kwargs["adventure_name"]
        return result

    def save(self, results: Dict, csv_path: Path) -> None:
        # resultsに冒険名が含まれていることを前提とする
        if "adventure_name" not in results:
            raise ValueError("resultsに 'adventure_name' キーが含まれている必要があります。")
        adventure_name = results["adventure_name"]
        csv_row = self._format_csv_row(adventure_name, results)
        self.csv_handler.write_row(csv_path, csv_row, headers=self.config.headers)
        self.csv_handler.sort_by_result(csv_path)

    @abstractmethod
    def _format_csv_row(self, adventure_name: str, results: Dict) -> List[str]:
        raise NotImplementedError("_format_csv_rowメソッドはサブクラスで実装する必要があります。")