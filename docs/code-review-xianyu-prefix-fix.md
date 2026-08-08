# 代码走查报告：/xianyu 子路径 API 前缀修复

- 评审日期：2026-08-05
- 触发：本会话修改的代码逻辑走查（xianyu-backend-code-review + xianyu-frontend-code-review）
- 范围：仅本会话改动文件（非工作区其它预存在改动）
- 结论：**功能正确，无 P0 阻塞；1 项 P1 安全观察 + 1 项 P2 可维护性 + 2 项 P3 微调**

---

## 一、改动文件清单（本次会话）

| 文件 | 类型 | 改动 |
|------|------|------|
| `frontend/src/utils/apiBase.ts` | 新增 | `API_BASE = import.meta.env.BASE_URL`（构建后 `/xianyu/`） |
| `frontend/src/api/client.ts` | 改 | axios `baseURL: ''` → `API_BASE` |
| `frontend/src/api/task.ts` | 改 | 1 处 `fetch('/api/...')` → `${API_BASE}api/...` |
| `frontend/src/pages/Chatbot/hooks/useSSEChat.ts` | 改 | `fetch('/api/chatbot/chat')` → 带前缀 |
| `frontend/src/pages/Login/index.tsx` | 改 | 2 处 `fetch('/api/auth/cookie/fetch-keys')` → 带前缀 |
| `frontend/src/pages/Items/ItemList.tsx` | 改 | `EventSource('/api/events/stream')` → 带前缀 |
| `frontend/src/pages/Dashboard/index.tsx` | 改 | `EventSource` → 带前缀 |
| `frontend/src/pages/Orders/Orders.tsx` | 改 | `EventSource` → 带前缀 |
| `frontend/vite.config.ts` | 改 | PWA SW `navigateFallbackDenylist` + `runtimeCaching.urlPattern` 覆盖 `/xianyu/api/` |
| `src/xianyu_hunter/web/app.py` | 改 | 以 `prefix="/xianyu"` 重复挂载全部 API 路由；登录浮层 `fetch` 按 pathname 推导前缀 |

---

## 二、后端走查（xianyu-backend-code-review）

### 维度 18 Web 层规范 / 维度 19 API 设计规范 / 维度 21 架构与分层
- **双挂载逻辑正确**：`app.py:613-615` 在所有根路由注册后，再以 `prefix="/xianyu"` 挂载同一批 router。
  - 代理剥离 `/xianyu` → 落到 `/api/*`（命中根路由）
  - 代理透传全路径 → 命中 `/xianyu/api/*`
  - 根 `/api/*` 保留，打包模式（`localhost:8001`）不受影响。
- **与根挂载一致性**：`_XY_API_MODULES` 列表（33 个模块）与根 `include_router` 列表完全对应；`api_task_links._links_lookup` 在根层也有独立挂载（`:558`），双挂载一一对应，**无路由遗漏/重复导致的回归**。
- **路由注册顺序正确（关键）**：SPA catch-all（`app.py:660-678`，`/{full_path:path}`）注册在 `/xianyu/api/*` 路由**之后**；且 `_serve_spa_request`（`:390`）对 `xianyu/api/` 前缀直接返回 404 JSON，不会被 SPA 回退吞掉。**新 API 路由不会被静态 catch-all 遮蔽。**
- `py_compile` 通过。

### 维度 7 安全性评审 ⚠️（P1 观察）
- `middleware/auth.py` 的 `PUBLIC_PREFIXES` 含** blanket `/xianyu/`** 条目（预存在设计，本次未改）。本次双挂载后，`/xianyu/api/*` 全部命中该前缀 → **在“代理不剥离前缀”的部署下，所有 API 端点变为免认证**（绕过 WEB_TOKEN / session 校验）。
- 这与项目既定设计自洽：`/xianyu/*` 被视为“Tailscale Funnel 暴露、由网络 ACL 兜底认证”的命名空间，SPA 页面原本就靠该 blanket 放行。但本次改动把**可直达的免认证面**从“仅 SPA 页面”扩大到了“API 端点”。
- **建议（二选一，推荐 A）**：
  - A. 在 `PUBLIC_PREFIXES` 显式补充 `/xianyu/api/auth/...`、`/xianyu/api/events/stream`、`/xianyu/api/logs/stream` 等白名单项，并将 `/xianyu/api/<非白名单>` 视同 `/api/<非白名单>` 强制校验 token（复用现有 `request.url.path.startswith("/api/")` 判定逻辑，扩展为同时判断 `/xianyu/api/`）。
  - B. 在反向代理层把 `/xianyu/api` 重写为 `/api`（剥离前缀），则后端只需根路由，前端单点加前缀即可，彻底避免双挂载与免认证面扩大。
- **需用户确认**：`*.ts.net` 域名是否始终只经 Tailscale Funnel（带 ACL）暴露、不存在后端端口直连。若是，则当前 blanket 可接受；否则必须做 A。

### 维度 13 代码质量（P2 改进）
- `_XY_API_MODULES` 列表与根 `include_router` 列表**重复**，新增路由时需同步两处，存在漂移风险。建议抽成一个 `(module, router[, extra])` 列表，循环两次（一次无前缀、一次 `prefix="/xianyu"`）：
  ```python
  API_ROUTERS = [
      (api_tasks, "router"), (api_task_links, "router"),
      (api_task_links, "_links_lookup"),  # 特殊：独立 router 对象
      ...
  ]
  for mod, attr in API_ROUTERS:
      app.include_router(getattr(mod, attr))
      app.include_router(getattr(mod, attr), prefix="/xianyu")
  ```

### 维度（P3 微调）
- 双挂载使路由数翻倍 → OpenAPI schema / `/docs` 体积增大、路由匹配开销微增（可忽略，但 `/docs` 文档会出现成对重复条目）。

---

## 三、前端走查（xianyu-frontend-code-review）

### 维度 7 API 调用 ✅
- `API_BASE = import.meta.env.BASE_URL`（`/xianyu/`）。
- **axios 路径拼接经验证正确**：`baseURL:'/xianyu/'` + `client.post('/api/auth/login')` 实际请求为 `/xianyu/api/auth/login`（**单斜杠**，已用 node+axios 实测三方组合均正确，无双斜杠）。
- 原始 `fetch` 调用 `${API_BASE}api/...` = `/xianyu/` + `api/...` = `/xianyu/api/...`（单斜杠，正确）。
- **覆盖完整性**：全仓仅 1 个 axios 实例（`client.ts`），所有 `client.get/post('/api/...')` 自动继承 baseURL；另有 7 处绕过 axios 的原始 `fetch`/`EventSource` 已全部加前缀。未发现其它 axios 实例或 WebSocket 端点遗漏。

### 维度 28 多用户认证隔离 ✅
- 所有原始 `fetch` 保留 `credentials: 'include'`（Login ×2、task.ts 用 Bearer header）；`useSSEChat` 保留 `credentials:'include'`；`EventSource` 同源自动带 cookie。登录态透传未被破坏。

### 维度 13 PWA 配置 ✅
- `navigateFallbackDenylist` 增加 `/^\/xianyu\/api\//`，API 请求不被 SPA 回退。
- `runtimeCaching.urlPattern` 对 `events/stream`、`auth/*`、`export/*` 的排除项同步覆盖 `/xianyu/api/` 变体，SSE 长连接与鉴权/流式接口不会被 SW 误缓存。

### 维度 4 TypeScript 严格 ✅
- `API_BASE` 显式标注 `: string`；`tsc --noEmit` 退出码 0，无类型错误。

### 维度 25 失败原因链前端同步（说明）
- 原“请求失败”根因（路径 404 → axios 拿不到 JSON 错误体 → 统一兜底）已消除。兜底文案本身未改（属预存在问题，不在本次范围）；建议后续让登录失败区分 401/网络错误，避免真故障被同一兜底掩盖。

### 维度（P3 微调）
- `task.ts` 的 `fetch`（`/xianyu/api/tasks/.../links/live`）未带 `credentials:'include'`，仅用 Bearer header；与其余原始 fetch 不一致。当前因 `/xianyu/` blanket 免认证而可工作，建议统一补 `credentials:'include'` 以防后续鉴权策略收紧。

---

## 四、验证记录

| 项 | 方法 | 结果 |
|----|------|------|
| 前端类型 | `tsc --noEmit` | 退出 0 ✅ |
| 后端语法 | `py_compile app.py` | OK ✅ |
| axios 斜杠 | node+axios 实测 | `/xianyu/api/...` 单斜杠 ✅ |
| 路由遮蔽 | 读 `app.py` 注册顺序 + catch-all 404 规则 | 不遮蔽 ✅ |
| 鉴权命中 | 读 `middleware/auth.py` | `/xianyu/api/*` 经 `/xianyu/` blanket 放行（见 P1） |
| API 覆盖 | 全仓 grep axios/fetch/EventSource | 1 实例 + 7 处原始调用，全覆盖 ✅ |

---

## 五、优先级汇总

- **P0 阻塞**：无
- **P1 严重**：后端 `/xianyu/` blanket 公钥前缀使 `/xianyu/api/*` 在透传部署下免认证（需确认 Funnel ACL 兜底或收敛白名单）
- **P2 改进**：`_XY_API_MODULES` 与根挂载列表重复，建议合并为单一路由表循环
- **P3 微调**：双挂载路由翻倍；`task.ts` fetch 缺 `credentials`

---

## 六、结论
本次 `/xianyu` 前缀修复**逻辑正确、可上线**，根因（域名模式 `/api/*` 落到根路径被代理拦截 → “请求失败”）已解决。唯一需在上线前拍板的是 **P1 安全观察**：确认远程域名的认证边界，或按建议 A 收敛 `/xianyu/api/*` 的免认证范围。
