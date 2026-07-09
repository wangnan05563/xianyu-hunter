# 闲鱼自动捡漏系统 - 技术设计说明书

> 项目代号：**XianyuHunter**
> 文档版本：v2.0
> 编写日期：2026-06-30
> 配套文档：[requirements.md](./requirements.md)

---

## 1. 文档说明

本文档面向开发与测试，回答"系统怎么实现"。每节给出可直接落地的设计：
- 模块边界与依赖
- 类、接口、关键算法
- 状态机与时序
- 数据表 DDL
- 部署脚本与目录约定

读者应先阅读 [requirements.md](./requirements.md) 了解业务需求。

---

## 2. 架构总览

### 2.1 分层架构

```
┌────────────────────────────────────────────────────────────────┐
│  表示层 (Presentation)                                          │
│  ┌─────────────────────┐  ┌──────────────────────────────┐    │
│  │  Web UI (127.0.0.1)  │  │  CLI (xianyu-hunter)         │    │
│  │  FastAPI + React SPA  │  │  Typer / Click               │    │
│  └──────────┬───────────┘  └────────────┬─────────────────┘    │
│             │              HTTP/WS       │                     │
├─────────────┼────────────────────────────┼─────────────────────┤
│  应用层 (Application)               命令 │ 事件                │
│  ┌──────────▼───────────┐  ┌────────────▼─────────────────┐    │
│  │  REST/WebSocket API  │  │  Command Bus  (asyncio.Queue) │    │
│  └──────────┬───────────┘  └────────────┬─────────────────┘    │
│             │                            │                     │
│  ┌──────────▼────────────────────────────▼─────────────────┐    │
│  │         核心域 (Core Domain)                              │    │
│  │  TaskScheduler │ Collector │ Evaluator │ Buyer │ Notifier│    │
│  └──────────┬──────────────────────────────────────────────┘    │
│             │                            │                     │
├─────────────┼────────────────────────────┼─────────────────────┤
│  基础设施层 (Infrastructure)                                    │
│  ┌──────────▼───────────┐  ┌────────────▼─────────────────┐    │
│  │  Playwright Runtime  │  │  SQLite Repository (DAO)     │    │
│  │  Persistent Context  │  │  Encrypted Storage (DPAPI)   │    │
│  └──────────────────────┘  └────────────────────────────────┘    │
│             │                            │                     │
│  ┌──────────▼───────────┐  ┌────────────▼─────────────────┐    │
│  │  Notifier Channels   │  │  Logger (loguru + rotating)  │    │
│  │  SvrChan/PushPlus/   │  │                                │    │
│  │  Bark Adapters        │  │                                │    │
│  └──────────────────────┘  └────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────┘
```

### 2.2 进程内模块

| 模块 | 角色 | 依赖 |
|---|---|---|
| `TaskScheduler` | 维护任务生命周期、调度 | SQLite, EventBus |
| `Collector` | 闲鱼数据采集 | Playwright, AntiDetect |
| `Evaluator` | 多维卖家画像评估 | Repository |
| `Buyer` | 拍下 / 私聊 | Playwright, AntiDetect |
| `Notifier` | 多渠道推送 | Channel Adapters |
| `AntiDetect` | 行为模拟、指纹修复、QPS 控制 | - |
| `WebServer` | Web UI 后端（FastAPI） | Repository, TaskScheduler |
| `EventBus` | 进程内事件分发（asyncio） | - |
| `Repository` | SQLite 读写 | sqlite3 |
| `ChatbotOrchestrator` | 智能客服对话编排 | RAGEngine, Agent, FAQMatcher |
| `RAGEngine` | 检索增强生成 | EmbeddingService, VectorStore |
| `KBManager` | 知识库管理 | VectorStore, ChromaDB |
| `AboutService` | 关于菜单服务 | BuildInfo, Repository |
| `DashboardService` | 仪表盘统计服务 | Repository, EventBus |
| `BatchRefreshScheduler` | 批量刷新调度 | APScheduler, Collector |
| `ConfigVersionManager` | 配置版本管理 | YAML, FileSystem |

### 2.3 目录结构

```
d:\code\otherProjects\17_xianyu\
├── docs\
│   ├── requirements.md        # 需求规格
│   ├── design.md              # 本文档
│   └── api.md                 # 接口文档（自动生成）
├── src\
│   ├── xianyu_hunter\
│   │   ├── __init__.py
│   │   ├── __main__.py        # CLI 入口
│   │   ├── app.py             # 启动主流程
│   │   ├── config.py          # 配置加载（pydantic）
│   │   ├── domain\            # 领域模型
│   │   │   ├── item.py
│   │   │   ├── seller.py
│   │   │   ├── task.py
│   │   │   ├── order.py
│   │   │   └── events.py
│   │   ├── modules\
│   │   │   ├── scheduler.py
│   │   │   ├── collector.py
│   │   │   ├── evaluator.py
│   │   │   ├── buyer.py
│   │   │   ├── notifier.py
│   │   │   ├── antidetect.py
│   │   │   ├── chatbot/       # 智能客服模块
│   │   │   │   ├── orchestrator.py
│   │   │   │   ├── rag_engine.py
│   │   │   │   ├── agent.py
│   │   │   │   ├── intent_classifier.py
│   │   │   │   ├── kb_manager.py
│   │   │   │   ├── faq_matcher.py
│   │   │   │   ├── context_manager.py
│   │   │   │   └── escalation.py
│   │   ├── infra\
│   │   │   ├── browser.py     # Playwright 封装
│   │   │   ├── repository.py  # SQLite DAO
│   │   │   ├── event_bus.py
│   │   │   ├── logger.py
│   │   │   ├── secrets.py     # DPAPI 加密
│   │   │   ├── selectors.py   # 选择器集中管理
│   │   │   ├── embedding.py       # 向量化服务
│   │   │   ├── vector_store.py    # ChromaDB 适配器
│   │   │   └── repo_chatbot.py    # 对话仓储
│   │   ├── notifiers\
│   │   │   ├── base.py
│   │   │   ├── serverchan.py
│   │   │   ├── pushplus.py
│   │   │   └── bark.py
│   │   ├── web\
│   │   │   ├── server.py      # FastAPI 入口
│   │   │   ├── routes\
│   │   │   │   ├── tasks.py
│   │   │   │   ├── items.py
│   │   │   │   ├── logs.py
│   │   │   │   ├── ws.py      # WebSocket 日志
│   │   │   │   ├── api_chatbot.py     # 智能客服 API
│   │   │   │   ├── api_kb.py          # 知识库管理 API
│   │   │   │   └── api_about.py       # 关于菜单 API
│   │   │   └── static\        # Vue 编译产物
│   │   └── utils\
│   │       ├── retry.py
│   │       └── humanize.py
│   └── pyproject.toml
├── tests\
│   ├── test_collector.py
│   ├── test_evaluator.py
│   ├── test_buyer.py
│   ├── test_notifier.py
│   └── fixtures\
├── scripts\
│   ├── start.cmd              # Windows 启动
│   ├── login.cmd              # 首次登录扫码
│   └── backup.cmd             # 数据备份
├── browser-data\              # Playwright 持久化数据（.gitignore）
├── data\
│   ├── xianyu.db              # SQLite（.gitignore）
│   └── logs\                  # 日志目录（.gitignore）
├── .env.example               # 环境变量示例
├── .gitignore
├── frontend/                  # React 前端（SPA）
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard/     # 仪表盘
│   │   │   ├── Chatbot/       # 智能客服
│   │   │   └── About/         # 关于
│   │   └── components/
└── README.md
```

---

## 3. 模块设计

### 3.1 Domain Models

```python
# domain/task.py
class TaskMode(str, Enum):
    AUTO = "auto"            # 全自动直接拍
    SEMI_AUTO = "semi_auto"  # 推送确认后拍
    CONFIRM = "confirm"      # 仅推送不拍
    NOTIFY_ONLY = "notify"   # 仅推送

@dataclass
class Task:
    id: str
    name: str
    keyword: str
    min_price: float | None
    max_price: float | None
    exclude_words: list[str]
    region: str | None
    cron: str                  # 标准 5 位 cron
    mode: TaskMode             # 默认 CONFIRM
    notifier_channels: list[str]  # ["serverchan", "pushplus", "bark"]
    ai_prompt: str | None
    eval_threshold: int = 60   # 评分阈值
    status: TaskStatus = TaskStatus.RUNNING
    created_at: datetime
    updated_at: datetime

class TaskStatus(str, Enum):
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"
```

```python
# domain/item.py
@dataclass
class ItemSummary:
    id: str
    title: str
    price: float
    region: str
    seller_id: str
    want_cnt: int
    view_cnt: int
    publish_time: datetime
    thumb_url: str

@dataclass
class ItemDetail(ItemSummary):
    description: str
    image_urls: list[str]
    raw_json: dict
```

```python
# domain/seller.py
@dataclass
class SellerProfile:
    id: str
    nick: str
    credit_score: int | None       # 芝麻信用
    register_days: int
    on_sale_count: int
    sold_count: int
    top_category: str | None
    post_count_30d: int
    bad_review_count: int
    in_blacklist: bool
    recent_posts: list[ItemSummary]
```

```python
# domain/events.py
class EventType(str, Enum):
    ITEM_DISCOVERED = "item.discovered"
    EVAL_PASSED = "eval.passed"
    EVAL_REJECTED = "eval.rejected"
    BUY_REQUESTED = "buy.requested"
    BUY_SUCCEEDED = "buy.succeeded"
    BUY_FAILED = "buy.failed"
    NOTIFY_SENT = "notify.sent"
    WAF_TRIGGERED = "waf.triggered"
    LOGIN_EXPIRED = "login.expired"

@dataclass
class Event:
    type: EventType
    task_id: str
    payload: dict
    timestamp: datetime
```

### 3.2 EventBus

```python
# infra/event_bus.py
class EventBus:
    def __init__(self):
        self._subscribers: dict[EventType, list[Callable]] = defaultdict(list)
        self._queue: asyncio.Queue[Event] = asyncio.Queue()

    def subscribe(self, event_type: EventType, handler: Callable):
        self._subscribers[event_type].append(handler)

    async def publish(self, event: Event):
        await self._queue.put(event)

    async def run_forever(self):
        while True:
            event = await self._queue.get()
            for handler in self._subscribers.get(event.type, []):
                try:
                    await handler(event)
                except Exception as e:
                    logger.exception(f"Handler {handler} failed: {e}")
```

### 3.3 AntiDetect（反检测核心）

```python
# modules/antidetect.py
class AntiDetect:
    def __init__(self, browser: Browser, config: AntiDetectConfig):
        self.browser = browser
        self.last_action_at = 0
        self._qps_lock = asyncio.Lock()

    async def human_delay(self, min_ms=200, max_ms=1500):
        """模拟人类思考时间，纳秒级随机抖动"""
        # 关键：分布不是均匀分布，而是 Beta 分布模拟"思考停顿"
        delay = random.betavariate(2, 5) * (max_ms - min_ms) + min_ms
        delay += random.gauss(0, 50)  # 抖动
        await asyncio.sleep(delay / 1000)

    async def throttle(self):
        """全局 QPS ≤ 1"""
        async with self._qps_lock:
            now = time.monotonic()
            elapsed = now - self.last_action_at
            if elapsed < 1.0:
                await asyncio.sleep(1.0 - elapsed + random.uniform(0, 0.3))
            self.last_action_at = time.monotonic()

    async def natural_mouse_move(self, page, target_x, target_y):
        """贝塞尔曲线轨迹，非直线"""
        from_x, from_y = await self._current_mouse(page)
        steps = random.randint(15, 30)
        # 控制点偏移制造弧线
        cp1 = (from_x + (target_x - from_x) * random.uniform(0.3, 0.5) + random.uniform(-50, 50),
               from_y + (target_y - from_y) * random.uniform(0.1, 0.3))
        cp2 = (from_x + (target_x - from_x) * random.uniform(0.5, 0.7) + random.uniform(-50, 50),
               from_y + (target_y - from_y) * random.uniform(0.7, 0.9))
        for i in range(steps + 1):
            t = i / steps
            x = self._bezier(t, from_x, cp1[0], cp2[0], target_x)
            y = self._bezier(t, from_y, cp1[1], cp2[1], target_y)
            await page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.005, 0.020))

    async def remove_webdriver_flag(self, context):
        """关键：每个新上下文注入 stealth 脚本"""
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh']});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            window.chrome = { runtime: {} };
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
            );
        """)
```

### 3.4 Collector（采集器）

```python
# modules/collector.py
class Collector:
    def __init__(self, browser: Browser, antidetect: AntiDetect, repo: Repository):
        self.browser = browser
        self.ad = antidetect
        self.repo = repo
        self.selectors = SelectorRepo()  # 选择器仓库

    async def search(self, keyword: str, max_pages: int = 5) -> list[ItemSummary]:
        """搜索 + 滚动加载完整虚拟列表"""
        page = await self.browser.new_page()
        items: list[ItemSummary] = []
        seen_ids: set[str] = set()
        try:
            url = f"https://www.goofish.com/publish?keyword={quote(keyword)}"
            await page.goto(url, wait_until="domcontentloaded")
            await self.ad.throttle()
            await page.wait_for_selector(self.selectors.SEARCH_CARD, timeout=15000)

            for p in range(max_pages):
                # 滚动到底部触发懒加载
                for _ in range(5):
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await self.ad.human_delay(800, 2000)
                    await page.wait_for_load_state("networkidle", timeout=5000)
                    new_cards = await page.query_selector_all(self.selectors.SEARCH_CARD)
                    if len(new_cards) >= 30:  # 单页约 30 条
                        break

                cards = await page.query_selector_all(self.selectors.SEARCH_CARD)
                for card in cards:
                    item = await self._parse_card(card)
                    if item and item.id not in seen_ids:
                        seen_ids.add(item.id)
                        items.append(item)
                if len(cards) < 30:
                    break  # 末页
                await self._click_next_page(page)
        finally:
            await page.close()
        return items

    async def _parse_card(self, card) -> ItemSummary | None:
        """DOM → ItemSummary"""
        try:
            link = await card.query_selector("a")
            href = await link.get_attribute("href")
            item_id = self._extract_item_id(href)
            title = await (await card.query_selector(self.selectors.CARD_TITLE)).inner_text()
            price_text = await (await card.query_selector(self.selectors.CARD_PRICE)).inner_text()
            price = float(re.findall(r"\d+\.?\d*", price_text)[0])
            ...
            return ItemSummary(id=item_id, title=title, price=price, ...)
        except Exception as e:
            logger.warning(f"parse card failed: {e}")
            return None

    async def detail(self, item_id: str) -> ItemDetail | None:
        """访问商品详情页，采集完整信息"""
        ...
        # 限流：单 IP QPS < 1
        await self.ad.throttle()
        page = await self.browser.new_page()
        try:
            await page.goto(f"https://www.goofish.com/item?id={item_id}")
            await page.wait_for_selector(self.selectors.DETAIL_TITLE)
            # 解析
            title = await page.locator(self.selectors.DETAIL_TITLE).inner_text()
            ...
            return ItemDetail(...)
        except PlaywrightTimeout:
            return None
        finally:
            await page.close()

    async def seller_profile(self, seller_id: str) -> SellerProfile | None:
        """访问卖家主页"""
        ...
```

### 3.5 Evaluator（评估器）

```python
# modules/evaluator.py
class Evaluator:
    def __init__(self, config: EvalConfig):
        self.config = config

    async def evaluate(
        self,
        item: ItemDetail,
        seller: SellerProfile
    ) -> EvalResult:
        scores = {}
        reasons = []

        # 1. 职业卖家识别 (权重 30)
        pro_score, pro_reasons = self._eval_professional(seller)
        scores["professional"] = pro_score
        reasons.extend(pro_reasons)

        # 2. 信用与资质 (权重 30)
        credit_score, credit_reasons = self._eval_credit(seller)
        scores["credit"] = credit_score
        reasons.extend(credit_reasons)

        # 3. 历史纠纷 (权重 25)
        dispute_score, dispute_reasons = self._eval_dispute(seller)
        scores["dispute"] = dispute_score
        reasons.extend(dispute_reasons)

        # 4. 价格与竞价异常 (权重 15)
        price_score, price_reasons = self._eval_price(item, seller)
        scores["price"] = price_score
        reasons.extend(price_reasons)

        # 加权汇总
        weights = self.config.weights  # {"professional":30, "credit":30, ...}
        total = sum(scores[k] * weights[k] for k in scores) / 100

        # 一票否决
        if seller.in_blacklist or seller.credit_score and seller.credit_score < 600:
            return EvalResult(
                score=0, risk_level="extreme",
                dimension_scores=scores, reject_reasons=["blacklist"]+reasons
            )

        if total >= 80:
            risk = "low"
        elif total >= 60:
            risk = "medium"
        elif total >= 40:
            risk = "high"
        else:
            risk = "extreme"

        return EvalResult(
            score=int(total),
            risk_level=risk,
            dimension_scores=scores,
            reject_reasons=reasons if risk in ("high", "extreme") else []
        )

    def _eval_professional(self, s: SellerProfile) -> tuple[int, list[str]]:
        score = 100
        reasons = []
        if s.on_sale_count > 30:
            score -= 40; reasons.append(f"在售{s.on_sale_count}件>30")
        if s.post_count_30d > 15:
            score -= 30; reasons.append(f"30天发布{s.post_count_30d}件>15")
        if s.top_category and s.top_category_ratio > 0.8:
            score -= 20; reasons.append(f"主营类目占比{s.top_category_ratio*100:.0f}%")
        # 描述关键词检测
        for kw in self.config.PROFESSIONAL_KEYWORDS:
            if any(kw in p.title for p in s.recent_posts):
                score -= 15; reasons.append(f"命中职业关键词:{kw}"); break
        return max(score, 0), reasons
    # _eval_credit, _eval_dispute, _eval_price 同理
```

### 3.6 Buyer（下单模块）

```python
# modules/buyer.py
class Buyer:
    def __init__(self, browser: Browser, antidetect: AntiDetect, repo: Repository):
        self.browser = browser
        self.ad = antidetect
        self.repo = repo

    async def buy_now(self, item: ItemDetail) -> OrderSnapshot:
        """打开商品 → 智能选择按钮 → 拍下（不支付）"""
        page = await self.browser.new_page()
        try:
            await page.goto(f"https://www.goofish.com/item?id={item.id}")
            await page.wait_for_selector(self.selectors.DETAIL_TITLE)
            await self.ad.throttle()

            # 智能选择按钮
            buy_btn = await self._find_buy_button(page)
            if not buy_btn:
                return OrderSnapshot(status="not_buyable", ...)

            await self.ad.natural_mouse_move(page, *await buy_btn.bounding_box())
            await buy_btn.click()
            await self.ad.human_delay(500, 1500)

            # 处理中间弹窗
            await self._dismiss_popups(page)

            # 等待"提交订单"页
            await page.wait_for_selector(self.selectors.SUBMIT_ORDER_BTN, timeout=10000)
            await self.ad.throttle()

            # 校验地址
            addr = await page.locator(self.selectors.ADDRESS).inner_text()
            if not self._validate_address(addr):
                return OrderSnapshot(status="address_invalid", ...)

            # 提交（不点击支付）
            await page.locator(self.selectors.SUBMIT_ORDER_BTN).click()
            await self.ad.human_delay(1000, 2000)

            # 抓取订单号
            order_no = await self._extract_order_no(page)
            screenshot_path = await page.screenshot(path=f"data/orders/{order_no}.png")

            return OrderSnapshot(
                order_no=order_no,
                price=item.price,
                status="pending_pay",
                screenshot=screenshot_path,
            )
        except Exception as e:
            await page.screenshot(path=f"data/orders/FAILED_{item.id}.png")
            return OrderSnapshot(status="failed", error=str(e), ...)
        finally:
            await page.close()

    async def _find_buy_button(self, page) -> ElementHandle | None:
        """根据按钮文案智能选择"""
        for selector, keyword in [
            (self.selectors.BTN_BUY_NOW, "立即购买"),
            (self.selectors.BTN_IWANT, "我想要"),
        ]:
            try:
                btn = page.locator(f"{selector}:has-text('{keyword}')").first
                if await btn.count() > 0 and await btn.is_visible():
                    return await btn.element_handle()
            except:
                continue
        return None
```

### 3.7 Notifier（多渠道）

```python
# notifiers/base.py
class INotifier(Protocol):
    name: str
    async def send(self, event: Event) -> NotifyResult: ...

# notifiers/serverchan.py
class ServerChanNotifier(INotifier):
    name = "serverchan"
    def __init__(self, send_key: str):
        self.send_key = send_key
        self.api = "https://sctapi.ftqq.com/{key}.send"

    async def send(self, event: Event) -> NotifyResult:
        title, desp = self._format(event)
        async with aiohttp.ClientSession() as s:
            r = await s.post(self.api.format(key=self.send_key),
                             data={"title": title, "desp": desp})
            return NotifyResult(success=r.status == 200, response=await r.text())

    def _format(self, event: Event) -> tuple[str, str]:
        if event.type == EventType.EVAL_PASSED:
            item = event.payload["item"]
            return (
                f"[捡漏] {item.title[:30]} ¥{item.price}",
                f"### 评估通过\n"
                f"- 卖家评分: {event.payload['score']}\n"
                f"- 风险等级: {event.payload['risk_level']}\n"
                f"- [立即查看]({item.url})\n"
                f"![商品图]({item.thumb_url})"
            )
        # ... 其他事件类型
        return "XianyuHunter", str(event.payload)

# notifiers/__init__.py
NOTIFIER_REGISTRY: dict[str, type[INotifier]] = {
    "serverchan": ServerChanNotifier,
    "pushplus": PushPlusNotifier,
    "bark": BarkNotifier,
}

def create_notifier(name: str, config: dict) -> INotifier:
    cls = NOTIFIER_REGISTRY[name]
    return cls(**config)
```

### 3.8 WebServer

```python
# web/server.py
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="XianyuHunter")

# REST API
app.include_router(tasks_router, prefix="/api/tasks")
app.include_router(items_router, prefix="/api/items")
app.include_router(logs_router, prefix="/api/logs")

# WebSocket 实时日志
@app.websocket("/ws/logs")
async def ws_logs(ws: WebSocket):
    await ws.accept()
    queue = event_bus.subscribe_log()
    try:
        while True:
            log = await queue.get()
            await ws.send_json(log.to_dict())
    except WebSocketDisconnect:
        event_bus.unsubscribe_log(queue)

# 静态资源（Vue 编译产物）
app.mount("/", StaticFiles(directory="src/xianyu_hunter/web/static", html=True))
```

**REST API 端点**：
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/tasks` | 任务列表 |
| POST | `/api/tasks` | 创建任务 |
| PATCH | `/api/tasks/{id}` | 更新任务 |
| POST | `/api/tasks/{id}/start` | 启动 |
| POST | `/api/tasks/{id}/pause` | 暂停 |
| DELETE | `/api/tasks/{id}` | 删除 |
| GET | `/api/items?status=...&task_id=...` | 商品列表（分页） |
| GET | `/api/items/{id}` | 商品详情（含评估结果） |
| POST | `/api/items/{id}/confirm` | 用户确认拍下 |
| POST | `/api/items/{id}/reject` | 用户放弃 |
| GET | `/api/logs?level=...` | 日志列表（分页） |
| WS | `/ws/logs` | 实时日志流 |

**Web UI 页面**：
| 路径 | 说明 |
|---|---|
| `/` | 仪表盘（任务运行状态、最近发现） |
| `/tasks` | 任务列表 + 创建/编辑表单 |
| `/items` | 商品卡片墙 |
| `/items/:id` | 商品详情 + 卖家画像雷达图 |
| `/logs` | 日志流（实时） |
| `/settings` | 推送 Key、登录态、风险阈值 |

---

## 4. 关键流程

### 4.1 任务运行主循环（时序）

```
User          CLI/Web        Scheduler       Collector       Evaluator       Notifier       Buyer
 │              │              │                │                │               │            │
 │  start()     │              │                │                │               │            │
 │─────────────▶│              │                │                │               │            │
 │              │  start()     │                │                │               │            │
 │              │─────────────▶│                │                │               │            │
 │              │              │  cron 触发     │                │               │            │
 │              │              │────────────▶   │                │               │            │
 │              │              │                │ search(kw)     │               │            │
 │              │              │                │─────┐          │               │            │
 │              │              │                │     │打开浏览器/滚动/解析        │            │
 │              │              │                │◀────┘          │               │            │
 │              │              │  [ItemSummary] │                │               │            │
 │              │              │◀───────────────│                │               │            │
 │              │              │                │                │               │            │
 │              │              │─── for each new item ───────────▶               │            │
 │              │              │                │  detail()      │               │            │
 │              │              │                │──┐             │               │            │
 │              │              │                │  │打开详情/解析  │               │            │
 │              │              │                │◀─┘             │               │            │
 │              │              │                │  seller_profile()             │            │
 │              │              │                │──┘             │               │            │
 │              │              │                │  │打开主页       │               │            │
 │              │              │                │◀─┘             │               │            │
 │              │              │                │                │               │            │
 │              │              │                │  evaluate()    │               │            │
 │              │              │                │───────────────▶│               │            │
 │              │              │                │                │               │            │
 │              │              │                │  [EvalResult]  │               │            │
 │              │              │                │◀───────────────│               │            │
 │              │              │                │                │               │            │
 │              │              │─── if score >= threshold ──────▶               │            │
 │              │              │                │                │  send(event)  │            │
 │              │              │                │                │──────────────▶│            │
 │              │              │                │                │               │ 微信推送   │
 │              │              │                │                │               │            │
 │              │              │─── if mode == AUTO ──────────────────────────▶│            │
 │              │              │                │                │               │            │
 │              │              │                │                │               │  buy_now()│
 │              │              │                │                │               │──────────▶│
 │              │              │                │                │               │           │拍下
 │              │              │                │                │               │◀──────────│
 │              │              │                │                │               │           │
 │              │              │                │                │  send(BUY)   │            │
 │              │              │                │                │──────────────▶│            │
 │              │              │                │                │               │ 推送成功   │
```

### 4.2 用户确认流程

```
Notifier                Web UI                Buyer            SQLite
   │                     │                    │                  │
   │  推送(EVAL_PASSED)  │                    │                  │
   │ ──────────────────▶ │ 用户手机微信       │                  │
   │                     │ 点击"确认"链接     │                  │
   │                     │──HTTP POST /confirm│                  │
   │                     │                   │                  │
   │                     │ update(items.status='confirmed')      │
   │                     │─────────────────────────────────────▶│
   │                     │                   │                  │
   │                     │  enqueue buy_task │                  │
   │                     │──────────────────▶│                  │
   │                     │                   │  buy_now(item)   │
   │                     │                   │  ...             │
   │                     │                   │  update(orders)  │
   │                     │                   │─────────────────▶│
   │                     │                   │  send(BUY)       │
   │                     │                   │                  │
```

### 4.3 风控熔断

```python
class WAFGuard:
    def __init__(self, threshold=3, window_sec=3600):
        self.threshold = threshold
        self.window = window_sec
        self.triggered: deque[datetime] = deque()

    def record(self):
        self.triggered.append(datetime.now())
        self._clean()
        if len(self.triggered) >= self.threshold:
            return WAFDecision.PAUSE_ALL
        return WAFDecision.CONTINUE

    def _clean(self):
        cutoff = datetime.now() - timedelta(seconds=self.window)
        while self.triggered and self.triggered[0] < cutoff:
            self.triggered.popleft()
```

---

## 5. 数据模型 DDL

```sql
-- 5.1 任务表
CREATE TABLE tasks (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    keyword         TEXT NOT NULL,
    min_price       REAL,
    max_price       REAL,
    exclude_words   TEXT,        -- JSON array
    region          TEXT,
    cron            TEXT NOT NULL DEFAULT '*/1 * * * *',
    mode            TEXT NOT NULL DEFAULT 'confirm',
    notifier_channels TEXT,      -- JSON array
    ai_prompt       TEXT,
    eval_threshold  INTEGER DEFAULT 60,
    status          TEXT NOT NULL DEFAULT 'running',
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_tasks_status ON tasks(status);

-- 5.2 商品表
CREATE TABLE items (
    id              TEXT PRIMARY KEY,
    task_id         TEXT,
    title           TEXT NOT NULL,
    price           REAL NOT NULL,
    publish_time    DATETIME,
    region          TEXT,
    seller_id       TEXT,
    want_cnt        INTEGER DEFAULT 0,
    view_cnt        INTEGER DEFAULT 0,
    thumb_url       TEXT,
    image_urls      TEXT,        -- JSON
    description     TEXT,
    raw_json        TEXT,        -- 备份原始数据
    first_seen      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);
CREATE INDEX idx_items_seller ON items(seller_id);
CREATE INDEX idx_items_task_first_seen ON items(task_id, first_seen DESC);

-- 5.3 卖家表
CREATE TABLE sellers (
    id              TEXT PRIMARY KEY,
    nick            TEXT,
    credit_score    INTEGER,
    register_days   INTEGER,
    on_sale_count   INTEGER,
    sold_count      INTEGER,
    top_category    TEXT,
    top_category_ratio REAL,
    post_count_30d  INTEGER,
    bad_review_count INTEGER DEFAULT 0,
    in_blacklist    INTEGER DEFAULT 0,
    recent_posts_json TEXT,     -- JSON: 最近发布
    last_visited    DATETIME,
    last_eval       DATETIME
);

-- 5.4 评估结果表
CREATE TABLE evaluations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id         TEXT NOT NULL,
    seller_id       TEXT,
    score           INTEGER NOT NULL,
    risk_level      TEXT NOT NULL,
    dimension_scores TEXT,      -- JSON
    reject_reasons  TEXT,       -- JSON
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES items(id)
);
CREATE INDEX idx_eval_item ON evaluations(item_id);

-- 5.5 订单快照
CREATE TABLE orders (
    id              TEXT PRIMARY KEY,
    item_id         TEXT NOT NULL,
    seller_id       TEXT,
    order_no        TEXT,
    price           REAL,
    status          TEXT NOT NULL,  -- pending_pay / paid / cancelled / failed
    screenshot      TEXT,
    error           TEXT,
    confirmed_at    DATETIME,
    paid_at         DATETIME,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES items(id)
);

-- 5.6 事件日志
CREATE TABLE events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id         TEXT,
    item_id         TEXT,
    stage           TEXT NOT NULL,    -- search/detail/eval/buy/notify/waf
    level           TEXT NOT NULL,    -- INFO/WARN/ERROR
    message         TEXT,
    payload         TEXT,             -- JSON
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_events_task_time ON events(task_id, created_at DESC);
CREATE INDEX idx_events_level_time ON events(level, created_at DESC);
```

---

## 6. 关键算法

### 6.1 选择器集中管理

```python
# infra/selectors.py
class SelectorRepo:
    """闲鱼 DOM 选择器集中仓库，UI 改版时只改这里"""
    SEARCH_CARD = "div[data-testid='search-card']"  # 主备选择器
    CARD_TITLE = "[class*='title']"
    CARD_PRICE = "[class*='price']"
    DETAIL_TITLE = "h1[class*='title']"
    BTN_BUY_NOW = "button"
    BTN_IWANT = "button"
    SUBMIT_ORDER_BTN = "button:has-text('提交订单')"
    ADDRESS = "[class*='address']"

    # 备用选择器（fallback）
    ALT_SEARCH_CARD = "[class*='search-card']"

    @classmethod
    def find_card(cls, page):
        return page.locator(cls.SEARCH_CARD).or_(page.locator(cls.ALT_SEARCH_CARD))
```

### 6.2 增量去重

```python
class ItemDedup:
    def __init__(self, repo: Repository):
        self.repo = repo

    async def filter_new(self, items: list[ItemSummary]) -> list[ItemSummary]:
        if not items:
            return []
        ids = [it.id for it in items]
        existing = await self.repo.items_exist(ids)
        return [it for it in items if it.id not in existing]
```

### 6.3 卖家评估权重（默认，可配置）

```yaml
# config/eval.yaml
weights:
  professional: 30
  credit: 30
  dispute: 25
  price: 15

thresholds:
  on_sale_count: 30           # 超过为职业
  post_count_30d: 15          # 超过为职业
  top_category_ratio: 0.8
  credit_score_min: 600       # 低于一票否决
  bad_review_max: 3           # 超过一票否决
  register_days_min: 30       # 新号加分风险

professional_keywords:
  - 批发
  - 代理
  - 代购
  - 大量
  - 店铺
  - 厂家
  - 直发
```

### 6.4 价格策略

```python
class PriceStrategy:
    def __init__(self, config: PriceConfig):
        self.config = config

    def check(self, item: ItemDetail, market: MarketContext) -> PriceVerdict:
        reasons = []
        # 1. 硬性上限
        if self.config.max_price and item.price > self.config.max_price:
            return PriceVerdict(reject=True, reasons=[f"price {item.price} > max {self.config.max_price}"])
        # 2. 硬性下限（防止 1 元拍下等异常）
        if self.config.min_price and item.price < self.config.min_price:
            return PriceVerdict(reject=True, reasons=[f"price {item.price} < min {self.config.min_price}"])
        # 3. 低于市场参考价
        if market.median_price and item.price > market.median_price * self.config.market_ratio:
            return PriceVerdict(reject=True, reasons=[f"price > median * {self.config.market_ratio}"])
        # 4. 与同类 Top1 卖家价差
        if market.cheaper_seller_count == 0 and item.price > market.median_price * 0.7:
            # 已经是最低价，但仍然高于市场 70%，可疑
            reasons.append("lowest_but_above_market_70%")
        return PriceVerdict(reject=False, reasons=reasons)
```

---

## 7. 状态机

### 7.1 任务状态机

```
                ┌─────────┐
       start    │ STOPPED │  delete
        ──────▶ │         │ ──────▶ (delete)
                └────┬────┘
                     │ run
                     ▼
                ┌─────────┐    pause    ┌────────┐
                │ RUNNING │────────────▶│ PAUSED │
                │         │◀────────────│        │
                └────┬────┘   resume     └────────┘
                     │ waf_trigger
                     ▼
                ┌─────────┐   resolve   ┌─────────┐
                │  ERROR  │────────────▶│ RUNNING │
                │         │◀────────────│         │
                └─────────┘  user_resume└─────────┘
```

### 7.2 订单状态机

```
   ┌──────────┐  confirm   ┌────────────┐  pay  ┌──────┐
   │ detected │ ─────────▶ │ pending_pay│ ────▶ │ paid │
   └──────────┘            └─────┬──────┘       └──────┘
                                 │ timeout/cancel
                                 ▼
                            ┌──────────┐
                            │cancelled │
                            └──────────┘
                                 │ fail
                                 ▼
                            ┌──────────┐
                            │  failed  │ (人工处理)
                            └──────────┘
```

---

## 8. 部署与运维

### 8.1 依赖清单

```toml
# pyproject.toml 关键依赖
[project]
requires-python = ">=3.10"
dependencies = [
    "playwright>=1.40",
    "fastapi>=0.110",
    "uvicorn[standard]>=0.27",
    "typer>=0.9",
    "pydantic>=2.5",
    "pydantic-settings>=2.1",
    "aiohttp>=3.9",
    "loguru>=0.7",
    "apscheduler>=3.10",   # Cron 调度
    "keyring>=24.0",        # Windows DPAPI
    "sqlalchemy>=2.0",      # 简化 DAO
    "pyyaml>=6.0",
    "tenacity>=8.2",        # 重试
]
```

### 8.2 启动脚本

```batch
@echo off
REM scripts\start.cmd
cd /d %~dp0..
call .venv\Scripts\activate
python -m xianyu_hunter start --port 8001
```

### 8.3 首次登录

```batch
@echo off
REM scripts\login.cmd
cd /d %~dp0..
call .venv\Scripts\activate
python -m xianyu_hunter login
REM 脚本会打开浏览器，等待用户扫码，登录态持久化到 browser-data/
```

### 8.4 数据备份

```batch
@echo off
REM scripts\backup.cmd - 每日定时
set TS=%date:~0,4%%date:~5,2%%date:~8,2%
copy data\xianyu.db backup\xianyu_%TS%.db
```

### 8.5 配置示例

```yaml
# config/config.yaml
server:
  host: 127.0.0.1
  port: 8001

browser:
  headless: true              # 是否无头模式（调试时 false）
  user_data_dir: ./browser-data
  viewport:
    width: 1920
    height: 1080

antidetect:
  qps: 1                      # 全局 QPS 上限
  min_delay_ms: 200
  max_delay_ms: 1500
  fail_pause_threshold: 3     # 连续失败次数触发熔断

notifier:
  default_channels: [serverchan, pushplus, bark]
  serverchan:
    send_key: ${SERVERCHAN_KEY}
  pushplus:
    token: ${PUSHPLUS_TOKEN}
  bark:
    server: ${BARK_SERVER}
    key: ${BARK_KEY}

waf:
  enabled: true
  login_check_interval_min: 30
```

### 8.6 .env.example

```bash
# 推送服务密钥（首次启动时填入，启动后用 keyring 加密存储）
SERVERCHAN_KEY=SCT123456ABCDEFG
PUSHPLUS_TOKEN=abcdef123456
BARK_SERVER=https://api.day.app
BARK_KEY=xxxxxxxxxx

# 可选：AI 服务（v1.0 启用）
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
```

### 8.7 启动序列

```
1. 读取 .env → keyring 加密存储推送 Key
2. 加载 config.yaml
3. 启动 SQLite（启用 WAL 模式）
4. 启动 Playwright（持久化 context）
5. 检查 Cookie 有效性，无效则进入登录引导
6. 注册 AntiDetect stealth 脚本
7. 启动 TaskScheduler（加载所有 running 任务）
8. 启动 WebServer（FastAPI）
9. 注册事件订阅（日志写入 events 表 + 推送到 WebSocket）
10. 进入主事件循环
```

---

## 9. 测试策略

| 层级 | 内容 | 工具 |
|---|---|---|
| 单元 | Evaluator 算法、PriceStrategy、Dedup | pytest |
| 集成 | Collector + Repository（mock 浏览器） | pytest + playwright-mock |
| 端到端 | 完整流程（dry-run 模式） | pytest + 真实浏览器（手动触发） |
| 录制回放 | 用 vcrpy 录制闲鱼真实响应，回归测试 | vcrpy |
| 视觉验证 | 截图对比 UI 改版 | playwright snapshot |

**关键测试用例**：

| 编号 | 场景 | 预期 |
|---|---|---|
| T1 | 职业卖家（在售 50 件）评估 | score < 60, risk = high |
| T2 | 黑名单卖家 | 0 分，一票否决 |
| T3 | 价格 < 上限、> 市场 80% | 拒绝（不低于市场参考价） |
| T4 | 网络超时重试 3 次 | 最终成功 |
| T5 | 连续 3 次异常熔断 | 所有任务暂停 + 推送 |
| T6 | 半自动确认 5 分钟未响应 | 订单超时取消 |

---

## 10. 风险与监控指标

### 10.1 运行时指标

```
- discover_rate:  每小时发现新商品数
- pass_rate:      通过评估的占比
- buy_success:    自动下单成功率
- waf_trigger:    风控触发频率
- avg_latency:    从发现到推送的延迟
- login_alive:    登录态持续时间
```

### 10.2 健康检查

```python
async def health_check():
    return {
        "browser": browser.is_alive(),
        "login_valid": await check_login_valid(),
        "tasks_running": count_running_tasks(),
        "db_ok": db.ping(),
        "notifier_ok": await notifier.ping(),
        "last_discover_at": last_discover_time,
    }
```

---

## 11. 实施计划

| 阶段 | 内容 | 交付物 | 估时 |
|---|---|---|---|
| **S0 环境** | Python venv、Playwright 安装、目录结构 | 可运行 hello world | 0.5d |
| **S1 基础设施** | Repository、EventBus、Logger、Config、Secrets | 单元测试通过 | 1d |
| **S2 AntiDetect** | 行为模拟、指纹修复、QPS 限流 | 模拟人类操作通过 | 1d |
| **S3 Collector** | 搜索/详情/卖家主页 | 能稳定抓取真实数据 | 2d |
| **S4 Evaluator** | 4 维评估算法 | 单元测试 + 真实样例验证 | 1d |
| **S5 Notifier** | 三渠道适配器 | 三种渠道各推送一次成功 | 0.5d |
| **S6 Buyer** | 拍下流程（含确认态） | 真实跑通 1 单（dry-run 模式） | 1.5d |
| **S7 Scheduler** | Cron 调度、任务生命周期 | 多任务并行跑 1h 无异常 | 1d |
| **S8 WebServer** | FastAPI 后端 + React 前端 | UI 可配置任务、看日志、看商品 | 2d |
| **S9 集成测试** | 端到端 dry-run | 全流程稳定 1 天 | 1d |
| **总计** | | | **~12d** |

---

## 12. 后续迭代（预留扩展点）

| 扩展 | 接入点 | 工作量 |
|---|---|---|
| 移动端 Appium | 新增 `MobileBuyer` 实现 `IBuyer` Protocol | 大 |
| 多账号 | `BrowserPool` + 任务级账号绑定 | 中 |
| AI 多模态评估 | Evaluator 内置 `AIPlugin` | 中 |
| 议价机器人 | Buyer.send_message 接 LLM | 中 |
| 跨平台比价 | 新增 Collector 子类（转转/爱回收） | 大 |
| 订阅付费化 | WebServer 加 Stripe 集成 | 大 |

---

## 13. 修订记录

| 版本 | 日期 | 修订内容 |
|------|------|----------|
| v1.0 | 2026-06-03 | 初始版本，基于 Playwright + FastAPI + Vue3 架构 |
| v2.0 | 2026-06-30 | 前端迁移至 React + Ant Design；新增智能客服模块（RAG+Agent）；新增关于菜单；新增仪表盘KPI/漏斗/雷达；新增配置版本管理；新增向量数据库维护；新增批量采集；新增钉钉通知渠道；架构调整为 DDD 分层 |

---

*文档结束*
