# 维度 35：列表聚合与状态联动

> **编码规范引用**：coding-standards v1.3 §统计查询-写入对齐 / 性能优化八步法
> **配置节点**：config.yaml#consistency_and_state_checks

## 触发条件
- Dashboard/列表页查询
- 统计聚合（COUNT/SUM/AVG）
- 分页查询 + 过滤条件联动
- 状态变更触发列表刷新

## 检查规则

### 强制（P0 阻塞）
- 列表查询与统计聚合一致性：同一页面的列表数据和顶栏统计数据必须使用一致的过滤条件
- COUNT 查询合并：`_overview()` 中的多个 COUNT 必须用 CASE WHEN 聚合查询减少 DB 调用
- 分页查询的总数（`COUNT(*)`）必须与列表数据的过滤条件完全一致

### 推荐（P1 严重）
- 状态变更后必须触发列表刷新：如任务状态从"运行中"变为"暂停"，列表中的状态标识和操作按钮必须联动更新
- 列表的过滤/排序/分页参数变化时，统计数字同步刷新
- 批量预查询优化：循环内不得逐个查询 DB（N+1），应循环前批量预查询 + set/dict 缓存
- 列表数据必须基于固定排序键分页，避免数据漂移（新增/删除导致翻页时重复或遗漏）

### 禁止
- 列表的 `COUNT(*)` 查询与列表查询使用不同的过滤条件
- 状态变更不刷新列表（用户看到过期数据）
- 循环内逐个 DB 查询

## Grep 扫描命令

```bash
# COUNT 查询 vs 列表过滤一致性
grep -rn "COUNT\|func\.count" src/xianyu_hunter/ --include="*.py" | grep -i "overview\|dashboard\|list"
grep -rn "select.*where\|\.filter\|\.where" src/xianyu_hunter/ --include="*.py" | grep -i "overview\|dashboard\|list"

# CASE WHEN 聚合
grep -rn "CASE.*WHEN\|case.*when" src/xianyu_hunter/ --include="*.py"

# 批量预查询
grep -rn "for\s+\w+\s+in" src/xianyu_hunter/ --include="*.py" -A 3 | grep "repo\.\|session\.\|db\."

# 分页漂移
grep -rn "ORDER BY\|order_by\|offset\|limit" src/xianyu_hunter/ --include="*.py"
```

## 判断标准
- `COUNT(*)` 与列表查询过滤条件不一致 → P0 阻塞
- `_overview()` 未用 CASE WHEN 合并 COUNT → P1 严重
- 状态变更不触发列表刷新 → P1 严重
- 循环内 N+1 查询 → P1 严重
- 分页无固定排序键 → P1 严重

## 适用/不适用场景
- **适用**：Dashboard 页面；列表/表格查询；统计聚合；分页列表
- **不适用**：无统计聚合的简单列表；单页查询无需分页；纯实时查询无缓存
