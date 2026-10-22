"""T02883：events.type 是事件的身份牌，写入侧不许静默落 NULL。

来源：依赖链激活（scheduler.py / api_orders.py）与登录态自愈（cookie_status.py）
三处 save_event 只写了 stage，没写 type。EventRow.type 是 nullable，插入不报错，
代价是行落在库里但时间线只能显示通用「事件」，按 type 精确匹配的订阅过滤还会把整行筛掉。

同批清点的第二扇门：upsert_eval_event 用 event.get("type", "eval.scored") 只喂给 DELETE
过滤，INSERT 走原始字典，漏写同样落 NULL（stage 有 NOT NULL 兜着、type 没有 ——
这个不对称正是本单的存在理由）。
"""
from __future__ import annotations

import ast
import tempfile
from pathlib import Path

import pytest

from xianyu_hunter.domain.events import EventType
from xianyu_hunter.infra.repository import Repository

PKG = Path(__file__).resolve().parents[1] / "backend" / "xianyu_hunter"


@pytest.fixture
def tmp_repo() -> Repository:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        repo = Repository(str(Path(d) / "test.db"))
        yield repo
        # Windows 上必须释放文件句柄，否则临时目录删不掉
        repo.engine.dispose()


def test_save_event_缺少type直接抛错(tmp_repo: Repository) -> None:
    """静默 NULL 比报错难排查：这里不接受兜底值，缺失就抛"""
    with pytest.raises(ValueError, match="缺少 type"):
        tmp_repo.save_event({
            "task_id": "t1",
            "stage": "dep_triggered",
            "level": "info",
            "message": "上游任务成功，自动激活下游任务",
        })


def test_save_event_type为空串同样拒绝(tmp_repo: Repository) -> None:
    """`"type": ""` 与漏写键的后果一样（落库后按 type 过滤筛不掉、标签显示不出来）"""
    with pytest.raises(ValueError, match="缺少 type"):
        tmp_repo.save_event({"type": "", "task_id": "t1", "level": "info", "message": "m"})


def test_依赖链激活事件落库带类型(tmp_repo: Repository) -> None:
    """与 scheduler.py / api_orders.py 的写法逐字对齐：type 补上，stage 语义不动"""
    tmp_repo.save_event({
        "type": EventType.TASK_DEP_TRIGGERED.value,
        "task_id": "t1",
        "stage": "dep_triggered",
        "level": "info",
        "message": "上游任务 t0 成功，自动激活下游任务",
        "payload": '{"upstream_task": "t0", "triggered_by": "dep_chain"}',
    })
    rows = tmp_repo.list_events(task_id="t1")
    assert [r["type"] for r in rows] == ["task.dep_triggered"]
    assert rows[0]["stage"] == "dep_triggered"


def test_登录态自愈事件落库带类型(tmp_repo: Repository) -> None:
    tmp_repo.save_event({
        "type": EventType.AUTH_COOKIE_SELF_HEAL.value,
        "stage": "cookie_self_heal",
        "level": "info",
        "message": "登录态自动自愈",
        "payload": "{}",
        "user_id": "u1",
    })
    rows = tmp_repo.list_events(user_id="u1")
    assert [r["type"] for r in rows] == ["auth.cookie_self_heal"]


def test_两个新类型走后端严重度口径() -> None:
    """严重度没登记时 severity_of 会兜底 info，等于「所有事件都不重要」，所以显式钉住"""
    from xianyu_hunter.domain.events import EVENT_SEVERITY, severity_of

    # 「在册」和「值」要分别钉：severity_of 对漏登记的类型兜底 info，
    # 只断言等值的话，把 EVENT_SEVERITY 里那行删掉这条用例照样绿（守卫自己变哑）。
    assert EventType.TASK_DEP_TRIGGERED in EVENT_SEVERITY
    assert EventType.AUTH_COOKIE_SELF_HEAL in EVENT_SEVERITY
    assert severity_of(EventType.TASK_DEP_TRIGGERED) == "info"
    assert severity_of(EventType.AUTH_COOKIE_SELF_HEAL) == "important"


# 传变量而非行字典的调用点：结构上扫不出键，逐个登记并在别处单独钉
# （写成注释或 `continue` 就等于免检牌，新增同类位点必须先进这张表）
_VARIABLE_EVENT_ROW_SITES = {
    "modules/price_watch.py:event_row",
}


def test_包内save_event的行字典必须带type键() -> None:
    """棘轮：新增写路径漏 "type" 键在这里红，而不是等到线上出现一堆「事件」标签的 NULL 行。

    为什么按 AST 而不按扫串：扫串会把 `event["type"]` 这类读侧代码算进来（T02850 实测过），
    红之后的修法变成改说法，比没有守卫更糟。
    """
    offenders: list[str] = []
    variable_sites: set[str] = set()
    for p in sorted(PKG.rglob("*.py")):
        rel = p.relative_to(PKG).as_posix()
        tree = ast.parse(p.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if getattr(node.func, "attr", "") != "save_event":
                continue
            arg = node.args[0] if node.args else None
            if isinstance(arg, ast.Dict):
                keys = [k.value for k in arg.keys if isinstance(k, ast.Constant)]
                if "type" not in keys:
                    offenders.append(f"{rel}:{node.lineno} keys={keys}")
            elif isinstance(arg, ast.Name):
                variable_sites.add(f"{rel}:{arg.id}")
            else:
                offenders.append(f"{rel}:{node.lineno} arg={type(arg).__name__} 写法不受支持")
    assert offenders == []
    assert variable_sites == _VARIABLE_EVENT_ROW_SITES, (
        "save_event 传变量的调用点变了：新位点要先确认它的行字典带 type，再登记进本表"
    )


def test_降价事件行带type() -> None:
    """price_watch 的两处 save_event 传的是变量，单独钉它构造的行字典里有 type"""
    src = (PKG / "modules" / "price_watch.py").read_text(encoding="utf-8-sig")
    assert src.count('"type": EventType.PRICE_DROPPED.value') == 2


def _count_in_pkg(marker: str) -> dict[str, int]:
    """按「文件 → 出现次数」返回，不返回布尔：存在性断言会被「补了一处漏了另一处」蒙过去"""
    return {
        p.relative_to(PKG).as_posix(): n
        for p in sorted(PKG.rglob("*.py"))
        if (n := p.read_text(encoding="utf-8-sig").count(marker))
    }


def test_依赖链两处的type必须同名() -> None:
    """scheduler（定时链）与 api_orders（订单成功级联）是同一件事的两个入口。

    两处类型不同名 = 时间线里出现两个「激活」标签、订阅只能筛到其中一个，
    所以钉的是「恰好这两处、各一次」，而不是「某个文件里有这个类型」。
    """
    assert _count_in_pkg('"type": EventType.TASK_DEP_TRIGGERED.value') == {
        "modules/scheduler.py": 1,
        "web/routes/api_orders.py": 1,
    }
    assert _count_in_pkg('"type": EventType.AUTH_COOKIE_SELF_HEAL.value') == {
        "web/services/cookie_status.py": 1,
    }


def test_upsert_eval_event_漏写type不落NULL(tmp_repo: Repository) -> None:
    """save_event 之外的第二扇门：本方法用 event.get("type", 兜底) 只喂 DELETE 过滤，
    INSERT 走原始字典 —— 漏写照样落 NULL，且部分唯一索引（WHERE type='eval.scored'）
    管不到 NULL 行，去重同时失效。
    """
    tmp_repo.upsert_eval_event({
        "task_id": "t9", "item_id": "i1", "stage": "eval", "level": "info", "message": "评估完成", "payload": "{}",
    })
    rows = tmp_repo.list_events(task_id="t9")
    assert [r["type"] for r in rows] == ["eval.scored"]


def test_upsert_eval_event_空串type同样兜底(tmp_repo: Repository) -> None:
    """`"type": ""` 是 falsy：原先 DELETE 按空串过滤、INSERT 落空串，后果与 NULL 相同"""
    tmp_repo.upsert_eval_event({
        "type": "", "task_id": "t8", "item_id": "i1", "stage": "eval", "level": "info",
        "message": "m", "payload": "{}",
    })
    assert [r["type"] for r in tmp_repo.list_events(task_id="t8")] == ["eval.scored"]


def test_upsert_eval_event_兜底后仍然去重(tmp_repo: Repository) -> None:
    """把「兜底值落到 INSERT」这条修法的效果钉成第二症状：连写两次只剩一行。

    只有当 DELETE 过滤的 type 与 INSERT 写入的 type 同源时才成立；
    两者分叉（改回 event.get 默认不落盘）时这里会剩两行。
    """
    row = {"task_id": "t7", "item_id": "i1", "stage": "eval", "level": "info", "message": "m", "payload": "{}"}
    tmp_repo.upsert_eval_event(row)
    tmp_repo.upsert_eval_event({**row, "payload": '{"score": 2}'})
    rows = tmp_repo.list_events(task_id="t7")
    assert len(rows) == 1, f"去重失效，出现 {len(rows)} 行：{[r['type'] for r in rows]}"

