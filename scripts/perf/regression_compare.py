"""P0/P1 回归对比：基线 JTL vs 本次回放 JSONL

- 复用 regression_replay.parse_jmx 取得每个采样器(testname)的预期码与 path。
- 基线/新跑都按"响应码是否满足预期码"重算 error（不信任 JTL 的 success 字段，
  与 memory 中 ORO 正则坑一致），保证前后口径一致。
- 输出：整体错误率/P95 对比 + 关键端点（3×P0 + maintenance + vector-admin）逐端点对比
  + 全端点错误率/P95 变化表，写入 markdown 报告。

用法：
  python regression_compare.py --jmx x.jmx --baseline before.jtl --new runs/reads.jsonl \
      --out REGRESSION_REPORT.md [--name "READS"]
"""
from __future__ import annotations
import argparse, csv, json, re, sys
from collections import defaultdict
from xml.etree import ElementTree as ET

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from regression_replay import parse_jmx, expected_ok, _pct  # noqa: E402


def load_jmx_map(jmx):
    info = parse_jmx(jmx)
    m = {}
    for sm in info["samplers"]:
        m[sm["name"]] = {"assertions": sm["assertions"], "path": sm["path"],
                         "method": sm["method"]}
    return m


def read_jtl(path):
    rows = []
    with open(path, encoding="utf-8", errors="ignore") as f:
        sample = f.read(4096)
        f.seek(0)
        has_header = "label" in sample.splitlines()[0] if sample else False
        rdr = csv.DictReader(f) if has_header else csv.reader(f)
        if has_header:
            for r in rdr:
                rows.append((r.get("label", ""), str(r.get("responseCode", "")),
                             float(r.get("elapsed", 0) or 0)))
        else:
            for r in rdr:
                # ts, elapsed, label, code, ...
                if len(r) < 4:
                    continue
                rows.append((r[2], str(r[3]), float(r[2] if False else r[1] or 0)))
    return rows


def read_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            rows.append((d["label"], str(d["code"]), float(d["el"])))
    return rows


def is_defect(code):
    """真正的服务缺陷：5xx 服务器错误 / 405 路由缺失 / 000 连接失败(连接重置)"""
    if code in ("000", "405"):
        return True
    return code[:1] == "5"


def aggregate(rows, jmx_map):
    by_label = defaultdict(list)
    for label, code, el in rows:
        by_label[label].append((code, el))
    agg = {}
    for label, lst in by_label.items():
        asr = jmx_map.get(label, {}).get("assertions", [])
        errs = sum(1 for code, _ in lst if not expected_ok(code, asr))
        defects = sum(1 for code, _ in lst if is_defect(code))
        lats = sorted(e for _, e in lst)
        agg[label] = {
            "total": len(lst), "errors": errs, "defects": defects,
            "error_rate": round(100.0 * errs / len(lst), 3) if lst else 0,
            "defect_rate": round(100.0 * defects / len(lst), 3) if lst else 0,
            "p50": _pct(lats, 50), "p95": _pct(lats, 95), "p99": _pct(lats, 99),
            "path": jmx_map.get(label, {}).get("path", ""),
            "method": jmx_map.get(label, {}).get("method", ""),
        }
    return agg


def overall(agg):
    total = sum(a["total"] for a in agg.values())
    errs = sum(a["errors"] for a in agg.values())
    defects = sum(a["defects"] for a in agg.values())
    return {
        "total": total, "errors": errs, "defects": defects,
        "error_rate": round(100.0 * errs / total, 3) if total else 0,
        "defect_rate": round(100.0 * defects / total, 3) if total else 0,
    }


KEY_MATCH = [
    ("P0-1 订单详情(缺失→404)", ("GET", "/api/orders/")),
    ("P0-2 偏好PUT(405→200)", ("PUT", "/api/preferences")),
    ("P0-3 商品批量(连接重置→200)", ("GET", "/api/items/batch")),
    ("P1-1 维护状态(缓存)", ("GET", "/maintenance/status")),
    ("P1-6 向量库状态(缓存)", ("GET", "/vector-admin/status")),
]


def find_key(jmx_map, method, substr):
    for name, v in jmx_map.items():
        if v["method"] == method and substr in v["path"]:
            return name
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jmx", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--new", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--name", default="RUN")
    a = ap.parse_args()

    jmx_map = load_jmx_map(a.jmx)
    base_rows = read_jtl(a.baseline)
    new_rows = read_jsonl(a.new)
    base_agg = aggregate(base_rows, jmx_map)
    new_agg = aggregate(new_rows, jmx_map)

    bo = overall(base_agg)
    no = overall(new_agg)

    lines = []
    lines.append(f"# P0/P1 回归对比报告 — {a.name}\n")
    lines.append("> 基线 = 修复前(`results_before_p04_20260728_021612`)，新跑 = 当前修复后代码回放。\n")
    lines.append("> 错误率口径：响应码是否满足 JMX 中断言的预期码（不信任 JTL 的 success 字段）。\n")
    lines.append("\n## 整体对比\n")
    lines.append("| 指标 | 基线(修复前) | 当前(修复后) | 变化 |")
    lines.append("|---|---|---|---|")
    lines.append(f"| 总样本 | {bo['total']} | {no['total']} | - |")
    lines.append(f"| 计划断言错误数 | {bo['errors']} | {no['errors']} | {no['errors']-bo['errors']:+d} |")
    lines.append(f"| 计划断言错误率 | {bo['error_rate']}% | {no['error_rate']}% | {no['error_rate']-bo['error_rate']:+.3f}pp |")
    lines.append(f"| **真实缺陷数(5xx/405/000)** | {bo['defects']} | {no['defects']} | {no['defects']-bo['defects']:+d} |")
    lines.append(f"| **真实缺陷率** | {bo['defect_rate']}% | {no['defect_rate']}% | {no['defect_rate']-bo['defect_rate']:+.3f}pp |")

    lines.append("\n## 关键端点逐端点对比\n")
    lines.append("| 端点 | 阶段 | 计划错误率 | 缺陷率 | 主要响应码 | P95(ms) | P50(ms) |")
    lines.append("|---|---|---|---|---|---|---|")
    for title, (method, substr) in KEY_MATCH:
        name = find_key(jmx_map, method, substr)
        if not name:
            lines.append(f"| {title} | - | (计划中未找到) | - | - | - | - |")
            continue
        b = base_agg.get(name, {})
        n = new_agg.get(name, {})
        # 主要响应码（取出现最多的码）
        def top_code(aggd):
            from collections import Counter
            return "-"
        if b:
            lines.append(f"| {title} | 基线 | {b['error_rate']}% | {b['defect_rate']}% | (见基线JTL) | {b['p95']} | {b['p50']} |")
        if n:
            lines.append(f"| {title} | 当前 | {n['error_rate']}% | {n['defect_rate']}% | (见新跑JSONL) | {n['p95']} | {n['p50']} |")
        if not b and not n:
            lines.append(f"| {title} | - | 缺失 | - | - | - | - |")

    lines.append("\n## 全端点错误率变化（按当前错误率降序，含基线有错者）\n")
    lines.append("| 端点 | 基线错误率 | 当前错误率 | Δpp | 基线P95 | 当前P95 |")
    lines.append("|---|---|---|---|---|---|")
    all_names = set(base_agg) | set(new_agg)
    ranked = sorted(all_names, key=lambda x: (new_agg.get(x, {}).get("error_rate", 0),
                                              base_agg.get(x, {}).get("error_rate", 0)), reverse=True)
    for name in ranked:
        b = base_agg.get(name, {})
        n = new_agg.get(name, {})
        ber = b.get("error_rate", 0)
        ner = n.get("error_rate", 0)
        if ber == 0 and ner == 0:
            continue
        dpp = round(ner - ber, 3)
        lines.append(f"| {name} ({n.get('method',b.get('method',''))} {n.get('path',b.get('path',''))}) | {ber}% | {ner}% | {dpp:+.3f} | {b.get('p95','-')} | {n.get('p95','-')} |")

    report = "\n".join(lines) + "\n"
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(report)
    print(report)
    print(f"\n[written] {a.out}")


if __name__ == "__main__":
    main()
