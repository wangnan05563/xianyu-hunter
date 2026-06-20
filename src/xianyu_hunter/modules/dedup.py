"""增量去重器（设计文档 §6.2 / §6.3）"""
from __future__ import annotations

from xianyu_hunter.domain.item import ItemSummary
from xianyu_hunter.infra.repository import Repository


class ItemDedup:
    """基于商品 ID 的增量去重

    使用 Repository 批量查询已存在 ID，过滤出新发现的商品。
    """

    def __init__(self, repo: Repository):
        self.repo = repo

    async def filter_new(self, items: list[ItemSummary]) -> list[ItemSummary]:
        """过滤出数据库中不存在的商品"""
        if not items:
            return []
        ids = [it.id for it in items]
        existing = self.repo.items_exist(ids)
        new_items = [it for it in items if it.id not in existing]
        return new_items

    async def save(self, items: list[ItemSummary], task_id: str | None = None) -> int:
        """批量保存到 items 表（单次事务批量 upsert）

        task_id 用于关联商品到具体任务，使得前端可按任务查询商品列表。
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
