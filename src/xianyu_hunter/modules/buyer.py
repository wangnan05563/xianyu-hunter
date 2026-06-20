"""闲鱼自动下单模块（抢单）

设计文档 §3.6 - 落单流程：
1. 导航到商品详情页
2. 点击"立即购买"按钮
3. 等待"提交订单"按钮出现
4. 点击"提交订单"按钮
5. 提取订单号
6. 持久化订单 + 发布 BUY_SUCCEEDED 事件

保护机制：
- 单账号串行（asyncio.Lock）：防止同时点两单
- 任务内幂等：内存 set + DB find_order_by_task_item 双重保护
"""
from __future__ import annotations

import asyncio
import re
import time
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from xianyu_hunter.infra.db_models import _utcnow
from xianyu_hunter.domain.events import Event, EventType
from xianyu_hunter.domain.order import (
    BuyOutcome,
    BuyResult,
    BuyerError,
    ButtonNotFoundError,
    OrderSnapshot,
    OrderStatus,
    OutOfStockError,
    PriceMismatchError,
)
from xianyu_hunter.domain.urls import build_item_url
from xianyu_hunter.infra.logger import get_logger
from xianyu_hunter.infra.repository import Repository
from xianyu_hunter.infra.selectors import SelectorRepo
from xianyu_hunter.modules.buyer_config import BuyerConfig

if TYPE_CHECKING:
    from xianyu_hunter.infra.event_bus import EventBus

logger = get_logger()


class Buyer:
    """自动抢单器

    使用方式：
        buyer = Buyer(browser, repo, event_bus, config)
        result = await buyer.buy(task_id="t1", item_id="abc123", expected_price=1999.0)

    并发安全：
        - 同实例内 buy() 调用会通过 _lock 串行执行
        - 同一 (task_id, item_id) 第二次调用会直接返回 SKIPPED_DUPLICATE
    """

    def __init__(
        self,
        browser,                # BrowserManager（避免循环 import 留空 type）
        repository: Repository,
        event_bus: "EventBus | None" = None,
        config: BuyerConfig | None = None,
        selectors: type[SelectorRepo] = SelectorRepo,
    ):
        self.browser = browser
        self.repo = repository
        self.bus = event_bus
        self.config = config or BuyerConfig()
        self.selectors = selectors
        # 串行锁：同账号同时只能落 1 单
        self._lock = asyncio.Lock()
        # 任务内幂等：记录本次进程内已下过单的 item_id
        self._task_item_set: set[tuple[str, str]] = set()
        # 上次落单时间（用于节流）
        self._last_buy_at: float = 0.0

    async def buy(
        self,
        task_id: str,
        item_id: str,
        expected_price: float,
        page: Page | None = None,
    ) -> BuyResult:
        """抢单入口

        Args:
            task_id: 所属任务 ID（用于幂等关联 + 事件携带）
            item_id: 目标商品 ID
            expected_price: 期望拍下价格（用于价格容差校验）
            page: 可选 Playwright page（测试注入用）
        """
        # 1+2. 幂等检查（内存 + DB）均在锁内执行，消除 TOCTOU 竞态
        key = (task_id, item_id)

        async with self._lock:
            if key in self._task_item_set:
                logger.info(f"[Buyer] 任务 {task_id} 内已下过 {item_id}，幂等跳过")
                return BuyResult(outcome=BuyOutcome.SKIPPED_DUPLICATE, error="in-process duplicate")

            # DB 幂等：跨进程重启后仍能识别
            existing = self.repo.find_order_by_task_item(task_id, item_id)
            if existing:
                self._task_item_set.add(key)
                logger.info(
                    f"[Buyer] DB 已存在订单 {existing.get('id')}，幂等跳过"
                )
                return BuyResult(
                    outcome=BuyOutcome.SKIPPED_DUPLICATE,
                    order=OrderSnapshot(
                        item_id=item_id,
                        order_no=existing.get("order_no", ""),
                        price=existing.get("price", 0.0),
                        status=OrderStatus(existing.get("status", "pending_pay")),
                    ),
                    error="db duplicate",
                )

            # 3. 节流：两次落单间最小间隔
            wait = self.config.min_interval_between_orders - (time.monotonic() - self._last_buy_at)
            if wait > 0:
                await asyncio.sleep(wait)

            # 4. 实际落单流程
            try:
                order = await self._do_buy(item_id, expected_price, page)
                # 补全 task_id 关联（_do_buy 不接收 task_id，在调用方补充）
                order["task_id"] = task_id
            except BuyerError as e:
                # 记录失败订单（便于后续分析）+ 发布事件
                self._save_failed_order(task_id, item_id, str(e))
                self._publish_buy_failed(task_id, item_id, str(e))
                return BuyResult(outcome=BuyOutcome.FAILED, error=str(e))
            except Exception as e:  # noqa: BLE001
                logger.exception(f"[Buyer] 落单未预期异常: {e}")
                self._save_failed_order(task_id, item_id, f"unexpected: {e}")
                self._publish_buy_failed(task_id, item_id, str(e))
                return BuyResult(outcome=BuyOutcome.FAILED, error=str(e))

            # 5. 持久化 + 发布事件
            self.repo.upsert_order(order)
            self._task_item_set.add(key)
            self._last_buy_at = time.monotonic()
            self._publish_buy_succeeded(task_id, item_id, order)
            return BuyResult(
                outcome=BuyOutcome.SUCCESS,
                order=OrderSnapshot(
                    item_id=item_id,
                    order_no=order["order_no"],
                    price=order["price"],
                    status=OrderStatus.PENDING_PAY,
                ),
            )

    # ============== 浏览器操作 ==============

    async def _do_buy(
        self,
        item_id: str,
        expected_price: float,
        page: Page | None = None,
    ) -> dict:
        """落单全流程：导航→点立即购买→点提交→提取订单号

        返回: dict (含 id / order_no / price / status 等字段，可直接 upsert)
        Raises: ButtonNotFoundError / OutOfStockError / PriceMismatchError
        """
        own_page = page is None
        if own_page:
            page = await self.browser.new_page()  # type: ignore[attr-defined]

        try:
            # 1. 导航到详情页
            await self._navigate(page, item_id)  # type: ignore[arg-type]

            # 2. 点击"立即购买"
            clicked = await self._click_buy_now(page)  # type: ignore[arg-type]
            if not clicked:
                raise ButtonNotFoundError("未找到「立即购买」按钮")

            # 3. 等待并点击"提交订单"
            confirmed = await self._click_submit_order(page)  # type: ignore[arg-type]
            if not confirmed:
                raise ButtonNotFoundError("未找到「提交订单」按钮")

            # 4. 提取订单号 + 实际价格
            order_no = await self._extract_order_no(page)  # type: ignore[arg-type]
            actual_price = await self._extract_actual_price(page)  # type: ignore[arg-type]
            if actual_price is None:
                # 拿不到价格时跳过校验（保守处理）
                logger.warning(f"[Buyer] 未能提取实际价格，跳过价格校验")
            elif abs(actual_price - expected_price) / max(expected_price, 0.01) > self.config.price_tolerance:
                raise PriceMismatchError(
                    f"价格偏差过大: 预期 ¥{expected_price} 实际 ¥{actual_price}"
                )

            return {
                # 订单 ID 时间戳与 created_at 统一使用 UTC，避免时区偏差
                "id": f"{item_id}:{_utcnow().strftime('%Y%m%d%H%M%S')}:{uuid.uuid4().hex[:8]}",
                "item_id": item_id,
                "order_no": order_no or "",
                "price": actual_price or expected_price,
                "status": OrderStatus.PENDING_PAY.value,
                "screenshot": "",
                "error": "",
                "created_at": _utcnow(),
            }
        finally:
            if own_page and page is not None:
                await page.close()

    async def _navigate(self, page: Page, item_id: str) -> None:
        url = build_item_url(item_id)
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        # 详情页加载需渲染，宽容等待 0.5s（原注释 2s 与实际不符，已修正）
        await asyncio.sleep(0.5)

    async def _click_buy_now(self, page: Page) -> bool:
        """点击"立即购买"，重试 click_retry_times 次"""
        for attempt in range(1, self.config.click_retry_times + 1):
            try:
                # 先判断是否下架
                if await self._is_out_of_stock(page):
                    raise OutOfStockError(f"商品已下架/无库存")
                # 主+备 选择器
                for selector in (self.selectors.BTN_BUY_NOW_MAIN, self.selectors.BTN_BUY_NOW_ALT):
                    try:
                        await page.locator(selector).first.click(timeout=2000)
                        return True
                    except PlaywrightTimeout:
                        continue
                # 本轮没点中，间隔后重试
                if attempt < self.config.click_retry_times:
                    await asyncio.sleep(self.config.click_retry_interval)
            except OutOfStockError:
                raise
        return False

    async def _click_submit_order(self, page: Page) -> bool:
        """等待并点击"提交订单"按钮"""
        try:
            await page.locator(self.selectors.SUBMIT_ORDER_BTN_MAIN).first.wait_for(
                timeout=int(self.config.confirm_button_timeout * 1000)
            )
            await page.locator(self.selectors.SUBMIT_ORDER_BTN_MAIN).first.click()
            return True
        except PlaywrightTimeout:
            try:
                # 备选
                await page.locator(self.selectors.SUBMIT_ORDER_BTN_ALT).first.click(timeout=2000)
                return True
            except PlaywrightTimeout:
                return False

    async def _extract_order_no(self, page: Page) -> str | None:
        """从页面提取订单号"""
        try:
            for selector in (self.selectors.ORDER_NO_MAIN, self.selectors.ORDER_NO_ALT):
                el = page.locator(selector).first
                if await el.count() > 0:
                    text = (await el.text_content() or "").strip()
                    # 取数字部分
                    m = re.search(r"\d{10,}", text)
                    if m:
                        return m.group(0)
        except Exception:  # noqa: BLE001
            pass
        return None

    async def _extract_actual_price(self, page: Page) -> float | None:
        """从提交订单页面提取实际价格"""
        try:
            el = page.locator(self.selectors.DETAIL_PRICE_MAIN).first
            if await el.count() > 0:
                text = (await el.text_content() or "").strip()
                m = re.search(r"\d+(?:\.\d+)?", text.replace(",", ""))
                if m:
                    return float(m.group(0))
        except Exception:  # noqa: BLE001
            pass
        return None

    async def _is_out_of_stock(self, page: Page) -> bool:
        """判断是否下架/无库存（检测页面提示文字）"""
        try:
            text = (await page.text_content("body") or "").lower()
            return any(kw in text for kw in (
                "已下架", "已结束", "暂时缺货", "商品不存在",
            ))
        except Exception:  # noqa: BLE001
            return False

    # ============== 持久化 / 事件 ==============

    def _save_failed_order(self, task_id: str, item_id: str, error: str) -> None:
        """记录失败订单（不计入幂等，retry 时可覆盖）"""
        try:
            self.repo.upsert_order({
                # 订单 ID 时间戳与 created_at 统一使用 UTC
                "id": f"{item_id}:{_utcnow().strftime('%Y%m%d%H%M%S')}:{uuid.uuid4().hex[:8]}",
                "item_id": item_id,
                "task_id": task_id,
                "price": 0.0,
                "status": OrderStatus.FAILED.value,
                "error": error[:500],
                "created_at": _utcnow(),
            })
        except Exception:  # noqa: BLE001
            logger.exception("[Buyer] 持久化失败订单失败")

    def _publish_buy_succeeded(self, task_id: str, item_id: str, order: dict) -> None:
        if not self.bus:
            return
        item = self.repo.get_item(item_id) or {}
        self.bus.publish_nowait(
            Event(
                type=EventType.BUY_SUCCEEDED,
                task_id=task_id,
                item_id=item_id,
                payload={
                    "item": {
                        "title": item.get("title", ""),
                        "price": order.get("price", 0.0),
                    },
                    "order_id": order.get("id", ""),
                    "order_no": order.get("order_no", ""),
                    "expire_at": "",
                },
            )
        )

    def _publish_buy_failed(self, task_id: str, item_id: str, error: str) -> None:
        if not self.bus:
            return
        self.bus.publish_nowait(
            Event(
                type=EventType.BUY_FAILED,
                task_id=task_id,
                item_id=item_id,
                payload={"error": error[:200]},
            )
        )
