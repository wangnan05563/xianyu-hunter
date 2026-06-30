# 商品已售状态检测与信息刷新设计

> 日期：2026-06-26
> 状态：设计阶段
> 关联模块：`modules/buyer.py`、`modules/collector/_detail.py`、`infra/db_models.py`、`infra/repo_items.py`、`web/routes/api_orders.py`、`web/routes/api_items.py`、`web/routes/api_evaluations.py`、`frontend/src/pages/Items/ItemList.tsx`

## 1. 背景与目标

### 1.1 现状

抢单流程位于 [buyer.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/modules/buyer.py)，`_do_buy` 分四步：导航详情页 → 点击立即购买 → 等待订单确认页 → 点击提交订单。当商品已售出时，"提交订单"按钮不存在，抛出 `ButtonNotFoundError("未找到「提交订单」按钮")`，错误信息无法区分"已售出"与其他失败原因。

商品销售状态 `is_sold` 当前仅由搜索 API（[collector/_search.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/modules/collector/_search.py)）写入 `task_links.display` JSON。前端 [ItemList.tsx](file:///d:/code/otherProjects/17_xianyu/frontend/src/pages/Items/ItemList.tsx) 已实现"已售/在售"标签与卡片角标，但 DB 模式下 `task_links.display` 旧数据缺失 `is_sold`，导致历史商品一律显示"在售"。

`items` 表（[db_models.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/infra/db_models.py) `ItemRow`）无 `is_sold` 字段；详情页采集（`_detail.py`）和官方采集（`api_evaluations.py`）均不检测/不同步销售状态。

### 1.2 待解决问题

| # | 问题 | 影响 |
|---|------|------|
| A | 抢单失败不区分"已售出" | 商品已售时报"未找到提交订单按钮"，用户无法判断真实原因 |
| B | `is_sold` 数据来源单一 | 仅搜索 API 写入，历史商品在 DB 模式下显示"在售"，状态失真 |
| C | 详情页采集不检测已售 | 官方采集更新了 items 表但不含销售状态 |
| D | 点击商品详情链接不刷新信息 | 用户点击链接仅跳转闲鱼原帖，不更新本地商品信息 |

### 1.3 目标

1. 抢单过程中两阶段检测已售，命中时标记 `is_sold=1` 并返回明确错误"商品已售出"
2. `items` 表新增 `is_sold` 字段，抢单/官方采集/链接刷新三处入口统一更新
3. 新增 `POST /api/items/{item_id}/refresh` 接口，链接点击时异步触发刷新（不阻塞跳转）
4. 官方采集流程同步写入 `is_sold`

## 2. 技术方案

### 2.1 数据模型变更

`ItemRow` 新增 2 列，复用项目既有 `db.ensure_columns()` 机制（见 [db.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/infra/db.py)），无需独立迁移脚本：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `is_sold` | BOOLEAN | 0 | 销售状态：0=在售，1=已售 |
| `sold_detected_at` | TEXT | NULL | 检测到已售的时间戳（ISO 格式），便于排查 |

`ItemDetail` 领域模型（[domain/item.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/domain/item.py)）已继承 `ItemSummary.is_sold`，无需改动领域模型结构，仅补充采集逻辑写入。

### 2.2 已售检测逻辑（buyer.py）

#### 2.2.1 新增异常类型

在 `buyer.py` 或 `domain/errors.py`（按项目惯例定位）新增：

```python
class ItemSoldError(Exception):
    """商品已售出，不可抢购"""
    pass
```

`api_orders.py` 的 `manual_takeover` 捕获 `ItemSoldError` 后返回 409 + `{"detail": "商品已售出"}`，与现有 502 `ButtonNotFoundError` 区分。

#### 2.2.2 新增 `_detect_sold` 方法

参考现有 `_is_out_of_stock` 的页面文字检测模式：

```python
SOLD_KEYWORDS = ("已售出", "已售完", "已售罄", "宝贝已售", "商品已售")

def _detect_sold(self) -> bool:
    # 检测详情页是否包含已售关键词
    # 命中则更新 items.is_sold=1 + sold_detected_at，返回 True
    # 未命中返回 False
```

#### 2.2.3 两阶段检测接入 `_do_buy`

**阶段一（导航详情页后，点击立即购买前）**：

```python
# 步骤1/4 导航详情页
await page.goto(...)
await asyncio.sleep(...)

# 新增：导航后先检测已售
if await self._detect_sold():
    self._mark_item_sold()
    raise ItemSoldError("商品已售出")

# 步骤2/4 点击立即购买
...
```

**阶段二（提交订单失败后回退）**：

```python
# 步骤3/4 点击提交订单
try:
    btn = await self._wait_submit_button(...)
except asyncio.TimeoutError:
    # 回退检测：是否因商品已售导致无提交订单按钮
    if await self._detect_sold():
        self._mark_item_sold()
        raise ItemSoldError("商品已售出")
    raise ButtonNotFoundError("未找到「提交订单」按钮")
```

`_mark_item_sold` 调用 `repo_items.mark_sold(item_id)` 更新 items 表 + 同步 `task_links.display.is_sold`。

### 2.3 商品刷新接口

新增路由 `POST /api/items/{item_id}/refresh`，挂载到 [api_items.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/web/routes/api_items.py)（若不存在则新建）。

**流程**：

1. 校验 `item_id` 格式
2. 获取 `container.collector`；若 `with_browser=False`，collector 不可用，返回 `503 {"detail": "需要浏览器实例，请以 scheduler 模式启动"}`
3. 调用 `collector.detail(item_id)` 采集详情页
4. `_detail.py` 的 `detail()` 增加已售检测：检测页面关键词，设置 `ItemDetail.is_sold`
5. 调用 `repo_items.upsert(detail)` 更新 items 表（含 is_sold）
6. 同步 `task_links.display.is_sold`（解决 DB 模式下旧数据缺失）
7. 返回更新后的商品信息

**鉴权**：复用现有 token 中间件（该接口不在白名单内，需认证）。

### 2.4 官方采集同步

[api_evaluations.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/web/routes/api_evaluations.py) 的 `_collect_official_and_evaluate` 流程中，`collector.detail()` 返回后，将 `detail.is_sold` 一并写入 items 表 + task_links.display。复用 2.3 步的更新逻辑，避免重复代码。

### 2.5 前端链接改造

[ItemList.tsx](file:///d:/code/otherProjects/17_xianyu/frontend/src/pages/Items/ItemList.tsx) 的商品详情链接由 `<a href={d.url}>` 改为 onClick 处理：

```tsx
const handleItemClick = (e, item) => {
  e.preventDefault()
  // 异步刷新，不阻塞跳转，失败静默忽略
  itemApi.refresh(item.item_id).catch(() => {})
  window.open(item.url, '_blank')
}
```

前端 `is_sold` 显示已就绪（表格 Tag + 卡片角标），刷新后列表数据更新自动反映新状态。

## 3. 错误处理

| 场景 | HTTP 状态 | 响应 |
|------|-----------|------|
| 抢单时商品已售 | 409 | `{"detail": "商品已售出"}` |
| 刷新接口无浏览器实例 | 503 | `{"detail": "需要浏览器实例，请以 scheduler 模式启动"}` |
| 刷新接口 item_id 不存在 | 404 | `{"detail": "商品不存在"}` |
| 链接异步刷新失败 | — | 静默忽略，不阻塞跳转 |

## 4. 影响范围

### 4.1 后端

| 文件 | 改动 |
|------|------|
| `infra/db_models.py` | `ItemRow` 新增 `is_sold`、`sold_detected_at` 字段 |
| `infra/db.py` | `ensure_columns` 覆盖新字段（已有机制自动适配） |
| `infra/repo_items.py` | 新增 `mark_sold()`、`upsert` 写入 `is_sold` |
| `infra/repo_links.py` | `task_links.display.is_sold` 同步更新 |
| `modules/buyer.py` | 新增 `ItemSoldError`、`_detect_sold`、`_mark_item_sold`，两阶段检测接入 `_do_buy`；构造函数新增 `repo_items` 依赖注入（`container` 构造 buyer 时传入） |
| `modules/collector/_detail.py` | `detail()` 增加已售检测，设置 `ItemDetail.is_sold` |
| `web/routes/api_items.py` | 新增 `POST /api/items/{item_id}/refresh` 路由 |
| `web/routes/api_orders.py` | `manual_takeover` 捕获 `ItemSoldError` 返回 409 |
| `web/routes/api_evaluations.py` | `_collect_official_and_evaluate` 同步 `is_sold` |

### 4.2 前端

| 文件 | 改动 |
|------|------|
| `frontend/src/api/item.ts` | 新增 `refresh(itemId)` 方法 |
| `frontend/src/pages/Items/ItemList.tsx` | 商品详情链接改为 onClick 异步刷新 + 跳转 |

## 5. 验收标准

1. 已售商品抢单时返回 409 "商品已售出"，items 表 `is_sold=1`，`sold_detected_at` 有值
2. 调用 `POST /api/items/{item_id}/refresh` 后，items 表 + task_links.display 的 `is_sold` 同步更新
3. 点击商品列表链接，跳转闲鱼原帖的同时异步触发刷新
4. 官方采集后 items 表 `is_sold` 反映最新状态
5. Web 进程无浏览器时刷新接口返回 503，不崩溃
