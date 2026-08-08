# 工作流与错误处理
> 包含元规范 #21 - #41

## 21. 错误处理决策树（适用于所有 try/except / .catch）

捕获异常后按三问决策：

1. **是否为启动/迁移/关键路径？**（函数名匹配 `config.yaml` 的 `error_handling_decision_tree.critical_path_patterns`）
   - 是 → `logger.exception()` 输出完整 traceback + 阻断启动
   - 否 → 进入问 2
2. **是否需要向用户展示？**
   - 是 → `reason_code`（与后端 `failure_reason_propagation.reason_enum` 对齐）+ `user_message` + 内部 `detail` 三层
   - 否 → `logger.warning` + 计数累计
3. **是否需要重试？**
   - 是 → 指数退避（`retry_strategy: exponential_backoff`）+ 熔断 + 持久化重试状态
   - 否 → 直接记录 + 上报

**关键约束**：
- 关键路径外层 except 禁止 `logger.warning(f"...{e}")`（丢失堆栈）
- 多个独立 try/except 块**禁止**外层统一 try/except 吞异常（强依赖场景允许合并但需注释说明）

**判断信号**：`grep "except" <file>` 关键路径缺 `logger.exception()` 即视为违规。

**适用**：启动钩子、迁移函数、初始化函数、API 路由 try/except、前端 `.catch`。
**不适用**：性能 hot path（用结构化异常）/ 测试代码（`pytest.raises` 期望异常）。

**历史教训**：`run_migrations()` 用外层 `try/except Exception as e: logger.warning(f"迁移失败: {e}")` → 后续迁移块全部跳过 → 启动时缺列触发 `OperationalError`。修复：每个迁移块独立 try/except + 关键路径用 `logger.exception()`。

## 22. 批处理熔断模板（适用于长任务断点续传）

长任务（>30 秒）+ 多步进度 + 需要断点续传的场景必须遵循：

**状态机**：`running → paused（可恢复）→ running（续传）` / `running → stopped（用户主动）/ failed（异常）/ completed（成功）`（后三个为终态）

**强制约束**：
1. **每完成一项就 `save_progress()`**（**关键**：熔断时漏持久化是历史高频 bug）
2. **熔断时**：剩余项标记 `pending`（配置项 `mark_remaining_as`），保存当前 `cursor` / `completed_ids` / `remaining_ids`（`persist_keys`）
3. **续传**：从持久化的 `cursor` 恢复，跳过已完成项
4. **日志区分**：使用 `config.yaml` 的 `log_phrasing.paused` / `stopped` / `failed` 三套文案，避免"暂停"与 `break` 混用导致语义不一致

**关键约束**：
- `failure_threshold`（默认 3）触发熔断后**必须**调用 `save_progress()`，禁止 `break` 后无持久化
- 剩余项处理策略从 `mark_remaining_as` 读取（`pending` / `skipped`），禁止硬编码

**判断信号**：
- `grep "consecutive failure" <file>` 但代码无 `save_progress()` 调用 → 视为违规
- `break` 与 `paused` 混用 → 视为违规
- 日志文案"暂停"但实际 `break` 跳出循环 → 视为违规（语义不一致）

**适用**：批量采集、批量导入、批量上报、长任务、用户主动取消（走 stopped 分支）。
**不适用**：实时单次请求、幂等的小批量（≤3 个）操作、性能 hot path。

**历史教训**：`batch_refresh_scheduler.py` 的 BatchRefresh#95 连续失败 3 次后用 `break` 跳出循环并标记剩余商品为 `skipped`，但**没有调用 `_save_progress()`** 持久化剩余项。导致"断点续传失效 + 剩余项被永久跳过"双重问题。修复后：熔断分支调用 `_save_progress()` + 修正日志措辞为"批次熔断暂停（可恢复）"。

## 25. 批量处理四要素（断路器 + 进度持久化 + 续传 + 日志对称）

> 与 #22 批处理熔断模板的区别：本条聚焦**熔断时刻的强约束四要素**，#22 侧重状态机整体；本条是 #22 的「熔断分支」专项检查。

批量处理（>30 秒 / 涉及多个 item / 需断点续传）触发熔断时必须满足四要素：

1. **失败计数**：`failure_threshold`（默认 3，连续失败）+ `failure_window_sec`（默认 3600，滑动窗口）双条件
2. **进度持久化**：熔断分支**必须**调用 `save_progress()`（cursor/completed_ids/remaining_ids 三键齐全），与「用户主动停止」分支对称
3. **续传入口**：从持久化 cursor 恢复，启动时检查 `pending_marker_dir`（默认 `data/markers/`）决定是否触发续传
4. **日志对称**：使用 `config.yaml#batch_circuit_breaker.log_phrasing` 区分 `paused` / `stopped` / `failed` 三套文案，禁止"暂停"与 `break` 混用

**关键约束**：
- 熔断分支未调用 `save_progress()` → 视为**必修 P0 缺陷**（断点续传失效 + 剩余项被永久跳过）
- `log_phrasing` 文案与实际动作必须一致（如"批次熔断暂停（可恢复）"对应 `break + save_progress`，不是 `return`）

**判断信号**：
- `grep "consecutive failure\|consecutive_failures" <file>` 出现但同函数内无 `save_progress()` → 视为违规
- `grep "break" <file>` 后紧跟 `mark.*skipped` 但无 `save_progress` → 视为违规
- `grep "paused" <file>` 但实际 `return`/`break` 跳出循环 → 视为日志语义不一致

**适用**：批量采集（`batch_refresh_scheduler`）、批量导入、批量上报、长任务重试。
**不适用**：单次 API 调用、≤3 个 item 的小批量操作、性能 hot path（持久化开销不可接受）、用户主动停止（走 stopped 分支，无须 save_progress）。

**历史教训**：`batch_refresh_scheduler.py` 的 BatchRefresh#95 连续失败 3 次后 `break` 跳出循环，将剩余商品标记为 `skipped`，但**未调用 `_save_progress()`**。结果：(1) 下次启动无法加载 `remaining_ids` 触发续传；(2) 剩余 10170xxxxx 等 6 个商品被永久跳过且日志无任何持久化记录。两缺陷叠加导致「看似批次结束，实际数据未处理」。

## 26. 关键路径异常保留完整 traceback

> 与 #21 错误处理决策树的关系：#21 给出「是否 critical path → logger.exception」的判断逻辑，本条是 critical path 内的**硬约束细化**。

`config.yaml#error_handling.critical_path_patterns` 列表中的函数（即「关键路径」：`_on_startup` / `run_migrations` / `_init_*` / `_on_close`）外层 except **必须**满足：

1. **使用 `logger.exception()`**：保留完整 traceback（含调用链、异常类型、文件行号）
2. **禁止 `logger.warning(f"...{e}")`**：仅打印异常对象会丢失 Python 堆栈、局部变量、上下文信息
3. **禁止 `logger.error(f"...{e}")`**：同上，error 级别还会触发告警噪音
4. **多个独立 try/except 块**禁止外层统一 try/except 吞掉后续块（强依赖场景如「表重建+数据回填」允许合并但需注释说明合并原因）
5. **降级不静默**：即使 catch 后继续启动，也必须 `logger.exception` 记录，启动后通过 `pending_marker` 提醒用户

**关键约束**：
- `grep "except Exception" <file>` 关键路径缺 `logger.exception()` → 视为违规
- `grep "logger.warning.*f\".*{e}\"\|logger.error.*f\".*{e}\"" <file>` 在关键路径 → 视为违规

**判断信号**：
- 函数名匹配 `critical_path_patterns`（如 `*_on_startup`/`run_migrations`/`_init_*`）→ 强制检查其外层 except
- 关键路径 try 块中含 `await` / `cursor.execute` / `INSERT` 等 IO 操作 → 视为高风险

**适用**：`_on_startup` / `run_migrations` / `_init_db` / `_init_session_manager` / `_on_close` / `_shutdown` / `_register_signal_handlers`。
**不适用**：常规业务函数（用 `logger.error(f"...{e}")` 即可）、测试代码（`pytest.raises` 期望异常）、性能 hot path（结构化异常）。

**历史教训**：`run_migrations()` 用外层 `try/except Exception as e: logger.warning(f"迁移失败: {e}")` → 后续 5 个迁移块 C-01~C-05 全部跳过（异常被吞）→ 启动时表缺列触发 `OperationalError: no such column`。修复：每个迁移块独立 try/except + 关键路径用 `logger.exception()` 输出完整 traceback，问题定位时间从 2 小时缩短到 5 分钟。

## 31. 状态恢复前置校验（pause→resume 根因消除校验）🆕v4.31

> 与 B-REVIEW-157（backend 调度器/任务恢复维度）+ F-REVIEW-116（frontend resume 按钮前置校验）对应。
> 本条覆盖所有具有 pause/resume 语义的组件的**恢复前根因消除校验**。

具有 pause/resume 语义的组件（任务调度器、登录会话、连接池、断路器）在 resume 操作前，必须校验「导致 pause 的根因」是否已消除，未消除时拒绝恢复并返回结构化提示。

1. **pause 时记录根因**：异常 pause 必须将 `root_cause`（含 `reason_code` + 失效层标识 + 时间戳）持久化到任务/会话状态，而非仅记日志
2. **resume 前 precheck**：resume 操作必须调用 precheck 函数校验 `root_cause` 对应的前置条件是否已恢复（如 Cookie 层 valid、连接可达、配额充足）
3. **结构化拒绝响应**：校验失败时返回 `{resume_blocked: true, reason_code, user_hint, retry_after}`，禁止静默失败或无条件放行
4. **冷却期**：异常 pause 后设置冷却期（`config.yaml#resume_policy.cooldown_seconds`），期间拒绝 resume，避免"恢复→失效→暂停"无效循环
5. **配置驱动**：冷却期时长、前置校验开关、`reason_code` → precheck 函数映射表均从 config 读取，禁止硬编码

**关键约束**：
- `resume`/`start`/`unpause` 接口缺 precheck 调用 → 视为**必修 P0 缺陷**（无效循环风险）
- 异常 pause 未记录 `root_cause` 字段 → 视为违规（无法校验根因消除）
- resume 接口无拒绝分支（无条件放行）→ 视为违规
- 冷却期时长硬编码在代码中 → 视为违规（应从 config 读）

**判断信号**：
- `grep "def resume\|def start\|def unpause\|def activate" <file>` 缺 `precheck`/`_check_prerequisite` 调用 → 视为违规
- `grep "pause\|paused\|should_pause"` 无 `root_cause` 字段赋值 → 视为违规
- resume 接口 `grep "return.*True\|return.*ok"` 无 `if not precheck` 拒绝分支 → 视为违规
- `grep "cooldown\|cool_down"` 时长为字面量数字而非 config 引用 → 视为硬编码

**适用**：任务调度器 pause/resume（如搜索任务会话失效暂停）、登录会话失效/恢复（Cookie 层失效后重新登录）、连接池断连/重连、断路器开/闭、限流配额耗尽/恢复。
**不适用**：用户主动 pause（非异常触发，无 root_cause）、一次性任务（无 resume 语义）、纯函数重试（无状态持久化）、开发调试手动 resume。

**历史教训**：搜索任务 `t68bc149b` 因闲鱼会话失效（RGV587_ERROR）被自动暂停后，用户/系统在 30 分钟内连续 4 次恢复任务，但 Cookie 未重新登录刷新，每次恢复后 13~22 秒内再次触发会话失效检测并暂停，形成"恢复→失效→暂停"无效循环，浪费浏览器资源并产生 555 条冗余 WARNING。修复：resume 前校验 `cookie_rotator` 的 identity/session 层 `valid` 状态，失效时拒绝恢复并提示"请先重新登录闲鱼"；异常 pause 后设 5 分钟冷却期（config 可配），彻底消除无效循环。

## 32. 多阶段降级链日志合并 🆕v4.31

> 与 B-REVIEW-158（backend 日志规范维度）对应。前端无降级链日志场景，不新增前端检查点。

同一逻辑链的多个中间阶段（降级、重试、回退、多策略尝试）日志必须合并为 1 条结构化结果日志，禁止每个中间步骤独立输出 WARNING。

1. **中间步骤 DEBUG 化**：降级/重试链的中间步骤（如"尝试刷新 token""尝试 DOM 回退"）使用 `logger.debug()`，最终结果使用 `logger.warning()` 或 `logger.error()`
2. **结果日志结构化**：最终结果日志必须含结构化 `extra` 字段：`{stages: [...], final_reason, keyword/context, attempts}`，其中 `stages` 为各中间步骤的简述数组
3. **合并阈值**：同一逻辑链内 ≥2 个阶段则必须合并（`config.yaml#log_merge.min_stages_to_merge` 可配），单阶段无需合并
4. **配置驱动**：合并阈值、中间步骤 DEBUG 开关、保留的中间步骤白名单均从 config 读取

**关键约束**：
- 同一函数内 ≥3 个 `logger.warning` 且属于同一 try/降级链 → 视为违规（应合并为 1 条）
- 降级链中间步骤用 `logger.warning` 而非 `logger.debug` → 视为违规（噪音日志）
- 结果日志无 `extra` 结构化字段 → 视为不规范（无法聚合分析）
- 合并阈值硬编码 → 视为违规（应从 config 读）

**判断信号**：
- `grep -c "logger.warning" <file>` 同一函数内 ≥3 条且属于同一降级链 → 视为违规
- `grep "logger.warning.*尝试\|logger.warning.*刷新\|logger.warning.*回退\|logger.warning.*重试" <file>` 多条且无结构化合并 → 视为冗余告警
- 降级链结果日志 `grep "logger.warning"` 缺 `extra=` 参数 → 视为不规范

**适用**：降级链（API→DOM→缓存）、重试链（指数退避多轮）、多策略回退（多 selector 候选）、浏览器自动化多策略尝试、批处理多阶段校验。
**不适用**：独立的一次性告警（不同业务流程）、用户操作触发的即时反馈、关键路径异常的 `logger.exception()`（需完整堆栈）、不同函数/模块的告警。

**历史教训**：搜索 API 会话失效时，`_search.py` 在同一次搜索失败中输出 5 条 WARNING（FAIL_SYS_ILLEGAL_ACCESS → 尝试强制刷新 _m_h5_tk → 刷新失败 → 尝试 DOM 回退 → DOM 回退超时），单次搜索失效产生 5 条噪音日志，12 小时内累积 555 条冗余 WARNING（占总 WARNING 88%），淹没真正需要关注的告警。修复：中间步骤降为 DEBUG，最终合并为 1 条结构化 WARNING（含 `stages`/`final_reason`/`keyword`），告警量从 628 降至 ~80，可观测性显著提升。

## 41. 状态恢复前置校验结构化响应（RESUME-PRECHECK-STRUCTURED）🆕v4.34

> 与 B-REVIEW-167（backend precheck 结构化响应）/ F-REVIEW-125（前端 precheck 失败 UI 反馈）对应。
> 与 #31 状态恢复前置校验的关系：#31 给出「resume 前 precheck 校验根因」的整体框架，本条是 precheck 函数自身的**结构化响应契约**。

precheck 函数必须返回结构化 dict，不抛异常，包含 5 个标准字段，便于 API 层统一转换为 HTTP 响应与前端统一渲染。

1. **5 字段结构化响应**：precheck 必须返回 dict，含 5 字段：
   - `resume_blocked: bool` — 是否阻断恢复
   - `reason_code: str` — 来自 `config.yaml#error_code.reason_enum` 枚举（ok / cooldown / cookie_invalid / not_registered 等）
   - `user_hint: str` — 人类可读提示（含恢复动作建议）
   - `retry_after: int | None` — 冷却期剩余秒数（null 表示无冷却期）
   - `task_registered: bool` — 任务是否注册到调度器（区分纯 web 模式）
2. **不抛异常原则**：precheck 内部异常必须 catch 并转换为结构化响应，禁止向上抛异常（API 层无法统一处理）
3. **API 层转换**：API 层（`api_tasks.py` 等）调用 precheck 后直接返回 dict，禁止再做异常转换
4. **前端 4 字段消费**：前端必须消费 4 字段（`resume_blocked` / `reason_code` / `user_hint` / `retry_after`），按 `reason_code` switch 分支
5. **配置驱动**：5 字段名、reason_code 枚举、纯 web 模式响应模板从 `config.yaml#precheck_structured_fields` 读取

**关键约束**：
- precheck 函数 `raise` 异常 → 视为**必修 P0 缺陷**（API 层无法处理）
- precheck 返回 dict 缺任一标准字段 → 视为违规
- API 层用 `try/except` 包 precheck → 视为违规（应在 precheck 内部 catch）
- 前端不消费 `reason_code` 而用 `user_hint.includes(...)` 判断 → 视为违规（违反 #29）

**判断信号**：
- `grep "def precheck_\|def _precheck" <file>` 函数体内含 `raise` → 视为违规
- `grep "def precheck_\|def _precheck" <file>` 返回值缺 `resume_blocked\|reason_code\|user_hint\|retry_after\|task_registered` 任一 → 视为违规
- `grep "precheck.*\(.*\).*:" <file>` API 路由内含 `try.*precheck.*except` → 视为违规
- `grep "result\.user_hint\.includes\|result\.user_hint\.indexOf" frontend/` → 视为违规

**适用**：任何 precheck/resume 类接口（任务恢复 / 会话恢复 / 调度器恢复 / 连接池重连 / 断路器闭合 / 限流配额恢复）。
**不适用**：单纯校验函数（无结构化响应需求，直接返回 bool）、同步阻塞式校验（无恢复语义）、纯前端校验（无后端 precheck）。

**历史教训**：`scheduler.precheck_resume` 最初设计为抛 `ResumeBlockedError` 异常，`api_tasks.py` 用 `try/except` 捕获后转换为 400 响应。问题：(1) 多种阻断原因（冷却期 / Cookie 失效 / 未注册）需多个异常类，类爆炸；(2) 前端无法用 `reason_code` 分支只能 substring 判断 `user_hint`；(3) 纯 web 模式（无 collector）需特殊处理。修复：改为结构化 dict 返回 5 字段，API 层直接透传，前端按 `reason_code` switch 分支（cooldown 显示倒计时、cookie_invalid 跳登录、not_registered 提示重启服务）。
