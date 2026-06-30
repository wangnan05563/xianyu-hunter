# XianyuHunter Web UI 设计文档

日期：2026-06-04
阶段：brainstorming 已完成，进入实施

## 1. 目标

为 XianyuHunter（闲鱼自动捡漏与抢单系统，Python CLI 工具）添加完整的 Web UI，
覆盖任务管理、配置编辑、运行监控、引导式入门。可读可写。

## 2. 范围

| 页面 | 路径 | 说明 |
|---|---|---|
| 首跑引导 | `/?onboard=1` | 4 步：扫码 → 加任务 → 验证配置 → 启动 |
| Dashboard | `/dashboard` | 统计卡 + 事件流 + 通知状态 + 系统状态 |
| 任务列表 | `/tasks` | 表格 + 启停/删除/详情 |
| 任务详情 | `/tasks/{id}` | 该任务的运行统计 + 商品/评估/订单 |
| 评估明细 | `/evaluations` | 全量评估记录，按评分排序 |
| 抢单记录 | `/orders` | 订单状态流转，手动介入按钮 |
| 配置管理 | `/config` | 5 个 Tab：搜索/价格/评估/通知/抢单 |
| 日志 | `/logs` | 实时日志（轮询） |

## 3. 技术栈

- **后端**：FastAPI + Jinja2（服务端渲染）
- **前端增强**：htmx（局部刷新）+ Alpine.js（局部状态）+ Tailwind CDN（快速样式）
- **数据流**：SSE（实时事件）+ htmx 轮询（次实时数据）
- **本地化**：htmx / alpine.js 复制到 static/，避免 CDN 失败

## 4. 进程拓扑

```
┌─────────────┐    SQLite    ┌──────────────┐
│ run 调度器  │ ──────────▶ │  data/       │
│ (asyncio)   │  读写任务    │  xianyu.db   │
└─────────────┘  写事件       └──────────────┘
                       ▲ ▲
                       │ │ 读写任务/配置
                       ▼ │
                ┌──────────────┐
                │  Web (FastAPI)│
                │  端口 8000    │
                │  浏览器访问   │
                └──────────────┘
```

- Web 和 run 是**独立进程**，互不依赖
- Web 写 task.status 字段 → run 的 scheduler 内存对象不会自动感知，需要重启
- Web 改 YAML 配置 → run 下次启动生效
- Web 写新任务 → run 必须重启才能注册
- **最佳实践**：run 已经稳定运行时，Web 主要用于查看 + 暂停/恢复（不重启）

## 5. 视觉规范

- **暗色为主**：`#0b0d12`（底）/`#1a1d27`（卡片）/`#252a3a`（边框）
- **强调色**：闲鱼橙 `#ff6a00`（按钮/状态指示）
- **状态色**：绿 `#22c55e`（运行）/ 黄 `#eab308`（暂停）/ 红 `#ef4444`（异常）/ 灰 `#6b7280`（停止）
- **字体**：正文 Inter（CDN），数值 ui-monospace
- **圆角**：8px（按钮）、12px（卡片）
- **阴影**：`0 4px 12px rgba(0,0,0,0.25)`（弹窗）
- **8px 栅格**

## 6. 实时数据流

1. **Dashboard 统计**：`GET /api/stats` 每 3s 拉取（SSE 备用）
2. **事件流**：`GET /api/events/stream` SSE，订阅 event_bus
3. **任务状态**：`GET /api/tasks/{id}/state` htmx 轮询 5s

## 7. 配置实时预览

- 用户在 `/config/eval` 拖动滑块 → Alpine.js 实时计算 pass_score 预览
- 点击"应用" → htmx POST `/api/config?dry_run=1` → 后端返回 diff + 校验错误
- 用户确认 → 真实写入 YAML（带 `.bak` 备份）
- 写入成功后弹出"已保存，重启 run 生效"提示

## 8. 危险操作护栏

- 删除任务 / 清空数据库 / 重置配置 → 二次确认 modal
- 抢单 auto 模式运行中 → 一键"暂停并接管"按钮
- 配置文件写入失败 → 自动回滚到 `.bak`

## 9. 引导式设计

- 首次访问 `/?onboard=1` → 4 步卡片：扫码 / 加任务 / 配置 / 启动
- 每步完成后该步变绿勾
- 检测到 cookie 有效时跳过第 1 步
- 全部完成时显示"进入 Dashboard"按钮

## 10. 文件结构

```
src/xianyu_hunter/
├── web/
│   ├── __init__.py
│   ├── app.py              # FastAPI 实例
│   ├── deps.py             # 容器注入
│   ├── routes/
│   │   ├── pages.py        # 页面路由
│   │   ├── api_config.py   # 配置 API
│   │   ├── api_tasks.py    # 任务 API
│   │   ├── api_stats.py    # 统计 + SSE
│   │   └── api_logs.py     # 日志
│   ├── templates/
│   │   ├── base.html
│   │   ├── dashboard.html
│   │   ├── onboarding.html
│   │   ├── tasks/
│   │   │   ├── list.html
│   │   │   └── detail.html
│   │   ├── config/
│   │   │   ├── base.html
│   │   │   ├── search.html
│   │   │   ├── price.html
│   │   │   ├── eval.html
│   │   │   ├── notifier.html
│   │   │   └── buyer.html
│   │   ├── evaluations.html
│   │   ├── orders.html
│   │   └── logs.html
│   ├── static/
│   │   ├── app.css
│   │   ├── htmx.min.js
│   │   └── alpine.min.js
│   └── partials/            # htmx 片段
│       ├── task_row.html
│       ├── stat_card.html
│       └── event_item.html
```

## 11. 风险与缓解

| 风险 | 缓解 |
|---|---|
| Web 改 task.status 但 run 内存中还是旧状态 | 在状态旁显示"需重启 run 生效" |
| 多 Web 实例同时启动 | 启动时检测端口占用并提示 |
| run 异常退出后 Web 仍显示"运行中" | 显示"最后心跳 > 30s"红色提示 |
| 配置 YAML 改坏导致 run 启动失败 | 写前备份 `.bak`，校验通过再替换 |
| Chrome 浏览器锁住 cookies 目录 | 提示关闭其他使用浏览器数据的进程 |

## 12. 实施顺序

1. 后端骨架（FastAPI + 路由 + 依赖注入）
2. base.html + design tokens
3. onboarding 引导
4. dashboard（核心入口）
5. tasks CRUD
6. config 5 个 Tab
7. evaluations / orders / logs
8. 注册 web CLI 子命令 + 启动验证
