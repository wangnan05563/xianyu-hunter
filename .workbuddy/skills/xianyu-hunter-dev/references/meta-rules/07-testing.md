# 测试规范
> 包含元规范 #13 - #110

## 13. 测试隔离规范

1. **生产路径 patch**：fixture 必须用 `tmp_path` 隔离生产路径，禁止直接读写生产文件
2. **测试数据可识别**：带 `test_fixture_` 前缀/`__test__` 后缀
3. **patch 验证**：fixture 加载后 `assert not os.path.exists(production_path)` 验证
4. **遍历 sys.modules**：禁止硬编码模块名列表，必须遍历 `sys.modules` 找所有持目标属性的模块
5. **importlib.import_module**：禁止 `__import__`（返回顶层包而非子模块）
6. **数据污染应急 5 步**：停止服务 → 删除污染文件 → 修复 conftest → 重跑测试 → 通知用户

## 46. 测试同步责任原则（TEST-SYNC-RESPONSIBILITY）🆕v4.35

> 与 B-REVIEW-176（backend 接口签名变更同步审查，v4.35 待落地）/ F-REVIEW-134（前端异步函数调用签名匹配审查，v4.39 待落地）对应。

后端接口签名变更（新增 / 删除 / 重命名参数）、异步同步重构（async → sync 或反之）、mock 字段集与生产 Pydantic 模型同步时，必须同步更新所有调用方测试，禁止「改了生产代码忘了改测试」导致测试失败或假阳性。

1. **签名变更同步**：方法签名新增参数后必须 grep 所有调用点（包括测试中的 mock 调用）确认传递新参数
2. **异步同步重构同步**：`async def` → `def` 或反之时，测试中的 `AsyncMock` ↔ `MagicMock` 必须同步切换
3. **mock 字段集同步**：测试 mock 数据必须与生产 Pydantic 模型字段集 1:1 对齐，禁止用 `as ModelType` 类型断言绕过完整性检查
4. **外部依赖隔离同步**：测试中依赖外部资源（keyring / env / 文件系统 / 网络）时必须 patch 为 None 或 mock，禁止依赖生产 fallback 导致测试不可重复
5. **配置驱动**：签名变更检查点、mock 类型映射表、外部依赖类型清单从 `config.yaml#test_synchronization` 读取

**关键约束**：
- 方法签名新增参数但测试调用未传新参数 → 视为违规（`TypeError: missing required positional argument`）
- 生产代码 `async def` 但测试用 `MagicMock`（或反之）→ 视为违规（mock 类型不匹配）
- mock 数据用 `as Item` / `as Task` 绕过字段检查 → 视为违规（与 B-REVIEW-TEST-MOCK-SYNC 一致）
- 测试依赖 keyring fallback → 视为违规（测试环境不可重复）
- 检查点清单硬编码在代码中 → 视为违规（应从 config 读）

**判断信号**：
- `git diff` 显示生产代码方法签名变更但同 PR 内 `tests/` 无对应修改 → 同步缺失
- `grep "AsyncMock" tests/` 但生产代码对应方法已改为 `def` → mock 类型不匹配
- `grep "as Item\b\|as Task\b\|as Order\b" tests/` → 类型断言绕过字段检查
- `grep "get_secret\|os.environ\.\[" tests/` 但无 `patch(..., return_value=None)` → 外部依赖未隔离
- 测试在 CI 通过但本地失败（或反之）→ 环境依赖问题

**适用**：后端接口签名重构（新增 / 删除 / 重命名参数）；async / await 重构（同步异步切换）；测试 mock 数据与生产 Pydantic 模型对齐；外部依赖（keyring / env / 文件系统 / 网络）测试隔离。
**不适用**：纯内部实现重构（不改变接口签名）；新增功能（不破坏现有测试）；一次性验证脚本（无长期维护成本）。

**历史教训**：`manual_takeover` 接口签名加了 `request` 参数（用于多用户隔离读取 `request.state.user_id`），但 `test_manual_takeover_lock.py` 未传 `request`，触发 `TypeError: missing 1 required positional argument: 'request'`。修复：创建 `mock_request = MagicMock()` 并设置 `mock_request.state.user_id = "default"` 后传入。同期 `worker.py` 重构为同步代码后 `test_dingtalk_notify_integration.py` 仍用 `AsyncMock` 导致断言失败，改为 `MagicMock` 后通过。建立 #46 强制同步规则。

## 47. 外部依赖隔离测试可重复性（EXTERNAL-DEP-ISOLATION）🆕v4.35

> 与 B-REVIEW-177（backend 外部依赖隔离审查，v4.35 待落地）/ F-REVIEW-135（前端 mock 类型与生产同步审查，v4.39 待落地）对应。

测试中依赖外部资源（keyring / 环境变量 / 文件系统 / 网络 / 系统 API）时必须显式 patch 为 None 或 mock，禁止依赖生产代码的 fallback 机制（如 keyring 不可用时回退到 env / yaml），避免测试环境与生产环境配置不一致导致测试不可重复（CI 通过本地失败或反之）。

1. **外部依赖清单识别**：从 `config.yaml#external_dependency_isolation.dependency_types` 读取外部依赖类型清单（keyring / env / file / network / system_api）
2. **patch 强制**：测试中调用任何外部依赖函数（如 `get_secret` / `os.environ[...]` / `Path(...).read_text()` / `httpx.get`）必须 `with patch(..., return_value=None)` 或 `MagicMock()` 显式隔离
3. **fallback 禁用**：禁止依赖生产代码的 fallback（如 `secret = get_secret(name) or os.environ.get(name) or read_from_yaml(name)`），测试中必须 patch 全部 3 层 fallback
4. **可重复性验证**：测试在「无外部依赖」环境下（如 Docker 容器无 keyring / 无 env / 无网络）必须仍能通过
5. **配置驱动**：依赖类型清单、隔离策略映射表、fallback 层数从 config 读取

**关键约束**：
- 测试中调用 `get_secret` 但无 `patch("...get_secret", return_value=None)` → 视为违规
- 测试中 `os.environ["XXX"]` 但无 `monkeypatch.setenv` 或 `patch.dict(os.environ, ...)` → 视为违规
- 测试在 CI 通过但本地失败（或反之）→ 视为环境依赖问题
- 依赖类型清单硬编码在测试中 → 视为违规（应从 config 读）

**判断信号**：
- `grep "get_secret\|keyring\.get_password" tests/` 但同测试无 `patch` → keyring fallback 未隔离
- `grep "os\.environ\[" tests/` 但同测试无 `monkeypatch\.setenv\|patch\.dict` → env 依赖未隔离
- `grep "Path\([^)]*\)\.read_text\(\)\|open\([^)]*\)\.read\(\)" tests/` 但无 `tmp_path` fixture → 文件系统依赖未隔离
- `grep "httpx\.get\|requests\.get\|aiohttp\.ClientSession" tests/` 但无 `respx` / `responses` / `MagicMock` → 网络依赖未隔离
- 测试结果随环境变化（CI vs 本地 / Windows vs Linux）→ 环境依赖问题

**适用**：依赖 keyring / 环境变量 / 文件系统 / 网络 / 系统 API 的测试；CI/CD 需可重复的场景；跨平台测试（Windows / Linux / macOS）。
**不适用**：纯函数测试（无外部依赖）；使用 pytest fixture 已隔离的测试（fixture 内部已 patch）；一次性验证脚本（无长期维护成本）；集成测试（故意依赖真实外部资源）。

**历史教训**：`test_notifier_new_channels.py` 中 `DingTalkNotifier(webhook_url="...", secret="")` 测试期望 `secret=""` 时不发送请求，但生产代码 `get_secret` 在 keyring 不可用时 fallback 到 keyring 真实值（测试机已配置 dingtalk secret），导致 `secret=""` 但实际读到 keyring 中的 secret，触发真实钉钉请求，断言失败。修复：在两个测试函数中都加 `with patch("...dingtalk.get_secret", return_value=None):` 显式隔离。建立 #47 强制隔离规则。

> 📖 详细测试同步责任原则、签名变更检查点、mock 类型映射表、外部依赖隔离策略、配置节点定义见 [test-synchronization-and-isolation.md](test-synchronization-and-isolation.md)。

---

# 调度器运行时治理元规范（48-51）🆕v4.36.0

> 基于 2026-07-07 "任务管理自动执行逻辑审查"修复的 5 个问题（BatchRefreshScheduler 运行时禁用无效 / CookieSyncScheduler 无法运行时禁用 / scheduler.py 异常重试等待硬编码 300s / `_resume_cooldown` 字典内存泄漏 / Cron 模式无最小间隔校验），使用 Sequential Thinking 4 维度复盘法——成功步骤/不确定性与失败点/可抽象的固定流程与判断逻辑/适用场景与不适用场景，提炼 4 条新元规范。门槛校验：#48/#49/#50 各有 ≥3 个相似 bug 达标立正式规范，#51 仅 1 个相似 bug 按门槛规则 #36 标 experimental 标签预沉淀。

## 55. mock 同步与边界精确性（MOCK-SYNC-BOUNDARY）🆕v4.37

> 与维度 20 测试建议（B-REVIEW-180）/ 维度 12 可测试性（F-REVIEW-146）对应。

**与 #47 EXTERNAL-DEP-ISOLATION 的边界**：
- #47 关注"是否要 patch"（强制 patch 外部依赖）
- 本规范关注"如何 patch"（patch 的类型/边界/字段/副作用）

修改被测代码后必须同步 mock：mock 类型与被 mock 对象的同步/异步特性必须一致，patch 必须 patch 实际调用点而非定义点，mock 数据必须覆盖完整字段集。

1. **类型匹配**：同步函数用 `MagicMock`，异步函数用 `AsyncMock`，禁止混用
2. **patch 边界**：patch 必须 patch 实际调用点（如 `worker.get_secret`）而非定义点（如 `secrets.get_secret`）
3. **字段完整性**：mock 数据必须覆盖被测代码访问的所有字段，禁止部分 mock
4. **副作用验证**：测试必须断言"副作用未发生"（如未发起真实网络请求 / 未写文件 / 未发邮件）

**关键约束**：
- 同步函数用 `AsyncMock` → CRITICAL（mock 类型错配）
- 异步函数用 `MagicMock` → CRITICAL
- patch 路径与实际调用路径不一致 → WARNING
- mock 数据缺字段 → 测试可能 NPE，视为不完整

**判断信号**：
- `grep "AsyncMock" <test_file>` 但被 mock 函数是同步函数（无 `async def`）→ 违规
- `grep "MagicMock" <test_file>` 但被 mock 函数是 `async def` → 违规
- `patch("module.function")` 但实际调用是 `from module import function; function()` → patch 边界错误

**适用**：所有 unit test / 集成测试中的 mock 替身
**不适用**：E2E 测试（应使用真实环境）、快照测试（snapshot test）

**历史教训**：`test_dingtalk_notify_integration.py` 用 `AsyncMock` 但 `worker.py` 的 `filter_new` 已改为同步实现，导致 `await` 在同步对象上失败。`test_notifier_new_channels.py` patch `get_secret` 位置错误导致 webhook_url/secret 实际不为空，测试发起真实钉钉请求。修复：AsyncMock 改 MagicMock 对齐同步实现 / patch get_secret 返回 None 确保真正为空 / test_manual_takeover_lock 构造 mock request 含 user_id。

> 📖 详见 [testing.md](../assets/guides/coding-rules/testing.md) step 192。

## 110. 类型注解契约对齐（TYPE-ANNOTATION-CONTRACT-ALIGNMENT）🆕v4.67.0 experimental

**问题**：后端函数返回类型注解（如 `-> list[str]`）与实际返回结构（如 `list[dict]`）不一致，且与前端 `types.ts` 声明（如 `Array<{url, hash}>`）也不一致，导致前端访问字段时取到 `undefined`。既有规范 #35/#88/#108 假设"后端为权威源"或"后端注解=实际返回"，未覆盖"后端类型注解本身错误"且"前端 types.ts 反而是真相源"的反向情况。

**核心规则**：
1. 返回复杂结构（`list[dict]` / `list[TypedDict]` / 嵌套 Pydantic BaseModel / `dict[str, Any]`）的后端函数，必须保证三方契约对齐：后端函数返回类型注解 ↔ 后端 Pydantic ResponseModel ↔ 前端 types.ts
2. 权威源优先级：① Pydantic ResponseModel（首选）② 前端 types.ts（反向校验源，当无 ResponseModel 时）③ 后端函数类型注解（最弱，仅辅助参考）
3. 单元测试必须断言**完整结构**（字段名 + 字段类型 + 至少一个字段的值），禁止仅断言长度或顶层类型

**判断信号**：
- `grep "def.*->.*list\[" src/` 或 `grep "def.*->.*dict" src/` 找返回复杂结构的函数 → 对照前端 types.ts 同名字段类型
- 单元测试 `for h in data["..."]:` 后仅 `assert len(h) == N` → 违反规则3（未断言完整结构）
- 前端显示 `undefined` 且后端函数返回类型注解为基本类型（`list[str]`）→ 违反规则1（三方不对齐）

**配置参数**：`typeAnnotationContract` 节点（enabled / complexReturnTypes / alignmentSources / authoritativeSource / fallbackAuthoritativeSource / testAssertionLevel / observationPeriodQuarters / observationEndDate / promotionThreshold / applicableScenarios / nonApplicableScenarios）

**适用**：返回 list[dict]/list[TypedDict]/嵌套 Pydantic 模型的后端函数；前后端分离 API 端点；无 ResponseModel 但有前端消费方的端点
**不适用**：返回基本类型（str/int/bool）；纯内部 helper（无前端消费方）；动态结构通用序列化（结构由 DB schema 决定）；已有 Pydantic ResponseModel 严格校验的端点

**与既有规范的关系**：
- #35（前后端字段契约单一可信源）：管"字段名/存在性"，本规范管"类型注解正确性"，互补
- #88（CROSS-LAYER-CONTRACT-SYNC）：管"跨层同步动作"，本规范管"注解与实际返回一致性"，互补
- #108（CROSS-LAYER-CLOSED-LOOP）：管"git diff 半边修改"，本规范管"函数签名注解本身错误"，互补

**历史教训**：2026-07-26 AI 深度鉴伪图片哈希 Bug。后端 `_compute_image_url_hash(image_urls: list[str]) -> list[str]` 实际返回 `[hashlib.md5(url).hexdigest()[:12] for url in image_urls]`（纯字符串列表），但前端 types.ts 声明 `Array<{ url: string; hash: string }>`。前端渲染 `h.url`/`h.hash` 取到 undefined，显示 `undefined → undefined`（重复 9 次）。本案特殊性：前端 types.ts 反而是契约真相源（已正确），后端偏离——既有规范 #35/#88 假设"后端为权威源"未覆盖此反向情况。修复：后端改为返回 `list[dict]`（`[{"url": url, "hash": ...}]`），同步更新类型注解和单元测试断言。

**experimental 升正条件**：1 季度内（截至 2026-10-26）同类根因再发 ≥ 2 次

**对应 step**：step 273（type-annotation-contract.md）。
