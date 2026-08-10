import json, concurrent.futures as cf
import requests
TOKEN = "PgEECYNIneqtk7fb-dyYvA4nzj3YTcjqPOVjZqAJATQ"
H = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

ENDPOINTS = {
    "偏好UPSERT": ("PUT", "http://127.0.0.1:8011/api/preferences", {"perf_test_key": "1"}),
    "创建会话": ("POST", "http://127.0.0.1:8011/api/chatbot/sessions", {"title": "perf-test"}),
    "清理缓存": ("POST", "http://127.0.0.1:8011/api/maintenance/cache", {"target": "temp", "dry_run": True}),
    "配置预览": ("POST", "http://127.0.0.1:8011/api/config/preview", {"antidetect": {"qps": 1.5}}),
}

def hit(name):
    method, url, body = ENDPOINTS[name]
    try:
        r = requests.request(method, url, json=body, headers=H, timeout=15)
        return (name, r.status_code, r.text[:400])
    except Exception as e:
        return (name, "EXC", repr(e)[:200])

for name in ENDPOINTS:
    with cf.ThreadPoolExecutor(max_workers=20) as ex:
        res = list(ex.map(lambda _: hit(name), range(20)))
    codes = {}
    sample_err = None
    for n, code, txt in res:
        codes[code] = codes.get(code, 0) + 1
        if code != 200 and sample_err is None:
            sample_err = txt
    print(f"{name}: codes={codes}")
    if sample_err:
        print(f"   sample error body: {sample_err}")
