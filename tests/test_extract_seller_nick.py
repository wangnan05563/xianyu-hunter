"""extract_seller_nick 字段错位修复测试

背景：闲鱼搜索 API 在不同商品上字段语义不稳定：
- 部分商品：region 字段实际是用户昵称，nick 字段为空
- 部分商品：userNick 字段实际是发布时间描述（如"一周内发布"），
            region 字段才是真实昵称

这两种异常都会导致前端 seller/region/publish_time 三列整体错位。
本测试覆盖所有已知场景，确保 extract_seller_nick 始终返回正确的 (nick, region)。
"""
from __future__ import annotations

import pytest

from xianyu_hunter.modules.collector_utils import extract_seller_nick


# 场景 1：标准情况——独立 userNick + 真实地名
def test_standard_user_nick_and_region() -> None:
    """正常情况：userNick 是昵称，region 是真地名"""
    nick, region = extract_seller_nick({"userNick": "小明", "region": "河北"})
    assert nick == "小明"
    assert region == "河北"


# 场景 2：region 字段是昵称，userNick 为空
def test_region_holds_nick_when_user_nick_empty() -> None:
    """API 把昵称放在 region 字段，userNick 为空（场景 A）"""
    nick, region = extract_seller_nick({"userNick": "", "region": "芯***鱼"})
    assert nick == "芯***鱼"
    assert region == ""


# 场景 3：userNick 是发布时间描述，region 才是真昵称（用户截图的实际场景）
def test_swap_user_nick_publish_label_and_region_nick() -> None:
    """API 把发布描述放进 userNick，把真昵称放进 region（场景 B，最关键）"""
    raw = {"userNick": "一周内发布", "region": "芯***鱼"}
    nick, region = extract_seller_nick(raw)
    assert nick == "芯***鱼", f"应该把 region 当作 nick，但得到 nick={nick!r}"
    assert region == "一周内发布", (
        f"userNick 是发布描述，应该被识别为 region，但得到 region={region!r}"
    )


# 场景 3.1：发布描述变体——"X 天前发布"
def test_swap_user_nick_with_days_ago() -> None:
    nick, region = extract_seller_nick({"userNick": "3天前发布", "region": "数码***爱好者"})
    assert nick == "数码***爱好者"
    assert region == "3天前发布"


# 场景 3.2：发布描述变体——"X 小时前发布"
def test_swap_user_nick_with_hours_ago() -> None:
    nick, region = extract_seller_nick({"userNick": "5小时前发布", "region": "小***鱼"})
    assert nick == "小***鱼"
    assert region == "5小时前发布"


# 场景 4：userNick 是真昵称，region 是真地名——不应被错误交换
def test_no_swap_when_both_normal() -> None:
    """真昵称 + 真地名不应被交换"""
    nick, region = extract_seller_nick({"userNick": "老王", "region": "浙江杭州"})
    assert nick == "老王"
    assert region == "浙江杭州"


# 场景 5：userNick 是标签（"包邮"），region 是真地名——保守不交换（region 看起来真）
def test_no_swap_when_region_looks_like_real_region() -> None:
    """userNick 是标签但 region 是真地名 → 不交换（无法确定谁是谁）"""
    nick, region = extract_seller_nick({"userNick": "包邮", "region": "河北"})
    assert nick == "包邮"
    assert region == "河北"


# 场景 6：region 为空，userNick 是发布描述——只返回 nick（不交换）
def test_no_swap_when_region_empty() -> None:
    nick, region = extract_seller_nick({"userNick": "2天前发布", "region": ""})
    assert nick == "2天前发布"
    assert region == ""


# 场景 7：userNick 包含价格字符（"¥XXX"）也视为非昵称
def test_swap_user_nick_with_price_marker() -> None:
    raw = {"userNick": "¥699.00", "region": "卖家***号"}
    nick, region = extract_seller_nick(raw)
    assert nick == "卖家***号"
    assert region == "¥699.00"


# 场景 8：使用 sellerNick 候选字段
def test_seller_nick_field_fallback() -> None:
    """无 userNick 但有 sellerNick 时使用 sellerNick"""
    nick, region = extract_seller_nick({"sellerNick": "卖家A", "region": "广东深圳"})
    assert nick == "卖家A"
    assert region == "广东深圳"


# 场景 9：所有字段都为空
def test_all_empty() -> None:
    nick, region = extract_seller_nick({})
    assert nick == ""
    assert region == ""


# 场景 10：userNick 是"已售"标签
def test_swap_user_nick_with_sold_label() -> None:
    raw = {"userNick": "已售", "region": "买***家"}
    nick, region = extract_seller_nick(raw)
    assert nick == "买***家"
    assert region == "已售"
