"""闲鱼 DOM 选择器集中仓库

设计文档 §6.2 - 闲鱼改版时只改这里。
所有选择器必须有主备两组：主用 + 备用。
"""
from __future__ import annotations


class SelectorRepo:
    """闲鱼 DOM 选择器（CSS / XPath）

    每个字段提供主备两组：主用 *_MAIN，备用 *_ALT。
    闲鱼改版时可快速调整而不影响业务代码。
    """

    # ===== 搜索页 =====
    # 商品卡片（搜索结果列表项）
    # 闲鱼搜索结果使用基于 feed 的结构：`feeds-item-wrap` 包裹 `row1/2/3/4-wrap-*`。
    # 旧的 SearchCard/GoodsCard 命名已不再匹配。
    SEARCH_CARD_MAIN = "[class*='feeds-item-wrap']"
    SEARCH_CARD_ALT_1 = "[class*='feeds-item']"
    # 注意：[class*='search-item'] 会误匹配搜索建议词（如"笔记本电脑""电动车"），
    # 而非商品卡片，已移除。保留此注释以防闲鱼改版后需要添加新选择器。

    # 卡片内字段
    CARD_TITLE_MAIN = "[class*='title--']"
    CARD_TITLE_ALT = "[class*='Title--']"

    CARD_PRICE_MAIN = "[class*='price--']"
    CARD_PRICE_ALT = "[class*='Price--']"

    CARD_LINK_MAIN = "a"  # href 含 itemId
    CARD_THUMB_MAIN = "img"

    # 卖家信息（搜索结果卡片中仅有所在地，无卖家ID）
    CARD_SELLER_LOCATION = "[class*='seller-left'], [class*='sellerLocation'], [class*='areaName'], [class*='userArea'], [class*='region']"

    # 分页/加载更多
    SEARCH_LOAD_MORE = "[class*='loadMore'], [class*='load-more']"
    SEARCH_EMPTY = "[class*='empty'], [class*='Empty']"

    # ===== 商品详情页 =====
    DETAIL_TITLE_MAIN = "h1[class*='title'], [class*='detail-title']"
    DETAIL_TITLE_ALT = "h1"

    DETAIL_PRICE_MAIN = "[class*='price--']"
    DETAIL_PRICE_ALT = "[class*='Price']"

    # 描述：必须排除运费/服务条款区域（如 class 含 'postage' / 'shippingFee' / 'service'）
    # 闲鱼详情页会把"运费说明"、"七天无理由"等内容放在与描述同级的块里，
    # 通用 [class*='description'] 会误抓，必须限定到商品描述主容器
    DETAIL_DESC_MAIN = "[class*='desc-content'] [class*='content'], [class*='detailDesc']"
    DETAIL_DESC_ALT = "[class*='description-content'], [class*='description']:not([class*='postage']):not([class*='service']):not([class*='shipping'])"

    DETAIL_IMAGES_MAIN = "[class*='image'] img"
    DETAIL_IMAGES_ALT = "[class*='Pic'] img"

    # 主图（详情页顶部缩略图/封面），用于 thumb_url
    # 注意：必须限定为详情页主图区，避免匹配到卖家头像/推荐位
    DETAIL_THUMB_MAIN = "[class*='mainPic'] img, [class*='detailPic'] img, [class*='picMain'] img"
    DETAIL_THUMB_ALT = "[class*='detailImage'] img:first-child, [class*='picContainer'] img:first-child"

    # 地区：闲鱼详情页通常在"商品信息"区块显示地区
    # className 常见模式：item-user-info-label--XXX / region / area / location
    DETAIL_REGION_MAIN = "[class*='item-user-info-label']"
    DETAIL_REGION_ALT = "[class*='region'], [class*='userArea'], [class*='itemArea']"

    # 想要数：通常文本包含"X人想要"或 class 含 want/favor/like
    DETAIL_WANT_MAIN = "[class*='want--']"
    DETAIL_WANT_ALT = "[class*='want'], [class*='favor']"
    # 文本模式：作为 _detail.py 数字提取失败的回退（不放在选择器里）

    # 浏览数：通常文本包含"X人看过"或"浏览X次"，class 含 view/pv/browse
    DETAIL_VIEW_MAIN = "[class*='view--']"
    DETAIL_VIEW_ALT = "[class*='view'], [class*='browse'], [class*='pv']"

    # 发布时间：通常显示"X天前发布"，class 含 time/publish/release
    DETAIL_PUBLISH_TIME_MAIN = "[class*='publishTime']"
    DETAIL_PUBLISH_TIME_ALT = "[class*='releaseTime'], [class*='pubTime'], [class*='itemTime']"

    # 详情页上的卖家信息块
    DETAIL_SELLER_NAME = "[class*='sellerName'], [class*='userNick']"
    # 卖家链接选择器（多个 fallback，闲鱼改版时常变）
    DETAIL_SELLER_LINK = "a[href*='userId']"
    DETAIL_SELLER_LINK_ALT1 = "a[href*='user']"
    DETAIL_SELLER_LINK_ALT2 = "[class*='seller'] a, [class*='user'] a"

    # 立即购买/我想要 按钮
    BTN_BUY_NOW_MAIN = "button:has-text('立即购买')"
    BTN_BUY_NOW_ALT = "[class*='buy']:has-text('立即购买')"

    BTN_IWANT_MAIN = "button:has-text('我想要')"
    BTN_IWANT_ALT = "[class*='iwant']"

    # 提交订单
    SUBMIT_ORDER_BTN_MAIN = "button:has-text('提交订单')"
    SUBMIT_ORDER_BTN_ALT = "[class*='submit']"

    # 收货地址
    ADDRESS_MAIN = "[class*='address']"
    ADDRESS_ALT = "[class*='Address']"

    # 订单号（提交后页面）
    ORDER_NO_MAIN = "[class*='orderNo'], [class*='order-no']"
    ORDER_NO_ALT = "[class*='orderNumber']"

    # ===== 卖家主页 =====
    SELLER_NICK_MAIN = "[class*='nick']"
    SELLER_NICK_ALT = "[class*='userName']"

    SELLER_CREDIT_MAIN = "[class*='credit']"
    SELLER_CREDIT_ALT = "[class*='zhima']"

    SELLER_ON_SALE_MAIN = "[class*='onSale'] [class*='count']"
    SELLER_SOLD_MAIN = "[class*='sold'] [class*='count']"

    SELLER_REGISTER_MAIN = "[class*='registerTime']"
    SELLER_BAD_REVIEW_MAIN = "[class*='badReview'], [class*='negative']"

    # 卖家在售列表
    SELLER_ITEM_LIST_MAIN = "[class*='itemList'] [class*='item']"
    SELLER_ITEM_LIST_ALT = "[class*='ItemList'] [class*='Item']"

    # ===== 通用 =====
    LOGIN_BTN = "button:has-text('登录')"
    CAPTCHA_IMG = "[class*='captcha']"
    SLIDER_BG = "[class*='slider'], [class*='slide']"

    @classmethod
    def search_card_candidates(cls) -> list[str]:
        """搜索卡片的所有候选选择器（按优先级）"""
        return [cls.SEARCH_CARD_MAIN, cls.SEARCH_CARD_ALT_1]

    @classmethod
    def title_candidates(cls) -> list[str]:
        return [cls.CARD_TITLE_MAIN, cls.CARD_TITLE_ALT]

    @classmethod
    def price_candidates(cls) -> list[str]:
        return [cls.CARD_PRICE_MAIN, cls.CARD_PRICE_ALT]
