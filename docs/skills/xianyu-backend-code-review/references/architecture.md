# 后端分层架构审查（Architecture）

> **配套技能**：[xianyu-backend-code-review](../SKILL.md)
> **范围**：项目分层 / 依赖方向 / 模块职责

---

## 1. 项目分层架构

```
src/xianyu_hunter/
├── domain/           # 领域模型（纯数据类，无副作用）
├── infra/            # 基础设施（DB、浏览器、日志、配置、密钥、仓储）
├── modules/          # 业务模块（collector / buyer / evaluator / notifier）
└── web/              # Web 层
    ├── routes/       # FastAPI 路由（api_*.py）
    ├── services/     # Web 服务层
    ├── templates/    # Jinja2 模板
    ├── static/       # 静态资源
    └── middleware/   # 中间件
```

---

## 2. 依赖方向（铁律）

### 2.1 单向依赖图

```
web/      →  modules/  →  infra/  →  domain/
   ↓            ↓            ↓
   └────────────┴────────────┴→  domain/
```

### 2.2 规则

| 层 | 允许依赖 | 禁止依赖 |
|---|---|---|
| `domain/` | （无依赖，标准库除外） | infra / modules / web |
| `infra/` | domain / 标准库 / 第三方 | modules / web |
| `modules/` | domain / infra / 标准库 / 第三方 | web |
| `web/` | 全部下层 | （无禁止） |
| `tests/` | 全部 | （无禁止） |

### 2.3 检测方法

```python
# ❌ 反例：domain 依赖 infra
# src/xianyu_hunter/domain/item.py
from xianyu_hunter.infra.db import async_session  # ❌ 违反

# ❌ 反例：infra 依赖 modules
# src/xianyu_hunter/infra/repo_items.py
from xianyu_hunter.modules.evaluator import evaluate  # ❌ 违反
```

```bash
# 检测 import 违规
mypy src/xianyu_hunter/ --strict
# 或自定义 importlinter 配置
```

---

## 3. 模块职责

### 3.1 domain/ - 领域模型

**职责**：纯数据类，**无副作用**。

```python
# ✅ 正确：纯 dataclass
from dataclasses import dataclass

@dataclass
class Item:
    item_id: str
    title: str
    price: float
    seller_id: str
```

**禁止**：
- ❌ import `infra/` / `modules/` / `web/`
- ❌ 数据库查询
- ❌ 外部 API 调用
- ❌ 业务逻辑（应该放 modules）

### 3.2 infra/ - 基础设施

**职责**：提供技术能力（DB / 浏览器 / 配置 / 密钥 / 仓储）。

| 子模块 | 职责 |
|---|---|
| `infra/db.py` | SQLAlchemy session / engine 创建 |
| `infra/yaml_config.py` | YAML 配置加载 + AppConfig 模型 |
| `infra/browser.py` | Playwright 浏览器管理 |
| `infra/logger.py` | loguru logger 配置 |
| `infra/secret.py` | 密钥管理（keyring） |
| `infra/repo_*.py` | 仓储（数据访问） |
| `infra/container.py` | 依赖注入容器 |

**仓储规范**：

```python
# infra/repo_items.py
class ItemRepository:
    async def list_recent(self, limit: int = 50) -> list[ItemDTO]:
        """返回 Pydantic / dataclass，不返回 ORM 对象"""
        ...

    async def get_by_id(self, item_id: str) -> ItemDTO | None:
        ...

    async def upsert(self, item: ItemDTO) -> None:
        ...
```

### 3.3 modules/ - 业务模块

**职责**：实现具体业务功能。

| 模块 | 职责 |
|---|---|
| `modules/collector.py` | 商品采集 |
| `modules/evaluator.py` | 卖家评估 |
| `modules/buyer.py` | 抢单逻辑 |
| `modules/worker.py` | 任务执行 |
| `modules/notifier.py` | 通知发送 |
| `modules/price_strategy.py` | 价格策略 |

**业务模块特点**：
- 协调多个 infra 能力（DB + 浏览器 + 配置）
- 持有业务状态机
- 通过 `container.py` 获取依赖

```python
# modules/buyer.py
class BuyerService:
    def __init__(self, config: AppConfig, repo: OrderRepository):
        self.config = config
        self.repo = repo

    async def should_auto_buy(self, item: Item) -> bool:
        score = evaluate(item, self.config.eval)
        return score >= self.config.eval.auto_buy_score
```

### 3.4 web/ - Web 层

**职责**：HTTP 接口 / 模板 / 静态资源。

```python
# web/routes/api_buyer.py
from fastapi import APIRouter, Depends
from xianyu_hunter.modules.buyer import BuyerService
from xianyu_hunter.container import get_buyer_service

router = APIRouter()

@router.post("/buy/{item_id}")
async def buy_item(
    item_id: str,
    service: BuyerService = Depends(get_buyer_service)
):
    """路由只做编排，业务在 service"""
    result = await service.buy(item_id)
    return result
```

---

## 4. 跨层数据流

### 4.1 完整调用链

```
HTTP Request
    ↓
web/routes/api_*.py  ← 编排（参数解析、调用 service、错误处理）
    ↓
modules/<feature>.py ← 业务逻辑（协调 infra 资源）
    ↓
infra/repo_*.py  ← 数据访问（ORM 操作）
    ↓
domain/<model>.py ← 数据模型
```

### 4.2 关键检查点

| 检查点 | 说明 |
|---|---|
| 路由不直接 DB | `web/routes/` 不能 `import async_session` |
| 路由不写业务 | 路由函数 ≤ 10 行，只做编排 |
| 仓储返回模型 | 返回 dataclass / Pydantic，不返回 ORM |
| 配置走 `get_config()` | 各模块统一从 `infra/yaml_config.get_config()` 读 |
| 业务异常上抛 | 模块抛业务异常，由路由层转为 HTTPException |

---

## 5. 依赖注入

### 5.1 container.py 模式

```python
# infra/container.py
from functools import lru_cache
from xianyu_hunter.modules.buyer import BuyerService
from xianyu_hunter.infra.repo_orders import OrderRepository

@lru_cache
def get_order_repository() -> OrderRepository:
    return OrderRepository()

@lru_cache
def get_buyer_service() -> BuyerService:
    return BuyerService(
        config=get_config(),
        repo=get_order_repository()
    )
```

### 5.2 路由使用

```python
# web/routes/api_buyer.py
from xianyu_hunter.container import get_buyer_service

@router.post("/buy/{item_id}")
async def buy_item(
    item_id: str,
    service: BuyerService = Depends(get_buyer_service)
):
    return await service.buy(item_id)
```

### 5.3 单元测试 mock

```python
def test_buyer_service():
    mock_repo = Mock(OrderRepository)
    service = BuyerService(config=mock_config, repo=mock_repo)
    # 测试业务逻辑
```

---

## 6. 错误传播

### 6.1 分层错误处理

```python
# 1) infra 层：抛底层异常
class ItemRepository:
    async def get_by_id(self, item_id: str) -> ItemDTO:
        async with async_session() as session:
            item = await session.get(ItemORM, item_id)
            if not item:
                raise ItemNotFoundError(item_id)  # 自定义异常
            return ItemDTO.model_validate(item)

# 2) modules 层：捕获并转为业务异常
class BuyerService:
    async def buy(self, item_id: str) -> OrderDTO:
        try:
            item = await self.repo.get_by_id(item_id)
        except ItemNotFoundError:
            raise  # 直接上抛

# 3) web 层：转为 HTTP 响应
@router.post("/buy/{item_id}")
async def buy_item(item_id: str):
    try:
        return await service.buy(item_id)
    except ItemNotFoundError:
        raise HTTPException(404, detail="商品不存在")
```

### 6.2 统一异常处理中间件

```python
# web/middleware/exception_handler.py
@app.exception_handler(ValidationError)
async def handle_validation(request, exc):
    return JSONResponse(
        status_code=400,
        content={"detail": {"message": "参数校验失败", "errors": exc.errors()}}
    )

@app.exception_handler(ItemNotFoundError)
async def handle_not_found(request, exc):
    return JSONResponse(status_code=404, content={"detail": str(exc)})
```

---

## 7. 常见反模式

| 反模式 | 问题 | 修复 |
|---|---|---|
| 路由直接 `session.execute(...)` | 路由臃肿，难测试 | 移到 `repo_*.py` |
| 业务写在路由函数 | 业务无法复用，难测 | 提取到 `modules/` |
| `domain/` 中 import `infra/` | 循环依赖，难测试 | domain 保持纯净 |
| 仓储返回 ORM 对象 | 上层耦合 ORM，难换实现 | 返回 dataclass / Pydantic |
| 业务模块跨层调路由 | 循环依赖 | 业务通过 service 调用 |
| 全局单例遍布各模块 | 难测试 | 走 `container.py` 注入 |
| 路由导入具体 service 实现 | 难换实现 | 走 `Depends(get_xxx)` |

---

## 8. 审查 checklist

| 类别 | 检查项 |
|---|---|
| 依赖方向 | 严格单向？无循环？ |
| 模块职责 | domain 纯净？infra 不含业务？modules 不含路由？ |
| 路由 | ≤ 10 行？无 DB / 业务？ |
| 业务模块 | 通过 container 拿依赖？ |
| 仓储 | 返回模型？方法命名规范？ |
| 错误传播 | 分层处理？统一异常处理？ |

---

## 9. 复盘：从对话中提炼

### 9.1 案例：抢单策略保存 Bug 涉及的层

- **domain**：`EvalConfig` 模型（Pydantic 校验 `pass_score <= auto_buy_score`）
- **infra**：`yaml_config.py` 加载 + 合并（深度合并修复 Bug 在这层）
- **modules**：无直接修改，但 `buyer.py` 通过 `get_config()` 实时读取
- **web**：`api_config.py` 保存端点（深度合并 + reload_config）

**层间职责清晰**，Bug 修复定位到 `infra/yaml_config._load_all`，**未越层**。

### 9.2 案例：前端错误处理 Bug（涉及 web 层）

`api_config.py` 校验失败已返回 `detail.message` + `detail.errors`（结构化错误），
但前端 `catch` 块没解析，**层级职责清晰**但**前后端契约未对齐**。

**预防**：后端文档化错误响应 schema，前端按 schema 解析。

---

## 10. 参考

- [Clean Architecture（Robert C. Martin）](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Domain-Driven Design](https://martinfowler.com/bliki/DomainDrivenDesign.html)
- [项目分层架构总入口](../../xianyu-hunter-dev/SKILL.md#3-项目结构速查)
- [FastAPI 依赖注入](https://fastapi.tiangolo.com/tutorial/dependencies/)

---

## 十一、数据删除完整性检查

### 11.1 审查规则

| 规则 | 说明 |
|---|---|
| **删除前检查关联** | 有外键引用的表删除前必须处理关联数据 |
| **关联策略可配置** | `TABLE_RELATIONS` 定义级联/置空策略，不硬编码在业务逻辑中 |
| **级联预览** | 提供只读预览 API，让用户确认影响范围 |
| **事务原子性** | 级联操作与主表删除在同一事务中 |
| **审计日志** | 级联详情（受影响表+行数）写入审计日志 |

### 11.2 完整性检查流程

```
删除请求 → 校验 confirm_token
         → 查询 TABLE_RELATIONS 获取关联表
         → （可选）级联预览 API 返回影响范围
         → engine.begin() 事务中：
              1. 先执行级联（cascade DELETE / set_null UPDATE）
              2. 再删除主表记录
         → 记录审计日志（含级联详情）
         → 返回结果（含 cascade 受影响行数）
```

### 11.3 防止孤立记录

| 场景 | 错误做法 | 正确做法 |
|---|---|---|
| 删 tasks | 直接 DELETE FROM tasks | 先级联删 items/orders/events |
| 删 sellers | DELETE FROM sellers | UPDATE items SET seller_id=NULL |
| 删叶子表 | 直接删除 | 无需级联，直接删除 |

---

## 十二、审计日志与操作追溯

### 12.1 审查规则

| 规则 | 说明 |
|---|---|
| **DML 必须审计** | 所有 create/update/delete 操作写入 events 表 |
| **type 前缀** | `db_admin.{action}`（如 `db_admin.delete`） |
| **level 规则** | create/update=info, delete=warn, 失败=err |
| **payload 含详情** | action + table + pk + cascade 详情 |
| **审计失败不阻塞** | `_log_audit` 用 try/except 包裹，审计日志不应阻塞主流程 |

### 12.2 正确模式

```python
def _log_audit(container, action, table, *, pk_value=None, detail=None, level="info"):
    try:
        container.repo.save_event({
            "type": f"db_admin.{action}",
            "level": level,
            "message": f"db_admin.{action} {table}" + (f" pk={pk_value}" if pk_value else ""),
            "payload": json.dumps({"action": action, "table": table, "detail": detail or {}}, default=str),
        })
    except Exception:
        logger.exception("写入审计日志失败")
```
