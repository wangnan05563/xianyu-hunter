#!/usr/bin/env python
# -*- coding: utf-8 -*-
import subprocess
import sys

result = subprocess.run(
    [sys.executable, "d:\\code\\otherProjects\\17_xianyu\\test_simple5.py"],
    capture_output=True, text=True, encoding="utf-8"
)
print(f"returncode: {result.returncode}")
print(f"stdout: {result.stdout}")
print(f"stderr: {result.stderr}")
