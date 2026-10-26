#Requires -Version 5.1
<#
.SYNOPSIS
    XianyuHunter 一键构建 + 打包 + 发布到 GitHub Releases（配置驱动，无硬编码）
.DESCRIPTION
    读取 config.publish.json：先执行构建流水线（更新版本号 -> PyInstaller 打包 -> Inno Setup 安装包），
    再定位产物（优先 release\XianyuHunter-Setup-v<VER>.exe，缺失则把 release\xianyu-hunter\ 压缩为 zip），
    推导版本号、生成/复用发布说明，最后调用通用发布器 publish-release.py 上传。
    所有项目名 / 路径 / 版本 / token 均来自配置或环境变量，脚本本身零硬编码。
    用法：
      scripts\一键发布.bat                      （构建并真实发布）
      scripts\一键发布.bat -SkipBuild          （跳过构建，直接发布已有产物）
      set GH_DRY_RUN=1 && scripts\一键发布.bat （只打印将要执行的动作，不真实上传）
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$ConfigPath,
    [Parameter(Mandatory=$true)][string]$RepoRoot,
    [switch]$SkipBuild,
    [switch]$DryRun
)

# 支持通过环境变量控制（参考 18_comparePakage 一键发布.bat 的用法）
if ($env:GH_DRY_RUN -eq '1') { $DryRun = $true }
if ($env:XH_SKIP_BUILD -eq '1') { $SkipBuild = $true }

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# ---- 与 .bat chcp 65001 匹配（UTF-8 输出） ----
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

# ---- 工具函数 ----
function Resolve-Python {
    $cands = if ($cfg.runtime -and $cfg.runtime.python_candidates) { $cfg.runtime.python_candidates } else { @() }
    foreach ($c in $cands) {
        $p = [System.Environment]::ExpandEnvironmentVariables($c)
        if (Test-Path $p) { return $p }
    }
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $cmd = Get-Command python3 -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

function Get-AssetVersion($assetPath) {
    $name = [System.IO.Path]::GetFileNameWithoutExtension($assetPath)
    if ($name -match '^XianyuHunter-Setup-v(.+)$') { return $matches[1] }
    if ($name -match '^XianyuHunter-(.+)$') { return $matches[1] }
    return $null
}

function Get-PyprojectVersion($root) {
    $pj = Join-Path $root "pyproject.toml"
    if (-not (Test-Path $pj)) { return $null }
    $c = Get-Content -Raw -Encoding UTF8 $pj
    if ($c -match '(?m)^version\s*=\s*"([^"]+)"') { return $matches[1] }
    return $null
}

# ---- 配置加载 ----
if (-not (Test-Path $ConfigPath)) { Write-Error "config 未找到: $ConfigPath"; exit 1 }
$cfg = Get-Content -Raw -Encoding UTF8 $ConfigPath | ConvertFrom-Json
$rel = $cfg.github_release
if (-not $rel -or $rel.enabled -ne $true) {
    Write-Host "[build-publish] github_release 未启用（enabled != true），跳过发布" -ForegroundColor Yellow
    exit 0
}

# ---- 解析 python（配置驱动，绝不硬编码运行时路径；陷阱 57） ----
$py = Resolve-Python
if (-not $py) { Write-Error "[build-publish] 未找到 python（请配置 runtime.python_candidates 或安装 python）"; exit 1 }
Write-Host "[build-publish] python: $py" -ForegroundColor Cyan
# 把 python 所在目录前置到 PATH，使构建脚本内的 `python` 命中同一解释器
$pyDir = Split-Path $py
$env:PATH = "$pyDir;$env:PATH"

Push-Location $RepoRoot
try {
    # ---- 1) 构建流水线 ----
    if (-not $SkipBuild) {
        if ($cfg.build_pipeline -and $cfg.build_pipeline.steps) {
            $i = 0
            foreach ($step in $cfg.build_pipeline.steps) {
                $i++
                $cmd = $step.command
                if (-not $cmd) { continue }
                $cmd = $cmd -replace '__SCRIPTS__', $PSScriptRoot
                Write-Host "[build-publish] [$i/$($cfg.build_pipeline.steps.Count)] $($step.name)" -ForegroundColor Cyan
                Write-Host "  > $cmd"
                Invoke-Expression $cmd
                if ($LASTEXITCODE -ne 0) {
                    $onFail = if ($step.on_fail) { $step.on_fail } else { "stop" }
                    if ($onFail -eq "skip") { Write-Warning "  step failed, skip"; continue }
                    if ($onFail -eq "warn") { Write-Warning "  step failed, continue"; continue }
                    Write-Error "[build-publish] 构建步骤失败 (exit $LASTEXITCODE): $($step.name)"
                }
            }
        } else {
            Write-Host "[build-publish] 未配置 build_pipeline.steps，跳过构建阶段" -ForegroundColor Yellow
        }
    } else {
        Write-Host "[build-publish] -SkipBuild 已指定，跳过构建阶段" -ForegroundColor Yellow
    }

    # ---- 2) 定位产物（优先安装包，缺失则压缩 dir 构建） ----
    $adir = $rel.asset.dir
    $glob = $rel.asset.glob
    $excl = if ($rel.asset.exclude_patterns) { $rel.asset.exclude_patterns } else { @() }
    $assetDir = Join-Path $RepoRoot $adir
    if (-not (Test-Path $assetDir)) { Write-Error "[build-publish] 资产目录不存在: $assetDir"; exit 1 }
    $matches = Get-ChildItem -Path $assetDir -File | Where-Object {
        $n = $_.Name
        ($n -like $glob) -and (-not ($excl | Where-Object { $n -like $_ -or $n.Contains($_) }))
    } | Sort-Object LastWriteTime -Descending
    $asset = $null
    if ($matches -and $matches.Count -gt 0) {
        $asset = $matches[0].FullName
    } else {
        # 回退：把 dir 模式产物压缩为 zip（陷阱 49：优先 Compress-Archive）
        Write-Host "[build-publish] 未找到安装包，尝试把 release\xianyu-hunter\ 压缩为 zip..." -ForegroundColor Yellow
        $ver = Get-PyprojectVersion -root $RepoRoot
        if (-not $ver) { Write-Error "[build-publish] 无法读取版本号（pyproject.toml）"; exit 1 }
        $zipName = "XianyuHunter-$ver.zip"
        $zipPath = Join-Path $assetDir $zipName
        $srcDir = Join-Path $RepoRoot "release\xianyu-hunter"
        if (-not (Test-Path $srcDir)) { Write-Error "[build-publish] 未找到构建产物: $srcDir"; exit 1 }
        if (-not (Test-Path $zipPath)) {
            Compress-Archive -Path (Join-Path $srcDir "*") -DestinationPath $zipPath -Force
        }
        $asset = $zipPath
    }
    Write-Host "[build-publish] 资产: $asset" -ForegroundColor Green

    # ---- 3) 推导版本 ----
    $ver = Get-AssetVersion $asset
    if (-not $ver) { $ver = Get-PyprojectVersion -root $RepoRoot }
    if (-not $ver) { Write-Error "[build-publish] 无法推导版本号: $asset"; exit 1 }
    Write-Host "[build-publish] 版本: $ver"

    # ---- 4) 发布说明（<VER> 模板；缺失则 git log 自动生成） ----
    $notes = $null
    if ($rel.notes -and $rel.notes.path_template) {
        $notesPath = Join-Path $RepoRoot ($rel.notes.path_template -replace "<VER>", $ver)
        if (-not (Test-Path $notesPath)) {
            if ($rel.notes.auto_generate -ne $false) {
                $auto = Join-Path $RepoRoot (($rel.notes.path_template -replace "<VER>", $ver) -replace "\.md$", ".auto.md")
                $logArgs = if ($rel.notes.auto_generate_git_log) { $rel.notes.auto_generate_git_log } else { "--no-merges --oneline -20" }
                $log = git -C $RepoRoot log @($logArgs -split " ") 2>$null
                Set-Content -Path $auto -Encoding UTF8 -Value ("# Release $ver`n`n（自动生成的发布说明，来自 git 提交记录；正式发布前请替换为正式说明。）`n`n" + ($log -join "`n"))
                $notesPath = $auto
                Write-Host "[build-publish] 自动生成说明: $notesPath" -ForegroundColor Yellow
            } else {
                Write-Error "[build-publish] 说明文件不存在且未启用 auto_generate: $notesPath"; exit 1
            }
        }
        $notes = $notesPath
    } else {
        Write-Error "[build-publish] 未配置 github_release.notes.path_template"; exit 1
    }
    Write-Host "[build-publish] 说明: $notes"

    # ---- 5) 发布（委托通用脚本；token 在其内部按 env > .env > git credential 解析） ----
    $pub = Join-Path $RepoRoot $rel.publish_script
    if (-not (Test-Path $pub)) { Write-Error "[build-publish] 发布脚本不存在: $pub"; exit 1 }
    $display = [System.IO.Path]::GetFileName($asset)
    $env:GH_TAG = $ver
    if ($rel.repo) { $env:GH_REPO = $rel.repo }
    if ($DryRun -or $rel.dry_run) { $env:GH_DRY_RUN = "1" }
    if ($rel.draft) { $env:GH_DRAFT = "1" }
    if ($rel.prerelease) { $env:GH_PRERELEASE = "1" }
    Write-Host "[build-publish] 发布中 (dry_run=$($DryRun -or $rel.dry_run))..." -ForegroundColor Cyan
    & $py $pub $asset $notes $display
    if ($LASTEXITCODE -ne 0) { Write-Error "[build-publish] 发布失败 (exit $LASTEXITCODE)"; exit 1 }
    Write-Host "[build-publish] 发布完成" -ForegroundColor Green
} finally {
    Pop-Location
}
exit 0
