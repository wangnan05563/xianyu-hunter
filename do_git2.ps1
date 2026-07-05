$ErrorActionPreference = "Continue"
$log = "d:\code\otherProjects\17_xianyu\git_op_log2.txt"

"=== STEP 1: reset soft HEAD~1 ===" | Out-File -FilePath $log -Encoding utf8
git reset --soft HEAD~1 2>&1 | Out-File -FilePath $log -Append -Encoding utf8

"=== STEP 2: reset (unstage all) ===" | Out-File -FilePath $log -Append -Encoding utf8
git reset 2>&1 | Out-File -FilePath $log -Append -Encoding utf8

"=== STEP 3: add only Task 11 files ===" | Out-File -FilePath $log -Append -Encoding utf8
git add frontend/src/mobile/pages/Orders/ 2>&1 | Out-File -FilePath $log -Append -Encoding utf8

"=== STEP 4: git status short ===" | Out-File -FilePath $log -Append -Encoding utf8
git status --short 2>&1 | Out-File -FilePath $log -Append -Encoding utf8

"=== STEP 5: create GBK commit_msg.txt ===" | Out-File -FilePath $log -Append -Encoding utf8
$gbk = [System.Text.Encoding]::GetEncoding("GBK")
$msg = "feat: " + [char]0x65B0 + [char]0x589E + [char]0x79FB + [char]0x52A8 + [char]0x7AEF + [char]0x62A2 + [char]0x5355 + [char]0x8BB0 + [char]0x5F55 + [char]0x5217 + [char]0x8868 + [char]0x4E0E + [char]0x8BE6 + [char]0x60C5 + [char]0x9875 + [char]0x9762 + [char]0xFF08 + [char]0x542B + [char]0x72B6 + [char]0x6001 + [char]0x4FEE + [char]0x6539 + [char]0xFF09
[System.IO.File]::WriteAllText("d:\code\otherProjects\17_xianyu\commit_msg.txt", $msg, $gbk)
"commit_msg.txt created with GBK encoding" | Out-File -FilePath $log -Append -Encoding utf8

"=== STEP 6: verify commit_msg.txt content ===" | Out-File -FilePath $log -Append -Encoding utf8
$gbk2 = [System.Text.Encoding]::GetEncoding("GBK")
$content = [System.IO.File]::ReadAllText("d:\code\otherProjects\17_xianyu\commit_msg.txt", $gbk2)
"Content: $content" | Out-File -FilePath $log -Append -Encoding utf8

"=== STEP 7: git commit ===" | Out-File -FilePath $log -Append -Encoding utf8
git commit -F "d:\code\otherProjects\17_xianyu\commit_msg.txt" 2>&1 | Out-File -FilePath $log -Append -Encoding utf8

"=== STEP 8: git log ===" | Out-File -FilePath $log -Append -Encoding utf8
git log --oneline -3 2>&1 | Out-File -FilePath $log -Append -Encoding utf8

"=== STEP 9: git rev-parse HEAD ===" | Out-File -FilePath $log -Append -Encoding utf8
git rev-parse HEAD 2>&1 | Out-File -FilePath $log -Append -Encoding utf8

"DONE" | Out-File -FilePath $log -Append -Encoding utf8
