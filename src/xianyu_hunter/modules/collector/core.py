"""Collector 组合类：通过多继承组合各职责 Mixin

设计文档 §3.4 - 三个核心方法：
- search(keyword): 搜索 + 滚动加载
- detail(item_id): 商品详情
- seller_profile(seller_id): 卖家主页

依赖：BrowserManager（提供 page）+ AntiDetect（限流/反检测）+ Repository（去重）

拆分说明：
- 状态字段集中在 _base.CollectorBase
- 搜索流程在 _search.SearchMixin
- 解析逻辑在 _parser.ParserMixin
- 详情/卖家在 _detail.DetailMixin
- 本文件仅做组合，保持对外接口（Collector 类名）不变
"""
from __future__ import annotations

from xianyu_hunter.modules.collector._base import CollectorBase
from xianyu_hunter.modules.collector._detail import DetailMixin
from xianyu_hunter.modules.collector._parser import ParserMixin
from xianyu_hunter.modules.collector._search import SearchMixin


class Collector(SearchMixin, ParserMixin, DetailMixin, CollectorBase):
    """闲鱼数据采集器

    所有方法接收可选 page 参数用于测试注入（默认从 BrowserManager 获取）。

    通过 Mixin 组合实现职责分离，对外接口与原 collector.py 完全兼容。
    MRO 顺序：Search → Parser → Detail → Base，Base 在最后确保 __init__ 不被覆盖。
    """
    pass
