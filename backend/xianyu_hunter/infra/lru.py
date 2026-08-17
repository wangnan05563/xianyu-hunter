"""带容量上限的 LRU 字典，避免长跑进程内存无限增长。

为什么需要：Buyer._task_item_set / Collector._seller_nicks /
_seller_profile_cache 都是进程级常驻字典，无清理逻辑，跑数月会持续扩张。
cachetools 未引入项目，OrderedDict 自带的 move_to_end + popitem(last=False)
即可实现等价语义，零新依赖。

为什么不用 functools.lru_cache：lru_cache 是函数级缓存，无法按 key 增删。
"""
from __future__ import annotations

from collections import OrderedDict
from typing import KT, VT


class LRUDict(OrderedDict[KT, VT]):
    """带容量上限的 LRU 字典。

    继承 OrderedDict 是 dict 的子类，所有 dict 操作（.get / in / []= /
    .clear() / len()）完全兼容，外部调用方零改动。

    LRU 语义：
    - __setitem__：已存在的 key 提到队尾；新 key 入队后若超 maxsize 驱逐队首
    - __getitem__：命中时提到队尾（标记最近访问）
    - .get()：走 __getitem__ 维护顺序，避免 .get 命中时不更新 LRU
    """

    def __init__(self, maxsize: int = 2000) -> None:
        super().__init__()
        # maxsize 必须 >= 1，否则 popitem 会抛 KeyError
        self.maxsize = max(1, maxsize)

    def __setitem__(self, key: KT, value: VT) -> None:
        if key in self:
            # 已存在：先更新值再提到队尾，避免重复条目
            super().__setitem__(key, value)
            self.move_to_end(key)
            return
        super().__setitem__(key, value)
        # 超容量驱逐最旧条目（队首）
        if len(self) > self.maxsize:
            self.popitem(last=False)

    def __getitem__(self, key: KT) -> VT:
        value = super().__getitem__(key)
        # 命中后提到队尾，标记为最近访问
        self.move_to_end(key)
        return value

    def get(self, key: KT, default: VT | None = None) -> VT | None:
        # 重写 .get 以走 __getitem__，避免 OrderedDict.get 不维护 LRU 顺序
        if key in self:
            return self[key]
        return default
