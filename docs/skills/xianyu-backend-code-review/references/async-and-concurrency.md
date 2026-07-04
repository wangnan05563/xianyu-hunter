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

## 13. 参考

- [asyncio 官方文档](https://docs.python.org/3/library/asyncio.html)
- [Real Python asyncio](https://realpython.com/async-io-python/)
- [FastAPI 异步](https://fastapi.tiangolo.com/async/)
- [SQLAlchemy 异步](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [项目编码规范总入口](../../xianyu-hunter-dev/references/coding-standards.md)
