"""商品（item）API（P3-UX-02）

提供商品轻量级查询，供"抢单记录"等列表页异步拉取商品标题使用。
- 之前：列表只显示 item_id，用户要"是不是想要的那一单"得逐个点开
- 现在：列表异步展示商品标题（一行字），用 sessionStorage 缓存减少重复请求
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from xianyu_hunter.container import Container
from xianyu_hunter.web.deps import get_container

router = APIRouter(prefix="/api/items", tags=["items"])


@router.get("/{item_id}/summary")
def item_summary(
    item_id: str,
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
    item = container.repo.get_item(item_id)
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
    summaries: dict[str, Any] = {}
    missing: list[str] = []
    for iid in id_list:
        item = container.repo.get_item(iid)
        if not item:
            missing.append(iid)
            continue
        summaries[iid] = {
            "title": item.get("title") or item.get("name") or None,
            "price": item.get("price"),
            "seller_id": item.get("seller_id"),
        }
    return {"summaries": summaries, "missing": missing, "count": len(summaries)}
