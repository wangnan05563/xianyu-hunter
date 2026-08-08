# 维度 10：事件总线

> **编码规范引用**：coding-standards v1.3 §代码边界契约
> **配置节点**：config.yaml#event_bus_startup_decoupling
> **参考文档**：references/async-and-concurrency.md §13.4

## 触发条件
- 修改 EventBus 启动/关闭逻辑时
- 新增发布-订阅模式的事件类型时
- 出现"事件发布但无消费者响应"的问题时

## 检查规则

### 强制（P0 阻塞）
- EventBus 启动必须独立于业务任务（B-REVIEW-331 EVENT-BUS-STARTUP-DECOUPLING）：`start_event_bus_in_background` 不嵌套在 `_scheduler_loop` 内部
- 启动顺序：EventBus → Scheduler（基础设施先于业务调度器）
- 关闭顺序：Scheduler → EventBus（业务停止后基础设施再停，确保终态事件发布）
- 消费者循环必须容错：单个消费者异常不影响其他消费者运行

### 推荐（P1 严重）
- `start()` 幂等防护：`if _task is not None and not _task.done(): return`
- 运行时入口重入检测：`control_task`/`resume`/`restart` 中检查 EventBus 是否运行，未运行则自动启动
- 消费者循环异常必须记录 `logger.exception()`（CancelledError 除外）
- `publish_nowait` 失败时应有日志告警

### 禁止
- EventBus 启动被业务条件阻断（如 `if not workers: return` 导致 EventBus 永不启动）
- 消费者循环中 `except Exception: pass` 吞异常
- EventBus 先于调度器停止（终态事件丢失）
- 无幂等防护的重入启动（可能多个消费者竞争同一队列）

## Grep 扫描命令
```bash
# 检测消费者循环嵌套在业务函数内部
grep -rn "run_forever\|consume_loop\|_dispatch" src/xianyu_hunter/

# 检测启动顺序（EventBus 应在 Scheduler 之前）
grep -rn "_on_startup\|startup" src/xianyu_hunter/ -A 5

# 检测关闭顺序（Scheduler 应在 EventBus 之前）
grep -rn "_on_shutdown\|shutdown" src/xianyu_hunter/ -A 5

# 检测幂等防护缺失
grep -rn "_event_bus_task" src/xianyu_hunter/
```

## 判断标准
- EventBus 嵌套在业务函数内部：P0 阻塞
- 启动/关闭顺序错误：P0 阻塞
- 消费者异常静默：P0 阻塞
- 缺少幂等防护：P1 严重
- 缺少运行时重入检测：P1 严重

## 适用场景
- `web/app.py` lifespan 启动钩子
- EventBus 的消费者循环实现
- 发布-订阅模式的所有基础设施
- Notifier 等订阅者通过 EventBus 接收事件的场景

## 不适用场景
- 同步调用链路（无发布-订阅）
- 一次性任务（不依赖事件队列）
- 进程内函数直接 invoke
