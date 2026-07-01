# 统一采集服务设计

## 背景

当前系统存在多条采集链路，用户观察到“评估明细中点击标题链接更新信息更全”，而系统维护菜单的批量采集仍会出现部分字段缺失。代码盘点后确认，差异主要来自采集语义分裂，而不是单个选择器问题。

现有入口如下：

- 搜索/实时采集：`Collector.search()` / `Collector.live_search()`，负责发现商品和写入搜索页摘要字段。
- 任务运行采集：`TaskWorker.run_once()`，串行执行详情页、卖家主页、评估和下单流程。
- 轻量刷新：`POST /api/items/{item_id}/refresh`，只执行 `collector.detail()` 并更新 `items` 与 `task_links.display`。
- 完整官方采集：`POST /api/evaluations/{item_id}/collect-official`，执行详情页、卖家主页、评价提取、旧值保护、重新评估、写入 `items/sellers/task_links/events`。
- 系统维护批量采集：`BatchRefreshScheduler._refresh_one()`，只执行 `collector.detail()`，因此质量低于完整官方采集。

目标是把“详情采集后如何合并、入库、同步展示、可选重评估”的业务语义收敛到统一服务，减少重复逻辑并提升批量采集质量。

## 目标

1. 新增统一采集服务，集中管理轻量详情刷新和完整官方采集两种模式。
2. 批量采集改为复用统一服务，默认使用完整官方采集能力补全卖家画像和评估事件。
3. 保留轻量刷新模式，供标题点击、商品列表快速刷新等低成本场景使用。
4. 统一旧值保护策略，避免空标题、空图片、空描述覆盖已有有效数据。
5. 保持现有 API 路径兼容，前端尽量不改或少改。

## 非目标

- 不重写 `Collector.search/detail/seller_profile` 的底层选择器和浏览器控制逻辑。
- 不改变任务搜索发现和去重策略。
- 不在本轮引入新的前端页面或大规模 UI 改造。
- 不把批量采集改成高并发执行。为降低反爬风险，仍保持串行或受控低并发。

## 设计

新增服务模块：

`src/xianyu_hunter/modules/collection_service.py`

核心对象：

```python
class CollectionMode(str, Enum):
    DETAIL_ONLY = "detail_only"
    OFFICIAL_FULL = "official_full"


@dataclass
class CollectionResult:
    ok: bool
    item_id: str
    mode: CollectionMode
    detail: ItemDetail | None = None
    seller: SellerProfile | None = None
    reviews: list[str] = field(default_factory=list)
    evaluation: EvalResult | None = None
    changed_fields: list[str] = field(default_factory=list)
```

服务入口：

```python
class ItemCollectionService:
    async def collect(
        self,
        item_id: str,
        *,
        task_id: str | None = None,
        mode: CollectionMode = CollectionMode.OFFICIAL_FULL,
        existing_item: dict | None = None,
        source: str = "official",
        reuse_page: Any | None = None,
        evaluate: bool | None = None,
    ) -> CollectionResult:
        ...
```

`DETAIL_ONLY` 模式执行：

1. Cookie 同步。
2. `collector.detail(item_id)`。
3. 旧值保护合并到 `items`。
4. `is_sold=True` 时调用 `mark_sold()`。
5. 同步 `task_links.display`。
6. 返回变更字段，不写 `sellers` 和 `eval.scored`。

`OFFICIAL_FULL` 模式执行：

1. Cookie 检查和同步，复用现有官方采集前置逻辑。
2. `collector.detail(item_id)`。
3. 并行提取详情页评价和 `collector.seller_profile(detail.seller_id)`。
4. 卖家主页失败时调用 `collector.seller_profile_fallback(None, detail)`。
5. 旧值保护合并到 `items`。
6. 写入 `sellers`。
7. 同步 `task_links.display`。
8. 执行 `evaluator.evaluate(detail, seller)`。
9. 写入或更新 `eval.scored`，payload 标记 `data_source="official"`。

## 数据合并策略

统一服务提供私有合并函数：

```python
def merge_item_row(existing: dict, incoming: dict, always_overwrite: set[str]) -> dict:
    ...
```

默认规则：

- `None` 和空字符串视为缺失，不覆盖旧值。
- 数字 `0` 是合法值，不再被当作缺失。
- `image_urls` 为空时保留旧值。
- `task_id`、`publish_time`、`view_cnt`、`want_cnt`、`region`、`seller_id`、`is_sold` 可以按采集结果覆盖。
- 下架场景如果详情标题为空，只标记售出/下架，不清空标题和展示字段。

这套策略替代目前分散在 `api_items.refresh_item`、`api_evaluations._collect_official_and_evaluate`、`BatchRefreshScheduler._refresh_one` 中的重复写法。

## 调用方迁移

`api_evaluations.py`

- 保留现有 `/api/evaluations/{item_id}/collect-official` 和 `/batch-collect-official` 路由。
- 路由只做参数校验、浏览器锁、HTTP 错误映射。
- 具体采集委托给 `ItemCollectionService.collect(mode=OFFICIAL_FULL)`。

`api_items.py`

- 保留 `/api/items/{item_id}/refresh`。
- 改为调用 `ItemCollectionService.collect(mode=DETAIL_ONLY, source="live")`。
- 返回结构保持与当前前端 `itemApi.refresh()` 兼容。

`batch_refresh_scheduler.py`

- `_refresh_one()` 改为调用统一服务。
- 默认模式使用 `OFFICIAL_FULL`，以接近评估明细官方采集的数据质量。
- 保留失败计数、暂停/继续/停止、进度、历史记录和变更日志。
- 变更字段来自统一服务返回的 `changed_fields`。

`web.startup._call_official_collect`

- 继续作为兼容包装，但内部委托统一服务或官方采集路由使用的同一函数。

## 错误处理

- Cookie 缺失：继续使用 403。
- Cookie 过期或未同步：继续使用 440。
- 反爬/验证码：继续使用 441。
- 商品下架或详情无法提取核心字段：继续使用 410。
- 浏览器断开或系统异常：继续使用 502/504。

批量采集中，单条商品的 410 计入 skipped 或业务失败但不中断；403/440/441 应触发熔断，避免整批继续浪费浏览器时间。

## 性能与反爬

完整官方采集比轻量刷新更慢，因为会访问卖家主页并重新评估。批量采集默认仍串行执行，并保留每条后的短暂让步。后续如需提速，只允许增加小并发配置，默认不开启。

为降低重复采集成本，保留现有 `max_items_per_run` 限制。后续可增加“最近 N 分钟已官方采集则跳过”的策略，但不作为本轮必要范围。

## 测试

新增或调整以下测试：

- `test_collection_service_detail_only_preserves_existing_fields`
- `test_collection_service_official_full_writes_seller_and_eval_event`
- `test_collection_service_marks_sold_without_clearing_existing_title`
- `test_batch_refresh_uses_collection_service`
- `test_api_items_refresh_keeps_response_shape`
- `test_collect_official_route_delegates_to_service`

现有回归测试继续保留：

- `tests/test_official_collect_integration.py`
- `tests/test_batch_refresh_scheduler.py`
- `tests/test_detail_extract_failure.py`

## 实施顺序

1. 新增 `collection_service.py`，先迁移合并和持久化逻辑，写服务级单元测试。
2. 改造 `api_items.refresh_item` 调用服务，确保响应结构不变。
3. 改造 `api_evaluations._collect_official_and_evaluate` 或保留兼容函数并委托服务。
4. 改造 `BatchRefreshScheduler._refresh_one()`，默认走完整官方采集模式。
5. 跑后端相关测试，必要时补充前端 API 类型。

## 风险

- 批量采集默认改完整模式后耗时会增加。用 `max_items_per_run`、串行执行和失败熔断控制风险。
- 官方采集函数目前位于路由文件，抽服务时要避免循环导入。
- 当前工作区已有未提交改动，实施时必须只修改与统一采集有关的文件，不回退用户改动。

## 验收标准

- 批量采集和评估明细官方采集共享同一套完整采集/合并/入库逻辑。
- 轻量刷新仍可快速更新标题、价格、品牌、地区、想要数、浏览数和售出状态。
- 空采集结果不会清空已有有效字段。
- 完整官方采集会写入 `sellers` 和 `eval.scored`，并标记 `data_source="official"`。
- 相关后端测试通过。
