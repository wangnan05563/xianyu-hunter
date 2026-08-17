"""领域模型：评估结果"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class RiskLevel(str, Enum):
    """风险等级（设计文档 §4.4）"""
    LOW = "low"            # >= 80
    MEDIUM = "medium"      # 60-80
    HIGH = "high"          # 40-60
    EXTREME = "extreme"    # < 40 或一票否决
    UNKNOWN = "unknown"    # 数据不足，无法评估


@dataclass
class EvalResult:
    """卖家评估结果

    输出 4 维细分分 + 加权总分 + 风险等级 + 拒绝原因。
    """
    score: int | None = None                               # 0~100 或 None（数据不足）
    risk_level: RiskLevel = RiskLevel.UNKNOWN
    dimension_scores: dict[str, int] = field(default_factory=dict)
    reject_reasons: list[str] = field(default_factory=list)
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    data_quality: str = "full"                              # full / partial / insufficient

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "risk_level": self.risk_level.value,
            "dimension_scores": self.dimension_scores,
            "reject_reasons": self.reject_reasons,
            "evaluated_at": self.evaluated_at.isoformat(),
            "data_quality": self.data_quality,
        }

    @property
    def is_passed(self) -> bool:
        """是否通过基本门槛（score >= 60）

        用于推送通知门槛。硬编码 60 作为保底默认值，
        具体阈值由调用方通过 should_pass() 传入。
        """
        if self.score is None or self.risk_level == RiskLevel.UNKNOWN:
            return False
        return self.score >= 60 and self.risk_level != RiskLevel.EXTREME

    def should_pass(self, pass_score: int = 60) -> bool:
        """是否通过推送门槛（可自定义阈值）

        为什么需要独立方法：property 无法接收参数，而 pass_score
        需要从配置读取以支持热更新，故提供此方法供 worker 调用。
        """
        if self.score is None or self.risk_level == RiskLevel.UNKNOWN:
            return False
        return self.score >= pass_score and self.risk_level != RiskLevel.EXTREME

    @property
    def is_auto_buy(self) -> bool:
        """是否允许全自动拍下（score >= 80 且低风险）

        硬编码 80 作为保底默认值，具体阈值由调用方通过
        should_auto_buy() 传入配置中的 auto_buy_score。
        """
        if self.score is None or self.risk_level == RiskLevel.UNKNOWN:
            return False
        return self.score >= 80 and self.risk_level == RiskLevel.LOW

    def should_auto_buy(self, auto_buy_score: int = 80) -> bool:
        """是否允许全自动拍下（可自定义阈值）

        为什么需要独立方法：auto_buy_score 需从配置读取（默认 75，
        见 config.yaml），property 无法传参，故提供此方法。
        风险等级需为 LOW（由 evaluator._score_to_risk 根据
        auto_buy_score 划分），确保高风商品不会被自动拍下。
        """
        if self.score is None or self.risk_level == RiskLevel.UNKNOWN:
            return False
        return self.score >= auto_buy_score and self.risk_level == RiskLevel.LOW
