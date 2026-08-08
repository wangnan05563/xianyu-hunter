# 复盘报告：2026-07-26 图片哈希 Bug + 2026-06-29 8 个 P0-P3 修复

> **版本**：v4.67.0
> **复盘日期**：2026-07-26
> **复盘方法**：Sequential Thinking 四维度复盘
> **触发来源**：用户引用 [迭代提示词.md#L31-53](../../../docs/00-待完成/迭代提示词.md#L31-L53)，要求基于最近历史对话复盘并优化技能
> **关联规范**：meta-rule #110（experimental）/ step 273 / B-REVIEW-330 / F-REVIEW-244 / 模式 AE

---

## H.1 复盘范围

| 范围 | 内容 | 来源 |
|------|------|------|
| 案例 A | AI 深度鉴伪图片哈希显示 undefined → undefined Bug 修复 | 2026-07-26 当前对话 |
| 案例 B | 8 个 P0-P3 后端日志问题修复 | 2026-06-29 日志分析（memory） |

---

## H.2 维度一：成功执行任务的完整步骤

### 案例 A：图片哈希 undefined Bug 修复

**问题现象**：前端"AI 深度鉴伪"面板的图片哈希折叠区显示 `undefined → undefined`（重复 9 次）。

**完整解决步骤**：

1. **现象定位**：前端 [Evaluations/index.tsx:1963](../../../frontend/src/pages/Evaluations/index.tsx#L1963) 渲染 `deepResult.image_hashes.map(h => \`${h.url}\n  → ${h.hash}\`)`，`h.url`/`h.hash` 为 undefined
2. **契约对照**：
   - 前端 [types.ts:410](../../../frontend/src/api/types.ts#L410) 声明 `image_hashes?: Array<{ url: string; hash: string }>`
   - 后端 [api_ai_deep.py:407](../../../src/xianyu_hunter/web/routes/api_ai_deep.py#L407) 函数签名 `_compute_image_url_hash(image_urls: list[str]) -> list[str]`，实际返回 `[hashlib.md5(...).hexdigest()[:12] for url in image_urls]`（纯字符串列表）
3. **根因确认**：后端函数类型注解 `list[str]` 与前端类型声明 `Array<{url, hash}>` 不一致；前端 types.ts 反而是契约真相源
4. **最小修复**：后端改为返回 `list[dict]`（`[{"url": url, "hash": ...}]`），同步更新类型注解为 `list[dict]`
5. **测试同步**：更新 [test_ai_deep.py:167](../../../tests/test_ai_deep.py#L167) 断言结构（从 `len(h) == 12` 改为校验 `url`/`hash` 字段）
6. **语法校验**：`python -m py_compile` 通过

### 案例 B：6月29日 8 个 P0-P3 修复

| 编号 | 失败现象 | 根因 | 修复 |
|------|----------|------|------|
| (a) | sqlite3.InterfaceError | 多线程共享 SQLite 连接 | 改用 NullPool 实现线程独立连接 |
| (b) | Notifier channel 配置错误 | 未校验渠道是否配置就发送 | 新增 is_configured 检查 |
| (c) | detail_dom JSON 空 | dump 逻辑不完整 | 改进 dump 逻辑 |
| (d) | Playwright TargetClosedError | 操作已关闭的 page | 新增 page.is_closed() 检查 |
| (e) | search goto 超时 | 默认超时不足 | 增加超时到 35s |
| (f) | 端口 8000 冲突 | 旧进程未释放端口 | 端口释放等待循环 |
| (g) | title selector 降级告警噪音 | 日志级别过高 | 降级到 debug |
| (h) | price 解析错误 | 字符串含空白 | strip 空白 |

---

## H.3 维度二：任务执行过程中的不确定性与失败点

| 编号 | 不确定性/失败点 | 教训 |
|------|-----------------|------|
| U1 | 既有规范 #35/#88 假设"后端为权威源"，但本案前端 types.ts 反而是真相源 | 契约方向不应单向假设，需双向校验 |
| U2 | 后端 Python 类型注解（`list[str]`）本身错误，静态类型检查未启用 | 类型注解正确性需独立校验，不能假设注解=实际 |
| U3 | 8 个 P0-P3 修复未及时沉淀为规范 | 修复后未触发复盘 SOP，遗漏沉淀窗口 |
| U4 | 完全未覆盖的 4 项（a/d/f/g）若再次发生需重新排查 | 缺少"待沉淀候选"标记机制 |
| U5 | #108（CROSS-LAYER-CLOSED-LOOP）已覆盖"跨层修改同步"动作维度，但未覆盖"类型注解正确性"维度 | 类型注解正确性是新维度，不与 #108 重复 |

---

## H.4 维度三：可抽象的固定流程与判断逻辑

### 流程 11：类型注解契约对齐三步校验（本案新增，落地为 step 273）

```
1. 前端 types.ts 类型声明 → 后端 Pydantic ResponseModel → 后端函数返回类型注解 三者逐字段对照
2. 任一不一致时，以后端 Pydantic ResponseModel 为权威源（若存在），无 ResponseModel 时以前端 types.ts 为反向校验源
3. 同步修复：函数体返回结构 + 类型注解 + 单元测试断言结构
```

**判断逻辑**：
```
对于每个返回复杂结构（list/dict/嵌套对象）的后端函数：
  1. 函数签名是否有返回类型注解？
  2. 类型注解是否与 Pydantic ResponseModel 一致？
  3. 类型注解是否与前端 types.ts 一致？
  4. 单元测试是否断言了完整结构（而非仅长度/类型）？
  任一答案为否 → 需要修复
```

**与 #108 的差异**：
- #108 关注"git diff 半边修改"（修改同步动作维度），强调 grep 验证三层同步
- 流程 11 关注"类型注解正确性"（函数签名维度），强调注解与实际返回结构一致
- 两者互补：#108 防"改了一层忘改另一层"，流程 11 防"注解本身就错"

### 流程 12：单 bug 沉淀候选标记（针对 8 个 P0-P3 未覆盖项）

```
1. 修复后立即在 retrospective 文件标记为"待沉淀候选"
2. 1 季度内同类根因再发 ≥ 2 次 → 升级为 experimental 元规则
3. 1 季度内未再发 → 标记为"偶发，不立规范"
```

---

## H.5 维度四：适用场景与不适用场景

### 流程 11（类型注解契约对齐）

**适用场景**：
- 返回 `list[dict]` / `list[TypedDict]` / 嵌套 Pydantic 模型的后端函数
- 前后端分离项目的 API 端点
- 单元测试断言复杂结构的端点

**不适用场景**：
- 返回基本类型（`str`/`int`/`bool`）的函数
- 纯内部 helper 函数（无前端消费方）
- 动态结构（如 ORM 行转 dict 的通用序列化）
- 已有 Pydantic ResponseModel 严格校验的端点（ResponseModel 本身即契约源）

### 流程 12（待沉淀候选标记）

**适用场景**：
- 所有修复后未达 SOP #36 沉淀阈值（< 3 次同类根因）的 bug

**不适用场景**：
- 安全漏洞/数据丢失（按 SOP #36 豁免条款立即立规范）
- 纯 typo/构建错误

---

## H.6 待沉淀候选清单（8 个 P0-P3 修复覆盖分析）

| 修复 | 覆盖状态 | 既有规范 | 处置 |
|------|----------|----------|------|
| (a) sqlite3.InterfaceError → NullPool | 完全未覆盖 | 无 | 标记待沉淀候选，1 季度观察 |
| (b) Notifier channel 配置 → is_configured | 部分覆盖 | 配置驱动原则 | 标记待沉淀候选 |
| (c) detail_dom JSON 空 → dump 改进 | 部分覆盖 | dump 机制 | 标记待沉淀候选 |
| (d) Playwright TargetClosedError → is_closed() | 完全未覆盖 | 无 | 标记待沉淀候选，1 季度观察 |
| (e) search goto 超时 → 增加超时 | 部分覆盖 | 超时配置项 | 标记待沉淀候选 |
| (f) 端口 8000 冲突 → 端口释放等待 | 完全未覆盖 | 无 | 标记待沉淀候选，1 季度观察 |
| (g) title selector 降级告警 → debug | 部分覆盖 | 日志级别规范 | 标记待沉淀候选 |
| (h) price 解析 → strip 空白 | 部分覆盖 | 字符串处理 | 标记待沉淀候选 |

**观察期**：2026-07-26 至 2026-10-26（1 季度）
**升正阈值**：同类根因再发 ≥ 2 次（按 SOP #36 沉淀阈值 3 次的 2/3，作为 experimental 升正门槛）

---

## H.7 新增规范与配置

### 新增 meta-rule #110（experimental）

| 字段 | 值 |
|------|-----|
| 编号 | #110 🆕v4.67 experimental |
| 名称 | TYPE-ANNOTATION-CONTRACT-ALIGNMENT 类型注解契约对齐 |
| 一句话概述 | 后端函数返回类型注解必须与 Pydantic ResponseModel 和前端 types.ts 三方一致；不一致时以 ResponseModel 为权威源，无 ResponseModel 时以前端 types.ts 为反向校验源 |
| 落地位置 | coding-rules/type-annotation-contract.md / step 273 / B-REVIEW-330 / F-REVIEW-244 |
| 升正条件 | 1 季度内同类根因再发 ≥ 2 次（截至 2026-10-26） |

### 新增配置节点

`config/tech-stack.json#hardConstraints.typeAnnotationContract`：
- `enabled`: true
- `complexReturnTypes`: list[dict] / list[TypedDict] / list[Pydantic BaseModel] / dict[str, Any]
- `authoritativeSource`: pydantic_response_model
- `fallbackAuthoritativeSource`: frontend_types_ts
- `observationPeriodQuarters`: 1
- `observationEndDate`: 2026-10-26
- `promotionThreshold`: 2

### 下游技能同步

| 技能 | 同步内容 |
|------|----------|
| xianyu-hunter-dev | meta-rule #110 + step 273 + 配置节点 + retrospective + version-history |
| xianyu-auto-testing | 模式 AE（类型注解契约对齐回归测试） |
| xianyu-backend-code-review | B-REVIEW-330（TYPE-ANNOTATION-CONTRACT-ALIGNMENT） |
| xianyu-frontend-code-review | F-REVIEW-244（FRONTEND-TYPE-CONTRACT-REVERSE-VALIDATION） |

---

## H.8 验证方法

### 静态验证
- `python -m py_compile` 通过（已验证）
- `python -c "import json; json.load(open('config/tech-stack.json'))"` — JSON 合法性
- `python -c "import yaml; yaml.safe_load(open('../xianyu-auto-testing/config.yaml'))"` — YAML 合法性

### 一致性验证
- `grep -r "meta-rule #110\|TYPE-ANNOTATION-CONTRACT" .trae/skills/` 应在 4 个技能中各命中至少 1 次
- step 273 在 `_step-index.md` 与 `_step-index.json` 中编号一致

### 回归测试
- 调用 `xianyu-auto-testing` 技能执行模式 AE，对 [api_ai_deep.py](../../../src/xianyu_hunter/web/routes/api_ai_deep.py) 跑类型注解契约对齐回归测试
- 验证 `pytest tests/test_ai_deep.py::test_deep_analyze_image_hashes` 通过

### SOP 合规性
- #110 标注 `experimental` + 观察期截止日 `2026-10-26` + 升正阈值 `2 次`
- 8 个 P0-P3 修复中完全未覆盖的 4 项标记为"待沉淀候选"，未直接立规范
