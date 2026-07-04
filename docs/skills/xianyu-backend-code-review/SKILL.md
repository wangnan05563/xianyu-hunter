---
name: xianyu-backend-code-review
description: "对闲鱼猎人项目后端代码（Python/FastAPI/SQLAlchemy）进行全面评审及逻辑审查，涵盖分层架构、异步并发、数据库规约、安全、性能、可维护性与最佳实践。调用时机：用户要求评审后端代码、审查 .py 文件修改、迭代发布前后端代码走查，或提到 '后端评审'、'backend review'、'Python 代码审查' 等关键词时。"
---

# xianyu-backend-code-review

> **范围**：`src/xianyu_hunter/**/*.py` + `tests/**/*.py`
> **技术栈**：Python 3.11 + FastAPI + SQLAlchemy 2.0 (async) + Pydantic v2 + Playwright + aiohttp + loguru
> **架构分层**：`domain` / `infra` / `modules` / `web`（routes + services + templates + static）
> **审查模式**：pending-change（审查未提交改动）/ file-focused（审查指定文件）/ snippet（审查粘贴代码）
> **配套技能**：[xianyu-hunter-dev](../xianyu-hunter-dev/SKILL.md) 提供编码规范来源

---

## When to use this skill

✅ 触发时机：
- 用户要求"评审后端代码" / "后端代码走查" / "code review 后端"
- 修改了 `src/xianyu_hunter/` 下任何文件后做发布前审查
- 新增 API 端点 / 业务模块 / 数据库表 / 配置加载
- 涉及异步、SQLAlchemy、外部 API 调用的修改

❌ 不适用：
- 前端代码（用 `xianyu-frontend-code-review`）
- 配置文件 / 文档（不在代码审查范围）
- 第三方依赖代码

---

## How to use this skill

按以下步骤执行审查：

1. **确定审查模式**（pending-change / file-focused / snippet）
2. **识别审查范围**（用 `git diff` 或用户指定的文件）
3. **按 §2 审查维度逐项检查**
4. **查阅 references/** 对应专题：
   - [references/architecture.md](references/architecture.md) —— 分层架构 / 依赖方向
   - [references/async-and-concurrency.md](references/async-and-concurrency.md) —— asyncio / 限流 / 并发
   - [references/sqlalchemy.md](references/sqlalchemy.md) —— ORM / Session / 事务
   - [references/security.md](references/security.md) —— 注入 / 认证 / 凭据
   - [references/performance.md](references/performance.md) —— N+1 / 缓存 / 阻塞
   - [references/maintainability.md](references/maintainability.md) —— 命名 / 注释 / 测试
   - [references/yaml-and-config.md](references/yaml-and-config.md) —— YAML 配置加载
   - [references/encoding-and-io.md](references/encoding-and-io.md) —— 字符编码 / I/O 边界 / 外部脚本调用 API（FAQ 乱码复盘）
   - [references/browser-subprocess-patterns.md](references/browser-subprocess-patterns.md) —— 浏览器自动化与子进程模式（登录模块复盘）
5. **按 §4 模板输出审查报告**

---

## §1 审查原则

| 原则 | 说明 |
|---|---|
| **业务正确性优先** | 架构 / 性能问题让位于业务 Bug |
| **改动局部化** | 评估影响范围，避免破坏性变更 |
| **审查可执行** | 每条 finding 必须能对应到一个修改动作 |
| **优先级分层** | Critical（必修）> Suggestion（应改）> Nit（可选） |
| **数据完整性** | 涉及写操作必须考虑事务 / 失败回滚 |

---

## §2 审查维度（8 个）

### 2.1 分层架构（Architecture）

| 编号 | 规则 | 严重度 |
|---|---|---|
| AR-01 | `domain/` 禁止 import `infra/` / `modules/` / `web/` | Critical |
| AR-02 | `infra/` 可 import `domain/`，但禁止 import `modules/` / `web/` | Critical |
| AR-03 | `modules/` 可 import `domain/` / `infra/`，禁止 import `web/` | Critical |
| AR-04 | `web/routes/` 编排业务，**禁止**直接操作数据库 / 浏览器 | Critical |
| AR-05 | 业务逻辑放 `modules/`，**禁止**写在路由函数中 | Critical |
| AR-06 | 仓储层命名 `repo_<实体>.py`，方法名 `list_xxx` / `get_xxx` / `upsert_xxx` | Suggestion |
| AR-07 | 仓储方法返回 dataclass / Pydantic 模型，**禁止**返回 ORM 对象 | Critical |
| AR-08 | 配置加载统一走 `infra/yaml_config.py`，**禁止**各模块独立读 YAML | Critical |
| AR-09 | 业务模块通过 `container.py` 获取依赖，**禁止**直接 `import` 跨模块实现 | Suggestion |

### 2.2 异步与并发（Async / Concurrency）

| 编号 | 规则 | 严重度 |
|---|---|---|
| AS-01 | I/O 必须 `async def` | Critical |
| AS-02 | **禁止**在 async 函数中调用 `requests.get` / `time.sleep` / `open().read()` | Critical |
| AS-03 | 异步 I/O 用 `aiohttp` / `httpx.AsyncClient` | Critical |
| AS-04 | 并发用 `asyncio.gather` / `asyncio.TaskGroup`（Python 3.11+） | Suggestion |
| AS-05 | 外部 API 调用必须有 `asyncio.Semaphore` 限流 | Suggestion |
| AS-06 | `await` 必须在 `async def` 内（不能裸 `await`） | Critical |
| AS-07 | 阻塞操作（CPU 密集）放 `asyncio.to_thread` / `ProcessPoolExecutor` | Suggestion |
| AS-08 | 长任务用后台 task + 状态汇报，不阻塞请求 | Suggestion |
| AS-09 | `for` 循环中串行 `await` 应改为 `gather`（如无依赖） | Suggestion |
| AS-10 | 资源清理用 `async with` / `try-finally` + 显式 close | Critical |

### 2.3 SQLAlchemy 与数据访问（SQLAlchemy）

| 编号 | 规则 | 严重度 |
|---|---|---|
| DB-01 | **禁止**在路由函数中直接 `session.execute(...)` | Critical |
| DB-02 | 数据库操作必须通过 `repo_*.py` 仓储层 | Critical |
| DB-03 | Session 用 `async with async_session() as session:` 上下文管理 | Critical |
| DB-04 | 写操作必须显式 `await session.commit()` | Critical |
| DB-05 | 异常时 `await session.rollback()` | Critical |
| DB-06 | 避免 N+1：用 `selectinload` / `joinedload` 预加载 | Critical |
| DB-07 | 频繁查询字段加索引（迁移文件中） | Suggestion |
| DB-08 | 模型定义放 `domain/`，**禁止**放在 `infra/` 或 `web/` | Suggestion |
| DB-09 | 复杂 SQL 写注释解释为什么（性能敏感） | Suggestion |
| DB-10 | **禁止**直接拼 SQL 字符串（参数化用 `text()` 或 ORM） | Critical |

### 2.4 安全（Security）

| 编号 | 规则 | 严重度 |
|---|---|---|
| SC-01 | **禁止**直接拼 SQL 字符串（防注入） | Critical |
| SC-02 | 用户输入**禁止**直接拼接 URL / 命令 / 文件路径（防 SSRF / 命令注入） | Critical |
| SC-03 | 敏感凭据（cookie / token）**禁止**写日志 / 硬编码 / 入库 | Critical |
| SC-04 | API 端点必须有认证（用 `Depends(get_current_user)`） | Critical |
| SC-05 | Web 路由返回前敏感字段必须 `_REDACT_KEYS` 脱敏 | Critical |
| SC-06 | 内部异常**禁止**直接返回给前端（含堆栈） | Critical |
| SC-07 | Pydantic 校验失败的错误信息不暴露内部字段名（可控） | Suggestion |
| SC-08 | 外部 API 响应先校验再使用 | Critical |
| SC-09 | 文件路径用 `Path`，**禁止** `os.path.join` 后直接 open（防路径穿越） | Critical |
| SC-10 | 关键操作（删除 / 转账）需二次确认（业务层） | Suggestion |

### 2.5 性能（Performance）

| 编号 | 规则 | 严重度 |
|---|---|---|
| PF-01 | 避免 N+1 查询（用 `selectinload`） | Critical |
| PF-02 | 大列表分页（`offset` + `limit`） | Suggestion |
| PF-03 | 热数据加缓存（`@lru_cache` / 显式 cache） | Suggestion |
| PF-04 | **禁止**在 async 循环中 `await asyncio.sleep(0)` 让步 | Nit |
| PF-05 | 长循环内**禁止**每条记录都查 DB（应 `IN (...)` 批量查） | Critical |
| PF-06 | 锁 / 资源竞争用 `asyncio.Lock` 而不是 `threading.Lock` | Critical |
| PF-07 | 启动期初始化用 `lifespan` 上下文，不在路由内 lazy init | Suggestion |
| PF-08 | Pydantic 模型用 `model_dump()` 比手写 dict 快 | Nit |
| PF-09 | 频繁创建的资源（aiohttp session）用单例 / 池 | Suggestion |
| PF-10 | loguru logger 用 `{}` 占位符（避免无参数格式化） | Nit |

### 2.6 可维护性（Maintainability）

| 编号 | 规则 | 严重度 |
|---|---|---|
| MN-01 | 函数长度 ≤ 50 行（过长需拆分） | Suggestion |
| MN-02 | 函数参数 ≤ 4 个（多则用 dataclass） | Suggestion |
| MN-03 | 类 / 函数职责单一（SRP） | Suggestion |
| MN-04 | 命名 `snake_case`（函数 / 变量）/ `PascalCase`（类） | Suggestion |
| MN-05 | 注释解释 **why**（不解释 what） | Suggestion |
| MN-06 | 公开函数 / 类有 docstring | Nit |
| MN-07 | magic number 提取为常量 / 配置 | Suggestion |
| MN-08 | **禁止**硬编码路径 / URL / 凭据 | Critical |
| MN-09 | **禁止**捕获所有异常 `except Exception` 后吞 | Critical |
| MN-10 | 关键路径必须 `logger.info` 记录 | Suggestion |
| MN-11 | 测试覆盖正常 + 边界 + 异常 | Suggestion |

### 2.7 YAML / 配置（Config）

| 编号 | 规则 | 严重度 |
|---|---|---|
| CFG-01 | 多层 YAML 配置必须 **深度合并**（不能用 `dict.update`） | Critical |
| CFG-02 | 加载顺序：子配置先（默认基线），主配置后（用户修改覆盖） | Critical |
| CFG-03 | 配置加载后必须 `AppConfig.model_validate(...)` 校验 | Critical |
| CFG-04 | 校验失败抛 `ValidationError`，HTTP 端点转为 400 | Critical |
| CFG-05 | 配置修改后必须 `reload_config()` 刷新单例 | Critical |
| CFG-06 | 敏感字段（cookie / token）不写 YAML，走 `.env` / keyring | Critical |
| CFG-07 | 新增配置字段**必须**同步更新 `*.example.yaml` 模板 | Suggestion |
| CFG-08 | YAML 时间字符串必须引号（`"07:00"` 不被解析为整数） | Critical |
| CFG-09 | Pydantic `extra` 策略：默认 `ignore`，**禁止** 用 `allow` | Suggestion |
| CFG-10 | 业务约束（如 `pass_score <= auto_buy_score`）用 `@model_validator` | Suggestion |

### 2.8 编码与 I/O（Encoding & I/O）

> **复盘来源**：FAQ 乱码问题（数据库存储 ASCII 0x3f）。详见 [references/encoding-and-io.md](references/encoding-and-io.md)。

| 编号 | 规则 | 严重度 |
|---|---|---|
| ENC-01 | 所有 `open()` / `Path.read_text()` / `Path.write_text()` 显式 `encoding="utf-8"` | Critical |
| ENC-02 | SQLite 不显式 `PRAGMA encoding`（默认 UTF-8）；MySQL/PG 连接串带 `charset=utf8mb4` | Critical |
| ENC-03 | 自定义 `Response` 显式 `media_type="application/json; charset=utf-8"` | Suggestion |
| ENC-04 | 写入文本字段前校验非 ASCII 字符不为 `?`（0x3f），防编码损坏 | Critical |
| ENC-05 | 临时调试脚本 `_debug_*.py` 用完即删，禁止提交 | Critical |
| ENC-06 | 编码参数（database / file_io / http_response）走 YAML 配置，禁止硬编码 | Suggestion |
| ENC-07 | 诊断字符乱码用 `conn.text_factory = bytes` 读原始字节，绕过 stdout 编码 | Suggestion |
| ENC-08 | 审计日志记录 source / UA / IP / 毫秒级时间戳，支持写入源追溯 | Suggestion |

### 2.9 统计查询验证（Statistics Query）

> **复盘来源**：仪表盘 KPI 始终显示 0% 问题（查询-写入取值不对齐 + 数据采集缺失）。详见 [xianyu-hunter-dev references/coding-standards.md §2.10](../xianyu-hunter-dev/references/coding-standards.md)。

| 编号 | 规则 | 严重度 |
|---|---|---|
| STQ-01 | 统计查询的筛选条件必须与写入端实际取值**完全匹配**（搜索所有写入位置确认） | Critical |
| STQ-02 | 查询条件中的状态值引用枚举类（如 `OrderStatus.SUCCEEDED.value`），**禁止**硬编码魔法字符串 | Critical |
| STQ-03 | 分母的统计范围必须与分子**同类**（分子查 notify 事件 → 分母也必须是 notify 事件总数） | Critical |
| STQ-04 | 返回前端的 hint 文案必须与实际计算公式的分子分母语义**一致** | Suggestion |
| STQ-05 | 统计指标依赖某表数据时，必须确认该表有**写入代码**；数据产生点必须写入对应记录 | Critical |
| STQ-06 | 统计字段（stage / level / status）取值必须**全代码库统一** | Critical |
| STQ-07 | 统计指标分母为 0 时必须记录 **WARNING 日志**，含可能原因提示 | Suggestion |
| STQ-08 | 新增构造函数属性时用 `getattr(self, '_x', None)` 兼容测试中 `__new__` 跳过构造的场景 | Suggestion |

**审查方法**：查询-写入对齐法

```
1. 找到查询端代码（如 business_kpi.py 中的查询条件）
2. 用 Grep 搜索所有写入端代码位置
3. 对比查询条件与写入值是否匹配
4. 如不匹配 → 标记为 STQ-01 Critical
```

**适用场景**：仪表盘 KPI / 报表统计 / 数据看板 / 任何涉及 COUNT/SUM 聚合查询的场景。
**不适用场景**：纯前端展示问题 / 数据丢失问题 / 查询性能问题。

### 2.10 浏览器自动化与子进程（Browser Automation & Child Process）

> **复盘来源**：登录模块 11 类问题（多 Chromium 争用 user_data_dir / Cookie 异步写入 / 跨域 Cookie / SPA 抓取 / 子进程异常静默 / 资源拦截过度）。详见 [references/browser-subprocess-patterns.md](references/browser-subprocess-patterns.md)。

| 编号 | 规则 | 严重度 |
|---|---|---|
| BAC-01 | `launch_persistent_context` 前必须调用 `_cleanup_lock_files` 清理 `SingletonLock` / `SingletonCookie` / `SingletonSocket` + Sessions 历史标签 | Critical |
| BAC-02 | 共享 `user_data_dir` 的 Manager 类必须含 `_refresh_lock` + `_refreshing` 互斥标志，防止多个 Chromium 并发 | Critical |
| BAC-03 | 登录路径触发 auth_helper 时必须传 `delay`（从 `auth.helper_delay_sec` 读取，默认 5.0），让 browser_login 的 Chromium 先退出 | Critical |
| BAC-04 | 禁止关闭 context 中唯一 page 后 `new_page()`（会触发 `Target.createTarget: Failed to open a new tab`），必须复用 `pages[0]` | Critical |
| BAC-05 | 异步写入操作（Cookie、SQLite、storage_state）完成后必须显式等待 `auth.cookie_write_wait_sec`（默认 3.0s）再读取 | Critical |
| BAC-06 | 读 Cookie 前必须调用 `await bc.storage_state()` 强制 flush 到 SQLite | Critical |
| BAC-07 | `bc.close()` 后必须等待 `auth.sqlite_flush_wait_sec`（默认 2.0s）让 SQLite 写入完成 | Critical |
| BAC-08 | Cookie 域过滤必须包含所有相关域（`browser.auth_cookie_domains`，默认 goofish + taobao），禁止仅按单一域过滤 | Critical |
| BAC-09 | 登录态判定以关键 Cookie（`auth.login_cookie_names`，默认 unb/_tb_token_/cookie2）为准，禁止用 `_m_h5_tk` 等访问首页就设置的 Cookie | Critical |
| BAC-10 | Cookie 值必须严格校验：`unb.isdigit() and len(unb) >= auth.unb_min_length`，过滤 `auth.unb_test_values`（默认 ["123456", "123"]） | Critical |
| BAC-11 | 从 DOM 抓取的业务文本（昵称/用户名）必须过滤 `auth.invalid_nicks` 占位符集合 + 二次重试（`wait_for_selector` + 固定 sleep 兜底） | Critical |
| BAC-12 | subprocess 调用必须 `capture_output=True` + 失败时 `logger.warning` + 记录 stderr 前 500 字符 + 超时单独处理，禁止 `except Exception: pass` | Critical |
| BAC-13 | Playwright `route` 拦截策略必须：不拦截 stylesheet + 域名白名单放行（`browser.resource_allow_domains`）+ 拦截类型走配置（`browser.resource_block_types`） | Critical |
| BAC-14 | 所有可变参数（等待时间 / Cookie 域 / 占位符集合 / 选择器 / 拦截类型）必须通过 YAML 配置管理，禁止硬编码 | Critical |

**审查方法**：进程互斥 + 异步时序 + Cookie 域 + 配置化 4 维度交叉验证

```
1. 检查 launch_persistent_context 前是否有 _cleanup_lock_files 调用
2. 检查 Manager 类是否有 _refresh_lock + _refreshing 互斥
3. 检查登录路径触发 auth_helper 是否传 delay（从配置读取）
4. 检查是否复用 pages[0] 而非 close + new_page
5. 检查异步写入后是否有 sleep + storage_state + sleep
6. 检查 Cookie 域过滤是否包含 goofish + taobao（从配置读取）
7. 检查登录态判定是否校验 unb 值（isdigit + len）
8. 检查占位符过滤是否从配置读取 + 是否有二次重试
9. 检查 subprocess 是否 capture_output + logger.warning + 超时单独处理
10. 检查 route 拦截是否不含 stylesheet + 域名白名单从配置读取
11. 检查所有等待时间 / 域名 / 选择器是否从配置读取
```

**适用场景**：Playwright 浏览器自动化、共享 user_data_dir 架构、subprocess 调用外部脚本、跨域 Cookie 处理、SPA 数据抓取。
**不适用场景**：纯 HTTP API 调用、静态页面爬取、单进程同步流程、桌面应用。

---

## §3 项目特定审查要点

### 3.1 配置管理（`infra/yaml_config.py` + `web/routes/api_config.py`）

| 编号 | 规则 |
|---|---|
| BCFG-01 | 加载顺序正确（子配置先于主配置） |
| BCFG-02 | 使用 `_deep_merge_yaml` 而非 `dict.update` |
| BCFG-03 | 保存端也用深度合并（与加载端保持一致） |
| BCFG-04 | 校验失败返回 `detail.message` + `detail.errors` |
| BCFG-05 | `reload_config()` 在保存成功后调用 |
| BCFG-06 | 敏感字段 `_REDACT_KEYS` 列表完整 |
| BCFG-07 | `*.example.yaml` 与 `*.yaml` 同步 |

### 3.2 抢单决策链（`modules/buyer.py` + `evaluator.py` + `worker.py`）

| 编号 | 规则 |
|---|---|
| BBUY-01 | 每次决策实时从 `get_config()` 读，不缓存 |
| BBUY-02 | 任务模式（auto / confirm / notify）正确解析 |
| BBUY-03 | 分数判断逻辑与 `EvalConfig` 约束一致 |
| BBUY-04 | 失败任务有重试 + 降级（不直接抛错） |
| BBUY-05 | 并发抢单有锁 / 信号量（防重复） |

### 3.3 浏览器自动化（`infra/browser.py`）

| 编号 | 规则 |
|---|---|
| BBR-01 | Playwright session 单例（不要每请求创建） |
| BBR-02 | 关闭资源用 `try-finally` |
| BBR-03 | 反爬策略（QPS / UA / 指纹）走配置 |
| BBR-04 | 登录态失效有检测 + 重登录流程 |

### 3.4 API 端点（`web/routes/api_*.py`）

| 编号 | 规则 |
|---|---|
| BAPI-01 | 路由函数不写业务逻辑（调用 service） |
| BAPI-02 | 认证依赖 `Depends(get_current_user)` |
| BAPI-03 | 错误用 `HTTPException(status_code, detail)` |
| BAPI-04 | 复杂参数用 Pydantic `BaseModel`（不直接 dict） |
| BAPI-05 | 响应模型显式 `response_model=...` |
| BAPI-06 | 限流（重要端点） |

### 3.5 仪表盘 KPI 查询（`web/routes/business_kpi.py` + `stats_*.py`）

| 编号 | 规则 |
|---|---|
| BKPI-01 | 查询条件中的状态值与写入端实际取值对齐（STQ-01） |
| BKPI-02 | 分子分母统计范围同类（STQ-03） |
| BKPI-03 | hint 文案与实际计算公式一致（STQ-04） |
| BKPI-04 | 统计依赖的表有写入代码（STQ-05） |
| BKPI-05 | 分母为 0 时有 WARNING 告警（STQ-07） |
| BKPI-06 | 多个统计端点（business_kpi / stats_overview / stats_eval_funnel）对同一字段取值定义一致 |

### 3.6 登录模块（`scripts/browser_login.py` + `scripts/auth_helper.py` + `web/services/auth_manager.py`）

> **复盘来源**：登录模块 11 类问题。详见 [references/browser-subprocess-patterns.md](references/browser-subprocess-patterns.md)。

| 编号 | 规则 |
|---|---|
| BLOGIN-01 | `browser_login.py` 启动前必须 `_cleanup_lock_files`（含 SingletonLock + Sessions/Tabs_* / Session_*）（对应 BAC-01） |
| BLOGIN-02 | `browser_login.py` 复用 `pages[0]`，禁止 `close() + new_page()`（对应 BAC-04） |
| BLOGIN-03 | `browser_login.py` 资源拦截不含 stylesheet + 域名白名单从配置读取（对应 BAC-13） |
| BLOGIN-04 | `browser_login.py` 登录成功后 `sleep(cookie_write_wait_sec) + storage_state() + sleep(sqlite_flush_wait_sec)`（对应 BAC-05/06/07） |
| BLOGIN-05 | `browser_login.py` 严格校验 Cookie 值（unb.isdigit + len >= unb_min_length + 过滤 unb_test_values）（对应 BAC-10） |
| BLOGIN-06 | `auth_helper.py` 启动前必须 `_cleanup_lock_files`（对应 BAC-01） |
| BLOGIN-07 | `auth_helper.py` Cookie 域过滤含 goofish + taobao（从 `browser.auth_cookie_domains` 读取）（对应 BAC-08） |
| BLOGIN-08 | `auth_helper.py` 占位符过滤从 `auth.invalid_nicks` 读取 + 二次重试（`wait_for_selector` + sleep 兜底）（对应 BAC-11） |
| BLOGIN-09 | `auth_helper.py` unb 兜底重读（`auth.unb_reread_wait_sec`）（对应 BAC-05） |
| BLOGIN-10 | `auth_manager.py` 含 `_refresh_lock` + `_refreshing` 互斥标志（对应 BAC-02） |
| BLOGIN-11 | `auth_manager.py` 登录路径触发 auth_helper 传 `delay=auth.helper_delay_sec`（对应 BAC-03） |
| BLOGIN-12 | `auth_manager.py` 子进程失败时 `logger.warning` + 记录 stderr 前 500 字符（对应 BAC-12） |
| BLOGIN-13 | `auth_manager.py` 超时单独处理 `subprocess.TimeoutExpired`（对应 BAC-12） |
| BLOGIN-14 | `unified_login.py` / `cookie_inject.py` 路由层传递 `user_id` 给 `issue_session`，不回退 web_token |
| BLOGIN-15 | 所有等待时间 / 域名 / 选择器 / 占位符从 `config/auth.yaml` + `config/browser.yaml` 读取（对应 BAC-14） |

---

## §4 输出模板

### 4.1 有问题（Template A）

```markdown
# Backend Code Review

Found <X> critical issues need to be fixed:

## 🔴 Critical (Must Fix)

### 1. <brief description>

**FilePath**: <path> line <line>
<相关代码片段或指针>

**问题**：
- 具体违反的规则编号（如 AR-01 / DB-01 / CFG-01）
- 影响范围（哪些场景会触发 / 风险等级）

**Suggested Fix**：
1. <具体修改步骤>
2. <代码示例（可选）>

---

... (重复每个 critical issue) ...

Found <Y> suggestions for improvement:

## 🟡 Suggestions (Should Consider)

### 1. <brief description>

**FilePath**: <path> line <line>
<相关代码片段或指针>

**Suggested Fix**：
1. ...

---

Found <Z> optional nits:

## 🟢 Nits (Optional)

### 1. <brief description>

**FilePath**: <path> line <line>

**Suggested Fix**：
- <minor suggestions>

---

## ✅ What's Good

- <值得肯定的实现>
```

### 4.2 无问题（Template B）

```markdown
# Backend Code Review

✅ No issues found. 当前实现符合本项目后端编码规范。
```

### 4.3 输出规则

- **优先按严重度排序**：Critical → Suggestion → Nit
- **同类问题聚合**：如多个路由都有同类问题，合并为一个 finding
- **每条 finding 包含**：规则编号 + 路径 + 行号 + 修复建议
- **超过 10 条同类问题**："Found 10+ <category> issues, only showing first 10"
- **末尾必须询问**："需要我直接应用这些修复吗？"

---

## §5 审查流程（详细）

### Step 1: 收集变更

```bash
# pending-change 模式
git diff src/xianyu_hunter/

# file-focused 模式
# 用户直接指定文件路径
```

### Step 2: 分类标记

按 `§2` 维度分类：
- 分层架构（AR-*）
- 异步并发（AS-*）
- SQLAlchemy（DB-*）
- 安全（SC-*）
- 性能（PF-*）
- 可维护性（MN-*）
- 配置（CFG-*）
- 编码与 I/O（ENC-*）
- 统计查询（STQ-*）
- 浏览器自动化与子进程（BAC-*）

### Step 3: 逐项检查

每条规则对照代码，按 Critical / Suggestion / Nit 分级。

### Step 4: 聚合输出

按模板输出，**每条 finding 至少包含**：
- 规则编号（便于追溯到 §2 规则表）
- 文件路径 + 行号
- 影响说明
- 修复建议（具体可执行）

### Step 5: 应用修复（可选）

如用户确认修复，按"先 Critical 后 Suggestion"顺序批量修改。

---

## §6 不审查什么

- ❌ 第三方库 / 框架内部代码
- ❌ 拼写 / 格式（用 ruff / black / isort 处理）
- ❌ 文档 / 注释内容
- ❌ 测试代码（除非影响主逻辑）

---

## §7 常用检查脚本

```bash
# 类型检查
mypy src/xianyu_hunter/

# Lint
ruff check src/xianyu_hunter/

# 格式化检查
black --check src/xianyu_hunter/

# 导入排序
isort --check src/xianyu_hunter/

# 安全检查
bandit -r src/xianyu_hunter/

# 单元测试
pytest tests/ -v
```

---

## §8 复盘：从对话中提炼的关键模式

### 8.1 反模式 1：浅合并多层 YAML 配置

**复盘案例**：抢单策略页面参数保存后刷新重置为默认值

**反模式代码**：
```python
# ❌ 浅合并 + 后加载整体覆盖
data.update(load_yaml("config/config.yaml"))  # 先加载主配置
for name in ("notifier.yaml", "eval.yaml", ...):
    data.update(section_data)  # 后加载 eval.yaml 整体覆盖 config.yaml 的 eval 块
```

**正确模式**：
```python
# ✅ 深度合并 + 主配置后加载
def _load_all() -> AppConfig:
    base = Path("config")
    data: dict[str, Any] = {}
    # 1) 子配置先加载（默认基线）
    for name in ("eval.yaml", "notifier.yaml", "browser.yaml"):
        section_data = load_yaml(base / name)
        if section_data:
            _deep_merge_yaml(data, section_data)
    # 2) 主配置后加载（用户修改覆盖）
    main_data = load_yaml(base / "config.yaml")
    if main_data:
        _deep_merge_yaml(data, main_data)
    return AppConfig.model_validate(data)


def _deep_merge_yaml(target: dict, source: dict) -> None:
    for k, v in source.items():
        if isinstance(v, dict) and isinstance(target.get(k), dict):
            _deep_merge_yaml(target[k], v)
        else:
            target[k] = v
```

**预防机制**：审查时必查 `dict.update(yaml_data)` / `data.update(load_yaml(...))` 这类浅合并。

### 8.2 反模式 2：路由函数中直接操作数据库

**反模式代码**：
```python
# ❌ 路由直接 ORM
@router.get("/items")
async def list_items():
    async with async_session() as session:
        result = await session.execute(select(Item))
        return result.scalars().all()
```

**正确模式**：
```python
# ✅ 路由只编排，业务在模块
@router.get("/items")
async def list_items():
    return await item_service.list_items()

# modules/items/service.py
async def list_items() -> list[ItemDTO]:
    repo = ItemRepository()
    return await repo.list_all()
```

### 8.3 反模式 3：async 中阻塞

**反模式代码**：
```python
# ❌ async 中调阻塞
async def fetch_data():
    resp = requests.get(url)  # 阻塞 event loop
    return resp.json()
```

**正确模式**：
```python
# ✅ 用 aiohttp
async def fetch_data():
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return await resp.json()

# ✅ 或 to_thread 包同步
async def fetch_data():
    return await asyncio.to_thread(requests.get, url)
```

### 8.4 反模式 4：异常信息吞错

**反模式代码**：
```python
# ❌ 吞错
try:
    await api.save()
except Exception:
    pass
```

**正确模式**：
```python
# ✅ 记录 + 上抛
try:
    await api.save()
except Exception as e:
    logger.exception("保存失败")
    raise HTTPException(500, detail="保存失败")
```

### 8.5 反模式 5：统计查询与写入端取值不对齐

**复盘案例**：仪表盘"抢单成功率"始终显示 0%

**反模式代码**：
```python
# ❌ 查询端凭空设计查询条件，未对照写入端实际取值
cur_paid, cur_total = repo.db_count_by_predicate(
    OrderRow, cur_start, now,
    extra_where=[OrderRow.status.in_(["paid", "confirmed"])],  # 写入端从未写入这两个值！
)
```

**正确模式**：
```python
# ✅ 搜索所有写入位置，确认实际取值后对齐查询条件
# buyer.py 写入 'pending_pay'，api_orders.py 写入 'succeeded'
cur_paid, cur_total = repo.db_count_by_predicate(
    OrderRow, cur_start, now,
    extra_where=[OrderRow.status == "succeeded"],  # 与 stats_overview.py 统计口径一致
)
if cur_total == 0:
    logger.warning(f"[business_kpi] 抢单成功率分母为 0：近 {range_days} 天无订单记录")
```

**预防机制**：审查统计查询时，用 Grep 搜索所有写入端代码位置，确认查询条件与实际写入取值完全匹配。

### 8.6 反模式 6：数据采集环节缺失

**复盘案例**：仪表盘"推送失败率"始终显示 0%

**反模式代码**：
```python
# ❌ 查询端期望 stage='notify' 的事件，但推送流程从不写入 EventRow
cur_fail, cur_total = repo.db_count_by_predicate(
    EventRow, cur_start, now,
    extra_where=[EventRow.stage.like("%notify%"), EventRow.level == "err"],
)  # 永远命中 0 行，因为 NotifierHub.send() 只写 logger.info，不写 EventRow
```

**正确模式**：
```python
# ✅ 在数据产生点（NotifierHub.send）补齐写入逻辑
if repo is not None:
    try:
        repo.save_event({
            "stage": "notify",
            "level": "err" if any_failed else "info",
            "message": f"{event.type.value} → {ok}/{len(results)} 渠道成功",
            ...
        })
    except Exception as log_err:
        logger.warning(f"写入 notify 事件失败: {log_err}")
```

**预防机制**：新增统计指标时，必须确认数据源有写入代码；数据产生点必须写入对应记录。

### 8.7 反模式 7：多 Chromium 争用 user_data_dir

**复盘案例**：登录后右上角显示"未登录"（6 次迭代才解决）

**反模式代码**：
```python
# ❌ 不清理锁文件 + 不互斥 + 不延迟触发
class AuthManager:
    def trigger_refresh_userinfo_async(self):
        # ❌ 缺少 _refresh_lock 检查
        threading.Thread(target=self._refresh_userinfo_sync).start()

# ❌ browser_login.py 不清理 SingletonLock
async with async_playwright() as pw:
    ctx = await pw.chromium.launch_persistent_context(
        user_data_dir=str(user_data_dir),  # ❌ 残留锁文件
    )
```

**问题**：
- Worker 异常退出后 SingletonLock 残留 → `Target.createTarget: Failed to open a new tab`
- auth_helper 与 browser_login 并发争用同一 user_data_dir → SQLite Cookie 数据库锁冲突
- Cookie 18 个而非 38 个，缺关键 unb → user_id 降级 → 显示"未登录"
- 立即触发 auth_helper，browser_login 的 Chromium 退出未完成

**正确模式**：
```python
# ✅ 清理锁文件 + 互斥 + 延迟触发
def _cleanup_lock_files(user_data_dir: Path) -> None:
    for pattern in (
        str(user_data_dir / "SingletonLock"),
        str(user_data_dir / "SingletonCookie"),
        str(user_data_dir / "SingletonSocket"),
        str(user_data_dir / "*lock*"),
        str(user_data_dir / "Default" / "Sessions" / "Tabs_*"),
        str(user_data_dir / "Default" / "Sessions" / "Session_*"),
    ):
        for f in _glob.glob(pattern):
            try:
                Path(f).unlink(missing_ok=True)
            except OSError:
                pass

class AuthManager:
    def __init__(self) -> None:
        self._refresh_lock = threading.Lock()
        self._refreshing = False

    def trigger_refresh_userinfo_async(self, delay: float | None = None):
        auth_cfg = _get_auth_cfg()
        if delay is None:
            delay = auth_cfg.helper_delay_sec  # ✅ 5.0s 从配置读取

    def _refresh_userinfo_sync_with_delay(self, delay: float = 0.0):
        with self._refresh_lock:
            if self._refreshing:
                return
            self._refreshing = True
        try:
            self._refresh_userinfo_sync()
        finally:
            with self._refresh_lock:
                self._refreshing = False

# 启动前清理
_cleanup_lock_files(Path(cfg.user_data_dir))
```

**预防机制**：审查所有共享 user_data_dir 的 Chromium 启动代码，必须确认有 `_cleanup_lock_files` + `_refresh_lock` + `delay`。

### 8.8 反模式 8：静默吞子进程异常

**复盘案例**：auth_helper 启动失败时前端显示"未登录"且无日志可查

**反模式代码**：
```python
# ❌ 静默吞异常
def _refresh_userinfo_sync(self) -> None:
    try:
        proc = subprocess.run(
            [sys.executable, str(_HELPER), "info", "--out-dir", str(_OUT_DIR)],
            timeout=60,
            capture_output=True,
        )
        if proc.returncode == 0 and _USERINFO_FILE.exists():
            self._userinfo = json.loads(_USERINFO_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass  # ❌ 静默吞，_userinfo 保持旧值（nick=""）
```

**问题**：
- auth_helper 启动失败（如 ImportError / SingletonLock 冲突）时，`_userinfo` 保持旧值
- 旧值的 `nick=""` → 前端显示"未登录"
- 没有日志，无法排查
- `except Exception: pass` 是反模式，违反 MN-09

**正确模式**：
```python
# ✅ 捕获 stderr + logger.warning + 超时单独处理
def _refresh_userinfo_sync(self) -> None:
    try:
        proc = subprocess.run(
            [sys.executable, str(_HELPER), "info", "--out-dir", str(_OUT_DIR)],
            timeout=_get_auth_cfg().helper_timeout_sec,  # ✅ 从配置读取
            capture_output=True,
        )
        if proc.returncode == 0 and _USERINFO_FILE.exists():
            with self._lock:
                self._userinfo = json.loads(_USERINFO_FILE.read_text(encoding="utf-8"))
                self._userinfo_at = time.time()
        elif proc.returncode != 0:
            # ✅ 记录 stderr 前 500 字符
            stderr = proc.stderr.decode(errors="replace")[:500] if proc.stderr else ""
            logger.warning("auth_helper info 失败 (returncode=%d): %s", proc.returncode, stderr)
    except subprocess.TimeoutExpired:
        # ✅ 超时单独处理
        logger.warning("auth_helper info 超时（%ds）", _get_auth_cfg().helper_timeout_sec)
    except Exception as e:
        # ✅ 其他异常用 warning 而非 debug
        logger.warning("auth_helper info 异常: %s", e)
```

**预防机制**：审查所有 `subprocess.run` / `subprocess.Popen` 调用，必须确认有 `capture_output=True` + `logger.warning` + 超时单独处理，禁止 `except Exception: pass`。

---

## §9 与其他技能协同

```
用户请求后端代码评审
    ↓
xianyu-backend-code-review（本技能）
    │
    ├── 编码规范依据 ──→ docs/skills/xianyu-hunter-dev/references/coding-standards.md
    │                  + docs/skills/xianyu-hunter-dev/references/browser-automation-and-async-patterns.md
    │
    ├── 分层架构 ──→ references/architecture.md
    │
    ├── 异步并发 ──→ references/async-and-concurrency.md
    │
    ├── SQLAlchemy ──→ references/sqlalchemy.md
    │
    ├── 安全 ──→ references/security.md
    │
    ├── 性能 ──→ references/performance.md
    │
    ├── 可维护性 ──→ references/maintainability.md
    │
    ├── 配置加载 ──→ references/yaml-and-config.md
    │
    ├── 编码与 I/O ──→ references/encoding-and-io.md
    │
    └── 浏览器自动化与子进程 ──→ references/browser-subprocess-patterns.md
```

---

## References

- [references/architecture.md](references/architecture.md)
- [references/async-and-concurrency.md](references/async-and-concurrency.md)
- [references/sqlalchemy.md](references/sqlalchemy.md)
- [references/encoding-and-io.md](references/encoding-and-io.md) —— 字符编码 / I/O 边界（FAQ 乱码复盘）
- [references/security.md](references/security.md)
- [references/performance.md](references/performance.md)
- [references/maintainability.md](references/maintainability.md)
- [references/yaml-and-config.md](references/yaml-and-config.md)
- [references/browser-subprocess-patterns.md](references/browser-subprocess-patterns.md) —— 浏览器自动化与子进程模式（登录模块复盘，BAC-01~14 检查点）
