"""钉钉通知端到端实测脚本

用 config.yaml 中的真实钉钉凭据发送一条测试消息，验证修复后的完整链路。
执行：python scripts/test_dingtalk_e2e.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# 确保能 import xianyu_hunter
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from xianyu_hunter.domain.events import Event, EventType
from xianyu_hunter.infra.yaml_config import get_config
from xianyu_hunter.modules.notifier.dingtalk import DingTalkNotifier
from xianyu_hunter.modules.notifier.hub import NotifierHub


async def main() -> int:
    cfg = get_config()
    print(f"[1] config.yaml 中 dingtalk 渠道开关: {cfg.notifier.channels.dingtalk}")
    print(f"[2] config.yaml 中 dingtalk_webhook: {cfg.dingtalk_webhook[:60]}...")
    print(f"[3] config.yaml 中 dingtalk_secret: {cfg.dingtalk_secret[:20]}...")

    if not cfg.notifier.channels.dingtalk:
        print("✗ config.yaml 中 notifier.channels.dingtalk=false，请先开启")
        return 1
    if not cfg.dingtalk_webhook:
        print("✗ config.yaml 中 dingtalk_webhook 为空")
        return 1

    # 用 yaml 明文凭据创建 notifier（模拟修复后的 wire_notifier 行为）
    yaml_credentials = {
        "dingtalk": {
            "webhook_url": cfg.dingtalk_webhook,
            "secret": cfg.dingtalk_secret,
        }
    }
    hub = NotifierHub(
        channels=["dingtalk"],
        yaml_credentials=yaml_credentials,
        warn_unconfigured=False,
    )

    if not hub.notifiers:
        print("✗ NotifierHub 未创建任何 dingtalk notifier（is_configured=False）")
        return 1

    notifier = hub.notifiers[0]
    print(f"[4] NotifierHub 创建 dingtalk notifier 成功: is_configured={notifier.is_configured}")
    print(f"[5] webhook_url: {notifier.webhook_url[:60]}...")
    print(f"[6] secret 长度: {len(notifier.secret)} 字符")

    # 构造 EVAL_PASSED 测试事件（用真实场景的完整字段，验证钉钉 markdown 优化格式）
    test_event = Event(
        type=EventType.EVAL_PASSED,
        task_id="__e2e_test__",
        item_id="1054694143770",
        payload={
            "item_id": "1054694143770",
            "item_title": "联想原装内存条，32G DDR4 3200频率，性能稳定，兼容性好",
            "item_price": 760.0,
            "score": 89,
            "risk_level": "low",
            "seller_nick": "无忧电脑买无忧",
            "region": "昆明",
            "data_quality": "full",
            "reject_reasons": [
                "on_sale 9 (ded=1)",
                "dealer:image_theft(sellers=6,sample=10506087,85381285,1921953405)",
                "credit_score 98 moderate",
            ],
            "thumb_url": "https://img.alicdn.com/bao/uploaded/i2/2254757204/O1CN01C6Wm9U235UP0CFdw8_!!4611686018427387220-53-xy_item.heic_Q90.jpg_.webp",
            "url": "https://www.goofish.com/item?id=1054694143770",
        },
    )

    print("[7] 发送 EVAL_PASSED 测试事件到钉钉...")
    # 打印实际发送的 payload 方便核对
    from xianyu_hunter.modules.notifier.templates import render
    title, body = render(test_event)
    print("=" * 60)
    print("【消息 - actionCard（单条）】")
    print("title:", title)
    print("body:")
    print(body)
    print()
    print("说明：钉钉 webhook 不支持 image 类型（官方限制），公共图床国内几乎都不可用。")
    print("      商品图作为 markdown 链接嵌入正文末尾（点击在新窗口打开原图）。")
    print("=" * 60)
    try:
        result = await hub.send(test_event)
    except Exception as e:
        print(f"✗ 发送异常: {type(e).__name__}: {e}")
        return 1

    for r in result:
        status = "✓ 成功" if r.success else "✗ 失败"
        print(f"[8] {status} channel={r.channel} attempts={r.attempts}")
        if r.response:
            print(f"    response: {r.response[:200]}")
        if r.error:
            print(f"    error: {r.error[:200]}")

    # 任一渠道成功即视为通过
    return 0 if any(r.success for r in result) else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
