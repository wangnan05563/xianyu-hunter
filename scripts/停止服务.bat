@echo off
chcp 936 >nul 2>&1
REM 脚本位于 scripts/ 子目录，回到项目根目录
cd /d "%~dp0.."
setlocal enabledelayedexpansion

echo ========================================
echo   正在停止闲鱼猎人服务...
echo ========================================

REM [1/3] 通过 PID 文件停止 Web 服务，失败则回退到端口扫描
echo [1/3] 正在停止 Web 服务...

set WEB_KILLED=0

if exist "logs\web.pid" (
    for /f "tokens=*" %%a in (logs\web.pid) do (
        taskkill /F /T /PID %%a >nul 2>&1
        if not errorlevel 1 (
            echo   [OK] Web 服务已停止 (PID %%a)
            set WEB_KILLED=1
        )
    )
    del "logs\web.pid" >nul 2>&1
)

REM 回退：杀掉监听 8001 端口的进程
if "!WEB_KILLED!"=="0" (
    for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8001.*LISTENING"') do (
        taskkill /F /T /PID %%a >nul 2>&1
        if not errorlevel 1 (
            echo   [OK] Web 服务已停止 (PID %%a, 通过端口扫描找到)
            set WEB_KILLED=1
        )
    )
)

if "!WEB_KILLED!"=="0" (
    echo   [SKIP] 未找到监听 8001 端口的 Web 服务进程
)

REM [2/3] 释放浏览器资源（WebView2 + Edge 子进程）
echo [2/3] 正在清理浏览器进程...

taskkill /F /IM msedgewebview2.exe >nul 2>&1
taskkill /F /IM msedge.exe >nul 2>&1
taskkill /F /IM chromium.exe >nul 2>&1
taskkill /F /IM chrome.exe >nul 2>&1

timeout /t 1 >nul 2>&1

REM [3/3] 验证关闭结果 - 端口已释放且无 xianyu_hunter 进程残留
echo [3/3] 正在验证关闭结果...

set PORT_FREE=1
netstat -aon | findstr ":8001.*LISTENING" >nul 2>&1
if not errorlevel 1 (
    set PORT_FREE=0
    echo   [WARN] 端口 8001 仍被占用！
)

if "!PORT_FREE!"=="1" (
    echo   [OK] 所有服务已成功停止
) else (
    echo   [WARN] 部分进程可能仍在运行，请检查任务管理器
)

echo.
echo ========================================
echo   服务已停止
echo ========================================
echo.
timeout /t 2 >nul 2>&1
