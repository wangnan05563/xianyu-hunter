@echo off
chcp 936 >nul 2>&1
REM Build script: calls scripts/build-exe.ps1 from project root
cd /d "%~dp0.."

echo ============================================
echo   XianyuHunter EXE Build
echo ============================================
echo.
echo Steps:
echo   1. Create clean build venv
echo   2. Install deps + PyInstaller + tray (optional)
echo   3. Lock deps to requirements-lock.txt
echo   4. Build SPA (if changed)
echo   5. PyInstaller packaging (dir mode)
echo   6. Copy resources (SPA + Chromium + model)
echo   7. Build installer (Inno Setup, optional)
echo.
echo Output: dist\xianyu-hunter\xianyu-hunter.exe
echo.

REM -NoProfile: skip user PS profile (avoids alias interference)
REM -ExecutionPolicy Bypass: allow running unsigned script via double-click
REM -File: target script, %* passes through all CLI args
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build-exe.ps1" %*

REM Forward PowerShell exit code
if errorlevel 1 (
    echo.
    echo [ERROR] Build failed. Check output above.
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Build complete!
echo ============================================
echo   Output:  dist\xianyu-hunter\
echo   EXE:     dist\xianyu-hunter\xianyu-hunter.exe
echo.
echo   Next:
echo   - Run: dist\xianyu-hunter\xianyu-hunter.exe
echo   - Installer: dist\XianyuHunter-Setup-v*.exe (needs Inno Setup)
echo ============================================
echo.
pause
exit