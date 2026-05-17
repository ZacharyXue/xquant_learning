"""
统一日志系统

使用 RotatingFileHandler，按日期分目录。
提供结构化日志接口，禁止直接使用 print。
"""

import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

LOG_DIR = Path(__file__).parent.parent.parent / "logs"

_loggers: dict[str, logging.Logger] = {}


def _create_log_dir() -> Path:
    today = datetime.now().strftime("%Y%m%d")
    log_dir = LOG_DIR / today
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def setup_logging(level: int = logging.DEBUG) -> None:
    """初始化根日志配置"""
    log_dir = _create_log_dir()

    root = logging.getLogger()
    root.setLevel(level)

    if root.handlers:
        return

    fmt = logging.Formatter(
        "%(asctime)s - [%(name)s] - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 控制台输出
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(fmt)
    root.addHandler(console)

    # 文件输出 (按模块分别记录)
    file_handler = RotatingFileHandler(
        log_dir / "app.log", maxBytes=10_485_760, backupCount=5, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """获取模块日志器"""
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)
    _loggers[name] = logger
    return logger
