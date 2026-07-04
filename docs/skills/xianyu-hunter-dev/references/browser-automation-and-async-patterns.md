# 浏览器自动化与异步时序规范（v1.0）

> **版本**：v1.0
> **日期**：2026-07-04
> **来源**：从"闲鱼登录模块"系列问题复盘（浏览器加载慢 / 多标签页 / Cookie 注入失效 / Target.createTarget 失败 / 取消登录卡死 / 页面无样式 / 右上角"未登录" / Cookie 读取不全等 11 类问题）
> **复盘方法**：Sequential Thinking 4 维度（成功步骤 / 失败点 / 可抽象流程 / 适用与不适用场景）
> **适用范围**：`scripts/browser_login.py` + `scripts/auth_helper.py` + `src/xianyu_hunter/web/services/auth_manager.py` + `src/xianyu_hunter/infra/browser.py` + `frontend/src/pages/Login/`
> **配套技能**：`xianyu-hunter-dev`（增量开发）、`xianyu-frontend-code-review`、`xianyu-backend-code-review`

---

## 一、问题原型

**用户报告（按时间顺序）**：

| # | 现象 | 根因 |
|---|---|---|
| 1 | 浏览器加载慢、页面无样式 | 拦截 stylesheet 导致 CSS 缺失 |
| 2 | 弹出 3-4 个标签页 | about:blank 默认页 + new_page + 历史会话恢复 |
| 3 | Target.createTarget 失败 | 关闭 context 中唯一 page 让 Edge 进入不稳定状态 |
| 4 | 取消登录卡死 | in-flight polling resolve 覆盖 setLoginStatus(null) |
| 5 | 注入 Cookie 未进入系统 | 未传 user_id，session_token 回退为 web_token |
| 6 | 右上角"未登录"（6 次迭代） | 多 Chromium 争用 user_data_dir + Cookie 异步写入未完成 + 域过滤遗漏 + SPA 占位符 |
| 7 | Cookie 18 个而非 38 个 | 异步写入未完成即读取 |
| 8 | auth_helper 并发触发卡死 | _maybe_refresh_userinfo 条件3 与登录路径并发 |
| 9 | 子进程异常静默无日志 | except Exception: pass 吞异常 |
| 10 | "Hi! 你好" 占位符 | SPA hydration 时序，domcontentloaded 后 2-8s 才挂载昵称元素 |
| 11 | Cookie 域过滤漏 unb | unb 实际在 .taobao.com 域而非 .goofish.com |

**矛盾本质**：浏览器自动化涉及多进程、异步时序、跨域 Cookie、SPA 渲染、子进程并发等多个独立维度，任一环节处理不当都会导致整体功能异常，且现象（"未登录"）与根因（Cookie 异步写入未完成）之间无明显因果关系，排查难度高。

---

## 二、成功执行任务的完整步骤

| 阶段 | 动作 | 产出 |
|---|---|---|
| 1. 证据收集 | 读完整调用链（UI → Store → API → Route → Service → Subprocess → Browser），不只看报错文件 | 定位真正故障点 |
| 2. 因果链假设 | 列 2-3 个可能根因，逐个验证（不默默选择一种解释） | 排除错误假设 |
| 3. 修复方案设计 | 先列改动点 + 影响范围 + 验证方式，再编辑 | 避免引入新问题 |
| 4. 精确编辑 | 只改必要部分，不顺手改旁边代码 | 最小修改原则 |
| 5. 语法验证 | 编辑后立即 Read 确认文件实际内容 | 防止工具返回"updated"但实际未生效 |
| 6. 端到端验证 | 用 Python 脚本调 API 模拟完整流程（GET → 改 → POST dry_run → POST save） | 验证修复真实有效 |
| 7. 总结归档 | 根因 + 修复点 + 验证结果 + 预防机制 | 沉淀为规范 |

**关键决策**：
- **不破坏现有 API 契约**：所有修复在子进程内部完成，不影响 web 后端 API 形状
- **保留用户控制权**：取消登录操作由用户主动触发，前端先停本地轮询再调远程 API
- **配置化兜底策略**：等待时间、Cookie 域白名单、占位符集合等参数由 YAML 配置管理

---

## 三、任务执行过程中的不确定性与失败点

### 3.1 不确定性

| 类别 | 描述 | 处理 |
|---|---|---|
| 等待时间 | Cookie 异步写入需要 3s 还是 5s | 经验值 3s + 重读兜底（不一开始就等更久） |
| 域过滤范围 | unb 在 goofish 还是 taobao 域 | 扩展为 goofish + taobao 双域过滤 |
| SPA 渲染时序 | domcontentloaded 后多久挂载昵称 | wait_for_selector + 5s 固定兜底 |
| 子进程并发 | auth_helper 是否会与 browser_login 并发 | _refresh_lock + _refreshing 标志互斥 |
| 取消时序 | cancel API 与 in-flight polling 谁先完成 | 前端先停轮询再调 API |

### 3.2 失败点

| # | 失败现象 | 根因 | 修复 |
|---|---|---|---|
| F-1 | 浏览器加载慢、页面无样式 | 拦截 stylesheet 导致 CSS 缺失 | 移除 stylesheet 拦截，保留 font/media/image/manifest |
| F-2 | 4 个标签页 | about:blank + new_page + new_page + 双击 | 关闭默认页 + 复用 pages[0] + 防抖 |
| F-3 | Target.createTarget 失败 | 关闭唯一 page 让 context 不稳定 | 改回不关闭，复用默认 page |
| F-4 | 取消登录卡死 | in-flight polling resolve 覆盖 setLoginStatus(null) | 先停轮询再调 API |
| F-5 | 注入 Cookie 未进入系统 | 未传 user_id，session_token 回退 web_token | 补全 user_id 传递并 issue_session |
| F-6 | 右上角"未登录"（6 次迭代） | 多 Chromium 争用 user_data_dir | delay=5.0 + _refresh_lock 互斥 |
| F-7 | Cookie 18 个而非 38 个 | 异步写入未完成即读取 | 3s+2s 等待 + 重读兜底 |
| F-8 | "Hi! 你好" 占位符 | SPA hydration 时序 | wait_for_selector + 二次重试 |
| F-9 | Cookie 域过滤漏 unb | unb 在 .taobao.com 而非 .goofish.com | 扩展为 goofish + taobao |
| F-10 | auth_helper 并发触发 | _maybe_refresh_userinfo 条件3 并发 | _refresh_lock + _refreshing 标志 |
| F-11 | 静默吞子进程异常 | except Exception: pass | logger.warning + stderr 记录 |

---

## 四、可抽象的固定流程与判断逻辑

### 流程 A：浏览器进程互斥（共享 user_data_dir 时）

**触发场景**：多个 Chromium 实例需要共用同一 user_data_dir（如登录子进程 + Worker 浏览器 + auth_helper）。

**固定步骤**：
1. **启动前清理锁文件**：`SingletonLock` / `SingletonCookie` / `SingletonSocket` + Sessions 历史标签
2. **进程级互斥**：`_refresh_lock` + `_refreshing` 标志，防止 auth_helper 与登录路径并发
3. **延迟触发**：登录路径触发 auth_helper 时传 `delay=5.0`，让 browser_login 的 Chromium 先退出
4. **退出后等待 SQLite flush**：`bc.close()` 后再等 2s，确保 SQLite 写入完成

**判断逻辑**：
```
启动 Chromium 前
  ├─ 清理 SingletonLock 等锁文件（防残留）
  ├─ 检查 _refreshing 标志（防并发）
  └─ 设置 _refreshing = True（占用）

Chromium 退出后
  ├─ 等待 SQLite flush（2s）
  └─ 释放 _refreshing = False
```

**反模式**：
- 不清理锁文件直接启动 → `Target.createTarget: Failed to open a new tab`
- 多个 auth_helper 并发执行 → SQLite Cookie 数据库锁冲突，Cookie 18 个而非 38 个
- 不延迟触发 → browser_login 的 Chromium 退出未完成，auth_helper 启动争用 user_data_dir

### 流程 B：异步写入等待策略

**触发场景**：浏览器登录成功后，Chromium 异步写入 Cookie 到 SQLite；SPA 异步挂载 DOM 元素。

**固定步骤**：
1. **不假设立即生效**：异步操作完成后必须显式等待
2. **关键数据读取前等待**：3s（cookie write） + 2s（SQLite flush）
3. **一次读取失败再读一次**：兜底重读（如 unb 未找到，再等 3s 重读）
4. **优先用 wait_for_selector**：比固定 sleep 更精准，固定 sleep 仅作兜底
5. **storage_state() 强制 flush**：读取前调用 `await bc.storage_state()` 触发持久化

**判断逻辑**：
```
异步写入触发
  ├─ sleep N 秒（N 由配置决定，默认 3s）
  ├─ storage_state() 强制 flush
  ├─ 读取数据
  └─ 数据不完整？
      ├─ 是 → 再 sleep M 秒（M 由配置决定，默认 3s）+ 重读
      └─ 否 → 完成
```

**反模式**：
- 立即读取 → 拿到 18 个 cookie 而非 38 个，缺关键 unb
- 用固定 sleep 替代 wait_for_selector → 浪费时间或不够长
- 不做兜底重读 → 首次失败后无 recovery 路径

### 流程 C：Cookie 处理规范

**触发场景**：跨域 Cookie 存储（unb 在 .taobao.com，session 在 .goofish.com）、登录态判定、用户身份识别。

**固定步骤**：
1. **域过滤必须包含所有相关域**：`goofish + taobao`（unb 实际在 .taobao.com 域）
2. **登录态判定以关键 Cookie 为准**：`unb / _tb_token_ / cookie2` 任一存在即视为已登录
3. **严格校验 Cookie 值**：`unb.isdigit() and len(unb) >= 6`，过滤测试值（`123456`）
4. **占位符过滤集合**：`_INVALID_NICKS = ["登录", "登錄", "Login", "Sign in", "立即登录", "Hi! 你好", "Hi！你好", "你好", "Hi", "Hi!"]`
5. **用户 ID 识别优先级**：`unb > _tb_token_截断 > sha256(cookie2)[:16] > default`

**判断逻辑**：
```
读取 Cookie
  ├─ 按 auth_cookie_domains 过滤（goofish + taobao）
  ├─ 校验 login_cookie_names 是否存在
  ├─ 校验 unb 值（isdigit + len >= 6）
  └─ 提取 user_id
      ├─ unb 存在 → user_id = unb
      ├─ _tb_token_ 存在 → user_id = _tb_token_[:16]（兜底重读 unb）
      └─ 都不存在 → user_id = sha256(cookie2)[:16]
```

**反模式**：
- 仅按 goofish 过滤 → 漏掉 unb（在 .taobao.com 域）
- 仅检测 Cookie 名称存在 → _m_h5_tk 访问首页就会设置，误判为已登录
- 不校验 unb 值 → unb="123456" 测试值被识别为登录
- 不过滤占位符 → 显示"Hi! 你好"作为用户昵称

### 流程 D：前端异步操作规范

**触发场景**：轮询 + 取消操作、防抖触发、状态机管理。

**固定步骤**：
1. **取消操作先停本地再调远程**：`clearInterval(pollRef.current)` 在 `await authApi.cancelLogin()` 之前
2. **防抖状态避免重复触发**：`startingBrowser` 状态在 API 返回前禁用按钮
3. **轮询终态保护**：in-flight polling resolve 不应覆盖用户主动设置的 `setLoginStatus(null)`
4. **状态机显式定义**：`idle → starting → opening → qr_ready → success / timeout / error / cancelled`

**判断逻辑**：
```
用户点击取消
  ├─ 本地：clearInterval(pollRef) + setLoginStatus(null)
  └─ 远程：await authApi.cancelLogin()
      └─ 远程返回后不再 setState（避免覆盖本地 null）

用户点击启动
  ├─ 检查 startingBrowser 状态（防抖）
  ├─ 设置 startingBrowser = true
  ├─ await authApi.startBrowserLogin()
  └─ finally: startingBrowser = false
```

**反模式**：
- 先调 cancel API 再停轮询 → in-flight polling resolve 覆盖 setLoginStatus(null)，卡在"已取消"
- 不做防抖 → 用户双击启动按钮，弹出 4 个标签页
- 轮询无终态保护 → 已取消后轮询仍在跑，状态闪烁

### 流程 E：子进程异常可观测

**触发场景**：`subprocess.run` / `subprocess.Popen` 调用 auth_helper / browser_login 等子进程。

**固定步骤**：
1. **子进程 stderr 必须捕获**：`capture_output=True` 或 `stderr=subprocess.PIPE`
2. **失败时记录 stderr**：`stderr.decode(errors="replace")[:500]`（截取前 500 字符）
3. **用 logger.warning 而非 logger.debug**：异常路径必须显眼
4. **超时单独处理**：`subprocess.TimeoutExpired` 不与普通异常混淆
5. **不静默吞异常**：`except Exception: pass` 是反模式

**判断逻辑**：
```
subprocess.run(...)
  ├─ returncode == 0 → 成功
  ├─ returncode != 0 → logger.warning("auth_helper 失败 (code={}): {}", code, stderr[:500])
  ├─ TimeoutExpired → logger.warning("auth_helper 超时（{}s）", timeout)
  └─ 其他异常 → logger.warning("auth_helper 异常: {}", e)
```

**反模式**：
- `except Exception: pass` → auth_helper 启动失败时 _userinfo 保持旧值（nick=""），前端显示"未登录"且无日志可查
- 用 logger.debug → 日志级别过低，生产环境默认不输出
- 不截取 stderr → 长字符串污染日志

### 流程 F：资源拦截策略

**触发场景**：Playwright `route("**/*", handler)` 拦截非必要资源加速加载。

**固定步骤**：
1. **不拦截 stylesheet**：CSS 缺失导致页面布局错乱、按钮不可见、扫码区域错位
2. **域名白名单放行**：登录页扫码二维码图与登录页资源必须可达
3. **拦截策略走配置**：`resource_block_types` + `resource_allow_domains` 由 YAML 管理
4. **拦截类型白名单**：`font / media / image / manifest`（不含 stylesheet）

**判断逻辑**：
```
route handler
  ├─ URL 含 resource_allow_domains → continue_()
  ├─ resource_type in resource_block_types → abort()
  └─ 其他 → continue_()
```

**反模式**：
- 拦截 stylesheet → 页面无样式，按钮不可见
- 不放行登录域名 → 扫码二维码无法显示
- 硬编码拦截类型 → 无法配置调整

---

## 五、适用场景与不适用场景

| 流程 | 适用场景 | 不适用场景 |
|---|---|---|
| A. 浏览器进程互斥 | Playwright 共享 user_data_dir、多 Chromium 实例、登录子进程 + Worker | 单进程浏览器、HTTP API 调用、纯前端 SPA |
| B. 异步写入等待 | Cookie 持久化、SQLite flush、SPA hydration、Chrome storage_state | 同步写入、静态页面、纯计算 |
| C. Cookie 处理 | 跨域 Cookie、登录态判定、用户身份识别、多 SSO 系统 | 单域 Cookie、纯前端 Cookie、无登录态 |
| D. 前端异步操作 | 轮询 + 取消、防抖触发、状态机、长任务进度 | 简单表单提交、一次性请求、纯展示组件 |
| E. 子进程异常可观测 | subprocess 调用、长任务子进程、外部脚本调用 | 同步函数、纯计算、内存操作 |
| F. 资源拦截策略 | Playwright 爬虫、浏览器自动化、登录页加载优化 | 普通 HTTP 客户端、API 调用、本地开发 |

**通用性边界**：
- 流程 A/B 适用于所有"多进程共享持久化资源 + 异步写入"的系统
- 流程 C 适用于所有"跨域 SSO + 多身份系统"（如淘宝/闲鱼/支付宝通用登录）
- 流程 D 适用于所有"前端轮询 + 用户主动取消"的场景（不限登录）
- 流程 E 适用于所有"主进程调子进程 + 需要可观测性"的架构
- 流程 F 适用于所有"浏览器自动化 + 资源加载优化"场景

---

## 六、衍生规范（直接可落地为强制规则）

### 6.1 强制规范：浏览器进程互斥

> 任何共享 `user_data_dir` 的 Chromium 实例启动前必须：清理锁文件 + 获取进程互斥锁 + 退出后等待 SQLite flush。禁止多个 Chromium 并发使用同一 user_data_dir。

### 6.2 强制规范：异步写入等待

> 任何异步写入操作（Cookie、SQLite、storage_state）完成后，必须显式等待 N 秒（由配置决定）再读取。一次读取失败必须兜底重读一次。

### 6.3 强制规范：Cookie 域白名单

> Cookie 域过滤必须包含所有相关域（goofish + taobao），禁止仅按单一域过滤。登录态判定以关键 Cookie（unb/_tb_token_/cookie2）为准，且必须校验值有效性（unb.isdigit + len>=6）。

### 6.4 强制规范：占位符过滤

> 任何从 DOM 抓取的业务文本（昵称、用户名、状态文案）必须过滤占位符集合（_INVALID_NICKS），禁止直接信任首次抓取结果。二次重试机制必须存在（wait_for_selector + 固定 sleep 兜底）。

### 6.5 强制规范：前端取消操作顺序

> 任何"轮询 + 取消"场景，前端必须先停本地轮询（clearInterval）再调远程 cancel API。轮询 resolve 不应覆盖用户主动设置的状态。

### 6.6 强制规范：子进程异常可观测

> 任何 subprocess 调用必须捕获 stderr + 记录 returncode + 用 logger.warning（而非 debug/pass）。禁止 `except Exception: pass` 静默吞异常。

### 6.7 强制规范：资源拦截白名单

> Playwright `route` 拦截策略必须：不拦截 stylesheet + 域名白名单放行业务关键资源 + 拦截类型走配置。禁止硬编码拦截类型和域名。

### 6.8 强制规范：配置化要求（无硬编码）

> 所有可变参数（等待时间、Cookie 域、占位符集合、选择器、拦截类型）必须通过 YAML 配置管理，禁止散落在代码中。新增参数必须同步更新 `*.example.yaml` 模板和 Pydantic AppConfig 字段。

---

## 七、配置化要求（无硬编码）

### 7.1 配置项清单

| 配置项 | 默认值 | 配置文件 | Pydantic 字段 |
|---|---|---|---|
| 无效昵称占位符 | `["登录", "登錄", "Login", "Sign in", "立即登录", "Hi! 你好", "Hi！你好", "你好", "Hi", "Hi!"]` | `config/auth.yaml` | `AuthConfig.invalid_nicks: list[str]` |
| Cookie 域白名单 | `["goofish", "taobao"]` | `config/browser.yaml` | `BrowserConfig.auth_cookie_domains: list[str]` |
| 关键登录 Cookie | `["unb", "_tb_token_", "cookie2"]` | `config/auth.yaml` | `AuthConfig.login_cookie_names: list[str]` |
| Cookie 写入等待 | `3.0` 秒 | `config/auth.yaml` | `AuthConfig.cookie_write_wait_sec: float` |
| SQLite flush 等待 | `2.0` 秒 | `config/auth.yaml` | `AuthConfig.sqlite_flush_wait_sec: float` |
| auth_helper 延迟 | `5.0` 秒 | `config/auth.yaml` | `AuthConfig.helper_delay_sec: float` |
| unb 兜底重读等待 | `3.0` 秒 | `config/auth.yaml` | `AuthConfig.unb_reread_wait_sec: float` |
| SPA 选择器等待 | `5.0` 秒 | `config/auth.yaml` | `AuthConfig.selector_wait_sec: float` |
| 资源拦截类型 | `["font", "media", "image", "manifest"]` | `config/browser.yaml` | `BrowserConfig.resource_block_types: list[str]` |
| 资源放行域名 | `["login.taobao.com", "passport.taobao.com", "mini_login", "alipay.com"]` | `config/browser.yaml` | `BrowserConfig.resource_allow_domains: list[str]` |
| 昵称选择器 | `[...]` | `config/auth.yaml` | `AuthConfig.nick_selectors: list[str]` |
| unb 测试值黑名单 | `["123456", "123"]` | `config/auth.yaml` | `AuthConfig.unb_test_values: list[str]` |
| unb 最小长度 | `6` | `config/auth.yaml` | `AuthConfig.unb_min_length: int` |
| cookie2 最小长度 | `10` | `config/auth.yaml` | `AuthConfig.cookie2_min_length: int` |
| auth_helper 超时 | `60` 秒 | `config/auth.yaml` | `AuthConfig.helper_timeout_sec: int` |
| 扫码登录超时 | `200` 秒 | `config/auth.yaml` | `AuthConfig.qr_timeout_sec: int` |
| userinfo 缓存 TTL | `300` 秒 | `config/auth.yaml` | `AuthConfig.userinfo_ttl_sec: float` |

### 7.2 配置加载示例

```python
# src/xianyu_hunter/infra/yaml_config.py
from pydantic import BaseModel, Field

class AuthConfig(BaseModel):
    """认证模块配置（无硬编码，全部走 YAML）"""
    invalid_nicks: list[str] = Field(
        default=["登录", "登錄", "Login", "Sign in", "立即登录",
                 "Hi! 你好", "Hi！你好", "你好", "Hi", "Hi!"],
        description="无效昵称占位符集合（SPA 默认欢迎语等）"
    )
    login_cookie_names: list[str] = Field(
        default=["unb", "_tb_token_", "cookie2"],
        description="关键登录 Cookie 名称（任一存在即视为已登录）"
    )
    cookie_write_wait_sec: float = Field(
        default=3.0, description="Cookie 异步写入等待时间"
    )
    sqlite_flush_wait_sec: float = Field(
        default=2.0, description="SQLite flush 等待时间"
    )
    helper_delay_sec: float = Field(
        default=5.0, description="auth_helper 延迟触发时间（避免与 browser_login 争用 user_data_dir）"
    )
    unb_reread_wait_sec: float = Field(
        default=3.0, description="unb 兜底重读等待时间"
    )
    selector_wait_sec: float = Field(
        default=5.0, description="SPA 选择器等待时间"
    )
    unb_test_values: list[str] = Field(
        default=["123456", "123"], description="unb 测试值黑名单"
    )
    unb_min_length: int = Field(default=6, description="unb 最小长度")
    cookie2_min_length: int = Field(default=10, description="cookie2 最小长度")
    helper_timeout_sec: int = Field(default=60, description="auth_helper 子进程超时")
    qr_timeout_sec: int = Field(default=200, description="扫码登录整体超时")
    userinfo_ttl_sec: float = Field(default=300, description="userinfo 缓存 TTL")
    nick_selectors: list[str] = Field(
        default=[
            '[class*="userInfo"] [class*="nick"]',
            '[class*="user-info"] [class*="nick"]',
            '[class*="userInfo--"] [class*="nick--"]',
            '[class*="userName"]',
            '[class*="nickName"]',
            '[class*="username"]',
            'header [class*="nick"]',
            'a[href*="personal"] [class*="nick"]',
        ],
        description="昵称元素 CSS 选择器集合"
    )

class BrowserConfig(BaseModel):
    """浏览器配置（含资源拦截策略）"""
    # ... 已有字段 ...
    auth_cookie_domains: list[str] = Field(
        default=["goofish", "taobao"],
        description="Cookie 域白名单（unb 实际在 .taobao.com 域）"
    )
    resource_block_types: list[str] = Field(
        default=["font", "media", "image", "manifest"],
        description="资源拦截类型（不含 stylesheet，CSS 缺失会导致布局错乱）"
    )
    resource_allow_domains: list[str] = Field(
        default=["login.taobao.com", "passport.taobao.com", "mini_login", "alipay.com"],
        description="资源放行域名（登录页扫码二维码与登录页资源）"
    )
```

### 7.3 配置使用示例

```python
# scripts/auth_helper.py
def _cmd_info(out_dir: Path) -> int:
    cfg = _get_browser_cfg()
    auth_cfg = _get_auth_cfg()  # 新增

    # ✅ 从配置读取，无硬编码
    goofish_cookies = [
        c for c in cookies
        if any(d in (c.get("domain") or "") for d in cfg.auth_cookie_domains)
    ]

    login_cookie_names = set(auth_cfg.login_cookie_names)
    has_login_cookie = bool(login_cookie_names & goofish_names)

    # ✅ 占位符过滤从配置读取
    _is_invalid_first = (not raw_nick) or (raw_nick in auth_cfg.invalid_nicks)

    # ✅ 等待时间从配置读取
    if _uid_via_tb_token:
        await page.wait_for_timeout(int(auth_cfg.unb_reread_wait_sec * 1000))

    # ✅ 选择器从配置读取
    await page.wait_for_selector(
        ", ".join(auth_cfg.nick_selectors),
        timeout=int(auth_cfg.selector_wait_sec * 1000),
        state="visible",
    )
```

```python
# scripts/browser_login.py
async def _block_resources(route):
    req = route.request
    url = req.url.lower()
    cfg = _get_browser_cfg()

    # ✅ 域名白名单从配置读取
    if any(d in url for d in cfg.resource_allow_domains):
        await route.continue_()
        return

    # ✅ 拦截类型从配置读取（不含 stylesheet）
    if req.resource_type in cfg.resource_block_types:
        await route.abort()
        return

    await route.continue_()
```

```python
# src/xianyu_hunter/web/services/auth_manager.py
class AuthManager:
    def __init__(self) -> None:
        # ✅ 从配置读取，无硬编码
        auth_cfg = _get_auth_cfg()
        self.USERINFO_TTL = auth_cfg.userinfo_ttl_sec
        self.QR_TIMEOUT = float(auth_cfg.qr_timeout_sec)

    def trigger_refresh_userinfo_async(self, delay: float | None = None) -> None:
        auth_cfg = _get_auth_cfg()
        # ✅ delay 默认值从配置读取
        if delay is None:
            delay = auth_cfg.helper_delay_sec
        # ...
```

---

## 八、落地映射

| 规范 | 后端审查规则 | 前端审查规则 | 配置节点 |
|---|---|---|---|
| 6.1 浏览器进程互斥 | `BAC-01 ~ BAC-04`（浏览器自动化与子进程） | — | `browser.auth_cookie_domains` / `auth.helper_delay_sec` |
| 6.2 异步写入等待 | `BAC-05 ~ BAC-07`（浏览器自动化与子进程） | — | `auth.cookie_write_wait_sec` / `auth.sqlite_flush_wait_sec` |
| 6.3 Cookie 域白名单 | `BAC-08 ~ BAC-10`（浏览器自动化与子进程） | — | `browser.auth_cookie_domains` / `auth.login_cookie_names` |
| 6.4 占位符过滤 | `BAC-11`（浏览器自动化与子进程） | — | `auth.invalid_nicks` / `auth.nick_selectors` |
| 6.5 前端取消操作顺序 | — | `FAC-01 ~ FAC-03`（异步操作与状态机） | — |
| 6.6 子进程异常可观测 | `BAC-12`（浏览器自动化与子进程） | — | `auth.helper_timeout_sec` |
| 6.7 资源拦截白名单 | `BAC-13`（浏览器自动化与子进程） | — | `browser.resource_block_types` / `browser.resource_allow_domains` |
| 6.8 配置化要求 | `BAC-14`（浏览器自动化与子进程） | `FAC-04`（异步操作与状态机） | 所有 `auth.*` / `browser.*` 节点 |

**配套技能更新**：
- `xianyu-hunter-dev`：补充 8 项强制规范 + 配置化要求清单
- `xianyu-backend-code-review`：新增 `BAC-01 ~ BAC-14` 共 14 项检查点（浏览器自动化与子进程维度）
- `xianyu-frontend-code-review`：新增 `FAC-01 ~ FAC-04` 共 4 项检查点（异步操作与状态机维度）
- 所有新规则参数集中在 `config/auth.yaml` + `config/browser.yaml` 管理（无硬编码）

---

## 九、相关文件

| 文件 | 职责 |
|------|------|
| `scripts/browser_login.py` | Playwright 有头浏览器登录入口子进程 |
| `scripts/auth_helper.py` | 用户昵称/头像抓取子进程（headless） |
| `src/xianyu_hunter/web/services/auth_manager.py` | 认证状态管理器（含 _refresh_lock 互斥） |
| `src/xianyu_hunter/web/routes/unified_login.py` | 统一登录路由（delay=5.0 触发） |
| `src/xianyu_hunter/web/routes/cookie_inject.py` | Cookie 注入登录路径 |
| `src/xianyu_hunter/web/routes/auth_query.py` | /me 路由（含 _INVALID_NICKS 过滤） |
| `src/xianyu_hunter/web/services/user_manager.py` | 用户身份识别（unb > sha256(cookie2)[:16]） |
| `src/xianyu_hunter/infra/browser.py` | Worker 浏览器管理（CDP 模式） |
| `src/xianyu_hunter/web/services/cookie_store.py` | Cookie 存储（_GOOFISH_KEY_COOKIES 集合） |
| `frontend/src/pages/Login/index.tsx` | 前端登录页（防抖 + 取消逻辑） |
| `frontend/src/components/layout/UserMenu.tsx` | 用户菜单（computeDisplayName 优先级） |
| `config/auth.yaml` | 认证模块配置（新增，无硬编码参数集中管理） |
| `config/browser.yaml` | 浏览器配置（含资源拦截策略） |

---

## 十、版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-07-04 | 初版：基于登录模块 11 类问题复盘，提炼 6 大流程 + 8 项强制规范 + 17 项配置化要求 |
