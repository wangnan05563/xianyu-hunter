"""成色关键词否定词感知扫描测试

修复背景：商品描述"无划痕磕碰"被朴素子串匹配误判为"明显使用"，
因为"磕碰"作为子串命中了 worn 类别。修复后引入否定词感知，
负面类别（used/worn/broken）的关键词若被否定词修饰则不计为命中。

测试覆盖：
1. 否定词感知核心场景：无/没有/不含/未见 等否定词修饰
2. 标点断开否定关系：无划痕、磕碰（磕碰未被否定）
3. 多次出现时未否定位置仍可命中
4. 正面/中性类别不受否定逻辑影响
5. 完整成色标签推断流程
"""
from __future__ import annotations

from xianyu_hunter.web.routes.evaluations_list import (
    _CONDITION_KEYWORDS,
    _is_negated,
    _resolve_base_condition_label,
    _scan_condition_keywords,
)


# ==== _is_negated 单元测试 ====
def test_is_negated_by_wu() -> None:
    """'无'修饰关键词时识别为否定"""
    text = "无划痕磕碰"
    # "磕碰"位置在 3，前缀"无划痕"包含"无"
    assert _is_negated(text, "磕碰", 3) is True


def test_is_negated_by_meiyou() -> None:
    """'没有'修饰关键词时识别为否定"""
    text = "没有划痕和磕碰"
    # "磕碰"位置在 5，前缀"没有划痕和"包含"没有"
    assert _is_negated(text, "磕碰", 5) is True


def test_is_negated_by_buhan() -> None:
    """'不含'修饰关键词时识别为否定"""
    text = "不含老化配件"
    # "老化"位置在 2，前缀"不含"包含"不含"
    assert _is_negated(text, "老化", 2) is True


def test_is_negated_by_weijian() -> None:
    """'未见'修饰关键词时识别为否定"""
    text = "未见维修痕迹"
    # "维修"位置在 2，前缀"未见"包含"未见"
    assert _is_negated(text, "维修", 2) is True


def test_is_negated_false_when_no_negation() -> None:
    """无否定词修饰时不识别为否定"""
    text = "商品有明显划痕"
    # "划痕"位置在 5，前缀"商品有明显"无否定词
    assert _is_negated(text, "划痕", 5) is False


def test_is_negated_false_when_punct_breaks() -> None:
    """断句标点之后的否定词不修饰关键词"""
    text = "无划痕、磕碰"
    # "磕碰"位置在 4，前缀"无划痕、"中"、"是断句标点
    # 标点之后无否定词，"磕碰"未被否定
    assert _is_negated(text, "磕碰", 4) is False


def test_is_negated_false_when_punct_comma_breaks() -> None:
    """逗号断开否定关系"""
    text = "无划痕，有磕碰"
    # "磕碰"位置在 5，前缀"无划痕，有"中"，"是断句标点
    # 标点之后是"有"，无否定词
    assert _is_negated(text, "磕碰", 5) is False


def test_is_negated_with_window_boundary() -> None:
    """否定词位于窗口边界（10字符）时仍可识别"""
    # "没有"在位置 0，"磕碰"在位置 10，窗口刚好覆盖
    text = "没有任何划痕和磕碰"
    pos = text.find("磕碰")
    assert _is_negated(text, "磕碰", pos) is True


# ==== _scan_condition_keywords 集成测试 ====
def test_scan_wu_huahen_képeng_not_judge_worn() -> None:
    """'无划痕磕碰'不应命中 worn 类别（核心修复场景）"""
    text = "商品无划痕磕碰，成色很好"
    tags, score = _scan_condition_keywords(text)
    # 不应有 worn 类别命中
    worn_tags = [t for t in tags if t["category"] == "worn"]
    assert worn_tags == [], f"误判为 worn: {worn_tags}"


def test_scan_meiyou_huahen_kepeng_not_judge_worn() -> None:
    """'没有划痕和磕碰'不应命中 worn 类别"""
    text = "iPhone 13 没有划痕和磕碰"
    tags, score = _scan_condition_keywords(text)
    worn_tags = [t for t in tags if t["category"] == "worn"]
    assert worn_tags == [], f"误判为 worn: {worn_tags}"


def test_scan_wu_huahen_kepeng_with_punct_still_worn() -> None:
    """'无划痕、磕碰'中"磕碰"未被否定，应命中 worn"""
    text = "商品无划痕、磕碰"
    tags, score = _scan_condition_keywords(text)
    worn_tags = [t for t in tags if t["category"] == "worn"]
    # "磕碰"前有"、"断句，未被否定，应命中
    assert len(worn_tags) == 1
    assert worn_tags[0]["label"] == "磕碰"


def test_scan_normal_worn_still_matched() -> None:
    """正常负面描述仍应命中 worn"""
    text = "商品有磕碰，成色一般"
    tags, score = _scan_condition_keywords(text)
    worn_tags = [t for t in tags if t["category"] == "worn"]
    assert len(worn_tags) >= 1


def test_scan_normal_broken_still_matched() -> None:
    """正常故障描述仍应命中 broken"""
    text = "手机屏幕破损，已维修"
    tags, score = _scan_condition_keywords(text)
    broken_tags = [t for t in tags if t["category"] == "broken"]
    assert len(broken_tags) >= 1


def test_scan_wu_weixiu_not_judge_broken() -> None:
    """'无维修'不应命中 broken"""
    text = "无维修，无进水，功能正常"
    tags, score = _scan_condition_keywords(text)
    broken_tags = [t for t in tags if t["category"] == "broken"]
    assert broken_tags == [], f"误判为 broken: {broken_tags}"


def test_scan_wu_jinshui_not_judge_broken() -> None:
    """'无进水'不应命中 broken"""
    text = "国行未激活，无进水无摔过"
    tags, score = _scan_condition_keywords(text)
    broken_tags = [t for t in tags if t["category"] == "broken"]
    assert broken_tags == [], f"误判为 broken: {broken_tags}"


def test_scan_positive_keywords_unaffected_by_negation() -> None:
    """正面类别（newness）不受否定逻辑影响"""
    # "未拆封"本身是 newness 关键词，"未"虽是否定词但 newness 不做否定检测
    text = "全新未拆封国行未激活"
    tags, score = _scan_condition_keywords(text)
    newness_tags = [t for t in tags if t["category"] == "newness"]
    assert len(newness_tags) >= 1


def test_scan_completeness_missing_unaffected_by_negation() -> None:
    """completeness_missing 类别（含'无包装'等）不受否定逻辑影响"""
    # "无包装"是 completeness_missing 关键词，不应被否定逻辑误判
    text = "裸机出，无包装无配件"
    tags, score = _scan_condition_keywords(text)
    missing_tags = [t for t in tags if t["category"] == "completeness_missing"]
    assert len(missing_tags) >= 1


def test_scan_multiple_occurrences_unnegated_match() -> None:
    """同一关键词多次出现时，未否定的位置仍可命中"""
    # 第一次"磕碰"被"无"否定，第二次"磕碰"未被否定
    text = "无磕碰，但实际有磕碰"
    tags, score = _scan_condition_keywords(text)
    worn_tags = [t for t in tags if t["category"] == "worn"]
    assert len(worn_tags) == 1
    assert worn_tags[0]["label"] == "磕碰"


def test_scan_score_not_decreased_when_negated() -> None:
    """被否定的负面关键词不应扣分"""
    text_negated = "无划痕磕碰"
    text_normal = "有划痕磕碰"
    _, score_negated = _scan_condition_keywords(text_negated)
    _, score_normal = _scan_condition_keywords(text_normal)
    # 被否定场景不应扣 worn 分数（-2）
    assert score_negated > score_normal


# ==== _resolve_base_condition_label 集成测试 ====
def test_resolve_label_wu_huahen_kepeng_not_obvious_used() -> None:
    """'无划痕磕碰'不应判定为'明显使用'"""
    text = "商品无划痕磕碰"
    tags, _ = _scan_condition_keywords(text)
    label = _resolve_base_condition_label(tags)
    assert label != "明显使用", f"误判为明显使用: {label}"


def test_resolve_label_normal_kepeng_is_obvious_used() -> None:
    """'有磕碰'应判定为'明显使用'"""
    text = "商品有磕碰磨损"
    tags, _ = _scan_condition_keywords(text)
    label = _resolve_base_condition_label(tags)
    assert label == "明显使用"


# ==== 回归测试：关键词库完整性 ====
def test_condition_keywords_worn_labels_intact() -> None:
    """确认 worn 类别关键词库未被破坏"""
    worn_labels = _CONDITION_KEYWORDS["worn"]["labels"]
    assert "磕碰" in worn_labels
    assert "有划痕" in worn_labels
    assert _CONDITION_KEYWORDS["worn"]["score_bonus"] == -2


def test_condition_keywords_broken_labels_intact() -> None:
    """确认 broken 类别关键词库未被破坏"""
    broken_labels = _CONDITION_KEYWORDS["broken"]["labels"]
    assert "维修" in broken_labels
    assert "进水" in broken_labels
    assert _CONDITION_KEYWORDS["broken"]["score_bonus"] == -3
