"""任务 API - 增删改查、启停控制"""
from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger
from pydantic import BaseModel, Field

from xianyu_hunter.domain.task import TaskMode
from xianyu_hunter.container import Container
from xianyu_hunter.infra.yaml_config import get_config
from xianyu_hunter.modules.scheduler import ResumeBlockedError
from xianyu_hunter.web.deps import get_container

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

# S1192: 提取重复的错误消息常量
_TASK_NOT_FOUND = "任务不存在"
_FORBIDDEN_TASK = "无权访问此任务"


def _check_task_ownership(
    container: Container, task_id: str, request: Request
) -> dict[str, Any]:
    """校验任务归属权，不属于当前用户则 403

    为什么用 403 而非 404：泄露 task_id 存在性本身是信息泄露，
    但 404 会让前端难以区分"任务不存在"与"无权访问"，这里选 403 明确语义。
    日志记录越权尝试便于审计（仅记录 user_id 与 task_id，不含敏感字段）。
    """
    t = container.repo.get_task(task_id)
    if not t:
        raise HTTPException(status_code=404, detail=_TASK_NOT_FOUND)
    user_id = getattr(request.state, "user_id", "default")
    if t.get("user_id") != user_id:
        logger.warning(
            "越权访问任务拒绝：user={} task={} owner={}",
            user_id, task_id, t.get("user_id"),
        )
        raise HTTPException(status_code=403, detail=_FORBIDDEN_TASK)
    return t


class TaskCreate(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=80)
    name: str = ""
    min_price: float | None = None
    max_price: float | None = None
    # 仅展示最近 N 天内发布的商品（None 表示不过滤）
    max_publish_days: int | None = None
    mode: str = "notify"
    region: str | None = None
    exclude_words: list[str] = []
    # 闲鱼筛选标签（与 goofish.com 搜索页复选框一致）
    # 可选值：personal_idle, verified, account_guarantee, free_shipping,
    #         super_shop, brand_new, strict_select, resale
    search_filters: list[str] = []
    # 调度配置：修复前端 cron 配置断层（之前字段被 Pydantic 静默丢弃）
    cron: str = "*/5 * * * *"
    use_cron: bool = False
    # interval_seconds: None 表示沿用全局 task_scheduler.default_interval_seconds
    # 为什么改为 None：让全局配置可热更新生效，无需重启服务即可调整新建任务默认采集周期
    # 为什么用 int 而非 float：DB schema 中 interval_seconds 是 INTEGER，float 会被 SQLite 截断且
    # 前端 Task.interval_seconds: number 无法区分 60 与 60.0，统一为 int 保持类型一致
    interval_seconds: int | None = Field(None, ge=30, le=3600)
    # AI 评估任务级配置：激活已有 DB 字段
    # eval_threshold: 任务级 pass_score 覆盖（None 表示沿用全局 eval.pass_score）
    eval_threshold: int | None = Field(None, ge=0, le=100)
    # ai_prompt: 任务级 AI 评估提示词（None 表示不使用自定义提示词）
    ai_prompt: str | None = None
    # 权威源字段：通知触发开关，启用后仅对价格≤捡漏价(P10)的商品触发通知
    # 默认 False 保持向后兼容；mode=notify 时仍生效（仅通知模式本身就只通知）
    notify_bargain_only: bool = Field(False, description="权威源：仅对价格≤捡漏价的商品触发通知")
    # 权威源字段：自动下单触发开关，启用后仅对价格≤捡漏价(P10)的商品执行自动下单
    # mode=notify 时无意义（仅通知模式不下单）；mode=auto/semi_auto/confirm 时生效
    auto_buy_bargain_only: bool = Field(False, description="权威源：仅对价格≤捡漏价的商品执行自动下单")
    # 任务级配置覆盖（JSON dict）：为空表示沿用全局配置
    # 为什么用 dict 而非结构化模型：任务级覆盖字段稀疏，dict 灵活且与前端表单直通；
    # 合并逻辑在 startup.py 中实现（任务级覆盖全局）
    search_config: dict[str, Any] | None = None
    price_config: dict[str, Any] | None = None
    antidetect_config: dict[str, Any] | None = None
    # eval_config: 任务级覆盖 AppConfig.eval（如 auto_collect_official/auto_collect_max_per_run）
    # 与 search_config 等保持一致的 dict 存储模式，None 表示沿用全局
    eval_config: dict[str, Any] | None = None


class TaskUpdate(BaseModel):
    name: str | None = None
    keyword: str | None = None
    min_price: float | None = None
    max_price: float | None = None
    max_publish_days: int | None = None
    mode: str | None = None
    status: str | None = None
    region: str | None = None
    # 与 TaskCreate 对齐：允许编辑闲鱼筛选标签和排除词（JSON 序列化存入 DB）
    search_filters: list[str] | None = None
    exclude_words: list[str] | None = None
    # 调度配置：允许编辑 cron / use_cron / interval_seconds
    cron: str | None = None
    use_cron: bool | None = None
    interval_seconds: int | None = Field(None, ge=30, le=3600)
    # AI 评估任务级配置（与 TaskCreate 对齐）
    eval_threshold: int | None = Field(None, ge=0, le=100)
    ai_prompt: str | None = None
    # 权威源字段：与 TaskCreate 对齐，PATCH 三态语义（未传=不更新，传 bool=更新）
    notify_bargain_only: bool | None = Field(None, description="权威源：仅对价格≤捡漏价的商品触发通知")
    auto_buy_bargain_only: bool | None = Field(None, description="权威源：仅对价格≤捡漏价的商品执行自动下单")
    # 任务级配置覆盖：传 None 清除覆盖，传 dict 设置覆盖
    search_config: dict[str, Any] | None = None
    price_config: dict[str, Any] | None = None
    # antidetect_config: 字段保留以兼容旧数据，但前端 UI 已移除任务级反检测覆盖（F4 修复）
    # AntiDetect 是 container 级共享单例，任务级覆盖架构上不可行；前端始终传 null
    antidetect_config: dict[str, Any] | None = None
    eval_config: dict[str, Any] | None = None


@router.get("")
def list_tasks(
    request: Request,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """列出任务；支持 status 过滤 + limit/offset 分页。

    - 默认 limit=50：百级任务列表一次性够用，避免前端渲染 1k+ 节点
    - 客户端渲染器会自己再细分页（前端 pageSize=20）
    - 同时返回 total 字段，前端用来算总页数
    - 多用户隔离：按 request.state.user_id 过滤当前账号任务
    """
    # 防滥用：限制 limit 上限，避免一次性拉 1w 行拖垮 sqlite
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    # repo 层已默认排除 deleted 任务，统一由 SQL 层过滤以保证 limit/offset 准确性
    effective_status = status
    # 与 _check_task_ownership 保持一致：用 "default" 兜底，避免 user_id=None 时
    # list_tasks_with_last_seen / count_tasks 不附加 WHERE user_id 过滤导致跨用户泄露
    user_id = getattr(request.state, "user_id", "default")
    rows = container.repo.list_tasks_with_last_seen(
        status=effective_status, limit=limit, offset=offset, user_id=user_id,
    )
    total = container.repo.count_tasks(status=effective_status, user_id=user_id)
    return {
        "items": rows,
        "count": len(rows),
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("")
def create_task(
    body: TaskCreate,
    request: Request,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    if body.min_price is not None and body.max_price is not None and body.min_price > body.max_price:
        raise HTTPException(status_code=400, detail="min_price 不能大于 max_price")
    try:
        mode = TaskMode(body.mode)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"未知 mode: {body.mode}")
    # interval_seconds None 时从全局配置兜底
    # 为什么不从 Pydantic 默认值取：让全局配置可热更新生效，无需重启
    interval_seconds = body.interval_seconds if body.interval_seconds is not None else get_config().task_scheduler.default_interval_seconds
    tid = f"t{uuid.uuid4().hex[:8]}"
    user_id = getattr(request.state, "user_id", "default")
    task = {
        "id": tid,
        "name": body.name or body.keyword,
        "keyword": body.keyword,
        "min_price": body.min_price,
        "max_price": body.max_price,
        "max_publish_days": body.max_publish_days,
        "mode": mode.value,
        "region": body.region,
        "exclude_words": json.dumps(body.exclude_words, ensure_ascii=False),
        "search_filters": json.dumps(body.search_filters, ensure_ascii=False),
        # 持久化调度配置，scheduler 启动时从 DB 读取并注入 TaskConfig
        "cron": body.cron,
        "use_cron": 1 if body.use_cron else 0,
        "interval_seconds": interval_seconds,
        # AI 评估任务级配置：序列化存 DB（None 表示沿用全局）
        "eval_threshold": body.eval_threshold,
        "ai_prompt": body.ai_prompt,
        # 捡漏价格触发开关：bool→int 存储（与 use_cron 一致）
        "notify_bargain_only": 1 if body.notify_bargain_only else 0,
        "auto_buy_bargain_only": 1 if body.auto_buy_bargain_only else 0,
        # 任务级配置覆盖：JSON 序列化存 DB（None 或空 dict 表示沿用全局）
        "search_config": json.dumps(body.search_config, ensure_ascii=False) if body.search_config else None,
        "price_config": json.dumps(body.price_config, ensure_ascii=False) if body.price_config else None,
        "antidetect_config": json.dumps(body.antidetect_config, ensure_ascii=False) if body.antidetect_config else None,
        "eval_config": json.dumps(body.eval_config, ensure_ascii=False) if body.eval_config else None,
        # 多用户隔离：任务归属当前登录账号
        "user_id": user_id,
    }
    container.repo.upsert_task(task)
    return {"ok": True, "id": tid, "task": task}


@router.get("/{task_id}")
def get_task(
    task_id: str,
    request: Request,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    # 多用户隔离：校验任务归属权，不属于当前用户返回 403
    t = _check_task_ownership(container, task_id, request)
    # 任务级配置覆盖字段：JSON 字符串解析为 dict，便于前端直接消费
    # 为什么在后端解析：避免前端重复实现 JSON 解析逻辑，且与 exclude_words/search_filters 的字符串返回保持兼容
    for cfg_field in ("search_config", "price_config", "antidetect_config", "eval_config"):
        raw = t.get(cfg_field)
        if isinstance(raw, str) and raw.strip():
            try:
                t[cfg_field] = json.loads(raw)
            except json.JSONDecodeError:
                t[cfg_field] = None
        elif raw is None:
            t[cfg_field] = None
    return t


def _normalize_task_updates(raw: dict[str, Any]) -> dict[str, Any]:
    """规范化 TaskUpdate 字段，集中处理 mode/JSON/None/bool 转换

    拆出主流程避免十几个独立 if 拉高 update_task 认知复杂度。
    顺序与原实现一致：mode → JSON 列表字段 → NOT NULL 字段 None 剔除 → bool→int → 配置覆盖。
    """
    updates: dict[str, Any] = dict(raw)
    _apply_mode_update(updates)
    _serialize_json_list_fields(updates)
    _drop_null_nullable_core_fields(updates)
    _convert_bool_fields_to_int(updates)
    _serialize_config_overrides(updates)
    return updates


def _apply_mode_update(updates: dict[str, Any]) -> None:
    """mode 字段校验为 TaskMode 枚举，无效值返回 400"""
    if "mode" not in updates:
        return
    try:
        updates["mode"] = TaskMode(updates["mode"]).value
    except ValueError:
        raise HTTPException(status_code=400, detail=f"未知 mode: {updates['mode']}")


def _serialize_json_list_fields(updates: dict[str, Any]) -> None:
    """search_filters / exclude_words 需 JSON 序列化后存入 DB（与 create_task 保持一致）"""
    for field in ("search_filters", "exclude_words"):
        if field in updates:
            updates[field] = json.dumps(updates[field], ensure_ascii=False)


def _drop_null_nullable_core_fields(updates: dict[str, Any]) -> None:
    """use_cron / interval_seconds 在 DB 中 NOT NULL，传 null 视为"不更新"

    为什么不像 search_config 那样允许 null：这两个是核心调度字段，不是覆盖字段。
    """
    for field in ("use_cron", "interval_seconds"):
        if updates.get(field) is None:
            updates.pop(field, None)


def _convert_bool_fields_to_int(updates: dict[str, Any]) -> None:
    """bool 字段转 INTEGER 存储（DB schema 与 use_cron 一致用 0/1）

    覆盖字段：use_cron / notify_bargain_only / auto_buy_bargain_only
    为什么统一处理：3 个字段都是 bool→int 转换，提取避免重复 if
    """
    for field in ("use_cron", "notify_bargain_only", "auto_buy_bargain_only"):
        if field in updates and updates[field] is not None:
            updates[field] = 1 if updates[field] else 0


_CONFIG_OVERRIDE_FIELDS = ("search_config", "price_config", "antidetect_config", "eval_config")


def _serialize_config_overrides(updates: dict[str, Any]) -> None:
    """任务级配置覆盖：JSON 序列化存 DB，空值保留 None（运行时视为无覆盖）"""
    for field in _CONFIG_OVERRIDE_FIELDS:
        if field in updates:
            val = updates[field]
            updates[field] = json.dumps(val, ensure_ascii=False) if val else None


@router.patch("/{task_id}")
def update_task(
    task_id: str,
    body: TaskUpdate,
    request: Request,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    # 多用户隔离：校验任务归属权
    t = _check_task_ownership(container, task_id, request)
    # 使用 exclude_unset=True 区分"未传"和"传 null"：
    # - 未传的字段被排除（跳过更新）
    # - 传 null 的字段被包含（清除覆盖/设为 NULL）
    # 这解决了前端"清除覆盖"时 null 被跳过导致旧值保留的 bug
    updates = _normalize_task_updates(body.model_dump(exclude_unset=True))
    t.update(updates)
    container.repo.upsert_task(t)
    return {"ok": True, "task": t}


@router.delete("/{task_id}")
def delete_task(
    task_id: str,
    request: Request,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """删除任务及所有关联数据（task_links、items、events、orders、deps）

    不再使用软删除，直接物理删除避免垃圾数据积累。
    多用户隔离：仅允许删除当前账号拥有的任务。
    """
    # 多用户隔离：校验任务归属权
    _check_task_ownership(container, task_id, request)
    user_id = getattr(request.state, "user_id", "default")

    # 级联删除所有关联数据
    cascade = container.repo.delete_task_cascade(task_id)

    # 最后删除任务本身（传入 user_id 兜底）
    container.repo.update_task_status(task_id, "deleted", user_id=user_id)

    # 清理 scheduler 内存中该任务的冷却期记录，避免长期运行后字典无限增长
    # 为什么用 try/except：scheduler 实例可能未注册该任务（Web only 模式），忽略 KeyError
    try:
        container.scheduler.drop_task_state(task_id)
    except Exception as e:  # noqa: BLE001
        logger.debug("清理 scheduler 任务状态失败（忽略）: {}", e)

    return {
        "ok": True,
        "id": task_id,
        "cascade": cascade,
    }


@router.get("/{task_id}/runs")
def get_task_runs(
    task_id: str,
    request: Request,
    range_hours: int = 24,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """F-09 任务运行历史：按时间窗聚合 events 表中的运行记录

    返回格式：
    {
        "task_id": "t1234",
        "runs": [
            {
                "start": "2026-06-08T10:00:00",
                "end": "2026-06-08T10:05:00",
                "event_count": 12,
                "hit_count": 3,
                "err_count": 0,
                "warn_count": 1,
                "duration_s": 12.5,
                "first_event_type": "search"
            }
        ],
        "idle_gaps": [
            {"from": "...", "to": "...", "duration_s": 2700}
        ],
        "total_runs": 5,
        "total_events": 60,
        "total_hits": 15
    }

    参数约束：
    - range_hours: 1~720（1 小时到 30 天），超出返回 422
    """
    # 参数校验
    if range_hours < 1 or range_hours > 720:
        raise HTTPException(status_code=422, detail="range_hours 须在 1~720 之间")
    # 多用户隔离：校验任务归属权
    _check_task_ownership(container, task_id, request)
    return container.repo.get_task_runs(task_id, range_hours=range_hours)


def _handle_scheduler_resume(container: Container, task_id: str, user_id: str) -> str:
    """resume 分支：scheduler.resume 失败时回滚 DB 到 paused 并抛 400

    P0-1/P0-2：Cookie 失效或冷却期内拒绝恢复，前端应提示用户重新登录。
    回滚 DB 状态：上方 update_task_status 已写入 "running"，
    但 scheduler 拒绝恢复，实际仍为 paused，需回滚避免 DB 与内存不一致。
    """
    try:
        container.scheduler.resume(task_id)
        return "已恢复调度器中的任务"
    except ResumeBlockedError as e:
        container.repo.update_task_status(task_id, "paused", user_id=user_id)
        raise HTTPException(status_code=400, detail=str(e))


async def _handle_scheduler_restart(container: Container, task_id: str, user_id: str) -> str:
    """restart 分支：stop + start，仅对已注册任务生效

    list_tasks 返回 Task 对象列表，需按 id 比较而非直接 in
    （Task 是 dataclass，in 会触发全字段 __eq__，字符串永不相等）。
    P0-1/P0-2：start 同样校验 Cookie 层 + 冷却期，失败时回滚 DB 到 stopped。
    """
    # 未注册任务（新建后未重启服务）需重启服务才会被加载
    registered_ids = {t.id for t in container.scheduler.list_tasks()}
    if task_id not in registered_ids:
        return "任务未注册到调度器，需重启服务加载"

    is_running = container.scheduler.is_running(task_id)
    if is_running:
        await container.scheduler.stop(task_id)
    try:
        container.scheduler.start(task_id)
        return "已重启调度器中的任务"
    except ResumeBlockedError as e:
        # 任务已被 stop，回滚 DB 到 stopped 保持与实际一致
        container.repo.update_task_status(task_id, "stopped", user_id=user_id)
        raise HTTPException(status_code=400, detail=str(e))


async def _dispatch_scheduler_action(
    container: Container, action: str, task_id: str, user_id: str,
) -> str:
    """按 action 分发到对应的 scheduler 内存操作，返回用户可读的 note

    主流程只负责 DB 写入与编排，scheduler 调用与异常兜底集中在此处
    以降低 control_task 的认知复杂度（S3776）。HTTPException 必须上抛，
    否则 P0-1/P0-2 的 ResumeBlockedError 400 会被兜底 except 吞掉。
    """
    try:
        if action == "pause":
            container.scheduler.pause(task_id)
            return "已暂停调度器中的任务"
        if action == "resume":
            return _handle_scheduler_resume(container, task_id, user_id)
        if action == "stop":
            await container.scheduler.stop(task_id)
            return "已停止调度器中的任务"
        if action == "restart":
            return await _handle_scheduler_restart(container, task_id, user_id)
        return ""  # 不会到达：上层已校验 action 合法性
    except KeyError as e:
        # 任务未注册到 scheduler：仅 DB 状态生效，不阻断请求
        return f"调度器未注册该任务，仅 DB 状态已更新：{e}"
    except HTTPException:
        # P0-1/P0-2：ResumeBlockedError 转换的 400 需向上传播，不能被兜底 except 吞掉
        raise
    except Exception as e:  # noqa: BLE001 - 兜底防止 scheduler 异常导致 500
        # scheduler 内部异常（如 loop 关闭、协程取消）：DB 状态已更新，不阻断
        return f"调度器操作异常，仅 DB 状态已更新：{type(e).__name__}: {e}"


@router.get("/{task_id}/precheck")
def precheck_task_resume(
    task_id: str,
    request: Request,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """恢复前置校验：前端"启动/恢复"按钮点击前调用，判断是否可恢复

    meta-rule #31 状态恢复前置校验：
    - 异常 pause（会话失效/连续失败）后直接 resume 会立即再次触发反爬，
      precheck 提前判断 root_cause 是否消除，避免"恢复→失效→暂停"无效循环
    - 返回结构化响应 {resume_blocked, reason_code, user_hint, retry_after, task_registered}
    - 前端根据 resume_blocked 决定是否弹出确认弹窗或直接阻断

    多用户隔离：仅允许校验当前账号拥有的任务。
    """
    _check_task_ownership(container, task_id, request)
    # collector 为 None 表示纯 web 模式（scheduler 未启动），
    # 此时 resume 不会有反爬风险，直接返回可恢复
    if container.collector is None:
        return {
            "resume_blocked": False,
            "reason_code": "ok",
            "user_hint": "纯 web 模式，无需校验",
            "retry_after": None,
            "task_registered": False,
        }
    return container.scheduler.precheck_resume(task_id)


@router.post("/{task_id}/control")
async def control_task(
    task_id: str,
    request: Request,
    action: str = "pause",
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """控制任务：pause / resume / stop / restart

    XH_WITH_SCHEDULER=1 模式下直接操作 scheduler 内存对象实时生效；
    纯 web 模式下仅改 DB（scheduler 未启动，需以 scheduler 模式重启才生效）。
    多用户隔离：仅允许控制当前账号拥有的任务。
    """
    # 多用户隔离：校验任务归属权
    _check_task_ownership(container, task_id, request)
    user_id = getattr(request.state, "user_id", "default")
    valid = {"pause": "paused", "resume": "running", "stop": "stopped", "restart": "running"}
    if action not in valid:
        raise HTTPException(status_code=400, detail=f"未知 action: {action}")
    new_status = valid[action]
    container.repo.update_task_status(task_id, new_status, user_id=user_id)

    # scheduler 模式下实时唤醒/暂停/停止内存对象，避免"必须重启才生效"痛点
    # 纯 web 模式下 collector 为 None，跳过 scheduler 调用，仅 DB 写入已足够
    scheduler_note = "状态已写入数据库"
    if container.collector is not None:
        scheduler_note = await _dispatch_scheduler_action(container, action, task_id, user_id)

    return {
        "ok": True,
        "id": task_id,
        "status": new_status,
        "note": scheduler_note,
    }


# ============== F-03 任务批量控制 ==============
class BatchControlBody(BaseModel):
    """批量操作入参：task_ids + action

    action 取值与单任务 control 一致：pause / resume / stop / restart / delete
    - delete 走"软删除"路径：status='deleted'，与单任务 DELETE 行为对齐
    """
    task_ids: list[str] = Field(..., min_length=1, max_length=200)
    action: str = Field(..., description="pause/resume/stop/restart/delete")


@router.post("/batch-control")
def batch_control_tasks(
    body: BatchControlBody,
    request: Request,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """批量控制任务（F-03）：N 个任务一次完成 1 个动作

    设计要点：
    - 不抛错"中断整批"：单个任务失败（如不存在/无权访问）只影响 successes/failures 计数，整体请求仍返回 200
    - 原因：用户选了 5 个任务，其中 1 个被别人删了，剩下 4 个必须还能成功
    - 失败原因存到 results[].reason，前端可下钻展示
    - 上限 200 个：避免前端"全选 1k 任务"瞬间打爆 DB
    - 多用户隔离：仅允许操作当前账号拥有的任务，越权任务记入 failures

    与单任务 control_task 的差异：
    - 批量操作仅改 DB status，不同步 scheduler 内存对象
    - 原因：批量调用 scheduler.pause/start 会串行 await N 次，N=200 时阻塞事件循环
    - scheduler 模式下批量暂停的任务会在下一轮 run_once 检测 status 时退出循环
    - 如需实时生效，前端应逐个调用单任务 control 端点
    """
    valid = {"pause": "paused", "resume": "running", "stop": "stopped", "restart": "running", "delete": "deleted"}
    if body.action not in valid:
        raise HTTPException(status_code=400, detail=f"未知 action: {body.action}")
    new_status = valid[body.action]
    user_id = getattr(request.state, "user_id", "default")
    successes: list[str] = []
    failures: list[dict[str, str]] = []
    for tid in body.task_ids:
        try:
            t = container.repo.get_task(tid)
            if not t:
                failures.append({"id": tid, "reason": "not_found"})
                continue
            # 多用户隔离：越权任务记入 failures，不中断整批
            if t.get("user_id") != user_id:
                logger.warning(
                    "批量操作越权拒绝：user={} task={} owner={}",
                    user_id, tid, t.get("user_id"),
                )
                failures.append({"id": tid, "reason": "forbidden"})
                continue
            if body.action == "delete":
                container.repo.delete_task_cascade(tid)
                container.repo.update_task_status(tid, "deleted", user_id=user_id)
                # 清理 scheduler 内存中该任务的冷却期记录
                try:
                    container.scheduler.drop_task_state(tid)
                except Exception:  # noqa: BLE001
                    pass
            else:
                container.repo.update_task_status(tid, new_status, user_id=user_id)
            successes.append(tid)
        except Exception as e:
            failures.append({"id": tid, "reason": str(e)[:120]})
    return {
        "ok": True,
        "action": body.action,
        "new_status": new_status,
        "success_count": len(successes),
        "failure_count": len(failures),
        "successes": successes,
        "failures": failures,
    }
