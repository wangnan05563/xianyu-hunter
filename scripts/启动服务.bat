@echo off
chcp 936 >nul 2>&1
REM 脚本位于 scripts/ 目录，先回到项目根目录
cd /d "%~dp0.."
setlocal enabledelayedexpansion

echo ========================================
echo   闲鱼猎人服务启动中...
echo ========================================

REM [1/4] 通过 PID 文件 + 端口扫描清理旧进程
echo [1/4] 正在清理旧进程...

if exist "logs\web.pid" (
    for /f "tokens=*" %%a in (logs\web.pid) do (
        taskkill /F /T /PID %%a >nul 2>&1
    )
    del "logs\web.pid" >nul 2>&1
)

REM 杀掉占用 8001 端口的进程（PID 文件缺失时的兜底策略）
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8001.*LISTENING"') do (
    taskkill /F /T /PID %%a >nul 2>&1
)

taskkill /F /IM msedgewebview2.exe >nul 2>&1
taskkill /F /IM msedge.exe >nul 2>&1

REM 等待端口释放（最多 5 秒），旧进程刚被杀时端口可能未释放
set /a portWait=0
:wait_port_release
netstat -aon | findstr ":8001.*LISTENING" >nul 2>&1
if not errorlevel 1 (
    set /a portWait+=1
    if !portWait! lss 5 (
        timeout /t 1 >nul 2>&1
        goto wait_port_release
    )
    echo [WARN] 端口 8001 仍被占用，继续启动可能失败
)

timeout /t 1 >nul 2>&1

REM [2/4] 检查依赖
echo [2/4] 正在检查依赖...

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] 未找到 .venv 虚拟环境！
    echo 请执行: python -m venv .venv
    echo 然后执行: .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

if not exist "logs" mkdir logs

REM 验证 Python 能否加载核心模块
.venv\Scripts\python.exe -c "import xianyu_hunter; import uvicorn; import fastapi" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 依赖缺失！
    echo 请执行: .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

REM [3/4] 启动 Web 服务（默认启用调度器：实时采集 + 批量采集 + 数据库脏数据同步）
REM 命令 xianyu web 会默认带 --with-scheduler（默认）
REM 纯 Web 模式（不启动调度器）请使用: -m xianyu_hunter web --no-with-scheduler
echo [3/4] 正在启动 Web 服务（默认启用调度器）...

REM 设置 Python 输出编码为 UTF-8，避免子窗口中文乱码
REM PYTHONIOENCODING=utf-8 强制 stdout/stderr 使用 UTF-8
REM PYTHONUTF8=1 启用 Python 3.7+ UTF-8 模式（覆盖系统默认编码）
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

REM 启动 Web 服务（子窗口实时显示日志，& pause 保持窗口在崩溃时不关闭）
REM Python 的 loguru 已自动写文件日志到 data/logs/ 和 run.stdout.log
REM 无需 cmd 重定向，子窗口即可看到完整的 uvicorn + loguru 输出
start "XianyuHunter-Web" cmd /c ".venv\Scripts\python.exe -m xianyu_hunter web --port 8001 & pause"

REM 等待 Web 端口就绪（最多 120 秒）
REM timeout /t 2 精确等待 2 秒，60 次循环 = 120 秒超时
REM 120 秒超时是为了容纳调度器+数据库+向量库的初始化时间
echo 正在等待 Web 服务就绪...
set /a tries=0
:wait_web
set /a tries+=1
timeout /t 2 /nobreak >nul 2>&1
netstat -aon | findstr ":8001.*LISTENING" >nul 2>&1
if errorlevel 1 (
    if !tries! lss 60 (
        echo   等待中... !tries!/60
        goto wait_web
    )
    echo [ERROR] Web 服务在 120 秒内未启动成功！
    echo.
    echo 请查看弹出的 "XianyuHunter-Web" 子窗口中的错误信息
    echo.
    echo Python 日志文件位置:
    echo   - data\logs\xianyu_*.log （结构化日志）
    echo   - run.stdout.log （纯文本日志）
    echo.
    pause
    exit /b 1
)

REM 通过端口扫描记录 Web PID
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8001.*LISTENING"') do (
    echo %%a> "logs\web.pid"
)
echo   Web 服务已监听 8001 端口

REM [4/4] 验证进程存活
echo [4/4] 正在验证进程存活...

set WEB_ALIVE=0

if exist "logs\web.pid" (
    for /f "tokens=*" %%a in (logs\web.pid) do (
        tasklist /FI "PID eq %%a" 2>nul | findstr "%%a" >nul 2>&1
        if not errorlevel 1 (
            set WEB_ALIVE=1
            echo   [OK] Web 服务 PID %%a
        )
    )
)

if "!WEB_ALIVE!"=="0" (
    echo   [FAIL] Web 服务进程未存活！
    echo   请查看弹出的 "XianyuHunter-Web" 子窗口中的错误信息
    pause
    exit /b 1
)

echo.
echo ========================================
echo   闲鱼猎人服务已启动
echo ========================================
echo   Web:  http://127.0.0.1:8001
echo   模式: Web + 调度器（实时采集）
echo   日志: 子窗口实时显示 + data\logs\ 文件
echo.
echo 停止服务请双击 scripts\停止服务.bat
echo.

start "" http://127.0.0.1:8001/app/
timeout /t 3 >nul 2>&1
exit
