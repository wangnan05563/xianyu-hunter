# SQLAlchemy 与数据访问审查（SQLAlchemy）

> **配套技能**：[xianyu-backend-code-review](../SKILL.md)

---

## 1. 项目 ORM 选型

- **SQLAlchemy 2.0 async** + **Alembic** 迁移
- **Pydantic** 模型用于 API 边界和领域 DTO
- **dataclass** 用于纯领域对象

### 1.1 三种模型分离

| 类型 | 用途 | 命名 | 例子 |
|---|---|---|---|
| ORM 模型 | 数据库表映射 | `*ORM` 或 `*Table` | `ItemORM` |
| Pydantic 模型 | API 边界 / 内部 DTO | `*DTO` / `*Schema` | `ItemDTO` |
| Dataclass | 纯数据 | 直接命名 | `Item` |

**为什么分离**：避免 ORM 对象穿透到 API 层（修改后自动持久化是 footgun）。

---

## 2. 仓储层规范

### 2.1 文件命名与结构

```
infra/
├── db.py           # engine / session 创建
├── repo_items.py   # 商品仓储
├── repo_orders.py  # 订单仓储
├── repo_tasks.py   # 任务仓储
└── ...
```

### 2.2 仓储实现

```python
# infra/repo_items.py
from xianyu_hunter.infra.db import async_session
from xianyu_hunter.domain.item_dto import ItemDTO

class ItemRepository:
    async def list_recent(self, limit: int = 50) -> list[ItemDTO]:
        async with async_session() as session:
            stmt = select(ItemORM).order_by(ItemORM.created_at.desc()).limit(limit)
            result = await session.execute(stmt)
            orms = result.scalars().all()
            # ✅ ORM → DTO 转换
            return [ItemDTO.model_validate(o) for o in orms]

    async def get_by_id(self, item_id: str) -> ItemDTO | None:
        async with async_session() as session:
            orm = await session.get(ItemORM, item_id)
            return ItemDTO.model_validate(orm) if orm else None

    async def upsert(self, item: ItemDTO) -> None:
        async with async_session() as session:
            existing = await session.get(ItemORM, item.item_id)
            if existing:
                # 更新
                for k, v in item.model_dump().items():
                    setattr(existing, k, v)
            else:
                # 插入
                session.add(ItemORM(**item.model_dump()))
            await session.commit()
```

### 2.3 方法命名

| 操作 | 命名 | 例子 |
|---|---|---|
| 列表 | `list_xxx` | `list_recent`, `list_by_status` |
| 单个查询 | `get_xxx` | `get_by_id`, `get_active` |
| 插入/更新 | `upsert_xxx` | `upsert`, `upsert_many` |
| 删除 | `delete_xxx` | `delete_by_id` |
| 计数 | `count_xxx` | `count_active` |

### 2.4 返回类型

```python
# ✅ 推荐：返回 DTO
async def get_by_id(self, item_id: str) -> ItemDTO | None:
    ...

# ⚠️ 谨慎：返回 ORM（仅限仓储内部使用，不外传）
async def _get_orm(self, item_id: str) -> ItemORM | None:
    ...

# ❌ 禁止：返回 dict
async def get_by_id(self, item_id: str) -> dict | None:
    ...
```

---

## 3. Session 管理

### 3.1 上下文管理（DB-03）

```python
# ✅ async with 自动关闭
async with async_session() as session:
    result = await session.execute(stmt)
    # 异常 / 正常结束自动 session.close()

# ❌ 反例：手动管理
session = async_session()
result = await session.execute(stmt)  # 异常时 session 未关
```

### 3.2 显式 commit / rollback

```python
# ✅ 写操作显式 commit
async with async_session() as session:
    try:
        session.add(item)
        await session.commit()
    except Exception:
        await session.rollback()  # 显式回滚
        raise
    # 读操作不需要 commit

# ⚠️ 自动 commit（依赖上下文退出）—— 不推荐
```

### 3.3 事务边界

```python
# ✅ 业务层定义事务边界（仓储暴露 commit 接口）
class OrderService:
    async def place_order_with_log(self, order: Order, log: Log):
        async with async_session() as session:
            try:
                await self.order_repo.add(session, order)
                await self.log_repo.add(session, log)
                await session.commit()  # 一次性 commit（原子性）
            except Exception:
                await session.rollback()
                raise
```

### 3.4 Session 注入（高级）

```python
# 仓储接受 session 参数
class ItemRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, item_id: str) -> ItemDTO | None:
        orm = await self.session.get(ItemORM, item_id)
        ...

# 业务层管理 session
@asynccontextmanager
async def transaction():
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

---

## 4. 性能：避免 N+1（DB-06 / PF-01 / PF-05）

### 4.1 预加载

```python
# ❌ N+1：每个 item 单独查 seller
async def list_items_with_seller():
    items = await session.execute(select(ItemORM))
    for item in items.scalars():
        seller = await session.get(SellerORM, item.seller_id)  # N+1
        ...

# ✅ 一次查询：selectinload
async def list_items_with_seller():
    stmt = select(ItemORM).options(selectinload(ItemORM.seller))
    items = await session.execute(stmt)
    return items.scalars().all()
```

### 4.2 批量查询

```python
# ❌ 循环中单条查询
async def get_items_by_ids(ids: list[str]):
    items = []
    for id in ids:
        item = await session.get(ItemORM, id)  # N 次查询
        items.append(item)
    return items

# ✅ 一次查询
async def get_items_by_ids(ids: list[str]):
    stmt = select(ItemORM).where(ItemORM.id.in_(ids))
    result = await session.execute(stmt)
    return result.scalars().all()
```

### 4.3 聚合查询

```python
# ❌ Python 端聚合
items = await repo.list_all()
count = len([i for i in items if i.status == "active"])  # 全表拉到内存

# ✅ 数据库聚合
stmt = select(func.count(ItemORM.id)).where(ItemORM.status == "active")
count = (await session.execute(stmt)).scalar_one()
```

---

## 5. 索引（DB-07）

### 5.1 迁移中添加索引

```python
# alembic/versions/xxx_add_indexes.py
def upgrade():
    op.create_index(
        'ix_items_seller_id_status',
        'items',
        ['seller_id', 'status'],
        unique=False
    )
    op.create_index(
        'ix_orders_created_at',
        'orders',
        ['created_at'],
        unique=False
    )
```

### 5.2 常见索引字段

| 表 | 字段 | 原因 |
|---|---|---|
| `items` | `item_id` (unique) | 主键 |
| `items` | `seller_id` | 按卖家查询 |
| `items` | `created_at` | 按时间排序 |
| `items` | `(seller_id, status)` | 复合查询 |
| `orders` | `task_id` | 按任务查询 |
| `orders` | `created_at` | 时间序列 |

---

## 6. 安全（DB-01 / SC-01 / SC-09）

### 6.1 参数化查询

```python
# ✅ 正确：参数化
stmt = select(ItemORM).where(ItemORM.seller_id == seller_id)

# ✅ 用 text() 时也必须参数化
from sqlalchemy import text
stmt = text("SELECT * FROM items WHERE seller_id = :sid")
result = await session.execute(stmt, {"sid": seller_id})

# ❌ 禁止：字符串拼接（SQL 注入）
stmt = text(f"SELECT * FROM items WHERE seller_id = '{seller_id}'")
```

### 6.2 ORM 对象安全

```python
# ORM 自动参数化（白名单）
stmt = select(ItemORM).where(ItemORM.seller_id == user_input)  # ✅
```

### 6.3 文件路径安全

```python
# ❌ 路径穿越
path = f"data/uploads/{user_filename}"
# 用户传入 "../../etc/passwd"

# ✅ 校验
from pathlib import Path
safe_filename = Path(user_filename).name  # 去掉路径部分
path = Path("data/uploads") / safe_filename
path.resolve().is_relative_to(Path("data/uploads").resolve())  # 验证
```

---

## 7. 异步 SQLAlchemy 模式

### 7.1 创建 Engine

```python
# infra/db.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

DATABASE_URL = "sqlite+aiosqlite:///data/xianyu.db"

engine = create_async_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
    echo=False,  # 生产环境关闭 SQL 日志
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False  # 提交后对象仍可访问
)
```

### 7.2 异步查询

```python
# 查询
result = await session.execute(stmt)
items = result.scalars().all()  # ScalarResult → list
one = result.scalar_one_or_none()  # 单个或 None
count = result.scalar_one()  # 标量

# 写
session.add(item)
await session.flush()  # 发送 SQL 但不 commit
await session.commit()
```

### 7.3 事务上下文

```python
# ✅ 用 session.begin()
async with async_session() as session:
    async with session.begin():  # 自动 commit / rollback
        session.add(item)
```

---

## 8. Alembic 迁移

### 8.1 创建迁移

```bash
alembic revision --autogenerate -m "add orders table"
alembic upgrade head
alembic downgrade -1
```

### 8.2 迁移文件示例

```python
# alembic/versions/xxx_add_orders.py
def upgrade():
    op.create_table(
        'orders',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('task_id', sa.String, nullable=False, index=True),
        sa.Column('item_id', sa.String, nullable=False, index=True),
        sa.Column('status', sa.String, nullable=False, default='pending'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

def downgrade():
    op.drop_table('orders')
```

---

## 9. 常见反模式

| 反模式 | 问题 | 修复 |
|---|---|---|
| 路由直接 `session.execute` | 路由臃肿 | 走 `repo_*.py` |
| 仓储返回 ORM 对象 | 上层耦合 | 返回 DTO |
| N+1 查询 | 性能差 | `selectinload` / `IN` 批量 |
| 字符串拼 SQL | SQL 注入 | 参数化 / ORM |
| 全表拉到内存 | 内存爆 | 分页 / 聚合 |
| 缺索引 | 全表扫描 | 迁移加索引 |
| 手动管理 session | 资源泄漏 | `async with` |
| 异常未 rollback | 事务悬挂 | try/except/rollback |
| 仓储返回 `dict` | 类型不安全 | 返回 Pydantic |
| 一个事务过大 | 锁竞争 | 拆小事务 |

---

## 10. 审查 checklist

| 类别 | 检查项 |
|---|---|
| 仓储 | 命名规范？返回 DTO？ |
| Session | `async with` 上下文？显式 commit/rollback？ |
| 性能 | N+1 已避免？批量查询？索引已加？ |
| 安全 | 参数化查询？无字符串拼 SQL？ |
| ORM 用法 | `selectinload`？`func` 聚合？分页？ |
| 事务 | 边界清晰？异常回滚？ |
| 迁移 | 索引？类型？默认值？ |
| 错误处理 | 仓储异常清晰？业务层捕获？ |

---

## 11. 复盘：从对话中提炼

### 11.1 案例：抢单策略保存 Bug（涉及配置存储）

虽不直接涉及 SQLAlchemy，但保存路径用了类似"先读 → 改 → 写"模式：

```python
# 类似 SQLAlchemy 事务：read-modify-write
current = yaml.safe_load(open("config/config.yaml").read())
new = copy.deepcopy(current)
_deep_merge(new, payload)
yaml.safe_dump(new, open("config/config.yaml", "w"))
```

**Bug 风险**：浅合并导致用户修改被覆盖（等价于"两个并发事务，第二个覆盖第一个"）。

**修复**：深度合并 + reload（等价于"乐观锁"思想）。

---

## 12. 参考

- [SQLAlchemy 2.0 异步](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Alembic 文档](https://alembic.sqlalchemy.org/en/latest/)
- [SQLAlchemy 性能](https://docs.sqlalchemy.org/en/20/orm/loading_relationships.html)
- [Pydantic + SQLAlchemy](https://docs.pydantic.dev/latest/concepts/orm_mode/)
- [项目编码规范总入口](../../xianyu-hunter-dev/references/coding-standards.md)

---

## 十二、SQLite 原始 SQL 查询类型兼容

### 12.1 问题描述

通过 `text()` 原始 SQL 查询时，SQLAlchemy 不走 ORM 类型转换。SQLite 驱动返回 Python 原生类型：

| 列类型 | ORM 查询返回 | text() 查询返回 |
|---|---|---|
| DateTime | `datetime` 对象 | `str`（如 `"2025-01-01 00:00:00"`） |
| JSON / Text | `str` | `str`（一致） |
| Integer | `int` | `int`（一致） |

### 12.2 审查规则

| 规则 | 说明 |
|---|---|
| **datetime 列序列化前检查类型** | `hasattr(obj, 'isoformat')` 区分 datetime 和字符串 |
| **json 列同理** | 可能返回 str 而非 dict，需要 `json.loads()` 或类型判断 |
| **ORM 查询不受影响** | `session.query(Model)` 自动类型转换 |

### 12.3 正确模式

```python
# ✅ 兼容 datetime 对象和字符串
"created_at": (
    r["created_at"].isoformat()
    if hasattr(r["created_at"], "isoformat")
    else str(r["created_at"])
    if r["created_at"] else None
)

# ❌ 假设 text() 返回 datetime 对象
"created_at": r["created_at"].isoformat() if r["created_at"] else None  # AttributeError!
```

### 12.4 适用场景

- ✅ 所有通过 `text()` 查询 datetime/json 列的序列化代码
- ❌ ORM 查询（自动类型转换）
- ❌ Pydantic 序列化场景（自带类型适配）

---

## 十三、级联删除策略

### 13.1 问题描述

SQLite 建表时未声明 `ON DELETE CASCADE`（SQLAlchemy 默认不生成外键级联行为），删除主表记录时关联数据不会自动处理，产生孤立记录。

### 13.2 审查规则

| 规则 | 说明 |
|---|---|
| **定义 TABLE_RELATIONS** | 每个有外键引用的表必须定义级联策略 |
| **cascade vs set_null** | 核心实体用 cascade，辅助实体用 set_null |
| **先级联后删主记录** | 在同一事务中先处理关联表，再删主表 |
| **级联预览 API** | 提供只读预览接口，删除前让用户确认 |
| **审计日志** | 级联详情写入 events 表 |

### 13.3 正确模式

```python
# 级联策略定义
TABLE_RELATIONS = {
    "tasks": [
        {"table": "items", "fk": "task_id", "action": "cascade"},
        {"table": "orders", "fk": "task_id", "action": "cascade"},
    ],
    "sellers": [
        {"table": "items", "fk": "seller_id", "action": "set_null"},
    ],
}

# 级联执行（在同一事务中）
def _cascade_delete(conn, table, pk_col_name, pk_values):
    for rel in TABLE_RELATIONS.get(table, []):
        if rel["action"] == "cascade":
            conn.execute(text(f"DELETE FROM {rel['table']} WHERE {rel['fk']} IN :pks"), ...)
        elif rel["action"] == "set_null":
            conn.execute(text(f"UPDATE {rel['table']} SET {rel['fk']} = NULL WHERE {rel['fk']} IN :pks"), ...)

# 删除端点
with engine.begin() as conn:
    cascade_affected = _cascade_delete(conn, table, pk_col, [pk_val])  # 先级联
    result = conn.execute(text(f"DELETE FROM {table} WHERE {pk_col} = :pk"), {"pk": pk_val})  # 再删主表
```

### 13.4 策略选择原则

| 策略 | 适用场景 | 理由 |
|---|---|---|
| `cascade` | 核心实体被删 | 依赖数据无独立存在价值 |
| `set_null` | 辅助实体被删 | 关联数据仍有查看价值 |
| 直接删除 | 叶子表 | 无下游依赖 |

---

## 十四、数据库字段语义标注

### 14.1 审查规则

| 规则 | 说明 |
|---|---|
| **每个字段有 COLUMN_LABELS** | 提供中文业务含义+类型特征+使用场景+约束条件 |
| **标注格式** | `业务名称（数据类型特征，使用场景，约束说明）` |
| **_get_columns 返回 label** | 反射列元数据时包含 label 字段 |
| **新增字段同步更新** | 新增数据库列时必须同步添加标注 |

### 14.2 正确模式

```python
COLUMN_LABELS = {
    "tasks": {
        "status": "任务状态（running=运行中/paused=已暂停/stopped=已停止/completed=已完成）",
        "cron": "Cron表达式（调度频率，默认*/1 * * * *即每分钟执行）",
    },
}

def _get_columns(container, table):
    return [{"name": c["name"], ..., "label": COLUMN_LABELS.get(table, {}).get(c["name"], "")} for c in cols]
```
