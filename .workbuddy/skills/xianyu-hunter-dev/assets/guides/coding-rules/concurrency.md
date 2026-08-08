# Concurrency 编码规范
> 本文件归档 xianyu-hunter-dev skill 中与「concurrency」主题相关的编码规范。
> 主索引见 [SKILL.md](../../../SKILL.md) 的"step 索引表"，元规范见 [meta-rules.md](../../../references/meta-rules.md)。

---

### step 27：死代码与资源生命周期【强制】🆕v4.3

27. **死代码与资源生命周期【强制】🆕v4.3**
    - 创建的长期存活对象（Proxy/Observer/Listener/Task）必须赋值给有生命周期的变量（实例属性/模块级变量），**禁止**赋值给局部变量后丢弃
    - `try/finally` 块中使用的变量必须在 `try` 之前初始化为 `None`，确保 `finally` 不会因未绑定而抛 `UnboundLocalError`
    - **判断信号**：`new Proxy()` / `new MutationObserver()` / `asyncio.create_task()` 的返回值赋值给局部变量；`try` 块内赋值的变量在 `finally` 中被引用
    - **修复模式**：监听器赋值给实例属性（`self._observer = new MutationObserver(...)`）；资源变量 `page = None` 前置初始化
    - **适用**：所有需要长期存活的监听器/观察者/后台任务；所有 try/finally 资源清理
    - **不适用**：一次性使用的临时对象、`with` 语句（自动管理生命周期）
    - **历史教训**：`awsc_spoof.py` 的 `var baxiaProxy = new Proxy(...)` 赋值给局部变量后从未使用，验证码触发事件永远不会被派发；`api_anticrawl.py` 的 `renew_callback` 中 `page` 变量未初始化，`new_page()` 抛异常时 `finally` 中 `page.close()` 报 `UnboundLocalError`


---

### step 33：独立调度器隔离模式【强制】🆕v4.4

33. **独立调度器隔离模式【强制】🆕v4.4**
    - 生命周期/优先级不同的后台任务必须使用独立 APScheduler `BackgroundScheduler`，避免与项目主调度器耦合
    - **判断信号**：后台任务生命周期与应用主调度器不同 + 共享状态有冲突风险 + 任务优先级不同
    - **修复模式**：创建独立 `BackgroundScheduler()` → 独立 `add_job()` 注册 → 独立 `start()`/`shutdown()` 钩子 → 不共享 jobstore
    - **配置参数**：`scheduler_name`、`max_instances`、`coalesce`、`misfire_grace_time` 在 `config/scheduler.yaml` 管理
    - **适用**：Cookie 同步调度器、健康检查调度器、生命周期不同于主任务调度器的辅助任务
    - **不适用**：紧耦合任务调度、共享状态访问需求、资源限制环境（内存敏感场景应合并调度器）
    - **历史教训**：Cookie 同步任务若复用项目主任务调度器，会与采集任务的优先级产生冲突，且 shutdown 时序复杂；独立调度器后生命周期清晰


---

### step 34：配置驱动功能开关模式【强制】🆕v4.4

34. **配置驱动功能开关模式【强制】🆕v4.4**
    - 高风险/高资源消耗功能默认关闭，需用户显式启用；所有功能参数集中在 `Config` 类（如 `BrowserConfig`），不硬编码
    - **判断信号**：功能需用户主动选择 + 可能耗资源（CPU/内存/网络） + 多环境部署需求
    - **修复模式**：`Config` 类新增 `enable_flag: bool = False` + 详细参数字段 → `config.yaml` 暴露开关 → 文档明确启用条件与资源消耗
    - **配置参数**：`enable_flag` 默认 `false`，详细参数（interval/threshold/port）集中在相应 `Config` 类
    - **适用**：CDP 在线导入、Cookie 自动同步、向量库重建等高风险/高资源消耗功能
    - **不适用**：核心功能（必须默认启用）、性能敏感场景（配置加载延迟不可接受）、简单脚本工具
    - **历史教训**：`auto_sync` 默认 `false`，避免用户不知情下启用自动同步导致浏览器资源被占用；`cdp_port` 通过 `BrowserConfig` 管理而非硬编码


---

### step 35：降级链模式【强制】🆕v4.4

35. **降级链模式【强制】🆕v4.4**
    - 多重方案按优先级排序，失败后自动降级，3 次失败加倍间隔，最大间隔 2 小时
    - **判断信号**：多方案优先级明确 + 网络不稳定环境 + 外部依赖不可控
    - **修复模式**：方案 A 失败 → 尝试方案 B → 方案 B 失败 N 次后触发 backoff（`interval *= 2`，上限 `max_interval`）→ 记录降级原因到日志
    - **配置参数**：`max_failures=3`、`backoff_multiplier=2`、`max_interval=7200` 在 `config/fallback.yaml` 管理
    - **适用**：Cookie 同步（offline import → CDP import → backoff）、网络重试、外部 API 调用
    - **不适用**：单一方案场景、降级后体验差于报错（应直接失败）、关键安全场景（必须 fail-fast）
    - **历史教训**：Cookie 同步调度器实现 offline import 优先 → CDP import 次之 → backoff 兜底的降级链，3 次失败后间隔加倍避免无意义重试


---

### step 50：异步操作整体超时保护【强制】🆕v4.7

50. **异步操作整体超时保护【强制】🆕v4.7**
    - 所有 `await` 调用外部资源（浏览器自动化、HTTP 客户端、IO 操作、远程 API）的异步操作，必须在**调用层**用 `asyncio.wait_for(coro, timeout=N)` 包装整体超时，超时后返回语义化状态码（如 504 网关超时），禁止依赖被调用方内部 timeout 参数
    - **判断信号**：代码含 `await container.<module>.<method>(...)` / `await client.<method>(...)` / `await page.<method>(...)` 调用外部资源 → 必须检查是否被 `asyncio.wait_for` 包裹；被调用方内部 `timeout` 参数不视为整体超时保护
    - **修复模式**：
      ```python
      try:
          detail = await asyncio.wait_for(
              container.collector.detail(item_id), timeout=60.0
          )
      except asyncio.TimeoutError:
          logger.warning("[RefreshItem] 采集超时 item=%s（%ss），外部资源可能异常", item_id, timeout)
          raise HTTPException(status_code=504, detail="采集超时：外部资源异常或被反爬拦截，请稍后重试")
      except Exception as e:
          logger.warning("[RefreshItem] 采集失败 item=%s: %s", item_id, e)
          raise HTTPException(status_code=502, detail=f"采集失败：{e}")
      ```
    - **关键约束**：
      - 超时时间必须从配置读取（`config.async_timeout.<operation>_seconds`），**禁止**硬编码
      - 超时后必须返回明确状态码（504=超时、502=失败、503=稍后重试），便于前端按状态码分类处理
      - 超时日志必须记录操作类型 + 资源 ID + 超时秒数，便于排查
      - `asyncio.CancelledError` 不应被 `wait_for` 的 `TimeoutError` 吞掉，应单独传播
    - **配置参数**：`timeout_seconds`（默认 60）、`max_retries`（默认 0=不重试）、`status_code_mapping`（超时→504、失败→502）在 `config.yaml` 的 `async_timeout` 节点管理
    - **适用**：所有 `await` 外部资源的异步操作（浏览器自动化、HTTP 请求、远程 API、IO 操作、子进程调用）
    - **不适用**：有内建 timeout 的 HTTP 客户端（`httpx.Timeout` 已配置）、纯计算函数、`asyncio.CancelledError` 传播路径、有重试机制（如 tenacity）包裹的场景
    - **历史教训**：`refresh_item` 调用 `collector.detail(item_id)` 时，`page.query_selector` 无 `timeout` 参数，闲鱼反爬 RGV587 拦截后浏览器实例异常导致 `query_selector` 无限挂起，前端 90 秒后客户端超时无任何错误提示。修复后 `refresh_item` 加 `asyncio.wait_for(..., timeout=60.0)` + 504 响应，14.4 秒返回明确错误


---

### step 61：资源生命周期规范【强制】🆕v4.10

61. **资源生命周期规范【强制】🆕v4.10**
    - 所有可注册的组件（Worker/Adapter/Plugin/Handler）必须实现 `cleanup()` 钩子，由调度器/容器在 `unregister` 时统一调用，确保资源释放
    - **关键约束**：
      1. **cleanup 钩子约定**：即使当前实现为空，也必须保留 `async def cleanup(self) -> None: return None` 方法（为未来扩展预留接入点，参考 `TaskWorker.cleanup`）
      2. **asyncio.Task 引用保留**：后台任务必须 `self._task = asyncio.create_task(...)` 保留引用防 GC，**禁止**裸 `asyncio.create_task(...)` 不持有引用
      3. **取消+收集模式**：取消后台任务必须 `task.cancel()` + `await asyncio.gather(task, return_exceptions=True)`，确保资源清理完成
      4. **try/finally 初始化**：`try/finally` 块中 `finally` 引用的变量必须在 `try` 之前初始化为 `None`（`page = None; try: page = await ...; finally: if page: await page.close()`）
      5. **锁内原子检查**：共享状态（计数器/冷却时间）的「检查+更新」必须在同一锁内完成，避免竞态
    - **判断信号**：组件有「注册/注销」生命周期 + 持有后台任务/连接/锁/文件句柄 → 必须按此流程设计
    - **修复模式**：
      ```python
      # ✅ cleanup 钩子 + Task 引用保留 + cancel+gather
      class TaskWorker:
          def __init__(self):
              self._task: asyncio.Task | None = None

          async def cleanup(self) -> None:
              """Worker 资源清理钩子，供 scheduler.unregister 调用"""
              if self._task is not None and not self._task.done():
                  self._task.cancel()
                  await asyncio.gather(self._task, return_exceptions=True)
                  self._task = None
      ```
    - **配置参数**：`lifecycle.cleanup_method_name`（默认 `cleanup`）、`lifecycle.task_cancel_timeout`（默认 5s）、`lifecycle.required_cleanup_components`（必须实现 cleanup 的组件类型列表）在 `config.yaml` 的 `resource_lifecycle` 节点管理
    - **适用**：可注册组件（Worker/Adapter/Plugin/Handler）、持有后台任务的组件、持有连接/锁/文件句柄的组件
    - **不适用**：纯函数（无状态无副作用）；一次性脚本（进程结束即释放）；纯数据对象（无生命周期）
    - **历史教训**：`TaskWorker` 缺少 `cleanup()` 方法，`TaskScheduler.unregister` 时无法释放 worker 持有的资源；`_WorkerHandle` 缺少 `loop_task` 字段声明导致 `getattr` 兜底反模式。修复后 `TaskWorker` 实现 cleanup 钩子，`_WorkerHandle` 显式声明所有字段


---

### step 63：并发安全规范【强制】🆕v4.10

63. **并发安全规范【强制】🆕v4.10**
    - 多线程/协程访问同一共享状态（计数器/冷却时间/最后执行时间）时，「检查+更新」必须在同一锁内完成，避免竞态
    - **关键约束**：
      1. **锁内原子检查**：共享状态的「检查+更新」必须在同一锁内（`with self._lock: if can_proceed(): self._last_run = now()`）
      2. **锁粒度最小化**：锁仅保护临界区（检查+更新），**禁止**用锁保护 IO（如 `await` 网络请求），避免阻塞其他协程
      3. **锁内禁止 await**：`asyncio.Lock` 内禁止 `await` 长时间操作（会导致锁持有过久），必要时先释放锁再做 IO
      4. **Dataclass 字段显式声明**：dataclass 字段必须显式声明默认值（`consecutive_errors: int = 0`），**禁止**用 `getattr(h, 'consecutive_errors', 0)` 兜底（反模式，掩盖字段未初始化的 bug）
      5. **锁类型选择**：跨线程用 `threading.RLock`（可重入），跨协程用 `asyncio.Lock`，**禁止**混用
    - **判断信号**：多线程/协程访问同一字段 + 字段有「检查-更新」模式（如 `if self._last_run + interval < now: self._last_run = now()`）→ 必须加锁
    - **修复模式**：
      ```python
      # ✅ 锁内原子检查 + Dataclass 字段显式声明
      @dataclass
      class _WorkerHandle:
          consecutive_errors: int = 0  # ✅ 显式声明，禁止 getattr 兜底

      class Scheduler:
          def __init__(self):
              self._lock = threading.RLock()
              self._handles: dict[str, _WorkerHandle] = {}

          def _check_and_update(self, task_id: str) -> bool:
              with self._lock:  # 锁内原子检查+更新
                  h = self._handles[task_id]
                  if h.consecutive_errors >= threshold:
                      return False
                  h.consecutive_errors += 1
                  return True
      ```
    - **配置参数**：`concurrency.lock_type`（默认 `RLock`）、`concurrency.critical_section_max_await`（默认 `0`，禁止 await）、`concurrency.required_lock_fields`（必须加锁保护的字段名列表）在 `config.yaml` 的 `concurrency_safety` 节点管理
    - **适用**：多线程/协程访问同一共享状态；定时任务与 API 请求并发修改同一数据
    - **不适用**：单线程顺序执行；thread-local 数据；不可变对象
    - **历史教训**：`_WorkerHandle` 缺少 `consecutive_errors` 字段声明，代码用 `getattr(h, 'consecutive_errors', 0) + 1` 兜底，掩盖了字段未初始化的 bug；并发场景下「检查+更新」未在锁内可能导致竞态。修复后显式声明字段 + 锁内原子检查


---

### step 74：后台任务健康监控【强制】🆕v4.12

74. **后台任务健康监控【强制】🆕v4.12**
    - 后台任务（EventBus 消费者 / 调度器循环 / 健康检查器）必须用轮询监控（`while not stop_event.is_set(): if task.done(): break; await asyncio.wait_for(stop_event.wait(), timeout=N)`），**禁止** `await asyncio.Event().wait()` 静默等待导致任务异常退出时主循环无感知
    - **判断信号**：代码含 `bus_task = asyncio.create_task(...)` 后 `await stop_event.wait()` → 必须改为轮询检查 `bus_task.done()`
    - **修复模式**：
      ```python
      # ✅ 轮询监控后台任务
      stop_event = asyncio.Event()
      while not stop_event.is_set():
          if bus_task.done():
              exc = bus_task.exception()
              if exc:
                  logger.error("EventBus 异常退出：{}", exc)
              else:
                  logger.warning("EventBus 已退出")
              break
          try:
              await asyncio.wait_for(stop_event.wait(), timeout=10.0)
          except asyncio.TimeoutError:
              continue  # 超时继续下一轮检查

      # ❌ 错误：Event.wait 静默等待，bus_task 异常退出无感知
      # bus_task = asyncio.create_task(event_bus.run())
      # await stop_event.wait()  # bus_task 死了也不知道
      ```
    - **配置参数**：`background_task_monitor.poll_interval_seconds`（默认 `10`，轮询间隔）、`background_task_monitor.monitored_tasks`（必须监控的后台任务名列表，如 `["event_bus", "scheduler_loop", "health_check"]`）、`background_task_monitor.on_task_exit`（默认 `log_and_break`，可选 `restart`）在 `config.yaml` 的 `background_task_monitor` 节点管理
    - **适用**：所有后台 asyncio.Task（EventBus / Scheduler / Health Checker / Cookie Sync / KB Refresh）；需要在主循环中感知子任务退出的场景
    - **不适用**：fire-and-forget 任务（不需感知退出）；一次性任务（如启动初始化）；有 done_callback 处理的任务
    - **历史教训**：`startup._scheduler_loop` 用 `await stop_event.wait()` 等待关闭信号，EventBus 任务异常退出时主循环无感知，事件推送静默失效 30 分钟才被用户发现


---

### step 95：长耗时异步请求 race condition 防护规范【强制】🆕v4.17

**背景**：Vision 推理 90s 期间用户切换商品，旧请求的 result/error/loading 污染新商品 UI 状态；原 onAIEval（60s）也存在同源问题。

**规范**：
1. 任何 > 3s 的异步请求（LLM Vision/批量采集/重型 DB 查询）必须用 `useRef` 跟踪最新请求 ID
2. 旧请求的 result/error/loading 三态在 setState 前必须校验 `ref.current === itemId`，不匹配则丢弃
3. finally 块同样校验，避免提前关闭新请求的 loading

**判断逻辑**：
- grep 前端 `client.post` / `client.get` 调用看是否有 `timeout` 参数 >= 3000
- 或调用方为 LLM/批量类（`aiApi.deepAnalyze` / `aiApi.evaluateCondition` / `evalApi.batchEvaluate`）
- 有则强制加 `useRef` 防护

**代码模板**：
```typescript
const itemIdRef = useRef('')
const onXxx = async (itemId: string) => {
  itemIdRef.current = itemId
  setLoading(true)
  setResult(null)
  try {
    const result = await api.fetch(itemId)
    if (itemIdRef.current !== itemId) return  // 丢弃过期结果
    setResult(result)
  } catch (err) {
    if (itemIdRef.current !== itemId) return  // 丢弃过期错误
    handleError(err)
  } finally {
    if (itemIdRef.current === itemId) {  // 仅最新请求结束 loading
      setLoading(false)
    }
  }
}
```

**配置参数**：`async_race_condition` 节点（enabled / threshold_ms / detect_patterns / abort_controller_preferred）

**适用场景**：timeout >= 3s 的异步请求 + 用户可触发多次切换商品/任务/对象的场景（Modal 内异步、列表行按钮异步）
**不适用场景**：同步请求（< 1s）；一次性请求（页面加载）；用户无法重复触发（如表单提交后禁用按钮）；请求顺序由用户显式控制（如分页加载）

注：`AbortController` 是更优解但需后端支持取消；`useRef` 方案是通用轻量解，无需后端配合。


---

### step 198：ASYNC-AWAIT-SYNC-CHECK async/await 同步性静态检查【强制】🆕v4.38

**背景**：本轮对话修复的 8 类问题之一——`async def` 方法体内不含 `await` 表达式（或仅 await 同步函数），导致 asyncio 事件循环被阻塞、并发性能退化为串行，且 Python 3.14 已对此类反模式强化告警。

**问题**：开发者将同步函数标记为 `async def` 但未在内部真正 await 异步操作，造成两种危害：① 调用点被迫 `await` 一个本质同步的操作，徒增事件循环负担；② Python 3.14+ 对此反模式有运行时告警，但项目未在静态检查阶段拦截。

**规范**：

1. **async def 方法体内必须含至少一个真异步 await【强制】**：`async def` 声明的方法体内若不含 `await <coroutine>` 表达式（或仅 `await` 同步函数返回值），必须改为同步 `def`，调用点同步移除 `await`。
   ```python
   # ❌ 错误：async def 内部无真异步 await，徒增事件循环负担
   async def get_user_name(user_id: str) -> str:
       row = db.query(User).filter_by(id=user_id).first()  # 同步 DB 调用
       return row.name if row else ""

   # ✅ 正确：同步函数，调用点不 await
   def get_user_name(user_id: str) -> str:
       row = db.query(User).filter_by(id=user_id).first()
       return row.name if row else ""
   ```

2. **调用点 await 与函数声明必须同步【强制】**：当 `async def` 改为 `def` 时，所有调用点的 `await xxx()` 必须同步移除 `await`；反向调整时亦然。修改必须覆盖全量调用点，禁止遗漏导致 `TypeError: object str can't be used in 'await' expression`。

3. **静态检查触发条件【强制】**：Code review 时必须用 `grep "async def" <file>` 列出所有异步声明，逐个检查方法体内是否含真异步 `await`；Python 3.14+ 的 `RuntimeWarning: coroutine never awaited` 也是触发信号。

4. **真异步判定【强制】**：`await` 的对象必须是 `coroutine` / `Task` / `Future`，`await` 同步函数返回值（如 `await db.query(...).first()`）不算真异步，应改为同步 `def`。

**配置驱动**：`async_await_check` 节点管理检测规则，包含 `require_true_await`（默认 `true`）、`python_min_version_for_runtime_warning`（默认 `"3.14"`）、`forbidden_patterns`（`async def` 内无 await 的代码模式清单）、`exempt_decorators`（豁免的装饰器列表，如 `@asynccontextmanager`）在 `config.yaml` 管理，不硬编码。

**适用场景**：
- 所有 `async def` 声明的函数（后端 FastAPI 路由、Service、Repository、调度器方法）
- Python 3.10+ 项目（Python 3.14+ 强化告警）
- async/await 与同步 DB 调用混用的代码库

**不适用场景**：
- `@asynccontextmanager` 装饰的异步上下文管理器（即使内部无 await，也保留 async 声明）
- `async def __aenter__` / `async def __aexit__` 协议方法（语义要求 async）
- 测试代码中的 `async def test_xxx()`（pytest-asyncio 框架要求）

**历史教训**：项目早期将多个本质同步的 DB 查询函数标记为 `async def` 但内部用同步 SQLAlchemy 调用，调用点被迫 `await`，FastAPI 路由的并发性能从理论 1000 QPS 退化为串行 50 QPS。Python 3.14 升级后出现 `RuntimeWarning: coroutine never awaited` 告警才被发现。修复后所有无真异步 await 的 `async def` 改为同步 `def`，调用点同步移除 `await`。

**判断信号（review 触发条件）**：
- `grep "async def" <file>` 命中后检查方法体内是否含 `await <coroutine>`
- `RuntimeWarning: coroutine never awaited` 运行时告警
- `TypeError: object str can't be used in 'await' expression` 运行时错误
- `async def` 方法体内仅 `return <value>` 或 `return <sync_call>()`


---

### step 203：EXTERNAL-RESOURCE-LIFECYCLE 外部资源生命周期配对管理【强制】🆕v4.38

**背景**：本轮对话修复的 8 类问题之一——并发场景下 Playwright `Page` 对象在外部资源注册/注销时未配对管理，导致 page 被 GC 后仍被引用、或注册后未清理残留引用，触发 `TargetClosedError` 与内存泄漏。

**问题**：外部资源（Playwright Page/BrowserContext、HTTP 连接池、文件句柄）在多协程环境下注册到容器后，若注销时未配对清理，会出现两类 bug：① 注销时 page 未关闭，残留引用占用内存；② 注册的 page 在使用中被 GC 回收，调用方拿到已关闭的 page 触发 `TargetClosedError`。

**规范**：

1. **register/unregister 必须配对【强制】**：外部资源（Page/BrowserContext/Connection）注册到容器时，必须同时实现 `unregister` 方法清理引用，禁止只 register 不 unregister：
   ```python
   # ✅ 正确：register/unregister 配对
   class PageRegistry:
       def __init__(self):
           self._pages: dict[str, Page] = {}

       async def register(self, key: str, page: Page) -> None:
           self._pages[key] = page

       async def unregister(self, key: str) -> None:
           page = self._pages.pop(key, None)
           if page and not page.is_closed():
               await page.close()  # 配对关闭
   ```

2. **持有强引用防 GC【强制】**：注册到容器的资源必须由容器持有强引用（`self._pages[key] = page`），禁止只传弱引用导致使用中被 GC 回收。与 step 27「死代码与资源生命周期」互补：step 27 管"赋值给有生命周期的变量"，本规范管"register/unregister 配对"。

3. **使用前检测 is_closed【强制】**：从注册表取出 Page/BrowserContext 后必须检测 `is_closed()`，已关闭则重新创建或抛出明确异常：
   ```python
   page = self._pages.get(key)
   if page is None or page.is_closed():
       page = await self._create_new_page()
       self._pages[key] = page
   ```

4. **异常路径必须清理【强制】**：使用外部资源的代码必须用 `try/finally` 包裹，`finally` 块调用 `unregister` 清理，禁止异常路径残留引用。与 step 27「try/finally 块变量前置初始化」配合使用。

5. **并发注销加锁【强制】**：register/unregister 必须在 `asyncio.Lock` 内完成，避免并发注销时同一资源被关闭两次触发 `RuntimeError`。

**配置驱动**：`external_resource_lifecycle` 节点管理配对规则，包含 `required_pair_methods`（必须配对的方法名对，如 `[("register", "unregister"), ("acquire", "release")]`）、`strong_reference_required`（默认 `true`）、`is_closed_check_before_use`（默认 `true`）、`cleanup_in_finally`（默认 `true`）、`lock_required_for_unregister`（默认 `true`）在 `config.yaml` 管理，不硬编码。

**适用场景**：
- Playwright Page/BrowserContext 的注册表管理
- HTTP 连接池（httpx.AsyncClient / aiohttp.ClientSession）的获取与释放
- 文件句柄、socket、subprocess 的注册与清理
- 多协程共享的外部资源池

**不适用场景**：
- `with` 语句管理的同步资源（Python 上下文管理器自动配对）
- `async with` 管理的异步资源（异步上下文管理器自动配对）
- 单次使用即释放的资源（无注册需求）

**历史教训**：项目的 `PageRegistry` 只实现了 `register` 未实现 `unregister`，批量采集任务结束后 page 残留在 `_pages` 字典中，30 分钟累积 50+ 个未关闭的 page，内存从 200MB 涨到 800MB；同时另一处代码取出 page 后未检测 `is_closed()`，page 被 GC 回收后调用方触发 `TargetClosedError`。修复后实现配对的 register/unregister + 使用前 is_closed 检测 + finally 块清理。

**判断信号（review 触发条件）**：
- `grep "def register" <file>` 命中但无对应 `def unregister`
- `grep "page.query_selector" <file>` 前未检测 `page.is_closed()`
- `asyncio.create_task` 创建的任务未持有强引用
- `try/finally` 块中 `finally` 未调用 unregister


---

### step 234：子进程心跳与阶段超时协同【强制】🆕v4.48.0

**背景**：项目采用 `subprocess.Popen` 启动长时交互式子进程（如浏览器登录脚本），主进程通过定期读取 status file 中的 `ts` 字段判断子进程是否存活。当 status file 只有一个状态字段（如 `status=running`），未区分阶段（starting / opening / running / waiting / already_logged）时，某些阶段（如 `waiting` 等待用户扫码）天然耗时长，会被误判为卡死。

**问题**：浏览器登录 Cookie 导出阶段（`_prepare_login_cookie_export`）内 `context.cookies()` 与 `storage_state()` 累计阻塞超过 90s，但 status file 仅 `status=running` 一个状态，后端用统一 90s 阈值监控所有阶段，导致 `ts` 字段未更新被误判为卡死，触发"登录进程无响应"误报。

**规范**：
1. subprocess.Popen + status file 心跳架构中，每阶段必须定义独立 status（如 `starting`/`opening`/`running`/`waiting`/`already_logged`）+ 独立超时阈值，从 `config.yaml#subprocessHeartbeat.timeoutByStatus` 读取，禁止硬编码
2. 阶段内所有阻塞调用超时之和必须 < 心跳阈值 × (1 - safety_margin)，safety_margin 从 `config.yaml#subprocessHeartbeat.safetyMargin` 读取（默认 0.3）
3. 心跳线程更新 status file 时必须同时写入 `status` 和 `ts` 两个字段，后端按 status 查对应阈值，不再用统一 90s
4. 累计超时超过 `maxAccumulatedTimeoutWarn`（默认 30s）时记录 WARNING 日志，提示开发者审查阶段超时配置
5. 配置 `subprocessHeartbeat.enabled=false` 时整体禁用，但必须在 PR 中说明理由

**判断逻辑**：
- `grep "subprocess.Popen"` + `grep "status_file"` 同文件出现 → 必须配置阶段级超时
- status file 只写 `ts` 不写 `status` → 后端无法按阶段区分阈值，违反规范 3
- 所有阶段共用同一超时值（如全部 90s）→ 未实现阶段级配置，违反规范 1
- 阶段内多个 `asyncio.wait_for` 累计超时 ≥ 心跳阈值 × (1 - safety_margin) → 违反规范 2，必须调整

**反例**：
```python
# ❌ 所有阶段共用 90s 阈值，status file 只写 ts 不写 status
import subprocess, time, json

def heartbeat_loop(proc, status_file):
    while proc.poll() is None:
        # ❌ 只写 ts，不区分阶段
        with open(status_file, "w") as f:
            json.dump({"ts": time.time()}, f)
        time.sleep(5)

# 后端
def check_alive(status_file):
    data = json.load(open(status_file))
    # ❌ 统一 90s，waiting 阶段天然耗时长会被误判
    if time.time() - data["ts"] > 90:
        return "登录进程无响应"
    return "alive"
```

**正例**：
```python
# ✅ 每阶段独立 status + 独立阈值 + 累计超时 < 阈值*(1-margin)
import subprocess, time, json
from config import get_config

def heartbeat_loop(proc, status_file, current_stage):
    cfg = get_config().subprocessHeartbeat
    while proc.poll() is None:
        # ✅ 同时写 status 和 ts，后端按 status 查阈值
        with open(status_file, "w") as f:
            json.dump({"status": current_stage, "ts": time.time()}, f)
        time.sleep(5)

def check_alive(status_file):
    cfg = get_config().subprocessHeartbeat
    data = json.load(open(status_file))
    status = data.get("status", "running")
    # ✅ 按 status 查对应阈值
    threshold = cfg.timeoutByStatus.get(status, 90.0)
    if time.time() - data["ts"] > threshold:
        return f"登录进程无响应（stage={status}, threshold={threshold}s）"
    return "alive"

# 阶段内累计超时校验（启动时一次性检查）
def validate_stage_timeouts():
    cfg = get_config().subprocessHeartbeat
    margin = cfg.safetyMargin
    warn_threshold = cfg.maxAccumulatedTimeoutWarn
    for status, stage_threshold in cfg.timeoutByStatus.items():
        # 假设 stage 内有 N 个阻塞调用，累计超时为 sum
        accumulated = _calc_stage_accumulated_timeout(status)
        limit = stage_threshold * (1 - margin)
        if accumulated >= limit:
            logger.warning(
                f"stage={status} accumulated_timeout={accumulated}s "
                f"exceeds limit={limit}s (threshold={stage_threshold}s, margin={margin}) "
                f"review config"
            )
```

**配置参数**（`config.yaml#subprocessHeartbeat`）：
- `enabled`：是否启用（默认 true）
- `timeoutByStatus.starting`：starting 阶段超时（秒）
- `timeoutByStatus.opening`：opening 阶段超时（秒）
- `timeoutByStatus.running`：running 阶段超时（秒）
- `timeoutByStatus.waiting`：waiting 阶段超时（秒，通常较短）
- `timeoutByStatus.already_logged`：already_logged 阶段超时（秒）
- `safetyMargin`：安全边际比例（默认 0.3，即阶段内累计超时 ≤ 阈值的 70%）
- `maxAccumulatedTimeoutWarn`：累计超时警告阈值（秒，默认 30）

**适用场景**：
- subprocess.Popen 启动的长时子进程（浏览器登录、OAuth 授权、外部命令交互）
- 通过 status file 心跳监控子进程存活的所有场景
- 跨 HTTP 请求的子进程状态管理（与 step 223-228 配合）
- 子进程有多个明确阶段（如启动→打开→运行→等待→完成）的场景
- 阶段间耗时差异显著（如 waiting 30s vs running 90s）的场景

**不适用场景**：
- 短时确定性命令（subprocess.run + capture_output）→ 无需心跳
- 同步阻塞调用（无 status file 心跳机制）→ 不适用
- 单阶段子进程（无阶段区分需求）→ 用统一超时即可
- 进程内 asyncio 任务（无子进程 IPC）→ 走 step 233 即可

**历史教训**：浏览器登录 Cookie 导出阶段 IPC 阻塞导致 90s 心跳超时误判 Bug（2026-07-18 修复）。status file 仅 `status=running` 一个状态，后端用统一 90s 阈值监控所有阶段；`_prepare_login_cookie_export` 阶段内 `context.cookies()` 与 `storage_state()` 累计阻塞超过 90s，心跳 `ts` 字段未更新，后端误判卡死。修复：每阶段独立 status + 独立阈值，阶段内累计超时 < 心跳阈值 × (1 - 0.3)，超出时记录 WARNING 提示审查配置。

**判断信号（review 触发条件）**：
- `grep "subprocess.Popen"` + `grep "status_file"` 同文件出现 → 必须配置阶段级超时
- status file 只写 `ts` 不写 `status` → 后端无法按阶段区分阈值
- 所有阶段共用同一超时值（如全部 90s）→ 未实现阶段级配置
- 阶段内多个 `asyncio.wait_for` 累计超时 ≥ 心跳阈值 × (1 - safety_margin)
- 配置 `subprocessHeartbeat.enabled=false` 但 PR 无说明


---

## step 253：登录成功路径副作用调度规范（LOGIN-SIDE-EFFECT-AUTOMATION-01，meta-rule #89 落地）

> **v4.56.0 新增**。基于 2026-07-22 会话管理自动启动复盘。所有登录成功路径必须 fire-and-forget 调度副作用（会话续期/状态同步），失败安全不阻塞主流程。

### 问题描述

登录成功后，用户需要手动点击"启动会话"按钮才能启动 TokenRenewer 后台续期。多个登录入口（QR 码、账密、浏览器导入、Cookie 注入）各自内联副作用逻辑，部分入口遗漏调用。

### 根因

- 多个登录入口各自维护副作用逻辑，未抽离共享 helper
- 部分入口使用 `await` 阻塞主流程，导致登录响应延迟
- 副作用失败时抛异常，导致登录流程中断

### 规范要求

1. **共享 helper 抽离**：所有登录成功路径的副作用逻辑必须抽离到独立模块（如 `web/services/session_starter.py`），禁止内联在路由处理函数中
2. **统一入口调用**：所有登录成功路径（QR/账密/浏览器导入/Cookie 注入）必须调用共享 helper 的 `trigger_session_start()` 函数
3. **fire-and-forget 调度**：副作用调度使用 `asyncio.ensure_future()` 不阻塞主流程，禁止使用 `await` 等待副作用完成
4. **失败安全**：副作用失败仅记录 `logger.debug`，不抛异常，不影响登录成功响应
5. **前端兜底提示**：检测到有效 Cookie 但会话未启动时（`session.active == false && cookie_layers.identity == true`），前端显示 warning Alert 提供手动操作入口

### 实现模式

```python
# web/services/session_starter.py
def trigger_session_start() -> None:
    """fire-and-forget 调度会话启动，不阻塞主流程"""
    from xianyu_hunter.modules.login_orchestrator import get_orchestrator
    orch = get_orchestrator()
    loop = asyncio.get_event_loop()
    if loop.is_running():
        asyncio.ensure_future(orch.start_session_default())
    else:
        asyncio.run(orch.start_session_default())

# web/routes/unified_login.py（每个登录成功路径调用）
from xianyu_hunter.web.services.session_starter import trigger_session_start
# 登录成功后
_trigger_session_start()  # fire-and-forget
```

### 配置参数

所有参数从 `config/tech-stack.json#hardConstraints.loginSideEffect` 读取：
- `triggerFunction`：触发函数名
- `helperModule`：helper 模块路径
- `dispatchMethod`：调度方式（asyncio.ensure_future）
- `failureLogLevel`：失败日志级别（debug）
- `entryPoints`：需调用 trigger 的入口列表

### 适用场景

- 登录成功后自动启动续期会话
- 导入数据后自动刷新列表
- 配置变更后自动重载缓存

### 不适用场景

- 同步要求的操作（必须等结果）→ 用 `await` 直接调用
- 用户主动触发的操作 → 走用户交互流程
- 高频事件（需防抖）→ 加 debounce/throttle

### 判断信号（review 触发条件）

- `grep "login.*success\|login.*ok" web/routes/` → 检查是否调用 `trigger_session_start()`
- `grep "await.*start_session" web/routes/` → 不应 await（应 ensure_future）
- `grep "trigger_session_start" web/routes/` → 每个登录入口都应调用
- 副作用逻辑内联在路由中而非独立模块 → 视为违规
- 副作用失败抛异常而非 logger.debug → 视为违规


---

### step 275：BATCH-START-FAULT-ISOLATION 批量启动容错隔离规范【强制】🆕v4.69

**背景**：服务重启时 Cookie 失效，`TaskScheduler.start_all()` 内部调用 `self.start(tid)` 时 `_check_resume_allowed` 抛 `ResumeBlockedError`，由于未捕获异常，整个 `start_all` 调用栈终止，外层 `_scheduler_loop` 的 `asyncio.create_task` 静默吞掉异常，导致所有任务（包括 Cookie 有效的任务）都不会运行，后台周期搜索完全不工作，日志中无任何 worker 搜索记录。

**问题**：批量启动/批量初始化操作中，单个项目失败（如凭证失效/资源不可用/前置校验不通过）抛出异常未被捕，导致整个批量操作终止，其他本可正常启动的项目被"连坐"阻塞，且由于外层 `create_task` 静默吞异常，问题无任何日志可查。

**规范**：

1. **批量操作必须容错单个失败【强制】**：批量启动/批量注册/批量初始化方法必须用 `for item in items: try: ... except Exception as e: logger.warning(...); continue` 包裹每个项目，单个失败不阻塞其他项目：
   ```python
   # ✅ 正确：批量启动容错
   def start_all(self) -> None:
       worker_tids = list(self._workers.keys())  # 快照防迭代中修改（配合 step 278）
       started: list[str] = []
       failed: list[tuple[str, str]] = []
       for tid in worker_tids:
           try:
               self.start(tid)
               started.append(tid)
           except Exception as e:
               # 单个任务启动失败不阻塞其他任务
               logger.warning(f"任务 {tid} 启动失败，跳过: {e}")
               failed.append((tid, str(e)))
       if failed:
           logger.warning(f"start_all 完成: 成功 {len(started)} 个, 失败 {len(failed)} 个: {failed}")
       return

   # ❌ 错误：单个失败阻塞全部
   def start_all(self) -> None:
       for tid in self._workers.keys():  # 未快照 + 未容错
           self.start(tid)  # ResumeBlockedError 终止整个循环
   ```

2. **失败结果必须可见化【强制】**：批量操作完成后必须记录成功/失败统计日志（`成功 N 个, 失败 M 个: [...]`），调用方可通过 `is_running(tid)` / `list_tasks()` 查询实际状态，禁止"静默完成"。

3. **禁止 re-raise 阻断调用方【强制】**：批量操作方法**不应** re-raise 单个项目异常，调用方（如 `_scheduler_loop`）的 `asyncio.create_task` 会静默吞掉异常导致整个后台循环死亡。如需上报失败，通过返回值或日志，不通过异常。

4. **与 step 277 配合【强制】**：即使批量操作本身容错，调用方（`_scheduler_loop`）仍必须按 step 277 用 `try/except Exception` 兜底，防止批量操作之外的其他异常（如 workers 列表构造异常）静默退出。

5. **失败项目可重试【推荐】**：失败项目应记录到失败列表，供后续重试机制（如定时重试/用户手动 resume）使用，不永久放弃。

**配置驱动**：参数在 `config.yaml` 的 `batchStartFaultIsolation` 节点管理，包含 `enabled`（开关，默认 true）、`logSuccessCount`（是否记录成功数，默认 true）、`logFailureDetails`（是否记录失败详情，默认 true）、`failureLogLevel`（失败日志级别，默认 `warning`）、`retryableExceptions`（可重试的异常类型列表，如 `["ResumeBlockedError", "TimeoutError"]`）、`nonBlockingExceptions`（不阻塞其他项目的异常类型列表）。

**适用场景**：
- 调度器批量启动任务（`TaskScheduler.start_all`）
- 批量注册组件（Worker/Adapter/Plugin 批量 register）
- 批量初始化资源（多用户 Cookie 批量导入、多个浏览器实例批量启动）
- 批量恢复任务（resume_all / restart_all）
- 启动时批量加载配置/数据

**不适用场景**：
- 单个关键资源启动失败应 fast-fail 的场景（如数据库连接、主浏览器实例）→ 应抛异常阻断启动
- 操作有严格原子性要求（全成功或全失败）→ 用事务
- 单次操作（非批量）→ 直接 try/except
- 同步阻塞操作且无并发隔离需求

**历史教训**：2026-07-30 服务重启时 Cookie 失效，`TaskScheduler.start_all()` 调用 `self.start("t1")` 时 `_check_resume_allowed` 抛 `ResumeBlockedError`，未捕获导致整个 `start_all` 终止，`_scheduler_loop` 的 `asyncio.create_task` 静默吞异常，所有任务（包括 Cookie 有效的 t2/t3）都不运行，后台周期搜索完全不工作。修复后 `start_all` 用 `try/except` 包裹每个任务，单个失败记录 warning 日志不阻塞其他任务，并输出成功/失败统计。

**判断信号（review 触发条件）**：
- `grep "def start_all\|def register_all\|def init_all" <file>` 命中后检查方法体内是否含 `try/except` 包裹每个项目
- `grep "for.*in.*workers\|for.*in.*items\|for.*in.*tasks" <file>` 后跟 `self.start(tid)` / `self.register(item)` 无 try/except → 违规
- 批量操作方法体内含 `raise` 语句 → 违规（除非是 fast-fail 关键资源）
- 批量操作完成后无成功/失败统计日志 → 违规
- 调用方用 `asyncio.create_task(batch_op())` 但 batch_op 内部未容错 → 配合 step 277 审查


---

### step 277：CREATE-TASK-EXCEPTION-VISIBILITY create_task 异常显式捕获规范【强制】🆕v4.69

**背景**：`_scheduler_loop` 被 `asyncio.create_task(_scheduler_loop())` 包装，内部只捕获 `asyncio.CancelledError`，`start_all()` 抛出的其他异常（如 `ResumeBlockedError` / `RuntimeError` / `KeyError`）被 `create_task` 静默吞掉，task 对象不抛异常也不记录日志，导致调度器主循环从未真正启动，所有后台任务都不运行，且日志中无任何错误信息可供排查。

**问题**：`asyncio.create_task(coro())` 创建的后台任务，若协程内部抛出非 `CancelledError` 异常，异常会被 task 对象"持有"但不主动记录日志，直到 task 被 `await` 或显式调用 `task.exception()` 才会暴露。若调用方只是 `create_task` 后不 await（fire-and-forget 模式），异常永远静默，问题无法被发现。

**规范**：

1. **create_task 包装的协程必须用 try/except 兜底【强制】**：所有被 `asyncio.create_task` 包装的协程函数，方法体内必须用 `try/except Exception` 兜底捕获所有非 `CancelledError` 异常，并 `logger.exception()` 记录完整 traceback：
   ```python
   # ✅ 正确：create_task 包装的协程有完整异常分层
   async def _scheduler_loop() -> None:
       try:
           container.scheduler.start_all()
           stop_event = asyncio.Event()
           await stop_event.wait()
       except asyncio.CancelledError:
           logger.info("调度器正在停止...")
           await container.scheduler.stop_all()
           raise  # 传播取消信号（符合 S7497）
       except Exception as e:
           # 关键路径异常必须保 traceback（meta-rule #26）
           logger.exception(f"调度器主循环启动失败: {e}")
           raise  # 重新抛出让 task.exception() 可查

   # ❌ 错误：只捕获 CancelledError，其他异常被 create_task 静默吞掉
   async def _scheduler_loop() -> None:
       try:
           container.scheduler.start_all()
           stop_event = asyncio.Event()
           await stop_event.wait()
       except asyncio.CancelledError:
           logger.info("调度器正在停止...")
           await container.scheduler.stop_all()
       # 其他异常（如 ResumeBlockedError）被 create_task 静默吞掉，无日志
   ```

2. **异常分层捕获【强制】**：必须按 `CancelledError` → `Exception` 顺序分层捕获：
   - `CancelledError` 单独捕获，清理资源后 `raise` 传播取消信号（符合 SonarQube S7497）
   - `Exception` 兜底捕获，`logger.exception()` 记录完整 traceback（meta-rule #26 关键路径保 traceback）
   - **禁止**用 `except BaseException` 统一捕获（会吞掉 `KeyboardInterrupt` / `SystemExit`）

3. **logger.exception 而非 logger.error【强制】**：关键路径异常必须用 `logger.exception()`（自动记录 traceback），**禁止**用 `logger.error(f"...{e}")` 或 `logger.warning(f"...{e}")`（丢失 traceback，无法定位根因）。

4. **task 引用必须保留【强制】**：`_task = asyncio.create_task(coro())` 必须保留 task 引用到实例属性或模块级变量，配合 step 27「死代码与资源生命周期」防止 task 被 GC 回收。配合 step 74「后台任务健康监控」轮询检查 `task.done()` 感知异常退出。

5. **异常后重新抛出【强制】**：`except Exception` 块中 `logger.exception()` 后必须 `raise`，让 task 进入 `done` 状态且 `task.exception()` 可查，配合 step 74 健康监控感知退出。**禁止**吞掉异常后 `await stop_event.wait()` 继续运行（掩盖了启动失败的事实）。

**配置驱动**：参数在 `config.yaml` 的 `createTaskExceptionVisibility` 节点管理，包含 `enabled`（开关，默认 true）、`requireExceptionLayering`（是否强制分层捕获，默认 true）、`forbiddenBroadExcept`（禁止的宽泛异常类型，默认 `["BaseException", "Exception"]` 不允许单独使用而不分层）、`requiredLogLevel`（关键路径异常最低日志级别，默认 `exception`）、`reRaiseRequired`（是否强制重新抛出，默认 true）、`monitoredTaskNames`（必须监控的后台任务名列表，如 `["scheduler_loop", "event_bus", "health_check"]`）。

**适用场景**：
- 所有 `asyncio.create_task(coro())` 包装的后台协程（调度器循环/事件总线/健康检查/Cookie 同步）
- fire-and-forget 模式的后台任务（创建后不 await）
- 长期运行的后台循环（`while True` / `await stop_event.wait()`）
- 应用启动钩子（`_on_startup`）中创建的后台任务

**不适用场景**：
- 被 `await` 的 task（调用方会直接拿到异常）
- 有 `done_callback` 处理异常的 task
- 短时一次性 task（如 `asyncio.create_task(fetch_one())` 后立即 await）
- 测试代码中的 task（pytest-asyncio 框架会捕获异常）

**历史教训**：2026-07-30 服务重启时 `TaskScheduler.start_all()` 抛 `ResumeBlockedError`，`_scheduler_loop` 只捕获 `CancelledError`，异常被 `asyncio.create_task` 静默吞掉，task 对象持有异常但无人查询，调度器主循环从未真正启动，所有后台任务都不运行，日志中无任何错误信息。修复后 `_scheduler_loop` 增加 `except Exception as e: logger.exception(...); raise`，异常可见且 task 进入 done 状态可被健康监控感知。

**判断信号（review 触发条件）**：
- `grep "asyncio.create_task" <file>` 命中后检查被包装的协程函数体内是否含 `try/except Exception`
- `grep "except asyncio.CancelledError" <file>` 后无 `except Exception` 兜底 → 违规
- `grep "logger.error.*f\".*{e}\"\|logger.warning.*f\".*{e}\""` 在关键路径 → 违规（应用 `logger.exception`）
- `grep "asyncio.create_task" <file>` 后 `_task =` 未保留引用 → 配合 step 27 审查
- `except Exception` 块中无 `raise` → 违规（吞掉异常）


---

### step 278：CONTAINER-ITERATION-SNAPSHOT 容器迭代快照规范【强制】🆕v4.69

**背景**：`TaskScheduler.start_all()` 中 `for tid in self._workers.keys():` 迭代字典，但 `self.start(tid)` 内部会修改 `self._workers`（如 `_WorkerHandle` 状态变更触发字典更新），导致 `RuntimeError: dictionary changed size during iteration`，迭代被中断，后续任务无法启动。

**问题**：Python 字典/集合在迭代过程中被修改（增删 key）会触发 `RuntimeError: dictionary changed size during iteration`，迭代被中断，后续元素无法处理。在并发场景或迭代中调用会修改容器的方法时，此问题尤为隐蔽——单元测试用固定数据可能无法复现，生产环境并发修改才触发。

**规范**：

1. **迭代中可能修改的容器必须先快照【强制】**：对字典/集合进行迭代时，若迭代体内可能修改容器（增删 key），必须先用 `list()` / `tuple()` 快照：
   ```python
   # ✅ 正确：迭代前快照
   def start_all(self) -> None:
       worker_tids = list(self._workers.keys())  # 快照防迭代中修改
       for tid in worker_tids:
           self.start(tid)  # start 内部修改 self._workers 不影响迭代

   # ❌ 错误：直接迭代，迭代中修改触发 RuntimeError
   def start_all(self) -> None:
       for tid in self._workers.keys():  # start 内部修改 self._workers → RuntimeError
           self.start(tid)
   ```

2. **快照注释必须说明原因【强制】**：快照代码必须附注释说明"为什么需要快照"（如"防止迭代中修改字典"），便于 reviewer 理解意图，禁止无注释的 `list()` 包裹（会被误认为冗余代码而删除）：
   ```python
   # ✅ 正确：注释说明快照原因
   worker_tids = list(self._workers.keys())  # 防止迭代中 self.start() 修改字典触发 RuntimeError
   ```

3. **触发条件识别【强制】**：以下场景必须快照：
   - `for key in dict.keys()` / `for key in dict` 后跟 `dict[key].method()` 可能修改字典
   - `for item in set` 后跟 `set.add()` / `set.remove()`
   - 迭代中调用 `self.start()` / `self.stop()` / `self.register()` / `self.unregister()` 等可能修改容器的方法
   - 并发场景下迭代共享容器（即使迭代体内不修改，其他协程/线程可能修改）

4. **替代方案：复制容器【可选】**：若迭代体修改幅度大（大量增删），可考虑 `for key in list(dict.items()):` 快照键值对，或 `import copy; snapshot = copy.deepcopy(dict)` 深拷贝。

5. **与 step 63 配合【强制】**：并发场景下迭代共享容器时，即使快照也必须在锁内完成（`with self._lock: snapshot = list(self._workers.keys())`），防止快照过程中其他线程修改容器导致快照不一致。

**配置驱动**：参数在 `config.yaml` 的 `containerIterationSnapshot` 节点管理，包含 `enabled`（开关，默认 true）、`requireCommentExplanation`（是否强制注释说明快照原因，默认 true）、`triggeringMethodPatterns`（触发快照的方法名模式列表，如 `["start", "stop", "register", "unregister", "add", "remove"]`）、`snapshotFunctions`（快照函数列表，默认 `["list", "tuple"]`）、`concurrentLockRequired`（并发场景是否强制锁内快照，默认 true）。

**适用场景**：
- 字典/集合迭代时调用可能修改容器的方法（`start`/`stop`/`register`/`unregister`）
- 并发场景下迭代共享容器（多协程/多线程访问同一字典）
- 批量操作方法（`start_all`/`stop_all`/`register_all`）
- 迭代中根据条件增删容器元素

**不适用场景**：
- 迭代体内不修改容器且无并发访问（只读迭代）
- `for item in list_:` 迭代列表（列表迭代时修改不触发 RuntimeError，但仍不推荐）
- `with` 语句管理的同步迭代（无并发风险）
- 测试代码中的固定数据迭代（无修改风险）

**历史教训**：`TaskScheduler.start_all()` 中 `for tid in self._workers.keys():` 迭代字典，`self.start(tid)` 内部修改 `self._workers`（`_WorkerHandle` 状态变更触发字典更新），触发 `RuntimeError: dictionary changed size during iteration`，迭代被中断，后续任务无法启动。单元测试用 2 个固定 worker 无法复现（数据量小且时序不触发），生产环境多任务并发才暴露。修复后 `worker_tids = list(self._workers.keys())` 快照，并附注释说明原因。

**判断信号（review 触发条件）**：
- `grep "for.*in.*\.keys()\|for.*in.*\.values()\|for.*in.*\.items()" <file>` 后跟 `self.start()` / `self.stop()` / `self.register()` 等可能修改容器的方法 → 违规
- `grep "for.*in.*self\.\w+s\b" <file>`（迭代 `self._workers` / `self._tasks` 等复数命名的容器）后无 `list()` 快照 → 违规
- `list(self._workers.keys())` 无注释说明快照原因 → 违规
- 并发场景下迭代共享容器未在锁内快照 → 配合 step 63 审查

---

