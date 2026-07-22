"""测试 _detail.py DetailMixin.detail() 的提取失败分支

覆盖场景（对应任务 SubTask 5.1-5.4）：
- HTTP 4xx/5xx → 返回 None + warning
- HTTP 3xx 重定向 → 返回 None + warning（含目标 URL）
- 标题为空（DOM/og:title/document.title 三层兜底全部失败）→ 返回 None + warning
- 价格 ≤ 0 → 返回 None + warning

实现策略：
- 使用 unittest.mock.AsyncMock mock Page（满足任务约束）
- mock self.browser.new_page() 返回 mock page
- mock self.ad.throttle() 为 no-op
- mock self.selectors 使用真实 SelectorRepo 常量
- 不修改 _detail.py 任何代码

日志断言策略：
- 项目用 loguru（非标准 logging），pytest caplog 默认无法捕获 loguru 输出
- 通过 autouse fixture 注册 loguru sink，将 WARNING+ 日志桥接到标准 logging.Logger
- 桥接后 caplog 可正常捕获并断言
"""
from __future__ import annotations

import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from loguru import logger as loguru_logger

from xianyu_hunter.infra.selectors import SelectorRepo
from xianyu_hunter.modules.collector import Collector


@pytest.fixture(autouse=True)
def loguru_to_caplog(caplog: pytest.LogCaptureFixture) -> Any:
    """将 loguru WARNING+ 日志桥接到 caplog

    为什么需要桥接：项目用 loguru 而非标准 logging，
    caplog 默认只能捕获标准 logging 输出。通过 loguru.logger.add 注册
    sink，将日志转发到标准 logging.Logger，使 caplog 能捕获到。
    teardown 时移除 sink 避免影响其他测试。
    """
    caplog.set_level(logging.WARNING)
    bridge_logger = logging.getLogger("xianyu_hunter.detail_test")

    def _sink(message: Any) -> None:
        record = message.record
        level_name = record["level"].name
        # detail 失败路径主要是 warning，error 也一并转发便于诊断
        if level_name == "WARNING":
            bridge_logger.warning(record["message"])
        elif level_name == "ERROR":
            bridge_logger.error(record["message"])

    sink_id = loguru_logger.add(_sink, level="WARNING")
    try:
        yield
    finally:
        loguru_logger.remove(sink_id)


def _make_response(status: int, headers: dict[str, str] | None = None) -> MagicMock:
    """构造 page.goto 返回的 mock response"""
    resp = MagicMock()
    resp.status = status
    resp.headers = headers or {}
    return resp


def _make_text_el(text: str) -> MagicMock:
    """构造 mock ElementHandle，inner_text 返回 text"""
    el = MagicMock()
    el.inner_text = AsyncMock(return_value=text)
    el.get_attribute = AsyncMock(return_value=None)
    return el


def _make_attr_el(attr_value: str | None) -> MagicMock:
    """构造 mock ElementHandle，get_attribute 返回 attr_value"""
    el = MagicMock()
    el.get_attribute = AsyncMock(return_value=attr_value)
    el.inner_text = AsyncMock(return_value="")
    return el


def _make_page(
    *,
    response: MagicMock,
    title_text: str | None = None,
    og_title: str | None = None,
    doc_title: str = "",
    price_text: str | None = None,
    page_url: str = "https://goofish.com/item?id=test_item",
) -> AsyncMock:
    """构造 mock Page，预设 detail() 流程所需的全部 mock 行为

    Args:
        response: page.goto 返回的 mock response
        title_text: DETAIL_TITLE_MAIN/ALT 命中的标题文本；None 表示元素不存在
        og_title: og:title meta 的 content；None 表示元素不存在
        doc_title: page.title() 返回值（document.title 兜底）
        price_text: DETAIL_PRICE_MAIN/ALT 命中的价格文本；None 表示元素不存在
        page_url: page.url 同步属性（URL 校验分支用）
    """
    page = AsyncMock()
    page.goto = AsyncMock(return_value=response)
    # page.url 是同步属性，AsyncMock 默认返回 MagicMock，需显式赋值字符串
    page.url = page_url
    # is_closed 必须返回 False（非协程），否则 detail() 开头防御检查会跳过采集
    page.is_closed = MagicMock(return_value=False)
    page.wait_for_selector = AsyncMock()  # 默认不抛 PlaywrightTimeout
    page.title = AsyncMock(return_value=doc_title)
    page.text_content = AsyncMock(return_value="")
    # content/evaluate 抛异常：跳过 dump 文件写入（避免测试产生 logs/ 副作用文件）
    # _detail.py L272/L379 会捕获 RuntimeError 并 log error，不影响 return None 路径
    page.content = AsyncMock(side_effect=RuntimeError("test: skip dump"))
    page.evaluate = AsyncMock(side_effect=RuntimeError("test: skip dump"))
    page.query_selector_all = AsyncMock(return_value=[])
    page.close = AsyncMock()

    # 提前读取选择器常量，避免在 side_effect 内重复属性访问
    title_main = SelectorRepo.DETAIL_TITLE_MAIN
    title_alt = SelectorRepo.DETAIL_TITLE_ALT
    price_main = SelectorRepo.DETAIL_PRICE_MAIN
    price_alt = SelectorRepo.DETAIL_PRICE_ALT
    og_meta = "meta[property='og:title']"
    want_parent = "[class*='want--']"

    def _qs_side_effect(selector: str) -> Any:
        """根据 selector 字符串返回对应 mock 元素

        为什么用 side_effect 而非 return_value：detail() 会以不同 selector
        多次调用 query_selector，需按 selector 区分返回值。
        """
        # 标题主/备选择器
        if selector == title_main or selector == title_alt:
            return _make_text_el(title_text) if title_text is not None else None
        # og:title meta 兜底
        if selector == og_meta:
            return _make_attr_el(og_title) if og_title is not None else None
        # 价格主/备选择器
        if selector == price_main or selector == price_alt:
            return _make_text_el(price_text) if price_text is not None else None
        # want-- 父元素：返回 None 让 _extract_count 兜底
        if selector == want_parent:
            return None
        # 其余选择器默认返回 None
        return None

    page.query_selector = AsyncMock(side_effect=_qs_side_effect)
    return page


def _make_collector(page: AsyncMock) -> Collector:
    """构造 Collector，注入 mock 依赖

    使用真实 Collector 类（多继承 DetailMixin + CollectorBase），
    CollectorBase.__init__ 仅设置属性，不触发外部 IO。
    """
    browser = MagicMock()
    browser.new_page = AsyncMock(return_value=page)
    ad = MagicMock()
    ad.throttle = AsyncMock()  # no-op
    return Collector(browser=browser, antidetect=ad, selectors=SelectorRepo)


# ============== SubTask 5.1：标题为空时返回 None ==============


async def test_detail_returns_none_when_title_empty(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """标题三层兜底全部失败时返回 None

    覆盖 _detail.py L354-381：
    - DOM 选择器（DETAIL_TITLE_MAIN/ALT）→ None
    - og:title meta → None
    - document.title → ""

    _detail.py 已实现此分支（L354-381），预期 PASS（无需 xfail）。
    """
    response = _make_response(status=200)
    page = _make_page(
        response=response,
        title_text=None,  # DOM 选择器未命中
        og_title=None,    # og:title 不存在
        doc_title="",     # document.title 也为空
    )
    collector = _make_collector(page)

    result = await collector.detail("test_item_title_empty")

    assert result is None
    assert any(
        "标题提取失败" in rec.message for rec in caplog.records
    ), f"应记录标题提取失败的 warning，实际日志: {[r.message for r in caplog.records]}"


# ============== SubTask 5.2：价格 ≤ 0 时返回 None ==============


async def test_detail_returns_none_when_price_zero(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """价格提取为 0 时返回 None

    覆盖 _detail.py L389-392：标题提取成功后，价格仍 ≤ 0 → return None。
    mock 价格元素 inner_text 返回 "0"，parse_price_from_text 解析为 0.0。

    _detail.py 已实现此分支（L389-392），预期 PASS（无需 xfail）。
    """
    response = _make_response(status=200)
    page = _make_page(
        response=response,
        title_text="测试商品标题",  # 标题成功提取，绕过 L354 标题为空分支
        price_text="0",             # 价格为 "0" → parse_price_from_text 返回 0.0
    )
    collector = _make_collector(page)

    result = await collector.detail("test_item_price_zero")

    assert result is None
    assert any(
        "价格提取失败" in rec.message for rec in caplog.records
    ), f"应记录价格提取失败的 warning，实际日志: {[r.message for r in caplog.records]}"


# ============== SubTask 5.3：HTTP 4xx/5xx 时返回 None ==============


async def test_detail_returns_none_on_http_4xx(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """HTTP 4xx 时返回 None + warning

    覆盖 _detail.py L57-61：http_status >= 400 → return None。
    _detail.py 已实现此分支，预期 PASS。
    """
    response = _make_response(status=404)
    page = _make_page(response=response)
    collector = _make_collector(page)

    result = await collector.detail("test_item_404")

    assert result is None
    assert any(
        "HTTP 404" in rec.message for rec in caplog.records
    ), f"应记录 HTTP 404 warning，实际日志: {[r.message for r in caplog.records]}"


async def test_detail_returns_none_on_http_5xx(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """HTTP 5xx 时返回 None + warning

    覆盖 _detail.py L57-61：http_status >= 400 → return None。
    _detail.py 已实现此分支，预期 PASS。
    """
    response = _make_response(status=500)
    page = _make_page(response=response)
    collector = _make_collector(page)

    result = await collector.detail("test_item_500")

    assert result is None
    assert any(
        "HTTP 500" in rec.message for rec in caplog.records
    ), f"应记录 HTTP 500 warning，实际日志: {[r.message for r in caplog.records]}"


# ============== SubTask 5.4：HTTP 3xx 重定向时返回 None ==============


async def test_detail_returns_none_on_http_3xx_redirect(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """HTTP 3xx 重定向时返回 None + warning 含目标 URL

    覆盖 _detail.py L62-67：http_status >= 300 → return None，
    日志含 response.headers['location']（重定向目标 URL）。
    _detail.py 已实现此分支，预期 PASS。
    """
    redirect_url = "https://example.com/login"
    response = _make_response(
        status=302,
        headers={"location": redirect_url},
    )
    page = _make_page(response=response)
    collector = _make_collector(page)

    result = await collector.detail("test_item_302")

    assert result is None
    # 验证日志同时包含"重定向"关键词和目标 URL
    assert any(
        redirect_url in rec.message and "重定向" in rec.message
        for rec in caplog.records
    ), f"应记录含目标 URL 的重定向 warning，实际日志: {[r.message for r in caplog.records]}"


# ============== 网络瞬时故障降级测试 ==============


async def test_handle_detail_exception_network_transient_downgraded_to_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """网络层瞬时故障（ERR_NAME_NOT_RESOLVED 等）应降级为 WARNING 而非 ERROR

    覆盖 _detail.py _handle_detail_exception 的网络异常分支：
    - 异常消息含 ERR_NAME_NOT_RESOLVED → last_detail_failure_reason='network_transient'
    - 日志级别应为 WARNING（而非 ERROR），避免污染告警
    - 日志应含"网络瞬时故障"关键词
    """
    page = _make_page(response=_make_response(status=200))
    collector = _make_collector(page)

    # 模拟 Playwright Page.goto 抛出 DNS 解析失败
    network_error = Exception(
        "Page.goto: net::ERR_NAME_NOT_RESOLVED at https://www.goofish.com/item?id=123"
    )
    collector._handle_detail_exception("test_item_dns_failure", network_error)

    assert collector.last_detail_failure_reason == "network_transient"
    assert any(
        "网络瞬时故障" in rec.message and "WARNING" == rec.levelname
        for rec in caplog.records
    ), f"应记录 WARNING 级网络瞬时故障日志，实际: {[(r.levelname, r.message) for r in caplog.records]}"


async def test_handle_detail_exception_network_changed_downgraded_to_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """ERR_NETWORK_CHANGED 同样应降级为 WARNING"""
    page = _make_page(response=_make_response(status=200))
    collector = _make_collector(page)

    network_error = Exception(
        "Page.goto: net::ERR_NETWORK_CHANGED at https://www.goofish.com/item?id=456"
    )
    collector._handle_detail_exception("test_item_network_changed", network_error)

    assert collector.last_detail_failure_reason == "network_transient"
    assert any(
        "网络瞬时故障" in rec.message for rec in caplog.records
    ), f"应记录网络瞬时故障日志，实际: {[r.message for r in caplog.records]}"


async def test_handle_detail_exception_unknown_still_logs_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """非网络层异常应保留 ERROR 级别 + 完整堆栈

    确保降级逻辑不会误吞真正的业务异常。
    """
    page = _make_page(response=_make_response(status=200))
    collector = _make_collector(page)

    business_error = RuntimeError("selector config missing")
    collector._handle_detail_exception("test_item_business_error", business_error)

    assert collector.last_detail_failure_reason == "unknown_exception"
    assert any(
        "采集详情失败" in rec.message and rec.levelname == "ERROR"
        for rec in caplog.records
    ), f"业务异常应记为 ERROR，实际: {[(r.levelname, r.message) for r in caplog.records]}"
