# 25. 端到端失败原因链前端侧同步原则 🆕v4.27

基于"Failed to collect item detail: page unavailable or login expired"根因复盘（代码被回退 + 服务未重启双重原因导致修复未生效），系统化梳理前端在端到端失败原因链中的同步原则。本维度不直接处理后端失败原因传递/数据完整性预检/合并写入等后端逻辑，但前端作为错误展示方与 API 调用方，必须遵循以下 3 项同步原则，确保前后端错误处理契约一致。

- 🆕v4.27【强制】**F-REVIEW-ERROR-CODE-BRANCH：错误展示按 error_code 字段分支**
  - 维度归属：25 端到端失败原因链前端侧同步原则
  - 严重等级：error
  - **检查点**：前端 catch 块中处理后端错误响应时，是否按 `error_code` 字段分支决策（重试/降级/提示用户操作）而非按文案子串判断
  - **判定标准**：**禁止** `if (msg.includes('expired'))` / `if (detail.indexOf('unavailable') !== -1)` / `if (err.message === '页面不可用')` 等子串匹配模式。必须改为 `switch (err.error_code) { case 'token_invalid': ...; case 'page_unavailable': ...; case 'rate_limited': ... }`，分支逻辑与后端 `failure_reason_propagation.reason_enum` 一一对应（命名风格以后端为准，统一 lower_snake_case）
  - **检查范围**：所有消费后端错误响应的前端 catch 块（API 调用、SSE 错误事件、批量操作错误处理）
  - **核心机制**（审查时必须理解）：
    - 后端 v4.27.0 起 `HTTPException` 的 detail 改为结构化 `{'error_code': 'XXX', 'message': '...'}`，禁止用字符串子串做日志降级 marker（后端 B-REVIEW-FAILURE-REASON-PROPAGATION）
    - 前端若按文案子串判断，后端调整文案后前端逻辑会失效（如后端把"login expired"改为"会话已过期"，前端的 `includes('expired')` 不再命中）
    - error_code 是稳定的契约接口，文案是可变的人类可读描述，前端必须依赖前者而非后者
    - 与 F-REVIEW-ERROR-CODE-CONSUMPTION（维度 20）配合：F-REVIEW-ERROR-CODE-CONSUMPTION 关注"是否决策重试/降级"，F-REVIEW-ERROR-CODE-BRANCH 关注"如何识别错误类型（按 error_code 而非文案子串）"
  - **判断信号**（grep 检测）：
    - `grep -nE "if\s*\(\s*\w+\.(message|detail|msg)\.includes\(" frontend/src/**/*.tsx` 命中 → 检查是否在判断后端错误类型
    - `grep -nE "\.(indexOf|search|match)\(['\"](expired|unavailable|rate limited|page unavailable|login expired)" frontend/src/**/*.tsx` 命中 → 违规（按文案子串判断错误类型）
    - `grep -nE "switch\s*\(\s*\w+\.error_code\s*\)" frontend/src/**/*.tsx` 未命中 → 检查是否有按 error_code 分支的实现
    - 用户反馈"后端改了错误文案后前端行为异常" → 必查前端是否按文案子串判断错误类型
  - **修复模式**：
    ```typescript
    // ✅ 正确：按 error_code 字段分支
    import type { ApiErrorResponse } from '@/api/types'

    try {
      await collectionApi.collectItem(itemId)
    } catch (e) {
      const err = e.response?.data as ApiErrorResponse
      switch (err?.error_code) {
        case 'token_invalid':
          message.warning('令牌已失效，请重新获取')
          break
        case 'page_unavailable':
          message.error('页面不可用，可能需要重新登录')
          break
        case 'rate_limited':
          message.warning('操作过于频繁，请稍后重试')
          break
        default:
          message.error(extractApiError(e), 5)
      }
    }

    // 禁止：按文案子串判断（后端改文案后失效）
    ```
  - **配置参数**：`failure_reason_chain_frontend` 节点（在 `config.yaml` 管理，不硬编码）：
    - `enabled`（默认 `true`，开关本检查）
    - `required_error_code_field`（默认 `"error_code"`，后端错误响应中必须包含的错误码字段名）
    - `forbidden_substring_markers`（默认 `["expired", "unavailable", "rate limited", "page unavailable", "login expired"]`，禁止用于判断错误类型的文案子串列表）
    - `required_branch_pattern`（默认 `"switch.*error_code"`，必须使用的分支模式正则）
    - `backend_reason_enum_source`（默认 `"xianyu-backend-code-review.failure_reason_propagation.reason_enum"`，后端 reason 枚举来源，确保前后端契约对齐）
    - `detection_signals`（默认 `[".includes('expired'", ".indexOf('unavailable'", ".match(/rate limited/i)"]`，触发检查的代码模式）
  - **适用场景**：所有消费后端错误响应的前端 catch 块（API 调用/SSE 错误事件/批量操作错误处理）；后端已实现结构化 error_code 字段的接口；需要按错误类型做不同 UI 反馈的场景（重试/降级/引导用户操作）
  - **不适用场景**：纯前端错误（表单校验错误、本地计算错误、本地 storage 读写错误）；后端未实现 error_code 字段的旧接口（应推动后端补齐）；网络层错误（如 axios 超时无 response.body，应用 F-REVIEW-ERROR-CONTRACT-TIMEOUT 的 `isAxiosTimeout()` 识别）
  - **历史教训**：闲鱼详情采集接口返回 `{"detail": "Failed to collect item detail: page unavailable or login expired"}`，前端按 `detail.includes('expired')` 判断为"登录过期"引导用户重新登录，但实际根因可能是页面不可用（非登录问题）。后端将 detail 改为结构化 `{"error_code": "page_unavailable", "message": "..."}` 后，前端子串判断失效。修复方式：前端改为按 `error_code` 分支，与后端 reason_enum 一一对应
  - **对应后端原则**：后端必须返回结构化错误响应含 `error_code` 字段，禁止用字符串子串做日志降级 marker，详见 `xianyu-backend-code-review` v4.27.0 的 `B-REVIEW-FAILURE-REASON-PROPAGATION` / `B-REVIEW-ERROR-MESSAGE-CONSTANT`

- 🆕v4.27【强制】**F-REVIEW-PRECHECK-API-DELEGATION：数据完整性预检委托后端**
  - 维度归属：25 端到端失败原因链前端侧同步原则
  - 严重等级：warning
  - **检查点**：前端调用后端 API 前若需预检数据完整性（如 cookie 数量是否足够、关键字段是否非空），是否调用后端预检端点而非前端自行判断
  - **判定标准**：**禁止**前端自行实现数据完整性预检逻辑（如 `if (cookies.length < 10)` / `if (!cookie.token)` / `if (!item.title || !item.price)`）。必须调用后端预检端点（如 `/api/cookies/precheck` / `/api/items/<id>/precheck`）获取预检结果，前端仅根据预检结果的 `passed` 字段决定是否继续调用主接口
  - **检查范围**：所有调用需预检的后端 API 的前端代码路径（采集前预检 cookie、提交前预检表单完整性、批量操作前预检数据状态）
  - **核心机制**（审查时必须理解）：
    - 后端 v4.27.0 起数据完整性预检方法签名统一为 `async def _check_xxx_completeness(self) -> str | None`，返回 None 表示通过、字符串表示错误描述（后端 B-REVIEW-DATA-COMPLETENESS-PRECHECK）
    - 后端预检使用双阈值 AND 判断（总数 + 关键项命中数），前端不具备后端业务规则的完整上下文（如哪些字段是"关键项"、阈值由业务场景决定）
    - 前端自行判断会与后端预检逻辑不一致，导致前端通过预检但后端拒绝（或反之）
    - 前端预检的职责是"调用预检端点 + 展示预检结果 + 引导用户修复"，不是"实现预检逻辑"
  - **判断信号**（grep 检测）：
    - `grep -nE "if\s+\(?\s*\w+\.length\s*<\s*\d+" frontend/src/**/*.tsx` 命中 → 检查是否在判断后端数据完整性
    - `grep -nE "if\s+\(?\s*!\w+\.(token|cookies|title|price)" frontend/src/**/*.tsx` 命中 → 检查是否在前端判断后端字段完整性
    - `grep -nE "/api/\w+/precheck" frontend/src/api/**/*.ts` 未命中 → 检查是否有调用后端预检端点
    - 用户反馈"前端预检通过但后端拒绝" → 必查前端是否自行实现预检逻辑
  - **修复模式**：
    ```typescript
    // ✅ 正确：调用后端预检端点
    try {
      const precheck = await collectionApi.precheckItem(itemId)
      if (!precheck.passed) {
        message.warning(precheck.reason)  // 如 "cookie 数量不足（4/22），请重新登录"
        return
      }
      await collectionApi.collectItem(itemId)  // 预检通过才调用主接口
    } catch (e) {
      message.error(extractApiError(e), 5)
    }

    // 禁止：前端自行判断（与后端预检逻辑可能不一致，阈值硬编码）
    ```
  - **配置参数**：`failure_reason_chain_frontend` 节点（在 `config.yaml` 管理，不硬编码）：
    - `precheck_endpoint_pattern`（默认 `"/api/<resource>/precheck"`，后端预检端点 URL 模式）
    - `precheck_result_field`（默认 `"passed"`，预检结果中是否通过的字段名）
    - `precheck_reason_field`（默认 `"reason"`，预检结果中失败原因的字段名）
    - `forbidden_frontend_precheck_patterns`（默认 `["length < \\d+", "!\\w+\\.token", "!\\w+\\.title"]`，禁止前端自行实现的预检模式）
    - `backend_precheck_method_source`（默认 `"xianyu-backend-code-review.data_completeness_precheck.method_name_pattern"`，后端预检方法来源，确保前后端契约对齐）
  - **适用场景**：调用需预检的后端 API（采集前预检 cookie、提交前预检表单、批量操作前预检数据状态）；后端已提供预检端点的接口；预检逻辑涉及业务规则（如哪些字段是关键项、阈值由业务场景决定）
  - **不适用场景**：纯前端表单校验（必填字段、格式校验、长度限制，用 antd Form rules 即可）；无需预检的简单查询接口（GET /api/items）；前端可独立判断的非业务规则（如"选择的批量操作数量是否超过 100"）
  - **历史教训**：闲鱼详情采集前前端自行判断 cookie 数量（`if (cookies.length < 4)`），但后端预检阈值是 22（关键 cookie 命中数），前端通过预检但后端仍返回 401。修复方式：前端改为调用 `/api/cookies/precheck` 端点，后端返回 `{"passed": false, "reason": "关键 cookie 命中数不足（4/12）"}`，前端展示原因并引导用户重新登录
  - **对应后端原则**：后端必须提供预检端点 + 预检方法签名统一为 `str | None` + 双阈值 AND 判断，详见 `xianyu-backend-code-review` v4.27.0 的 `B-REVIEW-DATA-COMPLETENESS-PRECHECK`

- 🆕v4.27【强制】**F-REVIEW-MOCK-FIELD-SET-SYNC：mock 数据完整字段集同步**
  - 维度归属：25 端到端失败原因链前端侧同步原则
  - 严重等级：warning
  - **检查点**：前端单元测试/集成测试的 mock 数据是否覆盖后端 Pydantic 模型的完整字段集，新增后端字段后前端 mock 是否同步补齐
  - **判定标准**：**禁止**前端 mock 数据仅包含测试用例当前需要的字段（如 `mockItem = { id: 1, title: 'test' }` 但后端 `Item` 模型有 12 个字段）。必须从后端 Pydantic 模型导出完整字段集作为 mock 基线，测试用例在基线上 override 需要的字段。新增后端字段后必须同步更新 mock 基线，避免测试通过但生产环境类型不一致
  - **检查范围**：所有前端单元测试/集成测试中的 mock 数据（API 响应 mock、组件 props mock、Zustand store 初始状态 mock）
  - **核心机制**（审查时必须理解）：
    - 后端 v4.27.0 起测试 mock 必须覆盖完整字段集（后端 B-REVIEW-TEST-MOCK-SYNC），前端同样需要同步
    - 前端 mock 数据不完整会导致：测试通过但生产环境访问未 mock 的字段时类型报错；TS 类型检查可能因 mock 类型断言绕过；新增后端字段后前端未同步 mock 会导致测试用例无法覆盖新字段逻辑
    - 后端 Pydantic 模型是字段集的唯一真实来源（single source of truth），前端 mock 必须与之一致
    - 前端可通过 `api/types.ts` 中声明的接口反推字段集，但 `api/types.ts` 必须与后端 Pydantic 模型同步（F-REVIEW-TYPE-CONTRACT-ALIGN）
  - **判断信号**（grep 检测）：
    - `grep -nE "const\s+mock\w+\s*=\s*\{\s*id:" frontend/src/**/*.test.tsx` 命中 → 检查 mock 是否仅包含部分字段
    - `grep -nE "as\s+(Item|Task|Order|Config)\b" frontend/src/**/*.test.tsx` 命中 → 检查是否用 `as` 类型断言绕过字段完整性检查
    - 后端新增字段后 `git diff frontend/src/api/types.ts` 无变更 → 前端类型未同步，mock 必然也不完整
    - 用户反馈"测试通过但生产环境类型报错" → 必查前端 mock 是否覆盖完整字段集
  - **修复模式**：
    ```typescript
    // ✅ 正确：从完整字段集基线 override
    // frontend/src/test/mocks/itemMocks.ts
    import type { Item } from '@/api/types'

    // 完整字段集基线（与后端 Item Pydantic 模型一一对应）
    export const mockItemBaseline: Item = {
      id: 1,
      title: 'test item',
      price: 100,
      description: '',
      seller_id: 'seller_001',
      status: 'active',
      created_at: '2026-07-05T10:00:00Z',
      updated_at: '2026-07-05T10:00:00Z',
      // ... 所有后端 Item 模型字段
    }

    // 测试用例在基线上 override 需要的字段
    const mockItem: Item = { ...mockItemBaseline, status: 'completed' }

    // 禁止：仅包含测试用例当前需要的字段（as 绕过类型检查）
    ```
  - **配置参数**：同 `failure_reason_chain_frontend` 节点
  - **适用场景**：前端单元测试/集成测试中的 mock 数据；后端 Pydantic 模型新增字段后前端 mock 同步；TS 严格模式下需要 mock 数据类型完整才能通过编译的场景
  - **不适用场景**：纯前端工具函数测试（无后端模型对应）；只测试组件渲染逻辑的 storybook 故事（可仅传必要 props）；快速原型验证阶段的临时 mock（但需在 PR 前补齐）
  - **历史教训**：闲鱼详情采集接口新增 `failure_reason` 字段后，前端测试 mock 未同步补齐，导致前端 catch 块访问 `err.failure_reason` 时在测试环境为 `undefined`，测试通过但生产环境逻辑分支未覆盖。修复方式：建立 `frontend/src/test/mocks/` 目录集中管理 mock 基线，新增后端字段后同步更新基线文件
  - **对应后端原则**：后端测试 mock 必须覆盖完整字段集 + 集中管理，详见 `xianyu-backend-code-review` v4.27.0 的 `B-REVIEW-TEST-MOCK-SYNC`
