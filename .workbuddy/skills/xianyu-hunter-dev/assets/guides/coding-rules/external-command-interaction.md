# External Command Interaction 编码规范

> 本文件归档外部命令交互（长时交互式命令两阶段异步执行）相关的编码规范。
> 主索引见 [SKILL.md](../../../SKILL.md) 的 step 索引表，元规范见 [meta-rules.md](../../../references/meta-rules.md)。
> 所有参数（超时、轮询间隔、检测路径等）均通过 config.yaml 的 `external_command_interaction` 节点管理，禁止硬编码。

---

### step 223：长时交互式命令识别与两阶段拆分【强制】 🆕v4.46

223. **长时交互式命令识别与两阶段拆分【强制】**
- 当外部命令满足以下任一特征时，必须拆分为两阶段异步模式（POST /start + GET /status），禁止使用 `subprocess.run` 阻塞调用：
  - 需要用户交互（浏览器授权、确认提示、输入凭证）
  - 运行时间不可预测（依赖用户操作完成、网络条件）
  - 输出包含关键信息（授权 URL、token、session ID）需要在进程运行中实时提取
  - 完成标志为文件生成（cert.pem、credentials.json），生成时机不确定
- 两阶段拆分契约：
  - Phase 1（POST /start）：`subprocess.Popen` 非阻塞启动 + 后台线程读取 stdout + 短时等待提取关键信息 → 返回 `waiting` 状态
  - Phase 2（GET /status）：轮询检查完成标志（文件存在/进程退出）→ 返回 `success`/`failed`/`waiting`/`idle`
- 判断命令是否需要两阶段的决策树参数在 config.yaml `external_command_interaction.two_phase_trigger` 中管理
- 历史教训：cloudflared tunnel login 使用 `subprocess.run(timeout=30)` 阻塞调用，因用户授权耗时超过 30s 导致 axios 超时，且 `capture_output=True` 吞掉了授权 URL，用户无法手动打开

**判断规则**：
- `grep -rn "subprocess.run.*timeout=" src/` 命中且命令涉及用户交互 → 违反两阶段拆分
- `grep -rn "capture_output=True" src/` 命中且输出包含关键信息 → 违反实时读取
- HTTP 端点内调用 `subprocess.run` 且执行时间可能超过 HTTP 超时 → 必须拆分

---

### step 224：子进程非阻塞启动与后台 stdout 读取【强制】 🆕v4.46

224. **子进程非阻塞启动与后台 stdout 读取【强制】**
- Phase 1 必须使用 `subprocess.Popen`（非阻塞）启动子进程，禁止 `subprocess.run`（阻塞至完成）
- 禁止使用 `capture_output=True` 或 `stdout=PIPE` + `communicate()`，这会阻塞到进程结束或缓冲区满
- 必须使用 `stdout=subprocess.PIPE` + `stderr=subprocess.STDOUT`（合并输出）+ `text=True`（行迭代）
- 必须启动后台守护线程（`daemon=True`）逐行读取 stdout，在读取过程中提取关键信息
- 关键信息提取正则模式通过 config.yaml `external_command_interaction.output_parsing` 配置，支持多模式 fallback
- Phase 1 启动后等待时间（提取关键信息的短时窗口）通过 config.yaml `external_command_interaction.start_wait_timeout` 配置，默认 10s
- Windows 平台必须设置 `creationflags=subprocess.CREATE_NO_WINDOW` 避免弹出控制台窗口
- 历史教训：`capture_output=True` 导致 cloudflared 输出的授权 URL 被吞，前端无法显示给用户手动打开

**判断规则**：
- `grep -rn "capture_output=True" src/` 在交互式命令场景命中 → 违规
- `grep -rn "subprocess.run" src/` 在需要用户交互的命令场景命中 → 违规
- Popen 后未启动后台线程读取 stdout → stdout 缓冲区满后子进程会挂起

---

### step 225：完成标志多路径检测【强制】 🆕v4.46

225. **完成标志多路径检测【强制】**
- 当命令的完成标志为文件生成时，必须检测所有可能的生成路径，禁止只检查单一目录
- 检测路径来源（全部通过 config.yaml `external_command_interaction.completion_detection.paths` 管理）：
  - 平台默认路径（如 `Path.home() / ".cloudflared" / "cert.pem"`）
  - 环境变量派生路径（如 `%LOCALAPPDATA%`、`%APPDATA%` 对应目录）
  - 从命令输出中正则提取的路径（兜底）
- 环境变量缺失时必须跳过对应路径，不得抛出异常
- 输出正则必须兼容 Windows 路径（`C:\...\file`）和 Unix 路径（`/.../file`），且处理含空格的路径
- 检测到完成标志后必须返回实际命中的路径，便于诊断和后续读取
- 失败时必须返回已检查的所有路径列表（`checked_paths`），帮助用户定位问题
- 历史教训：cloudflared 在 Windows 上可能将 cert.pem 写入 `%LOCALAPPDATA%\.cloudflared\` 而非 `%USERPROFILE%\.cloudflared\`，只检查单一目录导致误报"未找到 cert.pem"

**判断规则**：
- 完成标志检测只检查单一路径 → 违规
- 路径列表未包含环境变量派生路径 → 违规
- 失败响应中未包含 `checked_paths` 字段 → 诊断信息不足

---

### step 226：跨请求状态管理与全局单例生命周期【强制】 🆕v4.46

226. **跨请求状态管理与全局单例生命周期【强制】**
- 两阶段模式要求 Phase 1 和 Phase 2 在同一个对象实例上调用（子进程引用、输出缓冲、提取的关键信息都保存在实例上）
- HTTP 是无状态的，必须通过模块级全局单例保持跨请求状态
- 全局单例必须提供 `get`（惰性创建）和 `reset`（显式清理）两个管理函数
- 必须在以下三条退出路径上调用 `reset`：
  - 成功路径（Phase 2 返回 `success`）
  - 失败路径（Phase 2 返回 `failed`，或 Phase 1 启动失败）
  - 异常路径（任何未捕获异常的 except 块）
- `waiting` 状态下必须保留单例，供后续 Phase 2 轮询使用
- `reset` 函数内部必须调用子进程清理方法（terminate→wait→kill），不能只置 None
- 当 Phase 2 在单例未初始化时被调用，必须返回 `idle` 状态（而非抛出异常），前端据此提示用户重新触发
- 历史教训：Phase 1 创建的 provider 实例是局部变量，Phase 2 请求拿到的是新实例，子进程引用丢失导致无法检测 cert.pem

**判断规则**：
- `grep -rn "def.*login_status" src/` 命中但未通过全局单例获取 provider → 状态丢失
- 全局单例的 reset 函数未调用子进程清理方法 → 子进程泄漏
- Phase 2 在单例为 None 时抛出异常而非返回 idle → 前端无法优雅处理

---

### step 227：子进程清理协议（terminate→wait→kill）【强制】 🆕v4.46

227. **子进程清理协议（terminate→wait→kill）【强制】**
- 子进程清理必须按 `terminate → wait(timeout) → kill` 三步执行，禁止直接 kill
- `terminate()` 后必须等待 `wait(timeout=N)`，超时时间通过 config.yaml `external_command_interaction.cleanup_terminate_timeout` 配置（默认 3s）
- `wait` 超时后必须调用 `kill()` 强制终止
- 整个清理过程必须用 try/except/finally 包裹，finally 中置 None 确保引用释放
- `except` 块必须记录日志（`logger.warning`），不能静默吞掉异常
- 清理函数必须幂等：多次调用不应抛出异常（进程已退出时 terminate 是 no-op）
- 历史教训：login 成功后未清理子进程引用，导致子进程对象泄漏；直接 kill 可能导致子进程无法刷新缓冲区写入文件

**判断规则**：
- `grep -rn "\.kill()" src/` 命中但前方无 `terminate.*wait` → 违反三步协议
- 清理函数无 try/finally → 异常时引用不释放
- 清理函数无幂等保护 → 二次调用抛异常

---

### step 228：前端轮询四态契约与资源清理【强制】 🆕v4.46

228. **前端轮询四态契约与资源清理【强制】**
- 前端轮询必须处理四种状态（`waiting`/`success`/`failed`/`idle`），禁止只处理 success/failed 两态
- 轮询间隔通过 config.yaml `async_polling_pattern.interval_ms` 配置（默认 2500ms），禁止硬编码在组件中
- 轮询定时器引用必须存储在 `useRef` 中（`setInterval` 返回值），禁止存储在 state 中
- 必须在以下场景停止轮询并清理定时器：
  - `success` 状态：停止轮询，触发成功回调
  - `failed` 状态：停止轮询，展示错误信息
  - `idle` 状态：停止轮询，提示用户重新触发（服务端单例已重置）
  - 组件卸载：停止轮询（`useEffect` cleanup）
  - 网络异常：停止轮询，展示错误信息
- `waiting` 状态下可更新关键信息（如授权 URL 在 start 时未拿到、轮询时才拿到），使用 `prev ?? newValue` 避免覆盖已有值
- 轮询期间必须禁用触发按钮，展示 loading 状态，并显示可操作的关键信息（如授权链接）
- 组件卸载时必须通过 `useEffect` cleanup 调用停止轮询函数，防止卸载后 setState
- 历史教训：Named Tunnel login 轮询未在组件卸载时清理，导致卸载后仍调用 setState 触发 React 警告；未处理 idle 状态导致服务重启后无限轮询

**判断规则**：
- `grep -rn "setInterval" frontend/src/` 命中但无对应 `clearInterval` → 定时器泄漏
- 轮询分支只有 success/failed 两态 → 缺少 idle 兜底
- `setInterval` 返回值存储在 `useState` 而非 `useRef` → 每次渲染重新创建定时器
- 组件无 `useEffect` cleanup 调用 `clearInterval` → 卸载后定时器泄漏
