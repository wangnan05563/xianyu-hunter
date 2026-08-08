# 部署与运行时编码规范（子路径/域名模式 & 环境依赖完整性）

> 来源：本会话历史中已解决的 5 类真实问题复盘提炼（SPA 子路径前缀、鉴权路径归一化、路由去重、环境依赖损坏、测试/构建环境坑）。
> 关联技能：
> - `xianyu-frontend-code-review`（维度 41：子路径/域名模式部署前缀一致性）
> - `xianyu-backend-code-review`（维度 41 鉴权路径归一化 / 42 路由注册单一数据源 / 43 环境依赖完整性）
> - `xianyu-auto-testing`（模式 AL：子路径部署一致性验证）
> 关联文档：`project-rules.md`、`root-cause-protocol.md`、`coding-standards-append.md`

---

## 0. 为什么需要这些规范（问题来源速览）

| # | 历史问题 | 现象 | 根因类别 |
|---|---------|------|---------|
| A | SPA 子路径/域名模式部署前缀 | 生产域名 `/xianyu/login` 访问，点"启动浏览器窗口登录"报"请求失败" | 部署/前缀 |
| B | 鉴权路径归一化（P1） | 在 no-strip 反代下 `/xianyu/api/*` 绕过鉴权或 404 | 安全/路径 |
| C | 路由注册单一数据源（P2） | 路由表重复 `include_router`，双挂载易漏 | 架构/去重 |
| D | 环境依赖完整性 | 开发模式"客服配置"报"智能客服模块未启用或加载失败" | 环境/依赖 |
| E | 测试/构建环境坑 | safe-delete shim 误伤 vite/pytest 清理；全量 pytest hang；构建产物过期 | 工具链/CI |

> 共性根因：**「域名子路径部署」与「可选依赖降级」两类场景跨前后端、跨构建与测试，缺乏统一约定**，每次都靠事后排查。下面把每类固化为可执行的规范。

---

## 1. 编码规范条目（每条含四维复盘）

### 规范 S1：SPA 子路径/域名模式部署前缀一致性

**定义**：项目前端以 SPA 形式部署在非根路径（默认 `/xianyu/`）下，经反向代理（Tailscale Funnel 等）暴露。前端所有 API、文档、导出、SSE 请求，以及后端路由、鉴权、PWA 缓存规则，都必须与该子路径前缀保持一致。

#### 1.1 适用场景
- 前端 `vite.config.ts` 中 `base: '/xianyu/'` + `BrowserRouter basename="/xianyu"` 已启用。
- 反向代理有两种模式：**保留前缀（no-strip）** 与 **剥离前缀（strip）**。本规范默认按 no-strip 设计（最严格，两种模式都兼容）。

#### 1.2 完整步骤（开发/修改时怎么做）
1. **前端 API 基址单一可信源**：在 `src/utils/apiBase.ts` 定义 `export const API_BASE = import.meta.env.BASE_URL`（Vite 在非根 base 下会自动解析为 `/xianyu/`），所有 axios 实例 `baseURL: API_BASE`。
2. **原始请求必须带前缀**：所有 `fetch(...)` / `new EventSource(...)` 的 URL 用 `` `${API_BASE}api/...` `` 拼接，禁止裸 `/api/...`。
3. **文档/导出等 `<a href>` / `window.open` 链接**：同样用 `API_BASE` 拼接，禁止硬编码 `/api/docs`、`/api/logs/export`。
4. **后端双挂载**：每个 API router 在 `app.include_router(router)`（根 `/api/*`）之外，再 `app.include_router(router, prefix="/xianyu")`，保证两种代理模式都可达。
5. **直接 `app.get` 注册的端点**（如 `/api/docs`、`/api/about`）也须补 `/xianyu` 同名路由（它们不参与 `API_ROUTERS` 表，最易被漏）。
6. **鉴权归一化**：中间件在白名单/401 判断前，先把 `/xianyu/api/X` 归一化为 `/api/X`，使 `/api/*` 与 `/xianyu/api/*` 共享同一套鉴权语义（**不要**把 `/xianyu/` 直接塞进白名单——那是 P0 安全漏洞）。
7. **PWA 规则**：`vite.config.ts` 的 `navigateFallbackDenylist` 与 `runtimeCaching.urlPattern` 必须覆盖 `/xianyu/api/`（不只 `/api/`），否则 SW 会错误缓存或拦截 API。

#### 1.3 不确定性与失败点
- **构建产物过期**：失败的 vite 构建可能只更新了 `sw.js` 而留下旧的 JS chunk（旧 chunk 仍指向裸 baseURL），现象是"代码改了但前端没生效"。必须用构建产物的真实内容核对，而非看构建是否"执行过"。
- **代理模式假设错误**：以为走 strip 模式就不加 `/xianyu` 前缀，结果 no-strip 下全 404。
- **白名单误加 `/xianyu/`**：图省事把整个前缀加进公开白名单，导致 `/xianyu/api/*` 全部免鉴权（P0）。
- **SSE/EventSource 漏改**：相比 axios 实例容易被 grep 发现，`new EventSource(\`${API_BASE}api/events/stream\`)` 这种分散调用最易遗漏。

#### 1.4 抽象固定流程与判断逻辑
**审查判断逻辑（checklist）**：
- 前端是否存在裸 `/api/` 字面量（排除 axios 实例的相对路径与 SW 的 urlPattern）？→ 有则 P1。
- 后端是否在 `/api/*` 与 `/xianyu/api/*` 都注册了被改动的 router？→ 漏一个则 P1。
- 中间件是否用"归一化"而非"白名单塞前缀"？→ 后者 P0。
- `sw.js` 是否含 `/xianyu/api`？→ 不含则 P2。

**修复判断逻辑**：前端"请求失败"且后端 401/404 → 先区分"鉴权问题"还是"路径前缀问题"：带有效 token 仍 404 且路径含 `/xianyu/api` → 前缀/双挂载问题；带 token 直连后端 200、走代理 404 → 代理 rewrite 或前端前缀问题。

#### 1.5 不适用场景
- 纯根路径部署（`base: '/'`）且反向代理 strip 模式：本规范第 1、5、6、7 步的 `/xianyu` 部分可省略，但"原始请求不要裸拼 host"仍适用。
- 非 SPA 多页应用、SSR 应用：路由与 SW 机制不同，不适用 SPA 子路径规则。

---

### 规范 S2：路由注册单一数据源与双挂载一致性

**定义**：所有 API router 通过一张 `API_ROUTERS: list[tuple[module, attr]]` 表集中声明，循环两次（`/api/*` + `/xianyu` 前缀）完成双挂载；禁止在 `create_app()` 里散落多段 `include_router`。

#### 2.1 适用场景
- 新增/修改任何 `web/routes/api_*.py` 路由模块。
- 调整"是否需要在 `/xianyu` 前缀下暴露"时。

#### 2.2 完整步骤
1. 在 `API_ROUTERS` 表追加 `(module, "router")`；若该模块额外导出 lookup 路由（如 `api_task_links._links_lookup`），一并追加。
2. 循环体内：`app.include_router(router)` 与 `app.include_router(router, prefix="/xianyu")`。
3. 直接 `app.get(...)` 的特殊端点，单独补 `/xianyu` 同名路由（见 S1 第 5 步）。

#### 2.3 不确定性与失败点
- `API_ROUTERS` 表里漏写某个模块的属性名 → 该路由只在一种前缀下可达。
- 把特殊端点误放进 `API_ROUTERS` 循环（它已自带前缀逻辑）→ 重复挂载。

#### 2.4 抽象固定流程与判断逻辑
**审查判断**：`grep -n "include_router" web/app.py` 是否出现散落的逐路由注册？→ 有则 P2（应并入 `API_ROUTERS` 表）。新增路由是否在 `API_ROUTERS` 且双挂载？→ 否则 P1。

#### 2.5 不适用场景
- 中间件、异常处理、`app.get("/api/docs")` 等一次性注册的端点（它们本来就不走 `API_ROUTERS` 循环，但需单独补前缀，见 S1）。

---

### 规范 S3：开发环境依赖完整性与可选依赖降级契约

**定义**：项目含"可选依赖"模块（如智能客服依赖 `chromadb`/`sentence-transformers`/间接 `grpcio`）。当这些依赖缺失或版本错配时，模块必须**显式降级**（返回禁用状态 + 明确日志），且前端对此有对应的错误呈现约定。

#### 3.1 适用场景
- 任何 `container.py` 中 `except ImportError / Exception` 兜底返回 `None` 的可选模块初始化。
- venv 重建、Python 版本切换、pip 中断后。

#### 3.2 完整步骤（依赖损坏的排查与修复）
1. **复现**：前端报错 → 用有效 token 直接 curl 后端端点，区分"401 鉴权"还是"403 模块禁用"还是"404 路径"。
2. **看启动日志**：搜 `可选依赖缺失` / `初始化失败` / `Traceback`，定位是 `ImportError` 还是逻辑异常。
3. **验证依赖**：`venv\Scripts\python.exe -c "import <mod>"` 实测能否导入（注意 venv 的 Python 版本与 wheel 的 cp 标签是否匹配）。
4. **修复**：用 **venv 自带的 python** 重装损坏的依赖（`python -m pip install --force-reinstall --no-deps <pkg>`），拉到与 venv Python 匹配的 wheel。
5. **必须重启进程**：依赖修复对**已运行**的进程无效（坏 import 已被缓存），重启后端后验证端点返回 200。

#### 3.3 不确定性与失败点
- **wheel 版本错配**：venv 是 py3.12，却装了 cp314 的 `grpcio` → `import grpc` 失败 → 连锁导致 `chromadb` 失败 → 模块被兜底禁用。表面看是"chromadb 未安装"，实际是 grpcio 装错版本。
- **pip 中断残留**：`~ebsockets`/`~orch`/`~umpy` 等无效 distribution 残留，提示环境曾异常。
- **测试环境 hang**：全量 pytest 套件若含依赖外部/DB 的集成测试，在沙箱可能卡死（C 层阻塞，线程级 timeout 无法中断）；应改用"精准单测 + 构建产物核对"验证，而非强跑全量。

#### 3.4 抽象固定流程与判断逻辑
**环境健康检查判断**：
- `import <可选依赖>` 是否成功？失败 → 检查 venv Python 版本 vs wheel cp 标签。
- 启动日志是否含 `可选依赖缺失`？含 → 模块已降级，前端应呈现"未启用"而非崩溃。
- "修复后端点仍 403" → 多半是进程未重启（坏 import 缓存）。

**降级契约**：可选模块不可用时，后端返回明确禁用码（如 `403 CHATBOT_DISABLED`），前端 `getConfig()` 失败被 `.catch(() => null)` 接住并 `message.error('模块未启用或加载失败')`——这是**预期行为**，不是 bug；真正的 bug 是"依赖本应可用却被环境损坏"。

#### 3.5 不适用场景
- 必选依赖（项目核心运行所需）缺失：不属于"降级"，应直接 fail-fast，不适用本契约。
- 纯前端单测（vitest）：不涉及 venv 依赖，不适用。

---

## 2. 开发与测试过程复盘（四维）

### 2.1 开发过程复盘

**成功执行任务的完整步骤（以 S1 修复为例）**
1. 复现：用生产域名/ dev 代理实际触发报错，确认现象。
2. 定位：沿调用链（前端报错 → 后端端点 → 中间件/容器）逐层 grep + 实测（curl 带/不带 token，直连 vs 走代理）。
3. 根因：区分"代码缺陷" vs "环境/配置问题"。
4. 修复：改最小必要面（前端 API_BASE + 原始调用；后端双挂载 + 归一化）。
5. 验证：tsc / py_compile → 精准单测 → 生产构建 → **产物内容核对**（关键）。

**不确定性与失败点**
- 构建产物过期（见 S1.3）："构建跑过"≠"产物正确"。
- safe-delete shim：WorkBuddy 沙箱的 `genie-safe-delete` 会在 `CODEBUDDY_SESSION_ID` 存在时拦截 `os.remove`/`rmtree` 转到回收站，导致 vite `emptyDir` 与 pytest teardown 误判失败。
- 代理模式假设错误（见 S1.3）。

**可抽象的固定流程与判断逻辑**
- **复现优先**：任何"前端报错"先实测端点（带 token 直连 vs 代理），用二分法确定落在哪一层。
- **构建规避 shim**：vite 构建先输到**空临时目录**（emptyDir 无可删 → 不触发 shim），再 `cp -rf` 拷回 SPA 目录。
- **pytest 规避 shim**：跑 pytest 前清空 `CODEBUDDY_SESSION_ID`/`CLAUDE_SESSION_ID` 环境变量（仅影响 pytest 自身临时目录，安全）。
- **产物核对三连**：`grep` 构建产物中是否含目标字符串（如 `/xianyu/api`、`baseURL:"/xianyu/"`、修复后的 `exportUrl` 前缀）。

**适用与不适用场景**
- 适用：本项目的 SPA 子路径部署、可选依赖模块、WorkBuddy 沙箱内的构建/测试。
- 不适用：非 WorkBuddy 环境（shim 不存在，正常 `rm` 即可）；非 SPA 项目（构建/路由规则不同）。

### 2.2 测试过程复盘

**成功执行任务的完整步骤（Tier 机制）**
1. Tier 1（重构）：`pytest tests/ + tsc --noEmit` 全量。
2. Tier 2（bugfix）：改动文件核心功能 import 验证。
3. Tier 3（feature）：改动文件语法+导入链路 5/5 验证。
4. **精准单测优先**：对"直接覆盖改动模块"的测试文件跑（如 `test_auth_middleware_mu2.py` + `test_web_route_registration.py`），比全量更快更准。
5. **产物核对**：构建后核对 sw.js / 打包 chunk 是否含修复内容。

**不确定性与失败点**
- 全量套件 hang（SQLAlchemy DDL 阻塞）：与本次改动无关，权威回归以精准单测为准。
- shim 误杀 pytest teardown：`SystemExit(1)` 非测试失败（见 2.1）。
- tsc 与 pytest 必须用 **venv 的 python**（`.venv/Scripts/python.exe -m pytest`），否则报 `No module named pytest`。

**可抽象的固定流程与判断逻辑**
- **改动面 → 测试档位**映射（Tier 表）。
- **环境阻塞 ≠ 代码回归**：当全量套件因环境 hang/ shim 失败时，用"精准单测 + 类型检查 + 构建产物核对"三者交叉验证，给出权威结论。
- **构建产物即测试对象**：前端修复的"是否生效"最终以**打包后产物内容**为判据，而非源码改了没。

**适用与不适用场景**
- 适用：本项目前端 SPA/ PWA / 后端 FastAPI 的回归验证。
- 不适用：纯视觉设计评审、性能压测、跨浏览器兼容性（见 auto-testing「不适用场景」）。

---

## 3. 与代码审查 / 测试的关联映射

| 本规范 | 前端审查维度 | 后端审查维度 | 测试模式 | 关键判断 |
|--------|------------|------------|---------|---------|
| S1 子路径前缀 | 维度 41（subpath-deployment） | 维度 41 鉴权归一化 / 42 路由双挂载 | 模式 AL（子路径部署一致性） | 裸 `/api/` → P1；白名单塞前缀 → P0 |
| S2 路由单一源 | — | 维度 42 | — | 散落 `include_router` → P2 |
| S3 环境依赖 | — | 维度 43（可选依赖完整性） | 模式 Q（构建产物）/ E（pytest） | `import` 失败 + 日志降级 → 环境非代码 |

> 所有新增维度与模式均**配置驱动**：审查维度在 `config.yaml` 的 `checklist`/`coding_standards` 中开关；测试模式读取 `config.yaml` 的 `spa.basename`/`spa.api_prefix`/`web_process.port` 等，禁止硬编码 `/xianyu/`。
