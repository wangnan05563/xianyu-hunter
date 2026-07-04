#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os

LOG = r"d:\code\otherProjects\17_xianyu\docs\04-系统维护\sonar-reports\fetch_test.log"
if os.path.exists(LOG):
    os.remove(LOG)

with open(LOG, "w", encoding="utf-8") as f:
    f.write("Test write 1\n")

import json
import urllib.request
import urllib.error
import base64
import urllib.parse

BASE_URL = "http://localhost:9000"
TOKEN = "GLOBAL_ANALYSIS_TOKEN"
AUTH = base64.b64encode(f"{TOKEN}:".encode()).decode()

with open(LOG, "a", encoding="utf-8") as f:
    f.write(f"TOKEN prefix: {TOKEN[:10]}...\n")
    f.write(f"AUTH length: {len(AUTH)}\n")

    # Try API
    try:
        url = f"{BASE_URL}/api/issues/search?projectKeys=xianyu_hunter&statuses=OPEN&ps=1"
        req = urllib.request.Request(url, headers={"Authorization": f"Basic {AUTH}"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            f.write(f"API OK: total={data.get('paging', {}).get('total', 0)}\n")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")[:500]
        f.write(f"HTTP Error: {e.code}\n{body}\n")
    except Exception as e:
        f.write(f"Exception: {e}\n")

print(f"Log size: {os.path.getsize(LOG)}")
