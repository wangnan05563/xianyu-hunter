# 闲鱼猎人 Web 界面设计方案

> 早期 Web UI 设计基线文档。原基于 Jinja2 服务端渲染，现前端已迁移至 React SPA（`frontend/src/pages/*` + Ant Design + Vite）。

## 1. 目标

为闲鱼猎人（闲鱼自动捡漏与抢单系统，Python CLI 工具）添加完整的 Web UI，覆盖任务管理、配置编辑、运行监控、引导式入门。可读可写。

## 2. 范围

| 页面 | 路径 | 说明 |
|---|---|---|
| 首跑引导 | `/onboarding` | 4 步：扫码 → 加任务 → 验证配置 → 启动 |
| Dashboard | `/dashboard` | 统计卡 + 事件流 + 通知状态 + 系统状态 |
| 任务列表 | `/tasks` | 表格 + 启停/删除/详情 |
| 任务详情 | `/tasks/:id` | 该任务的运行统计 + 商品/评估/订单 |
| 评估明细 | `/evaluations` | 全量评估记录，按评分排序 |
| 抢单记录 | `/orders` | 订单状态流转，手动介入按钮 |
| 配置管理 | `/config/*` | 子页：SearchConfig / PriceStrategy / EvalRules / NotifierChannels / BuyerStrategy |
| 日志 | `/logs` | 实时日志 + 搜索 Tab |

## 3. 技术栈

**当前架构（已迁移）**：
- **后端**：FastAPI（`backend/xianyu_hunter/web/routes/*.py`）
- **前端**：React + TypeScript + Ant Design + Vite（`frontend/src/`）
- **数据流**：SSE 实时事件 + REST API + React Query

**早期架构（已废弃）**：
- FastAPI + Jinja2（服务端渲染）
- htmx（局部刷新）+ Alpine.js（局部状态）+ Tailwind CDN
- 数据流：SSE + htmx 轮询

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
                │  端口 8001    │
                │  浏览器访问   │
                └──────────────┘
```

- Web 和 run 是**独立进程**，互不依赖
- Web 写 task.status 字段 → run 的 scheduler 内存对象不会自动感知，需要重启
- Web 改 YAML 配置 → run 下次启动生效
- Web 写新任务 → run 必须重启才能注册
- **最佳实践**：run 已经稳定运行时，Web 主要用于查看 + 暂停/恢复（不重启）

## 5. 视觉规范（已演进至米其林风格）

当前视觉规范详见 `docs/michelin-design-system.md`：
- 主色：米其林红 `#E20613`
- 评级色：星标金 `#C9A961`
- Display 字体：Cormorant Garamond
- 圆角阶梯：2/4/6/10（"钢印感"）

早期视觉规范（已废弃）：
- 暗色为主：`#0b0d12` / `#1a1d27` / `#252a3a`
- 强调色：闲鱼橙 `#ff6a00`
- 字体：正文 Inter，数值 ui-monospace
- 圆角：8px（按钮）、12px（卡片）

## 6. 实时数据流

1. **Dashboard 统计**：`GET /api/stats` 周期拉取
2. **事件流**：`GET /api/events/stream` SSE，订阅 event_bus（支持 Last-Event-ID 重连回放，详见 Sprint E）
3. **任务状态**：`GET /api/tasks/:id/state` 轮询

## 7. 配置实时预览

- 用户在 SearchConfig/EvalRules 拖动滑块 → 实时计算 pass_score 预览
- 点击"应用" → `POST /api/config?dry_run=1` → 后端返回 diff + 校验错误
- 用户确认 → 真实写入 YAML（带 `.bak` 备份）
- 写入成功后弹出"已保存，重启 run 生效"提示

## 8. 危险操作护栏

- 删除任务 / 清空数据库 / 重置配置 → 二次确认 modal
- 抢单 auto 模式运行中 → 一键"暂停并接管"按钮
- 配置文件写入失败 → 自动回滚到 `.bak`

## 9. 引导式设计

- 首次访问 `/onboarding` → 4 步卡片：扫码 / 加任务 / 配置 / 启动
- 每步完成后该步变绿勾
- 检测到 cookie 有效时跳过第 1 步
- 全部完成时显示"进入 Dashboard"按钮

## 10. 当前文件结构

```
frontend/src/
├── pages/
│   ├── About/                  # 关于页面
│   ├── AntiCrawl/              # 反爬登录管理
│   ├── Chatbot/                # 智能助手
│   ├── Config/                 # 配置管理（含 AIConfig / NotifierChannels / BuyerStrategy / EvalRules / PriceStrategy / SearchConfig / VersionManager 子页）
│   ├── Dashboard/              # 仪表盘
│   ├── Evaluations/            # 评估明细
│   ├── Export/                 # 数据导出
│   ├── Help/                   # 帮助文档
│   ├── Items/                  # 商品列表
│   ├── Login/                  # 登录
│   ├── Logs/                   # 日志（含 ErrorLogs）
│   ├── Maintenance/            # 维护（BatchRefresh / Cleanup / DatabaseAdmin / VectorAdmin）
│   ├── MenuAdmin/              # 菜单管理
│   ├── Notifications/          # 通知中心
│   ├── Onboarding/             # 首跑引导
│   ├── Orders/                 # 抢单记录
│   ├── PriceDashboard/         # 价格看板
│   ├── Tasks/                  # 任务（TaskList / TaskDetail / TaskEditor）
│   └── Timeline/               # 统一时间线
├── components/                 # 通用组件（layout / charts / editors / icons / SheetWorkspace / TidalForagers）
├── hooks/                      # useAutoRefresh / useSearch / useSearchHistory / usePersistentState / useColumnConfig / useIsMobile / usePreferences / useMenuConfig / useAutoLiveSearch / useSheetSync
├── api/                        # API 客户端封装（按业务域拆分）
├── stores/                     # Zustand 状态管理（configStore / sheetStore）
├── contexts/                   # ThemeContext
├── mobile/                     # 移动端专属组件（TabBar / PullToRefresh / MobileLayout）
└── utils/                      # 工具函数（lazyRetry / apiError / storage）

backend/xianyu_hunter/
├── web/
│   ├── routes/                 # 所有 API 路由（api_*.py）
│   ├── services/               # 服务层（auth_manager / cookie_store / notification_engine / session_starter / tunnel_service / user_manager / menu_manager / browser_profile）
│   ├── middleware/             # 中间件（auth / error_capture / exception_handler / request_id）
│   ├── static/                 # 静态资源（SPA 构建产物 + SVG 图标）
│   ├── app.py                  # FastAPI 实例
│   └── deps.py                 # 容器注入
├── modules/                    # 核心业务模块（chatbot / collector / notifier + login_orchestrator / token_renewer / cookie_rotator / scheduler / evaluator / buyer 等）
├── infra/                      # 基础设施（repository / db_models / browser / event_bus / yaml_config / logger / secrets 等）
├── domain/                     # 领域模型（task / order / item / evaluation / seller / event / urls）
├── paths.py                    # 路径集中管理（支持 PyInstaller 打包）
├── _build_info.py              # 构建元信息（自动生成）
└── config.py                   # 配置加载
```

## 11. 风险与缓解

| 风险 | 缓解 |
|---|---|
| Web 改 task.status 但 run 内存中还是旧状态 | 在状态旁显示"需重启 run 生效" |
| 多 Web 实例同时启动 | 启动时检测端口占用并提示 |
| run 异常退出后 Web 仍显示"运行中" | 显示"最后心跳 > 30s"红色提示 |
| 配置 YAML 改坏导致 run 启动失败 | 写前备份 `.bak`，校验通过再替换 |
| Chrome 浏览器锁住 cookies 目录 | 提示关闭其他使用浏览器数据的进程 |
