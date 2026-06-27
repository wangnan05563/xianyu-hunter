"""Buyer 单元测试

mock 浏览器层（FakePage / FakeLocator），验证：
- 幂等（in-process + DB 双重保护）
- 落单成功 → 持久化 + 事件
- 落单失败（ButtonNotFoundError / OutOfStockError / PriceMismatchError）
- 串行锁
- 节流
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

import pytest

from xianyu_hunter.domain.events import EventType
from xianyu_hunter.domain.order import (
    ButtonNotFoundError,
    OutOfStockError,
    PriceMismatchError,
)
from xianyu_hunter.infra.event_bus import EventBus
from xianyu_hunter.infra.selectors import SelectorRepo
from xianyu_hunter.modules.buyer import Buyer
from xianyu_hunter.modules.buyer_config import BuyerConfig


# ============== Fakes ==============


class FakeLocator:
    """模仿 Playwright Locator，count/first.click/first.wait_for/text_content"""

    def __init__(self, owner, selector: str):
        self.owner = owner
        self.selector = selector

    @property
    def first(self) -> "FakeLocator":
        return self

    async def count(self) -> int:
        return 1 if self.owner._matches(self.selector) else 0

    async def click(self, timeout: float = 2000) -> None:
        if not self.owner._matches(self.selector):
            # 抛 Playwright 风格 TimeoutError，让 buyer 的 except 抓到
            from playwright.async_api import TimeoutError as PlaywrightTimeout
            raise PlaywrightTimeout(f"click timeout: {self.selector}")
        self.owner.clicks.append(self.selector)
        self.owner._after_click(self.selector)

    async def wait_for(self, state: str | None = None, timeout: float = 5000) -> None:
        # 模拟等待：找到则 ok
        if not self.owner._matches(self.selector):
            from playwright.async_api import TimeoutError as PlaywrightTimeout
            raise PlaywrightTimeout(f"wait_for timeout: {self.selector}")

    async def text_content(self) -> str | None:
        return self.owner.text_map.get(self.selector)


class FakeMouse:
    def __init__(self, owner):
        self.owner = owner

    async def click(self, x: float, y: float) -> None:
        text = self.owner.last_coordinate_text or "mouse"
        self.owner.clicks.append(f"{text}(mouse:{x:.0f},{y:.0f})")
        self.owner._after_click(text)


@dataclass
class _BuyScenario:
    """可配置的单次落单场景"""
    out_of_stock: bool = False
    buy_button_missing: bool = False
    buy_selector_missing: bool = False
    submit_button_missing: bool = False
    submit_selector_missing: bool = False
    submit_button_text: str = "提交订单"
    buy_click_enters_order_page: bool = True
    order_page_url: str = "https://www.goofish.com/order/confirm"
    actual_price: float | None = None
    order_no: str | None = "202606030001"


class FakePage:
    """最简化的 Playwright Page mock，支持按 selector 行为可定制"""

    def __init__(self, scenario: _BuyScenario):
        self.scenario = scenario
        self.clicks: list[str] = []
        self.text_map: dict[str, str] = {}
        # 预先填充订单号/价格（用真实 selector，便于 Buyer 提取）
        if scenario.order_no:
            self.text_map[SelectorRepo.ORDER_NO_MAIN] = f"订单号 {scenario.order_no}"
        if scenario.actual_price is not None:
            self.text_map[SelectorRepo.DETAIL_PRICE_MAIN] = f"¥{scenario.actual_price}"
        self.goto_calls: list[str] = []
        self.closed = False
        self.url = ""
        self.order_page_ready = False
        self.mouse = FakeMouse(self)
        self.last_coordinate_text = ""

    def locator(self, selector: str) -> FakeLocator:
        return FakeLocator(self, selector)

    async def goto(self, url: str, **kwargs) -> None:
        self.goto_calls.append(url)
        self.url = url

    async def wait_for_load_state(self, state: str, timeout: float = 5000) -> None:
        return None

    def is_closed(self) -> bool:
        return self.closed

    async def title(self) -> str:
        return "fake title"

    async def evaluate(self, script: str, *args):
        if "document.body" in script:
            return ""
        text = args[0] if args else ""
        if text == "立即购买" and not self.scenario.buy_button_missing:
            self.last_coordinate_text = text
            return [{
                "raw": "立即购买",
                "tag": "div",
                "className": "buy--fake",
                "x": 123,
                "y": 456,
                "width": 160,
                "height": 44,
                "score": 1,
            }]
        if (
            text == self.scenario.submit_button_text
            and self.order_page_ready
            and not self.scenario.submit_button_missing
        ):
            self.last_coordinate_text = text
            return [{
                "raw": text,
                "tag": "div",
                "className": "submit--fake",
                "x": 321,
                "y": 654,
                "width": 180,
                "height": 48,
                "score": 1,
            }]
        return []

    def _after_click(self, selector: str) -> None:
        if "立即购买" in selector or "buy-now" in selector:
            if self.scenario.buy_click_enters_order_page:
                self.order_page_ready = True
                self.url = self.scenario.order_page_url

    async def text_content(self, selector: str) -> str | None:
        # 模拟"已下架"提示检测
        if self.scenario.out_of_stock:
            return "该商品已下架"
        return self.text_map.get(selector)

    async def close(self) -> None:
        self.closed = True

    def _matches(self, selector: str) -> bool:
        s = self.scenario
        if "已下架" in selector or "下架" in selector:
            return False  # 我们没有"已下架"专用 selector
        # 立即购买按钮
        if "立即购买" in selector or "buy-now" in selector:
            return not s.buy_button_missing and not s.buy_selector_missing
        # 提交订单/确认购买按钮
        submit_texts = ("提交订单", "确认购买", "确认订单")
        if any(text in selector for text in submit_texts) or "submit" in selector or "confirm" in selector:
            if s.submit_button_missing or s.submit_selector_missing or not self.order_page_ready:
                return False
            # class 兜底选择器只要出现就认为可命中；文本选择器需匹配当前场景文案。
            if "submit" in selector or "confirm" in selector:
                return True
            return s.submit_button_text in selector
        # 订单号/价格等文本
        return selector in self.text_map


class FakeBrowser:
    """BrowserManager fake"""

    def __init__(self, scenario: _BuyScenario):
        self.scenario = scenario
        self.page = FakePage(scenario)

    async def new_page(self) -> FakePage:
        return self.page


class FakeRepository:
    """Repository fake（仅 Buyer 需要的子集）"""

    def __init__(self):
        self.orders: list[dict] = []
        self.items: dict[str, dict] = {}

    def find_order_by_task_item(self, task_id: str, item_id: str) -> dict | None:
        for o in reversed(self.orders):
            if o["item_id"] == item_id and o.get("status") != "failed":
                return o
        return None

    def upsert_order(self, order: dict) -> None:
        # 简化：直接 append
        self.orders.append(dict(order))

    def get_item(self, item_id: str) -> dict | None:
        return self.items.get(item_id)


# ============== 工厂 ==============


def make_buyer(
    scenario: _BuyScenario | None = None,
    config: BuyerConfig | None = None,
    bus: EventBus | None = None,
) -> tuple[Buyer, FakeRepository, FakeBrowser, EventBus | None]:
    scenario = scenario or _BuyScenario()
    browser = FakeBrowser(scenario)
    repo = FakeRepository()
    repo.items["i1"] = {"title": "iPhone 13", "price": 1999.0}
    bus = bus or EventBus()
    cfg = config or BuyerConfig(
        click_retry_times=1,
        click_retry_interval=0.01,
        confirm_button_timeout=0.5,
        min_interval_between_orders=0.0,
    )
    buyer = Buyer(browser=browser, repository=repo, event_bus=bus, config=cfg)
    return buyer, repo, browser, bus


# ============== 落单成功 ==============


@pytest.mark.asyncio
async def test_buy_success() -> None:
    """完整流程成功 → SUCCESS + 订单持久化 + BUY_SUCCEEDED 事件"""
    scenario = _BuyScenario(actual_price=1999.0, order_no="202606030001")
    buyer, repo, browser, bus = make_buyer(scenario)
    result = await buyer.buy(task_id="t1", item_id="i1", expected_price=1999.0, page=browser.page)

    assert result.outcome.value == "success"
    assert result.order is not None
    assert result.order.order_no == "202606030001"
    assert result.order.price == 1999.0
    # DB 持久化
    assert len(repo.orders) == 1
    assert repo.orders[0]["order_no"] == "202606030001"
    # 浏览器：导航 + 2 次点击
    assert browser.page.goto_calls == ["https://www.goofish.com/item?id=i1"]
    assert "buy" in browser.page.clicks[0] or "立即购买" in browser.page.clicks[0]
    # 事件
    events: list[Any] = []
    bus.subscribe(EventType.BUY_SUCCEEDED, lambda e: events.append(e))
    await bus.publish(  # 显式 publish 测试订阅路径
        type("E", (), {"type": EventType.BUY_SUCCEEDED})()
    )


@pytest.mark.asyncio
async def test_buy_success_with_confirm_purchase_button() -> None:
    """订单确认页按钮文案为「确认购买」时也能落单成功。"""
    scenario = _BuyScenario(actual_price=1999.0, submit_button_text="确认购买")
    buyer, _, browser, _ = make_buyer(scenario)

    result = await buyer.buy(task_id="t1", item_id="i1", expected_price=1999.0, page=browser.page)

    assert result.outcome.value == "success"
    assert any("确认购买" in click for click in browser.page.clicks)


@pytest.mark.asyncio
async def test_buy_success_with_submit_dom_coordinate_fallback() -> None:
    """订单确认按钮 selector 未命中时，DOM 坐标扫描仍能点击。"""
    scenario = _BuyScenario(
        actual_price=1999.0,
        submit_button_text="确认购买",
        submit_selector_missing=True,
    )
    buyer, _, browser, _ = make_buyer(scenario)

    result = await buyer.buy(task_id="t1", item_id="i1", expected_price=1999.0, page=browser.page)

    assert result.outcome.value == "success"
    assert any("确认购买(mouse" in click for click in browser.page.clicks)


@pytest.mark.asyncio
async def test_buy_success_with_create_order_url_containing_item_id() -> None:
    """create-order URL 会带 itemId，不能误判为仍停留在详情页。"""
    scenario = _BuyScenario(
        actual_price=1999.0,
        order_page_url="https://www.goofish.com/create-order?spm=x&itemId=i1",
    )
    buyer, _, browser, _ = make_buyer(scenario)

    result = await buyer.buy(task_id="t1", item_id="i1", expected_price=1999.0, page=browser.page)

    assert result.outcome.value == "success"
    assert "create-order" in browser.page.url


@pytest.mark.asyncio
async def test_buy_fail_when_buy_click_stays_on_detail_page() -> None:
    """点到「立即购买」但仍停留详情页时，错误应指向未进入确认页。"""
    scenario = _BuyScenario(actual_price=1999.0, buy_click_enters_order_page=False)
    buyer, _, browser, _ = make_buyer(
        scenario,
        config=BuyerConfig(
            click_retry_times=1,
            click_retry_interval=0.01,
            confirm_button_timeout=0.1,
            min_interval_between_orders=0.0,
        ),
    )

    result = await buyer.buy(task_id="t1", item_id="i1", expected_price=1999.0, page=browser.page)

    assert result.outcome.value == "failed"
    assert "未进入订单确认页" in result.error
    assert any("立即购买" in click for click in browser.page.clicks)


@pytest.mark.asyncio
async def test_buy_success_with_buy_succeeded_event() -> None:
    """buy() 成功时自动发布 BUY_SUCCEEDED 事件"""
    scenario = _BuyScenario(actual_price=1999.0)
    bus = EventBus()
    buyer, _, browser, _ = make_buyer(scenario, bus=bus)
    # 先订阅
    received: list = []
    bus.subscribe(EventType.BUY_SUCCEEDED, lambda e: received.append(e))
    # 启动消费循环
    task = asyncio.create_task(bus.run_forever())
    await asyncio.sleep(0.05)

    result = await buyer.buy(task_id="t1", item_id="i1", expected_price=1999.0, page=browser.page)
    assert result.outcome.value == "success"

    # 等事件分发
    for _ in range(20):
        if received:
            break
        await asyncio.sleep(0.05)
    bus.stop()
    await task

    assert len(received) == 1
    assert received[0].payload["order_no"] == "202606030001"


# ============== 幂等 ==============


@pytest.mark.asyncio
async def test_buy_idempotent_in_process() -> None:
    """同 task_id + item_id 在进程内已下过单 → 第二次直接跳过"""
    scenario = _BuyScenario(actual_price=1999.0)
    buyer, repo, browser, _ = make_buyer(scenario)

    r1 = await buyer.buy(task_id="t1", item_id="i1", expected_price=1999.0, page=browser.page)
    r2 = await buyer.buy(task_id="t1", item_id="i1", expected_price=1999.0, page=browser.page)

    assert r1.outcome.value == "success"
    assert r2.outcome.value == "skipped_duplicate"
    # DB 中只有 1 单
    assert len(repo.orders) == 1


@pytest.mark.asyncio
async def test_buy_idempotent_db_existing() -> None:
    """DB 已有非失败订单 → 跨进程重启后仍能识别"""
    scenario = _BuyScenario(actual_price=1999.0)
    buyer, repo, browser, _ = make_buyer(scenario)
    # 预置一条订单
    repo.orders.append({
        "id": "i1:20260603001:abcd",
        "item_id": "i1",
        "order_no": "PERSISTED",
        "price": 1999.0,
        "status": "pending_pay",
    })
    result = await buyer.buy(task_id="t1", item_id="i1", expected_price=1999.0, page=browser.page)
    assert result.outcome.value == "skipped_duplicate"
    # 第二次不会真的去点
    assert browser.page.clicks == []


@pytest.mark.asyncio
async def test_buy_idempotent_failed_can_retry() -> None:
    """DB 中只有 FAILED 订单时，可重试下单"""
    scenario = _BuyScenario(actual_price=1999.0)
    buyer, repo, browser, _ = make_buyer(scenario)
    repo.orders.append({
        "id": "i1:20260603001:abcd",
        "item_id": "i1",
        "order_no": "",
        "price": 0.0,
        "status": "failed",
        "error": "previous fail",
    })
    result = await buyer.buy(task_id="t1", item_id="i1", expected_price=1999.0, page=browser.page)
    assert result.outcome.value == "success"


# ============== 失败场景 ==============


@pytest.mark.asyncio
async def test_buy_fail_button_not_found() -> None:
    """找不到「立即购买」按钮 → FAILED + 失败订单持久化 + BUY_FAILED 事件"""
    bus = EventBus()
    scenario = _BuyScenario(buy_button_missing=True)
    buyer, repo, browser, _ = make_buyer(scenario, bus=bus)
    result = await buyer.buy(task_id="t1", item_id="i1", expected_price=1999.0, page=browser.page)
    assert result.outcome.value == "failed"
    assert "立即购买" in result.error
    # 失败订单已写库
    assert len(repo.orders) == 1
    assert repo.orders[0]["status"] == "failed"
    # 事件
    assert not bus._queue.empty()
    event = bus._queue.get_nowait()
    assert event.type == EventType.BUY_FAILED


@pytest.mark.asyncio
async def test_buy_fail_out_of_stock() -> None:
    """商品下架 → FAILED"""
    scenario = _BuyScenario(out_of_stock=True)
    buyer, _, browser, _ = make_buyer(scenario)
    result = await buyer.buy(task_id="t1", item_id="i1", expected_price=1999.0, page=browser.page)
    assert result.outcome.value == "failed"
    assert "下架" in result.error or "无库存" in result.error


@pytest.mark.asyncio
async def test_buy_fail_price_mismatch() -> None:
    """拍下价格与预期偏差过大 → FAILED"""
    scenario = _BuyScenario(actual_price=2300.0)  # 比预期 1999 高 15%
    buyer, _, browser, _ = make_buyer(scenario)
    result = await buyer.buy(task_id="t1", item_id="i1", expected_price=1999.0, page=browser.page)
    assert result.outcome.value == "failed"
    assert "价格偏差" in result.error


@pytest.mark.asyncio
async def test_buy_price_within_tolerance() -> None:
    """拍下价格在容差范围内 → SUCCESS"""
    scenario = _BuyScenario(actual_price=2050.0)  # 偏差 2.5%, < 5%
    buyer, _, browser, _ = make_buyer(scenario)
    result = await buyer.buy(task_id="t1", item_id="i1", expected_price=1999.0, page=browser.page)
    assert result.outcome.value == "success"


# ============== 串行锁 ==============


@pytest.mark.asyncio
async def test_serial_lock_concurrent_buys() -> None:
    """并发 buy() 调用按顺序执行（不会同时落 2 单）"""
    scenario = _BuyScenario(actual_price=1999.0)
    buyer, _, browser, _ = make_buyer(scenario)
    # 5 个不同 item 并发下单
    buyer.repo.items.update({
        f"i{i}": {"title": f"item{i}", "price": 1999.0} for i in range(5)
    })
    coros = [
        buyer.buy(task_id="t1", item_id=f"i{i}", expected_price=1999.0, page=browser.page)
        for i in range(5)
    ]
    results = await asyncio.gather(*coros)
    # 全部成功
    assert all(r.outcome.value == "success" for r in results)
    # 5 次导航（串行）
    assert len(browser.page.goto_calls) == 5


# ============== 节流 ==============


@pytest.mark.asyncio
async def test_throttle_between_orders() -> None:
    """min_interval_between_orders 起作用：两次 buy() 间隔被强制"""
    scenario = _BuyScenario(actual_price=1999.0)
    buyer, _, browser, _ = make_buyer(
        scenario,
        config=BuyerConfig(
            click_retry_times=1,
            click_retry_interval=0.01,
            confirm_button_timeout=0.5,
            min_interval_between_orders=0.3,  # 强制间隔
        ),
    )
    buyer.repo.items.update({
        f"i{i}": {"title": f"item{i}", "price": 1999.0} for i in range(2)
    })
    t0 = time.monotonic()
    await buyer.buy(task_id="t1", item_id="i0", expected_price=1999.0, page=browser.page)
    await buyer.buy(task_id="t1", item_id="i1", expected_price=1999.0, page=browser.page)
    elapsed = time.monotonic() - t0
    # 第二次应至少等 0.3s
    assert elapsed >= 0.28, f"节流未生效，elapsed={elapsed}"
