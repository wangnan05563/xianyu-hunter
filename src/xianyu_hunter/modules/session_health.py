"""会话健康检查器（设计文档 §4.9）

核心问题：现有方案仅在请求失败时才发现会话失效，无主动检测。

解决方案：定期主动探测 + 多维度健康评分。

检查维度：
1. Cookie 有效性 — _m_h5_tk 是否存在且未过期，identity 层 Cookie 是否完整
2. API 可达性 — 调用 getTimestamp 接口，检查是否返回正常
3. 页面可达性 — 访问 /personal，检查是否重定向到登录页
4. 风控状态 — 检查 LocalStorage 中 baxia 配置，检查最近失败率

健康评分 0-100：
- 80-100: 健康，无需操作
- 60-80:  需续期 token
- 40-60:  需重新登录
- < 40:   暂停 + 通知用户
"""
from __future__ import annotations

import inspect
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable

from xianyu_hunter.infra.logger import get_logger

logger = get_logger()


class HealthAction(str, Enum):
    """健康检查后的建议动作"""
    NONE = "none"               # 无需操作
    RENEW_TOKEN = "renew_token" # 续期 token
    RELOGIN = "relogin"         # 重新登录
    PAUSE = "pause"             # 暂停 + 通知


class WAFStatus(str, Enum):
    """风控状态"""
    CLEAR = "clear"       # 正常
    WARNING = "warning"   # 警告（有失败但未熔断）
    BLOCKED = "blocked"   # 已熔断


@dataclass
class HealthReport:
    """健康检查报告"""
    score: int                          # 0-100
    cookie_valid: bool
    api_reachable: bool
    page_accessible: bool
    waf_status: WAFStatus
    action: HealthAction
    details: dict[str, Any] = field(default_factory=dict)
    checked_at: float = field(default_factory=time.time)

    @property
    def is_healthy(self) -> bool:
        """是否健康（score >= 80）"""
        return self.score >= 80

    @property
    def needs_attention(self) -> bool:
        """需要关注（score < 60）"""
        return self.score < 60

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "cookie_valid": self.cookie_valid,
            "api_reachable": self.api_reachable,
            "page_accessible": self.page_accessible,
            "waf_status": self.waf_status.value,
            "action": self.action.value,
            "is_healthy": self.is_healthy,
            "needs_attention": self.needs_attention,
            "details": self.details,
            "checked_at": self.checked_at,
        }


class SessionHealthChecker:
    """会话健康检查器

    使用方式：
        checker = SessionHealthChecker()
        checker.set_cookie_checker(my_cookie_checker)
        checker.set_api_checker(my_api_checker)
        checker.set_page_checker(my_page_checker)
        checker.set_waf_status_provider(lambda: WAFStatus.CLEAR)

        report = await checker.check()
        if report.needs_attention:
            print(f"会话不健康: score={report.score}, action={report.action}")
    """

    # 检查间隔（秒）
    CHECK_INTERVAL = 300  # 5 分钟

    # 各维度权重（总和=100）
    WEIGHT_COOKIE = 40
    WEIGHT_API = 30
    WEIGHT_PAGE = 20
    WEIGHT_WAF = 10

    # 评分阈值
    SCORE_RENEW_THRESHOLD = 80    # < 80 需续期
    SCORE_RELOGIN_THRESHOLD = 60  # < 60 需重新登录
    SCORE_PAUSE_THRESHOLD = 40    # < 40 需暂停

    def __init__(self):
        # 兼容同步与异步检查器：浏览器内存兜底等场景需要 async 读取 cookie，
        # 因此允许 checker 返回 bool 或 Awaitable[bool]
        self._cookie_checker: Callable[[], bool | Awaitable[bool]] | None = None
        self._api_checker: Callable[[], Awaitable[bool]] | None = None
        self._page_checker: Callable[[], Awaitable[bool]] | None = None
        self._waf_provider: Callable[[], WAFStatus] | None = None
        self._last_report: HealthReport | None = None
        self._check_count = 0

    # ============== 配置 ==============

    def set_cookie_checker(self, checker: Callable[[str | None], bool | Awaitable[bool]]) -> None:
        """设置 Cookie 有效性检查器

        checker 可以是同步或异步函数，接受可选 user_id 参数（多用户隔离），
        返回 True 表示 Cookie 有效。
        为什么支持异步：cookie_checker 需要从浏览器内存读取 cookie 做兜底复核，
        而浏览器内存读取是 async 操作。
        为什么传 user_id：不同用户 cookie 文件隔离（cookies_{user_id}.json），
        硬编码 default 会导致多用户场景与导航栏状态矛盾（meta-rule #96）。
        """
        self._cookie_checker = checker

    def set_api_checker(self, checker: Callable[[], Awaitable[bool]]) -> None:
        """设置 API 可达性检查器

        checker 应是异步函数，返回 True 表示 API 可达
        """
        self._api_checker = checker

    def set_page_checker(self, checker: Callable[[], Awaitable[bool]]) -> None:
        """设置页面可达性检查器

        checker 应是异步函数，返回 True 表示页面可访问（未重定向到登录页）
        """
        self._page_checker = checker

    def set_waf_status_provider(self, provider: Callable[[], WAFStatus]) -> None:
        """设置风控状态提供器"""
        self._waf_provider = provider

    # ============== 核心检查 ==============

    async def check(self, user_id: str | None = None) -> HealthReport:
        """执行多维度健康检查

        按权重计算总分，返回建议动作。

        Args:
            user_id: 目标用户标识，透传给 cookie_checker 实现多用户隔离。
                None 时 checker 自行退化为 default（单用户/管理令牌场景）。
        """
        self._check_count += 1
        details: dict[str, Any] = {}

        # 1. Cookie 有效性（权重 40）
        cookie_valid = await self._check_cookies(user_id)
        details["cookie_valid"] = cookie_valid
        cookie_score = self.WEIGHT_COOKIE if cookie_valid else 0

        # 2. API 可达性（权重 30）
        api_reachable = await self._check_api()
        details["api_reachable"] = api_reachable
        api_score = self.WEIGHT_API if api_reachable else 0

        # 3. 页面可达性（权重 20）
        page_accessible = await self._check_page()
        details["page_accessible"] = page_accessible
        page_score = self.WEIGHT_PAGE if page_accessible else 0

        # 4. 风控状态（权重 10）
        waf_status = self._get_waf_status()
        details["waf_status"] = waf_status.value
        waf_score = {
            WAFStatus.CLEAR: self.WEIGHT_WAF,
            WAFStatus.WARNING: self.WEIGHT_WAF // 2,
            WAFStatus.BLOCKED: 0,
        }[waf_status]

        # 计算总分
        total_score = cookie_score + api_score + page_score + waf_score
        details["scores"] = {
            "cookie": cookie_score,
            "api": api_score,
            "page": page_score,
            "waf": waf_score,
            "total": total_score,
        }

        # 确定建议动作
        if total_score >= self.SCORE_RENEW_THRESHOLD:
            action = HealthAction.NONE
        elif total_score >= self.SCORE_RELOGIN_THRESHOLD:
            # 60-80: 可能 token 过期，先续期
            action = HealthAction.RENEW_TOKEN if not cookie_valid else HealthAction.NONE
        elif total_score >= self.SCORE_PAUSE_THRESHOLD:
            # 40-60: 需重新登录
            action = HealthAction.RELOGIN
        else:
            # < 40: 暂停
            action = HealthAction.PAUSE

        report = HealthReport(
            score=total_score,
            cookie_valid=cookie_valid,
            api_reachable=api_reachable,
            page_accessible=page_accessible,
            waf_status=waf_status,
            action=action,
            details=details,
        )

        self._last_report = report
        logger.info(
            f"健康检查完成: score={total_score}, cookie={cookie_valid}, api={api_reachable}, page={page_accessible}, waf={waf_status.value}, action={action.value}",
        )
        return report

    # ============== 内部检查方法 ==============

    async def _check_cookies(self, user_id: str | None = None) -> bool:
        """检查 Cookie 有效性

        Args:
            user_id: 透传给 cookie_checker，实现多用户隔离（与导航栏读取同一文件）。

        兼容性：cookie_checker 可能为旧式无参签名（测试/历史调用）或新式接受
        user_id 的签名，按参数数量自适应调用，避免破坏既有调用方与测试。
        """
        if not self._cookie_checker:
            return True  # 未设置检查器，默认有效
        try:
            # 按签名参数数量自适应：无参 checker（lambda: True）不传 user_id，
            # 新式 checker（接受 user_id）透传以实现多用户隔离
            if len(inspect.signature(self._cookie_checker).parameters) == 0:
                result = self._cookie_checker()
            else:
                result = self._cookie_checker(user_id)
            # 兼容 async 检查器：浏览器内存兜底等场景需要异步读取 cookie
            if inspect.isawaitable(result):
                result = await result
            return result
        except TypeError:
            # 兜底：旧式无参 checker 在被传入 user_id 时报错，重试无参调用
            try:
                result = self._cookie_checker()
                if inspect.isawaitable(result):
                    result = await result
                return result
            except Exception as e:  # noqa: BLE001
                logger.error(f"Cookie 检查异常: {e}")
                return False
        except Exception as e:  # noqa: BLE001
            logger.error(f"Cookie 检查异常: {e}")
            return False

    async def _check_api(self) -> bool:
        """检查 API 可达性"""
        if not self._api_checker:
            return True  # 未设置检查器，默认可达
        try:
            return await self._api_checker()
        except Exception as e:
            logger.error(f"API 检查异常: {e}")
            return False

    async def _check_page(self) -> bool:
        """检查页面可达性"""
        if not self._page_checker:
            return True  # 未设置检查器，默认可达
        try:
            return await self._page_checker()
        except Exception as e:
            logger.error(f"页面检查异常: {e}")
            return False

    def _get_waf_status(self) -> WAFStatus:
        """获取风控状态"""
        if not self._waf_provider:
            return WAFStatus.CLEAR  # 未设置，默认正常
        try:
            return self._waf_provider()
        except Exception as e:
            logger.error(f"WAF 状态获取异常: {e}")
            return WAFStatus.WARNING

    # ============== 状态查询 ==============

    def get_last_report(self) -> HealthReport | None:
        """获取最近一次检查报告"""
        return self._last_report

    def get_check_count(self) -> int:
        """获取检查次数"""
        return self._check_count

    @property
    def weights(self) -> dict[str, int]:
        """获取各维度权重"""
        return {
            "cookie": self.WEIGHT_COOKIE,
            "api": self.WEIGHT_API,
            "page": self.WEIGHT_PAGE,
            "waf": self.WEIGHT_WAF,
        }
