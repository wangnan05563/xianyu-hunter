"""智能客服配置与审计 API - 配置获取/热更新 + 审计日志查询

设计要点：
- GET /config 返回合并后的配置（yaml 基线 + DB 覆盖）
- PUT /config 仅支持热更新字段（_UPDATABLE_KEYS 白名单），写入 DB + 审计日志
- 审计日志仅存 sha256 hash 不存明文（敏感字段保护，见 repo_chatbot.add_audit_log）
- chatbot 子容器为 None 时统一返回 403 CHATBOT_DISABLED

认证：由 BearerAuthMiddleware 统一处理。
"""
from __future__ import annotations

import hashlib
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field, field_validator

from xianyu_hunter.web.deps import get_container

router = APIRouter(prefix="/api/chatbot", tags=["chatbot-config"])


# 支持热更新的配置 key 白名单
# 为什么用集合：O(1) 查找；为什么显式列出：避免误开放需要重启的字段（如 llm.model / kb.doc_paths / kb.embedding_model）
# 覆盖 Config.tsx 中所有 updateConfig 调用，避免前端编辑被 422 拒绝导致 UI 闪回
_UPDATABLE_KEYS: set[str] = {
    "enabled",
    "max_history_turns",
    "session_timeout_min",
    "rag.top_k",
    "rag.similarity_threshold",
    "rag.max_context_chars",
    "agent.enable_tools",
    "agent.max_tool_rounds",
    "agent.tool_trigger_mode",
    "kb.auto_update_enabled",
    "kb.update_interval_hours",
    "faq.similarity_threshold",
    "faq.confirm_threshold",
    "escalation.contact",
    "escalation.feedback_threshold",
    "escalation.feedback_window_min",
    "escalation.sanitize_pii",
    "welcome_message",
}


def _get_chatbot_or_403() -> dict[str, Any]:
    """获取 chatbot 子容器，未启用时抛 403"""
    container = get_container()
    if container.chatbot is None:
        raise HTTPException(
            status_code=403,
            detail={"code": "CHATBOT_DISABLED", "message": "智能客服未启用"},
        )
    return container.chatbot


class ConfigUpdateRequest(BaseModel):
    """配置更新请求（仅支持热更新字段）"""
    key: str = Field(..., description="配置 key（必须在 updatable_keys 中）")
    value: str = Field(..., max_length=1000, description="配置值（字符串形式）")

    @field_validator("key")
    @classmethod
    def validate_updatable(cls, v: str) -> str:
        if v not in _UPDATABLE_KEYS:
            raise ValueError(f"配置项 {v} 不支持热更新")
        return v


def _hash_value(value: str | None) -> str | None:
    """对配置值取 sha256 hash（审计日志不存明文）"""
    if value is None:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@router.get("/config")
def get_config() -> dict[str, Any]:
    """获取合并后的配置（yaml 基线 + DB 覆盖）

    DB 中存在的热更新 key 覆盖 yaml 默认值，未存在的用 yaml 默认值。
    """
    chatbot = _get_chatbot_or_403()
    cfg = chatbot["config"]
    db_overrides = chatbot["repo"].get_all_config()

    # 以 yaml 配置为基线
    result: dict[str, Any] = {
        "enabled": cfg.enabled,
        "max_history_turns": cfg.max_history_turns,
        "session_timeout_min": cfg.session_timeout_min,
        "rag": cfg.rag.model_dump(),
        "llm": cfg.llm.model_dump(),
        "agent": cfg.agent.model_dump(),
        "kb": cfg.kb.model_dump(),
        "faq": cfg.faq.model_dump(),
        "escalation": cfg.escalation.model_dump(),
    }

    # 应用 DB 覆盖（仅热更新字段，类型转换与 _UPDATABLE_KEYS 对应）
    # 类型映射：bool / int / float / str 分别处理，DB 一律存字符串
    if "enabled" in db_overrides:
        result["enabled"] = db_overrides["enabled"].lower() == "true"
    if "max_history_turns" in db_overrides:
        result["max_history_turns"] = int(db_overrides["max_history_turns"])
    if "session_timeout_min" in db_overrides:
        result["session_timeout_min"] = int(db_overrides["session_timeout_min"])
    if "rag.top_k" in db_overrides:
        result["rag"]["top_k"] = int(db_overrides["rag.top_k"])
    if "rag.similarity_threshold" in db_overrides:
        result["rag"]["similarity_threshold"] = float(db_overrides["rag.similarity_threshold"])
    if "rag.max_context_chars" in db_overrides:
        result["rag"]["max_context_chars"] = int(db_overrides["rag.max_context_chars"])
    if "agent.enable_tools" in db_overrides:
        result["agent"]["enable_tools"] = db_overrides["agent.enable_tools"].lower() == "true"
    if "agent.max_tool_rounds" in db_overrides:
        result["agent"]["max_tool_rounds"] = int(db_overrides["agent.max_tool_rounds"])
    if "agent.tool_trigger_mode" in db_overrides:
        result["agent"]["tool_trigger_mode"] = db_overrides["agent.tool_trigger_mode"]
    if "kb.auto_update_enabled" in db_overrides:
        result["kb"]["auto_update_enabled"] = db_overrides["kb.auto_update_enabled"].lower() == "true"
    if "kb.update_interval_hours" in db_overrides:
        result["kb"]["update_interval_hours"] = int(db_overrides["kb.update_interval_hours"])
    if "faq.similarity_threshold" in db_overrides:
        result["faq"]["similarity_threshold"] = float(db_overrides["faq.similarity_threshold"])
    if "faq.confirm_threshold" in db_overrides:
        result["faq"]["confirm_threshold"] = float(db_overrides["faq.confirm_threshold"])
    if "escalation.contact" in db_overrides:
        result["escalation"]["contact"] = db_overrides["escalation.contact"]
    if "escalation.feedback_threshold" in db_overrides:
        result["escalation"]["feedback_threshold"] = int(db_overrides["escalation.feedback_threshold"])
    if "escalation.feedback_window_min" in db_overrides:
        result["escalation"]["feedback_window_min"] = int(db_overrides["escalation.feedback_window_min"])
    if "escalation.sanitize_pii" in db_overrides:
        result["escalation"]["sanitize_pii"] = db_overrides["escalation.sanitize_pii"].lower() == "true"

    result["updatable_keys"] = sorted(_UPDATABLE_KEYS)
    return result


@router.put("/config")
def update_config(req: ConfigUpdateRequest) -> dict[str, Any]:
    """更新配置（仅热更新字段）

    流程：读旧值 → 写 DB → 写审计日志（仅 hash）→ 返回新旧值。
    """
    chatbot = _get_chatbot_or_403()
    repo = chatbot["repo"]

    old_value = repo.get_config(req.key)
    # 跳过未变更的写入，减少审计日志噪音
    if old_value == req.value:
        return {
            "ok": True,
            "key": req.key,
            "old_value": old_value,
            "new_value": req.value,
            "changed": False,
        }

    repo.set_config(req.key, req.value)
    repo.add_audit_log(
        action="update_config",
        target=req.key,
        old_value_hash=_hash_value(old_value),
        new_value_hash=_hash_value(req.value),
        source="web",
    )
    logger.info(f"配置更新: key={req.key} old={old_value} new={req.value}")

    return {
        "ok": True,
        "key": req.key,
        "old_value": old_value,
        "new_value": req.value,
        "changed": True,
    }


@router.get("/audit-logs")
def list_audit_logs(
    action: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """审计日志列表（按 created_at DESC）"""
    chatbot = _get_chatbot_or_403()
    items = chatbot["repo"].list_audit_logs(action=action, limit=limit)
    return {"items": items, "total": len(items)}


# ============== FAQ 管理 ==============
class FAQUpsertRequest(BaseModel):
    """FAQ 新增/更新请求

    字段 enabled (boolean) 对应 DB 中 is_active (int 0/1)，
    路由层做转换，前端不感知底层存储差异。
    """
    id: int | None = Field(None, description="FAQ ID；None 表示新增")
    question: str = Field(..., min_length=1, max_length=500, description="问题")
    answer: str = Field(..., min_length=1, max_length=2000, description="答案")
    category: str = Field("general", max_length=50, description="分类")
    enabled: bool = Field(True, description="是否启用")
    sort_order: int = Field(0, ge=0, description="排序权重")


@router.get("/faq")
def list_faqs(
    active_only: bool = Query(False, description="仅返回启用的 FAQ"),
) -> list[dict[str, Any]]:
    """FAQ 列表（按 sort_order ASC, id ASC）

    返回数组格式（非 {items, total}），与前端 FAQ[] 类型对齐。
    """
    chatbot = _get_chatbot_or_403()
    items = chatbot["repo"].list_faqs(active_only=active_only)
    # 字段映射：后端 is_active (int) → 前端 enabled (boolean)
    for item in items:
        item["enabled"] = bool(item.pop("is_active", 1))
    return items


@router.post("/faq", status_code=201)
def upsert_faq(req: FAQUpsertRequest) -> dict[str, Any]:
    """FAQ 新增/更新（upsert）

    id 为 None 时新增，否则更新已有 FAQ。
    FAQMatcher 有 5 分钟 TTL 缓存，更新后最多 5 分钟内生效（_load_faqs）。
    """
    chatbot = _get_chatbot_or_403()
    repo = chatbot["repo"]
    result = repo.upsert_faq(
        faq_id=req.id,
        question=req.question,
        answer=req.answer,
        category=req.category,
        is_active=1 if req.enabled else 0,
        sort_order=req.sort_order,
    )
    repo.add_audit_log(
        action="faq_upsert",
        target=str(result["id"]),
        old_value_hash=None,
        new_value_hash=_hash_value(req.question[:50]),
        source="web",
    )
    logger.info(f"FAQ upsert: id={result['id']} question={req.question[:30]}")
    result["enabled"] = bool(result.pop("is_active", 1))
    return result


@router.delete("/faq/{faq_id}")
def delete_faq(faq_id: int) -> dict[str, Any]:
    """删除 FAQ"""
    chatbot = _get_chatbot_or_403()
    repo = chatbot["repo"]
    ok = repo.delete_faq(faq_id)
    if not ok:
        raise HTTPException(
            status_code=404,
            detail={"code": "FAQ_NOT_FOUND", "message": "FAQ 不存在"},
        )
    repo.add_audit_log(
        action="faq_delete",
        target=str(faq_id),
        old_value_hash=None,
        new_value_hash=None,
        source="web",
    )
    logger.info(f"FAQ 删除: id={faq_id}")
    return {"ok": True, "id": faq_id}


# ============== 欢迎语（M1 引导卡）==============

# 默认欢迎语：DB 未配置时使用，前端可在用户首次进入时叠加"个性化"策略
_DEFAULT_WELCOME_MESSAGE = "Hi，我是智能客服小蜜，请问有什么可以帮您？"


@router.get("/welcome")
def get_welcome() -> dict[str, Any]:
    """获取欢迎语（M1 引导卡数据源）

    优先从 chatbot_config 表读 welcome_message，未配置时用默认值。
    chatbot 禁用时返回默认欢迎语（引导卡与 LLM 解耦）。
    """
    from sqlalchemy import select
    from xianyu_hunter.infra.db_models import ChatbotConfigRow

    container = get_container()
    message = _DEFAULT_WELCOME_MESSAGE
    updated_at: str | None = None
    # 走 chatbot 子容器获取 Session：与现有 get_config 保持一致的访问路径
    if container.chatbot is not None:
        repo = container.chatbot["repo"]
        db_value = repo.get_config("welcome_message")
        if db_value:
            message = db_value
        # updated_at 单独查一次（get_config 不返回时间戳，避免破坏现有签名）
        with repo._Session() as session:
            row = session.execute(
                select(ChatbotConfigRow).where(ChatbotConfigRow.key == "welcome_message")
            ).scalars().first()
            if row and row.updated_at:
                updated_at = row.updated_at.isoformat()
    return {
        "message": message,
        "persona": "xiaomi",  # 预留，不引入多 persona
        "updated_at": updated_at,
    }
