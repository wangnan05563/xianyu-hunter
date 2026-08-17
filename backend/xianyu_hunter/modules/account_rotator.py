"""P1-2 账号轮换调度器

策略：
- 轮询（Round-Robin）：按 last_used_at 升序选择最久未用的 active 账号
- 冷却机制：账号触发风控后进入 cooldown，冷却时间结束后自动恢复
- 失败计数：连续失败 N 次自动禁用账号

线程安全：所有操作通过 threading.Lock 保护，支持多线程并发取号。
"""
from __future__ import annotations

import json
import threading
from datetime import timedelta
from typing import Any

from loguru import logger
from sqlalchemy import select, update

from xianyu_hunter.infra.db_models import AccountRow, _utcnow


# 默认冷却时间（秒）：触发风控后冷却 30 分钟
DEFAULT_COOLDOWN_SEC = 1800
# 连续失败阈值：超过此值自动禁用账号
DEFAULT_FAIL_THRESHOLD = 5


class AccountRotator:
    """账号轮换调度器

    用法：
        rotator = AccountRotator(engine)
        account = rotator.acquire()  # 获取一个可用账号
        # 使用 account 执行任务...
        if task_failed:
            rotator.report_fail(account["id"])
        else:
            rotator.report_success(account["id"])
    """

    def __init__(self, engine, cooldown_sec: int = DEFAULT_COOLDOWN_SEC,
                 fail_threshold: int = DEFAULT_FAIL_THRESHOLD) -> None:
        self._engine = engine
        self._lock = threading.Lock()
        self._cooldown_sec = cooldown_sec
        self._fail_threshold = fail_threshold

    def _row_to_dict(self, row) -> dict[str, Any]:
        """将 ORM 行转为 dict"""
        return {
            "id": row.id,
            "name": row.name,
            "nickname": row.nickname,
            "cookies": row.cookies,
            "status": row.status,
            "last_used_at": row.last_used_at,
            "cooldown_until": row.cooldown_until,
            "use_count": row.use_count,
            "fail_count": row.fail_count,
            "note": row.note,
        }

    def _recover_expired_cooldowns(self, conn) -> int:
        """恢复已过冷却期的账号（status=cooldown → active）

        返回恢复的账号数。
        """
        now = _utcnow()
        result = conn.execute(
            update(AccountRow)
            .where(
                AccountRow.status == "cooldown",
                AccountRow.cooldown_until.is_not(None),
                AccountRow.cooldown_until <= now,
            )
            .values(status="active", cooldown_until=None, fail_count=0)
        )
        return result.rowcount or 0

    def list_accounts(self, status: str | None = None) -> list[dict[str, Any]]:
        """列出所有账号"""
        with self._engine.connect() as conn:
            self._recover_expired_cooldowns(conn)
            conn.commit()
            stmt = select(AccountRow).order_by(AccountRow.created_at.asc())
            if status:
                stmt = stmt.where(AccountRow.status == status)
            rows = conn.execute(stmt).all()
            return [self._row_to_dict(r) for r in rows]

    def get_account(self, account_id: int) -> dict[str, Any] | None:
        """获取单个账号"""
        with self._engine.connect() as conn:
            row = conn.execute(
                select(AccountRow).where(AccountRow.id == account_id)
            ).first()
            return self._row_to_dict(row) if row else None

    def add_account(self, name: str, nickname: str | None = None,
                    cookies: list[dict] | None = None, note: str | None = None) -> dict[str, Any]:
        """添加新账号

        cookies 为 Cookie 列表（与 cookie_store 格式一致）。
        """
        cookies_json = json.dumps(cookies, ensure_ascii=False) if cookies else None
        with self._engine.begin() as conn:
            # 检查 name 唯一性
            existing = conn.execute(
                select(AccountRow.id).where(AccountRow.name == name)
            ).first()
            if existing:
                raise ValueError(f"账号名 '{name}' 已存在")
            conn.execute(AccountRow.__table__.insert().values(
                name=name, nickname=nickname, cookies=cookies_json,
                status="active", note=note,
            ))
        logger.info(f"[P1-2] 添加账号: {name}")
        # 返回新创建的账号
        return self.get_account_by_name(name)

    def get_account_by_name(self, name: str) -> dict[str, Any] | None:
        """按名称获取账号"""
        with self._engine.connect() as conn:
            row = conn.execute(
                select(AccountRow).where(AccountRow.name == name)
            ).first()
            return self._row_to_dict(row) if row else None

    def update_account(self, account_id: int, **fields) -> dict[str, Any] | None:
        """更新账号字段

        支持的字段：nickname, cookies, status, note
        """
        allowed = {"nickname", "cookies", "status", "note"}
        update_fields = {k: v for k, v in fields.items() if k in allowed}
        if not update_fields:
            return self.get_account(account_id)

        # cookies 特殊处理：list → JSON
        if "cookies" in update_fields and isinstance(update_fields["cookies"], list):
            update_fields["cookies"] = json.dumps(update_fields["cookies"], ensure_ascii=False)

        with self._engine.begin() as conn:
            conn.execute(
                update(AccountRow).where(AccountRow.id == account_id).values(**update_fields)
            )
        return self.get_account(account_id)

    def delete_account(self, account_id: int) -> bool:
        """删除账号"""
        with self._engine.begin() as conn:
            result = conn.execute(
                AccountRow.__table__.delete().where(AccountRow.id == account_id)
            )
            return (result.rowcount or 0) > 0

    def acquire(self, preferred_name: str | None = None) -> dict[str, Any] | None:
        """获取一个可用账号（轮换调度核心方法）

        策略：
        1. 优先恢复已过冷却期的账号
        2. 如果指定 preferred_name，优先返回该账号（若可用）
        3. 否则按 last_used_at 升序选择最久未用的 active 账号
        4. 更新 last_used_at 和 use_count

        线程安全：通过 Lock 保证多线程并发取号不冲突。
        """
        with self._lock:
            with self._engine.begin() as conn:
                # 1. 恢复过期冷却
                self._recover_expired_cooldowns(conn)

                # 2. 优先返回指定账号
                if preferred_name:
                    row = conn.execute(
                        select(AccountRow)
                        .where(AccountRow.name == preferred_name, AccountRow.status == "active")
                        .limit(1)
                    ).first()
                    if row:
                        self._mark_used(conn, row.id)
                        return self._row_to_dict(row)
                    logger.warning(f"[P1-2] 指定账号 {preferred_name} 不可用，回退到轮换")

                # 3. 轮换：按 last_used_at 升序（NULL 视为最早）
                row = conn.execute(
                    select(AccountRow)
                    .where(AccountRow.status == "active")
                    .order_by(AccountRow.last_used_at.asc().nulls_first())
                    .limit(1)
                ).first()
                if not row:
                    return None
                self._mark_used(conn, row.id)
                return self._row_to_dict(row)

    def _mark_used(self, conn, account_id: int) -> None:
        """标记账号已使用（更新 last_used_at 和 use_count）"""
        conn.execute(
            update(AccountRow)
            .where(AccountRow.id == account_id)
            .values(last_used_at=_utcnow(), use_count=AccountRow.use_count + 1)
        )

    def report_success(self, account_id: int) -> None:
        """报告账号使用成功（重置失败计数）"""
        with self._engine.begin() as conn:
            conn.execute(
                update(AccountRow)
                .where(AccountRow.id == account_id)
                .values(fail_count=0)
            )

    def report_fail(self, account_id: int, cooldown_sec: int | None = None) -> dict[str, Any] | None:
        """报告账号使用失败

        - 累加 fail_count
        - 超过阈值 → 自动禁用（status=disabled）
        - 未超阈值 → 进入冷却（status=cooldown）
        """
        cd_sec = cooldown_sec if cooldown_sec is not None else self._cooldown_sec
        with self._engine.begin() as conn:
            # 先读取当前 fail_count
            row = conn.execute(
                select(AccountRow.fail_count).where(AccountRow.id == account_id)
            ).first()
            if not row:
                return None
            new_fail = (row[0] or 0) + 1

            if new_fail >= self._fail_threshold:
                # 超阈值 → 禁用
                conn.execute(
                    update(AccountRow)
                    .where(AccountRow.id == account_id)
                    .values(fail_count=new_fail, status="disabled")
                )
                logger.warning(f"[P1-2] 账号 {account_id} 连续失败 {new_fail} 次，已自动禁用")
            else:
                # 未超阈值 → 冷却
                conn.execute(
                    update(AccountRow)
                    .where(AccountRow.id == account_id)
                    .values(
                        fail_count=new_fail,
                        status="cooldown",
                        cooldown_until=_utcnow() + timedelta(seconds=cd_sec),
                    )
                )
                logger.info(f"[P1-2] 账号 {account_id} 失败 {new_fail} 次，进入冷却 {cd_sec}s")
        return self.get_account(account_id)

    def get_stats(self) -> dict[str, Any]:
        """获取账号池统计信息"""
        with self._engine.connect() as conn:
            self._recover_expired_cooldowns(conn)
            conn.commit()
            rows = conn.execute(select(AccountRow)).all()
            total = len(rows)
            active = sum(1 for r in rows if r.status == "active")
            cooldown = sum(1 for r in rows if r.status == "cooldown")
            disabled = sum(1 for r in rows if r.status == "disabled")
            return {
                "total": total,
                "active": active,
                "cooldown": cooldown,
                "disabled": disabled,
            }
