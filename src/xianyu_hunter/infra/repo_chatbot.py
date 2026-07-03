"""智能客服模块对话仓储 - 7 表 CRUD 封装

职责：封装 chatbot_sessions / chatbot_messages / chatbot_faqs /
chatbot_feedback / chatbot_kb_versions / chatbot_config / chatbot_audit_logs
七张表的持久化访问，复用主 Repository.engine（不独立 create_engine，
避免 SQLite 多连接锁竞争，见概要设计 §3.11 P0 修订）。

设计要点：
- 接受外部注入的 engine，自身只负责建表（checkfirst=True 幂等）与默认配置初始化
- 所有 Session 用 context manager（with self._session() as session:）确保关闭
- expire_on_commit=False：commit 后仍可访问 row 属性，避免 DetachedInstanceError
- 时间字段返回时统一 isoformat() 序列化，JSON 字段用 json.dumps/loads
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import Engine, delete, func, or_, select, update
from sqlalchemy.orm import sessionmaker

from xianyu_hunter.infra.db_models import (
    Base,
    ChatbotAuditLogRow,
    ChatbotConfigRow,
    ChatbotFAQRow,
    ChatbotFeedbackRow,
    ChatbotKBVersionRow,
    ChatbotMessageRow,
    ChatbotSessionRow,
)


def _utcnow() -> datetime:
    """统一 UTC 时间生成（与 db_models._utcnow 保持一致，避免循环导入）"""
    return datetime.now(timezone.utc)


def _uuid32() -> str:
    """生成无连字符的 UUID32（与主系统 task_id 生成方式一致）"""
    return uuid.uuid4().hex


def _serialize_dt(dt: datetime | None) -> str | None:
    """datetime → isoformat 字符串；None 透传"""
    return dt.isoformat() if dt is not None else None


class ChatbotRepository:
    """对话仓储：复用主 Repository.engine

    关键约束：
    - 不调用 create_engine / init_db，仅 checkfirst 建表
    - Session 使用 sessionmaker(bind=engine, expire_on_commit=False)
    """

    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        # expire_on_commit=False：commit 后 row 属性仍可访问，避免返回 dict 时触发 re-load 失败
        self._session = sessionmaker(bind=engine, expire_on_commit=False)
        # 幂等建表：主 init_db 可能未运行（如独立测试），checkfirst=True 保证安全
        Base.metadata.create_all(
            engine,
            tables=[
                ChatbotSessionRow.__table__,
                ChatbotMessageRow.__table__,
                ChatbotFAQRow.__table__,
                ChatbotFeedbackRow.__table__,
                ChatbotKBVersionRow.__table__,
                ChatbotConfigRow.__table__,
                ChatbotAuditLogRow.__table__,
            ],
            checkfirst=True,
        )
        self._init_default_config()

    # ==================== 会话表（chatbot_sessions）====================

    def create_session(
        self, user_id: str = "default", title: str = "新对话"
    ) -> dict:
        """创建会话，返回完整会话 dict"""
        session_id = _uuid32()
        now = _utcnow()
        with self._session() as session:
            row = ChatbotSessionRow(
                id=session_id,
                user_id=user_id,
                title=title,
                status="active",
                message_count=0,
                created_at=now,
                updated_at=now,
                last_active_at=now,
            )
            session.add(row)
            session.commit()
            return {
                "id": row.id,
                "user_id": row.user_id,
                "title": row.title,
                "status": row.status,
                "message_count": row.message_count,
                "created_at": _serialize_dt(row.created_at),
                "updated_at": _serialize_dt(row.updated_at),
                "last_active_at": _serialize_dt(row.last_active_at),
                "is_favorite": row.is_favorite,
            }

    def get_session(self, session_id: str) -> dict | None:
        with self._session() as session:
            row = session.get(ChatbotSessionRow, session_id)
            if row is None:
                return None
            return {
                "id": row.id,
                "user_id": row.user_id,
                "title": row.title,
                "status": row.status,
                "message_count": row.message_count,
                "created_at": _serialize_dt(row.created_at),
                "updated_at": _serialize_dt(row.updated_at),
                "last_active_at": _serialize_dt(row.last_active_at),
                "is_favorite": row.is_favorite,
            }

    def list_sessions(
        self,
        user_id: str = "default",
        status: str | None = None,
        keyword: str | None = None,
        favorite_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """按 is_favorite DESC, last_active_at DESC 排序

        keyword：模糊匹配标题或用户消息内容（子查询 LIMIT 50 防全表扫）
        favorite_only：仅返回收藏的会话
        """
        with self._session() as session:
            stmt = select(ChatbotSessionRow).where(
                ChatbotSessionRow.user_id == user_id
            )
            if status is not None:
                stmt = stmt.where(ChatbotSessionRow.status == status)
            if favorite_only:
                stmt = stmt.where(ChatbotSessionRow.is_favorite == 1)
            if keyword:
                # 子查询：匹配消息内容的 session_id 集合（LIMIT 50 防全表扫）
                msg_subq = (
                    select(ChatbotMessageRow.session_id)
                    .where(
                        ChatbotMessageRow.role == "user",
                        ChatbotMessageRow.content.like(f"%{keyword}%"),
                    )
                    .group_by(ChatbotMessageRow.session_id)
                    .limit(50)
                )
                stmt = stmt.where(
                    or_(
                        ChatbotSessionRow.title.like(f"%{keyword}%"),
                        ChatbotSessionRow.id.in_(msg_subq),
                    )
                )
            # 收藏置顶：is_favorite DESC 优先，再按 last_active_at DESC
            stmt = stmt.order_by(
                ChatbotSessionRow.is_favorite.desc(),
                ChatbotSessionRow.last_active_at.desc(),
            )
            stmt = stmt.limit(limit).offset(offset)
            rows = session.execute(stmt).scalars().all()
            return [
                {
                    "id": r.id,
                    "user_id": r.user_id,
                    "title": r.title,
                    "status": r.status,
                    "message_count": r.message_count,
                    "created_at": _serialize_dt(r.created_at),
                    "updated_at": _serialize_dt(r.updated_at),
                    "last_active_at": _serialize_dt(r.last_active_at),
                    "is_favorite": r.is_favorite,
                }
                for r in rows
            ]

    def count_sessions(
        self,
        user_id: str = "default",
        status: str | None = None,
        keyword: str | None = None,
        favorite_only: bool = False,
    ) -> int:
        """会话总数（H4 修复：list_sessions 的 total 需真实计数支持前端分页）

        与 list_sessions 共享过滤条件，但不应用 limit/offset。
        """
        with self._session() as session:
            stmt = select(func.count(ChatbotSessionRow.id)).where(
                ChatbotSessionRow.user_id == user_id
            )
            if status is not None:
                stmt = stmt.where(ChatbotSessionRow.status == status)
            if favorite_only:
                stmt = stmt.where(ChatbotSessionRow.is_favorite == 1)
            if keyword:
                msg_subq = (
                    select(ChatbotMessageRow.session_id)
                    .where(
                        ChatbotMessageRow.role == "user",
                        ChatbotMessageRow.content.like(f"%{keyword}%"),
                    )
                    .group_by(ChatbotMessageRow.session_id)
                    .limit(50)
                )
                stmt = stmt.where(
                    or_(
                        ChatbotSessionRow.title.like(f"%{keyword}%"),
                        ChatbotSessionRow.id.in_(msg_subq),
                    )
                )
            return int(session.execute(stmt).scalar() or 0)

    def update_session_status(self, session_id: str, status: str) -> bool:
        """status: active / ended / escalated；返回是否更新成功"""
        with self._session() as session:
            result = session.execute(
                update(ChatbotSessionRow)
                .where(ChatbotSessionRow.id == session_id)
                .values(status=status, updated_at=_utcnow())
            )
            session.commit()
            return result.rowcount > 0

    def update_session_title(self, session_id: str, title: str) -> bool:
        with self._session() as session:
            result = session.execute(
                update(ChatbotSessionRow)
                .where(ChatbotSessionRow.id == session_id)
                .values(title=title, updated_at=_utcnow())
            )
            session.commit()
            return result.rowcount > 0

    def update_session_favorite(self, session_id: str, is_favorite: bool) -> bool:
        """M2：切换会话收藏状态，收藏的会话在列表中置顶"""
        with self._session() as session:
            result = session.execute(
                update(ChatbotSessionRow)
                .where(ChatbotSessionRow.id == session_id)
                .values(is_favorite=1 if is_favorite else 0, updated_at=_utcnow())
            )
            session.commit()
            return result.rowcount > 0

    def merge_session_metadata(self, session_id: str, patch: dict) -> bool:
        """合并写入 session.metadata_json（保留已有字段）

        单事务内 SELECT + UPDATE 保证原子性，避免并发覆盖。
        返回是否更新成功（session_id 不存在时返回 False）。
        """
        now = _utcnow()
        with self._session() as session:
            row = session.execute(
                select(ChatbotSessionRow).where(ChatbotSessionRow.id == session_id)
            ).scalar_one_or_none()
            if row is None:
                return False
            existing: dict = {}
            if row.metadata_json:
                try:
                    existing = json.loads(row.metadata_json)
                except (json.JSONDecodeError, TypeError):
                    existing = {}
            # M-30 修复：过滤 None 值，避免覆盖已有有效字段（如 escalation_reason 被误清空）
            existing.update({k: v for k, v in patch.items() if v is not None})
            row.metadata_json = json.dumps(existing, ensure_ascii=False)
            row.updated_at = now
            session.commit()
            return True

    def touch_session(self, session_id: str) -> None:
        """更新 last_active_at（用于会话超时判定）"""
        with self._session() as session:
            session.execute(
                update(ChatbotSessionRow)
                .where(ChatbotSessionRow.id == session_id)
                .values(last_active_at=_utcnow(), updated_at=_utcnow())
            )
            session.commit()

    def delete_session(self, session_id: str) -> bool:
        """级联删除：先删 messages，再删 feedback，最后删 session

        顺序说明：messages 与 feedback 无外键依赖，但 feedback.message_id
        语义上引用 messages.id，先删 messages 可避免残留悬空引用。
        """
        with self._session() as session:
            session.execute(
                delete(ChatbotMessageRow).where(
                    ChatbotMessageRow.session_id == session_id
                )
            )
            session.execute(
                delete(ChatbotFeedbackRow).where(
                    ChatbotFeedbackRow.session_id == session_id
                )
            )
            result = session.execute(
                delete(ChatbotSessionRow).where(
                    ChatbotSessionRow.id == session_id
                )
            )
            session.commit()
            return result.rowcount > 0

    # ==================== 消息表（chatbot_messages）====================

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict | None = None,
        tokens_used: int | None = None,
        images: list[str] | None = None,
    ) -> dict:
        """添加消息，同步维护 sessions.message_count 与 last_active_at

        message_count 冗余字段由本方法维护，避免列表展示时 N+1 聚合查询。
        images: M4 用户消息关联的图片 data URL 列表，存 images_json
        """
        message_id = _uuid32()
        now = _utcnow()
        metadata_json = json.dumps(metadata, ensure_ascii=False) if metadata else None
        images_json = json.dumps(images, ensure_ascii=False) if images else None
        with self._session() as session:
            row = ChatbotMessageRow(
                id=message_id,
                session_id=session_id,
                role=role,
                content=content,
                metadata_json=metadata_json,
                tokens_used=tokens_used,
                images_json=images_json,
                created_at=now,
            )
            session.add(row)
            # 同步更新冗余计数与最后活跃时间（用于会话列表展示与超时判定）
            session.execute(
                update(ChatbotSessionRow)
                .where(ChatbotSessionRow.id == session_id)
                .values(
                    message_count=ChatbotSessionRow.message_count + 1,
                    last_active_at=now,
                    updated_at=now,
                )
            )
            session.commit()
            return {
                "id": row.id,
                "session_id": row.session_id,
                "role": row.role,
                "content": row.content,
                "metadata": metadata,
                "tokens_used": row.tokens_used,
                "images": images,
                "is_recalled": 0,
                "created_at": _serialize_dt(row.created_at),
            }

    def list_messages(
        self,
        session_id: str,
        limit: int = 50,
        before_id: str | None = None,
    ) -> list[dict]:
        """查询消息：游标分页，按 created_at ASC 排序

        before_id 不为 None 时，返回该 ID 消息之前（更早）的消息（不含该 ID）。
        """
        with self._session() as session:
            stmt = select(ChatbotMessageRow).where(
                ChatbotMessageRow.session_id == session_id
            )
            if before_id is not None:
                before = session.get(ChatbotMessageRow, before_id)
                if before is not None:
                    stmt = stmt.where(
                        ChatbotMessageRow.created_at < before.created_at
                    )
            stmt = stmt.order_by(ChatbotMessageRow.created_at.asc()).limit(limit)
            rows = session.execute(stmt).scalars().all()
            return [self._message_row_to_dict(r) for r in rows]

    def get_message(self, message_id: str) -> dict | None:
        with self._session() as session:
            row = session.get(ChatbotMessageRow, message_id)
            if row is None:
                return None
            return self._message_row_to_dict(row)

    def update_message_feedback(
        self,
        message_id: str,
        feedback: str,
        comment: str | None = None,
        star_rating: int | None = None,
        category: str | None = None,
    ) -> bool:
        """更新消息反馈，同时在 chatbot_feedback 表插入一条记录

        feedback: positive / negative（由星级推导：4-5→positive，1-3→negative）。
        star_rating: M6 1-5 星评分。
        category: M6 反馈分类（irrelevant/inaccurate/other）。
        chatbot_feedback 用于转人工判定（count_recent_negative_feedback 统计窗口内 negative 数）。
        """
        with self._session() as session:
            row = session.get(ChatbotMessageRow, message_id)
            if row is None:
                return False
            row.feedback = feedback
            row.feedback_comment = comment
            row.feedback_rating = star_rating
            row.feedback_category = category
            # 反馈独立表记录：与 messages.feedback 解耦，支持趋势分析与转人工判定
            session.add(
                ChatbotFeedbackRow(
                    session_id=row.session_id,
                    message_id=message_id,
                    rating=feedback,
                    comment=comment,
                    star_rating=star_rating,
                    category=category,
                    created_at=_utcnow(),
                )
            )
            session.commit()
            return True

    @staticmethod
    def _message_row_to_dict(row: ChatbotMessageRow) -> dict:
        """消息行 → dict，metadata_json / images_json 反序列化"""
        metadata = None
        if row.metadata_json:
            try:
                metadata = json.loads(row.metadata_json)
            except (json.JSONDecodeError, TypeError):
                metadata = None
        images = None
        if row.images_json:
            try:
                images = json.loads(row.images_json)
            except (json.JSONDecodeError, TypeError):
                images = None
        return {
            "id": row.id,
            "session_id": row.session_id,
            "role": row.role,
            "content": row.content,
            "metadata": metadata,
            "feedback": row.feedback,
            "feedback_comment": row.feedback_comment,
            # M6：返回星级与分类，供前端已评价状态回显
            "feedback_rating": row.feedback_rating,
            "feedback_category": row.feedback_category,
            "tokens_used": row.tokens_used,
            "images": images,
            "is_recalled": row.is_recalled,
            "created_at": _serialize_dt(row.created_at),
        }

    def recall_message(self, message_id: str, time_window_sec: int = 120) -> dict:
        """M4：软删除消息（标记 is_recalled=1）

        校验：仅 user 角色消息可撤回，且在 time_window_sec 秒内。
        返回 {"ok": bool, "reason": str}
        """
        with self._session() as session:
            row = session.get(ChatbotMessageRow, message_id)
            if row is None:
                return {"ok": False, "reason": "消息不存在"}
            if row.role != "user":
                return {"ok": False, "reason": "仅支持撤回用户消息"}
            if row.is_recalled:
                return {"ok": False, "reason": "消息已撤回"}
            # SQLite 存的 datetime 不带时区，_utcnow() 带 UTC 时区，
            # 统一为 naive 比较：两者都去掉时区后相减
            elapsed = (_utcnow().replace(tzinfo=None) - row.created_at).total_seconds()
            if elapsed > time_window_sec:
                return {"ok": False, "reason": f"超过 {time_window_sec} 秒撤回时限"}
            session.execute(
                update(ChatbotMessageRow)
                .where(ChatbotMessageRow.id == message_id)
                .values(is_recalled=1)
            )
            session.commit()
            return {"ok": True, "reason": ""}

    # ==================== FAQ 表（chatbot_faqs）====================

    def list_faqs(
        self,
        category: str | None = None,
        active_only: bool = True,
    ) -> list[dict]:
        with self._session() as session:
            stmt = select(ChatbotFAQRow)
            if active_only:
                stmt = stmt.where(ChatbotFAQRow.is_active == 1)
            if category is not None:
                stmt = stmt.where(ChatbotFAQRow.category == category)
            stmt = stmt.order_by(ChatbotFAQRow.sort_order.asc(), ChatbotFAQRow.id.asc())
            rows = session.execute(stmt).scalars().all()
            return [self._faq_row_to_dict(r) for r in rows]

    def get_faq(self, faq_id: int) -> dict | None:
        with self._session() as session:
            row = session.get(ChatbotFAQRow, faq_id)
            if row is None:
                return None
            return self._faq_row_to_dict(row)

    def upsert_faq(
        self,
        faq_id: int | None,
        question: str,
        answer: str,
        category: str = "general",
        is_active: int = 1,
        sort_order: int = 0,
    ) -> dict:
        """FAQ upsert：faq_id=None 新增，否则更新。返回完整 FAQ dict（含 id）"""
        now = _utcnow()
        with self._session() as session:
            if faq_id is not None:
                row = session.get(ChatbotFAQRow, faq_id)
                if row is not None:
                    row.question = question
                    row.answer = answer
                    row.category = category
                    row.is_active = is_active
                    row.sort_order = sort_order
                    row.updated_at = now
                    session.commit()
                    return self._faq_row_to_dict(row)
            row = ChatbotFAQRow(
                question=question,
                answer=answer,
                category=category,
                is_active=is_active,
                sort_order=sort_order,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            session.commit()
            return self._faq_row_to_dict(row)

    def delete_faq(self, faq_id: int) -> bool:
        with self._session() as session:
            result = session.execute(
                delete(ChatbotFAQRow).where(ChatbotFAQRow.id == faq_id)
            )
            session.commit()
            return result.rowcount > 0

    def update_faq_embedding(self, faq_id: int, embedding: list[float]) -> None:
        """将 embedding 序列化为 JSON 存入 question_embedding

        为什么存 DB 而非 ChromaDB：FAQ 量小（<1000），DB 查询 + 应用层
        cosine 即可，避免 ChromaDB 双集合管理复杂度（见设计文档 §2.2.3）。
        """
        with self._session() as session:
            session.execute(
                update(ChatbotFAQRow)
                .where(ChatbotFAQRow.id == faq_id)
                .values(
                    question_embedding=json.dumps(embedding),
                    updated_at=_utcnow(),
                )
            )
            session.commit()

    @staticmethod
    def _faq_row_to_dict(row: ChatbotFAQRow) -> dict:
        embedding = None
        if row.question_embedding:
            try:
                embedding = json.loads(row.question_embedding)
            except (json.JSONDecodeError, TypeError):
                embedding = None
        return {
            "id": row.id,
            "question": row.question,
            "answer": row.answer,
            "category": row.category,
            "question_embedding": embedding,
            "is_active": row.is_active,
            "sort_order": row.sort_order,
            "created_at": _serialize_dt(row.created_at),
            "updated_at": _serialize_dt(row.updated_at),
        }

    # ==================== 反馈表（chatbot_feedback）====================

    def add_feedback(
        self,
        session_id: str,
        message_id: str,
        rating: str,
        comment: str | None = None,
        escalate_triggered: int = 0,
    ) -> int:
        """添加反馈记录，返回 feedback id"""
        with self._session() as session:
            row = ChatbotFeedbackRow(
                session_id=session_id,
                message_id=message_id,
                rating=rating,
                comment=comment,
                escalate_triggered=escalate_triggered,
                created_at=_utcnow(),
            )
            session.add(row)
            session.commit()
            return row.id

    def count_recent_negative_feedback(
        self, session_id: str, window_min: int = 30
    ) -> int:
        """统计最近 window_min 分钟内的 negative 反馈数（用于转人工判定）

        转人工判定逻辑：窗口内 negative 数 ≥ escalation.feedback_threshold
        时触发转人工（见设计文档 §6.3）。
        """
        cutoff = _utcnow() - timedelta(minutes=window_min)
        with self._session() as session:
            count = session.scalar(
                select(func.count())
                .select_from(ChatbotFeedbackRow)
                .where(
                    ChatbotFeedbackRow.session_id == session_id,
                    ChatbotFeedbackRow.rating == "negative",
                    ChatbotFeedbackRow.created_at >= cutoff,
                )
            )
            return int(count or 0)

    def get_recent_feedback(self, limit: int = 50) -> list[dict]:
        """获取最近反馈记录（跨会话），按 created_at DESC"""
        with self._session() as session:
            stmt = (
                select(ChatbotFeedbackRow)
                .order_by(ChatbotFeedbackRow.created_at.desc())
                .limit(limit)
            )
            rows = session.execute(stmt).scalars().all()
            return [
                {
                    "id": r.id,
                    "session_id": r.session_id,
                    "message_id": r.message_id,
                    "rating": r.rating,
                    "comment": r.comment,
                    # M6：返回星级与分类，供反馈列表展示
                    "star_rating": r.star_rating,
                    "category": r.category,
                    "escalate_triggered": r.escalate_triggered,
                    "created_at": _serialize_dt(r.created_at),
                }
                for r in rows
            ]

    # ==================== KB 版本表（chatbot_kb_versions）====================

    def create_kb_version(
        self,
        version_id: str,
        snapshot_path: str,
        doc_hash: str,
        build_type: str = "build",
    ) -> dict:
        """创建 KB 版本记录，初始 status='building'，由后续 update_kb_version_status 修正

        初始必须为 building：若为 success，构建过程中前端轮询 /kb/status 会误报
        "构建完成"，且 build_all 异常时不会回滚到 building 状态，导致脏数据。
        """
        now = _utcnow()
        with self._session() as session:
            row = ChatbotKBVersionRow(
                id=version_id,
                snapshot_path=snapshot_path,
                doc_hash=doc_hash,
                build_type=build_type,
                status="building",
                created_at=now,
            )
            session.add(row)
            session.commit()
            return self._kb_version_row_to_dict(row)

    def update_kb_version_status(
        self,
        version_id: str,
        status: str,
        chunk_count: int = 0,
        failed_chunk_count: int = 0,
        build_duration_sec: float | None = None,
        error_message: str | None = None,
    ) -> bool:
        with self._session() as session:
            result = session.execute(
                update(ChatbotKBVersionRow)
                .where(ChatbotKBVersionRow.id == version_id)
                .values(
                    status=status,
                    chunk_count=chunk_count,
                    failed_chunk_count=failed_chunk_count,
                    build_duration_sec=build_duration_sec,
                    error_message=error_message,
                )
            )
            session.commit()
            return result.rowcount > 0

    def list_kb_versions(self, limit: int = 20) -> list[dict]:
        """按 created_at DESC 排序"""
        with self._session() as session:
            stmt = (
                select(ChatbotKBVersionRow)
                .order_by(ChatbotKBVersionRow.created_at.desc())
                .limit(limit)
            )
            rows = session.execute(stmt).scalars().all()
            return [self._kb_version_row_to_dict(r) for r in rows]

    def count_kb_versions(self) -> int:
        """KB 版本总数（M-36 修复：list_kb_versions 的 total 需真实计数支持前端分页）"""
        with self._session() as session:
            stmt = select(func.count(ChatbotKBVersionRow.id))
            return int(session.execute(stmt).scalar() or 0)

    def get_kb_version(self, version_id: str) -> dict | None:
        with self._session() as session:
            row = session.get(ChatbotKBVersionRow, version_id)
            if row is None:
                return None
            return self._kb_version_row_to_dict(row)

    def get_current_kb_version(self) -> dict | None:
        """返回最新的 status=success 的版本

        为什么不用 is_current 标记：db_models 中 ChatbotKBVersionRow 无该字段，
        通过 status=success + created_at DESC 隐式判定当前生效版本。
        """
        with self._session() as session:
            stmt = (
                select(ChatbotKBVersionRow)
                .where(ChatbotKBVersionRow.status == "success")
                .order_by(ChatbotKBVersionRow.created_at.desc())
                .limit(1)
            )
            row = session.execute(stmt).scalars().first()
            if row is None:
                return None
            return self._kb_version_row_to_dict(row)

    def has_building_kb_version(self) -> bool:
        """是否存在 status=building 的版本（供 /kb/status 返回 building 字段）

        build_all/rollback 会先创建 building 版本再更新为终态，
        查询是否存在 building 版本即可判断后台构建是否进行中。
        """
        with self._session() as session:
            stmt = (
                select(func.count(ChatbotKBVersionRow.id))
                .where(ChatbotKBVersionRow.status == "building")
            )
            return int(session.execute(stmt).scalar() or 0) > 0

    @staticmethod
    def _kb_version_row_to_dict(row: ChatbotKBVersionRow) -> dict:
        return {
            "id": row.id,
            "snapshot_path": row.snapshot_path,
            "doc_hash": row.doc_hash,
            "chunk_count": row.chunk_count,
            "failed_chunk_count": row.failed_chunk_count,
            "build_type": row.build_type,
            "status": row.status,
            "build_duration_sec": row.build_duration_sec,
            "error_message": row.error_message,
            "created_at": _serialize_dt(row.created_at),
        }

    # ==================== 配置表（chatbot_config）====================

    def get_config(self, key: str) -> str | None:
        """key 是 UNIQUE 约束而非主键，需 select 查询"""
        with self._session() as session:
            row = session.execute(
                select(ChatbotConfigRow).where(ChatbotConfigRow.key == key)
            ).scalars().first()
            return row.value if row else None

    def set_config(
        self, key: str, value: str, value_type: str = "string"
    ) -> None:
        """upsert：存在则更新，不存在则插入"""
        now = _utcnow()
        with self._session() as session:
            row = session.execute(
                select(ChatbotConfigRow).where(ChatbotConfigRow.key == key)
            ).scalars().first()
            if row is not None:
                row.value = value
                row.value_type = value_type
                row.updated_at = now
            else:
                session.add(
                    ChatbotConfigRow(
                        key=key,
                        value=value,
                        value_type=value_type,
                        updated_at=now,
                    )
                )
            session.commit()

    def get_all_config(self) -> dict[str, str]:
        """返回所有配置的 {key: value} 字典"""
        with self._session() as session:
            rows = session.execute(select(ChatbotConfigRow)).scalars().all()
            return {row.key: row.value for row in rows}

    def _init_default_config(self) -> None:
        """首次启动时插入默认配置（幂等）

        为什么用 4 元组而非 dict：description 字段需同步写入，便于
        Web 配置界面展示字段说明（见设计文档 §2.5）。
        """
        defaults = [
            ("enabled", "true", "bool", "智能客服总开关"),
            ("rag.similarity_threshold", "0.65", "float", "RAG 检索相似度阈值"),
            ("faq.similarity_threshold", "0.85", "float", "FAQ 直接返回阈值"),
            ("faq.confirm_threshold", "0.65", "float", "FAQ 确认阈值"),
            ("escalation.contact", "", "string", "转人工联系方式"),
            ("escalation.feedback_threshold", "2", "int", "转人工点踩阈值"),
        ]
        with self._session() as session:
            for key, value, vtype, desc in defaults:
                exists = session.execute(
                    select(ChatbotConfigRow).where(ChatbotConfigRow.key == key)
                ).scalars().first()
                if exists is None:
                    session.add(
                        ChatbotConfigRow(
                            key=key,
                            value=value,
                            value_type=vtype,
                            description=desc,
                            updated_at=_utcnow(),
                        )
                    )
            session.commit()

    # ==================== 审计日志表（chatbot_audit_logs）====================

    def add_audit_log(
        self,
        action: str,
        target: str,
        old_value_hash: str | None = None,
        new_value_hash: str | None = None,
        source: str = "web",
    ) -> int:
        """记录审计日志（仅存 hash 不存明文，敏感字段保护），返回 audit log id"""
        with self._session() as session:
            row = ChatbotAuditLogRow(
                action=action,
                target=target,
                old_value_hash=old_value_hash,
                new_value_hash=new_value_hash,
                source=source,
                created_at=_utcnow(),
            )
            session.add(row)
            session.commit()
            return row.id

    def list_audit_logs(
        self, action: str | None = None, limit: int = 50
    ) -> list[dict]:
        """按 created_at DESC 排序；action=None 不过滤"""
        with self._session() as session:
            stmt = select(ChatbotAuditLogRow)
            if action is not None:
                stmt = stmt.where(ChatbotAuditLogRow.action == action)
            stmt = stmt.order_by(ChatbotAuditLogRow.created_at.desc()).limit(limit)
            rows = session.execute(stmt).scalars().all()
            return [
                {
                    "id": r.id,
                    "action": r.action,
                    "target": r.target,
                    "old_value_hash": r.old_value_hash,
                    "new_value_hash": r.new_value_hash,
                    "source": r.source,
                    "created_at": _serialize_dt(r.created_at),
                }
                for r in rows
            ]
