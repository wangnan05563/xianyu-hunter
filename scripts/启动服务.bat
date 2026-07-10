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

REM 杀掉占用 8001 端口的进程（PID 文件缺失时的兜底方案）
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8001.*LISTENING"') do (
    taskkill /F /T /PID %%a >nul 2>&1
)

taskkill /F /IM msedgewebview2.exe >nul 2>&1
taskkill /F /IM msedge.exe >nul 2>&1

REM 等待端口释放（最多 5 秒），避免旧进程刚被杀但端口尚未释放导致绑定失败
set /a portWait=0
:wait_port_release
netstat -aon | findstr ":8001.*LISTENING" >nul 2>&1
if not errorlevel 1 (
    set /a portWait+=1
    if !portWait! lss 5 (
        timeout /t 1 >nul 2>&1
        goto wait_port_release
    )
    echo [WARN] 端口 8001 仍被占用，可能启动失败
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

REM 验证 Python 环境能否加载核心模块
.venv\Scripts\python.exe -c "import xianyu_hunter; import uvicorn; import fastapi" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 依赖缺失！
    echo 请执行: .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

REM [3/4] 启动 Web 服务（默认启用调度器：实时搜索 + 批量采集 + 数据库归集同步）
REM 用 xianyu web 命令默认带 --with-scheduler，无需额外参数
REM 纯 Web 模式（不启动调度器）请使用: -m xianyu_hunter web --no-with-scheduler
echo [3/4] 正在启动 Web 服务（默认启用调度器）...

REM 清空旧日志，避免新旧日志混淆导致误判
if exist "logs\web.log" del "logs\web.log" >nul 2>&1
if exist "logs\web.err" del "logs\web.err" >nul 2>&1

REM 启动 Web 服务并重定向输出到日志文件（便于失败时排查）
start "XianyuHunter-Web" cmd /c ".venv\Scripts\python.exe -m xianyu_hunter web --port 8001 > logs\web.log 2>&1"

REM 等待 Web 端口就绪（最多 30 秒）
echo 正在等待 Web 服务就绪...
set /a tries=0
:wait_web
set /a tries+=1
ping -n 2 127.0.0.1 >nul 2>&1
netstat -aon | findstr ":8001.*LISTENING" >nul 2>&1
if errorlevel 1 (
    if !tries! lss 15 goto wait_web
    echo [ERROR] Web 服务在 30 秒内未启动成功！
    echo.
    echo ====== 日志最后 30 行 ======
    if exist "logs\web.log" (
        powershell -NoProfile -Command "Get-Content 'logs\web.log' -Tail 30 -Encoding UTF8"
    ) else (
        echo 日志文件未生成，可能进程启动即崩溃
    )
    echo ==============================
    echo 完整日志请查看: logs\web.log
    pause
    exit /b 1
)

REM 通过端口扫描记录 Web PID
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8001.*LISTENING"') do (
    echo %%a> "logs\web.pid"
)
echo   Web 服务已监听 8001 端口

REM [4/4] 验证进程存活
echo [4/4] 正在验证服务...

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
    echo   [FAIL] Web 服务进程未在运行！
    echo   请查看 logs\web.log 了解详情
    pause
    exit /b 1
)

echo.
echo ========================================
echo   闲鱼猎人服务已启动
echo ========================================
echo   Web:  http://127.0.0.1:8001
echo   模式: Web + 调度器（实时采集）
echo   日志: logs\web.log
echo.
echo 停止服务请双击 scripts\停止服务.bat
echo.

start "" http://127.0.0.1:8001/app/
timeout /t 3 >nul 2>&1
exit
