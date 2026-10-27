"""数据库维护的编辑/导入/导出语义（T02576 / PRD FR-H-1 + 评审 4.2-1~4.2-3、4.2-5）

三条"假护栏 / 假回执"红线，全部源自同一类缺陷——界面说的、后端并没做：

- FR-H-1（4.2 主键）：`PATCH /tables/{t}/rows/{pk}` 里主键字段被 `continue` 静默丢弃，
  接口照样回 ok，前端照样弹「已更新」。用户以为改了主键，实际一个字节都没变。
  现在：改主键必须 400 点名，且不得写入审计里的 `update` 记录。
- 4.2-3（清空字段）：编辑提交时前端把空串字段全部丢弃，用户无法把任何字段置 NULL。
  后端本来支持 `null`，所以这里断言「显式 null 真的落成 NULL」，
  而 NOT NULL 列传 null 必须报错而不是被吞掉。
- 4.2-1/4.2-2：导入的失败行数必须如实回带（errors 只是样例，真实条数另给字段），
  导出必须是全表（接口没有筛选参数，UI 才能声称「全表」）。
"""
from __future__ import annotations

import asyncio
import inspect
import sqlite3

import pytest
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import create_engine, text

from xianyu_hunter.web.routes import api_db_admin as admin
from xianyu_hunter.web.routes.api_db_admin import ImportBody, WriteRowBody
from types import SimpleNamespace


# ============== 夹具：临时 SQLite + 白名单内的最小 tasks 表 ==============

DDL = """
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    keyword TEXT,
    min_price INTEGER,
    region TEXT
)
"""


def _request(user_id: str = "default"):
    """直调端点时顶替 FastAPI 注入的 Request（真实请求里由鉴权中间件写 state.user_id）"""
    return SimpleNamespace(state=SimpleNamespace(user_id=user_id))


@pytest.fixture
def engine(tmp_path):
    db = tmp_path / "dbadmin.db"
    eng = create_engine(f"sqlite:///{db}")
    with eng.begin() as conn:
        conn.execute(text(DDL))
        conn.execute(text("INSERT INTO tasks VALUES ('t1','原名','关键词',100,'杭州')"))
    yield eng
    eng.dispose()


@pytest.fixture
def container(engine):
    class _StubRepo:
        def __init__(self, eng):
            self.engine = eng
            self.audits: list[dict] = []

        def save_event(self, payload):
            self.audits.append(payload)
            return None

    class _StubContainer:
        def __init__(self, eng):
            self.repo = _StubRepo(eng)

    return _StubContainer(engine)


def _row(engine, pk: str = "t1") -> tuple:
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT name, keyword, min_price, region FROM tasks WHERE id=:i"), {"i": pk}
        ).first()


# ============== FR-H-1：改主键不再静默丢弃 ==============

def test_pk_change_is_rejected_with_named_consequence(container, engine):
    """把主键改成别的值必须 400，且文案点名「不可修改」与替代做法——不许再回 ok"""
    with pytest.raises(HTTPException) as ei:
        admin.update_row("tasks", "t1", WriteRowBody(values={"id": "t9", "name": "新名"}), request=_request(), container=container)
    assert ei.value.status_code == 400
    detail = ei.value.detail
    assert "主键" in detail and "不可修改" in detail
    # 拒绝必须是"整行不动"，不能一边报错一边把 name 改进去
    assert _row(engine)[0] == "原名"


def test_same_pk_in_payload_is_treated_as_unchanged(container, engine):
    """前端表单会带上主键原值：与路径一致时按"未修改主键"处理，其余字段照常更新"""
    result = admin.update_row("tasks", "t1", WriteRowBody(values={"id": "t1", "name": "新名"}), request=_request(), container=container)
    assert result["ok"] is True and result["affected"] == 1
    assert _row(engine)[0] == "新名"


def test_only_pk_in_payload_fails_loudly(container):
    """除了主键什么都没改 → 明确「没有可更新字段」，而不是"更新成功 0 个字段\""""
    with pytest.raises(HTTPException) as ei:
        admin.update_row("tasks", "t1", WriteRowBody(values={"id": "t1"}), request=_request(), container=container)
    assert ei.value.status_code == 400
    assert "没有可更新字段" in ei.value.detail


def test_rejected_update_writes_no_success_audit(container):
    """假回执的另一半：被拒绝的写入不得留下 db_admin.update 审计（否则日志看起来成功了）"""
    with pytest.raises(HTTPException):
        admin.update_row("tasks", "t1", WriteRowBody(values={"id": "t9"}), request=_request(), container=container)
    actions = [a["type"] for a in container.repo.audits]
    assert "db_admin.update" not in actions


# ============== 4.2-3：可空列真的能置 NULL ==============

def test_explicit_null_clears_nullable_column(container, engine):
    admin.update_row("tasks", "t1", WriteRowBody(values={"keyword": None, "region": None}), request=_request(), container=container)
    row = _row(engine)
    assert row[1] is None and row[3] is None
    # 未被点名的列保持原值（前端"留空=不改"的口径由此成立）
    assert row[0] == "原名"


def test_null_on_not_null_column_is_not_swallowed(container):
    """NOT NULL 列传 null 必须报错（409），不能静默改成空串或当作未提交"""
    with pytest.raises(HTTPException) as ei:
        admin.update_row("tasks", "t1", WriteRowBody(values={"name": None}), request=_request(), container=container)
    assert ei.value.status_code == 409


def test_schema_exposes_nullable_flag_for_ui_checkbox(container):
    """UI 只对可空列给「置为 NULL」勾选框，前提是 schema 接口如实标注 nullable"""
    cols = {c["name"]: c for c in admin._get_columns(container, "tasks")}
    assert cols["keyword"]["nullable"] is True
    assert cols["name"]["nullable"] is False
    assert cols["id"]["primary_key"] is True


# ============== 4.2-1：导入失败行数如实回带 ==============

def _import(container, rows, headers, mode="insert"):
    return admin.import_rows(
        "tasks", ImportBody(rows=rows, headers=headers, mode=mode, confirm_token=admin.CONFIRM_TOKEN),
        request=_request(), container=container,
    )


def test_import_reports_real_error_count_not_sample_length(container):
    """errors 只留 20 条样例，error_count 才是真实失败行数。

    旧实现前端用 `errors.length` 显示「N 错误」，50 行失败只会显示 20，
    是"成功回执掩盖真实损失"的同族缺陷。
    """
    bad = [["x%d" % i, "名", "多出来的列"] for i in range(25)]  # 与 2 列表头不符 → 每行都失败
    result = _import(container, bad, ["id", "name"])
    assert result["error_count"] == 25
    assert len(result["errors"]) == 20
    assert result["inserted"] == 0 and result["skipped"] == 0


def test_import_skips_conflict_and_counts_it(container, engine):
    """mode=insert 的真实语义：同主键跳过、不覆盖——UI 的「跳过冲突」承诺据此成立"""
    result = _import(container, [["t1", "覆盖名"], ["t2", "新行"]], ["id", "name"])
    assert result["skipped"] == 1 and result["inserted"] == 1 and result["error_count"] == 0
    assert _row(engine)[0] == "原名"  # 冲突行没被覆盖


def test_import_mode_validation_rejects_replace_per_d8(container):
    """D-8 裁决（2026-10-27，A 不开放）：replace 直接 400，不再有 INSERT OR REPLACE 路径。

    保留这一条是为了钉住「破坏性分支已被删除」——若将来有人把 mode 白名单放宽，
    这里会红，而不是等用户在界面上发现「导入把既有行覆盖了」。
    """
    assert admin.ImportBody(rows=[["x"]]).mode == "insert"
    with pytest.raises(HTTPException) as ei:
        admin._validate_import_body(ImportBody(rows=[["x"]], mode="replace", confirm_token=admin.CONFIRM_TOKEN))
    assert "D-8" in ei.value.detail
    with pytest.raises(HTTPException) as ei2:
        admin._validate_import_body(ImportBody(rows=[["x"]], mode="upsert", confirm_token=admin.CONFIRM_TOKEN))
    assert "D-8" in ei2.value.detail


def test_import_build_sql_never_emits_or_replace():
    """SQL 构造层只产出 plain INSERT：即使有人绕过校验，也没有覆盖语句可生成。"""
    sql = admin._build_insert_sql("tasks", {"id": 1, "name": "x"})
    assert sql.startswith("INSERT INTO tasks")
    assert "OR REPLACE" not in sql.upper()


# ============== 4.2-2：导出确实是"全表" ==============

def _drain(resp: StreamingResponse) -> str:
    it = resp.body_iterator
    if hasattr(it, "__aiter__"):
        async def go():
            out = []
            async for chunk in it:
                out.append(chunk if isinstance(chunk, str) else chunk.decode("utf-8"))
            return "".join(out)
        return asyncio.run(go())
    return "".join(c if isinstance(c, str) else c.decode("utf-8") for c in it)


def test_export_has_no_filter_params_so_ui_must_say_full_table(container):
    """导出接口没有任何筛选参数 → 按钮只能声称「全表」，不能说「导出当前搜索结果」"""
    params = inspect.signature(admin.export_rows).parameters
    assert not {"search", "q", "limit", "offset", "filters"} & set(params)


def test_export_csv_contains_every_row(container, engine):
    with engine.begin() as conn:
        for i in range(2, 6):
            conn.execute(text("INSERT INTO tasks VALUES (:i,:n,NULL,NULL,NULL)"), {"i": f"t{i}", "n": f"名{i}"})
    total = None
    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM tasks")).scalar()
    body = _drain(admin.export_rows("tasks", format="csv", container=container))
    data_lines = [ln for ln in body.splitlines() if ln.strip()][1:]  # 去掉表头
    assert len(data_lines) == total == 5


def test_export_reports_real_row_count(container, engine):
    """X-Export-Rows 回带真实行数（T02707）：前端据此区分 0 行与正常导出"""
    for fmt in ("csv", "json"):
        resp = admin.export_rows("tasks", format=fmt, container=container)
        assert resp.headers["x-export-rows"] == "1"

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM tasks"))
    resp = admin.export_rows("tasks", format="csv", container=container)
    assert resp.headers["x-export-rows"] == "0"


def test_unknown_table_is_rejected_before_any_scan(container):
    with pytest.raises(HTTPException) as ei:
        admin.export_rows("sqlite_master", format="csv", container=container)
    assert ei.value.status_code == 400


# ============== 回归：整行更新语义未被破坏 ==============

def test_update_rejects_multi_pk_table(container, engine, monkeypatch):
    """联合主键表仍明确拒绝，而不是"看起来更新了\""""
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE task_deps (a TEXT, b TEXT, PRIMARY KEY (a, b))"))
        conn.execute(text("INSERT INTO task_deps VALUES ('1','2')"))
    monkeypatch.setattr(admin, "ALLOWED_TABLES", tuple(admin.ALLOWED_TABLES) + ("task_deps",))
    with pytest.raises(HTTPException) as ei:
        admin.update_row("task_deps", "1", WriteRowBody(values={"b": "9"}), request=_request(), container=container)
    assert "仅支持单主键表" in ei.value.detail


def test_value_conversion_error_is_surfaced(container):
    """类型转换失败要说清楚是哪一列，避免用户把「更新失败」当成后端坏了"""
    with pytest.raises(HTTPException) as ei:
        admin.update_row("tasks", "t1", WriteRowBody(values={"min_price": "abc"}), request=_request(), container=container)
    assert ei.value.status_code == 400
    assert "字段类型转换失败" in ei.value.detail


def test_db_admin_module_still_has_no_silent_pk_discard():
    """正向断言：主键分支必须显式拒绝，不许退回 `continue` 吞掉（4.2/FR-H-1 复发防线）"""
    src = inspect.getsource(admin._collect_update_values)
    assert "HTTPException" in src
    assert "主键" in src and "不可修改" in src


def test_sqlite_roundtrip_helper_sanity(engine):
    """夹具自检：确认断言读的是真实库，而不是内存里的假数据"""
    assert _row(engine)[0] == "原名"
    with sqlite3.connect(str(engine.url.database)) as raw:
        assert raw.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 1
