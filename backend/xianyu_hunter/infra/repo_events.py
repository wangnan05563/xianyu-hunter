"""Events 领域数据访问 - 事件 CRUD + 运行历史聚合

提供：
- save_event / upsert_eval_event / list_events / get_event / update_event_payload / max_event_id
- list_events_by_request（按 request_id 检索链路日志）
- get_task_runs / _aggregate_bucket（F-09 时间窗聚合）
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select

from xianyu_hunter.domain.events import level_literals
from xianyu_hunter.infra.db_models import _utcnow, EventRow
from xianyu_hunter.infra.lru import LRUDict

# task_id → 归属用户 的内存缓存容量：任务归属创建后不变，命中后无需再查
_TASK_OWNER_CACHE_MAX = 2000


def _parse_event_time(value: Any) -> datetime:
    """把事件 created_at 统一解析为 datetime（字符串走 fromisoformat，datetime 直通）

    集中处理避免每个聚合函数重复 isinstance 判断（S3776）。
    """
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return value


def _compute_bucket_start(ev_time: datetime, window_minutes: int) -> datetime:
    """按时间窗对齐计算桶起始时间（截断到 window_minutes 整数倍）"""
    minutes_since_midnight = ev_time.hour * 60 + ev_time.minute
    bucket_minute = (minutes_since_midnight // window_minutes) * window_minutes
    return ev_time.replace(
        hour=bucket_minute // 60, minute=bucket_minute % 60, second=0, microsecond=0
    )


def _flush_current_bucket(
    buckets: list[dict[str, Any]],
    current_bucket_start: datetime | None,
    current_events: list[dict],
    aggregate_bucket,
    window_minutes: int,
) -> None:
    """提交当前桶到结果列表（仅在有起始时间和事件数据时）"""
    if current_bucket_start is not None and current_events:
        buckets.append(aggregate_bucket(current_bucket_start, current_events, window_minutes))


def _aggregate_events_into_buckets(
    events: list[dict],
    window_minutes: int,
    aggregate_bucket,
) -> list[dict[str, Any]]:
    """将事件按时间窗聚合到桶（接受 aggregate_bucket 回调以保持与类的解耦）

    为什么独立：get_task_runs 中桶聚合逻辑含嵌套 if 判断
    （current_bucket_start is None / bucket_start != current_bucket_start /
    current_bucket_start is not None and current_events），提取后主函数变为线性流程，
    且聚合逻辑可独立测试。
    """
    buckets: list[dict[str, Any]] = []
    current_bucket_start: datetime | None = None
    current_events: list[dict] = []

    for ev in events:
        ev_time = _parse_event_time(ev["created_at"])
        bucket_start = _compute_bucket_start(ev_time, window_minutes)

        if current_bucket_start is None or bucket_start != current_bucket_start:
            _flush_current_bucket(buckets, current_bucket_start, current_events, aggregate_bucket, window_minutes)
            current_bucket_start = bucket_start
            current_events = [ev]
        else:
            current_events.append(ev)

    _flush_current_bucket(buckets, current_bucket_start, current_events, aggregate_bucket, window_minutes)

    return buckets


# 命中关键词集合：level=info 且 stage 含这些词时计为一次命中
_HIT_STAGES = {"hit", "eval", "score", "match", "found"}


def _count_event_levels(events: list[dict]) -> tuple[int, int, int]:
    """统计事件列表中的 hit/err/warn 计数，返回 (hit_count, err_count, warn_count)

    独立出 _aggregate_bucket 的循环以降低其认知复杂度（S3776）。
    """
    hit_count = 0
    err_count = 0
    warn_count = 0
    for ev in events:
        level = (ev.get("level") or "").lower()
        stage = (ev.get("stage") or "").lower()
        if level == "err":
            err_count += 1
        elif level == "warn":
            warn_count += 1
        if level == "info" and any(kw in stage for kw in _HIT_STAGES):
            hit_count += 1
    return hit_count, err_count, warn_count


def _compute_idle_gaps(buckets: list[dict[str, Any]], idle_gap_minutes: int) -> list[dict[str, Any]]:
    """计算桶之间的空闲间隔（超过 idle_gap_minutes 阈值的间隔）

    为什么独立：get_task_runs 中空闲间隔计算含嵌套 isinstance 判断
    （prev_end / curr_start 都可能为 str），提取后主函数变为线性流程。
    """
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
    return idle_gaps


def _active_user_id_for_background_write() -> str:
    """后台/无 request 上下文时，事件应归属的用户 ID（T02684）

    与 cookie 读写用的是同一个口径（`get_active_user_id()`：最近活跃的
    非 default 用户，取不到降级 "default"），因此不会出现
    「日志归 A、cookie 归 B」两套真相。

    延迟 import：user_manager 属 web 层，infra 顶层 import 会造成循环依赖。
    任何异常都降级 "default"——日志归属错了可查，写入失败会直接吞掉事件。
    """
    try:
        from xianyu_hunter.web.services.user_manager import get_user_manager

        return get_user_manager().get_active_user_id() or "default"
    except Exception:  # noqa: BLE001 - 后台写入路径不得因用户体系未就绪而失败
        return "default"


def _sync_score_value(event: dict) -> None:
    """从 payload JSON 中提取 score 同步写入 score_value 列（P1-3 优化）

    为什么独立：save_event 与 upsert_eval_event 两条写入路径都需要相同的列化逻辑，
    提取后避免重复实现。仅 eval.scored 类型且 payload 含 score 字段时写入；
    其他事件保持 score_value=None，不影响联合索引选择性。

    幂等：event 已显式设置 score_value 时跳过，允许调用方覆盖。
    """
    # 已显式设置则不覆盖（保留调用方控制权）
    if "score_value" in event:
        return
    if event.get("type") != "eval.scored":
        return
    payload_raw = event.get("payload")
    if not payload_raw:
        return
    # payload 可能是 str（已序列化）或 dict（调用方未序列化）
    if isinstance(payload_raw, (dict,)):
        score = payload_raw.get("score")
    else:
        try:
            payload = json.loads(payload_raw)
            score = payload.get("score") if isinstance(payload, dict) else None
        except (json.JSONDecodeError, TypeError):
            return
    # 仅写入数值型 score；非数值（如 None / 字符串）保持 NULL
    if isinstance(score, (int, float)):
        event["score_value"] = float(score)


class EventsMixin:
    """Events 领域的 Repository 方法"""

    def _task_owner_user_id(self, task_id: str) -> str | None:
        """按 task_id 反查任务归属用户（T02801）

        后台线程（worker / scheduler / notifier）写事件时都得知道「这条属于谁」，
        但它们没有 request 上下文。原先统一取 `get_active_user_id()`（最后活跃用户），
        多账号同时跑任务时会把甲的事件写到乙名下：甲看不到自己的日志，乙的列表混入他人记录。

        优先反查 tasks.user_id 才是事实来源；这里带 LRU 缓存，避免每条日志一次 SELECT。
        缓存按 Repository 实例持有（而不是模块级），防止测试或换库时跨实例串味；
        任务归属创建后不变，因此命中后无需失效。
        查不到 / 查询异常返回 None，由调用方降级——归属错了日志还可追查，写入失败会直接丢事件。
        """
        cache: LRUDict[str, str] | None = getattr(self, "_task_owner_cache", None)
        if cache is None:
            cache = LRUDict(maxsize=_TASK_OWNER_CACHE_MAX)
            self._task_owner_cache = cache
        owner = cache.get(task_id)
        if owner:
            return owner
        try:
            task = self.get_task(task_id)
        except Exception:  # noqa: BLE001 - 归属查询失败只降级，不得阻断事件落库
            return None
        owner = (task or {}).get("user_id")
        if owner:
            cache[task_id] = owner
        return owner

    def save_event(self, event: dict) -> int:
        # T02883：type 没有可推断的默认值，缺失必须报错而不是静默落 NULL。
        # EventRow.type 是 nullable，漏写不报数据库错，代价是行还在但时间线只能显示通用「事件」，
        # 订阅过滤（按 type 精确匹配）把整行筛掉 —— 比抛错更难排查。
        # 对比：request_id / user_id 有 ContextVar 与活跃用户可推断，所以那里是补默认值。
        if not event.get("type"):
            raise ValueError(
                f"save_event 缺少 type（stage={event.get('stage')}）："
                "事件类型必须显式指定，落 NULL 会让时间线标签与订阅过滤双双失效"
            )
        # 自动注入 request_id：调用方未显式指定时从 ContextVar 读取
        # 确保同一请求触发的所有事件都被关联到同一流水号
        if "request_id" not in event or not event.get("request_id"):
            from xianyu_hunter.infra.request_context import get_request_id
            rid = get_request_id()
            if rid:
                event["request_id"] = rid
        # 多用户隔离（写侧）：调用方未指定归属时的取值顺序（T02684 → T02801）
        #   1. 事件带 task_id → 反查 tasks.user_id（事实来源，带缓存）；
        #   2. 否则/查不到 → 当前活跃用户（旧口径，单用户部署下等价）；
        #   3. 仍取不到 → "default"。
        # 为什么集中在单一入口而不是逐个改 12 处调用点：
        #   - EventRow.user_id NOT NULL 且有列默认值，散落调用点漏传时静默落成 "default"，
        #     读侧一旦按用户过滤，非 default 用户的日志页会直接空掉（比泄露更难排查）；
        #   - 单一入口保证「新增写入点默认就是归属正确的」，无需再来一次全站清点。
        # 为什么不再只用活跃用户近似（T02801）：调度器启动时加载所有用户的任务
        # （startup.list_tasks() 不带过滤），多账号并发下「最后活跃」会把 A 的日志写到 B 名下。
        if not event.get("user_id"):
            task_id = event.get("task_id")
            owner = self._task_owner_user_id(task_id) if task_id else None
            event["user_id"] = owner or _active_user_id_for_background_write()
        # P1-3：eval.scored 事件同步写入 score_value 列，避免 json_extract 全表扫描
        _sync_score_value(event)
        with self.engine.begin() as conn:
            result = conn.execute(EventRow.__table__.insert().values(**event))
            return result.inserted_primary_key[0]

    def upsert_eval_event(self, event: dict, user_id: str | None = None) -> int:
        """评估事件 upsert：按 (task_id, item_id, type) 去重

        防止 live_links 多次触发或 recompute 多次调用产生重复评估记录。
        利用数据库唯一索引 idx_eval_scored_unique 自动去重：
        - 先 DELETE 已有的相同 (task_id, item_id) eval.scored 记录
        - 再 INSERT 新记录，确保 payload 完全更新

        为什么用 DELETE+INSERT 而非 ON CONFLICT DO UPDATE：
        idx_eval_scored_unique 是部分唯一索引（WHERE type='eval.scored'），
        SQLite 的 UPSERT（ON CONFLICT）不支持部分唯一索引，
        因此用 DELETE+INSERT 实现 upsert 语义。
        整个操作在 engine.begin() 事务内执行，SQLite 序列化写入，
        不存在并发 DELETE+INSERT 导致的重复插入问题。

        user_id 不为 None 时（深度防御）：
        - DELETE 附加 user_id 过滤，防止跨用户误删对方评估记录
        - INSERT 时若 event 未显式设置 user_id，注入到 event 字典
        与 list_events / update_event_payload 等 user_id 参数语义一致。
        """
        task_id = event.get("task_id")
        item_id = event.get("item_id")
        # T02883：兜底值必须同时落到 INSERT 上。原先 `event.get("type", "eval.scored")`
        # 只喂给 DELETE 过滤，INSERT 走原始 event 字典 —— 调用方漏写（或写成空串）时
        # 行以 type=NULL 落库：时间线看不出类型、按 type 的订阅过滤整行筛掉，
        # 而 idx_eval_scored_unique 是 WHERE type='eval.scored' 的部分索引，NULL 行不受它约束
        # → 去重也一起失效（同一个坑的两种症状）。
        event_type = event.get("type") or "eval.scored"
        event["type"] = event_type
        # 调用方通过 user_id 关键字传入时，统一注入 event 字典，
        # 让 INSERT 路径自动写入 EventRow.user_id 列
        if user_id is not None and "user_id" not in event:
            event["user_id"] = user_id
        # ⚠ 这里**不**套用 save_event 的活跃用户兜底：本方法的 DELETE 过滤条件
        # 直接取自入参 user_id，若 INSERT 归属被改写而 DELETE 仍是旧值，
        # idx_eval_scored_unique 局部唯一索引会让 INSERT 撞 IntegrityError。
        # 评估事件的归属由调用方显式负责（evaluations_* 路由均传 request.state.user_id）。
        # P1-3：同步提取 score 到 score_value 列（仅 eval.scored 类型有效）
        _sync_score_value(event)
        with self.engine.begin() as conn:
            # 先删除已有的相同 (task_id, item_id, type) eval.scored 记录
            # 附加 user_id 过滤防止跨用户误删（与 list_events 的 user_id 隔离语义一致）
            delete_stmt = EventRow.__table__.delete().where(
                EventRow.task_id == task_id,
                EventRow.item_id == item_id,
                EventRow.type == event_type,
            )
            if user_id is not None:
                delete_stmt = delete_stmt.where(EventRow.user_id == user_id)
            conn.execute(delete_stmt)
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
        user_id: str | None = None,
    ) -> list[dict]:
        """列出事件（支持 SSE 回放 since_id 参数）"""
        with self.engine.connect() as conn:
            stmt = select(EventRow).order_by(
                EventRow.id.asc() if ascending else EventRow.created_at.desc()
            )
            if level:
                # 别名组匹配（err/error、warn/warning）：表内字面值历史上不统一，
                # 精确相等会让「筛 WARN」漏掉全部 warning 行
                literals = level_literals(level)
                if literals:
                    stmt = stmt.where(EventRow.level.in_(literals))
            if task_id:
                stmt = stmt.where(EventRow.task_id == task_id)
            if since_id is not None:
                stmt = stmt.where(EventRow.id > since_id)
            if user_id is not None:
                stmt = stmt.where(EventRow.user_id == user_id)
            stmt = stmt.limit(limit).offset(offset)
            return [self._row_to_dict(r) for r in conn.execute(stmt).all()]

    def list_events_by_type_prefix(
        self,
        type_prefix: str,
        task_id: str | None = None,
        limit: int = 50000,
        offset: int = 0,
        user_id: str | None = None,
    ) -> tuple[list[dict], int]:
        """按 type 前缀过滤事件，返回 (rows, total)

        为什么单独提供此方法：list_evaluations 需要按 eval.* 前缀过滤，
        之前用 list_events(limit=N*4) 在 Python 端过滤，当非 eval 事件多时
        会遗漏数据且 total 不准。这里在 SQL 端用 LIKE 过滤并返回准确 total。
        默认 limit=50000 是评估事件量级的上限（按 task_id+item_id 去重后可控）。
        """
        with self.engine.connect() as conn:
            stmt = select(EventRow).where(EventRow.type.like(f"{type_prefix}%"))
            if task_id:
                stmt = stmt.where(EventRow.task_id == task_id)
            if user_id is not None:
                stmt = stmt.where(EventRow.user_id == user_id)
            stmt = stmt.order_by(EventRow.created_at.desc()).limit(limit).offset(offset)
            rows = [self._row_to_dict(r) for r in conn.execute(stmt).all()]

            count_stmt = select(func.count()).select_from(EventRow).where(
                EventRow.type.like(f"{type_prefix}%")
            )
            if task_id:
                count_stmt = count_stmt.where(EventRow.task_id == task_id)
            if user_id is not None:
                count_stmt = count_stmt.where(EventRow.user_id == user_id)
            total = int(conn.execute(count_stmt).scalar() or 0)
            return rows, total

    def list_events_by_request(
        self,
        request_id: str,
        limit: int = 1000,
        offset: int = 0,
        user_id: str | None = None,
    ) -> tuple[list[dict], int]:
        """按 request_id 检索同链路所有事件日志

        全链路追踪核心查询：通过单个流水号检索本次请求触发的所有关联事件，
        按时间正序返回，便于展示调用链路顺序。
        """
        if not request_id:
            return [], 0
        with self.engine.connect() as conn:
            base_where = [EventRow.request_id == request_id]
            if user_id is not None:
                base_where.append(EventRow.user_id == user_id)
            stmt = (
                select(EventRow)
                .where(*base_where)
                # 正序返回：链路展示按时间顺序，最早的先出
                .order_by(EventRow.created_at.asc())
                .limit(limit)
                .offset(offset)
            )
            rows = [self._row_to_dict(r) for r in conn.execute(stmt).all()]
            total = int(
                conn.execute(
                    select(func.count()).select_from(EventRow).where(*base_where)
                ).scalar() or 0
            )
            return rows, total

    def get_event(self, event_id: int, user_id: str | None = None) -> dict | None:
        """获取单条事件

        user_id 不为 None 时附加 WHERE 过滤（T02684 深度防御）：
        跨用户查别人的行一律当作「不存在」，与 update_event_payload 的隔离语义一致，
        避免 /api/logs/tag 用别人的 event_id 直接改到对方 payload。
        """
        with self.engine.connect() as conn:
            stmt = select(EventRow).where(EventRow.id == event_id)
            if user_id is not None:
                stmt = stmt.where(EventRow.user_id == user_id)
            row = conn.execute(stmt).first()
            return self._row_to_dict(row) if row else None

    def get_eval_payload_by_item(self, item_id: str, user_id: str | None = None) -> dict | None:
        """按 item_id 查询最新评估事件的 payload

        seller_trend_for_item 在 items 表无记录时，从评估事件 payload 回退提取 seller_id。
        之前路由层直接访问 engine 查询 EventRow，这里提供正式方法。

        返回的 payload dict 中会注入 task_id 字段（若事件表有值），
        供 AI 评估回退场景查询同类物品价格区间使用。
        """
        if not item_id:
            return None
        with self.engine.connect() as conn:
            stmt = (
                select(EventRow.payload, EventRow.task_id)
                .where(EventRow.item_id == item_id)
                .where(EventRow.type.like("eval.%"))
                .order_by(EventRow.created_at.desc())
                .limit(1)
            )
            if user_id is not None:
                stmt = stmt.where(EventRow.user_id == user_id)
            row = conn.execute(stmt).first()
            if not row or not row.payload:
                return None
            try:
                payload = json.loads(row.payload) if isinstance(row.payload, str) else row.payload
            except (json.JSONDecodeError, TypeError):
                return None
            # 注入 task_id 到 payload，供 items 表无记录时的回退场景使用
            if isinstance(payload, dict) and row.task_id:
                payload.setdefault("task_id", row.task_id)
            return payload

    def update_event_payload(
        self, event_id: int, payload: str, user_id: str | None = None
    ) -> None:
        """更新事件的 payload JSON

        user_id 不为 None 时附加 WHERE 过滤，防止跨用户更新（深度防御）。
        """
        with self.engine.begin() as conn:
            stmt = (
                EventRow.__table__.update()
                .where(EventRow.id == event_id)
                .values(payload=payload)
            )
            if user_id is not None:
                stmt = stmt.where(EventRow.user_id == user_id)
            conn.execute(stmt)

    def update_eval_payload_by_keys(
        self, task_id: str, item_id: str, event_type: str, payload_updates: dict,
        user_id: str | None = None,
    ) -> bool:
        """按 (task_id, item_id, type) 查找评估事件并合并更新 payload

        payload_updates 中的键值对会合并到现有 payload 中（不覆盖整个 payload）。
        返回是否成功更新（未找到记录时返回 False）。

        user_id 不为 None 时附加 WHERE 过滤，防止跨用户更新（深度防御）。
        """
        with self.engine.begin() as conn:
            sel_stmt = (
                select(EventRow.id, EventRow.payload)
                .where(
                    EventRow.task_id == task_id,
                    EventRow.item_id == item_id,
                    EventRow.type == event_type,
                )
                .order_by(EventRow.created_at.desc())
                .limit(1)
            )
            if user_id is not None:
                sel_stmt = sel_stmt.where(EventRow.user_id == user_id)
            row = conn.execute(sel_stmt).first()
            if not row:
                return False
            try:
                payload = json.loads(row.payload) if isinstance(row.payload, str) else (row.payload or {})
            except (json.JSONDecodeError, TypeError):
                payload = {}
            payload.update(payload_updates)
            update_stmt = (
                EventRow.__table__.update()
                .where(EventRow.id == row.id)
                .values(payload=json.dumps(payload, ensure_ascii=False, default=str))
            )
            if user_id is not None:
                update_stmt = update_stmt.where(EventRow.user_id == user_id)
            conn.execute(update_stmt)
            return True

    def max_event_id(self, user_id: str | None = None) -> int:
        """获取当前 events 表最大 id（不存在时返回 0）

        user_id 不为 None 时仅统计该用户的事件 id（SSE 按用户回放场景）。
        """
        with self.engine.connect() as conn:
            stmt = select(func.max(EventRow.id))
            if user_id is not None:
                stmt = stmt.where(EventRow.user_id == user_id)
            return int(conn.execute(stmt).scalar() or 0)

    def delete_events_by_task(self, task_id: str, user_id: str | None = None) -> int:
        """按任务删除所有关联事件

        user_id 不为 None 时附加 WHERE 过滤，防止跨用户删除（深度防御）。
        """
        with self.engine.begin() as conn:
            stmt = EventRow.__table__.delete().where(EventRow.task_id == task_id)
            if user_id is not None:
                stmt = stmt.where(EventRow.user_id == user_id)
            result = conn.execute(stmt)
            return result.rowcount or 0

    def delete_eval_events_by_task_item(
        self, task_id: str, item_id: str, user_id: str | None = None
    ) -> int:
        """删除指定任务+商品的评估事件（联动清理垃圾数据）

        使用场景：删除 task_links 中 item 类型关联时，联动删除 events 表中
        对应的 eval.* 事件，避免评估明细残留垃圾数据。
        为什么按 task_id + item_id 双键：同一商品可能被多个任务关联，
        只按 item_id 删除会误清其他任务的评估记录。

        user_id 不为 None 时附加 WHERE 过滤，防止跨用户删除（深度防御）。
        """
        if not task_id or not item_id:
            return 0
        with self.engine.begin() as conn:
            stmt = EventRow.__table__.delete().where(
                EventRow.task_id == task_id,
                EventRow.item_id == item_id,
                EventRow.type.like("eval.%"),
            )
            if user_id is not None:
                stmt = stmt.where(EventRow.user_id == user_id)
            result = conn.execute(stmt)
            return result.rowcount or 0

    # ============== F-09 任务运行历史（按时间窗聚合 events） ==============
    def get_task_runs(
        self,
        task_id: str,
        range_hours: int = 24,
        window_minutes: int = 5,
        idle_gap_minutes: int = 30,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """按时间窗聚合 events 表中该 task_id 的运行记录

        user_id 不为 None 时附加 WHERE 过滤，防止跨用户读取（深度防御）。
        """
        now = _utcnow()
        start_time = now - timedelta(hours=range_hours)

        with self.engine.connect() as conn:
            stmt = (
                select(EventRow)
                .where(EventRow.task_id == task_id)
                .where(EventRow.created_at >= start_time)
                .where(EventRow.created_at <= now)
                .order_by(EventRow.created_at.asc())
            )
            if user_id is not None:
                stmt = stmt.where(EventRow.user_id == user_id)
            rows = conn.execute(stmt).all()

        if not rows:
            return {
                "task_id": task_id,
                "runs": [], "idle_gaps": [],
                "total_runs": 0, "total_events": 0, "total_hits": 0,
            }

        # 先批量转换 Row 为 dict，让后续聚合逻辑变为纯函数处理
        events = [self._row_to_dict(row) for row in rows]
        buckets = _aggregate_events_into_buckets(events, window_minutes, self._aggregate_bucket)
        idle_gaps = _compute_idle_gaps(buckets, idle_gap_minutes)

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
        hit_count, err_count, warn_count = _count_event_levels(events)
        first_event_stage = events[0].get("stage", "")  # API 字段名 first_event_type 实际取 stage 值

        first_time = _parse_event_time(events[0].get("created_at"))
        last_time = _parse_event_time(events[-1].get("created_at"))
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
            "first_event_type": first_event_stage,
        }
