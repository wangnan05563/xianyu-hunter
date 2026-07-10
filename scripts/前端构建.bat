@echo off
chcp 936 >nul 2>&1
REM 将 Node.js 24 前置到 PATH，让所有子进程都解析到 v24
set "PATH=D:\code\nodejs24;%PATH%"

echo ============================================
echo   闲鱼猎人 - 前端重新构建
echo ============================================
echo.
echo Node 版本:
D:\code\nodejs24\node.exe --version
echo.

REM 脚本位于 scripts/ 子目录，切换到 frontend 目录
cd /d "%~dp0..\frontend"

echo [1/2] 正在清理旧构建产物...
if exist "..\src\xianyu_hunter\web\static\spa" (
    rmdir /s /q "..\src\xianyu_hunter\web\static\spa"
    echo   旧文件已清理
)

echo.
echo [2/2] 正在构建前端...
D:\code\nodejs24\node.exe "node_modules\vite\bin\vite.js" build

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] 构建失败，请查看上方错误信息
    pause
    exit /b 1
)

echo.
echo [3/3] 正在生成构建信息（版本号 + git sha）...
cd /d "%~dp0.."
python scripts\build_info.py
if errorlevel 1 (
    echo [WARN] build_info.py 执行失败；关于页面将显示 "unknown"
)

echo.
echo ============================================
echo   构建完成！请重启服务并按 Ctrl+F5 强制刷新
echo ============================================
pause
