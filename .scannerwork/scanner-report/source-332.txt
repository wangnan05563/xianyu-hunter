from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from xianyu_hunter.config import Settings
from xianyu_hunter.infra.repository import Repository
from xianyu_hunter.web.app import app
from xianyu_hunter.web.deps import get_container


_TEST_TOKEN = "test-token-list-links-brand"


@pytest.fixture
def tmp_repo() -> Repository:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        repo = Repository(str(Path(d) / "test.db"))
        yield repo
        repo.engine.dispose()


@pytest.fixture
def client(tmp_repo: Repository, monkeypatch) -> TestClient:
    test_settings = Settings(web_token=_TEST_TOKEN)

    def _fake_settings():
        return test_settings

    monkeypatch.setattr("xianyu_hunter.config.get_settings", _fake_settings)
    monkeypatch.setattr("xianyu_hunter.web.app.get_settings", _fake_settings, raising=False)

    class _FakeContainer:
        def __init__(self, repo: Repository) -> None:
            self.repo = repo

    app.dependency_overrides[get_container] = lambda: _FakeContainer(tmp_repo)
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def test_list_links_corrects_brand_seller_region_misalignment(
    client: TestClient,
    tmp_repo: Repository,
) -> None:
    tmp_repo.upsert_task({"id": "t1", "name": "测试任务", "keyword": "DDR4"})
    tmp_repo.upsert_task_link(
        task_id="t1",
        link_type="item",
        link_key="item_brand_1",
        display={
            "title": "镁光DDR4 32G 3200 笔记本内存条",
            "price": 268.0,
            "seller_nick": "镁光数码",
            "region": "牧***蓉",
            "seller_credit": "",
            "is_sold": False,
        },
        source="auto",
    )

    resp = client.get(
        "/api/tasks/t1/links",
        headers={"Authorization": f"Bearer {_TEST_TOKEN}"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1

    display = data["items"][0]["display"]
    assert display["brand"] == "镁光数码"
    assert display["seller_nick"] == "牧***蓉"
    assert display["region"] == ""
