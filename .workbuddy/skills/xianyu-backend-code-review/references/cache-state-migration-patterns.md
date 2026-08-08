# 缓存失效/状态判定/Schema 演进检查示例（v4.15）

> **版本**：v1.0
> **日期**：2026-07-04
> **来源**：从"Cookie 层状态管理与功能可用性矛盾"问题复盘
> **对应检查点**：`B-REVIEW-CACHE-INVALIDATION` / `B-REVIEW-STATE-DETECTION-BOOTSTRAP` / `B-REVIEW-MIGRATION-TRANSACTION`（后端 3 项）+ `F-REVIEW-STATE-FUNCTIONAL-ALIGN`（前端 1 项）
> **适用范围**：`src/xianyu_hunter/`（Python/FastAPI/SQLAlchemy）
> **配套技能**：`xianyu-hunter-dev` v4.16.0、`xianyu-backend-code-review` v4.15.0、`xianyu-frontend-code-review` v4.16.0

---

## 一、问题原型

**用户报告**：

> 当前系统中，实时查询、官方采集等功能均能正常运行，这表明基础 cookie 机制是有效的。然而，系统持续显示 identity、session、tracking 状态失效。

**根因三层**：

1. **缓存层**：`CookieStore` 用 30 秒 TTL 兜底缓存子进程状态，浏览器子进程登录后只更新子进程自己的内存缓存，主进程读时仍取到 TTL 内的旧"失效"状态
2. **状态判定层**：`collector.last_session_invalid=False` 被解读为"会话有效"，强制恢复所有 Cookie 层（包括实际已失效的 IDENTITY）
3. **Schema 演进层**：旧版 `_migrate_make_column_nullable` 用 3 个独立 commit 拆分布骤 1/2/3/4，步骤 2 或 3 失败时旧表已 RENAME 但新表未创建完成，tasks 表变空且 tasks_old 残留，下次启动时 RENAME 因目标已存在永久阻塞

---

## 二、B-REVIEW-CACHE-INVALIDATION 详细示例

### 2.1 检查目标

任何持久化层（JSON/SQLite/外部配置）变更后，必须**显式调用**对应缓存对象的 `invalidate_cache()` 或等价方法；TTL 兜底不替代主动失效；跨进程变更必须主动通知主进程失效缓存。

### 2.2 违规代码示例

```python
# ❌ 违规模式 1：类含 _cache 字段但无 invalidate_cache 方法
class CookieStore:
    def __init__(self):
        self._cache: dict = {}
        self._cache_time: float = 0

    def get_layer_state(self, layer: str) -> dict:
        # ❌ 依赖 TTL 兜底（30 秒内即使状态变了也不更新）
        if time.time() - self._cache_time < 30:
            return self._cache.get(layer)
        # ... 加载逻辑
        return self._cache[layer]

# ❌ 违规模式 2：写入主数据源后未调用 invalidate_cache
def update_state(self, new_state: dict) -> None:
    with open(self.path, 'w') as f:
        json.dump(new_state, f)
    # ❌ 缺少 self.invalidate_cache()（主进程读时仍取到旧缓存）
```

### 2.3 修复代码示例

```python
# ✅ 修复：定义 invalidate_cache 方法 + 写入主路径后显式调用
class CookieStore:
    def __init__(self):
        self._cache: dict = {}
        self._cache_time: float = 0

    def invalidate_cache(self) -> None:
        """显式清除缓存（持久化层变更后必须调用）"""
        self._cache = {}
        self._cache_time = 0

    def write_json(self, data: dict) -> None:
        """写入主数据源（唯一入口）"""
        with open(self.path, 'w') as f:
            json.dump(data, f)
        # ✅ 写入主数据源后显式调用 invalidate_cache
        try:
            self.invalidate_cache()
        except Exception as e:
            # ✅ 同步钩子失败仅 logger.warning，不抛异常阻塞主流程
            logger.warning("CookieStore.invalidate_cache failed: {}", e)

    def update_state(self, new_state: dict) -> None:
        """更新状态（业务方法）"""
        with open(self.path, 'w') as f:
            json.dump(new_state, f)
        # ✅ update_state 后显式调用 invalidate_cache
        self.invalidate_cache()

    def get_layer_state(self, layer: str) -> dict:
        # ✅ 读取时检查是否需要刷新（仅在主动失效后）
        if not self._cache:
            self._load_from_disk()
        return self._cache.get(layer)
```

### 2.4 跨进程通知模式

```python
# ✅ 修复：子进程写后通过 SSE 通知主进程失效缓存
def update_state(self, new_state: dict) -> None:
    with open(self.path, 'w') as f:
        json.dump(new_state, f)
    # ✅ 子进程主动通知主进程
    try:
        sse_publish('cookie_state_changed', new_state)
    except Exception as e:
        logger.warning("SSE publish failed: {}", e)
    # ✅ 本进程缓存失效
    self.invalidate_cache()


# ✅ 主进程监听 SSE 推送并刷新缓存
@sse_broker.on('cookie_state_changed')
def on_cookie_state_changed(new_state: dict) -> None:
    """主进程收到子进程状态变更通知"""
    cookie_store.invalidate_cache()  # ✅ 显式失效
    # ... 重新加载或更新内存中的状态
```

### 2.5 检测模式（自动扫描）

```yaml
# config.yaml 的 cache_invalidation.detect_patterns
detect_patterns:
  # 类含 _cache 字段但无 invalidate_cache 方法
  - pattern: "def\\s+__init__[^)]*_cache[^)]*\\):(?!.*def\\s+invalidate_cache)"
    message: "类含 _cache 字段但未定义 invalidate_cache() 方法，违反显式失效规范"
    severity: HIGH

  # 写入主数据源后未调用 invalidate_cache
  - pattern: "def\\s+(update_|upsert_|write_)[a-z_]+\\(self[^)]*\\):(?!.*invalidate_cache)"
    message: "写入主数据源方法（update_*/upsert_*/write_*）未在写后调用 invalidate_cache()"
    severity: HIGH

  # 依赖 TTL 兜底
  - pattern: "time\\.time\\(\\)\\s*-\\s*self\\._cache_time\\s*<\\s*\\d+"
    message: "依赖 TTL 兜底（time.time() - self._cache_time < N）违反显式失效规范"
    severity: MEDIUM
```

### 2.6 适用与不适用场景

**适用**：
- JSON 持久化层（CookieStore / ConfigStore / SessionStore）
- 跨进程 Cookie/状态同步（子进程写→主进程读）
- 内存缓存与文件副本同步
- 登录态多进程写入

**不适用**：
- 纯函数、纯计算缓存（LRU math 缓存）
- 无外部数据源同步的内部状态

---

## 三、B-REVIEW-STATE-DETECTION-BOOTSTRAP 详细示例

### 3.1 检查目标

任何"功能信号"字段（`last_session_invalid`/`is_healthy`/`is_connected` 等）不能仅用布尔初始值（默认 `False`）代表"未检测"——`False` 与"已检测无失效"语义混淆，会导致刚启动时误判为"功能正常"。必须配合"已发生过检测"标记（时间戳 `_last_check_at > 0`、计数器 `use_count > 0`、首次成功标记 `_has_run`）。

### 3.2 违规代码示例

```python
# ❌ 违规模式 1：强制恢复仅依赖布尔字段
def force_restore_layers(collector_signals: dict, json_state: dict) -> None:
    # ❌ 仅依据 collector.last_session_invalid 强制恢复所有层
    if not collector.last_session_invalid:  # 初始 False 被解读为"会话有效"
        for layer in ['identity', 'session', 'tracking']:
            restore_layer(layer)  # ❌ 即使实际 IDENTITY 失效也会被恢复

# ❌ 违规模式 2：未配合"已检测"标记
if not api_health.is_healthy:  # 初始 False 被解读为"不健康"
    trigger_recovery()  # ❌ 启动时立即触发恢复（误判）
```

### 3.3 修复代码示例

```python
# ✅ 修复：强制恢复需白名单 + 已检测标记
def force_restore_layers(collector_signals: dict, json_state: dict) -> set[str]:
    """强制恢复 Cookie 层（仅在能证明有效的信号下）
    
    Returns:
        已恢复的层集合（用于日志/调试）
    """
    signals_to_layers = {
        # 信号 1：collector 已检测（_last_m5tk_refresh > 0）→ 恢复全层
        'collector': (
            collector_signals.get('last_m5tk_refresh', 0) > 0,
            ['identity', 'session', 'tracking'],
        ),
        # 信号 2：m5tk 有效（json_has_valid_m5tk）→ 仅恢复 SESSION 层
        'm5tk': (
            json_state.get('has_valid_m5tk', False),
            ['session'],
        ),
    }

    restored = set()
    for signal_name, (has_proof, layers) in signals_to_layers.items():
        if has_proof:
            for layer in layers:
                restored.add(layer)
                restore_layer(layer)
        else:
            # ✅ 防御性 else：未识别的信号组合不默认恢复所有层
            logger.warning("force_restore_layers: signal={} has no proof, skip", signal_name)

    if not restored:
        # ✅ 未识别任何有效信号，不触发任何恢复
        logger.warning("force_restore_layers: no valid signals, skip all layers")
    
    return restored
```

### 3.4 信号与层范围映射配置

```python
# config.yaml 的 state_detection_bootstrap.signal_layer_mapping
signal_layer_mapping:
  collector_signal: ["identity", "session", "tracking"]   # collector 已检测→恢复全层
  m5tk_signal: ["session"]                                # m5tk 有效→仅恢复 SESSION 层
```

### 3.5 检测模式（自动扫描）

```yaml
# config.yaml 的 state_detection_bootstrap.detect_patterns
detect_patterns:
  # 强制恢复仅依赖布尔字段未配合"已检测"标记
  - pattern: "if\\s+not\\s+\\w+\\.(last_session_invalid|is_healthy|is_connected)\\s*:"
    message: "强制恢复/兜底逻辑仅依赖布尔字段未配合'已发生过检测'标记（_last_m5tk_refresh > 0）"
    severity: HIGH

  # 信号恢复范围超出其能证明有效的层
  - pattern: "m5tk.*identity|json_has_valid_m5tk.*identity"
    message: "m5tk_signal 只能恢复 session 层，不应恢复 identity 层（信号范围溢出）"
    severity: HIGH
```

### 3.6 适用与不适用场景

**适用**：
- 跨进程/跨模块状态判定
- Cookie 层状态自愈
- 容器健康检查、服务可用性兜底

**不适用**：
- 纯客户端 UI 状态
- 单次函数返回值
- 无初始歧义的开关字段

---

## 四、B-REVIEW-MIGRATION-TRANSACTION 详细示例

### 4.1 检查目标

SQLite 不支持 `ALTER COLUMN`，任何修改列约束的操作（NOT NULL→nullable、类型变更）必须通过 `_migrate_make_column_nullable` 模式（事务 + 残留清理 + 数据复制 + 异常恢复），禁止分散 commit 或裸 ALTER。

### 4.2 违规代码示例

```python
# ❌ 违规模式 1：_migrate_* 函数含多个 conn.commit()
def _migrate_make_column_nullable(engine, table: str):
    conn = engine.connect()
    conn.execute(f"ALTER TABLE {table} RENAME TO {table}_old")
    conn.commit()  # ❌ 步骤 1 独立 commit

    orm_table.create(engine, checkfirst=True)  # ❌ 未传 conn
    conn.commit()  # ❌ 步骤 2 独立 commit

    conn.execute(f"INSERT INTO {table} SELECT * FROM {table}_old")
    conn.commit()  # ❌ 步骤 3 独立 commit

    conn.execute(f"DROP TABLE {table}_old")
    conn.commit()  # ❌ 步骤 4 独立 commit
    conn.close()
```

**问题分析**：
- 步骤 2 或 3 失败时旧表已 RENAME 但新表未创建完成
- tasks 表变空且 tasks_old 残留
- 下次启动时 RENAME 因目标已存在永久阻塞

```python
# ❌ 违规模式 2：SQLite 不支持的 ALTER COLUMN
conn.execute(f"ALTER TABLE {table} MODIFY COLUMN {col} VARCHAR(255) NULL")  # SQLite 不支持
conn.execute(f"ALTER TABLE {table} ALTER COLUMN {col} DROP NOT NULL")  # SQLite 不支持
```

```python
# ❌ 违规模式 3：orm_table.create() 未传 conn
orm_table.create(engine, checkfirst=True)  # ❌ DDL 未纳入事务
```

### 4.3 修复代码示例

```python
# ✅ 修复：engine.begin() 单事务 + 残留清理 + 数据复制 + 异常恢复
def _migrate_make_column_nullable(engine, orm_table, table: str) -> None:
    """SQLite 修改列约束必须用表重建 + 事务安全
    
    关键约束：
        1. 事务包裹：整个表重建用 engine.begin() 包裹
        2. 残留清理：迁移前 DROP TABLE IF EXISTS {table}_old
        3. 连接传参：orm_table.create(conn, checkfirst=True) 传入连接
        4. 数据复制：用列名交集复制数据
        5. 异常恢复：失败后从 {table}_old RENAME 恢复
    """
    with engine.begin() as conn:
        # 1. 残留清理（避免上次失败导致 RENAME 阻塞）
        conn.execute(sa_text(f"DROP TABLE IF EXISTS {table}_old"))
        # 2. RENAME 旧表
        conn.execute(sa_text(f"ALTER TABLE {table} RENAME TO {table}_old"))
        # 3. 创建新表（传 conn 而非 engine，确保 DDL 纳入事务）
        orm_table.create(conn, checkfirst=True)
        # 4. 数据复制（用列名交集，防止列差异导致 INSERT 失败）
        old_cols = {c[1] for c in conn.execute(sa_text(f"PRAGMA table_info({table}_old)")).all()}
        common_cols = [c for c in orm_table.columns if c.name in old_cols]
        col_list = ", ".join(f'"{c.name}"' for c in common_cols)
        conn.execute(sa_text(f"INSERT INTO {table} ({col_list}) SELECT {col_list} FROM {table}_old"))
        # 5. 删除旧表
        conn.execute(sa_text(f"DROP TABLE {table}_old"))
    # ✅ 异常路径：失败时 engine.begin() 自动回滚
    # ✅ 残留清理：下次启动时 DROP TABLE IF EXISTS {table}_old 兜底
```

### 4.4 检测模式（自动扫描）

```yaml
# config.yaml 的 migration_transaction.detect_patterns
detect_patterns:
  # _migrate_* 函数含多个 conn.commit()
  - pattern: "def\\s+_migrate_\\w+\\([^)]*\\):[\\s\\S]{0,2000}conn\\.commit\\(\\)[\\s\\S]{0,2000}conn\\.commit\\(\\)"
    message: "_migrate_* 函数含多个 conn.commit()，应拆分为单一 engine.begin() 事务"
    severity: CRITICAL

  # SQLite 不支持的 ALTER COLUMN
  - pattern: "ALTER\\s+TABLE\\s+\\w+\\s+(MODIFY|ALTER)\\s+COLUMN"
    message: "SQLite 不支持 ALTER TABLE ... MODIFY/ALTER COLUMN，必须用表重建（_migrate_make_column_nullable 模式）"
    severity: CRITICAL

  # DDL 操作未传 conn 给 orm_table.create
  - pattern: "orm_table\\.create\\(\\s*\\)"
    message: "orm_table.create() 应传入 conn 而非 engine，确保 DDL 纳入事务"
    severity: HIGH
```

### 4.5 适用与不适用场景

**适用**：
- SQLite 修改列约束（NOT NULL→nullable、类型变更）
- SQLite 表重建、任何不可逆 DDL

**不适用**：
- PostgreSQL/MySQL（有原生 DDL 事务）
- 新增列（直接 ADD COLUMN）
- 纯查询/插入操作

---

## 五、测试用例（pytest）

### 5.1 缓存失效测试

```python
# tests/backend/test_cookie_store_cache_invalidation.py
def test_write_json_should_invalidate_cache(tmp_path):
    """写入主数据源后必须显式调用 invalidate_cache()"""
    store = CookieStore(path=tmp_path / "cookies.json")
    store._cache = {"identity": {"valid": True}}
    store._cache_time = time.time()

    store.write_json({"identity": {"valid": False}})

    # ✅ 写入后缓存必须被清除
    assert store._cache == {}
    assert store._cache_time == 0


def test_get_layer_state_should_reload_after_invalidate(tmp_path):
    """缓存失效后读取必须重新加载磁盘数据"""
    store = CookieStore(path=tmp_path / "cookies.json")
    store.write_json({"identity": {"valid": True}})

    # 第一次读，缓存命中
    state1 = store.get_layer_state("identity")
    assert state1 == {"valid": True}

    # 修改磁盘
    store.write_json({"identity": {"valid": False}})

    # ✅ 失效后读，必须拿到新值
    state2 = store.get_layer_state("identity")
    assert state2 == {"valid": False}
```

### 5.2 状态判定测试

```python
# tests/backend/test_force_restore_layers.py
def test_force_restore_requires_check_marker():
    """强制恢复必须配合'已检测'标记，禁止仅依赖布尔字段"""
    collector = CollectorState()
    collector.last_session_invalid = False  # 初始 False = 未检测
    collector._last_m5tk_refresh = 0  # 0 = 未发生过检测

    # ✅ 未检测时不应触发强制恢复
    restored_layers = force_restore_layers(
        collector_signals={'last_m5tk_refresh': collector._last_m5tk_refresh},
        json_state={},
    )
    assert restored_layers == set()  # 未恢复任何层


def test_force_restore_with_collector_signal():
    """collector 已检测时（全层）应恢复所有层"""
    collector = CollectorState()
    collector._last_m5tk_refresh = time.time()  # 已检测

    restored_layers = force_restore_layers(
        collector_signals={'last_m5tk_refresh': collector._last_m5tk_refresh},
        json_state={},
    )
    assert 'identity' in restored_layers
    assert 'session' in restored_layers
    assert 'tracking' in restored_layers


def test_m5tk_signal_should_only_restore_session_layer():
    """m5tk_signal 只能恢复 session 层，不应恢复 identity 层"""
    json_state = {"has_valid_m5tk": True}

    restored_layers = force_restore_layers(
        collector_signals={'last_m5tk_refresh': 0},
        json_state=json_state,
    )

    # ✅ m5tk 信号只恢复 session 层
    assert restored_layers == {'session'}
    assert 'identity' not in restored_layers
```

### 5.3 迁移事务测试

```python
# tests/backend/test_migration_transaction.py
def test_migrate_make_column_nullable_should_use_single_transaction(engine, tasks_table):
    """_migrate_* 必须用 engine.begin() 单事务包裹"""
    # 制造 tasks_old 残留
    engine.execute(sa_text("CREATE TABLE tasks_old (id INTEGER)"))

    _migrate_make_column_nullable(engine, tasks_table, "tasks")

    # ✅ 单事务成功：tasks 表存在，tasks_old 不存在
    assert engine.dialect.has_table(engine.connect(), "tasks")
    assert not engine.dialect.has_table(engine.connect(), "tasks_old")


def test_migrate_failure_should_rollback(engine, tasks_table, monkeypatch):
    """迁移失败时必须回滚，不留残留"""
    # 制造 orm_table.create 失败
    def mock_create(*args, **kwargs):
        raise RuntimeError("simulated failure")
    monkeypatch.setattr(tasks_table, "create", mock_create)

    with pytest.raises(RuntimeError):
        _migrate_make_column_nullable(engine, tasks_table, "tasks")

    # ✅ 失败时 tasks 表不应被创建（事务回滚），tasks_old 也不应存在
    assert not engine.dialect.has_table(engine.connect(), "tasks")
    assert not engine.dialect.has_table(engine.connect(), "tasks_old")


def test_migrate_should_cleanup_residual_old_table(engine, tasks_table):
    """迁移前必须清理残留的 {table}_old 表"""
    # 制造残留
    engine.execute(sa_text("CREATE TABLE tasks_old (id INTEGER, name TEXT)"))

    _migrate_make_column_nullable(engine, tasks_table, "tasks")

    # ✅ 残留被清理
    assert not engine.dialect.has_table(engine.connect(), "tasks_old")
```

---

## 六、相关文件

| 文件 | 职责 |
|------|------|
| `src/xianyu_hunter/web/services/cookie_store.py` | Cookie 存储（含 `_cache` / `invalidate_cache()`） |
| `src/xianyu_hunter/modules/cookie_rotator.py` | Cookie 层管理（含 `LAYER_DEFINITIONS` / `force_restore_layers`） |
| `src/xianyu_hunter/web/routes/api_anticrawl.py` | Cookie 层 API（含 `/cookies/layers` 第三步） |
| `src/xianyu_hunter/infra/db_models.py` | 数据库模型（含 `_migrate_make_column_nullable`） |
| `src/xianyu_hunter/infra/event_bus.py` | 事件总线（跨进程通知） |
| `tests/test_cookie_layer_sync_fix.py` | Cookie 层同步修复测试（41 项） |
| `tests/backend/test_cookie_store_cache_invalidation.py` | 缓存失效测试 |
| `tests/backend/test_force_restore_layers.py` | 状态判定测试 |
| `tests/backend/test_migration_transaction.py` | 迁移事务测试 |
| `.trae/skills/xianyu-hunter-dev/config/tech-stack.json` | 硬约束配置（`cacheInvalidation` / `stateDetectionBootstrap` / `migrationTransaction` 节点） |
| `.trae/skills/xianyu-backend-code-review/config.example.yaml` | 后端审查配置（`cache_invalidation` / `state_detection_bootstrap` / `migration_transaction` 节点） |

---

## 七、版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-07-04 | 初版：基于 Cookie 层状态管理复盘，新增 3 项 B-REVIEW 检查点的详细检查示例 |
