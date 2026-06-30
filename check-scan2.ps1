$ErrorActionPreference = 'Continue'
$headers = @{ 'Authorization' = "Bearer sqa_fe4b774b40e19eca12e0f46a2f2f771f2d1a23bd" }
$base = "http://localhost:9000"

Write-Host "=== All Projects on Server ==="
try {
    $r = Invoke-RestMethod -Uri "$base/api/components/search?qualifiers=TRK&ps=500" -Headers $headers -TimeoutSec 10
    Write-Host "Total projects: $($r.paging.total)"
    foreach ($c in $r.components) {
        Write-Host "  - key=$($c.key) name=$($c.name)"
    }
} catch {
    Write-Host "ERROR: $($_.Exception.Message)"
}

Write-Host ""
Write-Host "=== Java Processes ==="
$java = Get-Process -Name "java" -ErrorAction SilentlyContinue
if ($java) {
    foreach ($p in $java) {
        Write-Host "  PID=$($p.Id) Mem=$([math]::Round($p.WorkingSet64/1MB))MB Started=$($p.StartTime.ToString('HH:mm:ss'))"
    }
} else {
    Write-Host "  No Java processes (scanner engine stopped)"
}

Write-Host ""
Write-Host "=== Scannerwork Status ==="
$sw = "d:\code\otherProjects\17_xianyu\.scannerwork"
if (Test-Path $sw) {
    $files = Get-ChildItem $sw -Recurse -File -ErrorAction SilentlyContinue
    Write-Host "  $($files.Count) files in .scannerwork"
    foreach ($f in ($files | Sort-Object LastWriteTime -Descending | Select-Object -First 5)) {
        Write-Host "  - $($f.Name) size=$($f.Length) modified=$($f.LastWriteTime.ToString('HH:mm:ss'))"
    }
} else {
    Write-Host "  .scannerwork NOT FOUND (scan completed & cleaned up, or never started)"
}

Write-Host ""
Write-Host "=== Total Issues & Latest ==="
try {
    $is = Invoke-RestMethod -Uri "$base/api/issues/search?ps=1" -Headers $headers -TimeoutSec 10
    Write-Host "  Total: $($is.paging.total)"
    if ($is.issues) {
        Write-Host "  Latest: project=$($is.issues[0].project) created=$($is.issues[0].creationDate)"
    }
} catch {
    Write-Host "ERROR: $($_.Exception.Message)"
}

Write-Host ""
Write-Host "=== Sonar-scan.log tail (last 30 lines) ==="
$logFile = "d:\code\otherProjects\17_xianyu\sonar-scan.log"
if (Test-Path $logFile) {
    $logInfo = Get-Item $logFile
    Write-Host "  Log size: $($logInfo.Length) bytes, last write: $($logInfo.LastWriteTime.ToString('HH:mm:ss'))"
    Get-Content $logFile -Tail 30 | ForEach-Object { Write-Host "  $_" }
}
