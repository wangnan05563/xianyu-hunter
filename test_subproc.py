#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""通过 subprocess 写入文件"""
import subprocess
import sys

result = subprocess.run([
    sys.executable, "-c",
    "import os; "
    "p = r'D:\\code\\otherProjects\\17_xianyu\\docs\\04-系统维护\\sonar-reports\\sonar-status.log'; "
    "os.path.exists(p) and os.remove(p); "
    "open(p, 'w', encoding='utf-8').write('subprocess write OK\\n'); "
    "print('size:', os.path.getsize(p))"
], capture_output=True, text=True, encoding="utf-8", cwd=r"D:\code\otherProjects\17_xianyu")

print("returncode:", result.returncode)
print("stdout:", result.stdout)
print("stderr:", result.stderr)
