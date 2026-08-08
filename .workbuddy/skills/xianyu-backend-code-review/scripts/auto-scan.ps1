# ========== 闲鱼猎人后端代码阻塞级问题自动扫描 v2.0.0 ==========
# 扫描 src/xianyu_hunter/ 下的 .py 文件，检查 12 项阻塞级问题
# 用法：pwsh .trae/skills/xianyu-backend-code-review/scripts/auto-scan.ps1

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..\..")).Path
$SourceDir = Join-Path $ProjectRoot "src\xianyu_hunter"
$ConfigYaml = Join-Path $ProjectRoot "config\config.yaml"
$ISSUE_COUNT = 0
$WARN_COUNT = 0

function Get-RelPath($fullPath) {
    if ($fullPath -like "$ProjectRoot*") {
        return $fullPath.Substring($ProjectRoot.Length + 1)
    }
    return $fullPath
}

if (-not (Test-Path $SourceDir)) {
    Write-Host "[ERROR] 源码目录不存在: $SourceDir" -ForegroundColor Red
    exit 1
}

Write-Host "========== 闲鱼猎人后端代码预检 ==========" -ForegroundColor Cyan
Write-Host "源码目录: $SourceDir`n" -ForegroundColor Gray

# 检查1：Token 比较使用 == 而非 hmac.compare_digest()
Write-Host "[1/12] 检查 Token 比较方式..." -ForegroundColor Yellow
Get-ChildItem -Path $SourceDir -Recurse -Filter "*.py" -ErrorAction SilentlyContinue | ForEach-Object {
    $lines = Get-Content $_.FullName -Encoding UTF8
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match '==\s*["\']?\w*token' -and $lines[$i] -notmatch 'hmac\.compare_digest') {
            $lineNum = $i + 1
            Write-Host "  [BLOCK] Token 用 == 比较 L${lineNum}: $(Get-RelPath $_.FullName)" -ForegroundColor Red
            $ISSUE_COUNT++
        }
    }
}

# 检查2：硬编码凭据
Write-Host "[2/12] 检查硬编码凭据..." -ForegroundColor Yellow
Get-ChildItem -Path $SourceDir -Recurse -Filter "*.py" -ErrorAction SilentlyContinue | ForEach-Object {
    $lines = Get-Content $_.FullName -Encoding UTF8
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match '(password|secret|token|api_key|access_key|webhook_secret|dingtalk_secret)\s*[:=]\s*["\'][^"\']{8,}["\']') {
            $lineNum = $i + 1
            Write-Host "  [BLOCK] 硬编码凭据 L${lineNum}: $(Get-RelPath $_.FullName)" -ForegroundColor Red
            $ISSUE_COUNT++
        }
    }
}

# 检查3：config/config.yaml 明文暴露凭据
Write-Host "[3/12] 检查 config.yaml 凭据明文..." -ForegroundColor Yellow
if (Test-Path $ConfigYaml) {
    $lines = Get-Content $ConfigYaml -Encoding UTF8
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match '(webhook_secret|access_token|secret_key|dingtalk_secret)\s*[:=]\s*["\'][^"\']+["\']') {
            $lineNum = $i + 1
            Write-Host "  [BLOCK] config.yaml 明文凭据 L${lineNum}: $(Get-RelPath $ConfigYaml)" -ForegroundColor Red
            $ISSUE_COUNT++
        }
    }
}

# 检查4：WebView2 子进程重定向到 DEVNULL
Write-Host "[4/12] 检查 WebView2 DEVNULL 重定向..." -ForegroundColor Yellow
Get-ChildItem -Path $SourceDir -Recurse -Filter "*.py" -ErrorAction SilentlyContinue | ForEach-Object {
    $lines = Get-Content $_.FullName -Encoding UTF8
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match 'subprocess\.(Popen|run).*DEVNULL') {
            $lineNum = $i + 1
            Write-Host "  [BLOCK] DEVNULL 重定向 L${lineNum}: $(Get-RelPath $_.FullName)" -ForegroundColor Red
            $ISSUE_COUNT++
        }
    }
}

# 检查5：CREATE_NO_WINDOW 标志（应用 CREATE_NEW_CONSOLE）
Write-Host "[5/12] 检查 CREATE_NO_WINDOW 标志..." -ForegroundColor Yellow
Get-ChildItem -Path $SourceDir -Recurse -Filter "*.py" -ErrorAction SilentlyContinue | ForEach-Object {
    $lines = Get-Content $_.FullName -Encoding UTF8
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match 'CREATE_NO_WINDOW') {
            $lineNum = $i + 1
            Write-Host "  [BLOCK] 应用 CREATE_NEW_CONSOLE 替代 CREATE_NO_WINDOW L${lineNum}: $(Get-RelPath $_.FullName)" -ForegroundColor Red
            $ISSUE_COUNT++
        }
    }
}

# 检查6：re/threading/logging 是否在模块级导入（仅扫描是否有缺失）
Write-Host "[6/12] 检查 re/threading/logging 模块级导入..." -ForegroundColor Yellow
Get-ChildItem -Path $SourceDir -Recurse -Filter "*.py" -ErrorAction SilentlyContinue | ForEach-Object {
    $content = Get-Content $_.FullName -Raw -Encoding UTF8
    $lines = Get-Content $_.FullName -Encoding UTF8
    # 如果函数内使用了 re/threading/logging，但模块级未导入
    foreach ($mod in @('re', 'threading', 'logging')) {
        $moduleLevelImport = $false
        foreach ($line in $lines) {
            if ($line -match "^\s*(import\s+$mod|from\s+$mod\s+import)") {
                $moduleLevelImport = $true
                break
            }
        }
        if (-not $moduleLevelImport) {
            # 检查是否在函数内使用
            if ($content -match "\b$mod\.\w+") {
                Write-Host "  [WARN] $mod 未在模块级导入但被使用: $(Get-RelPath $_.FullName)" -ForegroundColor DarkYellow
                $WARN_COUNT++
            }
        }
    }
}

# 检查7：裸 except + pass
Write-Host "[7/12] 检查裸 except + pass..." -ForegroundColor Yellow
Get-ChildItem -Path $SourceDir -Recurse -Filter "*.py" -ErrorAction SilentlyContinue | ForEach-Object {
    $lines = Get-Content $_.FullName -Encoding UTF8
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match 'except\s*:') {
            # 检查下一行是否是 pass
            if ($i + 1 -lt $lines.Count -and $lines[$i + 1] -match '^\s*pass\s*$') {
                $lineNum = $i + 1
                Write-Host "  [BLOCK] 裸 except + pass L${lineNum}: $(Get-RelPath $_.FullName)" -ForegroundColor Red
                $ISSUE_COUNT++
            }
        }
    }
}

# 检查8：已弃用的 datetime.utcnow()
Write-Host "[8/12] 检查 datetime.utcnow()..." -ForegroundColor Yellow
Get-ChildItem -Path $SourceDir -Recurse -Filter "*.py" -ErrorAction SilentlyContinue | ForEach-Object {
    $lines = Get-Content $_.FullName -Encoding UTF8
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match 'datetime\.utcnow\(\)') {
            $lineNum = $i + 1
            Write-Host "  [BLOCK] datetime.utcnow() 已弃用 L${lineNum}: $(Get-RelPath $_.FullName)" -ForegroundColor Red
            $ISSUE_COUNT++
        }
    }
}

# 检查9：SQLite 引擎使用 StaticPool
Write-Host "[9/12] 检查 StaticPool 使用..." -ForegroundColor Yellow
Get-ChildItem -Path $SourceDir -Recurse -Filter "*.py" -ErrorAction SilentlyContinue | ForEach-Object {
    $lines = Get-Content $_.FullName -Encoding UTF8
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match 'poolclass\s*=\s*StaticPool') {
            $lineNum = $i + 1
            Write-Host "  [BLOCK] 应使用 NullPool 而非 StaticPool L${lineNum}: $(Get-RelPath $_.FullName)" -ForegroundColor Red
            $ISSUE_COUNT++
        }
    }
}

# 检查10：local_embedding.py 是否设置 HF_ENDPOINT 镜像
Write-Host "[10/12] 检查 HF_ENDPOINT 镜像..." -ForegroundColor Yellow
$embeddingFile = Join-Path $SourceDir "modules\chatbot\local_embedding.py"
if (Test-Path $embeddingFile) {
    $content = Get-Content $embeddingFile -Raw -Encoding UTF8
    if ($content -match 'import sentence_transformers' -and $content -notmatch 'HF_ENDPOINT') {
        Write-Host "  [BLOCK] local_embedding.py 缺少 HF_ENDPOINT 镜像设置: $(Get-RelPath $embeddingFile)" -ForegroundColor Red
        $ISSUE_COUNT++
    }
} else {
    Write-Host "  [INFO] local_embedding.py 不存在，跳过" -ForegroundColor Gray
}

# 检查11：Pydantic 1.x .dict() / .json() 调用
Write-Host "[11/12] 检查 Pydantic 1.x .dict()/.json()..." -ForegroundColor Yellow
Get-ChildItem -Path $SourceDir -Recurse -Filter "*.py" -ErrorAction SilentlyContinue | ForEach-Object {
    $lines = Get-Content $_.FullName -Encoding UTF8
    for ($i = 0; $i -lt $lines.Count; $i++) {
        # 匹配 pydantic 模型的 .dict() 或 .json() 调用（排除普通 dict/json）
        if ($lines[$i] -match '\.dict\(\)' -and $lines[$i] -notmatch 'model_dump') {
            # 简单判断：如果上下文有 BaseModel，则可能是 pydantic 调用
            $content = Get-Content $_.FullName -Raw -Encoding UTF8
            if ($content -match 'BaseModel' -or $content -match 'pydantic') {
                $lineNum = $i + 1
                Write-Host "  [WARN] 疑似 Pydantic 1.x .dict() L${lineNum}: $(Get-RelPath $_.FullName)" -ForegroundColor DarkYellow
                $WARN_COUNT++
            }
        }
    }
}

# 检查12：print(traceback.format_exc()) 替代日志
Write-Host "[12/12] 检查 print(traceback.format_exc())..." -ForegroundColor Yellow
Get-ChildItem -Path $SourceDir -Recurse -Filter "*.py" -ErrorAction SilentlyContinue | ForEach-Object {
    $lines = Get-Content $_.FullName -Encoding UTF8
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match 'print\(traceback\.format_exc\(\)\)') {
            $lineNum = $i + 1
            Write-Host "  [WARN] 应用 logger.error 替代 print(traceback) L${lineNum}: $(Get-RelPath $_.FullName)" -ForegroundColor DarkYellow
            $WARN_COUNT++
        }
    }
}

# 检查13：技能定义健康度（3 个 SKILL.md 的 frontmatter 和编码质量）
Write-Host "[13/13] 检查技能定义健康度..." -ForegroundColor Yellow
$SkillsDir = Join-Path $ProjectRoot ".trae\skills"
$SkillTargets = @(
    "xianyu-hunter-dev",
    "xianyu-backend-code-review",
    "xianyu-frontend-code-review"
)
foreach ($skillName in $SkillTargets) {
    $skillFile = Join-Path $SkillsDir "$skillName\SKILL.md"
    if (-not (Test-Path $skillFile)) {
        Write-Host "  [WARN] 技能文件不存在: $skillName/SKILL.md" -ForegroundColor DarkYellow
        $WARN_COUNT++
        continue
    }
    $content = Get-Content $skillFile -Raw -Encoding UTF8

    # 13.1 检查 PUA 字符
    $puaCount = 0
    foreach ($c in $content.ToCharArray()) {
        $code = [int][char]$c
        if ($code -ge 0xE000 -and $code -le 0xF8FF) {
            $puaCount++
        }
    }
    if ($puaCount -gt 0) {
        Write-Host "  [BLOCK] $skillName/SKILL.md 含 $puaCount 个 PUA 字符（双重编码乱码）" -ForegroundColor Red
        $ISSUE_COUNT++
    }

    # 13.2 检查 U+FFFD 替换字符
    $fffdCount = ([regex]::Matches($content, [char]0xFFFD)).Count
    if ($fffdCount -gt 0) {
        Write-Host "  [BLOCK] $skillName/SKILL.md 含 $fffdCount 个 U+FFFD 替换字符" -ForegroundColor Red
        $ISSUE_COUNT++
    }

    # 13.3 检查 frontmatter 完整性
    if ($content -notmatch '^---\r?\nname:\s*"[^"]+"') {
        Write-Host "  [BLOCK] $skillName/SKILL.md 缺少有效的 YAML frontmatter name 字段" -ForegroundColor Red
        $ISSUE_COUNT++
    }

    # 13.4 检查 frontmatter 关键字段
    foreach ($field in @('description', 'whenToUse', 'triggers')) {
        if ($content -notmatch "(?ms)${field}:") {
            Write-Host "  [WARN] $skillName/SKILL.md 缺少 frontmatter ${field} 字段" -ForegroundColor DarkYellow
            $WARN_COUNT++
        }
    }

    if ($puaCount -eq 0 -and $fffdCount -eq 0) {
        Write-Host "  [OK] $skillName/SKILL.md 编码健康" -ForegroundColor Green
    }
}

# 汇总
Write-Host "`n========== 扫描完成 ==========" -ForegroundColor Cyan
if ($ISSUE_COUNT -eq 0 -and $WARN_COUNT -eq 0) {
    Write-Host "未发现阻塞级问题，可以继续人工审查。" -ForegroundColor Green
} elseif ($ISSUE_COUNT -eq 0) {
    Write-Host "未发现阻塞级问题，但有 $WARN_COUNT 个警告，建议修复后继续。" -ForegroundColor Yellow
} else {
    Write-Host "发现 $ISSUE_COUNT 个阻塞级问题（必须修复），$WARN_COUNT 个警告。" -ForegroundColor Red
    Write-Host "请修复阻塞级问题后再提交。" -ForegroundColor Red
}
