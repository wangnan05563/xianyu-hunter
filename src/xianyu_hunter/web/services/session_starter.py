"""会话启动辅助：登录成功后自动启动会话管理（TokenRenewer 后台续期）

设计动机：用户登录完成后，会话需要保持活跃（_m_h5_tk 自动续期）才能
支撑后续实时搜索/详情采集。在前端反爬登录管理菜单中原本需要用户
手动点击"启动会话"，登录成功的瞬间自动调起可减少操作步骤。

被以下登录入口调用：
- unified_login.py：统一登录（QR/浏览器窗口）
- browser_login.py：旧版浏览器登录
- browser_import.py：从系统浏览器导入 Cookie
- cookie_inject.py：手动 Cookie 注入
"""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


def trigger_session_start() -> None:
    """登录成功后自动启动会话管理（fire-and-forget）

    实现要点：
    - 已活跃时 start_session_default 内部会跳过，无副作用
    - 失败仅记录日志，不抛异常（避免影响登录成功的返回路径）
    - 后台线程调用时通过 create_task/ensure_future 调度到 FastAPI 主事件循环
    """
    try:
        from xianyu_hunter.modules.login_orchestrator import get_orchestrator

        orch = get_orchestrator()
        # get_running_loop 替代 get_event_loop：前者无运行循环时抛 RuntimeError
        # 走 except 分支；后者在 3.12+ 已弃用
        loop = asyncio.get_running_loop()
        # fire-and-forget：登录流程不应等待会话启动
        # 保存引用防止任务被 GC 回收
        _session_task = loop.create_task(orch.start_session_default())
    except RuntimeError:
        # 罕见：事件循环未运行时退化为同步执行（一般不会发生）
        try:
            from xianyu_hunter.modules.login_orchestrator import get_orchestrator
            get_orchestrator().start_session_default()
        except Exception as e:
            logger.debug("自动启动会话失败: %s", e)
    except Exception as e:
        logger.debug("自动启动会话失败: %s", e)
