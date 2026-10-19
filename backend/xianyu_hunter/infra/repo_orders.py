"""Orders 领域数据访问 - 订单 CRUD

提供：
- upsert_order / get_order / list_orders / find_order_by_task_item
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from xianyu_hunter.domain.order import OrderStatus
from xianyu_hunter.infra.db_models import OrderRow


def _status_condition(status: str | None):
    """把状态筛选值翻译成 WHERE 条件；None 表示不过滤

    T02585 起字面值与 OrderStatus 同源：不再为历史 pending 做别名合并
    （旧库中的 pending 行由 db_models 启动迁移归一为 pending_pay）。
    """
    if not status:
        return None
    return OrderRow.status == status


class OrdersMixin:
    """Orders 领域的 Repository 方法"""

    def upsert_order(self, order: dict, user_id: str | None = None) -> None:
        """按 id upsert 订单

        user_id 不为 None 时深度防御（与 upsert_eval_event 同语义）：
        - 字典未显式带 user_id 时注入，INSERT 路径自动落列
        - 冲突更新附加 WHERE，避免凭 id 覆盖他人订单
        api_orders 的接管/确认/取消/改状态四处都按 (order_id, user_id) 先读再写，
        这里补齐写入侧的同一道门。
        """
        if user_id is not None and "user_id" not in order:
            order["user_id"] = user_id
        with self.engine.begin() as conn:
            stmt = sqlite_insert(OrderRow).values(**order)
            update_cols = {c: stmt.excluded[c] for c in order.keys() if c != "id"}
            stmt = stmt.on_conflict_do_update(
                index_elements=["id"],
                set_=update_cols,
                where=(OrderRow.user_id == user_id) if user_id is not None else None,
            )
            conn.execute(stmt)

    def get_order(self, order_id: str, user_id: str | None = None) -> dict | None:
        with self.engine.connect() as conn:
            stmt = select(OrderRow).where(OrderRow.id == order_id)
            if user_id is not None:
                stmt = stmt.where(OrderRow.user_id == user_id)
            row = conn.execute(stmt).first()
            return self._row_to_dict(row) if row else None

    def list_orders(
        self,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
        task_id: str | None = None,
        item_id: str | None = None,
        user_id: str | None = None,
    ) -> list[dict]:
        with self.engine.connect() as conn:
            stmt = select(OrderRow).order_by(OrderRow.created_at.desc())
            if (cond := _status_condition(status)) is not None:
                stmt = stmt.where(cond)
            if task_id:
                stmt = stmt.where(OrderRow.task_id == task_id)
            if item_id:
                stmt = stmt.where(OrderRow.item_id == item_id)
            if user_id is not None:
                stmt = stmt.where(OrderRow.user_id == user_id)
            stmt = stmt.limit(limit).offset(offset)
            return [self._row_to_dict(r) for r in conn.execute(stmt).all()]

    def count_orders(
        self,
        status: str | None = None,
        task_id: str | None = None,
        item_id: str | None = None,
        user_id: str | None = None,
    ) -> int:
        with self.engine.connect() as conn:
            stmt = select(func.count(OrderRow.id))
            if (cond := _status_condition(status)) is not None:
                stmt = stmt.where(cond)
            if task_id:
                stmt = stmt.where(OrderRow.task_id == task_id)
            if item_id:
                stmt = stmt.where(OrderRow.item_id == item_id)
            if user_id is not None:
                stmt = stmt.where(OrderRow.user_id == user_id)
            return conn.execute(stmt).scalar() or 0

    def count_orders_by_status(
        self,
        task_id: str | None = None,
        item_id: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, int]:
        """按状态分组的**全量**计数（不受 status 筛选与分页影响）

        给订单页四张统计卡用：卡的分子（某状态条数）与列表分母同源——
        同 user_id / task_id / item_id 范围、同一次请求，而不是当前页 Python 端 filter。
        返回原始状态字面值 → 计数；状态名归一由调用方负责。
        """
        with self.engine.connect() as conn:
            stmt = select(OrderRow.status, func.count(OrderRow.id)).group_by(OrderRow.status)
            if task_id:
                stmt = stmt.where(OrderRow.task_id == task_id)
            if item_id:
                stmt = stmt.where(OrderRow.item_id == item_id)
            if user_id is not None:
                stmt = stmt.where(OrderRow.user_id == user_id)
            return {str(status or ""): int(n) for status, n in conn.execute(stmt).all()}

    def delete_order_by_id(self, order_id: str, user_id: str | None = None) -> int:
        """user_id 不为 None 时附加 WHERE 过滤，防止跨用户删除（深度防御）"""
        with self.engine.begin() as conn:
            stmt = OrderRow.__table__.delete().where(OrderRow.id == order_id)
            if user_id is not None:
                stmt = stmt.where(OrderRow.user_id == user_id)
            result = conn.execute(stmt)
            return result.rowcount or 0

    def find_order_by_task_item(
        self, task_id: str, item_id: str, user_id: str | None = None
    ) -> dict | None:
        """幂等查询：同 task 内该 item 是否已有非失败的订单"""
        with self.engine.connect() as conn:
            stmt = (
                select(OrderRow)
                .where(OrderRow.item_id == item_id)
                .where(OrderRow.task_id == task_id)
                .order_by(OrderRow.created_at.desc())
                .limit(1)
            )
            if user_id is not None:
                stmt = stmt.where(OrderRow.user_id == user_id)
            row = conn.execute(stmt).first()
            if not row:
                return None
            order = self._row_to_dict(row)
            if order.get("status") == "failed":
                return None
            return order

    def list_orders_by_item_ids(
        self, item_ids: list[str], include_failed: bool = False,
        user_id: str | None = None,
    ) -> dict[str, dict]:
        """批量查询多个商品的最新订单状态

        用于评估明细列表展示「订单状态」列，避免 N+1 查询。
        返回 {item_id: order_dict} 映射，每个 item 只保留最新一条订单。

        include_failed 控制是否包含 failed 订单：
        - False（默认）：跳过 failed 订单，用于「是否允许重新抢单」判断
        - True：保留 failed 订单，用于评估明细展示完整订单历史
        为什么需要 include_failed=True：评估明细需要展示失败记录，否则用户
        点击抢单失败后，刷新页面看到「—」会误以为没下过单而反复触发抢单。
        """
        if not item_ids:
            return {}
        result: dict[str, dict] = {}
        with self.engine.connect() as conn:
            stmt = (
                select(OrderRow)
                .where(OrderRow.item_id.in_(item_ids))
                .order_by(OrderRow.created_at.desc())
            )
            if user_id is not None:
                stmt = stmt.where(OrderRow.user_id == user_id)
            for row in conn.execute(stmt).all():
                order = self._row_to_dict(row)
                iid = order.get("item_id")
                if not iid or iid in result:
                    continue
                if not include_failed and order.get("status") == "failed":
                    continue
                result[iid] = order
        return result

    def delete_orders_by_task(self, task_id: str, user_id: str | None = None) -> int:
        """按任务删除所有关联订单

        user_id 不为 None 时附加 WHERE 过滤，防止跨用户删除（深度防御）。
        """
        with self.engine.begin() as conn:
            stmt = OrderRow.__table__.delete().where(OrderRow.task_id == task_id)
            if user_id is not None:
                stmt = stmt.where(OrderRow.user_id == user_id)
            result = conn.execute(stmt)
            return result.rowcount or 0

    def expire_takeover_pending_orders(
        self, timeout_minutes: int, user_id: str | None = None
    ) -> list[dict]:
        """将超时未确认支付的 takeover_pending 订单批量标记为 failed

        业务背景：用户点击「接管」后有 timeout_minutes（默认 30 分钟）在闲鱼 App
        完成支付。超时后闲鱼订单已被自动关闭，系统需同步状态避免用户误支付已关闭订单。

        状态机：takeover_pending → failed
        清空 confirmed_at：与 takeover_cancel 一致，让订单可被重新接管

        返回被超时清理的订单列表，供调用方发布事件/通知下游
        为什么一次 SQL 而非逐条 update：避免长事务和 N+1，且批量场景下性能更好

        user_id 不为 None 时仅清理该用户的超时订单（多用户隔离）；
        user_id=None 时跨用户清理（后台调度场景）。
        """
        from datetime import timedelta
        from sqlalchemy import update
        from xianyu_hunter.infra.db_models import _utcnow

        cutoff = _utcnow().replace(tzinfo=None) - timedelta(minutes=timeout_minutes)

        with self.engine.begin() as conn:
            # 先查询将要超时的订单（供返回）
            select_stmt = (
                select(OrderRow)
                .where(OrderRow.status == OrderStatus.TAKEOVER_PENDING.value)
                .where(OrderRow.confirmed_at.is_not(None))
                .where(OrderRow.confirmed_at < cutoff)
            )
            if user_id is not None:
                select_stmt = select_stmt.where(OrderRow.user_id == user_id)
            expired_orders = [self._row_to_dict(r) for r in conn.execute(select_stmt).all()]

            if not expired_orders:
                return []

            # 批量 update：status=failed, error=超时原因, confirmed_at=None
            update_stmt = (
                update(OrderRow)
                .where(OrderRow.id.in_([o["id"] for o in expired_orders]))
                .values(
                    status="failed",
                    error=f"接管超时未支付（{timeout_minutes} 分钟）",
                    confirmed_at=None,
                )
            )
            # select 已按 user_id 过滤，id 列表必然属于该用户，此处无需重复过滤
            conn.execute(update_stmt)

        # 同步内存中的字段，供调用方使用
        for o in expired_orders:
            o["status"] = "failed"
            o["error"] = f"接管超时未支付（{timeout_minutes} 分钟）"
            o["confirmed_at"] = None
        return expired_orders
