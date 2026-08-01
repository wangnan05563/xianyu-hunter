# scripts/build-exe.ps1
# XianyuHunter EXE 构建脚本（缓存优化版）
#
# 用法：
#   powershell -File scripts/build-exe.ps1            # 默认增量打包（首次慢，后续快）
#   powershell -File scripts/build-exe.ps1 -SkipSPA   # 跳过 SPA 构建（仅前端无变更时用）
#   powershell -File scripts/build-exe.ps1 -SkipDeps  # 跳过 pip/npm 依赖安装（仅依赖无变更时用）
#   powershell -File scripts/build-exe.ps1 -DepsOnly  # 仅验证/修复构建 venv 与 Python 依赖
#   powershell -File scripts/build-exe.ps1 -Clean     # 清理所有缓存重新下载（怀疑缓存损坏时用）
#
# 产物：dist/xianyu-hunter/ 目录 + dist/XianyuHunter-Setup-v*.exe
#
# 缓存策略（避免重复下载）：
# - .venv-build/         venv 增量更新（pip install 自动跳过已安装包）
# - frontend/node_modules/ 按 package-lock.json mtime 增量
# - .cache/playwright_browsers/  Chromium 缓存，复制到 dist
# - .cache/models/bge-small-zh-v1.5/  sentence-transformers 模型缓存，复制到 dist
#
# 构建步骤：
# 1. venv 增量更新 + 依赖安装
# 2. 锁定依赖到 requirements-lock.txt
# 3. 构建 SPA（按 lock mtime 增量）
# 4. PyInstaller 打包
# 5. 复制外置资源（SPA + 子进程脚本 + Chromium + 模型）
# 6. 制作安装包（Inno Setup）

param(
    [switch]$SkipSPA,
    [switch]$SkipDeps,
    [switch]$DepsOnly,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path "$PSScriptRoot\.."
Set-Location $repoRoot

# 清除可能干扰 pip/npm 的代理环境变量
# 为什么：用户系统可能配置了 HTTP_PROXY/HTTPS_PROXY 指向本地代理（如 VPN 客户端未启动），
# 会导致 pip 在 PEP 517 构建隔离环境中下载 setuptools/wheel 时 SSL 握手超时
# 仅影响当前脚本进程，不修改用户系统环境变量
foreach ($p in @("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy")) {
    Remove-Item Env:\$p -ErrorAction SilentlyContinue
}
# 配置 pip 使用阿里云镜像（国内访问最快，避免 PyPI 偶发超时）
# 构建隔离环境会继承此变量，确保 setuptools/wheel 也能从镜像下载
$env:PIP_INDEX_URL = "https://mirrors.aliyun.com/pypi/simple/"
$env:PIP_TRUSTED_HOST = "mirrors.aliyun.com"

# 缓存目录（独立于 dist，dist 每次删除不影响缓存）
$cacheDir = "$repoRoot\.cache"
$pwCacheDir = "$cacheDir\playwright_browsers"
$modelCacheDir = "$cacheDir\models\bge-small-zh-v1.5"
$buildVenv = ".venv-build"
$buildPython = "$buildVenv\Scripts\python.exe"
$buildVenvReadyMarker = "$buildVenv\.xh-build-ready"

function New-BuildVenv {
    if (Test-Path $buildVenv) {
        Write-Host "  删除损坏的 $buildVenv 后重建..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force $buildVenv -ErrorAction SilentlyContinue
    }
    Write-Host "  创建新 venv...（约 10 秒）"
    python -m venv $buildVenv
    if ($LASTEXITCODE -ne 0) { throw "venv 创建失败" }
}

function Test-BuildPip {
    if (-not (Test-Path $buildPython)) { return $false }
    & $buildPython -m pip --version *> $null
    return ($LASTEXITCODE -eq 0)
}

function Repair-BuildPip {
    if (-not (Test-Path $buildPython)) { return $false }
    Write-Host "  [WARN] build venv 中 pip 不可用，尝试 ensurepip 修复..." -ForegroundColor Yellow
    & $buildPython -m ensurepip --upgrade *> $null
    if ($LASTEXITCODE -ne 0) { return $false }
    return (Test-BuildPip)
}

function Invoke-BuildPip {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$PipArgs,
        [Parameter(Mandatory = $true)]
        [string]$FailureMessage,
        [switch]$RetryAfterRebuild
    )

    & $buildPython -m pip @PipArgs
    if ($LASTEXITCODE -eq 0) { return }

    if ($RetryAfterRebuild) {
        Write-Host "  [WARN] pip 命令失败，重建 build venv 后重试一次..." -ForegroundColor Yellow
        New-BuildVenv
        if (-not (Test-BuildPip)) {
            & $buildPython -m ensurepip --upgrade *> $null
            if (-not (Test-BuildPip)) { throw "build venv 中 pip 不可用" }
        }
        & $buildPython -m pip @PipArgs
        if ($LASTEXITCODE -eq 0) { return }
    }

    throw $FailureMessage
}

# -Clean：清理所有缓存
if ($Clean) {
    Write-Host "[Clean] 清理所有缓存..." -ForegroundColor Yellow
    foreach ($p in @(".venv-build", "frontend\node_modules", $cacheDir, "dist")) {
        if (Test-Path $p) {
            Write-Host "  删除 $p"
            Remove-Item -Recurse -Force $p -ErrorAction SilentlyContinue
        }
    }
}

# 创建缓存目录
New-Item -ItemType Directory -Force $cacheDir | Out-Null

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  闲鱼猎人 EXE 构建" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "仓库目录: $repoRoot"
Write-Host "缓存目录: $cacheDir"
if ($SkipDeps) { Write-Host "模式: SkipDeps（跳过依赖安装）" }
if ($SkipSPA)  { Write-Host "模式: SkipSPA（跳过 SPA 构建）" }
if ($DepsOnly) { Write-Host "模式: DepsOnly（仅验证构建依赖）" }

# ============== 1. venv 增量更新 + 依赖安装 ==============
Write-Host "`n[1/6] 准备构建 venv..." -ForegroundColor Yellow
# 为什么不每次删除重建：pip install 对已安装包会自动跳过，删除重建会让所有包重新解压
# 仅在 venv 不存在或 -Clean 时创建
if (-not (Test-Path $buildPython)) {
    Write-Host "  venv 不存在"
    New-BuildVenv
} else {
    Write-Host "  venv 已存在，增量更新" -ForegroundColor DarkGray
}

if ((-not $SkipDeps) -and (Test-Path $buildPython) -and (-not (Test-Path $buildVenvReadyMarker))) {
    Write-Host "  [WARN] build venv 缺少健康标记，可能是上次构建中断留下的半成品，重建..." -ForegroundColor Yellow
    New-BuildVenv
}

if (-not (Test-BuildPip)) {
    if (-not (Repair-BuildPip)) {
        Write-Host "  [WARN] ensurepip 修复失败，重建 build venv..." -ForegroundColor Yellow
        New-BuildVenv
        if (-not (Test-BuildPip)) {
            & $buildPython -m ensurepip --upgrade *> $null
            if (-not (Test-BuildPip)) { throw "build venv 中 pip 不可用" }
        }
    }
}

if (-not $SkipDeps) {
    Write-Host "  安装项目依赖（pip 自动跳过已安装包）..."
    Invoke-BuildPip -PipArgs @("install", "-e", ".", "--quiet") -FailureMessage "项目依赖安装失败" -RetryAfterRebuild

    Invoke-BuildPip -PipArgs @("install", "pyinstaller", "--quiet") -FailureMessage "PyInstaller 安装失败"

    # 系统托盘可选依赖：pystray + pillow
    # launcher.py 中 try/except 导入，未安装时控制台模式仍可用
    & $buildPython -m pip install pystray pillow --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [WARN] pystray/pillow 安装失败，托盘功能将不可用" -ForegroundColor Red
    }
    Set-Content -Path $buildVenvReadyMarker -Value (Get-Date -Format o) -Encoding UTF8
} else {
    Write-Host "  -SkipDeps 已指定，跳过依赖安装" -ForegroundColor DarkGray
}

# 验证关键依赖存在（即使 -SkipDeps 也要确保）
if (-not (Test-Path ".venv-build\Scripts\pyinstaller.exe")) {
    Write-Host "  [WARN] PyInstaller 未安装，强制安装..." -ForegroundColor Red
    Invoke-BuildPip -PipArgs @("install", "pyinstaller", "--quiet") -FailureMessage "PyInstaller 安装失败"
}

# ============== 2. 锁定依赖 ==============
Write-Host "`n[2/6] 锁定依赖..." -ForegroundColor Yellow
& $buildPython -m pip freeze > requirements-lock.txt
Write-Host "  依赖已锁定到 requirements-lock.txt"

if ($DepsOnly) {
    Write-Host "`n[DepsOnly] 构建 venv 与 Python 依赖验证完成" -ForegroundColor Green
    exit 0
}

# ============== 3. 构建 SPA ==============
# 默认每次都重建：避免前端源码已修改但 SPA 产物未更新导致打包后行为不一致
# 用 -SkipSPA 跳过（仅当确信前端无变更时使用，可省 1-3 分钟）
Write-Host "`n[3/6] 构建 SPA..." -ForegroundColor Yellow
$spaIndex = "src\xianyu_hunter\web\static\spa\index.html"
if ($SkipSPA -and (Test-Path $spaIndex)) {
    Write-Host "  SPA 已存在且 -SkipSPA 已指定，跳过构建" -ForegroundColor DarkGray
} else {
    # Node 版本检测：vite 5 + ??= 运算符需要 Node 18+
    # 为什么检测：用户机器可能装了多个 Node 版本，PATH 指向旧版会导致构建静默失败
    # 优先用 scripts/node-config.json 中配置的 node 路径，避免 PATH 中旧版优先（陷阱 5）
    $nodeConfigPath = Join-Path $PSScriptRoot "node-config.json"
    $configuredNodeExe = $null
    if (Test-Path $nodeConfigPath) {
        $nodeConfig = Get-Content $nodeConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
        # 遍历 search_paths 找到第一个存在的 node.exe
        foreach ($p in $nodeConfig.node.search_paths) {
            $expanded = [System.Environment]::ExpandEnvironmentVariables($p)
            if (Test-Path $expanded) {
                $configuredNodeExe = $expanded
                break
            }
        }
    }

    if ($configuredNodeExe) {
        # 把配置的 node 目录前置到 PATH，确保后续 npm/node 调用都走指定版本
        $nodeDir = Split-Path $configuredNodeExe -Parent
        $env:Path = "$nodeDir;$env:Path"
        Write-Host "  使用配置的 Node: $configuredNodeExe" -ForegroundColor DarkGray
        $nodeVersion = (& $configuredNodeExe --version 2>$null) -replace '[v\n\r]', ''
    } else {
        # 回退到 PATH 中的 node（无配置时的兜底方案）
        $nodeVersion = (node --version 2>$null) -replace '[v\n\r]', ''
    }

    if ($nodeVersion) {
        $nodeMajor = [int]($nodeVersion.Split('.')[0])
        if ($nodeMajor -lt 18) {
            Write-Host "  [ERROR] Node $nodeVersion 版本过低，vite 5 需要 Node 18+" -ForegroundColor Red
            Write-Host "  当前 PATH 中的 Node：$((Get-Command node).Source)" -ForegroundColor Red
            throw "Node 版本过低（$nodeVersion），需要 18+"
        }
        Write-Host "  Node 版本：$nodeVersion" -ForegroundColor DarkGray
    } else {
        throw "未检测到 Node.js，请安装 Node 18+ 后重试（或配置 scripts\node-config.json）"
    }

    Push-Location frontend

    # node_modules 增量：比较 package-lock.json 与 .install-stamp 的 mtime
    # 为什么不用 npm ci 每次重装：npm ci 会删除 node_modules 重新解压，耗时 1-3 分钟
    # 仅在 lock 文件变化时才 npm ci，否则直接 npm run build
    $lockFile = "package-lock.json"
    $stampFile = "node_modules\.install-stamp"
    $needInstall = $false

    if (-not (Test-Path "node_modules")) {
        $needInstall = $true
        Write-Host "  node_modules 不存在，需要安装"
    } elseif (-not (Test-Path $stampFile)) {
        $needInstall = $true
        Write-Host "  .install-stamp 不存在，需要重装"
    } elseif (Test-Path $lockFile) {
        $lockMtime = (Get-Item $lockFile).LastWriteTime
        $stampMtime = (Get-Item $stampFile).LastWriteTime
        if ($lockMtime -gt $stampMtime) {
            $needInstall = $true
            Write-Host "  package-lock.json 已变更，需要重新安装依赖"
        } else {
            Write-Host "  node_modules 已是最新（lock 未变），跳过安装" -ForegroundColor DarkGray
        }
    }

    if ($needInstall) {
        Write-Host "  预计耗时：约 1-3 分钟" -ForegroundColor DarkGray
        if (Test-Path $lockFile) {
            npm ci
        } else {
            npm install
        }
        if ($LASTEXITCODE -ne 0) { Pop-Location; throw "npm install 失败" }
        # 写入安装时间戳（用于下次增量判断）
        Set-Content -Path $stampFile -Value (Get-Date -Format "o") -Encoding UTF8
    }

    Write-Host "  构建 SPA..."
    npm run build
    if ($LASTEXITCODE -ne 0) { Pop-Location; throw "SPA 构建失败" }
    Pop-Location
    Write-Host "  SPA 构建完成"
}

# ============== 4. PyInstaller 打包 ==============
Write-Host "`n[4/6] 运行 PyInstaller 打包..." -ForegroundColor Yellow
Write-Host "  预计耗时：约 1-3 分钟" -ForegroundColor DarkGray
# 清理旧产物（dist 每次重建，但缓存独立在 .cache/ 不受影响）
if (Test-Path "dist\xianyu-hunter") {
    Remove-Item -Recurse -Force "dist\xianyu-hunter"
}
& .venv-build\Scripts\pyinstaller xianyu-hunter.spec --noconfirm
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 打包失败" }
Write-Host "  PyInstaller 打包完成"

# ============== 4.5 修复 PyInstaller 收集的 sentence_transformers 包完整性 ==============
Write-Host "`n[4.5] 修复 sentence_transformers 包完整性..." -ForegroundColor Yellow
& .venv-build\Scripts\python "$PSScriptRoot\sync-sentence-transformers.py"
if ($LASTEXITCODE -ne 0) { Write-Host "  [WARN] sentence_transformers 修复失败，继续构建" -ForegroundColor Yellow }
else { Write-Host "  sentence_transformers 包完整性修复完成" -ForegroundColor Green }

# ============== 5. 复制外置资源 ==============
Write-Host "`n[5/6] 复制外置资源..." -ForegroundColor Yellow

# 5.1 静态资源（含 SPA + icons，外置到 exe 同级 static 目录）
# app.py 在打包模式下通过 get_app_dir() / "static" 定位此目录
Write-Host "  [5.1] 复制静态资源（SPA + icons）..."
Copy-Item -Recurse -Force "src\xianyu_hunter\web\static" "dist\xianyu-hunter\static"

# 5.2 子进程脚本（auth_helper.py / browser_login.py）
# 为什么需要：browser_login.py / unified_login.py / auth_manager.py 通过 get_app_dir()/"scripts" 定位这些脚本
# PyInstaller 不收集 scripts/ 目录（仅打包 src/xianyu_hunter/），必须显式复制
# 仅复制运行时实际调用的子进程脚本，避免打包测试脚本（test_*.py / perf_test.py 等）
Write-Host "  [5.2] 复制子进程脚本（auth_helper, browser_login）..."
$scriptsTarget = "dist\xianyu-hunter\scripts"
New-Item -ItemType Directory -Force $scriptsTarget | Out-Null
foreach ($script in @("browser_login.py", "auth_helper.py")) {
    $src = "scripts\$script"
    if (Test-Path $src) {
        Copy-Item -Force $src $scriptsTarget
    } else {
        Write-Host "  [WARN] 缺少 $src，浏览器登录/二维码登录功能将不可用" -ForegroundColor Red
    }
}

# 5.3 配置文件（menu_registry.yaml 等只读配置，随安装包分发）
# 为什么需要：menu_manager.py 通过 get_app_dir()/"config"/"menu_registry.yaml" 定位
# 打包后 get_app_dir() 返回 exe 所在目录，config/ 需复制到 exe 同级
Write-Host "  [5.3] 复制配置文件（menu_registry.yaml）..."
$configTarget = "dist\xianyu-hunter\config"
New-Item -ItemType Directory -Force $configTarget | Out-Null
if (Test-Path "config\menu_registry.yaml") {
    Copy-Item -Force "config\menu_registry.yaml" $configTarget
} else {
    Write-Host "  [WARN] 缺少 config\menu_registry.yaml，菜单配置功能将不可用" -ForegroundColor Red
}

# 5.4 Playwright Chromium（从缓存复制，避免重复下载 ~150MB）
# 为什么用缓存：dist 每次打包都会删除重建，直接下载到 dist 会每次重下
# 缓存到 .cache/playwright_browsers/，复制到 dist/xianyu-hunter/playwright_browsers/
Write-Host "  [5.4] Playwright Chromium..." -ForegroundColor Yellow
$pwTarget = "dist\xianyu-hunter\playwright_browsers"
if (Test-Path "$pwCacheDir\chromium-*") {
    Write-Host "  从缓存复制 Chromium...（约 10-30 秒）"
    Copy-Item -Recurse -Force $pwCacheDir $pwTarget
    Write-Host "  Chromium 已从缓存复制到 $pwTarget"
} else {
    Write-Host "  缓存不存在，下载 Chromium...（下载约 150MB）"
    $env:PLAYWRIGHT_BROWSERS_PATH = $pwCacheDir
    & .venv-build\Scripts\playwright install chromium
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [WARN] Playwright Chromium 安装失败" -ForegroundColor Red
    } else {
        Write-Host "  Chromium 已下载到缓存 $pwCacheDir"
        # 复制到 dist
        Copy-Item -Recurse -Force $pwCacheDir $pwTarget
        Write-Host "  Chromium 已复制到 $pwTarget"
    }
    Remove-Item Env:\PLAYWRIGHT_BROWSERS_PATH -ErrorAction SilentlyContinue
}

# 5.5 sentence-transformers 模型（从缓存复制，避免重复下载 ~100MB）
# 为什么用缓存：同上，dist 每次重建会导致重新下载
# 缓存到 .cache/models/bge-small-zh-v1.5/，复制到 dist/xianyu-hunter/models/
Write-Host "  [5.5] sentence-transformers 模型..." -ForegroundColor Yellow
$modelTarget = "dist\xianyu-hunter\models\bge-small-zh-v1.5"
if (Test-Path "$modelCacheDir\config.json") {
    Write-Host "  从缓存复制模型...（约 5-15 秒）"
    New-Item -ItemType Directory -Force (Split-Path $modelTarget) | Out-Null
    Copy-Item -Recurse -Force $modelCacheDir $modelTarget
    Write-Host "  模型已从缓存复制到 $modelTarget"
} else {
    Write-Host "  缓存不存在，下载模型...（下载约 100MB）"
    # 设置 HF 镜像，避免国内访问 huggingface.co 超时
    $env:HF_ENDPOINT = "https://hf-mirror.com"
    New-Item -ItemType Directory -Force $modelCacheDir | Out-Null
    & .venv-build\Scripts\python -c @"
import os
os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')
from sentence_transformers import SentenceTransformer
m = SentenceTransformer('BAAI/bge-small-zh-v1.5')
m.save(r'$modelCacheDir')
print('Model saved to $modelCacheDir')
"@
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [WARN] 模型预置失败（首次运行将联网下载）" -ForegroundColor Red
    } else {
        Write-Host "  模型已下载到缓存 $modelCacheDir"
        # 复制到 dist
        New-Item -ItemType Directory -Force (Split-Path $modelTarget) | Out-Null
        Copy-Item -Recurse -Force $modelCacheDir $modelTarget
        Write-Host "  模型已复制到 $modelTarget"
    }
}

# 5.6 敏感信息扫描（防御性：确保 API Key / .env / .secrets.json 未被打包）
# 为什么需要：即使 spec 不收集 .env、前面的步骤不复制 .env，
# 仍需在打包产物中扫描确认，防止未来误改 spec 或新增依赖间接带入敏感信息
Write-Host "  [5.6] 扫描敏感信息..."
$distRoot = "dist\xianyu-hunter"

# 5.6.1 删除可能存在的敏感文件（防御性，即使前面步骤不应复制它们）
foreach ($sensitiveFile in @(".env", ".env.local", ".secrets.json")) {
    $sensitivePath = Join-Path $distRoot $sensitiveFile
    if (Test-Path $sensitivePath) {
        Write-Host "    [WARN] 发现敏感文件 $sensitiveFile，已删除" -ForegroundColor Red
        Remove-Item -Force $sensitivePath
    }
}

# 5.6.2 扫描打包产物中是否有 API Key 痕迹
# 扫描模式：sk- 开头（OpenAI/DeepSeek 标准 Key 前缀）、__MIGRATED_TO_KEYRING__ 占位符
# 注意：仅扫描项目级文件（exe 同级 + config/ + scripts/ + static/），
# 不扫描 _internal/（第三方库 dist-info 的 RECORD 文件含 sha256 hash，
#   如 torch 的 "sha256=...LJsk-trKzjJE0tUMSAsSlfOiR_3c" 会匹配 sk-[A-z0-9]{20,} 误报）
$scanRootFiles = $distRoot
$scanSubDirs = @("$distRoot\config", "$distRoot\scripts", "$distRoot\static")
$leakFound = $false
# exe 同级文件不递归（递归会进入 _internal/ 第三方库目录）
$scanTargets = @(@{ Path = $scanRootFiles; Recurse = $false })
foreach ($d in $scanSubDirs) {
    $scanTargets += @(@{ Path = $d; Recurse = $true })
}
foreach ($target in $scanTargets) {
    if (-not (Test-Path $target.Path)) { continue }
    if ($target.Recurse) {
        $files = Get-ChildItem -Path $target.Path -File -Recurse -ErrorAction SilentlyContinue
    } else {
        $files = Get-ChildItem -Path $target.Path -File -ErrorAction SilentlyContinue
    }
    foreach ($file in $files) {
        # 跳过二进制文件（exe/dll/pak 等），只扫描文本文件
        $ext = $file.Extension.ToLower()
        if ($ext -in @(".exe", ".dll", ".pak", ".bin", ".dat", ".node", ".pyd", ".so")) { continue }
        try {
            $content = Get-Content $file.FullName -Raw -Encoding UTF8 -ErrorAction Stop
            if ($content -match 'sk-[A-Za-z0-9]{20,}' -or $content -match '__MIGRATED_TO_KEYRING__') {
                Write-Host "    [ERROR] 在 $($file.FullName) 中发现疑似 API Key 痕迹" -ForegroundColor Red
                $leakFound = $true
            }
        } catch {
            # 读取失败的文件（如编码问题）跳过
        }
    }
}
if ($leakFound) {
    throw "打包产物中检测到 API Key 痕迹，已中止构建。请检查 spec 文件和复制步骤。"
}
Write-Host "    敏感信息扫描通过（无 API Key 痕迹）" -ForegroundColor Green

# ============== 6. 制作安装包（Inno Setup） ==============
Write-Host "`n[6/6] 构建安装包（Inno Setup）..." -ForegroundColor Yellow

# 6.1 查找 iscc.exe（Inno Setup 编译器）
function Find-ISCC {
    $cmd = Get-Command iscc -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $paths = @(
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        "$env:USERPROFILE\AppData\Local\Programs\Inno Setup 6\ISCC.exe"
    )
    foreach ($p in $paths) { if (Test-Path $p) { return $p } }
    return $null
}

function Refresh-Path {
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
}

$iscc = Find-ISCC

# 6.2 自动安装 Inno Setup（如未安装）
if (-not $iscc) {
    Write-Host "  Inno Setup 未安装，尝试自动安装..." -ForegroundColor Cyan

    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host "  使用 winget 安装..." -ForegroundColor DarkGray
        winget install --id JRSoftware.InnoSetup --silent --accept-package-agreements --accept-source-agreements
        Refresh-Path
        $iscc = Find-ISCC
    }

    if (-not $iscc) {
        Write-Host "  直接下载 Inno Setup 安装包..." -ForegroundColor DarkGray
        $installerUrl = "https://jrsoftware.org/download.php/is.exe"
        $installerFile = "$env:TEMP\innosetup-install.exe"
        try {
            Invoke-WebRequest -Uri $installerUrl -OutFile $installerFile -UseBasicParsing
            Start-Process -FilePath $installerFile -ArgumentList "/VERYSILENT","/SUPPRESSMSGBOXES","/NORESTART","/SP-" -Wait -NoNewWindow
            Refresh-Path
            $iscc = Find-ISCC
        } catch {
            Write-Host "  [WARN] 下载安装失败：$_" -ForegroundColor Red
        } finally {
            if (Test-Path $installerFile) { Remove-Item $installerFile -Force -ErrorAction SilentlyContinue }
        }
    }
}

# 6.3 自动创建 installer.iss（如不存在）
if ($iscc -and -not (Test-Path "installer.iss")) {
    Write-Host "  installer.iss 不存在，自动创建..." -ForegroundColor Cyan
    $issTemplate = @"
; Auto-generated by build-exe.ps1
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0.0"
#endif
[Setup]
AppName=XianyuHunter
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\XianyuHunter
DefaultGroupName=XianyuHunter
UninstallDisplayIcon={app}\xianyu-hunter.exe
OutputDir=dist
OutputBaseFilename=XianyuHunter-Setup-v{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin
DisableProgramGroupPage=yes
[Tasks]
Name: "desktopicon"; Description: "Create desktop shortcut"; GroupDescription: "Additional:"
[Files]
Source: "dist\xianyu-hunter\*"; DestDir: "{app}"; Excludes: "*.log,data\*"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\XianyuHunter"; Filename: "{app}\xianyu-hunter.exe"
Name: "{commondesktop}\XianyuHunter"; Filename: "{app}\xianyu-hunter.exe"; Tasks: desktopicon
[Run]
Filename: "{app}\xianyu-hunter.exe"; Description: "Launch XianyuHunter"; Flags: nowait postinstall skipifsilent
"@
    # Inno Setup 编译器（ISCC）需要 UTF-8 BOM 才能正确解析模板中的中文
    [System.IO.File]::WriteAllText("installer.iss", $issTemplate, (New-Object System.Text.UTF8Encoding($true)))
}

# 6.4 编译安装包
if (-not $iscc) {
    Write-Host "  [WARN] Inno Setup 不可用，跳过安装包制作" -ForegroundColor Red
    Write-Host "  手动安装：https://jrsoftware.org/isdl.php" -ForegroundColor DarkGray
} else {
    # 从 __init__.py 读取版本号
    $initFile = "src\xianyu_hunter\__init__.py"
    $version = "0.0.0.0"
    if (Test-Path $initFile) {
        $line = Get-Content $initFile | Where-Object { $_ -match '__version__' } | Select-Object -First 1
        if ($line -match '"([^"]+)"') { $version = $matches[1] }
    }
    Write-Host "  版本号: $version"
    Write-Host "  编译安装包..."
    & $iscc /DMyAppVersion=$version installer.iss
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [WARN] 安装包编译失败" -ForegroundColor Red
    } else {
        $setupExe = "dist\XianyuHunter-Setup-v$version.exe"
        Write-Host "  安装包已生成：$setupExe" -ForegroundColor Green
    }
}

# ============== 完成 ==============
$distDir = "dist\xianyu-hunter"
$size = (Get-ChildItem -Recurse $distDir | Measure-Object -Property Length -Sum).Sum / 1MB
Write-Host "`n========================================" -ForegroundColor Green
Write-Host "  构建完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "  产物目录: $distDir"
Write-Host ("  产物大小: {0:N1} MB" -f $size)
Write-Host "  EXE 路径: $distDir\xianyu-hunter.exe"
Write-Host "========================================" -ForegroundColor Green
