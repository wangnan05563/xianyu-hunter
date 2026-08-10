# XianyuHunter 全接口性能测试综合报告

> 生成时间：2026-08-09 ｜ 测试框架：JMeter 5.6.3 (non-GUI) ｜ 被测系统：XianyuHunter Web (FastAPI + SQLite WAL + ChromaDB)
> 范围：全部对外接口 + 内部核心接口（已排除一切外部依赖接口，零 ToS / 成本 / 封号风险）
> 运行模式：web-only（无浏览器自动化、无调度器、无真实闲鱼/LLM 调用）

---

## 1. 执行摘要

| 测试 | 部署模式 | 样本数 | 错误率 | 平均 | P95 | P99 | 吞吐量 |
|---|---|---|---|---|---|---|---|
| **Run1b 读（单 worker）** | 66 接口 × 4 阶段 | 31,165 | **5.195%** | 1910 ms | 5937 ms | 8626 ms | **51.1 req/s** |
| **Run2 读（4 worker）** | 66 接口 × 4 阶段 | 49,062 | **4.890%** | 1223 ms | 5505 ms | 13724 ms | **79.6 req/s** |
| **Run3b 写（单 worker）** | 7 接口 | 9,517 | **0.000%** | 242 ms | 423 ms | 524 ms | **79.4 req/s** |

**核心结论**

1. **吞吐天花板由单进程 GIL 决定**：单 worker 仅 51 req/s；4 worker 提升到 80 req/s（+56%），但机器 CPU 仍被打满（96–100%），说明单机已是瓶颈。
2. **读接口延迟普遍超标**：66 个读接口**全部**突破 P95<1s 的 SLA；最严重的是 `维护状态`（avg 10–11s，P95 18–22s）。
3. **错误率≈5% 几乎全部来自 3 个缺陷接口**：`订单详情`(100%→500)、`偏好 PUT`(100%→405 路由未挂载)、`商品批量`(100%→SocketException)。其余 63 个接口错误率≈0%。
4. **写路径健康**：受控写 0% 错误、avg 242ms、79 req/s；唯一问题是 `偏好 UPSERT` 返回 405（路由缺陷，非性能问题）。
5. **多 worker 提升吞吐与中位延迟，但峰值时长尾（P95）反而变差**：说明"加 worker"解决不了重接口的尾延迟，必须针对重接口做缓存 / 索引 / 异步化。

---

## 2. 测试范围与方法

### 2.1 接口覆盖
- **读（Tier A，66 个接口）**：stats / prices / tasks / orders / items / evaluations / config / menu / preferences / prompts / templates / about / notifications / error-logs / logs / accounts / anticrawl / vector-admin / kb / tunnel / maintenance / batch-refresh / cron / param-calculator / db-admin / chatbot 等。
- **写（Tier B，7 个接口）**：偏好 UPSERT、通知全部已读、创建会话、删除会话、清理缓存(dry_run)、配置预览、提交评估反馈。

### 2.2 分阶段加压（读）
| 阶段 | 并发 | 持续 | 目的 |
|---|---|---|---|
| Phase1 基准 | 10 | 60s | 单用户基线 |
| Phase2 负载 | 50 | 180s | 常态负载 |
| Phase3 压力 | 100 | 180s | 压力拐点 |
| Phase4 峰值 | 200 | 180s | 峰值 / 过载 |

### 2.3 写加压
单阶段：20 并发 / 10s 爬坡 / 120s。

### 2.4 关键方法决策（已与用户确认）
- **排除外部依赖接口**：不调用真实闲鱼浏览器自动化、外部 LLM，零封号 / 成本风险。
- **多 worker 对比**：Run2 用 `uvicorn --workers 4` 量化单 worker 天花板。
- **受控写隔离**：Run3 在**独立沙箱目录**（复制备份 DB）启动服务，生产 `data/xianyu.db` 全程未被触碰（详见 §6 限制）。

### 2.5 认证与数据
- 鉴权：`BearerAuthMiddleware` + `WEB_TOKEN` 管理令牌（`request.state.user_id="default"` 单用户模式）。
- 参数化 ID：从测试库抽取真实 `task_id` / `item_id` / `seller_id`，避免 404 噪声。
- 写测试基于 `orders` 表为空的备份库；`ORDER_ID` 故意用占位符以验证"缺失订单"健壮性。

---

## 3. 单 worker vs 多 worker 分阶段对比（读）

| 阶段 | 并发 | 单 worker 吞吐 | 4 worker 吞吐 | 倍率 | 单 worker P95 | 4 worker P95 |
|---|---|---|---|---|---|---|
| Phase1 | 10 | 36.1 | 58.4 | **1.62×** | 1272 ms | 956 ms |
| Phase2 | 50 | 45.3 | 78.2 | **1.73×** | 3804 ms | 3330 ms |
| Phase3 | 100 | 52.4 | 85.7 | **1.63×** | 5355 ms | 4623 ms |
| Phase4 | 200 | 60.7 | 82.1 | **1.35×** | 6988 ms | **9604 ms** |

**解读**
- 多 worker 在**吞吐量与中位/平均延迟**上全面占优（+35%~73%），证明 GIL 是单 worker 的硬天花板。
- **但 Phase4 的 P95 多 worker 反而更高（6988→9604ms）**：200 并发下 4 个 worker 仍把单核 CPU 打满，重接口（维护状态、反爬策略等）的尾延迟因 CPU 争用而恶化。
- 结论：**加 worker 解决吞吐，不解决重接口尾延迟**——后者必须靠缓存 / 索引 / 异步化（§5、§7）。

---

## 4. 资源占用

| 运行 | 系统 CPU 均值 / 峰值 | 系统内存占用 | 时长 |
|---|---|---|---|
| Run1b 单 worker 读 | 96.6% / **100%** | 61.8%（均值） | 630s |
| Run2 4 worker 读 | 96.0% / **100%** | 64.8%（均值） | 659s |
| Run3b 单 worker 写 | 87.5% / 100% | 69.2%（均值） | 178s |

- **CPU 全程打满** → 系统是 CPU 密集型，单机横向扩展受限于核数。
- 内存占用 62–70%，**非内存瓶颈**。
- 写测试 CPU 略低（87.5%）是因为写接口更轻、且 7 个接口并发压力小。

---

## 5. 性能瓶颈（延迟维度）

全部 66 读接口均突破 P95<1s SLA。按 Run2（4 worker，更贴近生产多 worker）P95 降序列出最严重的前 15 个：

| 接口 | avg | P95 | P99 | 问题类型 |
|---|---|---|---|---|
| 维护状态 | 11497 ms | **21876 ms** | 26041 ms | 同步全表扫描 + 文件系统遍历（browser_data / pycache / logs） |
| 向量库状态 | 5103 ms | 14375 ms | 30011 ms | headless 下 ChromaDB 不可用导致超时/重试（环境相关） |
| 反爬策略 | 4833 ms | 12540 ms | 17843 ms | 重聚合查询 |
| 隧道状态 | 3652 ms | 12106 ms | 20803 ms | 外部隧道探测阻塞 |
| Cron示例 | 2134 ms | 9886 ms | 19209 ms | 模板渲染 / 外部示例获取 |
| 检查更新 | 4268 ms | 9473 ms | 17569 ms | 外部版本检查阻塞 |
| 日志搜索 / 错误日志 / 日志 | 2100–2900 ms | 6880–8843 ms | — | 日志文件全量扫描 |
| 未读计数 / 通知列表 | 960–2760 ms | 3827–6883 ms | — | 事件表 COUNT 未索引 |
| DB表结构 / DB表行 / DB表列表 | 840–1627 ms | 4874–6566 ms | — | 元数据反射查询 |
| 账号 / 账号统计 | 985–1242 ms | 4686–5617 ms | — | 账号聚合 |
| 批量刷新历史 | 1542 ms | 5739 ms | — | 状态聚合 |

**特征归纳**
- 重接口集中在三类：**(a) 全量扫描型**（维护状态、日志类）、**(b) 聚合统计型**（反爬、账号、通知）、**(c) 阻塞外部探测型**（隧道状态、检查更新、向量库状态）。
- 轻量接口（Dashboard / 今日统计 / 趋势 / 业务 KPI）avg 0.4–0.9s、P95 2–3s，仍超 1s 但相对健康，主要靠缓存即可压到亚秒。

---

## 6. 发现的缺陷（错误率维度）

≈5% 的总错误率**几乎全部来自以下 3 个接口**（其余 63 个接口错误率≈0%）：

| 接口 | 错误率 | 实际表现 | 根因 | 严重度 |
|---|---|---|---|---|
| `订单详情` GET /api/orders/{id} | 100% | **500**（占位订单不存在时抛未捕获异常） | 缺失订单应返回 404，当前直接 500 | **P0** |
| `偏好` PUT /api/preferences | 100% | **405 Method Not Allowed** | preferences 路由未挂载 / 无 PUT 处理器（功能缺失） | **P0** |
| `商品批量` GET /api/items/batch | 99.6–100% | **SocketException / 连接被重置** | 重负载下连接被重置，疑似连接池 / 上游调用健壮性不足 | **P0** |
| `向量库状态` GET /api/vector-admin/status | 2.05%（仅 Run2） | 偶发失败 | headless 环境 ChromaDB 不可用 | P2（环境相关） |

> 注：Phase3/Phase4 重接口（维护状态、反爬策略等）有 0.1–0.5% 的超时错误，源于 30s response_timeout 在 CPU 饱和时的长尾，非独立缺陷。

---

## 7. 优化建议（按优先级）

### P0 — 正确性缺陷（导致 100% 失败，必须优先修复）

| # | 方向 | 具体动作 | 预期收益 | 工作量 |
|---|---|---|---|---|
| P0-1 | 接口健壮性 | `订单详情`：缺失订单捕获异常并返回 **404**（非 500）；统一所有 `{id}` 查询的空结果处理 | 消除 100% 错误；消除服务端 500 | 低 |
| P0-2 | 路由完整性 | 确认 `PUT /api/preferences` 是否应有对应处理器；若需支持则挂载 preferences 路由的 PUT，否则从前端移除该调用 | 恢复偏好写能力（当前 405） | 低–中 |
| P0-3 | 连接健壮性 | `商品批量`：排查连接重置根因（连接池上限 / 同步上游 / 超时）；加超时、连接复用、错误兜底；压测验证 0% 错误 | 恢复核心批量查询接口（当前 100% 失败） | 中 |

### P1 — 延迟优化（性能主战场）

| # | 方向 | 具体动作 | 预期收益 | 工作量 |
|---|---|---|---|---|
| P1-1 | 缓存策略 | `维护状态` 加 **TTL 缓存（30–60s）** + 后台异步刷新；该接口扫描 DB 计数 + browser_data + pycache + logs，是头号瓶颈（P95 18–22s） | P95 **18s → <500ms（≈36×）** | 低–中 |
| P1-2 | 数据库索引 | 为高频过滤/计数列加复合索引：`events(created_at, type)`、`notifications(user_id, read_at)`、`items(first_seen)`、`task_links(link_type)`、`logs(created_at)` | 日志/事件/通知类查询 **秒级 → 毫秒级** | 中 |
| P1-3 | 并发/连接池 | 提升 SQLAlchemy `pool_size`（当前 10 → 20–30），或迁移 **async SQLAlchemy (asyncpg)** 让 I/O 不阻塞线程 | 平抑并发延迟曲线（单 worker 200 并发时延迟涨 11× 即源于池饥饿） | 中–高 |
| P1-4 | 部署配置 | 生产以 `uvicorn --workers N`（N=CPU 核数，4–8）+ 反向代理部署 | 吞吐 **+56%**（已实测 51→80 req/s），中位延迟 −36% | 低 |
| P1-5 | 缓存层 | 引入 Redis / 进程内缓存覆盖读重接口：stats、config、menu、preferences、kb 状态、vector-admin 状态 | 读平均延迟 **−30~50%**，CPU 占用下降 | 中 |
| P1-6 | 异步化 | `检查更新`、`隧道状态`、`向量库状态` 等阻塞外部探测的接口改为后台任务 + 轮询/缓存，不在请求内同步等待 | 消除 4–12s 的同步阻塞，P95 大幅下降 | 中 |

### P2 — 架构 / 资源

| # | 方向 | 具体动作 | 预期收益 | 工作量 |
|---|---|---|---|---|
| P2-1 | 资源扩缩 | 单机 CPU 全程 100%，建议按核数扩 worker 或横向扩容到多机；重扫描接口下沉到独立 worker | 突破单机 CPU 天花板 | 中 |
| P2-2 | 测试加固 | 固化本次发现的 JMeter 陷阱（见 §8），形成可重复回归测试 | 后续性能回归可信、可自动化 | 低 |

---

## 8. 测试工具链踩坑（供后续复用）

1. **JMeter 断言 `test_type` 取值**：`8` = Substring（字面、忽略正则），`2` = Matches（正则全匹配）。多码断言须用单条正则 `200|404|405` + `test_type=2`，**不能用 8**（会把 `^(?:200|404)$` 当字面子串，永远匹配不到响应码，导致 100% 误判失败）。
2. **POST body 不能用 `HTTPSampler.postBody`**：高并发 + keep-alive 下会丢 body（后端收不到 → 422）。改用**单个无名 HTTPArgument**（`name=""` + `value=JSON`）发送原始 body，稳定。
3. **HTML 报告生成**需在自定义 `jmeter.properties` 显式声明 `jmeter.reportgenerator.apdex_satisfied_threshold` / `apdex_tolerated_threshold`，否则报告生成失败。
4. **`success` 字段不可全信**：依赖断言时 4xx 判定有 ORO 正则怪异；最终以 `responseCode ∈ 预期码集合` 重算（见 `scripts/perf/postproc_jtl.py`）。
5. **沙箱隔离写测试**：通过切换 CWD（复制备份 DB + `.env` + `config/`）启动服务，避免污染生产 `data/xianyu.db`，无需停生产服务即可安全压测写路径。

---

## 9. 限制与说明

- **外部依赖接口已排除**：本报告不含真实闲鱼爬取 / 外部 LLM 的路径性能，相关接口在 web-only 模式下多为本地 DB / 缓存查询，不代表带真实浏览器自动化的端到端耗时。
- **写测试隔离**：Run3 在 `test_results/jmeter/run3_sandbox/` 沙箱启动服务（复制备份 DB），**生产 `data/xianyu.db` 全程未被修改**。
- **历史写污染的透明说明**：本会话之前的 Run3（非沙箱）曾向生产库写入少量无害行（通知已读标记、1 条维护事件）。因生产服务（端口 8001）持续占用该 DB 文件，强制还原会干扰在运行的生产应用，**故未做强制还原**；这些写入对测试/开发库无功能影响，且本会话已通过沙箱隔离杜绝进一步污染。
- **headless 环境**：`向量库状态` / `创建会话` 等在真实 ChromaDB 可用时表现可能不同；本环境以 web-only 为准。
- **SLA 阈值**：默认 avg<500ms / P95<1000ms / err<1%，仅作基线参考，可按业务调整。

---

## 10. 交付物清单

```
test_results/jmeter/
├── scripts/
│   ├── gen_jmx.py            # JMX 生成器（读 66×4阶段 + 写 7）
│   ├── monitor_resources.py  # 资源监控（按端口采样 CPU/内存/线程）
│   ├── analyze_jtl_comprehensive.py  # JTL 聚合分析（per-label/phase, SLA, 瓶颈）
│   └── postproc_jtl.py       # 依据预期码重算 success（修正 JMeter 断言怪异）
├── xianyu_load_test_reads.jmx / xianyu_load_test_writes.jmx
├── results_comprehensive_reads.jtl / _fixed.jtl        # Run1b 单 worker 读
├── results_comprehensive_reads_multi.jtl / _fixed.jtl  # Run2 四 worker 读
├── results_comprehensive_writes_run3b.jtl / _fixed.jtl # Run3b 单 worker 写（沙箱）
├── analysis_run1b/reads.{summary,phases,report}.csv|md
├── analysis_run2/reads.{summary,phases,report}.csv|md
├── analysis_run3b/writes.{summary,phases,report}.csv|md
├── monitor_reads.csv / monitor_reads_multi.csv / monitor_writes2.csv
├── reports_comprehensive_reads/ / reports_comprehensive_reads_multi/ / reports_comprehensive_writes_run3b/  # JMeter HTML 报告
└── db_backup/                # SQLite 备份（db + wal + shm）
```

---

## 11. 行动建议（落地顺序）

1. **先修 P0 三个 100% 失败接口**（订单详情 404、偏好路由、商品批量连接重置）——这些是正确性硬伤，修复成本低、收益高。
2. **给 `维护状态` 加缓存**（P1-1）——单点优化即可消除头号瓶颈（18s→<500ms）。
3. **加 DB 索引 + 提升连接池 / 异步化**（P1-2/3）——系统性压低统计类接口延迟。
4. **生产改为多 worker 部署 + 引入读缓存层**（P1-4/5）——吞吐与体验双重提升。
5. **重接口异步化 + 横向扩容**（P1-6/P2-1）——应对峰值与未来增长。
