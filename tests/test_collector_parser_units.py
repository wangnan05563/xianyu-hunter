"""批次 5 覆盖率用例：collector/_parser.py 的 DOM 卡片解析与 API 字段解析

_parser.py 的解析方法全部围绕「卡片元素」这一 Playwright 句柄展开，
用轻量 fake 元素（按选择器字典返回子元素）即可覆盖各字段的命中/回退分支，
无需真实浏览器。
"""
from __future__ import annotations

import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from loguru import logger as loguru_logger
from playwright.async_api import TimeoutError as PlaywrightTimeout

from xianyu_hunter.infra.selectors import SelectorRepo
from xianyu_hunter.modules.collector import Collector


@pytest.fixture
def caplog_info(caplog):
    caplog.set_level(logging.DEBUG)
    bridge = logging.getLogger("parser_cov")
    _level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "EXCEPTION": logging.ERROR,
    }

    def _sink(message):
        std_level = _level_map.get(message.record["level"].name)
        if std_level is not None:
            bridge.log(std_level, message.record["message"])

    sink_id = loguru_logger.add(_sink, level="DEBUG")
    try:
        yield caplog
    finally:
        loguru_logger.remove(sink_id)


def _make_collector() -> Collector:
    browser = MagicMock()
    ad = MagicMock()
    ad.human_delay = AsyncMock()
    ad.throttle = AsyncMock()
    return Collector(browser=browser, antidetect=ad, selectors=SelectorRepo)


class _El:
    """最小可用的 ElementHandle 替身

    children 按选择器原文命中；未登记的选择器返回 None，
    对应真实 DOM 里 query_selector 未匹配的情况。
    """

    def __init__(
        self,
        text: str = "",
        attrs: dict[str, str | None] | None = None,
        children: dict[str, Any] | None = None,
        tag: str = "DIV",
    ):
        self._text = text
        self._attrs = attrs or {}
        self._children = children or {}
        self._tag = tag

    async def evaluate(self, _expr: str) -> str:
        return self._tag

    async def query_selector(self, selector: str):
        return self._children.get(selector)

    async def get_attribute(self, name: str):
        return self._attrs.get(name)

    async def inner_text(self) -> str:
        return self._text


# ============ 卡片选择器轮询 ============


async def test_wait_for_cards_first_hit_and_all_timeout(caplog_info) -> None:
    c = _make_collector()
    page = AsyncMock()
    candidates = SelectorRepo.search_card_candidates()
    await c._wait_for_cards(page, timeout=15000)
    assert page.wait_for_selector.await_count == 1
    assert page.wait_for_selector.await_args.args[0] == candidates[0]
    # 每轮超时预算按候选数均分
    assert page.wait_for_selector.await_args.kwargs["timeout"] == 15000 // len(candidates)

    page.wait_for_selector = AsyncMock(side_effect=PlaywrightTimeout("timeout"))
    caplog_info.clear()
    await c._wait_for_cards(page, timeout=9000)
    assert page.wait_for_selector.await_count == len(candidates)
    assert any("搜索卡片未找到任何匹配选择器" in r.message for r in caplog_info.records)

    # 前几个超时、最后一个命中：不应打印降级警告
    seq = [PlaywrightTimeout("t")] * (len(candidates) - 1) + [AsyncMock()]
    page.wait_for_selector = AsyncMock(side_effect=seq)
    caplog_info.clear()
    await c._wait_for_cards(page)
    assert not any("未找到任何匹配选择器" in r.message for r in caplog_info.records)


async def test_find_cards_returns_first_non_empty() -> None:
    c = _make_collector()
    cards = [_El(), _El()]
    second = SelectorRepo.search_card_candidates()[1]
    page = AsyncMock()
    page.query_selector_all = AsyncMock(side_effect=lambda sel: cards if sel == second else [])
    assert await c._find_cards(page) == cards
    assert page.query_selector_all.await_count == 2

    page.query_selector_all = AsyncMock(return_value=[])
    assert await c._find_cards(page) == []


# ============ 单字段提取 ============


def _item_link(href: str = "https://www.goofish.com/item?id=123456") -> _El:
    return _El(tag="A", attrs={"href": href})


async def test_extract_card_item_id_both_shapes() -> None:
    c = _make_collector()
    # 卡片本身即 <a>：直接取自身 href
    assert await c._extract_card_item_id(_El(tag="a", attrs={"href": "?itemId=777"})) == "777"
    # 非 <a> 卡片：向内找 CARD_LINK_MAIN
    nested = _El(children={SelectorRepo.CARD_LINK_MAIN: _item_link()})
    assert await c._extract_card_item_id(nested) == "123456"
    # 找不到链接 → 空串
    assert await c._extract_card_item_id(_El()) == ""
    # 链接存在但 href 为空 → extract_item_id 兜底返回空
    assert await c._extract_card_item_id(_El(children={SelectorRepo.CARD_LINK_MAIN: _El(tag="A")})) == ""


async def test_extract_card_title_and_price_fallbacks() -> None:
    c = _make_collector()
    title_sels = SelectorRepo.title_candidates()
    price_sels = SelectorRepo.price_candidates()

    # 首个候选没有元素，第二个候选给出带空白的标题 → 去除首尾空白
    card = _El(children={title_sels[1]: _El(text="  金士顿 DDR4 8G  "), price_sels[0]: _El(text="¥128.50")})
    assert await c._extract_card_title(card) == "金士顿 DDR4 8G"
    assert await c._extract_card_price(card) == 128.5

    # 所有候选都命中但文本为空 → 仍返回空串/0.0，不抛异常
    empty = _El(children={sel: _El(text="   ") for sel in title_sels + price_sels})
    assert await c._extract_card_title(empty) == ""
    assert await c._extract_card_price(empty) == 0.0

    # 文本是 "0" 时 parse_price_from_text 得到 0，不满足 > 0，继续尝试下一个候选
    two_step = _El(children={price_sels[0]: _El(text="0"), price_sels[1]: _El(text="1990")})
    assert await c._extract_card_price(two_step) == 1990.0


async def test_extract_card_thumbnail_attr_order() -> None:
    c = _make_collector()
    # 卡片内没有 img（懒加载尚未渲染）时返回空串
    assert await c._extract_card_thumbnail(_El()) == ""
    card = _El(children={SelectorRepo.CARD_THUMB_MAIN: _El()})
    assert await c._extract_card_thumbnail(card) == ""

    # src 是 data: 占位图 → 跳到 data-src，协议相对 URL 补全 https:
    img = _El(attrs={"src": "data:image/gif;base64,R0", "data-src": "//img.alicdn.com/p.jpg"})
    card = _El(children={SelectorRepo.CARD_THUMB_MAIN: img})
    assert await c._extract_card_thumbnail(card) == "https://img.alicdn.com/p.jpg"

    # 已是绝对 URL 时不重复补协议
    card = _El(children={SelectorRepo.CARD_THUMB_MAIN: _El(attrs={"src": "https://a.com/x.jpg"})})
    assert await c._extract_card_thumbnail(card) == "https://a.com/x.jpg"


async def test_extract_card_region_and_want_count() -> None:
    c = _make_collector()
    assert await c._extract_card_region(_El()) == ""
    loc = _El(children={SelectorRepo.CARD_SELLER_LOCATION: _El(text=" 浙江杭州 ")})
    assert await c._extract_card_region(loc) == "浙江杭州"

    assert await c._extract_card_want_count(_El(text="金士顿内存条\n45人想要\n¥128")) == 45
    assert await c._extract_card_want_count(_El(text="无想要数")) == 0

    boom = MagicMock(spec=["inner_text"])
    boom.inner_text = AsyncMock(side_effect=RuntimeError("detached"))
    assert await c._extract_card_want_count(boom) == 0


async def test_check_card_sold_all_strategies() -> None:
    c = _make_collector()
    assert await c._check_card_sold(_El(text="卖掉了")) is True
    assert await c._check_card_sold(_El(attrs={"class": "feeds-item sold-out"})) is True
    assert await c._check_card_sold(_El(children={".sold-tag": _El()})) is True
    assert await c._check_card_sold(_El(text="全新未拆封")) is False

    # 无 inner_text 属性的元素：文本降级为空串后继续走类名/子元素判断
    no_text = MagicMock(spec=["query_selector", "get_attribute"])
    no_text.query_selector = AsyncMock(return_value=None)
    no_text.get_attribute = AsyncMock(return_value=None)
    assert await c._check_card_sold(no_text) is False

    boom = MagicMock(spec=["inner_text"])
    boom.inner_text = AsyncMock(side_effect=RuntimeError("detached"))
    assert await c._check_card_sold(boom) is False


# ============ _parse_card 编排 ============


def _full_card(text: str = "金士顿内存条\n45人想要") -> _El:
    return _El(
        text=text,
        children={
            SelectorRepo.CARD_LINK_MAIN: _item_link(),
            SelectorRepo.title_candidates()[0]: _El(text="金士顿 DDR4 8G"),
            SelectorRepo.price_candidates()[0]: _El(text="¥128"),
            SelectorRepo.CARD_THUMB_MAIN: _El(attrs={"src": "//img.alicdn.com/p.jpg"}),
            SelectorRepo.CARD_SELLER_LOCATION: _El(text="浙江杭州"),
        },
    )


async def test_parse_card_success_and_gaps() -> None:
    c = _make_collector()
    item = await c._parse_card(_full_card())
    assert item is not None
    assert (item.id, item.title, item.price, item.region, item.want_cnt) == (
        "123456", "金士顿 DDR4 8G", 128.0, "浙江杭州", 45,
    )
    assert item.thumb_url == "https://img.alicdn.com/p.jpg"
    assert item.is_sold is False and item.publish_time is None

    # 卡片无链接 → 直接判为不可用，返回 None
    assert await c._parse_card(_El(text="无链接卡片")) is None


async def test_parse_card_exception_is_warning(caplog_info) -> None:
    c = _make_collector()
    boom = MagicMock()
    boom.evaluate = AsyncMock(return_value="DIV")
    boom.query_selector = AsyncMock(side_effect=RuntimeError("element detached"))
    caplog_info.clear()
    assert await c._parse_card(boom) is None
    records = [r for r in caplog_info.records if "解析卡片失败" in r.message]
    assert records and records[0].levelname == "WARNING"


# ============ 静态委托与信用分 ============


def test_static_delegates() -> None:
    c = _make_collector()
    assert Collector._extract_item_id("https://www.goofish.com/item/555") == "555"
    assert Collector._extract_item_id("no id here") == ""
    assert Collector._check_item_sold({"status": "sold"}) is True
    assert Collector._check_item_sold({"status": "onsale"}) is False
    # API 响应缺少 data 节点时解析为空列表，调用方据此走 DOM 回退
    assert c._parse_search_api_result({}) == []


@pytest.mark.parametrize(
    "raw,expected",
    [
        ({"userCreditScore": "820"}, 820),
        ({"creditScore": 950}, 950),
        ({"credit_score": 400}, 400),
        # 超出合理区间视为噪声字段，继续向后尝试
        ({"userCreditScore": 120, "zhimaCredit": 700}, 700),
        # 非数字信用分（文案等级）无法转 int → None
        ({"sellerCredit": "优秀"}, None),
        ({}, None),
    ],
)
def test_extract_credit_from_api_window(raw: dict, expected: int | None) -> None:
    assert Collector._extract_credit_from_api_raw(raw) == expected
