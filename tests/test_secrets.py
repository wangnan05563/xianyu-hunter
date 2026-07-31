"""Secrets 单元测试（不依赖 Windows DPAPI，使用回退实现）"""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

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


def test_runtime_broken_after_no_keyring_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """运行时抛 NoKeyringError 后应永久降级到 fallback

    为什么需要这个测试：keyring import 成功 ≠ 后端可用。在受限会话中
    （服务账户/SSH/Credential Locker 未启动），每次调用都会抛 NoKeyringError，
    必须一次性切换到 fallback 模式，避免重复抛错污染日志。
    """
    # 重置运行时降级标志
    monkeypatch.setattr(secrets, "_RUNTIME_BROKEN", False)
    monkeypatch.setattr(secrets, "KEYRING_AVAILABLE", True)
    monkeypatch.setattr(secrets, "_FALLBACK_FILE", tmp_path / "secrets.json")

    # mock keyring.get_password 抛 NoKeyringError
    from keyring.errors import NoKeyringError

    mock_keyring = MagicMock()
    mock_keyring.get_password.side_effect = NoKeyringError("no backend")
    monkeypatch.setattr(secrets, "keyring", mock_keyring)

    # 首次调用：应触发降级
    assert secrets._RUNTIME_BROKEN is False
    result = secrets.get_secret("openai_api_key")
    assert result is None  # fallback 文件不存在，返回 None
    assert secrets._RUNTIME_BROKEN is True
    assert secrets.is_available() is False

    # 第二次调用：keyring 不应被再次调用（直接走 fallback）
    mock_keyring.get_password.reset_mock()
    secrets.get_secret("embedding_api_key")
    mock_keyring.get_password.assert_not_called()


def test_runtime_broken_skips_keyring_on_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """_RUNTIME_BROKEN=True 时 set_secret 应直接走 fallback"""
    monkeypatch.setattr(secrets, "_RUNTIME_BROKEN", True)
    monkeypatch.setattr(secrets, "KEYRING_AVAILABLE", True)
    monkeypatch.setattr(secrets, "_FALLBACK_FILE", tmp_path / "secrets.json")

    mock_keyring = MagicMock()
    monkeypatch.setattr(secrets, "keyring", mock_keyring)

    secrets.set_secret("test_key", "test_value")

    # keyring.set_password 不应被调用
    mock_keyring.set_password.assert_not_called()
    # fallback 文件应包含值
    assert secrets.get_secret("test_key") == "test_value"
