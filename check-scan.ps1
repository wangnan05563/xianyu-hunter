$ErrorActionPreference = 'Continue'
$headers = @{ 'Authorization' = "Bearer sqa_fe4b774b40e19eca12e0f46a2f2f771f2d1a23bd" }
$base = "http://localhost:9000"

Write-Host "=== Java/Scanner Processes ==="
$java = Get-Process -Name "java" -ErrorAction SilentlyContinue
if ($java) {
    $java | Select-Object Id, ProcessName, @{N='MemMB';E={[math]::Round($_.WorkingSet64/1MB)}}, StartTime | Format-Table -AutoSize
} else {
    Write-Host "  No Java processes running (scanner engine likely finished)"
}

Write-Host ""
Write-Host "=== Scannerwork Directory ==="
$sw = "d:\code\otherProjects\17_xianyu\.scannerwork"
if (Test-Path $sw) {
    $files = Get-ChildItem $sw -Recurse -File -ErrorAction SilentlyContinue
    Write-Host "  Found $($files.Count) files in .scannerwork"
    $files | Sort-Object LastWriteTime -Descending | Select-Object -First 5 | ForEach-Object {
        Write-Host ("    - {0} (size={1}, modified={2})" -f $_.Name, $_.Length, $_.LastWriteTime.ToString('HH:mm:ss'))
    }
} else {
    Write-Host "  NO .scannerwork directory (scan may not have completed)"
}

Write-Host ""
Write-Host "=== Server: Search xianyu project ==="
try {
    $r = Invoke-RestMethod -Uri "$base/api/components/search?query=xianyu&ps=50" -Headers $headers -TimeoutSec 10
    Write-Host "  Components matching 'xianyu': $($r.components.Count)"
    $r.components | ForEach-Object {
        Write-Host ("    - key={0} name={1} qualifier={2} lang={3}" -f $_.key, $_.name, $_.qualifier, $_.language)
    }
} catch {
    Write-Host "  ERROR: $($_.Exception.Message)"
}

Write-Host ""
Write-Host "=== Server: Search xianyu_hunter project (exact key) ==="
try {
    $r2 = Invoke-RestMethod -Uri "$base/api/components/search?query=xianyu_hunter&ps=50" -Headers $headers -TimeoutSec 10
    Write-Host "  Components matching 'xianyu_hunter': $($r2.components.Count)"
    $r2.components | ForEach-Object {
        Write-Host ("    - key={0} name={1} qualifier={2} lang={3}" -f $_.key, $_.name, $_.qualifier, $_.language)
    }
} catch {
    Write-Host "  ERROR: $($_.Exception.Message)"
}

Write-Host ""
Write-Host "=== Server: Recent activity (last 5 issues across all projects) ==="
try {
    $is = Invoke-RestMethod -Uri "$base/api/issues/search?ps=5&sortKey=creationDate&sortAsc=false" -Headers $headers -TimeoutSec 10
    Write-Host "  Total issues in system: $($is.paging.total)"
    Write-Host "  Recent 5 issues:"
    $is.issues | ForEach-Object {
        Write-Host ("    - project={0} rule={1} severity={2} created={3}" -f $_.project, $_.rule, $_.severity, $_.creationDate)
    }
} catch {
    Write-Host "  ERROR: $($_.Exception.Message)"
}

Write-Host ""
Write-Host "=== Server: Activity timestamps ==="
try {
    $is2 = Invoke-RestMethod -Uri "$base/api/issues/search?ps=1" -Headers $headers -TimeoutSec 10
    if ($is2.issues) {
        Write-Host "  Most recent issue: $($is2.issues[0].creationDate)"
        Write-Host "  Today's date: $(Get-Date -Format 'yyyy-MM-ddTHH:mm:ss')"
    }
} catch {
    Write-Host "  ERROR: $($_.Exception.Message)"
}
