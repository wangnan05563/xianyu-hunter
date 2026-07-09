"""官方采集 API — 官方页面采集 + 重新评估

从 api_evaluations.py 拆分。
解决评估明细页依赖本地采集数据信息有限的问题：
优先访问闲鱼官方商品详情页+卖家主页，获取完整权威数据后重新评估。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from loguru import logger
from pydantic import BaseModel, Field

from xianyu_hunter.container import Container
from xianyu_hunter.web.deps import get_container

router = APIRouter(prefix="/api/evaluations", tags=["evaluations"])


# 官方采集所需的身份 Cookie（与 live_search 一致，确保登录态有效）
_OFFICIAL_COLLECT_IDENTITY_COOKIES = ("cookie2", "sgcookie", "unb")


async def _ensure_official_collect_cookies(container: Container) -> None:
    from xianyu_hunter.modules.collection_service import (
        CollectionError,
        ItemCollectionService,
    )

    try:
        await ItemCollectionService(container).ensure_official_cookies()
    except CollectionError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


async def _extract_reviews_from_page(page) -> list[str]:
    """从商品详情页 DOM 中尝试提取评价/留言信息

    闲鱼详情页的评价模块结构可能随版本变化，使用宽松选择器 + try-except，
    提取失败时返回空列表，不影响主采集流程。
    """
    reviews: list[str] = []
    # 候选选择器：覆盖闲鱼详情页可能的评价/留言/评论模块命名
    review_selectors = [
        "[class*='review'] [class*='item']",
        "[class*='comment'] [class*='item']",
        "[class*='evaluation'] [class*='item']",
        "[class*='message'] [class*='item']",
    ]
    for sel in review_selectors:
        try:
            els = await page.query_selector_all(sel)
            for el in els[:10]:  # 最多取 10 条，避免过多影响性能
                text = (await el.inner_text()).strip()
                if text and len(text) > 5:  # 过滤过短的无效文本
                    reviews.append(text)
            if reviews:
                break
        except Exception:
            continue
    return reviews


async def _collect_official_and_evaluate(
    container: Container,
    item_id: str,
    task_id: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    from xianyu_hunter.modules.collection_service import (
        CollectionError,
        CollectionMode,
        ItemCollectionService,
    )

    try:
        result = await ItemCollectionService(container).collect(
            item_id,
            task_id=task_id,
            mode=CollectionMode.OFFICIAL_FULL,
            source="official",
            user_id=user_id,
        )
    except CollectionError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

    detail = result.detail
    seller = result.seller
    eval_result = result.evaluation
    if detail is None or eval_result is None:
        raise HTTPException(status_code=502, detail=f"Official collection {item_id} returned incomplete result")

    return {
        "ok": True,
        "item_id": item_id,
        "collected": True,
        "item": {
            "title": detail.title,
            "price": detail.price,
            "description": detail.description or "",
            "image_urls": detail.image_urls or [],
            "thumb_url": detail.thumb_url or "",
            "region": detail.region or "",
            "seller_id": detail.seller_id or "",
            "want_cnt": detail.want_cnt,
            "view_cnt": detail.view_cnt,
        },
        "seller": {
            "id": seller.id if seller else "",
            "nick": seller.nick if seller else "",
            "credit_score": seller.credit_score if seller else None,
            "register_days": seller.register_days if seller else 0,
            "on_sale_count": seller.on_sale_count if seller else 0,
            "sold_count": seller.sold_count if seller else 0,
        },
        "reviews": result.reviews,
        "evaluation": {
            "score": eval_result.score,
            "risk_level": eval_result.risk_level.value,
            "dimension_scores": eval_result.dimension_scores,
            "reject_reasons": eval_result.reject_reasons,
            "is_passed": eval_result.is_passed,
            "data_quality": eval_result.data_quality,
            "data_source": "official",
        },
    }


class BatchCollectRequest(BaseModel):
    """批量官方采集请求体"""
    item_ids: list[str] = Field(..., min_length=1, max_length=50, description="商品 ID 列表，最多 50 个")


# ==== batch_collect_official 辅助函数 ====
def _classify_http_error_code(status_code: int) -> str:
    """根据 HTTP 状态码分类失败原因，方便调用方决定是否重试

    - 410: 商品已下架/不存在 → 不应重试
    - 其他业务错误 → 标记为 unknown，由调用方自行判断"""
    if status_code == 410:
        return "item_not_found"
    return "unknown"


def _classify_exception_error(e: Exception) -> str:
    """区分网络错误与未知错误

    网络错误通常可重试，未知错误不应盲目重试"""
    if isinstance(e, (TimeoutError, ConnectionError, OSError)):
        return "network_error"
    err_str = str(e)
    if "Timeout" in err_str or "ConnectError" in err_str or "Connection" in err_str:
        return "network_error"
    return "unknown"


@router.post("/batch-collect-official")
async def batch_collect_official(
    request: Request,
    body: BatchCollectRequest = Body(...),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """批量官方采集+评估

    串行采集每个商品（避免并发触发反爬虫），逐个返回结果。
    单个失败不中断整体流程，最终汇总成功/失败数。
    """
    item_ids = body.item_ids
    if not container.collector:
        raise HTTPException(
            status_code=503,
            detail="官方采集需要浏览器实例，请以 XH_WITH_SCHEDULER=1 模式启动",
        )
    if not container.browser:
        raise HTTPException(
            status_code=503,
            detail="浏览器实例未初始化，请重启服务",
        )

    results: list[dict] = []
    succeeded = 0
    failed = 0
    user_id = getattr(request.state, "user_id", None)

    for iid in item_ids:
        try:
            async with container.browser_lock:
                result = await _collect_official_and_evaluate(container, iid, user_id=user_id)
            results.append(result)
            succeeded += 1
        except HTTPException as e:
            # Cookie 失效类错误立即中断：后续商品也会逐个失败，浪费时间
            # - 403: Cookie 不完整（_ensure_official_collect_cookies 检测到缺失关键 cookie）
            # - 440: Cookie 过期/未刷新（重定向到登录页/首页）
            # - 441: 触发验证码（RGV587 反爬）
            # 注意：不检查 401——project_memory 要求闲鱼会话失效统一用 403/440/441，
            # 401 会触发前端 axios 全局登出逻辑（误判为系统认证失效）
            if e.status_code in (403, 440, 441):
                raise
            error_code = _classify_http_error_code(e.status_code)
            results.append({
                "ok": False, "item_id": iid, "error": e.detail,
                "error_code": error_code,
            })
            failed += 1
        except Exception as e:
            logger.exception("批量采集失败 item={}: {}", iid, e)
            err_str = str(e)
            error_code = _classify_exception_error(e)
            results.append({
                "ok": False, "item_id": iid, "error": err_str,
                "error_code": error_code,
            })
            failed += 1

    return {
        "ok": True,
        "total": len(item_ids),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
        "message": f"批量采集完成：成功 {succeeded}，失败 {failed}",
    }


@router.post("/{item_id}/collect-official")
async def collect_official(
    item_id: str,
    request: Request,
    task_id: str | None = Query(None, description="可选：指定任务 ID"),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """单条官方采集+评估

    访问闲鱼官方商品详情页和卖家主页，采集完整数据后重新评估。
    采集结果持久化到 items/sellers/events 表，评估标记 data_source=official。
    """
    if not item_id:
        raise HTTPException(status_code=400, detail="item_id 必填")
    if not container.collector:
        raise HTTPException(
            status_code=503,
            detail="官方采集需要浏览器实例，请以 XH_WITH_SCHEDULER=1 模式启动",
        )
    if not container.browser:
        raise HTTPException(
            status_code=503,
            detail="浏览器实例未初始化，请重启服务",
        )

    try:
        user_id = getattr(request.state, "user_id", None)
        async with container.browser_lock:
            result = await _collect_official_and_evaluate(container, item_id, task_id, user_id=user_id)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("官方采集失败 item={}: {}", item_id, e)
        err_msg = str(e)
        if "TargetClosed" in err_msg or "Browser has been closed" in err_msg:
            raise HTTPException(status_code=502, detail="浏览器连接已断开，请重启服务后重试")
        if "RGV587" in err_msg:
            # 反爬触发统一用 441，区别于 403（cookie 缺失）和 502（系统故障）
            raise HTTPException(status_code=441, detail="搜索令牌临时过期，请稍后重试；若持续失败请重新登录闲鱼")
        if "Connection closed" in err_msg:
            raise HTTPException(status_code=502, detail="浏览器连接异常，请重启服务后重试")
        raise HTTPException(status_code=502, detail=f"官方采集失败: {err_msg}")
