#!/usr/bin/env python3
"""分页统计 OPEN 状态问题。"""
import json
import urllib.request
import base64
import urllib.parse

URL = "http://localhost:9000/api/issues/search"
TOKEN = "GLOBAL_ANALYSIS_TOKEN"
auth = base64.b64encode(f"{TOKEN}:".encode()).decode()
OUT = r"d:\code\otherProjects\17_xianyu\docs\04-系统维护\sonar-reports\sonar-current-status.json"


def fetch_page(p, ps=500):
    params = {
        "projectKeys": "xianyu_hunter",
        "statuses": "OPEN",
        "ps": ps,
        "p": p,
        "facets": "severities,rules,files",
    }
    qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    req = urllib.request.Request(f"{URL}?{qs}", headers={"Authorization": f"Basic {auth}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


data = fetch_page(1, 500)
total = data.get("paging", {}).get("total", 0)
result = {
    "total_open": total,
    "fetched": len(data.get("issues", [])),
    "by_severity": [],
    "by_rule_top20": [],
    "by_file_top20": [],
    "all_open_keys_sample": [],
}
for facet in data.get("facets", []):
    name = facet.get("property")
    items = [{"val": v.get("val"), "count": v.get("count", 0)} for v in facet.get("values", [])]
    if name == "severities":
        result["by_severity"] = items
    elif name == "rules":
        result["by_rule_top20"] = items[:20]
        result["by_rule_all"] = items
    elif name == "files":
        result["by_file_top20"] = items[:20]
        result["by_file_all"] = items

for issue in data.get("issues", [])[:30]:
    result["all_open_keys_sample"].append({
        "key": issue.get("key"),
        "rule": issue.get("rule"),
        "severity": issue.get("severity"),
        "component": issue.get("component"),
        "line": issue.get("textRange", {}).get("startLine"),
        "message": issue.get("message"),
    })

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print("OPEN总数:", result["total_open"])
print("已抓取:", result["fetched"])
print("\n按严重度:")
for s in result["by_severity"]:
    print(f"  {s['val']:12s} {s['count']:>5d}")
print("\n按规则 Top 10:")
for r in result["by_rule_top20"][:10]:
    print(f"  {r['val']:30s} {r['count']:>5d}")
print("\n按文件 Top 10:")
for f in result["by_file_top20"][:10]:
    print(f"  {f['val']:60s} {f['count']:>5d}")
