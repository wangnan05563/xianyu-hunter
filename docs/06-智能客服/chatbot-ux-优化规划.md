# 智能客服 UX 优化规划

> **状态**：仅规划，未实现
> **范围**：基于现有 17_xianyu 智能客服（chromaDB + OpenAI 兼容 LLM + FastAPI + React + antd 马卡龙风格）做 UX 系统性优化
> **基线版本**：基于 2026-06-29 代码现状，含已落地的 vision_model 图片输入能力
> **目标**：不引入大改动、不重构，按 5 大类共 15 个子功能给出可分批落地的设计方案

---

## 0. 现状盘点与设计原则

### 0.1 已有能力（避免重复造轮子）

| 能力 | 现状 | 位置 |
|---|---|---|
| 会话列表/分页/创建/重命名/删除 | 完整 | [index.tsx](file:///d:/code/otherProjects/17_xianyu/frontend/src/pages/Chatbot/index.tsx) Sider |
| FAQ 库（增删改查/匹配） | 完整 | `api_chatbot.py:list_faqs` + Config.tsx |
| 消息列表分页（before_id 游标） | 完整 | `api_chatbot.py:list_messages` |
| 助手消息点赞/点踩 + 文字反馈 | 完整 | `AssistantMessage.tsx:handleFeedback` |
| 转人工（点踩触发 / 主动 / 关键词） | 完整 | `escalation.py` |
| 会话记录复制导出 | 完整 | `AssistantMessage.tsx:copySession` |
| 图片上传/拖拽/粘贴（vision） | 已落地 | [index.tsx](file:///d:/code/otherProjects/17_xianyu/frontend/src/pages/Chatbot/index.tsx) cb-image-* |
| 输入框 TextArea + 工具开关 | 基础 | index.tsx cb-input-area |
| 引用来源 / 工具调用次数 / 降级标记 | 完整 | AssistantMessage.tsx |
| 流式 SSE 推送 | 完整 | useSSEChat.ts |
| 知识库管理（构建/回滚/版本） | 完整 | Config.tsx「知识库管理」Tab |

### 0.2 缺失项（按 5 大类对照）

| 大类 | 缺失子功能 |
|---|---|
| 1. 首屏引导 | 功能介绍卡片、常见问题快捷入口、使用指南提示、个性化欢迎语 |
| 2. 历史对话 | 跨会话搜索、收藏/置顶、消息搜索、本地存储 |
| 3. 交互体验 | 自动聚焦、发送/已读状态、消息撤回、快捷回复、图文混排气泡 |
| 4. 功能入口 | 帮助中心入口、人工转接快速按钮（已有但隐藏） |
| 5. 反馈机制 | 评分（已有"正/负"）缺 1-5 星、文字反馈（已有）需加强 |

### 0.3 设计原则（沿用项目硬约束）

- **简约至上**：复用现有 SessionList、AssistantMessage、EmptyIllustration，不另起新组件结构
- **马卡龙风格延续**：所有新增 UI 沿用 `--cb-pink-light/-deep` `--cb-cyan` 等色板，不引入新色
- **不引入角色权限**：项目当前单实例单用户，user 角色与 admin 角色等同
- **不引入大依赖**：能用 antd 现成组件解决就不引第三方（如 react-intersection-observer 用 antd InfiniteScroll 替代）
- **后端优先复用现有路由**：仅在缺失时新增，避免接口膨胀
- **云端同步：本机即云端**：本地数据库 = 云端，多设备需求为"后续扩展"区，本规划不实现

---

## 1. 对话框初始引导优化

### 1.1 目标与场景

- **触发场景**：
  1. 用户首次打开 `/chatbot`（无任何会话）
  2. 用户首次进入某个新会话（消息数为 0）
- **设计目标**：3 秒内让用户理解客服能做什么、入口在哪里

### 1.2 信息架构

按附图参考的"中部内容 + 底部快捷词"模式，结合马卡龙风格，分三区：

```
┌────────────────────────────────────────┐
│  机器人头像 + 欢迎语                    │  ← 个性化欢迎
│  "Hi，我是智能客服小蜜，请问我能帮您"  │
├────────────────────────────────────────┤
│  ★ 热门功能卡片（3-4 张）              │  ← 功能介绍
│  [知识库] [工具调用] [人工转接] [多模态]│
├────────────────────────────────────────┤
│  📌 常见问题快捷入口（Top 5-8 条）     │  ← 常见问题
│  > 怎么开通小蜜？                      │
│  > 怎么接入自定义工具？                │
│  > 数据如何备份？                      │
├────────────────────────────────────────┤
│  💡 使用提示（可关闭、记住选择）        │  ← 使用指南
│  "Shift+Enter 换行 · 拖拽图片上传..."  │
└────────────────────────────────────────┘
```

### 1.3 前端设计

- **新增组件**：[ChatbotOnboarding.tsx](file:///d:/code/otherProjects/17_xianyu/frontend/src/pages/Chatbot/components/ChatbotOnboarding.tsx)
  - props: `onQuestionClick(q: string)` 点击常见问题直接发送
  - props: `onDismiss()` 用户关闭引导
- **数据来源**：
  - 欢迎语：从 `chatbot_dynamic_config.welcome_message` 读取（后端新增字段，见 1.4）
  - 热门功能卡片：硬编码 4 张（知识库 / 工具调用 / 人工转接 / 多模态），点击跳转
  - 常见问题：调用 `chatbotApi.listFAQ()` 取前 5-8 条
  - 使用提示：硬编码 3 条小贴士
- **个性化欢迎语策略**：
  - 首次（无历史会话）："Hi，我是智能客服小蜜..."
  - 非首次（历史会话 ≥1 条）："欢迎回来！上次我们聊到「{最近会话标题}」，可以继续哦"
  - 夜间（22:00-7:00）："夜深了，有什么需要帮忙的吗？"
- **触发逻辑**（index.tsx）：
  ```ts
  const showOnboarding =
    !loadingMessages && messages.length === 0 && !currentSession?.is_archived
  ```
- **记住关闭**：localStorage `chatbot_onboarding_dismissed` 标志位；下次创建新会话时重置

### 1.4 后端设计

- **新增字段**：`chatbot_dynamic_config` 表新增 `welcome_message TEXT`（可空）
- **新增 API**：`GET /api/chatbot/welcome` 返回 `{ message, persona, updated_at }`
  - persona 字段预留，默认 `xiaomi`（小蜜），不引入多 persona 系统
- **更新现有 API**：`PUT /api/chatbot/config` 接收 `welcome_message` 字段

### 1.5 验收标准

- [ ] 无会话时显示引导卡，含欢迎语 + 4 个功能卡 + Top 5 FAQ + 提示
- [ ] 点击 FAQ 立即发送
- [ ] 关闭后 localStorage 记住，创建新会话时重置显示
- [ ] 欢迎语可由管理员在 Config 页面修改

---

## 2. 历史对话记录功能增强

### 2.1 目标与场景

- **现状**：左侧 SessionList 已显示会话标题列表（按更新时间倒序）
- **缺失**：
  - 跨会话消息内容搜索
  - 收藏 / 置顶会话
  - 按时间区间过滤
  - 消息预览（最近一条内容）

### 2.2 功能子集（取舍）

| 需求 | 是否实现 | 理由 |
|---|---|---|
| 按时间倒序 | 已有 | SessionList 默认行为 |
| 关键词搜索会话 | 实现 | 后端 LIKE，标题 + 最近一条内容匹配 |
| 关键词搜索消息 | 不实现 | SQLite 无 FTS5 索引，全表扫描风险大；先用会话级搜索兜底 |
| 无限滚动 | 已有 | SessionList 用 antd List `loadMore` |
| 收藏 / 置顶 | 实现 | 加 `is_favorite` 字段 + 排序优先级 |
| 本地存储 / 云端同步 | 不实现 | 当前单实例单用户，DB 即云端；多设备为"后续扩展" |

### 2.3 前端设计

- **改造 SessionList**（如不存在则新建，现状估计在 index.tsx Sider 内）：
  - 顶部加 `Input.Search`（占位"搜索会话标题或内容"）
  - 列表项渲染：⭐ 收藏标 + 标题 + 时间 + 最近一条消息预览（截断 30 字）
  - 长按/右键菜单：收藏 / 取消收藏 / 重命名 / 删除
- **排序**：
  - 收藏置顶（`is_favorite DESC, updated_at DESC`）
  - 后端接受 `?favorite_only=true` 参数
- **无限滚动**：保持现有 `loadMore`，每次取 20 条

### 2.4 后端设计

- **数据库迁移**：新增 `chatbot_sessions.is_favorite BOOLEAN DEFAULT 0`
  - 迁移脚本：项目用 SQLAlchemy 但未见 alembic，需核查 `db_models.py` 是否有内建迁移机制
- **新增路由参数**：
  - `GET /api/chatbot/sessions?keyword=xxx&favorite_only=true&limit=20&before_id=...`
  - keyword 模糊匹配：`title LIKE '%xxx%' OR id IN (SELECT session_id FROM chatbot_messages WHERE content LIKE '%xxx%' AND role='user' GROUP BY session_id ORDER BY created_at DESC LIMIT 50)`
  - 注意：消息搜索要 LIMIT 限制防全表扫
- **性能边界**：
  - 关键词搜索结果上限 50 条会话
  - 不在 `chatbot_messages` 加 FTS 索引（YAGNI）
- **更新 `is_favorite`**：`PATCH /api/chatbot/sessions/{id}` body `{is_favorite: true}`

### 2.5 验收标准

- [ ] 会话列表顶部有搜索框，模糊匹配标题 + 内容
- [ ] 收藏的会话置顶
- [ ] 右键菜单可收藏 / 取消
- [ ] 关键词搜索结果不超过 50 条并按 updated_at 排序
- [ ] 无限滚动加载无重复

---

## 3. 交互体验优化

### 3.1 输入框自动聚焦

- **方案**：`index.tsx` 的 `currentSession` 变更时 `inputRef.current?.focus()`
- **实现**：`useEffect(() => inputRef.current?.focus(), [currentSession?.id])`
- **不冲突**：流式响应中（`isStreaming`）`disabled` 会禁止聚焦

### 3.2 消息状态提示

| 状态 | 实现 |
|---|---|
| 发送中 | 用户消息气泡右下角 `<Spin size="small" />` + "发送中..." |
| 已送达 | 后端 save_message 后，前端收到 SSE 首个 TOKEN 事件后切换 ✓ |
| 已读 | 不实现 | 理由：单用户，无"他人已读"语义 |

**实现**：
- Message 类型加 `status: 'sending' | 'sent' | 'failed'`（已读省略）
- 临时消息 id 用 `temp-` 前缀，server-confirmed 后替换
- 失败：捕获 sendMessage 错误，气泡显示红色 + 重试按钮

### 3.3 图文混排消息展示

- **当前**：用户消息 content 是纯文本（刚加 `[图片×N]` 文本标记）
- **目标**：用户消息气泡内同时显示图片缩略图 + 文字
- **方案**：
  - 后端：保存消息时把 images 关联到 message_id，新增 `chatbot_message_images` 表（image_url, message_id, order）
  - 前端：用户消息气泡组件 `UserMessage.tsx` 渲染图片（点击放大）+ 文字
  - 助手消息不需要：LLM 生成的是文本，没有"图片"
- **不引入 markdown 渲染**（YAGNI）：现有纯文本 + 引用编号已够用

### 3.4 消息撤回

- **时间窗**：2 分钟（业内常见）
- **后端实现**：
  - 软删除：加 `is_recalled BOOLEAN DEFAULT 0` 字段（不真删，保审计）
  - `POST /api/chatbot/messages/{id}/recall` 校验：仅 user 角色、自己的消息、2 分钟内
  - 撤回后 SSE 推 `message_update` 事件，其他端实时更新
- **前端**：
  - 用户消息气泡上 hover 显示"撤回"按钮（2 分钟内可见）
  - 撤回后气泡替换为"消息已撤回"灰色占位
- **LLM 上下文**：撤回后该消息仍保留在 messages 表中，但前端不渲染；LLM 历史中标记为 `[已撤回]`，避免影响后续对话

### 3.5 快捷回复

- **数据源**：复用 `chatbotApi.listFAQ()`，但用 `is_quick_reply=true` 过滤（FAQ 表加字段）
- **UI 位置**：输入区上方，横向滚动 `Tag` 列表（点击填充到输入框）
- **不发送**：仅填充到输入框，用户可编辑后再发（避免误解"快捷发送=自动问答"）

### 3.6 验收标准

- [ ] 切换会话后输入框自动聚焦
- [ ] 用户消息显示"发送中 → 已送达"状态
- [ ] 用户消息气泡显示已上传图片
- [ ] 2 分钟内用户消息可撤回
- [ ] 输入区上方显示快捷回复 Tag，点击填充输入框

---

## 4. 功能入口优化

### 4.1 现状入口盘点

| 入口 | 位置 | 状态 |
|---|---|---|
| 智能客服 | 主菜单 → 智能客服 | 存在 |
| 会话列表 | 顶部 Sider | 存在 |
| 新建会话 | Sider 顶部 + 按钮 | 存在 |
| 转人工 | 助手消息 hover 菜单 | 存在（隐藏） |
| 帮助中心 | 无 | 需新增 |
| 收藏会话 | 无入口 | 走右键菜单 |
| 历史消息搜索 | 无 | 走会话搜索 |
| 知识库管理 | 主菜单 → 客服配置 → 知识库管理 | 存在 |

### 4.2 信息架构（建议）

在 Sider 顶部新建会话按钮下方，添加固定操作区：

```
┌──────────────────────────┐
│ [+ 新建会话]              │
├──────────────────────────┤
│  ⭐ 收藏的会话（2）        │  ← 折叠面板
│  ❓ 帮助中心               │  ← 弹窗
│  🧑‍💼 立即转人工            │  ← 一键转人工
├──────────────────────────┤
│ 最近会话                  │
│ - 会话1                   │
│ - 会话2                   │
└──────────────────────────┘
```

### 4.3 详细设计

- **收藏的会话**：折叠面板，仅在有收藏时展开，点击跳转
- **帮助中心**：
  - 当前未实现独立帮助页，先做"弹窗式"
  - 弹窗内容：使用指南、常见问题、快捷键说明、版本信息
  - 复用 ChatbotOnboarding 的"使用提示"内容，扩展为完整文档
- **立即转人工**：
  - 走现有 escalation 流程（POST /api/chatbot/escalation/trigger）
  - 前端加确认弹窗："将转接至人工客服，是否继续？"
  - 理由：避免误触

### 4.4 验收标准

- [ ] Sider 顶部有"帮助中心"入口（弹窗）
- [ ] Sider 顶部有"立即转人工"入口（确认后触发）
- [ ] 收藏会话有独立折叠区
- [ ] 帮助中心弹窗内容完整（指南+FAQ+快捷键+版本）

---

## 5. 用户反馈机制

### 5.1 现状

- 助手消息下有 Like/Dislike 按钮，点击 Dislike 弹窗输入文字反馈
- 已调用 `POST /api/chatbot/messages/{id}/feedback`

### 5.2 缺失

- 缺 1-5 星评分（当前只有"赞/踩"二态）
- 缺"反馈后修改回复"功能（业内常见，AI 误答时用户可纠正）

### 5.3 设计

| 需求 | 实现 | 优先级 |
|---|---|---|
| 1-5 星评分 | AssistantMessage 改用 antd Rate 组件（1-5 星）；后端 feedback 表加 `rating: int` 字段 | 中 |
| 文字反馈 | 已有，保持 | - |
| 反馈分类（答非所问/答错/其他） | Modal 内加 Select 分类，分类存入 `feedback_category` 字段 | 低 |
| 反馈后修改回复 | 不实现。理由：会让 LLM 上下文紊乱，且需后端支持 edit_message，复杂度高 | - |

### 5.4 数据库迁移

- `chatbot_message_feedback` 表加字段：
  - `rating TINYINT`（1-5）
  - `category VARCHAR(32)`（irrelevant/inaccurate/other）
  - 原 `rating` 字段为正/负的语义保留为 `sentiment: VARCHAR(8)`（positive/negative）

### 5.5 前端

```tsx
<Rate defaultValue={5} onChange={setRating} />
<Select placeholder="问题类型" options={[
  { value: 'irrelevant', label: '答非所问' },
  { value: 'inaccurate', label: '信息有误' },
  { value: 'other', label: '其他' },
]} />
```

### 5.6 验收标准

- [ ] 助手消息可打 1-5 星
- [ ] 反馈 Modal 可选问题分类
- [ ] 后端存储 rating + category + comment + sentiment

---

## 6. 实施批次（按价值/依赖关系）

### 6.1 批次划分

| 批次 | 内容 | 文件数 | 风险 | 价值 |
|---|---|---|---|---|
| **M1 - 引导卡** | 第 1 大类全部 | 前端 1 新 + 2 改 | 低 | 高（首屏体验） |
| **M2 - 历史增强** | 第 2 大类搜索 + 收藏 | 前端 1 改 + 后端 1 路由 + 1 迁移 | 中 | 中 |
| **M3 - 交互优化** | 自动聚焦 + 状态 + 快捷回复 | 前端 2 改 | 低 | 中 |
| **M4 - 撤回 + 图文** | 撤回 + 用户消息图混排 | 前端 1 改 + 后端 1 路由 + 1 迁移 | 中 | 中 |
| **M5 - 功能入口** | 帮助中心 + 立即转人工 | 前端 1 改 | 低 | 中 |
| **M6 - 反馈增强** | 1-5 星 + 分类 | 前端 1 改 + 后端 1 迁移 | 低 | 低 |

### 6.2 推荐优先做

按"价值/风险"比，**M1 + M3** 优先：
- M1（引导卡）：纯前端，无后端依赖，3 秒理解产品
- M3（交互优化）：自动聚焦 + 发送状态 = 体感提升最大

**M2** 涉及数据库迁移，建议在数据稳定期再做。

**M4**（撤回 + 图文）复杂度高，建议放最后并单独评审。

### 6.3 不做的（YAGNI 清单）

- ❌ 消息级别 FTS5 搜索
- ❌ 多设备云端同步（auth 重构）
- ❌ 反馈后修改回复
- ❌ markdown 渲染
- ❌ "已读" 状态（单用户无意义）
- ❌ 多 persona 切换
- ❌ 实时消息推送（SSE 已满足，撤回推送是 M4 子任务）

---

## 7. 验收总览

按"是否落地"分两阶段：

### 7.1 M1 阶段验收（建议本迭代实现）

- [ ] 首屏展示引导卡，含欢迎语 + 4 功能卡 + Top 5 FAQ + 提示
- [ ] FAQ 点击直接发送
- [ ] 关闭引导后 localStorage 记忆
- [ ] 切换会话自动聚焦输入框
- [ ] 用户消息显示"发送中 → 已送达"状态
- [ ] 输入区上方快捷回复 Tag，点击填充

### 7.2 完整阶段验收（按 M1-M6 全实现）

- [ ] 上述 M1 + 上述 7.1 全部
- [ ] 会话搜索 + 收藏
- [ ] 2 分钟内消息可撤回
- [ ] 用户消息图文混排
- [ ] 帮助中心 + 一键转人工
- [ ] 1-5 星评分 + 反馈分类

---

## 8. 与现有系统集成点

### 8.1 后端需改文件

| 文件 | 改动 |
|---|---|
| `api_chatbot.py` | 新增 welcome 路由、PATCH session、recall 路由 |
| `repo_chatbot.py` | 加 `update_session_favorite`、`search_sessions_by_keyword` |
| `db_models.py` | 加 `is_favorite`、`is_recalled`、`welcome_message`、`feedback.rating/category/sentiment` |
| `chatbot_dynamic_config` 表 | 加 `welcome_message` 字段 |
| `chatbot_message_images` 新表 | 存消息图片关联 |

### 8.2 前端需改文件

| 文件 | 改动 |
|---|---|
| `pages/Chatbot/index.tsx` | 加引导卡渲染、自动聚焦、消息状态 |
| `pages/Chatbot/components/ChatbotOnboarding.tsx` | **新建**，引导卡组件 |
| `pages/Chatbot/components/UserMessage.tsx` | **新建**，用户消息气泡（图混排） |
| `pages/Chatbot/components/AssistantMessage.tsx` | 改 Rate + 反馈分类 |
| `pages/Chatbot/SessionList.tsx` | 改搜索 + 收藏 |
| `pages/Chatbot/hooks/useSSEChat.ts` | 改消息状态（sending/sent/failed） |
| `pages/Chatbot/api.ts` | 加 `searchSessions`、`updateSessionFavorite`、`recallMessage` |
| `pages/Chatbot/types.ts` | 加 `is_favorite`、`is_recalled`、`status` |
| `pages/Chatbot/chatbot.css` | 新增 5 个样式类（onboarding/quick-reply/favorite 等） |

### 8.3 不改的文件

- `orchestrator.py` / `rag_engine.py` / `agent.py`（核心 LLM 流程不动）
- `kb_manager.py`（知识库管理独立）
- `feedback.py`（重构而非新增）

---

## 9. 测试策略

- **单元测试**：FAQ 匹配、is_favorite 切换、recall 校验
- **集成测试**：SSE 撤回推送、搜索结果 LIMIT
- **E2E（Playwright）**：
  - M1：首屏引导卡渲染 + FAQ 点击
  - M3：自动聚焦 + 状态切换
  - M2：搜索 + 收藏置顶

---

## 10. 风险与回滚

| 风险 | 缓解 |
|---|---|
| 数据库迁移失败 | 加 `IF NOT EXISTS` 校验，迁移脚本可重入 |
| 引导卡过度展示 | localStorage 关闭 + session 切换重置 |
| 撤回推送导致状态错乱 | SSE 事件 + 客户端幂等（基于 message_id 替换） |
| 搜索慢 | LIMIT 50 + LIKE 索引（后续可加 FTS5） |

---

> **下一步**：本文档为规划阶段产物。实现前请确认：
> 1. 批次划分是否合理？
> 2. YAGNI 清单是否有需追加的？
> 3. M1 阶段（引导卡 + 交互优化）是否作为下一个迭代目标？
