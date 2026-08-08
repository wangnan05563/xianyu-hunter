# 维度 27：多路径数据源一致性

> **编码规范引用**：coding-standards v1.3 §统计查询-写入对齐 / 多层级状态校验
> **配置节点**：config.yaml#consistency_and_state_checks / dual_data_source_consistency

## 触发条件
- 统计/聚合查询（Dashboard、报表）
- 多数据源采集合并（JSON 持久化层 + 浏览器运行时层）
- 健康检查/状态检查器
- 数据写入多处同时进行

## 检查规则

### 强制（P0 阻塞）
- 统计查询条件必须与写入端取值完全匹配（如 `COUNT WHERE status='active'` 必须与写入端的 `status` 赋值一致）
- 双数据源（持久化层 + 运行时层）存在时，检查器判定无效后必须回退运行时层兜底复核
- 检查器的检查范围必须与实际消费者依赖范围一致（不检查消费者不依赖的字段，也不漏检消费者依赖的字段）

### 推荐（P1 严重）
- 多数据源结果合并时基于唯一标识去重（如 `item_id`）
- 聚合值跨数据源验证：DB 统计与实时 API 数据对比一致
- 检查器接口必须兼容 sync 和 async 两种实现（`inspect.isawaitable(result)` 判断）
- 兜底复核后应将运行时层最新数据回写到持久化层

### 禁止
- 检查器以持久化层为主源判定无效后直接返回 False（无兜底复核）
- 检查器检查范围 ⊃ 消费者依赖范围（过度检查误判）
- 检查器检查范围 ⊂ 消费者依赖范围（漏检假健康）
- 多数据源结果合并无去重

## Grep 扫描命令

```bash
# 统计查询 vs 写入端匹配
grep -rn "COUNT\|func\.count\|\.count()" src/xianyu_hunter/ --include="*.py" | grep -i "overview\|dashboard\|stats"

# 双数据源兜底复核
grep -rn "cookie_checker\|health_check\|_check_\|get_cookies\|cookie_map" src/xianyu_hunter/ --include="*.py"

# 检查器范围对齐
grep -rn "expires\|is_expired\|cookie.*valid" src/xianyu_hunter/ --include="*.py"

# inspect.isawaitable
grep -rn "isawaitable\|iscoroutinefunction" src/xianyu_hunter/ --include="*.py"
```

## 判断标准
- 统计查询条件与写入端不匹配 → P0 阻塞
- 检查器无兜底复核 → P0 阻塞
- 检查器范围与消费者不对齐 → P1 严重
- 多数据源合并无去重 → P1 严重
- 兜底复核后未回写持久化层 → P2 改进

## 适用/不适用场景
- **适用**：Dashboard/统计页面；双数据源（JSON + 浏览器内存）场景；健康检查器
- **不适用**：单一数据源场景；纯内存无持久化
