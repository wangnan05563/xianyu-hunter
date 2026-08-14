# XianyuHunter 编码规范补充（2026-08-13 登录/Cookie/测试专项）

> **版本**：v1.4 衍生
> **日期**：2026-08-13
> **来源**：从「开发模式根路径白板 / 浏览器登录 30s 无响应 + Cookie 异常 / safe-delete 测试陷阱」三起问题复盘提炼（详见 `retrospective-2026-08-13-login-cookie.md`，Sequential Thinking 四维度复盘）
> **适用范围**：`src/xianyu_hunter/`（Python）+ `frontend/src/`（TypeScript）
> **配套技能**：`xianyu-hunter-dev`（增量开发）、`xianyu-frontend-code-review`、`xianyu-backend-code-review`、`xianyu-auto-testing`
> **关联元规范**：meta-rule #120-#126
> **配置驱动**：所有可变参数（部署子路径、SPA 基路径、cookie 域名、venv 路径、测试命令、令牌刷新页）集中在各技能 `config.yaml`，本文件只描述通用流程与判断逻辑，禁止硬编码。

---

## 十一、部署入口与重定向安全（对应 #118 既有 + #120 新增）

### 11.1 SPA 入口契约（既有 #118 强化）

| 规则 | 说明 |
|---|---|
| **入口必须是部署子路径** | 所有「自动打开浏览器」入口必须指向 `spa.basename`（本仓 `/xianyu`），禁止 `/` 或 `/app/` |
| **三处对齐** | `vite.config.ts base` = `main.tsx BrowserRouter basename` = 后端 `_serve_spa_request` 剥离前缀，三者一致 |
| **根路径不是入口** | 访问根 `/` 在子路径部署下必然白板（basename 不匹配），这是 SPA 固有行为，非 bug |

### 11.2 重定向/中间件安全（#120 新增）

| 规则 | 说明 |
|---|---|
| **新增全局重定向前先 grep 约束** | 搜索 `Funnel`/`proxy`/`redirect`/`loop` 与路由注释，确认不会造成前缀剥离回环 |
| **禁止破坏反代** | 在经反向代理剥离前缀的部署（如 Funnel）下，`/`→`/xianyu/` 类重定向会造成「剥离后回到 `/` 再重定向」的无限循环，必须避免 |
| **正确做法** | 修复入口问题靠「统一入口指向子路径」，而非「根路径重定向」 |

**判断逻辑**：症状「根路径白板但子路径正常」→ 入口契约失配，修复入口而非加重定向。

---

## 十二、Cookie/会话令牌生命周期（#121 / #122 新增）

### 12.1 预热必须触达平台首页（#121）

| 规则 | 说明 |
|---|---|
| **登录/导出前预热页 = 平台首页** | 预热必须访问 `cookie.homepage_url`（本仓 `https://www.goofish.com/`），触发 MTOP `_m_h5_tk` 刷新 |
| **禁止仅访问子页** | 如 `/personal` 不触发 MTOP 令牌刷新，导出的是过期会话令牌 → 登录成功但立刻报 `cookie_expired_m_h5_tk` |
| **缓冲** | 预热后 `wait_for_load_state("networkidle")` + 固定 `sleep_buffer_sec` 缓冲，确保令牌写入 |

### 12.2 注入后必须 rehydrate（#122）

| 规则 | 说明 |
|---|---|
| **注入 ≠ 生效** | 向 Worker/无头浏览器注入 cookie 后，`_m_h5_tk` 可能仍陈旧，必须 rehydrate |
| **rehydrate 流程** | 开新 page → 访问 `cookie.homepage_url` → 等 networkidle + 缓冲 → 读新鲜 `_m_h5_tk`/`_m_h5_tk_enc` → `update_cookie_values(updates, user_id=)` 回写 JSON |
| **令牌有效性判定** | 用 `is_m5tk_expired(value)`（嵌入式时间戳），不依赖 cookie `expires` 字段（会话 cookie `expires=-1`） |

**判断逻辑**：凡涉及 `_m_h5_tk`/会话令牌，必须同时具备「刷新触发（#121）」与「注入后 rehydrate（#122）」；缺任一即可能报 `cookie_expired_*`。

---

## 十三、错误响应诊断契约（#123 新增）

| 规则 | 说明 |
|---|---|
| **invalid 响应必须带真实诊断字段** | `cookie_count=len(cookies_list)`、`layers_status`（identity/session/tracking 各层命中）、`security_flags`、`key_cookies_found`（命中关键 cookie） |
| **禁止返回 0/空误导** | 不得把 invalid 响应的计数/层状态填空或 0，否则用户看到「0 个 cookie / 各层缺失」虚假结论 |
| **错误响应是排障依据** | 前端健康态浮层、Cookie 状态展示必须消费真实字段，不得展示硬编码文案 |

**判断逻辑**：错误响应是用户排障唯一依据，缺字段 = 制造误导（对应前端 `cookie_health_display`、后端 `api_response_field_ui_alignment`）。

---

## 十四、沙箱安全测试协议与回归守护（#124 / #125 新增）

### 14.1 沙箱安全测试协议（#124）

| 规则 | 说明 |
|---|---|
| **用项目 venv 的 pytest** | `test.venv_pytest`（本仓 `.venv/Scripts/pytest.exe`），禁止系统 `python -m pytest`（无 pytest 模块且易踩环境） |
| **禁用 coverage** | 加 `--no-cov -p no:cacheprovider`；safe-delete 钩子 fail-closed 拦截 `.coverage.*` 清理 → `INTERNALERROR` |
| **临时目录崩溃** | pytest 收尾清理 `C:\pyfix_tmp\*garbage*` 也被拦截 → 偶发 exit1 无 summary，属环境崩溃 |
| **flake 跑 ≥2 次** | 大规模/易 flaky 测试各跑 ≥2 次，隔离单测确认；以「无 FAILED/AssertionError」为准 |

### 14.2 回归守护（#125）

| 规则 | 说明 |
|---|---|
| **修复即附回归测试** | 每条修复必须有对应测试，且测试在 pre-fix 代码必须失败（基线红灯） |
| **验证手法** | `git checkout -- <改动文件>` 取基线 → 跑测试应红灯 → 还原修复 → 应绿灯，证明测试真正守卫修复 |
| **避免误判** | 单跑一次的 `F` 不足以判回归；必须与 baseline 交叉验证排除环境崩溃 |

---

## 十五、第三方/包装器 API 核实（#126 新增）

| 规则 | 说明 |
|---|---|
| **调用前核实真实类与方法签名** | 如 `container.browser` 是项目自定义 `BrowserManager` 包装器，非原生 Playwright `Browser`；其 `get_cookies()`/`new_page()`/`add_cookies()` 合法 |
| **勿套用原生库假设** | 原生 `Browser` 无 `get_cookies()`（需 `context.cookies()`），但包装器有 → 假设「方法不存在」会误判为空操作 |
| **每个外部操作 try/except 非致命** | 浏览器操作放 `try/except` 内，单步失败不影响主流程 |

---

## 十六、配置参数清单（全部走 config，禁止硬编码）

| 参数 | 归属技能 config 节点 | 说明 |
|------|---------------------|------|
| `spa.basename` / `spa.api_prefix` | xianyu-auto-testing `config.yaml#spa` | 部署子路径与 API 前缀（禁止硬编码 `/xianyu/`） |
| `cookie.homepage_url` | xianyu-hunter-dev `tech-stack.json` + backend review config | 令牌刷新预热页（本仓 `https://www.goofish.com/`） |
| `test.venv_pytest` | xianyu-auto-testing `config.yaml#test_execution` | 项目 venv 的 pytest 可执行路径 |
| `test.safe_delete_workaround` | xianyu-auto-testing `config.yaml#sandbox_test_protocol` | `--no-cov -p no:cacheprovider` 等沙箱安全参数 |
| `test.flaky_min_runs` | xianyu-auto-testing `config.yaml#sandbox_test_protocol` | flake 测试最小运行次数（默认 2） |
| `regression.baseline_red_fix_green` | xianyu-auto-testing `config.yaml#regression_guard` | 回归守护开关与验证手法 |
| `proxy.strip_prefix_deployment` | xianyu-frontend/backend review config | 是否经反代剥离前缀（决定是否允许根路径重定向） |
