# 性能与安全编码规范

> 本文档基于闲鱼猎人项目实际排查解决的问题提炼，列举数据库性能优化、安全性、状态管理语义正确性及问题排查方法论方面的编码规范。开发时必须严格遵守带【强制】标记的条文，【建议】条文应在合理场景下采纳。

---

## 一、数据库性能优化

### PS-001: 循环内数据库查询必须批量预查询 【强制】

**问题描述**

去重检查在循环内逐个查询 `get_recently_collected_item_ids([detail.id], ...)`，导致 N+1 查询。当 `new_items` 数量较多时，数据库往返次数线性增长，严重影响性能。

**规范条文**

循环内的数据库查询必须批量预查询，用 `set` 缓存结果，循环内只查缓存。批量查询应在循环外一次性完成。

**代码示例**

正面示例：

```python
# 循环前批量预查询
recent_collected_cache: set[str] | None = None
if eval_cfg and eval_cfg.auto_collect_official:
    all_item_ids = [item.id for item in new_items if item.id]
    if all_item_ids:
        recent_collected_cache = self.repo.get_recently_collected_item_ids(
            all_item_ids,
            eval_cfg.auto_collect_dedup_window_minutes,
        )

# 循环内优先用缓存
if recent_collected_cache is not None:
    recent_ids = recent_collected_cache
elif self.repo is not None:
    recent_ids = self.repo.get_recently_collected_item_ids([detail.id], window)
```

反面示例：

```python
# 循环内逐个查询（N+1）
for item in new_items:
    recent_ids = self.repo.get_recently_collected_item_ids([item.id], window)
```

**适用场景**

任何在循环内查询数据库的场景。

**不适用场景**

循环次数极少（<=3）的场景，此时批量预查询的代码复杂度收益不显著。

---

### PS-002: JSON 字段查询必须用 json_extract 替代 LIKE 【强制】

**问题描述**

stats 端点用 `payload.like('%"data_source"%')` 做全表扫描，无法利用索引，且容易匹配到非目标字段。

**规范条文**

SQLite/MySQL 的 JSON 字段查询必须用 `json_extract()` 函数替代 `LIKE`，避免全表扫描并提升语义准确性。

**代码示例**

正面示例：

```python
from sqlalchemy import func

success_count = conn.execute(
    select(func.count())
    .select_from(EventRow)
    .where(EventRow.type == "eval.scored")
    .where(func.json_extract(EventRow.payload, '$.data_source') == 'official')
).scalar() or 0
```

反面示例：

```python
# LIKE 全表扫描，无法用索引
success_count = conn.execute(
    select(EventRow)
    .where(EventRow.payload.like('%"data_source": "official"%'))
).count()
```

**适用场景**

SQLite/MySQL 的 JSON 字段查询。

**不适用场景**

非 JSON 字段的模糊查询；需要全文检索的场景应使用专门的全文索引方案。

---

## 二、安全性规范

### PS-003: 异常消息必须脱敏后存储 【强制】

**问题描述**

`str(e)[:500]` 可能包含 token/Cookie 等敏感信息，直接写入数据库后会泄露到 events 表和前端，造成安全风险。

**规范条文**

异常消息写入数据库/日志/前端前，必须用正则脱敏 token/Cookie 等敏感信息，并对结果做长度截断。

**代码示例**

正面示例：

```python
import re

_SENSITIVE_PATTERNS = [
    re.compile(r'(token=)[^&\s"\'<>]+', re.IGNORECASE),
    re.compile(r'((?:[Cc]ookie)\s*:\s*)[^\r\n]+'),
    re.compile(r'(_m_h5_tk=)[^;]+'),
    re.compile(r'(unb=)[^;]+'),
    re.compile(r'(cookie2=)[^;]+'),
    re.compile(r'(sgcookie=)[^;]+'),
]

def _sanitize_error(text: str, max_len: int = 500) -> str:
    """对异常消息脱敏后截断，避免 token/Cookie 泄露"""
    sanitized = text
    for pattern in _SENSITIVE_PATTERNS:
        sanitized = pattern.sub(r'\1***', sanitized)
    return sanitized[:max_len]

# 使用
error_msg = _sanitize_error(str(e))
```

反面示例：

```python
error_msg = str(e)[:500]  # 可能泄露 token/Cookie
```

**适用场景**

任何将异常消息存储或传输到外部的场景（写入数据库、记录日志、返回前端、上报监控等）。

**不适用场景**

仅在内存中处理的异常（不持久化/不传输）。

---

### PS-004: 敏感信息脱敏模式必须提取为模块级常量 【强制】

**问题描述**

在函数内定义脱敏正则会导致每次调用都重新编译，且难以复用和维护。

**规范条文**

脱敏正则模式必须提取为模块级常量（通常以 `_SENSITIVE_PATTERNS` 命名），禁止在函数内定义。模块级常量在模块加载时编译一次，便于复用与统一维护。

**适用场景**

任何有脱敏需求的场景。

**代码示例**

正面示例：

```python
# 模块级常量，模块加载时编译一次
_SENSITIVE_PATTERNS = [
    re.compile(r'(token=)[^&\s"\'<>]+', re.IGNORECASE),
    re.compile(r'((?:[Cc]ookie)\s*:\s*)[^\r\n]+'),
]

def _sanitize_error(text: str) -> str:
    sanitized = text
    for pattern in _SENSITIVE_PATTERNS:
        sanitized = pattern.sub(r'\1***', sanitized)
    return sanitized
```

反面示例：

```python
def _sanitize_error(text: str) -> str:
    # 每次调用都重新编译，且难以复用
    patterns = [
        re.compile(r'(token=)[^&\s"\'<>]+', re.IGNORECASE),
        re.compile(r'((?:[Cc]ookie)\s*:\s*)[^\r\n]+'),
    ]
    for pattern in patterns:
        text = pattern.sub(r'\1***', text)
    return text
```

---

## 三、状态管理语义正确性

### PS-005: 计数器语义必须与变量名一致 【强制】

**问题描述**

`_consecutive_collect_failures` 仅在失败时自增、成功时不清零，导致实际语义变成"累计失败"而非"连续失败"，最终在累计失败次数达到阈值时错误触发暂停。

**规范条文**

计数器的语义必须与变量名一致——"连续失败计数器"必须在成功时清零，否则应改名为"累计失败计数器"（如 `_total_failures`）。命名与行为任何一方变更时，必须同步另一方。

**代码示例**

正面示例：

```python
# 成功时清零连续失败计数器
await self.official_collect_fn(detail.id, self.task.id)
stats.official_collected += 1
self._consecutive_collect_failures = 0  # 连续失败语义：成功时重置
```

反面示例：

```python
# 成功时不清零，导致"累计失败"触发暂停
await self.official_collect_fn(detail.id, self.task.id)
stats.official_collected += 1
# 缺少 self._consecutive_collect_failures = 0
```

**适用场景**

任何有状态计数器的场景。

**不适用场景**

确实需要累计统计的场景（此时变量名应改为 `_total_failures` 等表达累计语义的名称）。

---

### PS-006: 前端阈值必须从后端配置获取 【强制】

**问题描述**

前端用 `collectStats.failed >= 3` 硬编码阈值判断"已暂停"，且 `failed` 是累计数而非连续数，与后端实际暂停逻辑（基于连续失败）不一致，导致前端显示与后端状态脱节。

**规范条文**

阈值/限制值必须从后端配置获取，不得在前端硬编码。前端状态判断应使用后端返回的 `is_paused` 布尔值，而非自行根据计数器推断。

**代码示例**

正面示例：

```tsx
// 后端返回 is_paused + fail_pause_threshold
{collectStats.is_paused && (
  <Tag color="red">
    已暂停（连续失败达阈值 {collectStats.fail_pause_threshold} 次）
  </Tag>
)}
```

反面示例：

```tsx
// 硬编码阈值，且用累计数而非连续数
{collectStats.failed >= 3 && <Tag color="red">已暂停</Tag>}
```

**适用场景**

任何前端判断业务状态的场景。

**不适用场景**

纯 UI 状态（如 loading/visible/折叠展开）的判断。

---

### PS-007: 新一轮处理必须重置上一轮状态 【强制】

**问题描述**

`_consecutive_collect_failures` 未在新一轮 `run_once` 开始时重置，导致上一轮的失败延续到本轮，使新一轮在尚未发生任何失败时就接近或达到暂停阈值。

**规范条文**

跨商品/跨轮次累积的状态计数器，必须在新一轮处理开始时重置，保证每轮的状态起点是干净的。

**代码示例**

正面示例：

```python
async def run_once(self) -> RunResult:
    stats = RunStats()
    # 新一轮重置上一轮的连续失败计数
    self._consecutive_collect_failures = 0
```

反面示例：

```python
async def run_once(self) -> RunResult:
    stats = RunStats()
    # 未重置 _consecutive_collect_failures，上一轮失败会延续到本轮
```

**适用场景**

任何跨轮次累积的状态（连续失败计数、重试计数、阶段状态等）。

**不适用场景**

需要跨轮次保留的历史数据（如总采集数、运行日志等）。

---

## 四、问题排查方法论

### PS-008: 问题排查的标准化流程 【建议】

**规范条文**

运行时问题排查必须遵循以下标准化流程，避免遗漏关键环节：

1. 明确问题现象（复现条件、预期 vs 实际）
2. 追踪调用链（前端→后端→外部 API）
3. 对比参数传递（多入口差异）
4. 定位代码缺陷（静态分析）
5. 查看日志确认运行时状态
6. 提出解决方案
7. 应用修复并语法校验
8. 添加调试日志/测试用例验证
9. 用户验证

**适用场景**

任何运行时问题的排查。

**不适用场景**

纯代码风格/命名问题（直接静态分析即可，无需走完整流程）。

---

### PS-009: 修复后必须验证假设 【强制】

**问题描述**

价格问题首次修复后用户反馈"问题依然存在"，说明仅凭代码静态分析无法确认修复有效——实际运行时的数据流可能与预期不同。

**规范条文**

修复后必须用实际数据（日志/测试用例）验证修复效果，不能仅凭代码分析就认定修复成功。验证证据应包含在修复说明中。

**适用场景**

任何涉及数据提取/转换/过滤的修复。

**不适用场景**

纯逻辑修复且有测试覆盖的场景（测试通过即可作为验证证据）。

---

## 五、异步与并发性能

### PS-010: async 函数中同步 DB 调用必须用 run_in_executor 包装 【强制】

**问题描述**

FastAPI async 路由内直接调用同步 DB API（如 SQLite 的 `session.execute`）会阻塞事件循环，导致并发请求被串行化，响应时间线性增长。

**规范条文**

在 `async def` 函数体内调用同步 DB/同步外部库时，必须用 `await loop.run_in_executor(None, sync_func)` 包装，将阻塞操作放到线程池执行。**禁止**在 async 路由内直接调用同步 ORM 方法。

**代码示例**

正面示例：

```python
async def list_task_links(...):
    loop = asyncio.get_event_loop()
    # 同步 DB 调用包装到线程池，避免阻塞事件循环
    result = await loop.run_in_executor(
        None,
        lambda: repo.list_and_count_task_links(task_id, offset, limit)
    )
    return result
```

反面示例：

```python
async def list_task_links(...):
    # 直接调用同步 DB 方法，阻塞事件循环
    result = repo.list_and_count_task_links(task_id, offset, limit)
    return result
```

**适用场景**

FastAPI async 路由调用同步 ORM（SQLAlchemy 同步模式）、同步外部库。

**不适用场景**

已使用原生 async 驱动（如 asyncpg/aiomysql/databases）；此时再包 `run_in_executor` 是反模式。

---

### PS-011: 优先级锁设计——high 等待时 low 主动让出 【建议】

**问题描述**

浏览器实例等共享资源被多个任务竞争时，实时用户请求（如"实时查询"按钮）与后台周期性搜索任务使用同一把普通 `asyncio.Lock`，导致实时请求被后台任务长时间阻塞（15-20s）。

**规范条文**

共享资源竞争场景且有优先级区分时，必须使用优先级锁（`PriorityBrowserLock`）：
- high 优先级（实时用户请求）等待时，low 优先级（后台周期任务）检测到 high 等待后主动 `sleep` 让出（让出延迟从 config 读取）。
- 无优先级区分时使用普通 `asyncio.Lock` 即可。

**代码示例**

正面示例：

```python
class PriorityBrowserLock:
    """支持 high/low 优先级的异步锁"""
    def __init__(self, yield_delay: float):
        self._lock = asyncio.Lock()
        self._high_waiting = 0
        self._yield_delay = yield_delay  # 从 config 读取

    async def acquire(self, priority: str = "low"):
        if priority == "high":
            self._high_waiting += 1
            try:
                await self._lock.acquire()
            finally:
                self._high_waiting -= 1
        else:
            while True:
                if self._high_waiting > 0:
                    await asyncio.sleep(self._yield_delay)
                if not self._high_waiting:
                    await self._lock.acquire()
                    return
```

反面示例：

```python
# 所有任务共用普通 Lock，实时请求被后台任务阻塞
lock = asyncio.Lock()
async def live_search():
    async with lock:  # 等待 15-20s
        ...
```

**适用场景**

浏览器自动化、外部 API 调用等共享资源竞争且有优先级区分。

**不适用场景**

无优先级区分的场景（用普通 `asyncio.Lock`）；资源充足无需竞争的场景。

---

## 六、批量与查询优化

### PS-012: 批量写入必须用单事务批 upsert 【强制】

**问题描述**

`for` 循环内逐条 `db.add()` + `session.commit()` 产生 N 次磁盘 IO，当批量采集 50 条商品时写入耗时从 ~500ms 退化到 ~5000ms。

**规范条文**

批量写入必须用 `session.add_all()` + 单次 `session.commit()`，禁止在循环内逐条 commit。批量 upsert 应使用 `INSERT ... ON CONFLICT UPDATE` 或 SQLAlchemy 的 `bulk_save_objects`。

**代码示例**

正面示例：

```python
def batch_upsert_task_links(links: list[TaskLinkRow]):
    """单事务批量 upsert，避免逐条 commit"""
    session.add_all(links)
    session.commit()  # 单次提交
```

反面示例：

```python
for link in links:
    session.add(link)
    session.commit()  # N 次磁盘 IO
```

**适用场景**

批量数据同步、批量事件写入、批量采集结果落库。

**不适用场景**

需要独立事务边界（每条写入需独立提交/回滚）；需要逐条失败处理的场景。

---

### PS-013: 分页接口 list+count 必须合并查询 【强制】

**问题描述**

分页列表接口分别执行 `SELECT * ... LIMIT` 和 `SELECT COUNT(*)` 两次查询，产生两次 DB 往返，且 count 查询在全量数据上执行，与 list 查询的过滤条件可能不一致。

**规范条文**

分页接口的 list 和 count 必须合并为单次查询，使用窗口函数 `COUNT(*) OVER()` 或单次聚合查询。禁止分两次查询 list 和 count。

**代码示例**

正面示例：

```python
def list_and_count_task_links(task_id, offset, limit):
    """单次查询返回 list + count，避免两次 DB 往返"""
    stmt = (
        select(TaskLinkRow, func.count().over().label("total"))
        .where(TaskLinkRow.task_id == task_id)
        .offset(offset).limit(limit)
    )
    rows = session.execute(stmt).all()
    total = rows[0].total if rows else 0
    return [r[0] for r in rows], total
```

反面示例：

```python
# 两次查询，且 count 与 list 过滤条件可能不一致
items = session.query(TaskLinkRow).filter(...).offset(offset).limit(limit).all()
total = session.query(func.count()).filter(...).scalar()
```

**适用场景**

分页列表接口，count 与 list 过滤条件相同。

**不适用场景**

count 需要跨表聚合；count 与 list 过滤条件不同。

---

### PS-014: SQL 层过滤优先于 Python 层过滤 【强制】

**问题描述**

从 DB 取出全量数据后用 Python `filter()` 过滤，浪费网络 IO 和内存。当 JSON 字段内属性（如 `price_range.min`）需要过滤时，全量取出再过滤导致响应时间从 ~50ms 退化到 ~500ms。

**规范条文**

过滤条件必须下推到 SQL 层，使用 SQLAlchemy 的 `json_extract` + `cast` 将 JSON 字段属性过滤下推到 DB。**禁止**取出全量数据后用 Python filter。

**代码示例**

正面示例：

```python
from sqlalchemy import func, cast, Float

# SQL 层过滤 JSON 字段内的价格
stmt = (
    select(ItemRow)
    .where(
        cast(func.json_extract(ItemRow.payload, '$.price_range.min'), Float) >= min_price
    )
)
```

反面示例：

```python
# 取出全量后 Python 过滤
items = session.query(ItemRow).all()
filtered = [i for i in items if i.payload.get('price_range', {}).get('min', 0) >= min_price]
```

**适用场景**

JSON 字段属性过滤、数值范围过滤、简单逻辑过滤。

**不适用场景**

需要调用外部 API 判断的过滤；需要复杂 Python 业务逻辑的过滤；过滤条件依赖运行时外部变量。

---

## 七、缓存策略

### PS-015: 缓存 TTL 必须大于被缓存操作平均耗时 【强制】

**问题描述**

缓存 TTL 设为 5 秒，但被缓存操作（闲鱼搜索）平均耗时 15-20 秒，导致缓存命中率几乎为零，性能优化形同虚设。修正为 60 秒后缓存命中响应时间从 4240ms 降至 1ms（4240 倍提升）。

**规范条文**

缓存 TTL 必须 >= 被缓存操作平均耗时 × 期望命中倍数（默认 3 倍）。代码注释必须说明取值依据。TTL 值应从 config 读取，禁止硬编码。

**代码示例**

正面示例：

```python
# 60 秒 TTL：闲鱼搜索平均耗时 15-20s，60s 确保至少 3 次缓存命中
# TTL 从 config 读取，禁止硬编码
_LIVE_CACHE_TTL = config.get("live_search_cache_ttl_seconds", 60)
```

反面示例：

```python
# 5 秒 TTL：小于操作耗时 15-20s，缓存形同虚设
_LIVE_CACHE_TTL = 5
```

**适用场景**

耗时操作结果缓存、外部 API 响应缓存、计算密集型结果缓存。

**不适用场景**

强一致性要求的场景；数据频繁变更的场景。

---

### PS-016: 缓存策略必须区分空结果与非空结果 【强制】

**问题描述**

缓存空结果（0 条记录）会导致下次请求直接返回空列表，用户无法触发实时重试。但若不缓存空结果，短时间内重复请求会反复触发耗时操作。

**规范条文**

缓存策略必须区分空结果与非空结果：
- 非空结果（filtered > 0）：按正常 TTL 缓存
- 空结果（filtered == 0）：不写入缓存（确保下次请求触发实时查询），或使用短 TTL（如 5 秒）

**代码示例**

正面示例：

```python
if filtered > 0:
    # 非空结果写入缓存
    _live_cache[cache_key] = (result, time.time())
# 空结果不写入缓存，确保下次请求触发实时查询
```

反面示例：

```python
# 不区分空/非空，空结果也缓存，用户无法重试
_live_cache[cache_key] = (result, time.time())
```

**适用场景**

实时查询结果缓存、搜索结果缓存。

**不适用场景**

静态数据缓存（空结果也可安全缓存）。

---

## 八、SSE 流式响应

### PS-017: SSE 前置检查返回 HTTP 错误码，业务阶段错误通过事件传递 【强制】

**问题描述**

SSE 流式响应中所有错误都通过 SSE 事件传递，导致前置条件检查失败（如 404 资源不存在）时前端需解析 SSE 流才能发现错误，增加错误处理复杂度。

**规范条文**

SSE 流式响应的错误处理必须分两层：
- **前置条件检查**（资源存在性、参数合法性）：返回标准 HTTP 错误码（404/400/403），快速失败
- **业务执行阶段错误**（搜索失败、过滤失败、写入失败）：通过 SSE `error` 事件传递，让前端知道哪个阶段失败

**代码示例**

正面示例：

```python
@router.get("/live")
async def live_search(task_id: int):
    # 前置检查返回 HTTP 错误码
    task = repo.get_task(task_id)
    if not task:
        raise HTTPException(404, detail="Task not found")

    # 业务阶段通过 SSE 事件传递
    async def event_stream():
        yield sse_event("searching", {})
        try:
            result = await search()
        except Exception as e:
            yield sse_event("error", {"stage": "searching", "message": str(e)})
            return
        yield sse_event("done", {"count": len(result)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

反面示例：

```python
# 所有错误都通过 SSE 传递，前置检查也走 SSE
async def event_stream():
    task = repo.get_task(task_id)
    if not task:
        yield sse_event("error", {"message": "not found"})  # 应返回 404
        return
```

**适用场景**

长时间运行的多阶段任务（>3 秒）的 SSE 流式响应。

**不适用场景**

快速完成的单步操作（用普通 JSON 响应即可）。

---

### PS-018: SSE 阶段事件必须映射真实执行链路 【强制】

**问题描述**

SSE 事件名称随意命名（如 stage1/stage2），与代码执行顺序不一致，前端无法准确映射进度反馈。

**规范条文**

SSE 阶段事件必须满足：
- 每个事件对应一个真实的耗时操作
- 事件名称必须语义化（如 `checking_cache`/`acquiring_lock`/`searching`/`filtering`/`writing_db`/`done`）
- 事件序列必须与代码执行顺序一致
- 事件 payload 必须包含阶段名称和可选的进度信息

**适用场景**

多阶段任务的进度反馈（如实时搜索 → 过滤 → 写入）。

**不适用场景**

单步操作（无需阶段事件）。

---

### PS-019: 需要自定义 Header 的 SSE 必须用 fetch+ReadableStream 【强制】

**问题描述**

`EventSource` 不支持自定义 Header（如认证 token），导致需要认证的 SSE 接口无法使用 `EventSource`。

**规范条文**

需要自定义 Header 的 SSE 必须用 `fetch` + `ReadableStream` 手动解析 `text/event-stream`，**禁止**使用 `EventSource`。解析逻辑应封装为通用工具函数。

**代码示例**

正面示例：

```typescript
async function fetchSSE(url: string, token: string, onEvent: (stage: string, data: any) => void) {
  const resp = await fetch(url, {
    headers: { 'Authorization': `Bearer ${token}` },
  });
  const reader = resp.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop()!;
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        onEvent(JSON.parse(line.slice(6)));
      }
    }
  }
}
```

**适用场景**

需要自定义 Header（认证 token、自定义参数）的 SSE 场景。

**不适用场景**

无需自定义 Header 的 SSE（用 `EventSource` 更简单）。

---

## 九、前端性能

### PS-020: 列表派生计算必须用 useMemo 【强制】

**问题描述**

列表数据的派生计算（过滤、排序、统计）在每次渲染时都重新执行，当列表数据量大时导致页面卡顿。

**规范条文**

列表数据的派生计算必须用 `useMemo` 包裹，依赖项为原始数据 + 过滤条件。**禁止**在渲染路径内直接执行派生计算。

**代码示例**

正面示例：

```typescript
const filteredItems = useMemo(
  () => items.filter(i => i.price >= minPrice),
  [items, minPrice]  // 依赖项为原始数据 + 过滤条件
);
```

反面示例：

```typescript
// 每次渲染都重新过滤
const filteredItems = items.filter(i => i.price >= minPrice);
```

**适用场景**

列表页面的过滤、排序、统计等派生计算。

**不适用场景**

简单字段访问（无需 memo）；频繁变更的依赖（会导致频繁重计算，此时应考虑其他优化方案）。

---

## 十、运维验证

### PS-021: 服务重启三步预检 【强制】

**问题描述**

重启服务时未检查端口占用，旧进程仍占用端口导致新进程绑定失败；或使用 `-NoNewWindow` 启动导致子进程绑定到当前终端，命令结束后收到 `KeyboardInterrupt`。

**规范条文**

服务重启必须执行三步预检：
1. **端口检查**：检查目标端口是否被占用，若占用则终止旧进程（`taskkill /F /T /PID`）
2. **独立窗口启动**：用 `-WindowStyle Hidden` 在独立窗口启动新进程，**禁止**用 `-NoNewWindow`（会导致子进程绑定到当前终端）
3. **启动验证**：验证新进程启动成功（检查端口监听 + HTTP 响应）

**适用场景**

所有后端服务重启场景。

**不适用场景**

首次启动（无旧进程）；Docker 容器内启动（容器管理进程生命周期）。

---

### PS-022: 性能优化必须有量化验证指标 【强制】

**问题描述**

性能优化后仅凭"感觉变快了"判断效果，缺乏量化数据支撑，无法确认优化是否真正生效。

**规范条文**

每个性能优化方案必须定义"优化前/优化后"的可量化指标（如响应时间 4240ms → 1ms），并通过运行时测试验证。验证证据应包含在优化说明中。

**适用场景**

所有性能优化任务。

**不适用场景**

功能开发任务（无需量化指标）；UI 调整（主观体验为主）。

---

### PS-023: 多阶段任务必须有阶段性日志输出 【强制】

**问题描述**

长时间运行的任务无阶段性日志，出现问题时无法定位卡在哪个阶段。

**规范条文**

耗时 > 1 秒的任务必须有阶段性日志输出，每个阶段开始/结束都要记录耗时和结果。日志应包含阶段名称、开始时间、结束时间、耗时、结果状态。

**代码示例**

正面示例：

```python
import time
t0 = time.time()
logger.info("stage=searching start")
result = await search()
logger.info(f"stage=searching done duration={time.time()-t0:.2f}s count={len(result)}")
```

**适用场景**

耗时 > 1 秒的任务（搜索、采集、迁移、批量处理）。

**不适用场景**

毫秒级操作（日志开销大于操作耗时）。

---

### PS-024: 外部依赖失效必须自动暂停+用户提示 【强制】

**问题描述**

外部服务（如闲鱼会话）失效时任务静默失败或无限重试，用户无法感知问题。

**规范条文**

外部依赖失效时必须：
1. 自动暂停任务（设置 `paused` 标志）
2. 记录失效原因到日志和数据库
3. 通过通知渠道（SSE/轮询）提示用户
4. **禁止**静默失败或无限重试

**适用场景**

依赖外部 API/外部服务的任务。

**不适用场景**

纯本地计算（无外部依赖）。
