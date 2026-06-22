@echo off
REM Prepend Node.js 24 to PATH so all child processes (vite, esbuild, rollup,
REM tsc, etc.) resolve "node" to v24 instead of the legacy v14 on system PATH.
set "PATH=D:\code\nodejs24;%PATH%"

echo ============================================
echo   Xianyu Hunter - Frontend Rebuild
echo ============================================
echo.
echo Node:
D:\code\nodejs24\node.exe --version
echo.

cd /d "%~dp0frontend"

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
