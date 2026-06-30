"""list_links API 端点测试：覆盖 display 字段语义校正的端到端流程

回归测试：DB 中存储的 display 字段可能因闲鱼 API 字段语义不稳定而错位
（如 region 字段实际是脱敏昵称），list_links 端点必须对返回给前端的 display
字段做 normalize_display_fields 校正，避免"卖家"列显示地区、"地区"列显示
昵称等视觉错位问题。
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from xianyu_hunter.config import Settings
from xianyu_hunter.infra.repository import Repository
from xianyu_hunter.web.app import app
from xianyu_hunter.web.deps import get_container


_TEST_TOKEN = "test-token-list-links"


@pytest.fixture
def tmp_repo() -> Repository:
    """使用临时数据库"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db_path = str(Path(d) / "test.db")
        repo = Repository(db_path)
        yield repo
        repo.engine.dispose()


@pytest.fixture
def client(tmp_repo: Repository, monkeypatch) -> TestClient:
    """构造 TestClient，注入临时 repository 和测试 token"""
    test_settings = Settings(web_token=_TEST_TOKEN)

    def _fake_settings():
        return test_settings

    monkeypatch.setattr("xianyu_hunter.config.get_settings", _fake_settings)
    monkeypatch.setattr("xianyu_hunter.web.app.get_settings", _fake_settings, raising=False)

    class _FakeContainer:
        def __init__(self, repo):
            self.repo = repo

    fake = _FakeContainer(tmp_repo)
    app.dependency_overrides[get_container] = lambda: fake
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_TEST_TOKEN}"}


def test_list_links_corrects_region_to_seller_nick(client: TestClient, tmp_repo: Repository) -> None:
    """回归测试：DB 中 region 字段实际是脱敏昵称时，list_links 必须校正

    复现场景：闲鱼 API 在某些商品上把"卖家昵称"放到 region 字段、seller_nick 为空
    （与用户截图一致：DB 中 region='嘟***子', seller_nick='', seller_credit=''）
    list_links 端点必须对每行 display 调用 normalize_display_fields，
    把 region 字段的脱敏昵称移到 seller_nick，region 留空。
    """
    # 准备：创建任务和一条 DB 中存了错位 display 的记录
    tmp_repo.upsert_task({"id": "t1", "name": "测试任务", "keyword": "DDR4"})

    # 模拟历史错位数据：region 实际是昵称
    # title 必须包含关键词 "DDR4"，否则会被 _task_link_matches_task 过滤掉
    tmp_repo.upsert_task_link(
        task_id="t1",
        link_type="item",
        link_key="item_1",
        display={
            "title": "镁光DDR4 32G 3200笔记本内存",
            "price": 680.0,
            "thumb_url": "https://example.com/img.jpg",
            "region": "嘟***子",  # ← 实际是昵称
            "seller_nick": "",    # ← 真实为空
            "seller_credit": "",
            "is_sold": False,
        },
        source="auto",
    )

    # 调用 list_links API
    resp = client.get("/api/tasks/t1/links", headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1

    item = data["items"][0]
    display = item["display"]

    # 关键断言：display 必须经过校正
    # 脱敏昵称应移到 seller_nick，region 应清空
    assert display["seller_nick"] == "嘟***子", \
        f"region 的脱敏昵称应被校正到 seller_nick，但得到 seller_nick={display.get('seller_nick')!r}"
    assert display["region"] == "", \
        f"region 应被清空（值是脱敏昵称），但得到 region={display.get('region')!r}"


def test_list_links_corrects_multiple_misaligned_rows(client: TestClient, tmp_repo: Repository) -> None:
    """回归测试：批量错位数据全部应被校正"""
    tmp_repo.upsert_task({"id": "t1", "name": "测试任务", "keyword": "DDR4"})

    # 多条错位数据，title 必须包含关键词 "DDR4" 才能通过 _task_link_matches_task 过滤
    misaligneds = [
        ("item_1", "行***三"),
        ("item_2", "荒***芽"),
        ("item_3", "苏***根"),
        ("item_4", "嘟***子"),
    ]
    for item_id, masked_nick in misaligneds:
        tmp_repo.upsert_task_link(
            task_id="t1",
            link_type="item",
            link_key=item_id,
            display={
                "title": f"DDR4 32G 商品 {item_id}",
                "price": 100.0,
                "region": masked_nick,
                "seller_nick": "",
                "is_sold": False,
            },
            source="auto",
        )

    resp = client.get("/api/tasks/t1/links", headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 4

    # 全部应被校正
    by_key = {item["link_key"]: item["display"] for item in data["items"]}
    for item_id, masked_nick in misaligneds:
        assert by_key[item_id]["seller_nick"] == masked_nick, \
            f"{item_id} 应被校正到 seller_nick={masked_nick!r}"
        assert by_key[item_id]["region"] == "", \
            f"{item_id} 的 region 应清空"


def test_list_links_preserves_valid_region(client: TestClient, tmp_repo: Repository) -> None:
    """回归测试：合法地区名（省份/直辖市）应保持原样"""
    tmp_repo.upsert_task({"id": "t1", "name": "测试任务", "keyword": "DDR4"})

    tmp_repo.upsert_task_link(
        task_id="t1",
        link_type="item",
        link_key="item_1",
        display={
            "title": "DDR4 商品",
            "price": 100.0,
            "region": "天津",  # 合法省份名
            "seller_nick": "小明",
            "is_sold": False,
        },
        source="auto",
    )

    resp = client.get("/api/tasks/t1/links", headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    display = data["items"][0]["display"]

    # 合法地区不应被误判为昵称
    assert display["region"] == "天津"
    assert display["seller_nick"] == "小明"


def test_list_links_corrects_seller_nick_to_publish_time(client: TestClient, tmp_repo: Repository) -> None:
    """回归测试：seller_nick 实际是发布时间描述时，应被校正到 publish_time"""
    tmp_repo.upsert_task({"id": "t1", "name": "测试任务", "keyword": "DDR4"})

    tmp_repo.upsert_task_link(
        task_id="t1",
        link_type="item",
        link_key="item_1",
        display={
            "title": "DDR4 商品",
            "price": 100.0,
            "region": "",  # 真实地区为空
            "seller_nick": "一周内发布",  # 实际是发布时间描述
            "seller_credit": "",
            "publish_time": None,
            "is_sold": False,
        },
        source="auto",
    )

    resp = client.get("/api/tasks/t1/links", headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    display = data["items"][0]["display"]

    # seller_nick 应被清空（因为它不是昵称）
    # publish_time 应被填充为"一周内发布"
    assert display["seller_nick"] == "", \
        f"发布时间描述不应作为 seller_nick，但得到 {display.get('seller_nick')!r}"
    assert display["publish_time"] == "一周内发布", \
        f"发布时间描述应被移到 publish_time，但得到 {display.get('publish_time')!r}"


def test_batch_upsert_accepts_string_publish_time(tmp_repo: Repository) -> None:
    """回归测试：batch_upsert_item_task_links 接受字符串类型的 publish_time

    复现 bug：live_search 结果中 publish_time 已被转为 ISO 字符串，
    但 _build_item_link_rows 调用 publish_time.isoformat() 期望 datetime 对象，
    导致 'str' object has no attribute 'isoformat' 错误。
    """
    tmp_repo.upsert_task({"id": "t1", "name": "测试任务", "keyword": "DDR4"})

    # 模拟 live_search 传入的 items_data：publish_time 是 ISO 字符串
    items_data = [
        {
            "item_id": "item_str_pt",
            "title": "DDR4 32G 内存条",
            "price": 680.0,
            "thumb_url": "https://example.com/img.jpg",
            "brand": "",
            "seller_id": "seller_1",
            "seller_nick": "小明",
            "region": "天津",
            "publish_time": "2026-06-27T10:30:00",  # 字符串，非 datetime
            "want_cnt": 5,
            "view_cnt": 100,
            "is_sold": False,
        },
    ]

    # 不应抛出 'str' object has no attribute 'isoformat'
    saved = tmp_repo.batch_upsert_item_task_links(
        task_id="t1",
        items_data=items_data,
        source="live",
    )
    assert saved >= 1, "应至少写入 1 条记录"

    # 验证 publish_time 被正确存储为字符串
    rows = tmp_repo.list_task_links(task_id="t1")
    item_row = next(r for r in rows if r["link_type"] == "item")
    display = item_row["display"]
    if isinstance(display, str):
        import json
        display = json.loads(display)
    assert display["publish_time"] == "2026-06-27T10:30:00", \
        f"publish_time 应原样存储为字符串，但得到 {display.get('publish_time')!r}"


def test_list_links_enriches_is_sold_from_items_table(client: TestClient, tmp_repo: Repository) -> None:
    """回归测试：items 表 is_sold=1 时，list_links 必须将 display.is_sold 补全为 True

    复现 bug：_enrich_with_item_data 曾因过时注释"is_sold 不在 items 表中"而不补全 is_sold，
    导致 refresh_item/mark_sold 已将 items.is_sold 更新为 1，但前端仍显示"在售"。
    修复后 is_sold 总是以 items 表为准，即使 display 中已有 is_sold=False 也会被覆盖。
    """
    tmp_repo.upsert_task({"id": "t1", "name": "测试任务", "keyword": "DDR4"})

    # 1. 写入 items 表：商品已售（is_sold=1）
    tmp_repo.upsert_item({
        "id": "item_sold_001",
        "task_id": "t1",
        "title": "DDR4 已售内存条",
        "price": 200.0,
        "is_sold": 0,  # 初始未售
    })
    tmp_repo.mark_sold("item_sold_001")  # 标记为已售，items.is_sold=1

    # 2. 写入 task_links.display：is_sold=False（旧值，模拟采集前的数据）
    tmp_repo.upsert_task_link(
        task_id="t1",
        link_type="item",
        link_key="item_sold_001",
        display={
            "title": "DDR4 已售内存条",
            "price": 200.0,
            "is_sold": False,  # 旧值，与 items 表不一致
            "url": "https://www.goofish.com/item?id=item_sold_001",
        },
        source="auto",
    )

    # 3. 调用 list_links 端点
    resp = client.get("/api/tasks/t1/links", headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) > 0, "应至少返回 1 条记录"

    item_row = data["items"][0]
    display = item_row["display"]
    if isinstance(display, str):
        import json
        display = json.loads(display)

    # 4. 验证 is_sold 被 _enrich_with_item_data 从 items 表补全为 True
    assert display.get("is_sold") is True, \
        f"items 表 is_sold=1 时，display.is_sold 应被补全为 True，但得到 {display.get('is_sold')!r}"
