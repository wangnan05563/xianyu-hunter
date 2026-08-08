# Refactoring Checklist 编码规范

> 本文件归档 xianyu-hunter-dev skill 中与「配置化重构 / 长任务执行 / 跨文件契约」主题相关的编码规范。
> 主索引见 [SKILL.md](../../../SKILL.md) 的"step 索引表"，元规范见 [meta-rules.md](../../../references/meta-rules.md)。
>
> **本文件来源**：基于历史 NameError/ImportError 复盘、PowerShell 长任务执行失败案例、跨文件引用断裂事故等真实问题提炼，遵循"预防同类问题再次发生"原则，所有规范均有"为什么这么做"的说明与适用/不适用场景。

---

### step 262：配置化重构 5 步法【强制】🆕v4.63

262. **配置化重构 5 步法【强制】🆕v4.63**

    当把硬编码常量迁移到 `config.yaml` 时，必须严格按以下 5 步顺序执行，缺一不可：

    1. **grep 所有引用点**：`Grep -rn "<OLD_CONSTANT>" --include="*.py"` 列出所有使用方（含 import、注释、docstring）
    2. **Config 类新增字段**：在 `Config` 类中新增字段，带默认值与 docstring（说明取值范围、单位、为何此默认值）
    3. **config.yaml 新增配置块**：在 `config.yaml` 新增配置块，带注释说明（业务含义、变更影响范围）
    4. **源文件改为函数**：原硬编码常量改为 `_get_xxx()` 函数，内部 `try/except` 读取配置，失败时回退到默认值
    5. **强制核对引用点**：逐一核对步骤 1 列出的每个引用点已更新（含 import 语句、文档字符串、注释中的旧名）

    - **为什么这么做**：历史 NameError/ImportError 多源于"改了源文件但漏改引用点"，尤其是 import 语句、文档字符串、注释中的旧常量名。5 步法用 grep 强制全量核对，避免人工记忆遗漏。
    - **适用**：硬编码常量迁移到配置文件、模块级常量重构为函数、跨文件符号重命名
    - **不适用**：纯函数内部局部变量重命名、单文件内的常量移动、一次性脚本
    - **配置参数**：`config/tech-stack.json#hardConstraints.configRefactoring` 控制是否启用强制核对、grep 工具选择
    - **关联**：meta-rule #93 REFACTOR-IMPORT-COMPLETENESS / B-REVIEW-254

---

### step 263：作用域契约校验【强制】🆕v4.63

263. **作用域契约校验【强制】🆕v4.63**

    Python 函数访问配置/状态时，必须严格匹配作用域契约：

    | 函数类型 | 允许的访问方式 | 禁止 |
    |---|---|---|
    | 模块级函数 | 局部变量 或 `get_config()` | `self.xxx` / `cls.xxx` |
    | 类方法（实例方法） | `self.xxx` | 直接访问模块级单例 |
    | 静态方法 | 局部变量 或 `get_config()` | `self.xxx` / `cls.xxx` |

    - **检查点**：函数签名是否有 `self`/`cls` 参数；若有则用 `self`/`cls`，若无则用 `get_config()` 或局部变量
    - **为什么这么做**：历史 bug 多源于 `@staticmethod` 内误用 `self`（抛 NameError）或模块级函数内误用 `cls`（抛 NameError）；配置化重构时尤其容易混淆。
    - **适用**：配置化重构、新函数编写、函数装饰器变更（如 `@staticmethod` ↔ `@classmethod`）
    - **不适用**：纯函数式代码（无类）、纯展示型工具函数
    - **配置参数**：`config/tech-stack.json#hardConstraints.configRefactoring.scopeContractCheck` 控制是否启用静态检查

---

### step 264：导入名称变更 checklist【强制】🆕v4.63

264. **导入名称变更 checklist【强制】🆕v4.63**

    修改 Python 模块的导出符号（删除/重命名/类型变更）时，必须按以下 checklist 核对：

    1. **删除导出名前**：`Grep -rn "from <module> import <name>"` 列出所有 import 处，逐一替换或保留兼容别名
    2. **改名为函数前**：所有调用方需加 `()` 调用（原 `XXX` → `XXX()`）
    3. **改名为类前**：所有调用方需实例化或改属性访问（原 `XXX` → `XXX()` 或 `XXX.attr`）
    4. **类型变更**（如 `str` → `Callable[[], str]`）：所有调用方需调整访问语义
    5. **回填 import**：重构后必须 `python -c "import <module>"` 或启动服务验证，catch `ImportError`/`NameError`

    - **为什么这么做**：历史 ImportError/NameError 多源于"删了导出名但没改 import"、"改成函数但调用方未加 `()`"等机械性错误。checklist 强制每个变更类型都有对应的核对动作。
    - **适用**：跨文件符号重命名、模块 API 重构、模块拆分/合并
    - **不适用**：单文件内符号重命名、纯私有（前缀 `_`）符号变更、未导出的内部辅助函数
    - **关联**：meta-rule #93 REFACTOR-IMPORT-COMPLETENESS / B-REVIEW-254

---

### step 265：PowerShell 长任务日志输出规范【强制】🆕v4.63

265. **PowerShell 长任务日志输出规范【强制】🆕v4.63**

    在 PowerShell 中执行时长 > 30 秒的命令时，必须按以下规范输出日志，避免 sink cmdlet 缓冲导致输出丢失或进程假死：

    | 操作 | 推荐 | 禁止 |
    |---|---|---|
    | 重定向输出 | `> <file>` 或 `Start-Process -RedirectStandardOutput <file>` | `\| Select-Object -Last N`（sink cmdlet 必须缓冲） |
    | 查看尾部 | `Get-Content -Tail N <file>` | 等待命令结束后一次性读取 |
    | 实时跟踪 | `Get-Content -Wait <file>` | 在另一终端用 `\| Out-Host` 切换 |
    | 子进程启动 | `Start-Process -NoNewWindow -RedirectStandardOutput <file> -RedirectStandardError <err>` | 同步 `Wait-Process` 阻塞主进程 |

    - **为什么这么做**：PowerShell 的 `Select-Object -Last N` 是 sink cmdlet，必须缓冲全部输出后才能取最后 N 行，长任务下表现为"进程假死"。同样，`Wait-Process` 阻塞主进程会导致 AI Agent 无法读取中间日志。
    - **适用**：执行时长 > 30 秒的命令（SonarQube 扫描、pytest 全量、npm build、Docker 构建等）
    - **不适用**：短命令（< 30 秒）、交互式命令（需实时输入）、GUI 程序
    - **配置参数**：`config/tech-stack.json#hardConstraints.powershellLongTask` 控制 longTaskThresholdSeconds、redirectStrategy
    - **关联失败模式**：F6 PowerShell 5.1 编码重定向

---

### step 266：系统资源过载容错规范【强制】🆕v4.63

266. **系统资源过载容错规范【强制】🆕v4.63**

    当完整测试集超时或系统资源过载时，必须按以下顺序降级验证策略：

    1. **Tier 1（首选）**：完整测试集（`pytest tests/`），超时阈值通过 `config/tech-stack.json#hardConstraints.longTaskFallback.tier1TimeoutSec` 管理
    2. **Tier 2（降级）**：直接 `python -c "import <改动模块>"` 验证改动文件的导入与基本语义
    3. **Tier 3（最小）**：仅用 `tsc --noEmit` 或 `python -m py_compile <file>` 验证改动文件语法

    资源监控（长任务执行前必做）：

    ```powershell
    # 查看 CPU/内存 Top 10
    Get-Process | Sort-Object CPU -Descending | Select-Object -First 10
    ```

    - **为什么这么做**：历史教训是完整测试集在系统资源紧张时假死，浪费 30 分钟无产出；Tier 2/3 在 30 秒内能验证 80% 的导入/语法错误。
    - **适用**：CI 环境、本地开发机资源紧张、紧急修复需快速验证
    - **不适用**：发布前最终验证（必须 Tier 1）、跨模块重构（必须 Tier 1）、数据库迁移（必须 Tier 1）
    - **配置参数**：`config/tech-stack.json#hardConstraints.longTaskFallback` 控制 tier1TimeoutSec/tier2Enabled/tier3Enabled/cpuThresholdPercent
    - **关联**：质量门禁规范 C3 测试验证三档

---

### step 267：跨文件引用同步校验规范【强制】🆕v4.63

267. **跨文件引用同步校验规范【强制】🆕v4.63**

    修改跨文件共享的导出符号前，必须按以下流程核对：

    1. **修改前**：`Grep -rn "from <module> import <name>"` 列出所有引用点
    2. **修改时**：所有引用点同步更新（含 import、re-export、文档示例）
    3. **修改后**：必须启动服务或运行测试验证，catch `ImportError`/`NameError`/`AttributeError`
    4. **回归验证**：运行 `pytest tests/` 或至少 `python -c "import <module>"` 验证导入链

    - **为什么这么做**：跨文件符号断裂是 NameError/ImportError 的主要根因；只改源文件不改引用点 = 单点故障。grep 强制全量可见，比 IDE 重构更可靠（IDE 可能漏扫 `.md` 文档示例、`.j2` 模板）。
    - **适用**：跨模块符号重命名、API 接口签名变更、共享工具函数移动、配置类字段重命名
    - **不适用**：单文件内符号变更、私有（`_` 前缀）符号、`__all__` 中已声明的内部符号
    - **关联**：meta-rule #93 REFACTOR-IMPORT-COMPLETENESS / D1 跨文件引用同步校验

---

### step 268：配置访问统一入口规范【强制】🆕v4.63

268. **配置访问统一入口规范【强制】🆕v4.63**

    所有业务参数（TTL/超时/阈值/间隔/重试次数等）必须通过 `config.yaml` 读取，禁止模块级硬编码常量。配置读取函数必须有异常回退到默认值。

    **禁止模式**：

    ```python
    # 禁止：模块级硬编码常量
    _LIVE_CACHE_TTL = 60
    _MAX_RETRY = 3

    def get_live_data():
        cache = LiveCache(ttl=_LIVE_CACHE_TTL)  # 改配置需改代码
    ```

    **推荐模式**：

    ```python
    # 推荐：配置化读取 + 异常回退
    def _get_live_cache_ttl() -> int:
        try:
            return get_config().cache.live_cache_ttl
        except Exception:
            return 60  # 默认值与 config.yaml 一致

    def get_live_data():
        cache = LiveCache(ttl=_get_live_cache_ttl())  # 改配置无需改代码
    ```

    - **为什么这么做**：模块级硬编码常量在部署后无法调整，需改代码 + 重启；配置化后改 `config.yaml` + 热加载即可。异常回退避免配置缺失时崩溃。
    - **适用**：TTL、超时秒数、重试次数、QPS 限制、阈值、间隔、批大小、缓存容量等业务参数
    - **不适用**：纯算法常量（如 π、数学常数）、框架约定的固定值（如 HTTP 状态码 200）、枚举值
    - **配置参数**：`config/tech-stack.json#hardConstraints.configAccess` 控制 forbiddenPatterns、requireTryExcept
    - **关联**：step 42 硬编码阈值禁用 / step 90 配置驱动原则强化 / D2 配置访问统一入口

---

### step 269：长任务执行资源预检规范【强制】🆕v4.63

269. **长任务执行资源预检规范【强制】🆕v4.63**

    执行长任务（SonarQube 扫描、全量 pytest、Docker 构建等）前，必须完成以下资源预检：

    1. **CPU/内存检查**：`Get-Process | Sort-Object CPU -Descending | Select-Object -First 10` 查看是否有占 CPU > 50% 的进程
    2. **磁盘空间检查**：确认输出目录可用空间 > 任务预估产物大小的 2 倍
    3. **锁文件检查**：`.git/index.lock`、`.scannerwork/` 等锁文件是否残留
    4. **依赖进程检查**：SonarQube Server、PostgreSQL、Docker daemon 等依赖是否在运行
    5. **配置文件检查**：`config.yaml`、`sonar-project.properties` 等是否合法

    - **为什么这么做**：长任务启动后才发现资源不足会浪费 10-30 分钟；预检 30 秒可避免 90% 的失败。
    - **适用**：执行时长 > 5 分钟的任务、生产构建、CI 流水线、数据库迁移
    - **不适用**：短命令（< 5 分钟）、纯本地开发命令、增量构建
    - **配置参数**：`config/tech-stack.json#hardConstraints.longTaskPrecheck` 控制 cpuThresholdPercent/diskSpaceMultiplier/lockFilePatterns
    - **关联**：step 232 预检前置规范 / B2 系统资源过载容错

---

### step 270：弹性恢复机制配置化规范【强制】🆕v4.63

270. **弹性恢复机制配置化规范【强制】🆕v4.63**

    长任务执行中的弹性恢复机制（ES read-only 锁自愈、CE 报告轮询、NOSONAR 位置校验、TRAE 沙箱旁路、项目锁清理）必须通过配置文件管理触发条件与重试参数，禁止硬编码。

    - **ES read-only 锁自愈**：检测到 `cluster.read_only` 状态时自动 `PUT _all/_settings {"index.blocks.read_only_allow_delete": null}`，重试次数与间隔从 `config.yaml#resilience.esReadOnlyRecovery` 读取
    - **CE 报告轮询**：SonarQube CE 任务报告轮询间隔、最大等待时长从 `config.yaml#resilience.ceReportPolling` 读取
    - **NOSONAR 位置校验**：NOSONAR 注释必须紧邻被抑制的 issue 行（前一行或同一行），偏差阈值从 `config.yaml#resilience.nosonarPositionTolerance` 读取
    - **TRAE 沙箱旁路**：TRAE 沙箱环境检测到时跳过 SonarQube 扫描，沙箱检测模式从 `config.yaml#resilience.sandboxBypass` 读取
    - **项目锁清理**：`.scannerwork/`、`.git/index.lock` 等锁文件检测到残留时自动清理，锁文件路径与清理策略从 `config.yaml#resilience.lockCleanup` 读取

    - **为什么这么做**：弹性恢复机制本身是为了提升容错，若其参数硬编码则失去调优能力；部署环境差异（CI/本地/Docker）需要不同的重试策略。
    - **适用**：SonarQube 质量门禁全流程、长任务执行、跨进程协作
    - **不适用**：一次性脚本、纯本地开发、无外部依赖的纯算法任务
    - **配置参数**：`config/tech-stack.json#hardConstraints.resilienceRecovery` 集中管理所有弹性恢复参数
    - **关联**：质量门禁规范 C2 弹性恢复机制

---
