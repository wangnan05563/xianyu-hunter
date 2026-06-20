"""任务-内容关联 API

- GET    /api/tasks/{tid}/links              列出某任务的关联（按 type 过滤）
- GET    /api/tasks/{tid}/links/count        按 type 计数
- POST   /api/tasks/{tid}/links              手动新增关联
- POST   /api/tasks/{tid}/links/refresh      实时从闲鱼搜索并刷新关联数据
- GET    /api/tasks/{tid}/links/live          实时从闲鱼搜索并直接返回（不经过数据库）
- DELETE /api/tasks/{tid}/links/{id}         解除关联
- GET    /api/tasks/links/lookup?type=&key=  反查：内容 → 任务
- GET    /api/tasks/links/search?q=&type=    跨任务模糊搜索
- POST   /api/tasks/links/auto-migrate       一次性把已有 items.task_id 同步到 task_links
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from xianyu_hunter.container import Container
from xianyu_hunter.domain.urls import build_item_url
from xianyu_hunter.infra.logger import get_logger
from xianyu_hunter.infra.repo_links import task_keyword_matches_title
from xianyu_hunter.web.deps import get_container

logger = get_logger()

router = APIRouter(prefix="/api/tasks", tags=["task-links"])

# url 类型已废弃（项目决策只保留 item/seller），保留 item/seller 两个有效类型
_VALID_TYPES = {"item", "seller"}
_VALID_SOURCES = {"auto", "manual"}


class LinkCreate(BaseModel):
    link_type: str = Field(..., description="item | seller")
    link_key: str = Field(..., min_length=1, max_length=512)
    display: dict[str, Any] | None = None
    source: str = "manual"
    note: str | None = Field(default=None, max_length=500)


@router.get("/{task_id}/links")
def list_links(
    task_id: str,
    type: str | None = Query(None, description="item | seller | url"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """列出任务的关联内容（懒加载用：前端分页拉取）"""
    if type is not None and type not in _VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"未知 type: {type}")
    if not container.repo.get_task(task_id):
        raise HTTPException(status_code=404, detail="任务不存在")
    items = container.repo.list_task_links(
        task_id=task_id, link_type=type, limit=limit, offset=offset
    )
    # 获取该类型的真实总数（不受 limit/offset 影响），供前端分页计算
    counts = container.repo.count_task_links(task_id, link_type=type)
    total_for_type = counts.get(type, len(items)) if type else counts.get("total", len(items))

    # 按价格过滤（与 live_links 保持一致，确保 DB 数据也遵守任务价格区间）
    task = container.repo.get_task(task_id)
    min_price = (task or {}).get("min_price") if task else None
    max_price = (task or {}).get("max_price") if task else None
    if (min_price is not None or max_price is not None) and items:
        _filtered = []
        pf_count = 0
        for r in items:
            # DB 数据的 price 在 display JSON 中
            price_val = r.get("display")
            if isinstance(price_val, str):
                try: price_val = json.loads(price_val)
                except: pass
            if isinstance(price_val, dict):
                price_val = price_val.get("price")
            if price_val is None:
                _filtered.append(r)
                continue
            try:
                p = float(price_val)
            except (ValueError, TypeError):
                _filtered.append(r)
                continue
            if min_price is not None and p < min_price:
                pf_count += 1; continue
            if max_price is not None and p > max_price:
                pf_count += 1; continue
            _filtered.append(r)
        if pf_count:
            logger.info("list_links 价格过滤跳过 %d 条 (min=%s, max=%s)", pf_count, min_price, max_price)
            items = _filtered
            # 过滤后总数也需要更新（分页基于过滤后数据）
            total_for_type = len(_filtered)

    # 统一字段名为 link_id（前端接口定义用 link_id，后端 DB 主键为 id）
    result_items = []
    for r in _enrich_with_item_data(items, container):
        r["link_id"] = r.pop("id", 0)  # id → link_id 映射，确保前端 rowKey/delete 正常工作
        result_items.append(r)

    return {
        "items": result_items,
        "count": len(items),
        "total": total_for_type,
        "task_id": task_id,
        "type": type,
        "limit": limit,
        "offset": offset,
    }


def _enrich_with_item_data(links: list[dict], container: Container) -> list[dict]:
    """从 items 表补充 task_links.display 中缺失的字段（region/seller_id/want_cnt/view_cnt/publish_time）

    旧数据写入 task_links 时未包含这些字段，这里从 items 表实时补全，
    避免悬停摘要和地区筛选因旧数据缺字段而无法展示。
    注意：is_sold 字段不在 items 表中（来自搜索 API 实时数据），
    此处不补全 is_sold，避免把旧数据误标为未售。
    """
    if not links:
        return links
    # 收集需要补全的 item_id（link_type=item 时 link_key 即为 item_id）
    item_ids: set[str] = set()
    for r in links:
        if r.get("link_type") == "item" and r.get("link_key"):
            item_ids.add(str(r["link_key"]))
    if not item_ids:
        return links
    # 批量查询 items 表
    from xianyu_hunter.infra.db_models import ItemRow
    from sqlalchemy import select
    try:
        with container.repo.engine.connect() as conn:
            rows = conn.execute(
                select(ItemRow).where(ItemRow.id.in_(item_ids))
            ).all()
            # 构建 item_id -> 字段映射
            item_map: dict[str, dict] = {}
            for raw in rows:
                row = container.repo._row_to_dict(raw)
                if row and row.get("id"):
                    item_map[str(row["id"])] = {
                        "region": row.get("region") or "",
                        "seller_id": row.get("seller_id") or "",
                        "seller_nick": row.get("seller_nick") or row.get("seller_id") or "",  # 优先昵称，回退到 ID
                        "want_cnt": row.get("want_cnt") or 0,
                        "view_cnt": row.get("view_cnt") or 0,
                        "publish_time": row.get("publish_time").isoformat() if row.get("publish_time") else None,
                        # 图片和链接：旧 task_links.display 可能缺少这些字段，从 items 表补全
                        "thumb_url": row.get("thumb_url") or "",
                        "url": build_item_url(str(row["id"])) if row.get("id") else "",
                    }
    except Exception as e:
        logger.warning("从 items 表补全字段失败: %s", e)
        return links
    # 补全 display JSON
    for r in links:
        if r.get("link_type") != "item":
            continue
        item_id = str(r.get("link_key", ""))
        extra = item_map.get(item_id)
        if not extra:
            continue
        display = r.get("display")
        if isinstance(display, str):
            try:
                display = json.loads(display)
            except (json.JSONDecodeError, TypeError):
                display = {}
        if not isinstance(display, dict):
            display = {}
        # 仅补全缺失的字段（不覆盖已有值，不补全 is_sold 避免误标）
        for k, v in extra.items():
            if k not in display:
                display[k] = v
        r["display"] = display
    return links


@router.get("/{task_id}/links/count")
def count_links(
    task_id: str,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """按类型返回关联计数（用于 Tab 角标）"""
    if not container.repo.get_task(task_id):
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"task_id": task_id, **container.repo.count_task_links(task_id)}


@router.post("/{task_id}/links", status_code=201)
def create_link(
    task_id: str,
    body: LinkCreate,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """手动新增关联"""
    if body.link_type not in _VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"未知 link_type: {body.link_type}")
    if body.source not in _VALID_SOURCES:
        raise HTTPException(status_code=400, detail=f"未知 source: {body.source}")
    if not container.repo.get_task(task_id):
        raise HTTPException(status_code=404, detail="任务不存在")
    link_id = container.repo.upsert_task_link(
        task_id=task_id,
        link_type=body.link_type,
        link_key=body.link_key,
        display=body.display,
        source=body.source,
        note=body.note,
    )
    return {"ok": True, "id": link_id, "task_id": task_id}


@router.delete("/{task_id}/links/{link_id}")
def delete_link(
    task_id: str,
    link_id: int,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """解除关联"""
    ok = container.repo.delete_task_link(link_id)
    if not ok:
        raise HTTPException(status_code=404, detail="关联不存在")
    return {"ok": True, "id": link_id, "task_id": task_id}


@router.post("/{task_id}/links/refresh")
async def refresh_links(
    task_id: str,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """实时从闲鱼搜索并刷新关联数据

    不再依赖数据库缓存，直接调用 Collector 实时搜索闲鱼，
    清除旧的 auto 来源关联后写入新结果。
    仅在 Web 进程持有浏览器实例时可用（XH_WITH_SCHEDULER=1 模式）。
    """
    task = container.repo.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not container.collector:
        raise HTTPException(
            status_code=503,
            detail="实时搜索需要浏览器实例，请以 XH_WITH_SCHEDULER=1 模式启动",
        )
    if not container.browser:
        raise HTTPException(
            status_code=503,
            detail="浏览器实例未初始化，请重启服务",
        )

    keyword = task.get("keyword", "")
    if not keyword:
        raise HTTPException(status_code=400, detail="任务无关键词")

    # 清除该任务旧的 auto 来源关联（manual 来源保留）
    container.repo.delete_task_links_by_task(task_id, source="auto")

    # 使用互斥锁防止 Worker 和 refresh 端点并发操作浏览器
    # 不做 is_alive() 预检——直接尝试搜索，失败时返回明确错误
    items: list[dict] = []
    try:
        async with container.browser_lock:
            try:
                # skip_lock=True：外层已持有 browser_lock，search 内部不再获取，避免死锁
                items = await container.collector.search(keyword, max_pages=2, skip_lock=True)
            except Exception as e:
                logger.exception(f"refresh_links 搜索失败 task={task_id}: {e}")
                err_msg = str(e)
                if "TargetClosed" in err_msg or "Browser has been closed" in err_msg:
                    raise HTTPException(status_code=502, detail="浏览器连接已断开，请重启服务后重试")
                if "RGV587" in err_msg:
                    raise HTTPException(status_code=401, detail="闲鱼登录已过期，请通过「浏览器登录」重新登录")
                if "Connection closed" in err_msg:
                    raise HTTPException(status_code=502, detail="浏览器连接异常，请重启服务后重试")
                raise HTTPException(status_code=502, detail=f"闲鱼搜索失败: {err_msg}")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"refresh_links 未预期异常 task={task_id}: {e}")
        raise HTTPException(status_code=502, detail=f"刷新搜索异常: {str(e)}")

    # 写入新关联
    saved = 0
    for item in items:
        try:
            container.repo.upsert_item_task_links(
                task_id=task_id,
                item_id=item.id,
                title=item.title,
                price=item.price,
                thumb_url=item.thumb_url,
                seller_id=getattr(item, "seller_id", None) or "",
                source="auto",
                region=getattr(item, "region", None),
                publish_time=getattr(item, "publish_time", None),
                want_cnt=getattr(item, "want_cnt", None),
                view_cnt=getattr(item, "view_cnt", None),
                is_sold=getattr(item, "is_sold", False),
            )
            saved += 1
        except Exception as e:
            logger.warning("写入关联失败 item=%s: %s", getattr(item, "id", "?"), e)

    # 返回刷新后的统计
    counts = container.repo.count_task_links(task_id)
    return {
        "ok": True,
        "task_id": task_id,
        "keyword": keyword,
        "found": len(items),
        "saved": saved,
        "counts": counts,
    }


@router.get("/{task_id}/links/live")
async def live_links(
    task_id: str,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """实时从闲鱼搜索并直接返回结果（不经过数据库）

    与 /links/refresh 的区别：
    - refresh: 搜索 → 写入DB → 返回计数（前端再调 /links 读DB）
    - live: 搜索 → 直接返回结果列表（完全不依赖数据库）

    仅在 Web 进程持有浏览器实例时可用（XH_WITH_SCHEDULER=1 模式）。
    """
    task = container.repo.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not container.collector:
        raise HTTPException(
            status_code=503,
            detail="实时搜索需要浏览器实例，请以 XH_WITH_SCHEDULER=1 模式启动",
        )
    if not container.browser:
        raise HTTPException(
            status_code=503,
            detail="浏览器实例未初始化，请重启服务",
        )

    keyword = task.get("keyword", "")
    if not keyword:
        raise HTTPException(status_code=400, detail="任务无关键词")

    # 读取任务价格过滤条件（与 Worker 保持一致）
    min_price = task.get("min_price")
    max_price = task.get("max_price")
    max_publish_days = task.get("max_publish_days")

    # 使用互斥锁防止并发操作浏览器，设 10 秒超时避免长时间卡住
    raw_results: list[dict] = []
    try:
        try:
            await asyncio.wait_for(container.browser_lock.acquire(), timeout=10.0)
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=503,
                detail="系统正在执行后台搜索任务，请稍后重试",
            )
        try:
            # 快速搜索：max_pages=1 减少翻页等待，skip_m5tk=True 跳过 token 刷新（Worker 会处理）
            # 加 30 秒超时保护：浏览器实例损坏或 page.goto 卡住时避免请求无限等待
            try:
                raw_results = await asyncio.wait_for(
                    container.collector.live_search(
                        keyword, max_pages=1, collect_sellers=False, fast=True,
                    ),
                    timeout=30.0,
                )
            except asyncio.TimeoutError:
                raise HTTPException(status_code=504, detail="实时搜索超时，请稍后重试或重启服务")
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"实时搜索失败 task={task_id}: {e}")
            err_msg = str(e)
            if "TargetClosed" in err_msg or "Browser has been closed" in err_msg:
                raise HTTPException(status_code=502, detail="浏览器连接已断开，请重启服务后重试")
            if "RGV587" in err_msg:
                raise HTTPException(status_code=401, detail="闲鱼登录已过期，请通过「浏览器登录」重新登录")
            if "Connection closed" in err_msg:
                raise HTTPException(status_code=502, detail="浏览器连接异常，请重启服务后重试")
            raise HTTPException(status_code=502, detail=f"闲鱼搜索失败: {err_msg}")
        finally:
            container.browser_lock.release()
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"live_links 未预期异常 task={task_id}: {e}")
        raise HTTPException(status_code=502, detail=f"实时搜索异常: {str(e)}")

    # 格式化为前端期望的 task_links 行格式（与 DB 查询结果一致）
    now = datetime.now(timezone.utc).isoformat()
    results: list[dict] = []
    for r in raw_results:
        results.append({
            "link_id": 0,  # 实时数据无DB id，用0占位（前端需link_id字段）
            "task_id": task_id,
            "link_type": r["link_type"],
            "link_key": r["link_key"],
            "source": "live",
            "display": {
                "title": r.get("title", ""),
                "price": r.get("price"),
                "thumb_url": r.get("thumb_url", ""),
                "region": r.get("region", ""),
                "url": r.get("url", ""),
                "is_sold": r.get("is_sold", False),
                "publish_time": r.get("publish_time"),
                "seller_id": r.get("seller_id", ""),
                "seller_nick": r.get("seller_nick", ""),
                "want_cnt": r.get("want_cnt"),
                "view_cnt": r.get("view_cnt"),
            },
            "note": None,
            "created_at": now,
        })

    # 按关键词过滤：即使搜索API返回相关结果，也作为安全兜底过滤无关商品
    filtered = []
    for r in results:
        title = (r.get("display") or {}).get("title", "")
        if task_keyword_matches_title(keyword, title):
            filtered.append(r)
    skipped = len(results) - len(filtered)
    if skipped:
        logger.info("live_links 关键词过滤跳过了 %d 条无关结果", skipped)

    # 按价格过滤（与 Worker 的 price.check 逻辑保持一致）
    price_filtered = 0
    if min_price is not None or max_price is not None:
        _filtered = []
        for r in filtered:
            price = (r.get("display") or {}).get("price")
            if price is None:
                _filtered.append(r)  # 无价格信息不过滤
                continue
            try:
                p = float(price)
            except (ValueError, TypeError):
                _filtered.append(r)
                continue
            if min_price is not None and p < min_price:
                price_filtered += 1
                continue
            if max_price is not None and p > max_price:
                price_filtered += 1
                continue
            _filtered.append(r)
        filtered = _filtered
        if price_filtered:
            logger.info("live_links 价格过滤跳过了 {} 条 (min={}, max={})", price_filtered, min_price, max_price)

    # 按发布天数过滤（仅展示最近 N 天内发布的商品）
    days_filtered = 0
    if max_publish_days is not None:
        from datetime import datetime as _dt
        _now = _dt.now()
        _filtered = []
        for r in filtered:
            pub = (r.get("display") or {}).get("publish_time")
            if not pub:
                _filtered.append(r)  # 无发布时间不过滤
                continue
            try:
                pub_dt = _dt.fromisoformat(str(pub).replace("Z", "+00:00"))
                if (_now - pub_dt).days > max_publish_days:
                    days_filtered += 1
                    continue
            except (ValueError, TypeError):
                pass
            _filtered.append(r)
        filtered = _filtered
        if days_filtered:
            logger.info("live_links 发布天数过滤跳过了 {} 条 (max_days={})", days_filtered, max_publish_days)

    # 按类型分组（url 类型已废弃，item 的 link_key 可由前端自动拼接为完整 URL）
    items = [r for r in filtered if r["link_type"] == "item"]
    sellers = [r for r in filtered if r["link_type"] == "seller"]

    # 检测 Cookie 失效：搜索结果为空且 collector 标记会话失效
    # last_session_invalid 由 search() 在 RGV587_ERROR 时设置
    session_expired = (
        not raw_results
        and getattr(container.collector, "last_session_invalid", False)
    )
    # 额外检测：API 响应被捕获但解析为 0 个商品（可能是登录墙响应）
    if not session_expired and not raw_results:
        api_captured = getattr(container.collector, "_last_api_captured", False)
        if api_captured:
            session_expired = True

    return {
        "ok": True,
        "task_id": task_id,
        "keyword": keyword,
        "session_expired": session_expired,
        "counts": {
            "item": len(items),
            "seller": len(sellers),
            "total": len(filtered),
        },
        "items": filtered,
        "sellers": sellers,
        "all": filtered,
    }


# ============== 反查 / 搜索（跨任务） ==============

# 把这两个挂到 /api/tasks/links 而非 /api/tasks/{tid}/links
# 否则 FastAPI 会把 "links" 当作 task_id
_links_lookup = APIRouter(prefix="/api/tasks/links", tags=["task-links"])


@_links_lookup.get("/lookup")
def lookup(
    type: str = Query(..., description="item | seller | url"),
    key: str = Query(..., min_length=1, max_length=512),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """反查：给定 (type, key)，返回所有关联此 key 的任务链接行。

    使用场景：在「关联面板」上方搜索一个 item_id，能列出哪些任务也关联了它。
    """
    if type not in _VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"未知 type: {type}")
    rows = container.repo.lookup_task_links(link_type=type, link_key=key)
    return {"items": rows, "count": len(rows), "type": type, "key": key}


@_links_lookup.get("/search")
def search(
    q: str = Query(..., min_length=1, max_length=200),
    type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """跨任务模糊搜索（key 或 display 字段包含 q）"""
    if type is not None and type not in _VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"未知 type: {type}")
    rows = container.repo.search_task_links(q=q, link_type=type, limit=limit)
    return {"items": rows, "count": len(rows), "q": q, "type": type}


@_links_lookup.post("/auto-migrate")
def auto_migrate(
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """一次性把 items.task_id 隐式关联同步到 task_links 表。

    通常在 web 启动时调用一次即可；后续 Worker 抓新商品时也会写 task_links。
    """
    inserted = container.repo.auto_migrate_task_links()
    return {"ok": True, "inserted": inserted}
