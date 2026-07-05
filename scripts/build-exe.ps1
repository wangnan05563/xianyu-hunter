# scripts/build-exe.ps1
# P0 阶段构建脚本：在干净 venv 中构建 EXE 安装包
#
# 用法：
#   powershell -File scripts/build-exe.ps1            # 默认每次重建 SPA
#   powershell -File scripts/build-exe.ps1 -SkipSPA   # 跳过 SPA 构建（仅当确信前端无变更时使用）
# 产物：dist/xianyu-hunter/ 目录
#
# 构建步骤：
# 1. 创建干净 venv（避免开发环境传递依赖污染）
# 2. 安装项目依赖 + PyInstaller
# 3. 重建依赖锁定（传递依赖完整记录）
# 4. 构建 SPA（默认强制重建，-SkipSPA 可跳过）
# 5. PyInstaller 打包
# 6. 复制外置资源（SPA、Playwright Chromium、sentence-transformers 模型）

param(
    [switch]$SkipSPA
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path "$PSScriptRoot\.."
Set-Location $repoRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  XianyuHunter EXE Build (P0)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Repo: $repoRoot"

# ============== 1. 创建干净构建环境 ==============
Write-Host "`n[1/6] Creating clean build venv..." -ForegroundColor Yellow
Write-Host "  预计耗时：约 10-30 秒" -ForegroundColor DarkGray
if (Test-Path ".venv-build") {
    Remove-Item -Recurse -Force ".venv-build"
}
python -m venv .venv-build
if ($LASTEXITCODE -ne 0) { throw "venv 创建失败" }

# ============== 2. 安装项目依赖 + PyInstaller ==============
Write-Host "`n[2/6] Installing dependencies..." -ForegroundColor Yellow
Write-Host "  预计耗时：约 1-3 分钟（取决于网络速度）" -ForegroundColor DarkGray
& .venv-build\Scripts\pip install -e .
if ($LASTEXITCODE -ne 0) { throw "项目依赖安装失败" }
& .venv-build\Scripts\pip install pyinstaller
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 安装失败" }
# 系统托盘可选依赖：pystray + pillow
# launcher.py 中 try/except 导入，未安装时控制台模式仍可用
# 启用托盘功能时取消下面注释
& .venv-build\Scripts\pip install pystray pillow
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [WARN] pystray/pillow 安装失败，托盘功能将不可用" -ForegroundColor Red
} else {
    Write-Host "  pystray + pillow 已安装（托盘功能可用）"
}

# ============== 3. 重建依赖锁定 ==============
Write-Host "`n[3/6] Locking dependencies..." -ForegroundColor Yellow
Write-Host "  预计耗时：约 5 秒" -ForegroundColor DarkGray
& .venv-build\Scripts\pip freeze > requirements-lock.txt
Write-Host "  依赖已锁定到 requirements-lock.txt"

# ============== 4. 构建 SPA ==============
# 默认每次都重建：避免前端源码已修改但 SPA 产物未更新导致打包后行为不一致
# 用 -SkipSPA 跳过（仅当确信前端无变更时使用，可省 1-3 分钟）
Write-Host "`n[4/6] Building SPA..." -ForegroundColor Yellow
$spaIndex = "src\xianyu_hunter\web\static\spa\index.html"
if ($SkipSPA -and (Test-Path $spaIndex)) {
    Write-Host "  SPA 已存在且 -SkipSPA 已指定，跳过构建" -ForegroundColor DarkGray
} else {
    if (Test-Path $spaIndex) {
        Write-Host "  SPA 已存在但默认强制重建（避免前端源码与产物不一致）" -ForegroundColor DarkGray
    }
    Write-Host "  预计耗时：约 1-3 分钟" -ForegroundColor DarkGray

    # Node 版本检测：vite 5 + ??= 运算符需要 Node 18+
    # 为什么检测：用户机器可能装了多个 Node 版本，PATH 指向旧版会导致构建静默失败
    $nodeVersion = (node --version 2>$null) -replace '[v\n\r]', ''
    if ($nodeVersion) {
        $nodeMajor = [int]($nodeVersion.Split('.')[0])
        if ($nodeMajor -lt 18) {
            Write-Host "  [ERROR] Node $nodeVersion 版本过低，vite 5 需要 Node 18+" -ForegroundColor Red
            Write-Host "  当前 PATH 中的 Node：$((Get-Command node).Source)" -ForegroundColor Red
            Write-Host "  请安装 Node 18+ 或将高版本 Node 加入 PATH 后重试" -ForegroundColor Red
            throw "Node 版本过低（$nodeVersion），需要 18+"
        }
        Write-Host "  Node 版本：$nodeVersion" -ForegroundColor DarkGray
    } else {
        throw "未检测到 Node.js，请安装 Node 18+ 后重试"
    }

    Push-Location frontend
    if (Test-Path "package-lock.json") {
        npm ci
    } else {
        npm install
    }
    if ($LASTEXITCODE -ne 0) { Pop-Location; throw "npm install 失败" }
    npm run build
    if ($LASTEXITCODE -ne 0) { Pop-Location; throw "SPA 构建失败" }
    Pop-Location
    Write-Host "  SPA 构建完成"
}

# ============== 5. PyInstaller 打包 ==============
Write-Host "`n[5/6] Running PyInstaller..." -ForegroundColor Yellow
Write-Host "  预计耗时：约 1-3 分钟" -ForegroundColor DarkGray
if (Test-Path "dist\xianyu-hunter") {
    Remove-Item -Recurse -Force "dist\xianyu-hunter"
}
& .venv-build\Scripts\pyinstaller xianyu-hunter.spec --noconfirm
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 打包失败" }
Write-Host "  PyInstaller 打包完成"

# ============== 6. 复制外置资源 ==============
Write-Host "`n[6/6] Copying external resources..." -ForegroundColor Yellow
Write-Host "  预计耗时：约 2-5 分钟（需下载 Chromium ~150MB 和模型 ~100MB）" -ForegroundColor DarkGray

# 6.1 静态资源（含 SPA + icons，外置到 exe 同级 static 目录）
# app.py 在打包模式下通过 get_app_dir() / "static" 定位此目录
Write-Host "  [6.1] Copying static assets (SPA + icons)...（约 1 秒）"
Copy-Item -Recurse -Force "src\xianyu_hunter\web\static" "dist\xianyu-hunter\static"

# 6.1.1 子进程脚本（auth_helper.py / browser_login.py）
# 为什么需要：browser_login.py / unified_login.py / auth_manager.py 通过 get_app_dir()/"scripts" 定位这些脚本
# PyInstaller 不收集 scripts/ 目录（仅打包 src/xianyu_hunter/），必须显式复制
# 仅复制运行时实际调用的子进程脚本，避免打包测试脚本（test_*.py / perf_test.py 等）
Write-Host "  [6.1.1] Copying subprocess scripts (auth_helper, browser_login)..."
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

# 6.2 Playwright Chromium
# 直接安装到目标位置，避免大文件跨目录复制
# PLAYWRIGHT_BROWSERS_PATH 指定后，playwright install 会把浏览器放到此目录
Write-Host "  [6.2] Installing Playwright Chromium...（下载约 150MB）"
$pwTarget = "$repoRoot\dist\xianyu-hunter\playwright_browsers"
$env:PLAYWRIGHT_BROWSERS_PATH = $pwTarget
& .venv-build\Scripts\playwright install chromium
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [WARN] Playwright Chromium 安装失败" -ForegroundColor Red
} else {
    Write-Host "  Playwright Chromium 已安装到 $pwTarget"
}
Remove-Item Env:\PLAYWRIGHT_BROWSERS_PATH -ErrorAction SilentlyContinue

# 6.3 sentence-transformers 模型（预置，避免首次运行联网下载）
# 设置 HF 镜像，避免国内访问 huggingface.co 超时
Write-Host "  [6.3] Preparing sentence-transformers model...（下载约 100MB）"
$env:HF_ENDPOINT = "https://hf-mirror.com"
$modelDir = "dist\xianyu-hunter\models\bge-small-zh-v1.5"
New-Item -ItemType Directory -Force $modelDir | Out-Null
& .venv-build\Scripts\python -c @"
import os
os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')
from sentence_transformers import SentenceTransformer
m = SentenceTransformer('BAAI/bge-small-zh-v1.5')
m.save(r'$modelDir')
print('Model saved to $modelDir')
"@
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [WARN] 模型预置失败（首次运行将联网下载）" -ForegroundColor Red
} else {
    Write-Host "  模型已预置"
}

# ============== 7. 制作安装包（Inno Setup） ==============
Write-Host "`n[7/7] Building installer (Inno Setup)..." -ForegroundColor Yellow
Write-Host "  预计耗时：约 30 秒（已安装）/ 2-3 分钟（首次需下载安装）" -ForegroundColor DarkGray

# 7.1 查找 iscc.exe（Inno Setup 编译器）
# 优先 PATH，然后常见安装路径
function Find-ISCC {
    # 1. 优先 PATH 中的 iscc
    $cmd = Get-Command iscc -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    # 2. 检查常见安装路径（含 winget 用户级安装路径）
    $paths = @(
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe",
        # winget 用户级安装（不需要管理员权限，默认装到这里）
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        "$env:USERPROFILE\AppData\Local\Programs\Inno Setup 6\ISCC.exe"
    )
    foreach ($p in $paths) { if (Test-Path $p) { return $p } }
    return $null
}

# 刷新当前会话 PATH（安装程序可能已更新系统 PATH 但当前会话未感知）
function Refresh-Path {
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
}

$iscc = Find-ISCC

# 7.2 自动安装 Inno Setup（如未安装）
# 三段式 fallback：winget → 直接下载 is.exe 静默安装 → 跳过
if (-not $iscc) {
    Write-Host "  [7.1] Inno Setup 未安装，尝试自动安装..." -ForegroundColor Cyan

    # 方案 A：winget（Win10 1709+ 自带，最干净）
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host "  [7.1a] 使用 winget 安装..." -ForegroundColor DarkGray
        winget install --id JRSoftware.InnoSetup --silent --accept-package-agreements --accept-source-agreements
        Refresh-Path
        $iscc = Find-ISCC
    }

    # 方案 B：直接下载官方 is.exe 静默安装（绕过 winget，更可靠）
    # innosetup-X.X.X.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-
    if (-not $iscc) {
        Write-Host "  [7.1b] 直接下载 Inno Setup 安装包..." -ForegroundColor DarkGray
        $installerUrl = "https://jrsoftware.org/download.php/is.exe"
        $installerFile = "$env:TEMP\innosetup-install.exe"
        try {
            # Invoke-WebRequest 在 PS 5.1 默认使用 IE 引擎，需指定 -UseBasicParsing
            Invoke-WebRequest -Uri $installerUrl -OutFile $installerFile -UseBasicParsing
            Write-Host "  下载完成，开始静默安装..." -ForegroundColor DarkGray
            # /VERYSILENT：无 UI；/SUPPRESSMSGBOXES：抑制弹窗；/NORESTART：不重启；/SP-：禁用安装前磁盘检查
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

# 7.3 自动创建 installer.iss（如不存在）
# 与项目根目录的 installer.iss 保持一致；缺失时生成精简模板
if ($iscc -and -not (Test-Path "installer.iss")) {
    Write-Host "  [7.2] installer.iss 不存在，自动创建..." -ForegroundColor Cyan
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
Source: "dist\xianyu-hunter\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\XianyuHunter"; Filename: "{app}\xianyu-hunter.exe"
Name: "{commondesktop}\XianyuHunter"; Filename: "{app}\xianyu-hunter.exe"; Tasks: desktopicon
[Run]
Filename: "{app}\xianyu-hunter.exe"; Description: "Launch XianyuHunter"; Flags: nowait postinstall skipifsilent
"@
    # Inno Setup 编译器（ISCC）需要 UTF-8 BOM 才能正确解析模板中的中文（"创建桌面快捷方式"等）
    # 之前用 UTF8Encoding($false)（无 BOM）会导致编译时中文乱码，最终安装包路径或提示信息错位
    [System.IO.File]::WriteAllText("installer.iss", $issTemplate, (New-Object System.Text.UTF8Encoding($true)))
}

# 7.4 编译安装包
if (-not $iscc) {
    Write-Host "  [WARN] Inno Setup 不可用，跳过安装包制作" -ForegroundColor Red
    Write-Host "  手动安装：https://jrsoftware.org/isdl.php" -ForegroundColor DarkGray
} else {
    # 从 __init__.py 读取版本号（与 build_info.py 的 _read_version() 逻辑一致）
    $initFile = "src\xianyu_hunter\__init__.py"
    $version = "0.0.0.0"
    if (Test-Path $initFile) {
        $line = Get-Content $initFile | Where-Object { $_ -match '__version__' } | Select-Object -First 1
        if ($line -match '"([^"]+)"') { $version = $matches[1] }
    }
    Write-Host "  [7.3] 版本号: $version"

    Write-Host "  [7.4] 编译安装包..."
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
Write-Host "  Build Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Output: $distDir"
Write-Host ("  Size: {0:N1} MB" -f $size)
Write-Host "  EXE:   $distDir\xianyu-hunter.exe"
Write-Host "========================================" -ForegroundColor Green
