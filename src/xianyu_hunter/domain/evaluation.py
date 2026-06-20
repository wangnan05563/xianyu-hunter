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
        """是否通过基本门槛（score >= 60）"""
        if self.score is None or self.risk_level == RiskLevel.UNKNOWN:
            return False
        return self.score >= 60 and self.risk_level != RiskLevel.EXTREME

    @property
    def is_auto_buy(self) -> bool:
        """是否允许全自动拍下（score >= 80 且低风险）"""
        if self.score is None or self.risk_level == RiskLevel.UNKNOWN:
            return False
        return self.score >= 80 and self.risk_level == RiskLevel.LOW
