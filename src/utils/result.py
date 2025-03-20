from dataclasses import dataclass
from typing import Optional, TypeVar, Generic, Dict, List

T = TypeVar('T')

@dataclass
class Result(Generic[T]):
    success: bool
    value: Optional[T] = None
    error: Optional[str] = None

class GenerationError(Exception):
    def __init__(self, message: str, details: Optional[Dict] = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)

class ValidationError(Exception):
    def __init__(self, message: str, validation_errors: List[str]):
        self.message = message
        self.validation_errors = validation_errors
        super().__init__(message)
