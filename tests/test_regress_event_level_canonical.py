"""T02683 回归：events.level 只写小写全词，别名不得回流

裁决「小写全词」落地后，三处纪律必须同时成立，缺一处就会出现「写入值看不见」：
1. 写侧（含审计/通知/评估等所有 events 写入点）只写 info / warning / error / debug / trace；
2. 启动迁移把历史 warn/err/大写行幂等改写成规范值；
3. 读侧不再有任何别名展开，前端下拉也只传规范值。

通知域（notifications.level）是另一套枚举，不在本单范围，扫描时显式排除。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend" / "xianyu_hunter"

CANONICAL = {"trace", "debug", "info", "warning", "error"}
# 这些文件里的 level= 写的是 notifications.level（info/warn/err），与 events 无关
NOTIFICATION_LEVEL_FILES = {
    "modules/price_watch.py",
    "web/services/notification_engine.py",
    "domain/notification.py",
    "infra/repo_notifications.py",
    "web/routes/api_notifications.py",
}

LEGACY_WRITE = re.compile(r"level\s*[=:]\s*[\"'](warn|err)[\"']")


def _event_writers() -> list[tuple[Path, int, str]]:
    hits = []
    for path in sorted(BACKEND.rglob("*.py")):
        rel = path.relative_to(BACKEND).as_posix()
        if rel in NOTIFICATION_LEVEL_FILES:
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if LEGACY_WRITE.search(line):
                hits.append((path, lineno, line.strip()))
    return hits


def test_no_legacy_level_literals_in_event_writers() -> None:
    hits = _event_writers()
    assert hits == [], "events.level 仍在写缩写：\n" + "\n".join(
        f"{p.relative_to(ROOT)}:{n}: {line}" for p, n, line in hits
    )


def test_level_alias_table_removed_from_backend() -> None:
    import xianyu_hunter.domain.events as events

    assert not hasattr(events, "level_literals")
    assert not hasattr(events, "_LEVEL_ALIASES")
    src = (BACKEND / "infra" / "repo_events.py").read_text(encoding="utf-8")
    assert "level_literals" not in src


def test_frontend_dropdowns_send_canonical_levels() -> None:
    for rel in ("frontend/src/pages/Logs/Logs.tsx", "frontend/src/mobile/pages/Logs/index.tsx"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert not re.search(r"value:\s*[\"'](warn|err)[\"']", src), f"{rel} 仍传旧缩写"


def test_frontend_alias_map_removed() -> None:
    src = (ROOT / "frontend/src/constants/logLevels.ts").read_text(encoding="utf-8")
    assert "LEVEL_ALIASES" not in src


def test_histogram_counts_canonical_words() -> None:
    from xianyu_hunter.infra.repo_events import _count_event_levels

    events = [
        {"level": "error", "stage": "notify"},
        {"level": "warning", "stage": "eval"},
        {"level": "info", "stage": "search_hit"},
        {"level": "info", "stage": "notify"},
    ]
    assert _count_event_levels(events) == (1, 1, 1)


# 时间轴是 events.level 的读侧：移动端曾只认 warn/err，归一后严重度整段失效
TIMELINE_LEVEL_FILES = (
    "frontend/src/pages/Timeline/components/TimelineList.tsx",
    "frontend/src/pages/Timeline/components/TimelineItem.tsx",
    "frontend/src/mobile/pages/Timeline/index.tsx",
)


def _frontend_code_lines(rel: str) -> str:
    return "\n".join(
        line
        for line in (ROOT / rel).read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith(("//", "*", "/*"))
    )


def test_frontend_timeline_reads_canonical_levels() -> None:
    for rel in TIMELINE_LEVEL_FILES:
        code = _frontend_code_lines(rel)
        assert not re.search(r"level\s*===?\s*[\"'](warn|err)[\"']", code), (
            f"{rel} 仍在按旧缩写判断严重度"
        )
    severity = _frontend_code_lines("frontend/src/constants/eventTypes.ts")
    assert not re.search(r"^\s*(warn|err)\s*:", severity, re.M), (
        "SEVERITY_CONFIG 又长回了 warn/err 别名键"
    )

