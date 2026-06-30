# XianyuHunter 米其林风格 UI 设计规范

> 版本：v1.0
> 日期：2026-06-07
> 适用范围：`src/xianyu_hunter/web/static/app.css` + `templates/**/*.html`
> 风格锚点：**Michelin Guide 视觉识别系统**（法式优雅 · 经典红 · 星级评定 · Didone 字体）

---

## 一、设计哲学（Design Philosophy）

### 1.1 核心命题

XianyuHunter 是一款"自动化运营抢单"业务工具，原本的视觉语言是"功能优先 · 工程师审美"（深灰 + 闲鱼橙 + 系统字体）。本次重塑在**不牺牲业务可用性的前提下**，引入米其林品牌的**法式优雅 + 经典红黑 + 星级评定语义**，将工具从"内部脚本感"提升至"专业级 SaaS 品牌感"。

### 1.2 三大原则

| 原则 | 说明 | 落地手段 |
|---|---|---|
| **Michelin Identity** | 让用户在 0.5 秒内识别出"这是米其林系" | 主色 `#E20613`、星标金 `#C9A961`、Bibendum 品牌符 |
| **Functional First** | 美观不可挤占操作效率 | 保留所有网格密度、键盘流、信息层级 |
| **Editorial Restraint** | 留白即奢华 | 大标题用 Didone、字距加宽、卡片 1.5× 内边距 |

### 1.3 不做什么（Anti-Pattern）

- ❌ 不引入"米其林轮胎人 Bibendum"完整形象（业务工具不需要吉祥物干扰操作）
- ❌ 不堆砌装饰元素（雪花、菱形纹仅作为 1px 边框暗示）
- ❌ 不做整页动画（业务工具首屏必须毫秒级可用）
- ❌ 不破坏暗色 / 亮色双主题（设计师在两套主题下都需自洽）

---

## 二、色彩系统（Color System）

### 2.1 品牌色板（Brand Palette）

| Token | Hex | 用途 | 灵感 |
|---|---|---|---|
| `--michelin-red` | `#E20613` | 主色 · CTA · 重点强调 | 米其林指南经典红 |
| `--michelin-red-deep` | `#B8050F` | 暗主题下的红 · hover/active | 暗色环境下的视觉下沉 |
| `--star-gold` | `#C9A961` | 评级 · 高价值 KPI · "星级"标识 | 米其林星级奖章 |
| `--star-gold-soft` | `#E5D4A0` | 暗主题下的金 · 描边/次级 | 暗色环境里的低饱和金 |
| `--guide-cream` | `#F5F0E8` | 亮色背景 · 卡片底色 | 米其林指南纸质米色 |
| `--guide-cream-dim` | `#E8E0D0` | 亮色次级背景 · 分隔 | 米其林纸张阴影色 |

### 2.2 中性色（Neutrals）

**暗主题（默认）**：

| Token | Hex | 用途 |
|---|---|---|
| `--bg-0` | `#0A0B0E` | 全局最深背景（比原 #0b0d12 更纯黑，对比度更高） |
| `--bg-1` | `#14161C` | 卡片 / 顶栏 |
| `--bg-2` | `#1E2028` | 二级容器 / 输入框 |
| `--bg-3` | `#2A2D38` | hover / 三级容器 |
| `--border` | `#2D303B` | 默认描边 |
| `--border-strong` | `#404552` | 强调描边 / focus ring |

**亮色主题**：

| Token | Hex | 用途 |
|---|---|---|
| `--bg-0` | `#FAF7F2` | 暖米色全局背景 |
| `--bg-1` | `#FFFFFF` | 卡片白底 |
| `--bg-2` | `#F0EBE1` | 次级容器（暖米阴影） |
| `--bg-3` | `#E5DFD3` | hover |
| `--border` | `#D8D2C5` | 米色调描边（比原 #d8dde7 更暖） |
| `--border-strong` | `#B8B0A0` | 强调描边 |

### 2.3 文字色（Text）

| Token | 暗主题 | 亮主题 | 用途 |
|---|---|---|---|
| `--text-0` | `#F0EFE9` | `#1A1814` | 标题 / 主文（米色调白，黑） |
| `--text-1` | `#B8B5AC` | `#3A352D` | 次要文 |
| `--text-2` | `#7A776E` | `#6B6457` | 辅助文 |
| `--text-3` | `#4D4B45` | `#9A9282` | 弱化文 / placeholder |

### 2.4 状态色（Semantic）

| 状态 | 暗主题 | 亮主题 | 备注 |
|---|---|---|---|
| `--ok` | `#3FA572` | `#16A34A` | 比原 #22c55e 略沉，更稳重 |
| `--warn` | `#D4A017` | `#CA8A04` | 用米其林"二星"语义色，更金 |
| `--err` | `#DC2626` | `#DC2626` | 与品牌红区分度足够 |
| `--info` | `#5B7AB8` | `#2563EB` | 深一点的蓝，专业感 |

> **关键决策**：业务工具里 err 不能用品牌红（避免和米其林红混淆），
> 故 err 用了"消防红" `#DC2626`，与 `#E20613` 在色相上同族但明度不同。

---

## 三、字体系统（Typography）

### 3.1 字体族（Font Stack）

| 角色 | 字体 | 备选 | 用法 |
|---|---|---|---|
| **Display** | `'Cormorant Garamond', 'Playfair Display', Georgia, serif` | 系统衬线 | 品牌名 · H1 · 卡片大数值 |
| **Body** | `'Inter', -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif` | 系统无衬线 | 正文 · 按钮 · 标签 |
| **Mono** | `'JetBrains Mono', ui-monospace, "SF Mono", Menlo, Consolas, monospace` | 系统等宽 | ID · 时间戳 · 数值 |
| **Chinese** | `"Noto Serif SC", "Source Han Serif SC", "Songti SC", serif` | 系统宋体 | 中文 H1（叠在 Display 后） |

> CDN 引入 `Cormorant Garamond`（米其林指南同款 Didone 风格）+ `Inter` + `JetBrains Mono`，
> 中文回退到系统中文字体栈。

### 3.2 字号阶梯（Type Scale）

| 级别 | px | 用途 | 字距 |
|---|---|---|---|
| `display-1` | 56 | 仅品牌区大标题 | -1.5px |
| `display-2` | 40 | 页面 H1（Dashboard 等） | -0.5px |
| `h1` | 28 | 卡片 H1 | -0.3px |
| `h2` | 20 | 卡片标题（原 14px → 提升为差异化） | 0 |
| `body` | 14 | 正文（不变） | 0 |
| `small` | 12 | 辅助文 | +0.2px |
| `tiny` | 11 | label / 角标 | +0.5px |

### 3.3 字距规则（Letter-Spacing）

- **衬线大字**（display-*）：`-0.02em` 紧凑（Didone 经典收紧）
- **小字 / 全大写**：`+0.08em` 拉开（米其林指南封面风格）
- **正文**：默认 0

---

## 四、空间与几何（Geometry）

### 4.1 圆角（Border Radius）

| Token | 值 | 用途 |
|---|---|---|
| `--r-xs` | 2px | 强调方正的按钮 / 标签 |
| `--r-sm` | 4px | 输入框 / 按钮（比原 6px 更小，更"钢印感"） |
| `--r-md` | 6px | 卡片（原 12px → 6px，方正化） |
| `--r-lg` | 10px | 大卡片 / Modal |
| `--r-pill` | 999px | Chip · 状态徽章 |

> **关键决策**：把圆角从 6/8/12/16 阶梯统一压到 **2/4/6/10**，
> 让整体从"圆润友好"转向"锐利专业"。

### 4.2 间距（Spacing）

业务工具密度优先，保留 4px 基础单位（不变）：

| Token | 值 | 用途 |
|---|---|---|
| `--s-1` | 4px | 紧密内联 |
| `--s-2` | 8px | 行内间距 |
| `--s-3` | 12px | 卡片内文 |
| `--s-4` | 16px | 卡片间 |
| `--s-6` | 24px | 区块间 |
| `--s-8` | 32px | 页面留白 |
| `--s-12` | 48px | 顶部 hero 区 |

### 4.3 阴影（Shadows）

| Token | 值 | 用途 |
|---|---|---|
| `--shadow-1` | `0 1px 2px rgba(0,0,0,0.4)` | hover 微抬升 |
| `--shadow-2` | `0 4px 12px rgba(0,0,0,0.45)` | 卡片默认 |
| `--shadow-3` | `0 8px 24px rgba(0,0,0,0.55)` | Modal / Drawer |
| `--shadow-red` | `0 4px 12px rgba(226,6,19,0.25)` | 品牌红强调按钮 |
| `--shadow-gold` | `0 2px 8px rgba(201,169,97,0.30)` | 星级 KPI |

> 暗主题用更深的纯黑阴影；亮主题用更柔的米色阴影。

---

## 五、品牌元素（Brand Elements）

### 5.1 品牌符号（Logo Mark）

不直接用 Bibendum（米其林轮胎人）形象，而是抽象出"**指南之星 + 双圈环**"符号：

- **外圈**：深色描边圆环，象征"指南"
- **内圈**：米其林红实心圆
- **中心**：3 颗星 ★ ★ ★（米其林三星标志）

应用场景：顶栏左侧品牌区（32px）、Favicon、空状态中心装饰。

### 5.2 星级评价体系（Star Rating）

把"星级"作为 KPI 卡片的语义维度：

- **5 星（金）**：最优 KPI（如"抢单成功率 ≥ 95%"）→ 用 `--star-gold`
- **3 星（银）**：中等 → 灰星
- **1 星（铜）**：需改进 → 灰
- **0 星**：未达基线

### 5.3 装饰元素

- **顶部分隔线**：1px 实线 `--border-strong` + 1px 虚线 `--border` 双线（米其林封面风格）
- **数字强调**：KPI 数值用 Display 字体，字距收紧
- **强调红块**：关键操作按钮左侧 3px 米其林红竖条

---

## 六、组件规范（Components）

### 6.1 Button

```
┌─[ 主按钮 ]──────────┐    ┌─[ 幽灵按钮 ]─────┐    ┌─[ 危险按钮 ]────┐
│ ● 立即扫码登录       │    │   查看详情  →    │    │   删除         │
└─────────────────────┘    └──────────────────┘    └────────────────┘
   bg:--michelin-red          bg:transparent         bg:--err
   fg:#FFFFFF                 fg:--text-0            fg:#FFFFFF
   3px 红竖条在左              hover:bg:--bg-2
   hover:--michelin-red-deep
```

**新增：3px 米其林红竖条**（`::before` 伪元素）— 主按钮和危险按钮独有，强化品牌识别。

### 6.2 Card

- 背景：`--bg-1`
- 描边：1px `--border`
- 圆角：`--r-md` (6px)
- 内边距：18px（不变）
- **新增**：`hover` 时描边变 `--border-strong`，加 `--shadow-1`，**整卡微抬 2px**（transform）
- **新增**：KPI 卡片 `.kpi-card` 在 5 星状态时，左侧 3px 金色竖条

### 6.3 Status Chip / Badge

- 保持 pill 形状（`--r-pill`）
- **新增**：`★` 前缀（金色）表示"已达成星级"的目标
- 错误徽章背景从红改为 `--err/15%` 透明态，文字用 `--err`（避免和品牌红混淆）

### 6.4 Toast

- 4 档严重度维持
- **新增**：critical 级 toast 顶部 2px 金色边（"星级事故"语义）
- 字体：msg 仍用 Body，type 用 Display small caps（更"评级"感）

### 6.5 Drawer / Modal

- 背景 `--bg-1`，遮罩 `rgba(10,11,14,0.65)`（比原色更黑）
- 顶部 3px 米其林红横条（**drawer 专属**）
- 标题用 Display 字体，字号 24px

### 6.6 Nav Item（侧栏）

- 默认文字 `--text-1`
- active 状态：背景 `--bg-2` + 左侧 3px 米其林红（保留原行为）+ **新增**右侧 3 颗星（仅 dashboard 顶级项）
- 图标从纯符号（●▤✓）替换为内联 SVG（详见 §5.1 资源）

---

## 七、动效原则（Motion）

### 7.1 时长（Duration）

| 类型 | 值 | 场景 |
|---|---|---|
| 微交互 | 120ms | 按钮 hover · 输入框 focus |
| 过渡 | 200ms | 卡片 hover · 抽屉滑入 |
| 强调 | 400ms | 页面切换 · 模态弹出 |
| 仪式感 | 800ms | 仅品牌区首屏（5 颗星依次亮起） |

### 7.2 缓动（Easing）

- 默认：`cubic-bezier(0.2, 0, 0, 1)`（Material Design 标准）
- 强调：`cubic-bezier(0.16, 1, 0.3, 1)`（"弹簧"感，仅 toast 弹入）

### 7.3 不做

- 不做"扫光" / "霓虹" / "渐变流动" 装饰动效
- 不做整页交错动画（保留业务工具的"秒开"感）

---

## 八、图标系统（Iconography）

### 8.1 风格

**线性 + 锐角**，1.5px 描边，圆角端点（与字体 Didone 风格匹配）。
替代原有的 emoji（●▤✓⚡）和 unicode 符号。

### 8.2 必备图标（SVG 内联）

| 名称 | 用途 | 路径 |
|---|---|---|
| `icon-dashboard` | 仪表盘 | 矩形仪表盘 + 折线 |
| `icon-tasks` | 任务管理 | 复选框 + 列表 |
| `icon-evals` | 评估明细 | 五角星 |
| `icon-orders` | 抢单记录 | 闪电 |
| `icon-timeline` | 事件中心 | 时钟 |
| `icon-config` | 配置管理 | 齿轮 |
| `icon-logs` | 实时日志 | 终端 |

**资源位置**：`src/xianyu_hunter/web/static/icons/{name}.svg`

---

## 九、可访问性（Accessibility）

- 文字与背景对比度 ≥ WCAG AA（4.5:1）
- 焦点环：2px `--michelin-red` outline，2px offset
- 颜色 + 形状双通道：toast 严重度用图标 + 颜色双重标识
- 暗色 / 亮色主题都通过 WCAG AA 对比度审计

---

## 十、迁移清单（Migration Checklist）

| 优先级 | 文件 | 改动 |
|---|---|---|
| P0 | `static/app.css` | 替换 `:root` token；圆角 / 阴影 / 字体重写 |
| P0 | `templates/base.html` | 顶栏品牌区 Bibendum 符号 + Display 字体 |
| P1 | `templates/dashboard.html` | KPI 卡 5 星语义 + 大字 Display 数值 |
| P1 | `static/icons/*.svg` | 新增 7 个线性 SVG |
| P2 | 其他页面 | 仅依赖 CSS token 变更，自动继承 |

### 验收

- [x] 35 项 UX-11 E2E 全过
- [x] 24 项 P1-4 回归全过
- [ ] 27 项 UX-12 全过（仅验证，未修改 timeline 逻辑）
- [ ] Lighthouse 暗 / 亮主题对比度 ≥ 4.5

---

## 十一、参考与灵感（References）

- **Michelin Guide** 封面与目录：双色（米色 + 红）+ 衬线大字 + 紧凑字距
- **Michelin Red Guide** 星级符号：3 颗 + 1 颗 + 0 颗的差异化用法
- **Magazine Editorial**：H1 用 Didone 衬线，正文用现代无衬线
- **Le Mans / 赛车文化**：黑红高对比 + 锐角几何

---

> 本规范与代码同步维护；任何视觉变更必须先更新本文件再改 CSS。
