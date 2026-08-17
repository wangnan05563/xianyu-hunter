"""转人工处理：触发判定、话术生成、会话记录脱敏

职责：
- 判定是否需要转人工（5 个触发条件，任一满足即触发）
- 构建转人工响应（含联系方式与友好提示）
- 转人工时对会话数据脱敏（PII / 敏感字段），供复制给人工客服
- 标记会话为 escalated 并记录原因到 metadata_json 供审计

设计要点（见详细设计 §5.8、状态机 §6.3）：
- _ESCALATE_KEYWORDS 为类属性，便于扩展与测试覆盖
- should_escalate 内部查询 DB 完成所有判定，调用方只需传 session_id + 消息 + 状态
- 脱敏委托给 sanitizer.sanitize_session_for_copy，保持单一职责
- ChatbotEscalationConfig 不含 session_timeout_min（属 ChatbotConfig），
  超时判定用默认值 30 分钟（与 ChatbotConfig 默认一致）
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from loguru import logger

from xianyu_hunter.infra.repo_chatbot import ChatbotRepository
from xianyu_hunter.infra.yaml_config import ChatbotEscalationConfig
from xianyu_hunter.modules.chatbot.sanitizer import (
    sanitize_session_for_copy as _sanitize_session_for_copy,
)


@dataclass
class EscalationResponse:
    """转人工响应"""
    should_escalate: bool
    reason: str
    contact: str
    message_to_user: str
    sanitized_session: dict | None = None


class Escalation:
    """转人工处理器：无状态"""

    # 转人工关键词（用户显式请求）。从具体到宽泛排列，命中任一即触发
    _ESCALATE_KEYWORDS: list[str] = [
        "转人工", "人工客服", "联系客服", "找客服",
        "真人", "人工", "转接", "客服",
    ]

    def __init__(
        self,
        repo: ChatbotRepository,
        config: ChatbotEscalationConfig,
        session_timeout_min: int = 30,
    ) -> None:
        """Args:
            session_timeout_min: 会话超时阈值（分钟），来自 ChatbotConfig.session_timeout_min。
                H6 修复：原硬编码 30 分钟，现由 container 注入，支持配置热更新。
        """
        self._repo = repo
        self._config = config
        self._session_timeout_min = session_timeout_min

    def should_escalate(
        self,
        session_id: str,
        user_message: str,
        context_status: str,
    ) -> tuple[bool, str]:
        """判断是否触发转人工

        5 个触发条件（任一满足即转人工），按短路优先级排列：
        1. 用户消息含转人工关键词 → "用户请求转人工"
        2. 会话状态已是 escalated → "会话已转人工"
        3. 最近 feedback_window_min 内 negative 反馈数 >= feedback_threshold → "负面反馈触发阈值"
        4. 会话超时且未结束 → "会话超时"
        5. 连续 3 次 LLM 调用失败（通过 assistant 消息 metadata.llm_failed 检查）→ "LLM 持续失败"
        """
        # 1. 用户主动请求：关键词命中即转，最高优先级
        for kw in self._ESCALATE_KEYWORDS:
            if kw in user_message:
                return True, "用户请求转人工"

        # 2. 会话已转人工：避免重复判定（escalated 为终态，见状态机 §6.3.5）
        if context_status == "escalated":
            return True, "会话已转人工"

        # 3. 负面反馈触发阈值：窗口内点踩数达标即转
        neg_count = self._repo.count_recent_negative_feedback(
            session_id, window_min=self._config.feedback_window_min
        )
        if neg_count >= self._config.feedback_threshold:
            return True, "负面反馈触发阈值"

        # 4. 会话超时且未结束：ended 已是终态不再触发，active 才需转人工引导
        if context_status != "ended":
            session = self._repo.get_session(session_id)
            if session is not None and self._is_session_timed_out(session):
                return True, "会话超时"

        # 5. 连续 3 次 LLM 调用失败：通过 metadata.llm_failed 标记判定
        if self._has_consecutive_llm_failures(session_id, threshold=3):
            return True, "LLM 持续失败"

        return False, ""

    def build_escalation_response(
        self,
        reason: str,
        session_data: dict | None = None,
    ) -> EscalationResponse:
        """构建转人工响应

        contact 为空时降级为"请联系管理员"（见概要设计 §3.2.8）；
        sanitized_session 仅在提供 session_data 且开启 sanitize_pii 时生成，
        避免无复制需求时白白付出脱敏开销。
        """
        contact = self._config.contact or "请联系管理员"
        message_to_user = (
            "已为您转接人工客服，您可通过以下方式联系工作人员：\n" + contact
        )
        sanitized: dict | None = None
        if session_data is not None and self._config.sanitize_pii:
            sanitized = self.sanitize_session_for_copy(session_data)
        return EscalationResponse(
            should_escalate=True,
            reason=reason,
            contact=contact,
            message_to_user=message_to_user,
            sanitized_session=sanitized,
        )

    def sanitize_session_for_copy(self, session_data: dict) -> dict:
        """委托给 sanitizer 模块完成 PII 脱敏

        转人工时复制会话数据到剪贴板前调用，移除手机号/邮箱/凭据等敏感信息。
        """
        return _sanitize_session_for_copy(session_data)

    def mark_session_escalated(self, session_id: str, reason: str) -> None:
        """更新会话状态为 escalated 并记录原因到 metadata_json

        escalation_reason 写入 session.metadata_json 供审计追溯
        （状态机 §6.3.3：pending → escalated 副作用）。
        采用合并写入以保留其他模块已写入的元数据字段。
        """
        self._repo.update_session_status(session_id, "escalated")
        self._repo.merge_session_metadata(session_id, {"escalation_reason": reason})
        logger.info(f"会话 {session_id} 已转人工：{reason}")

    def _is_session_timed_out(self, session: dict) -> bool:
        """根据 last_active_at 判定会话是否超时"""
        last_active = session.get("last_active_at")
        if not last_active:
            return False
        try:
            last_dt = datetime.fromisoformat(last_active)
        except (ValueError, TypeError):
            return False
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        timeout = timedelta(minutes=self._session_timeout_min)
        return datetime.now(timezone.utc) - last_dt > timeout

    def _has_consecutive_llm_failures(
        self, session_id: str, threshold: int = 3
    ) -> bool:
        """检查最近 assistant 消息是否有连续 threshold 次 LLM 失败

        约定：LLM 调用失败时 assistant 消息 metadata 标记 {"llm_failed": True}。
        从最新消息向前计数，遇到非失败消息即中断（保证"连续"语义）。
        """
        # 取较多历史以覆盖 threshold 条 assistant（中间可能夹杂 user 消息）
        msgs = self._repo.list_messages(session_id, limit=threshold * 2)
        assistant_msgs = [m for m in msgs if m.get("role") == "assistant"]
        consecutive = 0
        for m in reversed(assistant_msgs):
            meta = m.get("metadata")
            if isinstance(meta, dict) and meta.get("llm_failed"):
                consecutive += 1
                if consecutive >= threshold:
                    return True
            else:
                break
        return False
