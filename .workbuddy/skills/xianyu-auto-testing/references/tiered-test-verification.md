# 测试验证三档机制

本文档描述测试验证的三档机制（Tier 1/2/3）、降级触发条件、长任务日志输出规范与系统资源过载容错。

所有参数从 `config.yaml` 的以下配置段读取，**禁止在文档中硬编码 CPU 阈值、超时秒数、文件数阈值、PowerShell 命令**：

- `tiered_test_verification`：三档机制档位定义、降级触发条件、测试覆盖契约、测试环境隔离
- `long_task_logging`：长任务日志输出规范（禁用模式、推荐模式、查看方式）
- `system_resource_monitoring`：系统资源过载容错（CPU/内存/磁盘检查、进程监控、容错策略）

对应复盘规范集：B1（PowerShell 长任务日志输出）、B2（系统资源过载容错）、C3（测试验证三档机制）、D1（测试覆盖契约）、D2（测试环境隔离）。

---

## 1. 设计动机：为什么需要三档机制

### 1.1 历史失败案例（真实引用）

| 案例 ID | 场景 | 根因 | 解决方案 | 教训 |
|---------|------|------|----------|------|
| HF-001 | 完整 pytest 测试集（`tiered_test_verification.tiers.tier_1.historical_full_test_count`，默认 1621 个测试）在 CPU 99% 过载环境下超时 | CPU 持续 99% 占用导致 pytest 调度饥饿，无输出超 10 分钟 | 改用直接 import 测试 5 个改动文件，5/5 通过 | 过载环境下完整测试集不可靠，必须降级到 Tier 2 |
| HF-002 | PowerShell `Tee-Object` 缓冲导致日志文件为空 | `Tee-Object` 是 sink cmdlet，必须等待所有输入才能输出，长任务下日志文件长时间为空 | 改用 `Start-Process -RedirectStandardOutput` 绕过缓冲 | 长任务日志输出禁用 sink cmdlet |

### 1.2 核心问题

1. **完整测试集在过载环境下不可靠**：CPU 持续高占用时 pytest 调度饥饿，无输出超 10 分钟，agent 无法判断是卡死还是正常运行
2. **sink cmdlet 缓冲陷阱**：`Select-Object -Last N` / `Tee-Object` / `More` 等 sink cmdlet 必须缓冲所有输入才能输出，长任务下日志文件长时间为空
3. **改动类型与验证档位不匹配**：新增功能却运行完整测试集浪费资源，重构类改动却只做 import 测试遗漏回归

### 1.3 解决方案

- **三档机制**：根据改动类型选择最低档位（D1 契约），根据系统资源降级（C3 规范）
- **长任务日志规范**：禁用 sink cmdlet，推荐 `Start-Process -RedirectStandardOutput`（B1 规范）
- **系统资源监控**：长任务前检查 CPU/内存/磁盘，过载时自动降级（B2 规范）

---

## 2. 三档定义（C3 规范）

### 2.1 Tier 1：完整测试集

| 项 | 配置路径 | 默认值 |
|----|----------|--------|
| 名称 | `tiered_test_verification.tiers.tier_1.name` | `完整测试集` |
| 描述 | `tiered_test_verification.tiers.tier_1.description` | `pytest tests/ + tsc --noEmit 全量验证` |
| pytest 命令 | `tiered_test_verification.tiers.tier_1.pytest_command` | `{python} -m pytest tests/ -v --timeout={timeout_seconds}` |
| tsc 命令 | `tiered_test_verification.tiers.tier_1.tsc_command` | `npx tsc --noEmit` |
| 最大执行时长 | `tiered_test_verification.tiers.tier_1.max_duration_sec` | `600`（秒） |
| 历史参考用例数 | `tiered_test_verification.tiers.tier_1.historical_full_test_count` | `1621` |
| 适用改动类型 | `tiered_test_verification.tiers.tier_1.applicable_change_types` | `refactor` |

**执行流程**：
1. 执行 `pytest_command`（带 `--timeout` 强制超时）
2. 执行 `tsc_command`（TypeScript 类型检查）
3. 两者均通过 → Tier 1 通过
4. 任一失败 → 记录失败详情，不自动降级（由人工判断是否需要修复后重跑）

### 2.2 Tier 2：直接 import 测试

| 项 | 配置路径 | 默认值 |
|----|----------|--------|
| 名称 | `tiered_test_verification.tiers.tier_2.name` | `直接 import 测试` |
| 描述 | `tiered_test_verification.tiers.tier_2.description` | `系统资源受限时，仅验证改动文件的核心功能` |
| import 测试模板 | `tiered_test_verification.tiers.tier_2.import_test_template` | `{python} -c "import ast; ast.parse(open(r'{changed_file}', encoding='utf-8').read()); print('OK: {changed_file}')"` |
| 改动文件来源 | `tiered_test_verification.tiers.tier_2.changed_files_source` | `git_diff` |
| 单文件超时 | `tiered_test_verification.tiers.tier_2.per_file_timeout_sec` | `10`（秒） |
| 适用改动类型 | `tiered_test_verification.tiers.tier_2.applicable_change_types` | `bugfix` |

**执行流程**：
1. 通过 `git diff` 获取改动文件列表
2. 对每个改动文件执行 `import_test_template`（替换 `{changed_file}` 占位符）
3. 单文件超时 `per_file_timeout_sec` 秒
4. 全部通过 → Tier 2 通过
5. 任一失败 → 触发级联降级到 Tier 3（`tiered_test_verification.downgrade_triggers.tier_2_failure`）

### 2.3 Tier 3：改动文件 5/5 验证

| 项 | 配置路径 | 默认值 |
|----|----------|--------|
| 名称 | `tiered_test_verification.tiers.tier_3.name` | `改动文件 5/5 验证` |
| 描述 | `tiered_test_verification.tiers.tier_3.description` | `最小验证，仅验证改动的文件能正确 import` |
| 最小验证文件数 | `tiered_test_verification.tiers.tier_3.min_files_to_verify` | `5` |
| 不足阈值时验证全部 | `tiered_test_verification.tiers.tier_3.verify_all_when_less_than_threshold` | `true` |
| 适用改动类型 | `tiered_test_verification.tiers.tier_3.applicable_change_types` | `feature` |

**执行流程**：
1. 通过 `git diff` 获取改动文件列表
2. 若文件数 < `min_files_to_verify` 且 `verify_all_when_less_than_threshold=true`，验证全部
3. 若文件数 ≥ `min_files_to_verify`，取前 `min_files_to_verify` 个文件验证
4. 对每个文件执行语法检查（`system_resource_monitoring.fault_tolerance.syntax_check_command`）
5. 全部通过 → Tier 3 通过

---

## 3. 降级触发条件（C3 规范）

### 3.1 降级触发器

| 触发器 | 配置路径 | 阈值 | 降级到 |
|--------|----------|------|--------|
| 高 CPU | `tiered_test_verification.downgrade_triggers.high_cpu` | CPU > `cpu_percent`（默认 90%）持续 `duration_sec`（默认 30 秒） | `tier_2` |
| 高 IO 延迟 | `tiered_test_verification.downgrade_triggers.high_io_latency` | 文件 IO 延迟 > `latency_sec`（默认 5 秒） | `tier_2` |
| Tier 2 失败 | `tiered_test_verification.downgrade_triggers.tier_2_failure` | Tier 2 任一文件 import 失败 | `tier_3` |

### 3.2 降级流程图

```
┌─ 选择初始档位（基于改动类型 D1 契约）──┐
│  refactor → Tier 1                      │
│  bugfix   → Tier 2                      │
│  feature  → Tier 3                      │
└─────────────────────────────────────────┘
                    ↓
┌─ 检查系统资源（D2 规范）──────────────┐
│  CPU > 90% 持续 30s?  → 降级到 Tier 2  │
│  IO 延迟 > 5s?        → 降级到 Tier 2  │
│  可用内存 < 512MB?    → 降级到 Tier 2  │
└─────────────────────────────────────────┘
                    ↓
┌─ 执行测试 ────────────────────────────┐
│  Tier 1 失败?  → 记录失败，人工判断    │
│  Tier 2 失败?  → 降级到 Tier 3        │
│  Tier 3 失败?  → 记录失败，必须修复    │
└─────────────────────────────────────────┘
```

---

## 4. 测试覆盖契约（D1 规范）

### 4.1 改动类型 → 最低档位映射

| 改动类型 | 最低档位 | 配置路径 |
|----------|----------|----------|
| `refactor`（重构） | Tier 1（完整测试集） | `tiered_test_verification.coverage_contract.change_type_to_min_tier.refactor` |
| `bugfix`（Bug 修复） | Tier 2（直接 import 测试） | `tiered_test_verification.coverage_contract.change_type_to_min_tier.bugfix` |
| `feature`（新增功能） | Tier 3（改动文件验证） | `tiered_test_verification.coverage_contract.change_type_to_min_tier.feature` |

### 4.2 强制升级条件

即使改动类型为 `feature`，触及以下关键文件时强制升级到 Tier 1（`tiered_test_verification.coverage_contract.force_upgrade_to`）：

| 关键文件 | 配置路径 | 升级原因 |
|----------|----------|----------|
| `src/xianyu_hunter/web/startup.py` | `tiered_test_verification.coverage_contract.force_upgrade_files` | 启动文件，影响全局初始化 |
| `src/xianyu_hunter/container.py` | `tiered_test_verification.coverage_contract.force_upgrade_files` | 依赖注入容器，影响所有模块 |
| `src/xianyu_hunter/core/scheduler.py` | `tiered_test_verification.coverage_contract.force_upgrade_files` | 核心调度器，影响任务执行 |

---

## 5. 长任务日志输出规范（B1 规范）

### 5.1 长任务判定

执行时长 > `long_task_logging.long_task_threshold_sec`（默认 30 秒）的命令视为长任务，必须遵守本规范。

适用工具列表（`long_task_logging.applicable_tools`）：
- `pytest`
- `sonar-scanner`
- `playwright test`
- `npm run build`
- `tsc --noEmit`

### 5.2 禁用模式（必须遵守）

以下 sink cmdlet 模式**禁止使用**（`long_task_logging.forbidden_patterns`）：

| 禁用模式 | 原因 |
|----------|------|
| `\| Select-Object -Last N` | `Select-Object` 是 sink cmdlet，必须缓冲所有输入才能输出最后 N 行 |
| `Tee-Object` | `Tee-Object` 是 sink cmdlet，必须缓冲所有输入才能输出（历史失败案例 HF-002） |
| `\| More` | `More` 是分页 sink cmdlet，必须缓冲所有输入 |

### 5.3 推荐模式

按优先级排序（`long_task_logging.recommended_patterns`）：

#### 5.3.1 Start-Process 重定向（首选）

```powershell
# {python}      ← .venv\Scripts\python.exe
# {args}        ← pytest 参数
# {output_file} ← 日志输出文件路径
# {error_file}  ← 错误输出文件路径
Start-Process -FilePath '{python}' -ArgumentList '{args}' -RedirectStandardOutput '{output_file}' -RedirectStandardError '{error_file}' -NoNewWindow -Wait
```

**为什么首选**：完全绕过 PowerShell 管道缓冲，子进程直接写文件。

#### 5.3.2 Out-File 重定向（次选）

```powershell
# {command}        ← 完整命令
# {output_file}    ← 日志输出文件路径
# {output_encoding}← 编码（utf8）
{command} 2>&1 | Out-File -FilePath '{output_file}' -Encoding {output_encoding}
```

**为什么次选**：流式写入（非 sink cmdlet），但仍有管道开销。

#### 5.3.3 直接重定向（备选）

```powershell
# {command}     ← 完整命令
# {output_file} ← 日志输出文件路径
{command} > '{output_file}' 2>&1
```

**为什么备选**：最简单，但无法控制编码（可能 CLIXML）。

### 5.4 日志查看方式

```powershell
# 查看最后 N 行（{n} ← 行数，{output_file} ← 文件路径）
Get-Content -Tail {n} '{output_file}'

# 实时跟踪（{output_file} ← 文件路径）
Get-Content -Wait '{output_file}'
```

**为什么用 `Get-Content` 而非 `cat`/`type`**：支持 `-Tail` 和 `-Wait` 实时跟踪。

---

## 6. 系统资源过载容错（B2 规范）

### 6.1 资源检查项

| 资源 | 阈值 | 配置路径 | 过载处理 |
|------|------|----------|----------|
| CPU | > `threshold_percent`（默认 90%）持续 `duration_sec`（默认 30 秒） | `system_resource_monitoring.checks.cpu` | `downgrade_to_tier_2` |
| 内存 | 可用 < `threshold_available_mb`（默认 512 MB） | `system_resource_monitoring.checks.memory` | `downgrade_to_tier_2` |
| 磁盘 IO | 延迟 > `threshold_latency_sec`（默认 5 秒） | `system_resource_monitoring.checks.disk_io` | `downgrade_to_tier_2` |

### 6.2 资源检查命令

所有检查命令为 PowerShell 语法，从配置读取，不硬编码：

```powershell
# CPU 检查（{check_command} ← system_resource_monitoring.checks.cpu.check_command）
Get-Counter '\Processor(_Total)\% Processor Time' -SampleInterval 1 -MaxSamples 3 | Select-Object -ExpandProperty CounterSamples | Select-Object -ExpandProperty CookedValue

# 内存检查（{check_command} ← system_resource_monitoring.checks.memory.check_command）
Get-Counter '\Memory\Available MBytes' -SampleInterval 1 -MaxSamples 1 | Select-Object -ExpandProperty CounterSamples | Select-Object -ExpandProperty CookedValue

# 磁盘 IO 检查（{check_command} ← system_resource_monitoring.checks.disk_io.check_command）
Get-Counter '\PhysicalDisk(_Total)\Avg. Disk sec/Transfer' -SampleInterval 1 -MaxSamples 1 | Select-Object -ExpandProperty CounterSamples | Select-Object -ExpandProperty CookedValue
```

### 6.3 进程监控

定位资源占用源头（`system_resource_monitoring.top_processes_command`）：

```powershell
# 查看 CPU 占用最高的 Top 10 进程
# {top_processes_count} ← system_resource_monitoring.top_processes_count（默认 10）
Get-Process | Sort-Object CPU -Descending | Select-Object -First {top_processes_count}
```

**为什么监控 Top 10 进程**：定位资源占用源头，必要时可建议用户关闭无关进程。

### 6.4 容错策略

| 容错场景 | 降级到 | 配置路径 |
|----------|--------|----------|
| 完整测试集超时 | `direct_import_test`（Tier 2） | `system_resource_monitoring.fault_tolerance.full_test_timeout_fallback` |
| 直接 import 测试失败 | `syntax_check_only`（语法检查） | `system_resource_monitoring.fault_tolerance.import_test_failure_fallback` |

语法检查命令模板（`system_resource_monitoring.fault_tolerance.syntax_check_command`）：

```powershell
# {python}       ← .venv\Scripts\python.exe
# {changed_file} ← 改动文件路径
{python} -c "import ast; ast.parse(open(r'{changed_file}', encoding='utf-8').read()); print('SYNTAX OK: {changed_file}')"
```

---

## 7. 测试环境隔离（D2 规范）

### 7.1 测试前检查清单

| 检查项 | 配置路径 | 说明 |
|--------|----------|------|
| 检查环境资源 | `tiered_test_verification.environment_isolation.pre_check_resources`（默认 true） | 测试前必须检查 CPU/内存/磁盘 |
| 长任务重定向 | `tiered_test_verification.environment_isolation.long_task_redirect_required`（默认 true） | 长任务必须重定向到日志文件 |
| 结果保存路径 | `tiered_test_verification.environment_isolation.result_save_path`（默认 `test-results/`） | 测试结果必须保存到指定路径 |

### 7.2 完整执行流程

1. **资源检查**：执行 `resource_check_commands` 中的 CPU/内存/磁盘检查命令
2. **档位选择**：根据改动类型（D1 契约）+ 系统资源（C3 降级）选择最终档位
3. **长任务重定向**：若预期执行时长 > `long_task_threshold_sec`，按 B1 规范重定向
4. **执行测试**：按所选档位执行测试
5. **结果保存**：将测试结果保存到 `result_save_path`
6. **降级处理**：若失败且符合降级条件，按 C3 规范降级到下一档

---

## 8. 适用场景与不适用场景

### 8.1 适用场景

- 所有涉及测试验证的模式（A~X）在执行前选择验证档位
- 长任务（pytest/sonar-scanner/playwright test）的日志输出
- 系统资源受限环境下的测试降级
- 重构/Bug 修复/新增功能后的测试覆盖选择

### 8.2 不适用场景

- 纯静态扫描类测试（如模式 F/G/H 的 grep 扫描）无需三档机制
- 执行时长 < `long_task_threshold_sec` 的短命令（直接输出即可）
- 已确定资源充足时的快速测试（可跳过资源检查）
- 非测试场景的命令执行（如 git 操作、文件读写）

---

## 9. 与其他模式的关系

### 9.1 与模式 E（大规模 pytest 测试执行）的关系

模式 E 专注于大规模 pytest 测试的失败分类与并行修复（TR1~TR6），三档机制专注于测试前的档位选择与资源容错。两者互补：

- **模式 E**：测试执行中（失败分类、并行修复、mock Request）
- **三档机制**：测试执行前（档位选择、资源检查、降级策略）

模式 E 在执行 pytest 前，应先按三档机制选择档位（Tier 1/2/3），若系统资源过载则降级。

### 9.2 与所有模式的集成

所有涉及测试验证的模式（C/D/E/F/G/H/I/J/K/L/M/O/P/Q/R/U/V/W/X）在执行测试前，应遵循三档机制选择验证档位。具体集成方式：

1. 模式触发后，先判断改动类型（refactor/bugfix/feature）
2. 按 D1 契约选择初始档位
3. 按 C3 降级触发条件调整档位
4. 执行测试时按 B1 规范输出日志
5. 测试结果按 D2 规范保存

---

## 10. 配置参数速查表

| 参数 | 路径 | 默认值 | 说明 |
|------|------|--------|------|
| 长任务阈值 | `long_task_logging.long_task_threshold_sec` | 30 | 超过此秒数视为长任务 |
| CPU 阈值 | `system_resource_monitoring.checks.cpu.threshold_percent` | 90 | CPU 使用率超过此值视为过载 |
| CPU 持续时间 | `system_resource_monitoring.checks.cpu.duration_sec` | 30 | CPU 持续超阈值此时长才判定过载 |
| 内存阈值 | `system_resource_monitoring.checks.memory.threshold_available_mb` | 512 | 可用内存低于此值视为过载 |
| IO 延迟阈值 | `system_resource_monitoring.checks.disk_io.threshold_latency_sec` | 5 | 磁盘 IO 延迟超过此值视为过载 |
| Top 进程数 | `system_resource_monitoring.top_processes_count` | 10 | 监控 CPU 占用最高的 N 个进程 |
| Tier 1 最大时长 | `tiered_test_verification.tiers.tier_1.max_duration_sec` | 600 | Tier 1 预期最大执行时长 |
| Tier 1 历史用例数 | `tiered_test_verification.tiers.tier_1.historical_full_test_count` | 1621 | 完整测试集历史参考用例数 |
| Tier 2 单文件超时 | `tiered_test_verification.tiers.tier_2.per_file_timeout_sec` | 10 | Tier 2 单文件 import 超时 |
| Tier 3 最小文件数 | `tiered_test_verification.tiers.tier_3.min_files_to_verify` | 5 | Tier 3 最小验证文件数 |
| 结果保存路径 | `tiered_test_verification.environment_isolation.result_save_path` | `test-results/` | 测试结果保存目录 |
