# Error Handling 编码规范
> 本文件归档 xianyu-hunter-dev skill 中与「error handling」主题相关的编码规范。
> 主索引见 [SKILL.md](../../../SKILL.md) 的"step 索引表"，元规范见 [meta-rules.md](../../../references/meta-rules.md)。

---

### step 23：会话失效处理与错误粒度区分【强制】🆕v4.1

23. **会话失效处理与错误粒度区分【强制】🆕v4.1**
    - **重试失败后状态信号必须传递**：SSE/HTTP 接口包含重试逻辑时，重试代码块结束后必须检查关键状态标志（如 `last_session_invalid`），状态仍异常则推送明确错误事件并 `return`，**禁止**"重试失败但仍走成功流程"误导用户
    - **错误粒度三类区分**（状态码与文案映射通过 review skill 的 config.yaml 管理）：
      - `503/504`：稍后重试（网络超时/限流/服务繁忙）
      - `401/403`：需用户介入（登录失效/权限不足）+ 明确指引"请前往 X 重新登录"
      - `502`：需重启服务（浏览器断开/TargetClosed）
    - **Cookie 检查全面性**：依赖多类 Cookie 的接口前置检查必须覆盖所有关键 token（身份 Cookie + 会话 token 如 `_m_h5_tk`），**不能**只检查身份 Cookie 存在性而忽略会话 token 有效性
    - **对照证据定位法**（问题排查）：用户反馈"业务查不到"但无明确错误时，排查首要步是要求用户提供"相同条件下浏览器直连成功"的对照证据；浏览器直连成功 → 聚焦 Cookie/会话状态，而非网络/代理问题
    - **适用**：所有含重试逻辑的 SSE/HTTP 接口、依赖多类 Cookie 的接口；**不适用**：一次性请求无重试逻辑、纯 token 认证（JWT）
    - **历史教训**：实时搜索 RGV587 重试失败后未检查 `last_session_invalid`，继续走 filtering 流程，前端只看到"0 个商品"误以为没货，实际是闲鱼登录态已过期


---

### step 39：错误提示语义准确性【强制】🆕v4.5

39. **错误提示语义准确性【强制】🆕v4.5**
    - 面向用户的错误提示必须与实际错误原因语义匹配，**禁止**将特定错误码映射为不相关的语义
    - **判断信号**：后端将特定错误码（如 RGV587）映射为 HTTP 状态码时，状态码语义必须与错误码根因一致
    - **修复模式**：错误码根因分析 → 选择语义匹配的状态码 → 提示文案与根因一致 → 提供正确的操作出口（"稍后重试" vs "重新登录"）
    - **适用**：所有面向用户的错误提示（API 响应 detail、前端 Alert、SSE error 事件）
    - **不适用**：内部调试日志、堆栈跟踪（developer-facing）
    - **历史教训**：RGV587 是 mtop API 的 `_m_h5_tk` 临时 token 过期（TTL 1 小时），不是浏览器 Cookie/登录态失效，但后端映射为 HTTP 401("闲鱼登录已过期")，前端显示"Cookie 失效或会话过期"。实际多查几次能成功——说明不是登录态失效。修复后提示改为"搜索令牌临时过期，请稍后重试"


---

### step 51：异步操作用户反馈三态【强制】🆕v4.7

51. **异步操作用户反馈三态【强制】🆕v4.7**
    - 前端所有异步操作（按钮点击触发 API、表单提交、数据刷新）必须实现 **loading（进行中）→ success（成功）→ error（失败）** 三态用户反馈，**禁止** `.catch(() => {})` 静默吞错误
    - **判断信号**：代码含 `.then(...).catch(() => {})` 空 catch / `try { await api() } catch {}` 空 catch / 异步操作无 loading 状态 → 视为违规
    - **修复模式**：
      ```typescript
      const onAction = (id: string) => {
        const hide = message.loading(`正在处理 ${id.slice(0, 8)}...`, 0)
        api.execute(id).then(() => {
          hide()
          message.success(`已处理：${id.slice(0, 8)}...`)
          refresh()
        }).catch((err: unknown) => {
          hide()
          const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
          message.error(detail || `处理失败：${id.slice(0, 8)}...，请稍后重试`)
        })
      }
      ```
    - **关键约束**：
      - `message.loading` 必须返回 `hide` 函数，在 `then` 和 `catch` 分支都调用 `hide()`
      - 错误提示必须从 `err.response.data.detail` 提取后端返回的具体错误（与后端错误语义对齐，参考 F-REVIEW-ERROR-SEMANTICS），**禁止**只显示通用"操作失败"
      - loading 文案必须包含资源标识（如 ID 前 8 位），让用户知道在处理什么
      - 操作成功后必须触发数据刷新（`refresh()` / `refetch()`），让用户看到结果
    - **配置参数**：`loading_template`（如"正在处理 {id}..."）、`success_template`（如"已处理：{id}..."）、`error_template`（如"处理失败：{id}...，请稍后重试"）、`id_display_length`（默认 8）在 `config.yaml` 的 `async_feedback` 节点管理
    - **适用**：所有用户主动触发的异步操作（按钮点击、表单提交、链接点击触发 API）
    - **不适用**：后台静默刷新（如 SSE 推送、定时轮询）、页面初始化加载（用 Skeleton/Spin）、开发环境调试
    - **历史教训**：评估明细页点击商品标题超链接触发 `itemApi.refresh(itemId)`，前端 `.catch(() => {})` 静默吞错误，用户点击后无任何反馈，不知道采集是否成功。修复后加 `message.loading` + `message.success` + `message.error` 三态反馈


---

### step 76：前后端错误码契约与超时识别【强制】🆕v4.13

76. **前后端错误码契约与超时识别【强制】🆕v4.13**
    - 前端调用后端含重试/异步逻辑的接口时，必须用模块级 `statusMessages: Record<number, string>` 映射表 + 独立 `isAxiosTimeout()` 函数双路识别错误：axios 超时无 `response.status`，必须用 `error.code === 'ECONNABORTED'` 或 `/timeout/i.test(error.message)` 识别；后端按语义区分的状态码（接续 step 71）必须在前端映射表中有对应文案，**禁止**所有错误走同一通用文案导致用户无法区分"网络超时"与"商品下架"
    - **判断信号**：前端 catch 块含 `err.response?.status` 但无超时识别 → 必须补 `isAxiosTimeout()` 模块级函数；前端 `message.error('官方采集失败，请稍后重试')` 出现在多个 catch 块 → 必须按状态码差异化文案
    - **修复模式**：
      ```typescript
      // ✅ 模块级常量 + 模块级函数
      const COLLECT_OFFICIAL_ERROR_MESSAGES: Record<number, string> = {
        503: '官方采集需要浏览器实例，请以 XH_WITH_SCHEDULER=1 模式启动',
        403: '闲鱼登录已过期，请重新登录闲鱼',
        440: '闲鱼登录已过期，请重新登录闲鱼',
        441: '触发闲鱼反爬限制，请稍后重试或手动完成验证',
        410: '商品详情页加载失败或已下架，请稍后重试',
        502: '浏览器连接异常，请重启服务后重试',
      }
      const COLLECT_OFFICIAL_TIMEOUT_MESSAGE = '官方采集超时（详情页+卖家主页加载缓慢），请稍后重试或检查网络'
      const COLLECT_OFFICIAL_FALLBACK_MESSAGE = '官方采集失败，请稍后重试'

      // axios 超时无 response.status，需通过 code 识别
      const isAxiosTimeout = (error: { code?: string; message?: string }): boolean =>
        error?.code === 'ECONNABORTED' || /timeout/i.test(error?.message || '')

      // 统一错误提示：超时优先 → status 映射 → fallback
      function showStatusError(err: unknown, statusMessages: Record<number, string>,
                               timeoutMessage: string, fallbackMessage: string): void {
        const error = err as { response?: { status?: number; data?: { detail?: string } }; code?: string; message?: string }
        if (isAxiosTimeout(error)) {
          message.error(timeoutMessage)
        } else if (error?.response?.status != null && statusMessages[error.response.status]) {
          message.error(error?.response?.data?.detail || statusMessages[error.response.status])
        } else {
          message.error(error?.response?.data?.detail || fallbackMessage)
        }
      }
      ```
    - **配置参数**：`frontend_error_contract.timeout_codes`（默认 `['ECONNABORTED']`，axios 超时 code 列表）、`frontend_error_contract.timeout_patterns`（默认 `['/timeout/i']`，超时 message 正则模式列表）、`frontend_error_contract.status_message_map`（场景到消息映射，按业务接口分组，如 `collect_official: { 410: '...', 441: '...' }`）、`frontend_error_contract.timeout_priority`（默认 `true`，超时识别优先于 status 映射）在 `config.yaml` 的 `frontend_error_contract` 节点管理
    - **适用**：含重试逻辑的 SSE/HTTP 接口、依赖多类 Cookie 的接口、含状态机的业务接口、浏览器自动化接口
    - **不适用**：一次性请求无重试逻辑、纯 token 认证（JWT 无超时概念）、内部 API（无业务文案需求）
    - **历史教训**：用户反馈"官方采集失败，请稍后重试"，理论推断为 axios 30s 超时，实际日志显示采集只花 12s，根因是后端选择器失效返回 502，前端无超时识别导致无法区分"超时"与"502"


---

### step 77：前端可重试错误集与退避策略【强制】🆕v4.13

77. **前端可重试错误集与退避策略【强制】🆕v4.13**
    - 前端调用后端接口必须区分「可重试错误」（410/441/502/timeout）与「需用户介入错误」（403/440/503），可重试错误用指数/固定退避重试 N 次（默认 N=1），重试时不弹消息避免打扰用户，**禁止**对所有错误一刀切重试导致需用户介入的错误被无意义重试
    - **判断信号**：前端 catch 块直接 throw 或直接 `message.error` → 必须评估错误是否可重试；前端 `retry_count` 硬编码数字 → 必须移到配置或模块级常量
    - **修复模式**：
      ```typescript
      // ✅ 可重试错误集 + 退避时间映射 + 重试不弹消息
      const RETRYABLE_STATUSES = new Set([410, 441, 502])
      const RETRY_DELAYS: Record<string, number> = {
        '410': 1000,   // 页面未加载，快速重试
        '441': 3000,   // 反爬触发，需 3s 冷却
        '502': 1000,   // 连接异常，快速重试
        'timeout': 2000,  // 超时，2s 后重试
      }

      async function collectOfficialWithRetry(itemId: string, taskId?: string): Promise<OfficialCollectResult> {
        const MAX_RETRIES = 1
        let lastErr: unknown
        for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
          try {
            return await evalApi.collectOfficial(itemId, taskId)
          } catch (err: unknown) {
            lastErr = err
            if (attempt >= MAX_RETRIES) break
            const e = err as { response?: { status?: number }; code?: string; message?: string }
            const status = e?.response?.status
            const isTimeout = e?.code === 'ECONNABORTED' || /timeout/i.test(e?.message || '')
            const retryable = isTimeout || (status !== undefined && RETRYABLE_STATUSES.has(status))
            if (!retryable) break
            const delayKey = isTimeout ? 'timeout' : String(status)
            const delay = RETRY_DELAYS[delayKey] ?? 2000
            await new Promise(resolve => setTimeout(resolve, delay))
            // 重试时不弹消息，避免打扰用户（仅在最终失败时展示错误）
          }
        }
        throw lastErr
      }
      ```
    - **配置参数**：`frontend_retry_strategy.retryable_statuses`（默认 `[410, 441, 502]`，可重试状态码列表）、`frontend_retry_strategy.retry_delays_ms`（默认 `{410: 1000, 441: 3000, 502: 1000, timeout: 2000}`，状态码到退避时间映射）、`frontend_retry_strategy.max_retries`（默认 `1`，最大重试次数）、`frontend_retry_strategy.non_retryable_statuses`（默认 `[403, 440, 503]`，需用户介入的错误列表）、`frontend_retry_strategy.silent_on_retry`（默认 `true`，重试时不弹消息）在 `config.yaml` 的 `frontend_retry_strategy` 节点管理
    - **适用**：网络请求（axios/fetch）、临时性错误（410/441/502/timeout）、浏览器自动化接口
    - **不适用**：需用户介入的错误（403 权限不足/440 Cookie 过期/503 服务未启动）、不可重试业务错误（404 资源不存在）、事务性操作（POST/PUT/DELETE 需幂等性保证）
    - **历史教训**：前端对所有错误直接 `message.error`，用户被偶发的 441 反爬或 502 连接异常打扰，需用户手动重试；改为仅对可重试错误自动重试 1 次后，95% 的偶发失败用户无感知


---

### step 78：多层兜底链模式【强制】🆕v4.13

78. **多层兜底链模式【强制】🆕v4.13**
    - 从 SPA 页面提取数据必须按「特定→通用」多级兜底：DOM 选择器（className-dependent）→ `meta[property='og:title']` 等 SPA-universal 选择器（不依赖 className）→ `document.title` 等最末兜底，每层失败进入下一层，所有兜底失败才走 dump（参见 step 79），**禁止**只依赖单一 className 选择器导致页面改版时数据全空
    - **判断信号**：代码含 `page.query_selector('.specific-class')` 后无兜底 → 必须补 og:meta 与 document.title 兜底；多个 DOM 选择器都属于 className 依赖型 → 必须至少补一层非 className 依赖的兜底
    - **修复模式**：
      ```python
      # ✅ 多层兜底链：DOM 选择器 → og:title meta → document.title
      title = ""
      # 第一层：DOM 选择器（className-dependent，可能因页面改版失效）
      try:
          el = await page.query_selector(DETAIL_TITLE_MAIN)
          if el:
              title = (await el.inner_text() or "").strip()
      except Exception as e:
          logger.debug(f"详情页 {item_id} DOM 选择器提取失败: {e}")

      # 第二层：og:title meta（SPA-universal，不依赖 className）
      if not title:
          try:
              og_el = await page.query_selector("meta[property='og:title']")
              if og_el:
                  og_title = (await og_el.get_attribute("content") or "").strip()
                  if og_title:
                      title = og_title
                      logger.debug(f"详情页 {item_id} 标题从 og:title 兜底提取: {title}")
          except Exception as e:
              logger.debug(f"详情页 {item_id} og:title 提取失败: {e}")

      # 第三层：document.title（最末兜底）
      if not title:
          try:
              title = (await page.title() or "").strip()
          except Exception as e:
              logger.debug(f"详情页 {item_id} document.title 提取失败: {e}")

      # 所有兜底失败 → dump HTML（参见 step 79）
      if not title:
          await _dump_html_for_diagnosis(page, "title_extract", item_id)
      ```
    - **配置参数**：`dom_fallback_chain.strategies`（默认 `['dom_selector', 'og_meta', 'document_title']`，按顺序尝试的兜底策略）、`dom_fallback_chain.dom_selectors`（项目特定选择器列表，从 `infra/selectors.py` 读取）、`dom_fallback_chain.meta_selectors`（默认 `['og:title', 'og:description']`，SPA-universal meta 标签）、`dom_fallback_chain.final_fallback`（默认 `document_title`，最末兜底策略）、`dom_fallback_chain.dump_on_all_fail`（默认 `true`，所有兜底失败时触发 dump）在 `config.yaml` 的 `dom_fallback_chain` 节点管理（与 v4.3 B-REVIEW-FALLBACK-CHAIN 的"多方案降级"语义不同，本节点专指 DOM 提取兜底）
    - **适用**：SPA 页面选择器提取（标题/描述/价格）、多源数据兜底（API→缓存→默认值）、爬虫类应用
    - **不适用**：结构化 API 响应（JSON 字段直接取值）、单一来源数据、需要严格一致性的场景（如金融数据）
    - **历史教训**：闲鱼详情页改版，原 `DETAIL_TITLE_MAIN` 选择器（h1 元素）失效，标题提取为空触发 502，30 个 dump 文件全为空数组无法定位；改为 og:title 兜底后即使页面改版也能提取标题


---

### step 79：失败诊断 dump 机制【强制】🆕v4.13

79. **失败诊断 dump 机制【强制】🆕v4.13**
    - 关键选择器/数据提取失败时必须自动 dump `page.content()` 到 `logs/<场景>_<id>_<timestamp>.html`，`logger.warning` 记录 dump 路径，dump 必须用 `try/except` 包裹不能阻塞主流程，dump 是「事后取证」不是「在线恢复」，**禁止**依赖 dump 结果做运行时决策，**禁止** dump 敏感数据（如完整 cookie/auth header）
    - **判断信号**：代码含 `if not data: return None` 或 `raise HTTPException` 但无 dump → 必须在 return/raise 前 dump 现场用于事后取证；`logs/` 目录下 dump 文件全为空 `[]` → 必须验证 dump 时机（页面未渲染完成时 dump 会得到空数组）
    - **修复模式**：
      ```python
      # ✅ dump HTML 到文件，不阻塞主流程
      import time
      from pathlib import Path

      async def _dump_html_for_diagnosis(page, scenario: str, item_id: str) -> None:
          """关键提取失败时 dump HTML 用于事后取证

          为什么用 try/except 包裹：dump 失败不应影响主流程的异常处理
          为什么 dump 到文件而非内存：完整 HTML 可能几百 KB，内存保存会污染日志
          """
          try:
              timestamp = int(time.time())
              dump_path = Path("logs") / f"{scenario}_{item_id}_{timestamp}.html"
              html_content = await page.content()
              if not html_content or html_content == "<html><head></head><body></body></html>":
                  logger.warning(f"详情页 {item_id} {scenario} dump 为空（页面可能未渲染完成）")
                  return
              dump_path.write_text(html_content, encoding="utf-8")
              logger.warning(f"详情页 {item_id} {scenario} 失败，HTML 已 dump 到 {dump_path}")
          except Exception as dump_err:
              logger.warning(f"详情页 {item_id} {scenario} dump 失败: {dump_err}")

      # 在所有兜底失败后调用 dump
      if not title:
          await _dump_html_for_diagnosis(page, "title_extract", item_id)
          raise HTTPException(502, "商品详情页加载失败或已下架")
      ```
    - **配置参数**：`failure_dump.enabled`（默认 `true`，是否启用 dump）、`failure_dump.dump_dir`（默认 `logs/`，dump 文件目录）、`failure_dump.filename_pattern`（默认 `{scenario}_{id}_{timestamp}.html`，文件名模式）、`failure_dump.max_file_size_mb`（默认 `10`，单文件最大大小，超过截断）、`failure_dump.max_files_per_scenario`（默认 `100`，每个场景保留的最大文件数，超过自动清理最旧）、`failure_dump.scenarios`（需 dump 的场景列表，如 `['title_extract', 'seller_extract', 'reviews_extract']`）、`failure_dump.sensitive_patterns`（默认 `['cookie', 'token', 'authorization', 'set-cookie']`，需脱敏的正则模式列表）在 `config.yaml` 的 `failure_dump` 节点管理
    - **适用**：浏览器自动化选择器失败、HTML 内容提取失败、爬虫数据提取失败、需要事后取证的场景
    - **不适用**：在线高频调用（dump 影响性能）、生产环境敏感数据（需脱敏或禁用 dump）、结构化 API 响应失败（应用日志记录 JSON）、纯计算函数失败（无 HTML 现场）
    - **历史教训**：30 个 `detail_dom_*.json` dump 文件全为空数组 `[]`，无法定位选择器失效的具体原因，因为 dump 时机在页面未渲染完成时；改为 dump `page.content()` 完整 HTML 并校验非空后才写入文件


---

### step 96：除零兜底禁止凑数规范【强制】🆕v4.17

**背景**：`_detect_post_burst` 中 `previous_count=0` 时用 `recent_count / 0.1` 凑数，产生 `ratio=100.0` 误导数字写入 reason 字符串展示给用户。

**规范**：
1. 除零/空值兜底禁止用凑数小数（`x / 0.1`）伪装比值
2. 比值/比率/百分比计算中 `previous_count`/`baseline` 可能为 0 时，直接置为 `0.0` 或 `float('inf')`
3. 写入 reason/log 展示给用户的数值，无意义时用字符串 `"N/A"` 而非数字

**判断逻辑**：
- grep ` / 0\.` 或 `/ 0.1` 或 `/ max(*, 1)` 等可疑除零兜底
- 逐个核查语义：是否在展示给用户的 reason/log 中？是否在统计数值中？
- 内部计算用途的 `max(prev, 1)` 防止除零可接受（结果不展示）；展示用途必须用 `0.0` + `N/A` 文案

**反例**：
```python
# ❌ 错误：凑数小数伪装比值，展示 "ratio=100.0x" 误导用户
ratio = recent_count / 0.1 if recent_count > 0 else 0.0
result.reasons.append(f"dealer:post_burst(ratio={ratio}x)")
```

**正例**：
```python
# ✅ 正确：previous=0 时 ratio=0.0，reason 显示 N/A
if previous_count > 0:
    ratio = recent_count / previous_count
else:
    ratio = 0.0
ratio_str = f"{ratio}x" if previous_count > 0 else "N/A"
result.reasons.append(f"dealer:post_burst(ratio={ratio_str})")
```

**配置参数**：`divzero_fallback` 节点（enabled / detect_patterns / display_value_for_empty_baseline）

**适用场景**：比值/比率/百分比计算；`previous_count`/`baseline` 可能为 0 的对比场景；写入 reason/log 展示给用户的数值
**不适用场景**：内部计算用途的兜底（如 `max(prev, 1)` 防止除零但结果不展示）；倒计时/计时器场景


---

### step 97：重复错误处理抽取规范【强制】🆕v4.17

**背景**：`onAIEval` 与 `onDeepAnalyze` 的 403/404/422 三段 if-else 完全重复，复制粘贴模式导致后续修改状态码文案时需同步多处。

**规范**：
1. 两处以上相同的 if-else 状态码分支必须抽取工具函数
2. 工具函数签名统一为 `handleXxxError(err, fallbackMsg, closeModal/...)`
3. 抽取后原调用处仅保留 `handleXxxError(err, '失败文案', () => setModalOpen(false))` 一行

**判断逻辑**：
- grep `status === 403` 或 `status === 404` 出现位置
- 同文件内 >= 2 处即需抽取
- 检查抽取后的工具函数是否覆盖所有状态码分支（403/404/422/500 等）

**反例**：
```typescript
// ❌ 错误：两处重复的 if-else
const onAIEval = async (itemId) => {
  try { ... } catch (err) {
    if (status === 403) message.error('AI 功能未开启')
    else if (status === 404) message.error('商品不存在')
    else if (status === 422) message.error('参数错误')
    else message.error(detail || 'AI 评估失败')
    setAiModalOpen(false)
  }
}
const onDeepAnalyze = async (itemId) => {
  try { ... } catch (err) {
    if (status === 403) message.error('AI 功能未开启')  // 重复
    else if (status === 404) message.error('商品不存在')  // 重复
    else if (status === 422) message.error('参数错误')  // 重复
    else message.error(detail || '深度分析失败')
    setDeepModalOpen(false)
  }
}
```

**正例**：
```typescript
// ✅ 正确：抽取 handleAiError 工具函数
const handleAiError = (err: unknown, fallbackMsg: string, closeModal: () => void) => {
  const status = (err as { response?: { status?: number } })?.response?.status
  const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
  if (status === 403) message.error('AI 功能未开启，请在配置页面开启')
  else if (status === 404) message.error('商品不存在于数据库中')
  else if (status === 422) message.error('请求参数错误：商品 ID 为空')
  else message.error(detail || fallbackMsg)
  closeModal()
}
const onAIEval = async (itemId) => {
  try { ... } catch (err) {
    handleAiError(err, 'AI 评估失败，请检查 AI 配置', () => setAiModalOpen(false))
  }
}
```

**配置参数**：`error_handler_extract` 节点（enabled / min_duplicate_count / detect_patterns / unified_signature）

**适用场景**：多个 async 函数调用同一后端端点；多个函数处理同一类外部 API 错误（HTTP 状态码分类）
**不适用场景**：仅一处调用的错误处理（抽取后反而增加间接性）；错误处理逻辑有差异（如不同端点状态码集合不同）


---

### step 121：前端错误处理规范【强制】🆕v4.26

**背景**：前端 API 调用的 catch 块必须用统一错误提取工具（`extractApiError`），显示具体错误信息（含状态码 + 详情）。

**问题**：前端 API 调用的 catch 块只显示 `message.error('保存失败')` 等无具体信息的错误提示，用户无法区分网络错误/验证错误/服务器错误，难以排查问题。

**规范**：

1. **统一错误提取【强制】**：API 调用的 catch 块必须用项目统一的 `extractApiError` 工具提取错误信息：
   ```typescript
   // ✅ 正确：用 extractApiError 显示具体错误信息，时长 5 秒
   catch (e) {
     message.error(extractApiError(e), 5);
   }

   // ❌ 错误：无具体信息的错误提示
   catch (e) {
     message.error('保存失败');
   }
   ```

2. **错误显示时长【强制】**：错误显示时长不少于 5 秒（配置驱动），保证用户有时间阅读。

3. **禁止无信息提示【强制】**：禁止 `message.error('保存失败')` / `message.error('操作失败')` 等无具体信息的错误提示。

**配置驱动**：错误显示时长、错误提取函数名、禁止的错误模式等参数在 `config.yaml` 的 `frontend_error_handling` 节点管理，包含 `error_display_duration_sec` / `required_error_extractor` / `forbidden_error_patterns` 等，不硬编码在技能中。

**适用场景**：
- 所有含 try/catch 的 API 调用
- 表单提交、配置保存、数据获取等可能失败的操作

**不适用场景**：
- 非 API 错误（如本地计算错误、表单验证错误）
- 已知预期错误（如取消操作）

**历史教训**：`TaskEditor.tsx` 的 `doSubmit` catch 块只显示 `message.error('保存失败')`，用户无法区分网络错误/验证错误/服务器错误，排查困难。修复：改用 `extractApiError(e)` + 5 秒显示时长。

**判断信号（review 触发条件）**：
- `grep "message.error('"` 不含 `extractApiError` 的 catch 块
- `grep "catch (e)"` 后跟 `message.error('xxx失败')` 等无信息提示


---

### step 123：失败原因传递链规范（reason propagation chain）【强制】🆕v4.27

**背景**：底层操作（如 `collector.detail()`）返回 `None`/空结果时，上层调用者无法区分根因（cookie 失效 / 反爬验证 / 页面下架 / 网络异常），导致一律抛 502 含糊错误，用户无法判断该重登录、该等待还是该手动验证。

**问题**：商品列表点击标题触发官方采集报错 `Failed to collect item detail: page unavailable or login expired`，所有失败都归为 502，用户无法区分根因，错误文案与实际原因无关。

**规范**：

1. **底层设置失败原因属性【强制】**：底层操作返回 `None`/空/失败时，必须在自身对象上设置 `last_<operation>_failure_reason` 属性，取值为可枚举的字符串：

   ```python
   # collector/_detail.py 各失败分支
   self.last_detail_failure_reason = "home_title_redirect"  # 首页标题（cookie 失效）
   self.last_detail_failure_reason = "login_redirect"        # 登录页重定向
   self.last_detail_failure_reason = "verify_redirect"       # 验证码页
   self.last_detail_failure_reason = "page_closed"           # 页面被关闭
   self.last_detail_failure_reason = "http_status_error"     # HTTP 4xx/5xx
   self.last_detail_failure_reason = "target_closed_exception"  # TargetClosed
   self.last_detail_failure_reason = "redirected_away_from_item"  # 非商品页
   ```

2. **中层按 reason 映射状态码【强制】**：中层业务模块读取 `last_<operation>_failure_reason` 属性，按 reason 映射到语义正确的 HTTP 状态码：

   ```python
   reason = getattr(self.container.collector, "last_detail_failure_reason", "") or "unknown"
   if reason in ("home_title_redirect", "login_redirect"):
       raise CollectionError(401, "采集失败：登录态失效，请重新登录", item_id=item_id)
   if reason == "verify_redirect":
       raise CollectionError(429, "采集失败：触发反爬验证码，请手动完成验证", item_id=item_id)
   if reason in ("page_closed", "target_closed_exception"):
       raise CollectionError(503, "采集失败：浏览器页面被关闭，请稍后重试", item_id=item_id)
   raise CollectionError(502, f"采集失败：详情页不可用（reason={reason}），请稍后重试", item_id=item_id)
   ```

3. **文案与根因语义匹配【强制】**：错误文案必须与根因一致，**禁止**含糊的"page unavailable or login expired"覆盖所有场景。

4. **reason 值可枚举集中管理【强制】**：所有可能的 reason 值必须定义为模块级常量或 `Literal` 类型，禁止散落字符串字面量。

**配置驱动**：reason 映射表、状态码映射、文案模板等参数在 `config.yaml` 的 `failure_reason_propagation` 节点管理，包含 `reason_to_status_code_mapping` / `reason_enum_values` / `fallback_status_code` / `fallback_message_template` 等，不硬编码在技能中。

**适用场景**：
- 多层架构中底层操作有明确失败原因枚举的场景（domain → infra → modules → web）
- 浏览器自动化（Playwright detail/seller_profile/search 等多失败模式）
- 含重试逻辑的 SSE/HTTP 接口

**不适用场景**：
- 单层脚本（无中层映射需求）
- 失败原因不可枚举的场景（用 unknown 兜底即可）
- 纯 token 认证（JWT 失败原因单一）

**历史教训**：商品详情采集 `collector.detail()` 返回 `None` 时，`_collect_detail_only` 一律抛 `CollectionError(502, "Failed to collect item detail: page unavailable or login expired")`，用户反馈"还是报错"但无法判断是 cookie 失效还是页面下架。修复后 `_detail.py` 在 7 个失败分支设置 `last_detail_failure_reason`，`_collect_detail_only` 按 reason 映射 401/429/502/503，文案明确告诉用户该怎么做。

**判断信号（review 触发条件）**：
- `grep "raise.*Error.*502"` 出现含糊文案（如 "page unavailable" / "login expired" / "unknown error"）
- 底层操作返回 `None` 但未设置 `last_*_failure_reason` 属性
- reason 字符串字面量散落在多个 if/elif 分支而非集中常量


---

### step 124：数据完整性预检规范（pre-call completeness check）【强制】🆕v4.27

**背景**：依赖外部状态的接口（如依赖 cookie 的详情采集、依赖 token 的搜索）在调用失败后，上层无法区分是状态不完整还是目标不可用。前置检查可在调用前识别状态问题，给出明确错误。

**问题**：`cookies_default.json` 只有 4 个身份 cookie（不完整），但 `_collect_detail_only` 直接调用 `collector.detail()`，详情页 SPA 渲染失败返回 `None`，上层抛 502 含糊错误。预检 cookie 完整性可避免"调用-失败-含糊报错"的循环。

**规范**：

1. **预检方法签名【强制】**：依赖外部状态的接口必须提供 `_check_<state>_completeness() -> str | None` 方法，返回 `None` 表示完整，返回 `str` 表示错误信息（含具体缺失情况）：

   ```python
   async def _check_detail_cookie_completeness(self) -> str | None:
       cookies = await self._get_browser_cookies()
       cookie_names = {c.get("name", "") for c in cookies}
       identity_found = set(_IDENTITY_COOKIES) & cookie_names
       session_found = _SESSION_COOKIES & cookie_names
       if len(cookies) >= _MIN_COUNT and len(session_found) >= _MIN_HITS:
           return None
       return f"Cookie 不完整（共 {len(cookies)} 个，身份 {sorted(identity_found)}，会话 {sorted(session_found)} 不足）"
   ```

2. **双阈值 AND 判断【强制】**：完整性判断必须用双阈值 AND 关系（任一不满足即不完整），避免单阈值误判：
   - 总数阈值（如 cookie 总数 < 10 → 不完整）
   - 关键项命中阈值（如必需项命中 < 3 → 不完整）

3. **调用前预检 + 调用后二次检查【强制】**：预检通过仅代表状态数量足够，但调用过程中可能因状态实际失效（如 token 过期）被重定向，需再次确认：

   ```python
   # 调用前预检
   issue = await self._check_detail_cookie_completeness()
   if issue:
       raise CollectionError(401, issue, item_id=item_id)
   result = await self._operation()
   if result is None:
       # 调用后二次检查
       issue = await self._check_detail_cookie_completeness()
       if issue:
           raise CollectionError(401, issue, item_id=item_id)
       # 走 reason 映射
   ```

4. **错误信息含具体缺失清单【强制】**：错误信息必须包含具体的缺失情况（总数、命中项、未命中项），便于用户排查。

**配置驱动**：状态完整性判断的阈值、关键项清单、双阈值关系等参数在 `config.yaml` 的 `data_completeness_precheck` 节点管理，包含 `min_total_count` / `required_items` / `min_required_hits` / `threshold_relation`（"and"/"or"）等，不硬编码在技能中。

**适用场景**：
- 依赖多字段外部状态的接口（cookie/header/token）
- 用户手动注入数据的场景（DevTools 复制 / 文件导入）
- 浏览器自动化（详情页 SPA 渲染依赖完整 cookie 集）
- 状态可能在中途失效的场景（token TTL 过期）

**不适用场景**：
- 主键精确查询（天然幂等）
- 纯查询接口（无外部状态依赖）
- 内部信任数据（无完整性风险）

**历史教训**：用户从浏览器 DevTools 复制 cookie 时只粘贴 4 个身份 cookie，`export_cookies` 覆盖写丢失原有 22 个完整 cookie 集，详情页 SPA 渲染失败。预检可在调用前识别"4 个 cookie 不足 10 个阈值"，直接抛 401 + 缺失清单，而非走 detail() → None → 502 含糊错误。

**判断信号（review 触发条件）**：
- 接口依赖外部状态（cookie/token/header）但无前置完整性检查
- 检查方法返回布尔值而非错误信息（无法告诉用户缺什么）
- 单阈值判断（仅检查总数或仅检查关键项）
- 调用前预检但无调用后二次检查


---

### step 126：文案常量集中管理规范（error message constant centralization）【强制】🆕v4.27

**背景**：错误文案散落在多个文件中（业务模块抛错、中间件日志降级 marker、前端错误映射），文案变更时需同步多处，漏改会导致日志降级失效或前端显示旧文案。

**问题**：`exception_handler.py` 用字符串 `"Failed to collect item detail"` 作为日志降级 marker，业务模块修改文案后 marker 失效，日志降级不再触发。

**规范**：

1. **文案常量集中定义【强制】**：错误文案必须集中定义为模块级常量，禁止在多处内联字符串字面量：

   ```python
   # collection_service.py 模块级
   _DETAIL_COOKIE_INCOMPLETE_MSG = "闲鱼登录 Cookie 不完整，请重新登录或导入完整 Cookie"
   _DETAIL_LOGIN_EXPIRED_MSG = "采集失败：登录态失效或 _m_h5_tk token 过期，请重新登录"
   _DETAIL_VERIFY_REQUIRED_MSG = "采集失败：触发闲鱼反爬验证码，请手动完成验证后重试"
   _DETAIL_PAGE_CLOSED_MSG = "采集失败：浏览器页面被并发清理关闭，请稍后重试"
   _DETAIL_UNKNOWN_FAILURE_MSG = "采集失败：详情页不可用或网络异常（reason={reason}），请稍后重试"
   ```

2. **跨模块引用必须 import 常量【强制】**：其他模块（如 exception_handler）引用文案做日志降级 marker 时，必须 import 常量而非硬编码字符串：

   ```python
   # exception_handler.py
   from xianyu_hunter.modules.collection_service import _DETAIL_COOKIE_INCOMPLETE_MSG
   _COOKIE_EXPIRED_MARKER = _DETAIL_COOKIE_INCOMPLETE_MSG  # 引用而非复制
   ```

3. **禁止用字符串子串做 marker【强制】**：日志降级判断禁止用 `if "Failed to collect" in detail`，必须用 `if detail == _DETAIL_COOKIE_INCOMPLETE_MSG` 或更精确的标识符（如 error_code 字段）。

4. **错误响应增加 error_code 字段【建议】**：复杂错误响应应增加 `error_code` 字段（如 `"DETAIL_COOKIE_INCOMPLETE"`），前端按 error_code 而非文案字符串做映射，文案变更不影响前端逻辑。

**配置驱动**：文案常量名、error_code 枚举、日志降级 marker 规则等参数在 `config.yaml` 的 `error_message_centralization` 节点管理，包含 `constant_naming_pattern` / `error_code_enum` / `forbidden_string_marker` / `require_constant_import` 等，不硬编码在技能中。

**适用场景**：
- 错误文案被多个模块引用（业务模块 + 中间件 + 前端）
- 日志降级基于文案内容判断
- 前端按错误文案做场景化提示
- 错误响应需国际化的场景

**不适用场景**：
- 单次使用的临时错误信息
- 内部调试日志（developer-facing）
- 堆栈跟踪（系统生成）

**历史教训**：`exception_handler.py` 用 `_COOKIE_EXPIRED_DETAIL_MARKER = "Failed to collect item detail"` 作为日志降级 marker，业务模块修改文案后 marker 失效，502 错误日志从 INFO 降级退回 WARNING，日志刷屏。修复后业务模块文案集中为模块级常量，exception_handler import 引用而非硬编码。

**判断信号（review 触发条件）**：
- `grep "Failed to collect"` 等字符串字面量出现在多个文件
- 日志降级判断用 `if "<substring>" in detail` 而非常量比较
- 业务模块抛错文案与中间件 marker 字符串不一致
- 前端按文案子串做场景化映射而非 error_code


---

### step 127：修改-验证-部署闭环规范（edit-verify-deploy closed loop）【强制】🆕v4.27

**背景**：Python 代码修改后未重启服务导致用户报"还是报错"，且修改被回退后未及时发现，浪费多轮对话。

**问题**：修改 `collection_service.py` 后未重启 uvicorn 进程，服务仍跑旧代码；git stash 管理失控导致修改丢失，未及时用 grep 验证关键标志符存在。

**规范**：

1. **修改后立即 grep 验证【强制】**：Edit 工具修改文件后，必须立即用 Grep 验证关键标志符（如新方法名、新常量名）存在于文件中：

   ```bash
   # 修改后立即验证
   grep "_check_detail_cookie_completeness" src/xianyu_hunter/modules/collection_service.py
   grep "merge_cookies" src/xianyu_hunter/web/services/cookie_store.py
   ```

2. **全局 grep 旧文案确保唯一来源【强制】**：修改错误文案后，必须全局 grep 旧文案，确保只有新文案存在：

   ```bash
   grep -r "Failed to collect item detail" src/  # 应无结果
   grep -r "采集失败：详情页不可用" src/  # 应有结果
   ```

3. **Python 修改后必须重启服务【强制】**：Python 代码修改后必须重启 uvicorn 进程使代码生效，禁止认为"修改即生效"：

   ```powershell
   # PowerShell 重启服务
   taskkill /F /T /PID <old_pid>
   .venv\Scripts\python.exe -m xianyu_hunter web
   ```

4. **重启后验证端口 + 数据状态【强制】**：重启后必须验证端口监听 + 关键数据状态（如 cookies 数量）：

   ```powershell
   # 验证端口
   Test-NetConnection -ComputerName 127.0.0.1 -Port 8000
   # 验证数据状态
   $c = Get-Content data/cookies_default.json -Raw | ConvertFrom-Json
   Write-Host "cookies count: $($c.cookies.Count)"  # 应 ≥ 10
   ```

5. **git stash 前先 commit 保底【强制】**：修改前先 `git add . && git commit -m "WIP"` 保底，避免 stash 混合导致修改丢失：

   ```bash
   # 修改前保底
   git add . && git commit -m "WIP: before refactor"
   # 然后再做修改
   ```

**配置驱动**：验证步骤清单、grep 标志符、端口验证超时、数据状态阈值等参数在 `config.yaml` 的 `edit_verify_deploy_loop` 节点管理，包含 `verify_grep_markers` / `restart_required` / `port_verify_timeout` / `data_state_thresholds` 等，不硬编码在技能中。

**适用场景**：
- 所有 Python 代码修改（需重启服务）
- 所有错误文案修改（需全局 grep 旧文案）
- 所有 git stash 操作（需先 commit 保底）
- 所有数据状态变更（需验证最终状态）

**不适用场景**：
- 前端 HMR 开发模式（自动热更新）
- 配置热更新场景（无需重启）
- 纯文档修改（无代码生效需求）

**历史教训**：修改 `collection_service.py` 后未重启服务，用户报"还是报错"，排查发现服务进程启动时间早于修改时间。又因 git stash 管理失控，修改被回退后未及时发现，浪费多轮对话。修复后建立"修改-验证-部署闭环"：Edit → Grep 验证 → 重启服务 → 端口验证 → 数据状态验证。

**判断信号（review 触发条件）**：
- Python 代码修改后无 `taskkill` + 重启命令
- 错误文案修改后无全局 grep 旧文案
- git stash 前无 commit 保底
- 重启后无端口验证或数据状态验证


---

### step 144：ATTRIB-01 错误归因精细化原则【强制】🆕v4.29

**背景**：`collector.detail()` 返回 `None` 时，API 一律抛 502 含糊错误（"page unavailable or login expired"），无具体原因，用户无法判断该重登录、该等待还是该手动验证。

**问题**：外部调用返回 None/失败时，未根据失败原因映射到具体 HTTP 状态码，导致所有失败归为同一含糊错误，用户无法采取正确操作。

**规范**：

1. **失败原因映射状态码【强制】**：外部调用返回 None/失败时，必须根据失败原因映射到具体 HTTP 状态码：
   - `401`：登录过期（cookie 失效/登录重定向）
   - `429`：反爬验证（验证码页/触发反爬）
   - `503`：页面不可用（页面被关闭/TargetClosed）
   - `502`：其他未知失败（兜底）

2. **记录 last_failure_reason【强制】**：底层操作必须设置 `last_<operation>_failure_reason` 属性，供中层读取并映射状态码：
   ```python
   # ✅ 正确：底层设置 reason，中层按 reason 映射状态码
   self.last_detail_failure_reason = "login_redirect"
   # 中层
   reason = getattr(self.collector, "last_detail_failure_reason", "")
   if reason in ("home_title_redirect", "login_redirect"):
       raise CollectionError(401, "登录态失效，请重新登录")
   ```

**配置驱动**：`coding_standards.error_attribution.status_mapping`（reason → status_code 字典）在 `config.yaml` 管理。

**适用场景**：
- 外部 API 调用（爬虫采集/第三方接口）
- 多失败模式的业务操作
- 需要用户区分操作的错误场景

**不适用场景**：
- 内部确定性调用（如纯计算函数）
- 单一失败模式的简单操作

**历史教训**：`collector.detail()` 返回 None 时一律抛 502，用户反馈"还是报错"但无法判断是 cookie 失效还是页面下架。修复后按 reason 映射 401/429/502/503。

**判断信号（review 触发条件）**：
- `grep "raise.*Error.*502"` 出现含糊文案（如 "page unavailable" / "login expired"）
- 外部调用返回 None 但未设置 `last_*_failure_reason`


---

### step 145：EXCEPT-01 异常传播原则【强制】🆕v4.29

**背景**：`_detect_detail_is_sold` 在页面关闭时返回 `False`，隐藏上游问题（页面关闭/会话失效），导致已售商品被误判为在售继续推送。

**问题**：页面关闭/会话失效等异常被 try/except 捕获后返回默认值（False/None），隐藏上游问题，导致错误结果被业务逻辑消费。

**规范**：

1. **异常应向上传播【强制】**：页面关闭/会话失效等异常应向上传播，而非返回默认值隐藏问题：
   ```python
   # ✅ 正确：检测 page.is_closed() 后重新抛出
   if page.is_closed():
       raise TargetClosedError("页面已关闭，无法检测商品状态")

   # ❌ 错误：页面关闭时返回 False，隐藏问题
   # try:
   #     text = await page.inner_text(selector)
   # except Exception:
   #     return False  # 隐藏了页面关闭的根本问题
   ```

2. **禁止 try/except 吞掉异常返回 False/None【强制】**：检测类函数禁止用 try/except 吞掉异常返回默认值，必须让异常向上传播由调用方处理。

3. **检测 page.is_closed()【强制】**：浏览器自动化检测函数必须先检测 `page.is_closed()`，若已关闭则抛出 `TargetClosedError` 而非返回默认值。

**配置驱动**：无（原则性规范）。

**适用场景**：
- 异常处理（页面关闭/会话失效/网络中断）
- 爬虫页面检测（已售检测/状态检测/内容提取）
- 任何不应返回默认值隐藏问题的场景

**不适用场景**：
- 已知可忽略的异常（如 `KeyboardInterrupt`）
- 多层兜底链模式（参见 step 78，每层失败进入下一层是设计行为）
- 非关键路径的 fire-and-forget 操作（失败可静默）

**历史教训**：`_detect_detail_is_sold` 在页面关闭时返回 False，已售商品被误判为在售，继续推送导致用户体验问题。修复后检测 `page.is_closed()` 并抛出 `TargetClosedError`。

**判断信号（review 触发条件）**：
- `grep "except.*:.*return False" <file>` 出现吞掉异常返回 False 的模式
- `grep "except.*:.*return None" <file>` 出现吞掉异常返回 None 的模式
- 检测类函数含 try/except 但无 logger 记录


---

### step 146：ERROR-01 错误消息透传原则【强制】🆕v4.29

**背景**：抢单策略"预览失败"时，前端只显示通用"操作失败"，未显示后端返回的具体错误（如"价格超过上限"/"库存不足"），用户无法判断如何调整。

**问题**：HTTPException 返回的 detail 字段未透传到前端，前端 catch 块只显示通用错误消息，用户无法获取具体错误原因。

**规范**：

1. **HTTPException 必须返回具体 detail【强制】**：后端抛出 HTTPException 时必须返回具体的 detail 字段，禁止使用通用错误消息：
   ```python
   # ✅ 正确：返回具体错误原因
   raise HTTPException(422, f"价格 {price} 超过上限 {max_price}")

   # ❌ 错误：返回通用错误消息
   # raise HTTPException(422, "操作失败")
   ```

2. **前端 catch 块必须提取后端具体错误【强制】**：前端 catch 块必须用 `extractApiError` 提取后端返回的具体错误消息，禁止显示通用"操作失败"：
   ```typescript
   // ✅ 正确：提取后端具体错误
   catch (e) {
     message.error(extractApiError(e), 5);
   }

   // ❌ 错误：显示通用错误
   // catch (e) {
   //   message.error('操作失败');
   // }
   ```

3. **禁止显示通用错误消息【强制】**：禁止 `message.error('操作失败')` / `message.error('保存失败')` 等无具体信息的错误提示。

**配置驱动**：无（原则性规范）。

**适用场景**：
- API 错误处理（HTTPException 抛错）
- 前端错误展示（catch 块错误提示）
- 表单提交/配置保存/数据获取等可能失败的操作

**不适用场景**：
- 客户端验证错误（如必填项为空，前端可直接提示）
- 已知预期错误（如取消操作）
- 内部调试日志（developer-facing）

**历史教训**：抢单策略预览失败时前端只显示"操作失败"，用户无法判断是价格超限还是库存不足。修复后前端用 `extractApiError` 提取后端 detail，显示具体原因。

**判断信号（review 触发条件）**：
- `grep "message.error('操作失败\|保存失败\|加载失败')" <frontend_file>` 出现通用错误提示
- HTTPException detail 字段为通用消息（如 "error" / "failed"）


---

### step 147：RETRY-01 重试策略配置化原则【强制】🆕v4.29

**背景**：搜索参数重试策略硬编码 10 次（`MAX_RETRIES = 10`），但 `config.yaml` 的 `search.retry_count = 3`，用户配置被忽略，重试 10 次浪费资源。

**问题**：重试次数/间隔/退避策略硬编码在代码中，与配置文件的对应配置项不一致，用户修改配置无效。

**规范**：

1. **禁止硬编码重试参数【强制】**：禁止硬编码重试次数/间隔/退避策略，必须从配置读取：
   ```python
   # ✅ 正确：从配置读取重试参数
   retry_count = get_config().search.retry_count
   retry_interval = get_config().search.retry_interval
   for attempt in range(retry_count):
       try:
           return await self._search()
       except Exception:
           if attempt >= retry_count - 1:
               raise
           await asyncio.sleep(retry_interval)

   # ❌ 错误：硬编码重试次数
   # MAX_RETRIES = 10  # 应从配置读取
   # for attempt in range(MAX_RETRIES):
   ```

2. **配置项必须完整【强制】**：重试策略配置项必须包含 `retry_count` / `retry_interval` / `retry_backoff` 三项，支持指数退避。

**配置驱动**：`coding_standards.retry.default_count` / `coding_standards.retry.default_interval` / `coding_standards.retry.backoff` 在 `config.yaml` 管理。

**适用场景**：
- 网络请求重试（HTTP 请求/外部 API 调用）
- 外部调用重试（爬虫采集/第三方服务）
- 任何含重试逻辑的业务操作

**不适用场景**：
- 一次性操作（无重试需求）
- 用户主动取消（不应重试）
- 已知不可恢复的错误（如 404 资源不存在）

**历史教训**：搜索重试硬编码 10 次，用户配置 `retry_count=3` 无效，重试 10 次浪费 30 秒。修复后改为从配置读取。

**判断信号（review 触发条件）**：
- `grep "MAX_RETRIES\|max_retries" <file>` 出现硬编码数字
- `grep "for.*range.*retry" <file>` 出现硬编码重试次数
- 配置文件有 retry_count 但代码未读取


---

### step 148：LOG-NOISE-01 已知场景日志降噪原则【强制】🆕v4.29

**背景**：Cookie 过期导致 300+ WARNING 日志（每次定时检查都记录），淹没真实问题，运维难以发现关键错误。

**问题**：Cookie 过期/反爬触发等已知场景在高频定时任务中产生大量 WARNING 日志，淹没真实问题，增加日志存储成本。

**规范**：

1. **已知场景不应产生大量 WARNING【强制】**：Cookie 过期/反爬触发/会话失效等已知场景在高频定时任务中不应产生大量 WARNING：
   ```python
   # ✅ 正确：聚合日志（首次 WARNING，后续 DEBUG）
   if not self._cookie_expired_warned:
       logger.warning("Cookie 已过期，请重新登录")
       self._cookie_expired_warned = True
   else:
       logger.debug("Cookie 仍过期（已警告）")

   # ❌ 错误：每次检查都记录 WARNING
   # logger.warning("Cookie 已过期，请重新登录")  # 300+ WARNING
   ```

2. **降噪策略【强制】**：已知高频错误必须采用以下降噪策略之一：
   - **聚合日志**：首次 WARNING，后续 DEBUG（推荐）
   - **降级为 INFO**：高频已知错误降级为 INFO 级别
   - **增加冷却期**：N 分钟内只记录一次 WARNING

**配置驱动**：`coding_standards.log_noise.suppress_patterns`（需降噪的日志模式列表）在 `config.yaml` 管理。

**适用场景**：
- 高频已知错误（Cookie 过期/反爬触发/会话失效）
- 定时任务日志（每分钟/每秒执行的检查）
- 批量操作日志（批量采集/批量刷新）

**不适用场景**：
- 低频未知错误（不应降噪，需立即暴露）
- 关键路径错误（如启动失败/数据丢失）
- 首次出现的错误（必须 WARNING）

**历史教训**：Cookie 过期导致 300+ WARNING 日志，运维误以为是严重问题，实际只是已知场景重复记录。修复后改为聚合日志（首次 WARNING，后续 DEBUG）。

**判断信号（review 触发条件）**：
- 同一 WARNING 消息在日志中出现 100+ 次
- 定时任务每次执行都记录相同 WARNING
- `grep "logger.warning" <file>` 出现在高频定时任务中


---

### step 180：LOGMERGE-01 降级链日志合并原则【强制】🆕v4.31

**背景**：同一逻辑链的多个中间阶段（降级、重试、回退、多策略尝试）若每个步骤独立输出 WARNING，单次失败会产生多条噪音日志，淹没真正需要关注的告警，增加日志存储与排查成本。对应元规范 meta-rules #32，与 B-REVIEW-158（backend 日志规范维度）对应。前端无降级链日志场景，不新增前端检查点。

**问题**：降级链/重试链/多策略回退链的每个中间步骤（如"尝试刷新 token""尝试 DOM 回退""刷新失败"）均用 `logger.warning` 独立输出，单次失败产生 5+ 条 WARNING，12 小时累积数百条冗余告警，占总 WARNING 80%+，淹没真正需要关注的告警。

**规范**：

1. **中间步骤 DEBUG 化【强制】**：降级/重试链的中间步骤（如"尝试刷新 token""尝试 DOM 回退"）使用 `logger.debug()`，最终结果使用 `logger.warning()` 或 `logger.error()`：
   ```python
   # ✅ 正确：中间步骤 DEBUG，最终结果 1 条结构化 WARNING
   async def search_with_fallback(self, keyword: str):
       stages = []
       # 阶段1：API 搜索
       try:
           result = await self._search_api(keyword)
           return result
       except Exception as e:
           stages.append(f"API_FAILED:{e.__class__.__name__}")

       # 阶段2：尝试强制刷新 _m_h5_tk
       logger.debug("尝试强制刷新 _m_h5_tk")  # 中间步骤 DEBUG
       if not await self._refresh_token():
           stages.append("TOKEN_REFRESH_FAILED")
       else:
           try:
               result = await self._search_api(keyword)
               return result
           except Exception as e:
               stages.append(f"API_RETRY_FAILED:{e.__class__.__name__}")

       # 阶段3：DOM 回退
       logger.debug("尝试 DOM 回退")  # 中间步骤 DEBUG
       try:
           return await self._search_dom(keyword)
       except Exception as e:
           stages.append(f"DOM_TIMEOUT:{e.__class__.__name__}")

       # 最终结果：1 条结构化 WARNING
       logger.warning(
           "搜索降级链全部失败",
           extra={
               "keyword": keyword,
               "stages": stages,                # 各中间步骤简述数组
               "final_reason": stages[-1] if stages else "UNKNOWN",
               "attempts": len(stages),
           },
       )
       raise SearchError(stages)

   # ❌ 错误：每个中间步骤独立 WARNING，单次失败产生 5 条噪音
   # except Exception as e:
   #     logger.warning("API 搜索失败")              # 噪音1
   #     logger.warning("尝试强制刷新 _m_h5_tk")      # 噪音2
   #     logger.warning("_m_h5_tk 刷新失败")          # 噪音3
   #     logger.warning("尝试 DOM 回退")              # 噪音4
   #     logger.warning("DOM 回退超时")               # 噪音5
   #     raise
   ```

2. **结果日志结构化【强制】**：最终结果日志必须含结构化 `extra` 字段：`{stages: [...], final_reason, keyword/context, attempts}`，其中 `stages` 为各中间步骤的简述数组，便于聚合分析。

3. **合并阈值【强制】**：同一逻辑链内 ≥2 个阶段则必须合并（阈值从 config 读取），单阶段无需合并：
   ```python
   min_stages = config["log_merge"]["min_stages_to_merge"]  # 默认 2
   if len(stages) >= min_stages:
       logger.warning("...", extra={"stages": stages, ...})
   ```

4. **配置驱动【强制】**：合并阈值、中间步骤 DEBUG 开关、保留的中间步骤白名单均从 config 读取，禁止硬编码。

**配置驱动**：
- `coding_standards.log_merge.min_stages_to_merge`：合并阈值，默认 `2`，同一逻辑链阶段数 ≥ 该值则必须合并
- `coding_standards.log_merge.intermediate_debug_enabled`：中间步骤 DEBUG 化开关（`true`/`false`，默认 `true`）

均在 `config.yaml` 管理。

**适用场景**：
- 降级链（API → DOM → 缓存）
- 重试链（指数退避多轮）
- 多策略回退（多 selector 候选）
- 浏览器自动化多策略尝试
- 批处理多阶段校验

**不适用场景**：
- 独立的一次性告警（不同业务流程）
- 用户操作触发的即时反馈
- 关键路径异常的 `logger.exception()`（需完整堆栈）
- 不同函数/模块的告警

**历史教训**：搜索 API 会话失效时，`_search.py` 在同一次搜索失败中输出 5 条 WARNING（FAIL_SYS_ILLEGAL_ACCESS → 尝试强制刷新 _m_h5_tk → 刷新失败 → 尝试 DOM 回退 → DOM 回退超时），单次搜索失效产生 5 条噪音日志，12 小时内累积 555 条冗余 WARNING（占总 WARNING 88%），淹没真正需要关注的告警。修复：中间步骤降为 DEBUG，最终合并为 1 条结构化 WARNING（含 `stages` / `final_reason` / `keyword`），告警量从 628 降至 ~80，可观测性显著提升。

**判断信号（review 触发条件）**：
- 同一函数内 ≥3 个 `logger.warning` 且属于同一 try/降级链 → 视为违规（应合并为 1 条）
- `grep "logger.warning.*尝试\|logger.warning.*刷新\|logger.warning.*回退\|logger.warning.*重试" <file>` 多条且无结构化合并 → 视为冗余告警
- 降级链结果日志 `grep "logger.warning"` 缺 `extra=` 参数 → 视为不规范
- 合并阈值/min_stages 硬编码为字面量数字而非 config 引用 → 视为硬编码


---

### step 200：HTTP-STATUS-CODE-MAPPING HTTP 状态码精细化映射表【强制】🆕v4.38

**背景**：本轮对话修复的 8 类问题之一——HTTP 状态码使用语义模糊，如 504 网关超时与 502 网关错误混用、401 未登录与 403 权限不足混用，导致前端无法按状态码分类处理，用户看到不相关的错误提示。

**问题**：HTTP 状态码是前后端错误处理的契约，但项目中对状态码的使用缺乏统一映射表，开发者凭直觉选择状态码，造成：① 同类错误在不同接口返回不同状态码（如登录失效有时 401 有时 403）；② 前端无法按状态码分类重试/提示/跳转；③ 状态码语义与错误根因不匹配（如 RGV587 反爬映射为 401 登录失效，但实际是临时 token 过期）。

**规范**：

1. **HTTP 状态码必须有统一映射表【强制】**：项目必须维护统一的 HTTP 状态码映射表（位于 `config/http_status_code_mapping.yaml`），每个状态码对应明确的业务语义、重试策略、用户提示：
   ```yaml
   # config/http_status_code_mapping.yaml
   status_codes:
     400:
       semantic: "请求参数错误"
       retry: false
       user_message: "请求参数有误，请检查后重试"
     401:
       semantic: "未登录或登录失效"
       retry: false
       user_message: "请重新登录"
       action: "redirect_login"
     403:
       semantic: "权限不足"
       retry: false
       user_message: "无权限执行此操作"
     404:
       semantic: "资源不存在"
       retry: false
       user_message: "资源不存在或已删除"
     422:
       semantic: "业务校验失败"
       retry: false
       user_message: "{detail}"  # 透传后端 detail
     502:
       semantic: "网关错误（服务异常）"
       retry: true
       user_message: "服务异常，请稍后重试"
       action: "restart_service"
     503:
       semantic: "服务不可用（限流/维护）"
       retry: true
       user_message: "服务繁忙，请稍后重试"
     504:
       semantic: "网关超时"
       retry: true
       user_message: "请求超时，请稍后重试"
       action: "check_network"
   ```

2. **状态码语义必须与根因匹配【强制】**：状态码的选择必须基于错误根因，禁止将特定错误码映射为不相关的状态码：
   - RGV587 反爬 → 503（临时限流，非登录失效，不应映射为 401）
   - `_m_h5_tk` token 过期 → 503（临时 token 过期，稍后重试可成功）
   - 浏览器 Cookie 失效 → 401（真正的登录失效）
   - 权限不足 → 403（已登录但无权限）

3. **前端按状态码分类处理【强制】**：前端必须按状态码分类处理（重试 / 跳转登录 / 提示 / 静默），禁止统一显示"操作失败"：
   ```typescript
   // ✅ 正确：按状态码分类处理
   catch (err: AxiosError) {
     const status = err.response?.status;
     if (status === 401) {
       redirectToLogin();
     } else if (status === 503 || status === 504) {
       showRetryToast();
     } else if (status === 422) {
       showDetailMessage(err.response.data.detail);
     } else {
       showGenericError();
     }
   }
   ```

4. **状态码变更必须 review【强制】**：新增或修改状态码映射必须经过 review，确认与现有映射表一致，禁止随意新增状态码。

**配置驱动**：`http_status_code_mapping` 节点管理映射表，包含 `mapping_config_path`（默认 `"config/http_status_code_mapping.yaml"`）、`require_consistency_check`（默认 `true`）、`frontend_classification_required`（默认 `true`）、`review_required_for_change`（默认 `true`）、`forbidden_mappings`（禁止的映射对，如 `[{"error": "RGV587", "forbidden_status": [401]}]`）在 `config.yaml` 管理，不硬编码。

**适用场景**：
- 所有 FastAPI 路由的 HTTPException 状态码选择
- 前端 axios/fetch 的错误分类处理
- SSE/WebSocket 的错误事件状态码
- API 响应的 error_code 字段映射

**不适用场景**：
- 内部 Service 层的异常（不直接暴露 HTTP 状态码）
- 健康检查端点（/healthz 用 200/503 即可）
- Webhook 回调（按第三方 API 的状态码规范）

**历史教训**：项目早期 RGV587 反爬错误映射为 HTTP 401（"闲鱼登录已过期"），但 RGV587 实际是 mtop API 的 `_m_h5_tk` 临时 token 过期（TTL 1 小时），多查几次能成功——说明不是登录态失效。前端显示"Cookie 失效或会话过期"，用户被误导去重新登录，但重新登录后仍可能触发 RGV587。修复后改为 503（"搜索令牌临时过期，请稍后重试"），前端按 503 自动重试，用户体验显著改善。

**判断信号（review 触发条件）**：
- `grep "HTTPException" <file>` 命中但状态码不在映射表中
- 同类错误在不同接口返回不同状态码
- 前端 catch 块无 `if (status === xxx)` 分类处理
- 状态码语义与错误根因不匹配（如临时错误映射为 4xx）


---

### step 202：EXCEPTION-LOG-SEMANTIC 异常日志语义保留规范【强制】🆕v4.38

**背景**：本轮对话修复的 8 类问题之一——异常日志用 `logger.warning(f"失败: {e}")` 丢失完整堆栈，排查时无法定位真正失败点；且日志消息不含业务上下文（如 item_id / user_id），无法关联具体请求。

**问题**：异常日志是排查问题的关键证据，但项目中常见两种退化：① `logger.warning(f"失败: {e}")` 只保留一行 message，丢失 traceback；② 日志消息不含业务上下文（如 item_id / user_id / task_id），无法关联是哪个请求失败。这两种退化导致问题排查时间从分钟级延长到小时级。

**规范**：

1. **关键路径必须用 logger.exception()【强制】**：关键路径（启动钩子 / 迁移函数 / 初始化函数 / 核心业务流程）的 except 块必须用 `logger.exception()` 输出完整 traceback，禁止用 `logger.warning(f"...{e}")` 丢失堆栈：
   ```python
   # ✅ 正确：logger.exception 保留完整堆栈
   try:
       container = get_container()
       run_migrations(container)
   except Exception:
       logger.exception("启动迁移钩子失败（不阻断主服务）")

   # ❌ 错误：logger.warning 丢失堆栈
   # try:
   #     run_migrations(container)
   # except Exception as e:
   #     logger.warning(f"启动迁移钩子失败: {e}")  # 只有一行 message
   ```

2. **日志必须含业务上下文【强制】**：异常日志必须包含业务上下文（item_id / user_id / task_id / request_id），便于关联具体请求：
   ```python
   # ✅ 正确：含业务上下文
   logger.exception(
       "采集详情失败 item_id=%s user_id=%s",
       item_id, user_id
   )

   # ❌ 错误：无业务上下文
   # logger.exception("采集失败")  # 无法定位是哪个商品
   ```

3. **非关键路径可用 logger.warning 但必须含异常类型【强制】**：非关键路径（如辅助功能、fire-and-forget 操作）的 except 块可用 `logger.warning`，但必须含异常类型与 message：
   ```python
   # ✅ 正确：非关键路径 warning + 异常类型
   except Exception as e:
       logger.warning("Cookie 同步失败（不影响主流程）: %s: %s", type(e).__name__, e)
   ```

4. **禁止吞掉异常【强制】**：禁止 `except: pass` 或 `except Exception: pass` 静默吞掉异常，至少必须记录日志。与 step 116「数据库迁移块独立容错与关键路径异常可见性规范」配合。

5. **敏感信息脱敏【强制】**：异常日志中不得包含敏感信息（token / password / cookie），必须用脱敏工具函数处理。与 step 7「安全调用检查」配合。

**配置驱动**：`exception_log_semantic` 节点管理日志语义要求，包含 `critical_path_use_exception`（默认 `true`）、`require_business_context`（默认 `true`）、`context_fields`（默认 `["item_id", "user_id", "task_id", "request_id"]`）、`non_critical_min_log_level`（默认 `"warning"`）、`forbidden_patterns`（默认 `["except: pass", "except Exception: pass", "logger.warning(f\"...{e}\")"]`）、`sensitive_fields_to_redact`（默认 `["token", "password", "cookie", "authorization"]`）在 `config.yaml` 管理，不硬编码。

**适用场景**：
- 所有关键路径的异常处理（启动钩子 / 迁移函数 / 初始化函数 / 核心业务流程）
- 所有需要排查问题的异常日志（含业务上下文）
- 多用户系统的异常日志（含 user_id 便于关联）

**不适用场景**：
- 预期异常（如 `KeyError` 用于判断字段存在，无需记录堆栈）
- 测试代码中的异常断言（`pytest.raises`）
- 静默降级场景（已知场景的 fire-and-forget，可用 warning）

**历史教训**：`startup.py` 的 `run_migrations()` 外层 `except Exception as e: logger.warning(f"启动迁移钩子失败（忽略）: {e}")` 吞掉异常，C-01 步骤的 `auto_migrate_task_links()` 因 `task_links` 表结构问题抛异常，但日志只有一行 message 无堆栈，排查 2 小时才定位到是 C-01 失败导致 C-04 被跳过。修复后改为 `logger.exception("启动迁移钩子失败（不阻断主服务）")`，完整堆栈帮助 5 分钟定位问题。

**判断信号（review 触发条件）**：
- `grep "logger.warning.*{e}" <file>` 命中关键路径函数
- `grep "except.*pass" <file>` 命中吞掉异常的代码
- 异常日志无 item_id / user_id / task_id 等业务上下文字段
- `grep "logger.exception" <file>` 在关键路径函数中未命中


---



### step 231：诊断日志模式规范【强制】🆕v4.47

**背景**：3 次关联会话排查耗时数小时，根因是自愈链路、重试逻辑、状态翻转等关键路径只打 `logger.warning`，不打 cookie 数量、层状态、刷新结果、注入结果等关键状态变量。缺乏结构化诊断日志导致"哪一级失败"无法快速定位，需要二次复现才能拿到上下文。

**问题**：关键路径（自愈链路 / 重试逻辑 / 状态翻转 / 熔断标志）的日志只有 message，无业务上下文（cookie 数量、层状态、刷新结果、注入结果、item_id、task_id），排查时无法从日志回溯失败现场。

**规范**：

1. **结构化诊断日志【强制】**：自愈链路 / 重试逻辑 / 状态翻转 / 熔断标志等关键路径必须调用 `_log_cookie_diagnostics(tag, context)` 集中记录，**禁止**仅 `logger.warning(message)`：
   - **tag**：固定标识（如 `token_refresh_failed` / `cookie_inject_failed` / `state_flip_invalid_to_valid`），便于 grep
   - **context**：dict 形式，至少含 `item_id` / `task_id` / `cookie_count` / `layer_states` / `refresh_result` / `inject_result`（按场景选择）

2. **诊断日志在每级失败时调用【强制】**：自愈链路每级失败、重试每次尝试、状态每次翻转、熔断标志每次置位/复位，都必须调用诊断日志函数

3. **诊断日志配置化【强制】**：诊断日志函数名、tag 清单、context 字段清单，全部从 `config.yaml` 读取，**禁止**硬编码在代码中

**判断信号**：
- `grep "logger.warning\|logger.error" src/` 命中关键路径函数，但同函数无 `_log_cookie_diagnostics` 调用 → 视为违规
- `grep "def _refresh_token_and_retry\|def _heal\|def _retry" src/` 找到自愈/重试函数 → 检查每级失败是否调用诊断日志
- 日志只有 message，无 item_id / cookie_count / layer_states 等结构化字段 → 视为违规

**修复模式**：
```python
# ✅ 关键路径调用诊断日志，含结构化上下文
async def _refresh_token_and_retry_detail(self, item_id: str, ...):
    refresh_ok = await self.token_renewer.refresh()
    if not refresh_ok:
        self._log_cookie_diagnostics(
            "token_refresh_failed",
            {
                "item_id": item_id,
                "cookie_count": len(self.cookie_store.as_dict()),
                "layer_states": self.cookie_store.get_layer_states(),
                "refresh_result": False,
            },
        )
        self.last_session_invalid = True
        return None

    inject_ok = await inject_cookie_store_to_worker_browser(self.browser, self.cookie_store)
    if not inject_ok:
        self._log_cookie_diagnostics(
            "cookie_inject_failed",
            {
                "item_id": item_id,
                "cookie_count": len(self.cookie_store.as_dict()),
                "refresh_result": True,
                "inject_result": False,
            },
        )
        self.last_session_invalid = True
        return None

# ❌ 反模式：关键路径只打 warning，无结构化上下文
async def _refresh_token_and_retry_detail(self, item_id: str, ...):
    refresh_ok = await self.token_renewer.refresh()
    if not refresh_ok:
        logger.warning("token 刷新失败")  # 排查时无法知道 cookie 数量、层状态
        return None
```

**配置参数**：`diagnostic_log_pattern.enabled`（默认 `true`，是否启用诊断日志）、`diagnostic_log_pattern.function_name`（默认 `_log_cookie_diagnostics`，诊断日志函数名）、`diagnostic_log_pattern.trigger_paths`（默认 `['self_heal', 'retry', 'state_flip', 'circuit_flag']`，触发路径清单）、`diagnostic_log_pattern.tags`（tag 清单，含 `token_refresh_failed` / `cookie_inject_failed` / `state_flip_invalid_to_valid` / `state_flip_valid_to_invalid` / `circuit_flag_set` / `circuit_flag_reset`）、`diagnostic_log_pattern.context_fields`（默认 `['item_id', 'task_id', 'cookie_count', 'layer_states', 'refresh_result', 'inject_result']`，按场景选择必填字段）、`diagnostic_log_pattern.log_level`（默认 `warning`，诊断日志级别）在 `config.yaml` 的 `diagnostic_log_pattern` 节点管理

**适用场景**：自愈链路（多级降级）、重试逻辑（含熔断标志检查）、状态翻转（invalid↔valid）、熔断标志置位/复位、任何"失败后需要回溯现场"的关键路径

**不适用场景**：高频路径（每秒数百次调用的热路径，需用采样）、纯参数校验（用 422 即可）、UI 渲染日志、调试阶段临时日志（用 logger.debug）

**历史教训**：3 次关联会话排查中，`_refresh_token_and_retry_detail` 失败时只打 `logger.warning("token 刷新失败")`，无 cookie 数量、层状态、item_id 等上下文。需要二次复现才能拿到失败现场，排查耗时从 5 分钟延长到 2 小时。引入 `_log_cookie_diagnostics(tag, context)` 后，单条日志即可回溯失败现场，定位时间从 2 小时缩短到 5 分钟。详细复盘参见 [cookie-state-recovery-patterns.md](../../../references/cookie-state-recovery-patterns.md) v3 流程 I。


---

### step 245：日志占位符格式规范【强制】🆕v4.51

**规范编号**：LOGURU-PLACEHOLDER-01
**对应元规范**：meta-rule #84 Cookie-Token 状态分离与一致性保障

**背景**：项目使用 loguru 作为日志库，但部分代码沿用了标准库 logging 的 `%s` 占位符风格。loguru 的 `{}` 占位符与 logging 的 `%s` 占位符不兼容——loguru 不会对 `%s` 做格式化，导致日志输出原始 `%s` 字面量而非实际值。

**问题**：loguru 与 logging 的占位符风格混用，导致日志输出 `%s` 字面量而非实际变量值，排查时无法从日志获取关键信息（如 Cookie 名称列表），延长定位时间。

**规范**：

1. **loguru 统一用 `{}` 占位符【强制】**：所有使用 loguru 的日志调用必须用 `{}` 占位符，**禁止**用 `%s` / `%d` / `%f`（标准库 logging 风格）：
   ```python
   # ✅ 正确：loguru {} 占位符
   logger.info("已同步 MTOP Set-Cookie 到浏览器上下文: {}", sorted(cookie_names))
   logger.warning("token 续期后回写 CookieStore 失败: {}", e)

   # ❌ 错误：标准库 logging %s 占位符（loguru 不格式化）
   # logger.info("已同步 MTOP Set-Cookie 到浏览器上下文: %s", sorted(cookie_names))
   # → 日志输出："已同步 MTOP Set-Cookie 到浏览器上下文: %s"
   ```

2. **f-string 与 {} 占位符的选择【推荐】**：
   - 简单拼接：用 f-string（`f"已重置 {field_name}"`）
   - 含方法调用的拼接：用 `{}` 占位符（避免 f-string 中执行方法调用）
   - 含异常对象的日志：用 `{}` 占位符（`logger.warning("失败: {}", e)`），**禁止**用 f-string（`f"失败: {e}"` 会在格式化时调用 `str(e)`，可能抛二次异常）

3. **配置化【强制】**：日志库类型、占位符风格、禁止的占位符列表，全部从 `config.yaml` 读取

**判断信号**：
- `grep "logger\.\(info\|warning\|error\|debug\).*%s" src/` 命中 → loguru 日志用了 `%s` 占位符
- `grep "logger\.\(info\|warning\|error\|debug\).*%[df]" src/` 命中 → loguru 日志用了 `%d` / `%f` 占位符
- 日志输出含 `%s` 字面量而非实际值 → 占位符风格错误

**修复模式**：
```python
# ✅ loguru {} 占位符
logger.info("已同步 MTOP Set-Cookie 到浏览器上下文: {}", sorted({c["name"] for c in cookies}))

# ❌ 标准库 %s 占位符（loguru 不格式化，输出字面量 %s）
# logger.info("已同步 MTOP Set-Cookie 到浏览器上下文: %s", sorted({c["name"] for c in cookies}))
```

**配置参数**：`loguru_placeholder_format.enabled`（默认 `true`）、`loguru_placeholder_format.logger_library`（默认 `loguru`，日志库类型）、`loguru_placeholder_format.correct_placeholder`（默认 `{}`，正确占位符）、`loguru_placeholder_format.forbidden_placeholders`（默认 `['%s', '%d', '%f', '%r']`，禁止的占位符列表）、`loguru_placeholder_format.exceptions_use_brace_not_fstring`（默认 `true`，异常对象日志是否强制用 `{}` 而非 f-string）在 `config.yaml` 的 `loguru_placeholder_format` 节点管理

**适用场景**：所有使用 loguru 的 Python 项目、从标准库 logging 迁移到 loguru 的项目

**不适用场景**：使用标准库 logging 的项目（应用 `%s`）、使用 structlog 等其他日志库的项目（按库规范）

**历史教训**：`_search.py` 的 `_sync_response_cookies_to_context` 中日志用 `logger.info("已同步 MTOP Set-Cookie 到浏览器上下文: %s", sorted(...))`，loguru 不格式化 `%s`，日志输出 `"已同步 MTOP Set-Cookie 到浏览器上下文: %s"` 而非实际 Cookie 名称列表。用户在错误日志中直接看到 `%s` 字面量，无法确认哪些 Cookie 被同步。改为 `{}` 后解决。


---

### step 246：静默异常禁止规范【强制】🆕v4.51

**规范编号**：SILENT-EXCEPTION-BAN-01
**对应元规范**：meta-rule #84 Cookie-Token 状态分离与一致性保障

**背景**：项目中存在大量 `except Exception: pass` 或 `except Exception as e: pass` 静默吞掉异常的代码，导致关键路径失败时无任何日志输出，排查时完全无线索。与 step 202 的"禁止吞掉异常"规则互补——step 202 聚焦"异常日志必须有堆栈和上下文"，本规则聚焦"异常处理不能完全静默"。

**问题**：静默异常（`except: pass`）是排查问题的最大障碍——失败发生时无日志、无堆栈、无上下文，开发者完全不知道异常发生过，问题持续累积直到引发更严重的连锁故障。

**规范**：

1. **禁止完全静默的 except 块【强制】**：所有 `except` 块**禁止**完全静默（`pass` / `...` / 空操作），至少必须记录日志：
   ```python
   # ✅ 正确：至少记录 warning
   try:
       await container.browser._context.add_cookies(pw_cookies)
   except Exception as e:
       logger.warning("实时搜索：从 JSON 补注入 cookie 失败: {}", e)

   # ❌ 错误：静默吞掉异常
   # try:
   #     await container.browser._context.add_cookies(pw_cookies)
   # except Exception:
   #     pass  # 完全无日志，排查时不知道是否失败
   ```

2. **关键路径必须用 logger.exception()【强制】**：关键路径（启动钩子 / 迁移函数 / 初始化函数 / 核心业务流程）的 except 块必须用 `logger.exception()` 输出完整 traceback，与 step 202 配合：
   - 启动钩子（`_on_startup`）外层 except
   - 迁移函数（`run_migrations`）外层 except
   - 初始化函数（`_init_*`）外层 except
   - 核心业务流程（登录 / 采集 / 搜索）外层 except

3. **辅助路径至少用 logger.warning()【强制】**：非关键路径（辅助功能 / fire-and-forget / 资源清理）的 except 块至少用 `logger.warning()`，**禁止**用 `logger.debug()` 静默降级：
   - 资源清理（`finally` 块中的 `close()` / `cleanup()`）失败 → `logger.warning()`
   - 辅助功能（缓存更新 / 状态同步）失败 → `logger.warning()`
   - fire-and-forget 操作（通知发送 / 指标上报）失败 → `logger.warning()`

4. **预期异常可用 logger.debug()【推荐】**：预期异常（如 `KeyError` 判断字段存在 / `FileNotFoundError` 判断文件存在）可用 `logger.debug()`，但**禁止**完全静默：
   ```python
   # ✅ 预期异常用 debug
   try:
       value = config["optional_field"]
   except KeyError:
       logger.debug("配置项 optional_field 未设置，使用默认值")
       value = DEFAULT_VALUE
   ```

5. **配置化【强制】**：关键路径函数名模式、禁止的静默模式、最低日志级别，全部从 `config.yaml` 读取

**判断信号**：
- `grep "except.*:\s*$" src/` 下一行为 `pass` / `...` → 静默异常
- `grep "except.*pass" src/` 直接命中 → 静默异常
- `grep "except.*:" src/ -A 1` 下一行无 `logger` 调用 → 静默异常
- 关键路径函数的 except 块用 `logger.warning(f"...{e}")` 而非 `logger.exception()` → 与 step 202 配合检查

**修复模式**：
```python
# ✅ 关键路径：logger.exception()
async def _on_startup(self):
    try:
        await self._init_db()
        await self._init_session_manager()
    except Exception:
        logger.exception("启动初始化失败（不阻断主服务）")

# ✅ 辅助路径：logger.warning()
try:
    get_cookie_store().export_cookies(cookies, method="renew")
except Exception as e:
    logger.warning("token 续期后回写 CookieStore 失败: {}", e)

# ❌ 静默异常
# try:
#     get_cookie_store().export_cookies(cookies, method="renew")
# except Exception:
#     pass  # 排查时完全不知道回写是否失败
```

**配置参数**：`silent_exception_ban.enabled`（默认 `true`）、`silent_exception_ban.critical_path_patterns`（默认 `['_on_startup', 'run_migrations', '_init_', '_shutdown', '_on_close']`，关键路径函数名模式列表）、`silent_exception_ban.critical_path_min_level`（默认 `exception`，关键路径最低日志级别）、`silent_exception_ban.auxiliary_path_min_level`（默认 `warning`，辅助路径最低日志级别）、`silent_exception_ban.forbidden_patterns`（默认 `['except.*:\\s*pass', 'except.*:\\s*\\.\\.\\.', 'except.*:\\s*$']`，禁止的静默模式正则列表）、`silent_exception_ban.exceptions_allowed_debug`（默认 `['KeyError', 'FileNotFoundError', 'AttributeError']`，允许用 debug 的预期异常类型）在 `config.yaml` 的 `silent_exception_ban` 节点管理

**适用场景**：所有生产代码的异常处理、关键路径（启动 / 迁移 / 初始化）、辅助路径（资源清理 / fire-and-forget）

**不适用场景**：测试代码中的异常断言（`pytest.raises`）、上下文管理器 `__exit__` 中的异常抑制（需按协议处理）、预期异常用于控制流（如 `StopIteration`）

**历史教训**：`_default_renew_callback` 中回写 CookieStore 的 `try/except` 块原本是 `except Exception: pass`，导致续期后回写失败时完全无日志。排查 `FAIL_SYS_ILLEGAL_ACCESS` 时无法确认回写是否执行过，延长定位时间。改为 `logger.warning("token 续期后回写 CookieStore 失败: {}", e)` 后，日志清晰记录了回写失败事件。与 step 202（异常日志语义保留）互补：step 202 聚焦"日志必须有堆栈和上下文"，本规则聚焦"异常处理不能完全静默"。

### step 248：TIMEOUT-ERROR-SEMANTICS-01 超时异常用户友好语义规范【强制】🆕v4.52.0

**背景**：抢单流程 `buyer.py` 添加 `asyncio.wait_for(timeout=90.0)` 后，超时异常被通用 `except Exception` 分支捕获，用户看到"未知异常"而非"超时"，无法判断是闲鱼页面加载异常还是会话失效，导致错误操作。

**问题**：`asyncio.TimeoutError` 被通用 `except Exception` 分支捕获时，错误信息笼统为"未知异常"或直接展示异常类名，用户无法区分"超时"与"其他异常"，无法采取正确的应对措施（超时需检查登录状态，其他异常需查看日志）。

**规范**：

1. **TimeoutError 必须有专门异常分支【强制】**：`asyncio.wait_for` 包裹的代码块，`except asyncio.TimeoutError` 必须在 `except Exception` 之前单独捕获，禁止让超时异常走通用分支：
   ```python
   # ✅ 正确：TimeoutError 专门分支，用户友好错误信息
   try:
       result = await asyncio.wait_for(self._do_buy(task_id, item_id), timeout=timeout_sec)
   except asyncio.TimeoutError:
       # 超时专用错误信息：含超时秒数 + 可能原因 + 建议操作
       msg = f"浏览器自动化流程超时（{timeout_sec}秒），请检查闲鱼登录状态后重试"
       logger.warning(f"[Buyer] 落单超时 task={task_id} item={item_id} timeout={timeout_sec}s")
       self._save_failed_order(task_id, item_id, msg)
       self._publish_buy_failed(task_id, item_id, msg)
       return BuyResult(outcome=BuyOutcome.FAILED, error=msg)
   except Exception as e:  # noqa: BLE001
       # 通用异常：记录详细异常信息
       logger.exception(f"[Buyer] 落单异常 task={task_id} item={item_id}: {e}")
       msg = f"落单失败：{e}"
       self._save_failed_order(task_id, item_id, msg)
       self._publish_buy_failed(task_id, item_id, msg)
       return BuyResult(outcome=BuyOutcome.FAILED, error=msg)
   ```

2. **超时错误信息必须含三要素【强制】**：超时错误信息必须含（1）超时秒数（2）可能原因（3）建议操作，禁止仅写"超时"或"操作超时"：
   - ✅ `"浏览器自动化流程超时（90秒），请检查闲鱼登录状态后重试"`
   - ❌ `"超时"` / `"操作超时"` / `"请求超时"`

3. **超时日志必须含业务标识+超时秒数【强制】**：超时日志必须含 `task_id`/`item_id` 等业务标识 + `timeout=Ns` 超时秒数，便于排查：
   - ✅ `logger.warning(f"[Buyer] 落单超时 task={task_id} item={item_id} timeout={timeout_sec}s")`
   - ❌ `logger.warning("落单超时")`

4. **超时阈值必须从配置读取【强制】**：超时秒数禁止硬编码，必须从 `config.yaml` 读取：
   ```yaml
   timeout_error_semantics:
     buyer_do_buy_timeout_sec: 90
     collector_detail_timeout_sec: 60
     login_flow_timeout_sec: 120
     error_message_template: "{operation}超时（{timeout}秒），{possible_cause}，{suggested_action}"
   ```

5. **超时错误信息模板配置化【强制】**：错误信息文案、可能原因、建议操作全部从配置读取，禁止硬编码中文文案。

**判断信号**：
- `grep "asyncio.wait_for" src/` 找到超时包裹 → 检查是否有 `except asyncio.TimeoutError` 专门分支
- `except asyncio.TimeoutError` 在 `except Exception` 之后 → 不可达死代码，视为违规
- 超时错误信息仅"超时"无秒数/原因/建议 → 视为违规
- 超时日志无业务标识（`task_id`/`item_id`）→ 视为违规
- 超时秒数硬编码（如 `timeout=90`）而非从配置读取 → 视为违规

**反模式**：
```python
# ❌ TimeoutError 走通用分支，用户看到"未知异常"
try:
    result = await asyncio.wait_for(self._do_buy(task_id, item_id), timeout=90.0)
except Exception as e:  # TimeoutError 被这里捕获，e = asyncio.TimeoutError()
    msg = f"未知异常：{e}"  # 用户看到"未知异常：asyncio.exceptions.TimeoutError"
    # 用户不知道是超时还是其他错误，无法判断该重新登录还是重试

# ❌ 超时错误信息无三要素
except asyncio.TimeoutError:
    msg = "超时"  # 用户不知道超时多久、什么原因、该怎么办

# ❌ 超时秒数硬编码
timeout=90.0  # 禁止硬编码，必须从配置读取
```

**配置参数**：`timeout_error_semantics.buyer_do_buy_timeout_sec`（默认 `90`，抢单超时秒数）、`timeout_error_semantics.collector_detail_timeout_sec`（默认 `60`，采集超时秒数）、`timeout_error_semantics.login_flow_timeout_sec`（默认 `120`，登录超时秒数）、`timeout_error_semantics.error_message_template`（默认 `"{operation}超时（{timeout}秒），{possible_cause}，{suggested_action}"`，错误信息模板）、`timeout_error_semantics.operation_names`（默认 `{"buyer_do_buy": "浏览器自动化流程", "collector_detail": "商品采集", "login_flow": "登录流程"}`，操作名称映射）、`timeout_error_semantics.possible_causes`（默认 `{"buyer_do_buy": "闲鱼页面加载异常或会话失效", "collector_detail": "外部资源异常或被反爬拦截"}`，可能原因映射）、`timeout_error_semantics.suggested_actions`（默认 `{"buyer_do_buy": "请检查闲鱼登录状态后重试", "collector_detail": "请稍后重试"}`，建议操作映射）在 `config.yaml` 的 `timeout_error_semantics` 节点管理

**适用场景**：所有面向用户的异步超时场景（抢单/采集/登录/导出）、`asyncio.wait_for` 包裹的代码块、需要用户根据错误信息采取不同操作的场景

**不适用场景**：内部超时重试（不直接面向用户，走 step 50 的 504 状态码）、有 tenacity 重试机制包裹的场景（重试耗尽后才面向用户）、纯计算函数（无 IO 超时风险）

**历史教训**：`buyer.py` 添加 `asyncio.wait_for(timeout=90.0)` 后，`TimeoutError` 被 `except Exception` 捕获，用户看到"未知异常：asyncio.exceptions.TimeoutError"，不知道是超时还是会话失效。添加 `except asyncio.TimeoutError` 专门分支后，用户看到"浏览器自动化流程超时（90秒），请检查闲鱼登录状态后重试"，可直接判断需要重新登录。与 step 50（异步操作整体超时保护）互补：step 50 聚焦"必须加超时保护"，本规则聚焦"超时异常的用户友好语义"。

---
