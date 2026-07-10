@echo off
chcp 936 >nul 2>&1
REM 构建脚本：从项目根目录调用 scripts/build-exe.ps1
cd /d "%~dp0.."

echo ============================================
echo   闲鱼猎人 EXE 构建
echo ============================================
echo.
echo 构建步骤:
echo   1. 创建干净的构建 venv
echo   2. 安装依赖 + PyInstaller + 托盘（可选）
echo   3. 锁定依赖到 requirements-lock.txt
echo   4. 构建 SPA（如有变更）
echo   5. PyInstaller 打包（dir 模式）
echo   6. 复制资源（SPA + Chromium + 模型）
echo   7. 构建安装包（Inno Setup，可选）
echo.
echo 产物路径: dist\xianyu-hunter\xianyu-hunter.exe
echo.

REM -NoProfile: 跳过用户 PS profile（避免别名干扰）
REM -ExecutionPolicy Bypass: 允许通过双击执行未签名脚本
REM -File: 目标脚本，%* 透传所有命令行参数
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build-exe.ps1" %*

REM 透传 PowerShell 退出码
if errorlevel 1 (
    echo.
    echo [ERROR] 构建失败，请查看上方输出
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   构建完成！
echo ============================================
echo   产物目录:  dist\xianyu-hunter\
echo   EXE 路径:  dist\xianyu-hunter\xianyu-hunter.exe
echo.
echo   后续操作:
echo   - 运行: dist\xianyu-hunter\xianyu-hunter.exe
echo   - 安装包: dist\XianyuHunter-Setup-v*.exe（需安装 Inno Setup）
echo ============================================
echo.
pause
exit
