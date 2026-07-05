"""PyInstaller 打包入口

设计要点：
1. 设置运行时环境变量（PLAYWRIGHT_BROWSERS_PATH、SENTENCE_TRANSFORMERS_HOME）
2. 单实例锁（通过 kernel32.CreateMutexW，不依赖 pywin32 完整版）
3. 端口清理（复用 scripts/启动服务.bat 逻辑，但用 Python 实现以便 PyInstaller 收集）
4. 启动 uvicorn + 自动开浏览器

与 scripts/启动服务.bat 的关系：
- 启动器复用 bat 的端口清理、健康轮询、自动开浏览器逻辑
- 替换 .venv\Scripts\python.exe 调用为 PyInstaller 收集的解释器
- 打包后 bat 不再需要（开发者模式仍保留）
"""
from __future__ import annotations

import ctypes
import os
import re
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from ctypes import wintypes
from pathlib import Path

# ERROR_ALREADY_EXISTS：Windows 系统常量，CreateMutex 已存在时返回
_ERROR_ALREADY_EXISTS = 183


def _is_frozen() -> bool:
    """PyInstaller 打包后 sys.frozen = True"""
    return getattr(sys, "frozen", False)


def _setup_env() -> None:
    """设置运行时环境变量

    仅在打包模式下设置：开发模式下走 .venv 与系统 Playwright 安装
    """
    if not _is_frozen():
        return
    # 通过 paths.py 推算程序安装目录
    sys.path.insert(0, str(Path(sys.executable).resolve().parent / "_internal"))
    from xianyu_hunter.paths import get_app_dir
    app_dir = get_app_dir()
    # Playwright 浏览器路径：随安装包分发
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(app_dir / "playwright_browsers")
    # sentence-transformers 模型路径：预置到 models/，避免首次运行联网下载
    os.environ["SENTENCE_TRANSFORMERS_HOME"] = str(app_dir / "models")
    # 启用调度器：Web + 浏览器 + 任务引擎同进程
    os.environ["XH_WITH_SCHEDULER"] = "1"


def _acquire_single_instance() -> bool:
    """单实例锁：通过 kernel32.CreateMutexW 防止多开

    用 ctypes 直接调用 Windows API，避免依赖 pywin32 完整版
    （项目仅安装 pywin32-ctypes，不含 win32event 模块）

    返回 True 表示获取锁成功（首次启动），False 表示已有实例运行
    """
    kernel32 = ctypes.windll.kernel32
    # CreateMutexW(lpMutexAttributes, bInitialOwner, lpName)
    # 返回句柄；GetLastError() == 183 表示已存在同名 Mutex
    kernel32.CreateMutexW(None, False, "XianyuHunter-Mutex")
    return kernel32.GetLastError() != _ERROR_ALREADY_EXISTS


def _cleanup_port(port: int = 8000) -> None:
    """端口清理：杀掉占用目标端口的进程

    netstat 输出形如：TCP    127.0.0.1:8000      0.0.0.0:0    LISTENING    1234
    需同时匹配端口号与 LISTENING 状态，避免误杀其他端口的进程
    """
    try:
        result = subprocess.run(
            ["netstat", "-aon"], capture_output=True, text=True, timeout=5
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return
    # 正则匹配：:PORT 任意空白 远程地址 任意空白 LISTENING 任意空白 PID
    pattern = re.compile(rf":{port}\s+\S+\s+\S+\s+LISTENING\s+(\d+)")
    killed: set[str] = set()
    for line in result.stdout.splitlines():
        m = pattern.search(line)
        if m:
            pid = m.group(1)
            if pid in killed or pid == str(os.getpid()):
                continue
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", pid],
                    capture_output=True, timeout=5
                )
                killed.add(pid)
            except subprocess.SubprocessError:
                pass


def _wait_for_port(host: str, port: int, timeout: int = 30) -> bool:
    """轮询等待端口就绪

    每秒尝试 TCP 连接，成功立即返回 True；超时返回 False
    """
    for _ in range(timeout * 2):
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def _print_banner(host: str, port: int) -> None:
    """打印启动横幅（控制台模式）"""
    print("=" * 40)
    print("  XianyuHunter Starting...")
    print("=" * 40)
    print(f"  Web:  http://{host}:{port}")
    print(f"  Mode: Web + Scheduler (with browser)")
    print(f"  Press Ctrl+C to stop")
    print("=" * 40)


def main() -> int:
    """启动器主入口"""
    host = "127.0.0.1"
    port = 8000

    _setup_env()

    if not _acquire_single_instance():
        print("已在运行，请勿重复启动")
        return 1

    _print_banner(host, port)

    # 端口清理：杀掉残留的旧实例
    print("[1/3] Cleaning up old processes...")
    _cleanup_port(port)

    # 启动 uvicorn（子线程运行，主线程等待端口就绪后开浏览器）
    # 主线程不能直接 server.run()，否则无法执行 webbrowser.open
    print("[2/3] Starting Web server...")
    import uvicorn
    from xianyu_hunter.web.app import app
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # 等待端口就绪
    print("[3/3] Waiting for Web server...")
    if _wait_for_port(host, port, timeout=30):
        print(f"  Web server started on port {port}.")
        webbrowser.open(f"http://{host}:{port}/app/")
    else:
        print(f"[ERROR] Web server failed to start within 30 seconds!")
        return 1

    # 阻塞主线程：uvicorn 在子线程运行，主线程 join 等待
    # Ctrl+C 时 daemon 线程自动退出
    try:
        thread.join()
    except KeyboardInterrupt:
        print("\n收到退出信号，正在停止...")
        server.should_exit = True
        thread.join(timeout=5)
    return 0


if __name__ == "__main__":
    sys.exit(main())
