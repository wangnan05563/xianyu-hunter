# Cookie 与认证
> 包含元规范 #66 - #101

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
