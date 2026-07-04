@echo off
REM Run sonar-scanner with output redirected to file (no PowerShell buffering)
set SONAR_TOKEN=sqa_fe4b774b40e19eca12e0f46a2f2f771f2d1a23bd
"D:\code\sonar\sonar-scanner-8.0.1.6346-windows-x64\bin\sonar-scanner.bat" > scan-output.log 2>&1
echo EXIT_CODE: %ERRORLEVEL%
