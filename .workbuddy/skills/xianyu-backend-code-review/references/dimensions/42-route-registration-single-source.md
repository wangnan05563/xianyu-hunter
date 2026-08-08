# 维度 42：路由注册单一数据源与双挂载一致性 🆕v4.70.0

> **编码规范引用**：xianyu-hunter-dev `references/deployment-runtime-standards.md` 规范 S2
> **配置节点**：config.yaml#coding_standards.subpath_deployment
> **测试关联**：xianyu-auto-testing 模式 AL

## 触发条件
- 新增/修改 `web/routes/api_*.py` 路由模块
- 在 `web/app.py` 的 `create_app()` 中调整 `include_router` 注册
- 调整"是否需在 `/xianyu` 前缀下暴露某 API"

## 检查规则

### 强制（P1 严重）
- 所有 API router 必须通过 `API_ROUTERS: list[tuple[module, attr]]` 表集中声明，**禁止**在 `create_app()` 里散落多段独立的 `app.include_router(...)`。
- 每个 router 必须**双挂载**：`app.include_router(router)`（根 `/api/*`）+ `app.include_router(router, prefix="/xianyu")`，保证 no-strip 代理下 `/xianyu/api/*` 也可达。
- 直接 `app.get(...)` 注册的特殊端点（如 `/api/docs`、`/api/about`）若需在子路径下可达，必须单独补 `/xianyu` 同名路由（它们不参与 `API_ROUTERS` 循环，最易被漏）。

### 推荐（P2 改进）
- `API_ROUTERS` 表注释标明每个模块导出的属性名（`router` / `_links_lookup` 等），便于审查是否漏挂载。

### 禁止
- 把已自带前缀逻辑的端点误放进 `API_ROUTERS` 循环导致重复挂载。

## Grep 扫描命令
```bash
# 检测散落的逐路由 include_router（应并入 API_ROUTERS 表）
grep -n "include_router" src/xianyu_hunter/web/app.py

# 检测是否双挂载（每个 router 出现两次）
grep -c "include_router(router" src/xianyu_hunter/web/app.py
```

## 判断标准
- 散落独立 `include_router` → P2 改进（应并入 `API_ROUTERS` 表）
- 新增路由只挂一种前缀 → P1 严重
- 特殊端点漏补 `/xianyu` 同名路由 → P1 严重

## 适用场景
- `web/app.py` 的 `create_app()`
- 任何 `web/routes/api_*.py`

## 不适用场景
- 中间件、异常处理、`API_ROUTERS` 循环外的特殊端点（仍适用 S1 第 5 步补前缀，但不进本维度"单一表"约束）
- 纯后端内部路由（不对外暴露 HTTP）
