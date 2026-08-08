# 闲鱼猎人开发技能（xianyu-hunter-dev）

## 概述

`xianyu-hunter-dev` 是闲鱼猎人（XianyuHunter）项目个性化开发的完整技能，涵盖后端（Python/FastAPI）、前端（React/TypeScript/AntD）、数据库（SQLite/ChromaDB）和智能客服（RAG/Agent/向量库）四大开发领域的编码规范、代码模板、参考文档与最佳实践。

## 项目背景

闲鱼猎人是一个面向个人的闲鱼（goofish.com）自动捡漏与抢单工具，通过 Playwright 浏览器自动化访问闲鱼平台，实现关键词搜索、价格过滤、4 维卖家评估、增量去重、自动下单和多渠道推送的完整闭环。

- **当前版本**：0.3.0
- **架构模式**：DDD Lite + Clean Architecture（domain → infra → modules → web 四层）
- **测试覆盖**：148/148 单元测试通过
- **部署模式**：Docker 三阶段构建 / Windows bat / Linux systemd

## 文档结构

```
xianyu-hunter-dev/
├── SKILL.md                          # Skill 定义文件（触发词、执行步骤、输出格式）
├── README.md                         # 本文件 - 使用说明
├── config/
│   └── tech-stack.json               # 技术栈版本、路径与硬约束配置
├── assets/
│   ├── guides/                       # 分领域开发指南
│   │   ├── frontend-guide.md         # 前端开发规范与模板
│   │   ├── backend-guide.md          # 后端开发规范与模板
│   │   ├── database-guide.md         # 数据库开发规范与模板
│   │   └── chatbot-guide.md          # 智能客服开发规范与模板
│   └── templates/                    # 标准化代码模板
│       ├── python/
│       │   ├── route.py              # FastAPI 路由模板
│       │   ├── repository.py         # 仓储 Mixin 模板
│       │   └── domain.py             # 领域模型模板
│       └── typescript/
│           ├── api.ts                # API 模块模板
│           ├── hook.ts               # 自定义 Hook 模板
│           └── store.ts              # Zustand store 模板
└── references/                       # 参考文档
    ├── project-rules.md              # 项目硬约束（强制规则）
    ├── architecture-patterns.md      # 架构模式知识库
    └── faq.md                        # 常见问题与最佳实践
```

## 文档内容

### 1. 前端开发指南

**文件位置**：`assets/guides/frontend-guide.md`

**包含内容**：
- 命名约定（文件、组件、Hook、Store、常量）
- React 18 + TypeScript 5 开发规范
- 组件设计（SheetWorkspace 多页签、ErrorBoundary、LazyImage、EChart）
- Hook 设计模式（useAutoLiveSearch、useAutoRefresh、useSheetSync 等 8 个）
- Zustand 状态管理（configStore 双状态、sheetStore 四分支）
- AntD 5 主题配置（亮/暗双主题、品牌橙 #FF6200）
- PWA 配置（vite-plugin-pwa、registerType=prompt）
- SonarQube 规则遵守（S2004/S3358/S6757/S7784/S6848 等 8 条）
- 代码模板（API/Hook/Store 3 个标准模板）

### 2. 后端开发指南

**文件位置**：`assets/guides/backend-guide.md`

**包含内容**：
- 四层分层架构（domain / infra / modules / web）
- Composition Root 依赖注入容器
- 命名约定（路由 `api_<域>.py`、仓储 `repo_<域>.py`、Mixin `<域>sMixin`）
- 异步并发模型（asyncio.CancelledError、run_coroutine_threadsafe、PriorityBrowserLock）
- 安全约束（hmac.compare_digest、_SENSITIVE_HEADERS、_escape_like、_USER_ID_RE）
- 错误处理三层兜底（路由层 → exception_handlers → loguru）
- 日志规约（loguru 三 sink + request_id ContextVar + patcher 钩子）
- 配置加载（.env + YAML 深度合并 + keyring）
- 代码模板（Route/Repository/Domain 3 个标准模板）

### 3. 数据库开发指南

**文件位置**：`assets/guides/database-guide.md`

**包含内容**：
- SQLite 引擎配置（WAL + NullPool + busy_timeout 10s）
- SQLAlchemy 2.0 风格（DeclarativeBase + Mapped + mapped_column）
- 表设计规范（26 张表，主系统/账号池/智能客服/多用户 4 大类）
- 索引策略（task_id/seller_id/first_seen/publish_time/created_at + 复合索引）
- 幂等迁移模式（_migrate_add_column/_migrate_create_index/_migrate_make_column_nullable）
- JSON 字段处理（_row_to_dict 白名单）
- 仓储 Mixin 组合模式（10 个 Mixin + 动态加载）

### 4. 智能客服开发指南

**文件位置**：`assets/guides/chatbot-guide.md`

**包含内容**：
- ChatbotOrchestrator 编排器（FAQ → Intent → RAG → Agent → Context → Escalation）
- RAGEngine 设计（无状态共享、向量化、ChromaDB 检索、阈值过滤、引用校验）
- Agent 多步工具调用（OpenAI function calling、总超时、预算控制）
- KBManager 两阶段提交（导出快照 → 清空+写入+建版本，失败回滚）
- ToolRegistry 5 个只读工具（task_status/eval_score/config_value/error_logs/help_page）
- 降级链（LLM → RAG 片段 → 转人工，每级发布 CHATBOT_DEGRADED 事件）
- 敏感字段脱敏（_filter_sensitive 递归遍历）
- 向量存储（ChromaDB + 本地 Embedding BAAI/bge-small-zh-v1.5）

### 5. 参考文档

**文件位置**：`references/`

| 文件 | 说明 |
|------|------|
| `project-rules.md` | 版本约束、目录规范、安全硬约束、命名规范、SonarQube 配置 |
| `architecture-patterns.md` | DI 容器、EventBus、Mixin 仓储、PriorityBrowserLock、SSE 流、Cookie 隔离、5 类调度器等架构模式与踩坑记录 |
| `deployment-runtime-standards.md` | 部署与运行时编码规范（SPA 子路径/域名模式前缀、路由单一数据源、环境依赖完整性）+ 开发/测试过程四维复盘 |
| `faq.md` | 常见问题（Cookie 隔离、配置热更新、asyncio.CancelledError、SonarQube 规则等）+ 最佳实践 |

## 使用指南

### 1. 开发前准备

1. 阅读 [project-rules.md](references/project-rules.md) 了解项目强制约束
2. 根据开发领域查阅对应的指南文档：
   - 前端：`assets/guides/frontend-guide.md`
   - 后端：`assets/guides/backend-guide.md`
   - 数据库：`assets/guides/database-guide.md`
   - 智能客服：`assets/guides/chatbot-guide.md`
3. 参考 `assets/templates/` 目录下的对应模板进行代码编写
4. 涉及架构疑问，查阅 [architecture-patterns.md](references/architecture-patterns.md)

### 2. 开发流程

#### 后端开发（FastAPI）

1. **新增业务域**：在 `domain/` 定义数据模型 → 在 `infra/` 定义仓储 Mixin → 在 `modules/` 实现业务逻辑 → 在 `web/routes/` 暴露 API
2. **依赖注入**：在 `container.py` 的 `Container` dataclass 中声明字段，在 `build_default_container()` 中初始化
3. **路由注册**：在 `web/app.py` 的 `create_app()` 中 `app.include_router(<新路由>.router)`
4. **启动钩子**：涉及后台任务在 `web/startup.py` 的 `setup_startup_hooks()` 中注册

#### 前端开发（React + AntD）

1. **新增页面**：在 `pages/<域>/index.tsx` 创建组件 → 在 `App.tsx` 用 `lazyRetry` 注册路由 → 在 `MainLayout.tsx` 添加菜单项 → 在 `sheetRegistry.tsx` 维护映射
2. **API 调用**：在 `api/<域>.ts` 导出 `<域>Api` → 在 `api/index.ts` re-export → 在 `api/types.ts` 追加类型
3. **跨页状态**：在 `stores/<feature>Store.ts` 用 Zustand 创建 store
4. **复用逻辑**：在 `hooks/use<Feature>.ts` 提取自定义 Hook

#### 数据库开发（SQLite + SQLAlchemy 2.0）

1. **新增表**：在 `infra/db_models.py` 定义 `*Row(Base)` 类，遵循 `Mapped[T] + mapped_column` 风格
2. **新增字段/索引**：在 `init_db()` 中追加 `_migrate_add_column` / `_migrate_create_index` 调用（幂等）
3. **修改列类型**：使用 `_migrate_make_column_nullable` 表重建模式
4. **仓储实现**：在 `infra/repo_<域>.py` 实现 Mixin，在 `infra/repository.py` 中聚合

#### 智能客服开发（RAG + Agent）

1. **新工具**：在 `modules/chatbot/tools/` 继承 `BaseTool`，在 `tool_registry.py` 注册
2. **降级链**：在 `ChatbotOrchestrator._handle_*` 中追加降级分支
3. **KB 数据源**：修改 `KBManager._scan_and_chunk` 扫描规则

### 3. 代码审查

- 前端代码审查：调用 `xianyu-frontend-code-review` Skill
- 后端代码审查：调用 `xianyu-backend-code-review` Skill
- SonarQube 扫描：调用 `xianyu-sonarqube-mcp` Skill

### 4. 常见问题

遇到问题先查阅 [faq.md](references/faq.md)，已覆盖 Cookie 隔离、配置热更新、asyncio 异常处理、SonarQube 规则、配置加载等常见场景。

## 技术栈

### 后端

- Python >=3.10（Docker 3.12-slim）
- FastAPI 0.136.3 + uvicorn 0.48.0
- SQLAlchemy 2.0.50 + aiosqlite 0.22.1
- pydantic 2.13.4 + pydantic-settings 2.14.1
- Playwright 1.60.0
- httpx 0.28.1 / aiohttp 3.14.0
- APScheduler 3.11.2
- loguru 0.7.3
- keyring 25.7.0（Windows DPAPI）
- tenacity 9.1.4
- cryptography 49.0.0
- chromadb >=1.0.0
- pytest 9.0.3 + pytest-asyncio 1.4.0

### 前端

- React 18.3.1 + TypeScript 5.5
- Ant Design 5.21 + @ant-design/icons 5.5
- Zustand 4.5
- react-router-dom 6.26
- axios 1.7
- echarts 5.5 + echarts-for-react 3.0
- @dnd-kit/core 6.1
- Vite 5.4 + vite-plugin-pwa 1.3
- Vitest 4.1 + @testing-library/react 16.3

### 数据库

- SQLite（WAL 模式，NullPool + busy_timeout 10s）
- ChromaDB 1.x（智能客服 RAG 向量库）

### 工具链

- Docker（三阶段构建：node:20-alpine + python:3.12-slim）
- Docker Compose（3 profile：prod / dev / split）
- pre-commit（check-added-large-files、check-merge-conflict、check-yaml、forbid-root-temp-files 等）
- SonarQube（projectKey=xianyu_hunter，Python 3.10 / TS tsconfig）
- bump_version.py（SemVer 版本同步）

## 相关 Skills

| Skill | 用途 |
|---|---|
| `xianyu-automation-startserver` | 启停服务、构建、状态检查 |
| `xianyu-backend-code-review` | 后端代码评审（Python/FastAPI） |
| `xianyu-frontend-code-review` | 前端代码评审（React/TypeScript） |
| `xianyu-sonarqube-mcp` | SonarQube 代码质量扫描与问题修复 |
| `xianyu-logs-review` | 运行时日志分析与 WARNING/ERROR 排查 |
