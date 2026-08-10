#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""解析 JMeter JTL(CSV) 生成综合性能分析报告。

输出:
  1) <out>.summary.csv   —— 每个接口(label)的指标
  2) <out>.phases.csv    —— 每个阶段(ThreadGroup)的聚合指标
  3) <out>.report.md     —— 人类可读报告(含 SLA 判定与瓶颈排序)

指标: 样本数、错误数、错误率、平均/最小/最大、P50/P90/P95/P99(响应时间)、
      吞吐量(req/s)、字节吞吐(KB/s)、平均连接时间、平均延迟(Latency)。
阶段解析: threadName 形如 "Phase1-... 1-1"，以最后一个空格切分取 ThreadGroup 名。
SLA: --avg-sla / --p95-sla / --err-sla 可调；默认 avg<500ms, p95<1000ms, err<1%。
"""
import argparse
import csv
import os
import statistics
from collections import defaultdict


def percentile(sorted_vals, p):
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return float(sorted_vals[f])
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def load_jtl(path):
    rows = []
    with open(path, encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        for d in r:
            try:
                elapsed = int(d.get("elapsed", "0") or 0)
                connect = int(d.get("Connect", "0") or 0)
                latency = int(d.get("Latency", "0") or 0)
                b = int(d.get("bytes", "0") or 0)
                sent = int(d.get("sentBytes", "0") or 0)
                ts = int(d.get("timeStamp", "0") or 0)
                success = (d.get("success", "true") or "true").lower() == "true"
                code = d.get("responseCode", "")
            except ValueError:
                continue
            label = d.get("label", "")
            tname = d.get("threadName", "")
            grp = tname.rsplit(" ", 1)[0] if " " in tname else tname
            rows.append({
                "label": label, "grp": grp, "elapsed": elapsed, "connect": connect,
                "latency": latency, "bytes": b, "sent": sent, "ts": ts,
                "success": success, "code": code,
            })
    return rows


def aggregate(rows):
    if not rows:
        return {}
    elapsed_list = sorted(r["elapsed"] for r in rows)
    n = len(rows)
    errs = sum(1 for r in rows if not r["success"])
    total_bytes = sum(r["bytes"] for r in rows)
    t0 = min(r["ts"] for r in rows)
    t1 = max(r["ts"] for r in rows)
    span = max((t1 - t0) / 1000.0, 1e-6)
    return {
        "samples": n,
        "errors": errs,
        "error_rate": errs / n * 100.0,
        "avg": statistics.fmean(elapsed_list),
        "min": elapsed_list[0],
        "max": elapsed_list[-1],
        "p50": percentile(elapsed_list, 50),
        "p90": percentile(elapsed_list, 90),
        "p95": percentile(elapsed_list, 95),
        "p99": percentile(elapsed_list, 99),
        "throughput": n / span,
        "kb_per_s": total_bytes / 1024.0 / span,
        "avg_connect": statistics.fmean(r["connect"] for r in rows),
        "avg_latency": statistics.fmean(r["latency"] for r in rows),
    }


def sla_verdict(m, avg_sla, p95_sla, err_sla):
    fails = []
    if m["avg"] > avg_sla:
        fails.append("avg>%dms" % avg_sla)
    if m["p95"] > p95_sla:
        fails.append("p95>%dms" % p95_sla)
    if m["error_rate"] > err_sla:
        fails.append("err>%.2f%%" % err_sla)
    return ("PASS" if not fails else "FAIL:" + ",".join(fails)), fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jtl", required=True)
    ap.add_argument("--out", default=None, help="输出前缀(同目录)，默认与 jtl 同名")
    ap.add_argument("--avg-sla", type=float, default=500)
    ap.add_argument("--p95-sla", type=float, default=1000)
    ap.add_argument("--err-sla", type=float, default=1.0)
    ap.add_argument("--title", default="XianyuHunter 性能测试")
    args = ap.parse_args()

    if args.out is None:
        args.out = os.path.splitext(args.jtl)[0]
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)

    rows = load_jtl(args.jtl)
    if not rows:
        print("[analyze] JTL 为空或无有效行:", args.jtl)
        return

    by_label = defaultdict(list)
    by_grp = defaultdict(list)
    for r in rows:
        by_label[r["label"]].append(r)
        by_grp[r["grp"]].append(r)

    # per-label
    labels = sorted(by_label.keys())
    label_rows = []
    for lb in labels:
        m = aggregate(by_label[lb])
        verdict, fails = sla_verdict(m, args.avg_sla, args.p95_sla, args.err_sla)
        m["label"] = lb
        m["verdict"] = verdict
        m["fails"] = ";".join(fails)
        label_rows.append(m)

    # per-phase
    grp_rows = []
    for g in sorted(by_grp.keys()):
        m = aggregate(by_grp[g])
        m["phase"] = g
        grp_rows.append(m)

    # overall
    overall = aggregate(rows)
    overall_verdict, _ = sla_verdict(overall, args.avg_sla, args.p95_sla, args.err_sla)

    # write CSVs
    lm = ["label", "samples", "errors", "error_rate", "avg", "min", "max",
          "p50", "p90", "p95", "p99", "throughput", "kb_per_s",
          "avg_connect", "avg_latency", "verdict", "fails"]
    with open(args.out + ".summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=lm, extrasaction="ignore")
        w.writeheader()
        for m in sorted(label_rows, key=lambda x: -x["p95"]):
            w.writerow(m)

    gm = ["phase", "samples", "errors", "error_rate", "avg", "min", "max",
          "p50", "p90", "p95", "p99", "throughput", "kb_per_s",
          "avg_connect", "avg_latency"]
    with open(args.out + ".phases.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=gm, extrasaction="ignore")
        w.writeheader()
        for m in grp_rows:
            w.writerow(m)

    # markdown report
    fails = [m for m in label_rows if m["verdict"].startswith("FAIL")]
    fails_sorted = sorted(fails, key=lambda x: -x["p95"])
    md = []
    md.append("# %s — 分析报告" % args.title)
    md.append("")
    md.append("## 总览")
    md.append("")
    md.append("- 总样本数: **%d**" % overall["samples"])
    md.append("- 总错误率: **%.3f%%**" % overall["error_rate"])
    md.append("- 平均响应: **%.1f ms** | P95: **%.1f ms** | P99: **%.1f ms** | 最大: **%d ms**"
              % (overall["avg"], overall["p95"], overall["p99"], overall["max"]))
    md.append("- 总吞吐量: **%.1f req/s** | 字节吞吐: **%.1f KB/s**"
              % (overall["throughput"], overall["kb_per_s"]))
    md.append("- 总体 SLA: **%s** (avg<%dms, p95<%dms, err<%.2f%%)"
              % (overall_verdict, args.avg_sla, args.p95_sla, args.err_sla))
    md.append("- 不达标接口数: **%d / %d**" % (len(fails), len(label_rows)))
    md.append("")
    md.append("## 阶段(Task Group)聚合")
    md.append("")
    md.append("| 阶段 | 样本 | 错误率 | avg | P95 | P99 | 吞吐(req/s) |")
    md.append("|---|---|---|---|---|---|---|")
    for m in grp_rows:
        md.append("| %s | %d | %.3f%% | %.1f | %.1f | %.1f | %.1f |"
                   % (m["phase"], m["samples"], m["error_rate"], m["avg"],
                      m["p95"], m["p99"], m["throughput"]))
    md.append("")
    md.append("## 接口级明细(按 P95 降序)")
    md.append("")
    md.append("| 接口 | 样本 | 错误率 | avg | P95 | P99 | 最大 | 吞吐 |  verdict |")
    md.append("|---|---|---|---|---|---|---|---|---|")
    for m in sorted(label_rows, key=lambda x: -x["p95"]):
        md.append("| %s | %d | %.3f%% | %.1f | %.1f | %.1f | %d | %.1f | %s |"
                   % (m["label"], m["samples"], m["error_rate"], m["avg"],
                      m["p95"], m["p99"], m["max"], m["throughput"], m["verdict"]))
    md.append("")
    md.append("## 性能瓶颈(不达标接口，按 P95 降序)")
    md.append("")
    if fails_sorted:
        for m in fails_sorted:
            md.append("- **%s**: avg=%.1fms, P95=%.1fms, 错误率=%.3f%% — %s"
                       % (m["label"], m["avg"], m["p95"], m["error_rate"], m["fails"]))
    else:
        md.append("- 无接口突破 SLA 阈值。")
    md.append("")
    with open(args.out + ".report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")

    print("[analyze] 完成:")
    print("  总样本=%d 错误率=%.3f%% avg=%.1f P95=%.1f 吞吐=%.1f"
          % (overall["samples"], overall["error_rate"], overall["avg"],
             overall["p95"], overall["throughput"]))
    print("  不达标接口=%d" % len(fails))
    print("  ->", args.out + ".summary.csv")
    print("  ->", args.out + ".phases.csv")
    print("  ->", args.out + ".report.md")


if __name__ == "__main__":
    main()
