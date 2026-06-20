"""FastAPI 依赖注入

复用 CLI 使用的 Container 工厂，避免在 Web 进程里重新装配组件。
注意：Web 进程里只读 DB + 写 DB，不持有浏览器实例。
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import TYPE_CHECKING

from xianyu_hunter.container import Container, build_default_container

if TYPE_CHECKING:
    pass


def _should_start_scheduler() -> bool:
    """检查环境变量 XH_WITH_SCHEDULER 是否启用调度器"""
    return os.environ.get("XH_WITH_SCHEDULER", "").strip() in ("1", "true", "yes")


@lru_cache(maxsize=1)
def get_container() -> Container:
    """单例容器（Web 进程内）

    默认 with_browser=False，跳过 BrowserManager/AntiDetect/Collector/Buyer 构造，
    Web 进程不需要浏览器实例（节省 ~100-200MB 内存）。

    当 XH_WITH_SCHEDULER=1 时，with_browser=True，同时启动调度器。
    """
    with_browser = _should_start_scheduler()
    return build_default_container(with_browser=with_browser)
