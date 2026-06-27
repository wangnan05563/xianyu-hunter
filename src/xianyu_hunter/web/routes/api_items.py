"""商品（item）API（P3-UX-02）

提供商品轻量级查询，供"抢单记录"等列表页异步拉取商品标题使用。
- 之前：列表只显示 item_id，用户要"是不是想要的那一单"得逐个点开
- 现在：列表异步展示商品标题（一行字），用 sessionStorage 缓存减少重复请求
"""
from __future__ import annotations

import asyncio
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


@router.post("/{item_id}/refresh")
async def refresh_item(
    item_id: str,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """刷新单个商品详情：采集详情页并更新 items 表 + task_links.display

    触发场景：
    - 前端商品列表点击商品链接时异步调用
    - 官方采集流程复用
    - 抢单失败回退刷新
    """
    from loguru import logger

    # 校验 collector 是否可用（Web 进程 with_browser=False 时为 None）
    if container.collector is None:
        raise HTTPException(
            status_code=503,
            detail="需要浏览器实例，请以 XH_WITH_SCHEDULER=1 模式启动",
        )

    item = container.repo.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="商品不存在")

    # detail() 内部 page.goto 已有 30s 超时，但 page.query_selector 等无 timeout 参数，
    # 浏览器实例异常（页面/上下文已关闭）时会无限挂起。
    # 这里加 60s 整体超时：detail 正常应在 30s 内完成，60s 是合理上限；
    # 超时说明浏览器实例异常或闲鱼反爬拦截，返回 504 让客户端知道是网关超时而非业务错误
    try:
        detail = await asyncio.wait_for(
            container.collector.detail(item_id), timeout=60.0
        )
    except asyncio.TimeoutError:
        logger.warning(f"[RefreshItem] 采集超时 item={item_id}（60s），浏览器实例可能异常")
        raise HTTPException(
            status_code=504,
            detail="采集超时：浏览器实例异常或闲鱼反爬拦截，请稍后重试或重启服务",
        )
    except Exception as e:
        logger.warning(f"[RefreshItem] 采集失败 item={item_id}: {e}")
        raise HTTPException(status_code=502, detail=f"采集失败：{e}")

    if detail is None:
        raise HTTPException(status_code=502, detail="采集商品详情失败：页面不可达或登录已过期")

    # 更新 items 表（复用官方采集的旧值保留策略，避免清空已有字段）
    new_row = {
        "id": item_id,
        "task_id": item.get("task_id") or "",
        "title": detail.title,
        "price": detail.price,
        "seller_id": detail.seller_id or "",
        "region": detail.region or "",
        "want_cnt": detail.want_cnt,
        "view_cnt": detail.view_cnt,
        "thumb_url": detail.thumb_url or "",
        "is_sold": 1 if detail.is_sold else 0,
    }
    container.repo.upsert_item(new_row)
    # 已售时通过 mark_sold 补写 sold_detected_at + 同步 task_links.display
    if detail.is_sold:
        container.repo.mark_sold(item_id)

    # 同步 task_links.display：评估明细页 brand 等字段从此处读取
    # 为什么不全量覆盖 display：worker.py 写入的 seller_credit 等字段不在 detail 中，
    # 直接 upsert 会丢失。改为读取现有 display 后按字段合并，仅当新值非空时覆盖。
    task_id = item.get("task_id") or ""
    if task_id:
        existing_map = container.repo.list_link_displays_by_keys([item_id], link_type="item")
        existing_display = existing_map.get(item_id, {})
        merged_display = dict(existing_display)
        # 用 detail 采集到的字段覆盖（非空才覆盖，避免清空已有有效值）
        if detail.title:
            merged_display["title"] = detail.title
        if detail.price is not None:
            merged_display["price"] = detail.price
        if detail.seller_id:
            merged_display["seller_id"] = detail.seller_id
        if detail.region:
            merged_display["region"] = detail.region
        if detail.thumb_url:
            merged_display["thumb_url"] = detail.thumb_url
        if detail.want_cnt is not None:
            merged_display["want_cnt"] = detail.want_cnt
        if detail.view_cnt is not None:
            merged_display["view_cnt"] = detail.view_cnt
        if detail.publish_time is not None:
            merged_display["publish_time"] = detail.publish_time.isoformat()
        if detail.is_sold is not None:
            merged_display["is_sold"] = detail.is_sold
        # brand 字段：仅当 detail 提取/推断到非空 brand 时覆盖原有值
        # 避免详情页未识别到品牌时清空已有的搜索 API brand
        if detail.brand:
            merged_display["brand"] = detail.brand
        container.repo.upsert_task_link(
            task_id=task_id,
            link_type="item",
            link_key=item_id,
            display=merged_display,
            source="auto",
        )

    logger.info(f"[RefreshItem] 刷新成功 item={item_id} is_sold={detail.is_sold} brand={detail.brand!r}")
    return {
        "ok": True,
        "item_id": item_id,
        "is_sold": detail.is_sold,
        "title": detail.title,
        "price": detail.price,
        "brand": detail.brand,
    }
