"""P1-8 Prompt 在线编辑器 API 单元测试"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from xianyu_hunter.config import get_settings
from xianyu_hunter.web.app import app
from xianyu_hunter.web.deps import get_container
from xianyu_hunter.web.routes import api_prompts


_TEST_TOKEN = "test-token-for-prompts-api"


@pytest.fixture
def client(monkeypatch, tmp_path) -> TestClient:
    """构造 TestClient，重定向 prompt 目录到临时路径"""
    # 固定测试 token
    from xianyu_hunter.config import Settings
    test_settings = Settings(web_token=_TEST_TOKEN)
    monkeypatch.setattr("xianyu_hunter.config.get_settings", lambda: test_settings)
    monkeypatch.setattr("xianyu_hunter.web.app.get_settings", lambda: test_settings, raising=False)

    # 重定向 prompt 目录到临时路径，避免污染真实文件
    monkeypatch.setattr(api_prompts, "_PROMPTS_DIR", tmp_path / "prompts")

    class _FakeContainer:
        pass
    app.dependency_overrides[get_container] = lambda: _FakeContainer()
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_TEST_TOKEN}"}


def test_list_prompts(client: TestClient) -> None:
    """列出所有可编辑 Prompt"""
    resp = client.get("/api/prompts", headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    keys = {p["key"] for p in data["prompts"]}
    assert "parse_task" in keys
    assert "evaluate_condition" in keys
    # 初始状态：无自定义文件，is_custom=False
    for p in data["prompts"]:
        assert p["is_custom"] is False
        assert p["content"]  # 有默认内容


def test_get_prompt(client: TestClient) -> None:
    """获取单个 Prompt"""
    resp = client.get("/api/prompts/parse_task", headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert data["key"] == "parse_task"
    assert "keyword" in data["content"]  # 默认 prompt 含 keyword 字段说明
    assert data["is_custom"] is False


def test_get_unknown_prompt_returns_404(client: TestClient) -> None:
    """未知 Prompt 返回 404"""
    resp = client.get("/api/prompts/unknown", headers=_auth_headers())
    assert resp.status_code == 404


def test_update_prompt(client: TestClient) -> None:
    """更新 Prompt 内容"""
    new_content = "你是一个测试用 Prompt。只输出 JSON: {\"keyword\": \"test\"}"
    resp = client.put(
        "/api/prompts/parse_task",
        json={"content": new_content},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    assert resp.json()["is_custom"] is True

    # 再次读取应返回新内容
    resp = client.get("/api/prompts/parse_task", headers=_auth_headers())
    assert resp.status_code == 200
    assert resp.json()["content"] == new_content
    assert resp.json()["is_custom"] is True


def test_update_prompt_creates_backup(client: TestClient) -> None:
    """更新 Prompt 时自动创建 .bak 备份"""
    # 第一次更新（无原文件，不应创建备份）
    client.put(
        "/api/prompts/parse_task",
        json={"content": "version 1"},
        headers=_auth_headers(),
    )
    data = client.get("/api/prompts/parse_task", headers=_auth_headers()).json()
    assert data["has_backup"] is False

    # 第二次更新（有原文件，应创建备份）
    client.put(
        "/api/prompts/parse_task",
        json={"content": "version 2"},
        headers=_auth_headers(),
    )
    data = client.get("/api/prompts/parse_task", headers=_auth_headers()).json()
    assert data["has_backup"] is True
    assert data["content"] == "version 2"


def test_reset_prompt(client: TestClient) -> None:
    """重置 Prompt 为默认值"""
    # 先自定义
    client.put(
        "/api/prompts/parse_task",
        json={"content": "custom content"},
        headers=_auth_headers(),
    )
    # 重置
    resp = client.post("/api/prompts/parse_task/reset", headers=_auth_headers())
    assert resp.status_code == 200
    assert resp.json()["is_custom"] is False

    # 内容应恢复为默认
    data = client.get("/api/prompts/parse_task", headers=_auth_headers()).json()
    assert "keyword" in data["content"]  # 默认 prompt 含 keyword
    assert data["is_custom"] is False


def test_update_prompt_hot_reload(client: TestClient) -> None:
    """更新后内存中的 prompt 变量应同步更新"""
    new_content = "热更新测试 Prompt"
    client.put(
        "/api/prompts/parse_task",
        json={"content": new_content},
        headers=_auth_headers(),
    )
    # 检查 api_ai 模块的全局变量是否同步
    from xianyu_hunter.web.routes import api_ai
    assert api_ai._SYSTEM_PROMPT == new_content


def test_update_unknown_prompt_returns_404(client: TestClient) -> None:
    """更新未知 Prompt 返回 404"""
    resp = client.put(
        "/api/prompts/unknown",
        json={"content": "test"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 404


def test_update_prompt_empty_content_returns_422(client: TestClient) -> None:
    """空内容返回 422"""
    resp = client.put(
        "/api/prompts/parse_task",
        json={"content": ""},
        headers=_auth_headers(),
    )
    assert resp.status_code == 422
