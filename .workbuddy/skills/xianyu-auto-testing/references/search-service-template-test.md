# 模式 AB：搜索服务模板方法模式回归测试

> **版本**：v2.4.0（2026-07-25 第九轮复盘落地）
> **关联复盘**：`xianyu-hunter-dev/references/retrospective-2026-07-25-r3.md`（第九轮复盘）
> **关联规范**：`xianyu-hunter-dev` 规范 19（搜索服务模板方法模式）+ coding-standards v1.3 §2.27
> **配套检查点**：
> - 后端：`xianyu-backend-code-review` v4.65.0 B-REVIEW-324~326

---

## 测试目标

验证后端搜索接口标准化机制（SearchService 抽象基类 + 4 钩子方法契约 + 慢查询日志）在不同触发场景下保持有效，防止"多个搜索接口重复实现分页/计数/慢查询日志缺失"问题再次出现。

## 测试范围

| 层 | 文件 | 检查点 |
|---|---|---|
| 后端服务层（基类） | `src/xianyu_hunter/web/services/search_base.py` | B-REVIEW-324 SEARCH-SERVICE-TEMPLATE |
| 后端服务层（子类） | `src/xianyu_hunter/web/services/search_items.py` 等 | B-REVIEW-325 SEARCH-HOOK-METHOD-CONTRACT |
| 后端日志层 | `src/xianyu_hunter/web/services/search_base.py`（`_maybe_log_slow`） | B-REVIEW-326 SEARCH-SLOW-QUERY-LOG |
| 测试层 | `tests/test_search_service_*.py` | 测试路由一致性 |

---

## 测试用例矩阵

### AB-T01：搜索接口计数与基类抽取必要性测试（B-REVIEW-324）

**场景**：项目内已存在 4 个搜索接口（items/sellers/logs/evaluations），必须抽取 SearchService 基类

**测试步骤**：
1. grep 所有 `@router.post`/`@router.get` 路由，过滤出搜索接口
2. 统计搜索接口总数 N
3. 验证 SearchService 基类存在性（路径 `template_method_pattern.base_class_path`）

**预期**：
- N ≥ `min_interfaces_to_extract`（默认 2）时，必须存在 SearchService 基类
- 基类必须包含 `search()` 入口方法
- 每个搜索接口的服务实现必须继承 SearchService

**测试代码示例**：
```python
def test_search_service_base_class_extracted_when_multiple_interfaces():
    """≥2 个搜索接口必须抽取 SearchService 基类"""
    search_services = discover_search_services()  # 扫描所有 search 接口

    assert len(search_services) >= 2  # 已有 4 个搜索接口
    assert Path("src/xianyu_hunter/web/services/search_base.py").exists()

    for svc in search_services:
        assert issubclass(svc.__class__, SearchService), f"{svc.__class__.__name__} 未继承 SearchService"
```

### AB-T02：4 钩子方法契约测试（B-REVIEW-325）

**场景**：每个搜索服务子类必须实现 4 个钩子方法，签名与基类一致

**测试步骤**：
1. 读取 SearchService 基类源码，提取 4 个钩子方法声明
2. 对每个子类，验证 4 个钩子方法存在且签名一致

**预期**：
- 基类声明 4 个钩子方法：`_build_query`/`_execute`/`_extract_facets`/`_paginate`
- 每个子类实现 4 个钩子方法，签名与基类一致
- `_paginate` 返回 `PaginationResult`，含 `items`/`total`/`page`/`page_size` 字段
- 子类未覆写 `search()` 入口方法

**测试代码示例**：
```python
def test_search_service_hook_method_contract():
    """4 钩子方法签名与返回类型契约"""
    from xianyu_hunter.web.services.search_base import SearchService
    from xianyu_hunter.web.services.search_items import ItemSearchService

    required_hooks = ["_build_query", "_execute", "_extract_facets", "_paginate"]
    for hook in required_hooks:
        assert hasattr(SearchService, hook), f"基类缺钩子方法 {hook}"
        assert hasattr(ItemSearchService, hook), f"子类缺钩子方法 {hook}"

    # 入口方法禁止覆写
    assert SearchService.search is not ItemSearchService.search.__func__ if hasattr(ItemSearchService, "search") else True
    # 若子类覆写了 search()，则违规
    assert "search" not in ItemSearchService.__dict__, "子类禁止覆写 search() 入口方法"
```

### AB-T03：5 步流程编排顺序测试（B-REVIEW-324）

**场景**：`search()` 方法必须按 `_build_query` → `_execute` → `_extract_facets` → `_paginate` → `_maybe_log_slow` 顺序调用

**测试步骤**：
1. 读取基类 `search()` 方法源码
2. 提取方法调用顺序
3. 验证顺序与 `template_method_pattern.orchestration_order` 一致

**预期**：
- 调用顺序必须为 `orchestration_order` 配置的顺序
- 不允许跳过任何步骤（即使 `_extract_facets` 返回 None，也必须调用）

### AB-T04：慢查询日志测试（B-REVIEW-326）

**场景**：构造慢查询场景（如全表 LIKE 查询），验证 `_maybe_log_slow` 输出日志

**测试步骤**：
1. 模拟查询耗时 > `slow_query_log.threshold_ms`（默认 500ms）
2. 验证日志输出
3. 验证日志字段集

**预期**：
- 慢查询日志包含 `elapsed_ms`/`service_class`/`query_keywords`/`total_count` 字段
- 日志级别为 `WARNING`
- `_maybe_log_slow` 在 `_execute` 之后调用

**测试代码示例**：
```python
def test_search_service_slow_query_log(caplog):
    """慢查询日志必须包含完整字段集"""
    import logging
    from xianyu_hunter.web.services.search_items import ItemSearchService

    caplog.set_level(logging.WARNING)

    # 构造慢查询场景（mock _execute 延迟 600ms）
    with mock.patch.object(ItemSearchService, "_execute", side_effect=_slow_execute):
        svc = ItemSearchService()
        await svc.search(SearchParams(keyword="test", page=1, page_size=20))

    # 验证日志
    slow_logs = [r for r in caplog.records if "slow_query" in r.getMessage().lower()]
    assert len(slow_logs) >= 1
    log = slow_logs[0]
    assert "elapsed_ms" in log.getMessage()
    assert "service_class" in log.getMessage()
    assert "query_keywords" in log.getMessage()
    assert "total_count" in log.getMessage()
```

### AB-T05：慢查询阈值配置源验证（B-REVIEW-326）

**场景**：慢查询阈值必须从 `config.yaml#search_service_template.slow_query_log.threshold_ms` 读取

**测试步骤**：
1. grep SearchService 基类源码，查找阈值引用
2. 验证无模块级硬编码常量（如 `_SLOW_THRESHOLD = 500`）

**预期**：
- 阈值从 config.yaml 读取
- 不存在模块级硬编码常量

**测试代码示例**：
```python
def test_search_service_slow_query_threshold_from_config():
    """慢查询阈值必须从 config.yaml 读取，禁止硬编码"""
    base_src = Path("src/xianyu_hunter/web/services/search_base.py").read_text()

    # 红旗模式：模块级硬编码阈值常量
    red_flags = [
        r"_SLOW_THRESHOLD\s*=\s*\d+",
        r"_SLOW_QUERY_MS\s*=\s*\d+",
        r"threshold\s*=\s*500\s*#.*硬编码",
    ]
    for pattern in red_flags:
        assert not re.search(pattern, base_src), f"发现硬编码阈值: {pattern}"
```

### AB-T06：测试路由一致性测试（跨技能交叉验证）

**场景**：测试 client 调用路径与方法必须与路由定义 1:1 对齐

**测试步骤**：
1. 从 `@router.post`/`@router.get` 装饰器提取路由定义
2. 从 pytest 测试用例提取 `client.post`/`client.get` 调用
3. 验证路径与方法对齐

**预期**：
- 测试调用路径与路由定义完全匹配（包括单复数）
- 测试 HTTP 方法与路由装饰器匹配

**历史失败案例**：
- 文件：`tests/test_chatbot_api_degraded.py`
- 问题：测试路径用复数 `/faqs` 但路由定义为单数 `/faq`，且测试用 PUT 但路由无 PUT 方法
- 修复：改为 `/faq` 并将 PUT 改为 POST upsert（带 id in body）

**测试代码示例**：
```python
def test_search_route_consistency():
    """测试 client 调用必须与路由定义 1:1 对齐"""
    route_defs = extract_route_definitions("src/xianyu_hunter/web/routes/")
    test_calls = extract_test_client_calls("tests/test_search_service_*.py")

    for call in test_calls:
        matching_route = find_matching_route(call, route_defs)
        assert matching_route is not None, f"测试调用 {call} 无匹配路由定义"
        assert call.method == matching_route.method, f"HTTP 方法不匹配: {call.method} vs {matching_route.method}"
```

---

## 静态扫描清单

| 扫描项 | grep 模式 | 严重等级 |
|---|---|---|
| 搜索接口未继承 SearchService | `class\s+\w+Search.*:.*$\n(?!.*SearchService)` | P0 |
| 子类覆写 search() 方法 | `def search\(self` 在子类文件中 | P0 |
| 慢查询阈值硬编码 | `_SLOW_THRESHOLD\s*=\s*\d+` | P1 |
| 慢查询日志字段缺失 | 检查 `logger.warning` 调用是否含 4 个必填字段 | P1 |
| 测试路径与路由不匹配 | 比对 `client.post/get` 与 `@router.post/get` | P1 |

---

## 运行时验证清单

| 验证项 | 方法 | 严重等级 |
|---|---|---|
| 5 步流程编排顺序 | 在 search() 中插入 trace，验证调用顺序 | P0 |
| 慢查询日志触发 | mock 慢查询，验证日志输出 | P1 |
| 钩子方法返回类型契约 | 调用钩子方法，验证返回类型 | P0 |
| 子类继承正确性 | `issubclass(sub, SearchService)` | P0 |

---

## 适用场景与不适用场景

| 流程 | 适用场景 | 不适用场景 |
|---|---|---|
| 基类抽取 | ≥2 个搜索接口 | 单搜索接口（无需抽象） |
| 钩子方法契约 | 搜索服务子类实现 | 基类内部辅助方法 |
| 慢查询日志 | SearchService 基类 | 单元测试 mock 日志 |
| 测试路由一致性 | 新增搜索接口测试 | 纯单元测试（不调用 client） |

---

## 跨技能联动

- **配套审查**：`xianyu-backend-code-review` v4.65.0 B-REVIEW-324~326
- **配套编码规范**：`xianyu-hunter-dev` 规范 19（搜索服务模板方法模式）
- **配套前端测试**：`xianyu-auto-testing` 模式 AC（useSearch/useSearchHistory Hook 测试）
- **配套复盘**：`xianyu-hunter-dev/references/retrospective-2026-07-25-r3.md`（第九轮复盘）
