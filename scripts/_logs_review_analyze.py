# -*- coding: utf-8 -*-
"""Logs Review analyzer: extract, classify, attribute backend log issues."""
import re, json, collections, sys
from datetime import datetime

LOG_PATH = "run.stdout.log"
OUT_JSON = "scripts/_logs_review_intermediate.json"

# severity pattern from skill config.yaml (mixed format)
SEV_RE = re.compile(
    r"(?P<timestamp>\d{4}-\d{2}-\d{2}.*?\d{2}:\d{2}:\d{2}\.\d{3})\s+\|\s+"
    r"(?P<severity>DEBUG|INFO|WARNING|ERROR|CRITICAL)\s+\|\s+"
    r"\[req=(?P<request_id>[^\]]+)\]\s+\|\s+"
    r"(?P<module>[^:]+):(?P<function>[^:]+):(?P<line>\d+)\s+-\s+"
    r"(?P<message>.*)"
)

# normalization for dedup templates
NORM_RULES = [
    (re.compile(r"req-[\d]+-[\da-f]+"), "{req}"),
    (re.compile(r"te[0-9a-f]{8}"), "{task}"),
    (re.compile(r"\b\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?"), "{ts}"),
    (re.compile(r"\b[0-9a-fA-F]{12,}\b"), "{hex}"),
    (re.compile(r"详情页\s+\d+"), "详情页 {n}"),
    (re.compile(r"\b\d+\.\d+\.\d+\.\d+\b"), "{ip}"),
    (re.compile(r"\b\d{6,}\b"), "{num}"),  # big numbers (ids, sizes)
    (re.compile(r"\b\d+\b"), "{n}"),       # remaining small numbers
]

def normalize(msg):
    s = msg
    for rx, rep in NORM_RULES:
        s = rx.sub(rep, s)
    return s.strip()

# ---- side-effect / type classification ----
HARMFUL = [
    (re.compile(r"(?i)(cookie.*失效|session.*失效|token.*续期失败|续期失败).*(标记失效|失效|跳过|等待)"), "state_check"),
    (re.compile(r"(?i)(HTTPException|status=50\d|status=40\d).*(failed|失败|collect)"), "state_check"),
    (re.compile(r"(?i)(timeout|超时|retry.*fail|重试.*耗尽|exhausted|放弃|give_up).*(abort|give_up|exhausted|放弃)"), "retry_failure"),
    (re.compile(r"(?i)(data\s*loss|inconsistent|corrupt|数据.*丢失|不一致)"), "state_check"),
    (re.compile(r"(?i)(登录.*失效|login.*expired|未登录).*(跳过|等待|失效)"), "state_check"),
]
HARMLESS = [
    (re.compile(r"(?i)(deprecated|弃用|警告).*(continue|跳过|忽略|skip|ignore)"), "warning_noise"),
    (re.compile(r"(?i)(retrying|retry_attempt|重试).*(succeed|成功|ok)"), "warning_noise"),
    (re.compile(r"(?i)(无订单记录|分母为 0|抢单成功率分母|缓存预热|缓存)"), "warning_noise"),
    (re.compile(r"(?i)(未启用|disabled|未配置|cookie 自动同步未启用)"), "warning_noise"),
]
PERF = [
    (re.compile(r"(?i)(slow|elapsed|duration|took|耗时|慢).*?(\d+)\s*ms"), "performance"),
    (re.compile(r"(?i)(batch|bulk|批量).*(missing|absent|none|缺失|未批)"), "performance"),
    (re.compile(r"(?i)(耗时|花费|花费时间|elapsed)\s*[:=]?\s*\d+"), "performance"),
]

def classify_type(msg):
    for rx, t in HARMFUL:
        if rx.search(msg):
            return t, "harmful"
    for rx, t in PERF:
        if rx.search(msg):
            m = rx.search(msg)
            # extract numeric if present
            return t, "performance"
    for rx, t in HARMLESS:
        if rx.search(msg):
            return t, "harmless"
    return None, "unknown"

def main():
    parsed = collections.defaultdict(list)   # template -> list of records
    raw_by_template = collections.defaultdict(list)
    stacktraces = []
    perf_hits = []
    total = 0
    matched = 0
    cur_trace = None
    with open(LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
        for lineno, line in enumerate(f, 1):
            total += 1
            line = line.rstrip("\n")
            m = SEV_RE.match(line)
            if not m:
                # capture traceback lines following an ERROR
                if cur_trace is not None:
                    if line.strip() == "" or line.startswith(("  ", "Traceback")) or "File " in line or "Error" in line or "raise" in line or line.strip().startswith("During"):
                        cur_trace["frames"].append(line)
                        if len(cur_trace["frames"]) > 60:
                            cur_trace = None
                    else:
                        cur_trace = None
                continue
            sev = m.group("severity")
            if sev not in ("WARNING", "ERROR", "CRITICAL"):
                cur_trace = None
                continue
            matched += 1
            ts = m.group("timestamp")
            module = m.group("module")
            func = m.group("function")
            ln = int(m.group("line"))
            msg = m.group("message")
            tmpl = normalize(msg)
            rec = dict(ts=ts, sev=sev, module=module, func=func, line=ln,
                       req=m.group("request_id"), msg=msg, lineno=lineno,
                       template=tmpl)
            parsed[tmpl].append(rec)
            raw_by_template[tmpl].append(msg)
            if sev == "ERROR":
                cur_trace = dict(lineno=lineno, ts=ts, module=module, func=func,
                                 line=ln, msg=msg, frames=[])
                stacktraces.append(cur_trace)
            else:
                cur_trace = None
            # perf scan across all sev
            for rx, t in PERF:
                if rx.search(msg):
                    perf_hits.append(rec)
                    break

    # build issue list
    issues = []
    iid = 0
    for tmpl, recs in parsed.items():
        iid += 1
        recs_sorted = sorted(recs, key=lambda r: r["ts"])
        first = recs_sorted[0]["ts"]
        last = recs_sorted[-1]["ts"]
        sev = recs_sorted[0]["sev"]
        module = recs_sorted[0]["module"]
        func = recs_sorted[0]["func"]
        line = recs_sorted[0]["line"]
        sample = recs_sorted[0]["msg"]
        # frequency: count in 30-min windows
        tss = [datetime.strptime(r["ts"], "%Y-%m-%d %H:%M:%S.%f") for r in recs_sorted]
        max_win = 0
        for i, t0 in enumerate(tss):
            c = sum(1 for t in tss if 0 <= (t - t0).total_seconds() <= 1800)
            max_win = max(max_win, c)
        t, side = classify_type(sample)
        if t is None:
            t = "warning_noise" if sev == "WARNING" else "state_check"
            if side == "unknown":
                side = "harmless" if sev == "WARNING" else "harmful"
        # priority
        if side == "harmful" or sev == "ERROR" or sev == "CRITICAL":
            prio = "high"
        elif t == "performance":
            prio = "medium"
        elif side == "harmless" and max_win >= 5:
            prio = "low"
        else:
            prio = "medium"
        issues.append(dict(
            issue_id=f"log-{iid:03d}", severity=sev, type=t, side_effect=side,
            priority=prio, module=module, func=func, line=line,
            template=tmpl, sample=sample, frequency=len(recs_sorted),
            max_window=max_win, first_seen=first, last_seen=last,
            distinct_raw=len(set(raw_by_template[tmpl])),
        ))

    # sort by frequency desc, then severity
    sev_order = {"CRITICAL":0,"ERROR":1,"WARNING":2}
    issues.sort(key=lambda x: (sev_order.get(x["severity"],9), -x["frequency"]))

    out = dict(
        total_lines=total, matched=matched,
        warning_count=sum(1 for r in sum(parsed.values(),[]) if r["sev"]=="WARNING"),
        error_count=sum(1 for r in sum(parsed.values(),[]) if r["sev"]=="ERROR"),
        traceback_count=len(stacktraces),
        issues=issues,
        stacktraces=[{k:v for k,v in s.items() if k!="frames"} | {"nframes":len(s["frames"])} for s in stacktraces],
    )
    # attach full stacktraces separately
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(dict(meta=dict(total_lines=total, matched=matched,
                                 warning_raw=out["warning_count"],
                                 error_raw=out["error_count"],
                                 traceback_count=len(stacktraces)),
                       issues=issues,
                       stacktraces=stacktraces), f, ensure_ascii=False, indent=2)

    # print summary
    print(f"total_lines={total} matched={matched}")
    print(f"WARNING raw={out['warning_count']} ERROR raw={out['error_count']} tracebacks={len(stacktraces)}")
    print(f"distinct templates={len(issues)}")
    print("\n=== TOP 40 TEMPLATES BY FREQUENCY ===")
    for it in issues[:40]:
        print(f"[{it['severity']:8}] freq={it['frequency']:5} win={it['max_window']:4} prio={it['priority']:6} type={it['type']:14} {it['module']}:{it['func']}:{it['line']}")
        print(f"    tmpl: {it['template'][:140]}")
    print("\n=== TYPE DISTRIBUTION ===")
    tc = collections.Counter(i["type"] for i in issues)
    for k,v in tc.most_common():
        print(f"  {k}: {v}")
    print("\n=== PRIORITY DISTRIBUTION ===")
    pc = collections.Counter(i["priority"] for i in issues)
    for k,v in pc.most_common():
        print(f"  {k}: {v}")
    print(f"\n=== STACKTRACES ({len(stacktraces)}) ===")
    for s in stacktraces:
        print(f"  L{s['lineno']} {s['module']}:{s['func']}:{s['line']} :: {s['msg'][:120]} (frames={len(s['frames'])})")

if __name__ == "__main__":
    main()
