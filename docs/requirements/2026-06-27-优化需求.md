# XianyuHunter 优化需求文档（2026-06-27 版）

> 文档版本：v2.0（增量版）
> 编写日期：2026-06-27
> 调研方法：Sequential Thinking 系统化分析 + firecrawl 全网调研 + 项目源码盘点
> 关联文档：
> - [requirements.md](file:///d:/code/otherProjects/17_xianyu/docs/requirements.md) — 业务需求规格 v1.0
> - [competitor-analysis-2026-06.md](file:///d:/code/otherProjects/17_xianyu/docs/competitor-analysis-2026-06.md) — 竞品分析 v1.0（2026-06-06）
> - [requirement-review.md](file:///d:/code/otherProjects/17_xianyu/docs/requirement-review.md) — 全面需求评审（2026-06-17）
> - [功能盘点与可视化方案.md](file:///d:/code/otherProjects/17_xianyu/docs/功能盘点与可视化方案.md) — 46 配置点盘点
> - [sprint-k-2026-06-26.md](file:///d:/code/otherProjects/17_xianyu/docs/sprint-k-2026-06-26.md) — Sprint K 交付报告
> - [project_memory.md](file:///c:/Users/hspcadmin/.trae-cn/memory/projects/-d-code-otherProjects-17-xianyu/project_memory.md) — 项目硬约束

---

## 0. 摘要：5 个核心判断

1. **ai-goofish-monitor 已于 2026-06-09 被 archive（作者归档）**——这是 XianyuHunter 承接其 12.3k star 用户群的关键时间窗口，应在 1-2 周内完成 Docker 一键部署 + 文档完善，承接迁移流量。
2. **闲鱼"秒没"已成常态，职业贩子脚本抢货**——抢单响应速度是核心战场，建议接入闲鱼 IM WebSocket 协议（cv-cat/XianYuApis 已逆向 sign+base64+Protobuf），将抢单响应从 30s+ 降至 3s 内，与海外 Resell Vault 同档。
3. **鱼小铺服务费 2026-04-18 从 0.6% 暴涨至 1.6%（涨幅 167%）**——卖家利润空间被压缩，利润计算器（含手续费）成为卖家端必备功能，也是 Open Core 变现的关键付费卖点。
4. **小红书内测 C2C 二手交易，转转关停 C2C**——跨平台比价的目标平台需重新评估：转转已无监控价值，小红书是潜在新机会但反爬严格，建议作为 v2.0 候选。
5. **闲鱼贩子识别需求达到顶峰**——V2EX/什么值得买 2026 年用户反馈显示，职业贩子脚本抢货是最大痛点，强化贩子识别引擎（4 维特征 + AI 文案模板化检测）是差异化护城河。

---

## 1. 项目现状盘点（截至 2026-06-27）

### 1.1 已落地能力清单

> 来源：源码目录扫描 + Sprint K 报告 + project_memory.md 硬约束

#### A. 核心业务模块（9 个）

| 模块 | 路径 | 状态 | 关键能力 |
|---|---|---|---|
| Collector | [modules/collector/](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/modules/collector) | ✅ | 搜索/详情/卖家主页/品牌采集 |
| Evaluator | [modules/evaluator.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/modules/evaluator.py) | ✅ | 4 维规则 + AI 深度分析（双轨） |
| Buyer | [modules/buyer.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/modules/buyer.py) | ✅ | 自动下单 + 价格容差 + 订单快照 + 登录失效检测 |
| Scheduler | [modules/scheduler.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/modules/scheduler.py) | ✅ | Cron 持久化 + 实时唤醒 + 任务依赖（F-16） |
| Dedup | [modules/dedup.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/modules/dedup.py) | ✅ | 增量去重 + 实时 inflight 去重 |
| PriceStrategy | [modules/price_strategy.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/modules/price_strategy.py) | ✅ | 4 种策略（max/min/market_ratio/top_n） |
| AntiDetect | [modules/anti_detect.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/modules/anti_detect.py) | ✅ | QPS + 延迟 + 熔断 + stealth v2 |
| Notifier | [modules/notifier/](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/modules/notifier) | ✅ | 7 渠道 + 免打扰时段 |
| Worker | [modules/worker.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/modules/worker.py) | ✅ | TaskWorker._run_loop + 诊断日志 |

#### B. 反爬能力（13 个）

| 模块 | 状态 | 关键能力 |
|---|---|---|
| cookie_rotator | ✅ | 三层管理（identity/session/tracking）+ manual_invalidate 标志 |
| cookie_sync_scheduler | ✅ | 跨进程缓存同步（invalidate_cache） |
| cookie_store | ✅ | JSON + SQLite 双源 + 30s TTL + 跨进程同步 |
| account_rotator | ⚠️ 代码就绪未启用 | 多账号轮换 |
| awsc_spoof | ✅ | 阿里滑块对抗 |
| captcha_handler | ✅ | 验证码处理（暂停+通知，不接打码平台） |
| fingerprint | ✅ | Canvas/WebGL/AudioContext 指纹修复 |
| freq_disguise | ✅ | 频率伪装 |
| login_orchestrator | ✅ | 3 种登录（扫码/浏览器/Cookie 注入）+ start_session_default |
| login_strategy | ✅ | 登录策略 |
| mtop_signer | ✅ | MTOP 协议签名 |
| proxy_pool | ⚠️ 代码就绪未启用 | 代理池 |
| session_health | ✅ | 会话健康检查 |
| token_renewer | ✅ | _m_h5_tk 自动续期 |

#### C. Web 前端页面（13 个，React 18 + TS + Ant Design 5 SPA）

| 页面 | 路径 | 核心组件 |
|---|---|---|
| Dashboard | [pages/Dashboard/](file:///d:/code/otherProjects/17_xianyu/frontend/src/pages/Dashboard) | KPI/趋势/事件流/价格直方图/告警雷达 |
| Tasks | [pages/Tasks/](file:///d:/code/otherProjects/17_xianyu/frontend/src/pages/Tasks) | List/Detail/Editor + Cron 编辑器 + 标签编辑器 |
| Items | [pages/Items/](file:///d:/code/otherProjects/17_xianyu/frontend/src/pages/Items) | 商品列表 + 已售检测 + 标题点击采集 |
| Evaluations | [pages/Evaluations/](file:///d:/code/otherProjects/17_xianyu/frontend/src/pages/Evaluations) | 热力图/价格直方图/趋势 sparkline |
| Orders | [pages/Orders/](file:///d:/code/otherProjects/17_xianyu/frontend/src/pages/Orders) | 订单管理 + 接管 Modal |
| Timeline | [pages/Timeline/](file:///d:/code/otherProjects/17_xianyu/frontend/src/pages/Timeline) | 时间线 + 过滤 |
| Logs | [pages/Logs/](file:///d:/code/otherProjects/17_xianyu/frontend/src/pages/Logs) | 日志 + 错误日志独立页 |
| Config | [pages/Config/](file:///d:/code/otherProjects/17_xianyu/frontend/src/pages/Config) | AI/Notifier/Buyer/Eval/Price/Search/VersionManager |
| AntiCrawl | [pages/AntiCrawl/](file:///d:/code/otherProjects/17_xianyu/frontend/src/pages/AntiCrawl) | Cookie 三层状态/会话管理/代理池 |
| Maintenance | [pages/Maintenance/](file:///d:/code/otherProjects/17_xianyu/frontend/src/pages/Maintenance) | Cleanup + DatabaseAdmin |
| Login | [pages/Login/](file:///d:/code/otherProjects/17_xianyu/frontend/src/pages/Login) | 3 种登录方式（浏览器登录为首要推荐） |
| Onboarding | [pages/Onboarding/](file:///d:/code/otherProjects/17_xianyu/frontend/src/pages/Onboarding) | 引导页 |
| Help | [pages/Help/](file:///d:/code/otherProjects/17_xianyu/frontend/src/pages/Help) | 帮助页 |

#### D. 基础设施（11 个）

| 设施 | 状态 | 关键能力 |
|---|---|---|
| SQLite + 9 表 | ✅ | 含 task_id/seller_id/first_seen/publish_time/created_at 索引 + 复合索引 |
| EventBus | ✅ | asyncio.Queue + SSE |
| LRU 缓存 | ✅ | Buyer/Collector LRU 防内存泄漏 |
| loguru | ✅ | 结构化日志（task_id/stage/item_id/duration） |
| keyring DPAPI | ✅ | Cookie/推送 Key 加密 |
| yaml_config | ✅ | 版本管理 + diff + 导入导出 |
| repository_base | ✅ | 9 个 repository |
| event_bus | ✅ | 事件总线 + 唯一索引（eval.scored） |
| browser_profile | ✅ | 浏览器配置 |
| cookie_runtime_sync | ✅ | 运行时同步 |
| cookie_db | ✅ | SQLite cookie 存储（delete_cookies_by_domain） |

#### E. 测试覆盖

- 截至 2026-06-27：**851+ 测试用例全部通过**（来源：project_memory.md）
- 含单元测试 + E2E 联通测试 + 跨进程缓存同步回归测试

### 1.2 未落地能力清单（截至 2026-06-27）

| 编号 | 能力 | 原计划 | 当前状态 |
|---|---|---|---|
| 1 | Docker 一键部署完善 | requirement-review P1-1 | Dockerfile 已存在，docker-compose.yml 未完善 |
| 2 | 多账号 + 代理池实际启用 | requirement-review P1-2 | 代码就绪但未启用，受单账号约束 |
| 3 | 闲鱼 IM WebSocket 实时监听 | requirement-review P2-5 | 未实现 |
| 4 | 卖家端功能（自动擦亮/AI 客服/利润追踪） | requirement-review P2-1 | 未实现 |
| 5 | 数据导出 CSV/Excel | requirement-review P1-5 | 未实现 |
| 6 | 跨平台比价（转转/小红书） | requirement-review P2-4 | 转转已关停 C2C，小红书待评估 |
| 7 | 图像盗图检测 | 新增 | 未实现 |
| 8 | PWA 移动端优化 | requirement-review P2-8 | 未实现 |
| 9 | 价格历史趋势可视化（折线/对比） | competitor-analysis F-07 | 仅 sparkline |
| 10 | 利润计算器（含鱼小铺 1.6%） | competitor-analysis F-13 | 未实现 |
| 11 | 全局快捷键 + Command Palette | competitor-analysis F-02 | 未实现 |
| 12 | 任务批量操作 | competitor-analysis F-03 | 未实现 |
| 13 | AI 自然语言建任务 | competitor-analysis F-01 | 未实现 |
| 14 | AI 多模态成色评估 | competitor-analysis F-06 | 未实现 |
| 15 | 评估分布直方图 | competitor-analysis O-05 | 未实现 |
| 16 | SSE 断线重连回放 | competitor-analysis O-09 | 未实现 |
| 17 | 变现模式设计 | requirement-review §5 | 未实现 |

---

## 2. 行业与竞品动态（2026 年）

### 2.1 重大行业变化

| 时间 | 事件 | 对本项目影响 |
|---|---|---|
| 2026-04-18 | 鱼小铺服务费从 0.6% → 1.6%，取消 60 元封顶 | 卖家利润压缩，利润计算器成为必备功能 |
| 2026-04 | 闲鱼"秒没"成常态，职业贩子脚本抢货 | 抢单响应速度成为核心战场 |
| 2026-05 | 转转关停 C2C"自由市场"，转向 C2B2C"官方验" | 跨平台比价目标重评估（转转已无价值） |
| 2026-05 | 小红书内测 C2C 二手交易"快捷售卖" | 新监控机会，但反爬严格 |
| 2026-06-09 | ai-goofish-monitor 项目被作者 archive（只读） | 承接其 12.3k star 用户群的时间窗口 |
| 2026 Q2 | 闲鱼投诉解决率仅 6.17%，信任危机加剧 | 贩子识别 + 卖家评估价值凸显 |

### 2.2 竞品矩阵更新（2026-06-27）

#### 国内开源竞品

| 竞品 | 仓库 | 状态 | 核心能力 | 与本项目差距 |
|---|---|---|---|---|
| **ai-goofish-monitor** | Usagi-org | 🔴 已 archive | Playwright + AI 多模态 + 多账号 + 代理池 + 自然语言建任务 + 5 渠道通知 | 本项目缺：AI 多模态/多账号/代理池/自然语言建任务 |
| **xianyu-auto-reply-fix** | 散落 | 🟢 活跃 | 多账号 + AI 自动回复 + 自动发货确认 + 多渠道消息通知 | 本项目缺：卖家端 IM WebSocket 接入 |
| **xianyu-auto-reply** | zhinianboke | 🟢 活跃 | WebSocket 连接闲鱼 + 自动回复 + 自动发货 + 自动擦亮 + 自动评价 | 本项目缺：卖家端完整功能链 |
| **XianYuApis** | cv-cat | 🟢 活跃 | 闲鱼第三方 API 集成库（WebSocket 私信协议逆向 sign+base64+Protobuf） | 可作为本项目 IM 接入的协议参考 |
| **Xianyu-Auto** | bixipeng | 🟢 活跃 | 闲鱼管家（逆向 API）+ 自动化运营 | 本项目缺：卖家端运营功能 |
| **xianyu-monitor-skill** | LENKIN233 | 🟢 活跃 | AI-native 监控机器人 | 新项目，能力待观察 |
| **myfish** | Kaguya233qwq | 🟢 活跃 | Python 异步 Bot 框架 + 闲鱼适配器 + 滑块风控对抗 | 本项目缺：Bot 框架抽象 |
| **XianyuAutoAgent** | shaxiu | 🟡 维护 | 关键词 + 价格 + 钉钉/邮件 | 本项目已领先（4 维评估 + 自动下单） |
| **idlefish_xianyu_spider** | gitcode | 🟡 维护 | 关键词 + 价格 + 钉钉推送 | 本项目已领先 |

#### 国外 SaaS 竞品

| 竞品 | 平台 | 核心能力 | 关键数据 | 启示 |
|---|---|---|---|---|
| **Resell Reserve** | Vinted | Sub-1s 检测 + AutoBuy + AutoCop + Discord 通知 | 3 档订阅 | 检测速度是核心卖点 |
| **Resell Vault** | Vinted | UK #1 Vinted Bot + 3 秒内 autobuy + Cook Group | 订阅制 | IM 实时通知 + 秒级响应是行业标杆 |
| **REPDASH** | eBay/Vinted | 2.4M+ sold listings + seller tracker + Telegram alerts + profit calculator | $19/mo | 卖家追踪 + 利润计算是决策支持标配 |
| **VintiePlus** | Vinted EU | 24/7 监控 + sniper mode + 98% 成功率 | €649k+ 库存追踪 | sniper mode = 抢单模式 |
| **Flipify** | FB Marketplace/Craigslist | 10 秒警报 + Premium 1 分钟刷新 + AI 过滤垃圾 | $5/10 per watchlist | per-watchlist 定价模式 |

#### 国内商业竞品

| 竞品 | 平台 | 核心能力 | 商业模式 |
|---|---|---|---|
| **捡漏王** | 闲鱼 | 5 分钟刷新 + 自动去重 + Excel 导出 | 商业付费 |
| **闲管家** | 闲鱼 | 自动回复 + 订单状态自动回复 + 多账号管理 | 商业付费 |

### 2.3 竞品差距总结（更新版）

#### 本项目独有优势（护城河，应保持）

1. ✅ **唯一具备完整自动抢单能力**（评估→拍下→价格容差→订单快照）的开源工具
2. ✅ **4 维规则评估 + AI 深度分析双轨模式**（竞品多为 AI 黑盒判断）
3. ✅ **React 18 + TS + Ant Design 5 SPA 架构**（其他项目多为 Vue 或纯 HTML）
4. ✅ **Cookie 三层管理 + 跨进程缓存同步**（30s TTL + invalidate_cache）
5. ✅ **AntiCrawl 反爬管理页面 + TokenRenewer 自动续期**
6. ✅ **7 个通知渠道 + 免打扰时段**
7. ✅ **任务依赖（F-16）+ Cron 持久化 + 实时调度器唤醒**
8. ✅ **配置版本管理 + 导入导出**
9. ✅ **商品已售检测 + 评估明细品牌采集**
10. ✅ **LRU 缓存防内存泄漏**
11. ✅ **闲鱼会话失效统一 HTTP 403**（避免触发前端登出逻辑）
12. ✅ **851+ 测试用例**（截至 2026-06-27）

#### 本项目劣势（需补齐）

1. ❌ Docker 一键部署未完善（ai-goofish-monitor 标配）
2. ❌ 多账号 + 代理池代码就绪但未启用
3. ❌ 闲鱼 IM WebSocket 实时监听未接入
4. ❌ 卖家端功能完全缺失（自动擦亮/AI 客服/利润追踪）
5. ❌ 数据导出 CSV/Excel 未实现
6. ❌ 跨平台比价未实现（且转转目标已失效）
7. ❌ 图像盗图检测未实现
8. ❌ PWA 移动端优化未实现
9. ❌ 价格历史趋势可视化（仅 sparkline，缺对比基线）
10. ❌ 利润计算器未实现（且需考虑鱼小铺 1.6%）
11. ❌ 全局快捷键 + Command Palette 未实现
12. ❌ 任务批量操作未实现
13. ❌ AI 自然语言建任务未实现
14. ❌ AI 多模态成色评估未实现
15. ❌ 评估分布直方图未实现
16. ❌ SSE 断线重连回放未实现
17. ❌ 变现模式未设计

---

## 3. 优化需求清单（20 项）

> 每条需求包含：**功能描述 / 用户价值 / 实施路径 / 难度 / 优先级 / 依赖**

### 3.1 P0 优先级（1-2 周内做）

#### O-01-26 闲鱼 IM WebSocket 实时消息接入

- **功能描述**：集成闲鱼 WebSocket 私信协议（sign+base64+Protobuf），实现买家消息/订单状态/上架提醒的秒级接收，替代当前 Buyer 的页面轮询
- **用户价值**：抢单响应从 30s+ → 3s 内，与海外 Resell Vault 同档；同时为卖家端 AI 客服打下基础
- **实施路径**：
  1. 评估 [cv-cat/XianYuApis](https://github.com/cv-cat/XianYuApis) 协议稳定性（1 天）
  2. 集成 Python 库作为消息接收端（2 天）
  3. 在 [buyer.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/modules/buyer.py) 中订阅订单状态变更事件（1 天）
  4. 增加 WebSocket 断线重连 + 协议失效降级到页面轮询（1 天）
- **难度**：L（3-5 人天）
- **依赖**：现有 Cookie 三层管理（已就绪）
- **风险**：协议失效（缓解：保留页面轮询作为降级方案）

#### O-02-26 Docker 一键部署完善

- **功能描述**：完善 [docker-compose.yml](file:///d:/code/otherProjects/17_xianyu/docker-compose.yml)（含 volumes/environment/healthcheck/profiles），承接 ai-goofish-monitor 用户迁移
- **用户价值**：降低部署门槛，NAS/服务器用户友好；抓住 ai-goofish-monitor archive 时间窗口
- **实施路径**：
  1. 完善 docker-compose.yml：web + scheduler 服务分离、volumes 持久化、healthcheck、profiles（dev/prod）
  2. 完善 Dockerfile：多阶段构建（frontend build + backend runtime）
  3. 增加部署文档 `docs/deployment.md`（含 NAS/服务器/本地三种场景）
  4. 增加 `.dockerignore` 完善
- **难度**：S（< 1 人天）
- **依赖**：无
- **关联代码**：[Dockerfile](file:///d:/code/otherProjects/17_xianyu/Dockerfile) + [docker-compose.yml](file:///d:/code/otherProjects/17_xianyu/docker-compose.yml)

#### O-03-26 任务批量操作（F-03）

- **功能描述**：任务列表行首 checkbox + 顶部"批量 [暂停/恢复/删除/启用/禁用] [N] 项"工具条
- **用户价值**：5 个任务从 5 次点击 → 1 次勾选 + 1 次按钮
- **实施路径**：
  1. 后端新增 `/api/tasks/batch-control` 端点（接收 task_ids + action）
  2. 前端 [TaskList.tsx](file:///d:/code/otherProjects/17_xianyu/frontend/src/pages/Tasks/TaskList.tsx) 增加行首 checkbox + 顶部批量工具条
  3. 复用现有 `control_task` 逻辑
- **难度**：S（0.5 人天）
- **依赖**：无

#### O-04-26 全局快捷键 + Command Palette（F-02）

- **功能描述**：
  - `g d/t/o/c/l/a` 跳 Dashboard / Tasks / Orders / Config / Logs / AntiCrawl
  - `?` 打开快捷键说明
  - `Ctrl/Cmd+K` 打开 Command Palette（模糊搜索任务名/订单 ID/配置项/页面）
  - `j/k` 在时间线上下选中
  - `Esc` 关闭任何 Modal/Drawer
- **用户价值**：高频用户每天省 5-10 分钟鼠标移动
- **实施路径**：
  1. 新增 [hooks/useHotkeys.ts](file:///d:/code/otherProjects/17_xianyu/frontend/src/hooks/) 全局快捷键 Hook
  2. 新增 [components/CommandPalette.tsx](file:///d:/code/otherProjects/17_xianyu/frontend/src/components/) 组件（Ant Design Modal + fuzzysort）
  3. 在 [MainLayout.tsx](file:///d:/code/otherProjects/17_xianyu/frontend/src/components/layout/MainLayout.tsx) 注册全局监听
- **难度**：M（2-3 人天）
- **依赖**：无

### 3.2 P1 优先级（1 个月内做）

#### O-05-26 数据导出 CSV/Excel（P1-5）

- **功能描述**：支持将商品/评估/订单/事件数据导出为 CSV/Excel，支持按时间/任务/品类筛选
- **用户价值**：数据分析、记账、复盘
- **实施路径**：
  1. 后端 [api_export.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/web/routes/api_export.py) 已存在，完善 4 个维度的导出端点
  2. 使用 `pandas` 或 `csv` 模块生成文件
  3. 前端各列表页加"导出"按钮（复用 Ant Design Button + Dropdown）
- **难度**：S（< 1 人天）
- **依赖**：无
- **关联**：[api_export.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/web/routes/api_export.py) 已有骨架

#### O-06-26 AI 自然语言建任务（F-01）

- **功能描述**：用户输入"我想买 95 新索尼 A7M4，预算 1.2w 以内，上海本地卖家"，后端调用 LLM 解析为 `{keyword, min_price, max_price, region, exclude_words, ai_prompt}` 并填入任务表单
- **用户价值**：新用户建任务从 5 分钟 → 10 秒，复购率 +50%
- **实施路径**：
  1. 后端新增 `/api/ai/parse-task` 路由（复用 [api_ai.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/web/routes/api_ai.py) 框架）
  2. 设计解析 Prompt（输出 JSON Schema 严格约束）
  3. 前端 [TaskEditor.tsx](file:///d:/code/otherProjects/17_xianyu/frontend/src/pages/Tasks/TaskEditor.tsx) 加"智能建任务"入口（Modal 或 Drawer）
  4. 解析结果填入表单（用户可二次调整）
- **难度**：M（1-2 人天）
- **依赖**：现有 AI 配置 + Budget 监控（已就绪）

#### O-07-26 利润计算器（含鱼小铺 1.6% 手续费）

- **功能描述**：在订单详情/接管 Modal 加"扣完手续费净赚"计算（普通 0.6% / 鱼小铺 1.6%，支持自定义）
- **用户价值**：2026-04-18 鱼小铺服务费上涨后，卖家需重新计算利润；决策时知道"实际赚多少"
- **实施路径**：
  1. 新增 [utils/profitCalculator.ts](file:///d:/code/otherProjects/17_xianyu/frontend/src/utils/) 工具函数
  2. 在 [Orders.tsx](file:///d:/code/otherProjects/17_xianyu/frontend/src/pages/Orders/Orders.tsx) 接管 Modal 加计算区域
  3. 支持输入成本/运费/手续费率，输出净赚
  4. 配置项加 `notifier.fee_rate_default`（默认 0.006，鱼小铺 0.016）
- **难度**：S（0.5 人天）
- **依赖**：无

#### O-08-26 评估命中率/误报率指标（决策支持）

- **功能描述**：Dashboard 加"评估漏斗"（发现→评估→通过→拍下→成交各环节转化率）+ 任务级"阈值严松度"指示器
- **用户价值**：用户改阈值后能立即看到命中率变化，避免盲目调优
- **实施路径**：
  1. 后端 [api_stats.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/web/routes/api_stats.py) 新增 `/api/stats/eval-funnel` 端点
  2. 基于 events 表聚合各 stage 计数（CASE WHEN 合并查询，符合 project_memory 约束）
  3. 前端 Dashboard 加漏斗图（ECharts funnel）
  4. 任务详情加"近 7 天命中率"徽章
- **难度**：M（2-3 人天）
- **依赖**：现有 events 表

#### O-09-26 价格历史趋势对比基线

- **功能描述**：在已有 sparkline 基础上，增加"今日 vs 7d/30d 均价 ±X%"对比基线 + 同关键词价格中位数趋势折线
- **用户价值**：用户能"看图决策"——是不是涨价了/该不该出手
- **实施路径**：
  1. 后端 [api_stats.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/web/routes/api_stats.py) 新增 `/api/stats/price-trend` 端点（返回 today_avg/d7_avg/d30_avg/delta_pct）
  2. 前端 Dashboard [PriceHistogramCard.tsx](file:///d:/code/otherProjects/17_xianyu/frontend/src/pages/Dashboard/components/PriceHistogramCard.tsx) 加红色虚线（今日均价）+ 蓝色虚线（7d 均价）
  3. Tooltip 加"vs 7 日均价 ±X%"
  4. 可选：对接慢慢买 API 获取全网比价基线
- **难度**：M（2-3 人天）
- **依赖**：现有价格直方图组件

#### O-10-26 贩子识别引擎增强（P2-2）

- **功能描述**：基于"卖家主页商品数突增/文案模板化/新注册低活跃/白底官方图"4 维特征训练贩子识别模型，自动标记高风险卖家
- **用户价值**：过滤 80%+ 职业贩子，找回真实个人闲置（V2EX 用户最大痛点）
- **实施路径**：
  1. 在 [evaluator.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/modules/evaluator.py) 4 维评估基础上，增加"贩子识别"子模块
  2. 卖家主页商品数突增：拉取 30 天时序数据，计算斜率
  3. 文案模板化：调用 LLM 检测文案相似度（Batch 模式降低成本）
  4. 白底官方图：调用 OpenCV 检测图片白底比例 > 80%
  5. 评估明细页加"贩子风险分"列
- **难度**：L（3-5 人天）
- **依赖**：O-08-26（命中率指标验证效果）

### 3.3 P2 优先级（2 个月内做）

#### O-11-26 AI 多模态成色评估（F-06）

- **功能描述**：评估通过的商品（4 维评分 ≥ 60）→ 拉取商品图 + 描述 → 调用 GPT-4o Vision / Gemini 二次确认成色真实性，输出"推荐/不推荐 + 理由"
- **用户价值**：高价商品（>5000 元）拍下决策信心 +80%，误拍率 -50%
- **实施路径**：
  1. 在 [api_ai_deep.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/web/routes/api_ai_deep.py) 增加 `/api/ai/vision-eval` 端点
  2. 设计多模态 Prompt（图片 + 文字描述 + 卖家标注成色）
  3. 仅对高分边缘单调用（控制 API 成本，单张图 ~$0.01-0.03）
  4. 前端评估明细页加"AI 成色复核"按钮
- **难度**：L（3-5 人天）
- **依赖**：O-06-26（复用 LLM Key 配置）

#### O-12-26 PWA 移动端优化

- **功能描述**：将现有响应式 Web 升级为 PWA，支持离线访问、推送通知、添加到主屏幕
- **用户价值**：手机端原生体验，无需安装 App
- **实施路径**：
  1. 安装 `vite-plugin-pwa`
  2. 配置 `manifest.json`（含 icons/start_url/display）
  3. 注册 Service Worker（缓存策略：API 走 NetworkFirst，静态资源走 CacheFirst）
  4. 增加"添加到主屏幕"引导
- **难度**：M（2-3 人天）
- **依赖**：现有响应式布局

#### O-13-26 图像盗图检测

- **功能描述**：对接 TinEye / Google Vision API 检测商品图盗用，识别"网上下载的图"vs"实拍图"
- **用户价值**：识别虚假商品（盗图贩子），降低误拍率
- **实施路径**：
  1. 在 [collector/_detail.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/modules/collector/_detail.py) 抓取商品图后调用检测
  2. 对接 TinEye API（付费）或 Google Vision API（$1.5/1000 张）
  3. 评估明细页加"盗图风险"标签
  4. 复用 O-10-26 贩子识别引擎
- **难度**：M（2-3 人天）
- **依赖**：O-10-26

#### O-14-26 SSE 断线重连回放（O-09）

- **功能描述**：SSE 断线重连后，PC 端漏掉的关键告警（err）从 events 表补拉
- **用户价值**：断网 1 小时回来不漏关键告警
- **实施路径**：
  1. SSE 客户端记录 `last_event_id`（localStorage 持久化）
  2. 重连时传 `Last-Event-ID` header
  3. 后端 [sse_stream.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/web/routes/sse_stream.py) 从 events 表查 `id > last_event_id AND level IN ('err','critical')`
  4. 补拉完成后切换到实时流
- **难度**：S（1 人天）
- **依赖**：现有 events 表

#### O-15-26 卖家端功能（自动擦亮/AI 客服）

- **功能描述**：基于闲鱼 WebSocket 私信协议实现自动擦亮（定时刷新商品保持曝光）+ AI 自动回复买家消息（意图分类 + 销售心理学 Prompt）
- **用户价值**：从纯买家工具扩展为买卖双向工具，覆盖闲鱼卖家运营全流程
- **实施路径**：
  1. 复用 O-01-26 IM WebSocket 接入
  2. 新增 `modules/seller/` 模块（自动擦亮/AI 客服/利润追踪）
  3. 前端新增"卖家中心"页面
  4. AI 客服复用 [api_ai_deep.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/web/routes/api_ai_deep.py) 框架
- **难度**：XL（> 7 人天）
- **依赖**：O-01-26

### 3.4 P3 优先级（远期规划）

#### O-16-26 跨平台比价（小红书 C2C）

- **功能描述**：在闲鱼基础上，增加小红书二手交易监控能力（转转已关停 C2C，不接入）
- **用户价值**：扩大监控覆盖面，不依赖单一平台
- **实施路径**：
  1. 调研小红书"快捷售卖"API（需逆向 H5）
  2. 统一数据模型（items/sellers 表跨平台兼容）
  3. 前端任务编辑器加"平台"选择
- **难度**：XL（> 7 人天）
- **依赖**：独立产品规划
- **风险**：高（小红书反爬严格）

#### O-17-26 多账号 + 代理池实际启用

- **功能描述**：启用已就绪的 account_rotator + proxy_pool 代码，支持配置多个闲鱼账号 + 代理 IP 轮换
- **用户价值**：从"1 账号 1 浏览器" → "N 账号 N 浏览器"，7×24 不掉线
- **难度**：XL（> 7 人天）
- **依赖**：突破 requirements.md §2.1 "单账号"约束
- **风险**：高（违反闲鱼 ToS 风险 +10x）

#### O-18-26 Open Core 变现模式

- **功能描述**：以开源免费版引流，Pro 版（¥29/月）提供 AI 深度分析 + 多账号 + 贩子识别等高级功能
- **用户价值**：实现项目可持续运营
- **实施路径**：
  1. 免费版：基础监控 + 价格过滤 + 去重 + 单账号 + 基础通知 + Web Dashboard + 基础卖家评估
  2. Pro 版（¥29/月）：AI 深度多模态分析（O-11-26）+ 多账号 + 贩子识别（O-10-26）+ 全部通知渠道 + 价格行情看板 + 数据导出 + Prompt 在线编辑
  3. Team 版（¥99/月）：SaaS 多租户 + 卖家端功能（O-15-26）+ API 开放平台
- **难度**：XL（> 7 人天）
- **依赖**：P1/P2 功能落地

#### O-19-26 闲鱼开放平台小程序接入

- **功能描述**：通过 [open.goofish.com](https://open.goofish.com) 官方小程序接入，规避反爬风险
- **用户价值**：合规化运行，降低封号风险
- **实施路径**：
  1. 申请闲鱼小程序开发者账号
  2. 配置 isv 容器地址域名
  3. 适配 JS-SDK
- **难度**：L（3-5 人天）
- **依赖**：闲鱼审核通过

#### O-20-26 API 开放平台

- **功能描述**：提供 RESTful API + API Key 管理，允许第三方集成
- **用户价值**：构建生态，B 端变现
- **难度**：L（3-5 人天）
- **依赖**：O-18-26

---

## 4. 优先级总表

| 编号 | 类型 | 标题 | 阶段 | 工时 | 依赖 |
|---|---|---|---|---|---|
| O-01-26 | 新增 | 闲鱼 IM WebSocket 接入 | P0 | 3-5 人天 | Cookie 三层管理 |
| O-02-26 | 优化 | Docker 一键部署完善 | P0 | < 1 人天 | 无 |
| O-03-26 | 新增 | 任务批量操作 | P0 | 0.5 人天 | 无 |
| O-04-26 | 新增 | 全局快捷键 + Command Palette | P0 | 2-3 人天 | 无 |
| O-05-26 | 新增 | 数据导出 CSV/Excel | P1 | < 1 人天 | 无 |
| O-06-26 | 新增 | AI 自然语言建任务 | P1 | 1-2 人天 | AI 配置 |
| O-07-26 | 新增 | 利润计算器（含 1.6% 手续费） | P1 | 0.5 人天 | 无 |
| O-08-26 | 新增 | 评估命中率/误报率指标 | P1 | 2-3 人天 | events 表 |
| O-09-26 | 优化 | 价格历史趋势对比基线 | P1 | 2-3 人天 | 价格直方图 |
| O-10-26 | 新增 | 贩子识别引擎增强 | P1 | 3-5 人天 | O-08-26 |
| O-11-26 | 新增 | AI 多模态成色评估 | P2 | 3-5 人天 | O-06-26 |
| O-12-26 | 优化 | PWA 移动端优化 | P2 | 2-3 人天 | 响应式布局 |
| O-13-26 | 新增 | 图像盗图检测 | P2 | 2-3 人天 | O-10-26 |
| O-14-26 | 优化 | SSE 断线重连回放 | P2 | 1 人天 | events 表 |
| O-15-26 | 新增 | 卖家端功能 | P2 | > 7 人天 | O-01-26 |
| O-16-26 | 新增 | 跨平台比价（小红书） | P3 | > 7 人天 | 独立规划 |
| O-17-26 | 新增 | 多账号 + 代理池启用 | P3 | > 7 人天 | 突破单账号约束 |
| O-18-26 | 新增 | Open Core 变现模式 | P3 | > 7 人天 | P1/P2 落地 |
| O-19-26 | 新增 | 闲鱼小程序接入 | P3 | 3-5 人天 | 审核通过 |
| O-20-26 | 新增 | API 开放平台 | P3 | 3-5 人天 | O-18-26 |

**汇总**：
- P0：4 项 / ~7-10 人天
- P1：6 项 / ~10-15 人天
- P2：5 项 / ~12-18 人天
- P3：5 项 / ~25+ 人天（独立规划）

---

## 5. 变现路径设计（Open Core 模式）

### 5.1 推荐变现模式：Open Core

| 模式 | 适用场景 | 优势 | 劣势 | 推荐度 |
|---|---|---|---|---|
| **Open Core**（推荐） | 核心开源，高级功能付费 | 社区引流 + 付费转化 | 需明确免费/付费边界 | ★★★★★ |
| SaaS 订阅 | 云端多租户服务 | 经常性收入 | 运营成本高、合规风险 | ★★★☆☆ |
| 一次性买断 | 桌面软件授权 | 简单直接 | 收入不可持续 | ★★☆☆☆ |
| API 计量收费 | 开放平台 | B 端变现 | 需要生态规模 | ★★☆☆☆ |

### 5.2 分版功能矩阵

| 功能 | 免费版（开源） | Pro 版（¥29/月） | Team 版（¥99/月） |
|---|---|---|---|
| 基础监控 + 价格过滤 + 去重 | ✅ | ✅ | ✅ |
| 单账号 + 基础通知（3 渠道） | ✅ | ✅ | ✅ |
| Web Dashboard + 任务管理 | ✅ | ✅ | ✅ |
| 4 维规则评估 | ✅ | ✅ | ✅ |
| **AI 深度多模态分析**（O-11-26） | ❌ | ✅ | ✅ |
| **贩子识别引擎**（O-10-26） | ❌ | ✅ | ✅ |
| **全部通知渠道**（7 渠道） | ❌（限 3 渠道） | ✅ | ✅ |
| **价格行情看板**（O-09-26） | ❌ | ✅ | ✅ |
| **数据导出**（O-05-26） | ❌ | ✅ | ✅ |
| **Prompt 在线编辑** | ❌ | ✅ | ✅ |
| **多账号 + 代理池**（O-17-26） | ❌ | ❌ | ✅ |
| **卖家端功能**（O-15-26） | ❌ | ❌ | ✅ |
| **API 开放平台**（O-20-26） | ❌ | ❌ | ✅ |
| 优先技术支持 | ❌ | ❌ | ✅ |

### 5.3 首批付费功能优先级（按变现关联度 × 实现可行性）

1. **O-10-26 贩子识别引擎** — 直击用户最大痛点，差异化卖点
2. **O-11-26 AI 深度多模态分析** — 竞品验证需求强烈，核心付费卖点
3. **O-09-26 价格行情看板** — 数据增值，提升付费感知
4. **O-15-26 卖家端功能** — 扩大用户群体（从买家到买卖双向）
5. **O-17-26 多账号 + 代理池** — 高频用户刚需，技术壁垒高

---

## 6. 实施路线图（Sprint L-N）

### Sprint L（建议 2 周内，~7-10 人天）

**主题：承接 ai-goofish-monitor 用户迁移 + 高频用户效率提升**

- O-02-26 Docker 一键部署完善（< 1 人天）
- O-03-26 任务批量操作（0.5 人天）
- O-04-26 全局快捷键 + Command Palette（2-3 人天）
- O-01-26 闲鱼 IM WebSocket 接入（3-5 人天，最难项）

**交付物**：
- 代码 + smoke test
- Playwright 截图（前后对比）
- 部署文档 `docs/deployment.md`
- 更新本文档 §4 状态栏

### Sprint M（建议 1 个月内，~10-15 人天）

**主题：补齐竞品差距 + 决策支持**

- O-05-26 数据导出 CSV/Excel（< 1 人天）
- O-06-26 AI 自然语言建任务（1-2 人天）
- O-07-26 利润计算器（0.5 人天）
- O-08-26 评估命中率/误报率指标（2-3 人天）
- O-09-26 价格历史趋势对比基线（2-3 人天）
- O-10-26 贩子识别引擎增强（3-5 人天）

### Sprint N（建议 2 个月内，~12-18 人天）

**主题：差异化竞争力 + 卖家端扩展**

- O-11-26 AI 多模态成色评估（3-5 人天）
- O-12-26 PWA 移动端优化（2-3 人天）
- O-13-26 图像盗图检测（2-3 人天）
- O-14-26 SSE 断线重连回放（1 人天）
- O-15-26 卖家端功能（> 7 人天，可拆分到 Sprint O）

### 远期（v2.0 候选）

- O-16-26 跨平台比价（小红书）
- O-17-26 多账号 + 代理池启用
- O-18-26 Open Core 变现模式
- O-19-26 闲鱼小程序接入
- O-20-26 API 开放平台

---

## 7. 风险与依赖

| 风险 | 等级 | 缓解措施 |
|---|---|---|
| 闲鱼 IM WebSocket 协议失效 | 高 | 保留页面轮询作为降级方案；监控 cv-cat/XianYuApis 仓库更新 |
| 闲鱼改版导致选择器失效 | 高 | 选择器集中管理 + 异常告警 + O-08-26 命中率指标提前发现 |
| LLM API 成本失控 | 中 | F-01/F-06/O-10-26/O-11-26 加 usage 监控（已有）+ 单用户限流 |
| 多账号扩展违反 ToS | 高 | v2.0 候选需用户明确确认风险；建议 Pro 版限额 3 账号 |
| 小红书反爬严格 | 高 | O-16-26 远期规划，先调研再实施 |
| Docker 部署后 cookie 持久化问题 | 中 | volumes 正确挂载 `data/browser_data/` + `data/cookies.json` |
| Open Core 模式被白嫖 | 低 | Pro 版功能需服务端校验（license key），核心算法服务端运行 |

---

## 8. 附录：调研来源

### 8.1 项目文档集（已引用）

- [requirements.md](file:///d:/code/otherProjects/17_xianyu/docs/requirements.md) — 业务需求规格 v1.0
- [competitor-analysis-2026-06.md](file:///d:/code/otherProjects/17_xianyu/docs/competitor-analysis-2026-06.md) — 竞品分析 v1.0
- [requirement-review.md](file:///d:/code/otherProjects/17_xianyu/docs/requirement-review.md) — 全面需求评审
- [功能盘点与可视化方案.md](file:///d:/code/otherProjects/17_xianyu/docs/功能盘点与可视化方案.md) — 46 配置点盘点
- [sprint-k-2026-06-26.md](file:///d:/code/otherProjects/17_xianyu/docs/sprint-k-2026-06-26.md) — Sprint K 交付报告
- [project_memory.md](file:///c:/Users/hspcadmin/.trae-cn/memory/projects/-d-code-otherProjects-17-xianyu/project_memory.md) — 项目硬约束

### 8.2 firecrawl 调研来源

- [ai-goofish-monitor GitHub](https://github.com/Usagi-org/ai-goofish-monitor) — 主要竞品（已 archive 2026-06-09）
- [cv-cat/XianYuApis](https://github.com/cv-cat/XianYuApis) — 闲鱼第三方 API 集成库（WebSocket 私信协议逆向）
- [zhinianboke/xianyu-auto-reply](https://github.com/zhinianboke/xianyu-auto-reply) — 闲鱼自动回复系统
- [bixipeng/Xianyu-Auto](https://github.com/bixipeng/Xianyu-Auto) — 闲鱼管家
- [LENKIN233/xianyu-monitor-skill](https://github.com/LENKIN233/xianyu-monitor-skill) — AI-native 监控机器人
- [Kaguya233qwq/myfish](https://github.com/Kaguya233qwq/myfish) — Python 异步 Bot 框架
- [Resell Reserve](https://www.resellreserve.co.uk/alternatives/vinted-bot) — Vinted 监控 SaaS
- [Resell Vault](https://resellvault.co.uk/) — UK #1 Vinted Bot
- [闲鱼开放平台](https://open.goofish.com/doc/quick-start.html) — 小程序官方接入
- [V2EX 闲鱼监控脚本讨论](https://www.v2ex.com/t/1013920)
- [V2EX 闲鱼助手工具实现](https://v2ex.com/t/1100337)
- [什么值得买：2026 闲鱼秒没](https://post.smzdm.com/p/a035ze7w)
- [21财经：二手江湖变天](https://www.21jingji.com/article/20250928/herald/33a739fbc51123eb96d70af13e0bf6a2.html)
- [钛媒体：转转离场 C2C，小红书入局](https://www.tmtpost.com/7726308.html)
- [慢慢买 - 全网比价](https://tool.manmanbuy.com/historylowest.aspx)
- [TinEye 反向图像搜索](https://tineye.com/)

---

*文档结束 — 后续每 Sprint 完成后回填 §4 状态栏*

## 9. 阶段交接声明

- 当前阶段：优化需求文档编制 ✅ 已完成
- 下一阶段：Sprint L 实施
- 下一阶段智能体：general_purpose_task / code-reviewer
- 下一阶段技能：writing-plans / executing-plans / test-driven-development
- 交接上下文：本文档 §3.1 P0 项 4 个（O-01-26 ~ O-04-26）为 Sprint L 必须交付项，其中 O-01-26（IM WebSocket）难度最高，建议先用 1 天评估 cv-cat/XianYuApis 协议稳定性再决策实施路径。所有 P0 项均不破坏 project_memory.md 中的硬约束（Cookie 管理/认证/403 等）。
