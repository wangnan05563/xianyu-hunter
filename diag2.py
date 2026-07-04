#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""精确抓取 xianyu_hunter 项目当前状态。

使用 components= 而非 projectKeys=，避免模糊匹配。
"""
import json
import os
import base64
import urllib.request
import urllib.error
import urllib.parse

BASE_URL = "http://localhost:9000"
TOKEN = "sqa_fe4b774b40e19eca12e0f46a2f2f771f2d1a23bd"
AUTH = base64.b64encode(f"{TOKEN}:".encode()).decode()
OUT = r"d:\code\otherProjects\17_xianyu\docs\04-系统维护\sonar-reports\diag2.json"


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


# 精确匹配
sev = get_json(f"{BASE_URL}/api/issues/search", {
    "components": "xianyu_hunter",
    "statuses": "OPEN",
    "ps": 1,
    "facets": "severities",
})
rules = get_json(f"{BASE_URL}/api/issues/search", {
    "components": "xianyu_hunter",
    "statuses": "OPEN",
    "ps": 1,
    "facets": "rules",
})
qg = get_json(f"{BASE_URL}/api/qualitygates/project_status", {
    "projectKey": "xianyu_hunter",
})

result = {
    "method": "components=xianyu_hunter 精确匹配",
    "open_total": sev.get("paging", {}).get("total", 0),
    "by_severity": [],
    "top_rules": [],
    "quality_gate": None,
}

for facet in sev.get("facets", []):
    if facet.get("property") == "severities":
        for v in facet.get("values", []):
            result["by_severity"].append({"val": v.get("val"), "count": v.get("count", 0)})

for facet in rules.get("facets", []):
    if facet.get("property") == "rules":
        for v in facet.get("values", [])[:30]:
            result["top_rules"].append({"val": v.get("val"), "count": v.get("count", 0)})

if "projectStatus" in qg:
    ps = qg["projectStatus"]
    result["quality_gate"] = {
        "status": ps.get("status"),
        "conditions": [
            {"metricKey": c.get("metricKey"), "status": c.get("status"),
             "value": c.get("value"), "errorThreshold": c.get("errorThreshold")}
            for c in ps.get("conditions", [])
        ],
    }

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(f"Written to {OUT}")
print(f"OPEN total: {result['open_total']}")
for s in result["by_severity"]:
    print(f"  {s['val']}: {s['count']}")
print("Top rules:")
for r in result["top_rules"][:20]:
    print(f"  {r['val']}: {r['count']}")
