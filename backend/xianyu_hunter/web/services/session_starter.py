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
    - start_session_default 是同步方法，直接调用即可；
      TokenRenewer.start() 内部通过 asyncio.create_task 调度 _renew_loop 协程
    """
    try:
        from xianyu_hunter.modules.login_orchestrator import get_orchestrator

        orch = get_orchestrator()
        # start_session_default 是同步方法（返回 bool），
        # 不能用 loop.create_task 包装——create_task 要求 coroutine，
        # 传入 bool 会抛 TypeError 被外层 except 吞掉，导致会话永远不启动。
        # 直接同步调用：start_session 内部调用 TokenRenewer.start()，
        # 后者自行 create_task(_renew_loop) 调度后台续期协程。
        orch.start_session_default()
    except Exception as e:
        logger.warning("自动启动会话失败: %s", e, exc_info=True)
