# XianyuHunter 市场竞品分析与体验优化建议

> 报告版本：v1.0
> 报告日期：2026-06-06
> 调研范围：闲鱼/Goofish 自动捡漏赛道 + 国际二手平台监控赛道 + 业内最佳实践对照
> 评估方法：现有功能梳理 → 竞品横评 → 差异化分析 → 新增功能与体验优化建议
> 受众：产品 / 前端 / 后端 / 用户本人

---

## 摘要：5 个核心判断

1. **XianyuHunter 在"自动下单 + 推送确认 + 风控熔断"这条链路上已领先所有开源竞品**——`ai-goofish-monitor`/`shaxiu/XianyuAutoAgent`/`idlefish_xianyu_spider-crawler-sender` 均止步于"分析+推送"，未做"拍下"。这构成了核心差异化护城河，应在产品对外介绍中重点突出。
2. **最大的能力差距是"AI 多模态评估"**——`ai-goofish-monitor` 已用 GPT-4o / Gemini 看图识成色、识卖家。XianyuHunter 的 4 维规则评估虽稳定但"不智能"，建议以"AI 评分 + 规则拦截"双轨模式补齐。
3. **自然语言创建任务是所有头部竞品的"惊艳入口"**——`ai-goofish-monitor` 的"我想买 95 新 A7M4，预算 1.2w 以内"一键生成任务；这是用户认知成本最低的入口。
4. **缺失的"键盘流 / 批量管理 / 数据迁移"3 项能力，在国际监控工具（Resell Reserve / REPDASH / VintiePlus）里是标配**。高频用户的"复制-粘贴式"操作流被严重低估。
5. **数据可视化停留在"分布"层，缺"时间趋势"+"对比基线"**——REPDASH 的"竞品卖家追踪"、VintiePlus 的"deals feed"提示我们：监控工具的下一个竞争点是"决策支持"而不是"机械通知"。

---

## 1. XianyuHunter 现有功能全景

### 1.1 核心能力（基于 requirements.md / design.md）

| 模块 | 现状能力 | 优先级 |
|---|---|---|
| 任务管理 | 创建/启停/编辑/删除/复制、间隔调度、4 种执行模式（auto/semi/confirm/notify） | P0 已完成 |
| 数据采集 | 关键词搜索、商品详情、卖家主页、卖家历史发布、增量去重 | P0/P1 |
| 价格策略 | 硬性价格上限、低于市场参考价 ×N、TopN 低价、价格异常检测、多策略叠加 | P0/P1/P2 |
| 卖家评估 | 4 维：职业度（5 子项）+ 信用（5 子项）+ 纠纷/黑名单（2 子项）+ 价格异常（3 子项） | P0 |
| 自动下单 | 进入详情 → "我想要/立即购买" → 拍下不支付 → 订单快照 + 截图 | P0 |
| 通知 | Server酱 / PushPlus / Bark 3 渠道并发 + 指数退避重试 | P0 |
| 反检测 | Playwright 持久化上下文、UA/Canvas/WebGL 指纹修复、QPS 控制、行为模拟、失败熔断 | P0/P1 |
| 配置 | 5 个 Tab：搜索 / 价格 / 评估 / 通知 / 抢单 + YAML + pydantic 校验 | P0 |
| 安全 | Cookie / 推送 Key 走 Windows DPAPI keyring 加密 | P0 |
| Web UI | FastAPI + Jinja2 + htmx + Alpine.js + Tailwind（CDN），9 个页面 + 1 个引导 | P0 |
| CLI | Typer 框架：add / list / run / pause / resume / stop / status / config-show | P0 |
| 可观测性 | loguru 结构化日志（task_id / stage / item_id / duration）、SSE 事件流 | P0 |

### 1.2 已落地的 UX 优化（Sprint A + Sprint B = 8 项）

| 编号 | 优化项 | 阶段 |
|---|---|---|
| UX-01 | 顶栏状态 chip 可下钻 | Sprint A P0 ✅ |
| UX-02 | 抢单记录"商品标题"列 | Sprint A P0 ✅ |
| UX-04 | 任务复制后"副本"标识 | Sprint A P0 ✅ |
| UX-05 | 关键错误持久化到通知中心 | Sprint A P0 ✅ |
| UX-06 | inline 二次确认（替代 confirm） | Sprint A P0 ✅ |
| UX-03 | 价格直方图 + P25/P50/P75 分位数 + 价格对比 | Sprint B ✅ |
| UX-07 | Dashboard 24h sparkline 趋势小图 | Sprint B ✅ |
| UX-13 | 配置字段级回滚（每字段 [↺ 恢复默认] + 全部重置） | Sprint B ✅ |
| P1-5 | 移动端响应式（≤900px 断点 + 抽屉 + 7 张验证截图） | Sprint A ✅ |
| P1-1~4 | 配置 diff/回滚、接管 Modal + 倒计时、任务分页、通知中心 | Sprint A ✅ |

### 1.3 待落地项（来自 UX 评审 P2）

| 编号 | 优化项 | 备注 |
|---|---|---|
| P2-1 | 全局快捷键 + Command Palette（Ctrl+K） | Alpine 准备就绪 |
| P2-2 | 时间趋势可视化（已部分落地 sparkline） | 缺折线 / 对比 / 下钻 |
| P2-3 | 配置导入导出/分享 | 仅有"备份历史"回滚 |
| P2-4 | 日志搜索/标记/导出 | 当前仅"清空"按钮 |
| P2-5 | 任务批量操作 | 5 个任务得 5 次点击 |
| P2-6 | 评估分布直方图 | 看不出阈值严不严 |
| P2-7 | 任务详情"运行历史"Tab | 当前跳到评估明细 |
| P2-8 | 时间线严重度过滤 | 已有 info/warn/err 但页面无切换 |
| P2-9 | 通知免打扰时段 | requirements.md 隐含 H-5 |

### 1.4 测试覆盖

- 148 个单元测试 + 4 个 E2E 联通测试，全部通过（来源：README.md）
- Sprint A 5 项 P0 + Sprint B 3 项 + P1-1~5 + P1-5 移动端均有 smoke test

---

## 2. 竞品调研

### 2.1 国内开源竞品矩阵

| 竞品 | 仓库 | Star | 核心能力 | 自动下单 | AI 多模态 | 自然语言建任务 | Web UI | 多账号 |
|---|---|---|---|---|---|---|---|---|
| **ai-goofish-monitor** | Usagi-org/ai-goofish-monitor | ~12.3k | 关键词 + 价格 + 卖家画像 + AI 成色 | ❌ | ✅ GPT-4o / Gemini | ✅ | ✅ | ✅ + 代理池 |
| **XianyuAutoAgent** | shaxiu/XianyuAutoAgent | ~1.5k | 关键词 + 价格 + 卖家筛选 + 钉钉/邮件 | ❌ | ❌ | ❌ | ❌ | ❌ |
| **idlefish_xianyu_spider** | gitcode | ~0.5k | 关键词 + 价格 + 钉钉推送 | ❌ | ❌ | ❌ | ❌ | ❌ |
| **XianyuHunter（本项目）** | 本地 | 内部 | 同上 + **自动下单** + 4维评估 + 推送确认 + Web UI + 移动端 | ✅ | ❌（4维规则） | ❌ | ✅ | ❌ |
| **OpenClaw+Qwen3.5-9B** | 二开 | 散落 | 关键词 + 询价话术 + 本地大模型 | ❌ | ✅ Qwen3.5-9B | 半自动 | ❌ | ❌ |

### 2.2 国外二手监控 SaaS 矩阵

| 竞品 | 平台 | 核心能力 | 关键数据 |
|---|---|---|---|
| **Resell Reserve** | Vinted | Sub-1s 检测、AutoBuy、AutoCop、Discord 通知、50+ 教程 | 3 档订阅制 |
| **Flipify** | Facebook Marketplace / Craigslist | 10 秒警报、Premium 1 分钟刷新、AI 过滤垃圾、per-watchlist 定价 | $5/10 per watchlist |
| **REPDASH** | eBay / Vinted | 2.4M+ sold listings、seller tracker、Telegram alerts、profit calculator | $19/mo |
| **VintiePlus** | Vinted EU | 24/7 监控、sniper mode、98% 成功率、€649k+ 库存追踪 | 订阅制 |
| **Marketplace Monitor** | iOS 跨 FB/OfferUp/eBay/Craigslist/Gumtree | 个人开发者、$5/月基础版 | iOS App |
| **捡漏王**（国内商业软件） | 闲鱼 | 5 分钟刷新、自动去重、Excel 导出 | 商业付费 |

### 2.3 头部竞品深度拆解：ai-goofish-monitor

#### 2.3.1 核心功能亮点

| 模块 | 实现细节 | 用户感知 |
|---|---|---|
| **自然语言建任务** | 描述"95 新 A7M4，1.2w 以内，快门 < 5000，上海" → AI 解析为关键词 + 价格 + 评估规则 | 零门槛、5 秒建任务 |
| **多模态 AI 评估** | GPT-4o 同时分析商品图（看成色）+ 文字（看描述真实性）+ 卖家画像 | 识破"九成新"实为翻新机 |
| **实时流式处理** | 发现→AI→推送秒级响应，无批处理 | 抢单窗口期 < 60s 内必到 |
| **多账号+代理池** | 内置多账号切换 + 代理 IP 轮换，单账号被风控自动切换 | 7×24 不掉线 |
| **Web UI** | 任务管理 / AI Prompt 在线编辑 / 日志实时流 / 结果筛选 | 不需命令行 |
| **通知** | ntfy.sh / 企业微信 / Bark / Telegram / Webhook | 5 渠道 |
| **部署** | Docker 一键启动 + login.py 扫码 + 状态持久化 | 装机 5 分钟 |

#### 2.3.2 短板（XianyuHunter 可对比的优势）

| 短板 | 原因 | XianyuHunter 现状 |
|---|---|---|
| ❌ **不做自动下单** | 仅做"分析+推送"由用户拍 | ✅ 已实现 Buyer 模块 |
| ❌ **不支持半自动 confirm** | 评估通过即推送，无二次确认 | ✅ 有 `confirm` 模式 |
| ❌ **无支付前价格容差** | 推送后用户点链接直接拍，错过改价 | ✅ Buyer 已校验价格 |
| ❌ **无 4 维规则评估** | 完全依赖 AI 评估，结果不可复现 | ✅ 4 维规则 + 拦截阈值 |
| ❌ **无风控熔断** | AI 不稳定时无法熔断 | ✅ AntiDetect 失败熔断 |
| ❌ **无订单快照** | 推送后无结构化记录 | ✅ orders 表 + 截图 |
| ❌ **无本地 Web UI 永久化** | 容器重启后 cookie 需重扫 | ✅ 持久化浏览器数据目录 |
| ❌ **无配置 diff/回滚** | Prompt 在线编辑无版本管理 | ✅ YAML + .bak + diff 预览 |
| ❌ **无移动端响应式** | 纯 PC Web UI | ✅ ≤900px 抽屉式 + 7 张验证截图 |
| ❌ **无通知中心** | 推送全在手机端，PC 端无汇总 | ✅ 双 Tab 通知中心 |

#### 2.3.3 XianyuHunter 借鉴清单

1. **自然语言建任务**：调用 LLM 把"95 新 A7M4"→ `{keyword:"a7m4", min_price:10000, max_price:13000, ai_prompt:"重点识别成色真实度..."}`
2. **多模态商品成色评估**：评估通过后调用 GPT-4o vision 二次确认（仅对高分边缘单使用，控制 API 成本）
3. **多账号 + 代理池**（如未来突破单账号限制）：v2.0 候选
4. **ntfy.sh / Telegram 通知**（如用户海外使用）：扩展通知渠道

### 2.4 国外 SaaS 模式深度拆解

| 维度 | Resell Reserve | REPDASH | VintiePlus | 启示 |
|---|---|---|---|---|
| 检测速度 | Sub-1s | 实时 | Sub-1s | 卖方市场对"快"的定义是秒级；买方市场可放宽到分钟 |
| 决策支持 | AI 工具 + 教程 | sold data + 卖家追踪 + 利润计算 | sniper mode + 实时价 | "决策"是 next level |
| 订阅模式 | 3 档（Basic/Advanced/Ultimate） | $19/mo | 订阅 | 个人工具不必 SaaS 化 |
| 通知渠道 | Discord | Telegram | 应用内 | 国内应优先微信（已实现） |
| 数据可视化 | 中央 Hub 监控页 | 卖家收入 + 类目穿透 + 利润 | 实时 deal feed | 趋势+对比+下钻是核心 |

---

## 3. 现有系统客户体验痛点（基于 ux-review-2026-06.md + 系统走查）

### 3.1 高严重度（高频用户每天损失 ≥ 5 分钟）

| # | 痛点 | 现状 | 根因 |
|---|---|---|---|
| P-A1 | **键盘流缺失**：每天 50+ 次点击（暂停/恢复/巡检） | 无全局快捷键 | Alpine 准备就绪但未注册 |
| P-A2 | **批量操作缺失**：5 个任务需 5 次点击 | 行级单点按钮 | 缺 `batch-control` API |
| P-A3 | **配置无法迁移**：换电脑 = 重新配 | 无导入导出 | 仅有"备份历史" |
| P-A4 | **日志无法检索**：1000+ 行只能翻 | 无搜索/标记 | `logs.html` 仅"清空" |
| P-A5 | **任务"沉默"无感知**：3 天没结果的不知道 | 无运行历史 | `tasks/detail.html` 缺 Tab |
| P-A6 | **决策支持弱**：改了阈值不知道对错 | 无效果追踪 | 缺"评估命中率/误报率"指标 |

### 3.2 中严重度（每周遇到 1-2 次）

| # | 痛点 | 现状 | 根因 |
|---|---|---|---|
| P-B1 | Toast 3.5s 自动消失，关键错误来不及截图 | 固定时长 | 缺"严重度分级时长" |
| P-B2 | 错误无"复制详情/查看日志"快捷操作 | 单纯文本 | 缺"展开 payload"按钮 |
| P-B3 | 评估分布看不出阈值严不严 | 列表无图 | 缺分布直方图 |
| P-B4 | 抢单记录缺"商品标题" | 已修复（Sprint A UX-02） | ✅ |
| P-B5 | 时间线无法按严重度过滤 | 过滤维度不全 | 缺 levels= 参数 |
| P-B6 | 接管 Modal 完成后需手动关闭 | 无限等待 | 缺 setTimeout 自动关 |
| P-B7 | 配置保存后丢失滚动位置 | `location.reload()` | 缺局部刷新 |
| P-B8 | SSE 标签页隐藏时断流 | 30s 重连漏消息 | 缺重连时回放 |
| P-B9 | 凌晨推送吵醒用户 | 无免打扰时段 | 缺"勿扰模式"配置 |

### 3.3 国际化与差异化差距

| # | 差距 | 竞品做法 | 影响 |
|---|---|---|---|
| P-C1 | **无自然语言建任务** | ai-goofish-monitor 标配 | 新用户认知成本高 |
| P-C2 | **无 AI 成色评估** | ai-goofish-monitor 标配 | 高价商品不敢拍 |
| P-C3 | **无多账号/代理池** | ai-goofish-monitor 标配 | 7×24 易掉线 |
| P-C4 | **无卖家历史价格趋势** | REPDASH 标配 | 不会判断"是不是涨价了" |
| P-C5 | **无利润计算器** | REPDASH 标配 | 不会算"扣完手续费赚多少" |

---

## 4. 新增功能建议（按 P0/P1/P2 排序）

> 每条建议包含：**功能描述 / 技术可行性 / 预期用户价值 / 优先级**

### 4.1 P0 优先级（1-2 周内做）

#### F-01 AI 自然语言创建任务
- **功能描述**：用户输入"我想买 95 新索尼 A7M4，预算 1.2w 以内，上海本地卖家"，后端调用 LLM 解析为 `{keyword, min_price, max_price, region, exclude_words, ai_prompt}` 并填入任务表单（可二次调整）
- **技术可行性**：⭐⭐⭐⭐⭐ — LLM API 成熟（OpenAI/DeepSeek/Qwen 任选），后端加 1 个 `/api/ai/parse-task` 路由 + 前端 1 个"智能建任务"按钮，1-2 人天
- **预期用户价值**：新用户建任务从 5 分钟 → 10 秒，复购率 +50%
- **依赖**：用户已有 LLM API Key（可与现有推送 Key 一起从 keyring 读取）

#### F-02 全局快捷键 + Command Palette
- **功能描述**：
  - `g d/t/o/c/l` 跳 Dashboard / Tasks / Orders / Config / Logs
  - `?` 打开快捷键说明
  - `Ctrl/Cmd+K` 打开 Command Palette（模糊搜索任务名/订单ID/配置项/页面）
  - `j/k` 在时间线上下选中
  - `Esc` 关闭任何 Modal/Drawer
- **技术可行性**：⭐⭐⭐⭐⭐ — Alpine `x-on:keydown.window` 监听 + 路由白名单，参考 [ux-review §2.8](file:///d:/code/otherProjects/17_xianyu/docs/ux-review-2026-06.md#L144-L154) 行业基线，2-3 人天
- **预期用户价值**：高频用户每天省 5-10 分钟鼠标移动
- **依赖**：无

#### F-03 任务批量操作
- **功能描述**：行首 checkbox + 顶部"批量 [暂停/恢复/删除/启用/禁用] [N] 项"工具条
- **技术可行性**：⭐⭐⭐⭐⭐ — 复用 htmx 批量 POST `/api/tasks/batch-control`，前端 0.5 人天
- **预期用户价值**：5 个任务从 5 次点击 → 1 次勾选 + 1 次按钮
- **依赖**：无

#### F-04 配置导入/导出/分享
- **功能描述**：
  - 导出：下载 `xh-config-{ts}.json`（含版本号、敏感字段脱敏）
  - 导入：上传 → diff 预览 → 确认覆盖
  - 分享：生成可复制的配置摘要（不含 token）
- **技术可行性**：⭐⭐⭐⭐ — 前端 `Blob+URL.createObjectURL` + 复用现有 diff Modal，1-2 人天
- **预期用户价值**：换电脑/重装系统从 30 分钟配置 → 1 分钟导入
- **依赖**：与现有"备份历史"共享数据格式

#### F-05 关键错误持久化 + 操作
- **功能描述**（承接 Sprint A UX-05 扩展）：
  - 错误 toast 自动"升级"为通知中心记录
  - 通知中心每条错误含"复制详情 / 查看日志 / 立即重试"按钮
  - 错误级别 3 档：warn（普通）/ err（持久化）/ critical（不自动消失）
- **技术可行性**：⭐⭐⭐⭐ — 复用现有 `/api/notifications`，加 payload JSON 字段，1 人天
- **预期用户价值**：关键告警不丢失、可追溯、可一键重试
- **依赖**：Sprint A UX-05 已落地

### 4.2 P1 优先级（1 个月内做）

#### F-06 AI 多模态商品成色评估（v1.0 核心承诺）
- **功能描述**：评估通过的商品（4维评分 ≥ 60）→ 拉取商品图 + 描述 → 调用 GPT-4o/Gemini 二次确认成色真实性，输出"推荐/不推荐 + 理由"
- **技术可行性**：⭐⭐⭐⭐ — OpenAI/Gemini API 已成熟，1 张商品图 ~$0.01-0.03 成本，3-5 人天
- **预期用户价值**：高价商品（>5000 元）拍下决策信心 +80%，误拍率 -50%
- **依赖**：F-01 复用 LLM Key 配置

#### F-07 时间趋势可视化（增强版）
- **功能描述**（在 Sprint B UX-07 基础上扩展）：
  - 4 张统计卡下方加 4 个 sparkline（已完成）
  - **新增**：可点击展开为大图折线（7d/30d/90d）+ 同关键词价格中位数基线
  - **新增**：任务成功率折线（按天）+ 失败率告警阈值线
- **技术可行性**：⭐⭐⭐⭐ — 复用现有 SVG 框架 + `/api/stats/trend` 已有，2-3 人天
- **预期用户价值**：用户能"看图决策"——阈值是不是该调
- **依赖**：Sprint B UX-07

#### F-08 日志搜索/标记/导出
- **功能描述**：
  - 顶栏搜索框（支持时间范围、level、stage、task_id 过滤）
  - 关键行可"打标签"（如"风控嫌疑"），后续过滤可只看标签行
  - "导出"按钮下载 `.log`/`.csv`
- **技术可行性**：⭐⭐⭐⭐ — `/api/logs` 已存在，加 query 参数 + 前端搜索框，2-3 人天
- **预期用户价值**：排查故障从翻 1000 行 → 关键词搜秒定位
- **依赖**：无

#### F-09 任务"运行历史"Tab
- **功能描述**：在 `tasks/detail.html` 加"运行历史"Tab：每次 cron 触发的（开始时间/命中数/错误/耗时/触发原因）
- **技术可行性**：⭐⭐⭐⭐ — 后端 `/api/tasks/{id}/runs` 基于 events 表聚合，前端 htmx 懒加载，1-2 人天
- **预期用户价值**：用户能看出"这任务今天跑了几次 / 失败几次 / 沉默了多久"
- **依赖**：现有 events 表

#### F-10 免打扰时段（Do Not Disturb）
- **功能描述**：
  - 配置"勿扰时段"（如 23:00-07:00）+ "勿扰例外（仅 critical）"
  - 顶栏显示"🌙 勿扰中（还剩 4h32m）"徽章
  - 临时关闭 30/60/120 分钟快捷按钮
- **技术可行性**：⭐⭐⭐⭐⭐ — Notifier 已分渠道，加时段过滤即可，1 人天
- **预期用户价值**：凌晨不再被推送吵醒
- **依赖**：Notifer Hub 已有渠道适配

#### F-11 任务模板市场（个人版）
- **功能描述**：
  - 内置 10 个"预置模板"（如"95 新 A7M4 镜头"、"Switch OLED"、"球鞋 43 码"、"演出门票"）
  - 用户可"另存为模板"（私有）
  - 模板 → 任务一键复制（自动填充关键词+价格+AI Prompt）
- **技术可行性**：⭐⭐⭐ — YAML 文件 + `/api/templates` 路由，2-3 人天
- **预期用户价值**：建任务从 5 分钟 → 30 秒（选模板 + 微调）
- **依赖**：无

### 4.3 P2 优先级（迭代中）

#### F-12 卖家历史价格趋势
- **功能描述**：在评估明细页加"卖家过去 30d 价格曲线"（拉取该卖家所有在售商品）
- **技术可行性**：⭐⭐⭐ — 复用 Collector，2-3 人天
- **预期用户价值**：识别"突然涨价 = 急出/钓鱼"模式
- **依赖**：F-09 数据源

#### F-13 利润计算器
- **功能描述**：在订单详情/接管 Modal 加"扣完手续费净赚"计算（支持鱼小铺 1.6%、普通 0.6%）
- **技术可行性**：⭐⭐⭐⭐⭐ — 纯前端计算，0.5 人天
- **预期用户价值**：决策时知道"实际赚多少"
- **依赖**：无

#### F-14 移动端操作降级（增强版）
- **功能描述**（在 P1-5 基础上）：
  - 移动端可"接管订单"（简化版 Modal）
  - 移动端可"暂停/恢复任务"（一键 swipe）
  - 移动端"通知中心"独立页（非 drawer）
- **技术可行性**：⭐⭐⭐ — 1-2 人天
- **预期用户价值**：通勤路上也能处理关键操作
- **依赖**：P1-5

#### F-15 评估分布直方图 + 阈值建议
- **功能描述**：评估明细页加"分数分布"图（0-100 分 5 档命中数） + "系统建议阈值"（基于你最近通过的命中分布反推）
- **技术可行性**：⭐⭐⭐ — 1-2 人天
- **预期用户价值**：用户能看出"阈值定太严了/太松了"
- **依赖**：无

#### F-16 任务依赖关系
- **功能描述**：任务 B 可配置"依赖任务 A 成功才启动"（如"A 抢到镜头 → 自动启动 B 抢配套滤镜"）
- **技术可行性**：⭐⭐ — Scheduler 加依赖图，3-5 人天
- **预期用户价值**：组合捡漏（如买齐一整套）
- **依赖**：现有 scheduler 扩展

### 4.4 v2.0 候选（突破单账号限制）

#### F-17 多账号 + 代理 IP 池
- **功能描述**：支持配置多个闲鱼账号（Cookie 隔离）+ 代理 IP 轮换；单账号触发风控自动切换
- **技术可行性**：⭐⭐ — 涉及账号池、IP 池、关联检测对抗，10+ 人天
- **预期用户价值**：从"1 账号 1 浏览器" → "N 账号 N 浏览器"，7×24 不掉线
- **依赖**：突破 requirements.md §2.1 "单账号"约束
- **风险**：高（违反闲鱼 ToS 风险 +10x）

#### F-18 跨平台比价（v2.0 候选）
- **功能描述**：除闲鱼外，接入转转、爱回收等二手平台，统一监控
- **技术可行性**：⭐ — 每平台独立适配 + 统一数据模型，30+ 人天
- **预期用户价值**：覆盖更广、捡漏概率 +N 倍
- **依赖**：独立产品规划

---

## 5. 现有痛点优化需求（按 P0/P1/P2 排序）

> 每条优化需求包含：**改进点 / 实施路径 / 预期效果**

### 5.1 P0 优化（1-2 周内做）

#### O-01 Toast 严重度分级 + 不自动消失
- **改进点**：当前 `base.html:312` Toast 3.5s 统一消失，err/critical 级别改为不消失（用户手动关）+ warn 5s + info 2s
- **实施路径**：
  1. `pushToast()` 接收 `severity` 参数
  2. CSS 加 `.toast.critical { animation: none; cursor: pointer; }`
  3. err 级关联现有 `/api/notifications` 持久化（Sprint A UX-05 已落地，扩展即可）
- **预期效果**：凌晨风控告警不再错过；关键错误可截图/复制
- **涉及文件**：[base.html](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/web/templates/base.html) + app.css

#### O-02 价格直方图对比基线（增强 Sprint B UX-03）
- **改进点**：在已有 P25/P50/P75 基础上，新增"今日 vs 7 日均价"对比线
- **实施路径**：
  1. `/api/stats/price-trend` 返回 `{today_avg, d7_avg, delta_pct}`
  2. SVG 加一条红色虚线（今日均价）
  3. Tooltip 加"vs 7 日均价 ±X%"
- **预期效果**：用户 5 秒看出"今天是不是涨价了"
- **涉及文件**：[dashboard.html](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/web/templates/dashboard.html) + api_stats.py

#### O-03 错误通知"复制详情 + 查看日志"快捷操作
- **改进点**：通知中心每条 err 加 3 个按钮（复制 payload / 跳转日志 / 立即重试）
- **实施路径**：
  1. notification 模型加 `payload` JSON 字段
  2. Notification 卡片 footer 加 3 个 icon 按钮
  3. "重试" 按钮调用对应 task 重新触发
- **预期效果**：故障定位从 5 分钟 → 30 秒
- **涉及文件**：[base.html](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/web/templates/base.html) + notification_engine.py

#### O-04 配置保存不刷新页面
- **改进点**：当前 `config/base.html:359` 保存后 `location.reload()` 丢失滚动位置
- **实施路径**：
  1. 保存成功后只刷新该 Tab 的内容（htmx swap）
  2. URL 锚点保持当前 Tab
  3. 滚动位置在 Alpine state 保存
- **预期效果**：配置改 5 项不丢位置、不打断思路
- **涉及文件**：[config/base.html](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/web/templates/config/base.html) + api_config.py

### 5.2 P1 优化（1 个月内做）

#### O-05 评估分布直方图
- **改进点**：[evaluations.html](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/web/templates/evaluations.html) 加"分数分布"图（0-20/20-40/40-60/60-80/80-100 五档命中数）
- **实施路径**：
  1. `/api/evaluations/distribution` 返回 5 档统计
  2. 复用现有 `renderHistogram()` 框架
  3. 加"如果阈值 = X，通过率 = Y%" 计算器
- **预期效果**：用户能看出"阈值定严了（80% 被刷）还是松了（90% 都过）"
- **涉及文件**：evaluations.html + api_evaluations.py

#### O-06 任务"沉默"高亮
- **改进点**：任务列表加"沉默"列徽章（>7 天无命中=黄、>30 天=红）
- **实施路径**：
  1. `/api/tasks/list` 加 `last_hit_at` 字段
  2. 列表渲染时根据时间差加徽章
  3. 鼠标 hover 显示"上次命中：X 天前（商品 Y）"
- **预期效果**：用户能及时发现"僵尸任务"并清理
- **涉及文件**：[tasks/list.html](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/web/templates/tasks/list.html) + api_tasks.py

#### O-07 时间线"严重度"过滤
- **改进点**：[timeline.html](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/web/templates/timeline.html) 过滤区加"严重度"多选（info/warn/err）
- **实施路径**：
  1. 过滤区加一组 pill
  2. 后端 query 加 `levels=` 参数
  3. URL 同步 `?levels=warn,err` 方便分享
- **预期效果**：排查故障时少 50% 噪声
- **涉及文件**：timeline.html + api_events

#### O-08 接管 Modal 自动关闭 done 阶段
- **改进点**：[orders.html](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/web/templates/orders.html) done 阶段 3s 后自动关闭
- **实施路径**：
  1. takeover 状态机加 `autoCloseAt` 字段
  2. `setTimeout(() => closeTakeover(), 3000)`
  3. 鼠标移入 Modal 清除 timer
- **预期效果**：少 1 次点击
- **涉及文件**：orders.html

#### O-09 SSE 断线重连时回放
- **改进点**：SSE 断线重连后，PC 端漏掉的关键告警（err）从 events 表补拉
- **实施路径**：
  1. SSE 客户端记录 `last_event_id`
  2. 重连时传 `Last-Event-ID` header
  3. 后端从 events 表查 `id > last_event_id AND level IN ('err','critical')`
- **预期效果**：断网 1 小时回来不漏关键告警
- **涉及文件**：[base.html](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/web/templates/base.html) + event_bus.py

#### O-10 通知中心免打扰时段
- **改进点**：Notifier 加 `quiet_hours: "23:00-07:00"` 配置 + `critical_only_during_quiet: true`
- **实施路径**：
  1. yaml_config 加 notifier.quiet_hours
  2. NotificationEngine.send() 时段过滤
  3. 顶栏徽章显示"🌙 勿扰中"状态
- **预期效果**：凌晨不再被推送吵醒
- **涉及文件**：notifier/hub.py + config.yaml + base.html

### 5.3 P2 优化（迭代中）

#### O-11 移动端 iPad 横屏适配
- **改进点**：当前 `≤900px` 断点，iPad 横屏（1024×768）走 PC 布局但触控体验差
- **实施路径**：
  1. 断点调整为 `≤768px`（手机）/ `769-1024px`（平板）/ `>1024px`（PC）
  2. 平板布局：保留表格但加大点击区（44px+）、抽屉默认折叠
- **预期效果**：iPad 用户不再"看着像 PC 但点不准"
- **涉及文件**：app.css

#### O-12 日志页"加载更多"
- **改进点**：当前 [logs.html](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/web/templates/logs.html) 1000 行限制，超长日志被截断
- **实施路径**：
  1. 加"加载更多"按钮 → 请求 `?offset=1000&limit=500`
  2. 或加"按时间范围"加载
- **预期效果**：长日志可回溯
- **涉及文件**：logs.html + api_logs.py

#### O-13 配置保存后内联"已保存 v123 · [↺ 立即回滚]"
- **改进点**：在 [config/base.html](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/web/templates/config/base.html) 头部加持久显示区
- **实施路径**：
  1. Alpine `inlineSaveBadge` 组件
  2. 保存成功后更新
  3. "回滚"按钮直接打开回滚 Modal
- **预期效果**：误改后可 1 步回滚（无需翻备份历史）
- **涉及文件**：config/base.html

#### O-14 颜色编码 + icon 双通道（无障碍）
- **改进点**：当前 `.stat`/`.pill` 颜色编码（红=失败/绿=成功）依赖颜色识别
- **实施路径**：
  1. 每个状态色配 icon（✓/⚠/✕/—）
  2. 标签加 `aria-label` 补充语义
- **预期效果**：色盲用户也能识别状态
- **涉及文件**：app.css 多处

#### O-15 加载态统一
- **改进点**：当前 `spinner`/`加载中…`/`加载中...` 不统一
- **实施路径**：
  1. 抽 `.skeleton` 组件 + `.loading` 文案标准
  2. 全站替换
- **预期效果**：视觉一致性
- **涉及文件**：app.css + 各页面

---

## 6. 优先级总表

| 编号 | 类型 | 标题 | 阶段 | 工时 | 依赖 |
|---|---|---|---|---|---|
| F-01 | 新增 | AI 自然语言建任务 | P0 | 1-2 人天 | LLM Key |
| F-02 | 新增 | 全局快捷键 + Command Palette | P0 | 2-3 人天 | 无 |
| F-03 | 新增 | 任务批量操作 | P0 | 0.5 人天 | 无 |
| F-04 | 新增 | 配置导入导出分享 | P0 | 1-2 人天 | O-13 |
| F-05 | 新增 | 关键错误持久化 + 操作 | P0 | 1 人天 | Sprint A UX-05 |
| O-01 | 优化 | Toast 严重度分级 | P0 | 0.5 人天 | 无 |
| O-02 | 优化 | 价格直方图对比基线 | P0 | 0.5 人天 | Sprint B UX-03 |
| O-03 | 优化 | 错误通知操作按钮 | P0 | 1 人天 | F-05 |
| O-04 | 优化 | 配置保存不刷页 | P0 | 0.5 人天 | 无 |
| F-06 | 新增 | AI 多模态成色评估 | P1 | 3-5 人天 | F-01 |
| F-07 | 新增 | 时间趋势可视化（增强） | P1 | 2-3 人天 | Sprint B UX-07 |
| F-08 | 新增 | 日志搜索/标记/导出 | P1 | 2-3 人天 | 无 |
| F-09 | 新增 | 任务运行历史 Tab | P1 | 1-2 人天 | events 表 |
| F-10 | 新增 | 免打扰时段 | P1 | 1 人天 | Notifier |
| F-11 | 新增 | 任务模板市场（个人版） | P1 | 2-3 人天 | 无 |
| O-05 | 优化 | 评估分布直方图 | P1 | 1-2 人天 | 无 |
| O-06 | 优化 | 任务沉默高亮 | P1 | 0.5 人天 | api_tasks |
| O-07 | 优化 | 时间线严重度过滤 | P1 | 0.5 人天 | api_events |
| O-08 | 优化 | 接管 Modal 自动关闭 | P1 | 0.3 人天 | 无 |
| O-09 | 优化 | SSE 重连回放 | P1 | 1 人天 | events 表 |
| O-10 | 优化 | 通知中心免打扰 | P1 | 1 人天 | F-10 |
| F-12 | 新增 | 卖家历史价格趋势 | P2 | 2-3 人天 | F-09 |
| F-13 | 新增 | 利润计算器 | P2 | 0.5 人天 | 无 |
| F-14 | 新增 | 移动端操作降级 | P2 | 1-2 人天 | P1-5 |
| F-15 | 新增 | 评估分布 + 阈值建议 | P2 | 1-2 人天 | O-05 |
| F-16 | 新增 | 任务依赖关系 | P2 | 3-5 人天 | scheduler 扩展 |
| F-17 | 新增（候选）| 多账号+代理池 | v2.0 | 10+ 人天 | 突破单账号约束 |
| F-18 | 新增（候选）| 跨平台比价 | v2.0 | 30+ 人天 | 独立规划 |
| O-11 | 优化 | iPad 横屏适配 | P2 | 0.5 人天 | P1-5 |
| O-12 | 优化 | 日志加载更多 | P2 | 0.5 人天 | api_logs |
| O-13 | 优化 | 配置回滚内联 | P2 | 0.5 人天 | F-04 |
| O-14 | 优化 | 色盲友好（icon 双通道） | P2 | 0.5 人天 | app.css |
| O-15 | 优化 | 加载态统一 | P2 | 0.5 人天 | app.css |

**汇总**：
- P0：9 项 / ~10 人天
- P1：11 项 / ~20 人天
- P2：9 项 / ~10 人天
- v2.0 候选：2 项 / 40+ 人天（独立规划）

---

## 7. 实施建议与下一步

### 7.1 推荐 Sprint 节奏（接续现有 Sprint A/B/C 模式）

```
Sprint D（建议 2 周内）：
  - F-02 全局快捷键 + Command Palette（ux-review §P2-1 已锁定）
  - F-03 任务批量操作
  - O-01 Toast 严重度分级
  - O-04 配置保存不刷页
  → 工时 ~6 人天，影响"高频用户每天省 10 分钟"

Sprint E（建议 1 个月内）：
  - F-01 AI 自然语言建任务（核心竞争力补齐）
  - F-05 + O-03 关键错误持久化 + 操作
  - O-02 价格直方图对比基线
  - O-05/O-06/O-07 数据可视化扩展
  - F-10 免打扰时段
  → 工时 ~10 人天，影响"新用户认知成本 -80% + 凌晨体验"

Sprint F（建议 2 个月内）：
  - F-06 AI 多模态成色评估（v1.0 核心承诺）
  - F-07/F-08/F-09 时间趋势+日志搜索+运行历史（决策支持三件套）
  - F-11 任务模板市场
  - O-08/O-09/O-10 体验完善
  → 工时 ~15 人天，影响"决策信心 +80%"
```

### 7.2 风险与依赖

| 风险 | 等级 | 缓解 |
|---|---|---|
| LLM API 成本失控 | 中 | F-01/F-06 加 usage 监控、单用户限流 |
| 闲鱼改版导致选择器失效 | 高 | 选择器集中 + 异常告警 + F-09 提前发现 |
| 账号被风控 | 中 | 严格 QPS + 行为模拟 + 不接打码平台 |
| 多账号扩展违反 ToS | 高 | v2.0 候选需用户明确确认风险 |

### 7.3 交付物建议

每 Sprint 交付：
1. **代码** + **smoke test**（参考 Sprint A/B 模板）
2. **截图**（Playwright 验证前后对比）
3. **更新版 [ux-review-2026-06.md](file:///d:/code/otherProjects/17_xianyu/docs/ux-review-2026-06.md)**（标记已落地）
4. **本文档的"已落地清单"**（更新本报告 §6 状态栏）

---

## 8. 参考资料

- [requirements.md](file:///d:/code/otherProjects/17_xianyu/docs/requirements.md) — 业务需求规格
- [design.md](file:///d:/code/otherProjects/17_xianyu/docs/design.md) — 技术设计
- [ux-review-2026-06.md](file:///d:/code/otherProjects/17_xianyu/docs/ux-review-2026-06.md) — UX 评审与功能审查报告
- [sprint-a-2026-06-06.md](file:///d:/code/otherProjects/17_xianyu/docs/sprint-a-2026-06-06.md) — Sprint A 交付报告
- [2026-06-04-web-ui-design.md](file:///d:/code/otherProjects/17_xianyu/docs/plans/2026-06-04-web-ui-design.md) — Web UI 设计
- [ai-goofish-monitor GitHub](https://github.com/Usagi-org/ai-goofish-monitor) — 主要开源竞品（~12.3k star）
- [Resell Reserve](https://www.resellreserve.co.uk/features) — Vinted 监控 SaaS
- [REPDASH](https://www.rep-dash.com/reseller-tools) — eBay/Vinted 卖家分析
- [VintiePlus](https://vintieplus.com/) — Vinted EU sniper
- [Flipify](https://www.flipifyapp.com/blog/best-reseller-apps) — Facebook/Craigslist 监控

---

*文档结束 — 后续每 Sprint 完成后回填 §6 状态栏*
