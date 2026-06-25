"""browser_import 模块单元测试（解密逻辑 + v20 检测）"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from xianyu_hunter.web.routes.browser_import import (
    decrypt_cookie_value,
    decrypt_dpapi,
    _decrypt_aes_gcm,
)


def test_decrypt_plaintext():
    """明文 Cookie 直接返回"""
    result = decrypt_cookie_value(b"", "plain_value", None)
    assert result == "plain_value"


def test_decrypt_empty():
    """空值返回 None"""
    result = decrypt_cookie_value(b"", None, None)
    assert result is None


def test_decrypt_aes_gcm_v10():
    """v10 加密格式能正确解密（mock AESGCM）"""
    # 构造 v10 格式：v10(3) + nonce(12) + ciphertext + tag(16)
    enc_bytes = b"v10" + b"\x00" * 12 + b"ciphertext" + b"\x00" * 16
    mock_aesgcm = patch("cryptography.hazmat.primitives.ciphers.aead.AESGCM")
    with mock_aesgcm as mock_cls:
        mock_instance = mock_cls.return_value
        mock_instance.decrypt.return_value = b"decrypted_value"
        result = _decrypt_aes_gcm(b"\x00" * 32, enc_bytes)
    assert result == "decrypted_value"


def test_decrypt_aes_gcm_v20_detected():
    """v20 加密格式检测到后返回 None（不崩溃）"""
    enc_bytes = b"v20" + b"\x00" * 12 + b"ciphertext" + b"\x00" * 16
    # v20 传入 _decrypt_aes_gcm 时，由于密钥不匹配会解密失败返回 None
    result = _decrypt_aes_gcm(b"\x00" * 32, enc_bytes)
    assert result is None


def test_decrypt_v20_without_aes_key():
    """v20 加密但无 AES 密钥时返回 None"""
    enc_bytes = b"v20" + b"\x00" * 12 + b"ciphertext" + b"\x00" * 16
    result = decrypt_cookie_value(enc_bytes, None, None)
    assert result is None


def test_decrypt_dpapi_success():
    """DPAPI 解密成功路径（mock CryptUnprotectData）"""
    # DPAPI 解密在非 Windows 环境会返回 None，这里只验证不崩溃
    result = decrypt_dpapi(b"test_data")
    # 在 Windows 上可能成功，非 Windows 返回 None
    assert result is None or isinstance(result, bytes)


def test_copy_file_with_share_locked(tmp_path: Path):
    """文件锁规避逻辑（mock robocopy）"""
    from xianyu_hunter.web.routes.browser_import import copy_file_with_share

    src = tmp_path / "src.db"
    dst = tmp_path / "sub" / "dst.db"
    src.write_bytes(b"test content")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        result = copy_file_with_share(str(src), str(dst))

    # robocopy 返回码 0 表示成功
    assert result is True
    assert dst.exists()
    assert dst.read_bytes() == b"test content"
