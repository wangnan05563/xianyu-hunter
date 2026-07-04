#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
p = r"d:\code\otherProjects\17_xianyu\docs\04-系统维护\sonar-reports\sonar-status.log"
if os.path.exists(p):
    os.remove(p)
with open(p, "w", encoding="utf-8") as f:
    f.write("simple write test\n")
print(f"size: {os.path.getsize(p)}")
