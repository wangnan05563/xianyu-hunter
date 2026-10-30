"""生成 jmeter-config.yml（唯一参数来源）：scenarios 由 groups.json 派生，phases 由阶梯表派生。

并发阶梯贴近真实业务：控制台为「读多写少、突发刷新」，因此
  - 读阶梯 1→64（拐点定位）
  - 写阶梯 1→16（抢单轮询 + 配置保存）
  - 混合业务恒定负载用于稳定性长跑（读:写≈9:1）
"""
import json
from pathlib import Path

import yaml

PERF = Path(r"D:\tmp\xh-perf")
groups = json.loads((PERF / "groups.json").read_text(encoding="utf-8"))
mixed = json.loads((PERF / "mixed.json").read_text(encoding="utf-8"))
PORT = 8011
PID = (PERF / "sut.pid").read_text().strip()


def samplers(items):
    out = []
    for s in items:
        sm = {"name": s["name"], "path": s["path"], "method": s["method"]}
        if s.get("params"):
            sm["params"] = {k: str(v) for k, v in s["params"].items() if str(v) != ""}
        if s["method"] in ("POST", "PUT", "PATCH"):
            sm["body"] = json.dumps(s.get("body") or {}, ensure_ascii=False)
        out.append(sm)
    return out


def scen(name, profile, items):
    return {"name": name, "profile": profile, "samplers": samplers(items)}


def phase(name, jmx, threads, duration):
    return {"name": name, "jmx": f"jmeter/{jmx}.jmx", "enabled": True,
            "threads_override": threads, "duration_override": duration}


cfg = {
    "mode": "python_replay",
    "sandbox": {
        "enabled": True, "cwd": str(PERF / "sandbox"), "startup_cmd": "", "pkg": "",
        "port": PORT, "health_path": "/healthz", "health_retries": 60,
        "port_kill_retries": 0, "require_new_instance": False,
        "env_overrides": {},
        "preflight": {"enabled": True, "rate_limit_burst": 120, "burst_path": "/healthz",
                       "abort_on_rate_limit": True, "login_warmup": False, "login_url": "",
                       "login_method": "POST", "login_body": "", "login_max_retries": 0},
        "min_output_lines": 20,
        "process_match": {"mode": "pid_file", "pid_file": str(PERF / "sut.pid"),
                           "name": "", "cmd_substr": ""},
        "lifecycle": {"never_global_kill": True, "kill_tree": False,
                       "kill_retries": 3, "kill_wait_ms": 500},
    },
    "resource_monitor": {
        "enabled": True,
        "match": {"mode": "pid_file", "pid_file": str(PERF / "sut.pid"), "name": "", "cmd_substr": ""},
        "sample_interval_sec": 2, "duration_samples": 0,
        "metrics": ["rss_mb", "private_mb", "cpu_percent", "handles", "threads"],
        "output_csv": str(PERF / "output" / "sut_resource.csv"),
        "alert": {"enabled": True, "max_rss_mb": 1800, "on_exceed": "warn"},
    },
    "target": {
        "base_url": f"http://127.0.0.1:{PORT}", "default_timeout_sec": 60,
        "ramp_stagger": True, "fixed_headers": {"Accept": "application/json"},
        "auth": {"type": "bearer", "header_name": "Authorization", "token_source": "file",
                  "token_env": "WEB_TOKEN", "token_file": str(PERF / "token.txt"),
                  "token_literal": "", "cookie_name": "xh_token",
                  "udv_names": ["WEB_TOKEN", "web_token"]},
    },
    "scenarios": {
        "enabled": True, "output_jmx_dir": "jmeter", "default_protocol": "http",
        "default_method": "GET", "fixtures": {},
        "thread_profiles": {
            "single": {"threads": 1, "ramp": 1, "duration": 300},
            "w_single": {"threads": 1, "ramp": 1, "duration": 180},
            "step": {"threads": 4, "ramp": 5, "duration": 60},
            "soak": {"threads": 12, "ramp": 30, "duration": 3600},
        },
        "list": [
            scen("reads_heavy", "single", groups["reads_heavy"]),
            scen("reads_light", "single", groups["reads_light"]),
            scen("writes_idem", "w_single", groups["writes_idem"]),
            scen("mixed_biz", "soak", mixed),
        ],
    },
    "phases": [],
    "defect_rules": {"defect_codes": ["000", "405"], "defect_prefixes": ["5"],
                      "expected_codes": ["404", "422"], "assertion_mismatch_is_defect": False},
    "comparison": {"enabled": False, "baseline_jtl": "", "key_endpoints": [],
                    "baseline_integrity": {"enforce_same_endpoints": True, "doc_fallback_allowed": True}},
    "report": {"formats": ["markdown"], "output_dir": str(PERF / "output"),
                "percentiles": [50, 90, 95, 99], "endpoint_table": True, "group_label_prefixes": []},
    "results": {"output_dir": str(PERF / "output"), "format": "csv", "keep_count": 40},
    "logging": {"level": "INFO", "file": str(PERF / "output" / "perf.log"), "verbose": False},
}

LADDER = [("t2", 2), ("t4", 4), ("t8", 8), ("t16", 16), ("t32", 32), ("t64", 64)]
for tag, n in LADDER:
    cfg["phases"].append(phase(f"stress_heavy_{tag}", "reads_heavy", n, 60))
for tag, n in [("t16", 16), ("t48", 48), ("t96", 96)]:
    cfg["phases"].append(phase(f"stress_light_{tag}", "reads_light", n, 60))
for tag, n in [("t4", 4), ("t8", 8), ("t16", 16)]:
    cfg["phases"].append(phase(f"stress_write_{tag}", "writes_idem", n, 60))
cfg["phases"] = ([phase("baseline_heavy", "reads_heavy", 1, 300),
                  phase("baseline_light", "reads_light", 1, 300),
                  phase("baseline_write", "writes_idem", 1, 180)]
                 + cfg["phases"]
                 + [phase("soak_mixed", "mixed_biz", 12, 3600)])

(PERF / "jmeter-config.yml").write_text(
    yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False, width=200), encoding="utf-8")
print("[config] phases:", len(cfg["phases"]))
print("[config] samplers: heavy=%d light=%d write=%d mixed=%d" % (
    len(groups["reads_heavy"]), len(groups["reads_light"]),
    len(groups["writes_idem"]), len(mixed)))
total = 300 + 300 + 180 + 6 * 60 + 3 * 60 + 3 * 60 + 3600
print("[config] 预计负载轮总时长: %.1f 分钟" % (total / 60))
