# 元规范 #14 测试与部署审查（#120-#126）

> **来源**：2026-08-13 复盘（根路径白板 / 登录 30s 无响应 + Cookie 异常 / safe-delete 测试陷阱），Sequential Thinking 四维度。
> **关联复盘**：`retrospective-2026-08-13-login-cookie.md`、`coding-standards-2026-08-13.md`
> **配置驱动**：所有可变参数集中在各技能 `config.yaml` / `tech-stack.json`，禁止硬编码。

---

## #120 PROXY-REDIRECT-SAFETY（重定向/中间件不得破坏反代）

**核心规则**：
1. 新增全局重定向/中间件/入口重写前，必须先 grep `Funnel`/`proxy`/`redirect`/`loop` 与路由注释，确认不会造成前缀剥离回环。
2. 在经反向代理剥离前缀的部署（如 Funnel）下，禁止 `/`→`/xianyu/` 类重定向（剥离后回到 `/` 再重定向 = 无限循环）。
3. 修复「根路径白板」靠「统一入口指向子路径」，而非加重定向。

**判断信号**：
- `grep -rn "Funnel\|strip\|prefix" src/xianyu_hunter/web/app.py` → 是否存在前缀剥离逻辑（违反信号：重定向目标会被再次剥离）
- 症状「根路径白板但 `/xianyu/` 正常」→ 入口契约失配，非重定向缺失

**配置参数**：`proxy.strip_prefix_deployment`（enabled / 是否经反代剥离前缀）

**适用**：子路径部署 SPA；经 Funnel/proxy 反向代理剥离前缀的部署；新增全局重定向/中间件
**不适用**：纯后端 JSON API（无 SPA 入口）；明确无前缀剥离的单层部署（仍建议先 grep 约束）
**历史教训**：2026-08 一度未读 `app.py` 约束就提议根路径 307 重定向，险些在 Funnel 部署下造成无限回环。
**对应 step**：step 浏览器入口统一（scripts/启动服务.bat、launcher.py、automation.ps1、web 命令日志）。

---

## #121 COOKIE-WARMUP-HOMEPAGE（预热必须触达平台首页）

**核心规则**：
1. 登录/导出/cookie 注入前预热必须访问 `cookie.homepage_url`（本仓 `https://www.goofish.com/`），触发 MTOP `_m_h5_tk` 刷新。
2. 禁止仅访问子页（如 `/personal`）——子页不触发 MTOP 令牌刷新，导出的是过期会话令牌。
3. 预热后 `wait_for_load_state("networkidle")` + 固定 `sleep_buffer_sec` 缓冲，确保令牌写入。

**判断信号**：
- `grep -n "goto(" scripts/browser_login.py` → 预热页是否为首页（违反信号：预热页是 `/personal` 等子页）
- 症状「登录成功但立刻报 cookie_expired_m_h5_tk」→ 预热未触达首页

**配置参数**：`cookie.homepage_url`、`cookie.warmup.sleep_buffer_sec`、`cookie.warmup.wait_networkidle_timeout_sec`

**适用**：任何登录/导出/cookie 注入前需刷新 MTOP `_m_h5_tk` 的场景；闲鱼/类 MTOP 会话令牌体系
**不适用**：非 MTOP/非会话令牌鉴权；令牌由后端下发且前端不持有刷新逻辑
**历史教训**：2026-08 P0-1 修复——预热页由 `/personal` 改为首页，消除 `cookie_expired_m_h5_tk`。
**对应 step**：step browser_login._prepare_login_cookie_export。

---

## #122 COOKIE-INJECT-REHYDRATE（注入后必须 rehydrate 会话令牌）

**核心规则**：
1. 向 Worker/无头浏览器注入 cookie 后，`_m_h5_tk` 可能仍陈旧，必须 rehydrate（注入 ≠ 生效）。
2. rehydrate 流程：开新 page → 访问 `cookie.homepage_url` → 等 networkidle + 缓冲 → 读新鲜 `_m_h5_tk`/`_m_h5_tk_enc` → `update_cookie_values(updates, user_id=)` 回写 JSON。
3. 令牌有效性用 `is_m5tk_expired(value)`（嵌入式时间戳），不依赖 cookie `expires` 字段（会话 cookie `expires=-1`）。

**判断信号**：
- `grep -n "sync_cookie_layers_from_json\|_refresh_worker_m5tk" src/xianyu_hunter/web/routes/unified_login.py` → 注入后是否有 rehydrate 步骤（违反信号：仅 sync 无 rehydrate）
- 症状「注入后立即请求报 cookie_expired_*」→ 缺 rehydrate

**配置参数**：`cookie.homepage_url`、`cookie.rehydrate.sleep_buffer_sec`、`cookie.rehydrate.enabled`

**适用**：向无头浏览器/Worker 注入 cookie 后需立即使用的场景；多账号 cookie 切换
**不适用**：注入后不立即发起需鉴权请求（可延后刷新）；原生 Playwright context 直接持有有效 cookie
**历史教训**：2026-08 P0-2 修复——注入后新增 `_refresh_worker_m5tk_after_inject` rehydrate。
**对应 step**：step unified_login._inject_cookies_to_worker_from_store。

---

## #123 INVALID-RESPONSE-DIAGNOSTICS（错误响应诊断契约）

**核心规则**：
1. invalid/错误响应必须携带真实诊断字段：`cookie_count=len(cookies_list)`、`layers_status`（identity/session/tracking 各层命中）、`security_flags`、`key_cookies_found`（命中关键 cookie）。
2. 禁止返回 0/空误导——不得把 invalid 响应的计数/层状态填空或 0，否则用户看到「0 个 cookie / 各层缺失」虚假结论。
3. 前端健康态浮层、Cookie 状态展示必须消费真实字段，不得展示硬编码文案。

**判断信号**：
- `grep -n "_make_invalid_status\|cookie_count=" src/xianyu_hunter/web/services/cookie_status.py` → invalid 响应是否填真实字段（违反信号：字段为 0/空/缺省）
- 症状「Cookie 异常但显示 0 个 cookie」→ 诊断字段缺失

**配置参数**：（无新增，依赖既有 `cookie_status` 字段定义；跨 `api_response_field_ui_alignment`）

**适用**：任何 invalid/错误/降级响应构造；前端健康态展示、Cookie 状态浮层
**不适用**：正常成功响应（按业务字段返回）；纯内部异常（不对外展示）
**历史教训**：2026-08 P1 修复——`_make_invalid_status` 补真实诊断字段，消除「0 个 cookie」误导。
**对应 step**：step cookie_status._make_invalid_status。

---

## #124 SANDBOX-SAFE-TEST（沙箱安全测试协议）

**核心规则**：
1. 用项目 venv 的 pytest：`test.venv_pytest`（本仓 `.venv/Scripts/pytest.exe`），禁止系统 `python -m pytest`（无 pytest 模块且易踩环境）。
2. 禁用 coverage：加 `--no-cov -p no:cacheprovider`；safe-delete 钩子 fail-closed 拦截 `.coverage.*` 清理 → `INTERNALERROR`。
3. 临时目录崩溃：pytest 收尾清理 `C:\pyfix_tmp\*garbage*` 也被拦截 → 偶发 exit1 无 summary，属环境崩溃。
4. flake 测试跑 ≥2 次；大规模/易 flaky 测试隔离单测确认；以「无 FAILED/AssertionError」为准。

**判断信号**：
- 测试 exit1 但无 `FAILED`/`AssertionError` → 环境崩溃（safe-delete），非回归
- 单跑一次 `F` 不足以判回归 → 必须与 baseline 交叉验证

**配置参数**：`test.venv_pytest`、`test.safe_delete_workaround`（--no-cov -p no:cacheprovider）、`test.flaky_min_runs`（默认 2）

**适用**：safe-delete 类沙箱（fail-closed 拦截删除）；pytest 带 cov 易崩；CI 中临时目录清理受限
**不适用**：无 safe-delete 钩子的标准环境（cov 可保留，但 --no-cov 仍无害）
**历史教训**：2026-08 验证修复时踩到 safe-delete 崩溃，单跑 `F` 误判为回归，后各跑≥2次+隔离单测排除。
**对应 step**：step 测试验证（xianyu-auto-testing 模式 E + config#sandbox_test_protocol）。

---

## #125 REGRESSION-GUARD（修复即附回归测试）

**核心规则**：
1. 每条修复必须有对应测试，且测试在 pre-fix 代码必须失败（基线红灯）。
2. 验证手法：`git checkout -- <改动文件>` 取基线 → 跑测试应红灯 → 还原修复 → 应绿灯，证明测试真正守卫修复。
3. 避免误判：单跑一次的 `F` 不足以判回归；必须与 baseline 交叉验证排除环境崩溃。

**判断信号**：
- 修复 PR 无新增/修改测试 → 违反回归守护
- 测试在 HEAD baseline 仍通过 → 未真正守卫修复（守卫无效）

**配置参数**：`regression.baseline_red_fix_green`（enabled / 验证手法说明）

**适用**：任何 Bug 修复 / 行为变更；需证明修复有效的场景
**不适用**：纯文档/配置微调（无逻辑分支变化）
**历史教训**：2026-08 为 P1 新增 `test_cookie_status_invalid_fields.py`，基线红灯/修复绿灯，证明守卫有效。
**对应 step**：step 测试验证（xianyu-auto-testing config#regression_guard + 模式 E）。

---

## #126 WRAPPER-API-VERIFY（核实包装器真实 API）

**核心规则**：
1. 调用第三方 SDK / 项目自定义包装器前，必须核实其真实类与方法签名。
2. 如 `container.browser` 是项目自定义 `BrowserManager` 包装器，非原生 Playwright `Browser`；其 `get_cookies()`/`new_page()`/`add_cookies()` 合法。
3. 勿套用原生库假设：原生 `Browser` 无 `get_cookies()`（需 `context.cookies()`），但包装器有 → 假设「方法不存在」会误判为空操作。
4. 每个外部操作放 `try/except` 内，单步失败不影响主流程（非致命）。

**判断信号**：
- `grep -n "class BrowserManager\|def get_cookies\|def new_page" src/xianyu_hunter/infra/browser.py` → 确认包装器真实 API
- 假设「方法不存在」前先查定义（违反信号：凭原生库文档否定包装器方法）

**配置参数**：（无新增，依赖 `browser` 包装器定义）

**适用**：调用第三方 SDK / 项目自定义包装器（如 BrowserManager）；原生库 API 与包装器 API 不一致时
**不适用**：直接持有原生对象且文档明确；纯标准库调用
**历史教训**：2026-08 P0-2 核实 `container.browser` 为 `BrowserManager` 包装器，确认 `get_cookies()` 合法，排除「空操作」误判。
**对应 step**：step unified_login._refresh_worker_m5tk_after_inject。
