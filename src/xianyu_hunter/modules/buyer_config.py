"""Buyer 配置

定义落单流程的可调参数，便于 YAML 配置层覆盖。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BuyerConfig:
    """Buyer 配置

    Attributes:
        click_retry_times: 点击"立即购买"按钮的重试次数
        click_retry_interval: 两次点击之间的退避秒数
        confirm_button_timeout: 等待"提交订单"按钮出现的超时（秒）
        price_tolerance: 拍下价格相对预期价格的允许偏差（0.05 = 5%）
        min_interval_between_orders: 两次落单间的最小间隔（秒），防手抖
    """
    click_retry_times: int = 2
    click_retry_interval: float = 1.0
    confirm_button_timeout: float = 5.0
    price_tolerance: float = 0.05
    min_interval_between_orders: float = 0.0
