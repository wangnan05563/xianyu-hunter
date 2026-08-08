# 调度器运行时治理

> 调度器开关对称性、时间参数配置化、资源生命周期清理、cron 表达式校验、调度器状态机恢复。
>
> 涵盖规范: #48, #49, #50, #51, #86
>
> 完整内容见 [../meta-rules.md](../meta-rules.md) | [返回索引](index.md)

---

### #48 调度器运行时开关对称性
禁用=remove_job+设标志位，启用=add_job+设标志位。job函数入口double-check
- grep: `grep "def update_config" <scheduler>` 缺 remove_job 或 add_job → 不对称

### #49 时间参数配置化
time.sleep/asyncio.sleep/timeout必须从config读取，禁止硬编码字面量数字
- grep: `grep "time\.sleep\([0-9]" <file>` → 硬编码违规

### #50 长生命周期对象状态清理
scheduler/container持有dict[str,...]必须提供drop_task_state(task_id)，DELETE API调用清理
- grep: `grep "self\._\w*: dict\[str,"` 但无 drop_task_state → 缺清理

### #51 用户输入时间表达式校验 (experimental)
cron最小间隔 ≥ 反爬最小延迟。枚举24h内触发点取最小差值校验
- grep: `grep "CronTrigger" <file>` 无 min_interval 校验 → 缺校验

### #86 调度器状态机恢复路径校验
resume前必须校验调度器状态机路径(之前如何暂停的)，禁止无条件恢复
- grep: `grep "def resume" <file>` 缺状态路径检查 → 违规
