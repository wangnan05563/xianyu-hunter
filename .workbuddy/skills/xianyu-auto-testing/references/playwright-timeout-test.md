# Playwright 超时保护测试

本文档描述模式 D（Playwright 超时保护测试模式）的详细操作步骤。

模式 D 用于验证浏览器自动化代码中 async 阻塞调用（如 `context.cookies()`、`bc.storage_state()`）是否被 `asyncio.wait_for` 超时保护包裹，避免 Playwright IPC 阻塞导致子进程心跳停滞被误判卡死。所有参数从 `config.yaml` 的 `async_timeout_test` 段读取，**禁止在文档中硬编码路径、超时值、正则、API 名**。

## 1. 静态扫描测试

### 1.1 async 阻塞调用超时保护扫描（AT-PT-001）

扫描所有 `await bc.xxx()/page.xxx()` 调用，验证是否被 `asyncio.wait_for(..., timeout=N)` 包裹。扫描范围由 `async_timeout_test.key_files` 指定，正则模式由 `scenarios[AT-PT-001].grep_pattern` 提供。

```powershell
# {files}  ← async_timeout_test.key_files[].path 拼接
# {pattern} ← scenarios[AT-PT-001].grep_pattern
Select-String -Path {files} -Pattern '{pattern}' -Encoding UTF8 | ForEach-Object {
    "$($_.Path):$($_.LineNumber): $($_.Line)"
}
```

**判定规则**（来自 `scenarios[AT-PT-001].expect`）：每个匹配项必须被 `asyncio.wait_for(..., timeout=N)` 包裹，超时值 N 从 `protected_apis.*.timeout_sec` 读取，不硬编码。

**保护分类**（由 `protected_apis` 配置）：
- `lightweight_read`（`cookies()` / `title()` / `url()`）：超时 `protected_apis.lightweight_read.timeout_sec`
- `heavy_serialize`（`storage_state()` / `snapshot()`）：超时 `protected_apis.heavy_serialize.timeout_sec`
- `evaluate`（`evaluate()`）：超时 `protected_apis.evaluate.timeout_sec`

### 1.2 心跳与阶段超时协同扫描（AT-PT-002）

验证子进程心跳架构中每阶段有独立 `status` 字段 + 独立超时阈值，且阶段内阻塞调用超时之和小于心跳阈值乘以 `(1 - safety_margin)`。

```powershell
# {files}   ← async_timeout_test.key_files[].path 拼接
# {pattern} ← scenarios[AT-PT-002].grep_pattern
Select-String -Path {files} -Pattern '{pattern}' -Encoding UTF8 | ForEach-Object {
    "$($_.Path):$($_.LineNumber): $($_.Line)"
}
```

**判定规则**（来自 `scenarios[AT-PT-002].expect`）：
- 心跳字段名：`heartbeat_coordination.status_file_field`（即 `ts`）
- 每个阶段（`heartbeat_coordination.stages[]`）必须有独立 `status` 与 `timeout_sec`
- 阶段内所有阻塞调用超时之和 < `stages[].timeout_sec * (1 - heartbeat_coordination.safety_margin)`
- 全局上限：累计超时不超过 `heartbeat_coordination.max_accumulated_timeout_sec`

**阶段清单**（从 `heartbeat_coordination.stages` 读取）：
| status | timeout_sec |
|--------|-------------|
| starting | 90.0 |
| opening | 90.0 |
| running | 90.0 |
| waiting | 30.0 |
| already_logged | 90.0 |

### 1.3 跨代码块一致性扫描（AT-PT-003）

统计同一 API 在不同文件的调用次数，对比保护措施是否一致。一致性阈值由 `consistency_check.min_occurrences` 决定，保护措施清单由 `consistency_check.protected_measures` 提供。

```powershell
# 第一步：统计每个 API 在所有 key_files 中的出现次数
# {files}   ← async_timeout_test.key_files[].path 拼接
# {apis}    ← protected_apis.*.apis 汇总（cookies|storage_state|snapshot|title|url|evaluate）
Select-String -Path {files} -Pattern '{apis}' -Encoding UTF8 | Group-Object -Property Pattern | Sort-Object Count -Descending

# 第二步：对出现次数 ≥ min_occurrences 的 API，逐文件检查保护措施是否一致
# {measures} ← consistency_check.protected_measures（asyncio.wait_for|try/except|fallback）
Select-String -Path {files} -Pattern '{measures}' -Encoding UTF8 | Group-Object -Property Path
```

**判定规则**（来自 `scenarios[AT-PT-003].expect`）：同一 API 在 `consistency_check.min_occurrences` 处以上调用时，保护措施（`consistency_check.protected_measures`）必须一致。

### 1.4 fallback 策略扫描（AT-PT-004）

验证 `asyncio.wait_for` 的 `except` 块在超时后提供 fallback 值，不中断主流程。

```powershell
# {files} ← async_timeout_test.key_files[].path 拼接
# 匹配 except 块中是否出现 fallback 赋值（如 return [] / return None / return best / = [] / = {} 等）
Select-String -Path {files} -Pattern 'except\s+asyncio\.TimeoutError|except\s+Exception' -Encoding UTF8 -Context 0,5 | ForEach-Object {
    "$($_.Path):$($_.LineNumber): $($_.Line)"
    $_.Context.PostContext | ForEach-Object { "    >> $_" }
}
```

**判定规则**（来自 `scenarios[AT-PT-004].expect`）：`asyncio.wait_for` 的 `except` 块必须提供 fallback 值（如 `best` / 空列表 / `None`），不得直接 `raise` 中断主流程。

## 2. 集成测试

### 2.1 模拟 IPC 阻塞验证心跳持续更新

验证当 Playwright IPC 阻塞时，子进程心跳 `ts` 字段仍能持续更新，未被误判为卡死。

**测试步骤**：
1. 启动浏览器登录流程（`scripts/browser_login.py`），进入 `running` 阶段
2. 模拟 `context.cookies()` 阻塞：在测试环境注入延迟 mock，使 `cookies()` 调用挂起超过 `protected_apis.lightweight_read.timeout_sec`
3. 监听 `heartbeat_coordination.status_file_field`（即 `ts`）字段更新频率：
   ```powershell
   # {status_file} ← 子进程心跳文件路径
   # 监听 10 秒内 ts 字段更新次数
   $start = Get-Date
   $updates = 0
   $lastTs = $null
   while ((Get-Date) - $start -lt [TimeSpan]::FromSeconds(10)) {
       $content = Get-Content "{status_file}" -Raw -Encoding UTF8
       $ts = ($content | ConvertFrom-Json).ts
       if ($ts -ne $lastTs) { $updates++; $lastTs = $ts }
       Start-Sleep -Milliseconds 500
   }
   Write-Host "心跳更新次数：$updates"
   ```
4. **预期**：心跳更新次数 ≥ 5（10 秒内每 2 秒至少一次），说明 `asyncio.wait_for` 超时保护生效，IPC 阻塞未影响心跳协程

### 2.2 验证超时后 fallback 值正确性

验证 `asyncio.wait_for` 触发 `TimeoutError` 后，`except` 块返回的 fallback 值类型与语义正确。

**测试步骤**：
1. 在 `_collect_settled_cookies` 第一轮调用中注入 mock，使 `context.cookies()` 超时
2. 触发登录流程，捕获 `_collect_settled_cookies` 返回值
3. 验证 fallback 值符合预期：
   - `cookies()` 超时 → fallback 为空列表 `[]`（不影响后续 `best` 合并）
   - `storage_state()` 超时 → fallback 为 `None` 或最小化 dict
   - `evaluate()` 超时 → fallback 为 `None` 或业务约定的默认值
4. 验证主流程未中断：登录流程继续执行，最终状态为 `already_logged` 或合理 fallback 路径

## 3. 诊断输出

### 3.1 静态扫描报告格式

```
## Playwright 超时保护测试结果

### AT-PT-001 async 阻塞调用超时保护
| 文件 | 行号 | API | 是否被 wait_for 包裹 | 超时值来源 | 状态 |
|------|------|-----|---------------------|-----------|------|
| scripts/browser_login.py | 123 | cookies() | YES | protected_apis.lightweight_read.timeout_sec | PASS |
| scripts/browser_login.py | 156 | storage_state() | NO | - | FAIL |

### AT-PT-002 心跳与阶段超时协同
| 阶段 status | 阈值 timeout_sec | 安全裕度 | 阶段内累计超时 | 上限 | 状态 |
|-------------|-----------------|---------|---------------|------|------|
| starting | 90.0 | 0.3 | 15.0 | 63.0 | PASS |
| running | 90.0 | 0.3 | 25.0 | 63.0 | PASS |

### AT-PT-003 跨代码块一致性
| API | 出现次数 | 出现位置 | 保护措施 | 一致性 | 状态 |
|-----|---------|---------|---------|--------|------|
| cookies() | 3 | browser_login.py:123, auth_helper.py:45, browser.py:67 | asyncio.wait_for | 一致 | PASS |
| storage_state() | 2 | browser_login.py:156, browser.py:89 | [不一致：一处 wait_for 一处无] | 不一致 | FAIL |

### AT-PT-004 fallback 策略
| 文件 | 行号 | except 块位置 | fallback 值 | 状态 |
|------|------|--------------|------------|------|
| scripts/browser_login.py | 130 | cookies() except | [] (空列表) | PASS |
| scripts/browser_login.py | 162 | storage_state() except | raise TimeoutError | FAIL |
```

### 3.2 集成测试报告格式

```
## 集成测试结果

### 2.1 IPC 阻塞下心跳持续更新
- 测试阶段：running
- 监听时长：10 秒
- 心跳更新次数：6
- 预期最低次数：5
- 状态：PASS

### 2.2 超时 fallback 值正确性
| API | 触发超时方式 | fallback 值 | 主流程是否中断 | 状态 |
|-----|-------------|------------|---------------|------|
| cookies() | 注入 6s 延迟（>5s 阈值） | [] | 否 | PASS |
| storage_state() | 注入 11s 延迟（>10s 阈值） | None | 否 | PASS |
```

### 3.3 问题报告格式

```
## 发现的问题

### 问题 1
- 描述：scripts/browser_login.py:156 的 storage_state() 调用未包裹 asyncio.wait_for
- 关联 key_files：scripts/browser_login.py
- 对应用例：AT-PT-001
- 严重程度：critical
- 复现步骤：执行 §1.1 Select-String 命令
- 建议修复方向：用 asyncio.wait_for(bc.storage_state(), timeout=protected_apis.heavy_serialize.timeout_sec) 包裹，except 块返回 None
```

## 4. 已知陷阱

执行模式 D 时需特别注意以下陷阱（来自历史踩坑）：

1. **page.goto 已有 timeout 参数，无需额外 wait_for**
   - 症状：对 `page.goto(url, timeout=30000)` 再套一层 `asyncio.wait_for`，导致超时阈值重复、语义混淆
   - 解决方案：`page.goto` / `page.wait_for_selector` / `page.wait_for_load_state` 等原生支持 `timeout` 参数的 API，直接使用原生参数，不再叠加 `asyncio.wait_for`。仅对 `cookies()` / `storage_state()` / `snapshot()` / `evaluate()` 等无 timeout 参数的读取型 API 使用 `asyncio.wait_for`

2. **同步 Playwright API 不适用**
   - 症状：对 `sync_playwright()` 下的 `page.cookies()` 套用 `asyncio.wait_for`，导致 `TypeError: object dict can't be used in 'await' expression`
   - 解决方案：`asyncio.wait_for` 仅适用于 `async_playwright()` 下的协程调用。同步 API 阻塞由 Playwright 内部 `timeout` 参数或子进程级超时（如 `subprocess.Popen` + 心跳）保护，不在此模式扫描范围

3. **一次性调用超时保护无意义**
   - 症状：对启动期一次性 `await browser.new_context()` 套 `asyncio.wait_for`，超时后无法 fallback，反而引入新故障
   - 解决方案：`asyncio.wait_for` 仅用于"有 fallback 路径"的读取型调用（如 `cookies()` fallback 空列表）。启动期一次性调用（`new_context` / `new_page`）失败应直接 fail-fast，不进入超时保护扫描范围

4. **_collect_settled_cookies 第一轮超时 best 为空列表**
   - 症状：第一轮 `cookies()` 超时后 fallback 返回 `None`，导致后续 `best = best or []` 逻辑分支异常
   - 解决方案：`_collect_settled_cookies` 第一轮 `cookies()` 的 `except` 块必须返回 `[]`（空列表），不得返回 `None`。文档扫描时若发现 `except` 块返回 `None`，标记为 FAIL（对应 `scenarios[AT-PT-004]`）
