# Security 编码规范
> 本文件归档 xianyu-hunter-dev skill 中与「security」主题相关的编码规范。
> 主索引见 [SKILL.md](../../../SKILL.md) 的"step 索引表"，元规范见 [meta-rules.md](../../../references/meta-rules.md)。

---

### step 5：功能实现约束【强制】

5. **功能实现约束【强制】**
   - 编码必须遵守 [项目规则](../../../references/project-rules.md) 中的安全、并发、命名硬约束
   - 涉及 token 校验必须使用 `hmac.compare_digest`（防时序攻击）
   - 涉及日志禁止打印敏感字段（authorization/cookie/xh_token/set-cookie）
   - 涉及 SQLite 迁移必须保持幂等（已存在则跳过）
   - 涉及 asyncio 任务必须保留引用防 GC（`self._task = asyncio.create_task(...)`）
   - 涉及 `asyncio.CancelledError` 必须用 `with suppress(asyncio.CancelledError)` 包裹 await


---

### step 7：安全调用检查【强制】

7. **安全调用检查【强制】**
   - 检查所有外部接口调用是否已做空值/边界判断
   - 检查是否存在未处理的异常分支
   - 确认敏感数据未在日志中明文输出（`_SENSITIVE_HEADERS` 脱敏）
   - 验证权限校验逻辑是否完整（`BearerAuthMiddleware` 白名单是否需追加）
   - SQL 注入防护：LIKE 用 `_escape_like`，表名/列名用 `_IDENT_RE` 白名单校验
   - 路径遍历防护：用户输入用 `_USER_ID_RE` 等正则校验
   - 🆕v4.0 外部链接安全：`target="_blank"` 必须配 `rel="noopener noreferrer"`（防 `window.opener` 钓鱼 + 不泄露 Referer）


---

### step 26：硬编码属性禁用【强制】🆕v4.3

26. **硬编码属性禁用【强制】🆕v4.3**
    - 写入外部系统（浏览器 Cookie、HTTP 响应头、数据库列）的属性必须根据数据语义动态设置，**禁止**硬编码固定值
    - **判断信号**：批量设置属性时使用固定值（如所有 Cookie 强制 `httpOnly:True`）而非从数据派生
    - **修复模式**：属性值从数据语义派生（如 identity 层 Cookie 的 `httpOnly` 根据 Cookie 名称判断），或通过配置文件管理属性映射
    - **适用**：Cookie/HTTP 头/数据库列属性、Playwright cookie 对象构造
    - **不适用**：项目固定常量（如域名、路径前缀）、安全必需的固定值（如 `path: "/"`）
    - **历史教训**：`cookie_rotator._batch_write` 强制 `httpOnly:True` + `secure:True`，导致 `unb`/`cookie2` 等 JS 可读 Cookie 被设为 httpOnly，页面 JS 读取失败触发闲鱼检测异常


---

### step 29：提示信息可操作性【强制】🆕v4.3

29. **提示信息可操作性【强制】🆕v4.3**
    - 面向用户的错误提示中引用的端点/方法/配置项/页面路径必须实际存在，提示应指向可操作的修复路径
    - **判断信号**：错误信息中包含 URL/方法名/配置项/路由路径引用
    - **修复模式**：提示中只引用已实现的端点；引用路由路径时确认前端路由已注册；提供具体的修复操作（如"请点击 X 按钮重新初始化"）
    - **适用**：所有面向用户的错误信息（API 响应、前端错误提示、日志中的用户指引）
    - **不适用**：内部调试日志（developer-facing）、堆栈跟踪
    - **历史教训**：`/api/anticrawl/health` 端点提示"请先调用 /api/anticrawl/health/configure"，但该端点从未实现，用户无法按提示操作


---

### step 30：加密升级退化策略模式【强制】🆕v4.4

30. **加密升级退化策略模式【强制】🆕v4.4**
    - 依赖外部进程/资源的加密机制（如 Chrome v20 App-Bound Encryption）无法离线解密时，必须选择运行时接管（CDP/IPC）而非等待离线解密方案出现
    - **判断信号**：加密依赖外部进程状态 + IElevator/COM 接口 + 本地密钥不可访问 + 文档明确标注"App-Bound"
    - **修复模式**：检测到 v20 加密 → 探测 CDP 端点可达性 → `Playwright.connect_over_cdp()` 接管运行中浏览器 → 通过 `Network.getAllCookies` 获取解密后 cookie
    - **配置参数**：加密方案识别标志、CDP 端口、降级方案优先级在 `config/encryption.yaml` 的 `encryption_solutions` 节点管理（不硬编码）
    - **适用**：依赖外部进程的加密（Chrome v20）、DRM 保护机制、需要在线状态验证的场景
    - **不适用**：可离线解密的加密（v10 AES）、依赖本地密钥的对称加密、静态资源处理
    - **历史教训**：浏览器 Cookie 导入增强任务中，v20 App-Bound Encryption 无法用传统 `CryptUnprotectData` 离线解密，调研后选择 CDP 接管方案（方案 A）而非 IElevator COM（方案 B）或智能降级（方案 C）


---

### step 31：多配置文件发现模式【强制】🆕v4.4

31. **多配置文件发现模式【强制】🆕v4.4**
    - 发现多个同名配置/profile 时，优先从结构化元数据（如 `Local State` JSON 的 `profile.info_cache`）读取，失败则 fallback 到目录扫描
    - **判断信号**：需发现多个同名配置/profile + 存在结构化索引文件 + 用户可能使用非默认 profile
    - **修复模式**：读取 `Local State` → 解析 `profile.info_cache` 字典 → 失败则扫描 `User Data/` 子目录匹配 `Profile *` 模式 → 按优先级排序（有目标 cookie → Default → 名称）
    - **配置参数**：主数据源路径、fallback 扫描目录、profile 目录正则模式、优先级排序规则在 `config/discovery.yaml` 管理
    - **适用**：浏览器多 profile 发现、多账户隔离环境、多环境配置加载
    - **不适用**：单一配置场景、严格顺序访问场景、路径已知且唯一的场景
    - **历史教训**：用户实际使用 `Profile 1` 而非 `Default`，原实现只读取 `Default` 导致 cookie 导入失败


---

### step 32：文件锁绕过模式（SQLite immutable）【强制】🆕v4.4

32. **文件锁绕过模式（SQLite immutable）【强制】🆕v4.4**
    - 并发访问被锁文件时，使用 SQLite URI `immutable=1` 参数打开只读数据库，绕过 Windows 文件锁机制
    - **判断信号**：Windows 文件锁报错（`database is locked` / `unable to open database`）+ 只读访问需求 + SQLite 数据库
    - **修复模式**：构建 URI `file:./Cookies?immutable=1` → 用 `sqlite3.connect(uri=True)` 打开 → 仅执行 SELECT 查询
    - **配置参数**：`immutable_flag` 默认 `true`，`lock_timeout_ms` 在 `config/database.yaml` 管理
    - **适用**：浏览器 cookie 数据库并发访问、Windows 文件锁定机制、需要只读访问的共享资源
    - **不适用**：需要写入的场景、Linux 文件锁（建议用 `flock`）、原子写场景
    - **历史教训**：浏览器运行时持有 `Cookies` 数据库写锁，传统 `sqlite3.connect()` 打开失败，改用 `immutable=1` 后可并发读取


---

### step 71：状态码语义精细化【强制】🆕v4.12

71. **状态码语义精细化【强制】🆕v4.12**
    - HTTP 状态码必须按语义精细化区分：`401` 未登录 / `403` 权限不足 / `440` Cookie 过期（需重新登录）/ `441` Token 过期（需刷新）/ `504` 网关超时，**禁止**所有认证失败都映射为 `401` 导致前端无法区分"未登录"与"登录态过期"
    - **判断信号**：`raise HTTPException(status_code=401)` 出现在 Cookie 检查 / Token 刷新 / 登录校验等多处 → 必须按语义区分状态码
    - **修复模式**：
      ```python
      # ✅ 按语义区分状态码
      if not identity_cookies:
          raise HTTPException(401, "未登录，请先登录")  # 完全未登录
      if is_cookie_expired(identity_cookies):
          raise HTTPException(440, "Cookie 已过期，请重新登录")  # 登录态过期
      if is_m5tk_expired(session_cookies):
          raise HTTPException(441, "会话 Token 已过期，请刷新")  # 临时 token 过期
      if not has_permission(user, action):
          raise HTTPException(403, "权限不足")  # 已登录但无权限
      ```
    - **配置参数**：`status_code_semantics.mapping`（错误场景到状态码的映射，如 `cookie_expired → 440`、`token_expired → 441`、`not_logged_in → 401`、`permission_denied → 403`）、`status_code_semantics.frontend_actions`（状态码到前端动作的映射，如 `401 → redirect_login`、`440 → redirect_relogin`、`441 → refresh_token`）在 `config.yaml` 的 `status_code_semantics` 节点管理
    - **适用**：所有认证相关 API（登录/Cookie 校验/Token 刷新/权限检查）；SSE error 事件的状态码字段
    - **不适用**：业务错误（如 404 资源不存在、409 状态冲突、422 参数校验失败）；纯内部 API
    - **历史教训**：Cookie 过期、Token 过期、未登录全部映射为 `401`，前端无法区分应"跳转登录页"还是"刷新 Token"，导致用户反复被踢出登录


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

### step 103：凭据同步桥接规范（yaml→keyring）【强制】🆕v4.19

**背景**：用户在通知渠道菜单填写钉钉 webhook 后，自动抢单成功却未收到钉钉通知。根因：前端写 yaml，`DingTalkNotifier` 从 keyring 读取，但中间无同步桥接，`is_configured=False`，渠道被 `NotifierHub` 静默跳过。同时 keyring KEY 常量名 `KEY_DINGTALK_WEBHOOK="dingtalk_webhook_url"` 与 yaml 字段名 `dingtalk_webhook` 不一致，即使有同步也会写错位置。

**规范**：

1. **双存储介质的凭据必须有显式同步桥接函数**
   - 前端写入 yaml，运行时从 keyring 读取的场景，必须在 DI 容器中添加同步函数
   - 同步时机：DI 容器初始化 Notifier/Client 之前必须先调用同步函数
   - 同步函数必须重新读主数据源（yaml），不依赖调用方传参

2. **keyring KEY 常量名必须与 yaml 字段名 1:1 对齐**
   - 禁止出现 `KEY_DINGTALK_WEBHOOK = "dingtalk_webhook_url"` 而 yaml 字段为 `dingtalk_webhook` 的情况
   - CI 检查：扫描 keyring KEY 常量名与 yaml 字段名对齐

3. **同步映射表必须集中在模块顶部声明**
   - 禁止散落在多个函数内的硬编码映射
   - 映射表必须配置驱动（在 `config.yaml` 的 `credential_sync_bridge.yaml_to_keyring_map` 节点管理）

4. **测试必须清理 keyring 避免污染**
   - 测试 setup/teardown 必须清理 keyring 中的测试凭证
   - 测试中调用 `wire_notifier()` 后，后续单测可能因 keyring 污染失败

5. **同步失败必须告警**
   - `secrets.set_secret()` 失败必须 `logging.warning()` 告警
   - 不允许静默吞掉同步失败错误

**判断逻辑**：

- `grep "secrets.get_secret" src/xianyu_hunter/` 找到读取点 → 必须有对应的 `secrets.set_secret()` 同步点
- keyring KEY 常量名与 yaml 字段名不一致 → 视为违规
- DI 容器初始化 Notifier 之前无同步调用 → 视为违规
- `grep "extra=.allow." src/xianyu_hunter/` 配置模型用 `extra='allow'` → 视为可疑

**反例**：

```python
# ❌ 错误：Notifier 直接从 keyring 读取但 yaml 从未同步
KEY_DINGTALK_WEBHOOK = "dingtalk_webhook_url"  # 与 yaml 字段名不一致

class DingTalkNotifier:
    def __init__(self):
        self.webhook_url = secrets.get_secret(KEY_DINGTALK_WEBHOOK)  # 永远为 None
        # is_configured = False，渠道被静默跳过
```

**正例**：

```python
# ✅ 1. keyring KEY 常量名与 yaml 字段名 1:1 对齐
KEY_DINGTALK_WEBHOOK = "dingtalk_webhook"

# ✅ 2. DI 容器初始化 Notifier 之前先同步
def wire_notifier(self) -> None:
    self._sync_yaml_credentials_to_keyring()  # 必须先同步
    self.notifier_hub = NotifierHub(channels=enabled, ...)
    self.notifier_hub.attach(self.event_bus)

def _sync_yaml_credentials_to_keyring(self) -> None:
    """把 yaml 中的明文凭证同步到 keyring"""
    from xianyu_hunter.infra import secrets
    cred_map = {
        "serverchan_send_key": secrets.KEY_SERVERCHAN,
        "pushplus_token": secrets.KEY_PUSHPLUS,
        "bark_server": secrets.KEY_BARK_SERVER,
        "bark_key": secrets.KEY_BARK_KEY,
        "telegram_bot_token": secrets.KEY_TELEGRAM_TOKEN,
        "telegram_chat_id": secrets.KEY_TELEGRAM_CHAT,
        "wecom_webhook": secrets.KEY_WECOM_WEBHOOK,
        "dingtalk_webhook": secrets.KEY_DINGTALK_WEBHOOK,
        "dingtalk_secret": secrets.KEY_DINGTALK_SECRET,
        "webhook_url": secrets.KEY_WEBHOOK_URL,
    }
    for yaml_attr, keyring_key in cred_map.items():
        yaml_value = getattr(self.config, yaml_attr, "")
        if yaml_value:
            try:
                secrets.set_secret(keyring_key, yaml_value)
            except Exception as e:
                logging.warning("同步凭据 %s 到 keyring 失败: %s", yaml_attr, e)
```

**配置参数**：`credential_sync_bridge` 节点（yaml_to_keyring_map / sync_timing / require_key_name_align）

**适用场景**：
- 双存储介质的凭据/配置同步（yaml ↔ keyring、yaml ↔ env、json ↔ 数据库）
- Notifier/Client 从 keyring 读取的场景
- 多写入入口的状态同步

**不适用场景**：
- 单一存储介质（如纯 yaml 或纯 keyring）
- 运行时计算字段（无需同步）
- 外部系统主动推送的状态（无本地写入）

**历史教训**：用户填写钉钉 webhook 后未收到通知。根因：前端写 yaml，Notifier 从 keyring 读取，无同步桥接，`is_configured=False` 静默跳过。同时 keyring KEY 常量名与 yaml 字段名不一致


---

### step 104：脱敏策略场景区分规范【强制】🆕v4.19

**背景**：通知渠道凭据字段被加入 `_REDACT_KEYS`，导致 `GET /api/config` 返回 `***`，前端无法回显用户已填写的凭据，刷新页面后输入框清空。同时分享/导出场景未脱敏凭据，存在泄露风险。

**规范**：

1. **同一字段在不同 API 场景下脱敏策略必须区分**
   - `GET /api/config`（前端回显，**不脱敏**凭据）：用 `_REDACT_KEYS` 仅脱敏真正敏感字段（如 cookie/session_id）
   - `/share`/`/export`（分享导出，**必须脱敏**凭据）：用 `_SHARE_REDACT_PATHS` 脱敏凭据路径
   - 日志输出（**必须脱敏**凭据）：用 `_SENSITIVE_KEYS` 过滤

2. **三个脱敏集合必须分离**
   - `_REDACT_KEYS`：全局脱敏字段集（仅前端无需回显的真正敏感字段，如 cookie/session_id）
   - `_SHARE_REDACT_PATHS`：分享场景脱敏路径集（凭据字段的嵌套路径）
   - `_SENSITIVE_KEYS`：日志脱敏字段集（所有凭据字段）

3. **凭据字段必须从 `_REDACT_KEYS` 移除**
   - 凭据字段需在前端回显，不能全局脱敏
   - 凭据字段必须加入 `_SHARE_REDACT_PATHS` 和 `_SENSITIVE_KEYS`

4. **UI 层用 `Input.Password` 组件隐藏敏感内容**
   - 前端层防护：用 `Input.Password` 组件显示凭据（默认隐藏，点击眼睛图标显示）
   - 不依赖后端脱敏（后端返回明文，前端 UI 层隐藏）

5. **脱敏策略必须配置驱动**
   - 三个脱敏集合在 `config.yaml` 的 `redact_strategy` 节点管理
   - 场景到字段集的映射在 `redact_strategy.scenario_field_map` 管理

**判断逻辑**：

- API 返回字段被脱敏但前端需要回显 → 必查 `_REDACT_KEYS` 是否包含该字段
- 分享/导出场景未脱敏凭据 → 必查 `_SHARE_REDACT_PATHS` 是否包含该字段
- 日志中打印凭据明文 → 必查 `_SENSITIVE_KEYS` 是否包含该字段
- 同一字段在所有 API 场景脱敏策略一致 → 视为可疑（未区分场景）

**反例**：

```python
# ❌ 错误：所有 API 都用 _REDACT_KEYS 脱敏凭据
_REDACT_KEYS = frozenset({
    "cookie", "session_id",
    "serverchan_send_key", "pushplus_token", "bark_key",  # 凭据字段也被脱敏
    "dingtalk_webhook", "dingtalk_secret",
})

@app.get("/api/config")
async def get_config():
    return _redact(config.model_dump(), _REDACT_KEYS)  # 前端拿到 ***，无法回显
```

**正例**：

```python
# ✅ 三个脱敏集合分离
_REDACT_KEYS = frozenset({
    "cookie", "cookies", "session_id",  # 仅前端无需回显的真正敏感字段
})
_SHARE_REDACT_PATHS = [
    ("notifier", "channels"),
    ("serverchan_send_key",),
    ("pushplus_token",),
    ("bark_server",),
    ("bark_key",),
    ("telegram_bot_token",),
    ("telegram_chat_id",),
    ("wecom_webhook",),
    ("dingtalk_webhook",),
    ("dingtalk_secret",),
    ("webhook_url",),
    ("browser", "user_data_dir"),
]
_SENSITIVE_KEYS = frozenset({
    "serverchan_send_key", "pushplus_token", "bark_key", "bark_server",
    "telegram_bot_token", "telegram_chat_id", "wecom_webhook",
    "dingtalk_webhook", "dingtalk_secret", "webhook_url",
    "openai_api_key",
})

# GET /api/config 不脱敏凭据（前端需回显）
@app.get("/api/config")
async def get_config():
    return config.model_dump()

# /share 端点用 _SHARE_REDACT_PATHS 脱敏
@app.post("/share")
async def share_config():
    data = config.model_dump()
    return _redact_paths(data, _SHARE_REDACT_PATHS)
```

**配置参数**：`redact_strategy` 节点（scenarios / scenario_field_map / ui_protection_components）

**适用场景**：
- 所有需要脱敏的敏感字段（凭据、Cookie、Token、用户隐私数据）
- 多场景 API 返回相同字段但脱敏策略不同
- 前端需回显但分享需脱敏的场景

**不适用场景**：
- 单一场景的字段（所有 API 都需脱敏或都不需脱敏）
- 非敏感字段（如配置项的开关状态）
- 前端纯展示字段（无后端写入需求）

**历史教训**：通知渠道凭据字段被加入 `_REDACT_KEYS`，导致 `GET /api/config` 返回 `***`，前端无法回显用户已填写的凭据。修复后将凭据字段从 `_REDACT_KEYS` 移除（前端需回显），同时扩展 `_SHARE_REDACT_PATHS` 和 `_SENSITIVE_KEYS`（分享和日志仍脱敏），前端用 `Input.Password` 组件隐藏内容


---

### step 105：第三方平台 API 兼容性规范【强制】🆕v4.19

**背景**：钉钉/企业微信等第三方平台对 markdown 子集支持不同，企业微信仅支持 `#/[]()/**/`/>/<font>` 子集，直接发送标准 markdown 会导致格式错乱或被截断。

**规范**：

1. **接入第三方平台前必须查阅官方文档确认 markdown 子集**
   - 列出平台支持的所有 markdown 语法
   - 列出平台不支持的语法（如企业微信不支持表格/代码块）
   - 文档链接必须记录在代码注释中

2. **必须实现降级转换函数**
   - 标准 markdown → 平台特定 markdown 子集
   - 不支持的语法降级为支持的等价表达（如表格降级为列表）
   - 转换函数必须有单元测试覆盖所有语法分支

3. **降级转换必须配置驱动**
   - 平台支持的语法子集在 `config.yaml` 的 `third_party_markdown_compat` 节点管理
   - 降级规则映射表在 `third_party_markdown_compat.degrade_rules` 管理

4. **测试必须用真实平台样本验证**
   - 单元测试必须用平台官方文档中的示例文本验证
   - 必须覆盖所有支持的语法和不支持的语法

**判断逻辑**：

- `grep "send_markdown\|send_message" src/xianyu_hunter/modules/notifier/` 找到发送点 → 必须有降级转换函数
- 第三方 Notifier 直接发送标准 markdown → 视为违规
- 降级转换函数无单元测试 → 视为可疑

**反例**：

```python
# ❌ 错误：直接发送标准 markdown
class WeComNotifier(BaseNotifier):
    async def send(self, message: str):
        # 企业微信不支持表格/代码块，直接发送会被截断
        payload = {"msgtype": "markdown", "markdown": {"content": message}}
        await self._post(payload)
```

**正例**：

```python
# ✅ 实现降级转换函数
class WeComNotifier(BaseNotifier):
    async def send(self, message: str):
        # 企业微信仅支持 #/[]()/**/`/>/<font> 子集
        # 文档：https://developer.work.weixin.qq.com/document/path/91770
        wecom_md = self._to_wecom_markdown(message)
        payload = {"msgtype": "markdown", "markdown": {"content": wecom_md}}
        await self._post(payload)

    def _to_wecom_markdown(self, message: str) -> str:
        """将标准 markdown 降级为企业微信支持的子集"""
        # 表格 → 列表（企业微信不支持表格）
        message = re.sub(r'\|.*?\|', lambda m: f'- {m.group(0)}', message)
        # 代码块 → 引用（企业微信不支持代码块）
        message = re.sub(r'```[\s\S]*?```', lambda m: f'> {m.group(0)}', message)
        return message
```

**配置参数**：`third_party_markdown_compat` 节点（platforms / supported_syntax / degrade_rules / require_doc_link）

**适用场景**：
- 第三方平台 API 集成（钉钉/企业微信/飞书/Slack/Discord）
- 富文本/Markdown 内容发送
- 不同平台语法差异处理

**不适用场景**：
- 单一平台的纯文本消息（无 markdown 语法）
- 内部系统消息（无第三方平台限制）
- 已知平台支持完整 markdown（无需降级）

**历史教训**：钉钉/企业微信通知发送标准 markdown，企业微信不支持表格/代码块导致格式错乱。修复后实现 `_to_wecom_markdown()` 降级转换函数


---

### step 125：合并写入 vs 覆盖写入决策规范（merge vs overwrite write strategy）【强制】🆕v4.27

**背景**：用户手动注入数据（如从 DevTools 复制 cookie）时可能只粘贴部分字段，若用覆盖写会丢失原有完整数据集，导致下游依赖完整数据的接口失败。

**问题**：`cookie_inject.py` 用 `export_cookies`（覆盖写）注入用户手动复制的 4 个 cookie，丢失原有 22 个完整 cookie 集，详情页 SPA 渲染失败。

**规范**：

1. **写入策略决策矩阵【强制】**：数据写入必须按数据来源选择写入策略：

   | 数据来源 | 写入策略 | 理由 |
   |---|---|---|
   | 用户手动注入（DevTools 复制） | 合并写（merge） | 用户可能只粘贴部分字段 |
   | 文件导入（Netscape/JSON） | 合并写（merge） | 安全保底，保留旧字段额外属性 |
   | 系统登录成功 | 覆盖写（overwrite） | 用完整集替换，但需先验证新集完整 |
   | 系统刷新 token | 合并写（merge） | 只更新 token 相关字段 |

2. **合并写方法签名【强制】**：合并写方法必须以字段名为 key 合并，相同 name 的新值覆盖旧值，旧文件中其他字段全部保留：

   ```python
   def merge_cookies(self, cookies: list[dict], method: str = "merge", user_id: str = "default") -> bool:
       with self._lock:
           existing = self._read_json(user_id)
           merged_by_name: dict[str, dict] = {}
           if existing and existing.get("cookies"):
               for c in existing["cookies"]:
                   merged_by_name[c.get("name", "")] = c
           for new_c in cookies:
               merged_by_name[new_c.get("name", "")] = new_c
           merged_cookies = list(merged_by_name.values())
           # ... 写入 + 同步
   ```

3. **合并后日志输出【强制】**：合并写必须输出"注入 N 个，原有 M 个，合并后 K 个"日志，便于排查数据丢失问题。

4. **覆盖写必须先验证新集完整【强制】**：系统登录成功后用覆盖写时，必须先验证新集完整性（如 cookie 总数 ≥ 阈值），不完整时降级为合并写或拒绝写入。

**配置驱动**：写入策略决策矩阵、合并 key 字段、完整性阈值等参数在 `config.yaml` 的 `write_strategy_decision` 节点管理，包含 `strategy_matrix` / `merge_key_field` / `overwrite_requires_validation` / `validation_threshold` 等，不硬编码在技能中。

**适用场景**：
- 用户手动注入数据（cookie/header/token）
- 文件导入数据（Netscape/JSON/CSV）
- 系统刷新部分字段（token 刷新）
- 多源数据合并（多个用户身份）

**不适用场景**：
- 系统完整集替换（登录成功后的完整 cookie 集）
- 审计日志（需保留全量历史，禁止合并）
- 计数器递增（需去重键，禁止合并）

**历史教训**：用户从 DevTools 复制 4 个身份 cookie 注入，`export_cookies` 覆盖写丢失原有 22 个完整 cookie 集（包括 cna/tracknick/_tb_token_/t/tfstk 等详情页 SPA 渲染必需的会话 cookie），导致详情页采集持续失败。修复后新增 `merge_cookies` 方法，用户注入只增量更新同名 cookie，保留原有其他 cookie。

**判断信号（review 触发条件）**：
- 用户手动注入接口（`/api/auth/cookie` 等）用 `export` / `overwrite` / `replace` 命名的方法
- 写入方法无合并逻辑（直接覆盖整个文件）
- 系统登录成功后用覆盖写但无完整性验证
- 合并写方法无日志输出（无法排查数据丢失）


---

### step 204：DB-WRITE-IDENTITY-TRACE 数据库写入身份追溯与类型安全（安全维度）【强制】🆕v4.38

> **完整规范见**：[database.md](database.md) 的 step 204。本条目从安全维度补充 user_id 隔离的安全要求。

**安全背景**：本轮对话修复的 8 类问题之一——`ItemsMixin.get_item()` 缺少 `user_id` 参数，写入/查询时无 user_id 过滤，多用户场景下可能查询/修改其他用户的数据，存在跨用户数据泄露风险。

**安全维度规范**：

1. **user_id 隔离是安全硬约束【强制】**：多用户系统中，所有涉及用户数据的 DB 写入/查询必须有 `user_id` 过滤，防止跨用户数据泄露。这是与 step 134「多用户资源隔离规范」配合的安全底线：
   ```python
   # ✅ 正确：WHERE user_id 过滤
   def get_item(self, item_id: str, user_id: str | None = None) -> ItemRow | None:
       stmt = select(ItemRow).where(ItemRow.item_id == item_id)
       if user_id is not None:
           stmt = stmt.where(ItemRow.user_id == user_id)
       return session.execute(stmt).scalar_one_or_none()

   # ❌ 错误：无 user_id 过滤，可能查到其他用户的数据
   # def get_item(self, item_id: str) -> ItemRow | None:
   #     return session.execute(select(ItemRow).where(ItemRow.item_id == item_id)).scalar_one_or_none()
   ```

2. **user_id 必须从认证上下文获取【强制】**：user_id 必须从认证中间件（`request.state.user_id`）获取，禁止从前端请求参数获取（防篡改）。与 step 135「认证中间件多路校验规范」配合。

3. **admin 接口豁免必须显式声明【强制】**：admin 接口（系统级查询）可豁免 user_id 过滤，但必须在路由装饰器中显式声明 `require_admin=True`，并在配置的 `exempt_functions` 列表中登记。

4. **敏感操作必须记录 user_id 审计日志【强制】**：所有涉及 user_id 的写入操作（INSERT/UPDATE/DELETE）必须记录审计日志，包含 user_id / 操作类型 / 资源 ID / 时间戳，便于追溯。

**配置驱动**：`db_write_identity_trace` 节点的安全维度参数，包含 `user_id_isolation_required`（默认 `true`）、`user_id_from_auth_context_only`（默认 `true`）、`admin_exempt_decorator_name`（默认 `"require_admin"`）、`audit_log_required_for_write`（默认 `true`）、`audit_log_fields`（默认 `["user_id", "operation", "resource_id", "timestamp"]`）在 `config.yaml` 管理，不硬编码。

**适用场景**：
- 多用户系统的所有 DB 写入/查询函数（安全维度）
- 涉及 user_id 隔离的表（items / orders / evaluations / tasks 等）
- 从认证中间件到 Repository 的安全调用链路

**不适用场景**：
- 系统级查询（admin 接口，显式豁免）
- 单用户系统（无 user_id 概念）
- 公共数据（所有用户共享，无隔离需求）

**历史教训**：`ItemsMixin.get_item()` 缺少 `user_id` 参数，查询时无 user_id 过滤，理论上用户 A 可以通过传入用户 B 的 item_id 查询到用户 B 的商品数据。虽然当前前端不会主动传入他人的 item_id，但这是潜在的安全漏洞。修复后 `get_item` 显式接收 `user_id` 并在 WHERE 过滤，从安全维度杜绝跨用户数据泄露。

**判断信号（review 触发条件）**：
- DB 查询无 `WHERE user_id ==` 过滤但表有 user_id 字段
- user_id 从前端请求参数获取而非认证上下文
- admin 接口未显式声明 `require_admin` 装饰器
- 写入操作无审计日志


---

