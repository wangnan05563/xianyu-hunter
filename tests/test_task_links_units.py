"""api_task_links（任务关联 API）单元与端点测试

覆盖面：
- Cookie 保障链路（浏览器内存读取、过期/陈旧判定、JSON 补注入、错误码）
- 关联行归一化与 items 表字段补全
- live 搜索的格式化 / 关键词 / 排除词 / 价格 / 发布天数过滤
- 价格策略与市场上下文构造
- live 评估与异步抢单（含冷却、模式、buyer 缺失分支）
- 11 个 HTTP 端点的正常与校验分支

隔离：所有 repo/浏览器/collector 均为假对象，不连真实 DB 与浏览器。
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from xianyu_hunter.domain.evaluation import RiskLevel
from xianyu_hunter.domain.order import BuyOutcome
from xianyu_hunter.modules.evaluator import PriceRange  # noqa: F401  (用于对照真实策略行为)
from xianyu_hunter.modules.price_strategy import PriceConfig, PriceStrategy
from xianyu_hunter.web.middleware.exception_handler import CodedHTTPException
from xianyu_hunter.web.routes import api_task_links as api


class _Lock:
    """最小 PriorityBrowserLock 替身：记录释放次数"""

    def __init__(self) -> None:
        self.released = 0

    async def acquire(self, priority: str = "normal") -> bool:
        return True

    def release(self) -> None:
        self.released += 1

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc) -> None:
        self.release()


class _Browser:
    def __init__(self, cookies: list[dict] | None = None, add_ok: bool = True) -> None:
        self._cookies = cookies or []
        self.add_ok = add_ok
        self.added: list[dict] = []

    async def get_cookies(self) -> list[dict]:
        return self._cookies

    async def add_cookies(self, cookies: list[dict]) -> bool:
        self.added = cookies
        return self.add_ok


class _AliveBrowser(_Browser):
    def __init__(self, alive: bool = True, **kwargs) -> None:
        super().__init__(**kwargs)
        self.alive = alive

    async def ensure_alive(self) -> bool:
        return self.alive


def _make_container(**overrides) -> SimpleNamespace:
    container = SimpleNamespace(
        repo=MagicMock(),
        collector=None,
        browser=None,
        buyer=None,
        evaluator=None,
        browser_lock=_Lock(),
    )
    for k, v in overrides.items():
        setattr(container, k, v)
    return container


def _eval_result(**overrides) -> SimpleNamespace:
    base = dict(
        score=90, risk_level=RiskLevel.LOW, is_passed=True, data_quality="ok",
        dimension_scores={"a": 1}, reject_reasons=[],
        should_auto_buy=MagicMock(return_value=True),
    )
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture(autouse=True)
def _reset_live_state(monkeypatch):
    """清理模块级 live 缓存 / in-flight / 冷却时间，避免用例互相污染"""
    api._live_cache.clear()
    api._live_inflight.clear()
    api._live_buy_tasks.clear()
    monkeypatch.setattr(api, "_live_last_buy_at", 0.0)
    yield
    api._live_cache.clear()
    api._live_inflight.clear()


# ============== 配置与 Cookie 保障 ==============


def test_config_readers_and_fallbacks(monkeypatch) -> None:
    assert isinstance(api._get_live_cache_ttl(), int)
    assert isinstance(api._should_skip_empty_result(), bool)

    def _boom():
        raise RuntimeError("config down")

    monkeypatch.setattr("xianyu_hunter.infra.yaml_config.get_config", _boom)
    assert api._get_live_cache_ttl() == 5
    assert api._should_skip_empty_result() is False
    assert api._load_refresh_search_config() == ("default", "")
    assert api._load_global_price_strategy() is None
    assert api._parse_task_price_config('{"a": 1}') == {"a": 1}
    cfg = api._load_live_search_config({"search_filters": ["x"]})
    assert cfg == (["x"], "default", "")


def test_load_live_search_config_merges_global_tags(monkeypatch) -> None:
    search_cfg = SimpleNamespace(sort_type="new", regions="上海", filter_tags=["g1", "g2"])
    monkeypatch.setattr(
        "xianyu_hunter.infra.yaml_config.get_config",
        lambda: SimpleNamespace(search=search_cfg),
    )
    filters, sort_type, regions = api._load_live_search_config({"search_filters": ["g2", "t1"]})
    assert filters == ["g2", "t1", "g1"]
    assert (sort_type, regions) == ("new", "上海")


def test_clear_live_inflight_pops_and_sets() -> None:
    import asyncio

    ev = asyncio.Event()
    api._live_inflight["t"] = ev
    api._clear_live_inflight("t", ev)
    assert "t" not in api._live_inflight and ev.is_set()


def test_cookie_name_and_expiry_helpers() -> None:
    assert api._missing_live_search_cookie_names({"unb"}) == ["cookie2", "sgcookie"]
    now = time.time()
    cookies = {
        "unb": {"expires": now - 10},
        "cookie2": {"expires": -1},
        "sgcookie": {"expires": "bad"},
    }
    assert api._get_expired_identity_cookies(cookies) == ["unb"]
    assert api._parse_cookie_expires({"expires": "12.5"}) == 12.5
    assert api._parse_cookie_expires({"expires": "x"}) == -1

    item = api._build_pw_cookie_item("unb", "952712345", {"expires": 1000})
    assert item == {
        "name": "unb", "value": "952712345", "domain": ".goofish.com",
        "path": "/", "expires": 1000.0,
    }
    assert "expires" not in api._build_pw_cookie_item("unb", "v", {"expires": -1})


@pytest.mark.asyncio
async def test_get_browser_cookies_by_name_variants() -> None:
    assert await api._get_browser_cookies_by_name(_make_container()) == {}

    dead = _make_container(browser=_AliveBrowser(alive=False))
    assert await api._get_browser_cookies_by_name(dead) == {}

    broken = _make_container(browser=MagicMock(get_cookies=AsyncMock(side_effect=RuntimeError("x"))))
    assert await api._get_browser_cookies_by_name(broken) == {}

    ok = _make_container(browser=_Browser([
        {"name": "unb", "value": "952712345"}, {"name": ""}, {"value": "no-name"},
    ]))
    assert set(await api._get_browser_cookies_by_name(ok)) == {"unb"}


@pytest.mark.asyncio
async def test_collect_cookie_issues_detects_missing_expired_stale() -> None:
    now = time.time()
    browser = _Browser([
        {"name": "unb", "value": "old", "expires": now - 1},
        {"name": "cookie2", "value": "browser"},
    ])
    missing, expired, stale = await api._collect_cookie_issues(
        _make_container(browser=browser), {"cookie2": "json"},
    )
    assert missing == ["sgcookie"]
    assert expired == ["unb"]
    assert stale == ["cookie2"]


@pytest.mark.asyncio
async def test_inject_cookies_from_json_branches(monkeypatch) -> None:
    container = _make_container(browser=_Browser())
    assert await api._inject_cookies_from_json(container, [], [], [], []) is False

    dead = _make_container(browser=_AliveBrowser(alive=False))
    assert await api._inject_cookies_from_json(dead, [{"name": "unb"}], ["x"], [], []) is False

    patched = []
    monkeypatch.setattr(
        "xianyu_hunter.modules.login_orchestrator.sync_cookie_layers_from_json",
        lambda: patched.append(1),
    )
    ok = _make_container(browser=_Browser(add_ok=True))
    assert await api._inject_cookies_from_json(ok, [{"name": "unb"}], [], [], []) is True
    assert patched and ok.browser.added == [{"name": "unb"}]

    refusing = _make_container(browser=_Browser(add_ok=False))
    assert await api._inject_cookies_from_json(refusing, [{"name": "unb"}], [], [], []) is False

    raising = _make_container(browser=MagicMock(add_cookies=AsyncMock(side_effect=RuntimeError("x"))))
    assert await api._inject_cookies_from_json(raising, [{"name": "unb"}], [], [], []) is False


def test_load_pw_cookies_from_json_skips_invalid_and_runtime_tokens(monkeypatch) -> None:
    """JSON 档案读取：空档案早返回，残缺/测试值/MTOP 运行态 Cookie 全部跳过"""
    from xianyu_hunter.web.services import cookie_store as cs

    class _Store:
        def __init__(self, data) -> None:
            self._data = data
            self.invalidated: list[str] = []

        def invalidate_cache(self, user_id: str | None = None) -> None:
            self.invalidated.append(str(user_id))

        def _read_json(self, user_id):
            return self._data

    empty_store = _Store(None)
    monkeypatch.setattr(cs, "get_cookie_store", lambda: empty_store)
    assert api._load_pw_cookies_from_json("default") == ([], {})
    assert empty_store.invalidated == ["default"]

    _cookie2 = "0123456789abcdef0123456789abcdef"
    _h5tk = _cookie2 + "_1730000000000"  # 合法格式：只有 MTOP 白名单会拦它
    store = _Store({"cookies": [
        {"name": "", "value": "v"},
        {"name": "cna", "value": ""},
        {"name": "unb", "value": "123456"},          # 测试数据
        {"name": "_m_h5_tk", "value": _h5tk},         # MTOP 运行态 token
        {"name": "cookie2", "value": _cookie2, "domain": ".goofish.com",
         "path": "/", "expires": 123},
        {"name": "sgcookie", "value": "s" * 40, "expires": "bad"},  # expires 解析失败 → 不带该字段
    ]})
    monkeypatch.setattr(cs, "get_cookie_store", lambda: store)
    pw, identity = api._load_pw_cookies_from_json("user_a")
    assert [c["name"] for c in pw] == ["cookie2", "sgcookie"]
    assert pw[0]["expires"] == 123
    assert "expires" not in pw[1]
    assert identity == {"cookie2": _cookie2, "sgcookie": "s" * 40}


def test_raise_live_cookie_errors() -> None:
    api._raise_live_cookie_errors([], [], [])  # 无错误不抛

    with pytest.raises(CodedHTTPException) as expired:
        api._raise_live_cookie_errors(["unb"], ["cookie2"], [])
    assert expired.value.status_code == 440 and expired.value.code == "cookie_expired"

    with pytest.raises(CodedHTTPException) as stale:
        api._raise_live_cookie_errors([], [], ["sgcookie"])
    assert stale.value.code == "cookie_stale"

    with pytest.raises(CodedHTTPException) as missing:
        api._raise_live_cookie_errors(["unb"], [], [])
    assert missing.value.code == "cookie_missing" and missing.value.status_code == 403


def test_maybe_reset_m5tk_refresh() -> None:
    api._maybe_reset_m5tk_refresh(_make_container(collector=None), True)  # 无 collector 直接返回

    collector = MagicMock()
    collector.should_reset_m5tk.return_value = False
    api._maybe_reset_m5tk_refresh(_make_container(collector=collector), False)
    collector.force_refresh_m5tk_next.assert_not_called()

    api._maybe_reset_m5tk_refresh(_make_container(collector=collector), True)
    collector.force_refresh_m5tk_next.assert_called_once()

    collector2 = MagicMock()
    collector2.should_reset_m5tk.return_value = True
    api._maybe_reset_m5tk_refresh(_make_container(collector=collector2), False)
    collector2.force_refresh_m5tk_next.assert_called_once()


@pytest.mark.asyncio
async def test_ensure_live_search_cookies_flow(monkeypatch) -> None:
    # 无浏览器：直接返回
    await api._ensure_live_search_cookies(_make_container())

    container = _make_container(browser=_Browser())
    monkeypatch.setattr(api, "_load_pw_cookies_from_json", lambda uid="default": ([], {}))
    monkeypatch.setattr(api, "_collect_cookie_issues", AsyncMock(return_value=([], [], [])))
    await api._ensure_live_search_cookies(container, "default")  # 全部正常

    # 缺失 + JSON 里有 + 注入失败 → 503 browser_unavailable
    monkeypatch.setattr(api, "_collect_cookie_issues", AsyncMock(return_value=(["unb"], [], [])))
    monkeypatch.setattr(api, "_load_pw_cookies_from_json", lambda uid="default": ([{"name": "unb"}], {"unb": "v"}))
    monkeypatch.setattr(api, "_inject_cookies_from_json", AsyncMock(return_value=False))
    with pytest.raises(CodedHTTPException) as err:
        await api._ensure_live_search_cookies(container)
    assert err.value.code == "browser_unavailable"

    # 注入成功但内存仍读不到 → 503 cookie_sync_failed
    monkeypatch.setattr(api, "_inject_cookies_from_json", AsyncMock(return_value=True))
    with pytest.raises(CodedHTTPException) as err2:
        await api._ensure_live_search_cookies(container)
    assert err2.value.code == "cookie_sync_failed"

    # JSON 中也没有该 cookie → 交给 _raise_live_cookie_errors（403）
    monkeypatch.setattr(api, "_load_pw_cookies_from_json", lambda uid="default": ([], {}))
    with pytest.raises(CodedHTTPException) as err3:
        await api._ensure_live_search_cookies(container)
    assert err3.value.code == "cookie_missing"


# ============== 归一化与字段补全 ==============


def test_normalize_task_link_rows_and_live_result() -> None:
    rows, field_map = api._normalize_task_link_rows([
        {"id": 1, "display": {"title": "t"}}, {"id": 2, "display": "not-a-dict"},
    ])
    assert len(rows) == 2 and isinstance(field_map, dict)

    out = api._normalize_live_result({
        "items": [{"link_type": "item", "link_key": "1", "display": {"title": "a"}}],
        "sellers": [{"link_type": "seller", "link_key": "s1", "display": {"title": "b"}}],
    })
    assert out["counts"] == {"item": 1, "seller": 1, "total": 2}
    assert out["field_map"] is not None

    empty = api._normalize_live_result({})
    assert empty["field_map"] == {}


def test_build_list_result_items_maps_id_to_link_id(monkeypatch) -> None:
    monkeypatch.setattr(api, "_enrich_with_item_data", lambda items, c, user_id=None: items)
    out = api._build_list_result_items(
        [{"id": 7, "display": {"title": "t"}}, {"display": "bad"}],
        _make_container(), None,
    )
    assert out[0]["link_id"] == 7 and "id" not in out[0]
    assert out[1]["display"] == "bad"


def test_log_list_links_performance_both_branches() -> None:
    api._log_list_links_performance("t", "item", 50, 0, 10, 10.0)
    api._log_list_links_performance("t", None, 50, 0, 10, 300.0)


def test_item_extra_helpers() -> None:
    links = [
        {"link_type": "item", "link_key": "1"},
        {"link_type": "seller", "link_key": "2"},
        {"link_type": "item", "link_key": ""},
    ]
    assert api._collect_item_ids_from_links(links) == {"1"}

    extra = api._build_item_extra_dict({
        "id": 5, "region": None, "seller_id": "s", "seller_nick": None,
        "want_cnt": None, "view_cnt": 2, "publish_time": None, "thumb_url": None,
        "is_sold": 1,
    })
    assert extra["region"] == "" and extra["seller_nick"] == "s"
    assert extra["publish_time"] is None and extra["is_sold"] is True
    assert extra["url"]

    dt = datetime(2026, 1, 2, tzinfo=timezone.utc)
    assert api._build_item_extra_dict({"id": 6, "publish_time": dt})["publish_time"] == dt.isoformat()

    item_map = api._build_item_map_from_rows([{"id": 1}, None, {"id": 0}])
    assert set(item_map) == {"1"}


def test_display_helpers() -> None:
    assert api._parse_display_json({"a": 1}) == {"a": 1}
    assert api._parse_display_json('{"a": 1}') == {"a": 1}
    assert api._parse_display_json("[1]") == {}
    assert api._parse_display_json("{bad") == {}
    assert api._parse_display_json(None) == {}

    assert api._should_update_field("is_sold", True) is True
    assert api._should_update_field("region", None) is True
    assert api._should_update_field("region", "") is True
    assert api._should_update_field("region", "None") is True
    assert api._should_update_field("region", "上海") is False

    display = {"region": "上海", "seller_id": ""}
    out = api._apply_extra_to_display(display, {"region": "北京", "seller_id": "s", "is_sold": False})
    assert out == {"region": "上海", "seller_id": "s", "is_sold": False}


def test_enrich_single_link_and_with_item_data() -> None:
    link = {"link_type": "seller", "link_key": "s1", "display": {}}
    api._enrich_single_link(link, {"s1": {"region": "x"}})
    assert link["display"] == {}

    link2 = {"link_type": "item", "link_key": "nope", "display": {}}
    api._enrich_single_link(link2, {})
    assert link2["display"] == {}

    link3 = {"link_type": "item", "link_key": "1", "display": '{"title": "t"}'}
    api._enrich_single_link(link3, {"1": {"region": "上海"}})
    assert link3["display"] == {"title": "t", "region": "上海"}

    container = _make_container()
    assert api._enrich_with_item_data([], container) == []
    assert api._enrich_with_item_data([{"link_type": "seller"}], container) == [{"link_type": "seller"}]

    container.repo.list_items_by_ids.side_effect = RuntimeError("db down")
    # 异常路径原样返回 links：不构造 display，调用方按缺字段降级展示
    assert api._enrich_with_item_data([{"link_type": "item", "link_key": "1"}], container) == [
        {"link_type": "item", "link_key": "1"}
    ]

    container2 = _make_container()
    container2.repo.list_items_by_ids.return_value = [{"id": "1", "region": "上海"}]
    out = api._enrich_with_item_data([{"link_type": "item", "link_key": "1", "display": {}}], container2)
    assert out[0]["display"]["region"] == "上海"


# ============== refresh 链路 ==============


def test_raise_search_error_branches() -> None:
    from fastapi import HTTPException

    for msg, status in [
        ("TargetClosed", 502), ("RGV587", 403), ("Connection closed", 502), ("unknown", 502),
    ]:
        with pytest.raises(HTTPException) as err:
            api._raise_search_error(msg)
        assert err.value.status_code == status


def test_build_and_save_refresh_results() -> None:
    item = SimpleNamespace(
        id="1", title="t", price=10, thumb_url="u", brand=None, seller_id=None,
        seller_nick=None, region="上海", publish_time=None, want_cnt=1, view_cnt=2, is_sold=False,
    )
    data = api._build_refresh_items_data([item])
    assert data[0]["item_id"] == "1" and data[0]["brand"] == "" and data[0]["seller_nick"] == ""

    container = _make_container()
    container.repo.batch_upsert_item_task_links.return_value = 1
    assert api._save_refresh_results(container, "t1", [item]) == 1

    container.repo.batch_upsert_item_task_links.side_effect = RuntimeError("write failed")
    assert api._save_refresh_results(container, "t1", [item]) == 0


@pytest.mark.asyncio
async def test_execute_refresh_search_success_and_errors() -> None:
    container = _make_container(collector=MagicMock(search=AsyncMock(return_value=[{"id": "1"}])))
    assert await api._execute_refresh_search(container, "t1", "kw", [], "default", "") == [{"id": "1"}]

    from fastapi import HTTPException

    container.collector.search = AsyncMock(side_effect=RuntimeError("RGV587"))
    with pytest.raises(HTTPException) as err:
        await api._execute_refresh_search(container, "t1", "kw", [], "default", "")
    assert err.value.status_code == 403

    bad_lock = MagicMock()
    bad_lock.__aenter__ = AsyncMock(side_effect=RuntimeError("boom"))
    bad_lock.__aexit__ = AsyncMock(return_value=False)
    container2 = _make_container(collector=MagicMock(), browser_lock=bad_lock)
    with pytest.raises(HTTPException) as err2:
        await api._execute_refresh_search(container2, "t1", "kw", [], "default", "")
    assert err2.value.status_code == 502 and "刷新搜索异常" in err2.value.detail


# ============== live 格式化与过滤 ==============


def _raw_item(**overrides) -> dict:
    base = {
        "link_type": "item", "link_key": "1", "title": "九成新 iPhone", "price": 500,
        "thumb_url": "u", "brand": "Apple", "region": "上海", "url": "http://x",
        "is_sold": False, "publish_time": None, "seller_id": "s1", "seller_nick": "n",
        "seller_credit": "c", "want_cnt": 1, "view_cnt": 2, "item_desc": "",
    }
    base.update(overrides)
    return base


def _summary() -> dict:
    return {
        "raw": 0, "formatted": 0, "keyword_skipped": 0, "price_skipped": 0,
        "publish_days_skipped": 0, "filtered_out": [],
    }


def test_format_live_raw_results() -> None:
    results, field_map, summary = api._format_live_raw_results([_raw_item()], "t1")
    assert results[0]["link_type"] == "item" and results[0]["link_id"] == 0
    assert results[0]["display"]["title"] == "九成新 iPhone"
    assert isinstance(field_map, dict) and summary["formatted"] == 1


def test_filter_live_by_keyword() -> None:
    summary = _summary()
    results = api._format_live_raw_results(
        [_raw_item(), _raw_item(link_key="2", title="显卡低价")], "t1",
    )[0]
    kept = api._filter_live_by_keyword(results, "iPhone", summary)
    assert len(kept) == 1 and summary["keyword_skipped"] == 1
    assert summary["filtered_out"][0]["filter_reason"] == "keyword"


def test_exclude_word_helpers_and_filter() -> None:
    assert api._find_exclude_word_hit("16G 内存", "", ["16G"]) == ("16G", "标题")
    assert api._find_exclude_word_hit("标题", "描述含仿品", ["仿品"]) == ("仿品", "描述")
    assert api._find_exclude_word_hit("t", "", ["", "x"]) == (None, "")

    capped: list[dict] = [{}] * 50
    api._add_filtered_out_item(capped, {"link_type": "item"}, "r", "d")
    assert len(capped) == 50

    summary = _summary()
    results = api._format_live_raw_results(
        [_raw_item(), _raw_item(link_key="2", item_desc="全新仅拆封仿品")], "t1",
    )[0]
    kept = api._filter_live_by_exclude_words(results, ["仿品"], summary)
    assert len(kept) == 1 and summary["exclude_words_skipped"] == 1
    assert api._filter_live_by_exclude_words(kept, [], summary) is kept


def test_price_helpers_and_filter(monkeypatch) -> None:
    ps = SimpleNamespace(enabled_min=True, min_price=100, enabled_max=True, max_price=200)
    assert api._compute_effective_price_range(None, None, ps) == (100, 200)
    assert api._compute_effective_price_range(50, None, ps) == (50, 200)
    assert api._compute_effective_price_range(None, None, None) == (None, None)
    assert api._safe_parse_price("12.5") == 12.5
    assert api._safe_parse_price("x") is None and api._safe_parse_price(None) is None
    assert api._check_price_filter(50, 100, None)
    assert api._check_price_filter(300, None, 200)
    assert api._check_price_filter(150, 100, 200) is None

    monkeypatch.setattr(api, "_load_global_price_strategy", lambda: None)
    summary = _summary()
    rows = api._format_live_raw_results(
        [_raw_item(price=50), _raw_item(link_key="2", price=300), _raw_item(link_key="3", price=None)],
        "t1",
    )[0]
    kept = api._filter_live_by_price(rows, 100, 200, summary)
    assert [r["link_key"] for r in kept] == ["3"]
    assert summary["price_skipped"] == 2

    assert api._filter_live_by_price(rows, None, None, _summary()) == rows


def test_filter_live_by_publish_days() -> None:
    assert api._filter_live_by_publish_days([], None, _summary()) == []

    old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    new = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    summary = _summary()
    rows = api._format_live_raw_results([
        _raw_item(link_key="1", publish_time=old),
        _raw_item(link_key="2", publish_time=new),
        _raw_item(link_key="3", publish_time=None),
        _raw_item(link_key="4", publish_time="not-a-date"),
    ], "t1")[0]
    kept = api._filter_live_by_publish_days(rows, 7, summary)
    assert {r["link_key"] for r in kept} == {"2", "3", "4"}
    assert summary["publish_days_skipped"] == 1

    # naive ISO（无时区）同样按 UTC 参与比较：不能因 TypeError 被静默放过
    naive_old = (datetime.now(timezone.utc) - timedelta(days=30)).replace(tzinfo=None).isoformat()
    rows_naive = api._format_live_raw_results([_raw_item(link_key="9", publish_time=naive_old)], "t1")[0]
    summary2 = _summary()
    assert api._filter_live_by_publish_days(rows_naive, 7, summary2) == []
    assert summary2["publish_days_skipped"] == 1


def test_build_live_items_data_and_final_result() -> None:
    items = [{"link_type": "item", "link_key": "1", "display": {"title": "t", "price": 10}}]
    data = api._build_live_items_data(items)
    assert data[0]["item_id"] == "1" and data[0]["brand"] == ""

    container = _make_container(collector=SimpleNamespace(last_session_invalid=True))
    result = api._build_live_final_result(
        "t1", "kw", container, items, [], items, {}, _summary(),
    )
    assert result["ok"] is True and result["session_expired"] is True
    assert result["counts"]["total"] == 1


def test_live_search_error_sse_branches() -> None:
    assert api._build_live_search_error_sse("TargetClosed")["status"] == 502
    assert api._build_live_search_error_sse("RGV587")["status"] == 403
    assert api._build_live_search_error_sse("Connection closed")["status"] == 502
    assert api._build_live_search_error_sse("x")["detail"] == "闲鱼搜索失败: x"


def test_check_live_cache_hit_and_miss() -> None:
    assert api._check_live_cache("t1", time.monotonic()) is None
    api._live_cache["t1"] = (time.monotonic(), {"items": [], "sellers": []})
    assert api._check_live_cache("t1", time.monotonic()) is not None


@pytest.mark.asyncio
async def test_wait_for_inflight_search_paths(monkeypatch) -> None:
    import asyncio

    ev = asyncio.Event()
    ev.set()
    # 缓存里有行才会生成 counts（_normalize_live_result 对空行不加 counts）
    api._live_cache["t1"] = (
        time.monotonic(), {"all": [{"link_type": "item", "link_key": "1", "display": {}}]},
    )
    got = await api._wait_for_inflight_search("t1", time.monotonic(), ev)
    assert got["stage"] == "done" and got["counts"] == {"item": 1, "seller": 0, "total": 1}

    api._live_cache.clear()
    got2 = await api._wait_for_inflight_search("t1", time.monotonic(), ev)
    assert got2["stage"] == "done" and got2["items"] == []

    async def _timeout(*args, **kwargs):
        raise asyncio.TimeoutError

    monkeypatch.setattr(api.asyncio, "wait_for", _timeout)
    got3 = await api._wait_for_inflight_search("t1", time.monotonic(), ev)
    assert got3["status"] == 503


@pytest.mark.asyncio
async def test_check_live_cookies_safely(monkeypatch) -> None:
    import asyncio

    ev = asyncio.Event()
    api._live_inflight["t1"] = ev
    monkeypatch.setattr(api, "_ensure_live_search_cookies", AsyncMock(return_value=None))
    assert await api._check_live_cookies_safely(_make_container(), "t1", ev) is None

    api._live_inflight["t1"] = ev = asyncio.Event()
    monkeypatch.setattr(
        api, "_ensure_live_search_cookies",
        AsyncMock(side_effect=CodedHTTPException(status_code=440, code="cookie_expired", detail="expired")),
    )
    event = await api._check_live_cookies_safely(_make_container(), "t1", ev)
    assert event["status"] == 440 and event["code"] == "cookie_expired"
    assert "t1" not in api._live_inflight

    api._live_inflight["t1"] = ev2 = asyncio.Event()
    monkeypatch.setattr(
        api, "_ensure_live_search_cookies",
        AsyncMock(side_effect=RuntimeError("boom")),
    )
    event2 = await api._check_live_cookies_safely(_make_container(), "t1", ev2)
    assert event2["status"] == 502 and "Cookie 检查异常" in event2["detail"]


@pytest.mark.asyncio
async def test_try_acquire_live_lock_once() -> None:
    assert await api._try_acquire_live_lock_once(_make_container(), 1.0) is True

    class _TimeoutLock:
        async def acquire(self, priority="normal"):
            raise TimeoutError

    assert await api._try_acquire_live_lock_once(
        _make_container(browser_lock=_TimeoutLock()), 1.0,
    ) is False


# ============== live 搜索重试 ==============


def _collector(live_results: list[dict] | None = None, invalid: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        live_search=AsyncMock(return_value=live_results or []),
        last_session_invalid=invalid,
        _ensure_fresh_m5tk=AsyncMock(return_value=True),
        should_reset_m5tk=lambda: False,
        force_refresh_m5tk_next=lambda: None,
    )


@pytest.mark.asyncio
async def test_maybe_retry_live_search_variants(monkeypatch) -> None:
    # 有结果 → 不重试
    results, err = await api._maybe_retry_live_search(
        _make_container(collector=_collector(invalid=True)), "t", "kw", [], "d", "", [{"a": 1}],
    )
    assert results == [{"a": 1}] and err is None

    # 空结果但登录态有效 → 不重试
    results, err = await api._maybe_retry_live_search(
        _make_container(collector=_collector(invalid=False)), "t", "kw", [], "d", "", [],
    )
    assert results == [] and err is None

    # RGV587：刷新 token 后重试成功
    page = SimpleNamespace(close=AsyncMock())
    browser = SimpleNamespace(new_page=AsyncMock(return_value=page))
    collector = _collector(live_results=[{"b": 2}], invalid=True)
    results, err = await api._maybe_retry_live_search(
        _make_container(collector=collector, browser=browser), "t", "kw", [], "d", "", [],
    )
    assert results == [{"b": 2}] and err is None
    page.close.assert_awaited_once()

    # 重试抛异常 → 返回错误事件
    browser2 = SimpleNamespace(new_page=AsyncMock(side_effect=RuntimeError("TargetClosed")))
    results, err = await api._maybe_retry_live_search(
        _make_container(collector=_collector(invalid=True), browser=browser2), "t", "kw", [], "d", "", [],
    )
    assert results == [] and err["status"] == 502

    # 重试超时 → 504
    async def _timeout(*args, **kwargs):
        import asyncio

        raise asyncio.TimeoutError

    monkeypatch.setattr(api.asyncio, "wait_for", _timeout)
    results, err = await api._maybe_retry_live_search(
        _make_container(collector=_collector(invalid=True), browser=SimpleNamespace(new_page=AsyncMock(return_value=page))),
        "t", "kw", [], "d", "", [],
    )
    assert err["status"] == 504


@pytest.mark.asyncio
async def test_execute_live_search_with_retry_variants(monkeypatch) -> None:
    results, err = await api._execute_live_search_with_retry(
        _make_container(collector=_collector(live_results=[{"a": 1}])), "t", "kw", [], "d", "",
    )
    assert results == [{"a": 1}] and err is None

    # RGV587 重试自身异常 → 直接返回重试错误事件（不走 403 分支）
    results, err = await api._execute_live_search_with_retry(
        _make_container(
            collector=_collector(live_results=[], invalid=True),
            browser=SimpleNamespace(new_page=AsyncMock(side_effect=RuntimeError("Connection closed"))),
        ),
        "t", "kw", [], "d", "",
    )
    assert results == [] and err["status"] == 502

    # RGV587 重试仍空 + 登录态仍失效 → 403（重试需要 browser.new_page）
    retry_page = AsyncMock()
    retry_page.close = AsyncMock()
    results, err = await api._execute_live_search_with_retry(
        _make_container(
            collector=_collector(live_results=[], invalid=True),
            browser=SimpleNamespace(new_page=AsyncMock(return_value=retry_page)),
        ),
        "t", "kw", [], "d", "",
    )
    assert results == [] and err["status"] == 403

    # 首次搜索抛异常 → 502 事件
    bad = _collector()
    bad.live_search = AsyncMock(side_effect=RuntimeError("Connection closed"))
    results, err = await api._execute_live_search_with_retry(
        _make_container(collector=bad), "t", "kw", [], "d", "",
    )
    assert results == [] and err["status"] == 502

    # 首次搜索超时 → 504
    async def _timeout(*args, **kwargs):
        import asyncio

        raise asyncio.TimeoutError

    monkeypatch.setattr(api.asyncio, "wait_for", _timeout)
    results, err = await api._execute_live_search_with_retry(
        _make_container(collector=_collector()), "t", "kw", [], "d", "",
    )
    assert results == [] and err["status"] == 504


# ============== 价格策略 / 评估 / 抢单 ==============


def test_price_strategy_helpers() -> None:
    assert api._parse_task_price_config({"a": 1}) == {"a": 1}
    assert api._parse_task_price_config('{"b": 2}') == {"b": 2}
    assert api._parse_task_price_config("[1]") == {}
    assert api._parse_task_price_config("{bad") == {}
    assert api._parse_task_price_config(None) == {}

    assert api._merge_task_price_params({"min_price": 1}, {"max_price": 2}) == (1, 2)
    assert api._merge_task_price_params({}, {"min_price": 3, "max_price": 4}) == (3, 4)
    assert api._merge_task_price_params({"min_price": 5}, {}) == (5, None)

    assert api._resolve_market_ratio({"market_ratio": 0.6}, SimpleNamespace(market_ratio=0.8)) == 0.6
    assert api._resolve_market_ratio({}, SimpleNamespace(market_ratio=0.8)) == 0.8

    assert api._collect_prices_from_items([
        {"display": {"price": "10"}}, {"display": {"price": None}},
        {"display": {"price": "x"}}, {},
    ]) == [10.0]

    assert api._compute_median([3, 1, 2]) == 2
    assert api._compute_median([4, 1, 3, 2]) == 2.5
    assert api._build_market_context([1, 2]) is None
    ctx = api._build_market_context([1, 2, 3])
    assert ctx.sample_size == 3 and ctx.median_price == 2


def test_build_live_price_strategy(monkeypatch) -> None:
    container = _make_container()
    container.repo.get_task.return_value = {
        "min_price": 100,
        "price_config": '{"max_price": 200, "market_ratio": 0.7}',
    }
    items = [{"display": {"price": p}} for p in (100, 200, 300)]
    strategy, ctx = api._build_live_price_strategy(container, "t1", items)
    assert isinstance(strategy, PriceStrategy)
    assert strategy.config.min_price == 100 and strategy.config.max_price == 200
    assert strategy.config.market_ratio == 0.7
    assert ctx is not None and ctx.sample_size == 3

    container.repo.get_task.return_value = None
    strategy2, ctx2 = api._build_live_price_strategy(container, "t1", [])
    assert isinstance(strategy2, PriceStrategy) and ctx2 is None


def test_build_live_item_detail_ok_and_failure() -> None:
    detail = api._build_live_item_detail("1", {"title": "t", "price": "10", "region": "", "is_sold": True})
    assert detail.id == "1" and detail.price == 10.0 and detail.is_sold is True
    assert api._build_live_item_detail("1", {"price": "not-a-number"}) is None


def test_eval_level_and_seller_profile() -> None:
    assert api._resolve_eval_event_level(True, RiskLevel.EXTREME) == "info"
    assert api._resolve_eval_event_level(False, RiskLevel.LOW) == "warning"
    assert api._resolve_eval_event_level(False, RiskLevel.EXTREME) == "error"
    assert api._resolve_eval_event_level(False, RiskLevel.UNKNOWN) == "warning"

    profile = api._build_degraded_seller_profile("", "")
    assert profile.id == "unknown" and profile.nick == ""


def test_write_live_eval_event() -> None:
    container = _make_container()
    detail = api._build_live_item_detail("1", {"title": "t", "price": 10})
    api._write_live_eval_event(container, "t1", "u1", detail, _eval_result(score=None))
    event = container.repo.upsert_eval_event.call_args[0][0]
    assert event["level"] == "info" and "N/A" in event["message"]
    assert json.loads(event["payload"])["item_id"] == "1"


def test_evaluate_single_live_item_branches() -> None:
    container = _make_container()
    evaluator = MagicMock()
    evaluator.evaluate.return_value = _eval_result()
    base = {"display": {"title": "t", "price": 10, "seller_id": "s"}, "link_key": "1"}

    assert api._evaluate_single_live_item({}, evaluator, "t1", "u", container, 80, None, None) == (False, None, False)

    # 构造 detail 失败
    assert api._evaluate_single_live_item(
        {"display": {"price": "bad"}, "link_key": "1"}, evaluator, "t1", "u", container, 80, None, None,
    ) == (False, None, False)

    # 未达抢单门槛
    evaluator.evaluate.return_value = _eval_result(should_auto_buy=MagicMock(return_value=False))
    assert api._evaluate_single_live_item(base, evaluator, "t1", "u", container, 80, None, None) == (True, None, False)

    # 达标 → 候选
    evaluator.evaluate.return_value = _eval_result()
    evaluated, candidate, price_filtered = api._evaluate_single_live_item(
        base, evaluator, "t1", "u", container, 80, None, None,
    )
    assert evaluated is True and candidate["item_id"] == "1" and price_filtered is False

    # 价格策略不通过 → price_filtered
    strategy = SimpleNamespace(
        config=None,
        check=lambda detail, ctx: SimpleNamespace(pass_=False, reasons=["too cheap"]),
    )
    evaluated, candidate, price_filtered = api._evaluate_single_live_item(
        base, evaluator, "t1", "u", container, 80, strategy, None,
    )
    assert evaluated is True and candidate is None and price_filtered is True

    # 策略带价格区间配置时，Evaluator 会收到 price_range 参数
    pass_strategy = SimpleNamespace(
        config=SimpleNamespace(min_price=1, max_price=None),
        check=lambda detail, ctx: SimpleNamespace(pass_=True, reasons=[]),
    )
    evaluator.evaluate = MagicMock(return_value=_eval_result())
    evaluated, candidate, price_filtered = api._evaluate_single_live_item(
        base, evaluator, "t1", "u", container, 80, pass_strategy, None,
    )
    assert evaluated is True and candidate is not None and price_filtered is False
    assert evaluator.evaluate.call_args.kwargs["price_range"].min_price == 1

    # 评估异常
    evaluator.evaluate.side_effect = RuntimeError("eval failed")
    assert api._evaluate_single_live_item(base, evaluator, "t1", "u", container, 80, None, None) == (False, None, False)


@pytest.mark.asyncio
async def test_trigger_live_evaluation_dispatches_candidates(monkeypatch) -> None:
    import asyncio

    container = _make_container(evaluator=MagicMock(evaluate=MagicMock(return_value=_eval_result())))
    container.repo.get_task.return_value = {"mode": "manual"}
    container.repo.upsert_eval_event.return_value = None
    container.browser_lock = _Lock()
    items = [{"display": {"title": "t", "price": 10, "seller_id": "s"}, "link_key": "1"}]

    api._trigger_live_evaluation(container, "t1", items, user_id=None)
    await asyncio.sleep(0)  # 让 create_task 的抢单协程启动并走"模式非 auto"分支
    assert container.repo.upsert_eval_event.called

    api._safe_trigger_live_evaluation(container, "t1", items)


@pytest.mark.asyncio
async def test_trigger_live_evaluation_counts_price_filtered(monkeypatch) -> None:
    """价格过滤命中的商品计入统计，且不进入抢单候选"""
    import asyncio

    container = _make_container(evaluator=MagicMock(evaluate=MagicMock(return_value=_eval_result())))
    container.repo.upsert_eval_event.return_value = None
    monkeypatch.setattr(
        api, "_build_live_price_strategy",
        lambda c, tid, its: (
            SimpleNamespace(
                config=None,
                check=lambda d, ctx: SimpleNamespace(pass_=False, reasons=["over max"]),
            ),
            None,
        ),
    )
    items = [{"display": {"title": "t", "price": 9999, "seller_id": "s"}, "link_key": "1"}]
    api._trigger_live_evaluation(container, "t1", items, user_id=None)
    await asyncio.sleep(0)
    assert api._live_buy_tasks == set()
    assert container.repo.upsert_eval_event.called


def test_safe_trigger_live_evaluation_swallows_errors(monkeypatch) -> None:
    def _boom(*args, **kwargs):
        raise RuntimeError("eval down")

    monkeypatch.setattr(api, "_trigger_live_evaluation", _boom)
    api._safe_trigger_live_evaluation(_make_container(), "t1", [])


@pytest.mark.asyncio
async def test_trigger_live_auto_buy_branches() -> None:
    candidate = {"item_id": "1", "price": 10, "score": 90}

    # 任务不存在 / 非 auto
    container = _make_container()
    container.repo.get_task.return_value = None
    await api._trigger_live_auto_buy(container, "t1", candidate)

    container.repo.get_task.return_value = {"mode": "manual"}
    await api._trigger_live_auto_buy(container, "t1", candidate)

    # buyer 未注入
    container.repo.get_task.return_value = {"mode": "auto"}
    await api._trigger_live_auto_buy(container, "t1", candidate)

    # 冷却中
    import time as _time

    buy = MagicMock()
    buy.buy = AsyncMock(return_value=SimpleNamespace(outcome=BuyOutcome.SUCCESS))
    container.buyer = buy
    api._live_last_buy_at = _time.monotonic()
    await api._trigger_live_auto_buy(container, "t1", candidate)
    buy.buy.assert_not_awaited()

    # 抢单成功
    api._live_last_buy_at = 0.0
    released_before = container.browser_lock.released
    await api._trigger_live_auto_buy(container, "t1", candidate)
    buy.buy.assert_awaited_once()
    # 冷却分支同样在锁内检查并在 finally 释放，故每次调用净增 1 次释放
    assert container.browser_lock.released == released_before + 1

    # 抢单失败分支
    api._live_last_buy_at = 0.0
    buy.buy = AsyncMock(return_value=SimpleNamespace(outcome=BuyOutcome.FAILED, error="no stock"))
    await api._trigger_live_auto_buy(container, "t1", candidate)

    # 异常分支（锁仍会释放）
    api._live_last_buy_at = 0.0
    buy.buy = AsyncMock(side_effect=RuntimeError("boom"))
    before = container.browser_lock.released
    await api._trigger_live_auto_buy(container, "t1", candidate)
    assert container.browser_lock.released == before + 1


# ============== live SSE 事件流 ==============


def _sse_payload(event: str) -> dict:
    assert event.startswith("data: ")
    return json.loads(event[len("data: "):])


def _live_container(**overrides) -> SimpleNamespace:
    collector = _collector(live_results=[_raw_item()])
    container = _make_container(browser=_Browser(), collector=collector)
    container.repo.batch_upsert_item_task_links.return_value = 1
    for k, v in overrides.items():
        setattr(container, k, v)
    return container


@pytest.mark.asyncio
async def test_live_event_stream_full_success(monkeypatch) -> None:
    from fastapi import BackgroundTasks

    monkeypatch.setattr(api, "_ensure_live_search_cookies", AsyncMock(return_value=None))
    container = _live_container()
    background = BackgroundTasks()
    events = [
        _sse_payload(e) async for e in api._live_event_stream(
            container, background, "t1", "iPhone", None, 100, 1000, None, [],
            [], "default", "",
        )
    ]
    stages = [e["stage"] for e in events]
    assert stages[0] == "checking_cache"
    assert "searching" in stages and "writing_db" in stages
    assert stages[-1] == "done" and events[-1]["counts"]["total"] == 1
    assert background.tasks  # 写入商品后应注册后台评估


@pytest.mark.asyncio
async def test_live_event_stream_cache_hit() -> None:
    from fastapi import BackgroundTasks

    api._live_cache["t1"] = (time.monotonic(), {"items": [], "sellers": [], "all": []})
    events = [
        _sse_payload(e) async for e in api._live_event_stream(
            _live_container(), BackgroundTasks(), "t1", "kw", None, None, None, None, [],
            [], "default", "",
        )
    ]
    assert [e["stage"] for e in events] == ["checking_cache", "done"]


@pytest.mark.asyncio
async def test_live_event_stream_waits_for_inflight() -> None:
    import asyncio
    from fastapi import BackgroundTasks

    api._live_cache["t1"] = (time.monotonic() - 10_000, {"all": []})  # 过期缓存：阶段 1 不命中
    ev = asyncio.Event()
    api._live_inflight["t1"] = ev
    events = []
    async for e in api._live_event_stream(
        _live_container(), BackgroundTasks(), "t1", "kw", None, None, None, None, [],
        [], "default", "",
    ):
        payload = _sse_payload(e)
        events.append(payload)
        if payload["stage"] == "waiting_inflight":
            # 模拟 in-flight 搜索在等待期间写入缓存
            api._live_cache["t1"] = (
                time.monotonic(), {"all": [{"link_type": "item", "link_key": "1", "display": {}}]},
            )
            ev.set()
    assert events[0]["stage"] == "checking_cache"
    assert events[1]["stage"] == "waiting_inflight"
    assert events[-1]["stage"] == "done"
    assert events[-1]["counts"]["total"] == 1


@pytest.mark.asyncio
async def test_live_event_stream_cookie_error(monkeypatch) -> None:
    from fastapi import BackgroundTasks

    monkeypatch.setattr(
        api, "_ensure_live_search_cookies",
        AsyncMock(side_effect=CodedHTTPException(status_code=440, code="cookie_expired", detail="expired")),
    )
    events = [
        _sse_payload(e) async for e in api._live_event_stream(
            _live_container(), BackgroundTasks(), "t1", "kw", None, None, None, None, [],
            [], "default", "",
        )
    ]
    assert events[-1]["status"] == 440 and events[-1]["code"] == "cookie_expired"
    assert "t1" not in api._live_inflight


@pytest.mark.asyncio
async def test_live_event_stream_lock_timeout(monkeypatch) -> None:
    from fastapi import BackgroundTasks

    monkeypatch.setattr(api, "_ensure_live_search_cookies", AsyncMock(return_value=None))
    monkeypatch.setattr(api, "_LIVE_LOCK_TOTAL_TIMEOUT", 0.0)
    events = [
        _sse_payload(e) async for e in api._live_event_stream(
            _live_container(), BackgroundTasks(), "t1", "kw", None, None, None, None, [],
            [], "default", "",
        )
    ]
    assert events[-1]["stage"] == "error" and events[-1]["status"] == 503


@pytest.mark.asyncio
async def test_live_event_stream_lock_wait_progress(monkeypatch) -> None:
    import asyncio
    from fastapi import BackgroundTasks

    monkeypatch.setattr(api, "_ensure_live_search_cookies", AsyncMock(return_value=None))
    lock = MagicMock()
    lock.acquire = AsyncMock(side_effect=[asyncio.TimeoutError, None])
    lock.release = MagicMock()
    container = _live_container(browser_lock=lock)
    container.collector.live_search = AsyncMock(return_value=[])
    events = [
        _sse_payload(e) async for e in api._live_event_stream(
            container, BackgroundTasks(), "t1", "kw", None, None, None, None, [],
            [], "default", "",
        )
    ]
    assert "waiting_lock" in [e["stage"] for e in events]
    lock.release.assert_called_once()


@pytest.mark.asyncio
async def test_live_event_stream_search_error(monkeypatch) -> None:
    from fastapi import BackgroundTasks

    monkeypatch.setattr(api, "_ensure_live_search_cookies", AsyncMock(return_value=None))
    container = _live_container()
    container.collector.live_search = AsyncMock(side_effect=RuntimeError("RGV587"))
    events = [
        _sse_payload(e) async for e in api._live_event_stream(
            container, BackgroundTasks(), "t1", "kw", None, None, None, None, [],
            [], "default", "",
        )
    ]
    assert events[-1]["status"] == 403
    assert container.browser_lock.released == 1
    assert "t1" not in api._live_inflight


@pytest.mark.asyncio
async def test_write_live_items_to_db_logs_and_swallows(monkeypatch) -> None:
    container = _make_container()
    container.repo.batch_upsert_item_task_links.return_value = 2
    await api._write_live_items_to_db(container, "t1", [{"item_id": "1"}])

    container.repo.batch_upsert_item_task_links.side_effect = RuntimeError("db down")
    await api._write_live_items_to_db(container, "t1", [{"item_id": "1"}])


# ============== HTTP 端点 ==============


@pytest.fixture(scope="module")
def app():
    from xianyu_hunter.web.app import create_app

    return create_app()


@pytest.fixture
def client(app, container):
    from xianyu_hunter.config import get_settings

    app.dependency_overrides[api.get_container] = lambda: container
    token = get_settings().web_token
    yield TestClient(app, headers={"Authorization": f"Bearer {token}"})
    app.dependency_overrides.pop(api.get_container, None)


@pytest.fixture
def container() -> SimpleNamespace:
    return _make_container()


def test_list_links_endpoint(client, container) -> None:
    assert client.get("/api/tasks/t1/links?type=bogus").status_code == 400

    container.repo.get_task.return_value = None
    assert client.get("/api/tasks/t1/links").status_code == 404

    container.repo.get_task.return_value = {"id": "t1"}
    container.repo.list_items_by_ids.return_value = []
    container.repo.list_and_count_task_links.return_value = (
        [{"id": 3, "link_type": "item", "link_key": "k", "display": {"title": "t"}}],
        {"item": 1, "total": 1},
    )
    data = client.get("/api/tasks/t1/links?type=item&keyword=iPhone&region=上海&brand=Apple").json()
    assert data["items"][0]["link_id"] == 3
    assert data["total_for_type"] == 1
    kwargs = container.repo.list_and_count_task_links.call_args.kwargs
    assert kwargs["search_keyword"] == "iPhone" and kwargs["sold_filter"] == "all"

    # seller 类型不参与关键词过滤
    data = client.get("/api/tasks/t1/links?type=seller&keyword=iPhone").json()
    assert container.repo.list_and_count_task_links.call_args.kwargs["search_keyword"] is None
    assert data["type"] == "seller"

    # 未指定 type → total 走 counts["total"]
    data = client.get("/api/tasks/t1/links").json()
    assert data["total_for_type"] == 1


def test_count_links_endpoint(client, container) -> None:
    container.repo.get_task.return_value = None
    assert client.get("/api/tasks/t1/links/count").status_code == 404

    container.repo.get_task.return_value = {"id": "t1"}
    container.repo.count_task_links.return_value = {"item": 2, "seller": 1, "total": 3}
    data = client.get("/api/tasks/t1/links/count").json()
    assert data["task_id"] == "t1" and data["total"] == 3


def test_facets_endpoint(client, container) -> None:
    assert client.get("/api/tasks/t1/links/facets?type=bogus").status_code == 400

    container.repo.get_task.return_value = None
    assert client.get("/api/tasks/t1/links/facets").status_code == 404

    container.repo.get_task.return_value = {"id": "t1"}
    data = client.get("/api/tasks/t1/links/facets?type=seller").json()
    assert data["regions"] == [] and data["brands"] == []

    container.repo.list_task_link_facets.return_value = {"regions": ["上海"], "brands": ["Apple"]}
    data = client.get("/api/tasks/t1/links/facets?keyword=iPhone&sold_filter=onsale").json()
    assert data["regions"] == ["上海"] and data["brands"] == ["Apple"]
    assert container.repo.list_task_link_facets.call_args.kwargs["sold_filter"] == "onsale"


def test_create_link_endpoint(client, container) -> None:
    assert client.post("/api/tasks/t1/links", json={"link_type": "x", "link_key": "k"}).status_code == 400
    assert client.post(
        "/api/tasks/t1/links", json={"link_type": "item", "link_key": "k", "source": "x"},
    ).status_code == 400

    container.repo.get_task.return_value = None
    assert client.post("/api/tasks/t1/links", json={"link_type": "item", "link_key": "k"}).status_code == 404

    container.repo.get_task.return_value = {"id": "t1"}
    container.repo.upsert_task_link.return_value = 9
    resp = client.post("/api/tasks/t1/links", json={"link_type": "item", "link_key": "k"})
    assert resp.status_code == 201 and resp.json() == {"ok": True, "id": 9, "task_id": "t1"}


def test_delete_link_endpoint(client, container, monkeypatch) -> None:
    from xianyu_hunter.web.routes import api_tasks

    monkeypatch.setattr(api_tasks, "_check_task_ownership", lambda *a, **k: None)

    container.repo.get_task_link.return_value = None
    assert client.delete("/api/tasks/t1/links/1").status_code == 404

    container.repo.get_task_link.return_value = {"task_id": "other", "link_type": "item", "link_key": "k"}
    assert client.delete("/api/tasks/t1/links/1").status_code == 404

    container.repo.get_task_link.return_value = {"task_id": "t1", "link_type": "seller", "link_key": "s"}
    container.repo.delete_task_link.return_value = True
    data = client.delete("/api/tasks/t1/links/1").json()
    assert data["deleted_events"] == 0 and data["deleted_evaluations"] == 0

    container.repo.get_task_link.return_value = {"task_id": "t1", "link_type": "item", "link_key": "k"}
    container.repo.delete_eval_events_by_task_item.return_value = 2
    container.repo.delete_evaluation_by_item.return_value = 1
    data = client.delete("/api/tasks/t1/links/1").json()
    assert (data["deleted_events"], data["deleted_evaluations"]) == (2, 1)

    container.repo.delete_task_link.return_value = False
    assert client.delete("/api/tasks/t1/links/1").status_code == 404


def test_refresh_links_endpoint(client, container, monkeypatch) -> None:
    container.repo.get_task.return_value = None
    assert client.post("/api/tasks/t1/links/refresh").status_code == 404

    container.repo.get_task.return_value = {"id": "t1", "keyword": "iPhone"}
    assert client.post("/api/tasks/t1/links/refresh").status_code == 503

    container.collector = MagicMock()
    assert client.post("/api/tasks/t1/links/refresh").status_code == 503

    container.browser = _Browser()
    monkeypatch.setattr(api, "_ensure_live_search_cookies", AsyncMock(return_value=None))
    container.repo.get_task.return_value = {"id": "t1", "keyword": ""}
    assert client.post("/api/tasks/t1/links/refresh").status_code == 400

    container.repo.get_task.return_value = {"id": "t1", "keyword": "iPhone", "search_filters": ["x"]}
    container.collector.search = AsyncMock(return_value=[])
    container.repo.count_task_links.return_value = {"item": 0}
    data = client.post("/api/tasks/t1/links/refresh").json()
    assert data["ok"] is True and data["found"] == 0
    container.repo.delete_task_links_by_task.assert_called_once_with("t1", source="auto")


def test_live_links_endpoint(client, container, monkeypatch) -> None:
    container.repo.get_task.return_value = None
    assert client.get("/api/tasks/t1/links/live").status_code == 404

    container.repo.get_task.return_value = {"id": "t1", "keyword": "iPhone"}
    assert client.get("/api/tasks/t1/links/live").status_code == 503

    container.collector = _collector()
    assert client.get("/api/tasks/t1/links/live").status_code == 503

    container.browser = _Browser()
    container.repo.get_task.return_value = {"id": "t1", "keyword": ""}
    assert client.get("/api/tasks/t1/links/live").status_code == 400

    monkeypatch.setattr(api, "_ensure_live_search_cookies", AsyncMock(return_value=None))
    container.repo.get_task.return_value = {"id": "t1", "keyword": "iPhone"}
    resp = client.get("/api/tasks/t1/links/live")
    assert resp.status_code == 200 and resp.headers["content-type"].startswith("text/event-stream")
    assert "checking_cache" in resp.text and "done" in resp.text


def test_lookup_endpoint(client, container) -> None:
    assert client.get("/api/tasks/links/lookup?type=url&key=k").status_code == 400

    container.repo.lookup_task_links.return_value = [{"task_id": "t1"}]
    data = client.get("/api/tasks/links/lookup?type=item&key=k").json()
    assert data["count"] == 1 and data["key"] == "k"


def test_search_endpoint(client, container, monkeypatch) -> None:
    assert client.get("/api/tasks/links/search?q=x&type=url").status_code == 400

    class _FakeService:
        def __init__(self, repo):
            self.repo = repo

        def search(self, params):
            return {"items": [{"task_id": "t1"}]}

    monkeypatch.setattr(api, "TaskLinkSearchService", _FakeService)
    data = client.get("/api/tasks/links/search?q=iphone").json()
    assert data == {"items": [{"task_id": "t1"}], "count": 1, "q": "iphone", "type": None}


def test_auto_migrate_endpoint(client, container) -> None:
    container.repo.auto_migrate_task_links.return_value = 5
    assert client.post("/api/tasks/links/auto-migrate").json() == {"ok": True, "inserted": 5}
