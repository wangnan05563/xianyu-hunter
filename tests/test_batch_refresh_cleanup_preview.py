"""批量采集清理预览与真实删除同源（T02578 / PRD 5.4-4.4-3、4.4-4）

本页面此前有两处「假数字/假回执」：

- 清理确认框只写「确认清理 30 天前的历史记录？」，不告诉用户会删掉几条；前端如果
  偷懒拿当前筛选的 `total` 顶上，那个数是「筛出来的条数」（且列表统计跨用户），与
  DELETE 的 `user_id == "default" AND started_at < cutoff` 根本不是同一个分母。
- 概览卡片标题写「总执行次数」，实际渲染的是筛选条件下的 `total`。

因此本文件的核心断言是：**预览条数 == 实际删除条数**（days>0 与 days=0 两个分支都验），
以及路由顺序（`/history/cleanup-preview` 必须早于 `/history/{history_id}`，否则 422）。
"""
from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from xianyu_hunter.infra.repository import Repository
from xianyu_hunter.web.deps import get_container
from xianyu_hunter.web.routes import api_batch_refresh


NOW = dt.datetime.now(dt.timezone.utc)


def _row(task_id: int, started_at: dt.datetime, user_id: str = "default") -> dict:
    return {
        "task_id": task_id,
        "trigger_source": "manual",
        "started_at": started_at,
        "completed_at": started_at + dt.timedelta(seconds=5),
        "total": 3,
        "success": 3,
        "failed": 0,
        "skipped": 0,
        "status": "completed",
        "consecutive_failures": 0,
        "duration_ms": 5000,
        "user_id": user_id,
    }


@pytest.fixture
def repo(tmp_path):
    r = Repository(str(tmp_path / "t02578.db"))
    # 4 条本用户记录：2 条超过 30 天、2 条在 30 天内；外加 1 条他人记录（30 天前）
    r.save_batch_refresh_history(_row(1, NOW - dt.timedelta(days=45)))
    r.save_batch_refresh_history(_row(2, NOW - dt.timedelta(days=31)))
    r.save_batch_refresh_history(_row(3, NOW - dt.timedelta(days=10)))
    r.save_batch_refresh_history(_row(4, NOW - dt.timedelta(days=1)))
    r.save_batch_refresh_history(_row(5, NOW - dt.timedelta(days=40), user_id="other"))
    return r


@pytest.fixture
def client(repo):
    app = FastAPI()
    app.include_router(api_batch_refresh.router)
    app.dependency_overrides[get_container] = lambda: SimpleNamespace(repo=repo)
    return TestClient(app)


# ============== 4.4-3：预览条数与 DELETE 逐字同源 ==============
def test_preview_days30_matches_rows_deleted(repo):
    """days=30：预览条数必须等于 cleanup_old_batch_refresh_history 的真实 rowcount

    本用户 30 天前的是 task_id 1/2 → 2 条；user_id="other" 的那条不能被计入，
    也不能被删掉（DELETE 带 user_id 过滤）。
    """
    cutoff = NOW - dt.timedelta(days=30)
    preview = repo.count_batch_refresh_history_before(cutoff, user_id="default")
    deleted = repo.cleanup_old_batch_refresh_history(30, user_id="default")
    assert preview == deleted == 2
    # 他人记录仍在（隔离口径）
    assert repo.count_batch_refresh_history_before(None, user_id="other") == 1


def test_preview_days0_matches_full_table_clear(client, repo):
    """days=0 走整表 DELETE（无 user 过滤）：预览同样必须不加 user 过滤"""
    total_before = repo.count_batch_refresh_history_before(None, user_id=None)
    assert total_before == 5  # 含 other 的 1 条
    resp = client.get("/api/batch-refresh/history/cleanup-preview", params={"days": 0})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["matched"] == total_before
    assert body["scope"] == "all_tables_rows"

    deleted = client.request(
        "DELETE", "/api/batch-refresh/history", params={"days": 0}
    ).json()["deleted"]
    assert deleted == body["matched"]
    assert repo.count_batch_refresh_history_before(None, user_id=None) == 0


def test_preview_boundary_uses_strict_less_than(repo):
    """边界口径：`started_at < cutoff`（严格小于）

    若误用 `<=`（列表统计的 `end_dt` 就是 <=），cutoff 当刻那条会被预览计入却不删除，
    出现「预览 3 条、实删 2 条」。DELETE 内部自己算 cutoff、与实时钟耦合，
    因此这里直接把仓储方法的比较语义钉死，而不是靠 live now 对齐。
    """
    cutoff = NOW - dt.timedelta(days=30)
    repo.save_batch_refresh_history(_row(9, cutoff))
    assert repo.count_batch_refresh_history_before(cutoff, user_id="default") == 2
    # 恰在 cutoff 上的记录：cutoff 往后挪 1 秒才被计入，证明用的是严格小于
    assert repo.count_batch_refresh_history_before(
        cutoff + dt.timedelta(seconds=1), user_id="default"
    ) == 3
    # 且删除路径同口径：30 天真实删除后，边界那条被删（内部 cutoff 已晚于它）
    deleted = repo.cleanup_old_batch_refresh_history(30, user_id="default")
    assert deleted == 3
    # 本用户剩 2 条（10 天、1 天），other 用户那条不受影响
    assert repo.count_batch_refresh_history_before(None, user_id="default") == 2
    assert repo.count_batch_refresh_history_before(None, user_id="other") == 1


def test_preview_route_not_shadowed_by_id_param(client):
    """路由顺序：/history/cleanup-preview 必须声明在 /history/{history_id} 之前

    否则 "cleanup-preview" 会被当成 history_id 走 int 校验 → 422，前端预览恒失败。
    """
    resp = client.get("/api/batch-refresh/history/cleanup-preview", params={"days": 30})
    assert resp.status_code == 200, resp.text
    assert {"days", "cutoff", "matched", "scope"} <= set(resp.json())


def test_history_detail_accepts_user_id(client):
    """详情路由按 `user_id=` 调用仓储：签名缺参会直接 TypeError → 500

    T02578 真机验收点击「详情」时暴露，已在 repo 侧补齐 user_id 过滤。
    """
    resp = client.get("/api/batch-refresh/history/1")
    assert resp.status_code == 200, resp.text
    assert resp.json()["task_id"] == 1


def test_cleanup_days0_scope_ignores_user_filter(client, repo):
    """days>0 的预览按 user 维度统计并回传 scope="user"，供前端文案区分两种口径"""
    body = client.get(
        "/api/batch-refresh/history/cleanup-preview", params={"days": 30}
    ).json()
    assert body["scope"] == "user"
    assert body["matched"] == 2  # 不含 other 用户那条
    assert body["cutoff"] is not None
