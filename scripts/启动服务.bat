@echo off
chcp 936 >nul 2>&1
REM 脚本位于 scripts/ 子目录，需回到项目根目录
cd /d "%~dp0.."
setlocal enabledelayedexpansion

echo ========================================
echo   XianyuHunter Starting...
echo ========================================

REM [1/4] Clean up old processes via PID file + port scan
echo [1/4] Cleaning up old processes...

if exist "logs\web.pid" (
    for /f "tokens=*" %%a in (logs\web.pid) do (
        taskkill /F /T /PID %%a >nul 2>&1
    )
    del "logs\web.pid" >nul 2>&1
)

REM Kill any process listening on port 8000 (fallback when PID file is missing)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000.*LISTENING"') do (
    taskkill /F /T /PID %%a >nul 2>&1
)

taskkill /F /IM msedgewebview2.exe >nul 2>&1
taskkill /F /IM msedge.exe >nul 2>&1
timeout /t 1 >nul 2>&1

REM [2/4] Check dependencies
echo [2/4] Checking dependencies...

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] .venv not found!
    echo Run: python -m venv .venv
    echo Then: .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

if not exist "logs" mkdir logs

REM Verify Python environment can import core modules
.venv\Scripts\python.exe -c "import xianyu_hunter; import uvicorn; import fastapi" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python dependencies missing!
    echo Run: .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

REM [3/4] Start Web server (默认调度器模式：浏览器 + 任务引擎 + 批量采集同进程)
REM 自 xianyu web 命令默认启用 --with-scheduler，无需显式传参
REM 若需纯 Web 模式（不启动浏览器），改用: -m xianyu_hunter web --no-with-scheduler
echo [3/4] Starting Web server (default: with scheduler)...

start "XianyuHunter-Web" cmd /c ".venv\Scripts\python.exe -m xianyu_hunter web 2>&1 & pause"

REM Wait for Web port to be ready (up to 30 seconds)
echo Waiting for Web server...
set /a tries=0
:wait_web
set /a tries+=1
ping -n 2 127.0.0.1 >nul 2>&1
netstat -aon | findstr ":8000.*LISTENING" >nul 2>&1
if errorlevel 1 (
    if !tries! lss 15 goto wait_web
    echo [ERROR] Web server failed to start within 30 seconds!
    echo Check logs\web.log and logs\web.err for details.
    pause
    exit /b 1
)

REM Record Web PID via port scan
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000.*LISTENING"') do (
    echo %%a> "logs\web.pid"
)
echo   Web server started on port 8000.

REM [4/4] Verify process is alive
echo [4/4] Verifying service...

set WEB_ALIVE=0

if exist "logs\web.pid" (
    for /f "tokens=*" %%a in (logs\web.pid) do (
        tasklist /FI "PID eq %%a" 2>nul | findstr "%%a" >nul 2>&1
        if not errorlevel 1 (
            set WEB_ALIVE=1
            echo   [OK] Web server PID %%a
        )
    )
)

if "!WEB_ALIVE!"=="0" (
    echo   [FAIL] Web server process not running!
    echo   Check logs\web.log for details.
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Service Started!
echo ========================================
echo   Web:  http://127.0.0.1:8000
echo   Mode: Web + Scheduler (with browser)
echo   Log:  logs\web.log
echo.
echo To stop: double-click scripts\停止服务.bat
echo.

start "" http://127.0.0.1:8000/app/
timeout /t 3 >nul 2>&1
exit
