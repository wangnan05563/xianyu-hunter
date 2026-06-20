"""P1-7 Cron 定时调度单元测试"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from xianyu_hunter.config import get_settings, Settings
from xianyu_hunter.modules.cron_utils import (
    next_run_time,
    parse_cron,
    seconds_until_next_run,
    validate_cron,
)
from xianyu_hunter.web.app import app
from xianyu_hunter.web.deps import get_container


_TEST_TOKEN = "test-token-for-cron-api"


@pytest.fixture
def client(monkeypatch) -> TestClient:
    """构造 TestClient"""
    test_settings = Settings(web_token=_TEST_TOKEN)
    monkeypatch.setattr("xianyu_hunter.config.get_settings", lambda: test_settings)
    monkeypatch.setattr("xianyu_hunter.web.app.get_settings", lambda: test_settings, raising=False)

    class _FakeContainer:
        pass
    app.dependency_overrides[get_container] = lambda: _FakeContainer()
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_TEST_TOKEN}"}


# ============== cron_utils 单元测试 ==============

def test_parse_cron_valid() -> None:
    """解析合法 cron 表达式"""
    trigger = parse_cron("*/5 * * * *")
    assert trigger is not None


def test_parse_cron_invalid_fields() -> None:
    """字段数不对应报错"""
    with pytest.raises(ValueError, match="5 字段"):
        parse_cron("*/5 * *")  # 只有 3 字段


def test_validate_cron_valid() -> None:
    """校验合法表达式"""
    assert validate_cron("*/1 * * * *") is True
    assert validate_cron("0 9-22 * * 1-5") is True
    assert validate_cron("*/30 9-22 * * *") is True


def test_validate_cron_invalid() -> None:
    """校验非法表达式"""
    assert validate_cron("invalid") is False
    assert validate_cron("* * * * * *") is False  # 6 字段
    assert validate_cron("") is False


def test_next_run_time_basic() -> None:
    """计算下次运行时间"""
    # 固定起始时间：2026-06-18 10:30:00 UTC
    from_time = datetime(2026, 6, 18, 10, 30, 0, tzinfo=timezone.utc)
    # "0 * * * *" 每小时整点 → 下次 11:00
    next_time = next_run_time("0 * * * *", from_time)
    assert next_time.hour == 11
    assert next_time.minute == 0


def test_next_run_time_every_5_min() -> None:
    """每 5 分钟"""
    from_time = datetime(2026, 6, 18, 10, 32, 0, tzinfo=timezone.utc)
    next_time = next_run_time("*/5 * * * *", from_time)
    assert next_time.minute == 35


def test_seconds_until_next_run() -> None:
    """距离下次触发的秒数"""
    from_time = datetime(2026, 6, 18, 10, 30, 0, tzinfo=timezone.utc)
    # "0 * * * *" → 下次 11:00，距离 30 分钟 = 1800 秒
    secs = seconds_until_next_run("0 * * * *", from_time)
    assert secs == 1800.0


def test_seconds_until_next_run_minimum_1() -> None:
    """最小返回 1 秒"""
    from_time = datetime(2026, 6, 18, 10, 59, 59, tzinfo=timezone.utc)
    # "*/1 * * * *" → 下次 11:00:00，距离 1 秒
    secs = seconds_until_next_run("*/1 * * * *", from_time)
    assert secs >= 1.0


def test_next_run_time_naive_datetime() -> None:
    """无时区信息的 datetime 视为 UTC"""
    from_time = datetime(2026, 6, 18, 10, 30, 0)  # naive
    next_time = next_run_time("0 * * * *", from_time)
    assert next_time.hour == 11


# ============== API 端点测试 ==============

def test_cron_validate_valid(client: TestClient) -> None:
    """校验合法 cron 表达式"""
    resp = client.post(
        "/api/cron/validate",
        json={"cron": "*/10 * * * *"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert len(data["next_runs"]) == 5
    assert data["error"] is None


def test_cron_validate_invalid(client: TestClient) -> None:
    """校验非法 cron 表达式"""
    resp = client.post(
        "/api/cron/validate",
        json={"cron": "invalid"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is False
    assert len(data["next_runs"]) == 0
    assert "错误" in data["error"]


def test_cron_examples(client: TestClient) -> None:
    """获取 cron 示例列表"""
    resp = client.get("/api/cron/examples", headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["examples"]) >= 5
    # 每个示例都有 cron 和 label
    for ex in data["examples"]:
        assert "cron" in ex
        assert "label" in ex


def test_cron_validate_workday_schedule(client: TestClient) -> None:
    """工作日调度表达式"""
    resp = client.post(
        "/api/cron/validate",
        json={"cron": "*/10 9-22 * * 1-5"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert len(data["next_runs"]) == 5


# ============== TaskConfig use_cron 字段测试 ==============

def test_task_config_use_cron_default_false() -> None:
    """TaskConfig.use_cron 默认为 False"""
    from xianyu_hunter.domain.task import TaskConfig
    config = TaskConfig()
    assert config.use_cron is False


def test_task_config_use_cron_can_be_true() -> None:
    """TaskConfig.use_cron 可设为 True"""
    from xianyu_hunter.domain.task import TaskConfig
    config = TaskConfig(use_cron=True)
    assert config.use_cron is True
