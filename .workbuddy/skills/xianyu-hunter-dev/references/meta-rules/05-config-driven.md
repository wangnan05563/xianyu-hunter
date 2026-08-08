# 配置驱动与验证
> 包含元规范 #16 - #104

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
