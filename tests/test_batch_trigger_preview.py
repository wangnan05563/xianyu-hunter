"""T02771 / PRD 4.4-2：触发前「本批会跑多少」必须与真实执行同源

同源不是口头承诺：`select_batch_items()` 被预估接口和 `_prepare_batch_items()` 共用，
两边的条数只能是同一个函数算出来的。本文件把这件事钉成两类用例——
一类跑真实取数（同源相等 / 上限裁剪 / 断点续传扣除），一类跑源码契约（不许绕开共用函数）。
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from xianyu_hunter.infra import yaml_config
from xianyu_hunter.modules import batch_refresh_scheduler as sched
from xianyu_hunter.web.routes import api_batch_refresh

SCHEDULER_SRC = Path(sched.__file__).read_text(encoding="utf-8")
ROUTE_SRC = Path(api_batch_refresh.__file__).read_text(encoding="utf-8")


class FakeRepo:
    def __init__(self, unsold, by_ids=None):
        self.unsold = list(unsold)
        self.by_ids = by_ids or {}
        self.calls: list[tuple] = []

    def list_unsold_items(self, limit: int = 100, user_id: str | None = None):
        self.calls.append(("list_unsold_items", limit, user_id))
        return self.unsold[:limit]

    def list_items_by_ids(self, item_ids, user_id: str | None = None):
        self.calls.append(("list_items_by_ids", tuple(item_ids), user_id))
        return [self.by_ids.get(i, {"item_id": i, "is_sold": False}) for i in item_ids]


def _cfg(max_items_per_run: int = 100):
    return SimpleNamespace(max_items_per_run=max_items_per_run)


def _items(n: int):
    return [{"item_id": f"i{k}"} for k in range(n)]


def _stub_scheduler(repo, cfg, cleared: list[bool]):
    """只装配 _prepare_batch_items 需要的最小状态（不启动浏览器、不建线程）"""
    scheduler = sched.BatchRefreshScheduler.__new__(sched.BatchRefreshScheduler)
    scheduler._container = SimpleNamespace(repo=repo)
    scheduler._config = cfg

    async def _no_sync(*_args, **_kwargs):
        return None

    scheduler._sync_cookie_before_batch = _no_sync
    scheduler._clear_progress = lambda: cleared.append(True)
    return scheduler


@pytest.fixture
def patched_config(monkeypatch):
    def _apply(limit: int):
        monkeypatch.setattr(
            yaml_config,
            "get_config",
            lambda: SimpleNamespace(batch_refresh=_cfg(limit)),
        )
        return _cfg(limit)

    return _apply


def test_new_batch_uses_max_items_per_run_and_no_user_filter():
    """新批次：只按 max_items_per_run 裁剪；list_unsold_items 不传 user_id（与执行路径原样一致）"""
    repo = FakeRepo(_items(5))
    items, processed, total = sched.select_batch_items(repo, _cfg(2), None)
    assert [it["item_id"] for it in items] == ["i0", "i1"]
    assert repo.calls == [("list_unsold_items", 2, None)]
    assert (processed, total) == (0, 2)


def test_resume_branch_drops_sold_and_keeps_progress_numbers():
    """断点续传：先滤掉暂停期间已售的，再如实回传 processed/total（不是剩余条数）"""
    resumed = {
        "task_id": 7,
        "pending_item_ids": ["i0", "gone"],
        "total": 9,
        "processed": 4,
    }
    repo = FakeRepo(
        [],
        by_ids={"i0": {"item_id": "i0", "is_sold": False}, "gone": {"item_id": "gone", "is_sold": True}},
    )
    items, processed, total = sched.select_batch_items(repo, _cfg(100), resumed)
    assert [it["item_id"] for it in items] == ["i0"]
    assert (processed, total) == (4, 9)
    # 续传不得再去查在售池（否则两个数会来自两套口径）
    assert [c[0] for c in repo.calls] == ["list_items_by_ids"]


async def test_preview_count_equals_executed_total(monkeypatch, patched_config):
    """验收点：预估 pending == 真实执行拿到的 total（同参数、无并发写入）"""
    cfg = patched_config(3)
    monkeypatch.setattr(sched, "load_resumable_progress", lambda _repo: None)
    repo = FakeRepo(_items(10))
    preview = api_batch_refresh.trigger_preview(container=SimpleNamespace(repo=repo))
    assert preview["pending"] == 3
    assert preview["at_limit"] is True

    executed_repo = FakeRepo(_items(10))
    cleared: list[bool] = []
    scheduler = _stub_scheduler(executed_repo, cfg, cleared)
    items, processed, total = await scheduler._prepare_batch_items(
        1, datetime.now(timezone.utc)
    )
    assert total == preview["pending"] == len(items)
    assert processed == preview["resumed_processed"] == 0


async def test_preview_counts_resume_remainder(monkeypatch, patched_config):
    """续传场景：预估的 pending 是「剩余未售」条数，并带回原批次进度"""
    cfg = patched_config(100)
    resumed = {"task_id": 3, "pending_item_ids": ["i0", "i1"], "total": 6, "processed": 4}
    repo = FakeRepo(
        [],
        by_ids={"i0": {"item_id": "i0", "is_sold": False}, "i1": {"item_id": "i1", "is_sold": True}},
    )
    monkeypatch.setattr(sched, "load_resumable_progress", lambda _repo: dict(resumed))

    out = api_batch_refresh.trigger_preview(container=SimpleNamespace(repo=repo))
    assert out == {
        "pending": 1,
        "limit": 100,
        "at_limit": False,
        "resumed": True,
        "resumed_processed": 4,
        "resumed_total": 6,
    }

    cleared: list[bool] = []
    scheduler = _stub_scheduler(FakeRepo([], by_ids=repo.by_ids), cfg, cleared)
    _items_out, processed, total = await scheduler._prepare_batch_items(
        2, datetime.now(timezone.utc)
    )
    assert processed == out["resumed_processed"] and total == out["resumed_total"]


def test_preview_is_read_only():
    """预估绝不允许写库/注入 Cookie：清理进度与 Cookie 同步都只属于执行路径"""
    start = ROUTE_SRC.index("def trigger_preview")
    body = ROUTE_SRC[start:]
    end = body.find("\n@router.")
    fn = body[: end if end > -1 else 2000]
    assert "load_resumable_progress(" in fn
    assert "select_batch_items(" in fn
    assert "_clear_progress" not in fn
    assert "_sync_cookie_before_batch" not in fn


def test_execution_path_goes_through_shared_selector():
    """执行路径不得自己再写一份取数（否则预估与执行必然漂移）"""
    start = SCHEDULER_SRC.index("async def _prepare_batch_items")
    body = SCHEDULER_SRC[start:]
    end = body.find("\n    async def ")
    fn = body[: end if end > -1 else 3000]
    assert "select_batch_items(" in fn
    assert "list_unsold_items(" not in fn
    assert "list_items_by_ids(" not in fn
