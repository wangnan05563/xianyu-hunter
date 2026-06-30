# Sprint About-Menu 交付报告：「关于」菜单 - 元信息 + 文档资源统一入口

> 报告日期：2026-06-28
> 关联需求：[about-menu-requirements.md](about-menu-requirements.md)
> 关联设计：[about-menu-design.md](about-menu-design.md)
> 实施计划：[plans/about-menu-implementation-plan.md](plans/about-menu-implementation-plan.md)

---

## 摘要

| 项 | 类型 | 优先级 | 状态 | 测试 | 影响 |
|---|---|---|---|---|---|
| About 菜单 | 新增功能 | P1 | ✅ | 前端 29 + 后端 16 + 回归 2 | 元信息 + 文档资源统一入口；整合原分散的 API 文档与帮助文档跳转 |

**总计**：1 项 / 新增 14 文件 / 修改 5 文件 / 0 新依赖

**背景**：
原系统 API 文档入口分散在 Swagger UI 顶栏与 MainLayout 顶栏；用户协议、隐私条款、开源声明等元信息无处归属。本次新增 `/about` 独立路由作为元信息 + 文档资源统一入口，整合原分散的「📖 帮助文档」按钮，并展示版本号、构建日期、Git SHA、检查更新状态机。

---

## §1 后端（P0）

### 改动点

**1. `src/xianyu_hunter/web/routes/api_about.py`（新建）**
- 2 个端点：`GET /api/about` + `GET /api/about/check-update`
- `_safe_build_info()` 使用 `try/except + getattr` 三层兜底，缺字段返回 `"unknown"`，绝不返回 5xx
- `check-update` 首版固定 `has_update=False`，不发起外网请求（无 SSRF 风险）
- `include_in_schema=False`：从 OpenAPI schema 隐藏，减少 `/openapi.json` 噪声

**2. `src/xianyu_hunter/web/app.py`（修改）**
- 在 `api_auth` 之后 `include_router(api_about.router)`
- Swagger UI 顶栏按钮：`href="/app/help"` → `href="/app/about"`，文案「📖 帮助文档」→「📖 关于」

**3. `src/xianyu_hunter/web/middleware/auth.py`（修改）**
- `PUBLIC_PREFIXES` 元组追加 `"/api/about"` 单条
- 为什么单条够用：`PUBLIC_PREFIXES` 用 `startswith` 前缀匹配，`/api/about` 同时覆盖 `/api/about` 与 `/api/about/check-update` 两个端点

**4. `scripts/build_info.py`（新建）**
- 构建时生成 `_build_info.py`，写入 `__version__` / `build_date` / `git_sha`
- `_git_sha()` 用 `subprocess.check_output(["git", "rev-parse", "--short", "HEAD"])`，timeout=3s
- git 不可用时返回 `"unknown"`，不中断构建

**5. `scripts/重新构建.bat`（修改）**
- 在 `npm run build` 之后追加 `python scripts\build_info.py`（步骤 [3/3]）

**6. `src/xianyu_hunter/_build_info.py`（构建时自动生成）**
- 当前内容：`__version__ = "0.1.0"` / `build_date = "2026-06-28"` / `git_sha = "eb97c096"`

---

## §2 前端（P1）

### 改动点

**1. `frontend/src/api/about.ts`（新建）**
- `AboutInfo` + `UpdateCheckResult` 类型与后端契约对齐
- `aboutApi.get()` / `aboutApi.checkUpdate()` 两个方法

**2. `frontend/src/api/index.ts`（修改）**
- 追加 `export { aboutApi } from './about'` 与类型导出

**3. `frontend/src/pages/About/i18n.ts`（新建）**
- 集中所有 UI 文案为 `TEXTS` 常量，未来接入 i18n 框架无需改组件

**4. `frontend/src/pages/About/useUpdateChecker.ts`（新建）**
- 状态机：`idle → loading → (latest | newer | error)`
- `latest` 态 3s 后自动回 `idle`（让用户看到「已是最新」反馈后恢复初始态）
- `isNetworkError()` 通过 `!err.response || err.code === 'ERR_NETWORK'` 区分网络/服务端错误
- `copy()` 用 `navigator.clipboard.writeText`，权限被拒时降级 toast 提示

**5. `frontend/src/pages/About/BrandCard.tsx`（新建）**
- Logo（48px 渐变 `#FF6200→#FF8533`，与 Swagger UI 顶栏品牌块一致）+ 版本号 + 复制按钮 + 构建日期 + Git SHA + 更新按钮
- `UpdateButton` 子组件按 5 态渲染：`idle` / `loading` / `latest` / `newer` / `error`
- `showSha = gitSha && gitSha !== 'unknown'`：未知 SHA 不展示，避免误导

**6. `frontend/src/pages/About/AboutMenuList.tsx`（新建）**
- 8 个菜单项：用户协议 / 隐私条款 / 开源声明（Modal）/ 帮助文档（SPA Link）/ API 文档 / 联系我们 / 官方社区 / 报告问题
- `help` 用 `<Link>` SPA 内链（避免整页刷新）；其余用 `<a target="_blank" rel="noopener noreferrer">`
- `licenses` 点击 `preventDefault` 后触发 `onOpenLicenses` 回调

**7. `frontend/src/pages/About/OpenSourceLicenses.tsx`（新建）**
- 静态依赖清单：21 个前端依赖（来自 `package.json`）+ 20 个后端依赖（来自 `requirements.txt`）
- 按名称字母序排序，支持名称/许可证双向搜索
- Modal `destroyOnClose`，最大高度 60vh 滚动，footer「以运行时实际安装为准」

**8. `frontend/src/pages/About/about.css`（新建）**
- `.xh-about-content` max-width 720px，padding 32px 24px 64px
- 移动端 media query：padding 16px，h1 font-size 32px

**9. `frontend/src/pages/About/index.tsx`（新建）**
- 页面壳：Header（sticky 56px）+ Content + Footer
- `FALLBACK: BuildInfo = { version: '--', buildDate: '--', gitSha: 'unknown' }`：API 失败兜底
- H1 用 Cormorant Garamond + Noto Serif SC 字体，40px，letterSpacing -0.5px

**10. `frontend/src/App.tsx`（修改）**
- `const About = lazyRetry(() => import('./pages/About'))`
- `<Route path="/about" element={<LazyRoute><About /></LazyRoute>} />` 独立路由（不嵌套 MainLayout，与 `/help` 同级）

**11. `frontend/src/components/layout/MainLayout.tsx`（修改，6 处）**
1. `@ant-design/icons` 导入追加 `InfoCircleOutlined`
2. `menuItems` 末尾追加 divider + `/about` 项（侧栏底部独立分组）
3. `ROUTE_LABELS` 追加 `'/about': '关于'`（面包屑映射）
4. `COMMAND_ITEMS` 追加 `{ key: '/about', label: '关于', icon: <InfoCircleOutlined /> }`（Ctrl+K 命令面板可搜）
5. `G_PREFIX_MAP` 追加 `a: '/about'`（g+a 快捷键导航）
6. Header 帮助按钮后追加关于按钮（圆形 InfoCircleOutlined 图标）

---

## §3 测试（P2）

### 前端单元测试（Vitest + jsdom）

**4 个测试文件，29 个测试全部通过**：

| 文件 | 测试数 | 覆盖点 |
|---|---|---|
| `__tests__/useUpdateChecker.test.tsx` | 7 | 状态机 5 态转换 + 3s 自动回 idle + copy 成功/失败 |
| `__tests__/BrandCard.test.tsx` | 10 | 5 态按钮渲染 + 版本号 + 构建日期 + gitSha 显示控制 + 复制按钮 |
| `__tests__/AboutMenuList.test.tsx` | 5 | 8 项渲染 + licenses 点击 + 外链 target/rel + help 内链 + api href |
| `__tests__/OpenSourceLicenses.test.tsx` | 7 | open 控制 + 标题 + 全部列表 + 关键字过滤 + 许可证过滤 + 空状态 + 清空恢复 |

**关键技术决策**：
- jsdom 未实现 `window.matchMedia`，antd Modal 内部 ResponsiveObserver 依赖它，在 OpenSourceLicenses 测试文件级别补最小可用 mock
- `useUpdateChecker` 测试用 `AntdApp + ConfigProvider` 包装，提供 `App.useApp()` 上下文
- `vi.useFakeTimers()` 控制 `latest → idle` 的 3s 自动回退

### 后端单元测试（pytest + TestClient）

**1 个测试文件，16 个测试全部通过**（`tests/test_about.py`）：

| 测试组 | 测试数 | 覆盖点 |
|---|---|---|
| 路由注册 | 2 | 两个端点注册到 `app.routes` + router prefix 正确 |
| 认证白名单 | 2 | `PUBLIC_PREFIXES` 包含 `/api/about` + 无 token 请求 200 |
| `/api/about` 字段契约 | 4 | 6 字段齐全 + product 固定 + python 格式 + platform 小写 |
| `_build_info` 兜底 | 3 | 缺失时 unknown + 存在时正确读取 + 部分缺失逐字段兜底 |
| `/api/about/check-update` 契约 | 5 | 6 字段齐全 + has_update=False + source=local + release_url 非空 + checked_at ISO 格式 |

**关键技术决策**：
- `from xianyu_hunter import _build_info` 走包属性查找路径，测试中需同时 patch `sys.modules` 和 `xianyu_hunter.__dict__['_build_info']`
- 用 `monkeypatch.setitem(sys.modules, "xianyu_hunter._build_info", None)` 模拟 ImportError
- `client` fixture 用 `monkeypatch` 注入测试 token，避免读取真实 `.env`

### 回归测试

| 文件 | 测试数 | 状态 |
|---|---|---|
| `tests/test_web_route_registration.py` | 2 | ✅ 通过 |

### 构建 / 编译验证

| 验证项 | 结果 |
|---|---|
| `npx tsc --noEmit` | About 相关代码全部通过；1 个预先存在的 `BatchRefresh.tsx:285` 错误与本次无关 |
| `npx vite build` | ✅ 成功，4105 模块 47.63s，PWA 产物正常生成 |
| `npx vitest run`（全量） | 36/38 通过；2 失败为预先存在的 `storage.test.ts` localStorage 模拟问题 |

---

## §4 验收对照（与需求 §11）

| 需求 | 任务 | 状态 |
|---|---|---|
| A1 顶栏 ℹ️ 按钮 | Task 12.6 | ✅ |
| A2 跳转 /about | Task 11 | ✅ |
| A3 品牌卡 | Task 7 | ✅ |
| A4 复制按钮 | Task 6 + Task 7 | ✅ |
| A5 检查更新三态 | Task 6 + Task 7 | ✅（实际 5 态：idle/loading/latest/newer/error） |
| A6 外部链接 | Task 8 | ✅（8 项） |
| A7 侧栏底部 | Task 12.2 | ✅ |
| A8 Command Palette | Task 12.4 | ✅ |
| A9 g+a 快捷键 | Task 12.5 | ✅ |
| A10 Swagger 跳转 | Task 3 | ✅ |
| A11 Help 页保留 | Task 12.6 | ✅（原 ❓ 按钮保留，仍跳 /help） |
| A12 开源声明 | Task 9 | ✅（21 前端 + 20 后端 = 41 项） |
| A13 暗 / 亮主题 | Task 7 + Task 10 | ✅（全部走 `theme.useToken()` token） |
| B 兼容 | Task 10 | ✅（about.css 移动端 media query） |
| C 性能 | - | ✅（懒加载 + 独立 chunk，构建产物约 14KB） |
| D 质量 | Task 13 + Task 14 | ✅（45 测试通过） |
| E 文档 | 本文件 | ✅ |

---

## §5 已知限制与后续迭代

1. **开源声明为静态常量**：当前从 `package.json` + `requirements.txt` 手工摘录 41 项直接依赖；P2 可接入 `license-checker` 自动生成完整传递依赖清单
2. **check-update 首版固定 `has_update=False`**：不发起外网请求，UI 始终显示「已是最新」；P2 可改为调用 GitHub Releases API（注意 SSRF 防护）
3. **8 个菜单项的 href 为占位 URL**（`https://example.com/terms` 等）：上线前需替换为实际法务/社区/工单地址
4. **`_build_info.py` 仅在执行 `重新构建.bat` 时刷新**：开发环境手动 `python -m xianyu_hunter web` 启动时会读到上一次构建的元信息，开发态可接受

---

## §6 文件清单

### 新建（14 文件）

| 路径 | 用途 |
|---|---|
| `src/xianyu_hunter/_build_info.py` | 构建时生成的版本元信息 |
| `src/xianyu_hunter/web/routes/api_about.py` | About API 路由 |
| `scripts/build_info.py` | 构建脚本 |
| `frontend/src/api/about.ts` | axios 客户端封装 |
| `frontend/src/pages/About/i18n.ts` | 文案常量 |
| `frontend/src/pages/About/useUpdateChecker.ts` | 检查更新 hook |
| `frontend/src/pages/About/BrandCard.tsx` | 品牌卡组件 |
| `frontend/src/pages/About/AboutMenuList.tsx` | 外部链接列表 |
| `frontend/src/pages/About/OpenSourceLicenses.tsx` | 开源声明 Modal |
| `frontend/src/pages/About/about.css` | 局部样式 |
| `frontend/src/pages/About/index.tsx` | 页面壳 |
| `frontend/src/pages/About/__tests__/useUpdateChecker.test.tsx` | Hook 测试 |
| `frontend/src/pages/About/__tests__/BrandCard.test.tsx` | 品牌卡测试 |
| `frontend/src/pages/About/__tests__/AboutMenuList.test.tsx` | 菜单列表测试 |
| `frontend/src/pages/About/__tests__/OpenSourceLicenses.test.tsx` | 开源声明测试 |
| `tests/test_about.py` | 后端测试 |
| `docs/sprint-about-menu-2026-06-28.md` | 本交付记录 |

### 修改（5 文件）

| 路径 | 改动点 |
|---|---|
| `src/xianyu_hunter/web/app.py` | `include_router` + Swagger UI 跳转改 `/app/about` |
| `src/xianyu_hunter/web/middleware/auth.py` | `PUBLIC_PREFIXES` 追加 `/api/about` |
| `scripts/重新构建.bat` | 追加 `python scripts\build_info.py` 步骤 |
| `frontend/src/api/index.ts` | 导出 `aboutApi` |
| `frontend/src/App.tsx` | About 懒加载 + `/about` 路由 |
| `frontend/src/components/layout/MainLayout.tsx` | 6 处微调（导入/menuItems/ROUTE_LABELS/COMMAND_ITEMS/G_PREFIX_MAP/Header 按钮） |
