@echo off
chcp 936 >nul 2>&1
REM 运行 sonar-scanner 并将输出重定向到文件（避免 PowerShell 缓冲）
set SONAR_TOKEN=sqa_fe4b774b40e19eca12e0f46a2f2f771f2d1a23bd
"D:\code\sonar\sonar-scanner-8.0.1.6346-windows-x64\bin\sonar-scanner.bat" > scan-output.log 2>&1
echo 退出码: %ERRORLEVEL%
