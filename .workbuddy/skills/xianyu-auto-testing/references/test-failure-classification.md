# 测试失败分类与执行规范

本文档描述大规模测试执行场景下的 6 项测试执行规范（TR1~TR6），覆盖超时配置、PowerShell 输出编码、失败分类并行修复、修复验证、mock Request 构造、monkeypatch 模块级绑定检测。

所有参数从 `config.yaml` 的 `test_execution` 段读取，**禁止在文档中硬编码超时秒数、文件名、错误签名、并行数量**。规范按错误类型/代码模式匹配，不绑定特定测试文件名。

适用场景：单次测试规模 ≥ 200 用例，或失败用例 ≥ 10 个时强制启用；小规模测试可参考执行。

## 1. TR1：测试超时配置与分批运行

### 1.1 规范

- `pyproject.toml` 必须配置 pytest 超时插件（`test_execution.plugin_required`，默认 `pytest-timeout`），默认超时 `test_execution.timeout_seconds`（30 秒）
- 大规模测试（用例数 > `test_execution.batch_threshold`，默认 200）必须按模块分组分批运行，避免单次运行无输出超 10 分钟难以判断是否卡死

### 1.2 执行方式

**单批运行（带超时）**：

```powershell
# {python} ← .venv\Scripts\python.exe
# {timeout} ← test_execution.timeout_seconds
{python} -m pytest tests/ --timeout={timeout} --tb=line -q
```

**分批运行（按模块分组）**：

```powershell
# 将 tests/ 下模块按 batch_threshold 拆分为多批，逐批执行
{python} -m pytest tests/test_module1.py tests/test_module2.py --timeout={timeout} --tb=line -q
{python} -m pytest tests/test_module3.py tests/test_module4.py --timeout={timeout} --tb=line -q
```

### 1.3 判断信号

| 信号 | 含义 | 处理 |
|------|------|------|
| 测试运行超过 10 分钟无输出 | 可能卡死或未启用超时 | 检查 `pyproject.toml` 是否配置 `pytest-timeout`，确认 `--timeout` 参数已传入 |
| `unrecognized arguments: --timeout` | 未安装 `pytest-timeout` 插件 | 执行 `{python} -m pip install pytest-timeout` |
| `FAILED tests/... - Timeout` | 单个用例超过超时阈值 | 标记为超时类失败，单独排查（通常是死锁/无限循环/网络等待） |

### 1.4 配置参数

| 参数 | 路径 | 默认值 |
|------|------|--------|
| 超时秒数 | `test_execution.timeout_seconds` | 30 |
| 分批阈值 | `test_execution.batch_threshold` | 200 |
| 必装插件 | `test_execution.plugin_required` | `pytest-timeout` |

## 2. TR2：PowerShell 测试输出编码规范

### 2.1 规范

PowerShell 环境下重定向测试输出时，**禁止使用 `>` 默认重定向**（会触发 CLIXML 序列化），必须用 `Out-File -Encoding utf8` 显式指定编码到 `test_execution.output_file`（默认 `test-results.txt`）。

### 2.2 执行方式

```powershell
# {python} ← .venv\Scripts\python.exe
# {output_file} ← test_execution.output_file
# {encoding} ← test_execution.output_encoding
{python} -m pytest tests/ --tb=line -q 2>&1 | Out-File -FilePath {output_file} -Encoding {encoding}
```

读取结果时用 `Read` 工具直接读取 `output_file`，避免在终端回显大量日志。

### 2.3 判断信号

| 信号 | 含义 | 处理 |
|------|------|------|
| 输出文件含 `<Objs Version="1.1.0.1" xmlns="...">` | CLIXML 格式污染 | 改用 `Out-File -Encoding utf8` 重定向，禁止 `>` 或默认管道 |
| 输出文件大小为 0 bytes | 重定向失败或编码不兼容 | 检查命令是否合并了 stderr（`2>&1`），确认 `Out-File` 参数正确 |
| 输出含 `?` 或乱码字符 | 编码不匹配 | 确认 `output_encoding` 为 `utf8`，且 `$OutputEncoding` 与之一致 |

### 2.4 配置参数

| 参数 | 路径 | 默认值 |
|------|------|--------|
| 输出编码 | `test_execution.output_encoding` | `utf8` |
| 输出文件名 | `test_execution.output_file` | `test-results.txt` |
| 避免 CLIXML | `test_execution.avoid_clixml` | `true` |

## 3. TR3：测试失败分类修复策略（核心）

### 3.1 规范

大规模测试失败（用例数 > `failure_classification.trigger_threshold`，默认 10）必须按错误类型聚类，分配子代理并行修复。每个错误类别对应一个子代理，子代理数量上限为 `failure_classification.parallel_agents`（默认 4）。

### 3.2 分类规则

错误签名匹配规则定义在 `failure_classification.rules`，每条规则包含：

| 字段 | 说明 |
|------|------|
| `signature` | 正则片段，匹配 pytest 失败堆栈首行（`Traceback` 之后的首个 `Error` 行） |
| `root_cause` | 根因类别标识符，用于子代理分配与报告聚合 |
| `description` | 中文描述，用于报告呈现 |

**默认分类规则**（来自 `config.yaml`）：

| 错误签名（正则） | 根因类别 | 描述 | 修复方向 |
|------------------|---------|------|---------|
| `TypeError: missing required argument\|missing 1 required positional argument` | `endpoint_signature_change` | 端点签名变更类 | 端点函数新增/删除了参数，测试需补齐 mock 参数（参见 TR5） |
| `TypeError: 'NoneType'/'bool' can't be awaited\|can't be used in 'await' expression` | `sync_async_mismatch` | 同步/异步不匹配类 | 端点从同步改为异步（或反之），测试需调整 `await` 用法或 Mock 返回值为 awaitable |
| `AttributeError: .* has no attribute` | `attribute_rename` | 属性名重构类 | 对象属性被重命名或删除，测试需更新 mock 对象属性或改用新属性名 |
| `AssertionError: assert .* == .*` | `business_logic` | 业务逻辑类 | 断言值不匹配，需核对预期值是否随业务规则变更而调整 |

### 3.3 并行修复流程

```
┌─────────────────────────────────────────────────────────┐
│ 1. 收集所有失败用例（pytest 输出文件）                     │
│ 2. 解析每个失败用例的错误签名（首行 Error）                │
│ 3. 按 failure_classification.rules 聚类                   │
│    - 命中规则的归入对应 root_cause 桶                     │
│    - 未命中的归入 "uncategorized" 桶（单独分配子代理）    │
│ 4. 每个桶分配 1 个子代理（上限 parallel_agents）           │
│    - 若桶数 > parallel_agents，合并较小的桶               │
│ 5. 并行调度子代理（Task 工具，独立上下文）                 │
│ 6. 子代理完成后进入 TR4 验证流程                          │
└─────────────────────────────────────────────────────────┘
```

### 3.4 子代理任务模板

每个子代理收到的任务上下文应包含：

- **根因类别**：`root_cause` 字段值
- **失败用例列表**：用例路径 + 错误堆栈摘要
- **修复方向**：本类别对应的修复策略（见 3.2 表格"修复方向"列）
- **验证要求**：修复后单独运行该模块测试（TR4）
- **配置约束**：所有路径/参数从 `config.yaml` 读取，禁止硬编码

### 3.5 判断信号

| 信号 | 含义 | 处理 |
|------|------|------|
| 失败用例 > `trigger_threshold` 但未触发并行 | 配置 `enabled: false` 或阈值过高 | 检查 `failure_classification.enabled` 与 `trigger_threshold` |
| 多个失败用例错误签名相同 | 同一根因类，应归入同一桶 | 确认聚类逻辑按 `signature` 正则匹配 |
| 子代理修复后引入新失败 | 修复未通过 TR4 单模块验证 | 要求子代理重跑该模块测试直至通过 |

### 3.6 配置参数

| 参数 | 路径 | 默认值 |
|------|------|--------|
| 是否启用 | `test_execution.failure_classification.enabled` | `true` |
| 并行子代理上限 | `test_execution.failure_classification.parallel_agents` | 4 |
| 触发阈值 | `test_execution.failure_classification.trigger_threshold` | 10 |
| 分类规则表 | `test_execution.failure_classification.rules` | 见 3.2 表格 |

## 4. TR4：测试修复验证策略

### 4.1 规范

每个子代理修复后必须**先单独运行该模块测试**验证（`verify_per_module`，默认 true）；所有子代理完成后必须**批量运行全部测试**验证（`verify_batch`，默认 true）。

### 4.2 执行方式

**单模块验证**（每个子代理修复后立即执行）：

```powershell
# {test_module} ← 子代理修复的测试模块路径
{python} -m pytest {test_module} --tb=short -q
```

**批量验证**（所有子代理完成后执行）：

```powershell
# 复用 TR2 的编码规范，输出到文件
{python} -m pytest tests/ --tb=line -q 2>&1 | Out-File -FilePath {output_file} -Encoding utf8
```

### 4.3 验证决策树

```
单模块验证失败？
├─ 是 → 子代理继续修复，不进入批量验证
└─ 否 → 标记该模块已通过，等待其他子代理
        ↓
所有模块通过？
├─ 是 → 执行批量验证
│       ├─ 批量验证通过 → 修复完成，输出报告
│       └─ 批量验证失败 → 收集新失败用例，回到 TR3 重新分类
└─ 否 → 等待
```

### 4.4 配置参数

| 参数 | 路径 | 默认值 |
|------|------|--------|
| 单模块验证 | `test_execution.verify_per_module` | `true` |
| 批量验证 | `test_execution.verify_batch` | `true` |

## 5. TR5：端点直接调用 mock Request 构造规范

### 5.1 规范

测试直接调用 FastAPI 端点函数（而非通过 `TestClient`）时，必须构造 mock `Request` 对象。默认使用 `types.SimpleNamespace` 构造轻量 mock，避免启动完整 ASGI 上下文。

### 5.2 构造方式

```python
from types import SimpleNamespace

# {user_id} ← test_execution.mock_request.default_user_id
request = SimpleNamespace(state=SimpleNamespace(user_id="{user_id}"))

# 调用端点
response = await endpoint_function(request, **kwargs)
```

如端点需要更多 `request` 属性（如 `headers`、`cookies`、`json`），按需扩展 SimpleNamespace 字段，但仍以 `state.user_id` 为最小必需字段。

### 5.3 判断信号

| 信号 | 含义 | 处理 |
|------|------|------|
| `TypeError: missing 1 required positional argument: 'request'` | 测试未传入 request 参数 | 用 SimpleNamespace 构造 mock request（参见 5.2） |
| `AttributeError: 'SimpleNamespace' object has no attribute 'headers'` | 端点访问了 mock 未提供的属性 | 扩展 SimpleNamespace 字段，补齐缺失属性 |
| 测试中出现 `Depends(...)` 解析失败 | 直接调用绕过了 FastAPI 依赖注入 | 改用 `TestClient` 或手动注入依赖值 |

### 5.4 配置参数

| 参数 | 路径 | 默认值 |
|------|------|--------|
| 默认 user_id | `test_execution.mock_request.default_user_id` | `default` |
| mock 模板 | `test_execution.mock_request.template` | `SimpleNamespace(state=SimpleNamespace(user_id="{user_id}"))` |

## 6. TR6：monkeypatch 模块级绑定检测

### 6.1 规范

测试 fixture 必须**检测并 patch 所有 `from X import Y` 的模块级引用**。`from X import Y` 执行后 `Y` 已绑定到当前模块命名空间，`monkeypatch.setattr(X, "Y", ...)` 只影响源模块 `X` 的 `Y`，被测代码读到的仍是导入时绑定的旧值。

### 6.2 检测方式

```powershell
# {config_module} ← 被 patch 的源模块路径（如 xianyu_hunter.config）
# {src_dir} ← project.backend_dir 或 frontend_dir
Select-String -Path "{src_dir}/**/*.py" -Pattern "from {config_module} import" -Encoding UTF8
```

或用 Grep 工具：

```
Pattern: "from {config_module} import"
Path: {src_dir}
glob: "*.py"
```

对每个命中模块，逐一 patch：

```python
# 假设源模块为 xianyu_hunter.config，被导入的符号为 SETTING_A
import target_module  # 命中 from xianyu_hunter.config import SETTING_A 的模块
monkeypatch.setattr(target_module, "SETTING_A", mock_value)
```

### 6.3 判断信号

| 信号 | 含义 | 处理 |
|------|------|------|
| 测试 monkeypatch 了源模块但被测代码读到的仍是环境变量真实值 | 模块级 `from X import Y` 绑定未 patch | 扫描所有命中模块，逐一 patch 模块级引用 |
| 测试本地通过但 CI 失败 | CI 环境变量与本地不同，patch 不彻底 | 启用 `auto_patch_all`，自动 patch 所有命中模块 |
| patch 后出现 `AttributeError: module 'X' has no attribute 'Y'` | 命中模块未实际导入该符号 | 检查 import 语句是否在 try/except 或条件分支内 |

### 6.4 配置参数

| 参数 | 路径 | 默认值 |
|------|------|--------|
| 扫描模式 | `test_execution.monkeypatch_scan.scan_pattern` | `from {config_module} import` |
| 自动 patch 所有命中模块 | `test_execution.monkeypatch_scan.auto_patch_all` | `true` |

## 7. 完整执行流程（大规模测试场景）

以下为大规模测试场景（如 1557 tests → 0 failed）的完整执行流程，串联 TR1~TR6：

```
┌─ 步骤 1：环境准备 ────────────────────────────────────────┐
│ 1. 确认 pyproject.toml 配置 pytest-timeout（TR1）          │
│ 2. 确认 .venv 可用，依赖已安装                              │
└──────────────────────────────────────────────────────────┘
                          ↓
┌─ 步骤 2：首轮全量运行（TR1+TR2）─────────────────────────┐
│ - 用例数 > batch_threshold → 分批运行                      │
│ - 输出重定向到 output_file（避免 CLIXML）                  │
│ - 命令：{python} -m pytest tests/ --timeout={timeout_seconds} --tb=line │
│         -q 2>&1 | Out-File -FilePath test-results.txt    │
│         -Encoding utf8                                    │
└──────────────────────────────────────────────────────────┘
                          ↓
┌─ 步骤 3：失败分类（TR3）─────────────────────────────────┐
│ - 失败用例 ≤ trigger_threshold → 串行修复                  │
│ - 失败用例 > trigger_threshold → 按错误签名聚类            │
│ - 每个根因类别分配 1 个子代理（上限 parallel_agents）      │
└──────────────────────────────────────────────────────────┘
                          ↓
┌─ 步骤 4：并行修复（TR3+TR5+TR6）─────────────────────────┐
│ 子代理按根因类别执行：                                     │
│ - endpoint_signature_change → 补齐 mock request（TR5）    │
│ - sync_async_mismatch → 调整 await/Mock 返回值            │
│ - attribute_rename → 更新 mock 属性名                     │
│ - business_logic → 核对预期值                             │
│ 修复时注意 monkeypatch 模块级绑定（TR6）                  │
└──────────────────────────────────────────────────────────┘
                          ↓
┌─ 步骤 5：单模块验证（TR4）───────────────────────────────┐
│ - 每个子代理修复后单独运行该模块测试                       │
│ - 失败则继续修复，不进入批量验证                           │
└──────────────────────────────────────────────────────────┘
                          ↓
┌─ 步骤 6：批量验证（TR4）─────────────────────────────────┐
│ - 所有模块通过后，批量运行全部测试                         │
│ - 复用 TR2 编码规范输出到文件                             │
│ - 失败 → 回到步骤 3 重新分类                              │
│ - 通过 → 进入报告生成（见 test-report.md）                │
└──────────────────────────────────────────────────────────┘
```

## 8. 注意事项

1. **规范泛化**：所有规则按错误类型/代码模式匹配，不绑定特定测试文件名。新增错误类别只需在 `failure_classification.rules` 追加条目，不改本文档流程。
2. **配置优先**：所有阈值、文件名、签名正则从 `config.yaml` 读取，禁止在流程中硬编码。
3. **并行安全**：子代理之间无共享状态，每个子代理独立修复独立模块，避免文件冲突。
4. **回归保护**：批量验证失败时回到 TR3 重新分类，避免修复引入新问题被掩盖。
5. **PowerShell 适配**：所有命令示例为 PowerShell 语法，`2>&1` 合并 stderr 后必须用 `Out-File -Encoding utf8` 重定向。

---

## 安全测试协议（safe-delete 沙箱）与回归守护

> 对应 config.yaml#sandbox_test_protocol (#124) + config.yaml#regression_guard (#125)；复盘 retrospective-2026-08-13-login-cookie.md。

### TR7：safe-delete 沙箱测试协议
- **现象**：pytest 带 coverage 时清 `.coverage.*` 被 safe-delete 钩子 fail-closed 拦截 → INTERNALERROR；收尾清理 C:\pyfix_tmp\*garbage* 也被拦截 → 偶发 exit1 无 summary。
- **协议**：用项目 venv 的 pytest（sandbox_test_protocol.venv_pytest，本仓 .venv/Scripts/pytest.exe），加 sandbox_test_protocol.pytest_args（--no-cov -p no:cacheprovider）。
- **判定**：以「无 FAILED/AssertionError」为准；exit1 无 summary 视为环境崩溃，非回归。
- **flake 处理**：易 flaky 测试跑 sandbox_test_protocol.flaky_min_runs（默认 2）次，隔离单测确认。

### TR8：回归守护（基线红灯 / 修复绿灯）
- 每条修复必须配回归测试，且测试在 pre-fix 代码必须失败。
- 验证手法（regression_guard.verify_method）：git checkout -- <改动文件> 取基线 → 跑测试应红灯 → 还原修复 → 应绿灯，证明测试真正守卫修复。
- 单跑一次的 F 不足以判回归；必须与 baseline 交叉验证排除环境崩溃。
