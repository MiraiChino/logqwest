from pathlib import Path
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod
import re
import json
import json5

from src.core.client import BaseClient, ResponseFormat

class ContentGenerator(ABC):
    def __init__(self, client: BaseClient, template_path: Optional[Path] = None):
        self.client = client
        self.template = self._load_template(template_path)
        self.json_pattern = re.compile(r"```json\n(.*?)```", re.DOTALL)

    def _load_template(self, template_path: Optional[Path]) -> Optional[str]:
        if not template_path:
            return None
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")
        return template_path.read_text(encoding="utf-8")

    def generate(self, response_format: Dict = ResponseFormat.TEXT, temperature: float = 1.5, 
                max_tokens: int = 8192, **kwargs) -> Any:
        if not self.template:
            raise ValueError("Template not loaded")
        prompt = self.template.format(**kwargs)
        response = self.client.generate_response(
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format
        )
        return response

    def extract_json(self, response: str) -> str:
        match = self.json_pattern.search(response)
        if not match:
            raise ValueError("レスポンスに```json ```形式のJSONが見つかりません。")
        json_text = match.group(1).strip()
        try:
            content = json5.loads(json_text)
            return content
        except json.JSONDecodeError:
            return None

    @abstractmethod
    def validate_content(self, json_content: Dict) -> None:
        pass

    @abstractmethod
    def create_data(self, json_content: Dict) -> Any:
        pass