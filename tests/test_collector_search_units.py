"""批次 4 覆盖率用例：collector/_search.py 的模块级纯函数与响应/cookie 转换

这些函数是搜索链路解析 Goofish API 响应的基础设施，不依赖浏览器页面，
可用纯数据结构驱动；`_sync_response_cookies_to_context` 用 mock page 驱动。
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from loguru import logger as loguru_logger

from xianyu_hunter.domain.item import ItemSummary
from xianyu_hunter.infra.selectors import SelectorRepo
from xianyu_hunter.modules.collector import Collector
from xianyu_hunter.modules.collector import _search as sm


@pytest.fixture
def caplog_info(caplog: pytest.LogCaptureFixture):
    """把 loguru DEBUG+ 桥接到标准 logging，使 caplog 可断言

    搜索链路的关键降级信号（unroute 超时、DOM 无卡片等）刻意用 DEBUG 避免刷屏，
    断言这些分支需要 DEBUG 级可见。
    """
    caplog.set_level(logging.DEBUG)
    bridge = logging.getLogger("search_cov")
    _level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "EXCEPTION": logging.ERROR,
    }

    def _sink(message: Any) -> None:
        record = message.record
        std_level = _level_map.get(record["level"].name)
        if std_level is not None:
            bridge.log(std_level, record["message"])

    sink_id = loguru_logger.add(_sink, level="DEBUG")
    try:
        yield caplog
    finally:
        loguru_logger.remove(sink_id)


# ============ key 归一化与递归取值 ============


def test_normalize_key_and_is_scalar() -> None:
    assert sm._normalize_key("Item_Id") == "itemid"
    assert sm._normalize_key("item-id") == "itemid"
    assert sm._normalize_key(None) == "none"
    assert sm._is_scalar("x") is True
    assert sm._is_scalar(0) is True
    assert sm._is_scalar("") is False
    assert sm._is_scalar(None) is False
    assert sm._is_scalar(["a"]) is False


def test_find_value_by_key_dict_list_and_depth() -> None:
    obj = {"data": {"item": {"title": " 二手显卡 ", "nested": {"price": 12}}}}
    assert sm._find_value_by_key(obj, "title") == " 二手显卡 "
    assert sm._find_value_by_key(obj, "price") == 12
    assert sm._find_value_by_key([{"a": {"b": "hit"}}], "b") == "hit"
    assert sm._find_value_by_key(obj, "missing") is None
    assert sm._find_value_by_key("scalar", "title") is None
    assert sm._find_value_by_key(123, "title") is None


def test_find_value_by_key_respects_max_depth() -> None:
    deep: Any = {"leaf": "value"}
    for _ in range(8):
        deep = {"wrap": deep}
    assert sm._find_value_by_key(deep, "leaf", 0, max_depth=3) is None
    assert sm._find_value_by_key(deep, "leaf", 0, max_depth=10) == "value"


def test_find_value_in_list_scans_first_40_items() -> None:
    items = [{"id": f"n{i}"} for i in range(45)]
    assert sm._find_value_by_key(items, "id") == "n0"
    tail = [{"filler": 1}] * 40 + [{"id": "late"}]
    assert sm._find_value_by_key(tail, "id") is None


def test_first_value_and_first_text() -> None:
    obj = {"payload": {"sellerNick": " 小铺 "}}
    # _first_value 原样返回命中值，去空白是 _first_text 的职责
    assert sm._first_value(obj, ("nope", "userNick", "sellerNick")) == " 小铺 "
    assert sm._first_text(obj, ("userNick",)) == ""
    assert sm._first_text(obj, ("sellerNick",)) == "小铺"
    assert sm._first_text({"nick": 42}, ("nick",)) == "42"


# ============ 数值 / 图片 / 时间转换 ============


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, 0), ("", 0), (True, 1), (False, 0), (7, 7), (7.9, 7),
        ("1,472", 1472), ("1472浏览", 1472), ("无", 0), ("  88 ", 88),
    ],
)
def test_coerce_int_variants(value: Any, expected: int) -> None:
    assert sm._coerce_int(value) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, 0.0), ("", 0.0), (12, 12.0), (12.5, 12.5),
        ("¥1,200.50", 1200.5), ("1.5万", 15000.0), ("2万", 20000.0), ("面议", 0.0),
    ],
)
def test_coerce_price_variants(value: Any, expected: float) -> None:
    assert sm._coerce_price(value) == expected


def test_normalize_image_url() -> None:
    assert sm._normalize_image_url("") == ""
    assert sm._normalize_image_url(None) == ""
    assert sm._normalize_image_url("data:image/png;base64,AA") == ""
    assert sm._normalize_image_url(" //cdn.com/a.jpg ") == "https://cdn.com/a.jpg"
    assert sm._normalize_image_url("http://cdn.com/a.jpg") == "http://cdn.com/a.jpg"
    assert sm._normalize_image_url("https://cdn.com/a.jpg") == "https://cdn.com/a.jpg"
    assert sm._normalize_image_url("cdn.com/a.jpg") == "https://cdn.com/a.jpg"


def test_parse_api_publish_time() -> None:
    assert sm._parse_api_publish_time(None) is None
    assert sm._parse_api_publish_time("") is None
    secs = 1_760_000_000
    assert sm._parse_api_publish_time(secs) == datetime.fromtimestamp(secs, tz=timezone.utc)
    assert sm._parse_api_publish_time(secs * 1000) == datetime.fromtimestamp(secs, tz=timezone.utc)
    assert sm._parse_api_publish_time(str(secs)) == datetime.fromtimestamp(secs, tz=timezone.utc)
    assert sm._parse_api_publish_time(str(secs * 1000)) == datetime.fromtimestamp(secs, tz=timezone.utc)
    assert sm._parse_api_publish_time("2026-10-01T08:30:00Z") == datetime(
        2026, 10, 1, 8, 30, tzinfo=timezone.utc
    )
    assert sm._parse_api_publish_time("刚刚") is None
    assert sm._parse_api_publish_time(float("inf")) is None


# ============ API 响应字段抽取 ============


def test_extract_api_item_fields_from_nested_shapes() -> None:
    raw = {
        "data": {
            "item": {"itemId": "123456", "title": "金士顿 16G", "price": "1,299.00"},
            "sellerInfo": {"sellerId": "9988", "userNick": "数码小铺", "region": "浙江 杭州"},
            "picUrl": "//img.alicdn.com/tps-2-2.png",
            "mainPicUrl": "https://img.alicdn.com/real.jpg",
            "wantCnt": "45人想要",
            "viewCnt": 1472,
            "publishTime": 1_760_000_000,
            "itemDesc": "全新未拆封",
            "sellerCredit": "极好",
        }
    }
    fields = sm._extract_api_item_fields(raw)
    assert fields["item_id"] == "123456"
    assert fields["title"] == "金士顿 16G"
    assert fields["price"] == 1299.0
    assert fields["seller_id"] == "9988"
    assert fields["thumb_url"] == "https://img.alicdn.com/real.jpg"
    assert (fields["want_cnt"], fields["view_cnt"]) == (45, 1472)
    assert fields["publish_time"] == datetime.fromtimestamp(1_760_000_000, tz=timezone.utc)
    assert fields["description"] == "全新未拆封"
    assert fields["seller_credit"] == "极好"
    # semantic_raw 合并了 source 顶层 key，便于下游按原始字段名取值
    assert fields["semantic_raw"]["userNick"] == "数码小铺"
    assert fields["semantic_raw"]["picUrl"] == "//img.alicdn.com/tps-2-2.png"


def test_extract_api_item_fields_flat_and_missing_thumb() -> None:
    fields = sm._extract_api_item_fields({"itemId": "1", "title": "内存", "price": None})
    assert fields["item_id"] == "1"
    assert fields["price"] == 0.0
    assert fields["thumb_url"] == ""
    assert fields["publish_time"] is None
    # 全部 thumb key 都是占位图时保持空串
    placeholder = sm._extract_api_item_fields({"picUrl": "//x/1x1.png", "pic": "data:image/png;base64"})
    assert placeholder["thumb_url"] == ""


# ============ Set-Cookie → Playwright cookie ============


def test_set_cookie_headers_from_response_variants() -> None:
    array_style = SimpleNamespace(
        headers_array=lambda: [
            {"name": "Set-Cookie", "value": "cookie2=abc; Domain=.goofish.com"},
            {"name": "content-type", "value": "application/json"},
            {"name": "Set-Cookie", "value": ""},
        ]
    )
    assert sm._set_cookie_headers_from_response(array_style) == ["cookie2=abc; Domain=.goofish.com"]

    map_style = SimpleNamespace(headers={"set-cookie": "unb=1; Domain=.goofish.com", "x-other": "y"})
    assert sm._set_cookie_headers_from_response(map_style) == ["unb=1; Domain=.goofish.com"]

    # headers 以方法形式暴露时先调用再遍历
    callable_style = SimpleNamespace(headers=lambda: {"Set-Cookie": "t=1; Domain=.goofish.com"})
    assert sm._set_cookie_headers_from_response(callable_style) == ["t=1; Domain=.goofish.com"]

    assert sm._set_cookie_headers_from_response(SimpleNamespace()) == []

    class _Boom:
        @property
        def headers_array(self):  # noqa: ANN201
            raise RuntimeError("nav")

        @property
        def headers(self):  # noqa: ANN201
            raise RuntimeError("nav")

    assert sm._set_cookie_headers_from_response(_Boom()) == []


def test_cookies_from_set_cookie_headers() -> None:
    headers = [
        "cookie2=abc123; Domain=.goofish.com; Path=/; Secure; HttpOnly; SameSite=Lax",
        "unb=9527; Domain=.goofish.com; SameSite=None",
        "_m_h5_tk=token; SameSite=Strict",
        "not-a-cookie-header",
        # RFC 2965 风格的扩展属性（部分服务端会下发 $foo=1）会让 SimpleCookie 抛 CookieError
        "k=v; $foo=1",
    ]
    cookies = sm._cookies_from_set_cookie_headers(headers, "https://h5api.m.goofish.com/h5/x/")
    by_name = {c["name"]: c for c in cookies}
    assert by_name["cookie2"]["domain"] == ".goofish.com"
    assert by_name["cookie2"]["secure"] is True
    assert by_name["cookie2"]["httpOnly"] is True
    assert by_name["cookie2"]["sameSite"] == "Lax"
    assert by_name["cookie2"]["path"] == "/"
    assert by_name["unb"]["sameSite"] == "None"
    # 无 Domain 时用响应 origin 兜底为 url
    assert by_name["_m_h5_tk"]["url"] == "https://h5api.m.goofish.com/"
    assert by_name["_m_h5_tk"]["sameSite"] == "Strict"
    # 无 = 的 header 解析不出 morsel，扩展属性 header 整体被拒，两者都不进结果
    assert "not-a-cookie-header" not in by_name
    assert "k" not in by_name
    assert sm._cookies_from_set_cookie_headers(["x=1"], "") == []


# ============ _sync_response_cookies_to_context ============


async def test_sync_response_cookies_writes_context_and_store(caplog_info, monkeypatch) -> None:
    from xianyu_hunter.web.services import cookie_store as cs

    store = MagicMock()
    monkeypatch.setattr(cs, "get_cookie_store", lambda: store)
    response = MagicMock()
    response.headers_array = MagicMock(
        return_value=[{"name": "Set-Cookie", "value": "_m_h5_tk=tk-value; Domain=.goofish.com"}]
    )
    response.url = "https://h5api.m.goofish.com/h5/mtop/x"
    page = AsyncMock()
    page.context = AsyncMock()
    page.context.add_cookies = AsyncMock()

    assert await sm._sync_response_cookies_to_context(page, response) == 1
    cookies = page.context.add_cookies.await_args.args[0]
    assert cookies[0]["name"] == "_m_h5_tk"
    store.update_cookie_values.assert_called_once_with({"_m_h5_tk": "tk-value"})
    assert any("MTOP Set-Cookie" in r.message for r in caplog_info.records)


async def test_sync_response_cookies_short_circuits(monkeypatch) -> None:
    from xianyu_hunter.web.services import cookie_store as cs

    store = MagicMock()
    monkeypatch.setattr(cs, "get_cookie_store", lambda: store)
    page = AsyncMock()
    page.context = AsyncMock()
    page.context.add_cookies = AsyncMock()
    no_headers = MagicMock(spec=[])
    assert await sm._sync_response_cookies_to_context(page, no_headers) == 0
    page.context.add_cookies.assert_not_awaited()

    unparsable = MagicMock()
    unparsable.headers_array = MagicMock(return_value=[{"name": "Set-Cookie", "value": "x=1"}])
    unparsable.url = ""
    assert await sm._sync_response_cookies_to_context(page, unparsable) == 0
    page.context.add_cookies.assert_not_awaited()


async def test_sync_response_cookies_reports_store_failure(caplog_info, monkeypatch) -> None:
    response = MagicMock()
    response.headers_array = MagicMock(
        return_value=[{"name": "set-cookie", "value": "cookie2=abc; Domain=.goofish.com"}]
    )
    response.url = "https://www.goofish.com/search"
    page = AsyncMock()
    page.context = AsyncMock()

    import xianyu_hunter.web.services.cookie_store as cs

    def _boom():
        raise RuntimeError("store offline")

    monkeypatch.setattr(cs, "get_cookie_store", _boom)
    assert await sm._sync_response_cookies_to_context(page, response) == 1
    assert any("回写 JSON 失败" in r.message and r.levelname == "WARNING" for r in caplog_info.records)


# ============ 搜索筛选参数 / 频率伪装 ============


def _make_collector() -> Collector:
    browser = MagicMock()
    ad = MagicMock()
    ad.human_delay = AsyncMock()
    ad.throttle = AsyncMock()
    return Collector(browser=browser, antidetect=ad, selectors=SelectorRepo)


def test_build_search_filter_params_whitelist(caplog_info) -> None:
    c = _make_collector()
    assert c._build_search_filter_params(None) == []
    assert c._build_search_filter_params([]) == []
    # 未知标签被静默忽略，避免向 URL 注入侵扰性参数
    assert c._build_search_filter_params(["unknown_tag"]) == []
    assert c._build_search_filter_params(
        ["personal_idle", "not_a_tag", "free_shipping"]
    ) == ["sourceType=0", "postageType=1"]
    assert any("搜索筛选参数" in r.message for r in caplog_info.records)
    caplog_info.clear()
    c._build_search_filter_params(["not_a_tag"])
    assert not caplog_info.records


async def test_apply_search_freq_delay_fast_and_normal(monkeypatch) -> None:
    """fast=False 走真实延迟；fast=True 仅记录统计且吞掉统计异常"""
    from xianyu_hunter.modules import login_orchestrator as lo

    orch = MagicMock()
    orch.apply_freq_delay = AsyncMock()
    orch.record_freq_request = MagicMock()
    monkeypatch.setattr(lo, "get_orchestrator", lambda: orch)

    c = _make_collector()
    await c._apply_search_freq_delay(fast=False)
    orch.apply_freq_delay.assert_awaited_once()
    orch.record_freq_request.assert_not_called()

    await c._apply_search_freq_delay(fast=True)
    orch.apply_freq_delay.assert_awaited_once()  # fast 模式不再引入延迟
    orch.record_freq_request.assert_called_once()

    # 统计失败不影响搜索主流程
    orch.record_freq_request.side_effect = RuntimeError("stats offline")
    await c._apply_search_freq_delay(fast=True)


# ============ DOM 解析构造 ItemSummary ============


@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, None),
        ("", None),
        ("2026-10-01T08:30:00Z", datetime(2026, 10, 1, 8, 30, tzinfo=timezone.utc)),
        ("2026-10-01T08:30:00", datetime(2026, 10, 1, 8, 30)),
        ("不是时间", None),
    ],
)
def test_parse_dom_publish_time(raw, expected) -> None:
    assert Collector._parse_dom_publish_time(raw) == expected


def test_build_item_from_dom_data_valid_and_filters() -> None:
    c = _make_collector()
    assert c._build_item_from_dom_data({"title": "无 ID"}, "显卡") is None

    filtered: list[str] = []
    dom = {
        "id": "1001",
        "title": "金士顿 DDR4 8G 内存条",
        "price": "199.5",
        "thumb": "//img.alicdn.com/x.jpg",
        "region": "浙江杭州",
        "seller_nick": "数码小铺",
        "seller_id": "5678",
        "seller_credit": "优秀",
        "want_cnt": "12",
        "is_sold": True,
        "publish_time": "2026-10-01T08:30:00Z",
    }
    item = c._build_item_from_dom_data(dom, "内存", filtered)
    assert item is not None
    assert item.id == "1001"
    assert item.price == 199.5
    assert item.thumb_url == "https://img.alicdn.com/x.jpg"
    assert item.seller_nick == "数码小铺"
    assert item.region == "浙江杭州"
    assert item.brand == "金士顿"
    assert item.want_cnt == 12
    assert item.is_sold is True
    assert item.publish_time == datetime(2026, 10, 1, 8, 30, tzinfo=timezone.utc)
    assert filtered == []

    # 关键词不匹配：记录到 filtered_out 并返回 None
    assert c._build_item_from_dom_data({"id": "1", "title": "运动鞋"}, "显卡", filtered) is None
    assert filtered == ["运动鞋"]
    # 不传 filtered_out 时静默跳过（翻页路径）
    assert c._build_item_from_dom_data({"id": "2", "title": "运动鞋"}, "显卡") is None
    # 标题为空时不做关键词过滤
    empty_title = c._build_item_from_dom_data({"id": "3", "title": ""}, "显卡")
    assert empty_title is not None and empty_title.price == 0.0


def test_build_items_from_dom_batch_dedup_and_filter() -> None:
    c = _make_collector()
    items = [ItemSummary(id="1001", title="金士顿 内存", price=1.0)]
    batch = [
        {"id": "1001", "title": "内存"},
        {"title": "缺少 id"},
        {"id": "1002", "title": "显卡"},
        {"id": "1003", "title": "内存条 全新"},
    ]
    filtered = c._build_items_from_dom_batch(batch, items, "内存")
    assert filtered == ["显卡"]
    assert [i.id for i in items] == ["1001", "1003"]


async def test_parse_dom_cards_one_by_one(monkeypatch) -> None:
    c = _make_collector()

    async def _fake_parse(card):
        if card.get("skip"):
            return None
        return ItemSummary(id=card["id"], title=card["title"], price=1.0)

    monkeypatch.setattr(c, "_parse_card", _fake_parse)
    items = [ItemSummary(id="dup", title="内存", price=1.0)]
    cards = [
        {"skip": True},
        {"id": "", "title": "内存"},
        {"id": "dup", "title": "内存"},
        {"id": "x1", "title": "运动鞋"},
        {"id": "x2", "title": "内存条"},
    ]
    filtered = await c._parse_dom_cards_one_by_one(cards, items, "内存")
    assert filtered == ["运动鞋"]
    assert [i.id for i in items] == ["dup", "x2"]


# ============ DOM 回退：卡片检测 / 批量解析 / 翻页 ============


_SEARCH_URL = "https://www.goofish.com/search?q=%E5%86%85%E5%AD%98"


def _dom_page(url: str = _SEARCH_URL) -> AsyncMock:
    page = AsyncMock()
    page.url = url
    page.wait_for_load_state = AsyncMock()
    return page


async def test_collect_dom_cards_guard_branches(caplog_info, monkeypatch) -> None:
    c = _make_collector()
    monkeypatch.setattr(sm.asyncio, "sleep", AsyncMock())

    # 会话已知失效：直接跳过
    c.last_session_invalid = True
    assert await c._collect_dom_cards(_dom_page(), "内存") == []
    c.last_session_invalid = False

    # 页面被重定向到非搜索页
    page = _dom_page("https://www.goofish.com/")
    assert await c._collect_dom_cards(page, "内存") == []
    assert any("页面已跳转至非搜索页" in r.message for r in caplog_info.records)

    # 首屏无卡片，等待渲染后重试仍无卡片
    page = _dom_page()
    page.evaluate = AsyncMock(return_value=0)
    assert await c._collect_dom_cards(page, "内存") == []
    assert page.wait_for_load_state.await_count == 1

    # 有卡片：委托 _find_cards
    page = _dom_page()
    page.evaluate = AsyncMock(return_value=6)
    monkeypatch.setattr(c, "_find_cards", AsyncMock(return_value=["card"]))
    assert await c._collect_dom_cards(page, "内存") == ["card"]

    # 超时 → 放弃
    page = _dom_page()
    page.evaluate = AsyncMock(side_effect=sm.asyncio.TimeoutError())
    assert await c._collect_dom_cards(page, "内存") == []

    # 页面异常 → 放弃
    page = _dom_page()
    page.evaluate = AsyncMock(side_effect=RuntimeError("detached"))
    assert await c._collect_dom_cards(page, "内存") == []


async def test_evaluate_dom_batch_failure_paths(monkeypatch) -> None:
    c = _make_collector()
    page = _dom_page()
    page.evaluate = AsyncMock(return_value=[{"id": "1"}])
    assert await c._evaluate_dom_batch(page) == [{"id": "1"}]

    page.evaluate = AsyncMock(side_effect=sm.asyncio.TimeoutError())
    assert await c._evaluate_dom_batch(page) == []
    page.evaluate = AsyncMock(side_effect=RuntimeError("eval boom"))
    assert await c._evaluate_dom_batch(page) == []


async def test_paginate_dom_results(monkeypatch) -> None:
    c = _make_collector()

    page = _dom_page()
    pages = [
        [{"id": "2", "title": "内存条 A"}],
        [{"id": "2", "title": "重复"}, {"id": "3", "title": "内存条 B"}],
        [{"id": "2"}],
    ]

    async def _eval(script):
        if "scrollTo" in script:
            return None
        return pages.pop(0) if pages else []

    page.evaluate = AsyncMock(side_effect=_eval)
    items = [ItemSummary(id="1", title="内存", price=1.0)]
    await c._paginate_dom_results(page, items, "内存", max_pages=4)
    assert [i.id for i in items] == ["1", "2", "3"]

    # 批量解析异常时中断翻页（滚动 evaluate 在 try 之外，仅解析异常被吞掉）
    page2 = _dom_page()

    async def _eval_boom(script):
        if "scrollTo" in script:
            return None
        raise RuntimeError("boom")

    page2.evaluate = AsyncMock(side_effect=_eval_boom)
    items2 = [ItemSummary(id="1", title="内存", price=1.0)]
    await c._paginate_dom_results(page2, items2, "内存", max_pages=3)
    assert [i.id for i in items2] == ["1"]
    assert page2.evaluate.await_count == 2  # 第 1 屏滚动 + 解析失败后即 break


async def test_apply_dom_fallback_pagination_resets_flag_and_counts(monkeypatch) -> None:
    c = _make_collector()
    c.last_session_invalid = True
    paginate = AsyncMock()
    monkeypatch.setattr(c, "_paginate_dom_results", paginate)
    items = [ItemSummary(id="1", title="内存", price=1.0)]
    chain: list[str] = []
    await c._apply_dom_fallback_pagination(_dom_page(), items, "内存", 1, True, chain)
    assert c.last_session_invalid is False
    assert chain == ["重置会话标志"]
    paginate.assert_not_awaited()

    c.last_session_invalid = False

    async def _add_more(page, _items, _keyword, _max_pages):
        _items.append(ItemSummary(id="2", title="内存条", price=2.0))

    monkeypatch.setattr(c, "_paginate_dom_results", _add_more)
    chain = []
    await c._apply_dom_fallback_pagination(_dom_page(), items, "内存", 3, False, chain)
    assert chain == ["翻页+1"]


async def test_fallback_to_dom_search_chains(caplog_info, monkeypatch) -> None:
    c = _make_collector()
    page = _dom_page()

    # 无卡片：早退并输出降级链
    monkeypatch.setattr(c, "_collect_dom_cards", AsyncMock(return_value=[]))
    assert await c._fallback_to_dom_search(page, "内存", 1, False) == []
    assert any("搜索降级链 [API不可用 → 无卡片]" in r.message for r in caplog_info.records)

    # 批量解析命中
    caplog_info.clear()
    monkeypatch.setattr(c, "_collect_dom_cards", AsyncMock(return_value=["c1", "c2"]))
    monkeypatch.setattr(
        c, "_evaluate_dom_batch",
        AsyncMock(return_value=[{"id": "9", "title": "内存条", "price": "30"}]),
    )
    monkeypatch.setattr(c, "_apply_dom_fallback_pagination", AsyncMock())
    items = await c._fallback_to_dom_search(page, "内存", 2, True)
    assert [i.id for i in items] == ["9"]
    assert any(
        "搜索降级链 [API会话失效 → 卡片2 → 批量解析 → 有效1]" in r.message
        for r in caplog_info.records
    )

    # 批量解析失败 → 逐个解析 + 过滤计数
    caplog_info.clear()
    monkeypatch.setattr(c, "_evaluate_dom_batch", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        c, "_parse_dom_cards_one_by_one", AsyncMock(return_value=["被过滤的标题"])
    )
    await c._fallback_to_dom_search(page, "内存", 1, False)
    assert any("逐个解析" in r.message and "过滤1" in r.message for r in caplog_info.records)

    # 有卡片但解析后无结果
    caplog_info.clear()
    monkeypatch.setattr(c, "_parse_dom_cards_one_by_one", AsyncMock(return_value=[]))
    assert await c._fallback_to_dom_search(page, "内存", 1, False) == []
    assert any("无结果" in r.message for r in caplog_info.records)


# ============ 会话失效 / 错误响应判定 ============


def test_is_session_invalid_response_branches(caplog_info) -> None:
    c = _make_collector()
    assert c._is_session_invalid_response({}, "内存", {}) is False
    assert c._is_session_invalid_response({"ret": "RGV587_ERROR"}, "内存", {}) is False
    assert c._is_session_invalid_response({"ret": []}, "内存", {}) is False
    assert c._is_session_invalid_response({"ret": ["SUCCESS::调用成功"]}, "内存", {}) is False

    state: dict = {}
    assert c._is_session_invalid_response({"ret": ["FAIL_SYS_USER_VALIDATE::RGV587_ERROR"]}, "内存", state) is True
    assert state == {"session_invalid": True}
    assert any("会话失效" in r.message and r.levelname == "WARNING" for r in caplog_info.records)

    caplog_info.clear()
    state = {}
    assert c._is_session_invalid_response({"ret": ["FAIL_SYS_TOKEN_ILLEGAL::非法令牌"]}, "内存", state) is True
    assert state == {"api_auth_failed": True}
    # token 类失败用 INFO，避免与 RGV587 的 WARNING 混淆
    assert any("token/签名校验失败" in r.message and r.levelname == "INFO" for r in caplog_info.records)


@pytest.mark.parametrize(
    "body,expected",
    [
        ({}, False),
        ({"ret": "ERROR"}, False),
        ({"ret": []}, False),
        ({"ret": ["SUCCESS::调用成功"]}, False),
        ({"ret": ["FAIL_SYS_TRAFFIC_LIMIT::限流"]}, True),
        ({"ret": ["ERROR::未知"]}, True),
    ],
)
def test_is_error_response(caplog_info, body, expected) -> None:
    c = _make_collector()
    caplog_info.clear()
    assert c._is_error_response(body) is expected
    if expected:
        assert any("可能限流/未登录" in r.message and r.levelname == "WARNING" for r in caplog_info.records)
    else:
        assert not caplog_info.records


def test_goto_timeout_indicates_session_invalid_variants() -> None:
    c = _make_collector()

    class _Raising:
        @property
        def url(self):  # noqa: ANN201
            raise RuntimeError("page closed")

    assert c._goto_timeout_indicates_session_invalid(SimpleNamespace(url="https://passport.goofish.com/login?x=1")) is True
    assert c._goto_timeout_indicates_session_invalid(SimpleNamespace(url=_SEARCH_URL)) is False
    assert c._goto_timeout_indicates_session_invalid(SimpleNamespace(url="about:blank")) is False
    assert c._goto_timeout_indicates_session_invalid(SimpleNamespace(url="")) is False
    assert c._goto_timeout_indicates_session_invalid(_Raising()) is False


async def test_poll_for_captured_responses(monkeypatch) -> None:
    c = _make_collector()
    sleeps = AsyncMock()
    monkeypatch.setattr(sm.asyncio, "sleep", sleeps)

    state = {"session_invalid": False, "api_auth_failed": False}
    await c._poll_for_captured_responses([{"ret": []}], state, 15)
    sleeps.assert_not_awaited()

    # 无响应且无失效标志：轮询用满 rounds 轮才退出
    await c._poll_for_captured_responses([], state, 15)
    assert sleeps.await_count == 15

    state["session_invalid"] = True
    sleeps.reset_mock()
    await c._poll_for_captured_responses([], state, 15)
    sleeps.assert_not_awaited()

    sleeps.reset_mock()
    state = {"session_invalid": False, "api_auth_failed": True}
    await c._poll_for_captured_responses([], state, 3)
    sleeps.assert_not_awaited()

    sleeps.reset_mock()
    state = {"session_invalid": False, "api_auth_failed": False}
    await c._poll_for_captured_responses([], state, 3)
    assert sleeps.await_count == 3


# ============ route 拦截 handler ============


async def test_maybe_consume_route_response_branches(caplog_info) -> None:
    c = _make_collector()
    route = AsyncMock()
    captured: list[dict] = []
    state = {"session_invalid": False, "api_auth_failed": False}

    # 非 JSON：记录 preview 后回放，不追加 captured
    html_resp = AsyncMock()
    html_resp.json = AsyncMock(side_effect=RuntimeError("not json"))
    html_resp.text = AsyncMock(return_value="<html>login</html>")
    assert await c._maybe_consume_route_response(route, html_resp, "内存", captured, state) is False
    route.fulfill.assert_awaited_once_with(response=html_resp)
    assert captured == []

    # 会话失效
    session_resp = AsyncMock()
    session_resp.json = AsyncMock(return_value={"ret": ["RGV587_ERROR::需要滑块验证"]})
    assert await c._maybe_consume_route_response(route, session_resp, "内存", captured, state) is False
    assert state["session_invalid"] is True

    # 错误响应
    err_resp = AsyncMock()
    err_resp.json = AsyncMock(return_value={"ret": ["FAIL_SYS_TRAFFIC_LIMIT::限流"]})
    assert await c._maybe_consume_route_response(route, err_resp, "内存", captured, state) is False

    # 正常响应
    good_resp = AsyncMock()
    body = {"ret": ["SUCCESS::调用成功"], "data": {"resultList": [{"itemId": "1"}]}}
    good_resp.json = AsyncMock(return_value=body)
    assert await c._maybe_consume_route_response(route, good_resp, "内存", captured, state) is True
    assert captured == [body]
    assert any("route 拦截捕获搜索 API 响应" in r.message for r in caplog_info.records)
    assert any("API 响应前500字符" in r.message for r in caplog_info.records)


async def test_make_search_route_handler_flow(monkeypatch) -> None:
    c = _make_collector()
    page = AsyncMock()
    captured: list[dict] = []
    state = {"session_invalid": False, "api_auth_failed": False}

    sync_cookies = AsyncMock(return_value=1)
    monkeypatch.setattr(sm, "_sync_response_cookies_to_context", sync_cookies)
    consume = AsyncMock(return_value=True)
    monkeypatch.setattr(c, "_maybe_consume_route_response", consume)

    route = AsyncMock()
    response = MagicMock()
    route.fetch = AsyncMock(return_value=response)

    handler = c._make_search_route_handler(page, "内存", captured, state)
    await handler(route)
    sync_cookies.assert_awaited_once_with(page, response)
    consume.assert_awaited_once_with(route, response, "内存", captured, state)

    # 响应已被消费（会话失效）时不再往下走
    consume.return_value = False
    await handler(route)

    # route.fetch 抛异常 → 交给异常分类处理
    handle_exc = AsyncMock()
    monkeypatch.setattr(c, "_handle_route_exception", handle_exc)
    boom_route = AsyncMock()
    boom_route.fetch = AsyncMock(side_effect=RuntimeError("Target closed"))
    await handler(boom_route)
    handle_exc.assert_awaited_once()


async def test_handle_route_exception_branches(caplog_info) -> None:
    c = _make_collector()
    route = AsyncMock()
    await c._handle_route_exception(route, RuntimeError("Route is already handled!"))
    route.continue_.assert_not_awaited()

    caplog_info.clear()
    await c._handle_route_exception(route, RuntimeError("net::ERR_FAILED"))
    route.continue_.assert_awaited_once()
    assert any("route 拦截处理失败" in r.message for r in caplog_info.records)

    # continue_ 自身失败也吞掉
    route.continue_ = AsyncMock(side_effect=RuntimeError("closed"))
    await c._handle_route_exception(route, RuntimeError("net::ERR_FAILED"))


# ============ unroute 与状态回写 ============


async def test_unroute_search_api_guard_branches(caplog_info) -> None:
    c = _make_collector()
    unroute = AsyncMock()
    await c._unroute_search_api(None, "**/mtop/**", unroute)
    unroute.assert_not_awaited()

    closed_page = AsyncMock()
    closed_page.is_closed = MagicMock(return_value=True)
    await c._unroute_search_api(closed_page, "**/mtop/**", unroute)
    closed_page.unroute.assert_not_awaited()

    closed_ctx_page = AsyncMock()
    closed_ctx_page.is_closed = MagicMock(return_value=False)
    ctx = MagicMock()
    ctx.is_closed = MagicMock(return_value=True)
    closed_ctx_page.context = ctx
    await c._unroute_search_api(closed_ctx_page, "**/mtop/**", unroute)
    closed_ctx_page.unroute.assert_not_awaited()

    disconnected_page = AsyncMock()
    disconnected_page.is_closed = MagicMock(return_value=False)
    browser = MagicMock()
    browser.is_connected = MagicMock(return_value=False)
    ctx2 = MagicMock()
    ctx2.is_closed = MagicMock(return_value=False)
    ctx2.browser = browser
    disconnected_page.context = ctx2
    await c._unroute_search_api(disconnected_page, "**/mtop/**", unroute)
    disconnected_page.unroute.assert_not_awaited()

    # 探测本身异常也继续走下方兜底
    weird = AsyncMock()
    weird.is_closed = MagicMock(side_effect=RuntimeError("dead"))
    weird.context = None
    await c._unroute_search_api(weird, "**/mtop/**", unroute)
    weird.unroute.assert_awaited_once()


async def test_unroute_search_api_success(monkeypatch, caplog_info) -> None:
    c = _make_collector()
    page = AsyncMock()
    page.is_closed = MagicMock(return_value=False)
    page.context = None
    await c._unroute_search_api(page, "**/mtop/**", AsyncMock())
    page.unroute.assert_awaited_once()
    assert any("page.unroute 完成" in r.message for r in caplog_info.records)


async def test_unroute_search_api_timeout_and_error(monkeypatch, caplog_info) -> None:
    c = _make_collector()
    page = AsyncMock()
    page.is_closed = MagicMock(return_value=False)
    page.context = None

    async def _boom_wait_for(awaitable, timeout):
        raise sm.asyncio.TimeoutError()

    monkeypatch.setattr(sm.asyncio, "wait_for", _boom_wait_for)
    await c._unroute_search_api(page, "**/mtop/**", AsyncMock())
    assert any("page.unroute 超时" in r.message for r in caplog_info.records)
    # 让 shield 包裹的后台任务收尾，避免 pending 告警
    await sm.asyncio.sleep(0)

    caplog_info.clear()

    async def _err_wait_for(awaitable, timeout):
        raise RuntimeError("TargetClosedError")

    monkeypatch.setattr(sm.asyncio, "wait_for", _err_wait_for)
    await c._unroute_search_api(page, "**/mtop/**", AsyncMock())
    assert any("page.unroute 异常(忽略)" in r.message for r in caplog_info.records)
    await sm.asyncio.sleep(0)


# ============ API 响应 → ItemSummary ============


_API_RAW = {
    "itemId": "555",
    "title": "金士顿 DDR4 8G 内存条",
    "price": "128",
    "picUrl": "//img.alicdn.com/p.jpg",
    "sellerId": "9001",
    "userNick": "数码小铺",
    "region": "浙江杭州",
    "publishTime": "1759283400000",
    "wantCnt": "45",
    "viewCnt": "1472",
    "sellerCredit": "优秀",
    "creditScore": 800,
    "onSaleCount": "12",
    "soldCount": "342",
}


def test_build_item_from_api_raw_success_and_nick_cache() -> None:
    c = _make_collector()
    fields = sm._extract_api_item_fields(_API_RAW)
    item = c._build_item_from_api_raw(_API_RAW, fields)
    assert item is not None
    assert item.id == "555"
    assert item.price == 128.0
    assert item.thumb_url == "https://img.alicdn.com/p.jpg"
    assert item.seller_id == "9001"
    assert item.seller_nick == "数码小铺"
    assert item.region == "浙江杭州"
    assert item.brand == "金士顿"
    assert item.want_cnt == 45 and item.view_cnt == 1472
    assert item.seller_credit_score == 800
    assert item.seller_on_sale_count == 12 and item.seller_sold_count == 342
    assert item.publish_time is not None
    assert item.is_sold is False
    # nick + seller_id 命中时写入缓存，供后续卖家行展示复用
    assert c._seller_nicks["9001"] == "数码小铺"


def test_build_item_from_api_raw_missing_fields(caplog_info) -> None:
    c = _make_collector()
    raw = {"data": {"item": {"foo": "bar"}}}
    assert c._build_item_from_api_raw(raw, sm._extract_api_item_fields(raw)) is None
    assert any("跳过搜索 API 条目" in r.message for r in caplog_info.records)


def test_build_preview_cache(caplog_info, monkeypatch) -> None:
    c = _make_collector()
    caplog_info.clear()
    cache = c._build_preview_cache([_API_RAW])
    assert set(cache) == {0}
    assert cache[0]["item_id"] == "555"
    assert any("前3个商品摘要" in r.message and "555" in r.message for r in caplog_info.records)

    caplog_info.clear()
    # 摘要缓存按 idx 落位，即使字段缺失也保留（供主循环复用），仅日志降级
    placeholder_cache = c._build_preview_cache([{"foo": "bar"}])
    assert list(placeholder_cache) == [0]
    assert placeholder_cache[0]["item_id"] == ""
    assert any("均缺少 item_id/title" in r.message and r.levelname == "WARNING" for r in caplog_info.records)

    caplog_info.clear()

    def _boom(_source):
        raise RuntimeError("preview boom")

    monkeypatch.setattr(sm, "_extract_api_item_fields", _boom)
    assert c._build_preview_cache([_API_RAW]) == {}
    assert any("商品摘要预览失败" in r.message for r in caplog_info.records)


def test_append_items_from_raw_dedup_and_error(monkeypatch, caplog_info) -> None:
    c = _make_collector()
    items = [ItemSummary(id="555", title="金士顿 内存", price=1.0)]
    raw_items = [_API_RAW, {"title": "无 id"}, {"itemId": "777", "title": "海盗船 内存"}]
    c._append_items_from_raw(raw_items, c._build_preview_cache(raw_items), items)
    assert [i.id for i in items] == ["555", "777"]

    caplog_info.clear()

    def _boom(raw, fields):
        raise RuntimeError("bad row")

    monkeypatch.setattr(c, "_build_item_from_api_raw", _boom)
    c._append_items_from_raw([_API_RAW], {}, items)
    assert [i.id for i in items] == ["555", "777"]
    assert any("解析搜索 API 条目失败" in r.message for r in caplog_info.records)


async def test_parse_captured_responses_and_scroll(monkeypatch) -> None:
    c = _make_collector()
    page = AsyncMock()
    monkeypatch.setattr(sm.asyncio, "sleep", AsyncMock())

    items: list[ItemSummary] = []
    captured = [{"page": 1}, {"page": 2}]
    monkeypatch.setattr(
        c, "_parse_search_api_result",
        MagicMock(side_effect=lambda r: [_API_RAW] if r["page"] == 1 else [{"itemId": "777", "title": "内存"}]),
    )
    await c._parse_captured_responses(page, captured, items, max_pages=3)
    assert [i.id for i in items] == ["555", "777"]
    # 未满 20 条不触发滚动翻页
    page.evaluate.assert_not_awaited()

    # 空结果页：消耗页码但不产出商品
    items2: list[ItemSummary] = []
    monkeypatch.setattr(c, "_parse_search_api_result", MagicMock(return_value=[]))
    await c._parse_captured_responses(page, [{"page": 1}], items2, max_pages=2)
    assert items2 == []

    # 满 20 条且未到上限 → 滚动触发下一页
    big = [{"itemId": f"i{n}", "title": "内存"} for n in range(20)]
    captured3: list[dict] = []
    monkeypatch.setattr(c, "_parse_search_api_result", MagicMock(return_value=big))
    page3 = AsyncMock()
    await c._parse_captured_responses(page3, [{"page": 1}], [], max_pages=2)
    page3.evaluate.assert_awaited_once()
    assert captured3 == []


async def test_maybe_scroll_for_next_page_gates(monkeypatch) -> None:
    c = _make_collector()
    sleeps = AsyncMock()
    monkeypatch.setattr(sm.asyncio, "sleep", sleeps)
    page = AsyncMock()

    await c._maybe_scroll_for_next_page(page, [], [{"itemId": "1"}], 0, 3)
    page.evaluate.assert_not_awaited()

    full = [{"itemId": str(n)} for n in range(20)]
    await c._maybe_scroll_for_next_page(page, [], full, 2, 3)  # 已到最后一页
    page.evaluate.assert_not_awaited()

    captured = [{"page": 2}]
    await c._maybe_scroll_for_next_page(page, captured, full, 0, 3)
    page.evaluate.assert_awaited_once()
    c.ad.human_delay.assert_awaited_once()
    sleeps.assert_not_awaited()  # 已有新响应，无需等待

    sleeps.reset_mock()
    await c._maybe_scroll_for_next_page(page, [], full, 0, 3)
    assert sleeps.await_count == 10  # 等待窗口耗尽


# ============ _call_search_api 编排 ============


async def test_call_search_api_registers_and_clears_route(monkeypatch) -> None:
    c = _make_collector()
    page = AsyncMock()
    handler = AsyncMock()
    monkeypatch.setattr(c, "_make_search_route_handler", lambda *a, **k: handler)
    monkeypatch.setattr(
        c, "_navigate_and_wait_for_api",
        AsyncMock(return_value=True),
    )

    async def _fill(page_arg, captured, items, max_pages):
        captured.append({"ret": ["SUCCESS::ok"]})
        items.append(ItemSummary(id="555", title="内存", price=1.0))

    monkeypatch.setattr(c, "_parse_captured_responses", _fill)
    unroute = AsyncMock()
    monkeypatch.setattr(c, "_unroute_search_api", unroute)

    items, session_invalid = await c._call_search_api(page, "内存", max_pages=2, fast=True)
    assert session_invalid is True
    assert [i.id for i in items] == ["555"]
    page.route.assert_awaited_once_with(c._SEARCH_API_ROUTE_PATTERN, handler)
    unroute.assert_awaited_once_with(page, c._SEARCH_API_ROUTE_PATTERN, handler)
    assert c._last_api_captured is True
    assert c._api_auth_backoff_until == 0.0

    # 导航异常时 finally 仍解除路由
    c._last_api_captured = False
    monkeypatch.setattr(
        c, "_navigate_and_wait_for_api", AsyncMock(side_effect=RuntimeError("goto failed"))
    )
    with pytest.raises(RuntimeError, match="goto failed"):
        await c._call_search_api(page, "内存")
    unroute.assert_awaited()


# ============ live_search 展示行构造 ============


def test_build_live_search_rows_and_seller_dedup() -> None:
    c = _make_collector()
    item = ItemSummary(
        id="555", title="金士顿 内存条", price=128.0, region="浙江杭州",
        brand="金士顿", seller_id="9001", seller_nick="", want_cnt=45, view_cnt=1472,
        thumb_url="https://img/x.jpg", publish_time=datetime(2026, 10, 1, 8, 30),
        seller_credit="优秀",
    )
    c._seller_nicks["9001"] = "数码小铺"
    results: list[dict] = []
    sellers: dict[str, dict] = {}
    c._build_live_search_results_from_items([item, item], results, sellers)

    # 商品行进入 results，卖家行按 seller_id 去重进入 sellers
    assert [r["link_type"] for r in results] == ["item", "item"]
    assert list(sellers) == ["9001"]
    item_row = results[0]
    seller_row = sellers["9001"]
    assert item_row["item_id"] == "555" and item_row["link_key"] == "555"
    assert item_row["seller_nick"] == "数码小铺"
    assert item_row["publish_time"] == "2026-10-01T08:30:00"
    assert item_row["url"].endswith("555")
    # seller 行与 item 行字段对称：price 置空、thumb 清空、计数归零
    assert seller_row["title"] == "数码小铺"
    assert seller_row["price"] is None and seller_row["thumb_url"] == ""
    assert seller_row["want_cnt"] == 0 and seller_row["view_cnt"] == 0
    assert seller_row["link_key"] == "9001"
    assert list(sellers) == ["9001"]  # 同一卖家只收集一次


def test_build_live_search_rows_without_optional_fields() -> None:
    c = _make_collector()
    bare = ItemSummary(id="1", title="内存", price=0.0)
    results: list[dict] = []
    sellers: dict[str, dict] = {}
    c._build_live_search_results_from_items([bare], results, sellers)
    assert results[0]["publish_time"] is None
    assert results[0]["seller_nick"] == ""
    # 无 seller_id 时不产生卖家行
    assert len(results) == 1 and sellers == {}

    # 昵称缺失时卖家行标题回落为「卖家 {id}」
    row = c._build_seller_row_from_item(
        ItemSummary(id="2", title="内存", price=0.0, seller_id="88", region="北京"), ""
    )
    assert row["title"] == "卖家 88"
    assert row["seller_credit"] == ""


def test_backfill_descriptions_to_results() -> None:
    c = _make_collector()
    results = [
        {"link_type": "item", "link_key": "555", "item_id": "555"},
        {"link_type": "seller", "link_key": "9001"},
        {"link_type": "item", "link_key": "", "item_id": "777"},
    ]
    c._backfill_descriptions_to_results(results, {})
    assert all("item_desc" not in r for r in results)

    c._backfill_descriptions_to_results(
        results, {"555": "全新未拆封", "777": "", "9001": "卖家描述"}
    )
    assert results[0]["item_desc"] == "全新未拆封"
    assert "item_desc" not in results[1]  # seller 行不参与 exclude_words 过滤
    assert "item_desc" not in results[2]  # 空描述不回填


# ============ token 刷新 ============


async def test_ensure_fresh_m5tk_cache_and_refresh(monkeypatch, caplog_info) -> None:
    c = _make_collector()
    monkeypatch.setattr(sm.asyncio, "sleep", AsyncMock())
    page = AsyncMock()

    # 首次调用（时间戳为 0）→ 执行刷新
    assert await c._ensure_fresh_m5tk(page) is True
    page.goto.assert_awaited_once()
    assert c._last_m5tk_refresh > 0
    assert any("_m_h5_tk token 已刷新" in r.message for r in caplog_info.records)

    # 刚刷新过：非 force 走 45 分钟缓存直接跳过
    caplog_info.clear()
    page.goto.reset_mock()
    assert await c._ensure_fresh_m5tk(page) is False
    page.goto.assert_not_awaited()

    # force 但不足 5 分钟最小间隔 → 跳过
    assert await c._ensure_fresh_m5tk(page, force=True) is False
    assert any("force 刷新被跳过" in r.message for r in caplog_info.records)

    # 超过 5 分钟后 force 生效
    c._last_m5tk_refresh = time.monotonic() - 400
    assert await c._ensure_fresh_m5tk(page, force=True) is True

    # 导航失败 → 返回 False 并告警
    c._last_m5tk_refresh = 0.0
    page.goto = AsyncMock(side_effect=RuntimeError("net::ERR_TIMED_OUT"))
    assert await c._ensure_fresh_m5tk(page) is False
    assert any("刷新 _m_h5_tk token 失败" in r.message for r in caplog_info.records)


# ============ 页面与锁的准备 / 清理 ============


async def test_prepare_and_cleanup_search_resources_lock_lifecycle() -> None:
    page_obj = AsyncMock()
    browser = MagicMock()
    browser.new_page = AsyncMock(return_value=page_obj)
    lock = asyncio.Lock()
    c = Collector(browser=browser, antidetect=MagicMock(), selectors=SelectorRepo, browser_lock=lock)

    # 注入 page：不创建页面、不取锁
    injected = AsyncMock()
    got_page, own, release = await c._prepare_search_page_and_lock(injected, skip_lock=False)
    assert (got_page, own, release) == (injected, False, False)
    browser.new_page.assert_not_awaited()

    # 自建 page + 有锁：获取锁并在清理时释放
    got_page, own, release = await c._prepare_search_page_and_lock(None, skip_lock=False)
    assert got_page is page_obj and own is True and release is True
    assert lock.locked()
    browser.register_external_page.assert_called_once_with(page_obj)
    await c._cleanup_search_resources(got_page, own, release)
    page_obj.close.assert_awaited_once()
    browser.unregister_external_page.assert_called_once_with(page_obj)
    assert not lock.locked()

    # skip_lock=True：不取锁
    browser.reset_mock()
    page_obj.reset_mock()
    _, own, release = await c._prepare_search_page_and_lock(None, skip_lock=True)
    assert own is True and release is False
    await c._cleanup_search_resources(page_obj, own, release)
    assert not lock.locked()


async def test_cleanup_swallows_close_error_and_keeps_injected_page() -> None:
    browser = MagicMock()
    c = Collector(browser=browser, antidetect=MagicMock(), selectors=SelectorRepo)
    page = AsyncMock()
    page.close = AsyncMock(side_effect=RuntimeError("already closed"))
    await c._cleanup_search_resources(page, own_page=True, release_lock=False)
    page.close.assert_awaited_once()

    injected = AsyncMock()
    await c._cleanup_search_resources(injected, own_page=False, release_lock=False)
    injected.close.assert_not_awaited()


# ============ search 主流程编排 ============


async def test_search_uses_api_result_when_present(monkeypatch) -> None:
    page = AsyncMock()
    c = _make_collector()
    monkeypatch.setattr(c, "_prepare_search_page_and_lock", AsyncMock(return_value=(page, True, False)))
    cleanup = AsyncMock()
    monkeypatch.setattr(c, "_cleanup_search_resources", cleanup)
    monkeypatch.setattr(c, "_apply_search_freq_delay", AsyncMock())
    monkeypatch.setattr(c, "_ensure_fresh_m5tk", AsyncMock(return_value=False))
    api_items = [ItemSummary(id="555", title="内存", price=1.0)]
    monkeypatch.setattr(c, "_call_search_api", AsyncMock(return_value=(api_items, False)))
    fallback = AsyncMock(return_value=[])
    monkeypatch.setattr(c, "_fallback_to_dom_search", fallback)

    items = await c.search("内存", max_pages=2, search_filters=["personal_idle"])
    assert items == api_items
    assert c.last_session_invalid is False
    assert c._last_search_error == ""
    fallback.assert_not_awaited()
    cleanup.assert_awaited_once_with(page, True, False)


async def test_search_falls_back_to_dom_and_honours_backoff(monkeypatch) -> None:
    page = AsyncMock()
    c = _make_collector()
    monkeypatch.setattr(c, "_prepare_search_page_and_lock", AsyncMock(return_value=(page, False, False)))
    monkeypatch.setattr(c, "_cleanup_search_resources", AsyncMock())
    monkeypatch.setattr(c, "_apply_search_freq_delay", AsyncMock())
    monkeypatch.setattr(c, "_ensure_fresh_m5tk", AsyncMock(return_value=False))
    dom_items = [ItemSummary(id="777", title="内存", price=2.0)]
    monkeypatch.setattr(c, "_call_search_api", AsyncMock(return_value=([], True)))
    monkeypatch.setattr(c, "_fallback_to_dom_search", AsyncMock(return_value=dom_items))

    assert await c.search("内存") == dom_items
    assert c.last_session_invalid is True

    # 冷却期内不再调用 API，直接导航后走 DOM
    cap = c._call_search_api
    cap.reset_mock()
    c._api_auth_backoff_until = time.monotonic() + 120
    assert await c.search("内存", fast=True) == dom_items
    cap.assert_not_awaited()
    page.goto.assert_awaited_once()
    assert page.goto.await_args.kwargs["timeout"] == 15000


async def test_search_exception_classification(monkeypatch, caplog_info) -> None:
    page = AsyncMock()
    c = _make_collector()
    monkeypatch.setattr(c, "_prepare_search_page_and_lock", AsyncMock(return_value=(page, False, False)))
    cleanup = AsyncMock()
    monkeypatch.setattr(c, "_cleanup_search_resources", cleanup)
    monkeypatch.setattr(c, "_apply_search_freq_delay", AsyncMock())
    monkeypatch.setattr(c, "_ensure_fresh_m5tk", AsyncMock(return_value=False))

    # 网络瞬时故障：降级为 WARNING，不打堆栈
    monkeypatch.setattr(
        c, "_call_search_api",
        AsyncMock(side_effect=RuntimeError("net::ERR_NAME_NOT_RESOLVED")),
    )
    assert await c.search("内存") == []
    assert c._last_search_error == "net::ERR_NAME_NOT_RESOLVED"
    network_records = [r for r in caplog_info.records if "网络瞬时故障" in r.message]
    assert network_records and network_records[0].levelname == "WARNING"

    # 其他异常：保留 ERROR + 堆栈
    caplog_info.clear()
    monkeypatch.setattr(c, "_call_search_api", AsyncMock(side_effect=RuntimeError("boom")))
    assert await c.search("内存") == []
    assert any(r.levelname in ("ERROR", "EXCEPTION") for r in caplog_info.records)
    cleanup.assert_awaited()


# ============ 导航 + 重试编排 ============


async def test_navigate_and_wait_for_api_branches(monkeypatch) -> None:
    page = AsyncMock()
    c = _make_collector()
    captured: list[dict] = [{"ret": []}]
    state = {"session_invalid": False, "api_auth_failed": False}
    poll = AsyncMock()
    monkeypatch.setattr(c, "_poll_for_captured_responses", poll)
    retry_auth = AsyncMock()
    monkeypatch.setattr(c, "_retry_search_after_api_auth_failure", retry_auth)
    retry_token = AsyncMock()
    monkeypatch.setattr(c, "_retry_search_after_token_refresh", retry_token)

    got = await c._navigate_and_wait_for_api(
        page, "内存", True, False, "newest", "浙江", ["sourceType=0"], captured, state
    )
    assert got is False
    poll.assert_awaited_once_with(captured, state, 8)  # fast 模式 8 轮
    retry_auth.assert_not_awaited()
    retry_token.assert_not_awaited()
    assert "wait_until" in str(page.goto.await_args)

    # 未捕获响应：输出回退提示
    cap2: list[dict] = []
    state2 = {"session_invalid": False, "api_auth_failed": False}
    poll2 = AsyncMock()
    monkeypatch.setattr(c, "_poll_for_captured_responses", poll2)
    assert await c._navigate_and_wait_for_api(
        page, "内存", False, True, "default", "", [], cap2, state2
    ) is False
    poll2.assert_awaited_once_with(cap2, state2, 15)

    # token 校验失败触发重试
    state3 = {"session_invalid": False, "api_auth_failed": True}
    assert await c._navigate_and_wait_for_api(
        page, "内存", False, True, "default", "", [], [], state3
    ) is False
    retry_auth.assert_awaited_once()

    # 会话失效且允许重试 → 强制刷新 token 后重试
    state4 = {"session_invalid": True, "api_auth_failed": False}
    assert await c._navigate_and_wait_for_api(
        page, "内存", False, False, "default", "", [], [], state4
    ) is True
    retry_token.assert_awaited_once()

    # skip_rgv587_retry=True 时跳过重试
    retry_token.reset_mock()
    state5 = {"session_invalid": True, "api_auth_failed": False}
    assert await c._navigate_and_wait_for_api(
        page, "内存", False, True, "default", "", [], [], state5
    ) is True
    retry_token.assert_not_awaited()


async def test_navigate_goto_timeout_paths(monkeypatch) -> None:
    page = AsyncMock()
    page.goto = AsyncMock(side_effect=RuntimeError("Timeout 20000ms exceeded"))
    c = _make_collector()
    monkeypatch.setattr(c, "_poll_for_captured_responses", AsyncMock())
    monkeypatch.setattr(c, "_goto_timeout_indicates_session_invalid", lambda _p: True)
    state = {"session_invalid": False, "api_auth_failed": False}
    assert await c._navigate_and_wait_for_api(
        page, "内存", False, False, "default", "", [], [], state
    ) is True
    assert state["session_invalid"] is True
    assert c._last_api_captured is False

    monkeypatch.setattr(c, "_goto_timeout_indicates_session_invalid", lambda _p: False)
    with pytest.raises(RuntimeError, match="Timeout"):
        await c._navigate_and_wait_for_api(page, "内存", False, False, "default", "", [], [], state)


async def test_retry_search_after_api_auth_failure(monkeypatch, caplog_info) -> None:
    c = _make_collector()
    monkeypatch.setattr(sm.asyncio, "sleep", AsyncMock())
    page = AsyncMock()
    state = {"session_invalid": False, "api_auth_failed": True}
    captured: list[dict] = []

    async def _fill(captured_arg, state_arg, rounds):
        captured_arg.append({"ret": ["SUCCESS::ok"]})

    monkeypatch.setattr(c, "_poll_for_captured_responses", _fill)
    await c._retry_search_after_api_auth_failure(page, "内存", "url", captured, state, 8, 15000)
    assert captured and c._api_auth_backoff_until == 0.0

    # 重试仍失败 → 进入冷却期
    # 方法开头会把 api_auth_failed 复位，因此冷却期只在轮询再次置位且无响应时触发
    caplog_info.clear()
    captured2: list[dict] = []
    state2 = {"session_invalid": False, "api_auth_failed": True}

    async def _still_failing(captured_arg, state_arg, rounds):
        state_arg["api_auth_failed"] = True

    monkeypatch.setattr(c, "_poll_for_captured_responses", _still_failing)
    await c._retry_search_after_api_auth_failure(page, "内存", "url", captured2, state2, 8, 15000)
    assert c._api_auth_backoff_until > time.monotonic()
    assert any("进入" in r.message and "冷却期" in r.message for r in caplog_info.records)

    # 重试导航失败 → 记录 WARNING 后仍按失败处理
    caplog_info.clear()
    page_boom = AsyncMock()
    page_boom.goto = AsyncMock(side_effect=RuntimeError("net::ERR_ABORTED"))
    captured3: list[dict] = []
    state3 = {"session_invalid": False, "api_auth_failed": True}
    await c._retry_search_after_api_auth_failure(page_boom, "内存", "url", captured3, state3, 3, 15000)
    assert any("重试导航失败" in r.message and r.levelname == "WARNING" for r in caplog_info.records)


async def test_retry_search_after_token_refresh(monkeypatch) -> None:
    c = _make_collector()
    sleeps = AsyncMock()
    monkeypatch.setattr(sm.asyncio, "sleep", sleeps)
    page = AsyncMock()

    # 刷新失败：跳过重试
    monkeypatch.setattr(c, "_ensure_fresh_m5tk", AsyncMock(return_value=False))
    state = {"session_invalid": True, "api_auth_failed": False}
    await c._retry_search_after_token_refresh(page, "内存", "url", [{"x": 1}], state)
    page.goto.assert_not_awaited()

    # 刷新成功：重置状态、清空已捕获响应后重试
    monkeypatch.setattr(c, "_ensure_fresh_m5tk", AsyncMock(return_value=True))
    # 必须把同一个 list 同时交给 _goto 和重试方法：方法内部 clear() 的是引用对象
    captured: list[dict] = [{"stale": 1}]

    async def _goto(url, **kwargs):
        captured.append({"ret": ["SUCCESS::ok"]})

    page.goto = AsyncMock(side_effect=_goto)
    await c._retry_search_after_token_refresh(page, "内存", "url", captured, state)
    assert state["session_invalid"] is False
    assert captured == [{"ret": ["SUCCESS::ok"]}]
    sleeps.assert_not_awaited()

    # 重试导航失败
    page.goto = AsyncMock(side_effect=RuntimeError("boom"))
    await c._retry_search_after_token_refresh(page, "内存", "url", [], state)


# ============ live_search 编排 ============


async def test_live_search_builds_rows_from_api_items(monkeypatch, caplog_info) -> None:
    c = _make_collector()
    item = ItemSummary(id="555", title="金士顿 内存", price=128.0, seller_id="9001",
                       region="浙江杭州", seller_credit="优秀")
    c._seller_nicks["9001"] = "数码小铺"
    monkeypatch.setattr(c, "search", AsyncMock(return_value=[item]))
    collect = AsyncMock()
    monkeypatch.setattr(c, "_collect_sellers_from_details", collect)

    results = await c.live_search("内存", max_pages=1)
    types = [r["link_type"] for r in results]
    assert types == ["item", "seller"]
    assert results[1]["seller_nick"] == "数码小铺"
    collect.assert_not_awaited()  # API 已给出 seller_id，无需访问详情页
    assert any("live_search 完成: 1 个商品, 1 个卖家, 2 条总结果" in r.message for r in caplog_info.records)


async def test_live_search_raises_when_search_failed(monkeypatch) -> None:
    c = _make_collector()
    c._last_search_error = "net::ERR_TIMED_OUT"
    monkeypatch.setattr(c, "search", AsyncMock(return_value=[]))
    with pytest.raises(RuntimeError, match="实时搜索采集失败"):
        await c.live_search("内存")


async def test_live_search_collects_sellers_when_dom_fallback(monkeypatch, caplog_info) -> None:
    c = _make_collector()
    item = ItemSummary(id="555", title="内存", price=1.0, region="北京")
    monkeypatch.setattr(c, "search", AsyncMock(return_value=[item]))

    async def _collect(page, items, max_details, results, desc_by_item_id):
        desc_by_item_id["555"] = "二手内存条"
        results.append({"link_type": "seller", "link_key": "9001", "item_id": "555"})

    monkeypatch.setattr(c, "_collect_sellers_from_details", _collect)
    results = await c.live_search("内存", collect_sellers=True)
    assert [r["link_type"] for r in results] == ["item", "seller"]
    assert results[0]["item_desc"] == "二手内存条"  # 描述回填到 item 行
    assert "item_desc" not in results[1]
    assert any("live_search 完成: 1 个商品, 1 个卖家, 2 条总结果" in r.message for r in caplog_info.records)

    # collect_sellers=False 时不访问详情页
    monkeypatch.setattr(c, "_collect_sellers_from_details", AsyncMock())
    results = await c.live_search("内存", collect_sellers=False)
    assert [r["link_type"] for r in results] == ["item"]


# ============ 详情页补抓卖家 ============


async def test_collect_sellers_from_details_creates_and_closes_page(monkeypatch) -> None:
    detail_page = AsyncMock()
    browser = MagicMock()
    browser.new_page = AsyncMock(return_value=detail_page)
    c = Collector(browser=browser, antidetect=MagicMock(), selectors=SelectorRepo)
    single = AsyncMock()
    monkeypatch.setattr(c, "_collect_single_seller_from_detail", single)

    items = [ItemSummary(id="", title="无 id", price=1.0), ItemSummary(id="555", title="内存", price=1.0)]
    results: list[dict] = []
    descs: dict[str, str] = {}
    await c._collect_sellers_from_details(None, items, 5, results, descs)
    browser.new_page.assert_awaited_once()
    browser.register_external_page.assert_called_once_with(detail_page)
    single.assert_awaited_once()
    assert single.await_args.args[1] is detail_page
    browser.unregister_external_page.assert_called_once_with(detail_page)
    detail_page.close.assert_awaited_once()

    # 注入 page 时不创建也不关闭
    browser.reset_mock()
    detail_page.reset_mock()
    single.reset_mock()
    await c._collect_sellers_from_details(detail_page, items, 5, results, descs)
    browser.new_page.assert_not_awaited()
    detail_page.close.assert_not_awaited()

    # new_page 返回 None → 明确报错，且仍执行清理
    browser.new_page = AsyncMock(return_value=None)
    with pytest.raises(RuntimeError, match="new_page 返回 None"):
        await c._collect_sellers_from_details(None, items, 5, results, descs)


async def test_collect_single_seller_from_detail(monkeypatch, caplog_info) -> None:
    c = _make_collector()
    item = ItemSummary(id="555", title="内存", price=1.0, region="北京", brand="金士顿")

    detail = SimpleNamespace(seller_id="9001", description="全新未拆封")
    monkeypatch.setattr(c, "detail", AsyncMock(return_value=detail))
    results: list[dict] = []
    descs: dict[str, str] = {}
    seen: set[str] = set()
    await c._collect_single_seller_from_detail(item, AsyncMock(), seen, results, descs)
    assert descs == {"555": "全新未拆封"}
    assert seen == {"9001"}
    assert results[0]["link_type"] == "seller"
    assert results[0]["title"] == "卖家 9001"
    assert results[0]["item_id"] == "555"
    assert results[0]["url"].endswith("9001")

    # 同一卖家第二个商品不再产生新行，但描述仍回填
    monkeypatch.setattr(c, "detail", AsyncMock(return_value=SimpleNamespace(seller_id="9001", description="")))
    other = ItemSummary(id="556", title="内存", price=1.0, region="北京")
    await c._collect_single_seller_from_detail(other, AsyncMock(), seen, results, descs)
    assert len(results) == 1
    assert "556" not in descs

    # detail 返回 None / 无 seller_id：不追加
    monkeypatch.setattr(c, "detail", AsyncMock(return_value=None))
    await c._collect_single_seller_from_detail(other, AsyncMock(), seen, results, descs)
    assert len(results) == 1

    # detail 抛异常：降级为 WARNING，不影响其余商品
    cap = AsyncMock(side_effect=RuntimeError("detail failed"))
    monkeypatch.setattr(c, "detail", cap)
    await c._collect_single_seller_from_detail(other, AsyncMock(), seen, results, descs)
    assert len(results) == 1
    assert any("提取卖家失败" in r.message and r.levelname == "WARNING" for r in caplog_info.records)
