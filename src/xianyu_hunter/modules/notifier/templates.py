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


def _translate_reject_reason(reason: str) -> str:
    """将评估器/贩子检测器生成的技术风险项翻译为中文

    翻译规则覆盖 evaluator.py + dealer_detector.py 中所有 reasons.append 模式。
    未知模式直接返回原值（保留原信息便于排查），但去掉过长参数避免视觉冲击。
    """
    if not reason:
        return ""

    # —— 贩子信号（dealer:*） ——
    m = re.match(r"dealer:image_theft\(sellers=(\d+),sample=([^)]+)\)", reason)
    if m:
        sellers = m.group(1)
        # 样本 seller_id 列表过长会撑爆卡片宽度，仅取首个并加省略号
        sample_ids = m.group(2).split(",")
        # sample_ids 是「同款图片出现的其他卖家样本」，sellers 是「被发现的总卖家数」
        # 避免重复措辞：默认用 sellers 总数；仅当样本数 < sellers 时附"样本：N 个"
        sample_count = len(sample_ids)
        if sample_count < int(sellers):
            suffix = f"，样本 {sample_count} 个"
        elif sample_count > 1:
            suffix = f"（含 {sample_count} 个样本）"
        else:
            suffix = ""
        return f"🖼️ 涉嫌盗图（已被 {sellers} 个其他卖家使用{suffix}）"

    m = re.match(r"dealer:new_register_low_activity\(days=(\d+),sold=(\d+),on_sale=(\d+)\)", reason)
    if m:
        days, sold, on_sale = m.group(1), m.group(2), m.group(3)
        return f"👶 新注册账号（{days} 天），在售 {on_sale} 件 / 已售 {sold} 件，疑似批量上号"

    m = re.match(r"dealer:templated_text\(max_sim=([\d.]+),sample=(\d+)\)", reason)
    if m:
        sim = m.group(1)
        return f"📋 文案高度模板化（与 {m.group(2)} 条已售商品相似度 {sim}），疑似批量发帖"

    m = re.match(r"dealer:post_burst\(recent=(\d+),previous=(\d+),ratio=([^)]+)\)", reason)
    if m:
        recent, previous, ratio = m.group(1), m.group(2), m.group(3)
        ratio_text = f"（环比 {ratio}）" if ratio != "N/A" else ""
        return f"📈 短期大量发帖（最近 {recent} 条 / 上一周期 {previous} 条）{ratio_text}"

    # —— 基础评估（evaluator） ——
    m = re.match(r"on_sale (\d+) \(ded=(\d+)\)", reason)
    if m:
        return f"📦 在售商品过多（{m.group(1)} 件），扣 {m.group(2)} 分"

    m = re.match(r"30d_post (\d+) \(ded=(\d+)\)", reason)
    if m:
        return f"📅 30 天内发布数过多（{m.group(1)} 条），扣 {m.group(2)} 分"

    m = re.match(r"top_category_ratio (\d+)% > (\d+)%", reason)
    if m:
        return f"🎯 类目集中度过高（{m.group(1)}%），疑似专注单一品类批发"

    m = re.match(r"professional_keyword:(.+)", reason)
    if m:
        return f"🏷️ 命中职业卖家关键词「{m.group(1)}」"

    m = re.match(r"credit_score (\d+) moderate", reason)
    if m:
        return f"💳 信用分一般（{m.group(1)} 分）"

    m = re.match(r"credit_score (\d+)", reason)
    if m:
        return f"💳 信用分偏低（{m.group(1)} 分）"

    if reason == "credit_score_unknown":
        return "💳 信用分未公开"

    m = re.match(r"register_days (\d+) < (\d+)", reason)
    if m:
        return f"📅 注册时间过短（仅 {m.group(1)} 天，要求 ≥{m.group(2)} 天）"

    m = re.match(r"low_sold_count (\d+)", reason)
    if m:
        return f"📉 销量过低（仅 {m.group(1)} 件成交）"

    m = re.match(r"bad_review (\d+) > (\d+)", reason)
    if m:
        return f"⚠️ 差评数过多（{m.group(1)} 条，要求 ≤{m.group(2)} 条）"

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

    # 风险等级 → 颜色映射（钉钉支持 6 位 hex <font color>，low=绿/medium=橙/high=红）
    risk_color = {
        RiskLevel.LOW.value: "#52C41A",      # 绿
        RiskLevel.MEDIUM.value: "#FA8C16",   # 橙
        RiskLevel.HIGH.value: "#F5222D",     # 红
    }.get(risk_level, "#FA8C16")

    # 短标题：用于钉钉会话列表预览（title 字段，纯文本，限 30 字符）
    head = f"[闲鱼捡漏] {display_title} {price_str}"
    # 卡片标题：钉钉会读取首行 # 标题渲染成会话内大字号卡片标题
    md_title = f"# 🛒 评估通过  {display_title}"
    md_price_line = f"\n<font color=\"#F5222D\">**{price_str}**</font>"

    body_lines = [md_title + md_price_line]
    # 元信息块：用 4 个空格作为柔性分隔（钉钉 markdown 不支持表格，柔性空格避免拥挤换行）
    meta_parts = []
    if item_id:
        meta_parts.append(f"**ID：** `{item_id}`")
    if seller_nick:
        meta_parts.append(f"**卖家：** {seller_nick}")
    if region:
        meta_parts.append(f"**地区：** {region}")
    if meta_parts:
        body_lines.append("  ".join(meta_parts))
    # 评估行：评分 + 风险等级 + 数据质量（4 空格分隔，避免堆在一起）
    eval_parts = [
        f"**评分：** <font color=\"#1890FF\">{score}</font>",
        f"**风险：** <font color=\"{risk_color}\">{risk_level}</font>",
    ]
    if data_quality:
        eval_parts.append(f"**数据：** {data_quality}")
    body_lines.append("    ".join(eval_parts))
    if reasons:
        # 风险项：用引用块突出，且通过翻译器转为人类可读中文
        # 4 个空格前缀避免在窄卡片中错位
        body_lines.append("\n**⚠️ 风险项：**")
        for r in reasons[:3]:
            body_lines.append(f"> {_translate_reject_reason(r)}")
    # 商品图说明：钉钉 markdown 在 actionCard 内的图片经常无法渲染
    # （图床防盗链、格式 webp 不支持、钉钉代理下载失败等）
    # 故改在 dingtalk.py 中发送单独的 link 类型消息展示 picUrl（更稳定）
    # 钉钉 webhook 不支持 image 类型（官方限制），且公共图床国内访问不通。
    # 降级为可点击图片链接：用户点击在新窗口打开原图（绕过防盗链问题）
    if thumb:
        body_lines.append(f"\n🖼️ [<font color=\"#0088FF\">点击查看商品图</font>]({thumb})")
    if url:
        # 跳转链接用 font 颜色更醒目，前后空行形成视觉分段
        body_lines.append(f"\n🔗 [<font color=\"#0088FF\">立即查看商品详情</font>]({url})")
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
