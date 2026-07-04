#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import time

p = r"D:\code\otherProjects\17_xianyu\docs\04-系统维护\sonar-reports\sonar-status.log"
if os.path.exists(p):
    os.remove(p)

# 用 wb 模式
with open(p, "wb") as f:
    f.write(f"test {time.time()}\n".encode("utf-8"))

# 验证
if os.path.exists(p):
    print(f"OK: size={os.path.getsize(p)}")
else:
    print("FAIL: file not created")
