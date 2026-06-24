"""Repository - SQLite 数据访问层（Mixin 组合架构）

设计文档 §5 DDL 的 DAO 封装。

重构说明（P2 代码质量优化）：
- 原文件 927 行单文件 → 拆分为 10 个职责清晰的 Mixin 子模块
- 本文件仅作为"组合门面"，通过多重继承聚合所有领域方法
- 对外 API 完全不变：container.repo.xxx() 调用无需任何改动

Mixin 分工：
- RepositoryBase (repository_base.py)     → 引擎初始化 / _row_to_dict / 通用查询工具
- TasksMixin      (repo_tasks.py)          → 任务 CRUD
- ItemsMixin      (repo_items.py)          → 商品 CRUD
- SellersMixin    (repo_sellers.py)        → 卖家 CRUD
- EvaluationsMixin(repo_evaluations.py)    → 评估记录 CRUD
- OrdersMixin     (repo_orders.py)         → 订单 CRUD
- EventsMixin     (repo_events.py)         → 事件 CRUD + 运行历史聚合
- TaskLinksMixin  (repo_links.py)          → 任务关联 CRUD
- TaskDepsMixin   (repo_deps.py)           → 任务依赖关系 CRUD
- NotificationsMixin(repo_notifications.py) → 业务通知 CRUD
"""
from __future__ import annotations

from xianyu_hunter.infra.repository_base import RepositoryBase, get_repository
from xianyu_hunter.infra.repo_tasks import TasksMixin
from xianyu_hunter.infra.repo_items import ItemsMixin
from xianyu_hunter.infra.repo_sellers import SellersMixin
from xianyu_hunter.infra.repo_evaluations import EvaluationsMixin
from xianyu_hunter.infra.repo_orders import OrdersMixin
from xianyu_hunter.infra.repo_events import EventsMixin
from xianyu_hunter.infra.repo_error_logs import ErrorLogsMixin
from xianyu_hunter.infra.repo_links import TaskLinksMixin
from xianyu_hunter.infra.repo_deps import TaskDepsMixin
from xianyu_hunter.infra.repo_notifications import NotificationsMixin


class Repository(
    RepositoryBase,
    TasksMixin,
    ItemsMixin,
    SellersMixin,
    EvaluationsMixin,
    OrdersMixin,
    EventsMixin,
    ErrorLogsMixin,
    TaskLinksMixin,
    TaskDepsMixin,
    NotificationsMixin,
):
    """SQLite 数据访问仓库（Mixin 组合模式）

    所有方法同步实现（SQLite + 单进程足够）。
    后续如需异步访问可加 async 包装层。
    """
    pass
