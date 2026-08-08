# 维度 28：LLM 端点能力派发

> **编码规范引用**：coding-standards v1.3 §2.21-2.24 LLM 调用治理
> **配置节点**：config.yaml#llm_call_governance
> **对应 references**：llm-governance-checks.md

## 触发条件
- LLM 调用代码（chat/completions、RAG、关键词提取等）
- LLM 端点路由/派发逻辑
- OpenAI 兼容 API 客户端封装
- 一个请求触发 ≥2 次 LLM 调用

## 检查规则

### 强制（P0 阻塞）
- LLM 端点选择策略必须明确：选哪个模型、走哪个 provider，禁止硬编码在业务代码中，应从 `config.yaml` 读取
- 附加 LLM 调用必须复用主调用的预算检查 + 用量记录工具：执行前 `check_budget()`，完成后 `_record_llm_usage()`
- 每个 LLM 调用必须用 `asyncio.wait_for` 包裹独立超时，超时后降级（返回空 + WARNING），禁止向上抛 TimeoutError

### 推荐（P1 严重）
- 共享工具函数不重复实现：多端点共用的能力（如 token 统计、预算检查、错误处理）提取为公共模块
- 能力路由可配置：哪些请求走哪些模型在 `config.yaml` 中定义，不硬编码
- LLM 响应必须用 `json.loads` + Pydantic 模型解析，禁止用正则提取 JSON
- 主调用与附加调用的错误处理/日志/降级策略必须一致

### 禁止
- 硬编码模型名称（如 `model="gpt-4"`）
- 用 `re.search(r'\{.*\}', text)` 提取 LLM 返回的 JSON
- 附加调用未检查预算（超限后仍消耗 token）
- 主调用降级时附加调用仍执行

## Grep 扫描命令

```bash
# LLM 调用点
grep -rn "chat\.completions\.create\|openai\.\|litellm\|generate_" src/xianyu_hunter/ --include="*.py"

# 模型名称硬编码
grep -rn "model\s*=\s*\"gpt\|model\s*=\s*\"claude\|model\s*=\s*\"deepseek" src/xianyu_hunter/ --include="*.py"

# 正则提取 JSON
grep -rn "re\.search.*\\\\{.*\\\\}\|re\.findall.*json" src/xianyu_hunter/ --include="*.py"

# wait_for 超时
grep -rn "asyncio\.wait_for\|timeout" src/xianyu_hunter/ --include="*.py" | grep -i "llm\|openai\|generate"

# 预算检查
grep -rn "check_budget\|_record_llm_usage\|llm_usage" src/xianyu_hunter/ --include="*.py"
```

## 判断标准
- 模型名称硬编码 → P0 阻塞
- 附加调用未复用预算检查 → P0 阻塞
- 无 `asyncio.wait_for` 超时 → P0 阻塞
- 正则提取 JSON → P1 严重
- 主调用与附加调用降级策略不一致 → P1 严重
- 能力路由硬编码 → P2 改进

## 适用/不适用场景
- **适用**：所有 LLM 调用场景（聊天、RAG、关键词提取、标题生成等）
- **不适用**：非 LLM 的纯本地计算；不同业务场景的独立 LLM 调用
