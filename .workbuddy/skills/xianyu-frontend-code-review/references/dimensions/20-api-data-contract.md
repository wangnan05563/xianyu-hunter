# 20. API 数据源一致性与类型契约对齐 🆕v4.4

- 【强制】**F-REVIEW-API-DATA-SOURCE-CONSISTENCY：API 响应消费一致性**：同一 API 响应被多处组件消费时，必须共用同一 fetch 结果（通过 store/context 缓存），禁止各组件独立调用导致数据不一致；后端返回新增字段时所有消费方必须同步更新
  - 检查清单（参数由 `config.yaml` 的 `api_data_source_consistency` 节点管理）：
    - `enabled`：默认 `true`
    - `shared_fetch_apis`：默认 `["/api/stats", "/api/prices/histogram", "/api/config"]`，需共享 fetch 的端点
    - `require_type_sync`：默认 `true`，后端新增字段时前端 types.ts 必须同步
  - **判断信号**：两个以上组件各自调用同一 `priceApi.histogram()` → 必须改为共享 fetch；后端 summary 新增 `task_price_range` 字段但前端 `HistogramData` 类型未声明 → 类型契约断裂
  - **修复模式**：将 fetch 结果存入 store/context，各组件从 store 读取；后端新增字段后立即在 `api/types.ts` 同步声明并注释字段语义
  - **适用**：仪表盘多卡片消费同一 API、配置页与业务页共用配置数据、后端响应结构变更
  - **不适用**：独立页面的独立 API 调用、明确需要实时刷新的独立请求
  - **历史教训**：后端 `price_histogram.py` summary 新增 `task_price_range` 字段，若前端 `HistogramData` 类型未同步声明，TS 严格模式下访问 `histogram.summary.task_price_range` 会类型报错；`PriceStrategy.tsx` 独立调用 `priceApi.histogram()` 且检查 `data?.counts`（不存在的字段），导致始终走 catch 降级到模拟数据

- 【强制】**F-REVIEW-TYPE-CONTRACT-ALIGN：前后端类型契约对齐**：后端 Pydantic 模型/响应体新增或修改字段时，前端 `api/types.ts` 必须同步更新；可选字段用 `field?: T`，可空字段用 `field: T | null`
  - 检查清单（参数由 `config.yaml` 的 `type_contract_align` 节点管理）：
    - `enabled`：默认 `true`
    - `type_file_path`：默认 `"frontend/src/api/types.ts"`
    - `optional_vs_null`：默认 `"optional"`，优先用 `field?: T` 而非 `field: T | null`
  - **判断信号**：后端响应含 `task_price_range: {min_price: float | null, max_price: float | null}` 但前端类型未声明 → 必须补齐；前端用 `as any` 绕过类型检查 → 必须改为精确类型
  - **修复模式**：后端新增字段后，在 `types.ts` 对应接口同步声明，注释字段语义和可空场景；前端消费新增字段时先做 null 检查
  - **适用**：所有后端响应结构变更、新增 API 端点、字段语义变更
  - **不适用**：内部工具函数返回值、纯前端计算字段

- 【建议】**F-REVIEW-ERROR-CODE-CONSUMPTION：error_code 消费决策**：后端错误响应含 `error_code` 时，前端必须根据 error_code 做重试/降级决策，而非统一展示错误信息
  - 检查清单（参数由 `config.yaml` 的 `error_code_consumption` 节点管理）：
    - `enabled`：默认 `true`
    - `retryable_codes`：默认 `["network_error", "timeout", "rate_limited", "service_unavailable"]`
    - `non_retryable_codes`：默认 `["item_not_found", "invalid_params", "auth_failed", "business_rule"]`
  - **判断信号**：catch 块统一 `message.error(extractApiError(e))` 但未检查 `error_code` → 可重试错误未提供重试入口
  - **修复模式**：解析响应体 `error_code`，可重试错误显示"重试"按钮，不可重试错误显示具体原因
  - **适用**：批量操作错误处理、需用户决策重试的场景
  - **不适用**：简单表单提交错误（用 extractApiError 统一处理即可）

- 🆕v4.25【强制】**F-REVIEW-ERROR-HANDLING-CONSISTENCY：错误处理一致性检查**
  - 维度归属：20 错误提示语义 + 配置链路
  - 严重等级：error
  - **检查点**：API 调用的 catch 块是否使用 `extractApiError` 提取具体错误信息
  - **判定标准**：**禁止** `message.error('保存失败')` / `message.error('操作失败')` 等无具体信息的错误提示。必须使用 `extractApiError(e)` 提取状态码 + 详情，显示时长不少于 `error_display_duration_sec`（默认 5 秒）
  - **检查范围**：所有含 try/catch 的 API 调用
  - **核心机制**（审查时必须理解）：
    - `extractApiError(e)` 工具函数位于 `frontend/src/utils/apiError.ts`，能从 axios 错误中提取 `error.response.status` + `error.response.data.detail` + `error.response.data.message` 等字段，组合成可读的错误信息
    - 用 `message.error('保存失败')` 让用户无法判断失败原因（网络错误/参数错误/权限不足/服务异常），无法自助排查
    - 显示时长 < 5 秒会导致用户来不及读完错误信息就被吞掉，特别是包含状态码 + 详情的长文本
    - 错误信息应包含：HTTP 状态码（401/403/404/500/502/503/504）+ 后端返回的具体 detail（如"商品不存在"/"评分必须大于 0"/"权限不足"）
  - **判断信号**（grep 检测）：
    - `grep -nE "message\.error\('保存失败'\)|message\.error\('操作失败'\)|message\.error\('加载失败'\)" frontend/src/pages/**/*.tsx` 命中 → 违规
    - `grep -nE "catch \(.*\) \{ message\.error\('" frontend/src/pages/**/*.tsx` 命中 → 检查是否调用 `extractApiError`
    - `grep -nE "message\.error\(.*\)" frontend/src/pages/**/*.tsx | Select-String -NotMatch "extractApiError"` 命中 → 检查 message.error 是否包含具体信息
    - `grep -nE "message\.error\([^,]+\)$" frontend/src/pages/**/*.tsx` 命中 → 检查是否省略了 duration 参数（应 >= 5 秒）
    - 用户反馈"保存失败但不知道原因" → 必查 catch 块是否用 extractApiError
  - **修复模式**：
    ```typescript
    // ✅ 正确：用 extractApiError 提取具体错误，显示 5 秒
    import { extractApiError } from '@/utils/apiError'

    try {
      await taskApi.update(taskId, payload)
      message.success('保存成功')
    } catch (e) {
      message.error(extractApiError(e), 5)  // 显示 "400: search_config 字段必须是对象"
    }

    // 禁止：无具体信息的错误提示（'保存失败' 用户不知道为什么失败）

    // 禁止：显示时长过短（默认 3 秒，长文本来不及读）

    // 禁止：直接用 error.message 丢失状态码（只有 "Request failed with status code 400"，没有 detail）
    ```
  - **配置参数**：`frontend_error_handling` 节点（在 `config.yaml` 管理，不硬编码）：
    - `enabled`（默认 `true`，开关本检查）
    - `error_display_duration_sec`（默认 `5`，错误提示最小显示时长，秒）
    - `required_error_extractor`（默认 `"extractApiError"`，强制使用的错误提取工具函数名）
    - `forbidden_error_patterns`（默认 `["保存失败", "操作失败", "加载失败", "提交失败", "请求失败"]`，禁止使用的笼统错误文案列表）
    - `required_fields_in_message`（默认 `["status_code", "detail"]`，错误信息中必须包含的字段）
    - `extractor_function_path`（默认 `"frontend/src/utils/apiError.ts"`，extractApiError 函数所在路径）
    - `detection_signals`（默认 `["message.error('", "catch (e) { message.error", "message.error(e.message)"]`，触发检查的代码模式）
  - **适用场景**：所有含 try/catch 的 API 调用（保存/更新/删除/查询/批量操作/SSE 错误处理）
  - **不适用场景**：非 API 错误（如本地计算错误、表单验证错误、本地 storage 读写错误）；开发环境调试信息（`console.error`）；用户主动取消操作（`message.info('已取消')`）；表单客户端校验错误（`form.setFields([{ errors: [...] }])`）
  - **历史教训**：任务级配置覆盖功能开发时，保存接口 catch 块用 `message.error('保存失败')`，用户反馈"清除覆盖不生效"但前端只显示"保存失败"，无法定位是 400（参数错误）还是 500（服务异常）还是 401（登录过期）。修复方式：改为 `message.error(extractApiError(e), 5)`，显示具体状态码 + 后端 detail（如"400: search_config 必须显式传 null 才能清除覆盖"），用户能自助排查
  - **对应后端原则**：后端 API 必须返回结构化错误响应（含 `detail` + `error_code` + `status_code`），禁止只返回 `{"detail": "Internal Server Error"}`，详见 `xianyu-backend-code-review` 的 `B-REVIEW-ERROR-RESPONSE-STRUCTURE`（如有）
