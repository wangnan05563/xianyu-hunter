# 模式 AM：隧道 / 域名访问 404 诊断

## 触发关键词
隧道裸根404 / 域名访问404 / page not found / 子路径跳转不过去 / 账户切换跳404 / 404 page not found

## 配置节点
`tunnel_access_404`（建议新增于 config.yaml），引用字段均从配置读取，禁止硬编码：
- `tunnel.path_prefix`（默认 `/xianyu/`）— funnel 仅转发该作用域
- `spa.basename` — SPA 路由前缀（与 `vite.config.ts base` 同源）
- `deploy.spa_dist` — 部署 SPA 目录（用于 src→dist 对齐校验）
- `web_process` — 端口/进程检查

## 诊断决策树（DT-12）
1. 现象：域名/隧道访问点账户切换跳 `https://…ts.net/`（裸根）显示 `404 page not found`？
2. 检查前端入口 chunk 的 `location.replace` 目标：
   - 含裸根 `/` → 违规（规范 23）；修复 `AccountSwitcher.tsx` 改用 `BASE_URL`。
   - 含 `/xianyu/` → 进入 3。
3. 检查部署副本 `deploy.spa_dist/index.html` 引用的入口 chunk 是否当前构建（hash 是否最新、是否含 `location.replace('/')` 旧标志）：
   - 旧构建 → 部署未对齐（规范 26）；执行 src→dist 对齐。
   - 当前构建 → 进入 4。
4. 检查 `tunnel.path_prefix` 配置与 funnel `--set-path` 是否一致（规范 24）；检查 `app.py` `@app.get("/")` 是否直出 index.html（非重定向，避免 funnel 下循环）。
5. 客户端 PWA SW 陈旧缓存（规范 25）：指导清 SW 缓存 / 硬刷新。

## 判断标准
- P0：前端重定向裸根 / 部署副本陈旧 → 必须修复
- P1：path_prefix 配置不一致 / `@app.get("/")` 重定向循环
- P2：客户端 SW 陈旧缓存（用户侧清缓存即可）

## 关联规范（保持跨技能一致）
- xianyu-hunter-dev 规范 23-26
- xianyu-frontend-code-review F-REVIEW-SPA-REDIRECT-SCOPE / F-REVIEW-SPA-DEPLOY-BASEPATH
- xianyu-backend-code-review B-REVIEW-TUNNEL-PATH-PREFIX / B-REVIEW-SPA-DEPLOY-ALIGN
- 模式 AL（子路径部署一致性）为本模式的广义前置，优先排查
