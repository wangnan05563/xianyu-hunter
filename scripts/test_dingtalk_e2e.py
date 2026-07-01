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

    # 构造 EVAL_PASSED 测试事件
    test_event = Event(
        type=EventType.EVAL_PASSED,
        task_id="__e2e_test__",
        item_id="__e2e_item__",
        payload={
            "item_title": "[E2E测试] 钉钉通知修复验证",
            "item_price": 999,
            "score": 75,
            "risk_level": "medium",
            "is_passed": True,
        },
    )

    print("[7] 发送 EVAL_PASSED 测试事件到钉钉...")
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
