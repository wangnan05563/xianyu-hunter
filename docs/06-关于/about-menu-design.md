# 闲鱼猎人 · "关于" 菜单概要设计

> 项目代号：**XianyuHunter**
> 文档版本：v1.0
> 编写日期：2026-06-28
> 阶段：概要设计（v1.0）✅ 已完成
> 关联文档：
> - [about-menu-requirements.md](./about-menu-requirements.md) — 需求规格
> - [michelin-design-system.md](./michelin-design-system.md) — 视觉规范
> - [directory-structure.md](./directory-structure.md) — 目录规范

---

## 0. 阶段交接声明

```
- 当前阶段：概要设计（v1.0）✅ 已完成
- 下一阶段：实施计划 + 任务拆分
- 下一阶段智能体：general_purpose_task
- 下一阶段技能：subagent-driven-development
- 交接上下文：
  · 需求规格 §13.1 列出 15 个关键文件，本设计落 7 个新建 + 5 处微调；
  · 实施 P0 = 后端 API + _build_info.py + Swagger 顶栏跳转；
  · 实施 P1 = 前端 6 个文件 + 路由 + 集成；
  · 实施 P2 = 测试 + 验收 + 文档；
  · 关键风险见需求 §10.1（SSRF）和 §10.2（_build_info 缺字段）；
  · 严格沿用 michelin-design-system.md CSS Token，禁止引入新 UI 库。
```

---

## 1. 设计目标

将"关于"菜单作为 XianyuHunter 元信息 + 文档资源的统一入口，**最小变更地整合**现有 3 个分散入口（顶栏 ❓、MainLayout 文字链、Swagger UI 顶栏）。

核心原则：
- **最小入侵**：现有 11 个页面 0 改动；MainLayout 仅 5 处微调；Help 路由保留。
- **风格统一**：所有 token 沿用 `michelin-design-system.md`，亮 / 暗双主题自动适配。
- **零外网依赖**：首版"检查更新"仅返回本机版本，UI 提示文案与未来外网通道解耦。

---

## 2. 信息架构

### 2.1 "关于" 页信息树

```
/about
├── H1: 关于 闲鱼猎人
├── BrandCard（品牌卡）
│   ├── Logo（占位字符"闲"或项目 SVG）
│   ├── 标题行：版本号 + 复制按钮
│   ├── 副标题：发布日期 + Git SHA
│   └── 操作行：[检查更新] 按钮
└── AboutMenuList（外部链接列表）
    ├── 用户协议        → https://example.com/terms
    ├── 隐私条款        → https://example.com/privacy
    ├── 开源软件声明    → OpenSourceLicenses Modal
    ├── 帮助文档        → /help（SPA 内链）
    ├── API 文档        → /api/docs（新窗口）
    ├── 联系我们        → mailto:dev@example.com
    ├── 官方社区        → https://example.com/community
    └── 报告问题        → https://example.com/issues/new
└── Footer
    ├── 版权：闲鱼猎人 · 2026
    └── 风险免责 Tooltip
```

### 2.2 状态机：检查更新按钮

```
            ┌──── idle ────┐
            │  "检查更新"  │
            └──────┬───────┘
                   │ click
                   ▼
            ┌──── loading ───┐
            │  "检查中..."   │
            └──────┬─────────┘
                   │ API resp
       ┌───────────┼───────────┬─────────────┐
       ▼           ▼           ▼             ▼
   latest=current  has_update  network_err  server_err
       │           │           │             │
       ▼           ▼           ▼             ▼
    "已是最新"   "有新版本"   "网络异常"   "服务异常"
    绿色 ✓       蓝色 ↑       红色 !       红色 !
    3s 后回 idle  → 链接     → 重试按钮   → 重试按钮
```

### 2.3 数据来源

| 字段 | 来源 | 写入时机 |
|---|---|---|
| `__version__` | `src/xianyu_hunter/__init__.py` | 手动维护（已存在 `0.1.0`） |
| `build_date` | `scripts/build_info.py` 写入 `_build_info.py` | `重新构建.bat` 末尾 |
| `git_sha` | 同上，`git rev-parse --short HEAD` | 同上 |
| `python` | `sys.version` | 运行时 |
| `platform` | `platform.system()` | 运行时 |

---

## 3. 路由与文件结构

### 3.1 路由变更

| 文件 | 行 | 改动 |
|---|---|---|
| `frontend/src/App.tsx` | 33-34 后 | 新增 `const About = lazyRetry(() => import('./pages/About'))` |
| `frontend/src/App.tsx` | 66-67 后 | 新增 `<Route path="/about" element={<LazyRoute><About /></LazyRoute>} />`（独立路由，不嵌 MainLayout） |

### 3.2 文件清单

#### 3.2.1 新建文件（7 个）

| 路径 | 用途 | 预估行数 |
|---|---|---|
| `frontend/src/pages/About/index.tsx` | 页面壳，组合 BrandCard + AboutMenuList + Footer | 80 |
| `frontend/src/pages/About/BrandCard.tsx` | 品牌卡组件 | 110 |
| `frontend/src/pages/About/AboutMenuList.tsx` | 外部链接列表 | 60 |
| `frontend/src/pages/About/OpenSourceLicenses.tsx` | 开源声明 Modal | 90 |
| `frontend/src/pages/About/useUpdateChecker.ts` | 检查更新 hook（封装 axios + 状态机） | 80 |
| `frontend/src/pages/About/i18n.ts` | 文案常量集中 | 30 |
| `frontend/src/pages/About/about.css` | 局部样式（仅 custom 部分，token 已全用 var） | 50 |
| `frontend/src/api/about.ts` | axios 客户端封装 | 25 |
| `src/xianyu_hunter/web/routes/api_about.py` | FastAPI 路由 | 70 |
| `src/xianyu_hunter/_build_info.py` | 构建时生成（`scripts/build_info.py` 写入） | 10 |
| `scripts/build_info.py` | 构建脚本 | 40 |
| `frontend/src/pages/About/__tests__/index.test.tsx` | 前端测试 | 80 |
| `tests/test_about.py` | 后端测试 | 60 |

#### 3.2.2 修改文件（5 个）

| 路径 | 改动 |
|---|---|
| `frontend/src/components/layout/MainLayout.tsx` | 5 处（见 §6.1） |
| `frontend/src/api/index.ts` | `export { aboutApi } from './about'` |
| `src/xianyu_hunter/web/app.py` | 1 行 `app.include_router(api_about.router)` + Swagger UI 顶栏改 1 处链接 |
| `src/xianyu_hunter/web/middleware/auth.py` | `WHITELIST` 增 2 项 |
| `scripts/重新构建.bat` | 末尾追加 1 行 `python scripts/build_info.py` |

---

## 4. 前端设计

### 4.1 组件树

```
<About>                                    // pages/About/index.tsx
├── <ConfigProvider>                       // 复用 ThemeContext
│   ├── <Layout style={{ minHeight: '100vh' }}>
│   │   ├── <Header>                       // 自有顶栏，与 Help 风格一致
│   │   │   ├── <Button> ← 返回控制台
│   │   │   └── <Title> 关于
│   │   └── <Content>
│   │       ├── <h1> 关于 闲鱼猎人         // display-2
│   │       ├── <BrandCard />              // 品牌卡
│   │       │   ├── <Logo />               // 32px 圆角红块 + "闲"字
│   │       │   ├── <VersionLine>
│   │       │   │   ├── 版本：0.1.0
│   │       │   │   └── <Button> 📋 复制
│   │       │   ├── <SubLine> 发布于 2026-06-28 · @abc1234
│   │       │   └── <UpdateButton />       // 三态
│   │       ├── <AboutMenuList />          // 8 行
│   │       │   └── 8 × <ListItem>
│   │       │       ├── <Text> 用户协议
│   │       │       └── <Icon> ↗
│   │       ├── <OpenSourceLicenses />     // 独立 Modal
│   │       │   ├── <Modal>
│   │       │   │   ├── <Input> 搜索
│   │       │   │   └── <List> 80+ 条
│   │       └── <Footer>
│   │           ├── 闲鱼猎人 · 2026
│   │           └── <Tooltip> 风险免责
```

### 4.2 BrandCard 关键代码骨架

```tsx
// frontend/src/pages/About/BrandCard.tsx
import { useState } from 'react'
import { Card, Button, Tooltip, message, theme } from 'antd'
import { CopyOutlined, ReloadOutlined, CheckCircleFilled, ArrowUpOutlined, WarningFilled } from '@ant-design/icons'
import { useUpdateChecker } from './useUpdateChecker'
import { TEXTS } from './i18n'

export function BrandCard() {
  const { token } = theme.useToken()
  const { version, buildDate, gitSha } = useBuildInfo()
  const { state, run, copy } = useUpdateChecker(version)

  return (
    <Card
      style={{
        background: token.colorBgContainer,
        border: `1px solid ${token.colorBorderSecondary}`,
        borderRadius: 6,
        marginBottom: 24,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        {/* Logo 占位：32px 圆角红块（沿用品牌色，与 Swagger UI 顶栏一致） */}
        <div
          style={{
            width: 48, height: 48, borderRadius: 6,
            background: 'linear-gradient(135deg, #FF6200, #FF8533)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: '#fff', fontSize: 22, fontWeight: 700,
          }}
        >闲</div>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 20, fontWeight: 600 }}>{TEXTS.versionLabel}: {version}</span>
            <Tooltip title={TEXTS.copyHint}>
              <Button
                type="text"
                size="small"
                icon={<CopyOutlined />}
                onClick={copy}
                aria-label={TEXTS.copyAriaLabel}
              />
            </Tooltip>
          </div>
          <div style={{ fontSize: 13, color: token.colorTextSecondary, marginTop: 4 }}>
            {TEXTS.releasedOn} {buildDate}{gitSha !== 'unknown' && ` · @${gitSha}`}
          </div>
        </div>
        <UpdateButton state={state} onClick={run} />
      </div>
    </Card>
  )
}

// UpdateButton 子组件：三态渲染
function UpdateButton({ state, onClick }: { state: UpdateState; onClick: () => void }) {
  // 状态机见 §2.2
  // - idle:    <Button type="primary" icon={<ReloadOutlined />}>检查更新</Button>
  // - loading: <Button loading>检查中…</Button>
  // - latest:  <Button type="text" icon={<CheckCircleFilled style={{ color: '#52c41a' }} />}>已是最新</Button>
  // - newer:   <Button type="primary" icon={<ArrowUpOutlined />} onClick={openReleaseUrl}>有新版本</Button>
  // - error:   <Button type="text" danger icon={<WarningFilled />}>重试</Button>
}
```

### 4.3 useUpdateChecker hook 骨架

```tsx
// frontend/src/pages/About/useUpdateChecker.ts
type UpdateState =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'latest' }
  | { kind: 'newer'; url: string; latest: string }
  | { kind: 'error'; reason: 'network' | 'server' }

export function useUpdateChecker(current: string) {
  const [state, setState] = useState<UpdateState>({ kind: 'idle' })
  const { message } = App.useApp()

  const run = useCallback(async () => {
    setState({ kind: 'loading' })
    try {
      const res = await aboutApi.checkUpdate()
      if (res.latest === res.current) {
        setState({ kind: 'latest' })
        setTimeout(() => setState({ kind: 'idle' }), 3000)
      } else {
        setState({ kind: 'newer', url: res.release_url, latest: res.latest })
      }
    } catch (e) {
      const reason = isNetworkError(e) ? 'network' : 'server'
      setState({ kind: 'error', reason })
    }
  }, [current])

  const copy = useCallback(async () => {
    await navigator.clipboard.writeText(current)
    message.success(TEXTS.copied)
  }, [current, message])

  return { state, run, copy }
}
```

### 4.4 样式规范（about.css）

**原则**：仅定义 `michelin-design-system.md` 未覆盖的局部样式（如 Logo 渐变背景），其余全部使用 antd `theme.useToken()` 消费 token。

```css
/* frontend/src/pages/About/about.css */
.xh-about-page {
  /* 全局：max-width 720px 居中，与 Help 一致 */
  --xh-about-max-width: 720px;
  --xh-about-padding: 32px 24px 64px;
}

.xh-about-logo {
  /* Logo 渐变：与 Swagger UI 顶栏 logo 完全一致（品牌识别统一） */
  background: linear-gradient(135deg, #FF6200, #FF8533);
  box-shadow: 0 2px 8px rgba(255, 98, 0, 0.25);
}

.xh-about-menu-item {
  /* 列表行：1px 描边分隔，hover 切到 --bg-2 */
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  cursor: pointer;
  border-bottom: 1px solid var(--xh-border);
  transition: background-color 120ms cubic-bezier(0.2, 0, 0, 1);
}
.xh-about-menu-item:hover {
  background-color: var(--xh-bg-2);
}
.xh-about-menu-item:last-child {
  border-bottom: none;
}
```

### 4.5 MainLayout 集成（5 处微调）

| 位置 | 改动 | 关键行 |
|---|---|---|
| 顶栏"关于"按钮 | Tooltip + Button 在 ❓ 之后插入 | MainLayout.tsx 第 554 行后 |
| Sider 底部 | 在 menuItems 末尾追加 `{ type: 'divider' }` + `{ key: '/about', icon: <InfoCircleOutlined />, label: '关于' }` | MainLayout.tsx 第 92 行后 |
| ROUTE_LABELS | 新增 `'/about': '关于'` | MainLayout.tsx 第 117 行后 |
| COMMAND_ITEMS | 末尾追加 `{ key: '/about', label: '关于', icon: <InfoCircleOutlined /> }` | MainLayout.tsx 第 142 行后 |
| G_PREFIX_MAP | 新增 `a: '/about'` | MainLayout.tsx 第 152 行后 |

**顶栏"关于"按钮代码**：

```tsx
import { InfoCircleOutlined } from '@ant-design/icons'

// 紧邻 ❓ 帮助按钮（MainLayout.tsx 第 554 行后）
<Tooltip title="关于">
  <Button
    type="text"
    shape="circle"
    size="small"
    icon={<InfoCircleOutlined />}
    style={{ fontSize: 16, width: 28, height: 28 }}
    onClick={() => navigate('/about')}
  />
</Tooltip>
```

---

## 5. 后端设计

### 5.1 API 契约

#### `GET /api/about` — 系统元信息

**鉴权**：白名单（无需登录）

**响应**：

```json
{
  "product": "闲鱼猎人",
  "version": "0.1.0",
  "build_date": "2026-06-28",
  "git_sha": "abc1234",
  "python": "3.10.12",
  "platform": "windows"
}
```

**异常处理**：

| 场景 | HTTP | Body |
|---|---|---|
| `_build_info.py` 缺字段 | 200 | 字段值 `"unknown"`（**不返回 5xx**，避免阻塞前端 UI） |
| `_build_info.py` 不存在 | 200 | 同上，兜底 |
| 数据库错误 | 500 | `{"detail": "About info unavailable"}` |

#### `GET /api/about/check-update` — 检查更新

**鉴权**：白名单（无需登录）

**响应（已是最新）**：

```json
{
  "current": "0.1.0",
  "latest": "0.1.0",
  "has_update": false,
  "release_url": "https://example.com/releases",
  "checked_at": "2026-06-28T16:00:00+08:00",
  "source": "local"
}
```

**响应（首版实现固定返回 `has_update=false`）**：

```python
# src/xianyu_hunter/web/routes/api_about.py
@router.get("/check-update", include_in_schema=False)
async def check_update() -> dict:
    current = _safe_version()
    return {
        "current": current,
        "latest": current,            # 首版：latest = current
        "has_update": False,
        "release_url": _RELEASE_URL,  # 占位：https://example.com/releases
        "checked_at": _now_iso(),
        "source": "local",
    }
```

**未来扩展点**：`_fetch_latest_version()` 内部实现可替换为调用 GitHub Releases API，**当前为占位 stub**。

### 5.2 `_build_info.py` 生成策略

**生成脚本**（`scripts/build_info.py`）：

```python
"""生成 _build_info.py：写入版本号、构建日期、Git SHA。

供 About API 与 /api/about/check-update 读取。
由 scripts/重新构建.bat 末尾自动调用。
"""
from __future__ import annotations
import subprocess
from datetime import datetime
from pathlib import Path
import sys

PKG_ROOT = Path(__file__).resolve().parents[1] / "src" / "xianyu_hunter"
INIT_FILE = PKG_ROOT / "__init__.py"
OUT_FILE = PKG_ROOT / "_build_info.py"


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            cwd=PKG_ROOT.parents[2],
            timeout=3,
        ).decode().strip()
    except Exception:
        return "unknown"


def _read_version() -> str:
    # 从 __init__.py 解析 __version__ = "x.y.z"
    for line in INIT_FILE.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("__version__"):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return "unknown"


def main() -> int:
    version = _read_version()
    sha = _git_sha()
    build_date = datetime.now().strftime("%Y-%m-%d")
    content = (
        f'# Auto-generated by scripts/build_info.py; do not edit.\n'
        f'__version__ = "{version}"\n'
        f'build_date = "{build_date}"\n'
        f'git_sha = "{sha}"\n'
    )
    OUT_FILE.write_text(content, encoding="utf-8")
    print(f"[build_info] {version} / {build_date} / {sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**生成的 `_build_info.py`**：

```python
# Auto-generated by scripts/build_info.py; do not edit.
__version__ = "0.1.0"
build_date = "2026-06-28"
git_sha = "abc1234"
```

**调用方式**（`scripts/重新构建.bat` 末尾追加）：

```bat
cd /d "%~dp0.."
python scripts\build_info.py
```

### 5.3 鉴权白名单扩展

**修改点**：`src/xianyu_hunter/web/middleware/auth.py` 第 32 行附近的 `WHITELIST` 集合：

```python
WHITELIST = {
    # ... 现有 7 项
    "/api/about",                  # 新增
    "/api/about/check-update",     # 新增
}
```

**为什么白名单**：
- `/api/about` 仅返回元信息，无敏感数据；
- `/api/about/check-update` 仅返回本机版本（首版）；
- 与 `/api/auth/me`、`/api/docs` 等公开端点保持一致。

### 5.4 Swagger UI 顶栏改动

**修改点**：`src/xianyu_hunter/web/app.py` 第 355 行：

```html
<!-- 旧 -->
<a class="xh-btn xh-btn-primary" href="/app/help" target="_blank">📖 帮助文档</a>
<!-- 新 -->
<a class="xh-btn xh-btn-primary" href="/app/about" target="_blank">📖 关于</a>
```

**不再改**：
- 顶栏 56px 布局、Logo 渐变、按钮配色（保持 Swagger 页与控制台的品牌一致）。

### 5.5 类图

```
api_about.py
├── router: APIRouter(prefix="/api/about", tags=["meta"])
├── GET /
│   └── returns AboutInfo (Pydantic model)
├── GET /check-update
│   └── returns UpdateCheckResult (Pydantic model)
├── _safe_version() -> str
│   └── try: import _build_info; except: "unknown"
├── _now_iso() -> str
│   └── datetime.now(UTC+8).isoformat()
└── _RELEASE_URL = "https://example.com/releases"
```

---

## 6. 数据流

### 6.1 首次访问 `/about`

```
User → SPA route /about
  → React.lazy() load About chunk
  → <About> mount
  → <BrandCard> mount → useUpdateChecker() lazy init (state=idle)
  → <AboutMenuList> mount → render 8 items
  → user click "检查更新"
    → setState(loading)
    → axios GET /api/about/check-update
      → api_about.py → read _build_info.py → return {current, latest=current, has_update=false}
    → response → setState(latest) → 3s 后 → setState(idle)
```

### 6.2 异常路径

| 触发 | 行为 |
|---|---|
| `_build_info.py` 不存在 | 后端 try/except → 字段 `"unknown"`，**不返回 5xx** |
| `/api/about/check-update` 网络中断 | axios 抛错 → hook catch → setState(error) → UI 显示"网络异常" |
| `/api/about` 返回 5xx | BrandCard 用 ErrorBoundary 隔离，列表照常显示 |

---

## 7. 视觉设计落地

### 7.1 与参考图对照

| 参考图元素 | 本设计落地 |
|---|---|
| 标题"关于 TRAE" | H1 字体 Cormorant + Noto Serif SC，字号 40px，字距 -0.5px |
| 浅灰底品牌卡 | 背景 `var(--xh-bg-1)`，1px 边框 `var(--xh-border)`，圆角 6px |
| Logo + 版本号 + 日期 + 检查更新 | BrandCard 一行布局，左 Logo 中文字 右按钮 |
| 列表行 + 右侧 ↗ | AboutMenuList 每行 padding 14px 16px，↗ icon 14px |
| 整体留白 | Content max-width 720px，padding 32px 24px 64px |
| 单色无装饰 | 不引入米其林红以外的色彩；CTA 用品牌红仅"检查更新"按钮 |

### 7.2 与项目现有风格的 3 个差异点

| 维度 | 项目既有（米其林） | 关于页（设计决策） | 原因 |
|---|---|---|---|
| 主色调 | 暗主题主导，红 + 金点缀 | 中性灰 + 品牌红 CTA | "关于"页偏 meta，避免过强品牌色干扰信息读取 |
| H1 字体 | Cormorant Didone | 同 Cormorant | 保持一致 |
| 圆角 | 6px 卡片 | 6px 卡片 | 完全一致 |

> 总体决策：**克制**。关于页是元信息容器，避免与主控制台争抢视觉焦点。

### 7.3 暗 / 亮主题验证清单

- [ ] 亮主题：背景 `#FFFFFF`、文字 `#262626`、卡片边框 `#D8D2C5`、hover `#F0EBE1`
- [ ] 暗主题：背景 `#14161C`、文字 `#F0EFE9`、卡片边框 `#2D303B`、hover `#1E2028`
- [ ] Logo 渐变（`#FF6200 → #FF8533`）在两套主题下对比度均 ≥ 3:1
- [ ] 列表 ↗ 图标在两套主题下对比度均 ≥ 4.5:1

---

## 8. 关键决策记录

| ID | 决策 | 备选 | 取舍 |
|---|---|---|---|
| D1 | `/about` 独立路由（不嵌 MainLayout） | 嵌 MainLayout 作子页 | 独立路由可分享链接、不被 Sider 占用；与 `/help` 风格一致 |
| D2 | Logo 用字符"闲"占位（与 Swagger 一致） | 设计独立 SVG | 避免资源依赖、保持品牌识别统一 |
| D3 | "检查更新"首版固定返回最新 | 调用 GitHub API | 项目无公开 release 渠道；为未来扩展留接口 |
| D4 | 开源声明用静态常量 + Modal | 引入 `license-checker` 自动生成 | 首版 80 条手动维护可控；P2 接入自动化 |
| D5 | 保留旧入口（❓、API 文字链）1 版本 | 立即移除 | 降低用户迁移成本；下版本移除 |
| D6 | `_build_info.py` 构建时生成 | 运行时 git 命令 | 避免运行时依赖 git 工具链；构建时固化 |
| D7 | `/api/about` 字段缺失返回 `"unknown"` 而非 5xx | 返回 503 | About 页是 meta，不应阻塞用户；前端用 `--` 兜底 |
| D8 | 不引入新 UI 库 | 引入 react-licenses 等 | 与 user_profile 偏好"禁止 AI 预制 UI 组件"一致 |

---

## 9. 风险与缓解

| ID | 风险 | 等级 | 缓解 | 验证 |
|---|---|---|---|---|
| R1 | `_build_info.py` 缺字段 → About 5xx | 中 | 兜底 `"unknown"`（D7） | `test_about.py::test_missing_build_info` |
| R2 | `check-update` 未来外网 SSRF | 中 | 当前 stub 仅返回本机；未来白名单域名 | 代码 review + ADR |
| R3 | 静态依赖列表与实际不一致 | 低 | 标注"以运行时实际安装为准"，P2 自动化 | 人工季度 review |
| R4 | 旧入口认知混淆 | 低 | Tooltip 标"（即将迁移）" | 用户反馈 |
| R5 | git_sha 在无 git 环境为 "unknown" | 低 | UI 显示逻辑跳过 unknown | E2E 测试 |
| R6 | 构建脚本未执行（开发者手动改 `__init__.py`） | 低 | `重新构建.bat` 末尾必调 | CI 钩子（P2） |

---

## 10. 测试策略

### 10.1 前端测试（Vitest + React Testing Library）

| 文件 | 用例 |
|---|---|
| `index.test.tsx` | 1) 渲染 H1 + BrandCard + 8 行列表  2) "检查更新" loading → latest 状态切换  3) 错误状态显示重试按钮  4) 复制版本号 Tooltip |
| `useUpdateChecker.test.ts` | 1) idle → loading → latest  2) 网络错误 → error(network)  3) 5xx → error(server)  4) 3s 后自动回 idle |
| `BrandCard.test.tsx` | 1) 渲染版本号 + 日期  2) git_sha=unknown 时不显示  3) 复制成功 |
| `OpenSourceLicenses.test.tsx` | 1) Modal 开关  2) 搜索过滤 |

### 10.2 后端测试（pytest）

| 文件 | 用例 |
|---|---|
| `test_about.py` | 1) GET /api/about 返回完整字段  2) _build_info 缺失时字段为 "unknown"  3) GET /api/about/check-update 返回 has_update=false  4) 鉴权白名单生效（无 token 仍可访问） |

### 10.3 端到端验收（人工 / Playwright）

| 场景 | 步骤 |
|---|---|
| 入口可达 | 顶栏 → 侧栏 → Command Palette → g+a 快捷键 → Swagger UI 顶栏 5 条路径全通 |
| 检查更新 | 正常 / 网络断开 / 服务挂 三态 |
| 主题切换 | 亮 / 暗截图对比 |
| 移动端 | 360px / 768px 截图 |

---

## 11. 验收对照（与需求 §11 映射）

| 需求验收项 | 设计落地章节 |
|---|---|
| A1 顶栏"关于"按钮 | §4.5 顶栏改动 |
| A2 跳转 `/about` | §3.1 路由变更 |
| A3 品牌卡 | §4.2 BrandCard |
| A4 复制按钮 | §4.2 + §4.3 |
| A5 检查更新三态 | §2.2 状态机 + §4.3 |
| A6 外部链接 | §4.1 信息树 |
| A7 侧栏底部 | §4.5 Sider 改动 |
| A8 Command Palette | §4.5 COMMAND_ITEMS |
| A9 g+a 快捷键 | §4.5 G_PREFIX_MAP |
| A10 Swagger UI 跳转 | §5.4 |
| A11 Help 页保留 | §6.1 现有路由不动 |
| A12 开源声明 Modal | §4.1 OpenSourceLicenses |
| A13 暗 / 亮主题 | §7.3 验证清单 |
| B1-B5 兼容 | §10.3 端到端 |
| C1-C4 性能 | 需求 §8 指标（设计阶段不细化压测） |
| D1-D5 质量 | §10 测试策略 |
| E1-E4 文档 | 需求 §11.5（已映射本文档） |

---

## 12. 配套实施计划

详见 [plans/about-menu-implementation-plan.md](./plans/about-menu-implementation-plan.md)。

---

## 13. 附录

### 13.1 关键文件链接

| 用途 | 路径 |
|---|---|
| 需求规格 | [about-menu-requirements.md](./about-menu-requirements.md) |
| 本设计 | `docs/about-menu-design.md` |
| 实施计划 | [plans/about-menu-implementation-plan.md](./plans/about-menu-implementation-plan.md) |
| 视觉规范 | [michelin-design-system.md](./michelin-design-system.md) |
| 目录规范 | [directory-structure.md](./directory-structure.md) |
| MainLayout | [MainLayout.tsx](../../frontend/src/components/layout/MainLayout.tsx) |
| App 路由 | [App.tsx](../../frontend/src/App.tsx) |
| Swagger UI HTML | [app.py](../../src/xianyu_hunter/web/app.py) |
| 鉴权白名单 | [auth.py](../../src/xianyu_hunter/web/middleware/auth.py) |
| 版本号源 | [\_\_init\_\_.py](../../src/xianyu_hunter/__init__.py) |

### 13.2 API 契约示例

**请求**：`GET /api/about`

**响应**：

```json
{
  "product": "闲鱼猎人",
  "version": "0.1.0",
  "build_date": "2026-06-28",
  "git_sha": "abc1234",
  "python": "3.10.12",
  "platform": "windows"
}
```

**请求**：`GET /api/about/check-update`

**响应**：

```json
{
  "current": "0.1.0",
  "latest": "0.1.0",
  "has_update": false,
  "release_url": "https://example.com/releases",
  "checked_at": "2026-06-28T16:00:00+08:00",
  "source": "local"
}
```

---

> 设计文档结束。代码改动必须先更新本设计文档及配套需求规格。
