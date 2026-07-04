# 闲鱼猎人编码规范复盘（v1）

> **版本**：v1.0
> **日期**：2026-06-28
> **来源**：从"Cookie 层状态管理与功能可用性矛盾"问题 + 代码变更逻辑审查复盘
> **复盘方法**：Sequential Thinking 4 维度（成功步骤 / 失败点 / 可抽象流程 / 适用与不适用场景）
> **适用范围**：`src/xianyu_hunter/`（Python）+ `frontend/src/`（TypeScript）
> **配套技能**：`xianyu-hunter-dev`（增量开发）、`xianyu-frontend-code-review`、`xianyu-backend-code-review`

---

## 一、问题原型

**用户报告**：

> 当前系统中，实时查询、官方采集等功能均能正常运行，这表明基础 cookie 机制是有效的。然而，系统持续显示 identity、session、tracking 状态失效。

**矛盾本质**：状态判定只看 cookie 命中数，不看实际功能可用性。当 cookie 写入子进程缓存、或 cookie 内容部分缺失时，状态被误判为失效。

**修复后扩展**：
- 排查过程中发现 2 个 Critical 缺陷（迁移函数事务原子性缺失、collector 误判）
- 5 个建议改进（死代码、时间戳、防御性 else）
- 涉及 3 个核心文件：`db_models.py`、`cookie_rotator.py`、`api_anticrawl.py`

---

## 二、成功执行任务的完整步骤

| 阶段 | 动作 | 产出 |
|---|---|---|
| 1. 现象分析 | 区分"功能可用"与"状态显示"两个独立维度 | 发现状态判定盲区 |
| 2. 依赖层建模 | 引入 `depends_on` 字段表达 SESSION 依赖 IDENTITY | `LAYER_DEFINITIONS` 增强 |
| 3. 缓存失效传播 | `CookieStore` 增加 `invalidate_cache()` 入口 | 跨进程一致性保证 |
| 4. 功能信号兜底 | 引入 `force_restore_layers` + `/cookies/layers` 第三步 | 状态自愈能力 |
| 5. Schema 演进 | 新增通用 `_migrate_make_column_nullable` 表重建函数 | ORM 变更可追溯 |
| 6. 测试驱动 | 编写 41 项专项测试覆盖层状态同步、依赖验证、强制恢复 | 998 项全量通过 |

**关键决策**：
- **不破坏现有 API 契约**：`force_restore_layers` 是新方法，不影响 `sync_state_from_cookies` 调用方
- **保留用户控制权**：`manual_invalidate=True` 永远不被自动恢复覆盖
- **配置化兜底策略**：信号1/2 恢复层范围由配置决定（collector 恢复全层，m5tk 恢复 SESSION）

---

## 三、任务执行过程中的不确定性与失败点

### 3.1 不确定性

| 类别 | 描述 | 处理 |
|---|---|---|
| 缓存粒度 | CookieStore TTL 设 30s 是否足够 | 改为按需主动 `invalidate_cache()`，不再依赖 TTL |
| 兜底触发条件 | collector `last_session_invalid=False` 是否可信 | 增加 `has_searched` 前置条件 |
| 依赖层方向 | SESSION 依赖 IDENTITY 是否唯一 | 数据驱动建模，后续可扩展更多层 |
| 表重建影响 | 重建 tasks 表是否会丢数据 | 列名交集复制 + 异常回滚到 `_old` |

### 3.2 失败点

| # | 失败现象 | 根因 | 修复 |
|---|---|---|---|
| F-1 | 浏览器登录成功后 3 个层仍显示失效 | 浏览器子进程只更新自己缓存，未通知主进程 | 调用 `invalidate_cache()` 后再 `sync_state_from_cookies` |
| F-2 | `test_update_mixed_test_and_real_cookies` 反复失败 | 测试预期未考虑 `is_test_cookie` 过滤逻辑 | 更新测试预期与实现对齐 |
| F-3 | 完整测试套件中 2 个 cron 持久化测试偶发失败 | 全局 `data/xianyu.db` 的 `eval_threshold` 列是旧 NOT NULL schema | 新增 `_migrate_make_column_nullable` 表重建迁移 |
| F-4 | Critical #1：迁移函数分 3 个独立 commit | 步骤 2/3 失败时旧表已 RENAME 但新表未创建完成 | 用 `engine.begin()` 单事务包裹 |
| F-5 | Critical #2：collector 刚启动时误判 | `last_session_invalid` 初始值 False 与"未检测"语义混淆 | 增加 `has_searched` 前置（`_last_m5tk_refresh > 0`） |
| F-6 | Suggestion #1：死代码 `identity_valid` 未使用 | 重构时遗留 | 删除并分两轮处理消除顺序依赖 |
| F-7 | Suggestion #2：`updated_at` 不更新 | 强制恢复路径漏改 | 总是 `state.updated_at = time.time()` |
| F-8 | 临时文件残留 | 调试脚本未及时清理 | 任务收尾时主动 `Glob` 清理 |

---

## 四、可抽象的固定流程与判断逻辑

### 流程 A：缓存失效传播（跨进程/跨模块一致性）

**触发场景**：模块 A 的状态变更需要被模块 B 感知；子进程写入需要主进程感知；JSON 持久化需要被内存缓存感知。

**固定步骤**：
1. **识别共享状态**：明确哪些字段是"输入"、哪些是"派生"、哪些是"持久化副本"
2. **设计 invalidate 入口**：每个缓存对象暴露 `invalidate_cache()` 或等价方法
3. **写入主路径后必调**：所有写主数据源的方法在写后**显式**调用同步钩子
4. **失败降级**：同步钩子失败仅 `logger.warning`，不抛异常阻塞主流程

**判断逻辑**：
```
写入主数据源
  ├─ 同步更新内存缓存（如有）
  ├─ 调用 invalidate_cache() 通知其他持有者
  └─ 异常仅记录不抛出
```

**反模式**：
- 依赖 TTL 自动失效（粒度粗、跨进程不可靠）
- 用回调函数（不可观测、难调试）
- 在 setter 内隐式调用（违反"精确编辑"原则）

### 流程 B：状态判定兜底（多信号融合）

**触发场景**：核心状态字段（cookie 有效/连接正常/服务可用）由多源数据派生，源数据可能短暂缺失或不一致。

**固定步骤**：
1. **列出所有可观测信号**：输入信号（cookie 内容）、功能信号（搜索成功）、时间信号（最后活跃时间）
2. **定义信号可信度等级**：主动检测 > 被动命中 > 默认值
3. **主动检测信号需前置条件**：必须"已发生过检测"才可信，不能用"初始值"误判
4. **强制恢复需白名单**：信号1/2 只能恢复其能证明有效的层范围

**判断逻辑**：
```
状态判定 = 输入信号 AND 依赖层验证 AND NOT 手动失效
        + 功能信号兜底（当显示失效但功能可用时）
```

**反模式**：
- 用布尔初始值（如 `False`）代表"未检测"（与"无失效"语义混淆）
- 单信号恢复全层（越权恢复）
- 默认恢复（应防御性写日志 + `set()`）

### 流程 C：Schema 迁移事务安全（SQLite DDL 不可逆操作）

**触发场景**：SQLite 不支持 `ALTER COLUMN`，需要表重建；任何 DDL 修改都应可回滚。

**固定步骤**：
1. **识别 DDL 类型**：ADD COLUMN（直接 ALTER）vs 修改列约束（表重建）
2. **DDL 必包裹在 `engine.begin()` 中**：失败自动回滚
3. **表重建前先清理残留**：`DROP TABLE IF EXISTS {table}_old`
4. **DDL 通过 ORM 连接执行**：`orm_table.create(conn, checkfirst=True)` 而非 `engine`
5. **数据复制用列名交集**：防止列差异导致 INSERT 失败
6. **失败后尝试从 `_old` 恢复**：`SELECT name FROM sqlite_master WHERE name='{table}'` 检查后 RENAME

**判断逻辑**：
```
是否修改列约束？
  ├─ 是 → 表重建（事务 + 残留清理 + 数据复制 + 异常恢复）
  └─ 否 → 直接 ALTER（幂等检查 + 列存在性检查）
```

**反模式**：
- 多步骤分散 commit（部分失败时数据不一致）
- 不清理残留表（下次 RENAME 阻塞）
- 不传连接给 `orm_table.create`（脱离事务）

### 流程 D：状态翻转日志（关键事件可观测）

**触发场景**：状态从 invalid → valid 或反之时；这是排查"为什么状态变了"的唯一线索。

**固定步骤**：
1. **识别关键状态字段**：`valid`、`updated_at`、`manual_invalidate`
2. **翻转时必记日志**：`invalid→valid` 用 `logger.info`，`valid→invalid` 用 `logger.warning`
3. **记录上下文**：cookie 数量、依赖层、恢复原因（`reason` 参数）
4. **时间戳必须更新**：`updated_at = time.time()`，不能遗漏

**判断逻辑**：
```
状态翻转？
  ├─ 是 → 记日志 + 更新 updated_at + 携带上下文
  └─ 否 → 静默通过
```

**反模式**：
- 翻转无日志（排查无据）
- `updated_at` 仅在"无值"时更新（不反映恢复时间）
- 日志只含状态不含原因（信息不足）

---

## 五、适用场景与不适用场景

| 流程 | 适用场景 | 不适用场景 |
|---|---|---|
| A. 缓存失效传播 | 跨进程状态、JSON 持久化、内存缓存、CookieStore、配置缓存 | 纯函数、纯计算缓存（如 LRU math 缓存） |
| B. 状态判定兜底 | 多源派生状态、cookie 有效/服务可用/会话有效 | 单源状态、纯布尔开关、UI 局部状态 |
| C. Schema 迁移事务安全 | SQLite DDL 不可逆、列约束修改、表重建 | ADD COLUMN（直接 ALTER）、PostgreSQL（原生 DDL 事务） |
| D. 状态翻转日志 | 关键业务状态、cookie 层、任务状态、调度状态 | 频繁翻转的高频状态（如计数器）、UI 渲染状态 |

**通用性边界**：
- 流程 A/B 适用于所有有"输入"和"功能"两个独立信号的系统
- 流程 C 仅适用于 SQLite，PostgreSQL/MySQL 有原生 DDL 事务支持
- 流程 D 适用于任何"状态不一致会导致用户困惑"的场景

---

## 六、衍生规范（直接可落地为强制规则）

### 6.1 强制规范：缓存失效传播

> 任何持久化层（JSON/SQLite/文件）变更后，必须**显式调用**对应缓存对象的 `invalidate_cache()` 或等价方法；TTL 兜底不替代主动失效。

### 6.2 强制规范：状态判定必须区分"未检测"与"已检测未失效"

> 任何"功能信号"字段的初始值（默认 `False`）不能被解读为"功能正常"；必须配合"已发生过检测"标记（如 `_last_m5tk_refresh > 0`、`use_count > 0`）。

### 6.3 强制规范：SQLite DDL 修改列约束必须用表重建 + 事务

> 任何 SQLite 列约束变更（NOT NULL→nullable、类型变更）必须通过 `_migrate_make_column_nullable` 模式（事务 + 残留清理 + 数据复制 + 异常恢复），禁止分散 commit。

### 6.4 强制规范：状态翻转必记日志 + 更新时间戳

> 任何状态字段 `valid` 翻转（`invalid→valid`/`valid→invalid`）必须记日志（info/warning）+ 更新 `updated_at`，禁止静默通过。

---

## 七、落地映射

| 规范 | 后端审查规则 | 前端审查规则 | 技能配置节点 |
|---|---|---|---|
| 6.1 缓存失效传播 | B-REVIEW-CACHE-INVALIDATION（维度 14 配置管理） | — | `cache_invalidation` |
| 6.2 状态判定兜底 | B-REVIEW-STATE-DETECTION-BOOTSTRAP（维度 9 异步） | F-REVIEW-STATE-FUNCTIONAL-ALIGN（维度 3 React 组件） | `state_detection_bootstrap` / `state_functional_align` |
| 6.3 迁移事务安全 | B-REVIEW-MIGRATION-TRANSACTION（维度 6 SQLite） | — | `migration_transaction` |
| 6.4 状态翻转日志 | B-REVIEW-STATE-FLIP-LOG（维度 12 日志） | — | `state_flip_log` |

**配套技能更新**：
- `xianyu-hunter-dev` v4.16.0：补充 4 项强制规范（步骤 89-92）
- `xianyu-backend-code-review` v4.15.0：新增 4 项 B-REVIEW 检查点（94-97 项）
- `xianyu-frontend-code-review` v4.16.0：新增 1 项 F-REVIEW 检查点（69 项）
- 所有新规则参数集中在 `config.yaml` 管理（不硬编码）

---

## 八、经验教训

1. **状态显示与功能可用性是两个独立维度**，必须分别度量、分别判定
2. **缓存的"自动失效"不可靠**（TTL 跨进程、回调不直观），必须设计显式 `invalidate` 入口
3. **Schema 演进的"非破坏性"是错觉**——SQLite 的 NOT NULL→nullable 必须重建表，重建必须事务安全
4. **代码审查发现的不止是"问题"**，更是"系统设计的盲区"——本次发现的状态自愈需求即是设计补完
5. **测试预期与实现需同步更新**——增量修改时测试预期要随实现一起更新，避免"通过/失败反复横跳"
