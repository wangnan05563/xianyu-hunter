# 知识库问答 · 模型自动获取与切换 · 接口与交互说明

> 适用范围：AI 服务（模型列表获取）+ 知识库问答（模型下拉切换）
> 关联代码：
> - 后端 `backend/xianyu_hunter/web/routes/api_ai.py`（`POST /api/ai/models`）
> - 后端 `backend/xianyu_hunter/modules/chatbot/{orchestrator,agent,rag_engine,intent_classifier}.py`（请求级 model 覆盖）
> - 前端 `frontend/src/api/{ai.ts,types.ts}`、`frontend/src/pages/Chatbot/hooks/{useModelList.ts,useSSEChat.ts}`、`frontend/src/pages/Chatbot/index.tsx`

---

## 1. 背景与设计决策

知识库问答原本固定使用 chatbot 配置中的 `config.llm.model`，用户无法在对话中自由选择模型。

设计上**不做全局热更新**，而是采用**请求级模型覆盖（request-level model override）**：

- 原因：`llm.model` 明确不在 chatbot 热更新白名单（`api_chatbot_config.py` 的 `_UPDATABLE_KEYS` 注释为「需要重启的字段」）。若改全局配置，多会话并发切换会互相竞态污染。
- 方案：前端把选中的 `model` 随每次对话请求上送，后端从 `ChatRequest.model` 穿透 `orchestrator → agent / rag / intent`，仅在本次请求内覆盖各自 `config.llm.model`，请求结束即失效，无跨会话副作用。

---

## 2. 后端接口

### 2.1 `POST /api/ai/models` — 获取可用模型列表

**用途**：根据服务端已配置的 `API Base URL` 与 `API Key`，请求上游 OpenAI 兼容的 `/models` 端点，解析并返回可用模型列表。

**鉴权**：沿用既有接口鉴权（业务 401 走 `detail` 透传，非 `Unauthorized` 不跳登录）。

**请求体** `ModelsRequest`：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `base_url` | `string \| null` | 否 | 若省略则用服务端已配置的 `openai_base_url` |
| `api_key` | `string \| null` | 否 | 若省略则用服务端已配置的 `openai_api_key` |

> 设计上**不要求前端回传 key**（脱敏考虑），默认复用服务端配置。前端仅在前端 AI 服务页用户手动改了 URL/Key 且未保存时，才可临时传入以预览列表。

**响应** `200 OK`：

```json
{
  "ok": true,
  "models": [
    { "id": "gpt-4o", "owned_by": "openai", "created": 1700000000 },
    { "id": "deepseek-chat", "owned_by": "deepseek", "created": 1710000000 }
  ],
  "base_url": "https://api.openai.com/v1"
}
```

- `models[].id`：模型标识，下拉选项值与对话上送值。
- `models[].owned_by` / `created`：上游原始字段，仅展示用。

**错误码**：

| HTTP | `detail` 示例 | 含义 |
|---|---|---|
| `400` | `API Base URL 未配置，请在「AI 服务」中填写` | 服务端未配置 base_url 且请求未带 |
| `400` | `API Key 未配置，请在「AI 服务」中填写` | 服务端未配置 api_key 且请求未带 |
| `400` | `API Base URL 格式无效: xxx` | URL 无法被 `httpx.URL` 解析 |
| `502` | `连接模型服务超时（>20s），请检查网络或地址` | 请求上游超时（超时 20s） |
| `502` | `连接模型服务失败: <err>` | 其他网络错误 |
| `401` / `403` | `API Key 无效或无权限访问模型列表（HTTP 401）` | key 无效或无权限 |
| `502` | `模型服务返回 502: <snippet>` | 上游非 200 且非 401/403 |
| `502` | `模型服务返回格式异常，无法解析模型列表` | 响应非 JSON 或缺少 `data[]` |

**实现要点**：
- 使用同步 `httpx.Client(timeout=20.0)`（接口为普通 `def`，非 `async def`，由 FastAPI 线程池承载）。
- 解析仅取 `data` 数组中带 `id` 的项，过滤脏数据。

---

## 3. 前端交互

### 3.1 API 层

`frontend/src/api/ai.ts`：

```ts
listModels: (body?: { base_url?: string; api_key?: string }) =>
  client.post<AIListModelsResult>('/api/ai/models', body ?? {}).then((r) => r.data)
```

`frontend/src/api/types.ts`：

```ts
export interface AIModelInfo { id: string; owned_by?: string; created?: number }
export interface AIListModelsResult { ok: boolean; models: AIModelInfo[]; base_url?: string }
```

### 3.2 `useModelList` Hook（`frontend/src/pages/Chatbot/hooks/useModelList.ts`）

职责：拉取、刷新、记忆默认模型。

**默认选中优先级**（需求：记录最后选择作为默认）：
1. `localStorage['xianyu.chatbot.model']` —— 上次用户选择（持久化）
2. `aiApi.getConfig().model` —— AI 服务配置中的默认模型
3. 列表第一个模型

**自动刷新策略**（需求：确保模型信息为最新）：
- 挂载时拉取一次
- 定时每 `60s` 拉取（`setInterval`）
- `window focus` 事件触发拉取（用户切回标签页即刷新）
- 下拉底部「刷新模型列表」手动入口

**状态**：`loading` / `error` / `models` / `selectedModel`。

**健壮性**：
- 错误态提取后端 `error.response.data.detail` 直显（URL/Key 无效等明确提示）。
- 若当前选中模型在一次刷新后已不在上游列表（如被删除），自动回退到默认逻辑，避免选到失效模型。

**持久化**：用户切换下拉时写入 `localStorage['xianyu.chatbot.model'] = selectedId`。

### 3.3 对话上送（`useSSEChat`）

`SendMessageParams` 新增 `model?: string`；`buildChatBody` 条件上送：

```ts
...(opts.model ? { model: opts.model } : {})
```

值为 `undefined` 时不上送，服务端回落到 `config.llm.model`。

### 3.4 页面 UI（`frontend/src/pages/Chatbot/index.tsx`）

- 有会话时在 `cb-content` 顶部渲染「问答模型」`Select` 下拉条（轻白极简商务风，复用 `--cb-*` 设计令牌）。
- `value={modelList.selectedModel}`，`onChange` 写入 localStorage 并更新 hook 状态。
- `handleSend` 调用 `sendMessage({ ..., model: modelList.selectedModel })` → **切换立即生效**，无需刷新或重启。

---

## 4. 端到端数据流

```
用户在「问答模型」下拉选择 M
   │  onChange → localStorage['xianyu.chatbot.model'] = M
   ▼
handleSend → sendMessage({ model: M })
   │  POST /api/chat  body.model = M
   ▼
orchestrator.orchestrate(model=M)
   ├─ intent_classify(message, model=M)   # 意图分类用 M
   ├─ _run_rag_flow(..., model=M)         # RAG 生成 / 追问用 M
   └─ _run_agent_flow(..., model=M)       # Agent 循环用 M
         └─ _call_llm(...)
               use_model = images && vision_model ? vision_model : (M or config.model)
   ▼
LLM 请求 model = use_model   # 仅本次请求生效，不改全局
```

> 视觉模型优先逻辑保留：当消息含图片且配置了 `vision_model` 时仍用 `vision_model`，否则用覆盖 `M` 或配置 `model`。

---

## 5. 测试要点

| 场景 | 预期 |
|---|---|
| AI 服务未配置 base_url/key | 下拉区显示后端 `detail` 提示，不崩页 |
| 配置正确 | 下拉列出上游 `data[].id` |
| 切换模型后发消息 | 服务端日志 `usage.model` 为该模型，回答即时切换 |
| 60s / 切回标签页 | 列表自动刷新 |
| 选中模型被上游删除 | 自动回退默认，不报错 |
| 刷新页面 | 默认选中 localStorage 记忆的模型 |

---

## 6. 验证状态（截至 2026-08-18）

- ✅ `npx tsc -b` 类型检查零错误
- ✅ `vite build` 应用层 4678 模块全部 transform 成功（仅 PWA `sw.js` 写盘受沙箱文件监视器锁拦截，属环境限制，非代码缺陷）
- ✅ 后端 6 文件 `py_compile` 全过

> 完整 bundle 需在沙箱外执行 `cd frontend && npm run build`。
