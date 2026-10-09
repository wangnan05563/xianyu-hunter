# scripts/update-build-version.ps1
# 在构建打包前生成唯一 patch 号，写回 pyproject.toml 与 __init__.py
#
# 版本号格式：base.YYYYMMDD.N
#   - base：pyproject.toml [project] version 的前两段（major.minor，如 "0.4.0" -> "0.4"）
#   - YYYYMMDD：当天日期，跨天序号重置为 1
#   - N：当天递增序号，状态持久化到 .build-counter.json
#
# 写回位置：
#   1. pyproject.toml [project] version 字段（用户指定的主写入位置）
#   2. backend/xianyu_hunter/__init__.py __version__
#      为什么同步这里：build-exe.ps1 第 656 行从此读取版本号传给 Inno Setup
#      （iscc /DMyAppVersion=<version>），不同步会导致安装包名仍用旧版本
#   3. .build-counter.json 持久化 {date, seq}
#
# 用法：在 scripts/构建打包.bat 调用 build-exe.ps1 之前调用本脚本

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path "$PSScriptRoot\.."
Set-Location $repoRoot

$pyprojectPath = "pyproject.toml"
$initPath = "backend\xianyu_hunter\__init__.py"
$counterPath = ".build-counter.json"

# 无 BOM UTF-8：pyproject.toml 与 __init__.py 均为无 BOM 文件，必须保持
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

# 1. 读取当前 pyproject.toml 的 version 字段，提取 base = major.minor
if (-not (Test-Path $pyprojectPath)) { throw "未找到 $pyprojectPath" }
$tomlContent = Get-Content $pyprojectPath -Raw -Encoding UTF8

# 只匹配 [project] 段下、行首的 version 字段，避免误改 [tool.*] 段的同名字段
# (?m) 多行模式，^ 行首锚定
if ($tomlContent -match '(?m)^version\s*=\s*"([^"]+)"') {
    $currentVersion = $matches[1]
} else {
    throw "无法从 pyproject.toml [project] 段解析 version 字段"
}

# 提取 base = major.minor（丢弃 patch 及以后，由日期+序号替换）
$parts = $currentVersion -split '\.'
if ($parts.Length -lt 2) { throw "pyproject.toml version 格式异常：$currentVersion" }
$base = "$($parts[0]).$($parts[1])"

# 2. 读取计数器：当天则递增，跨天重置为 1
$today = Get-Date -Format "yyyyMMdd"
$seq = 1
if (Test-Path $counterPath) {
    try {
        $counter = Get-Content $counterPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($counter.date -eq $today -and $counter.seq) {
            $seq = [int]$counter.seq + 1
        }
        # 跨天时 seq 保持默认 1
    } catch {
        Write-Host "[WARN] .build-counter.json 解析失败，序号重置为 1：$_" -ForegroundColor Yellow
    }
}

# 3. 构造新版本号
$newVersion = "$base.$today.$seq"
Write-Host "[update-build-version] 新版本号: $newVersion (base=$base, date=$today, seq=$seq)" -ForegroundColor Cyan

# 4. 写回 pyproject.toml 的 version 字段
# 判定标准是"正则是否命中"，而非"替换前后文本是否变化"：
# 同日重跑构建时新版本号可能与当前值相同（幂等），此时替换后内容不变属正常情况，
# 若按文本比较判定会把幂等场景误报为"替换失败"（2026-10-09 实测：counter seq=1、
# 文件已是 0.4.20261009.2，脚本算出同样版本号后直接 throw 中止构建）
if ($tomlContent -notmatch '(?m)^version\s*=\s*"[^"]+"') {
    throw "pyproject.toml [project] 段未找到 version 字段，替换失败"
}
$newTomlContent = $tomlContent -replace '(?m)^version\s*=\s*"[^"]+"', "version = `"$newVersion`""
[System.IO.File]::WriteAllText((Resolve-Path $pyprojectPath).Path, $newTomlContent, $utf8NoBom)
Write-Host "[update-build-version] pyproject.toml version 已更新" -ForegroundColor Green

# 5. 写回 backend/xianyu_hunter/__init__.py 的 __version__
if (Test-Path $initPath) {
    $initContent = Get-Content $initPath -Raw -Encoding UTF8
    # 与 pyproject 同理：按正则是否命中判定，不按替换前后文本比较（幂等场景内容不变属正常）
    if ($initContent -notmatch '__version__\s*=\s*"[^"]+"') {
        Write-Host "[WARN] $initPath 中未找到 __version__，跳过同步" -ForegroundColor Yellow
    } else {
        $newInitContent = $initContent -replace '__version__\s*=\s*"[^"]+"', "__version__ = `"$newVersion`""
        [System.IO.File]::WriteAllText((Resolve-Path $initPath).Path, $newInitContent, $utf8NoBom)
        Write-Host "[update-build-version] $initPath __version__ 已同步" -ForegroundColor Green
    }
} else {
    Write-Host "[WARN] $initPath 不存在，跳过同步（build-exe.ps1 可能读取失败）" -ForegroundColor Yellow
}

# 6. 写回 .build-counter.json
$counterObj = [PSCustomObject]@{
    date = $today
    seq = $seq
    last_version = $newVersion
    updated_at = (Get-Date -Format "o")
}
$counterJson = $counterObj | ConvertTo-Json -Depth 5
[System.IO.File]::WriteAllText((Join-Path $repoRoot $counterPath), $counterJson, $utf8NoBom)
Write-Host "[update-build-version] .build-counter.json 已更新" -ForegroundColor Green

# 7. 输出版本号供调用方使用（如果需要）
Write-Output $newVersion