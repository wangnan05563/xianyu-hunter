# 注册式资源三件套契约（meta-rule #33）

> **元规范编号**：#33（v4.32.0 新增）
> **适用场景**：任何"用户可点击/可导航"的功能入口（菜单/侧边栏/按钮/Tab/Drawer/路由/Breadcrumb/通知订阅）
> **不适用**：纯静态页面、SSR（菜单由后端渲染）、单页 CLI、嵌入式设备

---

## 一、问题背景

### 1.1 经典症状

> 用户反馈：「通知中心菜单点击无反应」

**根因链条**：
1. `config/menu_registry.yaml` 已注册菜单 `path=/notifications`
2. 后端 `api_notifications.py` 已完整实现接口
3. 但前端 `App.tsx` **没有**注册 `notifications` 路由
4. 前端 `pages/Notifications/` **没有**对应页面组件
5. 路由 fallback `<Route path="*" element={<Navigate to="/" replace />} />` 静默重定向回首页
6. 用户体感：「明明菜单点了几次，URL 都不变」

### 1.2 同类模式 4 类

| 缺哪一层 | 现象 | 排查优先级 |
|---|---|---|
| 1. 菜单未注册 | 侧边栏看不到入口 | P0：检查 menu_registry.yaml / MainLayout menuItems |
| 2. 路由未注册 | 菜单可见，点击后 URL 不变或 404 | P0：检查 App.tsx 的 `<Route path>` |
| 3. 页面文件缺失 | 路由命中但页面空白/红屏 | P1：检查 pages/<域>/index.tsx 是否存在 |
| 4. API wrapper 缺失 | 页面加载但所有请求报错 | P1：检查 api/<域>.ts + api/index.ts re-export |
| 5. 后端 endpoint 缺失 | 前端 404 一直报 "Network Error" | P2：检查 FastAPI 路由 + main.py include_router |

> **关键观察**：上述 4 类都属于"用户能感知但开发者未必能立刻发现"的隐性缺陷。**自动化校验脚本是必选项**，不能依赖人脑逐项对照。

---

## 二、5 层契约模型

| 层 | 权威源 | 必备字段 | 校验方式 |
|---|---|---|---|
| **L1 菜单注册** | `config/menu_registry.yaml` | `path` (kebab-case) + `component` (PascalCase) + `label` (中文) + `i18n_key` | 读取 YAML，提取 path 列表 |
| **L2 路由注册** | `frontend/src/App.tsx` | `<Route path>` + `lazyRetry(() => import(...))` | grep `<Route path="<path>"` 命中 |
| **L3 页面文件** | `frontend/src/pages/<域>/index.tsx` | 必须 `export default` 一个组件 | `Glob pages/<域>/index.tsx` 存在 |
| **L4 API wrapper** | `frontend/src/api/<域>.ts` | 必须导出 `<域>Api` 对象，方法返回 `Promise<T>` | 解析 TS AST 找 `export const xxxApi` |
| **L5 后端 endpoint** | `src/xianyu_hunter/web/routes/api_<域>.py` | 必须 `APIRouter` + `@router.get/post` + `include_router` | grep `include_router` + `@router.<method>` |

---

## 三、自动化校验脚本（v4.32.0 新增）

### 3.1 脚本位置

`.trae/skills/xianyu-hunter-dev/scripts/check_registration.py`

### 3.2 行为约定

- **触发时机**：CI 流水线 + 提交前 hook + 任何"新增菜单/路由/页面"改动后
- **退出码**：所有路径通过 → 0；任一缺层 → 1（CRITICAL）
- **输出格式**：结构化表格 + JSON 双输出（CI 解析 JSON，开发者读表格）

### 3.3 校验逻辑（伪代码）

```python
# 读 menu_registry.yaml
menu_paths = parse_yaml('config/menu_registry.yaml')['items']  # 提取 path 列表

for path in menu_paths:
    layer1_ok = True  # 已在 L1
    # L2：App.tsx 路由
    layer2_ok = grep_in_file('frontend/src/App.tsx', f'<Route path="{path}"')
    # L3：page 文件存在
    domain = extract_domain_from_path(path)  # /notifications → Notifications
    layer3_ok = os.path.exists(f'frontend/src/pages/{domain}/index.tsx')
    # L4：api wrapper
    layer4_ok = os.path.exists(f'frontend/src/api/{domain.lower()}.ts')
    # L5：后端 endpoint（从 API 路径反推）
    layer5_ok = grep_in_repo('src/xianyu_hunter/web/routes/', f'@router\\..*"{path}"')

    if not (layer1_ok and layer2_ok and layer3_ok and layer4_ok and layer5_ok):
        print(f"❌ {path}: 缺层 L{...}")
        exit(1)
```

### 3.4 配置节点

```yaml
# config/tech-stack.json 或 xianyu-frontend-code-review/config.yaml
frontend_registration_completeness:
  enabled: true
  check_command: "python .trae/skills/xianyu-hunter-dev/scripts/check_registration.py"
  required_layers:
    - "menu_registry"   # L1
    - "router"          # L2
    - "page"            # L3
    - "api_wrapper"     # L4
    - "backend_endpoint" # L5
  fail_on_missing_layer: "CRITICAL"
  output_format: "table+json"
  ci_integration: true
  pre_commit_hook: true
  # 豁免清单：标记为 wip 的菜单可临时跳过（带过期时间）
  exemption_list:
    - path: "/experimental"
      reason: "WIP 实验性功能"
      expires: "2026-12-31"
```

---

## 四、判断信号（grep 优先）

| 信号 | 含义 | 违规判定 |
|---|---|---|
| `python scripts/check_registration.py` 退出码非 0 | 任意层缺失 | CRITICAL |
| `grep -E "path: ['\"]/(notifications\|orders\|users)['\"]" config/menu_registry.yaml` 命中但 App.tsx 无对应 Route | L1 有 L2 无 | CRITICAL |
| `Glob "frontend/src/pages/Notifications/index.tsx"` 失败但 App.tsx 有 `path="notifications"` 的 Route 引用 | L3 缺失 | CRITICAL |
| `Glob "frontend/src/api/notifications.ts"` 失败但页面 import 该模块 | L4 缺失 | CRITICAL |
| `grep -E "@router\\.(get\|post).*['\"\\/]notifications" src/xianyu_hunter/web/routes/` 失败 | L5 缺失 | CRITICAL |

---

## 五、不适用场景（边界）

| 场景 | 不适用原因 | 替代方案 |
|---|---|---|
| SSR（菜单由后端 Jinja 渲染） | L1 与 L2 物理上是同一文件 | 检查 `templates/<page>.html` 与 `routes.py` 对应 |
| 单文件 CLI 工具 | 无菜单/路由/页面概念 | 不立规范 |
| 嵌入式 HMI | 静态 UI 树，无 SPA 路由 | UI 树静态校验即可 |
| PWA 离线首页 | 单一 HTML 入口 | 单一页面校验，不分 L1-L5 |
| 草稿/实验性 feature | 故意只实现部分 | 用 `exemption_list` 豁免 + 必填 `expires` |

---

## 六、与 meta-rule #34 / #35 的关系

- **#33 注册式资源三件套契约**：聚焦"用户入口的纵向 5 层齐备性"
- **#34 修复前全链路根因扫描协议**：聚焦"修复 bug 时横向根因扫描"（参见 `root-cause-protocol.md`）
- **#35 前后端字段契约单一可信源**：聚焦"跨层数据格式的一致性"（参见 `contract-single-source.md`）

**三者是互补关系，不是替代关系**。一个完整的"修复菜单点击无反应"流程：
1. 先用 **#33** 校验 5 层齐备性，定位"缺哪一层"
2. 修复后用 **#34** 反查全链路是否还有类似缺口
3. 字段定义时用 **#35** 验证前后端字段名一致性

---

## 七、历史教训

| 时间 | 现象 | 根因 | 修复 |
|---|---|---|---|
| 2026-07-06 | 通知中心菜单点击无反应 | L2/L3/L4 缺失 | 新建 3 个文件 + App.tsx 注册路由 |
| 历史多次 | 某功能上线后用户报"找不到入口" | 仅修改了后端 API，忘了菜单注册 | 加 #33 元规范 + 自动化脚本 |

---

## 八、相关引用

- **元规范 #34**：修复前全链路根因扫描协议（`root-cause-protocol.md`）
- **元规范 #35**：前后端字段契约单一可信源（`contract-single-source.md`）
- **审查要点**：
  - 前端：`F-REVIEW-117 REGISTRATION-COMPLETENESS`（xianyu-frontend-code-review v4.36.0）
  - 后端：`B-REVIEW-159 REGISTRATION-API-EXISTS`（xianyu-backend-code-review v4.31.0）
- **技术栈版本**：参见 `config/tech-stack.json`
- **下钻模板**：参见 `assets/templates/typescript/api.ts`（API wrapper 模板）
