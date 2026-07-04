#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import time

# Test path
LOG = "D:/code/otherProjects/17_xianyu/docs/04-系统维护/sonar-reports/sonar-status.log"
print(f"Target: {LOG}")

# Remove if exists
if os.path.exists(LOG):
    os.remove(LOG)

# Write
try:
    with open(LOG, "w", encoding="utf-8") as f:
        f.write(f"Test OK: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    print(f"Written, size: {os.path.getsize(LOG)}")
except Exception as e:
    print(f"Error: {e}")

# Also try subprocessing
import subprocess
import sys
result = subprocess.run([sys.executable, "-c", f"import os; open({LOG!r}, 'w').write('subprocess OK')"], capture_output=True, text=True)
print(f"Subprocess: rc={result.returncode}, out={result.stdout!r}, err={result.stderr!r}")
if os.path.exists(LOG):
    print(f"Final size: {os.path.getsize(LOG)}")
