# 维度 24：跨字段一致性

> **编码规范引用**：coding-standards v1.3 §统计查询-写入对齐 / 多格式输入解析 / meta-rules #25-30
> **配置节点**：config.yaml#consistency_and_state_checks
> **对应 references**：consistency-and-state-checks.md

## 触发条件
- 数据模型字段增删改
- 统计/聚合查询变更
- 多数据源合并逻辑
- 配置项值与代码映射表键名定义

## 检查规则

### 强制（P0 阻塞）
- 同一数据存在多字段存储时（如 `price` 与 `promoPrice`），必须明确字段优先级和取值来源，禁止二义性
- 统计查询条件必须与写入端取值完全匹配：新增统计查询前必须搜索所有写入端代码，确认查询条件与实际写入取值一致
- 配置项值必须与代码中映射表键名格式严格对齐（如 `config.yaml` 的 `filter_tags` 与 `XIANYU_FILTER_MAP` 键名）

### 推荐（P1 严重）
- 硬编码属性字段（如直接在代码中写 `item["price"]`）应改为模块级常量或数据类属性引用
- 字段值来源应可追溯：从采集→解析→存储→展示的完整链路清晰
- 多数据源结果合并时必须去重（基于唯一标识如 `item_id`）
- 聚合值跨数据源验证（如 DB 统计数据与实时 API 数据对比）

### 禁止
- 多入口调用同一底层 API 时代码各自重复参数合并逻辑（必须提取为共享函数）
- 配置键名与映射表键名不匹配导致静默失效
- 单位转换逻辑在多处各自实现且不一致

## Grep 扫描命令

```bash
# 多入口参数合并一致性
grep -rn "collector\.search\|live_search\|worker\.search" src/xianyu_hunter/ --include="*.py"

# 配置键名与映射表对齐
grep -rn "FILTER_MAP\|SORT_MAP\|REGION_MAP" src/xianyu_hunter/ --include="*.py"
grep -rn "filter_tags\|sort_type\|regions" config/ --include="*.yaml"

# 价格字段优先级
grep -rn "_PRICE_KEYS\s*=" src/xianyu_hunter/ --include="*.py"

# 单位转换一致性
grep -rn "\"万\"\|'万'\|在.*万\|万.*单位" src/xianyu_hunter/ --include="*.py"
```

## 判断标准
- 统计查询条件与写入端不匹配 → P0 阻塞
- 配置键名与映射表键名不对齐 → P0 阻塞
- 多入口参数合并逻辑不一致 → P1 严重
- 单位转换逻辑不一致 → P1 严重
- 多数据源合并无去重 → P1 严重

## 适用/不适用场景
- **适用**：统计页面/仪表盘；多数据源采集与聚合；配置与映射表联动
- **不适用**：单一数据源简单查询；纯展示类只读字段
