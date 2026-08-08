# 数据库开发指南

> 本文档整合了闲鱼猎人项目的数据库设计规范与开发实践，是 SQLite + SQLAlchemy 2.0 + ChromaDB 三层存储体系的完整参考。

---

## 目录

- [一、存储架构总览](#一存储架构总览)
- [二、SQLite 引擎配置](#二sqlite-引擎配置)
- [三、SQLAlchemy 2.0 表结构规范](#三sqlalchemy-20-表结构规范)
- [四、表设计清单](#四表设计清单)
- [五、索引策略](#五索引策略)
- [六、JSON 字段约定](#六json-字段约定)
- [七、时间字段约定](#七时间字段约定)
- [八、幂等迁移模式](#八幂等迁移模式)
- [九、Repository Mixin 组合模式](#九repository-mixin-组合模式)
- [十、查询规范与性能优化](#十查询规范与性能优化)
- [十一、安全规范](#十一安全规范)
- [十二、ChromaDB 向量库](#十二chromadb-向量库)
- [十三、常见问题与最佳实践](#十三常见问题与最佳实践)

---

## 一、存储架构总览

闲鱼猎人采用三层存储体系：

| 存储层 | 技术选型 | 用途 | 路径 |
|--------|---------|------|------|
| 关系型 | SQLite 3 (WAL 模式) | 任务/商品/订单/事件/通知等业务数据 | `data/xianyu.db` |
| 向量型 | ChromaDB | 智能客服 RAG 检索（文档片段向量） | `data/chatbot_vector/` |
| 文件型 | YAML + JSON | 配置文件、知识库快照 | `config/`、`data/chatbot_snapshots/` |

**设计原则**：
- **单文件 SQLite**：部署简单，适合单机场景，避免运维复杂度
- **WAL 模式 + NullPool**：兼顾读写并发与连接复用
- **应用层维护关系**：表之间无外键约束（SQLite 外键支持有限），关系由 Repository 层保证
- **JSON 字段灵活扩展**：稀疏字段用 JSON 列存储，避免 schema 臃肿

---

## 二、SQLite 引擎配置

### 2.1 引擎初始化

**【强制】** 必须使用 `create_sqlite_engine()` 工厂函数创建引擎，禁止直接调用 `create_engine()`。

```python
# src/xianyu_hunter/infra/db_models.py
def create_sqlite_engine(db_path: str) -> Engine:
    """创建 SQLite 引擎，统一启用 WAL + busy_timeout"""
    engine = create_engine(
        f"sqlite:///{db_path}",
        # NullPool：每次连接从池中取/归还，避免 SQLite 连接长期持有锁
        # 为什么用 NullPool：SQLite 单文件锁粒度粗，连接复用收益低且易触发锁竞争
        poolclass=NullPool,
        connect_args={
            "check_same_thread": False,  # 允许跨线程使用（FastAPI 异步需要）
            "timeout": 10,               # busy_timeout 10s，等待锁释放
        },
    )
    # PRAGMA 必须在连接初始化时执行
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")      # WAL 模式：读写不互斥
        cur.execute("PRAGMA synchronous=NORMAL")    # 性能与可靠性平衡
        cur.execute("PRAGMA busy_timeout=10000")    # 锁等待 10s
        cur.execute("PRAGMA foreign_keys=OFF")      # 应用层维护关系
        cur.close()
    return engine
```

### 2.2 关键 PRAGMA 说明

| PRAGMA | 值 | 说明 |
|--------|-----|------|
| `journal_mode` | `WAL` | Write-Ahead Logging，读写不互斥，提升并发 |
| `synchronous` | `NORMAL` | WAL 模式下安全且性能优 |
| `busy_timeout` | `10000` | 锁等待 10s，避免 SQLITE_BUSY 错误 |
| `foreign_keys` | `OFF` | 不使用外键约束，关系由应用层维护 |

### 2.3 初始化与迁移

```python
def init_db(db_path: str) -> None:
    """初始化数据库：create_all 建表 + 幂等迁移"""
    engine = create_sqlite_engine(db_path)
    Base.metadata.create_all(engine)  # 幂等：已存在的表不会重建
    _run_migrations(engine)            # 幂等迁移（见 §八）
```

---

## 三、SQLAlchemy 2.0 表结构规范

### 3.1 基类定义

**【强制】** 所有 ORM 模型必须继承 `Base`（`DeclarativeBase` 子类）。

```python
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    """所有 ORM 模型的基类"""
    pass
```

### 3.2 类型注解风格

**【强制】** 使用 SQLAlchemy 2.0 的 `Mapped[T]` + `mapped_column()` 风格，禁止 1.x 的 `Column()` 风格。

```python
from sqlalchemy import String, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column

class TaskRow(Base):
    __tablename__ = "tasks"
    
    # 必填字段：Mapped[T]（无 Optional）
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    
    # 可空字段：Mapped[T | None]
    min_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    # 带默认值
    status: Mapped[str] = mapped_column(String, nullable=False, default="running")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
```

### 3.3 命名规范

| 元素 | 规则 | 示例 |
|------|------|------|
| 表名 | snake_case 复数 | `tasks`、`items`、`error_logs` |
| 类名 | PascalCase + Row 后缀 | `TaskRow`、`ItemRow`、`ErrorLogRow` |
| 列名 | snake_case | `task_id`、`created_at`、`is_sold` |
| 索引名 | `ix_{table}_{columns}` | `ix_items_task_first_seen` |
| 唯一约束 | `uq_{table}_{columns}` | `uq_task_link` |

### 3.4 主键策略

- **业务主键**：`String` 类型，由应用层生成（如 UUID32），如 `tasks.id`、`items.id`
- **自增主键**：`Integer` + `autoincrement=True`，用于日志/事件类表，如 `events.id`、`error_logs.id`

---

## 四、表设计清单

闲鱼猎人共 26 张表，按业务域分类：

### 4.1 核心业务表（10 张）

| 表名 | 用途 | 主键类型 |
|------|------|---------|
| `tasks` | 任务定义 | String (UUID) |
| `items` | 商品快照 | String |
| `sellers` | 卖家信息 | String |
| `evaluations` | 评估结果 | Integer (自增) |
| `orders` | 订单快照 | String |
| `events` | 事件日志 | Integer (自增) |
| `error_logs` | 后台错误日志 | Integer (自增) |
| `task_links` | 任务-内容关联 | Integer (自增) |
| `task_deps` | 任务依赖关系 | Integer (自增) |
| `notifications` | 业务通知 | Integer (自增) |

### 4.2 批量采集表（2 张）

| 表名 | 用途 |
|------|------|
| `batch_refresh_progress` | 断点续传进度（单行设计） |
| `batch_refresh_history` | 批量采集执行历史 |

### 4.3 账号与代理表（2 张）

| 表名 | 用途 |
|------|------|
| `accounts` | 闲鱼账号池（多账号轮换） |
| `proxies` | 代理 IP 池 |

### 4.4 智能客服表（5 张，统一 `chatbot_` 前缀）

| 表名 | 用途 |
|------|------|
| `chatbot_sessions` | 会话表 |
| `chatbot_messages` | 消息表 |
| `chatbot_kb_versions` | 知识库版本记录 |
| `chatbot_feedback` | 用户反馈 |
| `chatbot_ai_usage` | AI 预算追踪 |

### 4.5 其他辅助表

包括 `evaluations` 索引扩展、配置覆盖字段等。

---

## 五、索引策略

### 5.1 索引设计原则

**【强制】** 以下列必须建索引：
- `task_id` — 任务关联查询
- `seller_id` — 卖家维度查询
- `first_seen` — 时间排序
- `publish_time` — 发布时间过滤
- `created_at` — 创建时间排序
- `request_id` — 链路追踪
- 状态字段（如 `status`）— 仅当区分度高时

### 5.2 复合索引设计

**【强制】** 复合索引按"过滤列 + 排序列"顺序设计，覆盖核心查询路径。

```python
class ItemRow(Base):
    __tablename__ = "items"
    __table_args__ = (
        # 商品列表查询：WHERE task_id=? ORDER BY first_seen DESC
        Index("ix_items_task_first_seen", "task_id", "first_seen"),
        Index("ix_items_seller", "seller_id"),
        Index("ix_items_publish_time", "publish_time"),
    )

class TaskLinkRow(Base):
    __tablename__ = "task_links"
    __table_args__ = (
        # 三元组复合索引：covering index scan，避免临时 B-Tree 排序
        Index("ix_task_links_task_type_created", "task_id", "link_type", "created_at"),
        # 批量删除：WHERE task_id=? AND source='auto'
        Index("ix_task_links_task_source", "task_id", "source"),
    )
```

### 5.3 索引使用禁忌

**【禁止】** 以下行为：
- 为区分度低的列（如布尔值）单独建索引
- 在 JSON 字段上建索引（SQLite 不支持 JSON 索引）
- 创建从未被查询使用的索引（增加写入开销）

### 5.4 索引一致性双写规则 🆕

**问题背景**：ORM `__table_args__` 中定义的 `Index(...)` 仅对新建数据库生效，已有数据库不会自动补建。导致 ORM 定义与实际数据库索引不一致，查询执行计划与预期不符。

**强制规则**：新增或修改索引时，必须同步更新两处：

| 位置 | 作用 | 生效时机 |
|------|------|----------|
| ORM `__table_args__` 中的 `Index(...)` | 新建数据库时自动创建索引 | `Base.metadata.create_all(engine)` 执行时 |
| `init_db()` 中的 `_migrate_create_index(...)` | 已有数据库增量补建索引 | 服务启动时（幂等，已存在则跳过） |

**审查要点**：
- `__table_args__` 中有 `Index(...)` 但 `init_db()` 中无对应 `_migrate_create_index` → 违规
- `init_db()` 中有 `_migrate_create_index` 但 `__table_args__` 中无对应 `Index(...)` → 违规（新建数据库会缺失）
- 两者索引名必须一致

**示例**（以 `ix_task_links_task_type_created` 为例）：

```python
# 1. ORM 定义（新建数据库生效）
class TaskLinkRow(Base):
    __table_args__ = (
        Index("ix_task_links_task_type_created", "task_id", "link_type", "created_at"),
    )

# 2. 增量迁移（已有数据库生效）
def init_db(db_path: str = "data/xianyu.db") -> None:
    # ...
    _migrate_create_index(engine, "task_links", "ix_task_links_task_type_created", "task_id, link_type, created_at")
```

**验证方法**：`PRAGMA index_list('<table>')` 检查实际索引，与 ORM 定义比对。

---

## 六、JSON 字段约定

### 6.1 何时使用 JSON 字段

**【推荐】** 以下场景使用 JSON 字段：
- **稀疏字段**：任务级配置覆盖（`search_config`、`price_config` 等），多数任务为空
- **数组数据**：`image_urls`、`exclude_words`、`notifier_channels`
- **灵活扩展**：`payload`、`metadata_json`、`display`

**【禁止】** 以下场景使用 JSON 字段：
- 需要独立查询/排序的字段
- 高频更新的字段（JSON 整体替换成本高）
- 区分度高的过滤字段（应建独立列 + 索引）

### 6.2 JSON 字段读写规范

**【强制】** 写入前必须 `json.dumps()`，读取时通过 `_row_to_dict()` 自动解析。

```python
# 写入
task.search_config = json.dumps({"page_size": 30, "sort_type": "newest"})

# 读取（_row_to_dict 自动解析已知 JSON 字段）
row_dict = Repository._row_to_dict(row)
config = row_dict["search_config"]  # 已是 dict，无需 json.loads
```

### 6.3 已知 JSON 字段清单

`_row_to_dict()` 中显式声明的 JSON 字段（需同步更新）：

```python
JSON_FIELDS = (
    "exclude_words", "notifier_channels", "image_urls",
    "raw_json", "recent_posts_json", "dimension_scores",
    "reject_reasons", "payload", "display", "search_filters",
)
```

---

## 七、时间字段约定

### 7.1 统一 UTC

**【强制】** 所有 `datetime` 列统一使用 UTC 时间，通过 `_utcnow()` 函数生成。

```python
from datetime import datetime, timezone

def _utcnow() -> datetime:
    """返回当前 UTC 时间
    
    使用 timezone-aware 的 datetime.now(UTC) 替代已弃用的 datetime.utcnow()。
    SQLite 不存储时区信息，但 Python 侧统一 UTC 避免混淆。
    """
    return datetime.now(timezone.utc)
```

### 7.2 时间字段命名约定

| 后缀 | 含义 | 示例 |
|------|------|------|
| `_at` | 绝对时间点 | `created_at`、`updated_at`、`paid_at` |
| `_until` | 截止时间 | `cooldown_until` |
| `_detected_at` | 检测时间 | `sold_detected_at` |

### 7.3 `onupdate` 自动更新

```python
updated_at: Mapped[datetime] = mapped_column(
    DateTime, default=_utcnow, onupdate=_utcnow
)
```

**注意**：`onupdate` 仅在 ORM `update` 操作时触发，原生 SQL 不触发。

---

## 八、幂等迁移模式

### 8.1 迁移原则

**【强制】** 所有迁移必须幂等（可重复执行不报错），通过 `PRAGMA table_info` 检查列是否存在。

### 8.2 标准迁移模板

```python
def _run_migrations(engine: Engine) -> None:
    """幂等迁移：检查列存在性后再执行 ALTER TABLE"""
    with engine.connect() as conn:
        # 1. 检查并添加列
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info(tasks)"))}
        if "user_id" not in cols:
            # 为什么用 server_default：全新数据库 create_all 后 raw SQL INSERT
            # 未指定 user_id 时也能自动填充 'default'
            conn.execute(text(
                "ALTER TABLE tasks ADD COLUMN user_id TEXT NOT NULL DEFAULT 'default'"
            ))
            conn.commit()
        
        # 2. 检查并创建索引
        indexes = {row[1] for row in conn.execute(
            text("PRAGMA index_list(tasks)")
        )}
        if "ix_tasks_user_id" not in indexes:
            conn.execute(text("CREATE INDEX ix_tasks_user_id ON tasks(user_id)"))
            conn.commit()
```

### 8.3 迁移注意事项

**【强制】** 迁移代码必须：
- 在 `try/except` 中包裹，重复执行不报错
- 使用 `conn.commit()` 显式提交 DDL
- 迁移后更新 `db_models.py` 中的 ORM 定义（保持 schema 与代码一致）

---

## 九、Repository Mixin 组合模式

### 9.1 架构设计

闲鱼猎人采用 **Mixin 组合模式** 实现 Repository，避免单一巨型类：

```
RepositoryBase（基类：引擎管理 + 通用工具方法）
    ↑
    ├── TasksMixin        （任务 CRUD）
    ├── ItemsMixin        （商品查询）
    ├── EventsMixin       （事件日志）
    ├── ErrorLogsMixin    （错误日志）
    ├── TaskDepsMixin     （任务依赖）
    ├── TaskLinksMixin    （任务关联）
    ├── EvaluationsMixin  （评估结果）
    ├── OrdersMixin       （订单）
    ├── NotificationsMixin（通知）
    └── SellersMixin      （卖家）
    ↑
Repository（运行时动态组合的具体类）
```

### 9.2 延迟构建避免循环导入

**【强制】** Mixin 文件反向导入 `RepositoryBase`，必须通过 `importlib` 延迟构建。

```python
# src/xianyu_hunter/infra/repository_base.py
import importlib

_mixin_modules = [
    'xianyu_hunter.infra.repo_tasks',
    'xianyu_hunter.infra.repo_items',
    # ... 10 个 Mixin
]

def _get_repository_class():
    """延迟构建 Repository 类，避免模块级循环导入"""
    mixin_classes = []
    for mod_name, cls_name in zip(_mixin_modules, [
        'TasksMixin', 'ItemsMixin', ...
    ]):
        mod = importlib.import_module(mod_name)
        mixin_classes.append(getattr(mod, cls_name))
    mixin_classes.append(RepositoryBase)
    return type('Repository', tuple(mixin_classes), {})

_repository_class = None

def _get_class():
    global _repository_class
    if _repository_class is None:
        _repository_class = _get_repository_class()
    return _repository_class
```

### 9.3 单例管理

**【强制】** 通过 `get_repository()` 获取全局单例，禁止直接实例化。

```python
_default_repo: RepositoryBase | None = None

def get_repository() -> RepositoryBase:
    """获取默认 Repository 单例"""
    global _default_repo
    if _default_repo is None:
        _default_repo = _get_class()()
    return _default_repo
```

### 9.4 编写新 Mixin

```python
# src/xianyu_hunter/infra/repo_xxx.py
from __future__ import annotations
from sqlalchemy import select, insert, update, delete
from xianyu_hunter.infra.db_models import XxxRow

class XxxMixin:
    """Xxx 表的数据访问方法"""
    
    def list_xxx_by_task(self, task_id: str) -> list[dict]:
        """按任务查询"""
        with self.engine.connect() as conn:
            stmt = select(XxxRow).where(XxxRow.task_id == task_id)
            return [self._row_to_dict(r) for r in conn.execute(stmt).all()]
    
    def upsert_xxx(self, data: dict) -> None:
        """插入或更新（业务层实现 upsert 语义）"""
        with self.engine.begin() as conn:
            existing = conn.execute(
                select(XxxRow).where(XxxRow.id == data["id"])
            ).first()
            if existing:
                conn.execute(
                    update(XxxRow).where(XxxRow.id == data["id"]).values(**data)
                )
            else:
                conn.execute(insert(XxxRow).values(**data))
```

### 9.5 注册新 Mixin

**【强制】** 新建 Mixin 后必须在 `_mixin_modules` 列表中注册。

```python
# repository_base.py
_mixin_modules = [
    'xianyu_hunter.infra.repo_tasks',
    'xianyu_hunter.infra.repo_items',
    # ... 新增：
    'xianyu_hunter.infra.repo_xxx',
]

# 同步更新 zip 的 cls_name 列表
```

---

## 十、查询规范与性能优化

### 10.1 事务管理

**【强制】** 写操作必须使用 `engine.begin()`（自动提交 + 回滚），读操作使用 `engine.connect()`。

```python
# 写操作
with self.engine.begin() as conn:
    conn.execute(insert(TaskRow).values(**data))

# 读操作
with self.engine.connect() as conn:
    stmt = select(TaskRow).where(TaskRow.id == task_id)
    return conn.execute(stmt).first()
```

### 10.2 CASE WHEN 聚合优化

**【强制】** Dashboard 计数查询必须用 `CASE WHEN` 合并多次 COUNT 为单次查询。

```python
def db_count_by_predicate(self, row_cls, start, end, *, extra_where=None):
    """时间窗内二元计数：满足条件数 / 总数，单次查询完成"""
    col = getattr(row_cls, "created_at")
    with self.engine.connect() as conn:
        if extra_where:
            matched_expr = case((and_(*extra_where), 1), else_=0)
            stmt = (
                select(
                    func.sum(matched_expr).label("matched"),
                    func.count().label("total"),
                )
                .select_from(row_cls)
                .where(col >= start)
                .where(col <= end)
            )
            row = conn.execute(stmt).one()
            return (int(row.matched or 0), int(row.total or 0))
        # ...
```

### 10.3 分页查询规范

```python
def list_items(self, task_id: str, page: int = 1, page_size: int = 20):
    """分页查询：必须使用 LIMIT + OFFSET，并返回总数"""
    with self.engine.connect() as conn:
        # 数据查询
        stmt = (
            select(ItemRow)
            .where(ItemRow.task_id == task_id)
            .order_by(ItemRow.first_seen.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        items = [self._row_to_dict(r) for r in conn.execute(stmt).all()]
        
        # 总数查询
        total = conn.execute(
            select(func.count())
            .select_from(ItemRow)
            .where(ItemRow.task_id == task_id)
        ).scalar() or 0
        
        return {"items": items, "total": total, "page": page, "page_size": page_size}
```

### 10.4 批量插入优化

**【推荐】** 批量插入使用 `insert().values(list_of_dicts)` 单次提交。

```python
with self.engine.begin() as conn:
    conn.execute(insert(ItemRow), [
        {"id": "...", "title": "...", "price": 99.0, ...},
        # ... 批量数据
    ])
```

### 10.5 查询性能埋点标准 🆕

**问题背景**：关键查询方法缺少执行时间监控，性能退化无法及时发现。

**强制规则**：面向用户响应的关键查询方法必须添加耗时埋点：

```python
import time as _time

def list_and_count_task_links(self, task_id: str, ...) -> tuple[list[dict], dict[str, int]]:
    _perf_start = _time.monotonic()
    # ... 查询逻辑 ...
    _elapsed_ms = (_time.monotonic() - _perf_start) * 1000
    if _elapsed_ms > SLOW_QUERY_THRESHOLD_MS:  # 阈值通过配置管理
        logger.warning("list_and_count_task_links 慢查询: task={}, elapsed={:.1f}ms", task_id, _elapsed_ms)
    else:
        logger.debug("list_and_count_task_links: task={}, elapsed={:.1f}ms", task_id, _elapsed_ms)
```

**埋点层级与阈值**（阈值通过 `config/tech-stack.json` 的 `performance` 节管理）：

| 层级 | 阈值 | 日志级别 | 说明 |
|------|------|----------|------|
| Repository 层 | 100ms | WARNING | DB 查询耗时 |
| API 端点层 | 200ms | WARNING | 端到端响应耗时（含 DB + 序列化） |

**适用场景**：所有面向用户响应的查询方法（列表查询、搜索、聚合统计）
**不适用场景**：内部辅助方法、单行主键查询、调试用 `echo=True`

---

## 十一、安全规范

### 11.1 SQL 注入防护

**【强制】** LIKE 查询必须使用 `_escape_like()` 转义通配符。

```python
from xianyu_hunter.infra.repository_base import _escape_like

def search_tasks(self, keyword: str) -> list[dict]:
    """按关键词搜索任务"""
    escaped = _escape_like(keyword)
    with self.engine.connect() as conn:
        stmt = select(TaskRow).where(
            TaskRow.name.like(f"%{escaped}%", escape="/")
        )
        return [self._row_to_dict(r) for r in conn.execute(stmt).all()]
```

### 11.2 参数化查询

**【强制】** 所有用户输入必须通过 SQLAlchemy 参数化查询绑定，禁止字符串拼接 SQL。

```python
# 正确：参数化
stmt = select(TaskRow).where(TaskRow.id == task_id)

# 禁止：字符串拼接
sql = f"SELECT * FROM tasks WHERE id = '{task_id}'"  # 绝对禁止
```

### 11.3 路径遍历防护

**【强制】** 涉及文件路径的字段必须用 `_USER_ID_RE` 校验。

```python
import re
_USER_ID_RE = re.compile(r'^[A-Za-z0-9_-]+$', re.ASCII)

def validate_user_id(user_id: str) -> None:
    if not _USER_ID_RE.match(user_id):
        raise ValueError("非法 user_id")
```

---

## 十二、ChromaDB 向量库

### 12.1 部署模式

- **嵌入式**：ChromaDB 以嵌入式模式运行，数据存储在 `data/chatbot_vector/`
- **单实例**：不支持多进程并发写入，通过 `asyncio.Lock` 串行化

### 12.2 集合设计

```python
# 单一集合：xianyu_kb
collection_name = "xianyu_kb"

# 文档片段元数据
{
    "source_file": "docs/chatbot-概要设计.md",
    "section_path": "## 3. 模块设计 > ### 3.1 Orchestrator",
    "line_start": 45,
    "line_end": 80,
    "doc_type": "design",  # requirement / design / manual / code
}
```

### 12.3 与 SQLite 的分工

| 数据类型 | 存储位置 | 原因 |
|---------|---------|------|
| 文档片段向量 | ChromaDB | 向量相似度检索 |
| 知识库版本记录 | SQLite (`chatbot_kb_versions`) | 关系查询 + 事务 |
| 会话/消息 | SQLite | 频繁更新 + 关系查询 |

### 12.4 两阶段提交

**【强制】** 知识库构建必须遵循两阶段提交，失败可回滚。

```
阶段1：导出当前 ChromaDB 快照到临时目录
阶段2：批量向量化 → 清空 ChromaDB → 写入新片段 → 更新版本状态
任一阶段失败：调用 _rollback_build 恢复快照
```

### 12.5 失败率阈值

```python
_PARTIAL_FAIL_RATE = 0.10  # >10% 状态记为 partial
_FAILED_FAIL_RATE = 0.50   # >50% 状态记为 failed 并回滚
```

---

## 十三、常见问题与最佳实践

### Q1: 为什么用 NullPool 而不是 QueuePool？

**A**: SQLite 单文件锁粒度粗，连接长期持有易触发 `SQLITE_BUSY`。NullPool 每次借/还连接，连接间不共享状态，配合 WAL 模式读写不互斥，整体性能更优。

### Q2: 如何调试 SQL 查询？

**A**: 启用 SQLAlchemy echo：
```python
engine = create_engine("sqlite:///...", echo=True)
```
或使用 `loguru` 配置 SQL 日志级别为 DEBUG。

### Q3: JSON 字段查询如何过滤？

**A**: SQLite 的 JSON 函数性能有限，**高频过滤字段必须独立建列**。JSON 字段仅用于存储不常查询的稀疏数据。如需查询，使用 `json_extract`：
```python
stmt = select(TaskRow).where(
    text("json_extract(search_config, '$.page_size') = 30")
)
```

### Q4: 如何添加新表？

**A**: 
1. 在 `db_models.py` 中定义 ORM 类（继承 `Base`）
2. 在 `repository_base.py` 的 `_run_migrations` 中添加幂等迁移（如需历史数据兼容）
3. 创建 `repo_xxx.py` 实现 Mixin
4. 在 `_mixin_modules` 列表中注册

### Q5: SQLite 数据库文件过大如何处理？

**A**: 
1. 定期执行 `VACUUM` 压缩空间
2. 清理历史 `events`、`error_logs` 数据（按 `created_at` 滚动删除）
3. ChromaDB 快照目录 `data/chatbot_snapshots/` 保留最新 `snapshot_max_keep` 个

### Q6: 如何处理数据库锁竞争？

**A**: 
1. 确保 `busy_timeout=10000` 已生效
2. 写事务尽量短（避免在事务中调用外部 API）
3. 批量操作拆分为小事务
4. 使用 `engine.begin()` 而非手动 `BEGIN/COMMIT`

### Q7: 任务级配置覆盖如何实现？

**A**: 使用 JSON 字段（`search_config`/`price_config`/`antidetect_config`/`eval_config`），运行时深度合并全局配置与任务级覆盖：
```python
import mergedeep
final_config = mergedeep.merge({}, global_config, task_config or {})
```

### 最佳实践总结

1. **统一 UTC**：所有时间字段使用 `_utcnow()`，避免时区混乱
2. **JSON 谨慎用**：仅用于稀疏字段，高频查询字段独立建列
3. **索引按需建**：覆盖核心查询路径，避免冗余索引
4. **迁移必幂等**：通过 `PRAGMA table_info` 检查后再执行 DDL
5. **Mixin 组合**：按业务域拆分 Mixin，避免单一巨型 Repository
6. **CASE WHEN 优化**：Dashboard 计数查询合并为单次 SQL
7. **参数化查询**：杜绝 SQL 拼接，LIKE 使用 `_escape_like()`
8. **两阶段提交**：知识库构建必须可回滚
