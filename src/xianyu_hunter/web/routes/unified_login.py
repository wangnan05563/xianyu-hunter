"""统一登录 API - 支持多种登录方式

端点：
- POST /api/auth/login          启动登录（method: browser / qr）
- GET  /api/auth/login/status   轮询登录状态
- POST /api/auth/login/cancel   取消登录

支持的登录方式：
1. browser - Playwright 有头浏览器（系统 Edge/Chrome），用户手动登录
2. qr      - 二维码扫码登录，headless 浏览器截屏二维码供手机扫码

设计原则：
- 同一时间只允许一个登录会话
- 状态通过内存 + 状态文件双重同步，防止进程崩溃导致状态丢失
- 登录成功后自动触发用户信息刷新
"""
from __future__ import annotations

import base64
import json
import logging
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse

from xianyu_hunter.web.routes.auth_helpers import make_auth_response
from xianyu_hunter.web.services.cookie_store import get_cookie_store

logger = logging.getLogger(__name__)

_REPO = Path(__file__).resolve().parents[4]
_BROWSER_LOGIN_SCRIPT = _REPO / "scripts" / "browser_login.py"
_AUTH_HELPER_SCRIPT = _REPO / "scripts" / "auth_helper.py"

router = APIRouter(tags=["unified-login"])

# ============================================================
# 全局登录会话状态
# ============================================================
_session: dict = {
    "method": None,        # "browser" | "qr" | None
    "status": "idle",      # idle | running | qr_ready | success | cancelled | error | timeout
    "message": "",
    "status_file": None,   # 子进程状态文件路径
    "proc": None,          # subprocess.Popen
    "pid": None,
    "qr_png_b64": None,    # QR 码 base64（qr_ready 时填充）
    "started_at": 0.0,
}
_session_lock = threading.Lock()


def _reset_session() -> None:
    """重置登录会话到 idle 状态"""
    global _session
    with _session_lock:
        # 杀掉残留子进程
        _kill_proc(_session.get("proc"))
        _session = {
            "method": None,
            "status": "idle",
            "message": "",
            "status_file": None,
            "proc": None,
            "pid": None,
            "qr_png_b64": None,
            "started_at": 0.0,
        }


def _kill_proc(proc) -> None:
    """安全终止子进程"""
    if proc is None:
        return
    try:
        if proc.poll() is None:
            proc.terminate()
            time.sleep(0.5)
            if proc.poll() is None:
                proc.kill()
    except OSError:
        pass


def _trigger_userinfo_refresh() -> None:
    """登录成功后触发用户信息刷新 + Cookie 注入到 Playwright 浏览器上下文"""
    try:
        from xianyu_hunter.web.services.auth_manager import get_auth_manager
        get_auth_manager().trigger_refresh_userinfo_async()
    except Exception as e:
        logger.debug("触发用户信息刷新失败: %s", e)

    # 登录成功后把 Cookie 同步注入到后端 Playwright 浏览器上下文
    # 否则 Playwright 内存中的 cookie 仍是旧的/空的，采集时会被闲鱼重定向到首页
    try:
        from xianyu_hunter.web.services.cookie_store import get_cookie_store
        from xianyu_hunter.web.deps import get_container
        import asyncio

        store = get_cookie_store()
        data = store._read_json()
        if not data or not data.get("cookies"):
            return

        container = get_container()
        if not container.browser or not container.browser._context:
            return

        pw_cookies = []
        for c in data["cookies"]:
            pw_cookies.append({
                "name": c["name"],
                "value": c["value"],
                "domain": c.get("domain", ".goofish.com"),
                "path": c.get("path", "/"),
            })

        if pw_cookies:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(
                    container.browser._context.add_cookies(pw_cookies)
                )
                logger.info("已注入 %d 个 Cookie 到 Playwright 浏览器上下文", len(pw_cookies))
    except Exception as e:
        logger.debug("Cookie 注入 Playwright 上下文失败: %s", e)


def _read_status_file(status_file: str | None) -> dict:
    """安全读取子进程状态文件"""
    if not status_file:
        return {}
    path = Path(status_file)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _verify_cookies(max_retries: int = 10, delay: float = 1.0) -> bool:
    """验证闲鱼 Cookie 是否已导出到 JSON 文件

    登录子进程成功后会立即调用 CookieStore.export_cookies() 写入 JSON，
    JSON 文件写入是原子的，比 SQLite 异步写入更可靠。
    """
    store = get_cookie_store()
    for attempt in range(max_retries):
        if store.has_valid_cookies():
            logger.info("Cookie 验证成功 (attempt=%d)", attempt + 1)
            return True
        if attempt < max_retries - 1:
            time.sleep(delay)
    logger.warning("Cookie 验证失败：JSON 中未找到闲鱼登录 Cookie")
    return False


# ============================================================
# POST /api/auth/login - 启动登录
# ============================================================
@router.post("/login")
def start_login(request: dict = Body(...)) -> JSONResponse:
    """启动登录会话

    Request body:
        {"method": "browser"}  - 浏览器窗口登录
        {"method": "qr"}       - 二维码扫码登录
    """
    global _session

    method = (request.get("method") or "").strip().lower()
    if method not in ("browser", "qr"):
        return JSONResponse(content={
            "ok": False,
            "error": f"不支持的登录方式: {method}，支持 browser / qr",
        })

    with _session_lock:
        # 检查是否有正在进行的会话
        if _session["status"] not in ("idle", "success", "cancelled", "error", "timeout"):
            # 检查子进程是否还活着
            proc = _session.get("proc")
            if proc is not None and proc.poll() is None:
                return JSONResponse(content={
                    "ok": False,
                    "error": f"已有 {_session['method']} 登录在进行中",
                    "current_method": _session["method"],
                    "current_status": _session["status"],
                })
            # 子进程已死，重置
            _reset_session()

        # 启动新会话
        _session["method"] = method
        _session["status"] = "running"
        _session["message"] = "正在启动..."
        _session["started_at"] = time.time()

    if method == "browser":
        return _start_browser_login()
    else:
        return _start_qr_login()


# ============================================================
# 方式一：浏览器窗口登录
# ============================================================
def _start_browser_login() -> JSONResponse:
    """启动 Playwright 有头浏览器子进程"""
    global _session

    if not _BROWSER_LOGIN_SCRIPT.exists():
        _reset_session()
        return JSONResponse(content={
            "ok": False,
            "error": "browser_login.py 脚本缺失",
        })

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
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except Exception as e:
        logger.error("浏览器登录子进程启动失败: %s", e)
        _reset_session()
        return JSONResponse(content={"ok": False, "error": f"无法启动浏览器: {e}"})

    with _session_lock:
        _session["status_file"] = str(status_file)
        _session["proc"] = proc
        _session["pid"] = proc.pid
        _session["status"] = "running"
        _session["message"] = "浏览器窗口已启动，请在窗口中完成登录"

    # 后台线程：等待子进程退出
    threading.Thread(
        target=_background_wait,
        args=(proc, status_file, "browser"),
        daemon=True,
    ).start()

    logger.info("浏览器登录已启动, pid=%d", proc.pid)
    return JSONResponse(content={
        "ok": True,
        "method": "browser",
        "status": "running",
        "message": "浏览器窗口已启动",
    })


# ============================================================
# 方式二：二维码扫码登录
# ============================================================
def _start_qr_login() -> JSONResponse:
    """启动 headless 浏览器，截屏二维码供手机扫码"""
    global _session

    if not _AUTH_HELPER_SCRIPT.exists():
        _reset_session()
        return JSONResponse(content={
            "ok": False,
            "error": "auth_helper.py 脚本缺失",
        })

    out_dir = Path(tempfile.gettempdir()) / "xh_qr_login" / f"qr_{int(time.time() * 1000)}"
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        proc = subprocess.Popen(
            [
                sys.executable, str(_AUTH_HELPER_SCRIPT),
                "qr",
                "--out-dir", str(out_dir),
                "--timeout", "180",
            ],
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        logger.error("二维码登录子进程启动失败: %s", e)
        _reset_session()
        return JSONResponse(content={"ok": False, "error": f"无法启动二维码登录: {e}"})

    with _session_lock:
        _session["status_file"] = str(out_dir / "status.json")
        _session["proc"] = proc
        _session["pid"] = proc.pid
        _session["status"] = "running"
        _session["message"] = "正在生成二维码..."

    # 后台线程：等待子进程退出 + 轮询二维码就绪
    threading.Thread(
        target=_background_wait_qr,
        args=(proc, out_dir),
        daemon=True,
    ).start()

    logger.info("二维码登录已启动, pid=%d, out_dir=%s", proc.pid, out_dir)
    return JSONResponse(content={
        "ok": True,
        "method": "qr",
        "status": "running",
        "message": "正在生成二维码...",
    })


def _background_wait_qr(proc: subprocess.Popen, out_dir: Path) -> None:
    """后台线程：等待二维码就绪 + 子进程退出"""
    global _session

    status_file = out_dir / "status.json"
    qr_png = out_dir / "qr.png"

    # 轮询等待二维码生成（最多等 30 秒）
    qr_ready = False
    for _ in range(60):  # 30s / 0.5s = 60
        if proc.poll() is not None:
            # 子进程已退出（可能启动失败）
            data = _read_status_file(str(status_file))
            with _session_lock:
                _session["status"] = data.get("state", "error")
                _session["message"] = data.get("message", "子进程异常退出")
            return
        if qr_png.exists() and qr_png.stat().st_size > 0:
            qr_ready = True
            break
        time.sleep(0.5)

    if qr_ready:
        # 读取二维码图片为 base64
        try:
            qr_b64 = base64.b64encode(qr_png.read_bytes()).decode("ascii")
        except Exception:
            qr_b64 = None

        with _session_lock:
            _session["status"] = "qr_ready"
            _session["message"] = "请用手机闲鱼 App 扫码登录"
            _session["qr_png_b64"] = qr_b64

        logger.info("二维码已生成，等待用户扫码...")

    # 等待子进程退出（用户扫码成功或超时）
    try:
        proc.wait(timeout=190)  # 180s timeout + 10s buffer
    except subprocess.TimeoutExpired:
        _kill_proc(proc)

    # 读取最终状态
    data = _read_status_file(str(status_file))
    final_state = data.get("state", "error")

    # QR 登录成功后验证 Cookie 是否已导出到 JSON
    if final_state == "success":
        if not _verify_cookies(max_retries=5, delay=1.5):
            logger.warning("QR 登录子进程返回 success，但 Cookie 未在数据库中检测到")
            final_state = "error"
            data["message"] = "登录似乎成功，但 Cookie 未持久化，请重试"

    with _session_lock:
        if final_state == "success":
            _session["status"] = "success"
            _session["message"] = "扫码登录成功"
            _trigger_userinfo_refresh()
        elif final_state == "timeout":
            _session["status"] = "timeout"
            _session["message"] = "扫码超时，请重试"
        elif final_state == "cancelled":
            _session["status"] = "cancelled"
            _session["message"] = "已取消"
        else:
            _session["status"] = "error"
            _session["message"] = data.get("message", "登录失败")

    logger.info("二维码登录结束，状态: %s", _session["status"])


# ============================================================
# 后台等待（浏览器登录子进程）
# ============================================================
def _background_wait(proc: subprocess.Popen, status_file: Path, method: str) -> None:
    """后台线程：等待子进程退出，同步终态"""
    global _session

    try:
        proc.wait(timeout=310)
    except subprocess.TimeoutExpired:
        logger.warning("登录子进程超时，强制终止")
        _kill_proc(proc)

    # 读取子进程输出用于调试
    try:
        stdout, stderr = proc.communicate(timeout=5)
        if stdout:
            logger.debug("登录子进程 stdout: %s", stdout.decode(errors="replace")[:500])
        if stderr:
            for line in stderr.decode(errors="replace").splitlines()[:10]:
                logger.debug("登录子进程 stderr: %s", line[:200])
    except Exception:
        pass

    # 读取状态文件
    data = _read_status_file(str(status_file))
    file_status = data.get("status", "error")

    # 浏览器登录：子进程返回 success 后，验证 Cookie 是否已导出到 JSON
    if file_status == "success" and method == "browser":
        if not _verify_cookies():
            logger.warning("浏览器登录子进程返回 success，但 Cookie 未在数据库中检测到")
            file_status = "error"
            data["message"] = "登录似乎成功，但 Cookie 未持久化，请重试"

    with _session_lock:
        # 如果已经是 success（前端轮询已更新），保持 success
        if _session["status"] == "success":
            return
        _session["status"] = file_status
        _session["message"] = data.get("message", "")

    if file_status == "success":
        _trigger_userinfo_refresh()
        logger.info("浏览器登录成功 (cookie_count=%s)", data.get("cookie_count", "?"))
    else:
        logger.info("浏览器登录结束，状态: %s", file_status)


# ============================================================
# GET /api/auth/login/status - 轮询登录状态
# ============================================================
@router.get("/login/status")
def login_status() -> dict:
    """轮询当前登录会话状态

    返回字段：
    - method: 登录方式
    - status: idle | running | qr_ready | success | cancelled | error | timeout
    - message: 状态描述
    - qr_png_b64: QR 码 base64（仅 qr_ready 状态）
    - elapsed: 已用时间（秒）
    """
    global _session

    with _session_lock:
        # 检查子进程是否还活着（防止僵尸状态）
        proc = _session.get("proc")
        if proc is not None and proc.poll() is not None:
            # 子进程已退出但状态未更新（后台线程可能还没执行）
            status_file = _session.get("status_file")
            if status_file:
                data = _read_status_file(status_file)
                file_status = data.get("status") or data.get("state", "")
                if file_status in ("success", "cancelled", "error", "timeout"):
                    # 如果状态文件显示 success，验证 Cookie 是否已导出到 JSON
                    if file_status == "success" and not _verify_cookies(max_retries=3, delay=0.5):
                        file_status = "error"
                        data["message"] = "登录似乎成功，但 Cookie 未持久化，请重试"
                    _session["status"] = file_status
                    _session["message"] = data.get("message", "")
                    if file_status == "success":
                        _trigger_userinfo_refresh()

        result = {
            "method": _session["method"],
            "status": _session["status"],
            "message": _session["message"],
            "elapsed": round(time.time() - _session["started_at"], 1) if _session["started_at"] else 0,
        }

        if _session["status"] == "qr_ready":
            result["qr_png_b64"] = _session.get("qr_png_b64")

    # 登录成功时设置 xh_token cookie
    if result["status"] == "success":
        return make_auth_response(result)

    return result


# ============================================================
# POST /api/auth/login/cancel - 取消登录
# ============================================================
@router.post("/login/cancel")
def cancel_login() -> dict:
    """取消当前登录会话"""
    global _session

    with _session_lock:
        if _session["status"] not in ("running", "qr_ready"):
            return {"ok": False, "error": "没有正在进行的登录"}

        _kill_proc(_session.get("proc"))
        _session["status"] = "cancelled"
        _session["message"] = "已取消"
        _session["qr_png_b64"] = None

    return {"ok": True, "message": "已取消"}