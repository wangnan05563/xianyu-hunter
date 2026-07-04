# Changelog

本文件记录 XianyuHunter（闲鱼猎人）的所有版本变化，遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 格式与 [Semantic Versioning](https://semver.org/lang/zh-CN/) 2.0.0 规范。

版本号变更规则见 [VERSIONING.md](VERSIONING.md)。

---

## [Unreleased]

_本次发布周期的变更已封版至 [0.2.0]，新变更请在此段落积累。_

---

## [0.3.0] - 2026-07-03

### Summary

本次发布聚焦多用户体系、任务调度自动化、多 Sheet 页工作区与远程访问能力。从单用户工具升级为支持多账号隔离与团队协作的捡漏平台，并补齐任务自动实时搜索、Cloudflare Tunnel 远程访问、SonarQube 代码质量整改等关键能力。

### Added

#### 多用户体系（MU1 + MU2）
- **多用户数据层**：新增 6 张多用户 ORM 表模型，TaskRow 增加 `user_id` 字段与索引迁移。
- **UserManager**：身份识别 `identify_or_create`、会话签发 `issue_session`、滑动续期 `verify_session`、会话注销 `revoke_session`、用户列表/状态切换/删除/账号探测等完整生命周期管理。
- **数据迁移**：`migrate_to_multi_user` 启动时自动迁移历史 Cookie 与任务到默认用户。
- **CookieStore 用户隔离**：按 `user_id` 维度隔离 JSON 文件与内存缓存。
- **认证中间件三路校验**：WEB_TOKEN 直通 + session_token 校验 + 401 降级，注入 `user_id` 到请求上下文。
- **登录流程接入**：`unified_login` 集成 UserManager，登录成功后自动签发会话并导出 Cookie。
- **向后兼容**：`cookie_inject` / `auth_query` 调用自动补充 `user_id=default`。

#### 任务管理菜单实时搜索与采集周期配置
- **useAutoLiveSearch Hook**：任务自动实时搜索，支持倒计时、页面可见性感知、并发控制。
- **TaskList 集成**：新增「下次搜索」倒计时列、「自动搜索」开关、「采集周期」只读列。
- **手动/自动互斥**：折叠面板「实时查询」按钮与自动搜索互斥，避免冲突。
- **TaskSchedulerConfig**：新增 `default_interval_seconds` / `auto_search_enabled` / `auto_search_concurrency` 配置块，支持全局默认与任务级覆盖。
- **SearchConfig 分区**：新增「任务调度默认值」分区。

#### 多 Sheet 页工作区
- **useIsMobile**：响应式断点检测 Hook。
- **sheetRegistry**：路径到懒加载页面组件的映射注册表。
- **sheetStore**：Sheet 状态管理与持久化，支持 navigator 注入。
- **useSheetSync**：URL 与当前 Sheet 双向同步。
- **Sheet 组件套件**：SheetContent、SheetTabs、SheetPreferences、SheetWorkspace 容器。
- **MainLayout 改造**：用 SheetWorkspace 替换 Outlet，登出时清空 Sheet 栈。

#### Cloudflare Tunnel 远程访问
- **内置 TunnelService**：零配置启动 Cloudflare Tunnel，支持远程访问本地服务。
- **Tunnel API**：`/api/tunnel/start` / `/api/tunnel/stop` 一键开关。

#### 其他
- **全局流水号中间件**：每个请求分配 `request_id`，贯穿日志链路。
- **钉钉通知渠道**：新增钉钉机器人推送。
- **采集服务**：统一搜索服务标准化。
- **前端用户菜单**：右上角用户头像下拉菜单。

### Changed
- **搜索服务标准化**：评估价格覆盖逻辑统一，钉钉通知时机修正。
- **MainLayout 重构**：Outlet → SheetWorkspace，登出清理 Sheet 栈。

### Fixed

#### Scheduler 与 API 修复
- **ResumeBlockedError ImportError**：main 分支上 `scheduler.py` 引用未定义的 `ResumeBlockedError`。
- **api_tasks await 不匹配**：移除 `pause/resume/start` 的 `await` 调用，匹配 scheduler 同步方法签名。
- **api_anticrawl 返回类型**：`/freq/delay` 返回 `dict | JSONResponse` Union 类型不被 Pydantic 支持，改为 `response_model=None`。
- **5 分钟冷却**：会话过期暂停后 5 分钟内禁止重复恢复，避免雪崩。

#### 多用户模块修复
- **Cookie 文件迁移异常保护**：迁移失败不中断启动。
- **verify_session 竞态条件**：滑动续期测试补充。
- **issue_session 隔离**：`_log_event` 失败不影响会话签发。
- **get_user_manager 初始化**：确保 `init_db` 在 engine 使用前调用。
- **时间字段类型**：与现有表模式保持一致。
- **路径遍历校验**：`_cookie_json_path` 防路径遍历攻击。
- **代码评审整改**：2 Critical + 7 Important 问题修复。

#### 任务管理与前端修复
- **类型不一致**：`api_tasks.py` 的 `interval_seconds` 类型与 DB schema 对齐。
- **递归调用栈**：`useAutoLiveSearch` 递归调用 `processQueue` 改为迭代。
- **Switch 关闭未暂停**：`TaskList.tsx` Switch 关闭时未调用 `pauseAll`。
- **defineProperty writable**：测试 L58 补齐 `writable: true`。
- **aria-label**：Switch 补充无障碍标签。
- **警告文本**：`SearchConfig` 自动并发警告文本优化。

#### 其他修复
- **TunnelService**：清理未使用导入，添加 `stdout=None` 防御。
- **test_app_config**：修复 `test_app_config_loads_task_scheduler_from_yaml` 全局 `_config` 污染。
- **SonarQube 整改**：79 个跟踪文件的代码质量问题全面修复。

### Security
- **路径遍历防护**：`_cookie_json_path` 增加路径遍历校验。
- **认证中间件**：三方校验防止会话伪造。

---

## [0.2.0] - 2026-06-29

### Summary

本次发布包含 Sprint A 至 About 菜单 sprint 的全部功能与优化，从 MVP 升级为功能完整的闲鱼捡漏平台。涉及任务管理、价格策略、AI 评估、通知渠道、反检测、浏览器自动化、配置版本管理、PWA、Docker 部署、数据导出、About 菜单等 14 个模块。

### Added

#### 任务管理
- **任务 CRUD**：创建/编辑/删除/启停，支持 Cron 表达式调度。
- **任务编辑向导**：6 步骤（基础信息、价格与过滤、搜索参数、AI 评估、反检测、调度与确认），任务级配置覆盖全局。
- **批量任务操作**：批量启停、删除、立即执行。
- **AI 自然语言建任务**：输入自然语言描述自动解析为任务配置。
- **任务依赖（F-16）**：任务间依赖关系配置。
- **模板市场（F-11）**：任务模板一键应用。

#### 价格策略
- **4 种策略独立开关**：硬性上限/下限、低于市场参考价、同类低价 TopN。
- **价格直方图**：ECharts 可视化当前商品价格分布与过滤区间。
- **30 天价格趋势基线**：PriceHistogramCard 增加 last30d 对比。

#### 评估规则
- **4 维权重雷达图**：滑块联动 ECharts 雷达图，权重总和指示器。
- **职业卖家检测**：3 维度（在售数/30 天发帖数/主营品类占比）+ 图像盗用检测（SQLite LIKE 查询）。
- **深度鉴伪**：`/api/ai/deep` 端点 + 前端 Tabs 展示单维度分析。
- **评估漏斗**：EvalFunnelCard 5 阶段转化率可视化。
- **AI 多轮趋势建议**：基于历史评估数据 LLM 生成优化建议。

#### 通知渠道
- **7 个渠道**：Server酱、PushPlus、Bark、Telegram、企业微信、钉钉、自定义 Webhook。
- **拖拽排序**：dnd-kit 实现通道顺序拖拽。
- **免打扰时段**：时间范围滑块 + 跨午夜 + 周末开关。
- **事件订阅规则**：12 种事件勾选 + 级别映射。

#### 反检测与浏览器
- **QPS 限流 + 延迟范围 + 失败熔断**：三道防线。
- **WAF 熔断器**：自动检测 WAF 触发并熔断。
- **WebView2 持久化**：`private_mode=False` + 唯一 `storage_path`，cookie 持久化。
- **CREATE_NEW_CONSOLE**：子进程使用新控制台，防止 GUI 闪退。

#### 反爬登录管理
- **统一登录入口**：扫码/浏览器登录/Cookie 注入/浏览器导入 4 路径收敛。
- **会话管理自动启动**：登录成功后自动启动 TokenRenewer 后台续期，无需手动点击。
- **Cookie 三层状态机**：identity / session / tracking 独立判定 + 自动恢复。
- **force_restore_layers**：依赖层校验，避免在底层 cookie 失效时误恢复上层。

#### 数据导出与采集
- **CSV 导出**：商品/评估/订单/事件 4 个数据集，支持 task_id/状态/时间过滤。
- **批量数据刷新**：APScheduler + asyncio 调度，重试 + 熔断机制。
- **已售商品过滤**：后端 SQL WHERE 推送 + 前端状态持久化。

#### About 菜单
- **品牌卡**：版本/构建日期/Git SHA + 5 态检查更新按钮。
- **开源软件声明**：41 个依赖（21 前端 + 20 后端）+ 搜索过滤。
- **构建元信息**：`scripts/build_info.py` 自动生成 `_build_info.py`。
- **5 个入口**：顶栏按钮、Sider、Command Palette、快捷键 `g+a`、Swagger UI。
- **GitHub 自动更新检查**：后端 `/api/about/check-update` 接入 GitHub Releases API（仓库 `wangnan05563/xianyu-hunter`），5 分钟缓存避免限速，失败安全降级。
- **前端自动定期检查**：About 页面挂载 5 秒后自动检查一次，每 60 分钟复查；卸载时清理所有定时器，杜绝内存泄漏。
- **BrandCard 发布时间展示**：newer 态 Tooltip 展示 release 发布日期。

#### 系统优化
- **PWA 支持**：VitePWA + manifest + workbox（排除 SSE/auth/export）。
- **SSE 断线重连**：Dashboard localStorage 持久化 lastEventId，重连后重放。
- **Docker 部署**：3 阶段 Dockerfile + 多 profile docker-compose。
- **全局快捷键**：Command Palette（`g+*` 路由前缀）。
- **利润计算器**：Orders 页面 1.6% 鱼小铺手续费。

### Changed

- **数据库索引优化**：task_id/seller_id/first_seen/publish_time/created_at 索引 + 复合索引。
- **COUNT 查询合并**：`_overview()` 使用 CASE WHEN 聚合，DB 调用减少 67%。
- **SQLite StaticPool**：单连接共享 + busy_timeout + cache_size，解决锁竞争。
- **dealer_detector 查询合并**：循环 LIKE → 单次 OR 查询。
- **配置覆盖语义**：任务级 `model_copy(update=...)` 不污染全局 singleton。
- **401 响应统一 JSON**：`{"detail": "Unauthorized"}` 替代纯文本。
- **token 比较**：`hmac.compare_digest()` 防止时序攻击。
- **`_is_newer` 保守策略**：任一端版本号无法解析时返回 False，避免 current='unknown' 时误判有更新。

### Fixed

- **评估明细点击「通过」查不到记录**：统计卡片显示全量计数，但前端仅过滤当前页。修复为后端 `result_category` 参数精确分类 + 分页返回。
- **`eval_threshold` NOT NULL 约束失败**：改为 nullable，worker 优先读取任务级阈值。
- **`antidetect_config` 死字段**：UI 改为全局快捷 Modal，避免配置保存但不生效。
- **编辑模式清空 overrides 失败**：`model_dump(exclude_unset=True)` 修复 null 语义断层。
- **TokenRenewer 启动遗漏**：4 个登录入口统一接入 `trigger_session_start`。
- **`_m_h5_tk` 续期失败**：导航到 `h5.m.taobao.com` 触发（用户自然行为，风控压力低）。
- **useUpdateChecker 内存泄漏**：setTimeout 句柄 useRef 持有 + useEffect 卸载清理。
- **PriceHistogramCard `token.colorPurple`**：替换为 `#722ED1` 修复 TS2339。

### Security

- **认证白名单**：`/api/about`、`/api/auth/cookie`、`/api/auth/me`、`/api/events/stream` 等加入 PUBLIC_PREFIXES。
- **敏感字段过滤**：token 长度不记录日志，仅记录布尔匹配结果。
- **Token 写入失败告警**：`logging.warning()` 提示。
- **导入补全**：`re`/`threading`/`logging` 模块级导入，防止运行时 NameError。
- **GitHub API 请求零隐私**：HTTP 头仅含 User-Agent + Accept，不携带 Authorization/token；不发送用户身份、cookie、设备指纹；release_url 始终指向 github.com。

### Compatibility

- **Python**：>=3.10（开发环境 3.14）。
- **Node.js**：>=18（构建环境 24）。
- **浏览器**：Chrome 90+（PWA 需 Service Worker 支持）。
- **数据库**：SQLite（无需额外服务）。
- **操作系统**：Windows 10+（WebView2 依赖）/ Linux / macOS。

---

## [0.1.0] - 2026-06-06

### Summary

初始 MVP 版本，包含基础任务管理、闲鱼搜索、商品采集、评估通知核心流程。

### Added

- **任务管理**：关键词、价格区间、地域、排除词、闲鱼筛选标签、任务模式（AUTO/SEMI_AUTO/CONFIRM/NOTIFY_ONLY）。
- **闲鱼搜索**：Playwright 浏览器自动化，支持 Cookie 注入。
- **商品采集**：标题、价格、卖家、图片、发布时间。
- **基础评估**：4 维权重（价格/卖家/信用/历史）+ pass_score 阈值。
- **通知渠道**：Server酱、PushPlus、Bark（3 个基础渠道）。
- **FastAPI 后端**：SQLAlchemy + SQLite，SSR 模板渲染。
- **htmx 前端**：服务端渲染 + htmx 局部刷新。
- **Swagger UI**：API 文档 + 顶栏品牌块。

### Compatibility

- **Python**：>=3.10。
- **浏览器**：Chrome 90+。
- **数据库**：SQLite。

---

[Unreleased]: https://github.com/wangnan05563/xianyu-hunter/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/wangnan05563/xianyu-hunter/releases/tag/v0.3.0
[0.2.0]: https://github.com/wangnan05563/xianyu-hunter/releases/tag/v0.2.0
[0.1.0]: https://github.com/wangnan05563/xianyu-hunter/releases/tag/v0.1.0
