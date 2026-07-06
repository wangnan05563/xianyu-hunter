from __future__ import annotations

import tomllib
from pathlib import Path


def test_playwright_dependency_is_pinned_to_verified_minor() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    dependencies = pyproject["project"]["dependencies"]

    playwright_specs = [
        dep for dep in dependencies if dep.lower().startswith("playwright")
    ]

    assert playwright_specs == ["playwright>=1.60,<1.61"]
