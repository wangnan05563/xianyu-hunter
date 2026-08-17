"""认证信息管理 - web 后端用

职责：
- 缓存 /api/auth/me 的结果（userinfo + 状态）
- 后台异步启动 auth_helper 拉取/刷新
- 管理扫码登录子进程的生命周期

设计原则：
- 不阻塞 web 请求：第一次请求触发后台拉取，5 分钟内复用
- subprocess 隔离：auth_helper 跑在独立进程，崩溃不影响 web
- 状态可观察：status 文件 + AuthState 数据类
"""
from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# 走 paths.py 统一入口：PyInstaller 打包后基于 exe 目录，开发模式基于 __file__ 推算
# _REPO 仅用于定位 scripts/auth_helper.py（仅开发模式存在，打包后该脚本由 launcher 替代）
from xianyu_hunter.paths import get_app_dir, get_data_dir
_REPO = get_app_dir()
_HELPER = _REPO / "scripts" / "auth_helper.py"
# 打包模式子进程脚本分发标志：与 launcher.py 的 _SCRIPT_DISPATCH_FLAG 保持一致
# 为什么需要：打包后 sys.executable 是 xianyu-hunter.exe，不能直接传脚本路径，
# 必须通过 --xh-run-script 标志告诉 launcher 运行内部脚本。
# 与 unified_login.py 的 _build_script_subprocess_command 逻辑一致。
_PACKAGED_SCRIPT_FLAG = "--xh-run-script"
_OUT_DIR = get_data_dir() / "auth_cache"
# status.json 文件名：_STATUS_FILE 路径、_set_status_file 写入、start_qr_login 清理复用
_STATUS_JSON_FILENAME = "status.json"
_USERINFO_FILE = _OUT_DIR / "userinfo.json"
_STATUS_FILE = _OUT_DIR / _STATUS_JSON_FILENAME


def _build_script_command(script_path: Path, *args: str) -> list[str]:
    """构建子进程脚本命令：开发模式直接传脚本路径，打包模式通过 --xh-run-script 分发

    为什么需要此函数：与 unified_login.py 的 _build_script_subprocess_command 逻辑一致。
    打包后 sys.executable 指向 xianyu-hunter.exe，不能直接传脚本路径作为参数，
    launcher.py 的 _dispatch_helper_script 要求 argv[1] 必须是 --xh-run-script。
    """
    if getattr(sys, "frozen", False):
        return [sys.executable, _PACKAGED_SCRIPT_FLAG, script_path.stem, *args]
    return [sys.executable, str(script_path), *args]


@dataclass
class AuthState:
    """扫码登录状态机：idle → starting → opening → qr_ready → success / timeout / error / cancelled"""
    state: str = "idle"
    message: str = ""
    ts: float = 0.0
    qr_png_b64: str | None = None
    userinfo: dict | None = None
    started_at: float = 0.0
    pid: int | None = None


class AuthManager:
    """单例认证状态管理器"""

    # userinfo 缓存 TTL：5 分钟
    USERINFO_TTL = 300.0
    # 扫码流程整体超时
    QR_TIMEOUT = 200.0

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._userinfo: dict | None = None
        self._userinfo_at: float = 0.0
        self._qr_state = AuthState()
        self._qr_proc: subprocess.Popen | None = None
        self._qr_monitor_task: asyncio.Task | None = None
        # auth_helper 进程互斥锁：防止多个 auth_helper 并发执行
        # 为什么需要：_maybe_refresh_userinfo 的条件3（nick 无效）会在登录后
        # 立即触发第二次 auth_helper，与第一次（delay=5s 后启动）并发执行，
        # 两个 Chromium 争用同一 user_data_dir → SingletonLock 冲突 → 卡死
        self._refresh_lock = threading.Lock()
        self._refreshing = False
        self._ensure_out_dir()

    @staticmethod
    def _ensure_out_dir() -> None:
        _OUT_DIR.mkdir(parents=True, exist_ok=True)

    # ---------- userinfo ----------
    def get_userinfo(self) -> dict:
        """返回缓存的 userinfo；不存在或过期则尝试快速读文件 + 后台刷新"""
        with self._lock:
            if self._userinfo and (time.time() - self._userinfo_at) < self.USERINFO_TTL:
                return self._userinfo
            # 文件里可能有上次的值
            if _USERINFO_FILE.exists():
                try:
                    self._userinfo = json.loads(_USERINFO_FILE.read_text(encoding="utf-8"))
                    self._userinfo_at = time.time()
                    return self._userinfo
                except Exception:
                    pass
            return {"logged_in": False, "user_id": "", "nick": "", "avatar_url": "", "fetched_at": 0}

    def trigger_refresh_userinfo_async(self, delay: float = 0.0) -> None:
        """触发后台刷新（不等完成）

        delay 参数：延迟秒数后执行。
        为什么需要延迟：登录成功后 browser_login.py 的 Chromium 进程需要 2-5 秒
        才完全退出（bc.close() 后 Edge 进程异步清理）。如果立即启动 auth_helper，
        两个 Chromium 会争用同一 user_data_dir，导致：
        1. SQLite Cookie 数据库锁冲突 → Cookie 写入丢失（38→18 个）
        2. Chromium 启动变慢（等待锁释放）
        3. auth_helper 读 Cookie 不完整 → 读不到 unb → user_id 降级为 sha256(cookie2)
        4. auth_helper 的 Chromium 虽然 headless=True，启动瞬间可能闪现窗口
        登录路径调用时传 delay=5.0，让 browser_login 的 Chromium 先退出。
        """
        if not _HELPER.exists():
            return
        # 用 fire-and-forget 异步任务；不阻塞
        # get_running_loop 替代 get_event_loop：前者无运行循环时抛 RuntimeError，
        # 正好走 except 分支起线程；后者在 3.12+ 已弃用
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._refresh_userinfo_bg(delay))
        except RuntimeError:
            threading.Thread(
                target=self._refresh_userinfo_sync_with_delay,
                args=(delay,),
                daemon=True,
            ).start()

    async def _refresh_userinfo_bg(self, delay: float = 0.0) -> None:
        if delay > 0:
            await asyncio.sleep(delay)
        # 复用 _refresh_userinfo_sync_with_delay 的互斥逻辑
        # 为什么不直接调 _refresh_userinfo_sync：async 路径也需要互斥，
        # 防止 /me 触发的 async 任务与登录触发的 thread 任务并发执行
        await asyncio.to_thread(self._refresh_userinfo_sync_with_delay, 0.0)

    def _refresh_userinfo_sync_with_delay(self, delay: float = 0.0) -> None:
        """线程入口：延迟后调用 _refresh_userinfo_sync

        为什么单独抽出：threading.Thread 的 target 不能是 async 函数，
        需要同步包装。delay=0 时直接调用，不引入额外开销。
        """
        if delay > 0:
            time.sleep(delay)
        # 互斥检查：如果已有 auth_helper 在运行，跳过本次触发
        # 为什么不阻塞等待：auth_helper 运行时间 30-60s，等待会堆积线程；
        # 跳过更安全，因为下一次 /me 请求会再次触发
        with self._refresh_lock:
            if self._refreshing:
                logger.debug("auth_helper 已在运行，跳过本次触发")
                return
            self._refreshing = True
        try:
            self._refresh_userinfo_sync()
        finally:
            with self._refresh_lock:
                self._refreshing = False

    def _refresh_userinfo_sync(self) -> None:
        try:
            cmd = _build_script_command(_HELPER, "info", "--out-dir", str(_OUT_DIR))
            proc = subprocess.run(
                cmd,
                timeout=60,
                capture_output=True,
            )
            if proc.returncode == 0 and _USERINFO_FILE.exists():
                with self._lock:
                    self._userinfo = json.loads(_USERINFO_FILE.read_text(encoding="utf-8"))
                    self._userinfo_at = time.time()
            elif proc.returncode != 0:
                # 记录失败原因：之前静默吞掉异常，导致 auth_helper 启动失败时
                # _userinfo 保持旧值（nick=""），前端一直显示"未登录"且无日志可查
                stderr = proc.stderr.decode(errors="replace")[:500] if proc.stderr else ""
                logger.warning(
                    "auth_helper info 失败 (returncode=%d): %s",
                    proc.returncode, stderr,
                )
        except subprocess.TimeoutExpired:
            logger.warning("auth_helper info 超时（60s）")
        except Exception as e:
            logger.warning("auth_helper info 异常: %s", e)

    def _qr_state_dict(self) -> dict:
        """把内部 _qr_state 序列化为对外字典"""
        s = self._qr_state
        return {
            "state": s.state,
            "message": s.message,
            "ts": s.ts,
            "pid": s.pid,
            "elapsed": round(time.time() - s.started_at, 1) if s.started_at else 0,
        }

    # ---------- 扫码登录 ----------
    def start_qr_login(self, timeout: int = 180) -> dict:
        """启动扫码流程（headless 浏览器 + 截屏）。如果已经在跑，返回当前状态"""
        with self._lock:
            if self._qr_state.state in ("starting", "opening", "qr_ready"):
                return self._qr_state_dict()
            if not _HELPER.exists():
                return {"error": "auth_helper.py 缺失"}
            # 清理旧状态
            for f in ("userinfo.json", _STATUS_JSON_FILENAME, "qr.png", "qr_full.png"):
                p = _OUT_DIR / f
                if p.exists():
                    p.unlink()
            self._qr_state = AuthState(state="starting", message="启动浏览器…", started_at=time.time())
            self._ensure_status_file_writable()
        # 启动子进程（不阻塞）
        self._launch_qr_subprocess(timeout)
        return self._qr_state_dict()

    def _ensure_status_file_writable(self) -> None:
        # 把 status.json 立即写入一份"启动中"，让前端首次轮询有数据
        _set_status_file(_OUT_DIR, state="starting", message="启动浏览器…", ts=time.time())

    def _launch_qr_subprocess(self, timeout: int) -> None:
        try:
            cmd = _build_script_command(
                _HELPER, "qr", "--out-dir", str(_OUT_DIR), "--timeout", str(timeout),
            )
            self._qr_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                # Windows 下 CREATE_NEW_PROCESS_GROUP 便于 cancel
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
            )
            with self._lock:
                self._qr_state.pid = self._qr_proc.pid
        except Exception as e:
            _set_status_file(_OUT_DIR, state="error", message=f"启动失败: {e}", ts=time.time())

    def poll_qr_status(self) -> dict:
        """前端轮询入口：返回当前状态（带二维码 base64）"""
        with self._lock:
            # 读 status.json
            st: dict = {}
            if _STATUS_FILE.exists():
                try:
                    st = json.loads(_STATUS_FILE.read_text(encoding="utf-8"))
                except Exception:
                    st = {}
            # 子进程退出同步：检测 qr 流程是否结束
            if self._qr_proc is not None:
                ret = self._qr_proc.poll()
                if ret is not None and st.get("state") not in ("success", "timeout", "error", "cancelled"):
                    # 子进程结束但 status 未终结（异常退出）
                    st = {"state": "error", "message": f"进程退出码 {ret}", "ts": time.time()}
                    _set_status_file(_OUT_DIR, **st)
            # 状态映射
            state = st.get("state", self._qr_state.state)
            message = st.get("message", self._qr_state.message)
            # qr_ready 时附带 base64
            qr_b64: str | None = None
            if state == "qr_ready":
                qr_png = _OUT_DIR / "qr.png"
                if qr_png.exists():
                    import base64
                    qr_b64 = base64.b64encode(qr_png.read_bytes()).decode("ascii")
            # 成功后回填 userinfo
            userinfo = None
            if state == "success" and _USERINFO_FILE.exists():
                try:
                    userinfo = json.loads(_USERINFO_FILE.read_text(encoding="utf-8"))
                    # 刷新主缓存
                    self._userinfo = userinfo
                    self._userinfo_at = time.time()
                except Exception:
                    pass
            return {
                "state": state,
                "message": message,
                "ts": st.get("ts", self._qr_state.ts),
                "qr_png_b64": qr_b64,
                "userinfo": userinfo,
                "elapsed": round(time.time() - self._qr_state.started_at, 1) if self._qr_state.started_at else 0,
            }

    def cancel_qr_login(self) -> dict:
        with self._lock:
            if self._qr_proc is not None and self._qr_proc.poll() is None:
                try:
                    self._qr_proc.terminate()
                except Exception:
                    try:
                        self._qr_proc.kill()
                    except Exception:
                        pass
                self._qr_proc = None
            _set_status_file(_OUT_DIR, state="cancelled", message="已取消", ts=time.time())
            self._qr_state = AuthState()
            return {"ok": True}

    # ---------- 退出登录 ----------
    def reset(self) -> None:
        """重置 userinfo 缓存为未登录状态（供 /api/auth/logout 调用）

        为什么需要此方法：避免外部模块直接访问 _userinfo / _userinfo_at 私有属性，
        破坏封装性。同时清理 userinfo.json 持久化文件，防止下次启动读到旧数据。
        """
        with self._lock:
            self._userinfo = {"logged_in": False, "user_id": "", "nick": "", "avatar_url": "", "fetched_at": 0}
            self._userinfo_at = time.time()
        # 清理持久化文件，避免下次启动读到旧的已登录状态
        try:
            if _USERINFO_FILE.exists():
                _USERINFO_FILE.unlink()
        except OSError:
            pass


def _set_status_file(out_dir: Path, **kw) -> None:
    s = {}
    p = out_dir / _STATUS_JSON_FILENAME
    if p.exists():
        try:
            s = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            s = {}
    s.update(kw)
    p.write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")


# 全局单例
_manager: AuthManager | None = None
_manager_lock = threading.Lock()


def get_auth_manager() -> AuthManager:
    global _manager
    with _manager_lock:
        if _manager is None:
            _manager = AuthManager()
        return _manager
