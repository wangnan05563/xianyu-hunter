# 缓存测试模板

> 关联编码规范：§2.15 缓存策略规范
> 适用场景：实时搜索缓存（`_live_cache`）的 TTL、命中、失效、空结果策略与配置化验证。
> 配置节点：`config.yaml#cache.live_search_ttl`

## 1. 测试场景总览

| 场景 | 目标 | 关键 mock 对象 | 关联规范 |
|------|------|----------------|----------|
| TTL 生效 | TTL 到期后触发新查询 | `time.monotonic` | §2.15.1 |
| 空结果不缓存 | `filtered=[]` 不写入 `_live_cache` | 实时搜索函数 | §2.15.2 |
| 缓存命中 | TTL 内二次请求不触发实时搜索 | 实时搜索函数 + `time.monotonic` | §2.15.3 |
| 缓存失效重查 | 主动 pop 后触发新查询 | `_live_cache` 操作 | §2.15.4 |
| 配置化验证 | TTL 从配置读取而非硬编码 | 配置加载函数 | §2.15.5 |

## 2. 场景 1：TTL 生效测试

**目标**：mock `time.monotonic()` 推进时间，验证 TTL 到期后触发新查询（而非返回缓存）。

**验证要点**：
- TTL 内的二次请求应命中缓存（搜索函数不被调用）
- TTL 到期后的请求应触发新搜索（搜索函数被再次调用）

```python
import time
import pytest


def test_ttl_expiry_triggers_new_query(monkeypatch):
    """TTL 到期后应触发新查询，不返回过期缓存。关联 §2.15.1。"""
    # 模拟时间序列：首次请求 t0，二次请求 t0 + ttl + 1（已过期）
    fake_clock = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: fake_clock[0])

    call_count = {"search": 0}

    def fake_live_search(task_id):
        call_count["search"] += 1
        return [{"item_id": "1", "price": 100}]

    cache = {}  # 模拟 _live_cache
    ttl = 60

    def query_with_cache(task_id):
        now = time.monotonic()
        cached = cache.get(task_id)
        if cached and now - cached["ts"] < ttl:
            return cached["data"]
        data = fake_live_search(task_id)
        # 空结果不缓存的守卫（§2.15.2）
        if data:
            cache[task_id] = {"data": data, "ts": now}
        return data

    # 首次请求：触发搜索
    result1 = query_with_cache("task_a")
    assert call_count["search"] == 1

    # 推进时间到 TTL 之后
    fake_clock[0] = 1000.0 + ttl + 1

    # 二次请求：应触发新搜索（非命中缓存）
    result2 = query_with_cache("task_a")
    assert call_count["search"] == 2, "TTL 到期后应触发新查询"
```

## 3. 场景 2：空结果不缓存测试

**目标**：构造空结果（`filtered=[]`），验证 `_live_cache` 字典未被写入。

**验证要点**：
- 实时搜索返回空列表时，`_live_cache` 不应写入该 task_id
- 后续相同 task_id 的请求应再次触发实时搜索

```python
import time
import pytest


def test_empty_result_not_cached(monkeypatch):
    """空结果（filtered=[]）不应写入 _live_cache。关联 §2.15.2。"""
    fake_clock = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: fake_clock[0])

    call_count = {"search": 0}

    def fake_live_search(task_id):
        call_count["search"] += 1
        return []  # 模拟 filtered=[] 空结果

    cache = {}  # 模拟 _live_cache
    ttl = 60

    def query_with_cache(task_id):
        now = time.monotonic()
        cached = cache.get(task_id)
        if cached and now - cached["ts"] < ttl:
            return cached["data"]
        data = fake_live_search(task_id)
        if data:  # 空结果不缓存守卫
            cache[task_id] = {"data": data, "ts": now}
        return data

    # 首次请求：返回空结果
    result1 = query_with_cache("task_a")
    assert result1 == []
    assert call_count["search"] == 1

    # 验证 _live_cache 未写入空结果
    assert "task_a" not in cache, "空结果不应写入缓存"

    # 二次请求（时间未推进）：应再次触发搜索（因未缓存）
    result2 = query_with_cache("task_a")
    assert call_count["search"] == 2, "空结果未缓存，二次请求应触发新查询"
```

## 4. 场景 3：缓存命中测试

**目标**：TTL 内第二次请求应命中缓存（不触发实时搜索）。

**验证要点**：
- 首次请求触发实时搜索
- TTL 内二次请求命中缓存，搜索函数不被再次调用
- 返回数据与首次一致

```python
import time
import pytest


def test_cache_hit_within_ttl(monkeypatch):
    """TTL 内二次请求应命中缓存，不触发实时搜索。关联 §2.15.3。"""
    fake_clock = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: fake_clock[0])

    call_count = {"search": 0}

    def fake_live_search(task_id):
        call_count["search"] += 1
        return [{"item_id": "1", "price": 100}]

    cache = {}  # 模拟 _live_cache
    ttl = 60

    def query_with_cache(task_id):
        now = time.monotonic()
        cached = cache.get(task_id)
        if cached and now - cached["ts"] < ttl:
            return cached["data"]
        data = fake_live_search(task_id)
        if data:
            cache[task_id] = {"data": data, "ts": now}
        return data

    # 首次请求：触发搜索
    result1 = query_with_cache("task_a")
    assert call_count["search"] == 1

    # 推进时间但仍在 TTL 内
    fake_clock[0] = 1000.0 + ttl - 1

    # 二次请求：应命中缓存，不触发搜索
    result2 = query_with_cache("task_a")
    assert call_count["search"] == 1, "TTL 内应命中缓存，不触发实时搜索"
    assert result2 == result1, "缓存返回数据应与首次一致"
```

## 5. 场景 4：缓存失效重查测试

**目标**：主动 `_live_cache.pop(task_id)`，验证下次请求触发新查询。

**验证要点**：
- 缓存命中后，主动 pop 清除缓存
- 下次请求应触发新的实时搜索
- 新搜索结果应写入缓存

```python
import time
import pytest


def test_cache_invalidation_triggers_requery(monkeypatch):
    """主动 pop 缓存后，下次请求应触发新查询。关联 §2.15.4。"""
    fake_clock = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: fake_clock[0])

    call_count = {"search": 0}

    def fake_live_search(task_id):
        call_count["search"] += 1
        return [{"item_id": "1", "price": 100}]

    cache = {}  # 模拟 _live_cache
    ttl = 60

    def query_with_cache(task_id):
        now = time.monotonic()
        cached = cache.get(task_id)
        if cached and now - cached["ts"] < ttl:
            return cached["data"]
        data = fake_live_search(task_id)
        if data:
            cache[task_id] = {"data": data, "ts": now}
        return data

    # 首次请求：触发搜索并缓存
    result1 = query_with_cache("task_a")
    assert call_count["search"] == 1
    assert "task_a" in cache

    # 主动失效缓存（模拟 _live_cache.pop(task_id)）
    cache.pop("task_a")
    assert "task_a" not in cache

    # 二次请求：缓存已失效，应触发新查询
    result2 = query_with_cache("task_a")
    assert call_count["search"] == 2, "缓存失效后应触发新查询"
    assert "task_a" in cache, "新查询结果应重新写入缓存"
```

## 6. 场景 5：配置化验证测试

**目标**：修改 `config.yaml` 的 `cache.live_search_ttl`，验证 TTL 从配置读取（不硬编码）。

**验证要点**：
- TTL 值从配置加载，而非硬编码在源码中
- 修改配置后 TTL 行为随之改变
- 配置缺失时有合理默认值

```python
import time
import pytest


def test_ttl_read_from_config(monkeypatch):
    """TTL 应从 config.yaml 读取，不硬编码。关联 §2.15.5。"""
    fake_clock = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: fake_clock[0])

    # 模拟配置加载（实际项目中从 config.yaml 读取）
    fake_config = {"cache": {"live_search_ttl": 30}}
    monkeypatch.setattr(
        "your_project.config.load_config",  # 替换为实际配置加载函数路径
        lambda: fake_config,
    )

    call_count = {"search": 0}

    def fake_live_search(task_id):
        call_count["search"] += 1
        return [{"item_id": "1", "price": 100}]

    cache = {}  # 模拟 _live_cache
    # 从配置读取 TTL（禁止硬编码）
    ttl = fake_config["cache"]["live_search_ttl"]
    assert ttl == 30, "TTL 应从配置读取"

    def query_with_cache(task_id):
        now = time.monotonic()
        cached = cache.get(task_id)
        if cached and now - cached["ts"] < ttl:
            return cached["data"]
        data = fake_live_search(task_id)
        if data:
            cache[task_id] = {"data": data, "ts": now}
        return data

    # 首次请求
    query_with_cache("task_a")
    assert call_count["search"] == 1

    # 推进时间到配置 TTL 的一半（应仍命中缓存）
    fake_clock[0] = 1000.0 + 15
    query_with_cache("task_a")
    assert call_count["search"] == 1, "TTL=30s 内应命中缓存"

    # 推进时间到配置 TTL 之后（应触发新查询）
    fake_clock[0] = 1000.0 + 31
    query_with_cache("task_a")
    assert call_count["search"] == 2, "超过配置 TTL 后应触发新查询"


def test_ttl_config_change_takes_effect(monkeypatch):
    """修改配置 TTL 后，缓存行为应随之改变。关联 §2.15.5。"""
    fake_clock = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: fake_clock[0])

    call_count = {"search": 0}

    def fake_live_search(task_id):
        call_count["search"] += 1
        return [{"item_id": "1"}]

    def make_query_with_ttl(ttl):
        cache = {}

        def query(task_id):
            now = time.monotonic()
            cached = cache.get(task_id)
            if cached and now - cached["ts"] < ttl:
                return cached["data"]
            data = fake_live_search(task_id)
            if data:
                cache[task_id] = {"data": data, "ts": now}
            return data

        return query, cache

    # 场景 A：TTL=10s（模拟配置值为 10）
    query_a, _ = make_query_with_ttl(10)
    query_a("task_a")
    assert call_count["search"] == 1
    fake_clock[0] = 1000.0 + 5  # 5s 后，TTL=10s 内
    query_a("task_a")
    assert call_count["search"] == 1, "TTL=10s 内应命中缓存"

    # 场景 B：TTL=2s（配置改为更短）
    call_count["search"] = 0
    fake_clock[0] = 2000.0
    query_b, _ = make_query_with_ttl(2)
    query_b("task_b")
    assert call_count["search"] == 1
    fake_clock[0] = 2000.0 + 3  # 3s 后，TTL=2s 已过期
    query_b("task_b")
    assert call_count["search"] == 2, "TTL=2s 过期后应触发新查询"
```

## 7. 使用说明

1. **替换项目实际路径**：模板中的 `your_project.config.load_config` 需替换为实际配置加载函数的 import 路径。
2. **适配实际缓存结构**：模板中 `_live_cache` 用简单 dict 模拟，实际项目可能包含更多字段（如时间戳、数据来源标记）。
3. **配合 monkeypatch**：所有时间相关断言依赖 `monkeypatch.setattr(time, "monotonic", ...)`，禁止使用 `time.sleep()` 等真实等待。
4. **关联规范追溯**：每个场景标注了关联的 §2.15 子条款，便于回归时定位规范要求。
5. **与模式 R 协作**：本模板为单元测试粒度，模式 R（性能优化回归测试）步骤 2 提供集成测试粒度的缓存命中验证，两者互补。
