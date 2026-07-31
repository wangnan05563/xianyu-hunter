"""JMeter JTL (XML 格式) 结果分析脚本

输入：test_results/jmeter/results_p2.jtl
输出：分阶段 + 分接口的关键性能指标
"""
import statistics
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

JTL_PATH = Path(r"d:\code\otherProjects\17_xianyu\test_results\jmeter\results_p2.jtl")


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

    # 流式解析 XML，避免大文件内存爆炸
    # httpSample 标签属性：t=elapsed, s=success("true"/"false"), rc=responseCode,
    #                    lb=label, tn=threadName, by=bytes, lt=latency, ct=connect
    context = ET.iterparse(str(JTL_PATH), events=("end",))
    for _, elem in context:
        if elem.tag != "httpSample":
            continue
        total_lines += 1
        thread_name = elem.get("tn", "")
        phase = classify_phase(thread_name)
        label = elem.get("lb", "")
        elapsed = float(elem.get("t", "0"))
        success = elem.get("s", "true").lower() == "true"
        code = elem.get("rc", "")
        bytes_ = int(elem.get("by", "0") or 0)

        samples[phase][label].append({
            "elapsed": elapsed,
            "success": success,
            "code": code,
            "bytes": bytes_,
        })

        if not success:
            error_count += 1
            if len(error_examples[label]) < 3:
                rm = elem.get("rm", "")
                error_examples[label].append(f"code={code} msg={rm[:100]}")
        # 释放元素，防止内存累积
        elem.clear()

    if total_lines == 0:
        print("[ERROR] 0 samples parsed. JTL 可能不是 XML 格式。")
        return 1

    # 输出结果
    print("=" * 110)
    print(f"  JMeter 性能测试结果分析报告（XML 格式解析）")
    print(f"  JTL 文件: {JTL_PATH}")
    print(f"  总采样数: {total_lines:,}  错误数: {error_count:,}  错误率: {error_count/total_lines*100:.3f}%")
    print("=" * 110)

    phases = ["Phase1-基准(10并发)", "Phase2-负载(50并发)", "Phase3-压力(100并发)"]

    for phase in phases:
        if phase not in samples:
            continue
        phase_samples = samples[phase]
        phase_total = sum(len(v) for v in phase_samples.values())
        phase_errors = sum(1 for label_data in phase_samples.values() for s in label_data if not s["success"])
        phase_all_times = [s["elapsed"] for label_data in phase_samples.values() for s in label_data]

        # 阶段默认持续时长（秒）：Phase1=60, Phase2=180, Phase3=180
        phase_duration = 60 if "Phase1" in phase else 180

        print()
        print("## " + phase)
        print("-" * 110)
        print(f"{'接口':<45} {'请求数':>8} {'错误数':>7} {'Avg(ms)':>9} {'P50':>7} {'P90':>7} {'P95':>7} {'P99':>7} {'Min':>7} {'Max':>7} {'TPS':>8} {'Bytes/s':>9}")
        print("-" * 110)

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

        print("-" * 110)
        if phase_all_times:
            print(f"{'阶段汇总':<45} {phase_total:>8} {phase_errors:>7} {statistics.mean(phase_all_times):>9.1f} {percentile(phase_all_times,50):>7.1f} {percentile(phase_all_times,90):>7.1f} {percentile(phase_all_times,95):>7.1f} {percentile(phase_all_times,99):>7.1f} {min(phase_all_times):>7.0f} {max(phase_all_times):>7.0f} {total_throughput:>8.1f} {'-':>9}")
            print(f"  错误率: {phase_errors/phase_total*100:.3f}%")

    # 错误明细
    if error_examples:
        print()
        print("=" * 110)
        print("  错误示例")
        print("=" * 110)
        for label, examples in error_examples.items():
            print(f"\n[{label}]")
            for ex in examples:
                print(f"  - {ex}")

    print()
    print("=" * 110)
    print("  性能评级参考（JMeter 技能标准）")
    print("=" * 110)
    print("  - TPS > 1000 为优秀")
    print("  - 平均响应时间 < 200ms 为优秀")
    print("  - P90 < 500ms 为良好")
    print("  - P95 < 1000ms 为可接受")
    print("  - P99 < 2000ms 为可接受")
    print("  - 错误率 < 1% 为优秀")

    return 0


if __name__ == "__main__":
    sys.exit(main())
