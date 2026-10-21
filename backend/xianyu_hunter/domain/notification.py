"""领域模型：业务通知的分类与等级口径（T02619）

为什么需要这个模块：`category` 的字面值此前散落在四处，且互相不认识——
- `web/routes/api_notifications._ALLOWED_CATEGORIES`（POST 白名单）
- `modules/price_watch`（写 `category="price"`）
- `web/services/notification_engine`（写 `order` / `auth`）
- 前端桌面 `pages/Notifications` 与移动 `mobile/pages/Notifications` 两张中文标签表

后果是「盯盘通知的 category=price 不在白名单里」：直写仓储能落库（绕过白名单），
但前端 `CATEGORY_LABEL['price']` 取到 undefined，标签渲染空白；而从 API 创建同类通知
会被 400 拒掉。两张前端标签表还各自把 auth 翻成「登录」和「认证」——同一含义两套文案。

本模块是 key 与中文标签的**唯一事实源**（与 T02556「文案收敛到单一事实源」同族）。
前端仍保留静态映射（不给一个标签值多开一次请求），由
`tests/test_regress_notification_category_single_source.py` 跨语言断言两侧一致：
新增分类只改这里，再跑测试，漏改前端会直接红。

新增分类的正规流程：
1. 在 `NotificationCategory` 加成员 + 中文标签；
2. 若需要落库，写通知处引用本模块常量（`NotificationCategory.X.value`），不要裸写字符串；
3. 跑回归，按提示补前端 `NOTIFICATION_CATEGORY_LABEL`（TS 的联合类型会编译报错，不会静默）。
"""
from __future__ import annotations

from enum import Enum


class NotificationCategory(str, Enum):
    """notifications.category 的唯一字面值来源

    成员顺序 = 通知中心里标签的展示顺序（订单/登录/盯盘 是用户常看到的，
    任务/配置/系统 为 API 侧保留分类，当前无内置写入方）。
    """

    ORDER = "order"
    AUTH = "auth"
    PRICE = "price"
    TASK = "task"
    CONFIG = "config"
    SYSTEM = "system"

    @property
    def label(self) -> str:
        """中文标签（前端标签表必须与此逐字一致，回归测试负责盯住）"""
        return _CATEGORY_LABELS[self]


_CATEGORY_LABELS: dict[NotificationCategory, str] = {
    NotificationCategory.ORDER: "订单",
    NotificationCategory.AUTH: "登录",
    NotificationCategory.PRICE: "盯盘",
    NotificationCategory.TASK: "任务",
    NotificationCategory.CONFIG: "配置",
    NotificationCategory.SYSTEM: "系统",
}

# 契约测试与白名单校验用：完整合法取值集合（frozenset[str]，元素是 .value 而非 Enum 成员）
NOTIFICATION_CATEGORY_VALUES: frozenset[str] = frozenset(c.value for c in NotificationCategory)

# 报错/文案用的展示顺序：成员声明序（严重度递增 / 用户常见在前），
# 而不是 sorted() 的字母序——"err/info/warn" 读起来不像一句人话
NOTIFICATION_CATEGORY_ORDER: tuple[str, ...] = tuple(c.value for c in NotificationCategory)

# 通知等级：与 notifications.level 列、前端 LEVEL_LABEL 同源
NOTIFICATION_LEVEL_VALUES: frozenset[str] = frozenset({"info", "warn", "err"})
NOTIFICATION_LEVEL_ORDER: tuple[str, ...] = ("info", "warn", "err")


def category_label(category: str | None) -> str:
    """把 category 字面值翻成中文标签；未知值原样返回

    为什么原样返回而不是抛错或返回空串：通知是历史数据，早期行里可能出现
    已下线的分类；给用户看原始英文 key 比看空白或让接口 500 更可诊断。
    """
    if not category:
        return ""
    try:
        return NotificationCategory(category).label
    except ValueError:
        return category
