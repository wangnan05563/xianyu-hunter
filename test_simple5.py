#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys

p = r"D:\code\otherProjects\17_xianyu\docs\04-系统维护\sonar-reports\sonar-status.log"
print(f"1. before remove: exists={os.path.exists(p)}", flush=True)
if os.path.exists(p):
    os.remove(p)
print(f"2. after remove: exists={os.path.exists(p)}", flush=True)

with open(p, "wb") as f:
    f.write(b"hello from simple script\n")
print(f"3. after write: size={os.path.getsize(p)}", flush=True)
