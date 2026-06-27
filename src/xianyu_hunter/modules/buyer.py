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

from playwright.async_api import Error as PlaywrightError, Page, TimeoutError as PlaywrightTimeout

from xianyu_hunter.infra.db_models import _utcnow
from xianyu_hunter.infra.lru import LRUDict
from xianyu_hunter.domain.events import Event, EventType
from xianyu_hunter.domain.order import (
    BuyOutcome,
    BuyResult,
    BuyerError,
    ButtonNotFoundError,
    ItemSoldError,
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
        # 使用 LRUDict[tuple[str,str], None] 模拟 set 语义并带上限，
        # 防止长跑进程内存无限增长。即便 LRU 驱逐后，DB 幂等兜底仍能拦截重复下单。
        self._task_item_set: LRUDict[tuple[str, str], None] = LRUDict(maxsize=10000)
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
                # set 语义用 LRUDict[key]=None 模拟（值无意义）
                self._task_item_set[key] = None
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

            # 4. 实际落单流程（90 秒总体超时：防止浏览器操作无限阻塞）
            try:
                order = await asyncio.wait_for(
                    self._do_buy(item_id, expected_price, page),
                    timeout=90.0,
                )
                # 补全 task_id 关联（_do_buy 不接收 task_id，在调用方补充）
                order["task_id"] = task_id
            except BuyerError as e:
                # 记录失败订单（便于后续分析）+ 发布事件
                self._save_failed_order(task_id, item_id, str(e))
                self._publish_buy_failed(task_id, item_id, str(e))
                return BuyResult(outcome=BuyOutcome.FAILED, error=str(e))
            except asyncio.TimeoutError:
                # 90 秒总体超时：通常意味着闲鱼页面加载异常或会话失效（RGV587_ERROR）
                # 不走通用 Exception 分支：错误信息需对用户明确指出"超时"而非"未知异常"
                msg = "浏览器自动化流程超时（90秒），请检查闲鱼登录状态后重试"
                logger.warning(f"[Buyer] 落单超时 task={task_id} item={item_id}")
                self._save_failed_order(task_id, item_id, msg)
                self._publish_buy_failed(task_id, item_id, msg)
                return BuyResult(outcome=BuyOutcome.FAILED, error=msg)
            except Exception as e:  # noqa: BLE001
                logger.exception(f"[Buyer] 落单未预期异常: {e}")
                # 捕获到 error_logs 表，抢单异常是高优先级业务错误，需要可视化追踪
                try:
                    from xianyu_hunter.web.middleware.error_capture import capture_background_error
                    capture_background_error(e, context={
                        "source": "buyer._do_buy",
                        "task_id": task_id,
                        "item_id": item_id,
                        "expected_price": expected_price,
                    })
                except Exception:
                    pass
                self._save_failed_order(task_id, item_id, f"unexpected: {e}")
                self._publish_buy_failed(task_id, item_id, str(e))
                return BuyResult(outcome=BuyOutcome.FAILED, error=str(e))

            # 5. 持久化 + 发布事件
            self.repo.upsert_order(order)
            self._task_item_set[key] = None
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
            logger.info(f"[Buyer] 步骤1/4 导航详情页 item={item_id}")
            await self._navigate(page, item_id)  # type: ignore[arg-type]

            # 阶段一已售检测：导航后、点击立即购买前，先检测是否已售
            # 为什么在此处检测：导航完成页面已渲染，此时检测最准；
            # 已售商品不应继续进入抢单流程，避免无效点击
            if await self._detect_sold(page):  # type: ignore[arg-type]
                self._mark_item_sold(item_id)
                raise ItemSoldError("商品已售出")

            # 2. 点击"立即购买"
            logger.info(f"[Buyer] 步骤2/4 点击立即购买 item={item_id}")
            clicked = await self._click_buy_now(page, item_id=item_id)  # type: ignore[arg-type]
            if not clicked:
                raise ButtonNotFoundError("未找到「立即购买」按钮")

            # 2.5 等待页面跳转完成：点击「立即购买」后会跳转到订单确认页
            # 为什么需要显式等待：不等待直接查找「提交订单」按钮会导致竞态失败
            # 未登录时会跳转到登录页，需检测并给出友好错误
            logger.info(f"[Buyer] 步骤2.5/4 等待订单确认页 item={item_id}")
            await self._wait_for_order_page(page, item_id=item_id)  # type: ignore[arg-type]

            # 3. 等待并点击"提交订单/确认购买"
            logger.info(f"[Buyer] 步骤3/4 点击提交订单/确认购买 item={item_id}")
            confirmed = await self._click_submit_order(page)  # type: ignore[arg-type]
            if not confirmed:
                # 阶段二回退检测：提交订单按钮找不到时，回退检测是否因商品已售
                # 为什么需要回退：部分商品渲染时机不同，阶段一可能未命中
                if await self._detect_sold(page):  # type: ignore[arg-type]
                    self._mark_item_sold(item_id)
                    raise ItemSoldError("商品已售出")
                raise ButtonNotFoundError("未找到「提交订单/确认购买」按钮")

            # 4. 提取订单号 + 实际价格
            logger.info(f"[Buyer] 步骤4/4 提取订单号 item={item_id}")
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
        # 主动检查：page 可能在两次调用之间被外部关闭（Edge 崩溃/CDP 断开等），
        # 提前抛错可避免在 wait_for_load_state 内白白浪费 8 秒超时
        if page.is_closed():
            raise BuyerError("浏览器页面已关闭，请重启服务后重试")
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        except PlaywrightError as e:
            # goto 阶段就遇到浏览器关闭：直接翻译为友好错误
            if "closed" in str(e).lower():
                raise BuyerError("浏览器已关闭，请重启服务后重试") from e
            raise
        # 闲鱼详情页是 SPA，DOM ready 后按钮还需异步渲染
        # 先等 networkidle 让首批XHR完成，再宽容等待 1s 确保按钮挂载
        try:
            await page.wait_for_load_state("networkidle", timeout=8000)
        except PlaywrightTimeout:
            pass
        except PlaywrightError as e:
            # networkidle 等待过程中浏览器被关闭：与登录失效区分开，给出明确指引
            if "closed" in str(e).lower():
                raise BuyerError("浏览器已关闭，请重启服务后重试") from e
            raise
        await asyncio.sleep(1.0)

    async def _wait_for_order_page(
        self,
        page: Page,
        item_id: str = "",
        timeout: float | None = None,
        raise_on_timeout: bool = True,
        wait_for_networkidle: bool = True,
    ) -> bool:
        """点击「立即购买」后等待页面跳转完成，并检测是否跳转到登录页

        闲鱼的订单确认页是 SPA 动态加载，networkidle 可能过早返回。
        采用渐进式等待：先等 networkidle，再轮询检测「提交订单/确认购买」按钮或登录页特征。
        检测到登录页时抛出 BuyerError，给出比「未找到提交订单按钮」更准确的错误信息。
        """
        wait_seconds = timeout if timeout is not None else self.config.confirm_button_timeout

        if wait_for_networkidle:
            try:
                await page.wait_for_load_state(
                    "networkidle",
                    timeout=max(500, min(int(wait_seconds * 1000), 8000)),
                )
            except PlaywrightTimeout:
                # networkidle 超时不致命，继续轮询检测
                pass

        deadline = time.monotonic() + max(wait_seconds, 0.1)
        while time.monotonic() < deadline:
            current_url = page.url or ""
            # 检测登录页跳转：URL 中包含 login 标记
            if self._is_login_url(current_url):
                raise BuyerError(
                    "闲鱼未登录或登录已过期，请先在「Cookie 注入」页面重新登录闲鱼"
                )
            # 检测订单确认页最终按钮是否已出现：提前退出轮询
            if await self._has_submit_order_button(page):
                return True
            # URL 已进入订单创建页时，认为跳转已发生。
            # 注意 create-order URL 会带 itemId，不能用「URL 包含 item_id」判断仍在详情页。
            if self._is_order_page_url(current_url):
                return True
            await asyncio.sleep(min(0.5, max(0.05, deadline - time.monotonic())))

        current_url = page.url or ""
        is_order_page = self._is_order_page_url(current_url)
        still_on_detail = self._is_item_detail_url(current_url, item_id)
        has_buy_now = await self._has_buy_now_button(page)
        logger.warning(
            f"[Buyer] 点击立即购买后未进入订单确认页 item={item_id} "
            f"url={current_url} is_order_page={is_order_page} "
            f"still_on_detail={still_on_detail} has_buy_now={has_buy_now}"
        )
        if not raise_on_timeout:
            return is_order_page
        if is_order_page:
            return True
        if still_on_detail or has_buy_now:
            raise ButtonNotFoundError(
                "点击「立即购买」后仍停留在商品详情页，未进入订单确认页；"
                "可能是按钮点击被页面拦截、登录风控弹窗或按钮定位点偏移"
            )
        raise ButtonNotFoundError("点击「立即购买」后订单确认页未加载完成")

    async def _click_buy_now(self, page: Page, item_id: str = "") -> bool:
        """点击"立即购买"，重试 click_retry_times 次

        闲鱼部分商品只有「我想要」按钮（需聊天协商），无「立即购买」按钮。
        检测到此情况时抛出 BuyerError，给出比「未找到立即购买按钮」更友好的提示。
        """
        clicked_any = False
        for attempt in range(1, self.config.click_retry_times + 1):
            # 登录页跳转检测：每轮重试开始时检查 URL
            # 为什么放在 _is_out_of_stock 之前：登录态失效是最高频的失败原因，
            # 先检测可在毫秒级返回准确错误，而非等 4 个 selector 各超时 5 秒
            try:
                current_url = page.url or ""
            except Exception:  # noqa: BLE001
                current_url = ""
            if self._is_login_url(current_url):
                raise BuyerError(
                    "闲鱼未登录或登录已过期，请先在「Cookie 注入」页面重新登录闲鱼"
                )
            try:
                # 先判断是否下架
                if await self._is_out_of_stock(page):
                    raise OutOfStockError(f"商品已下架/无库存")

                for selector in self._buy_now_candidates():
                    try:
                        loc = page.locator(selector).first
                        if await self._locator_count(loc, selector, timeout=0.8) <= 0:
                            continue
                        await self._locator_wait_visible(loc, selector, timeout=0.8)
                        await self._locator_click(loc, selector, timeout=1.5)
                        clicked_any = True
                        logger.info(f"[Buyer] 已点击立即购买候选 selector={selector}")
                        if await self._wait_for_order_page(
                            page,
                            item_id=item_id,
                            timeout=0.25,
                            raise_on_timeout=False,
                            wait_for_networkidle=False,
                        ):
                            return True
                        logger.warning(f"[Buyer] 点击候选后未进入订单确认页，继续尝试 selector={selector}")
                    except PlaywrightTimeout:
                        continue
                    except Exception as e:  # noqa: BLE001
                        logger.debug(f"[Buyer] 点击立即购买候选失败 selector={selector}: {e}")
                        continue

                # Playwright 的 text selector 仍可能命中外层容器；再用 get_by_text 精确点文字中心。
                try:
                    if hasattr(page, "get_by_text"):
                        text_loc = page.get_by_text("立即购买", exact=True).last
                        if await self._locator_count(text_loc, "get_by_text('立即购买')", timeout=0.8) <= 0:
                            raise PlaywrightTimeout("get_by_text not found")
                        await self._locator_wait_visible(text_loc, "get_by_text('立即购买')", timeout=0.8)
                        await self._locator_click(text_loc, "get_by_text('立即购买')", timeout=1.5)
                        clicked_any = True
                        logger.info("[Buyer] 已通过 get_by_text 精确点击立即购买")
                        if await self._wait_for_order_page(
                            page,
                            item_id=item_id,
                            timeout=0.25,
                            raise_on_timeout=False,
                            wait_for_networkidle=False,
                        ):
                            return True
                        logger.warning("[Buyer] get_by_text 点击后未进入订单确认页")
                except PlaywrightTimeout:
                    pass
                except Exception as e:  # noqa: BLE001
                    logger.debug(f"[Buyer] get_by_text 点击立即购买失败: {e}")

                if clicked_any:
                    # 已经点到过候选按钮，后续由步骤 2.5 给出「未进入确认页」的准确错误。
                    return True
                # 兼容极旧版本：如果按钮点击立即同步跳转但短轮询没捕获，也继续交给步骤 2.5。
                if await self._has_submit_order_button(page):
                    return True
                # 两轮主备都未命中，检测是否为「我想要」类型商品
                if await self._has_want_button(page):
                    raise BuyerError(
                        "该商品不支持直接购买（仅有「我想要」按钮），需手动联系卖家"
                    )
                # 本轮没点中，间隔后重试
                if attempt < self.config.click_retry_times:
                    await asyncio.sleep(self.config.click_retry_interval)
            except (OutOfStockError, BuyerError):
                raise
        return False

    def _is_login_url(self, url: str) -> bool:
        lower = (url or "").lower()
        return any(marker in lower for marker in ("login", "passport", "login.taobao", "login.m.taobao"))

    def _is_order_page_url(self, url: str) -> bool:
        lower = (url or "").lower()
        path = lower.split("?", 1)[0]
        return any(marker in path for marker in (
            "create-order",
            "/order",
            "/confirm",
            "/trade",
            "/pay",
        ))

    def _is_item_detail_url(self, url: str, item_id: str = "") -> bool:
        lower = (url or "").lower()
        path = lower.split("?", 1)[0]
        if self._is_order_page_url(url):
            return False
        if "goofish.com/item" in path or path.endswith("/item"):
            return True
        return bool(item_id and item_id in lower and not self._is_order_page_url(url))

    def _buy_now_candidates(self) -> list[str]:
        if hasattr(self.selectors, "buy_now_candidates"):
            return list(self.selectors.buy_now_candidates())
        return [
            self.selectors.BTN_BUY_NOW_MAIN,
            self.selectors.BTN_BUY_NOW_ALT,
            self.selectors.BTN_BUY_NOW_ALT2,
        ]

    async def _locator_count(self, loc, label: str, timeout: float = 0.8) -> int:
        try:
            return int(await asyncio.wait_for(loc.count(), timeout=timeout))
        except asyncio.TimeoutError:
            logger.warning(f"[Buyer] locator.count 超时 selector={label}")
            return 0

    async def _locator_wait_visible(self, loc, label: str, timeout: float = 0.8) -> None:
        try:
            await asyncio.wait_for(
                loc.wait_for(state="visible", timeout=int(timeout * 1000)),
                timeout=timeout + 0.3,
            )
        except asyncio.TimeoutError as e:
            logger.warning(f"[Buyer] locator.wait_for visible 超时 selector={label}")
            raise PlaywrightTimeout(f"wait_for visible timeout: {label}") from e

    async def _locator_click(self, loc, label: str, timeout: float = 1.5) -> None:
        try:
            await asyncio.wait_for(
                loc.click(timeout=int(timeout * 1000)),
                timeout=timeout + 0.5,
            )
        except asyncio.TimeoutError as e:
            logger.warning(f"[Buyer] locator.click 超时 selector={label}")
            raise PlaywrightTimeout(f"click timeout: {label}") from e

    async def _has_buy_now_button(self, page: Page) -> bool:
        for selector in self._buy_now_candidates():
            try:
                if await self._locator_count(page.locator(selector).first, selector, timeout=0.5) > 0:
                    return True
            except Exception:  # noqa: BLE001
                continue
        return False

    async def _click_visible_text_by_dom(self, page: Page, text: str) -> bool:
        """点击精确文本节点对应的最小可见元素。"""
        return await self._click_visible_text_by_coordinates(page, text)

    async def _click_visible_text_by_coordinates(
        self,
        page: Page,
        text: str,
        *,
        log_missing: bool = True,
    ) -> bool:
        """深度扫描可见文本并用鼠标坐标点击中心。"""
        script = (
            """(text) => {
                const startedAt = performance.now();
                const MAX_MS = 1200;
                const MAX_TEXT_NODES = 8000;
                const MAX_CANDIDATES = 40;
                const isVisible = (el) => {
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    return style.visibility !== 'hidden'
                        && style.display !== 'none'
                        && rect.width >= 8
                        && rect.height >= 8
                        && rect.bottom >= 0
                        && rect.right >= 0
                        && rect.top <= window.innerHeight
                        && rect.left <= window.innerWidth;
                };
                const normalize = (value) => (value || '').replace(/\\s+/g, '').trim();
                const needle = normalize(text);
                const clickableAncestor = (el) => {
                    let cur = el;
                    for (let i = 0; cur && i < 6; i += 1, cur = cur.parentElement) {
                        const tag = cur.tagName && cur.tagName.toLowerCase();
                        const role = cur.getAttribute && cur.getAttribute('role');
                        const className = String(cur.className || '');
                        if (tag === 'button' || tag === 'a' || role === 'button' || /buy|购买|submit|confirm|order|button|btn/i.test(className)) {
                            return cur;
                        }
                    }
                    return el;
                };
                const score = (el, label, rect) => {
                    const exact = label === needle ? 0 : 100000;
                    const area = rect.width * rect.height;
                    const tag = el.tagName.toLowerCase();
                    const clickable = tag === 'button' || tag === 'a' || el.getAttribute('role') === 'button' ? -50000 : 0;
                    const classHint = /buy|购买|submit|confirm/i.test(el.className || '') ? -20000 : 0;
                    const bottomHint = rect.top > window.innerHeight * 0.45 ? -5000 : 0;
                    return exact + area + clickable + classHint + bottomHint;
                };
                const roots = [document];
                const candidates = [];
                let scanned = 0;
                for (let r = 0; r < roots.length; r += 1) {
                    if (performance.now() - startedAt > MAX_MS || scanned > MAX_TEXT_NODES) break;
                    const root = roots[r];
                    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
                    let node;
                    while ((node = walker.nextNode())) {
                        if (performance.now() - startedAt > MAX_MS || scanned > MAX_TEXT_NODES) break;
                        scanned += 1;
                        const label = normalize(node.nodeValue);
                        if (!label.includes(needle)) continue;
                        const parent = node.parentElement;
                        if (!parent) continue;
                        const target = clickableAncestor(parent);
                        if (!target || !isVisible(target)) continue;
                        const rect = target.getBoundingClientRect();
                        candidates.push({
                            raw: (target.innerText || target.textContent || node.nodeValue || '').trim().slice(0, 80),
                            tag: target.tagName.toLowerCase(),
                            className: String(target.className || '').slice(0, 120),
                            x: rect.left + rect.width / 2,
                            y: rect.top + rect.height / 2,
                            width: rect.width,
                            height: rect.height,
                            score: score(target, normalize(target.textContent || node.nodeValue), rect),
                            scanned,
                        });
                        if (candidates.length >= MAX_CANDIDATES) break;
                    }
                    const shadowHosts = Array.from(root.querySelectorAll ? root.querySelectorAll('*') : [])
                        .filter((el) => el.shadowRoot)
                        .slice(0, 20);
                    roots.push(...shadowHosts.map((el) => el.shadowRoot));
                }
                candidates.sort((a, b) => a.score - b.score);
                return candidates;
            }"""
        )
        try:
            candidates = await asyncio.wait_for(page.evaluate(script, text), timeout=2.0)
        except asyncio.TimeoutError:
            logger.warning(f"[Buyer] DOM 扫描「{text}」超时，跳过坐标点击")
            return False
        if not candidates:
            if not log_missing:
                return False
            url = ""
            title = ""
            body_hint = ""
            try:
                url = page.url or ""
                title = await asyncio.wait_for(page.title(), timeout=1.0)
                body_hint = await asyncio.wait_for(
                    page.evaluate("() => (document.body && document.body.innerText || '').slice(0, 300)"),
                    timeout=1.0,
                )
            except Exception:  # noqa: BLE001
                pass
            logger.warning(
                f"[Buyer] DOM 未找到可见文本「{text}」 url={url} title={title} body={body_hint!r}"
            )
            return False

        first = candidates[0]
        logger.info(
            f"[Buyer] DOM 文本候选「{text}」top={first}"
        )
        await page.mouse.click(float(first["x"]), float(first["y"]))
        return True

    async def _has_want_button(self, page: Page) -> bool:
        """检测页面是否有「我想要」按钮（非直接购买类商品）

        闲鱼的「我想要」也是 <a> 标签，需三档选择器兜底。
        """
        for selector in (
            self.selectors.BTN_IWANT_MAIN,
            self.selectors.BTN_IWANT_ALT,
            self.selectors.BTN_IWANT_ALT2,
        ):
            try:
                if await self._locator_count(page.locator(selector).first, selector, timeout=0.5) > 0:
                    return True
            except Exception:  # noqa: BLE001
                continue
        return False

    def _submit_order_candidates(self) -> list[str]:
        if hasattr(self.selectors, "submit_order_candidates"):
            return list(self.selectors.submit_order_candidates())
        return [
            self.selectors.SUBMIT_ORDER_BTN_MAIN,
            self.selectors.SUBMIT_ORDER_BTN_ALT,
            self.selectors.SUBMIT_ORDER_BTN_ALT2,
        ]

    def _submit_order_text_candidates(self) -> list[str]:
        if hasattr(self.selectors, "submit_order_text_candidates"):
            return list(self.selectors.submit_order_text_candidates())
        return ["提交订单", "确认购买", "确认订单", "确认下单"]

    async def _has_submit_order_button(self, page: Page) -> bool:
        """检测订单确认页最终确认按钮是否已出现。"""
        for selector in self._submit_order_candidates():
            try:
                if await self._locator_count(page.locator(selector).first, selector, timeout=0.5) > 0:
                    return True
            except Exception:  # noqa: BLE001
                continue
        return False

    async def _click_submit_order(self, page: Page) -> bool:
        """等待并点击"提交订单/确认购买"按钮（多文案兜底）。"""
        deadline = time.monotonic() + self.config.confirm_button_timeout
        last_error: Exception | None = None

        while time.monotonic() < deadline:
            for selector in self._submit_order_candidates():
                try:
                    loc = page.locator(selector).first
                    if await self._locator_count(loc, selector, timeout=0.5) <= 0:
                        continue
                    await self._locator_wait_visible(loc, selector, timeout=0.5)
                    await self._locator_click(loc, selector, timeout=1.5)
                    logger.info(f"[Buyer] 已点击订单确认按钮 selector={selector}")
                    return True
                except PlaywrightTimeout as e:
                    last_error = e
                    continue
                except Exception as e:  # noqa: BLE001
                    last_error = e
                    continue

            current_url = page.url or ""
            if self._is_order_page_url(current_url):
                for text in self._submit_order_text_candidates():
                    try:
                        clicked = await self._click_visible_text_by_coordinates(
                            page,
                            text,
                            log_missing=False,
                        )
                        if clicked:
                            logger.info(f"[Buyer] 已通过 DOM 坐标点击订单确认按钮 text={text}")
                            return True
                    except Exception as e:  # noqa: BLE001
                        last_error = e
                        logger.debug(f"[Buyer] DOM 坐标点击订单确认按钮失败 text={text}: {e}")
                        continue

            await asyncio.sleep(0.2)

        if last_error:
            logger.debug(f"[Buyer] 点击订单确认按钮失败: {last_error}")
        await self._log_order_page_button_diagnostics(page)
        return False

    async def _log_order_page_button_diagnostics(self, page: Page) -> None:
        """记录订单页可见按钮/文本摘要，便于定位闲鱼改版文案。"""
        try:
            url = page.url or ""
            summary = await asyncio.wait_for(
                page.evaluate(
                    """() => {
                        const normalize = (value) => (value || '').replace(/\\s+/g, ' ').trim();
                        const isVisible = (el) => {
                            const style = window.getComputedStyle(el);
                            const rect = el.getBoundingClientRect();
                            return style.visibility !== 'hidden'
                                && style.display !== 'none'
                                && rect.width > 0
                                && rect.height > 0
                                && rect.bottom >= 0
                                && rect.top <= window.innerHeight;
                        };
                        return Array.from(document.querySelectorAll('button, a, [role="button"], div, span'))
                            .filter(isVisible)
                            .map((el) => normalize(el.innerText || el.textContent || ''))
                            .filter((text) => text && text.length <= 30)
                            .filter((text, index, arr) => arr.indexOf(text) === index)
                            .slice(0, 80);
                    }"""
                ),
                timeout=2.0,
            )
            logger.warning(f"[Buyer] 订单页未找到确认按钮 url={url} visible_texts={summary}")
        except Exception as e:  # noqa: BLE001
            logger.debug(f"[Buyer] 订单页按钮诊断失败: {e}")

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
            text = (await self._read_body_text(page, timeout=2.0)).lower()
            return any(kw in text for kw in (
                "已下架", "已结束", "暂时缺货", "商品不存在",
            ))
        except Exception:  # noqa: BLE001
            return False

    async def _detect_sold(self, page: Page) -> bool:
        """检测商品详情页是否显示已售出提示

        参照 _is_out_of_stock 的页面文字检测模式，独立检测已售关键词。
        为什么不复用 _is_out_of_stock：已售与已下架是不同业务语义，
        标记的目标字段（is_sold）和返回给用户的错误信息也不同。
        """
        try:
            text = await self._read_body_text(page, timeout=2.0)
            return any(kw in text for kw in (
                "已售出", "已售完", "已售罄", "宝贝已售", "商品已售",
            ))
        except Exception:  # noqa: BLE001
            return False

    async def _read_body_text(self, page: Page, timeout: float = 2.0) -> str:
        """短超时读取 body 文本，避免 SPA 页面卡住抢单流程。"""
        try:
            return await asyncio.wait_for(
                page.text_content("body", timeout=int(timeout * 1000)),  # type: ignore[call-arg]
                timeout=timeout + 0.5,
            ) or ""
        except TypeError:
            return await asyncio.wait_for(page.text_content("body"), timeout=timeout) or ""

    def _mark_item_sold(self, item_id: str) -> None:
        """标记商品已售并同步 task_links.display

        为什么在 buyer 内部直接标记：检测到已售的时机最准确（页面实时状态），
        延迟到路由层标记会增加耦合且可能遗漏。
        """
        try:
            self.repo.mark_sold(item_id)
            logger.info(f"[Buyer] 商品已标记为已售 item={item_id}")
        except Exception as e:  # noqa: BLE001
            # 标记失败不应阻断抢单错误返回，仅记录日志
            logger.warning(f"[Buyer] 标记商品已售失败 item={item_id}: {e}")

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
