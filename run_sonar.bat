@echo off
set SONAR_TOKEN=sqa_fe4b774b40e19eca12e0f46a2f2f771f2d1a23bd
sonar-scanner.bat -Dsonar.host.url=http://localhost:9000 -Dsonar.token=%SONAR_TOKEN% -Dsonar.projectKey=xianyu-hunter -Dsonar.sources=src,frontend/src -Dsonar.sourceEncoding=UTF-8 -Dsonar.scm.disabled=true -Dsonar.skipSystemTruststore=true