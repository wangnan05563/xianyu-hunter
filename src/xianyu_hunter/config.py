"""配置加载（pydantic-settings）

支持热更新：修改 AI 配置后无需重启服务，
通过 update_ai_config() 即时生效。
"""
from __future__ import annotations

import secrets as _secrets
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置，从 .env 读取"""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 日志
    log_level: str = "INFO"

    # 推送服务
    serverchan_key: str = ""
    pushplus_token: str = ""
    bark_server: str = "https://api.day.app"
    bark_key: str = ""
    # P1-3：新增通知渠道配置（也可通过 keyring 存储）
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    wecom_webhook_url: str = ""
    dingtalk_webhook_url: str = ""
    dingtalk_secret: str = ""
    webhook_url: str = ""
    webhook_token: str = ""

    # AI 服务配置
    ai_enabled: bool = True  # AI 全局开关：关闭后所有 AI 功能降级到规则模式
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    # 模型名称可配置：支持 DeepSeek(deepseek-chat) / 智谱(glm-4-flash) 等
    openai_model: str = "gpt-4o-mini"
    openai_vision_model: str = "gpt-4o"

    # Embedding 服务独立配置（与 LLM 解耦）：
    # - 留空时 fallback 到 OPENAI_* 配置（向后兼容）
    # - 配置后 KB/FAQ 向量化走独立 endpoint，避免 DeepSeek 等不支持 /embeddings 的服务商
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_model: str = ""
    # 0 表示未配置，由 cfg.kb.embedding_dimensions 兜底
    embedding_dimensions: int = 0

    # Web 认证：留空则首次启动自动生成并写入 .env
    # 本地个人工具场景下，token 防止同网络其他设备随意访问
    web_token: str = ""

    # 闲鱼站点基础 URL：支持通过环境变量切换镜像/测试环境，
    # 避免在多个模块中硬编码导致切换困难
    xianyu_base_url: str = "https://www.goofish.com"

    # 路径
    project_root: Path = Path(__file__).resolve().parent.parent.parent.parent


@lru_cache
def get_settings() -> Settings:
    """单例获取配置"""
    s = Settings()
    # 首次启动自动生成 token 并持久化到 .env
    if not s.web_token:
        s.web_token = _generate_and_persist_token()
    # 优先从 keyring 读取敏感字段（迁移后 .env 中为占位符）
    _load_secrets_from_keyring(s)
    return s


def _load_secrets_from_keyring(s: Settings) -> None:
    """从 keyring 加载敏感字段，覆盖 .env 中的值

    迁移到 keyring 后，.env 中对应字段为占位符 __MIGRATED_TO_KEYRING__，
    需要从 keyring 读取真实值。keyring 中无值时保持 .env 原值（向后兼容）。
    """
    from xianyu_hunter.infra import secrets as _secret_store
    api_key = _secret_store.get_secret(_secret_store.KEY_OPENAI_API_KEY)
    if api_key:
        s.openai_api_key = api_key
    # Embedding API Key 独立存储：DeepSeek 等不支持 /embeddings 时需切换到
    # Ollama/Jina 等服务，凭证不应与 LLM 混用
    emb_key = _secret_store.get_secret(_secret_store.KEY_EMBEDDING_API_KEY)
    if emb_key:
        s.embedding_api_key = emb_key


def update_ai_config(
    ai_enabled: bool | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    vision_model: str | None = None,
    embedding_base_url: str | None = None,
    embedding_api_key: str | None = None,
    embedding_model: str | None = None,
    embedding_dimensions: int | None = None,
) -> None:
    """热更新 AI 配置（无需重启服务）

    同时更新内存中的 Settings 单例和 .env 文件，
    确保下次启动也能读到最新值。

    注意：embedding_* 参数为 None 表示不修改；空字符串表示清除该字段。
    """
    s = get_settings()
    env_updates: dict[str, str] = {}

    if ai_enabled is not None:
        s.ai_enabled = ai_enabled
        env_updates["AI_ENABLED"] = str(ai_enabled)
    if base_url is not None:
        s.openai_base_url = base_url
        env_updates["OPENAI_BASE_URL"] = base_url
    if api_key is not None:
        s.openai_api_key = api_key
        # 敏感字段写入 keyring 而非 .env 明文
        from xianyu_hunter.infra import secrets as _secret_store
        _secret_store.set_secret(_secret_store.KEY_OPENAI_API_KEY, api_key)
    if model is not None:
        s.openai_model = model
        env_updates["OPENAI_MODEL"] = model
    if vision_model is not None:
        s.openai_vision_model = vision_model
        env_updates["OPENAI_VISION_MODEL"] = vision_model

    # Embedding 配置独立处理：留空时 fallback 到 OPENAI_*（向后兼容）
    if embedding_base_url is not None:
        s.embedding_base_url = embedding_base_url
        env_updates["EMBEDDING_BASE_URL"] = embedding_base_url
    if embedding_api_key is not None:
        s.embedding_api_key = embedding_api_key
        from xianyu_hunter.infra import secrets as _secret_store
        _secret_store.set_secret(_secret_store.KEY_EMBEDDING_API_KEY, embedding_api_key)
    if embedding_model is not None:
        s.embedding_model = embedding_model
        env_updates["EMBEDDING_MODEL"] = embedding_model
    if embedding_dimensions is not None:
        s.embedding_dimensions = embedding_dimensions
        env_updates["EMBEDDING_DIMENSIONS"] = str(embedding_dimensions)

    if env_updates:
        _persist_to_env(env_updates)


def _persist_to_env(updates: dict[str, str]) -> None:
    """将配置变更持久化到 .env 文件（upsert 语义）"""
    env_path = Path(".env")
    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    updated_keys: set[str] = set()
    new_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}")
                updated_keys.add(key)
                continue
        new_lines.append(line)

    # 追加新增的键
    for key, value in updates.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={value}")

    try:
        env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    except OSError as e:
        from xianyu_hunter.infra.logger import get_logger
        get_logger().warning("写入 .env 失败: %s", e)


def _generate_and_persist_token() -> str:
    """生成随机 token 并追加到 .env 文件"""
    token = _secrets.token_urlsafe(32)
    env_path = Path(".env")
    try:
        line = f"\nWEB_TOKEN={token}\n"
        with env_path.open("a", encoding="utf-8") as f:
            f.write(line)
    except OSError as e:
        # token 写入失败时仅警告，不阻断启动（用户可手动写入 .env 或通过 /api/auth/verify 设置）
        import logging
        logging.getLogger(__name__).warning("WEB_TOKEN 写入 .env 失败: %s", e)
    return token
