# 商品已售状态检测与信息刷新 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 抢单过程中两阶段检测商品已售并标记，新增商品刷新接口供链接点击/官方采集触发，统一更新 items 表 + task_links.display 的销售状态。

**Architecture:** items 表新增 `is_sold` 字段（复用 `_migrate_add_column` 机制）；buyer.py 增加两阶段已售检测（导航后 + 提交订单失败后回退）；新增 `POST /api/items/{item_id}/refresh` 接口调用 collector.detail() 采集并更新；官方采集流程同步 is_sold；前端链接点击改为异步刷新 + 跳转。

**Tech Stack:** Python + FastAPI + SQLAlchemy (SQLite) + Playwright；前端 React + TypeScript + Ant Design

**关联设计文档:** [2026-06-26-item-sold-status-detection-design.md](file:///d:/code/otherProjects/17_xianyu/docs/plans/2026-06-26-item-sold-status-detection-design.md)

---

## 文件结构

| 文件 | 职责 | 操作 |
|------|------|------|
| `src/xianyu_hunter/infra/db_models.py` | ItemRow ORM 模型 + init_db 迁移 | 修改 |
| `src/xianyu_hunter/infra/repo_items.py` | items 表 mark_sold 方法 | 修改 |
| `src/xianyu_hunter/infra/repo_links.py` | task_links.display.is_sold 同步 | 修改 |
| `src/xianyu_hunter/domain/order.py` | ItemSoldError 异常 | 修改 |
| `src/xianyu_hunter/modules/buyer.py` | 两阶段已售检测 + 标记 | 修改 |
| `src/xianyu_hunter/modules/collector/_detail.py` | detail() 增加已售检测 | 修改 |
| `src/xianyu_hunter/web/routes/api_items.py` | POST /api/items/{id}/refresh | 修改 |
| `src/xianyu_hunter/web/routes/api_orders.py` | manual_takeover 捕获 ItemSoldError | 修改 |
| `src/xianyu_hunter/web/routes/api_evaluations.py` | 官方采集同步 is_sold | 修改 |
| `frontend/src/api/item.ts` | refresh 方法 | 修改 |
| `frontend/src/pages/Items/ItemList.tsx` | 链接点击异步刷新 | 修改 |
| `tests/test_item_sold_status.py` | repo 层单元测试 | 新建 |

---

### Task 1: 数据模型与迁移

**Files:**
- Modify: `src/xianyu_hunter/infra/db_models.py:71-96`（ItemRow）、`src/xianyu_hunter/infra/db_models.py:357-379`（init_db）

- [ ] **Step 1: ItemRow 新增字段**

在 `src/xianyu_hunter/infra/db_models.py` 的 `ItemRow` 类（行 96 `last_seen` 之后）新增：

```python
    # 销售状态：0=在售，1=已售。由 buyer/collector 检测写入
    is_sold: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 检测到已售的时间戳（ISO 格式），便于排查检测来源
    sold_detected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

- [ ] **Step 2: init_db 增量迁移**

在 `init_db` 函数（行 363 `_migrate_add_column(engine, "tasks", "max_publish_days", "INTEGER")` 之后）新增：

```python
    # 增量迁移：items 表新增销售状态字段（buyer/collector 检测写入）
    _migrate_add_column(engine, "items", "is_sold", "INTEGER")
    _migrate_add_column(engine, "items", "sold_detected_at", "TEXT")
```

- [ ] **Step 3: 验证迁移**

Run: `python -c "from xianyu_hunter.infra.db_models import init_db; init_db('data/xianyu.db'); print('migration ok')"`

Expected: 输出 `migration ok`，不报错。检查 `data/xianyu.db` 中 items 表已有 is_sold 列：

Run: `python -c "import sqlite3; c=sqlite3.connect('data/xianyu.db'); print([r[1] for r in c.execute('PRAGMA table_info(items)').fetchall()])"`

Expected: 列表中包含 `is_sold` 和 `sold_detected_at`

- [ ] **Step 4: Commit**

```bash
git add src/xianyu_hunter/infra/db_models.py
git commit -m "feat(db): items 表新增 is_sold + sold_detected_at 字段"
```

---

### Task 2: Repository 层 - mark_sold + display 同步

**Files:**
- Modify: `src/xianyu_hunter/infra/repo_items.py`（ItemsMixin 新增 mark_sold）
- Modify: `src/xianyu_hunter/infra/repo_links.py`（新增 update_link_display_sold）
- Test: `tests/test_item_sold_status.py`（新建）

- [ ] **Step 1: 编写 mark_sold 失败测试**

新建 `tests/test_item_sold_status.py`：

```python
"""商品已售状态检测与信息刷新 - Repository 层测试"""
import tempfile
from pathlib import Path

from xianyu_hunter.infra.repository import Repository


def _new_repo() -> Repository:
    """创建临时数据库的 Repository"""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    return Repository(db_path=tmp.name)


def test_mark_sold_updates_item():
    repo = _new_repo()
    repo.upsert_item({
        "id": "item_001",
        "task_id": "t1",
        "title": "测试商品",
        "price": 100.0,
    })
    # 初始状态：未售
    assert repo.get_item("item_001").get("is_sold") == 0

    repo.mark_sold("item_001")

    item = repo.get_item("item_001")
    assert item["is_sold"] == 1
    assert item["sold_detected_at"] is not None


def test_mark_sold_syncs_task_link_display():
    repo = _new_repo()
    repo.upsert_item({"id": "item_002", "task_id": "t2", "title": "测试", "price": 50.0})
    # 先建立 task_links.display（含 is_sold=False）
    repo.upsert_task_link("t2", "item", "item_002", display={
        "title": "测试", "price": 50.0, "is_sold": False, "url": "https://example.com"
    })
    repo.mark_sold("item_002")

    links = repo.lookup_task_links("item", "item_002")
    assert links, "task_link 不存在"
    display = links[0].get("display") or {}
    if isinstance(display, str):
        import json
        display = json.loads(display)
    assert display.get("is_sold") is True
```

- [ ] **Step 2: 运行测试验证失败**

Run: `python -m pytest tests/test_item_sold_status.py -v`

Expected: FAIL with `AttributeError: 'Repository' object has no attribute 'mark_sold'`

- [ ] **Step 3: 实现 repo_items.mark_sold**

在 `src/xianyu_hunter/infra/repo_items.py` 的 `ItemsMixin` 类末尾（行 118 `delete_items_by_task` 之后）新增：

```python
    def mark_sold(self, item_id: str) -> None:
        """标记商品为已售出，同步更新 items 表 + task_links.display

        为什么同步 task_links：前端列表读 task_links.display.is_sold，
        DB 模式下旧数据缺失该字段会导致显示"在售"，需同步修正。
        """
        from xianyu_hunter.infra.db_models import _utcnow
        now = _utcnow()
        # 1. 更新 items 表
        with self.engine.begin() as conn:
            conn.execute(
                ItemRow.__table__.update()
                .where(ItemRow.id == item_id)
                .values(is_sold=1, sold_detected_at=now)
            )
        # 2. 同步 task_links.display.is_sold
        links = self.lookup_task_links("item", item_id)
        for link in links:
            display = link.get("display")
            if isinstance(display, str):
                import json
                display = json.loads(display) if display else {}
            elif display is None:
                display = {}
            display["is_sold"] = True
            self.upsert_task_link(
                task_id=link["task_id"],
                link_type="item",
                link_key=item_id,
                display=display,
            )
```

- [ ] **Step 4: 运行测试验证通过**

Run: `python -m pytest tests/test_item_sold_status.py -v`

Expected: PASS（2 tests passed）

- [ ] **Step 5: Commit**

```bash
git add src/xianyu_hunter/infra/repo_items.py tests/test_item_sold_status.py
git commit -m "feat(repo): 新增 mark_sold 同步更新 items + task_links 销售状态"
```

---

### Task 3: 领域异常 ItemSoldError

**Files:**
- Modify: `src/xianyu_hunter/domain/order.py:71-73`（ButtonNotFoundError 之后）

- [ ] **Step 1: 新增 ItemSoldError**

在 `src/xianyu_hunter/domain/order.py` 的 `ButtonNotFoundError` 类（行 73）之后新增：

```python
class ItemSoldError(BuyerError):
    """商品已售出，不可抢购（与 ButtonNotFoundError 区分，便于返回明确错误）"""
    pass
```

- [ ] **Step 2: 验证导入**

Run: `python -c "from xianyu_hunter.domain.order import ItemSoldError; print('ok')"`

Expected: 输出 `ok`

- [ ] **Step 3: Commit**

```bash
git add src/xianyu_hunter/domain/order.py
git commit -m "feat(domain): 新增 ItemSoldError 异常区分已售场景"
```

---

### Task 4: Buyer 两阶段已售检测

**Files:**
- Modify: `src/xianyu_hunter/modules/buyer.py`（import 区、_do_buy、新增 _detect_sold/_mark_item_sold）

- [ ] **Step 1: 补充 import**

在 `src/xianyu_hunter/modules/buyer.py` 行 28-37 的 import 块中，将 `ItemSoldError` 加入：

```python
from xianyu_hunter.domain.order import (
    BuyOutcome,
    BuyResult,
    BuyerError,
    ButtonNotFoundError,
    ItemSoldError,
    OrderSnapshot,
    OrderStatus,
    OutOfStockError,
    PriceMismatchError,
)
```

- [ ] **Step 2: 新增 _detect_sold 方法**

在 `src/xianyu_hunter/modules/buyer.py` 的 `_is_out_of_stock` 方法（行 432-440）之后新增：

```python
    async def _detect_sold(self, page: Page) -> bool:
        """检测商品详情页是否显示已售出提示

        参照 _is_out_of_stock 的页面文字检测模式，独立检测已售关键词。
        为什么不复用 _is_out_of_stock：已售与已下架是不同业务语义，
        标记的目标字段（is_sold）和返回给用户的错误信息也不同。
        """
        try:
            text = await page.text_content("body") or ""
            return any(kw in text for kw in (
                "已售出", "已售完", "已售罄", "宝贝已售", "商品已售",
            ))
        except Exception:  # noqa: BLE001
            return False

    def _mark_item_sold(self, item_id: str) -> None:
        """标记商品已售并同步 task_links.display

        为什么在 buyer 内部直接标记：检测到已售的时机最准确（页面实时状态），
        延迟到路由层标记会增加耦合且可能遗漏。
        """
        try:
            self.repo.mark_sold(item_id)
            logger.info(f"[Buyer] 商品已标记为已售 item={item_id}")
        except Exception as e:  # noqa: BLE001
            # 标记失败不应阻断抢单错误返回，仅记录日志
            logger.warning(f"[Buyer] 标记商品已售失败 item={item_id}: {e}")
```

- [ ] **Step 3: 阶段一检测接入 _do_buy**

在 `src/xianyu_hunter/modules/buyer.py` 的 `_do_buy` 方法中，行 201 `await self._navigate(page, item_id)` 之后、行 204 `logger.info(f"[Buyer] 步骤2/4...")` 之前插入阶段一检测：

```python
            # 1. 导航到详情页
            logger.info(f"[Buyer] 步骤1/4 导航详情页 item={item_id}")
            await self._navigate(page, item_id)  # type: ignore[arg-type]

            # 阶段一已售检测：导航后、点击立即购买前，先检测是否已售
            # 为什么在此处检测：导航完成页面已渲染，此时检测最准；
            # 已售商品不应继续进入抢单流程，避免无效点击
            if await self._detect_sold(page):  # type: ignore[arg-type]
                self._mark_item_sold(item_id)
                raise ItemSoldError("商品已售出")

            # 2. 点击"立即购买"
```

- [ ] **Step 4: 阶段二回退检测接入 _do_buy**

在 `_do_buy` 方法中，行 217-219 的提交订单失败分支，将：

```python
            confirmed = await self._click_submit_order(page)  # type: ignore[arg-type]
            if not confirmed:
                raise ButtonNotFoundError("未找到「提交订单/确认购买」按钮")
```

改为：

```python
            confirmed = await self._click_submit_order(page)  # type: ignore[arg-type]
            if not confirmed:
                # 阶段二回退检测：提交订单按钮找不到时，回退检测是否因商品已售
                # 为什么需要回退：部分商品渲染时机不同，阶段一可能未命中
                if await self._detect_sold(page):  # type: ignore[arg-type]
                    self._mark_item_sold(item_id)
                    raise ItemSoldError("商品已售出")
                raise ButtonNotFoundError("未找到「提交订单/确认购买」按钮")
```

- [ ] **Step 5: 手动验证**

启动服务（scheduler 模式），对一个已售商品触发抢单，观察日志：

Expected: 日志显示 `[Buyer] 商品已标记为已售 item=xxx`，API 返回 409 而非 502 "未找到提交订单按钮"

- [ ] **Step 6: Commit**

```bash
git add src/xianyu_hunter/modules/buyer.py
git commit -m "feat(buyer): 两阶段已售检测，命中时标记 is_sold 并抛出 ItemSoldError"
```

---

### Task 5: 采集层已售检测

**Files:**
- Modify: `src/xianyu_hunter/modules/collector/_detail.py`（detail 方法返回前增加检测）

- [ ] **Step 1: detail() 增加已售检测**

在 `src/xianyu_hunter/modules/collector/_detail.py` 的 `detail` 方法中，返回 `ItemDetail(...)` 之前（约行 373 构造返回值之前）插入已售检测：

```python
        # 已售检测：采集页面文字，判断商品是否已售出
        # 为什么在采集侧也检测：官方采集和刷新接口复用此方法，
        # 在此检测可统一覆盖三个入口（链接刷新/官方采集/抢单前的 detail 调用）
        is_sold = False
        try:
            body_text = await page.text_content("body") or ""
            is_sold = any(kw in body_text for kw in (
                "已售出", "已售完", "已售罄", "宝贝已售", "商品已售",
            ))
        except Exception:  # noqa: BLE001
            pass

        return ItemDetail(
            id=item_id,
            title=title,
            price=price,
            # ... 其余字段不变 ...
            is_sold=is_sold,
        )
```

注意：在现有 `return ItemDetail(...)` 中追加 `is_sold=is_sold` 参数（`ItemSummary` 已定义该字段）。

- [ ] **Step 2: 验证导入无报错**

Run: `python -c "from xianyu_hunter.modules.collector._detail import DetailMixin; print('ok')"`

Expected: 输出 `ok`

- [ ] **Step 3: Commit**

```bash
git add src/xianyu_hunter/modules/collector/_detail.py
git commit -m "feat(collector): detail() 增加已售检测，设置 ItemDetail.is_sold"
```

---

### Task 6: 商品刷新 API

**Files:**
- Modify: `src/xianyu_hunter/web/routes/api_items.py`（新增 refresh 路由）

- [ ] **Step 1: 新增 refresh 路由**

在 `src/xianyu_hunter/web/routes/api_items.py` 文件末尾新增：

```python
@router.post("/{item_id}/refresh")
async def refresh_item(
    item_id: str,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """刷新单个商品详情：采集详情页并更新 items 表 + task_links.display

    触发场景：
    - 前端商品列表点击商品链接时异步调用
    - 官方采集流程复用
    - 抢单失败回退刷新
    """
    from loguru import logger

    # 校验 collector 是否可用（Web 进程 with_browser=False 时为 None）
    if container.collector is None:
        raise HTTPException(
            status_code=503,
            detail="需要浏览器实例，请以 XH_WITH_SCHEDULER=1 模式启动",
        )

    item = container.repo.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="商品不存在")

    try:
        detail = await container.collector.detail(item_id)
    except Exception as e:
        logger.warning(f"[RefreshItem] 采集失败 item={item_id}: {e}")
        raise HTTPException(status_code=502, detail=f"采集失败：{e}")

    if detail is None:
        raise HTTPException(status_code=502, detail="采集商品详情失败：页面不可达或登录已过期")

    # 更新 items 表（复用官方采集的旧值保留策略，避免清空已有字段）
    import json as _json
    new_row = {
        "id": item_id,
        "task_id": item.get("task_id") or "",
        "title": detail.title,
        "price": detail.price,
        "seller_id": detail.seller_id or "",
        "region": detail.region or "",
        "want_cnt": detail.want_cnt,
        "view_cnt": detail.view_cnt,
        "thumb_url": detail.thumb_url or "",
        "is_sold": 1 if detail.is_sold else 0,
    }
    if detail.is_sold:
        from xianyu_hunter.infra.db_models import _utcnow
        new_row["sold_detected_at"] = _utcnow()

    container.repo.upsert_item(new_row)
    # 同步 task_links.display.is_sold
    if detail.is_sold:
        container.repo.mark_sold(item_id)

    logger.info(f"[RefreshItem] 刷新成功 item={item_id} is_sold={detail.is_sold}")
    return {
        "ok": True,
        "item_id": item_id,
        "is_sold": detail.is_sold,
        "title": detail.title,
        "price": detail.price,
    }
```

- [ ] **Step 2: 验证路由注册**

Run: `python -c "from xianyu_hunter.web.routes.api_items import router; print([r.path for r in router.routes])"`

Expected: 列表中包含 `/{item_id}/refresh`

- [ ] **Step 3: Commit**

```bash
git add src/xianyu_hunter/web/routes/api_items.py
git commit -m "feat(api): 新增 POST /api/items/{id}/refresh 商品刷新接口"
```

---

### Task 7: 抢单 API 异常处理

**Files:**
- Modify: `src/xianyu_hunter/web/routes/api_orders.py:278-280`（manual_takeover 异常捕获）

- [ ] **Step 1: manual_takeover 捕获 ItemSoldError**

在 `src/xianyu_hunter/web/routes/api_orders.py` 的 `manual_takeover` 函数中，将行 278-280 的宽泛异常捕获：

```python
    except Exception as e:
        logger.exception(f"[ManualTakeover] 抢单异常：{e}")
        raise HTTPException(status_code=500, detail=f"抢单失败：{e}")
```

改为优先捕获 `ItemSoldError`：

```python
    except ItemSoldError as e:
        # 已售出：返回 409 而非 500，区分业务错误与系统异常
        logger.info(f"[ManualTakeover] 商品已售出 item={item_id}: {e}")
        raise HTTPException(status_code=409, detail="商品已售出")
    except Exception as e:
        logger.exception(f"[ManualTakeover] 抢单异常：{e}")
        raise HTTPException(status_code=500, detail=f"抢单失败：{e}")
```

- [ ] **Step 2: 补充 import**

在 `api_orders.py` 的 import 区（已有的 `from xianyu_hunter.domain.order import ...` 附近）加入 `ItemSoldError`。若该文件尚未导入 order 异常，在函数内局部导入即可（与现有 manual_takeover 内部 import 风格一致）：

在 `manual_takeover` 函数内 `try:` 之前加入：

```python
    from xianyu_hunter.domain.order import ItemSoldError
```

- [ ] **Step 3: Commit**

```bash
git add src/xianyu_hunter/web/routes/api_orders.py
git commit -m "feat(api): manual_takeover 捕获 ItemSoldError 返回 409"
```

---

### Task 8: 官方采集同步 is_sold

**Files:**
- Modify: `src/xianyu_hunter/web/routes/api_evaluations.py:1698-1743`（_collect_official_and_evaluate 的 new_item_row）

- [ ] **Step 1: new_item_row 加入 is_sold**

在 `src/xianyu_hunter/web/routes/api_evaluations.py` 的 `_collect_official_and_evaluate` 函数中，找到 `new_item_row` 字典（约行 1700），在 `"publish_time": detail.publish_time,` 之后新增：

```python
        "is_sold": 1 if detail.is_sold else 0,
    }
    if detail.is_sold:
        from xianyu_hunter.infra.db_models import _utcnow
        new_item_row["sold_detected_at"] = _utcnow()
```

并在 `_ALWAYS_OVERWRITE` 集合中追加 `"is_sold"`（已售状态来自最新采集，应覆盖旧值）：

```python
_ALWAYS_OVERWRITE = {"task_id", "publish_time", "image_urls", "view_cnt", "want_cnt", "region", "seller_id", "is_sold"}
```

- [ ] **Step 2: 采集后同步 task_links.display**

在 `container.repo.upsert_item(item_row)` 之后（约行 1743），新增 task_links 同步：

```python
            # 已售时同步 task_links.display.is_sold（前端列表读 display）
            if detail.is_sold:
                container.repo.mark_sold(item_id)
```

- [ ] **Step 3: 验证导入**

Run: `python -c "from xianyu_hunter.web.routes.api_evaluations import router; print('ok')"`

Expected: 输出 `ok`

- [ ] **Step 4: Commit**

```bash
git add src/xianyu_hunter/web/routes/api_evaluations.py
git commit -m "feat(api): 官方采集同步写入 is_sold 到 items + task_links"
```

---

### Task 9: 前端改造

**Files:**
- Modify: `frontend/src/api/item.ts`（新增 refresh 方法）
- Modify: `frontend/src/pages/Items/ItemList.tsx`（链接点击异步刷新）

- [ ] **Step 1: 新增 itemApi.refresh**

查看 `frontend/src/api/item.ts` 现有结构，在 `itemApi` 对象中新增 `refresh` 方法：

```typescript
  // 刷新单个商品详情：采集详情页并更新销售状态
  // 触发场景：链接点击异步刷新、官方采集、抢单失败回退
  refresh: (itemId: string) =>
    client.post<{ ok: boolean; item_id: string; is_sold: boolean }>(
      `/api/items/${itemId}/refresh`,
    ).then((r) => r.data),
```

- [ ] **Step 2: ItemList.tsx 链接点击改为异步刷新**

在 `frontend/src/pages/Items/ItemList.tsx` 中，找到商品详情链接（`<a href={d.url}` 或类似），改为 onClick 处理：

```tsx
// 点击商品链接：异步触发刷新（不阻塞跳转），再打开闲鱼原帖
const handleItemClick = (e: React.MouseEvent, itemId: string, url: string) => {
  e.preventDefault()
  // 异步刷新，失败静默忽略（不阻塞跳转）
  itemApi.refresh(itemId).catch(() => {})
  window.open(url, '_blank')
}
```

将链接的 `href` 替换为 `onClick`，例如：
```tsx
<a onClick={(e) => handleItemClick(e, d.item_id, d.url)} style={{ cursor: 'pointer' }}>
```

- [ ] **Step 3: 构建验证**

Run: `cd frontend; npm run build`

Expected: 构建成功，无 TypeScript 错误

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/item.ts frontend/src/pages/Items/ItemList.tsx
git commit -m "feat(frontend): 商品链接点击异步触发刷新接口"
```

---

### Task 10: 集成验证

- [ ] **Step 1: 后端单元测试**

Run: `python -m pytest tests/test_item_sold_status.py -v`

Expected: 全部 PASS

- [ ] **Step 2: 端到端验证（已售商品抢单）**

1. 启动服务（scheduler 模式）：`XH_WITH_SCHEDULER=1` 启动
2. 对一个已售商品触发抢单（前端评估明细页点击抢单）
3. 验证：
   - API 返回 409 `{"detail": "商品已售出"}`
   - 日志显示 `[Buyer] 商品已标记为已售`
   - 数据库 `items.is_sold=1`，`sold_detected_at` 有值
   - 前端订单记录页显示错误信息"商品已售出"

- [ ] **Step 3: 端到端验证（链接刷新）**

1. 在商品列表点击一个商品链接
2. 验证：新标签页打开闲鱼原帖，同时后台日志显示 `[RefreshItem] 刷新成功`
3. 若商品已售，列表刷新后该商品显示"已售"标签

- [ ] **Step 4: 端到端验证（无浏览器降级）**

1. 以非 scheduler 模式启动（Web 进程 `with_browser=False`）
2. 调用 `POST /api/items/{item_id}/refresh`
3. 验证：返回 503 `{"detail": "需要浏览器实例，请以 XH_WITH_SCHEDULER=1 模式启动"}`

- [ ] **Step 5: Final Commit**

```bash
git add -A
git commit -m "test: 商品已售状态检测集成验证通过"
```
