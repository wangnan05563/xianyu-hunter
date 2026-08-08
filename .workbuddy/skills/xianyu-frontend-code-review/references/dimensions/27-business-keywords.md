# 27. 业务关键字常量集中管理与字段名大小写敏感 🆕v4.31

基于 2026-07-05 解决的 3 类前端反模式复盘（业务文案硬编码 / 事件类型前缀过滤 / 字段名大小写不一致），系统化梳理前端在业务关键字与字段契约层面的同步原则。本维度强调"前端业务关键字常量必须从后端配置拉取 + 事件类型过滤必须 === 精确匹配 + 前后端字段名大小写敏感对齐"，确保前后端业务规则一致性。3 项检查点对应 `xianyu-hunter-dev` 编码规范 step 129/130/131。

- 🆕v4.31【强制】**F-REVIEW-BUSINESS-KEYWORD-CENTRALIZATION：业务关键字常量集中管理**
  - 维度归属：27 业务关键字常量集中管理与字段名大小写敏感
  - 严重等级：error
  - **检查点**：前端使用业务关键字文案（如"卖掉了"/"已售"/"已下架"等业务状态判定文本）时，是否从后端配置端点（如 `/api/config/text_features`）拉取而非前端硬编码
  - **判定标准**：**禁止**前端在 `utils/`、`pages/`、`components/` 中硬编码业务关键字中文字面量（如 `const SOLD_KEYWORDS = ['卖掉了', '已售']`、`if (text.includes('卖掉了'))`）。必须改为从后端配置端点拉取关键字列表，前端通过共享 helper 函数（如 `isItemSoldByText(text)`）调用后端配置
  - **检查范围**：所有前端业务关键字文本判断（商品售出状态、订单状态、用户角色判定等业务规则文本）
  - **核心机制**（审查时必须理解）：
    - 后端 v4.31.0 起业务关键字常量集中在 `collector_utils.py` 的 `SOLD_TEXT_KEYWORDS` + `check_text_sold()` 函数，配置节点为 `config.yaml#external_platform.text_features`
    - 前端硬编码业务关键字会与后端规则不一致（如后端新增"已售出"文案但前端未同步，导致前端展示状态错误）
    - 业务关键字是"业务规则的可配置化入口"，前端不能假设关键字是固定不变的
    - 前端职责是"调用后端配置 + 通过 helper 函数判断"，不是"实现业务规则"
  - **判断信号**（grep 检测）：
    - `grep -nE "const\s+\w*_KEYWORDS?\s*=\s*\[" frontend/src/**/*.{ts,tsx}` 命中 → 检查是否硬编码业务关键字常量
    - `grep -nE "\.includes\(['\"](卖掉了|已售|已下架|已完成)" frontend/src/**/*.{ts,tsx}` 命中 → 违规（硬编码业务关键字判断）
    - `grep -nE "/api/config/text_features" frontend/src/api/**/*.ts` 未命中 → 检查是否有调用后端配置端点
    - 用户反馈"前端判断状态与后端不一致" → 必查前端是否硬编码业务关键字
  - **修复模式**：
    ```typescript
    // ✅ 正确：从后端配置拉取业务关键字
    import { configApi } from '@/api/config'

    let soldKeywords: string[] = ['卖掉了']  // 兜底默认值
    async function loadTextFeatures() {
      const features = await configApi.getTextFeatures()
      soldKeywords = features.sold_keywords ?? soldKeywords
    }

    export function isItemSoldByText(text: string): boolean {
      return soldKeywords.some(kw => text.includes(kw))
    }

    // 禁止：前端硬编码业务关键字（与后端规则可能不一致）
    ```
  - **配置参数**：`business_keyword_centralization` 节点（在 `config.yaml` 管理，不硬编码）：
    - `enabled`（默认 `true`，开关本检查）
    - `config_endpoint_pattern`（默认 `"/api/config/text_features"`，后端业务关键字配置端点 URL）
    - `forbidden_hardcoded_patterns`（默认 `["const \\w*_KEYWORDS?\\s*=\\s*\\[", "\\.includes\\(['\"][^'\"]*(卖掉了|已售|已下架)"]`，禁止前端硬编码业务关键字的代码模式）
    - `required_helper_pattern`（默认 `"is\\w+ByText"`，业务关键字判断必须使用的共享 helper 函数命名模式）
    - `backend_keyword_source`（默认 `"xianyu-backend-code-review.business_keyword_centralization.SOLD_TEXT_KEYWORDS"`，后端业务关键字常量来源，确保前后端契约对齐）
  - **适用场景**：前端业务状态判定（商品售出/订单状态/用户角色）、业务关键字文案判断、需要与后端规则保持一致的业务规则文本
  - **不适用场景**：纯前端 UI 文案（如"保存成功"/"加载中"，不涉及业务规则）；前端组件内部状态文本（如 tab 标签）；固定的 UI 提示文案（不依赖后端规则）
  - **历史教训**：闲鱼"卖掉了"文案判定，后端 `collector_utils.py` 新增"已售出"文案后前端 `utils/soldDetector.ts` 中硬编码的 `['卖掉了', '已售']` 未同步，导致前端展示商品状态错误（显示"在售"实际已售）。修复方式：前端改为从 `/api/config/text_features` 拉取 sold_keywords 列表，与后端 `SOLD_TEXT_KEYWORDS` 一一对应
  - **对应后端原则**：后端业务关键字常量必须集中在 `collector_utils.py` + `check_text_sold()` 统一入口 + 配置节点 `config.yaml#external_platform.text_features`，详见 `xianyu-hunter-dev` step 129

- 🆕v4.31【强制】**F-REVIEW-EVENT-TYPE-EXACT-MATCH：事件类型过滤精确匹配**
  - 维度归属：27 业务关键字常量集中管理与字段名大小写敏感
  - 严重等级：error
  - **检查点**：前端按事件类型（event_type）过滤时是否使用 `===` 精确匹配，禁止使用 `startsWith()` / `indexOf()` 前缀匹配
  - **判定标准**：**禁止** `if (event.type.startsWith('eval.'))` / `if (event.type.indexOf('task.') === 0)` 等前缀匹配模式（除非该前缀是明确的分组分类场景）。必须改为显式枚举 `if (event.type === 'eval.started' || event.type === 'eval.passed')`，或使用 `Set` 集合判断 `if (EVENT_TYPES_TO_HANDLE.has(event.type))`
  - **检查范围**：所有前端事件类型过滤逻辑（SSE 事件、WebSocket 事件、自定义事件分发、批量事件处理）
  - **核心机制**（审查时必须理解）：
    - 后端 v4.31.0 起事件类型过滤必须 == 精确匹配（step 130），前端 SSE 事件处理同样需要遵守
    - 前缀匹配会误包含子类型事件（如 `startsWith('eval.')` 会误包含 `eval.passed`/`eval.failed`/`eval.error`），导致前端逻辑分支错误
    - 事件类型是"枚举值"而非"前缀分类"，前端必须按枚举值精确匹配
    - 通知事件（如 `notification.created`）与业务事件（如 `task.created`）必须分离处理，禁止用前缀 `startsWith('task.')` 同时匹配业务事件和通知事件
  - **判断信号**（grep 检测）：
    - `grep -nE "\.startsWith\(['\"]\w+\." frontend/src/**/*.{ts,tsx}` 命中 → 检查是否在事件类型前缀匹配
    - `grep -nE "\.indexOf\(['\"]\w+\.\w" frontend/src/**/*.{ts,tsx}` 命中 → 检查是否在事件类型前缀匹配
    - `grep -nE "switch\s*\(\s*\w+\.(type|eventType)" frontend/src/**/*.{ts,tsx}` 未命中 → 检查是否有按事件类型 switch 的实现
    - 用户反馈"前端 SSE 处理了不该处理的事件" → 必查前端是否用前缀匹配事件类型
  - **修复模式**：
    ```typescript
    // ✅ 正确：精确匹配 + 显式枚举
    const EVENT_TYPES_TO_HANDLE = new Set([
      'eval.started',
      'eval.passed',
      'eval.failed',
    ])

    if (EVENT_TYPES_TO_HANDLE.has(event.type)) {
      handleEvent(event)
    }

    // ✅ 正确：switch case 精确匹配
    switch (event.type) {
      case 'eval.started':
        handleEvalStarted(event)
        break
      case 'eval.passed':
        handleEvalPassed(event)
        break
      // ...
    }

    // 禁止：前缀匹配（误包含子类型）
    ```
  - **配置参数**：`event_type_exact_match` 节点（在 `config.yaml` 管理，不硬编码）：
    - `enabled`（默认 `true`，开关本检查）
    - `forbidden_prefix_patterns`（默认 `["startsWith\\(['\"]\\w+\\.", "indexOf\\(['\"]\\w+\\.\\w"]`，禁止用于事件类型过滤的前缀匹配模式）
    - `required_match_pattern`（默认 `["===", "Set\\.has\\(", "switch.*case"]`，必须使用的精确匹配模式）
    - `notification_event_separation_required`（默认 `true`，是否强制通知事件与业务事件分离处理）
    - `allowed_prefix_grouping_scenarios`（默认 `["statistics_aggregation", "log_filtering"]`，允许前缀匹配的统计/日志场景）
  - **适用场景**：前端 SSE 事件处理、WebSocket 消息处理、自定义事件分发、批量事件处理
  - **不适用场景**：纯统计场景（如"统计 eval.* 类型事件总数"，允许前缀匹配）；日志过滤场景（如"过滤 task.* 类型事件"，允许前缀匹配）；路由前缀匹配（如 `/tasks/*` 路由，是路径前缀而非事件类型）
  - **历史教训**：评估明细页前端用 `event.type.startsWith('eval.')` 过滤 SSE 事件，导致 `eval.passed`/`eval.failed`/`eval.error` 等子类型事件全部进入同一处理分支，前端展示 227+ 条空记录（实际只有 `eval.started` 应该进入此分支）。修复方式：前端改为 `Set<string>` 精确匹配 `eval.started`，与后端事件类型枚举一一对应
  - **对应后端原则**：后端事件类型过滤必须 == 精确匹配 + 通知事件与业务事件分离 + 前缀分组仅限统计场景，详见 `xianyu-hunter-dev` step 130

- 🆕v4.31【强制】**F-REVIEW-FIELD-NAME-CASE-SENSITIVE：前后端字段名大小写敏感检查**
  - 维度归属：27 业务关键字常量集中管理与字段名大小写敏感
  - 严重等级：error
  - **检查点**：前端访问后端 API 响应字段时，字段名大小写是否与后端 Pydantic 模型完全一致
  - **判定标准**：**禁止**前端用 `data.totalForType` 访问后端 `total_for_type` 字段（驼峰/下划线混淆）、用 `repo._Session` 访问后端 `_session` 字段（私有属性大小写不一致）。必须严格对齐后端 Pydantic 模型字段名大小写，前端 `api/types.ts` 中声明的字段名必须与后端模型字段名一一对应；禁止用 `as any` 绕过类型检查
  - **检查范围**：所有前端访问后端 API 响应字段的代码路径（API 响应消费、组件 props 取值、Zustand store 字段读写、测试 mock 数据字段名）
  - **核心机制**（审查时必须理解）：
    - 后端 v4.31.0 起前后端字段名大小写敏感检查规范化（step 131），前端同样需要遵守
    - 后端 Pydantic 模型字段名是契约（如 `total_for_type` snake_case），前端 `api/types.ts` 必须严格对齐
    - 后端私有属性（如 `_session`）大小写敏感，前端通过类型断言访问时必须完全一致
    - 前端用 `as any` 绕过类型检查会掩盖字段名大小写不一致的 bug，必须改为精确类型 + grep 双向匹配验证
  - **判断信号**（grep 检测）：
    - `grep -nE "as\s+any\b" frontend/src/**/*.{ts,tsx}` 命中 → 检查是否用 `as any` 绕过字段名检查
    - `grep -nE "\.\w*[A-Z]\w*\b" frontend/src/api/**/*.ts` 命中 → 检查前端 API 类型定义中是否有驼峰字段名（后端应为 snake_case）
    - 后端字段重命名后 `git diff frontend/src/api/types.ts` 无变更 → 前端类型未同步
    - 用户反馈"前端字段显示 undefined / 0 / 空" → 必查前端字段名大小写是否与后端一致
  - **修复模式**：
    ```typescript
    // ✅ 正确：前端类型与后端 Pydantic 模型一一对应（snake_case）
    interface EvalDetailResponse {
      total: number
      total_for_type: number  // 与后端 Pydantic 模型一致
      items: EvalItem[]
    }

    const data = await api.getEvalDetail()
    console.log(data.total_for_type)  // ✅ 字段名一致
    // 禁止：字段名大小写不一致（前端误用驼峰 totalForType，与后端 total_for_type 不一致；as any 绕过类型检查导致 undefined）
    ```
  - **配置参数**：`field_name_case_sensitive` 节点（在 `config.yaml` 管理，不硬编码）：
    - `enabled`（默认 `true`，开关本检查）
    - `backend_field_naming_style`（默认 `"snake_case"`，后端字段命名风格）
    - `forbidden_frontend_naming_styles`（默认 `["camelCase", "PascalCase"]`，禁止前端字段命名风格（除非是前端独立字段））
    - `require_type_sync`（默认 `true`，后端字段变更时前端 types.ts 必须同步）
    - `forbidden_bypass_patterns`（默认 `["as\\s+any\\b", "as\\s+unknown\\s+as"]`，禁止用类型断言绕过字段名检查的模式）
    - `detection_signals`（默认 `["\\.\\w*[A-Z]\\w*\\b", "as\\s+any\\b"]`，触发检查的代码模式）
    - `backend_model_source`（默认 `"xianyu-backend-code-review.field_name_contract.models"`，后端 Pydantic 模型字段名来源，确保前后端契约对齐）
  - **适用场景**：前端访问后端 API 响应字段、前端 API 类型定义、前端 Zustand store 字段读写、前端测试 mock 数据字段
  - **不适用场景**：前端独立字段（如组件内部 state，不涉及后端契约）；前端 UI 文案常量（不涉及字段名）；前端路由参数（前端独立命名）
  - **历史教训**：评估明细页前端展示"0 条"，根因是前端用 `data.totalForType` 访问后端 `total_for_type` 字段（驼峰 vs snake_case 不一致），导致 `data.totalForType` 始终为 `undefined`，前端 `undefined || 0` 显示为 0。同时后端 `ChatbotRepository` 类用 `this._Session` 访问定义为 `this._session` 私有属性（大小写不一致），导致 `AttributeError: 'ChatbotRepository' object has no attribute '_Session'`。修复方式：前端类型定义严格对齐后端 snake_case，私有属性大小写完全一致
  - **对应后端原则**：后端私有属性大小写一致 + API 字段名前后端契约对齐 + grep 双向匹配验证，详见 `xianyu-hunter-dev` step 131
