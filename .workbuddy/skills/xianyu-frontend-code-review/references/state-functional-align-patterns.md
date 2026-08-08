# 状态显示与功能可用性一致性检查示例（v4.16）

> **版本**：v1.0
> **日期**：2026-07-04
> **来源**：从"Cookie 层状态管理与功能可用性矛盾"问题复盘
> **对应检查点**：`F-REVIEW-STATE-FUNCTIONAL-ALIGN`（前端）+ `B-REVIEW-CACHE-INVALIDATION` / `B-REVIEW-STATE-DETECTION-BOOTSTRAP`（后端）
> **适用范围**：`frontend/src/`（TypeScript/React）+ `src/xianyu_hunter/`（Python）
> **配套技能**：`xianyu-hunter-dev`（增量开发）、`xianyu-frontend-code-review` v4.16.0、`xianyu-backend-code-review` v4.15.0

---

## 一、问题原型

**用户报告**：

> 当前系统中，实时查询、官方采集等功能均能正常运行，这表明基础 cookie 机制是有效的。然而，反爬登录管理页面持续显示 `identity` / `session` / `tracking` 状态为失效（红 X 标签）。

**矛盾本质**：

| 维度 | 实际值 | UI 显示值 |
|------|--------|----------|
| 功能可用性 | ✅ 实时查询、官方采集均正常 | ❌ 持续显示失效 |
| 状态判定 | ❌ 仅依据 `valid: boolean` 字段 | ❌ 误判"未检测"为"已失效" |

**根因三层**：

1. **后端层**：`CookieStore` 用 30 秒 TTL 兜底缓存子进程状态，浏览器子进程登录后只更新子进程自己的内存缓存，主进程读时仍取到 TTL 内的旧"失效"状态
2. **后端层**：`collector.last_session_invalid=False` 被解读为"会话有效"，强制恢复所有 Cookie 层（包括实际已失效的 IDENTITY）
3. **前端层**：`LayerStatusBadge` 仅依据 `valid: boolean` 显示（无"未检测"区分），导致用户看到"功能可用但状态持续失效"长达 30 秒

---

## 二、检查清单（自动化扫描）

### 2.1 前端违规模式（`F-REVIEW-STATE-FUNCTIONAL-ALIGN`）

#### 违规模式 A：仅依据布尔字段判定状态显示

```typescript
// ❌ 违规：仅依据 valid 布尔字段
function LayerStatusBadge({ valid }: { valid: boolean }) {
  return <Tag color={valid ? 'success' : 'error'}>{valid ? '有效' : '失效'}</Tag>
}

// ❌ 违规：仅依据 isHealthy 布尔字段
function HealthIndicator({ isHealthy }: { isHealthy: boolean }) {
  return <Badge status={isHealthy ? 'success' : 'error'} text={isHealthy ? '健康' : '异常'} />
}
```

**问题**：
- 刚启动时 `valid=false` / `isHealthy=false` 被解读为"失效/异常"，但实际语义是"未检测"
- 后端初始值 `False` ≠ "已检测为失效"

#### 违规模式 B：缺少"已发生过检测"标记

```typescript
// ❌ 违规：types.ts 缺时间戳/计数器标记
interface LayerState {
  valid: boolean
  lastError?: string
}

// ❌ 违规：组件 props 缺 useCount/lastCheckedAt
function CollectorStatus({ isRunning }: { isRunning: boolean }) {
  return <Tag color={isRunning ? 'success' : 'default'}>{isRunning ? '运行中' : '未运行'}</Tag>
}
```

**问题**：
- 仅布尔字段无法区分"已检测且有效"与"已检测且失效"
- 跨进程/跨模块同步时，无首次成功时间戳无法判断状态新鲜度

#### 违规模式 C：跨进程状态同步依赖 TTL 兜底

```typescript
// ❌ 违规：依赖 30 秒 setInterval TTL 兜底
useEffect(() => {
  const interval = setInterval(() => {
    refetchLayers()  // 每 30 秒拉一次，子进程状态变更 30 秒后才显示
  }, 30 * 1000)
  return () => clearInterval(interval)
}, [])

// ❌ 违规：依赖 time.time() 缓存
const isValid = Date.now() - lastCheckTime < 30_000  // 30 秒内即使状态变了也不更新
```

**问题**：
- 子进程状态变更后 30 秒内前端仍显示旧状态
- 用户体感"明明能跑却一直报错"

### 2.2 后端违规模式（`B-REVIEW-CACHE-INVALIDATION`）

#### 违规模式 A：类含 `_cache` 字段但无 `invalidate_cache()` 方法

```python
# ❌ 违规：含 _cache 字段但未定义 invalidate_cache
class CookieStore:
    def __init__(self):
        self._cache: dict = {}
        self._cache_time: float = 0

    def get_layer_state(self, layer: str) -> dict:
        if time.time() - self._cache_time < 30:  # TTL 兜底
            return self._cache.get(layer)
        # ... 加载逻辑
        return self._cache[layer]

    def write_json(self, data: dict) -> None:
        # ❌ 写入主数据源后未调用 invalidate_cache
        with open(self.path, 'w') as f:
            json.dump(data, f)
```

#### 违规模式 B：写入主数据源后未调用 invalidate_cache

```python
# ❌ 违规：update_state 未调用 invalidate_cache
def update_state(self, new_state: dict) -> None:
    with open(self.path, 'w') as f:
        json.dump(new_state, f)
    # ❌ 缺少 self.invalidate_cache()
```

### 2.3 后端违规模式（`B-REVIEW-STATE-DETECTION-BOOTSTRAP`）

#### 违规模式 A：强制恢复仅依赖布尔字段

```python
# ❌ 违规：仅依据 collector.last_session_invalid 强制恢复所有层
if not collector.last_session_invalid:  # 初始 False 被解读为"会话有效"
    for layer in ['identity', 'session', 'tracking']:
        restore_layer(layer)

# ❌ 违规：未配合"已检测"标记
if not api_health.is_healthy:  # 初始 False 被解读为"不健康"
    trigger_recovery()
```

#### 违规模式 B：信号恢复范围超出其能证明有效的层

```python
# ❌ 违规：m5tk_signal 错误地恢复了 IDENTITY 层
if json_has_valid_m5tk:
    for layer in ['identity', 'session', 'tracking']:  # m5tk 只能证明 session 有效
        restore_layer(layer)
```

### 2.4 后端违规模式（`B-REVIEW-MIGRATION-TRANSACTION`）

#### 违规模式 A：`_migrate_*` 函数含多个 `conn.commit()`

```python
# ❌ 违规：用 3 个独立 commit 拆分布骤
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

**问题**：
- 步骤 2 或 3 失败时旧表已 RENAME 但新表未创建完成
- tasks 表变空且 tasks_old 残留
- 下次启动时 RENAME 因目标已存在永久阻塞

#### 违规模式 B：SQLite 不支持的 ALTER COLUMN

```python
# ❌ 违规：SQLite 不支持 ALTER TABLE ... MODIFY COLUMN
conn.execute(f"ALTER TABLE {table} MODIFY COLUMN {col} VARCHAR(255) NULL")  # SQLite 不支持
conn.execute(f"ALTER TABLE {table} ALTER COLUMN {col} DROP NOT NULL")  # SQLite 不支持
```

---

## 三、修复模式（参考实现）

### 3.1 前端：四态状态 + 已检测标记

```typescript
// ✅ 修复：types.ts 显式区分四态
export type LayerStatus = 'unknown' | 'valid' | 'invalid' | 'stale'

export interface LayerState {
  status: LayerStatus
  lastCheckedAt: number    // 0 = 未检测
  useCount: number         // 0 = 未检测
  lastError?: string
}

// ✅ 修复：UI 渲染区分四态
function LayerStatusBadge({ state }: { state: LayerState }) {
  // 必须先判断"未检测"（lastCheckedAt === 0 && useCount === 0）
  if (state.lastCheckedAt === 0 && state.useCount === 0) {
    return <Tag color="default">未检测</Tag>
  }
  if (state.status === 'valid') {
    return <Tag color="success">有效</Tag>
  }
  if (state.status === 'invalid') {
    return <Tag color="error">失效</Tag>
  }
  if (state.status === 'stale') {
    return <Tag color="warning">检测超时</Tag>
  }
  return <Tag color="default">未知</Tag>
}

// ✅ 修复：SSE 推送替代 TTL 兜底
useEffect(() => {
  const eventSource = new EventSource('/api/events/stream')
  eventSource.addEventListener('cookie_layer_update', (e) => {
    const newState = JSON.parse(e.data) as LayerState
    setLayerState(newState)  // 实时同步，无需 TTL
  })
  return () => eventSource.close()
}, [])
```

### 3.2 后端：缓存失效传播

```python
# ✅ 修复：类定义 invalidate_cache 方法
class CookieStore:
    def __init__(self):
        self._cache: dict = {}
        self._cache_time: float = 0

    def invalidate_cache(self) -> None:
        """显式清除缓存（持久化层变更后必须调用）"""
        self._cache = {}
        self._cache_time = 0

    def write_json(self, data: dict) -> None:
        with open(self.path, 'w') as f:
            json.dump(data, f)
        # ✅ 写入主数据源后显式调用 invalidate_cache
        try:
            self.invalidate_cache()
        except Exception as e:
            logger.warning("CookieStore.invalidate_cache failed: {}", e)

    def get_layer_state(self, layer: str) -> dict:
        # ✅ 读取时检查是否需要刷新（仅在主动失效后）
        if not self._cache:
            self._load_from_disk()
        return self._cache.get(layer)
```

### 3.3 后端：状态判定配合已检测标记

```python
# ✅ 修复：强制恢复需白名单 + 已检测标记
def force_restore_layers(collector_signals: dict, json_state: dict) -> None:
    """强制恢复 Cookie 层（仅在能证明有效的信号下）"""
    signals_to_layers = {
        # 信号 1：collector 已检测（_last_m5tk_refresh > 0）→ 恢复全层
        'collector': (collector_signals.get('last_m5tk_refresh', 0) > 0, ['identity', 'session', 'tracking']),
        # 信号 2：m5tk 有效（json_has_valid_m5tk）→ 仅恢复 SESSION 层
        'm5tk': (json_state.get('has_valid_m5tk', False), ['session']),
    }

    restored = set()
    for signal_name, (has_proof, layers) in signals_to_layers.items():
        if has_proof:
            for layer in layers:
                restored.add(layer)
                restore_layer(layer)
        else:
            # 防御性 else：未识别的信号组合不默认恢复
            logger.warning("force_restore_layers: signal={} has no proof, skip", signal_name)

    if not restored:
        logger.warning("force_restore_layers: no valid signals, skip all layers")
```

### 3.4 后端：SQLite DDL 单事务 + 残留清理

```python
# ✅ 修复：engine.begin() 单事务 + 残留清理 + 异常恢复
def _migrate_make_column_nullable(engine, orm_table, table: str) -> None:
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
    # 异常路径：失败时 engine.begin() 自动回滚
```

---

## 四、检测模式（自动扫描正则）

### 4.1 前端扫描模式（`config.yaml` 的 `state_functional_align.detect_patterns`）

```yaml
detect_patterns:
  # UI 状态显示组件仅依据布尔字段
  - pattern: "<(?:StatusTag|LayerStatusBadge|HealthIndicator)\\s+[^>]*\\bvalid\\s*=\\s*\\{"
    message: "UI 状态显示组件仅依据 valid 布尔字段，应改用 status: LayerStatus 四态 + lastCheckedAt/useCount 标记"
    severity: HIGH
    scope: "frontend/src/**/*.tsx"

  # 缺少"已检测"标记的类型
  - pattern: "valid\\s*:\\s*boolean"
    message: "API types.ts 中 valid:boolean 缺少 lastCheckedAt/useCount 标记，应改为 status: LayerStatus 四态"
    severity: MEDIUM
    scope: "frontend/src/api/types.ts"

  # 跨进程状态同步依赖 setInterval TTL 兜底
  - pattern: "setInterval\\([^,]+,\\s*30\\s*\\*\\s*1000\\)"
    message: "跨进程状态同步依赖 30 秒 setInterval TTL 兜底，应改用 SSE 推送"
    severity: MEDIUM
    scope: "frontend/src/**/*.tsx"
```

### 4.2 后端扫描模式（`config.yaml` 的 `cache_invalidation.detect_patterns`）

```yaml
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

### 4.3 后端扫描模式（`config.yaml` 的 `state_detection_bootstrap.detect_patterns`）

```yaml
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

### 4.4 后端扫描模式（`config.yaml` 的 `migration_transaction.detect_patterns`）

```yaml
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

---

## 五、测试用例

### 5.1 前端测试（vitest）

```typescript
// tests/frontend/LayerStatusBadge.test.tsx
import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { LayerStatusBadge } from '@/components/LayerStatusBadge'

describe('LayerStatusBadge', () => {
  it('应显示"未检测"当 lastCheckedAt === 0 && useCount === 0', () => {
    const { container } = render(
      <LayerStatusBadge state={{ status: 'unknown', lastCheckedAt: 0, useCount: 0 }} />
    )
    expect(container.textContent).toContain('未检测')
    // ✅ 必须用 Tag color="default"，不能是 error
  })

  it('应显示"有效"当 status === "valid" && useCount > 0', () => {
    const { container } = render(
      <LayerStatusBadge state={{ status: 'valid', lastCheckedAt: Date.now(), useCount: 5 }} />
    )
    expect(container.textContent).toContain('有效')
  })

  it('应显示"失效"当 status === "invalid" && useCount > 0', () => {
    const { container } = render(
      <LayerStatusBadge state={{ status: 'invalid', lastCheckedAt: Date.now(), useCount: 3 }} />
    )
    expect(container.textContent).toContain('失效')
  })

  it('应显示"检测超时"当 lastCheckedAt 超过 stale_threshold_seconds', () => {
    const { container } = render(
      <LayerStatusBadge
        state={{ status: 'stale', lastCheckedAt: Date.now() - 7200_000, useCount: 5 }}
      />
    )
    expect(container.textContent).toContain('检测超时')
  })
})
```

### 5.2 后端测试（pytest）

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


def test_force_restore_requires_check_marker():
    """强制恢复必须配合'已检测'标记，禁止仅依赖布尔字段"""
    collector = CollectorState()
    collector.last_session_invalid = False  # 初始 False = 未检测
    collector._last_m5tk_refresh = 0  # 0 = 未发生过检测

    # ✅ 未检测时不应触发强制恢复
    restored_layers = force_restore_layers(collector, json_state={})
    assert restored_layers == set()  # 未恢复任何层

    # ✅ 已检测后才触发恢复
    collector._last_m5tk_refresh = time.time()
    restored_layers = force_restore_layers(collector, json_state={})
    assert 'identity' in restored_layers
    assert 'session' in restored_layers
    assert 'tracking' in restored_layers


def test_m5tk_signal_should_only_restore_session_layer():
    """m5tk_signal 只能恢复 session 层，不应恢复 identity 层"""
    json_state = {"has_valid_m5tk": True}

    restored_layers = force_restore_layers(collector=None, json_state=json_state)

    # ✅ m5tk 信号只恢复 session 层
    assert restored_layers == {'session'}
    assert 'identity' not in restored_layers
```

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
```

---

## 六、相关文件

| 文件 | 职责 |
|------|------|
| `src/xianyu_hunter/web/services/cookie_store.py` | Cookie 存储（含 `_cache` / `invalidate_cache()`） |
| `src/xianyu_hunter/modules/cookie_rotator.py` | Cookie 层管理（含 `LAYER_DEFINITIONS` / `force_restore_layers`） |
| `src/xianyu_hunter/web/routes/api_anticrawl.py` | Cookie 层 API（含 `/cookies/layers` 第三步） |
| `src/xianyu_hunter/infra/db_models.py` | 数据库模型（含 `_migrate_make_column_nullable`） |
| `frontend/src/api/types.ts` | 前端类型定义（含 `LayerStatus` / `LayerState`） |
| `frontend/src/components/CookieLayerStatus/` | Cookie 层状态显示组件 |
| `frontend/src/utils/sseEventManager.ts` | SSE 事件管理器（替代 TTL 兜底） |
| `tests/test_cookie_layer_sync_fix.py` | Cookie 层同步修复测试（41 项） |
| `tests/frontend/LayerStatusBadge.test.tsx` | 前端状态显示组件测试 |
| `tests/backend/test_migration_transaction.py` | 后端迁移事务测试 |
| `.trae/skills/xianyu-hunter-dev/config/tech-stack.json` | 硬约束配置（`cacheInvalidation` / `stateDetectionBootstrap` / `migrationTransaction` / `stateFunctionalAlign` 节点） |
| `.trae/skills/xianyu-backend-code-review/config.example.yaml` | 后端审查配置（`cache_invalidation` / `state_detection_bootstrap` / `migration_transaction` / `debug_code_cleanup` 节点） |
| `.trae/skills/xianyu-frontend-code-review/config.example.yaml` | 前端审查配置（`state_functional_align` / `debug_code_cleanup` 节点） |

---

## 七、版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-07-04 | 初版：基于 Cookie 层状态管理复盘，新增 `F-REVIEW-STATE-FUNCTIONAL-ALIGN`（前端）+ `B-REVIEW-CACHE-INVALIDATION` / `B-REVIEW-STATE-DETECTION-BOOTSTRAP` / `B-REVIEW-MIGRATION-TRANSACTION`（后端）4 项检查点的详细检查示例 |
