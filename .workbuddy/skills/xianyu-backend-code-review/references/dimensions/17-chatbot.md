# 维度 17：智能客服专项

> **编码规范引用**：coding-standards v1.3 §LLM 调用
> **配置节点**：config.yaml#chatbot
> **参考文档**：references/llm-governance-checks.md

## 触发条件
- 新增/修改 LLM API 调用时
- 智能客服（chatbot）对话逻辑变更时
- 上下文窗口管理策略调整时

## 检查规则

### 强制（P0 阻塞）
- LLM 调用必须有预算管控：单次/单用户/单日 Token 上限
- LLM 响应必须做结构化解析：提取出明确答案而非原样返回
- 上下文窗口管理：历史消息有上限条数，避免超 token 上限

### 推荐（P1 严重）
- LLM API 调用有超时保护（`asyncio.wait_for`）
- LLM 调用失败有降级策略（返回预设回复或错误提示）
- 用户输入做安全过滤（注入/越狱检测）
- 响应结果做长度/内容校验（防止非法内容输出）

### 禁止
- 无 token 预算的 LLM 调用
- 原始 LLM 响应直接返回给用户（未解析/未过滤）
- 无限增长的历史上下文窗口
- LLM API Key 硬编码在代码中

## Grep 扫描命令
```bash
# 检测 LLM API 调用
grep -rn "openai\|anthropic\|chat/completions\|llm\|ChatCompletion" src/xianyu_hunter/

# 检测缺少超时保护的 LLM 调用
grep -rn "await.*llm\|await.*chat\|await.*completion" src/xianyu_hunter/ | grep -v "wait_for"

# 检测硬编码 API Key
grep -rn "api_key\s*=\s*['\"][^'\"]+['\"]" src/xianyu_hunter/
```

## 判断标准
- 无预算管控：P0 阻塞
- 原始 LLM 响应直返：P0 阻塞
- 无超时保护：P1 严重
- API Key 硬编码：P0 阻塞（安全维度）

## 适用场景
- 智能客服/聊天模块
- LLM 辅助评估/分析的功能
- 知识库（KBManager）与 LLM 的集成

## 不适用场景
- 纯规则匹配（不调用 LLM）
- 向量检索（KBManager 搜索，不涉及 LLM context）
- 前端 UI 对话界面
