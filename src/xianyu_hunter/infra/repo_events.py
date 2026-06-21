"""Events 领域数据访问 - 事件 CRUD + 运行历史聚合

提供：
- save_event / upsert_eval_event / list_events / get_event / update_event_payload / max_event_id
- get_task_runs / _aggregate_bucket（F-09 时间窗聚合）
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select

from xianyu_hunter.infra.db_models import _utcnow, EventRow
from xianyu_hunter.infra.repository_base import RepositoryBase


class EventsMixin:
    """Events 领域的 Repository 方法"""

    def save_event(self, event: dict) -> int:
        with self.engine.begin() as conn:
            result = conn.execute(EventRow.__table__.insert().values(**event))
            return result.inserted_primary_key[0]

    def upsert_eval_event(self, event: dict) -> int:
        """评估事件 upsert：按 (task_id, item_id, type) 去重

        防止 live_links 多次触发或 recompute 多次调用产生重复评估记录。
        利用数据库唯一索引 idx_eval_scored_unique 自动去重：
        - 先 DELETE 已有的相同 (task_id, item_id) eval.scored 记录
        - 再 INSERT 新记录，确保 payload 完全更新
        """
        task_id = event.get("task_id")
        item_id = event.get("item_id")
        event_type = event.get("type", "eval.scored")
        with self.engine.begin() as conn:
            # 先删除已有的相同 (task_id, item_id) eval.scored 记录
            conn.execute(
                EventRow.__table__.delete().where(
                    EventRow.task_id == task_id,
                    EventRow.item_id == item_id,
                    EventRow.type == event_type,
                )
            )
            # 插入新记录
            result = conn.execute(EventRow.__table__.insert().values(**event))
            return result.inserted_primary_key[0]

    def list_events(
        self,
        level: str | None = None,
        task_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
        since_id: int | None = None,
        ascending: bool = False,
    ) -> list[dict]:
        """列出事件（支持 SSE 回放 since_id 参数）"""
        with self.engine.connect() as conn:
            stmt = select(EventRow).order_by(
                EventRow.id.asc() if ascending else EventRow.created_at.desc()
            )
            if level:
                stmt = stmt.where(EventRow.level == level)
            if task_id:
                stmt = stmt.where(EventRow.task_id == task_id)
            if since_id is not None:
                stmt = stmt.where(EventRow.id > since_id)
            stmt = stmt.limit(limit).offset(offset)
            return [self._row_to_dict(r) for r in conn.execute(stmt).all()]

    def get_event(self, event_id: int) -> dict | None:
        """获取单条事件"""
        with self.engine.connect() as conn:
            row = conn.execute(select(EventRow).where(EventRow.id == event_id)).first()
            return self._row_to_dict(row) if row else None

    def update_event_payload(self, event_id: int, payload: str) -> None:
        """更新事件的 payload JSON"""
        with self.engine.begin() as conn:
            conn.execute(
                EventRow.__table__.update()
                .where(EventRow.id == event_id)
                .values(payload=payload)
            )

    def max_event_id(self) -> int:
        """获取当前 events 表最大 id（不存在时返回 0）"""
        with self.engine.connect() as conn:
            return int(conn.execute(select(func.max(EventRow.id))).scalar() or 0)

    def delete_events_by_task(self, task_id: str) -> int:
        """按任务删除所有关联事件"""
        with self.engine.begin() as conn:
            result = conn.execute(
                EventRow.__table__.delete().where(EventRow.task_id == task_id)
            )
            return result.rowcount or 0

    # ============== F-09 任务运行历史（按时间窗聚合 events） ==============
    def get_task_runs(
        self,
        task_id: str,
        range_hours: int = 24,
        window_minutes: int = 5,
        idle_gap_minutes: int = 30,
    ) -> dict[str, Any]:
        """按时间窗聚合 events 表中该 task_id 的运行记录"""
        now = _utcnow()
        start_time = now - timedelta(hours=range_hours)

        with self.engine.connect() as conn:
            rows = conn.execute(
                select(EventRow)
                .where(EventRow.task_id == task_id)
                .where(EventRow.created_at >= start_time)
                .where(EventRow.created_at <= now)
                .order_by(EventRow.created_at.asc())
            ).all()

        if not rows:
            return {
                "task_id": task_id,
                "runs": [], "idle_gaps": [],
                "total_runs": 0, "total_events": 0, "total_hits": 0,
            }

        window_td = timedelta(minutes=window_minutes)
        buckets: list[dict[str, Any]] = []
        current_bucket_start: datetime | None = None
        current_events: list[dict] = []

        for row in rows:
            ev = self._row_to_dict(row)
            ev_time = ev["created_at"]
            if isinstance(ev_time, str):
                ev_time = datetime.fromisoformat(ev_time)

            minutes_since_midnight = ev_time.hour * 60 + ev_time.minute
            bucket_minute = (minutes_since_midnight // window_minutes) * window_minutes
            bucket_start = ev_time.replace(hour=bucket_minute // 60, minute=bucket_minute % 60, second=0, microsecond=0)

            if current_bucket_start is None or bucket_start != current_bucket_start:
                if current_bucket_start is not None and current_events:
                    buckets.append(self._aggregate_bucket(current_bucket_start, current_events, window_minutes))
                current_bucket_start = bucket_start
                current_events = [ev]
            else:
                current_events.append(ev)

        if current_bucket_start is not None and current_events:
            buckets.append(self._aggregate_bucket(current_bucket_start, current_events, window_minutes))

        idle_gaps: list[dict[str, Any]] = []
        for i in range(1, len(buckets)):
            prev_end = buckets[i - 1]["end"]
            curr_start = buckets[i]["start"]
            if isinstance(prev_end, str):
                prev_end = datetime.fromisoformat(prev_end)
            if isinstance(curr_start, str):
                curr_start = datetime.fromisoformat(curr_start)
            gap_minutes = (curr_start - prev_end).total_seconds() / 60
            if gap_minutes > idle_gap_minutes:
                idle_gaps.append({
                    "from": prev_end.isoformat(),
                    "to": curr_start.isoformat(),
                    "duration_s": int((curr_start - prev_end).total_seconds()),
                })

        total_events = sum(b["event_count"] for b in buckets)
        total_hits = sum(b["hit_count"] for b in buckets)

        return {
            "task_id": task_id,
            "runs": buckets,
            "idle_gaps": idle_gaps,
            "total_runs": len(buckets),
            "total_events": total_events,
            "total_hits": total_hits,
        }

    @staticmethod
    def _aggregate_bucket(
        bucket_start: datetime,
        events: list[dict],
        window_minutes: int,
    ) -> dict[str, Any]:
        """将一个时间桶内的事件聚合为一条运行记录"""
        hit_stages = {"hit", "eval", "score", "match", "found"}
        hit_count = 0
        err_count = 0
        warn_count = 0
        first_event_type = events[0].get("stage", "")

        for ev in events:
            level = (ev.get("level") or "").lower()
            stage = (ev.get("stage") or "").lower()
            if level == "err":
                err_count += 1
            elif level == "warn":
                warn_count += 1
            if level == "info" and any(kw in stage for kw in hit_stages):
                hit_count += 1

        first_time = events[0].get("created_at")
        last_time = events[-1].get("created_at")
        if isinstance(first_time, str):
            first_time = datetime.fromisoformat(first_time)
        if isinstance(last_time, str):
            last_time = datetime.fromisoformat(last_time)
        duration_s = (last_time - first_time).total_seconds() if first_time and last_time else 0

        bucket_end = bucket_start + timedelta(minutes=window_minutes)

        return {
            "start": bucket_start.isoformat(),
            "end": bucket_end.isoformat(),
            "event_count": len(events),
            "hit_count": hit_count,
            "err_count": err_count,
            "warn_count": warn_count,
            "duration_s": round(duration_s, 1),
            "first_event_type": first_event_type,
        }
