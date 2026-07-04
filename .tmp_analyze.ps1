$ErrorActionPreference = 'Stop'
$src = 'C:\Users\HSPCAD~1\AppData\Local\Temp\trae\toolcall-output\c87fff4e-2632-4aa7-a0d2-5980d444f130.txt'
$dst = 'd:\code\otherProjects\17_xianyu\.tmp_sonar_summary.txt'

$json = Get-Content $src -Raw | ConvertFrom-Json
$payload = $json[0].text | ConvertFrom-Json
$issues = $payload.issues

$lines = @()
$lines += "Total issues: $($issues.Count)"
$lines += "Paging total: $($payload.paging.total)"
$lines += ""

# Group by component
$lines += "=== Files (grouped) ==="
$issues | Group-Object component | Sort-Object Count -Descending | ForEach-Object {
    $file = $_.Name -replace 'xianyu_hunter:', ''
    $lines += "  $($_.Count): $file"
}
$lines += ""

# Group by rule
$lines += "=== Rules ==="
$issues | Group-Object rule | Sort-Object Count -Descending | ForEach-Object {
    $lines += "  $($_.Count): $($_.Name)"
}
$lines += ""

# Group by severity
$lines += "=== Severity ==="
$issues | Group-Object severity | Sort-Object Name | ForEach-Object {
    $lines += "  $($_.Count): $($_.Name)"
}

# Write to file
$lines | Out-File -FilePath $dst -Encoding utf8
Write-Output "DONE: $dst"
