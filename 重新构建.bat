@echo off
REM 指定 Node.js 24 路径，避免使用系统 PATH 中的旧版本
set PATH=D:\code\nodejs24;%PATH%

echo ============================================
echo   Xianyu Hunter - Frontend Rebuild
echo ============================================
echo.
echo Node: 
call node --version
echo.

cd /d "%~dp0frontend"

echo [1/2] Cleaning old build...
if exist "..\src\xianyu_hunter\web\static\spa" (
    rmdir /s /q "..\src\xianyu_hunter\web\static\spa"
    echo   Old files cleaned
)

echo.
echo [2/2] Building frontend...
call npx vite build

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Build failed, check errors above
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Build complete! Restart service and Ctrl+F5
echo ============================================
pause
