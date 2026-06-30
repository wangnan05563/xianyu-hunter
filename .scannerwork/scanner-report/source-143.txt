"""Playwright 有头浏览器登录 - 比 WebView2 更可靠

端点：
- POST /api/auth/browser-login        启动 Playwright 浏览器登录
- GET  /api/auth/browser-login/status 轮询登录状态
- POST /api/auth/browser-login/cancel 取消登录

原理：
1. 启动 Playwright 有头浏览器子进程（browser_login.py）
2. 与 Worker 共享同一 user_data_dir，Cookie 天然兼容，无需跨进程复制
3. 用户在浏览器中正常登录后，Worker 立即可用
4. 通过状态文件（JSON）与 web 后端通信
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from xianyu_hunter.web.routes.auth_helpers import make_auth_response

logger = logging.getLogger(__name__)
router = APIRouter(tags=["browser-login"])

_REPO = Path(__file__).resolve().parents[4]
_BROWSER_LOGIN_SCRIPT = _REPO / "scripts" / "browser_login.py"

# 全局状态
_browser_login_state: dict = {
    "status": "idle",  # idle | running | success | cancelled | error | timeout
    "status_file": None,
    "pid": None,
    "proc": None,
}


def _cleanup_dead_process() -> None:
    """检测子进程是否已死亡，若死亡则重置状态"""
    global _browser_login_state
    pid = _browser_login_state.get("pid")
    proc = _browser_login_state.get("proc")
    if _browser_login_state["status"] != "running":
        return
    # 检查 subprocess.Popen 对象
    if proc is not None and proc.poll() is not None:
        logger.warning("浏览器登录子进程已退出（exitcode=%d），强制重置", proc.returncode)
        _browser_login_state = {"status": "idle", "status_file": None, "pid": None, "proc": None, "cookies_injected": False}
        return
    # 检查 pid
    if pid:
        try:
            import psutil
            if not psutil.pid_exists(pid):
                logger.warning("浏览器登录子进程 pid=%d 已不存在，强制重置", pid)
                _browser_login_state = {"status": "idle", "status_file": None, "pid": None, "proc": None, "cookies_injected": False}
        except ImportError:
            pass


@router.post("/browser-login")
def start_browser_login() -> JSONResponse:
    """启动 Playwright 浏览器登录窗口"""
    global _browser_login_state

    _cleanup_dead_process()

    if _browser_login_state["status"] == "running":
        return JSONResponse(content={
            "ok": False,
            "error": "登录窗口已在运行中",
            "status": "running",
        })

    if not _BROWSER_LOGIN_SCRIPT.exists():
        return JSONResponse(content={
            "ok": False,
            "error": "browser_login.py 脚本缺失，请检查 scripts/ 目录",
        })

    # 创建状态文件
    tmp_dir = Path(tempfile.gettempdir()) / "xh_browser_login"
    tmp_dir.mkdir(exist_ok=True)
    status_file = tmp_dir / f"browser_login_{int(time.time() * 1000)}.json"

    try:
        proc = subprocess.Popen(
            [
                sys.executable, str(_BROWSER_LOGIN_SCRIPT),
                "--status-file", str(status_file),
                "--timeout", "300",
            ],
            # 必须使用 CREATE_NEW_CONSOLE 而非 CREATE_NO_WINDOW
            # CREATE_NO_WINDOW 会导致 GUI 子进程（Playwright 浏览器）不稳定或闪退
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except Exception as e:
        logger.error("浏览器登录子进程启动失败: %s", e)
        return JSONResponse(content={
            "ok": False,
            "error": f"无法启动浏览器: {e}",
        })

    _browser_login_state = {
        "status": "running",
        "status_file": str(status_file),
        "pid": proc.pid,
        "proc": proc,
        "cookies_injected": False,
    }

    # 后台线程：等待子进程退出后处理终态
    threading.Thread(
        target=_background_wait_browser_login,
        args=(proc, status_file),
        daemon=True,
    ).start()

    logger.info("浏览器登录窗口已启动, pid=%d, status_file=%s", proc.pid, status_file)
    return JSONResponse(content={"ok": True, "status": "running", "message": "浏览器登录窗口已启动"})


def _background_wait_browser_login(proc: subprocess.Popen, status_file: Path) -> None:
    """后台线程：等待子进程退出，同步终态"""
    global _browser_login_state
    try:
        proc.wait(timeout=310)  # timeout 300 + 10 秒缓冲
    except subprocess.TimeoutExpired:
        logger.warning("浏览器登录子进程超时，强制终止")
        try:
            proc.kill()
        except OSError:
            pass

    # 读取子进程输出用于调试
    try:
        stdout, stderr = proc.communicate(timeout=5)
        if stdout:
            logger.debug("浏览器登录 stdout: %s", stdout.decode(errors="replace")[:500])
        if stderr:
            stderr_text = stderr.decode(errors="replace")
            # 只记录关键信息，避免日志过多
            for line in stderr_text.splitlines()[:10]:
                logger.debug("浏览器登录 stderr: %s", line[:200])
    except Exception:
        pass

    # 子进程退出后，从状态文件读取最终状态
    try:
        if status_file.exists():
            data = json.loads(status_file.read_text(encoding="utf-8"))
            final_status = data.get("status", "error")
            _browser_login_state["status"] = final_status
            if final_status == "success":
                # 触发用户信息刷新
                _trigger_userinfo_refresh()
                _trigger_session_start()
                logger.info("浏览器登录成功，Cookie 已写入 browser-data (count=%s)", data.get("cookie_count", "?"))
            else:
                logger.info("浏览器登录结束，状态: %s, 消息: %s", final_status, data.get("message", ""))
        else:
            _browser_login_state["status"] = "error"
    except Exception as e:
        logger.error("读取浏览器登录状态文件失败: %s", e)
        _browser_login_state["status"] = "error"


@router.get("/browser-login/status")
async def browser_login_status() -> dict:
    """轮询浏览器登录状态

    登录成功时，自动将 Cookie 注入到 Worker 浏览器实例中，
    解决 Worker 在登录前已启动、内存中缺少登录 Cookie 的问题。
    """
    global _browser_login_state

    _cleanup_dead_process()

    if _browser_login_state["status"] == "idle":
        return {"status": "idle", "message": "未启动登录"}

    status_file = _browser_login_state.get("status_file")
    if not status_file:
        return {"status": "running", "message": "等待浏览器启动..."}

    path = Path(status_file)
    if not path.exists():
        return {"status": "running", "message": "浏览器启动中..."}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return {"status": "running", "message": f"状态文件读取失败: {e}"}

    # 终态同步内存状态
    file_status = data.get("status", "running")
    if file_status in ("success", "cancelled", "error", "timeout"):
        if _browser_login_state["status"] != file_status:
            _browser_login_state["status"] = file_status
        if file_status == "success":
            # 登录成功：将 Cookie 注入到 Worker 浏览器实例
            # Worker 的 BrowserManager 在登录前就已启动，内存中没有登录 Cookie，
            # 需要主动注入才能让实时搜索立即可用
            if not _browser_login_state.get("cookies_injected"):
                await _inject_cookies_to_worker()
                _browser_login_state["cookies_injected"] = True
            # 登录成功时设置 xh_token cookie
            return make_auth_response(data)

    return data


async def _inject_cookies_to_worker() -> None:
    """从 last_login_cookies.json 读取 Cookie 并注入到 Worker 浏览器实例"""
    try:
        from xianyu_hunter.web.deps import get_container
        container = get_container()
        if not container.browser:
            logger.warning("Worker 浏览器实例未初始化，跳过 Cookie 注入")
            return

        cookie_file = _REPO / "data" / "last_login_cookies.json"
        if not cookie_file.exists():
            logger.warning("Cookie 文件不存在: %s，跳过注入", cookie_file)
            return

        cookies = json.loads(cookie_file.read_text(encoding="utf-8"))
        if not cookies:
            logger.warning("Cookie 文件为空，跳过注入")
            return

        logger.info("开始向 Worker 浏览器实例注入 %d 个 Cookie...", len(cookies))
        success = await container.browser.add_cookies(cookies)
        if success:
            logger.info("Cookie 注入成功，实时搜索现在可用")
            # 同步 CookieRotator 层状态：浏览器登录子进程已写 JSON，
            # 需主动同步层状态以避免 /cookies/layers 显示失效
            try:
                from xianyu_hunter.modules.login_orchestrator import sync_cookie_layers_from_json
                sync_cookie_layers_from_json()
            except Exception as e:
                logger.debug("浏览器登录后同步层状态失败: %s", e)
        else:
            logger.error("Cookie 注入失败：关键 Cookie 验证未通过")
    except Exception as e:
        logger.error("Cookie 注入异常: %s", e)


@router.post("/browser-login/cancel")
def cancel_browser_login() -> dict:
    """取消浏览器登录"""
    global _browser_login_state
    if _browser_login_state["status"] != "running":
        return {"ok": False, "error": "没有正在进行的登录"}
    proc = _browser_login_state.get("proc")
    if proc and proc.poll() is None:
        try:
            proc.terminate()
            # 给子进程一点时间清理
            time.sleep(0.5)
            if proc.poll() is None:
                proc.kill()
        except OSError:
            pass
    _browser_login_state = {"status": "idle", "status_file": None, "pid": None, "proc": None, "cookies_injected": False}
    return {"ok": True, "message": "已取消"}


def _trigger_userinfo_refresh() -> None:
    """登录成功后触发用户信息刷新"""
    try:
        from xianyu_hunter.web.services.auth_manager import get_auth_manager
        get_auth_manager().trigger_refresh_userinfo_async()
    except Exception as e:
        logger.debug("触发用户信息刷新失败: %s", e)


def _trigger_session_start() -> None:
    """登录成功后自动启动会话管理（TokenRenewer 后台续期）"""
    from xianyu_hunter.web.services.session_starter import trigger_session_start
    trigger_session_start()