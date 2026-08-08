# LLM 多调用治理检查点详细描述

> **配套技能**：[xianyu-backend-code-review](../SKILL.md)
> **维度归属**：45. LLM 多调用治理 Review（v4.62.0 新增）
> **配套编码规范**：[coding-standards v1.3 §2.21-2.24](../../xianyu-hunter-dev/references/coding-standards.md)
> **配置节点**：`config.yaml#llm_call_governance`
> **维护原则**：本文件为 B-REVIEW-291~294 的详细描述冷区域，日常审查无需预加载，仅在命中 LLM 多调用场景时查阅。

---

## 维度 45：LLM 多调用治理 Review v4.62.0

- **Severity**: HIGH（P1，LLM 附加调用缺乏预算/超时/解析/一致性治理导致主流程阻塞、用量统计偏差、数据丢失）
- **Reference**: coding-standards v1.3 §2.21-2.24 / 2026-07-25 代码评审 10 问题复盘后端落地
- **适用**：一个请求触发 ≥2 次 LLM 调用（主回答 + follow_ups/标题/标签/摘要等附加产出）；流式响应（SSE）中的附加调用
- **不适用**：单次 LLM 调用；非 LLM 的纯本地计算；不同业务场景的独立 LLM 调用

---

### B-REVIEW-291 LLM-AUX-CALL-BUDGET LLM 附加调用预算与用量闭环

- **检查点 ID**：B-REVIEW-291
- **严重等级**：CRITICAL（P0，预算超限后仍消耗 token 导致费用失控 + 用量统计偏差）
- **配置节点**：`config.yaml#llm_call_governance.aux_call_budget`
- **对应编码规范**：coding-standards v1.3 §2.21

#### 问题描述
附加 LLM 调用（如 `generate_follow_ups`、`generate_title`、`generate_tags`、`generate_summary`）未复用主调用 `generate` 方法的 `check_budget()` + `_record_llm_usage()`，导致：
1. 预算超限后附加调用仍执行，消耗 token 产生费用
2. 附加调用的用量未记录，统计偏差
3. 附加调用另起一套统计逻辑，维护成本高

#### 关键要求
1. **预算检查前置**：附加调用执行前必须调用 `check_budget()`，超限时拒绝调用并降级
2. **用量记录闭环**：附加调用完成后必须调用 `_record_llm_usage()`，写入 token 用量
3. **复用主调用工具**：必须复用主调用的预算/记录工具，禁止另起一套统计逻辑
4. **降级策略显式**：预算超限时必须显式降级（返回空结果 + WARNING 日志），禁止静默跳过

#### 定位方式
```powershell
# 查找所有 LLM 调用点（主+附加）
grep -rn "chat\.completions\.create\|generate_follow_ups\|generate_title\|generate_tags\|generate_summary" src/xianyu_hunter/ --include="*.py"
```

#### 判断标准
| 信号 | 等级 | 说明 |
|---|---|---|
| 附加调用未调用 `check_budget()` | CRITICAL | 预算超限后仍消耗 token |
| 附加调用未调用 `_record_llm_usage()` | WARNING | 用量统计偏差 |
| 附加调用另起一套统计逻辑 | WARNING | 维护成本高，易漂移 |
| 预算超限时静默跳过无日志 | WARNING | 排查困难 |

#### 修复方案
抽取 `_check_budget_and_record(stage, model)` 装饰器或上下文管理器，所有 LLM 调用（主+附加）复用同一套预算检查与用量记录工具。

#### 历史教训
`rag_engine.py` 的 `generate_follow_ups` 方法直接调用 LLM 未检查预算，导致预算超限后仍消耗 token；且未记录用量，导致 `ai_usage` 统计与实际消耗偏差。修复：复用主 `generate` 方法的 `check_budget()` + `_record_llm_usage()`。

---

### B-REVIEW-292 LLM-AUX-CALL-TIMEOUT LLM 附加调用独立超时

- **检查点 ID**：B-REVIEW-292
- **严重等级**：CRITICAL（P0，附加调用阻塞主流程导致 SSE DONE 事件延迟）
- **配置节点**：`config.yaml#llm_call_governance.aux_call_timeout`
- **对应编码规范**：coding-standards v1.3 §2.22

#### 问题描述
附加 LLM 调用未用 `asyncio.wait_for` 包裹，可能阻塞主流程（如 SSE DONE 事件）。主调用有超时保护但附加调用没有，导致附加调用异常时整个请求卡死。

#### 关键要求
1. **每个调用独立超时**：主调用和每个附加调用都必须用 `asyncio.wait_for(coro, timeout=cfg.xxx_timeout)` 包裹
2. **超时阈值配置化**：主调用/附加调用可有不同超时，均从 `config.yaml` 读取，禁止硬编码
3. **超时降级而非抛错**：超时 except 块必须降级（返回空结果 + WARNING），不向上抛 TimeoutError 中断主流程
4. **超时日志结构化**：必须记录 `stage=xxx elapsed=xxx timeout=xxx model=xxx`，便于聚合分析

#### 定位方式
```powershell
# 查找未用 wait_for 包裹的 LLM 调用
grep -rn "await.*chat\.completions\|await.*generate" src/xianyu_hunter/ --include="*.py" | grep -v "wait_for"
```

#### 判断标准
| 信号 | 等级 | 说明 |
|---|---|---|
| 附加调用未用 `asyncio.wait_for` 包裹 | CRITICAL | 可能阻塞主流程 |
| 超时阈值硬编码（如 `timeout=10`） | WARNING | 无法配置化调整 |
| 超时 except 块向上抛 TimeoutError | CRITICAL | 中断主流程 |
| 超时日志未结构化 | WARNING | 排查困难 |

#### 修复方案
```python
result = await asyncio.wait_for(
    self._call_llm(query, context),
    timeout=self._config.aux_call_timeout_sec,
)
```
超时 except 块降级返回空结果 + 结构化 WARNING 日志。

#### 历史教训
`generate_follow_ups` 未用 `asyncio.wait_for` 包裹，LLM 响应慢时阻塞 DONE 事件，前端长时间无响应。修复：用 `asyncio.wait_for` 包裹 + 8s 超时（从 config 读取）+ 超时降级返回空列表。

---

### B-REVIEW-293 LLM-RESPONSE-STRUCTURED-PARSE LLM 响应结构化解析

- **检查点 ID**：B-REVIEW-293
- **严重等级**：CRITICAL（P0，正则提取 JSON 不可靠 + 无类型校验导致运行时崩溃）
- **配置节点**：`config.yaml#llm_call_governance.response_parse`
- **对应编码规范**：coding-standards v1.3 §2.23

#### 问题描述
用正则 `re.search(r'\{.*\}', text)` 提取 LLM 返回的 JSON，未用 `json.loads` + 类型校验。正则提取不可靠（贪婪匹配/嵌套结构/转义字符问题），且解析后无类型校验，字段不存在时 KeyError 崩溃。

#### 关键要求
1. **禁止正则提取 JSON**：必须用 `json.loads` 解析，禁止 `re.search(r'\{.*\}', text)`
2. **元素类型校验**：解析后必须用 Pydantic 模型或显式 isinstance 检查每个字段类型
3. **解析失败降级**：`json.JSONDecodeError` 必须捕获并降级（返回默认值 + WARNING），禁止向上抛
4. **Markdown 代码块剥离**：LLM 常返回 ` ```json ... ``` `，必须先剥离代码块标记再 `json.loads`

#### 定位方式
```powershell
# 查找用正则提取 JSON 的代码
grep -rn "re\.search.*\\\\{.*\\\\}\|re\.findall.*json\|re\.match.*\\\\[" src/xianyu_hunter/ --include="*.py"
```

#### 判断标准
| 信号 | 等级 | 说明 |
|---|---|---|
| 用 `re.search(r'\{.*\}', text)` 提取 JSON | CRITICAL | 正则不可靠 |
| `json.loads` 后未做类型校验 | WARNING | 字段不存在时 KeyError |
| 未处理 ` ```json ``` ` 代码块标记 | WARNING | json.loads 失败 |
| 解析失败向上抛异常 | CRITICAL | 中断主流程 |

#### 修复方案
用 Pydantic 模型 `LLMResponse.model_validate_json(text)` 解析，自动处理类型校验；代码块标记剥离逻辑封装为独立函数；解析失败降级返回默认值。

#### 历史教训
follow_ups 解析用正则提取 JSON，LLM 返回含嵌套 JSON 时贪婪匹配错误；且无类型校验，`follow_ups` 字段为 null 时 `data["follow_ups"]` 返回 None，后续 `.map` 崩溃。修复：用 Pydantic 模型 + 类型校验 + 降级返回空列表。

---

### B-REVIEW-294 LLM-MULTI-CALL-CONSISTENCY LLM 多调用一致性

- **检查点 ID**：B-REVIEW-294
- **严重等级**：WARNING（P1，错误处理/日志/降级策略不一致导致排查困难、行为不可预测）
- **配置节点**：`config.yaml#llm_call_governance.multi_call_consistency`
- **对应编码规范**：coding-standards v1.3 §2.24

#### 问题描述
同一请求中多个 LLM 调用（主+附加）在错误处理、日志、降级策略上不一致：
1. 主调用 except 块用 `logger.exception`，附加调用用 `logger.error`
2. 主调用降级抛错，附加调用降级返回空（策略不对称）
3. 主调用日志含 `stage/model/elapsed`，附加调用只有 `message`
4. 配置参数散落在不同位置

#### 关键要求
1. **错误处理一致**：主调用和附加调用的 except 块结构一致（捕获相同异常类型 + 相同降级模式）
2. **日志格式一致**：所有 LLM 调用日志使用统一格式（`stage=xxx model=xxx elapsed=xxx tokens=xxx`）
3. **降级策略一致**：主调用降级时附加调用必须跳过；附加调用降级时主调用结果保留
4. **配置参数集中**：所有 LLM 调用的超时/重试/降级阈值集中在 `llm_call_governance` 节点，禁止散落

#### 定位方式
```powershell
# 对比主调用与附加调用的 except 块结构
grep -rn "except.*OpenAIError\|except.*Exception" src/xianyu_hunter/ --include="*.py" | grep -A2 "generate"
```

#### 判断标准
| 信号 | 等级 | 说明 |
|---|---|---|
| 主调用与附加调用 except 块结构不一致 | WARNING | 行为不可预测 |
| 日志格式不统一 | WARNING | 排查困难 |
| 降级策略冲突（主调用降级时附加调用仍执行） | CRITICAL | 资源浪费 |
| 配置参数散落未集中在 `llm_call_governance` | WARNING | 维护成本高 |

#### 修复方案
抽取 `LLMCallContext` 统一管理错误处理/日志/降级，主调用和附加调用共用同一上下文。配置参数集中在 `config.yaml#llm_call_governance` 节点。

#### 历史教训
主调用 `generate` 用 `logger.exception` + 抛错降级，附加调用 `generate_follow_ups` 用 `logger.error` + 返回空列表降级，导致：1）日志级别不一致排查困难；2）主调用失败时附加调用仍执行浪费资源。修复：抽取 `LLMCallContext` 统一治理策略。
