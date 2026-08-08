# 数据透传与职责分离规范

> 本规范源自 2026-07-18 卖家评估菜单 Bug 复盘：三个同源 Bug（seller 字段未合并、user_id 传递断裂、价格快照缺失）均为"信息传递断裂"问题。
> 适用范围：多层架构（domain → infra → modules → web）、多用户系统、采集-评估-展示链路、有 fallback 机制的采集流程。

---

## 一、跨层数据透传完整性原则（PROPAGATION-01）

### 核心原则

任一字段在多层调用链中传递时，**入口层接收的字段必须完整透传到最底层**，中间任一层断裂即 Bug。

### 判断流程

```
入口层接收字段 → 中间层传递 → 最底层使用
     ↓              ↓              ↓
   检查签名      检查透传       检查使用
```

1. **入口层**：函数签名是否接收该字段（`user_id: str | None = None`）
2. **中间层**：是否将字段传递给下一层（`next_layer(user_id=user_id)`）
3. **最底层**：是否使用该字段（`event["user_id"] = user_id`）

### 反模式（本次复盘 Bug 2A）

```python
# ❌ 错误：user_id 在 _evaluate_and_notify 断裂
async def collect(self, item_id, *, user_id=None):
    # user_id 接收了
    eval_result = self._evaluate_and_notify(item_id, detail, seller, reviews, task_id)
    # ↑ 未传 user_id，断裂！

def _evaluate_and_notify(self, item_id, detail, seller, reviews, task_id):
    self._save_eval_event(task_id, item_id, detail, seller, reviews, eval_result)
    # ↑ 未接收也未传 user_id

def _save_eval_event(self, task_id, item_id, detail, seller, reviews, eval_result):
    self.repo.upsert_eval_event({...})  # user_id 走默认值，多用户隔离失效
```

### 正模式

```python
# ✅ 正确：完整透传链路
async def collect(self, item_id, *, user_id=None):
    eval_result = self._evaluate_and_notify(item_id, detail, seller, reviews, task_id, user_id=user_id)

def _evaluate_and_notify(self, item_id, detail, seller, reviews, task_id, *, user_id=None):
    self._save_eval_event(task_id, item_id, detail, seller, reviews, eval_result, user_id=user_id)

def _save_eval_event(self, task_id, item_id, detail, seller, reviews, eval_result, *, user_id=None):
    self.repo.upsert_eval_event({...}, user_id=user_id)
```

### 适用场景

- 多用户系统的 user_id 透传
- 多任务系统的 task_id 透传
- 链路追踪的 request_id 透传
- 任何在多层调用链中传递的标识字段

### 不适用场景

- 单层脚本（无跨层传递）
- 纯内部辅助函数（不跨模块）

---

## 二、快照与最新值职责分离原则（SNAPSHOT-01）

### 核心原则

当同一字段同时用于**过滤**和**展示**时，必须职责分离：
- **过滤**用评估时快照（评估通过即说明当时在范围内）
- **展示**用最新值（用户期望看到最新信息）

### 判断流程

```
字段在 enrich 阶段被覆盖？
  ├─ 是 → 覆盖前必须保存快照
  │       └─ 过滤函数优先用快照，回退到最新值
  └─ 否 → 无需快照，直接用原值
```

### 反模式（本次复盘 Bug 2B）

```python
# ❌ 错误：enrich 用最新价格覆盖，过滤也用最新价格
def _apply_positive_fields(payload, candidates):
    for src_key, dst_key in _POSITIVE_FIELD_MAP.items():
        value = candidates.get(src_key)
        if value is not None and value > 0:
            payload[dst_key] = value  # 直接覆盖，丢失评估时价格

def _filter_price_range(payload, min_price, max_price):
    price_val = payload.get("item_price")  # 用的是被覆盖后的最新价格
    # 官方采集更新价格后，旧 eval 事件被按新价格误判超范围
```

### 正模式

```python
# ✅ 正确：覆盖前保存快照，过滤优先用快照
def _apply_positive_fields(payload, candidates):
    for src_key, dst_key in _POSITIVE_FIELD_MAP.items():
        value = candidates.get(src_key)
        if value is not None and value > 0:
            if src_key == "price" and "_eval_snapshot_price" not in payload:
                payload["_eval_snapshot_price"] = payload.get(dst_key)  # 保存快照
            payload[dst_key] = value  # 展示用最新值

def _filter_price_range(payload, min_price, max_price):
    # 过滤优先用快照
    if "_eval_snapshot_price" in payload:
        price_val = payload.get("_eval_snapshot_price")
    else:
        price_val = payload.get("item_price")  # 兼容未 enrich 的旧事件
```

### 快照保存时机

- **首次 enrich 覆盖前**保存（仅一次，后续不刷新）
- 保留的是**评估入库时**的值，而非多次 enrich 中任意一次的值
- 用 `"_eval_snapshot_price" not in payload` 判断是否首次

### 适用场景

- 评估-展示链路（评估时价格 vs 最新价格）
- 历史记录过滤（历史快照 vs 当前状态）
- 任何"写入时快照 + 展示时最新"的场景

### 不适用场景

- 纯展示场景（无过滤逻辑）
- 实时数据（无历史快照需求）

---

## 三、Fallback 路径数据合并完整性原则（FALLBACK-MERGE-01）

### 核心原则

任一采集层有 fallback 逻辑时，fallback 返回的数据**必须合并所有可用来源**，未合并即 Bug。

### 判断流程

```
存在 fallback 逻辑？
  ├─ 是 → fallback 返回后是否调用合并函数？
  │       ├─ 是 → 合并函数是否覆盖所有字段？
  │       │       ├─ 是 → ✅ 合格
  │       │       └─ 否 → ❌ 补充合并逻辑
  │       └─ 否 → ❌ 添加合并调用
  └─ 否 → 无需检查
```

### 反模式（本次复盘 Bug 1）

```python
# ❌ 错误：worker 有 seller_profile 但未合并 detail 字段
async def _collect_detail_and_seller(self, summary, shared_pages, _has_browser):
    seller = await self.collector.seller_profile(detail.seller_id, page=...)
    if not seller:
        seller = await self._seller_profile_fallback(summary=summary, detail=detail)
    # ↑ seller_profile 成功时未合并 detail 字段！
    # 当 seller_profile 返回部分字段为空时，evaluator 维度判定失败 → 65 分
```

### 正模式

```python
# ✅ 正确：seller_profile 成功后也合并 detail 字段
async def _collect_detail_and_seller(self, summary, shared_pages, _has_browser):
    seller = await self.collector.seller_profile(detail.seller_id, page=...)
    if not seller:
        seller = await self._seller_profile_fallback(summary=summary, detail=detail)
    # 合并 detail 字段（与 collection_service._merge_detail_seller_fields 对齐）
    if seller and detail:
        if not seller.nick and detail.detail_seller_nick:
            seller.nick = detail.detail_seller_nick
        if seller.credit_score is None and detail.detail_credit_score is not None:
            seller.credit_score = detail.detail_credit_score
        # ... 其他字段
```

### 合并字段优先级

- 主数据源（seller_profile）优先
- 仅当主数据源字段为空时，用次数据源（detail）补充
- 用 `is None` / `not` 判断字段是否为空，而非 `==`（避免 0/空字符串误判）

### 适用场景

- 有 fallback 的采集流程（seller_profile_fallback）
- 多数据源合并（搜索结果 + 详情页 + 卖家主页）
- 任何"主源失败时用次源"的场景

### 不适用场景

- 稳定数据源（无 fallback）
- 单一数据源（无需合并）

---

## 四、多用户隔离字段一致性原则（MULTIUSER-CONSISTENCY-01）

### 核心原则

写入数据库的记录有 user_id 字段时，**写入时必须显式传入 user_id**，不依赖默认值。查询时用 user_id 过滤的场景，写入时未传 user_id 即 Bug。

### 判断流程

```
写入数据库记录含 user_id 字段？
  ├─ 是 → 写入链路是否透传 user_id？
  │       ├─ 是 → ✅ 合格
  │       └─ 否 → ❌ Bug（依赖默认值，多用户隔离失效）
  └─ 否 → 无需检查
```

### 反模式（本次复盘 Bug 2A）

```python
# ❌ 错误：upsert_eval_event 未传 user_id
self.repo.upsert_eval_event({
    "type": "eval.scored",
    "task_id": task_id,
    # ... 其他字段
})  # user_id 未传，走默认值 "default"

# 查询时用 user_id 过滤
def list_evaluations(request):
    user_id = getattr(request.state, "user_id", None)
    rows, _ = container.repo.list_events_by_type_prefix(
        type_prefix=_EVAL_TYPE_PREFIX, user_id=user_id,
    )  # user_id != "default" 的查询会过滤掉 user_id="default" 的记录
```

### 正模式

```python
# ✅ 正确：显式传入 user_id
self.repo.upsert_eval_event({
    "type": "eval.scored",
    "task_id": task_id,
    # ... 其他字段
}, user_id=user_id)  # 显式传入
```

### 深度防御

`upsert_eval_event` 实现层应同时支持：
1. 调用方通过 `user_id` 关键字传入时，注入到 event 字典
2. DELETE 附加 user_id 过滤，防止跨用户误删
3. 与 list_events 等查询方法的 user_id 隔离语义一致

### 适用场景

- 多用户系统的数据库写入
- 任何有 user_id 列的表（events / items / tasks / sellers 等）
- 跨用户数据隔离场景

### 不适用场景

- 单用户系统（无 user_id 隔离需求）
- 系统级全局数据（无用户归属）

---

## 五、自检清单

开发完成前，对本次改动涉及的代码路径执行以下检查：

- [ ] **PROPAGATION-01**：跨层调用链中的标识字段（user_id/task_id/request_id）是否完整透传？
- [ ] **SNAPSHOT-01**：enrich 覆盖字段前是否保存快照？过滤是否优先用快照？
- [ ] **FALLBACK-MERGE-01**：fallback 路径返回的数据是否合并所有可用来源？
- [ ] **MULTIUSER-CONSISTENCY-01**：数据库写入是否显式传入 user_id？

任一项不通过，不得进入代码审查阶段。

---

## 六、关联文档

- [multi-user-auth.md](multi-user-auth.md)：多用户资源隔离与认证规范
- [multi-user-cookie-isolation.md](multi-user-cookie-isolation.md)：多用户 Cookie 隔离规范
- [state-management.md](state-management.md)：状态管理与一致性规范
- [config-driven.md](config-driven.md)：配置驱动与字段契约规范
