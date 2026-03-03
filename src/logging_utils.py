"""
统一日志工具
============
为项目提供一致的日志格式与文件落盘能力。
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from src.config import settings

_IS_INITIALIZED = False


def init_logging() -> None:
    """初始化全局日志配置（幂等）。"""
    global _IS_INITIALIZED
    if _IS_INITIALIZED:
        return

    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / settings.LOG_FILE_NAME

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(lineno)d| %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    if not root_logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        file_handler = RotatingFileHandler(
            filename=str(log_file),
            maxBytes=2 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    _IS_INITIALIZED = True


def get_logger(name: str) -> logging.Logger:
    init_logging()
    return logging.getLogger(name)

