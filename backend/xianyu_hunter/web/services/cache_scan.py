"""缓存目录增量扫描（T02738）

实测：浏览器 profile 2073 个文件 / 426 MB，在磁盘争用（并发 build/测试）下单次
全量遍历跑了 449.5s。把遍历直接放在请求线程里，前端 30s 超时必然 abort，用户看到
失败而扫描仍在继续。

这里把遍历切成「可续跑的批次」：每次调用最多消耗 budget 秒，进度与累计值留在
进程内状态里。调用方（/status 缓存未命中、/cache-scan 轮询、清理预览）都能在
秒级返回「统计中 x 项」，下一次调用从断点继续，不会重复计数。

时间片只在目录之间检查：单个目录必须完整走完，否则半个目录的条目会被重复统计。
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_BUDGET_SEC = 1.0
DEFAULT_TTL_SEC = 300.0


@dataclass
class _Scan:
    stack: list[str]
    total_bytes: int = 0
    files: int = 0
    scanned_entries: int = 0
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None

    @property
    def done(self) -> bool:
        return self.finished_at is not None


class CacheScanService:
    """按路径维护可续跑的目录统计

    同一路径并发请求共用一份进度（互斥锁串行）；完成后结果保留 ttl 秒，
    期内直接复用，过期重新全量扫描。
    """

    def __init__(
        self,
        *,
        budget_sec: float = DEFAULT_BUDGET_SEC,
        ttl_sec: float = DEFAULT_TTL_SEC,
    ) -> None:
        self._lock = threading.RLock()
        self._scans: dict[str, _Scan] = {}
        self._budget = budget_sec
        self._ttl = ttl_sec

    def snapshot(
        self,
        path: Path,
        *,
        budget: float | None = None,
        advance: bool = True,
    ) -> dict:
        """返回统计快照；advance=True 时先按预算推进扫描（非阻塞边界是预算本身）"""
        key = str(path)
        with self._lock:
            scan = self._scans.get(key)
            stale = (
                scan is not None
                and scan.done
                and time.time() - (scan.finished_at or 0) > self._ttl
            )
            if scan is None or stale:
                scan = _Scan(stack=[key])
                self._scans[key] = scan
            if advance and not scan.done:
                self._advance(scan, self._budget if budget is None else budget)
            return self._describe(key, scan)

    def invalidate(self, path: Path) -> None:
        """清理/删除后丢弃结果，下一次查询重新统计"""
        with self._lock:
            self._scans.pop(str(path), None)

    def _advance(self, scan: _Scan, budget: float) -> None:
        deadline = time.monotonic() + max(budget, 0.0)
        while scan.stack:
            if time.monotonic() >= deadline:
                return
            current = scan.stack.pop()
            try:
                with os.scandir(current) as entries:
                    for entry in entries:
                        scan.scanned_entries += 1
                        try:
                            if entry.is_dir(follow_symlinks=False):
                                scan.stack.append(entry.path)
                            elif entry.is_file(follow_symlinks=False):
                                scan.total_bytes += entry.stat(follow_symlinks=False).st_size
                                scan.files += 1
                        except OSError:
                            continue
            except OSError:
                continue
        scan.finished_at = time.time()

    @staticmethod
    def _describe(key: str, scan: _Scan) -> dict:
        finished = scan.finished_at
        return {
            "path": key,
            "state": "done" if scan.done else "scanning",
            "mb": round(scan.total_bytes / 1024 / 1024, 2),
            "files": scan.files,
            "scanned_entries": scan.scanned_entries,
            "elapsed_sec": round((finished or time.time()) - scan.started_at, 1),
        }
