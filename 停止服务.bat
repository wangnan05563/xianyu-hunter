@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
setlocal enabledelayedexpansion

echo ========================================
echo   Stopping XianyuHunter...
echo ========================================

REM [1/3] Stop Web server via PID file, fallback to port scan
echo [1/3] Stopping Web server...

set WEB_KILLED=0

if exist "logs\web.pid" (
    for /f "tokens=*" %%a in (logs\web.pid) do (
        taskkill /F /T /PID %%a >nul 2>&1
        if not errorlevel 1 (
            echo   [OK] Web server stopped (PID %%a)
            set WEB_KILLED=1
        )
    )
    del "logs\web.pid" >nul 2>&1
)

REM Fallback: kill any process listening on port 8000
if "!WEB_KILLED!"=="0" (
    for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000.*LISTENING"') do (
        taskkill /F /T /PID %%a >nul 2>&1
        if not errorlevel 1 (
            echo   [OK] Web server stopped (PID %%a, found by port scan)
            set WEB_KILLED=1
        )
    )
)

if "!WEB_KILLED!"=="0" (
    echo   [SKIP] No Web server process found on port 8000.
)

REM [2/3] Release browser resources (WebView2 + Edge child processes)
echo [2/3] Cleaning up browser processes...

taskkill /F /IM msedgewebview2.exe >nul 2>&1
taskkill /F /IM msedge.exe >nul 2>&1
taskkill /F /IM chromium.exe >nul 2>&1
taskkill /F /IM chrome.exe >nul 2>&1

timeout /t 1 >nul 2>&1

REM [3/3] Verify shutdown â€?port released and no xianyu_hunter process remaining
echo [3/3] Verifying shutdown...

set PORT_FREE=1
netstat -aon | findstr ":8000.*LISTENING" >nul 2>&1
if not errorlevel 1 (
    set PORT_FREE=0
    echo   [WARN] Port 8000 is still in use!
)

if "!PORT_FREE!"=="1" (
    echo   [OK] All services stopped successfully.
) else (
    echo   [WARN] Some processes may still be running. Check task manager.
)

echo.
echo ========================================
echo   Services Stopped.
echo ========================================
echo.
timeout /t 2 >nul 2>&1
