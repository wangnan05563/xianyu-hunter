"""降价检测与即时提醒（PRD FR-F1-3 / FR-F1-4，REQ-008/009）

检测规则（FR-F1-3）：新快照价 < 该商品此前最低价 × (1 - 阈值)（任务级可配，
price_config.price_drop_threshold，默认 0%）即触发降价事件。

通知三路（FR-F1-4）：
1. 事件时间线：repo.save_event（stage=price_drop）
2. 站内通知：repo.add_notification（category=price，dedup 防同价重复刷屏）
3. 8 渠道推送：EventBus 发布 PRICE_DROPPED → NotifierHub fan-out（免打扰降级由 hub 处理）

检测时序关键点：必须在写入新快照【之前】取旧最低价，
否则新价入表后 min_price 已被更新，永远检测不到降价。
"""
from __future__ import annotations

from typing import Any

from xianyu_hunter.domain.events import Event, EventType
from xianyu_hunter.infra.logger import get_logger
from xianyu_hunter.infra.repository import Repository

logger = get_logger()

# 默认降价阈值：任何跌破历史最低的新价都触发（PRD 默认 0%）
DEFAULT_DROP_THRESHOLD = 0.0


def get_drop_threshold(repo: Repository, task_id: str | None) -> float:
    """读取任务级降价阈值（price_config.price_drop_threshold，0~1 小数）

    任务未配置或配置非法时回退默认 0%。
    """
    if not task_id:
        return DEFAULT_DROP_THRESHOLD
    try:
        task = repo.get_task(task_id)
        if not task:
            return DEFAULT_DROP_THRESHOLD
        import json as _json

        raw = task.get("price_config")
        cfg = _json.loads(raw) if isinstance(raw, str) and raw.strip() else (raw or {})
        val = cfg.get("price_drop_threshold") if isinstance(cfg, dict) else None
        if isinstance(val, (int, float)) and 0 <= val < 1:
            return float(val)
    except Exception as e:  # noqa: BLE001
        logger.debug(f"[price-watch] 读取任务 {task_id} 降价阈值失败，用默认: {e}")
    return DEFAULT_DROP_THRESHOLD


def observe_price(
    repo: Repository,
    bus,
    item_id: str,
    price: float,
    source: str,
    *,
    task_id: str | None = None,
    user_id: str | None = None,
) -> dict | None:
    """写价格快照并检测降价，触发时发出三路通知

    时序：先取旧最低价（写入前）→ 写快照（同值去重）→ 比较检测。

    Returns:
        降价信息 dict（含 prev_min/new_price/drop_pct），未触发或被去重返回 None
    """
    if not isinstance(price, (int, float)) or price <= 0:
        return None
    # FR-F1-3 检测基线：该商品此前最低价（写入前取，避免新价污染基线）
    prev_min = repo.get_min_price(item_id, user_id=user_id)
    written = repo.record_price_snapshot(item_id, float(price), source, user_id=user_id)
    if not written or prev_min is None:
        return None

    threshold = get_drop_threshold(repo, task_id)
    # 严格小于阈值线才触发：同价（写快照时已去重）与微涨都不算降价，
    # 容差 1e-9 抵御浮点误差
    if not (float(price) < prev_min * (1 - threshold) - 1e-9):
        return None

    drop_pct = (prev_min - float(price)) / prev_min if prev_min > 0 else 0.0
    item = repo.get_item(item_id, user_id=user_id) or {}
    item_title = item.get("title") or ""

    info = {
        "item_id": item_id,
        "item_title": item_title,
        "new_price": float(price),
        "prev_min_price": float(prev_min),
        "drop_pct": round(drop_pct, 4),
        "source": source,
        "task_id": task_id or "",
    }
    _emit_drop_notifications(repo, bus, info, user_id=user_id)
    return info


def observe_prices(
    repo: Repository,
    bus,
    items: list[dict],
    source: str,
    *,
    task_id: str | None = None,
    user_id: str | None = None,
) -> list[dict]:
    """批量观察（采集链路）：先整批取旧最低价 → 批量写快照 → 逐个检测降价

    Returns:
        触发降价的商品信息列表
    """
    candidates = [
        (it["id"], float(it["price"]))
        for it in items
        if it.get("id") and isinstance(it.get("price"), (int, float)) and it["price"] > 0
    ]
    if not candidates:
        return []
    threshold = get_drop_threshold(repo, task_id)
    # 旧最低价 map（写入前取，保持检测基线不被本批污染）
    prev_mins = {cid: repo.get_min_price(cid, user_id=user_id) for cid, _ in candidates}
    repo.record_price_snapshots(
        [{"id": cid, "price": price} for cid, price in candidates], source, user_id=user_id,
    )

    drops: list[dict] = []
    for cid, price in candidates:
        prev_min = prev_mins.get(cid)
        # 与单条路径同口径：严格跌破阈值线才触发（同价已被快照去重）
        if prev_min is None or not (price < prev_min * (1 - threshold) - 1e-9):
            continue
        drop_pct = (prev_min - price) / prev_min if prev_min > 0 else 0.0
        item = repo.get_item(cid, user_id=user_id) or {}
        info = {
            "item_id": cid,
            "item_title": item.get("title") or "",
            "new_price": price,
            "prev_min_price": float(prev_min),
            "drop_pct": round(drop_pct, 4),
            "source": source,
            "task_id": task_id or "",
        }
        drops.append(info)
        _emit_drop_notifications(repo, bus, info, user_id=user_id)
    return drops


def _emit_drop_notifications(
    repo: Repository, bus, info: dict, user_id: str | None = None
) -> None:
    """降价三路通知（每路独立容错，任何一路失败不影响其他路）"""
    item_id = info["item_id"]
    # 1. 事件时间线
    try:
        import json as _json

        event_row = {
            "type": EventType.PRICE_DROPPED.value,
            "task_id": info.get("task_id") or None,
            "item_id": item_id,
            "stage": "price_drop",
            "level": "info",
            "message": f"降价提醒：{info['item_title'] or item_id} "
                       f"{info['prev_min_price']:.2f} → {info['new_price']:.2f}"
                       f"（-{info['drop_pct'] * 100:.1f}%）",
            "payload": _json.dumps(info, ensure_ascii=False),
        }
        if user_id:
            # EventRow.user_id NOT NULL：仅在调用方明确归属时注入，
            # None 会让 NOT NULL 约束失败（column default 不会兜底显式 None）
            event_row["user_id"] = user_id
        repo.save_event(event_row)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[price-watch] 事件时间线写入失败: {e}")

    # 2. 站内通知（dedup 按商品+新价：同一价格只提醒一次，避免反复刷屏）
    try:
        repo.add_notification(
            level="warn",
            category="price",
            title=f"降价提醒：{info['item_title'] or item_id}",
            message=f"现价 ¥{info['new_price']:.2f}（历史最低 ¥{info['prev_min_price']:.2f}，"
                    f"降幅 {info['drop_pct'] * 100:.1f}%），请尽快判断是否出手。",
            link="/m/items/",
            dedup_key=f"price_drop:{item_id}:{info['new_price']:.2f}",
            reset_read=True,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[price-watch] 站内通知写入失败: {e}")

    # 3. 8 渠道推送（免打扰时段降级由 NotifierHub 处理）
    if bus is not None:
        try:
            bus.publish_nowait(Event(
                type=EventType.PRICE_DROPPED,
                task_id=info.get("task_id") or "",
                item_id=item_id,
                payload=info,
            ))
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[price-watch] 渠道推送事件发布失败: {e}")
