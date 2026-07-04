Set-Location 'd:\code\otherProjects\17_xianyu\frontend'
$tscPath = Join-Path $PWD 'node_modules\typescript\lib\tsc.js'
$proc = Start-Process -FilePath 'node' -ArgumentList "`"$tscPath`"", '--noEmit', '--pretty', 'false' -NoNewWindow -Wait -PassThru -RedirectStandardOutput 'tsc-stdout.log' -RedirectStandardError 'tsc-stderr.log'
Write-Host "ExitCode: $($proc.ExitCode)"
if (Test-Path 'tsc-stdout.log') {
  Write-Host '--- stdout ---'
  Get-Content 'tsc-stdout.log' -Raw | Out-Host
}
if (Test-Path 'tsc-stderr.log') {
  Write-Host '--- stderr ---'
  Get-Content 'tsc-stderr.log' -Raw | Out-Host
}
