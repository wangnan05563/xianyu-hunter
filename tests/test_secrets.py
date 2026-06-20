"""Secrets 单元测试（不依赖 Windows DPAPI，使用回退实现）"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from xianyu_hunter.infra import secrets


@pytest.fixture
def tmp_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """强制使用回退实现（避免污染真实 keyring）"""
    monkeypatch.setattr(secrets, "KEYRING_AVAILABLE", False)
    monkeypatch.setattr(secrets, "_FALLBACK_FILE", tmp_path / "secrets.json")


def test_set_get_secret(tmp_fallback: None) -> None:
    """基本存取"""
    secrets.set_secret("test_key", "test_value")
    assert secrets.get_secret("test_key") == "test_value"


def test_delete_secret(tmp_fallback: None) -> None:
    """删除后读取为 None"""
    secrets.set_secret("del_key", "value")
    assert secrets.get_secret("del_key") == "value"
    secrets.delete_secret("del_key")
    assert secrets.get_secret("del_key") is None


def test_list_keys(tmp_fallback: None) -> None:
    """list_keys 返回已存储的键"""
    secrets.set_secret("a", "1")
    secrets.set_secret("b", "2")
    keys = secrets.list_keys()
    # 回退实现应返回所有键
    assert "a" in keys
    assert "b" in keys


def test_is_available_returns_bool() -> None:
    """is_available 返回布尔"""
    result = secrets.is_available()
    assert isinstance(result, bool)
