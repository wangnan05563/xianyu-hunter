# 重构安全性审查（Refactoring Safety Checks）

> **配套技能**：[xianyu-backend-code-review](../SKILL.md)
> **用途**：对配置化重构、长任务执行、质量门禁、跨文件契约四类高风险场景进行防御性审查。本文件是 v4.61.0 新增检查点 B-REVIEW-281~290 的细化展开，所有阈值与路径通过 `config.yaml#refactoring_safety` 节点管理，技能本身不含硬编码值。
> **维护原则**：新增历史失败案例时追加到对应检查点的「历史失败案例」段，并在 `version-changelog.md` 记录版本与触发来源。

---

## 设计理念

本文件的四类审查要点均来自真实复盘案例，核心目标是 **"防止低级重构失误占用大量调试时间"**：

1. **A 类（配置化重构）**：常量改函数、模块级函数误用 `self` 等失误导致 `NameError` / `ImportError`，服务启动直接失败。
2. **B 类（长任务执行）**：PowerShell 用 `| Select-Object -Last` 缓冲整流导致内存爆涨，或完整测试集超时无降级路径。
3. **C 类（质量门禁）**：SonarQube 扫描流程缺弹性恢复，单点故障导致整条质量门禁链路阻塞。
4. **D 类（跨文件契约）**：跨文件引用同步缺失导致重构后下游 ImportError，配置硬编码常量绕过统一入口。

每条检查点均提供「为什么这么做」「适用场景」「不适用场景」，避免误报与形式化合规。

---

## A. 配置化重构规范

### B-REVIEW-281 CONFIG-REFACTOR-5STEP 配置化重构 5 步法

**为什么这么做**：历史上将模块级常量（如 `TAKEOVER_TIMEOUT_MIN`）重构为 `config.yaml` 配置项时，多次因遗漏某个引用点同步更新，导致 `NameError` 或 `ImportError` 在运行时才暴露。5 步法把"grep 引用点 → 配置层声明 → YAML 增项 → 源文件改函数 → 强制核对"固化为不可跳过的工作流，每步都有可验证的产物。

**配置节点**：`refactoring_safety.refactor_5step`

**5 步法**：

1. **grep 所有引用点**：`grep -rn "<OLD_CONSTANT>" --include="*.py"`，把结果列表固化为本次重构的核对清单。
2. **在 Config 类中新增字段**：继承 `pydantic.BaseModel` 的 Config 类新增字段，必须带默认值与 docstring（默认值用于异常回退）。
3. **在 `config.yaml` 新增配置块**：带注释说明字段语义、单位、取值范围。
4. **源文件改为 `_get_xxx()` 函数**：函数内通过 `get_config()` 读取，必须含异常回退到默认值的逻辑（`try/except (KeyError, AttributeError)` 或 `getattr` 链）。
5. **强制核对**：对照步骤 1 列出的每个引用点逐项核对，包括 import 语句、文档字符串、注释中出现的旧名。

**检查方法**：
- 看 `git diff` 中是否有"常量 → 函数"的变更（如 `_TAKEOVER_TIMEOUT_MIN = 60` 改为 `def _get_takeover_timeout_min() -> int`）。
- 触发后必须 `grep` 旧名，逐项确认每个引用点已更新为 `_get_xxx()` 调用（带 `()`）。
- 函数内必须包含异常回退逻辑，否则记 P1。

**适用场景**：模块级硬编码常量（TTL/超时/阈值/间隔/重试次数等）改为 `config.yaml` 配置项；类常量改为实例属性。

**不适用场景**：
- 纯内部辅助常量（如 `_IDENT_RE = re.compile(...)` 正则白名单），无业务参数语义。
- 测试用 fixture 常量（测试代码不进入生产配置）。
- 框架装饰器参数（如 `@router.get("/path")`），路径本身是声明性的。

**历史失败案例**：
- `container.py:450` `self.config.buyer` 应为 `cfg.buyer`：模块级函数内误用 `self.config.buyer`，模块级函数没有 `self`，触发 `NameError: name 'self' is not defined`。根因是 5 步法的步骤 5 未严格执行，只改了源文件未核对调用点作用域。
- `startup.py:161` `from xxx import TAKEOVER_TIMEOUT_MIN` 应为 `from xxx import _get_takeover_timeout_min`：常量改名后调用方未同步更新 import，触发 `ImportError: cannot import name 'TAKEOVER_TIMEOUT_MIN'`。根因是步骤 1 grep 出的引用点未逐项核对 import 语句。

---

### B-REVIEW-282 SCOPE-CONTRACT-CHECK 作用域契约校验

**为什么这么做**：模块级函数误用 `self`、静态方法误用 `cls` 等"作用域违约"在静态分析阶段不易被发现，运行时才暴露为 `NameError`。作用域契约把函数签名（是否含 `self`/`cls`）与允许访问的变量绑定，作为可静态校验的契约。

**配置节点**：`refactoring_safety.scope_contract`

**契约规则**：

| 函数类型 | 函数签名特征 | 允许访问 | 禁止访问 |
|----------|--------------|----------|----------|
| 模块级函数 | 无 `self`/`cls` 参数 | 局部变量、`get_config()` 返回值、模块级常量 | `self.xxx`、`cls.xxx` |
| 实例方法 | 第一个参数 `self` | `self.xxx`、实例属性、局部变量 | `cls.xxx`（除 `@classmethod`） |
| 类方法 `@classmethod` | 第一个参数 `cls` | `cls.xxx`、类属性、局部变量 | `self.xxx` |
| 静态方法 `@staticmethod` | 无 `self`/`cls` 参数 | 局部变量、模块级常量、`get_config()` | `self.xxx`、`cls.xxx` |

**检查方法**：
- 对每个函数，先用 AST 或正则提取函数签名首参。
- 检查函数体内是否出现与签名不匹配的访问模式（如模块级函数体内出现 `self.`、静态方法体内出现 `cls.`）。
- 与 B-REVIEW-281 的 5 步法步骤 5 配套：常量改函数后，原调用方如果是 `self.config.xxx` 模式必须改为 `cfg.xxx`（`cfg = get_config()`）。

**适用场景**：
- 配置化重构后核对调用点作用域（与 B-REVIEW-281 配套）。
- 类方法/静态方法新增时校验作用域一致性。
- Mixin 类方法调用基类方法时校验 `self` 是否传递。

**不适用场景**：
- `__init__` / `__post_init__` 等构造方法（默认 `self` 可用）。
- `@property` 装饰的方法（默认 `self` 可用）。
- 测试代码中的 mock 函数（作用域由 mock 框架接管）。

**历史失败案例**：见 B-REVIEW-281 的 `container.py:450` 案例，模块级函数误用 `self.config.buyer` 即为典型作用域违约。

---

### B-REVIEW-283 IMPORT-NAME-CHECKLIST 导入名称变更 checklist

**为什么这么做**：导出符号改名（常量改函数、函数改类、名字变更）后，下游 `from xxx import OLD_NAME` 会触发 `ImportError`，且这种错误只在导入时才暴露，单元测试可能因测试模块未引用而漏掉。checklist 把"删除/改名前的 grep"固化为强制步骤。

**配置节点**：`refactoring_safety.import_name_change`

**checklist**：

1. **删除导出名前**：必须执行 `grep -rn "from <module> import <name>"` 并逐项处理每个引用点。
2. **常量改名为函数前**：所有调用方必须加 `()` 调用（如 `TAKEOVER_TIMEOUT_MIN` → `_get_takeover_timeout_min()`）。
3. **常量改名为类前**：所有调用方必须实例化或改属性访问（如 `CONFIG` 常量 → `AppConfig()` 实例）。
4. **改名后启动验证**：执行 `python -c "from xianyu_hunter import <affected_modules>"` 验证导入链无断裂。
5. **测试同步**：测试中 `from xxx import OLD_NAME` 必须同步更新，且测试需实际运行（不只是 `py_compile`）。

**检查方法**：
- 检查 `git diff` 是否含 `__all__` 或导出符号的删除/改名。
- 触发后必须 grep 旧名，确认无残留引用。
- 改名为函数时，grep 旧名的调用点是否都加了 `()`。

**适用场景**：
- 模块 `__all__` 列表变更。
- 公共 API 重命名（函数/类/常量）。
- 常量改为函数或类（语义升级）。

**不适用场景**：
- 私有辅助函数改名（前缀 `_`，仅模块内使用）。
- 测试内部 mock 函数改名。
- 自动生成代码（如 `# @generated` 标记的文件）。

**历史失败案例**：`startup.py:161` `from xxx import TAKEOVER_TIMEOUT_MIN` 触发 `ImportError`，根因是 checklist 步骤 1 未执行，调用方 import 未同步更新。

---

## B. 长任务执行规范

### B-REVIEW-284 POWERSHELL-LONG-TASK-OUTPUT PowerShell 长任务日志输出

**为什么这么做**：PowerShell 中 `| Select-Object -Last N` 是 sink cmdlet，必须把上游所有输出缓冲到内存后才能取最后 N 行，长任务（如 pytest 全量、sonar-scanner、uvicorn 启动日志）输出几十 MB 时会导致 PowerShell 进程内存爆涨甚至 OOM。直接重定向到文件则由 OS 流式写入磁盘，内存占用恒定。

**配置节点**：`refactoring_safety.long_task_output`

**规则**：

| 命令类型 | 禁用 | 推荐 |
|----------|------|------|
| 输出重定向 | `\| Select-Object -Last N`、`\| Select -Last N`、`\| more` | `> <file>`、`Start-Process -RedirectStandardOutput <file>` |
| 查看日志 | `\| Select-Object -Last N` 重新执行命令 | `Get-Content -Tail N <file>`、`Get-Content -Wait <file>`（实时跟踪） |

**判定阈值**：执行时长 > `long_task_threshold_sec`（默认 30 秒，由 `config.yaml` 管理）的命令视为长任务，必须用文件重定向。

**检查方法**：
- 检查 `scripts/` 目录下的 `.ps1` 文件，grep 是否含 `| Select-Object -Last` 或 `| Select -Last` 模式。
- 检查 `RunCommand` 工具调用历史，长任务命令是否用了 sink cmdlet。
- 触发后建议改为 `> <file>` + `Get-Content -Tail N <file>` 模式。

**适用场景**：
- 执行时长 > 30 秒的命令（pytest 全量、sonar-scanner、uvicorn 启动、`pip install` 大型包）。
- CI 流水线脚本中的日志收集。
- 长时间运行的子进程输出捕获。

**不适用场景**：
- 短命令（< 30 秒）的即时输出查看。
- 一次性交互式命令（如 `git log -n 5`）。
- Linux/macOS 下的 `tail -f` / `tail -n`（POSIX 工具无 sink 问题）。

---

### B-REVIEW-285 RESOURCE-OVERLOAD-TOLERANCE 系统资源过载容错

**为什么这么做**：完整 pytest 测试集在低配机器或并发场景下可能超时（>5 分钟），强行重试会加剧资源过载，形成"超时→重试→更超时"的恶性循环。容错策略要求长任务前预检资源，超时时降级为直接 import 测试或仅验证改动文件，避免阻塞审查流程。

**配置节点**：`refactoring_safety.resource_overload_tolerance`

**规则**：

1. **长任务前预检**：执行完整 pytest 前用 `Get-Process | Sort CPU -Desc | Select -First 10` 检查 CPU 占用最高的进程，若系统进程总 CPU > `cpu_threshold_pct`（默认 90%）则触发降级。
2. **超时降级**：完整 pytest 超时（> `full_test_timeout_sec`，默认 300 秒）时降级为：
   - **Tier 2**：直接 `python -c "from xianyu_hunter.xxx import yyy"` 验证改动文件的导入链。
   - **Tier 3**：仅 `py_compile` 改动文件，验证语法。
3. **内存监控**：长任务执行中若 Python 进程内存 > `memory_threshold_pct`（默认 85%），提前终止并降级。

**检查方法**：
- 检查审查流程是否在执行完整测试前有资源预检步骤。
- 检查超时降级路径是否在脚本中显式定义（不能依赖人工干预）。
- 检查降级后的验证是否覆盖核心改动文件。

**适用场景**：
- 完整 pytest 测试集执行（>100 个测试用例）。
- CI 流水线在低配机器上运行。
- 多个长任务并发的场景。

**不适用场景**：
- 小型测试集（<50 个测试用例，预计 < 30 秒完成）。
- 本地开发机配置充足且无并发负载。
- 仅验证单个文件的语法（直接 `py_compile` 即可）。

---

## C. 质量门禁规范

### B-REVIEW-286 SONARQUBE-PIPELINE-CLOSED-LOOP SonarQube 15 阶段闭环

**为什么这么做**：SonarQube 扫描流程涉及服务器检测、ES 预检、环境兼容、MCP 检测、模块定位、质量门、扫描、CE 轮询、修复、NOSONAR 校验、验证、报告等 15 个阶段，任一阶段失败都会阻塞整条链路。闭环规范把每个阶段的输入/输出/失败处理固化为可检查的契约，避免"扫描卡在某阶段但无人发现"。

**配置节点**：`refactoring_safety.sonarqube_pipeline`

**15 阶段契约**（精简为关键 12 阶段，完整列表在 `config.yaml` 管理）：

| 阶段 | 输入 | 输出 | 失败处理 |
|------|------|------|----------|
| 1. 服务器检测 | SonarQube URL | 服务器可达性 | 不可达则跳过扫描，标记 skipped |
| 2. ES 预检 | ES endpoint | `read_only_allow_delete` 状态 | 锁定则自动解锁（B-REVIEW-287） |
| 3. 环境兼容 | sonar-scanner 版本 | 版本兼容性 | 不兼容则提示升级 |
| 4. MCP 检测 | MCP server 配置 | MCP 可用性 | 不可用则降级为 CLI |
| 5. 模块定位 | 项目结构 | 待扫描模块列表 | 无模块则跳过 |
| 6. 质量门 | Quality Gate 配置 | 门禁状态 | 门禁失败则进入修复阶段 |
| 7. 扫描 | sonar-scanner 命令 | 扫描任务 ID | 扫描失败则记录错误 |
| 8. CE 轮询 | 任务 ID | CE 报告状态 | 轮询超时则降级 |
| 9. 修复 | Issue 列表 | 修复补丁 | 修复失败则标记 |
| 10. NOSONAR 校验 | NOSONAR 标记 | 位置校验 | 位置错误则告警 |
| 11. 验证 | 修复后代码 | 验证结果 | 验证失败则回滚 |
| 12. 报告 | 全流程数据 | 审查报告 | 报告生成失败则记录 |

**检查方法**：
- 检查 SonarQube 扫描脚本是否覆盖所有 12 个关键阶段。
- 每个阶段是否有明确的失败处理逻辑（不能 `exit 1` 终止整条链路）。
- 阶段间是否有状态传递（如任务 ID 从扫描阶段传到 CE 轮询阶段）。

**适用场景**：
- 项目级 SonarQube 全量扫描。
- CI 流水线中的质量门禁检查。
- 代码质量周报/月报的自动化扫描。

**不适用场景**：
- 单文件快速 lint（用 ruff/flake8 即可）。
- 本地开发机的临时扫描（无 SonarQube 服务器）。
- 仅查看 issue 不执行修复的只读扫描。

---

### B-REVIEW-287 RESILIENCE-RECOVERY 弹性恢复机制

**为什么这么做**：SonarQube 扫描链路中多个环节可能因环境问题失败（ES read-only 锁、CE 报告轮询超时、NOSONAR 位置漂移、TRAE 沙箱限制、项目锁残留），如果没有弹性恢复机制，单点故障就会阻塞整条质量门禁。弹性恢复要求每个故障点都有自愈逻辑或旁路策略。

**配置节点**：`refactoring_safety.resilience_recovery`

**5 类弹性恢复机制**：

1. **ES read-only 锁自愈**：扫描前检测 `cluster.blocks.read_only_allow_delete`，若为 `true` 则 `PUT /_cluster/settings` 解锁。
2. **CE 报告轮询**：扫描完成后轮询 CE 任务状态（`/api/ce/task?id=<task_id>`），超时则降级为只读模式（不阻塞报告生成）。
3. **NOSONAR 位置校验**：`// NOSONAR` 标记必须与 issue 行号匹配，位置漂移时记录告警但不阻塞。
4. **TRAE 沙箱旁路**：TRAE 沙箱限制文件写入时，扫描结果输出到临时目录再复制到目标路径。
5. **项目锁清理**：扫描前检查 `sonar-project.lock`，若存在且无活动进程则删除。

**检查方法**：
- 检查扫描脚本是否含 ES read-only 检测与解锁逻辑。
- 检查 CE 轮询是否有超时降级（不能无限轮询）。
- 检查 NOSONAR 标记是否做了位置校验（避免误标记其他行）。
- 检查 TRAE 沙箱旁路路径是否在脚本中定义。
- 检查项目锁清理是否在扫描前执行。

**适用场景**：
- 自动化 SonarQube 扫描流水线。
- CI 环境中资源受限的场景。
- 多项目并发扫描（可能产生项目锁冲突）。

**不适用场景**：
- 手动单次扫描（人工可处理故障）。
- 不依赖 ES 的扫描（如本地 sonar-scanner + 文件输出）。
- TRAE 沙箱外的开发环境。

---

### B-REVIEW-288 TEST-VERIFY-TIERS 测试验证三档

**为什么这么做**：审查流程中的"验证"环节如果只设一档（完整测试集），低配机器或大型项目会因超时而阻塞，反而拖慢审查速度。三档策略根据资源与改动范围选择合适的验证粒度，平衡覆盖度与执行速度。

**配置节点**：`refactoring_safety.test_verify_tiers`

**三档策略**：

| 档位 | 触发条件 | 执行内容 | 适用场景 |
|------|----------|----------|----------|
| Tier 1 完整测试集 | 改动文件数 ≤ `tier1_full_test.max_files`（默认 200）且资源充足 | `pytest tests/ -x --timeout=300` | 全量审查、发布前验证 |
| Tier 2 直接 import 测试 | 改动文件数 ≤ `tier2_direct_import.max_files`（默认 50）或 Tier 1 超时 | `python -c "from xianyu_hunter.xxx import yyy"` | 增量审查、配置化重构后验证 |
| Tier 3 改动文件验证 | 单文件改动或 Tier 2 失败 | `py_compile <changed_file>` + 语法检查 | 片段评审、快速自检 |

**检查方法**：
- 检查审查流程的验证阶段是否显式选择档位（不能默认 Tier 1）。
- 检查档位选择逻辑是否基于改动文件数与资源状态。
- 检查 Tier 1 超时后是否自动降级到 Tier 2（不能直接报错退出）。

**适用场景**：
- 审查流程的验证阶段（与 SKILL.md 阶段 4 配套）。
- 配置化重构后的快速验证。
- CI 流水线中根据 PR 改动范围选择测试粒度。

**不适用场景**：
- 发布前最终验证（必须 Tier 1）。
- 安全相关改动（必须 Tier 1 + 专项安全测试）。
- 数据库迁移改动（必须 Tier 1 + 迁移测试）。

---

## D. 跨文件契约规范

### B-REVIEW-289 CROSS-FILE-REFERENCE-SYNC 跨文件引用同步校验

**为什么这么做**：跨文件引用（`from xxx import yyy`）的同步问题在静态分析阶段不易发现，运行时才暴露为 `ImportError` 或 `NameError`。重构后必须启动服务或运行测试验证，捕获这两类异常。本检查点与 B-REVIEW-283 配套：283 关注改名前的 grep，289 关注改名后的运行时验证。

**配置节点**：`refactoring_safety.cross_file_sync`

**规则**：

1. **修改导出符号前**：必须 `grep -rn "from <module> import <name>"` 列出所有引用点（与 B-REVIEW-283 步骤 1 一致）。
2. **重构后必须验证**：
   - 启动服务：`python -m xianyu_hunter.web.startup` 或等价命令，捕获 `ImportError`。
   - 运行测试：`pytest tests/ -x --timeout=60`，捕获 `NameError` 与 `ImportError`。
3. **异常捕获清单**：`catch_exceptions: [ImportError, NameError]`，这两类异常是跨文件契约破裂的直接信号。

**检查方法**：
- 检查 `git diff` 是否含 `__all__` 或公共函数/类/常量的删除/改名。
- 触发后必须确认有运行时验证步骤（启动服务或运行测试）。
- 验证失败时必须修复所有引用点，不能仅修复报错的那个。

**适用场景**：
- 公共 API 重命名（函数/类/常量）。
- 模块 `__all__` 列表变更。
- 跨模块依赖重构（如把 `cookie_helper` 从 `core` 移到 `infra`）。
- 配置化重构（与 B-REVIEW-281 配套）。

**不适用场景**：
- 私有辅助函数改名（前缀 `_`）。
- 测试内部 mock 函数改名。
- 自动生成代码（`# @generated` 标记）。
- 单文件内部的重构（无跨文件引用）。

**历史失败案例**：`startup.py:161` `from xxx import TAKEOVER_TIMEOUT_MIN` 触发 `ImportError`，根因是重构后未执行运行时验证，仅靠 `py_compile` 无法发现 import 链断裂。

---

### B-REVIEW-290 CONFIG-ACCESS-UNIFIED-ENTRY 配置访问统一入口

**为什么这么做**：业务参数（TTL/超时/阈值/间隔）如果散落在模块级硬编码常量中，会导致两个问题：(1) 调整参数需要改代码而非配置；(2) 同一参数在不同模块有不同硬编码值，产生不一致。统一入口要求所有业务参数从 `config.yaml` 读取，且读取函数必须有异常回退到默认值，避免配置缺失时服务崩溃。

**配置节点**：`refactoring_safety.config_access_unified`

**规则**：

1. **业务参数必须从 `config.yaml` 读取**：TTL、超时、阈值、间隔、重试次数、批次大小等业务参数必须通过 `get_config()` 读取，禁止模块级硬编码常量。
2. **禁止模块级硬编码常量**：如 `_LIVE_CACHE_TTL = 60` 是违规模式，必须重构为 `CacheConfig.live_search_ttl`。
3. **配置读取函数必须有异常回退**：`_get_xxx()` 函数内必须 `try/except` 捕获配置缺失，回退到默认值（默认值在 Config 类字段声明中定义）。
4. **配置访问统一入口**：业务代码通过 `get_config()` 获取 Config 实例，禁止直接读 YAML 文件或绕过 Config 类。

**检查方法**：
- grep 模块级常量定义模式 `^[A-Z_]+ = \d+$`，识别疑似硬编码业务参数。
- 检查 `_get_xxx()` 函数是否含 `try/except` 异常回退逻辑。
- 检查业务代码是否通过 `get_config()` 访问配置（而非 `yaml.safe_load` 直接读文件）。

**适用场景**：
- 所有业务参数（TTL/超时/阈值/间隔/重试次数/批次大小）。
- 配置化重构后的核对（与 B-REVIEW-281 配套）。
- 多环境部署（dev/staging/prod 配置不同）。

**不适用场景**：
- 纯技术性常量（如 `_IDENT_RE = re.compile(...)` 正则白名单）。
- 框架装饰器参数（如 `@router.get("/path")` 的路径）。
- 测试用常量（测试代码不进入生产配置）。
- 数学常量（如 `PI = 3.14159`）。

**历史失败案例**：
- `_LIVE_CACHE_TTL = 60` 硬编码在模块级，调整缓存 TTL 需要改代码且不同模块有不同值。重构为 `CacheConfig.live_search_ttl` 后，统一从 `config.yaml` 读取，默认值 60 保留在 Config 类字段声明中。
- `container.py:450` `self.config.buyer` 在模块级函数中误用 `self`，根因是配置访问未走统一入口 `get_config()`，而是依赖类实例属性。

---

## 与现有检查点的关系

| 本文件检查点 | 关联现有检查点 | 关系说明 |
|--------------|----------------|----------|
| B-REVIEW-281 配置化重构 5 步法 | B-REVIEW-NO-HARDCODED-THRESHOLD / B-REVIEW-CONFIG-LINKAGE | 281 关注重构流程（5 步法），NO-HARDCODED-THRESHOLD 关注阈值硬编码本身，CONFIG-LINKAGE 关注配置全链路生效。三者互补：281 是流程，后两者是结果。 |
| B-REVIEW-282 作用域契约校验 | B-REVIEW-SHARED-SINGLETON-POLLUTION | 282 关注函数签名与作用域匹配，SHARED-SINGLETON 关注单例污染。282 是静态契约，SHARED-SINGLETON 是运行时行为。 |
| B-REVIEW-283 导入名称变更 checklist | B-REVIEW-PYTEST-MODULE-REIMPORT | 283 关注改名前的 grep，PYTEST-MODULE-REIMPORT 关注测试模块重复 import 隔离。 |
| B-REVIEW-284 PowerShell 长任务日志输出 | B-REVIEW-WINDOWS-TERMINAL-ENCODING / B-REVIEW-POWERSHELL-EXPLICIT-SUFFIX | 284 关注 sink cmdlet 内存问题，WINDOWS-TERMINAL-ENCODING 关注编码，POWERSHELL-EXPLICIT-SUFFIX 关注后缀显式声明。三者均针对 PowerShell 但维度不同。 |
| B-REVIEW-286 SonarQube 15 阶段闭环 | B-REVIEW-234 ES-RESILIENCE-PRECHECK | 286 关注全流程闭环，ES-RESILIENCE-PRECHECK 是 286 阶段 2（ES 预检）的细化。 |
| B-REVIEW-288 测试验证三档 | B-REVIEW-235 PYTEST-TIMEOUT-CONFIG | 288 关注档位选择策略，PYTEST-TIMEOUT-CONFIG 关注单次测试超时配置。288 是流程级，235 是配置级。 |
| B-REVIEW-289 跨文件引用同步校验 | B-REVIEW-PARAM-PASS-THROUGH | 289 关注导出符号改名的跨文件影响，PARAM-PASS-THROUGH 关注方法签名新增参数的调用点同步。两者均为"调用方同步"但粒度不同。 |
| B-REVIEW-290 配置访问统一入口 | B-REVIEW-NO-HARDCODED-THRESHOLD / B-REVIEW-CONFIG-DRIVEN-TOGGLE | 290 关注配置访问入口统一，NO-HARDCODED-THRESHOLD 关注阈值，CONFIG-DRIVEN-TOGGLE 关注功能开关。290 是访问层规范，后两者是应用层规范。 |

---

## 配置节点速查

所有阈值与路径通过 `config.yaml#refactoring_safety` 节点管理，禁止在 SKILL.md 或本文件中硬编码数值：

| 配置项 | 默认值 | 用途 |
|--------|--------|------|
| `refactoring_safety.refactor_5step.enabled` | `true` | 启用 5 步法检查 |
| `refactoring_safety.scope_contract.module_function_allowed` | `[local_var, get_config]` | 模块级函数允许访问的变量类型 |
| `refactoring_safety.long_task_output.long_task_threshold_sec` | `30` | 长任务判定阈值（秒） |
| `refactoring_safety.resource_overload_tolerance.cpu_threshold_pct` | `90` | CPU 占用阈值（%） |
| `refactoring_safety.resource_overload_tolerance.memory_threshold_pct` | `85` | 内存占用阈值（%） |
| `refactoring_safety.resource_overload_tolerance.full_test_timeout_sec` | `300` | 完整测试集超时阈值（秒） |
| `refactoring_safety.sonarqube_pipeline.required_stages` | 12 项 | SonarQube 闭环必需阶段 |
| `refactoring_safety.test_verify_tiers.tier1_full_test.max_files` | `200` | Tier 1 触发的最大文件数 |
| `refactoring_safety.test_verify_tiers.tier2_direct_import.max_files` | `50` | Tier 2 触发的最大文件数 |
| `refactoring_safety.cross_file_sync.catch_exceptions` | `[ImportError, NameError]` | 跨文件契约破裂的异常清单 |
| `refactoring_safety.config_access_unified.business_params_from_yaml` | `[TTL, timeout, threshold, interval]` | 必须从 YAML 读取的业务参数类型 |

完整配置定义见 `config.yaml#refactoring_safety` 节点。
