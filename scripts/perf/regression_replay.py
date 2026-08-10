"""JMX -> Python 负载回放工具（JMeter 不可用时的等价回归）

忠实复现 xianyu_load_test_reads/writes.jmx：
- 解析 TestPlan 的 User Defined Variables、ThreadGroup(threads/ramp/duration)、
  每个 HTTPSamplerProxy 的 method/path/body，以及紧随其后的 ResponseAssertion 预期码。
- 变量替换：${VAR} 取 UDV；${__P(prop,default)} 取 override 或 default。
- 多线程 urllib 回放，记录 (label, code, ok, elapsed_ms)。
- 预期码判定与 JMeter 一致：test_type==2 用正则 fullmatch，否则子串包含；
  仅对 Assertion.response_code 字段的断言生效。

用法：
  python regression_replay.py --jmx x.jmx --base-url http://127.0.0.1:8011 \
      --token <WEB_TOKEN> --out results_new/reads.jsonl [--duration 60]
"""
from __future__ import annotations
import argparse, csv, json, re, sys, threading, time, urllib.error, urllib.request
from collections import defaultdict
from xml.etree import ElementTree as ET

NS = ""  # JMeter JMX has no namespace


def _parent_map(root):
    pm = {}
    for p in root.iter():
        for c in p:
            pm[c] = p
    return pm


def parse_jmx(path):
    tree = ET.parse(path)
    root = tree.getroot()
    pm = _parent_map(root)

    # --- UDV ---
    udv = {}
    for arg in root.findall(".//TestPlan//elementProp[@elementType='Argument']"):
        nm = arg.find("stringProp[@name='Argument.name']")
        vl = arg.find("stringProp[@name='Argument.value']")
        if nm is not None and vl is not None:
            udv[nm.text] = vl.text or ""

    # --- ThreadGroup ---
    tg = root.find(".//ThreadGroup")
    threads = int(tg.find("stringProp[@name='ThreadGroup.num_threads']").text)
    ramp = int(tg.find("stringProp[@name='ThreadGroup.ramp_time']").text)
    loops_el = tg.find(".//elementProp[@name='ThreadGroup.main_controller']/stringProp[@name='LoopController.loops']")
    loops = int(loops_el.text) if loops_el is not None and loops_el.text else -1
    sched_el = tg.find("boolProp[@name='ThreadGroup.scheduler']")
    sched = sched_el is not None and sched_el.text == "true"
    dur_el = tg.find("stringProp[@name='ThreadGroup.duration']")
    duration = int(dur_el.text) if (dur_el is not None and dur_el.text) else 0
    if not sched:
        # loop-based: duration = loops * (samplers) roughly; caller may override
        duration = max(duration, 30)

    # --- Samplers (preserve order) ---
    samplers = []
    for s in root.iter("HTTPSamplerProxy"):
        method = s.find("stringProp[@name='HTTPSampler.method']").text or "GET"
        raw_path = s.find("stringProp[@name='HTTPSampler.path']").text or ""
        body = _extract_body(s)
        assertions = _extract_assertions(s, pm)
        name = s.get("testname") or raw_path
        samplers.append({"method": method, "path": raw_path, "body": body,
                         "assertions": assertions, "name": name})
    return {"udv": udv, "threads": threads, "ramp": ramp, "loops": loops,
            "scheduler": sched, "duration": duration, "samplers": samplers}


def _extract_body(s):
    args = s.find("elementProp[@elementType='Arguments']/collectionProp[@name='Arguments.arguments']")
    if args is None:
        return None
    for el in args.findall("elementProp[@elementType='HTTPArgument']"):
        nm = el.find("stringProp[@name='Argument.name']")
        vl = el.find("stringProp[@name='Argument.value']")
        # JMeter raw-body arg: empty Argument.name (parses to None or "") + use_equals=false
        if nm is not None and (nm.text is None or nm.text == "") and vl is not None:
            return vl.text  # raw body (use_equals=false)
    # named args -> form body (rare here)
    parts = []
    for el in args.findall("elementProp[@elementType='HTTPArgument']"):
        nm = el.find("stringProp[@name='Argument.name']")
        vl = el.find("stringProp[@name='Argument.value']")
        if nm is not None and nm.text:
            parts.append(f"{nm.text}={vl.text or ''}")
    return "&".join(parts) if parts else None


def _extract_assertions(s, pm):
    parent = pm.get(s)
    if parent is None:
        return []
    kids = list(parent)
    idx = kids.index(s)
    if idx + 1 >= len(kids) or kids[idx + 1].tag != "hashTree":
        return []
    rah = kids[idx + 1]
    out = []
    for ra in rah.findall("ResponseAssertion"):
        field = ra.find("stringProp[@name='Assertion.test_field']")
        if field is None or field.text != "Assertion.response_code":
            continue
        tt = ra.find("intProp[@name='Assertion.test_type']")
        test_type = int(tt.text) if tt is not None and tt.text else 2
        pats = [sp.text for sp in ra.findall("collectionProp[@name='Asserion.test_strings']/stringProp") if sp.text]
        out.append({"test_type": test_type, "patterns": pats})
    return out


def substitute(text, udv, overrides):
    if not text:
        return text

    def repl_p(m):
        inner = m.group(1)
        parts = inner.split(",", 1)
        prop = parts[0].strip()
        default = parts[1] if len(parts) > 1 else ""
        if prop in overrides:
            return str(overrides[prop])
        return substitute(default, udv, overrides)

    t = re.sub(r"\$\{__P\(([^)]*)\)\}", repl_p, text)

    def repl_v(m):
        name = m.group(1)
        if name in overrides:
            return str(overrides[name])
        return udv.get(name, "")

    return re.sub(r"\$\{([A-Za-z0-9_]+)\}", repl_v, t)


def expected_ok(code, assertions):
    """判定 response code 是否满足所有 response_code 断言（与 JMeter 一致）"""
    if not assertions:
        return code.startswith(("2", "3"))
    for a in assertions:
        pats = a["patterns"]
        if a["test_type"] == 2:  # Matches (regex fullmatch)
            ok = any(re.fullmatch(p, code) for p in pats)
        else:  # Substring / Contains / Equals
            ok = any(p in code for p in pats)
        if not ok:
            return False
    return True


def send_once(session, method, url, body, headers, timeout):
    t0 = time.perf_counter()
    req_headers = dict(headers) if headers else {}
    data = body
    # JSON body must be advertised as application/json, else FastAPI receives
    # raw bytes and fails to parse the Pydantic body model -> 422/500
    if isinstance(body, str) and body.strip()[:1] in ("{", "["):
        req_headers.setdefault("Content-Type", "application/json")
    try:
        resp = session.request(method, url, data=data, headers=req_headers, timeout=timeout)
        code = str(resp.status_code)
    except Exception as e:
        code = "000"
    el = (time.perf_counter() - t0) * 1000.0
    return code, el


def run(jmx, base_url, token, out_path, duration_override=None):
    import requests as _req
    info = parse_jmx(jmx)
    udv = info["udv"]
    overrides = {"web_token": token, "WEB_TOKEN": token}
    threads = info["threads"]
    duration = duration_override or info["duration"]
    ramp = info["ramp"]

    # pre-substitute each sampler
    prepared = []
    for sm in info["samplers"]:
        path = substitute(sm["path"], udv, overrides)
        body = substitute(sm["body"], udv, overrides)
        assertions = sm["assertions"]
        label = sm["name"]
        url = base_url + path
        # GET/DELETE: a k=v "body" in JMeter is really a query string
        if sm["method"] in ("GET", "DELETE") and body and body.strip() and not body.strip().startswith("{"):
            sep = "&" if "?" in url else "?"
            url = url + sep + body
            body = None
        prepared.append((sm["method"], url, body, assertions, label))

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "RegressionReplay/1.0",
    }
    timeout = 30.0

    records = []
    lock = threading.Lock()
    stop = threading.Event()
    deadline = time.time() + duration

    def worker(wid):
        session = _req.Session()
        session.headers.update(headers)
        # stagger start for ramp-up
        if ramp > 0:
            time.sleep(min(ramp, threads) * wid / max(threads, 1))
        while not stop.is_set() and time.time() < deadline:
            for method, url, body, assertions, label in prepared:
                if stop.is_set() or time.time() >= deadline:
                    break
                code, el = send_once(session, method, url, body, {}, timeout)
                ok = expected_ok(code, assertions)
                with lock:
                    records.append((label, code, ok, el))

    t0 = time.time()
    ths = [threading.Thread(target=worker, args=(i,)) for i in range(threads)]
    for t in ths:
        t.start()
    try:
        while time.time() < deadline:
            time.sleep(2)
    finally:
        stop.set()
        for t in ths:
            t.join(timeout=5)
    wall = time.time() - t0

    total = len(records)
    errs = sum(1 for _, _, ok, _ in records if not ok)
    lats = sorted(e for *_, e in records)
    p50 = _pct(lats, 50)
    p95 = _pct(lats, 95)
    p99 = _pct(lats, 99)

    with open(out_path, "w", encoding="utf-8") as f:
        for label, code, ok, el in records:
            f.write(json.dumps({"label": label, "code": code, "ok": ok, "el": round(el, 2)}) + "\n")

    meta = {
        "jmx": jmx, "base_url": base_url, "threads": threads, "duration": duration,
        "wall_sec": round(wall, 1), "samplers": len(prepared),
        "total": total, "errors": errs, "error_rate": round(100.0 * errs / total, 3) if total else 0,
        "p50_ms": p50, "p95_ms": p95, "p99_ms": p99,
    }
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    return meta


def _pct(sorted_vals, p):
    if not sorted_vals:
        return 0.0
    k = max(0, min(len(sorted_vals) - 1, int(round((p / 100.0) * (len(sorted_vals) - 1)))))
    return round(sorted_vals[k], 2)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--jmx", required=True)
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--token", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--duration", type=int, default=None)
    a = ap.parse_args()
    run(a.jmx, a.base_url.rstrip("/"), a.token, a.out, a.duration)
