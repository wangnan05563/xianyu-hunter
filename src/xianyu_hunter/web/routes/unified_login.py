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
# 打包后 __file__ 在 _internal/ 下，parents[4] 会指错位置；统一走 paths.get_app_dir()
# 开发模式返回项目根 CWD，打包模式返回 exe 同级目录（安装时复制 scripts/ 子进程脚本）
from xianyu_hunter.paths import get_app_dir

logger = logging.getLogger(__name__)

_REPO = get_app_dir()
_BROWSER_LOGIN_SCRIPT = _REPO / "scripts" / "browser_login.py"
_AUTH_HELPER_SCRIPT = _REPO / "scripts" / "auth_helper.py"
_TERMINAL_STATUSES = {"success", "cancelled", "error", "timeout"}
_LIVE_STATUSES = {"pending", "starting", "opening", "waiting", "already_logged", "running"}
_STARTUP_STATUSES = {"pending", "starting", "opening", "already_logged", "running"}
_STARTUP_HEARTBEAT_TIMEOUT_SEC = 90.0
_WAITING_HEARTBEAT_TIMEOUT_SEC = 30.0
# Cookie 未持久化提示文案：登录子进程返回 success 但 JSON 未检测到 Cookie 时复用
_COOKIE_NOT_PERSISTED_MSG = "登录似乎成功，但 Cookie 未持久化，请重试"
_PACKAGED_SCRIPT_FLAG = "--xh-run-script"
_PYTHON_EXE = "python.exe"
_PYTHONW_EXE = "pythonw.exe"

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


def _reset_session_locked() -> None:
    """重置登录会话到 idle 状态（调用方必须已持有 _session_lock）

    为什么需要这个无锁版本：start_login 在 with _session_lock 块内检测到子进程
    已死亡时需要重置 session，若调用 _reset_session() 会再次获取 _session_lock，
    而 threading.Lock 不可重入，会导致请求永久阻塞（用户表现为"按钮无响应"）。
    """
    global _session
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


def _reset_session() -> None:
    """重置登录会话到 idle 状态（调用方未持有 _session_lock 时使用）"""
    with _session_lock:
        _reset_session_locked()


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


def _get_quiet_python_executable() -> tuple[str, int]:
    """获取无控制台窗口的 Python 解释器路径及对应的 creationflags

    为什么需要 pythonw.exe：
    - Windows 下 python.exe 是控制台子系统程序，subprocess 启动时会弹出黑色控制台窗口
    - pythonw.exe 是 GUI 子系统程序，无控制台，启动时不弹窗
    - CREATE_NEW_CONSOLE 对 GUI 子系统程序无效（不会创建控制台），因此 pythonw.exe 不会弹窗
    - Playwright 浏览器子进程由 Playwright 库自身启动，不继承 Python 进程的 creationflags，
      因此 pythonw.exe 不会触发硬约束中"CREATE_NO_WINDOW 导致 Playwright 闪退"的问题

    Returns:
        (python_executable, creationflags)
        - Windows + pythonw.exe 可用：(pythonw_path, 0)  完全静默
        - Windows + pythonw.exe 不可用：(python_path, CREATE_NEW_CONSOLE)  fallback 弹窗但保证稳定
        - macOS/Linux：(sys.executable, 0)  无控制台问题
    """
    if os.name != "nt":
        # macOS/Linux：Python 进程不弹控制台窗口，无需特殊处理
        return sys.executable, 0

    if getattr(sys, "frozen", False):
        # PyInstaller 打包后 sys.executable 是 xianyu-hunter.exe，不是 Python 解释器。
        # 子进程脚本由 launcher.py 的内部分发入口执行，不能再寻找 pythonw.exe。
        return sys.executable, 0

    # Windows：优先使用 pythonw.exe
    exe = sys.executable
    pythonw_candidates: list[str] = []

    if exe.lower().endswith(_PYTHON_EXE):
        # 同目录下的 pythonw.exe（标准 Python 安装布局）
        pythonw_candidates.append(exe[:-len(_PYTHON_EXE)] + _PYTHONW_EXE)
    elif exe.lower().endswith(_PYTHONW_EXE):
        # 已经是 pythonw.exe
        return exe, 0

    # venv 场景：venv 目录下可能没有 pythonw.exe，回退到基础解释器
    # 检查 venv pyvenv.cfg 指向的基础 Python
    exe_dir = os.path.dirname(exe)
    pythonw_candidates.append(os.path.join(exe_dir, _PYTHONW_EXE))

    # 检查 venv 的 base_executable
    base_exe = getattr(sys, "_base_executable", None)
    if base_exe and base_exe.lower().endswith(_PYTHON_EXE):
        pythonw_candidates.append(base_exe[:-len(_PYTHON_EXE)] + _PYTHONW_EXE)

    for candidate in pythonw_candidates:
        if os.path.exists(candidate):
            logger.debug("使用无窗口 Python 解释器: %s", candidate)
            return candidate, 0

    # fallback：pythonw.exe 不可用，保留 CREATE_NEW_CONSOLE 防止 Playwright 闪退
    # （硬约束：CREATE_NO_WINDOW 会导致 Playwright GUI 子进程不稳定）
    logger.warning("pythonw.exe 不可用，回退到 python.exe + CREATE_NEW_CONSOLE（会弹出控制台窗口）")
    return exe, subprocess.CREATE_NEW_CONSOLE


def _build_script_subprocess_command(python_exe: str, script_path: Path, *args: str) -> list[str]:
    """Build the command used to run helper scripts in dev and packaged modes."""
    if getattr(sys, "frozen", False):
        return [python_exe, _PACKAGED_SCRIPT_FLAG, script_path.stem, *args]
    return [python_exe, str(script_path), *args]


def _trigger_userinfo_refresh() -> None:
    """登录成功后触发用户信息刷新和 Cookie 层状态同步。

    delay=5.0：延迟 5 秒触发 auth_helper。
    为什么：登录成功时 browser_login.py 的 Chromium 进程尚未完全退出
    （bc.close() 后 Edge 还需 2-5 秒清理），立即启动 auth_helper 会与
    browser_login 的 Chromium 争用同一 user_data_dir，导致 SQLite Cookie
    锁冲突、Cookie 丢失、auth_helper 读不到 unb。
    """
    try:
        from xianyu_hunter.web.services.auth_manager import get_auth_manager
        get_auth_manager().trigger_refresh_userinfo_async(delay=5.0)
    except Exception as e:
        logger.debug("触发用户信息刷新失败: %s", e)

    # 同步 CookieRotator 层状态：登录子进程已写 JSON，但 CookieRotator 层状态
    # 不会自动同步（on_login_success 是死代码），需主动调用以避免 /cookies/layers 显示失效
    try:
        from xianyu_hunter.modules.login_orchestrator import sync_cookie_layers_from_json
        sync_cookie_layers_from_json()
    except Exception as e:
        logger.debug("登录后同步 Cookie 层状态失败: %s", e)


def _convert_cookie_to_playwright(c: dict, is_test_cookie_fn) -> dict | None:
    """转换单条 cookie 为 Playwright add_cookies 入参，跳过无效或测试 cookie

    返回 None 表示该 cookie 应跳过。独立为模块级函数以降低
    _cookies_from_store_for_playwright 的认知复杂度（S3776）。
    """
    name = str(c.get("name") or "")
    value = str(c.get("value") or "")
    if not name or not value:
        return None
    if is_test_cookie_fn(name, value):
        logger.warning("登录后注入：跳过测试 Cookie %s=%s", name, value)
        return None
    item = {
        "name": name,
        "value": value,
        "domain": c.get("domain") or ".goofish.com",
        "path": c.get("path") or "/",
    }
    expires = c.get("expires", -1)
    if expires and expires > 0:
        item["expires"] = expires
    return item


def _cookies_from_store_for_playwright() -> list[dict]:
    """读取 CookieStore 最新 JSON，并转换成 Playwright add_cookies 入参。"""
    try:
        from xianyu_hunter.web.services.cookie_store import is_test_cookie

        store = get_cookie_store()
        with _session_lock:
            user_id = _session.get("current_user_id") or "default"
        store.invalidate_cache(user_id)
        data = store._read_json(user_id)
        if not data or not data.get("cookies"):
            return []

        pw_cookies: list[dict] = []
        for c in data["cookies"]:
            item = _convert_cookie_to_playwright(c, is_test_cookie)
            if item is not None:
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
        # 健康探测：注入成功后检查身份 cookie 完整性，
        # 提前发现"登录成功但 cookie 不完整/服务端未建立会话"问题
        await _post_login_cookie_health_check()


async def _post_login_cookie_health_check() -> None:
    """登录后 cookie 健康探测：验证身份 cookie 完整性

    为什么需要：登录子进程写 JSON + 主进程注入浏览器后，仍可能因
    cookie 不完整/服务端会话未建立导致采集立即失败。探测身份 cookie
    的存在性，可在登录后立即告警，而非等到 BatchRefresh 连续失败 3 次。

    设计取舍：只做静态检查（cookie 存在性+过期时间），不主动打开页面
    访问详情页，避免增加登录流程延迟。服务端会话有效性由后续采集时
    的 _refresh_token_and_retry_detail 两级自愈兜底。
    """
    try:
        from xianyu_hunter.web.deps import get_container

        container = get_container()
        browser = getattr(container, "browser", None)
        if not browser:
            return

        cookies = await browser.get_cookies()
        cookie_names = {c.get("name", "") for c in cookies}
        # 身份 cookie：闲鱼登录态的核心标识
        identity_cookies = ("cookie2", "sgcookie", "unb")
        missing = [name for name in identity_cookies if name not in cookie_names]

        if missing:
            logger.warning(
                "登录后健康探测失败：身份 cookie 缺失 %s（共 %d 个 cookie），"
                "采集可能立即失败，建议检查登录子进程 cookie 导出是否完整",
                missing,
                len(cookies),
            )
        else:
            logger.info("登录后健康探测通过：身份 cookie 齐全（共 %d 个 cookie）", len(cookies))
    except Exception as e:  # noqa: BLE001
        logger.debug("登录后健康探测异常（不影响登录流程）: %s", e)


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


def _heartbeat_timeout_for_status(file_status: str) -> float:
    """按子进程阶段返回心跳超时时间。"""
    if file_status in _STARTUP_STATUSES:
        return _STARTUP_HEARTBEAT_TIMEOUT_SEC
    return _WAITING_HEARTBEAT_TIMEOUT_SEC


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
            # 子进程已死，重置（必须用 _reset_session_locked 避免重入锁死锁）
            _reset_session_locked()

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
        # 使用 pythonw.exe 静默启动（无控制台窗口），提升用户体验
        # pythonw.exe 是 GUI 子系统程序，不会弹出 python.exe 黑窗
        # Playwright 浏览器子进程由 Playwright 库自身启动，不受此设置影响
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
            # - pythonw.exe 可用时为 0（完全静默）
            # - fallback 到 python.exe 时为 CREATE_NEW_CONSOLE（防 Playwright 闪退，但会弹窗）
            creationflags=creation_flags,
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
        cmd = _build_script_subprocess_command(
            sys.executable,
            _AUTH_HELPER_SCRIPT,
            "qr",
            "--out-dir", str(out_dir),
            "--timeout", "180",
        )
        proc = subprocess.Popen(
            cmd,
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


def _wait_for_qr_ready(proc: subprocess.Popen, status_file: Path, qr_png: Path) -> tuple[bool, dict | None]:
    """轮询等待二维码生成或子进程退出

    返回 (qr_ready, exit_data)：
    - qr_ready=True：二维码已生成，可继续扫码流程
    - qr_ready=False, exit_data=非空：子进程已退出，调用方需用 exit_data 更新 session 后直接返回
    - qr_ready=False, exit_data=None：轮询超时（30s 内既无二维码也未退出），继续等待子进程
    """
    for _ in range(60):  # 30s / 0.5s = 60
        if proc.poll() is not None:
            # 子进程已退出（可能启动失败）
            return False, _read_status_file(str(status_file))
        if qr_png.exists() and qr_png.stat().st_size > 0:
            return True, None
        time.sleep(0.5)
    return False, None


def _qr_final_session_state(final_state: str, data: dict) -> tuple[str, str]:
    """将 QR 登录终态映射为 (session_status, message)，未知状态归一为 error"""
    if final_state == "success":
        return "success", "扫码登录成功"
    if final_state == "timeout":
        return "timeout", "扫码超时，请重试"
    if final_state == "cancelled":
        return "cancelled", "已取消"
    return "error", data.get("message", "登录失败")


def _background_wait_qr(proc: subprocess.Popen, out_dir: Path) -> None:
    """后台线程：等待二维码就绪 + 子进程退出"""
    global _session

    status_file = out_dir / "status.json"
    qr_png = out_dir / "qr.png"

    # 轮询等待二维码生成（最多等 30 秒）；提取为辅助函数避免嵌套 if 拉高认知复杂度（S3776）
    qr_ready, exit_data = _wait_for_qr_ready(proc, status_file, qr_png)
    if exit_data is not None:
        # 子进程已退出（可能启动失败）
        with _session_lock:
            _session["status"] = exit_data.get("state", "error")
            _session["message"] = exit_data.get("message", "子进程异常退出")
        return

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
            data["message"] = _COOKIE_NOT_PERSISTED_MSG

    # 状态映射提取为辅助函数，避免多重 elif 拉高复杂度
    session_status, session_message = _qr_final_session_state(final_state, data)
    with _session_lock:
        _session["status"] = session_status
        _session["message"] = session_message

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

    # 必须使用 communicate() 而非 wait()：
    # wait() 不读取 PIPE 缓冲区，当子进程输出满 64KB 后会被阻塞卡死，
    # 导致 _session["status"] 永远停留在 "running"，后续启动请求被拒绝。
    # communicate() 会持续读取输出，避免缓冲区死锁。
    try:
        stdout, stderr = proc.communicate(timeout=310)
    except subprocess.TimeoutExpired:
        logger.warning("登录子进程超时，强制终止")
        _kill_proc(proc)
        # 超时后再次调用 communicate 以获取已产生的输出并回收子进程
        try:
            stdout, stderr = proc.communicate(timeout=5)
        except Exception:
            stdout, stderr = b'', b''
    except Exception:
        stdout, stderr = b'', b''

    # 读取子进程输出用于调试
    if stdout:
        logger.debug("登录子进程 stdout: %s", stdout.decode(errors="replace")[:500])
    if stderr:
        for line in stderr.decode(errors="replace").splitlines()[:10]:
            logger.debug("登录子进程 stderr: %s", line[:200])

    # 读取状态文件
    data = _read_status_file(str(status_file))
    file_status = data.get("status", "error")

    # 浏览器登录：子进程返回 success 后，验证 Cookie 是否已导出到 JSON
    # 子进程已同步写入 JSON，减少重试次数避免阻塞（10s→1.5s）
    if file_status == "success" and method == "browser":
        if not _verify_cookies(max_retries=3, delay=0.5):
            logger.warning("浏览器登录子进程返回 success，但 Cookie 未在数据库中检测到")
            file_status = "error"
            data["message"] = _COOKIE_NOT_PERSISTED_MSG

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
def _handle_heartbeat_timeout(data: dict, status_file, file_status: str) -> str:
    """检测心跳超时并清理卡死的子进程，返回更新后的 file_status

    为什么需要：browser_login.py 子进程的 bc.cookies() 在浏览器无响应时
    可能永久阻塞，导致心跳停止、status_file 停在最后一次写入的 message，
    前端秒数一直不变化。此处主动识别并清理，让前端停止轮询。
    启动阶段给更长宽限：打包 exe 冷启动、导入 Playwright、拉起 Edge 可能超过 15s。
    等待登录阶段仍保留较短阈值，及时识别浏览器 IPC 卡死。

    独立为模块级函数：原为 login_status 内多层嵌套 if + try/except，拉高了
    认知复杂度（S3776）；提取后 login_status 主流程变为线性调用。
    """
    if file_status not in _LIVE_STATUSES:
        return file_status
    ts = data.get("ts")
    if ts is None:
        return file_status
    stale_sec = time.time() - float(ts)
    timeout_sec = _heartbeat_timeout_for_status(file_status)
    if stale_sec <= timeout_sec:
        return file_status

    logger.warning("登录子进程心跳超时（%.1fs 未更新），判定为卡死", stale_sec)
    with _session_lock:
        proc = _session.get("proc")
        if proc and proc.poll() is None:
            try:
                proc.kill()
            except OSError:
                pass
        _session["status"] = "error"
        _session["message"] = f"登录进程无响应（{stale_sec:.0f}s 未更新），请重试"
    data["status"] = "error"
    data["message"] = _session["message"]
    # 写回 status_file 让 _background_wait 线程也能读到终态，
    # 否则它会读到旧的 "waiting" 把 _session["status"] 覆盖回去
    if status_file:
        try:
            Path(status_file).write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass
    return "error"


def _apply_terminal_status_to_session(
    data: dict, file_status: str, already_success: bool, result: dict,
) -> bool:
    """处理终态：验证 Cookie + 更新 session + 更新 result，返回 should_start_hooks"""
    normalized_status = file_status
    # 子进程已保证 Cookie 写入，快速确认即可（1.5s→0.6s）
    if normalized_status == "success" and not _verify_cookies(max_retries=2, delay=0.3):
        normalized_status = "error"
        data["message"] = _COOKIE_NOT_PERSISTED_MSG

    with _session_lock:
        _session["status"] = normalized_status
        _session["message"] = data.get("message", "")
        result.update({
            "status": normalized_status,
            "message": _session["message"],
            "elapsed": round(time.time() - (_session.get("started_at") or 0), 1)
            if _session.get("started_at") else 0,
        })
        return normalized_status == "success" and not already_success


def _merge_child_timings(data: dict, result: dict) -> None:
    """合并子进程的 elapsed/wait_elapsed/timings 字段到 result"""
    if not data:
        return
    if data.get("elapsed") is not None:
        result["child_elapsed"] = data.get("elapsed")
    if data.get("wait_elapsed") is not None:
        result["wait_elapsed"] = data.get("wait_elapsed")
    if data.get("timings") is not None:
        result["timings"] = data.get("timings")


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

    # 心跳超时检测提取为辅助函数，避免多层嵌套 if 拉高认知复杂度
    file_status = _handle_heartbeat_timeout(data, status_file, file_status)

    if file_status in _TERMINAL_STATUSES:
        should_start_hooks = _apply_terminal_status_to_session(
            data, file_status, already_success, result,
        )
    elif file_status in _LIVE_STATUSES and result["status"] not in _TERMINAL_STATUSES:
        # 子进程运行中也会持续写 status_file。实时透传这些阶段，便于定位
        # launch / goto / 等待用户登录分别耗时多少。
        result["status"] = "running"
        result["phase"] = file_status
        result["message"] = data.get("message") or result["message"]

    _merge_child_timings(data, result)

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
