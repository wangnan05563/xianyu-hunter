#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""用 subprocess.run 写文件 - 模仿 run_pytest.py"""
import subprocess
import sys
import os

# 1. 删除旧文件
p = r"D:\code\otherProjects\17_xianyu\docs\04-系统维护\sonar-reports\sonar-status.log"
if os.path.exists(p):
    os.remove(p)

# 2. 通过 subprocess 写
result = subprocess.run(
    [sys.executable, "-c",
     f"import os; open({p!r}, 'w', encoding='utf-8').write('subprocess write OK\\n'); print('size:', os.path.getsize({p!r}))"],
    capture_output=True, text=True, encoding="utf-8", cwd=r"D:\code\otherProjects\17_xianyu"
)

# 3. 写日志
log_path = r"D:\code\otherProjects\17_xianyu\docs\04-系统维护\sonar-reports\run_subprocess.log"
if os.path.exists(log_path):
    os.remove(log_path)
with open(log_path, "w", encoding="utf-8") as f:
    f.write(f"returncode: {result.returncode}\n")
    f.write(f"stdout: {result.stdout}\n")
    f.write(f"stderr: {result.stderr}\n")
    f.write(f"target file exists: {os.path.exists(p)}\n")
    if os.path.exists(p):
        f.write(f"target file size: {os.path.getsize(p)}\n")
    f.write(f"log file size: {os.path.getsize(log_path)}\n")
