# 测试同步与外部依赖隔离实施指南

> **版本**：🆕 v4.35.0
> **关联元规范**：meta-rules #50（TEST-SYNC-RESPONSIBILITY）/ #51（EXTERNAL-DEP-ISOLATION）
> **关联审查检查点**：B-REVIEW-176 / B-REVIEW-177 / F-REVIEW-134 / F-REVIEW-135
> **配套文档**：[meta-rules.md](meta-rules.md) #50 / #51

---

## 一、概述

### 1.1 问题背景

测试同步缺失与外部依赖未隔离是两类高频回归根因：

- **测试同步缺失**：生产代码签名变更后未同步更新调用方测试，导致 `TypeError` 或 mock 类型不匹配，CI 时好时坏
- **外部依赖未隔离**：测试依赖 keyring / env / 文件系统 / 网络等外部资源，依赖生产 fallback 兜底，导致 CI 通过本地失败（或反之）

### 1.2 必要性

| 问题类型 | 直接危害 | 间接危害 |
|---|---|---|
| 测试同步缺失 | 测试失败 / 假阳性 | 重构阻力增大，团队回避改测试 |
| 外部依赖未隔离 | 测试环境相关 | CI/本地结果不一致，信任崩塌 |

本指南提供 #50 / #51 的可执行落地步骤，避免规范停留在口号层。

---

## 二、测试同步责任原则（对应 #50）

### 2.1 签名变更同步检查清单

> 方法签名变更（新增 / 删除 / 重命名参数）后必须按下表逐项检查：

| # | 检查点 | 验证方式 |
|---|---|---|
| 1 | 所有调用点已传新参数 | `grep -rn "<method_name>(" src/ tests/` |
| 2 | 测试中 mock 调用签名同步 | `grep "mock.*<method_name>" tests/` |
| 3 | 关键字参数 vs 位置参数一致性 | 检查 mock 是否用关键字参数 |
| 4 | 默认值变更是否影响测试断言 | 比对 `def` 行与测试期望值 |
| 5 | 类型注解变更同步到 mock 构造 | 检查 `MagicMock(spec=...)` |

### 2.2 异步同步重构 mock 类型映射表

> `async def` ↔ `def` 切换时，mock 类型必须同步切换：

| 生产代码 | 错误 mock 类型 | 正确 mock 类型 | 验证方式 |
|---|---|---|---|
| `async def foo()` | `MagicMock` | `AsyncMock` | `await foo()` 不报错 |
| `def foo()` | `AsyncMock` | `MagicMock` | `foo()` 不返回 coroutine |
| `async def foo()` + `await` | `MagicMock(return_value=X)` | `AsyncMock(return_value=X)` | `assert_awaited_once` |
| `def foo()` + 同步调用 | `AsyncMock` | `MagicMock` | `assert_called_once` |

**反模式**：用 `MagicMock(side_effect=CoroutineReturns(X))` 模拟 async——增加维护成本，禁止使用。

### 2.3 mock 字段集与 Pydantic 模型对齐检查

```python
# ✅ 正确：显式构造所有字段，字段缺失立即报错
def make_item() -> Item:
    return Item(
        id=1,
        name="test",
        status="active",
        created_at="2026-07-07T00:00:00Z",
    )

# ❌ 错误：用 as 断言绕过字段完整性检查
item = {"id": 1} as Item  # 缺字段不报错，新增字段时无告警
```

**检查规则**：mock 数据字段集必须与生产 Pydantic 模型 1:1 对齐；新增字段必须同步加入 mock 构造函数，禁止用 `as ModelType` 类型断言绕过完整性检查。

### 2.4 配置驱动参数说明（config.yaml#test_synchronization）

```yaml
# config.yaml
test_synchronization:
  enabled: true
  # 签名变更检查点清单（grep 范围）
  signature_change_checkpoints:
    - "src/"
    - "tests/"
  # mock 类型映射表（生产 → 测试）
  mock_type_mapping:
    async_to_sync: "AsyncMock -> MagicMock"
    sync_to_async: "MagicMock -> AsyncMock"
  # Pydantic 模型对齐严格度
  mock_field_alignment:
    strict: true  # true: 1:1 对齐；false: 允许子集
    bypass_keywords_blacklist:
      - "as Item"
      - "as Task"
      - "as Order"
  # 审查检查点编号（供 review skill 引用）
  review_checkpoints:
    backend: "B-REVIEW-176"
    frontend: "F-REVIEW-134"
```

---

## 三、外部依赖隔离测试可重复性（对应 #51）

### 3.1 外部依赖类型清单与隔离策略

| 依赖类型 | 典型调用 | 隔离策略 | 强制级别 |
|---|---|---|---|
| **keyring** | `get_secret(name)` | `patch("...get_secret", return_value=None)` | CRITICAL |
| **env** | `os.environ["XXX"]` | `monkeypatch.setenv` / `patch.dict(os.environ, ...)` | CRITICAL |
| **file** | `Path(...).read_text()` | `tmp_path` fixture | CRITICAL |
| **network** | `httpx.get` / `requests.get` | `respx` / `responses` / `MagicMock` | CRITICAL |
| **system_api** | `socket.gethostname` / `platform.system` | `patch(..., return_value=...)` | WARNING |

### 3.2 patch 强制模式示例

```python
# ✅ 正确：显式 patch 所有外部依赖，测试可在无 keyring / 无 env / 无网络环境运行
def test_external_api_call_isolated():
    with patch("...get_secret", return_value=None), \
         patch("...external_api_call", return_value={"status": "ok"}), \
         patch.dict(os.environ, {"ENV_FLAG": "test"}, clear=True):
        result = service.run()
        assert result.status == "ok"

# ❌ 错误：依赖生产 fallback 兜底
def test_external_api_call_unsafe():
    # 生产代码：secret = get_secret(name) or os.environ.get(name) or read_from_yaml(name)
    # 测试机已配置 keyring → 读到真实 secret → 触发真实请求
    result = service.run()  # CI 通过但本地失败（或反之）
```

### 3.3 fallback 禁用清单

> 生产代码常见的多层 fallback，测试中必须 patch 全部 3 层：

| Fallback 层 | 生产代码示例 | 测试 patch 方式 |
|---|---|---|
| L1 keyring | `get_secret(name)` | `patch("...get_secret", return_value=None)` |
| L2 env | `os.environ.get(name)` | `patch.dict(os.environ, {}, clear=True)` |
| L3 yaml | `read_from_yaml(name)` | `patch("...read_from_yaml", return_value=None)` |

**禁止**：只 patch L1 期望 L2/L3 兜底——测试机未配置 env/yaml 时通过，配置后失败。

### 3.4 可重复性验证方法

1. **Docker 隔离测试**：在 `python:3.x-slim` 容器中运行 `pytest`，无 keyring / 无 env / 无网络
2. **CI 与本地一致性**：CI 环境变量白名单化，本地通过 `direnv` / `dotenv` 复现
3. **跨平台验证**：Windows / Linux / macOS 三平台均跑 `pytest`（重点检查路径分隔符与换行符）
4. **网络断言**：测试运行期间禁用网络（`--block-network` 模式或 `iptables -A OUTPUT -j DROP`）

### 3.5 配置驱动参数说明（config.yaml#external_dependency_isolation）

```yaml
# config.yaml
external_dependency_isolation:
  enabled: true
  # 依赖类型清单（与 §3.1 表对应）
  dependency_types:
    - keyring
    - env
    - file
    - network
    - system_api
  # 隔离策略映射表
  isolation_strategy:
    keyring: "patch(return_value=None)"
    env: "monkeypatch.setenv / patch.dict"
    file: "tmp_path fixture"
    network: "respx / responses / MagicMock"
    system_api: "patch(return_value=...)"
  # fallback 层数（patch 深度）
  fallback_layers: 3
  # 审查检查点编号
  review_checkpoints:
    backend: "B-REVIEW-177"
    frontend: "F-REVIEW-135"
```

---

## 四、适用场景与不适用场景

### 4.1 适用场景

| 场景 | 适用规则 |
|---|---|
| 后端接口签名重构（新增 / 删除 / 重命名参数） | #50 |
| async / await ↔ sync 重构 | #50 |
| 测试 mock 数据与生产 Pydantic 模型对齐 | #50 |
| 测试依赖 keyring / env / 文件 / 网络 / 系统 API | #51 |
| CI/CD 需可重复的测试 | #51 |
| 跨平台测试（Windows / Linux / macOS） | #51 |

### 4.2 不适用场景

| 场景 | 不适用原因 | 替代方案 |
|---|---|---|
| 纯内部实现重构（不改接口签名） | 不触发同步问题 | 信任单元测试覆盖 |
| 新增功能（不破坏现有测试） | 无历史同步负担 | 仅需新增测试 |
| 纯函数测试（无外部依赖） | 无隔离需求 | 直接断言 |
| pytest fixture 已隔离 | fixture 内部已 patch | 信任 fixture |
| 一次性验证脚本 | 无长期维护成本 | 不强制 |
| 集成测试（故意依赖真实外部资源） | 隔离与目标冲突 | 标注 `@pytest.mark.integration` 跳过 |

---

## 五、历史教训摘要

> 完整排查过程见 [meta-rules.md](meta-rules.md) #50 / #51 历史教训段落，此处仅摘要根因与规则建立动机。

### 5.1 #50 TEST-SYNC-RESPONSIBILITY 根因摘要

- **症状**：`manual_takeover` 接口加 `request` 参数后测试 `TypeError: missing 1 required positional argument`
- **同期症状**：`worker.py` 重构为同步后测试仍用 `AsyncMock` 导致断言失败
- **根因**：签名变更 / 异步重构未同步更新 mock 类型
- **规则建立**：强制签名变更同步检查 + mock 类型映射表

### 5.2 #51 EXTERNAL-DEP-ISOLATION 根因摘要

- **症状**：`DingTalkNotifier(webhook_url="...", secret="")` 期望不发送，但生产 `get_secret` fallback 到 keyring 真实值，触发真实钉钉请求
- **根因**：测试未 patch `get_secret`，依赖生产 fallback 兜底
- **规则建立**：强制 patch 外部依赖 + 禁用 fallback 兜底

---

## 六、相关引用

- **元规范 #50**：TEST-SYNC-RESPONSIBILITY（[meta-rules.md](meta-rules.md)）
- **元规范 #51**：EXTERNAL-DEP-ISOLATION（[meta-rules.md](meta-rules.md)）
- **审查检查点**：
  - 后端：`B-REVIEW-176`（签名变更同步）/ `B-REVIEW-177`（外部依赖隔离）
  - 前端：`F-REVIEW-134`（mock 类型同步）/ `F-REVIEW-135`（外部依赖隔离）
- **配置节点**：`config.yaml#test_synchronization` / `config.yaml#external_dependency_isolation`
- **现有约束**：
  - meta-rule #1：配置驱动原则（参数禁止硬编码）
  - meta-rule #2：适用/不适用场景说明
  - meta-rule #3：历史教训归档原则（本文件仅摘要，不重复完整排查过程）
