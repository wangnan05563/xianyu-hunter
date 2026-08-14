# AL. 子路径部署一致性验证

> 对应决策节点：DT-01（web 未运行）/ DT-02（构建产物缺失或过期）的延伸；专门验证"子路径/域名模式部署"下前后端前缀是否一致。
> 关联规范：xianyu-hunter-dev `references/deployment-runtime-standards.md` 规范 S1、meta-rules #116~#119（2026-08-13 复盘 retrospective-2026-08-13）；xianyu-frontend-code-review 维度 41/42/43/44/45（F-REVIEW-236~239）；xianyu-backend-code-review 维度 41/42/43 + B-REVIEW-296。
> **配置节点**（全部从 `config.yaml` 读取，禁止硬编码 `/xianyu/`）：
> - `spa.basename`：SPA 部署子路径，默认 `/xianyu`
> - `spa.api_prefix`：API 前缀，默认 `/xianyu/api`
> - `spa.forbidden_entry_prefixes`：自动打开入口禁止前缀（`/app/`、裸 `/`）
> - `pwa.navigate_fallback_absolute_path` / `pwa.require_cleanup_outdated_caches` / `pwa.loading_splash_selector`：PWA 子路径导航回退绝对化参数
> - `design_tokens`：设计令牌集中化静态 grep 参数（scan_paths / hex_exclude_patterns / min_contrast_ratio / forbidden_decorative_hex）
> - `source_file_protection`：清理脚本禁删 tracked 源静态兜底参数（主责在 code-review）
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

### AL6. PWA 子路径导航回退绝对化（meta-rule #117 / F-REVIEW-237）
读取 `pwa.navigate_fallback_absolute_path` / `pwa.require_cleanup_outdated_caches` / `pwa.loading_splash_selector`，在 `build_output_dir/sw.js` 与 `frontend/vite.config.ts` 中核对：
- `base` 非 `/`（读 `spa.basename` 判断）时，`navigateFallback` 必须为**绝对路径**（`navigate_fallback_absolute_path`，如 `/xianyu/index.html`），**禁止**相对 `'index.html'`。注意 sw.js 构建后字段为 `createHandlerBoundToURL`，需正则子串提取比对，勿依赖精确引号匹配（易误判）。
- workbox 必须 `cleanupOutdatedCaches: true`（`require_cleanup_outdated_caches`）。
- `index.html` 的 `#root` 内必须有加载占位（选择器 `loading_splash_selector`），JS 挂载后替换，避免纯白白屏。

```powershell
# base 是否非根
Select-String -Path "frontend/vite.config.ts" -Pattern 'base:\s*[''"]/xianyu'
# navigateFallback 是否为相对路径（命中即 P0）
Select-String -Path "frontend/vite.config.ts" -Pattern "navigateFallback:\s*['\"]index\.html['\"]"
# 是否开启 cleanupOutdatedCaches
Select-String -Path "frontend/vite.config.ts" -Pattern "cleanupOutdatedCaches:\s*true"
# sw.js 绝对化回退（正则子串提取 createHandlerBoundToURL 的参数）
Select-String -Path "<build_output_dir>/sw.js" -Pattern "createHandlerBoundToURL\(['\"]<navigate_fallback_absolute_path 去引号>['\"]\)"
# index.html 加载占位
Select-String -Path "frontend/index.html" -Pattern "<div id=`"xh-loading-splash`"|loading-splash"
```

**判断**：`base` 非 `/` 且 `navigateFallback` 相对 → **P0**；缺 `cleanupOutdatedCaches` → **P0**；无加载占位 → **P1**。

### AL7. SPA 基路径三处对齐（meta-rule #118 / F-REVIEW-239）
读取 `spa.basename`，核对三处一致性：
- `frontend/vite.config.ts` 的 `base` ⇄ `frontend/src/main.tsx` 的 `<BrowserRouter basename>` ⇄ 后端 `web/app.py` 的 `_serve_spa_request` 剥离前缀，三者必须一致（均等于 `basename`）。
- 所有「自动打开浏览器」入口（`scripts/启动服务.bat` / `scripts/launcher.py` / `scripts/automation.ps1`）必须统一指向 `basename`（或 `basename/`），**禁止** `spa.forbidden_entry_prefixes`（如 `/app/`、裸 `/`）。

```powershell
# base 与 basename 是否一致
Select-String -Path "frontend/vite.config.ts" -Pattern 'base:\s*[''"]<basename>'
Select-String -Path "frontend/src/main.tsx" -Pattern "basename="  # 应等于 <basename>
# 自动打开入口是否含禁止前缀
Select-String -Path "scripts/启动服务.bat","scripts/launcher.py","scripts/automation.ps1" -Pattern "/app/|http://\{host\}:\{port\}/`""
```

**判断**：`base` 与 `basename` 不一致 → **P0**；入口含 `/app/` 或裸 `/` → **P0**；后端剥离前缀缺失/不一致 → **P1**。

### AL8. 设计令牌集中化（禁硬编码色，meta-rule #119 / F-REVIEW-238）
读取 `design_tokens`（scan_paths / hex_exclude_patterns / min_contrast_ratio / forbidden_decorative_hex），在组件/页面内联 `style` 中 grep 硬编码十六进制色：
- 内联 `style` 含硬编码十六进制色（排除 `hex_exclude_patterns` 的 token 定义文件与 svg）→ **P0**。
- 命中 `forbidden_decorative_hex`（马卡龙系装饰色）→ **P1**。

```powershell
# 组件内联 style 硬编码十六进制色（排除 token 定义文件与 svg）
Select-String -Path "<design_tokens.scan_paths 展开>/*.tsx" -Pattern '#[0-9a-fA-F]{6}' |
  Where-Object { $_ -notmatch 'theme\.ts|tokens\.css|\.svg' }
# 残留装饰色
Select-String -Path "frontend/src" -Pattern '#(FFB3CC|FF8FAB|6ECDB4|A8E6CF|FFD6E8|E8D5F2)' -CaseSensitive:$false
```

**判断**：内联 style 硬编码十六进制色 → **P0**；装饰色未移除 → **P1**。

### AL9. 源码受保护静态兜底（meta-rule #116 / F-REVIEW-236 / B-REVIEW-296）
读取 `source_file_protection`（protected_patterns / allowed_cleanup_targets / require_git_status_guard），对清理脚本做静态兜底 grep（主责在 code-review 技能，此处仅兜底提示）：
- 清理脚本删除命令匹配 `protected_patterns`（`src/`、`*.py`、`*.css`、`*.ts(x)`）→ 提示转 code-review（**P0**）。
- 清理脚本无 `git status` 守卫 / 无白名单排除 `src/` → 提示（**P1**）。

```powershell
# 清理脚本删除命令是否匹配受保护源
Select-String -Path "scripts/*.bat","scripts/*.ps1","scripts/*.py" -Pattern 'rm -rf|Remove-Item|del ' |
  Where-Object { $_ -match 'src/|scripts/|\*\.py|\*\.css|\*\.tsx' }
# 是否有 git status 守卫
Select-String -Path "scripts/*.bat","scripts/*.ps1" -Pattern 'git status'
```

**判断**：命中受保护源删除 → **P0**（转 code-review）；无守卫 → **P1**（转 code-review）。

## 判断
- AL1/AL2 不符 → 构建产物未含前缀修复（DT-02 类，重新构建并核对产物内容）
- AL6 `navigateFallback` 相对 / 缺 `cleanupOutdatedCaches` → PWA 子路径白屏根因（重新构建并核对 sw.js 绝对化回退）
- AL7 `base`/`basename`/后端前缀不一致 或 入口含 `/app/` → SPA 整页白板根因（三处统一 `basename`，清理禁止前缀）
- AL8 硬编码色 / 装饰色 → 视觉不一致（转 design tokens 集中化）
- AL9 清理脚本误伤源 → 转 code-review 维度 42 / B-REVIEW-296
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
6. PWA 子路径导航回退绝对化（navigateFallback 绝对路径 / cleanupOutdatedCaches / 加载占位）
7. SPA 基路径三处对齐（base ⇄ basename ⇄ 后端前缀；入口禁止前缀）
8. 设计令牌集中化（硬编码色 / 装饰色 grep 结论）
9. 源码受保护静态兜底（清理脚本误伤源 grep 结论，主责转 code-review）

## 不适用场景
- 纯根路径部署（`basename: '/'` 且 strip 模式）：仅 AL5 的"不要裸拼 host"仍适用
- 非 SPA / SSR 项目：路由与 SW 机制不同
- 纯后端单元测试（应改用 pytest）
