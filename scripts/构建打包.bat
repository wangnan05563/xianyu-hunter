@echo off
set "MGPy=C:\Users\hspcadmin\.workbuddy\binaries\python\versions\3.13.12"
if exist "%MGPy%\python.exe" set "PATH=%MGPy%;%PATH%"
cd /d "%~dp0.."

echo ============================================
echo   XianyuHunter EXE Build
echo ============================================
echo.
echo Build steps:
echo   1. Create clean build venv
echo   2. Install deps + PyInstaller + tray (optional)
echo   3. Lock deps to requirements-lock.txt
echo   4. Build SPA (if changed)
echo   5. PyInstaller package (dir mode)
echo   6. Copy resources (SPA + Chromium + model)
echo   7. Build installer (Inno Setup, optional)
echo.
echo Output: release\xianyu-hunter\xianyu-hunter.exe
echo.

echo.
echo [Pre-build] Generating unique patch version...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0update-build-version.ps1"
if errorlevel 1 (
    echo.
    echo [ERROR] Version generation failed, see output above
    pause
    exit /b 1
)
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build-exe.ps1" %*

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed, see output above
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Build complete!
echo ============================================
echo   Dist dir:  release\xianyu-hunter\
echo   EXE path:  release\xianyu-hunter\xianyu-hunter.exe
echo.
echo   Next:
echo   - Run: release\xianyu-hunter\xianyu-hunter.exe
echo   - Installer: release\XianyuHunter-Setup-v*.exe (needs Inno Setup)
echo ============================================
echo.
pause
exit
