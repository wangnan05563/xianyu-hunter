# 验证 .bat / .ps1 / .vbs 文件编码、行尾、BOM 是否符合规范
# 用法: powershell -File verify.ps1 -TargetDir <DIR>
#
# 规范：
#   .bat → GBK + 无 BOM + CRLF
#   .ps1 → UTF-8 with BOM + CRLF
#   .vbs → GBK + 无 BOM + CRLF（含中文时 wscript/cscript 按 ANSI 解析）

param(
    [Parameter(Mandatory=$true)][string]$TargetDir
)

# GBK 编码（默认使用 DecoderReplacementFallback，遇到非法字节用 U+FFFD 替换）
$gbk = [System.Text.Encoding]::GetEncoding(936)
# UTF-8 严格模式（遇到非法字节抛异常）
$utf8Strict = New-Object System.Text.UTF8Encoding($false, $true)
$script:pass = 0
$script:fail = 0

function Test-FileEncoding {
    param($path, $expectedEncoding, $expectBom)
    $b = [System.IO.File]::ReadAllBytes($path)
    $hasBom = ($b.Length -ge 3 -and $b[0] -eq 0xEF -and $b[1] -eq 0xBB -and $b[2] -eq 0xBF)
    $issues = @()

    # BOM 检查
    if ($expectBom -and -not $hasBom) { $issues += "缺少 BOM" }
    if (-not $expectBom -and $hasBom) { $issues += "不应有 BOM" }

    # 行尾检查（孤立 LF）
    $lf = 0
    for ($i=0; $i -lt $b.Length; $i++) {
        if ($b[$i] -eq 0x0A -and ($i -eq 0 -or $b[$i-1] -ne 0x0D)) { $lf++ }
    }
    if ($lf -gt 0) { $issues += "$lf 个孤立 LF 行尾" }

    # 编码可解码性
    if ($expectedEncoding -eq 'GBK') {
        # GBK 解码：默认 DecoderReplacementFallback 遇到非法字节用 U+FFFD 替换
        # 检查解码结果是否包含 U+FFFD，包含则说明有非法字节
        $decoded = $gbk.GetString($b)
        if ($decoded -match [char]0xFFFD) { $issues += "GBK 解码出现替换字符 U+FFFD（含非法字节）" }
    }
    elseif ($expectedEncoding -eq 'UTF8') {
        try {
            $null = $utf8Strict.GetString($b)
        } catch {
            $issues += "无法按 UTF-8 严格解码: $($_.Exception.Message)"
        }
    }

    return @{ issues = $issues; hasBom = $hasBom; lf = $lf }
}

# 验证所有 .bat（GBK + 无 BOM + CRLF）
Get-ChildItem $TargetDir -Filter '*.bat' -Recurse | ForEach-Object {
    $r = Test-FileEncoding $_.FullName 'GBK' $false
    if ($r.issues.Count -eq 0) { Write-Host "[PASS] $($_.Name)" -ForegroundColor Green; $script:pass++ }
    else { Write-Host "[FAIL] $($_.Name): $($r.issues -join ', ')" -ForegroundColor Red; $script:fail++ }
}

# 验证所有 .ps1（UTF-8 + BOM + CRLF）
Get-ChildItem $TargetDir -Filter '*.ps1' -Recurse | ForEach-Object {
    $r = Test-FileEncoding $_.FullName 'UTF8' $true
    if ($r.issues.Count -eq 0) { Write-Host "[PASS] $($_.Name)" -ForegroundColor Green; $script:pass++ }
    else { Write-Host "[FAIL] $($_.Name): $($r.issues -join ', ')" -ForegroundColor Red; $script:fail++ }
}

# 验证所有 .vbs（GBK + 无 BOM + CRLF）
Get-ChildItem $TargetDir -Filter '*.vbs' -Recurse | ForEach-Object {
    $r = Test-FileEncoding $_.FullName 'GBK' $false
    if ($r.issues.Count -eq 0) { Write-Host "[PASS] $($_.Name)" -ForegroundColor Green; $script:pass++ }
    else { Write-Host "[FAIL] $($_.Name): $($r.issues -join ', ')" -ForegroundColor Red; $script:fail++ }
}

Write-Host ""
Write-Host "总计: $script:pass PASS, $script:fail FAIL" -ForegroundColor $(if ($script:fail -eq 0) {'Green'} else {'Red'})
exit $(if ($script:fail -eq 0) {0} else {1})
