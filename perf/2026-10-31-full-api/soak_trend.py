"""长跑内存/句柄趋势判定：只统计 SUT 存活样本，并给出 soak 窗口内的线性斜率。

用途：`resource_summary.json` 的分段均值不足以判定「缓存预热 vs 慢泄漏」——
它把 SUT 关停后的 rss=0 行也算了进去（会伪装成「末段回落」）。本脚本按
`ts_s` 取最后 N 秒窗口做线性拟合，是 REPORT §4/§6.8 与 OPTIMIZATIONS B4 的判据来源。

用法：python soak_trend.py [窗口秒数，默认 1800]
"""
import csv
import statistics
import sys
from pathlib import Path

OUT = next(p for p in (Path(__file__).resolve().parent / "results",
                       Path(__file__).resolve().parent / "output") if p.exists())
WIN = float(sys.argv[1]) if len(sys.argv) > 1 else 1800.0

rows = list(csv.DictReader(open(OUT / "sut_resource.csv", encoding="utf-8")))
alive = [r for r in rows if r.get("rss_mb") not in (None, "", "nan") and float(r["rss_mb"]) > 0]
ts = [float(r["ts_s"]) for r in alive]
series = {"rss_mb": [float(r["rss_mb"]) for r in alive],
          "private_mb": [float(r["private_mb"] or 0) for r in alive],
          "handles": [float(r["handles"] or 0) for r in alive]}

print(f"原始 {len(rows)} 行 / 存活 {len(alive)} 行 / 跨度 {ts[0]:.0f}~{ts[-1]:.0f} s"
      f"（rss=0 的 {len(rows) - len(alive)} 行是 SUT 关停后写入，已剔除）")

sel = [i for i, t in enumerate(ts) if t >= ts[-1] - WIN]
print(f"\n最后 {WIN:.0f} s 窗口：{len(sel)} 个存活样本")


def slope(vals):
    xs = [ts[i] for i in sel]
    ys = [vals[i] for i in sel]
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)


W = 6
size = len(sel) // W
for key, vals in series.items():
    segs = [round(statistics.fmean([vals[i] for i in sel[k * size:(k + 1) * size]]), 1) for k in range(W)]
    print(f"{key:11s} 斜率 {slope(vals) * 3600:+7.1f}/h  六段 {segs}  末值 {vals[sel[-1]]:.0f}  峰值 {max(vals):.0f}")

q = len(alive) // 8
print("全程 RSS 8 段", [round(statistics.fmean(series["rss_mb"][k * q:(k + 1) * q]), 1) for k in range(8)])
print("\n判定口径：斜率≈0 且负载停止后回落 → 无泄漏；斜率持续为正但句柄恒定 → 倾向缓存/arena 增长（需容量上限，见 B4）；"
      "斜率为正且句柄同涨 → 按泄漏查（tracemalloc）。")
