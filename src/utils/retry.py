from functools import wraps
import time
import traceback
from typing import Callable, TypeVar, Any


T = TypeVar('T')

class RateLimitExeeded(Exception):
    pass

class RetryLimitExeeded(Exception):
    pass

def retry_on_failure(max_retries: int = 10, wait_time: int = 10) -> Callable:
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            for attempt in range(1, max_retries + 1):
                try:
                    response = func(*args, **kwargs)
                    if response:
                        return response
                    error = "Received empty or invalid response"

                except ValueError as e:
                    error = str(e)

                except Exception as e:
                    if any(err in str(e) for err in ["429", "Rate limit", "RESOURCE_EXHAUSTED"]):
                        raise RateLimitExeeded("Rate limit exceeded")
                    else:
                        error = traceback.format_exc()
                print(f"❌ {attempt}/{max_retries}: {error}") 
 
                if attempt < max_retries:
                    time.sleep(wait_time)
                    
            raise RetryLimitExeeded(f"❌ {attempt}/{max_retries}: リトライ回数上限に達しました。")
            
        return wrapper
    return decorator

