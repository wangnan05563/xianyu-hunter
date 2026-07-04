#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""查询 SonarQube 状态"""
import os
import sys
import json
import time
import urllib.request
import urllib.error
import base64

LOG = r"D:\code\otherProjects\17_xianyu\docs\04-系统维护\sonar-reports\sonar-status.log"

if os.path.exists(LOG):
    os.remove(LOG)

lines = []

def w(msg):
    lines.append(msg)

w("=" * 60)
w("SonarQube Status Query")
w("=" * 60)
w("Time: " + time.strftime("%Y-%m-%d %H:%M:%S"))

BASE_URL = "http://localhost:9000"
TOKEN = "GLOBAL_ANALYSIS_TOKEN"
AUTH = base64.b64encode(f"{TOKEN}:".encode()).decode()

# 1. OPEN issues
w("\n[1] Query OPEN issues...")
try:
    url = f"{BASE_URL}/api/issues/search"
    params = "projectKeys=xianyu_hunter&statuses=OPEN&ps=1&facets=severities,rules"
    req = urllib.request.Request(f"{url}?{params}", headers={"Authorization": f"Basic {AUTH}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        total = data.get("paging", {}).get("total", 0)
        w(f"OPEN total: {total}")
        for facet in data.get("facets", []):
            name = facet.get("property")
            if name == "severities":
                w("\nBy severity:")
                for v in facet.get("values", []):
                    w(f"  {v.get('val')}: {v.get('count', 0)}")
            elif name == "rules":
                w("\nBy rule Top 25:")
                for v in facet.get("values", [])[:25]:
                    w(f"  {v.get('val')}: {v.get('count', 0)}")
except urllib.error.HTTPError as e:
    body = e.read().decode("utf-8", errors="ignore")[:500]
    w(f"HTTP Error {e.code}: {body}")
except Exception as e:
    w(f"Error: {type(e).__name__}: {e}")

# 2. Quality gate
w("\n[2] Query quality gate...")
try:
    url = f"{BASE_URL}/api/qualitygates/project_status?projectKey=xianyu_hunter"
    req = urllib.request.Request(url, headers={"Authorization": f"Basic {AUTH}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        qg = data.get("projectStatus", {})
        w(f"\n[Quality Gate] {qg.get('status', 'N/A')}")
        for c in qg.get("conditions", []):
            w(f"  {c.get('metricKey')}: {c.get('status')}")
except Exception as e:
    w(f"QG Error: {type(e).__name__}: {e}")

content = "\n".join(lines) + "\n"
# 用 wb 模式
with open(LOG, "wb") as f:
    f.write(content.encode("utf-8"))

print(f"Log written: {LOG}")
print(f"Size: {os.path.getsize(LOG)} bytes")
