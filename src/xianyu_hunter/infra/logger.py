"""日志配置（loguru）

设计要点：
- 三个 sink 输出：stderr（彩色）+ JSON 文件（结构化）+ 纯文本（SSE 消费）
- 通过 logger.configure(patcher=...) 钩子从 ContextVar 读取 request_id，
  自动注入到每条日志 record 的 extra 字段，业务代码无需手动 bind
- request_id 在三个 sink 的 format 中均以 [req=xxx] token 输出，
  既便于人工肉眼定位，又可被 SSE 流前端按正则解析过滤
"""
from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from xianyu_hunter.config import get_settings
from xianyu_hunter.infra.request_context import get_request_id
from xianyu_hunter.paths import get_log_dir


_configured = False


def _patcher(record) -> None:
    """loguru patcher：在每条日志记录前注入 request_id 到 extra

    通过 logger.configure(patcher=...) 注册后，所有 sink 都能从
    record["extra"]["request_id"] 读取，无需业务代码显式 bind。
    """
    record["extra"]["request_id"] = get_request_id() or "-"


def setup_logging() -> None:
    """全局初始化日志：控制台 + 文件双输出，结构化"""
    global _configured
    if _configured:
        return
    _configured = True

    settings = get_settings()
    logger.remove()

    # 注入 patcher：所有 sink 自动从 ContextVar 读取 request_id
    logger.configure(patcher=_patcher)

    # 控制台：人类可读，含 request_id token 便于排障定位
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>[req={extra[request_id]}]</cyan> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
    )

    # 文件：JSON 结构化（按日滚动，保留 14 天）
    # serialize=True 时 extra 字段自动序列化到 JSON，request_id 随之输出
    # 走 paths.py 统一入口：避免硬编码 Path("data/logs") 在打包后路径错乱
    log_dir = get_log_dir()
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
    # request_id 以 [req=xxx] token 输出，前端可正则解析按 request_id 过滤
    import os
    _project_root = Path(os.getcwd())
    logger.add(
        _project_root / "run.stdout.log",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | [req={extra[request_id]}] | {name}:{function}:{line} - {message}",
        encoding="utf-8",
        # 防止日志文件无限增长填满磁盘：每 10MB 轮转，保留 3 个备份
        rotation="10 MB",
        retention=3,
    )


def get_logger():
    """获取已配置的 logger"""
    return logger
