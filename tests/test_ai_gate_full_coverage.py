"""T02891 裁决 A（AI 功能总开关全量纳管）的行为级测试。

这一单的缺陷形态是「文案承诺关闭即停用，代码里那几条链路压根不判开关」，
所以断言必须落在「关掉开关后是否真的发起了网络调用」，而不是断言某行代码里出现过 ai_enabled。
每个用例都把网络出口换成会尖叫的桩：一旦被调用就直接失败，
这样「漏判开关」会立刻显形，而不是等真实 API Key 打出去、token 已经烧掉才发现。
"""
import asyncio
from types import SimpleNamespace

import pytest

from xianyu_hunter.config import is_ai_disabled
from xianyu_hunter.modules.chatbot import agent as agent_mod
from xianyu_hunter.modules.chatbot import embedding_service as emb_mod
from xianyu_hunter.modules.chatbot import intent_classifier as intent_mod
from xianyu_hunter.modules.chatbot import rag_engine as rag_mod
from xianyu_hunter.modules.chatbot.agent import Agent
from xianyu_hunter.modules.chatbot.embedding_service import EmbeddingService
from xianyu_hunter.modules.chatbot.intent_classifier import IntentClassifier
from xianyu_hunter.modules.chatbot.rag_engine import RAGEngine
from xianyu_hunter.web.middleware.exception_handler import CodedHTTPException
from xianyu_hunter.web.routes import api_ai, api_chatbot, api_kb, price_histogram


class ScreamingClient:
    """任何一次网络调用都视为失败——用来证明「开关关闭后确实没打出去」"""

    def __init__(self):
        self.calls = 0

    async def post(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError(f"开关已关闭却仍发起了网络调用：{args}")

    async def get(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError(f"开关已关闭却仍发起了网络调用：{args}")

    def stream(self, *args, **kwargs):
        raise AssertionError(f"开关已关闭却仍发起了流式调用：{args}")


class SilentUsage:
    """用量/预算桩：始终放行，把注意力留给开关本身"""

    def check_budget(self):
        return True, ""

    def record_usage(self, *args, **kwargs):
        return None


class FakeBackgroundTask:
    """fake create_task 的返回值：普通类才可哈希——rebuild 会把任务塞进 _background_tasks（M-35），
    换成 SimpleNamespace 会在 add 处 TypeError。"""

    def add_done_callback(self, callback):
        return None


# ============== 判据本身 ==============

def test_is_ai_disabled_reflects_the_switch(monkeypatch):
    for value, expected in ((True, False), (False, True)):
        monkeypatch.setattr(
            "xianyu_hunter.config.get_settings",
            lambda v=value: SimpleNamespace(ai_enabled=v),
        )
        assert is_ai_disabled() is expected


def test_judgement_is_read_per_call_not_per_instance(monkeypatch):
    """开关是热更新的：判据必须每次重读，否则关掉的瞬间在跑的实例仍能花钱"""
    monkeypatch.setattr(
        "xianyu_hunter.config.get_settings", lambda: SimpleNamespace(ai_enabled=True)
    )
    assert is_ai_disabled() is False
    monkeypatch.setattr(
        "xianyu_hunter.config.get_settings", lambda: SimpleNamespace(ai_enabled=False)
    )
    assert is_ai_disabled() is True


# ============== 对话助手三条 LLM 腿 ==============

@pytest.mark.asyncio
async def test_intent_classifier_skips_llm_when_disabled(monkeypatch):
    monkeypatch.setattr(intent_mod, "is_ai_disabled", lambda: True)
    clf = IntentClassifier.__new__(IntentClassifier)
    clf._http = ScreamingClient()
    result = await clf._llm_classify("帮我看看这个卖家靠不靠谱")
    assert result.used_llm is False
    assert result.in_scope is True  # 保守放行，交给下游兜底
    assert "AI 总开关" in result.reason


@pytest.mark.asyncio
async def test_intent_classifier_still_calls_llm_when_enabled(monkeypatch):
    """反向对照：把开关打开后这条腿必须仍然走 LLM，否则上面那个用例是假绿。
    这里不看返回内容——ScreamingClient 会把真实请求打断，判据是「有没有打到出口」。
    """
    monkeypatch.setattr(intent_mod, "is_ai_disabled", lambda: False)
    clf = IntentClassifier.__new__(IntentClassifier)
    http = ScreamingClient()
    clf._http = http
    clf._ai_usage = SilentUsage()
    clf._base_url = "http://x/v1"
    clf._config = SimpleNamespace(llm=SimpleNamespace(model="m"))
    # _llm_classify 对任何异常都「保守放行」，所以尖叫客户端不会往上抛
    result = await clf._llm_classify("随便问点什么")
    assert http.calls == 1
    assert result.used_llm is False


@pytest.mark.asyncio
async def test_agent_raises_before_touching_http_when_disabled(monkeypatch):
    monkeypatch.setattr(agent_mod, "is_ai_disabled", lambda: True)
    ex = Agent.__new__(Agent)
    ex._http = ScreamingClient()
    ex._ai_usage = SilentUsage()
    with pytest.raises(RuntimeError, match="AI 总开关"):
        await ex._call_llm([{"role": "user", "content": "hi"}], [])


@pytest.mark.asyncio
async def test_rag_generate_raises_before_streaming_when_disabled(monkeypatch):
    monkeypatch.setattr(rag_mod, "is_ai_disabled", lambda: True)
    engine = SimpleNamespace(
        _build_messages=lambda *a, **k: [{"role": "user", "content": "q"}],
        _llm_config=SimpleNamespace(model="m", vision_model=None, temperature=0.2, max_tokens=100),
        _ai_usage=SilentUsage(),
        _http=ScreamingClient(),
    )
    agen = RAGEngine.generate(engine, query="q", context="c", history=[])
    with pytest.raises(RuntimeError, match="AI 总开关"):
        await agen.__anext__()


@pytest.mark.asyncio
async def test_rag_follow_ups_returns_empty_when_disabled(monkeypatch):
    """推荐追问不能抛：抛了会把已经生成的主回答一起拖成错误"""
    monkeypatch.setattr(rag_mod, "is_ai_disabled", lambda: True)
    engine = SimpleNamespace(
        _llm_config=SimpleNamespace(model="m", vision_model=None, temperature=0.2, max_tokens=100),
        _http=ScreamingClient(),
        _ai_usage=SilentUsage(),
    )
    assert await RAGEngine.generate_follow_ups(engine, "q", "a", []) == []


# ============== Embedding：只管远程腿 ==============

@pytest.mark.asyncio
async def test_remote_embedding_refused_when_disabled(monkeypatch):
    monkeypatch.setattr(emb_mod, "is_ai_disabled", lambda: True)
    svc = EmbeddingService.__new__(EmbeddingService)
    svc._is_local = False
    svc._ai_usage = SilentUsage()
    svc._call_remote = pytest.fail
    with pytest.raises(RuntimeError, match="AI 总开关"):
        await svc._call_embedding("文本")


@pytest.mark.asyncio
async def test_local_embedding_unaffected_by_switch(monkeypatch):
    """本地后端不产生 token 费用：一起关掉只会让检索静默变空，省不到钱"""
    monkeypatch.setattr(emb_mod, "is_ai_disabled", lambda: True)
    called = {}

    async def _fake_local(text):
        called["text"] = text
        return [0.1, 0.2]

    svc = EmbeddingService.__new__(EmbeddingService)
    svc._is_local = True
    svc._ai_usage = SilentUsage()
    svc._call_local = _fake_local
    assert await svc._call_embedding("文本") == [0.1, 0.2]
    assert called["text"] == "文本"


@pytest.mark.asyncio
async def test_embed_batch_fails_fast_instead_of_retrying_per_text(monkeypatch):
    """批量远程向量化必须整体快速失败。

    靠 _call_embedding 逐条抛的话，远程腿对每条重试 3 次（退避 0.5/1/2s），
    一万片段的重建会白等 10000×3.5s 才最终失败——这条断言盯的就是那个 sleep 循环。
    """
    monkeypatch.setattr(emb_mod, "is_ai_disabled", lambda: True)
    svc = EmbeddingService.__new__(EmbeddingService)
    svc._is_local = False
    svc._semaphore = asyncio.Semaphore(4)
    svc._last_batch_failures = []
    svc._call_embedding = lambda text: pytest.fail("批量腿应整体拒绝，不该逐条下钻")
    with pytest.raises(RuntimeError, match="AI 总开关"):
        await svc.embed_batch(["a", "b", "c"])


# ============== 价格趋势 AI 解读 ==============

def test_price_analyze_refuses_when_disabled(monkeypatch):
    import httpx

    # prices_analyze 里 get_settings 是函数内导入，只能打模块属性
    monkeypatch.setattr(
        "xianyu_hunter.config.get_settings",
        lambda: SimpleNamespace(ai_enabled=False, openai_api_key="sk-test"),
    )
    def _boom(*a, **k):
        raise AssertionError("开关关闭时不该构造 httpx.Client")

    monkeypatch.setattr(httpx, "Client", _boom)
    out = price_histogram.prices_analyze(task_id=None, container=SimpleNamespace())
    assert out["source"] == "error"
    assert "总开关" in out["analysis"]
    # 必须给可执行的指向，而不是「分析失败」这种死路
    assert "直方图" in out["analysis"]


def test_price_analyze_still_runs_when_enabled(monkeypatch):
    monkeypatch.setattr(
        "xianyu_hunter.config.get_settings",
        lambda: SimpleNamespace(ai_enabled=True, openai_api_key=""),
    )
    out = price_histogram.prices_analyze(task_id=None, container=SimpleNamespace())
    # API Key 缺失那条既有的腿仍要说得通，证明我没把开关判断写成无条件短路
    assert "API Key" in out["analysis"]


# ============== 端点层：该拦的拦（2 个 403），该放的放（对话入口走降级） ==============

# 后台任务的协程被 fake create_task 拦下来后不会被 await，
# 不留到 loop 关闭前显式关掉，解释器退出时会报「coroutine never awaited」。
pending: list = []


@pytest.fixture(autouse=True)
def _close_pending_coroutines():
    yield
    for coro in pending:
        coro.close()
    pending.clear()


@pytest.mark.asyncio
async def test_chat_route_stays_open_and_degrades_when_disabled(monkeypatch):
    """AC-18 定住的行为：关掉 AI，对话不是死路，而是降级成 FAQ/检索片段。

    入口 403 曾让这条验收标准失效（orchestrator 的 LLM→片段→转人工 降级链本就能零成本兑现它），
    所以门禁只落在各付费出口（intent / rag generate / follow_ups / agent / 远程 embedding）。
    """
    seen = {}

    class _Orchestrator:
        async def orchestrate(self, **kwargs):
            seen.update(kwargs)
            yield SimpleNamespace(event=SimpleNamespace(value="token"), data={"content": "检索片段"})

    monkeypatch.setattr(api_chatbot, "_get_chatbot_or_403", lambda: {"orchestrator": _Orchestrator()})

    async def _still_connected():
        return False

    resp = await api_chatbot.chat(
        api_chatbot.ChatRequest(message="退款政策是什么"),
        SimpleNamespace(state=SimpleNamespace(), is_disconnected=_still_connected),
    )
    chunks = [chunk async for chunk in resp.body_iterator]
    assert seen["message"] == "退款政策是什么"  # 请求确实走到了编排，没有被端点拦下
    assert chunks and "token" in chunks[0]


def test_kb_rebuild_403_only_for_remote_embedding(monkeypatch):
    """本地 embedding 重建不花钱，开关关着也要能重建；远程才拦。

    这条必须拦在接单前：rebuild 是 202 + 后台任务，放行后异常只会落进审计日志，
    用户已经看到 building，最后得到一个 0 向量的空知识库。
    """
    monkeypatch.setattr(api_kb, "_get_chatbot_or_403", lambda: {"kb_manager": object(), "repo": object()})
    started = {}

    def _fake_create_task(coro):
        started["yes"] = True
        pending.append(coro)
        return FakeBackgroundTask()

    monkeypatch.setattr(api_kb.asyncio, "create_task", _fake_create_task)

    for base_url, expect_blocked in (("https://api.openai.com/v1", True), ("", False), ("local", False)):
        started.clear()
        monkeypatch.setattr(api_kb, "get_settings", lambda b=base_url: SimpleNamespace(
            ai_enabled=False, embedding_base_url=b
        ))
        if expect_blocked:
            with pytest.raises(CodedHTTPException) as exc:
                asyncio.run(api_kb.rebuild_kb())
            assert exc.value.code == "ai_disabled"
            # 被拦下时绝不能已经接单
            assert "yes" not in started
        else:
            assert asyncio.run(api_kb.rebuild_kb()) == {"status": "building"}
            assert started.get("yes") is True


def test_test_embedding_403_only_for_remote(monkeypatch):
    """推理端点是软降级，但「测试连接」类端点返回假成功比报错更坏（T02890 同一条理由）"""
    local_calls = {}

    def _fake_local(model):
        local_calls["model"] = model
        return {"ok": True, "detail": "本地后端可用"}

    monkeypatch.setattr(api_ai, "_test_local_embedding", _fake_local)
    for base_url, expect_blocked in (("https://api.openai.com/v1", True), ("", False)):
        local_calls.clear()
        monkeypatch.setattr(api_ai, "get_settings", lambda b=base_url: SimpleNamespace(
            ai_enabled=False, embedding_base_url=b, embedding_model="bge-small-zh-v1.5"
        ))
        if expect_blocked:
            with pytest.raises(CodedHTTPException) as exc:
                api_ai.test_embedding_connection()
            assert exc.value.code == "ai_disabled"
        else:
            assert api_ai.test_embedding_connection()["ok"] is True
            assert local_calls.get("model") == "bge-small-zh-v1.5"
