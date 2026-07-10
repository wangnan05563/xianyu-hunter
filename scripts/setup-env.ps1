<#
.SYNOPSIS
    XianyuHunter 一键环境配置脚本
.DESCRIPTION
    在新 PC 上自动检测、下载、安装项目所需的全部依赖，并完成项目初始化。
    覆盖：Python 3.12+ / Node.js 24+ / Git / Playwright Chromium / 前端构建 / 配置文件 / 数据目录。
    默认仅安装缺失项，已存在且版本达标的依赖会跳过，可重复执行。
.PARAMETER SkipSystem
    跳过系统级软件（Python/Node.js/Git）的安装，仅做项目级初始化。
    适用场景：已手动安装好运行时，或无管理员权限无法安装系统软件。
.PARAMETER SkipFrontend
    跳过前端依赖安装与构建。适用场景：仅调试后端，不需要 SPA 产物。
.PARAMETER SkipPlaywright
    跳过 Playwright Chromium 安装。适用场景：离线环境或已预装浏览器。
.PARAMETER StartService
    全部完成后自动启动 Web 服务（含调度器）。
.PARAMETER Force
    强制重新安装 Python 依赖（pip install --force-reinstall）。
.EXAMPLE
    .\setup-env.ps1
    标准执行：检测并补齐缺失依赖，完成项目初始化。
.EXAMPLE
    .\setup-env.ps1 -StartService
    初始化完成后立即启动 Web 服务。
.EXAMPLE
    .\setup-env.ps1 -SkipSystem
    跳过系统级软件安装，仅做项目内初始化（适用于运行时已就绪的环境）。
.NOTES
    作者：XianyuHunter
    适用：Windows 10/11 x64，PowerShell 5.1+
#>
#Requires -Version 5.0

[CmdletBinding()]
param(
    [switch]$SkipSystem,
    [switch]$SkipFrontend,
    [switch]$SkipPlaywright,
    [switch]$StartService,
    [switch]$Force
)

# 强制遇错即停：脚本任一步骤失败应立即暴露，避免后续步骤在错误状态下继续执行
$ErrorActionPreference = "Stop"
# 进度反馈统一前缀，便于在大量输出中快速定位脚本日志
$Script:StepPrefix = "[XH-Setup]"

# ============================================================
# 工具函数
# ============================================================

function Write-Step {
    # 阶段性进度提示，使用蓝色与普通输出区分
    param([string]$Message)
    Write-Host "$StepPrefix $Message" -ForegroundColor Cyan
}

function Write-OK {
    param([string]$Message)
    Write-Host "$StepPrefix   [OK] $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "$StepPrefix   [WARN] $Message" -ForegroundColor Yellow
}

function Write-Err {
    param([string]$Message)
    Write-Host "$StepPrefix   [FAIL] $Message" -ForegroundColor Red
}

function Test-CommandAvailable {
    # 通过 Get-Command 检测命令是否可用，比 try/catch 更轻量
    param([string]$Name)
    # 空值前置检查：Get-Command 的参数验证会抛出终止错误，-ErrorAction 无法抑制
    if ([string]::IsNullOrWhiteSpace($Name)) { return $false }
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Get-PythonVersion {
    # 解析 `python --version` 输出为 Version 对象，便于后续版本比较
    param([string]$ExePath)
    try {
        $output = & $ExePath --version 2>&1
        # Python 3.12+ 输出形如 "Python 3.12.1"，正则提取主版本号
        if ($output -match 'Python\s+(\d+)\.(\d+)\.(\d+)') {
            return [PSCustomObject]@{
                Major = [int]$Matches[1]
                Minor = [int]$Matches[2]
                Patch = [int]$Matches[3]
            }
        }
    } catch {
        # 路径不存在或执行失败时返回 null，让调用方走降级逻辑
    }
    return $null
}

function Get-NodeVersion {
    param([string]$ExePath)
    try {
        $output = & $ExePath --version 2>&1
        # Node.js 输出形如 "v24.10.0"，前缀 v 需剥离
        if ($output -match 'v?(\d+)\.(\d+)\.(\d+)') {
            return [PSCustomObject]@{
                Major = [int]$Matches[1]
                Minor = [int]$Matches[2]
                Patch = [int]$Matches[3]
            }
        }
    } catch {
        # 路径不存在或执行失败时返回 null，让调用方走降级逻辑
    }
    return $null
}

function Test-VersionSatisfy {
    # 语义版本比较：仅比较 Major.Minor，Patch 不作为门槛
    param($Current, [int]$MinMajor, [int]$MinMinor)
    if ($null -eq $Current) { return $false }
    if ($Current.Major -gt $MinMajor) { return $true }
    if ($Current.Major -lt $MinMajor) { return $false }
    return $Current.Minor -ge $MinMinor
}

function Test-WingetAvailable {
    # winget 是 Win10 1809+ 自带的 App Installer 组件，作为系统级软件安装的首选渠道
    # Test-CommandAvailable 已封装 Get-Command 检测，无需重复调用
    return (Test-CommandAvailable 'winget')
}

function Install-WithWinget {
    <#
        通过 winget 安装指定包。
        winget 自身会处理下载、静默安装、PATH 注入，无需脚本介入细节。
        返回 $true 表示安装成功或已安装；$false 表示失败。
    #>
    param([string]$PackageId, [string]$DisplayName)
    Write-Step "通过 winget 安装 $DisplayName ($PackageId) ..."
    try {
        # --accept-package-agreements / --accept-source-agreements：避免交互卡住
        # --silent：使用安装包的静默模式，避免弹窗
        # 注意：不能用 $args，它是 PowerShell 自动变量（接收未声明参数），无法显式赋值
        $wingetArgs = @('install', '--id', $PackageId, '--accept-package-agreements', '--accept-source-agreements', '--silent')
        & winget @wingetArgs
        if ($LASTEXITCODE -eq 0) {
            Write-OK "$DisplayName 安装完成"
            return $true
        } else {
            Write-Warn "winget 返回非零退出码 $LASTEXITCODE，可能已安装或需手动确认"
            return $false
        }
    } catch {
        Write-Err "winget 安装 $DisplayName 失败：$_"
        return $false
    }
}

function Invoke-Safe {
    # 封装外部命令调用：失败时输出上下文，便于排错
    param([scriptblock]$Block, [string]$Description)
    try {
        # 重置 LASTEXITCODE，避免历史值干扰纯 cmdlet 调用的判断
        # cmdlet 不会更新 LASTEXITCODE，若不重置会误用上一次外部命令的退出码
        $global:LASTEXITCODE = 0
        & $Block
        if ($LASTEXITCODE -ne 0) {
            throw "退出码 $LASTEXITCODE"
        }
    } catch {
        Write-Err "$Description 失败：$_"
        throw
    }
}

# ============================================================
# 路径常量
# ============================================================

$Script:ProjectRoot   = (Resolve-Path "$PSScriptRoot\..").Path
$Script:VenvDir       = Join-Path $ProjectRoot ".venv"
$Script:VenvPython    = Join-Path $VenvDir "Scripts\python.exe"
$Script:VenvPip       = Join-Path $VenvDir "Scripts\pip.exe"
$Script:VenvPlaywright= Join-Path $VenvDir "Scripts\playwright.exe"
$Script:FrontendDir   = Join-Path $ProjectRoot "frontend"
$Script:LogsDir       = Join-Path $ProjectRoot "logs"
$Script:DataDir       = Join-Path $ProjectRoot "data"
$Script:BrowserDataDir= Join-Path $ProjectRoot "browser-data"
$Script:EnvFile       = Join-Path $ProjectRoot ".env"
$Script:EnvExample    = Join-Path $ProjectRoot ".env.example"
$Script:ConfigDir     = Join-Path $ProjectRoot "config"
$Script:Requirements  = Join-Path $ProjectRoot "requirements.txt"
$Script:Pyproject     = Join-Path $ProjectRoot "pyproject.toml"

# 版本门槛：与 pyproject.toml requires-python>=3.10、Dockerfile python:3.12 对齐
$Script:PythonMinMajor = 3
$Script:PythonMinMinor = 12
# 前端构建脚本（重新构建.bat）显式使用 nodejs24 路径，此处与之一致
$Script:NodeMinMajor   = 24
$Script:NodeMinMinor   = 0

# ============================================================
# 主流程
# ============================================================

Write-Host ""
Write-Host "============================================================" -ForegroundColor DarkCyan
Write-Host "  XianyuHunter 一键环境配置" -ForegroundColor Cyan
Write-Host "  项目目录: $ProjectRoot" -ForegroundColor DarkGray
Write-Host "============================================================" -ForegroundColor DarkCyan
Write-Host ""

# ---------- Step 1: 系统级软件（Python / Node.js / Git） ----------

if ($SkipSystem) {
    Write-Step "[1/9] 跳过系统级软件安装（-SkipSystem）"
} else {
    Write-Step "[1/9] 检测并安装系统级软件（Python / Node.js / Git）"

    $wingetOk = Test-WingetAvailable
    if (-not $wingetOk) {
        Write-Warn "winget 不可用，将仅检测已有软件；缺失项需手动安装"
    }

    # --- Python ---
    # 优先用 `python`（Python 3 官方安装器在 Windows 上的 launcher），
    # 备选 `py`（Python Launcher for Windows），最后回退到常见安装路径
    $pythonExe = $null
    foreach ($candidate in @('python', 'py -3', 'C:\Python312\python.exe', 'C:\Python311\python.exe', "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe")) {
        $cmd = $candidate.Split(' ')[0]
        if (Test-CommandAvailable $cmd) {
            # py -3 需要参数，单独处理
            if ($candidate -eq 'py -3') {
                $ver = Get-PythonVersion 'py'
                if ($ver -and (Test-VersionSatisfy $ver $PythonMinMajor $PythonMinMinor)) {
                    # 借助 py -3 找到具体可执行文件路径
                    $pythonExe = ((& py -3 -c "import sys; print(sys.executable)") 2>&1).Trim()
                    break
                }
            } else {
                $ver = Get-PythonVersion $candidate
                if ($ver -and (Test-VersionSatisfy $ver $PythonMinMajor $PythonMinMinor)) {
                    $pythonExe = $candidate
                    break
                }
            }
        }
    }

    if ($pythonExe) {
        $ver = Get-PythonVersion $pythonExe
        Write-OK "Python 已就绪: $pythonExe ($($ver.Major).$($ver.Minor).$($ver.Patch))"
    } else {
        Write-Warn "未找到 Python >= $PythonMinMajor.$PythonMinMinor"
        if ($wingetOk) {
            # 选择 3.12 而非 3.13/3.14：requirements.txt 锁定版本在 3.12 上经过验证
            $installed = Install-WithWinget 'Python.Python.3.12' 'Python 3.12'
            if ($installed) {
                # winget 安装后当前会话 PATH 未刷新，需主动探测标准路径
                $candidatePaths = @(
                    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
                    "C:\Program Files\Python312\python.exe",
                    "C:\Python312\python.exe"
                )
                foreach ($p in $candidatePaths) {
                    if (Test-Path $p) { $pythonExe = $p; break }
                }
                if (-not $pythonExe) {
                    # 最后回退：从注册表读取 Python 安装路径
                    $reg = Get-ItemProperty 'HKLM:\SOFTWARE\Python\PythonCore\3.12\InstallPath' -ErrorAction SilentlyContinue
                    if ($reg) { $pythonExe = Join-Path $reg.'(default)' "python.exe" }
                }
            }
        }
        if (-not $pythonExe) {
            Write-Err "Python 安装失败。请手动安装 Python 3.12+ 后重跑此脚本（可加 -SkipSystem 跳过）"
            throw "Python 不可用"
        }
        # 刷新当前会话 PATH，让后续 python 命令直接生效
        $env:Path = [System.Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [System.Environment]::GetEnvironmentVariable('Path', 'User')
        Write-OK "Python 安装完成: $pythonExe"
    }

    # --- Node.js ---
    $nodeExe = $null
    if (Test-CommandAvailable 'node') {
        $ver = Get-NodeVersion 'node'
        if ($ver -and (Test-VersionSatisfy $ver $NodeMinMajor $NodeMinMinor)) {
            $nodeExe = 'node'
        } else {
            Write-Warn "检测到 Node.js $($ver.Major).$($ver.Minor)，但需要 >= $NodeMinMajor.$NodeMinMinor"
        }
    }
    # 兼容 `重新构建.bat` 中硬编码的 D:\code\nodejs24 路径
    if (-not $nodeExe -and (Test-Path 'D:\code\nodejs24\node.exe')) {
        $ver = Get-NodeVersion 'D:\code\nodejs24\node.exe'
        if ($ver -and (Test-VersionSatisfy $ver $NodeMinMajor $NodeMinMinor)) {
            $nodeExe = 'D:\code\nodejs24\node.exe'
        }
    }

    if ($nodeExe) {
        $ver = Get-NodeVersion $nodeExe
        Write-OK "Node.js 已就绪: $nodeExe ($($ver.Major).$($ver.Minor).$($ver.Patch))"
    } else {
        Write-Warn "未找到 Node.js >= $NodeMinMajor.$NodeMinMinor"
        if ($wingetOk) {
            # 选择 24.x LTS：与现有构建脚本路径一致，避免 Node 26+ 可能的生态滞后
            $installed = Install-WithWinget 'OpenJS.NodeJS.LTS' 'Node.js LTS'
            if ($installed) {
                $env:Path = [System.Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [System.Environment]::GetEnvironmentVariable('Path', 'User')
                if (Test-CommandAvailable 'node') {
                    $nodeExe = 'node'
                }
            }
        }
        if (-not $nodeExe) {
            Write-Err "Node.js 安装失败。请手动安装 Node.js 24+ 后重跑此脚本（可加 -SkipSystem 跳过）"
            throw "Node.js 不可用"
        }
        $ver = Get-NodeVersion $nodeExe
        Write-OK "Node.js 安装完成: $nodeExe ($($ver.Major).$($ver.Minor).$($ver.Patch))"
    }

    # --- Git（可选，仅检测提示，不强装） ---
    if (Test-CommandAvailable 'git') {
        Write-OK "Git 已就绪"
    } else {
        Write-Warn "未检测到 Git（非必需，仅克隆代码需要）。如需安装：winget install Git.Git"
    }
}

# ---------- Step 2: Python 虚拟环境 ----------

Write-Step "[2/9] 创建 Python 虚拟环境 (.venv)"

# 选定最终使用的 python 可执行文件：优先虚拟环境内，否则用系统 python
$bootstrapPython = $null
if (Test-CommandAvailable 'python') { $bootstrapPython = 'python' }
elseif (Test-CommandAvailable 'py') { $bootstrapPython = 'py' }
elseif (Test-Path "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe") { $bootstrapPython = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" }

if (-not $bootstrapPython) {
    Write-Err "找不到任何可用的 Python 解释器，无法创建虚拟环境"
    throw "Python 不可用"
}

if (Test-Path $VenvPython) {
    Write-OK "虚拟环境已存在: $VenvPython"
} else {
    Invoke-Safe { & $bootstrapPython -m venv $VenvDir } "创建虚拟环境"
    if (-not (Test-Path $VenvPython)) {
        throw "虚拟环境创建后未找到 $VenvPython"
    }
    Write-OK "虚拟环境创建完成"
}

# ---------- Step 3: 升级 pip + 安装 Python 依赖 ----------

Write-Step "[3/9] 安装 Python 依赖 (requirements.txt + 项目本体)"

# pip 自身先升级，避免老版本对 pyproject.toml metadata 解析失败
# setuptools 固定 <82：torch 2.12+ 要求 setuptools<82，升级到最新(83+)会破坏 torch
Invoke-Safe { & $VenvPython -m pip install --upgrade "pip" "setuptools<82" "wheel" } "升级 pip"

# 清理 pip 卸载残留（~前缀目录）：pip 卸载包时先重命名为 ~xxx，若中途失败会残留，每次 pip 执行都报警告
$brokenDists = Get-ChildItem (Join-Path $VenvDir "Lib\site-packages") -Directory -Filter '~*' -ErrorAction SilentlyContinue
if ($brokenDists) {
    foreach ($d in $brokenDists) { Remove-Item -Recurse -Force $d.FullName -ErrorAction SilentlyContinue }
    Write-OK "已清理 pip 卸载残留目录（~前缀）"
}

$pipArgs = @('install', '-r', $Requirements)
if ($Force) { $pipArgs += '--force-reinstall' }
Invoke-Safe { & $VenvPython -m pip @pipArgs } "安装 requirements.txt"

# 以可编辑模式安装项目本体，让 `import xianyu_hunter` 生效（pyproject.toml 配置 src 布局）
Invoke-Safe { & $VenvPython -m pip install -e $ProjectRoot } "安装项目本体（可编辑模式）"

# chromadb 是 pyproject.toml 主依赖（智能客服 RAG 向量库），但 requirements.txt 由 pip freeze
# 生成可能滞后；pip install -e . 在项目已以可编辑模式安装时会跳过依赖重检，导致 chromadb 缺失。
# 此处显式安装作为保障；失败不阻断主流程（chromadb 缺失时 chatbot 子容器自动降级为 None）
try {
    Invoke-Safe { & $VenvPython -m pip install "chromadb>=1.0.0" } "安装 chromadb（智能客服向量库）"
    # chromadb 依赖 huggingface-hub，后者要求 typer<0.26.0；requirements.txt 锁定的 0.26.6 不兼容，需降级
    Invoke-Safe { & $VenvPython -m pip install "typer<0.26.0" } "降级 typer 兼容 huggingface-hub"
} catch {
    Write-Warn "chromadb 安装失败（智能客服功能将不可用）：$_"
}

# sentence-transformers：智能客服本地 Embedding 模式必需（local_embedding.py）
# torch 是其传递依赖，需 setuptools<82（已在上方 pip 升级时固定）
# 失败不阻断主流程：缺失时 local_embedding.py raise RuntimeError，chatbot 自动降级到远程 embedding
try {
    Invoke-Safe { & $VenvPython -m pip install "sentence-transformers>=2.7.0" } "安装 sentence-transformers（本地 Embedding）"
} catch {
    Write-Warn "sentence-transformers 安装失败（本地 Embedding 模式将不可用，需改用远程 embedding）：$_"
}

# psutil：浏览器进程管理（browser_import.py / browser_login.py）
# 轻量纯 Python 包，缺失时回退到 taskkill，但 psutil 提供更可靠的进程树清理
try {
    Invoke-Safe { & $VenvPython -m pip install "psutil>=5.9.0" } "安装 psutil（进程管理）"
} catch {
    Write-Warn "psutil 安装失败（浏览器进程清理将降级到 taskkill）：$_"
}

# 核心模块导入冒烟测试，提前发现依赖缺失或路径错误
# 用 -join 合并可能的数组输出，-notmatch 避免 stderr 警告干扰判断
$importCheck = (& $VenvPython -c "import xianyu_hunter, uvicorn, fastapi, playwright, sqlalchemy, httpx, aiohttp, apscheduler, typer, pydantic, loguru, cryptography, keyring, yaml; print('ok')" 2>&1) -join "`n"
if ($importCheck -notmatch 'ok$') {
    Write-Err "核心模块导入失败：$importCheck"
    throw "Python 依赖校验失败"
}
Write-OK "Python 依赖安装完成，核心模块导入正常"

# ---------- Step 4: Playwright Chromium ----------

if ($SkipPlaywright) {
    Write-Step "[4/9] 跳过 Playwright Chromium 安装（-SkipPlaywright）"
} else {
    Write-Step "[4/9] 安装 Playwright Chromium 浏览器"
    # 仅装 chromium：项目仅用 Chromium 内核，避免下载 firefox/webkit 浪费磁盘
    Invoke-Safe { & $VenvPython -m playwright install chromium } "安装 Playwright Chromium"
    Write-OK "Playwright Chromium 安装完成"
}

# ---------- Step 5: 配置文件 ----------

Write-Step "[5/9] 初始化配置文件 (.env / config.yaml / eval.yaml)"

# .env：推送 Key 等敏感信息存放处，从模板复制后用户自行填值
if (Test-Path $EnvFile) {
    Write-OK ".env 已存在，跳过"
} elseif (Test-Path $EnvExample) {
    Copy-Item $EnvExample $EnvFile
    Write-OK ".env 已从模板创建，请编辑填入推送 Key"
} else {
    Write-Warn ".env.example 不存在，跳过 .env 创建"
}

# config.yaml：主配置，缺失则从模板复制（避免首次启动报错）
$configYaml = Join-Path $ConfigDir "config.yaml"
$configExample = Join-Path $ConfigDir "config.example.yaml"
if (Test-Path $configYaml) {
    Write-OK "config.yaml 已存在"
} elseif (Test-Path $configExample) {
    Copy-Item $configExample $configYaml
    Write-OK "config.yaml 已从模板创建"
} else {
    Write-Warn "config.yaml 和 config.example.yaml 均不存在，请手动创建配置"
}

# eval.yaml：评估规则配置，处理逻辑同上
$evalYaml = Join-Path $ConfigDir "eval.yaml"
$evalExample = Join-Path $ConfigDir "eval.example.yaml"
if (Test-Path $evalYaml) {
    Write-OK "eval.yaml 已存在"
} elseif (Test-Path $evalExample) {
    Copy-Item $evalExample $evalYaml
    Write-OK "eval.yaml 已从模板创建"
} else {
    Write-Warn "eval.yaml 和 eval.example.yaml 均不存在，请手动创建评估配置"
}

# ---------- Step 6: 数据目录 ----------

Write-Step "[6/9] 创建运行时数据目录"
# 这些目录在 .gitignore 中被忽略，需在初始化时主动创建
foreach ($d in @($LogsDir, $DataDir, $BrowserDataDir, (Join-Path $DataDir "logs"), (Join-Path $DataDir "prompts"), (Join-Path $DataDir "screenshots"))) {
    if (-not (Test-Path $d)) {
        New-Item -ItemType Directory -Path $d -Force | Out-Null
    }
}
Write-OK "数据目录就绪 (logs / data / browser-data)"

# ---------- Step 7: 前端依赖 ----------

if ($SkipFrontend) {
    Write-Step "[7/9] 跳过前端构建（-SkipFrontend）"
} else {
    Write-Step "[7/9] 安装前端依赖并构建 SPA"

    # 找到可用的 npm：优先 PATH 中的 npm，备选 node 同目录下的 npm.cmd
    $npmCmd = $null
    # 优先用 Step 1 验证过版本的 $nodeExe 推导 npm 路径，避免 PATH 中旧版 npm（如 npm 6 不兼容 lockfileVersion 3）
    if ($nodeExe -and $nodeExe -ne 'node' -and (Test-Path (Join-Path (Split-Path $nodeExe) 'npm.cmd'))) {
        $npmCmd = Join-Path (Split-Path $nodeExe) 'npm.cmd'
    } elseif (Test-CommandAvailable 'npm') { $npmCmd = 'npm' }
    elseif (Test-Path 'D:\code\nodejs24\npm.cmd') { $npmCmd = 'D:\code\nodejs24\npm.cmd' }

    if (-not $npmCmd) {
        Write-Warn "找不到 npm，跳过前端构建。请确认 Node.js 安装后重跑（可加 -SkipSystem）"
    } else {
        Push-Location $FrontendDir
        try {
            # npm ci 比 install 更严格（依赖 lockfile），失败时更能暴露环境问题
            if (Test-Path (Join-Path $FrontendDir "package-lock.json")) {
                Invoke-Safe { & $npmCmd ci --no-fund --no-audit } "npm ci 安装前端依赖"
            } else {
                Invoke-Safe { & $npmCmd install --no-fund --no-audit } "npm install 安装前端依赖"
            }
            Write-OK "前端依赖安装完成"

            # ---------- Step 8: 构建前端 ----------
            Write-Step "[8/9] 构建前端 SPA 产物"
            # 构建产物输出到 src/xianyu_hunter/web/static/spa，被 FastAPI 作为静态资源服务
            Invoke-Safe { & $npmCmd run build } "vite build"
            $spaDir = Join-Path $ProjectRoot "src\xianyu_hunter\web\static\spa"
            if (Test-Path (Join-Path $spaDir "index.html")) {
                Write-OK "前端构建完成，产物位于 src/xianyu_hunter/web/static/spa"
            } else {
                Write-Warn "构建完成但未找到 SPA 入口 index.html，请检查 vite 配置"
            }
        } finally {
            Pop-Location
        }
    }
}

# ---------- Step 9: 最终校验 ----------

Write-Step "[9/9] 环境自检"

$checklist = @(
    @{ Name = "Python 虚拟环境"; Test = { Test-Path $VenvPython } },
    @{ Name = "requirements.txt 依赖"; Test = {
        # 同 Step 3：用 -join 合并数组，-match 避免 stderr 干扰
        $r = (& $VenvPython -c "import uvicorn, fastapi, sqlalchemy, playwright, httpx, aiohttp, apscheduler, typer, pydantic, loguru, cryptography, keyring, yaml; print('ok')" 2>&1) -join "`n"
        $r -match 'ok$'
    } },
    @{ Name = ".env 配置文件"; Test = { Test-Path $EnvFile } },
    @{ Name = "config.yaml"; Test = { Test-Path (Join-Path $ConfigDir "config.yaml") } },
    @{ Name = "logs 目录"; Test = { Test-Path $LogsDir } },
    @{ Name = "data 目录"; Test = { Test-Path $DataDir } }
)
if (-not $SkipFrontend) {
    $checklist += @{ Name = "前端 SPA 产物"; Test = { Test-Path (Join-Path $ProjectRoot "src\xianyu_hunter\web\static\spa\index.html") } }
}

$allPass = $true
foreach ($item in $checklist) {
    if (& $item.Test) {
        Write-OK "$($item.Name) ✓"
    } else {
        Write-Err "$($item.Name) ✗"
        $allPass = $false
    }
}

Write-Host ""
if ($allPass) {
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  环境配置完成！" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
} else {
    Write-Host "============================================================" -ForegroundColor Yellow
    Write-Host "  部分检查未通过，请按上述提示修复后重跑" -ForegroundColor Yellow
    Write-Host "============================================================" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "下一步操作：" -ForegroundColor Cyan
Write-Host "  1. 编辑 .env 填入推送 Key（SERVERCHAN_KEY / PUSHPLUS_TOKEN / BARK_KEY 等）"
Write-Host "  2. 首次登录闲鱼：.venv\Scripts\python.exe -m xianyu_hunter login"
Write-Host "  3. 启动服务：双击 scripts\启动服务.bat 或执行："
Write-Host "       .\.venv\Scripts\python.exe -m xianyu_hunter web --with-scheduler"
Write-Host "  4. 访问：http://127.0.0.1:8001/app/"
Write-Host ""

# ---------- 可选：启动服务 ----------

if ($StartService -and $allPass) {
    Write-Step "启动 Web 服务（-StartService）"
    $env:PYTHONPATH = Join-Path $ProjectRoot "src"
    $env:PYTHONUNBUFFERED = "1"
    # 后台启动，输出重定向到 logs，避免阻塞当前会话
    if (-not (Test-Path $LogsDir)) { New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null }
    $outLog = Join-Path $LogsDir "setup-uvicorn.out.log"
    $errLog = Join-Path $LogsDir "setup-uvicorn.err.log"
    Start-Process -FilePath $VenvPython `
        -ArgumentList "-u","-m","xianyu_hunter","web","--host","127.0.0.1","--port","8001","--with-scheduler" `
        -WorkingDirectory $ProjectRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $outLog `
        -RedirectStandardError $errLog
    Write-OK "Web 服务已后台启动，访问 http://127.0.0.1:8001/app/"
    Write-Host "  日志: $outLog"
}

Write-Host ""
return 0
