"""P0-3 LRU 缓存测试：验证 Buyer._task_item_set / Collector._seller_nicks /
_seller_profile_cache 的 LRU 驱逐行为，防止长跑进程内存无限增长。

测试覆盖：
1. LRUDict 基本操作（get/set/in/clear）与 dict 完全兼容
2. LRU 驱逐：超出 maxsize 时驱逐最旧条目
3. LRU 访问顺序：get 命中后该条目被视为最近访问，不被驱逐
4. maxsize=1 边界场景
5. Buyer._task_item_set 用 LRUDict[tuple, None] 模拟 set 语义
6. Collector._seller_nicks / _seller_profile_cache 用 LRUDict 替换 dict
"""
from __future__ import annotations

import pytest

from xianyu_hunter.infra.lru import LRUDict


# ============== LRUDict 单元测试 ==============


class TestLRUDictBasics:
    """验证 LRUDict 与 dict 完全兼容，外部调用方零改动"""

    def test_set_and_get(self):
        d: LRUDict[str, int] = LRUDict(maxsize=10)
        d["a"] = 1
        d["b"] = 2
        assert d["a"] == 1
        assert d["b"] == 2

    def test_contains(self):
        d: LRUDict[str, int] = LRUDict(maxsize=10)
        d["a"] = 1
        assert "a" in d
        assert "b" not in d

    def test_get_with_default(self):
        d: LRUDict[str, int] = LRUDict(maxsize=10)
        d["a"] = 1
        assert d.get("a") == 1
        assert d.get("missing") is None
        assert d.get("missing", "fallback") == "fallback"

    def test_clear(self):
        d: LRUDict[str, int] = LRUDict(maxsize=10)
        d["a"] = 1
        d["b"] = 2
        d.clear()
        assert len(d) == 0
        assert "a" not in d

    def test_len(self):
        d: LRUDict[str, int] = LRUDict(maxsize=10)
        assert len(d) == 0
        d["a"] = 1
        assert len(d) == 1
        d["b"] = 2
        assert len(d) == 2


class TestLRUEviction:
    """验证 LRU 驱逐行为"""

    def test_evict_oldest_when_exceed_maxsize(self):
        """超出 maxsize 时驱逐最旧条目（队首）"""
        d: LRUDict[str, int] = LRUDict(maxsize=3)
        d["a"] = 1
        d["b"] = 2
        d["c"] = 3
        # 插入第 4 个，应驱逐 "a"（最旧）
        d["d"] = 4
        assert "a" not in d
        assert d["b"] == 2
        assert d["c"] == 3
        assert d["d"] == 4
        assert len(d) == 3

    def test_get_updates_lru_order(self):
        """get 命中后该条目被视为最近访问，不会被驱逐"""
        d: LRUDict[str, int] = LRUDict(maxsize=3)
        d["a"] = 1
        d["b"] = 2
        d["c"] = 3
        # 访问 "a"，使其成为最近访问
        _ = d["a"]
        # 插入新条目应驱逐 "b"（最旧），而非 "a"
        d["e"] = 5
        assert "a" in d
        assert "b" not in d
        assert "c" in d
        assert "e" in d

    def test_set_existing_key_updates_value_and_order(self):
        """已存在的 key 更新值并提到队尾"""
        d: LRUDict[str, int] = LRUDict(maxsize=3)
        d["a"] = 1
        d["b"] = 2
        d["c"] = 3
        # 更新 "a" 的值
        d["a"] = 99
        # 插入新条目应驱逐 "b"（最旧），而非 "a"
        d["e"] = 5
        assert d["a"] == 99
        assert "b" not in d

    def test_maxsize_one(self):
        """maxsize=1 边界：每次写入都驱逐前一个"""
        d: LRUDict[str, int] = LRUDict(maxsize=1)
        d["a"] = 1
        assert len(d) == 1
        d["b"] = 2
        assert len(d) == 1
        assert "a" not in d
        assert d["b"] == 2

    def test_maxsize_zero_treated_as_one(self):
        """maxsize=0 视为 1，避免 popitem 抛 KeyError"""
        d: LRUDict[str, int] = LRUDict(maxsize=0)
        d["a"] = 1
        assert len(d) == 1


# ============== Buyer._task_item_set 集成测试 ==============


class TestBuyerTaskItemSetLRU:
    """验证 Buyer._task_item_set 使用 LRUDict 模拟 set 语义"""

    def test_task_item_set_is_lrudict(self):
        """Buyer._task_item_set 应为 LRUDict 类型（而非原生 set）"""
        from unittest.mock import MagicMock
        from xianyu_hunter.modules.buyer import Buyer
        from xianyu_hunter.infra.lru import LRUDict

        buyer = Buyer(
            browser=MagicMock(),
            repository=MagicMock(),
            event_bus=None,
        )
        assert isinstance(buyer._task_item_set, LRUDict)
        assert buyer._task_item_set.maxsize == 10000

    def test_task_item_set_supports_contains_and_assign(self):
        """LRUDict[tuple, None] 应支持 `in` 和 `[key]=None` 操作（set 语义）"""
        from unittest.mock import MagicMock
        from xianyu_hunter.modules.buyer import Buyer

        buyer = Buyer(
            browser=MagicMock(),
            repository=MagicMock(),
            event_bus=None,
        )
        key = ("t1", "i1")
        # set 语义用 LRUDict[key]=None 模拟
        buyer._task_item_set[key] = None
        assert key in buyer._task_item_set
        assert len(buyer._task_item_set) == 1


# ============== Collector 缓存集成测试 ==============


class TestCollectorCachesLRU:
    """验证 Collector._seller_nicks / _seller_profile_cache 使用 LRUDict"""

    def test_seller_nicks_is_lrudict(self):
        """Collector._seller_nicks 应为 LRUDict 类型"""
        from unittest.mock import MagicMock
        from xianyu_hunter.modules.collector._base import CollectorBase
        from xianyu_hunter.infra.lru import LRUDict

        collector = CollectorBase(
            browser=MagicMock(),
            antidetect=MagicMock(),
        )
        assert isinstance(collector._seller_nicks, LRUDict)
        assert collector._seller_nicks.maxsize == 2000

    def test_seller_profile_cache_is_lrudict(self):
        """Collector._seller_profile_cache 应为 LRUDict 类型"""
        from unittest.mock import MagicMock
        from xianyu_hunter.modules.collector._base import CollectorBase
        from xianyu_hunter.infra.lru import LRUDict

        collector = CollectorBase(
            browser=MagicMock(),
            antidetect=MagicMock(),
        )
        assert isinstance(collector._seller_profile_cache, LRUDict)
        assert collector._seller_profile_cache.maxsize == 2000

    def test_seller_nicks_evicts_when_full(self):
        """_seller_nicks 达到上限时驱逐最旧 seller_id"""
        from unittest.mock import MagicMock
        from xianyu_hunter.modules.collector._base import CollectorBase

        collector = CollectorBase(
            browser=MagicMock(),
            antidetect=MagicMock(),
        )
        # 测试用小 maxsize：直接替换实例字段
        collector._seller_nicks = LRUDict(maxsize=3)
        collector._seller_nicks["s1"] = "nick1"
        collector._seller_nicks["s2"] = "nick2"
        collector._seller_nicks["s3"] = "nick3"
        collector._seller_nicks["s4"] = "nick4"
        # s1 应被驱逐
        assert "s1" not in collector._seller_nicks
        assert collector._seller_nicks.get("s1", "") == ""
        assert collector._seller_nicks["s4"] == "nick4"

    def test_seller_profile_cache_clear_still_works(self):
        """clear_seller_profile_cache 方法应正常工作（向后兼容）"""
        from unittest.mock import MagicMock
        from xianyu_hunter.domain.seller import SellerProfile
        from xianyu_hunter.modules.collector._base import CollectorBase

        collector = CollectorBase(
            browser=MagicMock(),
            antidetect=MagicMock(),
        )
        # 直接测试 _seller_profile_cache 的 clear 行为
        # （clear_seller_profile_cache 在 _detail.py 中，依赖 Collector 完整实例）
        collector._seller_profile_cache["s1"] = SellerProfile(
            id="s1", nick="test", credit_score=700, register_days=365,
            on_sale_count=1, sold_count=0
        )
        assert len(collector._seller_profile_cache) == 1
        collector._seller_profile_cache.clear()
        assert len(collector._seller_profile_cache) == 0
