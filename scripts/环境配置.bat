@echo off
chcp 936 >nul 2>&1
REM 脚本位于 scripts/ 子目录，调用同目录下的 setup-env.ps1
cd /d "%~dp0.."

echo ============================================
echo   闲鱼猎人环境配置（调用 PowerShell 脚本）
echo ============================================
echo.

REM -NoProfile：不加载用户自定义 profile（避免 safe_rm_aliases.ps1 等干扰）
REM -ExecutionPolicy Bypass：绕过执行策略限制，允许双击执行未签名脚本
REM -File：指定要执行的 ps1 脚本，%* 透传所有命令行参数（如 -SkipSystem）
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-env.ps1" %*

REM PowerShell 脚本退出码透传
if errorlevel 1 (
    echo.
    echo [ERROR] 环境配置失败，请查看上方错误信息
    pause
    exit /b 1
)

echo.
echo 配置完成，按任意键关闭窗口...
pause >nul
exit
