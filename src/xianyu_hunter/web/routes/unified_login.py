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

import asyncio
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
_TERMINAL_STATUSES = {"success", "cancelled", "error", "timeout"}
_LIVE_STATUSES = {"pending", "starting", "opening", "waiting", "already_logged", "running"}

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
    "cookies_injected": False,
    "session_token": None,      # MU2: 多用户会话令牌
    "current_user_id": None,    # MU2: 当前登录用户 ID
    "multi_user_finalized": False,  # MU2: 多用户接入是否已完成（幂等标志，防并发竞态）
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
            "cookies_injected": False,
            "session_token": None,      # MU2: 多用户会话令牌
            "current_user_id": None,    # MU2: 当前登录用户 ID
            "multi_user_finalized": False,  # MU2: 重置幂等标志，允许下次登录重新接入
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
    """登录成功后触发用户信息刷新和 Cookie 层状态同步。"""
    try:
        from xianyu_hunter.web.services.auth_manager import get_auth_manager
        get_auth_manager().trigger_refresh_userinfo_async()
    except Exception as e:
        logger.debug("触发用户信息刷新失败: %s", e)

    # 同步 CookieRotator 层状态：登录子进程已写 JSON，但 CookieRotator 层状态
    # 不会自动同步（on_login_success 是死代码），需主动调用以避免 /cookies/layers 显示失效
    try:
        from xianyu_hunter.modules.login_orchestrator import sync_cookie_layers_from_json
        sync_cookie_layers_from_json()
    except Exception as e:
        logger.debug("登录后同步 Cookie 层状态失败: %s", e)


def _cookies_from_store_for_playwright() -> list[dict]:
    """读取 CookieStore 最新 JSON，并转换成 Playwright add_cookies 入参。"""
    try:
        from xianyu_hunter.web.services.cookie_store import is_test_cookie

        store = get_cookie_store()
        store.invalidate_cache("default")
        data = store._read_json("default")
        if not data or not data.get("cookies"):
            return []

        pw_cookies: list[dict] = []
        for c in data["cookies"]:
            name = str(c.get("name") or "")
            value = str(c.get("value") or "")
            if not name or not value:
                continue
            if is_test_cookie(name, value):
                logger.warning("登录后注入：跳过测试 Cookie %s=%s", name, value)
                continue
            item = {
                "name": name,
                "value": value,
                "domain": c.get("domain") or ".goofish.com",
                "path": c.get("path") or "/",
            }
            expires = c.get("expires", -1)
            if expires and expires > 0:
                item["expires"] = expires
            pw_cookies.append(item)
        return pw_cookies
    except Exception as e:
        logger.debug("读取 CookieStore JSON 失败，无法注入 Playwright: %s", e)
        return []


async def _inject_cookies_to_worker_from_store() -> bool:
    """把最新登录 Cookie 注入长期运行的 Worker 浏览器实例。"""
    try:
        from xianyu_hunter.web.deps import get_container

        container = get_container()
        browser = getattr(container, "browser", None)
        if not browser:
            logger.warning("Worker 浏览器实例未初始化，跳过 Cookie 注入")
            return False

        pw_cookies = _cookies_from_store_for_playwright()
        if not pw_cookies:
            logger.warning("CookieStore 中没有可注入的 Cookie")
            return False

        success = await browser.add_cookies(pw_cookies)
        if success:
            logger.info("已注入 %d 个 Cookie 到 Worker 浏览器上下文", len(pw_cookies))
            try:
                from xianyu_hunter.modules.login_orchestrator import sync_cookie_layers_from_json
                sync_cookie_layers_from_json()
            except Exception as e:
                logger.debug("Cookie 注入后同步层状态失败: %s", e)
        else:
            logger.warning("Cookie 注入 Worker 浏览器后关键 Cookie 验证未通过")
        return success
    except Exception as e:
        logger.debug("Cookie 注入 Playwright 上下文失败: %s", e)
        return False


async def _ensure_session_cookies_injected() -> None:
    """让登录状态轮询等待 worker 浏览器真正拿到新 Cookie。"""
    with _session_lock:
        should_inject = (
            _session.get("status") == "success"
            and not _session.get("cookies_injected")
        )
    if not should_inject:
        return

    success = await _inject_cookies_to_worker_from_store()
    if success:
        with _session_lock:
            _session["cookies_injected"] = True


def _trigger_session_start() -> None:
    """登录成功后自动启动会话管理（TokenRenewer 后台续期）"""
    from xianyu_hunter.web.services.session_starter import trigger_session_start
    trigger_session_start()


def _finalize_multi_user_login() -> str | None:
    """登录成功后完成多用户接入：识别用户 + 签发会话 + 按用户存储 Cookie

    登录子进程把 Cookie 写入 default 文件后，本函数读取 default 文件，
    通过 Cookie 识别用户身份，签发 session_token，并将 Cookie 迁移到
    user_id 维度的独立文件，避免多用户共用 default 串号。

    幂等保护：本函数可能被 _background_wait 后台线程和 login_status 前端轮询
    并发调用，用 multi_user_finalized 标志保证只执行一次，避免重复签发
    session_token 导致前一个 token 失效（issue_session 会撤销旧 session）。

    Returns:
        session_token 或 None（失败时降级为单用户模式，不阻塞登录主流程）
    """
    # 幂等保护：已完成的直接返回已有 token，避免并发重复签发
    with _session_lock:
        if _session.get("multi_user_finalized"):
            return _session.get("session_token")
        _session["multi_user_finalized"] = True

    try:
        from xianyu_hunter.web.services.user_manager import get_user_manager
        from xianyu_hunter.web.services.cookie_store import _cookie_json_path

        store = get_cookie_store()
        store.invalidate_cache("default")
        # 登录子进程写入 default 文件，这里读取它做用户识别
        data = store._read_json("default")
        if not data or not data.get("cookies"):
            logger.warning("多用户接入失败：default 文件无 Cookie 数据")
            return None

        cookies = data["cookies"]
        mgr = get_user_manager()
        user_id = mgr.identify_or_create(cookies)
        session_token = mgr.issue_session(user_id)

        # 将 Cookie 从 default 迁移到 user_id 维度的独立文件
        store.export_cookies(cookies, method="login", user_id=user_id)

        # 迁移完成后清理 default 文件，避免多用户串号
        # 为什么必须清理：若不清理，default 文件仍保留真实用户 Cookie，
        # has_valid_cookies("default") 仍返回 True，下次登录子进程会覆写
        # default 文件，但本次用户的 Cookie 仍残留在 default 中造成串号
        default_path = _cookie_json_path("default")
        try:
            default_path.unlink(missing_ok=True)
        except OSError as e:
            logger.warning("清理 default Cookie 文件失败: %s", e)
        store.invalidate_cache("default")

        with _session_lock:
            _session["session_token"] = session_token
            _session["current_user_id"] = user_id

        logger.info("多用户登录完成: user_id=%s", user_id)
        return session_token
    except Exception as e:
        # 降级为单用户模式：登录主流程已成功，不应因多用户接入失败而回滚
        logger.error("多用户接入异常，降级为单用户模式: %s", e)
        return None



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
        store.invalidate_cache("default")
        if store.has_valid_cookies(user_id="default"):
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
        _session["cookies_injected"] = False

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
            # Playwright GUI 子进程必须用 CREATE_NEW_CONSOLE，CREATE_NO_WINDOW 会导致窗口不稳定/闪退
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0,
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
        _session["message"] = "正在启动浏览器窗口..."

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
        "message": "正在启动浏览器窗口...",
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
        elif final_state == "timeout":
            _session["status"] = "timeout"
            _session["message"] = "扫码超时，请重试"
        elif final_state == "cancelled":
            _session["status"] = "cancelled"
            _session["message"] = "已取消"
        else:
            _session["status"] = "error"
            _session["message"] = data.get("message", "登录失败")

    # hooks 在锁外调用，避免与 _finalize_multi_user_login 内部的锁获取死锁
    if final_state == "success":
        _trigger_userinfo_refresh()
        _trigger_session_start()
        # MU2: 多用户接入（识别用户 + 签发 session + 按 user_id 存储 Cookie）
        _finalize_multi_user_login()

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
    # 子进程已同步写入 JSON，减少重试次数避免阻塞（10s→1.5s）
    if file_status == "success" and method == "browser":
        if not _verify_cookies(max_retries=3, delay=0.5):
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
        _trigger_session_start()
        # MU2: 多用户接入（识别用户 + 签发 session + 按 user_id 存储 Cookie）
        _finalize_multi_user_login()
        logger.info("浏览器登录成功 (cookie_count=%s)", data.get("cookie_count", "?"))
    else:
        logger.info("浏览器登录结束，状态: %s", file_status)


# ============================================================
# GET /api/auth/login/status - 轮询登录状态
# ============================================================
@router.get("/login/status")
async def login_status() -> dict:
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
        proc = _session.get("proc")
        status_file = _session.get("status_file")
        started_at = _session.get("started_at") or 0
        session_status = _session["status"]
        already_success = session_status == "success"
        result = {
            "method": _session["method"],
            "status": session_status,
            "message": _session["message"],
            "elapsed": round(time.time() - started_at, 1) if started_at else 0,
        }

        if session_status == "qr_ready":
            result["qr_png_b64"] = _session.get("qr_png_b64")

    data = _read_status_file(status_file)
    file_status = data.get("status") or data.get("state") or ""
    should_start_hooks = False

    if file_status in _TERMINAL_STATUSES:
        normalized_status = file_status
        # 子进程已保证 Cookie 写入，快速确认即可（1.5s→0.6s）
        if normalized_status == "success" and not _verify_cookies(max_retries=2, delay=0.3):
            normalized_status = "error"
            data["message"] = "登录似乎成功，但 Cookie 未持久化，请重试"

        with _session_lock:
            _session["status"] = normalized_status
            _session["message"] = data.get("message", "")
            result.update({
                "status": normalized_status,
                "message": _session["message"],
                "elapsed": round(time.time() - (_session.get("started_at") or 0), 1)
                if _session.get("started_at") else 0,
            })
            should_start_hooks = normalized_status == "success" and not already_success
    elif file_status in _LIVE_STATUSES and result["status"] not in _TERMINAL_STATUSES:
        # 子进程运行中也会持续写 status_file。实时透传这些阶段，便于定位
        # launch / goto / 等待用户登录分别耗时多少。
        result["status"] = "running"
        result["phase"] = file_status
        result["message"] = data.get("message") or result["message"]

    if data:
        if data.get("elapsed") is not None:
            result["child_elapsed"] = data.get("elapsed")
        if data.get("wait_elapsed") is not None:
            result["wait_elapsed"] = data.get("wait_elapsed")
        if data.get("timings") is not None:
            result["timings"] = data.get("timings")

    if should_start_hooks:
        _trigger_userinfo_refresh()
        _trigger_session_start()
        # MU2: 前端轮询首次发现 success 时也尝试多用户接入
        # （兜底：_background_wait 线程可能因竞态未触发）
        # 用 asyncio.to_thread 包装避免阻塞事件循环：
        # _finalize_multi_user_login 内部有文件 I/O 和 DB I/O
        await asyncio.to_thread(_finalize_multi_user_login)

    if result["status"] == "success":
        await _ensure_session_cookies_injected()

    # 登录成功时设置 xh_token cookie
    if result["status"] == "success":
        # MU2: 优先使用 session_token，无则回退到 web_token（向后兼容单用户模式）
        session_token = _session.get("session_token")
        return make_auth_response(result, session_token=session_token)

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
