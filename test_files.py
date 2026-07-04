#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os

# Test 1: 在 sonar-reports 创建 .log
p1 = r"d:\code\otherProjects\17_xianyu\docs\04-系统维护\sonar-reports\test1.log"
# Test 2: 在 sonar-reports 创建 .txt
p2 = r"d:\code\otherProjects\17_xianyu\docs\04-系统维护\sonar-reports\test2.txt"
# Test 3: 在根目录创建 .log
p3 = r"d:\code\otherProjects\17_xianyu\test3.log"

for p in [p1, p2, p3]:
    try:
        if os.path.exists(p):
            os.remove(p)
        with open(p, "w", encoding="utf-8") as f:
            f.write(f"test {p}\n")
        print(f"OK: {p} (size={os.path.getsize(p)})")
    except Exception as e:
        print(f"FAIL: {p} - {e}")
