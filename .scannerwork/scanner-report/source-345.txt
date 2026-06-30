"""MtopSigner 单元测试"""
from __future__ import annotations

import hashlib
import json
from urllib.parse import parse_qs, urlparse

import pytest

from xianyu_hunter.modules.mtop_signer import (
    MtopAppKey,
    MtopRequest,
    MtopSignedParams,
    MtopSigner,
    extract_token_from_m5tk,
    verify_sign,
)


# ============== extract_token_from_m5tk 测试 ==============


def test_extract_token_with_timestamp() -> None:
    """从带时间戳的值中提取 token"""
    assert extract_token_from_m5tk("abc123_1700000000000") == "abc123"


def test_extract_token_without_timestamp() -> None:
    """不带时间戳的值原样返回"""
    assert extract_token_from_m5tk("abc123") == "abc123"


def test_extract_token_empty() -> None:
    """空值返回 None"""
    assert extract_token_from_m5tk("") is None
    assert extract_token_from_m5tk(None) is None  # type: ignore


# ============== MtopRequest 测试 ==============


def test_mtop_request_to_data_json_compact() -> None:
    """data JSON 序列化为紧凑格式（无空格）"""
    req = MtopRequest(
        api="test.api",
        data={"keyword": "iPhone", "page": 1},
    )
    data_json = req.to_data_json()
    # 紧凑格式：无空格
    assert " " not in data_json
    assert data_json == '{"keyword":"iPhone","page":1}'


def test_mtop_request_to_data_json_chinese() -> None:
    """中文字符不被转义"""
    req = MtopRequest(
        api="test.api",
        data={"keyword": "手机"},
    )
    data_json = req.to_data_json()
    assert "手机" in data_json
    assert "\\u" not in data_json


# ============== MtopSigner 签名测试 ==============


def test_sign_raises_without_token() -> None:
    """未设置 token provider 时签名抛出异常"""
    signer = MtopSigner()
    req = MtopRequest(api="test.api", data={})
    with pytest.raises(ValueError, match="未获取到"):
        signer.sign(req)


def test_sign_raises_when_token_none() -> None:
    """token provider 返回 None 时签名抛出异常"""
    signer = MtopSigner()
    signer.set_token_provider(lambda: None)
    req = MtopRequest(api="test.api", data={})
    with pytest.raises(ValueError, match="未获取到"):
        signer.sign(req)


def test_sign_produces_valid_md5() -> None:
    """签名是 32 位 MD5 十六进制"""
    signer = MtopSigner()
    signer.set_token_provider(lambda: "test_token_1700000000000")
    req = MtopRequest(api="test.api", data={"q": "test"})
    params = signer.sign(req)

    assert len(params.sign) == 32
    assert all(c in "0123456789abcdef" for c in params.sign)


def test_sign_algorithm_correct() -> None:
    """签名算法正确：MD5(token & timestamp & appKey & data)"""
    signer = MtopSigner()
    # 固定 token 和时间戳偏移
    signer.set_token_provider(lambda: "mytoken_1700000000000")
    signer.set_timestamp_offset(0)  # 无偏移

    req = MtopRequest(
        api="test.api",
        data={"keyword": "test"},
        app_key="34839810",
    )
    params = signer.sign(req)

    # 手动计算期望的签名
    token = "mytoken"
    data_json = '{"keyword":"test"}'
    expected_sign_str = f"{token}&{params.t}&34839810&{data_json}"
    expected_sign = hashlib.md5(expected_sign_str.encode("utf-8")).hexdigest()

    assert params.sign == expected_sign


def test_sign_different_data_different_sign() -> None:
    """不同 data 产生不同签名"""
    signer = MtopSigner()
    signer.set_token_provider(lambda: "token_1700000000000")
    signer.set_timestamp_offset(0)

    req1 = MtopRequest(api="test.api", data={"q": "a"})
    req2 = MtopRequest(api="test.api", data={"q": "b"})

    # 连续签名，时间戳可能相同
    params1 = signer.sign(req1)
    params2 = signer.sign(req2)

    assert params1.sign != params2.sign


def test_sign_different_appkey_different_sign() -> None:
    """不同 appKey 产生不同签名"""
    signer = MtopSigner()
    signer.set_token_provider(lambda: "token_1700000000000")
    signer.set_timestamp_offset(0)

    req1 = MtopRequest(api="test.api", data={"q": "a"}, app_key=MtopAppKey.SEARCH)
    req2 = MtopRequest(api="test.api", data={"q": "a"}, app_key=MtopAppKey.DETAIL)

    params1 = signer.sign(req1)
    params2 = signer.sign(req2)

    assert params1.sign != params2.sign


def test_sign_includes_required_params() -> None:
    """签名参数包含所有必需字段"""
    signer = MtopSigner()
    signer.set_token_provider(lambda: "token_1700000000000")

    req = MtopRequest(api="test.api", data={"q": "test"})
    params = signer.sign(req)

    assert params.jsv == "2.7.2"
    assert params.appKey == MtopAppKey.SEARCH
    assert params.t  # 时间戳非空
    assert params.sign  # 签名非空
    assert params.api == "test.api"
    assert params.v == "1.0"
    assert params.type == "originaljson"
    assert params.dataType == "json"
    assert params.data == '{"q":"test"}'


# ============== 时间戳偏移测试 ==============


def test_timestamp_offset_applied() -> None:
    """时间戳偏移正确应用"""
    signer = MtopSigner()
    signer.set_token_provider(lambda: "token_1700000000000")
    signer.set_timestamp_offset(57600000)  # 16 小时（毫秒）

    req = MtopRequest(api="test.api", data={})
    params = signer.sign(req)

    import time
    expected_t = str(int(time.time() * 1000) + 57600000)
    assert params.t == expected_t


def test_calibrate_timestamp() -> None:
    """通过服务端时间戳校准偏移"""
    signer = MtopSigner()
    signer.set_token_provider(lambda: "token_1700000000000")

    import time
    server_ts = int(time.time() * 1000) + 5000  # 服务端快 5 秒
    signer.calibrate_timestamp(server_ts)

    assert signer._timestamp_offset_ms == 5000


# ============== build_url 测试 ==============


def test_build_url_format() -> None:
    """构建的 URL 格式正确"""
    signer = MtopSigner()
    signer.set_token_provider(lambda: "token_1700000000000")

    req = MtopRequest(api="mtop.taobao.idlemtopsearch.pc.search", data={"q": "test"})
    url = signer.build_url(req)

    assert url.startswith("https://h5api.m.goofish.com/h5/")
    assert "mtop.taobao.idlemtopsearch.pc.search" in url
    assert "1.0" in url  # version


def test_build_url_contains_all_params() -> None:
    """URL 查询参数包含所有必需字段"""
    signer = MtopSigner()
    signer.set_token_provider(lambda: "token_1700000000000")

    req = MtopRequest(api="test.api", data={"q": "test"})
    url = signer.build_url(req)

    parsed = urlparse(url)
    qs = parse_qs(parsed.query)

    assert "jsv" in qs
    assert "appKey" in qs
    assert "t" in qs
    assert "sign" in qs
    assert "api" in qs
    assert "v" in qs
    assert "type" in qs
    assert "dataType" in qs
    assert "data" in qs


# ============== to_query_string / to_dict 测试 ==============


def test_signed_params_to_query_string() -> None:
    """to_query_string 生成有效查询字符串"""
    params = MtopSignedParams(
        jsv="2.7.2",
        appKey="34839810",
        t="1700000000000",
        sign="abc123",
        api="test.api",
        v="1.0",
        type="originaljson",
        dataType="json",
        data='{"q":"test"}',
    )
    qs = params.to_query_string()
    assert "jsv=2.7.2" in qs
    assert "sign=abc123" in qs
    # data 中的 JSON 应被 URL 编码
    assert "data=" in qs


def test_signed_params_to_dict() -> None:
    """to_dict 返回所有字段"""
    params = MtopSignedParams(
        jsv="2.7.2", appKey="34839810", t="123", sign="abc",
        api="test", v="1.0", type="json", dataType="json", data="{}",
    )
    d = params.to_dict()
    assert d["jsv"] == "2.7.2"
    assert d["appKey"] == "34839810"
    assert d["sign"] == "abc"


# ============== verify_sign 测试 ==============


def test_verify_sign_correct() -> None:
    """验证正确签名"""
    token = "mytoken"
    timestamp = "1700000000000"
    app_key = "34839810"
    data_json = '{"q":"test"}'

    sign_str = f"{token}&{timestamp}&{app_key}&{data_json}"
    sign = hashlib.md5(sign_str.encode("utf-8")).hexdigest()

    assert verify_sign(token, timestamp, app_key, data_json, sign) is True


def test_verify_sign_wrong_token() -> None:
    """错误 token 验证失败"""
    sign_str = "correct&1700000000000&34839810&{}"
    sign = hashlib.md5(sign_str.encode("utf-8")).hexdigest()
    assert verify_sign("wrong", "1700000000000", "34839810", "{}", sign) is False


def test_verify_sign_wrong_data() -> None:
    """错误 data 验证失败"""
    sign_str = "token&1700000000000&34839810&{correct}"
    sign = hashlib.md5(sign_str.encode("utf-8")).hexdigest()
    assert verify_sign("token", "1700000000000", "34839810", "{wrong}", sign) is False


# ============== AppKey 枚举测试 ==============


def test_appkey_values() -> None:
    """AppKey 枚举值正确"""
    assert MtopAppKey.SEARCH == "34839810"
    assert MtopAppKey.DETAIL == "12574478"
