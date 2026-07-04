#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查 SonarQube 服务"""
import urllib.request
import urllib.error
import json

# 不用 token 试一下
url = "http://localhost:9000/api/system/status"
try:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print(f"Server status: {data}")
except Exception as e:
    print(f"Error: {e}")

# 检查 api 访问
url = "http://localhost:9000/api/authentication/validate"
try:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print(f"Auth validate (no token): {data}")
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}: {e.read().decode('utf-8', errors='ignore')[:200]}")
except Exception as e:
    print(f"Error: {e}")

# 试不同的 token
import base64
tokens = ["GLOBAL_ANALYSIS_TOKEN", "squ_xxx", "admin:admin"]
for tok in tokens:
    try:
        auth = base64.b64encode(f"{tok}:".encode()).decode() if ":" not in tok else base64.b64encode(tok.encode()).decode()
        url = f"http://localhost:9000/api/issues/search?projectKeys=xianyu_hunter&ps=1"
        req = urllib.request.Request(url, headers={"Authorization": f"Basic {auth}"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"Token {tok!r}: OK total={data.get('paging', {}).get('total', 0)}")
    except urllib.error.HTTPError as e:
        print(f"Token {tok!r}: HTTP {e.code}")
    except Exception as e:
        print(f"Token {tok!r}: Error {e}")
