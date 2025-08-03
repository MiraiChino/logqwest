from functools import wraps
import time
import traceback
from typing import Callable, TypeVar, Any


T = TypeVar('T')

class RateLimitExeeded(Exception):
    pass

class RetryLimitExeeded(Exception):
    pass

class EmptyResponseError(Exception):
    pass

def retry_on_failure(max_retries: int = 10, wait_time: int = 10) -> Callable:
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            backoff = max(wait_time, 10)
            waited = 0
            max_total_wait = 60 * 15
            last_exc: Exception | None = None
            for attempt in range(1, max_retries + 1):
                try:
                    response = func(*args, **kwargs)
                    if response is None:
                        raise EmptyResponseError("Received empty or invalid response")
                    return response
                except Exception as e:
                    last_exc = e
                    msg = str(e)
                    if any(err in msg for err in ["408", "429", "Rate limit", "RESOURCE_EXHAUSTED", "500", "502", "503", "504"]):
                        if waited >= max_total_wait:
                            raise RateLimitExeeded("Rate limit exceeded") from e
                        sleep_for = min(backoff, 60, max_total_wait - waited)
                        time.sleep(sleep_for)
                        waited += sleep_for
                        backoff = min(backoff * 2, 60)
                        continue
                    print(f"❌ {attempt}/{max_retries}: {traceback.format_exc()}")
                    if attempt < max_retries:
                        time.sleep(backoff)
                        backoff = min(backoff * 2, 60)
                    else:
                        raise
            raise RetryLimitExeeded(f"❌ {attempt}/{max_retries}: リトライ回数上限に達しました。") from last_exc
        return wrapper
    return decorator
