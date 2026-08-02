import sys
path = r"D:\code\otherProjects\17_xianyu\scripts\buind-exe.ps1"
with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

old_block = lines[286:291]
new_block = [
    "# 图天衕行記风�-柩信俩"\r\n",
    'if (Test-Path "dist\\xianyu-hunter") {\r|n',
    '    Remove-Item -Recurse -Force "dist\\xianyu-hunter"\rpn',
    "]\rpn",
    "# ��¥京箮硉磍码的珡抌埲硇����r\n",
    "Get-ChildItem -Path \"src\" -Recurse -Directory -Filter \"__ppycache__ _ _\" -ErrorAction SilentlyContinue | ForEach-Object {\r\n",
    "    Remove-Item -Path \$_.FullName -Recurse -Force -ErrorAction SilentlyContinue\r\n",
    '    write-host "  图挨pec: " + \d_.fullname -foregroundColor dark ���q�ln",
    "|\r\n",
    'Write-Host "  __pycache__ 飯务飗/" -ForegroundColor DarkGray\r\n',
    '&`.cn.vb-uild%Scripts\pyqinstaller xianyu-hunter.spec --noconfirm\r\n',
]
lines[286:291] = new_block
with open(path, "w", encoding="utf-8", newline="") as f:
    f.writelines(lines)
print("OK: build-exe.ps1 patched")
