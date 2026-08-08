# 工程闭环

> 参数链验证、业务模式纵向链路一致性、外部页面解析容错、mock 同步与边界精确性、状态恢复校验、事件驱动基础设施。
>
> 涵盖规范: #31, #52, #53, #54, #55, #111
>
> 完整内容见 [../meta-rules.md](../meta-rules.md) | [返回索引](index.md)

---

### #31 状态恢复前置校验
pause时记录root_cause(reason_code+失效层+时间戳)，resume前precheck校验根因已消除。异常pause后冷却期内拒绝恢复
- grep: `grep "def resume\|def start" <file>` 缺 precheck 调用 → 违规

### #52 参数链闭环验证
过滤类参数必须存在对应消费点。参数在签名+return中但未参与过滤 → "参数悬挂"违规
- grep: `grep "<param_name>" <file>` 仅签名和return但未命中函数调用 → 可疑

### #53 业务模式纵向链路一致性
mode枚举在6层纵向一致：决策层→事件层→通知层→路由层→接口层→状态机层。任一层缺失即退化

### #54 外部页面解析容错
DOM解析三级fallback：结构化selector → HTML role属性 → 文本内容前缀扫描。dump触发收窄到核心字段
- grep: `grep "querySelector" <file>` 选择器单一无fallback → 违规

### #55 mock 同步与边界精确性
同步用MagicMock，异步用AsyncMock。patch必须patch调用点非定义点。mock覆盖完整字段集
- grep: `grep "AsyncMock" <test>` 但被mock函数是同步 → 违规

### #111 事件驱动基础设施启动解耦 (experimental)
EventBus消费者循环必须与业务任务存在性解耦。基础设施先于调度器启动，后于调度器停止
- grep: `grep "run_forever"` 启动嵌套在业务调度器函数内部 → 违规
