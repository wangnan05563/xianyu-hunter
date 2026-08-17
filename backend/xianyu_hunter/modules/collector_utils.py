"""采集器辅助工具函数

从 collector.py 提取的纯函数，无浏览器/采集器依赖，便于测试和复用。
"""
from __future__ import annotations

import re
from typing import Any

from xianyu_hunter.infra.logger import get_logger

logger = get_logger()


def extract_item_id(href: str) -> str:
    """从 URL 中提取商品 ID

    支持格式：
    - /item?id=123456
    - /item/123456
    - ?itemId=123456
    """
    if not href:
        return ""
    m = re.search(r"(?:itemId|id)=(\d+)", href)
    if m:
        return m.group(1)
    m = re.search(r"/item/(\d+)", href)
    if m:
        return m.group(1)
    return ""


def check_item_sold(raw: dict) -> bool:
    """从 API 响应中检测商品是否已售出

    闲鱼搜索 API 返回的数据中可能包含以下已售标识：
    - status: "sold" 或 "offline"
    - soldOut: true
    - itemStatus: 2 (已售)
    """
    if not raw:
        return False
    status = str(raw.get("status", "")).lower()
    if status in ("sold", "offline", "已售", "下架"):
        return True
    if raw.get("soldOut") or raw.get("sold_out") or raw.get("isSold"):
        return True
    item_status = raw.get("itemStatus", raw.get("item_status"))
    if item_status is not None and int(item_status) == 2:
        return True
    return False


# 页面文本检测已售的关键词列表（详情页/DOM 卡片/抢单前复用）
# 为什么集中维护：闲鱼前端文案多次变更，分散在 3 个文件的关键词列表容易漏改，
# 统一常量确保任一处发现新文案后全局生效
# 历史遗漏案例：2026-06-29 发现商品 1058031608014 详情页显示"卖掉了"但被误判为在售，
# 原因是 _detail.py 关键词列表只有"已售出"等，未覆盖新文案"卖掉了"
SOLD_TEXT_KEYWORDS: tuple[str, ...] = (
    "已售",
    "已售出",
    "已售完",
    "已售罄",
    "宝贝已售",
    "商品已售",
    "已下架",
    "已卖出",
    # 闲鱼新版文案：详情页参数区块下方直接显示"卖掉了"（无"已"前缀）
    "卖掉了",
    # 商品被卖家删除/不存在时的闲鱼提示文案
    "宝贝不存在",
    "宝贝走丢了",
    "该宝贝不存在",
    "商品不存在",
    "已删除",
    "已被删除",
    # 2026-06-29 新增：闲鱼新版下架文案，商品被卖家删除时页面显示"糟糕！宝贝被删掉了"
    # 之前 detail() 因 title 取到 document.title="闲鱼 - 闲不住？上闲鱼！"，
    # 被首页标题检测误判为 cookie 失效，返回 None 导致 is_sold 无法更新
    "宝贝被删掉了",
    "被删掉了",
)

# 下架/被删除专用关键词：详情页是错误页（HTTP 200 + URL 不变 + body 显示提示文案），
# 无法提取 title/price 等商品字段。与 SOLD_TEXT_KEYWORDS 区分：
# - SOLD_TEXT_KEYWORDS 包含"已售"等正常显示的已售商品文案（详情页仍可提取字段）
# - DELISTED_TEXT_KEYWORDS 仅包含"商品不存在/被删除"等错误页文案（详情页无法提取字段）
# detail() 用此列表做早期返回，避免空 title/price 覆盖 items 表已有数据
DELISTED_TEXT_KEYWORDS: tuple[str, ...] = (
    "宝贝不存在",
    "宝贝走丢了",
    "该宝贝不存在",
    "商品不存在",
    "已删除",
    "已被删除",
    "宝贝被删掉了",
    "被删掉了",
)


def check_text_sold(text: str) -> bool:
    """从页面文本检测商品是否已售/已删除

    供详情页采集、DOM 卡片检测、抢单前两阶段检测复用，
    避免三处维护独立关键词列表导致漏检。
    """
    if not text:
        return False
    return any(kw in text for kw in SOLD_TEXT_KEYWORDS)


def check_text_delisted(text: str) -> bool:
    """从页面文本检测商品是否被删除/不存在（详情页是错误页）

    与 check_text_sold 区分：本函数仅识别"商品被删除/不存在"等错误页文案，
    这些场景下详情页无法提取 title/price 等字段，detail() 据此做早期返回，
    避免空值覆盖 items 表已有数据。
    """
    if not text:
        return False
    return any(kw in text for kw in DELISTED_TEXT_KEYWORDS)


def parse_price_from_text(text: str) -> float:
    """从文本中提取价格数字

    闲鱼详情页/搜索卡片的 price 元素常将整数与小数部分拆到不同子元素，
    inner_text() 返回 "123\\n.45" 这样的文本。原正则 \\d+\\.?\\d* 跨不过换行，
    只能匹配到 "123" 丢失小数。这里先剥离所有空白与逗号再匹配，确保拆行价格被合并。

    支持"万"单位：与 _coerce_price 保持一致，如"1.2万"→12000.0，
    避免详情页显示"1.2万"时被解析为 1.2，与官网相差 10000 倍。
    """
    cleaned = re.sub(r"[\s,]+", "", text)
    m = re.search(r"\d+\.?\d*", cleaned)
    if not m:
        return 0.0
    price = float(m.group())
    if "万" in cleaned:
        price *= 10000
    return price


# 中国地名正则：用于判断 region 字段是否为真实地名
# 闲鱼 API 的 region 通常是"浙江"、"浙江杭州"格式
_REGION_PATTERN = re.compile(
    # 含行政区划后缀（省/市/区/县等）
    r'.*(?:省|市|自治区|特别行政区|盟|地区|县|旗|区|镇)$|'
    # 以省份/直辖市/特别行政区名开头
    r'^(?:北京|天津|上海|重庆|河北|山西|辽宁|吉林|黑龙江|江苏|浙江|安徽|福建|江西|山东|河南|湖北|湖南|广东|广西|海南|四川|贵州|云南|西藏|陕西|甘肃|青海|宁夏|新疆|香港|澳门|台湾|内蒙古)'
)

# 常见城市名（省会城市 + 计划单列市）
# 闲鱼 API 的 region 经常是简短城市名（如"杭州"、"深圳"），不带行政区划后缀，
# 但确实是地名，不应被误判为昵称。维护此列表以补充 _REGION_PATTERN 的不足。
_COMMON_CITIES = {
    # 直辖市
    "北京", "天津", "上海", "重庆",
    # 省会城市
    "石家庄", "太原", "沈阳", "长春", "哈尔滨", "南京", "杭州", "合肥", "福州", "南昌",
    "济南", "郑州", "武汉", "长沙", "广州", "海口", "成都", "贵阳", "昆明", "拉萨",
    "西安", "兰州", "西宁", "银川", "乌鲁木齐", "南宁", "呼和浩特",
    # 计划单列市
    "深圳", "大连", "青岛", "宁波", "厦门",
}


def is_region_like(text: str) -> bool:
    """判断文本是否像中国地名（省份/直辖市开头或含行政区划后缀，或常见城市名）"""
    if not text:
        return False
    if text in _COMMON_CITIES:
        return True
    return bool(_REGION_PATTERN.match(text))


# 常见品牌别名：用于两类兜底
# 1. 搜索 API 没有独立 brand 字段时，从标题推断品牌
# 2. API 把品牌/店铺标签误放进 seller_nick，且 region 是脱敏昵称时识别错位
# 覆盖范围：内存/存储、笔记本/PC、手机、相机、音频、游戏机、外设、其他常见 3C
# 命名约定：canonical 用中文常用名，aliases 含中文简称/英文/常见系列名
_BRAND_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    # === 内存/存储 ===
    ("SK海力士", ("sk海力士", "海力士", "hynix", "skhynix", "现代海力士")),
    ("镁光", ("镁光", "美光", "micron")),
    ("英睿达", ("英睿达", "crucial")),
    ("三星", ("三星", "samsung", "galaxy")),
    ("记忆科技", ("记忆科技", "ramaxel")),
    ("金士顿", ("金士顿", "kingston")),
    ("威刚", ("威刚", "adata")),
    ("光威", ("光威", "gloway")),
    ("亿捷", ("亿捷", "eaget")),
    ("全兴", ("全兴",)),
    # === 笔记本/PC ===
    ("联想", ("联想", "lenovo", "thinkpad", "thinkplus", "thinkbook", "拯救者", "legion")),
    ("戴尔", ("戴尔", "dell")),
    ("惠普", ("惠普", "hp")),
    ("华硕", ("华硕", "asus", "rog", "玩家国度")),
    ("宏碁", ("宏碁", "acer", "predator", "暗影骑士")),
    ("微星", ("微星", "msi")),
    ("外星人", ("外星人", "alienware")),
    ("机械革命", ("机械革命", "mechrevo")),
    ("雷蛇", ("雷蛇", "razer", "blade")),
    ("荣耀", ("荣耀", "honor", "magicbook")),
    ("微软", ("微软", "microsoft", "surface")),
    ("LG", ("lg", "lg电子")),
    ("技嘉", ("技嘉", "gigabyte", "aorus")),
    # === 手机 ===
    ("苹果", ("苹果", "apple", "iphone", "ipad", "macbook", "airpods")),
    ("华为", ("华为", "huawei", "mate")),
    ("小米", ("小米", "xiaomi", "redmi", "红米", "poco")),
    ("OPPO", ("oppo", "欧珀", "find", "reno")),
    ("vivo", ("vivo", "iqoo", "iQOO")),
    ("一加", ("一加", "oneplus")),
    ("realme", ("realme", "真我")),
    ("努比亚", ("努比亚", "nubia", "红魔", "redmagic")),
    ("魅族", ("魅族", "meizu")),
    ("黑鲨", ("黑鲨", "blackshark")),
    ("诺基亚", ("诺基亚", "nokia")),
    ("摩托罗拉", ("摩托罗拉", "motorola", "moto")),
    ("谷歌", ("谷歌", "google", "pixel")),
    ("中兴", ("中兴", "zte")),
    ("Nothing", ("nothing", "nothingphone")),
    # === 相机 ===
    ("佳能", ("佳能", "canon", "eos")),
    ("尼康", ("尼康", "nikon")),
    ("索尼", ("索尼", "sony")),
    # 注：不添加 a7/a7m4/alpha 等型号别名，避免误命中"华为Mate 7"等无关标题
    ("富士", ("富士", "fujifilm", "fuji", "x-t", "x-t4", "x-t5")),
    ("徕卡", ("徕卡", "leica")),
    ("松下", ("松下", "panasonic", "lumix")),
    ("奥林巴斯", ("奥林巴斯", "olympus", "om-d")),
    ("理光", ("理光", "ricoh", "grd", "gr3", "gr2")),
    ("哈苏", ("哈苏", "hasselblad")),
    ("宾得", ("宾得", "pentax")),
    # === 音频 ===
    ("森海塞尔", ("森海塞尔", "sennheiser")),
    ("AKG", ("akg", "爱科技")),
    ("铁三角", ("铁三角", "audio-technica", "audiotechnica")),
    ("Bose", ("bose",)),
    ("Beats", ("beats", "beatsaudio")),
    ("JBL", ("jbl",)),
    ("漫步者", ("漫步者", "edifier")),
    ("水月雨", ("水月雨", "moondrop")),
    # === 游戏机 ===
    ("任天堂", ("任天堂", "nintendo", "switch", "wii", "3ds")),
    ("PlayStation", ("playstation", "ps5", "ps4", "psn")),
    ("Xbox", ("xbox",)),
    ("Steam Deck", ("steam deck", "steamdeck")),
    # === 外设 ===
    ("罗技", ("罗技", "logitech")),
    ("Cherry", ("cherry", "cherrymx")),
    ("IKBC", ("ikbc",)),
    ("Keychron", ("keychron",)),
    ("雷柏", ("雷柏", "rapoo")),
    ("双飞燕", ("双飞燕", "a4tech")),
    # === 其他常见 3C ===
    ("大疆", ("大疆", "dji", "mavic", "phantom")),
    ("Dyson", ("dyson", "戴森")),
    ("Kindle", ("kindle",)),
    ("Anker", ("anker",)),
    ("绿联", ("绿联", "ugreen")),
)

_BRAND_GENERIC_SUFFIXES = (
    "官方旗舰店", "旗舰店", "专卖店", "专营店", "官方店", "官方",
    "数码优品", "数码", "优品", "严选", "正品", "科技", "电子",
    "电脑", "手机", "配件", "小店", "店铺", "店",
)


def _compact_text(text: str) -> str:
    """压缩文本用于宽松匹配：去掉空白/常见分隔符并转小写。"""
    return re.sub(r"[\s\-_·•/|,，.。:：;；()（）【】\[\]{}]+", "", (text or "").lower())


def _strip_brand_suffix(value: str) -> str:
    candidate = (value or "").strip()
    for suffix in _BRAND_GENERIC_SUFFIXES:
        if candidate.endswith(suffix) and len(candidate) > len(suffix):
            candidate = candidate[: -len(suffix)].strip()
            break
    return candidate


def _brand_candidate_matches_title(candidate: str, title: str) -> bool:
    """判断候选文本是否更像商品品牌，而不是卖家昵称。"""
    candidate = (candidate or "").strip()
    title = (title or "").strip()
    if not candidate or not title:
        return False
    if is_region_like(candidate) or _MASKED_NICK_PATTERN.match(candidate):
        return False

    compact_title = _compact_text(title)
    compact_candidate = _compact_text(_strip_brand_suffix(candidate) or candidate)
    if len(compact_candidate) >= 2 and compact_candidate in compact_title:
        return True

    compact_raw_candidate = _compact_text(candidate)
    for _canonical, aliases in _BRAND_ALIASES:
        alias_hits_candidate = any(_compact_text(a) in compact_raw_candidate for a in aliases)
        alias_hits_title = any(_compact_text(a) in compact_title for a in aliases)
        if alias_hits_candidate and alias_hits_title:
            return True
    return False


def infer_brand_from_title(title: str) -> str:
    """从标题中推断常见品牌；无命中时返回空字符串。"""
    compact_title = _compact_text(title)
    if not compact_title:
        return ""
    for canonical, aliases in _BRAND_ALIASES:
        if any(_compact_text(alias) in compact_title for alias in aliases):
            return canonical
    return ""


def normalize_display_brand(
    brand: str | None,
    title: str = "",
    seller_candidate: str = "",
) -> str:
    """校验展示层品牌，避免旧搜索/任务关键词品牌污染当前商品。

    task_links.display.brand 是冗余展示字段，可能来自搜索 API、标题推断或历史旧值。
    当当前标题已经可用时，品牌必须能被标题或标题中的别名解释；否则重新按标题/卖家候选
    推断，仍无命中则清空。
    """
    brand = str(brand or "").strip()
    title = str(title or "").strip()
    seller_candidate = str(seller_candidate or "").strip()

    if brand and (not title or _brand_candidate_matches_title(brand, title)):
        return brand
    if _brand_candidate_matches_title(seller_candidate, title):
        return seller_candidate
    inferred = infer_brand_from_title(title)
    if inferred:
        return inferred
    return "" if title else brand


def _find_first_text_by_keys(obj: Any, keys: set[str], depth: int = 0, max_depth: int = 3) -> str:
    """递归查找第一个匹配 keys 的文本字段

    重构说明：按 obj 类型分派到独立函数，避免主函数嵌套过深导致认知复杂度过高（S3776）。
    """
    if depth > max_depth:
        return ""
    if isinstance(obj, dict):
        return _find_text_in_dict(obj, keys, depth, max_depth)
    if isinstance(obj, list):
        return _find_text_in_list(obj, keys, depth, max_depth)
    return ""


def _find_text_in_dict(
    obj: dict, keys: set[str], depth: int, max_depth: int
) -> str:
    """先在本层 key 中查找，再递归 values

    为什么先本层再递归：本层 key 命中即返回，避免无谓的深递归；
    只有本层未命中时才向 values 下钻，符合"最短路径优先"。
    """
    for key, value in obj.items():
        # 归一化 key：去除非字母数字字符并小写，应对 camelCase/snake_case/含分隔符的差异
        normalized_key = re.sub(r"[^a-z0-9]", "", str(key).lower())
        if normalized_key in keys and isinstance(value, str) and value.strip():
            return value.strip()
    for value in obj.values():
        found = _find_first_text_by_keys(value, keys, depth + 1, max_depth)
        if found:
            return found
    return ""


def _find_text_in_list(
    obj: list, keys: set[str], depth: int, max_depth: int
) -> str:
    """限制前 20 个元素避免大列表性能问题

    为什么限制 20：商品 raw 数据中列表字段通常较短（图片、标签等），
    20 个元素足够覆盖；无限遍历可能遇到超大列表导致性能退化。
    """
    for value in obj[:20]:
        found = _find_first_text_by_keys(value, keys, depth + 1, max_depth)
        if found:
            return found
    return ""


def extract_brand(raw: dict | None, title: str = "", seller_candidate: str = "") -> str:
    """提取商品品牌。

    优先读取搜索 API 的品牌字段；没有稳定字段时，从标题和 seller_candidate
    做保守推断。seller_candidate 只有在它明显出现在标题/品牌别名里时才会被当作品牌，
    避免把普通卖家昵称误标为品牌。
    """
    brand_keys = {
        "brand", "brandname", "brandtext", "brandtitle", "brandvalue",
        "branddesc", "manufacturer", "maker",
    }
    raw_brand = _find_first_text_by_keys(raw or {}, brand_keys)
    if raw_brand and raw_brand not in {"其他", "其它", "other", "OTHER"}:
        raw_brand = raw_brand.strip()
        if not title or _brand_candidate_matches_title(raw_brand, title):
            return raw_brand

    if _brand_candidate_matches_title(seller_candidate, title):
        return seller_candidate.strip()

    return infer_brand_from_title(title)


def extract_seller_nick(raw: dict) -> tuple[str, str]:
    """从搜索 API 响应中提取卖家昵称和地区

    闲鱼搜索 API 在不同商品上的字段语义并不稳定，至少观察到两种异常：

    1. region 字段实际是用户昵称（如"芯***鱼"），无独立 nick 字段
       → 表现为"地区"列显示脱敏昵称，"卖家"列空
    2. userNick/sellerNick 字段实际是发布时间描述（如"一周内发布"），
       region 字段才是真实昵称
       → 表现为"卖家"列显示"一周内发布"，"地区"列显示脱敏昵称

    这两种情况都会导致 seller/region/publish_time 三列整体错位。
    主函数只负责场景编排，候选字段扫描与交换判断分别下沉到辅助函数
    以降低认知复杂度（S3776）。
    """
    nick = _extract_first_nick_candidate(raw)
    raw_region = raw.get("region", "")

    # 场景 1：nick 为空且 region 不像地名 → 把 region 当 nick
    # S1066: 合并嵌套 if，两个条件同属"是否把 region 当作 nick"的判断
    if not nick and raw_region and not is_region_like(raw_region):
        nick = raw_region.strip()
        raw_region = ""

    # 场景 2：nick 不像昵称（时间/价格/标签/地名）且 region 像昵称 → 交换
    # 详细判断下沉到 _should_swap_extracted_nick_with_region，避免主函数嵌套过深
    if nick and raw_region and _should_swap_extracted_nick_with_region(nick, raw_region):
        nick, raw_region = raw_region, nick

    return nick, raw_region


def _extract_first_nick_candidate(raw: dict) -> str:
    """按候选字段顺序取第一个非空字符串作为 nick

    为什么不直接 raw.get(...)：闲鱼 API 不同版本字段名差异大，
    需要按优先级顺序尝试多个字段名，命中即返回。
    """
    for nk in ("userNick", "sellerNick", "nick", "userNickname", "sellerNickName"):
        v = raw.get(nk)
        if v and isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _should_swap_extracted_nick_with_region(nick: str, region: str) -> bool:
    """场景 2 判断：nick 不像昵称且 region 像昵称时交换两者

    两条命中路径（任一即可）：
    - region 是脱敏昵称且 nick 明显不是昵称（地名/时间/标签）
    - nick 像发布标签且 region 不像地名且 region 像昵称

    例外：nick 也是脱敏昵称时，视为数据冗余，不交换（两个都是昵称）
    """
    region_is_masked_nick = bool(_MASKED_NICK_PATTERN.match(region))
    nick_is_masked_nick = bool(_MASKED_NICK_PATTERN.match(nick))
    nick_is_non_nick = is_region_like(nick) or _looks_like_publish_label(nick)
    return (
        (region_is_masked_nick and not nick_is_masked_nick and nick_is_non_nick)
        or (
            _looks_like_publish_label(nick)
            and not is_region_like(region)
            and _looks_like_nick(region)
        )
    )


# 闲鱼搜索结果中常混入"非昵称"字段的关键词：
# - 时间描述：N分钟/小时/天/周/月前发布
# - 价格标签：含 ¥、元
# - 通用标签：包邮、已售、信用、极好、良好、优秀
# - 商品成色描述：几乎全新 / 全新 / 充新 / 99新 / 9X新 / X成新（这些是描述商品状态的标签，不应作为昵称）
# - 交易描述：急售、秒发、正品、自提、议价、小刀
# - 商品描述片段：功能/完好/无损/维修/拆机/原装/配件/直接拍/不议价等
#   （闲鱼 DOM 提取时，标题或描述文本可能被误截取为 seller_nick 段落，
#    如"功能完好无维修"、"直接拍不议价"等，这些不是昵称）
_NON_NICK_PATTERN = re.compile(
    r"(?:分钟前|小时前|天前|周前|月前|前发布|内发布|包邮|已售|信用|极好|良好|优秀|¥|元"
    r"|几乎全新|^全新$|^充新$|\d{1,2}新|\d成新|\d\.\d成新"
    r"|急售|秒发|正品|自提|议价|小刀|大刀"
    r"|功能完好|无损|无维修|拆机|原装|配件"
    r"|直接拍|不议价|不退|非诚勿扰|喜欢可以"
    r"|需要|想要|感兴趣)"
)

# 闲鱼脱敏昵称的典型模式：1-2个汉字 + 至少2个* + 1-2个汉字
_MASKED_NICK_PATTERN = re.compile(
    r"^[\u4e00-\u9fa5A-Za-z0-9_]{1,3}\*{2,}[\u4e00-\u9fa5A-Za-z0-9_]*$"
)


def _looks_like_publish_label(text: str) -> bool:
    """判断文本是否是发布时间/价格/标签描述（不应该是昵称）"""
    if not text:
        return False
    return bool(_NON_NICK_PATTERN.search(text))


def _looks_like_nick(text: str) -> bool:
    """判断文本是否像昵称（含被脱敏的"x***y"格式）"""
    if not text:
        return False
    # 脱敏昵称：芯***鱼 / 买***家 / 数码***爱好者
    if _MASKED_NICK_PATTERN.match(text):
        return True
    # 短字符串（2-20 字符），无明显时间/价格关键词
    if 2 <= len(text) <= 20 and not _NON_NICK_PATTERN.search(text):
        return True
    return False


# 信用度关键词：闲鱼 API 返回的卖家信用度通常是"极好/良好/优秀/信誉极好"等
_CREDIT_PATTERN = re.compile(r"(?:信用|极好|良好|优秀|信誉)")


def _looks_like_credit(text: str) -> bool:
    """判断文本是否像信用度描述"""
    if not text:
        return False
    return bool(_CREDIT_PATTERN.search(text))


# 发布时间描述：闲鱼 API 可能返回"X天前发布"、"一周内发布"等时间描述
_PUBLISH_LABEL_PATTERN = re.compile(
    r"(?:\d+\s*(?:分钟|小时|天|周|月)前|一周内|\d+\s*天内|刚发|前发布|内发布)"
)


def _looks_like_publish_time(text: str) -> bool:
    """判断文本是否像发布时间描述（相对时间或 ISO 时间戳）"""
    if not text:
        return False
    # ISO 时间戳格式：2024-01-01T12:00:00
    if re.match(r"^\d{4}-\d{2}-\d{2}T", text):
        return True
    # 相对时间描述：X天前发布、一周内发布等
    return bool(_PUBLISH_LABEL_PATTERN.search(text))


# 字段元数据，描述每个字段的显示方式（标签、类型、宽度）  # NOSONAR
# 前端根据此元数据动态渲染列，当接口字段变化时前端展示自动调整
FIELD_METADATA: dict[str, dict[str, Any]] = {
    "thumb_url": {"label": "图片", "type": "image", "width": 80},
    "title": {"label": "标题", "type": "link", "width": None},
    "brand": {"label": "品牌", "type": "text", "width": 100},
    "price": {"label": "价格", "type": "price", "width": 100},
    "seller_nick": {"label": "卖家", "type": "seller", "width": 140},
    "seller_credit": {"label": "信用", "type": "tag", "color": "green", "width": 80},
    "region": {"label": "地区", "type": "text", "width": 100},
    "want_cnt": {"label": "想要", "type": "number", "width": 70},
    "publish_time": {"label": "发布时间", "type": "datetime", "width": 160},
    "is_sold": {"label": "状态", "type": "status", "width": 80},
}


def _swap_seller_nick_with_region(
    seller_nick: str,
    region: str,
    publish_time: str,
    seller_credit: str,
) -> tuple[str, str, str, str]:
    """场景 3：seller_nick 不像昵称且 region 像昵称 → 交换两者

    交换后 old_seller_nick 按其语义归入 publish_time / seller_credit / region / 丢弃。
    返回 (seller_nick, region, publish_time, seller_credit)。

    主函数只负责编排：判断是否交换 + 交换后字段重新分配，
    两个子判断下沉到辅助函数以降低认知复杂度（S3776）。
    """
    if not _should_swap_seller_nick_with_region(seller_nick, region):
        return seller_nick, region, publish_time, seller_credit
    # 交换时，seller_nick 的原始值按其语义归入合适字段
    new_region, new_publish_time, new_credit = _reassign_old_seller_nick(
        seller_nick, publish_time, seller_credit
    )
    return region, new_region, new_publish_time, new_credit


def _should_swap_seller_nick_with_region(seller_nick: str, region: str) -> bool:
    """场景 3 判断：region 是脱敏昵称且 seller_nick 明显不是昵称，或 seller_nick 不像昵称且 region 像昵称"""
    region_is_masked_nick = bool(_MASKED_NICK_PATTERN.match(region))
    seller_nick_is_masked_nick = bool(_MASKED_NICK_PATTERN.match(seller_nick))
    # seller_nick 是否明显不是昵称（地名/时间/信用/价格标签）
    seller_nick_is_non_nick = (
        is_region_like(seller_nick)
        or _looks_like_publish_time(seller_nick)
        or _looks_like_credit(seller_nick)
        or bool(_NON_NICK_PATTERN.search(seller_nick))
    )
    return (
        (region_is_masked_nick and not seller_nick_is_masked_nick and seller_nick_is_non_nick)
        or (not _looks_like_nick(seller_nick) and _looks_like_nick(region))
    )


def _reassign_old_seller_nick(
    old_seller_nick: str, publish_time: str, seller_credit: str
) -> tuple[str, str, str]:
    """交换后把 old_seller_nick 归入合适字段；返回 (region, publish_time, seller_credit)

    归入优先级：发布时间 > 信用度 > 地区 > 丢弃。
    丢弃场景：old_seller_nick 是非昵称关键词（如"几乎全新"），既不是时间/信用/地名。
    """
    # 像时间且 publish_time 为空 → 移到 publish_time
    if _looks_like_publish_time(old_seller_nick) and not publish_time:
        return "", old_seller_nick, seller_credit
    # 像信用且 seller_credit 为空 → 移到 seller_credit
    if _looks_like_credit(old_seller_nick) and not seller_credit:
        return "", publish_time, old_seller_nick
    # 像地名 → 移到 region（保留地名信息）
    if is_region_like(old_seller_nick):
        return old_seller_nick, publish_time, seller_credit
    # 否则丢弃（old_seller_nick 是非昵称关键词）
    return "", publish_time, seller_credit


def _build_field_map(corrected: dict) -> dict[str, dict[str, Any]]:
    """根据 corrected 中实际有值的字段构建元数据映射

    元数据来源 FIELD_METADATA；缺字段或值为空时不返回该字段。
    字段是否有值的判断下沉到 _field_has_value，避免类型分支堆积在循环内（S3776）。
    """
    field_map: dict[str, dict[str, Any]] = {}
    for field, meta in FIELD_METADATA.items():
        # 字段不在 display 中时跳过（如空字典输入时 is_sold 不存在）
        if field not in corrected:
            continue
        if _field_has_value(meta["type"], corrected.get(field)):
            field_map[field] = meta
    return field_map


def _field_has_value(meta_type: str, value: Any) -> bool:
    """判断字段是否有值（不同类型语义不同）

    - status：只要字段存在就显示（False 表示"在售"，是有效值）
    - price/number：非 None 且非 0
    - image/text：truthy 即有值
    """
    if meta_type == "image":
        return bool(value)
    if meta_type == "price":
        return value is not None and value != 0
    if meta_type == "number":
        return value is not None
    if meta_type == "status":
        return True
    return bool(value)


def normalize_display_fields(display: dict) -> tuple[dict, dict]:
    """对 display 字段做全面语义校正，并返回字段元数据

    闲鱼搜索 API 在不同商品上字段语义并不稳定，已观察到以下错位场景：
    1. seller_nick 字段实际是发布时间描述（如"一周内发布"），region 才是真实昵称
    2. seller_nick 字段实际是信用度描述（如"信用极好"），region 才是真实昵称
    3. region 字段实际是用户昵称（如"芯***鱼"），无独立 nick 字段
    4. publish_time 字段为空，但 seller_nick 包含时间描述

    本函数对 display 字段做全面语义校正，确保每个字段都符合其语义：
    - seller_nick 必须是昵称（不能是时间描述/价格/标签/信用度）
    - region 必须是地名（不能是昵称）
    - publish_time 必须是时间（不能是昵称或地区）
    - seller_credit 必须是信用度描述（不能是昵称）

    主函数只负责字段读取与场景编排，每个场景的判断+处理下沉到独立辅助函数
    以降低认知复杂度（S3776）。

    Args:
        display: 原始 display 字典

    Returns:
        (corrected_display, field_map)
        - corrected_display: 校正后的 display 字典
        - field_map: 字段元数据，描述每个字段的显示方式
    """
    if not isinstance(display, dict):
        return {}, {}

    corrected = dict(display)
    title = str(corrected.get("title", "") or "").strip()
    brand = str(corrected.get("brand", "") or "").strip()
    seller_nick = str(corrected.get("seller_nick", "") or "").strip()
    region = str(corrected.get("region", "") or "").strip()
    publish_time = str(corrected.get("publish_time", "") or "").strip()
    seller_credit = str(corrected.get("seller_credit", "") or "").strip()

    brand = normalize_display_brand(brand, title, seller_candidate=seller_nick)

    # 场景 0：seller_nick 实际是品牌/店铺标签，region 是脱敏卖家昵称
    seller_nick, region, brand = _normalize_scene0_brand_label_swap(
        seller_nick, region, brand, title
    )

    # 场景 1：seller_nick 像信用度描述，且 seller_credit 为空 → 移动到 seller_credit
    seller_nick, seller_credit = _normalize_scene1_move_nick_to_credit(
        seller_nick, seller_credit
    )

    # 场景 2：seller_nick 像发布时间描述，且 publish_time 为空 → 移动到 publish_time
    seller_nick, publish_time = _normalize_scene2_move_nick_to_publish_time(
        seller_nick, publish_time
    )

    # 场景 3：seller_nick 不像昵称，且 region 像昵称 → 交换
    if seller_nick and region:
        seller_nick, region, publish_time, seller_credit = _swap_seller_nick_with_region(
            seller_nick, region, publish_time, seller_credit
        )

    # 场景 4：seller_nick 为空，且 region 是脱敏昵称 → 把 region 当 seller_nick
    seller_nick, region = _normalize_scene4_region_to_seller_nick(seller_nick, region)

    # 场景 5：region 不像地名，且 seller_nick 像地名 → 交换
    seller_nick, region = _normalize_scene5_swap_when_region_not_location(
        seller_nick, region
    )

    # 场景 6：seller_nick 命中"非昵称"关键词但没有合适的归属字段 → 清空
    seller_nick = _normalize_scene6_clear_invalid_nick(seller_nick, region)

    # 写回校正后的字段
    corrected["seller_nick"] = seller_nick
    corrected["region"] = region
    corrected["publish_time"] = publish_time or None
    corrected["seller_credit"] = seller_credit
    corrected["brand"] = brand

    return corrected, _build_field_map(corrected)


def _normalize_scene0_brand_label_swap(
    seller_nick: str, region: str, brand: str, title: str
) -> tuple[str, str, str]:
    """场景 0：seller_nick 是品牌/店铺标签且 region 是脱敏卖家昵称

    近期实时搜索可见：seller_nick="镁光数码"/"现代海力士"，region="牧***蓉"/"行***三"。
    把 seller_nick 移到 brand，region 移到 seller_nick，真实地区未知则留空。
    """
    if (
        seller_nick
        and region
        and _MASKED_NICK_PATTERN.match(region)
        and not _MASKED_NICK_PATTERN.match(seller_nick)
        and _brand_candidate_matches_title(seller_nick, title)
    ):
        return region, "", (brand or seller_nick)
    return seller_nick, region, brand


def _normalize_scene1_move_nick_to_credit(
    seller_nick: str, seller_credit: str
) -> tuple[str, str]:
    """场景 1：seller_nick 像信用度描述，且 seller_credit 为空 → 移动到 seller_credit"""
    if seller_nick and not seller_credit and _looks_like_credit(seller_nick):
        return "", seller_nick
    return seller_nick, seller_credit


def _normalize_scene2_move_nick_to_publish_time(
    seller_nick: str, publish_time: str
) -> tuple[str, str]:
    """场景 2：seller_nick 像发布时间描述，且 publish_time 为空 → 移动到 publish_time"""
    if seller_nick and not publish_time and _looks_like_publish_time(seller_nick):
        return "", seller_nick
    return seller_nick, publish_time


def _normalize_scene4_region_to_seller_nick(
    seller_nick: str, region: str
) -> tuple[str, str]:
    """场景 4：seller_nick 为空，且 region 是脱敏昵称 → 把 region 当 seller_nick

    只在 region 明显是脱敏昵称（如"芯***鱼"）时才交换，避免误伤简短城市名
    （如"杭州"、"深圳"不带行政区划后缀，is_region_like 返回 False，
    但 _looks_like_nick 返回 True，会导致 region 被错误清空）。
    """
    if not seller_nick and region and _MASKED_NICK_PATTERN.match(region):
        return region, ""
    return seller_nick, region


def _normalize_scene5_swap_when_region_not_location(
    seller_nick: str, region: str
) -> tuple[str, str]:
    """场景 5：region 不像地名，且 seller_nick 像地名 → 交换两者"""
    if region and seller_nick and not is_region_like(region) and is_region_like(seller_nick):
        return region, seller_nick
    return seller_nick, region


def _normalize_scene6_clear_invalid_nick(seller_nick: str, region: str) -> str:
    """场景 6：seller_nick 命中"非昵称"关键词且 region 无有效值 → 清空

    例如 seller_nick='几乎全新'/'9成新'，既不是时间也不是信用度，
    前面场景已尝试纠正但仍然无法识别时应清空，避免前端误显示。
    """
    if seller_nick and _NON_NICK_PATTERN.search(seller_nick) and not region:
        return ""
    return seller_nick


def parse_search_api_result(result: dict) -> list[dict]:
    """解析搜索 API 返回的商品列表

    尝试多种可能的响应结构：
    - data.data.itemsList
    - data.itemsList
    - data.data.items
    以及递归搜索包含 itemId/title 的列表。

    重构说明：将 inner/data 两层查找拆分为独立函数，主函数只负责分派，
    降低圈复杂度（S3776）。两层日志格式不同，故分别保留独立函数。
    """
    if not result or not isinstance(result, dict):
        return []

    # 尝试已知的字段路径
    data = result.get("data", result)
    if not isinstance(data, dict):
        return []

    # 优先尝试 inner data 层（data.data.xxx），闲鱼 API 常见双层嵌套
    inner = data.get("data", data)
    if isinstance(inner, dict):
        return _extract_items_from_inner(inner, data, result)

    # 回退到 data 层（data.xxx）
    return _extract_items_from_data(data, result)


# 已知的商品列表字段名：闲鱼 API 在不同版本使用不同字段名，按优先级顺序尝试
_KNOWN_ITEM_KEYS = ("itemsList", "itemList", "items", "list", "result", "resultList")


def _extract_items_from_inner(
    inner: dict, data: dict, result: dict
) -> list[dict]:
    """从 inner dict 中提取商品列表，含详细调试日志

    inner 分支比 data 分支多记录 sample keys，因为 inner 是最常见的命中路径，
    需要更详细的日志便于排查字段名不匹配问题。
    """
    for key in _KNOWN_ITEM_KEYS:
        items_list = inner.get(key)
        if isinstance(items_list, list) and items_list:
            # 记录第一个元素的 keys，便于排查字段名不匹配问题
            if isinstance(items_list[0], dict):
                logger.info("parse_search_api_result: key='{}', count={}, sample keys={}",
                            key, len(items_list), list(items_list[0].keys())[:20])
            return items_list
    # 调试：记录实际响应结构（loguru 使用 {} 格式化，不是 %s）
    logger.info(
        "parse_search_api_result: inner keys={}, data keys={}, top keys={}",
        list(inner.keys())[:15], list(data.keys())[:15], list(result.keys())[:15],
    )
    # 递归搜索：在 inner 中查找包含 itemId 的列表
    found = _find_items_recursive(inner, depth=0)
    if found:
        logger.info("parse_search_api_result: 递归搜索找到 {} 个商品", len(found))
        return found
    return []


def _extract_items_from_data(data: dict, result: dict) -> list[dict]:
    """从 data dict 中提取商品列表（inner 层未命中时的回退路径）"""
    for key in _KNOWN_ITEM_KEYS:
        items_list = data.get(key)
        if isinstance(items_list, list) and items_list:
            return items_list
    logger.info(
        "parse_search_api_result: data keys={}, top keys={}",
        list(data.keys())[:15] if isinstance(data, dict) else type(data).__name__,
        list(result.keys())[:15],
    )
    # 递归搜索
    found = _find_items_recursive(data, depth=0)
    if found:
        logger.info("parse_search_api_result: 递归搜索找到 {} 个商品", len(found))
        return found
    return []


def _find_items_recursive(obj: Any, depth: int = 0, max_depth: int = 4) -> list[dict]:
    """递归搜索 dict/list 结构中包含商品特征的列表

    闲鱼 API 可能嵌套在不同层级，此函数做兜底搜索。

    重构说明：按 obj 类型分派到独立函数，避免主函数嵌套过深导致认知复杂度过高（S3776）。
    """
    if depth > max_depth:
        return []
    if isinstance(obj, list):
        return _find_items_in_list(obj, depth, max_depth)
    if isinstance(obj, dict):
        return _find_items_in_dict(obj, depth, max_depth)
    return []


# 商品标识字段：用于判断列表元素是否像商品
_ITEM_KEYS = ("itemId", "id", "item_id", "auctionId", "auction_id")


def _is_item_like(item: Any) -> bool:
    """判断对象是否像商品：直接含 itemId 或在 data 子字典中含 itemId

    闲鱼 resultList 元素可能将商品字段包裹在 data 子字典中，需要两层检查。
    """
    if not isinstance(item, dict):
        return False
    if any(k in item for k in _ITEM_KEYS):
        return True
    sub = item.get("data")
    return isinstance(sub, dict) and any(k in sub for k in _ITEM_KEYS)


def _find_items_in_list(
    obj: list, depth: int, max_depth: int
) -> list[dict]:
    """在列表中查找商品列表：先看本层前 3 个元素是否像商品，再递归子元素

    为什么只看前 3 个：列表若为商品列表，前几个元素必然是商品；
    只看前 3 个足够判断，避免对大列表做完整扫描。
    """
    # 检查列表元素是否像商品（含 itemId/id/auctionId 等标识字段）
    if obj and isinstance(obj[0], dict):
        for item in obj[:3]:
            if _is_item_like(item):
                return obj
    # 继续搜索子元素
    for item in obj:
        found = _find_items_recursive(item, depth + 1, max_depth)
        if found:
            return found
    return []


def _find_items_in_dict(
    obj: dict, depth: int, max_depth: int
) -> list[dict]:
    """在字典的 values 中递归查找商品列表"""
    for v in obj.values():
        found = _find_items_recursive(v, depth + 1, max_depth)
        if found:
            return found
    return []
