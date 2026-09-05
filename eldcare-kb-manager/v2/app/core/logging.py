"""统一日志 - loguru 风格 + 控制台 + 文件双输出"""
from __future__ import annotations

import sys

from loguru import logger as _logger

from app.core.config import get_settings


def setup_logging() -> None:
    s = get_settings()
    _logger.remove()
    # 控制台
    _logger.add(
        sys.stderr,
        level=s.log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        colorize=True,
    )
    # 文件（按日切分）
    _logger.add(
        str(s.log_dir / "app-{time:YYYY-MM-DD}.log"),
        level=s.log_level,
        rotation="00:00",
        retention="30 days",
        compression="zip",
        encoding="utf-8",
        enqueue=True,
    )


# 导出供业务模块使用
logger = _logger
