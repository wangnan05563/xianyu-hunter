"""闲鱼站点 URL 构建中心

将分散在各模块的 goofish.com 硬编码 URL 收敛到此处的统一入口，
切换站点（镜像/测试环境）时只需修改 Settings.xianyu_base_url 一处。
"""
from __future__ import annotations

from urllib.parse import quote

from xianyu_hunter.config import get_settings


def get_base_url() -> str:
    """获取闲鱼站点基础 URL（去除尾部斜杠以保证拼接一致性）"""
    return get_settings().xianyu_base_url.rstrip("/")


def build_item_url(item_id: str) -> str:
    """构建商品详情页 URL

    闲鱼详情页采用查询参数形式：/item?id=<item_id>
    """
    return f"{get_base_url()}/item?id={item_id}"


def build_seller_url(seller_id: str) -> str:
    """构建卖家主页 URL

    闲鱼卖家主页采用路径参数形式：/user/<seller_id>
    （历史代码中 live_search 使用此格式，保持一致以兼容前端渲染）
    """
    return f"{get_base_url()}/user/{seller_id}"


def build_search_url(
    keyword: str,
    filter_params: list[str] | None = None,
    sort_type: str = "default",
    regions: str = "",
) -> str:
    """构建搜索 URL

    Args:
        keyword: 搜索关键词，会做 URL 编码以避免 & # % 等特殊字符破坏查询语义
        filter_params: 闲鱼筛选标签对应的 URL 参数片段（如 ["price=0-100"]），
                       多个参数以 & 拼接追加到 q 参数之后
        sort_type: 排序方式（default/newest/price_asc/price_desc/want_count），
                   非 default 时追加 &sortType=... 参数
        regions: 地区过滤（逗号分隔，如 "北京,上海"），
                 非空时追加 &region=... 参数（已 URL 编码）

    Returns:
        形如 https://www.goofish.com/search?q=<encoded>&sortType=...&region=...
    """
    url = f"{get_base_url()}/search?q={quote(keyword)}"
    # 排序参数：闲鱼搜索页 sortType 映射
    # default 不追加参数（闲鱼默认行为），其他值直接作为 sortType 传递
    if sort_type and sort_type != "default":
        url += f"&sortType={sort_type}"
    # 地区过滤：逗号分隔转 URL 编码
    # 闲鱼搜索页 region 参数接受中文地区名
    if regions:
        url += f"&region={quote(regions)}"
    if filter_params:
        url += "&" + "&".join(filter_params)
    return url
