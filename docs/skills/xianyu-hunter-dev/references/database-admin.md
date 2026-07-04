# 数据库维护模块专项规范

> **来源**：从"数据库维护"二级菜单开发 + 多轮 Bug 修复中提炼
> **适用范围**：`api_db_admin.py`（后端）+ `DatabaseAdmin.tsx`（前端）+ 相关 API 类型
> **核心问题**：在线数据库 CRUD 的安全性、完整性、可追溯性

---

## 一、安全约束

### 1.1 表白名单

仅允许操作业务表，禁止访问系统表（如 `sqlite_master`、`alembic_version`）：

```python
ALLOWED_TABLES = frozenset({
    "tasks", "items", "sellers", "evaluations", "orders",
    "events", "task_links", "task_deps", "notifications", "accounts", "proxies",
})
```

新增业务表时必须同步更新此白名单。

### 1.2 SQL 注入防护

| 防护层 | 实现 | 代码位置 |
|---|---|---|
| 表名 | `_validate_table()` 白名单校验 | `api_db_admin.py` |
| 列名 | `_validate_identifier()` 正则校验 | `api_db_admin.py` |
| 值 | 参数化绑定 `:param` | 所有 SQL 语句 |

**铁律**：用户输入**绝不**拼接到 SQL 标识符位置（表名/列名/ORDER BY），只通过白名单或正则校验。

### 1.3 二次确认机制

危险操作（删除/批量删除/导入）必须传入 `confirm_token`：

```python
CONFIRM_TOKEN = "CONFIRM_DELETE"

# 前端：弹窗要求用户手动输入确认词
# 后端：校验 confirm_token == CONFIRM_TOKEN 才执行
```

**为什么不用更复杂的方案**：确认词写在代码中而非配置文件，因为它是安全策略而非业务参数，改动频率极低。

---

## 二、级联删除策略

### 2.1 关联关系图

```
tasks ──┬── items.task_id        (1:N)
        ├── orders.task_id       (1:N)
        ├── events.task_id       (1:N)
        ├── task_links.task_id   (1:N)
        └── task_deps.task_id / depends_on (1:N)

items ──┬── evaluations.item_id  (1:N)
        ├── orders.item_id       (1:N)
        └── events.item_id       (1:N)

sellers ──┬── items.seller_id    (1:N)
          ├── orders.seller_id   (1:N)
          └── evaluations.seller_id (1:N)
```

### 2.2 策略定义

```python
TABLE_RELATIONS = {
    "tasks": [
        {"table": "items", "fk": "task_id", "action": "cascade"},     # 级联删除
        {"table": "orders", "fk": "task_id", "action": "cascade"},
        {"table": "events", "fk": "task_id", "action": "cascade"},
        {"table": "task_links", "fk": "task_id", "action": "cascade"},
        {"table": "task_deps", "fk": "task_id", "action": "cascade"},
        {"table": "task_deps", "fk": "depends_on", "action": "cascade"},
    ],
    "items": [
        {"table": "evaluations", "fk": "item_id", "action": "cascade"},
        {"table": "orders", "fk": "item_id", "action": "cascade"},
        {"table": "events", "fk": "item_id", "action": "cascade"},
    ],
    "sellers": [
        {"table": "items", "fk": "seller_id", "action": "set_null"},  # 置空外键
        {"table": "orders", "fk": "seller_id", "action": "set_null"},
        {"table": "evaluations", "fk": "seller_id", "action": "set_null"},
    ],
}
```

### 2.3 策略选择原则

| 策略 | 适用场景 | 理由 |
|---|---|---|
| `cascade` | 核心实体被删（tasks/items） | 依赖数据无独立存在价值，避免孤立记录 |
| `set_null` | 辅助实体被删（sellers） | 关联数据仍有独立查看价值，只断开引用 |
| 直接删除 | 叶子表（events/notifications） | 无下游依赖 |

### 2.4 为什么在应用层实现而非 SQLite ON DELETE CASCADE

1. SQLite 建表时未声明 `ON DELETE CASCADE`（SQLAlchemy 默认不生成）
2. 应用层可精确控制策略（cascade vs set_null），并返回影响行数
3. 审计日志可记录级联细节
4. 同一事务保证原子性

### 2.5 级联预览

删除前提供只读预览 API，让用户看到影响范围：

```
POST /api/db-admin/tables/{table}/cascade-preview
Body: { ids: [1, 2, 3] }
Response: {
  table: "tasks",
  relations: [
    { table: "items", fk: "task_id", action: "cascade", count: 15, description: "将删除 items.task_id 中 15 条关联记录" },
    { table: "orders", fk: "task_id", action: "cascade", count: 3, description: "将删除 orders.task_id 中 3 条关联记录" },
  ],
  total_affected: 18
}
```

---

## 三、字段语义标注

### 3.1 标注规范

每个字段的标注包含四个维度：
1. **业务含义**：这个字段是什么（如"任务名称"）
2. **数据类型特征**：值的格式/范围（如"元"、"0-100"、"JSON数组"）
3. **使用场景**：在什么场景下被使用（如"用于计算发布天数"）
4. **约束条件**：NULL 语义、枚举值、FK 关系（如"NULL=不限"、"FK→tasks.id"）

### 3.2 标注格式

```
业务名称（数据类型特征，使用场景，约束说明）
```

示例：
- `任务状态（running=运行中/paused=已暂停/stopped=已停止/completed=已完成）`
- `最低价格（元，价格筛选下限，NULL=不限）`
- `关联任务ID（FK→tasks.id，标识该商品由哪个任务发现）`

### 3.3 前端展示规则

| 位置 | 展示方式 |
|---|---|
| 数据表表头 | 中文简称（`label.split('（')[0]`），hover 显示完整标注 |
| 表结构抽屉 | 独立"中文标注"列，完整显示 |
| 编辑表单 | label 显示中文简称 + 类型标签，hover 显示完整标注 |

---

## 四、SQLite 类型兼容

### 4.1 问题描述

通过 `text()` 原始 SQL 查询时，SQLAlchemy 不走 ORM 类型转换，SQLite 驱动返回 Python 原生类型：
- `DateTime` 列 → 返回 `str`（如 `"2025-01-01 00:00:00"`），不是 `datetime` 对象
- `JSON` 列 → 可能返回 `str`，不是 `dict`

### 4.2 解决模式

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

### 4.3 适用范围

- ✅ 所有通过 `text()` 查询 datetime/json 列的序列化代码
- ❌ ORM 查询（`session.query(Model)` 自动类型转换）
- ❌ 直接返回给 Pydantic 序列化的场景（Pydantic 自带类型适配）

---

## 五、审计日志

### 5.1 记录规则

所有 DML 操作写入 `events` 表：

```python
def _log_audit(container, action, table, *, pk_value=None, detail=None, level="info"):
    container.repo.save_event({
        "type": f"db_admin.{action}",
        "task_id": None,
        "stage": "db_admin",
        "level": level,
        "message": f"db_admin.{action} {table}" + (f" pk={pk_value}" if pk_value else ""),
        "payload": json.dumps({"action": action, "table": table, "pk": pk_value, "detail": detail or {}}, default=str),
    })
```

### 5.2 level 规则

| 操作 | level | 理由 |
|---|---|---|
| create / update | `info` | 常规操作 |
| delete / batch_delete | `warn` | 数据丢失风险 |
| 操作失败 | `err` | 需关注 |

### 5.3 审计日志查询

```sql
SELECT id, type, level, message, payload, created_at
FROM events
WHERE type LIKE 'db_admin.%'
ORDER BY id DESC LIMIT :limit
```

前端在审计日志抽屉中展示，支持按 level 着色（warn=橙色，err=红色）。

---

## 六、检查清单

修改数据库维护相关代码后：

- [ ] 新增表已加入 `ALLOWED_TABLES`
- [ ] SQL 标识符通过白名单/正则校验，值通过参数化绑定
- [ ] 危险操作需要 `confirm_token` 二次确认
- [ ] 有外键引用的表已定义 `TABLE_RELATIONS` 级联策略
- [ ] 级联操作在同一事务中执行
- [ ] 删除前有级联预览 API
- [ ] 所有字段有 `COLUMN_LABELS` 中文标注
- [ ] datetime 列序列化做了 `hasattr` 类型兼容
- [ ] DML 操作写入审计日志
- [ ] 前端删除确认弹窗展示级联影响预览
