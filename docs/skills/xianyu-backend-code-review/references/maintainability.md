# 后端可维护性审查（Maintainability）

> **配套技能**：[xianyu-backend-code-review](../SKILL.md)
> **范围**：命名 / 注释 / 函数设计 / 测试 / 重构

---

## 1. 命名规范（MN-04）

### 1.1 项目规范

| 类型 | 规范 | 示例 |
|---|---|---|
| 模块 | `snake_case.py` | `buyer_config.py` |
| 类 | `PascalCase` | `BuyerService` |
| 函数 | `snake_case()` | `load_all_yaml()` |
| 变量 | `snake_case` | `auto_buy_score` |
| 常量 | `UPPER_SNAKE_CASE` | `MAX_RETRY_COUNT` |
| 私有 | `_` 前缀 | `_load_all()` |
| 类型变量 | `PascalCase` | `T`, `ItemT` |
| 异常 | `Error` 后缀 | `ItemNotFoundError` |
| 抽象类 | `Base` 前缀 | `BaseRepository` |
| Mixin | `Mixin` 后缀 | `LogMixin` |
| 协议 | `Protocol` 后缀 | `StorageProtocol` |

### 1.2 命名原则

| 原则 | 说明 |
|---|---|
| 描述意图 | `process_payment` 而非 `do_work` |
| 避免缩写 | `evaluate` 而非 `eval`（除非是公认缩写） |
| 避免魔法词 | 不用 `data` / `info` / `item`（除非泛指） |
| 布尔值用 is_/has_/can_ | `is_active`, `has_permission` |
| 集合用复数 | `items`, `users` |
| 计数用 _count | `retry_count`, `error_count` |

---

## 2. 注释规范（MN-05）

### 2.1 解释 why，不解释 what

```python
# ❌ 解释 what
# 加载配置
def _load_all():
    data = {}
    data.update(load_yaml("config/config.yaml"))
    return AppConfig.model_validate(data)

# ✅ 解释 why
def _load_all():
    """合并 config/*.yaml，深度合并避免 eval.yaml 整体覆盖。

    旧实现用 data.update() 浅合并，导致用户在 config.yaml 修改的
    pass_score 被 eval.yaml 默认值覆盖。修复后子配置先加载作基线，
    主配置后加载做覆盖，同名字段细分 key 也被正确合并。
    """
    data = {}
    for name in ("eval.yaml", "notifier.yaml", "browser.yaml"):
        section_data = load_yaml(base / name)
        if section_data:
            _deep_merge_yaml(data, section_data)
    main_data = load_yaml(base / "config.yaml")
    if main_data:
        _deep_merge_yaml(data, main_data)
    return AppConfig.model_validate(data)
```

### 2.2 公开 API 必有 docstring

```python
def get_config() -> AppConfig:
    """获取应用配置（lru_cache 单例）。

    Returns:
        AppConfig: 合并 config/*.yaml 后的配置对象。

    Raises:
        ValidationError: 配置校验失败时。

    Note:
        修改配置后必须调用 reload_config() 失效缓存。
    """
    return _load_all()
```

### 2.3 TODO 规范

```python
# TODO(author): 描述问题
#   触发条件：[具体场景]
#   临时方案：[当前实现]
#   计划修复：[未来方案]
#   issue: #123
```

### 2.4 不要注释的

- ❌ 显而易见的代码（`x = x + 1  # x 加 1`）
- ❌ 修改前删除（注释掉的代码块）
- ❌ 不准确的注释（误导比没有更糟）

---

## 3. 函数设计（MN-01 / MN-02 / MN-03）

### 3.1 单一职责（SRP）

```python
# ❌ 函数做太多事
def process_order(order):
    validate(order)
    save_to_db(order)
    send_email(order)
    update_inventory(order)
    log(order)

# ✅ 拆分
def process_order(order):
    validate(order)
    save_to_db(order)
    notify(order)

def notify(order):
    send_email(order)
    update_inventory(order)
    log(order)
```

### 3.2 函数长度

```python
# ❌ 100+ 行函数
def huge_function():
    # ... 100 行

# ✅ 拆分为多个小函数
def step_one(): ...
def step_two(): ...

def orchestrate():
    a = step_one()
    b = step_two(a)
    return combine(a, b)
```

### 3.3 参数控制（≤4 个）

```python
# ❌ 5+ 个参数
def create_user(name, age, email, phone, address, role):
    ...

# ✅ 用 dataclass
@dataclass
class UserCreate:
    name: str
    age: int
    email: str
    phone: str
    address: str
    role: str

def create_user(data: UserCreate):
    ...
```

### 3.4 返回类型一致

```python
# ❌ 多种返回类型
def get_item(id) -> Item | None | list[Item]:
    if id is None:
        return []
    return ...

# ✅ 明确返回类型
def get_item(id) -> Item | None: ...
def list_items() -> list[Item]: ...
```

---

## 4. 类设计

### 4.1 抽象基类

```python
from abc import ABC, abstractmethod

class BaseRepository(ABC):
    @abstractmethod
    async def get_by_id(self, id: str): ...

    @abstractmethod
    async def list_all(self): ...

class ItemRepository(BaseRepository):
    async def get_by_id(self, id: str) -> ItemDTO | None:
        ...
```

### 4.2 dataclass vs Pydantic

| 场景 | 用 |
|---|---|
| 纯数据 + 内部传递 | `dataclass` |
| API 边界 / 配置 / 校验 | `Pydantic BaseModel` |
| 不可变值 | `frozen=True` dataclass |
| ORM 模型 | SQLAlchemy declarative |

### 4.3 依赖注入

```python
# ✅ 通过构造函数注入
class BuyerService:
    def __init__(
        self,
        config: AppConfig,
        repo: OrderRepository,
        notifier: NotifierService,
    ):
        self.config = config
        self.repo = repo
        self.notifier = notifier

# 测试时 mock
def test_buyer():
    service = BuyerService(
        config=mock_config,
        repo=Mock(),
        notifier=Mock(),
    )
```

---

## 5. 错误处理（MN-09）

### 5.1 自定义异常

```python
# ✅ 业务异常层次
class XianyuError(Exception):
    """基础异常"""

class ConfigError(XianyuError):
    """配置相关错误"""

class ConfigValidationError(ConfigError):
    """配置校验失败"""
    def __init__(self, message: str, errors: list[dict]):
        super().__init__(message)
        self.errors = errors

# 抛出
raise ConfigValidationError("配置校验失败", errors=pydantic_errors)

# 捕获
try:
    validate_config(cfg)
except ConfigValidationError as e:
    logger.error(f"配置错误: {e.message}, 详情: {e.errors}")
```

### 5.2 异常不要吞

```python
# ❌ 吞错
try:
    await api.save()
except Exception:
    pass

# ❌ 吞错只记录
try:
    await api.save()
except Exception as e:
    print(e)  # 用户看不到

# ✅ 记录 + 处理
try:
    await api.save()
except Exception as e:
    logger.exception("保存失败")
    raise  # 重新抛出 / 转为业务异常

# ✅ 记录 + 降级
try:
    result = await optional_api.fetch()
except Exception as e:
    logger.warning(f"可选 API 失败: {e}, 使用默认值")
    result = default_value
```

### 5.3 异常信息

```python
# ❌ 无意义
raise ValueError("error")

# ✅ 具体可读
raise ValueError(
    f"配置项 {key} 值 {value} 超出范围 [{min_value}, {max_value}]"
)
```

---

## 6. 类型注解

### 6.1 必须标注

```python
# ✅ 完整标注
def calc_score(
    weights: EvalWeights,
    metrics: ItemMetrics,
    *,
    strict: bool = False,
) -> float:
    ...
```

### 6.2 复杂类型

```python
from typing import TypeAlias, TypeVar

T = TypeVar("T")

# 别名
ItemList: TypeAlias = list[Item]
Callback: TypeAlias = Callable[[Result], None]

# 泛型
class Repository(Generic[T]):
    def get_by_id(self, id: str) -> T | None: ...
```

### 6.3 避免 Any

```python
# ❌ 滥用 Any
def process(data: Any) -> Any:
    return data["field"]  # 无类型检查

# ✅ 用 union / generic
def process(data: dict[str, str]) -> str:
    return data["field"]
```

---

## 7. 测试（MN-11）

### 7.1 测试覆盖

每个模块 / 函数必须有：
- 正常路径测试
- 边界条件（空 / 极大极小值 / null）
- 异常路径（错误输入 / 异常抛出）

### 7.2 测试结构

```python
# tests/test_buyer_service.py
import pytest
from xianyu_hunter.modules.buyer import BuyerService

@pytest.fixture
def service():
    return BuyerService(
        config=mock_config,
        repo=Mock(),
        notifier=Mock(),
    )

class TestShouldAutoBuy:
    def test_high_score_should_buy(self, service):
        """分数高于阈值应该自动买"""
        item = make_item(score=85)
        assert service.should_auto_buy(item) is True

    def test_low_score_should_not_buy(self, service):
        item = make_item(score=50)
        assert service.should_auto_buy(item) is False

    def test_threshold_boundary(self, service):
        """刚好等于阈值"""
        item = make_item(score=service.config.eval.auto_buy_score)
        assert service.should_auto_buy(item) is True
```

### 7.3 Mock 依赖

```python
from unittest.mock import Mock, AsyncMock, patch

def test_with_mock_repo():
    mock_repo = Mock()
    mock_repo.get_by_id = AsyncMock(return_value=make_item_dto())
    service = BuyerService(config=mock_config, repo=mock_repo)
    result = await service.buy("item-1")
    mock_repo.get_by_id.assert_awaited_once_with("item-1")
```

### 7.4 集成测试

```python
@pytest.mark.asyncio
async def test_save_and_reload_config(tmp_path, monkeypatch):
    """保存配置后能重新加载。"""
    monkeypatch.chdir(tmp_path)
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    (cfg_dir / "config.yaml").write_text("eval:\n  pass_score: 50\n")
    (cfg_dir / "eval.yaml").write_text("eval:\n  pass_score: 60\n  auto_buy_score: 80\n  weights: {}\n  thresholds: {}\n")

    cfg = get_config()
    assert cfg.eval.pass_score == 50  # config.yaml 覆盖
```

---

## 8. 日志（MN-10）

### 8.1 关键路径必记

```python
# ✅ 业务关键节点
logger.info("任务开始 task_id={} mode={}", task_id, mode)
logger.info("评估完成 item_id={} score={}", item_id, score)
logger.info("抢单成功 order_id={}", order_id)

# 异常
logger.exception("抢单失败 task_id={}", task_id)
```

### 8.2 日志级别

| 级别 | 用途 | 示例 |
|---|---|---|
| DEBUG | 调试信息（生产关） | `logger.debug("进入函数 X，参数={}", args)` |
| INFO | 业务关键节点 | 任务开始 / 结束 |
| WARNING | 可恢复异常 / 降级 | API 失败用默认值 |
| ERROR | 需人工介入的失败 | 配置加载失败 |
| EXCEPTION | 带堆栈的异常 | 业务异常 |

### 8.3 不记录敏感

```python
# ❌ 记录 cookie
logger.info("用户登录 cookie={}", cookie)

# ✅ 脱敏
logger.info("用户登录 cookie={}", mask(cookie))
```

---

## 9. 常见反模式

| 反模式 | 维护性问题 | 修复 |
|---|---|---|
| 100+ 行函数 | 难读难测 | 拆分小函数 |
| 5+ 个参数 | 调用混乱 | dataclass |
| 命名 `data` / `info` | 含义不明 | 具体命名 |
| 注释解释 what | 冗余 | 删 or 解释 why |
| 注释掉的代码 | 误导 | 删 |
| `except: pass` | 错误吞 | 记录 + 处理 |
| 滥用 Any | 类型失效 | 完整标注 |
| 无 docstring | API 难用 | 补 docstring |
| 业务逻辑无日志 | 出问题难排查 | 关键路径 INFO |
| 记录敏感 | 安全风险 | 脱敏 |
| 硬编码路径 | 难部署 | 配置驱动 |
| magic number | 含义不清 | 提取常量 |
| 全局单例遍布 | 难测试 | 依赖注入 |

---

## 10. 审查 checklist

| 类别 | 检查项 |
|---|---|
| 命名 | snake_case / PascalCase 规范？描述意图？ |
| 注释 | 解释 why？无过时注释？无冗余注释？ |
| 函数 | ≤ 50 行？≤ 4 个参数？SRP？ |
| 类 | 抽象基类？依赖注入？类型标注？ |
| 错误处理 | 不吞错？异常信息清晰？ |
| 类型 | 无 Any？union 明确？ |
| 测试 | 正常 + 边界 + 异常？Mock 依赖？ |
| 日志 | 关键路径 INFO？不记录敏感？ |
| 配置 | 无硬编码？走配置？ |

---

## 11. 复盘：从对话中提炼

### 11.1 案例：`_load_all` 文档化（MN-06）

修复前 `_load_all` 无 docstring，看不出加载顺序的重要性。

**修复后**：
```python
def _load_all() -> AppConfig:
    """合并 config/*.yaml 全部内容。

    加载顺序与合并策略：
    1. 子配置（eval.yaml 等）先加载作默认基线
    2. config.yaml 最后加载做覆盖
    3. 深度合并避免顶层整体替换

    为什么不：data.update() 浅合并会让 eval.yaml 整体覆盖 config.yaml。
    """
```

**意义**：后人维护时一眼看出为什么这样写，**避免回归 Bug**。

### 11.2 案例：save 路径缺少注释（MN-05）

保存端点的合并逻辑必须与加载一致。如果不注释，后人可能改其中一处导致不一致。

**预防**：在两个端点都加注释"必须保持与 _load_all 一致"。

---

## 12. 参考

- [PEP 8 风格指南](https://peps.python.org/pep-0008/)
- [PEP 257 docstring](https://peps.python.org/pep-0257/)
- [Refactoring（Fowler）](https://refactoring.com/)
- [Clean Code](https://www.oreilly.com/library/view/clean-code-a/9780136083238/)
- [项目编码规范总入口](../../xianyu-hunter-dev/references/coding-standards.md)
