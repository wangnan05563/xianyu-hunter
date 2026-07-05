# 智能客服 Agent Harness 重构文档评审报告

| 项 | 内容 |
|---|---|
| 报告版本 | v1.0 |
| 报告日期 | 2026-07-02 |
| 评审对象 | 智能客服-AgentHarness重构-需求规格.md（v1.1）<br>智能客服-AgentHarness重构-概要设计.md（v1.1） |
| 评审范围 | 准确性、完整性、一致性，并新增「用户沙箱模式」与「SKILL 安装功能」 |
| 评审方法 | 源码对照 + 文档交叉比对 + 架构兼容性分析 |

---

## 1. 评审概述

本次评审针对 Agent Harness 重构的两份核心文档进行全面核对，并按要求新增两个关键功能模块。评审过程：

1. **源码核对**：读取 `tool_registry.py`、`tools/base.py`、`orchestrator.py`、`container.py`、`yaml_config.py` 等现有实现，验证文档描述与代码的一致性。
2. **文档交叉比对**：检查需求规格与概要设计在权限模型、接口、数据模型、验收标准上的对应关系。
3. **新增功能设计**：在两份文档中分别补充「用户沙箱模式」与「SKILL 安装功能」的需求与设计，并更新受影响的图表、接口、数据模型与实施分期。

---

## 2. 源码核对结果（准确性验证）

| 核对项 | 文档描述 | 源码实际 | 结论 |
|---|---|---|---|
| 现有工具数量与类型 | 5 个只读工具 | `task_status/eval_score/config_value/error_logs/help_page` | ✅ 准确 |
| 工具注册表脱敏机制 | 递归脱敏敏感字段 | `_filter_sensitive` + `_redact_recursive` | ✅ 准确 |
| `get_openai_schemas` 过滤 | 只返回 read 工具 | `"read" in tool.permissions` 过滤 | ✅ 准确 |
| `BaseTool` 现有字段 | permissions/timeout_sec/is_llm_tool | 与 `tools/base.py` 一致 | ✅ 准确 |
| 容器子结构 | `_build_chatbot_container` 返回 dict | `container.py` 返回 dict 含 orchestrator/tool_registry 等 | ✅ 准确 |
| `ChatbotConfig` 配置层次 | 含 rag/llm/agent/kb/faq/escalation 子段 | `yaml_config.py` 一致 | ✅ 准确 |
| Orchestrator 编排入口 | 串联 FAQ→Intent→RAG→Agent | `orchestrator.py` 一致 | ✅ 准确 |

**结论**：两份文档对现有实现的描述准确，未发现事实性错误。概要设计 §4.1 提出"现有 BaseTool 增加元数据字段"与源码现状一致（现有 `BaseTool` 仅有 `permissions/timeout_sec/is_llm_tool`，需新增 `risk_level/requires_confirmation/category/enabled` 等字段）。

---

## 3. 原有文档评审意见

### 3.1 需求规格修改建议（已在 v1.1 落实）

| 编号 | 建议 | 处理 |
|---|---|---|
| R-01 | 权限类型缺少沙箱与 SKILL 管理权限 | 已在 §7.1 新增 `sandbox`、`skill_install` 权限 |
| R-02 | 风险等级示例未覆盖沙箱/SKILL 场景 | 已在 §7.2 high/critical 补充示例 |
| R-03 | 接口清单未含沙箱/SKILL 管理 API | 已在 §8.1 新增 15 个端点 |
| R-04 | 审计字段缺少 sandbox_id 与 skill_source | 已在 §10.2 补充 |
| R-05 | 安全要求未覆盖沙箱隔离与 SKILL 签名 | 已在 §11 新增 SR-11 ~ SR-16 |
| R-06 | 验收标准未含沙箱/SKILL | 已在 §13 新增 13.5、13.6（AC-19 ~ AC-31） |
| R-07 | 实施分期未含沙箱/SKILL 阶段 | 已在 §14 新增 Phase 6、Phase 7 |

### 3.2 概要设计修改建议（已在 v1.1 落实）

| 编号 | 建议 | 处理 |
|---|---|---|
| D-01 | 分层架构图未含沙箱/SKILL 管理器 | 已在 §2.1 Harness 层加入 `sandbox_manager.py`/`skill_manager.py` |
| D-02 | 核心组件关系图缺沙箱/SKILL 组件 | 已在 §2.2 加入 SBM/SKM 及其协作关系 |
| D-03 | 模块设计缺 SandboxManager/SkillManager | 已新增 §3.9、§3.10 含接口、模型、流程图 |
| D-04 | 工具元数据 category 缺 skill 分类 | 已在 §4.1 新增 `skill` 分类与 `skill_source`/`sandbox_only` 字段 |
| D-05 | 数据模型缺沙箱/SKILL 表 | 已新增 §5.1.5 ~ §5.1.9 共 5 张表，并为 `agent_actions`/`agent_tool_calls` 补 `sandbox_id`/`skill_source` 字段 |
| D-06 | API 端点清单缺沙箱/SKILL | 已在 §6.2 新增对应端点，§6.3 补请求响应示例 |
| D-07 | 关键流程缺沙箱配置覆盖流程 | 已新增 §7.5 沙箱配置覆盖与提升流程图 |
| D-08 | 容器集成未注入沙箱/SKILL 管理器 | 已在 §8.1 更新注入代码 |
| D-09 | 配置扩展未含沙箱/SKILL 子配置 | 已在 §8.4 新增 `sandbox`/`skill` 配置段 |
| D-10 | 安全设计缺沙箱隔离/SKILL 安全 | 已新增 §9.5、§9.6 |
| D-11 | 错误处理缺沙箱/SKILL 错误场景 | 已在 §10 新增 8 个错误场景 |
| D-12 | 前端设计缺沙箱/SKILL 管理页 | 已新增 §11.4、§11.5 |
| D-13 | 测试策略缺沙箱/SKILL 测试 | 已在 §12.1/12.2/12.3 补充 |
| D-14 | 实施分期与风险对策未含沙箱/SKILL | 已在 §13、§14 补充 |

---

## 4. 新增功能说明

### 4.1 用户沙箱模式

**核心定位**：沙箱是 Harness 在 `user_id` 维度上的强隔离执行边界，服务于多用户场景与第三方 SKILL 扩展执行环境隔离。

**关键技术设计**：

| 维度 | 设计要点 |
|---|---|
| 上下文隔离 | 按 `sandbox_id` 隔离 ActionPlan、工具调用、诊断报告；`ContextManager` 按 sandbox_id 分区管理会话历史与 RAG 检索片段 |
| 工具可见性 | 沙箱用户仅见管理员授权工具子集，`get_openai_schemas()` 对非沙箱会话不返回 SKILL 工具 |
| 配置覆盖层 | 沙箱内 `config.preview` 基于 overlay 计算 diff，不落盘全局；`promote_overlay` 提升时生成 `risk=high` ActionPlan 走标准确认门 |
| 资源配额 | 单用户并发动作数、调用频率、存储上限，超额返回 `SANDBOX_QUOTA_EXCEEDED` |
| 生命周期 | 空闲超时自动卸载、最大存活时长、手动启停；卸载后 sandbox_id 不可复用，保留审计摘要 |
| 绑定校验 | `ToolExecutor` 执行前强制 `check_binding(sandbox_id, user_id)`，未通过记录 `sandbox_binding_violation` |
| 快照与重置 | 管理员可打快照、回滚、清空临时数据，保留已确认全局副作用 |

**兼容性**：沙箱模式默认关闭（`sandbox.enabled=false`），关闭时单用户流程与现有 Harness 行为完全一致。

### 4.2 SKILL 安装功能

**核心定位**：SKILL 是 Agent 能力的可分发扩展包（封装工具/Procedure/Prompt/测试样例），所有 SKILL 工具必须在用户沙箱内执行。

**安装三道关卡**：

```text
签名校验 → Prompt Injection 校验 → 沙箱试运行
   ↓            ↓                      ↓
skill_signature_invalid  skill_prompt_injection  install_failed_dryrun
```

**关键机制**：

| 机制 | 设计 |
|---|---|
| 包格式 | manifest（name/version/permissions/risk/dependencies/resources）+ tools + procedures + prompt_fragments + test_cases + signature |
| 获取渠道 | 本地导入、官方市场 URL（白名单）、已安装重装；不支持匿名 URL |
| 命名空间 | `<skill_name>.<tool_name>`，冲突拒绝安装 |
| 权限约束 | 不得声明 admin/critical，降级为 high 或拒绝；PolicyEngine 取最严格策略合并 |
| 版本管理 | 多版本共存，`is_default` 标记默认版本，切换需管理员确认；升级失败自动回滚 |
| 卸载 | 清理 ToolRegistry 注册项，保留 agent_skills 历史与 agent_actions 审计 |
| 全局开关 | `allow_skill_install=false` 时安装接口返回 403，已安装 SKILL 仍可用 |

### 4.3 两功能协作关系

沙箱与 SKILL 强耦合：SKILL 试运行必须在沙箱内执行，SKILL 工具默认 `sandbox_only=True`。沙箱为 SKILL 提供隔离执行环境，SKILL 为沙箱提供可扩展能力。两者均在 Phase 6/7 落地，建立在 Harness 安全执行底座（Phase 1-5）稳定之后。

---

## 5. 一致性检查

### 5.1 两份文档对应关系

| 需求规格 | 概要设计 | 一致性 |
|---|---|---|
| §6.8 沙箱需求（FR-SB-01 ~ 12） | §3.9 SandboxManager + §9.5 沙箱隔离 | ✅ 需求项均有设计落点 |
| §6.9 SKILL 需求（FR-SK-01 ~ 15） | §3.10 SkillManager + §9.6 SKILL 安全 | ✅ 需求项均有设计落点 |
| §7.1 权限（sandbox/skill_install） | §4.1 工具元数据 + §4.4 执行约束 | ✅ 权限模型一致 |
| §8.1 API（15 个新端点） | §6.2 端点清单 + §6.3 请求响应示例 | ✅ 端点完全对应 |
| §10.1 数据表（5 张新表） | §5.1.5 ~ §5.1.9 + 字段补充 | ✅ 表结构一致 |
| §10.2 审计字段（sandbox_id/skill_source） | §5.1.1/§5.1.3 字段补充 | ✅ 审计字段一致 |
| §11 安全（SR-11 ~ SR-16） | §9.5/§9.6 安全设计 | ✅ 安全要求对应 |
| §13 验收（AC-19 ~ AC-31） | §12 测试策略 | ✅ 验收项有测试覆盖 |
| §14 实施分期（Phase 6/7） | §13 实施分期（Phase 6/7） | ✅ 分期一致 |

### 5.2 与现有架构兼容性

| 兼容项 | 验证 |
|---|---|
| 沙箱默认关闭 | `sandbox.enabled=false`，单用户流程不受影响 |
| SKILL 安装可禁用 | `allow_skill_install=false` 时安装接口 403，已安装可用 |
| 现有只读工具不受影响 | 沙箱关闭时 `ToolExecutor` 跳过绑定校验，行为不变 |
| 现有 SSE 兼容 | 新增 `sandbox_event`/`skill_event`，旧前端忽略未知事件 |
| 现有表不修改 | `agent_*` 新表独立，`chatbot_*` 表不变 |
| Orchestrator 降级保留 | Harness 不可用时降级回旧 RAG/FAQ 流程 |

---

## 6. 实施优先级评估

| 阶段 | 内容 | 优先级 | 依赖 | 风险 |
|---|---|---|---|---|
| Phase 1-5 | Harness 安全执行底座 | P0（前置） | 无 | 已有文档覆盖，按原计划推进 |
| Phase 6 | 用户沙箱模式 | P1 | Phase 1-5 稳定 | 覆盖层叠加算法与配额计数器需详细设计；沙箱默认关闭降低风险 |
| Phase 7 | SKILL 安装功能 | P1 | Phase 6（沙箱就绪） | 签名校验体系需配套密钥管理；试运行执行器需复用 ProcedureRunner |

**建议**：

- Phase 6 与 Phase 7 串行：SKILL 试运行依赖沙箱，必须先完成沙箱。
- Phase 6 可先实现"上下文隔离 + 绑定校验 + 配额"最小集，覆盖层与快照可后置。
- Phase 7 可先实现"本地导入 + 签名校验 + 试运行 + 命名空间注册"最小集，市场 URL 安装与多版本共存可后置。
- 两阶段均需在 Phase 1-5 审计闭环验证通过后启动，避免在不稳定底座上叠加隔离层。

---

## 7. 评审结论

| 维度 | 结论 |
|---|---|
| 准确性 | 两份文档对现有实现描述准确，源码核对未发现事实性错误 |
| 完整性 | 新增沙箱与 SKILL 功能后，需求与设计覆盖完整，无遗漏关键场景 |
| 一致性 | 需求规格与概要设计在权限、接口、数据模型、验收、分期上完全对应 |
| 兼容性 | 新功能默认关闭/可禁用，不影响现有单用户客服流程 |
| 建议 | 同意进入详细设计阶段；Phase 6/7 按 P1 优先级在底座稳定后串行推进 |

**评审状态**：通过，文档已更新至 v1.1，可进入详细设计阶段。

---

## 8. 阶段交接声明

- 当前阶段：Agent Harness 重构文档评审与更新 ✅ 已完成
- 下一阶段：详细设计
- 下一阶段智能体：详细设计智能体
- 下一阶段技能：writing-plans / doc-coauthoring
- 交接上下文：
  1. 两份文档已更新至 v1.1，新增用户沙箱模式（§6.8/§3.9）与 SKILL 安装功能（§6.9/§3.10）。
  2. 5 张新数据表（agent_sandboxes/agent_sandbox_overlays/agent_sandbox_snapshots/agent_skills/agent_skill_installations）需在详细设计中定义完整 DDL。
  3. 15 个新 API 端点需在详细设计中定义完整请求/响应 schema 与错误码。
  4. SandboxManager 覆盖层叠加算法、配额计数器、空闲超时巡检为详细设计重点。
  5. SkillManager 签名校验算法、试运行执行器、版本回滚为详细设计重点。
  6. 实施按 Phase 1-5（底座）→ Phase 6（沙箱）→ Phase 7（SKILL）串行推进。

---

**报告结束**
