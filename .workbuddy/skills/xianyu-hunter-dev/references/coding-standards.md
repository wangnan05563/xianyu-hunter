# XianyuHunter 统一编码规范

> **版本**：v1.3
> **日期**：2026-07-25
> **来源**：从多次 Bug 修复对话 + 项目实践提炼
> **适用范围**：`src/xianyu_hunter/`（Python）+ `frontend/src/`（TypeScript）
> **配套技能**：`xianyu-hunter-dev`（增量开发）、`xianyu-frontend-code-review`、`xianyu-backend-code-review`

---

## 一、通用原则（前后端通用）

| # | 原则 | 落地手段 |
|---|---|---|
| 1 | **编程前先思考** | 不确定时用 `AskUserQuestion` 询问，不要默默选择解释 |
| 2 | **简约至上** | 任何过度设计都一目了然，避免提前抽象 |
| 3 | **精确编辑** | 只修改必要的部分，不要顺便修改旁边代码 |
| 4 | **目标驱动** | 在开始前将模糊指令转化为可验证的目标 |
| 5 | **注释解释 why，不是 what** | `# 颠倒加载顺序：避免 eval.yaml 整体覆盖` 而不是 `# 加载配置` |
| 6 | **验证先于断言** | 任何"完成"声明前必须有测试输出或实测截图佐证 |

---

## 二、Python 后端规范

### 2.1 类型与数据结构

| 规则 | 说明 |
|---|---|
| **使用 Pydantic v2** | 配置 / API 请求 / 响应统一用 `BaseModel` |
| **避免 raw dict** | 业务层禁止传 `dict[str, Any]`，必须用模型 |
| **Optional 用 `X \| None`** | Python 3.10+ 风格，不用 `Optional[X]` |
| **枚举用 `StrEnum`** | 不要用 `Enum`（与 JSON 序列化更友好） |
| **路径用 `pathlib.Path`** | 不用 `os.path` |

### 2.2 异步与并发

| 规则 | 说明 |
|---|---|
| **I/O 必须 async** | `asyncio.sleep` / `await` / `aiohttp` |
| **禁止阻塞调用** | `requests.get` / `time.sleep` / `open(file).read()` 阻塞循环 |
| **并发任务用 `asyncio.gather`** | 不用裸 `for` 串行 await |
| **信号量限流** | 涉及外部 API 时用 `asyncio.Semaphore` 控制 QPS |

### 2.3 YAML / 配置加载（重要）

**铁律：深度合并 + 主配置最后加载**

```python
def _load_all() -> AppConfig:
    base = Path("config")
    data: dict[str, Any] = {}

    # 1) 先加载子配置（默认值基线）
    for name in ("eval.yaml", "notifier.yaml", "browser.yaml"):
        section_data = load_yaml(base / name)
        if section_data:
            _deep_merge_yaml(data, section_data)

    # 2) 主配置最后加载（用户修改覆盖子配置）
    main_data = load_yaml(base / "config.yaml")
    if main_data:
        _deep_merge_yaml(data, main_data)

    return AppConfig.model_validate(data)


def _deep_merge_yaml(target: dict, source: dict) -> None:
    """深度合并：source 的细分字段覆盖 target 同名字段。"""
    for k, v in source.items():
        if isinstance(v, dict) and isinstance(target.get(k), dict):
            _deep_merge_yaml(target[k], v)
        else:
            target[k] = v
```

**为什么这样**：浅合并 `data.update(eval_yaml)` 会让 eval.yaml 顶层整体覆盖 config.yaml，导致用户在 config.yaml 修改的 `eval.auto_buy_score` 丢失。

### 2.4 错误处理

| 场景 | 做法 |
|---|---|
| API 参数校验 | Pydantic `@field_validator` / `@model_validator` |
| 业务校验失败 | `raise HTTPException(400, detail={"message": "...", "errors": [...]})` |
| 文件 / 资源缺失 | `raise FileNotFoundError(f"配置文件缺失: {path}")` |
| 外部 API 失败 | 记录 loguru warning + 上抛（让上层决定重试） |
| 内部异常 | 通用 `except Exception` 必须有 `logger.exception` |

### 2.5 仓储层

- 命名 `repo_<实体>.py`（如 `repo_items.py`）
- 方法名 `list_xxx` / `get_xxx` / `upsert_xxx` / `delete_xxx`
- 禁止返回 ORM 对象，**必须**返回 dataclass / Pydantic 模型
- 复杂 SQL 放 `infra/`，不放业务模块

### 2.6 日志

- 用 `loguru.logger` 而不是 `logging`
- 业务关键路径：`logger.info("触发自动抢单 task_id={} score={}", task_id, score)`
- 异常：`logger.exception("抢购失败")`（自动带堆栈）
- WARNING：可恢复异常 / 降级 / 重试
- ERROR：需人工介入的失败

### 2.7 SQLite 原始 SQL 查询类型兼容

| 规则 | 说明 |
|---|---|
| **text() 查询 datetime 列返回字符串** | SQLAlchemy 的 `text()` 不走 ORM 类型转换，SQLite 驱动返回 str |
| **序列化前检查类型** | 用 `hasattr(obj, 'isoformat')` 区分 datetime 和字符串 |
| **json 列同理** | SQLite 的 JSON 列通过 text() 查询可能返回 str 而非 dict |

```python
# ✅ 正确：兼容 datetime 对象和字符串
"created_at": r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else str(r["created_at"]) if r["created_at"] else None,

# ❌ 错误：假设 text() 返回 datetime 对象
"created_at": r["created_at"].isoformat() if r["created_at"] else None,  # AttributeError!
```

**适用场景**：所有通过 `text()` 原始 SQL 查询 datetime / json 列的场景。
**不适用**：ORM 查询（`session.query(Model)` 自动类型转换）。

### 2.8 数据删除完整性

| 规则 | 说明 |
|---|---|
| **删除前检查关联** | 有外键引用的表删除前必须处理关联数据 |
| **定义级联策略** | `TABLE_RELATIONS` 字典：`cascade`（级联删除）/ `set_null`（置空外键） |
| **级联预览 API** | 提供只读预览接口，让用户确认影响范围 |
| **事务原子性** | 级联操作与主表删除在同一个 `engine.begin()` 事务中 |
| **审计日志** | 删除操作（含级联详情）写入 events 表 |

```python
# 级联策略定义示例
TABLE_RELATIONS = {
    "tasks": [
        {"table": "items", "fk": "task_id", "action": "cascade"},    # 删任务 → 级联删商品
        {"table": "orders", "fk": "task_id", "action": "cascade"},   # 删任务 → 级联删订单
    ],
    "sellers": [
        {"table": "items", "fk": "seller_id", "action": "set_null"}, # 删卖家 → 保留商品但断开引用
    ],
}
```

**设计原则**：
1. 核心实体（tasks/items）被删时级联删除所有依赖数据，避免孤立记录
2. 辅助实体（sellers）被删时用 `set_null`，保留关联数据的独立查看价值
3. 叶子表（events/notifications）无下游依赖，直接删除

### 2.9 数据库字段语义标注

| 规则 | 说明 |
|---|---|
| **每个字段必须有中文标注** | `COLUMN_LABELS` 字典提供业务含义+类型特征+使用场景+约束条件 |
| **标注内容规范** | 格式：`业务名称（数据类型特征，使用场景，约束说明）` |
| **前端三处展示** | 数据表表头 tooltip + 表结构抽屉 + 编辑表单 label |
| **标注来源为代码** | 与数据库 schema 紧耦合，放代码中比配置文件更合理 |

```python
COLUMN_LABELS = {
    "tasks": {
        "status": "任务状态（running=运行中/paused=已暂停/stopped=已停止/completed=已完成）",
        "cron": "Cron表达式（调度频率，默认*/1 * * * *即每分钟执行）",
    },
}
```

**前端展示规则**：
- 表头：取 `label.split('（')[0]` 显示中文简称，hover 显示完整标注
- 表结构：独立"中文标注"列
- 编辑表单：label 显示中文简称 + 类型标签，hover 显示完整标注

### 2.10 统计查询规范

> **复盘来源**：仪表盘抢单成功率与推送失败率始终显示 0% 问题。

| 规则 | 说明 |
|---|---|
| **查询-写入对齐** | 新增统计查询前，必须搜索所有写入端代码位置，确认查询条件与实际写入取值完全匹配 |
| **枚举值引用枚举类** | 查询条件中的状态值应引用 `OrderStatus` 等枚举类，不硬编码字符串 |
| **分子分母口径一致** | 分母的统计范围必须与分子同类（如分子查 notify 事件，分母不能是全量事件） |
| **hint 文案与公式一致** | 返回给前端的 hint 文案必须与实际计算公式的分子分母语义一致 |
| **数据采集闭环** | 统计指标依赖某表数据时，必须确认该表有写入代码；数据产生点必须写入对应记录 |
| **统计字段统一** | stage / level / status 等统计字段的取值必须全代码库统一 |
| **分母为 0 告警** | 统计指标分母为 0 时记录 WARNING 日志，含可能原因提示 |
| **构造函数测试兼容** | 新增构造函数属性时，用 `getattr(self, '_x', None)` 兼容测试中 `__new__` 跳过构造的场景 |

**统计查询验证流程**（查询-写入对齐法）：

```
1. 找到查询端代码（如 business_kpi.py 中的查询条件）
2. 反向追溯写入端代码（如 buyer.py 中的实际写入值）
   - 用 Grep 搜索所有写入位置
   - 确认实际写入的取值
3. 对比查询条件与写入值是否匹配
4. 如不匹配：
   - 修复查询条件以匹配写入端实际值
   - 或修复写入端以使用统一枚举值
5. 验证修复后查询能命中真实数据
```

**数据采集验证流程**：

```
1. 找到统计查询的数据源（如 EventRow 表）
2. 搜索所有写入该数据源的代码位置
3. 确认统计数据的关键字段（如 stage='notify'）是否有写入
4. 如无写入：
   - 在数据产生点（如 NotifierHub.send()）补齐写入逻辑
   - 确保写入的 level/stage 取值与查询条件一致
5. 添加分母为 0 时的 WARNING 告警日志
```

**适用场景**：
- 仪表盘 / 报表类统计查询问题（KPI 指标为 0 或不准确）
- 新增统计指标时的验证
- 数据采集环节缺失的排查

**不适用场景**：
- 纯前端展示问题（后端数据正确但前端显示错误）
- 数据丢失问题（数据写入后被误删除）
- 查询性能问题（查询慢但结果正确）

### 2.11 datetime 时区一致性

> **复盘来源**：`TypeError: can't subtract offset-naive and offset-aware datetimes` —— 应用层 `_utcnow()` 返回 aware datetime，SQLite `DateTime` 列（未声明 `timezone=True`）读回 naive datetime，aware - naive 抛 TypeError。

| 规则 | 说明 |
|---|---|
| **相减/比较前必须统一时区状态** | 两侧要么都是 aware，要么都是 naive，禁止混用 |
| **项目约定优先 naive** | 与 SQLite 默认行为对齐，应用层 `_utcnow().replace(tzinfo=None)` 统一去时区 |
| **边界处显式标注** | 跨 DB / 跨进程 / 跨模块传递时必须显式 `.replace(tzinfo=None)` 或 `.replace(tzinfo=timezone.utc)` |
| **序列化保留时区信息** | `isoformat()` 序列化的字符串必须包含时区偏移（如 `+00:00`），`fromisoformat` 读回才保持 aware |
| **解析外部时间字符串兜底** | `datetime.fromisoformat(s)` 后必须检查 `tzinfo is None` 并显式补时区 |

```python
# ✅ 正确：相减前两侧统一 naive
# SQLite 读回的 row.created_at 是 naive，_utcnow() 须同步去时区
elapsed = (_utcnow().replace(tzinfo=None) - row.created_at).total_seconds()

# ✅ 正确：解析外部时间字符串兜底补时区
last_dt = datetime.fromisoformat(last_active)
if last_dt.tzinfo is None:
    last_dt = last_dt.replace(tzinfo=timezone.utc)
return datetime.now(timezone.utc) - last_dt > timeout

# ❌ 错误：aware - naive 抛 TypeError
elapsed = (_utcnow() - row.created_at).total_seconds()
```

**根因分析**：SQLite 的 `DateTime` 列未声明 `timezone=True` 时，即使写入 aware datetime，读回也是 naive。这是 DB 边界的隐式契约，应用层必须显式处理。

**适用场景**：
- 任何对 datetime 做相减 / 比较 / 排序的代码
- 跨 DB 边界读取 datetime 字段（SQLAlchemy ORM / `text()` 原始 SQL）
- 跨进程传递 datetime（如子进程 → 主进程 → 前端）
- 反序列化外部时间字符串（ISO format / RFC 2822）

**不适用场景**：
- 仅展示 datetime 字符串（不参与运算）
- 使用 `isoformat()` 序列化且两端都遵循 aware 约定的场景

### 2.12 私有属性封装

> **复盘来源**：`AttributeError: 'XxxRepository' object has no attribute '_Session'` —— 类定义是 `self._session`（小写 s），外部模块调用 `repo._Session()`（大写 S），跨模块访问私有属性时大小写拼写错误。

| 规则 | 说明 |
|---|---|
| **跨模块禁止直接访问 `_` 前缀属性** | `_` 前缀是 Python 私有约定，外部访问破坏封装且易因拼写错误抛 AttributeError |
| **类必须提供公共方法封装跨模块访问** | 跨模块需要的私有属性应通过 `@property` 或公共方法暴露 |
| **跨模块访问必须有契约文档** | 公共方法必须有 docstring 说明返回值语义、并发安全性、生命周期 |
| **测试 mock 优先用公共方法** | 测试中 mock 公共方法而非私有属性，避免重构时测试失效 |

```python
# ✅ 正确：类提供公共方法封装跨模块访问
class XxxRepository:
    def __init__(self, engine):
        self._session = sessionmaker(engine)  # 私有

    def get_config_value(self) -> str | None:
        """获取配置值（跨模块公共 API）。

        Returns:
            str | None: 配置值，未设置时返回 None。
        """
        with self._session() as session:
            row = session.execute(
                select(SomeConfigRow).where(SomeConfigRow.key == SOME_CONFIG_KEY)
            ).scalars().first()
            return row.value if row else None

# 外部模块调用公共方法
repo = XxxRepository(engine)
value = repo.get_config_value()

# ❌ 错误：跨模块直接访问私有属性，易因大小写拼写错误抛 AttributeError
with repo._Session() as session:  # 大小写错误，应为 _session
    ...
```

**根因分析**：跨模块访问 `_` 前缀私有属性是代码气味。Python 不强制私有访问控制，但 `_` 前缀是社区契约，外部访问破坏封装且无类型检查保护。

**适用场景**：
- 任何跨模块 / 跨类访问的场景
- 仓储层（Repository）被业务层 / Web 层调用
- 工具类被多个调用方使用

**不适用场景**：
- 类内部方法访问自身私有属性（合法且推荐）
- 测试代码访问被测类的私有属性（应优先 mock 公共方法）

### 2.13 命名一致性验证

> **复盘来源**：类内属性 `self._session` 与外部调用 `repo._Session` 大小写不一致；类似的还有 `_url` vs `_URL`、`_http_client` vs `_httpClient` 等。

| 规则 | 说明 |
|---|---|
| **类内属性命名全类一致** | 大小写、复数、前缀（`_` / `__`）必须全类一致，禁止 `_session` 与 `_Session` 共存 |
| **代码审查 Grep 属性名变体** | 审查时用 Grep 搜索属性名的大小写 / 单复数 / 前缀变体，确认无拼写错误 |
| **属性命名遵循 PEP 8** | 实例属性用 `snake_case`，常量用 `UPPER_SNAKE_CASE`，私有用 `_` 前缀 |
| **跨模块引用必须与定义一致** | 外部模块引用类属性时必须与类定义完全一致（含大小写） |

```python
# ✅ 正确：类内属性命名一致，外部引用与定义匹配
class HttpClient:
    def __init__(self, base_url: str):
        self._base_url = base_url        # snake_case
        self._session = aiohttp.ClientSession()
        self._MAX_RETRIES = 3            # 常量用 UPPER_SNAKE

    async def get(self, path: str):
        # 类内访问自身属性
        return await self._session.get(f"{self._base_url}{path}")

# 外部模块引用
client = HttpClient("https://api.example.com")
# ✅ 通过公共方法访问，不直接引用 _base_url / _session

# ❌ 错误：类内大小写不一致 + 外部引用拼写错误
class HttpClient:
    def __init__(self):
        self._Session = ...  # 大写 S，违反 PEP 8（实例属性应 snake_case）

# 外部引用
client._session()  # 大小写错误，应为 _Session
```

**审查方法（属性名变体 Grep 法）**：

```
1. 提取类定义的所有 self._xxx 属性名（grep "self\\._\\w+" 文件）
2. 对每个属性名生成变体：
   - 大小写变体：_session → _Session, _SESSION
   - 单复数变体：_url → _urls, _urls → _url
   - 前缀变体：_x → __x, x → _x
3. Grep 全代码库搜索变体，确认无拼写错误引用
4. 重点检查跨模块引用（import 后访问的属性）
```

**适用场景**：
- 任何有类属性 / 实例属性的代码审查
- 跨模块引用类属性的场景
- 重命名属性后的回归检查

**不适用场景**：
- 局部变量（函数内变量无跨模块访问问题）
- 类型注解（TypeAlias / TypeVar 命名遵循独立规范）

### 2.14 跨边界访问契约（核心抽象原则）

> **复盘核心结论**：上述 2.11 / 2.12 / 2.13 三个 Bug 的共同根因都是「跨边界契约不明确」——应用层与 DB 层的时区契约、类定义与外部调用的命名契约，都依赖隐式约定而非显式声明。

| 边界类型 | 契约要求 | 落地手段 |
|---|---|---|
| **DB 边界** | 明确 datetime 字段的时区状态（naive / aware） | ORM 模型字段声明 `timezone=True` 或应用层统一 `.replace(tzinfo=None)` |
| **类边界** | 明确属性 / 方法的可访问性（public / private） | `_` 前缀私有 + 公共方法封装跨模块访问 |
| **模块边界** | 明确导出 API 的稳定性（稳定 / 实验） | `__all__` 显式声明导出 + 公共 API docstring |
| **进程边界** | 明确序列化格式（ISO 8601 / timestamp） | `isoformat()` 序列化 + `fromisoformat` 解析兜底 |

**核心原则**：**跨边界访问必须明确契约，不能依赖隐式约定**。

**审查 checklist**：
1. 是否存在跨 DB 边界的 datetime 读写？时区状态是否一致？
2. 是否存在跨模块访问 `_` 前缀私有属性？是否有公共方法封装？
3. 是否存在跨模块引用类属性？属性名是否与定义完全一致？
4. 是否存在跨进程传递 datetime？序列化格式是否一致？

### 2.15 缓存策略规范

> **复盘来源**：商品列表实时查询缓存策略优化——60 秒 TTL 导致数据滞后、0 条结果被缓存后 5 秒内持续返回空列表。

| 规则 | 说明 |
|---|---|
| **空结果不缓存** | 0 条记录的查询结果禁止写入缓存，否则缓存有效期内所有请求都返回空，掩盖实时数据恢复 |
| **TTL 从配置读取** | 缓存有效期必须从 `config.yaml` 读取，禁止模块级硬编码常量（如 `_LIVE_CACHE_TTL = 60`） |
| **写入守卫与上游独立** | 缓存写入条件（`if filtered:`）必须与上游业务逻辑（`if items:` 写 DB）独立判断，避免耦合 |
| **命中条件与 TTL 同源** | 缓存命中检查（`monotonic - cached[0] < ttl`）的 TTL 必须与写入时使用的 TTL 来自同一配置 |
| **失效自动重查** | 缓存超时后流程自动继续执行实时查询并重新写入缓存，无需人工干预 |

```python
# ✅ 正确：TTL 从配置读取，空结果不缓存
def _get_live_cache_ttl() -> int:
    try:
        from xianyu_hunter.infra.yaml_config import get_config
        return get_config().cache.live_search_ttl
    except Exception:
        return 5  # 配置加载失败时回退默认值

cached = _live_cache.get(task_id)
if cached and (time.monotonic() - cached[0]) < _get_live_cache_ttl():
    return cached[1]  # 命中缓存

# ... 执行实时查询 ...

# 写入缓存：空结果不缓存
if filtered or not _should_skip_empty_result():
    _live_cache[task_id] = (time.monotonic(), result)

# ❌ 错误：硬编码 TTL + 空结果也缓存
_LIVE_CACHE_TTL = 60
_live_cache[task_id] = (time.monotonic(), result)  # 空结果也写入
```

**config.yaml 配置化**：
```yaml
cache:
  live_search_ttl: 5           # 实时搜索缓存 TTL（秒），≤5 保证数据新鲜度
  empty_result_skip: true      # 空结果是否跳过缓存
```

**适用场景**：任何带 TTL 的内存缓存（dict + 时间戳模式）、Redis 缓存、函数结果缓存。
**不适用场景**：CDN 缓存（时效由 Cache-Control 头控制）、DB 查询缓存（由 DB 引擎管理）、无 TTL 的永久缓存。

### 2.16 状态同步规范

> **复盘来源**：Cookie 状态异常——`cookie_checker` 依赖 `CookieRotator` 未初始化的内存层状态，多数登录路径未调 `on_login_success` 导致状态初始化缺失。

| 规则 | 说明 |
|---|---|
| **校验基于实际数据** | 状态校验必须基于实际存储内容（Cookie 文件 / DB 记录），不依赖内存层缓存状态 |
| **显式同步方法** | 多层级状态必须有 `sync_state_from_xxx()` 方法，显式同步存储层 → 内存层 |
| **所有路径覆盖同步** | 枚举所有状态变更路径（登录成功 / Token 刷新 / 外部导入），确保每条都调用同步方法 |
| **存储层持久化关键字段** | `expires` / `created_at` 等关键字段必须持久化到存储层，不仅存内存 |

```python
# ✅ 正确：校验基于实际 Cookie 内容 + 显式同步方法
class CookieRotator:
    def sync_state_from_cookies(self, cookies: list[dict]) -> None:
        """从实际 Cookie 列表同步内存状态"""
        self._valid = any(c.get("name") == "cookie2" for c in cookies)
        self._expires = max((c.get("expires", 0) for c in cookies), default=0)

def cookie_checker(rotator) -> bool:
    cookies = rotator.store.load_cookies()  # 读实际数据
    rotator.sync_state_from_cookies(cookies)  # 显式同步
    return rotator.is_valid  # 基于同步后的状态

# ❌ 错误：校验依赖未初始化的内存状态
def cookie_checker(rotator) -> bool:
    return rotator._valid  # _valid 可能从未被 on_login_success 初始化
```

**适用场景**：多层级状态管理（存储+内存+校验）、登录态/会话态、Cookie 轮换。
**不适用场景**：无状态服务、纯计算函数、单层状态管理。

### 2.17 性能优化范式

> **复盘来源**：实时查询慢响应优化——13 个瓶颈（同步 DB 阻塞、无缓存、串行查询），8 个方案将响应从 15-20s 降至 <100ms（缓存命中）。

| 规则 | 说明 |
|---|---|
| **I/O 异步化** | 阻塞调用（`requests.get` / `time.sleep` / 同步 DB）必须用 `run_in_executor` 或原生 async 替代 |
| **缓存引入** | 高频查询必须引入缓存层，TTL 从配置读取（见 §2.15） |
| **SQL 下推过滤** | 价格 / 时间 / 关键词过滤应下推到 SQL 层，不在 Python 层全量加载后过滤 |
| **查询合并** | list + count 查询必须合并为单条 SQL（`SELECT *, COUNT(*) OVER()`），减少 DB 往返 |
| **流式响应** | 耗时 > 3s 的接口必须用 SSE / WebSocket 分阶段推送进度，不用同步等待 |

```python
# ✅ 正确：异步 DB + 缓存 + SQL 下推 + 流式响应
async def event_stream():
    cached = _live_cache.get(task_id)
    if cached and (time.monotonic() - cached[0]) < _get_live_cache_ttl():
        yield sse({"stage": "done", **cached[1]})
        return
    yield sse({"stage": "searching"})
    raw_results = await asyncio.wait_for(collector.live_search(...), timeout=20.0)
    # 批量写入 DB（run_in_executor 避免阻塞事件循环）
    await loop.run_in_executor(None, functools.partial(repo.batch_upsert, ...))

# ❌ 错误：同步 DB 阻塞事件循环 + 无缓存 + Python 层过滤
def search(keyword):
    results = requests.get(url).json()  # 阻塞！
    all_items = db.query(Item).all()    # 全量加载！
    filtered = [i for i in all_items if i.price > min_price]  # Python 层过滤！
```

**适用场景**：API 响应慢（> 500ms）、DB 查询慢、外部调用阻塞事件循环。
**不适用场景**：算法复杂度问题（需算法优化非缓存）、内存泄漏（需 profiling）。

### 2.18 评分系统规范

> **复盘来源**：AI 颜色评估分数收敛——退化 fallback 导致所有商品评分趋同（80-85 分），高分被低分维度拉低。

| 规则 | 说明 |
|---|---|
| **数据质量分级** | 评分必须按数据维度完整度分级：全维度（4 维有效）/ 部分维度（1-3 维）/ 仅有价格 |
| **平滑过渡函数** | 阈值扣分必须用 Sigmoid 渐进函数，不用硬阈值（`if x > 80: -10` 导致阈值附近分数跳变） |
| **动态缓冲** | 高分保护缓冲必须基于维度标准差动态计算（`buffer = max(30, int(50 - std * 0.4))`），不用固定值 |
| **结果集成非仅存储** | AI 评估结果必须通过 `apply_ai_eval` 集成到总分（reject→0, caution→*0.85），不能仅存为 metadata |
| **反馈闭环** | 评分系统必须有反馈收集 API（准确/部分准确/不准确），反馈数据用于优化评分模型 |

```python
# ✅ 正确：Sigmoid 渐进扣分 + 动态缓冲
def _sigmoid_deduction(self, value: float, threshold: float, max_deduction: int) -> int:
    """Sigmoid 渐进扣分：避免硬阈值附近的分数跳变"""
    if value >= threshold:
        return 0
    ratio = (threshold - value) / threshold
    return int(max_deduction / (1 + math.exp(-10 * (ratio - 0.5))))

def _evaluate_full(self, dims: dict) -> int:
    std = np.std(list(dims.values()))
    buffer = max(30, int(50 - std * 0.4))  # 维度分散时缩小缓冲
    base = sum(dims.values()) // len(dims)
    return min(100, base + buffer) if base > 70 else base

# ❌ 错误：硬阈值扣分 + 固定缓冲 + 退化 fallback
def _evaluate(self, dims):
    if len(dims) < 4:
        return 60  # 退化 fallback 导致分数收敛！
    if dims['credit'] < 60:
        score -= 10  # 硬阈值，60 和 59 差 10 分
```

**适用场景**：AI 评分、质量评分、风险评分、多维度综合评估。
**不适用场景**：单一维度评分（无需分级与缓冲）、二值判定（通过/不通过）。

### 2.19 外部依赖容错规范

> **复盘来源**：RGV587 反爬导致 49.4% 零结果搜索——token 过期、DOM 选择器变更、无限重试耗尽资源。

| 规则 | 说明 |
|---|---|
| **Token 预刷新** | 外部 API token 必须在过期前主动刷新，不等过期后被动重试 |
| **DOM 选择器容错** | 浏览器自动化的 DOM 选择器必须提供 2+ 个备选，主选择器失败时 fallback |
| **失败重试限流** | 重试必须有最大次数限制 + 退避间隔（`min(retry_count * 2, 30)` 秒），禁止无限重试 |
| **复合索引保障** | 外部数据写入 DB 必须有复合索引支撑高频查询，避免全表扫描 |
| **日志格式统一** | 外部调用日志必须统一格式（`stage=xxx elapsed=xxx result=xxx`），便于聚合分析 |

```python
# ✅ 正确：Token 预刷新 + DOM 容错 + 限流重试
async def live_search(self, keyword: str):
    # Token 预刷新：剩余有效期 < 阈值时主动刷新
    if self._token_expiring_soon():
        await self._ensure_fresh_m5tk(force=False)

    # DOM 选择器容错：主选择器 + 备选
    title = await page.query_selector(".title-main") or \
            await page.query_selector("[data-spm='title']") or \
            await page.query_selector(".item-title")

    # 限流重试：最多 3 次，指数退避
    for attempt in range(3):
        try:
            return await self._do_search(keyword)
        except RGVS87Error:
            await asyncio.sleep(min(attempt * 2, 30))
    raise SearchFailed("重试 3 次后仍失败")

# ❌ 错误：无预刷新 + 单选择器 + 无限重试
while True:
    title = await page.query_selector(".title-main")  # 选择器变更即失败
    if token_expired:
        refresh_token()  # 过期后才刷新，已有请求失败
    try:
        return await search()
    except:
        continue  # 无限重试！
```

**适用场景**：爬虫、第三方 API 集成、浏览器自动化、外部依赖不稳定场景。
**不适用场景**：内部稳定服务、一次性脚本、无外部依赖的纯计算。

### 2.20 多格式输入解析规范

> **复盘来源**：Cookie 注入登录快速粘贴——用户粘贴的 Cookie 格式多样（标准头、换行分隔、Header 前缀、尾分号），单一解析逻辑无法覆盖。

| 规则 | 说明 |
|---|---|
| **枚举所有格式** | 输入解析必须枚举所有可能的格式，逐个尝试匹配 |
| **容错分割点** | 键值分割只在第一个 `=` 处分割（`split('=', 1)`），避免值中包含 `=` 时截断 |
| **无效项过滤** | 解析结果必须过滤无效键（空值 / 非法字符 / 已知无效键名） |
| **实时反馈** | 解析过程必须提供实时视觉反馈（识别 N 项 / 填充 N 项 / 无效 N 项） |

```typescript
// ✅ 正确：枚举 4 种格式 + 第一个 = 分割 + 过滤无效键
function parseCookieText(text: string): Record<string, string> {
    const result: Record<string, string> = {};
    const invalidKeys = new Set(['path', 'domain', 'expires', 'max-age']);

    // 格式 1：标准 Cookie 头（key=val; key=val）
    // 格式 2：换行分隔（key=val\nkey=val）
    // 格式 3：Header 前缀（Cookie: key=val; ...）
    // 格式 4：尾分号（key=val;）
    const normalized = text.replace(/^Cookie:\s*/i, '').trim();
    const pairs = normalized.split(/[;\n]/).map(s => s.trim()).filter(Boolean);

    for (const pair of pairs) {
        const idx = pair.indexOf('=');        // 第一个 = 的位置
        if (idx < 1) continue;               // 无 = 或 key 为空 → 跳过
        const key = pair.slice(0, idx).trim();
        const val = pair.slice(idx + 1).trim();
        if (invalidKeys.has(key.toLowerCase())) continue;  // 过滤无效键
        result[key] = val;
    }
    return result;
}

// ❌ 错误：单一格式 + 全部 = 分割 + 不过滤
const pairs = text.split(';');
for (const pair of pairs) {
    const [key, ...rest] = pair.split('=');  // 值中含 = 会被截断！
    result[key.trim()] = rest.join('=');      // 虽然修复了截断但未过滤无效键
}
```

**适用场景**：粘贴板解析、文件导入（CSV / JSON / 多格式）、多源数据合并。
**不适用场景**：单一固定格式输入（如 API JSON 响应）、结构化表单输入。

---

### 2.21 LLM 附加调用预算与用量闭环规范

> **复盘来源**：B-REVIEW-291——`generate_follow_ups` 方法未复用主 `generate` 方法的 `check_budget()` + `_record_llm_usage()`，导致预算超限后仍消耗 token、用量统计偏差。

| 规则 | 说明 |
|---|---|
| **预算检查前置** | 任何 LLM 调用（主调用 + 附加调用）执行前必须调用 `check_budget()`，超限时拒绝调用并降级 |
| **用量记录闭环** | 任何 LLM 调用完成后必须调用 `_record_llm_usage()`，写入 token 用量、模型名、调用场景 |
| **复用主调用工具** | 附加调用必须复用主调用方法的预算/记录工具，禁止另起一套统计逻辑 |
| **降级策略显式** | 预算超限时必须显式降级（返回空 follow_ups + WARNING 日志），禁止静默跳过 |

```python
# ✅ 正确：附加调用复用主调用的预算检查 + 用量记录
async def generate_follow_ups(self, query: str, context: str) -> list[str]:
    # 复用主调用的预算检查：超限则降级，不消耗 token
    if self._ai_usage is not None:
        budget_ok, reason = self._ai_usage.check_budget()
        if not budget_ok:
            logger.warning(f"follow_ups 预算超限跳过: {reason}")
            return []  # 显式降级，返回空列表
    try:
        result = await self._call_llm(query, context)
        return result
    finally:
        # 复用主调用的用量记录：无论成功失败都记录
        self._record_llm_usage(messages, output)

# ❌ 错误：附加调用无预算检查 + 无用量记录
async def generate_follow_ups(self, query: str, context: str) -> list[str]:
    # 直接调用 LLM，未检查预算，超限后仍消耗 token
    result = await self._call_llm(query, context)
    return result  # 未记录用量，统计偏差
```

**适用场景**：一个请求触发多次 LLM 调用（主回答 + follow_ups 生成 + 标题摘要 + 标签抽取）。
**不适用场景**：单次 LLM 调用；非 LLM 的纯本地计算。

---

### 2.22 LLM 附加调用独立超时规范

> **复盘来源**：B-REVIEW-292——附加 LLM 调用未用 `asyncio.wait_for` 包裹，可能阻塞主流程（如 SSE DONE 事件）。

| 规则 | 说明 |
|---|---|
| **每个调用独立超时** | 主调用和每个附加调用都必须用 `asyncio.wait_for(coro, timeout=cfg.xxx_timeout)` 包裹 |
| **超时阈值配置化** | 主调用/附加调用可有不同超时，均从 `config.yaml` 读取，禁止硬编码 |
| **超时降级而非抛错** | 超时 except 块必须降级（返回空结果 + WARNING），不向上抛 TimeoutError 中断主流程 |
| **超时日志结构化** | 必须记录 `stage=xxx elapsed=xxx timeout=xxx model=xxx`，便于聚合分析 |

```python
# ✅ 正确：附加调用独立超时 + 超时降级
async def generate_follow_ups(self, query: str, context: str) -> list[str]:
    try:
        # 独立超时：附加调用超时阈值从 config 读取，不阻塞主流程
        result = await asyncio.wait_for(
            self._call_llm(query, context),
            timeout=self._config.aux_call_timeout_sec,  # 配置化，如 8s
        )
        return result
    except asyncio.TimeoutError:
        # 超时降级：返回空列表 + 结构化日志，不抛错
        logger.warning(
            f"stage=follow_ups elapsed={self._config.aux_call_timeout_sec} "
            f"timeout={self._config.aux_call_timeout_sec} model={self._llm_config.model}"
        )
        return []

# ❌ 错误：无超时包裹 + 超时抛错中断主流程
async def generate_follow_ups(self, query: str, context: str) -> list[str]:
    # 无 asyncio.wait_for，附加调用可能阻塞 DONE 事件
    result = await self._call_llm(query, context)
    return result
```

**适用场景**：流式响应（SSE）中的附加调用；任何"主流程不能被附加任务拖死"的场景。
**不适用场景**：同步阻塞的 CLI 工具；无超时要求的批处理任务。

---

### 2.23 LLM 响应结构化解析规范

> **复盘来源**：B-REVIEW-293——禁止用正则提取 JSON，必须用 `json.loads` + 元素类型校验，避免解析失败导致后续逻辑崩溃。

| 规则 | 说明 |
|---|---|
| **禁止正则提取 JSON** | LLM 返回的 JSON 必须用 `json.loads` 解析，禁止 `re.search(r'\{.*\}', text)` 提取 |
| **元素类型校验** | 解析后必须对每个字段做类型校验（用 Pydantic 模型或显式 isinstance 检查） |
| **解析失败降级** | `json.JSONDecodeError` 必须捕获并降级（返回默认值 + WARNING），禁止向上抛 |
| **Markdown 代码块剥离** | LLM 常返回 ` ```json ... ``` `，必须先剥离代码块标记再 `json.loads` |

```python
# ✅ 正确：json.loads + 类型校验 + 代码块剥离 + 降级
from pydantic import BaseModel, ValidationError

class FollowUpsResponse(BaseModel):
    """LLM 返回的 follow_ups 结构化模型"""
    follow_ups: list[str]

def parse_follow_ups(raw: str) -> list[str]:
    # 剥离 Markdown 代码块标记
    text = raw.strip()
    if text.startswith("```"):
        # 剥离 ```json 或 ``` 前缀和尾部 ```
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        data = json.loads(text)
        # Pydantic 类型校验：确保 follow_ups 是 list[str]
        return FollowUpsResponse.model_validate(data).follow_ups
    except (json.JSONDecodeError, ValidationError) as e:
        logger.warning(f"follow_ups 解析失败降级: {e}")
        return []  # 降级返回空列表

# ❌ 错误：正则提取 JSON + 无类型校验 + 解析失败抛错
def parse_follow_ups(raw: str) -> list[str]:
    match = re.search(r'\{.*\}', raw, re.DOTALL)  # 正则提取不可靠
    if match:
        data = json.loads(match.group())  # 无类型校验
        return data["follow_ups"]  # 字段不存在时 KeyError 崩溃
    raise ValueError("无法解析")  # 解析失败抛错，中断主流程
```

**适用场景**：LLM 返回结构化 JSON 的所有场景（follow_ups、标签、评分、工具调用）。
**不适用场景**：LLM 返回纯文本（无需解析）；SDK 已强制 JSON mode（如 OpenAI `response_format`）。

---

### 2.24 LLM 多调用一致性规范

> **复盘来源**：B-REVIEW-294——同一请求中多个 LLM 调用（主+附加）在错误处理、日志、降级策略上不一致，导致排查困难、行为不可预测。

| 规则 | 说明 |
|---|---|
| **错误处理一致** | 主调用和附加调用的 except 块结构一致（捕获相同异常类型 + 相同降级模式） |
| **日志格式一致** | 所有 LLM 调用日志使用统一格式（`stage=xxx model=xxx elapsed=xxx tokens=xxx`） |
| **降级策略一致** | 主调用降级时附加调用必须跳过；附加调用降级时主调用结果保留 |
| **配置参数集中** | 所有 LLM 调用的超时/重试/降级阈值集中在 `llm_call_governance` 节点，禁止散落 |

```python
# ✅ 正确：主调用与附加调用共用统一的错误处理/日志/降级上下文
class LLMCallContext:
    """统一 LLM 调用上下文：所有调用（主+附加）共用同一套治理策略"""
    def __init__(self, config: LLMCallGovernanceConfig):
        self._config = config

    async def call(self, stage: str, coro_factory) -> Any:
        """统一的调用入口：预算检查 + 独立超时 + 结构化日志 + 降级"""
        # 1. 预算检查（主+附加共用）
        if not self._check_budget():
            logger.warning(f"stage={stage} budget_exceeded action=skip")
            return None
        # 2. 独立超时（按 stage 配置不同阈值）
        timeout = self._config.timeout_by_stage.get(stage, self._config.default_timeout)
        try:
            start = time.monotonic()
            result = await asyncio.wait_for(coro_factory(), timeout=timeout)
            elapsed = time.monotonic() - start
            logger.info(f"stage={stage} model={self._model} elapsed={elapsed:.2f} status=ok")
            return result
        except asyncio.TimeoutError:
            logger.warning(f"stage={stage} elapsed={timeout} timeout={timeout} status=degraded")
            return None  # 统一降级：返回 None

# 主调用和附加调用共用同一上下文
ctx = LLMCallContext(config)
main_result = await ctx.call("main_answer", lambda: llm.generate(query, context))
follow_ups = await ctx.call("follow_ups", lambda: llm.generate_follow_ups(query, context))

# ❌ 错误：主调用与附加调用错误处理/日志/降级策略各不相同
async def main_call():
    try:
        return await llm.generate(query, context)
    except Exception:
        logger.exception("主调用失败")
        raise  # 主调用抛错

async def aux_call():
    try:
        return await llm.generate_follow_ups(query, context)
    except Exception:
        logger.error("附加调用失败")  # 日志级别不一致
        return []  # 附加调用降级，策略不对称
```

**适用场景**：一个请求触发 ≥2 次 LLM 调用；流式响应中主回答 + 附加产出（follow_ups/标题/标签）。
**不适用场景**：单次 LLM 调用；不同业务场景的 LLM 调用（无需强制一致）。

### 2.25 预设切换双步模式与归档加载契约

> **复盘来源**：B-REVIEW-327 / F-REVIEW-243——快捷预设切换时若只传 `to_preset`，当前预设的 API Key 无法归档，导致下次切回时丢失；前端保存明文 Key 也违反"敏感数据后端主导"原则（参见 §2.26）。

| 规则 | 说明 |
|---|---|
| **双参数契约** | 切换预设必须同时传 `from_preset` 与 `to_preset`，禁止只传 `to_preset` |
| **原子归档-加载** | 后端在同一事务中：① 归档 `from_preset` 当前 Key → ② 加载 `to_preset` 已存 Key，失败时整体回滚 |
| **返回脱敏值** | 后端返回脱敏 Key（如 `sk-***...abc`），前端只能用此值回显，禁止本地明文存储 |
| **前端无明文** | 前端禁止把明文 Key 写入 `localStorage` / `sessionStorage` / 状态管理 store |
| **幂等性** | 相同 `from→to` 多次切换结果一致：归档值不变，加载值不变 |
| **预设定义前后端分离** | 预设列表（`base_url`/`model`/`label`/`color`/`apiKeyUrl`）只存在于前端 `constants.ts`，后端通过 `apply-preset` 接口接收参数执行 |

```typescript
// ✅ 正确：双参数 + 用后端返回的脱敏值更新 UI
const applyPreset = async (fromPreset: string, toPreset: string) => {
  const result = await aiApi.applyPreset({
    from_preset: fromPreset,
    to_preset: toPreset,
    base_url: PRESETS[toPreset].base_url,
    model: PRESETS[toPreset].model,
    vision_model: PRESETS[toPreset].vision_model,
  })
  // result.api_key 为后端返回的脱敏值，直接用于回显
  setConfig((prev) => ({
    ...prev,
    api_key: result.api_key,        // 脱敏值，例如 "sk-***...abc"
    preset_id: toPreset,
    base_url: result.base_url,
    model: result.model,
  }))
  setActivePresetKey(toPreset)
}

// ❌ 错误：只传 to_preset，当前 Key 无法归档，下次切回需要重新输入
const applyPreset = async (toPreset: string) => {
  await aiApi.putConfig({ preset_id: toPreset, ...PRESETS[toPreset] })
}

// ❌ 错误：前端保存明文 Key（违反 §2.26 敏感数据后端主导原则）
localStorage.setItem(`preset_key_${toPreset}`, plainKey)
```

```python
# ✅ 正确：后端原子归档-加载 + 返回脱敏值
@router.post("/api/ai/apply-preset")
async def apply_preset(body: ApplyPresetBody):
    # 1. 归档当前预设的 Key（from_preset）
    if body.from_preset:
        current_key = await secrets.get_active_api_key()
        if current_key:
            await secrets.set_preset_api_key(body.from_preset, current_key)
    # 2. 加载目标预设的 Key（to_preset）
    target_key = await secrets.get_preset_api_key(body.to_preset) or ""
    # 3. 持久化新预设配置
    await update_config(base_url=body.base_url, model=body.model, api_key=target_key)
    # 4. 返回脱敏值供前端回显
    return {
        "api_key": mask_key(target_key),   # "sk-***...abc"
        "base_url": body.base_url,
        "model": body.model,
    }
```

**适用场景**：模型预设切换、Embedding 预设切换、通知渠道预设切换等任何"切换时需保留旧值、加载新值"的场景。
**不适用场景**：单字段直接编辑（如手动改 `base_url`，无预设概念）；首次初始化（无 `from_preset` 可归档）。

### 2.26 敏感数据后端主导原则

> **复盘来源**：API Key 关联存储改造、Token 比较时序攻击防护、401 JSON 化、Token 写入失败告警——历史经验表明前端持久化敏感数据 = 不可控泄漏面。

| 规则 | 说明 |
|---|---|
| **存储位置后端决定** | 敏感数据（API Key/Token/密码/Cookie）的存储位置由后端决定，前端只发送不持久化 |
| **展示必须脱敏** | 敏感数据展示必须由后端返回脱敏值（如 `sk-***...abc`），前端禁止本地明文存储 |
| **系统级存储** | 后端敏感字段必须使用 `keyring` / `secret` 等系统级存储，禁止 yaml/DB 明文 |
| **常量时间比较** | 敏感字段比较必须用 `hmac.compare_digest()`，禁止 `==` / `!=` 直接比较（防时序攻击） |
| **写入失败告警** | 敏感字段写入失败必须 `logging.warning()` 告警，禁止静默吞异常 |
| **日志禁打值** | 日志中禁止打印敏感字段值（包括长度、前缀），只记录布尔匹配结果或操作结果 |
| **401 返回 JSON** | 鉴权失败 401 必须返回 `{"detail": "Unauthorized"}` JSON，禁止纯文本（前端统一错误处理） |
| **白名单显式** | 不需要鉴权的接口必须显式加入认证白名单（参见 project_memory.md Hard Constraints） |

```python
# ✅ 正确：常量时间比较 + 日志只记布尔结果 + 写入失败告警
import hmac, logging
logger = logging.getLogger(__name__)

async def verify_token(provided: str, expected: str) -> bool:
    # hmac.compare_digest 防止时序攻击
    matched = hmac.compare_digest(provided or "", expected or "")
    # 日志只记录布尔结果，不记录 token 值或长度
    logger.info(f"token_verify status={'ok' if matched else 'fail'}")
    return matched

async def save_api_key(key: str) -> None:
    try:
        await secrets.set_active_api_key(key)
    except Exception as e:
        # 写入失败必须告警，不能静默
        logging.warning(f"api_key_save status=fail error={type(e).__name__}")
        raise

def mask_key(key: str) -> str:
    """脱敏：保留前3后3，中间用 *** 代替"""
    if not key or len(key) <= 6:
        return "***"
    return f"{key[:3]}***...{key[-3:]}"
```

```python
# ❌ 错误：直接 == 比较（时序攻击可逐字节探测）
if provided_token == expected_token:
    grant_access()

# ❌ 错误：日志打印 token 值或长度
logger.info(f"verify token={provided} len={len(provided)}")

# ❌ 错误：静默吞异常，前端无法感知 Key 未保存
try:
    save_api_key(key)
except Exception:
    pass

# ❌ 错误：401 返回纯文本（前端 fetch Promise reject 后无法解析 detail）
return PlainTextResponse("Unauthorized", status_code=401)
```

**适用场景**：API Key、Token、密码、Cookie、Webhook URL 中含 token 部分、签名密钥等任何不可泄漏的凭据。
**不适用场景**：非敏感配置（端点 URL、模型名、UI 偏好、缓存 TTL）；用户公开可见的数据（商品标题、卖家昵称）。

---

## 三、TypeScript 前端规范

### 3.1 类型系统

| 规则 | 说明 |
|---|---|
| **TS 严格模式开启** | `tsconfig.json` 启用 `strict: true` |
| **禁用 `any`** | 用 `Record<string, unknown>` 替代 |
| **API 响应必须有类型** | `api/types.ts` 集中定义，禁止页面内联 |
| **字段命名透传后端** | `snake_case` 直接传，不做大小写转换 |
| **可选字段用 `?`** | `field?: string` 而非 `field: string \| null` |

### 3.2 React 组件

| 规则 | 说明 |
|---|---|
| **函数组件 + Hooks** | 不用 class 组件 |
| **Props 接口命名 `XxxProps`** | `interface ButtonProps` |
| **避免大组件** | 超过 200 行拆子组件 |
| **状态就近** | 不在父组件存所有子组件状态 |
| **副作用 useEffect 最小化** | 优先用 `useMemo` / `useCallback` 替代 |
| **Key 稳定** | 列表 `key` 用业务 ID，不用 index |

### 3.3 Zustand 状态

- **按业务拆 store**：`configStore` / `taskStore` / `userStore`
- **Selector 订阅**：`useStore(s => s.field)` 而非 `useStore()`
- **Action 命名 `xxxSave` / `xxxUpdate`**：动词开头
- **不存整个大对象**：拆分到独立字段

```typescript
// ✅ 推荐
const autoBuyScore = useConfigStore(s => s.config.eval?.auto_buy_score)
const updateConfig = useConfigStore(s => s.updateConfig)

// ❌ 反例
const config = useConfigStore()  // 整个 store 订阅，任何字段变都重渲染
```

### 3.4 错误处理（重要）

**铁律：禁止空 catch 笼统提示**

```typescript
// ❌ 反例
try { await api.save() } catch { message.error('保存失败') }

// ✅ 正例
import { extractApiError } from '@/utils/apiError'

try {
  await api.save()
  message.success('保存成功')
} catch (e) {
  message.error(extractApiError(e), 5)
}
```

`extractApiError` 统一处理：
- 400 校验失败：`{detail: {message, errors: [...]}}` → 拼接展示
- 401：`"认证已过期，请重新登录"`
- 500：`"服务器内部错误，请稍后重试"`
- 网络失败：`e.message`

### 3.5 样式

- **用 Ant Design 5 组件**：Button / Form / Table / Modal
- **设计系统遵循米其林规范**：色彩 / 圆角 / 间距
- **避免 inline style**：用 CSS class / styled
- **暗 / 亮主题双适配**

### 3.6 新增页面三同步检查清单

| 检查项 | 文件 | 说明 |
|---|---|---|
| ① 路由表 | `App.tsx` | `<Route path="xxx" element={...} />` 必须添加 |
| ② 菜单项 | `MainLayout.tsx` | Menu items 中添加对应 key（以 `/` 开头的路径） |
| ③ 页面组件 | `pages/` | 创建对应页面组件 |
| ④ 构建验证 | 终端 | `tsc` + `vite build` 确认无报错 |

**常见遗漏**：只创建了组件和菜单，忘记添加路由 → 点击菜单跳转到 fallback 页面。

**验证方法**：点击菜单项后 URL 正确且页面内容正确显示，无 404 或重定向。

### 3.7 antd Modal 动态状态管理

| 规则 | 说明 |
|---|---|
| **禁止 DOM 操作** | `querySelector` 在 antd 5 Modal.confirm 中不可靠（DOM 结构不稳定） |
| **用 `modal.update()`** | 动态更新 Modal 的 `okButtonProps` / `title` / `content` |
| **初始状态设 `disabled: true`** | 防止用户未确认就点击 |

```typescript
// ✅ 正确：用 modal.update() 动态切换
const modal = Modal.confirm({
  okButtonProps: { danger: true, disabled: true },
  content: (
    <Input.Password onChange={(e) => {
      tokenValue = e.target.value
      modal.update((prev) => ({
        ...prev,
        okButtonProps: { danger: true, disabled: tokenValue !== CONFIRM_TOKEN },
      }))
    }} />
  ),
})

// ❌ 错误：用 querySelector 操作 DOM
setTimeout(() => {
  const okBtn = document.querySelector('.ant-btn-primary')
  if (okBtn) okBtn.removeAttribute('disabled')  // 不可靠！
}, 100)
```

### 3.8 antd Menu 防御性编程

| 规则 | 说明 |
|---|---|
| **onClick 校验路径 key** | SubMenu 父项的 key 不以 `/` 开头，navigate 会跳到非法 URL |
| **只对路径 key 调 navigate** | `if (key.startsWith('/')) navigate(key)` |

```typescript
// ✅ 正确：过滤非路径 key
<Menu
  onClick={({ key }) => {
    if (typeof key === 'string' && key.startsWith('/')) {
      navigate(key)
    }
  }}
/>

// ❌ 错误：所有 key 都 navigate
<Menu onClick={({ key }) => navigate(key)} />  // SubMenu key='sub-data' 也会触发
```

### 3.9 图表组件按需注册规范

> **复盘来源**：仪表盘"评估漏斗与命中率"图表不展示问题（ECharts `FunnelChart` 未在 `echarts.use([...])` 注册，导致 `type: 'funnel'` 静默渲染失败，canvas 不生成）。

| 规则 | 说明 |
|---|---|
| **使用点与注册点同步** | 新增图表 `type` 时必须同步在 `EChart.tsx` 的 `echarts.use([...])` 注册对应 Chart 类 |
| **集中注册** | 禁止在多个组件重复 `echarts.use()`，统一在 `components/charts/EChart.tsx` 注册一次，其他组件只 import `EChart` 组件 |
| **静默失败排查优先级** | 图表不渲染且无报错 → 优先用"使用点-注册点差集法"定位遗漏项，而非先怀疑数据/权限 |
| **修改后必验证** | 改 EChart.tsx 后必跑 `npm run build` + 浏览器实测 canvas 节点存在且尺寸 > 0 |

**排查方法（使用点-注册点差集法）**：

```
1. Grep 所有图表 type 使用点：
   grep "type:\s*['\"]\(bar\|line\|funnel\|heatmap\|radar\|pie\|scatter\|gauge\|graph\|sankey\|tree\|treemap\|sunburst\|boxplot\|candlestick\|effectScatter\|lines\|map\|parallel\|pictorialBar\|themeRiver\|custom\)['\"]" frontend/src
2. 读取 EChart.tsx 的 echarts.use([...]) 注册清单
3. 差集 = 使用点 type - 注册点 Chart 类 → 即遗漏的图表类
4. 从 'echarts/charts' 导入对应 Chart 类并加入 echarts.use
```

**适用场景**：ECharts 按需导入（`echarts/core` + `echarts.use`）架构；任何采用按需注册（tree-shakable）的第三方库。
**不适用场景**：全量导入（`import * as echarts from 'echarts'`）——不存在注册遗漏；显式报错（TypeError/ReferenceError）——直接看错误信息。

**验证清单**（修改 EChart.tsx 后必跑）：

| 步骤 | 命令 / 动作 | 期望 |
|---|---|---|
| 类型检查 | `cd frontend && npx tsc --noEmit` | 无报错 |
| 构建 | `cd frontend && npm run build` | 成功，chunk 体积合理增长 |
| 控制台 | 浏览器 devtools console | 无 `Component type not found` warn |
| DOM 验证 | `evaluate_script` 检测 `canvas` 数量 + 尺寸 | canvas 存在且 width/height > 0 |

详见 [xianyu-frontend-code-review §2.13](../../xianyu-frontend-code-review/SKILL.md) ERC-01~04 检查点。

---

### 3.10 Markdown 预处理代码块保护规范

> **复盘来源**：F-REVIEW-227——对 Markdown 字符串做 `[来源:N]` 替换时未分割代码块/行内代码，导致代码内容中的 `[来源:1]` 字面量被错误替换。

| 规则 | 说明 |
|---|---|
| **分割代码块再处理** | 对 Markdown 做字符串替换前必须先按 ` ``` ` 分割代码块，仅对非代码块部分替换 |
| **行内代码保护** | 用正则提取所有 `` `...` `` 行内代码段，替换前占位，替换后还原 |
| **替换函数纯函数化** | 替换逻辑封装为纯函数 `injectCitations(md, citations): string`，便于单测 |
| **单测覆盖代码块场景** | 必须有单测覆盖：代码块内含 `[来源:1]` 字面量、行内代码含 `[来源:1]`、嵌套代码块 |

```typescript
// ✅ 正确：分割代码块 + 行内代码占位 + 仅对非代码段替换
function injectCitations(markdown: string, citations: Citation[]): string {
  // 1. 按代码块分割，仅处理非代码块部分
  const parts = markdown.split(/(```[\s\S]*?```)/g)
  return parts.map(part => {
    // 代码块原样返回，不做替换
    if (part.startsWith('```')) return part
    // 2. 行内代码占位保护
    const inlineCodes: string[] = []
    let processed = part.replace(/`[^`]+`/g, (match) => {
      inlineCodes.push(match)
      return `__INLINE_CODE_${inlineCodes.length - 1}__`
    })
    // 3. 对非代码段做引用替换
    processed = processed.replace(/\[来源:(\d+)\]/g, (_, n) => {
      const cite = citations[parseInt(n) - 1]
      return cite ? `[${n}](${cite.url})` : _
    })
    // 4. 还原行内代码
    processed = processed.replace(/__INLINE_CODE_(\d+)__/g, (_, i) => inlineCodes[parseInt(i)])
    return processed
  }).join('')
}

// ❌ 错误：直接对整个 Markdown 字符串替换，破坏代码块内容
function injectCitationsBad(markdown: string, citations: Citation[]): string {
  // 代码块内的 [来源:1] 字面量也被替换，破坏代码语义
  return markdown.replace(/\[来源:(\d+)\]/g, (_, n) => {
    const cite = citations[parseInt(n) - 1]
    return cite ? `[${n}](${cite.url})` : _
  })
}
```

**适用场景**：对 LLM 返回的 Markdown 做后处理（引用注入、链接改写、关键词高亮）。
**不适用场景**：纯文本处理（无代码块）；只读不改的 Markdown 渲染。

---

### 3.11 流式响应 onComplete 持久化完整性规范

> **复盘来源**：F-REVIEW-228——onComplete 持久化条件基于"主回答非空"，导致有 follow_ups 但主回答为空时消息丢失。

| 规则 | 说明 |
|---|---|
| **持久化条件基于"任一产出非空"** | `if (mainAnswer \|\| followUps?.length \|\| citations?.length)` 才持久化，禁止仅检查主回答 |
| **产出字段显式枚举** | 持久化条件必须显式列出所有产出字段，禁止 `Object.values(resp).some(Boolean)` 等动态判断 |
| **空产出显式日志** | 所有产出均空时必须 `console.warn` 并跳过持久化，禁止静默 |
| **持久化字段完整性** | 持久化的 message 对象必须包含所有产出字段，禁止只存主回答丢附加产出 |

```typescript
// ✅ 正确：持久化条件覆盖所有产出字段
function handleStreamComplete(response: StreamResponse): void {
  const { mainAnswer, followUps, citations, title, tags } = response
  // 任一产出非空才持久化
  const hasAnyOutput = !!(mainAnswer || followUps?.length || citations?.length || title || tags?.length)
  if (!hasAnyOutput) {
    console.warn('流式响应所有产出均为空，跳过持久化')
    return
  }
  // 持久化完整 message 对象（包含所有产出字段）
  saveMessage({
    content: mainAnswer,
    follow_ups: followUps,
    sources: citations,
    title,
    tags,
    created_at: Date.now(),
  })
}

// ❌ 错误：仅检查主回答非空，follow_ups 非空但主回答为空时消息丢失
function handleStreamCompleteBad(response: StreamResponse): void {
  if (response.mainAnswer) {  // 仅检查主回答
    saveMessage({
      content: response.mainAnswer,
      // follow_ups/citations 等附加产出丢失
    })
  }
  // 主回答为空但有 follow_ups 时，消息被静默丢弃
}
```

**适用场景**：SSE 流式响应的 onComplete 回调；任何多产出字段的持久化决策点。
**不适用场景**：单产出字段的简单持久化；纯展示不落地的临时消息。

---

### 3.12 React render 阶段副作用禁止规范

> **复盘来源**：F-REVIEW-229——函数组件主体中 `handleSendRef.current = handleSend` 是 render 阶段副作用，违反 React 规则，StrictMode 下双重渲染会暴露问题。

| 规则 | 说明 |
|---|---|
| **render 阶段禁止写 ref** | 函数组件主体中禁止 `xxxRef.current = ...`，必须放到 `useEffect` 或事件回调中 |
| **render 阶段禁止写全局变量** | 禁止在组件主体中修改模块级 `let` 变量、`window.xxx`、`document.xxx` |
| **render 阶段禁止副作用函数调用** | 禁止在组件主体中调用 `fetch`/`localStorage.setItem`/`console.log`（调试除外） |
| **useEffect 内写 ref** | 必须用 `useEffect(() => { xxxRef.current = xxx }, [dep])` 模式 |

```typescript
// ✅ 正确：ref 写入放在 useEffect 中
function ChatPage() {
  const handleSendRef = useRef<(() => void) | null>(null)
  const handleSend = useCallback(() => {
    // 发送逻辑
  }, [deps])

  // ref 写入放在 useEffect，避免 render 阶段副作用
  useEffect(() => {
    handleSendRef.current = handleSend
  }, [handleSend])

  return <div>{/* ... */}</div>
}

// ❌ 错误：render 阶段直接写 ref
function ChatPage() {
  const handleSendRef = useRef<(() => void) | null>(null)
  const handleSend = useCallback(() => {
    // 发送逻辑
  }, [deps])

  // render 阶段写 ref：StrictMode 下双重渲染会执行两次，行为不可预测
  handleSendRef.current = handleSend

  return <div>{/* ... */}</div>
}
```

**适用场景**：所有 React 函数组件；自定义 Hook 的 render 阶段。
**不适用场景**：类组件的 `constructor`（初始化 ref 合法）；事件回调内的 ref 写入。

---

### 3.13 SSE 事件数据类型校验规范

> **复盘来源**：F-REVIEW-230——`follow_ups` 字段用 `as string[]` 强制断言，未用 zod schema/type guard 校验，运行时数据结构与声明类型不符时崩溃。

| 规则 | 说明 |
|---|---|
| **禁止 `as` 强制断言** | SSE 事件数据的 `JSON.parse` 结果禁止 `as Type`，必须用 zod schema 或 type guard 校验 |
| **zod schema 集中定义** | 所有 SSE 事件 schema 集中在 `frontend/src/api/sse-schemas.ts`，禁止散落组件内 |
| **校验失败降级** | schema 校验失败必须降级（丢弃该字段 + `console.warn`），禁止抛错中断流 |
| **schema 版本化** | schema 必须含 `version` 字段，后端 schema 变更时前端可感知 |

```typescript
// ✅ 正确：zod schema 运行时校验 + 校验失败降级
import { z } from 'zod'

// schema 集中定义在 sse-schemas.ts
const FollowUpsEventSchema = z.object({
  type: z.literal('follow_ups'),
  follow_ups: z.array(z.string()),  // 类型校验：必须是 string 数组
  version: z.string().optional(),
})

function handleSSEEvent(rawData: string): void {
  try {
    const data = JSON.parse(rawData)
    // zod 运行时校验：类型不符时抛 ZodError
    const event = FollowUpsEventSchema.parse(data)
    // 校验通过，安全使用 event.follow_ups
    renderFollowUps(event.follow_ups)
  } catch (e) {
    // 校验失败降级：丢弃该字段 + 警告，不中断流
    console.warn('SSE follow_ups 事件校验失败，跳过', e)
  }
}

// ❌ 错误：as 强制断言，运行时类型不符时崩溃
function handleSSEEventBad(rawData: string): void {
  const data = JSON.parse(rawData)
  // as 强制断言：运行时 follow_ups 可能不是数组，调用 .map 时崩溃
  const followUps = (data.follow_ups) as string[]
  followUps.forEach(q => renderQuestion(q))  // 运行时崩溃
}
```

**适用场景**：所有 SSE 事件数据解析；WebSocket 消息解析；postMessage 数据解析。
**不适用场景**：内部同源数据传递（已由 TS 类型保证）；Mock 数据。

---

### 3.14 定时器清理完整性规范

> **复盘来源**：F-REVIEW-231——`setTimeout`/`setInterval` 在组件卸载时未清理，多次触发前未清除旧定时器，导致组件卸载后仍触发状态更新。

| 规则 | 说明 |
|---|---|
| **ref 持有定时器 ID** | `setTimeout`/`setInterval` 的返回值必须存到 `useRef`，便于清理 |
| **useEffect 清理** | `useEffect` 返回的 cleanup 函数必须 `clearTimeout`/`clearInterval` 所有 ref 持有的定时器 |
| **触发前清除旧定时器** | 再次触发定时器前必须先 `clearTimeout(oldTimerRef.current)`，禁止叠加多个定时器 |
| **单测覆盖清理逻辑** | 必须有单测覆盖：组件卸载后定时器不触发；连续触发 N 次只有最后一个定时器生效 |

```typescript
// ✅ 正确：ref 持有 + useEffect 清理 + 触发前清除旧定时器
function useDebouncedSearch(query: string, delay: number): void {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    // 触发前清除旧定时器，避免叠加多个定时器
    if (timerRef.current) {
      clearTimeout(timerRef.current)
    }
    // 新定时器 ID 存到 ref
    timerRef.current = setTimeout(() => {
      doSearch(query)
    }, delay)

    // cleanup：组件卸载时清除定时器
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current)
      }
    }
  }, [query, delay])
}

// ❌ 错误：未用 ref 持有 + 无 cleanup + 触发前未清除旧定时器
function useDebouncedSearchBad(query: string, delay: number): void {
  useEffect(() => {
    // 定时器 ID 未存到 ref，无法清理
    setTimeout(() => {
      doSearch(query)
    }, delay)
    // 无 cleanup 函数，组件卸载后定时器仍触发状态更新
  }, [query, delay])
}
```

**适用场景**：所有使用 `setTimeout`/`setInterval` 的组件；轮询场景；防抖/节流。
**不适用场景**：Promise/async-await（无定时器 ID）；服务端渲染（无定时器）。

---

### 3.15 交互元素可访问性规范

> **复盘来源**：F-REVIEW-232——follow_ups 的 Tag 非原生交互元素，缺少 `tabIndex`、`role`、`onKeyDown`，键盘用户无法访问。

| 规则 | 说明 |
|---|---|
| **非原生交互元素必加三件套** | `<div>`/`<span>`/`<Tag>` 等非原生交互元素绑定 `onClick` 时，必须加 `tabIndex={0}` + `role="button"` + `onKeyDown`（处理 Enter/Space） |
| **键盘事件统一封装** | 键盘处理逻辑封装为 `useKeyboardClick(onClick)` Hook，禁止每个组件重复实现 |
| **焦点可见性** | 必须有 `:focus-visible` 样式（outline 或 box-shadow），禁止 `outline: none` 不提供替代 |
| **axe-core 单测** | 关键页面必须有 axe-core 自动化可访问性扫描单测 |

```typescript
// ✅ 正确：非原生交互元素三件套 + 键盘事件处理
function FollowUpTag({ question, onClick }: Props) {
  // 键盘事件统一处理：Enter/Space 触发点击
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onClick(question)
    }
  }
  return (
    <Tag
      tabIndex={0}              // 可聚焦
      role="button"             // 语义角色
      onKeyDown={handleKeyDown} // 键盘支持
      onClick={() => onClick(question)}
      className="cb-follow-up-tag"
    >
      {question}
    </Tag>
  )
}

// ❌ 错误：非原生交互元素无三件套，键盘用户无法访问
function FollowUpTagBad({ question, onClick }: Props) {
  return (
    <Tag onClick={() => onClick(question)}>  {/* 无 tabIndex/role/onKeyDown */}
      {question}
    </Tag>
  )
}
```

**适用场景**：所有可点击的非原生交互元素；自定义按钮/标签/卡片。
**不适用场景**：原生 `<button>`/`<a>`（已内置可访问性）；纯展示元素（无 onClick）。

---

## 四、配置规范

### 4.1 文件职责

| 文件 | 职责 | 版本控制 |
|---|---|---|
| `config/config.yaml` | 用户可改运行时配置 | ✅ |
| `config/eval.yaml` | 评估规则基线 | ✅ |
| `config/*.example.yaml` | 部署模板 | ✅ |
| `.env` | 敏感凭据 | ❌ gitignore |
| `.env.example` | 环境变量示例 | ✅ |

### 4.2 新增配置字段流程

1. **Pydantic 模型加字段** + 默认值（`src/xianyu_hunter/infra/yaml_config.py`）
2. **example.yaml 加注释**：`# 含义 + 合法值范围 + 默认值`
3. **前端 types.ts 加类型**
4. **UI 控件接入**（如 `BuyerStrategy.tsx` 的 `<InputNumber>`）
5. **测试覆盖**：单元测试 + 手动 E2E

### 4.3 敏感字段

| 字段 | 处理 |
|---|---|
| `cookie` / `cookies` / `session_id` | 写入 .env 或 keyring |
| `serverchan_key` / `pushplus_token` / `bark_key` | 写入 .env |
| **API 返回前必须 redact** | 见 `api_config.py` `_REDACT_KEYS` |

---

## 五、命名规范速查

| 类别 | 规范 | 示例 |
|---|---|---|
| Python 文件 | `snake_case.py` | `buyer_config.py` |
| Python 测试 | `test_*.py` | `test_yaml_config.py` |
| Python 类 | `PascalCase` | `EvalConfig` |
| Python 函数 | `snake_case()` | `load_all_yaml()` |
| Python 常量 | `UPPER_SNAKE` | `_REDACT_KEYS` |
| TS 文件 | `camelCase.ts` / `PascalCase.tsx` | `configApi.ts` / `BuyerStrategy.tsx` |
| TS 接口 | `PascalCase` | `AppConfig` / `DiffChange` |
| TS 函数 | `camelCase` | `extractApiError()` |
| YAML 字段 | `snake_case` | `auto_buy_score` |
| URL 路径 | `kebab-case` | `/api/config/save` |
| 数据库表 | `snake_case` 复数 | `task_records` |
| 数据库列 | `snake_case` | `created_at` |
| 文档 | `kebab-case.md` | `coding-standards.md` |

---

## 六、测试规范

| 规则 | 说明 |
|---|---|
| **测试文件命名** | `test_<被测模块>.py` |
| **测试函数命名** | `test_<场景>_<期望>`（如 `test_pass_score_gt_auto_buy_score_should_fail`） |
| **隔离 cwd** | 用 `monkeypatch.chdir(tmp_path)` 避免污染真实配置 |
| **覆盖正常 + 边界 + 异常** | 三个用例 |
| **回归测试** | 修复 Bug 时必须添加对应回归测试 |
| **运行** | `pytest tests/<file>.py -v` |

---

## 七、提交规范

- **commit message**：`type(scope): description`（如 `fix(yaml-config): use deep merge to fix parameter reset bug`）
- **修改前先读**：`Read` 工具读取完整文件，不直接 Edit
- **不要混合多个修改**：Bug 修复和功能重构分开 commit
- **敏感文件**（.env / .db / browser-data）必须 gitignore

---

## 八、不做什么（Anti-Pattern）

- ❌ 默默选择一种解释就直接开始编码
- ❌ 顺手修改旁边代码
- ❌ 硬编码路径 / 凭据 / 阈值（必须走配置）
- ❌ 命名不一致（`auto_buy_score` vs `autoBuyScore`）
- ❌ 浅合并多层配置
- ❌ catch 块写空 / 笼统提示
- ❌ 前端订阅整个 Zustand store
- ❌ 跳过测试就声称完成
- ❌ 提交时附带临时调试文件

---

## 九、参考

- [directory-structure.md](../../standards/directory-structure.md) —— 文件该放哪
- [michelin-design-system.md](../../standards/michelin-design-system.md) —— UI 视觉
- [xianyu-frontend-code-review](../xianyu-frontend-code-review/SKILL.md) —— 前端审查要点
- [xianyu-backend-code-review](../xianyu-backend-code-review/SKILL.md) —— 后端审查要点

---

## 十、合并冲突解决规范

> **教训来源**：多次大分支合并（如 codex/task-price-range-eval 合入 main）时，3 个以上文件同时冲突，旧内联代码与 main 重构 helper 产生矛盾。

### 10.1 冲突解决原则

| 原则 | 说明 | 反面教材 |
|---|---|---|
| **保留 main 重构** | main 上的 helper 提取、复杂度拆分优先保留 | 把旧内联代码拉回 main |
| **只改入口点** | 在 helper 内部加新功能，不在循环体内加逻辑 | 每个调用点重复加 PriceRange |
| **最小侵入** | 只改必要的最小范围，不顺便重构 | 改冲突文件时顺手改命名 |
| **冲突即验证** | 解决冲突后立即跑相关测试 | 全部解决后再验证 |

### 10.2 冲突解决流程

1. 用 rg 定位所有冲突块
2. 对每个冲突文件：
   a. 确定 main 版本的结构（helper 函数名、调用链）
   b. 确定 feature 版本的意图（新功能/修复）
   c. 在 main helper 内部接入 feature 逻辑
   d. 删除 feature 旧内联块
   e. 标记 git add 解决冲突
3. 语法编译验证（py_compile / tsc --noEmit）
4. 跑相关测试（不跑全量，只跑受影响模块）
5. 确认无冲突标记后提交 merge

### 10.3 常见冲突模式

| 冲突模式 | 解决策略 |
|---|---|
| 旧内联代码 vs main helper | 保留 helper，在 helper 内接入逻辑 |
| 同一函数两处修改 | 选语义更完整的版本，合并另一处改动 |
| import 顺序冲突 | 按字母序整理，不混入功能改动 |
| 编码问题（GBK vs UTF-8） | 统一用 UTF-8，PowerShell 输出用 utf-8-sig 读取 |
---

## 十一、前端构建与静态资源管理规范

> **教训来源**：vite build 超时、静态产物在 .gitignore 中、PWA 缓存导致页面不更新。

### 11.1 构建产物管理

| 规则 | 说明 |
|---|---|
| **构建产物不入库** | src/xianyu_hunter/web/static/spa/ 在 .gitignore 中 |
| **只提交源码** | 前端 TypeScript/TSX 源码提交到 Git |
| **构建后验证** | tsc --noEmit + vite build 都成功后才算前端改动完成 |

### 11.2 构建超时处理

| 场景 | 处理方式 |
|---|---|
| npm run build 超时 | 拆分为 npx tsc -b 和 npx vite build 分别跑 |
| tsc 通过但 vite 卡住 | 检查是否有死循环的 plugin 或过大的 chunk |
| 编码错误导致构建失败 | 确认文件编码为 UTF-8，PowerShell 输出用 utf-8-sig 读取 |

### 11.3 PWA 缓存处理

| 规则 | 说明 |
|---|---|
| **更新后刷新** | 页面改动后提示用户 Ctrl+F5 强制刷新 |
| **SW 管理** | DevTools -> Application -> Service Workers -> unregister |
| **版本感知** | vite-plugin-pwa 自动处理版本更新提示 |
---

## 十二、选择性暂存与提交规范

> **教训来源**：工作区有多个未提交改动时，git add . 会把不相关的内容也暂存。

### 12.1 选择性暂存

| 场景 | 做法 |
|---|---|
| 只提交本次改动 | git add <specific-file1> <specific-file2> |
| 避免混入无关改动 | 提交前 git diff --cached --stat 确认范围 |
| 多人协作时 | 只暂存自己的文件，不碰他人的未提交改动 |

### 12.2 提交前检查清单

1. git diff --cached --name-only - 确认只包含预期文件
2. git diff --cached --stat - 确认改动量合理
3. git diff --cached -U0 - 快速浏览变更行
4. 确认无临时文件/调试输出/无关修改
5. 确认无敏感信息泄露（key/token/password）
---

## 十三、PowerShell 编码与命令执行规范

> **教训来源**：PowerShell 默认 GBK 编码导致 UTF-8 文件读取失败、特殊字符编码错误。

### 13.1 文件读取

| 规则 | 示例 |
|---|---|
| **用 utf-8-sig 读取** | io.open(path, r, encoding=utf-8-sig) |
| **避免直接 print 中文** | sys.stdout.reconfigure(encoding=utf-8) |
| **超大文件分段读取** | 只读前 N 行，避免内存溢出 |

### 13.2 命令执行

| 规则 | 示例 |
|---|---|
| **PowerShell 路径分隔符** | 用 \\ 或 /，不用 \ |
| **stash@{0} 加引号** | git stash pop stash@{0} |
| **超时设置** | 长时间命令设 timeout_ms，避免无限等待 |
---

## 十四、任务级价格区间评分可视化规范

> **教训来源**：后端新增价格区间评分逻辑后，前端评估规则页面没有展示新规则说明，用户看不到新增的梯度评分规则。

### 14.1 规则页面同步

| 规则 | 说明 |
|---|---|
| **后端逻辑变更需前端同步** | 任何评估逻辑变更，必须在评估规则页面有对应说明 |
| **只读规则展示** | 规则说明用只读卡片（Table + Alert），不一定要做成可编辑控件 |
| **示例数据** | 用具体数值示例（如 600-800 元）帮助用户理解抽象规则 |
| **配置来源标注** | 明确标注规则数据来源（任务配置 vs 全局配置） |

### 14.2 前端规则卡片模板

Card(title=<Space><DollarCircleOutlined />任务价格区间梯度评分</Space>)
  Alert(type=info, message=价格维度会读取每个任务的 min_price / max_price)
  Table(dataSource=gradientRules, columns=[
    { title: 价格区间, dataIndex: range },
    { title: 评分含义, dataIndex: label },
    { title: 价格分调整, dataIndex: score }
  ])
  div(fontSize: 12, 区间中段优先，靠近上下边缘轻扣分)

### 14.3 验证清单

| 检查项 | 说明 |
|---|---|
| **规则可见性** | 新规则是否在评估规则页面展示？ |
| **示例准确性** | 示例数值是否与后端逻辑一致？ |
| **配置来源** | 是否标注了规则来自任务级配置？ |
| **构建通过** | tsc --noEmit + vite build 都通过？ |
| **PWA 刷新** | 提示用户强制刷新或 unregister SW？ |