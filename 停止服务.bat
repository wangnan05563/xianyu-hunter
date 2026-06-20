@echo off
chcp 65001 >nul
cd /d "%~dp0"
setlocal enabledelayedexpansion

echo ========================================
echo   Stopping XianyuHunter...
echo ========================================

REM ============================================================
REM [1/4] 停止 Run 调度器进程 — 优先通过 PID 文件，回退到进程扫描
REM ============================================================
echo [1/4] Stopping Run scheduler...

set RUN_KILLED=0

if exist "logs\run.pid" (
    for /f "tokens=*" %%a in (logs\run.pid) do (
        taskkill /F /T /PID %%a >nul 2>&1
        if not errorlevel 1 (
            echo   [OK] Run scheduler stopped (PID %%a)
            set RUN_KILLED=1
        )
    )
    del "logs\run.pid" >nul 2>&1
)

REM PID 文件不存在时，通过命令行匹配查找残留 Run 进程（usebackq 避免 PowerShell 单引号与 bat 冲突）
if "!RUN_KILLED!"=="0" (
    for /f "usebackq tokens=*" %%a in (`powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*xianyu_hunter*run*' -and $_.CommandLine -notlike '*web*' -and $_.CommandLine -notlike '*stop*' } | Select-Object -ExpandProperty ProcessId"`) do (
        taskkill /F /T /PID %%a >nul 2>&1
        if not errorlevel 1 (
            echo   [OK] Run scheduler stopped (PID %%a, found by scan)
            set RUN_KILLED=1
        )
    )
)

if "!RUN_KILLED!"=="0" (
    echo   [SKIP] No Run scheduler process found.
)

REM ============================================================
REM [2/4] 停止 Web 服务进程 — 优先通过 PID 文件，回退到端口扫描
REM ============================================================
echo [2/4] Stopping Web server...

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

REM PID 文件不存在时，通过端口扫描查找残留 Web 进程
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

REM ============================================================
REM [3/4] 释放浏览器资源 — WebView2 + Edge 子进程
REM ============================================================
echo [3/4] Cleaning up browser processes...

taskkill /F /IM msedgewebview2.exe >nul 2>&1
taskkill /F /IM msedge.exe >nul 2>&1
taskkill /F /IM chromium.exe >nul 2>&1
taskkill /F /IM chrome.exe >nul 2>&1

timeout /t 1 >nul 2>&1

REM ============================================================
REM [4/4] 确认停止状态 — 验证端口已释放、进程已退出
REM ============================================================
echo [4/4] Verifying shutdown...

set PORT_FREE=1
netstat -aon | findstr ":8000.*LISTENING" >nul 2>&1
if not errorlevel 1 (
    set PORT_FREE=0
    echo   [WARN] Port 8000 is still in use!
)

set RUN_GONE=1
for /f "usebackq tokens=*" %%a in (`powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*xianyu_hunter*' } | Select-Object -ExpandProperty ProcessId"`) do (
    set RUN_GONE=0
    echo   [WARN] Process %%a is still running.
)

if "!PORT_FREE!"=="1" if "!RUN_GONE!"=="1" (
    echo   [OK] All services stopped successfully.
)

echo.
echo ========================================
echo   Services Stopped.
echo ========================================
echo.
timeout /t 2 >nul 2>&1
