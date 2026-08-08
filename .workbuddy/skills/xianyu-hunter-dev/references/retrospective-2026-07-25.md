# 第七轮复盘：智能客服 Markdown 渲染与 follow_ups 推荐问题代码评审

> 复盘时间：2026-07-25（第七轮，基于智能客服系统 Markdown 渲染优化和 follow_ups 推荐问题功能的代码评审，发现 10 个问题）
> 复盘方法：Sequential Thinking 四维度复盘法（成功步骤 / 失败点 / 可抽象流程 / 适用场景）
> 配套编码规范：coding-standards v1.3 §2.21-2.24（后端 LLM 治理）+ §3.10-3.15（前端韧性）
> 配套审查规范：B-REVIEW-291~294（后端 LLM 治理）/ F-REVIEW-227~232（前端韧性）
> 配套测试模式：xianyu-auto-testing 模式 Y（前端韧性回归测试）/ 模式 Z（LLM 治理回归测试）

---

## G.1 代码评审发现的成功步骤

**适用问题**：智能客服系统涉及 Markdown 渲染、SSE 流式响应、LLM 附加调用（follow_ups/标题/标签）的代码修改

| 步骤 | 操作 | 验证方式 |
|---|---|---|
| 1. 识别所有 LLM 调用点 | grep 主调用与附加调用方法 | `grep -rn "generate\|chat.completions" src/xianyu_hunter/modules/chatbot/` |
| 2. 验证预算闭环 | 每个附加调用前 check_budget，后 _record_llm_usage | 静态阅读 + 运行时日志 |
| 3. 验证独立超时 | 附加调用用 asyncio.wait_for，超时 < 主调用 | 单元测试模拟超时 |
| 4. 验证响应解析 | json.loads + 类型校验 + 代码块剥离 | 畸形响应测试 |
| 5. 验证 Markdown 预处理 | 代码块分割后仅对非代码段替换 | 构造代码块内含待替换文本的用例 |
| 6. 验证 SSE 类型校验 | zod safeParse + fallback | schema 漂移测试 |
| 7. 验证定时器清理 | useRef 存储 ID + cleanup 清理 | 快速连续触发测试 |
| 8. 验证可访问性 | tabIndex/role/onKeyDown 三件套 | Playwright 键盘操作测试 |
| 9. 验证 onComplete 完整性 | 任一产出非空即持久化 | 主回答为空 + follow_ups 非空测试 |

**关键判断逻辑**：
- 附加 LLM 调用 ≠ 独立调用：必须共享主调用的预算上下文
- Markdown 替换 ≠ 全局替换：必须先分割代码块
- SSE 数据 ≠ 可信数据：必须运行时类型校验
- 持久化判断 ≠ 主回答非空：必须基于任一产出非空

---

## G.2 10 个失败模式与修复（2026-07-25）

### 后端 4 个失败模式

| 编号 | 失败模式 | 根因 | 修复 | 教训 |
|---|---|---|---|---|
| F27 | generate_follow_ups 未复用主调用的预算检查 | 附加 LLM 调用独立实现，未调用 check_budget + _record_llm_usage | 在 generate_follow_ups 中添加 check_budget() 和 _record_llm_usage()，共享 BudgetContext | 附加 LLM 调用必须共享主调用的预算上下文 |
| F28 | generate_follow_ups 无独立超时 | 附加调用沿用主调用超时（30s），阻塞 DONE 事件 | 用 asyncio.wait_for 设置 8s 独立超时，超时降级返回空列表 | 附加调用必须有独立且更短的超时 |
| F29 | LLM 响应用正则提取 JSON | `re.search(r'\{.*\}', ...)` 易误匹配嵌套结构 | 改用 json.loads + isinstance 类型校验 + 代码块剥离 | 禁止用正则提取 LLM 返回的 JSON |
| F30 | 附加调用异常处理与主调用不一致 | 异常类型、日志格式、降级策略不统一 | 统一异常处理模式，附加异常 catch 不冒泡到主调用 | 多调用必须保持异常/日志/降级一致性 |

### 前端 6 个失败模式

| 编号 | 失败模式 | 根因 | 修复 | 教训 |
|---|---|---|---|---|
| F31 | Markdown 替换破坏代码块 | `[来源:N]` 替换直接作用于原始字符串，未分割代码块 | 先按代码块分割，仅对非代码段执行替换 | Markdown 预处理必须保护代码块 |
| F32 | React render 阶段写 ref | `handleSendRef.current = handleSend` 写在函数组件主体内 | 移到 useEffect 中，依赖项 [handleSend] | render 阶段禁止副作用 |
| F33 | SSE 事件数据用 as 强制断言 | `data.follow_ups as string[]` 无运行时校验 | 用 zod schema safeParse + fallback | SSE 数据必须运行时类型校验 |
| F34 | CodeBlock 定时器未清理 | setTimeout 未在卸载时清理，连续复制时旧定时器覆盖新状态 | 用 useRef 存储 ID，卸载时清理，重设前清除旧定时器 | 定时器必须清理 + 竞态防护 |
| F35 | follow_ups Tag 缺可访问性 | `<div onClick>` 无 tabIndex/role/onKeyDown | 添加三件套，支持 Tab 聚焦 + Enter/Space 触发 | 非原生交互元素必须三件套齐全 |
| F36 | onComplete 持久化条件不完整 | `if (content.length > 0)` 仅检查主回答，附加产出丢失 | 改为 `content.length > 0 \|\| followUps.length > 0` | 持久化判断基于任一产出非空 |

---

## G.3 可沉淀的固定流程

| 流程 | 触发 | 步骤 | 验证 |
|---|---|---|---|
| LLM 附加调用治理 | 一个请求触发 ≥2 次 LLM 调用 | 识别附加调用 → check_budget → asyncio.wait_for 独立超时 → json.loads 解析 → _record_llm_usage → 异常 catch 不冒泡 | 单元测试覆盖预算超限/超时/畸形响应/异常冒泡四场景 |
| Markdown 预处理代码块保护 | 对 Markdown 字符串做字符替换 | 分割代码块和行内代码 → 对非代码段执行替换 → 拼接回原结构 | 构造代码块内含待替换文本的测试用例 |
| SSE 事件运行时类型校验 | 处理 SSE/WebSocket/PostMessage 数据 | 定义 zod schema → safeParse 校验 → 失败降级返回 fallback → 成功使用解析结果 | schema 漂移测试（后端字段类型不匹配） |
| 定时器清理与竞态防护 | 使用 setTimeout/setInterval | useRef 存储 ID → 重设前清除旧定时器 → 卸载时清理 → 避免在 render 中创建 | 快速连续触发测试 |
| 流式响应数据完整性 | SSE onComplete 持久化 | 识别所有产出字段 → 任一非空即持久化 → 所有产出传递给回调 → 空状态记录 WARNING | 主回答为空 + 附加产出非空的测试 |

---

## G.4 反模式（禁止清单）

1. **禁止**附加 LLM 调用跳过 check_budget 直接发起请求
2. **禁止**附加 LLM 调用使用与主调用相同的超时（必须独立且更短）
3. **禁止**用 re.search/re.findall 提取 LLM 返回的 JSON
4. **禁止**附加调用异常冒泡到主调用导致主回答失败
5. **禁止**对 Markdown 字符串直接做 replace 不分割代码块
6. **禁止**在 React 函数组件主体内写 ref.current
7. **禁止**用 as 强制断言 SSE 事件数据
8. **禁止**setTimeout/setInterval 未在 useEffect cleanup 中清理
9. **禁止**非原生交互元素无 tabIndex/role/onKeyDown
10. **禁止**onComplete 持久化条件仅检查主回答非空

---

## G.5 适用与不适用场景

### 适用场景

- 智能客服 / Chatbot 系统（涉及 Markdown 渲染、SSE 流式响应、LLM 附加调用）
- 任何一个请求触发 ≥2 次 LLM 调用的场景
- SSE / WebSocket 流式响应处理
- 富文本渲染前的内容预处理
- 定时器密集的交互组件（如复制成功提示、轮询、防抖）

### 不适用场景

- 单次 LLM 调用（无附加调用）
- 纯静态展示页面（无交互、无 SSE）
- 服务端渲染（SSR）应用
- 非 React 框架代码
- 测试代码中的 mock 数据（可放宽类型校验）

---

## G.6 下游技能同步清单（第七轮）

| 文件 | 本次新增内容 |
|---|---|
| `.trae/skills/xianyu-hunter-dev/references/coding-standards.md` | 版本 v1.2 → v1.3，新增 §2.21-2.24（后端 LLM 治理）+ §3.10-3.15（前端韧性） |
| `.trae/skills/xianyu-backend-code-review/SKILL.md` | 版本 v4.61.0 → v4.62.0，新增维度 45 LLM 多调用治理 Review |
| `.trae/skills/xianyu-backend-code-review/references/llm-governance-checks.md` | 新建，B-REVIEW-291~294 详细描述 |
| `.trae/skills/xianyu-backend-code-review/references/checkpoints-index.md` | 新增 B-REVIEW-291~294 索引行，统计 190→194 项 |
| `.trae/skills/xianyu-backend-code-review/config.yaml` | 新增 `llm_call_governance` 配置节点 |
| `.trae/skills/xianyu-frontend-code-review/SKILL.md` | 版本 v4.61.0 → v4.62.0，新增维度 40 前端韧性 Review |
| `.trae/skills/xianyu-frontend-code-review/references/frontend-resilience-checks.md` | 新建，F-REVIEW-227~232 详细描述 |
| `.trae/skills/xianyu-frontend-code-review/references/checkpoints-index.md` | 新增 F-REVIEW-227~232 索引行，统计 127→133 项 |
| `.trae/skills/xianyu-frontend-code-review/config.yaml` | 新增 `frontend_resilience` 配置节点 |
| `.trae/skills/xianyu-auto-testing/SKILL.md` | 版本 v2.1.0 → v2.2.0，新增模式 Y（前端韧性回归测试）+ 模式 Z（LLM 治理回归测试） |
| `.trae/skills/xianyu-auto-testing/config.yaml` | 新增 `mode_y_frontend_resilience_test` + `mode_z_llm_governance_test` 配置节点 |
| `.trae/skills/xianyu-hunter-dev/references/retrospective-2026-07-25.md` | 新建，本复盘报告 |

---

## G.7 跨技能一致性验证清单

| 验证项 | 验证方式 | 结果 |
|---|---|---|
| 编码规范版本号一致 | coding-standards.md v1.3 被所有技能引用 | ✅ |
| 检查点 ID 不冲突 | B-REVIEW-291~294（后端）/ F-REVIEW-227~232（前端）编号独立 | ✅ |
| 配置节点命名一致 | `llm_call_governance` / `frontend_resilience` / `mode_y_*` / `mode_z_*` | ✅ |
| 配套测试模式引用闭环 | backend/ frontend SKILL.md 引用 auto-testing 模式 Y/Z；auto-testing 引用 B-REVIEW/F-REVIEW | ✅ |
| 无硬编码 | 所有阈值/正则/方法名/文件路径通过 config.yaml 管理 | ✅ |
| YAML 语法正确 | 所有 config.yaml 修改通过 yaml.safe_load 校验 | 待验证 |
