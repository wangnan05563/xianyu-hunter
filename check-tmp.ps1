$ErrorActionPreference = 'Continue'
$sonarHome = "C:\Users\hspcadmin\.sonar"
$tmpDir = "$sonarHome\_tmp"
$cacheDir = "$sonarHome\cache"

Write-Host "=== Sonar Home: $sonarHome ==="
if (Test-Path $sonarHome) {
    $info = Get-Item $sonarHome
    Write-Host "  Exists: yes"
    Write-Host "  Attributes: $($info.Attributes)"
    $acl = Get-Acl $sonarHome
    Write-Host "  Owner: $($acl.Owner)"
    Write-Host "  Access rules:"
    foreach ($rule in $acl.Access) {
        Write-Host "    - $($rule.IdentityReference): $($rule.FileSystemRights) ($($rule.AccessControlType))"
    }
} else {
    Write-Host "  NOT FOUND"
}

Write-Host ""
Write-Host "=== _tmp dir: $tmpDir ==="
if (Test-Path $tmpDir) {
    $info2 = Get-Item $tmpDir
    Write-Host "  Exists: yes, Attributes: $($info2.Attributes)"
    $files = Get-ChildItem $tmpDir -Force -ErrorAction SilentlyContinue
    Write-Host "  Contains $($files.Count) entries"
    $files | Select-Object -First 5 | ForEach-Object {
        Write-Host "    - $($_.Name) ($($_.Attributes))"
    }
    # Try to create a test file
    try {
        $testFile = "$tmpDir\test_$(Get-Random).tmp"
        "test" | Out-File -FilePath $testFile -NoNewline
        Write-Host "  WRITE TEST: SUCCESS"
        Remove-Item $testFile -Force
        Write-Host "  DELETE TEST: SUCCESS"
    } catch {
        Write-Host "  WRITE TEST FAILED: $($_.Exception.Message)"
    }
} else {
    Write-Host "  NOT FOUND - attempting to create..."
    try {
        New-Item -Path $tmpDir -ItemType Directory -Force | Out-Null
        Write-Host "  CREATED: $tmpDir"
    } catch {
        Write-Host "  CREATE FAILED: $($_.Exception.Message)"
    }
}

Write-Host ""
Write-Host "=== Cache dir: $cacheDir ==="
if (Test-Path $cacheDir) {
    $info3 = Get-Item $cacheDir
    Write-Host "  Exists: yes, Attributes: $($info3.Attributes)"
    $cacheFiles = Get-ChildItem $cacheDir -Force -ErrorAction SilentlyContinue
    Write-Host "  Contains $($cacheFiles.Count) entries"
}

Write-Host ""
Write-Host "=== Test temp file creation in different locations ==="
$testLocations = @(
    $env:TEMP,
    $sonarHome,
    $tmpDir,
    "d:\code\otherProjects\17_xianyu"
)
foreach ($loc in $testLocations) {
    try {
        $t = "$loc\sonar_test_$(Get-Random).tmp"
        "test" | Out-File -FilePath $t -NoNewline
        Remove-Item $t -Force
        Write-Host "  OK: $loc"
    } catch {
        Write-Host "  FAIL: $loc - $($_.Exception.Message)"
    }
}
