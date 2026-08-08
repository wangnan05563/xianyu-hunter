# 复盘报告：2026-07-26 EventBus 启动耦合导致钉钉通知失效

> **版本**：v4.68.0
> **复盘日期**：2026-07-26
> **复盘方法**：Sequential Thinking 四维度复盘
> **触发来源**：用户引用 [迭代提示词.md#L31-53](../../../docs/00-待完成/迭代提示词.md#L31-L53)，要求基于最近历史对话复盘并优化技能
> **关联规范**：meta-rule #111（experimental）/ step 274 / B-REVIEW-331 / 模式 AF / step 107（既有，互补）

---

## H.1 复盘范围

| 范围 | 内容 | 来源 |
|------|------|------|
| 案例 C | 评分 80 以上商品未触发钉钉通知 → EventBus 主循环未启动 | 2026-07-26 当前对话 |

**问题现象**：用户反馈有评分 80 以上的商品（超过 `pass_score: 70` 门槛），但钉钉通知未触发。

---

## H.2 维度一：成功执行任务的完整步骤

### 案例 C：EventBus 启动耦合导致钉钉通知失效

**完整解决步骤**：

1. **链路梳理**：沿"评分 → 事件 → 通知"链路逐项核查配置
   - 评分门槛 `pass_score: 70`，80 分应过 `should_pass()` ✅
   - 风险等级 80 ≥ `auto_buy_score(80)` → `RiskLevel.LOW`，非 EXTREME ✅
   - AI 评估 `ai_auto_eval: false`，不会因 reject 跳过 ✅
   - 钉钉渠道 `dingtalk: true` + webhook + secret 已配置 ✅
   - `quiet_hours.enabled: false` ✅
   - `subscribed_events` 包含 `EVAL_PASSED` ✅

2. **配置排除**：所有配置项正常 → 排除配置问题，转向代码运行时行为追踪

3. **代码追踪**（关键转折点）：
   - [worker.py:489-511](../../../src/xianyu_hunter/modules/worker.py#L489-L511) 中 `self.event_bus.publish_nowait(Event)` 只是入队
   - [event_bus.py:54-63](../../../src/xianyu_hunter/infra/event_bus.py#L54-L63) 的 `run_forever()` 才是真正消费循环
   - `run_forever()` 只在 [startup.py:216](../../../src/xianyu_hunter/web/startup.py#L216) 的 `start_scheduler_in_background()` 内部启动

4. **根因定位**：`run_forever()` 启动有三重前置条件，任一不满足 EventBus 都不启动：
   - [deps.py:18-20](../../../src/xianyu_hunter/web/deps.py#L18-L20)：`XH_WITH_SCHEDULER=1` 环境变量
   - [startup.py:175-177](../../../src/xianyu_hunter/web/startup.py#L175-L177)：`container.collector is not None`
   - [startup.py:208-210](../../../src/xianyu_hunter/web/startup.py#L208-L210)：**启动时至少有一个 RUNNING 任务**——无则直接 return，EventBus 永不启动

5. **影响扩散分析**：[api_tasks.py:295-355](../../../src/xianyu_hunter/web/routes/api_tasks.py#L295-L355) 的 `control_task` 端点（resume/restart）完全不会启动 EventBus → 运行时新增任务永远发不出通知

6. **方案设计**：解耦启动——EventBus 主循环独立为无条件启动的后台任务

7. **实施修改**（5 处）：
   - 新增全局变量 `_event_bus_task`
   - 新增函数 `start_event_bus_in_background()`（含幂等防护 + 异常隔离）
   - 简化 `start_scheduler_in_background` 的 `_scheduler_loop`（移除 bus_task 管理）
   - `_on_startup` 中先启动 EventBus 再启动调度器
   - `_on_shutdown` 中独立停止 EventBus（在调度器之后）

8. **验证**：`py_compile` 通过 + GetDiagnostics 无错误 + grep 确认无遗留 `bus_task` 引用 + 现有测试不受影响

---

## H.3 维度二：任务执行过程中的不确定性与失败点

| 编号 | 不确定性/失败点 | 教训 |
|------|-----------------|------|
| U1 | 初看配置全正常，差点误判为"配置问题" | 配置正常 ≠ 链路正常，需追踪到代码运行时行为 |
| U2 | `publish_nowait` 方法名暗示"立即发送"，实际只是入队 | 方法名应准确反映行为，`publish_nowait` 实际语义是 `enqueue_nowait` |
| U3 | EventBus 启动条件埋在 `_scheduler_loop` 内部，外部看"调度器启动了"就以为 EventBus 也启动了 | 启动条件嵌套造成认知盲区，关键基础设施启动条件应显式可见 |
| U4 | 任务通过 API resume/restart 时不补启动 EventBus，原设计假设"启动时一次性决定" | 运行时新增的功能入口需考虑基础设施是否已就绪 |
| U5 | 无 RUNNING 任务时 EventBus 不启动，**无任何报错或日志** | 静默失败（无报错无日志）最难排查，关键基础设施需有启动日志 |
| U6 | shutdown 时 EventBus 停止逻辑原本耦合在 `_scheduler_loop` 的 CancelledError 中，调度器不启动则 EventBus 也不停止 | 启动/停止逻辑应成对独立，不能一侧启动另一侧才停止 |

---

## H.4 维度三：可抽象的固定流程与判断逻辑

### 流程 13：事件驱动基础设施启动解耦规范（本案新增，落地为 step 274）

```
1. 事件总线/消息队列/调度器等基础设施的消费者循环，必须与业务条件解耦
2. 启动顺序：基础设施先于业务调度器启动（确保业务 publish 时有消费者）
3. 停止顺序：基础设施后于业务调度器停止（确保业务停止时 publish 的事件能被消费）
4. 幂等防护：已在运行则跳过，避免重复启动产生多个消费者竞争同一队列
5. 异常隔离：消费者循环异常不能静默退出，需有兜底日志
6. 运行时新增入口：API/CLI 运行时新增业务任务时，需确认基础设施已就绪（或自动启动）
```

**判断逻辑**：
```
对于每个 publish-subscribe 模式的基础设施（EventBus/消息队列/事件循环）：
  1. 消费者循环的启动条件是否独立于业务任务存在？
  2. 业务 publish 事件时，是否有消费者在运行？
  3. 运行时新增业务入口（API/CLI）时，基础设施是否已就绪？
  4. 基础设施是否有启动日志（INFO）和异常退出日志（ERROR）？
  5. shutdown 时基础设施是否在业务调度器之后停止？
  任一答案为否 → 需要修复
```

**与 step 107（启动钩子完整性）的差异**：
- step 107 关注"依赖 container.browser/collector 的组件必须有启动钩子"（**组件覆盖维度**）
- step 274 关注"事件驱动基础设施的启动条件不能与业务任务耦合"（**启动条件维度**）
- 两者互补：step 107 防"漏启动组件"，step 274 防"启动条件嵌套导致静默失败"

**与 step 33（独立调度器隔离）的差异**：
- step 33 关注"生命周期不同的后台任务用独立调度器"（**资源隔离维度**）
- step 274 关注"基础设施启动不能依赖业务任务存在"（**启动依赖维度**）

---

## H.5 维度四：适用场景与不适用场景

### 流程 13（事件驱动基础设施启动解耦）

**适用场景**：
- 事件总线（EventBus / MessageQueue）的消费者循环
- 发布-订阅模式的基础设施（pub/sub）
- 后台调度器依赖的事件分发机制
- 任何"publish 方与 consume 方解耦"的架构
- Worker / Agent 把事件 publish 到队列、由独立消费者分发给 Notifier 的模式

**不适用场景**：
- 同步调用（无 publish-subscribe，直接 invoke）
- 一次性任务（启动即完成，无需持续消费）
- 进程内函数调用（无队列中间层）
- 前端组件间通信（如 React Context / Zustand，无独立消费者循环）

---

## H.6 新增规范与配置

### 新增 meta-rule #111（experimental）

| 字段 | 值 |
|------|-----|
| 编号 | #111 🆕v4.68 experimental |
| 名称 | EVENT-BUS-STARTUP-DECOUPLING 事件驱动基础设施启动解耦 |
| 一句话概述 | 事件总线/消息队列的消费者循环必须与业务任务存在性解耦；基础设施先于业务调度器启动、后于业务调度器停止；运行时新增业务入口时基础设施必须已就绪 |
| 落地位置 | coding-rules/scheduler.md / step 274 / B-REVIEW-331 / 模式 AF |
| 升正条件 | 1 季度内同类根因再发 ≥ 2 次（截至 2026-10-26） |

### 新增配置节点

`config/tech-stack.json#hardConstraints.eventBusStartupDecoupling`：
- `enabled`: true
- `infrastructureTypes`: event_bus / message_queue / pub_sub_loop
- `startupOrder`: before_business_scheduler
- `shutdownOrder`: after_business_scheduler
- `requireIdempotentGuard`: true
- `requireExceptionIsolation`: true
- `requireStartupLog`: true
- `observationPeriodQuarters`: 1
- `observationEndDate`: 2026-10-26
- `promotionThreshold`: 2

### 下游技能同步

| 技能 | 同步内容 |
|------|----------|
| xianyu-hunter-dev | meta-rule #111 + step 274 + 配置节点 + retrospective + version-history |
| xianyu-auto-testing | 模式 AF（事件驱动基础设施启动解联回归测试） |
| xianyu-backend-code-review | B-REVIEW-331（EVENT-BUS-STARTUP-DECOUPLING） |

---

## H.7 验证方法

### 静态验证
- `python -m py_compile src/xianyu_hunter/web/startup.py` 通过（已验证）
- 启动日志含 `"EventBus 主循环启动"` INFO 日志
- shutdown 时 EventBus 在 `_scheduler_task` 之后停止

### 一致性验证
- `grep -r "meta-rule #111\|EVENT-BUS-STARTUP-DECOUPLING\|step 274" .trae/skills/` 应在 3 个技能中各命中至少 1 次
- step 274 在 `_step-index.md` 与 `_step-index.json` 中编号一致

### 回归测试
- 调用 `xianyu-auto-testing` 技能执行模式 AF，验证：
  - 启动时无 RUNNING 任务 → EventBus 仍启动（日志可见）
  - 通过 API resume 任务 → 事件能被消费（钉钉通知触发）
- 验证 `pytest tests/test_dingtalk_notify_integration.py` 通过

### 场景验证（用户侧）
- 用 `XH_WITH_SCHEDULER=1` 启动，启动时 DB 无 RUNNING 任务
- 通过前端新建任务并启动
- 触发评分 ≥ pass_score 的商品
- 验证钉钉通知成功触发

### SOP 合规性
- #111 标注 `experimental` + 观察期截止日 `2026-10-26` + 升正阈值 `2 次`
- 与 step 107 互补不冲突，明确差异已在 H.4 说明
