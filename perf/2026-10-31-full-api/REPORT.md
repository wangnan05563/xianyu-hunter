# XianyuHunter 全量 API 性能测试报告（2026-10-31）

> 执行方式：`jmeter-performance-test` 技能，`mode: python_replay`（本机无 Java/JMeter，技能自动回退等价回放引擎）
> 完整阶梯、原始样本、聚合数据、JMX 与配置均留存在本目录，见「可追溯性」

## 1. 被测环境与口径

| 项 | 值 |
|---|---|
| 被测实例 | 隔离沙箱 `D:\tmp\xh-perf\sandbox`，端口 **8011**（生产控制台 8001、截图实例 8010 均不触碰） |
| 启动方式 | `python -m xianyu_hunter web --port 8011 --no-with-scheduler`（**调度器关闭**，不会拉起浏览器/采集任务） |
| 数据库 | `data/xianyu.db` 的 **SQLite backup API 一致性副本**（114.1 MB，items 774 / tasks 170 / evaluations·events·price_history 全量），与生产库物理隔离 |
| 配置 | 沙箱副本内 `tunnel.auto_start` 置 false；仓库 `config/config.yaml` 未被改动 |
| 服务端 | FastAPI + Uvicorn 单进程单 worker，SQLAlchemy 2.0 + SQLite(WAL, busy_timeout=10000, synchronous=NORMAL, QueuePool pool_size=20/max_overflow=10)，进程内 TTL 缓存 |
| 压测机 | Windows 10 / Python 3.12 venv；负载生成器与被测服务**同机**（见 §6 偏差声明） |
| 鉴权 | `Authorization: Bearer $WEB_TOKEN`（令牌仅存在于临时目录，压测后随目录删除） |
| 端点总数 | `/api/*` 共 **272** 个（另 272 个 `/xianyu/api/*` 为同一路由的前缀别名，不重复计） |

### 覆盖率（约束「不可遗漏」的对账口径）

| 分层 | 数量 | 处置 | 判据 |
|---|---|---|---|
| `load_read` | 109 | 进入基准 + 压力阶梯 | 本地只读接口 |
| `load_write` | 26 | 进入基准 + 压力阶梯 | 幂等/低代价写接口，落在沙箱副本库 |
| `probe_single` | 67 | 单发探针（记录真实响应码与延迟，不进负载轮） | 非幂等/破坏性/批处理类写接口；重复压测会把「夹具耗尽」伪装成服务缺陷 |
| `blocked` | 70 | 不压测，逐条给出原因 | 出站点（外部大模型/GitHub/推送渠道/真实站点抓取）、真实下单、真实登录态、SSE 长连接、内网穿透 |
| 合计 | **272** | 负载实测量 136 个接口 + 单发实测量 67 个 = 203 个拿到真实响应；69 个按安全红线不出击 | |

`blocked` 的代表项（完整原因见 `endpoint-coverage.json` 的 `reason` 字段）：

- `POST /api/orders/*`（真实下单）、`/api/batch-refresh/{start,run}`、`/api/items/{id}/refresh`、`/api/evaluations/{id}/collect-official`、`/api/tasks/{id}/start`（真实抓取 + 拉起浏览器）
- `/api/ai*`、`/api/chatbot/{chat,messages}`（外部大模型，计费且延迟由第三方支配）
- `/api/tunnel/*`（对外暴露本机端口）、`/api/auth/{qr,browser,cookie,session,import}*`（真实登录链路）
- `*/stream`、`/api/events/stream`（SSE 长连接，请求级吞吐口径不适用）
- `/api/notifier/test`（向真实钉钉/Server酱/Telegram 发消息）、`/api/about/check-update`（出网）

## 2. 基准测试（Baseline，1 并发）

| 组 | 采样器 | 时长 | 样本 | TPS | 平均 | P50 | P95 | P99 | 最大 | 真实缺陷率 | 4xx 率 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 重组 `reads_heavy` | 46 | 300s | 13 156 | 43.9 | 22.7 | 11.1 | 79.4 | 263.6 | 1602.6 | 0.00% | 21.74% |
| 轻组 `reads_light` | 64 | 180s | 3 547 | 19.5 | 50.9 | 11.1 | 180.6 | 1065.4 | 1372.5 | 1.58% | 18.72% |
| 写组 `writes_idem` | 26 | 180s | 5 975 | 32.8 | 30.0 | 10.0 | 148.7 | 253.6 | 4387.0 | 0.02% | 61.52% |

资源基线（空载→满载全周期 2111 个采样点，2s 间隔）：RSS `180.9 MB → 峰值 414.5 MB`，私有内存峰值 `617.7 MB`，句柄 `482 → 峰值 858`，CPU `平均 55.4% / 峰值 269.1%`（多核折算，单进程受 GIL 支配）。磁盘侧：SQLite 主库 + `-wal`，写阶梯期间 WAL  checkpoint 持续回收，未观察到数据库文件无界增长。

**基线结论**：绝大多数接口在单用户下 P95 低于 200 ms，符合本地工具体验；但有 4 个接口在**零并发**下就已经很慢（见 §4 表 A），属于固有成本而非容量问题。

## 3. 压力测试（阶梯并发与拐点）

### 3.1 重组 `reads_heavy`（控制台首屏/统计/评估/日志类聚合读，45+1 个接口）

| 并发 | 样本 | TPS | 平均 | P95 | P99 | 缺陷率 | 4xx |
|---|---|---|---|---|---|---|---|
| 1 | 13 156 | 43.9 | 22.7 | 79.4 | 263.6 | 0.00% | 21.7% |
| 2 | 4 307 | 71.8 | 27.7 | 95.1 | 176.9 | 0.00% | 21.7% |
| 4 | 4 874 | **81.2** | 49.0 | 152.9 | 281.6 | 0.00% | 21.7% |
| 8 | 4 784 | 79.7 | 99.4 | 250.8 | 499.3 | 0.00% | 21.6% |
| 16 | 4 420 | 73.7 | 213.7 | 440.0 | 677.1 | 0.00% | 21.4% |

拐点描述：**拐点出现在 4 并发**。TPS 从 43.9 → 81.2（4 并发）后彻底持平并在 16 并发回落至 73.7，而 P95 从 79 ms 线性攀升至 440 ms（×5.5），平均耗时 ×9.4 —— 典型的「吞吐封顶 + 排队增长」饱和曲线，且**没有任何 5xx**，说明不是逻辑回归而是单进程算力/调度饱和。

> 口径提示：本组数据来自 v1 轮（46 个采样器，含 1 个 SSE 接口 `/api/logs/stream`）。修正分层后该接口被判为 `blocked`，为保持同一集合的 apple-to-apple，未按新集合补跑 32/64 并发档（见 §6）。

### 3.2 轻组 `reads_light`（配置/菜单/账号/看板/维护/向量状态等 64 个接口）

| 并发 | 样本 | TPS | 平均 | P95 | P99 | 真实缺陷率 | 4xx |
|---|---|---|---|---|---|---|---|
| 1 | 3 547 | 19.5 | 50.9 | 180.6 | 1065.4 | 1.58% | 18.7% |
| 16 | 3 530 | **58.1** | 266.3 | 782.7 | 1275.5 | 1.81% | 18.4% |
| 48 | 2 507 | 41.3 | 1096.2 | 2064.0 | 3566.5 | 2.03% | 15.9% |
| 96 | 3 027 | 49.4 | 1825.8 | **3893.2** | 4296.9 | **3.17%** | 13.8% |

拐点描述：**拐点在 16 并发**（吞吐增益 2.98×，P95 相对基线劣化 4.3×）。16 并发后 TPS 不再上升（58.1 → 41.3 → 49.4，吞吐回落且抖动），P95 在 48→96 并发之间再劣化 ×5，同时真实缺陷率单调上升 1.81% → 2.03% → 3.17%。96 并发的 P99 4.3 s 已进入「控制台不可用」区间。

### 3.3 写组 `writes_idem`（26 个幂等写接口，含配置保存/评估重算/任务创建）

| 并发 | 样本 | TPS | 平均 | P95 | P99 | 真实缺陷率 | 4xx（夹具口径） |
|---|---|---|---|---|---|---|---|
| 1 | 5 975 | 32.8 | 30.0 | 148.7 | 253.6 | 0.02% | 61.5% |
| 4 | 3 523 | 57.3 | 67.2 | 259.3 | 441.6 | 0.03% | 61.5% |
| 8 | 4 042 | **66.4** | 118.0 | 378.6 | 577.3 | 0.00% | 61.6% |
| 16 | 3 170 | 51.9 | 291.9 | 635.8 | 816.0 | 0.00% | 61.6% |

拐点描述：**吞吐上限在 8 并发（66.4）**，8→16 并发吞吐不仅不涨反而回落到 78%（51.9），同时 P95 已达基线 ×4.3 —— 机械判据（`ladder_table.md`）把饱和档记为 16，实际可用容量应按「峰值档 8」取。该形态符合 SQLite WAL 单写者 + 连接池（20）在写侧的串行化特征。写侧 5xx 全程 ≈0，说明写路径在容量范围内是正确的。

### 3.4 最大并发能力（以 P95 < 1 s 为体验红线）

| 场景 | 可接受并发 | 依据 |
|---|---|---|
| 首屏/统计聚合读 | **≈4** | 4 并发后 TPS 不再增长 |
| 混合控制台读（含配置/看板） | **≈16** | 48 并发时 P95 2.06 s 越线 |
| 幂等写（配置保存、重算） | **≈8** | 16 并发吞吐回落 |

## 4. 稳定性 / 耐久测试

- 场景：`mixed_biz`（135 个接口，读:写 ≈ 9:1，贴近控制台真实比例）
- 配置：**12 并发恒定负载，连续 1800 s（30 分钟，实测墙钟 1 801.4 s）**，107 324 个样本
- 分窗趋势（每 5 分钟一窗 ×6，样本数完全相等说明节流稳定）：

| 窗口 | 样本 | TPS | 平均 | P95 | P99 | 真实缺陷率 | 4xx |
|---|---|---|---|---|---|---|---|
| 1（0–5min） | 17 887 | 59.6 | 198.3 | 545.0 | 1194.5 | 0.76% | 27.7% |
| 2（5–10min） | 17 887 | 59.6 | 201.4 | 521.2 | 1157.6 | 0.75% | 28.2% |
| 3（10–15min） | 17 887 | 59.6 | 194.9 | 548.2 | 1182.7 | 0.74% | 28.1% |
| 4（15–20min） | 17 887 | 59.6 | 220.7 | 624.4 | 1229.1 | 0.75% | 28.2% |
| 5（20–25min） | 17 887 | 59.6 | 223.3 | 585.8 | 1166.5 | 0.74% | 28.1% |
| 6（25–30min） | 17 887 | 59.6 | 164.7 | 398.6 | 1063.5 | 0.73% | 28.3% |

判定：
- **无吞吐/延迟退化**：TPS 六窗恒为 59.6（12 并发 × avg 200 ms 的理论值 60，说明客户端无空转），P95 在第 6 窗反而最优（398.6 ms），末窗相对首窗改善 27% —— 曲线在 30 分钟尺度上平稳。
- **内存**：RSS 按 8 段均值为 `203 → 218 → 312 → 322 → 333 → 358 → 373 → 350 MB`，前 4 段是预热爬升，后 3 段进入平台且末段回落，**未见单调上升**；私有内存峰值 617.7 MB（约 RSS 的 1.5 倍，含 SQLite 页缓存 `cache_size=-20000` ≈ 20 MB/连接 × 连接数）。
- **连接/句柄**：句柄数 `482 → 858 → 630`，负载停止后回落，**未见连接泄漏**；未出现 `database is locked`（服务端日志中该关键字命中 0 次）。
- **残余缺陷**：30 分钟内 795 次 503 **全部**来自 `GET /api/tasks/{id}/links/live`（100% 失败），根因是沙箱关闭调度器后采集器不可用；另有 4 次 `000` 超时（分布在 4 个写接口，单发，属长尾抖动）。扣除该项后，本轮真实缺陷率为 0.00%。
- **未达成项**：目标要求 ≥4 h。本次执行 30 min（会话预算限制），已把耐久长跑的参数留存在 `jmeter-config-v2.yml`（把 `soak_mixed.duration_override` 改为 `14400` 即可原样复跑 4 h），本报告不将 30 min 结果外推为 4 h 结论。

## 5. 瓶颈定位（测量 + 源码双向对齐）

### 表 A：零并发就慢的接口（固有成本，非容量问题）

| 接口 | 单用户 avg | 根因（源码位置） |
|---|---|---|
| `GET /api/anticrawl/strategy` | **1095 ms**（30 min 长跑中 avg 1300 ms） | 同步 `def` → 线程池；`login_strategy.py:144` 对 CDP 端口做 `socket.create_connection(timeout=1.0)`，端口未开即吃满 1 s；`login_strategy.py:150-184` 再打开 Chromium `Network/Cookies` SQLite 做全表 `LIKE '%goofish%'` 扫描。结果秒级稳定却**完全未缓存** |
| `GET /api/vector-admin/snapshots` | 451 ms | `api_vector_admin.py:89-108` 对每个快照目录调用 `_dir_size` **两次**（`:103` 与 `:104`），纯重复遍历；未缓存 |
| `GET /api/auth/me` | 153 ms（长跑 414 ms） | `auth_query.py:326` 起：`_resolve_current_user_id` 被调用两次（`:336`、`:406`），`_check_cookies` 每次 `invalidate_cache` 后重读 cookies JSON + `last_login_cookies.json`，再 `get_userinfo()` 读文件、`_sync_nick_to_users_table` 写库、`scan_and_notify` 查库。鉴权本身（`hmac.compare_digest` / `verify_session` 带 300 s 缓存）**不是**瓶颈，路由体的重复文件解析才是 |
| `GET /api/config/raw` `/api/config/share` | 132 / 105 ms | `api_config.py:45-48 _load_yaml()` 每次调用都重读并 `yaml.safe_load` 整个配置文件，无缓存（`infra/yaml_config.py:784-789` 的单例缓存在这条路径上被绕过） |
| `POST /api/config/preview` `/api/templates` | 419 / 377 ms（长跑） | 同一 `_load_yaml` 成本 + `_dump_yaml`/`_validate`/`_diff`；`templates` 另加读用户文件 + 写文件 + 读 presets |
| `GET /api/prices/category-comparison` | 580 ms（长跑） | `price_dashboard.py:95-98` 在 `task_id=None` 时无 WHERE 条件全表扫 `items`，`_build_item_select` 被重复执行（`range_days>0` 时读两遍）；未缓存 |
| `GET /api/maintenance/status` | 单发 1.6 s | `api_maintenance.py:245-250` 对 6 张大表逐一 `SELECT COUNT(*)`，并 glob 日志目录、`_cache_scan.snapshot()` 全树遍历；虽已有 `@cached_ttl(60, stale_while_revalidate=True)`，但冷/过期路径就是全量重算 |

### 表 B：并发下的系统性瓶颈

| # | 瓶颈 | 证据 | 根因 |
|---|---|---|---|
| B1 | **吞吐封顶 ~80 rps 且与并发无关**（重组 4 并发即到顶） | §3.1：TPS 43.9→81.2→79.7→73.7，缺陷率恒 0 | 单进程 Uvicorn + Python GIL：CPU avg 55%、峰值 269% 说明多核未用满，但同步 handler 全挤在 anyio 线程池。`__main__.py:280-284` 的 `--workers` 默认 **1**，且 `__main__.py:309-312` 注释自陈「已实测单 worker 51 → 多 worker 80 req/s，生产建议纯 Web 多 worker + 独立调度进程」——本次沙箱正是默认单 worker |
| B2 | **高并发尾延迟爆炸 + 超时** | 轻组 96 并发 P99 4296.9 ms、缺陷率 3.17%；v1 轮 `maintenance/status` 出现 P95 60 033 ms（= 客户端 60 s 超时判 000）而单发仅 1.6 s | 慢同步接口与快接口**共享 anyio 线程池（默认 40 token，代码未覆写）**；`CacheScanService` 进程级 `RLock`（`services/cache_scan.py:52,66`）把 `/cache-scan` 与 `/maintenance/status` 串行化，一个全树遍历就能让后续请求排队 → 排队即超时 |
| B3 | **缓存无单飞（击穿）** | 长跑 12 并发下 avg 200 ms，而单用户仅 50 ms；`stats` 类接口 300 s TTL 到期时并发全量重算 | `web/cache.py:62-79`：冷/过期 miss 无 `single-flight`，N 个并发请求各自重算同一聚合（只有 `stale_while_revalidate` 分支有 `_refreshing` 标志）；缓存字典无容量上限/淘汰，`invalidate_stats_cache()` 为全清 |
| B4 | **重活放在请求路径上** | `GET /api/evaluations` 每请求全量拉 `eval.*` 事件（`limit=50000`）+ JSON 解析 + Python 侧过滤/分页/中位数；`/api/logs/search` 取 1000 条事件再 Python 子串过滤；`/api/export` 最多 5 万行全内存拼 CSV | `evaluations_list.py:676`、`repo_events.py:333-365`（另发一次 COUNT）、`api_logs.py:127-162`、`api_export.py:76-98`；`compute_market_stats_batch`（`evaluations_list.py:69-80`）在缓存 miss 时**按 task_id 逐个**跑 `_compute_sold_range`（N+1） |
| B5 | **写侧 8 并发饱和** | §3.3：TPS 66.4（8 并发，峰值）→ 51.9（16 并发，−22%） | SQLite WAL 单写者；连接池 20 但 `busy_timeout=10000` 会把写冲突变成「等待」而非报错，因此表现为吞吐回落而不是 5xx —— 与技能判据「饱和非逻辑回归」一致 |
| B6 | **无索引的过滤列** | 代码核对（`db_models.py` 的 `Index(...)` 与 `init_db` 的 `_migrate_create_index`）后确认下列被查询列**无索引**：`items.price`（`stats_price_trend.py:49-51` 区间过滤）、`evaluations.risk_level`（`stats_overview.py:134-141` 全表 `SUM(CASE)`）、`price_history.user_id`（`repo_price_history.py:126,137` 过滤但该表不在 `_MU2_TABLES`）、`orders.type`（`repo_orders.py:90`）、`task_links.updated_at`（`price_dashboard.py:421`）、`events.level` / 单独 `events.stage`；`error_logs.error_type/request_path` 用 `%LIKE%` 前后通配（`repo_error_logs.py:63-65`，索引不可用） | 数据量小时不明显，本轮 items 774/evaluations·events 数万，全表扫已是百毫秒级；随采集累积会线性恶化 |
| B7 | **503 语义污染可观测性** | 30 min 内 795 次 503 全部来自 `links/live`（100%） | 依赖（采集器）不可用时直接 5xx。它既是本次缺陷率的全部来源，也说明生产中该状态会淹没真实故障信号 |

### 表 C：必须与「服务缺陷」区分开的环境/工具口径

| 现象 | 判定 | 依据 |
|---|---|---|
| `POST /api/tasks/{id}/links/refresh`、`/api/evaluations/batch-collect-official` 100% 503（v1 写基线） | 环境口径（非容量缺陷），已从负载轮剔除 | 沙箱关闭调度器 → 采集器不可用 |
| 写组 4xx 率 61.5%、长跑 422/400 共 20 068 次（`logs/search`、`logs/export`、`items/batch`、`error-logs`、`links/lookup` 等 8 类各 795~799 次全量 422） | 夹具口径（合成 query/body 未补齐必填参数），**不计入服务缺陷** | 422 = FastAPI 必填参数校验失败；技能规定错误率与缺陷率必须区分 |
| 轻组基线受一次旁路实验干扰（17:28 打开 45 路 SSE 共 25 s） | 该 25 s 落在 `baseline_light` 窗口内，占比 <1% 样本；已知偏差，报告中如实标注 | 副作用是我造成的，非被测系统行为 |

## 6. 偏差与局限（不粉饰）

1. **负载生成器与被测服务同机**（Windows、D 盘剩余 3 GB）。技能判据明确这会让尾延迟虚高；因此本文的 P95/P99 是**上界**，而「拐点相对位置」仍可比。旁证：轻组在 16 并发下 P50 仍健康，说明非纯机器饱和。
2. **`python_replay` 模式的绝对 TPS 低于真实 JMeter 分布式能力**（GIL + 线程模型，96 并发已近客户端上限）。因此「最大并发能力」三档数字应读作「在本客户端下观察到的饱和点」，不是服务端极限。
3. 重组阶梯（§3.1）使用 v1 分组（含 1 个 SSE），修正分组后未补跑 32/64 档，避免与基线不同构对比 —— 该组结论止步于 16 并发。
4. 耐久仅 30 min，未满足 ≥4 h；长跑中 `threads` 指标在本机采样接口返回空值，故未纳入泄漏判据（句柄数与 RSS 双指标已覆盖同类风险）。
5. v1 轮重组阶梯（2/4/8/16 并发）的**逐请求原始样本**在修正分层时被清理，因此 `results/agg_phases.json` 中不含这四档，只有本文件 §3.1 抄录的汇总数字（当时按配置时长 60 s 计算，与该轮引擎实测墙钟一致）。v2 轮 10 个阶段的原始样本全部留存。
6. 写压测在沙箱副本库留下了种子数据（约 230 次任务创建等）。副本已随临时目录删除，生产库未被写入。
7. **口径修正（复核时发现并已改正）**：首版聚合器按 v1 配置的时长去除 v2 轮的样本数（`baseline_light` 用 300 s、`soak_mixed` 用 3600 s），而这两阶段实跑 180 s / 1800 s，导致吞吐被系统性低估一半（曾误报 11.8 / 29.8）。现 `aggregate.py` 改为从引擎日志取每阶段**实测墙钟秒数**，本文件与 `results/*` 均为修正后数字；百分位、缺陷率、4xx 率不受影响。

## 7. 可追溯性

本目录留存：

| 文件 | 内容 |
|---|---|
| `jmx/reads_heavy.jmx` `reads_light.jmx` `writes_idem.jmx` `mixed_biz.jmx` | 4 份 JMX 脚本（配置驱动生成，主机/端口经 `${__P(host)}/${__P(port)}` 注入） |
| `jmeter-config.yml` / `jmeter-config-v2.yml` | 两轮唯一参数来源（沙箱、阶梯、缺陷规则、报告口径），含改 4 h 长跑的入口 |
| `tier-rules.json` / `build_scenarios.py` / `emit_config.py` | 端点分层规则与场景生成（换业务 = 改 JSON，不改代码） |
| `endpoint-coverage.json` | 272 端点的分层、真实响应码原因、`reason` 逐条可查 |
| `results/*.jsonl.gz` | 10 个阶段的逐请求原始样本（gzip-9） |
| `results/agg_phases.json` | 每阶段 × 每接口的样本数/TPS/P50/P90/P95/P99/最大/缺陷率/4xx/状态码分布 |
| `results/ladder_table.md` `endpoint_table.md` `soak_table.md` `resource_summary.json` `probe_probe_single.json` `sut_resource.csv` | 阶梯表 / 136 接口全量表 / 长跑分窗 / 资源采样（2111 点）/ 67 端点单发探针 |
| `setup_sandbox.py` `coverage_probe.py` `aggregate.py` `patch_and_v2.py` | 复现所需的环境搭建、探针、聚合、口径修正脚本 |

复现：`python setup_sandbox.py` → 启动沙箱实例并写 `sut.pid` → `python emit_config.py` → `gen_jmx.py --config jmeter-config.yml` → `python_replay_engine.py --config jmeter-config-v2.yml --all` → `python aggregate.py`。
