# 元规范（Meta-Rules）

> 📂 **已拆分为 12 个分类文件，按需查阅。**
>
> | 分类 | 文件 | 规范数 |
> |------|------|--------|
> | 核心原则 | [01-core-principles.md](meta-rules/01-core-principles.md) | #1-#20 |
> | 工作流 | [02-workflow.md](meta-rules/02-workflow.md) | #21-#24 |
> | 数据契约 | [03-data-contracts.md](meta-rules/03-data-contracts.md) | #25-#37, #66, #71, #88, #90-#91, #105, #108-#110 |
> | 列表聚合 | [04-list-aggregation.md](meta-rules/04-list-aggregation.md) | #38-#42 |
> | 跨层测试 | [05-cross-layer-testing.md](meta-rules/05-cross-layer-testing.md) | #43-#47 |
> | 调度器治理 | [06-scheduler-governance.md](meta-rules/06-scheduler-governance.md) | #48-#51, #86 |
> | 工程闭环 | [07-engineering-closure.md](meta-rules/07-engineering-closure.md) | #31, #52-#55, #111 |
> | 异步资源 | [08-async-resource.md](meta-rules/08-async-resource.md) | #57-#63, #79-#82, #92 |
> | Cookie 认证 | [09-cookie-auth.md](meta-rules/09-cookie-auth.md) | #72-#78, #96-#102 |
> | 前端 UI | [10-frontend-ui.md](meta-rules/10-frontend-ui.md) | #56, #64-#65, #67-#69, #83, #95, #103, #107 |
> | 性能缓存 | [11-performance.md](meta-rules/11-performance.md) | #93-#94, #104-#106 |
> | 配置安全 | [12-config-security.md](meta-rules/12-config-security.md) | #70, #87 |
>
> **[📋 完整索引（含关键词速查）](meta-rules/index.md)** | 主索引见 [SKILL.md](../SKILL.md)
>
> ⚠️ 以下为 111 条规范的**完整原文（canonical source）**，各分类文件仅提供摘要。

## 1. 配置驱动原则

所有 step 涉及的参数（阈值/超时/列表/映射表/命名规则）必须在 `config.yaml` 对应节点管理，**禁止**硬编码在代码或技能中。

**适用范围**：
- 数值型配置项（间隔时间/超时/重试次数/并发数/阈值）
- 字符串枚举值（状态码映射/错误文案模板）
- 列表/映射表（关键词白名单/选择器候选/字段对齐表）
- 命名规则（key 前缀/常量后缀/变量前缀）

**配置节点命名规范**：
- 节点名 `snake_case`
- 层级结构清晰，避免扁平化命名冲突
- 每个节点含 `enabled` 开关 + 详细参数字段

**例外**：
- 语言/框架级常量（如 HTTP 200、`path: "/"`）
- 协议固定值（不可配置）
- 安全必需的固定值（如 `hmac.compare_digest`）

## 2. 适用/不适用场景说明

每条编码规范必须明确说明**适用场景**与**不适用场景**，确保通用性，避免审查时误用于不适用场景。

**判断信号**：新增规范时必须自问"这个规范在什么场景下不适用？"，若无法回答则规范过于宽泛需细化。

**典型适用/不适用区分**：
- **适用**：业务模块、跨层调用、外部依赖、有状态生命周期
- **不适用**：纯函数、一次性脚本、内部信任数据、性能敏感 hot path

## 3. 历史教训归档

所有 step 的"历史教训"段落（含用户反馈/根因/修复过程）统一归档到：
- [version-history.md](version-history.md)（按版本组织）
- [cookie-state-recovery-patterns.md](cookie-state-recovery-patterns.md)（Cookie 层专题）
- 各 step 文件内的"历史教训"小节（保留简短引用）

**原则**：教训用于理解"为什么有这条规范"，不重复叙述完整排查过程。

## 4. 修复模式代码归档

完整的修复模式代码示例归档到对应主题文件（`coding-rules/<topic>.md`），step 内只保留：
- 核心规则一句话
- 判断信号（grep 关键词）
- 配置节点名
- 适用/不适用场景

**原则**：代码示例用于理解规范如何落地，不重复贴完整函数。

## 5. 判断信号优先 grep

所有判断信号必须可用 `grep` 验证，禁止用"语义判断"等模糊描述。

**判断信号格式**：
- `grep "<pattern>" <path>` 出现 → 视为违规/可疑
- `grep` 多个调用点 → 触发抽取建议
- 代码含 `<pattern>` → 必须检查

**禁止**：
- "代码风格不好"（无法 grep）
- "逻辑复杂"（无法 grep）
- "可能有问题"（无明确信号）

## 6. 复用优先级

新增功能/工具函数/帮助类时必须按以下优先级复用：

1. **项目内 helper**（如 `_utcnow`/`_escape_like`/`hmac.compare_digest`/`asyncio.wait_for`/`logger.warning`）
2. **标准库**（如 `contextlib.suppress`/`asyncio.gather`/`pathlib.Path`）
3. **第三方库**（如 `loguru`/`pydantic`/`SQLAlchemy`）
4. **新实现**（最后选择）

**判断信号**：新增函数 + `grep` 发现已有相似命名/相似参数/相似功能 → 必须复用而非重复实现。

**禁止**：跨 ≥2 文件出现相同的关键字/正则/常量字面量而未抽取共享（参考 step 113）。

## 7. 状态分类识别

新增任何状态字段前必须识别归属类别，选择对应持久化策略：

| 状态类别 | 持久化策略 | 典型示例 |
|---|---|---|
| 用户偏好类 | `usePersistentState`（localStorage） | 自动刷新/视图模式/列显隐/折叠/展开 |
| 业务数据类 | 后端 API + DB | 任务列表/订单状态/配置项 |
| 会话状态类 | Zustand store | 登录态/当前选中项/跨页共享 |
| 临时状态类 | `useState` | loading/modal open/submitting/表单 dirty |
| 敏感数据类 | secure storage / httpOnly cookie | token/密码/API key |

**判断信号**：新增 React state 时自问"刷新页面后状态应保留还是重置？"——保留则用户偏好类，重置则临时状态类。

## 8. 错误粒度区分

HTTP 状态码必须按语义精细化区分（参考 step 71/123）：

| 状态码 | 语义 | 前端动作 |
|---|---|---|
| 401 | 未登录 | 跳转登录页 |
| 403 | 权限不足 | 显示权限不足提示 |
| 440 | Cookie 过期 | 跳转重新登录 |
| 441 | Token 过期 | 刷新 Token |
| 429 | 反爬触发 | 提示手动验证 |
| 502 | 浏览器异常 | 提示重启服务 |
| 503 | 服务未启动 | 提示启动服务 |
| 504 | 网关超时 | 提示稍后重试 |

**禁止**：所有认证失败都映射为 `401` 导致前端无法区分"未登录"与"登录态过期"。

## 9. 日志级别规范

| 级别 | 适用场景 |
|---|---|
| `logger.error` | 需人工介入的失败（主流程失败/数据丢失/安全事件） |
| `logger.warning` | 可恢复异常/降级/重试（辅助功能失败/配置项缺失/可选资源不可用） |
| `logger.info` | 业务关键路径（触发抢单/采集完成/推送发送/调度器启动） |
| `logger.debug` | 调试信息（默认 INFO 级别不输出，仅开发环境可见） |
| `logger.exception` | 关键路径（启动钩子/迁移/初始化）外层 except 必须用，保留完整 traceback |

**禁止**：
- 辅助功能失败用 `logger.debug`（默认不输出，难以排查）
- 辅助功能失败用 `logger.error`（过度严重，污染告警）
- 关键路径外层 except 用 `logger.warning(f"...{e}")`（丢失堆栈）

## 10. 异步操作规范

所有 `await` 调用外部资源的异步操作必须满足：

1. **整体超时保护**：`asyncio.wait_for(coro, timeout=N)` 包裹，超时返回语义化状态码（504）
2. **超时时间从配置读取**：禁止硬编码，参考 `config.yaml` 的 `async_timeout` 节点
3. **CancelledError 传播**：用 `contextlib.suppress(asyncio.CancelledError)` 包裹并向上传播，禁止 `except: pass`
4. **Task 引用保留**：`self._task = asyncio.create_task(...)` 防止 GC，禁止裸 `asyncio.create_task(...)`
5. **取消+收集模式**：`task.cancel()` + `await asyncio.gather(task, return_exceptions=True)`

## 11. 安全调用检查

所有外部接口调用必须满足：

1. **空值/边界判断**：调用前校验参数非空、范围合法
2. **异常分支处理**：禁止 `except: pass` 静默吞异常
3. **敏感数据脱敏**：`_SENSITIVE_HEADERS` 过滤 authorization/cookie/xh_token/set-cookie
4. **权限校验**：`BearerAuthMiddleware` 白名单检查
5. **SQL 注入防护**：LIKE 用 `_escape_like`，表名/列名用 `_IDENT_RE` 白名单
6. **路径遍历防护**：用户输入用 `_USER_ID_RE` 等正则校验
7. **token 比较**：`hmac.compare_digest` 防时序攻击
8. **外部链接安全**：`target="_blank"` 配 `rel="noopener noreferrer"`

## 12. 状态机设计规范

含「状态」字段且状态会变化的业务对象必须满足：

1. **枚举穷举**：列出所有状态值
2. **转换白名单**：用 `(起始状态 → 目标状态)` 白名单校验，禁止黑名单
3. **终态不可复活**：`failed`/`succeeded`/`cancelled` 禁止再转换，状态变更接口前置校验
4. **中间态超时清理**：独立 APScheduler 定时扫描 + 一次 SQL 批量更新
5. **前后端枚举值统一**：禁止 snake_case ↔ camelCase 映射转换

## 13. 测试隔离规范

1. **生产路径 patch**：fixture 必须用 `tmp_path` 隔离生产路径，禁止直接读写生产文件
2. **测试数据可识别**：带 `test_fixture_` 前缀/`__test__` 后缀
3. **patch 验证**：fixture 加载后 `assert not os.path.exists(production_path)` 验证
4. **遍历 sys.modules**：禁止硬编码模块名列表，必须遍历 `sys.modules` 找所有持目标属性的模块
5. **importlib.import_module**：禁止 `__import__`（返回顶层包而非子模块）
6. **数据污染应急 5 步**：停止服务 → 删除污染文件 → 修复 conftest → 重跑测试 → 通知用户

## 14. Python 现代化规范

Python 3.10+ 项目必须：

1. **asyncio.create_task** 替代 `asyncio.get_event_loop().create_task`
2. **asyncio.get_running_loop** 替代 `asyncio.get_event_loop`（在协程内）
3. **dataclass 字段显式声明**，禁止 `getattr(obj, 'field', default)` 兜底
4. **模块级 import**，禁止函数内重复 import（除非解决循环依赖）
5. **CancelledError 传播**，用 `contextlib.suppress` 包裹
6. **类型注解现代语法**：`X | None` 替代 `Optional[X]`，`list[T]` 替代 `List[T]`

## 15. 前端三态反馈规范

所有用户主动触发的异步操作必须实现 **loading → success → error** 三态：

1. `message.loading` 返回 `hide` 函数，在 `then` 和 `catch` 分支都调用 `hide()`
2. 错误提示从 `err.response.data.detail` 提取后端返回的具体错误
3. loading 文案包含资源标识（如 ID 前 8 位）
4. 操作成功后触发数据刷新（`refresh()` / `refetch()`）
5. 禁止 `.catch(() => {})` 静默吞错误

## 16. 配置全链路生效验证

配置项从定义到消费必须全链路追踪：

1. `config.yaml` 新增字段
2. Config 类有字段
3. TaskConfig 注入
4. Worker/Module/方法参数中读取 `self.config.xxx`
5. 最终消费点（URL 构建/SQL 查询/阈值比较）有读取代码

**验证方法**：`grep` 每个配置项的字段名，确认从定义到最终消费点都有读取代码。

**禁止**：只注入到中间层就认为生效。

## 17. 修改-验证-部署闭环

1. Edit 后立即 `grep` 验证关键标志符存在
2. 修改错误文案后全局 `grep` 旧文案确保唯一来源
3. Python 修改后必须重启服务（禁止认为"修改即生效"）
4. 重启后验证端口监听 + 关键数据状态
5. `git stash` 前先 `git commit -m "WIP"` 保底

## 18. 跨前后端协同修复

跨端数据流问题必须前后端协同修复：

1. 检查前端调用 → 后端端点 → 数据源全链路
2. 禁止只改一边
3. 同步检查相关端点是否也有相同问题
4. 修复时同步清理死代码（只 set 不 read 的 state / 只 import 不调用的函数）

## 19. 死代码检测与清理

每次大版本（v4.x → v4.x+1）时主动检测：

1. `git log -p --all -S "<function_name>"` 查看历史变更
2. `grep -rn "<function_name>" src/ tests/` 确认无调用方
3. 在 PR/Commit 描述中标注"删除死代码 X"

**修复模式**：
- 找到调用方：恢复调用路径
- 改写为入口函数：将死代码改写为"统一同步入口"
- 直接删除：无任何依赖时

## 20. 失败诊断 dump 机制

关键选择器/数据提取失败时：

1. 自动 dump `page.content()` 到 `logs/<场景>_<id>_<timestamp>.html`
2. `logger.warning` 记录 dump 路径
3. dump 用 `try/except` 包裹不阻塞主流程
4. dump 是「事后取证」不是「在线恢复」
5. 禁止依赖 dump 结果做运行时决策
6. 禁止 dump 敏感数据（cookie/auth header）

---

# 工作流元规范（Workflow Meta-Rules，21-24）

> 以下 4 条元规范从「四维度复盘方法论」提炼，定义了 4 类高频工作流的通用判断逻辑。详细配置节点与适用/不适用场景见 [`docs/standards/四维度复盘方法论与历史教训集成.md`](../../../../docs/standards/四维度复盘方法论与历史教训集成.md)。
>
> 命名空间与配置驱动：所有参数（critical_path_patterns / failure_threshold / resource_holder_patterns / single_source_of_truth）均在 `config.yaml` 对应节点管理，禁止硬编码。

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

## 24. 跨组件/跨源状态同步（适用于多源/多链路场景）

> v4.29 扩展：原 #24 仅覆盖前端跨组件同步，现扩展为「前端跨组件 + 后端跨源」双场景，新增「后端内部双源同步」约束。

复杂前端应用（多组件共享同一份数据）+ 多 Tab / 多路由 + 配置变更实时生效的场景，以及后端内部存在多个数据源（YAML/keyring/EventRow/业务表/缓存）的场景必须满足：

### 24-A 前端跨组件同步

1. **单一可信源**：后端 `GET /api/xxx` 是前端唯一数据源，**禁止**前端 `usePersistentState` 重复持久化
2. **统一入口**：所有写入路径必须通过 `useXxxStore().setXxx(newData)` 集中入口，**禁止**各组件独立 `setState`
3. **统一 refetch**：API 调用后必须 `refetch()` 而非推断新状态（避免乐观更新与后端实际不一致）
4. **跨进程同步**：子进程状态变更必须 SSE 推送，**禁止**前端用 TTL 缓存兜底

### 24-B 后端内部跨源同步 🆕v4.29

后端内部存在多个数据源（YAML/keyring/EventRow/业务表/缓存/浏览器内存）时必须满足：

1. **源识别**：新增状态字段时必须识别归属类别并登记到 `config.yaml#state_sync.backend_internal_sources` 源对清单：
   | 源对 | 典型场景 | 同步方向 |
   |---|---|---|
   | YAML ↔ keyring | 凭据（DingTalk/ServerChan/Bark token） | YAML 启动时同步到 keyring |
   | EventRow ↔ 业务表 | KPI 统计（抢单成功率/推送失败率） | 业务表为可信源，EventRow 仅作聚合 |
   | 健康检查 ↔ Worker 实测 | Cookie 层状态 | Worker 实测优先，健康检查兜底 |
   | Cookie JSON ↔ 浏览器内存 | Cookie 层级管理 | 浏览器内存兜底回填 JSON |
   | 配置缓存 ↔ 原始配置 | AppConfig 单例 | 原始配置变更后必须 invalidate 缓存 |

2. **同步时机**：
   - **启动时同步**：`_on_startup` 中调用 `_sync_xxx()`（如 `_sync_yaml_credentials_to_keyring`）
   - **写入时同步**：业务表写入后同步写 EventRow（如 NotifierHub 推送后写 `type='notify'` 事件）
   - **失效时同步**：Worker 检测到失效（如 RGV587_ERROR）必须调用 `invalidate_layer` 同步到健康检查
   - **读取时兜底**：JSON 缺失时从浏览器内存兜底回填（如 `CookieStore.upsert_cookie_values`）

3. **同步方向约束**：
   - 业务表 → EventRow 单向（EventRow 不得反向写业务表）
   - 原始配置 → 配置缓存单向（缓存不得反向写原始配置）
   - 浏览器内存 → JSON 单向回填（JSON 不得反向写浏览器内存）
   - YAML → keyring 启动时单向（keyring 不得反向写 YAML）

4. **禁止**：
   - 多个源独立读写无同步机制（如 YAML 凭据写后 keyring 未同步，导致通知"凭据未找到"被静默跳过）
   - 健康检查与 Worker 实测使用不同判定标准（如健康检查看 cookie 存在，Worker 看 RGV587_ERROR）
   - EventRow 写入 `type='eval.passed'` 但业务表只查 `type='eval.scored'`，导致 KPI 统计 0

**关键约束**：
- 后端 `single_source_of_truth` 列表中的 API 返回值是前端唯一可信源
- `forbid_persistent_state_for` 列表中的字段禁止前端 `usePersistentState` 重复持久化
- 跨进程状态变更（`sse_push_required_for`）必须 SSE 推送，`ttl_grace_seconds: 0` 即禁止 TTL 兜底
- 后端 `backend_internal_sources` 列表中的源对必须有显式同步代码（启动/写入/失效/读取任一时机）

**判断信号**：
- 前端：`grep "usePersistentState" <file>` 但该字段在后端有 `GET /api/xxx` → 视为违规
- 前端：多个组件独立 `useEffect(() => fetch(...), [])` 拉取同一份数据 → 视为违规
- 前端：`setTimeout(refresh, 30000)` 作为跨进程状态同步方案 → 视为违规
- 后端：`grep "keyring" <file>` 与 `grep "yaml" <file>` 同一凭据出现两处但无 `_sync_` 函数 → 视为违规
- 后端：`grep "EventRow" <file>` 写入但业务表查询条件不匹配 → 视为违规
- 后端：健康检查函数与 Worker 函数对同一状态使用不同判定逻辑 → 视为违规
- 后端：`grep "json.load" <file>` 与 `grep "browser.cookies" <file>` 同一 cookie 出现两处但无回填代码 → 视为违规

**适用**：
- 前端：复杂前端应用（多组件共享同一份数据）/ 多 Tab / 多路由场景 / 配置变更实时生效
- 后端：YAML/keyring/EventRow/业务表/缓存/浏览器内存等多源场景

**不适用**：
- 前端：简单组件树（1-2 层 props drilling 即可）/ 服务端渲染场景 / 纯 UI 偏好（主题色、视图模式）→ 纯 UI 偏好应用 `usePersistentState`（参考 meta-rule #7）
- 后端：单一数据源（如纯 DB 查询无缓存）/ 一次性脚本 / 性能 hot path（同步开销不可接受）

**历史教训**：
- 前端：用户反馈"功能正常但状态显示失效"（30 秒才恢复），根因：子进程登录后只更新自己的内存缓存，主进程读时取到 TTL 内的旧"失效"状态，前端 `LayerStatusBadge` 仅依据 `valid: boolean` 显示（无"未检测"区分），三层叠加导致用户体感"明明能跑却一直报错"
- 后端：DingTalk 通知不发送，根因：YAML 中保存了 webhook 凭据但 `secrets.py` 的 KEY 常量名与 YAML 字段名不一致，启动时未调用 `_sync_yaml_credentials_to_keyring()`，keyring 中无凭据导致 DingTalk 渠道被静默跳过
- 后端：抢单成功率/推送失败率恒为 0%，根因：`business_kpi.py` 查询 `EventRow` 用 `type='paid'/'confirmed'`，但 NotifierHub 实际写入 `type='notify'`，且 NotifierHub 未写 EventRow；多源不一致导致 KPI 统计分母为 0
- 后端：健康检查显示 cookie 未过期但 Worker 报 RGV587_ERROR，根因：健康检查看 cookie 存在 + identity 层 validity，Worker 看 API 实际响应 RGV587_ERROR，两套判定标准未同步

---

# 数据契约与时序元规范（25-30）🆕v4.30.0

> 以下 6 条元规范从 2026-06 至 2026-07 期间修复的批量任务断路器/启动钩子/日期时间/多源同步/错误传递/关键字管理 6 类问题中提炼，定义为「数据契约与时序」维度的通用判断逻辑。
>
> 命名空间与配置驱动：所有阈值（`fail_pause_threshold`/`critical_path_patterns`/`timezone_strategy`/`pending_marker_dir`/`error_code_enum`/`business_keyword_set`）均在 `config.yaml` 对应节点管理，禁止硬编码。

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

## 27. datetime 统一时区策略（naive ↔ aware 混用防护）

> 与 #23 资源生命周期的区别：#23 关注「资源实例」的 GC 与 cleanup，本条关注「时间值」的时区属性对齐。

涉及跨时区/跨进程/跨服务的 `datetime` 算术与序列化必须满足三规则：

1. **存储一律 UTC**：`datetime.now(timezone.utc)` 或 `datetime.utcnow()`，禁止使用本地时区存储
2. **算术前显式 unify tzinfo**：
   - 与 `row.created_at`（DB 读出的 naive）相减 → `_utcnow().replace(tzinfo=None) - row.created_at`
   - 与前端传来的 ISO 字符串 → `datetime.fromisoformat(iso_str).astimezone(timezone.utc)`
3. **序列化时显式标注**：`to_iso_string(aware_dt)` 输出带时区的 ISO 8601；禁止 `aware_dt.isoformat()[:19]` 切片丢失时区
4. **前端渲染契约**（与 F-REVIEW-DATETIME-RENDER-CONTRACT 对应）：前端用 `new Date(isoStr).toLocaleString()` 解析，禁止字符串方法拼接

**关键约束**：
- `grep "\.replace(tzinfo=None)" <file>` 必须配合 `_utcnow()` 或 `datetime.now(timezone.utc)` 出现 → 视为合规
- `grep "datetime.now()" <file>` 无 `tzinfo` 参数 → 视为违规（应用 `datetime.now(timezone.utc)`）
- DB 列定义禁止 `TIMESTAMP WITH TIME ZONE` 与 `TIMESTAMP WITHOUT TIME ZONE` 混用（SQLite 默认无时区，但 ORM 读写约定须统一）

**判断信号**：
- `grep "datetime.now()" <file>` 无 `tzinfo` → 视为违规
- `grep "datetime.utcnow()" <file>` → 视为**反模式**（Python 3.12+ 弃用，应用 `datetime.now(timezone.utc)`）
- `grep "\.isoformat()\[:19\]\|isoformat().*replace.*T.*Z" <file>` → 视为序列化不规范

**适用**：所有 `created_at` / `updated_at` / `expires_at` / `lastCheckedAt` / `lastRunAt` 字段的算术运算、跨服务时间比较、ISO 序列化。
**不适用**：纯展示（前端用 `dayjs` 解析）、同函数内的 local variable 计算、纯日期不含时间（`date.today()`）。

**历史教训**：`repo_chatbot.py:478` 报 `TypeError: can't subtract offset-naive and offset-aware datetimes`：`datetime.utcnow() - row.created_at`，其中 `row.created_at` 是 SQLAlchemy 从 SQLite 读出的 naive datetime。修复：用 `_utcnow().replace(tzinfo=None) - row.created_at` 统一为 naive。同一问题在 `api_orders.py:57` 复现，确认是项目级模式问题。

## 28. 跨进程/跨组件状态同步六步法

> 与 #24 跨组件/跨源状态同步的区别：#24 聚焦「多源读写一致性」（如 YAML ↔ keyring），本条聚焦**写入端 + 同步调度器 + 读取端 + 启动检查**四方的全链路协作。

`config.yaml#state_sync.backend_internal_sources` 或 `frontend_pending_markers` 列表中的状态需要多源写入时（如 Cookie 多层管理、配置变更广播），必须满足六步：

1. **写端**：业务变更后写状态 + 写 `pending_marker`（如 `data/markers/cookie_refresh_<user_id>_<timestamp>.json`）
2. **同步端**：独立调度器（`cookie_sync_scheduler.py`）扫描 `pending_marker_dir` 执行同步
3. **读端**：仅读最新状态，不读 marker（marker 仅作同步信号）
4. **启动时**：`_on_startup` 检查 `pending_marker_dir` 中是否有未处理 marker，有则强制触发全量同步
5. **异常时**：保留 marker 不删除，下次重试（成功后才 `unlink`）
6. **配置**：同步开关、间隔、批次大小均通过 `config.yaml#state_sync` 节点管理

**关键约束**：
- `grep "pending_marker\|write_marker" <file>` 写端与 `grep "scan_marker\|process_marker" <file>` 同步端必须配对存在
- 启动函数匹配 `critical_path_patterns` → 必须含 `process_pending_markers()` 调用
- 失败重试最多 N 次（`max_retry_count`，默认 5）后告警，不无限重试

**判断信号**：
- `grep "write_marker" <file>` 但无 `scan_marker` 同步器 → 视为违规（marker 永远不会被消费）
- 启动函数无 `process_pending_markers` 但有 marker 写入端 → 视为违规（重启时积压 marker 丢失）
- `grep "os.unlink\|os.remove.*marker" <file>` 在 try 块内但无异常分支 → 视为违规（失败时 marker 丢失）

**适用**：Cookie 多层同步（JSON ↔ 浏览器内存 ↔ 业务表）、配置变更广播、跨 Tab 状态共享、用户偏好同步。
**不适用**：单写单读的临时状态、纯 UI 状态、性能 hot path（同步开销不可接受）、无跨进程边界的纯函数计算。

**历史教训**：Cookie 自愈系统（v4.32 优化）涉及 3 个写端（`auth_helper.py` / `browser_login.py` / 外部 API 调用）与 1 个同步器（`cookie_sync_scheduler.py`）。修复前：写端无 marker → 同步器无法被触发；写端有 marker 但启动时不检查 → 重启时积压 marker 永久丢失。修复：补全 6 步后，Cookie 自愈成功率从 65% 提升到 92%。

## 29. 前端错误按 error_code 分支（禁止 substring 判断）

> 与 F-REVIEW-ERROR-CODE-BRANCH（frontend 维度 25）对应，本条是后端 + 前端协同的**契约级**元规范。

所有展示后端错误的 UI 组件 + 后端错误响应必须满足：

1. **后端错误响应统一结构**：`{ "error_code": "<reason>", "user_message": "<人类可读>", "detail": "<技术细节>" }`，其中 `error_code` 来自 `config.yaml#failure_reason_propagation.reason_enum` 枚举
2. **前端 switch 分支**：UI 组件用 `switch (err.error_code) { case 'token_expired': ...; case 'anti_crawler': ...; default: ... }` 匹配枚举
3. **禁止 substring 判断**：`if (msg.includes('expired'))` 类反模式禁止（文案变更即失效）
4. **常量集中管理**：前端在 `frontend/src/constants/errorCode.ts` 定义 `ErrorCode` 联合类型与展示文案映射，与后端 `reason_enum` 一一对应
5. **未知 error_code**：降级为通用错误 + `logger.warn` 记录 + 触发运营补登记

**关键约束**：
- 后端响应缺 `error_code` 字段 → 视为**必修 P0 缺陷**（前端无法分支）
- 前端 `if (err.message.includes(...))` → 视为违规（substring 反模式）
- 前端常量文件缺失 `ErrorCode` 类型与后端 `reason_enum` 对应 → 视为**契约不一致**

**判断信号**：
- 后端 `grep "raise HTTPException" <file>` 无 `error_code` 字段 → 视为违规
- 前端 `grep "if\\s*\\(.*\\.message\\.(includes|indexOf|search|match)" <file>` → 视为违规
- 前端 `grep "constants/errorCode\\|ErrorCode =" <file>` 缺对应枚举值 → 视为契约不一致

**适用**：所有展示后端错误的 UI 组件（错误提示/重试按钮/跳转登录）、所有后端 4xx/5xx 响应（除 401/440/441 走认证拦截器外）。
**不适用**：开发环境 `console.error`、本地输入校验（Zod/yup）、HTTP 5xx 网络层错误（统一 toast"网络异常"）。

**历史教训**：多个前端组件用 `if (err.message.includes('expired'))` 判断 Cookie 过期 → 后端文案从「登录已过期」改为「会话已失效」后，所有页面判断失效，统一显示「未知错误」。修复：建立前后端 `error_code` 契约，前端 `switch` 分支，后端响应携带标准化 `error_code` 字段。

## 30. 业务关键字常量集中管理

> 与 F-REVIEW-BUSINESS-KEYWORD-CENTRALIZATION（frontend 维度 27）对应，本条覆盖后端 + 前端 + 配置 + 文档的**全栈关键字管理**。

业务关键字（已售、已删除、宝贝不存在、登录已过期、网络异常等需正则匹配/includes 判断的字符串）必须满足：

1. **集中位置**：
   - 后端：`config.yaml#business_keywords.<category>`（如 `sold` / `deleted` / `error_phrases`）
   - 前端：`frontend/src/constants/businessKeywords.ts`（如 `SOLD_KEYWORDS` / `DELETED_KEYWORDS` / `ERROR_PHRASES`）
2. **禁止散落**：业务代码中禁止硬编码关键字字符串（`if ('已售' in text）` → 应读 `config['business_keywords']['sold']`）
3. **配套版本号**：新增关键字需新增 `keyword_id`（如 `KW-SOLD-001`），用于追踪「哪条规则误判/漏判」
4. **配套测试**：每个关键字集合配单元测试（`test_business_keywords.py`）断言「新增商品文案 → 关键字集合应包含」
5. **同步约束**：前后端关键字集合**必须保持等价**（如后端 `sold` 含「卖掉了」，前端 `SOLD_KEYWORDS` 也必须含「卖掉了」），不一致 → 视为**契约不一致**

**关键约束**：
- `grep "['\"](已售|已删除|宝贝不存在|卖掉了|已售罄)['\"]" src/xianyu_hunter/` → 视为硬编码（应从 config 读）
- 业务代码 `grep "if.*['\"].*['\"].*in.*text\|if.*['\"].*['\"].*in.*msg" <file>` → 视为可能硬编码
- 前后端关键字集合不一致 → CI 校验失败（`tests/test_keyword_consistency.py`）

**判断信号**：
- 后端 `grep "['\"](已售|已删除|宝贝不存在|卖掉了|已售罄|该宝贝不存在|商品不存在)['\"]" <file>` → 视为违规
- 前端 `grep "['\"](已售|已删除|宝贝不存在|卖掉了|已售罄)['\"]" <file>` → 视为违规
- `config.yaml` 与 `frontend/src/constants/businessKeywords.ts` 关键字集合不一致 → 视为契约不一致

**适用**：商品状态识别（已售/已删/在售）、错误提示文案匹配、风控标签识别、敏感词过滤、用户行为分类。
**不适用**：日志/异常消息中的自由文本（仅展示用）、配置文件中的连接信息（用户名/密码）、测试用例中的 mock 数据（应使用 fixture）。

**历史教训**：Cookie 自愈系统的 `sold` 关键字集合在 `auth_helper.py`、`browser_login.py`、`cookie_sync_scheduler.py` 三处独立维护，新增「宝贝走丢了」时只更新了 2 处，第 3 处漏更新导致「已售商品」被误判为「在售」继续抢单。修复：抽取到 `config.yaml#business_keywords.sold` 集中管理，前后端同步，配套一致性测试，问题彻底消除。

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

## 33. 注册式资源三件套契约 🆕v4.32

> 与 B-REVIEW-159（backend 注册完整性）/ F-REVIEW-117（frontend 注册完整性）对应。

任何"用户可点击/可导航"的功能入口必须保证 5 层齐备：菜单注册 → 路由注册 → 页面文件 → API wrapper → 后端 endpoint。任一层缺失视为 CRITICAL 缺陷。

1. **5 层契约模型**：L1 `config/menu_registry.yaml`（path/component/label/i18n_key）+ L2 `frontend/src/App.tsx`（`<Route path>` + lazy import）+ L3 `frontend/src/pages/<域>/index.tsx`（export default 组件）+ L4 `frontend/src/api/<域>.ts`（导出 xxxApi 对象）+ L5 `src/xianyu_hunter/web/routes/api_<域>.py`（APIRouter + include_router）
2. **自动化校验**：`python scripts/check_registration.py` 必须在 CI + pre-commit hook 中执行，退出码非 0 即 CRITICAL
3. **结构化输出**：校验结果同时输出表格（开发者读）+ JSON（CI 解析）
4. **豁免机制**：实验性 feature 用 `exemption_list` 临时豁免，必填 `expires` 过期时间
5. **配置驱动**：5 层路径、校验命令、豁免清单均从 `config.yaml#frontend_registration_completeness` 读取，禁止硬编码

**关键约束**：
- 菜单注册了 path 但 App.tsx 无对应 `<Route>` → 视为 CRITICAL（L1 有 L2 无）
- App.tsx 有 `<Route>` 但 `pages/<域>/index.tsx` 不存在 → 视为 CRITICAL（L2 有 L3 无）
- 页面 import api 模块但 `api/<域>.ts` 不存在 → 视为 CRITICAL（L3 有 L4 无）
- api wrapper 调用 endpoint 但后端无 `@router.<method>` → 视为 CRITICAL（L4 有 L5 无）

**判断信号**：
- `python scripts/check_registration.py` 退出码非 0 → 任意层缺失
- `grep -E "path: ['\"]/(notifications|orders|users)['\"]" config/menu_registry.yaml` 命中但 App.tsx 无对应 Route → L1 有 L2 无
- `Glob "frontend/src/pages/Notifications/index.tsx"` 失败但 App.tsx 有 `path="notifications"` 的 Route 引用 → L3 缺失
- `Glob "frontend/src/api/notifications.ts"` 失败但页面 import 该模块 → L4 缺失
- `grep -E "@router\.(get|post).*['\"\/]notifications" src/xianyu_hunter/web/routes/` 失败 → L5 缺失

**适用**：任何"用户可点击/可导航"的功能入口（菜单/侧边栏/按钮/Tab/Drawer/路由/Breadcrumb/通知订阅）。
**不适用**：纯静态页面、SSR（菜单由后端渲染）、单页 CLI、嵌入式设备、PWA 离线首页（单一 HTML 入口）、草稿/实验性 feature（用 exemption_list 豁免）。

**历史教训**：用户反馈"通知中心菜单点击无反应"。根因：`menu_registry.yaml` 注册了 `path=/notifications`，后端 `api_notifications.py` 完整实现接口，但前端 `App.tsx` 未注册路由、`pages/Notifications/` 不存在、`api/notifications.ts` 缺失。路由 fallback `<Route path="*" element={<Navigate to="/" replace />} />` 静默重定向回首页，用户体感"明明菜单点了几次，URL 都不变"。修复：新建 3 个前端文件 + App.tsx 注册路由。预防：加 #33 元规范 + `check_registration.py` 自动化脚本。

> 📖 详细 5 层契约模型、自动化校验脚本伪代码、配置节点定义见 [registration-completeness.md](registration-completeness.md)。

## 34. 修复前全链路根因扫描协议 🆕v4.32

> 与 B-REVIEW-160（backend 修复链路反查）/ F-REVIEW-118（frontend 根因最小数量）对应。

修复任何非平凡 bug（≥2 个文件参与 / 涉及状态变更 / 跨前后端 / 复盘过 ≥1 次）必须执行 5 步根因扫描协议，禁止"看到什么修什么"的单点修复。

1. **Step 1 列根因（≥3 个）**：必须列出至少 3 个独立根因，覆盖"用户层/接口层/数据层/配置层/历史层"5 维度，按"可能性 × 危害性"排序
2. **Step 2 排根因**：对每个根因用 1-2 个工具命令（Grep/Glob/Read/RunCommand）验证，记录"哪些被排除、哪些被确认"
3. **Step 3 修复**：只修改根因相关行（精确编辑原则），不顺手重构相邻代码，修复后立即 `git diff` 检查改动范围
4. **Step 4 反查**：修复后必须反查"同类 bug 的所有变体（横向同类）+ 用户操作路径其他拦截点（纵向全链）+ 配置/文档/部署中的体现（横向文档）"
5. **Step 5 防回归**：加 unit test + integration test + 更新 B/F-REVIEW 检查点 + 更新 `version-history.md` + 必要时更新 `project_memory.md` 硬约束

**关键约束**：
- PR 描述"修复"段不足 3 句 → 视为根因未充分展开（SUGGESTION）
- 修复后没有"反查同类 bug"段 → 视为 Step 4 缺失（SUGGESTION）
- `git diff` 涉及 ≥3 个无关文件 → 视为违反最小修改原则（WARNING）
- 新增逻辑但没加 unit test → 视为 Step 5 缺失（WARNING）
- 没有更新 `version-history.md` → 视为 Step 5 文档缺失（NIT）

**判断信号**：
- PR 描述 "修复" 段不足 3 句 → 根因未充分展开
- 修复后没有"反查同类 bug" 段 → Step 4 缺失
- `git diff` 涉及 ≥3 个无关文件 → 违反最小修改原则
- 新增逻辑但没加 unit test → Step 5 缺失
- 没有更新 `version-history.md` → Step 5 文档缺失

**适用**：修复任何非平凡 bug（≥2 个文件参与 / 涉及状态变更 / 跨前后端 / 复盘过 ≥1 次）。
**不适用**：纯样式 bug（颜色/间距/字号）、单行 typo（错别字/标点）、纯构建错误（依赖缺失/版本冲突）、安全漏洞补丁（时间敏感，先修后复盘，1 周内补复盘）、实验性 feature 试错。

**历史教训**：用户报告"通知中心菜单点击无反应"。朴素做法：直接去 App.tsx 加一行路由 → 完成。但用户还报告"配置中心"、"操作手册"、"实时日志"等 5 个菜单都"点击无反应"，单点修复只解决了 1/5。根因：6 类失败模式（相似 bug 重复 / 配置一致性盲区 / 跨语言契约模糊 / 熔断重试副作用 / 资源生命周期泄漏 / 空 except 吞异常）都源于"看到什么修什么"的单点修复思维。修复：建立 #34 5 步根因扫描协议，强制列 ≥3 根因 + 反查全链路。

> 📖 详细 5 步协议、6 类失败模式、配置节点定义见 [root-cause-protocol.md](root-cause-protocol.md)。

## 35. 前后端字段契约单一可信源 🆕v4.32

> 与 B-REVIEW-161（backend 字段权威源标记）/ F-REVIEW-119（frontend 字段派生来源标注）对应。

前后端分离架构中，后端 Pydantic 模型 + DB Row 字段定义为权威源，前端 `types.ts` 必须显式标注派生来源，禁止无标注手工复制。

1. **单一可信源原则**：后端 Pydantic + DB Row = 权威源；前端 types.ts 必须显式标注派生来源（后端文件路径 + 行号 + Pydantic 字段 + 变更日期 + 约束）
2. **三种实现路径**：A 后端生成前端 types（datamodel-code-generator）/ B 手工对齐 + 注释标注（本项目当前选 B）/ C 共享 zod schema
3. **5 点追踪清单**：字段变更（新增/重命名/类型调整）必须 5 点全部更新：DB Row 定义 → Pydantic 模型 → 后端返回路径（_row_to_dict 白名单）→ 前端 types.ts → 前端消费点（api 方法 + pages 渲染）
4. **命名约定**：backend snake_case / frontend snake_case 严格透传（禁止转 camelCase）/ url_path kebab-case / class_name PascalCase
5. **配置驱动**：实现路径、注释模板字段、5 点追踪清单、命名约定、类型映射白名单均从 `config.yaml#contract_single_source` 读取

**关键约束**：
- 前端 types.ts 字段 `xxxYyy`（驼峰）但后端 Pydantic 字段 `xxx_yyy`（snake_case）→ 视为 CRITICAL（命名漂移）
- 后端新增字段但前端 types.ts 未同步 → 视为 CRITICAL（字段缺失）
- 前端 types.ts 缺 `派生来源` 注释 → 视为 WARNING（手工对齐但未标注）
- 前端 types.ts 字段标 `?` 但后端 Pydantic 标 `...` → 视为 WARNING（可选性漂移）
- 前端直接访问后端返回的 dict 用 `data['xxxYyy']`（驼峰）→ 视为 CRITICAL（违反 snake_case 透传）

**判断信号**：
- `grep "派生来源" frontend/src/api/types.ts` 缺失 → 手工对齐未标注
- 后端 Pydantic 字段 `xxx_yyy` + 前端 types.ts 字段 `xxxYyy` → 命名漂移
- 后端新增字段，前端 types.ts 未同步 → 字段缺失
- 前端 types.ts 字段标 `?` 但后端 Pydantic 标 `...` → 可选性漂移
- 前端直接访问后端返回的 dict 用 `data['xxxYyy']`（驼峰）→ 违反 snake_case 透传

**适用**：前后端分离架构中，任何跨网络边界传输的数据结构（HTTP body / query / path）。
**不适用**：纯前端单页（无后端）、SSR（后端直接渲染）、monorepo + 共享 types（已 typegen）、第三方 API（不可控，用适配层 + 注释"外部 API 字段名"）、性能 hot path（极致优化，用结构化 schema + 手工断言）。

**历史教训**：前端 `NotificationItem` 接口字段 `read_at` 拼成 `readAt`（驼峰）→ 后端返回 `read_at`（snake_case）→ 前端永远读到 `undefined` → "标记已读"按钮点击无效。根因：前端 types.ts 手工复制 Pydantic 字段时自己转成了驼峰。修复：建立 #35 单一可信源原则 + 5 点追踪清单 + types.ts 注释模板。5 类典型漂移：命名风格漂移 / 大小写漂移 / 类型漂移 / 可选性漂移 / 枚举值漂移。

> 📖 详细单一可信源原则、三种实现路径、5 点追踪清单、配置节点定义、典型反模式见 [contract-single-source.md](contract-single-source.md)。

## 36. 规范沉淀门槛（防过度规范化）🆕v4.33

> 与 B-REVIEW-162（backend 规范立项前置计数）/ F-REVIEW-120（frontend 规范立项前置计数）对应。

新立编码规范（meta-rule / step / B-REVIEW / F-REVIEW）前必须满足"≥3 个相似 bug"门槛，避免单一 bug 立规范导致规范膨胀。安全漏洞/数据丢失/付费受损类 bug 可豁免，立即立规范。

1. **相似 bug 计数门槛**：同一根因（非表象）在不同文件/模块出现 ≥3 次才可立规范，阈值从 `config.yaml#meta_rules_governance.sedimentation_threshold` 读取
2. **计数维度**：根因相同（如"datetime 时区不一致"）而非表象相同（如"TypeError"）；文件/模块不同（非同文件重复）；时间窗口 ≤ 6 个月（避免跨年代久远的 bug 凑数）
3. **例外豁免**：安全漏洞（如 token 泄露）、数据丢失（如 DB 迁移失败）、付费受损（如订单金额错误）可立即立规范，无需 ≥3 次
4. **experimental 标签机制**：未达门槛但希望预沉淀的规范可标 `experimental` 标签，1 季度后未再出现相似 bug 则废弃；达标后升级为正式规范
5. **配置驱动**：相似 bug 计数阈值、时间窗口、例外豁免类别、experimental 观察期均从 config 读取，禁止硬编码

**关键约束**：
- 单一 bug 立规范（无 experimental 标签）→ 视为违规（规范膨胀风险）
- experimental 标签超 1 季度未升级为正式 → 视为废弃候选（应清理）
- 例外豁免立规范但未标注豁免原因 → 视为不规范（无法审计）
- 计数阈值硬编码在代码中 → 视为违规（应从 config 读）

**判断信号**：
- `grep "experimental" meta-rules.md` 标签超 1 季度未升级 → 废弃候选
- 新立 meta-rule 但无"历史教训"段（无相似 bug 支撑）→ 视为可疑
- 新立 B-REVIEW/F-REVIEW 但无对应"历史教训" → 视为可疑
- `grep "豁免原因" meta-rules.md` 例外规范缺豁免说明 → 视为不规范

**适用**：所有新立编码规范（meta-rule / step / B-REVIEW / F-REVIEW）的立项前置检查。
**不适用**：紧急安全修复（先修后立规范，1 周内补立项）、配置项新增（不立规范，只加 config 节点）、文档修正（非规范变更）。

**历史教训**：v4.10 期间某次单一 typo（变量名拼错）触发立规范，新增 1 条 B-REVIEW 检查点，但后续 6 个月未再出现相似 typo。该 B-REVIEW 在审查中 0 命中，占比规范总数 1.5%，拉低审查效率。修复：建立 #36 门槛规则，单一 bug 用 experimental 标签预沉淀，1 季度后未复现则废弃。

## 37. 规范退化机制（防规范膨胀）🆕v4.33

> 与 B-REVIEW-163（backend 规范退化清理）/ F-REVIEW-121（frontend 规范退化清理）对应。

每季度统计各 step / B-REVIEW / F-REVIEW 在审查中的命中次数，利用率 < 3 次/季度则标记为"待合并"或"待废弃"，避免规范垃圾堆积拉低审查信噪比。安全类规范永不退化。

1. **利用率统计**：每季度末统计各 step / B-REVIEW / F-REVIEW 在审查报告中的命中次数，输出利用率排行榜
2. **退化阈值**：利用率 < `config.yaml#meta_rules_governance.degradation_threshold`（默认 3 次/季度）则标记为"待合并"或"待废弃"
3. **合并优先**：相似 step 优先合并（如 3 个 datetime 相关 step 合并为 1 个），废弃是最后手段
4. **废弃流程**：标记"待废弃" → 1 季度观察期（`config.yaml#meta_rules_governance.observation_period_quarters`，默认 1） → 确认无命中 → 废弃并移入 `version-history.md` 的 Deprecated 章节
5. **安全类豁免**：安全类规范（token 比较 / 加密 / 认证白名单等）永不退化，即使 0 命中也保留
6. **配置驱动**：退化阈值、观察期时长、安全类豁免清单均从 config 读取

**关键约束**：
- 利用率 < 阈值但未标记"待合并/待废弃" → 视为不规范（规范治理缺失）
- 废弃的 step/B-REVIEW 未移入 version-history.md 的 Deprecated 章节 → 视为不规范（历史记录缺失）
- 安全类规范被标记"待废弃" → 视为违规（安全规范永不退化）
- 退化阈值硬编码 → 视为违规（应从 config 读）

**判断信号**：
- `grep "待废弃" meta-rules.md` 标记超 1 季度未处理 → 废弃流程卡住
- `grep "Deprecated" version-history.md` 章节缺失 → 废弃记录不全
- 季度审查报告显示利用率 < 3 的规范未标记 → 退化机制未执行
- 安全类规范出现在"待废弃"列表 → 视为违规

**适用**：所有现有 step / B-REVIEW / F-REVIEW 的季度治理。
**不适用**：安全类规范（永不退化）、配置驱动类规范（依赖 config 存在，config 节点存在则规范保留）、meta-rule #1-35 的元规范（元规范是基础规则，不参与退化）。

**历史教训**：v4.0-v4.10 累积 30+ step，v4.20 季度审查发现其中 8 个 step 在 1 季度内 0 命中，占比 27%。这 8 个 step 拉低审查效率，且部分与后续新增 step 语义重叠。修复：建立 #37 退化机制，8 个 0 命中 step 中 5 个合并到相似 step、3 个移入 Deprecated 章节，规范总数从 30+ 精简到 22，审查信噪比提升 27%。

---

# 列表聚合与状态联动元规范（38-42）🆕v4.34.0

> 以下 5 条元规范从 2026-07 期间修复的「全局聚合列表过滤失效 / 列表交叉数据 N+1 查询 / 多字段联动开关语义模糊 / precheck 异常处理不规范 / 配置化阈值缺失兜底」5 类问题中提炼，定义为「列表聚合与状态联动」维度的通用判断逻辑。
>
> 命名空间与配置驱动：所有阈值（`global_aggregate_filter` / `cross_domain_inject` / `linked_switch_priority` / `precheck_structured_fields` / `config_fallback_defaults`）均在 `config.yaml` 对应节点管理，禁止硬编码。

## 38. 全局聚合任务级过滤（GLOBAL-AGGREGATE-TASK-FILTER）🆕v4.34

> 与 B-REVIEW-164（backend 列表聚合过滤维度）/ F-REVIEW-122（前端列表过滤透传）对应。

多任务共享的列表查询接口（无 `task_id` 参数的全局视图）必须按各任务的个体配置范围进行过滤，禁止只应用全局过滤而忽略任务级范围，导致越界数据被返回。

1. **全局视图与单任务视图区分**：列表查询接口必须区分「单任务视图」（显式 `task_id`）与「全局视图」（无 `task_id`），两者过滤逻辑不同
2. **全局视图任务级过滤**：全局视图必须遍历所有任务，对每条数据按其归属任务的个体配置（如价格范围）过滤，而非用全局默认范围过滤
3. **过滤函数抽取**：任务级过滤逻辑必须抽取为独立函数（如 `_filter_by_per_task_range`），便于复用与单测
4. **空范围处理**：任务无配置时使用全局默认范围兜底，禁止跳过过滤
5. **配置驱动**：过滤策略（per_task / global_only / hybrid）、默认范围兜底开关从 `config.yaml#global_aggregate_filter` 读取

**关键约束**：
- 全局视图缺任务级过滤分支 → 视为**必修 P0 缺陷**（数据越界）
- 任务级过滤逻辑硬编码在主循环（未抽取函数）→ 视为违规
- 任务无配置时跳过过滤（无兜底）→ 视为违规

**判断信号**：
- `grep "task_id.*None\|task_id.*is None" <file>` 但无 `_filter_by_per_task` / `_filter_by_task_range` 调用 → 视为违规
- `grep "def list_.*\(.*task_id.*\)" <file>` 缺全局视图分支 → 视为可疑
- 列表接口返回数据中存在超过任一任务配置上限的值 → 视为 P0

**适用**：多任务共享的列表查询接口（评估列表 / 仪表盘 / 商品列表 / 订单列表）、跨任务聚合视图、全局搜索。
**不适用**：单任务详情视图（task_id 显式传入，应用该任务范围）、统计聚合（无个体过滤需求）、管理后台超管视图（看全部数据）。

**历史教训**：用户反馈「最高价仍显示 ¥2,988.00」。根因：`evaluations_list.py` 在无 `task_id`（默认全局视图）时直接返回 `{min: None, max: None}` 不做任务级过滤，导致 task 价格上限 800 的商品也能查到 ¥2,988 的评估数据。修复：新增 `_filter_by_per_task_range` 函数，全局视图下按各任务个体价格范围过滤；`_load_sold_prices_from_links` 和 `_load_all_prices_from_items` 均调用此函数。

## 39. 列表交叉数据批量注入（LIST-CROSS-DOMAIN-INJECT）🆕v4.34

> 与 B-REVIEW-165（backend 列表 N+1 查询修复维度）/ F-REVIEW-123（前端列表数据合并展示）对应。

列表查询需要交叉注入其他数据源的数据（如评估列表注入捡漏价格、订单列表注入商品详情）时，必须采用批量查询 + TTL 缓存模式，禁止 N+1 单条查询导致接口性能退化。

1. **批量查询强制**：列表接口交叉其他数据源时必须用 `WHERE xxx IN (...)` 批量查询，禁止循环内单条查询
2. **TTL 缓存**：交叉数据查询结果必须按业务键（如 task_id / seller_id）缓存，TTL 从 `config.yaml#cross_domain_inject.cache_ttl_seconds` 读取
3. **单轮缓存**：单次 run_once / 单次请求内缓存，每轮重置（避免缓存陈旧）
4. **缺失降级**：交叉数据查询失败时降级为 `None` / 空对象，禁止阻断主列表返回
5. **配置驱动**：缓存开关、TTL、批量查询分块大小（避免 IN 子句过长）从 config 读取

**关键约束**：
- 循环内单条查询（`for item in items: db.query(filter=item.id)`）→ 视为**必修 P0 缺陷**（N+1 查询）
- 缺失交叉数据时抛异常阻断主列表 → 视为违规（应降级为 None）
- 缓存 key 含时间戳或随机值（无复用性）→ 视为违规

**判断信号**：
- `grep "for.*in.*items:" <file>` 后跟 `db.query\|session.execute` 单条查询 → 视为 N+1 违规
- `grep "def list_.*\(.*\)" <file>` 缺 `IN \(.*\)` 批量查询 → 视为可疑
- 交叉数据查询无 `cache_ttl` / `_cache` / `lru_cache` → 视为不规范

**适用**：列表接口需要交叉其他数据源（评估列表 + 捡漏价格、订单列表 + 商品详情、商品列表 + 卖家信息、任务列表 + 最后执行状态）。
**不适用**：单条详情查询（无 N+1 风险）、TTL 不可接受的热路径（需实时数据）、列表数据量固定 ≤3 条（无性能问题）。

**历史教训**：评估列表显示「预估盈利」时，`_compute_sold_range` 在循环内对每个 task 单独查询已售价格，10 个任务触发 10 次 DB 查询，接口耗时从 200ms 升到 1.8s。修复：改为批量查询所有 task 的已售价格 + 5 分钟 TTL 缓存，接口耗时降到 250ms。

## 40. 多字段联动开关范式（MULTI-FIELD-LINKED-SWITCH）🆕v4.34

> 与 B-REVIEW-166（backend 联动开关优先级矩阵）/ F-REVIEW-124（前端联动开关 UI 状态）对应。

多个业务字段叠加生效（如 `mode` 主开关 + `notify_bargain_only` / `auto_buy_bargain_only` 子过滤器）时，必须明确「主开关 → 过滤器」优先级矩阵，主开关失效时子过滤器自动禁用，禁止语义冲突的组合。

1. **优先级矩阵显式声明**：联动字段必须在文档/注释中显式声明「主开关 → 过滤器」优先级矩阵，列出所有合法组合
2. **主开关失效时子过滤器禁用**：主开关为 `notify`（仅通知）时 `auto_buy_*` 过滤器必须自动禁用 + UI 标识不可用
3. **PATCH 三态语义**：PATCH 接口必须用 `exclude_unset=True` 区分「未传 / 传 null / 传值」三态，禁止 0/false 被误判为未传
4. **bool→int 存储**：DB 存储 BOOLEAN 字段时统一用 INTEGER(0/1)，与同类开关字段（如 `use_cron`）保持一致
5. **配置驱动**：优先级矩阵、禁用规则、字段映射从 `config.yaml#linked_switch_priority` 读取

**关键约束**：
- 联动字段无优先级矩阵文档 → 视为 WARNING（语义模糊）
- 主开关 notify 模式但 `auto_buy_*` 未禁用 → 视为 P1（语义冲突）
- PATCH 接口未用 `exclude_unset=True` → 视为违规（三态丢失）
- bool 字段存储为 STRING('true'/'false') → 视为违规（应 INTEGER 0/1）

**判断信号**：
- `grep "mode.*notify\|mode.*auto_buy" <file>` 但无优先级矩阵注释 → 视为可疑
- `grep "exclude_unset.*True\|exclude_unset=True" <file>` PATCH 接口缺此参数 → 视为违规
- `grep "notify_bargain_only\|auto_buy_bargain_only" <file>` 缺 `disabled={.*mode.*===.*notify}` → 视为前端 UI 不规范
- `grep "BOOLEAN\|String.*true.*false" <file>` DB schema 中 bool 字段非 INTEGER → 视为违规

**适用**：多字段叠加生效的业务开关（mode + 子过滤器、enabled + 子配置、auto_* + 限制条件）。
**不适用**：独立开关（无联动）、纯前端 UI 开关（无后端逻辑）、单一布尔开关（无组合语义）。

**历史教训**：任务配置含 `mode` + `notify_bargain_only` + `auto_buy_bargain_only` 三个字段，无优先级矩阵。用户反馈「mode=notify 但 auto_buy_bargain_only=true 是否会触发自动下单」语义模糊。修复：明确优先级矩阵（mode 是主开关，*_bargain_only 是过滤器；mode=notify 时 auto_buy_bargain_only 自动禁用 + UI Tag 标识），PATCH 接口用 `exclude_unset=True` 三态语义，bool→int 存储与 `use_cron` 一致。

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

## 42. 配置化阈值兜底范式（CONFIG-DRIVEN-THRESHOLD-FALLBACK）🆕v4.34

> 与 B-REVIEW-168（backend 配置兜底范式）/ F-REVIEW-126（前端配置缺失降级）对应。

从 `config.yaml` 读取的阈值/分位数/百分位必须有 `try/except` 兜底默认值，保证配置缺失、配置加载失败、配置类型错误时系统仍可运行，禁止"配置缺失即崩溃"。

1. **try/except 兜底强制**：所有从 config 读取的阈值必须用 `try/except` 包裹，失败时回退到代码内默认值
2. **默认值合理性**：默认值必须与配置模板（`config.example.yaml`）保持一致，禁止默认值与示例配置冲突
3. **失败降级日志**：兜底时必须 `logger.warning` 记录（不用 `logger.error`，避免污染告警），含字段名与回退值
4. **配置全链路验证**：新增配置项必须同步更新 `config.example.yaml` + Config 类字段 + 消费点 try/except
5. **配置驱动**：兜底开关、默认值表、降级日志级别从 `config.yaml#config_fallback_defaults` 读取

**关键约束**：
- 配置读取无 `try/except` 兜底 → 视为 P1（配置缺失即崩溃）
- 默认值与 `config.example.yaml` 不一致 → 视为违规
- 兜底时用 `logger.error` 触发告警 → 视为不规范（应 `logger.warning`）
- 新增配置项未更新 `config.example.yaml` → 视为违规（参考 meta-rule #16 全链路验证）

**判断信号**：
- `grep "get_config\(\)\.\w+\.\w+" <file>` 但无 `try.*except.*default` 包裹 → 视为可疑
- `grep "from.*yaml_config import get_config" <file>` 但同文件 `get_config()` 调用无 try/except → 视为违规
- `grep "logger\.error.*配置.*默认\|logger\.error.*fallback" <file>` → 视为不规范（应 warning）
- `config.example.yaml` 与 Config 类默认值 grep 不一致 → 视为违规

**适用**：从 config 读取的阈值/分位数/百分位/重试次数/超时秒数/批次大小等可调参数。
**不适用**：强制必需配置（如数据库路径、认证密钥，缺失即不可启动，应在启动校验时 `raise` 而非兜底）、安全相关配置（如 token 比较方式，不可兜底）、协议固定值（不可配置）。

**历史教训**：`_compute_sold_range` 中 P10 分位数从配置读取 `bargain_percentile = get_config().bargain_price.percentile`，但用户 `config.yaml` 是旧版本无此字段，启动时未报错但调用时 `AttributeError: 'BargainPriceConfig' object has no attribute 'percentile'`，整个价格策略接口崩溃。修复：改为 `try: bargain_percentile = get_config().bargain_price.percentile; except Exception: bargain_percentile = 0.10` 兜底默认值，并 `logger.warning` 记录。后续推广为 #42 范式，所有配置读取必须有兜底。

> 📖 详细配置兜底范式、默认值表、降级日志模板见 [config-driven.md](../assets/guides/coding-rules/config-driven.md) step 188。

---

# 跨层契约与测试同步元规范（43-47）🆕v4.35.0

> 以下 5 条元规范从 2026-07-07 解决的「SEMI_AUTO 模式通知未触发确认 / EVAL_PASSED 事件三处发布点 task_mode 字段不对齐 / 前端 sheetRegistry 未注册新路由 + findSheetMeta 未剥离 query string / useSheetSync 丢失 query string / 历史测试 mock 类型不匹配 + keyring fallback + 接口签名变更未同步测试」5 类问题中提炼，定义为「跨层契约对齐与测试同步」维度的通用判断逻辑。
>
> 命名空间与配置驱动：所有参数（`event_multi_emit_alignment` / `frontend_route_registration` / `external_callback_query_retention` / `test_synchronization` / `external_dependency_isolation`）均在 `config.yaml` 对应节点管理，禁止硬编码。所有路径/模块名/字段名通过角色抽象描述（如「事件发布点」「路由注册表」「query string 字段名」），不硬编码具体文件名。

## 43. 事件多发布点字段对齐（EVENT-MULTI-EMIT-ALIGN）🆕v4.35

> 与 B-REVIEW-173（backend 事件多发布点字段对齐审查，v4.35 待落地）/ F-REVIEW-131（前端消费方分支对齐审查，v4.39 待落地）对应。

业务事件在多个层（worker / 服务 / 路由 / 通知模板）有发布点时，每处发布点必须保持事件 payload 字段集与字段语义一致，禁止某处补齐某字段而其他发布点遗漏，导致下游消费方按字段分支失败。

1. **多发布点识别**：grep 事件类型字符串（如 `EVAL_PASSED` / `task.started`），识别所有发布点（worker / service / route / template / SSE 推送器）
2. **字段对齐**：每处发布点的 payload 必须包含配置中声明的「必传字段集」（如 `task_mode` / `user_id` / `trace_id`），缺一视为违规
3. **重构同步**：当某处发布点新增字段时，必须 grep 所有发布点逐一同步
4. **下游消费对齐**：消费方按字段分支（如 `if payload.task_mode == SEMI_AUTO`）时，必须存在 fallback 分支（`else` / `default`），避免字段缺失时静默走默认路径
5. **配置驱动**：发布点清单、必传字段集、字段语义说明从 `config.yaml#event_multi_emit_alignment` 读取

**关键约束**：
- 业务事件有 ≥2 处发布点但 payload 字段集不一致 → 视为 **必修 P0 缺陷**（下游分支失效）
- 新增字段但未 grep 同步所有发布点 → 视为违规
- 消费方按字段分支但无 fallback → 视为违规（字段缺失时静默默认）
- 发布点清单硬编码在代码中（如 `["worker.py", "collection_service.py"]`）→ 视为违规（应从 config 读）

**判断信号**：
- `grep "<event_type>" src/` 命中 ≥2 处，每处上下文 `grep "<required_field>"` 不全命中 → 字段未对齐
- `grep "<event_type>.*emit\|publish.*<event_type>"` 多处但 `payload = {` 后字段数不同 → 字段集不一致
- 消费方 `if payload.<field> == X` 但无 `else` → fallback 缺失
- 新增字段后 git diff 显示发布点未同步更新 → 同步缺失

**适用**：业务事件在多层有发布点的场景（worker → service → route → 通知模板）；事件 payload 含分支决策字段（如 `task_mode` / `severity` / `source`）；事件需多消费方订阅（SSE 推送 + 通知中心 + Dashboard 刷新）。
**不适用**：单一发布点的内部事件（一处发布无需对齐）；纯调试日志事件（不产生下游副作用）；一次性脚本事件（无长期维护成本）。

**历史教训**：SEMI_AUTO 模式任务通过评估后，`worker.py` 的 `EVAL_PASSED` 发布点 payload 含 `task_mode` 字段，但 `collection_service.py` 与 `evaluations_common.py` 两处发布点未携带 `task_mode`，导致通知模板层无法按 `task_mode` 渲染"确认抢单"链接，SEMI_AUTO 退化为 NOTIFY_ONLY，从未触发确认动作。修复：grep 所有 EVAL_PASSED 发布点逐一补齐 `task_mode`，并建立 #43 强制对齐规则。

## 44. 前端路由三重注册同步（ROUTE-TRIPLE-REGISTRATION）🆕v4.35

> 与 B-REVIEW-174（backend 路由清单与前端注册对齐，v4.35 待落地）/ F-REVIEW-132（前端路由三重注册审查，v4.39 待落地）对应。

新增前端路由（含 SheetWorkspace 多页签应用）必须在「路由声明层 / 多页签注册层 / URL 同步 Hook 层」三处同步注册，禁止只注册一层导致「URL 变了内容不变」或「内容变了 URL 不变」的 UI 错乱。

1. **三重注册清单**：新增路由必须同步注册：
   - L1 路由声明层（如 `App.tsx` 的 `<Route>`）
   - L2 多页签注册层（如 `SheetWorkspace/sheetRegistry.tsx` 的 path → component 映射）
   - L3 URL 同步 Hook 层（如 `useSheetSync.ts` 的 location → sheet 同步逻辑）
2. **query string 保留**：路由携带 query string（如 `?task_id=xxx`）时，L3 Hook 必须 `location.pathname + location.search` 拼接，禁止只取 pathname 丢 query string
3. **路径匹配剥离**：L2 注册层的 `findSheetMeta` 函数必须先剥离 query string 与 hash 再匹配，避免 `?xxx` 干扰精确匹配
4. **配置驱动**：三重注册清单、query string 保留路由列表、路径匹配剥离规则从 `config.yaml#frontend_route_registration` 读取

**关键约束**：
- 新增路由只注册 L1（App.tsx）但未注册 L2（sheetRegistry）→ SheetWorkspace 显示"未打开任何页面"
- L3 Hook 只取 `location.pathname` 不取 `location.search` → query string 丢失，下游组件读不到参数
- L2 `findSheetMeta` 直接用原始 path 匹配（含 query string）→ 精确匹配失败
- 注册清单硬编码在代码中（如 `["/confirm-buy", "/tasks"]`）→ 视为违规（应从 config 读）

**判断信号**：
- `git diff` 显示新增 `<Route path="/<route_name>"` 但同 PR 内 `sheetRegistry` 无对应条目 → L2 同步缺失
- `grep "location.pathname" frontend/src/hooks/useSheetSync.ts` 但无 `location.search` → query string 丢失
- `grep "findSheetMeta" frontend/src/components/SheetWorkspace/` 函数体内无 `split('?')[0]` → 剥离缺失
- 新增路由后用户反馈"URL 变了内容不变"或"内容变了 URL 不变" → 三重同步失败

**适用**：SheetWorkspace 多页签应用中的新增路由；从外部链接（通知 / 邮件 / 二维码）回链进入应用的路由（依赖 query string 传参）；任何 path → component → URL 三层联动的路由系统。
**不适用**：独立路由（如 `/login` 不进入 SheetWorkspace）；纯 Hash 路由（query string 不在 pathname 中）；纯服务端渲染（无前端路由层）。

**历史教训**：新增 `/confirm-buy` 路由（SEMI_AUTO 通知回链）只在 `App.tsx` 注册，未同步到 `sheetRegistry`，导致用户点击通知后 URL 变为 `/confirm-buy` 但页面显示"未打开任何页面，请从左侧菜单选择"。修复：在 sheetRegistry 新增条目 + 修改 `findSheetMeta` 剥离 query string + 修改 `useSheetSync` 保留 query string，三重同步后页面正常渲染。

## 45. 外部回链 query string 保留（QUERY-STRING-RETAIN）🆕v4.35

> 与 B-REVIEW-175（backend 回链 URL 构造审查，v4.35 待落地）/ F-REVIEW-133（前端 query string 保留审查，v4.39 待落地）对应。

从外部链接（通知 / 邮件 / 二维码 / 公网 URL）回链进入应用的路由，必须完整保留 URL 中的 query string（如 `?task_id=xxx&item_id=yyy&error_code=zzz`），禁止 URL 同步 Hook 只取 pathname 丢失 query string，导致下游组件读不到业务参数。

1. **回链路由识别**：从 `config.yaml#external_callback_query_retention.callback_routes` 读取需要保留 query string 的路由列表
2. **URL 拼接规则**：URL 同步 Hook 在计算「当前路径」时必须 `location.pathname + location.search`，依赖数组必须包含 `location.search`
3. **路径匹配剥离**：路径查找函数（如 `findSheetMeta`）必须先 `path.split('?')[0].split('#')[0]` 剥离 query string 与 hash 再匹配
4. **下游消费契约**：回链页面组件必须能从 `useSearchParams` / `useLocation().search` 读取 query string 参数
5. **配置驱动**：回链路由列表、query string 字段名清单、剥离规则从 config 读取

**关键约束**：
- URL 同步 Hook 依赖数组缺 `location.search` → 视为违规（query string 变化不触发同步）
- 路径查找函数未剥离 query string 直接匹配 → 视为违规（带 `?xxx` 的 path 无法精确匹配）
- 回链路由列表硬编码在 Hook 中 → 视为违规（应从 config 读）
- 回链页面组件无法从 `useSearchParams` 读到 query string → 配置契约破裂

**判断信号**：
- `grep "location.pathname" frontend/src/hooks/` 但同函数无 `location.search` → query string 丢失
- `grep "findSheetMeta\|findRouteMeta" frontend/src/` 函数体内无 `split('?')` → 剥离缺失
- `grep "useEffect.*location.pathname" frontend/src/hooks/useSheetSync.ts` 依赖数组无 `location.search` → 依赖不全
- 用户反馈"从通知点击进入页面后参数丢失" → query string 未保留

**适用**：从外部通知 / 邮件 / 二维码 / 公网 URL 回链进入应用的路由（依赖 query string 传 task_id / item_id / error_code / token）；任何 URL 同步 Hook 处理带参数路由的场景。
**不适用**：纯内部导航（用户点击菜单，无 query string）；纯 `:param` 路径参数路由（参数在 pathname 中）；纯 Hash 路由（query string 不在 pathname 中）；纯服务端路由（无前端 Hook 层）。

**历史教训**：`/confirm-buy?task_id=xxx&item_id=yyy` 回链路由，`useSheetSync` 计算路径时只用 `location.pathname`，丢失 `?task_id=xxx`，导致 `ConfirmBuy` 组件读 `useSearchParams` 时 task_id 为 null，无法加载确认抢单数据。修复：path 改为 `location.pathname + location.search`，依赖数组加入 `location.search`，并建立 #45 强制保留规则。

## 46. 测试同步责任原则（TEST-SYNC-RESPONSIBILITY）🆕v4.35

> 与 B-REVIEW-176（backend 接口签名变更同步审查，v4.35 待落地）/ F-REVIEW-134（前端异步函数调用签名匹配审查，v4.39 待落地）对应。

后端接口签名变更（新增 / 删除 / 重命名参数）、异步同步重构（async → sync 或反之）、mock 字段集与生产 Pydantic 模型同步时，必须同步更新所有调用方测试，禁止「改了生产代码忘了改测试」导致测试失败或假阳性。

1. **签名变更同步**：方法签名新增参数后必须 grep 所有调用点（包括测试中的 mock 调用）确认传递新参数
2. **异步同步重构同步**：`async def` → `def` 或反之时，测试中的 `AsyncMock` ↔ `MagicMock` 必须同步切换
3. **mock 字段集同步**：测试 mock 数据必须与生产 Pydantic 模型字段集 1:1 对齐，禁止用 `as ModelType` 类型断言绕过完整性检查
4. **外部依赖隔离同步**：测试中依赖外部资源（keyring / env / 文件系统 / 网络）时必须 patch 为 None 或 mock，禁止依赖生产 fallback 导致测试不可重复
5. **配置驱动**：签名变更检查点、mock 类型映射表、外部依赖类型清单从 `config.yaml#test_synchronization` 读取

**关键约束**：
- 方法签名新增参数但测试调用未传新参数 → 视为违规（`TypeError: missing required positional argument`）
- 生产代码 `async def` 但测试用 `MagicMock`（或反之）→ 视为违规（mock 类型不匹配）
- mock 数据用 `as Item` / `as Task` 绕过字段检查 → 视为违规（与 B-REVIEW-TEST-MOCK-SYNC 一致）
- 测试依赖 keyring fallback → 视为违规（测试环境不可重复）
- 检查点清单硬编码在代码中 → 视为违规（应从 config 读）

**判断信号**：
- `git diff` 显示生产代码方法签名变更但同 PR 内 `tests/` 无对应修改 → 同步缺失
- `grep "AsyncMock" tests/` 但生产代码对应方法已改为 `def` → mock 类型不匹配
- `grep "as Item\b\|as Task\b\|as Order\b" tests/` → 类型断言绕过字段检查
- `grep "get_secret\|os.environ\.\[" tests/` 但无 `patch(..., return_value=None)` → 外部依赖未隔离
- 测试在 CI 通过但本地失败（或反之）→ 环境依赖问题

**适用**：后端接口签名重构（新增 / 删除 / 重命名参数）；async / await 重构（同步异步切换）；测试 mock 数据与生产 Pydantic 模型对齐；外部依赖（keyring / env / 文件系统 / 网络）测试隔离。
**不适用**：纯内部实现重构（不改变接口签名）；新增功能（不破坏现有测试）；一次性验证脚本（无长期维护成本）。

**历史教训**：`manual_takeover` 接口签名加了 `request` 参数（用于多用户隔离读取 `request.state.user_id`），但 `test_manual_takeover_lock.py` 未传 `request`，触发 `TypeError: missing 1 required positional argument: 'request'`。修复：创建 `mock_request = MagicMock()` 并设置 `mock_request.state.user_id = "default"` 后传入。同期 `worker.py` 重构为同步代码后 `test_dingtalk_notify_integration.py` 仍用 `AsyncMock` 导致断言失败，改为 `MagicMock` 后通过。建立 #46 强制同步规则。

## 47. 外部依赖隔离测试可重复性（EXTERNAL-DEP-ISOLATION）🆕v4.35

> 与 B-REVIEW-177（backend 外部依赖隔离审查，v4.35 待落地）/ F-REVIEW-135（前端 mock 类型与生产同步审查，v4.39 待落地）对应。

测试中依赖外部资源（keyring / 环境变量 / 文件系统 / 网络 / 系统 API）时必须显式 patch 为 None 或 mock，禁止依赖生产代码的 fallback 机制（如 keyring 不可用时回退到 env / yaml），避免测试环境与生产环境配置不一致导致测试不可重复（CI 通过本地失败或反之）。

1. **外部依赖清单识别**：从 `config.yaml#external_dependency_isolation.dependency_types` 读取外部依赖类型清单（keyring / env / file / network / system_api）
2. **patch 强制**：测试中调用任何外部依赖函数（如 `get_secret` / `os.environ[...]` / `Path(...).read_text()` / `httpx.get`）必须 `with patch(..., return_value=None)` 或 `MagicMock()` 显式隔离
3. **fallback 禁用**：禁止依赖生产代码的 fallback（如 `secret = get_secret(name) or os.environ.get(name) or read_from_yaml(name)`），测试中必须 patch 全部 3 层 fallback
4. **可重复性验证**：测试在「无外部依赖」环境下（如 Docker 容器无 keyring / 无 env / 无网络）必须仍能通过
5. **配置驱动**：依赖类型清单、隔离策略映射表、fallback 层数从 config 读取

**关键约束**：
- 测试中调用 `get_secret` 但无 `patch("...get_secret", return_value=None)` → 视为违规
- 测试中 `os.environ["XXX"]` 但无 `monkeypatch.setenv` 或 `patch.dict(os.environ, ...)` → 视为违规
- 测试在 CI 通过但本地失败（或反之）→ 视为环境依赖问题
- 依赖类型清单硬编码在测试中 → 视为违规（应从 config 读）

**判断信号**：
- `grep "get_secret\|keyring\.get_password" tests/` 但同测试无 `patch` → keyring fallback 未隔离
- `grep "os\.environ\[" tests/` 但同测试无 `monkeypatch\.setenv\|patch\.dict` → env 依赖未隔离
- `grep "Path\([^)]*\)\.read_text\(\)\|open\([^)]*\)\.read\(\)" tests/` 但无 `tmp_path` fixture → 文件系统依赖未隔离
- `grep "httpx\.get\|requests\.get\|aiohttp\.ClientSession" tests/` 但无 `respx` / `responses` / `MagicMock` → 网络依赖未隔离
- 测试结果随环境变化（CI vs 本地 / Windows vs Linux）→ 环境依赖问题

**适用**：依赖 keyring / 环境变量 / 文件系统 / 网络 / 系统 API 的测试；CI/CD 需可重复的场景；跨平台测试（Windows / Linux / macOS）。
**不适用**：纯函数测试（无外部依赖）；使用 pytest fixture 已隔离的测试（fixture 内部已 patch）；一次性验证脚本（无长期维护成本）；集成测试（故意依赖真实外部资源）。

**历史教训**：`test_notifier_new_channels.py` 中 `DingTalkNotifier(webhook_url="...", secret="")` 测试期望 `secret=""` 时不发送请求，但生产代码 `get_secret` 在 keyring 不可用时 fallback 到 keyring 真实值（测试机已配置 dingtalk secret），导致 `secret=""` 但实际读到 keyring 中的 secret，触发真实钉钉请求，断言失败。修复：在两个测试函数中都加 `with patch("...dingtalk.get_secret", return_value=None):` 显式隔离。建立 #47 强制隔离规则。

> 📖 详细测试同步责任原则、签名变更检查点、mock 类型映射表、外部依赖隔离策略、配置节点定义见 [test-synchronization-and-isolation.md](test-synchronization-and-isolation.md)。

---

# 调度器运行时治理元规范（48-51）🆕v4.36.0

> 基于 2026-07-07 "任务管理自动执行逻辑审查"修复的 5 个问题（BatchRefreshScheduler 运行时禁用无效 / CookieSyncScheduler 无法运行时禁用 / scheduler.py 异常重试等待硬编码 300s / `_resume_cooldown` 字典内存泄漏 / Cron 模式无最小间隔校验），使用 Sequential Thinking 4 维度复盘法——成功步骤/不确定性与失败点/可抽象的固定流程与判断逻辑/适用场景与不适用场景，提炼 4 条新元规范。门槛校验：#48/#49/#50 各有 ≥3 个相似 bug 达标立正式规范，#51 仅 1 个相似 bug 按门槛规则 #36 标 experimental 标签预沉淀。

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

## 49. 时间参数配置化（TIME-PARAM-CONFIG-DRIVEN）🆕v4.36

> 与 B-REVIEW-179（backend 时间参数配置化审查）/ F-REVIEW-137（前端轮询间隔配置化审查）对应。

异常重试等待秒数、轮询间隔、超时秒数、冷却期等时间参数必须从 `config.yaml` 读取，禁止在代码中硬编码字面量数字（如 `time.sleep(300)` / `await asyncio.sleep(60)` / `timeout=30`）。配置类（Pydantic BaseModel）必须设 `ge`/`le` 边界值校验，读取时按 #42 配置化阈值兜底范式用 `try/except` 包裹提供默认值。

1. **时间参数清单识别**：从 `config.yaml#time_param_config_driven.param_types` 读取需配置化的时间参数类型清单（retry_wait / poll_interval / timeout / cooldown / backoff_base / max_backoff）
2. **配置读取强制**：所有 `time.sleep()` / `asyncio.sleep()` / `timeout=` / `wait_for(timeout=)` 的时间参数必须从 `get_config()` 读取，禁止字面量数字
3. **边界值校验**：Pydantic 配置类必须用 `Field(300, ge=10, le=3600)` 标注边界值，超出范围触发 ValidationError
4. **默认值兜底**：配置读取失败（如配置文件缺失/字段未定义）必须 `try/except` 兜底默认值（参考 #42 配置化阈值兜底范式），禁止配置缺失即崩溃
5. **配置驱动**：参数类型清单、边界值、默认值从 `config.yaml#time_param_config_driven` 节点管理

**关键约束**：
- `grep "time\.sleep\([0-9]" <file>` 命中 → 视为 CRITICAL（硬编码 sleep）
- `grep "asyncio\.sleep\([0-9]" <file>` 命中 → 视为 CRITICAL（硬编码 await sleep）
- `grep "timeout=[0-9]" <file>` 命中 → 视为 CRITICAL（硬编码 timeout）
- Pydantic 配置类时间字段无 `ge`/`le` → 视为 WARNING（缺边界校验）

**判断信号**：
- `grep "time\.sleep\|asyncio\.sleep" <file>` 参数为字面量数字 → 硬编码
- `grep "Field\(.*ge=.*le=" <config_file>` 缺时间字段 → 边界校验缺失
- `grep "get_config\(\)\.\w+\.\w+_seconds" <file>` 但无 `try.*except` 包裹 → 缺兜底

**适用**：所有 `time.sleep` / `asyncio.sleep` / `timeout` / `wait_for(timeout=)` 调用；异常重试/退避策略；轮询/心跳间隔；超时控制；冷却期/防抖期。
**不适用**：单元测试中的 `time.sleep(0.1)`（测试固定延迟）；性能基准测试中的精确计时；日志刷新间隔（<100ms 无业务影响）；UI 动画时长（前端 CSS transition）。

**历史教训**：`scheduler.py` 的 `_compute_next_wait_seconds` 异常重试等待硬编码 `return 300`，导致所有任务异常后必须等 5 分钟才能重试，无法根据业务场景调整。同期 `cookie_sync_scheduler.py` 的同步间隔硬编码在代码中，`batch_refresh_scheduler.py` 的失败重试等待也是字面量数字。修复：在 `TaskSchedulerConfig` 加 `error_retry_wait_seconds: int = Field(300, ge=10, le=3600)` 字段，所有硬编码改为 `get_config().task_scheduler.error_retry_wait_seconds`。建立 #49 强制配置化规则。

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

## 52. 参数链闭环验证（PARAM-CHAIN-EXEC）🆕v4.37

> 与维度 19 API 设计（B-REVIEW-177）/ 维度 7 API 契约（F-REVIEW-144）对应。

过滤类参数（filter / constraint 语义）从 API 接收后必须存在对应的消费点（函数调用 / SQL WHERE / 条件分支），禁止"参数已接收但未被消费"。

1. **接收点验证**：API endpoint 函数签名声明参数后，函数体内必须存在该参数的消费逻辑
2. **消费点验证**：参数必须实际参与过滤条件构建（WHERE 子句 / 条件分支 / 函数调用参数）
3. **结果集验证**：必须存在单元测试验证"传参 vs 不传参"结果集差异，否则视为过滤未生效
4. **元数据参数豁免**：分页参数（page / page_size / limit / offset）与排序参数（sort / order）属于标识/定位类参数，不在本规范范围

**关键约束**：
- 参数出现在函数签名 + return dict 中但未出现在过滤逻辑 → 视为"参数悬挂"违规
- 参数命名暗示过滤语义（含 `filter_` / `range_` / `min_` / `max_` / `ratio_` 前缀）必须闭环
- 元数据参数白名单在 `config.yaml` 管理，禁止硬编码

**判断信号**：
- `grep "<param_name>" <file>` 仅命中函数签名和 return 语句但未命中函数调用 → 视为可疑
- API 接收 `market_ratio` 参数但未调用 `PriceStrategy.check(market_ratio=...)` → 违规
- 单元测试无 `with_param` / `without_param` 对比用例 → 视为闭环验证缺失

**适用**：所有有过滤参数的列表查询 API（list_evaluations / list_items / search_* / list_orders）、PATCH/PUT 接口的可空字段
**不适用**：GET 单个资源详情（无过滤）、DELETE 接口（参数仅定位资源）、仅作元数据返回的字段（total_count）、创建类 POST 接口

**历史教训**：`evaluations_list.py` 接收 `market_ratio=0.85` 参数但未调用 `PriceStrategy.check`，导致调整到 0.85 后仍能查出价格上限 800 的商品。修复：新增 `_resolve_market_ratio` / `_compute_eval_market_median` / `_filter_market_ratio` 三个辅助函数形成闭环。

> 📖 详见 [config-driven.md](../assets/guides/coding-rules/config-driven.md) step 189。

## 53. 业务模式纵向链路一致性（MODE-VERTICAL-CHAIN）🆕v4.37

> 与维度 19 状态管理（B-REVIEW-183，待落地）/ 维度 4 业务逻辑（F-REVIEW-141，待落地）对应。

业务模式枚举（如 AUTO / SEMI_AUTO / MANUAL）必须在 6 个层纵向一致传递：决策层 → 事件层 → 通知层 → 路由层 → 接口层 → 状态机层。任一层缺失即模式退化。

**与 #40 MULTI-FIELD-LINKED-SWITCH 的边界**：
- #40 关注"字段间横向联动"（主开关 + 子过滤器的优先级矩阵）
- 本规范关注"模式枚举纵向链路"（同一 mode 值在 6 层是否都引用）

1. **决策层**：`_should_buy()` 等决策函数必须根据 mode 返回不同决策
2. **事件层**：业务事件 payload 必含 mode 字段（如 `EVAL_PASSED` 事件含 `task_mode`）
3. **通知层**：不同 mode 渲染不同模板（SEMI_AUTO 必含确认链接）
4. **路由层**：前端为每个 mode 的后续动作提供对应路由（如 `/confirm-buy`）
5. **接口层**：后端为每个 mode 的后续动作提供 endpoint
6. **状态机层**：必要时引入中间状态（如 `pending_confirm`）防越权

**关键约束**：
- grep mode 枚举值，每个值必须在 6 个层都至少出现 1 次
- 中间状态必须显式声明，禁止用临时变量隐式表达
- mode 字段名在 6 层必须严格一致（snake_case 透传，禁止 camelCase 转换）

**判断信号**：
- `grep "task_mode\|mode.*AUTO\|mode.*MANUAL"` 在事件 payload / 通知模板 / 路由 / endpoint 中未命中 → 链路断裂
- 决策函数返回值与 mode 无关 → 决策层未实现
- 通知模板对所有 mode 渲染相同内容 → 通知层未实现

**适用**：所有引入 mode 枚举且影响后续行为的业务（任务执行模式、采集模式、通知模式、订单确认模式）
**不适用**：纯展示型 mode 字段（仅日志记录不影响流转）、内部状态字段（不跨层传递）、单一布尔开关（无枚举语义，归 #40）

**历史教训**：SEMI_AUTO 模式退化为 CONFIRM/NOTIFY，因为：`_should_buy()` 返回 False / 通知模板缺确认链接 / 事件 payload 缺 `task_mode` / 缺 `pending_confirm` 中间状态 / 缺确认接口。修复：5 层全补齐（决策/事件/通知/路由/接口）+ 引入 `pending_confirm` 状态。

> 📖 详见 [state-management.md](../assets/guides/coding-rules/state-management.md) step 190。

## 54. 外部页面解析容错（PARSER-FALLBACK-CHAIN）🆕v4.37

> 与维度 13 浏览器自动化（B-REVIEW-179）对应。

解析不受控的第三方页面 DOM 必须采用多级 fallback selector 策略，任一 selector 命中即返回，全部失败才触发 debug dump。

1. **三级 fallback**：按"结构化 selector → 属性 selector → 文本扫描"顺序尝试
2. **debug dump 触发条件**：基于业务语义（如 `on_sale == 0`）而非实现细节（如 `sold == 0`）
3. **selector 列表配置化**：所有 selector 字符串在 `config.yaml` 管理，禁止硬编码
4. **降级链日志合并**：与 #32 一致，多 selector 尝试的中间步骤 DEBUG 化，最终失败 WARNING

**关键约束**：
- 单一 selector 无 try/except fallback → 视为风险
- selector 硬编码在代码中 → 违规（必须配置化）
- debug dump 触发条件耦合实现细节 → 违规

**判断信号**：
- `grep "querySelector\|querySelectorAll\|select\|css"` 在外部页面解析上下文，无 `try/except` 或 `or []` fallback → 违规
- `grep "tabItem\|tab.*role.*tab\|tab.*class"` selector 字符串硬编码 → 违规
- debug dump 条件含 `sold == 0`（实现细节）而非 `on_sale == 0`（业务语义）→ 违规

**适用**：所有解析闲鱼/淘宝/天猫/京东等第三方页面的代码（`_detail.py` / `_parse_*` 函数 / Playwright page.evaluate 返回值解析）
**不适用**：解析自己生成的内容（本地 HTML 模板）、解析 API 返回的 JSON（结构稳定）、解析固定 schema 的 XML/YAML

**历史教训**：`_parse_sale_counts_from_tabs` 仅依赖 `tabItem` class 名，闲鱼页面 DOM 结构变化导致 `on_sale=0` 和 `sold=0`。修复：实现三级 fallback（`[class*='tabItem']` → `[class*='tab'][role='tab']` → 文本前缀扫描 div/span/a），收紧 debug dump 触发条件从 `on_sale==0 or sold==0` 改为 `on_sale==0`（因为 `sold==0` 是新 UI 的预期行为）。

> 📖 详见 [browser-automation.md](../assets/guides/coding-rules/browser-automation.md) step 191。

## 55. mock 同步与边界精确性（MOCK-SYNC-BOUNDARY）🆕v4.37

> 与维度 20 测试建议（B-REVIEW-180）/ 维度 12 可测试性（F-REVIEW-146）对应。

**与 #47 EXTERNAL-DEP-ISOLATION 的边界**：
- #47 关注"是否要 patch"（强制 patch 外部依赖）
- 本规范关注"如何 patch"（patch 的类型/边界/字段/副作用）

修改被测代码后必须同步 mock：mock 类型与被 mock 对象的同步/异步特性必须一致，patch 必须 patch 实际调用点而非定义点，mock 数据必须覆盖完整字段集。

1. **类型匹配**：同步函数用 `MagicMock`，异步函数用 `AsyncMock`，禁止混用
2. **patch 边界**：patch 必须 patch 实际调用点（如 `worker.get_secret`）而非定义点（如 `secrets.get_secret`）
3. **字段完整性**：mock 数据必须覆盖被测代码访问的所有字段，禁止部分 mock
4. **副作用验证**：测试必须断言"副作用未发生"（如未发起真实网络请求 / 未写文件 / 未发邮件）

**关键约束**：
- 同步函数用 `AsyncMock` → CRITICAL（mock 类型错配）
- 异步函数用 `MagicMock` → CRITICAL
- patch 路径与实际调用路径不一致 → WARNING
- mock 数据缺字段 → 测试可能 NPE，视为不完整

**判断信号**：
- `grep "AsyncMock" <test_file>` 但被 mock 函数是同步函数（无 `async def`）→ 违规
- `grep "MagicMock" <test_file>` 但被 mock 函数是 `async def` → 违规
- `patch("module.function")` 但实际调用是 `from module import function; function()` → patch 边界错误

**适用**：所有 unit test / 集成测试中的 mock 替身
**不适用**：E2E 测试（应使用真实环境）、快照测试（snapshot test）

**历史教训**：`test_dingtalk_notify_integration.py` 用 `AsyncMock` 但 `worker.py` 的 `filter_new` 已改为同步实现，导致 `await` 在同步对象上失败。`test_notifier_new_channels.py` patch `get_secret` 位置错误导致 webhook_url/secret 实际不为空，测试发起真实钉钉请求。修复：AsyncMock 改 MagicMock 对齐同步实现 / patch get_secret 返回 None 确保真正为空 / test_manual_takeover_lock 构造 mock request 含 user_id。

> 📖 详见 [testing.md](../assets/guides/coding-rules/testing.md) step 192。

## 56. 过滤结果透明化 UI（FILTER-RESULT-TRANSPARENCY-UI）🆕v4.37

> 与维度 7 API 契约（F-REVIEW-147）对应。

列表查询 UI 同时有 ≥2 个过滤参数（价格区间 + 市场比例 + 任务范围）时，必须透明化展示当前生效的过滤规则组合，否则用户无法理解"为何查不到数据"。

**与 #40 MULTI-FIELD-LINKED-SWITCH 的边界**：
- #40 关注"字段间联动 UI 禁用标识"（开关 disabled 状态）
- 本规范关注"过滤结果透明化展示"（数据被过滤的可见性）

1. **Tooltip 说明**：关键过滤参数提供 Tooltip 说明查询规则（如"价格区间 + 低于市场参考价参数取值"）
2. **filter_summary 三态**：空结果时区分"无数据"vs"被过滤排除"vs"全部数据"三种状态
3. **当前过滤组合展示**：UI 显式列出当前生效的过滤参数组合（如"当前过滤：价格 600-800 + 市场比例 ≤0.85"）
4. **参数语义化**：业务参数（如 `market_ratio` 0.85）应展示语义化文案（如"低于市场参考价 15%"）

**关键约束**：
- UI 同时有 ≥2 个过滤参数但无 tooltip / filter_summary → 透明化不足
- 空结果统一显示"暂无数据"不区分原因 → 违规
- 过滤参数展示仅显示数值不显示语义 → 不友好

**判断信号**：
- `grep "filter.*range\|market.*ratio\|min.*max"` 在列表 UI 但无 `Tooltip` / `filter_summary` → 违规
- `grep "empty.*data\|no.*data"` 但无 `filtered_count` / `total_count` 区分 → 违规
- 参数展示仅 `value` 无 `label` / `description` → 不友好

**适用**：所有多参数列表查询 UI（评估明细 / 商品列表 / 订单列表 / 仪表盘过滤）
**不适用**：单一过滤参数（如仅搜索关键字）、用户主动输入的查询条件（用户已知）、详情页（无过滤）

**历史教训**：用户调整"低于市场参考价"到 0.85 后，评估明细菜单仍能查出价格上限 800 的商品，且 UI 无任何提示当前生效的过滤规则。用户误以为是价格范围 600-800 的问题，实际是 market_ratio 过滤未生效。修复：在价格范围 label 处添加 `QuestionCircleOutlined` 图标 + Tooltip 说明查询规则（价格区间 + 低于市场参考价参数取值）。

> 📖 详见 [frontend-ui.md](../assets/guides/coding-rules/frontend-ui.md) step 193。

---

# 异步与资源安全元规范（57-63）🆕v4.38.0

> 基于 2026-07-08 解决的「async/await 误用、NullPool 性能问题、HTTP 状态码语义模糊、CSS 选择器失效、异常日志丢失 traceback、并发安全 page closure、参数传递缺失、日志质量退化链」8 类问题，使用 Sequential Thinking 8 步复盘法（问题识别 → 根因分析 → 修复方案 → 验证 → 影响评估 → 规范候选 → 落地决策 → 内容设计），新增 7 条元规范（meta-rules #57-63），元规范总数从 56 → 63。
>
> 命名空间与配置驱动：所有阈值（`async_await_check` / `resource_pool_benchmark` / `http_status_code_mapping` / `css_selector_fallback` / `exception_log_semantic` / `external_resource_lifecycle` / `db_write_identity_trace`）均在 `config.yaml` 对应节点管理，禁止硬编码。
>
> 编号说明：step 198-204 / B-REVIEW-182-188 / F-REVIEW-148-151。

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

## 64. URL↔状态同步失败回退（URL-STATE-SYNC-FALLBACK）🆕v4.39 experimental

> 与 F-REVIEW-152（前端 URL↔状态同步失败回退审查）对应。后端无此场景，不新增 B-REVIEW。

SheetWorkspace 多页签应用中，URL 变化触发 `openSheet` 失败时（路径未注册 / 栈满），URL 已改变但 activeId 未变，导致 `useParams()` 返回错误值，业务逻辑误判。必须在 `openSheet` 失败时回退 URL 到当前 active sheet 的 path，保持 URL 与 active sheet 一致。

1. **失败时 URL 回退强制**：`useSheetSync` Hook 在 `openSheet` 失败时（`!result.ok`）必须调用 `navigate(activeSheet.path, { replace: true })` 回退 URL
2. **activeSheet 存在性检查**：回退前必须检查 `activeSheet` 是否存在（可能首次加载无 activeId），不存在则跳过回退
3. **replace 参数强制**：回退必须用 `{ replace: true }` 避免污染浏览器历史记录
4. **防循环检查保留**：回退后 `activeSheet.path === URL`，防循环检查（第 40 行）会跳过，不会死循环
5. **配置驱动**：回退开关、回退策略（replace / push）、允许回退的 reason 清单从 `config.yaml#url_state_sync_fallback` 读取

**关键约束**：
- `useSheetSync` Hook 缺 `navigate` 引入 → 视为 WARNING（无法回退）
- `openSheet` 失败时无 URL 回退逻辑 → 视为 CRITICAL（URL 漂移导致业务误判）
- 回退未用 `{ replace: true }` → 视为 WARNING（污染历史记录）
- 回退前未检查 `activeSheet` 存在性 → 视为 WARNING（空指针风险）

**判断信号**：
- `grep "useSheetSync" frontend/src/hooks/` 但无 `useNavigate` 引入 → 缺 navigate
- `grep "!result.ok" frontend/src/hooks/useSheetSync.ts` 但无 `navigate(activeSheet.path)` → 缺回退逻辑
- `grep "navigate\(.*\)" frontend/src/hooks/useSheetSync.ts` 但无 `replace: true` → 缺 replace 参数

**适用**：SheetWorkspace 多页签应用（URL ↔ sheet 栈双向同步）、URL 参数驱动的页面状态（如 `useParams().id` 判断编辑/新增模式）、外部链接回链场景（通知点击、邮件链接、二维码）。
**不适用**：纯静态路由（无状态同步）、无 URL 参数的页面（无 useParams 依赖）、独立路由（如 `/login` 不进入 SheetWorkspace）、传统 MPA（后端渲染无前端状态）。

**反模式**：
```typescript
// ❌ openSheet 失败时 URL 已改变但 activeId 不变，useParams 漂移
useEffect(() => {
  const path = location.pathname + location.search
  const activeSheet = sheets.find((s) => s.id === activeId)
  if (activeSheet?.path === path) return
  const result = openSheetWithNotification(path)
  // 缺失败时 URL 回退，导致 isEdit 误判
}, [location.pathname, location.search, sheets, activeId])
```

**正确模式**：
```typescript
// ✅ openSheet 失败时回退 URL 到 active sheet 的 path
import { useNavigate } from 'react-router-dom'

export function useSheetSync(): void {
  const location = useLocation()
  const navigate = useNavigate()
  const sheets = useSheetStore((s) => s.sheets)
  const activeId = useSheetStore((s) => s.activeId)

  useEffect(() => {
    const path = location.pathname + location.search
    const activeSheet = sheets.find((s) => s.id === activeId)
    if (activeSheet?.path === path) return
    const result = openSheetWithNotification(path)
    // openSheet 失败时回退 URL 到当前 active sheet 的 path
    if (!result.ok && activeSheet) {
      navigate(activeSheet.path, { replace: true })
    }
  }, [location.pathname, location.search, sheets, activeId, navigate])
}
```

**历史教训**：任务修改流程中点击 Step 3「全局搜索配置」按钮，`navigate('/app/config/search')` 多了 `/app` 前缀（basename），`findSheetMeta('/app/config/search')` 返回 undefined，触发 React Router `*` 重定向到 `/`。此时 URL 变为 `/`，但 activeId 仍指向 TaskEditor，`useParams().id` 返回 undefined，`isEdit` 误判为 false，提交时创建重复任务。修复：(1) Step 3 改为打开 Modal（避免 navigate）；(2) `useSheetSync` 在 `openSheet` 失败时回退 URL。

> 📖 详见 [state-management.md](../assets/guides/coding-rules/state-management.md) step 205（预沉淀）。

## 65. Service Worker 缓存版本同步（SW-CACHE-VERSION-SYNC）🆕v4.39 experimental

> 与 F-REVIEW-153（前端 SW 缓存版本同步审查）对应。后端无此场景，不新增 B-REVIEW。

PWA 应用使用 Service Worker 缓存静态资源，构建时生成的版本哈希（如 `sw.js` 中的 `precaching-manifest`）必须与前端运行时检测的版本一致。版本不一致时（如用户浏览器缓存旧 `sw.js`），必须触发 `skipWaiting()` 强制更新，避免旧版本页面功能异常。

1. **构建时版本哈希**：`vite-plugin-pwa` 构建时在 `sw.js` 中生成版本哈希（`self.__WB_MANIFEST` 中的文件哈希）
2. **运行时版本检测**：前端启动时（`main.tsx` 或 `App.tsx`）读取 `navigator.serviceWorker.controller` 的版本，与当前构建版本对比
3. **skipWaiting 强制更新**：版本不一致时调用 `registration.waiting?.postMessage({ type: 'SKIP_WAITING' })` 触发 `skipWaiting()`
4. **硬刷新提示**：`skipWaiting` 后显示「新版本已就绪，点击刷新加载」提示，用户确认后 `window.location.reload()`
5. **配置驱动**：版本检测开关、硬刷新提示文案、skipWaiting 触发策略从 `config.yaml#sw_cache_version_sync` 读取

**关键约束**：
- `sw.js` 缺版本哈希 → 视为 WARNING（无法检测版本差异）
- 前端启动时无版本检测逻辑 → 视为 WARNING（无法触发强制更新）
- 版本不一致时无 `skipWaiting` 触发 → 视为 CRITICAL（用户功能异常）
- 缺硬刷新提示直接 `reload()` → 视为 WARNING（用户体验突兀）

**判断信号**：
- `grep "self.__WB_MANIFEST\|precaching-manifest" frontend/dist/sw.js` 缺失 → 缺版本哈希
- `grep "navigator.serviceWorker.getRegistration" frontend/src/` 缺失 → 缺版本检测
- `grep "SKIP_WAITING\|skipWaiting" frontend/src/` 缺失 → 缺强制更新逻辑
- `grep "新版本.*刷新\|版本已更新" frontend/src/` 缺失 → 缺硬刷新提示

**适用**：PWA 应用（使用 Service Worker 缓存）、SPA 应用（单页应用前端构建）、依赖 Service Worker 缓存的离线应用、频繁迭代的前端项目（版本更新快）。
**不适用**：传统 MPA 应用（每次加载最新 HTML）、无 Service Worker 的应用、纯静态站点（无动态内容）、测试环境（版本检测关闭）。

**反模式**：
```typescript
// ❌ 无版本检测逻辑，用户浏览器缓存旧 sw.js 导致功能异常
// main.tsx 直接注册 SW，不检测版本
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js')
}
```

**正确模式**：
```typescript
// ✅ 构建时生成版本哈希 + 运行时版本检测 + skipWaiting 强制更新
// vite.config.ts
VitePWA({
  strategies: 'generateSW',
  manifest: { /* ... */ },
  workbox: {
    skipWaiting: true,
    clientsClaim: true,
  },
})

// main.tsx
async function checkSWUpdate() {
  if (!('serviceWorker' in navigator)) return
  const registration = await navigator.serviceWorker.getRegistration()
  if (registration?.waiting) {
    // 版本不一致，显示硬刷新提示
    const userConfirmed = confirm('新版本已就绪，点击刷新加载')
    if (userConfirmed) {
      registration.waiting.postMessage({ type: 'SKIP_WAITING' })
      window.location.reload()
    }
  }
}
checkSWUpdate()
```

**历史教训**：PC 端首次登录后重定向到 `/app/m/`（移动端），根因是浏览器缓存了旧版 `sw.js`，旧版 SPA 中 `useMobileDetect.ts` 用 `pointer:coarse` 触屏判断导致 PC 端误判为移动端。修复：(1) 修复 `useMobileDetect.ts` 移除 `pointer:coarse` 判断；(2) 构建新 SPA 生成新 `sw.js` 哈希；(3) 用户需硬刷新（Ctrl+Shift+R）清除 Service Worker 缓存。预防：添加版本检测 + `skipWaiting` 强制更新逻辑。

> 📖 详见 [frontend-ui.md](../assets/guides/coding-rules/frontend-ui.md) step 206（预沉淀）。

## 66. HTTP 状态码语义分层与冲突避免（HTTP-STATUS-CODE-LAYERING）🆕v4.40.0

> 与 B-REVIEW-189（后端业务异常状态码冲突检查）/ F-REVIEW-154（前端全局拦截器状态码区分检查）对应。本规则解决「同一状态码在不同层语义冲突」问题，与 #59「多原因 None → 状态码映射」维度不同，互补不重复。

**问题背景**：业务异常（如闲鱼 cookie 过期）与认证失败（系统 token 失效）共用 HTTP 401 状态码，导致前端全局拦截器无法区分两者，把业务异常误判为认证失效并跳转登录页，破坏用户工作流。

**核心原则**：
1. **状态码分层所有权**：每个 HTTP 状态码应有明确的所有权层（认证层/业务层/校验层），同一状态码不应跨层共用
2. **认证中间件保留状态码**：401 应专属认证中间件（如 BearerAuthMiddleware 返回 `{"detail":"Unauthorized"}`），业务代码不得抛出 401
3. **业务异常使用专用状态码**：外部凭证失效（如闲鱼 cookie 过期）使用 440，参数校验使用 422，反爬使用 429
4. **前端拦截器精确化**：全局响应拦截器跳转登录页必须基于 `detail` 或 `error_code` 字段精确匹配，不能仅靠 status code
5. **多模式一致性**：同一语义（如 cookie 过期）在不同业务模式（detail-only/official-full）必须使用相同状态码

**判断信号（grep / 静态检查）**：
- `grep -rn "CollectionError(401" src/` 命中 → 业务代码抛出认证层专属状态码，需改为 440
- `grep -rn "raise HTTPException(401" src/` 命中（非认证中间件）→ 违反所有权
- 前端拦截器：`error.response?.status === 401` 后无 `detail === 'Unauthorized'` 校验 → 拦截器过宽

**配置驱动**：
- 状态码分层映射在 `config/tech-stack.json#hardConstraints.statusCodeLayering` 管理
- 一致性规则在 `consistency_rules` 数组中维护，新增模式时只需追加 `applies_to`

**适用场景**：
- 所有 HTTP API 后端业务异常处理
- 多模式业务（如 detail-only/official-full 采集模式）共享同一异常类
- 带全局响应拦截器的前端应用
- Bearer/JWT 认证体系

**不适用场景**：
- 无认证的内部接口
- 纯参数校验（422 由 FastAPI 自动处理）
- 测试 mock（可自由返回任意状态码）

**与 #59 的区别**：
- #59 关注「多原因 None → 状态码映射」（同层内多原因细分）
- #66 关注「同一状态码跨层语义冲突」（层间所有权划分）
- 两者互补，不重复

**复盘来源**：业务 401 与认证 401 状态码冲突 Bug（卖家评估页点击标题链接跳转登录页）。修复：后端 3 处 `CollectionError(401, ...)` → `CollectionError(440, ...)`（与 official-full 模式一致）；前端 axios 拦截器只对 `detail === 'Unauthorized'` 跳转登录页。

## 67. 移动端检测多重 fallback 强制要求（MOBILE-DETECT-MULTI-FALLBACK）🆕v4.41.0

> 与 F-REVIEW-155（前端移动端检测 Hook 审查）对应。本规则解决「设备仿真模式下单一触摸检测属性失效导致移动端路由不跳转」问题。

**问题背景**：iPadOS 13+ 设备 UA 伪装为桌面 macOS，移动端检测依赖 `'ontouchend' in document` 判断触摸能力，但 Chrome DevTools / Playwright 设备仿真模式下该属性可能未被正确设置，导致 Macintosh UA 分支检测失败，页面不跳转到移动端路由。

**核心原则**：
1. **多重 fallback**：移动端检测的触摸判断必须至少有 2 个独立检测属性（如 `ontouchend` + `maxTouchPoints`），任一为 true 即判为触摸设备
2. **仅限 Macintosh 分支**：fallback 仅在 Macintosh UA 分支生效，避免触屏笔记本（Surface 等）误判为移动端
3. **属性优先级**：`ontouchend` 优先（真实设备最可靠），`maxTouchPoints > 0` 作为 fallback（仿真模式下更稳定）
4. **禁止 pointer:coarse**：触屏笔记本/二合一设备会触发 coarse，但视口宽度通常 ≥1024，误判为移动端会导致桌面用户被强制跳到 /m/ 路由

**判断信号（grep / 静态检查）**：
- `grep "ontouchend.*in.*document" frontend/src/` 命中但同文件无 `maxTouchPoints` → 触摸检测缺少 fallback，视为 CRITICAL
- `grep "Macintosh.*ontouchend" frontend/src/` 但无 `maxTouchPoints` → iPadOS 13+ 检测不完整
- `grep "pointer.*coarse\|matchMedia.*pointer" frontend/src/mobile/` → 触屏笔记本误判风险

**配置驱动**：
- 触摸检测属性列表在 `config.yaml#mobile_detect.touch_detection_properties` 管理
- Macintosh UA 正则在 `config.yaml#mobile_detect.macintosh_pattern` 管理
- 视口阈值在 `config.yaml#mobile_detect.viewport_max_width` 管理

**适用场景**：
- React SPA 移动端路由跳转检测（useMobileDetect / useIsMobile）
- iPadOS 13+ 设备兼容性
- Chrome DevTools / Playwright 设备仿真模式测试
- PWA 应用移动端适配

**不适用场景**：
- 纯 CSS 响应式布局（无 JS 检测逻辑）
- SSR 应用（路由由服务端控制）
- 非 Macintosh UA 设备（Android/iPhone 直接由 UA 正则匹配）

**复盘来源**：设备仿真模式下 iPad Pro 页面不跳转到移动端路由。根因：`'ontouchend' in document` 在仿真模式下为 false，且无 `maxTouchPoints` fallback。修复：在 `isMobileUA()` 和 `detectMobile()` 两个函数中增加 `navigator.maxTouchPoints > 0` 作为 fallback。

## 68. 响应式断点统一规范（RESPONSIVE-BREAKPOINT-UNIFY）🆕v4.41.0

> 与 F-REVIEW-156（前端响应式断点一致性检查）对应。本规则解决「多个移动端检测 Hook 和 CSS 媒体查询使用不同断点阈值，导致同一视口宽度下路由跳转与 UI 布局不一致」问题。

**问题背景**：项目中存在两套移动端检测 Hook（useMobileDetect 600px + useIsMobile 767px）和 CSS 媒体查询（768px），阈值不一致导致：
- 600-767px 区间：useMobileDetect 判为桌面（不跳转 /m/），但 useIsMobile 判为移动端（UI 响应式生效）
- 600px 以下：三者一致判为移动端
- 这种不一致在设备仿真模式下尤为明显

**核心原则**：
1. **路由跳转阈值独立于 UI 响应式阈值**：路由跳转（useMobileDetect）的视口阈值可以小于 UI 响应式（useIsMobile）阈值，因为路由跳转有更强副作用（强制导航到 /m/）
2. **阈值差异必须显式声明**：若两个 Hook 阈值不同，必须在代码注释和 config.yaml 中显式声明差异原因
3. **CSS 媒体查询与 UI Hook 对齐**：useIsMobile 的 matchMedia 断点必须与 CSS `@media` 断点一致（均为 767px/768px）
4. **阈值配置化**：所有断点阈值从 config.yaml 读取，禁止硬编码

**判断信号（grep / 静态检查）**：
- `grep "MOBILE_VIEWPORT_MAX\|viewport_max_width" frontend/src/` 与 `grep "767\|768" frontend/src/` 值不同 → 阈值不一致，需显式声明
- `grep "max-width.*767\|max-width.*768\|max-width.*600" frontend/src/` 多个不同值 → CSS 断点分散
- useMobileDetect 阈值与 useIsMobile 阈值差 > 100px → 可能导致行为不一致区间过大

**配置驱动**：
- 路由跳转阈值：`config.yaml#mobile_detect.viewport_max_width`（600px，有明确副作用说明）
- UI 响应式阈值：`config.yaml#mobile_detect.ui_responsive_max_width`（767px，与 antd 对齐）
- CSS 媒体查询断点：`config.yaml#mobile_detect.css_media_breakpoint`（768px，与 UI Hook +1 对齐）

**适用场景**：
- 多 Hook + 多 CSS 断点的 React SPA 项目
- 路由跳转与 UI 响应式需要不同阈值的场景
- Ant Design 等 UI 框架有固定断点的项目

**不适用场景**：
- 单一检测 Hook + 单一 CSS 断点（无一致性问题）
- 纯服务端渲染（无客户端路由跳转）
- 纯 CSS 响应式（无 JS 检测逻辑）

**复盘来源**：useMobileDetect（600px）控制路由跳转，useIsMobile（767px）控制桌面响应式，CSS @media（768px）控制样式适配。三者阈值不一致，在 600-767px 区间行为割裂。

## 69. 设备仿真模式验证清单（DEVICE-EMULATION-CHECKLIST）🆕v4.41.0

> 与 xianyu-auto-testing 技能的全面测试模式步骤 2 对应。本规则确保设备仿真测试的完整性和可靠性。

**问题背景**：Playwright MCP 的 `playwright_resize` 设备预设只调整视口尺寸和部分设备属性，但不修改 `navigator.userAgent` 和 `navigator.maxTouchPoints`，导致仿真测试无法覆盖真实设备行为，需要额外的验证策略。

**核心原则**：
1. **仿真三要素验证**：设备仿真测试必须验证 UA、maxTouchPoints、innerWidth 三者是否与目标设备一致
2. **UA 不一致时 fallback 验证**：若仿真工具无法修改 UA，必须通过 JS 属性覆盖模拟真实设备环境，验证 fallback 逻辑
3. **桌面端防误判必测**：每次修复移动端检测后，必须验证桌面端（≥1280px）不会被误判为移动端
4. **多设备覆盖**：至少覆盖窄屏手机（≤390px）、宽屏平板（≥834px）、桌面（≥1280px）三个典型场景

**判断信号（测试流程检查）**：
- 测试报告中无 `navigator.maxTouchPoints` 检查 → 设备仿真验证不完整
- 测试报告中无桌面端防误判结果 → 缺少必要验证
- 测试仅用 `playwright_resize` 而无 JS 属性覆盖验证 → UA 依赖的检测逻辑未真正测试
- 修复移动端检测后未重新构建部署 → 测试对象不是修复后代码

**配置驱动**：
- 设备预设列表：`config.yaml#browser_automation.playwright_mcp.device_presets`（多设备）
- JS 属性覆盖脚本模板：`config.yaml#browser_automation.playwright_mcp.ua_override_script_template`
- 防误判视口宽度：`config.yaml#browser_automation.playwright_mcp.desktop_viewport_width`

**适用场景**：
- Playwright / Puppeteer 设备仿真测试
- Chrome DevTools Device Mode 测试
- 需要验证 iPadOS 13+ 等 UA 伪装设备的场景

**不适用场景**：
- 真实设备测试（UA/maxTouchPoints 自然正确）
- 纯视觉回归测试（不涉及 JS 检测逻辑）
- 后端 API 测试（无浏览器环境）

**复盘来源**：Playwright `playwright_resize` iPad Pro 预设下 UA 仍为 Windows、maxTouchPoints=0，无法直接仿真 iPadOS 13+。需通过 `Object.defineProperty` 覆盖 navigator 属性来验证 maxTouchPoints fallback 修复。

## 70. 快捷预设独立 API Key 存储规范（PRESET-APIKEY-INDEPENDENT-SLOT）🆕v4.42.0

> 与 B-REVIEW-195（后端）、F-REVIEW-167（前端）对应。本规则解决「AI 服务快捷预设切换时 API Key 不跟随模型变化」问题。

**问题背景**：前端 AI 配置页面支持快速预设切换（OpenAI / DeepSeek 等），但 API Key 采用全局单一存储，切换预设时仅更新 base_url 和 model，未切换对应的 API Key，导致请求使用错误的凭证。

**规则**：
1. 每个预设必须有独立的凭证存储槽位（keyring key 或配置键名），格式：`<prefix>_preset_<preset_id>`
2. 切换预设时必须原子操作：(a) 保存当前预设的凭证到其槽位，(b) 从目标预设槽位恢复凭证，(c) 更新 active preset 标识
3. 首次切换时，如果存在全局凭证，必须将其迁移到原始预设槽位
4. 空字符串应能覆盖/清除预设槽位中的旧值（允许清空某预设的凭证）
5. 配置变更接口（PUT/PATCH）必须返回完整更新后的状态（含派生字段如 preset_id、脱敏后的 api_key）

**判断信号**：
- `grep "api_key" config.py` 发现全局单一凭证存储，无预设维度区分
- `grep "if.*preset" *.py` 发现条件凭证逻辑但无 per-preset 存储键
- PUT 响应仅返回 `{ok: true}` 而前端需要额外 GET 获取更新状态

**落地位置**：
- 后端：`secrets.py` ai_preset_key_name() / `api_ai.py` save_ai_config() / AI_PRESET_BASE_URLS
- 前端：`AIConfig/index.tsx` applyPreset() / 独立保存按钮
- 配置：`config.yaml` credential_storage.per_preset_slots / config_save.independent_button_required

**适用场景**：
- 所有涉及预设/供应商/配置组切换的凭据管理（AI 服务、通知渠道、代理、隧道等）
- 表单配置项需要独立于"测试/验证"按钮的持久化机制

**不适用场景**：
- 无凭证字段的表单配置
- 一次性凭证操作（无需预设切换）

---

## 71. 配置变更前后端契约规范（CONFIG-MUTATION-CONTRACT）🆕v4.42.0

> 与 B-REVIEW-198/200（后端）、F-REVIEW-169/170（前端）对应。本规则解决「配置变更后前后端状态不一致」问题。

**问题背景**：前端修改配置后，后端 PUT 接口仅返回 `{ok: true}`，前端需要额外发起 GET 请求才能获取最新状态（含 preset_id、脱敏 api_key 等派生字段）。这导致：(a) 网络往返增加，(b) 状态同步窗口期可能出现竞态，(c) 脱敏值被误写回表单。

**规则**：
1. 配置变更的 PUT/PATCH 端点必须返回完整的更新后配置状态，包含所有派生字段
2. 响应数据应由 get_*() 处理器内部构建，避免重复逻辑
3. 前端收到响应后，仅更新非敏感字段（base_url、model、preset_id 等），api_key 输入框保持为空
4. 脱敏后的 api_key（如 `****xxxx`）不得写入密码输入框的 value
5. 前端 applyPreset 时不应发送 api_key 字段，应由后端根据 preset_id 从独立槽位恢复

**判断信号**：
- PUT 响应仅包含 `{ok: true, message: ...}` 而无完整配置
- 前端在保存后发起额外 GET 请求获取更新状态
- applyPreset 函数包含 `api_key: config.api_key` 在 patch 对象中

**落地位置**：
- 后端：`api_ai.py` save_ai_config() 返回 `**get_ai_config()` / `AIConfigBody.preset_id: Literal[...]`
- 前端：`AIConfig/index.tsx` applyPreset() 不发送 api_key / 脱敏值处理
- 配置：`config.yaml` api.mutation_response_echo / api.literal_preset_ids / credential_storage.frontend_contract

**适用场景**：
- 所有配置变更类 API（不限于 AI 配置，扩展到通知、代理、隧道等）
- 前端表单配置项需要即时状态同步的场景

**不适用场景**：
- 纯创建型接口（POST 返回新建资源即可）
- 不需要派生字段的简单配置更新
---

## 72. 多用户 Cookie 隔离传播规范（MULTI-USER-COOKIE-ISOLATION）🆕v4.45.0

> 对应 B-REVIEW-209/210/211（后端）、F-REVIEW-178/179（前端）。本规则解决「登录用户态 Cookie 正确写入 JSON 文件，但实时搜索/官方采集仍使用默认用户 Cookie 导致 FAIL_SYS_ILLEGAL_ACCESS」问题。

**问题背景**：多用户 Cookie 隔离改造后，CookieStore 按 user_id 读写独立的 cookies_{user_id}.json 文件。但实时搜索入口（_ensure_live_search_cookies、live_links、refresh_links）未将 request.state.user_id 传递给 cookie 读取函数，导致始终读取 cookies_default.json。前端看到 cookie 健康检查通过，后台搜索 API 却返回非法请求。

**规则**：
1. 所有 CookieStore 操作方法（_read_json、export_cookies、update_cookie_values、has_valid_cookies、invalidate_cache）必须接受 user_id 参数，默认值为 "default" 以保持向后兼容
2. 实时搜索入口（_ensure_live_search_cookies、_check_live_cookies_safely、_load_pw_cookies_from_json）必须接受 user_id 参数，并从请求上下文中获取
3. SSE 实时搜索流（_live_event_stream）必须将 user_id 传递给 cookie 检查函数
4. refresh_links 端点必须将 request.state.user_id 传递给 _ensure_live_search_cookies
5. Cookie 回写操作（_sync_response_cookies_to_context、update_cookie_values）必须按当前用户写入对应的 cookies_{user_id}.json
6. 所有 cookie 读取操作必须在读取前调用 invalidate_cache(user_id) 清除缓存，避免跨进程写入后读到旧数据

**判断信号**：
- grep "_ensure_live_search_cookies(container)$" 发现未传递 user_id 参数
- grep "_load_pw_cookies_from_json()" 发现未传递 user_id 参数
- grep "store._read_json()" 发现未传递 user_id 参数
- grep "store.invalidate_cache()" 发现未传递 user_id 参数
- SSE 流中 _check_live_cookies_safely 调用未传递 user_id

**落地位置**：
- 后端：api_task_links.py（_load_pw_cookies_from_json、_ensure_live_search_cookies、_check_live_cookies_safely、refresh_links、live_links）
- 后端：cookie_store.py（_read_json、invalidate_cache、export_cookies、update_cookie_values、has_valid_cookies）
- 后端：_search.py（_sync_response_cookies_to_context）
- 配置：config.yaml cookie_management.multi_user_isolation.enabled

**适用场景**：
- 所有涉及 Cookie 读取/写入/注入的后端代码路径
- 多用户隔离后的实时搜索、官方采集、自动购买等场景
- Cookie 层状态同步（sync_cookie_layers_from_json）

**不适用场景**：
- 单用户模式（无 user_id 概念）
- 一次性 Cookie 导入操作（无实时搜索需求）

## 73. Cookie 注入必须验证浏览器状态（COOKIE-INJECTION-VERIFY）🆕v4.45.0

> 对应 B-REVIEW-212。本规则解决「Cookie 注入后未验证浏览器实际持有状态，导致注入成功但搜索仍失败」问题。

**问题背景**：_inject_cookies_from_json 调用 container.browser.add_cookies() 返回 True 即认为注入成功，但未验证浏览器实际持有的 cookie 是否与注入的一致。当浏览器上下文与注入的 cookie 不匹配时（如 domain/path 错误），搜索 API 仍会返回非法请求。

**规则**：
1. Cookie 注入后必须立即验证浏览器持有的关键 identity cookie（unb、cookie2、sgcookie）是否与注入值一致
2. 验证失败时必须记录警告日志并标记注入结果为 False
3. 验证通过后才允许继续执行搜索操作
4. 验证逻辑应复用 _collect_cookie_issues 中已有的浏览器 cookie 读取方法

**判断信号**：
- grep "add_cookies.*return_value=True" 发现注入成功但未验证
- grep "_verify_cookies_after_injection" 未发现验证函数

**落地位置**：
- 后端：api_task_links.py（_inject_cookies_from_json、_collect_cookie_issues）
- 后端：unified_login.py（_verify_cookies）

**适用场景**：
- 所有通过 add_cookies 向浏览器注入 Cookie 的代码路径
- 登录成功后 Cookie 同步到 worker 浏览器

**不适用场景**：
- 仅写入 JSON 文件不注入浏览器的操作

## 74. _m_h5_tk 刷新必须按用户隔离（M5TK-REFRESH-ISOLATION）🆕v4.45.0

> 对应 B-REVIEW-213。本规则解决「_m_h5_tk 刷新后 Set-Cookie 回写 JSON 时未指定 user_id，导致写入默认用户文件」问题。

**问题背景**：搜索 API 返回的 _m_h5_tk Set-Cookie 通过 _sync_response_cookies_to_context 回写到 JSON。但该函数调用 update_cookie_values() 时未传递 user_id，导致新 token 总是写入 cookies_default.json。如果当前活跃用户不是 default，则搜索会使用过期的 token。

**规则**：
1. _sync_response_cookies_to_context 必须接受 user_id 参数并传递给 update_cookie_values
2. _ensure_fresh_m5tk 导航刷新 token 后，必须确认回写的 JSON 路径与当前用户匹配
3. 强制刷新 _m_h5_tk 失败时（如导航超时），必须记录警告并跳过重试，避免无限等待

**判断信号**：
- grep "update_cookie_values(updates)$" 发现未传递 user_id
- grep "_sync_response_cookies_to_context" 发现无 user_id 参数

**落地位置**：
- 后端：_search.py（_sync_response_cookies_to_context、_ensure_fresh_m5tk）
- 后端：cookie_store.py（update_cookie_values）

**适用场景**：
- 所有搜索 API 返回 Set-Cookie 头的场景
- _m_h5_tk token 刷新流程

**不适用场景**：
- 非搜索类的 Cookie 操作

## 75. Cookie 层状态同步必须清除缓存（COOKIE-LAYER-SYNC-INVALIDATE）🆕v4.45.0

> 对应 B-REVIEW-214。本规则解决「跨进程写入 Cookie JSON 后主进程缓存未清除，导致层状态同步读到旧数据」问题。

**问题背景**：浏览器登录子进程写入 cookies_{user_id}.json 后，只更新子进程自己的缓存。主进程 CookieStore 持有 30 秒 TTL 缓存，如果不主动调用 invalidate_cache(user_id)，sync_cookie_layers_from_json 会读到旧数据，导致 /cookies/layers 端点显示层状态失效。

**规则**：
1. 所有跨进程 Cookie 写入后，写入方必须调用 invalidate_cache(user_id) 通知主进程
2. sync_cookie_layers_from_json 必须在读取 JSON 前调用 store.invalidate_cache()（不带 user_id 参数以清除全部缓存）
3. 注入 Cookie 到浏览器后，必须调用 sync_cookie_layers_from_json 同步层状态
4. 层状态同步失败必须记录 WARNING 日志，但不阻断主流程

**判断信号**：
- grep "sync_cookie_layers_from_json" 发现调用前无 invalidate_cache
- grep "invalidate_cache" 发现未在使用跨进程写入后调用

**落地位置**：
- 后端：login_orchestrator.py（sync_cookie_layers_from_json）
- 后端：cookie_runtime_sync.py（inject_cookie_store_to_browser）
- 后端：unified_login.py（on_login_success）

**适用场景**：
- 所有登录成功后 Cookie 层状态同步
- 浏览器导入 Cookie 后层状态同步
- Cookie 注入后层状态同步

**不适用场景**：
- 单进程内的 Cookie 读写（无跨进程同步需求）

## 76. 实时搜索 Cookie 健康检查必须传递 user_id（LIVE-SEARCH-COOKIE-HEALTHCHECK）🆕v4.45.0

> 对应 B-REVIEW-215、F-REVIEW-180。本规则解决「实时搜索 Cookie 健康检查未使用请求用户态，导致检查的是默认用户而非当前登录用户」问题。

**问题背景**：live_links 端点在 SSE 流中调用 _check_live_cookies_safely 进行 Cookie 健康检查，但该函数未接收 user_id 参数，内部 _ensure_live_search_cookies 也未传递 user_id。这导致健康检查始终读取 cookies_default.json，而非当前登录用户的 cookies_{user_id}.json。

**规则**：
1. live_links 端点必须从 request.state.user_id 获取当前用户，并传递给 _live_event_stream
2. _live_event_stream 必须将 user_id 传递给 _check_live_cookies_safely
3. _check_live_cookies_safely 必须将 user_id 传递给 _ensure_live_search_cookies
4. _ensure_live_search_cookies 必须将 user_id 传递给 _load_pw_cookies_from_json
5. 所有中间调用链必须保持 user_id 透传，不得在中途丢失

**判断信号**：
- grep "_check_live_cookies_safely(container, task_id, inflight_event)$" 发现未传递 user_id
- grep "_ensure_live_search_cookies(container)$" 发现未传递 user_id
- grep "_load_pw_cookies_from_json()" 发现未传递 user_id

**落地位置**：
- 后端：api_task_links.py（live_links、_live_event_stream、_check_live_cookies_safely、_ensure_live_search_cookies、_load_pw_cookies_from_json）

**适用场景**：
- 所有实时搜索入口（live_links、refresh_links）
- 所有通过 SSE 流触发搜索的场景

**不适用场景**：
- 后台定时搜索（由 batch_refresh_scheduler 管理，使用独立的 Cookie 同步机制）

## 77. Cookie 测试数据过滤必须在注入前执行（COOKIE-TEST-FILTER-BEFORE-INJECT）🆕v4.45.0

> 对应 B-REVIEW-216。本规则解决「测试 Cookie 被注入到浏览器导致搜索 API 返回异常」问题。

**问题背景**：CookieStore 有 is_test_cookie 函数过滤测试数据，但 _load_pw_cookies_from_json 在转换为 Playwright 格式前未调用此函数。导致测试 Cookie（如 unb=test、cookie2=test）被注入浏览器，搜索 API 返回非法请求。

**规则**：
1. 从 JSON 读取 Cookie 后、注入浏览器前，必须调用 is_test_cookie 过滤测试数据
2. 被过滤的测试 Cookie 必须记录 WARNING 日志，包含 cookie 名称和值的前 8 个字符
3. 注入后必须验证浏览器持有的 cookie 不包含测试数据
4. is_test_cookie 的过滤规则必须集中在 config.yaml 中管理，不得硬编码

**判断信号**：
- grep "is_test_cookie" 发现未在注入前调用
- grep "add_cookies" 发现无测试数据过滤

**落地位置**：
- 后端：cookie_store.py（is_test_cookie）
- 后端：api_task_links.py（_load_pw_cookies_from_json、_build_pw_cookie_item）

**适用场景**：
- 所有从 JSON 读取 Cookie 并注入浏览器的场景
- 测试环境 Cookie 管理

**不适用场景**：
- 仅读取 Cookie 用于状态展示的場景（不注入浏览器）

## 78. Cookie 文件路径必须使用 Path 多参数构造（COOKIE-PATH-SAFE-CONSTRUCTION）🆕v4.45.0

> 对应 B-REVIEW-217。本规则解决「user_id 未经校验直接拼入文件路径，可能导致路径遍历攻击」问题。

**问题背景**：_cookie_json_path 使用 Path(_COOKIE_JSON_DIR, f"cookies_{user_id}.json") 构造文件路径。虽然 user_id 有正则校验，但如果正则被绕过或修改，恶意 user_id（如 ../../etc/passwd）会导致文件写入任意位置。

**规则**：
1. 所有从用户输入派生的 user_id 必须在拼入文件路径前通过正则校验：^[A-Za-z0-9_-]{1,64}$
2. Path 构造必须使用多参数形式（Path(dir, filename)），不得使用字符串拼接后构造 Path
3. 测试中通过 monkeypatch 替换 Path 时，lambda 必须取 args[-1]（文件名）而非完整路径
4. 文件路径操作前必须验证解析后的绝对路径仍在预期的数据目录内

**判断信号**：
- grep 'Path.*f"cookies_' 发现字符串拼接后直接构造 Path
- grep "user_id.*json" 发现无正则校验

**落地位置**：
- 后端：cookie_store.py（_cookie_json_path、_USER_ID_RE）
- 测试：conftest.py（fake_cookie_json_path）

**适用场景**：
- 所有从用户输入派生文件路径的场景
- 多用户隔离后的 Cookie 文件管理

**不适用场景**：
- 内部确定的文件路径（无用户输入参与）

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

---

## 83. UI 操作项分级保留与多视图一致性（UI-ACTION-TIER-RETAIN-AND-MULTI-VIEW-CONSISTENCY）🆕v4.49.0

> **experimental 标签**：本规则基于单一 UI Bug 复盘沉淀，需更多案例验证才能升级为正式规则。当前作为推荐性规范执行，季度复盘时评估升级条件。

**问题背景**：任务管理页面（TaskList.tsx）操作列同时承载 6 个文字按钮（编辑/启停/停止/复制/另存为模板/删除），在窄屏或默认列宽下操作列总宽度约 580px，超出页面样式边界导致按钮被挤压换行、视觉错乱。根因是缺少"操作项分级保留"的硬性约束——所有按钮一律以文字按钮平铺，没有按使用频率分级（高频保留文字 / 中频图标 / 低频收入 Dropdown 等收起容器），也没有横向滚动 fallback 容错。同 Bug 同时暴露另一问题：表格视图与卡片视图对同一行操作按钮做了两套实现，修改时容易遗漏同步，造成多视图模式行为分裂。

**核心原则**：
1. 操作项分级保留范式：当单行/单卡操作按钮总数 > `uiLayout.actionButtonVisibleThreshold`（默认 5）时，必须按使用频率分级：
   - 高频（≥ `lowFrequencyThresholdPerMonth` 次/月）：保留为文字按钮
   - 中频（< 阈值但有快捷需求）：转为图标按钮 + Tooltip
   - 低频（< 阈值且无快捷需求）：收入收起容器（Dropdown/Popover/Drawer）
2. 收起容器选择策略由 `uiLayout.collapseContainerStrategy` 配置驱动（≤3 → Dropdown / 3-6 → Popover / >6 → Drawer），禁止在代码中硬编码选择逻辑
3. 多视图模式一致性：表格视图与卡片视图对同一资源的操作集合必须**完全一致**（按钮数量、文案、handler 行为、disabled 条件），禁止分叉实现
4. 横向溢出容错：所有 Table 必须显式声明 `scroll={{ x: <minWidth 或 'max-content'> }}`，作为分级保留失败时的最后兜底，避免按钮被挤压换行

**判断信号**：
- 单个 `<Space>` / `actions=` 内文字按钮 ≥ `actionButtonVisibleThreshold`（默认 5）→ 必须分级
- `grep "<Button" <page>.tsx` 计数 ≥ 6 且无 `<Dropdown` / `<Popover` / `<Drawer` → 违规
- 同一页面存在 `<Table` 与 `<Card` 两套视图，但只有一处修改了操作按钮 → 违反多视图一致性
- `grep "scroll=" <page>.tsx` 无匹配 → 缺少横向滚动 fallback

**配置驱动**：
- `uiLayout.enabled`：是否启用（默认 true）
- `uiLayout.actionButtonVisibleThreshold`：文字按钮可见阈值（默认 5）
- `uiLayout.lowFrequencyThresholdPerMonth`：低频判定阈值（默认 1）
- `uiLayout.collapseContainerStrategy`：收起容器选择策略（le3/3to6/gt6 三档）
- `uiLayout.scrollFallback`：横向滚动策略（默认 'max-content'）
- `uiLayout.multiViewSyncRequired`：多视图同步要求（默认 true）
- `uiLayout.multiViewSyncScanGlob`：扫描的文件 glob（默认 `frontend/src/pages/**/*.tsx`）
- `uiLayout.tableViewMatchers` / `uiLayout.cardViewMatchers`：识别表格视图/卡片视图的特征字符串
- 禁止在组件代码中硬编码阈值或容器选择逻辑

**适用场景**：
- 列表页操作列按钮过多导致水平空间溢出（任务管理、订单管理、商品管理）
- 同一资源在表格视图 + 卡片视图双视图呈现的场景
- AntD `<Table>` 的 columns render 中承载多个操作按钮的场景
- 移动端窄屏下的操作列收起需求（自适应缩窄到 < 阈值的一半时）

**不适用场景**：
- 单个详情页的固定操作栏（无横向溢出风险）
- 操作按钮总数 ≤ 阈值（无需分级）
- 仅有一种视图的页面（无多视图同步需求）
- 表单提交按钮组（主/次按钮天然分级，无需走此规则）

**与其他规则区别**：
- 与 #67（移动端检测多重 fallback）的区别：#67 关注设备类型识别；#83 关注操作按钮的分级保留
- 与 #68（响应式断点统一）的区别：#68 关注 CSS 断点与 Hook 阈值对齐；#83 关注操作列在溢出时的分级策略
- 与 step 162（LAYOUT-01 布局响应式与最小宽度规范）的配合：step 162 定义容器最小宽度；#83 定义操作列内部的分级保留
- 与 step 14（多视图切换与 state 提升）的配合：step 14 关注视图切换的 state 同步；#83 关注多视图下操作按钮集合的一致性

**复盘来源**：TaskList.tsx 操作列 6 个文字按钮溢出页面样式 Bug（2026-07-18 修复）。根因：操作列未按使用频率分级，"另存为模板"作为低频操作却占用一个文字按钮位置；同时 Table 缺少 `scroll` fallback。修复：将"另存为模板"收入 Dropdown 更多菜单（操作列从 6 个文字按钮减为 5 个 + 1 个图标按钮），Table 显式声明 `scroll={{ x: 'max-content' }}`，表格视图与卡片视图同步修改。

---

## #84 COOKIE-TOKEN-STATE-SEPARATION Cookie-Token 状态分离与一致性保障

**问题背景**：闲鱼猎人项目使用 Worker 浏览器实例（常驻）+ LoginOrchestrator（短生命周期子进程）的架构。Worker 浏览器在登录前就启动，会自动生成匿名 `_m_h5_tk` token。登录通过独立进程完成后，身份 Cookie 写入了 JSON/SQLite 但未同步到 Worker 浏览器内存。即使后续通过补注入将身份 Cookie 注入浏览器内存，匿名 token 仍残留，与身份 Cookie 不匹配，导致 MTOP API 签名验证失败（`FAIL_SYS_ILLEGAL_ACCESS::非法请求`）。

同时，TokenRenewer 的续期回调通过导航触发服务端刷新 token，但只更新浏览器内存中的 token，未回写 CookieStore JSON/SQLite，导致"内存中 token 已刷新但 JSON 中仍是旧值"的状态分裂。此外，loguru 日志使用 `%s` 占位符（标准库 logging 风格）导致日志输出字面量而非实际值，以及 `except: pass` 静默异常导致排查无线索。

**核心原则**：
1. **Cookie 与 Token 状态分离**：身份 Cookie 和签名 token 是两个独立的状态，有各自的生命周期和刷新机制。Cookie 可通过 JSON 补注入同步，但 token 是浏览器启动时生成的值，不会随 Cookie 一起更新。**禁止**假设"Cookie 有效则 token 也有效"。
2. **Token 重置独立于 Cookie 补注入**：无论是否执行了 Cookie 补注入，都必须重置 token 刷新时间戳。**禁止**将 token 重置逻辑绑定在 Cookie 补注入分支内——浏览器可能已持有身份 Cookie（无需补注入），但匿名 token 仍残留。
3. **续期闭环完整性**：所有状态变更（token 刷新、Cookie 更新）必须同步到所有存储介质（浏览器内存 + JSON + SQLite）。续期回调导航刷新 token 后必须提取完整 Cookie 回写 CookieStore。回写失败不阻断续期（token 已在内存中刷新），但必须记日志。
4. **日志占位符一致性**：loguru 使用 `{}` 占位符，**禁止**用 `%s`（标准库 logging 风格）。混用会导致日志输出 `%s` 字面量而非实际值。
5. **静默异常禁止**：所有 `except` 块禁止完全静默（`pass` / `...`），至少必须记录日志。关键路径必须用 `logger.exception()`，辅助路径至少用 `logger.warning()`。

**判断信号**：
- `grep "_last_m5tk_refresh" src/` 找到 token 时间戳 → 检查重置逻辑是否在 Cookie 补注入分支**外部**
- `grep "_default_renew_callback\|renew_callback" src/` 找到续期回调 → 检查导航后是否回写 CookieStore
- `grep "logger\.\(info\|warning\|error\|debug\).*%s" src/` 命中 → loguru 日志用了 `%s` 占位符
- `grep "except.*pass" src/` 命中 → 静默异常
- 实时搜索报 `FAIL_SYS_ILLEGAL_ACCESS` 但健康检查 Cookie 有效 → token 与 Cookie 不匹配

**配置驱动**：
- `cookie_token_consistency.enabled`：是否启用 Cookie-Token 一致性检查（默认 true）
- `cookie_token_consistency.identity_cookies`：身份 Cookie 白名单（默认 `['unb', 'cookie2', 'sgcookie', '_tb_token_', 't']`）
- `cookie_token_consistency.inject_domains`：补注入域过滤列表（默认 `['goofish.com', 'taobao.com']`）
- `cookie_token_consistency.token_refresh_field`：token 刷新时间戳字段名（默认 `_last_m5tk_refresh`）
- `cookie_token_consistency.token_reset_value`：重置值（默认 `0.0`）
- `renewal_loop_completeness.enabled`：是否启用续期闭环检查（默认 true）
- `renewal_loop_completeness.nav_url`：续期导航 URL（默认 `https://h5.m.taobao.com/`）
- `renewal_loop_completeness.export_domains`：回写域过滤列表（默认 `['goofish.com', 'taobao.com']`）
- `renewal_loop_completeness.method_tag`：回写方法标记（默认 `renew`）
- `renewal_loop_completeness.writeback_failure_blocks_renewal`：回写失败是否阻断续期（默认 false）
- `loguru_placeholder_format.enabled`：是否启用占位符检查（默认 true）
- `loguru_placeholder_format.correct_placeholder`：正确占位符（默认 `{}`）
- `loguru_placeholder_format.forbidden_placeholders`：禁止的占位符（默认 `['%s', '%d', '%f', '%r']`）
- `silent_exception_ban.enabled`：是否启用静默异常禁止（默认 true）
- `silent_exception_ban.critical_path_patterns`：关键路径函数名模式（默认 `['_on_startup', 'run_migrations', '_init_', '_shutdown', '_on_close']`）
- `silent_exception_ban.critical_path_min_level`：关键路径最低日志级别（默认 `exception`）
- `silent_exception_ban.auxiliary_path_min_level`：辅助路径最低日志级别（默认 `warning`）
- 禁止在代码中硬编码上述参数

**适用场景**：
- 多进程共享浏览器实例（Worker 浏览器 + 登录子进程）
- token 与身份 Cookie 分离管理的认证体系（如 MTOP API 的 `_m_h5_tk`）
- 续期回调通过浏览器导航触发服务端刷新的场景
- 多存储介质同步（浏览器内存 + JSON + SQLite）
- 所有使用 loguru 的 Python 项目
- 所有关键路径的异常处理

**不适用场景**：
- 单进程内完成登录和请求（token 随 Cookie 一起更新）
- 无 token 机制的纯 Cookie 认证
- 单存储介质的 token 续期（无 JSON/SQLite 同步需求）
- 使用标准库 logging 的项目（用 `%s`）
- 测试代码中的异常断言（`pytest.raises`）

**与其他规则区别**：
- 与 #25（批量处理四要素）的区别：#25 关注批处理的熔断/进度持久化；#84 关注 Cookie 与 token 状态的分离与一致性
- 与 step 229（多级自愈）的区别：step 229 关注会话失效时的多级恢复链路；#84 关注日常运行中 Cookie 与 token 的状态同步
- 与 step 230（熔断标志重置）的区别：step 230 关注重试前重置熔断标志；#84 关注 token 刷新时间戳的重置时机（独立于 Cookie 补注入）
- 与 step 202（异常日志语义保留）的区别：step 202 聚焦"日志必须有堆栈和上下文"；#84 的静默异常禁止聚焦"异常处理不能完全静默"
- 与 step 231（诊断日志模式）的区别：step 231 聚焦"关键路径结构化诊断日志"；#84 的日志占位符聚焦"loguru 占位符风格正确性"

**复盘来源**：2026-06-26 `FAIL_SYS_ILLEGAL_ACCESS::非法请求` 问题修复。根因链：
1. Worker 浏览器启动时生成匿名 `_m_h5_tk` token，登录后身份 Cookie 注入但 token 未刷新
2. 第一次修复将 token 重置绑定在"补注入 Cookie"分支内，但浏览器已持有身份 Cookie（无需补注入），重置逻辑未执行
3. TokenRenewer 续期回调导航刷新 token 后未回写 CookieStore JSON，JSON 中 token 永远是旧值
4. loguru 日志使用 `%s` 占位符导致输出字面量而非实际值
5. 续期回写 CookieStore 的 `try/except` 块为 `except: pass`，失败时无日志

修复：token 重置独立于 Cookie 补注入 → 续期后回写 JSON → `%s` 改 `{}` → `except: pass` 改 `logger.warning`。对应 step 243/244/245/246。

---

## 元规则 #85：关键路径可观测性与状态同步三要素（meta-rule #85）🆕v4.52.0

**一句话概述**：多步骤关键路径必须有进度编号日志 + 超时异常用户友好语义 + 组件复用状态同步重置 + 字段覆盖集合选择标准，四者缺一即 Bug。

**关键判断信号**：
- `grep "async def _do_\|async def _collect_\|async def _login_" src/` 找到多步骤流程 → 检查步骤级编号日志（step 247）
- `grep "asyncio.wait_for" src/` 找到超时包裹 → 检查 `except asyncio.TimeoutError` 专门分支（step 248）
- `grep "useState" frontend/src/` 找到含内部状态的组件 → 检查是否在列表/展开行/Tab 面板中使用 + prop 变化时是否重置（step 249）
- `grep "_ALWAYS_OVERWRITE\|_COALESCE" src/` 找到集合定义 → 检查采集可能返回空的字段是否误入强制覆盖集合（step 250）

**核心机制**（审查时必须理解）：
1. **多步骤进度编号日志**：≥3 步骤的关键路径在每个步骤前打 `步骤X/N` 编号日志，超时或失败时可从日志快速定位卡在哪一步
2. **超时异常用户友好语义**：`asyncio.TimeoutError` 必须有专门异常分支（在 `except Exception` 之前），错误信息含超时秒数+可能原因+建议操作
3. **React 组件复用状态重置**：组件因 `rowKey` 不变被复用时，`useState` 状态不自动重置；内部状态依赖的 prop 变化时，必须用 `useEffect` 重置
4. **字段覆盖集合选择标准**：`_ALWAYS_OVERWRITE` 只放"每次采集必定获取到+新值更准确"的字段；采集可能返回空的字段走 `_coalesce`

**配置驱动**（所有参数从 config.yaml 读取，禁止硬编码）：
- `step_progress_log`：步骤描述模板、关键标识字段名、工作流步骤定义
- `timeout_error_semantics`：各操作超时秒数、错误信息模板、可能原因映射、建议操作映射
- `component_reuse_state_reset`：组件重置规则字典、重置默认值、复用场景列表
- `overwrite_set_selection`：强制覆盖字段清单、coalesce 字段清单、选择标准说明

**适用场景**：
- 多步骤浏览器自动化流程（抢单/采集/登录）
- 面向用户的异步超时场景（需用户根据错误信息采取操作）
- 列表项/展开行/Tab 面板组件（可能被 React 复用）
- 采集-存储链路（官方采集→items/sellers 表，有强制覆盖/coalesce 双策略）

**不适用场景**：
- 单步操作（无步骤概念）
- 内部超时重试（不直接面向用户）
- 每次都创建新实例的组件（key 唯一）
- 单一覆盖策略（无 coalesce 逻辑）

**与其他规则区别**：
- 与 #84（Cookie-Token 一致性）的区别：#84 关注 Cookie 与 token 状态同步；#85 关注关键路径的可观测性与数据合并的字段选择
- 与 step 50（异步操作整体超时保护）的区别：step 50 聚焦"必须加超时保护"；step 248 聚焦"超时异常的用户友好语义"
- 与 step 231（诊断日志模式）的区别：step 231 聚焦"自愈链路结构化上下文"；step 247 聚焦"多步骤流程进度编号定位"
- 与 step 159（useEffect 副作用清理）的区别：step 159 聚焦"组件卸载时清理副作用"；step 249 聚焦"组件复用时重置内部状态"
- 与 step 17（字段覆盖策略）的区别：step 17 定义分类覆盖基本原则；step 250 细化 `_ALWAYS_OVERWRITE` 集合字段选择标准

**复盘来源**：2026-07-22 三个关联 Bug 修复：
1. 抢单超时：`buyer.py` `_do_buy` 无步骤级日志 + `TimeoutError` 走通用分支 → 用户看到"未知异常"无法判断是超时还是会话失效。修复：添加 `步骤1/4`~`步骤4/4` 编号日志 + `except asyncio.TimeoutError` 专门分支
2. ThumbCell 状态残留：`frontend/src/pages/Evaluations/index.tsx` `ThumbCell` 组件因 `rowKey` 不变被 React 复用，`errored` 状态不自动重置 → 官方采集更新图片 URL 后仍显示占位图。修复：添加 `useEffect(() => { setErrored(false) }, [url])`
3. image_urls 被清空：`api_evaluations.py` `image_urls` 在 `_ALWAYS_OVERWRITE` 集合中，采集未获取到图片时 `None` 覆盖旧值 → 官方采集后图片消失。修复：将 `image_urls` 移出 `_ALWAYS_OVERWRITE` 走 `_coalesce`

对应 step 247/248/249/250。

---

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

---

## 87. 配置字段五层链路覆盖（CONFIG-FIELD-FIVE-LAYER-COVERAGE）🆕v4.55.0

> 与 B-REVIEW-247（backend 配置字段五层链路审查）/ F-REVIEW-201（前端配置字段编辑控件覆盖审查）/ F-REVIEW-202（配置字段恢复默认机制审查）/ xianyu-auto-testing 模式 K（DB 脏值诊断测试）对应。
> 与 #35（前后端字段契约单一可信源）的关系：#35 关注"字段派生来源标注"；#87 关注"配置字段从 DB 到 UI 的五层链路完整性"。

**问题背景**：智能客服新建会话时欢迎语显示乱码 `'??????????!'`。根因是 `chatbot_config` 表的 `welcome_message` 字段被写入了占位符字符串（可能是某次测试或迁移脚本残留），但该字段缺失五层链路中的三层：(1) `get_config` API 未返回该字段，前端拿不到值只能显示原始 DB 脏值；(2) `update_config` API 不支持该字段更新，用户无法通过 UI 修正；(3) 前端 `Config.tsx` 无编辑控件，用户无法修改；(4) 无"恢复默认"机制，脏值无法清除。同一问题模式在多个配置字段上反复出现（AI 快捷预设 API Key、评分阈值、Cookie 域白名单等），根因都是"新增 DB 字段时只完成了 schema 定义，未补全全链路"。

**核心原则**：
1. **五层链路完整性**：用户可编辑的配置字段必须同时覆盖五层，缺一即 Bug：
   - 第 1 层：DB schema（字段定义 + 默认值 + NOT NULL 约束）
   - 第 2 层：`get_config` API 返回该字段（前端能读到）
   - 第 3 层：`update_config` API 支持该字段更新（前端能写入）
   - 第 4 层：前端 `types.ts` 类型定义（TS 类型安全）
   - 第 5 层：前端 `Config.tsx` 编辑控件（用户可操作 UI）
2. **空值处理语义**：`update_config` 收到空值时应当**删除**该配置项（恢复默认），而非写入空字符串。空字符串是有效值（会覆盖默认值），空值/缺省才是"恢复默认"的语义。**禁止**用空字符串表示"恢复默认"。
3. **恢复默认机制**：每个配置字段必须提供"恢复默认"入口（按钮/菜单），调用 `delete_config` 删除 DB 记录，让 `get_config` 回退到代码内默认值。**禁止**通过写入"默认值字符串"来恢复默认——代码内默认值变更后，DB 中的"默认值字符串"会过时。
4. **占位符禁止**：DB schema 的默认值不得是占位符字符串（如 `'??????????!'`、`'TODO'`、`'placeholder'`）。默认值必须是真实可用的值，或留空（NULL）让 `get_config` 回退到代码内默认值。
5. **脏值检测与清除**：`get_config` 读取字段时必须验证值的有效性（如非占位符、在合法范围内），发现脏值时回退到代码内默认值并记日志。

**判断信号**：
- `grep "ALTER TABLE.*ADD COLUMN" migrations/` 找到新增字段 → 检查五层链路是否齐全
- `grep "placeholder\|TODO\|????????" src/` → 占位符字符串
- `get_config` 返回字段数 < DB schema 字段数 → 第 2 层缺失
- `update_config` 接受字段数 < DB schema 字段数 → 第 3 层缺失
- 前端 `Config.tsx` 编辑控件数 < `types.ts` 字段数 → 第 5 层缺失
- 用户报告"显示乱码/问号/方块" → 占位符或编码问题，参考模式 K

**配置驱动**：
- `config_field_coverage.enabled`：是否启用五层链路检查（默认 true）
- `config_field_coverage.layers`：五层链路定义（默认 `['db_schema', 'get_config', 'update_config', 'types_ts', 'config_tsx']`）
- `config_field_coverage.empty_value_action`：空值处理策略（默认 `delete`，可选 `delete` / `write_empty` / `reject`）
- `config_field_coverage.restore_default_mechanism`：恢复默认机制要求（默认 `required`）
- `config_field_coverage.placeholder_patterns`：占位符检测正则列表（默认 `['\\?{4,}', 'TODO', 'placeholder', 'FIXME']`）
- `config_field_coverage.dirty_value_fallback`：脏值回退策略（默认 `code_default`，回退到代码内默认值）
- `config_field_coverage.db_table`：配置表名（默认 `chatbot_config`）
- `config_field_coverage.config_api_module`：配置 API 模块路径（默认 `web/routes/api_config.py`）
- `config_field_coverage.frontend_types_file`：前端类型文件（默认 `frontend/src/types.ts`）
- `config_field_coverage.frontend_config_page`：前端配置页（默认 `frontend/src/pages/Config.tsx`）
- 禁止在代码中硬编码上述参数

**适用场景**：
- 用户可编辑的配置项（欢迎语、API Key、阈值、开关、白名单）
- DB 持久化的配置表（key-value 结构或字段表）
- 需要提供"恢复默认"功能的配置项
- 迁移脚本新增配置字段的场景

**不适用场景**：
- 代码内常量（非用户可编辑）
- 环境变量（通过 .env 管理，非 DB）
- 启动参数（通过 CLI 管理，非 DB）
- 只读配置（仅后端使用，前端无 UI）

**与其他规则区别**：
- 与 #35（前后端字段契约单一可信源）的区别：#35 关注"字段派生来源标注"；#87 关注"配置字段五层链路完整性"
- 与 #30（业务关键字常量集中管理）的区别：#30 关注"业务文案常量"；#87 关注"用户可编辑配置字段"
- 与 #33（注册式资源三件套契约）的区别：#33 关注"资源注册的五层契约"；#87 关注"配置字段的五层链路"
- 与 xianyu-auto-testing 模式 K 的关系：模式 K 聚焦"DB 脏值的诊断测试"；#87 聚焦"配置字段五层链路的预防性规范"

**复盘来源**：2026-07-22 智能客服欢迎语乱码 Bug。根因链：
1. `chatbot_config.welcome_message` 字段被写入占位符 `'??????????!'`
2. `get_config` API 未返回 `welcome_message`，前端无法读取真实值
3. `update_config` API 不支持 `welcome_message` 更新，用户无法修正
4. 前端 `Config.tsx` 无 textarea 编辑控件
5. 无"恢复默认"按钮，脏值无法清除

修复：
1. `get_config` 返回 `welcome_message` 字段
2. `update_config` 支持该字段更新（空值时 `delete_config` 恢复默认）
3. 前端 `Config.tsx` 新增 textarea 编辑控件
4. 新增"恢复默认"按钮（disabled-when-default），调用 `delete_config`
5. 清除 DB 中的占位符脏值

对应 step 254/255/256/257。

---

## 88. 跨层数据契约同步流程（CROSS-LAYER-CONTRACT-SYNC）🆕v4.55.0

> 与 B-REVIEW-248（backend 数据覆盖策略集合管理审查）/ F-REVIEW-200（前端 React 组件复用状态重置审查）/ xianyu-auto-testing 模式 M（跨层数据契约一致性测试）对应。
> 与 #85（关键路径可观测性与状态同步三要素）的关系：#85 的第 4 点定义了 `_ALWAYS_OVERWRITE` 集合选择标准；#88 定义了"发现字段跨层不一致时的修复流程"。

**问题背景**：用户反馈点击商品标题跳转至官方详细商品页面时，商品评估明细信息和商品图片未更新。根因是两个关联缺陷：(1) 前端 `ThumbCell` 组件在图片 URL 更新后未重置 `errored` 状态，导致加载失败的占位图残留——React 组件因 `rowKey` 不变被复用时，`useState` 状态不自动重置；(2) 后端在官方采集未获取到图片时，将 `items` 表的 `image_urls` 字段覆盖为 `None`，清空了旧数据——`image_urls` 误入 `_ALWAYS_OVERWRITE` 集合，应走 `_coalesce`。同类问题反复出现在 `brand`、`display`、`seller_credit` 等字段上，根因都是"修改字段覆盖策略时未走完整的跨层契约同步流程"。

**核心原则**：
1. **跨层契约同步五步流程**：发现字段跨层不一致时，必须按以下五步修复，缺步即遗留 Bug：
   - 步骤 1：识别跨层字段——找出前端消费、后端产出、DB 存储的三层字段
   - 步骤 2：判断覆盖策略——该字段属于 `_ALWAYS_OVERWRITE`（强制覆盖）/ `_coalesce`（旧值优先）/ `_NULL_SAFE`（空值不清空）哪个集合
   - 步骤 3：前端状态重置——React 组件复用场景，URL/props 变化时重置 `errored`/`loaded`/`loading` 等内部状态
   - 步骤 4：后端写回保护——外部 API 返回空值时不清空旧有效数据，空值视为"本次未取到"而非"应清空"
   - 步骤 5：跨层一致性验证——后端字段集合改动后，前端 `types.ts` 同步标注派生来源
2. **空值语义区分**：
   - `None`/`null`（显式空值）：API 返回了字段但值为空，语义是"应清空"，可覆盖
   - 字段缺失（API 未返回该字段）：语义是"本次未取到"，应走 `_coalesce` 保留旧值
   - **禁止**把"字段缺失"当作"显式空值"处理——采集可能因网络/权限/页面结构变化而未取到字段，这不代表字段值应为空
3. **React 组件复用状态重置**：组件因 `rowKey` 不变被 React 复用时，`useState` 状态不自动重置。内部状态依赖的 prop（如 `url`、`src`、`id`）变化时，必须用 `useEffect` 重置相关状态。**禁止**假设"props 变化时 React 会自动重置内部状态"——React 的复用机制是为了性能，不会重置 state。
4. **覆盖策略集合管理**：`_ALWAYS_OVERWRITE` 集合只放"每次采集必定获取到 + 新值更准确"的字段（如 `title`、`price`、`updated_at`）；采集可能返回空的字段（如 `image_urls`、`brand`、`description`）走 `_coalesce`。**禁止**把可能返回空的字段放入 `_ALWAYS_OVERWRITE`——采集失败时会用 `None` 覆盖旧有效数据。
5. **前后端契约同步**：后端 `ResponseModel` / DB Row 字段变更时，前端 `types.ts` 必须同步更新并标注派生来源（`// derived from backend ResponseModel.xxx`）。**禁止**后端字段变更但前端 `types.ts` 无响应。

**判断信号**：
- `grep "_ALWAYS_OVERWRITE" src/` 找到集合定义 → 检查每个字段是否"每次采集必定获取到"
- `grep "image_urls\|brand\|description" src/` 找到可能返回空的字段 → 检查是否在 `_ALWAYS_OVERWRITE` 中（应在 `_coalesce`）
- `grep "useState.*errored\|useState.*loaded\|useState.*loading" frontend/` 找到含内部状态的组件 → 检查是否在列表/展开行/Tab 面板中使用 + prop 变化时是否 `useEffect` 重置
- `grep "rowKey" frontend/` 找到列表组件 → 检查 `rowKey` 是否唯一（不唯一会导致复用）
- 后端 `ResponseModel` 新增字段但前端 `types.ts` 无对应 → 契约不同步

**配置驱动**：
- `cross_layer_contract_sync.enabled`：是否启用跨层契约同步检查（默认 true）
- `cross_layer_contract_sync.always_overwrite_set`：强制覆盖字段白名单（默认 `['title', 'price', 'updated_at', 'status']`）
- `cross_layer_contract_sync.coalesce_set`：coalesce 字段白名单（默认 `['image_urls', 'brand', 'description', 'seller_credit']`）
- `cross_layer_contract_sync.null_safe_set`：空值不清空字段白名单（默认 `[]`）
- `cross_layer_contract_sync.empty_value_semantics`：空值语义定义（默认 `{'none': 'explicit_clear', 'missing': 'keep_old'}`）
- `cross_layer_contract_sync.component_reuse_reset_fields`：组件复用需重置的状态字段（默认 `['errored', 'loaded', 'loading']`）
- `cross_layer_contract_sync.rowkey_uniqueness_required`：rowKey 唯一性要求（默认 true）
- `cross_layer_contract_sync.frontend_types_annotation_required`：前端 types.ts 派生来源标注要求（默认 true）
- `cross_layer_contract_sync.scan_globs`：扫描的文件 glob（默认 `['src/xianyu_hunter/web/routes/api_*.py', 'frontend/src/types.ts', 'frontend/src/pages/**/*.tsx']`）
- 禁止在代码中硬编码上述参数

**适用场景**：
- 前后端契约字段调整（新增/删除/重命名字段）
- DB 字段覆盖策略变更（`_ALWAYS_OVERWRITE` ↔ `_coalesce` 互转）
- React 组件在列表/展开行/Tab 面板中复用（`rowKey` 不变）
- 采集-存储链路（外部 API → DB → 前端展示）
- 官方采集/重采触发数据更新的场景

**不适用场景**：
- 纯前端 UI 样式调整（无数据契约变更）
- 纯后端内部计算逻辑（无前端消费）
- 一次性数据迁移（无持续同步需求）
- 每次都创建新实例的组件（`key` 唯一，无复用问题）
- 单一覆盖策略（无 `_coalesce` 逻辑）

**与其他规则区别**：
- 与 #85（关键路径可观测性与状态同步三要素）的区别：#85 定义了 `_ALWAYS_OVERWRITE` 集合选择标准（聚焦"哪个集合"）；#88 定义了"发现不一致时的五步修复流程"（聚焦"怎么修"）
- 与 #35（前后端字段契约单一可信源）的区别：#35 关注"字段派生来源标注"（静态契约）；#88 关注"字段覆盖策略变更时的动态同步流程"
- 与 #87（配置字段五层链路覆盖）的区别：#87 关注"用户可编辑配置字段"的链路完整性；#88 关注"业务数据字段"的跨层覆盖策略一致性
- 与 step 249（React 组件复用状态重置）的关系：step 249 是 #88 第 3 步的具体实现
- 与 step 250（字段覆盖集合选择标准）的关系：step 250 是 #88 第 2 步的具体实现

**复盘来源**：2026-07-22 商品评估明细/图片未更新 Bug。根因链：
1. 前端 `ThumbCell` 组件因 `rowKey` 不变被 React 复用，图片 URL 更新后 `errored` 状态未重置 → 旧的占位图残留
2. 后端 `api_evaluations.py` 中 `image_urls` 在 `_ALWAYS_OVERWRITE` 集合，官方采集未获取到图片时 `None` 覆盖旧值 → 图片消失

修复：
1. 前端 `index.tsx` 添加 `useEffect(() => { setErrored(false) }, [url])` 重置 errored 状态
2. 后端将 `image_urls` 移出 `_ALWAYS_OVERWRITE`，走 `_coalesce` 保留旧值

对应 step 258/259/260。

---

## 90. 回退构造保留关联键（FALLBACK-PRESERVE-KEY）🆕v4.57.0

> 与 B-REVIEW-251（backend 回退构造关联键审查）/ F-REVIEW-206（前端回退构造关联键审查）/ xianyu-auto-testing 模式 O（回退构造关联键一致性测试）对应。
> 与 #88（跨层数据契约同步流程）的关系：#88 关注"字段覆盖策略"的跨层一致性；#90 关注"回退构造实体"时关联键的完整性——两者都可能因"遗漏字段"导致下游逻辑被跳过。

**问题背景**：AI 评估接口返回结果缺少 `price_range` 字段。根因是 `get_eval_payload_by_item` 方法只查询 `EventRow.payload` 不查询 `EventRow.task_id`，导致从 payload 回退构造的伪 item dict 无 `task_id` 字段。下游价格区间查询 `if task_id:` 条件判断因 `task_id` 为 None 被跳过，价格区间数据未注入 LLM prompt。同类问题反复出现在"从部分数据回退构造实体"的场景——回退构造的实体遗漏了下游依赖的关联键，导致下游条件判断被静默跳过。

**核心原则**：
1. **回退构造必须保留关联键**：从事件 payload / 缓存 / 部分数据回退构造实体时，必须同时查询并注入下游依赖的所有关联键（如 `task_id`、`user_id`、`seller_id`）。**禁止**只取 payload 内容而不取关联键——下游条件判断 `if task_id:` 会因关联键缺失而静默跳过逻辑。
2. **下游条件判断前校验键存在**：回退构造的实体传入下游时，下游应在条件判断前校验关联键是否存在，而非假设关联键一定有值。若关联键缺失，应记录 WARNING 日志而非静默跳过。
3. **回退路径必须可观测**：回退构造实体时必须记录日志（包含实体 ID、关联键值、回退来源），禁止静默回退。日志用于排查"为什么下游逻辑被跳过"。
4. **关联键清单管理**：每个回退构造点必须维护"下游依赖的关联键清单"，查询时必须同时取这些键。**禁止**在回退构造函数中只取业务字段而遗漏关联键。

**判断信号**：
- `grep "payload.get\|fallback" src/` 找到回退构造逻辑 → 检查是否遗漏 `task_id`/`user_id`/`seller_id` 等关联键
- `grep "if task_id:\|if user_id:\|if seller_id:" src/` 找到下游条件判断 → 检查上游回退构造是否注入了该键
- `grep "setdefault.*task_id\|setdefault.*user_id" src/` 找到关联键注入 → 确认回退构造路径有此逻辑
- 回退构造函数只查询 `payload` 字段而不查询关联键字段 → 视为违规

**配置驱动**：
- `fallback_preserve_key.enabled`：是否启用回退构造关联键检查（默认 true）
- `fallback_preserve_key.required_keys`：回退构造必须保留的关联键清单（默认 `['task_id', 'user_id', 'seller_id']`）
- `fallback_preserve_key.log_on_missing_key`：关联键缺失时是否记录 WARNING（默认 true）
- `fallback_preserve_key.scan_globs`：扫描的文件 glob（默认 `['src/xianyu_hunter/infra/repo_*.py', 'src/xianyu_hunter/web/routes/api_*.py']`）
- 禁止在代码中硬编码上述参数

**适用场景**：
- 事件 payload 回退构造实体（如从 eval 事件 payload 回退构造 item dict）
- 缓存回退构造实体（如从缓存部分数据回退构造完整对象）
- 数据库多表回退查询（如从事件表回退查询时需要同时取关联表的外键）
- 任何"从部分数据构造实体 + 下游依赖关联键"的场景

**不适用场景**：
- 直接从主表查询完整实体（无回退，字段齐全）
- 纯展示场景（无下游关联查询需求）
- 一次性脚本（无持续维护需求）

**与其他规则区别**：
- 与 #88（跨层数据契约同步流程）的区别：#88 关注"字段覆盖策略"跨层一致性；#90 关注"回退构造实体"时关联键完整性
- 与 #35（前后端字段契约单一可信源）的区别：#35 关注"字段派生来源标注"；#90 关注"回退构造时关联键不遗漏"
- 与 #87（配置字段五层链路覆盖）的区别：#87 关注"用户配置字段"链路完整性；#90 关注"业务数据回退构造"时关联键完整性

**复盘来源**：2026-07-22 AI 评估 price_range 注入 Bug。根因链：
1. `repo_events.py` 的 `get_eval_payload_by_item` 只查 `EventRow.payload` 不查 `EventRow.task_id`
2. `api_ai.py` 回退构造伪 item dict 时 `task_id` 为 None
3. 价格区间查询 `if task_id:` 条件判断因 `task_id` 为 None 被跳过
4. AI 评估结果缺少 `price_range` 字段

修复：
1. `repo_events.py` 同时查询 `EventRow.payload` 和 `EventRow.task_id`，将 `task_id` 注入 payload dict
2. `api_ai.py` 回退构造伪 item 时从 payload 提取 `task_id`

对应 step 261/262/263。

---

## 91. 时间窗口查询全量回退（TIME-WINDOW-FULL-FALLBACK）🆕v4.57.0

> 与 B-REVIEW-252（backend 时间窗口全量回退审查）对应。
> 与 #90（回退构造保留关联键）的关系：#90 确保"关联键不缺失"；#91 确保"时间窗口无数据时有回退"——两者都防止下游逻辑被静默跳过。

**问题背景**：AI 评估接口查询同类物品已售价格区间时，`range_days=30` 返回 `source: "empty"`，但 `range_days=0`（全量）有 58 条数据。根因是数据库中商品数据时间较早，超过 30 天窗口。价格区间数据缺失导致 LLM 无法引用价格参考。同类问题反复出现在"基于时间窗口的统计查询"场景——窗口内无数据时直接返回空结果，而非回退到全量查询。

**核心原则**：
1. **时间窗口查询必须有全量回退**：基于时间窗口的统计查询（如价格区间、销量统计、热度排名），当窗口内无数据时必须自动回退到全量查询（`range_days=0`）。**禁止**窗口无数据时直接返回空结果——统计数据缺失会导致下游决策无参考。
2. **回退必须可观测**：窗口回退时必须记录日志（包含窗口参数、窗口内数据量、回退后数据量），禁止静默回退。日志用于排查"为什么数据量突然变少"。
3. **回退结果必须标注 source**：回退查询的结果必须标注数据来源（`source` 字段），区分"窗口内有数据"和"回退到全量"。下游消费方根据 `source` 判断数据时效性。
4. **窗口参数配置驱动**：时间窗口参数（如 `range_days`）必须在配置文件管理，**禁止**硬编码在代码中。

**判断信号**：
- `grep "range_days" src/` 找到时间窗口查询 → 检查窗口无数据时是否有全量回退
- `grep "source.*empty\|source.*full" src/` 找到 source 标注 → 确认回退时 source 有变化
- `grep "range_days.*30\|range_days.*7\|range_days.*90" src/` 找到硬编码窗口 → 应从配置读取
- 时间窗口查询返回 empty 但无回退逻辑 → 视为违规

**配置驱动**：
- `time_window_fallback.enabled`：是否启用时间窗口全量回退检查（默认 true）
- `time_window_fallback.default_window_days`：默认时间窗口天数（默认 30）
- `time_window_fallback.fallback_to_full`：窗口无数据时是否回退到全量（默认 true）
- `time_window_fallback.log_on_fallback`：回退时是否记录日志（默认 true）
- `time_window_fallback.source_field_name`：结果来源标注字段名（默认 `'source'`）
- `time_window_fallback.scan_globs`：扫描的文件 glob（默认 `['src/xianyu_hunter/web/routes/api_*.py', 'src/xianyu_hunter/web/routes/price_dashboard.py']`）
- 禁止在代码中硬编码上述参数

**适用场景**：
- 价格区间统计查询（如已售商品价格区间）
- 销量统计查询（如近 N 天销量排名）
- 热度排名查询（如近 N 天搜索热度）
- 任何"基于时间窗口的聚合统计 + 数据可能超出窗口"的场景

**不适用场景**：
- 实时性要求高的查询（如当前库存、实时价格——回退到全量会引入过期数据）
- 窗口语义即为"只看这个时间段"的查询（如"近 7 天新增商品"——回退到全量会改变语义）
- 增量同步查询（如"自上次同步以来的变更"——回退会重复处理）

**与其他规则区别**：
- 与 #90（回退构造保留关联键）的区别：#90 确保"关联键不缺失"（实体构造层面）；#91 确保"时间窗口无数据时有回退"（查询策略层面）
- 与 #22（批处理熔断断模式）的区别：#22 关注"批处理失败时保存进度"；#91 关注"时间窗口查询无数据时回退到全量"

**复盘来源**：2026-07-22 价格区间 30 天窗口返回 empty Bug。根因链：
1. `api_ai.py` 查询价格区间时用 `range_days=30`
2. 数据库中商品数据时间较早，超过 30 天窗口
3. 查询返回 `source: "empty"`，无回退逻辑
4. AI 评估结果缺少价格区间参考

修复：
1. `api_ai.py` 增加 30 天查询返回 empty 时用 `range_days=0` 重查
2. 日志记录回退行为和结果

对应 step 264/265。

---

## 92. PowerShell 外部命令显式后缀（POWERSHELL-EXPLICIT-SUFFIX）🆕v4.57.0

> 与 B-REVIEW-253（backend PowerShell 外部命令调用审查）/ xianyu-auto-testing 模式 O 的测试基础设施部分对应。
> 与 #79（长时交互式外部命令两阶段异步模式）的关系：#79 关注"长时命令的异步模式"；#92 关注"PowerShell 环境下外部命令的别名冲突"。

**问题背景**：在 PowerShell 中执行 `curl -s -o $null -w "%{http_code}"` 时报错 `Missing an argument for parameter 'SessionVariable'`。根因是 PowerShell 的 `curl` 是 `Invoke-WebRequest` 的别名，不是真正的 curl。`Invoke-WebRequest` 不支持 `-s`/`-w` 等 curl 参数。同类问题还出现在 `wget`（PowerShell 中也是 `Invoke-WebRequest` 别名）等命令上。此外，PowerShell 中传递 JSON body 时引号转义复杂（`-d "{\"key\":\"value\"}"` 和 `-d '{"key":"value"}'` 都可能失败），应通过文件传递。

**核心原则**：
1. **PowerShell 中调用外部命令必须用 `.exe` 后缀**：在 PowerShell 中调用 `curl`/`wget`/`git` 等外部命令时，必须用 `curl.exe`/`wget.exe`/`git.exe` 形式，避免触发 PowerShell 别名冲突。**禁止**在 PowerShell 脚本中用裸 `curl`——它会被解析为 `Invoke-WebRequest` 别名。
2. **复杂参数通过文件传递**：PowerShell 中传递 JSON body 等复杂参数时，应将内容写入临时文件，用 `-d "@<file>"` 形式传递。**禁止**在命令行中用多层引号转义——PowerShell 的引号转义规则与 bash 不同，容易出错。
3. **长命令拆分执行**：PowerShell 控制台缓冲区有限，超长命令可能导致 `PSReadLine` 渲染异常（`System.ArgumentOutOfRangeException`）。复杂命令应拆分为多步执行，每步验证结果。
4. **命令调用必须可重试**：外部命令调用失败时，必须记录错误信息并支持重试。**禁止**在外部命令失败时静默继续。

**判断信号**：
- `grep "^curl " scripts/` 或 `grep " curl " scripts/` 找到裸 curl → 应改为 `curl.exe`
- `grep "^wget " scripts/` 找到裸 wget → 应改为 `wget.exe`
- `grep '-d "' scripts/` 找到行内 JSON body → 应改为文件传递
- `grep "Invoke-WebRequest" scripts/` 找到 PowerShell 原生命令 → 确认是否为有意选择（而非 curl 别名冲突）

**配置驱动**：
- `powershell_explicit_suffix.enabled`：是否启用 PowerShell 外部命令后缀检查（默认 true）
- `powershell_explicit_suffix.conflicting_aliases`：PowerShell 别名冲突命令清单（默认 `['curl', 'wget', 'rmdir']`）
- `powershell_explicit_suffix.required_suffix`：必须添加的后缀（默认 `'.exe'`）
- `powershell_explicit_suffix.json_body_via_file`：JSON body 是否必须通过文件传递（默认 true）
- `powershell_explicit_suffix.command_max_length`：单条命令最大长度（默认 200，超过则拆分）
- `powershell_explicit_suffix.scan_globs`：扫描的文件 glob（默认 `['scripts/*.ps1', '.trae/skills/*/scripts/*.ps1']`）
- 禁止在代码中硬编码上述参数

**适用场景**：
- PowerShell 脚本中调用 curl/wget 等外部命令
- PowerShell 脚本中传递 JSON body 等复杂参数
- Windows 环境下的接口测试脚本
- CI/CD 流水线中的 PowerShell 脚本

**不适用场景**：
- bash/sh 脚本（无别名冲突）
- Python/Node.js 脚本中的 subprocess 调用（不经过 PowerShell 别名层）
- PowerShell 原生命令（如 `Invoke-WebRequest`、`Invoke-RestMethod`——有意使用而非别名冲突）

**与其他规则区别**：
- 与 #79（长时交互式外部命令两阶段异步模式）的区别：#79 关注"长时命令的异步模式"；#91 关注"PowerShell 别名冲突"
- 与 #78（Cookie 文件路径必须使用 Path 多参数构造）的区别：#78 关注"文件路径安全构造"；#91 关注"外部命令别名冲突"

**复盘来源**：2026-07-22 PowerShell 环境下的接口测试问题。根因链：
1. PowerShell 中 `curl` 是 `Invoke-WebRequest` 别名，不支持 `-s`/`-w` 参数
2. JSON body `-d "{\"key\":\"value\"}"` 因引号转义失败
3. 超长命令导致 PSReadLine 渲染异常

修复：
1. 改用 `curl.exe` 调用真正的 curl
2. 将 JSON 写入临时文件，用 `-d "@<file>"` 传递
3. 将复杂命令拆分为多步执行

对应 step 266/267/268。

---

## 93. 性能优化量化验证（PERFORMANCE-QUANTITATIVE-VERIFICATION）🆕v4.59.0

> 与 B-REVIEW-262~267（backend 性能审查）/ F-REVIEW-211~213（frontend 性能审查）/ xianyu-auto-testing 模式 R（性能优化回归测试）对应。
> 与 #26（关键路径异常保留 traceback）的区别：#26 关注"异常日志完整性"；#93 关注"性能优化的量化验证"。

**问题背景**：本次对话中实施了 8 个性能优化方案（批量 upsert / run_in_executor / 60 秒缓存 / SQL 层过滤 / list+count 合并 / useMemo / 优先级锁 / SSE 流式响应），其中缓存 TTL 从 5 秒修正为 60 秒后，缓存命中响应时间从 4240ms 降至 1ms（4240 倍提升）。但如果缺乏量化验证，优化效果无法确认——"感觉变快了"不是有效的验证证据。

**核心原则**：
1. **每个性能优化方案必须定义可量化指标**：指标必须包含"优化前值"和"优化后值"（如响应时间 4240ms → 1ms、缓存命中率 0% → 99%），禁止用"感觉变快了"等主观描述。
2. **必须通过运行时测试验证**：静态代码分析不能作为性能优化的验证证据，必须通过运行时测试（curl/API 调用/浏览器 E2E）获取实际指标。
3. **验证证据必须包含在优化说明中**：优化说明必须包含测试方法、测试数据、优化前/后指标对比表格。
4. **缓存类优化必须验证缓存命中率**：缓存优化必须验证缓存命中场景（重复请求命中缓存）和缓存失效场景（TTL 过期后重新触发操作）。

**判断信号**：
- `grep "优化前\|优化后\|before\|after" docs/` 找不到量化指标 → 补充量化验证
- `grep "缓存命中\|cache hit\|cache_hit" src/` 找不到缓存命中日志 → 补充缓存命中验证
- 性能优化说明中只有代码变更说明，无运行时测试结果 → 补充运行时验证

**配置驱动**：
- `performance_verification.enabled`：是否启用量化验证检查（默认 true）
- `performance_verification.required_metrics`：必须包含的指标类型（默认 `['response_time', 'cache_hit_rate']`）
- `performance_verification.runtime_test_required`：是否必须运行时测试（默认 true）
- `performance_verification.cache_hit_threshold_ms`：缓存命中响应时间阈值（默认 10ms，超过则视为未命中）
- 禁止在代码中硬编码上述参数

**适用场景**：
- 所有性能优化任务（响应时间优化、缓存优化、查询优化、并发优化）
- 性能优化代码审查（需验证优化说明中是否包含量化指标）
- 性能优化回归测试（需验证优化效果是否持续）

**不适用场景**：
- 功能开发任务（无需量化指标）
- UI 调整（主观体验为主，但交互响应时间仍需量化）
- 纯代码重构（无性能影响时无需量化）

**与其他规则区别**：
- 与 #26（关键路径异常保留 traceback）的区别：#26 关注"异常日志完整性"；#93 关注"性能优化的量化验证"
- 与 PS-022（性能优化必须有量化验证指标）的关系：PS-022 是本元规范在 performance-and-security-patterns.md 的落地条文

**复盘来源**：2026-07-22 闲鱼猎人实时查询性能优化。根因链：
1. 实施缓存优化时 TTL 设为 5 秒，小于操作耗时 15-20 秒
2. 缺乏量化验证，未发现缓存命中率几乎为零
3. E2E 测试时才发现缓存未命中（响应时间仍为 4240ms）
4. 修正为 60 秒后缓存命中响应时间降至 1ms（4240 倍提升）

修复：
1. TTL 从 5 秒修正为 60 秒
2. 补充缓存命中验证（首次请求触发搜索、60 秒内重复请求命中缓存）
3. 优化说明中包含量化指标对比表格

对应 step 269/270。

---

## 94. 缓存 TTL 合理性校验（CACHE-TTL-RATIONALITY-CHECK）🆕v4.59.0

> 与 B-REVIEW-267（backend 缓存 TTL 审查）/ PS-015（缓存 TTL 必须大于被缓存操作平均耗时）对应。
> 与 #93（性能优化量化验证）的区别：#93 关注"优化效果验证"；#94 关注"缓存 TTL 取值合理性"。

**问题背景**：本次对话中缓存 TTL 设为 5 秒，但被缓存操作（闲鱼搜索）平均耗时 15-20 秒，TTL < 操作耗时导致缓存命中率几乎为零。这是一个典型的配置参数合理性错误——配置值与实际业务耗时不匹配。

**核心原则**：
1. **缓存 TTL 必须 >= 被缓存操作平均耗时 × 期望命中倍数**：默认期望命中倍数为 3（即 TTL >= 3 × 操作耗时），确保至少 3 次缓存命中。
2. **代码注释必须说明 TTL 取值依据**：注释中必须记录被缓存操作的平均耗时和期望命中倍数，如 `# 60 秒 TTL：闲鱼搜索平均耗时 15-20s，60s 确保至少 3 次缓存命中`。
3. **TTL 值必须从 config 读取**：禁止在代码中硬编码 TTL 值，必须从 config.yaml 读取，便于调整。
4. **新增缓存时必须评估 TTL 合理性**：新增缓存代码时，必须评估被缓存操作的平均耗时，并据此设置 TTL。

**判断信号**：
- `grep "_TTL\s*=\s*\d" src/` 找到硬编码 TTL → 应改为从 config 读取
- `grep "_TTL\s*=" src/` 附近无注释说明取值依据 → 补充取值依据注释
- TTL 值 < 被缓存操作平均耗时 → 调整 TTL
- 新增缓存代码无 TTL 合理性评估 → 补充评估

**配置驱动**：
- `cache_ttl_check.enabled`：是否启用 TTL 合理性校验（默认 true）
- `cache_ttl_check.expected_hit_multiplier`：期望命中倍数（默认 3）
- `cache_ttl_check.min_ttl_seconds`：最小 TTL 允许值（默认 30）
- `cache_ttl_check.scan_globs`：扫描的文件 glob（默认 `['src/xianyu_hunter/**/*.py']`）
- 禁止在代码中硬编码上述参数

**适用场景**：
- 所有缓存代码（内存缓存、Redis 缓存、HTTP 缓存）
- 缓存配置审查（需验证 TTL 取值合理性）
- 新增缓存代码时（需评估 TTL）

**不适用场景**：
- 无缓存的代码
- 强一致性要求的缓存（TTL 设为 0 或极小值是有意选择）
- 静态数据缓存（TTL 可设为无限大）

**与其他规则区别**：
- 与 #93（性能优化量化验证）的区别：#93 关注"优化效果验证"；#94 关注"缓存 TTL 取值合理性"
- 与 PS-015（缓存 TTL 必须大于被缓存操作平均耗时）的关系：PS-015 是本元规范在 performance-and-security-patterns.md 的落地条文
- 与 #30（业务关键字常量集中管理）的区别：#30 关注"业务关键字集中"；#94 关注"缓存 TTL 合理性"

**复盘来源**：2026-07-22 闲鱼猎人实时查询缓存优化。根因链：
1. 缓存 TTL 设为 5 秒
2. 被缓存操作（闲鱼搜索）平均耗时 15-20 秒
3. TTL (5s) < 操作耗时 (15-20s)，缓存命中率几乎为零
4. 性能优化形同虚设

修复：
1. TTL 从 5 秒修正为 60 秒（>= 3 × 20s）
2. 代码注释说明取值依据：`# 60 秒 TTL：闲鱼搜索平均耗时 15-20s，60s 确保至少 3 次缓存命中`
3. TTL 从 config 读取

对应 step 271。

---

## 95. SPA 渲染容错体系（SPA-RENDER-RESILIENCE）🆕v4.61.0

> 与 F-REVIEW-217~221（前端 SPA 渲染容错审查）/ step 254~258（frontend-ui.md）/ step 259~261（testing.md）对应。
> 与 #83（UI 操作项分级保留与多视图一致性）的区别：#83 关注"UI 操作项与视图一致性"；#95 关注"SPA 渲染期异常的捕获、隔离与恢复"。
> 与 #85（关键路径可观测性与状态同步三要素）的区别：#85 关注"可观测性与状态重置"；#95 关注"渲染容错三件套（ErrorBoundary + lazyRetry + 路由隔离）+ 401 防抖"。

**问题背景**：本次对话中 React SPA 切换菜单时有 5-10% 概率白屏，刷新后恢复。经 Chrome DevTools 分析识别 5 类根因：① 缺少全局 ErrorBoundary，渲染异常冒泡到 React 顶层导致整页白屏；② 懒加载 chunk 失效（部署后旧 hash 404）无重试机制；③ 未保护的数据访问（`data.list[0].name` 未判空）；④ 401 拦截器硬跳转（`window.location.href`）在并发请求时多次跳转中断渲染；⑤ 路由级错误无隔离，单页错误使整个应用不可用。这是一个典型的 SPA 渲染容错体系缺失问题——缺少分层错误捕获、加载失败重试、数据访问防御、跳转防抖、错误隔离五道防线。

**核心原则**：
1. **渲染容错三件套【强制】**：全局 ErrorBoundary（兜底所有渲染异常）+ lazyRetry 包装（chunk 失效自动重试）+ 路由级 ErrorBoundary（隔离单路由错误），三者必须同时存在分层防御。
2. **resetKeys 仅限基本类型【强制】**：ErrorBoundary 的 `resetKeys` 只能放 `string`/`number`/`boolean`，禁止放对象/数组引用（引用每次渲染变化触发误重置）。
3. **数据访问防御性兜底【强制】**：组件渲染期访问 API 响应必须用可选链（`?.`）+ 空数组兜底（`?? []`），禁止假设响应结构一定完整。
4. **401 拦截器防抖【强制】**：401 跳转必须用模块级标志防抖 + `window.location.replace`（不留历史），禁止每个 401 都触发 `window.location.href` 跳转。
5. **测试环境预检【强制】**：运行 vitest 前必须预检安装状态，tsconfig 必须排除测试文件，antd v5 中文按钮断言必须兼容自动空格。

**判断信号**：
- `grep "BrowserRouter" frontend/src/App.tsx` 附近无 `<ErrorBoundary>` 包裹 → 缺全局 ErrorBoundary
- `grep "React.lazy" frontend/src/` 命中裸用（未包 lazyRetry）→ 缺 chunk 重试
- `grep "<Route" frontend/src/` 附近无 `<ErrorBoundary>` 包裹 → 缺路由级隔离
- 组件含 `data.xxx.yyy` 链式访问无 `?.` → 缺防御性兜底
- `grep "location.href" frontend/src/api/` 命中 401 拦截器 → 缺防抖
- 用户反馈"切菜单偶发白屏，刷新后恢复" → 典型症状

**配置驱动**：
- `spa_render_resilience.globalErrorBoundary.enabled`：是否强制全局 ErrorBoundary（默认 true）
- `spa_render_resilience.globalErrorBoundary.resetKeyTypeWhitelist`：resetKeys 允许的类型（默认 `['string', 'number', 'boolean']`）
- `spa_render_resilience.lazyRetry.enabled`：是否强制 lazyRetry 包裹（默认 true）
- `spa_render_resilience.lazyRetry.maxRetries`：最大重试次数（默认 3）
- `spa_render_resilience.lazyRetry.chunkErrorPatterns`：chunk 失败错误模式列表
- `spa_render_resilience.routeErrorBoundary.enabled`：是否强制路由级 ErrorBoundary（默认 true）
- `spa_render_resilience.apiArrayDefense.enabled`：是否强制数组访问判空（默认 true）
- `spa_render_resilience.http401Debounce.enabled`：是否强制 401 防抖（默认 true）
- `spa_render_resilience.http401Debounce.redirectMethod`：跳转方法（默认 replace）
- 禁止在代码中硬编码上述参数

**适用场景**：
- 所有 React SPA 项目（含路由 + 懒加载 + API 调用）
- CI/CD 频繁部署导致 chunk hash 变更的项目
- 含认证的 SPA（401 拦截器）
- 路由切换频繁的应用

**不适用场景**：
- SSR 应用（错误处理与跳转策略不同）
- 纯静态页面无路由无 API
- 无认证的公开 API（无 401 拦截器）

**与其他规则区别**：
- 与 #83（UI 操作项分级保留与多视图一致性）的区别：#83 关注"UI 操作项与视图一致性"；#95 关注"SPA 渲染期异常的捕获、隔离与恢复"
- 与 #85（关键路径可观测性与状态同步三要素）的区别：#85 关注"可观测性与状态重置"；#95 关注"渲染容错三件套 + 401 防抖"
- 与 step 249（React 组件复用状态同步重置）的区别：step 249 关注"组件复用时重置内部状态"；#95 关注"渲染异常的分层捕获与恢复"

**复盘来源**：2026-07-22 闲鱼猎人前端 React SPA 间歇性白屏修复。根因链：
1. 缺少全局 ErrorBoundary，渲染异常冒泡到 React 顶层导致整页白屏
2. 懒加载 chunk 失效（部署后旧 hash 404）无重试机制，直接白屏
3. 未保护的数据访问（`data.list[0].name` 未判空），后端返回非预期结构时抛异常
4. 401 拦截器用 `window.location.href` 跳转，并发请求多次跳转中断渲染
5. 路由级错误无隔离，单页错误使整个应用（含 Header/Sidebar）白屏

修复：
1. 添加全局 ErrorBoundary 包裹 `<BrowserRouter>`，resetKeys 用基本类型
2. 实现 `lazyRetry` 高阶函数包裹 `React.lazy`，sessionStorage 计数 + maxRetries
3. 路由级 ErrorBoundary 包裹 `<Outlet>`，resetKeys 绑定 `location.pathname`
4. API 响应防御性兜底：可选链 + 空数组兜底 + 前置判空
5. 401 防抖：模块级 `isRedirecting` 标志 + `window.location.replace`
6. 测试踩坑修复：vitest 预检、tsconfig 排除测试文件、antd 中文按钮空格兼容

对应 step 254~258（frontend-ui.md）+ step 259~261（testing.md）。


---

## 96. 多写入路径状态一致性检查（MULTI-WRITE-PATH-STATE-CHECK）🆕v4.60.0

**问题**：同一状态被多个写入路径（Zustand store 方法 + API 回调 + 定时器）修改时，写入顺序和条件不一致导致状态冲突。

**核心规则**：
1. 同一状态的所有写入路径必须经过单一调度函数，禁止各自直接修改状态
2. 多写入路径的优先级与互斥关系必须在配置中声明
3. 写入路径变更时必须同步更新所有调用方

**判断信号**：`grep` 发现同一 state 字段在 ≥2 处被 `setState` / `updateState` / `store.method` 修改 → 必须检查一致性

**配置参数**：`multi_write_path_check` 节点（enabled / stateFields / dedupMethod / priorityOrder）

**适用**：Zustand store 多方法操作同一字段、API 回调与定时器同时更新状态
**不适用**：单写入路径的状态、纯派生计算字段

**历史教训**：Cookie 状态被 `sync_state()` 和 `import_from_browser()` 两条路径分别修改，`sync_state` 写入 `valid=True` 但 `import_from_browser` 只写 `token` 未更新 `valid`，导致状态不一致。修复后提取 `_apply_cookie_update()` 单一调度函数。


---

## 97. UI 偏好持久化检查（UI-PREFERENCE-PERSISTENCE-CHECK）🆕v4.60.0

**问题**：用户 UI 偏好（主题色、CDP 模式开关、视图模式）用 `useState` 存储导致页面刷新后丢失。

**核心规则**：
1. 跨刷新需保留的偏好必须使用 `usePersistentState` / `localStorage`，禁止 `useState` 存储持久化偏好
2. 偏好关键词识别：`mode` / `theme` / `layout` / `view` / `collapsed` / `expanded` / `visible` / `enabled`
3. 禁止自行实现 localStorage 读写，必须复用项目 `usePersistentState` hook

**判断信号**：`useState` 的 key 名含偏好关键词 → 检查是否需要跨刷新持久化

**配置参数**：`ui_preference_persistence` 节点（enabled / preferenceKeywords / persistenceHookName / keyNamingPattern）

**适用**：用户手动切换的 UI 偏好（主题/模式/布局/展开状态）
**不适用**：临时交互状态（加载中/hover/焦点）、服务端数据同步状态

**历史教训**：AntiCrawl/index.tsx 的 CDP 模式开关用 `useState(false)`，刷新后状态重置为关闭，用户每次需重新开启。修复后改用 `usePersistentState('anticrawl-cdp-mode', false)`。


---

## 98. storage 错误处理检查（STORAGE-ERROR-HANDLING-CHECK）🆕v4.60.0

**问题**：localStorage/sessionStorage 在隐私模式、存储配额满、跨域 iframe 等场景下会抛异常，未做 try/catch 导致白屏。

**核心规则**：
1. 所有 `localStorage` / `sessionStorage` 读写必须 try/catch 包裹
2. 写入失败降级为内存存储 + `logger.warning` 告警
3. 读取失败返回默认值，不抛异常

**判断信号**：代码含 `localStorage.setItem` / `localStorage.getItem` / `sessionStorage` → 必须检查是否有 try/catch

**配置参数**：`storage_error_handling` 节点（enabled / fallbackToMemory / logLevel / quotaExceededRetries）

**适用**：所有 localStorage/sessionStorage 操作
**不适用**：Node.js 环境（无 localStorage）、Web Worker（无 localStorage）

**历史教训**：Safari 隐私模式下 `localStorage.setItem` 抛 QuotaExceededError，`usePersistentState` 未做 try/catch，导致页面白屏。


---

## 99. Cookie 状态异常与多写路径状态缺失预防（COOKIE-STATE-ANOMALY-MULTI-WRITE-PREVENTION）🆕v4.60.0

**问题**：Cookie 导入后状态字段（`valid`/`written_count`）未同步更新，导致"有 Cookie 但系统认为无效"。

**核心规则**：
1. Cookie 写入路径必须同步更新所有关联状态字段（`valid`/`written_count`/`last_checked`）
2. 状态同步方法必须以 `sync_state_from_xxx()` 命名，明确标识数据来源
3. 所有状态变更路径（登录成功/Token 刷新/外部导入）必须调用 `sync_state_from_xxx()`

**判断信号**：Cookie 文件写入但 `valid=False` / `written_count=0` → 检查是否有 `sync_state_from_xxx()` 调用

**配置参数**：`cookie_state_sync` 节点（enabled / syncMethodPattern / requiredFields / stateChangePaths）

**适用**：Cookie 状态管理、Token 刷新流程、外部数据导入
**不适用**：只读 Cookie 校验（无状态变更）、一次性 Cookie 使用

**历史教训**：`import_from_browser` 写入 Cookie 文件但未调用 `sync_state_from_cookie()`，导致 `valid` 仍为 `False`，系统认为 Cookie 无效拒绝使用。


---

## 100. 页面刷新后 Cookie 有效但系统认为无效的修复协议（COOKIE-REFRESH-VALID-MISMATCH-FIX）🆕v4.60.0

**问题**：页面刷新后从文件加载的 Cookie 实际有效（`valid=True` 在文件中），但系统内存状态仍为无效（未从文件同步）。

**核心规则**：
1. 启动时必须从 Cookie 文件加载状态，不能仅依赖内存缓存
2. `sync_state_from_cookie()` 必须在服务启动时调用
3. Cookie 文件存在且非空 → 默认认为有效，除非显式校验失败

**判断信号**：服务重启后 Cookie 状态显示无效但文件中 Cookie 存在 → 检查启动流程是否调用 `sync_state_from_cookie()`

**配置参数**：`cookie_refresh_sync` 节点（enabled / syncOnStartup / defaultValidIfFileExists / validateOnSync）

**适用**：服务重启/热重载后的 Cookie 状态恢复
**不适用**：首次启动（无 Cookie 文件）

**历史教训**：服务重启后内存中 Cookie 状态为空，但文件中 `valid=True`。根因是 `startup.py` 未调用 `sync_state_from_cookie()`，修复后在启动流程中增加文件状态同步步骤。


---

## 101. Cookie 状态异常+页面刷新后状态持久+CDP模式状态丢失三合一修复（COOKIE-STATE-ANOMALY-PERSIST-CDP-TRIPLE-FIX）🆕v4.60.0

**问题**：Cookie 状态异常、页面刷新后 UI 偏好丢失、CDP 模式状态丢失三个问题同时出现，根因都是"状态多写路径未同步 + 持久化缺失"。

**核心规则**：
1. 三类问题必须协同修复，不能只改一边
2. Cookie 状态修复 → 前端 UI 反馈修复 → 持久化修复，按依赖顺序逐层推进
3. 每层修复后立即验证，避免错误传播

**判断信号**：用户报告"Cookie 无效" + "刷新后设置丢失" + "CDP 模式重置" → 三问题根因相关，需协同修复

**配置参数**：`cookie_state_triple_fix` 节点（enabled / fixOrder / verifyAfterEachFix / crossLayerSync）

**适用**：多个状态管理问题同时出现的复杂场景
**不适用**：单一独立问题

**历史教训**：2026-07-22 闲鱼猎人前端修复，三个问题同时出现且根因相关，逐个修复导致互相影响，最终协同修复才解决。


---

## 102. 多写路径状态检查+UI偏好持久化+storage错误处理三合一（MULTI-WRITE-PERSIST-STORAGE-TRIPLE）🆕v4.60.0

**问题**：多写路径状态冲突 + UI 偏好未持久化 + storage 错误未处理，三类问题本质相同：状态管理缺乏系统性设计。

**核心规则**：
1. 状态管理设计必须同时考虑：写入路径唯一性 + 持久化策略 + 错误容错
2. 新增状态时必须填写"状态管理三要素检查清单"（写入路径/持久化方式/错误处理）
3. 代码审查时按三要素逐项检查

**配置参数**：`state_management_triple` 节点（enabled / checkListItems / reviewEnforcement）

**适用**：所有新增 React 状态、Zustand store 状态
**不适用**：纯计算派生状态（无副作用）

**历史教训**：#97（UI偏好持久化）+ #98（storage错误处理）+ #99（Cookie状态异常）三问题根因相同：状态管理缺乏系统性。


---

## 103. UI 视觉变更预确认门控（UI-PREVIEW-GATE）🆕v4.62.0

**问题**：视觉风格全量替换（如图标、主题色、布局）后，用户审查认为不美观与整体不协调，需要回滚。

**核心规则**：
1. 视觉风格变更影响 ≥10 个组件时，必须先预览再全量替换（渐进式替换策略）
2. 替换前必须记录回滚清单（被替换的组件 + 原始实现）
3. 风格一致性评估：新视觉元素与整体主题（颜色/圆角/间距/粗细）是否协调
4. 用户确认后才执行全量替换

**判断信号**：`git diff` 涉及 ≥10 个图标的替换 / 主题色变更 / 布局结构重构 → 必须执行预确认门控

**配置参数**：`ui_preview_gate` 节点（enabled / changeLineThreshold / previewStrategy / triggerPatterns / exemptPatterns）

**适用**：视觉风格替换、图标变更、主题色调整、布局重构
**不适用**：Bug 修复的微小 UI 调整、文案修正、样式微调

**历史教训**：Geometric Essence 图标全量替换 21 个 Ant Design 图标后，用户认为不美观与整体主题不协调，要求完整回滚。根因：未先预览就全量替换，替换后与 Ant Design 设计语言不协调。

**对应 step**：step 259（frontend-ui.md）。


---

## 104. 缓存守卫三原则（CACHE-GUARD-3RULES）🆕v4.62.0

**问题**：缓存 TTL 硬编码导致无法按环境调整、空结果被缓存掩盖实时数据恢复、缓存写入守卫与业务逻辑耦合导致逻辑变更时缓存行为异常。

**核心规则**：
1. **TTL 配置化**：Cache TTL 必须从 `config.yaml` 读取，禁止模块级硬编码常量（如 `_LIVE_CACHE_TTL = 60`）
2. **空结果不缓存**：查询结果为空（0 records）时不得写入缓存，避免缓存有效期内返回空列表掩盖实时数据恢复
3. **守卫独立性**：缓存写入守卫必须独立于上游业务逻辑（如 `if filtered:` cache write vs `if items:` DB write），避免业务逻辑变更时缓存行为被意外修改

**判断信号**：
- 模块级常量 `_XXX_CACHE_TTL = N` → 违反原则1
- `cache[key] = []` 或 `cache[key] = result` 其中 result 为空列表 → 违反原则2
- `if business_condition: cache_write()` 其中 cache_write 的触发条件与业务写入条件不同 → 违反原则3

**配置参数**：`cache_guard` 节点（ttlConfigPath / cacheEmptyResult / guardIndependent / detectionPatterns）

**适用**：所有业务缓存（搜索结果/统计聚合/列表查询）
**不适用**：静态配置缓存（永不过期）、CDN 缓存（由外部管理）

**历史教训**：`api_task_links.py` 中 `_LIVE_CACHE_TTL = 60` 硬编码，无法通过配置调整；空搜索结果被缓存导致新增商品在 60s 内不显示；`if filtered:` 写缓存与 `if items:` 写 DB 条件不同，DB 写入失败时缓存仍有效。

**对应 step**：step 253（config-driven.md）。


---

## 105. 数据写入策略字段级决策（FIELD-STRATEGY）🆕v4.62.0

**问题**：数据合并时"一刀切"覆盖策略导致：数值类字段被 0 覆盖、标识类字段频繁变化、状态类字段更新不及时。

**核心规则**：
1. 数据合并按字段语义分类采用不同策略，禁止一刀切
2. **alwaysOverwrite**：状态类字段（`is_sold`/`status`/`valid`）——时效性最高，始终覆盖
3. **coalesceIfTruthy**：数值类字段（`price`/`count`/`score`）——新值 > 0 才覆盖，防止 0 覆盖有效值
4. **fillIfMissing**：标识类字段（`seller_nick`/`brand`/`category`）——只填缺失，稳定性高
5. **overwriteIfNotBlank**：基本信息字段（`title`/`url`/`region`）——新值非空则覆盖

**判断信号**：数据合并/更新代码中 `for k, v in new_data.items(): old[k] = v` 无条件覆盖 → 必须按字段语义分类

**配置参数**：`field_strategy` 节点（alwaysOverwriteFields / coalesceIfTruthyFields / fillIfMissingFields / overwriteIfNotBlankFields）

**适用**：数据采集合并、爬虫数据覆盖历史快照、缓存更新
**不适用**：审计日志（需保留全量历史）、纯创建场景（无旧值）

**历史教训**：商品刷新时 `price=0`（平台返回缺失值）覆盖了历史有效价格，导致低价商品被误判。修复后 price 字段改为 `coalesceIfTruthy` 策略。

**对应 step**：step 248（general-engineering.md）+ step 17（数据合并字段覆盖策略）。


---

## 106. 回调注入默认值模式（CALLBACK-INJECTION-DEFAULT）🆕v4.62.0

**问题**：异步回调（如 `on_success`/`on_complete`）注入外部依赖时，调用方未传回调导致 `None` 调用报错，或回调内部依赖外部状态（如 `request_id`）但回调签名不包含该参数。

**核心规则**：
1. 可选回调参数必须提供默认空实现（`lambda *a, **kw: None`），禁止调用方手动 `if callback: callback()`
2. 回调内部依赖的外部状态必须通过闭包或参数注入，禁止回调内部直接读取全局变量
3. 回调注入的默认值必须与正常回调返回类型一致（如回调返回 dict，默认值返回空 dict）

**判断信号**：
- `if on_success: on_success(result)` → 违反规则1（应 `on_success = on_success or noop`）
- 回调内部引用 `request_id` / `task_id` 等外部变量但签名不包含 → 违反规则2
- 默认回调返回 `None` 但正常回调返回 dict → 违反规则3

**配置参数**：`callback_injection` 节点（enabled / defaultBehaviorStrategy / allowOverride / validateReturnType）

**适用**：所有异步回调（API 调用后回调、任务完成回调、事件处理器注册）
**不适用**：同步直接调用（无回调模式）、必须执行的回调（不应有默认空实现）

**历史教训**：`refresh_item` 的 `on_complete` 回调未传时为 `None`，调用 `on_complete(result)` 触发 `TypeError`。修复后 `on_complete = on_complete or (lambda r: None)`。

**对应 step**：step 249（general-engineering.md）。


---

## 107. React 状态选型判断矩阵（STATE-SELECTION-MATRIX）🆕v4.62.0

**问题**：React 状态管理选型不当导致：跨刷新持久化偏好用 `useState`（刷新丢失）、简单 UI 状态用全局 store（过度设计）、临时交互状态用 localStorage（性能浪费）。

**核心规则**：
1. **判断矩阵**（按优先级从高到低）：
   - 跨刷新需保留的偏好 → `usePersistentState`（key, defaultValue）
   - 跨组件共享的业务状态 → Zustand store
   - 仅组件内使用的 UI 状态 → `useState`
   - 表单临时输入 → `useState`（提交后清空）
2. **禁止**：`useState` 存储持久化偏好（key 含 `mode`/`theme`/`layout`/`view`/`collapsed`/`enabled`）
3. **禁止**：自行实现 `localStorage.getItem/setItem` 读写（必须复用 `usePersistentState`）

**判断信号**：
- `useState` 变量名含偏好关键词 → 检查是否应使用 `usePersistentState`
- `localStorage.getItem` 直接调用 → 违反规则3
- 组件内 `useState` 用于跨组件共享数据 → 应改用 Zustand

**配置参数**：`state_selection` 节点（enabled / preferenceKeywords / persistenceHookName / keyNamingPattern）

**适用**：React 组件状态管理选型、新增 useState/usePersistentState 前的判断
**不适用**：非 React 环境、服务端渲染（SSR 状态管理不同）

**历史教训**：AntiCrawl/index.tsx 的 CDP 模式开关用 `useState(false)`，刷新后状态重置。修复后改用 `usePersistentState('anticrawl-cdp-mode', false)`。

**对应 step**：step 260（frontend-ui.md）+ #97（UI偏好持久化检查）。


---

## 108. 跨层闭环验证（CROSS-LAYER-CLOSED-LOOP）🆕v4.62.0

**问题**：修改前端/types 后未同步修改后端/DB，或修改后端后未验证前端是否正确消费，导致"后端改了前端没改"或"前端调了后端没实现"的跨层不一致。

**核心规则**：
1. 跨层修改必须同步验证三层：前端 types → 后端 Pydantic → DB schema
2. 每层修改后必须 `grep` 验证其他层的对应代码是否同步更新
3. 修改产生的"半边修改"必须标记为 CRITICAL 级别问题

**判断信号**：
- `git diff` 只修改 `types.ts` 但未修改对应 `models.py` → 违反规则1
- `git diff` 只修改 `models.py` 但未修改对应 `types.ts` → 违反规则1
- 前端调用不存在的 API 端点 → 违反规则2

**配置参数**：`cross_layer_closed_loop` 节点（enabled / checkLayers / syncMethodPattern / grepVerification）

**适用**：前后端协同修改、API 接口变更、DB schema 变更
**不适用**：纯前端样式修改、纯后端内部逻辑重构、纯 DB 性能优化（不改 schema）

**历史教训**：评估详情页新增"反馈"列：后端 API 新增 `feedback_score` 字段，前端 `types.ts` 已更新但 `EvaluationDetail.tsx` 未读取该字段，导致列显示为空。根因：后端改了前端未完整消费。

**对应 step**：step 52（数据流转完整性5点追踪）+ B-REVIEW-279（跨层闭环验证）。


---

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


---

## 110. 类型注解契约对齐（TYPE-ANNOTATION-CONTRACT-ALIGNMENT）🆕v4.67.0 experimental

**问题**：后端函数返回类型注解（如 `-> list[str]`）与实际返回结构（如 `list[dict]`）不一致，且与前端 `types.ts` 声明（如 `Array<{url, hash}>`）也不一致，导致前端访问字段时取到 `undefined`。既有规范 #35/#88/#108 假设"后端为权威源"或"后端注解=实际返回"，未覆盖"后端类型注解本身错误"且"前端 types.ts 反而是真相源"的反向情况。

**核心规则**：
1. 返回复杂结构（`list[dict]` / `list[TypedDict]` / 嵌套 Pydantic BaseModel / `dict[str, Any]`）的后端函数，必须保证三方契约对齐：后端函数返回类型注解 ↔ 后端 Pydantic ResponseModel ↔ 前端 types.ts
2. 权威源优先级：① Pydantic ResponseModel（首选）② 前端 types.ts（反向校验源，当无 ResponseModel 时）③ 后端函数类型注解（最弱，仅辅助参考）
3. 单元测试必须断言**完整结构**（字段名 + 字段类型 + 至少一个字段的值），禁止仅断言长度或顶层类型

**判断信号**：
- `grep "def.*->.*list\[" src/` 或 `grep "def.*->.*dict" src/` 找返回复杂结构的函数 → 对照前端 types.ts 同名字段类型
- 单元测试 `for h in data["..."]:` 后仅 `assert len(h) == N` → 违反规则3（未断言完整结构）
- 前端显示 `undefined` 且后端函数返回类型注解为基本类型（`list[str]`）→ 违反规则1（三方不对齐）

**配置参数**：`typeAnnotationContract` 节点（enabled / complexReturnTypes / alignmentSources / authoritativeSource / fallbackAuthoritativeSource / testAssertionLevel / observationPeriodQuarters / observationEndDate / promotionThreshold / applicableScenarios / nonApplicableScenarios）

**适用**：返回 list[dict]/list[TypedDict]/嵌套 Pydantic 模型的后端函数；前后端分离 API 端点；无 ResponseModel 但有前端消费方的端点
**不适用**：返回基本类型（str/int/bool）；纯内部 helper（无前端消费方）；动态结构通用序列化（结构由 DB schema 决定）；已有 Pydantic ResponseModel 严格校验的端点

**与既有规范的关系**：
- #35（前后端字段契约单一可信源）：管"字段名/存在性"，本规范管"类型注解正确性"，互补
- #88（CROSS-LAYER-CONTRACT-SYNC）：管"跨层同步动作"，本规范管"注解与实际返回一致性"，互补
- #108（CROSS-LAYER-CLOSED-LOOP）：管"git diff 半边修改"，本规范管"函数签名注解本身错误"，互补

**历史教训**：2026-07-26 AI 深度鉴伪图片哈希 Bug。后端 `_compute_image_url_hash(image_urls: list[str]) -> list[str]` 实际返回 `[hashlib.md5(url).hexdigest()[:12] for url in image_urls]`（纯字符串列表），但前端 types.ts 声明 `Array<{ url: string; hash: string }>`。前端渲染 `h.url`/`h.hash` 取到 undefined，显示 `undefined → undefined`（重复 9 次）。本案特殊性：前端 types.ts 反而是契约真相源（已正确），后端偏离——既有规范 #35/#88 假设"后端为权威源"未覆盖此反向情况。修复：后端改为返回 `list[dict]`（`[{"url": url, "hash": ...}]`），同步更新类型注解和单元测试断言。

**experimental 升正条件**：1 季度内（截至 2026-10-26）同类根因再发 ≥ 2 次

**对应 step**：step 273（type-annotation-contract.md）。


---

## 111. 事件驱动基础设施启动解耦（EVENT-BUS-STARTUP-DECOUPLING）🆕v4.68.0 experimental

**问题**：事件总线/消息队列的消费者循环（如 `EventBus.run_forever()`）被嵌套在业务调度器启动函数内部（如 `start_scheduler_in_background` 的 `_scheduler_loop`），导致消费者循环的启动受制于业务条件——"是否有 RUNNING 任务""collector 是否就绪""环境变量是否开启"任一不满足时，消费者循环永不启动。后续通过 API/CLI 运行时新增业务任务时，`publish_nowait` 事件入队但无消费者，订阅者（如 NotifierHub）永远收不到事件，钉钉等通知静默失效，且**无任何报错日志**，极难排查。

**核心规则**：
1. 事件总线/消息队列/事件循环等基础设施的消费者循环，必须与业务任务存在性解耦——启动条件独立于"是否有业务任务在运行"
2. 启动顺序：基础设施**先于**业务调度器启动（确保业务 `publish` 事件时有消费者在等待）
3. 停止顺序：基础设施**后于**业务调度器停止（确保业务停止时 `publish` 的终态事件能被消费）
4. 启动函数必须**幂等**：已在运行则跳过，禁止重复启动产生多个消费者竞争同一队列
5. 消费者循环异常**不能静默退出**：除 `CancelledError` 外的异常必须 `logger.exception` 记录，避免任务静默死亡
6. 运行时新增业务入口（API resume/restart、CLI 命令）时，必须确认基础设施已就绪——若基础设施未启动则自动启动，不能假设"启动时一次性决定"

**判断信号**：
- `grep "run_forever\|consume_loop\|_dispatch" src/` 找到消费者循环 → 检查其启动是否嵌套在业务调度器函数内部
- `grep "publish_nowait\|publish(" src/` 找到 publish 调用 → 反向追踪消费者是否在同一启动链路中
- `grep "if not workers\|if not.*RUNNING\|if not container.collector" src/xianyu_hunter/web/startup.py` → 若该 return 阻断了基础设施启动则违反规则1
- `grep "control_task\|resume\|restart" src/xianyu_hunter/web/routes/` → 检查是否补启动基础设施
- 启动日志缺 `"EventBus 主循环启动"` 或类似 INFO → 违反规则5

**配置参数**：`eventBusStartupDecoupling` 节点（enabled / infrastructureTypes / startupOrder / shutdownOrder / requireIdempotentGuard / requireExceptionIsolation / requireStartupLog / observationPeriodQuarters / observationEndDate / promotionThreshold / applicableScenarios / nonApplicableScenarios）

**适用**：事件总线（EventBus/MessageQueue）的消费者循环；发布-订阅模式的基础设施；后台调度器依赖的事件分发机制；Worker/Agent publish 事件到队列、由独立消费者分发给 Notifier 的模式
**不适用**：同步调用（无 publish-subscribe）；一次性任务（启动即完成）；进程内函数直接 invoke（无队列中间层）；前端组件间通信（React Context/Zustand，无独立消费者循环）

**与既有规范的关系**：
- #48（SCHEDULER-RUNTIME-TOGGLE-SYMMETRY，step 194）：管"调度器运行时开关对称性"（启用/禁用 job），本规范管"消费者循环启动条件解耦"（启动依赖），互补
- step 33（独立调度器隔离模式）：管"生命周期不同的任务用独立调度器"（资源隔离），本规范管"基础设施启动不能依赖业务任务存在"（启动依赖），互补
- step 107（启动钩子完整性）：管"依赖 browser/collector 的组件必须有启动钩子"（组件覆盖），本规范管"启动条件不能与业务任务耦合"（启动条件），互补——step 107 防"漏启动组件"，本规范防"启动条件嵌套导致静默失败"

**历史教训**：2026-07-26 用户反馈评分 80 以上商品未触发钉钉通知。配置全正常（`pass_score: 70`、`dingtalk: true`、`quiet_hours.enabled: false`、`subscribed_events` 含 `EVAL_PASSED`），根因是 `EventBus.run_forever()` 被嵌套在 `start_scheduler_in_background` 的 `_scheduler_loop` 内部，三重前置条件任一不满足即 return：① `XH_WITH_SCHEDULER=1` ② `container.collector is not None` ③ 启动时有 RUNNING 任务。第③条最隐蔽——启动时无 RUNNING 任务则 EventBus 永不启动，且 `api_tasks.py` 的 `control_task`（resume/restart）完全不补启动 EventBus。结果 `worker.publish_nowait(EVAL_PASSED)` 事件入队但无消费者，NotifierHub 永远收不到事件，钉钉永不触发，且无任何报错日志。修复：抽离 `start_event_bus_in_background()` 独立启动函数，在 `_on_startup` 中无条件启动（先于调度器），`_on_shutdown` 中独立停止（后于调度器），含幂等防护与异常隔离。

**experimental 升正条件**：1 季度内（截至 2026-10-26）同类根因再发 ≥ 2 次

**对应 step**：step 274（scheduler.md）。
