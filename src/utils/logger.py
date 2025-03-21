from enum import Enum
from datetime import datetime
from pathlib import Path
from typing import Optional

class LogLevel(Enum):
    INFO = "ℹ️"
    GENERATE = "💬"
    SUCCESS = "✅"
    WARNING = "🚧"
    ERROR = "❌"
    DELETE = "🔥"
    SIMPLE = ""

class Logger:
    def __init__(self, log_file: Optional[Path] = None):
        self.log_file = log_file
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)

    def log(self, message: str, level: LogLevel = LogLevel.INFO) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if level == LogLevel.SIMPLE:
            formatted_message = f"{timestamp} {message}"
        else:
            formatted_message = f"{timestamp} {level.value} {message}"
        print(formatted_message)
        if self.log_file:
            with self.log_file.open('a', encoding='utf-8') as f:
                f.write(f"{formatted_message}\n")

    def info(self, message: str) -> None:
        self.log(message, LogLevel.INFO)

    def generate(self, message: str) -> None:
        self.log(message, LogLevel.GENERATE)

    def success(self, message: str) -> None:
        self.log(message, LogLevel.SUCCESS)

    def warning(self, message: str) -> None:
        self.log(message, LogLevel.WARNING)

    def error(self, message: str) -> None:
        self.log(message, LogLevel.ERROR)

    def delete(self, message: str) -> None:
        self.log(message, LogLevel.DELETE)

    def simple(self, message: str) -> None:
        self.log(message, LogLevel.SIMPLE)
