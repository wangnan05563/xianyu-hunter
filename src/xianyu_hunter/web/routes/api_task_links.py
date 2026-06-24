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
import functools
import json
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

from xianyu_hunter.container import Container
from xianyu_hunter.domain.urls import build_item_url
from xianyu_hunter.infra.logger import get_logger
from xianyu_hunter.infra.repo_links import task_keyword_matches_title
from xianyu_hunter.modules.collector_utils import normalize_display_fields
from xianyu_hunter.web.deps import get_container

logger = get_logger()

# 实时搜索结果缓存：task_id -> (monotonic_timestamp, result_dict)
# 60 秒 TTL：避免短时间重复搜索闲鱼（每次搜索 15-20s），60 秒内返回缓存结果
_live_cache: dict[str, tuple[float, dict]] = {}
_LIVE_CACHE_TTL = 60

router = APIRouter(prefix="/api/tasks", tags=["task-links"])

# url 类型已废弃（项目决策只保留 item/seller），保留 item/seller 两个有效类型
_VALID_TYPES = {"item", "seller"}
_VALID_SOURCES = {"auto", "manual"}
_LIVE_SEARCH_IDENTITY_COOKIES = ("cookie2", "sgcookie", "unb")


class LinkCreate(BaseModel):
    link_type: str = Field(..., description="item | seller")
    link_key: str = Field(..., min_length=1, max_length=512)
    display: dict[str, Any] | None = None
    source: str = "manual"
    note: str | None = Field(default=None, max_length=500)


def _missing_live_search_cookie_names(cookie_names: set[str]) -> list[str]:
    """Return identity cookies required by Xianyu search but absent in the browser context."""
    return [name for name in _LIVE_SEARCH_IDENTITY_COOKIES if name not in cookie_names]


async def _ensure_live_search_cookies(container: Container) -> None:
    """Fail fast when the running browser no longer has enough Xianyu login cookies."""
    if not container.browser:
        return
    try:
        cookies = await container.browser.get_cookies()
    except Exception as e:
        logger.warning("读取浏览器 Cookie 失败: {}", e)
        return

    names = {str(c.get("name") or "") for c in cookies}
    missing = _missing_live_search_cookie_names(names)
    if missing:
        raise HTTPException(
            status_code=401,
            detail=f"闲鱼登录 Cookie 不完整（缺少 {', '.join(missing)}），实时搜索不可用，请重新登录闲鱼",
        )


@router.get("/{task_id}/links")
def list_links(
    task_id: str,
    type: str | None = Query(None, description="item | seller | url"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    keyword: str | None = Query(None, description="标题关键词模糊匹配（仅 type=item 有效）"),
    region: str | None = Query(None, description="地区精确匹配（仅 type=item 有效）"),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """列出任务的关联内容（懒加载用：前端分页拉取）

    支持按 keyword/region 过滤：过滤已下推 SQL 层（json_extract + LIKE），
    避免 has_search 时全量加载到内存再 Python 过滤。
    """
    if type is not None and type not in _VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"未知 type: {type}")
    if not container.repo.get_task(task_id):
        raise HTTPException(status_code=404, detail="任务不存在")

    # 关键词/地区过滤仅对 item 类型生效（seller 行通常无 title/region 字段）
    has_search = bool(keyword or region) and (type is None or type == "item")
    search_keyword = keyword if has_search else None
    search_region = region if has_search else None

    # 过滤与分页均在 SQL 层完成，无需全量加载
    items, counts = container.repo.list_and_count_task_links(
        task_id=task_id, link_type=type, limit=limit, offset=offset,
        search_keyword=search_keyword, search_region=search_region,
    )
    total_for_type = counts.get(type, len(items)) if type else counts.get("total", len(items))

    # 统一字段名为 link_id（前端接口定义用 link_id，后端 DB 主键为 id）
    # 同步对每行 display 做字段语义校正：DB 中可能存了错位的 seller_nick/region/seller_credit，
    # 校正后传给前端，避免"卖家"列显示地区、"地区"列显示昵称等视觉错位
    result_items = []
    for r in _enrich_with_item_data(items, container):
        r["link_id"] = r.pop("id", 0)  # id → link_id 映射，确保前端 rowKey/delete 正常工作
        display = r.get("display")
        if isinstance(display, dict):
            corrected_display, _ = normalize_display_fields(display)
            r["display"] = corrected_display
        result_items.append(r)

    return {
        "items": result_items,
        "count": len(items),
        "total_for_type": total_for_type,
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
    # 批量查询 items 表（通过 Repository 方法，不直接访问 engine）
    try:
        rows = container.repo.list_items_by_ids(list(item_ids))
        # 构建 item_id -> 字段映射
        item_map: dict[str, dict] = {}
        for row in rows:
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
        logger.warning("从 items 表补全字段失败: {}", e)
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
        # 补全缺失或无效的字段（"None" 字符串/null/空字符串视为无效，用 items 表正确值覆盖）
        for k, v in extra.items():
            existing = display.get(k)
            if k not in display or existing is None or existing == "" or existing == "None":
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
    """解除关联

    联动清理：删除 item 类型关联时，同步删除 events 表中对应的 eval.* 评估事件，
    避免 task_links 已删但评估明细残留导致的垃圾数据。
    """
    # 删除前先查出关联信息，用于判断是否需要联动清理评估事件
    # 为什么不用 delete_task_link 直接删：它只返回 bool，拿不到 link_type/link_key
    from sqlalchemy import select as _select
    from xianyu_hunter.infra.db_models import TaskLinkRow

    with container.repo.engine.connect() as conn:
        row = conn.execute(
            _select(TaskLinkRow.link_type, TaskLinkRow.link_key)
            .where(TaskLinkRow.id == link_id)
            .where(TaskLinkRow.task_id == task_id)
        ).first()
        if not row:
            raise HTTPException(status_code=404, detail="关联不存在")
        # 必须在 with 块内提取值，连接关闭后 Row 对象可能失效
        link_type: str = row.link_type
        link_key: str = row.link_key
    ok = container.repo.delete_task_link(link_id)
    if not ok:
        raise HTTPException(status_code=404, detail="关联不存在")

    # 联动清理：item 类型关联删除时，同步删除该商品关联的评估数据
    # events 表存评估事件流（eval.*），evaluations 表存 AI 成色评估缓存
    # 两个表都需要清理，否则删除商品后评估明细仍会残留
    deleted_events = 0
    deleted_evaluations = 0
    if link_type == "item" and link_key:
        deleted_events = container.repo.delete_eval_events_by_task_item(task_id, str(link_key))
        deleted_evaluations = container.repo.delete_evaluation_by_item(str(link_key))
        if deleted_events or deleted_evaluations:
            logger.info("删除关联 link_id={} 联动清理: {} 条评估事件 + {} 条评估记录 (task={}, item={})",
                        link_id, deleted_events, deleted_evaluations, task_id, link_key)

    return {"ok": True, "id": link_id, "task_id": task_id, "deleted_events": deleted_events, "deleted_evaluations": deleted_evaluations}


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
    await _ensure_live_search_cookies(container)

    keyword = task.get("keyword", "")
    if not keyword:
        raise HTTPException(status_code=400, detail="任务无关键词")

    # 读取任务筛选标签，传递给搜索 URL（如个人闲置、包邮等）
    task_search_filters = task.get("search_filters") or []
    # 读取全局搜索配置的排序方式和地区过滤，与 Worker 保持一致
    try:
        from xianyu_hunter.infra.yaml_config import get_config
        _search_cfg = get_config().search
        _search_sort_type = _search_cfg.sort_type
        _search_regions = _search_cfg.regions
    except Exception:
        _search_sort_type = "default"
        _search_regions = ""

    # 清除该任务旧的 auto 来源关联（manual 来源保留）
    container.repo.delete_task_links_by_task(task_id, source="auto")

    # 使用互斥锁防止 Worker 和 refresh 端点并发操作浏览器
    # 不做 is_alive() 预检——直接尝试搜索，失败时返回明确错误
    items: list[dict] = []
    try:
        async with container.browser_lock:
            try:
                # skip_lock=True：外层已持有 browser_lock，search 内部不再获取，避免死锁
                items = await container.collector.search(
                    keyword, max_pages=2, skip_lock=True,
                    search_filters=task_search_filters,
                    sort_type=_search_sort_type, regions=_search_regions,
                )
            except Exception as e:
                logger.exception("refresh_links 搜索失败 task={}: {}", task_id, e)
                err_msg = str(e)
                if "TargetClosed" in err_msg or "Browser has been closed" in err_msg:
                    raise HTTPException(status_code=502, detail="浏览器连接已断开，请重启服务后重试")
                if "RGV587" in err_msg:
                    raise HTTPException(status_code=401, detail="搜索令牌临时过期，请稍后重试；若持续失败请重新登录闲鱼")
                if "Connection closed" in err_msg:
                    raise HTTPException(status_code=502, detail="浏览器连接异常，请重启服务后重试")
                raise HTTPException(status_code=502, detail=f"闲鱼搜索失败: {err_msg}")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("refresh_links 未预期异常 task={}: {}", task_id, e)
        raise HTTPException(status_code=502, detail=f"刷新搜索异常: {str(e)}")

    # 写入新关联
    # 批量写入：将 N 次独立事务合并为 1 次，减少 SQLite fsync 开销
    items_data = [
        {
            "item_id": item.id,
            "title": item.title,
            "price": item.price,
            "thumb_url": item.thumb_url,
            "seller_id": getattr(item, "seller_id", None) or "",
            "region": getattr(item, "region", None),
            "publish_time": getattr(item, "publish_time", None),
            "want_cnt": getattr(item, "want_cnt", None),
            "view_cnt": getattr(item, "view_cnt", None),
            "is_sold": getattr(item, "is_sold", False),
        }
        for item in items
    ]
    try:
        saved = container.repo.batch_upsert_item_task_links(
            task_id=task_id, items_data=items_data, source="auto"
        )
    except Exception as e:
        logger.warning("批量写入关联失败: {}", e)
        saved = 0

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
    background_tasks: BackgroundTasks,
    container: Container = Depends(get_container),
):
    """实时从闲鱼搜索并直接返回结果（SSE 流式响应）

    通过 SSE 推送搜索进度，前端可实时显示当前阶段。
    支持 60 秒结果缓存，避免短时间重复搜索。
    使用高优先级浏览器锁，优先于 Worker 后台搜索。
    同步 DB 调用通过 run_in_executor 异步化，避免阻塞事件循环。
    """
    # 前置检查（快速失败，返回正常 HTTP 错误码）
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
    task_search_filters = task.get("search_filters") or []
    try:
        from xianyu_hunter.infra.yaml_config import get_config
        search_cfg = get_config().search
        search_sort_type = search_cfg.sort_type
        search_regions = search_cfg.regions
    except Exception:
        search_sort_type = "default"
        search_regions = ""

    async def event_stream():
        """SSE 事件流：分阶段推送搜索进度和最终结果"""
        # 性能埋点：记录 live 搜索整体耗时，便于分析缓存命中率和搜索性能
        live_start = time.monotonic()
        def sse(data: dict) -> str:
            return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

        # 阶段 1：检查缓存
        yield sse({"stage": "checking_cache"})
        cached = _live_cache.get(task_id)
        if cached and (time.monotonic() - cached[0]) < _LIVE_CACHE_TTL:
            logger.info("live_links 命中缓存 task={}, 耗时 {:.3f}s", task_id, time.monotonic() - live_start)
            yield sse({"stage": "done", **cached[1]})
            return

        # 阶段 2：Cookie 检查
        yield sse({"stage": "checking_cookies"})
        try:
            await _ensure_live_search_cookies(container)
        except HTTPException as e:
            yield sse({"stage": "error", "detail": e.detail, "status": e.status_code})
            return
        except Exception as e:
            logger.exception("live_links cookie 检查异常 task={}: {}", task_id, e)
            yield sse({"stage": "error", "detail": f"Cookie 检查异常: {e}", "status": 502})
            return

        # 阶段 3：获取浏览器锁（高优先级，优先于 Worker 后台搜索）
        yield sse({"stage": "acquiring_lock"})
        try:
            await asyncio.wait_for(
                container.browser_lock.acquire(priority="high"),
                timeout=10.0,
            )
        except asyncio.TimeoutError:
            yield sse({"stage": "error", "detail": "系统正在执行后台搜索任务，请稍后重试", "status": 503})
            return

        # 阶段 4：搜索
        raw_results: list[dict] = []
        try:
            yield sse({"stage": "searching"})
            container.collector.last_session_invalid = False
            try:
                raw_results = await asyncio.wait_for(
                    container.collector.live_search(
                        keyword, max_pages=1, collect_sellers=False, fast=True,
                        search_filters=task_search_filters,
                        sort_type=search_sort_type, regions=search_regions,
                    ),
                    timeout=20.0,
                )
            except asyncio.TimeoutError:
                yield sse({"stage": "error", "detail": "实时搜索超时，请稍后重试或重启服务", "status": 504})
                return

            # RGV587 时 fast 模式跳过了 token 刷新重试，此处补一次
            if not raw_results and getattr(container.collector, "last_session_invalid", False):
                yield sse({"stage": "refreshing_token"})
                logger.info("实时搜索触发 RGV587，强制刷新 token 后重试: task={}", task_id)
                try:
                    refresh_page = await container.browser.new_page()
                    try:
                        await container.collector._ensure_fresh_m5tk(refresh_page, force=True)
                    finally:
                        await refresh_page.close()
                    yield sse({"stage": "searching_retry"})
                    raw_results = await asyncio.wait_for(
                        container.collector.live_search(
                            keyword, max_pages=1, collect_sellers=False, fast=False,
                            search_filters=task_search_filters,
                            sort_type=search_sort_type, regions=search_regions,
                        ),
                        timeout=45.0,
                    )
                except asyncio.TimeoutError:
                    yield sse({"stage": "error", "detail": "实时搜索重试超时，请稍后再试", "status": 504})
                    return
        except Exception as e:
            logger.exception("实时搜索失败 task={}: {}", task_id, e)
            err_msg = str(e)
            if "TargetClosed" in err_msg or "Browser has been closed" in err_msg:
                yield sse({"stage": "error", "detail": "浏览器连接已断开，请重启服务后重试", "status": 502})
            elif "RGV587" in err_msg:
                yield sse({"stage": "error", "detail": "搜索令牌临时过期，请稍后重试；若持续失败请重新登录闲鱼", "status": 401})
            elif "Connection closed" in err_msg:
                yield sse({"stage": "error", "detail": "浏览器连接异常，请重启服务后重试", "status": 502})
            else:
                yield sse({"stage": "error", "detail": f"闲鱼搜索失败: {err_msg}", "status": 502})
            return
        finally:
            container.browser_lock.release()

        # 阶段 5：格式化 + 过滤
        yield sse({"stage": "filtering", "count": len(raw_results)})
        now = datetime.now(timezone.utc).isoformat()
        results: list[dict] = []
        merged_field_map: dict[str, dict[str, Any]] = {}
        for r in raw_results:
            display = {
                "title": r.get("title", ""),
                "price": r.get("price"),
                "thumb_url": r.get("thumb_url", ""),
                "region": r.get("region", ""),
                "url": r.get("url", ""),
                "is_sold": r.get("is_sold", False),
                "publish_time": r.get("publish_time"),
                "seller_id": r.get("seller_id", ""),
                "seller_nick": r.get("seller_nick", ""),
                "seller_credit": r.get("seller_credit", ""),
                "want_cnt": r.get("want_cnt"),
                "view_cnt": r.get("view_cnt"),
            }
            corrected_display, field_map = normalize_display_fields(display)
            merged_field_map.update(field_map)
            results.append({
                "link_id": 0,
                "task_id": task_id,
                "link_type": r["link_type"],
                "link_key": r["link_key"],
                "source": "live",
                "display": corrected_display,
                "note": None,
                "created_at": now,
            })

        # 关键词过滤（安全兜底）
        filtered = []
        for r in results:
            title = (r.get("display") or {}).get("title", "")
            if task_keyword_matches_title(keyword, title):
                filtered.append(r)
        skipped = len(results) - len(filtered)
        if skipped:
            logger.info("live_links 关键词过滤跳过了 {} 条无关结果", skipped)

        # 价格过滤（任务级 + 全局 price_strategy）
        try:
            from xianyu_hunter.infra.yaml_config import get_config
            global_ps = get_config().price_strategy
        except Exception:
            global_ps = None
        effective_min = min_price
        effective_max = max_price
        if effective_min is None and global_ps and global_ps.enabled_min:
            effective_min = global_ps.min_price
        if effective_max is None and global_ps and global_ps.enabled_max:
            effective_max = global_ps.max_price
        if effective_min is not None or effective_max is not None:
            _filtered = []
            for r in filtered:
                price = (r.get("display") or {}).get("price")
                if price is None:
                    _filtered.append(r)
                    continue
                try:
                    p = float(price)
                except (ValueError, TypeError):
                    _filtered.append(r)
                    continue
                if effective_min is not None and p < effective_min:
                    continue
                if effective_max is not None and p > effective_max:
                    continue
                _filtered.append(r)
            filtered = _filtered

        # 发布天数过滤
        if max_publish_days is not None:
            from datetime import datetime as _dt
            _now = _dt.now()
            _filtered = []
            for r in filtered:
                pub = (r.get("display") or {}).get("publish_time")
                if not pub:
                    _filtered.append(r)
                    continue
                try:
                    pub_dt = _dt.fromisoformat(str(pub).replace("Z", "+00:00"))
                    if (_now - pub_dt).days > max_publish_days:
                        continue
                except (ValueError, TypeError):
                    pass
                _filtered.append(r)
            filtered = _filtered

        items = [r for r in filtered if r["link_type"] == "item"]
        sellers = [r for r in filtered if r["link_type"] == "seller"]

        # 阶段 6：批量写入 DB（run_in_executor 避免阻塞事件循环）
        if items:
            yield sse({"stage": "writing_db", "count": len(items)})
            items_data = [
                {
                    "item_id": r.get("link_key", ""),
                    "title": (r.get("display") or {}).get("title", ""),
                    "price": (r.get("display") or {}).get("price"),
                    "thumb_url": (r.get("display") or {}).get("thumb_url", ""),
                    "seller_id": (r.get("display") or {}).get("seller_id", "") or "",
                    "region": (r.get("display") or {}).get("region"),
                    "publish_time": (r.get("display") or {}).get("publish_time"),
                    "want_cnt": (r.get("display") or {}).get("want_cnt"),
                    "view_cnt": (r.get("display") or {}).get("view_cnt"),
                    "is_sold": (r.get("display") or {}).get("is_sold", False),
                }
                for r in items
            ]
            try:
                loop = asyncio.get_event_loop()
                saved_live = await loop.run_in_executor(
                    None,
                    functools.partial(
                        container.repo.batch_upsert_item_task_links,
                        task_id=task_id,
                        items_data=items_data,
                        source="live",
                    ),
                )
                if saved_live:
                    logger.info("live_links 已写入 {} 条记录到 DB (task={})", saved_live, task_id)
            except Exception as e:
                logger.warning("live_links 批量写入 DB 失败: {}", e)

            background_tasks.add_task(_safe_trigger_live_evaluation, container, task_id, items)

        # 阶段 7：完成
        session_expired = getattr(container.collector, "last_session_invalid", False)
        result = {
            "ok": True,
            "task_id": task_id,
            "keyword": keyword,
            "session_expired": session_expired,
            "counts": {
                "item": len(items),
                "seller": len(sellers),
                "total": len(filtered),
            },
            "items": items,
            "sellers": sellers,
            "all": filtered,
            "field_map": merged_field_map,
        }
        # 写入缓存：仅当查询结果非空时缓存，0 条记录不缓存以便下次请求重新触发实时查询
        if filtered:
            _live_cache[task_id] = (time.monotonic(), result)
        elapsed = time.monotonic() - live_start
        logger.info("live_links 完成 task={}, {} 个商品, 耗时 {:.1f}s", task_id, len(items), elapsed)
        yield sse({"stage": "done", **result})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _safe_trigger_live_evaluation(container: Container, task_id: str, items: list[dict]) -> None:
    """_trigger_live_evaluation 的安全包装，用于 BackgroundTasks

    BackgroundTasks 在响应返回后执行，异常不会反馈给客户端，需在此捕获并记录日志，
    避免未捕获异常导致任务静默失败。
    """
    try:
        _trigger_live_evaluation(container, task_id, items)
    except Exception as e:
        logger.warning("live_links 后台触发评估失败 task={}: {}", task_id, e)


def _trigger_live_evaluation(container: Container, task_id: str, items: list[dict]) -> None:
    """对 live 搜索结果触发轻量级评估

    基于搜索结果构造降级 ItemDetail 和 SellerProfile（不拉取详情页和卖家主页），
    调用 Evaluator.evaluate 生成评分，写入 events 表供评估明细页面展示。
    评估结果标记为"数据不足"，Worker 后续会拉取详情重新评估覆盖。
    """
    from xianyu_hunter.domain.item import ItemDetail, ItemSummary
    from xianyu_hunter.domain.seller import SellerProfile
    from xianyu_hunter.domain.evaluation import RiskLevel
    from xianyu_hunter.modules.evaluator import Evaluator

    # 构造 Evaluator（复用容器配置）
    # Evaluator 每次 evaluate 时从 get_config() 实时读取配置，无需传参
    evaluator = getattr(container, "evaluator", None) or Evaluator()

    evaluated = 0
    for r in items:
        display = r.get("display") or {}
        item_id = r.get("link_key", "")
        if not item_id:
            continue

        # 从搜索结果构造 ItemSummary → ItemDetail（降级，无详情页数据）
        try:
            price_val = display.get("price")
            price_float = float(price_val) if price_val is not None else 0.0
            summary = ItemSummary(
                id=str(item_id),
                title=display.get("title", ""),
                price=price_float,
                region=display.get("region", "") or "",
                seller_id=display.get("seller_id", "") or "",
                seller_nick=display.get("seller_nick", "") or "",
                thumb_url=display.get("thumb_url", "") or "",
                is_sold=display.get("is_sold", False),
                want_cnt=display.get("want_cnt") or 0,
                view_cnt=display.get("view_cnt") or 0,
            )
            detail = ItemDetail(
                **{k: getattr(summary, k) for k in summary.__dataclass_fields__},
                description="",
            )
        except Exception as e:
            logger.warning("构造 ItemDetail 失败 item={}: {}", item_id, e)
            continue

        # 构造降级 SellerProfile（无卖家主页数据，标记为数据不足）
        seller = SellerProfile(
            id=summary.seller_id or "unknown",
            nick=summary.seller_nick or "",
            credit_score=None,
            register_days=0,
            on_sale_count=0,
            sold_count=0,
        )

        # 评估
        try:
            eval_result = evaluator.evaluate(detail, seller)
            evaluated += 1

            # 写入 events 表（使用 upsert 按 task_id+item_id 去重，防止重复评估）
            import json as _json
            score_display = eval_result.score if eval_result.score is not None else "N/A"
            level = "info" if eval_result.is_passed else ("warn" if eval_result.risk_level != RiskLevel.EXTREME else "err")
            if eval_result.risk_level == RiskLevel.UNKNOWN:
                level = "warn"
            container.repo.upsert_eval_event({
                "type": "eval.scored",
                "task_id": task_id,
                "item_id": detail.id,
                "stage": "eval",
                "level": level,
                "message": f"商品 {detail.id} 评估分 {score_display} ({eval_result.risk_level.value}) [数据质量: {eval_result.data_quality}]",
                "payload": _json.dumps({
                    "item_id": detail.id,
                    "item_title": detail.title,
                    "item_price": detail.price,
                    "seller_id": detail.seller_id,
                    "seller_nick": detail.detail_seller_nick or summary.seller_nick or "",
                    "score": eval_result.score,
                    "risk_level": eval_result.risk_level.value,
                    "dimension_scores": eval_result.dimension_scores,
                    "reject_reasons": eval_result.reject_reasons,
                    "is_passed": eval_result.is_passed,
                    "data_quality": eval_result.data_quality,
                }, ensure_ascii=False, default=str),
            })
        except Exception as e:
            logger.warning("live 评估失败 item={}: {}", item_id, e)

    if evaluated:
        logger.info("live_links 触发轻量级评估 {} 条 (task={})", evaluated, task_id)


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
