"""Web UI 包

提供 FastAPI 应用、路由、Jinja 模板与静态资源。
独立于调度器进程，通过 SQLite 与 EventBus（若同进程）协调。
"""
from xianyu_hunter.web.app import app, create_app

__all__ = ["app", "create_app"]
