import importlib.util
spec = importlib.util.spec_from_file_location("rr", "regression_replay.py")
rr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rr)

JMX = "D:/code/otherProjects/17_xianyu/test_results/jmeter/scripts/xianyu_load_test_reads.jmx"
info = rr.parse_jmx(JMX)
print("threads", info["threads"], "duration", info["duration"], "samplers", len(info["samplers"]))
print("sample:", {k: info["samplers"][0][k] for k in ("method", "path", "name")})
udv = info["udv"]
ov = {"web_token": "X", "WEB_TOKEN": "X"}
for sm in info["samplers"]:
    if "ORDER_ID" in sm["path"] or "ITEM_ID" in sm["path"]:
        print("var path ->", rr.substitute(sm["path"], udv, ov))
        break
print("200 vs [200]:", rr.expected_ok("200", [{"test_type": 2, "patterns": ["200"]}]))
print("500 vs [200|404|405]:", rr.expected_ok("500", [{"test_type": 2, "patterns": ["200", "404", "405"]}]))
print("404 vs [200|404|405]:", rr.expected_ok("404", [{"test_type": 2, "patterns": ["200", "404", "405"]}]))
