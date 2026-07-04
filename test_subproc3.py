#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys

# 通过 subprocess 写入
result = __import__('subprocess').run(
    [sys.executable, "-c",
     "import os; "
     "p = r'D:\\code\\otherProjects\\17_xianyu\\docs\\04-系统维护\\sonar-reports\\sonar-status.log'; "
     "os.path.exists(p) and os.remove(p); "
     "open(p, 'wb').write(b'subprocess test OK\\n'); "
     "print('size:', os.path.getsize(p))"],
    capture_output=True, text=True, encoding="utf-8"
)

print("returncode:", result.returncode)
print("stdout:", result.stdout)
print("stderr:", result.stderr)
