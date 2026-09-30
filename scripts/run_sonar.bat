@echo off
rem Token is read from SONAR_TOKEN env var to avoid committing credentials into the repo.
rem Project key and sources are configured in sonar-project.properties (backend/xianyu_hunter, frontend/src).
if "%SONAR_TOKEN%"=="" (
    echo [ERROR] SONAR_TOKEN environment variable not set.
    exit /b 1
)
sonar-scanner.bat -Dsonar.host.url=http://localhost:9000 -Dsonar.token=%SONAR_TOKEN% -Dsonar.projectKey=xianyu_hunter -Dsonar.sourceEncoding=UTF-8 -Dsonar.scm.disabled=true -Dsonar.skipSystemTruststore=true