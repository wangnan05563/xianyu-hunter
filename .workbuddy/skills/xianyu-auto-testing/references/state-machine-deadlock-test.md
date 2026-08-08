# 模式 L：状态机死锁回归测试

> 对应 meta-rule #86（SCHEDULER-STATE-MACHINE-RECOVERY）/ B-REVIEW-245
> 配套 config 节点：`config.yaml#mode_l_state_machine_deadlock_test`

### 何时触发

满足以下任一条件即触发：
- 用户要求"测试状态机死锁" / "验证 pause/resume 闭环" / "测试调度器恢复"
- 用户报告"任务启动后不周期执行" / "resume 后无响应" / "任务永久卡死"
- `mode_l_state_machine_deadlock_test.key_files` 中任一文件被修改后需要回归验证
- scheduler / 任务循环 / 会话管理相关代码（pause_event / should_pause / resume）修改后
- 调度器 `_run_loop` / `_execute_run_once_locked` / `_run_one_iteration` 函数修改后

### 步骤 0：加载配置

读取 `config.yaml`，重点关注以下配置段：
- `mode_l_state_machine_deadlock_test.unit_test`：单元测试文件、pytest 命令模板、测试用例列表
- `mode_l_state_machine_deadlock_test.integration_test`：集成测试日志文件、预期日志序列
- `mode_l_state_machine_deadlock_test.key_files`：关键代码路径（用于代码变更后回归测试范围判定）
- `mode_l_state_machine_deadlock_test.state_machine_checks`：状态机校验项清单

**禁止在流程中编码任何路径、命令、日志模式、测试用例名**。所有参数从 `config.yaml` 读取。

### 步骤 1：单元测试验证

详细操作见 `references/state-machine-deadlock-test.md` 的"单元测试"部分。

1. **运行全部状态机测试**：执行 `unit_test.pytest_command_all`（将 `{test_file}` 替换为 `unit_test.test_file`）
2. **逐个用例验证**：对 `unit_test.test_cases` 中每个用例：
   - 执行 `unit_test.pytest_command_template`（替换 `{test_file}` 和 `{test_name}`）
   - 记录通过/失败状态与失败堆栈
3. **场景覆盖校验**：以下 5 类场景必须有用例覆盖（由 `test_cases` 描述字段标识）：
   - **pause/resume 事件配对**：pause_event.set() 有对应 wait()
   - **暂停语义验证**：暂停后 loop 回到顶部阻塞，不 break 退出
   - **返回值语义统一**：should_pause 返回 False（继续循环）而非 True（退出循环）
   - **错误计数隔离**：会话失效暂停时不重置 consecutive_errors
   - **恢复前置校验**：resume 前检查根因消除
4. **失败定位**：若有用例失败，按 `key_files` 顺序读取对应源码定位根因

### 步骤 2：集成测试验证

详细操作见 `references/state-machine-deadlock-test.md` 的"集成测试"部分。

1. **环境准备**：复用诊断模式 DT-01 ~ DT-03，确保服务已用最新代码重启
   - **关键陷阱**：修改 `key_files` 中任一文件后必须重启服务，否则新代码不生效
2. **状态机死锁场景模拟**：
   - 触发会话失效（如清空 cookie_store 或注入无效 token）
   - 观察任务是否暂停（非停止）
   - 在 `integration_test.stdout_log_file` 中查找 `pause_log.expected_pattern`
   - 验证任务状态显示"已暂停"而非"运行中"（`state_machine_checks.pause_status_field`）
3. **恢复闭环验证**：
   - 恢复会话（如重新登录或注入有效 cookie）
   - 调用 resume API
   - 在日志中查找 `resume_log.expected_pattern`
   - 验证任务是否恢复周期执行（`state_machine_checks.resume_verification`）
4. **死锁检测**：
   - 在 `state_machine_checks.deadlock_detection.timeout_seconds`（默认 60s）内观察是否有周期执行日志
   - 超时无日志 → 标记为死锁问题

### 步骤 3：诊断输出

报告包含：
1. **单元测试通过率**：用例数、通过数、失败数、失败用例详情
2. **集成测试状态机闭环验证**：暂停→恢复→周期执行的全链路日志匹配
3. **死锁检测结果**：是否有死锁、死锁持续时间、恢复方式
4. **发现的问题**：问题描述、关联的 `key_files` 条目、发现步骤、建议修复方案
