#!/usr/bin/env python
# -*- coding: utf-8 -*-
import subprocess
import sys
import os
import time

# 直接写入目标目录
log_path = r"d:\code\otherProjects\17_xianyu\docs\04-系统维护\sonar-reports\fetch_new.log"
if os.path.exists(log_path):
    os.remove(log_path)

# 测试1: 直接写
with open(log_path, "w", encoding="utf-8") as f:
    f.write(f"Direct write OK: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

# 测试2: 调用 SonarQube API
import json
import urllib.request
import urllib.error
import base64
import urllib.parse

BASE_URL = "http://localhost:9000"
TOKEN = "GLOBAL_ANALYSIS_TOKEN"
AUTH = base64.b64encode(f"{TOKEN}:".encode()).decode()

with open(log_path, "a", encoding="utf-8") as f:
    try:
        url = f"{BASE_URL}/api/issues/search?projectKeys=xianyu_hunter&statuses=OPEN&ps=1&facets=severities"
        req = urllib.request.Request(url, headers={"Authorization": f"Basic {AUTH}"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            total = data.get("paging", {}).get("total", 0)
            f.write(f"API OK: total={total}\n")
            for facet in data.get("facets", []):
                if facet.get("property") == "severities":
                    for v in facet.get("values", []):
                        f.write(f"  {v.get('val')}: {v.get('count', 0)}\n")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")[:500]
        f.write(f"HTTP Error: {e.code}\n{body}\n")
    except Exception as e:
        f.write(f"Exception: {type(e).__name__}: {e}\n")

print(f"Log size: {os.path.getsize(log_path)}")
