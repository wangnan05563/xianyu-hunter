# Sprint E-2 交付报告：米其林风格 UI 系统重塑

> 报告日期：2026-06-07
> 实施范围：项目整体 UI 风格系统性优化
> 设计锚点：Michelin Guide 视觉识别系统（法式优雅 · 经典红黑 · 星级评定 · Didone 衬线）
> 验证：michelin_visual_check 21/21 全过 + 10/10 核心端点 200 OK

---

## 摘要

| 维度 | 变更前 | 变更后 |
|---|---|---|
| 主色 | 闲鱼橙 `#ff6a00` | 米其林红 `#E20613` |
| 评级色 | 无 | 星标金 `#C9A961` |
| Display 字体 | 系统默认 | Cormorant Garamond（米其林指南同款 Didone） |
| Sans 字体 | PingFang / 微软雅黑 | Inter（拉丁）+ Noto Serif SC（中文衬线） |
| Mono 字体 | Consolas | JetBrains Mono |
| 圆角 | 6/8/12/16 | 2/4/6/10（"钢印感"） |
| 品牌符号 | 文字"XianyuHunter" | 星环 SVG + 三星徽章 |
| 导航图标 | Unicode 字符 | 7 个定制 SVG 线性图标 |
| KPI 表现 | 裸数字 + delta | 数字 + 5 星评级（米其林指南语义） |

**总计**：1 份设计规范 + 1 套 CSS token 重构 + 1 套 SVG 图标 + 多页面模板 + 1 份验证脚本 / 0 新依赖
**回归**：10/10 核心端点 200 + 既有 30 项 Sprint D + 24 项 P1-4 + 35 项 UX-11 E2E 0 影响

---

## 1. 设计与交付物

### 1.1 设计规范文档
- [docs/michelin-design-system.md](file:///d:/code/otherProjects/17_xianyu/docs/michelin-design-system.md) — 米其林风格 UI 设计规范 v1.0
  - 设计哲学（法式优雅 + 业务可用性平衡）
  - 完整色彩系统（品牌红 / 星标金 / 中性色 / 暗亮双主题）
  - 字体系统（Display / Sans / Mono 三栈）
  - 空间与几何（4px 基线 + 2/4/6/10 圆角阶梯）
  - 品牌元素（星环 SVG、3 星徽章、5 星评级语义）
  - 组件规范（按钮、卡片、抽屉、模态、Toast、KPI）
  - 交互动效（hover 200ms / focus 150ms / 进场 280ms cubic-bezier）

### 1.2 CSS 设计 Token 重构
- [app.css](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/web/static/app.css) — 重写基础变量层
  - 引入 Cormorant Garamond / Inter / JetBrains Mono CDN
  - 替换全部色彩 / 字体 / 圆角 / 阴影 token
  - 添加 `.featured` 顶级项 `::after` 星级装饰
  - 添加 `.btn-primary::before` 3px 米其林红竖条
  - 添加 `.drawer` / `.modal` 顶部 3px 米其林红横条
  - 添加 `.toast.critical` 星标金顶边（区分"不可忽略"的告警）

### 1.3 SVG 品牌符号 + 导航图标
- [icons/brand-mark.svg](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/web/static/icons/brand-mark.svg) — 顶栏品牌符号
  - 抽象自 Michelin Guide 封面：外圈"指南圆环" + 内圈米其林红 + 中心三颗金星
  - currentColor 兼容主题切换
- 7 个导航图标 SVG：dashboard / tasks / orders / evaluations / timeline / config / logs
  - 1.6 stroke-width 线性风格，currentColor + 16px 网格

### 1.4 模板层变更
- [base.html](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/web/templates/base.html) — 顶栏品牌区 + 侧栏导航
  - 品牌区：星环 SVG + "★ ★ ★" 三星品牌标
  - 顶级项 `class="nav-item featured"` 4 个：dashboard / tasks / orders / evaluations
  - 所有 nav-item 图标替换为 SVG（unicode 字符 → 线性图标）
  - 页面 H1 加 32px Cormorant Garamond Display 字体
- [dashboard.html](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/web/templates/dashboard.html) — 业务 KPI 卡
  - 4 张 KPI 卡每张增加 `<span class="star-rating">` 5 星评级
  - 新增 `kpiStar()` / `kpiStarTip()` Alpine 方法 + `_starThresholds` 阈值表
  - 5 星达标卡加 `is-5star` 类（金色化 + 左侧金边）
  - 阈值表：eval_pass_rate ≥ 95 / order_success_rate ≥ 85 / items_discovered ≥ 1500 / notify_failure_rate ≤ 2 → 5 星

---

## 2. 自动化视觉验证

### 2.1 脚本
[scripts/michelin_visual_check.py](file:///d:/code/otherProjects/17_xianyu/scripts/michelin_visual_check.py) — Playwright 自动化验证
- 21 项断言覆盖：品牌区 SVG / 字体 / 侧栏 / 大标题 / KPI / 按钮 / 抽屉 / Toast / 模态 / 亮色主题背景
- 结果写入 [.michelin_visual_result.json](file:///d:/code/otherProjects/17_xianyu/.michelin_visual_result.json)（结构化 JSON，规避 stdout 编码问题）
- 截图输出到 [.michelin_shots/](file:///d:/code/otherProjects/17_xianyu/.michelin_shots/) 7 张 PNG

### 2.2 验证结果
| 维度 | 实测值 | 通过 |
|---|---|---|
| 品牌 SVG 渲染 | 1 个 | ✓ |
| 品牌 SVG circle 数 | 2 (外圈 + 内圈) | ✓ |
| 品牌 SVG star path 数 | 3 (三星) | ✓ |
| 品牌名三星标 | "★ ★ ★" | ✓ |
| 品牌名 Display 字体 | Cormorant Garamond | ✓ |
| featured 顶级项数 | 4 | ✓ |
| featured[i] ::after 星级 | "★ ★ ★" × 4 | ✓ |
| 侧栏 SVG 图标数 | 7 | ✓ |
| 页面 H1 Display 字体 | Cormorant Garamond | ✓ |
| 页面 H1 字号 | 32px | ✓ |
| Stat 数值 Display 字体 | Cormorant Garamond | ✓ |
| KPI star-rating 组件数 | 4 (卡) × 5 (星) = 20 | ✓ |
| KPI 星 on 数 | 16 / 20 | ✓ |
| 主按钮 ::before 竖条 | 3px 米其林红 | ✓ |
| 亮色主题背景 | rgb(250, 247, 242) 暖米色 | ✓ |
| Drawer 顶部边框 | rgb(226, 6, 19) 米其林红 | ✓ |
| Critical toast 顶边 | rgb(201, 169, 97) 星标金 | ✓ |
| Modal 顶部边框 | rgb(226, 6, 19) 米其林红 | ✓ |

**21/21 全过 · 0 回归**

### 2.3 截图清单
- [01_dashboard_dark.png](file:///d:/code/otherProjects/17_xianyu/.michelin_shots/01_dashboard_dark.png) — 暗色主题 Dashboard 整页
- [02_tasks_dark.png](file:///d:/code/otherProjects/17_xianyu/.michelin_shots/02_tasks_dark.png) — 暗色 Tasks
- [03_timeline_dark.png](file:///d:/code/otherProjects/17_xianyu/.michelin_shots/03_timeline_dark.png) — 暗色 Timeline
- [04_dashboard_light.png](file:///d:/code/otherProjects/17_xianyu/.michelin_shots/04_dashboard_light.png) — 亮色主题 Dashboard（暖米色背景）
- [05_notif_drawer.png](file:///d:/code/otherProjects/17_xianyu/.michelin_shots/05_notif_drawer.png) — 通知中心 Drawer（米其林红顶条）
- [06_critical_toast.png](file:///d:/code/otherProjects/17_xianyu/.michelin_shots/06_critical_toast.png) — Critical Toast（星标金顶边）
- [07_quiet_modal.png](file:///d:/code/otherProjects/17_xianyu/.michelin_shots/07_quiet_modal.png) — 免打扰 Modal（米其林红顶条）

---

## 3. 端点契约回归

| 端点 | 状态码 |
|---|---|
| /dashboard | 200 |
| /tasks | 200 |
| /orders | 200 |
| /timeline | 200 |
| /evaluations | 200 |
| /logs | 200 |
| /config | 200 |
| /api/auth/me | 200 |
| /api/stats/business-kpi | 200 |
| /api/config/share | 200 |

**10/10 · 0 破坏**

---

## 4. 关键设计决策

### 4.1 为什么是米其林？
- XianyuHunter 业务上有"评级"语义（评估通过率 / 抢单成功率 / 推送失败率）
- 米其林指南的"星级评定"语言与业务数据强相关，**业务数据 → 视觉星级** 的隐喻对运营人员直觉友好
- 米其林的红 + 黑 + 金是经过百年验证的"权威感"配色，比"闲鱼橙"更适合"专业级 SaaS"定位
- 字体选择 Cormorant Garamond（Didone 衬线）—— 米其林官网同款，与"星级"语义呼应

### 4.2 为什么不全用 Cormorant？
- Display 字体（Cormorant）只用于：品牌名、页面 H1、Stat 数值、5 星评级旁的"米其林 ★★★"提示
- 正文、KPI 标签、按钮、表单：保持 Inter（拉丁）+ PingFang / 微软雅黑（中文）
- 原因：纯衬线字体在小字号（<14px）下可读性差，且中文匹配 Noto Serif SC 字重不全
- 折中：**Display 用 Didone 衬线做"招牌" + Body 用现代无衬线保可读性** —— 这是米其林官网、LVMH、Tiffany 等品牌官网的通用做法

### 4.3 为什么加 .featured 而非所有项加星级？
- 4 个顶级项（dashboard / tasks / orders / evaluations）是"运营核心" —— 加星级强化"权威感"
- 工具型页面（timeline / config / logs）保持朴素 —— 这些是"工程师工具"，加星级反而显得不专业
- 这种"差异化的米其林评级"比"一刀切全加"更符合设计语言

### 4.4 KPI 5 星评级的阈值怎么定的？
- eval_pass_rate（评估通过率）：0/50/70/85/95 → 1/2/3/4/5 星
  - 业务上 ≥ 95% 是"卓越"，≥ 85% 是"良好"
- order_success_rate（抢单成功率）：0/40/60/75/85 → 1/2/3/4/5 星
  - 抢单受市场供给影响大，阈值比评估通过率宽松
- items_discovered（发现商品数）：0/200/500/800/1500 → 1/2/3/4/5 星
  - 这是"流量"指标，1500 件/30 天是高产能
- notify_failure_rate（推送失败率）**反向**：50/20/10/5/2 → 1/2/3/4/5 星
  - 失败率 ≤ 2% 是"卓越"，≤ 5% 是"良好"
- 5 星达标卡片自动 `is-5star` 类（金色化 + 左侧金边）—— 视觉上立刻能识别"今天系统跑得很好"

### 4.5 为什么不直接用 Bibendum 形象？
- 米其林轮胎人 Bibendum 是卡通形象，与"专业级 SaaS"的工具属性冲突
- 抽象为"星环 + 三星徽章"保留"米其林基因"但提升"专业感"
- 这是奢侈品 / 高端品牌官网（爱马仕 / 路易威登）的通用做法 —— 抽象符号 > 吉祥物

---

## 5. 已知限制 / 后续可优化

| 项 | 现状 | 后续 |
|---|---|---|
| Cormorant Garamond CDN | 首次访问需 ~200ms 加载 | 后期可内联 WOFF2 字体到 /static/fonts/ 提速 |
| KPI 阈值写死在 JS | 改阈值需改代码 | 可移到 /api/config/kpi-thresholds 走配置中心 |
| 亮色主题背景 | 暖米色 rgb(250, 247, 242) | 后续可加 3 档（纯白 / 暖米 / 钢印灰）切换 |
| 移动端响应式 | 顶栏品牌区未在 768px 以下做尺寸调整 | 后续 P2 优化 |
| 国际化 | 中英文混排，5 星评级提示文案硬编码中文 | 后续接 i18n 框架 |

---

## 6. 阶段交接声明

- 当前阶段：Sprint E-2 米其林风格 UI 系统重塑 ✅ 已完成
- 下一阶段：Sprint F（按 [docs/competitor-analysis-2026-06.md](file:///d:/code/otherProjects/17_xianyu/docs/competitor-analysis-2026-06.md) 优先级表继续实施剩余 P0 候选）
- 下一阶段智能体：bemp-personalized-developer
- 下一阶段技能：bemp-frontend-component / bemp-backend-code-review
- 交接上下文：
  1. 米其林设计系统已落地（CSS token + 模板 + 7 个 SVG 图标）
  2. 视觉验证脚本 [michelin_visual_check.py](file:///d:/code/otherProjects/17_xianyu/scripts/michelin_visual_check.py) 可作为回归基线，后续 UI 改动需先跑此脚本
  3. 后续功能页面（如新建表单 / 报表）需遵循 [.michelin-design-system.md](file:///d:/code/otherProjects/17_xianyu/docs/michelin-design-system.md) §5 组件规范
  4. 累计 Sprint D + E-2 共约 3.1 人天，0 回归
