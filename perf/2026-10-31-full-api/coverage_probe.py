"""单发覆盖探针：对「不进负载轮」的写端点各发 1 次请求，取真实响应码与延迟基线。

blocked 端点只登记原因、不发请求（防止真实下单 / 出网 / 启浏览器 / 触发穿透）。
所有取值来自 coverage_matrix.json，本脚本零端点常量。
"""
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PERF = Path(r"D:\tmp\xh-perf")
BASE = "http://127.0.0.1:8011"
NON_ASCII = re.compile(r"[^\x00-\x7f]")


def token() -> str:
    for line in (PERF / "sandbox" / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("WEB_TOKEN="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("WEB_TOKEN not found")


def enc(v):
    s = str(v)
    return urllib.parse.quote(s) if NON_ASCII.search(s) else s


def run(s, tok):
    path = s["path"]
    if s.get("params"):
        qs = "&".join(f"{k}={enc(v)}" for k, v in s["params"].items() if v != "")
        if qs:
            path += ("&" if "?" in path else "?") + qs
    data = None
    headers = {"Authorization": f"Bearer {tok}", "Accept": "application/json"}
    if s["method"] in ("POST", "PUT", "PATCH"):
        data = json.dumps(s.get("body") or {}).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=s["method"])
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            code, body = r.status, r.read()
    except urllib.error.HTTPError as e:
        code, body = e.code, e.read()
    except Exception as e:
        return {"label": s["name"], "code": "000", "ms": round((time.perf_counter() - t0) * 1000, 1),
                "err": type(e).__name__ + ":" + str(e)[:120], "tier": s["tier"]}
    ms = round((time.perf_counter() - t0) * 1000, 1)
    return {"label": s["name"], "method": s["method"], "path": s["path"], "code": str(code),
            "ms": ms, "bytes": len(body), "tier": s["tier"], "reason": s["reason"]}


def main(which):
    matrix = json.loads((PERF / "coverage_matrix.json").read_text(encoding="utf-8"))
    targets = [s for s in matrix if s["tier"] in set(which.split(","))]
    tok = token()
    out = []
    for s in targets:
        rec = run(s, tok)
        out.append(rec)
        print(f"{rec['code']:>4} {rec['ms']:>8.1f}ms  {rec['label']}"[:150])
    name = which.replace(",", "_")
    (PERF / "output" / f"probe_{name}.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    # 追加为 jtl 兼容 CSV，便于 analyse_jtl 复用
    with (PERF / "output" / f"probe_{name}.csv").open("w", encoding="utf-8") as f:
        f.write("timeStamp,elapsed,label,responseCode,responseMessage,success,bytes\n")
        for i, r in enumerate(out):
            ok = str(r["code"]).startswith("2")
            f.write(f'{int(time.time()*1000)+i},{int(r["ms"])},{r["label"]},{r["code"]},"",{ok},{r.get("bytes",0)}\n')
    print(f"[probe] {len(out)} endpoints -> probe_{name}.json")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "probe_single")
