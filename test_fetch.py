#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import os
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"d:\code\otherProjects\17_xianyu\docs\04-系统维护\sonar-reports")
import fetch_status
try:
    fetch_status.main()
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
print(f"\nLog exists: {os.path.exists(fetch_status.LOG)}")
print(f"Log size: {os.path.getsize(fetch_status.LOG) if os.path.exists(fetch_status.LOG) else 'N/A'}")
print(f"JSON exists: {os.path.exists(fetch_status.OUTPUT)}")
