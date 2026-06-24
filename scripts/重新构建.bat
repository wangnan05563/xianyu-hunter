@echo off
chcp 65001 >nul 2>&1
REM Prepend Node.js 24 to PATH so all child processes resolve node to v24
set "PATH=D:\code\nodejs24;%PATH%"

echo ============================================
echo   Xianyu Hunter - Frontend Rebuild
echo ============================================
echo.
echo Node:
D:\code\nodejs24\node.exe --version
echo.

REM Script is in scripts/ subdirectory, change to frontend dir
cd /d "%~dp0..\frontend"

echo [1/2] Cleaning old build...
if exist "..\src\xianyu_hunter\web\static\spa" (
    rmdir /s /q "..\src\xianyu_hunter\web\static\spa"
    echo   Old files cleaned
)

echo.
echo [2/2] Building frontend...
D:\code\nodejs24\node.exe "node_modules\vite\bin\vite.js" build

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
