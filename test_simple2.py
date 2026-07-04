#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import os
import time

LOG = r"d:\code\otherProjects\17_xianyu\docs\04-系统维护\sonar-reports\sonar-status.log"

# Force remove and create
if os.path.exists(LOG):
    os.remove(LOG)

# Just write
with open(LOG, "w", encoding="utf-8") as f:
    f.write(f"hello world at {time.time()}\n")

print(f"Log path: {LOG}")
print(f"Log size after write: {os.path.getsize(LOG) if os.path.exists(LOG) else 'NOT EXISTS'}")
