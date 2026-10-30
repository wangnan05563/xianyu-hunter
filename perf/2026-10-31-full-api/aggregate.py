"""聚合器：读取各阶段 jsonl + 资源 CSV，产出接口级基线/拐点表与长跑退化趋势表。

口径说明：
  - 错误率一律从原始响应码重算，不信任 ok 字段
  - 真实缺陷 = 000 / 405 / 5xx 前缀；404/422 视为夹具预期内
  - 阶段 TPS = 阶段样本数 / 配置时长（秒）
"""
import csv
import json
import statistics
import time
from collections import defaultdict
from pathlib import Path

import yaml

PERF = Path(r"D:\tmp\xh-perf")
OUT = PERF / "output"
CFG = yaml.safe_load((PERF / "jmeter-config.yml").read_text(encoding="utf-8"))
PHASES = {p["name"]: p for p in CFG["phases"]}
DEFECT = set(CFG["defect_rules"]["defect_codes"])
EXPECTED = set(CFG["defect_rules"]["expected_codes"])


def pct(vals, q):
    if not vals:
        return 0.0
    s = sorted(vals)
    i = min(len(s) - 1, max(0, int(round(q / 100 * (len(s) - 1)))))
    return round(s[i], 1)


def is_defect(code):
    return code in DEFECT or code.startswith("5")


def load(phase):
    p = OUT / f"{phase}.jsonl"
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def engine_wall_times():
    """从引擎日志取每阶段**实测墙钟秒数**（wall_sec）。

    阶段时长不能只看配置：v2 轮只改了 `duration_override`，若仍按 v1 配置算 TPS，
    吞吐会被系统性低估（此处曾用 3600 除以 1800 秒的实跑，TPS 少一半）。
    """
    import re

    walls = {}
    for log in sorted(OUT.glob("engine*.log")):
        text = log.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"running phase: (\w+) ===[\s\S]*?\"wall_sec\": ([\d.]+)", text):
            walls[m.group(1)] = float(m.group(2))
    return walls


def stat(rows, dur):
    codes = defaultdict(int)
    for r in rows:
        codes[str(r["code"])] += 1
    lat = [r["el"] for r in rows]
    n = len(rows)
    d = sum(1 for r in rows if is_defect(str(r["code"])))
    c4 = sum(v for k, v in codes.items() if k.startswith("4") and k != "000")
    c5 = sum(v for k, v in codes.items() if k.startswith("5"))
    return {
        "n": n, "tps": round(n / dur, 1) if dur else 0,
        "avg": round(statistics.fmean(lat), 1) if lat else 0,
        "p50": pct(lat, 50), "p90": pct(lat, 90), "p95": pct(lat, 95), "p99": pct(lat, 99),
        "max": round(max(lat), 1) if lat else 0,
        "defect_pct": round(100 * d / n, 2) if n else 0,
        "c4_pct": round(100 * c4 / n, 2) if n else 0,
        "c5_pct": round(100 * c5 / n, 2) if n else 0,
        "codes": dict(sorted(codes.items(), key=lambda kv: -kv[1])),
    }


def main():
    result = {}
    walls = engine_wall_times()
    for name, ph in PHASES.items():
        rows = load(name)
        if not rows:
            continue
        dur = walls.get(name) or ph.get("duration_override") or 60
        result[name] = {"threads": ph.get("threads_override"), "dur": dur,
                        "overall": stat(rows, dur),
                        "by_endpoint": {}}
        by = defaultdict(list)
        for r in rows:
            by[r["label"]].append(r)
        for label, rs in by.items():
            result[name]["by_endpoint"][label] = stat(rs, dur)
    (OUT / "agg_phases.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print("[agg] phases with data:", len(result))

    # ---- 拐点表：按并发阶梯找 P95 相对基线劣化 / 缺陷率上升的档位 ----
    GROUPS = {"reads_heavy": ("baseline_heavy", "stress_heavy_t"),
              "reads_light": ("baseline_light", "stress_light_t"),
              "writes_idem": ("baseline_write", "stress_write_t")}
    ladder_rows = []
    for g, (base, prefix) in GROUPS.items():
        if base not in result:
            continue
        b = result[base]["overall"]
        ladder_rows.append(f"| {g} | 1（基线） | {b['n']} | {b['tps']} | {b['avg']} | {b['p95']} | {b['p99']} | {b['defect_pct']}% | {b['c4_pct']}% | - |")
        levels = sorted([k for k in result if k.startswith(prefix)],
                        key=lambda k: result[k]["threads"])
        prev_tps = b["tps"]
        knee = ""
        for k in levels:
            o = result[k]["overall"]
            th = result[k]["threads"]
            tps_gain = o["tps"] / prev_tps if prev_tps else 0
            degrade = o["p95"] / b["p95"] if b["p95"] else 0
            mark = ""
            if not knee and (tps_gain < 1.15 or degrade > 4 or o["defect_pct"] > 1):
                knee = f"拐点≈{th}（吞吐增益 {tps_gain:.2f}×，P95 劣化 {degrade:.1f}×）"
            ladder_rows.append(f"| {g} | {th} | {o['n']} | {o['tps']} | {o['avg']} | {o['p95']} | {o['p99']} | {o['defect_pct']}% | {o['c4_pct']}% | {'⚠️' if o['defect_pct']>0 else ''} |")
            prev_tps = o["tps"]
        ladder_rows.append(f"| **{g} 拐点** | {knee or '阶梯内未出现（需继续加压）'} | | | | | | | | |")
    (OUT / "ladder_table.md").write_text(
        "| 场景 | 并发 | 样本 | TPS | 平均ms | P95ms | P99ms | 缺陷率 | 4xx率 | 备注 |\n|---|---|---|---|---|---|---|---|---|---|\n"
        + "\n".join(ladder_rows) + "\n", encoding="utf-8")

    # ---- 接口级：基线 + 各档 P95/TPS + 拐点并发 ----
    per_endpoint = []
    for g, (base, prefix) in GROUPS.items():
        if base not in result:
            continue
        levels = sorted([k for k in result if k.startswith(prefix)], key=lambda k: result[k]["threads"])
        for label in sorted(result[base]["by_endpoint"]):
            bd = result[base]["by_endpoint"][label]
            cells, knee_t, worst = [], "", {"tps": 0, "t": 0}
            for k in levels:
                ed = result[k]["by_endpoint"].get(label)
                if not ed:
                    cells.append("-")
                    continue
                cells.append(f"{ed['p95']}({ed['tps']})")
                if ed["tps"] > worst["tps"]:
                    worst = {"tps": ed["tps"], "t": result[k]["threads"]}
                ratio = ed["p95"] / bd["p95"] if bd["p95"] else 999
                if not knee_t and (ratio > 4 or ed["defect_pct"] > 1):
                    knee_t = str(result[k]["threads"])
            per_endpoint.append({
                "group": g, "label": label, "n": bd["n"], "avg": bd["avg"], "p50": bd["p50"],
                "p95": bd["p95"], "p99": bd["p99"], "max": bd["max"],
                "codes": bd["codes"], "knee": knee_t or ">", "peak_tps": worst["tps"],
                "peak_at": worst["t"], "ladder_cells": cells})
    (OUT / "per_endpoint.json").write_text(json.dumps(per_endpoint, ensure_ascii=False, indent=1), encoding="utf-8")
    print("[agg] endpoints:", len(per_endpoint))

    lines = ["| 场景 | 接口 | 基线样本 | 平均 | P50 | P95 | P99 | 最大 | 拐点并发 | 峰值TPS@并发 | 状态码分布 |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for e in sorted(per_endpoint, key=lambda x: -x["p95"]):
        codes = " ".join(f"{k}×{v}" for k, v in list(e["codes"].items())[:3])
        lines.append(f"| {e['group']} | `{e['label']}` | {e['n']} | {e['avg']} | {e['p50']} | {e['p95']} | "
                     f"{e['p99']} | {e['max']} | {e['knee']} | {e['peak_tps']}@{e['peak_at']} | {codes} |")
    (OUT / "endpoint_table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ---- 稳定性长跑：分窗退化 + 资源趋势 ----
    soak = OUT / "soak_mixed.jsonl"
    if soak.exists():
        # jsonl 无时间戳，用文件读取顺序按等长分窗近似
        rows = [json.loads(x) for x in soak.read_text(encoding="utf-8").splitlines() if x.strip()]
        W = 6
        soak_dur = result.get("soak_mixed", {}).get("dur") or 1800
        size = len(rows) // W
        win = []
        for i in range(W):
            chunk = rows[i * size:(i + 1) * size]
            if chunk:
                win.append(stat(chunk, soak_dur / W))
        (OUT / "soak_windows.json").write_text(json.dumps(win, ensure_ascii=False, indent=1), encoding="utf-8")
        l = ["| 窗口 | 样本 | TPS | 平均 | P95 | P99 | 缺陷率 | 4xx率 |", "|---|---|---|---|---|---|---|---|"]
        for i, w in enumerate(win, 1):
            l.append(f"| {i}×{round(soak_dur / W / 60)}min | {w['n']} | {w['tps']} | {w['avg']} | {w['p95']} | {w['p99']} | {w['defect_pct']}% | {w['c4_pct']}% |")
        (OUT / "soak_table.md").write_text("\n".join(l) + "\n", encoding="utf-8")
        print("[agg] soak windows:", len(win))

    mon = OUT / "sut_resource.csv"
    if mon.exists():
        with open(mon, encoding="utf-8") as f:
            rr = list(csv.DictReader(f))
        def num(k):
            return [float(x[k]) for x in rr if x.get(k) not in (None, "", "nan")]
        rss, prv, cpu, hd, th = num("rss_mb"), num("private_mb"), num("cpu_percent"), num("handles"), num("threads")
        res = {"samples": len(rr),
               "rss": {"first": rss[0] if rss else 0, "last": rss[-1] if rss else 0,
                        "min": min(rss) if rss else 0, "max": max(rss) if rss else 0},
               "private": {"first": prv[0] if prv else 0, "last": prv[-1] if prv else 0,
                            "max": max(prv) if prv else 0},
               "cpu": {"avg": round(statistics.fmean(cpu), 1) if cpu else 0, "max": max(cpu) if cpu else 0},
               "handles": {"first": hd[0] if hd else 0, "max": max(hd) if hd else 0, "last": hd[-1] if hd else 0},
               "threads": {"first": th[0] if th else 0, "max": max(th) if th else 0, "last": th[-1] if th else 0}}
        # 分窗内存趋势（判泄漏）
        if rss:
            W = 8
            size = len(rss) // W
            res["rss_windows"] = [round(statistics.fmean(rss[i * size:(i + 1) * size]), 1) for i in range(W)]
        (OUT / "resource_summary.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        print("[agg] resource:", res["rss"], res["cpu"], "handles", res["handles"])


if __name__ == "__main__":
    main()
    print("[agg] done", time.strftime("%H:%M:%S"))
