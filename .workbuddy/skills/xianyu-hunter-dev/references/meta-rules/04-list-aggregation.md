# 列表聚合与状态联动

> 全局聚合过滤、列表交叉数据注入、多字段联动开关、precheck 结构化响应、配置化阈值兜底。
>
> 涵盖规范: #38, #39, #40, #41, #42
>
> 完整内容见 [../meta-rules.md](../meta-rules.md) | [返回索引](index.md)

---

### #38 全局聚合任务级过滤
多任务共享列表接口必须按各任务个体配置过滤，禁止仅用全局默认。全局视图→遍历任务→_filter_by_per_task_range()
- grep: `grep "task_id.*is None" <file>` 无 `_filter_by_per_task_range` → 违规

### #39 列表交叉数据批量注入
交叉数据源必须 WHERE IN 批量查询 + TTL缓存，禁止N+1循环单条查询
- grep: `grep "for.*in.*items:" <file>` 后跟单条 db.query → N+1违规

### #40 多字段联动开关范式
主开关+子过滤器必须有优先级矩阵。主开关失效时子过滤器自动禁用。PATCH用exclude_unset=True三态
- grep: `grep "mode.*notify" <file>` 无优先级矩阵注释 → 可疑

### #41 状态恢复前置校验结构化响应
precheck必须返回{resume_blocked, reason_code, user_hint, retry_after, task_registered}，不抛异常
- grep: precheck函数体内含 `raise` → 违规

### #42 配置化阈值兜底范式
config读取必须 try/except 兜底默认值。禁止配置缺失即崩溃。兜底时 logger.warning
- grep: `grep "get_config()" <file>` 无 `try.*except` 包裹 → 可疑
