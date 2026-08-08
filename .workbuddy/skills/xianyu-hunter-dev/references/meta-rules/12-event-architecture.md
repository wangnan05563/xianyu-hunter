# 事件架构
> 包含元规范 #111 - #111

## 111. 事件驱动基础设施启动解耦（EVENT-BUS-STARTUP-DECOUPLING）🆕v4.68.0 experimental

**问题**：事件总线/消息队列的消费者循环（如 `EventBus.run_forever()`）被嵌套在业务调度器启动函数内部（如 `start_scheduler_in_background` 的 `_scheduler_loop`），导致消费者循环的启动受制于业务条件——"是否有 RUNNING 任务""collector 是否就绪""环境变量是否开启"任一不满足时，消费者循环永不启动。后续通过 API/CLI 运行时新增业务任务时，`publish_nowait` 事件入队但无消费者，订阅者（如 NotifierHub）永远收不到事件，钉钉等通知静默失效，且**无任何报错日志**，极难排查。

**核心规则**：
1. 事件总线/消息队列/事件循环等基础设施的消费者循环，必须与业务任务存在性解耦——启动条件独立于"是否有业务任务在运行"
2. 启动顺序：基础设施**先于**业务调度器启动（确保业务 `publish` 事件时有消费者在等待）
3. 停止顺序：基础设施**后于**业务调度器停止（确保业务停止时 `publish` 的终态事件能被消费）
4. 启动函数必须**幂等**：已在运行则跳过，禁止重复启动产生多个消费者竞争同一队列
5. 消费者循环异常**不能静默退出**：除 `CancelledError` 外的异常必须 `logger.exception` 记录，避免任务静默死亡
6. 运行时新增业务入口（API resume/restart、CLI 命令）时，必须确认基础设施已就绪——若基础设施未启动则自动启动，不能假设"启动时一次性决定"

**判断信号**：
- `grep "run_forever\|consume_loop\|_dispatch" src/` 找到消费者循环 → 检查其启动是否嵌套在业务调度器函数内部
- `grep "publish_nowait\|publish(" src/` 找到 publish 调用 → 反向追踪消费者是否在同一启动链路中
- `grep "if not workers\|if not.*RUNNING\|if not container.collector" src/xianyu_hunter/web/startup.py` → 若该 return 阻断了基础设施启动则违反规则1
- `grep "control_task\|resume\|restart" src/xianyu_hunter/web/routes/` → 检查是否补启动基础设施
- 启动日志缺 `"EventBus 主循环启动"` 或类似 INFO → 违反规则5

**配置参数**：`eventBusStartupDecoupling` 节点（enabled / infrastructureTypes / startupOrder / shutdownOrder / requireIdempotentGuard / requireExceptionIsolation / requireStartupLog / observationPeriodQuarters / observationEndDate / promotionThreshold / applicableScenarios / nonApplicableScenarios）

**适用**：事件总线（EventBus/MessageQueue）的消费者循环；发布-订阅模式的基础设施；后台调度器依赖的事件分发机制；Worker/Agent publish 事件到队列、由独立消费者分发给 Notifier 的模式
**不适用**：同步调用（无 publish-subscribe）；一次性任务（启动即完成）；进程内函数直接 invoke（无队列中间层）；前端组件间通信（React Context/Zustand，无独立消费者循环）

**与既有规范的关系**：
- #48（SCHEDULER-RUNTIME-TOGGLE-SYMMETRY，step 194）：管"调度器运行时开关对称性"（启用/禁用 job），本规范管"消费者循环启动条件解耦"（启动依赖），互补
- step 33（独立调度器隔离模式）：管"生命周期不同的任务用独立调度器"（资源隔离），本规范管"基础设施启动不能依赖业务任务存在"（启动依赖），互补
- step 107（启动钩子完整性）：管"依赖 browser/collector 的组件必须有启动钩子"（组件覆盖），本规范管"启动条件不能与业务任务耦合"（启动条件），互补——step 107 防"漏启动组件"，本规范防"启动条件嵌套导致静默失败"

**历史教训**：2026-07-26 用户反馈评分 80 以上商品未触发钉钉通知。配置全正常（`pass_score: 70`、`dingtalk: true`、`quiet_hours.enabled: false`、`subscribed_events` 含 `EVAL_PASSED`），根因是 `EventBus.run_forever()` 被嵌套在 `start_scheduler_in_background` 的 `_scheduler_loop` 内部，三重前置条件任一不满足即 return：① `XH_WITH_SCHEDULER=1` ② `container.collector is not None` ③ 启动时有 RUNNING 任务。第③条最隐蔽——启动时无 RUNNING 任务则 EventBus 永不启动，且 `api_tasks.py` 的 `control_task`（resume/restart）完全不补启动 EventBus。结果 `worker.publish_nowait(EVAL_PASSED)` 事件入队但无消费者，NotifierHub 永远收不到事件，钉钉永不触发，且无任何报错日志。修复：抽离 `start_event_bus_in_background()` 独立启动函数，在 `_on_startup` 中无条件启动（先于调度器），`_on_shutdown` 中独立停止（后于调度器），含幂等防护与异常隔离。

**experimental 升正条件**：1 季度内（截至 2026-10-26）同类根因再发 ≥ 2 次

**对应 step**：step 274（scheduler.md）。
