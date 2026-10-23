"""T02890：AI 总开关关闭的 403 必须带机器码，且给人看的文案一字不变。

前端 src/utils/apiError.ts 的 isAiDisabledError 靠 code 分支，不再 grep 中文；
本文件钉住「响应体形状」与「文案不变」这两条契约（改文案要同时改前端测试）。
"""
import pytest
from fastapi import HTTPException
from types import SimpleNamespace

from xianyu_hunter.web.middleware.exception_handler import (
    CodedHTTPException, _http_exception_content,
)
from xianyu_hunter.web.routes import api_ai


@pytest.fixture
def gate(monkeypatch):
    """把 ai_enabled 关掉，返回 _check_ai_enabled 抛出的异常"""
    monkeypatch.setattr(
        api_ai, "get_settings", lambda: SimpleNamespace(ai_enabled=False)
    )
    with pytest.raises(HTTPException) as exc:
        api_ai._check_ai_enabled()
    return exc.value


def test_403_carries_machine_code(gate):
    assert gate.status_code == 403
    assert isinstance(gate, CodedHTTPException)
    assert gate.code == api_ai.AI_DISABLED_CODE == "ai_disabled"


def test_detail_wording_unchanged(gate):
    # 前端逐字转述这句，也用它做无 code 时的兜底识别，改动即视为破坏契约
    assert gate.detail == "AI 功能已关闭，请在「AI 服务」配置页面开启"
    assert "稍后重试" not in gate.detail


def test_response_body_shape(gate):
    assert _http_exception_content(gate) == {
        "detail": "AI 功能已关闭，请在「AI 服务」配置页面开启",
        "code": "ai_disabled",
    }


def test_gate_is_shared_by_deep_routes():
    """deep-analyze 复用同一个门禁，机器码自然跟着走，不必两处维护"""
    from xianyu_hunter.web.routes import api_ai_deep

    assert api_ai_deep._check_ai_enabled is api_ai._check_ai_enabled


def test_plain_403_has_no_code(monkeypatch):
    """其它 403 不得被误标为 ai_disabled，否则前端会把它说成开关问题"""
    exc = HTTPException(status_code=403, detail="无权访问该资源")
    assert _http_exception_content(exc) == {"detail": "无权访问该资源"}
