Set-Location "d:\code\otherProjects\17_xianyu"
# Use git show to get commit message and write to file with UTF-8 encoding
# Using [System.IO.File] to bypass PowerShell 5 console encoding issues
$msg = git show HEAD --no-patch --pretty=format:"%s"
$bytes = [System.Text.Encoding]::UTF8.GetBytes($msg)
[System.IO.File]::WriteAllBytes("d:\code\otherProjects\17_xianyu\msg_verify.txt", $bytes)
