# 模式 AF：事件驱动基础设施启动解联回归测试

> 对应 B-REVIEW-331（EventBus 启动耦合导致钉钉通知失效 Bug 修复）
> 配置节点：`config.yaml#event_bus_startup_decoupling_test`
> 配套编码规范：`xianyu-hunter-dev` step 274（scheduler.md，meta-rule #111）

### 触发关键词
- 测试 EventBus 启动 / 验证事件链路 / 测试钉钉通知触发 / 测试通知不生效
- 评分达标但通知未触发 / 事件入队但无消费者 / 通知静默失效
- EventBus 消费者循环 `run_forever` 的启动位置/启动条件被修改后
- `_on_startup` / `_on_shutdown` 中 EventBus 启停顺序被修改后
- API `control_task`（resume/restart）路径被修改后

### 适用场景
- EventBus `run_forever()` 消费者循环的启动位置/启动条件被修改
- `_on_startup` / `_on_shutdown` 中 EventBus 启停顺序被修改
- API `control_task`（resume/restart）路径被修改，需验证是否补启动 EventBus
- 用户报告"评分达标但通知未触发"、"事件入队但无消费者"、"通知静默失效"

### 检查点

| ID | 检查项 | 验证方法 | 严重等级 |
|----|--------|----------|----------|
| AF-01 | 消费者循环独立启动 | grep `run_forever\|consume_loop` 定位消费者循环 → 检查是否在独立启动函数中（非嵌套在业务调度器内部） | Blocker |
| AF-02 | 启动顺序：EventBus 先于调度器 | 读取 `_on_startup` → 验证 `start_event_bus_in_background` 在 `start_scheduler_in_background` 之前 | Critical |
| AF-03 | 停止顺序：EventBus 后于调度器 | 读取 `_on_shutdown` → 验证 `_event_bus_task.cancel()` 在 `_scheduler_task.cancel()` 之后 | Critical |
| AF-04 | 幂等防护 | grep 启动函数 → 验证含 `if _event_bus_task is not None and not _event_bus_task.done(): return` | Major |
| AF-05 | 异常隔离 | grep 消费者循环 except 块 → 验证除 CancelledError 外的异常 `logger.exception` 记录 | Major |
| AF-06 | 运行时入口补启动 | grep `control_task\|resume\|restart` → 验证 resume/restart 时检查 `_event_bus_task` 是否运行 | Critical |

### 步骤 0：加载配置
读取 `config.yaml` 的 `event_bus_startup_decoupling_test` 段。重点关注 `key_files`（startup.py / event_bus.py / api_tasks.py / worker.py / notifier/hub.py）、`startup_log_keyword`、`require_no_running_task_test`、`require_resume_trigger_test`。禁止硬编码任何日志关键词、测试条件。

### 步骤 1：静态扫描
1. **消费者循环定位**：`grep -n "run_forever\|consume_loop\|_dispatch" src/xianyu_hunter/` → 列出所有消费者循环位置
2. **publish 调用定位**：`grep -n "publish_nowait\|publish(" src/xianyu_hunter/` → 列出所有 publish 调用点
3. **启动条件嵌套检查**：`grep -n "if not workers\|if not.*RUNNING\|if not container.collector" src/xianyu_hunter/web/startup.py` → 检查这些 return 是否阻断了 EventBus 启动
4. **运行时入口检查**：`grep -n "control_task\|def.*resume\|def.*restart" src/xianyu_hunter/web/routes/api_tasks.py` → 检查是否补启动 EventBus

### 步骤 2：运行时验证
1. **无 RUNNING 任务启动验证**：
   - 清空 DB 中 RUNNING 状态任务（或用空 DB）
   - 用 `XH_WITH_SCHEDULER=1` 启动服务
   - 检查启动日志含 `"EventBus 主循环启动"` INFO 日志
   - 验证 EventBus 主循环已运行（非 None 且未 done）
2. **运行时 resume 触发验证**：
   - 启动服务（无 RUNNING 任务）
   - 通过 API 创建任务并 resume
   - 触发评分 ≥ pass_score 的商品
   - 验证钉钉通知成功触发（或 NotifierHub 收到 EVAL_PASSED 事件）
3. **shutdown 顺序验证**：
   - 启动服务后发送 shutdown 信号
   - 检查日志：`_scheduler_task` 先停止，`_event_bus_task` 后停止
   - 验证 EventBus stop() 在调度器 stop_all() 之后调用

### 步骤 3：幂等性与异常隔离验证
1. **幂等性**：连续调用 `start_event_bus_in_background` 两次 → 第二次应跳过并输出 "已在运行" 日志
2. **异常隔离**：模拟 `run_forever` 抛异常 → 验证 `logger.exception` 记录，task 标记为 done

### 步骤 4：生成测试报告
输出事件驱动基础设施启动解联回归测试报告，包含：
1. **六项检查点状态**：AF-01~AF-06 静态扫描与运行时验证结果
2. **启动条件嵌套问题**：是否有 return 阻断 EventBus 启动
3. **运行时入口补启动问题**：resume/restart 是否检查 `_event_bus_task`
4. **违规清单**：违规项的文件路径、行号、违规类型、严重等级
5. **修复建议**：引用 step 274 + B-REVIEW-331 的详细描述

### 配置参数
`config.yaml#event_bus_startup_decoupling_test`：
- `key_files`：需回归验证的文件列表（startup.py / event_bus.py / api_tasks.py / worker.py / notifier/hub.py）
- `startup_log_keyword`：启动日志关键词（默认 `"EventBus 主循环启动"`）
- `require_no_running_task_test`：是否强制"无 RUNNING 任务启动"验证（默认 true）
- `require_resume_trigger_test`：是否强制"resume 触发通知"验证（默认 true）

### 关联规范
- 配套编码规范：`xianyu-hunter-dev` step 274（scheduler.md，meta-rule #111 落地 experimental）
- 配套审查规范：`xianyu-backend-code-review` B-REVIEW-331（EVENT-BUS-STARTUP-DECOUPLING）
