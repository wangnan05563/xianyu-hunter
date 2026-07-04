"""推送模板渲染

支持事件类型：
- EVAL_PASSED: 评估通过，提示用户拍下
- BUY_SUCCEEDED: 已拍下未支付，提示用户尽快支付
- TASK_ERROR: 任务异常（如自动采集暂停），告警用户排查

每种事件返回 (title, body)：
- title: 简短一行（Server酱/PushPlus 用于消息标题）
- body: Markdown 详细（Server酱/PushPlus 支持，Bark 退化为纯文本）

为什么兼容两种 payload 格式：
- worker._publish_eval_passed_event 传扁平字段（item_title/item_price/...）
- buyer._publish_buy_succeeded 也用扁平字段
- 历史代码曾用 item 子对象，已被废弃但测试 fixture 仍可能保留
- 模板用 _get() 兼容两种来源，避免老 payload 渲染出 "(无标题) ¥0"
"""
from __future__ import annotations

from xianyu_hunter.domain.events import Event, EventType
from xianyu_hunter.domain.evaluation import RiskLevel

# 模板分隔线
SEP = "\n\n---\n"

# 闲鱼商品详情页 URL 模板：item_id 拼接即用
# 为什么硬编码 goofish 域名：与前端 Evaluations/index.tsx 标题列点击行为一致
GOOFISH_ITEM_URL = "https://www.goofish.com/item?id={item_id}"


def _get(payload: dict, key: str, item: dict | None, default=None):
    """优先从 payload 顶层取值，回退到 item 子对象，再回退到 default

    为什么需要：worker/buyer 传扁平字段（item_title），但早期代码用 item.title。
    顶层优先保证新代码路径正确，item 兜底兼容历史 fixture。
    """
    if key in payload:
        return payload[key]
    if item and key in item:
        return item[key]
    return default


def _format_price(price) -> str:
    """格式化价格：None/空/0/非数值显示 '—'，否则显示 ¥X.XX

    为什么 0 也视为无价格：闲鱼商品几乎不存在 0 元真实成交，
    0 通常是采集失败/字段缺失的占位值，显示 ¥0.00 会误导用户
    """
    if price is None or price == "" or price == 0:
        return "—"
    try:
        p = float(price)
        return f"¥{p:.2f}" if p > 0 else "—"
    except (TypeError, ValueError):
        return "—"


def _format_title(title: str | None, item_id: str | None) -> str:
    """标题格式化：空标题回退到商品 ID（短截），再无则 '商品'"""
    if title and title.strip():
        return title.strip()[:30]
    if item_id:
        return f"商品 {item_id[:12]}"
    return "商品"


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
    """评估通过模板

    兼容两种 payload：
    - 扁平格式（worker 推荐）：item_title / item_price / seller_nick / ...
    - item 子对象格式（历史兼容）：item.title / item.price / ...
    """
    p = event.payload or {}
    item = p.get("item") if isinstance(p.get("item"), dict) else {}
    item_id = _get(p, "item_id", item, "") or (event.item_id or "")
    title = _get(p, "item_title", item, "") or _get(p, "title", item, "")
    price = _get(p, "item_price", item, 0)
    if price in (0, None, ""):
        # 兜底：扁平用 item_price，子对象用 price，二者都空时再回退 0
        price = _get(p, "price", item, 0)
    score = p.get("score", 0)
    risk_level = p.get("risk_level", RiskLevel.MEDIUM.value)
    seller_nick = _get(p, "seller_nick", item, "")
    thumb = _get(p, "thumb_url", item, "")
    url = _get(p, "url", item, "") or (GOOFISH_ITEM_URL.format(item_id=item_id) if item_id else "")
    reasons = p.get("reject_reasons", []) or []
    data_quality = p.get("data_quality", "")
    region = _get(p, "region", item, "")

    display_title = _format_title(title, item_id)
    price_str = _format_price(price)
    head = f"[闲鱼捡漏] {display_title} {price_str}"

    body_lines = ["### 评估通过 ✅"]
    if item_id:
        body_lines.append(f"- 商品ID：`{item_id}`")
    if seller_nick:
        body_lines.append(f"- 卖家：{seller_nick}")
    if region:
        body_lines.append(f"- 地区：{region}")
    body_lines.append(f"- 评分：**{score}** / 风险等级：**{risk_level}**")
    if data_quality:
        body_lines.append(f"- 数据质量：{data_quality}")
    body_lines.append(f"- 价格：{price_str}")
    if reasons:
        body_lines.append(f"- 风险项：{', '.join(reasons[:3])}")
    if thumb:
        body_lines.append(f"\n![商品图]({thumb})")
    if url:
        body_lines.append(f"\n[立即查看 →]({url})")
    body_lines.append(SEP + "_系统自动发送，请尽快确认_")
    return head, "\n".join(line for line in body_lines if line)


def _order_placed(event: Event) -> tuple[str, str]:
    """已拍下模板

    兼容扁平 / item 子对象两种 payload 格式（见 _eval_passed 注释）
    """
    p = event.payload or {}
    item = p.get("item") if isinstance(p.get("item"), dict) else {}
    item_id = _get(p, "item_id", item, "") or (event.item_id or "")
    title = _get(p, "item_title", item, "") or _get(p, "title", item, "")
    price = _get(p, "item_price", item, 0)
    if price in (0, None, ""):
        price = _get(p, "price", item, 0)
    order_id = p.get("order_id", "")
    expire_at = p.get("expire_at", "")

    display_title = _format_title(title, item_id)
    price_str = _format_price(price)
    head = f"[已拍下] {display_title} {price_str}"
    body_lines = [
        "### 已拍下未支付 ⏰",
        f"- 商品ID：`{item_id}`" if item_id else "",
        f"- 订单号：`{order_id}`" if order_id else "",
        f"- 金额：{price_str}",
        f"- 过期时间：{expire_at}" if expire_at else "",
        "\n请打开闲鱼 App 在 **5 分钟内** 完成支付，否则订单自动释放。",
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
        "### ⚠️ 任务异常",
        f"- 任务：`{event.task_id}`" if event.task_id else "",
        f"- 详情：{message}" if message else "",
        f"- 原因：`{reason}`" if reason else "",
        "\n请尽快检查任务状态和 Cookie 有效性。",
    ]
    return head, "\n".join(line for line in body_lines if line)


def _generic(event: Event) -> tuple[str, str]:
    """通用降级模板"""
    return (
        f"[XianyuHunter] {event.type.value}",
        f"事件：{event.type.value}\n时间：{event.timestamp.isoformat()}\n载荷：{event.payload}",
    )
