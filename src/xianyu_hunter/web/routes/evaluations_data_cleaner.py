"""评估数据脏数据清洗模块

从 api_evaluations.py 拆分，专门处理 seller_nick 字段的历史污染数据：
- 早期 DOM 解析脚本用宽泛选择器导致 seller_nick 被写入地区/信用度/发布时间/成色关键词
- 通过白名单+模式识别检测污染，并尝试将脏数据分离到正确的字段
"""
from __future__ import annotations

import re

from loguru import logger

from xianyu_hunter.web.routes.evaluations_common import _USED_TRACE_LABEL

# 已知污染模式：早期 DOM 解析脚本错误写入的字段值
_REGION_PATTERNS = re.compile(r"^[\u4e00-\u9fa5]{2,4}$")  # 纯 2-4 字中文（省/市）
_CREDIT_PATTERNS = re.compile(r"^.*(信用|极好|良好|优秀|信誉).*$")
# match() 不要求匹配到字符串结尾，移除尾部 .* 降低正则复杂度（S5843）
_PUBLISH_TIME_PATTERNS = re.compile(
    r".*(周内|天内|小时前|分钟前|月前|刚刚|今天|昨天|前天|秒前|\d+\s*(分钟|小时|天|周|月)前)"
)
# 卖家昵称脏数据识别用的关键词集合
# 必须包含所有可能的污染值（如"几乎全新"、"全新"等成色关键词）
_POLLUTED_NICK_KEYWORDS = {
    "全新", "未拆封", "未使用", "未拆", "99新", "95新", "9成新", "几乎全新",
    "近全新", "近新", "9.5新", "9.9新", "8成新", "8.5新", "85新", "7成新",
    "正常使用", "使用过", _USED_TRACE_LABEL, "明显使用", "外观磨损", "有划痕", "磕碰",
    "维修", "维修过", "拆修", "故障", "损坏", "已坏", "屏幕破损", "进水", "摔过",
    "原装", "原厂", "正品", "原盒", "原包装", "带发票", "带保修", "在保",
    "裸机", "无包装", "无配件",
    "全新未拆", "未拆封未使用", "未激活", "国行未激活",
    "轻微使用", "保养好", "使用痕迹少", "成色新",
    "成色一般", "使用痕迹明显", "老化", "非全新", "不能用", "进水机",
    "全套", "配件齐全", "带原盒", "保修中", "保修卡", "原装盒", "全套包装",
    "无充电器", "无原盒", "无发票", "无保修卡", "配件不全", "缺包装",
}


def _is_polluted_seller_nick(value: str) -> tuple[bool, str]:
    """检测 seller_nick 是否为脏数据

    返回 (is_polluted, pollution_type)：
    - pollution_type: "region" | "credit" | "publish_time" | "condition" | "combined" | ""
    """
    if not value or not isinstance(value, str):
        return False, ""
    s = value.strip()
    if not s:
        return False, ""

    # 1. 复合污染：包含 \n 分隔的多个字段（地区+信用度）
    if "\n" in s or "\\n" in s:
        return True, "combined"

    # 2. 地区污染：纯 2-4 字中文
    if _REGION_PATTERNS.match(s) and s in {"河北", "山西", "山东", "河南", "江苏", "浙江",
                                              "安徽", "福建", "江西", "湖北", "湖南", "广东",
                                              "广西", "海南", "四川", "贵州", "云南", "陕西",
                                              "甘肃", "青海", "台湾", "北京", "天津", "上海",
                                              "重庆", "唐山", "石家庄", "保定", "邯郸", "秦皇岛",
                                              "广州", "深圳", "杭州", "南京", "苏州", "成都",
                                              "武汉", "西安", "郑州", "济南", "青岛", "厦门",
                                              "福州", "合肥", "南昌", "长沙", "太原"}:
        return True, "region"

    # 3. 信用度污染
    if _CREDIT_PATTERNS.match(s) and len(s) <= 20:
        return True, "credit"

    # 4. 发布时间污染（"一周内发布"、"x小时前"等）
    if _PUBLISH_TIME_PATTERNS.match(s) and len(s) <= 20:
        return True, "publish_time"

    # 5. 成色关键词污染（"几乎全新"等）
    if s in _POLLUTED_NICK_KEYWORDS:
        return True, "condition"

    return False, ""


# ==== clean_dirty_seller_nick 辅助函数 ====
def _handle_combined_pollution(payload: dict, nick: str) -> None:
    """复合污染处理：分离"地区\n信用度"格式，剩余部分作为 seller_nick"""
    parts = [s.strip() for s in nick.replace("\\n", "\n").split("\n") if s.strip()]
    region = ""
    credit = ""
    for p in parts:
        _, sub_type = _is_polluted_seller_nick(p)
        if sub_type == "region" and not region:
            region = p
        elif sub_type == "credit" and not credit:
            credit = p
    if region and not payload.get("region"):
        payload["region"] = region
    if credit and not payload.get("seller_credit"):
        payload["seller_credit"] = credit
    # 剩余部分作为 seller_nick
    real_nick = " ".join(p for p in parts if p != region and p != credit).strip()
    payload["seller_nick"] = real_nick


def _handle_region_pollution(payload: dict, nick: str) -> None:
    """地区污染处理：移到 region 字段，清空 seller_nick"""
    if not payload.get("region"):
        payload["region"] = nick.strip()
    payload["seller_nick"] = ""


def _handle_credit_pollution(payload: dict, nick: str) -> None:
    """信用度污染处理：移到 seller_credit 字段，清空 seller_nick"""
    if not payload.get("seller_credit"):
        payload["seller_credit"] = nick.strip()
    payload["seller_nick"] = ""


def _handle_publish_time_pollution(payload: dict, nick: str) -> None:
    """发布时间污染处理：保存为 publish_time_text，清空 seller_nick

    为什么存到 publish_time_text：前端发布时间为空时兜底显示"""
    if not payload.get("publish_time_text"):
        payload["publish_time_text"] = nick.strip()
    payload["seller_nick"] = ""


def _handle_condition_pollution(payload: dict, nick: str) -> None:
    """成色关键词污染处理：保存为 condition_label_override，清空 seller_nick

    为什么存到 condition_label_override：覆盖自动计算结果，保证脏数据恢复后展示正确"""
    if not payload.get("condition_label_override"):
        payload["condition_label_override"] = nick.strip()
    payload["seller_nick"] = ""


def clean_dirty_seller_nick(payload: dict) -> None:
    """清洗历史评估数据中 seller_nick 字段被污染的问题

    历史 bug 总结（多种污染模式）：
    1. 早期 DOM 解析脚本用宽泛的 [class*="seller"] 选择器，导致 seller_nick 字段
       被写入了"地区\\n\\n卖家信用度"格式的脏数据
    2. 部分历史代码从商品标题/描述中错误地提取了"几乎全新"、"一周内发布"等
       成色/时间关键词作为 seller_nick
    3. 部分记录 seller_nick 字段是纯地区名（"河北"、"唐山"等）

    本函数通过白名单+模式识别检测污染，并尝试将脏数据分离到正确的字段：
    - 地区 → region
    - 信用度 → seller_credit
    - 发布时间短语 → publish_time_text（前端兜底展示）
    - 成色关键词 → condition_label（覆盖自动计算结果）
    """
    nick = payload.get("seller_nick", "")
    is_polluted, pollution_type = _is_polluted_seller_nick(nick)

    if not is_polluted:
        return

    if pollution_type == "combined":
        _handle_combined_pollution(payload, nick)
    elif pollution_type == "region":
        _handle_region_pollution(payload, nick)
    elif pollution_type == "credit":
        _handle_credit_pollution(payload, nick)
    elif pollution_type == "publish_time":
        _handle_publish_time_pollution(payload, nick)
    elif pollution_type == "condition":
        _handle_condition_pollution(payload, nick)
    else:
        # 兜底：未识别的污染模式，清空 seller_nick
        payload["seller_nick"] = ""

    # 调试日志：记录脏数据清洗情况（生产环境可通过日志级别控制）
    logger.info(
        "Cleaned dirty seller_nick: type=%s, original=%r, new_nick=%r, region=%r, credit=%r, publish_text=%r, override=%r",
        pollution_type, nick, payload.get("seller_nick"),
        payload.get("region"), payload.get("seller_credit"),
        payload.get("publish_time_text"), payload.get("condition_label_override"),
    )
