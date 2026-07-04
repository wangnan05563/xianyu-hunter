"""智能客服对话 API - 对话流、会话管理、消息反馈

设计要点：
- SSE 流式响应：orchestrator.orchestrate() 产出 SSEEvent，API 层按 "event: {type}\ndata: {json}\n\n" 格式化
- 客户端断开检测：每个事件前 await request.is_disconnected()，断开则 break
- chatbot 子容器为 None 时统一返回 403 CHATBOT_DISABLED，避免后续访问 dict key 时 AttributeError
- 错误响应：detail 用 dict 形式 {"code": "CHATBOT_XXX", "message": "..."}，便于前端按 code 分支

认证：由 BearerAuthMiddleware 统一处理，路由内部不做 token 校验。
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field, field_validator

from xianyu_hunter.modules.chatbot.sanitizer import (
    sanitize_session_for_copy as _sanitize_session_for_copy,
)
from xianyu_hunter.web.deps import get_container
from xianyu_hunter.web.services.search_services import (
    ChatbotSessionSearchParams,
    ChatbotSessionSearchService,
)

router = APIRouter(prefix="/api/chatbot", tags=["chatbot"])

# 会话不存在的错误消息：多处端点统一返回此消息，提取为常量避免散落修改
SESSION_NOT_FOUND_MSG = "会话不存在"
# 消息不存在的错误消息：多处端点统一返回此消息，提取为常量避免散落修改
MESSAGE_NOT_FOUND_MSG = "消息不存在"
# 会话/消息 ID 格式校验：UUID32（无连字符的 MD5 风格 hex），多处 Field/Query 复用
_MD5_HEX_PATTERN = r"^[a-f0-9]{32}$"


def _get_chatbot_or_403() -> dict[str, Any]:
    """获取 chatbot 子容器，未启用时抛 403

    chatbot 为 None 表示功能未启用或可选依赖缺失（chromadb/openai 未装），
    此时所有 chatbot API 都应返回 403，避免后续访问 dict key 时 AttributeError。
    """
    container = get_container()
    if container.chatbot is None:
        raise HTTPException(
            status_code=403,
            detail={"code": "CHATBOT_DISABLED", "message": "智能客服未启用"},
        )
    return container.chatbot


# ============== 请求体模型 ==============
class ChatRequest(BaseModel):
    """对话请求

    session_id 为 None 表示首次对话，由 orchestrator 内部创建新会话。
    images 为 base64 data URL 列表（如 data:image/png;base64,...），用于多模态对话。
    """
    session_id: str | None = Field(
        None,
        pattern=_MD5_HEX_PATTERN,
        description="会话 ID（UUID32，无连字符）；None 表示首次对话",
    )
    message: str = Field(..., min_length=1, max_length=2000, description="用户消息（1-2000 字符）")
    enable_tools: bool | None = Field(None, description="是否启用 AGENT 工具；None 用 config 默认值")
    images: list[str] = Field(
        default_factory=list,
        max_length=4,
        description="图片 base64 data URL 列表（最多 4 张），需配置 vision_model 才能解析",
    )

    @field_validator("message")
    @classmethod
    def strip_message(cls, v: str) -> str:
        # 去除首尾空白，避免纯空格消息绕过 min_length=1
        v = v.strip()
        if not v:
            raise ValueError("消息不能为空")
        return v

    @field_validator("images")
    @classmethod
    def validate_images(cls, v: list[str]) -> list[str]:
        # 校验每张图必须是 data URL 前缀，防止注入非法 URL 或过大 payload
        for img in v:
            if not img.startswith("data:image/"):
                raise ValueError("images 必须是 data:image/* base64 data URL")
            # 单张图 base64 不超过 7M（约 5MB 原图），避免 token 爆炸
            if len(img) > 7_000_000:
                raise ValueError("单张图片过大（>5MB），请压缩后重试")
        return v


class SessionCreateRequest(BaseModel):
    title: str | None = Field(None, max_length=100, description="会话标题（可选，默认'新对话'）")


class SessionUpdateTitleRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)


class SessionUpdateFavoriteRequest(BaseModel):
    is_favorite: bool = Field(..., description="是否收藏")


class EscalationTriggerRequest(BaseModel):
    session_id: str = Field(..., pattern=_MD5_HEX_PATTERN, description="要转人工的会话 ID")


class FeedbackRequest(BaseModel):
    rating: str = Field(..., pattern=r"^(positive|negative)$")
    comment: str | None = Field(None, max_length=500)
    # M6：1-5 星评分（可选，向后兼容旧 API）
    star_rating: int | None = Field(None, ge=1, le=5, description="1-5 星评分")
    # M6：反馈分类（irrelevant/inaccurate/other）
    category: str | None = Field(None, pattern=r"^(irrelevant|inaccurate|other)$")


# ============== 对话 ==============
@router.post("/chat")
async def chat(req: ChatRequest, request: Request) -> StreamingResponse:
    """SSE 流式对话

    响应 Content-Type: text/event-stream
    SSE 格式：event: {type}\ndata: {json}\n\n
    客户端断开时停止迭代，orchestrator 协程由 GC 回收。
    """
    chatbot = _get_chatbot_or_403()
    orchestrator = chatbot["orchestrator"]

    async def event_generator():
        try:
            async for event in orchestrator.orchestrate(
                session_id=req.session_id,
                message=req.message,
                enable_tools=req.enable_tools,
                images=req.images,
            ):
                # 每个事件前检查断开，避免向已关闭连接写数据
                if await request.is_disconnected():
                    logger.info(f"客户端断开，停止 SSE 流（session_id={req.session_id}）")
                    break
                yield f"event: {event.event.value}\ndata: {json.dumps(event.data, ensure_ascii=False)}\n\n"
        except Exception as e:
            # orchestrator 内部异常已被转为 SSEEvent(ERROR)，此处兜底未预期异常
            logger.exception(f"SSE 流未预期异常: {e}")
            err = {"code": "INTERNAL_ERROR", "message": "服务器内部错误"}
            yield f"event: error\ndata: {json.dumps(err, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ============== 会话管理 ==============
@router.get("/sessions")
def list_sessions(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None, pattern=r"^(active|ended|escalated)$"),
    keyword: str | None = Query(None, max_length=100, description="搜索标题或消息内容"),
    favorite_only: bool = Query(False, description="仅返回收藏的会话"),
) -> dict[str, Any]:
    """会话列表（收藏置顶，按 last_active_at DESC）"""
    chatbot = _get_chatbot_or_403()
    repo = chatbot["repo"]
    # 使用 SearchService 统一处理分页/慢查询埋点
    # keyword 对应 params.q，由基类 SearchParams 统一持有
    service = ChatbotSessionSearchService(repo)
    result = service.search(ChatbotSessionSearchParams(
        q=keyword, status=status, favorite_only=favorite_only,
        limit=limit, offset=offset,
    ))
    return {"items": result["items"], "total": result["total"], "limit": limit, "offset": offset}


@router.post("/sessions", status_code=201)
def create_session(req: SessionCreateRequest) -> dict[str, Any]:
    """创建新会话"""
    chatbot = _get_chatbot_or_403()
    title = req.title if req.title else "新对话"
    return chatbot["repo"].create_session(title=title)


@router.get("/sessions/{session_id}")
def get_session(session_id: str) -> dict[str, Any]:
    """会话详情"""
    chatbot = _get_chatbot_or_403()
    session = chatbot["repo"].get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "SESSION_NOT_FOUND", "message": SESSION_NOT_FOUND_MSG},
        )
    return session


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str) -> dict[str, Any]:
    """删除会话（级联删除消息与反馈）"""
    chatbot = _get_chatbot_or_403()
    ok = chatbot["repo"].delete_session(session_id)
    if not ok:
        raise HTTPException(
            status_code=404,
            detail={"code": "SESSION_NOT_FOUND", "message": SESSION_NOT_FOUND_MSG},
        )
    return {"ok": True, "id": session_id}


@router.patch("/sessions/{session_id}/title")
def update_session_title(session_id: str, req: SessionUpdateTitleRequest) -> dict[str, Any]:
    """更新会话标题"""
    chatbot = _get_chatbot_or_403()
    repo = chatbot["repo"]
    # 先检查存在，update_session_title 仅返回 bool 无法区分 404 与 0 row
    if repo.get_session(session_id) is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "SESSION_NOT_FOUND", "message": SESSION_NOT_FOUND_MSG},
        )
    repo.update_session_title(session_id, req.title)
    return repo.get_session(session_id)


@router.patch("/sessions/{session_id}/favorite")
def update_session_favorite(session_id: str, req: SessionUpdateFavoriteRequest) -> dict[str, Any]:
    """M2：切换会话收藏状态"""
    chatbot = _get_chatbot_or_403()
    repo = chatbot["repo"]
    if repo.get_session(session_id) is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "SESSION_NOT_FOUND", "message": SESSION_NOT_FOUND_MSG},
        )
    repo.update_session_favorite(session_id, req.is_favorite)
    return repo.get_session(session_id)


@router.post("/sessions/{session_id}/end")
def end_session(session_id: str) -> dict[str, Any]:
    """结束会话（状态置为 ended）"""
    chatbot = _get_chatbot_or_403()
    repo = chatbot["repo"]
    if repo.get_session(session_id) is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "SESSION_NOT_FOUND", "message": SESSION_NOT_FOUND_MSG},
        )
    repo.update_session_status(session_id, "ended")
    return {"ok": True, "id": session_id, "status": "ended"}


# ============== 消息历史 ==============
@router.get("/sessions/{session_id}/messages")
def list_messages(
    session_id: str,
    limit: int = Query(50, ge=1, le=100),
    before_id: str | None = Query(None, pattern=_MD5_HEX_PATTERN),
) -> dict[str, Any]:
    """消息历史（游标分页，按 created_at ASC）"""
    chatbot = _get_chatbot_or_403()
    repo = chatbot["repo"]
    if repo.get_session(session_id) is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "SESSION_NOT_FOUND", "message": SESSION_NOT_FOUND_MSG},
        )
    items = repo.list_messages(session_id, limit=limit, before_id=before_id)
    # has_more + oldest_id 用于前端下次分页游标
    has_more = len(items) >= limit
    oldest_id = items[0]["id"] if items else None
    return {"items": items, "has_more": has_more, "oldest_id": oldest_id}


# ============== M4 消息撤回 ==============
@router.post("/messages/{message_id}/recall")
def recall_message(message_id: str) -> dict[str, Any]:
    """撤回用户消息（2 分钟时间窗内，软删除）"""
    chatbot = _get_chatbot_or_403()
    repo = chatbot["repo"]
    message = repo.get_message(message_id)
    if message is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "MESSAGE_NOT_FOUND", "message": MESSAGE_NOT_FOUND_MSG},
        )
    result = repo.recall_message(message_id, time_window_sec=120)
    if not result["ok"]:
        raise HTTPException(
            status_code=400,
            detail={"code": "RECALL_FAILED", "message": result["reason"]},
        )
    return {"ok": True, "id": message_id, "is_recalled": True}


# ============== M5 主动转人工 ==============
@router.post("/escalation/trigger")
def trigger_escalation(req: EscalationTriggerRequest) -> dict[str, Any]:
    """主动触发转人工（将 session 状态置为 escalated）"""
    chatbot = _get_chatbot_or_403()
    repo = chatbot["repo"]
    if repo.get_session(req.session_id) is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "SESSION_NOT_FOUND", "message": SESSION_NOT_FOUND_MSG},
        )
    repo.update_session_status(req.session_id, "escalated")
    return {"ok": True, "session_id": req.session_id, "status": "escalated"}


# ============== 反馈 ==============
@router.post("/messages/{message_id}/feedback", status_code=201)
def add_message_feedback(message_id: str, req: FeedbackRequest) -> dict[str, Any]:
    """消息反馈（positive/negative）

    negative 反馈会被 escalation 模块统计，达阈值时触发转人工。
    """
    chatbot = _get_chatbot_or_403()
    repo = chatbot["repo"]
    message = repo.get_message(message_id)
    if message is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "MESSAGE_NOT_FOUND", "message": MESSAGE_NOT_FOUND_MSG},
        )
    # M6：当 star_rating 存在时，后端自动派生 rating，防止客户端传矛盾值
    # 4-5 星 → positive，1-3 星 → negative；star_rating 为 None 时沿用客户端传的 rating
    effective_rating = req.rating
    if req.star_rating is not None:
        effective_rating = "positive" if req.star_rating >= 4 else "negative"
    ok = repo.update_message_feedback(
        message_id, effective_rating, req.comment,
        star_rating=req.star_rating, category=req.category,
    )
    if not ok:
        raise HTTPException(
            status_code=404,
            detail={"code": "MESSAGE_NOT_FOUND", "message": MESSAGE_NOT_FOUND_MSG},
        )
    # negative 反馈达阈值时触发会话转人工状态
    escalate_triggered = False
    if effective_rating == "negative":
        cfg = chatbot["config"]
        threshold = cfg.escalation.feedback_threshold
        window = cfg.escalation.feedback_window_min
        count = repo.count_recent_negative_feedback(message["session_id"], window_min=window)
        if count >= threshold:
            repo.update_session_status(message["session_id"], "escalated")
            escalate_triggered = True
    return {"ok": True, "escalate_triggered": escalate_triggered}


@router.get("/feedback/recent")
def list_recent_feedback(limit: int = Query(50, ge=1, le=200)) -> dict[str, Any]:
    """最近反馈列表（跨会话）"""
    chatbot = _get_chatbot_or_403()
    items = chatbot["repo"].get_recent_feedback(limit=limit)
    return {"items": items, "total": len(items)}


# ============== 转人工导出 ==============
@router.get("/escalation/{session_id}/export")
def export_session_for_escalation(session_id: str) -> dict[str, Any]:
    """导出会话记录供转人工复制，自动脱敏 PII / 敏感字段

    前端"复制会话记录"按钮调用此接口，返回纯文本格式，
    由 sanitizer.sanitize_session_for_copy 统一脱敏，避免泄露手机号/邮箱/凭据。
    """
    chatbot = _get_chatbot_or_403()
    repo = chatbot["repo"]
    session = repo.get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "SESSION_NOT_FOUND", "message": SESSION_NOT_FOUND_MSG},
        )
    # 取较大 limit 覆盖整个会话（list_messages 按 created_at ASC 排序）
    messages = repo.list_messages(session_id, limit=1000)
    # 委托 sanitizer 做深拷贝 + 脱敏，避免污染 repo 返回的原始数据
    sanitized = _sanitize_session_for_copy({"messages": messages})
    sanitized_msgs = sanitized.get("messages", [])

    # 拼接为人工客服可读的纯文本：会话头 + 逐条消息
    lines = [
        "会话记录",
        f"会话ID: {session.get('id', '')}",
        f"标题: {session.get('title', '')}",
        f"状态: {session.get('status', '')}",
        f"创建时间: {session.get('created_at', '')}",
        f"最后活跃: {session.get('last_active_at', '')}",
        "",
        "消息记录:",
    ]
    for msg in sanitized_msgs:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        created_at = msg.get("created_at", "")
        lines.append(f"[{role}] {created_at}")
        lines.append(content)
        lines.append("")
    return {"content": "\n".join(lines)}
