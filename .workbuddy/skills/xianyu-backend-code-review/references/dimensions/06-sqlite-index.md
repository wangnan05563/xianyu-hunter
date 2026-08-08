# 维度 6：SQLite 优化与索引

> **编码规范引用**：coding-standards v1.3 hard constraints §数据库索引
> **配置节点**：config.yaml#sqlite_optimization
> **参考文档**：references/sqlalchemy.md §5 / §12

## 触发条件
- 新增数据库表或查询时
- Dashboard/统计查询性能优化时
- 数据量增长导致查询变慢时

## 检查规则

### 强制（P0 阻塞）
- 数据库连接池：SQLite 专用 `poolclass=NullPool`，`timeout=10`，`check_same_thread=False`
- PRAGMA 优化：`journal_mode=WAL`、`busy_timeout=10000`、`cache_size=-20000`
- 必须建索引字段：`task_id`、`seller_id`、`first_seen`、`publish_time`、`created_at`、`request_id`
- 索引一致性双向：ORM `__table_args__` 中的 `Index` 定义 ↔ `init_db` 中的 `_migrate_create_index` 必须一一对应

### 推荐（P1 严重）
- COUNT 查询用 `CASE WHEN` 聚合合并（减少 DB 调用，如 3 次 → 1 次）
- 复合索引按过滤列+排序列顺序设计：`(filter_col, order_col)`
- Dashboard 查询使用复合索引优化
- 大结果集使用 `yield_per(N)` 流式加载而非一次全部加载
- 文件锁绕过：SQLite URI `immutable=1` 参数（只读场景）

### 禁止
- 全表扫描无索引的查询（WHERE 条件字段无对应索引）
- 使用 `OFFSET` 大数据量分页（应使用游标分页 `id > last_id`）
- 在 Python 内存中做聚合（应用 SQL 的 `func.count()` / `func.sum()`）

## Grep 扫描命令
```bash
# 检测索引定义不一致（ORM vs 迁移脚本）
grep -rn "Index(" src/xianyu_hunter/infra/ --include="*.py" -A 2
grep -rn "_migrate_create_index" src/xianyu_hunter/

# 检测 Python 端聚合（可能应下推到 SQL）
grep -rn "len(\[.*for.*if" src/xianyu_hunter/

# 检测 OFFSET 分页（大数据量风险）
grep -rn "\.offset(" src/xianyu_hunter/

# 检查 WAL 模式是否启用
grep -rn "journal_mode" src/xianyu_hunter/
```

## 判断标准
- 缺少必须索引：P0 阻塞
- 索引双向不一致：P0 阻塞
- 全表聚合未下推 SQL：P1 严重
- 大 OFFSET 分页：P1 严重

## 适用场景
- `infra/db.py` 数据库初始化
- 所有仓储层的查询方法
- 统计/聚合类 API（Dashboard 等）
- 数据量超过 10000 行的表

## 不适用场景
- 数据量 < 100 行的配置表
- 仅按主键查询的场景
- SQLite 内置表（sqlite_master 等）
