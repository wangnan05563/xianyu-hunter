# 后端 Cookie 自愈测试

本文档描述模式 C（后端 Cookie 自愈测试模式）的详细操作步骤。

模式 C 用于验证后端 Cookie 两级自愈机制（token 刷新 → cookie 强制注入 → 放弃）的正确性。所有参数从 `config.yaml` 的 `backend_cookie_healing` 段读取，**禁止在文档中硬编码路径、命令、日志模式、测试用例名**。

## 1. 单元测试

### 1.1 运行全部自愈测试

执行 `unit_test.pytest_command_all`，将 `{test_file}` 替换为 `unit_test.test_file` 的值：

```powershell
{pytest_command_all 的值，{test_file} 已替换}
```

**预期输出**：所有 `healing_test_cases` 中列出的用例全部通过（exit code 0）。

### 1.2 逐个用例验证

对 `unit_test.healing_test_cases` 中每个用例，执行 `unit_test.pytest_command_template`，将 `{test_file}` 替换为 `unit_test.test_file`，`{test_name}` 替换为用例 `name` 字段：

```powershell
{pytest_command_template 的值，{test_file} 与 {test_name} 已替换}
```

记录每个用例的：
- 通过/失败状态
- 失败用例的堆栈信息（用于步骤 1.4 定位）

### 1.3 场景覆盖校验

以下 4 类场景必须有用例覆盖（由 `healing_test_cases[].description` 字段标注场景类型）：

| 场景类型 | 对应用例 name 字段 | 验证点 |
|---------|-------------------|--------|
| 多级自愈 | `test_refresh_token_second_level_heal_succeeds` | 第一级失败 → 第二级 cookie 注入成功 |
| 熔断标志重置 | `test_refresh_token_resets_session_invalid_before_retry` | 重试前重置 `session_invalid`，重试失败时重新设置 |
| 诊断日志 | `test_refresh_token_both_levels_fail_logs_diagnostics` | 两级均失败时调用 `_log_cookie_diagnostics` |
| 非相关原因跳过 | `test_refresh_token_skips_when_reason_not_home_title_redirect` | reason 不匹配 `home_title_redirect` 时不进入自愈 |

### 1.4 失败定位

若有用例失败，按 `key_files` 顺序读取对应源码定位根因：

- `collection_service.py`：
  - `_refresh_token_and_retry_detail`：两级自愈主流程
  - `_force_reinject_cookies_from_store`：第二级 cookie 强制注入
  - `_log_cookie_diagnostics`：诊断日志输出
- `batch_refresh_scheduler.py`：`_sync_cookie_before_batch` 批次级预检
- `unified_login.py`：`_post_login_cookie_health_check` 登录后健康探测

## 2. 集成测试

### 2.1 环境准备

1. 复用诊断模式 DT-01 ~ DT-03，确保 web 进程已运行、构建产物最新、HTTP 响应正常
2. **关键**：修改 `key_files` 中任一文件后必须重启 web 进程，否则新代码不生效
   - 重启命令：`web_process.start_command`（将 `{port}` 替换为 `web_process.port`）
3. 清空旧日志：删除或备份 `integration_test.stdout_log_file`，便于识别新产生的日志（避免与历史日志混淆）

### 2.2 登录后健康探测验证

1. 触发任一登录流程（访问 `unified_login` 提供的登录端点）
2. 等待 2-3 秒让日志落盘
3. 在 `integration_test.stdout_log_file` 中查找 `login_health_check.expected_log`：
   ```powershell
   # {log_file} ← integration_test.stdout_log_file
   # {pattern}  ← login_health_check.expected_log
   Select-String -Path "{log_file}" -Pattern "{pattern}" -Encoding UTF8
   ```
4. 若出现 `login_health_check.failure_log`，标记为问题
5. 关联源码：`unified_login._post_login_cookie_health_check`

### 2.3 批次采集前预检验证

1. 触发一次批量采集任务（通过前端"批量采集"页或对应 API）
2. 等待 2-3 秒让日志落盘
3. 在日志中查找 `batch_precheck.expected_log`：
   ```powershell
   # {pattern} ← batch_precheck.expected_log
   Select-String -Path "{log_file}" -Pattern "{pattern}" -Encoding UTF8
   ```
4. 若出现 `batch_precheck.failure_log`，标记为问题
5. 关联源码：`batch_refresh_scheduler._sync_cookie_before_batch`

### 2.4 Cookie 失效两级自愈日志序列验证

1. 触发 Cookie 失效场景：
   - 方式 A：清空 cookie_store（通过 `/api/anticrawl` 管理页或数据库维护页）
   - 方式 B：访问详情接口强制返回 `home_title_redirect` reason
2. 等待 5-10 秒让两级自愈流程完整执行（第一级 token 刷新 + 第二级 cookie 注入）
3. 按 `integration_test.expected_log_sequence` 顺序在日志中匹配每个 `pattern`：
   ```powershell
   # 逐个 pattern 检查
   Select-String -Path "{log_file}" -Pattern "{pattern}" -Encoding UTF8
   ```
4. 记录每个 pattern：
   - 是否出现（命中/未命中）
   - 出现次数
   - 首次出现的时间戳（用于验证时序）
5. 时序校验规则：
   - `expected_log_sequence[0]`（"已强制刷新 _m_h5_tk 后重试"）与 `expected_log_sequence[1]`（"跳过 _m_h5_tk 刷新"）**互斥**：取决于 5 分钟内是否已刷新过 token，命中任一即视为第一级触发
   - `expected_log_sequence[2]`（"_m_h5_tk 刷新后重试仍失败"）应在第一级失败后出现，标志进入第二级
   - `expected_log_sequence[3]`（"cookie 重新注入后重试成功"）仅在第二级成功时出现；若两级均失败则不出现
   - `expected_log_sequence[4]`（"会话失效诊断"）仅在两级均失败时出现

## 3. 诊断输出

### 3.1 单元测试报告格式

```
## 单元测试结果

| 用例名 | 描述 | 状态 | 失败堆栈 |
|--------|------|------|---------|
| test_refresh_token_resets_session_invalid_before_retry | 验证熔断标志重置 | PASS | - |
| test_refresh_token_second_level_heal_succeeds | 验证两级自愈 | PASS | - |
| test_refresh_token_both_levels_fail_logs_diagnostics | 验证诊断日志 | PASS | - |
| test_refresh_token_skips_when_reason_not_home_title_redirect | 验证非相关原因跳过 | PASS | - |

通过率：4/4 (100%)
```

### 3.2 集成测试报告格式

```
## 集成测试结果

### 登录后健康探测
- 状态：PASS
- 命中日志："登录后健康探测通过：身份 cookie 齐全（共 N 个 cookie）"

### 批次采集前预检
- 状态：PASS
- 命中日志："[BatchRefresh#xxx] 批次前 Cookie 预检通过"

### 两级自愈日志序列
| 序号 | pattern | 描述 | 命中 | 次数 | 首次时间戳 |
|------|---------|------|------|------|-----------|
| 1 | 已强制刷新 _m_h5_tk 后重试 | 第一级自愈日志 | YES | 1 | 2026-07-17 10:00:01 |
| 2 | 跳过 _m_h5_tk 刷新 | 跳过刷新日志 | NO | 0 | - |
| 3 | _m_h5_tk 刷新后重试仍失败 | 第二级自愈触发日志 | YES | 1 | 2026-07-17 10:00:02 |
| 4 | cookie 重新注入后重试成功 | 第二级自愈成功日志 | YES | 1 | 2026-07-17 10:00:03 |
| 5 | 会话失效诊断 | 诊断日志 | NO | 0 | - |

时序校验：PASS（第一级 → 第二级触发 → 第二级成功）
```

### 3.3 问题报告格式

```
## 发现的问题

### 问题 1
- 描述：xxx
- 关联 key_files：src/xianyu_hunter/modules/collection_service.py
- 复现步骤：xxx
- 建议修复方向：xxx
```

## 4. 已知陷阱

执行模式 C 时需特别注意以下陷阱（来自历史踩坑）：

1. **服务未重启导致新代码未生效**：修改 `key_files` 中文件后，若仅重新构建前端而未重启 web 进程，后端 Python 代码不会重新加载。**必须重启 web 进程**（执行 `web_process.start_command`）。症状：单元测试通过但集成测试仍复现旧问题。

2. **PowerShell 管道缓冲导致输出截断**：pytest 输出较长时，PowerShell 管道可能截断或缓冲。建议用 `| Out-String -Stream` 或重定向到文件后用 `Read` 工具读取，避免直接在终端查看长输出。

3. **pytest 退出码非 0 但看不到失败信息**：Windows 控制台编码问题可能导致中文失败信息乱码。解决：
   - 在执行前运行 `chcp 65001` 切换到 UTF-8 编码
   - 或在 pytest 命令中加 `--tb=short` 减少输出体积

4. **日志文件未及时落盘**：loguru 默认异步刷盘，触发操作后立即读取日志可能缺失最新行。等待 2-3 秒后再读取 `stdout_log_file`。

5. **JSON 日志与纯文本日志混淆**：
   - `data_logs_dir` 下的 `xianyu_*.log` 是 JSON 序列化日志（loguru `serialize=True`），中文日志内容在 JSON 的 `message` 字段中，直接 `Select-String` 匹配中文 pattern 会失败
   - `stdout_log_file`（`run.stdout.log`）是纯文本日志，直接 `Select-String` 即可匹配
   - **推荐用 `stdout_log_file` 做日志序列验证**，JSON 日志仅在需要 request_id 关联分析时使用

6. **两级自愈时序互斥性**：`expected_log_sequence` 中 pattern[0]（"已强制刷新"）与 pattern[1]（"跳过刷新"）是互斥的，取决于 5 分钟内是否已刷新过 token。不会同时出现，匹配时允许任一出现即视为第一级触发。

7. **cookie_store 清空影响其他功能**：集成测试中清空 cookie_store 会导致所有依赖 cookie 的接口失败。测试后需重新登录恢复 cookie，避免影响后续测试。

8. **批次预检依赖采集任务触发**：`_sync_cookie_before_batch` 仅在批量采集任务启动时调用，不会自动触发。需手动启动一个批量采集任务才能验证预检日志。

9. **PowerShell Select-String 默认编码问题**：读取 UTF-8 日志文件时需显式指定 `-Encoding UTF8`，否则中文 pattern 可能因编码不匹配而漏命中。
