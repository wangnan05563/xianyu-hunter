# Config Driven 编码规范
> 本文件归档 xianyu-hunter-dev skill 中与「config driven」主题相关的编码规范。
> 主索引见 [SKILL.md](../../../SKILL.md) 的"step 索引表"，元规范见 [meta-rules.md](../../../references/meta-rules.md)。

---

### step 15：动态资源映射分离【强制】🆕v4.0

15. **动态资源映射分离【强制】🆕v4.0**
    - 映射表（`Record<string, string>`）与推断函数必须分离，不混合
    - 推断函数返回 `null` 表示无匹配（如本地模式无需 API Key）
    - 调用方根据返回值条件渲染，不在推断函数内渲染 JSX
    - 业务参数（URL、阈值、间隔）通过配置文件管理，不硬编码在技能/组件中
    - **适用**：根据配置值推断资源（如 base_url → 申请链接）；**不适用**：硬编码常量


---

### step 17：字段覆盖策略（数据合并）【强制】🆕v4.0

17. **字段覆盖策略（数据合并）【强制】🆕v4.0**
    - 数据采集合并（如爬虫数据覆盖历史快照）时，按字段语义分类覆盖策略，**不能一刀切**
    - 基本信息字段（title/url/region/brand/seller_id/publish_time）：新值非空则覆盖
    - 数值类字段（price/want_cnt/view_cnt）：新值 > 0 才覆盖（防止 0 覆盖有效值）
    - 状态类字段（is_sold）：始终覆盖（状态时效性最高）
    - 标识类字段（seller_nick）：只填缺失（稳定性高，无需频繁更新）
    - **适用**：数据采集合并、缓存更新；**不适用**：审计日志（需保留全量历史）


---

### step 18：幂等性设计【强制】🆕v4.0

18. **幂等性设计【强制】🆕v4.0**
    - 资源创建接口（如 `session/start`、`task/create`）必须幂等
    - 重复调用返回当前状态 + `already_active` 标志，不重复创建资源
    - 网络重试场景必须设计幂等键或状态检查
    - **适用**：资源创建接口、网络重试；**不适用**：纯查询接口（天然幂等）、计数器递增（需去重键）


---

### step 19：搜索接口标准化【强制】🆕v4.0 / v4.64.0 配置驱动升级

19. **搜索接口标准化【强制】🆕v4.0 / v4.64.0 配置驱动升级**
    - 实时搜索接口统一参数命名：`keyword`/`q`、`page`/`offset`、`page_size`/`limit`
    - 统一响应结构：`{ items, total, page, page_size }`
    - 统一防抖间隔（搜索场景默认 400ms，通过配置管理）
    - `requestId` 竞态保护：每次请求生成 requestId，丢弃过期响应
    - **适用**：实时搜索（用户输入 + 防抖 + 流式/分页）；**不适用**：主键精确查询、固定条件列表
    - **🆕v4.64.0 配置驱动升级（SearchService 模板方法）**：搜索接口的模板方法 4 钩子名称、慢查询阈值、响应字段、防抖间隔等参数必须通过 `config/tech-stack.json#hardConstraints.searchServiceTemplate` 节点管理，禁止在业务代码中硬编码：
      - `baseClassFile`：基类文件路径（`src/xianyu_hunter/web/services/search_base.py`）
      - `hooks`：4 个钩子名称列表（`_build_query` / `_execute` / `_extract_facets` / `_paginate`）
      - `slowQueryThresholdMs`：慢查询阈值（100ms 记 info）
      - `verySlowQueryThresholdMs`：极慢查询阈值（1000ms 记 warning）
      - `responseFields`：响应字段列表（`items` / `total` / `matched_facets` / `query_meta`）
      - `defaultDebounceMs`：前端防抖间隔（400ms，与 Alpine `@input.debounce.400ms` 对齐）
      - `defaultLimit`：默认分页大小（50）
      - `minInterfacesToExtract`：触发基类抽取的接口数阈值（≥2 个搜索接口时必须抽取）
    - **🆕v4.64.0 判断信号**：`grep "search_base\.SearchService" src/` 命中数 < 项目内搜索接口数 → 视为可疑（未抽取基类）；`grep "100\b\|1000\b" search_*.py` 出现硬编码阈值 → 视为违规
    - **🆕v4.64.0 配置同步要求**：`tech-stack.json#hardConstraints.searchServiceTemplate` 节点变更时，必须同步更新 `xianyu-backend-code-review` 的 B-REVIEW-324~326（搜索服务模板方法审查）与 `xianyu-frontend-code-review` 的 F-REVIEW-236~238（useSearch Hook 审查）配置节点


---

### step 34：配置驱动功能开关模式【强制】🆕v4.4

34. **配置驱动功能开关模式【强制】🆕v4.4**
    - 高风险/高资源消耗功能默认关闭，需用户显式启用；所有功能参数集中在 `Config` 类（如 `BrowserConfig`），不硬编码
    - **判断信号**：功能需用户主动选择 + 可能耗资源（CPU/内存/网络） + 多环境部署需求
    - **修复模式**：`Config` 类新增 `enable_flag: bool = False` + 详细参数字段 → `config.yaml` 暴露开关 → 文档明确启用条件与资源消耗
    - **配置参数**：`enable_flag` 默认 `false`，详细参数（interval/threshold/port）集中在相应 `Config` 类
    - **适用**：CDP 在线导入、Cookie 自动同步、向量库重建等高风险/高资源消耗功能
    - **不适用**：核心功能（必须默认启用）、性能敏感场景（配置加载延迟不可接受）、简单脚本工具
    - **历史教训**：`auto_sync` 默认 `false`，避免用户不知情下启用自动同步导致浏览器资源被占用；`cdp_port` 通过 `BrowserConfig` 管理而非硬编码


---

### step 40：配置全链路生效验证【强制】🆕v4.5

40. **配置全链路生效验证【强制】🆕v4.5**
    - 配置项从定义到消费必须全链路追踪，**禁止**只注入到中间层就认为生效
    - **判断信号**：`config.yaml` 新增字段 → Config 类有字段 → TaskConfig 注入 → 但 Worker/Module/方法参数中从未读取 `self.config.xxx` → 配置无效
    - **检查方法**：grep 每个配置项的字段名，确认从定义到最终消费点（URL 构建方法、SQL 查询、阈值比较）都有读取代码
    - **适用**：所有配置项（搜索参数、阈值、间隔、开关），尤其是新增配置项后
    - **不适用**：编译期常量、安全固定值（如 `path: "/"`）
    - **历史教训**：`search_sort_type` 和 `search_regions` 在 `startup.py` 注入到 TaskConfig，但 `worker.py` 和 `_search.py` 从未读取 `self.config.search_sort_type`，`build_search_url` 也不支持 sort_type 参数。用户在配置页设置了排序方式但搜索 URL 中从不包含 `&sortType=...` 参数


---

### step 42：硬编码阈值禁用【强制】🆕v4.5

42. **硬编码阈值禁用【强制】🆕v4.5**
    - 调度器/任务循环中的阈值参数必须从配置读取，**禁止**用硬编码常量替代已有配置项
    - **判断信号**：代码中存在 `MAX_XXX = N` 硬编码常量，且 `config.yaml` 中已有对应的配置项 → 必须改为读取配置
    - **修复模式**：`try: from infra.yaml_config import get_config; threshold = get_config().<section>.<field> except: threshold = <default>`
    - **适用**：所有业务阈值（失败重试次数、超时时间、间隔时间、并发数），尤其是已有对应配置项的场景
    - **不适用**：语言/框架级常量（如 HTTP 200）、数学常量、协议固定值
    - **历史教训**：Scheduler 用硬编码 `MAX_CONSECUTIVE_ERRORS = 10` 控制连续失败暂停，但 `config.yaml` 的 `antidetect.fail_pause_threshold = 3`。用户设置了失败 3 次后暂停，实际要失败 10 次才暂停


---

### step 69：配置项边界值校验【强制】🆕v4.12

69. **配置项边界值校验【强制】🆕v4.12**
    - 数值型配置项必须有边界值校验（min/max/non_zero/range），加载时主动校验，无效值用默认值并 `logger.warning` 告警，**禁止**直接使用未校验的数值导致运行时 ZeroDivisionError / ValueError
    - **判断信号**：`config.yaml` 新增数值字段 + 代码用 `interval / N` 或 `count * factor` 等算术运算 → 必须校验除数非零、乘数有界
    - **修复模式**：
      ```python
      # ✅ 加载时校验 + 默认值兜底
      interval = config.get("ai_suggestion_interval", 60)
      if not isinstance(interval, (int, float)) or interval <= 0:
          logger.warning("ai_suggestion_interval 配置无效（{}），使用默认值 60", interval)
          interval = 60
      # 使用 interval 做算术运算前已校验非零
      ```
    - **配置参数**：`config_validation.rules`（每条规则含 `field`/`min`/`max`/`non_zero`/`regex`/`default`）、`config_validation.on_invalid`（默认 `warn_and_fallback`，可选 `raise`）在 `config.yaml` 的 `config_validation` 节点管理
    - **适用**：所有数值型配置项（间隔时间/阈值/并发数/超时/重试次数）；字符串枚举值（用 regex 校验）
    - **不适用**：布尔型配置项（无需校验范围）；纯展示型字符串（如标题）
    - **历史教训**：`ai_suggestion_interval=0` 未校验直接用于 `asyncio.sleep(interval / 2)` 导致 ZeroDivisionError，任务循环崩溃


---

### step 90：配置驱动原则强化【强制】🆕v4.15

90. **配置驱动原则强化【强制】🆕v4.15**
    - 所有新增编码规范必须强调配置驱动，参数在 `config.yaml` 的对应节点管理，不硬编码。新增检查点必须包含适用/不适用场景说明，确保通用性。配置节点命名遵循 `snake_case`，层级结构清晰，避免扁平化命名冲突
    - **判断信号**：新增编码规范含硬编码参数 → 必须改为配置驱动；新增检查点无适用/不适用场景说明 → 必须补充；配置节点命名不规范 → 必须改为 snake_case
    - **修复模式**：
      1. 检查新增规范：是否有硬编码参数（如阈值、超时时间、列表）
      2. 提取配置节点：`config.yaml` 中新增对应节点（如 `browser.route_block`、`cookie_layers.signal_layer_mapping`）
      3. 补充场景说明：适用/不适用场景列表，确保通用性
      4. 验证：配置节点可被代码读取，场景说明覆盖典型用例
    - **配置参数**：`config_driven.required_for_new_rules`（默认 `true`，新增规范必须配置驱动）、`config_driven.scenario_description_required`（默认 `true`，新增检查点必须包含场景说明）、`config_driven.node_naming_style`（默认 `snake_case`）在 `config.yaml` 的 `config_driven` 节点管理
    - **适用**：所有新增编码规范、新增审查检查点、配置节点设计
    - **不适用**：语言/框架级常量（无业务意义）、协议固定值（不可配置）
    - **历史教训**：v4.14 新增规范部分参数仍硬编码，导致不同环境需改代码而非改配置；新增检查点无适用场景说明，审查时误用于不适用场景


---

### step 98：元数据单源管理与跨端显示对齐规范【强制】🆕v4.18

**背景**：版本管理菜单持续显示 "V10"，根因是前端 VersionManager 调用 `/api/config/version`（实际返回 `len(backups)`）当作版本号使用；同时后端 `export_config` 中残留占位符 `"version": "1.0"`。该问题暴露了元数据多源读取、占位符回填、前端"语义错位 API 调用"三类反模式同时存在时极难排查的现象。

**规范**：

1. **元数据必须有唯一源头**（Single Source of Truth）
   - 版本号、构建时间、git_sha 等构建期元数据必须指定唯一源头文件（如 `src/xianyu_hunter/__init__.py` 的 `__version__`）
   - 自动生成文件（如 `_build_info.py`）由 `scripts/build_info.py` 维护，**禁止**手动编辑
   - 所有读取点优先读源头，失败时回退到生成文件，最后回退到 `'unknown'`
   - **禁止**在生产代码路径出现占位符字面量（如 `'1.0'`/`'0.0.0'`/`'unknown version'`），占位符仅限测试 fixture

2. **多端点读取同一元数据必须封装 `_safe_xxx()` 辅助函数**
   - 函数名以 `_safe_` 前缀，表示"安全读取，失败回退"
   - 三层 try/except 结构：源头 → 生成文件 → 默认值 `'unknown'`
   - except 块使用宽泛 `Exception`（任何导入失败都应回退而非崩溃）
   - 返回值必须为字符串（非 `None`/空串），避免下游类型判断复杂化
   - 默认值统一为 `'unknown'`（不用空串，避免前端误判为"加载中"）

3. **前端显示元数据必须调用语义对齐的 API**
   - 版本号显示组件必须调用 `/api/about`（语义：系统元信息），**禁止**调用 `/api/config/version`（语义：备份数计数）等语义错位端点
   - 卡片/Statistic 的 `value` 必须与 `title` 语义对齐（如 `title="系统版本"` 时 `value` 不能是 `backups.length`）
   - 多个独立 API 调用应使用 `Promise.all` 并行化（如 `[configApi.listBackups(), aboutApi.get()]`）

4. **跨端数据流问题必须前后端协同修复**
   - 修复时必须检查前端调用 → 后端端点 → 数据源全链路，**禁止**只改一边
   - 同步检查相关端点是否也有占位符（如修复 `/api/about` 时同步检查 `/api/config/export`）

5. **修复时同步清理死代码**
   - 修复 bug 时发现只 `set` 不 `read` 的 state / 只 `import` 不调用的函数必须同步清理
   - 清理前用 `grep` 全局搜索确认无引用
   - 删除声明、赋值、import 三处
   - **禁止**"下次再说"——死代码会误导后续开发者认为该 state/函数仍在生效

**判断逻辑**：

- `grep "from xianyu_hunter import __version__" src/` 出现 ≥ 2 处 → 必须封装 `_safe_app_version()` 辅助函数
- `grep -E "'(1\.0|0\.0\.0|unknown version)'" src/xianyu_hunter/` 出现匹配 → 必须改为调用辅助函数
- 前端代码含 `configApi.getVersion()` 用于版本号显示 → 视为违规（应改用 `aboutApi.get()`）
- 前端代码含 `title="[Vv]ersion"` 的 Statistic/Card 但 `value` 来自 `length`/`count`/`size` → 视为违规
- 前端 `useState` 声明的变量在文件内只有 `setXxx` 调用无 `xxx` 读取 → 视为死代码

**反例**：

```python
# ❌ 错误：生产代码占位符版本号 + 多端点独立读取未封装
@api_router.get("/config/export")
async def export_config():
    return {"version": "1.0", "items": []}  # 占位符，与 __version__ 不一致
```

```typescript
// ❌ 错误：前端调用语义错位 API + 用列表长度当版本号
const [version, setVersion] = useState(0)
const res = await configApi.getVersion()  // 实际返回备份数计数
setVersion(res.count)  // 卡死在 BACKUP_KEEP=10
return <Statistic title="系统版本" value={`V${version}`} />
```

**正例**：

```python
# ✅ 正确：封装 _safe_app_version() 辅助函数 + 三层回退
def _safe_app_version() -> str:
    """读取系统真实版本号，失败时回退为 'unknown'。

    与 api_about._safe_build_info 同源：__init__.py 的 __version__ 是单一源头，
    _build_info.py 由 scripts/build_info.py 重新生成。开发环境 _build_info 可能
    未生成，所以优先读 __init__.py 的 __version__，再回退到 _build_info。
    """
    try:
        from xianyu_hunter import __version__
        if __version__:
            return __version__
    except Exception:
        pass
    try:
        from xianyu_hunter import _build_info
        return getattr(_build_info, "__version__", "unknown") or "unknown"
    except Exception:
        return "unknown"

@api_router.get("/config/export")
async def export_config():
    return {"version": _safe_app_version(), "items": []}
```

```typescript
// ✅ 正确：调用语义对齐的 aboutApi + Promise.all 并行化
const [buildInfo, setBuildInfo] = useState<AboutInfo | null>(null)
const [backupRes, aboutRes] = await Promise.all([
  configApi.listBackups(),
  aboutApi.get(),
])
setBackups(backupRes.backups || [])
setBuildInfo(aboutRes)
return (
  <Statistic
    title="系统版本"
    value={buildInfo ? `v${buildInfo.version}` : '--'}
  />
)
```

**配置参数**：`version_source_management` 节点（enabled / single_source_file / auto_generated_file / safe_helper_function / fallback_default / forbidden_placeholders / forbidden_version_endpoints / cross_layer_fix_required）

**适用场景**：
- 版本号、构建时间、git_sha、构建者等构建期元数据的读取与显示
- 多端点需读取同一元数据（如 `/api/about` + `/api/config/export` 都需返回 version）
- 前端版本管理/关于页面/系统信息卡片等显示构建期元数据
- 配置项、状态码、枚举值等"被多处引用的常量"的源管理

**不适用场景**：
- 业务数据（用户输入、数据库记录）—— 这些本身就是多源可变的
- 临时调试变量（如 `DEBUG=true`）—— 临时性优先于单源性
- 跨服务边界的元数据（如微服务间传递的 trace_id）—— 需要协议而非单源
- 必须存在的核心依赖（如 FastAPI）—— 失败应直接崩溃，不应回退
- Pydantic 模型字段 —— 应用类型系统而非 try/except 防御

**历史教训**：版本管理菜单持续显示 "V10"。根因链路：前端 `VersionManager.tsx` 调用 `configApi.getVersion()` 拉取 `/api/config/version`，但该端点实际返回 `len(backups)`（备份数量），受 `BACKUP_KEEP=10` 上限影响永远卡在 10，前端拼成 `'V' + 10 = 'V10'`。同时后端 `api_config.py` 的 `export_config` 中残留 `"version": "1.0"` 占位符。修复时跨端协同：前端改用 `aboutApi.get()` 拉取 `/api/about`（返回真实 `__version__`）；后端新增 `_safe_app_version()` 辅助函数（三层 try/except 回退到 `'unknown'`）替换占位符；顺带清理 Dashboard 中只 set 不 read 的 `configVersion` 死代码。验证时还遇到 Python `__pycache__` 缓存导致修改未生效、`BearerAuthMiddleware` 在 `web_token=""` 时短路导致 401 等环境层陷阱。


---

### step 102：Pydantic 模型字段完整性规范【强制】🆕v4.19

**背景**：通知渠道凭据字段（`serverchan_send_key` 等 10 个）未在 `AppConfig` 中显式声明，依赖 Pydantic v2 默认 `extra='ignore'` 行为，导致 `model_dump()` 丢弃这些字段，前端 `GET /api/config` 永远拿不到凭据，刷新页面后输入框清空。

**规范**：

1. **所有需持久化或回显的字段必须在 Pydantic 模型中显式声明**
   - 不允许依赖 `extra='allow'` 或 `extra='ignore'` 处理 yaml 中的字段
   - 即使字段默认值为空字符串，也必须显式声明（如 `serverchan_send_key: str = ""`）
   - 字段必须包含类型注解和默认值

2. **新增 yaml 字段时必须同步更新 Pydantic 模型**
   - 编辑 `config/config.yaml` 添加新字段后，必须同步在对应的 Pydantic 模型中声明
   - CI 检查：扫描 yaml 字段名与 Pydantic 模型字段对齐（`pydantic_field_integrity.scan_yaml_keys`）

3. **`model_dump()` 输出必须包含所有持久化字段**
   - 任何通过 `model_dump()` 序列化的字段集必须完整
   - 禁止用 `exclude=True` 排除需持久化的字段（运行时计算字段除外）

4. **API 响应必须验证字段完整性**
   - 新增 API 端点返回配置时，必须用单元测试验证所有字段都被序列化
   - 测试用例：写入 → `model_dump()` → 验证所有字段存在

**判断逻辑**：

- `grep "extra=.allow." src/xianyu_hunter/` 发现配置模型用 `extra='allow'` → 视为可疑
- yaml 中有字段但 Pydantic 模型无对应声明 → 视为违规
- API 返回字典缺失 yaml 中已有字段 → 必查 Pydantic 模型声明
- 代码用 `model_extra` 或 `__pydantic_extra__` 访问未声明字段 → 视为可疑（应改为显式声明）

**反例**：

```python
# ❌ 错误：依赖 extra='allow' 处理 yaml 字段
class AppConfig(BaseModel):
    model_config = ConfigDict(extra='allow')
    notifier: NotifierConfig = NotifierConfig()
    # 凭据字段未声明，model_dump() 时被丢弃
```

**正例**：

```python
# ✅ 正确：所有需持久化的字段显式声明（哪怕默认空字符串）
class AppConfig(BaseModel):
    notifier: NotifierConfig = NotifierConfig()
    # 通知渠道凭据（明文存到 yaml，前端用 Input.Password 组件隐藏）
    serverchan_send_key: str = ""
    pushplus_token: str = ""
    bark_server: str = ""
    bark_key: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    wecom_webhook: str = ""
    dingtalk_webhook: str = ""
    dingtalk_secret: str = ""
    webhook_url: str = ""
```

**配置参数**：`pydantic_field_integrity` 节点（enabled / require_explicit_declare / scan_yaml_keys / exceptions）

**适用场景**：
- 所有继承 `BaseModel` 的配置模型（AppConfig / NotifierConfig 等）
- 需持久化到 yaml/json 的字段
- 通过 API 回显的字段

**不适用场景**：
- 运行时计算字段（用 `@computed_field`）
- 显式标注 `exclude=True` 的字段
- 临时内存对象（无需序列化）

**历史教训**：通知渠道凭据字段未在 `AppConfig` 中显式声明，前端写入 yaml 后 `GET /api/config` 调用 `model_dump()` 丢弃这些字段，导致前端"填写后刷新页面变空"


---

### step 117：API 更新接口三态语义规范【强制】🆕v4.26

**背景**：PATCH/PUT 接口需要支持「未传字段（skip）」、「传 null（clear）」、「传值（update）」三态语义。手动循环跳过 None 无法区分「未传」和「传 null」，导致「清除覆盖」功能失效。

**问题**：PATCH/PUT 接口的可选字段更新逻辑用 `for k, v in raw.items(): if v is None: continue` 跳过 None，无法区分用户「未传该字段」（应保留旧值）和「显式传 null」（应清除旧值），导致前端「清除任务级覆盖」功能失效。

**规范**：

1. **三态语义区分【强制】**：PATCH/PUT 接口必须用 Pydantic v2 的 `model_dump(exclude_unset=True)` 区分三态：
   - **未传**（skip）：字段未在请求中提供 → `exclude_unset=True` 会过滤掉 → 跳过更新
   - **传 null**（clear）：字段显式传 null → 保留在 dump 结果中 → 写入 None（清除）
   - **传值**（update）：字段传具体值 → 保留在 dump 结果中 → 写入新值
   ```python
   # ✅ 正确：用 exclude_unset=True 区分三态
   raw = body.model_dump(exclude_unset=True)
   updates = dict(raw)

   # ❌ 错误：手动循环跳过 None，无法区分未传和传 null
   raw = body.model_dump()
   for k, v in raw.items():
       if v is None:
           continue
   ```

2. **NOT NULL 字段防御性 pop【强制】**：DB schema 为 NOT NULL 的字段（如 `use_cron`、`interval_seconds`）传 null 时必须防御性 pop（`updates.pop(field, None)`），而非直接写入 DB 触发 IntegrityError：
   ```python
   # ✅ 正确：NOT NULL 字段传 null 时防御性 pop
   for not_null_field in NOT_NULL_FIELDS:
       if updates.get(not_null_field) is None:
           updates.pop(not_null_field, None)

   # ❌ 错误：直接写入触发 IntegrityError
   # updates 中 use_cron=None 会触发 NOT NULL constraint failed
   ```

3. **覆盖字段允许 null 写入【强制】**：覆盖字段（如 `search_config`、`price_config`）传 null 表示「清除覆盖」，应正常写入 None，不得 pop：
   ```python
   # ✅ 正确：覆盖字段传 null 表示清除覆盖，正常写入 None
   # updates['search_config'] = None → DB 存 None → startup 读取时回退到全局配置
   ```

**配置驱动**：三态字段分类、NOT NULL 字段清单、覆盖字段清单等参数在 `config.yaml` 的 `api_update_semantics` 节点管理，包含 `three_state_fields` / `not_null_fields` / `clear_override_fields` 等，不硬编码在技能中。

**适用场景**：
- 所有 PATCH/PUT 接口的可选字段更新
- 需要支持「清除覆盖」语义的字段（任务级配置覆盖、用户偏好覆盖等）

**不适用场景**：
- POST 创建接口（所有字段都显式传，无需区分三态）
- 内部函数调用（参数语义在调用点明确）

**历史教训**：`api_tasks.py` 的 `update_task` 用手动循环 `for k, v in raw.items(): if v is None: continue` 跳过 None，导致前端「清除任务级覆盖」时 null 被跳过，旧值保留，覆盖无法清除。修复：改用 `model_dump(exclude_unset=True)` + NOT NULL 字段防御性 pop。

**判断信号（review 触发条件）**：
- `grep "model_dump()"` 不带 `exclude_unset` 的 PATCH/PUT 接口
- `grep "if v is None: continue"` 模式出现在 PATCH/PUT 接口中
- 前端「清除覆盖」功能无效（传 null 后旧值保留）


---

### step 118：字段全链路消费规范【强制】🆕v4.26

**背景**：新增任务级配置字段时必须同时实现「DB 存储 → startup 读取 → worker 消费」完整链路。禁止只实现存储和 API 暴露但不让 worker 消费（死字段）。

**问题**：新增任务级配置字段（如 `eval_threshold`、`antidetect_config`）只在 DB schema 和 API 中暴露，但 worker 运行时不读取该字段，仍用全局配置，导致字段成为「死字段」——用户编辑后无效果，误导用户。

**规范**：

1. **完整链路实现【强制】**：新增任务级配置字段必须同时实现三步链路：
   - **DB 存储**：schema 添加列 + ORM model 添加字段 + migration 脚本
   - **startup 读取**：`startup.py` 在构造 Task dataclass 时从 DB row 读取该字段
   - **worker 消费**：`worker.py` 在运行时优先读取 task 级字段，回退到全局配置
   ```python
   # ✅ 正确：worker 优先消费 task 级字段，回退到全局配置
   _pass_score = task.eval_threshold if task.eval_threshold is not None else (eval_cfg.pass_score if eval_cfg else 60)

   # ❌ 错误：worker 用全局配置，task.eval_threshold 成为死字段
   _pass_score = eval_cfg.pass_score if eval_cfg else 60
   ```

2. **死字段处理【强制】**：字段不能消费时必须明确处理：
   - 移除 UI 编辑入口（禁止用户编辑无效字段）
   - 添加注释说明原因（如「保留以兼容旧数据，worker 不消费」）
   - 不得保留可编辑的 UI 入口但不消费
   ```python
   # ✅ 正确：死字段添加注释说明
   # antidetect_config: 保留以兼容旧数据，worker 不消费（全局 Modal 管理）
   # 若未来需要任务级覆盖，需在 worker.py 激活消费
   ```

**配置驱动**：字段消费链路检查清单、死字段检测关键词、消费模式等参数在 `config.yaml` 的 `field_consumption_chain` 节点管理，包含 `required_chain_steps` / `dead_field_keywords` / `consume_pattern` 等，不硬编码在技能中。

**适用场景**：
- 所有任务级配置覆盖字段（`eval_threshold`、`ai_prompt`、`search_config`、`price_config` 等）
- 新增的配置覆盖字段

**不适用场景**：
- 向前兼容的遗留字段（应添加注释说明「保留以兼容旧数据，worker 不消费」）
- 纯展示字段（如 `created_at`、`updated_at`）

**历史教训**：`eval_threshold` 和 `antidetect_config` 都是死字段——DB 有字段但 worker 不消费。修复 eval_threshold：激活 worker 消费（`task.eval_threshold if task.eval_threshold is not None else eval_cfg.pass_score`）；修复 antidetect_config：移除前端 UI 入口改为全局 Modal + 添加注释说明「worker 不消费」。

**判断信号（review 触发条件）**：
- `grep` DB schema 中的 JSON/nullable 字段，逐一检查 worker 是否消费
- 前端有编辑入口但运行时不读取该字段
- 用户反馈「编辑了某字段但运行行为无变化」


---

### step 119：共享单例局部变量规范【强制】🆕v4.26

**背景**：循环中创建任务级覆盖对象时必须用局部变量，禁止直接修改 container 单例。container 单例在循环中被直接修改会导致循环结束后指向最后一个任务的配置，影响共享 container 的其他代码。

**问题**：startup/scheduler 中遍历任务构造 worker 时，直接 `container.xxx = new(...)` 修改共享单例，循环结束后 container 单例的属性指向最后一个任务的配置，污染共享 container 的其他代码（如 live 端点、状态查询）。

**规范**：

1. **局部变量隔离【强制】**：循环中创建任务级覆盖对象必须用局部变量（命名 `worker_xxx`），禁止直接修改 container 单例：
   ```python
   # ✅ 正确：用局部变量隔离，container 单例不受污染
   worker_price_strategy = container.price_strategy
   if override:
       worker_price_strategy = type(container.price_strategy)(PriceConfig(...))
   worker = TaskWorker(..., price_strategy=worker_price_strategy)

   # ❌ 错误：直接修改 container 单例，循环结束后污染
   container.price_strategy = type(container.price_strategy)(PriceConfig(...))
   worker = TaskWorker(..., price_strategy=container.price_strategy)
   ```

2. **命名规范【强制】**：局部变量必须用 `worker_` 前缀命名（`worker_price_strategy`、`worker_search_config` 等），明确标识为「worker 专用副本」。

**配置驱动**：共享单例清单、局部变量命名规则、检测模式等参数在 `config.yaml` 的 `shared_singleton_protection` 节点管理，包含 `shared_singletons` / `local_var_prefix` / `detection_patterns` 等，不硬编码在技能中。

**适用场景**：
- startup/scheduler 中遍历任务构造 worker 的循环体
- 任何在循环中创建覆盖对象的场景

**不适用场景**：
- 单任务场景（无需局部变量）
- 非共享对象（每次新建的实例）

**历史教训**：`startup.py` 在遍历任务循环中直接 `container.price_strategy = new(...)`，导致循环结束后 container.price_strategy 污染（指向最后一个任务的配置），影响 live 端点等共享 container 的代码。修复：引入局部变量 `worker_price_strategy`。

**判断信号（review 触发条件）**：
- `grep` 循环体内的 `container.xxx =` 赋值语句
- live 端点 / 状态查询返回的配置与预期不符（指向最后一个任务的配置）


---

### step 120：跨前后端类型对齐规范【强制】🆕v4.26

**背景**：前端 TypeScript interface 必须与后端运行时模型（Pydantic/dataclass）字段严格对齐。后端不消费的字段不得在前端 interface 中声明为「与后端对齐」。

**问题**：前端 TypeScript interface 声明「与后端某 model 对齐」，但后端运行时创建的是另一个 model（字段不同），导致前端类型声明误导，开发者以为字段会被消费但实际不会。

**规范**：

1. **严格对齐【强制】**：前端 TypeScript interface 必须与后端运行时模型（Pydantic/dataclass）字段严格对齐，不得与配置文件 model（如 yaml 配置类）对齐而误导：
   ```typescript
   // ❌ 错误：声明与 PriceStrategyConfig 对齐，但运行时创建的是 PriceConfig（无 enabled_*）
   // interface TaskPriceOverride {
   //   min_price: number;
   //   max_price: number;
   //   enabled_max: boolean;  // 运行时不消费
   //   enabled_min: boolean;  // 运行时不消费
   // }

   // ✅ 正确：与运行时 PriceConfig 对齐，并注释说明部分实现
   interface TaskPriceOverride {
     // 注意：仅消费 min_price/max_price/market_ratio
     // PriceStrategyConfig 的 enabled_* 开关和 top_n 未消费（UI 未暴露编辑入口）
     // PriceConfig 用 None 表示禁用，与 enabled_*=False 语义等价
     min_price: number | null;
     max_price: number | null;
     market_ratio: number | null;
   }
   ```

2. **部分实现注释【强制】**：部分实现时必须注释说明未消费字段及原因，不得让后续开发者误以为字段会被消费。

**配置驱动**：类型对齐检查清单、允许部分实现的字段清单、对齐检查规则等参数在 `config.yaml` 的 `cross_stack_type_alignment` 节点管理，包含 `required_aligned_interfaces` / `partial_implementation_fields` / `alignment_check_rules` 等，不硬编码在技能中。

**适用场景**：
- 所有跨前后端的类型定义（TypeScript interface ↔ Python Pydantic/dataclass）
- 任务级配置覆盖、API 请求/响应模型

**不适用场景**：
- 纯前端或纯后端的内部类型
- 第三方库类型（无法控制）

**历史教训**：`TaskPriceOverride`（前端）声明与 `PriceStrategyConfig`（yaml 配置）对齐，但运行时 startup.py 创建的是 `PriceConfig`（无 `enabled_*` 字段），不消费 `enabled_*`，导致前端类型声明误导。修复：添加注释说明「仅消费 min_price/max_price/market_ratio，PriceStrategyConfig 的 enabled_* 开关和 top_n 未消费」。

**判断信号（review 触发条件）**：
- diff 前端 interface 字段 vs 后端运行时模型字段，不一致即为可疑
- 前端 interface 注释「与后端 xxx 对齐」但 grep 后端运行时创建的是另一个 model


---

### step 129：业务关键字常量集中管理规范【强制】🆕v4.29

**背景**：外部平台（如闲鱼）UI 文案变化频繁（如「卖掉了」→「已售」→「宝贝不存在」），代码中散落的中文字面量导致新增文案时遗漏更新，表现为「卖家已删除商品但状态未采集为已售」。

**问题**：`_detail.py`/`_parser.py`/`buyer.py` 各自维护「已售」关键字列表（如 `['已售', '已下架']`），闲鱼新增「卖掉了」「宝贝走丢了」文案时只更新了部分文件，导致 `_detect_detail_is_sold` 在新文案下返回 `False`，已售商品被误判为「在售」继续推送。

**规范**：

1. **业务关键字常量集中管理【强制】**：外部平台文本特征（已售关键字/已下单关键字/区域关键字/状态文案等）必须集中到单一模块（如 `collector_utils.py` 的 `SOLD_TEXT_KEYWORDS` / `ORDERED_TEXT_KEYWORDS` 常量），**禁止**在各业务文件内散落字面量：
   ```python
   # ✅ 正确：集中到 collector_utils.py
   SOLD_TEXT_KEYWORDS: tuple[str, ...] = ("已售", "已下架", "卖掉了", "宝贝不存在", "宝贝走丢了", "该宝贝不存在", "商品不存在", "已删除", "已被删除")

   def check_text_sold(text: str) -> bool:
       """检查文本是否包含已售关键字（统一入口）"""
       return any(kw in text for kw in SOLD_TEXT_KEYWORDS)

   # ❌ 错误：各文件散落字面量
   # _detail.py: if "已售" in text or "已下架" in text: ...
   # _parser.py: if "卖掉了" in text: ...  # 缺少其他关键字
   # buyer.py: if "宝贝不存在" in text: ...  # 又一个版本
   ```

2. **统一访问函数【强制】**：业务代码必须通过统一函数（如 `check_text_sold`）访问关键字，**禁止**直接引用常量 tuple 做内联 `any(kw in text for kw in ...)`：
   ```python
   # ✅ 正确：调用统一函数
   from .collector_utils import check_text_sold
   if check_text_sold(page_text):
       item.is_sold = True

   # ❌ 错误：直接引用常量内联判断（绕过统一入口）
   from .collector_utils import SOLD_TEXT_KEYWORDS
   if any(kw in text for kw in SOLD_TEXT_KEYWORDS):
       ...
   ```

3. **新增文案时全链路更新【强制】**：发现新文案时必须更新集中常量，**禁止**只在出现 bug 的文件内打补丁：
   ```python
   # ✅ 正确：更新 collector_utils.py 的 SOLD_TEXT_KEYWORDS，所有调用方自动生效
   SOLD_TEXT_KEYWORDS = (..., "新文案")

   # ❌ 错误：只在 _detail.py 内加判断
   # if "新文案" in text: item.is_sold = True  # _parser.py 仍漏
   ```

**配置驱动**：业务关键字清单、统一访问函数名、检测场景等参数在 `config.yaml` 的 `external_platform.text_features` 节点管理，包含 `sold_keywords` / `ordered_keywords` / `region_keywords` / `unified_check_functions` 等，不硬编码在技能中。

**适用场景**：
- 外部平台文本特征识别（已售/已下单/区域/状态文案）
- 第三方系统响应文案解析
- 任何需要全链路同步更新的关键字常量

**不适用场景**：
- 框架内部固定文案（如 antd 默认 placeholder）
- 单次使用的字符串字面量（无复用需求）
- 协议固定值（如 HTTP method）

**历史教训**：闲鱼前端将「已售」文案改为「卖掉了」，但 `SOLD_TEXT_KEYWORDS` 只在 `_detail.py` 部分文件中维护，`_parser.py` 和 `buyer.py` 未同步更新，导致商品 1058031608014 已售但状态未采集。修复：抽取统一 `SOLD_TEXT_KEYWORDS` 常量和 `check_text_sold()` 函数到 `collector_utils.py`，三个文件统一调用。

**判断信号（review 触发条件）**：
- `grep "已售\|已下架\|卖掉了" <file>` 中文字面量散落多个文件 → 视为违规
- `grep "in text" <file>` 出现内联关键字判断而非调用统一函数 → 视为可疑
- 多个文件维护同一业务概念的关键字列表 → 视为违规


---

### step 131：前后端字段名大小写敏感检查规范【强制】🆕v4.29

**背景**：Python 类的私有属性命名（`_session` vs `_Session`）和 API 字段名（`total` vs `total_for_type`）在运行时大小写敏感，但 IDE 自动补全和代码 review 容易忽略，导致 `AttributeError` 或前端取不到数据。

**问题**：
1. `api_chatbot_config.py` line 343 使用 `self._Session()` 但类中定义的是 `self._session`（小写 s），运行时抛 `AttributeError: 'ChatbotRepository' object has no attribute '_Session'`
2. `api_task_links.py` 返回 `total` 字段，但前端 `ItemList.tsx` 期望 `total_for_type`，导致前端「0 条」显示
3. 前后端字段名 `min_price`/`minPrice` snake_case ↔ camelCase 转换遗漏

**规范**：

1. **私有属性大小写一致性【强制】**：Python 类中私有属性（`_` 开头）的命名必须在赋值和引用处严格大小写一致，**禁止**依赖 IDE 自动补全：
   ```python
   # ✅ 正确：赋值和引用大小写一致
   class ChatbotRepository:
       def __init__(self):
           self._session = self._build_session()  # 小写 _session

       def get(self):
           return self._session()  # 引用处也是小写 _session

   # ❌ 错误：赋值小写但引用大写
   # class ChatbotRepository:
   #     def __init__(self):
   #         self._session = ...  # 小写 _session
   #     def get(self):
   #         return self._Session()  # 大写 _Session → AttributeError
   ```

2. **API 字段名前后端契约对齐【强制】**：API 响应字段名必须前后端严格一致（含大小写、下划线、前后缀），前端 types.ts 字段名必须与后端 `model_dump()` / dict 字面量 key 完全相同：
   ```python
   # ✅ 正确：后端返回字段名与前端 types.ts 一致
   # 后端
   return {"total_for_type": count, "items": [...]}
   # 前端 types.ts
   interface TaskLinkListResponse {
     total_for_type: number;  // 与后端一致
     items: TaskLink[];
   }

   # ❌ 错误：后端用 total，前端期望 total_for_type
   # return {"total": count}  # 前端取不到 → 显示 0 条
   ```

3. **大小写敏感检查清单【强制】**：新增字段时必须 grep 双向匹配：
   ```bash
   # 后端字段 → 前端检查
   grep -rn "field_name" frontend/src/types.ts
   # 前端字段 → 后端检查
   grep -rn "field_name" src/xianyu_hunter/
   ```

**配置驱动**：大小写敏感字段清单、检查规则、snake_case ↔ camelCase 转换映射等参数在 `config.yaml` 的 `field_name_contract` 节点管理，包含 `case_sensitive_fields` / `snake_camel_mapping` / `bidirectional_check_required` 等，不硬编码在技能中。

**适用场景**：
- Python 类私有属性（`_xxx` 命名）
- API 请求/响应字段名（前后端契约）
- DB schema 字段名与 ORM model 字段名对齐
- TypeScript interface 与 Python Pydantic model 字段对齐

**不适用场景**：
- 框架内置属性（如 `__init__`/`__str__`，由 Python 规范保证）
- 第三方库字段名（无法控制）
- 内部局部变量（无跨模块引用）

**历史教训**：
- `api_chatbot_config.py` line 343 引用 `self._Session()` 但定义的是 `self._session`，运行时 `AttributeError`。根因：开发者混淆大小写，IDE 自动补全未提示。修复：改为 `self._session()`
- `api_task_links.py` 返回 `total` 但前端期望 `total_for_type`，前端显示「0 条」。根因：后端重构时改了字段名但未同步前端 types.ts。修复：后端改回 `total_for_type`

**判断信号（review 触发条件）**：
- `grep "_[A-Z]" <file>` 出现大写开头的私有属性引用 → 视为可疑（Python 惯例 `_xxx` 全小写）
- `grep` 后端响应字段名 vs 前端 types.ts 字段名不一致 → 视为违规
- `AttributeError: 'XxxRepository' object has no attribute '_Yyy'` 运行时错误 → 必然违规
- 前端显示「0 条」/「undefined」但后端日志显示有数据 → 字段名不一致可疑


---

### step 155：PARAM-CHAIN-01 参数传递链完整性原则【强制】🆕v4.29

**背景**：`build_search_url` 构造闲鱼搜索 URL 时漏传 `sort` / `region` 参数，导致采集结果排序与预期不符且地域过滤失效。前端配置的排序方式与地区筛选未透传到爬虫请求层。

**问题**：参数在配置层定义后，传递链路（config → API → service → builder → request）中任一节点遗漏即导致配置失效；由于参数缺失往往不报错（仅用默认值），问题难以被及时发现。

**规范**：

1. **参数链路清单【强制】**：新增可配置参数时必须列出完整传递链路，每个节点标注接收与转发责任：
   ```
   config.yaml.sort_strategy → api_tasks.py → collection_service.py → build_search_url() → 闲鱼请求
   ```

2. **链路断点检测【强制】**：参数传递函数（如 `build_search_url`）的签名必须显式接收所有相关参数，禁止依赖全局变量或隐式默认值：
   ```python
   # ✅ 正确：显式接收所有参数
   def build_search_url(keyword: str, sort: str, region: str, page: int) -> str:
       params = {"keyword": keyword, "sort": sort, "region": region, "page": page}
       return base + urlencode(params)

   # ❌ 错误：漏传 sort/region，依赖函数内默认值
   # def build_search_url(keyword: str, page: int) -> str:
   #     return base + urlencode({"keyword": keyword, "page": page})
   ```

3. **配置变更必须 grep 全链路【强制】**：配置项变更时必须 grep 参数名确认每个传递节点都已更新。

**配置驱动**：`coding_standards.param_chain.required_params`（必须透传的参数清单）在 `config.yaml` 管理。

**适用场景**：
- 多层架构的参数传递（config → API → service → builder）
- 爬虫请求构造（URL 参数链路）
- 任务调度参数透传

**不适用场景**：
- 内部派生参数（由其他参数计算得出，无需透传）
- 框架自动注入的参数（如 FastAPI 的 Depends）

**历史教训**：`build_search_url` 漏传 `sort` / `region` 参数，用户配置的排序方式与地区筛选未生效，采集结果与预期不符。

**判断信号（review 触发条件）**：
- 函数签名缺少配置层已定义的参数
- 配置项变更后未 grep 全链路验证
- 用户反馈「配置不生效」但配置已正确写入


---

### step 156：KEYWORD-01 业务关键词集中管理原则【强制】🆕v4.29

**背景**：已售商品关键词列表不完整（缺少"卖掉了"等新文案），且关键词散落在多个模块（`_detail.py` / `_parser.py` / `buyer.py`），导致同一文案变更需修改多处，容易漏改。

**问题**：业务关键词（已售文案/错误码/状态特征）分散在多个模块时，外部系统文案变更需逐文件修改，漏改即导致误判；关键词清单无版本化注释，无法追溯历史遗漏。

**规范**：

1. **关键词集中为模块级常量【强制】**：业务关键词必须提取为被依赖方模块的顶层常量（`tuple[str, ...]` / `frozenset[str]`），禁止分散在函数内部：
   ```python
   # collector_utils.py
   SOLD_TEXT_KEYWORDS: tuple[str, ...] = (
       "已售", "已售出", "已售完", "已售罄",
       "卖掉了",  # 闲鱼新版文案（2026-06-29 发现）
       "已下架", "已删除",
   )
   ```

2. **多处消费点必须 import 同一常量【强制】**：多处消费点必须 `from <source> import <KEYWORDS>`，禁止内联关键词列表。

3. **关键词变更必须版本化注释【强制】**：新增关键词时必须注释发现日期与来源，便于追溯历史遗漏。

**配置驱动**：`coding_standards.keyword_centralize.audit_keywords`（需集中管理的关键词类别清单）在 `config.yaml` 管理。

**适用场景**：
- 外部系统文案检测（已售/下架/错误状态）
- 多处消费同一类关键词
- 关键词需随外部系统变更而扩展

**不适用场景**：
- 单一消费点的临时字符串比较
- 内部状态判断（如 `status == 'completed'`）

**历史教训**：已售商品关键词列表分散在 3 个文件，新增"卖掉了"文案时漏改 `_parser.py`，导致商品 1058031608014 误判为在售。修复后提取 `SOLD_TEXT_KEYWORDS` 常量到 `collector_utils.py`，3 处复用。

**判断信号（review 触发条件）**：
- `grep "已售\|卖掉了\|已下架"` 同一关键词在多个文件出现
- 函数内部含关键词列表字面量而非 import 常量
- 外部系统文案变更后多处需修改


---

### step 157：PERSIST-01 用户可配置开关持久化原则【强制】🆕v4.29

**背景**：批量采集开关（如自动刷新/批量暂停）用裸 `useState` 管理，页面刷新后状态丢失，用户需反复重新配置，体验差。

**问题**：用户偏好类 UI 状态（开关/视图模式/列显隐）用裸 `useState` 时，页面刷新即丢失，与「持久化」语义不符；各组件自行实现 localStorage 读写导致 key 命名混乱、无脏数据防御。

**规范**：

1. **用户偏好类开关必须持久化【强制】**：用户可配置的开关（自动刷新/批量暂停/视图模式/列显隐）必须使用 `usePersistentState` hook，禁止裸 `useState`：
   ```typescript
   // ✅ 正确：持久化开关
   const [autoRefresh, setAutoRefresh] = usePersistentState<boolean>(
     'xh.batchRefresh.autoRefresh', false, { validator: (v) => typeof v === 'boolean' }
   );

   // ❌ 错误：裸 useState，刷新即丢失
   // const [autoRefresh, setAutoRefresh] = useState(false);
   ```

2. **key 命名规范【强制】**：持久化 key 必须遵循 `xh.<page>.<field>` 格式，避免跨页面冲突。

3. **validator 必填【强制】**：`usePersistentState` 必须传入 validator 防止 localStorage 脏数据导致运行时错误。

**配置驱动**：`coding_standards.persist_state.key_prefix`（`xh`）、`required_validator`（`true`）在 `config.yaml` 管理。

**适用场景**：
- 用户偏好类开关（自动刷新/批量暂停/视图模式/列显隐）
- 跨会话需保留的 UI 状态
- 用户可配置的阈值/筛选条件

**不适用场景**：
- 业务数据类状态（由后端管理）
- 会话状态类（登出即清除）
- 临时状态类（如 loading 标志）

**历史教训**：`Maintenance/BatchRefresh.tsx` 的自动刷新开关用裸 `useState(false)`，页面刷新后开关重置为 false，用户需反复重新开启。修复后改用 `usePersistentState`。

**判断信号（review 触发条件）**：
- `grep "useState" <tsx_file>` 出现在用户偏好类开关
- 用户反馈「刷新后配置丢失」
- 持久化 key 不符合 `xh.<page>.<field>` 格式


---

### step 158：CREDENTIAL-01 凭证多存储同步原则【强制】🆕v4.29

**背景**：钉钉通知未发送，排查发现 `config.yaml` 中已配置钉钉 webhook 凭证，但 `keyring`（Windows DPAPI）中未同步，通知模块从 keyring 读取失败即静默跳过。

**问题**：凭证存储在多源（yaml / keyring / .env）时，一处更新未同步到其他源即导致读取失败；通知模块读取失败时静默跳过而非降级到 yaml，问题难以发现。

**规范**：

1. **凭证多源同步【强制】**：凭证在 yaml / keyring / .env 任一存储更新时，必须显式同步到其他存储，禁止依赖单一数据源：
   ```python
   # ✅ 正确：yaml 凭证同步到 keyring
   def _sync_credential_to_keyring(name: str, value: str) -> None:
       try:
           keyring.set_password(SERVICE_NAME, name, value)
       except Exception as e:
           logger.warning(f"凭证 {name} 写入 keyring 失败: {e}")

   # ❌ 错误：仅写入 yaml，keyring 读取失败
   # config['dingtalk_webhook'] = new_url  # keyring 仍是旧值
   ```

2. **读取失败必须降级【强制】**：凭证从主存储（keyring）读取失败时，必须降级到备用存储（yaml / .env），禁止静默跳过：
   ```python
   def get_credential(name: str) -> str | None:
       # 优先 keyring，失败降级 yaml
       try:
           value = keyring.get_password(SERVICE_NAME, name)
           if value:
               return value
       except Exception:
           logger.warning(f"keyring 读取 {name} 失败，降级到 yaml")
       return config.get(name)
   ```

3. **凭证写入失败必须告警【强制】**：凭证写入 keyring 失败时必须 `logging.warning()` 告警，禁止静默吞掉异常。

**配置驱动**：`coding_standards.credential.storages`（存储优先级列表：`['keyring', 'yaml', 'env']`）在 `config.yaml` 管理。

**适用场景**：
- 凭证多存储场景（keyring + yaml + .env）
- 通知模块凭证读取（钉钉/企业微信/邮件）
- 多源凭证同步

**不适用场景**：
- 单一存储的凭证（仅 yaml 或仅 keyring）
- 临时 token（无需持久化）

**历史教训**：钉钉 webhook 凭证仅写入 yaml，keyring 中无对应记录，通知模块从 keyring 读取失败后静默跳过，用户反馈「通知未发送」但日志无错误。修复后添加 yaml → keyring 同步逻辑 + 读取失败降级。

**判断信号（review 触发条件）**：
- `grep "keyring.get_password" <file>` 后无降级逻辑
- `grep "keyring.set_password" <file>` 无 try/except 告警
- 用户反馈「通知未发送」但配置已正确


---

### step 196：TIME-PARAM-CONFIG-DRIVEN 时间参数配置化【强制，meta-rule #49 落地】🆕v4.36

**背景**：`scheduler.py` 的 `_compute_next_wait_seconds` 异常重试等待硬编码 `return 300`，导致所有任务异常后必须等 5 分钟才能重试，无法根据业务场景调整。同期 `cookie_sync_scheduler.py` 的同步间隔硬编码在代码中，`batch_refresh_scheduler.py` 的失败重试等待也是字面量数字。对应元规范 meta-rules #49，与 B-REVIEW-179（backend 时间参数配置化审查）+ F-REVIEW-137（frontend 轮询间隔配置化审查）对应。

**问题**：异常重试等待秒数、轮询间隔、超时秒数等时间参数硬编码在代码中，无法根据业务场景调整，配置变更需要改代码重新部署。

**规范**：

1. **时间参数清单识别【强制】**：从 `config.yaml#time_param_config_driven.param_types` 读取需配置化的时间参数类型清单（retry_wait / poll_interval / timeout / cooldown / backoff_base / max_backoff），代码中所有 `time.sleep()` / `asyncio.sleep()` / `timeout=` / `wait_for(timeout=)` 调用必须对照清单配置化：
   ```python
   # ✅ 正确：从 config 读取
   await asyncio.sleep(get_config().task_scheduler.error_retry_wait_seconds)
   
   # ❌ 错误：硬编码字面量
   # await asyncio.sleep(300)
   ```

2. **配置读取强制【强制】**：所有 `time.sleep()` / `asyncio.sleep()` / `timeout=` / `wait_for(timeout=)` 的时间参数必须从 `get_config()` 读取，禁止字面量数字。

3. **边界值校验【强制】**：Pydantic 配置类必须用 `Field(300, ge=10, le=3600)` 标注边界值，超出范围触发 ValidationError：
   ```python
   # ✅ 正确：边界值校验
   class TaskSchedulerConfig(BaseModel):
       error_retry_wait_seconds: int = Field(300, ge=10, le=3600)
       poll_interval_seconds: int = Field(60, ge=5, le=3600)
       timeout_seconds: int = Field(30, ge=1, le=600)
   ```

4. **默认值兜底【强制】**：配置读取失败（如配置文件缺失/字段未定义）必须 `try/except` 兜底默认值（参考 step 188 配置化阈值兜底范式），禁止配置缺失即崩溃：
   ```python
   # ✅ 正确：try/except 兜底
   def _get_retry_wait(self) -> int:
       try:
           return get_config().task_scheduler.error_retry_wait_seconds
       except Exception:
           return 300  # 回退默认值
   
   # ❌ 错误：配置缺失即崩溃
   # wait = get_config().task_scheduler.error_retry_wait_seconds  # AttributeError
   ```

5. **配置驱动【强制】**：参数类型清单、边界值、默认值从 `config.yaml#time_param_config_driven` 节点管理。

**配置驱动**：参数在 `config.yaml` 的 `time_param_config_driven` 节点管理，包含 `param_types`（需配置化的参数类型清单）、`require_ge_le`（是否强制 ge/le 边界校验，默认 true）、`require_try_except`（是否强制 try/except 兜底，默认 true）、`forbidden_patterns`（禁止模式列表，如 `time.sleep([0-9]` / `asyncio.sleep([0-9]` / `timeout=[0-9]`）。

**适用场景**：所有 `time.sleep` / `asyncio.sleep` / `timeout` / `wait_for(timeout=)` 调用；异常重试/退避策略；轮询/心跳间隔；超时控制；冷却期/防抖期。

**不适用场景**：单元测试中的 `time.sleep(0.1)`（测试固定延迟）；性能基准测试中的精确计时；日志刷新间隔（<100ms 无业务影响）；UI 动画时长（前端 CSS transition）。

**历史教训**：`scheduler.py` 异常重试等待硬编码 `return 300`，所有任务异常后必须等 5 分钟才能重试。用户反馈「任务失败后等太久」，排查发现硬编码无法配置。修复后在 `TaskSchedulerConfig` 加 `error_retry_wait_seconds: int = Field(300, ge=10, le=3600)` 字段，所有硬编码改为 `get_config().task_scheduler.error_retry_wait_seconds`。

**判断信号（review 触发条件）**：
- `grep "time\.sleep\([0-9]" <file>` 命中 → 硬编码 sleep
- `grep "asyncio\.sleep\([0-9]" <file>` 命中 → 硬编码 await sleep
- `grep "timeout=[0-9]" <file>` 命中 → 硬编码 timeout
- `grep "Field\(.*ge=.*le=" <config_file>` 缺时间字段 → 边界校验缺失
- `grep "get_config\(\)\.\w+\.\w+_seconds" <file>` 但无 `try.*except` 包裹 → 缺兜底


---

### step 189：参数链闭环验证规范【强制，meta-rule #52 落地】🆕v4.37

189. **参数链闭环验证规范【强制，meta-rule #52 落地】🆕v4.37**
    - 过滤类参数（filter / constraint 语义）从 API 接收后必须存在对应的消费点（函数调用 / SQL WHERE / 条件分支），**禁止**"参数已接收但未被消费"，否则会出现"用户调整过滤参数但结果不变"的隐蔽 bug
    - **与 step 118 字段全链路消费规范的边界**：
      - step 118 关注"字段在前端/后端/DB 间全链路消费"
      - 本规范关注"过滤类参数在 API 接收点 → 消费点 → 结果集的闭环验证"
    - **三段闭环验证**：
      | 验证点 | 检查内容 | 典型违规 |
      |--------|----------|----------|
      | 接收点 | API endpoint 函数签名声明参数 | 函数签名无 `market_ratio` 参数 |
      | 消费点 | 参数实际参与过滤条件构建（WHERE / 条件分支 / 函数调用） | 参数在签名中但未调用 `PriceStrategy.check(market_ratio=...)` |
      | 结果集 | 单元测试验证"传参 vs 不传参"结果集差异 | 无 `with_param` / `without_param` 对比用例 |
    - **元数据参数豁免**：分页参数（page / page_size / limit / offset）与排序参数（sort / order）属于标识/定位类参数，不在本规范范围
    - **判断信号**：
      - `grep "<param_name>" <file>` 仅命中函数签名和 return 语句但未命中函数调用 → 视为可疑
      - API 接收 `market_ratio` 参数但未调用 `PriceStrategy.check(market_ratio=...)` → 违规
      - 单元测试无 `with_param` / `without_param` 对比用例 → 视为闭环验证缺失
      - 参数命名暗示过滤语义（含 `filter_` / `range_` / `min_` / `max_` / `ratio_` 前缀）必须闭环
    - **修复模式**：
      ```python
      # ❌ 错误：参数悬挂（接收未消费）
      @router.get("/api/evaluations")
      async def list_evaluations(
          market_ratio: float | None = Query(None),  # 接收点
      ):
          items = await repo.list_all()  # 消费点缺失！market_ratio 未参与
          return {"items": items, "market_ratio": market_ratio}  # 仅 return 中出现

      # ✅ 正确：三段闭环
      @router.get("/api/evaluations")
      async def list_evaluations(
          market_ratio: float | None = Query(None),  # 接收点
      ):
          items = await repo.list_all()
          if market_ratio is not None:
              # 消费点：实际参与过滤
              items = [i for i in items if PriceStrategy.check(market_ratio=market_ratio, price=i.price)]
          return {"items": items}  # 不在 return 中重复 market_ratio

      # ✅ 正确：单元测试验证结果集差异
      async def test_market_ratio_filter_effective():
          # 不传参
          res_without = await client.get("/api/evaluations")
          # 传参
          res_with = await client.get("/api/evaluations?market_ratio=0.85")
          # 结果集必须不同（否则过滤未生效）
          assert len(res_with.json()["items"]) <= len(res_without.json()["items"])
          assert any(i["price"] <= 800 for i in res_with.json()["items"])  # 业务校验
      ```
    - **配置参数**：`param_chain_check.metadata_param_whitelist`（默认 `['page', 'page_size', 'limit', 'offset', 'sort', 'order']`，元数据参数白名单）、`param_chain_check.filter_prefixes`（默认 `['filter_', 'range_', 'min_', 'max_', 'ratio_']`，强制闭环的参数名前缀）、`param_chain_check.require_unit_test`（默认 `true`，强制单元测试对比用例）、`param_chain_check.exemption_endpoints`（豁免 endpoint 列表）在 `config.yaml` 的 `param_chain_check` 节点管理
    - **适用**：所有有过滤参数的列表查询 API（list_evaluations / list_items / search_* / list_orders）、PATCH/PUT 接口的可空字段
    - **不适用**：GET 单个资源详情（无过滤）、DELETE 接口（参数仅定位资源）、仅作元数据返回的字段（total_count）、创建类 POST 接口
    - **历史教训**：`evaluations_list.py` 接收 `market_ratio=0.85` 参数但未调用 `PriceStrategy.check`，导致调整到 0.85 后仍能查出价格上限 800 的商品，用户误以为是价格范围 600-800 的问题，实际是 market_ratio 过滤未生效。修复：新增 `_resolve_market_ratio` / `_compute_eval_market_median` / `_filter_market_ratio` 三个辅助函数形成闭环


---


### step 250：OVERWRITE-SET-SELECTION-01 字段覆盖集合选择标准规范【强制】🆕v4.52.0

**背景**：官方采集流程 `api_evaluations.py` 用 `_ALWAYS_OVERWRITE` 集合定义"强制覆盖"字段，`image_urls` 被放入该集合。采集未获取到图片时写入 `None`，直接覆盖 items 表已有图片数据，导致官方采集后商品图片消失。

**问题**：数据合并有"强制覆盖"（`_ALWAYS_OVERWRITE`）和"新值为空时保留旧值"（`_coalesce`）两种策略。字段被错误放入"强制覆盖"集合时，采集未获取到该字段会写入 `None`/空值，覆盖已有有效数据，导致数据丢失。

**规范**：

1. **强制覆盖集合字段选择标准【强制】**：`_ALWAYS_OVERWRITE` 集合只放"每次采集必定获取到 + 新值更准确"的字段：
   - ✅ **采集时刻字段**：`task_id`（任务标识）、`publish_time`（发布时间）、`view_cnt`/`want_cnt`（浏览/想要数，实时更新）
   - ✅ **来源信息字段**：`region`（地区）、`seller_id`（卖家 ID）
   - ❌ **采集可能未获取的字段**：`image_urls`（图片可能未加载）、`thumb_url`（缩略图可能未获取）、`description`（描述可能为空）
   - ❌ **稳定性高的字段**：`seller_nick`（卖家昵称，无需频繁更新）

2. **采集可能未获取的字段必须走 _coalesce【强制】**：采集可能返回 `None`/空值但旧值有价值的字段，必须走 `_coalesce` 逻辑（新值为空时保留旧值），禁止放入 `_ALWAYS_OVERWRITE`：
   ```python
   # ✅ 正确：image_urls 走 _coalesce，采集未获取时保留旧值
   _ALWAYS_OVERWRITE = {"task_id", "publish_time", "view_cnt", "want_cnt", "region", "seller_id"}
   # image_urls 不在此集合中——采集未获取到图片时应保留旧值，
   # 而非用 None 覆盖清空已有图片数据（走 _coalesce 逻辑）

   def _merge_item_data(new_row, existing_row):
       for field in _ALWAYS_OVERWRITE:
           # 强制覆盖：新值无论是否为空都覆盖
           if field in new_row:
               existing_row[field] = new_row[field]
       for field in _COALESCE_FIELDS:
           # coalesce：新值为空时保留旧值
           if new_row.get(field) is not None:
               existing_row[field] = new_row[field]
   ```

3. **集合定义必须注释字段选择理由【强制】**：`_ALWAYS_OVERWRITE` 和 `_coalesce` 集合定义必须注释每个字段的选择理由，说明为什么强制覆盖或保留旧值：
   ```python
   # 允许覆盖的字段（官方采集应优先更新采集时刻 + 来源信息）
   # 数字 0 是合法值（_is_blank 已修正不再当作 blank），所以这些字段
   # 走 ALWAYS_OVERWRITE 不会因新值为 0 而误判为"缺失"
   # 注意：image_urls 不在此集合中——采集未获取到图片时应保留旧值，
   # 而非用 None 覆盖清空已有图片数据（走 _coalesce 逻辑）
   _ALWAYS_OVERWRITE = {"task_id", "publish_time", "view_cnt", "want_cnt", "region", "seller_id"}
   ```

4. **集合字段选择必须配置化【强制】**：`_ALWAYS_OVERWRITE` 和 `_coalesce` 集合的字段清单从 `config.yaml` 读取，禁止硬编码：
   ```yaml
   overwrite_set_selection:
     always_overwrite_fields:
       - task_id        # 采集时刻：任务标识
       - publish_time   # 采集时刻：发布时间
       - view_cnt       # 采集时刻：浏览数（实时更新）
       - want_cnt       # 采集时刻：想要数（实时更新）
       - region         # 来源信息：地区
       - seller_id      # 来源信息：卖家 ID
     coalesce_fields:
       - image_urls     # 采集可能未获取：图片 URL 列表
       - thumb_url      # 采集可能未获取：缩略图 URL
       - description    # 采集可能未获取：商品描述
       - seller_nick    # 稳定性高：卖家昵称
     selection_criteria:
       always_overwrite: "每次采集必定获取到 + 新值更准确"
       coalesce: "采集可能返回空值但旧值有价值"
   ```

5. **新增字段必须明确归属集合【强制】**：新增数据字段时必须明确归属 `_ALWAYS_OVERWRITE` 还是 `_coalesce`，并在 PR 描述中说明选择理由。

**判断信号**：
- `grep "_ALWAYS_OVERWRITE\|_COALESCE" src/` 找到集合定义 → 检查每个字段的选择理由
- 字段在 `_ALWAYS_OVERWRITE` 中 + 采集可能返回 `None`/空 → 视为违规（应走 `_coalesce`）
- 集合定义无注释说明字段选择理由 → 视为违规
- 集合字段清单硬编码而非从配置读取 → 视为违规
- 采集后数据字段被 `None` 覆盖导致数据丢失 → 疑似字段归属错误

**反模式**：
```python
# ❌ image_urls 在 _ALWAYS_OVERWRITE 中，采集未获取时 None 覆盖旧值
_ALWAYS_OVERWRITE = {"task_id", "publish_time", "view_cnt", "want_cnt",
                     "region", "seller_id", "image_urls"}  # image_urls 不应在此！
# 采集未获取到图片时：existing_row["image_urls"] = None → 图片数据丢失

# ❌ 集合定义无注释
_ALWAYS_OVERWRITE = {"task_id", "publish_time", "view_cnt", "want_cnt",
                     "region", "seller_id"}
# 不知道为什么这些字段强制覆盖，新增字段时无法判断归属

# ❌ 集合字段硬编码而非配置化
_ALWAYS_OVERWRITE = {"task_id", "publish_time"}  # 硬编码，新增字段需改代码
```

**配置参数**：`overwrite_set_selection.always_overwrite_fields`（默认 `['task_id', 'publish_time', 'view_cnt', 'want_cnt', 'region', 'seller_id']`，强制覆盖字段清单）、`overwrite_set_selection.coalesce_fields`（默认 `['image_urls', 'thumb_url', 'description', 'seller_nick']`，coalesce 字段清单）、`overwrite_set_selection.selection_criteria.always_overwrite`（默认 `"每次采集必定获取到 + 新值更准确"`，强制覆盖选择标准）、`overwrite_set_selection.selection_criteria.coalesce`（默认 `"采集可能返回空值但旧值有价值"`，coalesce 选择标准）、`overwrite_set_selection.require_comment`（默认 `true`，是否强制注释选择理由）在 `config.yaml` 的 `overwrite_set_selection` 节点管理

**适用场景**：所有有 `_ALWAYS_OVERWRITE`/`_coalesce` 双策略的数据合并场景、采集-存储链路（官方采集→items/sellers 表）、缓存更新（新值可能为空的场景）、任何"强制覆盖 vs 保留旧值"的字段选择决策

**不适用场景**：单一覆盖策略（无 `_coalesce` 逻辑，所有字段都强制覆盖）、审计日志（需保留全量历史，不走覆盖逻辑）、纯新增场景（无旧值可保留）

**历史教训**：官方采集流程 `api_evaluations.py` 中 `image_urls` 被放入 `_ALWAYS_OVERWRITE` 集合，采集未获取到图片时写入 `None`，覆盖 items 表已有图片数据，导致官方采集后商品图片消失。将 `image_urls` 移出 `_ALWAYS_OVERWRITE` 走 `_coalesce` 逻辑后，采集未获取图片时保留旧值，图片不再丢失。与 step 17（字段覆盖策略）互补：step 17 定义分类覆盖策略的基本原则，本规则细化 `_ALWAYS_OVERWRITE` 集合的字段选择标准。与 step 240（快照与最新值职责分离）互补：step 240 聚焦"过滤用快照 vs 展示用最新值"，本规则聚焦"强制覆盖 vs 保留旧值的字段选择"。

---

### step 251：配置字段全链路覆盖检查（CONFIG-FIELD-FULL-CHAIN-COVERAGE）

> **meta-rule**：#86
> **来源**：2026-07-11 智能客服新建会话乱码 Bug 复盘
> **适用**：新增 chatbot_config 或其他 config 表字段
> **不适用**：非配置类字段（业务数据）、只读字段（created_at）、内部系统字段

**规则**：新增/修改配置字段时，必须同步检查并覆盖以下 5 层，任一层缺失会导致脏值无法清除或用户无法修改：

| # | 层 | 检查方式 | 缺失后果 |
|---|---|---|---|
| 1 | DB key | `SELECT key FROM <config_table> WHERE key=?` | 字段无法持久化 |
| 2 | 后端 get_config | `grep "welcome_message" api_chatbot_config.py` | 前端读不到字段值 |
| 3 | 后端 update_config | `grep "welcome_message" _UPDATABLE_KEYS` | 前端 PUT 被拒绝 |
| 4 | 前端 types.ts | `grep "welcome_message" types.ts` | TS 编译报错或类型不匹配 |
| 5 | 前端 Config.tsx UI | `grep "welcome_message" Config.tsx` | 脏值无法从界面清除 |

**判断逻辑**：
```
对于每个新增配置字段：
  1. DB 表中是否可读写该 key？
  2. 后端 get_config 是否返回该字段？
  3. 后端 update_config 是否接受该字段的 PUT？
  4. 前端 types.ts 是否有该字段的类型定义？
  5. 前端 Config.tsx 是否有该字段的编辑 UI？
  任一答案为否 → 需要修复
```

**实战案例**：
- Bug 现象：智能客服新建会话顶部 greeting 显示 `??????????!`
- 根因：DB 中 `welcome_message` 被写入占位串，但 Config.tsx 缺少编辑 UI（第 5 层缺失），用户无法从界面清除脏值
- 修复：补全 5 层链路，特别是 Config.tsx 增加 TextArea + 防抖保存

---

### step 252：空值=恢复默认语义（EMPTY-MEANS-RESET）

> **meta-rule**：#87
> **来源**：2026-07-11 智能客服乱码 Bug 修复中的增量需求"恢复默认"按钮
> **适用**：有默认值回退的 string 类配置字段（welcome_message, notify_text, contact 等）
> **不适用**：必填字段、数值型字段（0≠null）、布尔型字段（false≠null）

**规则**：对于有"默认值回退"语义的 string 类配置字段：

1. **后端 update_config**：收到空 value 时调用 `delete_config(key)` 而非 `set_config(key, '')`
   - 空串写入 DB 会被 `get_config` 当作有效覆盖值返回，污染前端状态
   - DELETE 后 `get_config` 读到 None，回退到代码默认值

2. **后端 get_config**：DB 值为 None 时回退到代码默认值
   - `result["welcome_message"] = db_overrides.get(KEY_WELCOME_MESSAGE)` # None 时前端用 placeholder

3. **前端 Config.tsx**：提供"恢复默认"按钮
   - 点击 → `updateConfig(key, '')` → 500ms 防抖后 PUT 空串 → 后端 DELETE
   - 当前值已为默认（null/空）时按钮 `disabled`

4. **前端 types.ts**：字段类型为 `string | null`
   - null 表示"使用默认"，空串不应出现（后端 DELETE 而非写入空串）

**判断逻辑**：
```
对于每个有默认值回退的 string 类配置字段：
  1. 后端 update_config 空 value 是否走 delete_config 而非 set_config？
  2. 后端 get_config 在 DB 值为 None 时是否回退到默认值？
  3. 前端 Config.tsx 是否有"恢复默认"按钮？
  4. 前端 types.ts 字段类型是否为 string | null？
  任一答案为否 → 需要修复
```

**反模式**：
- ❌ `set_config(key, '')` — 写入空串到 DB，get_config 返回空串覆盖默认值
- ❌ 前端无"恢复默认"按钮 — 用户只能手动删除 TextArea 内容
- ❌ 字段类型为 `string`（非 `string | null`）— null 语义丢失

**实战案例**：
- Bug 现象：用户无法将 welcome_message 恢复为默认文案
- 根因：update_config 空值写入空串到 DB，get_config 返回空串（而非回退到默认值）
- 修复：update_config 空值短路走 delete_config + Config.tsx 增加"恢复默认"按钮


---

### step 253：缓存守卫三原则（CACHE-GUARD-3RULES，meta-rule #104 落地）【强制】🆕v4.62.0

**背景**：缓存策略存在三个问题：(1) `_LIVE_CACHE_TTL` 硬编码为 60 秒而非从 config 读取；(2) 空结果（0 记录）被缓存，导致缓存有效期内返回空列表掩盖实时数据恢复；(3) 缓存写入守卫与业务逻辑耦合（`if filtered: cache_write` vs `if items: db_write`）。

**规范**：

1. **Cache TTL 必须从 config.yaml 读取，禁止模块级硬编码常量【强制】**
   - 禁止：`_LIVE_CACHE_TTL = 60`
   - 正确：`ttl = get_config().cache.live_search_ttl`

2. **空结果（0 records）不缓存【强制】**——避免缓存有效期内返回空列表掩盖实时数据恢复
   - 禁止：`cache[key] = []`（无论结果是否为空都缓存）
   - 正确：`if filtered: cache[key] = filtered`（仅非空时缓存）

3. **缓存写入守卫独立于业务逻辑【强制】**——缓存条件应独立于业务条件
   - 禁止：`if filtered: cache[key] = filtered; if items: db.write(items)`（缓存和 DB 写入共享 filtered 条件）
   - 正确：`if filtered: cache[key] = filtered`（缓存守卫基于缓存语义）；`if items: db.write(items)`（DB 写入基于业务语义）

**判断信号**：
- `grep "_TTL\s*=" <py>` 命中硬编码常量 → 违规
- `grep "cache\[.*\]\s*=" <py>` 无前置空结果检查 → 检查是否缓存空结果
- 缓存写入条件与 DB/业务写入条件相同 → 检查是否耦合

**配置参数**：`cache_guard.ttlConfigPath`（默认 `'cache.live_search_ttl'`，TTL 配置路径）、`cache_guard.cacheEmptyResult`（默认 `false`，是否缓存空结果）、`cache_guard.guardIndependent`（默认 `true`，缓存守卫是否独立于业务逻辑）在 `config.yaml` 的 `cache_guard` 节点管理

**适用**：所有业务数据缓存（搜索结果/列表查询/统计数据）

**不适用**：纯计算缓存（无实时性要求）、静态资源缓存（前端 CDN）、配置缓存（变更频率极低）

**历史教训**：`api_task_links.py` 的 `_LIVE_CACHE_TTL` 硬编码为 60 秒，后改为从 config.yaml 读取；实时搜索空结果被缓存，导致缓存有效期内返回空列表掩盖数据恢复；缓存写入用 `if filtered:` 与 DB 写入 `if items:` 共享条件，导致缓存语义被业务逻辑污染

---
