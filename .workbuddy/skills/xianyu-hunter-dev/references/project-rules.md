# 闲鱼猎人项目硬约束

> 本文档列出闲鱼猎人项目的所有硬约束（Hard Constraints），开发时必须严格遵守。

---

## 一、Web 进程与浏览器

### 1.1 浏览器进程模式

- **【强制】** Web 进程必须使用 `with_browser=False` 模式以节省内存
- **【强制】** WebView2/Playwright 子进程必须使用 `CREATE_NEW_CONSOLE` 标志（而非 `CREATE_NO_WINDOW`），防止 GUI 窗口闪退
- **【强制】** WebView2 子进程禁止重定向 stdout/stderr 到 DEVNULL，保留调试输出
- **【强制】** WebView2 `webview.start()` 必须设置 `private_mode=False` 并指定唯一的 `storage_path`（格式：`webview_data_{pid}_{timestamp}`），以持久化 Cookie 并防止冲突

### 1.2 认证白名单

- **【强制】** 以下端点必须加入认证白名单：
  - `/api/auth/cookie`
  - `/api/auth/me`
  - `/api/auth/import-from-browser`
  - `/import-from-browser/status`
  - `/api/events/stream`
  - `/api/notifications`
  - `/api/notifier/`
  - `/api/about`
  - `/api/about/check-update`

### 1.3 前端认证

- **【强制】** 前端 fetch 请求必须包含 `credentials: 'include'` 以传递认证 Cookie
- **【强制】** htmx 请求必须使用官方 `<meta>` 配置 credentials，确保初始化时机可靠
- **【强制】** 401 响应必须返回 JSON 格式 `{"detail": "Unauthorized"}`，禁止纯文本

---

## 二、安全规约

### 2.1 Token 比较

- **【强制】** 后端 Token 比较必须使用 `hmac.compare_digest()` 防止时序攻击
- **【强制】** 敏感字段（如 token 长度）禁止记录日志，仅记录布尔匹配结果
- **【强制】** Token 写入失败必须触发 `logging.warning()` 告警

### 2.2 输入消毒

- **【强制】** SQL LIKE 查询必须使用 `_escape_like()` 转义 `%` 和 `_` 通配符
- **【强制】** 涉及文件路径的字段必须用 `_USER_ID_RE`（`^[A-Za-z0-9_-]+$`）校验，防路径遍历
- **【强制】** 智能客服用户输入必须经过 `check_user_input_safety()` 检测 Prompt Injection

### 2.3 缺失导入

- **【强制】** 缺失导入（如 `re`、`threading`、`logging`）必须补齐，防止运行时 NameError

---

## 三、数据库规约

### 3.1 索引规约

- **【强制】** 以下列必须建索引：`task_id`、`seller_id`、`first_seen`、`publish_time`、`created_at`、`request_id`
- **【强制】** 必须建立复合索引以优化 Dashboard 查询

### 3.2 查询优化

- **【强制】** `_overview()` 中的 COUNT 查询必须用 `CASE WHEN` 聚合查询合并，减少 DB 调用 67%
- **【强制】** 函数内冗余导入必须移至模块级别

---

## 四、智能客服规约

### 4.1 知识库扫描

- **【强制】** `KBManager._scan_and_chunk` 必须排除以下目录：`web/static/`、`web/templates/`、`__pycache__/`、`node_modules/`、`.git/`、`dist/`、`build/`
- **【强制】** 仅索引 `.md`、`.py`、`.jsonl`、`.txt` 文件（白名单）
- **【原因】** 前端构建产物（packed .js/.css）会产生数千无用 chunk，向量化时间从 ~5min 膨胀到 30+min

### 4.2 Embedding 配置

- **【强制】** `local_embedding.py` 必须在模块顶层设置 `os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")`，避免 HuggingFace.co 国内访问超时
- **【强制】** 设置必须在 `import sentence_transformers` 之前
- **【强制】** 当 `EMBEDDING_BASE_URL` 为空或 "local" 时，使用本地 sentence-transformers 后端（BAAI/bge-small-zh-v1.5，dim=512），不依赖 Ollama/外部 API
- **【强制】** sentence-transformers 5.x 重命名 `get_sentence_embedding_dimension` 为 `get_embedding_dimension`，必须用 `getattr` fallback 实现跨版本兼容

### 4.3 编排器设计

- **【强制】** `ChatbotOrchestrator` 不持有请求级状态（如当前 session_id），保证可被多会话共享
- **【强制】** per-session Lock 用 `_locks_guard` 保护 `_session_locks` 字典的并发访问
- **【强制】** 异常不向外抛出，统一转为 `SSEEvent(ERROR)` 或 `SSEEvent(ESCALATE)`
- **【强制】** `asyncio.CancelledError` 是唯一例外，向上传播以触发资源清理

---

## 五、依赖与版本

### 5.1 后端依赖

| 依赖 | 版本 | 用途 |
|------|------|------|
| Python | 3.10+ | 运行时 |
| FastAPI | 0.136.3 | Web 框架 |
| SQLAlchemy | 2.0.50 | ORM |
| Playwright | 1.60.0 | 浏览器自动化 |
| APScheduler | 3.11.2 | 任务调度 |
| loguru | 0.7.3 | 日志 |
| keyring | 25.7.0 | 凭据存储 |
| chromadb | - | 向量库 |

### 5.2 前端依赖

| 依赖 | 版本 | 用途 |
|------|------|------|
| React | 18.3.1 | UI 框架 |
| TypeScript | 5.5 | 类型系统 |
| Ant Design | 5.21 | UI 组件库 |
| Zustand | 4.5 | 全局状态管理 |
| Vite | 5.4 | 构建工具 |
| Vitest | 4.1 | 单元测试 |
| vite-plugin-pwa | - | PWA 支持 |

---

## 六、SonarQube 规则

### 6.1 必须遵守的 8 条规则

| 规则 | 说明 | 修复方式 |
|------|------|---------|
| S2004 | 函数嵌套层级不超过 4 层 | 提取子函数 |
| S3358 | 三元表达式不超过 2 层 | 拆分为 if-else |
| S6757 | 使用 fetch 时必须处理错误 | try-catch 包裹 |
| S7784 | 字符串字面量应使用单引号 | 统一单引号 |
| S6848 | HTML 属性必须用双引号 | 统一双引号 |
| S1128 | 未使用的导入必须移除 | 清理 import |
| S4325 | 类型注解必须正确 | 修复类型 |
| S3776 | 认知复杂度不超过 15 | 拆分函数 |

---

## 七、Docker 构建

### 7.1 三阶段构建

- **【强制】** Dockerfile 必须使用三阶段构建：
  1. `frontend`：基于 `node:20-alpine` 构建前端
  2. `builder`：基于 `python:3.12-slim` 安装后端依赖
  3. `runtime`：基于 `python:3.12-slim` 运行时镜像

### 7.2 镜像优化

- **【强制】** 每个阶段只复制必要的文件
- **【强制】** runtime 阶段不包含构建工具，减小镜像体积

---

## 八、异步操作与数据流转规范 🆕v4.7

### 8.1 异步操作超时保护

- **【强制】** 所有 `await` 调用外部资源（浏览器自动化、HTTP 客户端、IO 操作、远程 API）必须在**调用层**用 `asyncio.wait_for(coro, timeout=N)` 包装整体超时
- **【强制】** 超时时间必须从配置读取（`config.async_timeout.<operation>_seconds`），**禁止**硬编码
- **【强制】** 超时后必须返回语义化状态码（504=超时、502=失败、503=稍后重试），便于前端按状态码分类处理
- **【强制】** 超时日志必须记录操作类型 + 资源 ID + 超时秒数
- **【禁止】** 依赖被调用方内部 `timeout` 参数作为唯一超时保护（可能失效或不存在）
- **【禁止】** `asyncio.wait_for` 的 `TimeoutError` 吞掉 `asyncio.CancelledError`，应单独传播
- **适用**：所有 `await` 外部资源的异步操作
- **不适用**：有内建 timeout 的 HTTP 客户端（`httpx.Timeout` 已配置）、纯计算函数、`CancelledError` 传播路径

### 8.2 数据流转 5 点追踪

- **【强制】** 用户反馈"字段为空 / 显示异常 / 数据丢失"类问题时，必须按 **DB schema → Repo 查询过滤 → API 注入 → 前端 types → render 取值** 5 点逐层追踪根因
- **【强制】** 5 点必须**逐层验证**，不能跳过任何一层
- **【强制】** 每层验证必须**打印中间值**（如 `print(order_map)` / `console.log(record.order)`），不能凭推断
- **【强制】** 找到根因后必须**修复根因**而非绕过（如 Repo 过滤逻辑错误应修 Repo，而非 API 层重新查询）
- **【强制】** 修复后必须**回归测试**覆盖该场景
- **适用**：所有"字段为空 / 显示异常 / 数据丢失"类根因定位
- **不适用**：UI 样式问题、纯前端计算字段、权限不足导致字段隐藏

### 8.3 过滤逻辑场景区分

- **【强制】** 同一查询函数被多个场景复用时，过滤逻辑必须**参数化场景标志**（如 `include_failed` / `include_deleted` / `scope`）
- **【强制】** 场景标志必须**默认安全**（如 `include_failed=False` 默认跳过失败，避免影响现有逻辑）
- **【强制】** 函数 docstring 必须说明**两种场景**的用途（操作判断 vs 展示历史）
- **【强制】** 调用方必须**显式传值**（如 `include_failed=True`），不依赖默认值
- **【强制】** 必须新增**回归测试**覆盖两种场景
- **【禁止】** 一刀切过滤（如 `if status == 'failed': continue`）导致展示页看不到完整数据
- **适用**：同一查询被"操作判断"与"展示历史"两种场景复用
- **不适用**：单一场景的查询、有独立 Repo 方法的查询、权限过滤（应单独抽取）

### 8.4 复用既有模式原则

- **【强制】** 新增功能前必须先 `grep` 项目内相似实现，复用既有 helper / 工具函数 / 模式
- **【强制】** 复用优先级：**项目内 helper > 标准库 > 第三方库 > 新实现**
- **【强制】** 复用必须**保持一致性**：调用方式、参数命名、返回值格式与已有函数一致
- **【强制】** 若已有函数不完全满足需求，应**扩展已有函数**而非新建（参考 8.3 参数化场景标志）
- **【推荐】** 在新增函数 docstring 中说明"为什么不复用 X"（如适用）
- **必须复用的常见模式**：
  - `asyncio.wait_for`（异步超时保护，参考 8.1）
  - `hmac.compare_digest`（凭据比较，防时序攻击）
  - `_escape_like`（SQL LIKE 转义）
  - `_utcnow`（UTC 时间）
  - `logger.warning`（告警日志）
- **适用**：所有新增功能 / 工具函数 / 帮助类 / 异步操作 / 安全相关代码
- **不适用**：业务完全独立的全新功能、性能优化重写、技术债清理重构

---

## 九、状态管理与日志治理规范 🆕v4.8

> **来源**：日志分析优化 + 代码评审复盘 — Cookie 失效导致 300+ WARNING 刷屏 + Edit 工具修改未生效

### 9.1 状态标志前置检查（B-DEV-STATE-FLAG-PRECHECK）

- **【强制】** 检测到异常状态（会话失效、Cookie 过期、服务降级、限流）后，必须设置状态标志
- **【强制】** 后续操作入口必须用 `getattr(self, "flag", False)` 检查标志，为 True 时提前返回 None/默认值
- **【强制】** 状态标志必须有**重置机制**（`grep "flag = False"` 确认重置点），否则等于永久禁用
- **【强制】** 调用方必须能处理 None 返回值（`grep` 所有调用点确认）
- **【强制】** 日志使用 `{}` 占位符（非 f-string），记录 DEBUG 级别（不刷屏）
- **【适用】** 会话失效、Cookie 过期、服务降级、限流、依赖不可用
- **【不适用】** 一次性错误（单条请求失败）、无恢复机制的场景、高频变化状态

### 9.2 日志级别动态降级（B-DEV-LOG-LEVEL-DOWNGRADE）

- **【强制】** 已知业务场景的错误日志可降级为更低级别，判断字符串必须提取为**模块级常量**（禁止魔法字符串）
- **【强制】** 常量必须注释标明文案来源（如 `# 文案来源：collection_service.py 的 CollectionError(502, ...)`）
- **【强制】** 只调整日志级别，不改变 HTTP 响应格式与状态码
- **【强制】** 未知错误必须保持 WARNING/ERROR 级别（确保新问题能被发现）
- **【强制】** 使用 `logger.log(log_level, ...)` 动态级别，用 `{}` 占位符
- **【适用】** 已知业务异常日志治理（Cookie 失效 502、重试中 WARNING）、外部依赖偶发失败
- **【不适用】** 未知错误、安全相关错误（不应降级）、首次出现的错误、需用户介入的错误

### 9.3 修改后验证流程（B-DEV-EDIT-VERIFY）

- **【强制】** 使用 Edit 工具修改文件后，必须立即用 Grep 或 Read 验证修改是否真正生效
- **【强制】** 验证标志必须是新增代码中的**唯一标识符**（变量名、函数名、常量名）
- **【强制】** 批量修改多个文件时，每个文件都需独立验证
- **【强制】** 重新执行 Edit 时，检查 `old_string` 是否在文件中唯一匹配
- **【适用】** 所有使用 Edit 工具的修改场景，尤其是批量修改多个文件时
- **【不适用】** Read/Write 工具（这些工具本身有返回验证）
