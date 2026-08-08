# 审查判断标准

> 本文件从 SKILL.md 外移而来，记录后端代码审查的阻塞/严重/警告三级判断标准。
> SKILL.md 仅保留索引引用，详细规则在本文件维护。

## 三级判断标准

| 🟠阻塞(必须修复) | 🟠严重(强烈建议) | 🟡警告(建议) |
|-----------------|-----------------|-------------|
| 违反分层架构（跨层调用） | 服务调用缺必需字段 | 格式化不规范 |
| 缺失模块级导入（re/threading/logging） | 未查看服务方法实现 | 变量命名不规范 |
| Token 比较未用 `hmac.compare_digest()` | 异常处理不完善（吞异常/丢堆栈） | 冗余代码 |
| 硬编码密码/密钥/钉钉推送 Key | 空指针风险（链式调用未判空） | 注释不清晰 |
| SQL 字符串拼接（未用 `_escape_like`） | N+1 查询/循环访问 DB | 魔法数字未提取常量 |
| 凭据明文写入 `config.yaml` | 日志含敏感信息 | 函数过长 |
| 使用已弃用 `datetime.utcnow()` | async 代码中阻塞 IO | 缺少类型注解 |
| SQLite 引擎用 `StaticPool`（应用 `NullPool`） | `asyncio.Task` 未保留引用 | 缺少测试 |
| WebView2 `CREATE_NO_WINDOW` | `CancelledError` 被静默吞掉 | 嵌套层级过深 |
| WebView2 重定向到 `DEVNULL` | `EventBus` 消费者未处理 `QueueEmpty` | 注释复述代码 |
| `except:` + `pass` | 未设置 `HF_ENDPOINT` 镜像 | DTO 未实现 Serializable（Pydantic 默认） |
| Pydantic 1.x `.dict()` / `.json()` | `sentence-transformers` 跨版本未 fallback | 路由缺少 tags |
| `config/config.yaml` 明文暴露凭据 | `ChatbotOrchestrator` 持有请求级状态 | 缺少文档字符串 |
| GET 请求引发状态变更 | `_scan_and_chunk` 未排除 `web/static/` | 缺少 `__all__` |
| 响应返回 ORM 对象（非 DTO） | `_overview()` 未用 CASE WHEN 合并 | 魔法字符串 |
| 必填字段缺失索引 | Web 进程未用 `with_browser=False` | - |
| `webview.start()` 未设 `private_mode=False` | `PriorityBrowserLock` 优先级缺失 | - |
| 循环依赖 A→B→C→A | `Container` 未深拷贝 chatbot 配置 | - |
| `local_embedding.py` 未设 HF 镜像 | Evaluator 接受覆盖参数 | - |
| 产物文件（`.scannerwork/` 等）git track | 异步方法调用遗漏 `await` | - |
| 🆕 `await` 非 `async` 函数（S7503） | 🆕 重复字符串字面量 2 处未提取为常量（S1192） | - |
| 🆕 认知复杂度 > 15 未拆分（S3776） | 🆕 复杂正则未拆分（S5843） | - |
| 🆕 未使用的参数/属性/局部变量（S6767） | 🆕 `Evaluator` 接受 `thresholds/weights/keywords` 覆盖参数 | - |
| 🆕 `asyncio.CancelledError` `except: pass` 静默吞掉 | 🆕 KB 索引未排除 `web/static/` 等前端构建产物 | - |
| 🆕v4.0 "已完成"事件在业务逻辑前触发（EVAL_PASSED 前置） | 🆕v4.0 字段覆盖一刀切"只填缺失"（应按语义分类） | - |
| 🆕v4.0 资源创建接口非幂等（重复调用重复创建） | 🆕v4.0 搜索接口参数/响应结构不统一 | - |
| 🆕v4.0 注释与代码逻辑不一致（误导性约束说明） | 🆕v4.0 动态资源映射表与推断函数混合 | - |
| 🆕v4.1 重试失败后未检查状态标志直接走成功流程（B-REVIEW-SESSION-SIGNAL） | 🆕v4.1 Cookie 检查只覆盖身份 Cookie，忽略会话 token（B-REVIEW-COOKIE-CHECK） | - |
| 🆕v4.1 错误粒度不区分（401/403/502/503/504 混用） | - | - |
| 🆕v4.2 语义关联字段矛盾（如 gpu_vendor 配不匹配 gpu_renderer） | 🆕v4.2 跨组件对同一概念判断维度未同步 | - |
| 🆕v4.2 Cookie/HTTP 属性硬编码（批量 httpOnly:True） | 🆕v4.2 错误提示引用不存在的端点 | - |
| 🆕v4.2 run_coroutine_threadsafe + future.result() 死锁组合 | - | - |
| 🆕v4.2 try/finally 变量未初始化为 None | - | - |
| 🆕v4.3 v20 加密用 `CryptUnprotectData` 离线解密（应 CDP 接管）（B-REVIEW-ENCRYPTION-DEGRADATION） | 🆕v4.3 profile 发现只读 Default（应用 `profile.info_cache`+fallback 扫描）（B-REVIEW-MULTI-PROFILE-DISCOVERY） | - |
| 🆕v4.3 SQLite 文件锁报错未用 `immutable=1` URI 绕过（B-REVIEW-FILE-LOCK-BYPASS） | 🆕v4.3 高风险功能默认启用（应默认关闭/配置驱动）（B-REVIEW-CONFIG-DRIVEN-TOGGLE） | - |
| 🆕v4.3 后台任务复用主调度器（应独立 BackgroundScheduler）（B-REVIEW-SCHEDULER-ISOLATION） | 🆕v4.3 多方案失败无 backoff 策略（应配置驱动 max_failures/max_interval）（B-REVIEW-FALLBACK-CHAIN） | - |
| 🆕v4.3 Chrome 136+ `--remote-debugging-port` `--user-data-dir` 非标准目录（B-REVIEW-CHROME-136-ADAPTATION） | 🆕v4.3 测试 Windows 环境变量未用 `tmp_path` mock（路径结构与实现不一致）（B-REVIEW-WINDOWS-TEST-MOCK） | - |
| 🆕v4.3 使用 pytest 插件未在 `pyproject.toml` 声明（运行时报 unrecognized arguments）（B-REVIEW-PLUGIN-DEPENDENCY-PRECHECK） | - | - |
| 🆕v4.4 错误码映射语义不匹配（如 RGV587=token 过期映射为 401 登录失效）（B-REVIEW-ERROR-SEMANTICS） | - | - |
| 🆕v4.4 配置项注入到中间层但消费层未读取（配置无效化）（B-REVIEW-CONFIG-LINKAGE） | - | - |
| - | 🆕v4.4 fast=True 失败后无降级重试（B-REVIEW-FAST-DEGRADATION） | - |
| - | 🆕v4.4 硬编码阈值替代已有配置项（B-REVIEW-NO-HARDCODED-THRESHOLD） | - |
| - | 🆕v4.4 方法签名新增参数后内部调用点遗漏传递（B-REVIEW-PARAM-PASS-THROUGH） | - |
| 🆕v4.9 状态机无白名单转换规则，散落式 `if status=='X': status='Y'`（B-REVIEW-STATE-MACHINE-WHITELIST） | 🆕v4.9 终态可复活 / 中间态无超时清理 / deadline 无限重置（B-REVIEW-STATE-MACHINE-WHITELIST） | - |
| 🆕v4.9 可注册组件无 cleanup 钩子 / asyncio.Task 未保留引用被 GC（B-REVIEW-RESOURCE-CLEANUP-HOOK） | 🆕v4.9 try/finally 资源未前置初始化为 None / gather 未用 return_exceptions（B-REVIEW-RESOURCE-CLEANUP-HOOK） | - |
| - | 🆕v4.9 双链路共用前置条件重复实现，未抽离为共享函数（B-REVIEW-DUAL-LINK-CONSISTENCY） | - |
| 🆕v4.9 共享状态检查/更新未在同一锁内（`if not active: start()` 错误模式）（B-REVIEW-CONCURRENT-STATE-LOCK） | 🆕v4.9 dataclass 字段用 `getattr` 兜底 / 锁内 `await` / 锁粒度过大（B-REVIEW-CONCURRENT-STATE-LOCK） | - |
| - | 🆕v4.9 `get_event_loop().create_task` 替代 `asyncio.create_task` / `except BaseException` 吞 CancelledError（B-REVIEW-PYTHON-MODERN-ASYNCIO） | - |
| 🆕v4.8 状态标志设置后无前置检查（B-REVIEW-STATE-FLAG-PRECHECK） | 🆕v4.8 日志降级判断用魔法字符串（B-REVIEW-LOG-DOWNGRADE-STABILITY） | - |
| 🆕v4.8 状态标志无重置机制（等于永久禁用） | 🆕v4.8 修改后未验证生效（B-REVIEW-EDIT-VERIFY） | - |
| 🆕v4.61 模块级函数误用 `self`/`cls`（B-REVIEW-282 SCOPE-CONTRACT-CHECK） | 🆕v4.61 PowerShell 长任务用 `| Select-Object -Last` sink cmdlet（B-REVIEW-284） | - |
| 🆕v4.61 删除/重命名导出符号前未 grep 所有引用点（B-REVIEW-283 IMPORT-NAME-CHECKLIST） | 🆕v4.61 完整 pytest 超时无降级策略（B-REVIEW-285 RESOURCE-OVERLOAD-TOLERANCE） | - |
| 🆕v4.61 配置化重构后未执行运行时验证（B-REVIEW-289 CROSS-FILE-REFERENCE-SYNC） | 🆕v4.61 SonarQube 扫描单阶段失败终止整条链路（B-REVIEW-286） | - |
| 🆕v4.61 模块级硬编码业务参数常量 `_LIVE_CACHE_TTL = 60`（B-REVIEW-290 CONFIG-ACCESS-UNIFIED-ENTRY） | 🆕v4.61 SonarQube ES read-only 锁无自愈（B-REVIEW-287 RESILIENCE-RECOVERY） | - |
| 🆕v4.61 配置读取函数无异常回退到默认值（B-REVIEW-281 CONFIG-REFACTOR-5STEP） | 🆕v4.61 审查验证阶段未按三档策略选择测试粒度（B-REVIEW-288 TEST-VERIFY-TIERS） | - |

## 分类规则

- **硬约束违规**：统一 P0
- **影响功能正确性/稳定性**：P1
- **影响可维护性/配置化**：P2
- **纯风格问题**：P3
