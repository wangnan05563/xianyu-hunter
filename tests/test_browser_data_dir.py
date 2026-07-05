import sys
from pathlib import Path

from xianyu_hunter import paths
from xianyu_hunter.infra.browser import BrowserManager


def _mark_frozen(monkeypatch, tmp_path: Path) -> Path:
    appdata = tmp_path / "AppData" / "Roaming"
    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    return appdata


def test_frozen_browser_data_dir_resolves_relative_config_under_appdata(monkeypatch, tmp_path):
    appdata = _mark_frozen(monkeypatch, tmp_path)

    resolved = paths.get_browser_data_dir("./browser-data")

    assert resolved == appdata / "XianyuHunter" / "data" / "browser-data"
    assert resolved.exists()


def test_frozen_browser_data_dir_respects_absolute_override(monkeypatch, tmp_path):
    _mark_frozen(monkeypatch, tmp_path)
    custom_dir = tmp_path / "custom-browser-profile"

    resolved = paths.get_browser_data_dir(custom_dir)

    assert resolved == custom_dir
    assert resolved.exists()


def test_browser_manager_uses_packaged_appdata_for_relative_user_data_dir(monkeypatch, tmp_path):
    appdata = _mark_frozen(monkeypatch, tmp_path)

    manager = BrowserManager(user_data_dir="./browser-data-test")

    assert manager.user_data_dir == appdata / "XianyuHunter" / "data" / "browser-data-test"
    assert manager.user_data_dir.exists()
