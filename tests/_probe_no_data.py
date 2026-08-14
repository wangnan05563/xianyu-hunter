import json
def test_probe_no_data(client, monkeypatch):
    from xianyu_hunter.web.services import cookie_store as cs_module
    monkeypatch.setattr(cs_module.CookieStore, "_read_json", lambda self, user_id="default": None)
    client.post("/api/anticrawl/initialize", json={"use_cdp": False}, cookies={"auth_token": "test-admin-token"})
    resp = client.get("/api/anticrawl/health", cookies={"auth_token": "test-admin-token"})
    print("\n=== PROBE RESPONSE ===")
    print(json.dumps(resp.json(), ensure_ascii=False, indent=2, default=str))
    print("=== END ===\n")
