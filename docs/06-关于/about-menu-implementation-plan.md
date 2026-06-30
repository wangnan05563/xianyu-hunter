# "关于" 菜单 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 整合 XianyuHunter 控制台分散的"帮助文档"与"API 文档"入口，新增"关于"菜单作为元信息 + 文档资源的统一入口，零侵入地完成 11 个现有页面的入口归口。

**Architecture:**
- 后端：FastAPI 新增 `GET /api/about` + `GET /api/about/check-update`，加入鉴权白名单
- 前端：React 懒加载新页面 `/about`，5 处 MainLayout 微调（顶栏 / Sider / Command Palette / 快捷键 / 路由字典）
- 构建：`scripts/build_info.py` 在 `重新构建.bat` 末尾生成 `_build_info.py`（版本号 / 构建日期 / Git SHA）
- 迁移：Swagger UI 顶栏"📖 帮助文档"跳转改为 `/app/about`

**Tech Stack:** Python + FastAPI + SQLAlchemy (SQLite) + pytest；前端 React + TypeScript + Ant Design 5 + Vitest

**关联设计文档:** [about-menu-design.md](../about-menu-design.md)
**关联需求文档:** [about-menu-requirements.md](../about-menu-requirements.md)

---

## 文件结构

| 文件 | 职责 | 操作 |
|------|------|------|
| `src/xianyu_hunter/_build_info.py` | 构建时生成的版本元信息 | 新建（构建脚本写入） |
| `src/xianyu_hunter/web/routes/api_about.py` | About API 路由 | 新建 |
| `src/xianyu_hunter/web/app.py` | include_router + Swagger UI 顶栏改跳转 | 修改 |
| `src/xianyu_hunter/web/middleware/auth.py` | 鉴权白名单新增 2 项 | 修改 |
| `scripts/build_info.py` | 构建脚本：写入 `_build_info.py` | 新建 |
| `scripts/重新构建.bat` | 末尾追加 1 行 | 修改 |
| `frontend/src/api/about.ts` | axios 客户端封装 | 新建 |
| `frontend/src/api/index.ts` | 导出 aboutApi | 修改 |
| `frontend/src/pages/About/index.tsx` | 页面壳 | 新建 |
| `frontend/src/pages/About/BrandCard.tsx` | 品牌卡组件 | 新建 |
| `frontend/src/pages/About/AboutMenuList.tsx` | 外部链接列表 | 新建 |
| `frontend/src/pages/About/OpenSourceLicenses.tsx` | 开源声明 Modal | 新建 |
| `frontend/src/pages/About/useUpdateChecker.ts` | 检查更新 hook | 新建 |
| `frontend/src/pages/About/i18n.ts` | 文案常量 | 新建 |
| `frontend/src/pages/About/about.css` | 局部样式 | 新建 |
| `frontend/src/pages/About/__tests__/index.test.tsx` | 前端测试 | 新建 |
| `frontend/src/components/layout/MainLayout.tsx` | 5 处微调 | 修改 |
| `frontend/src/App.tsx` | 新增 About 懒加载 + 路由 | 修改 |
| `tests/test_about.py` | 后端测试 | 新建 |

---

## Task 1: 后端 API 路由

**Files:**
- Create: `src/xianyu_hunter/web/routes/api_about.py`
- Modify: `src/xianyu_hunter/web/app.py`（`include_router` 列表）
- Modify: `src/xianyu_hunter/web/middleware/auth.py`（`WHITELIST` 集合）

- [ ] **Step 1.1: 创建 `api_about.py`**

新建 `src/xianyu_hunter/web/routes/api_about.py`：

```python
"""About API：暴露系统元信息 + 检查更新。

首版实现：
- GET /api/about 返回 _build_info.py 写入的版本/日期/SHA
- GET /api/about/check-update 固定返回 has_update=False（无外网通道）

后续扩展：check-update 可改为调用 GitHub Releases API；
当前实现不发起外网请求，不存在 SSRF 风险。
"""
from __future__ import annotations

import sys
import platform as _platform
from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/api/about", tags=["meta"])

# 占位 release URL：未来接入 GitHub Releases 时改为实际仓库地址
_RELEASE_URL = "https://example.com/releases"
_PRODUCT_NAME = "闲鱼猎人"

# UTC+8 时区（构建日期/检查时间统一使用）
_CST = timezone(timedelta(hours=8))


def _safe_build_info() -> dict[str, str]:
    """读取 _build_info.py，缺字段兜底为 'unknown'。"""
    try:
        from xianyu_hunter import _build_info  # type: ignore
    except Exception:
        return {"version": "unknown", "build_date": "unknown", "git_sha": "unknown"}
    return {
        "version": getattr(_build_info, "__version__", "unknown"),
        "build_date": getattr(_build_info, "build_date", "unknown"),
        "git_sha": getattr(_build_info, "git_sha", "unknown"),
    }


def _now_iso() -> str:
    return datetime.now(_CST).isoformat(timespec="seconds")


@router.get("", include_in_schema=False)
async def get_about() -> dict[str, Any]:
    """系统元信息：版本、构建日期、Git SHA、Python 版本、平台。"""
    info = _safe_build_info()
    return {
        "product": _PRODUCT_NAME,
        "version": info["version"],
        "build_date": info["build_date"],
        "git_sha": info["git_sha"],
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "platform": _platform.system().lower(),
    }


@router.get("/check-update", include_in_schema=False)
async def check_update() -> dict[str, Any]:
    """检查更新：首版固定返回 has_update=False。

    未来扩展：将 _fetch_latest_version() 内部改为调用 GitHub Releases API。
    当前不发起外网请求，UI 始终显示"已是最新"。
    """
    info = _safe_build_info()
    current = info["version"]
    return {
        "current": current,
        "latest": current,        # 首版：latest = current
        "has_update": False,
        "release_url": _RELEASE_URL,
        "checked_at": _now_iso(),
        "source": "local",
    }
```

> 为什么 include_in_schema=False：OpenAPI schema 暴露这两个端点无意义（前端独立消费），减少 /openapi.json 噪声。

- [ ] **Step 1.2: 在 app.py 注册路由**

修改 `src/xianyu_hunter/web/app.py` 的路由 include 列表（参考第 159-186 行的 `app.include_router(...)` 调用），在 `api_auth` 之后追加：

```python
    app.include_router(api_about.router)  # 关于菜单：版本信息 + 检查更新
```

- [ ] **Step 1.3: 鉴权白名单扩展**

修改 `src/xianyu_hunter/web/middleware/auth.py` 第 32 行附近的 `WHITELIST` 集合，追加：

```python
    "/api/about",                  # 系统元信息
    "/api/about/check-update",     # 检查更新
```

- [ ] **Step 1.4: 验证路由注册**

Run: `cd d:\code\otherProjects\17_xianyu; $env:PYTHONPATH="src"; python -c "from xianyu_hunter.web.app import create_app; app = create_app(); print([r.path for r in app.routes if 'about' in r.path])"`

Expected: 输出包含 `/api/about` 和 `/api/about/check-update`

- [ ] **Step 1.5: 验证白名单生效**

Run: `cd d:\code\otherProjects\17_xianyu; $env:PYTHONPATH="src"; python -c "from xianyu_hunter.web.middleware.auth import WHITELIST; assert '/api/about' in WHITELIST; assert '/api/about/check-update' in WHITELIST; print('whitelist ok')"`

Expected: 输出 `whitelist ok`

- [ ] **Step 1.6: Commit**

```bash
git add src/xianyu_hunter/web/routes/api_about.py src/xianyu_hunter/web/app.py src/xianyu_hunter/web/middleware/auth.py
git commit -m "feat(about): add /api/about meta endpoints + auth whitelist"
```

---

## Task 2: 构建脚本与 `_build_info.py`

**Files:**
- Create: `scripts/build_info.py`
- Modify: `scripts/重新构建.bat`

- [ ] **Step 2.1: 创建 `build_info.py`**

新建 `scripts/build_info.py`：

```python
"""生成 _build_info.py：写入版本号、构建日期、Git SHA。

供 About API 与 /api/about/check-update 读取。
由 scripts/重新构建.bat 末尾自动调用。

幂等：每次运行覆盖写入，不做时间戳累加。
容错：git 不可用时 git_sha 写 "unknown"，不中断构建。
"""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

# _build_info.py 输出路径
PKG_ROOT = Path(__file__).resolve().parents[1] / "src" / "xianyu_hunter"
INIT_FILE = PKG_ROOT / "__init__.py"
OUT_FILE = PKG_ROOT / "_build_info.py"
# 项目根目录（用于 git rev-parse）
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _git_sha() -> str:
    """读取当前 commit 的短 SHA；git 不可用时返回 'unknown'。"""
    try:
        result = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            cwd=PROJECT_ROOT,
            timeout=3,
        )
        sha = result.decode().strip()
        return sha if sha else "unknown"
    except Exception:
        return "unknown"


def _read_version() -> str:
    """从 __init__.py 解析 __version__ = "x.y.z"。

    失败兜底 "unknown"，不中断构建。
    """
    try:
        text = INIT_FILE.read_text(encoding="utf-8")
    except Exception:
        return "unknown"
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("__version__"):
            try:
                # __version__ = "0.1.0" 或 __version__ = '0.1.0'
                value = stripped.split("=", 1)[1].strip().strip('"').strip("'")
                return value
            except Exception:
                return "unknown"
    return "unknown"


def main() -> int:
    version = _read_version()
    sha = _git_sha()
    build_date = datetime.now().strftime("%Y-%m-%d")
    content = (
        "# Auto-generated by scripts/build_info.py; do not edit.\n"
        f'__version__ = "{version}"\n'
        f'build_date = "{build_date}"\n'
        f'git_sha = "{sha}"\n'
    )
    OUT_FILE.write_text(content, encoding="utf-8")
    print(f"[build_info] version={version} build_date={build_date} git_sha={sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2.2: 修改 `重新构建.bat` 末尾**

修改 `scripts/重新构建.bat`，在原有 `npm run build` 之后追加（参考 `scripts/重新构建.bat` 现有结构）：

```bat
echo [build_info] 生成版本元信息...
python scripts\build_info.py
if errorlevel 1 (
    echo [WARN] build_info.py 执行失败，About 页将显示 "unknown"
)
```

- [ ] **Step 2.3: 验证脚本**

Run: `cd d:\code\otherProjects\17_xianyu; python scripts\build_info.py`

Expected: 输出形如 `[build_info] version=0.1.0 build_date=2026-06-28 git_sha=abc1234`

- [ ] **Step 2.4: 验证 `_build_info.py` 内容**

Run: `Get-Content d:\code\otherProjects\17_xianyu\src\xianyu_hunter\_build_info.py`

Expected: 包含 `__version__`、`build_date`、`git_sha` 三个赋值语句

- [ ] **Step 2.5: 验证后端能读取**

Run: `cd d:\code\otherProjects\17_xianyu; $env:PYTHONPATH="src"; python -c "from xianyu_hunter import _build_info; print(_build_info.__version__, _build_info.build_date, _build_info.git_sha)"`

Expected: 输出形如 `0.1.0 2026-06-28 abc1234`

- [ ] **Step 2.6: Commit**

```bash
git add scripts/build_info.py scripts/重新构建.bat src/xianyu_hunter/_build_info.py
git commit -m "feat(build): add build_info.py to generate version metadata"
```

---

## Task 3: Swagger UI 顶栏跳转

**Files:**
- Modify: `src/xianyu_hunter/web/app.py:355`

- [ ] **Step 3.1: 改跳转链接**

修改 `src/xianyu_hunter/web/app.py` 第 355 行附近：

```html
<!-- 旧 -->
<a class="xh-btn xh-btn-primary" href="/app/help" target="_blank">📖 帮助文档</a>
<!-- 新 -->
<a class="xh-btn xh-btn-primary" href="/app/about" target="_blank">📖 关于</a>
```

- [ ] **Step 3.2: 验证**

Run: `Get-Content d:\code\otherProjects\17_xianyu\src\xianyu_hunter\web\app.py | Select-String "app/about"`

Expected: 至少 1 个匹配

- [ ] **Step 3.3: Commit**

```bash
git add src/xianyu_hunter/web/app.py
git commit -m "feat(docs): Swagger UI topbar jumps to /app/about"
```

---

## Task 4: 前端 API 客户端

**Files:**
- Create: `frontend/src/api/about.ts`
- Modify: `frontend/src/api/index.ts`

- [ ] **Step 4.1: 创建 `about.ts`**

新建 `frontend/src/api/about.ts`：

```typescript
import client from './client'

// About API 响应类型（与后端 api_about.py 契约对齐）
export interface AboutInfo {
  product: string
  version: string
  build_date: string
  git_sha: string
  python: string
  platform: string
}

export interface UpdateCheckResult {
  current: string
  latest: string
  has_update: boolean
  release_url: string
  checked_at: string
  source: 'local' | 'remote'  // 未来扩展 remote 分支
}

export const aboutApi = {
  get: () => client.get<AboutInfo>('/api/about').then((r) => r.data),
  checkUpdate: () => client.get<UpdateCheckResult>('/api/about/check-update').then((r) => r.data),
}
```

- [ ] **Step 4.2: 在 `index.ts` 导出**

修改 `frontend/src/api/index.ts` 第 8 行附近，追加：

```typescript
export { aboutApi } from './about'
```

- [ ] **Step 4.3: 类型检查**

Run: `cd d:\code\otherProjects\17_xianyu\frontend; npx tsc --noEmit`

Expected: 0 错误

- [ ] **Step 4.4: Commit**

```bash
git add frontend/src/api/about.ts frontend/src/api/index.ts
git commit -m "feat(about): add aboutApi client + types"
```

---

## Task 5: 前端 i18n 文案

**Files:**
- Create: `frontend/src/pages/About/i18n.ts`

- [ ] **Step 5.1: 创建 `i18n.ts`**

新建 `frontend/src/pages/About/i18n.ts`：

```typescript
// About 页面文案集中：未来接入 i18n 框架时无需改组件
export const TEXTS = {
  pageTitle: '关于',
  productName: '闲鱼猎人',
  h1Title: '关于 闲鱼猎人',
  versionLabel: '版本',
  releasedOn: '发布于',
  copyHint: '复制完整版本号',
  copyAriaLabel: '复制版本号',
  copied: '已复制',
  updateIdle: '检查更新',
  updateLoading: '检查中…',
  updateLatest: '已是最新',
  updateNewer: '有新版本',
  updateErrorNetwork: '网络异常',
  updateErrorServer: '服务异常',
  updateRetry: '重试',
  backToConsole: '返回控制台',
  footerCopyright: '闲鱼猎人',
  riskDisclaimer: '本工具仅供个人研究学习，详见 README 中的"风险免责"',
  menu: {
    terms: '用户协议',
    privacy: '隐私条款',
    licenses: '开源软件声明',
    help: '帮助文档',
    api: 'API 文档',
    contact: '联系我们',
    community: '官方社区',
    report: '报告问题',
  },
  licensesSearchPlaceholder: '搜索依赖名 / 许可证…',
  licensesTitle: '开源软件声明',
  emptySearch: '未找到匹配的依赖',
} as const
```

- [ ] **Step 5.2: Commit**

```bash
git add frontend/src/pages/About/i18n.ts
git commit -m "feat(about): add i18n constants"
```

---

## Task 6: useUpdateChecker hook

**Files:**
- Create: `frontend/src/pages/About/useUpdateChecker.ts`

- [ ] **Step 6.1: 创建 hook**

新建 `frontend/src/pages/About/useUpdateChecker.ts`：

```typescript
import { useState, useCallback } from 'react'
import { App } from 'antd'
import { aboutApi } from '../../api'
import { TEXTS } from './i18n'

/**
 * 检查更新状态机：
 * idle → loading → (latest | newer | error)
 * latest 3s 后自动回 idle
 */
export type UpdateState =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'latest' }
  | { kind: 'newer'; url: string; latest: string }
  | { kind: 'error'; reason: 'network' | 'server' }

const IDLE_TIMEOUT_MS = 3000

// axios 错误简易判定：网络中断通常无 response
function isNetworkError(e: unknown): boolean {
  if (typeof e === 'object' && e !== null) {
    const err = e as { response?: unknown; code?: string }
    return !err.response || err.code === 'ERR_NETWORK'
  }
  return false
}

export function useUpdateChecker(current: string) {
  const [state, setState] = useState<UpdateState>({ kind: 'idle' })
  const { message } = App.useApp()

  const run = useCallback(async () => {
    setState({ kind: 'loading' })
    try {
      const res = await aboutApi.checkUpdate()
      if (res.has_update) {
        setState({ kind: 'newer', url: res.release_url, latest: res.latest })
      } else {
        setState({ kind: 'latest' })
        // 3s 后自动回 idle，让用户看到"已是最新"反馈
        setTimeout(() => {
          setState((prev) => (prev.kind === 'latest' ? { kind: 'idle' } : prev))
        }, IDLE_TIMEOUT_MS)
      }
    } catch (e) {
      setState({ kind: 'error', reason: isNetworkError(e) ? 'network' : 'server' })
    }
  }, [])

  const copy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(current)
      message.success(TEXTS.copied)
    } catch {
      // 剪贴板权限被拒时降级：仅 toast 提示
      message.warning('复制失败，请手动选择')
    }
  }, [current, message])

  return { state, run, copy }
}
```

- [ ] **Step 6.2: Commit**

```bash
git add frontend/src/pages/About/useUpdateChecker.ts
git commit -m "feat(about): add useUpdateChecker hook with state machine"
```

---

## Task 7: BrandCard 组件

**Files:**
- Create: `frontend/src/pages/About/BrandCard.tsx`

- [ ] **Step 7.1: 创建 `BrandCard.tsx`**

新建 `frontend/src/pages/About/BrandCard.tsx`：

```tsx
import { Card, Button, Tooltip, theme } from 'antd'
import {
  CopyOutlined,
  ReloadOutlined,
  CheckCircleFilled,
  ArrowUpOutlined,
  WarningFilled,
  LoadingOutlined,
} from '@ant-design/icons'
import type { UpdateState } from './useUpdateChecker'
import { TEXTS } from './i18n'

interface BrandCardProps {
  version: string
  buildDate: string
  gitSha: string
  state: UpdateState
  onCheck: () => void
  onCopy: () => void
}

// 三态按钮渲染：根据状态机分别呈现
function UpdateButton({ state, onCheck }: { state: UpdateState; onCheck: () => void }) {
  switch (state.kind) {
    case 'loading':
      return (
        <Button loading icon={<LoadingOutlined />}>
          {TEXTS.updateLoading}
        </Button>
      )
    case 'latest':
      return (
        <Button type="text" icon={<CheckCircleFilled style={{ color: '#52c41a' }} />}>
          {TEXTS.updateLatest}
        </Button>
      )
    case 'newer':
      return (
        <Button
          type="primary"
          icon={<ArrowUpOutlined />}
          onClick={() => window.open(state.url, '_blank', 'noopener,noreferrer')}
        >
          {TEXTS.updateNewer} ({state.latest})
        </Button>
      )
    case 'error':
      return (
        <Button
          danger
          type="text"
          icon={<WarningFilled />}
          onClick={onCheck}
        >
          {state.reason === 'network' ? TEXTS.updateErrorNetwork : TEXTS.updateErrorServer} · {TEXTS.updateRetry}
        </Button>
      )
    case 'idle':
    default:
      return (
        <Button type="primary" icon={<ReloadOutlined />} onClick={onCheck}>
          {TEXTS.updateIdle}
        </Button>
      )
  }
}

export function BrandCard({ version, buildDate, gitSha, state, onCheck, onCopy }: BrandCardProps) {
  const { token } = theme.useToken()
  const showSha = gitSha && gitSha !== 'unknown'

  return (
    <Card
      style={{
        background: token.colorBgContainer,
        border: `1px solid ${token.colorBorderSecondary}`,
        borderRadius: 6,
        marginBottom: 24,
      }}
      styles={{ body: { padding: 20 } }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        {/* Logo：与 Swagger UI 顶栏品牌块完全一致（品牌识别统一） */}
        <div
          aria-hidden
          style={{
            width: 48,
            height: 48,
            borderRadius: 6,
            background: 'linear-gradient(135deg, #FF6200, #FF8533)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            fontSize: 22,
            fontWeight: 700,
            boxShadow: '0 2px 8px rgba(255, 98, 0, 0.25)',
            flexShrink: 0,
          }}
        >
          闲
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 18, fontWeight: 600, color: token.colorText }}>
              {TEXTS.versionLabel}: {version}
            </span>
            <Tooltip title={TEXTS.copyHint}>
              <Button
                type="text"
                size="small"
                icon={<CopyOutlined />}
                onClick={onCopy}
                aria-label={TEXTS.copyAriaLabel}
              />
            </Tooltip>
          </div>
          <div style={{ fontSize: 13, color: token.colorTextSecondary, marginTop: 4 }}>
            {TEXTS.releasedOn} {buildDate}
            {showSha && (
              <span style={{ marginLeft: 8, fontFamily: 'monospace' }}>@{gitSha}</span>
            )}
          </div>
        </div>
        <UpdateButton state={state} onCheck={onCheck} />
      </div>
    </Card>
  )
}
```

- [ ] **Step 7.2: Commit**

```bash
git add frontend/src/pages/About/BrandCard.tsx
git commit -m "feat(about): add BrandCard component with 5-state update button"
```

---

## Task 8: AboutMenuList 组件

**Files:**
- Create: `frontend/src/pages/About/AboutMenuList.tsx`

- [ ] **Step 8.1: 创建 `AboutMenuList.tsx`**

新建 `frontend/src/pages/About/AboutMenuList.tsx`：

```tsx
import { Card, theme } from 'antd'
import { ExportOutlined } from '@ant-design/icons'
import { Link } from 'react-router-dom'
import { TEXTS } from './i18n'

interface MenuItem {
  key: string
  label: string
  href: string
  external: boolean
}

// 8 个外部链接；按需求 §5.1 排序
const MENU_ITEMS: MenuItem[] = [
  { key: 'terms', label: TEXTS.menu.terms, href: 'https://example.com/terms', external: true },
  { key: 'privacy', label: TEXTS.menu.privacy, href: 'https://example.com/privacy', external: true },
  { key: 'licenses', label: TEXTS.menu.licenses, href: '#licenses', external: false }, // 触发 Modal
  { key: 'help', label: TEXTS.menu.help, href: '/help', external: false },           // SPA 内链
  { key: 'api', label: TEXTS.menu.api, href: '/api/docs', external: true },         // 新窗口
  { key: 'contact', label: TEXTS.menu.contact, href: 'mailto:dev@example.com', external: true },
  { key: 'community', label: TEXTS.menu.community, href: 'https://example.com/community', external: true },
  { key: 'report', label: TEXTS.menu.report, href: 'https://example.com/issues/new', external: true },
]

interface AboutMenuListProps {
  onOpenLicenses: () => void
}

export function AboutMenuList({ onOpenLicenses }: AboutMenuListProps) {
  const { token } = theme.useToken()

  const handleClick = (item: MenuItem, e: React.MouseEvent) => {
    if (item.key === 'licenses') {
      e.preventDefault()
      onOpenLicenses()
    }
  }

  return (
    <Card
      style={{
        background: token.colorBgContainer,
        border: `1px solid ${token.colorBorderSecondary}`,
        borderRadius: 6,
        overflow: 'hidden',
      }}
      styles={{ body: { padding: 0 } }}
    >
      {MENU_ITEMS.map((item, idx) => {
        const isInternal = !item.external && item.key !== 'licenses'
        const content = (
          <div
            className="xh-about-menu-item"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '14px 16px',
              cursor: 'pointer',
              borderBottom: idx < MENU_ITEMS.length - 1 ? `1px solid ${token.colorBorderSecondary}` : 'none',
              transition: 'background-color 120ms cubic-bezier(0.2, 0, 0, 1)',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = token.colorBgTextHover
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'transparent'
            }}
            onClick={(e) => handleClick(item, e)}
          >
            <span style={{ fontSize: 14, color: token.colorText }}>{item.label}</span>
            <ExportOutlined style={{ fontSize: 14, color: token.colorTextTertiary }} aria-hidden />
          </div>
        )
        if (isInternal) {
          return (
            <Link key={item.key} to={item.href} style={{ textDecoration: 'none', color: 'inherit' }}>
              {content}
            </Link>
          )
        }
        return (
          <a
            key={item.key}
            href={item.href}
            target={item.external ? '_blank' : undefined}
            rel={item.external ? 'noopener noreferrer' : undefined}
            style={{ textDecoration: 'none', color: 'inherit', display: 'block' }}
          >
            {content}
          </a>
        )
      })}
    </Card>
  )
}
```

- [ ] **Step 8.2: Commit**

```bash
git add frontend/src/pages/About/AboutMenuList.tsx
git commit -m "feat(about): add AboutMenuList with 8 link items"
```

---

## Task 9: OpenSourceLicenses Modal

**Files:**
- Create: `frontend/src/pages/About/OpenSourceLicenses.tsx`

- [ ] **Step 9.1: 创建 `OpenSourceLicenses.tsx`**

新建 `frontend/src/pages/About/OpenSourceLicenses.tsx`：

```tsx
import { useState, useMemo } from 'react'
import { Modal, Input, List, Tag, theme } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import { TEXTS } from './i18n'

// 首版静态依赖清单（80 条左右，P2 接入 license-checker 自动生成）
// 字段：name / version / license / repo
interface Dependency {
  name: string
  version: string
  license: string
  repo: string
}

const DEPENDENCIES: Dependency[] = [
  // 前端（约 30 条）
  { name: 'react', version: '18.3.1', license: 'MIT', repo: 'https://github.com/facebook/react' },
  { name: 'react-dom', version: '18.3.1', license: 'MIT', repo: 'https://github.com/facebook/react' },
  { name: 'antd', version: '5.21.0', license: 'MIT', repo: 'https://github.com/ant-design/ant-design' },
  { name: '@ant-design/icons', version: '5.5.0', license: 'MIT', repo: 'https://github.com/ant-design/ant-design-icons' },
  { name: 'react-router-dom', version: '6.27.0', license: 'MIT', repo: 'https://github.com/remix-run/react-router' },
  { name: 'axios', version: '1.7.0', license: 'MIT', repo: 'https://github.com/axios/axios' },
  { name: 'echarts', version: '5.5.0', license: 'Apache-2.0', repo: 'https://github.com/apache/echarts' },
  { name: 'dayjs', version: '1.11.0', license: 'MIT', repo: 'https://github.com/iamkun/dayjs' },
  // ... 略，按需补充到 30 条
  // 后端（约 50 条）
  { name: 'fastapi', version: '0.115.0', license: 'MIT', repo: 'https://github.com/tiangolo/fastapi' },
  { name: 'uvicorn', version: '0.30.0', license: 'BSD-3-Clause', repo: 'https://github.com/encode/uvicorn' },
  { name: 'pydantic', version: '2.9.0', license: 'MIT', repo: 'https://github.com/pydantic/pydantic' },
  { name: 'sqlalchemy', version: '2.0.0', license: 'MIT', repo: 'https://github.com/sqlalchemy/sqlalchemy' },
  { name: 'playwright', version: '1.47.0', license: 'Apache-2.0', repo: 'https://github.com/microsoft/playwright-python' },
  { name: 'loguru', version: '0.7.0', license: 'MIT', repo: 'https://github.com/Delgan/loguru' },
  { name: 'httpx', version: '0.27.0', license: 'BSD-3-Clause', repo: 'https://github.com/encode/httpx' },
  // ... 略，按需补充到 50 条
]

interface OpenSourceLicensesProps {
  open: boolean
  onClose: () => void
}

export function OpenSourceLicenses({ open, onClose }: OpenSourceLicensesProps) {
  const { token } = theme.useToken()
  const [search, setSearch] = useState('')

  const filtered = useMemo(() => {
    const kw = search.trim().toLowerCase()
    if (!kw) return DEPENDENCIES
    return DEPENDENCIES.filter(
      (d) =>
        d.name.toLowerCase().includes(kw) ||
        d.license.toLowerCase().includes(kw),
    )
  }, [search])

  return (
    <Modal
      title={TEXTS.licensesTitle}
      open={open}
      onCancel={onClose}
      footer={null}
      width={720}
      destroyOnClose
    >
      <Input
        placeholder={TEXTS.licensesSearchPlaceholder}
        prefix={<SearchOutlined />}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        allowClear
        style={{ marginBottom: 16 }}
      />
      <div style={{ maxHeight: '60vh', overflowY: 'auto' }}>
        {filtered.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 32, color: token.colorTextSecondary }}>
            {TEXTS.emptySearch}
          </div>
        ) : (
          <List
            size="small"
            dataSource={filtered}
            renderItem={(d) => (
              <List.Item>
                <List.Item.Meta
                  title={
                    <a href={d.repo} target="_blank" rel="noopener noreferrer">
                      {d.name} <span style={{ color: token.colorTextTertiary }}>@{d.version}</span>
                    </a>
                  }
                  description={<Tag color="blue">{d.license}</Tag>}
                />
              </List.Item>
            )}
          />
        )}
      </div>
    </Modal>
  )
}
```

- [ ] **Step 9.2: 补充完整依赖列表（按 package.json + requirements.txt 实际填写）**

> 实际实施时，扫描 `frontend/package.json` 的 dependencies + devDependencies 与 `requirements.txt`，按上面 7 个示例补全。**这一步是体力活，不在此处展开模板**。

- [ ] **Step 9.3: Commit**

```bash
git add frontend/src/pages/About/OpenSourceLicenses.tsx
git commit -m "feat(about): add OpenSourceLicenses modal with static deps list"
```

---

## Task 10: About 页面壳

**Files:**
- Create: `frontend/src/pages/About/index.tsx`
- Create: `frontend/src/pages/About/about.css`

- [ ] **Step 10.1: 创建 `index.tsx`**

新建 `frontend/src/pages/About/index.tsx`：

```tsx
import { useEffect, useState } from 'react'
import { Layout, Typography, Button, Space, Tooltip, theme } from 'antd'
import { ArrowLeftOutlined, FileTextOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { BrandCard } from './BrandCard'
import { AboutMenuList } from './AboutMenuList'
import { OpenSourceLicenses } from './OpenSourceLicenses'
import { useUpdateChecker } from './useUpdateChecker'
import { aboutApi } from '../../api'
import { TEXTS } from './i18n'
import './about.css'

const { Header, Content } = Layout
const { Title, Text } = Typography

interface BuildInfo {
  version: string
  buildDate: string
  gitSha: string
}

const FALLBACK: BuildInfo = { version: '--', buildDate: '--', gitSha: 'unknown' }

export default function About() {
  const navigate = useNavigate()
  const { token } = theme.useToken()
  const [info, setInfo] = useState<BuildInfo>(FALLBACK)
  const [licensesOpen, setLicensesOpen] = useState(false)

  // 拉取元信息；失败时 FALLBACK 兜底，不阻塞 UI
  useEffect(() => {
    aboutApi.get().then(
      (d) => setInfo({ version: d.version, buildDate: d.build_date, gitSha: d.git_sha }),
      () => {/* 失败用 FALLBACK */},
    )
  }, [])

  const { state, run, copy } = useUpdateChecker(info.version)

  return (
    <Layout style={{ minHeight: '100vh' }} className="xh-about-page">
      <Header
        style={{
          background: token.colorBgContainer,
          padding: '0 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          boxShadow: '0 1px 4px rgba(0, 0, 0, 0.04)',
          position: 'sticky',
          top: 0,
          zIndex: 10,
          height: 56,
        }}
      >
        <Space>
          <FileTextOutlined style={{ fontSize: 18, color: token.colorPrimary }} />
          <Title level={4} style={{ margin: 0 }}>{TEXTS.pageTitle}</Title>
        </Space>
        <Button
          type="primary"
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate('/')}
        >
          {TEXTS.backToConsole}
        </Button>
      </Header>
      <Content style={{ background: token.colorBgLayout, overflow: 'auto' }}>
        <div className="xh-about-content">
          <h1
            className="xh-about-h1"
            style={{
              fontFamily: '"Cormorant Garamond", "Noto Serif SC", Georgia, serif',
              fontSize: 40,
              fontWeight: 600,
              letterSpacing: '-0.5px',
              color: token.colorTextHeading,
              marginBottom: 8,
            }}
          >
            {TEXTS.h1Title}
          </h1>
          <BrandCard
            version={info.version}
            buildDate={info.buildDate}
            gitSha={info.gitSha}
            state={state}
            onCheck={run}
            onCopy={copy}
          />
          <AboutMenuList onOpenLicenses={() => setLicensesOpen(true)} />
          <OpenSourceLicenses
            open={licensesOpen}
            onClose={() => setLicensesOpen(false)}
          />
          <div className="xh-about-footer">
            <Tooltip title={TEXTS.riskDisclaimer}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                © {new Date().getFullYear()} {TEXTS.footerCopyright}
              </Text>
            </Tooltip>
          </div>
        </div>
      </Content>
    </Layout>
  )
}
```

- [ ] **Step 10.2: 创建 `about.css`**

新建 `frontend/src/pages/About/about.css`：

```css
.xh-about-page {
  /* 全部色彩 / 圆角 / 阴影 / 字体走 CSS Token；
     此处仅定义 max-width 与 padding 等结构性样式 */
}

.xh-about-content {
  max-width: 720px;
  margin: 0 auto;
  padding: 32px 24px 64px;
}

.xh-about-h1 {
  /* Cormorant 在浅色主题下需要 #1A1814，深色主题下需要 #F0EFE9；
     由内联 style 注入 color，此处只保留结构性声明 */
}

.xh-about-footer {
  text-align: center;
  margin-top: 32px;
  padding-top: 16px;
  border-top: 1px solid var(--xh-border, transparent);
}

@media (max-width: 768px) {
  .xh-about-content {
    padding: 16px 16px 48px;
  }
  .xh-about-h1 {
    font-size: 32px !important;
  }
}
```

- [ ] **Step 10.3: Commit**

```bash
git add frontend/src/pages/About/index.tsx frontend/src/pages/About/about.css
git commit -m "feat(about): add About page shell with BrandCard + List + Modal"
```

---

## Task 11: 路由注册

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 11.1: 懒加载 + 路由**

修改 `frontend/src/App.tsx`：
- 在第 33-34 行（Help 附近）新增 `const About = lazyRetry(() => import('./pages/About'))`
- 在第 66-67 行（Help 路由附近）新增 `<Route path="/about" element={<LazyRoute><About /></LazyRoute>} />`

```tsx
const About = lazyRetry(() => import('./pages/About'))
// ...
<Route path="/about" element={<LazyRoute><About /></LazyRoute>} />
```

- [ ] **Step 11.2: 类型检查**

Run: `cd d:\code\otherProjects\17_xianyu\frontend; npx tsc --noEmit`

Expected: 0 错误

- [ ] **Step 11.3: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat(about): register /about route with lazy loading"
```

---

## Task 12: MainLayout 5 处微调

**Files:**
- Modify: `frontend/src/components/layout/MainLayout.tsx`

- [ ] **Step 12.1: 导入 InfoCircleOutlined**

在 import 块（第 2-37 行）找到 `@ant-design/icons` 行，追加：

```tsx
  InfoCircleOutlined,
```

- [ ] **Step 12.2: 顶栏新增"关于"按钮**

在第 554 行（❓ 帮助按钮 `</Tooltip>` 之后）追加：

```tsx
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

- [ ] **Step 12.3: Sider 底部新增菜单项**

在 `menuItems` 数组（第 50-94 行）末尾（第 92-93 行 `}` 之后）追加：

```tsx
  { type: 'divider' as const },
  {
    key: '/about',
    icon: <InfoCircleOutlined />,
    label: '关于',
  },
```

- [ ] **Step 12.4: ROUTE_LABELS 字典新增**

在第 117 行（`'/help': '帮助文档',` 之后）追加：

```tsx
  '/about': '关于',
```

- [ ] **Step 12.5: COMMAND_ITEMS 数组新增**

在第 142 行（`{ key: '/help', label: '帮助文档', icon: <QuestionCircleOutlined /> },` 之后）追加：

```tsx
  { key: '/about', label: '关于', icon: <InfoCircleOutlined /> },
```

- [ ] **Step 12.6: G_PREFIX_MAP 新增快捷键**

在第 152 行（`l: '/logs',` 之后）追加：

```tsx
  a: '/about',
```

- [ ] **Step 12.7: 类型检查**

Run: `cd d:\code\otherProjects\17_xianyu\frontend; npx tsc --noEmit`

Expected: 0 错误

- [ ] **Step 12.8: Commit**

```bash
git add frontend/src/components/layout/MainLayout.tsx
git commit -m "feat(about): integrate About into MainLayout (5 spots)"
```

---

## Task 13: 前端单元测试

**Files:**
- Create: `frontend/src/pages/About/__tests__/index.test.tsx`

- [ ] **Step 13.1: 创建测试**

新建 `frontend/src/pages/About/__tests__/index.test.tsx`：

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ConfigProvider, App as AntdApp } from 'antd'
import About from '../index'
import { aboutApi } from '../../../api'

// mock 掉 axios 调用，避免真实网络
vi.mock('../../../api', async () => {
  const actual = await vi.importActual<typeof import('../../../api')>('../../../api')
  return {
    ...actual,
    aboutApi: {
      get: vi.fn().mockResolvedValue({
        product: '闲鱼猎人',
        version: '0.1.0',
        build_date: '2026-06-28',
        git_sha: 'abc1234',
        python: '3.10.0',
        platform: 'windows',
      }),
      checkUpdate: vi.fn().mockResolvedValue({
        current: '0.1.0',
        latest: '0.1.0',
        has_update: false,
        release_url: 'https://example.com/releases',
        checked_at: '2026-06-28T16:00:00+08:00',
        source: 'local',
      }),
    },
  }
})

function renderWithProviders(ui: React.ReactNode) {
  return render(
    <ConfigProvider>
      <AntdApp>{ui}</AntdApp>
    </ConfigProvider>,
  )
}

describe('About page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders H1 + version + 8 menu items', async () => {
    renderWithProviders(<About />)
    await waitFor(() => {
      expect(screen.getByText(/关于 闲鱼猎人/)).toBeInTheDocument()
    })
    expect(screen.getByText(/版本: 0.1.0/)).toBeInTheDocument()
    expect(screen.getByText('用户协议')).toBeInTheDocument()
    expect(screen.getByText('API 文档')).toBeInTheDocument()
    expect(screen.getByText('报告问题')).toBeInTheDocument()
  })

  it('click 检查更新 → 显示"已是最新"', async () => {
    const user = userEvent.setup()
    renderWithProviders(<About />)
    await waitFor(() => screen.getByText('检查更新'))
    await user.click(screen.getByText('检查更新'))
    await waitFor(() => {
      expect(screen.getByText('已是最新')).toBeInTheDocument()
    })
  })

  it('API 失败时显示 FALLBACK (--)', async () => {
    vi.mocked(aboutApi.get).mockRejectedValueOnce(new Error('network'))
    renderWithProviders(<About />)
    await waitFor(() => {
      // 即便失败也要显示卡片，不能白屏
      expect(screen.getByText(/版本: --/)).toBeInTheDocument()
    })
  })
})
```

- [ ] **Step 13.2: 跑测试**

Run: `cd d:\code\otherProjects\17_xianyu\frontend; npx vitest run src/pages/About`

Expected: 3 个用例全部通过

- [ ] **Step 13.3: Commit**

```bash
git add frontend/src/pages/About/__tests__/index.test.tsx
git commit -m "test(about): add 3 unit tests for About page"
```

---

## Task 14: 后端单元测试

**Files:**
- Create: `tests/test_about.py`

- [ ] **Step 14.1: 创建测试**

新建 `tests/test_about.py`：

```python
"""About API 单元测试。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    from xianyu_hunter.web.app import create_app
    app = create_app()
    return TestClient(app)


def test_get_about_returns_full_fields(client: TestClient) -> None:
    """GET /api/about 返回完整字段（_build_info.py 已生成时）。"""
    resp = client.get("/api/about")
    assert resp.status_code == 200
    data = resp.json()
    assert data["product"] == "闲鱼猎人"
    assert "version" in data
    assert "build_date" in data
    assert "git_sha" in data
    assert "python" in data
    assert "platform" in data


def test_get_about_handles_missing_build_info(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    """_build_info 模块导入失败时，字段为 'unknown'，不返回 5xx。"""
    import sys

    # 隐藏 _build_info
    monkeypatch.setitem(sys.modules, "xianyu_hunter._build_info", None)

    resp = client.get("/api/about")
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == "unknown"
    assert data["build_date"] == "unknown"
    assert data["git_sha"] == "unknown"


def test_check_update_returns_no_update(client: TestClient) -> None:
    """GET /api/about/check-update 首版固定返回 has_update=False。"""
    resp = client.get("/api/about/check-update")
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_update"] is False
    assert data["current"] == data["latest"]
    assert data["source"] == "local"
    assert "checked_at" in data


def test_about_endpoints_in_auth_whitelist(client: TestClient) -> None:
    """无 token 仍可访问（白名单生效）。"""
    # 不传 Authorization header
    resp1 = client.get("/api/about")
    resp2 = client.get("/api/about/check-update")
    assert resp1.status_code == 200
    assert resp2.status_code == 200
```

- [ ] **Step 14.2: 跑测试**

Run: `cd d:\code\otherProjects\17_xianyu; $env:PYTHONPATH="src"; python -m pytest tests/test_about.py -v`

Expected: 4 个用例全部通过

- [ ] **Step 14.3: 回归测试**

Run: `cd d:\code\otherProjects\17_xianyu; $env:PYTHONPATH="src"; python -m pytest tests/ -q -x --ignore=tests/test_about.py`

Expected: 其他测试无回归失败

- [ ] **Step 14.4: Commit**

```bash
git add tests/test_about.py
git commit -m "test(about): add 4 backend tests for /api/about endpoints"
```

---

## Task 15: 端到端验证

**Files:** 无新文件

- [ ] **Step 15.1: 启动后端服务**

Run: `cd d:\code\otherProjects\17_xianyu; $env:PYTHONPATH="src"; python -m xianyu_hunter web --port 8000`

Expected: 服务在 8000 端口启动，Swagger UI 可访问 `http://127.0.0.1:8000/api/docs`

- [ ] **Step 15.2: 验证 API**

Run: `curl http://127.0.0.1:8000/api/about`（PowerShell: `Invoke-RestMethod http://127.0.0.1:8000/api/about`）

Expected: 返回 JSON 含 version / build_date / git_sha

Run: `Invoke-RestMethod http://127.0.0.1:8000/api/about/check-update`

Expected: `has_update: false`

- [ ] **Step 15.3: 验证 Swagger 顶栏跳转**

浏览器访问 `http://127.0.0.1:8000/api/docs` → 点击右上角"📖 关于"按钮

Expected: 新窗口打开 SPA 登录页（未登录时被引导到 /login）

- [ ] **Step 15.4: 启动前端 + 完整路径验证**

```bash
cd d:\code\otherProjects\17_xianyu\frontend
npm run build
```

启动完整服务（`scripts/启动服务.bat`），浏览器登录后验证：

| 入口 | 验证 | 期望 |
|---|---|---|
| 顶栏 ℹ️ 图标 | 点击 | 跳 `/about` |
| 侧栏底部"关于" | 点击 | 跳 `/about` |
| Command Palette Ctrl+K | 输入"关于" | 列表含"关于"项，回车跳转 |
| g+a 快捷键 | 连续按 | 跳 `/about` |
| Swagger 顶栏 | 点击"📖 关于" | 跳 `/app/about` |
| 旧 ❓ 入口 | 点击 | 仍跳 `/help`（回流） |

- [ ] **Step 15.5: 主题切换**

在 About 页切换暗 / 亮主题，对比截图：
- 卡片背景色
- 文字对比度
- Logo 渐变可见性

- [ ] **Step 15.6: 移动端**

浏览器 DevTools 切到 360px 宽度，截图确认无横向滚动 + 列表行可点击。

- [ ] **Step 15.7: 关闭服务**

Run: `cd d:\code\otherProjects\17_xianyu; .\scripts\停止服务.bat`

- [ ] **Step 15.8: 写交付记录**

新建 `docs/sprints/2026-06-28-about-menu.md`（参照 `docs/sprints/2026-06-26-item-sold-status-detection-design.md` 格式）：

```markdown
# About 菜单 - 交付记录

> 日期：2026-06-28
> 关联需求：about-menu-requirements.md
> 关联设计：about-menu-design.md

## 实施内容
- 新增 13 个文件、修改 5 个文件（详见 about-menu-design.md §3.2）
- P0-P2 全量完成

## 测试
- 前端 Vitest：3 用例通过
- 后端 pytest：4 用例通过
- 端到端：5 入口 + 2 主题 + 1 移动端 全部通过

## 已知限制
- 开源声明为静态常量，P2 接入 license-checker 自动生成
- check-update 首版固定返回 has_update=False，P2 接入外网通道
```

- [ ] **Step 15.9: Commit 交付记录**

```bash
git add docs/sprints/2026-06-28-about-menu.md
git commit -m "docs(about): add delivery record for About menu"
```

---

## 任务依赖图

```
Task 1 (后端 API) ─┐
                    ├─→ Task 13-14 (测试) ─→ Task 15 (端到端)
Task 2 (构建脚本) ─┤
                    │
Task 3 (Swagger)  ─┤
                    │
Task 4 (前端 API)  ─┼─→ Task 5 (i18n) ─→ Task 6 (hook) ─→ Task 7 (BrandCard) ─┐
                                                                                ├─→ Task 10 (页面壳)
                                                                                │
                                                                  Task 8 (Menu) ┤
                                                                                │
                                                                  Task 9 (Modal) ┘
                                                                                       │
                                                                                       ▼
                                                                              Task 11 (路由)
                                                                                       │
                                                                                       ▼
                                                                              Task 12 (MainLayout 5 处)
                                                                                       │
                                                                                       ▼
                                                                              Task 15 (端到端)
```

## 验收对照（与需求 §11）

| 需求 | 任务 | 状态 |
|---|---|---|
| A1 顶栏 ℹ️ 按钮 | Task 12.2 | □ |
| A2 跳转 /about | Task 11.1 | □ |
| A3 品牌卡 | Task 7 | □ |
| A4 复制按钮 | Task 6 + Task 7.1 | □ |
| A5 检查更新三态 | Task 6 + Task 7.1 | □ |
| A6 外部链接 | Task 8 | □ |
| A7 侧栏底部 | Task 12.3 | □ |
| A8 Command Palette | Task 12.5 | □ |
| A9 g+a 快捷键 | Task 12.6 | □ |
| A10 Swagger 跳转 | Task 3 | □ |
| A11 Help 页保留 | Task 15.4 | □ |
| A12 开源声明 | Task 9 | □ |
| A13 暗 / 亮主题 | Task 15.5 | □ |
| B 兼容 | Task 15.4-15.6 | □ |
| C 性能 | 性能由 Vitest 跑分时附带；本文不细化 | □ |
| D 质量 | Task 13 + Task 14 | □ |
| E 文档 | Task 15.8 | □ |

---

> 实施计划结束。15 个 Task 完成后回写交付记录；任一 Task 失败需在 docs/sprints 中追加 incident note。
