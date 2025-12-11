"""
Module ghi log và xử lý lỗi
"""
import logging
import os
from datetime import datetime
from typing import Optional, Callable


class Logger:
    """Class ghi log với nhiều level"""

    def __init__(self, name: str, log_file: Optional[str] = None,
                 on_error: Optional[Callable[[str], None]] = None):
        self.name = name
        self.on_error = on_error

        # Tạo logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        # Format
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # File handler
        if log_file is None:
            os.makedirs("logs", exist_ok=True)
            log_file = f"logs/chat_{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

    def debug(self, message: str):
        """Log debug message"""
        self.logger.debug(message)

    def info(self, message: str):
        """Log info message"""
        self.logger.info(message)

    def warning(self, message: str):
        """Log warning message"""
        self.logger.warning(message)

    def error(self, message: str, notify: bool = True):
        """Log error message"""
        self.logger.error(message)
        if notify and self.on_error:
            self.on_error(message)

    def critical(self, message: str, notify: bool = True):
        """Log critical message"""
        self.logger.critical(message)
        if notify and self.on_error:
            self.on_error(f"CRITICAL: {message}")

    def exception(self, message: str, notify: bool = True):
        """Log exception với traceback"""
        self.logger.exception(message)
        if notify and self.on_error:
            self.on_error(message)
