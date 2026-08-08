# 后端开发指南

> 本文档整合了闲鱼猎人后端开发规范与代码模板，是 Python + FastAPI + SQLAlchemy + Playwright 个性化后端开发的完整参考。

## 目录导航

- [一、开发规范](#一开发规范)
  - [1. 概述](#1-概述)
  - [2. 工程规约](#2-工程规约)
  - [3. 命名约定](#3-命名约定)
  - [4. 分层架构](#4-分层架构)
  - [5. 依赖注入容器](#5-依赖注入容器)
  - [6. 异步并发模型](#6-异步并发模型)
  - [7. 安全约束](#7-安全约束)
  - [8. 错误处理](#8-错误处理)
  - [9. 日志规约](#9-日志规约)
  - [10. 配置加载](#10-配置加载)
  - [11. 事件总线](#11-事件总线)
  - [12. 后台调度器](#12-后台调度器)
  - [13. 启动钩子](#13-启动钩子)
  - [14. 中间件链](#14-中间件链)
  - [15. Web 服务层](#15-web-服务层)
  - [16. 最佳实践](#16-最佳实践)
- [二、代码模板](#二代码模板)
  - [模板1：FastAPI 路由](#模板1fastapi-路由)
  - [模板2：仓储 Mixin](#模板2仓储-mixin)
  - [模板3：领域模型](#模板3领域模型)

---

## 一、开发规范

## 1. 概述

### 1.1 文档目的

本文档规范闲鱼猎人后端开发流程，确保代码质量、可维护性与项目硬约束遵守。

### 1.2 适用范围

- 闲鱼猎人后端所有功能开发（`src/xianyu_hunter/`）
- 领域模型、仓储、业务模块、Web 路由、中间件、服务
- 异步任务、调度器、事件总线、配置加载

### 1.3 核心原则

- **分层严格**：依赖单向 `web → modules → infra → domain`，domain 不依赖任何层
- **Composition Root**：`container.py` 合法依赖所有层，是唯一装配点
- **Mixin 组合**：仓储用 Mixin 组合模式，避免单文件膨胀
- **异步优先**：IO 密集型全 async，SQLite 仓储同步实现
- **幂等迁移**：所有 DB schema 变更幂等，已存在则跳过
- **解释"为什么"**：注释说明设计权衡与历史教训

### 1.4 技术栈

- **Python** >=3.10（Docker 3.12-slim）
- **FastAPI** 0.136.3 + uvicorn 0.48.0
- **SQLAlchemy** 2.0.50（DeclarativeBase + Mapped + mapped_column）
- **pydantic** 2.13.4 + pydantic-settings 2.14.1
- **Playwright** 1.60.0（浏览器自动化）
- **APScheduler** 3.11.2（后台调度）
- **loguru** 0.7.3（日志）
- **keyring** 25.7.0（Windows DPAPI 密钥存储）
- **tenacity** 9.1.4（重试）
- **cryptography** 49.0.0（Chrome Cookie 解密）
- **chromadb** >=1.0.0（向量库）
- **pytest** 9.0.3 + pytest-asyncio 1.4.0（测试）

---

## 2. 工程规约

### 2.1 包发现

- **src layout**：`pyproject.toml` 配置 `packages.find where = ["src"]`
- **包数据**：`xianyu_hunter = ["web/static/**/*"]`（包含 SPA 静态资源）
- **脚本入口**：`xianyu-hunter = xianyu_hunter.__main__:app`（Typer CLI）

### 2.2 pytest 配置

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
asyncio_mode = "auto"  # 自动识别 async 测试函数
```

### 2.3 版本管理

- **版本源头**：`src/xianyu_hunter/__init__.py::__version__`
- **同步工具**：`scripts/bump_version.py` 同步到 `pyproject.toml`、`_build_info.py`、`CHANGELOG.md`
- **禁止**：`pyproject.toml` 中使用 `dynamic = ["version"]`（About API 需运行时反射）
- **规范**：Semantic Versioning 2.0.0

### 2.4 Docker 构建

- **不使用 requirements.txt**：包含 pythonnet/pywin32 等 Windows 专用包会在 Linux 失败
- **改用**：`pip install --no-cache-dir --user -e .` 基于 `pyproject.toml`
- **三阶段构建**：frontend（node:20-alpine）→ builder（python:3.12-slim）→ runtime（python:3.12-slim）

---

## 3. 命名约定

### 3.1 文件命名

| 类型 | 规范 | 示例 |
|---|---|---|
| 领域模型 | `<域>.py` | `domain/task.py`、`domain/evaluation.py` |
| 仓储 Mixin | `repo_<域>.py` | `repo_tasks.py`、`repo_chatbot.py` |
| 业务模块 | `<域>.py` 或 `<域>/` 子包 | `modules/buyer.py`、`modules/chatbot/` |
| Web 路由 | `api_<域>.py` | `api_tasks.py`、`api_chatbot.py` |
| 中间件 | `<名>.py` | `auth.py`、`request_id.py`、`exception_handler.py` |
| Web 服务 | `<名>.py` 或 `<名>_manager.py` | `auth_manager.py`、`cookie_store.py` |
| 测试 | `test_<被测>.py` | `test_collector.py`、`test_cookie_layer_sync_fix.py` |

### 3.2 标识符命名

| 类型 | 规范 | 示例 |
|---|---|---|
| 类 | PascalCase | `TaskWorker`、`NotifierHub`、`PriorityBrowserLock` |
| 方法/函数 | snake_case | `run_once`、`build_worker_from_raw_task` |
| 私有方法/属性 | 单下划线前缀 | `_workers`、`_dispatch`、`_session_locks` |
| 模块级常量 | UPPER_SNAKE_CASE | `_MAX_SSE_CONNECTIONS`、`DEFAULT_NOTIFY_EVENTS` |
| 枚举 | UPPER_SNAKE_CASE，继承 `str, Enum` | `TaskMode.AUTO`、`EventType.EVAL_PASSED` |
| 领域模型 | 无后缀 | `Task`、`ItemSummary`、`OrderSnapshot` |
| DB Row 类 | `*Row` 后缀 | `TaskRow`、`ItemRow` |
| 配置类 | `*Config` 后缀 | `AppConfig`、`BrowserConfig` |

### 3.3 方法命名

- CRUD：`upsert_<entity>` / `get_<entity>` / `list_<entity>` / `count_<entity>` / `update_<entity>_status`
- 业务动词：`refresh_links` / `cleanup_old_batch_refresh_history` / `auto_migrate_task_links`
- 异步方法：`async def` 无需 `async` 后缀
- 事件处理：`on_<event>` 或 `_handle_<scenario>`

---

## 4. 分层架构

### 4.1 四层职责

| 层 | 目录 | 职责 | 依赖 |
|---|---|---|---|
| **domain** | `domain/` | 纯领域模型（dataclass + Enum），无 IO 依赖 | 无 |
| **infra** | `infra/` | 基础设施：DB / 仓储 / 事件总线 / 日志 / 密钥 / 配置 / ContextVar | domain |
| **modules** | `modules/` | 业务模块：采集 / 评估 / 购买 / 通知 / 调度 / 客服 | infra + domain |
| **web** | `web/` | FastAPI 表现层：路由 / 中间件 / 服务 / SPA 静态资源 | modules + infra + domain |

### 4.2 依赖方向

- 依赖严格**单向**：`web → modules → infra → domain`
- **Composition Root** 在 `xianyu_hunter.container`，合法依赖所有层
- **反向依赖用 `TYPE_CHECKING` + 字符串注解**避免循环导入
  ```python
  from typing import TYPE_CHECKING
  if TYPE_CHECKING:
      from xianyu_hunter.domain.item import ItemSummary
  ```
- **延迟导入**解决循环依赖：`startup.py → app.py → container.py` 间用 `partial(_callback, self)` 包装

### 4.3 架构思想

属于 **DDD Lite + Clean Architecture 混合**：
- DDD 特征：明确的领域模型层；领域事件（`EventType` 枚举 35 种）；仓储模式分离持久化
- Clean Architecture 特征：Composition Root 显式装配；用例层纯编排；infra 接口可替换（容器支持 fake 注入）
- **没有**完整 Application Service 层——`web/routes` 直接调用 `container.repo` 与 `container.scheduler`

---

## 5. 依赖注入容器

### 5.1 Container dataclass

文件：`src/xianyu_hunter/container.py`

```python
@dataclass
class Container:
    """Composition Root，合法依赖所有层。"""
    config: AppConfig
    repo: Repository
    event_bus: EventBus
    browser: BrowserManager | None
    antidetect: AntiDetect | None
    collector: Collector | None
    dedup: Dedup
    price_strategy: PriceStrategy
    evaluator: Evaluator
    buyer: Buyer | None
    notifier_hub: NotifierHub
    scheduler: TaskScheduler
    browser_lock: PriorityBrowserLock
    chatbot: ChatbotContainer | None
```

### 5.2 build_default_container 工厂

```python
def build_default_container(
    config: AppConfig,
    db_path: Path,
    with_browser: bool = True,
) -> Container:
    """装配容器。
    
    with_browser=False 时跳过 BrowserManager/AntiDetect/Collector/Buyer 构造，
    Web 进程节省 100-200MB 内存（硬约束）。
    """
```

### 5.3 关键设计

- **Evaluator 构造时不传 thresholds/weights/keywords 覆盖参数**
  - 一旦传了就被存为 `_override_*` 永远返回覆盖值
  - 导致用户配置页面修改后不生效
  - 每次 `evaluate()` 从 `get_config()` 实时读取阈值
- **chatbot 子容器深拷贝配置**
  - 避免 `settings.openai_model` 污染 `get_config()` 全局单例
  - chromadb 等可选依赖缺失时返回 None
- **wire_notifier() 通过 `model_dump()` 自动收集所有为 True 的渠道字段**
  - 避免新增渠道时遗漏
  - `yaml_credentials` 作为 keyring 的 fallback
  - `subscribed_events` 仅匹配已知 EventType，跳过 `chatbot.*` 等不该通过 NotifierHub 推送的事件
- **build_worker_from_raw_task(raw) 统一 CLI 与 Web 的 Worker 构造**
  - 支持任务级 `search_config / price_config / eval_config` 覆盖
  - None 沿用全局

---

## 6. 异步并发模型

### 6.1 async/await 使用规范

- **IO 密集型全 async**：HTTP / 浏览器 / DB 长查询
  - `collector.search` / `buyer.buy` / `event_bus.run_forever` / `agent._call_llm`
- **SQLite 仓储同步实现**
  - 注释明确："SQLite + 单进程足够，后续如需异步访问可加 async 包装层"
- **后台任务用 `asyncio.create_task`**，保留引用防 GC
  ```python
  self._session_task = loop.create_task(self._run_session())
  ```

### 6.2 跨线程提交 async 任务

```python
# APScheduler BackgroundScheduler 线程 → 主事件循环
import asyncio
from functools import partial

def _submit_to_loop(coro, loop):
    """从同步线程提交协程到主事件循环。"""
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=30)  # 同步等待结果
```

### 6.3 asyncio.CancelledError 处理

- **`with suppress(asyncio.CancelledError)` 包裹 await 已取消的子任务**
  ```python
  from contextlib import suppress
  import asyncio
  
  async def shutdown(self):
      for task in self._tasks:
          task.cancel()
      for task in self._tasks:
          with suppress(asyncio.CancelledError):
              await task
  ```
- **`raise` 重新抛出以传播取消信号**（符合 S7497）

### 6.4 asyncio.timeout / wait_for

- **`asyncio.timeout`** 控制总超时（Agent 工具调用）
  ```python
  async with asyncio.timeout(tool_total_timeout_sec):
      result = await self._call_llm(messages)
  ```
- **`asyncio.wait_for`** 控制 queue.get 超时（EventBus 1.0s 超时让 while 循环可响应 stop）
  ```python
  event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
  ```

### 6.5 Windows 信号处理

- `loop.add_signal_handler` 在 Windows 抛 `NotImplementedError`
- 用 try/except 跳过
  ```python
  try:
      loop.add_signal_handler(signal.SIGINT, self._handle_sigint)
  except NotImplementedError:
      pass  # Windows 不支持
  ```

### 6.6 get_running_loop 替代 get_event_loop

- `get_running_loop`：无运行循环时抛 RuntimeError 走 except 分支
- `get_event_loop`：在 3.12+ 已弃用

### 6.7 PriorityBrowserLock

自定义优先级锁，high 优先级（live 端点）通过 `_high_waiting` 计数器让 Worker 在搜索完成后主动让出。

**关键约束**：不改变 asyncio.Lock 的 FIFO 语义以避免复杂竞态。

---

## 7. 安全约束

### 7.1 Token 校验

- **必须使用 `hmac.compare_digest`** 恒定时间比较防时序攻击
  ```python
  import hmac
  if hmac.compare_digest(token, expected_token):
      # 通过
  ```
- **session_token 的 sha256 哈希存储**（防库泄露后伪造）
  ```python
  import hashlib
  token_hash = hashlib.sha256(token.encode()).hexdigest()
  ```

### 7.2 敏感字段不日志

```python
_SENSITIVE_HEADERS = {"authorization", "cookie", "xh_token", "set-cookie"}

def _sanitize_headers(headers: dict) -> dict:
    return {k: "<REDACTED>" if k.lower() in _SENSITIVE_HEADERS else v 
            for k, v in headers.items()}
```

**注意**：`exception_handler.py` 和 `error_capture.py` 两处独立实现 `_sanitize_headers`，新增敏感头时两处都要更新。

### 7.3 SQL 注入防护

- **LIKE 用 `_escape_like`** 转义通配符
  ```python
  def _escape_like(s: str) -> str:
      return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
  ```
- **表名/列名用 `_IDENT_RE` 白名单校验**
  ```python
  _IDENT_RE = re.compile(r"^[A-Za-z_]\w*$", re.ASCII)
  if not _IDENT_RE.match(table_name):
      raise ValueError(f"Invalid table name: {table_name}")
  ```

### 7.4 路径遍历防护

```python
_USER_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

def _cookie_json_path(user_id: str) -> Path:
    if not _USER_ID_RE.match(user_id):
        raise ValueError(f"Invalid user_id: {user_id}")
    return DATA_DIR / f"cookies_{user_id}.json"
```

### 7.5 request_id 格式校验

```python
# 防止客户端通过 X-Request-Id 头注入任意字符串到日志
def is_valid_request_id(rid: str) -> bool:
    return bool(re.match(r"^req-\d{17}-[0-9a-f]{6}$", rid))
```

### 7.6 chatbot 敏感字段脱敏

```python
def _filter_sensitive(obj):
    """递归遍历 dict/list，键名匹配敏感模式时替换值为 <REDACTED>。"""
    if isinstance(obj, dict):
        return {k: "<REDACTED>" if _is_sensitive(k) else _filter_sensitive(v) 
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [_filter_sensitive(i) for i in obj]
    return obj
```

### 7.7 Cookie 测试数据拦截

```python
_TEST_COOKIE_VALUES = {"test", "123456", "fake_cookie", ...}
_COOKIE_FORMAT_PATTERNS = [re.compile(r"..."), ...]

def _is_real_cookie(value: str) -> bool:
    if value.lower() in _TEST_COOKIE_VALUES:
        return False
    return any(p.match(value) for p in _COOKIE_FORMAT_PATTERNS)
```

### 7.8 密钥存储

- **keyring 首选**（Windows DPAPI / macOS Keychain / Linux Secret Service）
- **fallback 到 base64 + 文件权限 600**（注释明确："base64 不是加密，仅防肉眼"）
- **启动时打印警告**：fallback 时记录 warning
- **migrate_from_env**：从 .env 读取敏感 Key 迁移到 keyring，成功后替换为 `__MIGRATED_TO_KEYRING__` 占位符

### 7.9 认证白名单

`BearerAuthMiddleware` 的 `PUBLIC_PREFIXES`：
- `/static/` / `/healthz` / `/app/`
- `/api/auth/login` / `/api/events/stream`
- `/api/about` / `/api/about/check-update`
- `/api/auth/cookie` / `/api/auth/me` / `/api/auth/import-from-browser`
- `/api/notifications` / `/api/notifier/`

**新增公开端点必须同步更新白名单**。

---

## 8. 错误处理

### 8.1 三层兜底

1. **路由层 try-except**：捕获业务异常返回合适的 HTTP 状态码
2. **`register_exception_handlers`**：兜底未捕获异常
3. **loguru**：记录完整堆栈

### 8.2 异常处理响应

```python
# Exception → 500
{"detail": "内部服务器错误", "code": "internal_error", "request_id": "req-..."}

# RequestValidationError → 422（保留 FastAPI errors 结构）
{"detail": [...], "code": "validation_error", "request_id": "req-..."}

# HTTPException → 保持原有 status_code 与 detail
```

**禁止**向前端暴露堆栈。

### 8.3 业务异常分层

- **领域层定义异常基类**：`BuyerError` → 子类 `PriceMismatchError` / `OutOfStockError` / `ButtonNotFoundError` / `ItemSoldError`
- **调度层定义**：`ResumeBlockedError`（注释明确："scheduler 是纯 Python 调度层，不应感知 HTTP 语义"）

### 8.4 异常隔离

- **`_safe_call` 捕获 handler 异常**：单个 handler 失败不影响其他
- **迁移块独立 try/except**：避免连锁失败
  ```python
  # 历史教训：auto_migrate_task_links 抛异常会让后续迁移全跳过，
  # 外层 try/except 吞掉异常，最终 schema 与 ORM 不一致
  try:
      auto_migrate_task_links(engine)
  except Exception as e:
      logger.warning(f"task_links 迁移失败: {e}")
  try:
      _migrate_add_column(engine, "items", "is_sold", Boolean)
  except Exception as e:
      logger.warning(f"items.is_sold 迁移失败: {e}")
  ```
- **可选依赖 `ImportError` 降级为 info 不阻断主系统**
  ```python
  try:
      import chromadb
  except ImportError:
      logger.info("chromadb 未安装，chatbot 功能不可用")
      chromadb = None
  ```

### 8.6 错误日志写入失败不阻断主流程

```python
async def _save_error_log(...):
    try:
        await repo.save_error_log(...)
    except Exception as e:
        logger.error(f"错误日志写入失败: {e}")  # 仅记录到 loguru
```

### 8.7 会话失效处理与错误粒度区分 🆕v4.1

**问题背景**：实时搜索触发 RGV587 重试失败后，代码未检查 `last_session_invalid` 状态标志，继续走 filtering 流程，前端只收到 `stage="done"` + 0 商品，误以为"真的没货"，实际是闲鱼登录态已过期（`_m_h5_tk` 失效）。

#### 8.7.1 重试失败后状态信号必须传递

**强制规则**：SSE/HTTP 接口包含重试逻辑时，重试代码块结束后必须检查关键状态标志，状态仍异常则推送明确错误事件并 `return`，**禁止**"重试失败但仍走成功流程"。

```python
# ✅ 推荐：重试后检查状态标志
raw_results = await retry_search(...)
if not raw_results and getattr(container.collector, "last_session_invalid", False):
    yield sse({
        "stage": "error",
        "detail": "闲鱼登录态已过期，请前往「反爬登录管理」重新登录闲鱼",
        "status": 403,
    })
    return
# 只有 last_session_invalid=False 时才走 filtering 流程
logger.info("搜索返回 raw_results={}", len(raw_results))
```

```python
# ❌ 反面：重试后不检查状态直接走后续流程
raw_results = await retry_search(...)
logger.info("raw_results={}", len(raw_results))  # 0 商品但未检查 session_invalid
# 继续走 filtering → 前端误以为"真的没货"
```

#### 8.7.2 错误粒度三类区分

面向用户的错误响应必须按粒度区分（状态码与文案映射在 review skill 的 `config.yaml` 中管理，避免硬编码）：

| 状态码 | 场景 | 用户行动 | 示例 |
|--------|------|---------|------|
| `503/504` | 网络超时/限流/服务繁忙 | 稍后重试 | "实时搜索重试超时，请稍后再试" |
| `401/403` | 登录失效/权限不足 | 需用户介入 + 明确指引 | "闲鱼登录态已过期，请前往「反爬登录管理」重新登录" |
| `502` | 浏览器断开/TargetClosed | 需重启服务 | "浏览器连接断开，请重启服务" |

**判断信号**：
- 错误源于 `_m_h5_tk` 过期、身份 Cookie 失效 → 401/403
- 错误源于 `asyncio.TimeoutError`、网络不可达 → 503/504
- 错误源于 `TargetClosedError`、`PlaywrightProcessCrash` → 502

#### 8.7.3 Cookie 检查全面性

依赖多类 Cookie 的接口前置检查必须覆盖**所有**关键 token：

```python
# ✅ 推荐：检查身份 Cookie + 会话 token
_LIVE_SEARCH_IDENTITY_COOKIES = ("cookie2", "sgcookie", "unb")  # 身份 Cookie
_SESSION_TOKEN_KEY = "_m_h5_tk"  # 会话 token

def _ensure_live_search_cookies(container):
    # 检查身份 Cookie 存在性
    for name in _LIVE_SEARCH_IDENTITY_COOKIES:
        if not _cookie_exists(name):
            raise HTTPException(401, "身份 Cookie 缺失，请重新登录")
    # 检查会话 token 有效性（不能只检查身份 Cookie）
    if _is_session_token_expired(_SESSION_TOKEN_KEY):
        raise HTTPException(401, "会话 token 已过期，请重新登录")
```

```python
# ❌ 反面：只检查身份 Cookie，忽略会话 token
def _ensure_live_search_cookies(container):
    for name in ("cookie2", "sgcookie", "unb"):
        if not _cookie_exists(name):
            raise HTTPException(401, "身份 Cookie 缺失")
    # _m_h5_tk 已过期但未检查 → 搜索仍会失败
```

#### 8.7.4 对照证据定位法（问题排查）

用户反馈"业务查不到"但无明确错误时，排查首要步骤：

1. **要求用户提供对照证据**："相同条件下浏览器直连成功"的 URL
2. **浏览器直连成功** → 聚焦 Cookie/会话状态（非网络/代理问题）
   - 检查 `_m_h5_tk` 有效性（搜索 `data/logs/xianyu_*.log` 中"过期 _m_h5_tk"）
   - 检查 RGV587 反爬触发（搜索日志中"RGV587"）
   - 检查 `last_session_invalid` 状态（搜索日志中"会话失效"）
3. **浏览器直连失败** → 检查系统网络/代理配置
   - 搜索日志中 `ERR_PROXY_CONNECTION_FAILED`、`ERR_INTERNET_DISCONNECTED`
   - 检查 `config/config.yaml` 的 `proxy_server` 配置
   - 检查 `browser-data/Default/Preferences` 中的 proxy 字段

#### 8.7.5 适用与不适用场景

| 规则 | 适用 | 不适用 |
|------|------|--------|
| 重试失败状态信号传递 | 含 fast/slow 重试逻辑的 SSE/HTTP 接口 | 一次性请求无重试逻辑；重试后状态不可观测 |
| 错误粒度区分 | 面向用户的 API，需用户根据错误决策 | 内部服务间调用（用 gRPC status code 即可） |
| Cookie 检查全面性 | 依赖多类 Cookie（身份 + 会话）的接口 | 单一 Cookie 检查；纯 token 认证（JWT） |
| 对照证据定位法 | 用户反馈"业务查不到"但无错误 | 系统级故障（服务挂了、端口被占用） |

### 8.8 错误日志表字段

`error_logs` 表包含完整诊断信息：
- 完整堆栈
- 请求上下文（脱敏 headers、path、method、query_params）
- 服务器环境（Python 版本、平台、进程 ID）
- AI 诊断上下文：`ai_context_json`（结构化）+ `ai_context_md`（Markdown 报告，含可能原因推断）

---

## 9. 日志规约

### 9.1 loguru 三 sink

文件：`src/xianyu_hunter/infra/logger.py`

1. **stderr**（彩色，含 `[req={extra[request_id]}]` token）
2. **JSON 文件**（`data/logs/xianyu_{time}.log`，按日滚动，保留 14 天，`serialize=True`）
3. **纯文本文件**（`run.stdout.log`，10MB 轮转，保留 3 个备份，供 SSE 流消费）

### 9.2 request_id ContextVar + patcher 钩子

```python
# 关键设计：通过 logger.configure(patcher=...) 在每条日志记录前
# 从 ContextVar 读取 request_id 注入到 record["extra"]，业务代码无需手动 bind
def _patcher(record):
    record["extra"].setdefault("request_id", get_current_request_id() or "-")

logger.configure(patcher=_patcher)
```

### 9.3 日志级别选择

| 级别 | 使用场景 |
|---|---|
| `logger.debug` | 详细调试信息（生产关闭） |
| `logger.info` | 关键业务节点（任务启动/完成、登录成功、配置更新） |
| `logger.warning` | 可恢复异常、降级、fallback |
| `logger.error` | 错误日志写入失败、关键依赖初始化失败 |
| `logger.exception` | 捕获异常时记录完整堆栈 |

### 9.4 日志内容规范

- **禁止打印敏感字段**：`_SENSITIVE_HEADERS` 脱敏
- **只记录布尔匹配结果，不记录 token 长度**
- **Token 写入失败必须 `logging.warning()` 警告**

### 9.5 loguru 格式规范（禁用 printf 风格） 🆕

**问题背景**：项目中部分模块使用 `%s`/`%d`/`%f` printf 风格占位符，loguru 不解析这些占位符，导致日志参数未替换，输出原始 `%s` 字符串，严重影响可观测性。

**强制规则**：loguru 日志必须使用 `{}` 占位符风格：

```python
# ✅ 正确：loguru {} 占位符
logger.info("task={} rows={} elapsed={:.1f}ms", task_id, rows, elapsed_ms)

# ❌ 错误：printf %s/%d 占位符（loguru 不解析）
logger.info("task=%s rows=%d", task_id, rows)  # 输出 "task=%s rows=%d"
```

**审查要点**：
- 在 `logger.xxx(...)` 调用中出现 `%s`、`%d`、`%f` → 违规
- 异常日志必须包含异常对象：`logger.error("msg", e)`（loguru 自动格式化）
- 使用 `{:.1f}` 等格式说明符控制精度，而非 `%f`

**批量检测命令**：
```bash
# 搜索所有使用 printf 风格的 logger 调用
grep -rn 'logger\.\(info\|warning\|error\|debug\).*%[sdf]' src/xianyu_hunter/
```

---

## 10. 配置加载

### 10.1 三层配置源

1. **`.env` 文件**（`pydantic-settings`，`Settings` 类）：环境变量、敏感凭证（迁移到 keyring 后为占位符）
2. **`config/*.yaml`**（`AppConfig` Pydantic 模型）：业务配置，深度合并
3. **`keyring`**（Windows DPAPI）：敏感凭证首选

### 10.2 YAML 深度合并

文件：`src/xianyu_hunter/infra/yaml_config.py`

- **加载策略**：先加载子配置（`eval.yaml / notifier.yaml / browser.yaml`）作为基线，最后加载主配置（`config.yaml`）覆盖
- **修复了"抢单策略页面保存后刷新参数被重置"问题**（旧实现浅合并 + config.yaml 先加载导致 eval.yaml 整体覆盖）

### 10.3 配置校验

```python
class EvalWeights(BaseModel):
    professional: int = 30
    credit: int = 30
    dispute: int = 25
    price: int = 15
    
    @model_validator(mode="after")
    def _check_weight_sum(self):
        # 权重和必须为 100
        if self.professional + self.credit + self.dispute + self.price != 100:
            raise ValueError("权重和必须为 100")
        return self

class EvalConfig(BaseModel):
    pass_score: int = 60
    auto_buy_score: int = 80
    
    @model_validator(mode="after")
    def _check_score_order(self):
        # pass_score 不能大于 auto_buy_score
        if self.pass_score > self.auto_buy_score:
            raise ValueError("pass_score 不能大于 auto_buy_score")
        return self
```

### 10.4 单例 + 热更新

```python
from functools import lru_cache

@lru_cache
def get_config() -> AppConfig:
    """全局单例配置。"""
    return _load_config()

def reload_config():
    """重置缓存，下次调用重新加载。"""
    get_config.cache_clear()
```

### 10.5 任务级配置覆盖

DB 中 `search_config / price_config / antidetect_config / eval_config` JSON 字段：
- None 沿用全局
- 运行时深度合并

---

## 11. 事件总线

文件：`src/xianyu_hunter/infra/event_bus.py`

### 11.1 核心 API

- `subscribe(event_type, handler)`：订阅事件
- `publish(event)`：入队事件（不阻塞）
- `publish_nowait(event)`：非阻塞入队
- `run_forever()`：主循环（独立 asyncio.Task）

### 11.2 关键设计

- **基于 `asyncio.Queue`** 的进程内事件分发
- **自动注入 request_id**：调用方未显式指定时从 `ContextVar` 读取
  - 注释说明："publish 只是入队，实际分发发生在异步任务恢复后，此时 ContextVar 才是当前请求的作用域"
- **`_safe_call` 捕获所有异常**：单个 handler 失败不影响其他
- **`asyncio.gather` 并发执行 handler**：`return_exceptions=False`（_safe_call 内部已隔离异常）
- **全局单例 `get_event_bus()`**

### 11.3 EventType 枚举

共 **35 种**：主系统 22 种 + 智能客服 13 种。

命名约定 `<域>.<动作>`：
- `task.started` / `task.paused` / `task.stopped` / `task.error`
- `eval.passed` / `eval.rejected`
- `buy.succeeded` / `buy.failed` / `buy.requested`
- `item.discovered` / `item.sold`
- `waf.triggered` / `login.expired`
- `chatbot.kb.rebuilt` / `chatbot.degraded`

### 11.4 EVENT_SEVERITY

字典分三级：`critical / important / info`，用于免打扰时段决策。

chatbot 严重度用 `setdefault` 幂等写入，保持主字典简洁。

---

## 12. 后台调度器

### 12.1 5 类调度器

| 调度器 | 实现方式 | 启动条件 |
|---|---|---|
| 主任务调度器 | asyncio.Task | `_should_start_scheduler()` |
| EventBus | asyncio.Task（独立于调度器） | 始终启动（避免链式失败） |
| Cookie 同步 | APScheduler BackgroundScheduler | `browser.auto_sync=true` |
| 批量采集 | APScheduler + `run_coroutine_threadsafe` | collector 非 None |
| KB 刷新 | APScheduler | chatbot 可选模块 |
| 接管超时清理 | 独立于 with_browser | 始终启动（纯 DB） |

### 12.2 解耦设计

- **EventBus 独立于"是否有 RUNNING 任务"**：避免链式失败
  - 历史教训：原实现把 `run_forever()` 放在 `_scheduler_loop` 内部，导致无 RUNNING 任务时 EventBus 不启动

### 12.3 任务调度模式

- `use_cron=True`：按 cron 表达式（基于 APScheduler `CronTrigger`，5 字段，UTC 时区）
- `use_cron=False`：按 `interval_seconds` 固定间隔（默认 60s）

### 12.4 全局并发锁

```python
class TaskScheduler:
    _run_lock: asyncio.Lock  # 同一时间只允许一个 task 执行 run_once
    _workers_lock: asyncio.Lock  # 保护 _workers 字典并发修改
```

**设计原因**：避免多任务并发打开多个浏览器页面弹窗。

### 12.5 会话失效冷却期

```python
import time
_RESUME_COOLDOWN_SECONDS = 300

# 用 time.monotonic（不受系统时钟调整影响）
self._resume_cooldown_until = time.monotonic() + _RESUME_COOLDOWN_SECONDS
```

---

## 13. 启动钩子

文件：`src/xianyu_hunter/web/startup.py`

### 13.1 setup_startup_hooks(app)

```python
def setup_startup_hooks(app: FastAPI):
    @app.on_event("startup")
    async def _startup():
        setup_logging()
        container = get_container()
        run_migrations(container)  # 增量迁移（C-01 ~ C-06，独立 try/except）
        if _should_start_scheduler():
            start_event_bus_in_background(container)  # 先启动 EventBus（幂等防护）
            start_scheduler_in_background(container)
        start_cookie_sync_scheduler(container)       # browser.auto_sync=true 时
        start_batch_refresh_scheduler(container)     # collector 非 None 时
        start_kb_refresh_scheduler(container)        # chatbot 可选模块
        start_takeover_timeout_scheduler(container)  # 始终启动
        trigger_session_start()                      # 反爬会话管理（TokenRenewer）
    
    @app.on_event("shutdown")
    async def _shutdown():
        # 反向关闭：KB → Batch → Cookie → Takeover → Scheduler → EventBus（最后停）
        with suppress(asyncio.CancelledError):
            await _shutdown_all()
```

### 13.2 关闭顺序

反向关闭：KB 调度器 → Batch → Cookie → Takeover → Scheduler → EventBus（最后停，因为 scheduler stop_all 时仍可能 publish 事件）。

`with suppress(asyncio.CancelledError)` 包裹 await 防止中断 cleanup。

---

## 14. 中间件链

### 14.1 执行顺序

**LIFO 后注册先执行**：`RequestIdMiddleware → BearerAuthMiddleware → 路由`。

注册顺序：`setup_auth_middleware` → `setup_request_id_middleware` → `register_exception_handlers`。

### 14.2 RequestIdMiddleware

- 从 `X-Request-Id` 头读取（需通过 `is_valid_request_id` 格式校验防注入）
- 否则生成新流水号：`req-{YYYYMMDDHHMMSSfff}-{6位hex}`
- **双重存储**：`request.state` 同步 + `ContextVar` 异步
- 响应头回传 `X-Request-Id`
- `finally` 清理 ContextVar 防跨请求泄漏

### 14.3 BearerAuthMiddleware

```python
PUBLIC_PREFIXES = (
    "/static/", "/healthz", "/app/",
    "/api/auth/login", "/api/events/stream",
    "/api/about", "/api/about/check-update",
    "/api/auth/cookie", "/api/auth/me", "/api/auth/import-from-browser",
    "/api/notifications", "/api/notifier/",
)

# 三路径校验：
# 1. WEB_TOKEN 管理令牌直通
# 2. session_token 多用户会话校验
# 3. 校验失败 401 返回 JSON {"detail": "Unauthorized"}
```

### 14.4 register_exception_handlers

- `Exception` → 500 `{"detail": "内部服务器错误", "code": "internal_error", "request_id": ...}`
- `RequestValidationError` → 422 保留 FastAPI errors 结构
- `HTTPException` → 保持原有 status_code 与 detail
- 敏感请求头脱敏

---

## 15. Web 服务层

### 15.1 AuthManager

- **单例**：缓存 `/api/auth/me` 结果（5 分钟 TTL）
- **后台异步启动 `auth_helper.py` 子进程**：拉取/刷新登录信息，subprocess 隔离崩溃不影响 web
- **状态机**：`idle → starting → opening → qr_ready → success / timeout / error / cancelled`

### 15.2 CookieStore

- **JSON 文件存储替代 SQLite 读取**：浏览器 Cookie 写入 SQLite 是异步的，直接读取不可靠
- **按 `user_id` 隔离**（MU2 改造）：`_USER_ID_RE` 白名单防路径遍历
- **`_COOKIE_FORMAT_PATTERNS` 正则校验真实 Cookie 格式**，拦截测试数据

### 15.3 session_starter.trigger_session_start()

- 登录成功后自动启动会话管理（fire-and-forget）
- 被 `unified_login / browser_login / browser_import / cookie_inject` 4 个登录入口调用

### 15.4 user_manager

- 多用户会话管理
- `session_token` 的 sha256 哈希存储（防库泄露后伪造）
- 原始 token 仅存 cookie

### 15.5 SSE 流式接口

文件：`src/xianyu_hunter/web/routes/sse_stream.py`

```python
_MAX_SSE_CONNECTIONS = 10  # 防止多标签页耗尽资源

# 每条事件含 id 字段以启用断线回放
def _format_sse_event(event: Event) -> str:
    return f"id: {event.id}\nevent: {event.type}\ndata: {json.dumps(event.payload)}\n\n"

# Last-Event-ID 头或 last_event_id 查询参数
```

### 15.6 查询过滤下推原则 🆕

**问题背景**：部分查询方法先 `SELECT *` 全量加载到内存，再在 Python 层做过滤和切片，导致内存浪费和性能下降。

**强制规则**：查询方法设计时，按以下优先级下推过滤条件：

| 优先级 | 层级 | 适用场景 | 示例 |
|--------|------|----------|------|
| 1（最高） | SQL WHERE | 等值/范围/LIKE 过滤 | `WHERE task_id=? AND link_type=?` |
| 2 | SQL ORDER BY + LIMIT/OFFSET | 排序与分页 | `ORDER BY created_at DESC LIMIT 20 OFFSET 0` |
| 3（最低） | Python 层 | SQL 无法表达的逻辑 | 中文分词匹配、跨行聚合后过滤 |

**违规模式**：
```python
# ❌ 全量加载 + Python 过滤 + 内存切片
all_rows = conn.execute(select(TaskLinkRow).where(...)).all()
filtered = [r for r in all_rows if some_filter(r)]  # Python 层过滤
page = filtered[offset:offset + limit]  # 内存切片
```

**正确模式**：
```python
# ✅ 过滤下推 SQL + SQL 分页
stmt = select(TaskLinkRow).where(
    TaskLinkRow.task_id == task_id,
    # 过滤条件下推到 SQL
    func.json_extract(TaskLinkRow.display, '$.price') >= min_price,
).order_by(TaskLinkRow.created_at.desc()).limit(limit).offset(offset)
```

**JSON 字段过滤下推**：SQLite 支持 `json_extract` + `CAST` + `LIKE` 组合，可将存储在 JSON 字段中的价格、关键词、地区等过滤条件下推到 SQL 层。

**适用场景**：所有 Repository 层查询方法
**不适用场景**：需要跨行聚合后再过滤的场景（如先 GROUP BY 再 HAVING）、Python 专有逻辑（如 jieba 分词匹配）

---

## 16. 最佳实践

### 16.1 模块级 docstring

每个文件开头说明职责 + 设计要点 + 引用设计文档：
```python
"""采集器模块，负责闲鱼商品搜索与详情抓取。

设计要点：
- Mixin 组合架构：SearchMixin + ParserMixin + DetailMixin + CollectorBase
- 依赖 BrowserManager + AntiDetect + PriorityBrowserLock

参考：docs/02-数据查看/商品列表-详细设计.md §3.1
"""
```

### 16.2 注释解释"为什么"

```python
# 为什么用 NullPool 而非 StaticPool：
# StaticPool 全进程共享单连接，sqlite3.Connection 不是线程安全对象，
# 多线程并发 cursor 竞争触发 InterfaceError
engine = create_engine(url, poolclass=NullPool, connect_args={"check_same_thread": False})
```

### 16.3 版本化标记

```python
# C-01 修复：从 infra/ 迁出 container，修复反向依赖违例
# F-16：任务依赖关系
# MU1：多用户改造
# M2：收藏置顶
```

### 16.4 异步任务保留引用

```python
# 错误：task 会被 GC 回收
asyncio.create_task(self._run_session())

# 正确：保留引用
self._session_task = asyncio.create_task(self._run_session())
```

### 16.5 时间统一 UTC

```python
from datetime import datetime, timezone

# 正确
now = datetime.now(timezone.utc)

# 错误（已弃用）
now = datetime.utcnow()
```

### 16.6 状态标志前置检查模式（B-DEV-STATE-FLAG-PRECHECK）

> **来源**：日志分析优化复盘 — Cookie 失效导致 300+ WARNING 刷屏，根因是检测到失效后后续操作仍重复尝试。

**场景**：检测到异常状态（会话失效、Cookie 过期、服务降级、限流）后，后续操作入口必须检查标志提前返回，避免重复失败与日志刷屏。

```python
# 1. 检测到异常时设置标志
def _mark_detail_session_invalid(self, item_id: str, reason: str) -> None:
    self.last_session_invalid = True

# 2. 后续操作入口检查标志（使用 getattr 防御性编程）
async def detail(self, item_id: str, page: Page | None = None) -> ItemDetail | None:
    if getattr(self, "last_session_invalid", False):
        logger.debug("详情页 {} 跳过采集（会话已失效）", item_id)
        return None
    # ... 正常逻辑

# 3. 状态恢复时重置标志（必须有重置机制）
# grep "last_session_invalid = False" 确认重置点
```

**关键约束**：
- 必须有**重置机制**（grep `flag = False` 确认重置点），否则等于永久禁用
- 调用方必须能处理 `None` 返回值（grep 所有调用点确认）
- 使用 `getattr(self, "flag", False)` 防御性编程，避免 AttributeError
- 日志使用 `{}` 占位符（非 f-string），且记录 DEBUG 级别（不刷屏）

**适用场景**：会话失效、Cookie 过期、服务降级、限流、依赖不可用
**不适用场景**：一次性错误（单条请求失败）、无恢复机制的场景、高频变化状态

### 16.7 日志级别动态降级模式（B-DEV-LOG-LEVEL-DOWNGRADE）

> **来源**：代码评审复盘 — 502 采集失败日志刷屏，需对已知业务场景降级但不影响未知错误发现。

**场景**：已知业务场景的错误日志可降级为更低级别，避免高频重复错误刷屏，同时保持未知错误的告警能力。

```python
# 模块级常量（注释标明文案来源）
# 采集失败的 detail 标识，文案来源：collection_service.py 的 CollectionError(502, ...)
_COOKIE_EXPIRED_DETAIL_MARKER = "Failed to collect item detail"

async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if exc.status_code >= 500:
        # 已知业务场景降级为 INFO，其他 500+ 保持 WARNING
        is_known_business_error = exc.status_code == 502 and _COOKIE_EXPIRED_DETAIL_MARKER in str(exc.detail)
        log_level = "INFO" if is_known_business_error else "WARNING"
        logger.log(
            log_level,
            "HTTPException path={path} status={status} | {detail}",
            path=request.url.path,
            status=exc.status_code,
            detail=exc.detail,
        )
    # ... 响应格式不变
```

**关键约束**：
- 判断字符串必须提取为**模块级常量**（禁止魔法字符串），注释标明文案来源
- 只调整**日志级别**，不改变 HTTP 响应格式与状态码
- 未知错误必须保持 WARNING/ERROR 级别（确保新问题能被发现）
- 使用 `logger.log(log_level, ...)` 动态级别，用 `{}` 占位符

**适用场景**：已知业务异常的日志治理（Cookie 失效 502、重试中 WARNING）、外部依赖偶发失败
**不适用场景**：未知错误、安全相关错误（不应降级）、首次出现的错误、需用户介入的错误

### 16.8 修改后验证流程（B-DEV-EDIT-VERIFY）

> **来源**：代码评审复盘 — Edit 工具返回"修改成功"但实际修改未保存，导致评审了未修改的代码。

**场景**：使用 Edit 工具修改文件后，必须立即用 Grep 或 Read 验证修改是否真正生效。

```
# 1. Edit 返回成功 → 不信任返回结果
# 2. Grep 搜索新增的标志性代码（如新增的变量名、函数名）
# 3. 若 Grep 无匹配 → 重新执行 Edit，检查 old_string 是否唯一匹配
# 4. 若 Grep 有匹配 → 确认修改生效，继续下一步
```

**关键约束**：
- 验证标志必须是新增代码中的**唯一标识符**（变量名、函数名、常量名）
- 批量修改多个文件时，每个文件都需独立验证
- 重新执行 Edit 时，检查 `old_string` 是否在文件中唯一匹配

**适用场景**：所有使用 Edit 工具的修改场景，尤其是批量修改多个文件时
**不适用场景**：Read/Write 工具（这些工具本身有返回验证）

---

## 二、代码模板

## 模板1：FastAPI 路由

**文件位置**：`src/xianyu_hunter/web/routes/api_<域>.py`

```python
"""<域> API 路由。

设计要点：
- 路由前缀 /api/<域>，与文件名一一对应
- 通过 Depends(get_container) 注入容器
- 错误消息提取为常量（S1192 规则）
- 敏感数据脱敏

参考：docs/<模块>-详细设计.md §x.y
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from xianyu_hunter.web.deps import get_container

if TYPE_CHECKING:
    from xianyu_hunter.container import Container

# 错误消息提取为常量（S1192 规则）
_NOT_FOUND = "<域>不存在"
_FORBIDDEN = "无权限操作此<域>"
_VALIDATION_ERROR = "<域>参数校验失败"

router = APIRouter(prefix="/api/<域>", tags=["<域>"])


# Pydantic 请求模型
class <域>CreateBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=80, description="名称")
    description: str | None = Field(None, max_length=500, description="描述")


class <域>UpdateBody(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=80)
    description: str | None = Field(None, max_length=500)


class <域>Response(BaseModel):
    id: str
    name: str
    description: str | None
    created_at: str


@router.get("", response_model=list[<域>Response])
async def list_<域>(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str | None = Query(None, max_length=80),
    container: Container = Depends(get_container),
):
    """列表查询。<域>列表，支持分页与关键词搜索。"""
    items = container.repo.list_<域>(page=page, page_size=page_size, keyword=keyword)
    return [<域>Response(**item) for item in items]


@router.post("", response_model=<域>Response, status_code=201)
async def create_<域>(
    body: <域>CreateBody,
    container: Container = Depends(get_container),
):
    """创建<域>。"""
    try:
        item = container.repo.upsert_<域>(body.model_dump())
        return <域>Response(**item)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{item_id}", response_model=<域>Response)
async def get_<域>(
    item_id: str,
    container: Container = Depends(get_container),
):
    """详情查询。"""
    item = container.repo.get_<域>(item_id)
    if not item:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
    return <域>Response(**item)


@router.patch("/{item_id}", response_model=<域>Response)
async def update_<域>(
    item_id: str,
    body: <域>UpdateBody,
    container: Container = Depends(get_container),
):
    """更新<域>。"""
    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="无可更新字段")
    item = container.repo.update_<域>(item_id, update_data)
    if not item:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
    return <域>Response(**item)


@router.delete("/{item_id}", status_code=204)
async def delete_<域>(
    item_id: str,
    container: Container = Depends(get_container),
):
    """删除<域>（软删除）。"""
    success = container.repo.delete_<域>(item_id)
    if not success:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
```

## 模板2：仓储 Mixin

**文件位置**：`src/xianyu_hunter/infra/repo_<域>.py`

```python
"""<域> 仓储 Mixin。

设计要点：
- 通过 Mixin 组合到 Repository 类（infra/repository.py 聚合）
- 同步实现（SQLite + 单进程足够）
- JSON 字段需在 RepositoryBase._row_to_dict 白名单中注册
- UPSERT 用 sqlite_insert.on_conflict_do_update

参考：docs/<模块>-详细设计.md §x.y
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from xianyu_hunter.infra.repository_base import RepositoryBase, _escape_like

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine


class <域>sMixin(RepositoryBase):
    """<域> 仓储方法。

    继承 RepositoryBase 获得 _row_to_dict、_execute、db_count_by_predicate 等工具方法。
    """

    def upsert_<域>(self, data: dict[str, Any]) -> dict[str, Any]:
        """插入或更新<域>（UPSERT）。"""
        now = datetime.now(timezone.utc).isoformat()
        data.setdefault("created_at", now)
        data["updated_at"] = now

        stmt = sqlite_insert(self._<域>_table).values(**data)
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={k: stmt.excluded[k] for k in data if k != "id"},
        )
        with self._engine.connect() as conn:
            conn.execute(stmt)
            conn.commit()
        return data

    def get_<域>(self, item_id: str) -> dict[str, Any] | None:
        """根据 ID 查询<域>。"""
        stmt = select(self._<域>_table).where(self._<域>_table.c.id == item_id)
        with self._engine.connect() as conn:
            row = conn.execute(stmt).mappings().first()
        return self._row_to_dict(row) if row else None

    def list_<域>(
        self,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
    ) -> list[dict[str, Any]]:
        """分页查询<域>列表，支持关键词搜索。"""
        stmt = select(self._<域>_table).where(self._<域>_table.c.status != "deleted")
        if keyword:
            # LIKE 用 _escape_like 转义通配符防注入
            escaped = _escape_like(keyword)
            stmt = stmt.where(self._<域>_table.c.name.like(f"%{escaped}%"))
        # 软删除必须在 SQL 层过滤，避免 limit/offset 在内存过滤前已截断
        stmt = stmt.order_by(self._<域>_table.c.created_at.desc())
        stmt = stmt.limit(page_size).offset((page - 1) * page_size)
        with self._engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [self._row_to_dict(row) for row in rows]

    def update_<域>(self, item_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        """更新<域>。"""
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        stmt = (
            update(self._<域>_table)
            .where(self._<域>_table.c.id == item_id)
            .values(**data)
        )
        with self._engine.connect() as conn:
            result = conn.execute(stmt)
            conn.commit()
            if result.rowcount == 0:
                return None
        return self.get_<域>(item_id)

    def delete_<域>(self, item_id: str) -> bool:
        """软删除<域>。"""
        stmt = (
            update(self._<域>_table)
            .where(self._<域>_table.c.id == item_id)
            .values(status="deleted", updated_at=datetime.now(timezone.utc).isoformat())
        )
        with self._engine.connect() as conn:
            result = conn.execute(stmt)
            conn.commit()
            return result.rowcount > 0

    def count_<域>(self, keyword: str | None = None) -> int:
        """统计<域>数量（不含软删除）。"""
        return self.db_count_by_predicate(
            self._<域>_table,
            predicate=(self._<域>_table.c.status != "deleted"),
        )
```

## 模板3：领域模型

**文件位置**：`src/xianyu_hunter/domain/<域>.py`

```python
"""<域> 领域模型。

设计要点：
- dataclass + Enum，无 IO 依赖
- 继承 str, Enum 便于 JSON 序列化
- 时间统一 UTC（datetime.now(timezone.utc)）
- 反向依赖用 TYPE_CHECKING + 字符串注解避免循环导入

参考：docs/<模块>-详细设计.md §x.y
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class <域>Status(str, Enum):
    """<域>状态枚举（继承 str, Enum 便于 JSON 序列化）。"""
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"
    DELETED = "deleted"  # 软删除


class <域>Mode(str, Enum):
    """<域>模式枚举。"""
    AUTO = "auto"           # 全自动
    SEMI_AUTO = "semi_auto" # 推送确认后执行
    CONFIRM = "confirm"     # 仅推送不执行
    NOTIFY_ONLY = "notify_only"  # 仅推送


@dataclass
class <域>:
    """<域>领域模型。

    核心字段：
    - id: 唯一标识
    - name: 名称
    - status: 状态
    - mode: 模式

    时间字段统一 UTC，业务代码用 datetime.now(timezone.utc)。
    """
    id: str
    name: str
    status: <域>Status = <域>Status.ACTIVE
    mode: <域>Mode = <域>Mode.CONFIRM

    # 业务字段
    description: str | None = None
    config: dict[str, Any] = field(default_factory=dict)

    # 时间字段（UTC）
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_active(self) -> bool:
        """是否处于活跃状态。"""
        return self.status == <域>Status.ACTIVE

    @property
    def is_deleted(self) -> bool:
        """是否已软删除。"""
        return self.status == <域>Status.DELETED

    def can_execute(self) -> bool:
        """判断<域>是否可执行（业务规则）。"""
        # property 提供保底默认值
        # 独立方法支持运行时配置覆盖
        return self.is_active and self.mode in (<域>Mode.AUTO, <域>Mode.SEMI_AUTO)

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典（用于 API 响应）。"""
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "mode": self.mode.value,
            "description": self.description,
            "config": self.config,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
```
