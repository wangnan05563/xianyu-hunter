# 重构安全性审查（Refactoring Safety Checks）

> **配套技能**：[xianyu-frontend-code-review](../SKILL.md)
> **范围**：配置化重构 / 长任务构建执行 / 跨文件契约同步
> **复盘来源**：复盘规范集 A/B/D 三类前端版本（基于真实重构失败案例提炼）
> **审查阶段**：阶段 2 子阶段 2.7 重构安全性检查（在常规代码质量检查后执行）
> **配置节点**：`config.yaml#refactoring_safety_checks`

---

## 0. 设计原则

本节检查点源于真实重构失败复盘，强调"重构不是机械替换"——任何重命名、常量抽取、Hook 改造、构建命令变更都伴随着跨文件契约，必须配套同步验证。

**为什么独立成节**：常规代码质量检查（code-quality.md）关注"代码写得对不对"，重构安全性检查关注"改的过程是否安全"。两者维度不同，混在一起会模糊审查重点。

**通用执行约束**：
- 所有阈值参数（执行时长、变更文件数、引用计数等）通过 `config.yaml#refactoring_safety_checks` 管理，技能本身不硬编码
- 每个检查点必须解释"为什么这么做"（基于真实失败案例）
- 必须说明适用场景与不适用场景，避免误报

---

## A 类：配置化重构规范

### A1. 常量配置化 5 步法（F-REVIEW-220 CONSTANT-CONFIG-DRIVEN）

> **维度**：11 类型安全 / 4 业务逻辑
> **severity**：MAJOR
> **配置节点**：`refactoring_safety_checks.constant_config_driven`

**为什么这么做**：
历史复盘中，常量重构最常见的失败模式是"漏改引用点"——开发者只修改了定义位置，遗漏了分散在多个文件中的引用，导致运行时取到旧值或 `undefined`。机械替换无法覆盖所有引用点，必须遵循"grep 全量 → 新增常量 → 源文件改造 → 核对引用 → 文档同步"的五步闭环。

**判断信号**（命中任一即视为违规）：
- 改动常量定义但未执行 `grep -rn "<OLD_CONSTANT>" --include="*.ts" --include="*.tsx"` 全量引用扫描
- 常量已迁移到 `src/config/constants.ts` 但源文件仍保留旧的内联字面量
- 注释或文档字符串中引用旧常量名（如 `// 见 DEFAULT_INTERVAL` 未同步更新）
- 常量定义位置变更但未运行 `tsc --noEmit` 验证类型完整性

**修复模式**（5 步法闭环）：
```typescript
// Step 1: grep 所有引用点（PowerShell 等价命令）
// Grep 工具：pattern="OLD_CONSTANT", glob="*.{ts,tsx}", path="frontend/src/"

// Step 2: 在 constants.ts 新增常量
// frontend/src/config/constants.ts
export const POLL_INTERVAL_MS = 10000  // 数值通过 config.yaml 注入

// Step 3: 源文件改为读取配置
import { POLL_INTERVAL_MS } from '@/config/constants'
setInterval(refresh, POLL_INTERVAL_MS)

// Step 4: 强制核对——再次 grep 确认旧常量已无残留
// Grep 工具：pattern="OLD_CONSTANT"，期望返回 0 条

// Step 5: 注释同步更新
// ❌ 注释仍引用旧名：// 默认间隔见 DEFAULT_INTERVAL
// ✅ 注释同步更新：// 默认间隔见 POLL_INTERVAL_MS（config.yaml 注入）
```

**配置节点**：
```yaml
refactoring_safety_checks:
  constant_config_driven:
    enabled: true
    severity: MAJOR
    require_grep_before_refactor: true           # 重构前必须 grep 引用点
    require_tsc_verify_after: true               # 重构后必须 tsc --noEmit
    require_doc_sync: true                       # 注释/文档必须同步
    file_extensions_to_scan: [".ts", ".tsx"]     # grep 扫描扩展名
    constants_source_file: "src/config/constants.ts"  # 常量集中位置
```

**适用场景**：
- 常量从组件内联字面量迁移到 `constants.ts`
- 常量重命名（如 `DEFAULT_INTERVAL` → `POLL_INTERVAL_MS`）
- 常量值修改但需要核对所有引用点是否仍然兼容

**不适用场景**：
- 单次性临时变量（仅函数内部使用）
- 测试 fixture 中的 mock 数据
- 已被 ESLint `no-restricted-syntax` 规则覆盖的简单字面量替换

**历史教训**：
开发者将 `MIN_INTERVAL` 重命名为 `POLL_INTERVAL_MS`，只改了定义位置和 3 个主要调用点，遗漏了 `useAutoRefresh.ts` 中的引用。运行时该 Hook 取到 `undefined`，导致 setInterval 用 `undefined` 作为延迟参数被浏览器默认为 0ms，页面每秒发起数百次 API 请求触发后端限流。复盘后确立 5 步法，强制 grep 核对。

---

### A2. React Hooks 作用域契约（F-REVIEW-221 REACT-HOOKS-SCOPE-CONTRACT）

> **维度**：3 React 组件规范 / 10 Hooks 设计模式
> **severity**：HIGH
> **配置节点**：`refactoring_safety_checks.react_hooks_scope_contract`

**为什么这么做**：
Hook 改造时最容易混淆"组件作用域"和"模块作用域"。复盘案例显示，开发者将组件内的 `useState` 提升为模块级常量以"避免重复创建"，导致多组件实例共享同一状态——切换 Tab 后两个 Tab 显示相同数据。React Hooks 的状态隔离依赖函数作用域，破坏作用域契约即破坏状态隔离。

**判断信号**（命中任一即视为违规）：
- 组件函数体内使用 `useState` / `useRef` 但被改为模块级 `let` 变量
- 自定义 Hook `useXxx` 被改为普通函数（丢失 `use` 前缀 + 不再调用 Hook）
- 模块级常量在组件 `useEffect` / 事件回调中被直接修改（破坏单数据流）
- 组件 re-mount 后状态未恢复（如导航离开再返回，筛选条件被保留）

**修复模式**（作用域契约）：
```typescript
// ❌ 反例 1：useState 提升为模块级变量
// frontend/src/pages/Tasks/TaskList.tsx
let selectedRowKeys: React.Key[] = []  // 模块级，多实例共享！
function TaskList() {
  // selectedRowKeys 在多个 TaskList 实例间共享，切换 Tab 后数据错乱
}

// ✅ 正例 1：保持 useState 在组件内
function TaskList() {
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  // 每个 TaskList 实例有独立状态
}

// ❌ 反例 2：Hook 被改为普通函数
// frontend/src/hooks/useAutoRefresh.ts
export function autoRefresh(interval: number) {  // 丢失 use 前缀，不再调用 Hook
  setInterval(() => refresh(), interval)
}

// ✅ 正例 2：保留 use 前缀 + 内部调用 Hook
export function useAutoRefresh(interval: number) {
  const timerRef = useRef<number>()
  useEffect(() => {
    timerRef.current = window.setInterval(() => refresh(), interval)
    return () => clearInterval(timerRef.current)
  }, [interval])
}

// ❌ 反例 3：模块级常量被组件修改
const SHARED_CACHE = new Map()  // 模块级
function TaskList() {
  useEffect(() => {
    SHARED_CACHE.set('tasks', data)  // 多实例互相覆盖
  }, [data])
}

// ✅ 正例 3：状态提升到 Zustand 或 props，而非模块级可变状态
// 或使用 useRef 持有实例级缓存
function TaskList() {
  const localCacheRef = useRef(new Map())
  useEffect(() => {
    localCacheRef.current.set('tasks', data)
  }, [data])
}
```

**re-mount 状态恢复检查**：
- 组件被路由切换卸载后重新挂载，`useState` 初始值必须恢复为初始状态（不应保留上次状态）
- 持久化状态（如列配置、筛选条件）必须通过 `usePersistentState` Hook 显式持久化，不应依赖模块级变量隐式保留
- `usePersistentState` 的 localStorage key 必须有命名空间（见 D2 检查点）

**配置节点**：
```yaml
refactoring_safety_checks:
  react_hooks_scope_contract:
    enabled: true
    severity: HIGH
    forbid_module_level_mutable_in_component: true    # 禁止组件内修改模块级可变变量
    require_use_prefix_for_hooks: true                  # Hook 必须保留 use 前缀
    require_persistent_state_for_cross_mount: true      # 跨 mount 状态必须用 usePersistentState
    persistent_state_hook_name: "usePersistentState"    # 持久化 Hook 名称
```

**适用场景**：
- Hook 重构（如 `useXxx` 拆分为多个 Hook 或合并）
- 组件状态管理方式变更（`useState` → Zustand / Context）
- 提取自定义 Hook（确认保留 `use` 前缀 + 内部调用 Hook）

**不适用场景**：
- 纯工具函数（无状态，无 Hook 调用）
- 模块级不可变常量（`const CONFIG = Object.freeze({...})`）
- SSR 场景（需另行评估 hydration 一致性）

**历史教训**：
将 `useFilterState` Hook 改造为返回纯对象的工厂函数以"减少 Hook 调用次数"，结果多个列表页共享同一份筛选状态——A 页面选择"已完成"后，B 页面也显示"已完成"筛选。复盘确认 Hook 的 `use` 前缀不仅是命名约定，更是 React 用于识别状态隔离边界的标记，丢失前缀等于丢失隔离。

---

### A3. 导入名称变更 checklist（F-REVIEW-222 IMPORT-NAME-CHANGE-CHECKLIST）

> **维度**：11 类型安全 / 2 命名规范
> **severity**：MAJOR
> **配置节点**：`refactoring_safety_checks.import_name_change_checklist`

**为什么这么做**：
重命名导出符号时，三类调用方的修改方式不同：值调用需加 `()`、组件调用需用 JSX、Hook 调用需保留 `use` 前缀。复盘案例显示，开发者统一用"查找替换"重命名，导致 Hook 被当作普通函数调用（丢失 React Hook 调用规则）、组件被当作函数调用（丢失 JSX 上下文）。重命名必须按调用类型分类核对。

**判断信号**（命中任一即视为违规）：
- 删除导出名前未执行 `grep -rn "from '<module>' import <name>"` 全量引用扫描
- 将 Hook 重命名为普通函数后，调用方未同步加 `()` 调用
- 将函数重命名为组件后，调用方未同步改为 `<NewName />` JSX 形式
- 重命名后 `tsc --noEmit` 报错但未修复即提交

**修复模式**（按调用类型分类核对）：
```typescript
// === 场景 1：Hook 改名为普通函数 ===
// 旧：export function useFetchTasks() { ... }
// 新：export function fetchTasks() { ... }

// ❌ 调用方未修改
const tasks = useFetchTasks  // 丢失 () 调用，tasks 是函数引用而非结果

// ✅ 调用方加 () 调用
const tasks = fetchTasks()

// === 场景 2：函数改名为组件 ===
// 旧：export function taskList(props: TaskListProps) { ... }
// 新：export function TaskList(props: TaskListProps) { ... }

// ❌ 调用方未改为 JSX
{taskList({ items })}  // 函数调用形式，丢失 React 上下文

// ✅ 调用方改为 JSX
{<TaskList items={items} />}

// === 场景 3：Hook 改名为另一个 Hook ===
// 旧：export function useTaskFilter() { ... }
// 新：export function useFilterState() { ... }

// ✅ 调用方同步更新变量名 + 保留 use 前缀调用
const filterState = useFilterState()  // 保留 () 调用
```

**变更 checklist**（重构前必跑）：
1. `grep -rn "from '<module>' import <oldName>"` 找到所有引用点
2. 按调用类型分类：
   - Hook 调用（`use` 前缀）→ 保留 `()` 调用
   - 函数调用 → 加 `()` 调用
   - 组件调用 → 改为 `<PascalCase />` JSX
3. 同步更新 TypeScript 类型定义（`types.ts` 中导出类型引用）
4. 运行 `tsc --noEmit` 验证类型完整性
5. 运行 `npm run lint` 验证 ESLint 规则（如 `react-hooks/rules-of-hooks`）

**配置节点**：
```yaml
refactoring_safety_checks:
  import_name_change_checklist:
    enabled: true
    severity: MAJOR
    require_grep_before_rename: true                 # 重命名前必须 grep
    require_tsc_verify_after: true                   # 重命名后必须 tsc --noEmit
    require_lint_verify_after: true                  # 重命名后必须 eslint
    hook_call_patterns: ["use[A-Z]\\w*"]              # Hook 调用识别模式
    component_call_patterns: ["<[A-Z]\\w+"]          # 组件调用识别模式
    verify_command: "npm --prefix frontend run typecheck"
```

**适用场景**：
- 重命名导出符号（Hook / 函数 / 组件 / 类型）
- 修改导出方式（`export default` → `export` / 反向）
- 拆分模块（如将 `utils.ts` 拆为 `utils/format.ts` + `utils/date.ts`）

**不适用场景**：
- 仅修改实现细节（不改变导出名）
- 内部私有变量重命名（不涉及外部引用）
- 自动生成的代码（由工具负责同步）

**历史教训**：
将 `useTaskFilter` Hook 重命名为 `fetchTaskFilter`（意图表达"这是 fetch 操作"），但调用方仍按 Hook 形式 `const filter = fetchTaskFilter` 调用，导致 `filter` 是函数引用而非结果。运行时访问 `filter.current` 报错 `undefined`。复盘确认：Hook 改名必须区分"是否保留 use 前缀"，保留前缀则调用方不变，去掉前缀则调用方必须加 `()`。

---

## B 类：长任务执行规范

### B1. 长任务前端构建日志输出（F-REVIEW-223 LONG-TASK-BUILD-LOG-REDIRECT）

> **维度**：12 SonarQube 合规 / 工程化规范
> **severity**：MAJOR
> **配置节点**：`refactoring_safety_checks.long_task_build_log_redirect`

**为什么这么做**：
PowerShell 的 sink cmdlet（如 `| Select-Object -Last N`、`| Out-Host -Paging`）会缓冲整个输出流，导致长任务（npm run build / tsc --noEmit / vitest / playwright test）执行时终端无任何输出，开发者误以为卡死而中断。复盘案例显示，tsc --noEmit 在大型项目中执行 60+ 秒，使用 `| Select-Object -Last 50` 后终端无输出，开发者中断并重试 3 次，每次都因"看似卡死"而中断。必须改用文件重定向避免缓冲。

**判断信号**（命中任一即视为违规）：
- 构建脚本中使用 `| Select-Object -Last N` / `| Out-Host -Paging` / `| more` 等 sink cmdlet
- 构建命令未重定向输出到文件，导致超长输出无法回溯
- 长任务脚本未设置超时（依赖人工中断）

**修复模式**（文件重定向）：
```powershell
# ❌ 反例：sink cmdlet 导致缓冲
npm --prefix frontend run build | Select-Object -Last 50
tsc --noEmit | Out-Host -Paging

# ✅ 正例 1：文件重定向 + 实时 tail
$logFile = "frontend-build-$(Get-Date -Format 'yyyyMMdd-HHmmss').log"
Start-Process -FilePath "npm" -ArgumentList "run","build" `
  -WorkingDirectory "frontend" `
  -RedirectStandardOutput $logFile `
  -RedirectStandardError "build-err.log" `
  -NoNewWindow -Wait
Get-Content $logFile -Wait -Tail 20  # 实时 tail 最后 20 行

# ✅ 正例 2：调用 cmd 避免 PowerShell 管道
cmd /c "npm --prefix frontend run build > build.log 2>&1"

# ✅ 正例 3：直接执行（短任务）
npm --prefix frontend run build  # 不使用管道，输出直接显示
```

**适用命令清单**（执行时长通常超过阈值）：
- `npm run build` / `npm run typecheck` / `tsc --noEmit`
- `vitest run` / `vitest watch` / `jest`
- `playwright test` / `playwright codegen`
- `eslint --fix` 大型项目

**配置节点**：
```yaml
refactoring_safety_checks:
  long_task_build_log_redirect:
    enabled: true
    severity: MAJOR
    long_task_threshold_seconds: 30        # 执行时长阈值（秒），超过即视为长任务
    forbidden_sink_cmdlets:                # 禁止的 sink cmdlet 清单
      - "Select-Object"
      - "Out-Host"
      - "Out-String"
      - "more"
      - "less"
    recommended_redirect_strategy: "Start-Process -RedirectStandardOutput"
    log_file_pattern: "build-{timestamp}.log"
    require_timeout: true                  # 长任务必须设置超时
    default_timeout_seconds: 300           # 默认超时 5 分钟
    long_task_commands:                    # 长任务命令清单
      - "npm run build"
      - "npm run typecheck"
      - "tsc --noEmit"
      - "vitest run"
      - "playwright test"
```

**适用场景**：
- PowerShell 终端执行前端构建 / 类型检查 / 测试
- CI/CD 流水线中的长任务步骤
- 本地开发时运行 vitest / playwright

**不适用场景**：
- bash / zsh / Git Bash 环境（管道行为不同）
- 短任务（执行时长 < 阈值，无需重定向）
- IDE 内置终端的交互式命令（如 `npm run dev` 需实时输出）

**历史教训**：
开发者执行 `tsc --noEmit | Select-Object -Last 50` 检查类型错误，PowerShell 缓冲整个输出流（约 2000 行），执行 90 秒期间终端无任何反馈。开发者误以为卡死中断 3 次，每次重新执行都从零开始。最终改为 `Start-Process -RedirectStandardOutput build.log` + `Get-Content -Wait` 实时 tail，执行 90 秒期间可见进度输出。复盘确认 sink cmdlet 是 PowerShell 长任务的常见陷阱。

---

### B2. 系统资源过载容错（F-REVIEW-224 SYSTEM-RESOURCE-OVERLOAD-TOLERANCE）

> **维度**：12 SonarQube 合规 / 16 性能
> **severity**：WARNING
> **配置节点**：`refactoring_safety_checks.system_resource_overload_tolerance`

**为什么这么做**：
大型 TypeScript 项目执行 `tsc --noEmit` 时 Node.js 进程内存占用可达 4GB+，触发 V8 堆内存限制导致进程崩溃或无限卡顿。复盘案例显示，开发者执行全量 tsc 检查卡住 5 分钟无响应，最终进程被 OOM Killer 杀死。容错策略是：卡住时改用单文件检查 + 监控 Node 进程内存。

**判断信号**（命中任一即视为违规）：
- `tsc --noEmit` 全量检查超过 `long_task_threshold_seconds` 仍无输出
- Node 进程内存占用超过 `node_memory_threshold_mb`（如 4096MB）
- 脚本未提供单文件检查 fallback 选项
- 长任务未监控 Node 进程内存

**修复模式**（容错策略）：
```powershell
# ❌ 反例：全量 tsc 无 fallback
tsc --noEmit  # 卡住无响应，无容错

# ✅ 正例 1：单文件检查 fallback
# 若全量 tsc 卡住，改为单文件检查
tsc --noEmit --skipLibCheck frontend/src/pages/Tasks/TaskList.tsx

# ✅ 正例 2：监控 Node 进程内存
$nodeProc = Get-Process -Name "node" -ErrorAction SilentlyContinue
if ($nodeProc -and $nodeProc.WorkingSet64 -gt 4GB) {
    Write-Warning "Node 进程内存超过 4GB，可能卡住，建议中断并改用单文件检查"
    Stop-Process -Id $nodeProc.Id -Force
    # 切换为单文件检查
    tsc --noEmit --skipLibCheck <target-file>
}

# ✅ 正例 3：增加 Node 堆内存上限
$env:NODE_OPTIONS = "--max-old-space-size=8192"
tsc --noEmit

# ✅ 正例 4：使用 project references 拆分检查
tsc --noEmit -p frontend/src/pages/tsconfig.json
tsc --noEmit -p frontend/src/components/tsconfig.json
```

**配置节点**：
```yaml
refactoring_safety_checks:
  system_resource_overload_tolerance:
    enabled: true
    severity: WARNING
    node_memory_threshold_mb: 4096                # Node 进程内存阈值（MB）
    long_task_threshold_seconds: 60              # 长任务判定阈值（秒）
    fallback_to_single_file: true                 # 卡住时 fallback 单文件检查
    single_file_check_command: "tsc --noEmit --skipLibCheck <file>"
    node_options_env: "--max-old-space-size=8192"  # Node 堆内存上限
    require_memory_monitor: true                  # 长任务必须监控 Node 内存
    oom_recovery_strategy: "single_file_check"   # OOM 后恢复策略
```

**适用场景**：
- 大型 TypeScript 项目全量类型检查
- CI/CD 流水线中 tsc 卡住无响应
- 本地开发时 vitest 执行大量测试用例

**不适用场景**：
- 小型项目（tsc 执行 < 30 秒）
- 非构建类任务（如纯 lint 检查）
- 已使用 SWC / esbuild 等快速类型检查工具

**历史教训**：
全量 `tsc --noEmit` 卡住 5 分钟无响应，开发者强制结束后再次执行仍卡住。排查发现 Node 进程内存占用 6GB（V8 默认上限 4GB，已被 swap 拖慢）。最终改为单文件检查 + `--max-old-space-size=8192` 环境变量，10 秒内完成单文件类型检查。复盘确认大型项目的类型检查必须有 fallback 策略。

---

## D 类：跨文件契约规范

### D1. 跨文件引用同步校验（F-REVIEW-225 CROSS-FILE-CONTRACT-SYNC）

> **维度**：11 类型安全 / 6 Zustand 状态管理
> **severity**：CRITICAL
> **配置节点**：`refactoring_safety_checks.cross_file_contract_sync`

**为什么这么做**：
前端重构失败的最高频根因是"跨文件引用未同步"——修改了导出符号但遗漏了引用方，导致 `ImportError` / `TypeError: undefined is not a function` 等运行时错误。复盘案例显示，开发者删除了 `utils/format.ts` 中的 `formatPrice` 函数，但 `ItemList.tsx` 仍在引用，运行时页面崩溃。仅靠 IDE 重命名功能无法覆盖动态导入和字符串引用，必须用 `tsc --noEmit` 兜底验证。

**判断信号**（命中任一即视为违规）：
- 修改导出符号（重命名 / 删除 / 改签名）前未 grep 所有引用点
- 重构后未运行 `tsc --noEmit` 验证（catch ImportError / NameError）
- 删除导出符号但未检查 `import * as` / `require` / 动态 `import()` 引用
- 修改函数签名（参数数量 / 类型）但未同步更新所有调用方

**修复模式**（跨文件同步校验）：
```typescript
// === 场景 1：删除导出符号 ===
// Step 1: grep 所有引用点
// Grep 工具：pattern="formatPrice", glob="*.{ts,tsx}", path="frontend/src/"

// Step 2: 确认引用方已迁移替代方案
// frontend/src/pages/Items/ItemList.tsx
// ❌ 仍引用已删除的 formatPrice
import { formatPrice } from '@/utils/format'  // 运行时 ImportError

// ✅ 迁移到新位置
import { formatPrice } from '@/utils/currency'  // 新位置

// Step 3: tsc 验证
// $ tsc --noEmit
// 若有遗漏的引用，tsc 会报错：Cannot find module or its corresponding type declarations

// === 场景 2：修改函数签名 ===
// 旧：export function updateTask(id: string, data: Partial<Task>)
// 新：export function updateTask(id: string, data: Partial<Task>, options?: { silent?: boolean })

// ❌ 调用方未同步（虽然不会报错，但调用方未利用新参数）
updateTask('123', { status: 'completed' })

// ✅ 调用方同步更新（若需要 silent 选项）
updateTask('123', { status: 'completed' }, { silent: true })

// === 场景 3：动态导入 ===
// ❌ 字符串引用无法被 IDE 重命名覆盖
const module = await import('@/utils/format')
module.formatPrice()  // 运行时 undefined

// ✅ 改为静态导入 + tsc 验证
import { formatPrice } from '@/utils/currency'
```

**校验命令清单**（重构后必跑）：
1. `tsc --noEmit`（catch 类型错误 + 缺失导入）
2. `npm run lint`（catch ESLint 规则违规，如 `no-unused-vars`、`no-undef`）
3. `npm test`（catch 运行时行为变化）
4. `npm run build`（catch 构建时错误，如 tree-shaking 移除仍在使用的代码）

**配置节点**：
```yaml
refactoring_safety_checks:
  cross_file_contract_sync:
    enabled: true
    severity: CRITICAL
    require_grep_before_export_change: true      # 修改导出前必须 grep
    require_tsc_verify_after: true                # 重构后必须 tsc --noEmit
    require_lint_verify_after: true               # 重构后必须 eslint
    require_test_verify_after: true               # 重构后必须运行测试
    require_build_verify_after: true              # 重构后必须运行构建
    verify_commands:                              # 验证命令清单
      - "npm --prefix frontend run typecheck"
      - "npm --prefix frontend run lint"
      - "npm --prefix frontend test"
      - "npm --prefix frontend run build"
    scan_file_extensions: [".ts", ".tsx"]        # grep 扫描扩展名
    dynamic_import_patterns: ["import\\(", "require\\("]  # 动态导入识别模式
```

**适用场景**：
- 删除 / 重命名导出符号（函数 / 类 / 类型 / 常量）
- 修改函数签名（参数数量 / 类型 / 顺序）
- 修改模块路径（如 `@/utils/format` → `@/utils/currency`）
- 拆分 / 合并模块文件

**不适用场景**：
- 仅修改实现细节（不改变导出 API）
- 测试代码内部重构（不影响生产代码）
- 自动生成的代码（由工具负责同步）

**历史教训**：
开发者删除 `utils/format.ts` 中的 `formatPrice` 函数（已迁移到 `utils/currency.ts`），但 `ItemList.tsx` 仍通过 `import { formatPrice } from '@/utils/format'` 引用。IDE 重命名功能未覆盖该引用（因 `tsconfig.json` 路径别名配置变化）。运行时页面加载后 `formatPrice is not a function`，用户访问商品列表页崩溃。复盘确认：跨文件重构必须用 `tsc --noEmit` 兜底验证，IDE 重命名无法覆盖所有引用模式。

---

### D2. 状态持久化统一入口（F-REVIEW-226 STATE-PERSISTENCE-UNIFIED-ENTRY）

> **维度**：6 Zustand 状态管理 / 10 Hooks 设计模式
> **severity**：HIGH
> **配置节点**：`refactoring_safety_checks.state_persistence_unified_entry`

**为什么这么做**：
业务参数（轮询间隔、timeout、阈值）硬编码在组件内会导致两类问题：1) 修改需改代码重新部署；2) 不同环境（开发 / 测试 / 生产）无法差异化配置。复盘案例显示，开发者将轮询间隔硬编码为 `10000`，测试环境调试时需修改代码才能加快轮询。此外 localStorage key 无命名空间会导致跨页面冲突——`columns` key 被 ListA 和 ListB 同时使用，后写入的覆盖前者。

**判断信号**（命中任一即视为违规）：
- 业务参数（轮询间隔 / timeout / 阈值）硬编码在组件内（如 `setInterval(refresh, 10000)`）
- localStorage key 无命名空间（如 `localStorage.setItem('columns', ...)` 而非 `xh.orders.columns`）
- 状态读取无类型守卫（如 `JSON.parse(localStorage.getItem('columns'))` 不校验类型）
- 不同页面的 localStorage key 命名风格不一致（如 `columns` vs `taskColumns` vs `task_columns`）

**修复模式**（统一入口 + 命名空间 + 类型守卫）：
```typescript
// ❌ 反例 1：业务参数硬编码
function TaskList() {
  useEffect(() => {
    const timer = setInterval(refresh, 10000)  // 10000 硬编码
    return () => clearInterval(timer)
  }, [])
}

// ✅ 正例 1：从 config 读取
import { POLL_INTERVALS } from '@/config/constants'
function TaskList() {
  useEffect(() => {
    const timer = setInterval(refresh, POLL_INTERVALS.TASK_LIST)  // 从 config 读取
    return () => clearInterval(timer)
  }, [])
}

// ❌ 反例 2：localStorage key 无命名空间
localStorage.setItem('columns', JSON.stringify(columns))  // 跨页面冲突

// ✅ 正例 2：命名空间 key
const STORAGE_KEY = 'xh.orders.columns'  // 命名空间：xh.<page>.<field>
localStorage.setItem(STORAGE_KEY, JSON.stringify(columns))

// ❌ 反例 3：状态读取无类型守卫
const columns = JSON.parse(localStorage.getItem('columns') || '[]')  // 无类型校验
columns.forEach(col => console.log(col.width))  // 若 col 无 width 字段，undefined

// ✅ 正例 3：类型守卫
function isColumn(value: unknown): value is Column {
  return typeof value === 'object' && value !== null &&
    'key' in value && 'width' in value
}
function loadColumns(): Column[] {
  const raw = localStorage.getItem('xh.orders.columns')
  if (!raw) return DEFAULT_COLUMNS
  try {
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return DEFAULT_COLUMNS
    return parsed.every(isColumn) ? parsed : DEFAULT_COLUMNS
  } catch {
    return DEFAULT_COLUMNS
  }
}

// ✅ 正例 4：统一通过 usePersistentState Hook 持久化
import { usePersistentState } from '@/hooks/usePersistentState'
function OrdersPage() {
  const [columns, setColumns] = usePersistentState<Column[]>(
    'xh.orders.columns',           // 命名空间 key
    DEFAULT_COLUMNS,                // 默认值
    isColumnArray                   // 类型守卫
  )
}
```

**命名空间约定**：
- 格式：`xh.<page>.<field>`（如 `xh.orders.columns`、`xh.tasks.filters`）
- 前缀 `xh` 表示闲鱼猎人项目
- `<page>` 为页面标识（如 `orders`、`tasks`、`evaluations`）
- `<field>` 为字段标识（如 `columns`、`filters`、`viewMode`）

**配置节点**：
```yaml
refactoring_safety_checks:
  state_persistence_unified_entry:
    enabled: true
    severity: HIGH
    forbid_hardcoded_business_params: true        # 禁止业务参数硬编码
    require_namespace_for_localstorage: true      # localStorage key 必须有命名空间
    require_type_guard_for_state_read: true       # 状态读取必须有类型守卫
    namespace_prefix: "xh"                        # 命名空间前缀
    namespace_pattern: "xh\\.<page>\\.<field>"    # 命名空间正则
    business_params_source: "config"              # 业务参数来源（config / env / api）
    persistent_state_hook: "usePersistentState"   # 持久化 Hook 名称
    forbidden_hardcoded_patterns:                 # 禁止硬编码模式
      - "setInterval\\([^,]+,\\s*\\d+\\)"
      - "setTimeout\\([^,]+,\\s*\\d+\\)"
      - "localStorage\\.setItem\\(['\"][^'\".]+['\"]"  # 无命名空间的 key
```

**适用场景**：
- 业务参数（轮询间隔 / timeout / 阈值 / 重试次数）
- 用户偏好持久化（列配置 / 筛选条件 / 视图模式）
- localStorage 状态管理
- 跨页面共享的状态

**不适用场景**：
- 一次性临时变量（无需持久化）
- 服务端状态（由 API 管理，使用 React Query / SWR）
- 临时 UI 状态（如 Modal open / close，无需持久化）

**历史教训**：
开发者将轮询间隔硬编码为 `10000`，测试环境调试时需修改代码才能加快轮询。同时 `columns` key 被 OrdersPage 和 TasksPage 同时使用——用户先访问 OrdersPage 设置列配置，再访问 TasksPage 时列配置被覆盖。复盘确认：业务参数必须从 config 读取，localStorage key 必须有命名空间。

---

## 附录：与其他检查点的关系

| 本节检查点 | 关联检查点 | 关系说明 |
|-----------|-----------|---------|
| F-REVIEW-220 CONSTANT-CONFIG-DRIVEN | F-REVIEW-CONFIG-DRIVEN-TOGGLE（v4.4） | 前者关注常量重构过程，后者关注功能开关配置驱动 |
| F-REVIEW-221 REACT-HOOKS-SCOPE-CONTRACT | F-REVIEW-EFFECT-MINIMIZE（v4.33） | 前者关注 Hook 作用域契约，后者关注 useEffect 副作用最小化 |
| F-REVIEW-221 REACT-HOOKS-SCOPE-CONTRACT | F-REVIEW-UI-PREFERENCE-PERSISTENCE（v4.24） | 前者确立 usePersistentState 模式，后者验证偏好持久化 |
| F-REVIEW-222 IMPORT-NAME-CHANGE-CHECKLIST | F-REVIEW-PRIVATE-HOOK-ENCAPSULATION（v4.30） | 前者关注重命名 checklist，后者关注私有 Hook 封装 |
| F-REVIEW-223 LONG-TASK-BUILD-LOG-REDIRECT | F-REVIEW-194 TS-STRICT-CHECK（v4.51.1） | 前者关注长任务执行，后者关注类型检查严格性 |
| F-REVIEW-224 SYSTEM-RESOURCE-OVERLOAD-TOLERANCE | F-REVIEW-208 BUILD-ENVIRONMENT-TOOLCHAIN（v4.58.0） | 前者关注资源容错，后者关注工具链版本 |
| F-REVIEW-225 CROSS-FILE-CONTRACT-SYNC | F-REVIEW-119 CONTRACT-SINGLE-SOURCE（v4.36） | 前者关注前端跨文件同步，后者关注前后端字段契约 |
| F-REVIEW-226 STATE-PERSISTENCE-UNIFIED-ENTRY | F-REVIEW-UI-PREFERENCE-PERSISTENCE（v4.24） | 前者确立统一入口与命名空间，后者验证偏好持久化实施 |

---

## 附录：执行优先级

| 检查点 | 优先级 | 阻塞合并 | 理由 |
|--------|--------|----------|------|
| F-REVIEW-225 CROSS-FILE-CONTRACT-SYNC | P0 | 是 | 跨文件契约失败导致运行时崩溃 |
| F-REVIEW-221 REACT-HOOKS-SCOPE-CONTRACT | P1 | 否（强烈建议） | 作用域错误导致状态隔离失效 |
| F-REVIEW-226 STATE-PERSISTENCE-UNIFIED-ENTRY | P1 | 否（强烈建议） | 硬编码与命名空间冲突导致数据丢失 |
| F-REVIEW-220 CONSTANT-CONFIG-DRIVEN | P2 | 否 | 漏改引用导致取到旧值 |
| F-REVIEW-222 IMPORT-NAME-CHANGE-CHECKLIST | P2 | 否 | 调用方式错误导致运行时异常 |
| F-REVIEW-223 LONG-TASK-BUILD-LOG-REDIRECT | P3 | 否 | 影响开发效率，不影响运行时 |
| F-REVIEW-224 SYSTEM-RESOURCE-OVERLOAD-TOLERANCE | P3 | 否 | 影响开发效率，不影响运行时 |
