# 优化建议清单（基于 2026-10-31 全量 API 压测数据）

> 每条给出：**具体优化内容** → **证据**（实测数字 + 源码位置） → **量化预期收益** → **优先级** → **验证方式**。
> 收益口径说明：下文所有「目标值」以本次实测的**同类廉价接口**为地板参照 —— `GET /api/anticrawl/fingerprint` 9.0 ms、`GET /api/notifier/quiet-hours` 8.4 ms、`GET /api/anticrawl/freq/delay` 7.4 ms（单用户基线，纯配置/内存读取）。凡「缓存命中」类预测均按该地板 + 少量序列化开销（10~20 ms）估算，未采用无参照的外推。
> 优先级 = 影响面（该接口在真实控制台中的调用频率 × 劣化幅度）÷ 实现成本。

## 0. 汇总表（按优先级）

| 编号 | 优化项 | 优先级 | 关键指标预期变化 | 成本 |
|---|---|---|---|---|
| B1 | 缓存单飞（single-flight） | **高** | 长跑混合场景 avg 200.5 → ≤80 ms；长跑整体 P95 544.5 → ≤250 ms | 低（`web/cache.py` 约 20 行） |
| C2 | `/api/auth/me` 去重复文件解析 | **高** | avg 152.6 → ≤50 ms（长跑 414.3 → ≤120 ms） | 低 |
| C4 | 反爬策略探测降本 + 缓存 | **高** | avg 1 094.7 → ≤30 ms；96 并发 2 511.8 → ≤100 ms | 低 |
| D1 | 慢同步接口独立线程池 | **高** | 48/96 并发轻组 P95 2 064/3 893 → ≤1 000 ms；缺陷率 2.03/3.17% → <0.5% | 中 |
| A2 | `eval.*` 事件查询下推 | **高** | `/api/evaluations` avg 195.9 → ≤60 ms；P99 858 → ≤250 ms | 中 |
| B2 | 慢接口纳入 TTL 缓存（raw/share/snapshots/preview） | **高** | 轻组基线 avg 50.9 → ≤25 ms | 低 |
| A4 | `maintenance/status` 计数降本 | **高** | 单发 1.6 s → ≤200 ms；消除 60 s 超时（曾致 P95 60 033 ms / 37.5% 超时） | 低 |
| A1 | 补齐 5 个过滤列索引 | 中 | `prices/category-comparison` 长跑 avg 580.2 → ≤200 ms | 低 |
| C3 | `_load_yaml` 走单例缓存 | 中 | `config/raw` 132.4 → ≤15 ms、`config/share` 104.7 → ≤15 ms | 低 |
| C1 | `_dir_size` 双调用合并 | 中 | `vector-admin/snapshots` 233.8 → ≤120 ms（叠加 B2 后 ≤20 ms） | 极低 |
| D2 | 打破 `cache_scan` 进程级 RLock 串行 | 中 | `maintenance/cache-scan` 96 并发 avg 1 822.8 → ≤400 ms | 中 |
| D3 | 写侧批量 UPSERT + 池/超时调优 | 中 | 16 并发写 TPS 51.9 → ≥66（回到峰值档）；P95 635.8 → ≤400 ms | 中 |
| D4 | 大结果集流式导出 | 中 | `db-admin/tables/items/export` P99 1 827.7 → ≤600 ms；私有内存峰值 617.7 MB 下降 | 中 |
| E1 | 多 worker 部署（纯 Web） | 中 | 吞吐 80 → ≥150 rps；96 并发 P99 4 296.9 → ≤1 500 ms | 中（需配合 B1/B3） |
| A5 | 日志/错误检索改前缀匹配或 FTS5 | 中 | `logs/search` 132.9 → ≤40 ms | 中 |
| B3 | 启动预热扩展 | 中 | 冷启动首请求 1.1 s → ≤100 ms | 低 |
| E3 | 依赖不可用的 503 语义改造 | 中 | 30 min 内 795 次 503 → 0，长跑缺陷率 0.74% → 0 | 低 |
| C5 | 评估列表 N+1 批量化 | 中 | 评估列表 P99 858 → ≤300 ms | 中 |
| B4 | 缓存键粒度 + 容量上限/LRU | 低 | RSS 峰值 414.5 → ≤350 MB；失效不再全清 | 中 |
| E2 | SSE 与 API 线程池隔离 | 低 | 长连接不再挤占同池（见「本次自伤实验」证据） | 中 |

---

## A. 数据库查询优化

### A1. 补齐 5 个高频过滤列索引 — 优先级 **中**
**具体优化内容**：在 `backend/xianyu_hunter/infra/db_models.py` 的 `__table_args__` 中补建索引，并按现有迁移通道 `init_db._migrate_create_index` 落库：
- `items.price`（区间过滤）
- `evaluations.risk_level`（`SUM(CASE …)` 分组统计）
- `price_history.user_id`（多用户隔离过滤；该表当前只有 `ix_price_history_item_captured(item_id, captured_at)`，见 `db_models.py:177`）
- `orders.type`
- `task_links.updated_at`

**证据**：已核对 `db_models.py:117-119/194-195/214-215/323-328` 的现有索引清单，上述列**均无索引**。使用点：`web/routes/stats_price_trend.py:49-51`、`web/routes/stats_overview.py:134-141`、`infra/repo_price_history.py:126,137`、`infra/repo_orders.py:90`、`web/routes/price_dashboard.py:421`。实测体现为 `GET /api/prices/category-comparison` 在 1 并发时 29.9 ms、12 并发长跑 580.2 ms（P95 1 329.9 / P99 1 831.4）—— 该接口在 `task_id=None` 时无 WHERE 条件全表扫 `items`（`price_dashboard.py:95-98`）。
**量化预期收益**：本副本 items 仅 774 行时全表扫已是百毫秒级；补索引后区间过滤类接口 P95 预计由 1 330 → **≤500 ms**（12 并发），且随数据量增长由线性恶化转为对数级。**当前数据量下延迟收益有限，属「防恶化」型投资**，故列为中优先级而非高。
**验证方式**：`EXPLAIN QUERY PLAN` 前后对比 + 同一 JMX（`reads_light`）复跑，看 `category-comparison` 与 `stats/price-trend` 的 P95。

### A2. `eval.*` 事件全量重载下推到 SQL — 优先级 **高**
**具体优化内容**：`GET /api/evaluations` 目前经 `web/routes/evaluations_list.py:732` 调 `container.repo.list_events_by_type_prefix(...)`，其默认 `limit=50000`（`infra/repo_events.py:337`，注释自陈「评估事件量级的上限」），把事件整段读进 Python 再过滤 / 分页 / 求中位数；另在同函数额外发一次 COUNT（`repo_events.py:333-365`）。改为：SQL 侧 `WHERE type LIKE 'eval.%' AND …` + `LIMIT/OFFSET`（或 keyset 分页）+ `COUNT(*) OVER ()` 单趟取总数，聚合（中位数/分位）改为 SQL 侧或物化到快照表。
**证据**：基线 1 并发 19.8 ms（缓存命中态）→ 12 并发长跑 **195.9 ms / P95 456.9 / P99 858.0**；同族 `evaluations/distribution` 190.4、`evaluations/threshold-suggestion` 180.2、`evaluations/brands` 173.1 —— 说明整族都被同一重载支配。
**量化预期收益**：长跑该族 avg **195.9 → ≤60 ms**（-70%），P99 **858 → ≤250 ms**；由于评估列表是控制台首页的核心调用，混合场景整体 avg 200.5 可下移约 5~8%。
**验证方式**：同一 JMX 复跑 + `sqlite3 .stats` 或 `EXPLAIN QUERY PLAN`；比对事件表行数翻倍后的 P95（抗增长才是真收益）。

### A4. `maintenance/status` 计数降本 — 优先级 **高**
**具体优化内容**：`web/routes/api_maintenance.py:236-250` 对 `tasks/items/task_links/events/orders/notifications` 逐张 `SELECT COUNT(*)`（`:245`），再 glob 日志目录 + `_cache_scan.snapshot()` 全树遍历。改为：① 用 `PRAGMA`/`sqlite_stat1` 近似行数或维护计数器表；② 全量精确计数移到后台调度任务，接口只读快照；③ 现有 `@cached_ttl(60, …)`（`:235`）把 TTL 提到 300 s 并启用 `stale_while_revalidate` 命中优先。
**证据**：单发探针 1.6 s；**v1 负载轮中该接口 P95 = 60 033 ms（= 客户端 60 s 超时判 000，超时率 37.5%）**，直接把 `baseline_light` 整轮数据打废（该轮已作废重跑）。为控制影响面，最终分层把它判为 `probe_single`（见 `tier-rules.json` 修正规则「单请求耗时 >60 s … 留在负载轮会把整轮 TPS 稀释成假瓶颈」）。
**量化预期收益**：接口自身 avg **1.6 s → ≤200 ms**；更重要的是**消除 60 s 级超时长尾**，使任何并发档位不再出现整轮污染。
**验证方式**：把它重新放回 `reads_light` 负载轮复跑，确认 000 计数为 0。

### A5. 日志/错误检索避免前后通配 — 优先级 **中**
**具体优化内容**：`infra/repo_error_logs.py:63-65` 对 `error_type` / `request_path` 使用 `%keyword%` 通配（索引不可用）；`web/routes/api_logs.py:127-162` 的 `logs/search` 先取 1 000 条事件再在 Python 侧做子串过滤。改为：前缀匹配 `keyword%` + 索引，或引入 SQLite FTS5 虚拟表；过滤条件下推到 SQL。
**证据**：`logs/search` 基线 12.4 ms → 长跑 132.9 ms（P95 308.4）；其 4xx 夹具率虽高但不影响延迟口径。
**量化预期收益**：长跑 avg **132.9 → ≤40 ms**，且检索结果不再受「1 000 条截断」影响正确性。
**验证方式**：构造 10 万级 events 副本，对比 P95 是否随数据量线性增长。

---

## B. 缓存策略调整

### B1. 给进程内 TTL 缓存加单飞（single-flight） — 优先级 **高**（本条为全场最大杠杆）
**具体优化内容**：`backend/xianyu_hunter/web/cache.py:59-79` 的 `_make_sync_wrapper` 在冷/过期 miss 时直接 `result = func(...)`（`:77`），**没有 per-key 锁与双重检查**；只有 `stale_while_revalidate` 分支（`:71-75`）有后台刷新标志。补：`_locks.setdefault(key, Lock())` + 取锁后二次查缓存，未取到锁的请求等待而非重算；并为 `invalidate_stats_cache()` 增加按维度（user/task）失效而非整表清空。
**证据**：① `reads_heavy` 基线 avg **22.7 ms**（单用户，缓存基本命中）→ 同一 135 接口混合场景在 12 并发长跑 avg **200.5 ms**，放大 8.8×；② 同族评估/统计接口长跑均值集中在 165~200 ms 一个窄带（`evaluations/*` 167~196、`notifications*` 170~218、`export*` 134~288），**这是「大家都在等同一份重算」的特征，而不是各自计算不同东西**；③ `startup.py:799-828` 只预热 4 个 key，300 s TTL 到期后首波并发必然击穿。
**量化预期收益**：混合场景 avg **200.5 → ≤80 ms**（-60%），P95 **544.5 → ≤250 ms**，P99 **1 164.5 → ≤450 ms**；`reads_light` 96 并发 P95 3 893.2 预计降至 **≤1 200 ms**（与 D1 叠加后更低）。
**验证方式**：长跑复跑 + 在服务端计数 `func` 实际执行次数（单飞生效应看到重算次数 ≈ 接口数 × 时长/TTL，而非 ≈ 请求数）。

### B2. 把「零并发就慢」的接口纳入 TTL 缓存 — 优先级 **高**
**具体优化内容**：对以下未缓存的只读接口加 `@cached_ttl`（TTL 30~120 s，配 `stale_while_revalidate=True`）：`GET /api/anticrawl/strategy`、`GET /api/vector-admin/snapshots`、`GET /api/config/raw`、`GET /api/config/share`、`GET /api/maintenance/cache-scan`。
**证据**：基线（1 并发）分别 1 094.7 / 233.8 / 132.4 / 104.7 / 94.1 ms，长跑 12 并发 1 300.7 / 450.7 / 334.4 / 292.7 / 287.7 ms；96 并发 2 511.8 / 1 328.3 / 3 236.2 / 2 950.2 / 1 822.8 ms。这些接口的结果秒级内稳定，重复计算无业务价值。
**量化预期收益**：命中后回到地板级 10~20 ms；`reads_light` 基线 avg **50.9 → ≤25 ms**，96 并发 P95 **3 893.2 → ≤1 500 ms**。
**验证方式**：selftest 后同一 JMX 复跑；抽查 TTL 内两次请求的响应体一致性。

### B3. 预热清单扩展 — 优先级 **中**
**具体优化内容**：`web/startup.py:799-828` 的 `_warm_stats_cache` 目前只暖 `business_kpi:30 / stats_today / stats_overview / stats_trend:events:24` 四个 key。把 B2 的接口与首页聚合（评估分布、通知未读数）纳入预热，并在每次调度周期后重暖。
**证据**：基线首样本级长尾（`reads_light` P99 1 065.4 ms 而 P50 仅 11.1 ms）—— 99% 分位完全由冷算/击穿贡献。
**量化预期收益**：冷启动/首个请求 **1.1 s → ≤100 ms**；P99 与 P50 的比值从 96× 降至 **≤10×**。
**验证方式**：重启实例后立刻打 `reads_light` 基线，比较 P99。

### B4. 缓存容量上限与淘汰 — 优先级 **低**
**具体优化内容**：`web/cache.py` 的 `_cache_store` 无容量上限/淘汰策略；加 `max_entries` + LRU，并对大 payload（导出类）不进缓存。
**证据**：长跑 RSS 8 段均值 `203→218→312→322→333→358→373→350 MB`，峰值 **414.5 MB**、私有内存峰值 **617.7 MB**；虽末段回落（未见单调泄漏），但爬升段与缓存/页缓存增长混在一起，不可归因。
**量化预期收益**：RSS 峰值 **414.5 → ≤350 MB**；把「内存增长到底是缓存还是泄漏」变成可判定问题。
**验证方式**：4 h 长跑（见 §E 与 CONCLUSION 的未达成项）分段对比 RSS 斜率。

---

## C. 代码逻辑精简

### C2. `/api/auth/me` 去除重复文件解析与多余 SQL — 优先级 **高**
**具体优化内容**：`web/routes/auth_query.py` 中：① `_resolve_current_user_id(request)` 在一次请求里被调用两次（`:336` 与 `:406`），合并为一次并透传；② `_check_cookies`（`:341` → 其内部 `:83`）每次都 `invalidate_cache` 后重读 cookies JSON 与 `last_login_cookies.json`，改为带 TTL 的进程内 memo；③ `get_userinfo()`（`:344`）再次读文件，复用 ② 的结果；④ `_sync_nick_to_users_table` 的写库（`:369`）仅在昵称变化时才执行（先比对）；⑤ `scan_and_notify`（`:403`）移出 `/me` 请求路径（改调度触发）。
**证据**：基线 avg **152.6 ms**（P95 394.7 / P99 492.7），长跑 **414.3 ms**（P95 1 049.5），96 并发 2 365.2 ms。同时须澄清：**鉴权本身不是瓶颈** —— `web/middleware/auth.py` 的 `verify_session` 走 sha256 + `_verify_cache`（TTL 300 s），非 bcrypt；同族 `POST /api/auth/me/refresh` 仅 17.9 ms，可作「去掉文件重读后的落点」参照。
**量化预期收益**：avg **152.6 → ≤50 ms**（对标 `me/refresh` 17.9 ms + 用户信息查询）；长跑 **414.3 → ≤120 ms**。该接口是控制台每个页面加载的必经调用，收益覆盖全站请求，故列为高优先级。
**验证方式**：`/me` 单接口阶梯（1/16/48 并发）复跑；统计每请求的文件 open 次数。

### C4. 反爬策略接口降本（socket 探测 + Chromium Cookie 全表扫） — 优先级 **高**
**具体优化内容**：`backend/xianyu_hunter/modules/login_strategy.py:144` 用 `socket.create_connection(("127.0.0.1", cdp_target_port), timeout=1.0)` 判断 CDP 可用性 —— 端口未开时**每次请求都吃满 1 s**；`:150-184` 再打开 Chromium `Network/Cookies` SQLite 做全表 `LIKE '%goofish%'`。改为：① 探测 timeout 降到 0.1 s 并 fail-fast；② 探测结果整体短 TTL 缓存（10~30 s）；③ Cookie 计数改用 `WHERE host_key = ?` 精确匹配（该表有 `idx_user_cookies_user_host` 类比索引可用，见 `db_models.py:776`）。
**证据**：`GET /api/anticrawl/strategy` 基线 avg **1 094.7 ms**（≈ 1 s 探测 + 扫描），P99 1 216.8 ms；长跑 1 300.7 ms；96 并发 2 511.8 ms。同族 `anticrawl/fingerprint` 仅 9.0 ms，证明「不算这一跳」的成本地板。
**量化预期收益**：avg **1 094.7 → ≤30 ms**（-97%）。这同时是 D1 的关键前提——它曾是最占用 anyio 线程的接口之一。
**验证方式**：CDP 关闭态下压该接口，确认不再出现 ~1 s 常数项。

### C3. `_load_yaml()` 走单例缓存 — 优先级 **中**
**具体优化内容**：`web/routes/api_config.py:45-48` 每次调用都 `CONFIG_FILE.read_text()` + `yaml.safe_load()` 整份配置，绕过了 `infra/yaml_config.py:784-789` `get_config()` 已有的单例缓存。改为复用单例 + mtime 失效。模板接口同一形态：`web/routes/api_templates.py:65-66 list_templates` 每次调 `_load_presets`(`:39` 读 YAML) + `_load_user`(`:47` 读 JSON)，`POST`(`:76-77 save_template`) 还要再读后整表写回 —— 应按 mtime memo 化。
**证据**：`config/raw` 132.4 ms、`config/share` 104.7 ms、`GET /api/templates` 115.8 ms、`POST /api/config/preview` 151.0 ms、`POST /api/templates` 200.9 ms（均 1 并发基线）；长跑分别 334.4 / 292.7 / 296.4 / 419.0 / 377.3 ms。
**量化预期收益**：命中后 **≤15 ms**（-88%）；写侧 `preview/save` 去掉一次全量读后 avg **151 → ≤80 ms**。
**验证方式**：同一 JMX 复跑 + 配置文件 mtime 变更后确认仍能读到新值（正确性回归）。

### C1. 快照目录体积重复遍历合并 — 优先级 **中**
**具体优化内容**：`web/routes/api_vector_admin.py:103-104` 对同一目录连续调用 `_dir_size(d)` 两次（分别填 `size_bytes` 与 `size_display`）。改为一次求值后复用。
**证据**：`GET /api/vector-admin/snapshots` 基线 avg **233.8 ms**（P95 630.2），长跑 450.7 ms；其成本主要是磁盘遍历（`:64-72` 的 `rglob` 还跑在 async handler 内，会阻塞事件循环）。
**量化预期收益**：**直接减半** → avg ≤120 ms；叠加 B2 缓存后 ≤20 ms。
**验证方式**：单接口阶梯复跑，比较 `size_bytes` 一致性。

### C5. 评估列表市场统计去 N+1 — 优先级 **中**
**具体优化内容**：`web/routes/evaluations_list.py:69-80` 的 `compute_market_stats_batch` 在缓存 miss 时**按 task_id 逐个**调用 `_compute_sold_range`。改为单条 `IN (...)` / 分组聚合一次取回。
**证据**：评估族在长跑中齐处 167~196 ms 窄带（A2/B1 与本条互相放大），`evaluations/1000915580797/seller-trend` 171.6 ms。
**量化预期收益**：多任务用户的评估列表 P99 **858 → ≤300 ms**；调用 task 数越多收益越大（当前是线性放大）。
**验证方式**：种子注入 20 个 task 后对比 P95 斜率。

---

## D. 连接池配置调优与线程模型

### D1. 慢同步接口与快接口隔离线程池 — 优先级 **高**
**具体优化内容**：本项目大量 handler 是同步 `def`，FastAPI 一律丢进 anyio 线程池（默认 **40 token**，代码未覆写）。给已知慢接口（`maintenance/*`、`export*`、`logs/search`、`vector-admin/*`、`anticrawl/strategy`）单独设置 `anyio.to_thread.RunVars`/`CapacityLimiter`（如 4），并把 `vector-admin` 的 `rglob`、`_dir_size` 移出 async handler。
**证据（饥饿的直接形态）**：96 并发时，**本身只要 8.4 ms 的** `GET /api/notifier/quiet-hours` 变成 avg 2 096.8 ms；60 s 窗口内它的完成样本数从基线的 55 掉到 **7**，`vector-admin/snapshots` 只剩 **3**，`maintenance/cache-scan` 剩 **6** —— 完成数骤降 + 廉价接口延迟被抬到 2 s，是「排队等线程」而非「服务算得慢」的教科书特征。轻组整体：16 并发 P95 782.7 → 48 并发 2 064.0 → 96 并发 3 893.2 ms，真实缺陷率 1.81% → 2.03% → **3.17%**。
**量化预期收益**：48/96 并发轻组 P95 **2 064/3 893 → ≤1 000 ms**；缺陷率 **2.03/3.17% → <0.5%**；廉价接口（`quiet-hours`、`fingerprint`）在高并发下回到 ≤100 ms。
**验证方式**：同一 `reads_light` JMX 在 48/96 并发复跑，比较 `notifier/quiet-hours` 的 avg 与完成样本数（样本数恢复即证明隔离生效）。

### D2. 解除缓存扫描的进程级互斥 — 优先级 **中**
**具体优化内容**：`web/services/cache_scan.py:52` 的 `self._lock = threading.RLock()` 在 `snapshot()`（`:66`）里对**所有路径**互斥，使 `/maintenance/cache-scan` 与 `/maintenance/status`（内部也调 `snapshot`）在并发下完全串行。改为按扫描路径分锁，或改增量/无锁读。
**证据**：`maintenance/cache-scan` 基线 94.1 ms → 长跑 287.7（P99 1 581.4）→ 96 并发 avg 1 822.8 ms 且窗口内仅完成 6 次；`maintenance/status` 的 60 s 超时（A4）与该锁的串行化叠加。
**量化预期收益**：两接口并发下不再互相阻塞，96 并发 avg **1 822.8 → ≤400 ms**。
**验证方式**：并发两个不同路径的 `cache-scan`，确认总耗时 ≈ 单路径耗时而非两倍。

### D3. 写侧：批量 UPSERT + 池/超时组合调优 — 优先级 **中**
**具体优化内容**：写阶梯显示 **8 并发即到顶（66.4 TPS）**，16 并发回落到 51.9（-22%）且 P95 已到基线 ×4.3；根因是 SQLite WAL 单写者 + `db_models.py:901-902` 的 `pool_size=20/max_overflow=10` 与 `busy_timeout=10 000`（`:912-913` `synchronous=NORMAL`、`PRAGMA` 设置）。做法：① 写路径合并为批量 UPSERT（`P0-3` 注释里已有同类先例）；② 把 `busy_timeout` 从 10 s 降到 2 s 并对「等锁」加指标暴露（等待时间比报错更危险，因为它把饱和藏起来）；③ 池大小不必再增大——20 > anyio 40 的一半，扩池只延长队列。
**证据**：§3.3 阶梯；全程 5xx ≈0、未出现 `database is locked`（服务端日志关键字命中 0 次），说明冲突被 `busy_timeout` 全部转成等待。
**量化预期收益**：16 并发写 TPS **51.9 → ≥66**（持平峰值档，不再回落），P95 **635.8 → ≤400 ms**；写侧长尾（`baseline_write` max 4 387 ms）收敛。
**验证方式**：`stress_write_t16` 复跑 + 单独统计写接口 avg，验证「吞吐不再回落」。

### D4. 大结果集流式化 — 优先级 **中**
**具体优化内容**：`web/routes/api_export.py:76-98` 虽返回 `StreamingResponse`，但先把最多 5 万行整份 CSV 拼进 `io.StringIO`（`:82-88`），再以 `iter([buf.getvalue()])`（`:91`）单元素「流式」发出 —— 等价于全内存拼接；`web/routes/api_logs.py:127-128` 先取 `min(limit*10, 1000)` 条事件，再在 Python 侧做子串/标签/stage 过滤（`:133-162`，注释自陈 SQLite 无原生 JSON 查询）。改为生成器逐块产出 + 服务端游标分批，过滤条件下推。
**证据**：`GET /api/db-admin/tables/items/export` 基线 35.0 → 长跑 **558.2 ms（P95 1 278.6 / P99 1 827.7）**；`GET /api/config/export` 107.5 → 288.4 ms；`GET /api/export` 16.2 → 134.4 ms。私有内存峰值 617.7 MB（RSS 414.5 MB）。
**量化预期收益**：导出类 P99 **1 827.7 → ≤600 ms**，长跑内存峰值下降（幅度随导出行数而定），并降低与 B4 的耦合。
**验证方式**：774 行副本 vs 5 万行副本各跑一次，比较 RSS 峰值差。

---

## E. 负载均衡方案改进 / 部署形态

### E1. 纯 Web 多 worker（+ 独立调度进程） — 优先级 **中**
**具体优化内容**：`backend/xianyu_hunter/__main__.py:280-284` 的 `--workers` 默认 **1**；`:309-312` 注释自陈「**已实测单 worker 51 → 多 worker 80 req/s**」「生产建议：纯 Web 多 worker（`--no-with-scheduler`）配合独立调度进程」。落地：Web 侧 `--workers N`（N≈物理核数），采集/浏览器留在单进程调度器。
**证据**：本次重组阶梯 4 并发即封顶（81.2 TPS 后持平），CPU avg 55.4%、峰值 269.1%（多核折算）—— **多核有余量而吞吐不涨，正是 GIL 单进程封顶**；与本次实测的 51→80 量级一致。
**量化预期收益**：读吞吐 **≈80 → ≥150 rps**（4 worker，按历史 1.57× 单/多 worker 增益外推）；96 并发 P99 **4 296.9 → ≤1 500 ms**。
**注意（必须先解决的副作用）**：`web/cache.py` 的缓存是**进程内**的，多 worker 会把命中率除以 worker 数，反而放大 B1 的击穿。因此 **B1/B3 必须先落地**，或与共享缓存（Redis / SQLite 快照表）一并设计。这也是本条列中优先级而非高的原因。

### E2. SSE 与 API 线程/连接资源隔离 — 优先级 **低**
**具体优化内容**：SSE（`web/sse_stream.py`，受 `_MAX_SSE_CONNECTIONS`/`_sse_gate` 门控）与短请求共用同一 worker 与线程池。生产建议：SSE 单独进程/端口，或至少把上限与告警暴露到 `/api/metrics`。
**证据**：本次一次旁路的 45 路 SSE 并发实验（17:28 打开、持续 25 s）落在 `baseline_light` 测量窗口内，是我造成的已知污染（见 REPORT §5 表 C）—— 反过来说明 SSE 与 API 的资源确实互相可见。
**量化预期收益**：长连接波动不再影响短请求 P95；可观测性提升（属稳定性收益，非本次直接量化项）。

### E3. 依赖不可用时不要用 5xx — 优先级 **中**
**具体优化内容**：`GET /api/tasks/{id}/links/live` 在采集器不可用时直接 503。改为 200 + `available: false` + 原因字段，或 501/503 但带明确 `code`，并在控制台侧降级展示。
**证据**：30 分钟长跑中 **795 次 503 全部来自该接口（100% 失败）**，构成本轮 0.74% 缺陷率的**全部**；扣掉它后真实缺陷率为 0.00%。
**量化预期收益**：长跑缺陷率 **0.74% → 0**；更重要的是**监控信噪比**——真实故障不再被固定 503 淹没。
**验证方式**：调度器关闭态跑 `soak_mixed`，缺陷率应为 0。

### E4. 尚未覆盖、需在下一轮补的方向
- **≥4 h 耐久**：本次实跑 30 min（墙钟 1 801.4 s），未达目标要求。改 `jmeter-config-v2.yml` 的 `soak_mixed.duration_override: 14400` 即可原样复跑；4 h 才能给出 RSS/句柄斜率的可靠判定（现在只能说「30 min 内未见泄漏」）。
- **CPU/磁盘 IO 逐秒曲线、网络带宽**：`monitor_sut.py` sidecar 只采进程级 RSS/私有内存/CPU%/句柄/线程；系统级磁盘与网络需另接 PerfMon，本报告未据此下任何结论。
- **真实负载画像**：本次「读:写 ≈ 9:1」是按控制台行为的近似，若有真实访问日志（nginx / uvicorn access log），应据此重定权重后再定容量红线。
- **外置压测机**：负载生成器与被测服务同机会让 P95/P99 虚高（技能判据）。当前所有尾延迟应读作**上界**；换机复跑后拐点位置应仍可比。

---

## F. 短期落地路线（建议顺序）

| 阶段 | 内容 | 预期累计效果 |
|---|---|---|
| **第 1 周（低风险高收益）** | B1 单飞 + B2 慢接口缓存 + C1 双调用合并 + C4 探测降本 + A4 计数降本 + E3 503 语义 | 混合场景 avg 200.5 → **≤90 ms**；消除 60 s 超时与 503 噪声；轻组 96 并发 P95 3 893 → **≤1 500 ms** |
| **第 2–4 周（结构性）** | C2 `/me` 去重 + A2 事件下推 + D1 线程池隔离 + D2 解锁 + C3/YAML 单例 | 48/96 并发缺陷率 2.03/3.17% → **<0.5%**；`/me` 全站收益；廉价接口高并发不再被拖到 2 s |
| **季度内（容量形态）** | D3 写批量 + D4 流式 + A1 索引 + A5 FTS + E1 多 worker（须先完成 B1/B3） | 读吞吐 80 → **≥150 rps**；写侧 16 并发不再回落；内存峰值收敛；随数据增长的劣化斜率变缓 |

> 每条落地后请用同一份 JMX 复跑对比（`jmeter-config-v2.yml` + `aggregate.py`，其阶段时长已改为取引擎日志实测墙钟），并保留 jtl/jsonl 作为前后证据。
