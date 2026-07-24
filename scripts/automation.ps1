<#
.SYNOPSIS
    闲鱼猎人项目自动化生命周期管理脚本
.DESCRIPTION
    整合 启动服务.bat / 停止服务.bat / 前端构建.bat 三个脚本，
    提供统一的 start/stop/rebuild/check/status 接口，
    包含环境预检查、日志记录、错误处理与回滚提示。
.PARAMETER Action
    必填。取值：start | stop | rebuild | check | status
.PARAMETER LogFile
    可选。日志文件路径，默认 logs\automation.log
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\automation.ps1 -Action start
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\automation.ps1 -Action rebuild
.NOTES
    仅在 Windows + PowerShell 5.x 环境验证；不依赖 && 语法。
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('start', 'stop', 'rebuild', 'check', 'status')]
    [string]$Action,

    [string]$LogFile = 'logs\automation.log'
)

# 切换到项目根目录（脚本位于 scripts/ 子目录）
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

# 确保日志目录存在
$LogDir = Split-Path -Parent $LogFile
if ($LogDir -and -not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

# 控制台使用 UTF-8 输出，避免中文脚本名乱码
try { chcp 65001 > $null } catch { }

# 项目常量
$Script:StartBat  = Join-Path $ProjectRoot 'scripts\启动服务.bat'
$Script:StopBat   = Join-Path $ProjectRoot 'scripts\停止服务.bat'
$Script:RebuildBat = Join-Path $ProjectRoot 'scripts\前端构建.bat'
$Script:VenvPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
# Node.exe 路径从 scripts/node-config.json 读取，避免硬编码（便于跨环境迁移）
# 为什么不直接写死路径：不同机器 Node 安装位置不同，配置化便于切换版本
$Script:NodeExe    = $null
$nodeConfigPath = Join-Path $PSScriptRoot 'node-config.json'
if (Test-Path $nodeConfigPath) {
    try {
        $nodeConfig = Get-Content $nodeConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
        # 按 search_paths 顺序查找第一个存在的 node.exe
        foreach ($p in $nodeConfig.node.search_paths) {
            $expanded = [System.Environment]::ExpandEnvironmentVariables($p)
            if (Test-Path $expanded) { $Script:NodeExe = $expanded; break }
        }
    } catch {
        Write-Host "[WARN] node-config.json 解析失败，将回退到 PATH 中的 node" -ForegroundColor Yellow
    }
}
# 兜底：配置文件缺失时用 PATH 中的 node
if (-not $Script:NodeExe) {
    $cmd = Get-Command node -ErrorAction SilentlyContinue
    if ($cmd) { $Script:NodeExe = $cmd.Source }
}
$Script:ViteJs     = Join-Path $ProjectRoot 'frontend\node_modules\vite\bin\vite.js'
$Script:ConfigYaml = Join-Path $ProjectRoot 'config\config.yaml'
$Script:EnvFile    = Join-Path $ProjectRoot '.env'
$Script:PidFile    = Join-Path $ProjectRoot 'logs\web.pid'
$Script:WebLog     = Join-Path $ProjectRoot 'logs\web.log'
$Script:WebErr     = Join-Path $ProjectRoot 'logs\web.err'

# ========== 日志函数 ==========
function Write-Log {
    param(
        [string]$Level = 'INFO',
        [string]$ActionName,
        [string]$Step,
        [string]$Result = 'pass',
        [string]$Msg = ''
    )
    $ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $line = "$ts [$Level] ACTION=$ActionName STEP=$Step RESULT=$Result"
    if ($Msg) { $line += " MSG=`"$Msg`"" }
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
    # 同时输出到控制台
    $color = switch ($Level) {
        'ERROR' { 'Red' }
        'WARN'  { 'Yellow' }
        default { 'Gray' }
    }
    Write-Host $line -ForegroundColor $color
}

function Write-Step {
    param([string]$Text)
    Write-Host "`n>>> $Text" -ForegroundColor Cyan
}

# ========== 端口与进程检查 ==========
function Test-PortListening {
    param([int]$Port = 8001)
    $line = netstat -aon | Select-String ":$Port.*LISTENING"
    return [bool]$line
}

function Get-PortPid {
    param([int]$Port = 8001)
    $line = netstat -aon | Select-String ":$Port.*LISTENING" | Select-Object -First 1
    if ($line) {
        # 形如 "  TCP    0.0.0.0:8001    0.0.0.0:0    LISTENING    12345"
        $parts = $line.ToString().Trim() -split '\s+'
        return $parts[-1]
    }
    return $null
}

function Test-PidAlive {
    param([string]$Pid)
    if (-not $Pid) { return $false }
    $r = tasklist /FI "PID eq $Pid" 2>$null | Select-String $Pid
    return [bool]$r
}

# ========== 环境检查 ==========
function Invoke-EnvCheck {
    Write-Step '环境预检查'
    $results = @()

    # 1. Python 虚拟环境
    $ok = Test-Path $VenvPython
    $results += [pscustomobject]@{ Item = 'Python venv'; Ok = $ok; Fix = 'python -m venv .venv' }
    if (-not $ok) {
        Write-Log -Level 'ERROR' -ActionName $Action -Step 'env-check' -Result 'fail' -Msg '.venv not found'
    }

    # 2. Python 核心依赖（仅在 venv 存在时检查）
    if ($ok) {
        $pyCheck = & $VenvPython -c "import xianyu_hunter, uvicorn, fastapi" 2>$null
        $pyOk = ($LASTEXITCODE -eq 0)
        $results += [pscustomobject]@{ Item = 'Python deps'; Ok = $pyOk; Fix = '.venv\Scripts\pip install -r requirements.txt' }
        if (-not $pyOk) {
            Write-Log -Level 'ERROR' -ActionName $Action -Step 'env-check' -Result 'fail' -Msg 'Python core deps missing'
        }
    } else {
        $results += [pscustomobject]@{ Item = 'Python deps'; Ok = $false; Fix = '需先创建 .venv' }
    }

    # 3. Node.js 24
    $nodeOk = Test-Path $NodeExe
    $results += [pscustomobject]@{ Item = 'Node.js 24'; Ok = $nodeOk; Fix = "检查 $NodeExe 是否存在" }
    if (-not $nodeOk) {
        Write-Log -Level 'WARN' -ActionName $Action -Step 'env-check' -Result 'skip' -Msg 'Node.js 24 not found (rebuild 时需要)'
    }

    # 4. 前端依赖
    $viteOk = Test-Path $ViteJs
    $results += [pscustomobject]@{ Item = 'Frontend deps'; Ok = $viteOk; Fix = 'cd frontend; npm install' }

    # 5. 配置文件
    $cfgOk = Test-Path $ConfigYaml
    $results += [pscustomobject]@{ Item = 'config.yaml'; Ok = $cfgOk; Fix = 'copy config\config.example.yaml config\config.yaml' }

    # 6. .env 文件
    $envOk = Test-Path $EnvFile
    $results += [pscustomobject]@{ Item = '.env'; Ok = $envOk; Fix = 'copy .env.example .env' }

    # 7. 日志目录
    $logDir = Join-Path $ProjectRoot 'logs'
    $logOk = Test-Path $logDir
    if (-not $logOk) {
        New-Item -ItemType Directory -Path $logDir -Force | Out-Null
        $logOk = $true
    }
    $results += [pscustomobject]@{ Item = 'logs dir'; Ok = $logOk; Fix = '自动创建' }

    # 8. PID 文件状态
    $pidExists = Test-Path $PidFile
    $pidAlive = $false
    $pidValue = $null
    if ($pidExists) {
        $pidValue = Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($pidValue) { $pidAlive = Test-PidAlive -Pid $pidValue }
    }
    $results += [pscustomobject]@{ Item = 'web.pid'; Ok = $pidAlive; Fix = '若 PID 已失效，删除 logs\web.pid' }

    # 9. 8001 端口状态
    $portInUse = Test-PortListening -Port 8001
    $results += [pscustomobject]@{ Item = 'port 8001'; Ok = $portInUse; Fix = '' }
    # 注意：端口被占用对 start 是问题，对 stop 是预期

    # 输出检查结果表格
    Write-Host ''
    Write-Host '检查项                状态    修复建议' -ForegroundColor White
    Write-Host ('-' * 70)
    foreach ($r in $results) {
        $mark = if ($r.Ok) { '[OK]  ' } else { '[FAIL]' }
        $color = if ($r.Ok) { 'Green' } else { 'Red' }
        $fix = if ($r.Fix) { "  -> $($r.Fix)" } else { '' }
        Write-Host ("{0,-20} {1} {2}" -f $r.Item, $mark, $fix) -ForegroundColor $color
    }

    # 返回综合判定
    $critical = $results | Where-Object { $_.Item -in @('Python venv', 'Python deps', 'config.yaml') -and -not $_.Ok }
    return (@() -eq $critical)
}

# ========== 调用 .bat 的封装 ==========
function Invoke-BatScript {
    param(
        [string]$BatPath,
        [string]$StepName
    )
    if (-not (Test-Path $BatPath)) {
        Write-Log -Level 'ERROR' -ActionName $Action -Step $StepName -Result 'fail' -Msg "bat not found: $BatPath"
        return $false
    }
    Write-Log -ActionName $Action -Step $StepName -Result 'pass' -Msg "calling $BatPath"
    # 使用 cmd /c 调用，避免 PowerShell 解析 .bat 中的 & 等特殊字符
    # 输出直接到控制台，让用户看到 .bat 的进度
    cmd /c "`"$BatPath`""
    $exit = $LASTEXITCODE
    if ($exit -ne 0) {
        Write-Log -Level 'ERROR' -ActionName $Action -Step $StepName -Result 'fail' -Msg "bat exit code $exit"
        return $false
    }
    Write-Log -ActionName $Action -Step $StepName -Result 'pass'
    return $true
}

# ========== 等待端口就绪 ==========
function Wait-PortReady {
    param([int]$TimeoutSec = 30, [int]$Port = 8001)
    $tries = [int]($TimeoutSec / 2)
    for ($i = 1; $i -le $tries; $i++) {
        Start-Sleep -Seconds 2
        if (Test-PortListening -Port $Port) {
            return $true
        }
        Write-Host "  等待端口 $Port 就绪... ($i/$tries)" -ForegroundColor DarkGray
    }
    return $false
}

# ========== 等待端口释放 ==========
function Wait-PortFree {
    param([int]$TimeoutSec = 10, [int]$Port = 8001)
    $tries = [int]($TimeoutSec / 1)
    for ($i = 1; $i -le $tries; $i++) {
        if (-not (Test-PortListening -Port $Port)) {
            return $true
        }
        Start-Sleep -Seconds 1
    }
    return $false
}

# ========== 动作实现 ==========
function Invoke-Start {
    Write-Step '[start] 启动闲鱼猎人服务'
    $envOk = Invoke-EnvCheck
    if (-not $envOk) {
        Write-Host "`n[FAIL] 环境检查未通过，已终止启动。" -ForegroundColor Red
        Write-Host "请按上方修复建议处理后重试。" -ForegroundColor Yellow
        return $false
    }

    # 端口已占用时给出明确提示
    if (Test-PortListening -Port 8001) {
        $pidOcc = Get-PortPid -Port 8001
        Write-Log -Level 'WARN' -ActionName $Action -Step 'pre-check' -Result 'skip' -Msg "port 8001 already in use by PID $pidOcc"
        Write-Host "`n[WARN] 端口 8001 已被占用 (PID: $pidOcc)。" -ForegroundColor Yellow
        Write-Host "建议先执行 -Action stop，或手动 taskkill /F /PID $pidOcc" -ForegroundColor Yellow
        return $false
    }

    Write-Step '[1/2] 调用 启动服务.bat'
    $ok = Invoke-BatScript -BatPath $StartBat -StepName 'call-bat'
    if (-not $ok) {
        Write-Host "`n[FAIL] 启动脚本执行失败。" -ForegroundColor Red
        return $false
    }

    Write-Step '[2/2] 验证 8001 端口'
    if (Wait-PortReady -TimeoutSec 30 -Port 8001) {
        $newPid = Get-PortPid -Port 8001
        Write-Log -ActionName $Action -Step 'verify-port' -Result 'pass' -Msg "PID=$newPid"
        Write-Host "`n[OK] 服务已启动" -ForegroundColor Green
        Write-Host "  Web:  http://127.0.0.1:8001/app/" -ForegroundColor White
        Write-Host "  PID:  $newPid" -ForegroundColor White
        Write-Host "  Log:  $LogFile" -ForegroundColor White
        return $true
    } else {
        Write-Log -Level 'ERROR' -ActionName $Action -Step 'verify-port' -Result 'fail' -Msg 'port 8001 not listening after 30s'
        Write-Host "`n[FAIL] 30 秒内端口 8001 未就绪。" -ForegroundColor Red
        if (Test-Path $WebLog) {
            Write-Host "`n--- logs\web.log 末尾 20 行 ---" -ForegroundColor Yellow
            Get-Content $WebLog -Tail 20 -ErrorAction SilentlyContinue
        }
        if (Test-Path $WebErr) {
            Write-Host "`n--- logs\web.err 末尾 20 行 ---" -ForegroundColor Yellow
            Get-Content $WebErr -Tail 20 -ErrorAction SilentlyContinue
        }
        return $false
    }
}

function Invoke-Stop {
    Write-Step '[stop] 停止闲鱼猎人服务'
    $ok = Invoke-BatScript -BatPath $StopBat -StepName 'call-bat'
    if (-not $ok) {
        Write-Host "`n[FAIL] 停止脚本执行失败。" -ForegroundColor Red
        return $false
    }

    Write-Step '[verify] 验证端口已释放'
    if (Wait-PortFree -TimeoutSec 10 -Port 8001) {
        Write-Log -ActionName $Action -Step 'verify-stop' -Result 'pass'
        Write-Host "`n[OK] 服务已停止，端口 8001 已释放" -ForegroundColor Green
        return $true
    } else {
        $pidOcc = Get-PortPid -Port 8001
        Write-Log -Level 'WARN' -ActionName $Action -Step 'verify-stop' -Result 'fail' -Msg "port 8001 still in use by PID $pidOcc"
        Write-Host "`n[WARN] 端口 8001 仍被占用 (PID: $pidOcc)。" -ForegroundColor Yellow
        Write-Host "请打开任务管理器手动结束该进程。" -ForegroundColor Yellow
        return $false
    }
}

function Invoke-Rebuild {
    Write-Step '[rebuild] 重新构建前端并重启服务'

    Write-Step '[1/3] 停止现有服务'
    $ok1 = Invoke-BatScript -BatPath $StopBat -StepName 'stop'
    if (-not $ok1) {
        Write-Host "`n[FAIL] 停止服务失败，已终止重建流程。" -ForegroundColor Red
        Write-Host "       端口可能仍被占用，请先手动释放后再重试。" -ForegroundColor Yellow
        return $false
    }
    # 给端口释放留时间
    Wait-PortFree -TimeoutSec 10 -Port 8001 | Out-Null

    Write-Step '[2/3] 构建前端'
    $ok2 = Invoke-BatScript -BatPath $RebuildBat -StepName 'build'
    if (-not $ok2) {
        Write-Host "`n[FAIL] 前端构建失败，已终止，不会启动服务。" -ForegroundColor Red
        Write-Host "       请检查 frontend\ 目录下的 vite 错误输出。" -ForegroundColor Yellow
        Write-Host "       旧构建产物已清理，服务保持停止状态。" -ForegroundColor Yellow
        return $false
    }

    Write-Step '[3/3] 启动服务'
    $ok3 = Invoke-BatScript -BatPath $StartBat -StepName 'start'
    if (-not $ok3) {
        Write-Host "`n[FAIL] 启动脚本执行失败。" -ForegroundColor Red
        Write-Host "       构建产物已保留，请检查后端日志后手动启动。" -ForegroundColor Yellow
        return $false
    }

    if (Wait-PortReady -TimeoutSec 30 -Port 8001) {
        $newPid = Get-PortPid -Port 8001
        Write-Log -ActionName $Action -Step 'verify-port' -Result 'pass' -Msg "PID=$newPid"
        Write-Host "`n[OK] 重建并重启完成" -ForegroundColor Green
        Write-Host "  Web:  http://127.0.0.1:8001/app/" -ForegroundColor White
        Write-Host "  PID:  $newPid" -ForegroundColor White
        Write-Host "  请在浏览器中 Ctrl+F5 强制刷新以加载新版本。" -ForegroundColor Yellow
        return $true
    } else {
        Write-Log -Level 'ERROR' -ActionName $Action -Step 'verify-port' -Result 'fail'
        Write-Host "`n[FAIL] 服务启动超时，请检查 logs\web.log" -ForegroundColor Red
        return $false
    }
}

function Invoke-Status {
    Write-Step '[status] 查询服务状态'
    $portInUse = Test-PortListening -Port 8001
    $pidExists = Test-Path $PidFile
    $pidValue = $null
    $pidAlive = $false
    if ($pidExists) {
        $pidValue = (Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
        if ($pidValue) { $pidAlive = Test-PidAlive -Pid $pidValue }
    }

    Write-Host ''
    Write-Host "端口 8001 监听 : $(if ($portInUse) { '是' } else { '否' })" -ForegroundColor $(if ($portInUse) { 'Green' } else { 'Gray' })
    Write-Host "PID 文件存在   : $(if ($pidExists) { '是' } else { '否' })" -ForegroundColor $(if ($pidExists) { 'Green' } else { 'Gray' })
    if ($pidExists) {
        Write-Host "PID 文件值     : $pidValue" -ForegroundColor White
        Write-Host "PID 进程存活   : $(if ($pidAlive) { '是' } else { '否 (僵尸 PID 文件)' })" -ForegroundColor $(if ($pidAlive) { 'Green' } else { 'Yellow' })
    }
    if ($portInUse) {
        $realPid = Get-PortPid -Port 8001
        Write-Host "实际占用 PID   : $realPid" -ForegroundColor White
    }

    if ($portInUse -and $pidAlive -and ($pidValue -eq (Get-PortPid -Port 8001))) {
        Write-Host "`n[结论] 服务运行中" -ForegroundColor Green
        Write-Host "  Web: http://127.0.0.1:8001/app/" -ForegroundColor White
    } elseif (-not $portInUse) {
        Write-Host "`n[结论] 服务未运行" -ForegroundColor Gray
    } else {
        Write-Host "`n[结论] 状态异常（端口被占用但 PID 文件不匹配）" -ForegroundColor Yellow
        Write-Host "  建议执行 -Action stop 清理后重启" -ForegroundColor Yellow
    }

    Write-Log -ActionName $Action -Step 'status' -Result 'pass' -Msg "port=$portInUse pidAlive=$pidAlive"
    return $true
}

# ========== 主入口 ==========
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  闲鱼猎人自动化：$Action" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  项目目录: $ProjectRoot"
Write-Host "  日志文件: $LogFile"

$success = switch ($Action) {
    'start'   { Invoke-Start }
    'stop'    { Invoke-Stop }
    'rebuild' { Invoke-Rebuild }
    'check'   { Invoke-EnvCheck }
    'status'  { Invoke-Status }
}

Write-Host ''
if ($success) {
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  动作 '$Action' 已完成" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    exit 0
} else {
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "  动作 '$Action' 失败" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    exit 1
}
