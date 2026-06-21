@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
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

REM [3/4] Start Web server with scheduler (browser + task engine in same process)
REM 实时搜索 API 需�?container.collector 不为 None，只�?--with-scheduler 模式才满�?echo [3/4] Starting Web server with scheduler...

start "XianyuHunter-Web" /min cmd /c ".venv\Scripts\python.exe -m xianyu_hunter web --with-scheduler > logs\web.log 2> logs\web.err"

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
echo To stop: double-click 停止服务.bat
echo.

start "" http://127.0.0.1:8000/app/
timeout /t 3 >nul 2>&1
exit
