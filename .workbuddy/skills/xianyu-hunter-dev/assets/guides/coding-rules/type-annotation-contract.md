# 类型注解契约对齐规范（TYPE-ANNOTATION-CONTRACT-ALIGNMENT-01）

> **step 编号**：273
> **版本**：v4.67.0（experimental）
> **关联 meta-rule**：#110
> **关联审查点**：B-REVIEW-330 / F-REVIEW-244
> **关联复盘**：[retrospective-2026-07-26.md](../../references/retrospective-2026-07-26.md)
> **配置节点**：`config/tech-stack.json#hardConstraints.typeAnnotationContract`

---

## 一、问题背景

2026-07-26 修复"AI 深度鉴伪图片哈希显示 undefined → undefined"Bug，根因是后端函数 `_compute_image_url_hash` 类型注解声明 `-> list[str]` 且实际返回 `[hashlib.md5(url).hexdigest()[:12] for url in image_urls]`（纯字符串列表），而前端 `types.ts` 声明 `Array<{ url: string; hash: string }>`。前端渲染 `h.url`/`h.hash` 时取到 undefined。

既有规范 #35（前后端字段契约单一可信源）和 #88（CROSS-LAYER-CONTRACT-SYNC）只覆盖"字段名/存在性"维度，未覆盖"类型注解正确性"维度。#108（CROSS-LAYER-CLOSED-LOOP）关注"git diff 半边修改"动作维度，也未覆盖"函数签名注解本身错误"的情况。

本规范作为 experimental 元规则 #110 的落地补充，1 季度观察期内收集同类根因再发频次，达到 2 次即升正。

---

## 二、核心规则

### 规则 1：三方契约对齐

返回复杂结构（`list[dict]` / `list[TypedDict]` / 嵌套 Pydantic BaseModel / `dict[str, Any]`）的后端函数，必须保证三方一致：

| 层 | 内容 | 示例 |
|----|------|------|
| 后端函数返回类型注解 | `def f(...) -> list[dict]:` | `list[dict]` |
| 后端 Pydantic ResponseModel（若存在） | `class FResponse(BaseModel): items: list[Item]` | `list[Item]` |
| 前端 types.ts | `interface FResponse { items: Array<{...}> }` | `Array<{...}>` |

### 规则 2：权威源优先级

任一不一致时，按以下优先级确定权威源：

1. **后端 Pydantic ResponseModel**（首选）— 类型最严格，运行时校验
2. **前端 types.ts**（反向校验源）— 当后端无 ResponseModel 时，以前端声明为反向校验源
3. **后端函数类型注解**（最弱）— 仅作辅助参考，不能作为权威源

### 规则 3：单元测试断言完整结构

返回复杂结构的函数，单元测试必须断言**完整结构**（字段名 + 字段类型 + 至少一个字段的值），而非仅断言长度或顶层类型。

**反模式**：
```python
# ❌ 仅断言长度
assert len(data["image_hashes"]) == 2
for h in data["image_hashes"]:
    assert len(h) == 12  # 假设 h 是字符串，但实际可能是 dict
```

**正确模式**：
```python
# ✅ 断言完整结构
assert len(data["image_hashes"]) == 2
for h in data["image_hashes"]:
    assert "url" in h and isinstance(h["url"], str) and h["url"]
    assert "hash" in h and len(h["hash"]) == 12
```

---

## 三、判断逻辑

对于每个返回复杂结构的后端函数：

```
1. 函数签名是否有返回类型注解？
   否 → 建议补充（非强制）
2. 类型注解是否与 Pydantic ResponseModel 一致？
   否 → 修复类型注解或 ResponseModel（以 ResponseModel 为准）
3. 类型注解是否与前端 types.ts 一致？
   否 → 修复类型注解或 types.ts（无 ResponseModel 时以 types.ts 为准）
4. 单元测试是否断言了完整结构（而非仅长度/类型）？
   否 → 补充结构断言
任一答案为"否且影响契约" → 需要修复
```

---

## 四、适用与不适用场景

### 适用场景
- 返回 `list[dict]` / `list[TypedDict]` / 嵌套 Pydantic 模型的后端函数
- 前后端分离项目的 API 端点
- 单元测试断言复杂结构的端点
- 无 Pydantic ResponseModel 但有前端消费方的端点

### 不适用场景
- 返回基本类型（`str`/`int`/`bool`）的函数
- 纯内部 helper 函数（无前端消费方）
- 动态结构（如 ORM 行转 dict 的通用序列化，结构由 DB schema 决定）
- 已有 Pydantic ResponseModel 严格校验的端点（ResponseModel 本身即契约源，类型注解冗余）

---

## 五、与既有规范的关系

| 既有规范 | 覆盖维度 | 与本规范的关系 |
|---------|----------|----------------|
| #35 前后端字段契约单一可信源 | 字段名/存在性 | 互补：#35 管"字段是否存在"，本规范管"类型注解是否正确" |
| #88 CROSS-LAYER-CONTRACT-SYNC | 跨层数据契约同步动作 | 互补：#88 管"同步流程"，本规范管"注解正确性" |
| #108 CROSS-LAYER-CLOSED-LOOP | git diff 半边修改检测 | 互补：#108 管"修改动作"，本规范管"注解与实际返回一致性" |
| 规范 32 前端 async handler 三分支完整性 | API 函数返回类型与后端响应字段 1:1 对齐 | 部分重叠：规范 32 关注前端类型，本规范关注后端函数注解 |

**核心差异**：本规范是首个明确要求"后端函数返回类型注解本身必须正确"的规范，既有规范都假设"后端注解=实际返回"，本规范打破这个假设。

---

## 六、配置参数

所有阈值从 `config/tech-stack.json#hardConstraints.typeAnnotationContract` 读取：

```json
{
  "enabled": true,
  "complexReturnTypes": ["list[dict]", "list[TypedDict]", "list[Pydantic BaseModel]", "dict[str, Any]"],
  "alignmentSources": ["pydantic_response_model", "frontend_types_ts"],
  "authoritativeSource": "pydantic_response_model",
  "fallbackAuthoritativeSource": "frontend_types_ts",
  "testAssertionLevel": "full_structure",
  "observationPeriodQuarters": 1,
  "observationEndDate": "2026-10-26",
  "promotionThreshold": 2,
  "applicableScenarios": ["前后端分离 API", "返回复杂嵌套结构的端点"],
  "nonApplicableScenarios": ["返回基本类型", "纯内部 helper", "动态结构通用序列化"]
}
```

---

## 七、历史教训来源

**2026-07-26 闲鱼猎人 AI 深度鉴伪图片哈希 undefined Bug**：

- **现象**：前端"AI 深度鉴伪"面板的图片哈希折叠区显示 `undefined → undefined`（重复 9 次）
- **根因**：后端 `_compute_image_url_hash(image_urls: list[str]) -> list[str]` 实际返回纯字符串列表，但前端 types.ts 声明 `Array<{ url: string; hash: string }>`
- **修复**：后端改为返回 `list[dict]`（`[{"url": url, "hash": ...}]`），同步更新类型注解和单元测试断言
- **特殊性**：本案前端 types.ts 反而是契约真相源（已正确），后端偏离——这是既有规范 #35/#88 假设"后端为权威源"未覆盖的反向情况

---

## 八、检查信号（grep）

```bash
# 找返回复杂结构的后端函数
grep -rn "def.*->.*list\[" src/xianyu_hunter/
grep -rn "def.*->.*dict" src/xianyu_hunter/

# 找前端 types.ts 中的复杂类型声明
grep -n "Array<{.*}>" frontend/src/api/types.ts

# 找仅断言长度的单元测试（反模式）
grep -B2 "assert len(" tests/ | grep -A2 "for.*in.*\["
```
