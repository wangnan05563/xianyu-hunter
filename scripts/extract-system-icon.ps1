# scripts/extract-system-icon.ps1
# 将 Windows 系统图标（来自 shell32.dll / imageres.dll 等）提取为 .ico 文件
#
# 背景：Inno Setup 的 SetupIconFile 与 PyInstaller 的 --icon 都只接受具体的 .ico 文件，
#       不能直接绑定 “系统图标资源（如 shell32.dll,42）”。本脚本先把系统图标抽取成 .ico，
#       之后就能在 installer.iss 用 SetupIconFile=xxx.ico 复用它。
#
# 用法：
#   powershell -File scripts/extract-system-icon.ps1
#   powershell -File scripts/extract-system-icon.ps1 -SourceDll "C:\Windows\System32\shell32.dll" -Index 3 -OutputIco "assets\system-icon.ico"
#
# 版权提示：系统图标属于 Microsoft，直接打包进分发给第三方的产品存在商标/版权风险，
#   且观感偏“通用”。正式产品建议改用自有品牌图标（本项目已有 assets\xianyu-hunter.ico）。

param(
    [string]$SourceDll = "C:\Windows\System32\imageres.dll",
    [int]$Index = 1,
    [string]$OutputIco = "assets\extracted-system-icon.ico"
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class IconExtractor {
    [DllImport("shell32.dll", CharSet=CharSet.Auto)]
    public static extern uint ExtractIconEx(string lpszFile, int nIconIndex, out IntPtr phiconLarge, out IntPtr phiconSmall, uint nIcons);
    [DllImport("user32.dll")]
    public static extern bool DestroyIcon(IntPtr hIcon);
}
"@

if (-not (Test-Path $SourceDll)) { throw "找不到系统文件: $SourceDll" }

[IntPtr]$hLarge = [IntPtr]::Zero
[IntPtr]$hSmall = [IntPtr]::Zero
$count = [IconExtractor]::ExtractIconEx($SourceDll, $Index, [ref]$hLarge, [ref]$hSmall, 1)
if ($count -eq 0 -or $hLarge -eq [IntPtr]::Zero) { throw "未能从 $SourceDll 提取索引 $Index 的图标" }

function Save-IcoImage($hIcon) {
    if ($hIcon -eq [IntPtr]::Zero) { return $null }
    $icon = [System.Drawing.Icon]::FromHandle($hIcon)
    try {
        $ms = New-Object System.IO.MemoryStream
        $icon.Save($ms)
        return $ms.ToArray()
    } finally {
        $icon.Dispose()
    }
}

$bytesL = Save-IcoImage $hLarge
$bytesS = Save-IcoImage $hSmall

if ($hLarge -ne [IntPtr]::Zero) { [IconExtractor]::DestroyIcon($hLarge) }
if ($hSmall -ne [IntPtr]::Zero) { [IconExtractor]::DestroyIcon($hSmall) }

function Get-IcoData($bytes) {
    if ($null -eq $bytes) { return $null }
    $imageOffset = [BitConverter]::ToUInt32($bytes, 18)   # ICONDIRENTRY.dwImageOffset (entry starts at 6, +12)
    $bytesInRes  = [BitConverter]::ToUInt32($bytes, 14)   # ICONDIRENTRY.dwBytesInRes  (entry starts at 6, +8)
    return $bytes[$imageOffset .. ($imageOffset + $bytesInRes - 1)]
}

function Equals-Array($a, $b) {
    if ($null -eq $a -or $null -eq $b) { return $false }
    if ($a.Length -ne $b.Length) { return $false }
    for ($i = 0; $i -lt $a.Length; $i++) { if ($a[$i] -ne $b[$i]) { return $false } }
    return $true
}

$dataL = Get-IcoData $bytesL
$dataS = Get-IcoData $bytesS

$pairs = @()
if ($null -ne $dataL) { $pairs += @{ e = [byte[]]@($bytesL[6..21]); d = $dataL } }
if ($null -ne $dataS) {
    $dup = $false
    foreach ($p in $pairs) { if (Equals-Array $p.d $dataS) { $dup = $true; break } }
    if (-not $dup) { $pairs += @{ e = [byte[]]@($bytesS[6..21]); d = $dataS } }
}
if ($pairs.Count -eq 0) { throw "提取到的图标数据为空" }

$out = New-Object System.Collections.Generic.List[byte]
$out.Add([byte]0); $out.Add([byte]0); $out.Add([byte]1); $out.Add([byte]0)   # ICONDIR
$out.AddRange([BitConverter]::GetBytes([uint16]$pairs.Count))
$dataStart = 6 + 16 * $pairs.Count
$offset = $dataStart
foreach ($p in $pairs) {
    $entry = $p.e
    [array]::Copy([BitConverter]::GetBytes([uint32]$offset), 0, $entry, 12, 4)
    $out.AddRange($entry)
    $offset += $p.d.Length
}
foreach ($p in $pairs) { $out.AddRange([byte[]]$p.d) }

$dir = Split-Path $OutputIco -Parent
if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
[System.IO.File]::WriteAllBytes($OutputIco, $out.ToArray())

Write-Host "已提取系统图标 -> $OutputIco ($([math]::Round((Get-Item $OutputIco).Length/1KB,1)) KB, $($pairs.Count) 个尺寸)" -ForegroundColor Green
Write-Host "用法：在 installer.iss 中加入  SetupIconFile=$OutputIco" -ForegroundColor DarkGray
