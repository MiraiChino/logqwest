from dataclasses import dataclass
from typing import Dict
import google.generativeai as genai
import time
import os
import requests

DEFAULT_WAIT_TIME = 10


@dataclass
class ResponseFormat:
    JSON = {"type": "json_object"}
    TEXT = {"type": "text"}


class BaseClient:
    def __init__(self, model: str):
        self.model = model

    def generate_response(self, prompt: str, temperature: float, max_tokens: int, response_format: Dict) -> str:
        raise NotImplementedError


class GeminiClient(BaseClient):
    def __init__(self, model: str = "models/gemini-2.0-flash-exp"):
        super().__init__(model)
        self.client = genai.GenerativeModel(model)

    def generate_response(self, prompt: str, temperature: float = 1.5, max_tokens: int = 8192, response_format: Dict = ResponseFormat.TEXT) -> str:
        response = self.client.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
        )
        time.sleep(DEFAULT_WAIT_TIME)
        return response.text


class OpenRouterClient(BaseClient):
    def __init__(self, model: str = "openrouter/openai:gpt-4o-mini"):
        super().__init__(model)
        self.base_url = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api")
        self.api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not set")

    def generate_response(self, prompt: str, temperature: float = 0.7, max_tokens: int = 8192, response_format: Dict = ResponseFormat.TEXT) -> str:
        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }
        resp = requests.post(url, headers=headers, json=body, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        time.sleep(DEFAULT_WAIT_TIME)
        return data["choices"][0]["message"]["content"]


class ClientFactory:
    @staticmethod
    def create_client(client_type: str, model: str = None) -> BaseClient:
        clients = {
            "gemini": lambda m: GeminiClient(m or "models/gemini-2.0-flash-001"),
            "openrouter": lambda m: OpenRouterClient(m or "openai:gpt-4o-mini"),
        }

        if client_type not in clients:
            raise ValueError(f"Unsupported client type: {client_type}")

        return clients[client_type](model)
