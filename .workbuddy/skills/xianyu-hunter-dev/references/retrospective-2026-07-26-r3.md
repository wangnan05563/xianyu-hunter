# 复盘报告：2026-07-26 健康检查 Cookie 无效但实时搜索正常（双数据源不一致）

> **版本**：v4.69.0
> **复盘日期**：2026-07-26
> **复盘方法**：Sequential Thinking 四维度复盘
> **触发来源**：用户引用 [迭代提示词.md#L31-53](../../../docs/00-待完成/迭代提示词.md#L31-L53)，要求基于最近历史对话复盘并优化技能
> **关联规范**：meta-rule #112（experimental）/ step 275 / B-REVIEW-332 / B-REVIEW-333 / B-REVIEW-334 / F-REVIEW-245 / 模式 AH / T005-T007

---

## I.1 复盘范围

| 范围 | 内容 | 来源 |
|------|------|------|
| 案例 D | 健康检查显示 Cookie 无效，但实时搜索仍能正常查询商品 | 2026-07-26 当前对话 |

**问题现象**：用户在反爬登录管理界面点击"健康检查"，结果显示 cookie 无效；但切换到任务详情做实时搜索，仍能正常拉取商品列表。两个功能对同一份 cookie 状态给出矛盾判定。

---

## I.2 维度一：成功执行任务的完整步骤

### 案例 D：双数据源（JSON 持久化层 + 浏览器运行时层）不一致

**完整解决步骤**：

1. **链路梳理**：用 Explore agent 并行搜索"健康检查"与"实时搜索"两条代码路径
   - 健康检查：`/api/anticrawl/health` → `LoginOrchestrator.check_health` → `SessionHealthChecker.check` → `cookie_checker()` 闭包
   - 实时搜索：`/api/tasks/{task_id}/links/live` → `_ensure_live_search_cookies` → `collector.live_search` → `collector.search`

2. **数据源定位**（关键转折点）：
   - 健康检查 `cookie_checker` 读 [api_anticrawl.py:54-56](../../../src/xianyu_hunter/web/routes/api_anticrawl.py#L54-L56) `store._read_json()` → **JSON 文件**
   - 实时搜索用 [api_task_links.py:111](../../../src/xianyu_hunter/web/routes/api_task_links.py#L111) `await container.browser.get_cookies()` → **浏览器运行时内存**
   - 两者使用**不同的数据源**

3. **根因分析**：识别 8 个导致"健康检查失败但搜索成功"的具体代码原因
   - JSON 落后于浏览器内存（MTOP Set-Cookie 回写失败/部分回写）
   - `_m_h5_tk` 处理策略相反（健康检查被动判定过期，实时搜索主动刷新续期）
   - `last_session_invalid` 粘性标志不对称（实时搜索 DOM 回退可重置，健康检查只读不重置）
   - `/cookies/layers` 的兜底机制不作用于健康检查
   - 健康检查 identity 层要求"至少一个"，实时搜索只检查 `cookie2/sgcookie/unb`
   - JSON 30 秒 TTL 缓存窗口期
   - MTOP Set-Cookie 回写 JSON 失败被静默吞掉（debug 级别日志）
   - 健康检查 expires 字段遍历所有 cookie，实时搜索只检查关键 cookie

4. **代码验证**：Read 关键文件确认 agent 分析结论准确
   - [api_anticrawl.py:51-140](../../../src/xianyu_hunter/web/routes/api_anticrawl.py#L51-L140) cookie_checker 闭包
   - [api_task_links.py:91-248](../../../src/xianyu_hunter/web/routes/api_task_links.py#L91-L248) _ensure_live_search_cookies
   - [_search.py:279-313](../../../src/xianyu_hunter/modules/collector/_search.py#L279-L313) _sync_response_cookies_to_context
   - [_search.py:557-591](../../../src/xianyu_hunter/modules/collector/_search.py#L557-L591) _ensure_fresh_m5tk

5. **修复设计**：4 项修复整合到 cookie_checker 改造
   - 修复1：健康检查增加浏览器内存兜底（JSON 判定无效时复核）
   - 修复2：`_sync_response_cookies_to_context` 回写异常 `debug` → `warning`
   - 修复3：JSON 中 `_m_h5_tk` 过期时，从浏览器内存读取最新 token 回写 JSON
   - 修复4：expires 检查范围与实时搜索对齐（仅关键 cookie：identity + session 层）

6. **实施修改**（3 文件）：
   - [session_health.py](../../../src/xianyu_hunter/modules/session_health.py)：`_check_cookies` 用 `inspect.isawaitable` 兼容 async 检查器；类型签名 `Callable[[], bool]` → `Callable[[], bool | Awaitable[bool]]`
   - [api_anticrawl.py](../../../src/xianyu_hunter/web/routes/api_anticrawl.py)：`cookie_checker` 改为 async + 新增 `_try_refresh_m5tk_from_browser` + `_browser_cookies_fallback` 两个辅助函数
   - [_search.py](../../../src/xianyu_hunter/modules/collector/_search.py)：回写异常 `logger.debug` → `logger.warning`

7. **验证**：
   - `py_compile` 语法检查通过
   - `pytest` 跑 5 个相关测试文件，126 passed + 3 failed
   - `git stash` 对比确认 3 个失败在修改前就存在（测试数据 `"token_123"` 被 `is_m5tk_expired` 误判过期 + 固定 timestamp 随时间过期），**未引入新失败**

---

## I.3 维度二：任务执行过程中的不确定性与失败点

| 编号 | 不确定性/失败点 | 教训 |
|------|-----------------|------|
| U1 | `cookie_checker` 是同步函数，但浏览器内存读取 `get_cookies()` 是 async，无法直接 await | 检查器接口设计时应预留 async 兼容性，避免后期改造牵连类型签名变更 |
| U2 | 一开始考虑用 `asyncio.run()` 在同步函数内跑协程，但 FastAPI 已有运行中事件循环会报错 | 同步函数内调用 async 资源的方案需先确认调用上下文是否已在事件循环中 |
| U3 | 最终方案是改造 `_check_cookies` 用 `inspect.isawaitable(result)` 兼容 sync/async 检查器 | 接口兼容层应放在调用方而非被调用方，保持检查器实现自由 |
| U4 | 测试 `test_cookie_valid_when_layer_not_initialized` 失败，最初以为是本次修改引入 | 修改后跑测试失败时，必须用 `git stash` 对比确认是否为既有失败，避免误归因 |
| U5 | 测试数据 `"token_123"` 被造为 _m_h5_tk 值，但 `is_m5tk_expired` 会解析 `_` 后的 timestamp，"123" 被判为 1970 年的过期 token | 测试数据中带下划线的 token 值需用未来 timestamp（如 `token_<未来ms>`），或用无下划线值（如 `token`） |
| U6 | 修复4（expires 范围对齐）一度担心放过 tracking 层 cookie 过期 | 检查器判定范围应与实际消费者依赖范围对齐，消费者不依赖的字段过期不影响功能，不应触发误判 |
| U7 | 修复3"主动刷新 token"原本想调用 `_ensure_fresh_m5tk`，但需要 page 对象且耗时 4s+，会拖慢健康检查 | 健康检查不应触发耗时操作；改为"从浏览器内存读取最新 token 回写 JSON"的被动同步，避免主页导航开销 |
| U8 | MTOP Set-Cookie 回写 JSON 失败原本是 `logger.debug`，导致问题完全不可观测 | 回写/同步失败的日志级别必须与影响匹配——影响数据一致性的用 warning，纯查询失败的用 debug |

---

## I.4 维度三：可抽象的固定流程与判断逻辑

### 流程 14：双数据源一致性保障流程（本案新增，落地为 step 275）

```
1. 识别双数据源：当系统存在"持久化层（JSON/DB/文件）+ 运行时层（内存/缓存/浏览器上下文）"时，
   必须识别两者是否会被不同消费者读取。若会，进入双数据源一致性保障流程。

2. 判定逻辑：检查器（健康检查/状态查询）以持久化层为主源判定时，
   主源判定无效必须回退运行时层兜底复核，以运行时层为最终判定标准。
   - 因为运行时层是实际消费者使用的数据源，与功能可用性直接对应
   - 持久化层可能因回写失败/部分回写/缓存窗口期而落后于运行时层

3. 同步机制：运行时层更新后必须回写持久化层，回写失败必须 warning 级别日志（可观测）。
   - 回写失败会导致下次检查器读持久化层时误判
   - debug 级别会导致问题不可观测，排查困难

4. 检查器与消费者判定标准对齐：
   - 检查器的检查范围（字段/cookie/状态）必须与实际消费者依赖范围一致
   - 不应让检查器检查消费者不依赖的字段（如 tracking 层 cookie 过期不影响搜索）
   - 不应让检查器只检查消费者依赖字段的子集（如只查 identity 不查 session）

5. 检查器接口 async 兼容：
   - 检查器接口应支持 sync 和 async 两种实现
   - 调用方用 `inspect.isawaitable(result)` 兼容处理
   - 类型签名为 `Callable[[], bool | Awaitable[bool]]`
```

### 流程 15：异常可观测性分级规范（本案新增，落地为 step 276）

```
异常处理 except 分支的日志级别必须与影响匹配：

| 异常类型 | 日志级别 | 理由 |
|---------|---------|------|
| 回写/同步失败 | warning | 影响数据一致性，需排查；静默会导致下次检查误判 |
| 配置缺失/解析失败 | warning | 影响功能可用性 |
| 查询失败（不影响主流程） | debug | 避免噪音，但有 fallback 兜底 |
| 兜底路径触发 | info | 标记走了非主路径，便于统计 |
| 关键路径失败 | error | 需立即处理 |

反模式：所有 except 分支统一用 debug 静默吞掉——导致问题不可观测，排查困难。
```

### 流程 16：检查器接口异步兼容模式（本案新增，落地为 step 277）

```
当检查器需要读取 async 资源（浏览器内存/HTTP 客户端/数据库异步驱动）时：

1. 检查器接口类型签名：`Callable[[], bool | Awaitable[bool]]`
2. 调用方处理：
   ```python
   result = self._checker()
   if inspect.isawaitable(result):
       result = await result
   return result
   ```
3. 同步检查器直接返回 bool，异步检查器返回 coroutine
4. 不强制所有检查器统一为 async（避免无 async 需求的检查器被迫包装）

适用场景：检查器可能访问 async 资源（浏览器/HTTP/DB）的系统
不适用场景：纯内存状态检查器（无需 async 兼容）
```

---

## I.5 维度四：适用场景与不适用场景

### 流程 14（双数据源一致性）适用性

**适用场景**：
- 持久化层 + 运行时层双数据源（cookie JSON + 浏览器内存、DB + Redis 缓存、文件 + 内存映射）
- 检查器与实际消费者分离的场景（健康检查 vs 业务流程、监控探测 vs 实际请求）
- 存在回写失败/部分回写/缓存窗口期的场景

**不适用场景**：
- 单一数据源场景（无需兜底）
- 检查器与消费者同源的场景（同读一个数据源，不存在不一致）
- 强一致性要求场景（应使用事务而非兜底）

### 流程 15（异常可观测性分级）适用性

**适用场景**：所有 except 分支（ universal ）
**不适用场景**：无（这是通用规范）

### 流程 16（检查器接口异步兼容）适用性

**适用场景**：
- 检查器可能访问 async 资源的系统（浏览器自动化、HTTP 客户端、异步 DB 驱动）
- 检查器接口需同时支持 sync 和 async 实现的场景

**不适用场景**：
- 纯同步检查器（如纯内存状态检查），无需引入 async 兼容复杂度
- 全 async 检查器（可直接强制 async 接口，无需兼容层）

---

## I.6 技能优化落地

### xianyu-hunter-dev
- 新增 [dual-data-source-consistency.md](dual-data-source-consistency.md) 编码规范（流程 14-16 完整定义）
- 更新 [cookie-state-recovery-patterns.md](cookie-state-recovery-patterns.md) 补充"健康检查浏览器内存兜底"模式
- 更新 version-history.md → v4.69.0

### xianyu-backend-code-review
- 新增 B-REVIEW-332 双数据源兜底复核（对应流程 14）
- 新增 B-REVIEW-333 检查器与消费者判定标准对齐（对应流程 14 第 4 条）
- 新增 B-REVIEW-334 异步检查器接口兼容（对应流程 16）
- 强化 B-REVIEW-152 关键路径异常保留完整 traceback → 异常可观测性分级（对应流程 15）
- 更新 consistency-and-state-checks.md、checkpoints-index.md、version-changelog.md → v4.69.0

### xianyu-frontend-code-review
- 新增 F-REVIEW-245 健康状态展示与后端实际状态一致性
- 更新 state-and-consistency-checks.md、checkpoints-index.md、version-changelog.md → v4.68.0

### xianyu-auto-testing
- 新增 T005 健康检查端到端测试（JSON 无效 + 浏览器内存有效 → 健康检查通过）
- 新增 T006 双数据源一致性验证（MTOP Set-Cookie 回写失败 → warning 日志 + 兜底通过）
- 新增 T007 异步检查器兼容验证（sync/async 检查器均能被 _check_cookies 正确调用）
- 新增 [health-check-e2e-test.md](health-check-e2e-test.md) 测试文档
- 更新 config.yaml、SKILL.md

---

## I.7 总结

本案核心教训：**检查器与消费者使用不同数据源时，必须以运行时层为最终判定标准，否则会产生"检查器判定无效但功能正常"的矛盾现象**。

这种矛盾现象的危害：
1. 用户体验差：看到"cookie 无效"但功能正常，无法判断该不该重新登录
2. 误导运维：可能触发不必要的重新登录或重启操作
3. 掩盖真问题：当 cookie 真正失效时，"狼来了"效应导致用户不再信任健康检查

修复后行为：健康检查与实时搜索使用一致的判定标准（运行时层兜底），消除矛盾现象；回写失败可观测（warning 日志），便于排查。
