#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""诊断脚本：检查 project key 过滤是否生效。"""
import json
import os
import base64
import urllib.request
import urllib.error
import urllib.parse

TOKEN = "sqa_fe4b774b40e19eca12e0f46a2f2f771f2d1a23bd"
AUTH = base64.b64encode(f"{TOKEN}:".encode()).decode()
OUT = r"d:\code\otherProjects\17_xianyu\docs\04-系统维护\sonar-reports\diag.json"


def get_json(url, params):
    qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    req = urllib.request.Request(f"{url}?{qs}", headers={"Authorization": f"Basic {AUTH}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}", "body": e.read().decode("utf-8", errors="ignore")[:500]}
    except Exception as e:
        return {"error": str(e)}


# 取 5 个 OPEN issues 的实际 component
data = get_json("http://localhost:9000/api/issues/search", {
    "projectKeys": "xianyu_hunter",
    "statuses": "OPEN",
    "ps": 10,
})

# 也取 java 规则的，看 component
java_data = get_json("http://localhost:9000/api/issues/search", {
    "projectKeys": "xianyu_hunter",
    "statuses": "OPEN",
    "rules": "java:S1192",
    "ps": 5,
})

diag = {
    "sample_issues": [
        {
            "key": i.get("key"),
            "rule": i.get("rule"),
            "severity": i.get("severity"),
            "component": i.get("component"),
            "project": i.get("project"),
        }
        for i in data.get("issues", [])
    ],
    "java_s1192_count": java_data.get("paging", {}).get("total", "ERR"),
    "java_s1192_sample": [
        {"component": i.get("component"), "project": i.get("project"), "rule": i.get("rule")}
        for i in java_data.get("issues", [])
    ],
    "paging": data.get("paging"),
}

# 再按 project facet 查
pf = get_json("http://localhost:9000/api/issues/search", {
    "projectKeys": "xianyu_hunter",
    "statuses": "OPEN",
    "ps": 1,
    "facets": "projects",
})
diag["by_project"] = pf.get("facets", [])

# 不带 projectKeys，看 java:S1192 总数
all_data = get_json("http://localhost:9000/api/issues/search", {
    "statuses": "OPEN",
    "rules": "java:S1192",
    "ps": 1,
    "facets": "projects",
})
diag["all_java_s1192_by_project"] = all_data.get("facets", [])

# 验证 project xianyu_hunter
proj = get_json("http://localhost:9000/api/projects/search", {"q": "xianyu_hunter"})
diag["project_search"] = proj

# 验证 components
comp = get_json("http://localhost:9000/api/components/tree", {
    "component": "xianyu_hunter",
    "ps": 20,
})
diag["components"] = [{"key": c.get("key"), "name": c.get("name"), "language": c.get("language")} for c in comp.get("components", [])]

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(diag, f, ensure_ascii=False, indent=2)
print(f"Written to {OUT}")
