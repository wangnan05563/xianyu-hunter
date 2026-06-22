"""直接验证 normalize_display_fields 函数的动态显示方案

使用模拟的闲鱼 API 响应数据，验证：
1. 字段语义自动校正（seller_nick/region/publish_time/seller_credit 错位修复）
2. field_map 字段元数据生成
3. 前端动态列头渲染所需的数据结构
"""
import json
import sys
from pathlib import Path

# 添加 src 到 path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from xianyu_hunter.modules.collector_utils import normalize_display_fields, FIELD_METADATA


def test_case(name: str, display: dict, expect_nick: str, expect_region: str = "", expect_publish: str = None, expect_credit: str = ""):
    """测试单个用例并打印结果"""
    corrected, field_map = normalize_display_fields(display)

    print(f"\n{'='*60}")
    print(f"测试用例: {name}")
    print(f"{'='*60}")
    print(f"输入 display: {json.dumps(display, ensure_ascii=False, indent=2)}")
    print(f"\n校正后 display: {json.dumps(corrected, ensure_ascii=False, indent=2)}")
    print(f"\nfield_map 字段顺序: {list(field_map.keys())}")
    print(f"field_map 详情:")
    for field, meta in field_map.items():
        print(f"  {field}: {meta}")

    # 验证字段校正
    ok = True
    actual_nick = corrected.get("seller_nick", "")
    actual_region = corrected.get("region", "")
    actual_publish = corrected.get("publish_time")
    actual_credit = corrected.get("seller_credit", "")

    if actual_nick != expect_nick:
        print(f"❌ seller_nick 校正失败: 期望 {expect_nick!r}, 实际 {actual_nick!r}")
        ok = False
    else:
        print(f"✅ seller_nick 校正正确: {actual_nick!r}")

    if actual_region != expect_region:
        print(f"❌ region 校正失败: 期望 {expect_region!r}, 实际 {actual_region!r}")
        ok = False
    else:
        print(f"✅ region 校正正确: {actual_region!r}")

    if expect_publish is not None and actual_publish != expect_publish:
        print(f"❌ publish_time 校正失败: 期望 {expect_publish!r}, 实际 {actual_publish!r}")
        ok = False
    elif expect_publish is not None:
        print(f"✅ publish_time 校正正确: {actual_publish!r}")

    if actual_credit != expect_credit:
        print(f"❌ seller_credit 校正失败: 期望 {expect_credit!r}, 实际 {actual_credit!r}")
        ok = False
    else:
        print(f"✅ seller_credit 校正正确: {actual_credit!r}")

    return ok


def main() -> int:
    print("="*60)
    print("normalize_display_fields 动态显示方案验证")
    print("="*60)

    all_ok = True

    # 场景 1：标准情况——所有字段都正确
    all_ok &= test_case(
        "标准情况：所有字段都正确",
        {
            "title": "Switch OLED 二手",
            "price": 1500.0,
            "thumb_url": "https://img.alicdn.com/test.jpg",
            "region": "浙江杭州",
            "seller_nick": "小明",
            "seller_credit": "信用极好",
            "publish_time": "2024-06-22T10:00:00",
            "want_cnt": 5,
            "is_sold": False,
        },
        expect_nick="小明",
        expect_region="浙江杭州",
        expect_publish="2024-06-22T10:00:00",
        expect_credit="信用极好",
    )

    # 场景 2：seller_nick 是发布时间描述，region 是真实昵称
    all_ok &= test_case(
        "seller_nick 是发布时间描述，region 是真实昵称",
        {
            "title": "Switch OLED 二手",
            "price": 1500.0,
            "seller_nick": "一周内发布",
            "region": "芯***鱼",
            "publish_time": None,
            "seller_credit": "",
        },
        expect_nick="芯***鱼",
        expect_region="",
        expect_publish="一周内发布",
        expect_credit="",
    )

    # 场景 3：seller_nick 是信用度描述，region 是真实昵称
    all_ok &= test_case(
        "seller_nick 是信用度描述，region 是真实昵称",
        {
            "title": "Switch OLED 二手",
            "price": 1500.0,
            "seller_nick": "信用极好",
            "region": "数码***爱好者",
            "publish_time": "2024-06-22T10:00:00",
            "seller_credit": "",
        },
        expect_nick="数码***爱好者",
        expect_region="",
        expect_publish="2024-06-22T10:00:00",
        expect_credit="信用极好",
    )

    # 场景 4：region 是昵称，seller_nick 为空
    all_ok &= test_case(
        "region 是昵称，seller_nick 为空",
        {
            "title": "Switch OLED 二手",
            "price": 1500.0,
            "seller_nick": "",
            "region": "芯***鱼",
            "publish_time": None,
            "seller_credit": "",
        },
        expect_nick="芯***鱼",
        expect_region="",
    )

    # 场景 5：seller_nick 是价格标签
    all_ok &= test_case(
        "seller_nick 是价格标签",
        {
            "title": "Switch OLED 二手",
            "price": 1500.0,
            "seller_nick": "¥699.00",
            "region": "卖家***号",
            "publish_time": None,
            "seller_credit": "",
        },
        expect_nick="卖家***号",
        expect_region="",
    )

    # 场景 6：模拟 live_links 接口返回的完整 display 结构
    print(f"\n{'='*60}")
    print("模拟 live_links 接口返回的完整结构")
    print(f"{'='*60}")

    # 模拟多个商品的 display 数据
    items_display = [
        # 商品 1：标准情况
        {
            "title": "Switch OLED 白色",
            "price": 1500.0,
            "thumb_url": "https://img.alicdn.com/item1.jpg",
            "region": "浙江杭州",
            "url": "https://www.goofish.com/item?id=123",
            "is_sold": False,
            "publish_time": "2024-06-22T10:00:00",
            "seller_id": "seller_001",
            "seller_nick": "小明",
            "seller_credit": "信用极好",
            "want_cnt": 5,
            "view_cnt": 100,
        },
        # 商品 2：seller_nick 是发布时间描述
        {
            "title": "Switch OLED 黑色",
            "price": 1600.0,
            "thumb_url": "https://img.alicdn.com/item2.jpg",
            "region": "芯***鱼",
            "url": "https://www.goofish.com/item?id=456",
            "is_sold": False,
            "publish_time": None,
            "seller_id": "seller_002",
            "seller_nick": "一周内发布",
            "seller_credit": "",
            "want_cnt": 3,
            "view_cnt": 50,
        },
        # 商品 3：seller_nick 是信用度描述
        {
            "title": "Switch OLED 红蓝",
            "price": 1700.0,
            "thumb_url": "https://img.alicdn.com/item3.jpg",
            "region": "数码***爱好者",
            "url": "https://www.goofish.com/item?id=789",
            "is_sold": True,
            "publish_time": "2024-06-21T10:00:00",
            "seller_id": "seller_003",
            "seller_nick": "信用良好",
            "seller_credit": "",
            "want_cnt": 8,
            "view_cnt": 200,
        },
    ]

    # 模拟 live_links 接口的处理逻辑
    merged_field_map = {}
    corrected_items = []
    for display in items_display:
        corrected, field_map = normalize_display_fields(display)
        merged_field_map.update(field_map)
        corrected_items.append(corrected)

    print(f"\n合并后的 field_map（前端动态渲染列的依据）:")
    for field, meta in merged_field_map.items():
        print(f"  {field}: label={meta['label']}, type={meta['type']}, width={meta.get('width')}")

    print(f"\n校正后的商品列表:")
    for i, item in enumerate(corrected_items):
        print(f"\n商品 {i+1}: {item.get('title', '?')}")
        print(f"  seller_nick:   {item.get('seller_nick', '')!r}")
        print(f"  region:        {item.get('region', '')!r}")
        print(f"  publish_time:  {item.get('publish_time', '')!r}")
        print(f"  seller_credit: {item.get('seller_credit', '')!r}")

    # 验证前端动态列头渲染所需的数据结构
    print(f"\n{'='*60}")
    print("前端动态列头渲染验证")
    print(f"{'='*60}")

    # 模拟前端根据 field_map 生成列定义
    print(f"\n前端根据 field_map 生成的列:")
    for field, meta in merged_field_map.items():
        print(f"  列 {meta['label']} (字段: {field}, 类型: {meta['type']}, 宽度: {meta.get('width', '自适应')})")

    print(f"\n{'='*60}")
    if all_ok:
        print("✅ 所有测试用例通过！动态显示方案验证成功。")
    else:
        print("❌ 部分测试用例失败！")
    print(f"{'='*60}")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
