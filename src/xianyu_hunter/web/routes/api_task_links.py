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

# live 抢单冷却：避免实时搜索频繁触发抢单冲击闲鱼下单接口
# 为什么需要：live 搜索可能每分钟触发多次，不加冷却会短时间内重复尝试下单
_live_last_buy_at: float = 0.0
_LIVE_BUY_COOLDOWN = 30.0

# 持有 task 引用避免被 GC 回收（Python 官方警告：未持有的 task 可能消失）
# done_callback 自动从集合移除已完成的 task，避免集合无限增长
_live_buy_tasks: set[asyncio.Task] = set()

# 实时搜索 in-flight 去重：task_id -> asyncio.Event
# 当搜索正在进行时，后续请求等待 Event 完成后复用缓存结果，避免并发竞争 browser_lock
# 为什么需要：前端轮询（15s）与用户点击可能同时发起 live 请求，第二个请求会因
# browser_lock 被持有而等待 10s 超时，返回"系统正在执行后台搜索任务"错误
_live_inflight: dict[str, asyncio.Event] = {}
# 等待 in-flight 搜索完成的超时时间：覆盖正常搜索（30s）+ 缓冲（5s）
_LIVE_INFLIGHT_WAIT_TIMEOUT = 35.0


def _clear_live_inflight(task_id: str, event: asyncio.Event) -> None:
    """清除 in-flight 标记并通知所有等待者

    在搜索的所有退出路径（成功/失败/异常）调用，确保后续请求不会卡在等待逻辑。
    为什么需要：in-flight Event 未 set 时，后续请求会等待 35s 超时，导致用户体验差。
    """
    _live_inflight.pop(task_id, None)
    event.set()

router = APIRouter(prefix="/api/tasks", tags=["task-links"])

# url 类型已废弃（项目决策只保留 item/seller），保留 item/seller 两个有效类型
_VALID_TYPES = {"item", "seller"}
_VALID_SOURCES = {"auto", "manual"}
_LIVE_SEARCH_IDENTITY_COOKIES = ("cookie2", "sgcookie", "unb")

# S1192: 提取重复的错误消息常量
_TASK_NOT_FOUND = "任务不存在"


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
    """检查浏览器是否持有有效的闲鱼登录 Cookie，无效时尝试从 JSON 补注入

    为什么需要 JSON 补注入：Worker 浏览器实例在登录前已启动，
    登录通过 LoginOrchestrator(CDP) 或 browser-login 子进程完成时，
    Cookie 写入了 JSON/SQLite 但未同步到 Worker 浏览器内存。
    此时通过 Playwright context.add_cookies() 直接注入到浏览器内存，
    避免用户重新登录后实时搜索仍报"Cookie 不完整"。

    _m_h5_tk 重置策略：仅在 Cookie 补注入成功或距上次刷新超过 5 分钟时重置。
    - 补注入时重置：身份 Cookie 变更后，旧 token 必然失效
    - 5 分钟阈值：覆盖 Worker 浏览器启动时的匿名 token 场景（启动后 5 分钟内
      首次实时搜索会触发刷新），同时避免短时间连续实时搜索反复刷新（每次约 4s）
    - _ensure_fresh_m5tk 内部还有 45 分钟缓存，未过期时直接返回 False
    """
    if not container.browser:
        return

    async def _get_cookie_by_name() -> dict[str, dict]:
        try:
            cookies = await container.browser.get_cookies()
        except Exception as e:
            logger.warning("读取浏览器 Cookie 失败: {}", e)
            return {}
        return {
            str(c.get("name") or ""): c
            for c in cookies
            if str(c.get("name") or "")
        }

    def _expired_identity_cookies(cookies_by_name: dict[str, dict]) -> list[str]:
        now = time.time()
        expired = []
        for name in _LIVE_SEARCH_IDENTITY_COOKIES:
            c = cookies_by_name.get(name)
            if not c:
                continue
            try:
                expires = float(c.get("expires", -1) or -1)
            except (TypeError, ValueError):
                expires = -1
            # session cookie（expires <= 0）不按过期处理
            if expires > 0 and expires < now:
                expired.append(name)
        return expired

    from xianyu_hunter.web.services.cookie_store import get_cookie_store, is_test_cookie

    def _cookies_from_json() -> tuple[list[dict], dict[str, str]]:
        store = get_cookie_store()
        store.invalidate_cache()
        json_data = store._read_json()
        if not json_data or not json_data.get("cookies"):
            return [], {}

        pw_cookies: list[dict] = []
        identity_values: dict[str, str] = {}
        for c in json_data["cookies"]:
            name = str(c.get("name") or "")
            value = str(c.get("value") or "")
            if not name or not value:
                continue
            # 深度防御：跳过测试数据，防止 JSON 被污染时测试值注入浏览器
            if is_test_cookie(name, value):
                logger.warning("实时搜索：跳过测试 Cookie {}={}，不注入浏览器", name, value)
                continue

            item = {
                "name": name,
                "value": value,
                "domain": c.get("domain") or ".goofish.com",
                "path": c.get("path") or "/",
            }
            try:
                expires = float(c.get("expires", -1) or -1)
            except (TypeError, ValueError):
                expires = -1
            if expires > 0:
                item["expires"] = expires
            pw_cookies.append(item)
            if name in _LIVE_SEARCH_IDENTITY_COOKIES:
                identity_values[name] = value
        return pw_cookies, identity_values

    async def _cookie_issues(json_identity_values: dict[str, str]) -> tuple[list[str], list[str], list[str]]:
        cookies_by_name = await _get_cookie_by_name()
        names = set(cookies_by_name)
        missing = _missing_live_search_cookie_names(names)
        expired = _expired_identity_cookies(cookies_by_name)
        stale = [
            name for name, value in json_identity_values.items()
            if name in cookies_by_name and cookies_by_name[name].get("value") != value
        ]
        return missing, expired, stale

    pw_cookies, json_identity_values = _cookies_from_json()
    missing, expired, stale = await _cookie_issues(json_identity_values)
    cookies_injected = False  # 标记是否进行了 Cookie 补注入
    if missing or expired or stale:
        # 浏览器缺少、过期或仍持有旧关键 Cookie 时，尝试从 CookieStore JSON 补/替换注入。
        if pw_cookies:
            logger.info(
                "实时搜索：准备从 CookieStore JSON 注入 cookie，missing={}, expired={}, stale={}",
                missing, expired, stale,
            )
            try:
                success = await container.browser.add_cookies(pw_cookies)
                if success:
                    cookies_injected = True
                    # 为什么记录具体名称：排查"补注入 2 个 cookie"时无法定位是哪两个
                    # cookie 的关键信息，便于日志审计与问题复现
                    logger.info(
                        "实时搜索：从 CookieStore JSON 补注入/替换 {} 个 cookie 到浏览器: {}",
                        len(pw_cookies), [c["name"] for c in pw_cookies],
                    )
                    # 同步 CookieRotator 层状态：补注入成功说明 JSON 持有有效 cookie，
                    # 若层状态从未初始化（updated_at==0.0），此处补救同步避免 /cookies/layers 误显示失效
                    try:
                        from xianyu_hunter.modules.login_orchestrator import sync_cookie_layers_from_json
                        sync_cookie_layers_from_json()
                    except Exception as e:
                        logger.debug("实时搜索补注入后同步层状态失败: {}", e)
                else:
                    logger.warning("实时搜索：从 CookieStore JSON 注入 cookie 后关键 Cookie 验证未通过")
            except Exception as e:
                logger.warning("实时搜索：从 JSON 补注入 cookie 失败: {}", e)

        # 重新检查补注入后是否仍缺少/过期/陈旧
        missing, expired, stale = await _cookie_issues(json_identity_values)
        if expired:
            logger.warning("实时搜索：关键 Cookie 已过期 {}，需重新登录闲鱼", expired)
            raise HTTPException(
                status_code=440,
                detail=f"闲鱼登录 Cookie 已过期（{', '.join(expired)}），实时搜索不可用，请重新登录闲鱼",
            )
        if stale:
            raise HTTPException(
                status_code=440,
                detail=f"闲鱼登录 Cookie 未刷新到实时搜索浏览器（{', '.join(stale)}），请重新登录闲鱼",
            )
        if missing:
            raise HTTPException(
                status_code=403,
                detail=f"闲鱼登录 Cookie 不完整（缺少 {', '.join(missing)}），实时搜索不可用，请重新登录闲鱼",
            )

    # 仅在以下情况重置 _m_h5_tk 刷新时间戳：
    # 1. 刚进行了 Cookie 补注入：身份 Cookie 变更后，旧 token 必然失效，需强制刷新
    # 2. 距上次刷新超过 5 分钟：避免短时间连续实时搜索反复刷新 token（每次刷新约 4s）
    # 不再无条件重置：原逻辑导致每次实时搜索都额外 4s 主页导航，60s 缓存命中也无效
    if container.collector:
        # 通过封装方法访问 _last_m5tk_refresh，避免破坏 collector 私有属性封装性
        # （历史问题：原代码直接读写 _last_m5tk_refresh 私有属性，collector 内部
        #  重命名会导致此处的重置逻辑静默失效）
        if cookies_injected or container.collector.should_reset_m5tk():
            container.collector.force_refresh_m5tk_next()
            reason = "Cookie 补注入" if cookies_injected else "距上次刷新超过 5 分钟"
            logger.info("已重置 _m_h5_tk 刷新时间戳（{}），下次搜索将强制刷新 token", reason)


def _normalize_task_link_rows(rows: list[dict]) -> tuple[list[dict], dict[str, dict[str, Any]]]:
    """Normalize display payloads and collect field metadata for frontend columns."""
    normalized: list[dict] = []
    merged_field_map: dict[str, dict[str, Any]] = {}
    for row in rows or []:
        item = dict(row)
        display = item.get("display")
        if isinstance(display, dict):
            corrected_display, field_map = normalize_display_fields(display)
            item["display"] = corrected_display
            merged_field_map.update(field_map)
        normalized.append(item)
    return normalized, merged_field_map


def _normalize_live_result(result: dict) -> dict:
    """Re-normalize live result payloads, including cached responses."""
    out = dict(result or {})
    rows = out.get("all")
    if not isinstance(rows, list):
        rows = []
        for key in ("items", "sellers"):
            value = out.get(key)
            if isinstance(value, list):
                rows.extend(value)
    normalized_rows, field_map = _normalize_task_link_rows(rows)
    if normalized_rows:
        out["all"] = normalized_rows
        out["items"] = [r for r in normalized_rows if r.get("link_type") == "item"]
        out["sellers"] = [r for r in normalized_rows if r.get("link_type") == "seller"]
        out["counts"] = {
            "item": len(out["items"]),
            "seller": len(out["sellers"]),
            "total": len(normalized_rows),
        }
    out["field_map"] = field_map or out.get("field_map") or {}
    return out


@router.get("/{task_id}/links")
def list_links(
    task_id: str,
    type: str | None = Query(None, description="item | seller | url"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    keyword: str | None = Query(None, description="标题关键词模糊匹配（仅 type=item 有效）"),
    region: str | None = Query(None, description="地区精确匹配（仅 type=item 有效）"),
    brand: str | None = Query(None, description="品牌精确匹配（仅 type=item 有效）"),
    sold_filter: str = Query("all", pattern="^(all|onsale|sold)$", description="销售状态过滤：all=全部 / onsale=在售 / sold=已售"),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """列出任务的关联内容（懒加载用：前端分页拉取）

    支持按 keyword/region/brand 过滤：过滤已下推 SQL 层（json_extract + LIKE/=），
    避免 has_search 时全量加载到内存再 Python 过滤。
    sold_filter 通过 JOIN items 表下推 SQL，仅 item 类型有效；seller 类型行不受影响。
    """
    # 性能埋点：记录端到端耗时（含 DB 查询 + 字段补全 + 序列化），用于长期监控
    _list_start = time.monotonic()

    if type is not None and type not in _VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"未知 type: {type}")
    if not container.repo.get_task(task_id):
        raise HTTPException(status_code=404, detail=_TASK_NOT_FOUND)

    # 关键词/地区/品牌过滤仅对 item 类型生效（seller 行通常无 title/region/brand 字段）
    has_search = bool(keyword or region or brand) and (type is None or type == "item")
    search_keyword = keyword if has_search else None
    search_region = region if has_search else None
    search_brand = brand if has_search else None

    # 过滤与分页均在 SQL 层完成，无需全量加载
    items, counts = container.repo.list_and_count_task_links(
        task_id=task_id, link_type=type, limit=limit, offset=offset,
        search_keyword=search_keyword, search_region=search_region,
        search_brand=search_brand, sold_filter=sold_filter,
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

    # 性能埋点：端到端耗时记录（>200ms 告警，覆盖 DB + enrich + 序列化全链路）
    _elapsed_ms = (time.monotonic() - _list_start) * 1000
    if _elapsed_ms > 200:
        logger.warning(
            "list_links 慢响应: task={}, type={}, limit={}, offset={}, items={}, elapsed={:.1f}ms",
            task_id, type, limit, offset, len(result_items), _elapsed_ms,
        )
    else:
        logger.debug(
            "list_links: task={}, type={}, items={}, elapsed={:.1f}ms",
            task_id, type, len(result_items), _elapsed_ms,
        )

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
    """从 items 表补充 task_links.display 中缺失的字段（region/seller_id/want_cnt/view_cnt/publish_time/is_sold）

    旧数据写入 task_links 时未包含这些字段，这里从 items 表实时补全，
    避免悬停摘要和地区筛选因旧数据缺字段而无法展示。
    is_sold 字段从 items 表补全：refresh_item 和 mark_sold 会将最新售出状态写入 items 表，
    补全到 display 确保前端展示与实际库存一致。
    """
    # 返回新列表引用以满足 S3516（不变返回值规则），内部 dict 仍为原对象引用以保留 in-place 修改
    if not links:
        return list(links)
    # 收集需要补全的 item_id（link_type=item 时 link_key 即为 item_id）
    item_ids: set[str] = set()
    for r in links:
        if r.get("link_type") == "item" and r.get("link_key"):
            item_ids.add(str(r["link_key"]))
    if not item_ids:
        return list(links)
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
                    # is_sold：items 表存 int(0/1)，转为 bool 给前端 truthy 判断
                    "is_sold": bool(row.get("is_sold")),
                }
    except Exception as e:
        logger.warning("从 items 表补全字段失败: {}", e)
        return list(links)
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
            # is_sold 总是以 items 表为准：items 表由 refresh_item/mark_sold 更新，
            # 比 task_links.display 中的旧值更准确，避免已售商品仍显示在售
            if k == "is_sold":
                display[k] = v
            elif k not in display or existing is None or existing == "" or existing == "None":
                display[k] = v
        r["display"] = display
    return list(links)


@router.get("/{task_id}/links/count")
def count_links(
    task_id: str,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """按类型返回关联计数（用于 Tab 角标）"""
    if not container.repo.get_task(task_id):
        raise HTTPException(status_code=404, detail=_TASK_NOT_FOUND)
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
        raise HTTPException(status_code=404, detail=_TASK_NOT_FOUND)
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
        raise HTTPException(status_code=404, detail=_TASK_NOT_FOUND)
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
                    raise HTTPException(status_code=403, detail="搜索令牌临时过期，请稍后重试；若持续失败请重新登录闲鱼")
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
            "brand": getattr(item, "brand", None) or "",
            "seller_id": getattr(item, "seller_id", None) or "",
            # 修复：之前漏写 seller_nick，导致 list_links 从 items 表回退到 seller_id 展示
            "seller_nick": getattr(item, "seller_nick", None) or "",
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
        raise HTTPException(status_code=404, detail=_TASK_NOT_FOUND)
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
    # 排除词：标题命中任一排除词则丢弃（如 "16G" 过滤掉 16G 内存条）
    # 为什么单独读取：原 live 端点漏接此字段，导致 16G 等无关商品被保留并展示给用户
    exclude_words = list(task.get("exclude_words") or [])
    # 任务级 search_filters 与全局 search.filter_tags 合并（与 Worker 行为对齐）
    # 为什么需要合并：官方链接使用 sourceType=0&yhb=1&postageType=1 筛选条件，
    # 若仅用任务级 filters 而任务又未配置，Live 搜索 URL 不会附加任何筛选参数，
    # 导致返回的商品池与官方链接不一致（如 600-680 元区间商品无法被搜到）
    task_search_filters = list(task.get("search_filters") or [])
    try:
        from xianyu_hunter.infra.yaml_config import get_config
        search_cfg = get_config().search
        search_sort_type = search_cfg.sort_type
        search_regions = search_cfg.regions
        # 合并全局 filter_tags，去重保序（任务级优先）
        global_filters = list(search_cfg.filter_tags or [])
        seen = set(task_search_filters)
        for f in global_filters:
            if f not in seen:
                task_search_filters.append(f)
                seen.add(f)
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
            yield sse({"stage": "done", **_normalize_live_result(cached[1])})
            return

        # 阶段 1.5：in-flight 去重
        # 如果该 task 的搜索正在进行，等待其完成后复用缓存结果
        # 避免并发请求竞争 browser_lock 导致"系统正在执行后台搜索任务"错误
        inflight_event = _live_inflight.get(task_id)
        if inflight_event is not None and not inflight_event.is_set():
            yield sse({"stage": "waiting_inflight"})
            logger.info("live_links 等待 in-flight 搜索完成 task={}", task_id)
            try:
                await asyncio.wait_for(inflight_event.wait(), timeout=_LIVE_INFLIGHT_WAIT_TIMEOUT)
            except asyncio.TimeoutError:
                # 等待超时：in-flight 搜索耗时过长，放弃等待让客户端重试
                yield sse({"stage": "error", "detail": "搜索耗时较长，请稍后重试", "status": 503})
                return
            # in-flight 搜索完成，检查缓存是否已写入
            cached = _live_cache.get(task_id)
            if cached and (time.monotonic() - cached[0]) < _LIVE_CACHE_TTL:
                logger.info("live_links 命中 in-flight 缓存 task={}, 耗时 {:.3f}s", task_id, time.monotonic() - live_start)
                yield sse({"stage": "done", **_normalize_live_result(cached[1])})
                return
            # in-flight 搜索完成但缓存未命中（搜索失败或 0 结果未缓存）：
            # 不再重复搜索，返回空结果避免再次竞争锁
            logger.warning("live_links in-flight 搜索未产生缓存结果 task={}", task_id)
            yield sse({"stage": "done", "items": [], "sellers": [], "all": [], "counts": {"item": 0, "seller": 0, "total": 0}, "field_map": {}, "filter_summary": {}})
            return

        # 创建 in-flight Event，标记搜索开始
        # 在所有退出路径调用 _clear_live_inflight 确保标记被清除，避免后续请求卡在等待逻辑
        inflight_event = asyncio.Event()
        _live_inflight[task_id] = inflight_event

        # 阶段 2：Cookie 检查
        yield sse({"stage": "checking_cookies"})
        try:
            await _ensure_live_search_cookies(container)
        except HTTPException as e:
            _clear_live_inflight(task_id, inflight_event)
            yield sse({"stage": "error", "detail": e.detail, "status": e.status_code})
            return
        except Exception as e:
            logger.exception("live_links cookie 检查异常 task={}: {}", task_id, e)
            _clear_live_inflight(task_id, inflight_event)
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
            _clear_live_inflight(task_id, inflight_event)
            yield sse({"stage": "error", "detail": "系统正在执行后台搜索任务，请稍后重试", "status": 503})
            return

        # 阶段 4：搜索
        raw_results: list[dict] = []
        try:
            yield sse({"stage": "searching"})
            container.collector.last_session_invalid = False
            try:
                # 整体超时 45s：max_pages=2 需翻页 2 次
                # goto(15s) + 首屏 API(8s) + 滚动(4s) + 第 2 屏 API(8s) + unroute(2s) ≈ 37s
                # 为什么 max_pages=2：max_pages=1 仅取首屏 26 条，会遗漏 600-680 价位段商品，
                # 官网用户可滚动加载多屏，本地至少取 2 屏以缩小数据差异
                raw_results = await asyncio.wait_for(
                    container.collector.live_search(
                        keyword, max_pages=2, collect_sellers=False, fast=True,
                        search_filters=task_search_filters,
                        sort_type=search_sort_type, regions=search_regions,
                    ),
                    timeout=45.0,
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
            logger.info(
                "live_links 搜索返回 raw_results={} task={} keyword={} filters={} sort={} regions={}",
                len(raw_results), task_id, keyword, task_search_filters, search_sort_type, search_regions,
            )
        except Exception as e:
            logger.exception("实时搜索失败 task={}: {}", task_id, e)
            err_msg = str(e)
            if "TargetClosed" in err_msg or "Browser has been closed" in err_msg:
                yield sse({"stage": "error", "detail": "浏览器连接已断开，请重启服务后重试", "status": 502})
            elif "RGV587" in err_msg:
                yield sse({"stage": "error", "detail": "搜索令牌临时过期，请稍后重试；若持续失败请重新登录闲鱼", "status": 403})
            elif "Connection closed" in err_msg:
                yield sse({"stage": "error", "detail": "浏览器连接异常，请重启服务后重试", "status": 502})
            else:
                yield sse({"stage": "error", "detail": f"闲鱼搜索失败: {err_msg}", "status": 502})
            return
        finally:
            container.browser_lock.release()
            # 搜索阶段结束：清除 in-flight 标记，通知等待者检查缓存
            # 此时搜索数据已获取，后续格式化/写入DB（阶段5-7）不涉及锁竞争
            _clear_live_inflight(task_id, inflight_event)

        # 阶段 5：格式化 + 过滤
        yield sse({"stage": "filtering", "count": len(raw_results)})
        now = datetime.now(timezone.utc).isoformat()
        results: list[dict] = []
        merged_field_map: dict[str, dict[str, Any]] = {}
        filter_summary: dict[str, Any] = {
            "raw": len(raw_results),
            "formatted": 0,
            "keyword_skipped": 0,
            "price_skipped": 0,
            "publish_days_skipped": 0,
            # 被过滤的商品列表（带过滤原因），供前端"显示被过滤结果"使用
            # 为什么限制 50 条：避免响应体积过大（59 条约 30KB），50 条足够用户判断是否需调整过滤条件
            "filtered_out": [],
        }
        for r in raw_results:
            display = {
                "title": r.get("title", ""),
                "price": r.get("price"),
                "thumb_url": r.get("thumb_url", ""),
                "brand": r.get("brand", ""),
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
        filter_summary["formatted"] = len(results)

        # 关键词过滤（安全兜底）
        filtered = []
        keyword_skipped_titles: list[str] = []
        _filtered_out = filter_summary["filtered_out"]
        for r in results:
            title = (r.get("display") or {}).get("title", "")
            if task_keyword_matches_title(keyword, title):
                filtered.append(r)
            else:
                keyword_skipped_titles.append(str(title)[:60])
                # 记录被过滤的商品（限制总量避免响应过大）
                if len(_filtered_out) < 50:
                    _filtered_out.append({
                        "link_type": r.get("link_type"),
                        "link_key": r.get("link_key"),
                        "display": r.get("display"),
                        "filter_reason": "keyword",
                        "filter_detail": f"标题不匹配关键词「{keyword}」",
                    })
        skipped = len(results) - len(filtered)
        filter_summary["keyword_skipped"] = skipped
        if skipped:
            logger.info("live_links 关键词过滤跳过了 {} 条无关结果，样例={}", skipped, keyword_skipped_titles[:5])

        # 排除词过滤：标题命中任一排除词则丢弃
        # 为什么放在关键词后、价格前：排除词是硬性条件，先剔除可减少后续价格过滤的计算量
        if exclude_words:
            _filtered = []
            exclude_skipped = 0
            exclude_skipped_titles: list[str] = []
            for r in filtered:
                title = str((r.get("display") or {}).get("title", ""))
                # 大小写不敏感匹配：避免 "16g" 与 "16G" 因大小写差异漏过
                title_lower = title.lower()
                hit_word = next(
                    (w for w in exclude_words if w and w.lower() in title_lower),
                    None,
                )
                if hit_word:
                    exclude_skipped += 1
                    exclude_skipped_titles.append(str(title)[:60])
                    if len(_filtered_out) < 50:
                        _filtered_out.append({
                            "link_type": r.get("link_type"),
                            "link_key": r.get("link_key"),
                            "display": r.get("display"),
                            "filter_reason": "exclude_words",
                            "filter_detail": f"标题命中排除词「{hit_word}」",
                        })
                else:
                    _filtered.append(r)
            filtered = _filtered
            filter_summary["exclude_words_skipped"] = exclude_skipped
            if exclude_skipped:
                logger.info(
                    "live_links 排除词过滤跳过了 {} 条 (words={})，样例={}",
                    exclude_skipped, exclude_words, exclude_skipped_titles[:5],
                )

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
            price_skipped = 0
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
                    price_skipped += 1
                    if len(_filtered_out) < 50:
                        _filtered_out.append({
                            "link_type": r.get("link_type"),
                            "link_key": r.get("link_key"),
                            "display": r.get("display"),
                            "filter_reason": "price",
                            "filter_detail": f"价格 {p} 低于下限 {effective_min}",
                        })
                    continue
                if effective_max is not None and p > effective_max:
                    price_skipped += 1
                    if len(_filtered_out) < 50:
                        _filtered_out.append({
                            "link_type": r.get("link_type"),
                            "link_key": r.get("link_key"),
                            "display": r.get("display"),
                            "filter_reason": "price",
                            "filter_detail": f"价格 {p} 超出上限 {effective_max}",
                        })
                    continue
                _filtered.append(r)
            filtered = _filtered
            filter_summary["price_skipped"] = price_skipped
            if price_skipped:
                logger.info(
                    "live_links 价格过滤跳过了 {} 条 (min={}, max={})",
                    price_skipped, effective_min, effective_max,
                )

        # 发布天数过滤
        if max_publish_days is not None:
            from datetime import datetime as _dt
            _now = _dt.now()
            _filtered = []
            publish_days_skipped = 0
            for r in filtered:
                pub = (r.get("display") or {}).get("publish_time")
                if not pub:
                    _filtered.append(r)
                    continue
                try:
                    pub_dt = _dt.fromisoformat(str(pub).replace("Z", "+00:00"))
                    if (_now - pub_dt).days > max_publish_days:
                        publish_days_skipped += 1
                        if len(_filtered_out) < 50:
                            _filtered_out.append({
                                "link_type": r.get("link_type"),
                                "link_key": r.get("link_key"),
                                "display": r.get("display"),
                                "filter_reason": "publish_days",
                                "filter_detail": f"发布 {(_now - pub_dt).days} 天，超过上限 {max_publish_days} 天",
                            })
                        continue
                except (ValueError, TypeError):
                    pass
                _filtered.append(r)
            filtered = _filtered
            filter_summary["publish_days_skipped"] = publish_days_skipped
            if publish_days_skipped:
                logger.info(
                    "live_links 发布时间过滤跳过了 {} 条 (max_publish_days={})",
                    publish_days_skipped, max_publish_days,
                )

        items = [r for r in filtered if r["link_type"] == "item"]
        sellers = [r for r in filtered if r["link_type"] == "seller"]
        filter_summary["final_total"] = len(filtered)
        filter_summary["final_items"] = len(items)
        filter_summary["final_sellers"] = len(sellers)
        logger.info("live_links 过滤汇总 task={}: {}", task_id, filter_summary)

        # 阶段 6：批量写入 DB（run_in_executor 避免阻塞事件循环）
        if items:
            yield sse({"stage": "writing_db", "count": len(items)})
            items_data = [
                {
                    "item_id": r.get("link_key", ""),
                    "title": (r.get("display") or {}).get("title", ""),
                    "price": (r.get("display") or {}).get("price"),
                    "thumb_url": (r.get("display") or {}).get("thumb_url", ""),
                    "brand": (r.get("display") or {}).get("brand", "") or "",
                    "seller_id": (r.get("display") or {}).get("seller_id", "") or "",
                    # 修复：之前漏写 seller_nick，导致 list_links 从 items 表回退到 seller_id 展示
                    "seller_nick": (r.get("display") or {}).get("seller_nick", "") or "",
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
            "filter_summary": filter_summary,
        }
        result = _normalize_live_result(result)
        # 写入缓存：仅当查询结果非空时缓存，0 条记录不缓存以便下次请求重新触发实时查询
        if filtered:
            _live_cache[task_id] = (time.monotonic(), result)
        elapsed = time.monotonic() - live_start
        logger.info("live_links 完成 task={}, {} 个商品, 耗时 {:.1f}s", task_id, len(items), elapsed)
        yield sse({"stage": "done", **result})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


async def _safe_trigger_live_evaluation(container: Container, task_id: str, items: list[dict]) -> None:
    """_trigger_live_evaluation 的安全包装，用于 BackgroundTasks

    BackgroundTasks 在响应返回后执行，异常不会反馈给客户端，需在此捕获并记录日志，
    避免未捕获异常导致任务静默失败。
    """
    try:
        await _trigger_live_evaluation(container, task_id, items)
    except Exception as e:
        logger.warning("live_links 后台触发评估失败 task={}: {}", task_id, e)


def _build_live_price_strategy(
    container: Container, task_id: str, items: list[dict],
) -> tuple[Any, Any | None]:
    """构造 live 链路的价格策略与市场上下文

    与 worker.run_once / startup.py 中价格策略构造逻辑保持一致：
    1. 任务级 min_price/max_price（最高优先级）
    2. 任务级 price_config dict（仅当上面为 None 时生效）
    3. 全局 AppConfig.price_strategy（market_ratio 默认 0.8，top_n 默认 None）

    返回 (price_strategy, market_ctx)：
    - price_strategy 始终非 None（与 worker 一致，即使所有规则都为 None 也会构造）
      PriceStrategy.check 在所有规则都为 None 时返回 pass_=True，不会误过滤
    - market_ctx 从当前批次 items 实时算 median（与 worker._compute_market_context 一致），
      样本数 < 3 时返回 None，market_ratio 规则自动跳过

    为什么独立函数：startup.py 中价格策略是任务注册时一次性构造并注入 worker，
    而 live 链路是请求时按 task_id 现取任务字段，无法复用 startup 的注入路径
    """
    from xianyu_hunter.modules.price_strategy import (
        MarketContext, PriceConfig, PriceStrategy,
    )
    from xianyu_hunter.infra.yaml_config import get_config

    task = container.repo.get_task(task_id) or {}

    # 合并优先级与 startup.py:233-253 完全一致
    effective_min = task.get("min_price")
    effective_max = task.get("max_price")

    task_price_override = task.get("price_config") or {}
    if isinstance(task_price_override, str):
        try:
            import json as _json
            task_price_override = _json.loads(task_price_override)
        except Exception:
            task_price_override = {}

    if task_price_override:
        if effective_min is None and "min_price" in task_price_override:
            effective_min = task_price_override["min_price"]
        if effective_max is None and "max_price" in task_price_override:
            effective_max = task_price_override["max_price"]

    # market_ratio：任务级 price_config 优先，否则回退全局
    global_price_cfg = get_config().price_strategy
    if task_price_override and "market_ratio" in task_price_override:
        market_ratio = task_price_override["market_ratio"]
    else:
        market_ratio = global_price_cfg.market_ratio

    strategy = PriceStrategy(PriceConfig(
        min_price=effective_min,
        max_price=effective_max,
        market_ratio=market_ratio,
        top_n=global_price_cfg.top_n,
    ))

    # market_ctx：从当前批次 items 算 median（与 worker._compute_market_context 一致）
    prices: list[float] = []
    for r in items:
        p = (r.get("display") or {}).get("price")
        if p is None:
            continue
        try:
            prices.append(float(p))
        except (TypeError, ValueError):
            continue
    market_ctx = None
    if len(prices) >= 3:
        prices.sort()
        n = len(prices)
        median = prices[n // 2] if n % 2 == 1 else (prices[n // 2 - 1] + prices[n // 2]) / 2
        market_ctx = MarketContext(
            median_price=median, sample_size=n, all_prices=prices,
        )

    return strategy, market_ctx


async def _trigger_live_evaluation(container: Container, task_id: str, items: list[dict]) -> None:
    """对 live 搜索结果触发轻量级评估

    基于搜索结果构造降级 ItemDetail 和 SellerProfile（不拉取详情页和卖家主页），
    调用 Evaluator.evaluate 生成评分，写入 events 表供评估明细页面展示。
    评估结果标记为"数据不足"，Worker 后续会拉取详情重新评估覆盖。

    架构优化：评估达标的商品会异步触发抢单（_trigger_live_auto_buy），
    让实时搜索发现的达标商品不必等待 worker 下一轮调度即可抢单。

    价格过滤：评估达标的商品在加入抢单候选名单前，会按任务级价格策略
    (min_price/max_price/market_ratio) 过滤，与 worker.run_once 行为一致。
    过滤仅阻止加入候选名单，评估事件仍照写，让前端评估明细页面可见全部商品。
    """
    from xianyu_hunter.domain.item import ItemDetail, ItemSummary
    from xianyu_hunter.domain.seller import SellerProfile
    from xianyu_hunter.domain.evaluation import RiskLevel
    from xianyu_hunter.modules.evaluator import Evaluator

    # 构造 Evaluator（复用容器配置）
    # Evaluator 每次 evaluate 时从 get_config() 实时读取配置，无需传参
    evaluator = getattr(container, "evaluator", None) or Evaluator()

    # 从配置实时读取抢单门槛（与 worker.run_once 使用同一份配置）
    from xianyu_hunter.infra.yaml_config import get_config
    auto_buy_score = get_config().eval.auto_buy_score

    # 构造任务级价格策略（与 worker.run_once / startup.py 保持一致）
    # 为什么 live 链路也需要价格过滤：上一次架构优化加入 _trigger_live_auto_buy 时
    # 只对齐了"分数达标"判断，遗漏了"价格过滤"，导致任务设了 max_price=5000 但
    # 商品价格 8000 且评分 85 时，live 链路会误抢单，与 worker 行为不一致
    price_strategy, market_ctx = _build_live_price_strategy(container, task_id, items)

    evaluated = 0
    price_filtered = 0
    auto_buy_candidates: list[dict] = []
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
                brand=display.get("brand", "") or "",
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
            if eval_result.is_passed:
                level = "info"
            elif eval_result.risk_level != RiskLevel.EXTREME:
                level = "warn"
            else:
                level = "err"
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

            # 达标商品收集：score >= auto_buy_score 且 risk == LOW
            # 为什么用 should_auto_buy 而非 is_auto_buy：前者接受配置阈值参数，
            # 与 worker.run_once 使用同一份 auto_buy_score，保证一致性
            if eval_result.should_auto_buy(auto_buy_score):
                # 价格过滤：与 worker.run_once 行为一致，避免任务设置了价格区间
                # 但 live 链路只看分数导致误抢单
                # 注意：过滤仅阻止"加入候选名单"，评估事件仍照写，
                # 让评估明细页面能看到全部商品供用户决策
                if price_strategy is not None:
                    verdict = price_strategy.check(detail, market_ctx)
                    if not verdict.pass_:
                        price_filtered += 1
                        logger.info(
                            "live_links 商品 {} 价格未通过策略({})，跳过加入抢单候选",
                            detail.id, ", ".join(verdict.reasons),
                        )
                        continue
                auto_buy_candidates.append({
                    "item_id": detail.id,
                    "title": detail.title,
                    "price": detail.price,
                    "score": eval_result.score,
                    "risk_level": eval_result.risk_level.value,
                })
        except Exception as e:
            logger.warning("live 评估失败 item={}: {}", item_id, e)

    if evaluated:
        logger.info(
            "live_links 触发轻量级评估 {} 条 (task={}, 价格过滤 {} 条)",
            evaluated, task_id, price_filtered,
        )

    # 评估达标的商品异步触发抢单（不阻塞 BackgroundTasks）
    # 为什么用 create_task 而非 await：抢单耗时 30-90s，串行 await 会阻塞后续 BackgroundTasks
    if auto_buy_candidates:
        logger.info(
            "live_links 发现 {} 个达标商品，触发异步抢单 (task={})",
            len(auto_buy_candidates), task_id,
        )
        for candidate in auto_buy_candidates:
            task = asyncio.create_task(_trigger_live_auto_buy(container, task_id, candidate))
            _live_buy_tasks.add(task)
            task.add_done_callback(_live_buy_tasks.discard)


async def _trigger_live_auto_buy(container: Container, task_id: str, candidate: dict) -> None:
    """对 live 评估达标的商品异步触发抢单

    与 worker.run_once() 的抢单逻辑独立，让实时搜索发现的达标商品也能被抢单，
    而不必等待 worker 下一轮调度。

    安全保障：
    1. 任务模式检查：只有 AUTO 模式才抢单（与 worker._should_buy 一致）
    2. buyer 注入检查：with_browser=False 时优雅跳过
    3. 冷却检查（锁内）：避免频繁冲击闲鱼下单接口
    4. browser_lock：避免与 worker/live 端点并发操作浏览器导致 TargetClosedError
    5. buyer.buy 内部有幂等检查（内存 + DB），无需在此重复
    """
    from xianyu_hunter.domain.order import BuyOutcome

    global _live_last_buy_at

    item_id = candidate.get("item_id", "")
    score = candidate.get("score", "?")

    # 1. 任务模式检查：只有 AUTO 模式才抢单
    task = container.repo.get_task(task_id)
    if not task or task.get("mode") != "auto":
        logger.info(
            "[LiveAutoBuy] 任务 {} 模式非 auto({})，跳过 live 抢单 {}",
            task_id, task.get("mode") if task else "None", item_id,
        )
        return

    # 2. buyer 注入检查
    buyer = container.buyer
    if buyer is None:
        logger.warning(
            "[LiveAutoBuy] buyer 未注入（with_browser=False），跳过 live 抢单 {}", item_id
        )
        return

    # 3. 获取 browser_lock 并执行抢单
    # 为什么用 priority="low"：live 抢单是后台任务，不应抢占 live 端点（前端实时搜索）的锁
    # 为什么用 acquired 标志 + 单一 finally：acquire 成功后若被 CancelledError 打断，
    # 内层 try/finally 的窗口期内 lock 不会释放，导致后续浏览器操作全部阻塞
    acquired = False
    try:
        await container.browser_lock.acquire(priority="low")
        acquired = True
        # 冷却检查在锁内：避免多个协程同时通过检查后串行 buy() 导致冷却失效
        # 场景：一次搜索发现 3 个达标商品，3 个协程并行触发，若检查在锁外会全部通过
        now = time.monotonic()
        if now - _live_last_buy_at < _LIVE_BUY_COOLDOWN:
            remaining = int(_LIVE_BUY_COOLDOWN - (now - _live_last_buy_at))
            logger.info(
                "[LiveAutoBuy] 冷却中（剩余 {}s），跳过 live 抢单 {}", remaining, item_id
            )
            return

        _live_last_buy_at = time.monotonic()
        logger.info(
            "[LiveAutoBuy] 触发 live 抢单 task={} item={} score={} price={}",
            task_id, item_id, score, candidate.get("price"),
        )
        buy_result = await buyer.buy(
            task_id=task_id,
            item_id=item_id,
            expected_price=candidate.get("price"),
        )
        if buy_result.outcome == BuyOutcome.SUCCESS:
            logger.info(
                "[LiveAutoBuy] 抢单成功 task={} item={}", task_id, item_id
            )
        else:
            logger.warning(
                "[LiveAutoBuy] 抢单未成功 task={} item={} outcome={} error={}",
                task_id, item_id, buy_result.outcome.value,
                getattr(buy_result, "error", None),
            )
    except Exception as e:
        logger.exception(
            "[LiveAutoBuy] live 抢单异常 task={} item={}: {}", task_id, item_id, e
        )
    finally:
        if acquired:
            container.browser_lock.release()


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
