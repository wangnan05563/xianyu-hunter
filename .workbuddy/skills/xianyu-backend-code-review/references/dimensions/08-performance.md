# 维度 8：性能评审

> **编码规范引用**：coding-standards v1.3 §性能优化八步法
> **配置节点**：config.yaml#performance
> **参考文档**：references/performance.md

## 触发条件
- 新增/修改数据库查询时
- 新增/修改 I/O 密集操作时
- 数据量增长导致响应变慢时
- 新增缓存逻辑时

## 检查规则

### 强制（P0 阻塞）
- N+1 查询已避免：关联数据用 `selectinload()` 或 `IN` 批量查询
- 数据库聚合在 SQL 层完成：`func.count()` / `func.sum()` / `CASE WHEN`，禁止 Python 端聚合
- 异步化：同步阻塞调用用 `run_in_executor` 包装
- 批量写入：避免循环中单条 `session.add()` + `commit()`

### 推荐（P1 严重）
- 缓存用 `dict + TTL` 模式，TTL 从 `config.yaml` 读取
- 空结果（0 条记录）也必须缓存，防止反复触发重查询
- 合并查询：`list + count` 一次查询完成
- 大结果集用 `yield_per(N)` 流式加载
- `list` API 必须有默认 `limit`（如 50）和上限（如 200）
- 共享 HTTP session（aiohttp.ClientSession 单例）
- 日志使用占位符而非 f-string

### 禁止
- 循环中 `await session.get(Model, id)` N 次
- Python 端 `len([x for x in items if ...])` 替代 SQL 聚合
- 全表加载到内存做过滤
- 每请求创建新的 HTTP session

## Grep 扫描命令
```bash
# 检测 N+1 查询模式
grep -rn "for.*in.*:.*await.*session\.get\|for.*in.*:.*await.*session\.execute" src/xianyu_hunter/

# 检测 Python 端聚合
grep -rn "len(\[.*for.*in" src/xianyu_hunter/

# 检测缺少 limit 的 list 查询
grep -rn "select(.*ORM).*\.all()" src/xianyu_hunter/ | grep -v "limit"

# 检测硬编码 TTL
grep -rn "TTL\s*=\s*\d+\|ttl\s*=\s*\d+\|_TTL\s*=\s*\d+" src/xianyu_hunter/
```

## 判断标准
- N+1 查询：P0 阻塞
- Python 端聚合可下推 SQL：P0 阻塞
- 无 limit 的全表查询：P0 阻塞
- 硬编码 TTL：P1 严重
- 空结果未缓存：P1 严重

## 适用场景
- 所有仓储层查询方法
- `modules/` 中的批量处理逻辑
- 高频调用 API 的缓存设计
- 大数据量统计/导出场景

## 不适用场景
- 单条主键查询（天然 O(1)）
- 配置加载的 lru_cache（不是本维度重点）
- 低频管理操作（如手动触发的一次性任务）
