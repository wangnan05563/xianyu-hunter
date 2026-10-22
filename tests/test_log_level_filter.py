"""日志级别筛选别名（T02569 / REQ-037、REQ-039 / 评审 2.7-1、2.7-2、2.7-4）

钉住两件只有真数据才会暴露的问题：

1. 库里 events.level 的字面值历史上并不统一：实测开发库同时存在
   `info`(15173) / `err`(30) / `warning`(4)，另有代码路径写 `error`。
   原先 list_events 用 `level == :level` 精确匹配，前端下拉传 `warn`
   就一条 warning 也查不到，传 `err` 查不到写成 error 的行——
   搜索结果、级别分布、导出 CSV 三处一起少数据。
2. 导出 CSV 现在与页面同源：exportUrl 拼上 q/level/task_id，
   后端必须真的按这些参数过滤（评审前是固定 URL 导全量，文案却写「导出当前日志」）。

级别写入侧的枚举归一是独立范围（与订单状态 T02585 同类），
本测试钉的是读取侧互认；归一落地后这些别名桶应随之删除。

按前端实际调用的端点打真实 FastAPI 应用（请求序列化、白名单校验、Repository
写入、回读全链路为真），只把数据库换成临时 SQLite，不使用 Mock 替身。
"""
from __future__ import annotations

import pytest


class _ContainerShim:
    """只提供路由实际用到的 `.repo`，其余容器资源与本测试无关"""

    def __init__(self, repo):
        self.repo = repo


@pytest.fixture
def api(tmp_path):
    from fastapi.testclient import TestClient

    from xianyu_hunter.config import get_settings
    from xianyu_hunter.infra.repository import Repository
    from xianyu_hunter.web.app import create_app
    from xianyu_hunter.web.deps import get_container

    repo = Repository(db_path=str(tmp_path / "ux569.db"))
    app = create_app()
    app.dependency_overrides[get_container] = lambda: _ContainerShim(repo)

    client = TestClient(app)
    # /api/* 全量需鉴权：与 tests/test_order_stats_and_notif_batch.py 同一口径
    client.cookies.set("xh_token", get_settings().web_token)
    return client, repo


def _mk_event(repo, *, level: str, message: str, task_id: str = "t1") -> int:
    return repo.save_event({
        "type": "system.test",
        "stage": "test",
        "level": level,
        "message": message,
        "task_id": task_id,
    })


# ---------------- 1. 领域层：别名展开 ----------------

def test_level_literals_expands_aliases() -> None:
    from xianyu_hunter.domain.events import level_literals

    # 每种写法同时给出小写/大写两形（SQLite 字符串比较大小写敏感，库里两种都出现过）
    assert set(level_literals("err")) == {"err", "ERR", "error", "ERROR"}
    assert set(level_literals("error")) == {"err", "ERR", "error", "ERROR"}
    assert set(level_literals("warn")) == {"warn", "WARN", "warning", "WARNING"}
    assert set(level_literals("WARN")) == {"warn", "WARN", "warning", "WARNING"}
    assert set(level_literals("info")) == {"info", "INFO"}
    assert set(level_literals("debug")) == {"debug", "DEBUG"}


def test_level_literals_empty_and_unknown() -> None:
    from xianyu_hunter.domain.events import level_literals

    # 空值 → 空元组（调用方据此不加过滤分支）
    assert level_literals(None) == ()
    assert level_literals("  ") == ()
    # 未知字面值原样给出大小写两形，保持精确匹配语义，不放大成「不过滤」
    assert set(level_literals("Critical")) == {"critical", "CRITICAL"}


# ---------------- 2. 仓储层：按别名组匹配 ----------------

def test_list_events_matches_both_spellings(api) -> None:
    _, repo = api
    _mk_event(repo, level="err", message="缩写写法")
    _mk_event(repo, level="error", message="全称写法")
    _mk_event(repo, level="warning", message="全称警告")
    _mk_event(repo, level="warn", message="缩写警告")
    _mk_event(repo, level="info", message="信息")

    errors = {e["message"] for e in repo.list_events(level="err", limit=50)}
    assert errors == {"缩写写法", "全称写法"}

    warns = {e["message"] for e in repo.list_events(level="warn", limit=50)}
    assert warns == {"全称警告", "缩写警告"}

    # 反向：以全称筛选也必须命中缩写行
    assert {e["message"] for e in repo.list_events(level="error", limit=50)} == {"缩写写法", "全称写法"}

    # 其余级别不受影响
    assert {e["message"] for e in repo.list_events(level="info", limit=50)} == {"信息"}


def test_list_events_keeps_uppercase_rows_visible(api) -> None:
    """大小写两形都要命中：既有 tests/test_repository.py::test_event_save_and_list 写的是大写级别

    改成只认小写会让「历史上写过大写字面值的库」一条查不到，属回归。
    """
    _, repo = api
    _mk_event(repo, level="ERROR", message="大写历史行")
    _mk_event(repo, level="WARN", message="大写警告行")

    assert {e["message"] for e in repo.list_events(level="err", limit=50)} == {"大写历史行"}
    assert {e["message"] for e in repo.list_events(level="warn", limit=50)} == {"大写警告行"}
    # 调用方直接传大写（绕过路由归一）同样可用
    assert {e["message"] for e in repo.list_events(level="ERROR", limit=50)} == {"大写历史行"}


# ---------------- 3. 搜索端点：筛选与分布同源 ----------------

def test_search_endpoint_filters_by_alias_group(api) -> None:
    client, repo = api
    _mk_event(repo, level="err", message="E1")
    _mk_event(repo, level="error", message="E2")
    _mk_event(repo, level="warning", message="W1")
    _mk_event(repo, level="info", message="I1")

    res = client.get("/api/logs/search", params={"level": "err", "limit": 50})
    assert res.status_code == 200
    body = res.json()
    assert {i["message"] for i in body["items"]} == {"E1", "E2"}
    assert body["matched_levels"].get("err") == 1
    assert body["matched_levels"].get("error") == 1

    res = client.get("/api/logs/search", params={"level": "warn", "limit": 50})
    assert {i["message"] for i in res.json()["items"]} == {"W1"}


def test_search_rejects_out_of_enum_level(api) -> None:
    client, _ = api
    # 入参白名单不变：归一化不等于放开任意值
    assert client.get("/api/logs/search", params={"level": "fatal"}).status_code == 422


def test_search_total_estimate_counts_all_matches_before_paging(api) -> None:
    """total_estimate 是命中总数，不是当页条数（T02678）。

    原先先切片再 len()，total_estimate 恒等于 count，前端无法区分「共 N 条」与
    「已展示 M 条」，截断提示也就永远不会出现。
    """
    client, repo = api
    for i in range(5):
        _mk_event(repo, level="info", message=f"I{i}")

    body = client.get("/api/logs/search", params={"limit": 2}).json()
    assert len(body["items"]) == 2
    assert body["count"] == 2
    assert body["total_estimate"] == 5


# ---------------- 4. 导出端点：与页面筛选拼合一致 ----------------

def test_export_csv_honors_filters(api) -> None:
    client, repo = api
    _mk_event(repo, level="err", message="要导出", task_id="tA")
    _mk_event(repo, level="error", message="也要导出", task_id="tA")
    _mk_event(repo, level="info", message="级别不符", task_id="tA")
    _mk_event(repo, level="err", message="任务不符", task_id="tB")

    res = client.get("/api/logs/export", params={"format": "csv", "level": "err", "task_id": "tA"})
    assert res.status_code == 200
    text = res.text
    assert "要导出" in text
    assert "也要导出" in text
    assert "级别不符" not in text
    assert "任务不符" not in text
    assert res.headers["content-disposition"].startswith("attachment; filename=")


def test_export_csv_keyword_filter_combined_with_level(api) -> None:
    client, repo = api
    _mk_event(repo, level="warn", message="价格偏离")
    _mk_event(repo, level="warning", message="价格偏离-第二次")
    _mk_event(repo, level="warning", message="无关内容")

    res = client.get("/api/logs/export", params={"format": "csv", "level": "warn", "q": "价格偏离"})
    text = res.text
    assert "价格偏离" in text
    assert "价格偏离-第二次" in text
    assert "无关内容" not in text
