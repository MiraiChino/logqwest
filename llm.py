import time
import traceback
from functools import wraps
import requests
import sys
from groq import Groq
import google.generativeai as genai

from config import DEFAULT_WAIT_TIME, MAX_RETRIES

# 型定義
TYPE_JSON = {"type": "json_object"}
TYPE_TEXT = {"type": "text"}

def retry_on_failure(max_retries=MAX_RETRIES, wait_time=DEFAULT_WAIT_TIME, logger=None):
    if logger is None:
        logger = print
    if max_retries <= 0 or wait_time < 0:
        raise ValueError("max_retries は 0 より大きく、wait_time は 0 以上である必要があります。")
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_retries + 1):
                try:
                    response = func(*args, **kwargs)
                    if response:
                        return response
                    logger(f"[Attempt {attempt}/{max_retries}] 空または無効なレスポンスを受信しました。")
                except requests.RequestException as e:
                    logger(f"[Attempt {attempt}/{max_retries}] RequestException: {e}")
                except Exception as e:
                    if any(err_msg in str(e) for err_msg in ["429", "Rate limit", "RESOURCE_EXHAUSTED"]):
                        logger("レート制限超過。15分間スリープ後にプログラムを終了します...")
                        time.sleep(60 * 15)
                        sys.exit(1) # プログラムを終了
                    else:
                        logger(f"[Attempt {attempt}/{max_retries}] エラー: {traceback.format_exc()}")
                if attempt < max_retries:
                    logger(f"[Attempt {attempt}/{max_retries}] {wait_time}秒後にリトライします...")
                    time.sleep(wait_time)
            raise ValueError(f"[Attempt {max_retries}/{max_retries}] 最大リトライ回数に達しました。")
        return wrapper
    return decorator


class ChatClient:
    def __init__(self, model):
        self.model = model

    def get_response(self, user_prompt, temperature, max_tokens, response_format):
        raise NotImplementedError("サブクラスで実装してください。")


class GeminiChat(ChatClient):
    def __init__(self, model="models/gemini-2.0-flash-exp"):
        super().__init__(model)
        self.client = genai.GenerativeModel(model)

    def get_response(self, user_prompt, temperature=1.5, max_tokens=8192, response_format=TYPE_TEXT):
        response = self.client.generate_content(
            user_prompt,
            generation_config=genai.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
        )
        return response.text


class GroqChat(ChatClient):
    def __init__(self, model="gemma2-9b-it"):
        super().__init__(model)
        self.client = Groq()

    def get_response(self, user_prompt, temperature=0.6, max_tokens=8192, response_format=TYPE_TEXT):
        chat_completion = self.client.chat.completions.create(
            messages=[{"role": "user", "content": user_prompt}],
            model=self.model,
            temperature=temperature,
            max_tokens=max_tokens,
            stop=None,
            response_format=response_format,
        )
        return chat_completion.choices[0].message.content