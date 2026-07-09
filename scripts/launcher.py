r"""PyInstaller 打包入口

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
import runpy
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
_SCRIPT_DISPATCH_FLAG = "--xh-run-script"
_SCRIPT_DISPATCH: dict[str, str] = {
    "browser_login": "browser_login.py",
    "auth_helper": "auth_helper.py",
}


def _is_frozen() -> bool:
    """PyInstaller 打包后 sys.frozen = True"""
    return getattr(sys, "frozen", False)


def _setup_env() -> None:
    """设置运行时环境变量

    仅在打包模式下设置：开发模式下走 .venv 与系统 Playwright 安装
    """
    if not _is_frozen():
        return
    # 打包模式：chdir 到用户数据目录，让所有相对路径（data/xxx、.env、config/xxx）正确定位
    # 为什么 chdir 而不是改每处路径：最小改动，不影响开发模式和 1394 个测试
    # 为什么不 chdir 到 exe 所在目录：exe 目录可能只读，且用户数据应在 %APPDATA%
    # 为什么在 sys.path.insert 之前：确保后续 import xianyu_hunter 时 config.py 的
    #   env_file=".env" 能在 CWD=%APPDATA%/XianyuHunter/ 找到文件
    _appdata = Path(os.environ.get("APPDATA", "")) / "XianyuHunter"
    _appdata.mkdir(parents=True, exist_ok=True)
    os.chdir(str(_appdata))

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


def _dispatch_helper_script() -> int | None:
    """Run packaged helper scripts inside this PyInstaller executable.

    In frozen mode there is no bundled python.exe/pythonw.exe next to the app.
    The web process starts helper scripts by relaunching xianyu-hunter.exe with
    this private flag; this branch must run before the single-instance mutex.
    """
    if len(sys.argv) < 2 or sys.argv[1] != _SCRIPT_DISPATCH_FLAG:
        return None

    _setup_env()
    if len(sys.argv) < 3:
        print("Missing helper script name")
        return 2

    script_key = sys.argv[2]
    script_name = _SCRIPT_DISPATCH.get(script_key)
    if not script_name:
        print(f"Unknown helper script: {script_key}")
        return 2

    script_path = Path(sys.executable).resolve().parent / "scripts" / script_name
    if not script_path.exists():
        print(f"Helper script missing: {script_path}")
        return 2

    sys.argv = [str(script_path), *sys.argv[3:]]
    try:
        runpy.run_path(str(script_path), run_name="__main__")
    except SystemExit as exc:
        if exc.code is None:
            return 0
        if isinstance(exc.code, int):
            return exc.code
        print(exc.code)
        return 1
    return 0


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


def _cleanup_port(port: int = 8001) -> None:
    """端口清理：杀掉占用目标端口的进程

    netstat 输出形如：TCP    127.0.0.1:8001      0.0.0.0:0    LISTENING    1234
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


def _try_start_tray(host: str, port: int, on_quit) -> threading.Thread | None:
    """可选启动系统托盘（pystray 未安装时返回 None）

    为什么是可选依赖：项目核心是 Web 应用，控制台 + Ctrl+C 已满足基本需求。
    pystray + pillow 仅在需要托盘图标时才安装，避免增加打包体积和复杂度。

    启用方式：build-exe.ps1 中 `pip install pystray pillow` 后重打包。
    """
    try:
        import pystray
        from PIL import Image, ImageDraw
    except ImportError:
        return None

    # 生成简单图标（不依赖外部图片文件）
    # 32x32 圆形，米其林红 + 金色三星
    img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((2, 2, 30, 30), fill=(226, 6, 19, 255))  # 米其林红
    # 简化的三星（白色小圆点代替）
    for x, y in [(16, 9), (10, 20), (22, 20)]:
        draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill=(201, 169, 97, 255))

    def on_open(icon, item):
        webbrowser.open(f"http://{host}:{port}/app/")

    def on_quit_item(icon, item):
        icon.stop()
        on_quit()

    menu = pystray.Menu(
        pystray.MenuItem("打开浏览器", on_open, default=True),
        pystray.MenuItem("退出", on_quit_item),
    )
    icon = pystray.Icon("XianyuHunter", img, "闲鱼猎人", menu)
    thread = threading.Thread(target=icon.run, daemon=True)
    thread.start()
    return thread


def _print_banner(host: str, port: int) -> None:
    """打印启动横幅（控制台模式）

    强制 stdout 使用 UTF-8 编码，避免 Windows 控制台 OEM 编码（如 GBK/CP936）下中文乱码。
    为什么需要：打包后 PyInstaller 的 stdout 默认走系统编码（中文 Windows 通常是 GBK），
    写入 UTF-8 字节会被 GBK 错误解析，banner 中文显示为问号或乱码。
    """
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    print("=" * 40)
    print("  闲鱼猎人 启动中...")
    print("=" * 40)
    print(f"  Web:  http://{host}:{port}/app/")
    print(f"  Mode: Web + 调度器（含浏览器）")
    print(f"  提示: 按 Ctrl+C 停止")
    print("=" * 40)


def main() -> int:
    """启动器主入口"""
    dispatched = _dispatch_helper_script()
    if dispatched is not None:
        return dispatched

    host = "127.0.0.1"
    port = 8001

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
        # 为什么需要 try/except + fallback：PyInstaller 打包后 webbrowser.open() 依赖
        # os.startfile() -> ShellExecuteW 调起系统默认浏览器，在以下场景会静默失败：
        # 1) 默认浏览器未在 Windows 注册表中设置
        # 2) Windows Server / 无 GUI 环境下没有关联浏览器
        # 3) PyInstaller 打包的 webbrowser 模块未能正确读取注册表
        # fallback 1：os.startfile 走 ShellExecuteW
        # fallback 2：cmd /c start 走 cmd.exe 解析，能在更多边缘场景成功
        url = f"http://{host}:{port}/app/"
        opened = False
        try:
            opened = webbrowser.open(url)
        except Exception as e:
            print(f"  [WARN] webbrowser.open 失败: {e}")
        if not opened:
            try:
                os.startfile(url)  # type: ignore[attr-defined]
                opened = True
                print("  使用 os.startfile 成功打开浏览器")
            except Exception as e:
                print(f"  [WARN] os.startfile 失败: {e}")
        if not opened:
            try:
                # CREATE_NO_WINDOW 避免弹黑色控制台
                subprocess.Popen(
                    ["cmd", "/c", "start", "", url],
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08001000),
                )
                opened = True
                print("  使用 cmd /c start 成功打开浏览器")
            except Exception as e:
                print(f"  [WARN] cmd /c start 失败: {e}")
        if not opened:
            print(f"  [ERROR] 未能自动打开浏览器，请手动访问 {url}")
    else:
        print(f"[ERROR] Web server failed to start within 30 seconds!")
        return 1

    # 可选启动系统托盘（pystray 未安装时返回 None，控制台模式继续）
    # 托盘提供"打开浏览器"和"退出"菜单，用户可通过托盘退出而无需 Ctrl+C
    def _on_tray_quit():
        server.should_exit = True

    tray_thread = _try_start_tray(host, port, _on_tray_quit)
    if tray_thread is not None:
        print("  System tray enabled (pystray).")

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
