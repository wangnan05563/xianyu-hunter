#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
p = r"d:\code\otherProjects\17_xianyu\docs\04-系统维护\sonar-reports\test_write.txt"
with open(p, "w", encoding="utf-8") as f:
    f.write("test")
print(f"wrote to: {p}")
print(f"exists: {os.path.exists(p)}")
print(f"size: {os.path.getsize(p)}")
