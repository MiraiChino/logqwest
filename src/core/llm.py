from dataclasses import dataclass
from typing import Dict
import google.generativeai as genai
from groq import Groq

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
        return response.text

class GroqClient(BaseClient):
    def __init__(self, model: str = "gemma2-9b-it"):
        super().__init__(model)
        self.client = Groq()

    def generate_response(self, prompt: str, temperature: float = 0.6, max_tokens: int = 8192, response_format: Dict = ResponseFormat.TEXT) -> str:
        response = self.client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=self.model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )
        return response.choices[0].message.content

class ClientFactory:
    @staticmethod
    def create_client(client_type: str, model: str = None) -> BaseClient:
        clients = {
            "gemini": lambda m: GeminiClient(m or "models/gemini-2.0-flash-001"),
            "groq": lambda m: GroqClient(m or "gemma2-9b-it")
        }
        
        if client_type not in clients:
            raise ValueError(f"Unsupported client type: {client_type}")
            
        return clients[client_type](model)
