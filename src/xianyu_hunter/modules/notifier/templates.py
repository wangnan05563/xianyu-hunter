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

import re

from xianyu_hunter.domain.events import Event, EventType
from xianyu_hunter.domain.evaluation import RiskLevel

# 模板分隔线
SEP = "\n\n---\n"

# 闲鱼商品详情页 URL 模板：item_id 拼接即用
# 为什么硬编码 goofish 域名：与前端 Evaluations/index.tsx 标题列点击行为一致
GOOFISH_ITEM_URL = "https://www.goofish.com/item?id={item_id}"

# 钉钉 markdown 消息卡片正文宽度有限（PC 端约 25-30 个汉字宽）
# 标题太长会被强制换行影响视觉，故统一截到 24 字符
TITLE_MAX_LEN = 24


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
    """标题格式化：空标题回退到商品 ID（短截），再无则 '商品'

    为什么要进一步限长到 TITLE_MAX_LEN：钉钉 markdown 消息卡片宽度有限
    （PC 端约 25-30 个汉字），超长标题会被强制断行影响视觉。
    """
    if title and title.strip():
        return title.strip()[:TITLE_MAX_LEN]
    if item_id:
        return f"商品 {item_id[:12]}"
    return "商品"


# ============== 风险项翻译器 ==============
# evaluator/dealer_detector 生成的 reject_reasons 是面向开发者的技术描述
# （如 "on_sale 9 (ded=1)"、"dealer:image_theft(sellers=6,sample=...)"），
# 必须在模板层翻译为人类可读的中文，否则用户看不懂。
# 为什么不改 evaluator：保持单一职责（评估器只管算分，UI 翻译由模板负责），
# 评估器内部逻辑/日志/前端 API 都仍能看到原始技术描述便于排查。


def _translate_dealer_image_theft(m: re.Match) -> str:
    """翻译 dealer:image_theft 风险项
    
    为什么提取为独立函数：原函数内嵌套了 sample_count 三分支判断，
    与外层 if 链叠加推高认知复杂度。单独提取后主函数只需查表调度。
    """
    sellers = m.group(1)
    sample_ids = m.group(2).split(",")
    sample_count = len(sample_ids)
    sellers_int = int(sellers)
    if sample_count < sellers_int:
        suffix = f"，样本 {sample_count} 个"
    elif sample_count > 1:
        suffix = f"（含 {sample_count} 个样本）"
    else:
        suffix = ""
    return f"🖼️ 涉嫌盗图（已被 {sellers} 个其他卖家使用{suffix}）"


def _translate_dealer_new_register(m: re.Match) -> str:
    """翻译 dealer:new_register_low_activity 风险项"""
    days, sold, on_sale = m.group(1), m.group(2), m.group(3)
    return f"👶 新注册账号（{days} 天），在售 {on_sale} 件 / 已售 {sold} 件，疑似批量上号"


def _translate_dealer_templated_text(m: re.Match) -> str:
    """翻译 dealer:templated_text 风险项"""
    sim = m.group(1)
    return f"📋 文案高度模板化（与 {m.group(2)} 条已售商品相似度 {sim}），疑似批量发帖"


def _translate_dealer_post_burst(m: re.Match) -> str:
    """翻译 dealer:post_burst 风险项"""
    recent, previous, ratio = m.group(1), m.group(2), m.group(3)
    ratio_text = f"（环比 {ratio}）" if ratio != "N/A" else ""
    return f"📈 短期大量发帖（最近 {recent} 条 / 上一周期 {previous} 条）{ratio_text}"


def _translate_on_sale(m: re.Match) -> str:
    """翻译 on_sale 风险项"""
    return f"📦 在售商品过多（{m.group(1)} 件），扣 {m.group(2)} 分"


def _translate_30d_post(m: re.Match) -> str:
    """翻译 30d_post 风险项"""
    return f"📅 30 天内发布数过多（{m.group(1)} 条），扣 {m.group(2)} 分"


def _translate_top_category_ratio(m: re.Match) -> str:
    """翻译 top_category_ratio 风险项"""
    return f"🎯 类目集中度过高（{m.group(1)}%），疑似专注单一品类批发"


def _translate_professional_keyword(m: re.Match) -> str:
    """翻译 professional_keyword 风险项"""
    return f"🏷️ 命中职业卖家关键词「{m.group(1)}」"


def _translate_credit_score_moderate(m: re.Match) -> str:
    """翻译 credit_score moderate 风险项"""
    return f"💳 信用分一般（{m.group(1)} 分）"


def _translate_credit_score(m: re.Match) -> str:
    """翻译 credit_score 风险项（非 moderate）"""
    return f"💳 信用分偏低（{m.group(1)} 分）"


def _translate_register_days(m: re.Match) -> str:
    """翻译 register_days 风险项"""
    return f"📅 注册时间过短（仅 {m.group(1)} 天，要求 ≥{m.group(2)} 天）"


def _translate_low_sold_count(m: re.Match) -> str:
    """翻译 low_sold_count 风险项"""
    return f"📉 销量过低（仅 {m.group(1)} 件成交）"


def _translate_bad_review(m: re.Match) -> str:
    """翻译 bad_review 风险项"""
    return f"⚠️ 差评数过多（{m.group(1)} 条，要求 ≤{m.group(2)} 条）"


# 风险项翻译模式表：按优先级排序，匹配到第一个即返回
# 为什么用查表替代 if-elif 链：13 个 if 分支的认知复杂度 = 1 + 分支数，
# 查表法将复杂度降为固定的循环+条件判断，不受模式数量影响。
_REASON_PATTERNS: list[tuple[re.Pattern, callable]] = [
    (re.compile(r"dealer:image_theft\(sellers=(\d+),sample=([^)]+)\)"), _translate_dealer_image_theft),
    (re.compile(r"dealer:new_register_low_activity\(days=(\d+),sold=(\d+),on_sale=(\d+)\)"), _translate_dealer_new_register),
    (re.compile(r"dealer:templated_text\(max_sim=([\d.]+),sample=(\d+)\)"), _translate_dealer_templated_text),
    (re.compile(r"dealer:post_burst\(recent=(\d+),previous=(\d+),ratio=([^)]+)\)"), _translate_dealer_post_burst),
    (re.compile(r"on_sale (\d+) \(ded=(\d+)\)"), _translate_on_sale),
    (re.compile(r"30d_post (\d+) \(ded=(\d+)\)"), _translate_30d_post),
    (re.compile(r"top_category_ratio (\d+)% > (\d+)%"), _translate_top_category_ratio),
    (re.compile(r"professional_keyword:(.+)"), _translate_professional_keyword),
    (re.compile(r"credit_score (\d+) moderate"), _translate_credit_score_moderate),
    (re.compile(r"credit_score (\d+)"), _translate_credit_score),
    (re.compile(r"register_days (\d+) < (\d+)"), _translate_register_days),
    (re.compile(r"low_sold_count (\d+)"), _translate_low_sold_count),
    (re.compile(r"bad_review (\d+) > (\d+)"), _translate_bad_review),
]


def _translate_reject_reason(reason: str) -> str:
    """将评估器/贩子检测器生成的技术风险项翻译为中文

    翻译规则覆盖 evaluator.py + dealer_detector.py 中所有 reasons.append 模式。
    未知模式直接返回原值（保留原信息便于排查），但去掉过长参数避免视觉冲击。
    
    为什么用查表法：原函数有 13+ 个 if-elif 分支，认知复杂度随分支数线性增长。
    改为模式表 + 循环匹配后，复杂度降为固定值，新增模式只需在表中追加一项。
    """
    if not reason:
        return ""

    # 精确匹配的简单模式（无需正则，性能更优）
    if reason == "credit_score_unknown":
        return "💳 信用分未公开"

    # 正则模式表匹配
    for pattern, handler in _REASON_PATTERNS:
        m = pattern.match(reason)
        if m:
            return handler(m)

    # 未知模式：截断到合理长度（避免超长参数撑爆卡片）
    if len(reason) > 30:
        return f"⚙️ {reason[:27]}..."
    return f"⚙️ {reason}"


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


def _extract_eval_payload(event: Event) -> dict:
    """从事件 payload 中提取评估模板所需的所有字段
    
    为什么提取为独立函数：原 _eval_passed 中数据提取 + 兜底逻辑
    与模板渲染逻辑混在一起，多个 if/or 条件叠加推高复杂度。
    单独提取后渲染函数只关注字符串拼接。
    """
    p = event.payload or {}
    item = p.get("item") if isinstance(p.get("item"), dict) else {}
    
    item_id = _get(p, "item_id", item, "") or (event.item_id or "")
    title = _get(p, "item_title", item, "") or _get(p, "title", item, "")
    
    price = _get(p, "item_price", item, 0)
    if price in (0, None, ""):
        price = _get(p, "price", item, 0)
    
    # task_id 来自 Event 顶层（worker/collection_service/evaluations_common 三处发布点均设置）
    task_id = event.task_id or ""
    return {
        "item_id": item_id,
        "title": title,
        "price": price,
        "score": p.get("score", 0),
        "risk_level": p.get("risk_level", RiskLevel.MEDIUM.value),
        "seller_nick": _get(p, "seller_nick", item, ""),
        "thumb": _get(p, "thumb_url", item, ""),
        "url": _get(p, "url", item, "") or (GOOFISH_ITEM_URL.format(item_id=item_id) if item_id else ""),
        "reasons": p.get("reject_reasons", []) or [],
        "data_quality": p.get("data_quality", ""),
        "region": _get(p, "region", item, ""),
        "task_id": task_id,
        # SEMI_AUTO 模式专属：模板渲染"确认抢单"链接，URL 指向前端 /confirm-buy 页面
        # 空 task_mode 视为非 SEMI_AUTO（保守降级，与历史 CONFIRM/NOTIFY_ONLY 行为一致）
        "task_mode": p.get("task_mode", "") or "",
    }


def _build_meta_parts(data: dict) -> list[str]:
    """构建元信息行的各个部分（ID/卖家/地区）
    
    为什么提取：原函数内三个独立 if 追加到列表，
    与其他条件判断叠加推高复杂度。单独提取后职责单一。
    """
    parts = []
    if data["item_id"]:
        parts.append(f"**ID：** `{data['item_id']}`")
    if data["seller_nick"]:
        parts.append(f"**卖家：** {data['seller_nick']}")
    if data["region"]:
        parts.append(f"**地区：** {data['region']}")
    return parts


def _build_eval_parts(data: dict, risk_color: str) -> list[str]:
    """构建评估行的各个部分（评分/风险/数据质量）"""
    parts = [
        f"**评分：** <font color=\"#1890FF\">{data['score']}</font>",
        f"**风险：** <font color=\"{risk_color}\">{data['risk_level']}</font>",
    ]
    if data["data_quality"]:
        parts.append(f"**数据：** {data['data_quality']}")
    return parts


def _build_reasons_lines(reasons: list) -> list[str]:
    """构建风险项引用块的行列表
    
    为什么提取：原函数内 if reasons + for 循环嵌套，
    与其他条件叠加增加嵌套深度。单独提取后调用方只需判断是否非空。
    """
    lines = ["\n**⚠️ 风险项：**"]
    for r in reasons[:3]:
        lines.append(f"> {_translate_reject_reason(r)}")
    return lines


def _get_risk_color(risk_level: str) -> str:
    """风险等级 → 颜色映射（钉钉支持 6 位 hex <font color>）"""
    color_map = {
        RiskLevel.LOW.value: "#52C41A",
        RiskLevel.MEDIUM.value: "#FA8C16",
        RiskLevel.HIGH.value: "#F5222D",
    }
    return color_map.get(risk_level, "#FA8C16")


def _get_web_base_url() -> str:
    """获取本系统 Web 服务公网可达 URL，用于通知中渲染"确认抢单"等回链

    优先级：
    1. tunnel_service.public_url（用户开启了 Cloudflare Tunnel 远程访问）
    2. http://localhost:{server.port}（本地访问兜底，用户在本机点击通知时可用）

    为什么不在模板层 import 时一次性缓存：tunnel 可能在运行中被启停，
    每次渲染都重新读取以保证 URL 反映当前隧道状态
    """
    try:
        from xianyu_hunter.web.routes.api_tunnel import get_tunnel_service
        public = get_tunnel_service().public_url
        if public:
            return public.rstrip("/")
    except Exception:
        # tunnel_service 未初始化或导入失败时降级，模板渲染不应因 URL 解析失败而中断
        pass
    try:
        from xianyu_hunter.infra.yaml_config import get_config
        port = get_config().server.port
    except Exception:
        port = 8000
    return f"http://localhost:{port}"


def _build_confirm_buy_url(task_id: str, item_id: str) -> str:
    """构建 SEMI_AUTO 模式下"确认抢单"前端页面 URL

    前端 BrowserRouter basename="/app"，所以路径前缀必须包含 /app
    页面加载后展示商品快照与"确认抢单"按钮，点击调用 manual-takeover 接口
    """
    base = _get_web_base_url()
    return f"{base}/app/confirm-buy?task_id={task_id}&item_id={item_id}"


def _eval_passed(event: Event) -> tuple[str, str]:
    """评估通过模板

    兼容两种 payload：
    - 扁平格式（worker 推荐）：item_title / item_price / seller_nick / ...
    - item 子对象格式（历史兼容）：item.title / item.price / ...

    格式说明（钉钉 markdown 优化）：
    - 首行 `# 标题` —— 钉钉会读取首行 `#` 渲染成会话列表预览
    - `<font color="#xxxxxx">` —— 关键字段（评分/风险/价格）上色，钉钉/Server酱/PushPlus 均支持
    - `> 引用` —— 突出风险项
    - `![alt](url)` —— 商品图（钉钉 markdown 支持公网可访问图片）
    - `[text](url)` —— 跳转链接
    - 风险项经 `_translate_reject_reason` 翻译为中文便于用户理解
    
    为什么重构：原函数将数据提取、各区块构建、条件判断全部混在一起，
    多个 if 分支 + 嵌套循环导致认知复杂度超标。拆分为多个单一职责
    辅助函数后，主函数只负责串联各区块，复杂度大幅降低。
    """
    data = _extract_eval_payload(event)
    
    display_title = _format_title(data["title"], data["item_id"])
    price_str = _format_price(data["price"])
    risk_color = _get_risk_color(data["risk_level"])

    head = f"[闲鱼捡漏] {display_title} {price_str}"
    md_title = f"# 🛒 评估通过  {display_title}"
    md_price_line = f"\n<font color=\"#F5222D\">**{price_str}**</font>"

    body_lines = [md_title + md_price_line]
    
    meta_parts = _build_meta_parts(data)
    if meta_parts:
        body_lines.append("  ".join(meta_parts))
    
    eval_parts = _build_eval_parts(data, risk_color)
    body_lines.append("    ".join(eval_parts))
    
    if data["reasons"]:
        body_lines.extend(_build_reasons_lines(data["reasons"]))
    
    if data["thumb"]:
        body_lines.append(f"\n🖼️ [<font color=\"#0088FF\">点击查看商品图</font>]({data['thumb']})")
    
    if data["url"]:
        body_lines.append(f"\n🔗 [<font color=\"#0088FF\">立即查看商品详情</font>]({data['url']})")
    
    # SEMI_AUTO 半自动模式专属：渲染"确认抢单"链接到本系统 /confirm-buy 页面
    # 为什么独立于商品详情链接：商品详情链接跳到闲鱼，用户无法在闲鱼触发本系统抢单
    # 必须有专属链接让用户回到本系统点击确认按钮，才能复用 manual-takeover 接口
    if data["task_mode"] == "semi_auto" and data["task_id"] and data["item_id"]:
        confirm_url = _build_confirm_buy_url(data["task_id"], data["item_id"])
        body_lines.append(
            f"\n⚡ [<font color=\"#FF6200\">**确认抢单（半自动）**</font>]({confirm_url})"
        )
    
    body_lines.append(f"\n<font color=\"#999999\">{SEP}_系统自动发送，请尽快确认_</font>")
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
        f"# ⏰ 已拍下未支付  {display_title}",
        f"\n<font color=\"#F5222D\">**{price_str}**</font>",
        f"**ID：** `{item_id}`" if item_id else "",
        f"**订单：** `{order_id}`" if order_id else "",
        f"**过期：** {expire_at}" if expire_at else "",
        "",
        "⚠️ 请打开闲鱼 App 在 <font color=\"#FA8C16\">**5 分钟内**</font> 完成支付，否则订单自动释放。",
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
        f"# ⚠️ 任务异常  {title}",
        f"**任务：** `{event.task_id}`" if event.task_id else "",
        f"**详情：** {message}" if message else "",
        f"**原因：** `{reason}`" if reason else "",
        "",
        "请尽快检查任务状态和 Cookie 有效性。",
    ]
    return head, "\n".join(line for line in body_lines if line)


def _generic(event: Event) -> tuple[str, str]:
    """通用降级模板"""
    return (
        f"[XianyuHunter] {event.type.value}",
        f"事件：{event.type.value}\n时间：{event.timestamp.isoformat()}\n载荷：{event.payload}",
    )
