"""T02984 回归：聊天机器人 get_error_logs 只读本会话用户的错误日志

背景：T02800 给 error_logs 补了 user_id，但 chatbot 工具仍调用
`list_error_logs(...)` 不带 user_id（None = 不过滤），LLM 工具能读到所有人的
request_path / stack_trace。本文件锁住整条透传链：
chat 路由 → orchestrator → Agent → ToolRegistry → GetErrorLogsTool。

身份只允许服务端注入：LLM 生成的参数里即使带 caller_user_id 也会被 Agent 丢弃。
`default` 直通（reader_user_id 返回 None）保持「看全量」的既有口径。

运行：
    .venv/Scripts/python.exe -m pytest tests/test_chatbot_error_logs_user_isolation.py \
        -o addopts="" -p no:cacheprovider -q
"""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from xianyu_hunter.infra.repository import Repository
from xianyu_hunter.infra.yaml_config import ChatbotAgentConfig
from xianyu_hunter.modules.chatbot.agent import Agent
from xianyu_hunter.modules.chatbot.orchestrator import ChatbotOrchestrator, SSEEvent
from xianyu_hunter.modules.chatbot.tool_registry import ToolRegistry
from xianyu_hunter.web.routes import api_chatbot
from xianyu_hunter.web.routes.api_chatbot import ChatRequest


@pytest.fixture
def repo(tmp_path):
    return Repository(db_path=str(tmp_path / "chat_error_logs.db"))


@pytest.fixture
def registry(repo):
    return ToolRegistry(repo)


def _seed(repo) -> None:
    """alice 与 bob 各一条异常日志，路径可区分"""
    repo.save_error_log({
        "error_type": "SchedulerError", "error_message": "alice task failed",
        "request_path": "/api/tasks/alice-1", "user_id": "alice",
    })
    repo.save_error_log({
        "error_type": "SchedulerError", "error_message": "bob task failed",
        "request_path": "/api/tasks/bob-1", "user_id": "bob",
    })


def _paths(result) -> list[str]:
    return sorted(log["request_path"] for log in result.data["logs"])


def test_tool_only_returns_callers_own_error_logs(repo, registry):
    """A 的会话只看到 A 的异常行，B 的 request_path 不出现"""
    _seed(repo)

    result = asyncio.run(registry.call("get_error_logs", caller_user_id="alice"))

    assert result.success is True
    assert _paths(result) == ["/api/tasks/alice-1"]


def test_passthrough_without_caller_sees_all_error_logs(repo, registry):
    """default 直通口径：caller 为 None 时不过滤（单用户部署看全量）"""
    _seed(repo)

    result = asyncio.run(registry.call("get_error_logs", caller_user_id=None))

    assert _paths(result) == ["/api/tasks/alice-1", "/api/tasks/bob-1"]


def test_llm_supplied_user_id_is_ignored(repo, registry):
    """工具入参里的 user_id 来自 LLM，不可作为身份来源"""
    _seed(repo)

    result = asyncio.run(
        registry.call("get_error_logs", caller_user_id="alice", user_id="bob")
    )

    assert _paths(result) == ["/api/tasks/alice-1"]


def test_tool_results_are_json_serializable(repo, registry):
    """仓储行里的 datetime 必须在注册表统一转字符串

    结果既回填 LLM 消息也进 SSE tool_result，两处都要 json.dumps；
    T02984 实测：不转换时 get_task_status 查到任务就抛 TypeError。
    """
    repo.upsert_task({
        "id": "t1", "name": "n", "keyword": "kw", "cron": "*/5 * * * *",
        "status": "active", "user_id": "default",
        "min_price": None, "max_price": None, "notifier_channels": None,
    })

    result = asyncio.run(registry.call("get_task_status", task_id="t1"))

    assert result.success is True
    json.dumps(result.to_dict(), ensure_ascii=False)


def _fake_agent(registry) -> Agent:
    """跳过 __init__（避免建 httpx 客户端），只装配 _run_loop 需要的两样东西"""
    agent = Agent.__new__(Agent)
    agent._tools = registry
    agent._config = ChatbotAgentConfig(max_tool_rounds=2)
    return agent


def test_agent_threads_caller_user_id_and_drops_spoofed_arg(repo, registry):
    """LLM 在参数里伪造 caller_user_id=bob，工具仍按服务端注入的 alice 过滤"""
    _seed(repo)
    agent = _fake_agent(registry)
    rounds = {"n": 0}

    async def fake_llm(messages, tools, images=None, model=None):
        rounds["n"] += 1
        if rounds["n"] == 1:
            return {
                "content": None,
                "tool_calls": [{
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "get_error_logs",
                        "arguments": '{"limit": 10, "caller_user_id": "bob", "user_id": "bob"}',
                    },
                }],
            }
        return {"content": "done", "tool_calls": None}

    agent._call_llm = fake_llm

    async def go():
        return [
            event
            async for event in agent._run_loop("查错误日志", "", [], caller_user_id="alice")
        ]

    events = asyncio.run(go())
    tool_results = [e.data["result"] for e in events if e.type == "tool_result"]

    assert len(tool_results) == 1
    assert tool_results[0]["success"] is True
    logs = tool_results[0]["data"]["logs"]
    assert sorted(log["request_path"] for log in logs) == ["/api/tasks/alice-1"]


class _StubRag:
    async def retrieve(self, query):
        return []

    def to_sources(self, chunks):
        return []

    def build_context(self, chunks):
        return ""


class _StubCtx:
    def build_history_messages(self, context):
        return []


class _CaptureAgent:
    def __init__(self):
        self.seen: list[str | None] = []

    async def run(self, query, context, history, images=None, model=None, caller_user_id=None):
        self.seen.append(caller_user_id)
        if False:  # 保持 async generator 语义
            yield None


def test_orchestrator_passes_user_id_to_agent():
    """编排层把 user_id 原样交给 Agent（缺失这一跳时工具会退回全局）"""
    orch = ChatbotOrchestrator.__new__(ChatbotOrchestrator)
    orch._rag = _StubRag()
    orch._ctx = _StubCtx()
    orch._agent = _CaptureAgent()

    async def go():
        return [
            event
            async for event in orch._run_agent_flow("q", SimpleNamespace(), user_id="alice")
        ]

    assert asyncio.run(go()) == []
    assert orch._agent.seen == ["alice"]


class _FakeOrchestrator:
    def __init__(self):
        self.calls: list[dict] = []

    async def orchestrate(self, **kwargs):
        self.calls.append(kwargs)
        yield SSEEvent(event="done", data={})


def _fake_request(user_id: str):
    class _Req:
        state = SimpleNamespace(user_id=user_id)

        async def is_disconnected(self):
            return False

    return _Req()


def _call_chat(monkeypatch, user_id: str) -> dict:
    fake = _FakeOrchestrator()
    monkeypatch.setattr(api_chatbot, "_get_chatbot_or_403", lambda: {"orchestrator": fake})

    async def go():
        response = await api_chatbot.chat(ChatRequest(message="hi"), _fake_request(user_id))
        assert [chunk async for chunk in response.body_iterator]
        return fake.calls[-1]

    return asyncio.run(go())


def test_chat_route_passes_reader_user_id(monkeypatch):
    """真实会话用户身份进入编排层"""
    assert _call_chat(monkeypatch, "alice")["user_id"] == "alice"


def test_chat_route_default_passthrough_passes_none(monkeypatch):
    """default 直通必须传 None（= 不过滤），不能传 'default' 把自己锁进命名空间"""
    assert _call_chat(monkeypatch, "default")["user_id"] is None
