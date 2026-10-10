# tests/test_health_unified.py
"""登录态健康度统一端点测试（PRD FR-C1-1/FR-C1-2，REQ-001/002）

覆盖：
- healthy / degraded / invalid 三态判定
- freshness 优先级：per-user 过期 + default 新鲜 → 结论取 default（T01717 根因场景）
- reasons 逐条结构（source / cookie / issue）
"""
import json
import time

import pytest
from fastapi.testclient import TestClient

from xianyu_hunter.web.app import create_app

_NOW = time.time()
_FUTURE = _NOW + 3600
_PAST = _NOW - 3600


def _m5tk_value(age_sec: float = 0) -> str:
    """构造 _m_h5_tk：32位hex + _ + 13位毫秒时间戳"""
    ts_ms = int((_NOW - age_sec) * 1000)
    return f"a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4_{ts_ms:013d}"


def _full_cookies(m5tk_age: float = 0, cookie2_expires: float = _FUTURE) -> list[dict]:
    return [
        {"name": "cookie2", "value": "a" * 40, "domain": ".goofish.com", "expires": cookie2_expires},
        {"name": "sgcookie", "value": "s" * 40, "domain": ".goofish.com", "expires": _FUTURE},
        {"name": "unb", "value": "952712345", "domain": ".goofish.com", "expires": _PAST},
        {"name": "_m_h5_tk", "value": _m5tk_value(m5tk_age), "domain": ".goofish.com", "expires": -1},
    ]


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    """隔离档案目录与浏览器/collector 依赖"""
    from xianyu_hunter.web.services import cookie_status as cs
    from xianyu_hunter.web.services import cookie_store as store_mod

    monkeypatch.setattr(
        store_mod, "Path", lambda *args: tmp_path / args[-1] if args else tmp_path)
    store = store_mod.CookieStore()
    store._cache = {}
    monkeypatch.setattr(cs, "get_cookie_store", lambda: store)
    # last_login 兜底文件与 data 目录隔离到 tmp_path
    monkeypatch.setattr(cs, "get_data_dir", lambda: tmp_path)
    yield store


@pytest.fixture
def client():
    return TestClient(create_app())


def _write_archive(tmp_path, uid: str, cookies: list[dict], exported_at: float):
    """直接落盘档案文件（模拟真实档案数据）"""
    payload = {
        "exported_at": exported_at,
        "method": "test",
        "cookie_count": len(cookies),
        "cookies": cookies,
    }
    (tmp_path / f"cookies_{uid}.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_healthy_with_fresh_default_archive(client, tmp_path):
    """default 档案含有效身份 Cookie + 未过期 m5tk → healthy"""
    _write_archive(tmp_path, "default", _full_cookies(), _NOW - 60)
    resp = client.get("/api/auth/health/unified")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["status"] == "healthy"
    assert data["freshest_source"] == "cookies_default.json"
    assert data["self_healed"] is False


def test_freshness_prefers_newer_default_over_stale_per_user(client, tmp_path):
    """T01717 根因场景：per-user 档案过期但 default 新鲜 → 结论以 default 为准"""
    stale = [
        {"name": "cookie2", "value": "a" * 40, "domain": ".goofish.com", "expires": _PAST},
        {"name": "sgcookie", "value": "s" * 40, "domain": ".goofish.com", "expires": _PAST},
        {"name": "unb", "value": "111", "domain": ".goofish.com", "expires": -1},
        {"name": "_m_h5_tk", "value": _m5tk_value(7200), "domain": ".goofish.com", "expires": -1},
    ]
    _write_archive(tmp_path, "user_a", stale, exported_at=_NOW - 100)
    _write_archive(tmp_path, "default", _full_cookies(), exported_at=_NOW - 10)
    resp = client.get("/api/auth/health/unified?user_id=user_a")
    assert resp.status_code == 200
    data = resp.json()
    # 旧逻辑按 uid → last_login → default 固定顺序会读 user_a 过期档案误报失效；
    # freshness 口径取 exported_at 最新的 default 档案
    assert data["freshest_source"] == "cookies_default.json"
    assert data["status"] == "healthy"
    # 过期的 user_a 档案在 reasons 中逐条可见（哪个 Cookie / 哪个档案 / 过期）
    expired_reasons = [r for r in data["reasons"]
                       if r["source"] == "cookies_user_a.json" and r["issue"] == "expired"]
    assert {"cookie2", "sgcookie"} <= {r["cookie"] for r in expired_reasons}


def test_degraded_when_m5tk_stale_but_identity_valid(client, tmp_path):
    """身份 Cookie 有效但 m5tk 过期 → degraded（登录态在，实时搜索暂不可用）"""
    _write_archive(tmp_path, "default", _full_cookies(m5tk_age=7200), _NOW - 60)
    resp = client.get("/api/auth/health/unified")
    data = resp.json()
    assert data["status"] == "degraded"
    assert any(r["issue"] == "mtop_token_stale" and r["cookie"] == "_m_h5_tk"
               for r in data["reasons"])


def test_invalid_when_all_archives_identity_expired(client, tmp_path):
    """全部档案身份 Cookie 过期 → invalid + reasons 汇总"""
    stale = [
        {"name": "cookie2", "value": "a" * 40, "domain": ".goofish.com", "expires": _PAST},
        {"name": "sgcookie", "value": "s" * 40, "domain": ".goofish.com", "expires": _PAST},
        {"name": "unb", "value": "952712345", "domain": ".goofish.com", "expires": -1},
        {"name": "_m_h5_tk", "value": _m5tk_value(7200), "domain": ".goofish.com", "expires": -1},
    ]
    _write_archive(tmp_path, "default", stale, _NOW - 60)
    resp = client.get("/api/auth/health/unified")
    data = resp.json()
    assert data["status"] == "invalid"
    assert data["freshest_source"] is None
    expired = {r["cookie"] for r in data["reasons"] if r["issue"] == "expired"}
    assert "cookie2" in expired


def test_invalid_when_no_archive(client, tmp_path):
    """无任何档案 → invalid + no_cookie_data"""
    resp = client.get("/api/auth/health/unified")
    data = resp.json()
    assert data["status"] == "invalid"
    assert any(r["issue"] == "no_cookie_data" for r in data["reasons"])
    assert data["sources"] == []


def test_sources_detail_exposed(client, tmp_path):
    """sources 逐源透出评估明细（供 T01778 诊断抽屉展示）"""
    _write_archive(tmp_path, "default", _full_cookies(), _NOW - 60)
    resp = client.get("/api/auth/health/unified")
    data = resp.json()
    src = data["sources"][0]
    assert src["source"] == "cookies_default.json"
    assert set(src["identity_valid"]) == {"cookie2", "sgcookie", "unb"}
    assert src["has_valid_m5tk"] is True
    assert src["cookie_count"] == 4
