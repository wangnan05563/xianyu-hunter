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
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
_HELPER = _REPO / "scripts" / "auth_helper.py"
_OUT_DIR = _REPO / "data" / "auth_cache"
# status.json 文件名：_STATUS_FILE 路径、_set_status_file 写入、start_qr_login 清理复用
_STATUS_JSON_FILENAME = "status.json"
_USERINFO_FILE = _OUT_DIR / "userinfo.json"
_STATUS_FILE = _OUT_DIR / _STATUS_JSON_FILENAME


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

    def trigger_refresh_userinfo_async(self) -> None:
        """触发后台刷新（不等完成）"""
        if not _HELPER.exists():
            return
        # 用 fire-and-forget 异步任务；不阻塞
        # get_running_loop 替代 get_event_loop：前者无运行循环时抛 RuntimeError，
        # 正好走 except 分支起线程；后者在 3.12+ 已弃用
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._refresh_userinfo_bg())
        except RuntimeError:
            threading.Thread(target=self._refresh_userinfo_sync, daemon=True).start()

    async def _refresh_userinfo_bg(self) -> None:
        await asyncio.to_thread(self._refresh_userinfo_sync)

    def _refresh_userinfo_sync(self) -> None:
        try:
            proc = subprocess.run(
                [sys.executable, str(_HELPER), "info", "--out-dir", str(_OUT_DIR)],
                timeout=60,
                capture_output=True,
            )
            if proc.returncode == 0 and _USERINFO_FILE.exists():
                with self._lock:
                    self._userinfo = json.loads(_USERINFO_FILE.read_text(encoding="utf-8"))
                    self._userinfo_at = time.time()
        except Exception:
            pass

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
            self._qr_proc = subprocess.Popen(
                [sys.executable, str(_HELPER), "qr", "--out-dir", str(_OUT_DIR), "--timeout", str(timeout)],
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
