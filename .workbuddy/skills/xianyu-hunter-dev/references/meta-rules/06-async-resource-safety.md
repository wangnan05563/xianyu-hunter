# 异步与资源安全
> 包含元规范 #10 - #82

## 10. 异步操作规范

所有 `await` 调用外部资源的异步操作必须满足：

1. **整体超时保护**：`asyncio.wait_for(coro, timeout=N)` 包裹，超时返回语义化状态码（504）
2. **超时时间从配置读取**：禁止硬编码，参考 `config.yaml` 的 `async_timeout` 节点
3. **CancelledError 传播**：用 `contextlib.suppress(asyncio.CancelledError)` 包裹并向上传播，禁止 `except: pass`
4. **Task 引用保留**：`self._task = asyncio.create_task(...)` 防止 GC，禁止裸 `asyncio.create_task(...)`
5. **取消+收集模式**：`task.cancel()` + `await asyncio.gather(task, return_exceptions=True)`

## 23. 资源生命周期管理（适用于浏览器/订阅/连接）

可注册组件（Playwright Page/Browser、EventSource/SSE、WebSocket、Proxy/Observer、asyncio.Task）必须满足：

1. **持有**：实例属性 / ref，命名以 `_` 开头（`self._page`、`this._proxy`、`_task`）
2. **清理**：在 `stop()` / `useEffect cleanup` / `onUnmounted` 中调用 `close()` / `dispose()` / `cancel()`
3. **检测**：硬约束禁止 `const x = new Proxy()` 局部变量（被 GC 回收导致代理失效）
4. **监控**：建立资源使用计数 dashboard（`lifecycle_audit_interval_seconds`）

**关键约束**：
- `asyncio.create_task(coro)` **必须**赋值给实例属性（`self._task = asyncio.create_task(...)`），禁止裸 `create_task`（GC 风险）
- 长连接组件必须有 cleanup hook（`useEffect(() => { ...; return () => es.close() }, [])`）
- `forbid_local_var_creation` 列表中的资源类型禁止局部变量持有

**判断信号**：
- `grep "(const|let)\\s+\\w+\\s*=\\s*new (Proxy|MutationObserver|IntersectionObserver|ResizeObserver)" <file>` → 视为违规
- `asyncio.create_task(coro)` 未赋值给实例属性 → 视为违规
- 长连接组件无 cleanup → 视为违规

**适用**：浏览器自动化（Playwright/Selenium）、SSE/WebSocket 连接、EventSource、Proxy/Observer 订阅、长生命周期 Timer。
**不适用**：短生命周期的局部计算（一次性数组 map）/ 一次性 useEffect（无需 cleanup）/ 测试 mock 资源。

**历史教训**：前端反爬模块 `const observer = new MutationObserver(...)` 后未保存到实例属性，被 GC 回收后 DOM 变化不再触发回调，表面上"代码正常执行"但实际"功能失效"，难以察觉。

## 50. 长生命周期对象状态清理（LIFECYCLE-RESOURCE-CLEANUP）🆕v4.36

> 与 B-REVIEW-180（backend 长生命周期对象状态清理审查）/ F-REVIEW-138（前端长生命周期 Hook cleanup 审查）对应。

长生命周期对象（scheduler / container / registry / manager）持有 task 级或 session 级状态字典（如 `_resume_cooldown: dict[str, float]` / `_last_failure_reason: dict[str, str]` / `_task_status_cache: dict[str, dict]`）时，必须提供 `drop_task_state(task_id: str) -> None` 方法，DELETE API 删除 task 时调用该方法清理对应状态，避免字典无限增长导致内存泄漏。

1. **状态字典识别**：长生命周期对象的 `__init__` 中所有 `dict[str, ...]` 类型字段视为状态字典，必须支持按 task_id 清理
2. **drop_task_state 方法签名**：`def drop_task_state(self, task_id: str) -> None: ...`，内部遍历所有状态字典 `self._resume_cooldown.pop(task_id, None)` / `self._last_failure_reason.pop(task_id, None)` 等
3. **DELETE API 调用**：`DELETE /api/tasks/{task_id}` 和 `DELETE /api/tasks/batch` 路由必须调用 `container.scheduler.drop_task_state(task_id)`，与 DB 删除操作配对执行
4. **异常容错**：`drop_task_state` 内部 `pop` 操作必须 `try/except Exception: logger.debug(...)` 容错，不阻断主流程（DB 删除已成功，状态清理失败仅记日志）
5. **配置驱动**：状态字典清单、清理策略（lazy/active）、清理触发点（DELETE API/scheduler shutdown/定期扫描）从 `config.yaml#lifecycle_resource_cleanup` 节点管理

**关键约束**：
- 长生命周期对象 `__init__` 有 `self._xxx: dict[str, ...]` 但无 `drop_task_state` 方法 → 视为 CRITICAL（状态字典无清理入口）
- `grep "def delete_task\|def unregister" <route_file>` 无 `drop_task_state` 调用 → 视为 CRITICAL（DELETE 未清理状态）
- `drop_task_state` 内 `pop` 操作无 `try/except` → 视为 WARNING（清理失败可能阻断主流程）

**判断信号**：
- `grep "self\._\w*: dict\[str," <scheduler_file>` 命中 → 状态字典识别
- `grep "def drop_task_state" <scheduler_file>` 无匹配 → 缺清理方法
- `grep "def delete_task" <route_file>` 但无 `drop_task_state` → DELETE 未清理

**适用**：长生命周期对象（scheduler / container / registry / manager / singleton service）；持有 `dict[str, ...]` 状态字段的组件；task 级或 session 级状态缓存；DELETE API 删除资源的场景。
**不适用**：短生命周期对象（请求级 / 函数级局部变量）；无状态服务（stateless）；只读缓存（never expire，如配置缓存）；测试 fixture（测试结束自动清理）。

**历史教训**：`scheduler.py` 的 `_resume_cooldown: dict[str, float]` 在 task 异常 pause 后写入冷却时间戳，但 DELETE API 删除 task 时未清理该字段，长期运行后字典无限增长（每个已删除 task 留一条记录）。同期 `_last_failure_reason: dict[str, str]` 和 `_task_status_cache: dict[str, dict]` 也有同样问题。修复：在 `scheduler.py` 加 `drop_task_state(task_id)` 方法遍历清理所有状态字典，`api_tasks.py` 的 `delete_task` 和 `batch_delete_tasks` 路由调用该方法。建立 #50 强制清理规则。

## 57. async/await 同步性静态检查（ASYNC-AWAIT-SYNC-CHECK）🆕v4.38

> 与 B-REVIEW-182（backend async/await 同步性审查）/ F-REVIEW-148（前端 async/await 同步性审查）对应。

`async def` 方法体内若不含 `await` 表达式，必须改为同步 `def`；调用点同步移除 `await`。Python 3.14 可能优化无 await 的 async 函数返回 None，导致 `await None` 触发 `TypeError: 'NoneType' object can't be awaited`。

1. **静态检查强制**：所有 `async def` 方法必须检查方法体内是否含 `await` 表达式，无 `await` 则改为 `def`
2. **调用点同步**：方法从 `async def` 改为 `def` 后，所有调用点必须同步移除 `await`
3. **白名单豁免**：`@abstractmethod` 纯接口定义、`__aenter__`/`__aexit__` 上下文管理器、async generator（含 `yield`）可保留 `async def` 无 `await`
4. **AST 分析**：推荐用 AST 分析而非正则，准确识别方法体内是否含 `await` 节点
5. **配置驱动**：白名单装饰器清单、检查开关、严重级别从 `config.yaml#async_await_check` 读取

**关键约束**：
- `async def` 方法体内无 `await` 且不在白名单 → 视为 CRITICAL（Python 3.14 兼容性风险）
- 方法改为 `def` 后调用点仍用 `await` → 视为 CRITICAL（`TypeError: object NoneType can't be awaited`）
- 白名单装饰器硬编码 → 视为违规（应从 config 读）

**判断信号**：
- `grep "async def" <file>` 后检查方法体内是否含 `await`；或用 AST 分析
- `grep "await self._finalize_run\|await self._simple_method" <file>` 但方法体全同步 → 违规
- 方法从 async 改为 sync 但 `grep "await <method_name>"` 仍有命中 → 调用点未同步

**适用**：Python 3.11+ 异步代码，尤其是被 `await` 调用的方法；使用 asyncio 的 FastAPI/uvicorn 项目；含 `async def` 的 worker/scheduler/service 层。
**不适用**：纯接口定义（`@abstractmethod`）、上下文管理器（`__aenter__`/`__aexit__`）、async generator（含 `yield`）、测试代码中的 `async def test_*`（pytest-asyncio 自动处理）。

**反模式**：
```python
# ❌ async def 但方法体全同步，Python 3.14 优化后 await None 触发 TypeError
async def _finalize_run(self, stats: dict) -> None:
    self._stats = stats
    self._persist_to_db(stats)
    logger.info("完成统计")

# 调用点
await self._finalize_run(stats)  # Python 3.14: TypeError: 'NoneType' object can't be awaited
```

**正确模式**：
```python
# ✅ 改为同步 def，调用点移除 await
def _finalize_run(self, stats: dict) -> None:
    self._stats = stats
    self._persist_to_db(stats)
    logger.info("完成统计")

# 调用点
self._finalize_run(stats)
```

**历史教训**：`worker.py` 的 `_finalize_run` 标记为 `async def` 但方法体全同步（仅赋值 + DB 写入 + 日志），Python 3.14 优化后返回 None，`await None` 触发 TypeError 导致调度器崩溃。修复：改为 `def _finalize_run` + 所有调用点移除 `await`。同期发现 3 处类似问题（`_save_progress` / `_update_status` / `_notify_done`），均改为同步。

> 📖 详见 [concurrency.md](../assets/guides/coding-rules/concurrency.md) step 198。

## 58. 资源池配置性能基准与决策（RESOURCE-POOL-BENCHMARK）🆕v4.38

> 与 B-REVIEW-183（backend 资源池配置性能审查）对应。

数据库/HTTP/浏览器资源池配置（如 `poolclass=NullPool` / `QueuePool` / `StaticPool`）必须有性能基准数据支持，docstring 记录选择理由与对比数据。禁止"无说明选 NullPool"导致每次连接都执行初始化开销（如 PRAGMA）。

1. **性能基准强制**：资源池选择必须有性能基准数据支持，记录"NullPool vs QueuePool"的连接建立/复用/销毁开销对比
2. **docstring 记录**：资源池配置代码必须有 docstring 说明选择理由、对比数据、适用场景
3. **开销阈值**：系统层开销（连接建立 + PRAGMA + init SQL）> `config.yaml#resource_pool_benchmark.overhead_threshold_ms`（默认 50ms）时禁止用 NullPool
4. **测试环境豁免**：测试环境可用 StaticPool 保证隔离，但需 docstring 标注"仅测试用"
5. **配置驱动**：开销阈值、池类型清单、基准数据模板从 `config.yaml#resource_pool_benchmark` 读取

**关键约束**：
- `grep "poolclass=" <file>` 无 docstring 说明 → 视为 WARNING（选择理由缺失）
- 慢查询日志中系统层开销 > 50ms 且使用 NullPool → 视为 CRITICAL（性能退化）
- 生产环境用 StaticPool → 视为 CRITICAL（无连接复用）

**判断信号**：
- `grep "poolclass=" <file>` 后检查是否有 docstring 说明；或慢查询日志中系统层开销>50ms
- `grep "poolclass=NullPool" <file>` 但无性能基准 docstring → 违规
- `grep "PRAGMA\|initialization SQL" <file>` 与 `grep "NullPool" <file>` 同时出现 → 性能风险

**适用**：所有资源池选择（NullPool/QueuePool/StaticPool）；含 PRAGMA/init/重试开销的资源初始化；数据库连接池、HTTP 连接池、浏览器实例池。
**不适用**：测试环境（用 StaticPool 保证隔离）、单次请求资源（无复用价值）、内存数据结构（无连接开销）、CLI 一次性脚本（无长期运行需求）。

**反模式**：
```python
# ❌ NullPool 无 docstring 说明，每次连接都执行 5 条 PRAGMA（~100ms 开销）
engine = create_engine(
    "sqlite:///data/xianyu.db",
    poolclass=NullPool,  # 无任何说明
)
```

**正确模式**：
```python
# ✅ QueuePool + docstring 记录选择理由与对比数据
engine = create_engine(
    "sqlite:///data/xianyu.db",
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=5,
    pool_pre_ping=True,
    # docstring: NullPool 每次新建连接执行 PRAGMA 开销 ~100ms（5 条 PRAGMA），
    # QueuePool 复用连接，性能提升 10-50x。list_and_count_task_links 从 231ms 降至 11.9ms。
)
```

**历史教训**：`db_models.py` 使用 `NullPool` 导致 `list_and_count_task_links` 慢查询 231ms（其中 ~100ms 是 PRAGMA 开销：`PRAGMA journal_mode=WAL` / `PRAGMA foreign_keys=ON` / `PRAGMA synchronous=NORMAL` / `PRAGMA busy_timeout=10000` / `PRAGMA cache_size=-20000`）。改为 `QueuePool(pool_size=5, max_overflow=5, pool_pre_ping=True)` 后降至 11.9ms（19x 提升）。根因：NullPool 每次操作都新建连接并执行 5 条 PRAGMA，QueuePool 复用连接跳过 PRAGMA。

> 📖 详见 [database.md](../assets/guides/coding-rules/database.md) step 199。

## 59. HTTP 状态码精细化映射表（HTTP-STATUS-CODE-MAPPING）🆕v4.38

> 与 B-REVIEW-184（backend HTTP 状态码精细化审查）/ F-REVIEW-149（前端状态码本地化消息审查）对应。
> 与 #8 错误粒度区分的关系：#8 给出"状态码→语义"的通用映射表，本条是**多原因 None 返回值的精细化映射**专项规范。

底层模块返回多原因的 None/错误时，必须建立 `reason_code → status_code` 映射表；底层设置 `last_*_failure_reason`；上游按映射查找状态码；前端按状态码提供本地化消息。禁止"所有 None 一律映射为 410 Gone"导致用户无法区分"商品下架"与"Cookie 过期"。

1. **reason_code 持久化**：底层模块返回 None 时必须设置 `self.last_*_failure_reason`（如 `last_detail_failure_reason`），记录具体原因
2. **映射表强制**：上游必须建立 `_FAILURE_STATUS_MAP = {reason_code: status_code}` 映射表，按 reason 查找状态码
3. **默认状态码兜底**：未知 reason 用默认状态码（如 410），但必须 `logger.warning` 记录未知 reason
4. **前端本地化**：前端按状态码提供本地化消息，禁止用 `detail.includes(...)` substring 判断
5. **配置驱动**：映射表、默认状态码、reason 枚举从 `config.yaml#http_status_code_mapping` 读取

**关键约束**：
- `grep "raise HTTPException(410\|raise HTTPException(502" <file>` 多原因汇聚同一码 → 视为 WARNING（语义模糊）
- 底层返回 None 但无 `last_*_failure_reason` 设置 → 视为 WARNING（原因丢失）
- 前端用 `detail.includes("下架")` 判断 → 视为 CRITICAL（违反 #29 error_code 分支）

**判断信号**：
- `grep "raise HTTPException(410\|raise HTTPException(502" <file>` 后检查是否多原因汇聚同一码
- `grep "last_.*_failure_reason" <file>` 与 `grep "is None" <file>` 配对检查
- `grep "_FAILURE_STATUS_MAP\|_STATUS_MAP" <file>` 无映射表 → 违规

**适用**：所有 HTTP 错误响应；多原因返回 None/错误的底层模块（如 detail() 返回 None 有 10+ 原因：商品下架/Cookie 过期/登录重定向/验证码拦截/页面不存在/网络超时等）。
**不适用**：唯一原因的错误码（如 404 仅表示资源不存在）、内部异常不向用户暴露、纯日志级别错误、健康检查端点（固定 200/503）。

**反模式**：
```python
# ❌ detail() is None 一律映射为 410 Gone，但 detail() 返回 None 有 10+ 原因
detail = await self.container.collector.detail(item_id)
if detail is None:
    raise HTTPException(status_code=410, detail="商品详情页加载失败或已下架")
    # 实际原因可能是 cookie 过期需重新登录，但用户看到"已下架"
```

**正确模式**：
```python
# ✅ reason_code → status_code 映射表 + 底层设置 last_detail_failure_reason
_DETAIL_FAILURE_STATUS_MAP = {
    "home_title_redirect": 403,      # 首页重定向，权限不足
    "login_redirect": 403,           # 登录重定向，权限不足
    "verify_redirect": 441,          # 验证重定向，需刷新 Token
    "item_not_found": 410,           # 商品不存在
    "item_removed": 410,             # 商品已下架
    "anti_crawler": 429,             # 反爬触发
    "network_timeout": 504,          # 网络超时
}

detail = await self.container.collector.detail(item_id)
if detail is None:
    reason = getattr(self.container.collector, "last_detail_failure_reason", "unknown")
    status_code = self._DETAIL_FAILURE_STATUS_MAP.get(reason, 410)
    if reason == "unknown":
        logger.warning(f"detail() 返回 None 但未设置 failure_reason, item_id={item_id}")
    raise HTTPException(status_code=status_code, detail=f"商品详情获取失败: {reason}")
```

**历史教训**：`collection_service.py` 将所有 `detail() is None` 映射为 410 Gone，前端展示"商品详情页加载失败或已下架"。但实际原因可能是 Cookie 过期（需重新登录）、登录重定向（需刷新 Token）、反爬触发（需手动验证）。用户看到"已下架"后误以为商品真的下架，实际重新登录后商品仍在。修复：建立 `_DETAIL_FAILURE_STATUS_MAP` + 底层设置 `last_detail_failure_reason` + 前端按状态码提供本地化消息（410→"商品已下架"、403→"权限不足请重新登录"、441→"Token 过期请刷新"、429→"触发反爬请验证"）。

> 📖 详见 [error-handling.md](../assets/guides/coding-rules/error-handling.md) step 200。

## 60. CSS 选择器多级降级策略（CSS-SELECTOR-FALLBACK）🆕v4.38

> 与 B-REVIEW-185（backend CSS 选择器降级审查）对应。
> 与 #54 外部页面解析容错的关系：#54 给出"三级 fallback selector"的整体框架，本条是**降级策略与 dump 触发条件的细化**。

依赖第三方网站 DOM 的选择器必须有 ≥3 级降级（业务语义 className → HTML role 属性 → 文本内容前缀扫描）；每级失败自动降级；调试 dump 触发条件收窄到核心字段失败，禁止"任一字段失败就 dump"导致 dump 文件泛滥。

1. **三级降级强制**：选择器必须按"业务语义 className → HTML role 属性 → 文本内容前缀扫描"顺序尝试，每级失败自动降级
2. **dump 触发条件收窄**：调试 dump 仅在核心字段（如 `on_sale`）失败时触发，非核心字段（如 `sold`）失败不 dump
3. **选择器配置化**：所有 selector 字符串在 `config.yaml` 管理，禁止硬编码
4. **降级链日志合并**：与 #32 一致，多 selector 尝试的中间步骤 DEBUG 化，最终失败 WARNING
5. **配置驱动**：降级级数、dump 触发条件、选择器清单从 `config.yaml#css_selector_fallback` 读取

**关键约束**：
- `grep "querySelectorAll\|querySelector" <file>` 选择器单一无 fallback → 视为 CRITICAL（改版即失效）
- `grep "tabItem\|tab.*role.*tab\|tab.*class"` selector 字符串硬编码 → 视为违规
- dump 触发条件含 `sold == 0`（非核心字段）→ 视为 WARNING（dump 泛滥）
- dump 文件频繁生成（> `config.yaml#css_selector_fallback.dump_max_per_hour`）→ 视为 WARNING

**判断信号**：
- `grep "querySelectorAll\|querySelector" <file>` 后检查选择器是否单一；或 dump 文件频繁生成
- `grep "tabItem\|tab.*class.*tab" <file>` 无 `try/except` 或 `or []` fallback → 违规
- `grep "dump.*html\|page.content" <file>` 触发条件含非核心字段 → dump 泛滥

**适用**：第三方网站 DOM 解析（闲鱼/淘宝/天猫/京东/第三方 API 返回 HTML）；依赖 className 的选择器；Playwright `page.querySelectorAll` / `page.evaluate` 返回值解析。
**不适用**：自有代码 DOM（可控制稳定性）、ID 选择器（业务语义稳定）、`data-*` 属性选择器（开发者主动标记）、后端 API JSON 解析（结构稳定）、SSR 页面（结构固定）。

**反模式**：
```python
# ❌ 单一选择器，闲鱼改版 className 后失效
tabs = page.querySelectorAll('[class*="tabItem"]')
# 无 fallback，改版后 on_sale=0 sold=0 误报
if not tabs:
    page.content()  # dump 触发条件过宽
```

**正确模式**：
```python
# ✅ 三级降级 + dump 触发条件收窄
# Level 1: 业务语义 className
tabs = page.querySelectorAll('[class*="tabItem"]')
# Level 2: HTML role 属性
if not tabs:
    tabs = page.querySelectorAll('[class*="tab"][role="tab"]')
# Level 3: 文本内容前缀扫描
if not tabs:
    tabs = page.querySelectorAll('div, span, a').filter(el =>
        el.text_content().startswith(("在售", "已售", "想要")))
# dump 仅在核心字段 on_sale 失败时触发（非 sold）
if on_sale == 0:
    logger.warning("on_sale 解析失败，dump 页面")
    dump_page(page, "sale_counts")
```

**历史教训**：`_detail.py` 的 `_parse_sale_counts_from_tabs` 仅依赖 `tabItem` class 名，闲鱼页面 DOM 结构变化后 `on_sale=0` 和 `sold=0`。dump 触发条件设为 `on_sale==0 or sold==0`，但 `sold==0` 是新 UI 的预期行为（新 UI 不显示已售数），导致每次采集都生成 dump 文件，12 小时内累积 500+ dump 文件。修复：实现三级 fallback（`[class*='tabItem']` → `[class*='tab'][role='tab']` → 文本前缀扫描 div/span/a），收紧 dump 触发条件从 `on_sale==0 or sold==0` 改为 `on_sale==0`。

> 📖 详见 [browser-automation.md](../assets/guides/coding-rules/browser-automation.md) step 201。

## 61. 异常日志语义保留规范（EXCEPTION-LOG-SEMANTIC）🆕v4.38

> 与 B-REVIEW-186（backend 异常日志语义审查）/ F-REVIEW-150（前端异常日志语义审查）对应。
> 与 #26 关键路径异常保留 traceback 的关系：#26 聚焦"关键路径"的 `logger.exception()`，本条覆盖**所有 except 块**的日志语义保留。

`except` 块内必须用 `logger.exception('描述')` 保留完整 traceback，禁用 `logger.warning(f'...{e}')` 丢失堆栈；非 `except` 块用 `warning + exc_info=True`；多阶段降级链合并为单条结构化 WARNING。

1. **except 块强制 exception()**：`except` 块内必须用 `logger.exception("描述")` 自动保留完整 traceback（含调用链、异常类型、文件行号）
2. **禁止 warning 丢堆栈**：`except` 块内禁止 `logger.warning(f"操作失败: {e}")`（仅打印异常对象，丢失堆栈）
3. **非 except 块用 exc_info**：非 except 块需记录异常信息时用 `logger.warning("描述", exc_info=True)`
4. **多阶段降级链合并**：同一逻辑链多个 except 的中间步骤 DEBUG 化，最终合并为单条结构化 WARNING（参考 #32）
5. **配置驱动**：禁止模式、必需模式、关键路径函数清单从 `config.yaml#exception_log_semantic` 读取

**关键约束**：
- `except` 块内 `logger.warning(f"...{e}")` → 视为 CRITICAL（丢失 traceback）
- `except` 块内 `logger.error(f"...{e}")` → 视为 CRITICAL（丢失 traceback）
- `except` 块内 `logger.exception(f"...{e}")` → 视为 WARNING（exception 已保留堆栈，但 f-string 冗余）
- 关键路径函数（`critical_path_functions`）的 `except` 块无 `logger.exception` → 视为 CRITICAL

**判断信号**：
- `grep "logger.warning.*f\".*{e}\"" <file>` 或 `grep "logger.exception.*f\"" <file>` 在 except 块内
- `grep "except.*as e:" <file>` 后跟 `logger.warning\|logger.error` 但无 `logger.exception` → 违规
- `grep "logger.error.*f\".*{e}\"" <file>` 在 except 块内 → 违规

**适用**：所有异常处理代码，尤其是关键路径（启动/迁移/初始化）；多阶段降级链路（API→DOM→缓存）；后台任务异常处理；API 路由异常处理。
**不适用**：纯性能日志（无异常场景）、DEBUG 级别日志（仅诊断用）、非 except 块的 warning（用 exc_info=True）、测试代码（`pytest.raises` 期望异常）。

**反模式**：
```python
# ❌ except 块内用 warning(f"...{e}") 丢失 traceback
try:
    result = await self.collector.detail(item_id)
except Exception as e:
    logger.warning(f"获取详情失败: {e}")  # 丢失 traceback，定位问题耗时 30+ 分钟
    return None
```

**正确模式**：
```python
# ✅ except 块内用 exception() 保留完整 traceback
try:
    result = await self.collector.detail(item_id)
except Exception:
    logger.exception(f"获取详情失败, item_id={item_id}")  # 自动保留 traceback
    return None

# ✅ 非 except 块用 warning + exc_info=True
try:
    result = risky_operation()
except Exception as e:
    logger.warning(f"操作失败: {e}", exc_info=True)
    return None
```

**历史教训**：关键路径（`_on_startup` / `run_migrations` / `_init_db`）用 `logger.warning(f"操作失败: {e}")` 丢失 traceback，排查问题时只能看到异常消息但无法定位具体行号和调用链，定位耗时 30+ 分钟。修复：所有 `except` 块改用 `logger.exception("描述")` 自动保留 traceback，问题定位时间从 30+ 分钟缩短到 5 分钟。同期发现 15+ 处类似问题，全部修复。

> 📖 详见 [error-handling.md](../assets/guides/coding-rules/error-handling.md) step 202。

## 62. 外部资源生命周期配对管理（EXTERNAL-RESOURCE-LIFECYCLE）🆕v4.38

> 与 B-REVIEW-187（backend 外部资源生命周期审查）/ F-REVIEW-151（前端外部资源生命周期审查）对应。
> 与 #23 资源生命周期管理的关系：#23 关注"资源实例的 GC 与 cleanup"，本条关注"外部传入资源的配对 register/unregister"。

外部传入的资源（Page/Connection/Lock）必须配对调用 `register`/`unregister`，且在 `finally` 块 `unregister` 避免泄漏；并发场景下资源不被误关。

1. **register/unregister 配对**：外部传入的资源必须调用 `register_external_page(page)` 注册，使用完毕在 `finally` 块调用 `unregister_external_page(page)` 注销
2. **finally 块强制**：`unregister` 必须在 `finally` 块中调用，确保异常时也能注销
3. **并发安全**：并发采集时，资源不被主流程误关（通过 register 标记"资源正在使用"）
4. **引用计数**：`register` 时引用计数 +1，`unregister` 时 -1，计数为 0 时才允许关闭资源
5. **配置驱动**：资源类型清单、配对函数名、引用计数策略从 `config.yaml#external_resource_lifecycle` 读取

**关键约束**：
- 外部传入 page 未调用 `register_external_page` → 视为 CRITICAL（并发采集时 page 被误关）
- `register` 后无 `finally: unregister` → 视为 CRITICAL（资源泄漏）
- `unregister` 不在 `finally` 块 → 视为 WARNING（异常时无法注销）
- 引用计数为 0 但未关闭资源 → 视为 WARNING（资源泄漏）

**判断信号**：
- `grep "reuse_page\|external_page\|register_external" <file>` 后检查是否配对 register/unregister
- `grep "def.*page.*Page" <file>` 参数含 Page 但无 `register_external_page` → 违规
- `grep "register_external_page" <file>` 但无 `finally.*unregister` → 配对缺失

**适用**：外部资源传入（Page/Connection/Lock/SSE 连接）；并发采集场景（多 worker 共享 Page）；Playwright Page 共享（主流程创建 Page 传给采集器）；跨函数/跨模块资源传递。
**不适用**：内部创建的资源（自己管理生命周期）、单线程使用（无并发风险）、一次性资源（用完即关）、`with` 语句管理的资源（自动生命周期）。

**反模式**：
```python
# ❌ 外部传入 page 未注册，并发采集时 page 被主流程关闭
async def collect_items(self, page: Page, item_ids: list[str]):
    # 未调用 register_external_page，主流程可能在此期间关闭 page
    for item_id in item_ids:
        await self._collect_one(page, item_id)
    # 主流程关闭 page 后，后续操作报 TargetClosedError
```

**正确模式**：
```python
# ✅ register + finally unregister 配对
async def collect_items(self, page: Page, item_ids: list[str]):
    self._register_external_page(page)  # 引用计数 +1，标记"正在使用"
    try:
        for item_id in item_ids:
            await self._collect_one(page, item_id)
    finally:
        self._unregister_external_page(page)  # 引用计数 -1，计数为 0 时才允许关闭
```

**历史教训**：`collection_service.py` 接收外部传入的 `page` 但未调用 `register_external_page`，并发采集时主流程（`_cleanup_idle_pages`）检测到 page 空闲后关闭，导致采集器后续操作报 `playwright._impl._errors.TargetClosedError`。修复：在 `collection_service.py` 入口调用 `self._register_external_page(page)` + `finally: self._unregister_external_page(page)`，主流程通过引用计数判断 page 是否正在使用，使用中不关闭。

> 📖 详见 [concurrency.md](../assets/guides/coding-rules/concurrency.md) step 203。

## 63. 数据库写入函数身份追溯与类型安全（DB-WRITE-IDENTITY-TRACE）🆕v4.38

> 与 B-REVIEW-188（backend 数据库写入身份追溯审查）对应。

数据库写入函数必须含 `user_id` 参数用于跨用户隔离；converter 函数处理 `re.Match` 对象必须显式调用 `m.group(1)` 再转型，禁用 `int(m)`。

1. **user_id 参数强制**：所有数据库写入函数（`upsert_*` / `insert_*` / `update_*` / `create_*`）必须含 `user_id: str` 参数，用于跨用户数据隔离
2. **WHERE 子句强制**：写入 SQL 的 WHERE 子句必须含 `user_id` 条件，禁止跨用户写入
3. **converter 类型安全**：正则 converter 函数处理 `re.Match` 对象必须显式调用 `m.group(1)` 获取字符串再转型（`int(m.group(1))`），禁用 `int(m)`（报 `int() argument must be a string, not 're.Match'`）
4. **Pydantic 入口校验豁免**：Pydantic 模型入口已校验的函数可豁免 user_id（但需注释标注"入口已校验"）
5. **配置驱动**：必需 user_id 函数名清单、converter 检查规则从 `config.yaml#db_write_identity_trace` 读取

**关键约束**：
- `grep "def upsert_\|def insert_\|def update_\|def create_" <file>` 无 `user_id` 参数 → 视为 WARNING（跨用户风险）
- `grep "lambda m: int"` 无 `group(1)` → 视为 CRITICAL（`int() argument must be a string, not 're.Match'`）
- `grep "WHERE.*task_id" <file>` 但无 `AND user_id` → 视为 WARNING（跨用户写入风险）

**判断信号**：
- `grep "def upsert_\|def insert_\|def update_\|def create_" <file>` 后检查参数是否含 `user_id`
- `grep "lambda m: int" <file>` 检查是否显式 `group(1)`
- `grep "WHERE.*task_id.*$" <file>` 但无 `user_id` 条件 → 跨用户风险

**适用**：所有数据库写入函数（upsert/insert/update/create）；正则 converter 函数；跨用户系统（多用户共享数据库）；含 `re.findall` + converter 的解析逻辑。
**不适用**：系统级写入（如日志表、统计表、全局配置表，无 user_id 概念）、单一调用点的函数（无复用需求）、Pydantic 入口校验后的函数（已校验 user_id）、纯查询函数（SELECT 无写入风险）。

**反模式 1**：
```python
# ❌ 缺 user_id 参数，跨用户写入风险
def upsert_eval_event(event: EventRow):
    session.execute(
        text("INSERT INTO evaluations (task_id, score) VALUES (:task_id, :score)"),
        {"task_id": event.task_id, "score": event.score}
    )
    # 无 user_id，可能写入其他用户的数据
```

**反模式 2**：
```python
# ❌ lambda m: int(m) 报 "int() argument must be a string, not 're.Match'"
_SELLER_LABEL_PATTERNS = {
    "follower_count": (re.compile(r"关注(\d+)"), lambda m: int(m)),  # TypeError
}
```

**正确模式 1**：
```python
# ✅ 含 user_id 参数 + WHERE 子句含 user_id
def upsert_eval_event(event: EventRow, user_id: str):
    session.execute(
        text("INSERT INTO evaluations (task_id, user_id, score) VALUES (:task_id, :user_id, :score)"),
        {"task_id": event.task_id, "user_id": user_id, "score": event.score}
    )
```

**正确模式 2**：
```python
# ✅ 显式调用 m.group(1) 再转型
_SELLER_LABEL_PATTERNS = {
    "follower_count": (re.compile(r"关注(\d+)"), lambda m: int(m.group(1))),
}
```

**历史教训**：`_SELLER_LABEL_PATTERNS` 用 `int` 作为 converter，`re.findall` 返回 `Match` 对象，`int(m)` 报 `TypeError: int() argument must be a string, not a 're.Match'`，导致卖家关注数解析失败。修复：改为 `lambda m: int(m.group(1))`。同期发现 `upsert_eval_event` 缺 `user_id` 参数，多用户场景下可能写入其他用户的评估数据。修复：新增 `user_id: str` 参数 + WHERE 子句含 `user_id` 条件。

> 📖 详见 [database.md](../assets/guides/coding-rules/database.md) step 204。

---

# experimental 元规范（64-65）🆕v4.39.0

> 以下 2 条元规范从 2026-07-08 解决的「SheetWorkspace URL↔状态同步失败回退」「Service Worker 缓存版本同步」2 类问题中提炼，使用 Sequential Thinking 4 维度复盘法（成功步骤 / 不确定性与失败点 / 可抽象的固定流程与判断逻辑 / 适用场景与不适用场景）抽象而成。
>
> **experimental 标签说明**（参考 #36 规范沉淀门槛）：以下规范案例数 <3 次（仅 2026-07-08 一个案例），未达正式规范门槛（≥3 个相似 bug），标 experimental 标签预沉淀，1 季度观察期（2026-07-08 至 2026-10-08）。观察期内若再出现 ≥2 个相似 bug 则升级为正式规范，否则废弃。
>
> 命名空间与配置驱动：所有参数（`url_state_sync_fallback` / `sw_cache_version_sync`）均在 `config.yaml` 对应节点管理，禁止硬编码。

## 79. 长时交互式外部命令两阶段异步模式（LONG-RUNNING-INTERACTIVE-COMMAND-TWO-PHASE）🆕v4.46.0

> 对应 B-REVIEW-222~225（后端审查）/ F-REVIEW-188~190（前端审查）/ coding-rules step 223-228。本规则解决「长时交互式外部命令在 HTTP 请求内阻塞执行导致超时、输出丢失、状态无法跨请求保持」问题。与 #57-#63（异步与资源安全）维度不同：#57-#63 关注 asyncio/线程池资源管理，#79 关注外部命令的交互式执行模式。

**问题背景**：cloudflared tunnel login 是交互式命令（打开浏览器让用户授权），使用 `subprocess.run(cmd, capture_output=True, timeout=30)` 阻塞调用导致三个 P0 问题：① 用户授权耗时超过 30s 触发 axios 超时；② `capture_output=True` 吞掉了授权 URL，用户无法手动打开；③ cert.pem 只检查 `~/.cloudflared/` 单一路径，而 cloudflared 在 Windows 上可能写入 `%LOCALAPPDATA%\.cloudflared\`。

**核心原则**：
1. **两阶段拆分**：交互式命令必须拆分为 POST /start（Popen 非阻塞启动 + 后台线程读 stdout + 短时等待提取关键信息）+ GET /status（轮询检查完成标志），禁止 `subprocess.run` 阻塞调用
2. **后台 stdout 读取**：禁止 `capture_output=True`（阻塞到进程结束），必须用 `Popen + stdout=PIPE + stderr=STDOUT + text=True` + `daemon=True` 后台线程逐行读取并实时提取关键信息
3. **完成标志多路径检测**：文件类完成标志（cert.pem、credentials.json）必须检测所有可能路径（平台默认 + 环境变量派生 + 输出正则提取），失败时返回 `checked_paths` 辅助诊断
4. **全局单例状态保持**：两阶段需在同一实例上调用，必须通过模块级全局单例 + get/reset 管理函数保持跨请求状态；success/failed/exception 三条退出路径都必须调用 reset
5. **三步清理协议**：子进程清理必须 `terminate → wait(timeout) → kill`，try/except/finally 包裹，finally 置 None，函数必须幂等
6. **前端四态轮询**：轮询必须处理 waiting/success/failed/idle 四态，idle 表示服务端单例已重置；定时器存 useRef，组件卸载时 cleanup

**判断信号（grep / 静态检查）**：
- `grep -rn "subprocess.run.*timeout=" src/` 命中且命令涉及用户交互 → 违反两阶段拆分
- `grep -rn "capture_output=True" src/` 命中且输出含关键信息 → 违反实时读取
- 完成标志检测只检查单一路径 → 违反多路径检测
- 全局单例 reset 函数未调用子进程清理方法 → 子进程泄漏
- `grep -rn "setInterval" frontend/src/` 命中但无对应 `clearInterval` → 定时器泄漏
- 轮询分支只有 success/failed 两态 → 缺少 idle 兜底

**配置驱动**：
- 两阶段触发条件、启动等待超时、清理超时、检测路径、输出解析正则均通过 `config.yaml#external_command_interaction` 节点管理
- 前端轮询间隔、状态枚举、清理场景通过 `config.yaml#async_polling_pattern` 节点管理
- 禁止在代码中硬编码超时值、路径列表、轮询间隔

**适用场景**：
- 交互式外部命令（OAuth 授权、浏览器登录、SSH key 确认）
- 运行时间不可预测的命令（依赖用户操作、网络条件）
- 输出包含关键信息的命令（授权 URL、token、session ID）
- 完成标志为文件生成的命令（cert.pem、credentials.json）
- 需跨 HTTP 请求保持子进程状态的场景

**不适用场景**：
- 短时确定性命令（ls、git status、curl 简单请求）→ 直接 `subprocess.run`
- 无需用户交互的批处理命令 → 异步任务队列
- 输出无需实时提取的命令 → `capture_output` 即可
- 单次请求内完成的操作 → 无需全局单例
- 完成标志明确单一的命令 → 无需多路径检测

**与 #57-#63 的区别**：
- #57-#63 关注 asyncio/线程池/资源的异步安全管理（同进程内并发）
- #79 关注外部命令的交互式执行模式（跨进程 + 跨 HTTP 请求）
- 两者互补：#79 的后台线程读取 stdout 属于 #57-#63 的线程安全范畴，但 #79 额外解决两阶段拆分和跨请求状态问题

**复盘来源**：Cloudflare Named Tunnel login 失败 Bug（`login 失败: login 似乎成功但未找到 cert.pem`）。根因：9 个隐患（P0: subprocess.run 阻塞 + 30s axios 超时、capture_output 吞授权 URL、cert.pem 单路径检测；P1: --no-autoupdate 位置错误、失败无 stdout/stderr、正则不兼容 Windows 空格路径；P2: 30s 超时过紧、ready_pattern 版本不兼容、子进程泄漏）。修复：两阶段异步模式（POST start + GET poll）+ Popen 非阻塞 + 后台线程读 stdout + 4 路径 cert.pem 检测 + 全局单例 + 三路径清理 + 前端 2500ms 四态轮询。

## 80. async 阻塞调用超时保护（ASYNC-BLOCKING-CALL-TIMEOUT）🆕v4.48.0

**问题背景**：浏览器登录成功后进入 Cookie 导出阶段（`_prepare_login_cookie_export`），其中的 `await context.cookies()` 与 `await bc.storage_state()` 是 Playwright 通过 IPC 通道与浏览器进程通信的 async 调用。当浏览器进程无响应或 IPC 通道阻塞时，这两个调用会永久挂起，既不返回也不抛异常。由于心跳线程依赖主流程定期调用 `set_status` 更新 status file 的 `ts` 字段，主流程挂起后心跳随之停止，后端 90s 后误判为"登录进程无响应"并强制中断，但实际登录早已成功。此类 Bug 的根因不是业务逻辑错误，而是缺少对"可能永久挂起的 async API"的超时保护。

**核心原则**：
1. 所有可能永久挂起的 async API 调用（Playwright IPC、外部进程 await、网络读取等）必须用 `asyncio.wait_for(coro, timeout=...)` 包裹，禁止裸 `await`
2. 超时值按调用成本分类从 `config.yaml#asyncTimeoutProtection.timeoutByCategory` 读取，禁止硬编码：
   - `lightweightRead`（轻量读取，如 `title`/`url`）
   - `heavySerialize`（重序列化，如 `cookies`/`storage_state`/`snapshot`）
   - `evaluate`（JS 执行，如 `evaluate`）
3. 超时触发后必须提供 fallback（返回空列表 / 返回缓存 / 跳过当前阶段），不中断主流程；fallback 策略从 `config.yaml#asyncTimeoutProtection.fallbackStrategy` 读取
4. 超时日志必须包含阶段名、调用 API、配置超时值、实际耗时，便于定位是哪一类 IPC 阻塞

**判断信号**：
- `grep "await.*\.(cookies|storage_state|snapshot|title|url|evaluate)\("` 命中但未被 `asyncio.wait_for` 包裹 → 违反
- `grep "asyncio.wait_for" <file>` 数量 < `grep "await.*\.(cookies|storage_state|snapshot|title|url|evaluate)\("` 数量 → 部分调用未保护
- 配置文件 `asyncTimeoutProtection.enabled=false` 或缺失该节点 → 整体禁用超时保护

**配置驱动**：
- `asyncTimeoutProtection.enabled`：是否启用（默认 true）
- `asyncTimeoutProtection.timeoutByCategory.lightweightRead`：轻量读取超时（秒）
- `asyncTimeoutProtection.timeoutByCategory.heavySerialize`：重序列化超时（秒）
- `asyncTimeoutProtection.timeoutByCategory.evaluate`：JS 执行超时（秒）
- `asyncTimeoutProtection.fallbackStrategy`：fallback 策略（best_effort / cached / abort）
- `asyncTimeoutProtection.auditGrepPattern`：审查用 grep 正则
- 禁止在代码中硬编码超时值

**适用场景**：
- Playwright 浏览器自动化（cookies / storage_state / snapshot / title / url / evaluate）
- 任何跨进程 IPC 的 async 调用（浏览器进程 / 子进程 / 长连接）
- 网络读取类 async API（httpx 流式读取、websocket recv）
- 文件 I/O 类 async API（aiofiles 大文件读取）
- 依赖外部资源响应的 await 调用（无法预测响应时间）

**不适用场景**：
- 纯内存计算类 async 调用（asyncio.Lock / asyncio.Queue 的 acquire/get，本身有内部机制）
- 已有显式 timeout 参数的 API（如 `httpx.AsyncClient.get(timeout=...)`）→ 重复包裹反而干扰
- 框架级 timeout 已覆盖的场景（如 FastAPI 请求级 timeout）
- 单元测试中的 mock async 调用（不会真正阻塞）

**与其他规则区别**：
- 与 #57-#63（async/资源安全）的区别：#57-#63 关注同进程内的 async 同步性与资源生命周期；#80 专门解决跨进程 IPC 永久挂起问题
- 与 #79（外部命令交互）的区别：#79 关注两阶段拆分与跨请求状态；#80 关注阶段内单个 await 调用的超时保护
- 与 #81（子进程心跳协同）配合：#80 是阶段内单个调用的超时，#81 是阶段级总超时与心跳阈值的协同

**复盘来源**：浏览器登录 Cookie 导出阶段 IPC 阻塞导致 90s 心跳超时误判 Bug（2026-07-18 修复）。根因：`_prepare_login_cookie_export` 中 `await context.cookies()` 和 `await bc.storage_state()` 在浏览器进程无响应时永久挂起，导致心跳 `set_status` 无法更新 `ts` 字段，后端 90s 后误判卡死报"登录进程无响应"。修复：所有 Playwright async API 调用统一用 `asyncio.wait_for` 包裹，按调用成本分类配置超时，超时后走 fallback 不中断主流程。

## 81. 子进程心跳与阶段超时协同（SUBPROCESS-HEARTBEAT-STAGE-COORDINATION）🆕v4.48.0

**问题背景**：项目采用 `subprocess.Popen` 启动长时交互式子进程（如浏览器登录脚本），主进程通过定期读取 status file 中的 `ts` 字段判断子进程是否存活。但 status file 只有一个状态字段（如 `status=running`），未区分阶段（starting / opening / running / waiting / already_logged），导致某些阶段（如 `waiting` 等待用户扫码）天然耗时长，被误判为卡死。同时，阶段内多个阻塞调用的累计耗时如果接近或超过心跳阈值，会导致 `ts` 字段更新不及时，触发误报。这类 Bug 的根因是缺少阶段级超时与心跳阈值的协同约束。

**核心原则**：
1. subprocess.Popen + status file 心跳架构中，每阶段必须定义独立 status（如 `starting`/`opening`/`running`/`waiting`/`already_logged`）+ 独立超时阈值，从 `config.yaml#subprocessHeartbeat.timeoutByStatus` 读取
2. 阶段内所有阻塞调用超时之和必须 < 心跳阈值 × (1 - safety_margin)，safety_margin 从 `config.yaml#subprocessHeartbeat.safetyMargin` 读取（默认 0.3）
3. 心跳线程更新 status file 时必须同时写入 `status` 和 `ts` 两个字段，后端按 status 查对应阈值，不再用统一 90s
4. 累计超时超过 `maxAccumulatedTimeoutWarn`（默认 30s）时记录 WARNING 日志，提示开发者审查阶段超时配置

**判断信号**：
- `grep "subprocess.Popen"` + `grep "status_file"` 同文件出现 → 必须配置阶段级超时
- status file 只写 `ts` 不写 `status` → 后端无法按阶段区分阈值
- 所有阶段共用同一超时值（如全部 90s）→ 未实现阶段级配置
- 阶段内多个 `asyncio.wait_for` 累计超时 ≥ 心跳阈值 × (1 - safety_margin) → 必须调整

**配置驱动**：
- `subprocessHeartbeat.enabled`：是否启用（默认 true）
- `subprocessHeartbeat.timeoutByStatus.starting`：starting 阶段超时（秒）
- `subprocessHeartbeat.timeoutByStatus.opening`：opening 阶段超时（秒）
- `subprocessHeartbeat.timeoutByStatus.running`：running 阶段超时（秒）
- `subprocessHeartbeat.timeoutByStatus.waiting`：waiting 阶段超时（秒，通常较短）
- `subprocessHeartbeat.timeoutByStatus.already_logged`：already_logged 阶段超时（秒）
- `subprocessHeartbeat.safetyMargin`：安全边际比例（默认 0.3，即阶段内累计超时 ≤ 阈值的 70%）
- `subprocessHeartbeat.maxAccumulatedTimeoutWarn`：累计超时警告阈值（秒）
- 禁止在代码中硬编码阶段超时

**适用场景**：
- subprocess.Popen 启动的长时子进程（浏览器登录、OAuth 授权、外部命令交互）
- 通过 status file 心跳监控子进程存活的所有场景
- 跨 HTTP 请求的子进程状态管理（与 #79 配合）
- 子进程有多个明确阶段（如启动→打开→运行→等待→完成）的场景
- 阶段间耗时差异显著（如 waiting 30s vs running 90s）的场景

**不适用场景**：
- 短时确定性命令（subprocess.run + capture_output）→ 无需心跳
- 同步阻塞调用（无 status file 心跳机制）→ 不适用
- 单阶段子进程（无阶段区分需求）→ 用统一超时即可
- 进程内 asyncio 任务（无子进程 IPC）→ 走 #80 即可

**与其他规则区别**：
- 与 #79（外部命令交互）的区别：#79 关注两阶段拆分（POST start + GET poll）+ 跨请求状态管理；#81 关注阶段内总超时与心跳阈值的协同
- 与 #80（async 阻塞调用超时）配合：#80 是单次调用的超时保护，#81 是阶段级总超时的约束；两者一起构成"单点超时 + 阶段总超时"双层防护
- 与 #25（批量处理四要素）的区别：#25 关注批处理的熔断/进度持久化；#81 关注子进程心跳的阶段级配置

**复盘来源**：浏览器登录 Cookie 导出阶段 IPC 阻塞导致 90s 心跳超时误判 Bug（2026-07-18 修复）。根因：status file 仅 `status=running` 一个状态，后端用统一 90s 阈值监控所有阶段；`_prepare_login_cookie_export` 阶段内 `context.cookies()` 与 `storage_state()` 累计阻塞超过 90s，心跳 `ts` 字段未更新，后端误判卡死。修复：每阶段独立 status + 独立阈值，阶段内累计超时 < 心跳阈值 × (1 - 0.3)，超出时记录 WARNING 提示审查配置。

## 82. 跨代码块一致性检查（CROSS-BLOCK-CONSISTENCY-CHECK）🆕v4.48.0 experimental

> **experimental 标签**：本规则基于单一 Bug 复盘沉淀，需更多案例验证才能升级为正式规则。当前作为推荐性规范执行，季度复盘时评估升级条件。

**问题背景**：浏览器登录流程中，同一类 Playwright API 调用散落在多个代码块（`_prepare_login_cookie_export`、`_verify_login_state`、`_inject_cookies` 等），早期对 `context.cookies()` 加了 `asyncio.wait_for` 保护，但 `bc.storage_state()` 在另一代码块中调用却遗漏了保护。这种"同一 API 在不同代码块保护措施不一致"的问题，单纯靠 review 难以发现，因为 reviewer 通常聚焦单个代码块的逻辑，而非跨块的一致性。根因是缺少"同一 API 多处调用时保护措施必须一致"的硬性约束。

**核心原则**：
1. 同一 API（如 `context.cookies()`、`bc.storage_state()`）在 ≥2 处代码块调用时，保护措施（超时 / 异常处理 / fallback）必须一致，以更严格为准同步修复
2. 一致性维度包括：是否包裹 `asyncio.wait_for`、超时值是否同量级、异常处理是否同类型（try/except vs raise）、fallback 策略是否相同
3. 当发现某 API 在 A 处有保护、B 处无保护时，必须将 B 处同步升级到 A 处的保护级别，禁止"只在 review 触发的位置补丁式修复"
4. `min_occurrences`（最小出现次数，默认 2）从 `config.yaml#consistencyCheck.minOccurrences` 读取，扫描路径从 `config.yaml#consistencyCheck.scanPaths` 读取

**判断信号**：
- grep 同一 API 名（如 `context.cookies`），统计出现次数 ≥ `minOccurrences`（默认 2）→ 必须做一致性检查
- 同一 API 在 A 文件有 `asyncio.wait_for` 包裹，在 B 文件裸 `await` → 不一致
- 同一 API 在 A 文件 try/except 兜底返回 `[]`，在 B 文件抛原始异常 → 不一致
- 同一 API 在 A 文件超时值从 config 读取，在 B 文件硬编码 → 不一致

**配置驱动**：
- `consistencyCheck.enabled`：是否启用（默认 true）
- `consistencyCheck.minOccurrences`：触发一致性检查的最小出现次数（默认 2）
- `consistencyCheck.scanPaths`：扫描的文件路径列表
- `consistencyCheck.reviewCheckpoint`：审查 checkpoint 名（B-REVIEW-228）
- 禁止在代码中硬编码 minOccurrences 或 scanPaths

**适用场景**：
- 同一 Playwright API 在多个函数 / 多个文件调用的场景
- 同一 httpx 调用在多模块复用的场景
- 同一外部服务 SDK 调用散落多个代码块的场景
- 重构后同一 API 在新旧代码并存的过渡期

**不适用场景**：
- API 只在单处调用（无一致性需求）
- 不同 API 但功能相似（如 `cookies()` 与 `storage_state()`）→ 走 #80 统一保护，不强制一致性
- 测试代码中的 mock 调用（不真正执行，无需一致性）
- experimental 阶段未达 minOccurrences 的 API

**与其他规则区别**：
- 与 #80（async 阻塞调用超时）配合：#80 定义单次调用的保护范式，#82 确保同 API 多处调用时保护范式一致
- 与 #34（修复前安全链路根因扫描）的区别：#34 关注"修复一个 bug 时扫描所有相关 pattern 是否有同样问题"；#82 关注"同一 API 多处调用时保护措施的一致性"，更聚焦 API 维度
- 与 #46（测试同步责任）的区别：#46 关注测试与生产代码的同步；#82 关注生产代码内部跨块的一致性

**复盘来源**：浏览器登录 Cookie 导出阶段 IPC 阻塞导致 90s 心跳超时误判 Bug（2026-07-18 修复）。根因：`context.cookies()` 在 `_prepare_login_cookie_export` 中已有部分保护，但 `bc.storage_state()` 在同一函数内调用却完全无保护；同时 `context.cookies()` 在 `_verify_login_state` 中也无保护。修复：对所有调用点统一加 `asyncio.wait_for`，超时值从 config 统一读取，确保同 API 跨块保护一致。
