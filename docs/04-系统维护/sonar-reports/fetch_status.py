#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import urllib.request
import urllib.error
import base64
import urllib.parse
import sys
import os

BASE_URL = "http://localhost:9000"
TOKEN = "GLOBAL_ANALYSIS_TOKEN"
AUTH = base64.b64encode(f"{TOKEN}:".encode()).decode()
OUTPUT = r"d:\code\otherProjects\17_xianyu\docs\04-系统维护\sonar-reports\sonar-current-status.json"
LOG = r"d:\code\otherProjects\17_xianyu\docs\04-系统维护\sonar-reports\fetch_status.log"

# 删除旧日志
if os.path.exists(LOG):
    os.remove(LOG)


def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def get_json(url, params):
    query = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    full_url = f"{url}?{query}"
    req = urllib.request.Request(full_url, headers={"Authorization": f"Basic {AUTH}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}", "body": e.read().decode("utf-8", errors="ignore")[:500]}
    except Exception as e:
        return {"error": str(e)}


def main():
    log("=" * 60)
    log("SonarQube Status Query")
    log("=" * 60)

    result = {"fetch_time": "2026-07-04"}

    base = get_json(f"{BASE_URL}/api/issues/search", {
        "projectKeys": "xianyu_hunter",
        "statuses": "OPEN",
        "ps": 1,
        "facets": "severities,rules",
    })
    if "error" in base:
        log(f"ERROR: {base['error']}")
        result["error"] = base["error"]
    else:
        result["total_open"] = base.get("paging", {}).get("total", 0)
        log(f"OPEN total: {result['total_open']}")
        for facet in base.get("facets", []):
            name = facet.get("property")
            entries = []
            for v in facet.get("values", []):
                entries.append({"val": v.get("val"), "count": v.get("count", 0)})
            if name == "severities":
                result["by_severity"] = entries
                log(f"By severity:")
                for e in entries:
                    log(f"  {e['val']}: {e['count']}")
            elif name == "rules":
                result["by_rule"] = entries
                log(f"By rule Top 15:")
                for e in entries[:15]:
                    log(f"  {e['val']}: {e['count']}")

    qg = get_json(f"{BASE_URL}/api/qualitygates/project_status", {"projectKey": "xianyu_hunter"})
    if "error" not in qg:
        result["quality_gate"] = qg
        qg_status = qg.get("projectStatus", {}).get("status", "N/A")
        log(f"Quality gate: {qg_status}")
        for c in qg.get("projectStatus", {}).get("conditions", []):
            log(f"  {c.get('metricKey')}: {c.get('status')} (value={c.get('value')}, threshold={c.get('errorThreshold')})")

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    log(f"\nOutput JSON written to: {OUTPUT}")


if __name__ == "__main__":
    main()
