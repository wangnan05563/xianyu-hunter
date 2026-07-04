# 后端性能审查（Performance）

> **配套技能**：[xianyu-backend-code-review](../SKILL.md)
> **重点**：N+1 查询 / 阻塞调用 / 锁竞争 / 缓存

---

## 1. N+1 查询（PF-01 / PF-05）

### 1.1 预加载

```python
# ❌ N+1
async def list_orders_with_items():
    orders = await session.execute(select(OrderORM))
    for o in orders.scalars():
        item = await session.get(ItemORM, o.item_id)  # N 次查询
        print(item.title)

# ✅ selectinload
async def list_orders_with_items():
    stmt = select(OrderORM).options(selectinload(OrderORM.item))
    orders = await session.execute(stmt)
    for o in orders.scalars():
        print(o.item.title)  # 已预加载
```

### 1.2 批量查询

```python
# ❌ 循环单条
async def get_sellers(items: list[Item]) -> dict[str, Seller]:
    sellers = {}
    for item in items:
        seller = await session.get(SellerORM, item.seller_id)  # N 次
        sellers[item.seller_id] = seller
    return sellers

# ✅ IN 批量
async def get_sellers(items: list[Item]) -> dict[str, Seller]:
    seller_ids = list({item.seller_id for item in items})
    stmt = select(SellerORM).where(SellerORM.id.in_(seller_ids))
    rows = await session.execute(stmt)
    return {s.id: s for s in rows.scalars()}
```

### 1.3 聚合

```python
# ❌ Python 端聚合
items = await repo.list_all()
total_price = sum(item.price for item in items)  # 全表加载

# ✅ 数据库聚合
stmt = select(func.sum(ItemORM.price))
total_price = (await session.execute(stmt)).scalar_one()
```

---

## 2. 分页（PF-02）

### 2.1 限制 + 偏移

```python
async def list_items(page: int = 1, page_size: int = 20):
    offset = (page - 1) * page_size
    stmt = select(ItemORM).offset(offset).limit(page_size)
    return (await session.execute(stmt)).scalars().all()
```

### 2.2 游标分页（大数据量）

```python
async def list_items_cursor(last_id: str | None = None, limit: int = 20):
    stmt = select(ItemORM).order_by(ItemORM.id).limit(limit)
    if last_id:
        stmt = stmt.where(ItemORM.id > last_id)
    return (await session.execute(stmt)).scalars().all()
```

### 2.3 默认限制

```python
# ✅ 任何 list API 都有默认 limit
async def list_items(limit: int = 50, offset: int = 0):  # 默认 50
    stmt = select(ItemORM).offset(offset).limit(min(limit, 200))  # 上限 200
    ...
```

---

## 3. 缓存（PF-03）

### 3.1 配置缓存（lru_cache）

```python
# infra/yaml_config.py
@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    return _load_all()

def reload_config():
    get_config.cache_clear()  # 强制重载
    return _load_all()
```

### 3.2 显式缓存

```python
# infra/cache.py
from cachetools import TTLCache

class Cache:
    def __init__(self, ttl: int = 60, maxsize: int = 1000):
        self._cache = TTLCache(maxsize=maxsize, ttl=ttl)

    def get(self, key):
        return self._cache.get(key)

    def set(self, key, value):
        self._cache[key] = value

# 用法
user_cache = Cache(ttl=300)  # 5 分钟
user = user_cache.get(user_id) or await fetch_user(user_id)
if user:
    user_cache.set(user_id, user)
```

### 3.3 缓存失效

```python
# 写入时失效相关缓存
async def update_item(item_id: str, update: ItemUpdate):
    await repo.upsert(item_id, update)
    cache.delete(f"item:{item_id}")
    cache.delete(f"items:seller:{update.seller_id}")
```

---

## 4. 异步 I/O 性能（PF-04 / PF-09）

### 4.1 避免空 await

```python
# ❌ 无意义
for i in range(100):
    await asyncio.sleep(0)  # 不必要

# ✅ 让步用 await gather
```

### 4.2 共享 aiohttp session

```python
# ❌ 每请求创建
async def fetch():
    async with aiohttp.ClientSession() as session:
        ...

# ✅ 单例 session
http_session: aiohttp.ClientSession | None = None

async def get_session() -> aiohttp.ClientSession:
    global http_session
    if http_session is None or http_session.closed:
        http_session = aiohttp.ClientSession()
    return http_session
```

### 4.3 连接池

```python
# ✅ 限制并发
semaphore = asyncio.Semaphore(10)

async def fetch(url: str):
    async with semaphore:
        async with session.get(url) as resp:
            return await resp.text()
```

---

## 5. 锁与并发（PF-06）

### 5.1 asyncio.Lock

```python
# ✅ async 用 asyncio.Lock
order_lock = asyncio.Lock()

async def place_order(order):
    async with order_lock:  # 不阻塞 event loop
        if await is_duplicate(order):
            return False
        return await save(order)
```

### 5.2 减少锁粒度

```python
# ❌ 大锁
class OrderService:
    def __init__(self):
        self.lock = asyncio.Lock()  # 所有操作都加锁

# ✅ 细粒度锁
class OrderService:
    def __init__(self):
        self.user_locks: dict[str, asyncio.Lock] = {}

    def _get_user_lock(self, user_id: str) -> asyncio.Lock:
        if user_id not in self.user_locks:
            self.user_locks[user_id] = asyncio.Lock()
        return self.user_locks[user_id]
```

---

## 6. 启动优化（PF-07）

### 6.1 lifespan 上下文

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动：初始化共享资源
    await db.create_all()  # 启动时建表
    await browser_manager.warmup()  # 启动时预热浏览器
    scheduler_task = asyncio.create_task(run_scheduler())
    yield
    # 关闭：清理
    scheduler_task.cancel()
    await browser_manager.close()
    await db.close()
```

### 6.2 避免热路径启动

```python
# ❌ 路由内 lazy init
@router.get("/items")
async def list_items():
    if not hasattr(app.state, 'db'):
        app.state.db = await init_db()  # 每次都检查
    return await app.state.db.list_items()

# ✅ lifespan 中初始化
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = await init_db()  # 启动时一次
    yield
```

---

## 7. Pydantic 性能（PF-08）

```python
# ✅ model_dump 比手写快
config = get_config().model_dump()

# ⚠️ 不是所有情况都用
# 简单 dataclass 可以 dict() 更快
```

---

## 8. 日志性能（PF-10）

```python
# ❌ 即使不打印也会格式化
logger.info(f"用户 {user.name} 登录，cookie={cookie}")

# ✅ 用占位符（loguru 支持）
logger.info("用户 {} 登录，cookie={}", user.name, mask(cookie))
# 不打印时不会执行格式化
```

---

## 9. 性能审查 checklist

| 类别 | 检查项 |
|---|---|
| 数据库 | N+1 已避免？批量查询？聚合下推？ |
| 分页 | list API 有 limit？游标分页？ |
| 缓存 | 热数据缓存？TTL 合理？写时失效？ |
| 异步 | 单例 session？连接池？无空 await？ |
| 锁 | asyncio.Lock？粒度合适？ |
| 启动 | lifespan 初始化？路由内无 init？ |
| 日志 | 用占位符？ |
| 外部 API | 限流？超时？失败重试？ |

---

## 10. 性能测试

### 10.1 基准测试

```python
import time

async def benchmark_list():
    start = time.perf_counter()
    items = await repo.list_recent(100)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.1, f"太慢: {elapsed}s"
```

### 10.2 慢查询日志

```python
# infra/db.py
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    echo_pool=False,
    # SQLAlchemy 自带慢查询
)
```

### 10.3 Profiling

```bash
# py-spy
py-spy top --pid <pid>
py-spy dump --pid <pid>

# cProfile
python -m cProfile -o profile.out main.py
```

---

## 11. 复盘：从对话中提炼

### 11.1 案例：配置加载性能（间接相关）

修复前每次 `get_config()` 都重新加载 YAML（如果没用 `@lru_cache`）。

**当前实现**：
```python
@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    return _load_all()
```

**节省**：抢单决策链每次实时读，lru_cache 保证只解析一次。

### 11.2 案例：保存后 reload 关键

`confirmSave` 后必须 `reload_config()`，否则：

```python
# ❌ 危险
async def confirm_save():
    await configApi.save(payload, false)
    # 不 reload → 业务模块继续用旧值
```

**修复**：保存成功后调用 `reload_config()` 失效 lru_cache。

---

## 12. 常见反模式

| 反模式 | 性能影响 | 修复 |
|---|---|---|
| N+1 查询 | O(N) 次 DB 查询 | `selectinload` / `IN` |
| 全表加载 | 内存爆 | 分页 / 聚合 |
| 循环 await | O(N) 串行 | `asyncio.gather` |
| 每请求创建 session | 连接开销 | 单例 / 池 |
| threading.Lock | 阻塞 | `asyncio.Lock` |
| 路由内 init | 每次请求初始化 | lifespan |
| 字符串 f-string 日志 | 总格式化 | 占位符 |
| 缺索引 | 全表扫描 | 迁移加索引 |

---

## 13. 参考

- [SQLAlchemy 性能](https://docs.sqlalchemy.org/en/20/orm/loading_relationships.html)
- [asyncio 性能](https://docs.python.org/3/library/asyncio.html)
- [py-spy](https://github.com/benfred/py-spy)
- [项目编码规范总入口](../../xianyu-hunter-dev/references/coding-standards.md)
