"""修正分层（把「工具口径污染」的端点移出负载轮），重建分组并重写 v2 配置。

移出理由写入 coverage_matrix，报告里逐条可追溯。
"""
import json
import sys
from pathlib import Path

import yaml

PERF = Path(r"D:\tmp\xh-perf")
sys.path.insert(0, str(PERF))
sys.path.insert(0, str(Path(r"C:\Users\hspcadmin\.qoder-cn\skills\jmeter-performance-test\scripts")))

EXTRA = [
    {"pattern": "^/api/maintenance/status", "method": "GET", "tier": "probe_single",
     "reason": "单请求耗时 >60s（客户端超时判 000），留在负载轮会把整轮 TPS 稀释成假瓶颈；改为单发计量并单列"},
    {"pattern": "^/api/tasks/\\{task_id\\}/links/refresh", "method": "POST", "tier": "blocked",
     "reason": "沙箱关闭调度器，采集器不可用，稳定返回 503，属环境口径而非容量缺陷"},
    {"pattern": "^/api/evaluations/batch-collect-official", "method": "POST", "tier": "blocked",
     "reason": "同上：采集器未运行返回 503；且真实触发会出网抓取"},
    {"pattern": "^/api/tasks/links/auto-migrate", "method": "POST", "tier": "probe_single",
     "reason": "全表迁移类批处理（基线 1.4s/次），重复执行会改数据，不进负载轮"},
    {"pattern": "/stream$", "method": "GET", "tier": "blocked",
     "reason": "SSE/长连接，请求级吞吐口径不适用"},
]

rules = json.loads((PERF / "tier-rules.json").read_text(encoding="utf-8"))
head = [r for r in rules["rules"] if not any(r["pattern"] == e["pattern"] for e in EXTRA)]
rules["rules"] = EXTRA + head
(PERF / "tier-rules.json").write_text(json.dumps(rules, ensure_ascii=False, indent=1), encoding="utf-8")

import build_scenarios  # noqa: E402
build_scenarios.main()

cfg = yaml.safe_load((PERF / "jmeter-config.yml").read_text(encoding="utf-8"))
ph = cfg["phases"]


def pick(prefix):
    return [p for p in ph if p["name"].startswith(prefix)]


# v2 只跑需要重测的阶段：轻读基线+阶梯、写阶梯、混合长跑（重读阶梯沿用 v1 已产出数据）
v2 = []
base = [p for p in ph if p["name"] == "baseline_light"][0]
base["duration_override"] = 180
v2.append(base)
v2 += pick("stress_light")
for p in pick("stress_write"):
    v2.append(p)
v2 += [p for p in ph if p["name"] == "baseline_write"]
# 重读阶梯 v1 已跑到 t16 且拐点已现；v2 分组构成变化（剔除 SSE），
# 再补 t32/t64 会与 v1 基线不同构，按「非 apple-to-apple」原则放弃补测，报告沿用 v1 到 t16。
soak = [p for p in ph if p["name"] == "soak_mixed"][0]
soak["duration_override"] = 1800
v2.append(soak)
cfg["phases"] = v2
cfg["logging"]["file"] = str(PERF / "output" / "perf_v2.log")
mins = sum(p["duration_override"] for p in v2) / 60
(PERF / "jmeter-config-v2.yml").write_text(
    yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False, width=200), encoding="utf-8")
print("[v2] phases:", [p["name"] for p in v2])
print(f"[v2] 预计 {mins:.0f} 分钟")
