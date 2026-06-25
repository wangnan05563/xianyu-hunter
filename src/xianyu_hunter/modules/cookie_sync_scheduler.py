"""Cookie 定时同步调度器

职责：定时检查 Cookie 有效性，过期前自动触发导入流程。
不做具体导入逻辑，委托给 browser_import（离线）或 browser_import_cdp（在线）。

降级策略：
1. 优先尝试离线导入（browser_import.py，支持 v10/DPAPI/明文）
2. 离线失败（v20 或文件锁）则尝试 CDP 导入（需浏览器以调试端口运行）
3. 都失败则记录日志，等待下次重试
4. 连续 3 次失败后降低频率（间隔翻倍，上限 2 小时）
"""
from __future__ import annotations

import logging
import time

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

# 退避上限（秒）= 2 小时
_MAX_BACKOFF_INTERVAL = 7200
# 触发退避的失败次数阈值
_BACKOFF_THRESHOLD = 3


class CookieSyncScheduler:
    """Cookie 定时同步调度器

    使用 APScheduler 的 BackgroundScheduler 独立运行，
    不干扰项目现有的任务调度系统。
    """

    def __init__(
        self,
        cookie_store,
        auto_sync_interval: int = 30,
        expiry_threshold: int = 10,
        cdp_port: int = 9222,
    ) -> None:
        self._cookie_store = cookie_store
        self._base_interval = auto_sync_interval
        self._expiry_threshold = expiry_threshold  # 分钟
        self._cdp_port = cdp_port
        self._consecutive_failures = 0
        self._current_interval = auto_sync_interval
        self._scheduler: BackgroundScheduler | None = None

    def start(self) -> None:
        """启动定时调度"""
        if self._scheduler:
            return
        self._scheduler = BackgroundScheduler(daemon=True)
        self._scheduler.add_job(
            self._run_sync_job,
            "interval",
            minutes=self._current_interval,
            id="cookie_sync",
            replace_existing=True,
        )
        self._scheduler.start()
        logger.info("Cookie 同步调度器已启动，间隔 %d 分钟", self._current_interval)

    def stop(self) -> None:
        """停止定时调度"""
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
            logger.info("Cookie 同步调度器已停止")

    def _run_sync_job(self) -> None:
        """定时任务：检查并同步 Cookie

        1. 检查当前 Cookie 是否即将过期
        2. 若即将过期或无效，触发导入流程
        3. 优先离线导入，失败则降级到 CDP
        4. 全部失败则记录日志
        """
        if not self._should_sync():
            return

        success = self._try_offline_import()
        if not success:
            success = self._try_cdp_import()

        if success:
            self._consecutive_failures = 0
            self._current_interval = self._base_interval
            self._reschedule()
        else:
            self._consecutive_failures += 1
            if self._consecutive_failures >= _BACKOFF_THRESHOLD:
                self._current_interval = min(
                    self._current_interval * 2,
                    _MAX_BACKOFF_INTERVAL,
                )
                self._reschedule()
                logger.warning(
                    "Cookie 同步连续失败 %d 次，间隔调整为 %d 分钟",
                    self._consecutive_failures,
                    self._current_interval,
                )

    def _should_sync(self) -> bool:
        """判断是否需要同步（Cookie 无效或即将过期）"""
        if not self._cookie_store.has_valid_cookies():
            return True
        expiry = self._cookie_store.get_cookie_expiry()
        if expiry is None:
            return True
        # 剩余有效期低于阈值时触发同步
        remaining_min = (expiry - time.time()) / 60
        return remaining_min < self._expiry_threshold

    def _try_offline_import(self) -> bool:
        """尝试离线导入（v10/DPAPI/明文）"""
        try:
            from xianyu_hunter.web.routes.browser_import import _do_import_from_browser
            result = _do_import_from_browser("edge", auto_close=False)
            if result.get("ok") and result.get("imported_count", 0) > 0:
                logger.info("离线导入成功，导入 %d 个 Cookie", result["imported_count"])
                return True
            if result.get("has_v20"):
                logger.info("检测到 v20 加密，降级到 CDP 方式")
            return False
        except Exception as e:
            logger.warning("离线导入异常: %s", e)
            return False

    def _try_cdp_import(self) -> bool:
        """尝试 CDP 导入（需浏览器以调试端口运行）"""
        try:
            from xianyu_hunter.web.routes.browser_import_cdp import (
                _check_cdp_reachable,
                _collect_cookies_via_cdp,
            )
            if not _check_cdp_reachable(self._cdp_port):
                logger.info("CDP 端口不可达，跳过 CDP 导入")
                return False
            cookies = _collect_cookies_via_cdp(self._cdp_port)
            if not cookies:
                return False
            success = self._cookie_store.export_cookies(cookies, method="cdp_sync")
            if success:
                logger.info("CDP 导入成功，导入 %d 个 Cookie", len(cookies))
            return success
        except Exception as e:
            logger.warning("CDP 导入异常: %s", e)
            return False

    def _reschedule(self) -> None:
        """用新间隔重新调度"""
        if not self._scheduler:
            return
        self._scheduler.reschedule_job(
            "cookie_sync",
            trigger="interval",
            minutes=self._current_interval,
        )
