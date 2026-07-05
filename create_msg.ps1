$m = "feat: " + [char]0x65B0 + [char]0x589E + [char]0x79FB + [char]0x52A8 + [char]0x7AEF + [char]0x62A2 + [char]0x5355 + [char]0x8BB0 + [char]0x5F55 + [char]0x5217 + [char]0x8868 + [char]0x4E0E + [char]0x8BE6 + [char]0x60C5 + [char]0x9875 + [char]0x9762 + [char]0xFF08 + [char]0x542B + [char]0x72B6 + [char]0x6001 + [char]0x4FEE + [char]0x6539 + [char]0xFF09
$gbk = [System.Text.Encoding]::GetEncoding("GBK")
[System.IO.File]::WriteAllText("d:\code\otherProjects\17_xianyu\msg.txt", $m, $gbk)
Write-Output "File created"
