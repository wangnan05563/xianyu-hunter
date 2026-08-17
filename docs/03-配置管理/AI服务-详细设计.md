# AI 服务 - 详细设计文档

## 1. 文档元信息

| 属性     | 值                                                              |
| -------- | --------------------------------------------------------------- |
| 文档名称 | AI 服务-详细设计                                                |
| 版本     | v2.0                                                            |
| 发布日期 | 2026-07-05                                                      |
| 所属菜单 | 配置管理 / AI 服务                                              |
| 关联路由 | `/config/ai`（前端）/ `/api/ai/*`、`/api/ai/deep-analyze`、`/api/ai/seller-template-check`、`/api/ai/test-embedding`（后端） |
| 文档用途 | 开发团队技术指导 / 智能客服向量库训练素材                       |
| 维护人   | XianyuHunter 团队                                               |
| 关联代码 | `frontend/src/pages/Config/AIConfig/`、`frontend/src/api/ai.ts`、`backend/xianyu_hunter/web/routes/api_ai.py`、`backend/xianyu_hunter/web/routes/api_ai_deep.py`、`backend/xianyu_hunter/modules/chatbot/local_embedding.py`、`backend/xianyu_hunter/infra/yaml_config.py` |

> **v1.0 → v2.0 主要差异**：
>
> - **新增 Embedding 服务整套**：双后端（本地 sentence-transformers + 远程 OpenAI 兼容）、前端 `EmbeddingConfigForm` 组件、5 个 Embedding 预设、`/api/ai/test-embedding` 端点、`LocalEmbeddingBackend` 类、HF 镜像、sentence-transformers 5.x 兼容。
> - **新增 deep-analyze / seller-template-check 端点**：4 维度深度分析（盗图/损坏/一致性/模板化）、`DEEP_ANALYZE_TIMEOUT_SEC=90s`、图片哈希、卖家多商品文案样本、综合判定（reject/caution/recommend）、卖家模板化检测（**纯规则不调 LLM**）。
> - **新增 Prompt 热更新、价格区间注入、评估结果缓存**：`get_active_prompt` 运行时读取最新 Prompt；`_query_price_range` 调 `price_dashboard.sold_range`（近 30 天 → 回退全部历史）；`_get_cached_ai_eval` / `_cache_eval_result` 走 evaluations 表 `dimension_scores.ai_condition_eval`。
> - **修正 9 项描述不符**：
>   1. `deep_analyze` 超时 60s → **90s**（`DEEP_ANALYZE_TIMEOUT_SEC`）。
>   2. `seller_template_check` 实现由"调 openai_model" → **纯规则不调 LLM**。
>   3. Vision 检测由内联关键字 → **抽取为 `_is_vision_capable()` 函数 + `_VISION_CAPABLE_KEYWORDS` 元组**（位于 `api_ai.py`，被 `api_ai_deep.py` 复用）。
>   4. AIConfig 类型由 5 字段 → **补全 10 字段**（新增 5 个 `embedding_*` 字段）。
>   5. UsageStats "近 7 天趋势图" → **列表渲染**（调用分布列表 + 近 7 天趋势列表，非图表）。
>   6. 关联代码补全 `api_ai_deep.py` / `local_embedding.py` / `yaml_config.py`。
>   7. AI 端点数量由 5 个 → **6 个**（新增 `test_embedding`）。
>   8. `_call_llm_vision` 行号区间更正为 `414-522` 之外的实际位置（详见 §8）。
>   9. Prompt 来源由"Prompt 编辑器" → **`api_prompts.get_active_prompt` 热更新**。

---

## 2. 功能概述

**一句话说明**：管理 AI 总开关 + LLM 双后端配置 + Embedding 双后端配置 + 8 个 LLM 预设 + 5 个 Embedding 预设 + ModelConfigForm + EmbeddingConfigForm + UsageStats + BudgetSettings，通过 `/api/ai/*` 系列接口实现配置热更新、连接测试、用量统计、预算控制、深度分析与卖家模板化检测。

**核心价值**：
- AI 总开关（关闭时二次确认），关闭后所有 AI 功能降级到规则模式（不消耗 token）。
- **LLM 双后端**：8 个 AI 提供商预设（openai/deepseek/zhipu/moonshot/qwen/ernie/doubao/ollama），兼容 OpenAI / DeepSeek / 智谱 / Moonshot / 通义千问 / 文心一言 / 豆包 / Ollama。
- **Embedding 双后端**：本地 `sentence-transformers`（BAAI/bge-small-zh-v1.5，512 维，~95MB）或远程 OpenAI 兼容 `/v1/embeddings`，3 种模式（local / inherit / remote）。
- API Key 通过 `keyring` 加密存储，配置走 `.env` + 内存单例。
- `update_ai_config()` 热更新：内存单例 + `.env` + keyring，无需重启。
- **Vision 能力检测**：抽取为 `_is_vision_capable(model_name)` 共享函数 + `_VISION_CAPABLE_KEYWORDS` 元组（位于 `api_ai.py`，被 `api_ai_deep.py` 复用）。
- 6 个 AI 端点：`parse_task` / `evaluate_condition` / `deep_analyze` / `seller_template_check` / `test_connection` / `test_embedding`。
- **Prompt 热更新**：`api_prompts.get_active_prompt(name)` 运行时读取最新 Prompt，无需重启。
- **价格区间注入**：`_query_price_range` 调 `price_dashboard.sold_range` 注入同类物品已售价格参考。
- **评估结果缓存**：缓存在 `evaluations` 表 `dimension_scores.ai_condition_eval`，避免重复调用 LLM。
- 预算控制：`daily_token_limit` / `daily_cost_limit_usd` / `rate_limit_per_min`。
- 用量统计：今日汇总 + 最近 7 天趋势，按 endpoint / model 维度（列表渲染）。

---

## 3. 用户场景

### 场景一：配置 OpenAI Vision 评估
用户希望使用 OpenAI 进行成色评估。选择 "OpenAI" 预设（自动填入 base_url + model + vision_model），输入 API Key，点击"测试连接"验证。系统先 `aiApi.putConfig(config)` 保存配置，再调用 `/api/ai/test-connection` 发送最小化请求（`messages: [{role: user, content: "Hi"}], max_tokens: 5`，超时 15s），成功后即可在评估规则页面开启 `ai_auto_eval`。

### 场景二：切换到 DeepSeek 节省成本
用户觉得 OpenAI 太贵，切换到 DeepSeek。选择 "DeepSeek" 预设，model 自动设为 `deepseek-chat`，vision_model 也设为 `deepseek-chat`（DeepSeek 不支持 Vision，`_is_vision_capable` 返回 `False`，会降级到规则模拟）。API Key 通过 keyring 加密存储。

### 场景三：设置每日预算上限
用户担心 AI 调用失控，设置 `daily_token_limit=500000, daily_cost_limit_usd=5`。系统在每次 AI 调用前 `check_budget()`，超出预算后拒绝调用并降级到规则模式，前端用量仪表盘显示 token/cost 使用百分比（颜色：<70% 绿 / 70-90% 黄 / ≥90% 红）。

### 场景四：启用本地 Embedding 节省向量库成本
用户希望为智能客服 RAG 启用 Embedding 服务，但不想付费 OpenAI。在 "Embedding 向量服务配置" Tab 选择 "本地" 预设，model 自动填入 `BAAI/bge-small-zh-v1.5`，dimensions 自动填入 512。点击"测试连接"，系统调用 `/api/ai/test-embedding`，首次加载模型约 30s（含下载模型权重 ~95MB 到 `~/.cache/huggingface/hub`），后续启动秒级响应。前端超时 180s 兼容首次加载。

### 场景五：复用 LLM 配置作为 Embedding 后端
用户的 LLM 服务商（如智谱）同时提供 Embedding 接口，希望复用 LLM 的 base_url 和 api_key。选择 "复用 LLM" 预设，所有 Embedding 字段置空，后端走 `inherit` 模式 fallback 到 LLM 配置。前端显示蓝色 Alert 提示"将复用 LLM 的 base_url 和 api_key"。

### 场景六：深度分析某商品
用户对某商品想进行 4 维度深度鉴伪。点击"深度分析"，调用 `/api/ai/deep-analyze`（前端 90s 超时）。后端拉取商品图（最多 6 张，闲鱼图片 URL 补全为 `https://`）+ 标题 + 描述 + 卖家其他商品文案样本，调用 LLM Vision 返回 4 维度（stolen_image/damage/consistency/template）评分 + 综合判定（recommend/caution/reject）。LLM 失败时降级到规则模拟。

### 场景七：检测卖家是否为贩子
用户怀疑某卖家是贩子。调用 `/api/ai/seller-template-check`（前端 30s 超时），后端**纯规则不调 LLM**：从 DB 拉取该卖家最近 N 个商品（默认 20，3-50 可调），统计模板词频率 + 描述长度方差 + 共用句子数 → 计算 `template_score`（0-100），返回 `is_dealer` / `risk_level` / `signals` / `keyword_freq` / `shared_sentences_count` / `desc_length_variance` / `detail`。

---

## 4. 页面布局与交互

### 4.1 组件结构

```
AIConfig (页面根组件，两个 Tab)
├── Tab 1：AI 服务配置
│   ├── AI 功能总开关 Card
│   │   ├── 标题 + 状态 Tag（success/error）
│   │   └── Switch（关闭时二次确认 confirm）
│   ├── 配置区域（AI 关闭时半透明遮罩 + 不可点击）
│   │   └── ModelConfigForm
│   │       ├── 8 个 LLM 预设按钮（openai/deepseek/zhipu/moonshot/qwen/ernie/doubao/ollama）
│   │       ├── base_url Input
│   │       ├── api_key Input.Password（显示/隐藏切换 + 跳转申请页链接）
│   │       ├── model Input
│   │       ├── vision_model Input
│   │       └── 测试连接按钮 + 结果显示
│   ├── UsageStats（用量仪表盘，始终可见）
│   │   ├── 4 个 Statistic 卡片：今日调用数 / Token 数 / 费用(USD) / 费用(CNY)
│   │   ├── Token 预算进度条（getProgressColor 颜色映射）
│   │   ├── 费用预算进度条（getProgressColor 颜色映射）
│   │   ├── 「调用分布」列表（按 endpoint 维度，ENDPOINT_LABELS 中文标签）
│   │   └── 「近 7 天趋势」列表（非图表，逐日列出调用数）
│   └── BudgetSettings（预算控制区）
│       ├── daily_token_limit InputNumber
│       ├── daily_cost_limit_usd InputNumber（step=0.1）
│       ├── rate_limit_per_min InputNumber
│       └── 保存预算按钮
└── Tab 2：Embedding 向量服务配置
    └── EmbeddingConfigForm
        ├── 5 个 Embedding 预设按钮（local/openai/jina/ollama/inherit）
        ├── 模式识别提示
        │   ├── local 模式：绿色 Alert（sentence-transformers + bge-small-zh-v1.5 + ~95MB）
        │   └── inherit 模式：蓝色 Alert（将复用 LLM 配置）
        ├── embedding_base_url Input
        ├── embedding_api_key Input.Password
        ├── embedding_model Input
        ├── embedding_dimensions InputNumber（0-3072，0=自动）
        └── 测试连接按钮 + 结果显示（含 dimensions 字段）
```

### 4.2 关键交互

| 区域                  | 交互行为                                                                                                                                                                          |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| AI 总开关二次确认     | 关闭时弹出 `globalThis.confirm` 确认框，防止误操作导致所有 AI 功能降级。                                                                                                          |
| AI 关闭遮罩           | `ai_enabled=false` 时 Tab 1 配置区域半透明 + 不可点击，覆盖"AI 功能已关闭"提示。Tab 2 Embedding 配置不受影响（独立于 AI 总开关）。                                                  |
| LLM 预设切换          | 点击预设按钮调用 `applyPreset`：先 `aiApi.putConfig(patch)` 落库再更新本地状态，确保 UI 与后端一致。`message.success("已切换到 xxx 预设")`。                                          |
| Embedding 预设切换    | 点击预设按钮调用 `applyEmbeddingPreset`：同样先 `putConfig` 落库再更新本地状态。                                                                                                  |
| API Key 脱敏          | `GET /api/ai/config` 返回的 api_key 与 embedding_api_key 仅保留末 4 位（`****xxxx`）；前端回传时若以 `****` 开头视为未修改，跳过更新；空字符串清除 keyring。                       |
| API Key 申请页跳转    | `findPresetByBaseUrl` 反查预设，若有 `apiKeyUrl` 则在 api_key 输入框下方显示"获取 API Key"链接。                                                                                  |
| 测试连接（LLM）       | 先 `aiApi.putConfig(config)` 保存当前配置，再 `aiApi.testConnection()` 发送最小化请求（`messages: [{role: user, content: "Hi"}], max_tokens: 5`，15s 超时）。                       |
| 测试连接（Embedding） | 先 `aiApi.putConfig(config)` 保存当前配置，再 `aiApi.testEmbedding()` 发送最小化请求（`input: ["hi"]`，180s 超时覆盖本地首次加载模型）。返回含 `dimensions` 字段。                  |
| 用量仪表盘始终可见    | 即使 AI 关闭，用量统计仍可见（历史数据），便于查看过往消耗。                                                                                                                       |
| 预算进度条颜色        | `getProgressColor(pct)` 函数：<70% 绿色（`green`）、70-90% 黄色（`orange`）、≥90% 红色（`red`）。                                                                                  |
| UsageStats 渲染形态   | **列表渲染**而非图表：调用分布逐条列出 endpoint 及次数，近 7 天趋势逐日列出日期与调用数。`formatTokens` 函数格式化 token 数（>1000 显示 1.xK）。                                    |
| Embedding 模式识别    | 前端按字段自动识别：base_url 空 + model 有值 → `local`；全空 → `inherit`；base_url 有值 → `remote`。                                                                              |
| Embedding dimensions  | `embedding_dimensions=0` 时后端不传 `dimensions` 参数，兼容 Ollama（不支持指定维度）。                                                                                            |

---

## 5. 接口定义

### 5.1 AI 配置与连接测试 API（`api_ai.py`，prefix=`/api/ai`，tags=`ai`）

| 方法 | 路径                       | 用途                          | 请求参数                                                                                                                                                                                                              | 响应字段                                                                                                                                                                                                   |
| ---- | -------------------------- | ----------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GET  | `/api/ai/config`           | 获取 AI 配置（API Key 脱敏）  | 无                                                                                                                                                                                                                    | `{ai_enabled, base_url, api_key(脱敏), model, vision_model, has_key, embedding_base_url, embedding_api_key(脱敏), embedding_model, embedding_dimensions, embedding_has_key}`                                |
| PUT  | `/api/ai/config`           | 保存 AI 配置（热更新）        | Body (`AIConfigBody`): `{ai_enabled?, base_url?, api_key?, model?, vision_model?, embedding_base_url?, embedding_api_key?, embedding_model?, embedding_dimensions?}`                                                  | `{ok, message}`                                                                                                                                                                                            |
| POST | `/api/ai/test-connection`  | 测试 LLM 服务连接             | 无（用已保存配置）                                                                                                                                                                                                    | `{ok: true, model}` 或 `{ok: false, detail}`                                                                                                                                                               |
| POST | `/api/ai/test-embedding`   | 测试 Embedding 服务连接       | 无（用已保存配置；本地首次加载模型约 30s）                                                                                                                                                                            | `{ok: true, dimensions, model?}` 或 `{ok: false, detail}`                                                                                                                                                  |
| GET  | `/api/ai/usage`            | 获取今日用量 + 7 天趋势       | 无                                                                                                                                                                                                                    | `{today: {...}, budget: {...}, history: [...]}`                                                                                                                                                            |
| PUT  | `/api/ai/budget`           | 更新预算配置                  | Body: `{daily_token_limit?, daily_cost_limit_usd?, rate_limit_per_min?}`                                                                                                                                              | `{ok, message}`                                                                                                                                                                                            |

### 5.2 AI 业务调用 API（`api_ai.py`，prefix=`/api/ai`，tags=`ai`）

| 方法 | 路径                          | 用途                       | 请求参数                                                                                                  | 响应字段                                                                                                                                                                                                                                                                                                                  |
| ---- | ----------------------------- | -------------------------- | --------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| POST | `/api/ai/parse-task`          | 自然语言 → 结构化任务      | Body (`ParseTaskBody`): `{text: str(1-2000)}`                                                             | `{keyword, name, min_price, max_price, mode, exclude_words, notes, reason, source}`                                                                                                                                                                                                                                       |
| POST | `/api/ai/evaluate-condition`  | 多模态成色评估             | Body (`ConditionEvalRequest`): `{item_id, evaluation_id?}`                                               | `{verdict, condition_score, appearance_score, consistency_score, price_reasonability, risk_signals, reason, detail, source, cached, price_range?}`                                                                                                                                                                        |

### 5.3 AI 深度分析与卖家模板检测 API（`api_ai_deep.py`，prefix=`/api/ai`，tags=`ai-deep`）

| 方法 | 路径                              | 用途                       | 请求参数                                                                                                  | 响应字段                                                                                                                                                                                                                                                                                                                  |
| ---- | --------------------------------- | -------------------------- | --------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| POST | `/api/ai/deep-analyze`            | 单商品 4 维度深度分析      | Body (`DeepAnalyzeRequest`): `{item_id: str, checks?: list[str]}`（checks 默认 `["stolen_image","damage","consistency","template"]`） | `{stolen_image, damage, consistency, template, overall_verdict, overall_score, summary, source, detail?}`（详见 §6.4）                                                                                                                                                                                                    |
| POST | `/api/ai/seller-template-check`   | 卖家文案模板化检测（**纯规则不调 LLM**） | Body (`SellerTemplateCheckRequest`): `{seller_id: str, sample_size?: int(3-50, 默认 20)}`                | `{seller_id, sample_count, template_score, is_dealer, risk_level, signals, keyword_freq, shared_sentences_count, desc_length_variance, detail}`                                                                                                                                                                           |

### 5.4 端点超时与模型矩阵

| 端点                    | 后端超时              | 前端超时 | 模型                     | 是否调 LLM | 说明                                                              |
| ----------------------- | --------------------- | -------- | ------------------------ | ---------- | ----------------------------------------------------------------- |
| `parse_task`            | `HTTP_TIMEOUT_SEC=25s`| 30s      | `openai_model`           | 是         | 文本 LLM 调用，失败降级 `_rule_parse`                             |
| `evaluate_condition`    | `VISION_TIMEOUT_SEC=60s` | 60s   | `openai_vision_model`    | 是         | Vision LLM 调用，失败降级 `_rule_eval_condition`                  |
| `deep_analyze`          | `DEEP_ANALYZE_TIMEOUT_SEC=90s` | 90s | `openai_vision_model`    | 是         | 多图 Vision 推理较慢；纯文本模型跳过图片                          |
| `seller_template_check` | 同步规则计算          | 30s      | —                        | **否**     | 纯规则（高频模板词 + 描述长度方差 + 共用句子检测），不消耗 token  |
| `test_connection`       | 15s                   | 30s      | `openai_model`           | 是         | 最小化请求 `max_tokens=5`                                         |
| `test_embedding`        | 同步加载+1 次推理     | 180s     | `embedding_model`        | 是         | 本地首次加载模型约 30s，180s 覆盖首次下载                        |

---

## 6. 数据结构

### 6.1 前端 AIConfig 类型（`frontend/src/api/types.ts`）

```typescript
interface AIConfig {
  ai_enabled: boolean
  base_url: string
  api_key: string        // 脱敏值 ****xxxx
  model: string
  vision_model: string
  has_key: boolean
  // Embedding 字段（v2.0 新增）
  embedding_base_url: string
  embedding_api_key: string  // 脱敏值 ****xxxx
  embedding_model: string
  embedding_dimensions: number  // 0-3072，0=自动（兼容 Ollama）
  embedding_has_key: boolean
}
```

> **v1.0 修正**：原 AIConfig 类型仅 5 字段，缺 5 个 `embedding_*` 字段与 `has_key`。v2.0 补全为 10 字段 + 2 个布尔状态字段。

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
    total_cost_cny: number  // = total_cost_usd * 7.2
    by_endpoint: Record<string, number>  // 调用分布列表数据源
    by_model: Record<string, number>
  }
  budget: {
    daily_token_limit: number
    daily_cost_limit_usd: number
    rate_limit_per_min: number
    token_usage_pct: number  // 0-100
    cost_usage_pct: number   // 0-100
  }
  history: Array<{
    date: string
    calls: number
    tokens: number
    cost_usd: number
  }>
}
```

> **v1.0 修正**：v1.0 称"近 7 天趋势图"为图表渲染，实际 UsageStats 组件用**列表**渲染（逐日列出日期+调用数），并非图表。

### 6.3 前端 DeepAnalyzeResult / SellerTemplateCheckResult 类型（`frontend/src/api/types.ts`）

```typescript
interface DeepCheckResult {
  score: number          // 1-10
  risk_level: 'low' | 'medium' | 'high'
  signals?: string[]
  damages?: string[]
  inconsistencies?: string[]
  detail: string
}

interface DeepAnalyzeResult {
  stolen_image: DeepCheckResult
  damage: DeepCheckResult
  consistency: DeepCheckResult
  template: DeepCheckResult
  overall_verdict: 'recommend' | 'caution' | 'reject'
  overall_score: number
  summary: string
  source: 'llm' | 'rule'
  detail?: string
}

interface SellerTemplateCheckResult {
  seller_id: string
  sample_count: number
  template_score: number       // 0-100，越高越像贩子
  is_dealer: boolean
  risk_level: 'low' | 'medium' | 'high'
  signals: string[]
  keyword_freq: Record<string, number>
  shared_sentences_count: number
  desc_length_variance: number
  detail: string
}

interface AITestEmbeddingResult {
  ok: boolean
  dimensions?: number
  model?: string
  detail?: string
}
```

### 6.4 8 个 LLM 提供商预设（`frontend/src/pages/Config/AIConfig/constants.ts`）

| 预设      | base_url                                          | model              | vision_model            | apiKeyUrl                              |
| --------- | ------------------------------------------------- | ------------------ | ----------------------- | -------------------------------------- |
| `openai`  | `https://api.openai.com/v1`                       | `gpt-4o-mini`      | `gpt-4o`                | https://platform.openai.com/api-keys   |
| `deepseek`| `https://api.deepseek.com/v1`                     | `deepseek-chat`    | `deepseek-chat`（不支持）| https://platform.deepseek.com/api_keys |
| `zhipu`   | `https://open.bigmodel.cn/api/paas/v4`            | `glm-4-flash`      | `glm-4v-flash`          | https://open.bigmodel.cn/usercenter/apikeys |
| `moonshot`| `https://api.moonshot.cn/v1`                      | `moonshot-v1-8k`   | `moonshot-v1-8k`（不支持）| https://platform.moonshot.cn/console/api-keys |
| `qwen`    | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus`      | `qwen-vl-plus`          | https://dashscope.console.aliyun.com/apiKey |
| `ernie`   | `https://qianfan.baidubce.com/v2`                 | `ernie-speed-128k` | `ernie-vision-4k`       | https://console.bce.baidu.com/qianfan/ais/console/applicationConsole/application |
| `doubao`  | `https://ark.cn-beijing.volces.com/api/v3`        | `doubao-pro-32k`   | `doubao-vision-pro-32k` | https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey |
| `ollama`  | `http://localhost:11434/v1`                       | `qwen2.5:7b`       | `llava:7b`              | —（本地部署无需 Key）                  |

### 6.5 5 个 Embedding 预设（`constants.ts`，v2.0 新增）

| 预设       | embedding_base_url                                  | embedding_model            | embedding_dimensions | 模式识别    | 说明                                                  |
| ---------- | --------------------------------------------------- | -------------------------- | -------------------- | ----------- | ----------------------------------------------------- |
| `local`    | `""`（空）                                          | `BAAI/bge-small-zh-v1.5`   | `512`                | local       | 本地 sentence-transformers，~95MB，中文优化           |
| `openai`   | `https://api.openai.com/v1`                         | `text-embedding-3-small`   | `1536`               | remote      | OpenAI Embedding                                      |
| `jina`     | `https://api.jina.ai/v1`                            | `jina-embeddings-v2-base-zh` | `768`              | remote      | Jina 中文 Embedding                                   |
| `ollama`   | `http://localhost:11434/v1`                         | `nomic-embed-text`         | `768`                | remote      | 本地 Ollama Embedding（dimensions=0 不传该参数）      |
| `inherit`  | `""`（空）                                          | `""`（空）                 | `0`                  | inherit     | 复用 LLM 的 base_url + api_key（fallback 到 cfg.kb.embedding_model） |

### 6.6 后端 Settings（BaseSettings）

位置：`backend/xianyu_hunter/config.py`（从 `.env` 读取）

| 字段                     | 来源      | 说明                                       |
| ------------------------ | --------- | ------------------------------------------ |
| `ai_enabled`             | `.env`    | AI 总开关                                  |
| `openai_base_url`        | `.env`    | OpenAI 兼容端点                            |
| `openai_api_key`         | keyring   | LLM API Key（加密存储）                    |
| `openai_model`           | `.env`    | 文本模型                                   |
| `openai_vision_model`    | `.env`    | Vision 模型                               |
| `embedding_base_url`     | `.env`    | Embedding 端点（空=local/inherit 模式）   |
| `embedding_api_key`      | keyring   | Embedding API Key（加密存储）              |
| `embedding_model`        | `.env`    | Embedding 模型名                           |
| `embedding_dimensions`   | `.env`    | 向量维度（0=不传 dimensions 参数，兼容 Ollama） |

### 6.7 后端 Pydantic 配置（`yaml_config.py`）

`ChatbotKBConfig` 中 Embedding 相关字段（test_embedding_connection 的 fallback 来源）：

| 字段                    | 类型 | 默认值                  | 校验范围     | 说明                                                          |
| ----------------------- | ---- | ----------------------- | ------------ | ------------------------------------------------------------- |
| `embedding_model`       | str  | `text-embedding-3-small`| —            | OpenAI Embedding 模型名（test-embedding 端点 fallback）       |
| `embedding_dimensions`  | int  | `1536`                  | 256-3072     | 向量维度                                                      |
| `chunk_size`            | int  | `500`                   | 100-2000     | 分块字符数                                                    |
| `chunk_overlap`         | int  | `50`                    | 0-500        | 分块重叠字符数                                                |

> 说明：`test_embedding_connection` 端点优先使用 `Settings.embedding_model` / `embedding_dimensions`，若为空则 fallback 到 `cfg.kb.embedding_model` / `embedding_dimensions`。

### 6.8 端点中文标签映射（`constants.ts`）

```typescript
export const ENDPOINT_LABELS: Record<string, string> = {
  parse_task: '自然语言解析',
  evaluate_condition: '成色评估',
  deep_analyze: '深度分析',
  seller_template_check: '模板检测',
  test_connection: '连接测试',
}
```

### 6.9 工具函数（`constants.ts`）

| 函数                  | 签名                                  | 说明                                                                  |
| --------------------- | ------------------------------------- | --------------------------------------------------------------------- |
| `formatTokens(n)`     | `(n: number) => string`               | >1000 显示 `1.xK`，>1000000 显示 `1.xM`                               |
| `getProgressColor(pct)`| `(pct: number) => string`             | <70% `green`、70-90% `orange`、≥90% `red`                            |
| `findPresetByBaseUrl` | `(url: string) => Preset \| undefined`| 反查预设获取 apiKeyUrl 链接                                           |
| `findEmbeddingPresetByBaseUrl` | `(url: string) => EmbeddingPreset \| undefined` | 反查 Embedding 预设                                          |

---

## 7. 业务逻辑

### 7.1 AI 总开关与降级机制

位置：`backend/xianyu_hunter/web/routes/api_ai.py` `_check_ai_enabled()` 函数

- 所有 AI 端点（除 config GET/PUT）调用前先执行 `_check_ai_enabled()`。
- `ai_enabled=false` 时抛 HTTP 403，`detail="AI 功能已关闭，请在「AI 服务」配置页面开启"`。
- 前端关闭时二次确认（`globalThis.confirm`），防止误操作。
- 关闭后所有 AI 功能降级到规则模式（`_rule_parse` / `_rule_eval_condition` / `_rule_deep_analyze`），不消耗 token。
- `seller_template_check` 本身就是纯规则，无需降级。

### 7.2 配置存储与热更新

#### 存储分层
- **`.env` 文件**：`ai_enabled` / `openai_base_url` / `openai_model` / `openai_vision_model` / `embedding_base_url` / `embedding_model` / `embedding_dimensions`。
- **keyring**：`openai_api_key` / `embedding_api_key`（加密存储，不写入 .env 明文）。
- **内存单例**：`Settings()` 单例，启动时从 .env + keyring 加载。

#### `update_ai_config()` 热更新
位置：`backend/xianyu_hunter/config.py`

1. 更新内存单例字段。
2. 写入 `.env` 文件（API Key 除外）。
3. API Key 单独写入 keyring。
4. 下次 `get_settings()` 返回新配置，无需重启服务。

#### API Key 特殊处理
- 前端回传 `****xxxx`（脱敏值）→ 视为未修改，跳过。
- 前端回传空字符串 → 清除 keyring 中的 Key。
- 前端回传新值 → 写入 keyring。

### 7.3 Vision 能力检测（v2.0 抽取为共享函数）

位置：`backend/xianyu_hunter/web/routes/api_ai.py`

```python
_VISION_CAPABLE_KEYWORDS: tuple[str, ...] = (
    "vision", "gpt-4o", "gpt-4-vision", "qvq", "qwen-vl",
    "glm-4v", "claude-3", "opus", "sonnet", "haiku",
)

def _is_vision_capable(model_name: str | None) -> bool:
    if not model_name:
        return False
    name = model_name.lower()
    return any(kw in name for kw in _VISION_CAPABLE_KEYWORDS)
```

- **设计动机**：升级模型时只需在此处追加关键字，所有调用点（`api_ai._call_llm_vision`、`api_ai_deep._call_llm_deep_analyze`）自动生效。
- 纯文本模型（`deepseek-chat` / `moonshot-v1-8k` / `gpt-3.5-turbo` 等）服务端 schema 不支持 `image_url` content block，强行传图会被报 400（`unknown variant \`image_url\``）导致降级。
- `vision_capable=false` 时：
  - `_call_llm_vision`：prompt 追加"当前模型不支持图片分析，请仅基于标题、描述、价格评估"。
  - `_call_llm_deep_analyze`：prompt 追加"当前模型不支持图片分析...盗图/损坏/一致性维度因无图无法判断，对应 score 取默认值 5、risk_level='medium'"，并跳过图片传入。

> **v1.0 修正**：v1.0 将关键字内联在 `_call_llm_vision` 函数中（第 441-446 行），v2.0 已抽取为模块级常量 + 共享函数，被 `api_ai_deep.py` 复用。

### 7.4 Prompt 热更新（v2.0 新增）

位置：`backend/xianyu_hunter/web/routes/api_ai.py`（P1-8 Prompt 热更新）

```python
from xianyu_hunter.web.routes.api_prompts import get_active_prompt

system_prompt = get_active_prompt("parse_task") or _SYSTEM_PROMPT
```

- **设计动机**：用户在「Prompt 编辑器」修改 Prompt 后，无需重启服务即可生效。
- `get_active_prompt(name)` 从 DB 读取最新启用的 Prompt 版本；返回 `None` 时 fallback 到代码内置 `_SYSTEM_PROMPT`。
- 影响端点：`parse_task`（`_call_llm`）、`evaluate_condition`（`_call_llm_vision`）。
- `deep_analyze` 的 Prompt 暂未接入热更新（复杂多模态 Prompt 较稳定）。

### 7.5 价格区间注入（v2.0 新增）

位置：`backend/xianyu_hunter/web/routes/api_ai.py` `_query_price_range()` 函数

- **设计动机**：评估商品时注入同类物品已售价格区间，让 LLM 判断价格合理性有依据。
- 数据来源：`price_dashboard.sold_range(keyword, days=30)`，从 sold_items 表查近 30 天已售商品价格区间。
- **回退策略**：近 30 天无数据时，回退到全部历史已售数据。
- 注入位置：`_call_llm_vision` 的 user message 中追加"同类物品近 30 天已售价格区间：¥min - ¥max（共 N 件）"。
- `_rule_eval_condition` 规则模拟也支持 price_range 参数，保证降级时一致性。
- 响应字段 `price_range?: {min, max, count, source}` 返回给前端展示。

### 7.6 评估结果缓存（v2.0 新增）

位置：`backend/xianyu_hunter/web/routes/api_ai.py` `_get_cached_ai_eval()` / `_cache_eval_result()` 函数

- **设计动机**：同一商品多次评估时避免重复调用 LLM 浪费 token。
- 缓存位置：`evaluations` 表 `dimension_scores` 字段（JSON），key 为 `ai_condition_eval`。
- **缓存命中**：`_get_cached_ai_eval(item_id)` 返回缓存结果，响应 `cached=true`，`source="llm_cached"`。
- **缓存写入**：`_cache_eval_result(item_id, result)` 将评估结果写入 evaluations 表。
- **失效策略**：商品信息变更（标题/描述/图片）后，前端可强制刷新（传 `evaluation_id` 新建评估记录）。
- 缓存与降级正交：缓存命中不消耗 token，未命中走 LLM 失败再降级规则。

### 7.7 6 个 AI 端点详解

#### 7.7.1 `parse_task` 自然语言解析
- **超时**：`HTTP_TIMEOUT_SEC=25s`（与前端 AbortController 30s 对齐）。
- **模型**：`openai_model`。
- **流程**：
  1. `_check_ai_enabled()` 检查总开关。
  2. 检查 `openai_api_key` 是否配置。
  3. `check_budget()` 预算检查。
  4. **Prompt 热更新**：`get_active_prompt("parse_task") or _SYSTEM_PROMPT`。
  5. `httpx.Client(timeout=25s)` 调用 OpenAI 兼容 chat completions。
  6. `record_usage("parse_task", model, resp_data)` 记录用量。
  7. `_parse_llm_response(r)` 解析 JSON（剥离 ```json 代码块）。
  8. 失败时降级到 `_rule_parse(text)` 规则解析（覆盖 80% 常见场景，返回 `source="rule"`）。

#### 7.7.2 `evaluate_condition` 多模态成色评估
- **超时**：`VISION_TIMEOUT_SEC=60s`。
- **模型**：`openai_vision_model`。
- **流程**：
  1. **缓存检查**：`_get_cached_ai_eval(item_id)` 命中则直接返回（`cached=true`）。
  2. **价格区间注入**：`_query_price_range()` 调 `price_dashboard.sold_range` 获取同类已售价格。
  3. `_call_llm_vision()` 调用 LLM Vision（最多 4 张图，闲鱼图片 URL 补全为 `https://`）。
  4. `record_usage("evaluate_condition", vision_model, resp_data)`。
  5. **缓存写入**：`_cache_eval_result(item_id, result)`。
  6. 失败降级到 `_rule_eval_condition()`（含 price_range 支持）。

#### 7.7.3 `deep_analyze` 4 维度深度分析
- **超时**：`DEEP_ANALYZE_TIMEOUT_SEC=90s`（v1.0 文档说 60s 是错的，多图 Vision 推理较慢）。
- **模型**：`openai_vision_model`。
- **位置**：`backend/xianyu_hunter/web/routes/api_ai_deep.py`。
- **请求体**：
  ```python
  class DeepAnalyzeRequest(BaseModel):
      item_id: str
      checks: list[str] = ["stolen_image", "damage", "consistency", "template"]
  ```
- **4 维度检查**：
  1. **盗图检测**（stolen_image）：图片 URL 域名 + 数量 + 水印检测。
  2. **物理损坏识别**（damage）：图片中可见划痕/磕碰/裂纹/变色。
  3. **描述与图片一致性**（consistency）：标题型号与图片展示、成色描述与实际。
  4. **文案模板化检测**（template）：模板词堆砌 + 缺个性化细节 + 贩子特征。
- **图片处理**：最多 6 张图，闲鱼 URL 补全为 `https://`，纯文本模型跳过图片。
- **卖家样本**：`_get_seller_items()` 仅当 checks 含 `template` 且有 `seller_id` 时查询卖家其他商品（最多 5 个，每个描述截前 100 字）。
- **图片哈希**：`_compute_image_url_hash()` MD5 截前 12 位，用于盗图检测。
- **综合判定**（`_compute_overall_verdict`）：
  - `has_high`（任一维度 score≤3）→ `reject`。
  - `has_medium`（3<score<7）→ `caution`。
  - 全 `low`（score≥7）→ `recommend`。
- **降级**：`_rule_deep_analyze()` 基于关键词启发式判断，精度低于 LLM 但保证开箱可用。
- **响应归一化**：`_normalize_deep_result()` 统一 LLM 与规则输出字段格式。

#### 7.7.4 `seller_template_check` 卖家模板化检测（纯规则）
- **超时**：同步规则计算（毫秒级），前端 30s。
- **模型**：无（**纯规则不调 LLM**，v1.0 文档说用 `openai_model` 是错的）。
- **位置**：`backend/xianyu_hunter/web/routes/api_ai_deep.py`。
- **请求体**：
  ```python
  class SellerTemplateCheckRequest(BaseModel):
      seller_id: str
      sample_size: int = Field(default=20, ge=3, le=50)
  ```
- **算法**：
  1. `_get_seller_items(seller_id, sample_size)` 从 DB 拉取卖家最近 N 个商品。
  2. `_count_template_keywords()` 统计高频模板词（"99新"/"仅拆封"/"未使用"/"自用"/"国行"/"全新"/"正品"/"专柜"/"代购" 等）。
  3. `_compute_desc_length_variance()` 计算描述长度方差（贩子文案长度高度一致）。
  4. `_find_shared_sentences()` 检测多商品共用句子。
  5. `_compute_template_score()` 综合计算 `template_score`（0-100）。
  6. `_infer_template_risk_level()` 推断 `risk_level`（low/medium/high）。
- **响应字段**：
  ```json
  {
    "seller_id": "xxx",
    "sample_count": 20,
    "template_score": 75,
    "is_dealer": true,
    "risk_level": "high",
    "signals": ["高频模板词5个", "描述长度方差低", "3个共用句子"],
    "keyword_freq": {"99新": 15, "仅拆封": 10, "未使用": 8},
    "shared_sentences_count": 3,
    "desc_length_variance": 12.5,
    "detail": "..."
  }
  ```

#### 7.7.5 `test_connection` 连接测试
- **超时**：15s。
- **模型**：`openai_model`。
- **请求**：最小化 `{messages: [{role: user, content: "Hi"}], max_tokens: 5}`。
- **流程**：先 `putConfig` 保存当前配置 → 调 `test_ai_connection`。
- **响应**：成功 `{ok: true, model}`，失败 `{ok: false, detail}`。

#### 7.7.6 `test_embedding` Embedding 连接测试（v2.0 新增）
- **超时**：前端 180s（覆盖本地首次加载模型 ~30s + 模型下载 ~95MB）。
- **位置**：`backend/xianyu_hunter/web/routes/api_ai.py` `test_embedding_connection` 端点。
- **流程**：
  1. 优先使用 `Settings.embedding_*` 字段；为空时 fallback 到 `cfg.kb.embedding_model` / `embedding_dimensions`。
  2. **本地模式**（base_url 空 + model 有值）：调 `_test_local_embedding()` → `LocalEmbeddingBackend.embed("hi")`。
  3. **远程模式**（base_url 有值）：调 `_test_remote_embedding()` → httpx POST `/v1/embeddings`。
  4. `dimensions=0` 时不传 `dimensions` 参数（兼容 Ollama）。
- **响应**：成功 `{ok: true, dimensions, model?}`，失败 `{ok: false, detail}`。

### 7.8 Embedding 双后端架构（v2.0 新增）

#### 7.8.1 三种模式识别

| 模式     | 识别条件                                    | 后端                | 说明                                                  |
| -------- | ------------------------------------------- | ------------------- | ----------------------------------------------------- |
| `local`  | `embedding_base_url` 空 + `embedding_model` 有值 | `LocalEmbeddingBackend` | 本地 sentence-transformers，~95MB，无需外部服务       |
| `inherit`| `embedding_base_url` + `embedding_model` 全空 | 复用 LLM 配置       | Fallback 到 `openai_base_url` + `openai_api_key` + `cfg.kb.embedding_model` |
| `remote` | `embedding_base_url` 有值                   | HTTP `/v1/embeddings` | 兼容 OpenAI / Jina / Ollama 等                        |

#### 7.8.2 `LocalEmbeddingBackend` 类

位置：`backend/xianyu_hunter/modules/chatbot/local_embedding.py`

```python
class LocalEmbeddingBackend:
    def __init__(self, model_name: str) -> None: ...
    @property
    def dimensions(self) -> int: ...
    def _ensure_loaded(self) -> None: ...   # 懒加载（线程安全）
    def embed(self, text: str) -> list[float]: ...
    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...  # batch_size=32
```

**关键设计**：

1. **HF 镜像**（必须模块顶部设置）：
   ```python
   os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
   ```
   国内访问 huggingface.co 经常超时（WinError 10060），默认走 hf-mirror.com 镜像；用户已设置时尊重其选择。**必须在 import sentence_transformers 之前执行**，否则模型配置文件下载仍走原域名。

2. **懒加载策略**：模型在首次 `embed` 时加载（避免启动卡顿），同一进程内复用实例。

3. **线程安全**：`threading.Lock` 保护 `_ensure_loaded`，避免多线程同时加载模型。

4. **device='cpu' 显式指定**：避免在无 CUDA 环境下自动探测失败。

5. **sentence-transformers 5.x 兼容**：
   ```python
   get_dim = getattr(
       self._model,
       "get_embedding_dimension",  # 5.x 新名
       getattr(self._model, "get_sentence_embedding_dimension", None),  # 4.x 旧名
   )
   ```
   5.x 重命名 `get_sentence_embedding_dimension` → `get_embedding_dimension`，用 `getattr` fallback 兼容新旧版本。

6. **延迟导入**：`from sentence_transformers import SentenceTransformer` 在 `_ensure_loaded` 内导入，避免未安装 torch 时整个模块 import 失败（用户使用 HTTP backend 时无需安装 torch）。

7. **batch_size=32**：sentence-transformers 内部已做 batch 优化，比循环单条快 10-50 倍。

8. **normalize_embeddings=False**：保留原始向量，避免与 L2 距离计算不一致。

### 7.9 预算控制机制

位置：`backend/xianyu_hunter/infra/ai_usage.py`

- `check_budget()`：每次 AI 调用前检查，返回 `(allowed: bool, reason: str)`。
- 三道防线：
  1. `daily_token_limit`：每日 Token 上限。
  2. `daily_cost_limit_usd`：每日费用上限（USD）。
  3. `rate_limit_per_min`：每分钟调用频率上限。
- 超出任一限制 → 拒绝调用，降级到规则模式。
- `record_usage(endpoint, model, resp_data)`：调用后记录用量。
- `seller_template_check` 不调 LLM，不消耗 token，无需预算检查。

### 7.10 用量统计

- `get_daily_summary()`：今日汇总（calls/tokens/cost，按 endpoint/model 维度）。
- `get_recent_usage(7)`：最近 7 天趋势（逐日数据）。
- `get_budget_config()`：预算配置 + 使用百分比。
- 费用换算：`total_cost_cny = total_cost_usd * 7.2`（固定汇率，仅用于展示）。
- 前端 UsageStats 组件用**列表渲染**：
  - 「调用分布」列表：逐条列出 endpoint 及次数（用 `ENDPOINT_LABELS` 中文标签）。
  - 「近 7 天趋势」列表：逐日列出日期与调用数（非图表）。

### 7.11 校验规则
- **API Key 脱敏**：`GET /api/ai/config` 返回 `****xxxx`（仅末 4 位）。
- **API Key 未修改检测**：前端回传 `****` 开头视为未修改。
- **预算值范围**：`daily_token_limit > 0`、`daily_cost_limit_usd > 0`、`rate_limit_per_min > 0`。
- **text 长度**：`parse_task` 的 text 字段 `min_length=1, max_length=2000`。
- **sample_size 范围**：`seller_template_check` 的 `sample_size` 字段 `ge=3, le=50`。
- **embedding_dimensions 范围**：`0-3072`，`0` 表示不传该参数（兼容 Ollama）。

---

## 8. 关键代码位置

### 8.1 前端代码

| 文件路径                                                  | 行号/章节 | 说明                                                         |
| --------------------------------------------------------- | --------- | ------------------------------------------------------------ |
| `frontend/src/pages/Config/AIConfig/index.tsx`            | 全文      | 页面根组件，两个 Tab（AI 服务配置 + Embedding 向量服务配置）  |
| `frontend/src/pages/Config/AIConfig/index.tsx`            | `handleToggleAI` | AI 开关二次确认                                        |
| `frontend/src/pages/Config/AIConfig/index.tsx`            | `applyPreset` | LLM 预设切换（先落库再更新 UI）                          |
| `frontend/src/pages/Config/AIConfig/index.tsx`            | `applyEmbeddingPreset` | Embedding 预设切换                              |
| `frontend/src/pages/Config/AIConfig/index.tsx`            | `handleTestConnection` | LLM 测试连接                                    |
| `frontend/src/pages/Config/AIConfig/index.tsx`            | `handleTestEmbeddingConnection` | Embedding 测试连接                    |
| `frontend/src/pages/Config/AIConfig/index.tsx`            | `handleSaveBudget` | 保存预算                                             |
| `frontend/src/pages/Config/AIConfig/components/ModelConfigForm.tsx` | 全文 | LLM 配置表单（8 预设 + base_url/api_key/model/vision_model + 测试连接） |
| `frontend/src/pages/Config/AIConfig/components/EmbeddingConfigForm.tsx` | 全文 | Embedding 配置表单（5 预设 + 4 字段 + 模式识别提示 + 测试连接） |
| `frontend/src/pages/Config/AIConfig/components/UsageStats.tsx` | 全文 | 用量仪表盘（4 Statistic 卡片 + 进度条 + 调用分布列表 + 7 天趋势列表） |
| `frontend/src/pages/Config/AIConfig/components/BudgetSettings.tsx` | 全文 | 预算控制区（3 InputNumber + 保存按钮）                    |
| `frontend/src/pages/Config/AIConfig/constants.ts`         | `PRESETS` | 8 个 LLM 提供商预设（含 apiKeyUrl）                          |
| `frontend/src/pages/Config/AIConfig/constants.ts`         | `EMBEDDING_PRESETS` | 5 个 Embedding 预设                                |
| `frontend/src/pages/Config/AIConfig/constants.ts`         | `ENDPOINT_LABELS` | 端点中文标签（5 个）                                  |
| `frontend/src/pages/Config/AIConfig/constants.ts`         | `formatTokens` / `getProgressColor` / `findPresetByBaseUrl` / `findEmbeddingPresetByBaseUrl` | 工具函数 |
| `frontend/src/api/ai.ts`                                  | 全文      | `aiApi` 完整接口封装（含 `testEmbedding` 180s 超时、`deepAnalyze` 90s、`sellerTemplateCheck` 30s） |
| `frontend/src/api/types.ts`                               | `AIConfig` / `AIUsage` / `DeepAnalyzeResult` / `SellerTemplateCheckResult` / `AITestEmbeddingResult` / `DeepCheckResult` | 类型定义 |

### 8.2 后端代码

| 文件路径                                                  | 行号/章节 | 说明                                                         |
| --------------------------------------------------------- | --------- | ------------------------------------------------------------ |
| `backend/xianyu_hunter/web/routes/api_ai.py`                  | `_VISION_CAPABLE_KEYWORDS` | Vision 关键字白名单元组（10 个关键字）            |
| `backend/xianyu_hunter/web/routes/api_ai.py`                  | `_is_vision_capable(model_name)` | Vision 能力检测共享函数（被 api_ai_deep 复用）    |
| `backend/xianyu_hunter/web/routes/api_ai.py`                  | `_check_ai_enabled()` | AI 开关检查（403）                                     |
| `backend/xianyu_hunter/web/routes/api_ai.py`                  | `HTTP_TIMEOUT_SEC=25.0` | parse_task 超时                                        |
| `backend/xianyu_hunter/web/routes/api_ai.py`                  | `VISION_TIMEOUT_SEC=60.0` | evaluate_condition 超时                                |
| `backend/xianyu_hunter/web/routes/api_ai.py`                  | `ParseTaskBody` | Pydantic 请求模型（text 1-2000）                          |
| `backend/xianyu_hunter/web/routes/api_ai.py`                  | `_call_llm` | 文本 LLM 调用 + Prompt 热更新                              |
| `backend/xianyu_hunter/web/routes/api_ai.py`                  | `_rule_parse` | 规则解析 fallback                                         |
| `backend/xianyu_hunter/web/routes/api_ai.py`                  | `_call_llm_vision` | Vision LLM 调用（60s，含 price_range 注入）          |
| `backend/xianyu_hunter/web/routes/api_ai.py`                  | `_query_price_range` | 价格区间查询（调 price_dashboard.sold_range）          |
| `backend/xianyu_hunter/web/routes/api_ai.py`                  | `_get_cached_ai_eval` / `_cache_eval_result` | 评估结果缓存（evaluations 表）             |
| `backend/xianyu_hunter/web/routes/api_ai.py`                  | `_rule_eval_condition` | 规则评估 fallback（含 price_range 支持）              |
| `backend/xianyu_hunter/web/routes/api_ai.py`                  | `AIConfigBody` | Pydantic 配置模型（含 5 个 embedding_* 字段）            |
| `backend/xianyu_hunter/web/routes/api_ai.py`                  | `_mask_key` | API Key 脱敏                                              |
| `backend/xianyu_hunter/web/routes/api_ai.py`                  | `get_ai_config` | 获取 AI 配置（LLM + Embedding 双组，含 has_key）        |
| `backend/xianyu_hunter/web/routes/api_ai.py`                  | `save_ai_config` | 保存 AI 配置（热更新 + keyring）                        |
| `backend/xianyu_hunter/web/routes/api_ai.py`                  | `test_ai_connection` | LLM 连接测试（15s，最小化请求）                      |
| `backend/xianyu_hunter/web/routes/api_ai.py`                  | `_test_local_embedding` | 本地 Embedding 测试（调 LocalEmbeddingBackend）     |
| `backend/xianyu_hunter/web/routes/api_ai.py`                  | `_test_remote_embedding` | 远程 Embedding 测试（dimensions=0 不传，兼容 Ollama） |
| `backend/xianyu_hunter/web/routes/api_ai.py`                  | `test_embedding_connection` | Embedding 连接测试端点（settings 优先，空时 fallback cfg.kb） |
| `backend/xianyu_hunter/web/routes/api_ai.py`                  | `get_ai_usage` | 用量统计（today/budget/history，CNY=USD*7.2）          |
| `backend/xianyu_hunter/web/routes/api_ai.py`                  | `update_ai_budget` | 预算更新                                                  |
| `backend/xianyu_hunter/web/routes/api_ai_deep.py`             | `DEEP_ANALYZE_TIMEOUT_SEC=90.0` | 深度分析超时（v1.0 文档说 60s 是错的）          |
| `backend/xianyu_hunter/web/routes/api_ai_deep.py`             | `_RULE_DETAIL_PREFIX` | 规则模拟前缀常量                                         |
| `backend/xianyu_hunter/web/routes/api_ai_deep.py`             | `DeepAnalyzeRequest` | Pydantic 请求模型（item_id + checks 默认 4 项）        |
| `backend/xianyu_hunter/web/routes/api_ai_deep.py`             | `SellerTemplateCheckRequest` | Pydantic 请求模型（seller_id + sample_size 3-50 默认 20） |
| `backend/xianyu_hunter/web/routes/api_ai_deep.py`             | `_DEEP_ANALYZE_PROMPT` | 4 维度深度分析 Prompt                                    |
| `backend/xianyu_hunter/web/routes/api_ai_deep.py`             | `_call_llm_deep_analyze` | LLM Vision 深度分析（90s，最多 6 张图，纯文本模型跳过图片） |
| `backend/xianyu_hunter/web/routes/api_ai_deep.py`             | `_rule_check_stolen_image` / `_rule_check_damage` / `_rule_check_consistency` / `_rule_check_template` | 4 维度规则模拟 |
| `backend/xianyu_hunter/web/routes/api_ai_deep.py`             | `_compute_overall_verdict` | 综合判定（has_high→reject, has_medium→caution, 全 low→recommend） |
| `backend/xianyu_hunter/web/routes/api_ai_deep.py`             | `_rule_deep_analyze` | 规则模拟深度分析 fallback                                |
| `backend/xianyu_hunter/web/routes/api_ai_deep.py`             | `_normalize_deep_result` | 响应归一化（统一 LLM 与规则输出）                       |
| `backend/xianyu_hunter/web/routes/api_ai_deep.py`             | `_compute_image_url_hash` | 图片哈希（MD5 截前 12 位）                              |
| `backend/xianyu_hunter/web/routes/api_ai_deep.py`             | `_get_seller_items` | 卖家商品查询（仅 template 检查时）                       |
| `backend/xianyu_hunter/web/routes/api_ai_deep.py`             | `@router.post("/deep-analyze")` | 深度分析端点                                       |
| `backend/xianyu_hunter/web/routes/api_ai_deep.py`             | `_count_template_keywords` / `_compute_desc_length_variance` / `_find_shared_sentences` / `_compute_template_score` / `_infer_template_risk_level` | 卖家模板化检测算法 |
| `backend/xianyu_hunter/web/routes/api_ai_deep.py`             | `@router.post("/seller-template-check")` | 卖家模板化检测端点（**纯规则不调 LLM**）        |
| `backend/xianyu_hunter/modules/chatbot/local_embedding.py`    | 全文      | `LocalEmbeddingBackend` 类（懒加载 + 线程安全 + 5.x 兼容）   |
| `backend/xianyu_hunter/modules/chatbot/local_embedding.py`    | 模块顶部 | `os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")` |
| `backend/xianyu_hunter/modules/chatbot/local_embedding.py`    | `_ensure_loaded` | 懒加载模型（threading.Lock 保护）                       |
| `backend/xianyu_hunter/modules/chatbot/local_embedding.py`    | `embed` / `embed_batch` | 同步向量化接口（batch_size=32）                       |
| `backend/xianyu_hunter/infra/yaml_config.py`                  | `ChatbotKBConfig` | KB 配置（embedding_model/embedding_dimensions 等默认值） |
| `backend/xianyu_hunter/config.py`                             | `update_ai_config` | 配置热更新（内存单例 + .env + keyring）                  |
| `backend/xianyu_hunter/infra/ai_usage.py`                     | `check_budget` / `record_usage` | 预算检查 + 用量记录                          |

---

## 9. 常见问题 FAQ

### Q1：8 个 LLM 提供商都有哪些？
**A**：openai / deepseek / zhipu / moonshot / qwen / ernie / doubao / ollama。前 7 个是云服务，ollama 是本地部署。每个预设含 base_url / model / vision_model / apiKeyUrl，切换预设仅修改前三个字段，API Key 需用户自行填写（点击"获取 API Key"跳转对应服务商申请页）。

### Q2：5 个 Embedding 预设都有哪些？
**A**：
- `local`：本地 sentence-transformers，模型 `BAAI/bge-small-zh-v1.5`，512 维，~95MB，无需外部服务。
- `openai`：OpenAI Embedding，`text-embedding-3-small`，1536 维。
- `jina`：Jina 中文 Embedding，`jina-embeddings-v2-base-zh`，768 维。
- `ollama`：本地 Ollama，`nomic-embed-text`，768 维（dimensions=0 不传该参数兼容）。
- `inherit`：复用 LLM 的 base_url + api_key（fallback 到 cfg.kb.embedding_model）。

### Q3：API Key 安全吗？会被泄露吗？
**A**：安全。LLM API Key 与 Embedding API Key 都通过 keyring 加密存储，不写入 .env 明文。`GET /api/ai/config` 返回时仅保留末 4 位（`****xxxx`）。前端回传 `****` 开头视为未修改，跳过更新；空字符串清除 keyring。

### Q4：AI 关闭后会影响什么？
**A**：所有 AI 功能降级到规则模式，不消耗任何 token。包括：自然语言解析走 `_rule_parse`、成色评估走 `_rule_eval_condition`、深度分析走 `_rule_deep_analyze`。`seller_template_check` 本身就是纯规则，不受影响。用量仪表盘仍可见历史数据。可随时重新开启。Tab 2 Embedding 配置独立于 AI 总开关。

### Q5：Vision 能力是怎么检测的？
**A**：通过 `_is_vision_capable(model_name)` 共享函数判断（位于 `api_ai.py`，被 `api_ai_deep.py` 复用）。模型名（小写）包含 `_VISION_CAPABLE_KEYWORDS` 中任一关键字（`vision` / `gpt-4o` / `gpt-4-vision` / `qvq` / `qwen-vl` / `glm-4v` / `claude-3` / `opus` / `sonnet` / `haiku`）即视为支持 Vision。纯文本模型（如 `deepseek-chat`）会跳过图片传入，避免 400 报错。

### Q6：预算超出后会怎样？
**A**：`check_budget()` 返回 `(False, reason)`，AI 调用被拒绝并降级到规则模式。三道防线：`daily_token_limit`（每日 Token）、`daily_cost_limit_usd`（每日费用 USD）、`rate_limit_per_min`（每分钟频率）。任一超出即拒绝。`seller_template_check` 不调 LLM，不消耗 token，无需预算检查。

### Q7：测试连接发送什么请求？
**A**：
- **LLM**：最小化请求 `{messages: [{role: user, content: "Hi"}], max_tokens: 5}`，超时 15s。成功返回 `{ok: true, model}`，失败返回 `{ok: false, detail}`。测试前会先 `putConfig` 保存当前配置。
- **Embedding**：最小化请求 `{input: ["hi"]}`，前端超时 180s（覆盖本地首次加载模型 ~30s + 下载 ~95MB）。返回 `{ok: true, dimensions, model?}`。`dimensions=0` 时不传 `dimensions` 参数（兼容 Ollama）。

### Q8：成色评估的图片是怎么传入的？
**A**：最多 4 张图片，以 `image_url` 字段传入 LLM。闲鱼图片 URL 常为协议相对路径（`//img.alicdn.com/...`），需补全为 `https://`。纯文本模型不传图，避免 400 报错。同时注入同类物品已售价格区间（`_query_price_range` 调 `price_dashboard.sold_range`）。

### Q9：评估结果会缓存吗？
**A**：会。`_get_cached_ai_eval(item_id)` 从 evaluations 表 `dimension_scores.ai_condition_eval` 取缓存，命中返回 `cached=true`，不消耗 token。`_cache_eval_result` 写入缓存。商品信息变更后可强制刷新（传新 `evaluation_id`）。

### Q10：parse_task 失败后会怎样？
**A**：降级到 `_rule_parse(text)` 规则解析。规则解析覆盖 80% 常见场景（中文价格描述 + 关键词抽取），返回结果带 `source: "rule"` 标识。LLM 失败原因可能是：未配置 Key、预算超限、网络超时（>25s）、API 返回非 JSON。Prompt 走热更新（`get_active_prompt("parse_task")`），用户修改 Prompt 后无需重启。

### Q11：deep_analyze 的 90s 超时为什么这么长？
**A**：多图 Vision 推理较慢，最多 6 张图片 + 4 维度分析（盗图/损坏/一致性/模板）。`DEEP_ANALYZE_TIMEOUT_SEC=90.0`，前端 90s 超时同步对齐。LLM 失败时降级到 `_rule_deep_analyze` 规则模拟（基于关键词启发式）。

### Q12：seller_template_check 真的不调 LLM 吗？
**A**：是的，**纯规则不调 LLM**。算法：从 DB 拉取卖家最近 N 个商品（默认 20，3-50 可调）→ 统计模板词频率 + 描述长度方差 + 共用句子数 → 计算 `template_score`（0-100）。响应包含 `is_dealer` / `risk_level` / `signals` / `keyword_freq` / `shared_sentences_count` / `desc_length_variance` / `detail`。不消耗 token，无需预算检查。

### Q13：本地 Embedding 模型加载很慢怎么办？
**A**：首次加载约 30s（含下载模型权重 ~95MB 到 `~/.cache/huggingface/hub`），后续启动秒级响应。已设置 `HF_ENDPOINT=https://hf-mirror.com` 镜像应对国内访问。前端 `testEmbedding` 180s 超时覆盖首次加载。同一进程内复用实例（懒加载 + threading.Lock）。

### Q14：sentence-transformers 5.x 兼容怎么处理？
**A**：5.x 重命名 `get_sentence_embedding_dimension` → `get_embedding_dimension`。代码用 `getattr` fallback：
```python
get_dim = getattr(
    self._model,
    "get_embedding_dimension",  # 5.x 新名
    getattr(self._model, "get_sentence_embedding_dimension", None),  # 4.x 旧名
)
```

### Q15：embedding_dimensions=0 是什么意思？
**A**：表示"不传 dimensions 参数"，兼容 Ollama（不支持指定维度）。后端 `_test_remote_embedding` 检测 `dimensions=0` 时不传该参数。前端 `InputNumber` 范围 0-3072，预设 `ollama` 默认 0。

### Q16：用量统计的 CNY 是怎么算的？
**A**：`total_cost_cny = total_cost_usd * 7.2`，固定汇率 7.2。仅用于展示，实际计费按服务商 USD 价格。`get_daily_summary()` 返回今日汇总，`get_recent_usage(7)` 返回最近 7 天趋势。前端用**列表渲染**（非图表）：调用分布列表 + 近 7 天趋势列表。

---

## 阶段交接声明

- 当前阶段：AI 服务详细设计文档 v2.0 重写 ✅ 已完成
- 下一阶段：AI 服务需求规格文档 v1.0 编写
- 下一阶段智能体：文档编写智能体
- 下一阶段技能：文档编写
- 交接上下文：AI 服务详细设计 v2.0 已完成，涵盖 2 个前端 Tab（AI 服务配置 + Embedding 向量服务配置）、3 个后端 router（`api_ai.py` 配置/业务 + `api_ai_deep.py` 深度分析 + `api_prompts` Prompt 热更新）、6 个 AI 端点（parse_task/evaluate_condition/deep_analyze/seller_template_check/test_connection/test_embedding）、8 个 LLM 预设 + 5 个 Embedding 预设、双后端架构（本地 sentence-transformers + 远程 OpenAI 兼容）、4 维度深度分析、卖家模板化检测（纯规则）、Prompt 热更新、价格区间注入、评估结果缓存、Vision 能力检测共享函数、预算控制三道防线、16 条 FAQ。关键修正：deep_analyze 超时 60s→90s；seller_template_check 调 LLM→纯规则；Vision 检测内联→共享函数；AIConfig 5 字段→10 字段；UsageStats 趋势图→列表渲染；新增 Embedding 服务整套；新增 deep-analyze/seller-template-check 端点；新增 Prompt 热更新/价格区间注入/评估结果缓存。
