# 异步与资源安全

> async/await 同步性检查、资源池性能基准、HTTP 状态码映射、CSS 选择器降级、异常日志语义、外部资源生命周期、DB 写入身份追溯、异步阻塞超时、子进程心跳等。
>
> 涵盖规范: #57, #58, #59, #60, #61, #62, #63, #79, #80, #81, #82, #92
>
> 完整内容见 [../meta-rules.md](../meta-rules.md) | [返回索引](index.md)

---

### #57 async/await 同步性静态检查
async def方法体无await必须改为def。白名单：@abstractmethod/__aenter__/__aexit__/async generator
- grep: `grep "async def" <file>` 后检查方法体内是否含 `await` → 同步冗余

### #58 资源池配置性能基准与决策
NullPool/QueuePool选择必须有docstring记录性能数据。系统层开销>50ms禁止NullPool
- grep: `grep "poolclass=" <file>` 无 docstring → WARNING

### #59 HTTP 状态码精细化映射表
多原因None→reason_code→status_code映射表。底层设置last_failure_reason，上游按映射查找
- grep: `grep "raise HTTPException(410" <file>` 多原因汇聚同一码 → 语义模糊

### #60 CSS 选择器多级降级策略
三级fallback：业务语义className → HTML role属性 → 文本前缀扫描。dump仅在核心字段失败触发
- grep: `grep "querySelectorAll" <file>` 选择器单一无fallback → CRITICAL

### #61 异常日志语义保留规范
except块必须用logger.exception()保留完整traceback。禁止warning(f"...{e}")丢失堆栈
- grep: `grep "logger.warning.*f\".*{e}\"" <file>` 在except块内 → 违规

### #62 外部资源生命周期配对管理
外部Page/Connection必须register/unregister配对，finally块unregister。引用计数为0才关闭
- grep: `grep "register_external_page" <file>` 无 `finally.*unregister` → 配对缺失

### #63 数据库写入函数身份追溯与类型安全
写入函数必须含user_id参数+WHERE user_id条件。converter必须显式m.group(1)再转型
- grep: `grep "def upsert_\|def insert_" <file>` 无 `user_id` → 跨用户风险

### #79 长时交互式外部命令两阶段异步模式
长时交互命令先start异步启动→轮询状态→收集结果。禁止同步阻塞主线程

### #80 async 阻塞调用超时保护
async调用外部资源必须asyncio.wait_for超时保护。超时返回语义化状态码504

### #81 子进程心跳与阶段超时协同
子进程必须有心跳检测机制。心跳间隔<阶段超时。心跳停止即判定失败

### #82 跨代码块一致性检查 (experimental)
不同代码块处理同一数据时必须保持一致性。分支逻辑在多个位置必须同步

### #92 PowerShell 外部命令显式后缀
Windows PowerShell调用Python脚本必须用显式`.py`后缀。禁止依赖PATHEXT自动解析
