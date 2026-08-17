"""collector 包入口：re-export Collector 保持对外接口不变

历史导入路径 `from xianyu_hunter.modules.collector import Collector` 仍然有效。
具体实现拆分到子模块（_base / _search / _parser / _detail / core）。
"""
from xianyu_hunter.modules.collector.core import Collector

__all__ = ["Collector"]
