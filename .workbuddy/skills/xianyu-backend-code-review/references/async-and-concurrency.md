# 后端异步与并发审查（Async & Concurrency）

> **配套技能**：[xianyu-backend-code-review](../SKILL.md)

---

## 1. 异步基础规则

### 1.1 必须 async 的场景（AS-01）

所有 I/O 操作必须 `async def`：
- 数据库查询（SQLAlchemy async session）
- HTTP 请求（aiohttp / httpx）
- 文件 I/O（aiofiles）
- 浏览器操作（Playwright async API）
- 外部 API 调用

### 1.2 禁止阻塞调用（AS-02）

```python
# ❌ 严重：在 async 中阻塞
async def fetch_data():
    resp = requests.get(url)         # 阻塞 event loop
    data = open(file).read()          # 阻塞 I/O
    time.sleep(1)                     # 阻塞 sleep
    result = subprocess.run(cmd)      # 阻塞子进程

# ✅ 正确：用 async I/O
async def fetch_data():
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return await resp.json()
```

**检测方法**：
```bash
# 静态扫描：找 async def 中的同步 I/O
grep -nE "async def|requests\.|time\.sleep|open\(|subprocess\." src/xianyu_hunter/
```

---

## 2. 异步 I/O 选择

| 场景 | 同步 | 异步 |
|---|---|---|
| HTTP 客户端 | `requests` | `aiohttp` / `httpx` |
| 数据库 | SQLAlchemy 同步 | SQLAlchemy async |
| 文件 I/O | `open` | `aiofiles` |
| 浏览器 | Playwright sync | Playwright async |
| 子进程 | `subprocess.run` | `asyncio.create_subprocess_exec` |
| Redis | `redis` | `redis.asyncio` |

---

## 3. 限流（AS-05）

### 3.1 asyncio.Semaphore

```python
# ✅ 用 Semaphore 控制并发
class CollectorService:
    def __init__(self, config: AppConfig):
        # 配置驱动，不硬编码
        self.semaphore = asyncio.Semaphore(config.antidetect.qps)

    async def fetch_item(self, item_id: str) -> ItemDTO:
        async with self.semaphore:
            return await self._fetch(item_id)
```

### 3.2 配置驱动

```python
# AppConfig
class AntiDetectConfig(BaseModel):
    qps: int = 1  # 每秒请求数
    max_concurrent: int = 3  # 最大并发

# 启动时校验
@field_validator('qps')
def validate_qps(cls, v: int) -> int:
    if v < 1 or v > 100:
        raise ValueError('qps must be 1-100')
    return v
```

### 3.3 速率限制（QPS 模式）

```python
# 限制每秒请求数
class RateLimiter:
    def __init__(self, qps: int):
        self.interval = 1.0 / qps
        self.last = 0.0
        self.lock = asyncio.Lock()

    async def acquire(self):
        async with self.lock:
            now = time.monotonic()
            wait = self.last + self.interval - now
            if wait > 0:
                await asyncio.sleep(wait)
            self.last = time.monotonic()
```

---

## 4. 并发任务

### 4.1 asyncio.gather（AS-04 / AS-09）

```python
# ✅ 正确：并发执行独立任务
async def fetch_all_items(item_ids: list[str]) -> list[ItemDTO]:
    tasks = [fetch_item(id) for id in item_ids]
    return await asyncio.gather(*tasks)

# ❌ 反例：串行 await
async def fetch_all_items(item_ids: list[str]) -> list[ItemDTO]:
    results = []
    for id in item_ids:
        results.append(await fetch_item(id))  # 慢
    return results
```

### 4.2 asyncio.TaskGroup（Python 3.11+）

```python
# ✅ TaskGroup 自动处理异常
async def fetch_multiple():
    async with asyncio.TaskGroup() as tg:
        task_a = tg.create_task(fetch_a())
        task_b = tg.create_task(fetch_b())
    return task_a.result(), task_b.result()
```

### 4.3 错误处理

```python
# gather 默认 return_exceptions=False：任一失败全失败
try:
    results = await asyncio.gather(*tasks)
except SomeError as e:
    logger.exception("部分任务失败")

# 收集所有结果（含失败的）
results = await asyncio.gather(*tasks, return_exceptions=True)
for r in results:
    if isinstance(r, Exception):
        logger.error(f"任务失败: {r}")
    else:
        process(r)
```

---

## 5. 资源管理（AS-10）

### 5.1 async with 上下文

```python
# ✅ 正确
async def fetch_with_session():
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return await resp.json()
# session / response 自动关闭

# ❌ 反例：手动管理
async def fetch_no_with():
    session = aiohttp.ClientSession()
    resp = await session.get(url)  # 异常时未关闭
    return await resp.json()
```

### 5.2 单例长连接

```python
# infra/http.py
class HttpClient:
    _instance: aiohttp.ClientSession | None = None

    @classmethod
    def get_session(cls) -> aiohttp.ClientSession:
        if cls._instance is None or cls._instance.closed:
            cls._instance = aiohttp.ClientSession()
        return cls._instance

    @classmethod
    async def close(cls):
        if cls._instance and not cls._instance.closed:
            await cls._instance.close()
            cls._instance = None

# lifespan 中管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await HttpClient.close()
```

### 5.3 Playwright 资源

```python
# infra/browser.py
class BrowserManager:
    _playwright: Playwright | None = None
    _browser: Browser | None = None

    async def get_browser(self) -> Browser:
        if self._browser is None or not self._browser.is_connected():
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch()
        return self._browser

    async def close(self):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
```

---

## 6. 后台任务

### 6.1 启动后台任务

```python
# web/app.py
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动
    scheduler_task = asyncio.create_task(run_scheduler())
    yield
    # 关闭
    scheduler_task.cancel()
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass

app = FastAPI(lifespan=lifespan)
```

### 6.2 不阻塞请求

```python
# ❌ 阻塞：长任务在请求中执行
@router.post("/start-collection")
async def start_collection():
    await collect_all_items()  # 可能跑几小时
    return {"status": "ok"}

# ✅ 正确：异步启动 + 状态汇报
@router.post("/start-collection")
async def start_collection(background: BackgroundTasks):
    background.add_task(collect_all_items)
    return {"status": "started", "task_id": get_task_id()}
```

### 6.3 任务状态

```python
# infra/task_status.py
class TaskStatus:
    _statuses: dict[str, dict] = {}

    @classmethod
    def update(cls, task_id: str, status: dict):
        cls._statuses[task_id] = status

    @classmethod
    def get(cls, task_id: str) -> dict | None:
        return cls._statuses.get(task_id)
```

---

## 7. 锁与同步原语

### 7.1 asyncio.Lock（PF-06）

```python
# ✅ 异步锁
class OrderService:
    def __init__(self):
        self.lock = asyncio.Lock()

    async def place_order(self, order: Order) -> bool:
        async with self.lock:
            if await self._is_duplicate(order):
                return False
            return await self._place(order)

# ❌ 反例：threading.Lock 阻塞 event loop
import threading
self.lock = threading.Lock()  # 在 async 中用会让 event loop 卡死
```

### 7.2 资源池

```python
# 数据库连接池（SQLAlchemy 异步）
engine = create_async_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
)
```

---

## 8. 取消与超时

### 8.1 超时

```python
# ✅ 显式超时
async def fetch_with_timeout():
    try:
        async with asyncio.timeout(30):  # Python 3.11+
            return await slow_api_call()
    except asyncio.TimeoutError:
        logger.warning("API 调用超时")
        raise HTTPException(504, detail="上游服务超时")
```

### 8.2 取消传播

```python
async def parent_task():
    task = asyncio.create_task(child_task())
    await asyncio.sleep(5)
    task.cancel()  # 取消子任务
    try:
        await task
    except asyncio.CancelledError:
        pass

async def child_task():
    try:
        await asyncio.sleep(100)
    except asyncio.CancelledError:
        # 清理资源
        await cleanup()
        raise  # 必须 re-raise
```

### 8.3 async 阻塞调用超时保护范式（v4.48.0）

> 本节对应 `xianyu-hunter-dev` v4.48.0 meta-rule #80 / B-REVIEW-226，配套 `config.yaml` 的 `async_timeout_protection` 节点。背景：浏览器登录成功后 Cookie 导出阶段 `context.cookies()` 与 `bc.storage_state()` 缺少 `asyncio.wait_for` 超时保护，Playwright IPC 阻塞导致子进程心跳停滞，后端 90s 后误判卡死并 kill 子进程，丢失已登录 Cookie。

**核心范式**：所有可能永久挂起的 async API 调用必须用 `asyncio.wait_for(coro, timeout=...)` 包裹，超时值按调用成本分类从 config 读取，禁止硬编码。

```python
import asyncio
from xianyu_hunter.config import load_config

cfg = load_config()
_ts = cfg.async_timeout_protection.timeout_by_category

async def export_cookies(context, bc):
    # heavy_serialize 类（10s）：Playwright 跨 IPC 序列化所有 cookies + storage
    timeout = _ts.heavy_serialize
    try:
        cookies = await asyncio.wait_for(context.cookies(), timeout=timeout)
        storage = await asyncio.wait_for(bc.storage_state(), timeout=timeout)
        return cookies, storage
    except asyncio.TimeoutError:
        # fallback_strategy: best_effort - 返回空 cookies 并告警
        logger.warning("cookie export timed out after %.1fs", timeout)
        return [], {}
```

**调用成本分类**（从 `async_timeout_protection.timeout_by_category` 读取）：
- `lightweight_read`（5s）：`page.title()` / `page.url()`，单次 IPC 读
- `heavy_serialize`（10s）：`context.cookies()` / `bc.storage_state()` / `page.snapshot()`，跨 IPC 序列化全部状态
- `evaluate`（15s）：`page.evaluate()`，可能跑任意 JS 逻辑

**不适用**：`page.goto(timeout=...)` / `wait_for_load_state(timeout=...)` 已自带 timeout 参数，无需包裹；同步 API 调用；纯计算型 async 函数。

**子进程心跳协同**（meta-rule #81 / B-REVIEW-227）：在 `subprocess.Popen` + status file 心跳架构中，每阶段独立 status + 独立超时阈值，阶段内阻塞调用累计超时 < 心跳阈值 × (1 - safety_margin)。详见 `references/browser-subprocess-patterns.md` 第八章。

**跨代码块一致性**（meta-rule #82 / B-REVIEW-228）：同一 API 在 ≥2 处调用时保护措施必须一致，以更严格者为准。详见 `references/browser-subprocess-patterns.md` 第 8.3 节。

---

## 9. 异步测试

### 9.1 pytest-asyncio

```python
import pytest

@pytest.mark.asyncio
async def test_fetch_data():
    result = await fetch_data()
    assert result is not None
```

### 9.2 Mock 异步函数

```python
from unittest.mock import AsyncMock

async def test_with_mock():
    mock_service = AsyncMock()
    mock_service.buy.return_value = OrderDTO(...)
    result = await test_function(mock_service)
    mock_service.buy.assert_called_once()
```

---

## 10. 常见反模式

| 反模式 | 问题 | 修复 |
|---|---|---|
| async 中 `requests.get` | 阻塞 event loop | `aiohttp` |
| async 中 `time.sleep` | 阻塞 event loop | `await asyncio.sleep` |
| async 中 `open().read()` | 阻塞 I/O | `aiofiles.open` |
| 串行 `for + await` | 慢 | `asyncio.gather` |
| `except Exception: pass` | 吞错 | 记录 + 上抛 |
| `threading.Lock` 在 async | 阻塞 | `asyncio.Lock` |
| 手动 `session = ...` | 资源未关 | `async with` |
| 长任务在请求中 | 阻塞 HTTP | `BackgroundTasks` |

---

## 11. 审查 checklist

| 类别 | 检查项 |
|---|---|
| 阻塞 | async 中无 `requests` / `time.sleep` / `open` / `subprocess`？ |
| 库选择 | HTTP 用 aiohttp / httpx？DB 用 async session？ |
| 限流 | 外部 API 用 Semaphore？限流走配置？ |
| 并发 | 独立任务用 gather？串行 await 优化？ |
| 资源 | `async with` 上下文？长连接单例？ |
| 后台任务 | 长任务用 BackgroundTasks？不阻塞请求？ |
| 锁 | 用 asyncio.Lock 不用 threading.Lock？ |
| 超时 | 外部调用有超时？ |
| 测试 | 用 pytest-asyncio？mock 异步函数？ |

---

## 12. 复盘：从对话中提炼

### 12.1 反模式 1：浅合并导致覆盖（async 无关但相关）

虽然本次问题不是 async，但抢单决策链涉及**实时读取配置**：

```python
# ✅ 正确：每次决策实时读
async def should_auto_buy(self, item: Item) -> bool:
    config = get_config()  # 不缓存，实时读
    score = evaluate(item, config.eval)
    return score >= config.eval.auto_buy_score
```

**好处**：用户改 `auto_buy_score` 后**立即生效**，无需重启。

### 12.2 反模式 2：限流硬编码

```python
# ❌ 反例
self.semaphore = asyncio.Semaphore(3)  # 硬编码

# ✅ 正确：走配置
self.semaphore = asyncio.Semaphore(config.antidetect.max_concurrent)
```

---

## 13. async_timeout_protection 审查要点

> 本章是 `xianyu-hunter-dev` v4.48.0 meta-rules #80/#81/#82 的审查速查。配套配置：`config.yaml` 的 `async_timeout_protection` / `subprocess_heartbeat` / `consistency_check` 三个节点。

### 13.1 B-REVIEW-226：async 阻塞调用超时保护

**审计信号**：`grep -rnP "await\s+\w+\.(cookies|storage_state|snapshot|title|url|evaluate)\("` 命中行无 `asyncio.wait_for` 包裹 → 违规。

**修复范式**：
```python
# ❌ 违规
cookies = await context.cookies()

# ✅ 合规
timeout = cfg.async_timeout_protection.timeout_by_category.heavy_serialize
cookies = await asyncio.wait_for(context.cookies(), timeout=timeout)
```

**配置节点**：`async_timeout_protection.enabled` / `async_timeout_protection.timeout_by_category.{lightweight_read,heavy_serialize,evaluate}` / `async_timeout_protection.fallback_strategy` / `async_timeout_protection.audit_grep_pattern`

**适用**：Playwright async API（cookies/storage_state/snapshot/title/url/evaluate）、httpx 长连接、aiohttp websocket。
**不适用**：Playwright 自带 `timeout` 参数的调用（page.goto/wait_for_load_state）、同步 API、一次性调用且失败即终止的场景。

### 13.2 B-REVIEW-227：子进程心跳与阶段超时协同

**审计信号**：同文件同时出现 `subprocess.Popen` + `status_file`（或 status file 写入逻辑）→ 触发该检查点。

**核心公式**：
```
阶段允许累计超时 = subprocess_heartbeat.timeout_by_status[stage] × (1 - subprocess_heartbeat.safety_margin)
```

阶段内所有 `asyncio.wait_for` 的 timeout 之和必须 < 阶段允许累计超时，否则后端会在阶段未完成时误判卡死。

**配置节点**：`subprocess_heartbeat.enabled` / `subprocess_heartbeat.timeout_by_status.{starting,opening,running,waiting,already_logged}` / `subprocess_heartbeat.safety_margin`（默认 0.3）/ `subprocess_heartbeat.max_accumulated_timeout_warn`

**适用**：subprocess.Popen + status file 心跳架构；多阶段长时间任务（登录→导出→采集）。
**不适用**：同步请求-响应模式（FastAPI 路由直接 await）；后台一次性任务；纯前端状态管理。

### 13.3 B-REVIEW-228：跨代码块一致性检查

**审计信号**：扫描 `consistency_check.scan_paths` 列出的文件，对同一 API 名出现 ≥ `consistency_check.min_occurrences` 次的调用点进行保护措施对比；不一致即触发违规。

**修复策略**：以更严格者为准。若一处有 `asyncio.wait_for` 而另一处无，则无保护处必须补齐至与有保护处一致（不能反向「为了统一而移除保护」）。

**配置节点**：`consistency_check.enabled` / `consistency_check.min_occurrences`（默认 2）/ `consistency_check.scan_paths`

**适用**：同一 API 在多处调用的场景；复用代码片段（多个登录方式共享 Cookie 导出逻辑）；重构后检查是否漏改。
**不适用**：首次实现的唯一调用点；故意差异化的实现（测试 stub vs 生产代码）；不同框架的类似操作（Playwright page.goto() vs httpx client.get()）。

### 13.4 B-REVIEW-331：事件驱动基础设施启动解耦（EVENT-BUS-STARTUP-DECOUPLING）🆕v4.68 experimental

**问题模式**：事件总线/消息队列的消费者循环（如 `EventBus.run_forever()`）被嵌套在业务调度器启动函数内部（如 `start_scheduler_in_background` 的 `_scheduler_loop`），消费者循环启动受制于业务条件——"是否有 RUNNING 任务""collector 是否就绪""环境变量是否开启"任一不满足则永不启动。后续运行时新增任务时 `publish_nowait` 事件入队但无消费者，订阅者（NotifierHub）永远收不到事件，钉钉等通知静默失效且**无任何报错日志**。

**审查要点**：

1. **消费者循环独立启动**（grep `run_forever\|consume_loop\|_dispatch` 定位消费者循环 → 检查是否嵌套在业务调度器函数内部）
   - ✅ 独立启动函数（如 `start_event_bus_in_background`），启动条件独立于业务任务
   - ❌ 嵌套在 `_scheduler_loop` 内部，受 `if not workers: return` 等业务条件阻断

2. **启动顺序：基础设施先于业务调度器**（grep `_on_startup\|startup` → 检查调用顺序）
   - ✅ `await start_event_bus_in_background(container)` 在 `await start_scheduler_in_background(container)` 之前
   - ❌ EventBus 启动在调度器启动之后或被调度器函数包裹

3. **停止顺序：基础设施后于业务调度器**（grep `_on_shutdown\|shutdown` → 检查停止顺序）
   - ✅ 先 `_scheduler_task.cancel()`，后 `_event_bus_task.cancel()`
   - ❌ EventBus 先于调度器停止（业务停止时 publish 的终态事件丢失）

4. **幂等防护**（grep 启动函数 → 检查是否含 `if _task is not None and not _task.done(): return`）
   - ✅ 已在运行则跳过，避免多个消费者竞争同一队列
   - ❌ 无幂等检查，重复调用产生多个消费者

5. **异常隔离**（grep 消费者循环 → 检查 except 块）
   - ✅ 除 `CancelledError` 外的异常 `logger.exception` 记录
   - ❌ 异常静默退出（task 死亡但无日志，后续事件全部丢失）

6. **运行时入口补启动**（grep `control_task\|resume\|restart` → 检查是否补启动基础设施）
   - ✅ API/CLI resume/restart 时检查 `_event_bus_task` 是否运行，未运行则自动启动
   - ❌ 假设"启动时一次性决定"，运行时新增任务时基础设施未就绪

**正例**：
```python
# ✅ 独立启动函数 + 幂等防护 + 异常隔离
async def start_event_bus_in_background(container):
    global _event_bus_task
    if _event_bus_task is not None and not _event_bus_task.done():
        logger.info("EventBus 已在运行，跳过")
        return
    async def _bus_loop():
        try:
            logger.info("EventBus 主循环启动")
            await container.event_bus.run_forever()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception(f"EventBus 异常退出: {e}")
    _event_bus_task = asyncio.create_task(_bus_loop())

# ✅ startup 中先 EventBus 后调度器
if _should_start_scheduler():
    await start_event_bus_in_background(container)
    await start_scheduler_in_background(container)
```

**反例**：
```python
# ❌ 消费者循环嵌套在业务调度器内部，受业务条件阻断
async def start_scheduler_in_background(container):
    if not container.collector: return   # ← 阻断 EventBus
    if not workers: return                 # ← 阻断 EventBus
    async def _scheduler_loop():
        bus_task = asyncio.create_task(container.event_bus.run_forever())  # 嵌套
```

**配置节点**：`event_bus_startup_decoupling.enabled` / `infrastructureTypes` / `startupOrder` / `shutdownOrder` / `requireIdempotentGuard` / `requireExceptionIsolation` / `requireStartupLog`

**适用**：EventBus/MessageQueue 消费者循环；发布-订阅模式基础设施；后台调度器依赖的事件分发机制；Worker publish 事件到队列、由独立消费者分发给 Notifier 的模式。
**不适用**：同步调用（无 pub/sub）；一次性任务；进程内函数直接 invoke；前端组件间通信（React Context/Zustand）。

**与既有审查点关系**：
- B-REVIEW-178（SCHEDULER-RUNTIME-TOGGLE-SYMMETRY）：管"调度器运行时开关对称性"，本审查点管"消费者循环启动条件解耦"，互补
- step 107 审查（启动钩子完整性）：管"组件覆盖"，本审查点管"启动条件"，互补

**历史教训**：2026-07-26 评分 80 以上商品未触发钉钉通知。配置全正常，根因是 `EventBus.run_forever()` 嵌套在 `_scheduler_loop` 内部，启动时无 RUNNING 任务则 EventBus 永不启动，且 `api_tasks.py` 的 resume/restart 不补启动。修复后抽离独立启动函数。

## 14. 参考

- [asyncio 官方文档](https://docs.python.org/3/library/asyncio.html)
- [Real Python asyncio](https://realpython.com/async-io-python/)
- [FastAPI 异步](https://fastapi.tiangolo.com/async/)
- [SQLAlchemy 异步](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [项目编码规范总入口](../../xianyu-hunter-dev/references/coding-standards.md)
