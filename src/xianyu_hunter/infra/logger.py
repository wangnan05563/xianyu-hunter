"""日志配置（loguru）"""
from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from xianyu_hunter.config import get_settings


_configured = False


def setup_logging() -> None:
    """全局初始化日志：控制台 + 文件双输出，结构化"""
    global _configured
    if _configured:
        return
    _configured = True

    settings = get_settings()
    logger.remove()

    # 控制台：人类可读
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
    )

    # 文件：JSON 结构化（按日滚动，保留 14 天）
    log_dir = Path("data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_dir / "xianyu_{time:YYYY-MM-DD}.log",
        level="DEBUG",
        rotation="00:00",
        retention="14 days",
        encoding="utf-8",
        serialize=True,  # JSON
    )

    # 实时日志 SSE 流需要 run.stdout.log 文件
    # 以纯文本格式写入，供 /api/logs/stream 轮询推送
    # 使用绝对路径确保文件创建在项目根目录
    import os
    _project_root = Path(os.getcwd())
    logger.add(
        _project_root / "run.stdout.log",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        encoding="utf-8",
        # 防止日志文件无限增长填满磁盘：每 10MB 轮转，保留 3 个备份
        rotation="10 MB",
        retention=3,
    )


def get_logger():
    """获取已配置的 logger"""
    return logger
