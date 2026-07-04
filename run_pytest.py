#!/usr/bin/env python
# -*- coding: utf-8 -*-
import subprocess
import sys
import os

log_path = r"d:\code\otherProjects\17_xianyu\docs\04-系统维护\sonar-reports\pytest_full.log"
if os.path.exists(log_path):
    os.remove(log_path)

result = subprocess.run(
    [sys.executable, "-m", "pytest",
     "tests/test_login_orchestrator.py",
     "-v", "--tb=short", "-p", "no:cacheprovider"],
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
    cwd=r"d:\code\otherProjects\17_xianyu",
)

# 立即写
with open(log_path, "wb") as f:
    f.write(b"=== ENTRY ===\n")
    f.write(f"Exit: {result.returncode}\n".encode("utf-8"))
    f.write(b"=== STDOUT ===\n")
    f.write(result.stdout.encode("utf-8"))
    f.write(b"\n=== STDERR ===\n")
    f.write(result.stderr.encode("utf-8"))

print(f"File size: {os.path.getsize(log_path)}")
print(f"Exit code: {result.returncode}")
print("--- Last 30 lines of stdout ---")
print("\n".join(result.stdout.splitlines()[-30:]))
