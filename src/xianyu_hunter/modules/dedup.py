"""增量去重器（设计文档 §6.2 / §6.3）

去重策略：按 task_id 隔离
- 不同任务可独立发现同一商品，避免全局去重导致后搜索的任务跳过
- 同一任务不重复处理已关联过的商品
- 为什么改用 task_links 而非 items 表：items 表的 task_id 在 upsert 时被覆盖，
  无法可靠区分"哪个任务已处理过"。task_links 的 UNIQUE(task_id, link_type, link_key)
  约束保证任务级关联唯一性。
"""
from __future__ import annotations

from xianyu_hunter.domain.item import ItemSummary
from xianyu_hunter.infra.repository import Repository


class ItemDedup:
    """基于任务级 task_links 关联的增量去重

    filter_new 查询 task_links 表中 (task_id, link_type='item') 已存在的 link_key，
    只返回当前任务尚未关联过的商品。
    """

    def __init__(self, repo: Repository):
        self.repo = repo

    def filter_new(self, items: list[ItemSummary], task_id: str) -> list[ItemSummary]:
        """过滤出当前任务尚未处理过的商品

        Args:
            items: 搜索到的商品列表
            task_id: 当前任务 ID，用于按任务隔离去重
        """
        if not items:
            return []
        ids = [it.id for it in items]
        existing = self.repo.get_existing_task_link_keys(task_id, "item", ids)
        return [it for it in items if it.id not in existing]

    def save(self, items: list[ItemSummary], task_id: str | None = None) -> int:
        """批量保存到 items 表（单次事务批量 upsert）

        task_id 用于关联商品到具体任务，使得前端可按任务查询商品列表。
        注意：items 表的 task_id 在 upsert 时会被覆盖为最后采集的任务，
        但 task_links 表的 UNIQUE 约束保证任务级关联不被重复写入。
        """
        if not items:
            return 0
        dicts = [
            {
                "id": it.id,
                "task_id": task_id,
                "title": it.title,
                "price": it.price,
                "region": it.region,
                "seller_id": it.seller_id,
                "want_cnt": it.want_cnt,
                "view_cnt": it.view_cnt,
                "publish_time": it.publish_time,
                "thumb_url": it.thumb_url,
            }
            for it in items
        ]
        return self.repo.batch_upsert_items(dicts)
