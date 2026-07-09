"""商品（item）API（P3-UX-02）

提供商品轻量级查询，供"抢单记录"等列表页异步拉取商品标题使用。
- 之前：列表只显示 item_id，用户要"是不是想要的那一单"得逐个点开
- 现在：列表异步展示商品标题（一行字），用 sessionStorage 缓存减少重复请求
"""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from xianyu_hunter.container import Container
from xianyu_hunter.web.deps import get_container

router = APIRouter(prefix="/api/items", tags=["items"])


@router.get("/{item_id}/summary")
def item_summary(
    item_id: str,
    request: Request,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """商品概要：标题 + 价格 + 卖家 ID

    为什么是 summary 而不是完整 item：列表页只关心"这是啥 + 多少钱"，
    完整 item 含描述 / 评价 / 风险分等大字段，序列化开销大。
    为什么不缓存到 Redis：单机 SQLite 部署，单条查询走主键即 < 1ms；
    浏览器侧 sessionStorage 二次缓存足够。
    """
    if not item_id:
        raise HTTPException(status_code=400, detail="item_id 必填")
    # 多用户隔离：仅返回当前账号拥有的商品
    user_id = getattr(request.state, "user_id", None)
    item = container.repo.get_item(item_id, user_id=user_id)
    if not item:
        # 返回 200 + null：列表页批量拉时，个别缺失不应阻塞其他行
        return {"item_id": item_id, "title": None, "price": None, "seller_id": None}
    return {
        "item_id": item.get("id") or item_id,
        # 商品标题是用户在"是不是想要的"决策时最关注的字段；
        # 没有 title（早期数据）时退回 item_id 至少不显示空字符串
        "title": item.get("title") or item.get("name") or None,
        "price": item.get("price"),
        "seller_id": item.get("seller_id"),
    }


@router.get("/batch")
def items_batch(
    request: Request,
    ids: str = Query(..., description="逗号分隔的 item_id 列表，最多 50 个"),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """批量拉取商品概要（列表页一次性补全更省请求）

    入参：?ids=id1,id2,id3
    出参：{summaries: {id1: {...}, id2: {...}}, missing: [id3]}

    为什么不直接走 /items/{id}/summary × N：浏览器并发 6 个限制，
    50 行订单要拉 50 次太慢；后端 1 次查询也能走 IN (?, ?, ...) 索引。
    """
    id_list = [x.strip() for x in ids.split(",") if x.strip()]
    if not id_list:
        raise HTTPException(status_code=400, detail="ids 必填")
    if len(id_list) > 50:
        raise HTTPException(status_code=400, detail="一次最多 50 个")
    # 多用户隔离：仅返回当前账号拥有的商品
    user_id = getattr(request.state, "user_id", None)
    summaries: dict[str, Any] = {}
    missing: list[str] = []
    for iid in id_list:
        item = container.repo.get_item(iid, user_id=user_id)
        if not item:
            missing.append(iid)
            continue
        summaries[iid] = {
            "title": item.get("title") or item.get("name") or None,
            "price": item.get("price"),
            "seller_id": item.get("seller_id"),
        }
    return {"summaries": summaries, "missing": missing, "count": len(summaries)}


@router.post("/{item_id}/refresh")
async def refresh_item(
    item_id: str,
    request: Request,
    task_id: str | None = Query(None, description="可选：指定任务 ID，items 表无记录时用于回填 task_links.display"),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """轻量刷新：仅采集商品详情页并 upsert 到 items + task_links.display

    语义：
        轻量刷新，只调用 ``collector.detail(item_id)`` 采集商品详情，
        然后 ``upsert_item`` 写回 items 表，并 ``sync_item_display_from_detail``
        同步 task_links.display。已售时额外 ``mark_sold`` 补写 sold_detected_at。

    不做什么（与完整官方采集的语义边界）：
        - 不触发 ``evaluator.evaluate`` 重新评估
        - 不采集卖家主页（``seller_profile``）
        - 不提取评价/留言（``_extract_reviews_from_page``）
        - 不写 ``eval.scored`` 事件、不更新 sellers 表

    用途：
        用户在商品列表点击商品标题链接时手动触发，用于快速更新商品基础信息
        （标题、价格、已售状态、品牌等），不做重计算。

    完整官方采集：
        若需要 detail + seller + reviews + 重新评估 + events 写入的端到端流程，
        请改用 ``POST /api/evaluations/{item_id}/collect-official`` 端点
        （对应 ``_collect_official_and_evaluate``）。

    为什么允许 items 表无记录：
        评估列表的 item_id 来自 events 表（eval.* 事件），常见场景是评估事件
        已写入但 items 表尚未入库。本端点本身就是为了采集并写入 items 表，
        若要求 items 表必须已有记录则自相矛盾，且会让"评估列表点击标题"
        在首条采集前直接 404，无法触发采集。

    Args:
        item_id: 商品 ID。
        task_id: 可选任务 ID，items 表无记录时用于回填 task_links.display。
        container: 应用容器，提供 ``collector`` / ``repo`` 等依赖。

    Returns:
        dict: 包含 ``ok`` / ``item_id`` / ``is_sold`` / ``title`` / ``price`` /
        ``brand`` 的轻量结果。``brand`` 为详情页推断的品牌（可能为空字符串）。
    """
    from loguru import logger

    from xianyu_hunter.modules.collection_service import (
        CollectionError,
        CollectionMode,
        ItemCollectionService,
    )

    if container.collector is None:
        raise HTTPException(
            status_code=503,
            detail="需要浏览器实例，请以 XH_WITH_SCHEDULER=1 模式启动",
        )

    try:
        user_id = getattr(request.state, "user_id", None)
        result = await asyncio.wait_for(
            ItemCollectionService(container).collect(
                item_id,
                task_id=task_id,
                mode=CollectionMode.DETAIL_ONLY,
                source="live",
                user_id=user_id,
            ),
            timeout=60.0,
        )
    except asyncio.TimeoutError:
        logger.warning(f"[RefreshItem] collection timeout item={item_id}")
        raise HTTPException(
            status_code=504,
            detail="采集超时：浏览器实例异常或闲鱼反爬拦截，请稍后重试或重启服务",
        )
    except CollectionError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

    detail = result.detail
    if detail is None:
        raise HTTPException(status_code=502, detail="采集商品详情失败：未返回详情")
    return {
        "ok": True,
        "item_id": item_id,
        "is_sold": detail.is_sold,
        "title": detail.title,
        "price": detail.price,
        "brand": detail.brand,
        "seller_id": detail.seller_id or "",
        "region": detail.region or "",
        "want_cnt": detail.want_cnt,
        "view_cnt": detail.view_cnt,
        "thumb_url": detail.thumb_url or "",
        "image_urls": detail.image_urls or [],
        "publish_time": detail.publish_time.isoformat() if detail.publish_time else None,
        "seller_nick": detail.detail_seller_nick or "",
        "seller_credit": detail.detail_credit_score,
    }


