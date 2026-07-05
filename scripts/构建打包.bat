@echo off
chcp 936 >nul 2>&1
REM 脚本位于 scripts/ 子目录，调用同目录的 build-exe.ps1
cd /d "%~dp0.."

echo ============================================
echo   XianyuHunter EXE 一键打包（调用 PowerShell 脚本）
echo ============================================
echo.
echo 构建流程：
echo   1. 创建干净 venv（避免开发环境传递依赖污染）
echo   2. 安装项目依赖 + PyInstaller + 可选托盘依赖
echo   3. 锁定依赖到 requirements-lock.txt
echo   4. 构建 SPA（如未构建）
echo   5. PyInstaller 打包（目录模式）
echo   6. 复制外置资源（SPA + Playwright Chromium + sentence-transformers 模型）
echo   7. 制作安装包（Inno Setup 编译 installer.iss，未安装时自动安装）
echo.
echo 产物：dist\xianyu-hunter\xianyu-hunter.exe
echo.

REM -NoProfile：避免用户自定义 profile 干扰（如 safe_rm_aliases.ps1）
REM -ExecutionPolicy Bypass：绕过执行策略限制，允许双击执行未签名脚本
REM -File：指定要执行的 ps1 脚本，%* 透传所有命令行参数
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build-exe.ps1" %*

REM PowerShell 脚本退出码透传
if errorlevel 1 (
    echo.
    echo [ERROR] 打包失败，请查看上方错误信息
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   打包完成！
echo ============================================
echo   产物目录：dist\xianyu-hunter\
echo   启动器：  dist\xianyu-hunter\xianyu-hunter.exe
echo.
echo   产物：
echo   - EXE：dist\xianyu-hunter\xianyu-hunter.exe
echo   - 安装包：dist\XianyuHunter-Setup-v*.exe（如 Inno Setup 可用）
echo   - 或直接运行 dist\xianyu-hunter\xianyu-hunter.exe 测试
echo ============================================
echo.
pause
exit