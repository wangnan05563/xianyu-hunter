# 智能客服 Agent Harness 重构概要设计说明书

| 项 | 内容 |
|---|---|
| 文档版本 | v1.1 |
| 文档日期 | 2026-07-02 |
| 文档状态 | 评审更新稿 |
| 所属项目 | 闲鱼猎人（XianyuHunter） |
| 文档类型 | 概要设计说明书（SDD） |
| 上游文档 | [智能客服-AgentHarness重构-需求规格.md](./智能客服-AgentHarness重构-需求规格.md) |
| 设计方案 | 增量 Harness 层 |
| 风险策略 | 写操作默认二次确认后执行 |

---

## 1. 引言

### 1.1 编写目的

本文档基于 Agent Harness 重构需求规格说明书，定义智能客服从现有 RAG/FAQ/只读 Agent 升级为可控执行智能体的概要设计。文档覆盖系统分层、模块边界、核心数据模型、接口契约、关键流程、安全控制、审计与测试策略，作为后续详细设计和编码实施依据。

本概要设计采用“增量 Harness 层”方案：保留现有智能客服对话链路，在 `ChatbotOrchestrator` 与工具执行之间增加 `AgentHarness`。模型仍负责理解、规划和解释；Harness 负责结构化计划、策略判断、确认门、工具执行、审计和结果汇总。

### 1.2 设计原则

1. **增量兼容**：不破坏现有 `/api/chatbot/chat`、RAG、FAQ、只读工具调用和会话历史。
2. **后端确认门**：二次确认必须在后端生效，前端确认卡片只做交互展示。
3. **模型不直接写业务**：LLM 输出只作为计划候选，必须转换成 `ActionPlan` 后由 Harness 校验。
4. **工具元数据驱动**：工具权限、风险、确认、超时、回滚能力均由元数据声明。
5. **审计优先**：所有计划、确认、取消、执行、失败和策略拦截都可追溯。
6. **可扩展**：新增工具或 Procedure 不修改 Agent 主循环，只注册工具和策略。

### 1.3 与现有设计关系

本设计是现有 [智能客服-概要设计.md](./智能客服-概要设计.md) 的增强版，不替代原 RAG/Agent 问答架构。原设计中的知识库、FAQ、上下文、SSE、配置页继续保留；新增设计聚焦执行型 Agent 的治理能力。

---

## 2. 总体架构

### 2.1 分层架构

```text
┌─────────────────────────────────────────────────────────────┐
│ 前端层                                                       │
│ Chatbot 页面 · ActionPlan 确认卡片 · 诊断报告卡片 · 工具管理页 │
│ 沙箱管理页 · SKILL 管理页                                    │
├─────────────────────────────────────────────────────────────┤
│ Web 层                                                       │
│ api_chatbot.py · api_chatbot_agent.py · api_chatbot_config.py │
├─────────────────────────────────────────────────────────────┤
│ Harness 层（新增）                                           │
│ agent_harness.py · action_planner.py · policy_engine.py       │
│ approval_gate.py · tool_executor.py · procedure_runner.py     │
│ audit_service.py · response_composer.py                       │
│ sandbox_manager.py · skill_manager.py                         │
├─────────────────────────────────────────────────────────────┤
│ 现有智能客服业务层                                           │
│ orchestrator · agent · rag_engine · faq_matcher · context     │
│ tool_registry · tools/read-only                              │
├─────────────────────────────────────────────────────────────┤
│ 业务能力适配层（新增工具）                                    │
│ config_tools · order_tools · log_tools · diagnose_procedures  │
│ skill_tools（命名空间化，沙箱内执行）                         │
├─────────────────────────────────────────────────────────────┤
│ 基础设施层                                                   │
│ repo_chatbot · repository · ai_usage · event_bus · logger     │
├─────────────────────────────────────────────────────────────┤
│ 数据层                                                       │
│ SQLite chatbot_* / agent_* · ChromaDB · run.stdout.log        │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 核心组件关系

```mermaid
flowchart TB
    UI[Chatbot 前端] --> CHAT[/POST /api/chatbot/chat/]
    UI --> PLAN[/POST /api/chatbot/agent/plan/]
    UI --> CONFIRM[/POST /api/chatbot/agent/confirm/]
    UI --> SBX[/沙箱管理接口/]
    UI --> SKILL[/SKILL 管理接口/]

    CHAT --> ORCH[ChatbotOrchestrator]
    PLAN --> H[AgentHarness]
    CONFIRM --> H
    ORCH --> H
    SBX --> SBM
    SKILL --> SKM

    subgraph "Agent Harness"
        H --> AP[ActionPlanner]
        AP --> PE[PolicyEngine]
        PE --> AG[ApprovalGate]
        AG --> TE[ToolExecutor]
        TE --> RC[ResponseComposer]
        H --> PR[ProcedureRunner]
        H --> AU[AuditService]
        H --> SBM[SandboxManager]
        H --> SKM[SkillManager]
        SBM -- 绑定校验/配额 --> TE
        SKM -- 命名空间注册 --> TR
        SKM -- 试运行 --> SBM
    end

    AP --> LLM[Agent / LLM]
    AP --> TR[ToolRegistry]
    TE --> TR
    TR --> RT[Read Tools]
    TR --> WT[Write Tools]
    TR --> SKT[Skill Tools 命名空间]
    PR --> RT
    PR --> WT

    WT --> CFG[Config API / Service]
    WT --> ORD[Order API / Buyer]
    RT --> LOGS[Logs API / Repo]
    RT --> REPO[Repository]

    SBM --> OVL[沙箱配置覆盖层]
    AU --> DB[(SQLite agent_* + chatbot_audit_logs)]
    SBM --> DB
    SKM --> DB
    RC --> UI
```

### 2.3 运行模式

| 模式 | 触发入口 | 行为 |
|---|---|---|
| 普通问答 | `/api/chatbot/chat` | 沿用现有 FAQ/RAG/Agent 流程。 |
| 只读诊断 | `/api/chatbot/chat` 或 `/api/chatbot/agent/procedures/{name}/run` | Harness 调用只读工具，直接返回诊断报告。 |
| 写操作计划 | `/api/chatbot/chat` 或 `/api/chatbot/agent/plan` | Harness 生成待确认 `ActionPlan`，不执行写入。 |
| 确认执行 | `/api/chatbot/agent/confirm` | 校验 token 与 payload hash，通过后执行工具并审计。 |
| 取消动作 | `/api/chatbot/agent/cancel` | 标记动作取消，记录审计，不执行业务写入。 |
| 沙箱模式 | `/api/chatbot/agent/sandboxes*` | 建立/卸载/快照/重置沙箱，工具调用绑定 sandbox_id，配置变更走覆盖层。 |
| SKILL 管理 | `/api/chatbot/agent/skills*` | 安装/升级/卸载/启停 SKILL，试运行在沙箱内，命名空间注册到 ToolRegistry。 |

---

## 3. 模块设计

### 3.1 `agent_harness.py`

**职责**：执行型 Agent 的总控入口，连接计划、策略、确认、执行和审计。

**核心接口**：

```python
class AgentHarness:
    async def plan(self, request: PlanRequest) -> HarnessResult:
        """生成回答、诊断报告或待确认 ActionPlan。"""

    async def confirm(self, request: ConfirmRequest) -> ActionExecutionResult:
        """确认并执行待确认动作。"""

    async def cancel(self, action_id: str, user_id: str) -> ActionCancelResult:
        """取消待确认动作。"""

    async def get_action(self, action_id: str, user_id: str) -> AgentAction:
        """查询动作详情与执行状态。"""
```

**设计要点**：

- `AgentHarness` 不直接调用业务 API，所有业务能力通过 `ToolExecutor`。
- `plan()` 返回三类结果：`answer`、`diagnostic_report`、`action_plan`。
- `confirm()` 必须重新加载数据库中的 action，校验状态、过期时间、用户、session 和 payload hash。
- 任意异常转为结构化错误，并交给 `AuditService` 记录。

### 3.2 `action_planner.py`

**职责**：把用户自然语言意图转换为结构化计划。

**输入**：

- 用户消息
- 会话上下文
- RAG 检索结果
- 可用工具元数据
- 当前系统状态摘要

**输出**：

- `ActionPlan`：写操作待确认计划
- `DiagnosticPlan`：诊断 Procedure 执行计划
- `AnswerPlan`：普通回答计划

**设计要点**：

- LLM 只能输出 JSON 结构候选，候选必须通过 Pydantic 校验。
- 如果 JSON 校验失败，降级为普通 RAG 回答，不执行工具。
- `ActionPlanner` 不决定是否允许执行，只生成候选计划。
- 对配置修改等常见意图优先使用规则解析，LLM 作为兜底。

### 3.3 `policy_engine.py`

**职责**：对计划做权限、风险和安全策略判断。

**策略维度**：

| 维度 | 判断依据 |
---|---|
| 工具开关 | 工具是否启用，是否在当前配置允许列表。 |
| 权限 | 当前用户是否具备 `read`、`diagnose`、`write_config`、`order`、`admin`。 |
| 风险 | 工具 `risk_level` 与 payload 内容综合判断。 |
| 确认 | `requires_confirmation` 是否为 true，风险是否至少 medium。 |
| Prompt Injection | 用户输入是否命中注入模式。 |
| 数据敏感性 | payload 或 observation 是否包含敏感字段。 |

**输出**：

```python
class PolicyDecision(BaseModel):
    allowed: bool
    requires_confirmation: bool
    risk_level: Literal["low", "medium", "high", "critical"]
    reasons: list[str]
    blocked_code: str | None = None
```

**设计要点**：

- `critical` 工具默认 `allowed=false`，除非管理员显式开启。
- 命中 Prompt Injection 且计划包含写工具时，直接阻断。
- 写工具即使工具元数据误配为无需确认，策略层也强制确认。

### 3.4 `approval_gate.py`

**职责**：生成、校验和消费二次确认 token。

**确认 token 设计**：

```text
confirmation_token = base64url(
  action_id + "." + expires_at + "." + hmac_sha256(secret, canonical_payload)
)
```

`canonical_payload` 包含：

- action_id
- user_id
- session_id
- tool_name
- payload_hash
- expires_at

**设计要点**：

- token 默认 5 分钟过期。
- token 一次性使用，确认成功后 action 状态变为 `running` 或 `succeeded`。
- payload 执行前重新计算 hash，hash 不一致则拒绝执行。
- 使用 `hmac.compare_digest()` 比较签名。

### 3.5 `tool_executor.py`

**职责**：统一执行工具、超时控制、脱敏、错误包装和 observation 收集。

**执行流程**：

1. 从 `ToolRegistry` 获取工具实例和元数据。
2. 校验工具启用状态。
3. 对 payload 做 schema 校验。
4. 执行工具，应用 `asyncio.timeout(tool.timeout_sec)`。
5. 对结果做敏感字段脱敏。
6. 写入 `agent_tool_calls`。
7. 返回 `ToolObservation`。

**设计要点**：

- 只读工具可在 plan 阶段执行。
- 写工具只能在 confirm 阶段执行。
- 工具异常不击穿 Harness，统一返回 `success=false`。
- 工具返回给 LLM 的 observation 必须是脱敏版本。

### 3.6 `procedure_runner.py`

**职责**：执行多步骤诊断流程。

**Procedure 定义**：

```python
class ProcedureDefinition(BaseModel):
    name: str
    description: str
    input_schema: dict
    steps: list[ProcedureStep]
    output_schema: dict
    failure_policy: Literal["continue", "stop"]
```

**首批 Procedure**：

| Procedure | 关键步骤 |
---|---|
| `task_not_running` | 解析 task_id → 查任务状态 → 查调度事件 → 查依赖 → 汇总建议 |
| `order_failed` | 查商品 → 查评估 → 查订单 → 查 buyer 前置条件 → 查错误日志 |
| `login_cookie_invalid` | 查 Cookie 状态 → 查 AUTH/WAF 事件 → 查最近错误 → 给出修复步骤 |
| `config_anomaly` | 查当前配置 → 查最近审计 → 运行 preview 校验 → 给出回滚建议 |
| `ai_budget_issue` | 查 AI 配置 → 查用量 → 查 LLM 错误 → 给出降级建议 |

**设计要点**：

- Procedure 只由结构化步骤组成，不由 LLM 自由决定工具顺序。
- 步骤失败默认继续，诊断报告标记“不完整”。
- Procedure 可输出修复动作建议，但修复动作仍进入 `ActionPlan` 确认流程。

### 3.7 `audit_service.py`

**职责**：记录计划、确认、取消、执行、失败、策略拦截和工具调用审计。

**审计目标**：

- 用户能查“刚才 Agent 做了什么”。
- 管理员能查“谁通过 Agent 改了配置或触发下单”。
- 测试能断言写操作未确认前未执行。

**设计要点**：

- 继续保留 `chatbot_audit_logs`，新增更细粒度 `agent_*` 表。
- 对敏感 payload 只保存脱敏 JSON 和 hash。
- 每条审计记录关联 `request_id`，便于 `/api/logs/request/{request_id}` 聚合。

### 3.8 `response_composer.py`

**职责**：把计划、诊断结果或执行 observation 转为用户可读响应。

**输出类型**：

- 普通 Markdown 回答
- ActionPlan 卡片数据
- DiagnosticReport 卡片数据
- ExecutionResult 卡片数据

**设计要点**：

- 不把原始工具 JSON 直接展示给用户。
- 高风险动作必须展示影响范围和失败可能。
- 诊断报告必须包含证据摘要，不输出完整敏感日志。

### 3.9 `sandbox_manager.py`

**职责**：用户沙箱上下文的生命周期管理、资源配额、配置覆盖层、快照与重置，并向 `ToolExecutor` 提供绑定校验。

**核心接口**：

```python
class SandboxManager:
    async def create(self, user_id: str, quota: SandboxQuota) -> SandboxContext:
        """为 user_id 创建沙箱上下文，返回 sandbox_id 与初始配额。"""

    async def get(self, sandbox_id: str) -> SandboxContext | None:
        """查询沙箱状态、配额用量、生命周期。"""

    async def teardown(self, sandbox_id: str, keep_audit: bool = True) -> None:
        """卸载沙箱：清理覆盖层与临时数据，保留审计摘要。"""

    async def snapshot(self, sandbox_id: str) -> str:
        """对沙箱覆盖层与未确认动作打快照，返回 snapshot_id。"""

    async def reset(self, sandbox_id: str, snapshot_id: str | None) -> None:
        """回滚到快照或清空临时数据，保留已确认执行的全局副作用。"""

    async def check_binding(self, sandbox_id: str, user_id: str) -> bool:
        """校验 sandbox_id 与 user_id 绑定关系，供 ToolExecutor 调用。"""

    async def acquire_quota(self, sandbox_id: str, kind: str) -> None:
        """占用配额（并发动作/调用频率/存储），超额抛 QuotaExceeded。"""

    async def promote_overlay(self, sandbox_id: str) -> ActionPlan:
        """将沙箱配置覆盖层提升为全局配置变更计划，走标准确认流程。"""
```

**沙箱上下文模型**：

```python
class SandboxContext(BaseModel):
    sandbox_id: str
    user_id: str
    status: Literal["active", "suspended", "teardown"]
    quota: SandboxQuota
    overlay: dict[str, Any]            # 配置覆盖层（未提升到全局）
    allowed_tools: list[str]           # 授权工具子集
    created_at: datetime
    last_active_at: datetime
    idle_timeout_sec: int
```

**设计要点**：

- 沙箱是 Harness 在 `user_id` 维度上的强隔离边界，非可选装饰：`ToolExecutor` 执行任何工具前必须调用 `check_binding`，未通过则记录 `sandbox_binding_violation` 并拒绝。
- 配置覆盖层（overlay）是沙箱内 `config.preview` 的计算基准，仅在 `promote_overlay` 显式提升、并经过标准 `ActionPlan` 确认后才合并到全局 `config.yaml`，沙箱内绝不直接落盘。
- `ContextManager` 按 `sandbox_id` 分区管理会话历史与 RAG 检索片段，避免跨沙箱上下文串扰（对应 FR-SB-11）。
- 配额检查采用"先占后执行"：`acquire_quota` 成功才进入工具执行，失败抛 `QuotaExceeded` 由 Harness 转为 `SANDBOX_QUOTA_EXCEEDED`。
- 沙箱空闲超时由后台巡检任务卸载，卸载后 `sandbox_id` 不可复用，仅保留审计摘要。
- `SandboxManager` 不直接执行业务工具，只提供上下文与配额；业务执行仍走 `ToolExecutor`。

### 3.10 `skill_manager.py`

**职责**：SKILL 包解析、签名校验、Prompt Injection 校验、沙箱试运行、命名空间注册、版本管理与卸载。

**核心接口**：

```python
class SkillManager:
    async def install(
        self, source: SkillSource, sandbox_id: str, approver: str
    ) -> SkillInstallResult:
        """安装 SKILL：解析→签名校验→展示权限→试运行→注册。"""

    async def upgrade(
        self, skill_name: str, target_version: str, sandbox_id: str
    ) -> SkillInstallResult:
        """升级 SKILL，保留旧版本，失败自动回滚。"""

    async def uninstall(self, skill_name: str, version: str | None = None) -> None:
        """卸载 SKILL：清理 ToolRegistry 注册项，保留审计与 agent_actions。"""

    async def set_default(self, skill_name: str, version: str) -> None:
        """切换默认版本，需管理员确认并审计。"""

    async def enable(self, skill_name: str) -> None:
        """启用 SKILL，其工具重新进入 ToolRegistry 可见集。"""

    async def disable(self, skill_name: str) -> None:
        """禁用 SKILL，其工具从 ToolRegistry 可见集移除但保留注册。"""

    async def list_installed(self) -> list[SkillRecord]:
        """查询已安装 SKILL 及版本、状态、默认版本标记。"""
```

**SKILL manifest 模型**：

```python
class SkillManifest(BaseModel):
    name: str                          # 命名空间前缀，需匹配 ^[a-z][a-z0-9_]*$
    version: str                       # semver
    author: str
    permissions: list[str]             # 不允许 admin/critical
    risk_level: Literal["low", "medium", "high"]
    dependencies: list[str]            # 依赖的其它 SKILL
    resources: SkillResources          # 网络/文件/子进程声明
    tools: list[ToolSpec]
    procedures: list[ProcedureSpec]
    prompt_fragments: list[str]
    test_cases: list[TestCase]
    signature: str                     # 对 manifest canonical JSON 的签名
```

**安装流程**：

```mermaid
sequenceDiagram
    participant Admin as 管理员
    participant API as api_chatbot_agent
    participant SKM as SkillManager
    participant SBM as SandboxManager
    participant TR as ToolRegistry
    participant DB as SQLite

    Admin->>API: POST /skills/install (source, sandbox_id)
    API->>SKM: install(source, sandbox_id)
    SKM->>SKM: 解析 manifest + 校验签名
    alt 签名无效
        SKM-->>API: skill_signature_invalid
        SKM->>DB: 审计 skill_signature_invalid
    else Prompt Injection 命中
        SKM-->>API: skill_prompt_injection
        SKM->>DB: 审计 skill_prompt_injection
    else 校验通过
        SKM-->>Admin: 展示权限/风险/依赖/注册项
        Admin->>API: 确认安装
        API->>SKM: proceed
        SKM->>SBM: 在 sandbox_id 内试运行 test_cases
        alt test_cases 失败
            SKM-->>API: install_failed_dryrun
            SKM->>SBM: 清理试运行产物
        else test_cases 通过
            SKM->>TR: 命名空间注册 <skill>.<tool>
            SKM->>DB: 写 agent_skills + agent_skill_installations
            SKM-->>API: installed
        end
    end
```

**设计要点**：

- SKILL 工具一律以 `<skill_name>.<tool_name>` 命名空间注册，`ToolRegistry` 校验命名冲突，冲突时拒绝安装（对应 FR-SK-06）。
- 试运行必须在 `SkillManager.install` 传入的 `sandbox_id` 内执行，试运行产物不污染全局，失败时由 `SandboxManager.reset` 清理。
- `PolicyEngine` 对 SKILL 工具取"最严格策略合并"：系统默认策略与 SKILL 声明取严，SKILL 不得声明 admin/critical，此类声明降级为 high 并强制确认或拒绝安装（对应 SR-14）。
- 多版本共存：`agent_skills` 表以 `(skill_name, version)` 为唯一键，`is_default` 标记默认版本；`ToolRegistry` 只加载默认版本工具，切换默认版本需重新加载。
- 升级失败自动回滚：保留上一可用版本，回滚后恢复其 ToolRegistry 注册。
- 卸载只清理 `ToolRegistry` 注册项与 `ProcedureRunner` 定义，不删除 `agent_skills` 历史与 `agent_actions` 记录（对应 SR-15）。
- SKILL 的 prompt 片段在安装时经 `sanitizer.check_user_input_safety` 校验，命中注入模式拒绝安装。

---

## 4. 工具体系设计

### 4.1 工具元数据

现有 `BaseTool` 增加元数据字段，保持向后兼容。

```python
class ToolMetadata(BaseModel):
    name: str
    description: str
    category: Literal["read", "diagnose", "config", "order", "task", "admin", "skill"]
    permissions: list[str]
    risk_level: Literal["low", "medium", "high", "critical"]
    requires_confirmation: bool
    dry_run_supported: bool = False
    rollback_supported: bool = False
    timeout_sec: int = 5
    enabled: bool = True
    skill_source: str | None = None     # SKILL 工具标记来源 SKILL 名与版本，系统工具为 None
    sandbox_only: bool = False          # 是否仅限沙箱内调用（SKILL 工具默认 True）
```

兼容策略：

- 旧工具未声明 `risk_level` 时默认为 `low`。
- 旧工具 `permissions=["read"]` 时默认不需要确认。
- 新增写工具必须声明非 read 权限，缺省 `requires_confirmation=true`。

### 4.2 工具分类

| 分类 | 工具示例 | 执行阶段 |
---|---|---|
| read | `task_status.get`、`eval_score.get`、`config_value.get` | plan 可执行 |
| diagnose | `logs.search`、`logs.request_chain` | plan 可执行 |
| config | `config.preview`、`config.save`、`config.rollback` | preview 可执行，save/rollback 需 confirm |
| order | `order.precheck`、`order.manual_takeover` | precheck 可执行，manual_takeover 需 confirm |
| task | `task.status_update`、`task.pause`、`task.resume` | 需 confirm |
| admin | `db.cleanup`、`vector.rebuild`、`tunnel.toggle` | 默认禁用或需 confirm |
| skill | `<skill>.<tool>`（命名空间化） | 仅在所属沙箱内执行，继承 SKILL 风险与确认策略 |

### 4.3 首批新增工具

| 工具 | 权限 | 风险 | 确认 | 底层复用 |
---|---|---|---|---|
| `config.preview` | read | low | 否 | `api_config.preview_config` 逻辑 |
| `config.save` | write_config | high | 是 | `api_config.save_config` 逻辑 |
| `config.rollback` | write_config | high | 是 | `api_config.rollback_config` 逻辑 |
| `logs.search` | diagnose | low | 否 | `repo.list_events` / `/api/logs/search` |
| `logs.request_chain` | diagnose | low | 否 | `repo.list_events_by_request` + `repo.list_error_logs` |
| `order.precheck` | read | low | 否 | `repo.get_item`、`repo.find_order_by_task_item`、CookieStore |
| `order.manual_takeover` | order | high | 是 | `api_orders.manual_takeover` 逻辑或 `Buyer.buy` 服务 |

### 4.4 写工具执行约束

- 写工具不得出现在普通 OpenAI function calling schema 中。
- `ToolRegistry.get_openai_schemas()` 默认只返回 read/diagnose 工具。
- 写工具仅通过 `ToolExecutor.execute_confirmed()` 调用。
- 写工具执行前必须存在 `agent_actions.status="confirmed"` 或 `running`。
- 沙箱模式下所有工具调用必须携带 `sandbox_id`，`ToolExecutor` 调用 `SandboxManager.check_binding` 校验绑定，未通过拒绝并记录 `sandbox_binding_violation`。
- SKILL 工具（`category="skill"`）默认 `sandbox_only=True`，仅能在所属沙箱内调用；`get_openai_schemas()` 对非沙箱会话不返回 SKILL 工具。
- SKILL 工具的 `risk_level` 由 `PolicyEngine` 取系统策略与 SKILL 声明的最严格值，确认策略不得低于 high。

---

## 5. 数据模型设计

### 5.1 新增表

#### 5.1.1 `agent_actions`

记录用户可确认动作。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | TEXT PK | action_id，UUID32 或 `act_` 前缀 |
| session_id | TEXT | 关联客服会话 |
| user_id | TEXT | 默认 `default`，预留多用户 |
| title | TEXT | 动作标题 |
| tool_name | TEXT | 工具名 |
| risk_level | TEXT | low/medium/high/critical |
| status | TEXT | planned/confirmed/running/succeeded/failed/cancelled/expired |
| payload_json | TEXT | 脱敏 payload |
| payload_hash | TEXT | 原始 payload canonical JSON 的 SHA256 |
| diffs_json | TEXT | 配置或状态变更 diff |
| impact_json | TEXT | 影响说明 |
| rollback_json | TEXT | 回滚信息 |
| confirmation_expires_at | DATETIME | token 过期时间 |
| confirmed_at | DATETIME | 确认时间 |
| executed_at | DATETIME | 执行开始时间 |
| finished_at | DATETIME | 执行结束时间 |
| result_json | TEXT | 脱敏执行结果 |
| error_code | TEXT | 失败错误码 |
| request_id | TEXT | 全局流水号 |
| sandbox_id | TEXT | 沙箱模式必填，非沙箱模式为空 |
| skill_source | TEXT | SKILL 工具调用时记录来源 SKILL 名与版本，系统工具为空 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

索引：

- `ix_agent_actions_session_created(session_id, created_at)`
- `ix_agent_actions_status_created(status, created_at)`
- `ix_agent_actions_request_id(request_id)`
- `ix_agent_actions_sandbox(sandbox_id, created_at)`

#### 5.1.2 `agent_action_steps`

记录 Procedure 或多工具执行步骤。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | 自增 |
| action_id | TEXT | 关联 agent_actions.id，可为空用于纯诊断 |
| procedure_name | TEXT | Procedure 名称 |
| step_name | TEXT | 步骤名 |
| tool_name | TEXT | 调用工具 |
| status | TEXT | pending/running/succeeded/failed/skipped |
| input_hash | TEXT | 输入 hash |
| output_json | TEXT | 脱敏输出 |
| error_message | TEXT | 错误摘要 |
| duration_ms | INTEGER | 耗时 |
| created_at | DATETIME | 创建时间 |

索引：

- `ix_agent_action_steps_action(action_id, id)`
- `ix_agent_action_steps_procedure(procedure_name, created_at)`

#### 5.1.3 `agent_tool_calls`

记录每次工具调用。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | 自增 |
| action_id | TEXT | 关联动作，可为空 |
| session_id | TEXT | 会话 |
| tool_name | TEXT | 工具名 |
| permissions_json | TEXT | 权限快照 |
| risk_level | TEXT | 风险快照 |
| success | INTEGER | 0/1 |
| duration_ms | INTEGER | 耗时 |
| input_hash | TEXT | 输入 hash |
| output_hash | TEXT | 输出 hash |
| error_code | TEXT | 错误码 |
| request_id | TEXT | 流水号 |
| sandbox_id | TEXT | 沙箱调用必填，非沙箱为空 |
| skill_source | TEXT | SKILL 工具调用时记录来源，系统工具为空 |
| created_at | DATETIME | 创建时间 |

索引：

- `ix_agent_tool_calls_tool_created(tool_name, created_at)`
- `ix_agent_tool_calls_session_created(session_id, created_at)`
- `ix_agent_tool_calls_request_id(request_id)`
- `ix_agent_tool_calls_sandbox(sandbox_id, created_at)`

#### 5.1.4 `agent_policy_events`

记录策略判断、阻断和风险升级。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | 自增 |
| session_id | TEXT | 会话 |
| action_id | TEXT | 动作 |
| event_type | TEXT | allowed/blocked/risk_upgraded/confirmation_required |
| reason_code | TEXT | 原因码 |
| message | TEXT | 说明 |
| request_id | TEXT | 流水号 |
| created_at | DATETIME | 创建时间 |

#### 5.1.5 `agent_sandboxes`

记录沙箱上下文生命周期与配额。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | TEXT PK | sandbox_id，UUID32 |
| user_id | TEXT | 绑定用户 |
| status | TEXT | active/suspended/teardown |
| quota_json | TEXT | 配额配置（并发动作/调用频率/存储上限） |
| usage_json | TEXT | 当前配额用量快照 |
| allowed_tools_json | TEXT | 授权工具子集 |
| idle_timeout_sec | INTEGER | 空闲超时秒数 |
| last_active_at | DATETIME | 最近活动时间 |
| teardown_at | DATETIME | 卸载时间，卸载后不可复用 |
| request_id | TEXT | 创建时流水号 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

索引：

- `ix_agent_sandboxes_user_status(user_id, status)`
- `ix_agent_sandboxes_last_active(last_active_at)`

#### 5.1.6 `agent_sandbox_overlays`

记录沙箱配置覆盖层（未提升到全局的临时配置 diff）。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | 自增 |
| sandbox_id | TEXT | 关联沙箱 |
| path | TEXT | 配置路径，如 `eval.pass_score` |
| op | TEXT | modify/add/delete |
| old_value | TEXT | 脱敏旧值 |
| new_value | TEXT | 脱敏新值 |
| promoted | INTEGER | 0/1，是否已提升到全局 |
| created_at | DATETIME | 创建时间 |

索引：

- `ix_agent_sandbox_overlays_sandbox(sandbox_id, path)`
- `ix_agent_sandbox_overlays_promoted(promoted)`

#### 5.1.7 `agent_sandbox_snapshots`

记录沙箱快照（覆盖层与未确认动作的不可变副本）。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | TEXT PK | snapshot_id |
| sandbox_id | TEXT | 关联沙箱 |
| overlay_json | TEXT | 快照时刻覆盖层深拷贝 |
| pending_action_ids_json | TEXT | 快照时刻未确认动作列表 |
| created_by | TEXT | 操作人 |
| created_at | DATETIME | 创建时间 |

索引：

- `ix_agent_sandbox_snapshots_sandbox(sandbox_id, created_at)`

#### 5.1.8 `agent_skills`

记录已安装 SKILL 及版本。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | 自增 |
| skill_name | TEXT | SKILL 名，命名空间前缀 |
| version | TEXT | semver 版本 |
| manifest_json | TEXT | 完整 manifest（含脱敏后字段） |
| signature | TEXT | 签名 |
| status | TEXT | installed/enabled/disabled/uninstalled |
| is_default | INTEGER | 0/1，是否默认版本 |
| installed_by | TEXT | 安装人 |
| installed_at | DATETIME | 安装时间 |
| uninstalled_at | DATETIME | 卸载时间 |

索引：

- `ix_agent_skills_name_version(skill_name, version)` 唯一
- `ix_agent_skills_name_default(skill_name, is_default)`
- `ix_agent_skills_status(status)`

#### 5.1.9 `agent_skill_installations`

记录 SKILL 安装/升级/卸载/启停审计事件。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | 自增 |
| skill_name | TEXT | SKILL 名 |
| version | TEXT | 目标版本 |
| operation | TEXT | install/upgrade/uninstall/enable/disable/set_default |
| before_status | TEXT | 操作前状态 |
| after_status | TEXT | 操作后状态 |
| operator | TEXT | 操作人 |
| reason_code | TEXT | 成功/失败原因码 |
| request_id | TEXT | 流水号 |
| created_at | DATETIME | 创建时间 |

索引：

- `ix_agent_skill_installations_skill(skill_name, created_at)`
- `ix_agent_skill_installations_request_id(request_id)`

### 5.2 与现有表关系

| 现有表 | 关系 |
---|---|
| `chatbot_sessions` | `agent_actions.session_id` 关联会话。 |
| `chatbot_messages` | ActionPlan 可作为 assistant 消息 metadata 保存。 |
| `chatbot_audit_logs` | 保留旧审计，Agent 执行动作同步写摘要审计。 |
| `events` / `error_logs` | 通过 request_id 与 Agent 动作关联。 |
| `orders` | 下单工具执行后读取或写入订单状态。 |
| `tasks` / `items` / `evaluations` | 下单前置检查和诊断工具读取。 |
| `agent_actions` / `agent_tool_calls` | 新增 `sandbox_id` 字段关联 `agent_sandboxes`，SKILL 工具调用额外记录 `skill_source`。 |
| `agent_sandboxes` | 通过 `user_id` 与多用户体系关联，沙箱内动作与工具调用均回写 `sandbox_id`。 |
| `agent_skills` | SKILL 工具的 `skill_source` 关联 `agent_skills(skill_name, version)`，卸载后历史调用保留可查。 |

### 5.3 迁移策略

- 新增表通过 `Base.metadata.create_all(engine)` 创建。
- 已有数据库使用 `_migrate_add_column` 风格补建缺失列。
- 不修改现有 `chatbot_*` 表字段，避免影响已上线客服功能。
- `ChatbotRepository` 可扩展 Agent CRUD，也可新增 `AgentRepository`；推荐新增 `AgentRepository`，降低 `repo_chatbot.py` 文件膨胀。

---

## 6. API 设计

### 6.1 路由文件

新增 `src/xianyu_hunter/web/routes/api_chatbot_agent.py`，前缀 `/api/chatbot/agent`。

### 6.2 端点清单

| 方法 | 路径 | 用途 |
---|---|---|
| POST | `/plan` | 生成普通回答、诊断报告或 ActionPlan |
| POST | `/confirm` | 确认并执行动作 |
| POST | `/cancel` | 取消动作 |
| GET | `/actions/{action_id}` | 查询动作状态 |
| GET | `/tools` | 查询工具目录 |
| GET | `/procedures` | 查询 Procedure 目录 |
| POST | `/procedures/{name}/run` | 运行诊断 Procedure |
| POST | `/sandboxes` | 创建沙箱上下文 |
| GET | `/sandboxes` | 查询沙箱列表与状态 |
| DELETE | `/sandboxes/{sandbox_id}` | 卸载沙箱 |
| POST | `/sandboxes/{sandbox_id}/snapshot` | 沙箱打快照 |
| POST | `/sandboxes/{sandbox_id}/reset` | 回滚到快照或清空临时数据 |
| POST | `/sandboxes/{sandbox_id}/promote` | 提升沙箱覆盖层到全局（走确认流程） |
| POST | `/skills/install` | 安装 SKILL（本地导入或市场 URL） |
| GET | `/skills` | 查询已安装 SKILL |
| GET | `/skills/{skill_name}` | 查询 SKILL 详情 |
| DELETE | `/skills/{skill_name}` | 卸载 SKILL |
| POST | `/skills/{skill_name}/enable` | 启用 SKILL |
| POST | `/skills/{skill_name}/disable` | 禁用 SKILL |
| POST | `/skills/{skill_name}/upgrade` | 升级 SKILL |
| POST | `/skills/{skill_name}/default` | 切换默认版本 |
| GET | `/skills/{skill_name}/versions` | 查询历史版本 |

### 6.3 请求响应模型

#### `POST /plan`

请求：

```json
{
  "session_id": "uuid32-or-null",
  "message": "帮我把评分阈值调到85",
  "mode": "auto"
}
```

响应：

```json
{
  "type": "action_plan",
  "session_id": "uuid32",
  "action": {
    "id": "act_xxx",
    "title": "修改评估通过分",
    "tool_name": "config.save",
    "risk_level": "high",
    "requires_confirmation": true,
    "summary": "将 eval.pass_score 从 80 调整为 85",
    "diffs": [],
    "impact": [],
    "expires_at": "2026-07-01T18:05:00+08:00"
  },
  "confirmation_token": "opaque-token"
}
```

#### `POST /confirm`

请求：

```json
{
  "action_id": "act_xxx",
  "confirmation_token": "opaque-token"
}
```

响应：

```json
{
  "action_id": "act_xxx",
  "status": "succeeded",
  "result": {
    "ok": true,
    "backup": "config.yaml.bak.20260701-180110",
    "restart_required": true
  },
  "audit_event_id": 123
}
```

#### `POST /sandboxes`

请求：

```json
{
  "user_id": "user_001",
  "quota": {
    "max_pending_actions": 5,
    "max_calls_per_min": 30,
    "max_storage_kb": 10240
  },
  "allowed_tools": ["config.preview", "logs.search", "logs.request_chain"],
  "idle_timeout_sec": 1800
}
```

响应：

```json
{
  "sandbox_id": "sb_20260702_001",
  "user_id": "user_001",
  "status": "active",
  "expires_at": "2026-07-02T19:00:00+08:00"
}
```

#### `POST /skills/install`

请求：

```json
{
  "source": {"type": "local", "path": "/tmp/skill_pkg/price_analyzer"},
  "sandbox_id": "sb_20260702_001",
  "approver": "admin"
}
```

响应（待确认阶段）：

```json
{
  "stage": "approval_required",
  "manifest": {
    "name": "price_analyzer",
    "version": "1.2.0",
    "permissions": ["read", "diagnose"],
    "risk_level": "medium",
    "tools": ["price_analyzer.compare", "price_analyzer.history"]
  },
  "install_token": "opaque-install-token"
}
```

响应（安装完成）：

```json
{
  "stage": "installed",
  "skill_name": "price_analyzer",
  "version": "1.2.0",
  "is_default": true,
  "registered_tools": ["price_analyzer.compare", "price_analyzer.history"],
  "audit_event_id": 678
}
```

### 6.4 SSE 扩展

现有 `/api/chatbot/chat` SSE 增加事件：

| event | data |
---|---|
| `action_plan` | ActionPlan 卡片数据 |
| `action_required` | 需要确认的提醒 |
| `diagnostic_report` | 诊断报告 |
| `tool_observation` | 脱敏工具结果摘要 |
| `action_result` | 执行结果 |
| `sandbox_event` | 沙箱创建/卸载/重置/配额告警 |
| `skill_event` | SKILL 安装/升级/卸载/试运行进度 |

兼容性：旧前端忽略未知 SSE event，不影响普通聊天。

---

## 7. 关键流程

### 7.1 配置修改流程

```mermaid
sequenceDiagram
    participant U as 用户
    participant UI as 前端
    participant API as api_chatbot_agent
    participant H as AgentHarness
    participant P as ActionPlanner
    participant PE as PolicyEngine
    participant AG as ApprovalGate
    participant EX as ToolExecutor
    participant CFG as ConfigTool
    participant DB as SQLite

    U->>UI: 帮我把评分阈值调到 85
    UI->>API: POST /plan
    API->>H: plan()
    H->>P: 解析配置修改意图
    P->>CFG: config.preview(dry_run)
    CFG-->>P: diff + validation
    P->>PE: evaluate(ActionPlan)
    PE-->>P: requires_confirmation=true, risk=high
    H->>DB: 保存 agent_actions(planned)
    H->>AG: issue_token(action_id, payload_hash)
    H-->>API: ActionPlan + token
    API-->>UI: 确认卡片

    U->>UI: 确认修改
    UI->>API: POST /confirm
    API->>H: confirm()
    H->>AG: verify_and_consume_token()
    AG-->>H: ok
    H->>EX: execute(config.save)
    EX->>CFG: save_config(dry_run=false)
    CFG-->>EX: saved + backup
    EX->>DB: 记录 tool_call
    H->>DB: 更新 action=succeeded
    H-->>API: ExecutionResult
    API-->>UI: 结果卡片
```

### 7.2 智能下单流程

```mermaid
sequenceDiagram
    participant U as 用户
    participant H as AgentHarness
    participant PR as ProcedureRunner
    participant EX as ToolExecutor
    participant ORD as OrderTool
    participant DB as Repository
    participant Buyer as Buyer

    U->>H: 帮我下这个商品
    H->>PR: order_precheck(item_id)
    PR->>DB: 查询 item/task/evaluation/order
    PR->>ORD: 检查 buyer 注入、Cookie、重复订单、商品状态
    ORD-->>PR: precheck report
    PR-->>H: 下单建议
    H->>H: 生成 high risk ActionPlan
    H-->>U: 展示商品/价格/评分/风险/确认按钮

    U->>H: 确认触发下单
    H->>EX: execute(order.manual_takeover)
    EX->>ORD: manual_takeover(payload)
    ORD->>Buyer: buyer.buy(...)
    Buyer-->>ORD: success / skipped_duplicate / error
    ORD-->>EX: ToolObservation
    EX-->>H: ExecutionResult
    H-->>U: 订单结果与后续接管提示
```

### 7.3 日志诊断流程

```mermaid
flowchart TB
    A[用户描述问题或提供 request_id] --> B[ActionPlanner 判断诊断意图]
    B --> C{有 request_id?}
    C -- 是 --> D[logs.request_chain]
    C -- 否 --> E[logs.search 按 task_id/time/level/q 检索]
    D --> F[ProcedureRunner 聚合 events + error_logs]
    E --> F
    F --> G[提取异常点与时间线]
    G --> H[ResponseComposer 生成诊断报告]
    H --> I{有建议修复动作?}
    I -- 否 --> J[返回诊断报告]
    I -- 是 --> K[生成可确认 ActionPlan]
    K --> J
```

### 7.4 确认 token 校验流程

```mermaid
flowchart LR
    A[POST /confirm] --> B[读取 action]
    B --> C{状态 planned?}
    C -- 否 --> X[拒绝]
    C -- 是 --> D{未过期?}
    D -- 否 --> X
    D -- 是 --> E[重算 payload_hash]
    E --> F{hash 一致?}
    F -- 否 --> X
    F -- 是 --> G[验证 HMAC]
    G --> H{签名有效?}
    H -- 否 --> X
    H -- 是 --> I[标记 confirmed/running]
    I --> J[执行工具]
```

### 7.5 沙箱配置覆盖与提升流程

```mermaid
flowchart TB
    A[沙箱用户提出配置修改] --> B[ActionPlanner 生成建议型 ActionPlan]
    B --> C[config.preview 基于沙箱 overlay 计算 diff]
    C --> D{用户在沙箱内确认?}
    D -- 取消 --> E[仅记录沙箱临时动作]
    D -- 确认 --> F[写入 agent_sandbox_overlays<br/>不落盘全局 config.yaml]
    F --> G[沙箱内后续 preview 基于 overlay 叠加]

    H[管理员发起 promote] --> I[SandboxManager.promote_overlay]
    I --> J[生成全局配置变更 ActionPlan<br/>risk=high]
    J --> K{管理员二次确认?}
    K -- 否 --> L[放弃提升，overlay 保留]
    K -- 是 --> M[ToolExecutor 执行 config.save]
    M --> N[overlay 标记 promoted]
    N --> O[全局 config.yaml 更新 + 审计]
```

要点：沙箱内配置变更默认不触达全局；只有显式 `promote` 并经过标准 `ActionPlan` 确认后才合并到全局配置，确保沙箱隔离与全局安全执行底座不冲突。

---

## 8. 集成设计

### 8.1 容器集成

当前 `container.chatbot` 是 dict 子容器，新增 Harness 组件继续放入该 dict。

```python
agent_repo = AgentRepository(container.repo.engine)
tool_registry = ToolRegistry(...)
policy_engine = PolicyEngine(config=cfg.agent_harness)
approval_gate = ApprovalGate(secret=settings.app_secret)
sandbox_manager = SandboxManager(agent_repo, config=cfg.agent_harness.sandbox)
# ToolExecutor 注入 sandbox_manager，沙箱模式下强制绑定校验与配额
tool_executor = ToolExecutor(tool_registry, agent_repo, sandbox_manager)
skill_manager = SkillManager(tool_registry, sandbox_manager, agent_repo, config=cfg.agent_harness.skill)
procedure_runner = ProcedureRunner(tool_executor, definitions=...)
audit_service = AuditService(agent_repo, chatbot_repo, event_bus)
agent_harness = AgentHarness(
    planner=ActionPlanner(agent, rag_engine, tool_registry),
    policy_engine=policy_engine,
    approval_gate=approval_gate,
    tool_executor=tool_executor,
    procedure_runner=procedure_runner,
    audit_service=audit_service,
    sandbox_manager=sandbox_manager,
    skill_manager=skill_manager,
)

return {
    ...
    "agent_repo": agent_repo,
    "agent_harness": agent_harness,
    "sandbox_manager": sandbox_manager,
    "skill_manager": skill_manager,
}
```

### 8.2 Orchestrator 集成

`ChatbotOrchestrator` 增加可选 `agent_harness` 依赖。

- 普通问答仍走现有流程。
- 当 `intent.suggested_action` 属于 `config_update`、`order_request`、`diagnose` 时，转交 Harness。
- Harness 返回 `action_plan` 时，Orchestrator 以 SSE `action_plan` 事件输出。
- Harness 不可用时，降级为现有 RAG 回答。

### 8.3 路由注册

在 `startup.py` 注册：

```python
from xianyu_hunter.web.routes import api_chatbot_agent

app.include_router(api_chatbot_agent.router)
```

### 8.4 配置扩展

在 `ChatbotConfig` 下增加：

```yaml
chatbot:
  agent_harness:
    enabled: true
    confirmation_ttl_sec: 300
    allow_write_tools: true
    allow_order_tools: true
    allow_admin_tools: false
    max_action_payload_bytes: 20000
    prompt_injection_block_write: true
    sandbox:
      enabled: false                     # 沙箱模式总开关，默认关闭保持单用户兼容
      default_idle_timeout_sec: 1800
      default_quota:
        max_pending_actions: 5
        max_calls_per_min: 30
        max_storage_kb: 10240
      max_lifetime_sec: 86400            # 单沙箱最大存活时长
      enforce_binding: true              # ToolExecutor 强制绑定校验
    skill:
      allow_skill_install: true          # SKILL 安装总开关
      allowed_market_urls: []            # 官方市场白名单
      require_signature: true            # 强制签名校验
      require_dryrun: true               # 强制沙箱试运行
      default_risk_level: high           # SKILL 缺省风险
      deny_admin_critical: true          # 拒绝 admin/critical 声明
```

---

## 9. 安全设计

### 9.1 写操作隔离

- 普通 Agent function calling schema 只暴露 read/diagnose 工具。
- 写工具不进入 LLM 可直接调用列表。
- 写工具只能由 `ToolExecutor.execute_confirmed()` 调用。
- `execute_confirmed()` 必须要求 action 状态已确认。

### 9.2 脱敏策略

脱敏分三层：

1. 工具返回层：`ToolRegistry` / `ToolExecutor` 递归脱敏。
2. 审计存储层：保存 redacted payload 和 hash。
3. 前端展示层：确认卡片和诊断报告不展示完整敏感值。

敏感 key 包括：`api_key`、`openai_key`、`cookie`、`token`、`password`、`secret`、`webhook_url`、`authorization`、`bearer`。

### 9.3 权限失败

权限失败返回结构化错误：

```json
{
  "code": "AGENT_POLICY_DENIED",
  "message": "当前能力需要 order 权限，已阻止执行",
  "reasons": ["tool_permission_denied"]
}
```

### 9.4 审计不可绕过

- `AgentHarness.confirm()` 在执行前后都写审计。
- `ToolExecutor` 每次工具调用都写 `agent_tool_calls`。
- 写审计失败时，写工具不得继续执行，返回 `AUDIT_WRITE_FAILED`。

### 9.5 沙箱隔离

- `ToolExecutor` 执行工具前调用 `SandboxManager.check_binding(sandbox_id, user_id)`，未通过返回 `sandbox_binding_violation`，不执行工具。
- 沙箱配置覆盖层只存在于 `agent_sandbox_overlays` 与内存，`config.preview` 在沙箱上下文中叠加 overlay 计算 diff，绝不直接写全局 `config.yaml`。
- 覆盖层提升到全局必须经 `promote_overlay` 生成 `risk=high` 的 `ActionPlan`，走标准确认门与 HMAC token 校验。
- `ContextManager` 按 `sandbox_id` 分区管理会话历史与 RAG 检索片段，跨沙箱读取被拒绝。
- 沙箱配额在 `ToolExecutor` 与 `AgentHarness.plan()` 前置检查，超额返回 `SANDBOX_QUOTA_EXCEEDED`，不进入工具执行。
- 沙箱卸载后 `sandbox_id` 不可复用，临时数据清理，审计摘要与已确认全局副作用保留。

### 9.6 SKILL 安全

- SKILL 安装三道关卡：签名校验（`require_signature`）→ Prompt Injection 校验（`sanitizer.check_user_input_safety`）→ 沙箱试运行（`require_dryrun`），任一失败拒绝安装。
- SKILL 工具命名空间化 `<skill>.<tool>`，`ToolRegistry.register` 校验冲突，冲突拒绝安装。
- SKILL 不得声明 admin/critical 权限，`SkillManager` 对此类声明降级为 high 或拒绝安装；`PolicyEngine` 对 SKILL 工具取系统策略与 SKILL 声明的最严格值。
- SKILL 工具默认 `sandbox_only=True`，非沙箱会话的 `get_openai_schemas()` 不返回 SKILL 工具，LLM 无法在非沙箱上下文直接调用。
- SKILL 工具的 observation 进入 LLM 前必须脱敏，脱敏策略与系统工具一致（复用 `ToolRegistry._filter_sensitive`）。
- SKILL 卸载只清理 `ToolRegistry` 注册项，不删除 `agent_skills` 历史与 `agent_actions`，保证审计可追溯。
- `allow_skill_install=false` 时所有 SKILL 安装相关接口返回 403，已安装 SKILL 保持可用但不可新增/升级。

---

## 10. 错误处理与降级

| 场景 | 处理 |
---|---|
| Planner 输出非法 JSON | 降级为普通 RAG 回答，记录 `planner_parse_failed`。 |
| 策略阻断 | 返回阻断说明，不执行工具。 |
| confirmation_token 过期 | action 标记 expired，返回重新生成计划提示。 |
| payload hash 不一致 | 拒绝执行，记录高风险审计。 |
| 工具超时 | action 标记 failed，返回可重试建议。 |
| 配置 preview 校验失败 | 不生成确认 token，直接展示校验错误。 |
| 下单前置检查失败 | 不生成下单确认卡，展示修复步骤。 |
| 审计写入失败 | 阻断写工具执行。 |
| Harness 初始化失败 | `/api/chatbot/chat` 降级回旧 RAG/FAQ 流程。 |
| 沙箱绑定校验失败 | 拒绝工具调用，记录 `sandbox_binding_violation`，返回隔离错误。 |
| 沙箱配额超额 | 返回 `SANDBOX_QUOTA_EXCEEDED`，不执行超额动作，提示管理员调配额。 |
| 沙箱空闲超时 | 后台巡检自动卸载，保留审计摘要，sandbox_id 不可复用。 |
| SKILL 签名校验失败 | 拒绝安装，记录 `skill_signature_invalid`，不写入 ToolRegistry。 |
| SKILL Prompt Injection 命中 | 拒绝安装，记录 `skill_prompt_injection`，清理已下载包。 |
| SKILL 试运行失败 | 拒绝正式注册，清理沙箱试运行产物，返回失败用例摘要。 |
| SKILL 升级失败 | 自动回滚到上一可用版本，记录 `skill_upgrade_rolled_back`。 |
| SKILL 工具运行时异常 | 与系统工具一致由 `ToolExecutor` 捕获，返回 `success=false`，不击穿 Harness。 |

---

## 11. 前端概要设计

### 11.1 ActionPlan 确认卡片

字段：

- 标题
- 风险等级 tag
- 动作摘要
- diff 表格
- 影响说明
- 可回滚说明
- 过期倒计时
- 确认/取消按钮

交互：

- 确认按钮调用 `/api/chatbot/agent/confirm`。
- 取消按钮调用 `/api/chatbot/agent/cancel`。
- 过期后按钮禁用，提示重新生成计划。
- 执行中显示 loading，不允许重复点击。

### 11.2 诊断报告卡片

字段：

- 诊断结论
- 检查项
- 时间线
- 证据摘要
- 建议动作
- 可确认修复入口

### 11.3 工具管理页

位置：现有智能客服配置页新增“Agent Harness”Tab。

展示：

- 工具名
- 分类
- 权限
- 风险等级
- 是否启用
- 是否需要确认
- 最近调用成功率
- 来源（系统 / SKILL 名+版本，SKILL 工具标记命名空间）

### 11.4 沙箱管理页

位置：Agent Harness Tab 下新增"沙箱"子页（仅管理员可见）。

展示：

- 沙箱列表：sandbox_id、user_id、状态、配额用量、最近活动时间、空闲超时倒计时
- 沙箱详情：授权工具子集、配置覆盖层 diff、未确认动作列表、快照列表
- 操作：创建、卸载、打快照、回滚到快照、清空临时数据、提升覆盖层到全局（跳转确认卡片）

交互：

- 提升覆盖层生成 `risk=high` 的 ActionPlan 确认卡片，走标准确认流程。
- 卸载高危操作需二次确认，提示"将清理临时数据，保留审计"。
- 配额用量接近上限以警告色提示。

### 11.5 SKILL 管理页

位置：Agent Harness Tab 下新增"SKILL"子页（仅管理员可见）。

展示：

- 已安装 SKILL 列表：名称、版本、状态、默认版本标记、来源、安装时间
- SKILL 详情：manifest 摘要（权限、风险、依赖、资源声明）、注册工具/Procedure 列表、安装审计历史、历史版本
- 安装入口：本地导入、市场 URL 安装（市场地址受白名单约束）

交互：

- 安装分阶段展示：校验中 → 待确认（展示权限清单）→ 试运行中 → 安装完成/失败。
- 升级展示版本对比与回滚提示。
- 卸载高危操作需二次确认，提示"将清理工具注册，保留历史审计"。
- `allow_skill_install=false` 时安装入口置灰禁用。

---

## 12. 测试策略

### 12.1 单元测试

| 模块 | 测试重点 |
---|---|
| `PolicyEngine` | 权限、风险升级、Prompt Injection 阻断、SKILL 工具最严格策略合并 |
| `ApprovalGate` | token 签发、过期、篡改、一次性消费 |
| `ActionPlanner` | 配置修改解析、非法 JSON 降级、沙箱内建议型计划生成 |
| `ToolExecutor` | 超时、异常、脱敏、写工具确认门、沙箱绑定校验、配额占用 |
| `ProcedureRunner` | 成功、部分失败、权限不足 |
| `SandboxManager` | 创建/卸载/快照/重置、配额超额、绑定校验、覆盖层提升、空闲超时卸载 |
| `SkillManager` | 签名校验、Prompt Injection 拒绝、试运行失败、命名空间冲突、升级回滚、卸载保留审计 |

### 12.2 集成测试

- `/api/chatbot/agent/plan` 生成配置修改 ActionPlan。
- 未确认前配置文件不变化。
- `/confirm` 后配置写入并返回 backup。
- 重复 confirm 被拒绝。
- 下单前置检查失败时不生成可执行下单动作。
- request_id 日志诊断返回脱敏报告。
- 沙箱内配置修改不落盘全局，`promote` 后经确认才写入全局。
- 跨沙箱工具调用被拒绝并记录 `sandbox_binding_violation`。
- 沙箱配额超额返回 `SANDBOX_QUOTA_EXCEEDED`。
- 未签名 SKILL 安装被拒绝并记录 `skill_signature_invalid`。
- SKILL 试运行失败不注册到 ToolRegistry，沙箱产物被清理。
- SKILL 工具以 `<skill>.<tool>` 命名空间注册，卸载后不可调用但历史可查。

### 12.3 回归测试

- 现有 `tests/test_chatbot_*` 继续通过。
- 禁用 `chatbot.agent_harness.enabled` 后，现有 RAG/FAQ 对话不受影响。
- 禁用 `agent_harness.sandbox.enabled` 后，单用户流程与现有 Harness 行为一致。
- 禁用 `agent_harness.skill.allow_skill_install` 后，已安装 SKILL 仍可用但安装接口返回 403。
- 旧前端忽略新增 SSE event 时不报错。

---

## 13. 实施分期

| 阶段 | 范围 | 交付物 |
---|---|---|
| Phase 1 | Harness 骨架、ActionPlan、PolicyEngine、ApprovalGate、AgentRepository | 可生成和确认空动作，审计闭环可用 |
| Phase 2 | 配置 preview/save/rollback 工具、确认卡片 | 可通过 Agent 安全修改配置 |
| Phase 3 | 日志 search/request_chain 工具、诊断报告卡片 | 可读取后台日志并输出诊断报告 |
| Phase 4 | 下单 precheck/manual_takeover 工具 | 可确认后触发手动抢单 |
| Phase 5 | ProcedureRunner 与工具管理页 | 支持任务、登录、抢单、配置异常诊断 |
| Phase 6 | SandboxManager、配置覆盖层、资源配额、沙箱管理 API 与前端 | 多用户隔离与 SKILL 执行环境就绪 |
| Phase 7 | SkillManager、SKILL 包格式、签名/试运行/版本管理、卸载、SKILL 管理页 | 可分发扩展生态形成 |

---

## 14. 关键风险与对策

| 风险 | 对策 |
---|---|
| 写工具绕过确认门 | 写工具不暴露给 LLM，ToolExecutor 强制检查 action 状态。 |
| 前端伪造确认请求 | token 绑定 payload_hash、user_id、session_id，后端 HMAC 校验。 |
| 配置修改影响自动下单 | risk=high，确认卡展示影响说明和 diff。 |
| 下单失败原因复杂 | 先做 `order.precheck`，失败不生成下单动作。 |
| repo_chatbot 文件继续膨胀 | 新增 `AgentRepository`，只复用 engine，不塞进 `repo_chatbot.py`。 |
| 诊断日志泄露敏感字段 | 工具层和展示层双重脱敏。 |
| 现有客服功能被影响 | Harness 可配置禁用，Orchestrator 可降级到旧流程。 |
| 沙箱隔离被绕过 | ToolExecutor 强制 `check_binding`，沙箱模式默认关闭保持单用户兼容。 |
| 沙箱配置覆盖层污染全局 | 覆盖层仅存内存与 overlay 表，提升到全局必须走标准确认门。 |
| 恶意 SKILL 注入 | 签名校验 + Prompt Injection 校验 + 沙箱试运行三道关卡，缺一不可。 |
| SKILL 工具权限越界 | 禁止 admin/critical 声明，PolicyEngine 取最严格策略合并，SKILL 工具默认 sandbox_only。 |
| SKILL 卸载丢审计 | 卸载仅清理 ToolRegistry 注册项，agent_skills 历史与 agent_actions 永久保留。 |
| 多版本 SKILL 冲突 | 命名空间 + 版本唯一键，默认版本标记，切换需管理员确认。 |

---

## 15. 阶段交接声明

- 当前阶段：Agent Harness 重构概要设计（含用户沙箱模式与 SKILL 安装功能扩展）。
- 下一阶段：详细设计。
- 推荐详细设计重点：
  1. `AgentRepository` 表结构与 CRUD 方法。
  2. `ActionPlan` / `PolicyDecision` / `ToolObservation` / `SandboxContext` / `SkillManifest` Pydantic 模型。
  3. `ApprovalGate` HMAC token 细节与测试用例。
  4. `config.preview/save/rollback` 和 `logs.request_chain` 工具实现细节。
  5. `SandboxManager` 覆盖层叠加算法、配额计数器、空闲超时巡检实现。
  6. `SkillManager` 签名校验算法、命名空间注册、试运行执行器、版本回滚实现。
  7. `ToolExecutor` 与 `SandboxManager` 的绑定校验与配额占用协作时序。
  8. 前端 ActionPlan 卡片、沙箱管理页、SKILL 管理页状态机。

---

**文档结束**
