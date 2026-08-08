# 模式 AA：资源创建幂等性与状态闭环回归测试

> **版本**：v2.3.0（2026-07-25 第八轮复盘落地）
> **关联复盘**：`xianyu-hunter-dev/references/retrospective-2026-07-25-r2.md`（第八轮复盘）
> **关联规范**：`xianyu-hunter-dev` 规范 31（资源创建接口幂等性设计）+ 规范 32（前端 async handler 三分支完整性）
> **配套检查点**：
> - 后端：`xianyu-backend-code-review` v4.64.0 B-REVIEW-313~315
> - 前端：`xianyu-frontend-code-review` v4.63.0 F-REVIEW-233~235

---

## 测试目标

验证反爬登录会话启动矛盾修复的三层防护机制在不同触发场景下保持有效，防止"UI 状态与后端响应不一致"的矛盾现象再次出现。

## 测试范围

| 层 | 文件 | 检查点 |
|---|---|---|
| 后端路由层 | `src/xianyu_hunter/web/routes/api_anticrawl.py` | B-REVIEW-313 IDEMPOTENT-RESOURCE-CREATION |
| 后端响应层 | `src/xianyu_hunter/web/routes/api_anticrawl.py` | B-REVIEW-314 OPERATION-RESULT-CONTRACT |
| 后端→前端同步 | `src/xianyu_hunter/web/routes/api_anticrawl.py` + `frontend/src/api/types.ts` | B-REVIEW-315 FRONTEND-STATE-REFRESH-CLOSED-LOOP |
| 前端 API 层 | `frontend/src/api/anticrawl.ts` | F-REVIEW-234 API-RETURN-TYPE-CONTRACT |
| 前端 handler 层 | `frontend/src/pages/AntiCrawl/index.tsx` | F-REVIEW-233 ASYNC-HANDLER-THREE-BRANCH |
| 前端 UI 层 | `frontend/src/pages/AntiCrawl/index.tsx` | F-REVIEW-235 UI-BACKEND-STATE-CONSISTENCY |

---

## 测试用例矩阵

### AA-T01：后端 `/session/start` 幂等行为单元测试（B-REVIEW-313）

**场景**：会话已被 `trigger_session_start()` 自动启动后，用户再次点击"启动会话"按钮

**测试步骤**：
1. 调用 `POST /api/anticrawl/session/start`，模拟会话已活跃场景
2. 验证响应结构

**预期**：
- 响应 JSON 包含 `ok: true`
- 响应 JSON 包含 `already_active: true`
- 响应不包含 `error` 字段（或 `error` 为空）
- 不重复创建资源（不调用 `playwright.launch` 二次启动）

**测试代码示例**：
```python
def test_start_session_when_already_active_returns_already_active_flag(client, auth_cookie):
    """会话已活跃时，/session/start 必须返回 ok:True + already_active:True，禁止 ok:False"""
    # 预置：会话已被自动启动
    orchestrator = get_orchestrator()
    orchestrator._session_active = True

    resp = client.post("/api/anticrawl/session/start", cookies=auth_cookie)

    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["already_active"] is True
    assert "error" not in data or not data["error"]
```

### AA-T02：OperationResult 响应结构契约测试（B-REVIEW-314）

**场景**：所有写操作响应必须用统一 OperationResult 模型

**测试步骤**：
1. 调用所有写操作端点：`/session/start` / `/session/stop` / `/cookies/update` / `/cookies/invalidate` / `/strategy/set`
2. 验证响应字段集

**预期**：
- 必填字段 `ok: bool` 存在
- 幂等标志字段（`already_active` / `already_exists`）可选存在
- 错误字段（`error` / `error_code` / `detail`）可选存在
- 不存在 `msg` / `message`（在错误场景）等非契约字段

### AA-T03：前端 `OperationResult` 类型定义完整性测试（F-REVIEW-234）

**场景**：前端 `types.ts` 中 `OperationResult` 接口必须包含 `already_active` 字段

**测试步骤**：
1. 读取 `frontend/src/api/anticrawl.ts` 文件内容
2. 提取 `OperationResult` 接口定义
3. 验证字段集

**预期**：
- 接口名：`OperationResult`
- 必填字段：`ok: boolean`
- 可选字段：`already_active?: boolean`、`already_exists?: boolean`、`error?: string`、`error_code?: string`、`detail?: string`、`message?: string`

### AA-T04：前端 `startSession` 返回类型契约测试（F-REVIEW-234）

**场景**：`startSession` 函数返回类型必须显式声明为 `Promise<OperationResult>`

**测试步骤**：
1. 读取 `frontend/src/api/anticrawl.ts`
2. 提取 `startSession` 函数签名
3. 验证返回类型

**预期**：
- 返回类型为 `Promise<OperationResult>`，禁止 `Promise<any>` / `Promise<unknown>`

### AA-T05：前端 `handleStartSession` 三分支完整性测试（F-REVIEW-233）

**场景**：`handleStartSession` 的 try/else/catch 三分支都必须显示具体错误 + 调用 `loadSession()`

**测试步骤**：
1. 静态扫描 `frontend/src/pages/AntiCrawl/index.tsx` 的 `handleStartSession` 函数
2. 验证 success 分支：调用 `loadSession()`
3. 验证 else 分支：显示 `resp.error` 字段（非固定文案）+ 调用 `loadSession()`
4. 验证 catch 分支：用 `extractApiError(e)` + 调用 `loadSession()`

**预期**：
- 三分支都有 `loadSession()` 调用
- else 分支不出现 `message.error('启动会话失败')` 等固定文案
- catch 分支不出现 `message.error('启动失败')` 等无信息文案

### AA-T06：UI 状态强制刷新测试（F-REVIEW-235）

**场景**：写操作完成后，无论 success/else/catch 都必须刷新业务状态

**测试步骤**：
1. Playwright 启动浏览器，导航到反爬页面
2. 模拟会话已活跃状态（后端预置 `session._active = True`）
3. 点击"启动会话"按钮
4. 等待响应
5. 验证 UI 显示的会话状态

**预期**：
- 响应成功时：UI 显示"会话已活跃"（基于 `already_active` 标志）+ 状态为"已启动"
- 响应失败时：UI 显示后端具体错误 + 状态仍为"已启动"（基于 `loadSession()` 拉取的最新状态）
- 不出现"启动失败"但状态显示"已启动"的矛盾

### AA-T07：业务状态来源验证测试（F-REVIEW-235）

**场景**：业务状态（会话活跃）必须来自 API 响应，禁止前端 `useState` 独立维护

**测试步骤**：
1. 静态扫描 `frontend/src/pages/AntiCrawl/index.tsx`
2. 查找业务状态 `useState` 声明
3. 验证状态来源

**预期**：
- 业务状态 `sessionStatus` 通过 `loadSession()` 从后端拉取
- 不存在 `setActive(true)` 等独立维护业务状态的代码
- `loading` 状态独立于业务状态

---

## 静态扫描信号

```bash
# 后端：检查 /session/start 是否幂等
grep -n "session/start" src/xianyu_hunter/web/routes/api_anticrawl.py
# 后接 already_active 返回 → 通过；返回 ok:False → 违规

# 后端：检查 OperationResult 字段
grep -n "JSONResponse\|return.*ok.*True\|return.*ok.*False" src/xianyu_hunter/web/routes/api_anticrawl.py

# 前端：检查 OperationResult 接口
grep -n "interface OperationResult\|type OperationResult" frontend/src/api/anticrawl.ts
# 缺少 already_active 字段 → 违规

# 前端：检查 startSession 返回类型
grep -n "export async function startSession" frontend/src/api/anticrawl.ts
# 返回 Promise<any> → 违规

# 前端：检查 handleStartSession 三分支
grep -n "handleStartSession\|loadSession\|message\.error" frontend/src/pages/AntiCrawl/index.tsx
# 三分支无 loadSession → 违规
```

---

## 测试报告输出

测试完成后输出结构化报告：

```markdown
## 模式 AA 测试报告

### 测试概览
- 测试时间：YYYY-MM-DD HH:MM
- 测试范围：反爬登录会话启动幂等性与状态闭环
- 总用例数：7
- 通过：N
- 失败：N
- 跳过：N

### 检查点状态
| 检查点 | 静态扫描 | 运行时验证 | 单元测试 | 状态 |
|---|---|---|---|---|
| B-REVIEW-313 IDEMPOTENT-RESOURCE-CREATION | ✅/❌ | ✅/❌ | AA-T01 ✅/❌ | PASS/FAIL |
| B-REVIEW-314 OPERATION-RESULT-CONTRACT | ✅/❌ | ✅/❌ | AA-T02 ✅/❌ | PASS/FAIL |
| B-REVIEW-315 FRONTEND-STATE-REFRESH-CLOSED-LOOP | ✅/❌ | ✅/❌ | AA-T03 ✅/❌ | PASS/FAIL |
| F-REVIEW-233 ASYNC-HANDLER-THREE-BRANCH | ✅/❌ | ✅/❌ | AA-T05 ✅/❌ | PASS/FAIL |
| F-REVIEW-234 API-RETURN-TYPE-CONTRACT | ✅/❌ | ✅/❌ | AA-T03/T04 ✅/❌ | PASS/FAIL |
| F-REVIEW-235 UI-BACKEND-STATE-CONSISTENCY | ✅/❌ | ✅/❌ | AA-T06/T07 ✅/❌ | PASS/FAIL |

### 违规清单
（如有违规项列出文件路径、行号、违规类型、严重等级）

### 修复建议
（引用对应 references 文档的修复方案）
```

---

## 适用与不适用场景

### 适用场景

- 反爬登录管理系统会话启动/停止矛盾回归测试
- 任何资源创建类接口（`/xxx/start` / `/xxx/create` / `/xxx/register` / `/xxx/launch`）的幂等性验证
- 前端 async handler 三分支完整性回归测试
- UI 与后端状态一致性回归测试
- 后端响应字段变更后的前端 types.ts 同步验证

### 不适用场景

- 纯查询接口（天然幂等，无需测试幂等行为）
- 计数器递增接口（非幂等设计）
- 一次性副作用接口（如发短信验证码，需用 token 防重）
- 前端纯 UI 状态（无后端同步需求）
