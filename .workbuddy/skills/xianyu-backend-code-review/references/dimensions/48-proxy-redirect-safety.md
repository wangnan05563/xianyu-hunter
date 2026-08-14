# 维度 48：重定向/中间件不得破坏反代（Funnel 回环安全）🆕v4.71.0 · B-REVIEW-341

> **编码规范引用**：xianyu-hunter-dev `references/coding-standards-2026-08-13.md` §11.2 / meta-rule #120
> **配置节点**：config.yaml#proxy_redirect_safety（新增）
> **测试关联**：xianyu-auto-testing 模式 AL（子路径部署一致性）；xianyu-frontend-code-review 维度 48（前端侧交叉）
> **复盘来源**：retrospective-2026-08-13-login-cookie.md（案例 G/H + 流程 P1 + 规范 #120）

## 触发条件
- 新增/修改全局重定向（如 `/` → `/xianyu/`）、入口重写、中间件改写 `Location`
- 后端 `web/app.py` 的 SPA 路由（`spa_root` / `spa_index`）逻辑变更
- 涉及反向代理（Funnel/proxy）剥离前缀的部署路径变更

## 检查规则

### 强制（P0 阻塞）
- 新增全局重定向/中间件前，必须先 grep `Funnel`/`proxy`/`redirect`/`loop` 与路由注释，确认不会造成前缀剥离回环。
- 在经反向代理剥离前缀的部署（如 Funnel）下，**禁止** `/` → `/xianyu/` 类重定向：剥离后回到 `/` 再重定向 = 无限循环。
- 修复「根路径白板」靠「统一入口指向子路径」，而非加重定向。

### 推荐（P1 严重）
- 反代/前缀剥离相关约束写成代码注释或配置开关（`config.yaml#proxy_redirect_safety.strip_prefix_deployment`），审查时显式核对。

### 推荐（P2 改进）
- 重定向逻辑与 SPA `basename` 对齐（与维度 45/46 联动），避免前端入口失配。

## Grep 扫描命令
```bash
# 检测可能破坏反代的重定向
grep -rn "redirect\|307\|RedirectResponse" src/xianyu_hunter/web/app.py

# 检测反代/前缀剥离约束注释
grep -rn "Funnel\|strip\|prefix" src/xianyu_hunter/web/app.py
```

## 判断标准
- 重定向目标会被反代再次剥离 → P0 阻塞（无限回环风险）
- 无反代剥离约束却新增根路径重定向 → P1 严重（需先确认部署形态）

## 适用场景
- 子路径部署 SPA
- 经 Funnel/proxy 反向代理剥离前缀的部署
- 新增全局重定向/中间件/入口重写

## 不适用场景
- 纯后端 JSON API（无 SPA 入口）
- 明确无前缀剥离的单层部署（仍建议先 grep 约束）
