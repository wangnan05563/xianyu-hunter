# 维度 39：SQLAlchemy 写路径并发保护

> **编码规范引用**：coding-standards v1.3 §SQLAlchemy 规范 + references/sqlalchemy.md
> **配置节点**：config.yaml#sqlalchemy_write_concurrency

## 触发条件
- 数据库写操作（INSERT/UPDATE/DELETE）
- Session 管理代码
- 多线程/多协程并发访问 SQLite
- 多租户/多用户写入同一表

## 检查规则

### 强制（P0 阻塞）
- **Session 显式事务管理**：所有写操作必须在 `async with async_session() as session:` 内+ `await session.commit()`，禁止共享 session 跨请求
- **SQLite 并发保护**：SQLite 写路径必须使用同步锁（`asyncio.Lock` / `threading.Lock`），避免 "database is locked" 错误
- **多租户隔离**：写操作必须携带 `user_id` / `task_id` 过滤条件，禁止无隔离的全表 UPDATE/DELETE

### 推荐（P1 严重）
- 写路径并发选型根据场景：单进程用 `asyncio.Lock`，多进程用 `threading.RLock` 或文件锁
- 优先 ORM 表达式（`update(X).where(...).values(...)`）而非原始 SQL 字符串
- 批量写入用 `session.add_all()` 或 `bulk_insert_mappings` 而非循环逐个 `session.add()`
- 写操作异常后必须 `session.rollback()`，确保连接池正常回收

### 禁止
- 共享 session 跨请求/跨协程（导致事务混乱）
- SQLite 写路径无锁（并发写入触发 "database is locked"）
- 全表 UPDATE/DELETE 无 WHERE 条件
- 写操作异常后未 `rollback()`

## Grep 扫描命令

```bash
# Session 共享检查
grep -rn "async_session\(\)" src/xianyu_hunter/ --include="*.py"
grep -rn "session\.commit\|session\.rollback" src/xianyu_hunter/ --include="*.py"

# SQLite 并发锁
grep -rn "asyncio\.Lock\|threading\.Lock\|RLock\|Semaphore" src/xianyu_hunter/ --include="*.py"

# 全表操作检查
grep -rn "DELETE FROM\|\.delete()\|UPDATE.*SET" src/xianyu_hunter/ --include="*.py" | grep -v "WHERE\|where"

# 批量写入模式
grep -rn "session\.add\|session\.add_all\|bulk_insert" src/xianyu_hunter/ --include="*.py"

# 原始 SQL 拼接
grep -rn "session\.execute(text\|session\.execute(f\"" src/xianyu_hunter/ --include="*.py"
```

## 判断标准
- 写操作无显式事务管理 → P0 阻塞
- SQLite 写路径无锁 → P0 阻塞
- UPDATE/DELETE 无 WHERE 条件 → P0 阻塞
- 共享 session 跨请求 → P0 阻塞
- 循环内逐个 add（非批量）→ P1 严重
- 写异常后未 rollback → P1 严重

## 适用/不适用场景
- **适用**：所有数据库写操作；SQLite 并发访问；多租户数据隔离
- **不适用**：只读查询；内存数据库无并发竞争；单用户单协程操作
