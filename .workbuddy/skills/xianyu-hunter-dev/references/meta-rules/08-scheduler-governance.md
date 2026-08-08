# 调度器治理
> 包含元规范 #48 - #109

## 48. 调度器运行时开关对称性（SCHEDULER-RUNTIME-TOGGLE-SYMMETRY）🆕v4.36

> 与 B-REVIEW-178（backend 调度器开关对称性审查）/ F-REVIEW-136（前端调度器状态同步审查）对应。

调度器（APScheduler BackgroundScheduler/AsyncIOScheduler）的 `update_config(enabled=False)` 必须立即生效——调用 `remove_job(job_id)` 移除已注册 job + job 函数入口 `if not self._enabled: return` 双重检查；`update_config(enabled=True)` 必须恢复 job（`add_job(...)` 或 `resume_job(...)`）。开关操作必须对称：禁用即移除、启用即恢复，禁止"禁用只设标志位不移除 job"或"启用只设标志位不恢复 job"的不对称实现。

1. **禁用立即生效**：`update_config(enabled=False)` 必须在同一个方法内完成"设标志位 + remove_job"两步操作，禁止只设标志位依赖 job 函数入口检查兜底（job 函数入口检查是第二道防线，不是第一道）
2. **入口 double-check**：job 函数入口必须 `if not self._enabled: logger.warning("调度器已禁用但 job 仍触发，检查 update_config 实现"); return`，作为 remove_job 失败/时序竞态的兜底
3. **启用恢复 job**：`update_config(enabled=True)` 必须调用 `add_job(...)` 或 `resume_job(job_id)` 重新注册/恢复 job，禁止只设标志位期望"下次 job 触发时自动恢复"
4. **开关状态可查询**：调度器必须提供 `is_enabled() -> bool` 方法供 API 层查询当前状态，禁止 API 层直接访问 `_enabled` 私有字段
5. **配置驱动**：`enabled` 字段必须从 `config.yaml` 的对应节点读取（如 `batch_refresh.enabled` / `cookie_sync.enabled`），运行时 `update_config` 修改后必须同步写回 config 持久化（参考 B-REVIEW-CONFIG-DRIVEN-TOGGLE）

**关键约束**：
- `update_config(enabled=False)` 后 `scheduler.get_job(job_id)` 仍返回非 None → 视为 CRITICAL（禁用未生效）
- `update_config(enabled=True)` 后 `scheduler.get_job(job_id)` 返回 None 且无 `add_job` 调用 → 视为 CRITICAL（启用未恢复）
- job 函数入口无 `if not self._enabled: return` → 视为 WARNING（缺第二道防线）
- API 层直接访问 `scheduler._enabled` → 视为 WARNING（应通过 `is_enabled()` 方法）

**判断信号**：
- `grep "def update_config" <scheduler_file>` 缺 `remove_job` 或缺 `add_job`/`resume_job` → 开关不对称
- `grep "def _run_.*_job" <scheduler_file>` 缺 `if not self._enabled` → 缺入口 double-check
- `grep "scheduler\._enabled\|scheduler\.enabled" routes/` → API 层直接访问私有字段

**适用**：所有 APScheduler 调度器（BackgroundScheduler/AsyncIOScheduler）；具有 `enabled` 配置开关的后台任务；运行时可动态启停的调度器（如批量采集/Cookie 同步/状态回查）。
**不适用**：一次性任务（无 `enabled` 字段）；启动时确定整个生命周期不启停的调度器（如系统监控）；外部托管调度器（如 celery beat，由外部进程管理）。

**历史教训**：`BatchRefreshScheduler.update_config(enabled=False)` 只设 `self._enabled = False` 标志位，未调用 `scheduler.remove_job()`，APScheduler 已注册的 job 仍按 trigger 触发，触发后 job 函数入口也无 double-check，导致禁用后仍持续执行批量采集。同期 `CookieSyncScheduler` 完全没有 `_enabled` 字段和 `update_config` 方法，配置开关形同虚设。修复：两个调度器都加 `_enabled` 字段 + `update_config` 方法（禁用即 remove_job、启用即 add_job）+ job 函数入口 double-check。建立 #48 强制对称规则。

## 51. 用户输入时间表达式校验（CRON-MIN-INTERVAL-CHECK）🆕v4.36 experimental

> 与 B-REVIEW-181（backend cron 表达式最小间隔审查）/ F-REVIEW-139（前端 cron 表达式校验审查）对应。
> experimental 标签：仅 1 个相似 bug（Cron 模式无最小间隔校验），按 #36 门槛规则未达标（≥3 个相似 bug 才立正式规范），标 experimental 标签预沉淀，1 季度观察期内若再出现 ≥2 个相似 bug 则升级为正式规范。

用户输入的 cron 表达式（如 task 的 `schedule_cron` 字段）必须校验最小间隔 ≥ 反爬最小延迟（`antidetect.min_delay_ms / 1000` 秒），禁止 `* * * * *`（每秒执行）等滥用表达式导致触发反爬封禁。校验在 `add_job` 前执行，校验失败返回结构化错误不抛异常。

1. **cron 表达式解析**：使用 `apscheduler.triggers.cron.CronTrigger.from_crontab(cron_expr)` 解析表达式，解析失败返回 `{"valid": False, "reason": "cron 表达式语法错误"}`
2. **最小间隔计算**：解析后计算连续两次触发的时间差最小值（`_get_min_cron_interval_seconds(cron_expr) -> float`），通过枚举 24 小时内所有触发点取最小差值
3. **阈值校验**：最小间隔 < `get_config().antidetect.min_delay_ms / 1000` 视为滥用，返回 `{"valid": False, "reason": "cron 最小间隔 X 秒 < 反爬最小延迟 Y 秒"}`；阈值配置读取失败回退 10 秒默认值
4. **配置读取容错**：`_get_min_cron_interval_seconds` 内 `try/except` 包裹 `get_config()` 调用，配置缺失时回退 `return 10.0`（参考 #42 配置化阈值兜底范式）
5. **配置驱动**：最小间隔阈值、回退默认值、校验开关从 `config.yaml#cron_min_interval_check` 节点管理

**关键约束**：
- `grep "CronTrigger\.from_crontab" <file>` 但无 `_get_min_cron_interval_seconds` 调用 → 视为 WARNING（缺最小间隔校验）
- `add_job` 前无 cron 表达式校验 → 视为 WARNING
- 校验函数内 `raise ValueError` → 视为 WARNING（应返回结构化 dict 不抛异常，参考 #41）

**判断信号**：
- `grep "CronTrigger" <file>` 无 `min_interval` 校验 → 缺最小间隔校验
- `grep "schedule_cron" <file>` 但无 `validate_cron` 调用 → 用户输入未校验
- `grep "def _get_min_cron_interval_seconds" <file>` 无 `try.*except` → 配置读取无容错

**适用**：用户输入的 cron 表达式（task 的 `schedule_cron` 字段）；APScheduler CronTrigger 调度器；可能触发反爬的定时任务（采集/同步/轮询）。
**不适用**：interval 触发器（已通过 `seconds=` 参数控制间隔）；date 触发器（一次性执行无间隔概念）；内部系统调度（非用户输入，已通过 code review 保证合理）；测试用 cron 表达式（测试环境无反爬风险）。

**历史教训**：task 的 `schedule_cron` 字段接受任意 cron 表达式，用户配置 `* * * * *`（每分钟执行）导致批量采集每分钟触发一次，远低于反爬最小延迟（10 秒），触发闲鱼反爬封禁。修复：在 `scheduler.py` 加 `_compute_next_wait_seconds` 调用 `_get_min_cron_interval_seconds` 校验最小间隔，小于阈值时返回结构化错误不创建 job。建立 #51 强制校验规则（experimental，待 1 季度观察期升级）。

---

# 工程闭环元规范（52-56）🆕v4.37

> 以下 5 条元规范从 2026-07-07 修复的「价格过滤失效 / SEMI_AUTO 模式退化 / 外部 DOM 解析失败 / 测试 mock 错配 / 多参数 UI 不透明」5 类问题中提炼，使用 Sequential Thinking 4 维度复盘法（成功步骤 / 不确定性与失败点 / 可抽象的固定流程与判断逻辑 / 适用场景与不适用场景）抽象而成。
>
> 与 v4.36.0 的 #48 调度器运行时开关对称性（SCHEDULER-RUNTIME-TOGGLE-SYMMETRY）视角互补：v4.36.0 #48 关注"update_config + double-check"对称性，本批次不重复定义调度器开关规范。
>
> 命名空间与配置驱动：所有阈值（参数名白名单 / mock 类型映射表 / fallback 层级数）均在 `config.yaml` 对应节点管理，禁止硬编码。

## 86. 调度器状态机恢复路径校验（SCHEDULER-STATE-MACHINE-RECOVERY）🆕v4.55.0

> 与 B-REVIEW-245（backend 调度器状态机恢复路径审查）/ xianyu-auto-testing 模式 L（状态机死锁回归测试）对应。
> 与 #31（状态恢复前置校验）的关系：#31 关注"resume 前必须校验根因消除"；#86 关注"pause/resume 的事件配对与 loop 闭环"。

**问题背景**：任务管理模块中所有任务处于启动状态但未进行持续周期性实时搜索商品。根因是 `scheduler.py` 的 `_run_loop` 函数在会话失效（`should_pause=True`）时通过 `return True` 导致主循环 `break`，后续 `resume` API 调用 `pause_event.set()` 时无循环在等待该 event，造成任务永久卡死。同一问题暴露三个关联缺陷：(1) `should_pause` 返回值语义混淆（True 被外层解读为"应退出循环"而非"应暂停"）；(2) `_execute_run_once_locked` 在 `should_pause` 时返回 True 而非 False；(3) `_run_one_iteration` 会话失效暂停时重置了 `consecutive_errors`，恢复后误判健康。

**核心原则**：
1. **pause/resume 事件配对**：`pause_event.set()` 必须有对应的 `pause_event.wait()` 在等待。`set` 后无 `wait` 是状态机断裂的标志——意味着 pause 信号无处接收，resume 时无法唤醒循环。**禁止**在 pause 分支 `return True` 导致主循环 `break` 退出。
2. **暂停语义是"循环回到顶部阻塞"而非"退出循环"**：会话失效时循环必须 `continue` 回到顶部，在顶部 `pause_event.wait()` 阻塞等待 resume。**禁止**用 `break` 或 `return` 退出循环——退出后 `pause_event.set()` 无 waiter，任务永久卡死。
3. **返回值语义统一**：`should_pause` 返回 False 表示"继续循环"（即使本次因会话失效跳过执行），返回 True 表示"应退出循环"。**禁止**混用"暂停"和"退出"两种语义到同一返回值。会话失效属于"暂停"（False），正常停止属于"退出"（True）。
4. **错误计数隔离**：会话失效导致的暂停不应重置 `consecutive_errors`——会话失效不是错误处理成功，恢复后仍需观察错误率。只有真正成功执行一次任务后才重置计数。
5. **恢复前置校验**：`resume` 前必须检查根因消除（如会话已恢复），不能无条件恢复。参考 #31。

**判断信号**：
- `grep "return True" scheduler.py` 在 `should_pause` 分支内 → 违规（应 `return False` + `continue`）
- `grep "pause_event.set" src/` 找到 resume 路径 → 检查是否有对应的 `pause_event.wait()` 在循环内
- `grep "pause_event.clear" src/` → 检查是否在 resume 前清除（否则循环不阻塞会空转）
- `grep "consecutive_errors = 0" scheduler.py` → 检查是否在会话失效暂停分支内（不应在此重置）
- 任务状态显示"运行中"但日志无"周期执行"记录 → 状态机死锁标志

**配置驱动**：
- `scheduler_state_machine.enabled`：是否启用状态机校验（默认 true）
- `scheduler_state_machine.pause_event_name`：暂停事件字段名（默认 `pause_event`）
- `scheduler_state_machine.should_pause_return_value`：会话失效时的正确返回值（默认 `false`）
- `scheduler_state_machine.loop_top_check_required`：循环顶部是否必须检查 pause_event 状态（默认 true）
- `scheduler_state_machine.error_reset_guard`：错误计数重置守卫——仅在任务成功执行后重置（默认 true）
- `scheduler_state_machine.critical_files`：关键文件清单（默认 `['scheduler.py', '_run_loop', '_execute_run_once_locked', '_run_one_iteration']`）
- 禁止在代码中硬编码上述参数

**适用场景**：
- 后台任务调度器（APScheduler / 自定义 loop）
- 会话管理（登录态失效→暂停→恢复→继续执行）
- 任何使用 `threading.Event` / `asyncio.Event` 控制 loop 暂停/恢复的场景
- 多状态机协作（如任务循环 + 会话健康检查 + 熔断器）

**不适用场景**：
- 一次性执行的脚本（无循环概念）
- 无状态 API（每次请求独立）
- 进程级控制（用信号 SIGTERM/SIGINT，非 Event）
- 协程级取消（用 `asyncio.CancelledError`，非 Event）

**与其他规则区别**：
- 与 #31（状态恢复前置校验）的区别：#31 聚焦"resume 前校验根因"；#86 聚焦"pause/resume 的事件配对与 loop 闭环"
- 与 #25（批量处理四要素）的区别：#25 关注批处理的熔断与进度持久化；#86 关注调度器 loop 的暂停/恢复闭环
- 与 #22（批处理熔断持久化）的区别：#22 关注熔断后的 cursor 续传；#86 关注熔断后 loop 是否保留 wait 能力
- 与 step 50（异步操作整体超时保护）的区别：step 50 关注单次操作超时；#86 关注 loop 级别的暂停/恢复

**复盘来源**：2026-07-22 任务管理模块所有任务启动后不周期搜索 Bug。根因链：
1. `_run_loop` 会话失效时 `should_pause=True` → `_execute_run_once_locked` 返回 True → 主循环 `break`
2. 用户点击恢复 → resume API 调用 `pause_event.set()` → 但 loop 已退出，无 waiter
3. 任务状态显示"运行中"（因为 `is_running=True` 未被重置），但实际无 loop 在执行
4. `_run_one_iteration` 会话失效暂停时重置 `consecutive_errors=0`，恢复后误判健康

修复：
1. `_run_loop` 顶部检查 `pause_event` 状态，会话失效 `clear` 后跳过 interval 等待直接回到顶部阻塞
2. `_execute_run_once_locked` 在 `should_pause` 时返回 `False`（继续循环）而非 `True`（退出循环）
3. `_run_one_iteration` 会话失效暂停时不重置 `consecutive_errors`

对应 step 251/252/253。

## 109. 状态机返回值语义校验（STATE-MACHINE-RETURN-SEMANTICS）🆕v4.62.0

**问题**：状态机转换函数返回值语义不明确，调用方根据返回值做分支判断但返回值含义不一致（有时返回 `True`/`False`，有时返回新状态，有时返回 `None`），导致误判。

**核心规则**：
1. 状态机转换函数返回值语义必须统一：返回新状态对象（成功）或抛异常（失败），禁止返回 `True`/`False`/`None`
2. 返回值必须包含转换后状态 + 转换时间戳 + 转换原因
3. 调用方禁止根据返回值是否为 `None` 判断转换成功（应 try/except 捕获异常）

**判断信号**：
- `if scheduler.pause():` / `if not scheduler.resume():` → 违反规则1
- 状态机方法 `return True` / `return False` → 违反规则1
- 调用方 `result = state_machine.transition()` 后 `if result is None:` → 违反规则3

**配置参数**：`state_machine_return` 节点（enabled / returnValueFormat / exceptionOnFailure / requireTransitionReason）

**适用**：所有状态机转换（调度器 pause/resume、Cookie valid/invalid、任务 start/stop）
**不适用**：简单的布尔标志切换（非状态机模式）、纯查询方法（无状态变更）

**历史教训**：`scheduler.resume()` 返回 `True`/`False`，调用方 `if not scheduler.resume(): logger.error("恢复失败")`，但 `resume()` 内部捕获了所有异常并返回 `False`，真正的失败原因被吞掉。修复后 `resume()` 成功返回新状态对象，失败抛 `StateTransitionError`。

**对应 step**：step 245（state-management.md）。
