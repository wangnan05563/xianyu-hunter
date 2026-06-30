# AI 服务 - 详细设计文档

## 1. 文档元信息

| 字段 | 值 |
|------|------|
| 文档名称 | AI 服务-详细设计 |
| 版本 | v1.0 |
| 创建日期 | 2026-06-29 |
| 所属菜单 | 配置管理 / AI 服务 |
| 关联路由 | `/config/ai`（前端） / `/api/ai/*`（后端） |
| 关联代码 | `frontend/src/pages/Config/AIConfig/index.tsx`、`frontend/src/pages/Config/AIConfig/constants.ts`、`src/xianyu_hunter/web/routes/api_ai.py`、`src/xianyu_hunter/config.py` |

## 2. 功能概述

**一句话说明**：管理 AI 总开关 + 8 个 AI 提供商预设 + ModelConfigForm + UsageStats + BudgetSettings，通过 `/api/ai/*` 系列接口实现配置热更新、连接测试、用量统计、预算控制。

**核心价值**：
- AI 总开关（关闭时二次确认），关闭后所有 AI 功能降级到规则模式
- 8 个 AI 提供商预设：openai/deepseek/zhipu/moonshot/qwen/ernie/doubao/ollama
- API Key 通过 keyring 加密存储，配置走 `.env` + 内存单例
- `update_ai_config()` 热更新：内存单例 + `.env`/keyring，无需重启
- Vision 能力检测：通过模型名关键词判断（gpt-4o/vision/qwen-vl 等）
- 5 个 AI 端点：parse_task/evaluate_condition/deep_analyze/seller_template_check/test_connection
- 预算控制：daily_token_limit / daily_cost_limit_usd / rate_limit_per_min
- 用量统计：今日汇总 + 最近 7 天趋势，按 endpoint/model 维度

## 3. 用户场景

### 场景 1：配置 OpenAI Vision 评估
用户希望使用 OpenAI 进行成色评估。选择 "OpenAI" 预设（自动填入 base_url + model + vision_model），输入 API Key，点击"测试连接"验证。系统调用 `/api/ai/test-connection` 发送最小化请求，成功后即可在评估规则页面开启 `ai_auto_eval`。

### 场景 2：切换到 DeepSeek 节省成本
用户觉得 OpenAI 太贵，切换到 DeepSeek。选择 "DeepSeek" 预设，model 自动设为 `deepseek-chat`，vision_model 也设为 `deepseek-chat`（DeepSeek 不支持 Vision，会降级到规则模拟）。API Key 通过 keyring 加密存储。

### 场景 3：设置每日预算上限
用户担心 AI 调用失控，设置 `daily_token_limit=500000, daily_cost_limit_usd=5`。系统在每次 AI 调用前 `check_budget()`，超出预算后拒绝调用并降级到规则模式，前端用量仪表盘显示 token/cost 使用百分比。

## 4. 页面布局与交互

### 4.1 组件结构
```
AIConfig (页面根组件)
├── AI 功能总开关 Card
│   ├── 标题 + 状态 Tag（success/error）
│   └── Switch（关闭时二次确认 confirm）
├── 配置区域（AI 关闭时半透明遮罩）
│   └── ModelConfigForm
│       ├── 8 个预设按钮（openai/deepseek/zhipu/moonshot/qwen/ernie/doubao/ollama）
│       ├── base_url Input
│       ├── api_key Input.Password（显示/隐藏切换）
│       ├── model Input
│       ├── vision_model Input
│       └── 测试连接按钮 + 结果显示
├── UsageStats（用量仪表盘，始终可见）
│   ├── 今日调用数 / Token 数 / 费用（USD + CNY）
│   ├── 预算使用百分比进度条（token + cost）
│   ├── 按 endpoint 维度统计
│   ├── 按 model 维度统计
│   └── 最近 7 天趋势图
└── BudgetSettings（预算控制区）
    ├── daily_token_limit InputNumber
    ├── daily_cost_limit_usd InputNumber
    ├── rate_limit_per_min InputNumber
    └── 保存预算按钮
```

### 4.2 关键交互
- **AI 总开关二次确认**：关闭时弹出 `globalThis.confirm` 确认框，防止误操作导致所有 AI 功能降级。
- **AI 关闭遮罩**：`ai_enabled=false` 时配置区域半透明 + 不可点击，覆盖"AI 功能已关闭"提示。
- **预设切换**：点击预设按钮调用 `applyPreset`，先 `aiApi.putConfig(patch)` 落库再更新本地状态，确保 UI 与后端一致。
- **API Key 脱敏**：`GET /api/ai/config` 返回的 api_key 仅保留末 4 位（`****xxxx`）；前端回传时若以 `****` 开头视为未修改，跳过更新。
- **测试连接**：先 `aiApi.putConfig(config)` 保存当前配置，再 `aiApi.testConnection()` 发送最小化请求（`messages: [{role: user, content: "Hi"}], max_tokens: 5`）。
- **用量仪表盘始终可见**：即使 AI 关闭，用量统计仍可见（历史数据），便于查看过往消耗。
- **预算进度条颜色**：`getProgressColor(pct)` 函数，<70% 绿色、70-90% 黄色、≥90% 红色。

## 5. 接口定义

| 方法 | 路径 | 用途 | 请求参数 | 响应字段 |
|------|------|------|----------|----------|
| GET | `/api/ai/config` | 获取 AI 配置（API Key 脱敏） | 无 | `{ai_enabled, base_url, api_key(脱敏), model, vision_model, has_key}` |
| PUT | `/api/ai/config` | 保存 AI 配置（热更新） | `{ai_enabled?, base_url?, api_key?, model?, vision_model?}` | `{ok, message}` |
| POST | `/api/ai/test-connection` | 测试 AI 服务连接 | 无（用已保存配置） | `{ok, model} 或 {ok: false, detail}` |
| POST | `/api/ai/parse-task` | 自然语言 → 结构化任务 | `{text: string}` | `{keyword, name, min_price, max_price, mode, exclude_words, notes, reason, source}` |
| POST | `/api/ai/evaluate-condition` | 多模态成色评估 | `{item_id, evaluation_id?}` | `{verdict, condition_score, appearance_score, consistency_score, price_reasonability, risk_signals, reason, detail, source, cached, price_range?}` |
| GET | `/api/ai/usage` | 获取今日用量 + 7 天趋势 | 无 | `{today: {...}, budget: {...}, history: [...]}` |
| PUT | `/api/ai/budget` | 更新预算配置 | `{daily_token_limit?, daily_cost_limit_usd?, rate_limit_per_min?}` | `{ok, message}` |

## 6. 数据结构

### 6.1 前端 AIConfig 类型
```typescript
interface AIConfig {
  ai_enabled: boolean
  base_url: string
  api_key: string        // 脱敏值 ****xxxx
  model: string
  vision_model: string
}
```

### 6.2 前端 AIUsage 类型
```typescript
interface AIUsage {
  today: {
    date: string
    total_calls: number
    total_input_tokens: number
    total_output_tokens: number
    total_tokens: number
    total_cost_usd: number
    total_cost_cny: number
    by_endpoint: Record<string, number>
    by_model: Record<string, number>
  }
  budget: {
    daily_token_limit: number
    daily_cost_limit_usd: number
    rate_limit_per_min: number
    token_usage_pct: number
    cost_usage_pct: number
  }
  history: Array<{...}>
}
```

### 6.3 8 个 AI 提供商预设

位置：`frontend/src/pages/Config/AIConfig/constants.ts` 第 3-60 行

| 预设 | base_url | model | vision_model |
|------|----------|-------|--------------|
| `openai` | `https://api.openai.com/v1` | `gpt-4o-mini` | `gpt-4o` |
| `deepseek` | `https://api.deepseek.com/v1` | `deepseek-chat` | `deepseek-chat`（不支持 Vision） |
| `zhipu` | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-flash` | `glm-4v-flash` |
| `moonshot` | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` | `moonshot-v1-8k` |
| `qwen` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` | `qwen-vl-plus` |
| `ernie` | `https://qianfan.baidubce.com/v2` | `ernie-speed-128k` | `ernie-vision-4k` |
| `doubao` | `https://ark.cn-beijing.volces.com/api/v3` | `doubao-pro-32k` | `doubao-vision-pro-32k` |
| `ollama` | `http://localhost:11434/v1` | `qwen2.5:7b` | `llava:7b` |

### 6.4 后端 Settings（BaseSettings）

位置：`src/xianyu_hunter/config.py`（从 `.env` 读取）

| 字段 | 来源 | 说明 |
|------|------|------|
| `ai_enabled` | `.env` | AI 总开关 |
| `openai_base_url` | `.env` | OpenAI 兼容端点 |
| `openai_api_key` | keyring | API Key（加密存储） |
| `openai_model` | `.env` | 文本模型 |
| `openai_vision_model` | `.env` | Vision 模型 |

### 6.5 端点中文标签映射

位置：`frontend/src/pages/Config/AIConfig/constants.ts` 第 63-69 行

```typescript
export const ENDPOINT_LABELS: Record<string, string> = {
  parse_task: '自然语言解析',
  evaluate_condition: '成色评估',
  deep_analyze: '深度分析',
  seller_template_check: '模板检测',
  test_connection: '连接测试',
}
```

## 7. 业务逻辑

### 7.1 AI 总开关与降级机制

位置：`src/xianyu_hunter/web/routes/api_ai.py` `_check_ai_enabled()` 函数（第 38-46 行）

- 所有 AI 端点（除 config GET/PUT）调用前先执行 `_check_ai_enabled()`
- `ai_enabled=false` 时抛 HTTP 403，detail="AI 功能已关闭，请在「AI 服务」配置页面开启"
- 前端关闭时二次确认（`globalThis.confirm`），防止误操作
- 关闭后所有 AI 功能降级到规则模式（`_rule_parse` / `_rule_eval_condition`），不消耗 token

### 7.2 配置存储与热更新

#### 存储分层
- **`.env` 文件**：`ai_enabled` / `openai_base_url` / `openai_model` / `openai_vision_model`
- **keyring**：`openai_api_key`（加密存储，不写入 .env 明文）
- **内存单例**：`Settings()` 单例，启动时从 .env + keyring 加载

#### `update_ai_config()` 热更新
位置：`src/xianyu_hunter/config.py`

1. 更新内存单例字段
2. 写入 `.env` 文件（API Key 除外）
3. API Key 单独写入 keyring
4. 下次 `get_settings()` 返回新配置，无需重启服务

#### API Key 特殊处理
- 前端回传 `****xxxx`（脱敏值）→ 视为未修改，跳过
- 前端回传空字符串 → 清除 keyring 中的 Key
- 前端回传新值 → 写入 keyring

### 7.3 Vision 能力检测

位置：`src/xianyu_hunter/web/routes/api_ai.py` `_call_llm_vision()` 函数（第 441-446 行）

```python
model_name = (settings.openai_vision_model or "").lower()
vision_capable = any(
    kw in model_name
    for kw in ("vision", "gpt-4o", "gpt-4-vision", "qvq", "qwen-vl", "glm-4v", "claude-3", "opus", "sonnet", "haiku")
)
```

- 纯文本模型（deepseek-chat / gpt-3.5-turbo 等）不支持 `image_url` 字段
- 强行传图会被服务商报 400，导致降级规则模拟
- `vision_capable=false` 时，prompt 中追加"当前模型不支持图片分析，请仅基于标题、描述、价格评估"

### 7.4 5 个 AI 端点

| 端点 | 用途 | 超时 | 模型 |
|------|------|------|------|
| `parse_task` | 自然语言 → 结构化任务 | 25s | `openai_model` |
| `evaluate_condition` | 多模态成色评估 | 60s | `openai_vision_model` |
| `deep_analyze` | 深度分析（成色/真伪/性价比） | 60s | `openai_vision_model` |
| `seller_template_check` | 卖家模板检测 | 25s | `openai_model` |
| `test_connection` | 连接测试 | 15s | `openai_model` |

### 7.5 预算控制机制

位置：`src/xianyu_hunter/infra/ai_usage.py`

- `check_budget()`：每次 AI 调用前检查，返回 `(allowed: bool, reason: str)`
- 三道防线：
  1. `daily_token_limit`：每日 Token 上限
  2. `daily_cost_limit_usd`：每日费用上限（USD）
  3. `rate_limit_per_min`：每分钟调用频率上限
- 超出任一限制 → 拒绝调用，降级到规则模式
- `record_usage(endpoint, model, resp_data)`：调用后记录用量

### 7.6 用量统计
- `get_daily_summary()`：今日汇总（calls/tokens/cost，按 endpoint/model 维度）
- `get_recent_usage(7)`：最近 7 天趋势
- `get_budget_config()`：预算配置
- 费用换算：`total_cost_cny = total_cost_usd * 7.2`

### 7.7 LLM 调用流程（以 parse_task 为例）
1. `_check_ai_enabled()` 检查总开关
2. 检查 `openai_api_key` 是否配置
3. `check_budget()` 预算检查
4. 从 Prompt 编辑器读取最新 `parse_task` prompt（支持热更新）
5. `httpx.Client(timeout=25s)` 调用 OpenAI 兼容 chat completions
6. `record_usage("parse_task", model, resp_data)` 记录用量
7. `_parse_llm_response(r)` 解析 JSON（剥离 ```json 代码块）
8. 失败时降级到 `_rule_parse(text)` 规则解析

### 7.8 校验规则
- **API Key 脱敏**：`GET /api/ai/config` 返回 `****xxxx`（仅末 4 位）
- **API Key 未修改检测**：前端回传 `****` 开头视为未修改
- **预算值范围**：`daily_token_limit > 0`、`daily_cost_limit_usd > 0`、`rate_limit_per_min > 0`
- **text 长度**：`parse_task` 的 text 字段 `min_length=1, max_length=2000`

## 8. 关键代码位置

| 文件路径 | 行号 | 说明 |
|----------|------|------|
| `frontend/src/pages/Config/AIConfig/index.tsx` | 12-244 | 页面根组件 + 状态管理 |
| `frontend/src/pages/Config/AIConfig/index.tsx` | 70-86 | `handleToggleAI` AI 开关二次确认 |
| `frontend/src/pages/Config/AIConfig/index.tsx` | 95-111 | `applyPreset` 预设切换（先落库再更新 UI） |
| `frontend/src/pages/Config/AIConfig/index.tsx` | 114-135 | `handleTestConnection` 测试连接 |
| `frontend/src/pages/Config/AIConfig/index.tsx` | 143-160 | `handleSaveBudget` 保存预算 |
| `frontend/src/pages/Config/AIConfig/constants.ts` | 3-60 | `PRESETS` 8 个 AI 提供商预设 |
| `frontend/src/pages/Config/AIConfig/constants.ts` | 63-69 | `ENDPOINT_LABELS` 端点中文标签 |
| `frontend/src/pages/Config/AIConfig/constants.ts` | 72-84 | `formatTokens` / `getProgressColor` 工具函数 |
| `src/xianyu_hunter/web/routes/api_ai.py` | 38-46 | `_check_ai_enabled` AI 开关检查 |
| `src/xianyu_hunter/web/routes/api_ai.py` | 835-886 | `get_ai_config` / `save_ai_config`（含 keyring 处理） |
| `src/xianyu_hunter/web/routes/api_ai.py` | 889-930 | `test_ai_connection` 连接测试 |
| `src/xianyu_hunter/web/routes/api_ai.py` | 941-975 | `get_ai_usage` 用量统计 |
| `src/xianyu_hunter/web/routes/api_ai.py` | 978-989 | `update_ai_budget` 预算更新 |
| `src/xianyu_hunter/web/routes/api_ai.py` | 414-522 | `_call_llm_vision` Vision 调用 + 能力检测 |
| `src/xianyu_hunter/web/routes/api_ai.py` | 107-160 | `_call_llm` 文本 LLM 调用 |

## 9. 常见问题 FAQ

### Q1：8 个 AI 提供商都有哪些？
**A**：openai/deepseek/zhipu/moonshot/qwen/ernie/doubao/ollama。前 7 个是云服务，ollama 是本地部署。每个预设含 base_url/model/vision_model，切换预设仅修改这三个字段，API Key 需用户自行填写。

### Q2：API Key 安全吗？会被泄露吗？
**A**：安全。API Key 通过 keyring 加密存储，不写入 .env 明文。`GET /api/ai/config` 返回时仅保留末 4 位（`****xxxx`）。分享配置时凭据字段会被替换为 `***`。前端回传 `****` 开头视为未修改，跳过更新。

### Q3：AI 关闭后会影响什么？
**A**：所有 AI 功能降级到规则模式，不消耗任何 token。包括：自然语言解析走 `_rule_parse`、成色评估走 `_rule_eval_condition`、深度分析/模板检测不可用。用量仪表盘仍可见历史数据。可随时重新开启。

### Q4：Vision 能力是怎么检测的？
**A**：通过模型名关键词判断。包含 `vision`/`gpt-4o`/`gpt-4-vision`/`qvq`/`qwen-vl`/`glm-4v`/`claude-3`/`opus`/`sonnet`/`haiku` 之一的视为支持 Vision。纯文本模型（如 deepseek-chat）会跳过图片传入，避免 400 报错。

### Q5：预算超出后会怎样？
**A**：`check_budget()` 返回 `(False, reason)`，AI 调用被拒绝并降级到规则模式。三道防线：daily_token_limit（每日 Token）、daily_cost_limit_usd（每日费用 USD）、rate_limit_per_min（每分钟频率）。任一超出即拒绝。

### Q6：测试连接发送什么请求？
**A**：最小化请求 `{messages: [{role: user, content: "Hi"}], max_tokens: 5}`，超时 15s。成功返回 `{ok: true, model}`，失败返回 `{ok: false, detail}`。测试前会先 `putConfig` 保存当前配置，确保测试用最新参数。

### Q7：成色评估的图片是怎么传入的？
**A**：最多 4 张图片，以 `image_url` 字段传入 LLM。闲鱼图片 URL 常为协议相对路径（`//img.alicdn.com/...`），需补全为 `https://`。纯文本模型不传图，避免 400 报错。

### Q8：用量统计的 CNY 是怎么算的？
**A**：`total_cost_cny = total_cost_usd * 7.2`，固定汇率 7.2。仅用于展示，实际计费按服务商 USD 价格。`get_daily_summary()` 返回今日汇总，`get_recent_usage(7)` 返回最近 7 天趋势。

### Q9：预设切换会立即保存吗？
**A**：是。`applyPreset` 先 `aiApi.putConfig(patch)` 落库，再更新本地状态。这样确保 UI 与后端一致，避免刷新页面后预设丢失。message.success 提示"已切换到 xxx 预设"。

### Q10：parse_task 失败后会怎样？
**A**：降级到 `_rule_parse(text)` 规则解析。规则解析覆盖 80% 常见场景（中文价格描述 + 关键词抽取），返回结果带 `source: "rule"` 标识。前端可据此显示"规则解析结果"提示。LLM 失败原因可能是：未配置 Key、预算超限、网络超时（>25s）、API 返回非 JSON。
