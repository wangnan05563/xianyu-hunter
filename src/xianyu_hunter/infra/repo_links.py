"""Task Links 领域数据访问 - 任务关联 CRUD

提供：
- upsert_task_link / list_task_links / count_task_links / delete_task_link
- lookup_task_links / search_task_links / auto_migrate_task_links
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, func, cast, Float
# 别名与其他 repo_*.py 统一为 sqlite_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from xianyu_hunter.domain.urls import build_item_url
from xianyu_hunter.infra.db_models import ItemRow, TaskLinkRow, TaskRow
from xianyu_hunter.infra.repository_base import RepositoryBase, _escape_like


_WORD_RE = re.compile(r"[0-9a-zA-Z]+|[\u4e00-\u9fff]+")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def _normalize_for_match(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _keyword_parts(keyword: str) -> list[str]:
    return [part for part in re.split(r"[\s,，/、|]+", keyword) if part]


def _cjk_chars(value: str) -> list[str]:
    return _CJK_RE.findall(value)


def _token_matches_title(token: str, title: str) -> bool:
    if not token:
        return True
    if token in title:
        return True
    words = _WORD_RE.findall(token)
    if len(words) > 1:
        return all(word in title for word in words if word)
    cjk_chars = _cjk_chars(token)
    if len(cjk_chars) >= 4:
        return all(ch in title for ch in cjk_chars)
    return False


def task_keyword_matches_title(keyword: str | None, title: str | None) -> bool:
    """Return True when an auto-linked item title still matches the task keyword."""
    keyword = _normalize_for_match(keyword)
    if not keyword:
        return True
    title = _normalize_for_match(title)
    if not title:
        return False
    if keyword in title:
        return True

    tokens = _keyword_parts(keyword)
    if not tokens:
        return True
    matches = sum(1 for token in tokens if _token_matches_title(token, title))
    if len(tokens) <= 2:
        return matches == len(tokens)
    return matches >= len(tokens) - 1


def xianyu_item_url(item_id: str) -> str:
    # 委托给 domain.urls 统一入口，保持本函数签名以兼容现有调用
    return build_item_url(item_id)


class TaskLinksMixin:
    """Task Links 领域的 Repository 方法"""

    def _task_link_matches_task(self, row: dict, task: dict | None) -> bool:
        # 按关键词过滤：只展示标题匹配关键词的关联数据，
        # 避免因闲鱼反爬返回的不相关商品污染关联面板
        if not task:
            return True
        keyword = task.get("keyword")
        if not keyword:
            return True
        display = row.get("display")
        if isinstance(display, str):
            try:
                display = json.loads(display)
            except (json.JSONDecodeError, TypeError):
                display = {}
        # seller 行的 title 是"卖家 xxx"，不匹配关键词；
        # 但 item_title 字段保存了原商品标题，应该也参与匹配
        title = (display or {}).get("title") or ""
        item_title = (display or {}).get("item_title") or ""
        return (task_keyword_matches_title(keyword, title)
                or task_keyword_matches_title(keyword, item_title))

    def _build_item_link_rows(
        self,
        task_id: str,
        item_id: str,
        title: str | None,
        price: float | None = None,
        thumb_url: str | None = None,
        seller_id: str | None = None,
        region: str | None = None,
        publish_time: datetime | None = None,
        want_cnt: int | None = None,
        view_cnt: int | None = None,
        is_sold: bool | None = None,
        seller_nick: str | None = None,
        brand: str | None = None,
    ) -> list[tuple[str, str, dict]]:
        item_url = xianyu_item_url(item_id)
        rows: list[tuple[str, str, dict]] = [
            (
                "item",
                item_id,
                {
                    "title": title,
                    "brand": brand or "",
                    "price": price,
                    "thumb_url": thumb_url,
                    "seller_id": seller_id,
                    "seller_nick": seller_nick or "",
                    "url": item_url,
                    "region": region or "",
                    # publish_time 可能是 datetime 对象（upsert_item_task_links 调用方）
                    # 或 ISO 字符串（live_search 结果经 display 字典传入），
                    # 统一转为 ISO 字符串存储
                    "publish_time": (
                        publish_time.isoformat() if isinstance(publish_time, datetime)
                        else (str(publish_time) if publish_time else None)
                    ),
                    "want_cnt": want_cnt,
                    "view_cnt": view_cnt,
                    "is_sold": bool(is_sold) if is_sold is not None else False,
                },
            ),
        ]
        if seller_id:
            rows.append(
                (
                    "seller",
                    seller_id,
                    {
                        "title": seller_nick or f"卖家 {seller_id}",
                        "nick": seller_nick or seller_id,
                        "seller_nick": seller_nick or "",
                        "item_title": title,
                        "item_id": item_id,
                        "brand": brand or "",
                        "region": region or "",
                    },
                )
            )
        return rows

    def upsert_item_task_links(
        self,
        task_id: str,
        item_id: str,
        title: str | None,
        price: float | None = None,
        thumb_url: str | None = None,
        seller_id: str | None = None,
        source: str = "auto",
        region: str | None = None,
        publish_time: datetime | None = None,
        want_cnt: int | None = None,
        view_cnt: int | None = None,
        is_sold: bool | None = None,
        seller_nick: str | None = None,
        brand: str | None = None,
    ) -> int:
        written = 0
        for link_type, link_key, display in self._build_item_link_rows(
            task_id=task_id,
            item_id=item_id,
            title=title,
            price=price,
            thumb_url=thumb_url,
            seller_id=seller_id,
            region=region,
            publish_time=publish_time,
            want_cnt=want_cnt,
            view_cnt=view_cnt,
            is_sold=is_sold,
            seller_nick=seller_nick,
            brand=brand,
        ):
            self.upsert_task_link(
                task_id=task_id,
                link_type=link_type,
                link_key=link_key,
                display=display,
                source=source,
            )
            written += 1
        return written

    def upsert_task_link(
        self,
        task_id: str,
        link_type: str,
        link_key: str,
        display: dict | None = None,
        source: str = "auto",
        note: str | None = None,
    ) -> int | None:
        """插入或忽略重复，返回行 id。已存在则仅更新 display / note。"""
        with self.engine.begin() as conn:
            stmt = sqlite_insert(TaskLinkRow).values(
                task_id=task_id,
                link_type=link_type,
                link_key=link_key,
                display=json.dumps(display, ensure_ascii=False) if display else None,
                source=source,
                note=note,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["task_id", "link_type", "link_key"],
                # 修复：之前不更新 source，导致 live 搜索命中的商品若已存在 auto 来源，
                # source 仍为 "auto"，后续 refresh_links 删除 auto 时会误删 live 数据。
                set_={
                    "display": stmt.excluded["display"],
                    "note": stmt.excluded["note"],
                    "source": stmt.excluded["source"],
                },
            )
            result = conn.execute(stmt)
            row = conn.execute(
                select(TaskLinkRow.id)
                .where(TaskLinkRow.task_id == task_id)
                .where(TaskLinkRow.link_type == link_type)
                .where(TaskLinkRow.link_key == link_key)
            ).first()
            return int(row[0]) if row else None

    def batch_upsert_task_links(self, batch: list[dict]) -> int:
        """批量 upsert task_links，单事务提交

        替代逐条 upsert_task_link 调用，将 N 次独立事务合并为 1 次，
        减少 SQLite fsync 开销（50 条商品从 ~100 次事务降至 1 次）。
        """
        if not batch:
            return 0
        written = 0
        with self.engine.begin() as conn:
            for row in batch:
                display = row.get("display")
                if isinstance(display, dict):
                    display = json.dumps(display, ensure_ascii=False)
                stmt = sqlite_insert(TaskLinkRow).values(
                    task_id=row["task_id"],
                    link_type=row["link_type"],
                    link_key=row["link_key"],
                    display=display,
                    source=row.get("source", "auto"),
                    note=row.get("note"),
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["task_id", "link_type", "link_key"],
                    set_={
                        "display": stmt.excluded["display"],
                        "note": stmt.excluded["note"],
                        "source": stmt.excluded["source"],
                    },
                )
                result = conn.execute(stmt)
                written += result.rowcount or 0
        return written

    def batch_upsert_item_task_links(
        self,
        task_id: str,
        items_data: list[dict],
        source: str = "auto",
    ) -> int:
        """批量写入 item + seller 关联，单事务提交

        替代逐条 upsert_item_task_links 调用。
        items_data 格式：[{item_id, title, price, thumb_url, seller_id, region, ...}, ...]
        """
        if not items_data:
            return 0
        batch: list[dict] = []
        for data in items_data:
            for link_type, link_key, display in self._build_item_link_rows(
                task_id=task_id,
                item_id=data["item_id"],
                title=data.get("title"),
                price=data.get("price"),
                thumb_url=data.get("thumb_url"),
                seller_id=data.get("seller_id"),
                region=data.get("region"),
                publish_time=data.get("publish_time"),
                want_cnt=data.get("want_cnt"),
                view_cnt=data.get("view_cnt"),
                is_sold=data.get("is_sold"),
                seller_nick=data.get("seller_nick"),
                brand=data.get("brand"),
            ):
                batch.append({
                    "task_id": task_id,
                    "link_type": link_type,
                    "link_key": link_key,
                    "display": display,
                    "source": source,
                })
        return self.batch_upsert_task_links(batch)

    def _filter_task_links(self, rows: list[dict], task: dict | None) -> list[dict]:
        """统一过滤逻辑：关键词 + 价格 + 发布天数

        list_task_links 和 count_task_links 共用此方法，确保两者结果一致。
        """
        # 关键词过滤
        rows = [r for r in rows if self._task_link_matches_task(r, task)]
        # 价格过滤
        min_price = (task or {}).get("min_price")
        max_price = (task or {}).get("max_price")
        max_publish_days = (task or {}).get("max_publish_days")
        if min_price is not None or max_price is not None or max_publish_days is not None:
            filtered = []
            # 与 db_models._utcnow 保持一致：publish_time 存储为 UTC，比较时也用 UTC
            now = datetime.now(timezone.utc)
            for r in rows:
                display = r.get("display")
                if isinstance(display, str):
                    try:
                        display = json.loads(display)
                    except (json.JSONDecodeError, TypeError):
                        display = {}
                # 价格过滤（price 为空时保留，兼容 url/seller 类型）
                if min_price is not None or max_price is not None:
                    price_val = (display or {}).get("price") if isinstance(display, dict) else None
                    if price_val is not None:
                        try:
                            p = float(price_val)
                            if min_price is not None and p < min_price:
                                continue
                            if max_price is not None and p > max_price:
                                continue
                        except (ValueError, TypeError):
                            pass
                # 发布天数过滤（publish_time 为空时保留，兼容旧数据）
                if max_publish_days is not None and isinstance(display, dict):
                    pub = display.get("publish_time")
                    if pub:
                        try:
                            pub_dt = datetime.fromisoformat(str(pub).replace("Z", "+00:00"))
                            if (now - pub_dt).days > max_publish_days:
                                continue
                        except (ValueError, TypeError):
                            pass
                filtered.append(r)
            rows = filtered
        return rows

    def list_task_links(
        self,
        task_id: str,
        link_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        with self.engine.connect() as conn:
            task_row = conn.execute(select(TaskRow).where(TaskRow.id == task_id)).first()
            task = self._row_to_dict(task_row) if task_row else None
            stmt = select(TaskLinkRow).where(TaskLinkRow.task_id == task_id)
            if link_type:
                stmt = stmt.where(TaskLinkRow.link_type == link_type)

            # 价格过滤下推 SQL：减少全量加载的行数
            # 关键词/发布天数过滤保留 Python 层（中文分词 + 时间计算兼容性）
            min_price = (task or {}).get("min_price")
            max_price = (task or {}).get("max_price")
            if min_price is not None or max_price is not None:
                price_expr = func.json_extract(TaskLinkRow.display, '$.price')
                if min_price is not None:
                    stmt = stmt.where(
                        (price_expr.is_(None)) | (cast(price_expr, Float) >= min_price)
                    )
                if max_price is not None:
                    stmt = stmt.where(
                        (price_expr.is_(None)) | (cast(price_expr, Float) <= max_price)
                    )

            stmt = stmt.order_by(TaskLinkRow.created_at.desc())
            rows = [self._row_to_dict(r) for r in conn.execute(stmt).all()]
            rows = self._filter_task_links(rows, task)
            return rows[offset:offset + limit]

    def list_and_count_task_links(
        self,
        task_id: str,
        link_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
        search_keyword: str | None = None,
        search_region: str | None = None,
        search_brand: str | None = None,
    ) -> tuple[list[dict], dict[str, int]]:
        """单次查询同时返回列表和计数，避免 list + count 两次全量加载

        替代分别调用 list_task_links + count_task_links，
        将两次全量加载合并为一次，DB 查询耗时减半。

        search_keyword/search_region/search_brand：将关键词/地区/品牌过滤下推 SQL 层，
        避免 has_search 时全量加载到内存再 Python 过滤。
        """
        # 性能埋点：记录查询耗时，用于长期监控商品列表查询性能
        import time as _time
        from xianyu_hunter.infra.logger import get_logger as _get_logger
        _perf_logger = _get_logger()
        _perf_start = _time.monotonic()

        with self.engine.connect() as conn:
            task_row = conn.execute(select(TaskRow).where(TaskRow.id == task_id)).first()
            task = self._row_to_dict(task_row) if task_row else None
            stmt = select(TaskLinkRow).where(TaskLinkRow.task_id == task_id)
            if link_type:
                stmt = stmt.where(TaskLinkRow.link_type == link_type)

            # 价格过滤下推 SQL（与 list_task_links 保持一致）
            min_price = (task or {}).get("min_price")
            max_price = (task or {}).get("max_price")
            if min_price is not None or max_price is not None:
                price_expr = func.json_extract(TaskLinkRow.display, '$.price')
                if min_price is not None:
                    stmt = stmt.where(
                        (price_expr.is_(None)) | (cast(price_expr, Float) >= min_price)
                    )
                if max_price is not None:
                    stmt = stmt.where(
                        (price_expr.is_(None)) | (cast(price_expr, Float) <= max_price)
                    )

            # 关键词/地区过滤下推 SQL：避免 has_search 时全量加载到内存再 Python 过滤
            # json_extract 对 NULL display 返回 NULL，NULL LIKE '%kw%' 为 NULL（非 true），
            # 行被自动排除，与原 Python 逻辑（空 title 不匹配）一致
            if search_keyword:
                kw_pattern = f'%{search_keyword.lower()}%'
                title_expr = func.lower(func.json_extract(TaskLinkRow.display, '$.title'))
                stmt = stmt.where(title_expr.like(kw_pattern))
            if search_region:
                region_expr = func.json_extract(TaskLinkRow.display, '$.region')
                stmt = stmt.where(region_expr == search_region)
            if search_brand:
                # 品牌精确匹配（与地区过滤一致），空品牌自动排除
                brand_expr = func.json_extract(TaskLinkRow.display, '$.brand')
                stmt = stmt.where(brand_expr == search_brand)

            # 发布天数过滤下推 SQL：减少 Python 层处理的数据行数
            # publish_time 存储为 ISO 字符串（UTC），substr 截取前 19 字符去掉时区后缀，
            # datetime() 将字符串转为可比较的时间值
            # 为什么下推：原 Python 层过滤需全量加载到内存再逐行解析，SQL 层过滤直接减少返回行数
            max_publish_days = (task or {}).get("max_publish_days")
            if max_publish_days is not None:
                pub_expr = func.json_extract(TaskLinkRow.display, '$.publish_time')
                # substr(..., 1, 19) 截取 "YYYY-MM-DDTHH:MM:SS"，datetime() 解析为时间值
                pub_dt_expr = func.datetime(func.substr(pub_expr, 1, 19))
                cutoff_dt = datetime.now(timezone.utc) - timedelta(days=max_publish_days)
                cutoff_str = cutoff_dt.strftime('%Y-%m-%d %H:%M:%S')
                # publish_time 为 NULL 或解析失败时保留行（兼容旧数据，与 Python 逻辑一致）
                stmt = stmt.where(
                    (pub_expr.is_(None)) | (pub_dt_expr.is_(None)) | (pub_dt_expr >= cutoff_str)
                )

            stmt = stmt.order_by(TaskLinkRow.created_at.desc())
            all_rows = [self._row_to_dict(r) for r in conn.execute(stmt).all()]
            filtered = self._filter_task_links(all_rows, task)

            # 一次遍历同时产出分页列表和各类型计数
            counts: dict[str, int] = {"item": 0, "seller": 0, "url": 0, "total": 0}
            for row in filtered:
                lt = row.get("link_type")
                if lt in counts:
                    counts[lt] += 1
                    counts["total"] += 1

            page_rows = filtered[offset:offset + limit]

            # 性能埋点：慢查询告警（>100ms 记录 warning，便于持续监控）
            _elapsed_ms = (_time.monotonic() - _perf_start) * 1000
            if _elapsed_ms > 100:
                _perf_logger.warning(
                    "list_and_count_task_links 慢查询: task={}, type={}, rows={}, filtered={}, elapsed={:.1f}ms",
                    task_id, link_type, len(all_rows), len(filtered), _elapsed_ms,
                )
            else:
                _perf_logger.debug(
                    "list_and_count_task_links: task={}, type={}, rows={}, elapsed={:.1f}ms",
                    task_id, link_type, len(all_rows), _elapsed_ms,
                )

            return page_rows, counts

    def count_task_links(
        self,
        task_id: str,
        link_type: str | None = None,
    ) -> dict[str, int]:
        """按类型返回关联计数（与 list_task_links 的过滤逻辑保持一致）"""
        with self.engine.connect() as conn:
            task_row = conn.execute(select(TaskRow).where(TaskRow.id == task_id)).first()
            task = self._row_to_dict(task_row) if task_row else None
            stmt = select(TaskLinkRow).where(TaskLinkRow.task_id == task_id)
            if link_type:
                stmt = stmt.where(TaskLinkRow.link_type == link_type)
            rows = [self._row_to_dict(r) for r in conn.execute(stmt).all()]
            rows = self._filter_task_links(rows, task)
            result = {"item": 0, "seller": 0, "url": 0, "total": 0}
            for row in rows:
                lt = row.get("link_type")
                if lt in result:
                    result[lt] += 1
                    result["total"] += 1
            return result

    def delete_task_link(self, link_id: int) -> bool:
        with self.engine.begin() as conn:
            result = conn.execute(
                TaskLinkRow.__table__.delete().where(TaskLinkRow.id == link_id)
            )
            return (result.rowcount or 0) > 0

    def delete_task_links_by_task(self, task_id: str, source: str | None = None) -> int:
        """按任务删除关联数据；source 可选过滤（'auto' 只删自动采集的）"""
        with self.engine.begin() as conn:
            stmt = TaskLinkRow.__table__.delete().where(TaskLinkRow.task_id == task_id)
            if source:
                stmt = stmt.where(TaskLinkRow.source == source)
            result = conn.execute(stmt)
            return result.rowcount or 0

    def lookup_task_links(
        self,
        link_type: str,
        link_key: str,
    ) -> list[dict]:
        """反查：给定 (type, key)，返回所有关联该 key 的任务链接行"""
        with self.engine.connect() as conn:
            stmt = (
                select(TaskLinkRow)
                .where(TaskLinkRow.link_type == link_type)
                .where(TaskLinkRow.link_key == link_key)
            )
            return [self._row_to_dict(r) for r in conn.execute(stmt).all()]

    def list_link_displays_by_keys(
        self,
        link_keys: list[str],
        link_type: str = "item",
    ) -> dict[str, dict]:
        """按 link_key 批量查询 display，返回 {link_key: display_dict}

        评估明细接口需要按评估事件涉及的 item_id 批量查询 task_links.display，
        之前路由层直接访问 engine 绕过 Repository，这里提供正式方法。
        同一 item_id 可能关联到多个任务，选择字段最完整的 display
        （老任务可能字段缺失，新任务字段更完整）。
        """
        if not link_keys:
            return {}
        # 先收集每个 key 的所有 display 候选
        candidates: dict[str, list[dict]] = {}
        batch_size = 500
        with self.engine.connect() as conn:
            for i in range(0, len(link_keys), batch_size):
                batch = link_keys[i:i + batch_size]
                rows = conn.execute(
                    select(TaskLinkRow.link_key, TaskLinkRow.display)
                    .where(TaskLinkRow.link_type == link_type)
                    .where(TaskLinkRow.link_key.in_(batch))
                ).fetchall()
                for lk, display_json in rows:
                    if not lk:
                        continue
                    key = str(lk)
                    try:
                        d = json.loads(display_json) if isinstance(display_json, str) else (display_json or {})
                    except (json.JSONDecodeError, TypeError):
                        d = {}
                    if d:
                        candidates.setdefault(key, []).append(d)
        # 每个 key 选择非空字段最多的 display
        result: dict[str, dict] = {}
        for key, display_list in candidates.items():
            result[key] = max(display_list, key=lambda d: sum(1 for v in d.values() if v not in (None, "", False, 0)))
        return result

    def search_task_links(
        self,
        q: str,
        link_type: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """跨任务模糊搜索 link_key / display"""
        like = f"%{_escape_like(q)}%"
        with self.engine.connect() as conn:
            stmt = select(TaskLinkRow)
            if link_type:
                stmt = stmt.where(TaskLinkRow.link_type == link_type)
            stmt = stmt.where(
                (TaskLinkRow.link_key.like(like, escape="/")) | (TaskLinkRow.display.like(like, escape="/"))
            )
            stmt = stmt.order_by(TaskLinkRow.created_at.desc()).limit(limit)
            return [self._row_to_dict(r) for r in conn.execute(stmt).all()]

    def auto_migrate_task_links(self) -> int:
        """一次性把 items 表里已有的隐式关联搬到 task_links"""
        inserted = 0
        with self.engine.begin() as conn:
            def insert_link(task_id: str, link_type: str, link_key: str, display: dict) -> None:
                nonlocal inserted
                stmt = sqlite_insert(TaskLinkRow).values(
                    task_id=task_id,
                    link_type=link_type,
                    link_key=link_key,
                    display=json.dumps(display, ensure_ascii=False),
                    source="auto",
                )
                stmt = stmt.on_conflict_do_nothing(
                    index_elements=["task_id", "link_type", "link_key"]
                )
                result = conn.execute(stmt)
                inserted += result.rowcount or 0

            rows = conn.execute(
                select(
                    ItemRow.id,
                    ItemRow.task_id,
                    ItemRow.title,
                    ItemRow.price,
                    ItemRow.thumb_url,
                    ItemRow.seller_id,
                    TaskRow.keyword,
                )
                .join(TaskRow, TaskRow.id == ItemRow.task_id)
                .where(ItemRow.task_id.is_not(None))
            ).all()
            for item_id, tid, title, price, thumb, seller_id, keyword in rows:
                # 不按关键词过滤：搜索结果可能因反爬返回不相关商品，
                # 但前端需要展示所有采集到的数据
                for link_type, link_key, display in self._build_item_link_rows(
                    task_id=tid,
                    item_id=item_id,
                    title=title,
                    price=price,
                    thumb_url=thumb,
                    seller_id=seller_id,
                ):
                    insert_link(tid, link_type, link_key, display)

            legacy_rows = conn.execute(
                select(TaskLinkRow.task_id, TaskLinkRow.link_key, TaskLinkRow.display, TaskRow.keyword)
                .join(TaskRow, TaskRow.id == TaskLinkRow.task_id)
                .where(TaskLinkRow.link_type == "item")
                .where(TaskLinkRow.source == "auto")
            ).all()
            for tid, item_id, raw_display, keyword in legacy_rows:
                try:
                    display = json.loads(raw_display) if isinstance(raw_display, str) and raw_display else {}
                except json.JSONDecodeError:
                    display = {}
                title = display.get("title") or display.get("item_title")
                if not task_keyword_matches_title(keyword, title):
                    continue
                for link_type, link_key, derived_display in self._build_item_link_rows(
                    task_id=tid,
                    item_id=item_id,
                    title=title,
                    price=display.get("price"),
                    thumb_url=display.get("thumb_url"),
                    seller_id=display.get("seller_id"),
                ):
                    if link_type == "item":
                        continue
                    insert_link(tid, link_type, link_key, derived_display)
        return inserted
