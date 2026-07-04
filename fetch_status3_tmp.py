#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立运行 SonarQube 状态查询脚本。

注意：本脚本使用硬编码 token，来源于 scripts/run_scan.bat。
此脚本不入版本控制（位置在 docs 下的 reports 子目录，便于检索但不主动提交）。
"""
import json
import os
import sys
import base64
import urllib.request
import urllib.error
import urllib.parse

BASE_URL = "http://localhost:9000"
TOKEN = "sqa_fe4b774b40e19eca12e0f46a2f2f771f2d1a23bd"
AUTH = base64.b64encode(f"{TOKEN}:".encode()).decode()
OUT_DIR = r"d:\code\otherProjects\17_xianyu\docs\04-系统维护\sonar-reports"
OUT_JSON = os.path.join(OUT_DIR, "sonar-current-status.json")
LOG = os.path.join(OUT_DIR, "fetch_status.log")

for p in (OUT_JSON, LOG):
    if os.path.exists(p):
        os.remove(p)


def log(msg: str) -> None:
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def get_json(url: str, params: dict):
    qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    req = urllib.request.Request(f"{url}?{qs}", headers={"Authorization": f"Basic {AUTH}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")[:500]
        return {"error": f"HTTP {e.code}", "body": body}
    except Exception as e:
        return {"error": str(e)}


def main() -> int:
    log("=" * 60)
    log("SonarQube Status Query")
    log("=" * 60)

    result = {"base_url": BASE_URL}

    base = get_json(f"{BASE_URL}/api/issues/search", {
        "projectKeys": "xianyu_hunter",
        "statuses": "OPEN",
        "ps": 1,
        "facets": "severities,rules",
    })
    if "error" in base:
        log(f"[1] ERROR: {base['error']} body={base.get('body','')[:200]}")
        result["error"] = base["error"]
    else:
        paging = base.get("paging", {})
        result["total_open"] = paging.get("total", 0)
        log(f"[1] OPEN total: {result['total_open']}")
        for facet in base.get("facets", []):
            name = facet.get("property")
            entries = [{"val": v.get("val"), "count": v.get("count", 0)}
                       for v in facet.get("values", [])]
            if name == "severities":
                result["by_severity"] = entries
                log("By severity:")
                for e in entries:
                    log(f"  {e['val']}: {e['count']}")
            elif name == "rules":
                result["by_rule"] = entries
                log("Top 20 rules:")
                for e in entries[:20]:
                    log(f"  {e['val']}: {e['count']}")

    qg = get_json(f"{BASE_URL}/api/qualitygates/project_status", {
        "projectKey": "xianyu_hunter",
    })
    if "error" in qg:
        log(f"[2] QG ERROR: {qg['error']}")
    else:
        ps = qg.get("projectStatus", {})
        result["quality_gate"] = {
            "status": ps.get("status"),
            "conditions": [
                {
                    "metricKey": c.get("metricKey"),
                    "status": c.get("status"),
                    "value": c.get("value"),
                    "errorThreshold": c.get("errorThreshold"),
                }
                for c in ps.get("conditions", [])
            ],
        }
        log(f"[2] Quality gate: {ps.get('status')}")
        for c in ps.get("conditions", []):
            log(f"  {c.get('metricKey')}: {c.get('status')} "
                f"(value={c.get('value')}, threshold={c.get('errorThreshold')})")

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    log(f"\nOutput JSON: {OUT_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
