# Scheduler 编码规范
> 本文件归档 xianyu-hunter-dev skill 中与「scheduler」主题相关的编码规范。
> 主索引见 [SKILL.md](../../../SKILL.md) 的"step 索引表"，元规范见 [meta-rules.md](../../../references/meta-rules.md)。

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

### step 56：孤岛模块检测规范【强制】🆕v4.9

56. **孤岛模块检测规范【强制】🆕v4.9**
    - 统计/计数器/采样类模块（如 `FreqDisguise`、`MetricsCollector`、`Sampler`）设计时必须主动考虑"业务模块是否调用"——核心逻辑正确不等于有数据
    - **判断信号**：
      - 计数器/采样器类模块有 `_total_count` / `_history` 等内部状态
      - 但 `grep` 不到任何业务模块（如 collector / buyer / notifier）调用其方法
      - 出现"统计持续为 0 且无变化"或"前端页面永远是空数据"
    - **修复模式**：
      1. **检测阶段**：`grep -rn "<核心方法名>" src/ frontend/src/` 检查调用方数量
      2. **入口封装**：在 Orchestrator / Service 层提供便捷方法封装（如 `LoginOrchestrator.apply_freq_delay()`）
      3. **业务集成**：在所有相关业务模块（采集、详情、购买、登录）的关键路径调用
      4. **前端展示**：确保前端有定时器（如 `setInterval(loadFreqStats, 10s)`）持续拉取统计
    - **关键约束**：
      - 业务模块集成时必须用 `try/except` 包裹（如 `try: get_orchestrator().record_freq_request(...)`）防止辅助功能失败阻塞主流程
      - Orchestrator 单例初始化失败不应影响调用方（fail-safe 设计）
      - 前端必须实现**定时刷新**才能反映业务模块持续调用的累计结果，不能只依赖"页面加载时拉一次"
    - **配置参数**：`front_end_refresh_interval_ms`（前端定时刷新间隔，默认 10000）、`business_call_sites`（必须调用的业务模块路径列表）、`fail_safe`（默认 true，Orchestrator 异常是否静默）在 `config.yaml` 的 `freq_disguise_stats` 节点管理
    - **适用**：所有内部状态需持续累加的模块（频率统计、采样器、计数器、令牌桶、健康评分）
    - **不适用**：纯计算型工具函数（无内部状态）、一次性使用的辅助方法、纯前端 store 状态
    - **历史教训**：`FreqDisguise` 模块设计完整（含 `next_interval` / `should_insert_noise` / `get_stats` 方法），`/api/anticrawl/freq/stats` API 端点也正确返回 stats，但所有业务模块（collector/buyer/notifier）从未调用过任何方法，统计永远为 0。修复后在 LoginOrchestrator 增加 `apply_freq_delay` / `record_freq_request` 便捷方法，collector/buyer 集成调用，前端 AntiCrawl 增加 10 秒定时刷新


---

### step 57：时间敏感场景的延迟/统计分离规范【强制】🆕v4.9

57. **时间敏感场景的延迟/统计分离规范【强制】🆕v4.9**
    - 业务操作存在延迟容忍度差异时（如抢单 vs 采集），核心模块必须提供"延迟+统计"与"仅统计"两种调用入口，业务模块按场景选择，**禁止**一刀切（全 sleep 或全不 sleep）
    - **判断信号**：
      - 业务操作有秒级竞争（抢单/秒杀/实时通知）+ 同一模块的默认行为会引入 5s+ 延迟
      - 业务模块用 `if fast: return` 完全跳过核心模块（导致统计失准）或 `if not fast: sleep(...)` 一刀切延迟
    - **修复模式**：
      ```python
      # 核心模块：提供两种入口
      def next_interval(self, action: ActionType) -> float:
          """生成下一个请求的等待时间（采样+截断+累加统计）"""
          ...
      def record_request(self, action: ActionType) -> None:
          """仅记录请求统计（不实际 sleep）

          用于抢单等时间敏感场景：需要累加统计计数器，但不能引入额外延迟。
          复用 next_interval 的采样+截断+写入 history+累加计数逻辑，避免重复。
          """
          self.next_interval(action)  # 复用消除代码重复

      # Orchestrator 便捷方法：返回值类型明确业务语义
      async def apply_freq_delay(self, action: ActionType) -> float:
          """应用频率伪装延迟（业务模块集成入口）"""
          delay = self._freq_disguiser.next_interval(action)
          await asyncio.sleep(delay)
          return delay  # 返回 delay_sec 便于调用方二次处理

      def record_freq_request(self, action: ActionType) -> None:
          """仅记录请求统计（不 sleep）"""
          self._freq_disguiser.record_request(action)  # 返回 None 表达无副作用

      # 业务模块：按场景选择
      # 抢单场景
      try:
          get_orchestrator().record_freq_request(ActionType.LOGIN)
      except Exception:
          logger.warning("[Buyer] record_freq_request 失败，忽略不影响抢单")
      # 采集场景
      if not fast:
          await get_orchestrator().apply_freq_delay(ActionType.SEARCH)
      else:
          get_orchestrator().record_freq_request(ActionType.SEARCH)
      ```
    - **关键约束**：
      - **复用优先**：`record_request` 必须复用 `next_interval` 的采样+截断+累加逻辑，**禁止**重复实现（消除代码重复）
      - **返回值语义明确**：`apply_freq_delay` 返回 `float`（delay_sec），`record_freq_request` 返回 `None`，**禁止**两个方法都返回被忽略的标志位（如 `should_noise`）导致统计虚高
      - **fast 模式必须保持统计连续**：快速模式仅跳过 sleep，**禁止**完全跳过核心模块
      - **try/except 包裹 Orchestrator 调用**：Orchestrator 初始化失败不应阻塞业务主流程
    - **配置参数**：`time_sensitive_actions`（时间敏感操作类型列表，默认 `[LOGIN]`）、`default_actions`（默认 sleep 操作类型列表，默认 `[SEARCH, DETAIL, BROWSE]`）、`reuse_target`（默认 `next_interval`）在 `config.yaml` 的 `freq_disguise_time_sensitive` 节点管理
    - **适用**：所有业务操作存在延迟容忍度差异的场景（抢单 vs 采集、实时通知 vs 批量推送、即时反馈 vs 后台同步）
    - **不适用**：业务操作延迟容忍度一致的场景（全部秒级或全部分钟级）
    - **历史教训**：抢单（buyer.buy）是秒级竞争，若调用 `apply_freq_delay(ActionType.LOGIN)` 会引入 5-60s 延迟导致抢单失败。原实现 `_search.py` 中 `fast=True` 完全跳过 `apply_freq_delay` 调用导致搜索统计缺失。修复后 buyer 调用 `record_freq_request`（仅统计），_search 在 fast 模式调用 `record_freq_request`（仅统计），保证统计连续性同时不破坏时间敏感场景


---

### step 58：Orchestrator 便捷方法封装规范【强制】🆕v4.9

58. **Orchestrator 便捷方法封装规范【强制】🆕v4.9**
    - 多业务模块依赖同一核心模块时，必须在 Orchestrator 层提供便捷方法封装（命名 `<core_method>` 或 `<core_method>_<variant>`），业务模块通过 Orchestrator 集成而非直接调用核心模块
    - **判断信号**：
      - 多个业务模块（≥2 个）需要调用同一核心模块的同一/相似方法
      - 每个业务模块都自己处理异常/日志/编排逻辑（代码重复）
      - 核心模块的 API 不够"业务友好"（如返回原始统计 dict 而非格式化指标）
    - **修复模式**：
      1. **核心模块保持纯净**：只暴露底层方法（如 `FreqDisguise.next_interval`）
      2. **Orchestrator 便捷方法**：提供"应用 + 副作用"封装（如 `LoginOrchestrator.apply_freq_delay` = `next_interval` + `asyncio.sleep`）
      3. **业务模块通过 Orchestrator 调用**：业务模块只调 Orchestrator 方法，不直接 import 核心模块
      4. **统一异常处理**：Orchestrator 内部处理核心模块异常，转换为业务可理解的错误
    - **关键约束**：
      - Orchestrator 必须是**单例**（如 `get_orchestrator()` 工厂函数），确保全局状态一致
      - 便捷方法命名应**明确业务语义**（如 `apply_freq_delay` 表达"应用延迟"），不是 `do_thing` 之类的泛化命名
      - 核心模块的纯逻辑方法应在 Orchestrator 中**也暴露**（如 `next_interval` 与 `apply_freq_delay` 并存），允许特殊场景直接使用
      - 便捷方法应**支持异步**（`async def`），如果核心逻辑是同步的则内部用 `asyncio.sleep` 包装
    - **配置参数**：`orchestrator_singleton_name`（默认 `get_orchestrator`）、`convenience_method_prefix`（默认 `apply_` / `record_`）、`core_module_aliases`（核心模块在 Orchestrator 中的别名映射）在 `config.yaml` 的 `orchestrator_pattern` 节点管理
    - **适用**：所有多业务模块依赖同一核心模块、需要统一异常/日志/编排处理的场景
    - **不适用**：单一业务模块使用核心模块（直接调用即可）、核心模块本身已有业务友好 API
    - **历史教训**：collector 和 buyer 都需要调用 `FreqDisguise` 模块但各自直接 import，自己处理 sleep 和异常。修复后通过 `LoginOrchestrator.get_orchestrator().apply_freq_delay()` 统一封装，异常/日志/编排逻辑集中管理


---

### step 59：辅助功能异常日志级别规范【强制】🆕v4.9

59. **辅助功能异常日志级别规范【强制】🆕v4.9**
    - 辅助功能调用（如频率伪装统计、装饰器、日志记录）失败时，异常日志级别必须用 `logger.warning`，**禁止**用 `logger.debug`（默认不输出，难以排查）和 `logger.error`（过度严重，污染告警）
    - **判断信号**：
      - 辅助功能调用被 `try/except Exception` 包裹
      - 异常处理中用 `logger.debug(...)` 记录失败原因
      - 异常处理中用 `logger.error(...)` 触发告警（但功能失败不影响主流程）
    - **修复模式**：
      ```python
      # ✅ 正确：logger.warning 记录可恢复异常
      try:
          get_orchestrator().record_freq_request(ActionType.LOGIN)
      except Exception:  # noqa: BLE001
          logger.warning("[Buyer] record_freq_request 失败，忽略不影响抢单")

      # ❌ 错误：logger.debug 默认不输出
      try:
          ...
      except Exception:
          logger.debug("record_freq_request 失败")  # 默认级别看不到！

      # ❌ 错误：logger.error 过度严重
      try:
          ...
      except Exception:
          logger.error("record_freq_request 失败")  # 会触发告警，但功能失败不影响主流程
      ```
    - **关键约束**：
      - `logger.warning` 用于**可恢复异常 / 降级 / 重试**：辅助功能失败、配置项缺失、可选资源不可用
      - `logger.error` 用于**需人工介入的失败**：主流程失败、数据丢失、安全事件
      - `logger.info` 用于**业务关键路径**：触发抢单、采集完成、推送发送
      - `logger.debug` 用于**调试信息**：默认 `INFO` 级别不输出，仅开发环境可见
    - **配置参数**：`auxiliary_log_level`（默认 `warning`）、`recoverable_exceptions`（可恢复异常类型列表）、`critical_exceptions`（需人工介入异常类型列表）在 `config.yaml` 的 `log_level_strategy` 节点管理
    - **适用**：所有辅助功能调用（统计、装饰、日志、监控、采样）的异常处理
    - **不适用**：主流程失败的异常处理（应用 `logger.error`）、调试期主动记录上下文（应用 `logger.debug`）
    - **历史教训**：`buyer.py` 中 `record_freq_request` 失败时用 `logger.debug` 记录，导致默认日志级别下完全看不到失败信息。修复后改为 `logger.warning`，符合项目惯例（参考 `project-rules.md` 日志规约）


---

### step 60：状态机设计规范【强制】🆕v4.10

60. **状态机设计规范【强制】🆕v4.10**
    - 任何含「状态」字段且状态会变化的业务对象（订单/任务/会话/工作流）必须按以下流程设计状态机：
      1. **枚举穷举**：列出所有状态枚举值（如 `pending_pay`/`takeover_pending`/`succeeded`/`failed`/`cancelled`）
      2. **转换白名单**：每个状态变更操作必须用白名单校验起始状态——只允许明确列出的 (起始状态 → 目标状态) 转换，**禁止**用黑名单（禁止某些转换）。白名单更安全：新增状态时不会意外允许非法转换
      3. **终态不可复活**：`failed`/`succeeded`/`cancelled` 等终态禁止再转换到其他状态，状态变更接口必须前置校验 `if current_status in TERMINAL_STATES: raise HTTPException(409, ...)`
      4. **中间态超时清理**：`pending_pay`/`takeover_pending` 等中间态必须有超时清理机制——独立 APScheduler `BackgroundScheduler` 定时扫描（默认 5 分钟，通过 `config.yaml` 的 `state_machine.<entity>.timeout_scan_interval` 节点管理）+ 一次 SQL 批量更新（SELECT + UPDATE 在同一事务），**禁止**逐条更新
      5. **deadline 不可无限重置**：如 `takeover_deadline` 等截止时间字段，同一操作（如 `takeover_order`）禁止反复延长，状态机白名单天然保证（仅 `pending_pay → takeover_pending` 允许，再次接管会被白名单拒绝）
      6. **前后端枚举值统一**：后端 `status: str = "pending_pay"` 与前端 `type Status = 'pending_pay' | ...` 必须字面值完全一致，**禁止**后端 snake_case 前端 camelCase 的映射转换（增加维护成本且易出错）
    - **判断信号**：业务对象有 `status`/`state` 字段 + 字段会通过 API/调度器/事件变更 → 必须按此流程设计
    - **修复模式**：
      ```python
      # ✅ 白名单模式：仅允许 pending_pay → takeover_pending
      ALLOWED_TRANSITIONS: dict[str, set[str]] = {
          "pending_pay": {"takeover_pending", "cancelled"},
          "takeover_pending": {"succeeded", "failed"},
          # 终态 succeeded/failed/cancelled 不在 key 中 → 任何转换都被拒绝
      }
      def transition(current: str, target: str) -> None:
          if current not in ALLOWED_TRANSITIONS or target not in ALLOWED_TRANSITIONS[current]:
              raise HTTPException(409, detail=f"非法状态转换: {current} → {target}")
      ```
    - **配置参数**：`state_machine.<entity>.timeout_scan_interval`（默认 300s）、`state_machine.<entity>.timeout_threshold`（默认 1800s）、`state_machine.<entity>.terminal_states`（终态列表）、`state_machine.<entity>.allowed_transitions`（白名单映射）在 `config.yaml` 的 `state_machine` 节点管理
    - **适用**：订单/任务/会话/工作流等有状态生命周期的业务对象
    - **不适用**：纯 CRUD 实体（如配置项，无状态流转）；单状态字段（如 `is_active: bool` 用简单 if 判断即可）；一次性事件（如日志记录）
    - **历史教训**：`takeover_order` 接口未校验起始状态，导致 `failed` 终态订单可被接管（终态复活）；`takeover_pending` 超时无清理机制，订单永久卡死；同一订单可被反复 `takeover_order` 延长 deadline（无限重置）。修复后改为白名单 + 独立调度器批量清理 + 终态前置校验


---

### step 62：双链路一致性规范【强制】🆕v4.10

62. **双链路一致性规范【强制】🆕v4.10**
    - 同一业务目标有 ≥2 条执行链路时（如 Worker 调度链路 + Live 实时链路都到达「下单」），共用前置条件必须提取为独立函数，两条链路调用同一函数，**禁止**各自实现
    - **关键约束**：
      1. **共用前置条件提取**：价格过滤/分数校验/库存检查等前置条件提取为独立函数（如 `_build_price_strategy(task) -> PriceStrategy`）
      2. **两链路调用同一函数**：Worker 链路和 Live 链路必须调用同一函数，**禁止**各自实现相似逻辑
      3. **过滤范围明确**：前置条件过滤仅阻止「执行动作」（如抢单），不阻止「评估写库」（评估结果仍写入 DB 供后续分析）
      4. **grep 验证**：修改后必须 `grep` 验证两条链路确实调用同一函数，禁止遗漏
      5. **测试覆盖**：必须新增测试覆盖两条链路的前置条件一致性
    - **判断信号**：同一业务目标（如「下单」「采集」「通知」）有 ≥2 条执行链路 → 必须按此流程设计
    - **修复模式**：
      ```python
      # ✅ 提取共用前置条件为独立函数
      def _build_price_strategy(task: Task) -> PriceStrategy:
          """构建价格策略，Worker 和 Live 链路共用"""
          return PriceStrategy(
              max_price=task.price_config.get("max_price") or 0,
              min_price=task.price_config.get("min_price") or 0,
          )

      # Worker 链路
      class TaskWorker:
          async def run_once(self):
              strategy = _build_price_strategy(self.task)
              if not strategy.is_acceptable(item): return  # 共用过滤

      # Live 链路
      async def _trigger_live_auto_buy(item, task):
          strategy = _build_price_strategy(task)
          if not strategy.is_acceptable(item): return  # 共用过滤
      ```
    - **配置参数**：`dual_link.target_entities`（业务目标列表，如 `["buy", "collect", "notify"]`）、`dual_link.shared_predicate_patterns`（共用前置条件函数命名模式，如 `_build_*_strategy`）、`dual_link.verify_callers`（是否启用 grep 验证，默认 `true`）在 `config.yaml` 的 `dual_link_consistency` 节点管理
    - **适用**：同一业务目标有多个触发入口（如 Worker 调度 + Live 实时 + API 手动 + CLI 命令）
    - **不适用**：单一入口的业务（如只有 API 触发）；链路间业务逻辑本就不同（如 Worker 是异步批量，Live 是同步单条）——此时应抽取「共同部分」为函数，「差异部分」各自处理
    - **历史教训**：Worker 链路调用 `PriceStrategy.is_acceptable()` 做价格过滤，Live 链路只看分数达标不做价格过滤，导致两条链路行为不一致——Worker 链路过滤掉的高价商品在 Live 链路被下单。修复后提取 `_build_live_price_strategy` 共用函数，两链路调用同一函数


---

### step 73：调度器状态与 DB 同步【强制】🆕v4.12

73. **调度器状态与 DB 同步【强制】🆕v4.12**
    - 调度器内存状态变更（pause/resume/stop/error_pause）必须同步到 DB（`update_task_status`），**禁止**只在内存变更导致 API 返回的状态与实际运行状态不一致
    - **判断信号**：调度器代码含 `pause_event.clear()` / `pause_event.set()` / `self._active = False` → 必须同步调用 `self._repo.update_task_status(task_id, "paused"/"running"/"stopped")`
    - **修复模式**：
      ```python
      # ✅ 状态变更后同步 DB
      async def _auto_pause_on_errors(self, task_id: str, h: _WorkerHandle) -> None:
          h.pause_event.clear()
          h.consecutive_errors = 0
          # 同步 DB 状态，确保 API 返回与实际一致
          try:
              await self._repo.update_task_status(task_id, "paused")
          except Exception as e:
              logger.warning("[Task {}] DB 状态同步失败：{}", task_id, e)
      ```
    - **配置参数**：`scheduler_db_sync.required_transitions`（必须同步 DB 的状态转换列表，如 `["running→paused", "paused→running", "running→stopped"]`）、`scheduler_db_sync.sync_failure_strategy`（默认 `warn`，可选 `raise`）、`scheduler_db_sync.status_field`（默认 `status`）在 `config.yaml` 的 `scheduler_db_sync` 节点管理
    - **适用**：所有调度器状态变更（auto_pause / manual_pause / resume / stop / unregister）；任务状态机转换
    - **不适用**：纯计算状态（如 consecutive_errors 计数器）；临时状态（如 pause_event 内部信号）；fire-and-forget 任务
    - **历史教训**：调度器连续失败触发 `pause_event.clear()` 自动暂停，但未调用 `update_task_status("paused")`，API 仍返回 `running`，前端显示"运行中"但任务实际已停止


---

### step 101：关键调度器启动状态可见性规范【强制】🆕v4.19

**背景**：用户启动 web 服务时未加 `--with-scheduler` 参数，`BatchRefreshScheduler`（批量采集调度器，每 30 分钟回查 `is_sold=0` 商品状态）永远不运行。日志仅输出一条 info"批量采集调度器未启动（collector 未初始化，需 XH_WITH_SCHEDULER=1）"，用户无感知。导致商品 1058031608014 实际已售但数据库 `is_sold=0` 长期不刷新。

**规范**：

1. **关键后台调度器必须有启动状态可见性**
   - 关键调度器（影响业务正确性的，如批量采集/状态回查/数据同步/定时清理）启动状态必须在启动日志中明确告知用户
   - 启动时输出 INFO 级别日志：`调度器 {name} 已启动（间隔 {interval} 分钟）`
   - 未启动时输出 WARNING 级别日志 + 醒目提示：`调度器 {name} 未启动，相关功能将不生效。如需启用：{startup_command}`

2. **--help 输出必须说明启动参数的影响范围**
   - 每个启动参数（如 `--with-scheduler`）必须在 `--help` 输出中说明启用什么/禁用什么
   - 影响范围说明应包含：调度的任务名称、间隔、依赖该调度器的下游功能

3. **调度器启动状态应可通过 API 查询**
   - `/api/about` 或 `/api/health` 端点必须返回关键调度器启动状态
   - 返回结构含 `schedulers: [{name, enabled, interval_minutes, last_run_at}]`
   - 前端"关于"页面可展示调度器状态，让用户直观感知

4. **调度器启动参数列表集中管理**
   - 启动参数与环境变量的映射（如 `--with-scheduler` ↔ `XH_WITH_SCHEDULER`）在 `config.yaml` 的 `scheduler_startup_visibility.startup_param_env_mapping` 节点管理
   - 关键调度器名单在 `critical_schedulers` 节点管理，便于扩展
   - **禁止**在代码中硬编码调度器启动参数列表

5. **未启动调度器的影响范围必须在文档中说明**
   - 每个关键调度器必须在项目文档中说明"未启动时影响哪些功能"
   - 文档位置：`docs/02-后台调度器.md` 或 `README.md` 的"调度器"章节

**判断逻辑**：

- `grep "asyncio.create_task\|scheduler.start" src/xianyu_hunter/` 发现调度器启动但无启动日志 → 视为违规
- 启动日志仅用 `logger.info("xxx 已启动")` 但未告知用户如何禁用/启用 → 视为可疑
- 调度器未启动时仅静默跳过（无 WARNING）→ 视为违规
- `/api/about` 端点未返回调度器状态 → 视为可疑
- `--help` 输出中启动参数无影响范围说明 → 视为可疑

**反例**：

```python
# ❌ 错误：调度器未启动时仅静默跳过，用户无感知
if not os.environ.get("XH_WITH_SCHEDULER"):
    logger.info("批量采集调度器未启动")  # info 级别，用户看不到
    return  # 静默跳过，用户以为系统正常
```

**正例**：

```python
# ✅ 正确：WARNING 级别 + 醒目提示 + 启动命令
if not os.environ.get("XH_WITH_SCHEDULER"):
    logger.warning(
        "⚠️ 批量采集调度器未启动，已售商品状态将不刷新。\n"
        "  如需启用：python -m xianyu_hunter web --with-scheduler\n"
        "  影响范围：商品 is_sold 状态回查、已售商品检测"
    )
    return

# 启动时输出 INFO + 间隔
logger.info("✅ 批量采集调度器已启动（间隔 30 分钟，每批 100 条）")

# /api/about 端点返回调度器状态
@api_router.get("/about")
async def about():
    return {
        "version": _safe_app_version(),
        "schedulers": [
            {
                "name": "BatchRefreshScheduler",
                "enabled": scheduler.is_running,
                "interval_minutes": 30,
                "last_run_at": scheduler.last_run_at,
            }
        ],
    }
```

**配置参数**：`scheduler_startup_visibility` 节点（enabled / critical_schedulers / require_startup_log / require_warning_when_disabled / require_help_doc / require_about_endpoint / startup_param_env_mapping）

**适用场景**：
- 关键后台调度器（批量采集/状态回查/数据同步/定时清理）
- 通过启动参数或环境变量控制的功能开关
- 影响业务正确性的后台任务

**不适用场景**：
- 调试用的可选功能（如 `--debug` 模式）
- 默认启动且无法关闭的核心功能
- 一次性任务（如启动时迁移）

**历史教训**：用户启动 web 服务时未加 `--with-scheduler` 参数，`BatchRefreshScheduler`（每 30 分钟回查 `is_sold=0` 商品状态）永远不运行。日志仅输出一条 info，用户无感知。导致商品 1058031608014 实际已售但数据库 `is_sold=0` 长期不刷新，用户看到已售商品仍被推荐。修复后调度器未启动时输出 WARNING + 醒目提示 + 启动命令 + 影响范围。


---

### step 107：启动钩子完整性检查规范【强制】🆕v4.20

**背景**：反爬会话管理（LoginOrchestrator + TokenRenewer）依赖 container.browser 进行 Cookie 续期，但 startup.py 的 `_on_startup` 只启动了主调度器/Cookie 同步/批量采集/知识库四个调度器，缺失反爬会话管理的启动钩子。导致服务重启后即使 Cookie 仍有效，TokenRenewer 后台续期也不会自动启动，用户必须手动点击「启动会话」按钮。

**问题**：新增依赖 container.browser/collector 的组件时，未同步在 startup.py 添加对应启动钩子，导致功能不可用。

**规范**：

1. 所有依赖 `container.browser` 或 `container.collector` 的组件，必须在 `startup.py` 的 `_on_startup` 中有对应的 `start_xxx()` 启动钩子
2. 启动钩子必须用 `if _should_start_scheduler():` 包裹，避免无浏览器时错误启动
3. 启动钩子必须放在依赖的调度器之后（如反爬会话管理放在批量采集调度器之后，确保浏览器已就绪）
4. 启动失败必须 try/except 兜底，仅记录 warning 不阻断主服务启动
5. 验证方法：`grep -rn "container.browser\|container.collector" src/xianyu_hunter/` 找所有依赖点，逐个检查 startup.py 是否有对应 start_xxx 调用

**配置驱动**：参数在 `config.yaml` 的 `startup_hook_completeness` 节点管理，包含 `required_components`（必须启动的组件列表）、`dependency_check_fields`（依赖检查字段）、`startup_order`（启动顺序）。

**适用场景**：含 BackgroundScheduler/asyncio.Task 后台任务的项目，特别是依赖浏览器/外部资源的组件。

**不适用场景**：纯 Web 项目无后台任务；单进程无外部依赖项目；纯前端组件。


---

### step 108：任务历史持久化三层状态保护规范【强制】🆕v4.20

**背景**：批量采集任务执行历史功能中，`_run_batch_async` 在开始时插入 running 状态记录，结束时更新为终态。但如果 `future.result(timeout=_BATCH_TIMEOUT)` 超时或协程异常退出，历史记录会残留 running 状态。

**问题**：长时间运行任务的执行历史记录在异常退出时残留中间态（running），导致历史记录与实际状态不一致。

**规范**：

1. 任何写入 running 状态的代码路径，都必须有对应的 finalize 调用更新为终态（completed/failed/cancelled）
2. finalize 必须覆盖三条路径：
   - 正常结束路径（在 `_run_batch_async` 的 finally 块中调用）
   - future.result 超时路径（在 `_run_batch_job` 的 except 块中调用 `_finalize_history_on_exception`）
   - 协程异常路径（在 `_run_batch_async` 的 except 块中调用）
3. 错误消息累积必须设上限（FIFO 切片丢弃最旧），避免 JSON 字段无限膨胀
4. 状态语义必须区分：circuit_broken（连续失败熔断）→ failed，_stop_flag（用户主动停止）→ cancelled，正常完成 → completed
5. 业务自增 task_id 不能依赖内存初始化（进程重启会重置），必须从 DB `SELECT MAX(task_id)` 初始化

**配置驱动**：参数在 `config.yaml` 的 `task_history_protection` 节点管理，包含 `required_states`（必须覆盖的终态列表）、`exception_fallback_required`（是否需要异常兜底）、`max_error_messages`（错误消息上限默认 50）、`counter_init_query`（计数器初始化查询语句）。

**适用场景**：长时间运行任务的执行历史记录（批量采集/数据同步/批处理/定时任务）。

**不适用场景**：短时间 HTTP 请求；不需要历史记录的任务；一次性脚本任务。


---

### step 109：业务自增计数器 DB MAX 初始化规范【强制】🆕v4.20

**背景**：批量采集任务的 task_id 是业务字段（progress 表/历史表/日志均引用），调度器内存中维护自增计数器。如果进程重启，内存计数器从 0 开始，会与历史记录的 task_id 冲突。

**问题**：业务自增 ID 依赖内存初始化，进程重启后重置，导致新记录的 ID 与历史记录冲突。

**规范**：

1. 业务自增 ID（task_id/batch_id/run_id 等）不能依赖内存初始化（进程重启会重置）
2. 调度器 `__init__` 时必须从 DB `SELECT MAX(id)` 初始化计数器
3. 查询失败时回退到 0 + `logger.warning`，不阻断启动
4. `trigger_now()` 调用时 `+= 1` 后立即返回给前端，不等待 DB 写入
5. 为什么不用 DB 自增主键：业务自增 ID 需在调度器内存中维护以便 trigger_now 立即返回给前端，DB 自增主键要等 INSERT 后才知道值

**配置驱动**：参数在 `config.yaml` 的 `counter_db_max_init` 节点管理，包含 `counter_fields`（需要 DB MAX 初始化的字段列表）、`init_query_template`（初始化查询模板）、`fallback_value`（回退值默认 0）、`warning_on_failure`（失败时是否记录 warning）。

**适用场景**：业务自增 ID（task_id/batch_id/run_id）跨进程重启不能重置的场景。

**不适用场景**：DB 自增主键（autoincrement）；UUID/GUID；临时计数器（无需跨进程持久化）。


---

### step 110：APScheduler interval 触发器首次执行控制规范【强制】🆕v4.20

**背景**：APScheduler 的 interval 触发器默认首次执行时间是 `start_time + interval`（即启动后还要等 30 分钟才会第一次触发），用户感知不到调度器在工作，误以为功能不生效。

**问题**：interval 触发器默认首次执行延迟一个完整间隔，用户感知不到调度器已启动。

**规范**：

1. 使用 APScheduler interval 触发器时，必须明确首次执行时间
2. 需要启动后快速反馈的场景，必须设置 `next_run_time` 参数
3. `next_run_time` 不建议设为 `datetime.now()`（立即执行），应留 5-10 秒延迟给初始化依赖（浏览器/collector/DB）就绪
4. 日志必须输出间隔 + 首次执行时间：`logger.info("调度器已启动，间隔 %d 分钟，首次执行于 %s", interval, next_run)`
5. 为什么不设为立即执行：给浏览器/collector 初始化留时间，避免首次采集因浏览器未就绪而连续失败触发熔断

**配置驱动**：参数在 `config.yaml` 的 `apscheduler_interval_first_run` 节点管理，包含 `default_next_run_delay_seconds`（默认延迟秒数 10）、`needs_immediate_execution`（是否需要启动后立即执行）、`log_format`（日志格式模板）。

**适用场景**：APScheduler interval 触发器且需要启动后快速反馈的场景（批量采集/数据同步/定时巡检）。

**不适用场景**：cron 触发器（有明确时间点）；首次执行依赖外部状态需手动触发的场景；纯 Web 请求无定时任务。


---

### step 111：CLI 默认参数友好性规范【强制】🆕v4.20

**背景**：`xianyu web` 命令默认 `with_scheduler=False`，用户必须显式加 `--with-scheduler` 才能启动调度器。但实时搜索/批量采集/自动抢单等核心功能都依赖浏览器实例，不启动调度器等于核心功能不可用。

**问题**：CLI 默认参数未启用核心功能，用户不知道需要加参数，导致功能不生效。

**规范**：

1. CLI 命令的核心功能参数应默认启用（如 `--with-scheduler` 默认 True）
2. 必须提供关闭选项（如 `--no-with-scheduler`），让用户可以选择降级模式
3. 启动时必须输出当前模式：`typer.echo("→ 模式: Web + 调度器（默认）")` 或 `typer.echo("→ 模式: Web only（纯 Web）")`
4. `--help` 必须说明参数影响范围：「默认启用调度器与浏览器实例，使用 --no-with-scheduler 关闭」
5. 启动脚本（.bat/.sh）可省略显式参数（因已是默认），但建议保留作为显式标记

**配置驱动**：参数在 `config.yaml` 的 `cli_default_friendly` 节点管理，包含 `default_enabled_params`（默认启用的参数列表）、`disable_flag_pattern`（关闭参数命名模式 `--no-xxx`）、`mode_echo_required`（是否必须输出当前模式）。

**适用场景**：CLI 命令有核心功能开关参数，且大部分场景需要启用。

**不适用场景**：可选功能参数（如调试模式/日志级别）；有副作用的参数（如重置数据库）；开发专用参数。


---

### step 194：SCHEDULER-RUNTIME-TOGGLE-SYMMETRY 调度器运行时开关对称性【强制，meta-rule #48 落地】🆕v4.36

**背景**：`BatchRefreshScheduler.update_config(enabled=False)` 只设 `self._enabled = False` 标志位，未调用 `scheduler.remove_job()`，APScheduler 已注册的 job 仍按 trigger 触发，导致禁用后仍持续执行批量采集。同期 `CookieSyncScheduler` 完全没有 `_enabled` 字段和 `update_config` 方法，配置开关形同虚设。对应元规范 meta-rules #48，与 B-REVIEW-178（backend 调度器开关对称性审查）+ F-REVIEW-136（frontend 调度器状态同步审查）对应。

**问题**：调度器开关操作不对称——"禁用只设标志位不移除 job" 或 "启用只设标志位不恢复 job"，导致配置开关无效或时序竞态下 job 仍触发。

**规范**：

1. **禁用立即生效【强制】**：`update_config(enabled=False)` 必须在同一个方法内完成"设标志位 + remove_job"两步操作，禁止只设标志位依赖 job 函数入口检查兜底：
   ```python
   # ✅ 正确：禁用即移除 job
   def update_config(self, *, enabled: bool | None = None) -> None:
       if enabled is not None:
           self._enabled = enabled
           if not enabled:
               # 立即移除已注册 job，不依赖入口检查兜底
               try:
                   self._scheduler.remove_job(self._job_id)
               except Exception as e:
                   logger.warning("移除 job 失败: {}", e)
           else:
               # 启用即恢复 job
               self._scheduler.add_job(self._run_job, trigger=..., id=self._job_id)
   
   # ❌ 错误：只设标志位，job 仍按 trigger 触发
   # def update_config(self, *, enabled: bool | None = None):
   #     self._enabled = enabled  # remove_job 缺失
   ```

2. **入口 double-check【强制】**：job 函数入口必须 `if not self._enabled: return`，作为 remove_job 失败/时序竞态的第二道防线：
   ```python
   # ✅ 正确：入口 double-check
   def _run_job(self):
       if not self._enabled:
           logger.warning("调度器已禁用但 job 仍触发，检查 update_config 实现")
           return
       # ... 业务逻辑
   ```

3. **启用恢复 job【强制】**：`update_config(enabled=True)` 必须调用 `add_job(...)` 或 `resume_job(job_id)` 重新注册/恢复 job，禁止只设标志位期望"下次 job 触发时自动恢复"。

4. **开关状态可查询【强制】**：调度器必须提供 `is_enabled() -> bool` 方法供 API 层查询当前状态，禁止 API 层直接访问 `_enabled` 私有字段。

5. **配置驱动【强制】**：`enabled` 字段必须从 `config.yaml` 的对应节点读取，运行时 `update_config` 修改后必须同步写回 config 持久化。

**配置驱动**：参数在 `config.yaml` 的 `scheduler_runtime_toggle` 节点管理，包含 `require_remove_job`（禁用时是否强制 remove_job，默认 true）、`require_entry_check`（job 函数入口是否强制 double-check，默认 true）、`require_is_enabled_method`（是否强制提供 is_enabled() 方法，默认 true）、`require_config_persist`（是否强制写回 config，默认 true）。

**适用场景**：所有 APScheduler 调度器（BackgroundScheduler/AsyncIOScheduler）；具有 `enabled` 配置开关的后台任务；运行时可动态启停的调度器（如批量采集/Cookie 同步/状态回查）。

**不适用场景**：一次性任务（无 `enabled` 字段）；启动时确定整个生命周期不启停的调度器（如系统监控）；外部托管调度器（如 celery beat，由外部进程管理）。

**历史教训**：`BatchRefreshScheduler` 禁用后批量采集仍持续执行，用户反馈「关闭开关后任务还在跑」。排查发现 `update_config` 只设标志位未 remove_job，APScheduler 已注册的 job 仍按 trigger 触发。修复后加 `remove_job` + 入口 double-check + `is_enabled()` 方法。

**判断信号（review 触发条件）**：
- `grep "def update_config" <scheduler_file>` 缺 `remove_job` 或缺 `add_job`/`resume_job` → 开关不对称
- `grep "def _run_.*_job" <scheduler_file>` 缺 `if not self._enabled` → 缺入口 double-check
- `grep "scheduler\._enabled\|scheduler\.enabled" routes/` → API 层直接访问私有字段


---

### step 195：CRON-MIN-INTERVAL-CHECK 用户输入时间表达式校验【强制，meta-rule #51 落地】🆕v4.36 experimental

**背景**：task 的 `schedule_cron` 字段接受任意 cron 表达式，用户配置 `* * * * *`（每分钟执行）导致批量采集每分钟触发一次，远低于反爬最小延迟（10 秒），触发闲鱼反爬封禁。对应元规范 meta-rules #51（experimental），与 B-REVIEW-181（backend cron 表达式最小间隔审查）+ F-REVIEW-139（frontend cron 表达式校验审查）对应。

**问题**：用户输入的 cron 表达式无最小间隔校验，可能配置每秒/每分钟执行的滥用表达式触发反爬封禁。

**规范**：

1. **cron 表达式解析【强制】**：使用 `apscheduler.triggers.cron.CronTrigger.from_crontab(cron_expr)` 解析表达式，解析失败返回结构化错误不抛异常：
   ```python
   # ✅ 正确：解析失败返回结构化 dict
   def validate_cron(cron_expr: str) -> dict:
       try:
           trigger = CronTrigger.from_crontab(cron_expr)
       except Exception as e:
           return {"valid": False, "reason": f"cron 表达式语法错误: {e}"}
       min_interval = self._get_min_cron_interval_seconds(trigger)
       threshold = self._get_min_interval_threshold()
       if min_interval < threshold:
           return {"valid": False, "reason": f"cron 最小间隔 {min_interval}s < 反爬最小延迟 {threshold}s"}
       return {"valid": True}
   
   # ❌ 错误：抛异常
   # if min_interval < threshold:
   #     raise ValueError("cron 间隔过小")
   ```

2. **最小间隔计算【强制】**：解析后计算连续两次触发的时间差最小值（`_get_min_cron_interval_seconds(trigger) -> float`），通过枚举 24 小时内所有触发点取最小差值。

3. **阈值校验【强制】**：最小间隔 < `get_config().antidetect.min_delay_ms / 1000` 视为滥用，返回结构化错误。

4. **配置读取容错【强制】**：`_get_min_interval_threshold` 内 `try/except` 包裹 `get_config()` 调用，配置缺失时回退默认值（参考 step 188 配置化阈值兜底范式）：
   ```python
   # ✅ 正确：配置读取容错
   @staticmethod
   def _get_min_interval_threshold() -> float:
       try:
           from xianyu_hunter.infra.yaml_config import get_config
           return get_config().antidetect.min_delay_ms / 1000.0
       except Exception:
           return 10.0  # 回退默认值
   ```

5. **配置驱动【强制】**：最小间隔阈值、回退默认值、校验开关从 `config.yaml#cron_min_interval_check` 节点管理。

**配置驱动**：参数在 `config.yaml` 的 `cron_min_interval_check` 节点管理，包含 `enabled`（校验开关，默认 true）、`threshold_source`（阈值来源 `antidetect.min_delay_ms`，默认）、`fallback_threshold_seconds`（回退阈值，默认 10）、`scan_window_hours`（最小间隔扫描窗口，默认 24）。

**适用场景**：用户输入的 cron 表达式（task 的 `schedule_cron` 字段）；APScheduler CronTrigger 调度器；可能触发反爬的定时任务（采集/同步/轮询）。

**不适用场景**：interval 触发器（已通过 `seconds=` 参数控制间隔）；date 触发器（一次性执行无间隔概念）；内部系统调度（非用户输入，已通过 code review 保证合理）；测试用 cron 表达式（测试环境无反爬风险）。

**历史教训**：用户配置 `* * * * *`（每分钟执行）触发闲鱼反爬封禁，账号被限流 24 小时。修复后加 `_get_min_cron_interval_seconds` 校验，小于阈值（10 秒）时返回结构化错误不创建 job。

**判断信号（review 触发条件）**：
- `grep "CronTrigger\.from_crontab" <file>` 但无 `_get_min_cron_interval_seconds` 调用 → 缺最小间隔校验
- `grep "schedule_cron" <file>` 但无 `validate_cron` 调用 → 用户输入未校验
- `grep "def _get_min_cron_interval_seconds" <file>` 无 `try.*except` → 配置读取无容错


---

### step 274：事件驱动基础设施启动解耦规范【强制，meta-rule #111 落地】🆕v4.68 experimental

**背景**：用户反馈评分 80 以上商品未触发钉钉通知。配置全正常（`pass_score: 70`、`dingtalk: true`、`quiet_hours.enabled: false`、`subscribed_events` 含 `EVAL_PASSED`），但 `EventBus.run_forever()` 消费者循环被嵌套在 `start_scheduler_in_background` 的 `_scheduler_loop` 内部，三重前置条件任一不满足即 return：① `XH_WITH_SCHEDULER=1` ② `container.collector is not None` ③ 启动时有 RUNNING 任务。第③条最隐蔽——启动时无 RUNNING 任务则 EventBus 永不启动，且 `api_tasks.py` 的 `control_task`（resume/restart）完全不补启动 EventBus。结果 `worker.publish_nowait(EVAL_PASSED)` 事件入队但无消费者，钉钉永不触发，且无任何报错日志。对应元规范 meta-rule #111，与 B-REVIEW-331（backend 事件驱动启动解耦审查）+ 模式 AF（事件链路启动解联回归测试）对应。

**问题**：事件总线/消息队列的消费者循环启动条件与业务任务存在性耦合，导致无业务任务时基础设施静默不启动，后续运行时新增任务时事件入队但无消费者，订阅者永远收不到事件，且无报错日志。

**规范**：

1. **消费者循环独立启动【强制】**：事件总线/消息队列的消费者循环必须从业务调度器启动函数中抽离，作为独立启动函数（如 `start_event_bus_in_background`），启动条件独立于"是否有业务任务在运行"：
   ```python
   # ✅ 正确：独立启动函数，无条件启动
   async def start_event_bus_in_background(container: Any) -> None:
       global _event_bus_task
       # 幂等防护：已在运行则跳过
       if _event_bus_task is not None and not _event_bus_task.done():
           logger.info("EventBus 已在运行，跳过重复启动")
           return
       async def _bus_loop():
           try:
               logger.info("EventBus 主循环启动")  # 必须有启动日志
               await container.event_bus.run_forever()
           except asyncio.CancelledError:
               raise
           except Exception as e:  # 异常不能静默退出
               logger.exception(f"EventBus 主循环异常退出: {e}")
       _event_bus_task = asyncio.create_task(_bus_loop())

   # ❌ 错误：消费者循环嵌套在业务调度器内部，受业务条件阻断
   # async def start_scheduler_in_background(container):
   #     if not container.collector: return  # ← 阻断了 EventBus
   #     if not workers: return                # ← 阻断了 EventBus
   #     async def _scheduler_loop():
   #         bus_task = asyncio.create_task(container.event_bus.run_forever())  # 嵌套启动
   ```

2. **启动顺序：基础设施先于业务调度器【强制】**：`_on_startup` 中必须先调用 `start_event_bus_in_background`，再调用 `start_scheduler_in_background`，确保业务 `publish` 事件时消费者已在等待：
   ```python
   # ✅ 正确：先 EventBus 后调度器
   if _should_start_scheduler():
       await start_event_bus_in_background(container)  # 先启动消费者
       await start_scheduler_in_background(container)  # 后启动业务
   ```

3. **停止顺序：基础设施后于业务调度器【强制】**：`_on_shutdown` 中必须先停止业务调度器（`_scheduler_task`），再停止 EventBus（`_event_bus_task`），确保业务停止时 `publish` 的终态事件（如 TASK_STOPPED）能被消费：
   ```python
   # ✅ 正确：先停调度器后停 EventBus
   if _scheduler_task and not _scheduler_task.done():
       _scheduler_task.cancel()
       with suppress(asyncio.CancelledError): await _scheduler_task
   # EventBus 在调度器之后停止
   if _event_bus_task and not _event_bus_task.done():
       container.event_bus.stop()
       _event_bus_task.cancel()
       with suppress(asyncio.CancelledError): await _event_bus_task
   ```

4. **幂等防护【强制】**：启动函数必须检查 `_event_bus_task is not None and not _event_bus_task.done()`，已在运行则跳过，禁止重复启动产生多个消费者竞争同一队列。

5. **异常隔离【强制】**：消费者循环异常不能静默退出，除 `CancelledError` 外的异常必须 `logger.exception` 记录，避免任务静默死亡导致后续事件全部丢失。

6. **运行时新增入口补启动【强制】**：API/CLI 运行时新增业务任务（如 `control_task` 的 resume/restart）时，必须确认基础设施已就绪——若 `_event_bus_task` 未运行则调用 `start_event_bus_in_background` 自动启动，不能假设"启动时一次性决定"：
   ```python
   # ✅ 正确：resume 时补启动 EventBus
   if _event_bus_task is None or _event_bus_task.done():
       await start_event_bus_in_background(container)
   await container.scheduler.start(task_id)
   ```

**配置驱动**：参数在 `config.yaml` 的 `eventBusStartupDecoupling` 节点管理，包含 `enabled`（开关，默认 true）、`infrastructureTypes`（适用基础设施列表，如 `["event_bus", "message_queue"]`）、`startupOrder`（启动顺序，默认 `before_business_scheduler`）、`shutdownOrder`（停止顺序，默认 `after_business_scheduler`）、`requireIdempotentGuard`（是否强制幂等防护，默认 true）、`requireExceptionIsolation`（是否强制异常隔离，默认 true）、`requireStartupLog`（是否强制启动日志，默认 true）。

**适用场景**：事件总线（EventBus/MessageQueue）的消费者循环；发布-订阅模式的基础设施；后台调度器依赖的事件分发机制；Worker/Agent publish 事件到队列、由独立消费者分发给 Notifier 的模式。

**不适用场景**：同步调用（无 publish-subscribe）；一次性任务（启动即完成）；进程内函数直接 invoke（无队列中间层）；前端组件间通信（React Context/Zustand，无独立消费者循环）。

**历史教训**：2026-07-26 用户反馈评分 80 以上商品未触发钉钉通知。配置全正常，根因是 `EventBus.run_forever()` 嵌套在 `_scheduler_loop` 内部，启动时无 RUNNING 任务则 EventBus 永不启动，`api_tasks.py` 的 resume/restart 也不补启动。修复后抽离 `start_event_bus_in_background()` 独立启动，先于调度器启动、后于调度器停止，含幂等防护与异常隔离。

**判断信号（review 触发条件）**：
- `grep "run_forever\|consume_loop\|_dispatch" src/` 找到消费者循环 → 检查其启动是否嵌套在业务调度器函数内部
- `grep "publish_nowait\|publish(" src/` 找到 publish 调用 → 反向追踪消费者是否在同一启动链路中
- `grep "if not workers\|if not.*RUNNING" src/xianyu_hunter/web/startup.py` → 若该 return 阻断了基础设施启动则违反规则1
- `grep "control_task\|resume\|restart" src/xianyu_hunter/web/routes/` → 检查是否补启动基础设施
- 启动日志缺 `"EventBus 主循环启动"` 或类似 INFO → 违反规则5


---

### step 279：SCHEDULER-LOOP-LAYERED-EXCEPTION 调度器主循环异常分层捕获规范【强制】🆕v4.69

**背景**：与 step 277「CREATE-TASK-EXCEPTION-VISIBILITY」互补——step 277 关注「create_task 包装的协程必须用 try/except 兜底」，本规范关注「调度器主循环的异常分层捕获策略」。`_scheduler_loop` 被 `asyncio.create_task` 包装，原实现只捕获 `asyncio.CancelledError`，`start_all()` 抛出的其他异常被静默吞掉。即使配合 step 275（批量启动容错）隔离了单个任务失败，`start_all` 之外的其他异常（如 `workers` 列表构造异常、`stop_event` 创建失败、`container.scheduler` 属性访问异常）仍会静默退出主循环。

**问题**：调度器主循环（`_scheduler_loop` / `_bus_loop` / `_health_check_loop`）被 `asyncio.create_task` 包装后，异常处理策略不当导致三类问题：① 只捕获 `CancelledError`，其他异常静默吞掉；② 用 `except BaseException` 统一捕获，吞掉 `KeyboardInterrupt` / `SystemExit`；③ `except Exception` 后用 `logger.error(f"...{e}")` 丢失 traceback，无法定位根因。

**规范**：

1. **异常分层捕获【强制】**：调度器主循环必须按 `CancelledError` → `Exception` 顺序分层捕获，**禁止**用 `except BaseException` 统一捕获：
   ```python
   # ✅ 正确：分层捕获
   async def _scheduler_loop() -> None:
       try:
           container.scheduler.start_all()
           stop_event = asyncio.Event()
           await stop_event.wait()
       except asyncio.CancelledError:
           # 第 1 层：取消信号，清理资源后传播
           logger.info("调度器正在停止...")
           await container.scheduler.stop_all()
           raise  # 传播取消信号（符合 SonarQube S7497）
       except Exception as e:
           # 第 2 层：兜底捕获所有非 CancelledError 异常
           logger.exception(f"调度器主循环启动失败: {e}")
           raise  # 重新抛出让 task.exception() 可查

   # ❌ 错误 1：只捕获 CancelledError，其他异常静默吞掉
   async def _scheduler_loop() -> None:
       try:
           await stop_event.wait()
       except asyncio.CancelledError:
           pass
       # 其他异常被 create_task 静默吞掉

   # ❌ 错误 2：用 BaseException 统一捕获，吞掉 KeyboardInterrupt / SystemExit
   async def _scheduler_loop() -> None:
       try:
           await stop_event.wait()
       except BaseException as e:
           logger.exception(f"调度器异常: {e}")  # 吞掉了 KeyboardInterrupt
   ```

2. **CancelledError 必须清理资源后 re-raise【强制】**：`except asyncio.CancelledError` 块中必须执行资源清理（`stop_all` / `close` / `cleanup`），清理完成后必须 `raise` 传播取消信号，符合 SonarQube S7497 规则。**禁止**吞掉 `CancelledError`（`except asyncio.CancelledError: pass`），会导致取消信号无法传播，应用关闭时调度器不停止。

3. **Exception 必须保 traceback【强制】**：`except Exception as e` 块中必须用 `logger.exception()`（自动记录 traceback），**禁止**用 `logger.error(f"...{e}")` / `logger.warning(f"...{e}")`（丢失 traceback，无法定位根因）。这是 meta-rule #26「关键路径异常保 traceback」的落地。

4. **Exception 必须 re-raise【强制】**：`except Exception as e` 块中 `logger.exception()` 后必须 `raise`，让 task 进入 `done` 状态且 `task.exception()` 可查，配合 step 74「后台任务健康监控」轮询检查 `task.done()` 感知异常退出。**禁止**吞掉异常后 `await stop_event.wait()` 继续运行（掩盖了启动失败的事实，调度器主循环"假活"）。

5. **与 step 275 配合【强制】**：即使 `start_all()` 按 step 275 容错了单个任务失败，`_scheduler_loop` 仍必须用 `except Exception` 兜底，捕获 `start_all` 之外的其他异常（如 `workers` 列表构造异常、`container.scheduler` 属性访问异常）。step 275 隔离的是「批量操作内部单项目失败」，本规范隔离的是「主循环启动阶段的异常」。

6. **启动日志必须可见【强制】**：`try` 块中 `start_all()` 后必须记录启动成功日志（`logger.info(f"调度器已启动 N 个任务: [...]")`），便于排查"调度器是否真正启动"。与 step 101「关键调度器启动状态可见性规范」配合。

**配置驱动**：参数在 `config.yaml` 的 `schedulerLoopLayeredException` 节点管理，包含 `enabled`（开关，默认 true）、`requireCancelledErrorLayer`（是否强制 CancelledError 单独捕获，默认 true）、`requireExceptionLayer`（是否强制 Exception 兜底捕获，默认 true）、`forbiddenBroadExcept`（禁止的宽泛异常类型，默认 `["BaseException"]`）、`requireReRaise`（是否强制重新抛出，默认 true）、`requireLoggerException`（是否强制用 logger.exception 而非 logger.error，默认 true）、`requireStartupLog`（是否强制启动成功日志，默认 true）、`applicableLoops`（适用的循环类型列表，如 `["scheduler_loop", "event_bus_loop", "health_check_loop"]`）。

**适用场景**：
- 调度器主循环（`_scheduler_loop`）
- 事件总线消费者循环（`_bus_loop`，与 step 274 配合）
- 健康检查循环（`_health_check_loop`）
- Cookie 同步循环（`_cookie_sync_loop`）
- 所有被 `asyncio.create_task` 包装的长期运行后台循环

**不适用场景**：
- 短时一次性 task（如 `asyncio.create_task(fetch_one())` 后立即 await）→ 调用方直接拿到异常
- 有 `done_callback` 处理异常的 task → callback 中处理异常
- 测试代码中的 task（pytest-asyncio 框架捕获异常）
- 同步函数（无 asyncio.CancelledError 概念）

**历史教训**：2026-07-30 服务重启时 `TaskScheduler.start_all()` 抛 `ResumeBlockedError`，`_scheduler_loop` 只捕获 `CancelledError`，异常被 `asyncio.create_task` 静默吞掉，调度器主循环从未真正启动，所有后台任务都不运行，日志中无任何错误信息。即使修复 `start_all` 容错（step 275），`_scheduler_loop` 仍需 `except Exception` 兜底捕获 `start_all` 之外的其他异常。修复后 `_scheduler_loop` 增加 `except Exception as e: logger.exception(...); raise`，异常可见且 task 进入 done 状态可被健康监控感知。

**判断信号（review 触发条件）**：
- `grep "async def _scheduler_loop\|async def _bus_loop\|async def _health_check_loop" <file>` 命中后检查方法体内是否含分层捕获
- `grep "except asyncio.CancelledError" <file>` 后无 `except Exception` 兜底 → 违规
- `grep "except BaseException" <file>` → 违规（吞掉 KeyboardInterrupt / SystemExit）
- `grep "except asyncio.CancelledError" <file>` 后无 `raise` → 违规（吞掉取消信号）
- `grep "logger.error.*f\".*{e}\"\|logger.warning.*f\".*{e}\""` 在主循环 → 违规（应用 `logger.exception`）
- `except Exception` 块中无 `raise` → 违规（吞掉异常后继续运行）


---

