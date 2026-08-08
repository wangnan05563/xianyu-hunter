# 闲鱼猎人后端代码审查报告

## 基本信息

- **审查版本**：v2.0.0
- **审查模式**：[全量审查 / 增量审查 / 指定文件审查 / 片段评审]
- **审查范围**：`src/xianyu_hunter/**/*.py`
- **审查文件数**：X 个
- **审查时间**：YYYY-MM-DD HH:MM:SS
- **审查人**：xianyu-backend-code-review Skill
- **上次审查**：[有/无]

## 相对于上次审查的变化

| 状态 | 数量 | 说明 |
|------|------|------|
| 🆕 新增 | X | 本次新发现的问题 |
| ✅ 已修复 | X | 上次存在的问题已修复 |
| ⚠️ 仍存在 | X | 上次存在的问题仍未修复 |

## 审查结果摘要

- 🔴 阻塞问题：X 个（必须修复）
- 🟠 严重问题：X 个（强烈建议修复）
- 🟡 警告问题：X 个（建议修复）
- 🟢 优化建议：X 个（可选）

### 按 severity 分布

| Severity | 数量 |
|----------|------|
| CRITICAL | X |
| HIGH | X |
| MEDIUM | X |
| LOW | X |
| INFO | X |

### 按 category 分布（29 维度）

| Category | 数量 |
|----------|------|
| security | X |
| sqlite_optimization | X |
| sqlalchemy | X |
| async_scheduler | X |
| ... | X |

## 硬约束合规性检查结果

| 硬约束规则 | 状态 | 违规位置 |
|------------|------|----------|
| `hmac_compare_digest_for_token` | ✅ 通过 / ❌ 违规 | - |
| `no_hardcoded_credentials` | ✅ 通过 / ❌ 违规 | - |
| `no_credentials_in_config_yaml` | ✅ 通过 / ❌ 违规 | - |
| `bare_except_pass` | ✅ 通过 / ❌ 违规 | - |
| `no_devnull_redirect_for_webview2` | ✅ 通过 / ❌ 违规 | - |
| `create_no_window_flag` | ✅ 通过 / ❌ 违规 | - |
| `deprecated_utcnow` | ✅ 通过 / ❌ 违规 | - |
| `staticpool_usage` | ✅ 通过 / ❌ 违规 | - |
| `missing_module_level_imports` | ✅ 通过 / ❌ 违规 | - |
| `pydantic_v1_dict_method` | ✅ 通过 / ❌ 违规 | - |
| `missing_hf_endpoint` | ✅ 通过 / ❌ 违规 | - |

**合并结论**：[允许合并 / 阻止合并（存在 CRITICAL 违规）]

## 详细问题列表

### 🔴 阻塞问题（必须修复）

1. **问题描述**：[具体问题描述]
   - **位置**：`src/xianyu_hunter/web/routes/api_xxx.py` 第 X 行
   - **当前代码**：
     ```python
     # 问题代码示例
     ```
   - **修复建议**：
     ```python
     # 修复后的代码示例
     ```
   - **参考规范**：[对应 SKILL.md 维度章节]

### 🟠 严重问题（强烈建议修复）

1. **问题描述**：[具体问题描述]
   - **位置**：`src/xianyu_hunter/xxx.py` 第 X 行
   - **修复建议**：[具体建议]

### 🟡 警告问题（建议修复）

1. **问题描述**：[具体问题描述]
   - **位置**：`src/xianyu_hunter/xxx.py` 第 X 行
   - **修复建议**：[具体建议]

### 🟢 优化建议（可选）

1. **建议描述**：[具体建议]
   - **位置**：`src/xianyu_hunter/xxx.py` 第 X 行
   - **优化方案**：[具体方案]

## ✅ 好的实践

- [正面反馈：列出本次审查中发现的好实践]
  - 例如：`hmac.compare_digest()` 正确使用
  - 例如：SQLite 引擎正确配置 `NullPool` + WAL
  - 例如：ChatbotOrchestrator 设计无请求级状态

## 测试运行结果

- **测试命令**：`pytest tests/ -x`
- **测试结果**：[通过 / 失败]
- **测试覆盖**：[覆盖率]

## 审查结论

- [ ] 通过（无阻塞问题）
- [ ] 有条件通过（仅警告和提示级别问题）
- [ ] 不通过（存在阻塞或严重问题）

## 修复验证

修复完成后，请重新运行审查确认问题已解决：

```powershell
# 1. 重新运行快速自检
pwsh .trae/skills/xianyu-backend-code-review/scripts/auto-scan.ps1

# 2. 重新运行人工评审
# 调用 xianyu-backend-code-review 技能
```

## 报告归档

报告保存路径：`.trae/skills/xianyu-backend-code-review/reports/YYYY-MM-DD_HHmmss_[full|incremental]_report.md`

---

## 🆕 v4.28.0 四维度复盘

> 基于 [`docs/standards/四维度复盘方法论与历史教训集成.md`](../../../../docs/standards/四维度复盘方法论与历史教训集成.md) 的四维度框架，对本次审查的发现进行结构化复盘，沉淀可复用的工作流模板。

### 维度 1：成功执行任务的完整步骤

- 本次审查在 `XXX` 类目下识别出 `N` 个问题，其中 `M` 个被成功闭环
- 关键成功路径（按时间顺序）：
  1. `step 1`: ...
  2. `step 2`: ...
- 复用已有方法/工具：xxx

### 维度 2：任务执行过程中的不确定性与失败点

| 失败点 | 触发条件 | 影响范围 | 根因 | 修复方式 |
|--------|----------|----------|------|----------|
| 关键路径异常被吞 | 外层 except 用 `logger.warning(f"...{e}")` | 启动失败无法定位 | 异常堆栈丢失 | 改用 `logger.exception()` |
| 多迁移块被外层 try 包裹 | `run_migrations` 一个 try 包裹 C-01~C-05 | 后续迁移块被跳过 | 外层吞异常 | 每个迁移块独立 try/except |
| 批处理熔断后无 `save_progress()` | `consecutive failure >= 3` 后 `break` | 剩余商品永久 skipped | 熔断分支未持久化 cursor | 熔断时调用 `_save_progress()` |
| asyncio.create_task 无引用 | `asyncio.create_task(coro)` 裸调用 | 协程被 GC 回收 | 局部变量无生命周期 | 改 `self._task = asyncio.create_task(coro)` |
| aware/naive datetime 相减 | `_utcnow() - row.created_at` | 抛 `TypeError` | SQLite 默认 naive + 应用层 aware | `.replace(tzinfo=None)` 对齐 |
| 跨模块访问 _Session 私有属性 | `repo._session()` | `AttributeError` | 类内为 `_session` 私有 | 改 `repo.get_session()` 公共方法 |
| 30 秒 TTL 缓存兜底跨进程 | `cache_ttl_seconds=30` | 状态显示延迟 30s | 跨进程未 SSE 推送 | 改 `invalidate_cache()` + SSE |
| 布尔字段初始值被误读 | `last_session_invalid=False` | 状态闪烁 | False ≠ 未检测 | 加 `_last_m5tk_refresh > 0` 标记 |

### 维度 3：可抽象的固定流程与判断逻辑

| 模板 | 对应工作流元规范 | 核心判断信号 | 落地配置节点 |
|------|------------------|--------------|--------------|
| 错误处理决策树 | meta-rule #21 | `grep "except" <file>` 关键路径缺 `logger.exception()` | `workflow_meta_rules_backend.error_handling_decision_tree.critical_path_patterns` |
| 批处理熔断模板 | meta-rule #22 | `grep "consecutive failure" <file>` 无 `save_progress()` | `workflow_meta_rules_backend.batch_circuit_breaker_backend.required_persist_keys` |
| 资源生命周期 | meta-rule #23 | `grep "asyncio.create_task"` 未赋值实例属性 | `workflow_meta_rules_backend.resource_lifecycle_backend.required_task_holders` |
| 跨进程状态同步 | meta-rule #24 | `grep "cache_ttl_seconds" <file>` 跨进程状态 | `workflow_meta_rules_backend.state_sync_workflow_backend.single_source_of_truth_sources` |

### 维度 4：适用场景与不适用场景

| 模板 | 适用场景 | 不适用场景 |
|------|----------|------------|
| 错误处理决策树 | `_on_startup` / `run_migrations` / `_init_*` / API 路由 try-except | 性能 hot path / 测试代码（`pytest.raises`） |
| 批处理熔断模板 | `BatchRefreshScheduler` / `AutoLoginScheduler` / 长任务 / 断点续传 | 实时单次请求 / 幂等小批量（≤3 个）/ 用户主动取消（走 stopped 分支） |
| 资源生命周期 | Playwright Page/Browser / httpx/aiohttp ClientSession / asyncio.Task / asyncio.Lock / SQLAlchemy Session | 短生命周期对象 / 测试 mock / `with` 语句（自动管理） |
| 跨进程状态同步 | `CookieRotator` / `Scheduler._job_states` / `TaskRow.status` 等跨进程读写 | 同进程单例状态 / 一次性函数返回值 |

## 🆕 v4.28.0 工作流元规范触发

> 本次审查触发的元规范编号（与 xianyu-hunter-dev/references/meta-rules.md #21-24 对应）。每条触发需指明：触发规则名、对应 config.yaml 配置节点、违规位置、修复方式。

| 触发编号 | 元规范名称 | 触发规则 | 配置节点 | 违规位置 | 修复方式 |
|----------|------------|----------|----------|----------|----------|
| #21 | 错误处理决策树 | B-REVIEW-WF-ERROR-HANDLING | `workflow_meta_rules_backend.error_handling_decision_tree.forbidden_critical_path_patterns` | `src/xianyu_hunter/web/startup.py:L45` | 改用 `logger.exception()` 输出 traceback |
| #22 | 批处理熔断模板 | B-REVIEW-WF-BATCH-CIRCUIT-BREAKER | `workflow_meta_rules_backend.batch_circuit_breaker_backend.detect_patterns` | `src/xianyu_hunter/collector/batch_refresh_scheduler.py:L95` | 熔断时调用 `_save_progress()` |
| #23 | 资源生命周期 | B-REVIEW-WF-RESOURCE-LIFECYCLE | `workflow_meta_rules_backend.resource_lifecycle_backend.required_task_holders` | `src/xianyu_hunter/xxx.py:L123` | 改 `self._task = asyncio.create_task(coro)` |
| #24 | 跨进程状态同步 | B-REVIEW-WF-STATE-SYNC | `workflow_meta_rules_backend.state_sync_workflow_backend.forbidden_ttl_patterns` | `src/xianyu_hunter/cookie/store.py:L67` | 显式 `invalidate_cache()` + SSE 推送 |

## 🆕 v4.28.0 配置变更点

> 本次审查触发的 `config.yaml` 节点变更建议。所有变更遵循"无硬编码"原则，仅调整阈值/白名单/关键字等参数化配置，不引入新的硬编码业务值。

| 变更类型 | 配置节点 | 当前值 | 建议值 | 变更理由 | 影响范围 |
|----------|----------|--------|--------|----------|----------|
| 阈值调整 | `workflow_meta_rules_backend.batch_circuit_breaker_backend.failure_threshold` | `3` | `5` | 现有 3 次不足以应对浏览器冷启动 | 批处理熔断（meta-rule #22） |
| 白名单新增 | `workflow_meta_rules_backend.error_handling_decision_tree.critical_path_patterns` | `[startup_, migrate_, init_, _on_startup$, run_migrations$]` | 同左 + `[setup_, bootstrap_]` | 补齐其他关键路径前缀 | 错误处理决策树（meta-rule #21） |
| 必填字段新增 | `workflow_meta_rules_backend.batch_circuit_breaker_backend.required_persist_keys` | `[batch_id, cursor, completed_ids, remaining_ids]` | 同左 + `[paused_at, pause_reason, total_count, last_error]` | 续传调试需要时间戳与原因 | 批处理熔断（meta-rule #22） |
| 资源类型新增 | `workflow_meta_rules_backend.resource_lifecycle_backend.required_holder_patterns` | `[Page, ClientSession, AsyncClient, Task, Lock, Session]` | 同左 + `[Browser, Context, Engine, Connection]` | 补齐其他可注册资源 | 资源生命周期（meta-rule #23） |
| 模式新增 | `workflow_meta_rules_backend.state_sync_workflow_backend.forbidden_ttl_patterns` | `[cache_ttl_seconds=30/60]` | 同左 + `[cache_ttl_seconds=120, last_update.*<.*seconds]` | 扩展检测粒度 | 跨进程状态同步（meta-rule #24） |

**变更后自检清单**：
- [ ] 无硬编码新增（所有数值/列表/关键字均在 config 节点管理）
- [ ] 通用性未降低（参数化配置可被不同业务场景覆盖）
- [ ] 现有违规检测不失效（回归测试通过）
- [ ] SKILL.md 附录 C 的 30 维度与本变更一致
- [ ] references/version-changelog.md 已追加 v4.28.0 变更说明

## 🆕 v4.30 跨边界访问契约

> 跨边界访问必须明确契约，不能依赖隐式约定。与 xianyu-hunter-dev/references/coding-standards.md §2.11-2.14 配套。

### 跨边界契约检查（后端侧）

| 边界类型 | 契约内容 | 配置节点 | 检查工具 |
|----------|----------|----------|----------|
| DB → 应用 | 应用层 `aware datetime` 与 DB 读回 `naive datetime` 运算前必须 `.replace(tzinfo=None)` | `cross_boundary_contract.datetime_tz_consistency.project_tz_strategy` | B-REVIEW-DATETIME-TZ-CONSISTENCY |
| 类 → 外部模块 | 禁止跨模块访问 `repo._session` 私有属性 | `cross_boundary_contract.private_attr_encapsulation.external_object_prefixes` | B-REVIEW-PRIVATE-ATTR-ENCAPSULATION |
| 命名一致性 | 实例属性 snake_case（`self._session`），禁止 `self._Session` 大小写变体 | `cross_boundary_contract.naming_consistency.instance_attr_case` | B-REVIEW-NAMING-CONSISTENCY |
| 跨进程序列化 | `datetime.isoformat()` 必须保留 tzinfo，禁止 `datetime.now().isoformat()` | `cross_boundary_contract.datetime_tz_consistency.recommended_isoformat_patterns` | B-REVIEW-DATETIME-TZ-CONSISTENCY |

## 🆕 v4.38.0 编码规范防御性复盘报告条目（B-REVIEW-182~188）

> 本节为 v4.38.0 新增 7 项 B-REVIEW 检查点（meta-rules #57-63 后端落地）的报告条目模板。每条违规按以下格式记录，参数在 `config.yaml#meta_rules_57_63` 节点管理。

### B-REVIEW-182 ASYNC-AWAIT-STATIC-CHECK 异步方法静态校验

```
### 🔴 [CRITICAL] B-REVIEW-182：async def 方法体内缺少 await 表达式

- **位置**：`src/xianyu_hunter/xxx.py` 第 X 行
- **当前代码**：
  ```python
  async def _finalize_run(self, stats: RunStats, new_items: list[ItemSummary] | None) -> None:
      # 全同步操作，无 await
      self._save_stats(stats)
      self._notify_done(new_items)
  ```
- **问题**：`async def` 方法体内不含 `await` 表达式，Python 3.14 优化后返回 None，调用点 `await self._finalize_run(...)` 触发 `TypeError: object NoneType can't be used in 'await' expression`
- **修复建议**：将 `async def` 改为同步 `def`，调用点同步移除 `await`
- **配置节点**：`meta_rules_57_63.async_await_check`
- **规范引用**：meta-rule #57 / xianyu-hunter-dev v4.38.0 step 189
- **适用**：Python 3.11+ 异步代码，尤其是被 `await` 调用的方法
- **不适用**：`@abstractmethod` 接口定义、`__aenter__`/`__aexit__` 上下文管理器、async generator
```

### B-REVIEW-183 RESOURCE-POOL-BENCHMARK 资源池性能基准

```
### 🟡 [WARNING] B-REVIEW-183：资源池配置缺少性能基准 docstring

- **位置**：`src/xianyu_hunter/db/db_models.py` 第 X 行
- **当前代码**：
  ```python
  engine = create_engine(
      f"sqlite:///{db_path}",
      poolclass=NullPool,  # 无 docstring 说明，每次连接执行 PRAGMA ~100ms
  )
  ```
- **问题**：`poolclass=NullPool` 选择缺少 docstring 说明性能基准数据，NullPool 每次新建连接执行 5 条 PRAGMA ~100ms，慢查询日志显示系统层开销 > 50ms
- **修复建议**：改为 `QueuePool` 复用连接，docstring 记录对比数据（NullPool 231ms → QueuePool 11.9ms，19x 提升）
- **配置节点**：`meta_rules_57_63.resource_pool_benchmark`
- **规范引用**：meta-rule #58 / xianyu-hunter-dev v4.38.0 step 190
- **适用**：所有资源池选择（NullPool/QueuePool/StaticPool）
- **不适用**：测试环境（用 StaticPool 保证隔离）、单次请求资源
```

### B-REVIEW-184 HTTP-STATUS-CODE-MAPPING HTTP 状态码语义映射

```
### 🔴 [CRITICAL] B-REVIEW-184：多原因 None 一律映射同一状态码

- **位置**：`src/xianyu_hunter/services/collection_service.py` 第 X 行
- **当前代码**：
  ```python
  if detail is None:
      raise CollectionError(410, f"Failed to collect item {item_id}: detail page unavailable or item removed")
  # 但 detail() 返回 None 有 10+ 原因（cookie 失效/反爬/页面关闭/真正下架）
  ```
- **问题**：底层 `detail()` 返回 None 有 10+ 原因，但上游一律映射为 410，前端无法区分"cookie 过期需重新登录"与"商品真正下架"
- **修复建议**：建立 `_DETAIL_FAILURE_STATUS_MAP: dict[str, int]` 映射表，底层设置 `last_detail_failure_reason`，上游按映射查找状态码
- **配置节点**：`meta_rules_57_63.http_status_code_mapping`
- **规范引用**：meta-rule #59 / xianyu-hunter-dev v4.38.0 step 191
- **适用**：所有 HTTP 错误响应；多原因返回 None/错误的底层模块
- **不适用**：唯一原因的错误码（如 404 仅表示资源不存在）
```

### B-REVIEW-185 CSS-SELECTOR-FALLBACK CSS 选择器降级链

```
### 🔴 [CRITICAL] B-REVIEW-185：第三方网站 DOM 选择器缺少降级链

- **位置**：`src/xianyu_hunter/collector/_detail.py` 第 X 行
- **当前代码**：
  ```javascript
  let tabs = document.querySelectorAll('[class*="tabItem"]');  // 单一选择器，闲鱼改版 className 后失效
  ```
- **问题**：第三方网站 DOM 选择器单一，闲鱼改版 className 后 `on_sale=0 sold=0` 误报
- **修复建议**：添加 ≥3 级降级（业务语义 className → HTML role 属性 → 文本内容前缀扫描）
- **配置节点**：`meta_rules_57_63.css_selector_fallback`
- **规范引用**：meta-rule #60 / xianyu-hunter-dev v4.38.0 step 192
- **适用**：第三方网站 DOM 解析（闲鱼/淘宝/第三方 API 返回 HTML）
- **不适用**：自有代码 DOM、ID 选择器、data-* 属性选择器、后端 API JSON 解析
```

### B-REVIEW-186 EXCEPTION-LOG-SEMANTIC 异常日志语义完整性

```
### 🔴 [CRITICAL] B-REVIEW-186：except 块内使用 logger.warning 丢失 traceback

- **位置**：`src/xianyu_hunter/xxx.py` 第 X 行
- **当前代码**：
  ```python
  except Exception as e:
      logger.warning(f"操作失败: {e}")  # 丢失 traceback，定位问题困难
  ```
- **问题**：except 块内使用 `logger.warning(f'...{e}')` 丢失 traceback，关键路径定位问题耗时 30+ 分钟才能复现
- **修复建议**：改用 `logger.exception("操作失败")` 自动保留完整 traceback
- **配置节点**：`meta_rules_57_63.exception_log_semantic`
- **规范引用**：meta-rule #61 / xianyu-hunter-dev v4.38.0 step 193
- **适用**：所有异常处理代码，尤其是关键路径（启动/迁移/初始化）
- **不适用**：纯性能日志（无异常场景）、DEBUG 级别日志、非 except 块的 warning
```

### B-REVIEW-187 EXTERNAL-RESOURCE-LIFECYCLE 外部资源生命周期

```
### 🔴 [CRITICAL] B-REVIEW-187：外部传入资源未配对 register/unregister

- **位置**：`src/xianyu_hunter/services/collection_service.py` 第 X 行
- **当前代码**：
  ```python
  async def collect(self, item_id: str, reuse_page: Page | None = None):
      # 外部传入 page 但未注册，被采集器误关
      page = reuse_page or await self.container.browser.new_page()
      await self._collect_with_page(page)
  ```
- **问题**：外部传入的 Page 未注册，并发采集时 page 被主流程关闭
- **修复建议**：配对调用 `register_external_page`/`unregister_external_page`，在 `finally` 块 unregister 避免泄漏
- **配置节点**：`meta_rules_57_63.external_resource_lifecycle`
- **规范引用**：meta-rule #62 / xianyu-hunter-dev v4.38.0 step 194
- **适用**：外部资源传入、并发采集场景、Playwright Page 共享
- **不适用**：内部创建的资源（自己管理生命周期）、单线程使用、一次性资源
```

### B-REVIEW-188 DB-WRITE-IDENTITY-TRACE 数据库写入身份追踪

```
### 🔴 [CRITICAL] B-REVIEW-188：数据库写入函数缺 user_id 参数 / converter 处理 Match 错误

- **位置**：`src/xianyu_hunter/xxx.py` 第 X 行
- **当前代码（反模式1）**：
  ```python
  def upsert_eval_event(event: EventRow):
      # 缺 user_id，跨用户数据可能被误删
      session.add(event)
  ```
- **当前代码（反模式2）**：
  ```python
  _SELLER_LABEL_PATTERNS = (
      ("sold_count", re.compile(r"卖出(\d+)件"), int),  # int(m) 报错：int() argument must be a string, not 're.Match'
  )
  ```
- **问题**：数据库写入函数缺 `user_id` 参数导致跨用户数据删除；converter 用 `int` 直接转型 `re.Match` 对象报错
- **修复建议**：(1) 添加 `user_id: str` 参数并赋值到 `event.created_by`；(2) converter 改为 `lambda m: int(m.group(1))`
- **配置节点**：`meta_rules_57_63.db_write_identity_trace`
- **规范引用**：meta-rule #63 / xianyu-hunter-dev v4.38.0 step 195
- **适用**：所有数据库写入函数、正则 converter 函数、跨用户系统
- **不适用**：系统级写入（日志表/统计表）、单一调用点的函数、纯查询函数
```

### B-REVIEW-189 BUSINESS-STATUS-CODE-CONFLICT 业务异常状态码冲突检查

```
### 🔴 [CRITICAL] B-REVIEW-189：业务代码抛出认证层专属状态码

- **位置**：`src/xianyu_hunter/modules/collection_service.py` 第 X 行
- **当前代码**：
  ```python
  # ❌ 业务代码抛出认证层专属状态码 401
  raise CollectionError(401, "采集失败：闲鱼登录态失效或 _m_h5_tk token 过期", item_id=item_id)
  ```
- **问题**：业务异常使用 401 状态码与认证中间件 BearerAuthMiddleware 返回的 401 语义重叠，前端全局响应拦截器无法区分「认证失效」与「业务凭证失效」，把业务 401 误判为认证失效跳转登录页，破坏用户工作流。违反状态码分层所有权：401 应专属认证中间件。
- **修复建议**：
  ```python
  # ✅ 外部凭证失效使用 440 状态码
  raise CollectionError(440, "采集失败：闲鱼登录态失效或 _m_h5_tk token 过期", item_id=item_id)
  ```
- **配置节点**：`status_code_audit.layers.auth_layer.codes` / `status_code_audit.forbidden_business_codes`
- **规范引用**：meta-rule #66 / xianyu-hunter-dev v4.40.0
- **适用**：所有 HTTP API 后端业务异常处理；多模式业务（detail-only/official-full）共享同一异常类
- **不适用**：无认证接口；纯参数校验（422 由 FastAPI 自动处理）；测试 mock
- **与 B-REVIEW-184 的区别**：
  - B-REVIEW-184 关注「多原因 None → 状态码映射」（同层内多原因细分）
  - B-REVIEW-189 关注「同一状态码跨层语义冲突」（层间所有权划分）
  - 两者互补，不重复
```

### B-REVIEW-189 多模式状态码一致性检查

```
### 🟡 [WARNING] B-REVIEW-189：同一语义在不同业务模式使用不同状态码

- **位置**：`src/xianyu_hunter/modules/collection_service.py` 第 X 行
- **当前代码**：
  ```python
  # ❌ detail-only 模式 cookie 过期抛 401，official-full 模式抛 440
  # _collect_detail_only
  raise CollectionError(401, "cookie 失效", item_id=item_id)
  # _collect_official_full
  raise CollectionError(440, "cookie 失效", item_id=item_id)
  ```
- **问题**：同一语义（cookie 过期）在不同业务模式（detail-only vs official-full）使用不同状态码，违反一致性规则，前端需为同一含义写多套处理逻辑
- **修复建议**：
  ```python
  # ✅ 两种模式统一使用 440
  raise CollectionError(440, "cookie 失效", item_id=item_id)
  ```
- **配置节点**：`status_code_audit.consistency_rules[0]`（semantic: cookie_expired, expected_code: 440, applies_to: [detail_only, official_full]）
- **规范引用**：meta-rule #66 / xianyu-hunter-dev v4.40.0
- **适用**：多模式业务共享同一异常类；多渠道采集；同一服务的不同实现路径
- **不适用**：完全独立的服务；无状态码透传的接口
```

### B-REVIEW-189 路由透传未校验认证层状态码

```
### 🟠 [HIGH] B-REVIEW-189：路由透传 CollectionError 未校验是否属于认证层专属状态码

- **位置**：`src/xianyu_hunter/web/routes/api_items.py` 第 X 行
- **当前代码**：
  ```python
  # ❌ 无条件透传状态码，未校验 e.status_code 是否属于认证层专属
  @router.post("/{item_id}/refresh")
  async def refresh_item(item_id: int, task_id: str):
      try:
          result = await collection_service.refresh(item_id, task_id)
          return result
      except CollectionError as e:
          raise HTTPException(status_code=e.status_code, detail=e.detail)
  ```
- **问题**：路由层无条件透传 CollectionError 的状态码，若上游业务代码误抛 401，则会被前端误判为认证失效。路由透传应通过单元测试或断言确保上游不会抛出认证层专属状态码
- **修复建议**：
  ```python
  # ✅ 通过单元测试覆盖 CollectionError 不抛出 401/403
  # tests/test_collection_service.py
  @pytest.mark.parametrize("status_code", [401, 403])
  def test_collection_error_not_use_auth_codes(status_code):
      with pytest.raises(AssertionError):
          CollectionError(status_code, "test")
  ```
- **配置节点**：`status_code_audit.detection_patterns.route_transparent_pass`
- **规范引用**：meta-rule #66 / xianyu-hunter-dev v4.40.0
- **适用**：所有透传 CollectionError 的路由；FastAPI/Flask 等使用 HTTPException 的框架
- **不适用**：直接构造响应的路由（不使用 HTTPException）；内部 RPC 调用
```

## 🆕 v4.48.0 async_timeout_protection 审查报告条目（B-REVIEW-226~228）

> 本节为 v4.48.0 新增检查点 B-REVIEW-226/227/228 的报告条目模板。审查时按实际代码填写「位置」「当前代码」「问题」，其余字段保持模板结构一致。

### B-REVIEW-226 ASYNC-BLOCKING-CALL-TIMEOUT async 阻塞调用超时保护

```
### 🔴 [CRITICAL] B-REVIEW-226：async 阻塞调用缺少 asyncio.wait_for 超时保护

- **位置**：`scripts/browser_login.py` 第 X 行（Cookie 导出阶段）
- **当前代码**：
  ```python
  # ❌ context.cookies() 与 bc.storage_state() 在浏览器 IPC 阻塞时会永久挂起
  cookies = await context.cookies()
  storage = await bc.storage_state()
  ```
- **问题**：Playwright 跨 IPC 调用 `context.cookies()` / `bc.storage_state()` 未用 `asyncio.wait_for` 包裹超时，浏览器进程卡死时永久阻塞，子进程心跳停滞，后端 90s 后误判卡死并 kill 子进程，丢失已登录 Cookie。违反 B-REVIEW-226。
- **修复建议**：
  ```python
  # ✅ 用 asyncio.wait_for 包裹，超时值从 config 读取
  import asyncio
  from xianyu_hunter.config import load_config
  cfg = load_config()
  _ts = cfg.async_timeout_protection.timeout_by_category
  try:
      cookies = await asyncio.wait_for(context.cookies(), timeout=_ts.heavy_serialize)
      storage = await asyncio.wait_for(bc.storage_state(), timeout=_ts.heavy_serialize)
  except asyncio.TimeoutError:
      logger.warning("cookie export timed out, fallback to empty")
      cookies, storage = [], {}
  ```
- **配置节点**：`async_timeout_protection.enabled` / `async_timeout_protection.timeout_by_category.{lightweight_read,heavy_serialize,evaluate}` / `async_timeout_protection.fallback_strategy` / `async_timeout_protection.audit_grep_pattern`
- **规范引用**：meta-rule #80 / xianyu-hunter-dev v4.48.0
- **适用**：Playwright async API（cookies/storage_state/snapshot/title/url/evaluate）、httpx 长连接、aiohttp websocket
- **不适用**：Playwright 自带 timeout 参数的调用（page.goto/wait_for_load_state）、同步 API、一次性调用且失败即终止的场景
```

### B-REVIEW-227 SUBPROCESS-HEARTBEAT-STAGE-COORDINATION 子进程心跳与阶段超时协同

```
### 🔴 [CRITICAL] B-REVIEW-227：子进程心跳架构中阶段未区分 status + 累计超时超过心跳阈值

- **位置**：`scripts/browser_login.py` 第 X 行（status file 写入逻辑 + 阻塞调用累计）
- **当前代码**：
  ```python
  # ❌ 所有阶段共用单一 running status，后端按 90s 阈值判定
  def write_status(stage):
      status_file.write_text("running")  # 违规：阶段未区分

  # already_logged 阶段累计超时 80s > 90 × (1 - 0.3) = 63s
  cookies = await asyncio.wait_for(context.cookies(), timeout=30)
  storage = await asyncio.wait_for(bc.storage_state(), timeout=30)
  snapshot = await asyncio.wait_for(page.snapshot(), timeout=20)
  ```
- **问题**：子进程仅定义单一 `running` status + 单一 90s 阈值，但 `already_logged` 阶段累计阻塞调用超时 80s > 90 × (1 - 0.3) = 63s，后端按 `running` 阈值 90s 判定时可能在 80s 处误判卡死并 kill 子进程。违反 B-REVIEW-227。
- **修复建议**：
  ```python
  # ✅ 每阶段独立 status + 独立阈值，累计超时 < 阈值 × (1 - safety_margin)
  from xianyu_hunter.config import load_config
  cfg = load_config()
  _hb = cfg.subprocess_heartbeat

  def enter_stage(stage: str):
      if stage not in _hb.timeout_by_status:
          raise ValueError(f"unknown stage: {stage}")
      status_file.write_text(stage)  # 后端按 stage 查 timeout_by_status[stage]

  async def export_all(context, bc, page):
      enter_stage("already_logged")  # 阈值 90s，允许累计 63s
      cookies = await asyncio.wait_for(context.cookies(), timeout=10)
      storage = await asyncio.wait_for(bc.storage_state(), timeout=10)
      snapshot = await asyncio.wait_for(page.snapshot(), timeout=10)
      # 累计 30s < 63s  ✅
  ```
- **配置节点**：`subprocess_heartbeat.enabled` / `subprocess_heartbeat.timeout_by_status.{starting,opening,running,waiting,already_logged}` / `subprocess_heartbeat.safety_margin` / `subprocess_heartbeat.max_accumulated_timeout_warn`
- **规范引用**：meta-rule #81 / xianyu-hunter-dev v4.48.0
- **适用**：subprocess.Popen + status file 心跳架构；多阶段长时间任务（登录→导出→采集）；后端轮询前端 status file 判定超时的场景
- **不适用**：同步请求-响应模式（FastAPI 路由直接 await）；后台一次性任务；纯前端状态管理
```

### B-REVIEW-228 CROSS-BLOCK-CONSISTENCY-CHECK 跨代码块一致性检查

```
### 🟡 [MAJOR] B-REVIEW-228：同一 API 在多处调用时保护措施不一致

- **位置**：`scripts/browser_login.py` 第 X 行 / `scripts/auth_helper.py` 第 Y 行（两处 `context.cookies()` 调用）
- **当前代码**：
  ```python
  # scripts/browser_login.py - 主登录流程（有保护）
  cookies = await asyncio.wait_for(context.cookies(), timeout=10)  # ✅

  # scripts/auth_helper.py - 快速导出路径（无保护，违规）
  cookies = await context.cookies()  # ❌ 同一 API 无 asyncio.wait_for
  ```
- **问题**：`context.cookies()` 在 ≥2 处调用，但保护措施不一致：主登录流程有 `asyncio.wait_for` 保护，快速导出路径无保护。一旦快速导出路径走 IPC 阻塞分支，复现 B-REVIEW-226 已修复的问题。违反 B-REVIEW-228（以更严格者为准）。
- **修复建议**：
  ```python
  # ✅ 两处调用统一保护，超时值从 config 读取
  from xianyu_hunter.config import load_config
  cfg = load_config()
  _ts = cfg.async_timeout_protection.timeout_by_category

  # scripts/browser_login.py
  cookies = await asyncio.wait_for(context.cookies(), timeout=_ts.heavy_serialize)

  # scripts/auth_helper.py
  cookies = await asyncio.wait_for(context.cookies(), timeout=_ts.heavy_serialize)
  ```
- **配置节点**：`consistency_check.enabled` / `consistency_check.min_occurrences` / `consistency_check.scan_paths`
- **规范引用**：meta-rule #82 / xianyu-hunter-dev v4.48.0
- **适用**：同一 API 在多处调用的场景；复用代码片段（多个登录方式共享 Cookie 导出逻辑）；重构后检查是否漏改
- **不适用**：首次实现的唯一调用点；故意差异化的实现（测试 stub vs 生产代码）；不同框架的类似操作（Playwright page.goto() vs httpx client.get()）
```

## 🆕 v4.49.1 测试质量与同步性报告条目（B-REVIEW-229~236）

> 本节为 v4.49.1 新增 8 项检查点（meta-rules #83-90 后端落地）的报告条目模板。每条违规按以下格式记录，参数在 `config.yaml#test_quality_protection` / `config.yaml#soft_delete_data_isolation` / `config.yaml#es_resilience_precheck` / `config.yaml#multi_user_id_propagation` 节点管理。

### B-REVIEW-229 MONKEYPATCH-FROM-IMPORT-COVERAGE monkeypatch 模块级 from-import 覆盖完整性

```
### 🔴 [CRITICAL] B-REVIEW-229：测试仅 patch 源模块而漏掉被测模块顶层 from-import 引用

- **位置**：`tests/test_xxx.py` 第 X 行
- **当前代码**：
  ```python
  # 被测代码 src/xianyu_hunter/xxx.py
  from xianyu_hunter.core import cookie_helper

  def use_cookie():
      cookie_helper.refresh()

  # 测试代码
  monkeypatch.setattr("xianyu_hunter.core.cookie_helper.refresh", lambda: None)  # ❌
  ```
- **问题**：被测代码 `from xianyu_hunter.core import cookie_helper` 在 `xxx` 模块建立了独立的 `cookie_helper` 引用，patch 源模块属性无法影响 `xxx` 模块已 import 的引用，测试无法真正生效（假阳性通过）
- **修复建议**：patch 被测模块的属性 `monkeypatch.setattr("xianyu_hunter.xxx.cookie_helper.refresh", lambda: None)`，并扫描被测模块所有 `from X import Y` 语句逐项 patch
- **配置节点**：`test_quality_protection.monkeypatch_coverage.enabled` / `.severity` / `.detection_patterns` / `.required_coverage_scope`
- **规范引用**：meta-rule #83 / xianyu-hunter-dev v4.49.1
- **适用**：所有使用 monkeypatch / unittest.mock.patch 的测试代码
- **不适用**：纯函数测试（无模块级 import）、fixture 注入式测试
```

### B-REVIEW-230 ASYNC-SYNC-TEST-CALL-MATCH 同步/异步方法测试调用匹配

```
### 🔴 [CRITICAL] B-REVIEW-230：测试对 async 方法用 MagicMock 而非 AsyncMock

- **位置**：`tests/test_xxx.py` 第 X 行
- **当前代码**：
  ```python
  # 被测代码
  async def fetch_data(self): ...

  # 测试代码
  repo.fetch_data = MagicMock(return_value={...})  # ❌
  result = await repo.fetch_data()  # TypeError: object dict can't be used in 'await' expression
  ```
- **问题**：被测方法是 `async def`，测试用 `MagicMock` 而非 `AsyncMock`，`await` 调用返回的不是 awaitable，触发 `TypeError`
- **修复建议**：`repo.fetch_data = AsyncMock(return_value={...})`，并确保测试用 `@pytest.mark.asyncio` 标注
- **配置节点**：`test_quality_protection.async_sync_test_match.enabled` / `.severity` / `.mock_class_for_async` / `.mock_class_for_sync` / `.await_required_for_async`
- **规范引用**：meta-rule #84 / xianyu-hunter-dev v4.49.1
- **适用**：所有 async/sync 方法测试
- **不适用**：纯同步代码、无 mock 的端到端测试
```

### B-REVIEW-231 PROPERTY-RENAME-SERIALIZE-FIELD-SEP 属性名重构与序列化字段名分离

```
### 🟠 [HIGH] B-REVIEW-231：属性名重构后序列化字段名跟随变更导致前后端契约破裂

- **位置**：`src/xianyu_hunter/models/xxx.py` 第 X 行
- **当前代码**：
  ```python
  # 重构前（前端契约使用 camelCase）
  class Item:
      itemUrl: str

  # 重构后（属性名改 snake_case，序列化字段名也跟着改了）
  class Item:
      item_url: str  # ❌ JSON 输出变成 "item_url"，前端读不到 "itemUrl"
  ```
- **问题**：属性名从 `itemUrl` 重构为 `item_url`（PEP 8 合规），但未用 `alias` 分离序列化字段名，JSON 输出键名同步变更，前端契约破裂
- **修复建议**：用 Pydantic `Field(alias="itemUrl")` 或 dataclass `field(metadata={"alias": "itemUrl"})` 分离属性名与序列化字段名，测试断言同步更新到新属性名
- **配置节点**：`test_quality_protection.property_rename_serialize.enabled` / `.severity` / `.require_alias_separation` / `.serialization_field_name_stability`
- **规范引用**：meta-rule #85 / xianyu-hunter-dev v4.49.1
- **适用**：数据类属性名重构、跨进程序列化场景
- **不适用**：纯内部数据类、无序列化需求的 DTO
```

### B-REVIEW-232 FASTAPI-ENDPOINT-SIGNATURE-TEST-SYNC FastAPI 端点签名变更测试同步

```
### 🔴 [CRITICAL] B-REVIEW-232：端点签名新增 request / user_id 参数后测试未同步更新

- **位置**：`tests/test_xxx.py` 第 X 行
- **当前代码**：
  ```python
  # 被测代码（端点签名已变更）
  @router.post("/items")
  async def create_item(payload: ItemIn, request: Request, user_id: str = Depends(...)):
      ...

  # 测试代码（仍用旧签名调用）
  async def test_create_item():
      await create_item(payload)  # ❌ TypeError: missing 2 required positional arguments
  ```
- **问题**：端点签名新增 `request: Request` / `user_id: str` 参数后，测试仍用旧签名调用，mock 缺少对应参数，所有相关测试批量失败
- **修复建议**：测试中用 `AsyncMock(spec=Request)` 构造 `request` 对象，设置 `request.state.user_id = "default"`，并传入 `user_id="default"` 参数；用 `inspect.signature(endpoint)` 检测签名漂移
- **配置节点**：`test_quality_protection.fastapi_endpoint_test_sync.enabled` / `.severity` / `.detect_signature_drift` / `.required_test_param_match`
- **规范引用**：meta-rule #86 / xianyu-hunter-dev v4.49.1
- **适用**：FastAPI 端点签名变更、新增依赖注入参数
- **不适用**：纯函数测试、无签名变更
```

### B-REVIEW-233 SOFT-DELETE-CATEGORY-ISOLATION 软删除数据分类隔离

```
### 🟠 [HIGH] B-REVIEW-233：分类统计混淆 NULL 外键与已删除外键

- **位置**：`src/xianyu_hunter/repository/xxx.py` 第 X 行
- **当前代码**：
  ```python
  # ❌ 分类统计将 NULL 与已删除外键混淆
  rows = session.execute(text("""
      SELECT category, COUNT(*) FROM items
      WHERE deleted_at IS NULL OR category_id IS NULL
      GROUP BY category
  """))
  ```
- **问题**：分类统计查询将 `category_id IS NULL`（孤儿数据，应归入「未分类」）与 `deleted_at IS NOT NULL`（已删除，应跳过统计）混淆，导致孤儿数据被错误跳过、已删除数据被错误计入未分类
- **修复建议**：
  ```python
  # ✅ 显式区分两种情况
  rows = session.execute(text("""
      SELECT
          CASE
              WHEN deleted_at IS NOT NULL THEN 'skip'
              WHEN category_id IS NULL THEN 'uncategorized'
              ELSE category
          END AS bucket,
          COUNT(*)
      FROM items
      GROUP BY bucket
      HAVING bucket <> 'skip'
  """))
  ```
- **配置节点**：`soft_delete_data_isolation.enabled` / `.severity` / `.classification_rules.orphan_rule` / `.classification_rules.deleted_rule`
- **规范引用**：meta-rule #87 / xianyu-hunter-dev v4.49.1
- **适用**：所有软删除 + 外键分类统计的查询
- **不适用**：无软删除的表、无外键分类的查询
```

### B-REVIEW-234 ES-RESILIENCE-PRECHECK ES 弹性预检（扫描前检查）

```
### 🟠 [HIGH] B-REVIEW-234：SonarQube 扫描前未做 ES 弹性预检

- **位置**：`scripts/run_sonarqube_scan.py` 第 X 行
- **当前代码**：
  ```python
  # ❌ 直接启动扫描，未预检 ES 状态
  subprocess.run(["sonar-scanner", f"-Dproject.settings={config}"], check=True)
  # 扫描中 ES 被锁（read_only_allow_delete=true），CE 报告写入失败
  ```
- **问题**：扫描前未检测 ES `read_only_allow_delete` 锁，扫描中 ES 磁盘水位超阈值自动加锁，CE（Compute Engine）报告写入失败，SonarQube 任务标记 FAILED
- **修复建议**：
  ```python
  # ✅ 扫描前预检 ES 并解锁
  import httpx
  resp = httpx.get(f"{es_host}:{es_port}/_cluster/settings")
  if "read_only_allow_delete" in resp.text and "true" in resp.text:
      httpx.put(f"{es_host}:{es_port}/_cluster/settings",
                json={"transient": {"cluster.blocks.read_only_allow_delete": None}})
      logger.warning("ES read_only_allow_delete 已解锁")
  ```
- **配置节点**：`es_resilience_precheck.enabled` / `.severity` / `.es_endpoint.host` / `.es_endpoint.port` / `.read_only_indicator` / `.unlock_action`
- **规范引用**：meta-rule #88 / xianyu-hunter-dev v4.49.1
- **适用**：SonarQube 全量扫描、依赖 ES 写入的批处理任务
- **不适用**：不依赖 ES 的扫描、ES 单机开发环境
```

### B-REVIEW-235 PYTEST-TIMEOUT-CONFIG 测试超时配置

```
### 🟡 [MAJOR] B-REVIEW-235：大规模测试套件无 pytest-timeout 超时保护

- **位置**：`pyproject.toml` 第 X 行
- **当前代码**：
  ```toml
  [tool.pytest.ini_options]
  # ❌ 未配置 timeout，单测卡死导致 CI 整体超时（30 分钟）
  testpaths = ["tests"]
  ```
- **问题**：`pyproject.toml` 未配置 `pytest-timeout` 超时，单个测试用例卡死（如 Playwright 等待选择器）会导致整个 CI 流水线超时，无法定位具体卡死的测试
- **修复建议**：
  ```toml
  [tool.pytest.ini_options]
  timeout = 30                          # 默认 30s 超时
  timeout_method = "thread"             # 兼容 async 测试
  # 大规模套件分批运行，单批 ≤ 200 个
  ```

  ```python
  # 慢测试单独标注更长超时
  @pytest.mark.timeout(120)
  @pytest.mark.asyncio
  async def test_full_collection(): ...
  ```
- **配置节点**：`test_quality_protection.pytest_timeout_config.enabled` / `.severity` / `.default_timeout_seconds` / `.slow_test_marker` / `.max_tests_per_batch`
- **规范引用**：meta-rule #89 / xianyu-hunter-dev v4.49.1
- **适用**：大规模测试套件（≥100 个测试）、CI 流水线测试
- **不适用**：小型测试集（<50 个）、本地快速测试
```

### B-REVIEW-236 MULTI-USER-ID-PROPAGATION 多用户隔离 user_id 透传一致性

```
### 🔴 [CRITICAL] B-REVIEW-236：端点取到 user_id 后未透传到下游 service 导致跨用户数据污染

- **位置**：`src/xianyu_hunter/web/routes/api_xxx.py` 第 X 行
- **当前代码**：
  ```python
  @router.get("/items")
  async def list_items(request: Request):
      user_id = request.state.user_id  # ✅ 取到 user_id
      # ❌ 只存局部变量，未传入下游 service
      items = await item_service.list_items()  # item_service 无 user_id 参数，返回所有用户数据
      return items
  ```
- **问题**：端点取到 `user_id` 后只存局部变量，未传入下游 `item_service.list_items(user_id)`，service 层无 `user_id` 过滤，返回所有用户数据，跨用户数据污染
- **修复建议**：
  ```python
  @router.get("/items")
  async def list_items(request: Request):
      user_id = request.state.user_id
      # ✅ 全链路透传：route → service → repository → external_api
      items = await item_service.list_items(user_id=user_id)
      return items

  # service 层
  async def list_items(self, user_id: str):
      return await self.repo.list_items(user_id=user_id)

  # repository 层
  async def list_items(self, user_id: str):
      return session.execute(select(Item).where(Item.user_id == user_id))
  ```
- **配置节点**：`multi_user_id_propagation.enabled` / `.severity` / `.user_id_source` / `.default_value` / `.required_propagation_layers`
- **规范引用**：meta-rule #90 / xianyu-hunter-dev v4.49.1
- **适用**：多用户系统、多租户系统、多账号管理
- **不适用**：单用户工具、内部微服务通信
```

## 🆕 v4.50.0 数据透传与职责分离规范报告条目（B-REVIEW-238~241）

> 本节为 v4.50.0 新增检查点 B-REVIEW-238/239/240/241 的报告条目模板。审查时按实际代码填写「位置」「当前代码」「问题」，其余字段保持模板结构一致。

### B-REVIEW-238 DATA-PROPAGATION-INTEGRITY 跨层数据透传完整性

```
### 🔴 [CRITICAL] B-REVIEW-238：跨层调用链中 user_id/task_id/request_id 未完整透传到最底层

- **位置**：`src/xianyu_hunter/modules/collection_service.py` 第 X 行
- **当前代码**：
  ```python
  # ❌ 入口层接收 user_id 但中间层未透传
  async def _evaluate_and_notify(self, item, task_id):
      # user_id 在此处丢失
      eval_event = await self._save_eval_event(item, task_id)
      return eval_event

  async def _save_eval_event(self, item, task_id):
      # ❌ 调用 upsert_eval_event 未传入 user_id，依赖默认值 "default"
      await repo_events.upsert_eval_event(event)
  ```
- **问题**：入口层 `_evaluate_and_notify` 未接收/透传 `user_id`，下游 `_save_eval_event` → `upsert_eval_event` 依赖默认值 `"default"`，导致多用户隔离过滤把官方采集评估记录隐藏
- **修复建议**：
  ```python
  # ✅ 全链路透传 user_id
  async def _evaluate_and_notify(self, item, task_id, user_id: str):
      eval_event = await self._save_eval_event(item, task_id, user_id=user_id)
      return eval_event

  async def _save_eval_event(self, item, task_id, *, user_id: str):
      await repo_events.upsert_eval_event(event, user_id=user_id)
  ```
- **配置节点**：`data_propagation.propagation_integrity.required_propagation_fields` / `.check_mode` / `.exempt_scenarios`
- **规范引用**：meta-rule #83 / xianyu-hunter-dev v4.50.0
- **适用**：多层架构（domain→infra→modules→web）、含 user_id/task_id 隔离的链路
- **不适用**：单层脚本、后台任务（无 HTTP 请求上下文）
```

### B-REVIEW-239 SNAPSHOT-VS-LATEST-SEPARATION 快照与最新值职责分离

```
### 🔴 [CRITICAL] B-REVIEW-239：enrich 覆盖字段前未保存快照导致过滤函数用最新值误判

- **位置**：`src/xianyu_hunter/web/services/evaluations_list.py` 第 X 行
- **当前代码**：
  ```python
  # ❌ enrich 用最新价格覆盖 payload.item_price，过滤也用覆盖后的最新价格
  def _apply_positive_fields(self, item, payload):
      item.item_price = payload.item_price  # 覆盖了评估时快照

  def _filter_price_range(self, items, min_price, max_price):
      # ❌ 用最新价格过滤，旧 eval 事件被误判超范围
      return [i for i in items if min_price <= i.item_price <= max_price]
  ```
- **问题**：enrich 流程用 items 表最新价格覆盖了 `payload.item_price`，过滤函数 `_filter_price_range` 也用覆盖后的最新价格过滤，导致旧 eval 事件被按新价格误判超范围隐藏
- **修复建议**：
  ```python
  # ✅ enrich 覆盖前保存快照，过滤优先用快照
  def _apply_positive_fields(self, item, payload):
      # 保存评估时快照
      item._eval_snapshot_price = item.item_price
      item.item_price = payload.item_price  # 展示用最新值

  def _filter_price_range(self, items, min_price, max_price):
      # 过滤优先用快照
      return [i for i in items
              if min_price <= getattr(i, '_eval_snapshot_price', i.item_price) <= max_price]
  ```
- **配置节点**：`data_propagation.snapshot_latest_separation.snapshot_required_fields` / `.snapshot_field_prefix` / `.filter_priority`
- **规范引用**：meta-rule #83 / xianyu-hunter-dev v4.50.0
- **适用**：采集-评估-展示链路、含 enrich 覆盖字段的过滤场景
- **不适用**：纯展示场景（无过滤）、稳定数据源（无 enrich）
```

### B-REVIEW-240 FALLBACK-DATA-MERGE-COMPLETENESS Fallback 路径数据合并完整性

```
### 🔴 [CRITICAL] B-REVIEW-240：fallback 路径返回数据未合并所有可用来源导致维度判定失败

- **位置**：`src/xianyu_hunter/scheduler/worker.py` 第 X 行（`_collect_detail_and_seller` 函数）
- **当前代码**：
  ```python
  # ❌ seller_profile 成功后未合并 detail 页字段
  async def _collect_detail_and_seller(self, item_id):
      detail = await self._fetch_detail(item_id)
      seller_profile = await self._fetch_seller_profile(item_id)
      if seller_profile:
          # ❌ 仅返回 seller_profile，未合并 detail 字段
          return seller_profile
      return detail
  ```
- **问题**：`_collect_detail_and_seller` 在 `seller_profile` 成功后未合并 `detail` 页字段，导致 evaluator 维度判定失败 → insufficient 模式 → cap 65 分
- **修复建议**：
  ```python
  # ✅ 主源成功后也必须合并次源字段
  async def _collect_detail_and_seller(self, item_id):
      detail = await self._fetch_detail(item_id) or {}
      seller_profile = await self._fetch_seller_profile(item_id) or {}
      # 合并所有可用来源
      return {**detail, **seller_profile}
  ```
- **配置节点**：`data_propagation.fallback_data_merge.fallback_functions` / `.merge_on_primary_success` / `.empty_check_semantics`
- **规范引用**：meta-rule #83 / xianyu-hunter-dev v4.50.0
- **适用**：有 fallback 机制的采集流程、多数据源合并场景
- **不适用**：稳定数据源（无 fallback）、单源数据
```

### B-REVIEW-241 MULTIUSER-ISOLATION-WRITE-CONSISTENCY 多用户隔离写入一致性

```
### 🔴 [CRITICAL] B-REVIEW-241：数据库写入未显式传入 user_id 依赖默认值导致多用户数据错位

- **位置**：`src/xianyu_hunter/infra/repo_events.py` 第 X 行（`upsert_eval_event` 方法）
- **当前代码**：
  ```python
  # ❌ upsert_eval_event 依赖默认值 user_id="default"
  async def upsert_eval_event(self, event, user_id: str = "default"):
      session.add(event)
      session.commit()
  ```
- **问题**：`upsert_eval_event` 等写入方法依赖默认值 `user_id="default"`，调用方未显式传入 user_id 时，写入的数据 user_id 为 "default"，多用户隔离过滤会把官方采集评估记录隐藏
- **修复建议**：
  ```python
  # ✅ 显式传入 user_id，不依赖默认值
  async def upsert_eval_event(self, event, *, user_id: str):
      # 关键字参数强制调用方传入
      event.user_id = user_id
      session.add(event)
      session.commit()

  # DELETE 也附加 user_id 过滤（深度防御）
  async def delete_eval_event(self, event_id, *, user_id: str):
      session.execute(delete(EventRow).where(
          EventRow.id == event_id,
          EventRow.user_id == user_id  # 附加 user_id 过滤
      ))
  ```
- **配置节点**：`data_propagation.multiuser_write_consistency.required_user_id_methods` / `.default_value_is_bug` / `.delete_with_user_filter`
- **规范引用**：meta-rule #83 / xianyu-hunter-dev v4.50.0
- **适用**：多用户系统（user_id 隔离）、多租户系统
- **不适用**：单用户系统、系统级操作（如 _log_* / _stats_*）
```

## 🆕 v4.38.0 配置节点缺失检查（meta_rules_57_63）

> 若 `config.yaml` 中缺少 `meta_rules_57_63` 节点或其子节点，配置驱动检查将无法生效。审查报告必须列出缺失的配置节点。

| 缺失节点 | 影响范围 | 修复建议 |
|----------|----------|----------|
| `meta_rules_57_63.async_await_check` | B-REVIEW-182 无法判定白名单装饰器与 async generator 豁免 | 从 `config.example.yaml` 复制完整节点 |
| `meta_rules_57_63.resource_pool_benchmark` | B-REVIEW-183 无法判定开销阈值与资源池类型 | 同上 |
| `meta_rules_57_63.http_status_code_mapping` | B-REVIEW-184 无法判定 reason 字段名与默认状态码 | 同上 |
| `meta_rules_57_63.css_selector_fallback` | B-REVIEW-185 无法判定降级级数与 dump 触发条件 | 同上 |
| `meta_rules_57_63.exception_log_semantic` | B-REVIEW-186 无法判定禁用模式与关键路径函数 | 同上 |
| `meta_rules_57_63.external_resource_lifecycle` | B-REVIEW-187 无法判定资源类型与配对函数 | 同上 |
| `meta_rules_57_63.db_write_identity_trace` | B-REVIEW-188 无法判定函数模式与豁免清单 | 同上 |

## 🆕 v4.61.0 重构安全性审查报告（B-REVIEW-281~290）

> 本节为 v4.61.0 新增 10 项检查点（复盘规范集后端落地）的报告条目模板。审查时按实际代码填写「位置」「当前代码」「问题」，其余字段保持模板结构一致。所有阈值通过 `config.yaml#refactoring_safety` 节点管理，技能本身不含硬编码值。

### 配置化重构核对（B-REVIEW-281 / 282 / 283）

> 列出本次审查中检测到的配置化重构变更，核对 5 步法每步的执行状态。

| 旧常量名 | 新函数名/Config 字段 | 步骤 1 grep | 步骤 2 Config 字段 | 步骤 3 YAML 块 | 步骤 4 _get_xxx() | 步骤 5 强制核对 | 异常回退 |
|----------|---------------------|-------------|---------------------|----------------|---------------------|-----------------|----------|
| `TAKEOVER_TIMEOUT_MIN` | `_get_takeover_timeout_min()` | ✅ | ✅ | ✅ | ✅ | ❌ 漏 `startup.py:161` | ✅ |
| `_LIVE_CACHE_TTL` | `CacheConfig.live_search_ttl` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

**作用域契约校验（B-REVIEW-282）**：

| 函数位置 | 函数类型 | 违规访问 | 修复建议 |
|----------|----------|----------|----------|
| `container.py:450` | 模块级函数 | `self.config.buyer` | 改为 `cfg = get_config(); cfg.buyer` |

**导入名称变更 checklist（B-REVIEW-283）**：

| 删除/改名的导出符号 | grep 引用点数 | 已同步更新 | 运行时验证 |
|---------------------|---------------|------------|------------|
| `TAKEOVER_TIMEOUT_MIN` | 3 处 | ❌ 2/3（漏 `startup.py:161`） | ❌ 未执行 |

### 跨文件引用影响图（B-REVIEW-289）

> 显示导出符号变更的跨文件传播路径，标识受影响的文件和行号。

```
module_a.OLD_CONST
  ├── module_b.py:45  from module_a import OLD_CONST        ❌ 未更新
  ├── module_c.py:120 OLD_CONST.value                       ❌ 未更新
  └── tests/test_a.py:23 from module_a import OLD_CONST     ✅ 已更新为 _get_new_const()
```

**运行时验证结果**：

| 验证类型 | 命令 | 结果 | 捕获异常 |
|----------|------|------|----------|
| 启动服务 | `python -m xianyu_hunter.web.startup` | ❌ 失败 | `ImportError: cannot import name 'TAKEOVER_TIMEOUT_MIN'` at `startup.py:161` |
| 运行测试 | `pytest tests/ -x --timeout=60` | ❌ 失败 | `NameError: name 'OLD_CONST' is not defined` at `module_b.py:45` |

### 硬编码业务参数清单（B-REVIEW-290）

> 列出扫描到的模块级硬编码业务参数常量，标注应迁移到的 Config 字段。

| 文件位置 | 硬编码常量 | 值 | 应迁移到的 Config 字段 | 异常回退默认值 |
|----------|------------|-----|------------------------|----------------|
| `src/xianyu_hunter/collector/live_search.py:23` | `_LIVE_CACHE_TTL = 60` | 60 | `CacheConfig.live_search_ttl` | 60 |
| `src/xianyu_hunter/scheduler/worker.py:45` | `_RETRY_COUNT = 3` | 3 | `RetryConfig.default_count` | 3 |

### PowerShell 长任务日志输出检查（B-REVIEW-284 / 285）

> 列出 `scripts/` 目录下检测到的 sink cmdlet 违规与资源过载容错情况。

| 脚本位置 | 违规命令 | 推荐替代 | 阈值（秒） |
|----------|----------|----------|------------|
| `scripts/run_tests.ps1:12` | `pytest tests/ \| Select-Object -Last 50` | `pytest tests/ > test.log; Get-Content -Tail 50 test.log` | 30 |

**资源过载容错（B-REVIEW-285）**：

| 检查项 | 当前值 | 阈值 | 状态 |
|--------|--------|------|------|
| CPU 占用 | 92% | 90% | ⚠️ 超阈值，建议降级 |
| 内存占用 | 78% | 85% | ✅ 正常 |
| 完整 pytest 超时 | 320 秒 | 300 秒 | ❌ 超时，降级到 Tier 2 |

### 测试验证档位标记（B-REVIEW-288）

> 报告末尾标注本次审查使用的测试验证档位及降级原因。

| 档位 | 触发条件 | 执行内容 | 结果 | 降级原因 |
|------|----------|----------|------|----------|
| Tier 1 完整测试集 | 改动文件数 15 ≤ 200 | `pytest tests/ -x --timeout=300` | ❌ 超时 | CPU 92% > 90% 阈值 |
| Tier 2 直接 import 测试 | Tier 1 超时降级 | `python -c "from xianyu_hunter.xxx import yyy"` | ✅ 通过 | - |

### 历史失败案例引用

> 每个重构安全性违规必须引用对应的历史失败案例，说明"为什么这么做"的真实教训。

| 检查点 | 历史案例 | 教训 |
|--------|----------|------|
| B-REVIEW-281 CONFIG-REFACTOR-5STEP | `container.py:450` `self.config.buyer` 应为 `cfg.buyer` | 模块级函数误用 self，5 步法步骤 5 未核对调用点作用域 |
| B-REVIEW-283 IMPORT-NAME-CHECKLIST | `startup.py:161` `from xxx import TAKEOVER_TIMEOUT_MIN` 应为 `_get_takeover_timeout_min` | 常量改名后调用方未同步更新 import，checklist 步骤 1 未执行 |
| B-REVIEW-290 CONFIG-ACCESS-UNIFIED-ENTRY | `_LIVE_CACHE_TTL = 60` 硬编码 | 业务参数散落模块级，调整需改代码且不同模块有不同值 |

### 重构安全性配置节点缺失检查

> 若 `config.yaml` 中缺少 `refactoring_safety` 节点或其子节点，配置驱动检查将无法生效。审查报告必须列出缺失的配置节点。

| 缺失节点 | 影响范围 | 修复建议 |
|----------|----------|----------|
| `refactoring_safety.refactor_5step` | B-REVIEW-281 无法判定 5 步法必需步骤与异常回退要求 | 从 `config.example.yaml` 复制完整节点 |
| `refactoring_safety.scope_contract` | B-REVIEW-282 无法判定作用域契约规则 | 同上 |
| `refactoring_safety.import_name_change` | B-REVIEW-283 无法判定导入名称变更 checklist | 同上 |
| `refactoring_safety.long_task_output` | B-REVIEW-284 无法判定长任务阈值与禁用模式 | 同上 |
| `refactoring_safety.resource_overload_tolerance` | B-REVIEW-285 无法判定 CPU/内存阈值与降级策略 | 同上 |
| `refactoring_safety.sonarqube_pipeline` | B-REVIEW-286 无法判定 SonarQube 闭环必需阶段 | 同上 |
| `refactoring_safety.resilience_recovery` | B-REVIEW-287 无法判定弹性恢复机制开关 | 同上 |
| `refactoring_safety.test_verify_tiers` | B-REVIEW-288 无法判定测试验证三档阈值 | 同上 |
| `refactoring_safety.cross_file_sync` | B-REVIEW-289 无法判定跨文件引用同步校验规则 | 同上 |
| `refactoring_safety.config_access_unified` | B-REVIEW-290 无法判定配置访问统一入口规则 | 同上 |

## 🆕 v4.70.0 源码文件编码完整性审查报告条目（B-REVIEW-337）

> 本节为 v4.70.0 新增检查点（基于登录页提示信息乱码复盘：后端源码中文被替换为字面量 `?` 0x3F，及 GBK 误读为 UTF-8 乱码）。配套 xianyu-hunter-dev step 280、前端 F-REVIEW-246、测试模式 AK。判定参数全部来自 `config.yaml#coding_standards.source_file_encoding_integrity`，**禁止硬编码**路径/阈值/严重级。扫描**只读**，仅输出 `file:line` 证据，不自动改写。

### B-REVIEW-337 检查结果汇总

| 检查点 | 名称 | 维度 | severity | 配置节点 | 违规数 | 状态 |
|--------|------|------|----------|----------|--------|------|
| B-REVIEW-337 | SOURCE-FILE-ENCODING-INTEGRITY 源码文件编码完整性 | 28. 编码规范 | HIGH | `coding_standards.source_file_encoding_integrity` | X | ✅ 通过 / ❌ 违规 |

### B-REVIEW-337 SOURCE-FILE-ENCODING-INTEGRITY 违规详情

> 后端源码文件**本体**在磁盘上出现非 ASCII 字符（中文等）被替换为连续 `?`（≥ `min_consecutive` 个）且处于非 ASCII 上下文，或含 U+FFFD 替换字符，或（可选）命中 GBK-as-UTF-8 误读特征（`鑱岃`/`、` 类）。编译/运行通常仍正常，但用户可见文案、注释、日志出现损坏，并污染 Git 历史。

**判定信号（来自配置）**：

| 信号 | 规则 | 配置键 |
|------|------|--------|
| 连续 `?` 且非 ASCII 上下文 | `[\u4e00-\u9fff]\?{N,}\|\?{N,}[\u4e00-\u9fff]`（N=`min_consecutive`） | `min_consecutive` |
| Unicode 替换字符 | 行内含 `\ufffd` | `check_fffd` |
| GBK 误读特征 | （`check_gbk_misdecode=true` 时）`鑱`/`、` 等非预期字符簇 | `check_gbk_misdecode` |

1. **问题描述**：[源码中文被替换为连续 `?` / 源码含 U+FFFD / 源码含 GBK 误读乱码 / HEAD 已提交版本携带损坏字符]
   - **位置**：`src/xianyu_hunter/web/routes/xxx.py` 第 X 行（扫描输出 `file:line`）
   - **证据（只读扫描命令）**：
     ```bash
     grep -rPn '[\x{4e00}-\x{9fff}]\?{3,}|\?{3,}[\x{4e00}-\x{9fff}]' src scripts
     grep -rPn '\x{fffd}' src scripts
     # 修复后全仓复扫确认 0 命中
     grep -rPn '\?{3,}' src scripts && echo "仍有残留" || echo "OK"
     ```
   - **当前代码**：
     ```python
     # ❌ 源码本体损坏：中文被替换为 ?
     self.set_status("??????，请重新登录")
     ```
   - **修复建议**：
     ```python
     # ✅ 还原正确的中文文案；python -m py_compile 校验语法
     self.set_status("登录已过期，请重新登录")
     ```
   - **配置节点**：`coding_standards.source_file_encoding_integrity`（scan_globs / scan_exclude / min_consecutive / check_fffd / check_gbk_misdecode / severity）
   - **规范引用**：xianyu-hunter-dev step 280（SOURCE-FILE-ENCODING-INTEGRITY-01）/ 前端 F-REVIEW-246 / 测试模式 AK
   - **修复协议**：S1 分类（源码本体 vs 运行时）→ S2 按 `scan_globs` 扫描 → S3 匹配信号 → S4 输出 `file:line` → S5 人工确认排除合法 `?`（URL 模板 / 正则可选匹配 / SQL `?` 参数占位）→ S6 还原中文 + `py_compile` 校验 → S7 全仓复扫 0 命中（必要时修正 HEAD 已提交版本）→ S8 pre-commit/CI 门禁
   - **适用**：含中文/非 ASCII 字符的后端源码（`.py`/`.ps1`/`.bat`/`.yaml`/`.md`）；跨编辑器/OS 保存后可疑 `?` 或乱码；合并冲突解决后；CI 门禁；历史提交回溯
   - **不适用**：运行时数据字段乱码（→ ENC 规范 / 测试模式 K）；终端 stdout 显示乱码（`B-REVIEW-WINDOWS-TERMINAL-ENCODING`）；浏览器字体缺失"方框/豆腐块"；字符串/正则/SQL 中合法 `?`；纯 ASCII 文件
   - **与已有规则的关系**：
     - 与 `B-REVIEW-WINDOWS-TERMINAL-ENCODING`（dim 28）**正交**：彼为运行时终端/Shell 编码，本为源码静态完整性
     - 与 ENC 系列（编码规范阈值）互补：运行时数据损坏由 ENC 与测试模式 K 覆盖

### v4.70.0 配置变更点

> 本次审查触发的 `config.yaml#coding_standards.source_file_encoding_integrity` 节点（新增）。所有参数遵循"无硬编码"原则。

| 变更类型 | 配置节点 | 当前值 | 建议值 | 变更理由 | 影响范围 |
|----------|----------|--------|--------|----------|----------|
| 扫描范围扩展 | `coding_standards.source_file_encoding_integrity.scan_globs` | `[src/**/*.py, scripts/**/*.py]` | `[...现有, <新 glob>]` | 项目新增源码目录 | B-REVIEW-337 |
| 阈值调整 | `coding_standards.source_file_encoding_integrity.min_consecutive` | `3` | `<新阈值>` | 误报/漏报调优 | B-REVIEW-337 |
| 开关开启 | `coding_standards.source_file_encoding_integrity.check_gbk_misdecode` | `false` | `true` | 需检测 GBK 误读类乱码 | B-REVIEW-337 |

**变更后自检清单**：
- [ ] 无硬编码新增（扫描路径/阈值/严重级均在 config 节点管理）
- [ ] 通用性未降低（参数化配置可被不同业务场景覆盖）
- [ ] 现有违规检测不失效（回归测试通过）
- [ ] references/checkpoints-index.md 已追加 B-REVIEW-337 索引
- [ ] references/source-file-encoding-integrity.md 已与配置节点一致

### 🟠 [HIGH] B-REVIEW-337：源码中文被替换为字面量 `?`

- **位置**：`src/xianyu_hunter/xxx.py` 第 X 行（扫描证据 `file:line`）
- **证据**：`grep -rPn '[\x{4e00}-\x{9fff}]\?{3,}|\?{3,}[\x{4e00}-\x{9fff}]' src scripts` 命中
- **问题**：源码文件本体中文被替换为连续 `?`，用户可见文案/注释/日志损坏，且可能已随 `HEAD` 提交污染历史
- **修复建议**：
  ```python
  # ✅ 还原正确的中文；py_compile 校验；全仓复扫 0 命中；必要时修正 HEAD 已提交版本
  self.set_status("登录已过期，请重新登录")
  ```
- **配置节点**：`coding_standards.source_file_encoding_integrity`
- **规范引用**：xianyu-hunter-dev step 280 / 前端 F-REVIEW-246 / 测试模式 AK
- **适用**：含中文的源码文件；跨工具保存后可疑 `?`
- **不适用**：运行时数据乱码（→ ENC/模式 K）；纯 ASCII 文件；SQL/正则中合法 `?`
