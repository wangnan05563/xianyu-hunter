# 状态同步测试模板

> 关联编码规范：§2.16 状态同步规范
> 适用场景：Cookie/Token 状态校验、内存状态与存储数据一致性、多写入路径覆盖、过期状态检测。
> 配置节点：`config/tech-stack.json#hardConstraints.multiWritePathCheck`

## 1. 测试场景总览

| 场景 | 目标 | 关键 mock 对象 | 关联规范 |
|------|------|----------------|----------|
| 校验逻辑 | 未初始化状态不误报"有效" | 状态对象 | §2.16.1 |
| 同步方法 | 内存状态与存储数据一致 | 存储读写函数 | §2.16.2 |
| 所有路径覆盖 | 每条状态变更路径都调用同步 | 各写入入口函数 | §2.16.3 |
| 过期状态 | 过期 Cookie 正确报告"过期" | 时间函数 + Cookie 数据 | §2.16.4 |

## 2. 场景 1：校验逻辑测试

**目标**：构造未初始化状态（`_valid` 未设置），验证校验不误报"有效"。

**验证要点**：
- `_valid` 字段未初始化（None 或不存在）时，校验结果应为"无效"或"未初始化"
- 校验函数不因默认值（如 falsy 检查）而误判为"有效"
- 校验函数直接检查实际数据，而非仅依赖中间层状态

```python
import pytest


def test_uninitialized_state_not_reported_valid():
    """未初始化状态（_valid 未设置）不应误报为'有效'。关联 §2.16.1。"""
    # 模拟状态对象：_valid 未设置
    state = {}

    def validate_state(state_obj):
        # 直接检查 _valid 标志，None 视为未初始化 → 无效
        valid = state_obj.get("_valid")
        if valid is None:
            return False  # 未初始化 → 无效
        return bool(valid)

    # 未初始化状态
    assert validate_state(state) is False, "未初始化状态不应误报为'有效'"

    # 显式设置为 False
    state["_valid"] = False
    assert validate_state(state) is False

    # 显式设置为 True
    state["_valid"] = True
    assert validate_state(state) is True


def test_validation_checks_actual_data_not_only_flag():
    """校验函数应直接检查实际数据，而非仅依赖中间层状态。关联 §2.16.1。"""
    # 模拟中间层状态与实际数据不一致的场景
    layer_state = {"_valid": True}  # 中间层声称有效
    actual_cookies = {}  # 实际数据为空

    def validate_with_actual_data(layer_state, cookies):
        # 优先验证实际数据（§2.16.1：validateActualDataPreferred）
        if not cookies:
            return False  # 实际数据为空 → 无效
        # 实际数据有效时才信任中间层状态
        return layer_state.get("_valid", False)

    # 中间层有效但实际数据为空 → 应报告无效
    assert validate_with_actual_data(layer_state, actual_cookies) is False

    # 中间层有效且实际数据存在 → 应报告有效
    actual_cookies["token"] = "abc123"
    assert validate_with_actual_data(layer_state, actual_cookies) is True
```

## 3. 场景 2：同步方法测试

**目标**：调用 `sync_state_from_xxx()`，验证内存状态与存储数据一致。

**验证要点**：
- 同步后内存状态字段与存储数据一致
- 同步方法是幂等的（多次调用结果一致）
- 同步方法能检测并修复不一致

```python
import pytest


def test_sync_state_aligns_memory_with_storage():
    """调用 sync_state_from_xxx() 后，内存状态应与存储数据一致。关联 §2.16.2。"""
    # 模拟存储数据
    storage_data = {
        "cookies": {"token": "abc123", "expires": 9999999999},
        "last_refresh": 1000.0,
    }

    # 模拟内存状态（与存储不一致）
    memory_state = {"_valid": False, "cookies": {}, "last_refresh": 0}

    def sync_state_from_storage(state, storage):
        """同步方法：从存储数据更新内存状态。"""
        state["cookies"] = storage["cookies"].copy()
        state["last_refresh"] = storage["last_refresh"]
        # 根据实际数据计算 _valid（而非信任旧值）
        state["_valid"] = bool(storage["cookies"].get("token"))

    # 同步前：内存状态与存储不一致
    assert memory_state["_valid"] is False
    assert memory_state["cookies"] == {}

    # 执行同步
    sync_state_from_storage(memory_state, storage_data)

    # 同步后：内存状态应与存储一致
    assert memory_state["_valid"] is True
    assert memory_state["cookies"] == storage_data["cookies"]
    assert memory_state["last_refresh"] == storage_data["last_refresh"]


def test_sync_method_is_idempotent():
    """同步方法应幂等：多次调用结果一致。关联 §2.16.2。"""
    storage_data = {"cookies": {"token": "abc"}, "last_refresh": 1000.0}
    memory_state = {"_valid": False, "cookies": {}, "last_refresh": 0}

    def sync_state_from_storage(state, storage):
        state["cookies"] = storage["cookies"].copy()
        state["last_refresh"] = storage["last_refresh"]
        state["_valid"] = bool(storage["cookies"].get("token"))

    # 多次同步
    sync_state_from_storage(memory_state, storage_data)
    snapshot = {
        "_valid": memory_state["_valid"],
        "cookies": memory_state["cookies"].copy(),
        "last_refresh": memory_state["last_refresh"],
    }

    sync_state_from_storage(memory_state, storage_data)
    sync_state_from_storage(memory_state, storage_data)

    # 多次同步后状态不变
    assert memory_state == snapshot
```

## 4. 场景 3：所有路径覆盖测试

**目标**：枚举所有状态变更路径（登录成功/Token刷新/外部导入），验证每条都调用同步方法。

**验证要点**：
- 每条写入路径（登录成功、Token 刷新、外部导入）都调用同步方法
- 未调用同步的写入路径会被检测为缺陷
- 同步方法在写入完成后被调用（而非写入前）

```python
import pytest
from unittest.mock import MagicMock


def test_all_write_paths_call_sync():
    """所有状态变更路径都应调用同步方法。关联 §2.16.3。"""
    sync_mock = MagicMock()

    # 定义三条写入路径
    def on_login_success(cookies, sync_fn):
        """路径 1：登录成功"""
        # 写入 cookie 存储...
        sync_fn()  # 必须调用同步

    def on_token_refresh(new_token, sync_fn):
        """路径 2：Token 刷新"""
        # 更新 token...
        sync_fn()  # 必须调用同步

    def on_external_import(cookies_data, sync_fn):
        """路径 3：外部导入"""
        # 导入 cookie...
        sync_fn()  # 必须调用同步

    # 执行每条路径
    on_login_success({"token": "abc"}, sync_mock)
    assert sync_mock.call_count == 1, "登录成功路径应调用同步"

    on_token_refresh("new_token", sync_mock)
    assert sync_mock.call_count == 2, "Token 刷新路径应调用同步"

    on_external_import({"token": "xyz"}, sync_mock)
    assert sync_mock.call_count == 3, "外部导入路径应调用同步"


def test_write_path_without_sync_detected_as_defect():
    """未调用同步的写入路径应被检测为缺陷。关联 §2.16.3。"""
    sync_mock = MagicMock()

    # 故意不调用同步的写入路径（模拟缺陷）
    def buggy_login_success(cookies, sync_fn):
        """路径 1：登录成功（缺陷版本——未调用同步）"""
        # 写入 cookie 存储...
        pass  # 缺少 sync_fn() 调用

    buggy_login_success({"token": "abc"}, sync_mock)

    # 验证缺陷被检测到：同步未被调用
    assert sync_mock.call_count == 0, "此路径未调用同步，应标记为 P0 缺陷"


def test_sync_called_after_write_not_before():
    """同步方法应在写入完成后调用，而非写入前。关联 §2.16.3。"""
    call_order = []

    def sync_fn():
        call_order.append("sync")

    def on_login_success(cookies, sync_fn):
        call_order.append("write_start")
        # 执行写入...
        call_order.append("write_end")
        sync_fn()  # 写入完成后同步

    on_login_success({"token": "abc"}, sync_fn)

    # 验证调用顺序：写入完成后才同步
    assert call_order == ["write_start", "write_end", "sync"], "同步应在写入完成后调用"
```

## 5. 场景 4：过期状态测试

**目标**：构造过期 Cookie（`expires < now`），验证校验正确报告"过期"。

**验证要点**：
- Cookie 的 `expires` 字段小于当前时间时，校验报告"过期"
- 过期 Cookie 不应因中间层状态有效而被误判
- 校验函数正确读取并比较 `expires` 字段

```python
import time
import pytest


def test_expired_cookie_reported_correctly(monkeypatch):
    """过期 Cookie（expires < now）应被正确报告为'过期'。关联 §2.16.4。"""
    # 固定当前时间
    now = 2000000.0
    monkeypatch.setattr(time, "time", lambda: now)

    def validate_cookie_expires(cookie):
        """校验 Cookie 是否过期。"""
        expires = cookie.get("expires")
        if expires is None:
            return "no_expires"  # 无过期字段
        if expires < time.time():
            return "expired"
        return "valid"

    # 过期 Cookie
    expired_cookie = {"token": "abc", "expires": now - 100}
    assert validate_cookie_expires(expired_cookie) == "expired", "过期 Cookie 应报告'过期'"

    # 有效 Cookie
    valid_cookie = {"token": "abc", "expires": now + 3600}
    assert validate_cookie_expires(valid_cookie) == "valid"

    # 无过期字段
    no_expires_cookie = {"token": "abc"}
    assert validate_cookie_expires(no_expires_cookie) == "no_expires"


def test_expired_cookie_not_masked_by_valid_flag(monkeypatch):
    """过期 Cookie 不应因中间层 _valid=True 而被误判为有效。关联 §2.16.4。"""
    now = 2000000.0
    monkeypatch.setattr(time, "time", lambda: now)

    # 中间层状态声称有效，但实际 Cookie 已过期
    layer_state = {"_valid": True}
    expired_cookie = {"token": "abc", "expires": now - 100}

    def validate_with_priority(layer_state, cookie):
        """优先检查实际数据（expires），而非仅依赖中间层状态。"""
        expires = cookie.get("expires")
        if expires is not None and expires < time.time():
            return "expired"  # 实际数据过期 → 直接报告
        # 实际数据未过期时才参考中间层状态
        return "valid" if layer_state.get("_valid") else "invalid"

    # 中间层有效但 Cookie 过期 → 应报告"过期"
    result = validate_with_priority(layer_state, expired_cookie)
    assert result == "expired", "过期 Cookie 不应被中间层状态掩盖"


def test_expires_field_preserved_in_storage():
    """Cookie 存储应保留 expires 字段，不丢弃。关联 §2.16.4。"""
    # 模拟从存储读取的 Cookie
    stored_cookies = [
        {"name": "token", "value": "abc", "expires": 2000100},
        {"name": "session", "value": "xyz", "expires": 2000200},
    ]

    # 验证每个 Cookie 都保留了 expires 字段
    for cookie in stored_cookies:
        assert "expires" in cookie, f"Cookie '{cookie['name']}' 应保留 expires 字段"
        assert isinstance(cookie["expires"], (int, float)), "expires 应为数值类型"
```

## 6. 使用说明

1. **替换项目实际方法名**：模板中的同步方法名（如 `sync_state_from_storage`）需替换为项目实际方法名（如 `sync_state_from_cookies`）。
2. **适配实际状态结构**：模板中用简单 dict 模拟状态对象，实际项目可能使用 dataclass 或自定义类。
3. **配合 monkeypatch**：过期测试中时间相关断言依赖 `monkeypatch.setattr(time, "time", ...)`，禁止使用 `time.sleep()`。
4. **路径枚举完整性**：场景 3 的写入路径列表应与 `config/tech-stack.json#hardConstraints.multiWritePathCheck.writeEntryPatterns` 保持一致。
5. **关联规范追溯**：每个场景标注了关联的 §2.16 子条款，便于回归时定位规范要求。
6. **与模式 T 协作**：本模板为单元测试粒度，模式 T（多写入路径状态一致性测试）提供静态扫描 + 集成测试粒度，两者互补。
