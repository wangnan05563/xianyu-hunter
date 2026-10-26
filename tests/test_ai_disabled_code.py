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


def test_gate_is_not_reachable_from_deep_routes():
    """T02947 裁决 A：deep 路由不再引用硬门禁，只共享 `_ai_enabled()` 这个开关读取

    `_check_ai_enabled` 若被重新 import 回 api_ai_deep，说明有人又把
    deep-analyze / seller-template-check 改回了硬失败。
    """
    from xianyu_hunter.web.routes import api_ai_deep

    assert not hasattr(api_ai_deep, "_check_ai_enabled")
    assert api_ai_deep._ai_enabled is api_ai._ai_enabled


def test_ai_enabled_reflects_the_switch(monkeypatch):
    for value, expected in ((True, True), (False, False)):
        monkeypatch.setattr(api_ai, "get_settings", lambda v=value: SimpleNamespace(ai_enabled=v))
        assert api_ai._ai_enabled() is expected


def test_parse_task_falls_back_to_rule_when_switch_off(monkeypatch):
    """开关关闭时 parse-task 不再 403：一次都不碰 LLM，结果标注 source=rule"""
    monkeypatch.setattr(api_ai, "get_settings", lambda: SimpleNamespace(ai_enabled=False))
    llm_calls: list[int] = []

    def _no_llm(*args, **kwargs):
        llm_calls.append(1)
        return {}, "llm"

    monkeypatch.setattr(api_ai, "_try_parse_with_llm", _no_llm)
    result = api_ai.parse_task(api_ai.ParseTaskBody(text="iPhone 13 128G 银色"))
    assert llm_calls == []
    assert result["source"] == "rule"
    assert result["keyword"]


def test_eval_helpers_force_rule_branch_when_switch_off(monkeypatch):
    """成色评估/深度分析：allow_llm=False 时即使配了 Key 也不发起 LLM 调用

    有 Key 却关掉开关是最容易漏的场景——门禁必须落在调用点，而不只是入口 raise。
    """
    import asyncio
    from xianyu_hunter.web.routes import api_ai_deep

    settings = SimpleNamespace(ai_enabled=False, openai_api_key="sk-test")
    monkeypatch.setattr(api_ai, "_call_llm_vision", _boom)
    monkeypatch.setattr(api_ai_deep, "_call_llm_deep_analyze", _boom)

    _, source = asyncio.run(api_ai._run_condition_eval(
        "索尼 A7M4", "九成新，箱说全", 8000.0, [], None, "item-1", allow_llm=False))
    assert source == "rule"

    _, deep_source = asyncio.run(api_ai_deep._run_deep_analyze(
        "索尼 A7M4", "九成新，箱说全", 8000.0, [], [], "item-1", allow_llm=False))
    assert deep_source == "rule"


async def _boom(*args, **kwargs):  # 被调用即失败：规则分支不该碰 LLM
    raise AssertionError("LLM 被调用，说明开关未生效")


def test_test_connection_still_hard_fails(monkeypatch):
    """test-connection 没有规则形态，关闭时仍必须 403 + 机器码"""
    monkeypatch.setattr(api_ai, "get_settings", lambda: SimpleNamespace(ai_enabled=False))
    with pytest.raises(HTTPException) as exc:
        api_ai.test_ai_connection()
    assert exc.value.status_code == 403
    assert _http_exception_content(exc.value)["code"] == api_ai.AI_DISABLED_CODE


def test_plain_403_has_no_code(monkeypatch):
    """其它 403 不得被误标为 ai_disabled，否则前端会把它说成开关问题"""
    exc = HTTPException(status_code=403, detail="无权访问该资源")
    assert _http_exception_content(exc) == {"detail": "无权访问该资源"}
