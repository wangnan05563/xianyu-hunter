# 闲鱼猎人数据一致性编码规范

> 本规范基于实际运行中排查并修复的问题提炼而成，旨在约束多入口调用、价格采集、状态检测等场景下的代码一致性，避免同类问题反复出现。

---

## 一、多入口调用参数一致性

### DC-001: 多入口调用同一底层 API 时必须共享参数合并逻辑

**【强制】**

- **问题描述**：Live 搜索只用 `task.search_filters`，不合并全局 `search.filter_tags`；而 Worker 搜索合并两者。导致实时搜索结果与后台搜索结果不一致。
- **规范条文**：同一底层 API（如 `collector.search`）有多个调用入口（Worker / Live / Manual）时，所有入口必须共享相同的参数合并逻辑，将其提取为独立函数复用，禁止在各入口处分别内联实现合并逻辑。

**正面示例**：

```python
def _merge_search_filters(task_filters: list[str], global_filters: list[str]) -> list[str]:
    """合并任务级和全局筛选标签，去重保序"""
    seen = set(task_filters)
    result = list(task_filters)
    for f in global_filters:
        if f not in seen:
            result.append(f)
            seen.add(f)
    return result
```

**反面示例**：

```python
# Worker 入口：合并了全局配置
combined_filters = list(set(task_filters + global_filters))
# Live 入口：未合并全局配置（行为不一致）
task_search_filters = task.get("search_filters") or []
```

- **适用场景**：任何有多入口调用同一底层 API 的场景（搜索 / 采集 / 查询 / 刷新）。
- **不适用场景**：明确需要差异化的场景（如 Worker 需要 `skip_rgv587_retry=True`，Live 不需要）。

---

### DC-002: 配置值格式必须与代码映射表键名一致

**【强制】**

- **问题描述**：`config.yaml` 的 `filter_tags` 配置为中文 `[包邮]`，但 `XIANYU_FILTER_MAP` 键名是英文 `free_shipping`，导致映射失败。
- **规范条文**：配置文件中的枚举值必须与代码中的映射表 / 常量键名使用相同的命名规范。新增映射表时必须同步更新配置文件的示例值和注释，并在映射失败时输出告警日志便于排查。

**正面示例**：

```yaml
# config.yaml - 使用与 XIANYU_FILTER_MAP 一致的英文键名
filter_tags:
  - personal_idle   # 个人闲置
  - verified        # 验货宝
  - free_shipping   # 包邮
```

**反面示例**：

```yaml
# config.yaml - 使用中文，与映射表键名不匹配
filter_tags:
  - 包邮  # 无法映射到 free_shipping
```

- **适用场景**：任何使用映射表 / 枚举的配置项。
- **不适用场景**：用户可读的展示文案（如 UI 标签）。

---

## 二、价格采集一致性

### DC-003: 价格字段优先级必须与官网展示对齐

**【强制】**

- **问题描述**：`_PRICE_KEYS` 优先取 `promoPrice`（促销价），但官网展示的是 `price`（当前挂牌价），导致本地金额与官网不一致。
- **规范条文**：采集价格时应优先取「当前挂牌价」（`price`），促销价（`promoPrice`）作为兜底，确保本地展示金额与官网保持一致。

**正面示例**：

```python
_PRICE_KEYS = ("price", "promoPrice", "promotionPrice", "soldPrice", "originalPrice")
```

**反面示例**：

```python
_PRICE_KEYS = ("promoPrice", "promotionPrice", "price", "soldPrice", "originalPrice")
```

- **适用场景**：任何从外部 API 采集价格字段。
- **不适用场景**：明确需要采集促销价的场景（如促销分析）。

---

### DC-004: DOM 选择器必须排除干扰元素

**【强制】**

- **问题描述**：`[class*='price']` 选择器过宽，匹配到原价 / 运费 / 促销价等非目标元素。
- **规范条文**：CSS 选择器必须用 `:not()` 排除干扰元素（`original` / `postage` / `shipping` / `line-through`），避免取到非目标元素。

**正面示例**：

```python
DETAIL_PRICE_MAIN = "[class*='price--']:not([class*='original']):not([class*='Original']):not([class*='postage']):not([class*='shipping']):not([class*='line-through'])"
```

**反面示例**：

```python
DETAIL_PRICE_MAIN = "[class*='price--']"  # 可能匹配到原价元素
```

- **适用场景**：任何从 DOM 提取特定字段的场景。
- **不适用场景**：只有一个匹配元素的简单 DOM 结构。

---

### DC-005: 同类型解析函数必须保持单位转换一致

**【强制】**

- **问题描述**：`_coerce_price` 支持「万」单位转换，但 `parse_price_from_text` 不支持，导致「1.2万」被解析为 1.2 而非 12000。
- **规范条文**：同一类型的数据解析函数（价格 / 数量 / 日期）必须保持一致的单位转换逻辑。新增单位转换规则时，所有同类解析函数必须同步更新。

**正面示例**：

```python
def parse_price_from_text(text: str) -> float:
    cleaned = re.sub(r"[\s,]+", "", text)
    m = re.search(r"\d+\.?\d*", cleaned)
    if not m:
        return 0.0
    price = float(m.group())
    if "万" in cleaned:  # 与 _coerce_price 保持一致
        price *= 10000
    return price
```

**反面示例**：

```python
def parse_price_from_text(text: str) -> float:
    cleaned = re.sub(r"[\s,]+", "", text)
    m = re.search(r"\d+\.?\d*", cleaned)
    return float(m.group()) if m else 0.0  # 不支持"万"单位
```

- **适用场景**：任何有多个解析同一类型数据的函数。
- **不适用场景**：明确不需要单位转换的场景。

---

## 三、状态检测完整性

### DC-006: 状态检测关键词必须覆盖所有平台文案变体

**【强制】**

- **问题描述**：`is_sold` 检测只覆盖「已售 / 已下架 / 已卖出」，未覆盖「宝贝不存在 / 走丢 / 已删除」等文案，导致部分已售商品未被识别。
- **规范条文**：通过文本关键词检测页面状态时，关键词列表必须覆盖所有可能的平台提示文案变体，并定期根据实际遇到的文案更新。

**正面示例**：

```python
is_sold = "已售" in body_text or any(kw in body_text for kw in (
    "已售出", "已售完", "已售罄", "宝贝已售", "商品已售",
    "已下架", "已卖出",
    # 商品被卖家删除/不存在时的文案
    "宝贝不存在", "宝贝走丢了", "该宝贝不存在",
    "商品不存在", "已删除", "已被删除",
))
```

**反面示例**：

```python
is_sold = "已售" in body_text  # 漏检大量文案变体
```

- **适用场景**：任何通过文本关键词检测页面状态的场景。
- **不适用场景**：有明确 DOM 结构标识状态的场景（用选择器更可靠）。

---

### DC-007: 状态检测关键词列表必须提取为模块级常量

**【建议】**

- **问题描述**：关键词散落在多个函数内部，难以统一维护与扩展。
- **规范条文**：外部系统（闲鱼 / 淘宝 / 第三方 API）的文本特征必须提取为模块级常量（`tuple` 或 `frozenset`），多处消费点必须复用同一常量，禁止在函数内部硬编码关键词字面量。

**正面示例**：

```python
# 模块级常量
SOLD_KEYWORDS: tuple[str, ...] = (
    "已售", "已售出", "已售完", "已售罄", "宝贝已售", "商品已售",
    "已下架", "已卖出",
    "宝贝不存在", "宝贝走丢了", "该宝贝不存在",
    "商品不存在", "已删除", "已被删除",
)

# 消费点
is_sold = any(kw in body_text for kw in SOLD_KEYWORDS)
```

**反面示例**：

```python
# 散落在函数内部
def check_sold(body_text: str) -> bool:
    return "已售" in body_text or "已下架" in body_text
```

- **适用场景**：任何有关键词列表的场景。
- **不适用场景**：仅一次性使用的简单判断。

---

## 四、问题排查流程规范

### DC-008: 问题排查必须包含日志分析步骤

**【强制】**

- **问题描述**：仅靠代码分析无法定位运行时问题（如价格提取取到了什么值），需要实际日志验证。
- **规范条文**：问题排查必须包含日志分析步骤，不能仅靠静态代码分析。修复后必须提供验证手段（日志 / 测试用例），并在 PR 描述中附上日志证据或测试输出。

**正面示例**：

```text
排查步骤：
1. 复现问题，开启 DEBUG 日志
2. 在日志中搜索 [item_id] 关键字，确认采集到的原始字段值
3. 对比代码预期与实际取值，定位偏差
4. 修复后补充测试用例或调试日志，输出验证结果
```

**反面示例**：

```text
排查步骤：
1. 看代码逻辑猜测问题原因
2. 修改代码后直接提交
```

- **适用场景**：任何运行时问题的排查。
- **不适用场景**：纯代码风格 / 命名问题。

---

### DC-009: 修复后必须提供可验证的调试手段

**【强制】**

- **问题描述**：价格问题首次修复后用户反馈「问题依然存在」，因为仅靠代码分析不够。
- **规范条文**：修复后必须添加调试日志或测试用例，用实际数据验证修复效果。调试日志须记录关键字段值与决策路径，便于二次问题排查。

**正面示例**：

```python
logger.info(f"详情页 {item_id} 最终采用价格: {price}")
logger.debug(f"详情页 {item_id} 价格选择器[{sel_idx}] sel={sel!r} text={text!r} price={price}")
```

**反面示例**：

```python
# 修复后无任何调试日志，无法验证
price = parse_price_from_text(text)
```

- **适用场景**：任何涉及数据提取 / 转换的修复。
- **不适用场景**：纯逻辑修复（如条件判断修复）。
