$ErrorActionPreference = "Continue"
$log = "d:\code\otherProjects\17_xianyu\git_op_log.txt"
"=== STEP 1: git status before ===" | Out-File -FilePath $log -Encoding utf8
git status --short 2>&1 | Out-File -FilePath $log -Append -Encoding utf8
"=== STEP 2: git add ===" | Out-File -FilePath $log -Append -Encoding utf8
git add frontend/src/mobile/pages/Orders/ 2>&1 | Out-File -FilePath $log -Append -Encoding utf8
"=== STEP 3: git status after add ===" | Out-File -FilePath $log -Append -Encoding utf8
git status --short 2>&1 | Out-File -FilePath $log -Append -Encoding utf8
"=== STEP 4: git commit ===" | Out-File -FilePath $log -Append -Encoding utf8
git commit -F "d:\code\otherProjects\17_xianyu\commit_msg.txt" 2>&1 | Out-File -FilePath $log -Append -Encoding utf8
"=== STEP 5: git log ===" | Out-File -FilePath $log -Append -Encoding utf8
git log --oneline -3 2>&1 | Out-File -FilePath $log -Append -Encoding utf8
"=== STEP 6: git rev-parse HEAD ===" | Out-File -FilePath $log -Append -Encoding utf8
git rev-parse HEAD 2>&1 | Out-File -FilePath $log -Append -Encoding utf8
"DONE" | Out-File -FilePath $log -Append -Encoding utf8
