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

---

# 闲鱼猎人编码规范复盘（v2 增补）

> **版本**：v2.0
> **日期**：2026-06-29
> **来源**：从"Cookie 分层管理 identity/session/tracking 一直显示失效"问题复盘
> **复盘方法**：Sequential Thinking 4 维度（成功步骤 / 失败点 / 可抽象流程 / 适用与不适用场景）
> **本次新增**：流程 E（Session Cookie 内嵌 Timestamp 过期检测）+ 流程 F（UI 状态显示与操作按钮分离）+ 规范 6.5/6.6

---

## 九、v2 问题原型

**用户报告**：

> Cookie 分层管理中，identity、session、tracking 一直显示失效

**矛盾本质（两层）**：

1. **后端振荡**：`_m_h5_tk` 已过期 9 小时，但 `cookie.expires=-1`（session cookie）不被常规过期过滤识别。`/cookies/layers` 端点把过期的 `_m_h5_tk` 当作有效 cookie 同步给 CookieRotator，与 TokenRenewer 的失效标记反复振荡
2. **前端 UI 混淆**：`state.valid=true` 时前端显示红色"失效"按钮（供用户主动失效），用户把按钮文字误认为状态显示

**修复涉及文件**：
- `cookie_rotator.py`：新增 `is_m5tk_expired` 辅助函数
- `api_anticrawl.py`：4 处 cookie_map 构造逻辑增加 _m_h5_tk 过期过滤
- `login_orchestrator.py`：`sync_cookie_layers_from_json` 增加过滤
- `frontend/src/pages/AntiCrawl/index.tsx`：按钮文案"失效"→"主动失效" + 图标 + 特殊状态文案

---

## 十、v2 成功执行任务的完整步骤

| 阶段 | 动作 | 产出 |
|---|---|---|
| 1. 数据确认 | 读取 cookies.json 确认 _m_h5_tk timestamp=1782673201708（已过期 9 小时） | 定位振荡根因 |
| 2. 辅助函数 | 在 cookie_rotator.py 添加 `is_m5tk_expired`（检查内嵌 timestamp + TTL=1200s） | 纯函数可独立测试 |
| 3. 后端过滤 | api_anticrawl.py 4 处 + login_orchestrator.py 1 处 cookie_map 构造增加过滤 | 消除振荡 |
| 4. 前端 UI | Playwright 检查 DOM 确认三层 Badge 实际都是 success；按钮文案改为"主动失效" | 消除用户混淆 |
| 5. TS 类型修复 | ItemList.tsx:315 seller_credit number→String() 转换（既有类型不一致） | 解除构建阻塞 |
| 6. 验证 | API 调用确认三层 valid=true + Playwright DOM 检查确认 success Badge | 端到端验证 |

---

## 十一、v2 任务执行过程中的不确定性与失败点

### 11.1 不确定性

| 类别 | 描述 | 处理 |
|---|---|---|
| TTL 值选择 | _m_h5_tk 服务端 TTL 15-22 分钟，取什么值 | 取保守值 1200s，与 token_renewer.RenewerConfig.token_ttl_sec 一致 |
| timestamp 解析 | _m_h5_tk 格式是否稳定 | `rsplit("_", 1)[-1]` 安全解析，无下划线返回 False |
| 过滤范围 | is_m5tk_expired 应在哪些位置应用 | 所有构造 cookie_map 的位置（4 处后端 + 1 处登录同步） |
| UI 修复范围 | 按钮混淆是个案还是通用问题 | 个案，只改 AntiCrawl 页面 |
| force_restore 语义 | count=0 但 valid=true 是否合理 | 不合理但 force_restore 有意设计，UI 显示"已恢复"区分 |

### 11.2 失败点

| # | 失败现象 | 根因 | 修复 |
|---|---|---|---|
| F-9 | 用户报告"显示失效"但 Playwright 检查是 success | 用户把红色"失效"按钮误认为状态显示 | 按钮文案改为"主动失效" + 图标 |
| F-10 | 前端构建失败 | ItemList.tsx:315 seller_credit 类型不一致 | String() 转换（最小修改） |
| F-11 | 用户重启后仍报告问题 | PWA Service Worker 缓存旧 API 响应 | 建议硬刷新或清除 Service Worker |
| F-12 | session/tracking count=0 但 valid=true | force_restore_layers 强制恢复无 cookie 的层 | UI 显示"已恢复（无 Cookie）" |
| F-13 | 初次诊断振荡根因走了弯路 | 未第一时间检查 cookies.json 实际内容 | 先读数据文件再读代码逻辑 |

---

## 十二、v2 可抽象的固定流程与判断逻辑

### 流程 E：Session Cookie 内嵌 Timestamp 过期检测

**触发场景**：Cookie 的 expires 字段为 -1（session cookie），但 cookie 值内嵌了服务端下发时间戳，服务端有独立 TTL。典型代表：`_m_h5_tk`（格式 `{token}_{timestamp_ms}`，服务端 TTL 15-22 分钟）。

**固定步骤**：
1. **识别 session cookie 是否内嵌 timestamp**：检查 cookie 值格式是否包含可解析的时间戳
2. **定义 TTL 常量**：与服务端 TTL 保持一致（如 `_M5TK_TTL_SEC = 1200`），集中为模块级常量
3. **实现过期检测函数**：解析 timestamp，计算 age，与 TTL 比较
4. **在所有 cookie_map 构造处应用过滤**：凡是读取 cookie 并用于状态同步的位置，都必须调用过期检测
5. **解析失败时保守返回 False**（不过期）：避免格式异常导致误判

**判断逻辑**：
```
cookie.expires == -1（session cookie）
  └─ cookie 值是否内嵌 timestamp？
     ├─ 是 → 检查 timestamp + TTL 是否过期
     │     ├─ 过期 → 过滤掉，不纳入 valid_cookies
     │     └─ 未过期 → 保留
     └─ 否 → 按 cookie.expires 常规处理
```

**反模式**：
- 只看 cookie.expires 字段，忽略内嵌 timestamp（导致过期 token 被当作有效，与 TokenRenewer 振荡）
- TTL 值硬编码在多个位置（应集中为模块级常量）
- 解析失败时返回 True（过期）——过于激进，应保守返回 False

### 流程 F：UI 状态显示与操作按钮文案分离

**触发场景**：状态卡片中同时展示状态信息（Badge + 文字）和操作按钮（如"失效""删除""重启"），按钮文案可能被误认为状态描述。

**固定步骤**：
1. **识别易混淆的操作动词**："失效""删除""禁用""停止"等红色/危险按钮文案
2. **按钮文案加前缀或图标**："主动失效"而非"失效"，加 `StopOutlined` 等图标
3. **状态与按钮视觉分离**：状态用 Badge + 副文字，按钮单独一行或右上角
4. **特殊状态显式标注**：如 `valid=true` 但 `count=0` 时显示"已恢复"而非"0 个"

**判断逻辑**：
```
状态卡片中是否同时有状态显示 + 危险操作按钮？
  ├─ 是 → 按钮文案是否可能被误读为状态？
  │     ├─ 是 → 加前缀（"主动"）+ 图标 + 视觉分离
  │     └─ 否 → 保持现状
  └─ 否 → 无需处理
```

**反模式**：
- 按钮文案与状态描述使用相同词汇（如"失效"既表示状态又表示操作）
- `valid=true` 但 `count=0` 时显示"0 个"（用户困惑：有效为什么是 0？）

---

## 十三、v2 适用场景与不适用场景

| 流程 | 适用场景 | 不适用场景 |
|---|---|---|
| E. Session Cookie 内嵌 Timestamp 过期检测 | 服务端下发的 session cookie（expires=-1）但值内嵌时间戳；_m_h5_tk / _m_h5_tk_enc 等 MTOP token；任何有服务端独立 TTL 的 session cookie | 持久 cookie（expires>0，可直接用字段判断）；不内嵌 timestamp 的 session cookie；客户端设置的 cookie（无服务端 TTL） |
| F. UI 状态显示与操作按钮分离 | 状态卡片同时有状态 + 危险操作按钮；Badge + 文字 + 按钮的布局；用户报告"状态不对"但实际是按钮文案混淆 | 纯状态展示（无操作按钮）；操作按钮文案不与状态词汇重叠（如"编辑""导出"）；列表页的操作列 |

**通用性边界**：
- **流程 E** 适用于所有"cookie 字段无法反映真实过期"的场景——不仅限于 _m_h5_tk，任何格式为 `{value}_{timestamp}` 的 cookie 都可复用 `is_m5tk_expired` 模式
- **流程 F** 适用于所有"状态 + 操作"混合的 UI 组件——不仅限于 Cookie 分层管理，任务状态卡片、会话状态卡片等都适用

**与现有流程的关系**：
- 流程 E 是流程 B（状态判定兜底）的**前置补充**——在多信号融合前，先确保输入信号（cookie 内容）本身是有效的
- 流程 F 是流程 D（状态翻转日志）的**前端镜像**——后端记日志保证可观测，前端 UI 分离保证用户可理解

---

## 十四、v2 衍生规范

### 6.5 强制规范：Session Cookie 内嵌 Timestamp 过期检测

> 任何 `expires=-1` 的 session cookie，若值内嵌服务端下发时间戳（格式 `{token}_{timestamp_ms}`），必须实现独立的 timestamp 过期检测函数；所有 cookie_map 构造处必须调用此函数过滤过期 cookie，禁止仅依赖 cookie.expires 字段。

- TTL 值必须与服务端配置一致，集中为模块级常量（如 `_M5TK_TTL_SEC = 1200`）
- 解析失败时保守返回 False（不过期），避免格式异常导致误判
- 过期检测函数必须可独立测试（纯函数，无副作用）

### 6.6 强制规范：UI 状态显示与操作按钮文案分离

> 状态卡片中，操作按钮的文案不得与状态描述使用相同词汇；危险操作按钮必须加前缀（如"主动"）或图标，与状态 Badge 视觉分离。

- `valid=true` 但 `count=0`（强制恢复）时，必须显示"已恢复"而非"0 个"，区分正常有效与强制恢复
- 危险操作按钮（失效/删除/禁用）必须加图标 + 前缀，避免与状态词汇重叠

---

## 十五、v2 落地映射

| 规范 | 后端审查规则 | 前端审查规则 | 技能配置节点 |
|---|---|---|---|
| 6.5 Session Cookie timestamp 过期检测 | B-REVIEW-SESSION-COOKIE-TIMESTAMP（维度 2.4 Cookie 处理） | — | `session_cookie_timestamp` |
| 6.6 UI 状态与操作按钮分离 | — | F-REVIEW-UI-STATE-ACTION-SEPARATION（维度 2.2 业务逻辑 + 2.8 框架模式） | `ui_state_action_separation` |

**配套技能更新**：
- `xianyu-hunter-dev`：在 cookie-state-recovery-patterns.md 补充流程 E/F + 规范 6.5/6.6（本文档）
- `xianyu-backend-code-review`：新增 B-REVIEW-SESSION-COOKIE-TIMESTAMP 检查点
- `xianyu-frontend-code-review`：新增 F-REVIEW-UI-STATE-ACTION-SEPARATION 检查点
- 所有新规则参数集中在模块级常量管理（不硬编码）

---

## 十六、v2 经验教训

1. **用户报告"显示失效"不一定是状态真的失效**——必须用 Playwright 检查实际 DOM 状态，区分"状态显示"与"操作按钮"
2. **session cookie 的 expires=-1 不代表永不过期**——必须检查内嵌 timestamp + 服务端 TTL
3. **前端构建类型错误会阻塞所有修改**——必须先修复既有 TS 错误才能构建新修改
4. **PWA Service Worker 会缓存 API 响应**——NetworkFirst 策略下仍可能返回旧缓存，需建议用户硬刷新
5. **force_restore 导致的 count=0 但 valid=true 是特殊状态**——UI 必须显式标注"已恢复"，不能显示"0 个"


---

# 闲鱼猎人编码规范复盘（v3）

> **版本**：v3.0
> **日期**：2026-07-17
> **来源**：从 3 次关联会话的 Cookie 自愈机制修复过程复盘
> **复盘方法**：Sequential Thinking 4 维度（成功步骤 / 失败点 / 可抽象流程 / 适用与不适用场景）
> **适用范围**：`src/xianyu_hunter/`（Python）
> **配套技能**：`xianyu-hunter-dev`、`xianyu-backend-code-review`、`xianyu-auto-testing`

---

## 十七、v3 问题原型

**3 次关联会话**：

| 会话 | 时间 | 现象 | 根因 |
|---|---|---|---|
| 会话 1 | 2026-07-15 | Cookie 异常 `cookie_expired:_m_h5_tk`，恢复机制失败 | TokenRenewer 未启动（`create_task` 包装同步方法 TypeError）；cookie 过期检查不一致；`_default_renew_callback` 依赖 browser（`with_browser=False` 时失败）；`_should_start_scheduler` 门控 |
| 会话 2 | 2026-07-15 | `_refresh_token_and_retry_detail` 假重试 | `last_session_invalid` 熔断标志未重置；`detail()` 入口检查该标志直接短路返回 `None`，重试形同虚设 |
| 会话 3 | 2026-07-17 | 刚登录成功就检测出会话失效 | `_refresh_token_and_retry_detail` 只刷新 `_m_h5_tk` 不重注入完整 cookie；`BatchRefresh` 批次级无预检；`ensure_official_cookies` 只检查 missing/expired/stale 无法识别"cookie 存在但服务端失效" |

**矛盾本质（3 层）**：

1. **自愈链路断裂**：token 刷新成功 ≠ 会话恢复，刷新后必须重注入完整 cookie 到运行时载体
2. **熔断标志与重试不协调**：熔断标志的生命周期必须与重试逻辑对齐，重试前必须重置标志，否则重试被短路
3. **预检缺失**：批次级操作无前置健康检查，登录后无健康探测，导致"刚登录就失效"和"批次内逐项失败"两种浪费

**修复涉及文件**：
- `collection_service.py`：两级自愈（token 刷新 + cookie 强制注入）、`_log_cookie_diagnostics` 诊断日志
- `batch_refresh_scheduler.py`：批次级预检
- `unified_login.py`：登录后健康探测
- `token_renewer.py`：直接同步调用、拆分 browser/httpx 续期方法、移除启动门控
- `cookie_rotator.py`：`is_m5tk_expired` 辅助函数

---

## 十八、v3 成功执行任务的完整步骤

| 阶段 | 动作 | 产出 |
|---|---|---|
| 1. 现象定位 | 区分"token 刷新失败"与"token 刷新成功但会话未恢复"两种独立故障 | 发现自愈链路断裂根因 |
| 2. 多级自愈设计 | 引入两级自愈（token 刷新 + cookie 强制注入），刷新后必重注入完整 cookie | `collection_service.py` 两级自愈链路 |
| 3. 熔断标志协调 | 重试前显式重置 `last_session_invalid=False`，修正日志误导（区分已刷新/跳过） | `_refresh_token_and_retry_detail` 真重试 |
| 4. 诊断日志模式 | 新增 `_log_cookie_diagnostics`，记录关键状态变量（cookie 数量、层状态、刷新结果、注入结果） | 排查"刚登录就失效"可观测 |
| 5. 批次级预检 | `BatchRefresh` 批次开始前对所有 item 做健康预检，批量失败时熔断而非逐项失败 | 避免批次内逐项失败浪费资源 |
| 6. 登录后健康探测 | `unified_login.py` 登录成功后主动探测一次（搜索/详情任一），失败则降级为"登录成功但会话异常" | 识别"cookie 存在但服务端失效" |
| 7. TokenRenewer 修复 | 移除 `create_task` 包装同步方法、拆分 browser/httpx 续期方法、移除 `_should_start_scheduler` 门控 | `with_browser=False` 模式下 TokenRenewer 正常启动 |

**关键决策**：
- **多级自愈而非单点修复**：token 刷新只是第一级，cookie 重注入是第二级，两级都成功才算自愈成功
- **熔断标志生命周期与重试对齐**：重试前重置标志，避免标志残留导致重试短路
- **预检前置而非事后补救**：批次级预检 + 登录后健康探测，把"逐项失败"前移为"批次级熔断"

---

## 十九、v3 任务执行过程中的不确定性与失败点

### 19.1 失败点

| # | 失败现象 | 根因 | 修复 |
|---|---|---|---|
| U-1 | TokenRenewer 未启动，`cookie_expired:_m_h5_tk` 恢复机制失败 | `create_task` 包装同步方法触发 TypeError；`_default_renew_callback` 依赖 browser（`with_browser=False` 时失败）；`_should_start_scheduler` 门控误判 | 直接同步调用；用 `is_m5tk_expired`；拆分 browser/httpx 续期方法；移除启动门控 |
| U-2 | `_refresh_token_and_retry_detail` 假重试，重试形同虚设 | `last_session_invalid` 熔断标志未重置，`detail()` 入口检查该标志直接短路返回 `None` | 刷新前重置 `last_session_invalid=False` |
| U-3 | 日志误导：刷新被跳过但仍记"已刷新" | 日志未区分"已刷新"与"跳过刷新"两种路径 | 修正日志文案，区分已刷新/跳过 |
| U-4 | 刚登录成功就检测出会话失效 | `_refresh_token_and_retry_detail` 只刷新 `_m_h5_tk` 不重注入完整 cookie | 两级自愈：token 刷新 + cookie 强制注入 |
| U-5 | `BatchRefresh` 批次内逐项失败，资源浪费 | 批次级无预检，无法在批次开始前识别整体失效 | 批次级预检，批量失败时熔断 |
| U-6 | `ensure_official_cookies` 无法识别"cookie 存在但服务端失效" | 只检查 missing/expired/stale，不检查服务端实际可用性 | 登录后健康探测，主动调用一次 API 验证 |
| U-7 | 排查"刚登录就失效"无据可查 | 关键状态变量（cookie 数量、层状态、刷新结果、注入结果）未记录 | `_log_cookie_diagnostics` 诊断日志 |

### 19.2 不确定性

| 类别 | 描述 | 处理 |
|---|---|---|
| 自愈层级数 | 两级是否足够，是否需要三级（token → cookie → 重新登录） | 两级覆盖 90% 场景，第三级"重新登录"由用户/系统手动触发 |
| 熔断标志重置时机 | 重置在"重试前"还是"刷新成功后" | 重试前重置，避免标志残留导致重试短路；刷新失败时标志会被再次置位 |
| 预检失败阈值 | 批次预检失败多少项才熔断 | 失败比例 ≥ 阈值（默认 50%）才熔断，避免单点失败误熔断整个批次 |
| 健康探测 API 选择 | 用搜索还是详情作为探测 | 用详情（轻量、不依赖搜索关键词），失败时降级为"登录成功但会话异常" |

---

## 二十、v3 可抽象的固定流程与判断逻辑

### 流程 G：多级自愈模式（Token → Cookie → 放弃）

**触发场景**：会话失效时，单点刷新（如 token 刷新）成功不等于会话恢复，需要多级自愈链路。

**固定步骤**：
1. **第一级（Token 刷新）**：调用 `token_renewer.refresh()`，刷新 `_m_h5_tk` 等临时 token
2. **第二级（Cookie 重注入）**：token 刷新成功后，从 CookieStore 读取完整 cookie 并强制注入到运行时载体（浏览器/httpx）
3. **第三级（放弃）**：两级都失败时，标记会话失效，等待用户/系统重新登录

**判断逻辑**：
```
会话失效检测
  ├─ 第一级：token 刷新
  │     ├─ 成功 → 第二级：cookie 重注入
  │     │     ├─ 成功 → 自愈成功，继续业务
  │     │     └─ 失败 → 第三级：放弃，标记失效
  │     └─ 失败 → 第三级：放弃，标记失效
  └─ 自愈链路任何一级失败都必须记日志（含上下文）
```

**反模式**：
- 只刷新 token 不重注入 cookie（"刷新成功但会话未恢复"）
- 自愈链路无日志（排查无据）
- 单级自愈失败直接放弃（未尝试下一级）

### 流程 H：熔断标志与自动重试协调

**触发场景**：系统有熔断标志（如 `last_session_invalid`）+ 自动重试逻辑时，两者必须协调，否则重试被短路。

**固定步骤**：
1. **识别熔断标志**：列出所有"会阻断重试"的标志字段（`last_session_invalid`、`is_paused`、`circuit_broken`）
2. **重试前重置标志**：自动重试逻辑开始前，显式重置熔断标志（`last_session_invalid=False`）
3. **重试失败时标志回置**：重试失败时，标志会被业务逻辑再次置位，无需手动回置
4. **日志区分路径**：日志必须区分"已重置标志并重试"与"标志未重置跳过重试"两种路径

**判断逻辑**：
```
自动重试逻辑开始
  ├─ 检查熔断标志
  │     ├─ 标志为 True → 显式重置为 False → 执行重试
  │     └─ 标志为 False → 直接执行重试
  ├─ 重试成功 → 标志保持 False，继续业务
  └─ 重试失败 → 业务逻辑置位标志，等待下次自愈
```

**反模式**：
- 重试前不重置熔断标志（重试被短路，"假重试"）
- 日志不区分"已重置"与"跳过"（排查误导）
- 重试失败时手动回置标志（与业务逻辑重复，可能导致标志不一致）

### 流程 I：诊断日志模式（关键状态变量记录）

**触发场景**：会话失效、自愈失败、批次失败等关键事件，需要记录关键状态变量用于事后排查。

**固定步骤**：
1. **识别关键状态变量**：cookie 数量、层状态（valid/updated_at）、刷新结果、注入结果、熔断标志
2. **集中记录**：用专用函数（如 `_log_cookie_diagnostics`）集中记录，而非散落在各处
3. **结构化字段**：日志含 `extra={...}` 结构化字段，便于日志聚合查询
4. **日志级别**：自愈成功用 `info`，自愈失败用 `warning`，诊断细节用 `debug`

**判断逻辑**：
```
关键事件（会话失效/自愈失败/批次失败）
  ├─ 调用 _log_cookie_diagnostics(tag, context)
  │     ├─ 记录 cookie 数量、层状态、刷新结果、注入结果
  │     ├─ 记录熔断标志当前值
  │     └─ 日志级别按事件严重性选择
  └─ 日志含结构化字段 extra={...}
```

**反模式**：
- 关键状态变量散落在各处 `logger.info`（排查时需拼凑）
- 日志只含状态不含上下文（信息不足）
- 诊断细节用 `warning`（刷屏，淹没真正告警）

### 流程 J：预检前置模式（批次级预检 + 登录后健康探测）

**触发场景**：批次级操作（如 `BatchRefresh`）逐项失败浪费资源；登录后立即使用但会话实际未恢复。

**固定步骤**：
1. **批次级预检**：批次开始前对所有 item 健康预检（cookie 存在性 + 服务端可用性抽样）
2. **预检失败熔断**：失败比例 ≥ 阈值（默认 50%）时熔断整个批次，而非逐项失败
3. **登录后健康探测**：登录成功后主动调用一次 API（如详情）验证会话可用性
4. **探测失败降级**：探测失败时降级为"登录成功但会话异常"，触发自愈或提示用户

**判断逻辑**：
```
批次开始
  ├─ 批次级预检（所有 item）
  │     ├─ 失败比例 < 阈值 → 继续批次
  │     └─ 失败比例 ≥ 阈值 → 熔断批次，记日志
  └─ 登录成功后
        ├─ 健康探测（调用一次 API）
        │     ├─ 成功 → 会话可用，继续业务
        │     └─ 失败 → 降级"登录成功但会话异常"，触发自愈
```

**反模式**：
- 批次无预检（逐项失败，资源浪费）
- 登录后无健康探测（"刚登录就失效"无法识别）
- 预检失败不熔断（继续批次，浪费资源）
- 探测失败不降级（误以为登录成功，业务异常）

---

## 二十一、v3 适用场景与不适用场景

| 流程 | 适用场景 | 不适用场景 |
|---|---|---|
| G. 多级自愈模式 | 会话失效自愈（token + cookie）、多级降级链、需要"刷新 + 重注入"的场景 | 单点刷新即可恢复的场景（如纯 token 续期）、无运行时载体的纯文件存储 |
| H. 熔断标志与自动重试协调 | 有熔断标志 + 自动重试的系统（会话失效、断路器、连接池）、重试可能被标志短路的场景 | 无熔断标志的简单重试、一次性操作无重试逻辑、纯客户端重试（无服务端标志） |
| I. 诊断日志模式 | 关键事件排查（会话失效、自愈失败、批次失败）、需要事后取证的运维场景 | 高频路径（日志开销不可接受）、纯计算函数（无状态可记）、开发环境调试（用 print 即可） |
| J. 预检前置模式 | 批次级操作（批量采集、批量刷新）、登录后立即使用、需要"前置健康检查"的场景 | 单次操作（无批次概念）、实时交互（预检延迟不可接受）、无服务端可用性概念（如本地缓存） |

**通用性边界**：
- **流程 G** 适用于所有"单点刷新不等于恢复"的场景——不仅限于 cookie，任何"刷新 + 重注入"的两级自愈都适用
- **流程 H** 适用于所有"熔断标志 + 自动重试"的组合——不仅限于 `last_session_invalid`，任何"标志可能短路重试"的场景都适用
- **流程 I** 适用于所有"关键事件需要事后排查"的场景——不仅限于 cookie 自愈，任何"状态变量多、排查难"的场景都适用
- **流程 J** 适用于所有"批次操作 + 登录后使用"的场景——不仅限于 BatchRefresh，任何"逐项失败浪费资源"的场景都适用

**与现有流程的关系**：
- **流程 G** 是流程 B（状态判定兜底）的**自愈链路扩展**——流程 B 管"如何判定状态"，流程 G 管"状态失效后如何多级自愈"
- **流程 H** 是流程 D（状态翻转日志）的**协调补充**——流程 D 管"翻转必记日志"，流程 H 管"标志与重试如何协调"
- **流程 I** 是流程 D（状态翻转日志）的**诊断增强**——流程 D 记单次翻转，流程 I 记完整诊断快照
- **流程 J** 是流程 A（缓存失效传播）的**前置补充**——流程 A 管"写后同步"，流程 J 管"读前预检"

---

## 二十二、v3 衍生规范

### 6.7 强制规范：多级自愈模式（Token → Cookie → 放弃）

> 会话失效自愈必须实现多级链路（token 刷新 → cookie 重注入 → 放弃），单级刷新成功不等于会话恢复，刷新后必须重注入完整 cookie 到运行时载体，禁止只刷新 token 不重注入 cookie。

- 自愈链路每级失败都必须记日志（含上下文：cookie 数量、层状态、刷新结果、注入结果）
- 自愈链路配置化：层级数、每级动作、失败后是否进入下一级，全部从 `config.yaml` 读取
- 第三级"放弃"必须标记会话失效，等待用户/系统重新登录，禁止无限重试

### 6.8 强制规范：熔断标志与自动重试协调

> 有熔断标志（如 `last_session_invalid`）+ 自动重试逻辑时，重试前必须显式重置熔断标志，否则重试被短路；日志必须区分"已重置标志并重试"与"标志未重置跳过重试"两种路径。

- 熔断标志清单、重置时机、日志文案模板，全部从 `config.yaml` 读取
- 重试失败时标志由业务逻辑置位，禁止手动回置（避免与业务逻辑重复）
- 标志重置必须用显式赋值（`last_session_invalid=False`），禁止依赖隐式副作用

### 6.9 强制规范：诊断日志模式（关键状态变量记录）

> 关键事件（会话失效、自愈失败、批次失败）必须用专用函数（如 `_log_cookie_diagnostics`）集中记录关键状态变量（cookie 数量、层状态、刷新结果、注入结果、熔断标志），禁止散落 `logger.info`。

- 关键状态变量清单、日志级别映射、结构化字段 schema，全部从 `config.yaml` 读取
- 诊断日志必须含 `extra={...}` 结构化字段，便于日志聚合查询
- 日志级别按事件严重性选择：自愈成功 `info`、自愈失败 `warning`、诊断细节 `debug`

### 6.10 强制规范：预检前置（批次级预检 + 登录后健康探测）

> 批次级操作（如 `BatchRefresh`）开始前必须对所有 item 健康预检，失败比例 ≥ 阈值时熔断批次；登录成功后必须主动调用一次 API（如详情）验证会话可用性，探测失败时降级为"登录成功但会话异常"。

- 预检失败阈值（默认 50%）、健康探测 API 选择、降级文案，全部从 `config.yaml` 读取
- 预检失败熔断时必须记日志（含失败比例、失败项清单）
- 健康探测失败降级时必须触发自愈或提示用户，禁止误以为登录成功

---

## 二十三、v3 落地映射

| 规范 | 后端审查规则 | 前端审查规则 | 技能配置节点 |
|---|---|---|---|
| 6.7 多级自愈模式 | B-REVIEW-MULTI-LEVEL-SELF-HEAL（维度 9 异步 + 维度 12 日志） | — | `multi_level_self_heal` |
| 6.8 熔断标志与重试协调 | B-REVIEW-CIRCUIT-FLAG-RETRY-COORD（维度 9 异步 + 维度 14 配置管理） | — | `circuit_flag_retry_coord` |
| 6.9 诊断日志模式 | B-REVIEW-DIAGNOSTIC-LOG-PATTERN（维度 12 日志） | — | `diagnostic_log_pattern` |
| 6.10 预检前置 | B-REVIEW-PRECHECK-FRONTLOAD（维度 9 异步 + 维度 6 SQLite） | — | `precheck_frontload` |

**配套技能更新**：
- `xianyu-hunter-dev` v4.47.0：新增 4 项强制规范（step 229-232）
- `xianyu-backend-code-review`：新增 4 项 B-REVIEW 检查点
- `xianyu-auto-testing`：新增 4 个配置节点（自愈链路测试、熔断标志协调测试、诊断日志测试、预检前置测试）
- 所有新规则参数集中在 `config.yaml` 管理（不硬编码）

---

## 二十四、v3 经验教训

1. **单点刷新成功不等于会话恢复**——token 刷新只是第一级，cookie 重注入是第二级，两级都成功才算自愈成功
2. **熔断标志的生命周期必须与重试逻辑对齐**——重试前必须重置标志，否则重试被短路，"假重试"比"不重试"更危险
3. **日志必须区分"已执行"与"跳过"两种路径**——"已刷新"与"跳过刷新"是两种不同语义，混淆会误导排查
4. **批次级操作必须前置预检**——逐项失败浪费资源，预检失败熔断整个批次是更优策略
5. **登录成功 ≠ 会话可用**——cookie 存在但服务端失效是常见场景，登录后必须健康探测
6. **诊断日志必须集中记录关键状态变量**——散落在各处的 `logger.info` 在排查时需拼凑，集中记录才能快速定位
7. **多级自愈链路必须配置化**——层级数、每级动作、失败后是否进入下一级，禁止硬编码在代码中
