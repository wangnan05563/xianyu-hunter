# 闲鱼猎人后端走查案例集（xianyu walkthrough cases）

> 本文件是 `xianyu-backend-code-review` 技能的**按需加载**补充材料，沉淀自一次真实的端到端代码走查：
> 「LLM 用量指标页面内容一直不显示」→ 定位并修复三条链路（时区分桶 / embedding token 泄漏 / 移动端静默失败）。
> 它不是新的检查点，而是把既有的若干 `B-REVIEW-*` 检查点落到**具体代码形态**上，便于评审时快速对照「这段代码是否踩了同一种坑」。

## 何时加载本文件

- 审查文件命中以下任一信号：`ai_usage.py`、`embedding_service.py`、`UsageRecord`、`record_usage`、`get_daily_summary`、`check_budget`、`billable`、`_today_key`、`_date_key_of`、`input_tokens_override`、`cost_override`。
- 或审查「用量 / 计费 / 配额 / 本地模型」相关模块，需要判断「可见性」与「计费」是否被正确隔离时。
- 或移动端与桌面端同一数据接口的失败处理需要对照时（见 Case 4 跨端部分，详见前端案例集）。

---

## Case 1 — 路径解析器硬化（path-resolver hardening）

**现象**：用量数据持久化文件 `data/ai_usage.json` 的读写若直接拼接 `os.getcwd()` 或硬编码绝对路径，在 PyInstaller 打包、不同启动目录、CI 环境下会出现「文件写到意料之外的地方 / 读不到历史数据」。

**正确形态**：所有数据文件读写必须经过统一解析器 `get_data_dir()`（来自 `infra/path_resolver` 一类模块），由它决定 `data/` 的真实落点（开发态 vs 打包态 vs 用户态）。

**评审要点**：
- 任何 `open("data/...")`、`Path("data/...")`、`os.path.join(os.getcwd(), ...)` 直接拼接都标记为问题，要求改为 `get_data_dir() / "ai_usage.json"`。
- 该规则对齐 **B-REVIEW-290（路径解析器一致性）**：数据/缓存/日志三类落点必须走同一解析器，禁止散落硬编码。
- 泛化判断：凡「会在运行时产生或读取的持久化文件」，先问「它的目录从哪来」；答案不是单一 resolver 即疑似违规。

**修复模板**：
```python
from xianyu_hunter.infra.path_resolver import get_data_dir
path = get_data_dir() / "ai_usage.json"
```

---

## Case 2 — 本地时区日期分桶（local-timezone date bucketing）

**现象**：用量按「天」聚合（`_today_key()` / `get_daily_summary()`），最初用 `datetime.fromtimestamp(ts, tz=timezone.utc)` 把时间戳折算成 UTC 日期。但业务边界是中国本地（UTC+8）自然日，导致每天 08:00 前（本地）产生的用量被算进「前一天」，跨天统计错一位。

**正确形态**：日期分桶统一用**业务所在时区**的本地时间：
```python
def _date_key_of(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")  # 本地时区
def _today_key() -> str:
    return _date_key_of(time.time())
```
历史记录的日期回填也必须用同一函数，避免新旧口径混用。

**评审要点**：
- 凡涉及「按自然日 / 自然月聚合、配额、预算、统计窗口」的代码，检查其分桶时区是否与业务边界一致。**计费/用量类绝不能默认 UTC**。
- 对齐 **B-REVIEW-121 / B-REVIEW-153（时区一致性）**：同一概念（「今天」「本日用量」）在写入端、读取端、回填端必须用同一分桶函数。
- 泛化判断：出现 `tz=timezone.utc`、`astimezone(timezone.utc)` 又紧邻「天数/日期」语义时，停下来核对业务时区。

**反模式**：
```python
# 错：用量按天统计却用 UTC，跨天错位
key = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
```

---

## Case 3 — 免费本地资源的 billable 隔离

**现象**：本地 embedding 模型免费，但最初 `record_usage` 把它的 token 记成 `total_tokens: 0` 且**同样纳入预算**，或者反过来——若改成记录估算 token 又不加标记，会**假装消耗计费预算**，挤占真实 LLM 调用的额度。

**正确形态**：引入 `billable` 标志，分离两种语义：
- 「在仪表盘**可见**」：本地 embedding 的估算 token 也要进 `get_daily_summary`，让用户看到总量。
- 「计入**预算/配额**」：`check_budget()` 只累加 `r.billable is True` 的记录；免费本地资源 `billable=False` 且 `cost_override=0.0`。

```python
# 本地 embedding：可见但免费
record_usage(
    model="local-embedding",
    input_tokens_override=estimate,   # 估算值，仅用于展示
    cost_override=0.0,
    billable=False,
)
# 预算核查只算计费项
def check_budget():
    billable = [r for r in history if r.billable]
    ...
```

**评审要点**：
- 凡出现「免费资源 / 本地模型 / 缓存命中 / 重试不计费」等语义，检查是否存在 `billable`（或等价 flag）把「展示」与「计费」解耦。
- 没有该 flag 时，默认行为是「记录即计费」，**对免费资源是危险默认**——评审应要求显式标记。
- 泛化判断：任何「用量/成本/配额」聚合函数，第一问应是「它聚合的是全部记录还是仅计费记录」。

---

## Case 4 — 静默失败暴露（silent-failure surfacing，跨端）

**现象**：移动端 `mobile/pages/AIConfig` 的用量加载 `getUsage().catch(() => null)` 把任何错误吞掉，既不告警也不暴露，导致「页面内容一直不显示」却无任何线索。桌面端 `pages/Config/AIConfig` 早已改为 `console.warn(...)` + 返回 `null`。

**正确形态（后端/前端共通原则）**：禁止裸 `.catch(() => null)` / 裸 `except: pass`。失败必须至少留一条可检索的告警，并返回安全的降级值。

```javascript
// 错
.getUsage().catch(() => null)
// 对
.getUsage().catch((e) => {
  console.warn("[MobileAIConfig] 用量数据加载失败，已隐藏卡片：", e);
  return null;
})
```

**评审要点**：
- 对齐 **B-REVIEW-245（禁止静默吞异常）**：`try/except` 空体、`except Exception: pass`、Promise `.catch(() => x)` 无日志，均标记为问题。
- 降级返回 `null` 本身可以接受（用于隐藏卡片），前提是**有日志**且前端对 `null` 有显式处理分支。
- 跨端一致性：同一数据接口在桌面端与移动端应共享同一失败诊断模式（都 warn + 都安全降级），不一致即标记。

---

## Case 5 — token 记账统一（embedding token fallback）

**现象**：远程 LLM 返回 `usage.prompt_tokens` / `completion_tokens`；但当两者都为 0（某些本地/代理响应只给 `total_tokens`，或本地 embedding 根本不给 usage）时，直接记 0 会让仪表盘对本地模型的用量「失明」。

**正确形态**：`record_usage` 在 `prompt_tokens == 0 and completion_tokens == 0` 时回退到 `usage.total_tokens`；对本地 embedding 再额外接受 `input_tokens_override`（按字符数估算：`max(1, len(text)/1.5)`）覆盖输入 token。

```python
if prompt_tokens == 0 and completion_tokens == 0:
    prompt_tokens = usage.get("total_tokens", 0)
```

**评审要点**：
- 凡是「把第三方/本地模型的 usage 落库」的代码，检查缺失字段的回退逻辑，避免静默记 0。
- 与 Case 3 配合：回退/估算出的 token 用于**展示**，但免费资源仍需 `billable=False` 以免污染计费。
- 泛化判断：任何依赖外部响应体字段做内部统计的地方，都要问「字段缺失时我用默认值还是回退值，会不会让指标失真」。

---

## 走查提炼的通用评审清单（可直接套用到同类模块）

1. **落点单一性**：运行时持久化文件的目录是否来自统一 resolver？（Case 1 / B-REVIEW-290）
2. **时区口径**：按自然日/月聚合的时区是否与业务边界一致，且写入/读取/回填三端统一？（Case 2 / B-REVIEW-121/153）
3. **展示↔计费解耦**：免费/本地/缓存资源是否有 flag 隔离「可见」与「计费」？（Case 3）
4. **失败可见性**：异步/异常分支是否留告警日志，降级值是否被显式处理？（Case 4 / B-REVIEW-245）
5. **字段缺失回退**：依赖外部 usage/响应字段做指标时，缺失字段如何处理才不会让指标失真？（Case 5）

> 上述每条都可映射到既有 `B-REVIEW-*` 检查点；本案例集的价值是提供「真实代码形态 + 反模式 + 修复模板」，缩短从「看到代码」到「判定违规」的距离。
