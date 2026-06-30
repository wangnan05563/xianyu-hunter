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

    # 详情页主价格：排除原价/划线价/运费等干扰元素
    # 为什么需要排除：详情页通常有原价（划线）、当前价、促销价、运费等多个含 price 的元素，
    # 通用 [class*='price--'] 会取到第一个匹配（可能是原价），导致采集金额与官网不一致
    DETAIL_PRICE_MAIN = "[class*='price--']:not([class*='original']):not([class*='Original']):not([class*='postage']):not([class*='shipping']):not([class*='line-through'])"
    DETAIL_PRICE_ALT = "[class*='Price']:not([class*='original']):not([class*='Original']):not([class*='postage']):not([class*='shipping']):not([class*='line-through'])"

    # 描述：必须排除运费/服务条款区域（如 class 含 'postage' / 'shippingFee' / 'service'）
    # 闲鱼详情页会把"运费说明"、"七天无理由"等内容放在与描述同级的块里，
    # 通用 [class*='description'] 会误抓，必须限定到商品描述主容器
    DETAIL_DESC_MAIN = "[class*='desc-content'] [class*='content'], [class*='detailDesc'], [class*='desc--']"
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
    # 新版闲鱼详情页卖家昵称 class 为 item-user-info-nick--XXXX
    DETAIL_SELLER_NAME = "[class*='sellerName'], [class*='userNick'], [class*='user-info-nick']"
    # 卖家链接选择器（多个 fallback，闲鱼改版时常变）
    DETAIL_SELLER_LINK = "a[href*='userId']"
    DETAIL_SELLER_LINK_ALT1 = "a[href*='user']"
    DETAIL_SELLER_LINK_ALT2 = "[class*='seller'] a, [class*='user'] a"

    # 立即购买/我想要 按钮
    # 闲鱼详情页的「立即购买」实际是 <a> 标签（class 含 buy--XXXX），而非 <button>
    BTN_BUY_NOW_TEXT = "text=\"立即购买\""
    BTN_BUY_NOW_MAIN = "a:has-text('立即购买')"
    BTN_BUY_NOW_ALT = "[class*='buy']:has-text('立即购买')"
    BTN_BUY_NOW_ALT2 = "button:has-text('立即购买')"

    BTN_IWANT_MAIN = "a:has-text('我想要')"
    BTN_IWANT_ALT = "[class*='iwant']"
    BTN_IWANT_ALT2 = "button:has-text('我想要')"

    # 提交订单/确认购买（多档选择器，覆盖闲鱼不同版本的订单确认页文案）
    SUBMIT_ORDER_BTN_MAIN = "button:has-text('提交订单')"
    SUBMIT_ORDER_BTN_CONFIRM_BUY = (
        "button:has-text('确认购买'), a:has-text('确认购买'), [role='button']:has-text('确认购买')"
    )
    SUBMIT_ORDER_BTN_ALT = "[class*='submit']:has-text('提交订单'), [class*='submit']:has-text('确认购买')"
    SUBMIT_ORDER_BTN_ALT2 = "button:has-text('确认订单')"
    SUBMIT_ORDER_BTN_ALT3 = (
        "[class*='confirm']:has-text('确认购买'), [class*='confirm']:has-text('确认订单')"
    )

    # 收货地址
    ADDRESS_MAIN = "[class*='address']"
    ADDRESS_ALT = "[class*='Address']"

    # 订单号（提交后页面）
    ORDER_NO_MAIN = "[class*='orderNo'], [class*='order-no']"
    ORDER_NO_ALT = "[class*='orderNumber']"

    # ===== 卖家主页 =====
    # 昵称：限定在 infoTop 容器内，避免匹配到页头的"登录"按钮（nick--RyNYtDXM）
    SELLER_NICK_MAIN = "[class*='infoTop'] [class*='nick']"
    SELLER_NICK_ALT = "[class*='userName'], [class*='personalWrap'] [class*='nick']"

    SELLER_CREDIT_MAIN = "[class*='credit']"
    SELLER_CREDIT_ALT = "[class*='zhima']"

    # 在售数/已售数：新版闲鱼用 tabItem 类，文本格式 "在售9" / "已售出342"
    # 旧版用 onSale/sold + count 子元素，新版改为 tabItem 直接包含数字
    SELLER_ON_SALE_MAIN = "[class*='tabItem']"
    SELLER_ON_SALE_ALT = "[class*='onSale'] [class*='count']"
    SELLER_SOLD_MAIN = "[class*='tabItem']"
    SELLER_SOLD_ALT = "[class*='sold'] [class*='count']"

    # 注册时间：新版闲鱼卖家主页已移除该字段，保留旧版选择器兼容
    SELLER_REGISTER_MAIN = "[class*='registerTime']"
    SELLER_REGISTER_ALT = "[class*='register'], [class*='joinTime']"
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

    @classmethod
    def submit_order_candidates(cls) -> list[str]:
        """订单确认页最终确认按钮候选选择器。"""
        return [
            cls.SUBMIT_ORDER_BTN_MAIN,
            cls.SUBMIT_ORDER_BTN_CONFIRM_BUY,
            cls.SUBMIT_ORDER_BTN_ALT,
            cls.SUBMIT_ORDER_BTN_ALT2,
            cls.SUBMIT_ORDER_BTN_ALT3,
        ]

    @classmethod
    def submit_order_text_candidates(cls) -> list[str]:
        """订单确认页最终确认按钮文案候选。"""
        return ["提交订单", "确认购买", "确认订单", "确认下单"]

    @classmethod
    def buy_now_candidates(cls) -> list[str]:
        """详情页「立即购买」按钮候选选择器。"""
        return [
            cls.BTN_BUY_NOW_TEXT,
            cls.BTN_BUY_NOW_MAIN,
            cls.BTN_BUY_NOW_ALT,
            cls.BTN_BUY_NOW_ALT2,
        ]
