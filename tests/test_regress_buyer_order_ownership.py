"""T02832 回归：buyer 自动抢单的 orders 写入必须带 user_id（按 task_id 反查）

为什么用 ast 而不是只写行为用例：三处写入（真实单/失败单/演练报告）的 user_id
来自 `_order_owner_user_id(task_id)`，行为用例只会覆盖被触发的那条路径，
删掉任意一处的透传不会让其余用例变红。这里直接扫真实调用点，缺一处就点名。
"""
from __future__ import annotations

import ast
from pathlib import Path

BUYER = Path(__file__).resolve().parents[1] / "backend" / "xianyu_hunter" / "modules" / "buyer.py"


def _parse() -> ast.AST:
    return ast.parse(BUYER.read_text(encoding="utf-8-sig"))


def test_buyer_order_writes_all_pass_user_id() -> None:
    calls = [
        node for node in ast.walk(_parse())
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "upsert_order"
    ]
    assert len(calls) == 3, (
        f"buyer 里 upsert_order 调用点数量变了（{len(calls)}）："
        "新增写入点同样要按 task_id 反查归属，不能落 default"
    )
    missing = [c.lineno for c in calls if not any(kw.arg == "user_id" for kw in c.keywords)]
    assert missing == [], f"这些 upsert_order 调用没传 user_id（订单会落到 default）: {missing}"


def test_buyer_order_owner_resolves_from_task() -> None:
    """归属必须来自任务反查；挂错对象（例如按商品/会话反查）AST 看不出来，这里钉住 get_task"""
    fn = next(
        node for node in ast.walk(_parse())
        if isinstance(node, ast.FunctionDef) and node.name == "_order_owner_user_id"
    )
    attrs = [n.attr for n in ast.walk(fn) if isinstance(n, ast.Attribute)]
    assert "get_task" in attrs
