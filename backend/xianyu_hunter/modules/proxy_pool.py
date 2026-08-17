"""P1-2 代理 IP 池

策略：
- 轮询（Round-Robin）：按 last_used_at 升序选择最久未用的 active 代理
- 健康检查：异步检测代理可用性和延迟
- 失败计数：连续失败 N 次自动禁用代理

线程安全：所有操作通过 threading.Lock 保护。
"""
from __future__ import annotations

import threading
import time
from typing import Any

import httpx
from loguru import logger
from sqlalchemy import select, update

from xianyu_hunter.infra.db_models import ProxyRow, _utcnow


# 连续失败阈值：超过此值自动禁用代理
DEFAULT_FAIL_THRESHOLD = 5
# 健康检查超时（秒）
HEALTH_CHECK_TIMEOUT = 10.0
# 健康检查目标 URL（轻量级公开接口）
HEALTH_CHECK_URL = "https://httpbin.org/ip"


class ProxyPool:
    """代理 IP 池

    用法：
        pool = ProxyPool(engine)
        proxy = pool.acquire()  # 获取一个可用代理
        # 使用 proxy 发请求...
        if request_failed:
            pool.report_fail(proxy["id"])
        else:
            pool.report_success(proxy["id"])
    """

    def __init__(self, engine, fail_threshold: int = DEFAULT_FAIL_THRESHOLD) -> None:
        self._engine = engine
        self._lock = threading.Lock()
        self._fail_threshold = fail_threshold

    def _row_to_dict(self, row) -> dict[str, Any]:
        """将 ORM 行转为 dict"""
        return {
            "id": row.id,
            "url": row.url,
            "status": row.status,
            "last_used_at": row.last_used_at,
            "last_check_at": row.last_check_at,
            "use_count": row.use_count,
            "fail_count": row.fail_count,
            "latency_ms": row.latency_ms,
            "note": row.note,
        }

    def list_proxies(self, status: str | None = None) -> list[dict[str, Any]]:
        """列出所有代理"""
        with self._engine.connect() as conn:
            stmt = select(ProxyRow).order_by(ProxyRow.created_at.asc())
            if status:
                stmt = stmt.where(ProxyRow.status == status)
            rows = conn.execute(stmt).all()
            return [self._row_to_dict(r) for r in rows]

    def get_proxy(self, proxy_id: int) -> dict[str, Any] | None:
        """获取单个代理"""
        with self._engine.connect() as conn:
            row = conn.execute(
                select(ProxyRow).where(ProxyRow.id == proxy_id)
            ).first()
            return self._row_to_dict(row) if row else None

    def add_proxy(self, url: str, note: str | None = None) -> dict[str, Any]:
        """添加新代理

        url 格式：http://user:pass@host:port 或 http://host:port
        """
        # 简单 URL 格式校验
        if not url.startswith(("http://", "https://", "socks5://")):
            raise ValueError("代理 URL 必须以 http://、https:// 或 socks5:// 开头")

        with self._engine.begin() as conn:
            existing = conn.execute(
                select(ProxyRow.id).where(ProxyRow.url == url)
            ).first()
            if existing:
                raise ValueError(f"代理 {url} 已存在")
            conn.execute(ProxyRow.__table__.insert().values(
                url=url, status="active", note=note,
            ))
        logger.info(f"[P1-2] 添加代理: {url}")
        return self.get_proxy_by_url(url)

    def get_proxy_by_url(self, url: str) -> dict[str, Any] | None:
        """按 URL 获取代理"""
        with self._engine.connect() as conn:
            row = conn.execute(
                select(ProxyRow).where(ProxyRow.url == url)
            ).first()
            return self._row_to_dict(row) if row else None

    def update_proxy(self, proxy_id: int, **fields) -> dict[str, Any] | None:
        """更新代理字段"""
        allowed = {"url", "status", "note"}
        update_fields = {k: v for k, v in fields.items() if k in allowed}
        if not update_fields:
            return self.get_proxy(proxy_id)

        with self._engine.begin() as conn:
            conn.execute(
                update(ProxyRow).where(ProxyRow.id == proxy_id).values(**update_fields)
            )
        return self.get_proxy(proxy_id)

    def delete_proxy(self, proxy_id: int) -> bool:
        """删除代理"""
        with self._engine.begin() as conn:
            result = conn.execute(
                ProxyRow.__table__.delete().where(ProxyRow.id == proxy_id)
            )
            return (result.rowcount or 0) > 0

    def acquire(self) -> dict[str, Any] | None:
        """获取一个可用代理（轮换调度核心方法）

        策略：按 last_used_at 升序选择最久未用的 active 代理。
        线程安全：通过 Lock 保证多线程并发取代理不冲突。
        """
        with self._lock:
            with self._engine.begin() as conn:
                row = conn.execute(
                    select(ProxyRow)
                    .where(ProxyRow.status == "active")
                    .order_by(ProxyRow.last_used_at.asc().nulls_first())
                    .limit(1)
                ).first()
                if not row:
                    return None
                # 标记已使用
                conn.execute(
                    update(ProxyRow)
                    .where(ProxyRow.id == row.id)
                    .values(last_used_at=_utcnow(), use_count=ProxyRow.use_count + 1)
                )
                return self._row_to_dict(row)

    def report_success(self, proxy_id: int) -> None:
        """报告代理使用成功（重置失败计数）"""
        with self._engine.begin() as conn:
            conn.execute(
                update(ProxyRow)
                .where(ProxyRow.id == proxy_id)
                .values(fail_count=0)
            )

    def report_fail(self, proxy_id: int) -> dict[str, Any] | None:
        """报告代理使用失败

        - 累加 fail_count
        - 超过阈值 → 自动禁用
        """
        with self._engine.begin() as conn:
            row = conn.execute(
                select(ProxyRow.fail_count).where(ProxyRow.id == proxy_id)
            ).first()
            if not row:
                return None
            new_fail = (row[0] or 0) + 1

            if new_fail >= self._fail_threshold:
                conn.execute(
                    update(ProxyRow)
                    .where(ProxyRow.id == proxy_id)
                    .values(fail_count=new_fail, status="disabled")
                )
                logger.warning(f"[P1-2] 代理 {proxy_id} 连续失败 {new_fail} 次，已自动禁用")
            else:
                conn.execute(
                    update(ProxyRow)
                    .where(ProxyRow.id == proxy_id)
                    .values(fail_count=new_fail)
                )
        return self.get_proxy(proxy_id)

    def check_proxy(self, proxy_id: int) -> dict[str, Any]:
        """健康检查单个代理

        通过 httpx 经代理访问 httpbin.org/ip 检测可用性和延迟。
        """
        proxy = self.get_proxy(proxy_id)
        if not proxy:
            raise ValueError(f"代理 {proxy_id} 不存在")

        url = proxy["url"]
        start = time.monotonic()
        try:
            with httpx.Client(proxy=url, timeout=HEALTH_CHECK_TIMEOUT) as client:
                resp = client.get(HEALTH_CHECK_URL)
                latency_ms = int((time.monotonic() - start) * 1000)
                ok = resp.status_code == 200
        except (httpx.HTTPError, OSError) as e:
            latency_ms = None
            ok = False
            logger.debug(f"[P1-2] 代理 {url} 健康检查失败: {e}")

        # 更新检查结果
        with self._engine.begin() as conn:
            if ok:
                conn.execute(
                    update(ProxyRow)
                    .where(ProxyRow.id == proxy_id)
                    .values(
                        last_check_at=_utcnow(),
                        latency_ms=latency_ms,
                        fail_count=0,
                        status="active",
                    )
                )
            else:
                conn.execute(
                    update(ProxyRow)
                    .where(ProxyRow.id == proxy_id)
                    .values(
                        last_check_at=_utcnow(),
                        fail_count=ProxyRow.fail_count + 1,
                    )
                )
                # 检查是否需要自动禁用
                updated = self.get_proxy(proxy_id)
                if updated and updated["fail_count"] >= self._fail_threshold:
                    with self._engine.begin() as conn:
                        conn.execute(
                            update(ProxyRow)
                            .where(ProxyRow.id == proxy_id)
                            .values(status="disabled")
                        )

        return {
            "proxy_id": proxy_id,
            "url": url,
            "healthy": ok,
            "latency_ms": latency_ms,
        }

    def check_all(self) -> list[dict[str, Any]]:
        """批量健康检查所有 active 代理"""
        proxies = self.list_proxies(status="active")
        results: list[dict[str, Any]] = []
        for p in proxies:
            try:
                result = self.check_proxy(p["id"])
                results.append(result)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[P1-2] 代理 {p['id']} 检查异常: {e}")
                results.append({
                    "proxy_id": p["id"],
                    "url": p["url"],
                    "healthy": False,
                    "latency_ms": None,
                    "error": str(e),
                })
        return results

    def get_stats(self) -> dict[str, Any]:
        """获取代理池统计信息"""
        with self._engine.connect() as conn:
            rows = conn.execute(select(ProxyRow)).all()
            total = len(rows)
            active = sum(1 for r in rows if r.status == "active")
            disabled = sum(1 for r in rows if r.status == "disabled")
            avg_latency = None
            latencies = [r.latency_ms for r in rows if r.latency_ms is not None]
            if latencies:
                avg_latency = round(sum(latencies) / len(latencies))
            return {
                "total": total,
                "active": active,
                "disabled": disabled,
                "avg_latency_ms": avg_latency,
            }
