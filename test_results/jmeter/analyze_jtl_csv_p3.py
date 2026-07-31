"""JMeter JTL (CSV 格式) 结果分析脚本 - P3 性能测试

输入：test_results/jmeter/results_p3.jtl
输出：分阶段 + 分接口的关键性能指标，对标 P2 基准进行对比
"""
import csv
import statistics
import sys
from collections import defaultdict
from pathlib import Path

JTL_PATH = Path(r"d:\code\otherProjects\17_xianyu\test_results\jmeter\results_p3.jtl")

# P2 基线数据（来自 PERFORMANCE_REPORT.md）用于对比
P2_BASELINE = {
    "Phase1-基准(10并发)": {"avg": 41.0, "p95": 96.0, "throughput": 119.8},
    "Phase2-负载(50并发)": {"avg": 187.0, "p95": 463.0, "throughput": 248.6},
    "Phase3-压力(100并发)": {"avg": 826.0, "p95": 1475.0, "throughput": 121.5},
}


def percentile(data: list[float], p: float) -> float:
    """计算分位数（线性插值法，与 JMeter 一致）"""
    if not data:
        return 0.0
    s = sorted(data)
    k = (len(s) - 1) * p / 100.0
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (k - f) * (s[c] - s[f])


def classify_phase(thread_name: str) -> str:
    """根据 threadName 识别阶段（JMeter 线程组命名规则）"""
    if "Phase1" in thread_name:
        return "Phase1-基准(10并发)"
    if "Phase2" in thread_name:
        return "Phase2-负载(50并发)"
    if "Phase3" in thread_name:
        return "Phase3-压力(100并发)"
    return "Unknown"


def main() -> int:
    if not JTL_PATH.exists():
        print(f"[ERROR] JTL file not found: {JTL_PATH}")
        return 1

    # phase -> label -> list of (elapsed, success, code, bytes)
    samples: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    total_lines = 0
    error_count = 0
    error_examples: dict[str, list[str]] = defaultdict(list)

    # 阶段时间戳范围（用于精确计算阶段持续时长 -> TPS）
    phase_min_ts: dict[str, int] = {}
    phase_max_ts: dict[str, int] = {}

    with open(JTL_PATH, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_lines += 1
            thread_name = row.get("threadName", "")
            phase = classify_phase(thread_name)
            label = row.get("label", "")
            try:
                elapsed = float(row.get("elapsed", "0"))
                ts = int(row.get("timeStamp", "0"))
            except ValueError:
                continue
            success = row.get("success", "true").lower() == "true"
            code = row.get("responseCode", "")
            try:
                bytes_ = int(row.get("bytes", "0") or 0)
            except ValueError:
                bytes_ = 0

            samples[phase][label].append({
                "elapsed": elapsed,
                "success": success,
                "code": code,
                "bytes": bytes_,
            })

            # 更新阶段时间戳范围
            if ts > 0:
                if phase not in phase_min_ts or ts < phase_min_ts[phase]:
                    phase_min_ts[phase] = ts
                if phase not in phase_max_ts or ts > phase_max_ts[phase]:
                    phase_max_ts[phase] = ts

            if not success:
                error_count += 1
                if len(error_examples[label]) < 3:
                    rm = row.get("responseMessage", "")
                    error_examples[label].append(f"code={code} msg={rm[:100]}")

    if total_lines == 0:
        print("[ERROR] 0 samples parsed.")
        return 1

    # 输出结果
    print("=" * 130)
    print(f"  JMeter P3 性能测试结果分析报告（CSV 格式解析）")
    print(f"  JTL 文件: {JTL_PATH}")
    print(f"  总采样数: {total_lines:,}  错误数: {error_count:,}  错误率: {error_count/total_lines*100:.3f}%")
    print("=" * 130)

    phases = ["Phase1-基准(10并发)", "Phase2-负载(50并发)", "Phase3-压力(100并发)"]

    phase_summary: list[dict] = []

    for phase in phases:
        if phase not in samples:
            continue
        phase_samples = samples[phase]
        phase_total = sum(len(v) for v in phase_samples.values())
        phase_errors = sum(1 for label_data in phase_samples.values() for s in label_data if not s["success"])
        phase_all_times = [s["elapsed"] for label_data in phase_samples.values() for s in label_data]

        # 用实际时间戳计算阶段持续时长（秒），更精确
        if phase in phase_min_ts and phase in phase_max_ts:
            phase_duration = (phase_max_ts[phase] - phase_min_ts[phase]) / 1000.0
            if phase_duration < 1.0:
                phase_duration = 60.0 if "Phase1" in phase else 180.0
        else:
            phase_duration = 60.0 if "Phase1" in phase else 180.0

        print()
        print("## " + phase)
        print("-" * 130)
        print(f"{'接口':<45} {'请求数':>8} {'错误数':>7} {'Avg(ms)':>9} {'P50':>7} {'P90':>7} {'P95':>7} {'P99':>7} {'Min':>7} {'Max':>7} {'TPS':>8} {'Bytes/s':>9}")
        print("-" * 130)

        total_throughput = 0.0
        for label in sorted(phase_samples.keys()):
            data = phase_samples[label]
            times = [s["elapsed"] for s in data]
            err = sum(1 for s in data if not s["success"])
            avg = statistics.mean(times)
            p50 = percentile(times, 50)
            p90 = percentile(times, 90)
            p95 = percentile(times, 95)
            p99 = percentile(times, 99)
            mn, mx = min(times), max(times)
            tps = len(times) / phase_duration
            total_throughput += tps
            bytes_total = sum(s["bytes"] for s in data)
            bytes_per_sec = bytes_total / phase_duration

            print(f"{label:<45} {len(times):>8} {err:>7} {avg:>9.1f} {p50:>7.1f} {p90:>7.1f} {p95:>7.1f} {p99:>7.1f} {mn:>7.0f} {mx:>7.0f} {tps:>8.1f} {bytes_per_sec:>9.0f}")

        print("-" * 130)
        if phase_all_times:
            avg_phase = statistics.mean(phase_all_times)
            p95_phase = percentile(phase_all_times, 95)
            print(f"{'阶段汇总':<45} {phase_total:>8} {phase_errors:>7} {avg_phase:>9.1f} {percentile(phase_all_times,50):>7.1f} {percentile(phase_all_times,90):>7.1f} {p95_phase:>7.1f} {percentile(phase_all_times,99):>7.1f} {min(phase_all_times):>7.0f} {max(phase_all_times):>7.0f} {total_throughput:>8.1f} {'-':>9}")
            err_rate = phase_errors/phase_total*100 if phase_total else 0
            print(f"  错误率: {err_rate:.3f}%  阶段持续: {phase_duration:.0f}s  总吞吐: {total_throughput:.1f} TPS")

            # 与 P2 基线对比
            if phase in P2_BASELINE:
                base = P2_BASELINE[phase]
                avg_diff = (avg_phase - base["avg"]) / base["avg"] * 100
                p95_diff = (p95_phase - base["p95"]) / base["p95"] * 100
                tps_diff = (total_throughput - base["throughput"]) / base["throughput"] * 100
                print(f"  对比 P2 基线: Avg {avg_phase:.1f} vs {base['avg']:.1f} ({avg_diff:+.1f}%), P95 {p95_phase:.1f} vs {base['p95']:.1f} ({p95_diff:+.1f}%), TPS {total_throughput:.1f} vs {base['throughput']:.1f} ({tps_diff:+.1f}%)")

            phase_summary.append({
                "phase": phase,
                "samples": phase_total,
                "errors": phase_errors,
                "avg": avg_phase,
                "p95": p95_phase,
                "throughput": total_throughput,
                "duration": phase_duration,
            })

    # 错误明细
    if error_examples:
        print()
        print("=" * 130)
        print("  错误示例")
        print("=" * 130)
        for label, examples in error_examples.items():
            print(f"\n[{label}]")
            for ex in examples:
                print(f"  - {ex}")

    # 汇总对比表
    print()
    print("=" * 130)
    print("  P3 vs P2 vs P0(基线) 汇总对比")
    print("=" * 130)
    print(f"{'阶段':<28} {'P0-Avg':>10} {'P2-Avg':>10} {'P3-Avg':>10} {'P0-P95':>10} {'P2-P95':>10} {'P3-P95':>10} {'P3-TPS':>10} {'P3-Err':>10}")
    print("-" * 130)

    # P0 基线数据（来自首版报告）
    P0_BASELINE = {
        "Phase1-基准(10并发)": {"avg": 35.0, "p95": 78.0},
        "Phase2-负载(50并发)": {"avg": 165.0, "p95": 423.0},
        "Phase3-压力(100并发)": {"avg": 1649.0, "p95": 2880.0},
    }

    for s in phase_summary:
        phase = s["phase"]
        p0 = P0_BASELINE.get(phase, {"avg": 0, "p95": 0})
        p2 = P2_BASELINE.get(phase, {"avg": 0, "p95": 0})
        err_rate = s["errors"]/s["samples"]*100 if s["samples"] else 0
        print(f"{phase:<28} {p0['avg']:>10.1f} {p2['avg']:>10.1f} {s['avg']:>10.1f} {p0['p95']:>10.1f} {p2['p95']:>10.1f} {s['p95']:>10.1f} {s['throughput']:>10.1f} {err_rate:>9.3f}%")

    # 优化幅度（与 P0 基线对比）
    print()
    print("  优化幅度（P3 vs P0 基线）")
    print("-" * 130)
    for s in phase_summary:
        phase = s["phase"]
        p0 = P0_BASELINE.get(phase, {"avg": 1, "p95": 1})
        avg_imp = (p0["avg"] - s["avg"]) / p0["avg"] * 100
        p95_imp = (p0["p95"] - s["p95"]) / p0["p95"] * 100
        print(f"  {phase}: Avg 下降 {avg_imp:+.1f}%  P95 下降 {p95_imp:+.1f}%")

    print()
    print("=" * 130)
    print("  性能评级参考（JMeter 技能标准）")
    print("=" * 130)
    print("  - TPS > 1000 为优秀")
    print("  - 平均响应时间 < 200ms 为优秀")
    print("  - P90 < 500ms 为良好")
    print("  - P95 < 1000ms 为可接受")
    print("  - P99 < 2000ms 为可接受")
    print("  - 错误率 < 1% 为优秀")

    return 0


if __name__ == "__main__":
    sys.exit(main())
