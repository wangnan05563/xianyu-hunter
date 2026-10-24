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

    def __init__(self, repo: Repository, bus=None):
        self.repo = repo
        # EventBus 引用：降价检测（price_watch）需要发布 PRICE_DROPPED 到通知渠道；
        # None 时降级为仅写事件时间线（测试场景）
        self.bus = bus

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

    def save(
        self,
        items: list[ItemSummary],
        task_id: str | None = None,
        user_id: str | None = None,
    ) -> int:
        """批量保存到 items 表（单次事务批量 upsert）

        task_id 用于关联商品到具体任务，使得前端可按任务查询商品列表。
        注意：items 表的 task_id 在 upsert 时会被覆盖为最后采集的任务，
        但 task_links 表的 UNIQUE 约束保证任务级关联不被重复写入。

        user_id 透传给降价检测（T02815）：采集 worker 在后台拿到的归属必须一路
        送到 add_notification，否则降价通知全落 default，真实用户看不到自己的提醒。
        None 时由仓储层兜底 default（与事件写入同口径）。
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
        written = self.repo.batch_upsert_items(dicts)
        # 价格快照落库 + 降价检测（PRD FR-F1-1/FR-F1-3，source=collect）。
        # FR-F1-5 冷启动抑制由 observe_prices 内部自动判定（全批无快照历史即首轮建快照），
        # 任何异常不阻断商品落库主流程
        try:
            from xianyu_hunter.modules.price_watch import observe_prices

            observe_prices(self.repo, self.bus, dicts, "collect", task_id=task_id, user_id=user_id)
        except Exception as e:  # noqa: BLE001
            import logging
            logging.getLogger(__name__).warning("价格快照/降价检测失败（不影响商品落库）: %s", e)
        return written
