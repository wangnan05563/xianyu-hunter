# 以调试端口启动 Edge，用于 CDP 方式导入 Cookie
#
# 使用独立 Debug 目录避免与用户日常浏览器冲突
# Chrome 136+ 要求 --remote-debugging-port 必须配合 --user-data-dir 指向非标准目录
#
# 首次运行需在打开的浏览器中登录闲鱼，之后 Cookie 会持久化在 Debug 目录

$debugProfile = "$env:LOCALAPPDATA\Microsoft\Edge\User Data\Debug"

# 查找 Edge 可执行文件
$edgePaths = @(
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
)
$edgePath = $edgePaths | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $edgePath) {
    Write-Host "未找到 Edge 浏览器，请确认已安装 Microsoft Edge" -ForegroundColor Red
    exit 1
}

Write-Host "启动 Edge 调试实例..." -ForegroundColor Green
Write-Host "  端口: 9222" -ForegroundColor Cyan
Write-Host "  Profile: $debugProfile" -ForegroundColor Cyan
Write-Host ""
Write-Host "浏览器启动后，请登录闲鱼，然后调用:" -ForegroundColor Yellow
Write-Host "  POST http://localhost:8001/api/auth/import-from-browser/cdp" -ForegroundColor Yellow

& $edgePath `
    --remote-debugging-port=9222 `
    --user-data-dir="$debugProfile" `
    --remote-allow-origins=* `
    "https://www.goofish.com/"
