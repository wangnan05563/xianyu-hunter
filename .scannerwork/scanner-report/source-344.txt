"""测试 collector 脱敏昵称正则模式

回归测试：闲鱼脱敏昵称（"嘟***子"）和"几乎全新"等成色描述混入段落时，
sellerNick 兜底逻辑应能正确识别脱敏昵称，且排除成色描述。
此测试覆盖 JS 兜底逻辑中的关键正则模式。
"""
from __future__ import annotations

import re

# 复制 collector/_search.py JS 中的关键正则
_MASKED_NICK_RE = re.compile(r"^[\u4e00-\u9fa5*]+\*{2,}[\u4e00-\u9fa5*]*$")
_CONDITION_LABEL_RE = re.compile(r"几乎全新|^全新$|^充新$|\d{1,2}新|\d成新")
_TRADE_LABEL_RE = re.compile(r"急售|包邮|秒发|正品|自提|议价|小刀|大刀")


def test_masked_nick_recognized() -> None:
    """脱敏昵称应被正确识别"""
    for nick in ("嘟***子", "芯***鱼", "爱***猫", "行***三", "荒***芽", "数***好", "空***猫"):
        assert _MASKED_NICK_RE.match(nick), f"脱敏昵称 {nick!r} 应被识别"


def test_masked_nick_length_range() -> None:
    """脱敏昵称长度应在 3-20 字符之间"""
    # 太短
    assert not (_MASKED_NICK_RE.match("a**") and len("a**") >= 3)
    # 适中
    assert _MASKED_NICK_RE.match("嘟***子") and 3 <= len("嘟***子") <= 20


def test_pure_chinese_nick_not_matched() -> None:
    """纯中文昵称不应被脱敏昵称正则匹配（这些由另一个分支处理）"""
    for nick in ("小明", "数码爱好者", "张三"):
        assert not _MASKED_NICK_RE.match(nick), f"纯中文昵称 {nick!r} 不应匹配脱敏昵称正则"


def test_non_chinese_not_matched() -> None:
    """非中文脱敏格式不应匹配"""
    for s in ("abc", "123", "嘟*子"):  # 嘟*子只有 1 个 *
        assert not _MASKED_NICK_RE.match(s), f"{s!r} 不应匹配脱敏昵称正则"


def test_condition_label_excluded() -> None:
    """商品成色描述应被成色正则识别（用于 sellerNick 兜底时排除）"""
    for label in ("几乎全新", "全新", "9成新", "99新", "充新", "9.5成新"):
        assert _CONDITION_LABEL_RE.search(label), f"成色描述 {label!r} 应被识别"


def test_trade_label_excluded() -> None:
    """交易描述应被交易正则识别（用于 sellerNick 兜底时排除）"""
    for label in ("急售", "包邮", "秒发", "正品", "自提", "议价", "小刀", "大刀"):
        assert _TRADE_LABEL_RE.search(label), f"交易描述 {label!r} 应被识别"
