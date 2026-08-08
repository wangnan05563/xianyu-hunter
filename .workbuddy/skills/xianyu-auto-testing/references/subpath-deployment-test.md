# AL. 子路径部署一致性验证

> 对应决策节点：DT-01（web 未运行）/ DT-02（构建产物缺失或过期）的延伸；专门验证"子路径/域名模式部署"下前后端前缀是否一致。
> 关联规范：xianyu-hunter-dev `references/deployment-runtime-standards.md` 规范 S1；xianyu-frontend-code-review 维度 41；xianyu-backend-code-review 维度 41/42/43。
> **配置节点**（全部从 `config.yaml` 读取，禁止硬编码 `/xianyu/`）：
> - `spa.basename`：SPA 部署子路径，默认 `/xianyu`
> - `spa.api_prefix`：API 前缀，默认 `/xianyu/api`
> - `web_process.port` / `web_process.host`
> - `build.command` / `project.build_output_dir`

## 检查项

### AL1. 前端产物 base 与资源引用
读取 `config.yaml` 的 `spa.basename`，在 `build_output_dir/index.html` 与 `assets/*.js` 中核对：
- `index.html` 的资源引用是否基于 `basename`（非根 `/assets/...`）
- 打包 chunk 中 axios `baseURL` 是否等于 `basename`

```powershell
# 读取配置后替换 <basename>
Select-String -Path "<build_output_dir>/index.html" -Pattern '<script[^>]+src="<basename>assets/'
```

### AL2. PWA SW 是否覆盖前缀 API
读取 `spa.api_prefix`，在 `build_output_dir/sw.js` 中确认含 `api_prefix`（`navigateFallbackDenylist` 与 `runtimeCaching.urlPattern` 必须覆盖前缀 API）。

```powershell
Select-String -Path "<build_output_dir>/sw.js" -Pattern '<api_prefix 去首尾斜杠，如 xianyu/api>'
```

### AL3. 后端双挂载可达性
分别请求根 API 与 `api_prefix` 下的同一端点（无 token，预期均 401/403 而非 404）：

```powershell
# 根路径
Invoke-WebRequest -Uri "http://<host>:<port>/api/about" -Method GET -ErrorAction SilentlyContinue |
  Select-Object StatusCode
# 前缀路径
Invoke-WebRequest -Uri "http://<host>:<port><api_prefix>/about" -Method GET -ErrorAction SilentlyContinue |
  Select-Object StatusCode
```

### AL4. 鉴权归一化（带 token 对比）
用有效 token 分别请求根 `/api/...` 与 `api_prefix/...`，两者应同为 200（证明中间件做了前缀归一化）。

### AL5. 文档/导出等导航链接前缀
在 `build_output_dir/assets/*.js` 中 grep 裸 `/api/`（排除 axios 实例相对路径与 SW urlPattern）：
- 命中 → 该链接在子路径模式下会失效（P1）。

## 判断
- AL1/AL2 不符 → 构建产物未含前缀修复（DT-02 类，重新构建并核对产物内容）
- AL3 前缀路径 404 → 后端漏双挂载（维度 42）
- AL4 前缀路径 401 而根路径 200 → 鉴权未归一化（维度 41）
- AL5 命中裸 `/api/` → 前端链接未用 `API_BASE`（维度 41 前端）

## 命中后动作
- 构建问题：按 `build.command` 重建（**先输出到空临时目录再拷回，规避 safe-delete shim**），核对产物内容。
- 后端问题：补 `app.include_router(router, prefix="<spa.basename>")` 与直接 `app.get` 端点的前缀同名路由；重启进程。
- 鉴权问题：在 `auth.py` 增加前缀归一化（见维度 41 后端）。

## 输出报告
1. `basename` / `api_prefix` 配置值
2. 前端产物 base / sw.js 覆盖结论
3. 后端双挂载可达性（根 vs 前缀）
4. 鉴权归一化（带 token 根 vs 前缀）
5. 命中的规范维度与修复建议

## 不适用场景
- 纯根路径部署（`basename: '/'` 且 strip 模式）：仅 AL5 的"不要裸拼 host"仍适用
- 非 SPA / SSR 项目：路由与 SW 机制不同
- 纯后端单元测试（应改用 pytest）
