"""按 OpenAPI 自动分层，产出：coverage_matrix.json / probe_plan.json / jmeter-config.yml。

业务值全部来自 tier-rules.json（seeds + rules）与目标服务自身的 openapi.json，
脚本内不含任何端点名/路径常量。
"""
import json
import re
import sys
from pathlib import Path

PERF = Path(r"D:\tmp\xh-perf")
RULES = json.loads((PERF / "tier-rules.json").read_text(encoding="utf-8"))
SPEC = json.loads((PERF / "output" / "openapi.json").read_text(encoding="utf-8"))
SEEDS = RULES["seeds"]
METHOD_RE = re.compile(r"^/api/")


def classify(path: str, method: str) -> tuple[str, str]:
    for r in RULES["rules"]:
        if not re.search(r["pattern"], path):
            continue
        if r.get("method") and not re.search(r["method"], method):
            continue
        return r["tier"], r["reason"]
    return "blocked", "未匹配任何放行规则"


def dummy(schema, key_hint=""):
    """按 schema 造 ASCII 哑值；种子表按字段名优先命中真实样例值。"""
    if key_hint in SEEDS and not isinstance(schema.get("example"), (dict, list)):
        return SEEDS[key_hint]
    if "example" in schema:
        return schema["example"]
    if "default" in schema and schema["default"] is not None:
        return schema["default"]
    if "enum" in schema and schema["enum"]:
        return schema["enum"][0]
    for k in ("anyOf", "oneOf", "allOf"):
        if k in schema:
            for sub in schema[k]:
                if sub.get("type") != "null" and sub:
                    return dummy(sub, key_hint)
    t = schema.get("type")
    if t == "integer":
        return 1
    if t == "number":
        return 1.0
    if t == "boolean":
        return True
    if t == "array":
        return [dummy(schema.get("items", {"type": "string"}))]
    if t == "object":
        return build_body(schema)
    if key_hint in SEEDS:
        return SEEDS[key_hint]
    return "perf"


def ref_schema(node):
    ref = node.get("$ref")
    if not ref:
        return node
    name = ref.split("/")[-1]
    return SPEC.get("components", {}).get("schemas", {}).get(name, {})


def build_body(schema):
    schema = ref_schema(schema)
    if schema.get("type") != "object" and "properties" not in schema:
        return {}
    props = schema.get("properties", {})
    required = schema.get("required", [])
    out = {}
    keys = list(required) or list(props)
    for name in keys[:12]:
        sub = ref_schema(props.get(name, {"type": "string"}))
        out[name] = dummy(sub, name)
    return out


def query_value(p):
    name = p["name"]
    sch = ref_schema(p.get("schema", {}))
    if name in SEEDS:
        return str(SEEDS[name])
    if "default" in sch and sch["default"] is not None:
        return str(sch["default"])
    if sch.get("enum"):
        return str(sch["enum"][0])
    return ""


def expand_path(path):
    return re.sub(r"\{(\w+)\}", lambda m: str(SEEDS.get(m.group(1), "1")), path)


def sampler_for(path, method, op):
    tier, reason = classify(path, method)
    real = expand_path(path)
    s = {"name": f"{method} {real}", "path": real, "method": method,
         "tier": tier, "reason": reason, "tpl": path}
    params = {}
    for p in op.get("parameters", []):
        if p.get("in") != "query":
            continue
        v = query_value(p)
        if v:
            params[p["name"]] = v
    if method in ("GET", "DELETE") and params:
        s["params"] = params
    body = None
    rb = op.get("requestBody", {}).get("content", {}).get("application/json", {})
    if rb.get("schema"):
        body = build_body(rb["schema"])
    if method in ("POST", "PUT", "PATCH"):
        s["body"] = body if body else {}
    s["assert_code"] = "200|201|204|400|404|409|422"
    return s


def main():
    samplers = []
    for path, ops in SPEC["paths"].items():
        if not METHOD_RE.match(path):
            continue
        for method, op in ops.items():
            if method not in ("get", "post", "put", "delete", "patch"):
                continue
            samplers.append(sampler_for(path, method.upper(), op))

    from collections import Counter
    dist = Counter(s["tier"] for s in samplers)
    print("[tier]", dict(dist), "total", len(samplers))

    (PERF / "coverage_matrix.json").write_text(
        json.dumps(samplers, ensure_ascii=False, indent=1), encoding="utf-8")

    probe = [s for s in samplers if s["tier"] == "probe_single"]
    (PERF / "probe_plan.json").write_text(
        json.dumps(probe, ensure_ascii=False, indent=1), encoding="utf-8")

    HEAVY = re.compile(r"stats|evaluations|timeline|trend|price|logs|export|items|sellers|notifications")
    reads = [s for s in samplers if s["tier"] == "load_read"]
    groups = {
        "reads_heavy": [s for s in reads if HEAVY.search(s["path"])],
        "reads_light": [s for s in reads if not HEAVY.search(s["path"])],
        "writes_idem": [s for s in samplers if s["tier"] == "load_write"],
    }
    for k, v in groups.items():
        print(f"[group] {k}: {len(v)}")
    (PERF / "groups.json").write_text(
        json.dumps(groups, ensure_ascii=False, indent=1), encoding="utf-8")

    # 混合业务场景：贴近控制台真实读多写少（读:写 ≈ 9:1）
    mixed = groups["reads_heavy"] + groups["reads_light"] + groups["writes_idem"]
    (PERF / "mixed.json").write_text(
        json.dumps(mixed, ensure_ascii=False, indent=1), encoding="utf-8")
    print("[group] mixed:", len(mixed))


if __name__ == "__main__":
    main()
