# Llm Ai 编码规范
> 本文件归档 xianyu-hunter-dev skill 中与「llm ai」主题相关的编码规范。
> 主索引见 [SKILL.md](../../../SKILL.md) 的"step 索引表"，元规范见 [meta-rules.md](../../../references/meta-rules.md)。

---

### step 72：LLM 响应防御性三层级解析【强制】🆕v4.12

72. **LLM 响应防御性三层级解析【强制】🆕v4.12**
    - 调用 LLM API（OpenAI 兼容协议、Anthropic、本地模型）的响应必须按三层级防御性解析：`choices → message → content`，每层用 `.get()` / `isinstance` / 长度检查，**禁止**直接 `response["choices"][0]["message"]["content"]` 链式访问导致 KeyError / IndexError
    - **判断信号**：代码含 `response["choices"]` 或 `response['choices'][0]` → 必须用 `.get()` + 边界检查
    - **修复模式**：
      ```python
      # ✅ 三层级防御性解析
      def _extract_llm_content(response: dict) -> str | None:
          # 第一层：choices 数组存在且非空
          choices = response.get("choices") if isinstance(response, dict) else None
          if not choices or not isinstance(choices, list):
              logger.warning("LLM 响应缺少 choices 字段：{}", response)
              return None
          # 第二层：message 对象存在
          first = choices[0] if len(choices) > 0 else {}
          message = first.get("message") if isinstance(first, dict) else None
          if not message or not isinstance(message, dict):
              logger.warning("LLM 响应缺少 message 字段")
              return None
          # 第三层：content 字符串非空
          content = message.get("content")
          if not content or not isinstance(content, str):
              logger.warning("LLM 响应 content 为空")
              return None
          return content.strip()
      ```
    - **配置参数**：`llm_defensive_parsing.required_layers`（默认 `["choices", "message", "content"]`，必须校验的层级）、`llm_defensive_parsing.allow_empty_content`（默认 `false`，空 content 视为失败）、`llm_defensive_parsing.fallback_strategy`（默认 `return None`，可选 `raise`）在 `config.yaml` 的 `llm_defensive_parsing` 节点管理
    - **适用**：所有调用 LLM API 的代码（OpenAI 兼容协议 / Anthropic / 本地 Ollama / sentence-transformers）；流式响应（每个 chunk 也需校验）
    - **不适用**：本地模型直接返回对象（无 JSON 解析）；Embedding API 响应（结构不同）
    - **历史教训**：`_call_ai_suggestion` 直接 `response["choices"][0]["message"]["content"]`，LLM 服务异常时返回 `{"error": "..."}` 导致 KeyError 未捕获，AI 建议任务静默失败


---

### step 112：能力驱动派发规范（capability-driven dispatch）【强制】🆕v4.21

**背景**：闲鱼猎人有 2 个独立的 LLM 端点（`openai_chat_model` 用于成色评估、`openai_vision_model` 用于深度分析多模态场景）。深度分析无脑拼接 `image_url` content block，当 `openai_vision_model` 配置为纯文本模型（如 `qwen-turbo`/`deepseek-chat`）时，服务端 schema 拒绝并返回 400 `unknown variant 'image_url'`，触发 WARNING 日志噪音 + 降级失败。

**问题**：调用 LLM 前未做"能力-需求"匹配校验，payload 携带模型不支持的内容块，导致服务端 400。

**规范**：

1. 任何 LLM/多模态/function_call 调用必须在**构造 payload 前**预检目标模型能力
2. 校验模型能力的判断函数必须是共享的（如 `api_ai._is_vision_capable(model_name)`），禁止在多个调用点内联关键字白名单
3. 关键字白名单与模型名映射必须配置化（`config.yaml` 的 `llm_capability_keywords` 节点），关键字散落在代码中即视为违规
4. 校验逻辑分层：纯文本模型降级到 prompt 文字描述；多模态模型才发 `image_url` content block
5. 关键字白名单维护单一入口（如 `api_ai._VISION_CAPABLE_KEYWORDS`），其他模块通过 `from xianyu_hunter.web.routes.api_ai import _is_vision_capable` 复用
6. 单元测试必须覆盖：每类能力（vision / function_call / json_mode）的"支持"与"不支持"两组样本

**配置驱动**：参数在 `config.yaml` 的 `llm_capability_keywords` 节点管理，包含 `vision_keywords`（Vision 能力关键字列表）、`function_call_keywords`（函数调用能力关键字列表）、`json_mode_keywords`（JSON 模式能力关键字列表）、`case_insensitive`（是否大小写不敏感默认 True）。

**适用场景**：调用外部 LLM endpoint（OpenAI/Claude/通义千问/DeepSeek/Ollama）；调用多模态模型（Vision/Audio）；调用 function call / tool use；调用 structured output / JSON mode。

**不适用场景**：调用固定单一能力的稳定服务（不会扩展能力维度）；本地固定函数（无外部 endpoint）；已由 SDK 强制约束的调用（如 langchain 的 with_structured_output）。


---

### step 113：共享工具函数规范（避免散落内联判断）【强制】🆕v4.21

**背景**：本次修复初版把 `vision_capable` 判断内联到 `api_ai_deep.py`，与 `api_ai.py` 早已存在的相同关键字白名单重复 → 模型升级时需同时改 2 处 → 散落修改风险。

**问题**：跨模块复用的判断逻辑/常量被复制粘贴到多个调用点，导致关键字白名单/规则分散维护，模型升级时漏改。

**规范**：

1. 跨 ≥2 模块复用的判断逻辑必须抽取为"被依赖方"模块顶层的**纯函数**或**模块级常量**
2. 导入方只能 `from <source_module> import <shared_name>`，禁止复制粘贴关键字列表
3. 共享函数必须满足：纯函数（无副作用）/ 类型注解完整 / 单测覆盖 / docstring 注明"为什么是共享的"
4. 共享函数位置选择原则：
   - 业务最早引入该逻辑的模块作为"权威源"（避免循环依赖）
   - 若多个模块都引入过早，提取到 `domain/` 或 `infra/` 公共层
5. 审查场景：跨 ≥2 文件出现相同的关键字/正则/常量字面量，必须触发"抽取共享"建议
6. 共享范围判定标准：≥2 调用点 / ≥2 模块 / 调用方不修改逻辑（纯查询）

**配置驱动**：参数在 `config.yaml` 的 `shared_util_rules` 节点管理，包含 `min_call_sites`（触发抽取的最小调用点数默认 2）、`min_module_count`（触发抽取的最小模块数默认 2）、`pure_function_required`（是否强制纯函数默认 True）。

**适用场景**：跨模块复用的关键字白名单/正则/常量；模型/接口/协议的版本判断；权限/角色/能力位判断；业务规则判断（如"是否已售"关键词）。

**不适用场景**：仅单模块内部使用的 helper（不必抽取）；逻辑需要复用的同时还要扩展（应抽象为基类/策略模式）；性能敏感的 hot path 抽取会带来 import 开销（需评估）。


---

### step 114：静默降级预检规范（不支持能力 → 友好降级）【强制】🆕v4.21

**背景**：深度分析失败时直接抛 400，调用方需要 catch + 重试 + 降级，链路长且日志噪音大。`image_url` 这种"可选增强"内容块如果模型不支持，最优解不是抛错，而是**在调用前预检并降级到等价表达**（如 prompt 文本里加"图片请参考以下文字描述"）。

**问题**：LLM 端点不支持的能力被无脑发送，导致服务端 400 → 调用方抛错 → 日志噪音 → 降级链冗长。

**规范**：

1. 任何"可选增强"能力（vision / function call / tool use / json_mode）调用前必须预检
2. 预检失败时降级为"等价文本表达"，而非抛错：
   - vision 不支持 → 在 prompt 追加"图片 URL + 描述"
   - function call 不支持 → 用 prompt 引导模型输出 JSON 文本，调用方解析
   - json_mode 不支持 → 用 prompt 引导 + 调用方解析
3. 预检失败的日志级别必须是 `logger.warning`（step 59 规范），不阻断主流程
4. 主路径（核心文本生成）能力缺失必须报错，不能静默降级（区分"可选增强"与"核心能力"）
5. 降级路径必须有可观测性：日志中明确 `mode=downgrade reason=<缺失能力> model=<model_name>`
6. 降级路径的 prompt 模板必须集中管理（`config.yaml` 的 `llm_downgrade_prompts` 节点），禁止在调用点拼接

**配置驱动**：参数在 `config.yaml` 的 `llm_downgrade` 节点管理，包含 `optional_capabilities`（可选能力列表）、`downgrade_log_level`（降级日志级别默认 warning）、`prompt_templates`（降级 prompt 模板字典）、`downgrade_marker_format`（降级标记格式）。

**适用场景**：调用外部 LLM endpoint 且 payload 含可选能力字段；多模态/function call/structured output 调用；用户上传图片但模型可能不支持 Vision；用户启用 tool 但模型可能不支持 function call。

**不适用场景**：核心能力缺失（chat 文本生成失败必须报错）；用户明确要求某能力（如选择 vision-only 模型）；预检与降级开销大于直接调用（极简场景）。


---

