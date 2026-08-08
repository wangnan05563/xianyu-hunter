# ========== 闲鱼猎人前端代码阻塞级问题自动扫描 v4.6.0 ==========
# 扫描 frontend/src/ 下的 .ts/.tsx/.js 文件，检查阻塞级问题（12 项基础 + v4.6.0 新增）
# 🆕v4.6.0 新增检查 13：F-REVIEW-MULTI-WRITE-ENTRY-FRONTEND（多源状态同步统一入口）
# 用法：pwsh .trae/skills/xianyu-frontend-code-review/scripts/auto-scan.ps1

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..\..")).Path
$SourceDir = Join-Path $ProjectRoot "frontend\src"
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

Write-Host "========== 闲鱼猎人前端代码预检 ==========" -ForegroundColor Cyan
Write-Host "源码目录: $SourceDir`n" -ForegroundColor Gray

# 收集所有待扫描文件（排除测试、声明、构建产物）
$Files = Get-ChildItem -Path $SourceDir -Recurse -Include "*.ts", "*.tsx", "*.js" -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notmatch "\\__tests__\\" -and $_.FullName -notmatch "\.test\." -and $_.FullName -notmatch "\.d\.ts$" -and $_.FullName -notmatch "\\node_modules\\" -and $_.FullName -notmatch "\\dist\\" }

# 检查1：fetch 请求缺少 credentials: 'include'
Write-Host "[1/12] 检查 fetch credentials..." -ForegroundColor Yellow
foreach ($file in $Files) {
    $lines = Get-Content $file.FullName -Encoding UTF8
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match 'fetch\s*\(' -and $lines[$i] -notmatch 'credentials') {
            # 向下查找 5 行内是否包含 credentials（多行调用）
            $multiLineHasCreds = $false
            for ($j = $i; $j -lt [Math]::Min($i + 6, $lines.Count); $j++) {
                if ($lines[$j] -match 'credentials') { $multiLineHasCreds = $true; break }
            }
            if (-not $multiLineHasCreds) {
                $lineNum = $i + 1
                Write-Host "  [BLOCK] fetch 缺少 credentials: 'include' L${lineNum}: $(Get-RelPath $file.FullName)" -ForegroundColor Red
                $ISSUE_COUNT++
            }
        }
    }
}

# 检查2：axios.create 缺少 withCredentials: true
Write-Host "[2/12] 检查 axios withCredentials..." -ForegroundColor Yellow
foreach ($file in $Files) {
    $lines = Get-Content $file.FullName -Encoding UTF8
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match 'axios\.create\s*\(') {
            $multiLineHasCreds = $false
            for ($j = $i; $j -lt [Math]::Min($i + 6, $lines.Count); $j++) {
                if ($lines[$j] -match 'withCredentials') { $multiLineHasCreds = $true; break }
            }
            if (-not $multiLineHasCreds) {
                $lineNum = $i + 1
                Write-Host "  [BLOCK] axios.create 缺少 withCredentials: true L${lineNum}: $(Get-RelPath $file.FullName)" -ForegroundColor Red
                $ISSUE_COUNT++
            }
        }
    }
}

# 检查3：token 写入 localStorage
Write-Host "[3/12] 检查 localStorage 存储 token..." -ForegroundColor Yellow
foreach ($file in $Files) {
    $lines = Get-Content $file.FullName -Encoding UTF8
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match 'localStorage\.(setItem|getItem)\s*\(' -and $lines[$i] -match 'token') {
            $lineNum = $i + 1
            Write-Host "  [BLOCK] token 写入/读取 localStorage L${lineNum}: $(Get-RelPath $file.FullName)" -ForegroundColor Red
            $ISSUE_COUNT++
        }
    }
}

# 检查4：dangerouslySetInnerHTML 使用
Write-Host "[4/12] 检查 dangerouslySetInnerHTML..." -ForegroundColor Yellow
foreach ($file in $Files) {
    $lines = Get-Content $file.FullName -Encoding UTF8
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match 'dangerouslySetInnerHTML') {
            $lineNum = $i + 1
            Write-Host "  [BLOCK] 使用 dangerouslySetInnerHTML 存在 XSS 风险 L${lineNum}: $(Get-RelPath $file.FullName)" -ForegroundColor Red
            $ISSUE_COUNT++
        }
    }
}

# 检查5：any 类型使用
Write-Host "[5/12] 检查 any 类型..." -ForegroundColor Yellow
foreach ($file in $Files) {
    $lines = Get-Content $file.FullName -Encoding UTF8
    for ($i = 0; $i -lt $lines.Count; $i++) {
        # 匹配 :any 但排除注释和字符串
        if ($lines[$i] -match ':\s*any\b' -and $lines[$i] -notmatch '^\s*//' -and $lines[$i] -notmatch '^\s*\*') {
            $lineNum = $i + 1
            Write-Host "  [WARN] 使用 any 类型 L${lineNum}: $(Get-RelPath $file.FullName)" -ForegroundColor DarkYellow
            $WARN_COUNT++
        }
    }
}

# 检查6：空 catch 块
Write-Host "[6/12] 检查空 catch 块..." -ForegroundColor Yellow
foreach ($file in $Files) {
    $lines = Get-Content $file.FullName -Encoding UTF8
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match '\.catch\s*\(\s*\)' -or ($lines[$i] -match 'catch\s*\(' -and $i + 1 -lt $lines.Count -and $lines[$i + 1] -match '^\s*\}\s*$')) {
            $lineNum = $i + 1
            Write-Host "  [WARN] 空 catch 块 L${lineNum}: $(Get-RelPath $file.FullName)" -ForegroundColor DarkYellow
            $WARN_COUNT++
        }
    }
}

# 检查7：enum 使用（应用字符串字面量联合）
Write-Host "[7/12] 检查 enum 使用..." -ForegroundColor Yellow
foreach ($file in $Files) {
    $lines = Get-Content $file.FullName -Encoding UTF8
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match '^\s*enum\s+\w+') {
            $lineNum = $i + 1
            Write-Host "  [WARN] 应用字符串字面量联合替代 enum L${lineNum}: $(Get-RelPath $file.FullName)" -ForegroundColor DarkYellow
            $WARN_COUNT++
        }
    }
}

# 检查8：index 作为 key
Write-Host "[8/12] 检查 index 作为 key..." -ForegroundColor Yellow
foreach ($file in $Files) {
    $lines = Get-Content $file.FullName -Encoding UTF8
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match 'key\s*=\s*\{\s*(index|i|idx)\s*\}') {
            $lineNum = $i + 1
            Write-Host "  [BLOCK] 使用 index 作为 key L${lineNum}: $(Get-RelPath $file.FullName)" -ForegroundColor Red
            $ISSUE_COUNT++
        }
    }
}

# 检查9：JSON.parse(JSON.stringify()) 深拷贝
Write-Host "[9/12] 检查 JSON 深拷贝..." -ForegroundColor Yellow
foreach ($file in $Files) {
    $lines = Get-Content $file.FullName -Encoding UTF8
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match 'JSON\.parse\s*\(\s*JSON\.stringify\s*\(') {
            $lineNum = $i + 1
            Write-Host "  [BLOCK] 用 structuredClone 替代 JSON 深拷贝 L${lineNum}: $(Get-RelPath $file.FullName)" -ForegroundColor Red
            $ISSUE_COUNT++
        }
    }
}

# 检查10：箭头函数组件（应用 function 关键字）
Write-Host "[10/12] 检查箭头函数组件..." -ForegroundColor Yellow
foreach ($file in $Files) {
    if ($file.Name -notmatch '\.tsx$') { continue }
    $lines = Get-Content $file.FullName -Encoding UTF8
    for ($i = 0; $i -lt $lines.Count; $i++) {
        # 匹配 const Component = (props) => (<... 或 const Component: React.FC = ...
        if ($lines[$i] -match '^\s*const\s+[A-Z]\w*\s*[:=].*=>\s*\(?<') {
            $lineNum = $i + 1
            Write-Host "  [WARN] 应用 function 关键字定义组件 L${lineNum}: $(Get-RelPath $file.FullName)" -ForegroundColor DarkYellow
            $WARN_COUNT++
        }
    }
}

# 检查11：ConfigProvider 必须在 BrowserRouter 外层（main.tsx 专项）
Write-Host "[11/12] 检查 ConfigProvider 位置（main.tsx）..." -ForegroundColor Yellow
$mainTsx = Join-Path $SourceDir "main.tsx"
if (Test-Path $mainTsx) {
    $content = Get-Content $mainTsx -Raw -Encoding UTF8
    # 通过查找 ConfigProvider 和 BrowserRouter 出现顺序判断
    $cfgIdx = $content.IndexOf("ConfigProvider")
    $routerIdx = $content.IndexOf("BrowserRouter")
    if ($cfgIdx -ge 0 -and $routerIdx -ge 0 -and $cfgIdx -gt $routerIdx) {
        Write-Host "  [BLOCK] ConfigProvider 应在 BrowserRouter 外层（main.tsx）" -ForegroundColor Red
        $ISSUE_COUNT++
    } elseif ($cfgIdx -ge 0 -and $routerIdx -lt 0) {
        Write-Host "  [INFO] ConfigProvider 已配置，但未发现 BrowserRouter" -ForegroundColor Gray
    } elseif ($cfgIdx -lt 0) {
        Write-Host "  [WARN] main.tsx 未发现 ConfigProvider，主题切换可能不生效" -ForegroundColor DarkYellow
        $WARN_COUNT++
    }
} else {
    Write-Host "  [INFO] main.tsx 不存在，跳过" -ForegroundColor Gray
}

# 检查12：三处映射同步检查（App.tsx, MainLayout.tsx, sheetRegistry.tsx）
Write-Host "[12/12] 检查三处映射同步..." -ForegroundColor Yellow
$threeMappings = @(
    @{ Path = "frontend\src\App.tsx"; Pattern = "lazy\s*\(|<Route"; Desc = "路由声明" },
    @{ Path = "frontend\src\components\layout\MainLayout.tsx"; Pattern = "menuItems"; Desc = "menuItems 菜单注册" },
    @{ Path = "frontend\src\components\SheetWorkspace\sheetRegistry.tsx"; Pattern = "registerSheet|path:"; Desc = "path → component 映射" }
)
foreach ($mapping in $threeMappings) {
    $fullPath = Join-Path $ProjectRoot $mapping.Path
    if (Test-Path $fullPath) {
        $content = Get-Content $fullPath -Raw -Encoding UTF8
        if (-not ($content -match $mapping.Pattern)) {
            Write-Host "  [WARN] $($mapping.Path) 未发现 $($mapping.Desc) 模式" -ForegroundColor DarkYellow
            $WARN_COUNT++
        }
    } else {
        Write-Host "  [WARN] $($mapping.Path) 不存在（$($mapping.Desc)）" -ForegroundColor DarkYellow
        $WARN_COUNT++
    }
}

# 检查13（🆕v4.6.0）：F-REVIEW-MULTI-WRITE-ENTRY-FRONTEND 多源状态同步统一入口
# 检测多组件独立 useEffect + fetch 拉取相同状态的反模式
Write-Host "[13/13] 检查多源状态同步统一入口（F-REVIEW-MULTI-WRITE-ENTRY-FRONTEND）..." -ForegroundColor Yellow
# 维护统一状态 Hook 白名单（从 config.yaml.state_sync_frontend.unified_state_hooks.hooks 同步）
$unifiedStateHooks = @(
    "useCookieLayersStore",
    "useAuthStore",
    "useAppConfigStore"
)
foreach ($file in $Files) {
    if ($file.Name -notmatch '\.tsx?$') { continue }
    $content = Get-Content $file.FullName -Raw -Encoding UTF8
    # 检测 useEffect(() => { ... fetch(...) / axios.get(...) ... }, []) 模式
    $useEffectPattern = 'useEffect\s*\(\s*\(\s*\)\s*=>\s*\{[^}]*?(fetch|axios\.[a-z]+)\s*\('
    if ([regex]::IsMatch($content, $useEffectPattern, [System.Text.RegularExpressions.RegexOptions]::Singleline)) {
        # 检查是否调用了统一状态 Hook（白名单）
        $usesUnifiedHook = $false
        foreach ($hook in $unifiedStateHooks) {
            if ($content -match [regex]::Escape($hook)) { $usesUnifiedHook = $true; break }
        }
        if (-not $usesUnifiedHook) {
            Write-Host "  [WARN] 多组件独立 useEffect 拉取状态，未使用统一 Hook（如 $($unifiedStateHooks -join '/')） L1: $(Get-RelPath $file.FullName)" -ForegroundColor DarkYellow
            $WARN_COUNT++
        }
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
