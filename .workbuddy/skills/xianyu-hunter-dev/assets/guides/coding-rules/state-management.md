# State Management 编码规范
> 本文件归档 xianyu-hunter-dev skill 中与「state management」主题相关的编码规范。
> 主索引见 [SKILL.md](../../../SKILL.md) 的"step 索引表"，元规范见 [meta-rules.md](../../../references/meta-rules.md)。

---

### step 11：状态管理一致性【强制】

11. **状态管理一致性【强制】**
    - 状态变更操作必须同步更新所有相关字段，避免"激活但未恢复""关闭但未清除引用"等不一致状态
    - 典型场景：`activateSheet` 激活最小化 sheet 时必须同时设 `minimized: false`，否则内容区显示空状态
    - 检查方法：每个状态变更函数，列出影响的所有字段，确认全部同步更新
    - 适用范围：Zustand store 的所有操作（open/close/activate/minimize/restore），后端状态机转换


---

### step 24：UI 状态独立性原则【强制】🆕v4.2

24. **UI 状态独立性原则【强制】🆕v4.2**
    - **受控 UI 状态不应自动联动路由变化**：Menu `openKeys`、Tree `expandedKeys`、Collapse `activeKey`、Tabs `activeKey` 等用户手动控制的展开/折叠状态，必须独立于路由，仅在用户主动操作（点击 SubMenu 标题、折叠面板等）时变化
    - **路由变化只应更新派生状态**：`selectedKeys`（高亮当前项）、breadcrumb（面包屑）、页面标题等派生状态应联动路由，但**不应**改变用户手动控制的 UI 状态
    - **判断信号**：组件有 `useState` + `useEffect` 依赖 `location.pathname`/`useNavigate` → 检查是否过度联动（`openKeys`/`expandedKeys` 联动路由视为违规）
    - **修复模式**：`openKeys` 仅在首次挂载时按当前路由初始化（`useState(() => autoOpenKeys)`），之后完全由用户通过 `onOpenChange` 控制，**移除** `useEffect(() => setOpenKeys(autoOpenKeys), [autoOpenKeys])` 联动逻辑
    - **适用**：Menu `openKeys`、Tree `expandedKeys`、Collapse `activeKey`、Drawer `open` 等用户手动控制的 UI 状态
    - **不适用**：`selectedKeys`（应联动路由高亮当前项）、breadcrumb（应联动路由）、页面标题（应联动路由）
    - **历史教训**：MainLayout 的 `openKeys` 通过 `useEffect` 联动 `autoOpenKeys`，sheet 切换触发 `navigate` → URL 变化 → `autoOpenKeys` 重算 → `setOpenKeys` 重置 → SubMenu 展开/折叠动画遮挡内容。第一次修复用"合并"策略仍会展开新 SubMenu，最终改为完全移除 `useEffect` 联动才彻底解决


---

### step 28：跨组件状态同步【强制】🆕v4.3

28. **跨组件状态同步【强制】🆕v4.3**
    - 多个组件对同一概念（如"会话有效性"、"登录状态"）做判断时，状态变更必须双向同步：
      - 组件 A 检测到状态变化 → 主动通知组件 B 更新状态
      - 组件 B 查询状态时 → 额外检查组件 A 的最新状态（而非仅依赖自身缓存）
    - **判断信号**：两个以上组件各自独立判断"会话有效性"/"登录状态"/"Cookie 有效性"等同一概念
    - **修复模式**：状态变更方调用 `invalidate_layer()` / `notify()` 通知其他组件；查询方在判断时额外检查其他组件的状态标志（如 `collector.last_session_invalid`）
    - **适用**：分布式状态、跨层状态同步（如 orchestrator + worker + health_checker 对"会话有效性"的判断）
    - **不适用**：单组件内部状态、无跨组件依赖的独立判断
    - **历史教训**：健康检查器检查 Cookie 本地存在性（返回有效），但 worker 通过实际 API 调用检测到 RGV587_ERROR（服务端已注销会话），两者判断维度不同导致"健康检查显示有效但任务自动暂停"的矛盾现象


---

### step 44：多源状态同步统一入口【强制】🆕v4.6

44. **多源状态同步统一入口【强制】🆕v4.6**
    - 同一份状态（如 Cookie 层状态、用户登录态、连接池状态）有 ≥ 2 个写入入口时，必须建立**统一同步入口函数**（如 `sync_cookie_layers_from_json()`），在所有写入路径写完后主动调用
    - **判断信号**：核心状态依赖外部存储（JSON / SQLite / 浏览器内存 / 远程 API），但内存层状态只在某个入口被同步 → 出现"实际有数据但显示失效"的脱节现象
    - **修复模式**：识别所有写入路径（登录 / 注入 / 导入 / 工具刷新）→ 抽取 `sync_xxx_from_<主数据源>()` 公共函数 → 在每个写入路径的成功分支主动调用 → 同步逻辑必须重新读主数据源（而非用调用方传入的列表），避免过滤逻辑不一致
    - **关键约束**：禁止依赖某个回调（如 `on_login_success`）自动触发而无任何调用方——必须显式调用
    - **适用**：状态分布在多个存储介质（JSON / SQLite / 浏览器 / 内存）且需保持显示一致；多入口写入同一份状态
    - **不适用**：单一写入入口、状态天然同步（无中间层缓存）、纯计算型状态
    - **历史教训**：`CookieRotator` 的 `on_login_success` 钩子函数被定义后从未被任何调用方触发，导致 5 个登录路径（`browser_login` / `auth_helper` / `cookie_inject` / `browser_import` / `qr_login`）都绕过层状态更新，登录后 `/cookies/layers` 端点始终显示三层失效但功能完全正常


---

### step 45：状态条件区分'从未初始化'与'主动失效'【强制】🆕v4.6

45. **状态条件区分"从未初始化"与"主动失效"【强制】🆕v4.6**
    - 当状态字段有"从未初始化 / 已初始化 / 主动失效"三种语义时，**禁止**用 `not state.valid` 笼统判断"该同步了"——必须用 `state.updated_at == 0.0` 区分"从未初始化"和"主动失效后"
    - **判断信号**：状态对象有 `valid` + `updated_at` 两个字段 + 存在"主动失效"语义（如 `invalidate_layer()` 显式置 `valid=False` 但保留 `updated_at`）→ 用 `not valid` 会覆盖手动失效状态
    - **修复模式**：
      - **从未初始化**（`updated_at == 0.0`）：可主动补救同步（读主数据源、读浏览器内存兜底）
      - **主动失效**（`updated_at > 0.0 and not valid`）：保留状态不覆盖（用户/系统已显式标记失效）
      - **已初始化有效**（`updated_at > 0.0 and valid`）：正常返回
    - **适用**：所有"状态机 + 主动失效"语义的场景（Cookie 层状态、用户会话状态、健康检查状态）
    - **不适用**：纯二元状态（有效/无效）、无"主动失效"语义的简单标志位
    - **历史教训**：`cookie_checker` 健康检查器用 `not identity_state.valid` 作为"需要同步"的判断条件，导致 collector 检测到 RGV587 主动失效 identity 层后，cookie_checker 在下次 tick 立即从 JSON 重新同步覆盖失效状态，造成"自动失效永远不生效"的死循环


---

### step 46：浏览器内存兜底同步模式【强制】🆕v4.6

46. **浏览器内存兜底同步模式【强制】🆕v4.6**
    - 当主数据源（JSON）可能与运行时状态（浏览器内存、内存缓存）脱节时，状态查询端点必须实现**两步同步**：第一步从主数据源同步；第一步后仍有状态未恢复时，从运行时载体读取作为兜底
    - **判断信号**：主数据源 + 运行时载体共存 + 某些字段（如 MTOP token）只在运行时载体更新（被外部进程 `Set-Cookie`） + 状态查询可能因为 JSON 过期而误报失效
    - **修复模式**：
      1. **第一步（主数据源同步）**：从 JSON 读取、过滤过期、构造 cookie_map、调用 `sync_state_from_cookies()`
      2. **第二步（兜底同步）**：检查仍有 `updated_at==0.0` 的层 → 从 `browser.context.cookies()` 读取对应域 → 重新构造 cookie_map → 同步 → 回写主数据源（避免下次再走兜底）
    - **回写策略**：用 `upsert`（更新 + 添加）而非 `update`（只更新已存在），因 JSON 中可能完全不存在该 cookie 条目
    - **配置参数**：兜底同步开关、读取的 cookie 域列表、回写白名单在 `config/cookie_fallback.yaml` 管理
    - **适用**：浏览器 Cookie 多源持久化、CDP/Playwright 抓取场景、外部进程状态回写
    - **不适用**：无运行时载体的纯文件存储、有强一致要求的场景（应直接报错而非兜底）
    - **历史教训**：`_m_h5_tk` 等 session token 在 MTOP 响应中被 `Set-Cookie` 写入浏览器内存，但 `_sync_response_cookies_to_context` 只调 `add_cookies` 不回写 JSON。重启后浏览器从 JSON 加载旧 token 失败，但功能靠浏览器内存正常工作。`/cookies/layers` 端点增加浏览器内存兜底同步 + 回写 JSON 后彻底解决


---

### step 47：Update vs Upsert 语义区分【强制】🆕v4.6

47. **Update vs Upsert 语义区分【强制】🆕v4.6**
    - 持久化层（CookieStore / Repository）必须明确区分"Update"和"Upsert"两类操作，**禁止**用一个方法兼顾两种语义
    - **判断信号**：函数命名含 `update` 但实际行为是"更新或新增"，或反之 → 维护者无法从命名判断行为
    - **修复模式**：
      - **`update_cookie_values(updates)`**：只更新已存在的 cookie（name 在 JSON 中存在 → 替换 value；不存在 → 跳过）。用于 token 刷新场景
      - **`upsert_cookie_values(upserts)`**：更新已存在 + 添加不存在（name 在 JSON 中存在 → 替换 value；不存在 → 追加新条目）。用于浏览器兜底回写场景
    - **关键约束**：upsert 必须携带完整属性（`value`/`domain`/`path`/`expires`），不能只传 value 因为新条目需要完整字段
    - **并发安全**：读-改-写必须在 `self._lock`（`RLock`）内完成，避免与并发 `export_cookies` 交错导致数据丢失
    - **元数据保护**：方法标签（如 `data["method"]`）必须用 `if "mtop_refresh" not in existing_method: data["method"] = existing_method + "+mtop_refresh"` 避免无限追加
    - **适用**：所有持久化层的数据合并操作（Cookie / 缓存 / 索引）
    - **不适用**：纯 add-only 日志、纯 replace 全量覆盖
    - **历史教训**：MTOP 刷新 `_m_h5_tk` 时若用 `update_*` 但 JSON 中没有该条目 → 静默丢失；反之若用 `upsert_*` 但 JSON 中已有 → 字段被覆盖（如 `expires`）→ 下次过滤过期逻辑失效


---

### step 48：写后钩子（Post-Write Hook）规范【强制】🆕v4.6

48. **写后钩子（Post-Write Hook）规范【强制】🆕v4.6**
    - 所有"写主数据源 + 同步派生状态"的操作必须实现**显式写后钩子**——禁止依赖隐式回调、事件总线自动触发、定时器轮询
    - **判断信号**：派生状态（缓存 / 索引 / 内存模型）需要与主数据源保持一致，但代码中只在某个特定入口同步 → 其他写入路径遗漏
    - **修复模式**：
      - 在每个写入路径的成功分支（`if json_written: ...`）添加显式调用
      - 钩子函数应**幂等**：可重复调用而不会产生副作用
      - 钩子失败必须**仅记录日志不抛异常**：派生状态同步失败不能阻断主写入
      - 钩子逻辑应**重新读主数据源**而非用调用方传入的列表（避免过滤逻辑不一致）
    - **典型实现**：
      ```python
      if json_written:
          try:
              sync_cookie_layers_from_json()
          except Exception as e:
              logger.debug("写后钩子失败（不影响主流程）: %s", e)
      ```
    - **适用**：所有"写后需要同步派生状态"的场景（Cookie 状态机、缓存失效、索引重建、计数器重置）
    - **不适用**：单写入入口且无派生状态、性能敏感场景（钩子开销不可接受）
    - **历史教训**：登录路径写 JSON 后没有任何钩子触发 `CookieRotator.sync_state_from_cookies()`，导致层状态永远停留在 `valid=False, updated_at=0.0`，`/cookies/layers` 显示三层全部失效


---

### step 49：死代码检测与清理【强制】🆕v4.6

49. **死代码检测与清理【强制】🆕v4.6**
    - 业务流程中**未在任何调用点被触发的函数/方法**必须在每次大版本（v4.x → v4.x+1）时主动检测并清理
    - **判断信号**：
      - 函数被定义（如 `def on_login_success(self): ...`）但 `grep -rn "on_login_success" src/` 找不到任何调用
      - 事件订阅被注册但 `grep` 不到发布者
      - 抽象方法被子类实现但从未被子类外部调用
    - **检测方法**：
      1. `git log -p --all -S "<function_name>"` 查看该函数的所有历史变更
      2. `grep -rn "<function_name>" src/ tests/` 确认无任何调用方
      3. 在 PR/Commit 描述中显式标注"删除死代码 X"
    - **修复模式**：
      - **找到调用方**：恢复调用路径（适合误删调用方导致的死代码）
      - **改写为入口函数**：将死代码改写为"统一同步入口"（如 `on_login_success` 改写为 `sync_cookie_layers_from_json`）
      - **直接删除**：无任何依赖时直接删除
    - **适用**：所有"定义即遗忘"的函数/回调/事件订阅/类方法
    - **不适用**：保留作为 API 接口的方法（即便未被内部调用）、测试 fixture、抽象基类
    - **历史教训**：`CookieRotator.on_login_success` 方法被定义后从未被任何登录路径调用，"逻辑上应该被触发"但实际是死代码，导致登录后层状态永远不更新


---

### step 87：Cookie 层依赖关系信号匹配规范【强制】🆕v4.15

87. **Cookie 层依赖关系信号匹配规范【强制】🆕v4.15**
    - 层恢复信号必须与层范围匹配，SESSION 层信号不能恢复 IDENTITY 层，IDENTITY 无效时 SESSION 也不能恢复。层定义的 `depends_on` 字段指示依赖关系，信号只能恢复其所属层及以下层，禁止跨层恢复导致状态不一致
    - **判断信号**：代码含 `sync_cookie_layers_from_json()` 或 `_sync_layers_from_signal()` → 必须检查信号与层的匹配关系；层定义含 `depends_on` 字段 → 信号恢复必须遵循依赖链
    - **修复模式**：
      1. 检查层定义依赖关系：`grep -rn "depends_on" src/` 找到层依赖配置
      2. 分析信号范围：SESSION 层信号只能恢复 SESSION 层，IDENTITY 层信号可恢复 IDENTITY + SESSION 层（依赖链）
      3. 修复跨层恢复：信号恢复逻辑必须按 `depends_on` 递归恢复，禁止直接跳层
      4. 验证：层状态恢复后依赖链上的所有层状态一致
    - **配置参数**：`cookie_layers.signal_layer_mapping`（信号到层的映射表，如 `login_success → identity`，`session_refresh → session`）、`cookie_layers.depends_on_chain`（层依赖链，如 `session → identity → base`）在 `config.yaml` 的 `cookie_layers` 节点管理
    - **适用**：层级依赖的状态恢复、Cookie 层管理、多源状态同步
    - **不适用**：无层级依赖的状态、独立状态恢复、单层状态管理
    - **历史教训**：SESSION 层恢复信号 `sync_from_browser()` 被误用于恢复 IDENTITY 层，导致 IDENTITY 层状态与实际不一致（浏览器已失效但层状态显示有效）


---

### step 91：缓存失效传播规范【强制】🆕v4.16

91. **缓存失效传播规范【强制】🆕v4.16**
    - 任何持久化层（JSON 文件 / SQLite / 外部配置）变更后，必须**显式调用**对应缓存对象的 `invalidate_cache()` 或等价方法，TTL 兜底不替代主动失效
    - 跨进程变更（子进程写、主进程读）必须主动通知主进程失效缓存，禁止依赖"下次读时发现不一致"（读时已晚）
    - **判断信号**：类含 `_cache`/`_cache_time`/`_cached_*` 字段 → 必须有 `invalidate_cache()` 方法；写入主数据源的方法（`update_*`/`upsert_*`/`write_*`）未在写后调用同步钩子 → 必须补齐
    - **修复模式**：
      1. 识别共享状态：明确"输入字段"、"派生字段"、"持久化副本"三类
      2. 设计 invalidate 入口：每个缓存对象暴露 `invalidate_cache()` 方法
      3. 写入主路径后必调：所有写主数据源方法在写后**显式**调用 `invalidate_cache()`
      4. 失败降级：同步钩子失败仅 `logger.warning`，不抛异常阻塞主流程
    - **配置参数**：`cache_invalidation.enabled`（默认 `true`）、`cache_invalidation.ttl_grace_seconds`（TTL 兜底秒数，默认 0 即不依赖 TTL）、`cache_invalidation.fail_log_level`（默认 `warning`）在 `config.yaml` 的 `cache_invalidation` 节点管理
    - **适用**：JSON 持久化层、跨进程 Cookie/状态同步、内存缓存与文件副本同步、登录态多进程写入
    - **不适用**：纯函数、纯计算缓存（如 LRU math 缓存）、无外部数据源同步的内部状态
    - **历史教训**：CookieStore 用 30 秒 TTL 兜底缓存，浏览器子进程登录后只更新子进程自己的缓存，主进程仍读到旧缓存，导致 3 个 Cookie 层显示失效（功能实际可用）


---

### step 92：状态判定需区分'未检测'与'已检测未失效'【强制】🆕v4.16

92. **状态判定需区分"未检测"与"已检测未失效"【强制】🆕v4.16**
    - 任何"功能信号"字段（`last_session_invalid`/`is_healthy`/`is_connected` 等）不能仅用布尔初始值（如 `False`）代表"未检测"——`False` 与"已检测无失效"语义混淆，会导致刚启动时误判为"功能正常"
    - 必须配合"已发生过检测"标记（时间戳 `_last_check_at > 0`、计数器 `use_count > 0`、首次成功标记 `_has_run`）
    - **判断信号**：布尔字段默认值 `False` + 实际语义是"初始未检测" → 必须增加时间戳/计数器区分；强制恢复/兜底逻辑仅依赖布尔字段 → 必须加前置条件
    - **修复模式**：
      1. 增加"已检测"标记：`_last_m5tk_refresh > 0` / `use_count > 0` / `_has_run = True`
      2. 信号判定前置条件：`if has_searched and session_ok: signals.add(...)`
      3. 强制恢复需白名单：信号 1/2 只能恢复其能证明有效的层范围（`collector.last_session_invalid=False` 恢复全层，`json_has_valid_m5tk` 恢复 SESSION 层）
      4. 防御性 else：未识别的信号组合不默认恢复所有层，写 `logger.warning` 后 `set()`
    - **配置参数**：`state_detection_bootstrap.required_marker`（前置条件类型：`timestamp`/`counter`/`flag`，默认 `timestamp`）、`state_detection_bootstrap.signal_layer_mapping`（信号到层范围映射，如 `collector_signal → [identity, session, tracking]`、`m5tk_signal → [session]`）、`state_detection_bootstrap.unknown_signal_strategy`（默认 `set()` 即不恢复）在 `config.yaml` 的 `state_detection_bootstrap` 节点管理
    - **适用**：跨进程/跨模块状态判定、Cookie 层状态自愈、容器健康检查、服务可用性兜底
    - **不适用**：纯客户端 UI 状态、单次函数返回值、无初始歧义的开关字段
    - **历史教训**：collector 刚启动还没搜索过任何商品时，`last_session_invalid=False` 被解读为"会话有效"，强制恢复所有 Cookie 层（包括实际已失效的 IDENTITY），导致用户看到"状态闪烁"（失效→恢复→再失效）


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

### step 149：CIRCUIT-01 熔断器持久化对称性原则【强制】🆕v4.29

**背景**：`batch_refresh_scheduler.py` 熔断时未调用 `_save_progress()`，剩余项未持久化为 pending，导致重启后无法续传，剩余项丢失。

**问题**：熔断分支与正常停止分支的持久化流程不对称，熔断时跳过进度保存，导致剩余项状态不一致，重启后无法续传。

**规范**：

1. **熔断分支必须执行完整持久化流程【强制】**：熔断分支必须与正常停止分支执行相同的持久化流程，实现清单：
   - **保存当前进度**：调用 `_save_progress()` 保存已完成项
   - **记录熔断状态**：剩余项标记为 `pending`（可续传），而非 `cancelled`（不可续传）
   - **通知下游**：发布熔断事件，通知订阅方
   - **日志措辞准确**：用 `break=terminated`（熔断终止）而非 `stop=completed`（正常完成）

2. **熔断与正常停止的日志区分【强制】**：熔断日志必须明确标识为"熔断"（如 `consecutive failures, circuit broken`），禁止与正常停止日志混淆。

**配置驱动**：`coding_standards.circuit_breaker.cleanup_checklist`（熔断清理清单）在 `config.yaml` 管理。

**适用场景**：
- 任何熔断器/断路器实现（批量采集/批量刷新/批处理）
- 长时间运行任务的异常终止
- 需要重启续传的批处理任务

**不适用场景**：
- 无状态服务（无进度需保存）
- 一次性脚本（无需续传）
- 用户主动取消（应标 `cancelled` 而非 `pending`）

**历史教训**：`batch_refresh_scheduler.py` 熔断时未调用 `_save_progress()`，100 个剩余项未标 pending，重启后无法续传，用户需重新启动。修复后熔断分支补齐 `_save_progress()` + 标 pending。

**判断信号（review 触发条件）**：
- `grep "consecutive.*fail" <file>` 附近无 `_save_progress()` 调用
- 熔断分支与正常停止分支的持久化逻辑不一致


---

### step 150：STATE-01 状态切换原子性原则【强制】🆕v4.29

**背景**：Sheet 页 `activateSheet` 激活时未设置 `minimized: false`，导致恢复按钮无响应（sheet 激活但仍处于最小化状态）。

**问题**：状态切换涉及多个相关字段时，仅更新部分字段导致状态不一致（如激活但未恢复、关闭但未清除引用）。

**规范**：

1. **多字段状态切换必须同步更新【强制】**：状态切换涉及多个字段时，必须同步更新所有相关字段：
   ```typescript
   // ✅ 正确：激活时同步设置 minimized: false
   activateSheet: (key) => set((state) => ({
     activeKey: key,
     sheets: state.sheets.map(s =>
       s.key === key ? { ...s, minimized: false } : s
     ),
   })),

   // ❌ 错误：仅更新 activeKey，minimized 未更新
   // activateSheet: (key) => set({ activeKey: key }),
   ```

2. **封装 transition 方法【强制】**：状态切换必须封装为 transition 方法（如 `activateSheet` / `closeSheet` / `minimizeSheet`），禁止分散赋值。

3. **检查方法【强制】**：每个状态变更函数，列出影响的所有字段，确认全部同步更新。

**配置驱动**：无（原则性规范）。

**适用场景**：
- 多字段状态切换（激活/关闭/最小化/最大化）
- 状态机转换（如 `pending → running → completed`）
- Zustand store 的所有操作（open/close/activate/minimize/restore）
- 后端状态机转换（如订单状态/任务状态）

**不适用场景**：
- 单字段状态（无关联字段需同步）
- 独立无关联字段（各自更新即可）

**历史教训**：`activateSheet` 仅更新 `activeKey` 未设置 `minimized: false`，sheet 激活后仍处于最小化状态，恢复按钮无响应。修复后同步更新 `minimized: false`。

**判断信号（review 触发条件）**：
- 状态切换函数仅更新部分字段
- `grep "set.*activeKey\|set.*active" <file>` 附近无相关字段同步更新


---

### step 151：CONSISTENCY-01 多源失效判定一致性原则【强制】🆕v4.29

**背景**：健康检查器依赖本地 cookie 存在性判断"会话有效"，worker 通过实际 API 调用检测 `RGV587_ERROR` 判断"会话失效"，两者标准不一，导致"健康检查显示有效但任务自动暂停"的矛盾现象。

**问题**：多个组件判断同一状态（如"会话有效性"）时使用不同判定标准，导致状态不一致与用户困惑。

**规范**：

1. **统一失效判定标准【强制】**：多个组件判断同一状态时，必须使用相同的判定标准：
   ```python
   # ✅ 正确：统一用 _check_session_valid() 判断
   def _check_session_valid(self) -> bool:
       """统一会话有效性判定：cookie 存在 + 未触发 RGV587"""
       return self._has_cookies() and not self._has_rgv587_error()

   # ❌ 错误：健康检查器用 cookie 存在性，worker 用 RGV587 检测
   # 健康检查器: return self._has_cookies()  # 标准 1
   # worker: return not self._has_rgv587_error()  # 标准 2
   ```

2. **状态变更时所有组件同步【强制】**：状态变更时，所有相关组件必须同步更新，禁止部分组件持有旧状态。

3. **统一失效判定函数【强制】**：抽取统一的失效判定函数（如 `_check_session_valid()`），所有组件调用同一函数。

**配置驱动**：无（原则性规范）。

**适用场景**：
- 多组件状态同步（健康检查器 + worker + collector）
- 跨层状态判断（前端 + 后端 + 调度器）
- 分布式状态一致性

**不适用场景**：
- 单一组件状态判断（无需统一）
- 独立无关联状态（各自判断即可）

**历史教训**：健康检查器用 cookie 存在性（返回有效），worker 用 RGV587 检测（返回失效），导致"健康检查显示有效但任务自动暂停"。修复后统一用 `_check_session_valid()` 判断。

**判断信号（review 触发条件）**：
- 两个以上组件各自独立判断同一状态
- 健康检查与实际行为不一致


---

### step 152：FALLBACK-01 缺失数据回退策略【强制】🆕v4.29

**背景**：`sync_state_from_cookies` 仅在 JSON 有对应 cookies 时更新层状态，缺浏览器内存回退，导致 JSON 缺失时层状态显示失效但功能正常（浏览器内存有数据）。

**问题**：主数据源（JSON）缺失时未从备用数据源（浏览器内存）回退同步，导致状态显示与实际功能脱节。

**规范**：

1. **主数据源缺失时从备用数据源回退【强制】**：主数据源（JSON）缺失时，必须从备用数据源（浏览器内存/缓存/DB）回退同步：
   ```python
   # ✅ 正确：JSON 缺失时从浏览器内存回退
   json_cookies = self._load_from_json()
   if not json_cookies:
       browser_cookies = await self._get_browser_cookies()
       if browser_cookies:
           self._sync_from_cookies(browser_cookies)
           self._write_back_json(browser_cookies)  # 回写主数据源

   # ❌ 错误：JSON 缺失时不回退，状态显示失效
   # if not json_cookies:
   #     return  # 状态停留在 valid=False
   ```

2. **回退同步后必须写回主数据源【强制】**：从备用数据源回退同步后，必须写回主数据源，避免下次再走回退。

**配置驱动**：无（原则性规范）。

**适用场景**：
- 多数据源场景（JSON + 浏览器内存 + DB）
- 主数据源可能缺失或过期的场景
- 状态显示与实际功能需保持一致

**不适用场景**：
- 单一数据源（无回退源）
- 强一致要求场景（应直接报错而非回退）
- 临时数据（无需持久化）

**历史教训**：`sync_state_from_cookies` 仅在 JSON 有对应 cookies 时更新，JSON 缺失时层状态显示失效但功能正常（浏览器内存有数据）。修复后增加浏览器内存回退 + 回写 JSON。

**判断信号（review 触发条件）**：
- 主数据源缺失时未尝试备用数据源
- 状态显示失效但功能正常（典型多源脱节症状）


---

### step 153：SYNC-01 多源状态同步标记机制【强制】🆕v4.29

**背景**：`auth_helper` / `browser_login` 写入 pending marker 文件，`cookie_sync_scheduler` 消费 marker 同步状态，但 `auto_sync=false` 时启动未检查 marker，导致登录后状态未同步。

**问题**：多进程/多组件状态同步依赖 marker 文件，但启动时未检查 marker，导致登录后状态未同步。

**规范**：

1. **写入方写 pending marker【强制】**：写入方（如 `auth_helper` / `browser_login`）完成状态变更后必须写 pending marker 文件：
   ```python
   # ✅ 正确：登录成功后写 pending marker
   marker_path = Path("data/pending_sync.marker")
   marker_path.write_text(json.dumps({
       "type": "login_success",
       "timestamp": time.time(),
       "cookies_count": len(cookies),
   }))
   ```

2. **消费方定期检查并同步【强制】**：消费方（如 `cookie_sync_scheduler`）必须定期检查 marker 并同步状态。

3. **启动时必须检查 pending markers【强制】**：即使 `auto_sync=false`，服务启动时也必须检查 pending markers，避免登录后状态未同步：
   ```python
   # ✅ 正确：启动时检查 pending markers
   def _on_startup():
       if _has_pending_markers():
           _sync_from_markers()  # 即使 auto_sync=false 也同步
   ```

**配置驱动**：`coding_standards.state_sync.pending_marker_dir` / `coding_standards.state_sync.check_on_startup` 在 `config.yaml` 管理。

**适用场景**：
- 多进程/多组件状态同步（主进程 + 子进程）
- 跨服务状态同步（Web + 调度器 + 浏览器）
- 登录态/Cookie 状态同步

**不适用场景**：
- 单进程同步（无需 marker）
- 实时同步（用事件总线而非 marker）

**历史教训**：`auth_helper` 登录成功后写 pending marker，但 `auto_sync=false` 时启动未检查 marker，导致登录后状态未同步。修复后启动时强制检查 pending markers。

**判断信号（review 触发条件）**：
- `grep "pending.*marker\|marker.*sync" <file>` 但启动流程未检查 marker
- `auto_sync=false` 时登录后状态未同步


---

### step 154：RACE-01 异步竞态防护原则【强制】🆕v4.29

**背景**：AI 深度检测 `onDeepAnalyze` 存在 race condition，用户切换商品时旧请求的 result/error/loading 污染新商品 UI 状态。

**问题**：异步请求完成时，未检查请求 ID 是否为最新，导致旧请求的结果污染新商品的 UI 状态（result/error/loading 三态）。

**规范**：

1. **异步请求完成时检查请求 ID【强制】**：异步请求完成时，必须检查请求 ID 是否为最新，否则丢弃结果：
   ```typescript
   // ✅ 正确：用 useRef 维护最新请求 ID，响应回来时对比
   const itemIdRef = useRef('')
   const onDeepAnalyze = async (itemId: string) => {
     itemIdRef.current = itemId
     setLoading(true)
     try {
       const result = await api.deepAnalyze(itemId)
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

2. **三态校验【强制】**：result/error/loading 三态在 setState 前必须校验 `ref.current === itemId`，不匹配则丢弃。

3. **finally 块同样校验【强制】**：finally 块同样校验，避免提前关闭新请求的 loading。

**配置驱动**：`coding_standards.race.check_request_id`（`true`/`false`，默认 `true`）在 `config.yaml` 管理。

**适用场景**：
- 搜索（用户输入防抖 + 异步查询）
- AI 分析（LLM 推理 60s+ 期间用户切换）
- 数据刷新（用户切换对象时旧请求未完成）
- 任何 > 3s 的异步请求 + 用户可触发多次切换的场景

**不适用场景**：
- 单次请求无竞态风险（如页面加载）
- 用户无法重复触发（如表单提交后禁用按钮）
- 请求顺序由用户显式控制（如分页加载）

**历史教训**：`onDeepAnalyze` 90s 期间用户切换商品，旧请求的 result/error/loading 污染新商品 UI 状态。修复后用 `useRef` 维护最新请求 ID，响应回来时对比。

**判断信号（review 触发条件）**：
- 异步请求 timeout >= 3s 但无 `useRef` 防护
- 用户可触发多次切换商品/任务/对象的异步操作


---

### step 179：RESUME-01 状态恢复前置校验原则【强制】🆕v4.31

**背景**：具有 pause/resume 语义的组件（任务调度器、登录会话、连接池、断路器）在 resume 时若不校验"导致 pause 的根因"是否消除，会形成"恢复→失效→暂停"无效循环，浪费资源并产生大量冗余告警。对应元规范 meta-rules #31，与 B-REVIEW-157（backend 调度器/任务恢复维度）+ F-REVIEW-116（frontend resume 按钮前置校验）对应。

**问题**：异常 pause 后 resume 操作无条件放行，未校验 root_cause 对应的前置条件（如 Cookie 层 valid、连接可达、配额充足）是否已恢复，导致恢复后短时间内再次触发同一失效条件，进入无效循环。

**规范**：

1. **pause 时持久化 root_cause【强制】**：异常 pause 必须将 `root_cause`（含 `reason_code` + 失效层标识 + 时间戳）持久化到任务/会话状态，而非仅记日志：
   ```python
   # ✅ 正确：异常 pause 持久化 root_cause 到任务状态
   async def pause_task(self, task_id: str, reason_code: str, failed_layer: str):
       root_cause = {
           "reason_code": reason_code,       # 如 "RGV587_SESSION_EXPIRED"
           "failed_layer": failed_layer,     # 如 "identity" / "session"
           "paused_at": time.time(),
       }
       await self.task_store.update(task_id, status="paused", root_cause=root_cause)
       logger.warning(f"Task {task_id} paused", extra=root_cause)
   ```

2. **resume 前 precheck【强制】**：resume 操作必须调用 precheck 函数校验 `root_cause` 对应的前置条件是否已恢复（如 Cookie 层 valid、连接可达、配额充足）：
   ```python
   # ✅ 正确：resume 前查 reason_precheck_map 调对应 precheck 函数
   async def resume_task(self, task_id: str):
       task = await self.task_store.get(task_id)
       root_cause = task.get("root_cause")
       # 用户主动 pause 无 root_cause，直接放行
       if not root_cause:
           return {"resume_blocked": False}

       # 冷却期检查（从 config 读，禁止硬编码）
       cooldown_seconds = config["resume_policy"]["cooldown_seconds"]
       elapsed = time.time() - root_cause["paused_at"]
       if elapsed < cooldown_seconds:
           return {
               "resume_blocked": True,
               "reason_code": root_cause["reason_code"],
               "user_hint": f"冷却期内，请 {cooldown_seconds - int(elapsed)} 秒后重试",
               "retry_after": cooldown_seconds - int(elapsed),
           }

       # precheck：根据 reason_code 查映射表调对应校验函数
       if config["resume_policy"]["precheck_enabled"]:
           precheck_fn = config["resume_policy"]["reason_precheck_map"].get(
               root_cause["reason_code"]
           )
           if precheck_fn and not precheck_fn():  # 如 cookie_rotator.is_identity_valid()
               return {
                   "resume_blocked": True,
                   "reason_code": root_cause["reason_code"],
                   "user_hint": "请先重新登录闲鱼刷新 Cookie",
                   "retry_after": None,
               }

       # precheck 通过，清除 root_cause 并恢复
       await self.task_store.update(task_id, status="running", root_cause=None)
       return {"resume_blocked": False}

   # ❌ 错误：resume 无条件放行，形成"恢复→失效→暂停"无效循环
   # async def resume_task(self, task_id):
   #     await self.task_store.update(task_id, status="running")
   #     return True
   ```

3. **结构化拒绝响应【强制】**：校验失败时必须返回 `{resume_blocked: true, reason_code, user_hint, retry_after}`，禁止静默失败或无条件放行。

4. **冷却期【强制】**：异常 pause 后设置冷却期（从 config 读取），期间拒绝 resume，避免"恢复→失效→暂停"无效循环。

5. **配置驱动【强制】**：冷却期时长、前置校验开关、`reason_code` → precheck 函数映射表均从 config 读取，禁止硬编码。

**配置驱动**：
- `coding_standards.resume_policy.cooldown_seconds`：异常 pause 后冷却期时长（秒）
- `coding_standards.resume_policy.precheck_enabled`：resume 前置校验总开关（`true`/`false`）
- `coding_standards.resume_policy.reason_precheck_map`：`reason_code` → precheck 函数路径映射表

均在 `config.yaml` 管理。

**适用场景**：
- 任务调度器 pause/resume（如搜索任务会话失效暂停后恢复）
- 登录会话失效/恢复（Cookie 层失效后重新登录）
- 连接池断连/重连
- 断路器开/闭
- 限流配额耗尽/恢复

**不适用场景**：
- 用户主动 pause（非异常触发，无 root_cause）
- 一次性任务（无 resume 语义）
- 纯函数重试（无状态持久化）
- 开发调试手动 resume

**历史教训**：搜索任务 `t68bc149b` 因闲鱼会话失效（RGV587_ERROR）被自动暂停后，用户/系统在 30 分钟内连续 4 次恢复任务，但 Cookie 未重新登录刷新，每次恢复后 13~22 秒内再次触发会话失效检测并暂停，形成"恢复→失效→暂停"无效循环，浪费浏览器资源并产生 555 条冗余 WARNING。修复：resume 前校验 `cookie_rotator` 的 identity/session 层 `valid` 状态，失效时拒绝恢复并提示"请先重新登录闲鱼"；异常 pause 后设冷却期（config 可配），彻底消除无效循环。

**判断信号（review 触发条件）**：
- `grep "def resume\|def start\|def unpause\|def activate" <file>` 缺 `precheck` / `_check_prerequisite` 调用 → 视为违规
- `grep "pause\|paused\|should_pause" <file>` 无 `root_cause` 字段赋值 → 视为违规
- resume 接口 `grep "return.*True\|return.*ok"` 无 `if not precheck` 拒绝分支 → 视为违规
- `grep "cooldown\|cool_down" <file>` 时长为字面量数字而非 config 引用 → 视为硬编码


---

### step 197：LIFECYCLE-RESOURCE-CLEANUP 长生命周期对象状态清理【强制，meta-rule #50 落地】🆕v4.36

**背景**：`scheduler.py` 的 `_resume_cooldown: dict[str, float]` 在 task 异常 pause 后写入冷却时间戳，但 DELETE API 删除 task 时未清理该字段，长期运行后字典无限增长（每个已删除 task 留一条记录）。同期 `_last_failure_reason: dict[str, str]` 和 `_task_status_cache: dict[str, dict]` 也有同样问题。对应元规范 meta-rules #50，与 B-REVIEW-180（backend 长生命周期对象状态清理审查）+ F-REVIEW-138（frontend 长生命周期 Hook cleanup 审查）对应。

**问题**：长生命周期对象（scheduler / container / registry / manager）持有 task 级或 session 级状态字典，DELETE API 删除 task 时未清理对应状态，长期运行后字典无限增长导致内存泄漏。

**规范**：

1. **状态字典识别【强制】**：长生命周期对象的 `__init__` 中所有 `dict[str, ...]` 类型字段视为状态字典，必须支持按 task_id 清理：
   ```python
   # ✅ 正确：状态字典识别 + drop_task_state 方法
   class TaskScheduler:
       def __init__(self):
           self._resume_cooldown: dict[str, float] = {}      # 状态字典
           self._last_failure_reason: dict[str, str] = {}    # 状态字典
           self._task_status_cache: dict[str, dict] = {}     # 状态字典
       
       def drop_task_state(self, task_id: str) -> None:
           """清理指定 task 的所有状态字典，DELETE API 调用"""
           try:
               self._resume_cooldown.pop(task_id, None)
               self._last_failure_reason.pop(task_id, None)
               self._task_status_cache.pop(task_id, None)
           except Exception as e:
               logger.debug("清理 task 状态失败（忽略）: {}", e)
   ```

2. **drop_task_state 方法签名【强制】**：`def drop_task_state(self, task_id: str) -> None: ...`，内部遍历所有状态字典 `pop(task_id, None)`。

3. **DELETE API 调用【强制】**：`DELETE /api/tasks/{task_id}` 和 `DELETE /api/tasks/batch` 路由必须调用 `container.scheduler.drop_task_state(task_id)`，与 DB 删除操作配对执行：
   ```python
   # ✅ 正确：DELETE API 调用 drop_task_state
   @router.delete("/{task_id}")
   async def delete_task(task_id: str):
       await task_store.delete(task_id)
       # 清理 scheduler 内存中该任务的冷却期记录，避免长期运行后字典无限增长
       try:
           container.scheduler.drop_task_state(task_id)
       except Exception as e:
           logger.debug("清理 scheduler 任务状态失败（忽略）: {}", e)
       return {"deleted": task_id}
   ```

4. **异常容错【强制】**：`drop_task_state` 内部 `pop` 操作必须 `try/except Exception: logger.debug(...)` 容错，不阻断主流程（DB 删除已成功，状态清理失败仅记日志）。

5. **配置驱动【强制】**：状态字典清单、清理策略（lazy/active）、清理触发点（DELETE API/scheduler shutdown/定期扫描）从 `config.yaml#lifecycle_resource_cleanup` 节点管理。

**配置驱动**：参数在 `config.yaml` 的 `lifecycle_resource_cleanup` 节点管理，包含 `state_dict_pattern`（状态字典识别正则 `self\._\w+: dict\[str,`）、`require_drop_method`（是否强制提供 drop_task_state 方法，默认 true）、`require_delete_api_call`（DELETE API 是否强制调用，默认 true）、`cleanup_strategy`（清理策略 lazy/active，默认 lazy）、`cleanup_triggers`（清理触发点列表，默认 `["delete_api", "scheduler_shutdown"]`）。

**适用场景**：长生命周期对象（scheduler / container / registry / manager / singleton service）；持有 `dict[str, ...]` 状态字段的组件；task 级或 session 级状态缓存；DELETE API 删除资源的场景。

**不适用场景**：短生命周期对象（请求级 / 函数级局部变量）；无状态服务（stateless）；只读缓存（never expire，如配置缓存）；测试 fixture（测试结束自动清理）。

**历史教训**：`scheduler.py` 的 `_resume_cooldown` 字典在 task 异常 pause 后写入冷却时间戳，DELETE API 删除 task 时未清理，长期运行后字典无限增长。用户反馈「服务运行 7 天后内存占用从 200MB 涨到 1.5GB」，排查发现每个已删除 task 在 3 个状态字典中各留一条记录。修复后加 `drop_task_state(task_id)` 方法 + DELETE API 调用 + try/except 容错。

**判断信号（review 触发条件）**：
- `grep "self\._\w*: dict\[str," <scheduler_file>` 命中 → 状态字典识别
- `grep "def drop_task_state" <scheduler_file>` 无匹配 → 缺清理方法
- `grep "def delete_task" <route_file>` 但无 `drop_task_state` → DELETE 未清理
- `drop_task_state` 内 `pop` 操作无 `try/except` → 清理失败可能阻断主流程


---

## step 190 MODE-VERTICAL-CHAIN-01 业务模式纵向链路一致性规范 🆕v4.37

**规范编号**：MODE-VERTICAL-CHAIN-01
**对应元规范**：meta-rule #53 业务模式纵向链路一致性
**一句话规则**：业务模式枚举必须在决策 / 事件 / 通知 / 路由 / 接口 / 状态机 6 层纵向一致传递，任一层缺失即模式退化。

### 6 层链路清单

| 层 | 实现位置 | 检查方式 |
|---|---|---|
| 决策层 | `_should_buy()` 等决策函数 | grep mode 枚举值在决策函数体内 |
| 事件层 | 业务事件 payload | grep `task_mode` 在 EVENT_PASSED 等事件 |
| 通知层 | 通知模板渲染 | grep mode 枚举值在 templates.py |
| 路由层 | 前端 Route 配置 | grep mode 在 App.tsx / router 配置 |
| 接口层 | 后端 endpoint | grep mode 在 api_*.py |
| 状态机层 | 订单 / 任务状态 | grep `pending_confirm` 等中间状态 |

### 与 #40 MULTI-FIELD-LINKED-SWITCH 的边界

| 维度 | #40 横向 | #53 纵向 |
|---|---|---|
| 视角 | 字段间联动（mode + 子过滤器） | 模式枚举全链路一致 |
| 关注点 | 优先级矩阵 / PATCH 三态 / 前端 UI 禁用 | 链路断裂检测 |
| 判断信号 | `grep "mode.*notify"` 缺优先级矩阵 | grep mode 枚举值在某层未命中 |

### 反模式

```python
# ❌ 反模式：5 层断裂
# 决策层：返回 False 不区分 mode
def _should_buy(item, mode):
    return False  # 模式无关

# 事件层：payload 缺 task_mode
event = Event(type="EVAL_PASSED", payload={"item_id": item.id})  # 缺 task_mode

# 通知层：所有 mode 渲染相同模板
def render_notification(event):
    return "评估通过"  # 无确认链接

# 路由层：无 /confirm-buy 路由
# 接口层：无确认 endpoint
# 状态机层：无 pending_confirm 中间状态
```

### 判断信号

- `grep "task_mode\|mode.*AUTO\|mode.*MANUAL"` 在事件 payload / 通知模板 / 路由 / endpoint 中未命中 → 链路断裂
- 决策函数返回值与 mode 无关 → 决策层未实现
- 通知模板对所有 mode 渲染相同内容 → 通知层未实现

### 配置节点

`config.yaml` 的 `mode_vertical_chain` 节点：
- `enabled`：开关
- `required_layers`：必需层列表（默认 `["decision", "event", "notification", "router", "endpoint", "state_machine"]`）
- `optional_layers`：可选层列表（默认 `[]`）
- `mode_field_names`：mode 字段名列表（默认 `["task_mode", "execution_mode", "notification_mode"]`）

### 适用

- 任务执行模式（AUTO / SEMI_AUTO / MANUAL）
- 通知模式（IMMEDIATE / BATCHED / DIGEST）
- 采集模式（CRON / INTERVAL / ONESHOT）
- 任何引入 mode 枚举且影响后续行为的业务

### 不适用

- 纯展示型 mode 字段（仅日志记录不影响流转）
- 内部状态字段（不跨层传递）
- 单一布尔开关（无枚举语义，归 #40）




---

### step 229：多级自愈模式规范【强制】🆕v4.47

**背景**：`_refresh_token_and_retry_detail`（`collection_service.py`）只刷新 `_m_h5_tk` 不重注入完整 cookie，导致"token 刷新成功但会话未恢复"，刚登录成功就检测出会话失效。根因是把"token 刷新"等同于"会话恢复"，忽略了 cookie 重注入这一关键环节。

**问题**：会话失效自愈只做单点刷新（token 刷新），不重注入完整 cookie 到运行时载体（浏览器/httpx），导致自愈链路断裂。

**规范**：

1. **多级自愈链路【强制】**：会话失效自愈必须实现多级链路（token 刷新 → cookie 重注入 → 放弃），单级刷新成功不等于会话恢复：
   - **第一级（Token 刷新）**：调用 `token_renewer.refresh()`，刷新 `_m_h5_tk` 等临时 token
   - **第二级（Cookie 重注入）**：token 刷新成功后，从 CookieStore 读取完整 cookie 并强制注入到运行时载体（浏览器/httpx），调用 `inject_cookie_store_to_worker_browser()`
   - **第三级（放弃）**：两级都失败时，标记会话失效（`last_session_invalid=True`），等待用户/系统重新登录，**禁止**无限重试

2. **自愈链路日志【强制】**：自愈链路每级失败都必须记日志，含上下文（cookie 数量、层状态、刷新结果、注入结果），调用 `_log_cookie_diagnostics(tag, context)` 集中记录

3. **自愈链路配置化【强制】**：层级数、每级动作、失败后是否进入下一级，全部从 `config.yaml` 读取，**禁止**硬编码在代码中

**判断信号**：
- `grep "refresh_token_and_retry" src/` 找到自愈函数 → 检查是否有 cookie 重注入步骤
- `grep "_m_h5_tk" src/` 找到 token 刷新逻辑 → 检查刷新后是否调用 `inject_cookie_store_to_worker_browser()`
- 自愈函数只调用 `token_renewer.refresh()` 无后续重注入 → 视为违规

**修复模式**：
```python
# ✅ 多级自愈：token 刷新 → cookie 重注入 → 放弃
async def _refresh_token_and_retry_detail(self, item_id: str, ...):
    # 第一级：token 刷新
    refresh_ok = await self.token_renewer.refresh()
    if not refresh_ok:
        self._log_cookie_diagnostics("token_refresh_failed", {"item_id": item_id})
        self.last_session_invalid = True
        return None

    # 第二级：cookie 重注入（关键步骤，不能省略）
    inject_ok = await inject_cookie_store_to_worker_browser(self.browser, self.cookie_store)
    if not inject_ok:
        self._log_cookie_diagnostics("cookie_inject_failed", {"item_id": item_id})
        self.last_session_invalid = True
        return None

    # 两级都成功，重置熔断标志，重试业务
    self.last_session_invalid = False
    return await self.detail(item_id)

# ❌ 反模式：只刷新 token 不重注入 cookie
async def _refresh_token_and_retry_detail(self, item_id: str, ...):
    await self.token_renewer.refresh()  # 刷新后直接重试，cookie 未重注入
    return await self.detail(item_id)   # 重试时浏览器内存仍是旧 cookie
```

**配置参数**：`multi_level_self_heal.enabled`（默认 `true`，是否启用多级自愈）、`multi_level_self_heal.levels`（默认 `['token_refresh', 'cookie_inject', 'give_up']`，自愈层级列表）、`multi_level_self_heal.level_actions`（每级动作函数名映射）、`multi_level_self_heal.fail_through_to_next`（默认 `true`，某级失败是否进入下一级）、`multi_level_self_heal.max_retry_count`（默认 `1`，最大重试次数）、`multi_level_self_heal.diagnostic_log_function`（默认 `_log_cookie_diagnostics`，诊断日志函数名）在 `config.yaml` 的 `multi_level_self_heal` 节点管理

**适用场景**：会话失效自愈（token + cookie）、多级降级链、需要"刷新 + 重注入"的场景、任何"单点刷新不等于恢复"的系统

**不适用场景**：单点刷新即可恢复的场景（如纯 token 续期，无运行时载体）、无运行时载体的纯文件存储、一次性操作无重试逻辑

**历史教训**：`_refresh_token_and_retry_detail`（`collection_service.py`）只调用 `token_renewer.refresh()` 刷新 `_m_h5_tk`，不重注入完整 cookie 到 worker 浏览器。token 刷新成功后立即重试 `detail()`，但浏览器内存仍持有旧 cookie，导致"刚登录成功就检测出会话失效"。改为两级自愈（token 刷新 + cookie 强制注入）后彻底解决。详细复盘参见 [cookie-state-recovery-patterns.md](../../../references/cookie-state-recovery-patterns.md) v3 流程 G。


---

### step 230：熔断标志与自动重试协调规范【强制】🆕v4.47

**背景**：`_refresh_token_and_retry_detail`（`collection_service.py`）重试前未重置 `last_session_invalid` 熔断标志，而 `detail()` 入口检查该标志直接短路返回 `None`，导致重试形同虚设——"假重试"比"不重试"更危险，因为日志显示已重试但实际从未执行。

**问题**：有熔断标志 + 自动重试逻辑时，重试前不重置标志，标志残留导致重试被短路，重试逻辑形同虚设。

**规范**：

1. **重试前显式重置熔断标志【强制】**：自动重试逻辑开始前，必须显式重置熔断标志（`last_session_invalid=False`），**禁止**依赖标志自然失效或隐式重置：
   - 识别所有"会阻断重试"的标志字段（`last_session_invalid`、`is_paused`、`circuit_broken`）
   - 重试前显式赋值重置（`self.last_session_invalid = False`）
   - 重试失败时标志由业务逻辑置位，**禁止**手动回置（避免与业务逻辑重复）

2. **日志区分路径【强制】**：日志必须区分"已重置标志并重试"与"标志未重置跳过重试"两种路径：
   - 重置后重试：`logger.info("已重置 last_session_invalid=False，开始重试")`
   - 跳过重试：`logger.debug("标志未重置，跳过重试")`
   - **禁止**两种路径共用同一日志文案（排查误导）

3. **标志重置配置化【强制】**：熔断标志清单、重置时机、日志文案模板，全部从 `config.yaml` 读取，**禁止**硬编码在代码中

**判断信号**：
- `grep "def.*retry" src/` 找到重试函数 → 检查重试前是否重置熔断标志
- `grep "last_session_invalid" src/` 找到熔断标志 → 检查所有读取点的上游是否有重置逻辑
- 重试函数内无 `last_session_invalid = False` 赋值 → 视为违规
- 日志含"已刷新"但无法区分"已重置标志"与"跳过" → 视为违规

**修复模式**：
```python
# ✅ 重试前显式重置熔断标志，日志区分路径
async def _refresh_token_and_retry_detail(self, item_id: str, ...):
    # 重试前重置熔断标志（关键步骤，不能省略）
    if self.last_session_invalid:
        self.last_session_invalid = False
        logger.info("已重置 last_session_invalid=False，开始重试 item=%s", item_id)
    else:
        logger.debug("标志未重置，直接重试 item=%s", item_id)

    refresh_ok = await self.token_renewer.refresh()
    if refresh_ok:
        logger.info("token 已刷新，重试业务")  # 明确"已刷新"
    else:
        logger.debug("跳过刷新（无需刷新），重试业务")  # 明确"跳过"
        # ❌ 反模式：这里写 logger.info("token 已刷新") 就是误导

    return await self.detail(item_id)

# ❌ 反模式：重试前不重置标志，重试被短路
async def _refresh_token_and_retry_detail(self, item_id: str, ...):
    await self.token_renewer.refresh()
    return await self.detail(item_id)  # detail() 入口检查 last_session_invalid=True，直接返回 None
```

**配置参数**：`circuit_flag_retry_coord.enabled`（默认 `true`，是否启用协调）、`circuit_flag_retry_coord.flag_fields`（默认 `['last_session_invalid', 'is_paused', 'circuit_broken']`，熔断标志字段清单）、`circuit_flag_retry_coord.reset_before_retry`（默认 `true`，重试前是否重置）、`circuit_flag_retry_coord.log_templates`（日志文案模板，含 `reset_and_retry` / `skip_retry` / `refreshed` / `skipped_refresh`）、`circuit_flag_retry_coord.reset_value`（默认 `False`，重置后的值）在 `config.yaml` 的 `circuit_flag_retry_coord` 节点管理

**适用场景**：有熔断标志 + 自动重试的系统（会话失效、断路器、连接池）、重试可能被标志短路的场景、任何"标志生命周期与重试逻辑需协调"的组合

**不适用场景**：无熔断标志的简单重试、一次性操作无重试逻辑、纯客户端重试（无服务端标志）、无标志检查的直通重试

**历史教训**：`_refresh_token_and_retry_detail`（`collection_service.py`）重试前未重置 `last_session_invalid`，而 `detail()` 入口检查 `if self.last_session_invalid: return None`，导致重试被短路。日志显示"已刷新 token 并重试"，但实际 `detail()` 从未执行——"假重试"持续数小时未被发现。改为重试前显式重置标志 + 日志区分路径后彻底解决。详细复盘参见 [cookie-state-recovery-patterns.md](../../../references/cookie-state-recovery-patterns.md) v3 流程 H。


---

### step 243：Cookie-Token 一致性保障规范【强制】🆕v4.51

**规范编号**：COOKIE-TOKEN-CONSISTENCY-01
**对应元规范**：meta-rule #84 Cookie-Token 状态分离与一致性保障

**背景**：Worker 浏览器实例在登录前已启动，会自动生成匿名 `_m_h5_tk` token。登录通过独立进程（LoginOrchestrator / browser-login 子进程）完成后，身份 Cookie 写入了 JSON/SQLite 但未同步到 Worker 浏览器内存。即使后续通过补注入将身份 Cookie 注入浏览器内存，匿名 token 仍残留在内存中，与身份 Cookie 不匹配，导致 MTOP API 签名验证失败（`FAIL_SYS_ILLEGAL_ACCESS::非法请求`）。

**问题**：多进程共享浏览器实例时，身份 Cookie 与签名 token 的生命周期不同步——Cookie 可通过 JSON 补注入同步，但 token 是浏览器启动时生成的匿名值，不会随 Cookie 一起更新，导致"Cookie 有效但 token 不匹配"的隐蔽状态。

**规范**：

1. **身份 Cookie 检查与补注入【强制】**：实时搜索等关键端点入口必须检查浏览器是否持有完整身份 Cookie，缺失时从 CookieStore JSON 补注入：
   - 检查 `cookie2` / `sgcookie` / `unb` 等身份 Cookie 是否在浏览器内存中
   - 缺失时从 `data/cookies.json` 读取并通过 `context.add_cookies()` 注入
   - 补注入后重新检查，仍缺失则报 401 引导用户重新登录

2. **Token 强制重置独立于 Cookie 补注入【强制】**：**无论是否执行了 Cookie 补注入**，都必须重置 token 刷新时间戳（`_last_m5tk_refresh = 0.0`），强制下次搜索时刷新 token：
   - **禁止**将 token 重置逻辑绑定在"补注入 Cookie"分支内——浏览器可能已持有身份 Cookie（无需补注入），但匿名 token 仍残留
   - token 一致性问题是**独立于** Cookie 补注入的问题，两者不能耦合
   - 重置 token 只增加 ~1.5s 延迟（导航刷新），且实时搜索有缓存窗口，性能影响可接受

3. **补注入域过滤【强制】**：从 CookieStore JSON 补注入时，必须按域过滤，**禁止**注入无关域的 Cookie：
   - 只注入 `goofish.com` / `taobao.com` 等业务域
   - 避免注入第三方分析/广告域 Cookie 污染浏览器状态

4. **配置化【强制】**：身份 Cookie 白名单、补注入域列表、token 刷新时间戳字段名、重置值，全部从 `config.yaml` 读取，**禁止**硬编码

**判断信号**：
- `grep "_ensure_live_search_cookies\|_ensure.*cookies" src/` 找到 Cookie 检查函数 → 检查是否有 token 重置逻辑
- `grep "_last_m5tk_refresh" src/` 找到 token 时间戳 → 检查重置逻辑是否在补注入分支**外部**
- token 重置逻辑在 `if missing:` 分支内 → 视为违规（耦合了 Cookie 补注入与 token 重置）
- `grep "add_cookies" src/` 找到补注入逻辑 → 检查是否按域过滤

**修复模式**：
```python
# ✅ Cookie 检查 + 补注入 + token 重置（token 重置在补注入分支外部）
async def _ensure_live_search_cookies(container: Container) -> None:
    """检查浏览器是否持有有效身份 Cookie，无效时补注入，并强制重置 token"""
    if not container.browser:
        return

    # 第一步：检查身份 Cookie 是否完整
    missing = await _get_missing_identity_cookies(container)
    if missing:
        # 第二步：从 CookieStore JSON 补注入（按域过滤）
        await _inject_cookies_from_store(container, missing)
        # 重新检查，仍缺失则报 401
        missing = await _get_missing_identity_cookies(container)
        if missing:
            raise HTTPException(401, f"Cookie 不完整（缺少 {missing}），请重新登录")

    # 第三步：无论是否补注入，都重置 token 刷新时间戳
    # 为什么独立于补注入：浏览器可能已持有身份 Cookie，但匿名 token 仍残留
    if container.collector:
        container.collector._last_m5tk_refresh = 0.0
        logger.info("已重置 _m_h5_tk 刷新时间戳，下次搜索将强制刷新 token")

# ❌ 反模式：token 重置绑定在补注入分支内
async def _ensure_live_search_cookies(container: Container) -> None:
    missing = await _get_missing_identity_cookies(container)
    if missing:
        await _inject_cookies_from_store(container, missing)
        # token 重置在这里 → Cookie 完整时不执行 → 匿名 token 残留
        container.collector._last_m5tk_refresh = 0.0
    # Cookie 完整时直接返回，token 仍是匿名值 → FAIL_SYS_ILLEGAL_ACCESS
```

**配置参数**：`cookie_token_consistency.enabled`（默认 `true`）、`cookie_token_consistency.identity_cookies`（默认 `['unb', 'cookie2', 'sgcookie', '_tb_token_', 't']`，身份 Cookie 白名单）、`cookie_token_consistency.inject_domains`（默认 `['goofish.com', 'taobao.com']`，补注入域过滤列表）、`cookie_token_consistency.token_refresh_field`（默认 `_last_m5tk_refresh`，token 刷新时间戳字段名）、`cookie_token_consistency.token_reset_value`（默认 `0.0`，重置值）、`cookie_token_consistency.incomplete_status_code`（默认 `401`，Cookie 不完整时的 HTTP 状态码）在 `config.yaml` 的 `cookie_token_consistency` 节点管理

**适用场景**：多进程共享浏览器实例（Worker 浏览器 + 登录子进程）、token 与身份 Cookie 分离管理的认证体系（如 MTOP API 的 `_m_h5_tk`）、浏览器在登录前启动的场景

**不适用场景**：单进程内完成登录和请求（token 随 Cookie 一起更新）、无 token 机制的纯 Cookie 认证、无浏览器实例的纯 API 调用

**历史教训**：用户使用浏览器登录后，反爬健康检查 Cookie 有效，但点击实时搜索时后台报 `FAIL_SYS_ILLEGAL_ACCESS::非法请求`。根因：Worker 浏览器启动时生成的匿名 `_m_h5_tk` token 残留内存，登录后身份 Cookie 注入但 token 未刷新。第一次修复将 token 重置绑定在"补注入 Cookie"分支内，但用户浏览器已持有身份 Cookie（无需补注入），重置逻辑未执行。改为"无论是否补注入都重置"后解决。


---

### step 244：续期闭环完整性规范【强制】🆕v4.51

**规范编号**：RENEWAL-LOOP-COMPLETENESS-01
**对应元规范**：meta-rule #84 Cookie-Token 状态分离与一致性保障

**背景**：TokenRenewer 每 2 分钟检查 token 有效期，过期前 10 分钟触发续期回调（`_default_renew_callback`）。续期回调通过导航到 `h5.m.taobao.com` 触发服务端刷新 token，但只返回 `True` 表示续期成功，未提取导航后的完整 Cookie 回写 CookieStore JSON。导致 `data/cookies.json` 中的 `_m_h5_tk` 永远是登录时的旧值，健康检查误判 token 过期、实时搜索从 JSON 补注入旧 token。

**问题**：续期回调只更新了浏览器内存中的 token，未同步到持久化存储（JSON/SQLite），导致"内存中 token 已刷新但 JSON 中仍是旧值"的状态分裂。

**规范**：

1. **续期后回写存储【强制】**：续期回调导航刷新 token 成功后，必须提取完整 Cookie 并回写 CookieStore JSON + SQLite：
   - 导航成功后调用 `browser.get_cookies(domains)` 提取指定域的完整 Cookie
   - 调用 `cookie_store.export_cookies(cookies, method="renew")` 回写 JSON + SQLite
   - 回写形成完整闭环：登录（全量写入）→ 续期（增量同步）→ 失效重新登录

2. **回写域过滤【强制】**：回写时必须按域过滤，**禁止**写入无关域 Cookie：
   - 只提取 `goofish.com` / `taobao.com` 等业务域
   - 避免写入第三方分析/广告域 Cookie 污染 CookieStore

3. **回写失败不阻断续期【强制】**：回写失败时只记 `logger.warning`，**不**返回 `False`：
   - token 已在浏览器内存中刷新成功，回写失败不影响当前会话
   - 回写失败的影响是"下次从 JSON 补注入时拿到旧值"，而非"当前会话失效"
   - 返回 `False` 会触发 `on_renew_fail` 回调，导致不必要的重新登录

4. **回写方法标记【强制】**：`export_cookies` 调用时必须传 `method` 参数标记来源（如 `"renew"` / `"login"` / `"import"`），便于审计与排查

5. **配置化【强制】**：续期导航 URL、回写域列表、回写方法标记、回写失败日志级别，全部从 `config.yaml` 读取

**判断信号**：
- `grep "_default_renew_callback\|renew_callback" src/` 找到续期回调 → 检查导航后是否回写 CookieStore
- `grep "export_cookies" src/` 找到回写调用 → 检查是否在续期回调中调用
- 续期回调只 `return True` 无 `export_cookies` 调用 → 视为违规
- `data/cookies.json` 中 `_m_h5_tk` 值长期不变但健康检查报 token 有效 → 回写闭环断裂

**修复模式**：
```python
# ✅ 续期回调：导航刷新 → 提取 Cookie → 回写存储
async def _default_renew_callback(self) -> bool:
    page = None
    try:
        container = get_container()
        if not container.browser or not container.browser._context:
            return False
        page = await container.browser.new_page()
        try:
            await page.goto(RENEWAL_NAV_URL, wait_until="domcontentloaded", timeout=RENEWAL_TIMEOUT)
        finally:
            await page.close()

        # 导航成功后提取完整 Cookie 回写 CookieStore
        try:
            cookies = await container.browser.get_cookies(RENEWAL_EXPORT_DOMAINS)
            if cookies:
                get_cookie_store().export_cookies(cookies, method=RENEWAL_METHOD_TAG)
                logger.debug("token 续期后已同步 {} 个 cookie 到 CookieStore", len(cookies))
        except Exception as e:
            # 回写失败不阻断续期（token 已在浏览器内存中刷新）
            logger.warning("token 续期后回写 CookieStore 失败: {}", e)
        return True
    except Exception as e:
        logger.debug("默认 token 续期回调失败: {}", e)
        return False

# ❌ 反模式：续期后不回写存储
async def _default_renew_callback(self) -> bool:
    page = await container.browser.new_page()
    await page.goto("https://h5.m.taobao.com/")
    await page.close()
    return True  # 未回写 → JSON 中 token 永远是旧值
```

**配置参数**：`renewal_loop_completeness.enabled`（默认 `true`）、`renewal_loop_completeness.nav_url`（默认 `https://h5.m.taobao.com/`，续期导航 URL）、`renewal_loop_completeness.nav_timeout_ms`（默认 `10000`，导航超时毫秒）、`renewal_loop_completeness.export_domains`（默认 `['goofish.com', 'taobao.com']`，回写域过滤列表）、`renewal_loop_completeness.method_tag`（默认 `renew`，回写方法标记）、`renewal_loop_completeness.writeback_failure_level`（默认 `warning`，回写失败日志级别）、`renewal_loop_completeness.writeback_failure_blocks_renewal`（默认 `false`，回写失败是否阻断续期）在 `config.yaml` 的 `renewal_loop_completeness` 节点管理

**适用场景**：所有需要续期回调的认证机制（OAuth token 续期、session 续期、MTOP token 续期）、多存储介质同步（浏览器内存 + JSON + SQLite）、续期回调通过浏览器导航触发服务端刷新的场景

**不适用场景**：单存储介质的 token 续期（无 JSON/SQLite 同步需求）、无续期机制的认证（每次请求都重新登录）、纯 API token 续期（不通过浏览器导航）

**历史教训**：TokenRenewer 的 `_default_renew_callback` 导航刷新 token 后只返回 `True`，未回写 CookieStore JSON。`data/cookies.json` 中的 `_m_h5_tk` 永远是登录时的旧值，健康检查误判 token 过期，实时搜索从 JSON 补注入旧 token 导致 `FAIL_SYS_ILLEGAL_ACCESS`。改为续期后提取完整 Cookie 回写 JSON + SQLite 后形成完整闭环。


---

### step 245：状态机返回值语义校验规范（STATE-MACHINE-RETURN-01，meta-rule #109 落地）【强制】🆕v4.62.0

**背景**：`scheduler.py` 的 `_run_loop` 函数在会话失效（should_pause=True）时通过 `return True` 导致主循环 break，后续 resume API 调用 `pause_event.set()` 时无循环等待该 event，造成任务永久卡死。

**规范**：

1. **状态机中 return 值的语义必须与调用方逻辑对齐【强制】**——return True/False 的语义必须在注释中明确说明（True=继续/完成 vs True=需要 break）

2. **pause/resume/idle 语义一致性校验【强制】**——每个状态转换的前置/后置条件必须文档化

3. **异常路径的恢复机制必须验证【强制】**——pause 后 resume 是否能正确恢复到运行状态

4. **关键状态转换需添加不变量断言【推荐】**

**判断信号**：
- `grep "return True\|return False" <py>` 在状态机循环中 → 检查调用方如何使用返回值
- `grep "break\|continue" <py>` 在 while 循环中受 return 值影响 → 检查语义对齐
- 任务/会话在 pause 后无法 resume → 典型症状

**配置参数**：`state_machine_return.returnSemanticsDocument`（默认 `true`，是否要求 return 语义文档化）、`state_machine_return.pauseResumeVerify`（默认 `true`，是否要求 pause/resume 恢复验证）在 `config.yaml` 的 `state_machine_return` 节点管理

**适用**：scheduler 任务生命周期、session 登录状态、工作流引擎、订单状态流转

**不适用**：简单布尔开关、一次性操作（无状态流转）、纯函数（无状态）

**历史教训**：`scheduler.py` 的 `_run_loop` 在 should_pause 时 `return True`，调用方用 `if result: break` 退出循环。但 resume 时 `pause_event.set()` 无循环等待该 event，任务永久卡死。修复：should_pause 时 `return False`（不 break），在循环顶部检查 `pause_event` 状态
