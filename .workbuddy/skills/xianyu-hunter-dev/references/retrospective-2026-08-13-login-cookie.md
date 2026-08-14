# 复盘报告：2026-08-13 根路径白板 / 登录 30s 无响应 + Cookie 异常 / safe-delete 测试陷阱

> **版本**：v4.71.0 衍生
> **复盘日期**：2026-08-13
> **复盘方法**：Sequential Thinking 四维度复盘
> **触发来源**：用户要求基于最近历史对话（开发模式根路径白板、浏览器登录「30s 无响应」后「Cookie 异常(cookie_expired_m_h5_tk)」、验证修复时踩到 safe-delete 沙箱导致 pytest 崩溃）系统性提炼编码规范，并整合进 `xianyu-hunter-dev`（本技能）、`xianyu-frontend-code-review`、`xianyu-backend-code-review`、`xianyu-auto-testing`。
> **关联规范（新增）**：meta-rule #120 PROXY-REDIRECT-SAFETY / #121 COOKIE-WARMUP-HOMEPAGE / #122 COOKIE-INJECT-REHYDRATE / #123 INVALID-RESPONSE-DIAGNOSTICS / #124 SANDBOX-SAFE-TEST / #125 REGRESSION-GUARD / #126 WRAPPER-API-VERIFY
> **下游技能同步**：`xianyu-frontend-code-review`（维度 46 proxy-redirect-safety）、`xianyu-backend-code-review`（维度 45 cookie-token-lifecycle / 46 invalid-response-diagnostics / 47 wrapper-api-verify）、`xianyu-auto-testing`（config#sandbox_test_protocol + config#regression_guard + 模式 E 增强）

---

## H.1 复盘范围

| 范围 | 内容 | 来源对话 |
|------|------|----------|
| 案例 G | 开发模式访问 `http://127.0.0.1:8001/`（根路径）显示白板；正确入口应为 `/xianyu/`。根因为 SPA `BrowserRouter basename="/xianyu"` + vite `base='/xianyu/'` 与根路径访问失配 | 白板诊断对话 |
| 案例 H | 浏览器登录后「登录进程无响应（30s 未更新）」，重试登录成功但 Cookie 状态显示「Cookie 异常(cookie_expired_m_h5_tk)」 | 登录异常对话 |
| 案例 I | 验证上述修复时，pytest 在 safe-delete 沙箱下偶发崩溃（cov 清 `.coverage` 与 `C:\pyfix_tmp` 垃圾目录被 fail-closed 拦截），单跑一次的 `F` 被误判为回归 | 修复验证对话 |

案例 H 拆为三处修复：P0-1 登录导出前预热页由 `/personal` 改为闲鱼首页（触发 MTOP `_m_h5_tk` 刷新）；P0-2 注入 Worker 后刷新会话令牌（rehydrate）；P1 invalid 响应补真实诊断字段。三起问题横跨**部署入口契约**、**Cookie/会话令牌生命周期**、**错误响应诊断契约**、**沙箱安全测试协议**四个此前规范薄弱/缺失的主题。

---

## H.2 维度一：成功执行任务的完整步骤

### 案例 G：根路径白板

1. **精确定义症状**：访问 `http://127.0.0.1:8001/` 整页白板，`index.html` 返回 200 但无内容。
2. **排除资源 404**：直接读 `src/.../spa/index.html` 与 `assets/` 下 chunk 哈希，确认资源存在且哈希匹配 → 非 404。
3. **定位 SPA 路由契约**：`frontend/src/main.tsx` 的 `<BrowserRouter basename="/xianyu">` 只匹配 `/xianyu/*` 路由，根 `/` 无匹配路由 → 白板。
4. **核对三处一致性**：`vite.config.ts base='/xianyu/'`、`main.tsx basename="/xianyu"`、后端 `_serve_spa_request` 剥离 `xianyu/` 前缀三处对齐 → 正确入口是 `/xianyu/`。
5. **纠正入口**：所有「自动打开浏览器」入口统一指向 `/xianyu/`（曾误写 `/app/` 已全部改）。

### 案例 H：登录 30s 无响应 + Cookie 异常

1. **读日志定位信号**：后端消息 `unified_login.py` / `browser_login.py` 的 30s 心跳超时 → 登录子进程心跳中断；Cookie 健康返回 `cookie_expired_m_h5_tk` → 令牌过期。
2. **根因拆解**：
   - P0-1：登录导出前预热页用 `/personal`，该页**不触发** MTOP `_m_h5_tk` 刷新 → 导出的是过期会话令牌。
   - P0-2：注入 Worker 的 cookie 中 `_m_h5_tk` 同样陈旧，注入后未 rehydrate。
   - P1：`_make_invalid_status` 返回空字段（`cookie_count=0`、无 layers）→ 用户看到「0 个 cookie」误导。
3. **最小修复（正确层级）**：
   - P0-1：预热页改为 `https://www.goofish.com/`（首页触发 MTOP 刷新），加 `networkidle` + 2s 缓冲。
   - P0-2：注入后开新 page 访问首页 → 读浏览器新鲜 `_m_h5_tk`/`_m_h5_tk_enc` → `update_cookie_values()` 回写 JSON。
   - P1：invalid 响应返回真实 `cookie_count`/`layers_status`/`security_flags`/`key_cookies_found`。
4. **改前核实 API 真实签名**：`container.browser` 是自定义 `BrowserManager` 包装器（非原生 Playwright `Browser`），其 `get_cookies()`/`new_page()` 合法；`is_m5tk_expired(value)`、`update_cookie_values(updates, user_id=)` 签名对得上 → 修复有效接线。
5. **读既有约束**：`app.py` 注释明确禁止 `/`→`/xianyu/` 重定向（Funnel 模式剥离前缀会回环）→ **放弃**一度提议的 307 重定向。

### 案例 I：safe-delete 测试陷阱

1. **复现崩溃**：带 cov 跑 pytest → 清 `.coverage.*` 被 safe-delete fail-closed 拦截 → `INTERNALERROR`；大规模跑 → `C:\pyfix_tmp` 垃圾目录清理被拦截 → 偶发 exit1 无 summary。
2. **排除误判**：baseline（HEAD）单独跑同一测试也偶发 exit1（无 summary）→ 证明是环境崩溃而非代码回归。
3. **交叉验证**：edited vs baseline 各跑 ≥2 次 + 隔离单测 → 确认无真实 `FAILED`/`AssertionError`。
4. **回归守护**：为 P1 新增测试，`git checkout` 回基线跑 → 测试红灯；恢复修复 → 绿灯 → 证明测试真正守卫修复。

---

## H.3 维度二：任务执行过程中的不确定性与失败点

### 案例 G/H 的不确定性与失败点

- **失败点 1（误提 307 重定向）**：一度未读 `app.py` 约束就提议根路径→`/xianyu/` 重定向，险些在 Funnel 部署下造成无限回环。必须先 grep 反代/重定向/回环相关注释。
- **不确定性 1（原生库假设）**：先验假设 `container.browser.get_cookies()` 在原生 Playwright `Browser` 上不存在 → 错误，实为自定义包装器。调用第三方/包装器方法前必须核实真实类与方法签名。
- **不确定性 2（症状=根因陷阱）**：白板第一直觉是「资源 404 / SW 缓存」，实际是路径契约失配；Cookie 异常第一直觉是「登录失败」，实际是令牌 TTL 未刷新。症状≠根因，必须读通真实代码路径再下结论。

### 案例 I 的不确定性与失败点

- **失败点 1（cov 崩溃）**：pytest 带 coverage 时清 `.coverage.*` 被 safe-delete 钩子 fail-closed 拦截 → `INTERNALERROR` / exit3。
- **失败点 2（临时目录崩溃）**：pytest 收尾清理 `C:\pyfix_tmp\*garbage*` 被拦截 → 偶发 exit1 无 summary。
- **失败点 3（单跑误判）**：单跑一次出现 `F` 即认定回归 → 实际 baseline 同样 flaky，必须用「同命令 baseline vs edited 各跑≥2次 + 隔离单测」交叉验证。
- **失败点 4（git stash 单文件失败）**：本仓 `git stash push <单文件>` 因 autocrlf 守卫失败 → 改用 `git checkout -- <file>` 取基线，再 `cp` 还原。

---

## H.4 维度三：可抽象的固定流程与判断逻辑

### 流程 P1：根因优先的诊断闭环（通用）

```
1. 精确定义症状（URL/截图/日志原文），不急于改代码
2. 排除表层原因（白板先排除 404；异常先排除登录失败）
3. 定位真实代码路径（SPA 入口契约 / Cookie 生命周期 / 错误响应构造）
4. 读既有约束注释（grep Funnel/proxy/redirect/loop + 路由注释），确认不会破坏部署
5. 在正确层级做最小修复
6. 改前核实第三方/包装器 API 真实签名（勿套用原生库假设）
7. 沙箱安全命令验证 + 回归测试守护
```

**判断逻辑**：任何修复前必须「复现 + 读通代码路径 + 读约束」，禁止凭经验直接改（对应 meta-rule 既有 #1 编程前先思考 / 本复盘新增 #120-#126）。

### 流程 P2：Cookie/会话令牌生命周期「预热 + 注入后 rehydrate」

```
1. 读取 _m_h5_tk 等会话令牌处，必须配套刷新触发：
   - 登录/导出前预热 → 访问平台【首页】(触发 MTOP _m_h5_tk 刷新)，禁止仅访问子页(/personal)
2. 向 Worker/浏览器注入 cookie 后，必须 rehydrate：
   - 开新 page 访问首页 → 等 networkidle + 缓冲 → 读新鲜 _m_h5_tk/_m_h5_tk_enc
   - update_cookie_values(updates, user_id=) 回写 JSON
3. 令牌有效性以嵌入式时间戳判定（is_m5tk_expired），不依赖 cookie  expires 字段
```

**判断逻辑**：凡涉及 `_m_h5_tk`/会话令牌，必须同时存在「刷新触发」与「注入后 rehydrate」两环；缺任一即可能报 `cookie_expired_*`（对应 #121 / #122）。

### 流程 P3：错误响应诊断契约

```
invalid/错误响应必须携带真实诊断字段，禁止返回 0/空误导：
- cookie_count = len(cookies_list)
- layers_status = 各层(identity/session/tracking)命中状态
- security_flags = 安全标记
- key_cookies_found = 命中的关键 cookie 列表
```

**判断逻辑**：错误响应是用户排障的唯一依据，缺字段会制造「0 个 cookie / 各层缺失」的虚假结论（对应 #123）。

### 流程 P4：沙箱安全测试协议 + 回归守护

```
1. 用项目 venv 的 pytest，禁止系统 python -m pytest 带 cov：
   <venv>/Scripts/pytest.exe <target> --no-cov -p no:cacheprovider
2. flake 测试跑 ≥2 次；大规模跑分模块/隔离单测排除环境崩溃
3. 每条修复配回归测试，且测试在 pre-fix 代码必须失败（基线红灯/修复绿灯）
4. 验证结论以「无 FAILED/AssertionError」为准，exit1 无 summary 视为环境崩溃而非回归
```

**判断逻辑**：safe-delete 沙箱下 cov 与临时目录清理会被 fail-closed 拦截，必须走 `--no-cov`；单跑 `F` 不足以判定回归（对应 #124 / #125）。

---

## H.5 维度四：适用场景与不适用场景

### 规范 #120 PROXY-REDIRECT-SAFETY（重定向/中间件不得破坏反代）

| | 说明 |
|---|---|
| **适用** | 新增全局重定向/中间件/入口重写；子路径部署 SPA；经 Funnel/proxy 反向代理剥离前缀的部署 |
| **不适用** | 纯后端 JSON API（无 SPA 入口）；明确无前缀剥离的单层部署（仍建议先 grep 约束） |

### 规范 #121 COOKIE-WARMUP-HOMEPAGE（预热必须触达首页）

| | 说明 |
|---|---|
| **适用** | 任何登录/导出/cookie 注入前需要刷新 MTOP `_m_h5_tk` 的场景；闲鱼/类 MTOP 会话令牌体系 |
| **不适用** | 非 MTOP/非会话令牌鉴权；令牌由后端下发且前端不持有刷新逻辑的场景 |

### 规范 #122 COOKIE-INJECT-REHYDRATE（注入后必须 rehydrate）

| | 说明 |
|---|---|
| **适用** | 向无头浏览器/Worker 注入 cookie 后需立即使用的场景；多账号 cookie 切换 |
| **不适用** | 注入后不立即发起需鉴权请求（可延后刷新）；原生 Playwright context 直接持有有效 cookie |

### 规范 #123 INVALID-RESPONSE-DIAGNOSTICS（错误响应诊断契约）

| | 说明 |
|---|---|
| **适用** | 任何 invalid/错误/降级响应构造；前端健康态展示、Cookie 状态浮层 |
| **不适用** | 正常成功响应（按业务字段返回）；纯内部异常（不对外展示） |

### 规范 #124 SANDBOX-SAFE-TEST（沙箱安全测试协议）

| | 说明 |
|---|---|
| **适用** | safe-delete 类沙箱（fail-closed 拦截删除）；pytest 带 cov 易崩；CI 中临时目录清理受限 |
| **不适用** | 无 safe-delete 钩子的标准环境（cov 可保留，但 --no-cov 仍无害） |

### 规范 #125 REGRESSION-GUARD（修复即附回归测试）

| | 说明 |
|---|---|
| **适用** | 任何 Bug 修复 / 行为变更；需证明修复有效的场景 |
| **不适用** | 纯文档/配置微调（无逻辑分支变化） |

### 规范 #126 WRAPPER-API-VERIFY（核实包装器真实 API）

| | 说明 |
|---|---|
| **适用** | 调用第三方 SDK / 项目自定义包装器（如 BrowserManager）；原生库 API 与包装器 API 不一致时 |
| **不适用** | 直接持有原生对象且文档明确；纯标准库调用 |

### 通用判断信号（跨六规范）

- 「根路径访问白板、但 `/xianyu/` 正常」→ SPA basename/入口契约失配（#118 既有 + #120 重定向安全）。
- 「登录成功但立刻报 cookie_expired」→ 令牌 TTL 未刷新（#121 预热 / #122 注入后 rehydrate）。
- 「错误响应显示 0/空」→ 诊断字段缺失（#123）。
- 「单跑 pytest 偶发 exit1 无 summary」→ safe-delete 环境崩溃，非回归（#124 + #125 交叉验证）。

---

## H.6 沉淀与下游同步

| 新规范 | 内容 | hunter-dev 落点 | 前端审查 | 后端审查 | auto-testing |
|--------|------|----------------|----------|----------|--------------|
| #120 | 重定向/中间件不得破坏反代（Funnel 回环） | meta-rules #120 + coding-standards-2026-08-13 | 维度 46 proxy-redirect-safety | 维度 47（后端侧交叉） | 模式 AL 增强 |
| #121 | 预热必须触达平台首页刷新 _m_h5_tk | meta-rules #121 + coding-standards-2026-08-13 | — | 维度 45 cookie-token-lifecycle | 模式 C 增强（backend_cookie_healing） |
| #122 | 注入 cookie 后必须 rehydrate 会话令牌 | meta-rules #122 + coding-standards-2026-08-13 | — | 维度 45 cookie-token-lifecycle | 模式 C / N 增强 |
| #123 | invalid 响应必须返回真实诊断字段 | meta-rules #123 + coding-standards-2026-08-13 | cookie_health_display 交叉 | 维度 46 invalid-response-diagnostics | — |
| #124 | 沙箱安全测试协议（--no-cov + 项目 venv） | meta-rules #124 + coding-standards-2026-08-13 | — | 维度 20 testing 交叉 | config#sandbox_test_protocol + 模式 E |
| #125 | 修复即附基线红灯/修复绿灯回归测试 | meta-rules #125 + coding-standards-2026-08-13 | — | 维度 20 testing 交叉 | config#regression_guard + 模式 E |
| #126 | 调用包装器前核实真实 API 签名 | meta-rules #126 + coding-standards-2026-08-13 | — | 维度 47 wrapper-api-verify | — |

**价值观提炼**：本次问题本质都是「**部署入口契约** + **会话令牌生命周期** + **错误响应可观测性** + **沙箱测试纪律**」的规范缺失，而非业务逻辑错误。预防优于救火——把 #120-#126 前置到代码审查（前端维度 46 / 后端维度 45-47）与自动化测试（auto-testing config#sandbox_test_protocol / #regression_guard），可在合入前拦截，而非上线后白屏/异常才救。所有可变参数（部署子路径、SPA 基路径、cookie 域名、venv 路径、测试命令、令牌刷新页）抽进各技能 config.yaml，SKILL.md/references 只描述通用流程与判断逻辑，杜绝硬编码，保证跨业务场景可泛化。
