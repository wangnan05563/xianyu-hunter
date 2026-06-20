@echo off
chcp 65001 >nul
cd /d "%~dp0"
setlocal enabledelayedexpansion

echo ========================================
echo   XianyuHunter Starting...
echo ========================================

REM ============================================================
REM [1/5] 清理旧进程 — 通过 PID 文件 + 端口扫描双重定位
REM ============================================================
echo [1/5] Cleaning up old processes...

if exist "logs\run.pid" (
    for /f "tokens=*" %%a in (logs\run.pid) do (
        taskkill /F /T /PID %%a >nul 2>&1
    )
    del "logs\run.pid" >nul 2>&1
)

if exist "logs\web.pid" (
    for /f "tokens=*" %%a in (logs\web.pid) do (
        taskkill /F /T /PID %%a >nul 2>&1
    )
    del "logs\web.pid" >nul 2>&1
)

REM 通过端口扫描清理残留 Web 进程（防止 PID 文件丢失时端口仍被占用）
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000.*LISTENING"') do (
    taskkill /F /T /PID %%a >nul 2>&1
)

REM 通过命令行匹配清理残留 Run 进程（usebackq 避免 PowerShell 单引号与 bat 冲突）
for /f "usebackq tokens=*" %%a in (`powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*xianyu_hunter*run*' -and $_.CommandLine -notlike '*web*' } | Select-Object -ExpandProperty ProcessId"`) do (
    taskkill /F /T /PID %%a >nul 2>&1
)

taskkill /F /IM msedgewebview2.exe >nul 2>&1
taskkill /F /IM msedge.exe >nul 2>&1
timeout /t 1 >nul 2>&1

REM ============================================================
REM [2/5] 依赖检查 — venv + Python 模块可用性
REM ============================================================
echo [2/5] Checking dependencies...

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] .venv not found!
    echo Run: python -m venv .venv
    echo Then: .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

if not exist "logs" mkdir logs

REM 验证 Python 环境可正常导入核心模块
.venv\Scripts\python.exe -c "import xianyu_hunter; import uvicorn; import fastapi" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python dependencies missing!
    echo Run: .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

REM ============================================================
REM [3/5] 启动 Web 进程 — FastAPI 控制台（不含调度器）
REM ============================================================
echo [3/5] Starting Web server...

powershell -NoProfile -Command "$p = Start-Process -FilePath '.venv\Scripts\python.exe' -ArgumentList '-m','xianyu_hunter','web' -WorkingDirectory '%CD%' -RedirectStandardOutput 'logs\web.log' -RedirectStandardError 'logs\web.err' -WindowStyle Minimized -PassThru; $p.Id | Out-File -FilePath 'logs\web.pid' -Encoding ascii -NoNewline"

REM 等待 Web 端口就绪（最多 30 秒）
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
echo   Web server started on port 8000.

REM ============================================================
REM [4/5] 启动 Run 进程 — 独立调度器（含浏览器 + 抢单引擎）
REM ============================================================
echo [4/5] Starting Run scheduler...

powershell -NoProfile -Command "$p = Start-Process -FilePath '.venv\Scripts\python.exe' -ArgumentList '-m','xianyu_hunter','run' -WorkingDirectory '%CD%' -RedirectStandardOutput 'logs\run.log' -RedirectStandardError 'logs\run.err' -WindowStyle Minimized -PassThru; $p.Id | Out-File -FilePath 'logs\run.pid' -Encoding ascii -NoNewline"

REM 等待 Run 进程初始化
ping -n 4 127.0.0.1 >nul 2>&1

REM ============================================================
REM [5/5] 验证启动结果 — 确认两个进程均存活
REM ============================================================
echo [5/5] Verifying services...

set WEB_ALIVE=0
set RUN_ALIVE=0

if exist "logs\web.pid" (
    for /f "tokens=*" %%a in (logs\web.pid) do (
        tasklist /FI "PID eq %%a" 2>nul | findstr "%%a" >nul 2>&1
        if not errorlevel 1 (
            set WEB_ALIVE=1
            echo   [OK] Web server  PID %%a
        )
    )
)

if exist "logs\run.pid" (
    for /f "tokens=*" %%a in (logs\run.pid) do (
        tasklist /FI "PID eq %%a" 2>nul | findstr "%%a" >nul 2>&1
        if not errorlevel 1 (
            set RUN_ALIVE=1
            echo   [OK] Run scheduler PID %%a
        )
    )
)

if "!WEB_ALIVE!"=="0" (
    echo   [FAIL] Web server process not running!
    echo   Check logs\web.log for details.
)

if "!RUN_ALIVE!"=="0" (
    echo   [FAIL] Run scheduler process not running!
    echo   Check logs\run.log for details.
    echo   Note: Ensure Xianyu session is valid (login via Dashboard).
)

echo.
echo ========================================
echo   Services Started!
echo ========================================
echo   Web:  http://127.0.0.1:8000
echo   Run:  Scheduler (logs/run.log)
echo.
echo To stop: double-click 停止服务.bat
echo.

start "" http://127.0.0.1:8000/app/
timeout /t 3 >nul 2>&1
exit
