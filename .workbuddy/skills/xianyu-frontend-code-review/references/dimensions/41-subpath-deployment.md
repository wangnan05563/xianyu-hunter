# 维度 41：SPA 子路径/域名模式部署前缀一致性 🆕v4.67.0

> **编码规范引用**：xianyu-hunter-dev `references/deployment-runtime-standards.md` 规范 S1
> **配置节点**：config.yaml#checklist.subpath_deployment
> **测试关联**：xianyu-auto-testing 模式 AL（子路径部署一致性验证）

## 触发条件
- 项目前端以非根路径部署（`vite.config.ts` 中 `base: '/xianyu/'`）时，任何新增/修改涉及：
  - `fetch(...)` / `new EventSource(...)` 的原始请求
  - `<a href>` / `window.open(...)` / `Button href` 等导航链接
  - axios 实例的 `baseURL` 配置
  - PWA `vite.config.ts` 的 `navigateFallbackDenylist` / `runtimeCaching.urlPattern`

## 检查规则

### 强制（P0 阻塞）
- 不允许把整个 `/xianyu/` 前缀直接塞进后端公开白名单（属安全漏洞，由后端维度 41 约束）。

### 推荐（P1 严重）
- 所有 `fetch(...)` / `new EventSource(url)` 的 URL 必须基于 `API_BASE` 拼接（`` `${API_BASE}api/...` ``），**禁止裸 `/api/...` 字面量**（排除 axios 实例的相对路径与 PWA `urlPattern` 正则）。
- 所有文档/导出等导航链接（`<a href>`、`window.open`、`Button href`）必须使用 `API_BASE` 拼接，**禁止硬编码 `/api/docs`、`/api/logs/export` 等**。
- `apiBase.ts` 的 `API_BASE` 必须是单一可信源，axios `baseURL: API_BASE`；不允许在组件里另写一套前缀逻辑。
- `vite.config.ts` 的 `navigateFallbackDenylist` 与 `runtimeCaching.urlPattern` 必须覆盖 `/xianyu/api/`（不只 `/api/`），否则 Service Worker 会错误缓存或拦截 API 请求。
- 若 `vite.config.ts` 的 `base` 为非根路径，则 `BrowserRouter` 的 `basename` 必须一致。

### 推荐（P2 改进）
- 原始请求前缀逻辑集中在 `api/` 模块或 `utils/apiBase.ts`，避免散落各页面文件。

## Grep 扫描命令
```bash
# 检测裸 /api/ 字面量（排除 axios 实例相对路径、PWA urlPattern、测试断言）
grep -rn "'/api/\|"/api/\|`/api/" frontend/src/ --include="*.ts" --include="*.tsx"

# 检测未带 API_BASE 的 fetch / EventSource
grep -rn "fetch(\s*['\"/]\|new EventSource(\s*['\"/]" frontend/src/ --include="*.ts" --include="*.tsx"

# 检测硬编码文档/导出链接
grep -rn "href:\s*'/api\|open('/api\|href=\"\/api" frontend/src/ --include="*.ts" --include="*.tsx"

# 检测 PWA 是否覆盖 /xianyu/api
grep -n "xianyu/api" frontend/vite.config.ts
```

## 判断标准
- 裸 `/api/` 字面量出现在原始请求/链接 → P1 严重
- PWA `sw.js` 构建产物不含 `/xianyu/api` → P2 改进
- 前缀逻辑散落多文件且无单一源 → P2 改进
- 白名单误加 `/xianyu/`（后端侧）→ 由后端维度 41 判 P0

## 适用场景
- `frontend/src/api/*.ts` 原始请求封装
- `frontend/src/pages/**` 中的 `fetch`/`EventSource`/导航链接
- `frontend/vite.config.ts` PWA 配置
- 任何以子路径部署的 SPA 项目（可泛化到任意 `base` 非 `/` 的场景）

## 不适用场景
- 纯根路径部署（`base: '/'`）且反向代理 strip 模式：仅"原始请求不要裸拼 host"仍适用，子路径专属项可跳过
- 后端 `*.py` 路由/中间件：由 xianyu-backend-code-review 维度 41/42 负责
- 非 SPA 多页应用 / SSR 应用：路由与 SW 机制不同
- 第三方库内部请求（不在本仓库源码控制范围）
