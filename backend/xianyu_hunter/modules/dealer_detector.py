"""贩子识别引擎 - O-10-26 / O-13-26

基于 4 维特征识别职业贩子，过滤非真实个人闲置：
1. 新注册低活跃：register_days < 30 AND sold_count < 5（组合信号）
2. 文案模板化：recent_posts 多个标题高度相似（规则检测，不调 LLM 降低成本）
3. 图像盗图：同一图片被多个不同卖家使用（O-13-26，DB 查询 image_urls 字段）
4. 卖家主页商品数突增：近 15 天 vs 前 15 天发布数比值（基于 items.first_seen）

设计原则：
- 独立模块，不侵入 Evaluator 核心逻辑
- 返回扣分建议 + 原因列表，由 Evaluator 决定如何整合
- 规则优先，避免 LLM 调用成本（文案模板化用字符 overlap 检测）
- 图像盗图用 SQLite LIKE 查询 JSON 字段，无需新增依赖
- 商品数突增用 items 表 first_seen 字段对比前后窗口，无需新增时序表
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from xianyu_hunter.domain.item import ItemDetail
from xianyu_hunter.domain.seller import SellerProfile

logger = logging.getLogger(__name__)

# H7: 贩子识别缓存——同一卖家在同一轮评估中多次出现时避免重复 DB 查询
# _detect_image_theft 用 LIKE 全表扫描 + _detect_post_burst 用 2 次 COUNT，
# 20 商品 × (3+2) = 100 次 DB 查询。缓存命中后直接返回结果，减少 DB 压力。
# 缓存上限 512 条，超限时清空重建（内存仅 ~100KB，无需 LRU 淘汰算法）
_DEALER_CACHE: dict[tuple[str, str | None], DealerDetectionResult] = {}
_DEALER_CACHE_MAX = 512


@dataclass
class DealerDetectionResult:
    """贩子识别结果

    score_deduction: 建议扣分（0-50），由调用方决定如何应用
    reasons: 命中的贩子信号列表（用于 reject_reasons 展示）
    confidence: 置信度 0-1，多维度命中时更高
    """
    score_deduction: int = 0
    reasons: list[str] = field(default_factory=list)
    confidence: float = 0.0
    # 各维度命中详情（供前端展示）
    signals: dict[str, dict] = field(default_factory=dict)


def _text_similarity(a: str, b: str) -> float:
    """计算两段文本的相似度（基于字符 n-gram overlap）

    用 2-gram 字符集的 Jaccard 系数，比编辑距离更快，
    适合短文本（标题）批量比较。
    """
    if not a or not b:
        return 0.0
    # 2-gram 字符集
    def bigrams(s: str) -> set[str]:
        return {s[i:i+2] for i in range(len(s) - 1)} if len(s) > 1 else {s}

    bg_a = bigrams(a)
    bg_b = bigrams(b)
    if not bg_a or not bg_b:
        return 0.0
    intersection = bg_a & bg_b
    union = bg_a | bg_b
    return len(intersection) / len(union) if union else 0.0


def _detect_templated_text(titles: list[str], threshold: float = 0.7) -> tuple[bool, float]:
    """检测标题列表是否存在模板化（多个标题高度相似）

    返回 (is_templated, max_similarity)
    - 阈值 0.7：经验值，标题 2-gram Jaccard > 0.7 通常意味着仅替换了型号/颜色
    - 只要有 1 对相似度 > 阈值即判定为模板化
    """
    if len(titles) < 2:
        return False, 0.0
    max_sim = 0.0
    # 两两比较，O(n²) 但 n 通常 < 20（recent_posts 上限）
    for i in range(len(titles)):
        for j in range(i + 1, len(titles)):
            sim = _text_similarity(titles[i], titles[j])
            if sim > max_sim:
                max_sim = sim
            if sim >= threshold:
                return True, round(max_sim, 2)
    return False, round(max_sim, 2)


def _escape_sql_like(s: str) -> str:
    """转义 SQLite LIKE 的 % 和 _ 通配符

    image_urls 字段是 JSON 数组字符串，URL 中可能包含 % 等字符，
    若不转义会导致 LIKE 误匹配。
    SQLite 默认没有 ESCAPE 子句时，用 / 作为转义符。
    """
    return s.replace("/", "//").replace("%", "/%").replace("_", "/_")


def _detect_image_theft(
    image_urls: list[str],
    seller_id: str,
    max_images: int = 3,
) -> tuple[bool, int, list[str]]:
    """O-13-26 图像盗图检测：查询 DB 中是否有其他卖家使用相同图片

    策略：image_urls 是 JSON 数组字符串（如 ["url1","url2"]），
    用 LIKE '%"url"%' 匹配 JSON 中的 URL 子串。

    Args:
        image_urls: 当前商品的图片 URL 列表
        seller_id: 当前卖家 ID（用于排除自己）
        max_images: 最多查询几张图，避免大列表拖慢 DB（默认 3）

    Returns:
        (is_theft, distinct_seller_count, sample_other_seller_ids)
        - is_theft: 是否检测到盗图（distinct_seller_count > 0）
        - distinct_seller_count: 使用相同图片的不同卖家数
        - sample_other_seller_ids: 前 5 个其他卖家 ID（用于 reasons 展示）
    """
    if not image_urls or not seller_id:
        return False, 0, []

    # 延迟导入避免循环依赖：dealer_detector 是被 evaluator 调用的，
    # 而 evaluator 在 worker.py 中被调用，worker 已先初始化 repo
    from xianyu_hunter.infra.db_models import ItemRow
    from xianyu_hunter.infra.repository_base import get_repository
    from sqlalchemy import or_, select

    try:
        repo = get_repository()
    except Exception as e:
        logger.warning("图像盗图检测获取 repo 失败: %s", e)
        return False, 0, []

    # 预处理：收集所有有效的 LIKE pattern，过滤掉过短的 URL
    # image_urls 是 JSON 数组字符串，URL 总是被双引号包裹，用 '%"url"%' 精确匹配引号内
    patterns: list[str] = []
    for url in image_urls[:max_images]:
        if not url or len(url) < 20:
            # 太短的 URL 容易误匹配（如占位图），跳过
            continue
        escaped = _escape_sql_like(url)
        patterns.append(f'%"{escaped}"%')

    if not patterns:
        return False, 0, []

    other_sellers: set[str] = set()
    try:
        # 性能优化：原实现循环中对每个 URL 发 1 次 LIKE 查询（N+1 模式），
        # image_urls 是 JSON 文本字段无索引，每次全表扫描 items。
        # 改为用 or_ 连接所有 LIKE 条件，合并为 1 次查询，N 次全表扫描降为 1 次。
        like_conditions = [ItemRow.image_urls.like(p, escape="/") for p in patterns]
        stmt = (
            select(ItemRow.seller_id)
            .where(or_(*like_conditions))
            .where(ItemRow.seller_id.is_not(None))
            .where(ItemRow.seller_id != seller_id)
            .distinct()
        )
        with repo.engine.connect() as conn:
            for row in conn.execute(stmt).all():
                if row[0]:
                    other_sellers.add(row[0])
    except Exception as e:
        logger.warning("图像盗图检测查询失败: %s", e)
        return False, 0, []

    return len(other_sellers) > 0, len(other_sellers), list(other_sellers)[:5]


def _detect_post_burst(
    seller_id: str,
    total_window_days: int = 30,
    recent_window_days: int = 15,
    min_recent_count: int = 10,
    burst_ratio: float = 3.0,
) -> tuple[bool, int, int, float]:
    """O-13-26 维度4：卖家主页商品数突增检测

    策略：用 items 表 first_seen 字段，对比近 15 天 vs 前 15 天的发布数
    - 若近 15 天发布数 >= 10 且 >= 前 15 天的 3 倍 → 判定为突增
    - 用 first_seen 而非 publish_time：first_seen 一定有值，publish_time 可能为空

    Args:
        seller_id: 卖家 ID
        total_window_days: 总窗口天数（默认 30，前后窗口各 15 天）
        recent_window_days: 近期窗口天数（默认 15）
        min_recent_count: 近期最少发布数阈值（默认 10）
        burst_ratio: 突增倍数阈值（默认 3.0）

    Returns:
        (is_burst, recent_count, previous_count, ratio)
    """
    if not seller_id:
        return False, 0, 0, 0.0

    from datetime import datetime, timedelta, timezone
    from xianyu_hunter.infra.db_models import ItemRow
    from xianyu_hunter.infra.repository_base import get_repository
    from sqlalchemy import func, select

    try:
        repo = get_repository()
    except Exception as e:
        logger.warning("商品数突增检测获取 repo 失败: %s", e)
        return False, 0, 0, 0.0

    now = datetime.now(timezone.utc)
    recent_start = now - timedelta(days=recent_window_days)
    previous_start = now - timedelta(days=total_window_days)

    try:
        with repo.engine.connect() as conn:
            # 近 15 天发布数
            recent_stmt = (
                select(func.count())
                .select_from(ItemRow)
                .where(ItemRow.seller_id == seller_id)
                .where(ItemRow.first_seen >= recent_start)
                .where(ItemRow.first_seen <= now)
            )
            recent_count = int(conn.execute(recent_stmt).scalar() or 0)

            # 前 15 天（窗口 30 天到 15 天前）发布数
            previous_stmt = (
                select(func.count())
                .select_from(ItemRow)
                .where(ItemRow.seller_id == seller_id)
                .where(ItemRow.first_seen >= previous_start)
                .where(ItemRow.first_seen < recent_start)
            )
            previous_count = int(conn.execute(previous_stmt).scalar() or 0)
    except Exception as e:
        logger.warning("商品数突增检测查询失败: %s", e)
        return False, 0, 0, 0.0

    # 计算比值：previous_count=0 时比值无意义（不能用 recent/0.1 凑数，会误导用户）
    # 直接置为 0.0，由 is_burst 判定中的 previous_count == 0 短路 OR 处理
    if previous_count > 0:
        ratio = recent_count / previous_count
    else:
        ratio = 0.0
    # 前窗口为 0 时，比值无意义，仅看近期绝对数
    is_burst = (
        recent_count >= min_recent_count
        and (previous_count == 0 or ratio >= burst_ratio)
    )
    return is_burst, recent_count, previous_count, round(ratio, 1)


def detect_dealer(seller: SellerProfile, item: ItemDetail | None = None) -> DealerDetectionResult:
    """贩子识别主入口

    Args:
        seller: 卖家画像
        item: 当前商品（可选，用于未来扩展图片检测）

    Returns:
        DealerDetectionResult，包含扣分建议和命中信号

    重构说明：4 个维度各自独立检测，提取为私有函数，主函数只负责编排、
    置信度聚合与缓存。降低圈复杂度（S3776）并便于单维度独立测试。
    """
    # H7: 缓存优先——同一卖家在同一轮评估中多次出现时直接返回缓存结果
    # 避免 _detect_image_theft（LIKE 全表扫描）和 _detect_post_burst（2 次 COUNT）
    # 对同一卖家重复执行。缓存 key 为 (seller_id, item_id)，
    # item_id 可选（部分调用方可能不传 item，此时仅按 seller_id 缓存）
    cache_key = (seller.id, item.id if item else None)
    cached = _DEALER_CACHE.get(cache_key)
    if cached is not None:
        return cached

    result = DealerDetectionResult()
    # 各维度独立检测，命中则累加扣分与命中数
    hit_count = 0
    hit_count += _check_new_register_low_activity(seller, result)
    hit_count += _check_templated_text(seller, result)
    hit_count += _check_image_theft(seller, item, result)
    hit_count += _check_post_burst(seller, result)

    # 置信度：命中维度越多越高（1 维=0.4, 2 维=0.7, 3 维=0.9）
    result.confidence = min(0.9, hit_count * 0.35) if hit_count > 0 else 0.0

    # 扣分上限 50（避免单卖家过度惩罚）
    result.score_deduction = min(result.score_deduction, 50)

    if result.reasons:
        logger.debug(
            "贩子识别命中: seller=%s, signals=%d, deduction=%d, confidence=%.2f",
            seller.id, hit_count, result.score_deduction, result.confidence,
        )

    # H7: 缓存结果，避免同一卖家重复 DB 查询
    # 超限时清空缓存重建（estimate: 512 条 × ~200B ≈ 100KB，可忽略）
    if len(_DEALER_CACHE) >= _DEALER_CACHE_MAX:
        _DEALER_CACHE.clear()
    _DEALER_CACHE[cache_key] = result

    return result


def _check_new_register_low_activity(
    seller: SellerProfile, result: DealerDetectionResult
) -> int:
    """维度1：新注册低活跃检测

    单独"新注册"或"低活跃"不一定是贩子（可能是新用户），
    但两者组合（新注册 AND 低活跃 AND 高在售）是职业贩子典型特征：
    批量注册账号 → 上架大量商品 → 但还没有成交记录。

    返回命中数（0 或 1），命中时已填充 result 的对应字段。
    """
    if not (
        seller.register_days > 0
        and seller.register_days < 30
        and seller.sold_count < 5
        and seller.on_sale_count > 10
    ):
        return 0
    deduction = 25
    result.score_deduction += deduction
    result.reasons.append(
        f"dealer:new_register_low_activity(days={seller.register_days},sold={seller.sold_count},on_sale={seller.on_sale_count})"
    )
    result.signals["new_register_low_activity"] = {
        "register_days": seller.register_days,
        "sold_count": seller.sold_count,
        "on_sale_count": seller.on_sale_count,
        "deduction": deduction,
    }
    return 1


def _check_templated_text(
    seller: SellerProfile, result: DealerDetectionResult
) -> int:
    """维度2：文案模板化检测

    职业贩子常用同一模板批量发品，标题仅替换型号/颜色/品牌。
    用 2-gram Jaccard 相似度检测，阈值 0.7。
    """
    titles = [p.title for p in seller.recent_posts if p.title]
    is_templated, max_sim = _detect_templated_text(titles)
    if not is_templated:
        return 0
    deduction = 20
    result.score_deduction += deduction
    result.reasons.append(f"dealer:templated_text(max_sim={max_sim},sample={len(titles)})")
    result.signals["templated_text"] = {
        "max_similarity": max_sim,
        "sample_size": len(titles),
        "deduction": deduction,
    }
    return 1


def _check_image_theft(
    seller: SellerProfile,
    item: ItemDetail | None,
    result: DealerDetectionResult,
) -> int:
    """维度3：图像盗图检测（O-13-26）

    职业贩子常盗用其他卖家的商品图片批量上架，节省拍摄成本。
    通过 DB 查询相同 image_url 是否被其他 seller_id 使用。
    限制：仅检测已采集到 DB 的商品，无法检测站外盗图。
    """
    if item is None or not item.image_urls or not seller.id:
        return 0
    is_theft, theft_count, sample_sellers = _detect_image_theft(
        item.image_urls, seller.id
    )
    if not is_theft:
        return 0
    # 扣分梯度：1 个其他卖家 -15，2+ 个 -25，3+ 个 -30
    if theft_count >= 3:
        deduction = 30
    elif theft_count == 2:
        deduction = 25
    else:
        deduction = 15
    result.score_deduction += deduction
    result.reasons.append(
        f"dealer:image_theft(sellers={theft_count},sample={','.join(sample_sellers[:3])})"
    )
    result.signals["image_theft"] = {
        "distinct_seller_count": theft_count,
        "sample_other_sellers": sample_sellers,
        "deduction": deduction,
    }
    return 1


def _check_post_burst(
    seller: SellerProfile, result: DealerDetectionResult
) -> int:
    """维度4：卖家主页商品数突增检测

    职业贩子批量注册后会突然大量上架，近 15 天发布数远超前 15 天。
    用 items.first_seen 字段对比前后窗口，无需新增时序表。
    """
    if not seller.id:
        return 0
    is_burst, recent_n, previous_n, ratio = _detect_post_burst(seller.id)
    if not is_burst:
        return 0
    # 扣分梯度：比值 3-5x -15，5-10x -20，>10x -25
    # previous=0 时 ratio=0.0（无意义），梯度按 min_recent_count 命中给最低扣分 -15
    if ratio >= 10:
        deduction = 25
    elif ratio >= 5:
        deduction = 20
    else:
        deduction = 15
    result.score_deduction += deduction
    # ratio=0 时显示 N/A 避免误导（previous=0 时比值本就无意义）
    ratio_str = f"{ratio}x" if previous_n > 0 else "N/A"
    result.reasons.append(
        f"dealer:post_burst(recent={recent_n},previous={previous_n},ratio={ratio_str})"
    )
    result.signals["post_burst"] = {
        "recent_count": recent_n,
        "previous_count": previous_n,
        "ratio": ratio,
        "deduction": deduction,
    }
    return 1
