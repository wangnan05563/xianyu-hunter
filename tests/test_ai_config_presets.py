"""AI 服务快捷预设配置回归测试。"""
from __future__ import annotations

from types import SimpleNamespace

from xianyu_hunter.infra import secrets as secret_store
from xianyu_hunter import config as config_module
from xianyu_hunter.web.routes import api_ai


def _preset_key(preset_id: str) -> str:
    return f"openai_api_key_preset_{preset_id}"


def test_switching_presets_restores_each_presets_api_key(monkeypatch) -> None:
    """切换快捷预设时保存当前 Key，并恢复目标预设自己的 Key。"""
    settings = SimpleNamespace(
        ai_enabled=True,
        openai_base_url="https://api.openai.com/v1",
        openai_api_key="sk-openai-current",
        openai_model="gpt-4o-mini",
        openai_vision_model="gpt-4o",
        embedding_base_url="",
        embedding_api_key="",
        embedding_model="",
        embedding_dimensions=0,
    )
    stored = {
        _preset_key("deepseek"): "sk-deepseek-saved",
    }

    monkeypatch.setattr(api_ai, "get_settings", lambda: settings)
    monkeypatch.setattr(secret_store, "get_secret", stored.get)
    monkeypatch.setattr(secret_store, "set_secret", stored.__setitem__)

    def fake_update_ai_config(**updates) -> None:
        field_map = {
            "base_url": "openai_base_url",
            "api_key": "openai_api_key",
            "model": "openai_model",
            "vision_model": "openai_vision_model",
        }
        for key, value in updates.items():
            if value is not None and key in field_map:
                setattr(settings, field_map[key], value)

    monkeypatch.setattr(api_ai, "update_ai_config", fake_update_ai_config)

    result = api_ai.save_ai_config(
        api_ai.AIConfigBody(
            preset_id="deepseek",
            base_url="https://api.deepseek.com/v1",
            model="deepseek-chat",
            vision_model="deepseek-chat",
        )
    )

    assert stored[_preset_key("openai")] == "sk-openai-current"
    assert settings.openai_api_key == "sk-deepseek-saved"
    assert result["api_key"] == "****aved"
    assert result["preset_id"] == "deepseek"


def test_saving_key_updates_only_selected_preset(monkeypatch) -> None:
    """编辑 API Key 时只覆盖当前快捷预设的密钥槽。"""
    settings = SimpleNamespace(
        ai_enabled=True,
        openai_base_url="https://api.deepseek.com/v1",
        openai_api_key="sk-deepseek-old",
        openai_model="deepseek-chat",
        openai_vision_model="deepseek-chat",
        embedding_base_url="",
        embedding_api_key="",
        embedding_model="",
        embedding_dimensions=0,
    )
    stored: dict[str, str] = {}
    monkeypatch.setattr(api_ai, "get_settings", lambda: settings)
    monkeypatch.setattr(secret_store, "get_secret", stored.get)
    monkeypatch.setattr(secret_store, "set_secret", stored.__setitem__)
    monkeypatch.setattr(api_ai, "update_ai_config", lambda **_: None)

    api_ai.save_ai_config(
        api_ai.AIConfigBody(preset_id="deepseek", api_key="sk-deepseek-new")
    )

    assert stored[_preset_key("deepseek")] == "sk-deepseek-new"
    assert _preset_key("openai") not in stored


def test_empty_active_key_in_keyring_overrides_legacy_env_value(monkeypatch) -> None:
    """切到未配置 Key 的预设后，重启不能让旧 .env Key 重新出现。"""
    settings = SimpleNamespace(
        openai_api_key="legacy-env-key",
        embedding_api_key="legacy-embedding-key",
    )
    monkeypatch.setattr(secret_store, "get_secret", lambda _: "")

    config_module._load_secrets_from_keyring(settings)

    assert settings.openai_api_key == ""
    assert settings.embedding_api_key == ""
