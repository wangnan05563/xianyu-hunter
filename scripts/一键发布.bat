@echo off
setlocal enabledelayedexpansion
REM ============================================================
REM XianyuHunter one-click build + package + publish to GitHub Releases
REM Pure ASCII entry (English only). All Chinese output is delegated
REM to build-publish.ps1. No project name / path / version hardcoded.
REM Configure everything in config.publish.json (github_release + build_pipeline).
REM ============================================================

set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."
for %%I in ("%REPO_ROOT%") do set "REPO_ROOT=%%~fI"

if not defined CONFIG_PATH set "CONFIG_PATH=%SCRIPT_DIR%config.publish.json"

REM Console output codepage: 65001 so the .ps1 UTF-8 output shows correctly.
chcp 65001 >nul

echo [publish] repo root: %REPO_ROOT%
echo [publish] config   : %CONFIG_PATH%

powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%build-publish.ps1" -ConfigPath "%CONFIG_PATH%" -RepoRoot "%REPO_ROOT%" %*
if errorlevel 1 (
  echo [publish] FAILED - see output above
  exit /b 1
)

echo.
echo [publish] DONE.
endlocal
