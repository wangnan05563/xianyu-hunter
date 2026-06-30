$ErrorActionPreference = 'Continue'

Write-Host "=== Attempt 1: Grant CodexSandboxUsers Modify on .sonar ==="
& icacls "C:\Users\hspcadmin\.sonar" /grant "CodexSandboxUsers:(OI)(CI)M" /T 2>&1 | Tee-Object -Variable icaclsResult | Out-Host
$icaclsExit = $LASTEXITCODE
Write-Host "icacls exit code: $icaclsExit"

Write-Host ""
Write-Host "=== Verify _tmp is now writable ==="
$testFile = "C:\Users\hspcadmin\.sonar\_tmp\test_$(Get-Random).tmp"
try {
    "test" | Out-File -FilePath $testFile -NoNewline
    Write-Host "  WRITE TEST: SUCCESS"
    Remove-Item $testFile -Force
    Write-Host "  DELETE TEST: SUCCESS"
    $canWriteTmp = $true
} catch {
    Write-Host "  WRITE TEST FAILED: $($_.Exception.Message)"
    $canWriteTmp = $false
}

Write-Host ""
if ($canWriteTmp) {
    Write-Host "=== Running scanner with existing .sonar cache (fast) ==="
    $env:SONAR_SCANNER_OPTS = "-Xmx2048m"
} else {
    Write-Host "=== Permission grant failed - using SONAR_USER_HOME fallback ==="
    $newHome = "d:\code\otherProjects\17_xianyu\.sonar-home"
    if (-not (Test-Path $newHome)) {
        New-Item -Path $newHome -ItemType Directory -Force | Out-Null
    }
    # Copy cache to new home to avoid re-download
    if (Test-Path "C:\Users\hspcadmin\.sonar\cache") {
        if (-not (Test-Path "$newHome\cache")) {
            Write-Host "  Copying cache from C:\Users\hspcadmin\.sonar\cache to $newHome\cache..."
            Copy-Item -Path "C:\Users\hspcadmin\.sonar\cache" -Destination "$newHome\cache" -Recurse -Force
            Write-Host "  Cache copy complete"
        }
    }
    $env:SONAR_USER_HOME = $newHome
    $env:SONAR_SCANNER_OPTS = "-Xmx2048m"
}

Write-Host ""
Write-Host "=== SONAR_USER_HOME = $env:SONAR_USER_HOME ==="
Write-Host "=== SONAR_SCANNER_OPTS = $env:SONAR_SCANNER_OPTS ==="
Write-Host ""
Write-Host "=== Executing sonar-scanner... ==="

& "D:\code\sonar\sonar-scanner-8.0.1.6346-windows-x64\bin\sonar-scanner.bat" 2>&1 | Tee-Object -FilePath "d:\code\otherProjects\17_xianyu\sonar-scan.log"
Write-Host ""
Write-Host "=== Scanner exit code: $LASTEXITCODE ==="
