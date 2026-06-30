"""推送模板渲染

支持事件类型：
- EVAL_PASSED: 评估通过，提示用户拍下
- BUY_SUCCEEDED: 已拍下未支付，提示用户尽快支付
- TASK_ERROR: 任务异常（如自动采集暂停），告警用户排查

每种事件返回 (title, body)：
- title: 简短一行（Server酱/PushPlus 用于消息标题）
- body: Markdown 详细（Server酱/PushPlus 支持，Bark 退化为纯文本）
"""
from __future__ import annotations

from xianyu_hunter.domain.events import Event, EventType
from xianyu_hunter.domain.evaluation import RiskLevel

# 模板分隔线
SEP = "\n\n---\n"


def render(event: Event) -> tuple[str, str]:
    """根据事件类型路由到具体模板

    Returns: (title, body)
    """
    if event.type == EventType.EVAL_PASSED:
        return _eval_passed(event)
    if event.type == EventType.BUY_SUCCEEDED:
        return _order_placed(event)
    if event.type == EventType.TASK_ERROR:
        return _task_error(event)
    # 未支持的事件：退化为通用提示
    return _generic(event)


def _eval_passed(event: Event) -> tuple[str, str]:
    """评估通过模板"""
    p = event.payload
    item = p.get("item", {})
    title = item.get("title", "(无标题)")
    price = item.get("price", 0)
    score = p.get("score", 0)
    risk_level = p.get("risk_level", RiskLevel.MEDIUM.value)
    url = item.get("url", "")
    thumb = item.get("thumb_url", "")
    seller_nick = p.get("seller_nick", "")
    reasons = p.get("reject_reasons", [])

    head = f"[闲鱼捡漏] {title[:30]} ¥{price}"
    body_lines = [
        f"### 评估通过 ✅",
        f"- 卖家：{seller_nick}" if seller_nick else "",
        f"- 评分：**{score}** / 风险等级：**{risk_level}**",
        f"- 价格：¥{price}",
    ]
    if reasons:
        body_lines.append(f"- 风险项：{', '.join(reasons[:3])}")
    if thumb:
        body_lines.append(f"\n![商品图]({thumb})")
    if url:
        body_lines.append(f"\n[立即查看 →]({url})")
    body_lines.append(SEP + "_系统自动发送，请 5 分钟内确认_")
    return head, "\n".join(line for line in body_lines if line)


def _order_placed(event: Event) -> tuple[str, str]:
    """已拍下模板"""
    p = event.payload
    item = p.get("item", {})
    title = item.get("title", "(无标题)")
    price = item.get("price", 0)
    order_id = p.get("order_id", "")
    expire_at = p.get("expire_at", "")

    head = f"[已拍下] {title[:30]} ¥{price}"
    body_lines = [
        f"### 已拍下未支付 ⏰",
        f"- 订单号：`{order_id}`" if order_id else "",
        f"- 金额：¥{price}",
        f"- 过期时间：{expire_at}" if expire_at else "",
        f"\n请打开闲鱼 App 在 **5 分钟内** 完成支付，否则订单自动释放。",
    ]
    return head, "\n".join(line for line in body_lines if line)


def _task_error(event: Event) -> tuple[str, str]:
    """任务异常模板（如自动采集暂停告警）"""
    p = event.payload
    title = p.get("title", "任务异常")
    message = p.get("message", "")
    reason = p.get("reason", "")

    head = f"[告警] {title}"
    body_lines = [
        f"### ⚠️ 任务异常",
        f"- 任务：`{event.task_id}`" if event.task_id else "",
        f"- 详情：{message}" if message else "",
        f"- 原因：`{reason}`" if reason else "",
        f"\n请尽快检查任务状态和 Cookie 有效性。",
    ]
    return head, "\n".join(line for line in body_lines if line)


def _generic(event: Event) -> tuple[str, str]:
    """通用降级模板"""
    return (
        f"[XianyuHunter] {event.type.value}",
        f"事件：{event.type.value}\n时间：{event.timestamp.isoformat()}\n载荷：{event.payload}",
    )
