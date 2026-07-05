Set-Location "d:\code\otherProjects\17_xianyu"
Remove-Item -Path "frontend\run_build.ps1" -Force -ErrorAction SilentlyContinue
git status --short | Out-File "d:\code\otherProjects\17_xianyu\final_status.txt" -Encoding utf8
git log -1 --pretty=format:"%H %s" | Out-File "d:\code\otherProjects\17_xianyu\final_status.txt" -Append -Encoding utf8
