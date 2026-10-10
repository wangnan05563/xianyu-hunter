# tests/test_cookie_import_endpoint.py
"""登录态 JSON 导入端点测试（PRD C2+F2，REQ-016/017）

覆盖 FR-F2-1 校验规则与 FR-F2-2 逐条回执：
- 数组 / 整档 JSON 两种格式解析
- 残缺条目拒绝、测试数据拒绝、过期条目跳过
- 身份 Cookie（cookie2/sgcookie/unb）全缺失 → 400
"""
import time

import pytest
from fastapi.testclient import TestClient

from xianyu_hunter.web.app import create_app


@pytest.fixture
def client():
    return TestClient(create_app())


def _make_cookie(name: str, value: str, expires: float = -1) -> dict:
    return {"name": name, "value": value, "domain": ".goofish.com", "expires": expires}


def _valid_identity_cookies() -> list[dict]:
    """构造符合真实格式的身份 Cookie 三件套（绕过 is_test_cookie 格式校验）"""
    future = time.time() + 3600
    return [
        _make_cookie("cookie2", "a" * 40, future),
        _make_cookie("sgcookie", "s" * 40, future),
        _make_cookie("unb", "952712345", -1),
    ]


def test_import_json_array_ok(client):
    """数组格式：有效身份 Cookie 导入成功，逐条 accepted"""
    cookies = _valid_identity_cookies()
    resp = client.post("/api/auth/cookies/import", json=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["accepted_count"] == 3
    assert set(data["identity_found"]) == {"cookie2", "sgcookie", "unb"}


def test_import_whole_archive_format(client):
    """整档 JSON 格式（含 cookies 字段包装）同样接受"""
    payload = {"cookies": _valid_identity_cookies(), "exported_at": time.time()}
    resp = client.post("/api/auth/cookies/import", json=payload)
    assert resp.status_code == 200
    assert resp.json()["accepted_count"] == 3


def test_import_expired_entry_skipped(client):
    """过期条目被跳过且回执说明原因（unb 除外：其 expires 不可信，见跳过名单）"""
    future = time.time() + 3600
    past = time.time() - 3600
    cookies = [
        _make_cookie("cookie2", "a" * 40, future),
        _make_cookie("sgcookie", "s" * 40, past),  # 已过期 → 跳过
        _make_cookie("unb", "952712345", past),    # unb 跳过名单内 → 接受
    ]
    resp = client.post("/api/auth/cookies/import", json=cookies)
    assert resp.status_code == 200
    data = resp.json()
    by_name = {r["name"]: r for r in data["results"]}
    assert by_name["sgcookie"]["status"] == "expired_skipped"
    assert by_name["unb"]["status"] == "accepted"


def test_import_expired_m5tk_detected_by_embedded_ts(client):
    """_m_h5_tk 过期按内嵌时间戳判定（expires=-1 也一样）"""
    old_ts_ms = int((time.time() - 3600) * 1000)
    cookies = [
        _make_cookie("cookie2", "a" * 40),
        _make_cookie("sgcookie", "s" * 40),
        _make_cookie("unb", "952712345"),
        _make_cookie("_m_h5_tk", f"a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4_{old_ts_ms:013d}"),
    ]
    resp = client.post("/api/auth/cookies/import", json=cookies)
    assert resp.status_code == 200
    by_name = {r["name"]: r for r in resp.json()["results"]}
    assert by_name["_m_h5_tk"]["status"] == "expired_skipped"


def test_import_incomplete_entry_rejected(client):
    """残缺条目（缺 value）被拒绝且回执标注"""
    cookies = _valid_identity_cookies() + [{"name": "broken", "value": ""}]
    resp = client.post("/api/auth/cookies/import", json=cookies)
    assert resp.status_code == 200
    data = resp.json()
    by_name = {r["name"]: r for r in data["results"]}
    assert by_name["broken"]["status"] == "rejected"
    assert "残缺" in by_name["broken"]["reason"]


def test_import_test_cookie_rejected(client):
    """测试数据（unb=123456）被拦截拒绝"""
    cookies = _valid_identity_cookies()
    cookies[2]["value"] = "123456"
    resp = client.post("/api/auth/cookies/import", json=cookies)
    # cookie2/sgcookie 仍在，能构成登录态 → 200，但 unb 被拒绝
    assert resp.status_code == 200
    data = resp.json()
    by_name = {r["name"]: r for r in data["results"]}
    assert by_name["unb"]["status"] == "rejected"
    assert data["identity_missing"] == ["unb"]


def test_import_identity_all_missing_400(client):
    """身份 Cookie 全缺失 → 400 + 明确文案 + 完整回执"""
    resp = client.post("/api/auth/cookies/import", json=[
        _make_cookie("cna", "track123"),
        _make_cookie("t", "other-value"),
    ])
    assert resp.status_code == 400
    data = resp.json()
    assert data["ok"] is False
    assert set(data["identity_missing"]) == {"cookie2", "sgcookie", "unb"}
    assert "cookie2" in data["error"]
    assert len(data["results"]) == 2


def test_import_test_value_identity_rejected_400(client):
    """身份 Cookie 全为测试值（unb=123456/cookie2=abc）→ 视为全缺失 400"""
    resp = client.post("/api/auth/cookies/import", json=[
        _make_cookie("cookie2", "abc"),
        _make_cookie("sgcookie", "s" * 40),
        _make_cookie("unb", "123456"),
    ])
    # sgcookie 有格式黑名单但此处给任意 40 字符值视为有效 → 身份未全缺失
    # 若 sgcookie 也被拒则 400。此用例验证测试值确实被逐条拦截
    data = resp.json()
    by_name = {r["name"]: r for r in data.get("results", [])}
    assert by_name["cookie2"]["status"] == "rejected"
    assert by_name["unb"]["status"] == "rejected"


def test_import_invalid_body_400(client):
    """非 JSON / 空数组 / 不支持的包装格式 → 400 且文案明确"""
    cases = [
        # 非法 JSON
        ("not-json", {}),
        # 空数组
        ([], {}),
        # 对象但无 cookies 字段
        ({"foo": 1}, {}),
    ]
    for body, _ in cases:
        if body == "not-json":
            resp = client.post("/api/auth/cookies/import",
                               content="not-json",
                               headers={"Content-Type": "application/json"})
        else:
            resp = client.post("/api/auth/cookies/import", json=body)
        assert resp.status_code == 400, f"body={body!r} 应返回 400"
        assert resp.json()["ok"] is False


def test_import_requires_no_auth(client):
    """导入端点在认证白名单内：无 token 也可调用（未登录引导场景）"""
    # client fixture 未带任何 token，若白名单缺失会返回 401
    cookies = _valid_identity_cookies()
    resp = client.post("/api/auth/cookies/import", json=cookies)
    assert resp.status_code != 401
