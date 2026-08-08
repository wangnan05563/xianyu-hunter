# 闲鱼猎人架构模式知识库

> 本文档总结闲鱼猎人项目中的关键架构模式与设计决策，便于开发人员理解项目设计的"为什么"。

---

## 模式1：DDD Lite + Clean Architecture 四层架构

### 问题描述

闲鱼猎人采用领域驱动设计精简版（DDD Lite）+ Clean Architecture，分为四层：

```
domain（领域层）
  ↓
infra（基础设施层）
  ↓
modules（业务模块层）
  ↓
web（Web 层）
```

### 层次职责

| 层次 | 职责 | 示例 |
|------|------|------|
| domain | 领域模型、领域事件、值对象 | `Task`、`Item`、`Event` |
| infra | 基础设施：DB、浏览器、日志、配置 | `Repository`、`Browser`、`Logger` |
| modules | 业务模块：采集、评估、通知、客服 | `Collector`、`Evaluator`、`Notifier`、`Chatbot` |
| web | HTTP 接口、SSE、中间件 | `FastAPI Router`、`SSE Event` |

### 依赖方向

**【强制】** 依赖方向必须从外向内：
- `web` → `modules` → `infra` → `domain`
- `domain` 不依赖任何其他层
- `infra` 只依赖 `domain`
- `modules` 依赖 `infra` 和 `domain`
- `web` 依赖所有层

### 判断逻辑

1. 领域模型变更 → 仅影响 `domain` 层
2. DB 切换 → 仅影响 `infra` 层
3. 业务逻辑变更 → `modules` 层
4. API 路由变更 → `web` 层

---

## 模式2：Composition Root 依赖注入

### 问题描述

闲鱼猎人使用 Composition Root 模式集中管理依赖注入，避免分散的 `new` 操作。

### 实现

```python
# src/xianyu_hunter/web/container.py
class Container:
    """依赖注入容器：所有组件的工厂方法集中于此"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def repository(self) -> Repository:
        return get_repository()
    
    def chatbot_orchestrator(self) -> ChatbotOrchestrator:
        return ChatbotOrchestrator(
            faq_matcher=self.faq_matcher(),
            intent_classifier=self.intent_classifier(),
            rag_engine=self.rag_engine(),
            agent=self.agent(),
            context_manager=self.context_manager(),
            escalation=self.escalation(),
            chatbot_repo=self.chatbot_repo(),
            config=self.config().chatbot,
            event_bus=self.event_bus(),
        )
```

### 优势

1. **集中管理**：所有依赖关系一目了然
2. **便于测试**：可注入 mock 依赖
3. **生命周期控制**：单例/瞬时由容器决定
4. **避免循环依赖**：通过容器显式声明依赖

---

## 模式3：Repository Mixin 组合

### 问题描述

闲鱼猎人 26 张表，若每个表一个 Repository 类会产生类爆炸；单一巨型 Repository 又难以维护。

### 解决方案

采用 **Mixin 组合模式**：

```python
# 10 个 Mixin 按业务域拆分
class TasksMixin: ...
class ItemsMixin: ...
class EventsMixin: ...
# ...

# 运行时通过 type() 动态组合
Repository = type('Repository', (
    TasksMixin, ItemsMixin, EventsMixin, ...
    RepositoryBase,
), {})
```

### 延迟构建避免循环导入

```python
# Mixin 文件反向导入 RepositoryBase，必须延迟构建
def _get_repository_class():
    mixin_classes = []
    for mod_name in _mixin_modules:
        mod = importlib.import_module(mod_name)
        # ...
    return type('Repository', tuple(mixin_classes), {})
```

### 判断逻辑

1. 新表 → 新建 `repo_xxx.py` 实现 Mixin
2. 在 `_mixin_modules` 列表注册
3. 同步更新 `cls_name` 列表

---

## 模式4：EventBus 事件总线

### 问题描述

模块间需要解耦通信，直接调用会产生紧耦合。

### 实现

```python
class EventBus:
    """事件总线：发布订阅模式"""
    
    def __init__(self):
        self._handlers: dict[EventType, list[Callable]] = {}
    
    def subscribe(self, event_type: EventType, handler: Callable):
        """订阅事件"""
        self._handlers.setdefault(event_type, []).append(handler)
    
    async def publish(self, event: Event):
        """发布事件"""
        for handler in self._handlers.get(event.type, []):
            await handler(event)
```

### 应用场景

- 任务状态变更 → 发布 `TASK_STATUS_CHANGED` 事件
- 订单创建 → 发布 `ORDER_CREATED` 事件
- 智能客服降级 → 发布 `CHATBOT_DEGRADED` 事件
- 浏览器登录态失效 → 发布 `AUTH_EXPIRED` 事件

---

## 模式5：PriorityBrowserLock 浏览器锁

### 问题描述

闲鱼猎人单浏览器实例需支持多任务并发，但 Playwright 操作不可并行，且部分操作需优先级。

### 实现

```python
class PriorityBrowserLock:
    """带优先级的浏览器锁"""
    
    def __init__(self):
        self._lock = asyncio.Lock()
        self._waiters: list[tuple[int, asyncio.Future]] = []
    
    async def acquire(self, priority: int = 0):
        """获取锁，priority 越高越优先"""
        # ...
```

### 优先级规则

- 手动操作（用户触发）：priority=100
- 实时搜索：priority=50
- 定时任务：priority=10
- 后台批量：priority=1

---

## 模式6：SSE 流式接口

### 问题描述

智能客服 LLM 生成需要流式返回，传统 HTTP 请求/响应模式不适用。

### 实现

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

@router.get("/chatbot/chat")
async def chat(request: ChatRequest):
    async def event_stream():
        async for event in orchestrator.orchestrate(
            session_id=request.session_id,
            message=request.message,
        ):
            yield f"event: {event.event}\n"
            yield f"data: {json.dumps(event.data, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        },
    )
```

### SSE 事件类型

```python
class SSEEventType(str, Enum):
    TOKEN = "token"            # LLM 流式 token
    SOURCES = "sources"        # RAG 引用来源
    TOOL_CALL = "tool_call"    # 工具调用事件
    INTENT = "intent"          # 意图分类结果
    DONE = "done"              # 流结束
    ERROR = "error"            # 错误
    ESCALATE = "escalate"      # 转人工
```

---

## 模式7：两阶段提交（知识库）

### 问题描述

知识库构建涉及"清空 + 写入"，若中途失败会导致数据丢失。

### 解决方案

```python
async def build_all(self) -> KBVersion:
    # 阶段1：导出快照
    snapshot_path = self._make_snapshot_path(version_id)
    await self._export_snapshot(snapshot_path)
    
    try:
        # 阶段2：清空 + 写入
        await self._vector_store.clear()
        await self._vector_store.batch_insert(snippets)
        # 更新版本状态
    except Exception:
        # 失败回滚
        await self._rollback_build(snapshot_path)
        raise
```

### 失败率阈值

- ≤10%：`success`
- 10%~50%：`partial`（保留部分结果）
- >50%：`failed`（自动回滚）

---

## 模式8：多级降级链

### 问题描述

智能客服依赖外部 LLM API，可能超时/失败，需保证可用性。

### 降级链路

```
LLM 流式生成（最优体验）
  │ 失败
  ▼
RAG 检索片段直返（无 LLM 加工）
  │ 失败
  ▼
转人工（兜底）
```

### 实现

```python
try:
    # 1. 尝试 LLM 流式生成
    async for event in self._rag.generate(...):
        yield event
except LLMTimeoutError:
    # 2. 降级到 RAG 片段直返
    await self._publish_degraded("llm_to_rag")
    async for event in self._yield_rag_fallback(chunks):
        yield event
except NoRelevantDocError:
    # 3. 降级到转人工
    await self._publish_degraded("rag_to_escalation")
    yield SSEEvent(event=SSEEventType.ESCALATE, data={...})
```

---

## 模式9：SQLite 引擎配置

### 问题描述

SQLite 默认配置不适合 Web 应用并发场景。

### 解决方案

```python
def create_sqlite_engine(db_path: str) -> Engine:
    engine = create_engine(
        f"sqlite:///{db_path}",
        poolclass=NullPool,                    # 不复用连接
        connect_args={
            "check_same_thread": False,         # 允许跨线程
            "timeout": 10,                      # busy_timeout
        },
    )
    
    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")       # 读写不互斥
        cur.execute("PRAGMA synchronous=NORMAL")     # 性能/可靠性平衡
        cur.execute("PRAGMA busy_timeout=10000")     # 锁等待 10s
        cur.execute("PRAGMA foreign_keys=OFF")       # 应用层维护关系
        cur.close()
```

### 为什么用 NullPool

- SQLite 单文件锁粒度粗
- 连接长期持有易触发 `SQLITE_BUSY`
- NullPool 每次借/还连接，配合 WAL 模式性能更优

---

## 模式10：per-session Lock（智能客服）

### 问题描述

同一会话的并发请求会导致上下文错乱（如消息顺序混乱）。

### 实现

```python
class ChatbotOrchestrator:
    def __init__(self, ...):
        self._session_locks: dict[str, asyncio.Lock] = {}
        self._locks_guard = asyncio.Lock()  # 保护字典本身
    
    async def _get_session_lock(self, session_id: str) -> asyncio.Lock:
        async with self._locks_guard:
            if session_id not in self._session_locks:
                self._session_locks[session_id] = asyncio.Lock()
            return self._session_locks[session_id]
```

### 清理策略

会话 `ended` 时主动清理 Lock，防止内存泄漏：

```python
if context.status == "ended":
    async with self._locks_guard:
        self._session_locks.pop(context.session_id, None)
```

---

## 模式11：异步操作整体超时保护（asyncio.wait_for）🆕v4.7

### 问题描述

`await` 调用外部资源（浏览器自动化、HTTP 客户端、IO 操作）时，被调用方内部 `timeout` 参数可能失效或不存在，导致浏览器实例异常 / 反爬拦截 / 网络挂起时整个请求无限阻塞，客户端超时后无任何错误提示。

### 适用场景

- 浏览器自动化（Playwright `page.query_selector` / `page.goto`）无 `timeout` 参数的调用
- HTTP 客户端未配置 `httpx.Timeout` 的请求
- 远程 API 调用、IO 操作、子进程调用
- 任何 `await` 外部资源且无内建 timeout 的场景

### 不适用场景

- 已配置 `httpx.Timeout` 的 HTTP 客户端（内建 timeout 已生效）
- 纯计算函数（无 IO 等待）
- `asyncio.CancelledError` 传播路径（应单独处理，参考模式10）
- 有 tenacity 等重试机制包裹的场景

### 实现模式

```python
import asyncio
from fastapi import HTTPException

async def refresh_item(item_id: str):
    """采集商品详情（带整体超时保护）"""
    timeout = get_config().async_timeout.refresh_seconds  # 从配置读取
    try:
        detail = await asyncio.wait_for(
            container.collector.detail(item_id),
            timeout=timeout,
        )
        return detail
    except asyncio.TimeoutError:
        # 超时返回 504 网关超时，便于前端按状态码分类处理
        logger.warning(
            "[RefreshItem] 采集超时 item=%s（%ss），外部资源可能异常",
            item_id, timeout,
        )
        raise HTTPException(
            status_code=504,
            detail="采集超时：外部资源异常或被反爬拦截，请稍后重试",
        )
    except Exception as e:
        # 其他异常返回 502 失败
        logger.warning("[RefreshItem] 采集失败 item=%s: %s", item_id, e)
        raise HTTPException(status_code=502, detail=f"采集失败：{e}")
```

### 关键约束

1. **超时时间从配置读取**：禁止硬编码 `timeout=60.0`，应从 `config.async_timeout.<operation>_seconds` 读取
2. **语义化状态码**：超时→504、失败→502、稍后重试→503，便于前端按状态码分类处理（参考 v4.1 错误粒度三类区分）
3. **日志包含上下文**：必须记录操作类型 + 资源 ID + 超时秒数
4. **CancelledError 单独传播**：`asyncio.wait_for` 的 `TimeoutError` 不应吞掉 `CancelledError`

### 配置驱动

```yaml
# config.yaml
async_timeout:
  refresh_seconds: 60        # 采集详情超时
  search_seconds: 30         # 搜索超时
  login_seconds: 120         # 登录超时
  status_code_mapping:
    timeout: 504
    failure: 502
    retry: 503
  max_retries: 0             # 默认不重试（重试由调用方或 tenacity 管理）
```

### 历史教训

`refresh_item` 调用 `collector.detail(item_id)` 时，`page.query_selector` 无 `timeout` 参数，闲鱼反爬 RGV587 拦截后浏览器实例异常导致 `query_selector` 无限挂起，前端 90 秒后客户端超时无任何错误提示。修复后 `refresh_item` 加 `asyncio.wait_for(..., timeout=60.0)` + 504 响应，14.4 秒返回明确错误。

---

## 模式12：数据流转完整性 5 点追踪 🆕v4.7

### 问题描述

用户反馈"某字段为空 / 显示异常 / 数据丢失"时，根因可能位于数据流转的任一环节：数据库无数据、Repo 层过滤掉、API 层未注入、前端 types 未声明、render 未取值。仅查看前端或仅查看后端都无法定位根因。

### 适用场景

- 用户反馈"字段为空 / 显示异常 / 数据丢失"
- 涉及前后端多层的字段
- 数据流转经过 ≥ 3 个环节的查询

### 不适用场景

- UI 样式问题（颜色 / 布局错误）
- 纯前端计算字段（如 `total = price * quantity`）
- 权限不足导致字段隐藏

### 追踪流程（5 点逐层验证）

```
DB schema → Repo 查询过滤 → API 注入 → 前端 types → render 取值
   ↓             ↓              ↓            ↓             ↓
原始数据存在？  被过滤掉？    正确注入？   类型声明？    正确绑定？
```

#### 第 1 点：DB schema（原始数据是否存在）

```bash
# 用 sqlite3 / DB 客户端查询原始数据
sqlite3 data/xianyu.db "SELECT * FROM orders WHERE item_id = '1059778837640';"
```

- 数据存在 → 进入第 2 点
- 数据不存在 → 根因在数据写入层（采集 / 同步逻辑）

#### 第 2 点：Repo 查询过滤（数据是否被过滤）

```python
# 检查 Repo 层是否有 WHERE / if continue 等过滤逻辑
# grep -rn "if status.*continue" src/xianyu_hunter/infra/
```

- 数据被过滤 → 根因在 Repo 层（参考 step 53 过滤逻辑场景区分）
- 数据未过滤 → 进入第 3 点

#### 第 3 点：API 注入（数据是否传递给前端）

```python
# 检查 API 路由层是否正确调用 Repo 并注入响应
# grep -rn "list_orders_by_item_ids" src/xianyu_hunter/web/routes/
order_map = container.repo.list_orders_by_item_ids(
    list(event_item_ids), include_failed=True  # 关键：是否传 include_failed=True
)
```

- 数据未注入 → 根因在 API 层（参数未传 / 调用错误）
- 数据已注入 → 进入第 4 点

#### 第 4 点：前端 types（类型定义是否声明字段）

```typescript
// 检查 frontend/src/api/types.ts
// grep -rn "order_status" frontend/src/api/types.ts
type EvalItem = {
  order_status?: string  // 字段是否声明？
}
```

- 字段未声明 → 根因在前端类型定义
- 字段已声明 → 进入第 5 点

#### 第 5 点：render 取值（组件是否正确渲染）

```typescript
// 检查组件 render 逻辑
// grep -rn "order_status" frontend/src/pages/Evaluations/
<td>{record.order?.status || '—'}</td>  // 是否正确取值？
```

- 取值错误 → 根因在 render 层
- 取值正确 → 检查浏览器 Network 面板，确认响应实际包含数据

### 关键约束

1. **逐层验证**：5 点必须依次验证，不能跳过任何一层
2. **打印中间值**：每层必须打印实际值（`print(order_map)` / `console.log(record.order)`），不能凭推断
3. **修复根因**：找到根因后必须修复根因，禁止绕过（如 Repo 过滤错误应修 Repo，而非 API 层重新查询）
4. **回归测试**：修复后必须新增测试覆盖该场景（如 `test_list_orders_by_item_ids_failed_filter`）

### 历史教训

评估明细页"订单"列显示 "—"，根因是 `repo_orders.list_orders_by_item_ids` 无条件 `if status == 'failed': continue`，但 API 层评估明细调用未传 `include_failed=True`。数据库中实际有 3 条 failed 订单，但全部被 Repo 层过滤。修复后 API 返回 `order_status=failed`（之前为 `null`）。
