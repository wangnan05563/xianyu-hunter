# 后台系统日志分析报告（Logs Review）

> 生成时间：2026-08-20 15:49:34  
> 分析模式：**全量**（无基线，首次运行）  
> 日志文件：`run.stdout.log`

## 一、日志摘要（元信息）

| 指标 | 数值 |
|------|------|
| 总行数 | 18,211 |
| 成功解析（WARNING/ERROR/CRITICAL） | 2,942 |
| WARNING 原始行数 | 2,907 |
| ERROR 原始行数 | 35 |
| CRITICAL 原始行数 | 0 |
| 去重后的问题模板数 | 57 |
| 异常堆栈（traceback）数 | 35 |
| WARNING 模板数 | 53 |
| ERROR 模板数 | 4 |

**整体结论（根因故事）**：系统在 2026-08-14 17:35 启动后，会话即处于失效状态（`_m_h5_tk` 缺失/过期），而目标站点 `goofish.com` 在运行环境内 DNS 解析持续失败（`net::ERR_NAME_NOT_RESOLVED`），导致 token 刷新与自动重登永远无法成功，形成‘失效→重试→失败’死循环。叠加磁盘使用率达 93%（`data/chromadb` 占 4.1G）引发的 `database or disk is full` 写失败，**采集链路已连续 6 天零有效产出**。日志层面同时存在严重的噪声问题（business_kpi 分母为 0 刷屏 648 次、Cookie 注入冗余对、INFO 跳过日志数千行），以及级别误判（Tailscale 未配置被记为 ERROR 并打印 38 行堆栈）。

## 二、WARNING 分类表（全量，按频率/优先级）

| ID | 级别 | 类型 | 优先级 | 次数 | 30min峰 | 来源模块:函数:行 | 消息模板（归一化） |
|----|------|------|--------|------|---------|----------------------|------------------------|
| log-004 | WARNING | warning_noise | low | 648 | 7 | xianyu_hunter.web.routes.business_kpi:_compute_business_kpi:276 | [business_kpi] 抢单成功率分母为 {n}：近 {n} 天无订单记录，可能抢单未触发或订单数据采集异常 |
| log-025 | WARNING | warning_noise | low | 306 | 100 | xianyu_hunter.modules.collection_service:_collect_detail_and_seller:766 | 官方采集 detail 返回 None: item={hex}, failure_reason=network_transient |
| log-055 | WARNING | warning_noise | low | 300 | 100 | xianyu_hunter.modules.collector._detail:_log_detail_failure:1024 | 详情页 {hex} 采集失败（网络瞬时故障）: Page.goto: net::ERR_NAME_NOT_RESOLVED at https://www.goofish.com/i |
| log-009 | WARNING | warning_noise | low | 246 | 36 | xianyu_hunter.infra.browser:add_cookies:475 | add_cookies: 以下 Cookie 注入后未落地，尝试显式属性重试: ['xlly_s'] |
| log-010 | WARNING | warning_noise | low | 246 | 36 | xianyu_hunter.infra.browser:add_cookies:492 | add_cookies: 显式属性重试后仍缺失: ['xlly_s'] |
| log-054 | WARNING | warning_noise | low | 133 | 31 | xianyu_hunter.modules.collector._search:_ensure_fresh_m5tk:671 | 刷新 _m_h5_tk token 失败: Page.goto: net::ERR_NAME_NOT_RESOLVED at https://www.goofish.com/ |
| log-045 | WARNING | warning_noise | low | 96 | 32 | xianyu_hunter.infra.browser:_retry_missing_cookies:640 | add_cookies: 以下 Cookie 注入后未落地，尝试显式属性重试: ['_m_h5_tk', '_m_h5_tk_enc', 'mtop_partitioned_det |
| log-046 | WARNING | warning_noise | low | 96 | 32 | xianyu_hunter.infra.browser:_retry_missing_cookies:657 | add_cookies: 显式属性重试后仍缺失: ['_m_h5_tk', '_m_h5_tk_enc', 'mtop_partitioned_detect', 'xlly_s'] |
| log-052 | WARNING | warning_noise | low | 96 | 19 | xianyu_hunter.modules.collector._search:search:763 | 搜索失败 联想 DDR4 {n} 32G（网络瞬时故障）: Page.goto: net::ERR_NAME_NOT_RESOLVED at https://www.goofish |
| log-021 | WARNING | warning_noise | low | 74 | 25 | xianyu_hunter.modules.collector._search:_unroute_search_api:1472 | page.unroute 超时（后台继续清理，不影响 DOM 解析） |
| log-002 | WARNING | warning_noise | medium | 65 | 2 | xianyu_hunter.modules.cookie_rotator:invalidate_layer:228 | Cookie 层 session 已标记失效 (manual=False) |
| log-003 | WARNING | state_check | high | 65 | 2 | xianyu_hunter.modules.login_orchestrator:_invalidate_session_layer_after_renew_fail:329 | Token 续期失败（第 {n} 次），session 层已标记失效 |
| log-053 | WARNING | warning_noise | low | 60 | 12 | xianyu_hunter.modules.collector._search:search:763 | 搜索失败 联想 DDR4 {n} 16G（网络瞬时故障）: Page.goto: net::ERR_NAME_NOT_RESOLVED at https://www.goofish |
| log-022 | WARNING | retry_failure | high | 44 | 24 | xianyu_hunter.modules.collector._search:_collect_dom_cards:963 | DOM 回退查找卡片超时，放弃: keyword=联想 DDR4 {n} 16G |
| log-011 | WARNING | warning_noise | low | 43 | 6 | xianyu_hunter.modules.collector._detail:_mark_detail_session_invalid:217 | 详情页 {hex} 检测到会话失效：首页标题 title=闲鱼 - 闲不住？上闲鱼！（cookie 可能失效被重定向到首页，主动返回 None），后续任务将暂停 |
| log-012 | WARNING | warning_noise | low | 43 | 5 | xianyu_hunter.modules.collection_service:_collect_detail_and_seller:766 | 官方采集 detail 返回 None: item={hex}, failure_reason=home_title_redirect |
| log-013 | WARNING | warning_noise | low | 39 | 5 | xianyu_hunter.modules.collector._detail:_log_detail_failure:1024 | 详情页 {hex} 采集失败（Playwright 超时）: Page.goto: Timeout 30000ms exceeded. |
| log-031 | WARNING | retry_failure | high | 38 | 15 | xianyu_hunter.modules.collector._search:_collect_dom_cards:963 | DOM 回退查找卡片超时，放弃: keyword=联想 DDR4 {n} 32G |
| log-014 | WARNING | warning_noise | medium | 35 | 4 | xianyu_hunter.modules.collection_service:_refresh_token_and_retry_detail:522 | _m_h5_tk 刷新后重试仍失败 item={hex}, reason=playwright_timeout，尝试从 cookie_store 重新注入完整 cookie |
| log-032 | WARNING | warning_noise | low | 35 | 11 | xianyu_hunter.modules.collector._search:_retry_search_after_api_auth_failure:1378 | token/签名校验失败后 API 重试导航失败: Page.goto: Timeout 20000ms exceeded. |
| log-033 | WARNING | retry_failure | high | 30 | 10 | xianyu_hunter.modules.collector._search:_collect_dom_cards:963 | DOM 回退查找卡片超时，放弃: keyword=hynix 海力士 DDR4 {n} 16G |
| log-006 | WARNING | warning_noise | medium | 26 | 2 | xianyu_hunter.infra.browser:add_cookies:475 | add_cookies: 以下 Cookie 注入后未落地，尝试显式属性重试: ['_m_h5_tk_enc', 'mtop_partitioned_detect', 'xlly_ |
| log-007 | WARNING | warning_noise | medium | 26 | 2 | xianyu_hunter.infra.browser:add_cookies:492 | add_cookies: 显式属性重试后仍缺失: ['_m_h5_tk_enc', 'mtop_partitioned_detect', 'xlly_s'] |
| log-016 | WARNING | warning_noise | low | 20 | 20 | xianyu_hunter.modules.worker:_finalize_run:1086 | [Task t68bc149b] 写入搜索事件失败: (sqlite3.OperationalError) database or disk is full |
| log-017 | WARNING | warning_noise | low | 12 | 12 | xianyu_hunter.modules.worker:_finalize_run:1086 | [Task teb721570] 写入搜索事件失败: (sqlite3.OperationalError) database or disk is full |
| log-018 | WARNING | warning_noise | low | 12 | 12 | xianyu_hunter.modules.worker:_finalize_run:1086 | [Task te8f98598] 写入搜索事件失败: (sqlite3.OperationalError) database or disk is full |
| log-001 | WARNING | warning_noise | medium | 10 | 1 | xianyu_hunter.modules.token_renewer:_mark_session_expired:249 | 无法获取 _m_h5_tk，可能未登录 |
| log-020 | WARNING | warning_noise | medium | 5 | 4 | xianyu_hunter.modules.collector._search:_retry_search_after_api_auth_failure:1378 | token/签名校验失败后 API 重试导航失败: Page.goto: Timeout 15000ms exceeded. |
| log-041 | WARNING | warning_noise | medium | 5 | 2 | xianyu_hunter.infra.browser:add_cookies:475 | add_cookies: 以下 Cookie 注入后未落地，尝试显式属性重试: ['_m_h5_tk', '_m_h5_tk_enc', 'mtop_partitioned_det |
| log-042 | WARNING | warning_noise | medium | 5 | 2 | xianyu_hunter.infra.browser:add_cookies:492 | add_cookies: 显式属性重试后仍缺失: ['_m_h5_tk', '_m_h5_tk_enc', 'mtop_partitioned_detect'] |
| log-056 | WARNING | warning_noise | low | 5 | 5 | xianyu_hunter.modules.token_renewer:_do_renew:345 | _m_h5_tk 续期失败（回调返回 False） |
| log-019 | WARNING | warning_noise | medium | 4 | 2 | xianyu_hunter.modules.cookie_rotator:invalidate_all:242 | 所有 Cookie 层已标记失效 |
| log-024 | WARNING | warning_noise | medium | 4 | 4 | xianyu_hunter.modules.collector._detail:_log_detail_failure:1024 | 详情页 {hex} 采集失败（网络瞬时故障）: Page.goto: net::ERR_TIMED_OUT at https://www.goofish.com/item?id={ |
| log-036 | WARNING | warning_noise | medium | 4 | 3 | xianyu_hunter.modules.collector._search:_goto_timeout_indicates_session_invalid:1341 | goto 超时且页面已跳转至非搜索页，判定为会话失效: url=https://www.goofish.com/ |
| log-037 | WARNING | warning_noise | medium | 4 | 3 | xianyu_hunter.modules.collector._search:_collect_dom_cards:930 | 页面已跳转至非搜索页，跳过 DOM 回退: url=https://www.goofish.com/ |
| log-023 | WARNING | warning_noise | medium | 3 | 3 | xianyu_hunter.modules.collection_service:_collect_detail_and_seller:766 | 官方采集 detail 返回 None: item={hex}, failure_reason=playwright_timeout |
| log-043 | WARNING | warning_noise | medium | 3 | 1 | xianyu_hunter.infra.browser:add_cookies:475 | add_cookies: 以下 Cookie 注入后未落地，尝试显式属性重试: ['_m_h5_tk', '_m_h5_tk_enc'] |
| log-044 | WARNING | warning_noise | medium | 3 | 1 | xianyu_hunter.infra.browser:add_cookies:492 | add_cookies: 显式属性重试后仍缺失: ['_m_h5_tk', '_m_h5_tk_enc'] |
| log-026 | WARNING | warning_noise | medium | 2 | 2 | xianyu_hunter.modules.collector._detail:_log_detail_failure:1024 | 详情页 {hex} 采集失败（网络瞬时故障）: Page.goto: net::ERR_NETWORK_CHANGED at https://www.goofish.com/ite |
| log-047 | WARNING | warning_noise | medium | 2 | 1 | xianyu_hunter.infra.browser:_retry_missing_cookies:640 | add_cookies: 以下 Cookie 注入后未落地，尝试显式属性重试: ['_m_h5_tk', '_m_h5_tk_enc', 'xlly_s'] |
| log-048 | WARNING | warning_noise | medium | 2 | 1 | xianyu_hunter.infra.browser:_retry_missing_cookies:657 | add_cookies: 显式属性重试后仍缺失: ['_m_h5_tk', '_m_h5_tk_enc', 'xlly_s'] |
| log-027 | WARNING | warning_noise | medium | 1 | 1 | xianyu_hunter.modules.collector._detail:_populate_seller_info_labels:659 | 详情页 {hex} 卖家信息标签未出现（5s 超时），尝试继续提取 |
| log-028 | WARNING | warning_noise | medium | 1 | 1 | xianyu_hunter.modules.collection_service:_refresh_token_and_retry_detail:522 | _m_h5_tk 刷新后重试仍失败 item={hex}, reason=home_title_redirect，尝试从 cookie_store 重新注入完整 cookie |
| log-029 | WARNING | warning_noise | medium | 1 | 1 | xianyu_hunter.modules.collection_service:_log_cookie_diagnostics:581 | 会话失效诊断 item={hex}, cookie总数={n}, 身份cookie[cookie2=存在, sgcookie=存在, unb=存在]，若身份cookie均存在但仍失 |
| log-030 | WARNING | warning_noise | medium | 1 | 1 | xianyu_hunter.modules.collector._detail:_dump_seller_dom_for_debug:1227 | [P2 调试] 卖家 {num} 提取异常（on_sale={n}, sold={n}）已 dump 到 logs\seller_dom_2565537061.txt |
| log-034 | WARNING | warning_noise | medium | 1 | 1 | xianyu_hunter.modules.worker:_execute_search_with_timeout:541 | [Task t68bc149b] 搜索超时（90秒），自动暂停任务 |
| log-035 | WARNING | warning_noise | medium | 1 | 1 | xianyu_hunter.modules.worker:_execute_search_with_timeout:541 | [Task te8f98598] 搜索超时（90秒），自动暂停任务 |
| log-038 | WARNING | warning_noise | medium | 1 | 1 | xianyu_hunter.modules.worker:_search_phase:327 | [Task teb721570] 闲鱼会话失效（RGV587_ERROR），自动暂停任务，请重新登录闲鱼 |
| log-039 | WARNING | warning_noise | medium | 1 | 1 | xianyu_hunter.modules.cookie_rotator:invalidate_layer:228 | Cookie 层 identity 已标记失效 (manual=False) |
| log-040 | WARNING | warning_noise | medium | 1 | 1 | xianyu_hunter.modules.cookie_rotator:invalidate_layer:235 | Cookie 层 session 级联失效 (manual=False) |
| log-049 | WARNING | warning_noise | medium | 1 | 1 | xianyu_hunter.modules.collector._search:search:763 | 搜索失败 联想 DDR4 {n} 32G（网络瞬时故障）: Page.goto: Timeout 20000ms exceeded. |
| log-050 | WARNING | warning_noise | medium | 1 | 1 | xianyu_hunter.modules.collector._search:search:763 | 搜索失败 联想 DDR4 {n} 16G（网络瞬时故障）: Page.goto: Timeout 15000ms exceeded. |
| log-051 | WARNING | warning_noise | medium | 1 | 1 | xianyu_hunter.modules.worker:_execute_search_with_timeout:541 | [Task teb721570] 搜索超时（90秒），自动暂停任务 |

> **人工复核说明**：自动分类器将上表多数行标记为 `warning_noise / low`。经人工复核，下列行已上调严重程度（详见第四节）：
> - `database or disk is full`（log-016/017/018）→ **Critical / P0（F1，资源/磁盘写失败，数据丢失风险）**；
> - 全部 `ERR_NAME_NOT_RESOLVED` / `network_transient` 行（log-025/055/054/052/053/024 等）→ **High / P0（F2，站点 DNS 持续不可达，非瞬时故障）**；
> - `Token 续期失败…session 层已标记失效`（log-003）→ **High / P1（F3，会话失效死循环）**；
> - `DOM 回退查找卡片超时，放弃`（log-022/031/033）→ **High / P1（F6，下游于 F2/F3）**。
>
> 其余 `low` 行（business_kpi 刷屏、xlly_s 缺失、page.unroute、INFO 跳过日志等）确为噪声，按降频/降级处理即可，无业务副作用。

## 三、ERROR 与异常堆栈

| ID | 级别 | 类型 | 优先级 | 次数 | 来源模块:函数:行 | 消息模板（归一化） |
|----|------|------|--------|------|----------------------|------------------------|
| log-008 | ERROR | state_check | high | 26 | 1 | xianyu_hunter.modules.login_orchestrator:_maybe_trigger_auto_relogin:395 | 续期连续失败 {n} 次，cookie 同步无效，触发自动重登 |
| log-005 | ERROR | state_check | high | 5 | 1 | xianyu_hunter.web.startup:_run_tunnel_autostart:771 | 内网穿透自动启动失败: 请先打开并登录 Tailscale，然后重新启动隧道 |
| log-015 | ERROR | state_check | high | 3 | 1 | xianyu_hunter.modules.chatbot.kb_refresh_scheduler:_refresh_job_sync:98 | 知识库定时更新超时（>600s）: |
| log-057 | ERROR | state_check | high | 1 | 1 | xianyu_hunter.modules.token_renewer:_handle_renew_result:272 | 连续 {n} 次续期失败，触发重新登录 |

**异常堆栈统计**：共 35 处 ERROR 后附带 traceback，其中：
- `内网穿透自动启动失败`（Tailscale RuntimeError）：5 次，每次 38 行完整堆栈（F7，级别误判+堆栈噪声）。
- `续期连续失败…触发自动重登`：27 次，无附带堆栈（仅 ERROR 行，F3）。
- `知识库定时更新超时（>600s）`：3 次，无附带堆栈（F8）。
- `连续 N 次续期失败，触发重新登录`：1 次（F3）。

## 四、关键发现与修复方案（严重程度 / 优先级 / 策略）

> 严重程度：Critical > High > Medium > Low；优先级：P0（立即）> P1（本周）> P2（迭代）> P3（择机）。

### F1 · 磁盘/数据库写失败：database or disk is full（资源/磁盘泄漏）

- **严重程度**：`Critical`　**优先级**：`P0`　**类别**：资源泄漏 / 数据丢失风险
- **影响范围**：worker:_finalize_run / xianyu.db（events 表）；根因在磁盘 93% + chromadb 4.1G
- **证据**：WARNING 共 44 次（2026-08-15 21:45–22:14 集中爆发，3 个任务轮流失败）；磁盘 D: 已用 93%（剩 9.3G/131G）；data/ 共 4.4G，其中 data/chromadb 占 4.1G。
- **根因**：SQLite 写搜索事件时返回 SQLITE_FULL。根因是磁盘空间被 chromadb 向量库持续增长吃满、缺乏保留/压缩策略；写失败导致搜索事件（遥测）被静默丢弃。
- **修复策略**：配置 + 监控 + 代码
- **具体建议**：
  - ① 运维：立即回收磁盘（清理 chromadb 中已下架商品的过期向量 / 启用 chromadb 保留策略与 compaction；临时扩容 D:）。
  - ② 代码：事件写入失败不应进入无限重试循环——改为‘本地队列 + 丢弃告警’，并记录一次 ERROR 级告警（当前是 WARNING 且每任务每轮都打，反而淹没真正信号）。
  - ③ 监控：新增磁盘使用率监控，≥85% 即告警（见 F10）。
  - ④ 排查 xianyu.db 是否开启 WAL + 自动 checkpoint，避免 WAL/rollback 临时文件加剧空间压力。

### F2 · 目标站点 DNS 持续解析失败（net::ERR_NAME_NOT_RESOLVED）——采集链路整体不可用

- **严重程度**：`High`　**优先级**：`P0`　**类别**：环境/网络（核心阻断）
- **影响范围**：collection_service / collector._detail / collector._search / token_renewer
- **证据**：WARNING 约 895 次（network_transient + 详情页/搜索/token 刷新均报 ERR_NAME_NOT_RESOLVED），30 分钟窗口内峰值达 100 次；与 F4 叠加导致 6 天零有效采集。
- **根因**：goofish.com 在运行环境内无法解析（DNS 失败），并非偶发瞬时故障。所有依赖导航/接口的请求全部失败，采集、token 刷新、自动重登全部被阻断。
- **修复策略**：代码 + 监控
- **具体建议**：
  - ① 代码：将‘瞬时网络错误’与‘DNS 解析失败（持续）’区分——连续 K 次 ERR_NAME_NOT_RESOLVED 即判定‘站点不可达’，停止逐条 item/keyword 的重试轰炸，改为单次明确告警 + 暂停采集。
  - ② 增加启动期 DNS/连通性健康检查（解析 www.goofish.com），不通则启动即给出可操作提示而非运行 6 天后才发现。
  - ③ 监控：站点不可达持续 >5min 触发 P0 告警并通知运维/用户。
  - ④ 若为沙箱/无外网环境，应在配置中显式关闭采集并在 UI 提示，而非持续刷 WARNING。

### F3 · 会话永久失效 / Token 续期失败死循环（state_check）

- **严重程度**：`High`　**优先级**：`P1`　**类别**：状态一致性（业务流程中断）
- **影响范围**：login_orchestrator / token_renewer / cookie_rotator / worker
- **证据**：WARNING ‘Token 续期失败（第 N 次），session 层已标记失效’ 75 次；ERROR ‘续期连续失败…触发自动重登’ 27 次；token_renewer 日志显示‘会话失效状态未恢复，第 8 次检查后退避 600s’；自 2026-08-14 17:35 起至 2026-08-20 15:28 持续 6 天。
- **根因**：_m_h5_tk 自启动即缺失/过期，自动重登因 F2（DNS 不通）无法完成，形成‘失效→重试→失败→再失效’循环；worker 每轮均‘跳过等待续期’，但续期永远不会成功。
- **修复策略**：代码 + 监控
- **具体建议**：
  - ① 代码：自动重登增加冷却/上限——连续 N 次失败后停止自动重登，改为单次高优告警 + 引导用户手动重登（notifier 已支持 system.error 推送，应在此触发，而非仅 DEBUG）。
  - ② 当会话已知失效时，worker 进入‘静默等待’而非每轮都打 INFO‘跳过本轮’（见 F11）。
  - ③ 监控：会话失效持续 >30min 触发告警，提示用户重新登录。

### F10 · 监控告警机制缺失（系统性）

- **严重程度**：`High`　**优先级**：`P1`　**类别**：可观测性
- **影响范围**：全局
- **证据**：日志中存在磁盘写满（F1）、站点不可达（F2）、会话失效 6 天（F3）等 P0/P1 事件，但全程仅靠被动刷 WARNING/ERROR，无任何阈值告警/收敛，问题潜伏 6 天无人知。
- **根因**：缺乏指标化监控与告警收敛：重复异常被当作独立事件刷屏，真正需要人工介入的 P0 反而被噪声淹没。
- **修复策略**：监控
- **具体建议**：
  - ① 磁盘使用率 ≥85% 告警（F1）。
  - ② 站点不可达持续 >5min 告警（F2）。
  - ③ 会话失效持续 >30min 告警 + 引导重登（F3）。
  - ④ 同类 WARNING 做时间窗聚合（如 5min 内同模板 >N 条则合并为一条摘要告警），避免刷屏。
  - ⑤ 关键指标（采集成功率、续期成功率）接入 dashboard。

### F6 · DOM 回退查找卡片超时放弃（retry_failure，下游于 F2/F3）

- **严重程度**：`Medium`　**优先级**：`P1`　**类别**：重试耗尽（性能浪费）
- **影响范围**：collector._search:_collect_dom_cards:963
- **证据**：WARNING 共 112 次（按 keyword 拆分多条），每次等待 30s 超时后放弃。
- **根因**：会话失效后页面被重定向到闲鱼首页，DOM 回退必然失败；仍每次等待满 30s 超时，浪费时间且刷 WARNING。
- **修复策略**：代码
- **具体建议**：
  - ① 进入 DOM 回退前先校验当前 URL 是否为搜索结果页，已被重定向到首页则直接跳过（日志降为 DEBUG）。
  - ② 会话已知失效时完全跳过 DOM 回退（与 F3/F11 联动）。
  - ③ 控制单 keyword 的 DOM 回退次数上限，避免重复超时。

### F7 · 内网穿透（Tailscale）启动失败被记为 ERROR 并打印 38 行堆栈

- **严重程度**：`Medium`　**优先级**：`P2`　**类别**：级别误判 + 堆栈噪声
- **影响范围**：web.startup:_run_tunnel_autostart:771/1541、tunnel_service/TailscaleProvider
- **证据**：ERROR 5 次，每次附带 38 行完整 traceback；异常为 RuntimeError('请先打开并登录 Tailscale…')。
- **根因**：tunnel.auto_start=True 但 Tailscale 未安装/未登录，属‘可预期的未配置状态’，却被 logger.error + 抛栈，误导为系统故障。
- **修复策略**：代码（降级 + 抑制堆栈）
- **具体建议**：
  - ① 该情况降级为 WARNING，且仅记录 message，不打印完整 traceback（使用 logger.warning(...) 而非 error+exception）。
  - ② 尊重配置开关：auto_start 关闭或 provider 不可用时静默跳过。
  - ③ 若确需告警，合并为单次并提示如何启用，而非每次启动都打。

### F8 · 知识库定时更新超时 >600s（performance）

- **严重程度**：`Medium`　**优先级**：`P2`　**类别**：性能瓶颈
- **影响范围**：chatbot.kb_refresh_scheduler:_refresh_job_sync:98
- **证据**：ERROR 3 次（‘知识库定时更新超时（>600s）’）。
- **根因**：KB 刷新（embedding/重建索引）耗时超 600s，可能与 chromadb 体积膨胀（4.1G，F1）或单批过大、无进度日志有关。
- **修复策略**：代码 + 性能
- **具体建议**：
  - ① 增加分片/增量刷新，避免全量重建；记录每阶段耗时（计时日志）。
  - ② 设定硬超时并告警，超时不阻塞主进程。
  - ③ 与 F1 联动：审计 chromadb 向量保留策略，清理僵尸向量以缩短刷新时间。

### F4 · business_kpi 分母为 0 日志高频刷屏（warning_noise）

- **严重程度**：`Low`　**优先级**：`P2`　**类别**：日志噪声
- **影响范围**：web.routes.business_kpi:_compute_business_kpi:276
- **证据**：WARNING 648 次（全量第一），每 ~5 分钟缓存预热触发一次。
- **根因**：‘近 30 天无订单记录’属正常初始态，却被当作 WARNING 每次计算都打印，无副作用但严重淹没日志。
- **修复策略**：代码（降频/降级）
- **具体建议**：
  - ① 仅在‘分母从非 0 变为 0’或状态变化时记录一次；或用冷却时间（如 6h 一条）限制。
  - ② 改为 DEBUG 或仅在确实有异常（抢单已触发但订单采集落空）时 WARNING。

### F5 · Cookie 注入未落地日志冗余且含无害项（warning_noise）

- **严重程度**：`Low`　**优先级**：`P3`　**类别**：日志噪声 + 误报
- **影响范围**：infra.browser:add_cookies:475/492、_retry_missing_cookies:640/657
- **证据**：add_cookies 相关 WARNING 共 756 次；同一调用必成对打印‘尝试显式属性重试’+‘显式属性重试后仍缺失’；其中 xlly_s 缺失为无害（追踪 cookie，非身份 cookie）。
- **根因**：每次注入都打两条；xlly_s 这种已知无害 cookie 被当异常告警，制造噪声并掩盖真正重要的 _m_h5_tk/_m_h5_tk_enc 缺失。
- **修复策略**：代码（合并/过滤）
- **具体建议**：
  - ① 将‘重试’与‘仍缺失’合并为单条结构化日志（含重试结果）。
  - ② 维护‘已知无害 cookie 白名单’（xlly_s 等），命中则不告警。
  - ③ 仅当关键身份 cookie（_m_h5_tk*、cookie2、unb 等）缺失时才 WARNING，并关联 F3 会话失效。

### F9 · 详情页会话失效检测（home_title_redirect）与冗余 INFO 刷屏

- **严重程度**：`Low`　**优先级**：`P3`　**类别**：日志噪声 / 冗余
- **影响范围**：collector._detail:_mark_detail_session_invalid、worker:_search_phase/_dedup_and_limit
- **证据**：WARNING ‘详情页检测到会话失效（home_title_redirect）’ 43 次；INFO ‘[Task X] 会话已失效…跳过本轮搜索’ + ‘全部已看过，本轮跳过’ 每 ~1–2 分钟成对出现，6 天累计数千行。
- **根因**：会话已知失效时，仍对每个 detail/item 走完整‘检测→返回 None’流程并打 INFO，制造海量冗余日志，掩盖真实信号。
- **修复策略**：代码（去重/降级）
- **具体建议**：
  - ① 会话失效状态做全局缓存，失效期间 detail/搜索直接短路返回，避免逐条 goto 与重复 INFO。
  - ② ‘跳过本轮/全部已看过’降级为 DEBUG，或按任务每 N 分钟合并一条。
  - ③ page.unroute 超时（74 次）同样降级为 DEBUG。

### F11 · 日志质量：未格式化的 %s 占位符

- **严重程度**：`Low`　**优先级**：`P3`　**类别**：日志质量
- **影响范围**：web.startup:_restore_session_on_startup:1083
- **证据**：启动日志出现字面量 ‘启动会话恢复成功: user_id=%s’，%s 未被替换——说明该 logger 用 %-style 但参数缺失（或混用 .format）。
- **根因**：日志调用参数不匹配，输出失真，影响问题定位。
- **修复策略**：代码
- **具体建议**：
  - ① 修正该 logger 调用，补齐参数或改为 f-string/正确 % 参数。
  - ② 建议统一日志格式化风格，避免 % 与 {} 混用。

## 五、监控告警完善建议（汇总）

| 监控项 | 触发条件 | 级别 |
|--------|----------|------|
| 磁盘使用率 | ≥85%（当前 93%） | P0 |
| 站点不可达 | goofish.com DNS/连通性失败持续 >5min | P0 |
| 会话失效 | _m_h5_tk 缺失持续 >30min | P1 |
| 知识库刷新 | 单次 >600s | P1 |
| 同类日志刷屏 | 5min 内同模板 WARNING >20 条 → 聚合为单条摘要告警 | P2 |
| 采集成功率 | 滚动窗口成功率 <阈值 | P1 |

## 六、凭据安全检查

- 扫描 `token/password/secret/api_key/bearer/长 hex` 等模式：**未发现明文凭据泄露**。
- 发现 1 处日志质量问题：`web.startup:_restore_session_on_startup` 打印字面量 `user_id=%s`（% 占位符未替换，参数缺失/格式化风格混用），见 F11。不影响安全，但影响排障。
- 报告中已对所有 item id、task id、req id 做 `{hex}/{task}/{req}` 归一化脱敏。

## 七、基线快照状态

- 本次为**全量模式**（配置 `baseline_log` 为空），未做增量对比。
- 建议：将本轮作为基线快照（复制 `run.stdout.log` 至 `logs/baselines/`），下次运行切换增量模式，仅关注新增 WARNING/ERROR，量化优化效果。

## 八、Phase 5：修复与验证结果（2026-08-20）

### 已实施的代码级修复（7 项）

| 发现 | 文件 | 改动 |
|------|------|------|
| F11 | `web/routes/unified_login.py:1093/1096` | `%s` → f-string（loguru 拦截 stdlib 日志时 %-style 原样输出，值被吞） |
| F7 | `web/startup.py:_run_tunnel_autostart` | `logger.exception`→`logger.warning`（抑制 38 行堆栈）；DB 事件 `level: err`→`warning` |
| F4 | `web/routes/business_kpi.py:_compute_business_kpi` | 分母为 0 仅“有订单→无订单”状态切换时告警一次（函数属性 static var，无硬编码冷却） |
| F5 | `infra/browser.py:_retry_missing_cookies` | 合并“尝试重试+仍缺失”两条为一条；新增 `_BENIGN_COOKIES={"xlly_s"}` 无害白名单降级 DEBUG |
| F6 | `modules/collector/_search.py:_collect_dom_cards` | 会话已知失效（`last_session_invalid`）时直接短路跳过 DOM 回退，消除 30s 空等超时 |
| F8 | `infra/yaml_config.py` + `config/config.yaml` + `modules/chatbot/kb_refresh_scheduler.py` | 超时配置化（新增 `kb.refresh_timeout_sec`，默认 600→**1800s**）；超时降级为 WARNING 且不误报失败（后台继续跑，以版本状态为准）；**修复后台失败事件丢失**（`_refresh_job` 吞异常导致 `CHATBOT_KB_FAILED` 永不发布，现改为本地发布）；阶段计时日志 |
| F9 | `_search.py` page.unroute 超时、`worker.py:308/342` | 均降级为 DEBUG（会话失效跳过/全部已看过为常态轮空） |

### 未在代码层处理的项
- **F1 / F2 / F10**：环境/运维/监控基础设施项（磁盘清理、chromadb 保留策略、网络确认、监控告警），需你侧处理，见第四节具体建议。
- **F3**：`login_orchestrator.py` 已具备双层冷却（10min/30min）+ 失败阈值 + `LOGIN_EXPIRED` 事件通知引导手动重登，覆盖报告建议；当前死循环根因是环境（F2 DNS）+ 需要手动重登，非代码缺陷。

### F8 根因补充（2026-08-20 处理时定位）
`incremental_update` 是**伪增量**：对全语料算全局 `doc_hash`，任一文件变化即走 `_do_build` **全量重建**（`embed_batch` 全部 chunk → `clear_collection` → 全量 upsert + 导出 400-600MB 快照）。`doc_paths` 含整个 `backend/xianyu_hunter/`（216 py）+ `docs/`（150 md），本地 CPU 模型 embedding 上万 chunk 必然 >600s → 超时误报。
- 先已修复"超时语义 + 超时值可配"（`kb.refresh_timeout_sec` 1800s + 超时降级 WARNING，见上表 F8 行）。
- **根治已实施（文件级增量）**：`incremental_update` 改为按 `{source_file: content_md5}` 文件指纹对比，只对**变更/新增文件**重新分块 + embedding，对**已移除文件**按 `source_file` 从向量库删除，不清空集合（复用已有 `vector_store.delete_by_source`）。改动涉及：
  - `db_models.py`：`chatbot_kb_versions` 新增 `file_fingerprints` 列
  - `repo_chatbot.py`：老库幂等 ALTER 迁移 + `create_kb_version`/序列化支持指纹
  - `kb_manager.py`：`_scan_and_chunk_with_fingerprints`（单次读盘算指纹）、`incremental_update` 文件级 diff、`_do_build` 合并式写入（`full_rebuild` 仍保留全量路径）、回滚沿用目标版本指纹、旧版本无指纹时降级全量
  - 新测试 `tests/test_kb_manager_incremental.py`：4 用例覆盖"首次全量 / 无变化跳过 / 单文件变更只重建该文件 / 文件删除按 source 清理"，全部通过
  - 验证：迁移老库补列 OK、指纹读写 OK、chatbot 相关回归 84 项通过
  - 效果：单文件改动从"分钟级全量重 embedding"降为"秒级单文件处理"
- **产品级选项**：若客服不需要 backend 源码问答，可把 `doc_paths` 收窄到 `docs/`，全量重建更快（非必需，增量已解决）。

### 验证结果
- **定向测试**：234 通过 / 0 失败（login_orchestrator、unified_login、unroute、tunnel、worker、cookie 注入、collector 等覆盖全部改动模块）。
- **全量 `pytest tests/`**：**1729 通过 / 1 失败 / 3 跳过**（396s，`-o addopts= -p no:cov` 干净运行；首次带 coverage 的运行因沙箱 `safe-delete` 拦截 `coverage.combine()` 的 `os.remove` 产生 INTERNALERROR，非测试失败）。
- **唯一失败项为既有环境问题**：`tests/test_browser_import_integration.py::test_import_multi_profile_e2e` 报 `ValueError: the environment variable is longer than 32767 characters` —— Windows 环境变量长度上限（32767 字符）被某已装产品注入的超长 `ACC_PRODUCT_CONFIG_V3` 变量触发，与本轮 7 项修复无关（相关模块定向测试全部通过）。
- **硬约束（modified_only）**：无新增违例（未引入硬编码凭据/冷却/重试计数）。既有假阳性 `unified_login.py:791/850/928` 的 `max_retries=` 为函数入参非硬编码，未改动。
- **语法检查**：7 个改动文件 `py_compile` 全部通过。

---
*本报告由 logs-review 技能生成，问题分类依据 `config.yaml` 的 side_effect / classify 规则，部分高频噪声经人工复核已上调严重程度（如 F2 站点不可达、F3 会话死循环）。*