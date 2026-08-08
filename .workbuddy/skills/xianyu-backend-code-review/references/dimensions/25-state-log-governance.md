# 维度 25：状态管理与日志治理

> **编码规范引用**：coding-standards v1.3 §多层级状态校验 / 计数器语义
> **配置节点**：config.yaml#consistency_and_state_checks.counter_semantics / round_reset

## 触发条件
- 状态流转代码（如登录、采集、抢单、任务周期）
- 计数器（连续失败/成功/重试等）增删改
- 调度器/Worker 的 `run_once` 或等价入口函数
- 异常处理后状态恢复逻辑

## 检查规则

### 强制（P0 阻塞）
- 状态流转必须记录日志，日志包含足够的上下文：`task_id` / `user_id` / `timestamp` / `from_state` / `to_state`
- 状态变更原因必须可追溯（日志中明确 `reason=` 字段）
- `_consecutive_*` 命名计数器成功时必须清零，保持"连续"语义（非"累计"）
- 新一轮处理开始时（`run_once` 等入口），必须重置上一轮的跨轮次状态（计数器/标志位/临时缓存）

### 推荐（P1 严重）
- 日志使用结构化格式（`key=value`），便于日志聚合分析
- 状态变更日志级别用 `INFO`（生产可见），非 `DEBUG`
- 异常处理中的状态回滚必须记录（含回滚原因和回滚前状态）
- 批量操作的状态变更应记录批量级别摘要（成功数/失败数/跳过数）

### 禁止
- 状态变更无日志（静默状态跳转）
- `_consecutive_*` 计数器成功时不清零（语义漂移为"累计"）
- 跨轮次状态未重置导致上一轮失败污染本轮
- 异常吞掉后不记录状态（静默恢复）

## Grep 扫描命令

```bash
# 连续失败计数器
grep -rn "_consecutive_\w*\s*[+=]" src/xianyu_hunter/ --include="*.py"

# 跨轮次重置
grep -rn "run_once\|_process_round\|_scheduler_tick\|_round_" src/xianyu_hunter/ --include="*.py" -A 5 | grep -E "reset|= 0|=0|= \[\]|= \{\}"

# 状态流转日志
grep -rn "logger\.\(info\|warning\).*state\|状态" src/xianyu_hunter/ --include="*.py"

# 状态变更无日志
grep -rn "self\._.*state\s*=" src/xianyu_hunter/ --include="*.py" | grep -v "#"
```

## 判断标准
- `_consecutive_*` 计数器成功时不清零 → P0 阻塞
- 跨轮次状态未重置 → P0 阻塞
- 状态变更无日志 → P1 严重
- 状态日志缺 `task_id` / `from_state` / `to_state` → P1 严重

## 适用/不适用场景
- **适用**：所有状态机代码（登录状态、采集状态、任务状态）；调度器/Worker 循环入口
- **不适用**：无跨轮次状态的简单函数；确需累计统计的计数器（应命名 `_total_*` 而非 `_consecutive_*`）
