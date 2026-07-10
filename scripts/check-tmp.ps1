$ErrorActionPreference = 'Continue'
$sonarHome = "C:\Users\hspcadmin\.sonar"
$tmpDir = "$sonarHome\_tmp"
$cacheDir = "$sonarHome\cache"

Write-Host "=== Sonar Home 目录: $sonarHome ==="
if (Test-Path $sonarHome) {
    $info = Get-Item $sonarHome
    Write-Host "  存在: 是"
    Write-Host "  属性: $($info.Attributes)"
    $acl = Get-Acl $sonarHome
    Write-Host "  所有者: $($acl.Owner)"
    Write-Host "  访问规则:"
    foreach ($rule in $acl.Access) {
        Write-Host "    - $($rule.IdentityReference): $($rule.FileSystemRights) ($($rule.AccessControlType))"
    }
} else {
    Write-Host "  未找到"
}

Write-Host ""
Write-Host "=== _tmp 目录: $tmpDir ==="
if (Test-Path $tmpDir) {
    $info2 = Get-Item $tmpDir
    Write-Host "  存在: 是, 属性: $($info2.Attributes)"
    $files = Get-ChildItem $tmpDir -Force -ErrorAction SilentlyContinue
    Write-Host "  包含 $($files.Count) 个条目"
    $files | Select-Object -First 5 | ForEach-Object {
        Write-Host "    - $($_.Name) ($($_.Attributes))"
    }
    # 尝试创建测试文件
    try {
        $testFile = "$tmpDir\test_$(Get-Random).tmp"
        "test" | Out-File -FilePath $testFile -NoNewline
        Write-Host "  写入测试: 成功"
        Remove-Item $testFile -Force
        Write-Host "  删除测试: 成功"
    } catch {
        Write-Host "  写入测试失败: $($_.Exception.Message)"
    }
} else {
    Write-Host "  未找到 - 尝试创建..."
    try {
        New-Item -Path $tmpDir -ItemType Directory -Force | Out-Null
        Write-Host "  已创建: $tmpDir"
    } catch {
        Write-Host "  创建失败: $($_.Exception.Message)"
    }
}

Write-Host ""
Write-Host "=== 缓存目录: $cacheDir ==="
if (Test-Path $cacheDir) {
    $info3 = Get-Item $cacheDir
    Write-Host "  存在: 是, 属性: $($info3.Attributes)"
    $cacheFiles = Get-ChildItem $cacheDir -Force -ErrorAction SilentlyContinue
    Write-Host "  包含 $($cacheFiles.Count) 个条目"
}

Write-Host ""
Write-Host "=== 测试不同位置的临时文件创建 ==="
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
        Write-Host "  成功: $loc"
    } catch {
        Write-Host "  失败: $loc - $($_.Exception.Message)"
    }
}
