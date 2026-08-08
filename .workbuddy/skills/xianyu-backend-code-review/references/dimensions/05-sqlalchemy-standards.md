# 维度 5：SQLAlchemy 2.0 规范

> **编码规范引用**：coding-standards v1.3 §2.11 datetime 时区一致性
> **配置节点**：config.yaml#sqlalchemy_patterns
> **参考文档**：references/sqlalchemy.md

## 触发条件
- 新增/修改 ORM 模型、仓储、迁移脚本时
- 原始 SQL（`text()`）查询时
- 数据库 schema 变更时
- UPSERT 操作时

## 检查规则

### 强制（P0 阻塞）
- ORM 模型使用 `DeclarativeBase` + `Mapped` + `mapped_column` 风格（SQLAlchemy 2.0）
- 时间字段统一 UTC：`_utcnow = lambda: datetime.now(timezone.utc)`，SQLite 读回 naive datetime 时运算前 `.replace(tzinfo=None)`
- SQL 注入防护：LIKE 用 `_escape_like()`、表名列名用 `_IDENT_RE` 白名单、用户 ID 用 `_USER_ID_RE` 校验
- 所有写操作必须使用 `async with async_session() as session` 上下文管理（B-REVIEW-320）
- 多用户查询必须带 `user_id` 隔离条件（B-REVIEW-321）
- 写路径必须有并发保护（乐观锁/Redis锁/FOR UPDATE）（B-REVIEW-322）

### 推荐（P1 严重）
- Schema 变更必须幂等：`_migrate_add_column`、`_migrate_create_index`（IF NOT EXISTS）
- UPSERT 用 `on_conflict_do_update`
- 优先使用 ORM 表达式而非 `text()` 拼接字符串（B-REVIEW-323）
- 参数透传完整性：方法签名新增参数必须同步更新所有内部调用点
- 返回 DTO 而非 ORM 对象，不返回 `dict`
- 仓储方法命名规范：`list_xxx` / `get_xxx` / `upsert_xxx` / `delete_xxx` / `count_xxx`

### 禁止
- `text(f"SELECT ... WHERE x = '{input}'")` 字符串拼接
- `session = async_session()` 不使用 `async with`
- 事务内调用外部 API 或执行长时间操作
- 仓储返回 ORM 对象给上层

## Grep 扫描命令
```bash
# 检测 Session 管理违规
grep -rn "session\s*=\s*async_session()" src/xianyu_hunter/

# 检测字符串拼接 SQL
grep -rn "text(f['\"]" src/xianyu_hunter/

# 检测缺少 user_id 隔离的查询
grep -rn "select(\w+ORM)\.where(\w+\.id\s*==" src/xianyu_hunter/

# 检测写路径无并发保护
grep -rnE "session\.execute\(update\(\w+\)\.where\(\w+\.id\s*==[^)]+\)\.values\(" src/xianyu_hunter/

# 检测 datetime 运算前后时区不一致
grep -rn "_utcnow\(\)\s*-" src/xianyu_hunter/
```

## 判断标准
- 字符串拼接 SQL：P0 阻塞
- Session 手动管理：P0 阻塞
- 缺少 user_id 隔离：P0 阻塞
- datetime 运算混用 aware/naive：P0 阻塞
- 返回 dict/ORM 给上层：P1 严重
- UPSERT 非幂等：P1 严重

## 适用场景
- `infra/repo_*.py` 仓储层
- `infra/db.py` 数据库初始化和迁移
- 所有使用 `text()` 原始 SQL 的场景
- datetime 列读写和运算

## 不适用场景
- 纯读操作（无需并发保护）
- SQLite DDL 操作（如建表、加索引）
- 单元测试中 mock 的 session
