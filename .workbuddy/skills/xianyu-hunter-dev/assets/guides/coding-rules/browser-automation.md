# Browser Automation 编码规范
> 本文件归档 xianyu-hunter-dev skill 中与「browser automation」主题相关的编码规范。
> 主索引见 [SKILL.md](../../../SKILL.md) 的"step 索引表"，元规范见 [meta-rules.md](../../../references/meta-rules.md)。

---

### step 36：Chrome 136+ 限制适配模式【强制】🆕v4.4

36. **Chrome 136+ 限制适配模式【强制】🆕v4.4**
    - Chrome/Edge 136+ 版本使用 `--remote-debugging-port` 时必须配合 `--user-data-dir` 指向非标准目录
    - **判断信号**：Chrome/Edge 136+ 版本 + 使用 `--remote-debugging-port` 参数 + 浏览器自动化场景
    - **修复模式**：启动命令同时包含 `--remote-debugging-port=9222` + `--user-data-dir=<unique-path>` → 路径不指向默认 `User Data` 目录
    - **配置参数**：`user_data_dir` 路径模板（`browser_data/debug_{timestamp}`）、`debug_port` 在 `config/browser.yaml` 管理
    - **适用**：Chrome/Edge 浏览器自动化、CDP 调试、Playwright `connect_over_cdp`
    - **不适用**：其他浏览器（Firefox/Safari）、旧版 Chrome（< 136）、不使用 remote-debugging 的场景
    - **历史教训**：Chrome 136+ 安全限制要求 `--user-data-dir` 指向非标准目录，否则 `--remote-debugging-port` 不生效；使用独立 `Debug` profile 避免污染用户主 profile


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

### step 80：关键路径计时埋点【强制】🆕v4.13

80. **关键路径计时埋点【强制】🆕v4.13**
    - 关键路径（`page.goto` / `wait_for_selector` / 外部 HTTP / DB 查询）必须用 `time.perf_counter()` 埋点，记录各阶段耗时与总耗时，超阈值（默认 5s）升为 `warning`，埋点不能影响业务逻辑（用 `try/finally` 包裹确保异常时也能记录耗时），**禁止**用 `time.time()`（精度低）或 `datetime.now()`（含时区开销）
    - **判断信号**：代码含 `await page.goto(url)` 但无耗时记录 → 必须用 `time.perf_counter()` 包裹记录耗时；用户反馈"采集慢"但无耗时数据 → 必须在关键路径补埋点
    - **修复模式**：
      ```python
      import time

      # ✅ 关键路径计时埋点
      async def _fetch_detail_with_timing(page, url: str, item_id: str) -> dict:
          t_start = time.perf_counter()
          try:
              # 阶段 1：page.goto
              t_goto_start = time.perf_counter()
              await page.goto(url, wait_until="domcontentloaded", timeout=30000)
              goto_elapsed = (time.perf_counter() - t_goto_start) * 1000
              if goto_elapsed > 5000:
                  logger.warning(f"详情页 {item_id} page.goto 慢: {goto_elapsed:.0f}ms")
              else:
                  logger.debug(f"详情页 {item_id} page.goto: {goto_elapsed:.0f}ms")

              # 阶段 2：wait_for_selector
              t_wait_start = time.perf_counter()
              await page.wait_for_selector(DETAIL_TITLE_MAIN, timeout=10000)
              wait_elapsed = (time.perf_counter() - t_wait_start) * 1000
              if wait_elapsed > 3000:
                  logger.warning(f"详情页 {item_id} wait_for_selector 慢: {wait_elapsed:.0f}ms")

              # 业务逻辑
              ...
          finally:
              total_elapsed = (time.perf_counter() - t_start) * 1000
              if total_elapsed > 30000:
                  logger.warning(f"详情页 {item_id} 总耗时超阈值: {total_elapsed:.0f}ms")
              else:
                  logger.info(f"详情页 {item_id} 总耗时: {total_elapsed:.0f}ms")
      ```
    - **配置参数**：`timing_instrumentation.thresholds_ms`（默认 `{goto: 5000, wait_for_selector: 3000, http_request: 5000, db_query: 2000, total: 30000}`，各阶段超阈值）、`timing_instrumentation.log_level_normal`（默认 `debug`，正常耗时日志级别）、`timing_instrumentation.log_level_slow`（默认 `warning`，超阈值日志级别）、`timing_instrumentation.enabled_scenarios`（默认 `['browser_automation', 'http_request', 'db_query']`，启用埋点的场景）、`timing_instrumentation.timer_function`（默认 `time.perf_counter`，计时函数，禁止用 `time.time`）在 `config.yaml` 的 `timing_instrumentation` 节点管理
    - **适用**：浏览器自动化（page.goto/wait_for_selector/evaluate）、外部 HTTP 请求（httpx/aiohttp）、数据库查询、文件 IO、需要性能监控的关键路径
    - **不适用**：纯计算函数（如 math 运算）、高频调用（每秒百次以上，埋点开销影响性能）、已有 tenacity 装饰器的方法（装饰器内已处理）、CancelledError 处理（应用 suppress 包裹）
    - **历史教训**：用户反馈"官方采集慢"但无耗时数据，无法定位是 page.goto 慢、wait_for_selector 慢还是业务逻辑慢；补埋点后发现 page.goto 平均 8s（网络问题），为后续优化提供数据支撑


---

### step 81：凭证前置校验与并行采集【强制】🆕v4.13

81. **凭证前置校验与并行采集【强制】🆕v4.13**
    - 昂贵操作（如 `page.goto` 30s 超时）前必须校验凭证有效性（cookie.expires / token.exp / session.timeout）：session cookie（`expires=-1`）跳过校验，persistent cookie（`expires>0`）若 `expires < now` 判定过期直接报 440 不走昂贵流程；多个无依赖 IO 任务必须用 `asyncio.gather(*tasks, return_exceptions=True)` 并行执行，**禁止**串行调用导致总耗时累加
    - **判断信号**：代码含 `await page.goto(url, timeout=30000)` 但前置无 cookie/token 校验 → 必须补前置校验；多个 `await self._fetch_xxx()` 串行调用且无依赖关系 → 必须改为 `asyncio.gather` 并行
    - **修复模式**：
      ```python
      import asyncio
      import time

      # ✅ 凭证前置校验
      async def _ensure_official_collect_cookies() -> None:
          """调用 page.goto 前校验 cookie 有效性，避免 30s 浪费"""
          async def _get_expired() -> list[str]:
              cookies = await _get_cookies()
              now = time.time()
              expired = []
              for c in cookies:
                  name = str(c.get("name") or "")
                  if name not in _OFFICIAL_COLLECT_IDENTITY_COOKIES:
                      continue
                  expires = c.get("expires", -1)
                  # session cookie (expires=-1) 跳过，只校验 persistent cookie
                  if expires > 0 and expires < now:
                      expired.append(name)
              return expired

          expired = await _get_expired()
          if expired:
              raise HTTPException(440, f"Cookie 已过期: {expired}，请重新登录")

      # ✅ 并行采集无依赖任务
      async def _collect_official_data(page, item_id: str) -> dict:
          # reviews extraction 与 seller profile 无依赖关系，并行执行
          reviews_task = _extract_reviews_from_page(page, item_id)
          seller_task = _fetch_seller_profile(page, item_id)

          # return_exceptions=True 容错：一个失败不影响另一个
          reviews_result, seller_result = await asyncio.gather(
              reviews_task, seller_task, return_exceptions=True
          )

          # 逐个检查结果
          reviews = reviews_result if not isinstance(reviews_result, Exception) else []
          if isinstance(reviews_result, Exception):
              logger.warning(f"详情页 {item_id} reviews 提取失败: {reviews_result}")

          seller = seller_result if not isinstance(seller_result, Exception) else {}
          if isinstance(seller_result, Exception):
              logger.warning(f"详情页 {item_id} seller profile 提取失败: {seller_result}")

          return {"reviews": reviews, "seller": seller}
      ```
    - **配置参数**：`precheck_parallel.credential_check_enabled`（默认 `true`，是否启用凭证前置校验）、`precheck_parallel.identity_cookies_whitelist`（项目特定，身份 cookie 白名单，如 `['_m_h5_tk', 'unb', 'cookie2', 'sgcookie']`）、`precheck_parallel.skip_session_cookies`（默认 `true`，`expires=-1` 的 session cookie 跳过校验）、`precheck_parallel.expiry_status_code`（默认 `440`，凭证过期时返回的 HTTP 状态码）、`precheck_parallel.parallel_gather_return_exceptions`（默认 `true`，asyncio.gather 是否容错）、`precheck_parallel.parallel_gather_max_concurrency`（默认 `0` 表示无限制，可设为正整数限制并发数）、`precheck_parallel.parallel_scenarios`（需并行的场景列表，如 `['reviews_and_seller', 'multi_item_collect']`）在 `config.yaml` 的 `precheck_parallel` 节点管理
    - **适用**：昂贵操作前的凭证检查（cookie.expires / token.exp / session.timeout）、多个无依赖 IO 任务并行（reviews + seller、多个独立 API 调用）、批量数据采集
    - **不适用**：有依赖关系的任务（如先登录再采集）、共享资源竞争（如同一浏览器 page 不能并行操作）、顺序敏感的流程（如订单状态机转换）、纯计算任务（并行无性能提升）
    - **历史教训**：未做 cookie expires 前置校验，cookie 已过期仍走 30s page.goto，浪费 30s 后才报 502；reviews 与 seller 串行采集总耗时 12s，改为 asyncio.gather 并行后降至 7s


---

### step 86：浏览器自动化资源拦截粒度规范【强制】🆕v4.15

86. **浏览器自动化资源拦截粒度规范【强制】🆕v4.15**
    - 浏览器自动化资源拦截必须考虑业务关键资源（二维码图片、关键数据接口），禁止盲目拦截 image/font/media。拦截前必须检查页面是否依赖图片渲染关键内容（如二维码图片是登录流程关键资源），若依赖则必须排除或延迟拦截
    - **判断信号**：代码含 `route.abort("image")` 或 `route.abort("font")` 或 `route.abort("media")` → 必须检查页面是否依赖该类型资源渲染关键业务内容；登录流程/二维码页面/图片采集页面 → 禁止拦截 image
    - **修复模式**：
      1. 检查页面关键资源依赖：`grep -rn "route.abort" src/` 找到拦截逻辑
      2. 分析拦截类型：是否拦截了业务关键资源（二维码图片、关键数据接口返回的图片）
      3. 细化拦截规则：按 URL 或资源类型精细化拦截（如只拦截非关键广告图片，保留二维码图片）
      4. 验证：拦截后关键内容仍能正常渲染/加载
    - **配置参数**：`browser.route_block_types`（默认 `["font", "media"]`，不拦截 image）、`browser.route_block_whitelist`（关键资源 URL 白名单，如二维码图片 URL）、`browser.route_block_scenarios`（场景到拦截类型的映射，如 `login → []` 不拦截，`search → ["image", "font", "media"]` 可拦截）在 `config.yaml` 的 `browser.route_block` 节点管理
    - **适用**：浏览器自动化场景的资源拦截优化（减少带宽、加快加载）
    - **不适用**：纯数据抓取页面（无关键图片渲染）、纯 API 请求场景（无需浏览器）
    - **历史教训**：登录流程 `route.abort("image")` 拦截所有图片，导致二维码图片无法渲染，用户看不到二维码无法扫码登录。修复后改为精细化拦截，排除二维码图片 URL


---

### step 88：DEBUG 代码清理规范【强制】🆕v4.15

88. **DEBUG 代码清理规范【强制】🆕v4.15**
    - 临时 DEBUG 代码在问题修复后必须移除，禁止留在生产代码中。DEBUG 代码包括：临时 import（如 `import os as _os`）、临时环境变量检查（如 `environ.get("DEBUG")`）、临时日志文件写入（如 `open("debug.log", "w")`）、临时打印语句（如 `print("DEBUG: ...")`）。问题修复后必须 grep 所有 DEBUG 代码并移除，避免污染生产环境
    - **判断信号**：代码含 `import os as _os` / `environ.get("DEBUG")` / `open("debug.log")` / `print("DEBUG")` / `logger.debug` 异常密集 → 必须检查是否为临时 DEBUG 代码；问题修复后 grep 仍有 DEBUG 代码 → 必须移除
    - **修复模式**：
      1. 问题修复后 grep DEBUG 代码：`grep -rn "DEBUG\|debug\.log\|import os as _os\|environ.get(\"DEBUG\")" src/`
      2. 逐项检查是否为临时调试代码（非长期监控指标）
      3. 移除临时 DEBUG 代码：删除 import、删除环境变量检查、删除日志文件写入、删除打印语句
      4. 验证：grep 无残留 DEBUG 代码
    - **配置参数**：`debug.enabled`（默认 `false`，生产环境禁止 DEBUG 代码）、`debug.cleanup_after_fix`（默认 `true`，问题修复后自动清理 DEBUG 代码）、`debug.whitelist`（长期监控指标白名单，如 `["performance_metrics", "health_check"]`）在 `config.yaml` 的 `debug` 节点管理
    - **适用**：临时调试代码、排查问题后的清理、开发环境调试
    - **不适用**：日志级别动态降级（需保留配置）、长期监控指标收集（需保留）、性能埋点（需保留）
    - **历史教训**：登录流程问题排查时添加 `import os as _os` 和 `open("debug.log", "w")` 写入调试信息，问题修复后未移除，导致生产环境产生 debug.log 文件污染日志目录


---

### step 89：子进程创建标志规范【强制】🆕v4.15

89. **子进程创建标志规范【强制】🆕v4.15**
    - WebView2/Playwright GUI 子进程必须用 `CREATE_NEW_CONSOLE` 标志创建，避免 GUI 进程与主进程控制台输出混淆。Windows 平台 `subprocess.Popen` 的 `creationflags` 参数必须包含 `CREATE_NEW_CONSOLE = 0x00000010`，确保 GUI 子进程有独立控制台窗口
    - **判断信号**：代码含 `subprocess.Popen` 创建 WebView2/Playwright GUI 进程 → 必须检查 `creationflags` 是否包含 `CREATE_NEW_CONSOLE`；GUI 子进程无独立控制台 → 必须添加标志
    - **修复模式**：
      1. 检查 GUI 子进程创建：`grep -rn "subprocess.Popen" src/` 找到进程创建逻辑
      2. 确认 GUI 进程类型：WebView2/Playwright/浏览器等 GUI 进程
      3. 添加 `CREATE_NEW_CONSOLE` 标志：`creationflags=subprocess.CREATE_NEW_CONSOLE`（Windows）
      4. 验证：GUI 子进程启动后有独立控制台窗口，不污染主进程控制台
    - **配置参数**：`subprocess.creationflags_gui`（默认 `0x00000010` 即 CREATE_NEW_CONSOLE）、`subprocess.creationflags_cli`（默认 `0` 无特殊标志）、`subprocess.gui_process_types`（GUI 进程类型列表，如 `["webview2", "playwright", "browser"]`）在 `config.yaml` 的 `subprocess` 节点管理（引用 `project_memory.md` 硬约束）
    - **适用**：所有 GUI 子进程创建（WebView2/Playwright/浏览器）
    - **不适用**：CLI 子进程（无 GUI）、非 Windows 平台（无 CREATE_NEW_CONSOLE 标志）
    - **历史教训**：WebView2 子进程未用 CREATE_NEW_CONSOLE 创建，GUI 输出污染主进程控制台，日志混乱难以排查


---

### step 99：选择器仓库同步与单一数据源规范【强制】🆕v4.19

**背景**：DOM 回退批量解析提取到 1 条数据（实际 31 个卡片）。根因：`_BATCH_PARSE_SCRIPT`（嵌入到 `page.evaluate` 的 JS 字符串）用 2 种 CSS 选择器（`feeds-item-wrap`/`feeds-item`），而 `_find_cards` 的 `card_selectors` 用 6 种（含 `item-card`/`search-item`/`product-card`/`data-spm*='item'`）。两套选择器无同步机制，闲鱼前端 DOM 结构变更时主解析器会更新但批量解析脚本易遗漏。

**规范**：

1. **同一 DOM 数据源的所有解析路径必须引用同一选择器仓库**
   - 选择器仓库（selector repository）是单一数据源，所有解析路径（主解析 `_find_cards` / 批量解析 `_BATCH_PARSE_SCRIPT` / 降级解析）必须引用同一份选择器列表
   - **禁止**在 JS 脚本字符串中内联 CSS 选择器，必须通过 Python 端拼接后注入
   - 选择器仓库需提供 `to_js_selector_string()` 方法，将 Python 列表转为 JS `document.querySelectorAll('...')` 可用的字符串

2. **批量解析脚本必须动态拼接选择器**
   - JS 脚本中的 `document.querySelectorAll(...)` 的参数必须由 Python 端 f-string 或 `.format()` 注入
   - **禁止**在 JS 字符串中硬编码选择器候选列表
   - 修改主解析器选择器时，批量解析脚本自动同步（单一数据源）

3. **新增选择器候选时的同步验证**
   - 在 `selectors.search_card_candidates()` 新增选择器后，必须 grep 所有 `_BATCH_PARSE_SCRIPT` 类变量确认选择器一致
   - 审查时检查 `audit_files`（默认 `["_search.py", "_parser.py", "_detail.py"]`）中所有 `querySelectorAll` 调用

4. **ID 提取多层级兜底**
   - DOM 批量解析必须有 3 层 ID 提取兜底：data-* 属性 → 内部任意 `a[href]` → `/item/数字` 路径
   - 单层提取失败时自动降级到下一层，**禁止**单层失败即返回 None

**判断逻辑**：

- `grep "document\.querySelectorAll" src/xianyu_hunter/modules/` 发现 JS 字符串中硬编码选择器 → 视为违规
- 主解析器的 `card_selectors` 列表与 `_BATCH_PARSE_SCRIPT` 内的选择器字符串不一致 → 视为违规
- 修改主解析器选择器后未同步批量脚本（grep 验证）→ 视为违规
- DOM 解析脚本中 ID 提取只有单层无兜底 → 视为可疑

**反例**：

```python
# ❌ 错误：JS 脚本硬编码 2 种选择器，与主解析器的 6 种不一致
_BATCH_PARSE_SCRIPT = """
() => {
    const cards = document.querySelectorAll(
        "[class*='feeds-item-wrap'], [class*='feeds-item']"  // 仅 2 种
    );
    // ...
}
"""
```

**正例**：

```python
# ✅ 正确：动态拼接选择器字符串，与主解析器共享 selectors 仓库
def _build_batch_parse_script(self) -> str:
    """构造批量解析 JS 脚本，选择器由 selectors 仓库统一提供。

    为什么动态拼接：_BATCH_PARSE_SCRIPT 之前硬编码 2 种选择器，
    与 _find_cards 的 6 种不一致，导致 31 个卡片仅提取到 1 条。
    改为引用 selectors.search_card_candidates() 后自动同步。
    """
    js_selector = self.selectors.to_js_selector_string()  # 单一数据源
    return f"""
() => {{
    const cards = document.querySelectorAll({js_selector});
    // ... 3 层 ID 提取兜底
}}
"""
```

**配置参数**：`selector_repository_sync` 节点（enabled / require_js_consumer_method / audit_files / batch_script_marker / require_id_fallback_layers）

**适用场景**：
- 同一 DOM 数据源有多条解析路径（主解析 + 批量解析 + 降级解析）
- DOM 解析脚本嵌入到 Playwright `page.evaluate` 中执行
- 闲鱼/淘宝/第三方网站前端 DOM 结构频繁变更的场景

**不适用场景**：
- API 响应解析（结构固定，无 DOM 选择器概念）
- 单次单卡片解析（无批量场景）
- 一次性爬虫脚本（无长期维护需求）

**历史教训**：DOM 回退模式检测到 31 个卡片，但 `_BATCH_PARSE_SCRIPT` 仅用 2 种选择器（`feeds-item-wrap`/`feeds-item`），与 `_find_cards` 的 6 种选择器（含 `item-card`/`search-item`/`product-card`/`data-spm*='item'`）不一致，导致仅提取到 1 条数据。修复：选择器对齐为 6 种 + 新增 3 层 ID 提取兜底（data-* 属性、内部任意 a[href]、/item/数字 路径）。


---

### step 100：外部系统文本特征集中管理规范【强制】🆕v4.19

**背景**：商品 1058031608014 实际已售（详情页含"卖掉了"文本），但系统误判为在售（`is_sold=0`）。根因：3 处独立关键词列表（`_detail.py` / `_parser.py` / `buyer.py`）都只检测"已售"/"已售出"等旧文案，未包含闲鱼新文案"卖掉了"。Chrome DevTools MCP 实际打开页面取 body 文本才发现该关键词。

**规范**：

1. **外部系统的文本特征必须集中到单一常量**
   - 外部系统（闲鱼/淘宝/第三方 API）的文本特征（已售关键词/错误码/状态文案/反爬识别）必须提取为模块级常量
   - 常量类型为 `tuple[str, ...]` 或 `frozenset[str]`（不可变，便于扩展）
   - 常量名以 `_KEYWORDS` / `_TEXTS` / `_CODES` 后缀，明确语义
   - **禁止**在多处重复定义同一类关键词列表

2. **多处消费点必须复用同一检测函数**
   - 检测函数封装为纯函数（`check_xxx(text: str) -> bool`），无副作用，便于单测
   - 函数名以 `check_` 前缀，明确语义
   - 多处消费点（详情页/DOM 卡片/抢单前检测）必须 import 并调用同一函数
   - **禁止**在消费点内联关键词列表（如 `if "已售" in text`）

3. **关键词清单变更时的单点修改**
   - 新增外部文案时只需修改单一常量，所有消费点自动同步
   - 修改前必须 grep 全局确认无内联关键词列表遗漏

4. **关键词清单的版本化注释**
   - 常量定义处必须注释历史遗漏案例（如 `# 2026-06-29 发现闲鱼新文案"卖掉了"`）
   - 注释说明为什么集中维护（避免闲鱼文案变更时漏改）

**判断逻辑**：

- `grep "已售\|卖掉了\|已下架\|已删除" src/xianyu_hunter/` 发现同一关键词在多个文件重复 → 视为违规
- 代码含 `if "xxx" in text` 但未调用统一函数 → 视为违规
- 关键词以列表字面量出现在函数内部而非模块级常量 → 视为可疑
- `grep "check_text_sold\|check_item_sold"` 调用点 < 定义点 → 视为可疑（有内联替代）

**反例**：

```python
# ❌ 错误：3 处独立关键词列表，新增文案时漏改
# _detail.py
if any(kw in body_text for kw in ["已售", "已售出", "已售完"]):
    is_sold = True

# _parser.py
if "已售" in text or "已售出" in text:  # 漏了"卖掉了"
    return True

# buyer.py
SOLD_KEYWORDS = ["已售", "已售出"]  # 漏了"卖掉了"
```

**正例**：

```python
# ✅ 正确：单一常量 + 纯函数 + 3 处复用
# collector_utils.py
SOLD_TEXT_KEYWORDS: tuple[str, ...] = (
    "已售", "已售出", "已售完", "已售罄", "宝贝已售", "商品已售",
    "已下架", "已卖出",
    "卖掉了",  # 闲鱼新版文案（2026-06-29 发现）
    "宝贝不存在", "宝贝走丢了", "该宝贝不存在", "商品不存在", "已删除", "已被删除",
)

def check_text_sold(text: str) -> bool:
    """检测页面文本是否表示商品已售。

    为什么集中维护：闲鱼前端文案多次变更，分散在 3 个文件的关键词列表容易漏改。
    历史遗漏案例：2026-06-29 发现商品 1058031608014 详情页显示"卖掉了"但被误判为在售。
    """
    if not text:
        return False
    return any(kw in text for kw in SOLD_TEXT_KEYWORDS)

# _detail.py / _parser.py / buyer.py 统一复用
from xianyu_hunter.modules.collector_utils import check_text_sold
is_sold = check_text_sold(body_text)
```

**配置参数**：`external_text_pattern_centralize` 节点（enabled / require_constant_extraction / require_pure_function / audit_keywords / max_inline_occurrences / require_version_comment）

**适用场景**：
- 外部系统文案检测（已售/下架/错误状态/异常提示）
- 错误码识别（HTTP 状态码/业务错误码/反爬识别）
- 第三方 API 响应文本特征提取
- 多处消费同一类文本特征的场景

**不适用场景**：
- 内部状态判断（如 `task.status == 'completed'`，前端可控）
- 单一消费点的临时字符串比较
- 配置文件中已管理的关键词（无需再提取为代码常量）

**历史教训**：商品 1058031608014 实际已售（详情页 body 文本含"卖掉了"），但 3 处独立关键词列表（`_detail.py` / `_parser.py` / `buyer.py`）都未包含"卖掉了"，导致系统误判为在售，用户看到已售商品仍被推荐。Chrome DevTools MCP 实际打开页面取 body 文本才发现该关键词。修复后提取 `SOLD_TEXT_KEYWORDS` 常量 + `check_text_sold()` 函数到 `collector_utils.py`，3 处复用。


---

### step 168：COOKIE-01 Cookie 完整保留与导入规范【强制】🆕v4.29

**背景**：浏览器导入 cookie 时仅保留少量关键字段（name/value），丢弃 `domain`/`path`/`expires`/`secure`/`httponly` 等字段，导致 75+ cookie 目标无法达成，反爬触发频率升高。

**问题**：cookie 字段不完整时，浏览器无法正确匹配 cookie 到请求域，导致请求被反爬拦截；导入逻辑未用 `import_full=true` 模式，仅保留关键字段即丢失上下文。

**规范**：

1. **Cookie 导入必须保留完整字段【强制】**：浏览器导入 cookie 时必须用 `import_full=true` 模式，保留所有字段（name/value/domain/path/expires/secure/httponly/samesite），禁止仅保留 name/value：
   ```python
   # ✅ 正确：import_full=true 保留完整字段
   await browser_import.import_cookies(cookies, import_full=True)

   # ❌ 错误：仅保留 name/value，丢失 domain/path
   # await browser_import.import_cookies(
   #     [{"name": c["name"], "value": c["value"]} for c in cookies]
   # )
   ```

2. **75+ cookie 目标【强制】**：cookie 同步必须维护 75+ 条完整 cookie，覆盖 `_m_h5_tk` / `cookie2` / `sgcookie` / `unb` / `csg` 等关键反爬字段，禁止仅同步少量登录 cookie。

3. **Cookie 字段缺失检测【强制】**：导入前必须检测关键字段（domain/path/expires）是否完整，缺失时记录 warning 并跳过该 cookie。

**配置驱动**：`coding_standards.cookie.import_full`（`true`）、`min_cookie_count`（`75`）、`required_fields`（`['name', 'value', 'domain', 'path', 'expires']`）在 `config.yaml` 管理。

**适用场景**：
- 浏览器自动化 cookie 导入（Playwright/WebView2）
- 反爬 cookie 同步（75+ cookie 目标）
- 多源 cookie 合并（浏览器内存 + DB + 文件）

**不适用场景**：
- 临时会话 cookie（无需持久化）
- 测试环境 mock cookie（字段可简化）

**历史教训**：`browser_import.py` 仅保留 cookie 的 name/value 字段，导入后浏览器无法匹配 cookie 到 `.taobao.com` 域，反爬触发频率从 5% 升至 40%。修复后改用 `import_full=true` 保留完整字段，cookie 数量从 12 条提升到 78 条。

**判断信号（review 触发条件）**：
- `grep "import_cookies" <file>` 后无 `import_full=True`
- 导入后 cookie 数量 < 75
- cookie 字段缺失 domain/path/expires


---

### step 169：PARSER-01 解析器多层兜底规范【强制】🆕v4.29

**背景**：DOM 解析器仅用单一选择器（如 `data-id`），闲鱼前端变更 HTML 结构后选择器失效，解析返回空列表；无兜底选择器导致采集全面中断。

**问题**：依赖单一 DOM 选择器的解析器在外部前端变更时即失效；无多层兜底机制导致采集中断，需等待修复才能恢复。

**规范**：

1. **多选择器仓库【强制】**：DOM 解析器必须维护多选择器仓库（≥3 种），按优先级顺序匹配，任一选择器命中即返回结果：
   ```python
   # ✅ 正确：6 种选择器 + 3 层 ID 提取兜底
   CARD_SELECTORS = [
       "[data-id]",                    # 优先：data-id 属性
       ".item-card[data-itemid]",      # 兜底 1：class + data-itemid
       "a[href*='/item/']",            # 兜底 2：href 路径
       ".search-item .item-info",      # 兜底 3：class 结构
       "[data-spm*='item']",           # 兜底 4：data-spm
       ".feeds-item",                  # 兜底 5：feeds class
   ]

   for selector in CARD_SELECTORS:
       cards = await page.query_selector_all(selector)
       if cards:
           break
   ```

2. **ID 提取 3 层兜底【强制】**：商品 ID 提取必须有 3 层兜底（`data-*` 属性 → `a[href]` 路径 → `/item/数字` 正则），禁止依赖单一提取方式。

3. **选择器仓库单一数据源【强制】**：多解析路径（主解析/批量解析/降级解析）必须引用同一选择器仓库，禁止各路径独立维护选择器。

**配置驱动**：`coding_standards.parser.min_selectors`（`3`）、`id_fallback_layers`（`3`）、`single_source`（`true`）在 `config.yaml` 管理。

**适用场景**：
- 爬虫 DOM 解析（闲鱼/淘宝等外部前端）
- 多解析路径共享选择器仓库
- 外部前端频繁变更的场景

**不适用场景**：
- 内部系统 DOM（可控，无需多层兜底）
- API 响应解析（用 JSON path，非 DOM 选择器）

**历史教训**：`_BATCH_PARSE_SCRIPT` 仅用 2 种选择器，闲鱼前端改版后 2 种选择器均失效，采集全面中断 6 小时。修复后扩展到 6 种选择器 + 3 层 ID 提取兜底，覆盖更多 HTML 结构变体。

**判断信号（review 触发条件）**：
- 解析器选择器数量 < 3
- ID 提取无兜底（仅 1 种方式）
- 多解析路径选择器各自维护（非单一数据源）
- 采集返回空列表但页面有数据


---

### step 170：KEYWORD-01 爬虫关键词集中管理规范【强制】🆕v4.29

**背景**：爬虫模块的已售关键词列表分散在 `_detail.py` / `_parser.py` / `buyer.py` 三个文件，闲鱼新增「卖掉了」文案时仅更新了 2 个文件，第 3 个文件漏改导致误判。

**问题**：爬虫关键词（已售/下架/错误码/反爬识别）分散在多个模块时，外部文案变更需逐文件修改，漏改即导致误判；与 step 100（外部系统文本特征集中管理）有重叠，但本规范强调爬虫场景的多消费点强制复用。

**规范**：

1. **爬虫关键词必须集中到 `collector_utils.py`【强制】**：爬虫模块的关键词（已售/下架/错误码/反爬识别）必须集中到 `collector_utils.py` 的模块级常量，禁止分散在 `_detail.py` / `_parser.py` / `buyer.py`：
   ```python
   # collector_utils.py
   SOLD_TEXT_KEYWORDS: tuple[str, ...] = (
       "已售", "已售出", "已售完", "已售罄", "宝贝已售", "商品已售",
       "已下架", "已卖出",
       "卖掉了",  # 闲鱼新版文案（2026-06-29 发现）
       "宝贝不存在", "宝贝走丢了", "该宝贝不存在", "商品不存在", "已删除", "已被删除",
   )

   def check_text_sold(text: str) -> bool:
       if not text:
           return False
       return any(kw in text for kw in SOLD_TEXT_KEYWORDS)
   ```

2. **多处消费点必须 import 同一函数【强制】**：`_detail.py` / `_parser.py` / `buyer.py` 必须从 `collector_utils` import `check_text_sold`，禁止内联关键词列表：
   ```python
   # ✅ 正确：统一 import
   from xianyu_hunter.modules.collector_utils import check_text_sold
   is_sold = check_text_sold(body_text)

   # ❌ 错误：内联关键词列表
   # if any(kw in body_text for kw in ["已售", "已售出"]):  # 漏了"卖掉了"
   #     is_sold = True
   ```

3. **关键词变更必须版本化注释【强制】**：新增关键词时必须注释发现日期与来源商品 ID，便于追溯历史遗漏。

**配置驱动**：`coding_standards.crawler_keyword.centralize`（`true`）、`required_consumer_import`（`true`）在 `config.yaml` 管理。

**适用场景**：
- 爬虫模块关键词管理（已售/下架/错误码/反爬）
- 多消费点（详情页/列表页/抢单前检测）复用同一关键词
- 外部文案频繁变更的场景

**不适用场景**：
- 内部状态判断（如 `task.status == 'completed'`）
- 单一消费点的临时字符串比较

**历史教训**：商品 1058031608014 详情页显示「卖掉了」，但 `buyer.py` 的 `SOLD_KEYWORDS` 列表仅含「已售」「已售出」，未包含「卖掉了」，导致抢单前检测误判为在售。Chrome DevTools MCP 打开页面取 body 文本才发现该关键词。修复后提取 `SOLD_TEXT_KEYWORDS` 常量 + `check_text_sold()` 函数到 `collector_utils.py`，3 处复用。

**判断信号（review 触发条件）**：
- `grep "已售\|卖掉了\|已下架" src/xianyu_hunter/modules/` 同一关键词在多个文件出现
- `grep "if .* in text" <file>` 内联关键词列表而非 import `check_text_sold`
- 爬虫误判已售商品为在售


---

### step 191：外部页面解析容错规范【强制，meta-rule #54 落地】🆕v4.37

191. **外部页面解析容错规范【强制，meta-rule #54 落地】🆕v4.37**
    - 解析不受控的第三方页面 DOM（闲鱼/淘宝/天猫/京东等）必须采用多级 fallback selector 策略，按"结构化 selector → 属性 selector → 文本扫描"顺序尝试，任一 selector 命中即返回，全部失败才触发 debug dump（参见 step 79），**禁止**只依赖单一 className 选择器导致页面改版时数据全空
    - **与 step 78 多层兜底链模式的边界**：
      - step 78 关注"DOM → og:meta → document.title"的**跨类型兜底**（从结构化到非结构化）
      - 本规范关注"同类 selector 的多级 fallback"（如多个 tab 选择器互为备份，仍是结构化提取）
    - **三级 fallback 策略**：
      | 级别 | 策略 | 典型 selector | 容错来源 |
      |------|------|----------------|----------|
      | L1 结构化 selector | className 精确匹配 | `[class*='tabItem']` | DOM 结构已知 |
      | L2 属性 selector | role/aria 属性匹配 | `[class*='tab'][role='tab']` | 语义稳定但 class 易变 |
      | L3 文本扫描 | 标签文本前缀匹配 | `div/span/a` 文本含 `在售`/`已售` | 仅依赖可见文案 |
    - **debug dump 触发条件**：基于**业务语义**（如 `on_sale == 0`）而非**实现细节**（如 `sold == 0`），因为 `sold == 0` 可能是新版 UI 的预期行为，不应误判为解析失败
    - **判断信号**：
      - `grep "querySelector\|querySelectorAll\|select\|css"` 在外部页面解析上下文，无 `try/except` 或 `or []` fallback → 违规
      - `grep "tabItem\|tab.*role.*tab\|tab.*class"` selector 字符串硬编码 → 违规（必须配置化）
      - debug dump 条件含 `sold == 0`（实现细节）而非 `on_sale == 0`（业务语义）→ 违规
    - **修复模式**：
      ```python
      # ✅ 正确：三级 fallback + 业务语义触发 dump
      async def _parse_sale_counts_from_tabs(page, item_id: str) -> dict:
          selectors = cfg.parser_fallback.tab_selectors  # 从 config 读取
          on_sale, sold = 0, 0

          # L1 结构化 selector
          try:
              tabs = await page.query_selector_all(selectors[0])
              if tabs:
                  on_sale, sold = await _extract_from_tabs(tabs)
          except Exception as e:
              logger.debug(f"详情页 {item_id} L1 selector 失败: {e}")

          # L2 属性 selector（L1 失败才尝试）
          if on_sale == 0 and sold == 0:
              try:
                  tabs = await page.query_selector_all(selectors[1])
                  if tabs:
                      on_sale, sold = await _extract_from_tabs(tabs)
              except Exception as e:
                  logger.debug(f"详情页 {item_id} L2 selector 失败: {e}")

          # L3 文本扫描（L2 失败才尝试）
          if on_sale == 0 and sold == 0:
              on_sale, sold = await _scan_text_prefix(page)

          # 业务语义触发 dump（不是 sold == 0）
          if on_sale == 0:
              await _dump_html_for_diagnosis(page, "sale_counts", item_id)
              logger.warning(f"详情页 {item_id} on_sale=0，已 dump HTML")
          return {"on_sale": on_sale, "sold": sold}

      # ❌ 错误：单一 selector + 实现细节触发 dump
      # tabs = await page.query_selector_all("[class*='tabItem']")
      # if not tabs or sold == 0:  # 实现细节触发，新版 UI 误报
      #     await _dump_html_for_diagnosis(page, "sale_counts", item_id)
      ```
    - **配置参数**：`parser_fallback.tab_selectors`（默认 `['[class*="tabItem"]', '[class*="tab"][role="tab"]', 'text_scan']`）、`parser_fallback.dump_trigger_field`（默认 `on_sale`，业务语义字段名）、`parser_fallback.dump_trigger_value`（默认 `0`）、`parser_fallback.fallback_chain_log_level`（默认 `debug`，中间步骤日志级别）、`parser_fallback.final_failure_log_level`（默认 `warning`）在 `config.yaml` 的 `parser_fallback` 节点管理
    - **适用**：解析闲鱼/淘宝/天猫/京东等第三方页面的 DOM（`_detail.py` / `_parse_*` 函数 / Playwright `page.evaluate` 返回值解析）
    - **不适用**：解析自己生成的内容（本地 HTML 模板）、解析 API 返回的 JSON（结构稳定）、解析固定 schema 的 XML/YAML
    - **历史教训**：`_parse_sale_counts_from_tabs` 仅依赖 `tabItem` class 名，闲鱼页面 DOM 结构变化导致 `on_sale=0` 和 `sold=0`。原 dump 条件 `on_sale==0 or sold==0` 在新版 UI（`sold=0` 是预期行为）下持续误报，产生大量噪声 dump 文件。修复：实现三级 fallback（`[class*='tabItem']` → `[class*='tab'][role='tab']` → 文本前缀扫描 div/span/a），收紧 dump 触发条件从 `on_sale==0 or sold==0` 改为 `on_sale==0`


---

### step 201：CSS-SELECTOR-FALLBACK CSS 选择器多级降级策略【强制】🆕v4.38

**背景**：本轮对话修复的 8 类问题之一——CSS 选择器仅依赖单一 className（如 `.tabItem`），第三方网站改版后 className 变更导致选择器失效，数据解析全部返回空值，但代码无降级机制。

**问题**：CSS 选择器是浏览器自动化的核心，但第三方网站的 DOM 结构随时可能变化。仅依赖单一 className 选择器（如 `.tabItem`）的代码在网站改版后会全部失效，且无法快速定位是选择器问题还是数据本身为空。

**规范**：

1. **CSS 选择器必须有多级降级【强制】**：所有解析第三方 DOM 的 CSS 选择器必须按「特定 → 通用 → 最末兜底」三级降级，每级失败进入下一级，所有兜底失败才走 dump 机制：
   ```python
   # ✅ 正确：三级降级
   SELECTOR_CHAIN = [
       ".tabItem",                          # 第一级：特定 className（最精确，但易失效）
       "[class*='tab'][role='tab']",        # 第二级：属性选择器（不依赖具体 className）
       "div, span, a",                      # 第三级：通用标签 + 文本扫描（最末兜底）
   ]
   for selector in SELECTOR_CHAIN:
       elements = await page.query_selector_all(selector)
       if elements:
           break
   ```

2. **降级策略优先级【强制】**：选择器降级按以下优先级排序：
   - **第一级（特定）**：className / id 选择器（最精确，但易失效）
   - **第二级（属性）**：`[data-*]` / `[role]` / `[aria-*]` 属性选择器（不依赖 className，较稳定）
   - **第三级（结构）**：`a[href*='/item/']` 等路径选择器（基于 URL 结构，最稳定）
   - **第四级（兜底）**：`document.title` / `meta[property='og:title']` / 通用标签文本扫描

3. **每级降级必须记录日志【强制】**：每级降级必须用 `logger.debug` 记录降级原因与命中选择器，便于排查：
   ```python
   if not elements:
       logger.debug(f"选择器 {selector} 未命中，降级到下一级")
       continue
   logger.debug(f"选择器 {selector} 命中 {len(elements)} 个元素")
   ```

4. **dump 触发条件基于业务语义【强制】**：所有兜底失败后触发 dump 的条件必须基于业务语义字段（如 `on_sale == 0`）而非实现细节（如 `on_sale == 0 or sold == 0`），避免新版 UI 的预期空值触发误报。

5. **选择器仓库集中管理【强制】**：所有 CSS 选择器必须集中在 `selectors.py` 或 `selectors.yaml` 管理，禁止散落在代码中，便于网站改版时统一更新。与 step 99「选择器仓库同步与单一数据源规范」配合。

**配置驱动**：`css_selector_fallback` 节点管理降级策略，包含 `required_levels`（默认 `3`，最少降级级数）、`fallback_chain_log_level`（默认 `debug`）、`final_failure_log_level`（默认 `warning`）、`dump_trigger_based_on_business_semantics`（默认 `true`）、`selector_repository_required`（默认 `true`）、`selector_repo_path`（默认 `"src/xianyu_hunter/modules/collector/selectors.py"`）在 `config.yaml` 管理，不硬编码。

**适用场景**：
- 解析第三方网站 DOM（闲鱼/淘宝/天猫/京东等）
- Playwright `page.query_selector` / `page.query_selector_all` 调用
- `page.evaluate` 中的 `document.querySelector` 调用
- 任何依赖外部 DOM 结构的 CSS 选择器

**不适用场景**：
- 解析自己生成的内容（本地 HTML 模板，DOM 结构可控）
- 解析 API 返回的 JSON（结构稳定，无需选择器）
- 测试代码中的固定 DOM（测试环境可控）

**历史教训**：`_parse_sale_counts_from_tabs` 仅依赖 `.tabItem` className，闲鱼页面改版后 className 变更为 `_tabItem_1a2b3`，选择器失效导致 `on_sale=0` 和 `sold=0`。用户反馈"商品数据全空"但无明确错误，排查 2 小时才发现是选择器失效。修复后实现三级降级（`.tabItem` → `[class*='tab'][role='tab']` → 文本扫描），并收紧 dump 触发条件从 `on_sale==0 or sold==0` 改为 `on_sale==0`，避免新版 UI 的预期 `sold=0` 触发误报。

**判断信号（review 触发条件）**：
- `grep "query_selector\|querySelector" <file>` 命中但无降级链
- 选择器中含具体 className（如 `.tabItem`）但无属性选择器兜底
- dump 触发条件含 `or` 连接多个字段（可能是实现细节触发）
- 选择器散落在多个文件而非集中在 `selectors.py`


---

### step 233：async 阻塞调用超时保护【强制】🆕v4.48.0

**背景**：浏览器自动化中，Playwright 通过 IPC 通道与浏览器进程通信，`await context.cookies()` / `await bc.storage_state()` / `await page.evaluate()` 等 async 调用在浏览器进程无响应或 IPC 通道阻塞时会永久挂起，既不返回也不抛异常。此类挂起会连锁影响所有依赖主流程的辅助机制（如心跳更新），导致整体卡死。

**问题**：浏览器登录成功后进入 Cookie 导出阶段（`_prepare_login_cookie_export`），其中的 `context.cookies()` 与 `bc.storage_state()` 缺少 `asyncio.wait_for` 超时保护，浏览器进程无响应时永久挂起，触发后端 90s 心跳超时误判"登录进程无响应"。

**规范**：
1. 所有可能永久挂起的 Playwright async API 调用（`cookies` / `storage_state` / `snapshot` / `title` / `url` / `evaluate`）必须用 `asyncio.wait_for(coro, timeout=...)` 包裹，禁止裸 `await`
2. 超时值按调用成本分类从 `config.yaml#asyncTimeoutProtection.timeoutByCategory` 读取：
   - `lightweightRead`（title / url 等轻量读取）
   - `heavySerialize`（cookies / storage_state / snapshot 等重序列化）
   - `evaluate`（page.evaluate 等 JS 执行）
3. 超时触发后必须走 fallback（返回空列表 / 返回缓存 / 跳过当前阶段），不中断主流程；fallback 策略从 `config.yaml#asyncTimeoutProtection.fallbackStrategy` 读取
4. 超时日志必须包含阶段名、调用 API 名、配置超时值、实际耗时，便于定位是哪一类 IPC 阻塞
5. 配置 `asyncTimeoutProtection.enabled=false` 时整体禁用，但必须在 PR 中说明理由

**判断逻辑**：
- `grep "await.*\.(cookies|storage_state|snapshot|title|url|evaluate)\("` 命中 → 检查是否被 `asyncio.wait_for` 包裹
- 未包裹 → 违反规范 1
- 包裹但超时值硬编码 → 违反规范 2
- 包裹但超时后 raise → 违反规范 3
- 日志无阶段名/API 名/超时值 → 违反规范 4

**反例**：
```python
# ❌ 裸 await，浏览器进程无响应时永久挂起
async def _prepare_login_cookie_export(context, bc):
    cookies = await context.cookies()
    state = await bc.storage_state()
    return cookies, state
```

**正例**：
```python
# ✅ asyncio.wait_for 包裹 + 配置驱动 + fallback 不中断
import asyncio
from config import get_config

async def _prepare_login_cookie_export(context, bc, stage_name="cookie_export"):
    cfg = get_config().asyncTimeoutProtection
    if not cfg.enabled:
        # 整体禁用时直接调用（需 PR 说明理由）
        cookies = await context.cookies()
        state = await bc.storage_state()
        return cookies, state

    heavy_timeout = cfg.timeoutByCategory.heavySerialize
    fallback = cfg.fallbackStrategy

    # cookies 调用：heavySerialize 类
    try:
        cookies = await asyncio.wait_for(context.cookies(), timeout=heavy_timeout)
    except asyncio.TimeoutError:
        logger.warning(
            f"stage={stage_name} api=context.cookies timeout={heavy_timeout}s "
            f"fallback={fallback} elapsed=>{heavy_timeout}s"
        )
        cookies = [] if fallback == "best_effort" else await _load_cached_cookies()

    # storage_state 调用：heavySerialize 类（同 cookies 一致，参见 step 235）
    try:
        state = await asyncio.wait_for(bc.storage_state(), timeout=heavy_timeout)
    except asyncio.TimeoutError:
        logger.warning(
            f"stage={stage_name} api=bc.storage_state timeout={heavy_timeout}s "
            f"fallback={fallback} elapsed=>{heavy_timeout}s"
        )
        state = {"cookies": cookies} if fallback == "best_effort" else await _load_cached_state()

    return cookies, state
```

**配置参数**（`config.yaml#asyncTimeoutProtection`）：
- `enabled`：是否启用（默认 true）
- `timeoutByCategory.lightweightRead`：轻量读取超时（秒）
- `timeoutByCategory.heavySerialize`：重序列化超时（秒）
- `timeoutByCategory.evaluate`：JS 执行超时（秒）
- `fallbackStrategy`：fallback 策略（best_effort / cached / abort）
- `auditGrepPattern`：审查用 grep 正则

**适用场景**：
- Playwright 浏览器自动化（cookies / storage_state / snapshot / title / url / evaluate）
- 跨进程 IPC 的 async 调用（浏览器进程 / 子进程 / 长连接）
- 网络读取类 async API（httpx 流式读取、websocket recv）
- 文件 I/O 类 async API（aiofiles 大文件读取）

**不适用场景**：
- 纯内存计算类 async 调用（asyncio.Lock / asyncio.Queue 的 acquire/get）
- 已有显式 timeout 参数的 API（如 `httpx.AsyncClient.get(timeout=...)`）
- 框架级 timeout 已覆盖的场景（如 FastAPI 请求级 timeout）
- 单元测试中的 mock async 调用

**历史教训**：浏览器登录 Cookie 导出阶段 IPC 阻塞导致 90s 心跳超时误判 Bug（2026-07-18 修复）。`_prepare_login_cookie_export` 中 `await context.cookies()` 和 `await bc.storage_state()` 在浏览器进程无响应时永久挂起，导致心跳 `set_status` 无法更新 `ts` 字段，后端 90s 后误判卡死报"登录进程无响应"，但实际登录早已成功。修复：所有 Playwright async API 调用统一用 `asyncio.wait_for` 包裹，按调用成本分类配置超时，超时后走 fallback 不中断主流程。

**判断信号（review 触发条件）**：
- `grep "await.*\.(cookies|storage_state|snapshot|title|url|evaluate)\("` 命中但无 `asyncio.wait_for` 包裹
- `grep "asyncio.wait_for" <file>` 数量 < `grep "await.*\.(cookies|storage_state|snapshot|title|url|evaluate)\("` 数量
- 配置 `asyncTimeoutProtection.enabled=false` 但 PR 无说明
- 超时值硬编码在代码中而非从 config 读取


---

### step 235：跨代码块一致性检查【推荐】🆕v4.48.0 experimental

> **experimental 标签**：本规则基于单一 Bug 复盘沉淀，需更多案例验证才能升级为正式规则。当前作为推荐性规范执行，季度复盘时评估升级条件。

**背景**：浏览器自动化流程中，同一类 Playwright API 调用散落在多个代码块（`_prepare_login_cookie_export`、`_verify_login_state`、`_inject_cookies` 等），单纯靠 review 难以发现"同一 API 在不同代码块保护措施不一致"的问题，因为 reviewer 通常聚焦单个代码块的逻辑，而非跨块的一致性。

**问题**：早期对 `context.cookies()` 加了 `asyncio.wait_for` 保护，但 `bc.storage_state()` 在另一代码块中调用却遗漏了保护；同时 `context.cookies()` 在 `_verify_login_state` 中也无保护。这种不一致导致保护存在盲区，部分调用点仍会永久挂起。

**规范**：
1. 同一 API（如 `context.cookies()`、`bc.storage_state()`、`page.evaluate()`）在 ≥2 处代码块调用时，保护措施（超时 / 异常处理 / fallback）必须一致，以更严格为准同步修复
2. 一致性维度包括：是否包裹 `asyncio.wait_for`、超时值是否同量级、异常处理是否同类型（try/except vs raise）、fallback 策略是否相同
3. 当发现某 API 在 A 处有保护、B 处无保护时，必须将 B 处同步升级到 A 处的保护级别，禁止"只在 review 触发的位置补丁式修复"
4. `min_occurrences`（最小出现次数，默认 2）从 `config.yaml#consistencyCheck.minOccurrences` 读取，扫描路径从 `config.yaml#consistencyCheck.scanPaths` 读取

**判断逻辑**：
- grep 同一 API 名（如 `context.cookies`），统计出现次数 ≥ `minOccurrences`（默认 2）→ 触发一致性检查
- 同一 API 在 A 文件有 `asyncio.wait_for` 包裹，在 B 文件裸 `await` → 不一致
- 同一 API 在 A 文件 try/except 兜底返回 `[]`，在 B 文件抛原始异常 → 不一致
- 同一 API 在 A 文件超时值从 config 读取，在 B 文件硬编码 → 不一致

**反例**：
```python
# ❌ context.cookies() 在两处调用，保护不一致
# 文件 A：_prepare_login_cookie_export
cookies = await asyncio.wait_for(context.cookies(), timeout=10.0)  # 有保护

# 文件 B：_verify_login_state
cookies = await context.cookies()  # ❌ 无保护，浏览器无响应时永久挂起
```

**正例**：
```python
# ✅ 同一 API 多处调用时保护一致，超时值从 config 统一读取
# 文件 A：_prepare_login_cookie_export
heavy_timeout = get_config().asyncTimeoutProtection.timeoutByCategory.heavySerialize
cookies = await asyncio.wait_for(context.cookies(), timeout=heavy_timeout)

# 文件 B：_verify_login_state（同 A 完全一致的保护）
heavy_timeout = get_config().asyncTimeoutProtection.timeoutByCategory.heavySerialize
cookies = await asyncio.wait_for(context.cookies(), timeout=heavy_timeout)
```

**配置参数**（`config.yaml#consistencyCheck`）：
- `enabled`：是否启用（默认 true）
- `minOccurrences`：触发一致性检查的最小出现次数（默认 2）
- `scanPaths`：扫描的文件路径列表
- `reviewCheckpoint`：审查 checkpoint 名（B-REVIEW-228）

**适用场景**：
- 同一 Playwright API 在多个函数 / 多个文件调用的场景
- 同一 httpx 调用在多模块复用的场景
- 同一外部服务 SDK 调用散落多个代码块的场景
- 重构后同一 API 在新旧代码并存的过渡期

**不适用场景**：
- API 只在单处调用（无一致性需求）
- 不同 API 但功能相似（如 `cookies()` 与 `storage_state()`）→ 走 step 233 统一保护
- 测试代码中的 mock 调用（不真正执行，无需一致性）
- experimental 阶段未达 minOccurrences 的 API

**历史教训**：浏览器登录 Cookie 导出阶段 IPC 阻塞导致 90s 心跳超时误判 Bug（2026-07-18 修复）。`context.cookies()` 在 `_prepare_login_cookie_export` 中已有部分保护，但 `bc.storage_state()` 在同一函数内调用却完全无保护；同时 `context.cookies()` 在 `_verify_login_state` 中也无保护。修复：对所有调用点统一加 `asyncio.wait_for`，超时值从 config 统一读取，确保同 API 跨块保护一致。

**判断信号（review 触发条件）**：
- grep 同一 API 名（如 `context.cookies`），统计出现次数 ≥ `minOccurrences`（默认 2）
- 同一 API 在 A 文件有 `asyncio.wait_for` 包裹，在 B 文件裸 `await`
- 同一 API 在 A 文件 try/except 兜底，在 B 文件抛原始异常
- 同一 API 在 A 文件超时值从 config 读取，在 B 文件硬编码


---

### step 276：EXTERNAL-RESOURCE-ASYNC-LIVENESS 外部资源活性真异步检测规范【强制】🆕v4.69

**背景**：点击"实时搜索"报"浏览器不可用，请稍后重试"（503）。日志显示 `BrowserManager.is_alive()` 用 `self._context.pages`（同步 property）检测连接活性，`pages` 返回内部缓存的页面对象列表，不触发 CDP 请求。浏览器底层连接已断开时 `pages` 仍可访问并返回缓存列表，导致 `is_alive` 错误返回 `True`，`ensure_alive` 走快速路径不触发重启，后续 `add_cookies` / `get_cookies` 反复抛 `"Connection closed while reading from the driver"`，实时搜索持续报 503。

**问题**：外部资源（Playwright BrowserContext / HTTP 连接 / 数据库连接）的活性检测使用了同步属性（property / 缓存字段），同步属性返回内部缓存数据不触发真实的网络/IPC 调用，连接已断开时仍返回缓存的"正常"结果，导致活性检测假阳性，不触发重连/重启逻辑，后续操作反复失败。

**规范**：

1. **活性检测必须用真异步调用【强制】**：外部资源活性检测必须用真实的异步 RPC/CDP/HTTP 调用验证连接，**禁止**用同步属性（property / 缓存字段 / 内存标志位）：
   ```python
   # ✅ 正确：用真异步 CDP 调用检测连接活性
   async def is_alive(self) -> bool:
       if self._context is None:
           return False
       try:
           # cookies() 是 async CDP 调用（Network.getAllCookies），
           # 连接断开时会抛异常，真实反映连接状态
           await self._context.cookies()
           return True
       except Exception:
           return False

   # ❌ 错误：用同步 property 检测，连接断开时仍返回缓存列表
   async def is_alive(self) -> bool:
       if self._context is None:
           return False
       # pages 是同步 property，返回内部缓存列表，不触发 CDP 请求
       # 连接断开时 pages 仍可访问，导致 is_alive 假阳性
       return len(self._context.pages) >= 0  # 永远 True
   ```

2. **不要求返回值非空【强制】**：活性检测只验证"连接是否可用"，**不要求**返回值非空。刚重启的浏览器可能没有 Cookie、刚创建的连接可能没有活跃页面，但连接仍可用：
   ```python
   # ✅ 正确：只验证调用成功，不要求 cookies 非空
   await self._context.cookies()  # 刚重启的浏览器 cookies 为空，但调用成功即连接可用
   return True

   # ❌ 错误：要求 cookies 非空，刚重启的浏览器会误判为不可用
   cookies = await self._context.cookies()
   return len(cookies) > 0  # 刚重启时 cookies 为空，误判不可用
   ```

3. **异常即不可用【强制】**：真异步调用抛任何异常（`Connection closed` / `TimeoutError` / `TargetClosedError`）即判定连接不可用，必须返回 `False` 触发 `ensure_alive` 重连逻辑，**禁止**捕获异常后返回 `True` 或忽略。

4. **与 step 203 配合【强制】**：`is_alive` 返回 `False` 后，`ensure_alive` 必须按 step 203「EXTERNAL-RESOURCE-LIFECYCLE」执行重连：注销旧资源 → 创建新资源 → 注册到容器 → 持有强引用。

5. **性能权衡【推荐】**：真异步调用有 IPC 开销，`is_alive` 调用频率应从配置读取（如每次 `ensure_alive` 前调用，而非每秒轮询），高频场景可加短缓存（如 1 秒内只调一次），但缓存时间必须从配置读取且 ≤ 5 秒（避免缓存过久导致假阳性）。

**配置驱动**：参数在 `config.yaml` 的 `externalResourceAsyncLiveness` 节点管理，包含 `enabled`（开关，默认 true）、`livenessCheckMethod`（活性检测方法名，默认 `cookies`）、`requireNonNullResult`（是否要求返回值非空，默认 `false`）、`cacheTtlSeconds`（结果缓存时间，默认 `0` 不缓存，最大 5）、`exceptionMeansDead`（异常即不可用，默认 `true`）、`applicableResources`（适用的资源类型列表，如 `["BrowserContext", "HttpClient", "DatabaseConnection"]`）、`forbiddenSyncProperties`（禁止用于活性检测的同步属性列表，如 `["pages", "is_connected", "_alive"]`）。

**适用场景**：
- Playwright BrowserContext / Page 连接活性检测（`is_alive` / `ensure_alive`）
- HTTP 连接池活性检测（httpx.AsyncClient / aiohttp.ClientSession）
- 数据库连接活性检测（SQLAlchemy engine / connection）
- WebSocket 连接活性检测
- 任何外部资源（子进程 / 文件句柄 / socket）的活性检测

**不适用场景**：
- 内存对象活性检测（无外部连接，用 `is None` 即可）
- 同步资源活性检测（如 `file.closed`，property 本身反映真实状态）
- 有内建健康检查的资源（如 `httpx.AsyncClient.is_closed` 已是真检测）
- 测试代码中的 mock 对象（mock 行为可控）

**历史教训**：2026-07-30 用户点击"实时搜索"报"浏览器不可用，请稍后重试"（503）。`BrowserManager.is_alive()` 用 `self._context.pages`（同步 property）检测，`pages` 返回内部缓存列表不触发 CDP 请求，浏览器底层连接已断开时 `pages` 仍可访问返回缓存列表，`is_alive` 错误返回 `True`，`ensure_alive` 走快速路径不触发重启，后续 `add_cookies` 反复抛 `"Connection closed while reading from the driver"`，实时搜索持续报 503。修复后 `is_alive` 改用 `await self._context.cookies()`（真异步 CDP 调用），连接断开时抛异常返回 `False`，`ensure_alive` 触发重启。

**判断信号（review 触发条件）**：
- `grep "def is_alive\|def ensure_alive" <file>` 命中后检查方法体内是否用同步 property（`self._context.pages` / `self._client.is_connected`）
- `grep "async def is_alive" <file>` 但方法体内无 `await` → 违规（伪异步）
- `grep "\.pages\b\|\.is_connected\b\|\.is_closed\b"` 在 `is_alive` 方法内 → 检查是否为同步 property
- `is_alive` 返回值依赖 `len(result) > 0` → 违规（刚重启时结果为空会误判）
- `is_alive` 捕获异常后返回 `True` → 违规（异常即不可用）


---

