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
        max_orders_per_day: UTC 自然日内最多真实落单次数，0＝不限制
    """
    click_retry_times: int = 2
    click_retry_interval: float = 1.0
    # 闲鱼订单确认页 SPA 加载较慢，5 秒在弱网/高负载下不够
    confirm_button_timeout: float = 10.0
    price_tolerance: float = 0.05
    min_interval_between_orders: float = 0.0
    # FR-A-4（T02589）：UI 曾宣称此护栏「在 buyer_config.py 中配置」，实际字段与逻辑都不存在。
    # 默认 0＝不限制，避免给未经同意的刹车；真实执行逻辑见 Buyer.buy()
    max_orders_per_day: int = 0
