"""批次 3 覆盖率用例：collector/_detail.py 纯解析函数与低依赖方法

只覆盖不需要真实浏览器的表面：模块级纯函数、DetailMixin 的同步校验方法、
以及用 AsyncMock Page 即可驱动的字段提取器。

隔离要求（_detail.py 的副作用）：
- 模块级可变集合 _DUMPED_SELLER_IDS / _DUMPED_ITEM_IDS 每例前后清空
- Path("logs") 相对写入：autouse fixture chdir 到 tmp_path，dump 文件不落仓库
- 项目用 loguru，caplog 默认取不到，需桥接 sink
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from loguru import logger as loguru_logger
from playwright.async_api import TimeoutError as PlaywrightTimeout

from xianyu_hunter.domain.item import ItemDetail, ItemSummary
from xianyu_hunter.infra.selectors import SelectorRepo
from xianyu_hunter.modules.collector import Collector
from xianyu_hunter.modules.collector import _detail as dm

S = SelectorRepo
_ITEM_URL = "https://www.goofish.com/item?id=1"


@pytest.fixture(autouse=True)
def _isolate_globals(tmp_path, monkeypatch):
    """清空模块级 dump 去重集合，并把相对 logs/ 写入重定向到 tmp_path"""
    dm._DUMPED_SELLER_IDS.clear()
    dm._DUMPED_ITEM_IDS.clear()
    monkeypatch.chdir(tmp_path)
    yield
    dm._DUMPED_SELLER_IDS.clear()
    dm._DUMPED_ITEM_IDS.clear()


@pytest.fixture
def caplog_warning(caplog: pytest.LogCaptureFixture):
    """把 loguru INFO+ 桥接到标准 logging，使 caplog 可断言"""
    caplog.set_level(logging.INFO)
    bridge = logging.getLogger("detail_cov")

    def _sink(message: Any) -> None:
        lvl = message.record["level"].name
        if lvl == "WARNING":
            bridge.warning(message.record["message"])
        elif lvl in ("ERROR", "EXCEPTION"):
            bridge.error(message.record["message"])
        elif lvl == "INFO":
            bridge.info(message.record["message"])

    sink_id = loguru_logger.add(_sink, level="INFO")
    try:
        yield caplog
    finally:
        loguru_logger.remove(sink_id)


def _collector(browser: Any | None = None) -> Collector:
    b = browser if browser is not None else MagicMock()
    ad = MagicMock()
    ad.throttle = AsyncMock()
    return Collector(browser=b, antidetect=ad, selectors=SelectorRepo)


def _el(text: str = "", **attrs: Any) -> MagicMock:
    el = MagicMock()
    el.inner_text = AsyncMock(return_value=text)
    el.get_attribute = AsyncMock(side_effect=lambda name: attrs.get(name))
    return el


def _page(
    *,
    qs: dict[str, Any] | None = None,
    qsa: dict[str, list[Any]] | None = None,
    evaluated: Any = None,
    url: str = _ITEM_URL,
    title: str = "",
    body: str = "",
    html: str = "<html></html>",
) -> AsyncMock:
    page = AsyncMock()
    page.url = url
    qs = qs or {}
    qsa = qsa or {}
    page.query_selector = AsyncMock(side_effect=lambda sel: qs.get(sel))
    page.query_selector_all = AsyncMock(side_effect=lambda sel: qsa.get(sel, []))
    page.evaluate = AsyncMock(return_value=evaluated)
    page.title = AsyncMock(return_value=title)
    page.text_content = AsyncMock(return_value=body)
    page.content = AsyncMock(return_value=html)
    page.wait_for_selector = AsyncMock()
    page.is_closed = MagicMock(return_value=False)
    page.close = AsyncMock()
    return page


# ============ 模块级纯函数：图片 src 判定 ============


def test_is_valid_image_src_variants() -> None:
    assert dm._is_valid_image_src("https://img/a.jpg") is True
    assert dm._is_valid_image_src("") is False
    assert dm._is_valid_image_src("data:image/png;base64,AAA") is False
    for mark in dm._PLACEHOLDER_MARKS:
        assert dm._is_valid_image_src(f"https://img/x-{mark}.png") is False


# ============ 模块级纯函数：卖家标签表驱动解析 ============


@pytest.mark.parametrize(
    "text,field,value",
    [
        ("卖出128件宝贝", "sold_count", 128),
        ("在售9", "on_sale_count", 9),
        ("来闲鱼1024天", "register_days", 1024),
        ("来闲鱼3年", "register_days", 1095),
        ("来闲鱼18个月", "register_days", 540),
        ("好评率99%", "credit_score", 99),
        ("好评率100%", "credit_score", 100),
    ],
)
def test_parse_seller_label_text_matches(text: str, field: str, value: int) -> None:
    assert dm._parse_seller_label_text(text) == (field, value)


def test_parse_seller_label_text_no_match_returns_none() -> None:
    assert dm._parse_seller_label_text("浙江 杭州") is None
    # 已知口径：好评率正则不容忍标签与数字之间的空格，此类文案不会被解析
    assert dm._parse_seller_label_text("好评率 98") is None


# ============ 模块级纯函数：tab 计数 ============


def test_parse_single_tab_count_branches() -> None:
    assert dm._parse_single_tab_count("在售9", "在售", 0) == 9
    # 前缀不匹配保持原值
    assert dm._parse_single_tab_count("全部351", "在售", 7) == 7
    # 前缀匹配但无数字保持原值
    assert dm._parse_single_tab_count("在售", "在售", 7) == 7


def test_parse_sold_tab_count_branches() -> None:
    assert dm._parse_sold_tab_count("已售出342", 0) == 342
    assert dm._parse_sold_tab_count("已售5", 0) == 5
    assert dm._parse_sold_tab_count("信用及评价88", 3) == 3
    assert dm._parse_sold_tab_count("已售罄", 3) == 3


# ============ 模块级纯函数：相对发布时间 ============


_NOW = datetime(2026, 10, 30, 15, 0, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("刚刚", _NOW),
        ("30秒前", _NOW - timedelta(seconds=30)),
        ("15分钟前", _NOW - timedelta(minutes=15)),
        ("6小时前", _NOW - timedelta(hours=6)),
        ("3天前", _NOW - timedelta(days=3)),
        ("2周前", _NOW - timedelta(weeks=2)),
        ("4个月前", _NOW - timedelta(days=120)),
        ("4月前", _NOW - timedelta(days=120)),
        ("2年前", _NOW - timedelta(days=730)),
    ],
)
def test_parse_relative_publish_time_offsets(text: str, expected: datetime) -> None:
    assert dm._parse_relative_publish_time(text, _NOW) == expected


def test_parse_relative_publish_time_today_and_yesterday() -> None:
    got = dm._parse_relative_publish_time("今天 09:30", _NOW)
    assert got == _NOW.replace(hour=9, minute=30, second=0, microsecond=0)
    got = dm._parse_relative_publish_time("昨天 23:05", _NOW)
    assert got == (_NOW.replace(hour=23, minute=5, second=0, microsecond=0)
                   - timedelta(days=1))


def test_parse_relative_publish_time_unmatched_returns_none() -> None:
    assert dm._parse_relative_publish_time("2026-10-01", _NOW) is None


# ============ 模块级纯函数：绝对发布时间 ============


def test_parse_absolute_publish_time_formats() -> None:
    assert dm._parse_absolute_publish_time("2026-10-01 08:30") == datetime(
        2026, 10, 1, 8, 30, tzinfo=timezone.utc
    )
    assert dm._parse_absolute_publish_time("2026/10/01 08:30:45") == datetime(
        2026, 10, 1, 8, 30, 45, tzinfo=timezone.utc
    )
    assert dm._parse_absolute_publish_time("发布于 2026-09-30") == datetime(
        2026, 9, 30, tzinfo=timezone.utc
    )


def test_parse_absolute_publish_time_out_of_range_returns_none() -> None:
    # 两种格式都命中越界日期 → 两处 ValueError 分支都被走过，最终 None
    assert dm._parse_absolute_publish_time("2026-13-45 99:99") is None
    assert dm._parse_absolute_publish_time("2026-02-30") is None
    assert dm._parse_absolute_publish_time("刚刚") is None


# ============ _parse_publish_time 编排 ============


def test_parse_publish_time_dispatches_relative_and_absolute() -> None:
    relative = dm.DetailMixin._parse_publish_time("3天前")
    assert relative is not None and relative.tzinfo is not None
    assert abs((relative - (datetime.now(timezone.utc) - timedelta(days=3))).total_seconds()) < 5
    assert dm.DetailMixin._parse_publish_time("2020-05-06 12:00") == datetime(
        2020, 5, 6, 12, 0, tzinfo=timezone.utc
    )


def test_parse_publish_time_empty_inputs_return_none() -> None:
    assert dm.DetailMixin._parse_publish_time("") is None
    assert dm.DetailMixin._parse_publish_time("   ") is None
    assert dm.DetailMixin._parse_publish_time("无时间信息") is None


# ============ _parse_register_days ============


def test_parse_register_days_formats() -> None:
    assert dm.DetailMixin._parse_register_days("注册1234天") == 1234
    assert dm.DetailMixin._parse_register_days("3年前注册") == 1095
    assert dm.DetailMixin._parse_register_days("2个月前") == 60
    # 纯数字兜底
    assert dm.DetailMixin._parse_register_days("NO.58") == 58
    assert dm.DetailMixin._parse_register_days("未知") == 0


def test_parse_register_days_from_date_string() -> None:
    got = dm.DetailMixin._parse_register_days("2020-01-01注册")
    expected = max(0, (datetime.now() - datetime(2020, 1, 1)).days)
    assert got == expected


def test_parse_register_days_invalid_date_falls_back_to_digits() -> None:
    # 越界日期触发 ValueError，随后落入「纯数字」兜底取到 2026
    assert dm.DetailMixin._parse_register_days("2026-13-45") == 2026


# ============ _extract_count ============


async def test_extract_count_strips_commas_and_handles_failures() -> None:
    page = _page(qs={S.DETAIL_WANT_MAIN: _el(text=" 1,472 浏览")})
    assert await dm.DetailMixin._extract_count(page, S.DETAIL_WANT_MAIN) == 1472
    # 元素不存在 / 无数字 / 异常 三种情况都是 0
    assert await dm.DetailMixin._extract_count(page, "no-such") == 0
    assert await dm.DetailMixin._extract_count(_page(qs={"x": _el("无数字")}), "x") == 0
    boom = AsyncMock()
    boom.query_selector = AsyncMock(side_effect=RuntimeError("closed"))
    assert await dm.DetailMixin._extract_count(boom, "x") == 0


# ============ 会话失效标记 & HTTP 状态守卫 ============


def test_mark_detail_session_invalid_logs_warning_only_once(caplog_warning) -> None:
    c = _collector()
    assert c.last_session_invalid is False
    c._mark_detail_session_invalid("i1", "首页标题")
    assert c.last_session_invalid is True
    c._mark_detail_session_invalid("i1", "首页标题")
    msgs = [r.message for r in caplog_warning.records if "会话失效" in r.message]
    assert len(msgs) == 1


def test_check_detail_http_status_branches(caplog_warning) -> None:
    c = _collector()
    assert c._check_detail_http_status("i", None) is False
    ok = MagicMock()
    ok.status = 200
    assert c._check_detail_http_status("i", ok) is False
    bad = MagicMock()
    bad.status = 404
    assert c._check_detail_http_status("i", bad) is True
    assert c.last_detail_failure_reason == "http_status_error"
    redirect = MagicMock()
    redirect.status = 302
    redirect.headers = {"location": "https://example.com/login"}
    assert c._check_detail_http_status("i", redirect) is True
    assert any("HTTP 302" in r.message and "/login" in r.message for r in caplog_warning.records)


# ============ 渲染信号等待 ============


async def test_wait_for_detail_render_signal_returns_json_value() -> None:
    c = _collector()
    signal = MagicMock(json_value=AsyncMock(return_value="price"))
    page = AsyncMock()
    page.wait_for_function = AsyncMock(return_value=signal)
    assert await c._wait_for_detail_render_signal(page, 100) == "price"


async def test_wait_render_signal_with_timeout_falls_back_on_timeout() -> None:
    c = _collector()
    ok_page = AsyncMock()
    ok_page.wait_for_function = AsyncMock(
        return_value=MagicMock(json_value=AsyncMock(return_value="title"))
    )
    assert await c._wait_render_signal_with_timeout(ok_page, "i") == "title"
    slow = AsyncMock()
    slow.wait_for_function = AsyncMock(side_effect=PlaywrightTimeout("Timeout 2500ms exceeded"))
    assert await c._wait_render_signal_with_timeout(slow, "i") == "timeout"


# ============ 标题三层兜底 ============


async def test_extract_detail_title_from_dom_selector() -> None:
    c = _collector()
    page = _page(qs={S.DETAIL_TITLE_ALT: _el(text="  二手显卡  ")})
    assert await c._extract_detail_title(page, "i") == "二手显卡"


async def test_extract_detail_title_falls_back_to_og_and_doc() -> None:
    c = _collector()
    og_page = _page(qs={"meta[property='og:title']": _el(content=" og 标题 ")})
    assert await c._extract_detail_title(og_page, "i") == "og 标题"
    doc_page = _page(title="商品名 - 闲鱼")
    assert await c._extract_detail_title(doc_page, "i") == "商品名"
    for doc, expect in (("商品名_闲鱼", "商品名"), ("商品名 | 闲鱼", "商品名"), ("无后缀", "无后缀")):
        assert await c._extract_detail_title(_page(title=doc), "i") == expect
    assert await c._extract_detail_title(_page(title=""), "i") == ""


async def test_extract_title_helpers_swallow_errors() -> None:
    c = _collector()
    boom = AsyncMock()
    boom.query_selector = AsyncMock(side_effect=RuntimeError("nav"))
    assert await c._extract_title_from_og(boom, "i") == ""
    boom.title = AsyncMock(side_effect=RuntimeError("nav"))
    assert await c._extract_title_from_doc_title(boom, "i") == ""


# ============ 首页标题 / 登录验证重定向守卫 ============


def test_is_home_page_title_early_branches(caplog_warning) -> None:
    c = _collector()
    assert c._is_home_page_title_early("i", "") is False
    assert c._is_home_page_title_early("i", "二手笔记本") is False
    assert c._is_home_page_title_early("i", "闲鱼 - 闲不住？上闲鱼！") is True
    assert c.last_detail_failure_reason == "home_title_redirect"
    assert c.last_session_invalid is True


def test_is_home_page_title_late_marks_session_invalid(caplog_warning) -> None:
    c = _collector()
    assert c._is_home_page_title_late("i", "二手笔记本") is False
    assert c._is_home_page_title_late("i", "闲不住？上闲鱼") is True
    assert c.last_detail_failure_reason == "home_title_redirect"
    assert c.last_session_invalid is True


def test_is_login_or_verify_redirect_branches(caplog_warning) -> None:
    c = _collector()
    login = _page(url="https://passport.goofish.com/mini_login.htm")
    assert c._is_login_or_verify_redirect(login, "i") is True
    assert c.last_detail_failure_reason == "login_redirect"
    verify = _page(url="https://www.goofish.com/new_verify_code.htm")
    assert c._is_login_or_verify_redirect(verify, "i") is True
    assert c.last_detail_failure_reason == "verify_redirect"
    assert c._is_login_or_verify_redirect(_page(url=_ITEM_URL), "i") is False
    # page.url 不可读时静默返回 False
    assert c._is_login_or_verify_redirect(object(), "i") is False


def test_is_redirected_away_from_item_branches(caplog_warning) -> None:
    c = _collector()
    assert c._is_redirected_away_from_item(_page(url="https://www.goofish.com/"), "1") is True
    assert c.last_detail_failure_reason == "redirected_away_from_item"
    assert c._is_redirected_away_from_item(_page(url="https://www.goofish.com/item?id=2"), "1") is True
    assert c._is_redirected_away_from_item(_page(url=_ITEM_URL), "1") is False
    assert c._is_redirected_away_from_item(object(), "1") is False


# ============ 价格 / 描述 / 图片 / 地区 / 想要数 ============


async def test_extract_detail_price_breaks_on_first_hit() -> None:
    c = _collector()
    page = _page(qs={S.DETAIL_PRICE_MAIN: _el(text="¥1999")})
    assert await c._extract_detail_price(page, "i") == 1999.0
    empty = _page()
    assert await c._extract_detail_price(empty, "i") == 0.0


async def test_extract_detail_description_and_region() -> None:
    c = _collector()
    page = _page(
        qs={
            S.DETAIL_DESC_ALT: _el(text="九成新"),
            S.DETAIL_REGION_MAIN: _el(text="浙江\n 杭州  "),
        }
    )
    assert await c._extract_detail_description(page) == "九成新"
    assert await c._extract_detail_description(_page()) == ""
    assert await c._extract_detail_region(page) == "浙江 杭州"
    assert await c._extract_detail_region(_page()) == ""


async def test_resolve_img_src_handles_lazy_attributes() -> None:
    plain = _el(src="https://img/a.jpg")
    assert await dm.DetailMixin._resolve_img_src(plain) == "https://img/a.jpg"
    lazy = _el(src="data:image/png;base64", **{"data-src": "https://img/b.jpg"})
    assert await dm.DetailMixin._resolve_img_src(lazy) == "https://img/b.jpg"
    assert await dm.DetailMixin._resolve_img_src(_el()) == ""


async def test_extract_detail_images_deduces_and_caps() -> None:
    c = _collector()
    els = [_el(src=f"https://img/{i}.jpg") for i in range(12)]
    els.append(_el(src="data:image/png;base64"))
    els.append(els[0])
    page = _page(qsa={S.DETAIL_IMAGES_MAIN: els})
    images = await c._extract_detail_images(page)
    assert len(images) == 10
    assert images[0] == "https://img/0.jpg"
    assert await c._extract_detail_images(_page()) == []


async def test_extract_detail_thumb_url_paths() -> None:
    c = _collector()
    page = _page(qs={S.DETAIL_THUMB_MAIN: _el(src=" https://img/main.jpg ")})
    assert await c._extract_detail_thumb_url(page, []) == "https://img/main.jpg"
    placeholder = _page(qs={S.DETAIL_THUMB_MAIN: _el(src="https://x/1x1.png")})
    assert await c._extract_detail_thumb_url(placeholder, ["https://img/fallback.jpg"]) == (
        "https://img/fallback.jpg"
    )
    assert await c._extract_detail_thumb_url(_page(), []) == ""


async def test_extract_detail_want_view_counts_paths() -> None:
    c = _collector()
    parent = _page(qs={"[class*='want--']": _el(text="45人想要\n1472浏览")})
    assert await c._extract_want_view_from_parent(parent, "i") == (45, 1472)
    assert await c._extract_detail_want_view_counts(parent, "i") == (45, 1472)
    # 父元素不存在 → 走单选择器兜底
    assert await c._extract_want_view_from_parent(_page(), "i") == (0, 0)
    fallback = _page(qs={S.DETAIL_WANT_ALT: _el(text="88人想要"), S.DETAIL_VIEW_ALT: _el(text="9 浏览")})
    assert await c._extract_detail_want_view_counts(fallback, "i") == (88, 9)
    assert await c._extract_detail_want_view_counts(_page(), "i") == (0, 0)
    boom = AsyncMock()
    boom.query_selector = AsyncMock(side_effect=RuntimeError("nav"))
    assert await c._extract_want_view_from_parent(boom, "i") == (0, 0)


# ============ 发布时间提取 ============


async def test_extract_detail_publish_time_uses_parser_or_now() -> None:
    c = _collector()
    page = _page(qs={S.DETAIL_PUBLISH_TIME_MAIN: _el(text="2020-05-06 12:00")})
    assert await c._extract_detail_publish_time(page) == datetime(2020, 5, 6, 12, 0, tzinfo=timezone.utc)
    before = datetime.now(timezone.utc)
    junk = _page(qs={S.DETAIL_PUBLISH_TIME_MAIN: _el(text="无"), S.DETAIL_PUBLISH_TIME_ALT: _el(text="  ")})
    assert (await c._extract_detail_publish_time(junk)) >= before
    assert (await c._extract_detail_publish_time(_page())) >= before


# ============ 卖家 ID / 昵称 / 标签 ============


async def test_extract_detail_seller_id_href_formats() -> None:
    c = _collector()
    slash = _page(qs={S.DETAIL_SELLER_LINK: _el(href="https://www.goofish.com/user/12345")})
    assert await c._extract_detail_seller_id(slash, "1", _ITEM_URL) == "12345"
    param = _page(qs={S.DETAIL_SELLER_LINK_ALT1: _el(href="//www.goofish.com?userId=999")})
    assert await c._extract_detail_seller_id(param, "1", _ITEM_URL) == "999"


async def test_extract_detail_seller_id_dumps_candidates(tmp_path, caplog_warning) -> None:
    c = _collector()
    page = _page(
        evaluated=[{"href": "/user/link", "cls": "x", "text": "进店"}],
        title="二手笔记本",
    )
    assert await c._extract_detail_seller_id(page, "dump1", _ITEM_URL) == ""
    dump = tmp_path / "logs" / "detail_dom_dump1.json"
    assert dump.exists()
    assert "dump1" in dm._DUMPED_ITEM_IDS
    # 同一 item 第二次不再 dump（去重集合生效）
    calls_before = page.evaluate.await_count
    assert await c._extract_detail_seller_id(page, "dump1", _ITEM_URL) == ""
    assert page.evaluate.await_count == calls_before


async def test_dump_seller_id_candidates_adds_body_preview() -> None:
    c = _collector()
    page = _page(evaluated=[])
    page.evaluate = AsyncMock(side_effect=[[], "页面空白"])
    await c._dump_seller_id_candidates(page, "empty1", _ITEM_URL)
    payload = (Path("logs") / "detail_dom_empty1.json").read_text(encoding="utf-8")
    assert "body_text_preview" in payload and "页面空白" in payload


async def test_dump_seller_id_candidates_reports_failure(caplog_warning) -> None:
    c = _collector()
    boom = AsyncMock()
    boom.evaluate = AsyncMock(side_effect=RuntimeError("context destroyed"))
    await c._dump_seller_id_candidates(boom, "boom1", _ITEM_URL)
    assert not (Path("logs") / "detail_dom_boom1.json").exists()


async def test_extract_detail_seller_info_and_name() -> None:
    c = _collector()
    page = _page(
        qs={S.DETAIL_SELLER_NAME: _el(text=" 数码小铺 ")},
        qsa={
            S.DETAIL_REGION_MAIN: [
                _el(text="卖出128件宝贝"),
                _el(text=""),
                _el(text="浙江 杭州"),
            ]
        },
    )
    info = await c._extract_detail_seller_info(page, "i")
    assert info["nick"] == "数码小铺"
    assert info["sold_count"] == 128
    assert info["on_sale_count"] == 0


async def test_populate_seller_info_labels_survives_timeout(caplog_warning) -> None:
    c = _collector()
    page = _page(qsa={S.DETAIL_REGION_MAIN: [_el(text="来闲鱼3年"), _el(text="好评率99%")]})
    page.wait_for_selector = AsyncMock(side_effect=PlaywrightTimeout("Timeout 5000ms exceeded"))
    info = {"nick": "", "credit_score": None, "on_sale_count": 0, "sold_count": 0, "register_days": 0}
    await c._populate_seller_info_labels(page, "i", info)
    assert info["register_days"] == 1095 and info["credit_score"] == 99
    assert any("卖家信息标签未出现" in r.message for r in caplog_warning.records)


async def test_populate_seller_info_labels_reports_outer_exception(caplog_warning) -> None:
    c = _collector()
    boom = AsyncMock()
    boom.wait_for_selector = AsyncMock()
    boom.query_selector_all = AsyncMock(side_effect=RuntimeError("nav"))
    info = {"nick": "", "credit_score": None, "on_sale_count": 0, "sold_count": 0, "register_days": 0}
    await c._populate_seller_info_labels(boom, "i", info)
    assert any("卖家信息标签提取异常" in r.message for r in caplog_warning.records)


async def test_extract_detail_seller_name_swallows_errors() -> None:
    c = _collector()
    boom = AsyncMock()
    boom.query_selector = AsyncMock(side_effect=RuntimeError("nav"))
    assert await c._extract_detail_seller_name(boom) == ""
    assert await c._extract_detail_seller_name(_page()) == ""


# ============ 下架检测 / 已售检测 / 品牌 ============


async def test_early_and_second_delisted_detection(tmp_path) -> None:
    c = _collector()
    page = _page(body="糟糕！宝贝被删掉了")
    early = await c._early_detect_delisted(page, "d1")
    assert early is not None and early.id == "d1" and early.is_sold is True
    second = await c._second_detect_delisted(page, "d2")
    assert second is not None and second.price == 0.0
    assert await c._early_detect_delisted(_page(body="正常商品"), "d3") is None
    assert await c._second_detect_delisted(_page(body="正常商品"), "d4") is None
    boom = AsyncMock()
    boom.text_content = AsyncMock(side_effect=RuntimeError("nav"))
    assert await c._early_detect_delisted(boom, "d5") is None
    assert await c._second_detect_delisted(boom, "d6") is None


async def test_detect_detail_is_sold(tmp_path) -> None:
    c = _collector()
    assert await c._detect_detail_is_sold(_page(body="卖家已卖掉了"), "i") is True
    assert await c._detect_detail_is_sold(_page(body="全新未拆封"), "i") is False
    boom = AsyncMock()
    boom.text_content = AsyncMock(side_effect=RuntimeError("crash"))
    assert await c._detect_detail_is_sold(boom, "i") is False


def test_extract_detail_brand_prefers_title_then_description() -> None:
    c = _collector()
    assert c._extract_detail_brand("金士顿 16G 内存条", "", "") == "金士顿"
    assert c._extract_detail_brand("内存条 16G", "全新 金士顿 正品保障", "") == "金士顿"
    assert c._extract_detail_brand("内存条", "", "") == ""


# ============ 标题提取失败处理 ============


async def test_handle_title_extraction_failure_branches(caplog_warning) -> None:
    c = _collector()
    await c._handle_title_extraction_failure(_page(url="https://passport.goofish.com/login"), "t1")
    await c._handle_title_extraction_failure(_page(url="https://www.goofish.com/captcha"), "t2")
    await c._handle_title_extraction_failure(_page(url=_ITEM_URL, html="<h1>x</h1>"), "t3")
    msgs = [r.message for r in caplog_warning.records]
    assert any("重新登录" in m for m in msgs)
    assert any("验证码" in m for m in msgs)
    assert any("标题提取失败" in m for m in msgs)
    assert (Path("logs") / "detail_html_t3.html").exists()
    assert "t3" in dm._DUMPED_ITEM_IDS


async def test_handle_title_extraction_failure_reports_dump_error(caplog_warning) -> None:
    c = _collector()
    boom = AsyncMock()
    boom.url = _ITEM_URL
    boom.content = AsyncMock(side_effect=RuntimeError("page closed"))
    await c._handle_title_extraction_failure(boom, "t4")
    assert any("dump HTML 失败" in r.message for r in caplog_warning.records)


# ============ 异常分类与重复日志抑制 ============


def test_handle_detail_exception_classification(caplog_warning) -> None:
    c = _collector()
    c._handle_detail_exception("i", RuntimeError("Target page, context or browser has been closed"))
    assert c.last_detail_failure_reason == "target_closed_exception"
    c._handle_detail_exception("i", RuntimeError("Page.goto: net::ERR_CONNECTION_RESET"))
    assert c.last_detail_failure_reason == "network_transient"
    c._handle_detail_exception("i", RuntimeError("Timeout 30000ms exceeded waiting for selector"))
    assert c.last_detail_failure_reason == "playwright_timeout"
    c._handle_detail_exception("i", ValueError("boom"))
    assert c.last_detail_failure_reason == "unknown_exception"


def test_log_detail_failure_downgrades_after_threshold(caplog_warning) -> None:
    c = _collector()
    c.last_detail_failure_reason = "unknown_exception"
    for _ in range(dm._REPEAT_SUPPRESSION_THRESHOLD):
        c._log_detail_failure("i", "采集详情失败", ValueError("boom"), level="error")
    errors_before = sum(1 for r in caplog_warning.records if r.levelname == "ERROR")
    assert errors_before == dm._REPEAT_SUPPRESSION_THRESHOLD
    for _ in range(2):
        c._log_detail_failure("i", "采集详情失败", ValueError("boom"), level="error")
    assert sum(1 for r in caplog_warning.records if r.levelname == "ERROR") == errors_before
    assert c._detail_fail_counts["unknown_exception"] == dm._REPEAT_SUPPRESSION_THRESHOLD + 2
    c.last_detail_failure_reason = "network_transient"
    c._log_detail_failure("i", "网络瞬时故障", RuntimeError("net::ERR_TIMED_OUT"))
    assert any("采集失败" in r.message and r.levelname == "WARNING" for r in caplog_warning.records)


# ============ 卖家主页字段提取 ============


async def test_extract_seller_nick_with_doc_title_fallback() -> None:
    c = _collector()
    assert await c._extract_seller_nick(_page(qs={S.SELLER_NICK_ALT: _el(text=" 小铺 ")})) == "小铺"
    for doc, expect in (
        ("小铺_闲鱼", "小铺"),
        ("小铺 - 闲鱼", "小铺"),
        ("小铺 | 闲鱼", "小铺"),
        # 已知口径：无「_闲鱼」后缀时不猜测昵称，返回空串
        ("裸标题", ""),
        ("", ""),
    ):
        assert await c._extract_nick_from_doc_title(_page(title=doc)) == expect
    assert await c._extract_seller_nick(_page(title="小铺_闲鱼")) == "小铺"
    boom = AsyncMock()
    boom.title = AsyncMock(side_effect=RuntimeError("nav"))
    assert await c._extract_nick_from_doc_title(boom) == ""


async def test_extract_seller_credit_score() -> None:
    c = _collector()
    page = _page(qs={S.SELLER_CREDIT_MAIN: _el(text="芝麻分 1350 优质")})
    assert await c._extract_seller_credit_score(page) == 1350
    assert await c._extract_seller_credit_score(_page()) is None
    assert await c._extract_seller_credit_score(_page(qs={S.SELLER_CREDIT_MAIN: _el(text="无分数")})) is None


async def test_extract_seller_sale_counts_from_tabs_and_fallback() -> None:
    c = _collector()
    tabs = _page(evaluated=["全部351", "在售9", "已售出342"])
    assert await c._extract_seller_sale_counts(tabs, "s1") == (9, 342)
    # 新版改版：无「在售」tab 时用「宝贝」tab 近似
    new_look = _page(evaluated=["宝贝12", "信用及评价88"])
    assert await c._extract_seller_sale_counts(new_look, "s2") == (12, 0)
    # tab 失效但旧版选择器可用：拿到计数，因 on_sale>0 不 dump
    legacy = _page(
        qs={S.SELLER_ON_SALE_ALT: _el(text="在售 7"), S.SELLER_SOLD_ALT: _el(text="已售 21")},
        evaluated=[],
    )
    legacy.evaluate = AsyncMock(side_effect=[[], "body"])
    assert await c._extract_seller_sale_counts(legacy, "s3") == (7, 21)
    assert not (Path("logs") / "seller_dom_s3.txt").exists()
    # 全部选择器失效：on_sale=0 → dump 调试文件并登记去重
    dead = _page(evaluated=[])
    dead.evaluate = AsyncMock(side_effect=[[], "卖家主页空白内容"])
    assert await c._extract_seller_sale_counts(dead, "s4") == (0, 0)
    assert (Path("logs") / "seller_dom_s4.txt").read_text(encoding="utf-8") == "卖家主页空白内容"
    assert "s4" in dm._DUMPED_SELLER_IDS


async def test_parse_sale_counts_from_tabs_swallows_errors() -> None:
    c = _collector()
    boom = AsyncMock()
    boom.evaluate = AsyncMock(side_effect=RuntimeError("nav"))
    assert await c._parse_sale_counts_from_tabs(boom) == (0, 0)
    none_page = _page(evaluated=None)
    assert await c._parse_sale_counts_from_tabs(none_page) == (0, 0)


async def test_dump_seller_dom_for_debug_swallows_errors() -> None:
    c = _collector()
    boom = AsyncMock()
    boom.evaluate = AsyncMock(side_effect=RuntimeError("nav"))
    await c._dump_seller_dom_for_debug(boom, "s9", 0, 0)
    assert not (Path("logs") / "seller_dom_s9.txt").exists()
    assert "s9" not in dm._DUMPED_SELLER_IDS


async def test_extract_seller_register_days_and_bad_review() -> None:
    c = _collector()
    page = _page(
        qs={
            S.SELLER_REGISTER_MAIN: _el(text="2020-01-01注册"),
            S.SELLER_BAD_REVIEW_MAIN: _el(text="差评 3"),
        }
    )
    assert await c._extract_seller_register_days(page) > 2000
    assert await c._extract_seller_bad_review(page) == 3
    assert await c._extract_seller_register_days(_page()) == 0
    assert await c._extract_seller_bad_review(_page()) == 0
    boom = AsyncMock()
    boom.query_selector = AsyncMock(side_effect=RuntimeError("nav"))
    assert await c._extract_seller_register_days(boom) == 0
    assert await c._extract_seller_bad_review(boom) == 0


async def test_seller_profile_visits_own_page(monkeypatch, tmp_path) -> None:
    async def _no_sleep(_seconds):  # 跳过懒加载等待
        return None

    monkeypatch.setattr(dm.asyncio, "sleep", _no_sleep)
    page = _page(
        qs={
            S.SELLER_NICK_MAIN: _el(text="小铺"),
            S.SELLER_CREDIT_MAIN: _el(text="信用 1200"),
        },
        evaluated=["在售9", "已售出342"],
    )
    browser = MagicMock()
    browser.new_page = AsyncMock(return_value=page)
    c = _collector(browser)
    profile = await c.seller_profile("s10")
    assert profile is not None
    assert (profile.id, profile.nick, profile.credit_score) == ("s10", "小铺", 1200)
    assert (profile.on_sale_count, profile.sold_count) == (9, 342)
    assert profile.last_visited is not None
    browser.register_external_page.assert_called_once_with(page)
    browser.unregister_external_page.assert_called_once_with(page)
    page.close.assert_awaited_once()


async def test_seller_profile_failure_paths(monkeypatch, caplog_warning) -> None:
    async def _no_sleep(_seconds):
        return None

    monkeypatch.setattr(dm.asyncio, "sleep", _no_sleep)
    no_page = _collector(MagicMock(new_page=AsyncMock(return_value=None)))
    with pytest.raises(RuntimeError, match="new_page 返回 None"):
        await no_page.seller_profile("s")
    c = _collector()
    closed = AsyncMock()
    closed.is_closed = MagicMock(return_value=True)
    assert await c.seller_profile("s", closed) is None
    crashed = _page()
    crashed.goto = AsyncMock(side_effect=RuntimeError("Target closed"))
    assert await c.seller_profile("s", crashed) is None
    assert any("页面被并发关闭" in r.message for r in caplog_warning.records)
    err = _page()
    err.goto = AsyncMock(side_effect=RuntimeError("nav boom"))
    assert await c.seller_profile("s", err) is None


# ============ 降级画像 seller_profile_fallback 及其拆分出的辅助方法 ============


def _summary(**kw: Any) -> ItemSummary:
    base = dict(id="i1", title="t", price=1.0)
    base.update(kw)
    return ItemSummary(**base)


def _detail(**kw: Any) -> ItemDetail:
    base = dict(id="i1", title="t", price=1.0)
    base.update(kw)
    return ItemDetail(**base)


def test_resolve_fallback_cache_key_prefers_detail() -> None:
    c = _collector()
    assert c._resolve_fallback_cache_key(_detail(seller_id="d"), _summary(seller_id="s")) == "d"
    assert c._resolve_fallback_cache_key(None, _summary(seller_id="s")) == "s"
    assert c._resolve_fallback_cache_key(_detail(), _summary()) == ""


def test_merge_seller_info_detail_wins_and_counts_use_max() -> None:
    c = _collector()
    summary = _summary(seller_id="s1", seller_nick="搜索昵称", seller_credit_score=600,
                       seller_on_sale_count=10, seller_sold_count=20)
    detail = _detail(seller_id="d1", detail_seller_nick="详情昵称", detail_credit_score=800,
                     detail_on_sale_count=4, detail_sold_count=35)
    seller_id, nick, credit, on_sale, sold = c._merge_seller_info_from_sources(summary, detail)
    assert (seller_id, nick, credit) == ("d1", "搜索昵称", 800)
    assert (on_sale, sold) == (10, 35)
    # 仅有 summary / 仅有 detail / 两者皆无
    assert c._merge_seller_info_from_sources(summary, None) == ("s1", "搜索昵称", 600, 10, 20)
    assert c._merge_seller_info_from_sources(None, detail) == ("d1", "详情昵称", 800, 4, 35)
    assert c._merge_seller_info_from_sources(None, None) == ("", "", None, 0, 0)


def test_has_basic_seller_info_and_register_days() -> None:
    c = _collector()
    assert c._has_basic_seller_info(None, 0, 0, "") is False
    assert c._has_basic_seller_info(0, 0, 0, "nick") is True
    assert c._has_basic_seller_info(600, 0, 0, "") is True
    assert c._has_basic_seller_info(None, 3, 0, "") is True
    assert c._has_basic_seller_info(None, 0, 5, "") is True
    assert c._get_fallback_register_days(_detail(detail_register_days=42)) == 42
    assert c._get_fallback_register_days(_detail()) == 0
    assert c._get_fallback_register_days(None) == 0


def test_seller_profile_fallback_builds_and_caches(caplog_warning) -> None:
    c = _collector()
    detail = _detail(seller_id="d1", detail_seller_nick="小铺", detail_credit_score=800,
                     detail_sold_count=12, detail_register_days=365)
    first = c.seller_profile_fallback(_summary(), detail)
    assert (first.id, first.nick, first.credit_score) == ("d1", "小铺", 800)
    assert (first.sold_count, first.register_days) == (12, 365)
    assert c._seller_profile_cache["d1"] is first
    # 第二次命中缓存：即使换了 detail 也返回同一对象
    second = c.seller_profile_fallback(None, _detail(seller_id="d1", detail_credit_score=10))
    assert second is first
    infos = [r.message for r in caplog_warning.records if "SellerProfile降级" in r.message]
    assert any("seller_id=d1" in m and "credit=800" in m and "数据质量=partial" in m for m in infos), infos


def test_seller_profile_fallback_without_seller_id_is_not_cached() -> None:
    c = _collector()
    profile = c.seller_profile_fallback(_summary(title="t"), None)
    assert profile.id == "unknown"
    assert profile.register_days == 0
    assert len(c._seller_profile_cache) == 0
    assert c.clear_seller_profile_cache() == 0


def test_seller_profile_fallback_uses_summary_cache_key() -> None:
    c = _collector()
    profile = c.seller_profile_fallback(_summary(seller_id="s9", seller_on_sale_count=3), None)
    assert profile.id == "s9"
    assert profile.on_sale_count == 3
    assert c._seller_profile_cache["s9"] is profile
    assert c.clear_seller_profile_cache() == 1
    assert len(c._seller_profile_cache) == 0


# ============ detail() 编排：成功路径与各提前返回分支 ============


def _resp(status: int = 200, headers: dict[str, str] | None = None) -> MagicMock:
    r = MagicMock()
    r.status = status
    r.headers = headers or {}
    return r


def _good_detail_page(item_id: str = "777") -> AsyncMock:
    page = _page(
        qs={
            S.DETAIL_TITLE_MAIN: _el(text="金士顿 16G 内存条"),
            S.DETAIL_PRICE_MAIN: _el(text="¥199"),
            S.DETAIL_DESC_MAIN: _el(text="全新未拆封"),
            S.DETAIL_REGION_MAIN: _el(text="浙江 杭州"),
            S.DETAIL_WANT_MAIN: _el(text="45人想要"),
            S.DETAIL_VIEW_MAIN: _el(text="1472浏览"),
            S.DETAIL_PUBLISH_TIME_MAIN: _el(text="2026-10-01 08:30"),
            S.DETAIL_SELLER_LINK: _el(href="https://www.goofish.com/user/5678"),
            S.DETAIL_SELLER_NAME: _el(text="数码小铺"),
            "[class*='want--']": _el(text="45人想要\n1472浏览"),
        },
        qsa={
            S.DETAIL_IMAGES_MAIN: [_el(src="https://img/a.jpg"), _el(src="https://img/b.jpg")],
            S.DETAIL_REGION_MAIN: [_el(text="卖出128件宝贝"), _el(text="来闲鱼3年")],
        },
        url=f"https://www.goofish.com/item?id={item_id}",
        body="全新未拆封",
    )
    page.goto = AsyncMock(return_value=_resp())
    page.wait_for_function = AsyncMock(
        return_value=MagicMock(json_value=AsyncMock(return_value="title"))
    )
    return page


def _collector_with_page(page: AsyncMock) -> Collector:
    browser = MagicMock()
    browser.new_page = AsyncMock(return_value=page)
    return _collector(browser)


async def test_detail_success_path_assembles_item_detail() -> None:
    c = _collector()
    detail = await c.detail("777", _good_detail_page())
    assert detail is not None
    assert (detail.id, detail.title, detail.price) == ("777", "金士顿 16G 内存条", 199.0)
    assert detail.image_urls == ["https://img/a.jpg", "https://img/b.jpg"]
    assert detail.thumb_url == "https://img/a.jpg"
    assert detail.region == "浙江 杭州"
    assert (detail.want_cnt, detail.view_cnt) == (45, 1472)
    assert detail.seller_id == "5678"
    assert detail.brand == "金士顿"
    assert detail.publish_time == datetime(2026, 10, 1, 8, 30, tzinfo=timezone.utc)
    assert detail.detail_seller_nick == "数码小铺"
    assert (detail.detail_sold_count, detail.detail_register_days) == (128, 1095)
    assert detail.is_sold is False
    assert c.last_detail_failure_reason == ""


async def test_detail_marks_is_sold_from_body() -> None:
    page = _good_detail_page()
    page.text_content = AsyncMock(return_value="卖家卖掉了")
    detail = await _collector().detail("777", page)
    assert detail is not None and detail.is_sold is True


async def test_detail_skips_when_session_already_invalid(caplog_warning) -> None:
    c = _collector()
    c.last_session_invalid = True
    browser = MagicMock()
    c.browser = browser
    assert await c.detail("777") is None
    assert c.last_detail_failure_reason == "home_title_redirect"
    browser.new_page.assert_not_called()


async def test_detail_raises_when_new_page_returns_none() -> None:
    browser = MagicMock()
    browser.new_page = AsyncMock(return_value=None)
    c = _collector(browser)
    with pytest.raises(RuntimeError, match="new_page 返回 None"):
        await c.detail("777")


async def test_detail_closes_own_page_even_on_failure() -> None:
    page = _good_detail_page()
    page.is_closed = MagicMock(return_value=True)
    browser = MagicMock()
    browser.new_page = AsyncMock(return_value=page)
    c = _collector(browser)
    assert await c.detail("777") is None
    assert c.last_detail_failure_reason == "page_closed"
    page.close.assert_awaited_once()
    browser.unregister_external_page.assert_called_once_with(page)


async def test_detail_early_returns_on_delisted_and_redirects(caplog_warning) -> None:
    deleted = _good_detail_page()
    deleted.text_content = AsyncMock(return_value="糟糕！宝贝被删掉了")
    got = await _collector().detail("777", deleted)
    assert got is not None and got.is_sold is True and got.title == ""

    home = _good_detail_page()
    home.query_selector = AsyncMock(
        side_effect=lambda sel: _el(text="闲鱼 - 闲不住？上闲鱼！")
        if sel == S.DETAIL_TITLE_MAIN else None
    )
    assert await _collector().detail("777", home) is None
    assert any("首页标题" in r.message for r in caplog_warning.records)

    login = _good_detail_page()
    login.url = "https://passport.goofish.com/mini_login.htm"
    assert await _collector().detail("777", login) is None
    assert any("跳转登录页" in r.message for r in caplog_warning.records)


async def test_detail_second_delisted_and_late_home_title(monkeypatch) -> None:
    page = _good_detail_page()
    page.text_content = AsyncMock(side_effect=["正常商品", "宝贝不存在"])
    c = _collector()
    got = await c.detail("777", page)
    assert got is not None and got.is_sold is True

    late = _collector()
    monkeypatch.setattr(late, "_is_home_page_title_early", lambda item_id, title: False)
    home_page = _good_detail_page()
    home_page.query_selector = AsyncMock(
        side_effect=lambda sel: _el(text="闲不住？上闲鱼") if sel == S.DETAIL_TITLE_MAIN else None
    )
    assert await late.detail("777", home_page) is None
    assert late.last_detail_failure_reason == "home_title_redirect"
    assert late.last_session_invalid is True


async def test_detail_redirected_away_from_item_and_price_failure(caplog_warning) -> None:
    away = _good_detail_page(item_id="999")
    c = _collector()
    assert await c.detail("777", away) is None
    assert c.last_detail_failure_reason == "redirected_away_from_item"

    no_price = _good_detail_page()
    original = no_price.query_selector.side_effect
    no_price.query_selector = AsyncMock(
        side_effect=lambda sel: (
            None if sel in (S.DETAIL_PRICE_MAIN, S.DETAIL_PRICE_ALT) else original(sel)
        )
    )
    c2 = _collector()
    assert await c2.detail("777", no_price) is None
    assert c2.last_detail_failure_reason == "price_extraction_failed"


async def test_detail_wraps_exceptions_via_handler(caplog_warning) -> None:
    page = _good_detail_page()
    page.goto = AsyncMock(side_effect=RuntimeError("Page.goto: net::ERR_TIMED_OUT"))
    c = _collector()
    assert await c.detail("777", page) is None
    assert c.last_detail_failure_reason == "network_transient"
