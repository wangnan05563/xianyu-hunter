# 快速问题定位速查表

> **配套技能**：[xianyu-backend-code-review](../SKILL.md)
> **用途**：审查/开发过程中遇到已知问题时快速定位根因与方案，按问题类型分类（模块导入/WebView2/数据库/网络/前端集成/SonarQube/调度器/状态机/Python 现代化等）。本表是冷区域（按需查阅），日常审查无需预加载。
> **维护原则**：新增问题-原因-方案三元组时按问题类型倒序追加到对应分组，保持与 SKILL.md `## 快速问题定位` 索引同步。
> **来源**：xianyu 项目实战复盘，跨 v2.0-v4.40 版本沉淀（数据截至 2026-07-09）。

---

## 一、模块导入与基础环境

| 现象 | 原因 | 方案 |
|------|------|------|
| `NameError: name 're' is not defined` | 模块级导入缺失 | 在文件顶部 `import re` |
| `NameError: name 'threading' is not defined` | 同上 | `import threading` |
| WebView2 GUI 窗口闪退 | 使用 `CREATE_NO_WINDOW` | 改为 `CREATE_NEW_CONSOLE` |
| HuggingFace.co 连接超时 | 未设 `HF_ENDPOINT` 镜像 | 模块顶层 `os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")` |
| 向量化时间 30+ 分钟 | `_scan_and_chunk` 未排除前端构建产物 | 加入 `web/static/`、`web/templates/` 等到排除列表 |
| Token 比较被时序攻击 | 用 `==` 比较 | 改用 `hmac.compare_digest()` |

## 二、数据库与 SQLAlchemy

| 现象 | 原因 | 方案 |
|------|------|------|
| SQLite "database is locked" | `poolclass` 用 `StaticPool` | 改为 `NullPool` + `check_same_thread=False` |
| SQLite `utcnow` 弃用警告 | `datetime.utcnow()` | `datetime.now(timezone.utc)` |
| 查询慢但数据量小 | ORM 索引定义与 init_db 迁移不一致 | 比对 `__table_args__` 与 `_migrate_create_index`，补建缺失索引 |
| 商品列表刷新卡顿 | 全量加载到 Python 层过滤后切片 | 将过滤条件下推到 SQL WHERE + json_extract |
| `git` 操作报 `index.lock exists` | 失败 stash/merge 留下 `.git/index.lock` | 用 `python -c "import os; os.remove('.git/index.lock')"` 删除（PowerShell/cmd 被安全策略阻止时） |
| `git status` 卡死或极慢 | 产物文件（`.scannerwork/`、`__pycache__/`）被 git track（数千文件） | `git rm -r --cached <dir>` 清理并加入 `.gitignore` |

## 三、SonarQube 规则报错

| 现象 | 原因 | 方案 |
|------|------|------|
| S7503 报错 | `async` 函数无 `await` | 改同步函数，或确认需要异步上下文 |
| S3776 报错 | 认知复杂度 > 15 | 拆分为多个小函数（参考 `login_orchestrator.start_session` 7 步拆分模式） |
| S6767 报错 | 未使用的参数/属性/局部变量 | 删除未使用项，或用 `_` 前缀 |
| S1192 报错 | 重复字符串字面量 ≥ 2 处 | 提取为模块级常量（如 `_TASK_NOT_FOUND`） |
| S5843 报错 | 复杂正则表达式 | 拆分为多个简单正则或改用字符串方法 |
| 纯编排函数被误报 async | 函数无 await 但标注 async | 改同步 `def`（如 `scheduler.start_all`） |
| 用户配置修改不生效 | Evaluator 接受 `thresholds/weights/keywords` 覆盖参数 | 移除覆盖参数，每次 `evaluate()` 从 `get_config()` 实时读取 |
| 知识库构建回滚失败 | 失败率阈值未触发回滚 | 确认 `_PARTIAL_FAIL_RATE=0.10` + `_FAILED_FAIL_RATE=0.50` 触发条件 |

## 四、日志与错误处理

| 现象 | 原因 | 方案 |
|------|------|------|
| 401 响应解析失败（前端） | 返回纯文本非 JSON | 返回 `JSONResponse({"detail": "Unauthorized"}, status_code=401)` |
| Chatbot 并发会话状态污染 | Orchestrator 持有请求级状态 | 改为 per-session Lock + 无状态设计 |
| `CancelledError` 被吞，资源泄漏 | `except: pass` | 用 `suppress(asyncio.CancelledError)` 包裹并向上传播 |
| Pydantic `model_dump` 不存在 | 用了 1.x 的 `.dict()` | 升级到 2.x，用 `model_dump()` |
| 日志参数未替换显示 %s | loguru 使用了 printf 风格占位符 | 改用 `{}` 占位符：`logger.info("task={}", id)` |

## 五、v4.0-v4.4 复盘高频问题

| 现象 | 原因 | 方案 |
|------|------|------|
| 🆕v4.0 钉钉通知在状态未变前触发 | "已完成"事件在业务逻辑前置触发（EVAL_PASSED 前置） | 事件触发时机应在业务逻辑完成之后（如 `update_eval_result()` 后再触发 EVAL_PASSED） |
| 🆕v4.0 评估详情字段被空值覆盖 | 字段覆盖策略一刀切"只填缺失" | 按语义分类：基本信息仅填缺失、数值取较大值、状态按优先级、标识符仅在原值为空且新值非空时覆盖 |
| 🆕v4.0 重复登录创建多个会话 | 资源创建接口非幂等 | 引入 `already_active` 标志，检测到已激活资源时直接返回，避免重复创建 |
| 🆕v4.0 搜索接口参数混乱 | 多个搜索接口参数命名/响应结构不统一 | 统一参数命名（`keyword/page/page_size`）与响应结构（`items/total/page/page_size`），引入 400ms 防抖 + requestId 竞态保护 |
| 🆕v4.0 注释误导维护者 | 注释描述的约束与代码逻辑不一致 | 修改代码时同步更新注释；评审时校验注释中"必须 X 否则 Y"的真实性 |
| 🆕v4.0 动态资源映射难扩展 | 映射表与推断逻辑混合在 IIFE 中 | 抽离为模块级映射表（如 `API_KEY_URLS`）+ 推断函数（如 `getApiKeyUrlByBaseUrl`），便于单测与扩展 |
| 🆕v4.1 实时搜索返回 0 商品但实际是登录失效 | 重试失败后未检查 `last_session_invalid` 状态，仍走成功流程 | 重试代码块结束后检查状态标志，若仍为 True 则推送 SSE error 事件并 `return`（参考 `api_task_links.py` 修复） |
| 🆕v4.1 健康检查显示 Cookie 有效但业务调用失败 | Cookie 检查只覆盖身份 Cookie（`cookie2/sgcookie/unb`），忽略会话 token（`_m_h5_tk`） | Cookie 检查清单必须覆盖**所有**关键 token（身份 + 会话），清单在 `config.yaml` 的 `cookie_check_lists` 节点管理 |
| 🆕v4.1 前端用户无法区分"稍后重试"还是"前往登录" | 错误响应粒度未区分（401/403/502/503/504 混用） | 按错误粒度三类区分：`503/504` 稍后重试、`401/403` 需用户介入+指引、`502` 需重启服务 |
| 🆕v4.2 指纹被 AWSC fireyejs 识破 | GPU vendor 与 renderer 矛盾（如 Intel Inc. 配 AMD 渲染器） | 校验字段一致性：`Google Inc. (AMD)` 配 AMD 渲染器 |
| 🆕v4.2 页面 JS 读取 Cookie 失败 | Cookie 批量硬编码 `httpOnly:True`，JS 可读 Cookie 被禁 | 根据 Cookie 名称动态设置 `httpOnly`（identity 层设 False） |
| 🆕v4.2 验证码事件永远不触发 | `new Proxy()` 赋值给局部变量后丢弃 | 赋值给实例属性或用 `Object.defineProperty` 重写 setter |
| 🆕v4.2 API 请求死锁 | 同步函数中 `run_coroutine_threadsafe` + `future.result()` 等待异步结果 | 改纯异步路径或 fire-and-forget + 同步兜底（JSON 持久化） |
| 🆕v4.2 finally 块报 UnboundLocalError | try 内赋值的变量在 finally 中引用，但 try 抛异常 | 前置初始化 `page = None`，finally 中 `if page: await page.close()` |
| 🆕v4.2 健康检查显示有效但任务自动暂停 | 健康检查器与 worker 对"会话有效性"判断维度不同 | 状态变更双向同步：worker 检测到失效时 `invalidate_layer(IDENTITY)`，health_checker 查询时检查 `collector.last_session_invalid` |
| 🆕v4.2 用户按错误提示操作但端点不存在 | 错误提示引用了未实现的 API 端点 | 提示中只引用已实现的端点（如改为"请调用 POST /api/anticrawl/initialize"） |
| 🆕v4.3 Chrome v20 Cookie 解密失败 | v20 App-Bound Encryption 无法离线解密 | 改用 CDP 接管运行中浏览器：`Playwright.connect_over_cdp()` + `Network.getAllCookies` |
| 🆕v4.3 SQLite "database is locked" | 浏览器运行时持有 Cookies 数据库写锁 | 用 SQLite URI `file:./Cookies?immutable=1` + `connect(uri=True)` 只读打开 |
| 🆕v4.3 Cookie 同步任务与采集任务冲突 | 复用项目主调度器导致优先级与生命周期冲突 | 创建独立 `BackgroundScheduler()` + 独立 `start()`/`shutdown()` 钩子 |
| 🆕v4.3 用户不知情下浏览器资源被占用 | `auto_sync` 默认启用 | `auto_sync: bool = False` 默认关闭，需用户在 `config.yaml` 显式启用 |
| 🆕v4.3 Cookie 同步无意义重试 | 多方案失败无 backoff 策略 | 3 次失败后 `interval *= 2`，上限 2 小时（参数在 `config.yaml` 的 `fallback_chain` 管理） |
| 🆕v4.3 Chrome 136+ CDP 端口不生效 | `--remote-debugging-port` 缺 `--user-data-dir` 非标准目录 | 启动命令同时包含两参数，`user_data_dir` 指向 `browser_data/debug_{timestamp}` |
| 🆕v4.3 用户 Profile 1 的 Cookie 导入失败 | 实现只读 Default profile | 读 `Local State` 的 `profile.info_cache` + fallback 目录扫描 `Profile *` |
| 🆕v4.3 测试报路径不存在 | 测试 fixture 路径结构与实现不一致 | `monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))` + 创建 `tmp_path / "Microsoft" / "Edge" / "User Data"` 完整路径 |
| 🆕v4.3 `pytest --timeout=60` 报 unrecognized arguments | 项目未安装 `pytest-timeout` 插件 | 移除 `--timeout` 标志，或在 `pyproject.toml` 声明插件依赖 + `requirements-dev.txt` 列出 |
| 🆕v4.4 用户设置了排序方式但搜索结果无变化 | sort_type 配置注入到 TaskConfig 但 Worker 未读取 self.config.search_sort_type | 从 config.yaml→Config→TaskConfig→Worker→search()→build_search_url() 全链路追踪，确认每层都读取并传递参数 |
| 🆕v4.4 刚登录后搜索偶尔成功偶尔失败 | fast=True 模式跳过 token 刷新，token 过期时搜索失败 | fast 失败后自动以 fast=False 重试一次（含 token 刷新） |
| 🆕v4.4 连续失败 10 次才暂停但配置设为 3 次 | Scheduler 用硬编码 MAX_CONSECUTIVE_ERRORS=10 替代 fail_pause_threshold 配置 | 改为 `get_config().antidetect.fail_pause_threshold` |
| 🆕v4.4 RGV587 重试时 URL 丢失排序参数 | search() 新增 sort_type 参数后 _call_search_api 内部 build_search_url 未传递 | grep 方法名检查所有调用点，同步更新内部调用传递新参数 |

## 六、v4.8-v4.9 状态机与 Python 现代化

| 现象 | 原因 | 方案 |
|------|------|------|
| 🆕v4.9 任务状态出现非法转换（如 failed → running） | 状态机无白名单转换规则，散落式 `if status=='X': status='Y'` | 集中定义 `TRANSITIONS: dict[str, set[str]]` 显式列出允许的转换；终态不可复活；中间态有超时清理；deadline 不可无限重置；前后端枚举值统一（参数在 `config.yaml` 的 `state_machine` 节点管理） |
| 🆕v4.9 服务关闭后 asyncio.Task 资源泄漏 / 警告 "Task was destroyed but it is pending" | `asyncio.create_task(...)` 未保留引用被 GC，组件无 cleanup 钩子 | 可注册组件实现 `cleanup()` 钩子并在 shutdown 事件调用；Task 保留到实例属性 `self._task = asyncio.create_task(...)`；取消用 `await asyncio.gather(*tasks, return_exceptions=True)`；try/finally 资源前置 `= None` |
| 🆕v4.9 同一业务目标两条链路行为不一致（API 路由能正确校验，定时任务跳过校验） | 双链路共用前置条件重复实现，未抽离为共享函数 | 抽离共用前置条件为 `def _validate_xxx(...): ...`，两链路调用同一函数；grep 验证两链路都调用；新增测试覆盖两链路 |
| 🆕v4.9 并发场景下"检查通过但更新前状态已变"导致重复启动 | 共享状态检查+更新未在同一锁内（`if not self._active: self._start()` 错误模式） | 改为 `async with self._lock: if not self._active: await self._start()` 同一锁内完成检查+更新；dataclass 字段显式声明默认值禁 `getattr` 兜底；锁粒度最小化；锁内禁止 `await`（除非 asyncio.Lock） |
| 🆕v4.9 Python 3.12+ 报 DeprecationWarning: There is no current event loop | 用 `asyncio.get_event_loop().create_task(coro)` 替代 `asyncio.create_task(coro)` | 改为 `asyncio.create_task(coro)`（3.10+ 推荐）；避免 `getattr` 兜底；模块级 import；`except BaseException` 改为 `except Exception` 或显式 `except asyncio.CancelledError: raise`；类型注解用现代语法 `dict[str, str]` / `int \| None` |
| 🆕v4.8 WARNING 日志刷屏（300+条/小时） | 检测到异常状态后后续操作仍重复尝试 | 设置状态标志 + 操作入口增加 `getattr(self, "flag", False)` 前置检查 + 重置机制（`flag = False`）（B-REVIEW-STATE-FLAG-PRECHECK） |
| 🆕v4.8 日志降级文案变更后失效 | 判断字符串硬编码未提取为常量 | 提取为模块级常量（如 `_COOKIE_EXPIRED_DETAIL_MARKER`）并注释文案来源（B-REVIEW-LOG-DOWNGRADE-STABILITY） |
| 🆕v4.8 代码评审发现修改未生效 | Edit 工具返回成功但修改未保存 | Edit 后立即 Grep 验证标志性标识符（变量名/函数名/常量名），无匹配则重新执行 Edit（B-REVIEW-EDIT-VERIFY） |
