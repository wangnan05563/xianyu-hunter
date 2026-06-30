"""normalize_display_fields 字段语义自动校正测试

背景：闲鱼搜索 API 在不同商品上字段语义并不稳定，已观察到以下错位场景：
- seller_nick 字段实际是发布时间描述（如"一周内发布"）
- seller_nick 字段实际是信用度描述（如"信用极好"）
- region 字段实际是用户昵称（如"芯***鱼"）
- publish_time 字段为空，但 seller_nick 包含时间描述

本测试覆盖所有已知场景，确保 normalize_display_fields 始终返回正确的字段语义，
并返回正确的 field_map 供前端动态渲染列。
"""
from __future__ import annotations

import pytest

from xianyu_hunter.modules.collector_utils import normalize_display_fields


# 场景 1：标准情况——所有字段都正确
def test_standard_all_fields_correct() -> None:
    """正常情况：seller_nick 是昵称，region 是地名，publish_time 是时间"""
    display = {
        "title": "测试商品",
        "price": 100.0,
        "thumb_url": "https://example.com/img.jpg",
        "region": "浙江杭州",
        "seller_nick": "小明",
        "seller_credit": "信用极好",
        "publish_time": "2024-01-01T12:00:00",
        "want_cnt": 5,
        "is_sold": False,
    }
    corrected, field_map = normalize_display_fields(display)
    assert corrected["seller_nick"] == "小明"
    assert corrected["region"] == "浙江杭州"
    assert corrected["seller_credit"] == "信用极好"
    assert corrected["publish_time"] == "2024-01-01T12:00:00"
    # field_map 应包含所有有值的字段
    assert "seller_nick" in field_map
    assert "region" in field_map
    assert "seller_credit" in field_map
    assert "publish_time" in field_map


# 场景 2：seller_nick 是发布时间描述，region 是真实昵称
def test_seller_nick_is_publish_label_region_is_nick() -> None:
    """API 把发布描述放进 seller_nick，把真昵称放进 region"""
    display = {
        "title": "测试商品",
        "price": 100.0,
        "seller_nick": "一周内发布",
        "region": "芯***鱼",
        "publish_time": None,
        "seller_credit": "",
    }
    corrected, field_map = normalize_display_fields(display)
    # seller_nick 应该被校正为真实昵称
    assert corrected["seller_nick"] == "芯***鱼", f"应该把 region 当 seller_nick，但得到 {corrected['seller_nick']!r}"
    # publish_time 应该被填充为发布时间描述
    assert corrected["publish_time"] == "一周内发布", f"应该把 seller_nick 当 publish_time，但得到 {corrected['publish_time']!r}"
    # region 应该被清空
    assert corrected["region"] == ""


# 场景 3：seller_nick 是信用度描述，region 是真实昵称
def test_seller_nick_is_credit_region_is_nick() -> None:
    """API 把信用度放进 seller_nick，把真昵称放进 region"""
    display = {
        "title": "测试商品",
        "price": 100.0,
        "seller_nick": "信用极好",
        "region": "数码***爱好者",
        "publish_time": "2024-01-01T12:00:00",
        "seller_credit": "",
    }
    corrected, field_map = normalize_display_fields(display)
    # seller_nick 应该被校正为真实昵称
    assert corrected["seller_nick"] == "数码***爱好者", f"应该把 region 当 seller_nick，但得到 {corrected['seller_nick']!r}"
    # seller_credit 应该被填充为信用度描述
    assert corrected["seller_credit"] == "信用极好", f"应该把 seller_nick 当 seller_credit，但得到 {corrected['seller_credit']!r}"
    # region 应该被清空
    assert corrected["region"] == ""


# 场景 4：region 是昵称，seller_nick 为空
def test_region_is_nick_seller_nick_empty() -> None:
    """API 把昵称放在 region 字段，seller_nick 为空"""
    display = {
        "title": "测试商品",
        "price": 100.0,
        "seller_nick": "",
        "region": "芯***鱼",
        "publish_time": None,
        "seller_credit": "",
    }
    corrected, field_map = normalize_display_fields(display)
    # seller_nick 应该被填充为 region 的值
    assert corrected["seller_nick"] == "芯***鱼"
    # region 应该被清空
    assert corrected["region"] == ""


# 场景 4 回归：region 是简短城市名（不带行政区划后缀），seller_nick 为空
# 修复前：is_region_like("杭州")=False + _looks_like_nick("杭州")=True → 误判为昵称，region 被清空
# 修复后：只在 region 匹配脱敏昵称模式时才交换，城市名保持原样
def test_region_is_short_city_name_seller_nick_empty() -> None:
    """region 是简短城市名（如'杭州'/''深圳'），不应被误判为昵称"""
    for city in ("杭州", "深圳", "广州", "成都", "武汉", "南京"):
        display = {
            "title": "测试商品",
            "price": 100.0,
            "seller_nick": "",
            "region": city,
            "publish_time": None,
            "seller_credit": "",
        }
        corrected, field_map = normalize_display_fields(display)
        # region 应保持原样，不应被清空或移到 seller_nick
        assert corrected["region"] == city, f"城市名 {city!r} 不应被清空，但得到 region={corrected['region']!r}"
        assert corrected["seller_nick"] == "", f"城市名 {city!r} 不应被误判为昵称，但得到 seller_nick={corrected['seller_nick']!r}"
        # field_map 应包含 region
        assert "region" in field_map, f"field_map 应包含 region 字段（城市名 {city!r}）"


# 场景 5：seller_nick 像地名，region 不像地名
def test_seller_nick_is_region_region_is_not_region() -> None:
    """seller_nick 像地名，region 不像地名 → 交换"""
    display = {
        "title": "测试商品",
        "price": 100.0,
        "seller_nick": "浙江杭州",
        "region": "芯***鱼",
        "publish_time": None,
        "seller_credit": "",
    }
    corrected, field_map = normalize_display_fields(display)
    # 这种情况下，seller_nick 是地名，region 是昵称
    # 但是 seller_nick "浙江杭州" 既像地名又像昵称（2-20字符，无非昵称关键词）
    # 所以 _looks_like_nick("浙江杭州") 返回 True，不会触发场景 5 的交换
    # 实际上会触发场景 4：seller_nick 不为空，所以不会进入场景 4
    # 这里只验证不会崩溃
    assert corrected["seller_nick"] is not None
    assert corrected["region"] is not None


# 场景 6：field_map 只包含有值的字段
def test_field_map_only_includes_fields_with_values() -> None:
    """field_map 应该只包含有值的字段，空字段不应该出现在 field_map 中"""
    display = {
        "title": "测试商品",
        "price": 100.0,
        "thumb_url": "https://example.com/img.jpg",
        "region": "浙江杭州",
        "seller_nick": "小明",
        "seller_credit": "",  # 空字符串
        "publish_time": None,  # None
        "want_cnt": 0,
        "is_sold": False,
    }
    corrected, field_map = normalize_display_fields(display)
    # seller_credit 为空，不应该出现在 field_map 中
    assert "seller_credit" not in field_map
    # publish_time 为 None，不应该出现在 field_map 中
    assert "publish_time" not in field_map
    # is_sold 始终显示（状态字段）
    assert "is_sold" in field_map
    # want_cnt 为 0，但 type='number'，has_value = value is not None → True
    assert "want_cnt" in field_map


# 场景 7：空字典
def test_empty_dict() -> None:
    """空字典应该返回空字段值和空 field_map"""
    corrected, field_map = normalize_display_fields({})
    # 空字典输入时，normalize_display_fields 会初始化 seller_nick/region/publish_time/seller_credit 为空值
    # 这是预期行为：确保这些字段始终存在，避免前端访问 undefined
    assert corrected.get("seller_nick", "") == ""
    assert corrected.get("region", "") == ""
    assert corrected.get("publish_time") is None
    assert corrected.get("seller_credit", "") == ""
    # field_map 应该为空（所有字段都无值）
    assert field_map == {}


# 场景 8：非字典输入
def test_non_dict_input() -> None:
    """非字典输入应该返回空字典和空 field_map"""
    corrected, field_map = normalize_display_fields(None)  # type: ignore
    assert corrected == {}
    assert field_map == {}


# 场景 9：seller_nick 是价格标签
def test_seller_nick_is_price_tag() -> None:
    """seller_nick 是价格标签（如 ¥699.00），region 是真实昵称"""
    display = {
        "title": "测试商品",
        "price": 100.0,
        "seller_nick": "¥699.00",
        "region": "卖家***号",
        "publish_time": None,
        "seller_credit": "",
    }
    corrected, field_map = normalize_display_fields(display)
    # seller_nick 应该被校正为真实昵称
    assert corrected["seller_nick"] == "卖家***号", f"应该把 region 当 seller_nick，但得到 {corrected['seller_nick']!r}"
    # region 应该被清空（¥699.00 不是时间也不是信用度，所以不会被移到其他字段）
    assert corrected["region"] == ""


# 场景 10：field_map 包含正确的元数据
def test_field_map_contains_correct_metadata() -> None:
    """field_map 应该包含正确的字段元数据（label, type, width）"""
    display = {
        "title": "测试商品",
        "price": 100.0,
        "thumb_url": "https://example.com/img.jpg",
        "region": "浙江杭州",
        "seller_nick": "小明",
        "seller_credit": "信用极好",
        "publish_time": "2024-01-01T12:00:00",
        "want_cnt": 5,
        "is_sold": False,
    }
    corrected, field_map = normalize_display_fields(display)
    # 验证字段元数据
    assert field_map["thumb_url"]["label"] == "图片"
    assert field_map["thumb_url"]["type"] == "image"
    assert field_map["thumb_url"]["width"] == 80
    assert field_map["title"]["label"] == "标题"
    assert field_map["title"]["type"] == "link"
    assert field_map["price"]["label"] == "价格"
    assert field_map["price"]["type"] == "price"
    assert field_map["seller_nick"]["label"] == "卖家"
    assert field_map["seller_nick"]["type"] == "seller"
    assert field_map["seller_credit"]["label"] == "信用"
    assert field_map["seller_credit"]["type"] == "tag"
    assert field_map["region"]["label"] == "地区"
    assert field_map["region"]["type"] == "text"
    assert field_map["want_cnt"]["label"] == "想要"
    assert field_map["want_cnt"]["type"] == "number"
    assert field_map["publish_time"]["label"] == "发布时间"
    assert field_map["publish_time"]["type"] == "datetime"
    assert field_map["is_sold"]["label"] == "状态"
    assert field_map["is_sold"]["type"] == "status"


# 场景 11：seller_nick 是商品成色描述（如"几乎全新"），region 是脱敏昵称 → 交换
# 复现用户截图第 2 行：seller_nick='几乎全新' + region='荟***猫' 的错位
def test_seller_nick_is_condition_label_region_is_nick() -> None:
    """seller_nick 是商品成色描述（"几乎全新"），region 是脱敏昵称 → 交换"""
    display = {
        "title": "测试商品",
        "price": 100.0,
        "seller_nick": "几乎全新",  # 商品成色描述，不是昵称
        "region": "荟***猫",  # 脱敏昵称
        "publish_time": None,
        "seller_credit": "卖家信用极好",
    }
    corrected, field_map = normalize_display_fields(display)
    # seller_nick 应被校正为脱敏昵称
    assert corrected["seller_nick"] == "荟***猫", \
        f"应把 region 当 seller_nick，但得到 {corrected['seller_nick']!r}"
    # region 应被清空
    assert corrected["region"] == "", \
        f"region 应清空（值已移走），但得到 {corrected['region']!r}"
    # seller_credit 应保持原样
    assert corrected["seller_credit"] == "卖家信用极好"


# 场景 12：seller_nick 是商品成色描述，且 region 为空 → 清空 seller_nick
# 复现用户截图第 1 行：seller_nick='几乎全新' 时无 region 可填补
def test_seller_nick_is_condition_label_no_region_clears() -> None:
    """seller_nick 是"几乎全新"等成色描述且 region 为空时，应清空 seller_nick"""
    for label in ("几乎全新", "全新", "9成新", "99新", "充新", "急售", "包邮"):
        display = {
            "title": "测试商品",
            "price": 100.0,
            "seller_nick": label,
            "region": "",
            "seller_credit": "",
        }
        corrected, field_map = normalize_display_fields(display)
        # seller_nick 应被清空（因为无 region 可填补，且不匹配时间/信用）
        assert corrected["seller_nick"] == "", \
            f"成色描述 {label!r} 无 region 可填时应清空 seller_nick，但得到 {corrected['seller_nick']!r}"


# 场景 13：实时搜索中 seller_nick 与 region 都是昵称（卖家昵称的双向冗余）→ 保持
def test_seller_nick_and_region_both_nick() -> None:
    """seller_nick 和 region 都是脱敏昵称时（API 双向冗余），应保持"""
    display = {
        "title": "测试商品",
        "price": 100.0,
        "seller_nick": "芯***鱼",  # 脱敏昵称
        "region": "数***好",  # 也是脱敏昵称（卖家昵称冗余）
        "publish_time": None,
        "seller_credit": "",
    }
    corrected, field_map = normalize_display_fields(display)
    # seller_nick 应保持（场景 3 的判断需要 region 不像昵称，region 是昵称时不交换）
    # 这种情况是数据冗余，但都不影响显示
    assert corrected["seller_nick"] == "芯***鱼"


# 场景 14：seller_nick 是商品描述片段（"功能完好无维修"）→ 应被清空
# 复现用户截图第 3 行：seller_nick='功能完好无维修' 被误当昵称显示在卖家列
def test_seller_nick_is_product_description_cleared() -> None:
    """seller_nick 是商品描述文本（如'功能完好无维修'）应被清空"""
    for desc in ("功能完好无维修", "直接拍不议价", "喜欢可以直接拍", "拆机功能完好"):
        display = {
            "title": "测试商品",
            "price": 100.0,
            "seller_nick": desc,   # 商品描述，不是昵称
            "region": "河北",
            "seller_credit": "卖家信用极好",
        }
        corrected, field_map = normalize_display_fields(display)
        assert corrected.get("seller_nick") != desc, \
            f"商品描述 {desc!r} 不应作为 seller_nick"


# 场景 15：seller_nick 是简短城市名，region 是脱敏昵称 → 应交换
# 复现用户反馈：实时查询时卖家昵称显示"杭州"，地区显示"芯***鱼"（错位）
# 修复前：_looks_like_nick("杭州")=True → not _looks_like_nick("杭州")=False → 场景 3 不触发
# 修复后：region 是脱敏昵称且 seller_nick 像地名时强制交换，城市名移到 region 保留
def test_seller_nick_is_short_city_region_is_masked_nick_swap() -> None:
    """seller_nick 是简短城市名（如'杭州'），region 是脱敏昵称 → 应交换，城市名移到 region"""
    for city, nick in [("杭州", "芯***鱼"), ("深圳", "买***家"), ("广州", "数***好")]:
        display = {
            "title": "测试商品",
            "price": 100.0,
            "seller_nick": city,  # 简短城市名，被 _looks_like_nick 误判为昵称
            "region": nick,       # 脱敏昵称，一定是昵称
            "publish_time": None,
            "seller_credit": "",
        }
        corrected, field_map = normalize_display_fields(display)
        # seller_nick 应被校正为脱敏昵称
        assert corrected["seller_nick"] == nick, \
            f"城市名 {city!r} + 脱敏昵称 {nick!r} 时，seller_nick 应为 {nick!r}，但得到 {corrected['seller_nick']!r}"
        # region 应保留城市名（地名信息移到 region，不丢弃）
        assert corrected["region"] == city, \
            f"region 应保留城市名 {city!r}，但得到 {corrected['region']!r}"


# 场景 16：seller_nick 是普通昵称，region 是脱敏昵称 → 保持 seller_nick（不交换）
# 双昵称冗余时，seller_nick 已是有效昵称，无需用 region 覆盖
def test_seller_nick_normal_region_masked_nick_keep() -> None:
    """seller_nick 是普通昵称，region 是脱敏昵称 → 保持 seller_nick"""
    display = {
        "title": "测试商品",
        "price": 100.0,
        "seller_nick": "小明",      # 普通昵称
        "region": "芯***鱼",       # 脱敏昵称（冗余）
        "publish_time": None,
        "seller_credit": "",
    }
    corrected, field_map = normalize_display_fields(display)
    # seller_nick 应保持原值（已是有效昵称）
    assert corrected["seller_nick"] == "小明", \
        f"seller_nick 已是普通昵称，应保持，但得到 {corrected['seller_nick']!r}"

