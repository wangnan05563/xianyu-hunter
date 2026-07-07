"""Collector 单元测试（mock page 模式）"""
from __future__ import annotations

import tempfile
import time
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from xianyu_hunter.modules.collector import Collector
from xianyu_hunter.modules.collector._search import (
    _cookies_from_set_cookie_headers,
    _sync_response_cookies_to_context,
)


class FakeElement:
    """模拟 Playwright ElementHandle"""

    def __init__(self, *, text: str = "", attrs: dict[str, str] | None = None, tag: str = "DIV"):
        self._text = text
        self._attrs = attrs or {}
        self._tag = tag

    async def inner_text(self) -> str:
        return self._text

    async def get_attribute(self, name: str) -> str | None:
        return self._attrs.get(name)

    async def evaluate(self, expression: str) -> str:
        # 支持 el => el.tagName 的简单模拟
        if "tagName" in expression:
            return self._tag
        return ""

    async def query_selector(self, selector: str) -> "FakeElement | None":
        return None


class FakePage:
    """模拟 Playwright Page 的最小子集"""

    def __init__(self):
        self.goto_log: list[str] = []
        self.evaluations: list[str] = []
        self.cards: list[FakeElement] = []
        self.title_el: FakeElement | None = None
        self.price_el: FakeElement | None = None
        self.desc_el: FakeElement | None = None
        self.image_els: list[FakeElement] = []
        self.seller_link_el: FakeElement | None = None
        self.nick_el: FakeElement | None = None
        self.credit_el: FakeElement | None = None
        self.on_sale_el: FakeElement | None = None
        self.sold_el: FakeElement | None = None
        # selector -> element 显式映射
        self.selector_map: dict[str, FakeElement | None] = {}
        self.url = "https://www.goofish.com/"

    async def goto(self, url: str, **kwargs: Any) -> None:
        self.goto_log.append(url)
        self.url = url

    async def evaluate(self, script: str) -> Any:
        self.evaluations.append(script)
        return 0

    def _resolve(self, selector: str) -> FakeElement | None:
        """根据 selector 返回对应元素（显式映射优先）"""
        if selector in self.selector_map:
            return self.selector_map[selector]
        if "search-card" in selector or "SearchCard" in selector or "GoodsCard" in selector or "feeds-item" in selector or "search-item" in selector:
            return self.cards[0] if self.cards else None
        if "title" in selector.lower():
            return self.title_el
        if "price" in selector.lower():
            return self.price_el
        if "desc" in selector.lower() or "description" in selector.lower():
            return self.desc_el
        if "image" in selector.lower() or "Pic" in selector:
            return self.image_els[0] if self.image_els else None
        if "sellerName" in selector or "userNick" in selector:
            return self.nick_el
        if "credit" in selector.lower() or "zhima" in selector.lower():
            return self.credit_el
        if "onSale" in selector:
            return self.on_sale_el
        if "sold" in selector.lower():
            return self.sold_el
        if "userId" in selector:
            return self.seller_link_el
        return None

    async def query_selector(self, selector: str) -> FakeElement | None:
        return self._resolve(selector)

    async def query_selector_all(self, selector: str) -> list[FakeElement]:
        if ("search-card" in selector or "SearchCard" in selector or "GoodsCard" in selector
                or "feeds-item" in selector or "search-item" in selector):
            return self.cards
        if "image" in selector.lower() or "Pic" in selector:
            return self.image_els
        return []

    async def wait_for_selector(self, selector: str, timeout: int = 5000) -> None:
        return None

    async def wait_for_load_state(self, state: str = "load", timeout: int = 5000) -> None:
        return None

    async def close(self) -> None:
        return None


class FakeContext:
    """模拟 Playwright BrowserContext 的 cookie 写入能力"""

    def __init__(self):
        self.added_cookies: list[dict[str, Any]] = []

    async def add_cookies(self, cookies: list[dict[str, Any]]) -> None:
        self.added_cookies.extend(cookies)


class FakeCookiePage:
    """用于测试 route.fetch() 响应 cookie 同步的 Page 子集"""

    def __init__(self):
        self.context = FakeContext()


class FakeApiResponse:
    """模拟 Playwright APIResponse 的响应头接口"""

    url = "https://h5api.m.goofish.com/h5/mtop.taobao.idlemtopsearch.pc.search/1.0/"

    @property
    def headers_array(self) -> list[dict[str, str]]:
        return [
            {
                "name": "set-cookie",
                "value": "_m_h5_tk=token_1700000000000; Domain=.goofish.com; Path=/; Secure; HttpOnly; SameSite=None",
            },
            {
                "name": "set-cookie",
                "value": "_m_h5_tk_enc=enc_value; Domain=.goofish.com; Path=/; Secure",
            },
        ]


class FakeSearchApiResponse:
    """用于测试搜索 API route 拦截的最小响应对象"""

    url = "https://h5api.m.goofish.com/h5/mtop.taobao.idlemtopsearch.pc.search/1.0/"

    def __init__(self, body: dict[str, Any] | None = None):
        self._body = body or {"ret": ["SUCCESS::调用成功"], "data": {}}

    async def json(self) -> dict[str, Any]:
        return self._body


class FakeSearchRoute:
    """用于模拟 Playwright Route"""

    def __init__(self, url: str, response: FakeSearchApiResponse | None = None):
        self.request = MagicMock(url=url)
        self._response = response or FakeSearchApiResponse()
        self.fulfilled = False
        self.continued = False

    async def fetch(self) -> FakeSearchApiResponse:
        return self._response

    async def fulfill(self, **kwargs: Any) -> None:
        self.fulfilled = True

    async def continue_(self) -> None:
        self.continued = True


class FakeSearchApiPage:
    """模拟会发起搜索 API 请求的 Page"""

    def __init__(
        self,
        response: FakeSearchApiResponse | None = None,
        responses: list[FakeSearchApiResponse] | None = None,
    ):
        self.context = FakeContext()
        self.route_calls: list[tuple[str, Any]] = []
        self.unroute_calls: list[tuple[str, Any]] = []
        self.url = "https://www.goofish.com/search"
        self._handler = None
        self._response = response
        self._responses = list(responses or [])
        self.goto_count = 0

    async def route(self, pattern: str, handler: Any) -> None:
        self.route_calls.append((pattern, handler))
        self._handler = handler

    async def unroute(self, pattern: str, handler: Any | None = None) -> None:
        self.unroute_calls.append((pattern, handler))

    async def goto(self, url: str, **kwargs: Any) -> None:
        self.goto_count += 1
        self.url = url
        assert self._handler is not None
        response = self._responses.pop(0) if self._responses else self._response
        route = FakeSearchRoute(
            "https://h5api.m.goofish.com/h5/mtop.taobao.idlemtopsearch.pc.search/1.0/?data=%7B%7D",
            response=response,
        )
        await self._handler(route)

    async def evaluate(self, script: str) -> Any:
        return None


@pytest.fixture
def fake_browser() -> Any:
    """Mock BrowserManager"""
    b = MagicMock()
    b.new_page = AsyncMock(return_value=FakePage())
    return b


@pytest.fixture
def fake_ad() -> Any:
    """Mock AntiDetect"""
    ad = MagicMock()
    ad.throttle = AsyncMock()
    ad.human_delay = AsyncMock(return_value=0.001)
    return ad


# ============== 纯函数测试 ==============


def test_extract_item_id_id_param() -> None:
    """提取 id= 参数"""
    assert Collector._extract_item_id("/item.htm?id=123456") == "123456"


def test_extract_item_id_path() -> None:
    """提取 /item/123 路径"""
    assert Collector._extract_item_id("/item/789012") == "789012"


def test_extract_item_id_itemid_param() -> None:
    """提取 itemId 参数"""
    assert Collector._extract_item_id("/page?itemId=345678") == "345678"


def test_extract_item_id_empty() -> None:
    """空字符串"""
    assert Collector._extract_item_id("") == ""


def test_extract_item_id_no_match() -> None:
    """无 ID 返回空"""
    assert Collector._extract_item_id("/some/random/url") == ""


def test_extract_item_id_userId_distinguished() -> None:
    """不应把 userId 当 itemId"""
    assert Collector._extract_item_id("/user/12345") == ""


def test_parse_mtop_set_cookie_headers_for_browser_context() -> None:
    """MTOP 下发的新 token cookie 应能转换为 Playwright cookie 结构"""
    cookies = _cookies_from_set_cookie_headers(
        [
            "_m_h5_tk=token_1700000000000; Domain=.goofish.com; Path=/; Secure; HttpOnly; SameSite=None",
        ],
        "https://h5api.m.goofish.com/h5/test/1.0/",
    )

    assert cookies == [
        {
            "name": "_m_h5_tk",
            "value": "token_1700000000000",
            "path": "/",
            "domain": ".goofish.com",
            "secure": True,
            "httpOnly": True,
            "sameSite": "None",
        }
    ]


@pytest.mark.asyncio
async def test_search_api_route_uses_narrow_pattern(fake_browser: Any, fake_ad: Any) -> None:
    """搜索 API 拦截不应使用 **/* 全量路由，避免拖慢页面资源和 unroute。"""
    collector = Collector(browser=fake_browser, antidetect=fake_ad)
    page = FakeSearchApiPage()

    items, session_invalid = await collector._call_search_api(page, "DDR4", max_pages=1)

    assert items == []
    assert session_invalid is False
    assert page.route_calls, "应注册 route handler"
    pattern, handler = page.route_calls[0]
    assert pattern != "**/*"
    assert "mtop.taobao.idlemtopsearch.pc.search/1.0" in pattern
    assert page.unroute_calls == [(pattern, handler)]


@pytest.mark.asyncio
async def test_search_api_illegal_access_is_retryable_not_session_invalid(fake_browser: Any, fake_ad: Any) -> None:
    """FAIL_SYS_ILLEGAL_ACCESS 是 MTOP 签名失败，不应直接判定登录失效。"""
    collector = Collector(browser=fake_browser, antidetect=fake_ad)
    collector._last_m5tk_refresh = time.monotonic()
    page = FakeSearchApiPage(
        response=FakeSearchApiResponse({"ret": ["FAIL_SYS_ILLEGAL_ACCESS::非法请求"], "data": {}})
    )

    items, session_invalid = await collector._call_search_api(page, "DDR4", max_pages=1, fast=True)

    assert items == []
    assert session_invalid is False
    assert page.unroute_calls


@pytest.mark.asyncio
async def test_search_api_repeated_illegal_access_sets_backoff(fake_browser: Any, fake_ad: Any) -> None:
    """连续 MTOP 签名失败后应短时间跳过 API，避免每轮重复等待失败。"""
    collector = Collector(browser=fake_browser, antidetect=fake_ad)
    page = FakeSearchApiPage(
        responses=[
            FakeSearchApiResponse({"ret": ["FAIL_SYS_ILLEGAL_ACCESS::非法请求"], "data": {}}),
            FakeSearchApiResponse({"ret": ["FAIL_SYS_ILLEGAL_ACCESS::非法请求"], "data": {}}),
        ]
    )

    items, session_invalid = await collector._call_search_api(page, "DDR4", max_pages=1, fast=True)

    assert items == []
    assert session_invalid is False
    assert page.goto_count == 2
    assert collector._api_auth_backoff_until > time.monotonic()


@pytest.mark.asyncio
async def test_search_api_navigation_keeps_filter_params(fake_browser: Any, fake_ad: Any) -> None:
    """API 拦截实际导航 URL 应与日志 URL 一致，保留搜索筛选参数。"""
    collector = Collector(browser=fake_browser, antidetect=fake_ad)
    page = FakeSearchApiPage()

    await collector._call_search_api(
        page,
        "DDR4",
        max_pages=1,
        fast=True,
        filter_params=["sourceType=0", "yhb=1", "postageType=1"],
    )

    assert "sourceType=0" in page.url
    assert "yhb=1" in page.url
    assert "postageType=1" in page.url


@pytest.mark.asyncio
async def test_sync_mtop_set_cookie_response_to_context() -> None:
    """route.fetch() 捕获到的 Set-Cookie 应手动写回浏览器上下文"""
    page = FakeCookiePage()

    synced = await _sync_response_cookies_to_context(page, FakeApiResponse())

    assert synced == 2
    assert [c["name"] for c in page.context.added_cookies] == ["_m_h5_tk", "_m_h5_tk_enc"]


# ============== 集成测试（mock page） ==============


@pytest.mark.asyncio
async def test_search_dedup_in_run(fake_browser: Any, fake_ad: Any) -> None:
    """搜索结果内部去重逻辑：同一商品 ID 出现两次，_parse_card 能解析出相同 ID"""
    page = FakePage()
    # 闲鱼卡片是 <a> 标签，tag="A" 让 _parse_card 直接用 card 当链接
    card1 = FakeElement(attrs={"href": "/item.htm?id=1"}, tag="A")
    page.cards = [card1, card1]

    fake_browser.new_page = AsyncMock(return_value=page)
    collector = Collector(browser=fake_browser, antidetect=fake_ad)

    cards = await collector._find_cards(page)
    assert len(cards) == 2

    # 两张卡片都能解析出 item_id=1
    items = []
    for c in cards:
        result = await collector._parse_card(c)
        if result:
            items.append(result)
    assert len(items) == 2
    assert items[0].id == "1"
    assert items[1].id == "1"


@pytest.mark.asyncio
async def test_detail_returns_None_on_error(fake_browser: Any, fake_ad: Any) -> None:
    """详情采集失败返回 None 而不是抛错"""
    page = FakePage()
    page.goto = AsyncMock(side_effect=Exception("network down"))
    fake_browser.new_page = AsyncMock(return_value=page)
    collector = Collector(browser=fake_browser, antidetect=fake_ad)
    result = await collector.detail("999")
    assert result is None


@pytest.mark.asyncio
async def test_extract_count_parses_digits(fake_browser: Any, fake_ad: Any) -> None:
    """_extract_count 从文本提取数字"""
    page = FakePage()
    page.selector_map["any"] = FakeElement(text="在售 42 件")
    fake_browser.new_page = AsyncMock(return_value=page)
    collector = Collector(browser=fake_browser, antidetect=fake_ad)
    result = await collector._extract_count(page, "any")
    assert result == 42


@pytest.mark.asyncio
async def test_extract_count_handles_comma(fake_browser: Any, fake_ad: Any) -> None:
    """_extract_count 处理千分位逗号"""
    page = FakePage()
    page.selector_map["any"] = FakeElement(text="已售 1,234 件")
    fake_browser.new_page = AsyncMock(return_value=page)
    collector = Collector(browser=fake_browser, antidetect=fake_ad)
    result = await collector._extract_count(page, "any")
    assert result == 1234


@pytest.mark.asyncio
async def test_extract_count_returns_zero_on_missing(fake_browser: Any, fake_ad: Any) -> None:
    """元素不存在返回 0"""
    page = FakePage()
    fake_browser.new_page = AsyncMock(return_value=page)
    collector = Collector(browser=fake_browser, antidetect=fake_ad)
    result = await collector._extract_count(page, "fake-selector")
    assert result == 0


@pytest.mark.asyncio
async def test_find_cards_returns_empty_on_no_match(fake_browser: Any, fake_ad: Any) -> None:
    """无任何匹配选择器返回空列表"""
    page = FakePage()
    fake_browser.new_page = AsyncMock(return_value=page)
    collector = Collector(browser=fake_browser, antidetect=fake_ad)
    cards = await collector._find_cards(page)
    assert cards == []
