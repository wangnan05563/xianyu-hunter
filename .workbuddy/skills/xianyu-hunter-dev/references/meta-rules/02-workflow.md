# 工作流规范

> 异常处理决策、批处理熔断、资源生命周期管理、跨组件/跨源状态同步等高频工作流模式。
>
> 涵盖规范: #21, #22, #23, #24
>
> 完整内容见 [../meta-rules.md](../meta-rules.md) | [返回索引](index.md)

---

### #21 错误处理决策树
捕获异常后三问决策：①是否为关键路径→logger.exception()阻断 ②是否需要向用户展示→reason_code三层 ③是否需要重试→指数退避+熔断
- grep: `grep "except" <file>` 关键路径缺 `logger.exception()` → 违规

### #22 批处理熔断模板
长任务断点续传：running→paused(可恢复)→running(续传)，每完成一项save_progress()，熔断时持久化cursor
- grep: `grep "consecutive failure" <file>` 无 `save_progress()` → 违规

### #23 资源生命周期管理
Playwright/SSE/WebSocket必须持有(_前缀实例属性)，在stop()/useEffect cleanup中清理
- grep: `asyncio.create_task(coro)` 未赋值实例属性 → 违规

### #24 跨组件/跨源状态同步
前端跨组件：单一可信源(GET /api/xxx)+统一入口(useXxxStore)+统一refetch+SSE推送。
后端跨源：YAML↔keyring/EventRow↔业务表/健康检查↔Worker实测 必须同步
- grep: `grep "usePersistentState"` 但该字段在后端有 GET /api/xxx → 违规
