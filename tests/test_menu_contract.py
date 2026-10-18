# tests/test_menu_contract.py
"""PUT /api/menu 前后端契约测试（T02584 / FR-A-3）

背景：前端曾发送 `{items: [{menu_key, ...}]}`，后端模型是 `{menus: [{key, ...}]}`，
每一次菜单保存都必然 422 —— 且过去没有任何测试能发现，因为它跨了前后端边界。

本测试按前端**实际发出的字面形状**打真实端点（请求体序列化、Pydantic 校验、
MenuManager UPSERT、GET 回读全链路为真），只把数据库换成临时 SQLite，
避免污染开发库；不使用 Mock 替身，否则测不到契约本身。
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine

from xianyu_hunter.infra.db_models import Base
from xianyu_hunter.web.services.menu_manager import MenuManager


def _user_menu_table():
    for tbl in Base.metadata.tables.values():
        if tbl.name == "user_menu_configs":
            return tbl
    raise AssertionError("db_models 中找不到 user_menu_configs 表定义")


@pytest.fixture
def menu_client(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'menu.db'}")
    Base.metadata.create_all(engine, tables=[_user_menu_table()])
    manager = MenuManager(engine)
    import xianyu_hunter.web.routes.api_menu as api_menu

    monkeypatch.setattr(api_menu, "get_menu_manager", lambda: manager)

    from fastapi.testclient import TestClient
    from xianyu_hunter.web.app import create_app

    client = TestClient(create_app())
    # /api/* 全量需鉴权：与 tests/test_api_anticrawl.py 同一口径，用管理令牌 Cookie 直通
    from xianyu_hunter.config import get_settings

    client.cookies.set("xh_token", get_settings().web_token)
    return client, manager


# 前端 menuApi.update 发出的就是这个形状（frontend/src/api/menu.ts）
FRONTEND_PAYLOAD = {
    "menus": [
        {"key": "tasks", "visible": True, "sort_order": 3},
        {"key": "orders", "visible": False, "sort_order": 7},
    ]
}


def test_put_menu_accepts_frontend_payload(menu_client):
    client, _ = menu_client
    resp = client.put("/api/menu", json=FRONTEND_PAYLOAD)
    assert resp.status_code == 200, resp.text


def test_put_menu_persists_and_reads_back(menu_client):
    client, manager = menu_client
    assert client.put("/api/menu", json=FRONTEND_PAYLOAD).status_code == 200

    menus = manager.get_menus("default")
    by_key = {m["key"]: m for m in menus}
    # visible=False 的项不会出现在 GET 结果里（后端只返回可见项），
    # 因此用「tasks 的排序被覆盖 + orders 不可见」两条一起断言持久化生效
    assert "tasks" in by_key
    assert by_key["tasks"]["sort_order"] == 3
    assert "orders" not in by_key
    # registry 里已注册的行情/导出菜单仍必须可解析到路径
    for key in ("price_dashboard", "export"):
        assert key in by_key, f"{key} 不在默认菜单里，menu_registry.yaml 可能被改动"
        assert by_key[key]["path"], f"{key} 缺少 path"


def test_legacy_items_payload_is_rejected(menu_client):
    """旧形状必须 422 —— 这条断言用于锁住契约方向，防止前端改回 items/menu_key"""
    client, _ = menu_client
    resp = client.put(
        "/api/menu",
        json={"items": [{"menu_key": "tasks", "visible": True, "sort_order": 3}]},
    )
    assert resp.status_code == 422


# T02557 / 2.2：曾被注册表漏掉、只能靠手敲 URL 进入的隐藏页
FORMERLY_HIDDEN = ("vector_admin", "help", "menu_admin")


def test_hidden_pages_now_have_menu_entries(menu_client):
    client, _ = menu_client
    resp = client.get("/api/menu")
    assert resp.status_code == 200
    by_key = {m["key"]: m for m in resp.json()["menus"]}
    for key in FORMERLY_HIDDEN:
        assert key in by_key, f"{key} 未进入菜单，仍是隐藏页"
        assert by_key[key]["path"], f"{key} 缺少 path"


def test_menu_admin_cannot_be_hidden(menu_client):
    """菜单管理是唯一恢复入口：请求隐藏它必须被后端拒绝写入，GET 仍返回可见"""
    client, manager = menu_client
    payload = {"menus": [{"key": "menu_admin", "visible": False, "sort_order": 305}]}
    assert client.put("/api/menu", json=payload).status_code == 200

    by_key = {m["key"]: m for m in manager.get_menus("default")}
    assert "menu_admin" in by_key, "菜单管理被隐藏后用户再也进不去，形成死锁"
    assert by_key["menu_admin"]["locked"] is True


# T02558 / FR-B-5：分组标题与图标改为随 GET /api/menu 下发
# 此前前端 SubMenu 图标取「组内第一个菜单项的图标」，多个分组图标雷同、名称靠内置表拼
def test_get_menu_carries_group_meta(menu_client):
    client, _ = menu_client
    data = client.get("/api/menu").json()
    groups = {g["key"]: g for g in data["groups"]}
    assert len(groups) >= 5, f"分组定义缺失：{list(groups)}"
    for key, g in groups.items():
        assert g["label"], f"分组 {key} 缺少中文标题"
        assert g["icon"], f"分组 {key} 缺少图标名"
    # 每个菜单的 category 都要有对应分组，否则前端只能回退到内置常量表（第二份定义）
    categories = {m["category"] for m in data["menus"] if m.get("category")}
    assert categories <= set(groups), f"未定义分组的 category: {categories - set(groups)}"
