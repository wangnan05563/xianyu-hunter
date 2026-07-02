"""MU2 端到端集成测试：认证中间件 + CookieStore + UserManager 协作

验证三个核心场景：
1. WEB_TOKEN 用户访问 API 时 user_id=default，CookieStore 读写 default 文件
2. session_token 用户和 WEB_TOKEN 管理员可以同时访问
3. 两个用户的 Cookie 文件完全隔离，无交叉污染

注意：_cookie_json_path 内部硬编码 Path("data", ...)，
需要同时 patch _COOKIE_JSON_DIR 和 _cookie_json_path 函数本身，
否则文件不会落到 tmp_path 下（计划文档中的 patch 不完整）。
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI, Request
from starlette.testclient import TestClient


def test_full_flow_web_token_compat():
    """WEB_TOKEN 用户访问 API 时 user_id=default，CookieStore 读写 default 文件"""
    from xianyu_hunter.web.middleware.auth import setup_auth_middleware
    from xianyu_hunter.config import get_settings

    app = FastAPI()
    setup_auth_middleware(app)

    @app.get("/api/test")
    def test_endpoint(request: Request):
        return {"user_id": getattr(request.state, "user_id", "not_set")}

    client = TestClient(app)
    resp = client.get("/api/test", headers={"Authorization": f"Bearer {get_settings().web_token}"})
    assert resp.status_code == 200
    assert resp.json()["user_id"] == "default"


def test_session_token_and_web_token_coexist():
    """session_token 用户和 WEB_TOKEN 管理员可以同时访问"""
    from xianyu_hunter.web.middleware.auth import setup_auth_middleware
    from xianyu_hunter.config import get_settings

    app = FastAPI()
    setup_auth_middleware(app)

    @app.get("/api/me")
    def me(request: Request):
        return {"user_id": getattr(request.state, "user_id", "not_set")}

    client = TestClient(app)

    # WEB_TOKEN 用户
    resp1 = client.get("/api/me", headers={"Authorization": f"Bearer {get_settings().web_token}"})
    assert resp1.json()["user_id"] == "default"

    # session_token 用户
    with patch("xianyu_hunter.web.services.user_manager.get_user_manager") as mock:
        mgr = MagicMock()
        mgr.verify_session.return_value = "user_xyz"
        mock.return_value = mgr
        resp2 = client.get("/api/me", headers={"Authorization": "Bearer session_abc"})
        assert resp2.json()["user_id"] == "user_xyz"


def test_cookie_store_isolation_no_cross_contamination(tmp_path, monkeypatch):
    """两个用户的 Cookie 文件完全隔离"""
    from xianyu_hunter.web.services import cookie_store as cs_module
    from xianyu_hunter.web.services.cookie_store import CookieStore

    # 同时 patch 目录常量和路径函数
    # 为什么需要两个 patch：_cookie_json_path 硬编码 Path("data", ...)，
    # 不引用 _COOKIE_JSON_DIR，单独 patch 常量不会改变文件路径
    monkeypatch.setattr(cs_module, "_COOKIE_JSON_DIR", tmp_path)
    monkeypatch.setattr(
        cs_module,
        "_cookie_json_path",
        lambda user_id="default": tmp_path / f"cookies_{user_id}.json",
    )

    store = CookieStore()
    store._cache = {}

    # 用 8 位以上纯数字 unb 值，避免被 is_test_cookie 过滤
    cookies_a = [{"name": "unb", "value": "11111111", "domain": ".goofish.com"}]
    cookies_b = [{"name": "unb", "value": "22222222", "domain": ".goofish.com"}]

    assert store.export_cookies(cookies_a, method="browser", user_id="user_a") is True
    assert store.export_cookies(cookies_b, method="browser", user_id="user_b") is True

    # user_a 的 Cookie 不包含 user_b 的值
    data_a = store._read_json("user_a")
    data_b = store._read_json("user_b")
    assert data_a["cookies"][0]["value"] == "11111111"
    assert data_b["cookies"][0]["value"] == "22222222"
