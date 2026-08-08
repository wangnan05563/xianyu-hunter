# 模式 AE：类型注解契约对齐回归测试

> **版本**：v2.6.0（2026-07-26 第九轮复盘落地）
> **关联复盘**：`xianyu-hunter-dev/references/retrospective-2026-07-26.md`
> **关联规范**：`xianyu-hunter-dev` meta-rule #110（experimental）+ step 273
> **配套检查点**：
> - 后端：`xianyu-backend-code-review` v4.67.0 B-REVIEW-330（TYPE-ANNOTATION-CONTRACT-ALIGNMENT）
> - 前端：`xianyu-frontend-code-review` v4.67.0 F-REVIEW-244（FRONTEND-TYPE-CONTRACT-REVERSE-VALIDATION）
> **配置来源**：`../xianyu-hunter-dev/config/tech-stack.json#hardConstraints.typeAnnotationContract`

---

## 测试目标

验证后端函数返回类型注解、Pydantic ResponseModel、前端 types.ts 三方契约对齐，防止"类型注解 `list[str]` 但实际返回 `list[dict]`"导致前端取到 undefined 的 Bug 再次出现。

## 测试范围

| 层 | 文件 | 检查点 |
|---|---|---|
| 后端函数签名 | `src/xianyu_hunter/web/routes/api_ai_deep.py` | B-REVIEW-330 TYPE-ANNOTATION-CONTRACT-ALIGNMENT |
| 后端 Pydantic ResponseModel（若存在） | `src/xianyu_hunter/web/routes/api_ai_deep.py` 或 schemas | B-REVIEW-330 三方对齐 |
| 后端→前端同步 | `src/xianyu_hunter/web/routes/api_ai_deep.py` + `frontend/src/api/types.ts` | B-REVIEW-330 + F-REVIEW-244 |
| 前端类型层 | `frontend/src/api/types.ts` | F-REVIEW-244 类型声明反向校验 |
| 前端消费层 | `frontend/src/pages/Evaluations/index.tsx` | F-REVIEW-244 字段访问与类型声明一致 |
| 单元测试层 | `tests/test_ai_deep.py` | B-REVIEW-330 完整结构断言 |

---

## 测试用例矩阵

### AE-T01：后端函数返回类型注解与实际返回结构一致性测试（B-REVIEW-330）

**场景**：后端函数 `_compute_image_url_hash` 声明 `-> list[str]` 但实际返回 `list[dict]`

**测试步骤**：
1. 调用 `POST /api/ai/deep-analyze`，传入包含 2 张图片 URL 的请求
2. 验证响应 `image_hashes` 字段结构

**预期**：
- `image_hashes` 是 list 类型
- 每个 element 是 dict（不是 str）
- 每个 dict 包含 `url` 和 `hash` 两个 key
- `url` 是非空字符串，`hash` 是 12 位 MD5 字符串

**测试代码示例**：
```python
def test_deep_analyze_image_hashes_structure_alignment(client, tmp_repo):
    """验证 image_hashes 返回结构与类型注解一致（B-REVIEW-330）"""
    _seed_item(tmp_repo)
    resp = client.post(
        "/api/ai/deep-analyze",
        json={"item_id": "i1", "checks": ["stolen_image"]},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    image_hashes = data["image_hashes"]
    
    # 结构断言：每个元素必须是 dict，不是 str
    assert len(image_hashes) == 2
    for h in image_hashes:
        assert isinstance(h, dict), f"期望 dict，实际 {type(h).__name__}（类型注解与返回结构不一致）"
        assert "url" in h and isinstance(h["url"], str) and h["url"]
        assert "hash" in h and len(h["hash"]) == 12
```

### AE-T02：前端 types.ts 与后端响应字段 1:1 对齐测试（F-REVIEW-244）

**场景**：前端 `types.ts` 声明 `Array<{ url: string; hash: string }>`，验证后端响应字段名与类型完全匹配

**测试步骤**：
1. 读取 `frontend/src/api/types.ts` 中 `image_hashes` 的类型声明
2. 调用后端 API 获取实际响应
3. 逐字段对照类型声明与实际响应

**预期**：
- types.ts 声明的每个字段在后端响应中都存在
- 字段类型匹配（string 对应 str，number 对应 int/float，boolean 对应 bool）
- 后端响应中不存在 types.ts 未声明的字段（除非显式标注可选）

### AE-T03：单元测试完整结构断言验证（B-REVIEW-330）

**场景**：单元测试 `test_deep_analyze_image_hashes` 是否断言了完整结构

**测试步骤**：
1. 读取 `tests/test_ai_deep.py` 中相关测试函数
2. 检查断言模式

**预期**：
- 禁止仅断言 `len(h) == 12`（假设 h 是字符串）
- 必须断言 `isinstance(h, dict)` + 字段存在性 + 字段类型
- 必须至少断言一个字段的值（如 `len(h["hash"]) == 12`）

### AE-T04：复杂返回结构端点扫描测试（B-REVIEW-330）

**场景**：扫描所有返回 `list[dict]` / `list[TypedDict]` 的后端函数，验证三方对齐

**测试步骤**：
1. `grep -rn "def.*->.*list\[" src/xianyu_hunter/` 找出所有返回复杂结构的函数
2. 对每个函数，检查：
   - 是否有对应的 Pydantic ResponseModel？
   - 是否有对应的前端 types.ts 声明？
   - 三方是否一致？
3. 输出扫描报告

**预期**：
- 所有返回复杂结构的函数都有明确契约
- 三方一致或显式标注"无前端消费方"

---

## 配置驱动

所有测试参数从 `xianyu-hunter-dev/config/tech-stack.json#hardConstraints.typeAnnotationContract` 读取：

| 参数 | 含义 | 默认值 |
|------|------|--------|
| `enabled` | 是否启用本测试模式 | true |
| `complexReturnTypes` | 视为复杂返回结构的类型列表 | `["list[dict]", "list[TypedDict]", "list[Pydantic BaseModel]", "dict[str, Any]"]` |
| `alignmentSources` | 契约对齐源 | `["pydantic_response_model", "frontend_types_ts"]` |
| `authoritativeSource` | 权威源 | `pydantic_response_model` |
| `fallbackAuthoritativeSource` | 反向校验源 | `frontend_types_ts` |
| `testAssertionLevel` | 测试断言级别 | `full_structure` |

---

## 通过判据

1. **AE-T01**：后端函数实际返回结构与类型注解完全一致
2. **AE-T02**：前端 types.ts 字段与后端响应字段 1:1 对齐
3. **AE-T03**：单元测试断言完整结构（非仅长度）
4. **AE-T04**：扫描报告无"三方不一致"的端点

任一判据失败 → 触发 B-REVIEW-330 或 F-REVIEW-244 阻塞项，需修复后复测。

---

## 关联模式

| 关联模式 | 关系 |
|---------|------|
| 模式 AA（资源创建幂等性） | 互补：AA 管响应语义（ok/already_active），AE 管响应结构（字段类型） |
| 模式 H（快照与最新值一致性） | 互补：H 管字段值正确性，AE 管字段结构正确性 |
| 模式 G（数据透传完整性） | 互补：G 管跨层字段传递，AE 管跨层类型对齐 |

---

## 历史教训来源

**2026-07-26 AI 深度鉴伪图片哈希 undefined Bug**：
- 前端显示 `undefined → undefined`（重复 9 次）
- 根因：后端 `_compute_image_url_hash` 类型注解 `-> list[str]` 与前端 `Array<{url, hash}>` 不一致
- 修复：后端改为返回 `list[dict]`，同步更新类型注解和单元测试断言
- 本模式 AE 即针对此类 Bug 的回归测试模式

---

## 适用与不适用场景

### 适用
- 后端函数返回 `list[dict]` / `list[TypedDict]` / 嵌套 Pydantic 模型的端点
- 前后端分离项目的 API 契约验证
- 单元测试断言复杂结构的端点
- 修复"前端显示 undefined"类 Bug 后的回归测试

### 不适用
- 返回基本类型（str/int/bool）的端点
- 纯内部 helper 函数（无前端消费方）
- 动态结构通用序列化（结构由 DB schema 决定）
- 已有 Pydantic ResponseModel 严格校验的端点（ResponseModel 本身即契约源）
