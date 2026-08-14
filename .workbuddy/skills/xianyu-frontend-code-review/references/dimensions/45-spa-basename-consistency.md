# 维度 45：SPA 基路径三处对齐 🆕v4.71.0 · F-REVIEW-239

> **编码规范引用**：xianyu-hunter-dev `references/coding-standards.md` §3.16.3 / meta-rule #118
> **配置节点**：config.yaml#checklist.spa_basename_consistency + config.yaml#spa_basename_consistency
> **测试关联**：xianyu-auto-testing 模式 AL（子路径部署一致性）

## 触发条件
- `frontend/vite.config.ts` 的 `base` 配置变更
- `frontend/src/main.tsx` 的 `<BrowserRouter basename>` 变更
- 后端 `web/app.py` 的 `_serve_spa_request` 剥离前缀逻辑变更
- 任何「自动打开浏览器」入口脚本（见 config.yaml#spa_basename_consistency.launch_entry_scripts）的 URL 变更

## 检查规则

### 强制（P0 阻塞）
- `vite.config.ts base` ⇄ `main.tsx <BrowserRouter basename>` ⇄ 后端 `_serve_spa_request` 剥离前缀三处必须一致（base 见 config.yaml#spa_basename_consistency.expected_base，如 `/xianyu/`）。
- 所有「自动打开浏览器」入口必须统一指向 `<base>`（或 `<base>/`），**禁止** `config.yaml#spa_basename_consistency.forbidden_entry_prefixes`（如 `/app/`、裸 `/`）。

### 推荐（P1 严重）
- 后端 `_serve_spa_request` 剥离前缀逻辑存在且与前端一致（config.yaml#spa_basename_consistency.backend_strip_prefix_check=true）。

### 推荐（P2 改进）
- 入口 URL 集中在启动脚本/配置，避免散落多处硬编码。

## Grep 扫描命令
```bash
# 检测 base 与 basename 是否一致
grep -n "base:" frontend/vite.config.ts
grep -n "basename" frontend/src/main.tsx

# 检测自动打开入口是否含禁止前缀
grep -rn "start.*http\|/app/\|http://{host}:{port}/" scripts/launcher.py scripts/启动服务.bat scripts/automation.ps1
```

## 判断标准
- `base` 与 `basename` 不一致 → P0 阻塞
- 入口含 `/app/` 或裸 `/` → P0 阻塞
- 后端剥离前缀逻辑缺失/不一致 → P1 严重

## 适用场景
- 子路径部署的 SPA（vite `base` 非 `/`）
- 含 `BrowserRouter basename` 的 React 项目

## 不适用场景
- 根路径部署 SPA（`base: '/'`）
- HashRouter / MemoryRouter（无 basename）
- 后端 `*.py` 路由/中间件（由 xianyu-backend-code-review 维度 41/42 负责）
