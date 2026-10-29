"""降价检测与即时提醒（PRD FR-F1-3 / FR-F1-4，REQ-008/009）

检测规则（FR-F1-3）：新快照价 < 该商品此前最低价 × (1 - 阈值)（任务级可配，
price_config.price_drop_threshold，默认 0%）即触发降价事件。

通知三路（FR-F1-4）：
1. 事件时间线：repo.save_event（stage=price_drop）
2. 站内通知：repo.add_notification（category=NotificationCategory.PRICE，dedup 防同价重复刷屏）
   —— 分类字面值取自 domain/notification（T02619）：写死 "price" 时它不在 API 白名单里，
   前端通知中心渲染该条也取不到中文标签，只能显示空白。
3. 8 渠道推送：EventBus 发布 PRICE_DROPPED → NotifierHub fan-out（免打扰降级由 hub 处理）

检测时序关键点：必须在写入新快照【之前】取旧最低价，
否则新价入表后 min_price 已被更新，永远检测不到降价。
"""
from __future__ import annotations

from typing import Any

from xianyu_hunter.domain.events import Event, EventType
from xianyu_hunter.domain.notification import NotificationCategory
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
    # 容差 1e-9 抵御浮点误差；因此「大于等于阈值线」即不触发
    if float(price) >= prev_min * (1 - threshold) - 1e-9:
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
    suppress_notify: bool = False,
) -> list[dict]:
    """批量观察（采集链路）：先整批取旧最低价 → 批量写快照 → 检测降价

    降级保护（FR-F1-5）：
    - suppress_notify=True 时只写快照不通知（批量采集首轮全量建快照场景，
      调用方判定首轮后传入，避免冷启动轰炸）
    - 单轮多条降价合并为一条汇总推送（同一任务一次推送汇总多条降价）

    Returns:
        触发降价的商品信息列表（suppress_notify=True 时仍返回检测结果但不通知）
    """
    candidates = _collect_candidates(items)
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
        drop = _build_drop(
            repo, cid, price, prev_mins.get(cid), threshold, source, task_id, user_id
        )
        if drop is not None:
            drops.append(drop)

    _notify_batch_drops(repo, bus, drops, candidates, prev_mins, suppress_notify, user_id)
    return drops


def _collect_candidates(items: list[dict]) -> list[tuple[str, float]]:
    """从采集结果筛出可参与比价的商品：有 ID、价格为数值且大于 0"""
    return [
        (it["id"], float(it["price"]))
        for it in items
        if it.get("id") and isinstance(it.get("price"), (int, float)) and it["price"] > 0
    ]


def _build_drop(
    repo: Repository,
    item_id: str,
    price: float,
    prev_min: float | None,
    threshold: float,
    source: str,
    task_id: str | None,
    user_id: str | None,
) -> dict | None:
    """单条降价判定：严格跌破阈值线才返回降价信息，否则返回 None

    与单条路径同口径：同价已被快照去重，只有 price 严格小于
    prev_min × (1 - threshold) - 1e-9 才算降价。
    """
    if prev_min is None or price >= prev_min * (1 - threshold) - 1e-9:
        return None
    drop_pct = (prev_min - price) / prev_min if prev_min > 0 else 0.0
    item = repo.get_item(item_id, user_id=user_id) or {}
    return {
        "item_id": item_id,
        "item_title": item.get("title") or "",
        "new_price": price,
        "prev_min_price": float(prev_min),
        "drop_pct": round(drop_pct, 4),
        "source": source,
        "task_id": task_id or "",
    }


def _notify_batch_drops(
    repo: Repository,
    bus,
    drops: list[dict],
    candidates: list[tuple[str, float]],
    prev_mins: dict[str, float | None],
    suppress_notify: bool,
    user_id: str | None,
) -> None:
    """批量降价通知：冷启动抑制 + 单条直推 / 多条汇总"""
    if not drops or suppress_notify:
        return
    # 冷启动自动抑制（FR-F1-5 首轮跳过）：本批全部商品均无快照历史
    # （prev_min 全 None）说明是首轮全量建快照，任何「下跌」都无从谈起，
    # 不推送。部分商品有旧快照时（重新采集）跌价通知是有效的，正常触发
    cold_start = all(prev_mins.get(cid) is None for cid, _ in candidates)
    if cold_start:
        logger.info(f"[price-watch] 首轮全量建快照（{len(candidates)} 个商品），抑制降价通知")
    elif len(drops) == 1:
        _emit_drop_notifications(repo, bus, drops[0], user_id=user_id)
    else:
        # FR-F1-5 合并推送：同一任务一轮内多条降价汇总为一条通知，
        # 避免批量采集后推送风暴淹没用户
        _emit_drop_summary(repo, bus, drops, user_id=user_id)


def _emit_drop_summary(
    repo: Repository, bus, drops: list[dict], user_id: str | None = None
) -> None:
    """多条降价合并推送（FR-F1-5）：一条站内通知 + 一条渠道推送事件"""
    import json as _json

    task_id = drops[0].get("task_id") or ""
    # 按降幅降序：最值得关注的排在最前
    ordered = sorted(drops, key=lambda d: d["drop_pct"], reverse=True)
    top = ordered[0]
    total_drop = sum(d["drop_pct"] for d in drops)
    summary_line = "；".join(
        f"{d['item_title'] or d['item_id']} ¥{d['new_price']:.2f}（-{d['drop_pct'] * 100:.1f}%）"
        for d in ordered[:5]
    )
    more = len(ordered) - 5
    message_text = (
        f"{len(drops)} 个商品降价，最大降幅 {top['drop_pct'] * 100:.1f}%：{summary_line}"
        + (f" 等共 {len(drops)} 条" if more > 0 else "")
    )
    try:
        event_row = {
            "type": EventType.PRICE_DROPPED.value,
            "task_id": task_id or None,
            "stage": "price_drop",
            "level": "info",
            "message": message_text,
            "payload": _json.dumps({"summary": True, "drops": ordered}, ensure_ascii=False),
        }
        if user_id:
            event_row["user_id"] = user_id
        repo.save_event(event_row)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[price-watch] 汇总事件写入失败: {e}")
    try:
        repo.add_notification(
            level="warn",
            category=NotificationCategory.PRICE.value,
            title=f"降价汇总：{len(drops)} 个商品降价（最大 {top['drop_pct'] * 100:.1f}%）",
            message=message_text,
            link="/m/items/",
            dedup_key=f"price_drop_summary:{task_id}:{int(total_drop * 10000)}:{len(drops)}",
            reset_read=True,
            # 归属跟随盯盘任务所属用户（T02618）：None 时仓储兜底 default，
            # 否则真实用户的降价提醒会全部落在 default 名下、他自己的通知中心空白
            user_id=user_id,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[price-watch] 汇总站内通知写入失败: {e}")
    if bus is not None:
        try:
            bus.publish_nowait(Event(
                type=EventType.PRICE_DROPPED,
                task_id=task_id,
                item_id=top["item_id"],
                payload={"summary": True, "drops": ordered, "count": len(ordered)},
            ))
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[price-watch] 汇总渠道推送发布失败: {e}")


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
            category=NotificationCategory.PRICE.value,
            title=f"降价提醒：{info['item_title'] or item_id}",
            message=f"现价 ¥{info['new_price']:.2f}（历史最低 ¥{info['prev_min_price']:.2f}，"
                    f"降幅 {info['drop_pct'] * 100:.1f}%），请尽快判断是否出手。",
            link="/m/items/",
            dedup_key=f"price_drop:{item_id}:{info['new_price']:.2f}",
            reset_read=True,
            user_id=user_id,  # 同上：归属跟随任务所属用户（T02618）
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
