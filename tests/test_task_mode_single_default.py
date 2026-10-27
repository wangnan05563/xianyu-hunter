"""T02963 裁决守卫：mode 默认值只归 API 契约（notify），domain 必填。

改回任何「第二份默认值」都会让这里红：
- domain 重新给 CONFIRM 默认；
- TaskCreate / TemplateCreate 默认改成别的值；
- CLI `add --mode` 或 DB 列兜底回到 confirm。
"""
from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

import pytest

from xianyu_hunter.domain.task import Task
from xianyu_hunter.infra.db_models import TaskRow
from xianyu_hunter.web.routes.api_tasks import TaskCreate
from xianyu_hunter.web.routes.api_templates import TemplateCreate

BACKEND = Path(__file__).resolve().parents[1] / "backend" / "xianyu_hunter"


def test_domain_mode_has_no_default():
    field = next(f for f in dataclasses.fields(Task) if f.name == "mode")
    assert field.default is dataclasses.MISSING, "domain 不允许再有 mode 默认值"
    assert field.default_factory is dataclasses.MISSING


def test_domain_task_requires_explicit_mode():
    with pytest.raises(TypeError):
        Task(id="t1", name="x", keyword="kw")  # type: ignore[call-arg]


def test_api_contracts_default_to_notify():
    assert TaskCreate(keyword="kw").mode == "notify"
    assert TemplateCreate(name="n", keyword="kw").mode == "notify"


def test_db_column_default_is_notify():
    assert TaskRow.__table__.c.mode.default.arg == "notify"


def _cli_add_mode_default() -> str:
    tree = ast.parse((BACKEND / "__main__.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "add":
            # 默认值挂在 args.defaults（与 args.args 尾部对齐），不在单个 arg 上
            offset = len(node.args.args) - len(node.args.defaults)
            for idx, default in enumerate(node.args.defaults):
                arg = node.args.args[offset + idx]
                if arg.arg == "mode" and isinstance(default, ast.Call):
                    return ast.literal_eval(default.args[0])
    raise AssertionError("未找到 CLI add 的 --mode 定义")


def test_cli_default_is_notify():
    assert _cli_add_mode_default() == "notify"


def test_container_reload_fallback_is_notify():
    lines = [
        ln
        for ln in (BACKEND / "container.py").read_text(encoding="utf-8").splitlines()
        if 'get("mode"' in ln
    ]
    assert lines, "container 里找不到 raw.get(\"mode\") 兜底"
    assert all("NOTIFY" in ln.upper() for ln in lines)
