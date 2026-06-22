"""MTOP 网关签名器（设计文档 §4.5）

核心问题：现有方案完全依赖 Playwright route 拦截获取 API 数据，
无法脱离浏览器独立请求。

解决方案：从浏览器中提取签名要素，实现纯 Python MTOP 签名。

MTOP 签名算法：
    sign = MD5(token + "&" + timestamp + "&" + appKey + "&" + data)

参数说明：
- token: Cookie _m_h5_tk 下划线前的部分，动态令牌，15-22分钟过期
- timestamp: 毫秒级时间戳（存在 16 小时偏移，需校准）
- appKey: 固定值，区分不同业务线
- data: POST 请求体 JSON 字符串

注意：MtopSigner 依赖 _m_h5_tk 中的 token 部分，
必须与 TokenRenewer 协同工作。
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from urllib.parse import urlencode

from xianyu_hunter.infra.logger import get_logger

logger = get_logger()


class MtopAppKey(str, Enum):
    """MTOP 业务线 appKey"""
    SEARCH = "34839810"     # 搜索接口
    DETAIL = "12574478"     # 详情接口
    COMMON = "00000000"     # 通用接口


@dataclass
class MtopRequest:
    """MTOP 请求参数"""
    api: str                          # API 名称，如 mtop.taobao.idlemtopsearch.pc.search
    version: str = "1.0"              # API 版本
    data: dict[str, Any] = field(default_factory=dict)  # 请求数据
    method: str = "GET"               # HTTP 方法
    app_key: str = MtopAppKey.SEARCH  # 业务线 appKey

    def to_data_json(self) -> str:
        """序列化 data 为 JSON 字符串

        关键：必须使用紧凑格式（无空格），否则签名不匹配
        ensure_ascii=False 保证中文字符不被转义
        """
        return json.dumps(self.data, separators=(",", ":"), ensure_ascii=False)


@dataclass
class MtopSignedParams:
    """MTOP 签名后的请求参数"""
    jsv: str
    appKey: str
    t: str           # 时间戳（毫秒）
    sign: str        # MD5 签名
    api: str
    v: str
    type: str        # 响应类型
    dataType: str
    data: str        # 序列化后的 data

    def to_query_string(self) -> str:
        """转换为 URL 查询参数字符串"""
        return urlencode({
            "jsv": self.jsv,
            "appKey": self.appKey,
            "t": self.t,
            "sign": self.sign,
            "api": self.api,
            "v": self.v,
            "type": self.type,
            "dataType": self.dataType,
            "data": self.data,
        })

    def to_dict(self) -> dict[str, str]:
        """转换为字典"""
        return {
            "jsv": self.jsv,
            "appKey": self.appKey,
            "t": self.t,
            "sign": self.sign,
            "api": self.api,
            "v": self.v,
            "type": self.type,
            "dataType": self.dataType,
            "data": self.data,
        }


class MtopSigner:
    """MTOP 网关签名器

    使用方式：
        signer = MtopSigner()
        signer.set_token_provider(lambda: get_m5tk_token())
        signer.set_timestamp_offset(57600)  # 16 小时偏移校准

        request = MtopRequest(
            api="mtop.taobao.idlemtopsearch.pc.search",
            data={"keyword": "iPhone"},
        )
        params = signer.sign(request)
        url = f"https://h5api.m.goofish.com/h5/{request.api}/{request.version}/?{params.to_query_string()}"
    """

    # MTOP 网关 URL
    GATEWAY_URL = "https://h5api.m.goofish.com/h5"

    # JS 版本（与闲鱼前端 lib-mtop 一致）
    JSV = "2.7.2"

    # 默认响应类型
    DEFAULT_TYPE = "originaljson"
    DEFAULT_DATA_TYPE = "json"

    def __init__(self):
        self._token_provider: Any = None  # Callable[[], str | None]
        self._timestamp_offset_ms: int = 0  # 时间戳偏移（毫秒）

    # ============== 配置 ==============

    def set_token_provider(self, provider: Any) -> None:
        """设置 token 提供器

        provider 应返回 _m_h5_tk 中下划线前的部分（token），
        无 token 时返回 None。
        """
        self._token_provider = provider

    def set_timestamp_offset(self, offset_ms: int) -> None:
        """设置时间戳偏移

        闲鱼 mtop 接口时间戳存在 16 小时偏移，
        需通过 getTimestamp 接口校准。
        正值表示服务端时间比本地快。
        """
        self._timestamp_offset_ms = offset_ms

    def calibrate_timestamp(self, server_timestamp_ms: int) -> None:
        """通过服务端返回的时间戳校准偏移

        Args:
            server_timestamp_ms: getTimestamp 接口返回的毫秒时间戳
        """
        local_ms = int(time.time() * 1000)
        self._timestamp_offset_ms = server_timestamp_ms - local_ms
        logger.info("MTOP 时间戳偏移校准: %dms", self._timestamp_offset_ms)

    # ============== 签名 ==============

    def sign(self, request: MtopRequest) -> MtopSignedParams:
        """生成 MTOP 签名参数

        sign = MD5(token + "&" + timestamp + "&" + appKey + "&" + data_json)

        Raises:
            ValueError: 未设置 token 或 token 为空
        """
        token = self._get_token()
        if not token:
            raise ValueError("未获取到 _m_h5_tk token，无法签名")

        timestamp = self._get_timestamp()
        data_json = request.to_data_json()

        # 核心签名算法
        sign_str = f"{token}&{timestamp}&{request.app_key}&{data_json}"
        sign = hashlib.md5(sign_str.encode("utf-8")).hexdigest()

        return MtopSignedParams(
            jsv=self.JSV,
            appKey=request.app_key,
            t=timestamp,
            sign=sign,
            api=request.api,
            v=request.version,
            type=self.DEFAULT_TYPE,
            dataType=self.DEFAULT_DATA_TYPE,
            data=data_json,
        )

    def build_url(self, request: MtopRequest) -> str:
        """构建完整的 MTOP 请求 URL

        URL 格式：{GATEWAY_URL}/{api}/{version}/?{query_params}
        """
        params = self.sign(request)
        query = params.to_query_string()
        return f"{self.GATEWAY_URL}/{request.api}/{request.version}/?{query}"

    # ============== 内部方法 ==============

    def _get_token(self) -> str | None:
        """获取当前 token"""
        if not self._token_provider:
            return None
        try:
            value = self._token_provider()
            if not value:
                return None
            # _m_h5_tk 格式：{token}_{timestamp}
            # 取下划线前的部分作为签名 token
            if "_" in value:
                return value.split("_", 1)[0]
            return value
        except Exception as e:
            logger.error("获取 token 失败: %s", e)
            return None

    def _get_timestamp(self) -> str:
        """获取校准后的时间戳（毫秒级字符串）"""
        local_ms = int(time.time() * 1000)
        adjusted_ms = local_ms + self._timestamp_offset_ms
        return str(adjusted_ms)


# ============== 辅助函数 ==============


def extract_token_from_m5tk(m5tk_value: str) -> str | None:
    """从 _m_h5_tk Cookie 值中提取 token

    _m_h5_tk 格式：{token}_{timestamp}
    返回下划线前的部分，无下划线则返回原值
    """
    if not m5tk_value:
        return None
    if "_" in m5tk_value:
        return m5tk_value.split("_", 1)[0]
    return m5tk_value


def verify_sign(
    token: str,
    timestamp: str,
    app_key: str,
    data_json: str,
    expected_sign: str,
) -> bool:
    """验证签名是否正确（供调试用）"""
    sign_str = f"{token}&{timestamp}&{app_key}&{data_json}"
    actual_sign = hashlib.md5(sign_str.encode("utf-8")).hexdigest()
    return actual_sign == expected_sign
