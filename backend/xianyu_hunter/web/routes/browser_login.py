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
# 打包后 __file__ 在 _internal/ 下，parents[4] 会指错位置；统一走 paths.get_app_dir()
# 开发模式返回项目根 CWD，打包模式返回 exe 同级目录（安装时复制 scripts/ 子进程脚本）
from xianyu_hunter.paths import get_app_dir

logger = logging.getLogger(__name__)
router = APIRouter(tags=["browser-login"])

_REPO = get_app_dir()
_BROWSER_LOGIN_SCRIPT = _REPO / "scripts" / "browser_login.py"

# 全局状态
_browser_login_state: dict = {
    "status": "idle",  # idle | running | success | cancelled | error | timeout
    "status_file": None,
    "pid": None,
    "proc": None,
}


def _reset_browser_login_state() -> None:
    """重置浏览器登录状态为 idle

    为什么提取：原函数中多次重复相同的重置字典赋值，提取为函数后减少重复，
    也避免因拼写不一致导致的 bug。
    """
    global _browser_login_state
    _browser_login_state = {
        "status": "idle",
        "status_file": None,
        "pid": None,
        "proc": None,
        "cookies_injected": False,
    }


def _check_process_exited(proc: subprocess.Popen | None) -> bool:
    """检测1：子进程是否已通过 poll() 退出"""
    if proc is None:
        return False
    if proc.poll() is None:
        return False
    logger.warning("浏览器登录子进程已退出（exitcode=%d），强制重置", proc.returncode)
    return True


def _check_pid_not_exists(pid: int | None) -> bool:
    """检测2：pid 是否还存在（使用 psutil）"""
    if not pid:
        return False
    try:
        import psutil
        if not psutil.pid_exists(pid):
            logger.warning("浏览器登录子进程 pid=%d 已不存在，强制重置", pid)
            return True
    except ImportError:
        pass
    return False


def _check_heartbeat_timeout(status_file: str | None, proc: subprocess.Popen | None) -> bool:
    """检测3：status file 心跳是否超时（30s 阈值）

    阈值 30s：子进程心跳 3s + Playwright 偶尔阻塞 5-10s + 余量。
    为什么需要：bc.cookies() 阻塞时 _background_wait_browser_login 仍在
    proc.wait(timeout=310) 中阻塞，proc.poll() 仍返回 None，
    status file 也不更新，_browser_login_state 永远停留在 running。
    心跳超时检测能识别"子进程未死但已无响应"的卡死状态。
    """
    if not status_file:
        return False

    path = Path(status_file)
    if not path.exists():
        return False

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        ts = data.get("ts")
        if ts is None:
            return False

        stale_sec = time.time() - float(ts)
        if stale_sec <= 30:
            return False

        logger.warning(
            "浏览器登录子进程心跳超时（%.1fs 未更新），强制 kill 并重置",
            stale_sec,
        )
        if proc and proc.poll() is None:
            try:
                proc.kill()
            except OSError:
                pass
        return True
    # S5713: JSONDecodeError 是 ValueError 子类，二者择一即可；OSError 独立
    except (ValueError, OSError):
        return False


def _cleanup_dead_process() -> None:
    """检测子进程是否已死亡，若死亡则重置状态

    三重检测：
    1. subprocess.Popen.poll() — 子进程是否已退出
    2. psutil.pid_exists() — pid 是否还存在
    3. status file 心跳超时 — 即使子进程未死但已卡死也应清理

    重构说明：将三重检测拆分为独立函数，按顺序短路返回，
    认知复杂度从 28 降到 7 以下。
    """
    global _browser_login_state
    if _browser_login_state["status"] != "running":
        return

    proc = _browser_login_state.get("proc")
    pid = _browser_login_state.get("pid")
    status_file = _browser_login_state.get("status_file")

    if _check_process_exited(proc):
        _reset_browser_login_state()
        return

    if _check_pid_not_exists(pid):
        _reset_browser_login_state()
        return

    if _check_heartbeat_timeout(status_file, proc):
        _reset_browser_login_state()


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
        # 使用 pythonw.exe 静默启动（无控制台窗口），提升用户体验
        # 复用 unified_login 的工具函数，保持两个路由行为一致
        from xianyu_hunter.web.routes.unified_login import _build_script_subprocess_command, _get_quiet_python_executable
        python_exe, creation_flags = _get_quiet_python_executable()
        cmd = _build_script_subprocess_command(
            python_exe,
            _BROWSER_LOGIN_SCRIPT,
            "--status-file", str(status_file),
            "--timeout", "300",
        )
        proc = subprocess.Popen(
            cmd,
            # creation_flags 由 _get_quiet_python_executable 决定：
            # - pythonw.exe 可用时为 0（完全静默，不弹 python.exe 黑窗）
            # - fallback 到 python.exe 时为 CREATE_NEW_CONSOLE（防 Playwright 闪退）
            creationflags=creation_flags,
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


_RUNNING_STATES = ("pending", "starting", "running", "waiting", "opening", "already_logged")
_FINAL_STATES = ("success", "cancelled", "error", "timeout")


def _read_status_file(path: Path) -> dict | None:
    """读取状态文件并解析为 JSON，失败返回 None"""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _handle_heartbeat_timeout(data: dict, file_status: str, path: Path) -> dict | None:
    """处理心跳超时逻辑，返回超时后的 data，未超时返回 None

    重构说明：将心跳超时检测和处理逻辑独立出来，降低主函数复杂度。
    """
    ts = data.get("ts")
    if ts is None:
        return None

    from xianyu_hunter.web.routes.unified_login import _heartbeat_timeout_for_status
    stale_sec = time.time() - float(ts)
    if stale_sec <= _heartbeat_timeout_for_status(file_status):
        return None

    logger.warning(
        "浏览器登录子进程心跳超时（%.1fs 未更新），判定为卡死",
        stale_sec,
    )

    proc = _browser_login_state.get("proc")
    if proc and proc.poll() is None:
        try:
            proc.kill()
        except OSError:
            pass

    _browser_login_state["status"] = "error"
    data["status"] = "error"
    data["message"] = f"登录进程无响应（{stale_sec:.0f}s 未更新），请重试"

    try:
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass

    return data


async def _handle_final_success(data: dict) -> dict:
    """处理登录成功终态：注入 Cookie 到 Worker 并返回认证响应"""
    if not _browser_login_state.get("cookies_injected"):
        await _inject_cookies_to_worker()
        _browser_login_state["cookies_injected"] = True
    return make_auth_response(data)


@router.get("/browser-login/status")
async def browser_login_status() -> dict:
    """轮询浏览器登录状态

    登录成功时，自动将 Cookie 注入到 Worker 浏览器实例中，
    解决 Worker 在登录前已启动、内存中缺少登录 Cookie 的问题。

    心跳检测：检查 status file 的 ts 字段，如果距上次更新超过阈值，
    说明子进程可能卡住或被异常 kill，主动标记为 error 让前端停止轮询。

    重构说明：将状态检查、心跳检测、终态处理拆分为独立函数，
    主函数只做流程编排，认知复杂度从 32 降到 10 以下。
    """
    global _browser_login_state

    _cleanup_dead_process()

    if _browser_login_state["status"] == "idle":
        return {"status": "idle", "message": "未启动登录（上次进程已超时清理）"}

    status_file = _browser_login_state.get("status_file")
    if not status_file:
        return {"status": "running", "message": "等待浏览器启动..."}

    path = Path(status_file)
    if not path.exists():
        return {"status": "running", "message": "浏览器启动中..."}

    data = _read_status_file(path)
    if data is None:
        return {"status": "running", "message": "状态文件读取失败"}

    file_status = data.get("status", "running")

    if file_status in _RUNNING_STATES:
        timeout_result = _handle_heartbeat_timeout(data, file_status, path)
        if timeout_result is not None:
            return timeout_result

    if file_status not in _FINAL_STATES:
        return data

    if _browser_login_state["status"] != file_status:
        _browser_login_state["status"] = file_status

    if file_status == "success":
        return await _handle_final_success(data)

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
