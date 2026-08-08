# 编码规范
> 包含元规范 #7 - #14

## 7. 状态分类识别

新增任何状态字段前必须识别归属类别，选择对应持久化策略：

| 状态类别 | 持久化策略 | 典型示例 |
|---|---|---|
| 用户偏好类 | `usePersistentState`（localStorage） | 自动刷新/视图模式/列显隐/折叠/展开 |
| 业务数据类 | 后端 API + DB | 任务列表/订单状态/配置项 |
| 会话状态类 | Zustand store | 登录态/当前选中项/跨页共享 |
| 临时状态类 | `useState` | loading/modal open/submitting/表单 dirty |
| 敏感数据类 | secure storage / httpOnly cookie | token/密码/API key |

**判断信号**：新增 React state 时自问"刷新页面后状态应保留还是重置？"——保留则用户偏好类，重置则临时状态类。

## 8. 错误粒度区分

HTTP 状态码必须按语义精细化区分（参考 step 71/123）：

| 状态码 | 语义 | 前端动作 |
|---|---|---|
| 401 | 未登录 | 跳转登录页 |
| 403 | 权限不足 | 显示权限不足提示 |
| 440 | Cookie 过期 | 跳转重新登录 |
| 441 | Token 过期 | 刷新 Token |
| 429 | 反爬触发 | 提示手动验证 |
| 502 | 浏览器异常 | 提示重启服务 |
| 503 | 服务未启动 | 提示启动服务 |
| 504 | 网关超时 | 提示稍后重试 |

**禁止**：所有认证失败都映射为 `401` 导致前端无法区分"未登录"与"登录态过期"。

## 9. 日志级别规范

| 级别 | 适用场景 |
|---|---|
| `logger.error` | 需人工介入的失败（主流程失败/数据丢失/安全事件） |
| `logger.warning` | 可恢复异常/降级/重试（辅助功能失败/配置项缺失/可选资源不可用） |
| `logger.info` | 业务关键路径（触发抢单/采集完成/推送发送/调度器启动） |
| `logger.debug` | 调试信息（默认 INFO 级别不输出，仅开发环境可见） |
| `logger.exception` | 关键路径（启动钩子/迁移/初始化）外层 except 必须用，保留完整 traceback |

**禁止**：
- 辅助功能失败用 `logger.debug`（默认不输出，难以排查）
- 辅助功能失败用 `logger.error`（过度严重，污染告警）
- 关键路径外层 except 用 `logger.warning(f"...{e}")`（丢失堆栈）

## 10. 异步操作规范

所有 `await` 调用外部资源的异步操作必须满足：

1. **整体超时保护**：`asyncio.wait_for(coro, timeout=N)` 包裹，超时返回语义化状态码（504）
2. **超时时间从配置读取**：禁止硬编码，参考 `config.yaml` 的 `async_timeout` 节点
3. **CancelledError 传播**：用 `contextlib.suppress(asyncio.CancelledError)` 包裹并向上传播，禁止 `except: pass`
4. **Task 引用保留**：`self._task = asyncio.create_task(...)` 防止 GC，禁止裸 `asyncio.create_task(...)`
5. **取消+收集模式**：`task.cancel()` + `await asyncio.gather(task, return_exceptions=True)`

## 11. 安全调用检查

所有外部接口调用必须满足：

1. **空值/边界判断**：调用前校验参数非空、范围合法
2. **异常分支处理**：禁止 `except: pass` 静默吞异常
3. **敏感数据脱敏**：`_SENSITIVE_HEADERS` 过滤 authorization/cookie/xh_token/set-cookie
4. **权限校验**：`BearerAuthMiddleware` 白名单检查
5. **SQL 注入防护**：LIKE 用 `_escape_like`，表名/列名用 `_IDENT_RE` 白名单
6. **路径遍历防护**：用户输入用 `_USER_ID_RE` 等正则校验
7. **token 比较**：`hmac.compare_digest` 防时序攻击
8. **外部链接安全**：`target="_blank"` 配 `rel="noopener noreferrer"`

## 12. 状态机设计规范

含「状态」字段且状态会变化的业务对象必须满足：

1. **枚举穷举**：列出所有状态值
2. **转换白名单**：用 `(起始状态 → 目标状态)` 白名单校验，禁止黑名单
3. **终态不可复活**：`failed`/`succeeded`/`cancelled` 禁止再转换，状态变更接口前置校验
4. **中间态超时清理**：独立 APScheduler 定时扫描 + 一次 SQL 批量更新
5. **前后端枚举值统一**：禁止 snake_case ↔ camelCase 映射转换

## 13. 测试隔离规范

1. **生产路径 patch**：fixture 必须用 `tmp_path` 隔离生产路径，禁止直接读写生产文件
2. **测试数据可识别**：带 `test_fixture_` 前缀/`__test__` 后缀
3. **patch 验证**：fixture 加载后 `assert not os.path.exists(production_path)` 验证
4. **遍历 sys.modules**：禁止硬编码模块名列表，必须遍历 `sys.modules` 找所有持目标属性的模块
5. **importlib.import_module**：禁止 `__import__`（返回顶层包而非子模块）
6. **数据污染应急 5 步**：停止服务 → 删除污染文件 → 修复 conftest → 重跑测试 → 通知用户

## 14. Python 现代化规范

Python 3.10+ 项目必须：

1. **asyncio.create_task** 替代 `asyncio.get_event_loop().create_task`
2. **asyncio.get_running_loop** 替代 `asyncio.get_event_loop`（在协程内）
3. **dataclass 字段显式声明**，禁止 `getattr(obj, 'field', default)` 兜底
4. **模块级 import**，禁止函数内重复 import（除非解决循环依赖）
5. **CancelledError 传播**，用 `contextlib.suppress` 包裹
6. **类型注解现代语法**：`X | None` 替代 `Optional[X]`，`list[T]` 替代 `List[T]`
