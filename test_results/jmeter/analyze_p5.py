"""JMeter JTL 结果分析 - P5 (300s TTL)
简化版：仅输出三阶段汇总对比
"""
import csv
import statistics
import sys
from collections import defaultdict
from pathlib import Path

JTL_PATH = Path(r"d:\code\otherProjects\17_xianyu\test_results\jmeter\results_p5.jtl")

P4_BASELINE = {
    "Phase1-基准(10并发)": {"avg": 60.1, "p95": 219.0, "throughput": 159.4},
    "Phase2-负载(50并发)": {"avg": 297.0, "p95": 602.0, "throughput": 161.5},
    "Phase3-压力(100并发)": {"avg": 654.6, "p95": 1063.8, "throughput": 144.7},
}


def percentile(data: list[float], p: float) -> float:
    if not data:
        return 0.0
    s = sorted(data)
    k = (len(s) - 1) * p / 100.0
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return s[f] if f == c else s[f] + (k - f) * (s[c] - s[f])


def classify_phase(thread_name: str) -> str:
    if "Phase1" in thread_name:
        return "Phase1-基准(10并发)"
    if "Phase2" in thread_name:
        return "Phase2-负载(50并发)"
    if "Phase3" in thread_name:
        return "Phase3-压力(100并发)"
    return "Unknown"


def main() -> int:
    if not JTL_PATH.exists():
        print(f"[ERROR] {JTL_PATH} not found")
        return 1

    samples: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    total = errs = 0

    with open(JTL_PATH, "r", encoding="utf-8", errors="ignore") as f:
        for row in csv.DictReader(f):
            total += 1
            phase = classify_phase(row.get("threadName", ""))
            label = row.get("label", "")
            try:
                elapsed = float(row.get("elapsed", "0"))
            except ValueError:
                continue
            success = row.get("success", "true").lower() == "true"
            samples[phase][label].append({"elapsed": elapsed, "success": success})
            if not success:
                errs += 1

    print("=" * 110)
    print(f"  P5 300s TTL 压测: {total:,} samples, {errs} errors ({errs/total*100:.3f}%)")
    print("=" * 110)

    phases = ["Phase1-基准(10并发)", "Phase2-负载(50并发)", "Phase3-压力(100并发)"]
    summary: list[dict] = []

    for phase in phases:
        if phase not in samples:
            continue
        ps = samples[phase]
        pt = sum(len(v) for v in ps.values())
        pe = sum(1 for ld in ps.values() for s in ld if not s["success"])
        all_times = [s["elapsed"] for ld in ps.values() for s in ld]

        dur = 60.0 if "Phase1" in phase else 180.0
        tps = pt / dur * sum(1 for v in ps.values() for _ in v) / max(pt, 1)  # just use pt/dur
        
        print()
        print(f"## {phase}")
        print("-" * 110)
        print(f"{'接口':<45} {'请求':>7} {'Avg(ms)':>9} {'P50':>7} {'P90':>7} {'P95':>7} {'P99':>7} {'Max':>7}")
        print("-" * 110)

        tt = 0.0
        for label in sorted(ps.keys()):
            data = ps[label]
            times = [s["elapsed"] for s in data]
            avg = statistics.mean(times)
            p50 = percentile(times, 50)
            p90 = percentile(times, 90)
            p95 = percentile(times, 95)
            p99 = percentile(times, 99)
            mx = max(times)
            tt += len(times) / dur

            print(f"{label:<45} {len(times):>7} {avg:>9.1f} {p50:>7.1f} {p90:>7.1f} {p95:>7.1f} {p99:>7.1f} {mx:>7.0f}")

        print("-" * 110)
        avg_phase = statistics.mean(all_times)
        p95_phase = percentile(all_times, 95)
        print(f"{'阶段汇总':<45} {pt:>7} {avg_phase:>9.1f} {percentile(all_times,50):>7.1f} {percentile(all_times,90):>7.1f} {p95_phase:>7.1f} {percentile(all_times,99):>7.1f} {max(all_times):>7.0f}")
        print(f"  TPS={tt:.1f}  错误率={pe/pt*100:.3f}%")

        if phase in P4_BASELINE:
            b = P4_BASELINE[phase]
            ad = (avg_phase - b["avg"]) / b["avg"] * 100
            pd = (p95_phase - b["p95"]) / b["p95"] * 100
            td = (tt - b["throughput"]) / b["throughput"] * 100
            print(f"  vs P4: Avg {ad:+.1f}%  P95 {pd:+.1f}%  TPS {td:+.1f}%")

        summary.append({"phase": phase, "avg": avg_phase, "p95": p95_phase, "tps": tt, "samples": pt})

    # 汇总
    print()
    print("=" * 110)
    print("  P0 → P3 → P4 → P5 汇总对比")
    print("=" * 110)
    print(f"{'阶段':<28} {'P0-Avg':>10} {'P3-Avg':>10} {'P4-Avg':>10} {'P5-Avg':>10} {'P0-P95':>10} {'P5-P95':>10}")
    print("-" * 110)

    P0 = {
        "Phase1-基准(10并发)": {"avg": 35.0, "p95": 78.0},
        "Phase2-负载(50并发)": {"avg": 165.0, "p95": 423.0},
        "Phase3-压力(100并发)": {"avg": 1649.0, "p95": 2880.0},
    }
    P3 = {
        "Phase1-基准(10并发)": {"avg": 42.8, "p95": 155.0},
        "Phase2-负载(50并发)": {"avg": 206.8, "p95": 452.0},
        "Phase3-压力(100并发)": {"avg": 430.2, "p95": 767.0},
    }

    for s in summary:
        ph = s["phase"]
        print(f"{ph:<28} {P0[ph]['avg']:>10.1f} {P3[ph]['avg']:>10.1f} {P4_BASELINE[ph]['avg']:>10.1f} {s['avg']:>10.1f} {P0[ph]['p95']:>10.1f} {s['p95']:>10.1f}")

    print()
    print("  P5 vs P0 优化幅度")
    print("-" * 110)
    for s in summary:
        ph = s["phase"]
        ai = (P0[ph]["avg"] - s["avg"]) / P0[ph]["avg"] * 100
        pi = (P0[ph]["p95"] - s["p95"]) / P0[ph]["p95"] * 100
        print(f"  {ph}: Avg {ai:+.1f}%  P95 {pi:+.1f}%")

    return 0


if __name__ == "__main__":
    sys.exit(main())
