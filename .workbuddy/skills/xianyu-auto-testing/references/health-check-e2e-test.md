# 健康检查端到端测试（Health Check E2E Test）

> **测试场景编号**：T005 / T006 / T007
> **引入版本**：v4.69.0
> **关联规范**：[dual-data-source-consistency.md](../xianyu-hunter-dev/references/dual-data-source-consistency.md)
> **关联复盘**：[retrospective-2026-07-26-r3.md](../xianyu-hunter-dev/references/retrospective-2026-07-26-r3.md)
> **关联检查点**：B-REVIEW-332 / B-REVIEW-333 / B-REVIEW-334

---

## T005 健康检查端到端测试（JSON 无效 + 浏览器内存有效 → 健康检查通过）

### 场景描述

验证双数据源兜底复核机制：JSON 中 cookie 无效（过期/缺失/损坏），但浏览器运行时内存中 cookie 有效时，健康检查应通过浏览器内存兜底复核，返回 cookie_valid=true。

### 前置条件

1. Worker 浏览器已启动（`container.browser` 不为 None）
2. 浏览器内存中有有效 cookie（`_m_h5_tk` 未过期 + identity 层至少一个 + 关键 cookie 未过期）
3. JSON 文件被人为破坏或清空

### 测试步骤

```python
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from xianyu_hunter.web.services.cookie_store import get_cookie_store

@pytest.mark.asyncio
async def test_health_check_browser_fallback_when_json_invalid(monkeypatch):
    """T005: JSON 无效 + 浏览器内存有效 → 健康检查通过"""
    # Step 1: 构造 JSON 无效场景（无 cookie 数据）
    store = get_cookie_store()
    monkeypatch.setattr(store, "_read_json", lambda: None)
    
    # Step 2: 构造浏览器内存有效场景
    mock_container = MagicMock()
    mock_browser = MagicMock()
    future_ts = str(int((time.time() + 3600) * 1000))  # 未来 timestamp
    browser_cookies = [
        {"name": "_m_h5_tk", "value": f"valid_token_{future_ts}", "domain": ".goofish.com", "path": "/", "expires": -1},
        {"name": "_m_h5_tk_enc", "value": "enc_valid", "domain": ".goofish.com", "path": "/", "expires": -1},
        {"name": "unb", "value": "123456", "domain": ".goofish.com", "path": "/", "expires": -1},
        {"name": "cookie2", "value": "abc", "domain": ".goofish.com", "path": "/", "expires": -1},
    ]
    mock_browser.get_cookies = AsyncMock(return_value=browser_cookies)
    mock_container.browser = mock_browser
    
    # Step 3: 调用 cookie_checker
    with patch("xianyu_hunter.web.deps.get_container", return_value=mock_container):
        from xianyu_hunter.web.routes.api_anticrawl import _browser_cookies_fallback
        result = await _browser_cookies_fallback(orch=MagicMock())
    
    # Step 4: 验证兜底通过
    assert result is True, "JSON 无效但浏览器内存有效时，兜底应通过"
```

### 验证点

- [ ] JSON 无数据时，调用 `_browser_cookies_fallback` 返回 True
- [ ] JSON 中 `_m_h5_tk` 过期时，先尝试 `_try_refresh_m5tk_from_browser` 回写 JSON
- [ ] 回写成功后重新读 JSON 判定
- [ ] 回写失败时转浏览器内存兜底
- [ ] 浏览器内存兜底判定标准与实时搜索一致（_m_h5_tk + identity + 关键 cookie expires）

### 反向验证

```python
@pytest.mark.asyncio
async def test_health_check_fails_when_both_sources_invalid(monkeypatch):
    """T005 反向：JSON 无效 + 浏览器内存也无效 → 健康检查失败"""
    monkeypatch.setattr(store, "_read_json", lambda: None)
    mock_container = MagicMock()
    mock_browser = MagicMock()
    # 浏览器内存也无 _m_h5_tk
    mock_browser.get_cookies = AsyncMock(return_value=[])
    mock_container.browser = mock_browser
    
    with patch("xianyu_hunter.web.deps.get_container", return_value=mock_container):
        result = await _browser_cookies_fallback(orch=MagicMock())
    
    assert result is False, "双数据源都无效时，健康检查应失败"
```

---

## T006 双数据源一致性验证（MTOP Set-Cookie 回写失败 → warning 日志 + 兜底通过）

### 场景描述

验证回写失败可观测性：MTOP 搜索 API 响应的 Set-Cookie 回写 JSON 失败时，应触发 warning 级别日志（非 debug），且下次健康检查通过浏览器内存兜底通过。

### 测试步骤

```python
@pytest.mark.asyncio
async def test_m5tk_sync_failure_logs_warning(caplog):
    """T006: MTOP Set-Cookie 回写 JSON 失败应记 warning 日志"""
    import logging
    from xianyu_hunter.modules.collector._search import _sync_response_cookies_to_context
    
    # 构造 mock response 带 Set-Cookie 头
    mock_response = MagicMock()
    mock_response.headers = {"set-cookie": "_m_h5_tk=new_token_123; Path=/"}
    mock_response.url = "https://h5api.m.goofish.com/h5/mtop.relationsearch.wirelessrecommend.recommend/2.0/"
    
    mock_page = MagicMock()
    mock_page.context.add_cookies = AsyncMock()
    
    # 让 get_cookie_store().update_cookie_values 抛异常
    with patch("xianyu_hunter.web.services.cookie_store.get_cookie_store") as mock_get_store:
        mock_store = MagicMock()
        mock_store.update_cookie_values.side_effect = IOError("磁盘满")
        mock_get_store.return_value = mock_store
        
        with caplog.at_level(logging.WARNING):
            await _sync_response_cookies_to_context(mock_page, mock_response)
    
    # 验证 warning 级别日志
    warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("回写 JSON 失败" in r.message for r in warning_records), \
        "回写失败应记 warning 日志，而非 debug"
```

### 验证点

- [ ] `_sync_response_cookies_to_context` 回写失败时记 warning 日志
- [ ] 日志消息包含失败原因（如 "磁盘满"）
- [ ] 回写失败不影响浏览器内存的 cookie 同步（`page.context.add_cookies` 仍被调用）
- [ ] 下次健康检查时，JSON 中 token 陈旧，但浏览器内存兜底通过

### 反向验证（回归测试）

```python
def test_no_debug_level_swallow_for_sync_failure():
    """T006 反向：确保代码中不存在 debug 级别静默吞掉回写异常"""
    import inspect
    from xianyu_hunter.modules.collector import _search
    
    source = inspect.getsource(_search._sync_response_cookies_to_context)
    # 不应出现 debug 级别吞掉回写异常
    assert 'logger.debug("MTOP Set-Cookie 回写 JSON 失败' not in source, \
        "回写失败不应使用 debug 级别（应升级为 warning）"
    assert 'logger.warning("MTOP Set-Cookie 回写 JSON 失败' in source, \
        "回写失败应使用 warning 级别"
```

---

## T007 异步检查器兼容验证（sync/async 检查器均能被 _check_cookies 正确调用）

### 场景描述

验证检查器接口异步兼容性：`SessionHealthChecker._check_cookies` 应能正确处理 sync 和 async 两种检查器实现。

### 测试步骤

```python
@pytest.mark.asyncio
async def test_check_cookies_supports_sync_checker():
    """T007-a: _check_cookies 支持 sync 检查器"""
    from xianyu_hunter.modules.session_health import SessionHealthChecker
    
    checker = SessionHealthChecker()
    checker.set_cookie_checker(lambda: True)  # sync 检查器
    
    result = await checker._check_cookies()
    assert result is True

@pytest.mark.asyncio
async def test_check_cookies_supports_async_checker():
    """T007-b: _check_cookies 支持 async 检查器"""
    from xianyu_hunter.modules.session_health import SessionHealthChecker
    
    async def async_checker():
        await asyncio.sleep(0.01)  # 模拟 async 资源访问
        return True
    
    checker = SessionHealthChecker()
    checker.set_cookie_checker(async_checker)
    
    result = await checker._check_cookies()
    assert result is True

@pytest.mark.asyncio
async def test_check_cookies_supports_sync_returning_coroutine():
    """T007-c: _check_cookies 支持返回 coroutine 的同步函数"""
    from xianyu_hunter.modules.session_health import SessionHealthChecker
    
    async def inner():
        return True
    
    def sync_returning_coroutine():
        return inner()  # 同步函数返回 coroutine
    
    checker = SessionHealthChecker()
    checker.set_cookie_checker(sync_returning_coroutine)
    
    result = await checker._check_cookies()
    assert result is True
```

### 验证点

- [ ] sync 检查器（`lambda: bool`）能被正确调用
- [ ] async 检查器（`async def`）能被正确 await
- [ ] 返回 coroutine 的同步函数能被正确 await（`inspect.isawaitable` 兼容）
- [ ] 检查器抛异常时返回 False（不向上传播）
- [ ] 未设置检查器时返回 True（默认有效）

### 静态代码检查

```python
def test_check_cookies_uses_inspect_isawaitable():
    """T007 静态：确保 _check_cookies 用 inspect.isawaitable 而非 asyncio.iscoroutinefunction"""
    import inspect
    from xianyu_hunter.modules.session_health import SessionHealthChecker
    
    source = inspect.getsource(SessionHealthChecker._check_cookies)
    assert "inspect.isawaitable" in source, \
        "_check_cookies 应使用 inspect.isawaitable 兼容 async 检查器"
    assert "asyncio.iscoroutinefunction" not in source, \
        "不应使用 asyncio.iscoroutinefunction（无法处理返回 coroutine 的同步函数）"
```

---

## 测试覆盖矩阵

| 测试场景 | 编号 | 覆盖检查点 | 覆盖规范流程 |
|---------|------|-----------|-------------|
| JSON 无效 + 浏览器内存有效 → 健康检查通过 | T005 | B-REVIEW-332 | 流程 14 第 2 条 |
| MTOP Set-Cookie 回写失败 → warning 日志 | T006 | B-REVIEW-152 强 | 流程 15 |
| sync/async 检查器兼容 | T007 | B-REVIEW-334 | 流程 16 |
| 双数据源都无效 → 健康检查失败 | T005 反向 | B-REVIEW-332 | 流程 14 第 2 条 |
| 回写异常不使用 debug 静默 | T006 反向 | B-REVIEW-152 强 | 流程 15 |
| _check_cookies 用 inspect.isawaitable | T007 静态 | B-REVIEW-334 | 流程 16 |

---

## 关联

- **规范源**：[dual-data-source-consistency.md](../xianyu-hunter-dev/references/dual-data-source-consistency.md)
- **复盘**：[retrospective-2026-07-26-r3.md](../xianyu-hunter-dev/references/retrospective-2026-07-26-r3.md)
- **后端检查点**：B-REVIEW-332 / B-REVIEW-333 / B-REVIEW-334
- **前端检查点**：F-REVIEW-245
- **关联既有测试**：[cookie-token-consistency-test.md](cookie-token-consistency-test.md)（I-01 ~ I-11，本案补充 T005-T007）
