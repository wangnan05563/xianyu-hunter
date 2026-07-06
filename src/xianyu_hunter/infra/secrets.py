"""密钥加密存储（Windows DPAPI / keyring）

设计文档 §5.3：账号 Cookie、推送 Key 等敏感信息本地加密存储。

安全层级：
1. keyring（首选）：Windows DPAPI / macOS Keychain / Linux Secret Service
2. fallback：base64 编码 + 文件权限限制（弱保护，仅防"肉眼误看"；
   不防"有意读取"，启动时会打印警告）
"""
from __future__ import annotations

import base64
import json
import os
import stat
from pathlib import Path

# keyring 在 Windows 上使用 Windows Credential Locker，
# 在底层调用 DPAPI 进行加密，绑定当前 Windows 用户账号。
# 跨用户/跨机器不可读，正好满足"个人辅助工具"的安全边界。
try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False

from xianyu_hunter.infra.logger import get_logger

logger = get_logger()

# 服务名（keyring 中的"应用名"分组）
SERVICE_NAME = "XianyuHunter"

# 已知的敏感键
KEY_SERVERCHAN = "serverchan_send_key"
KEY_PUSHPLUS = "pushplus_token"
KEY_BARK_SERVER = "bark_server"
KEY_BARK_KEY = "bark_key"
# P1-3：新增通知渠道密钥
# key 名与 yaml 字段名保持一致，便于 wire_notifier 同步
KEY_TELEGRAM_TOKEN = "telegram_bot_token"
KEY_TELEGRAM_CHAT = "telegram_chat_id"
KEY_WECOM_WEBHOOK = "wecom_webhook"
KEY_DINGTALK_WEBHOOK = "dingtalk_webhook"
KEY_DINGTALK_SECRET = "dingtalk_secret"
KEY_WEBHOOK_URL = "webhook_url"
KEY_WEBHOOK_TOKEN = "webhook_token"
# ntfy：免费跨平台推送（公共实例 https://ntfy.sh，可自托管）
KEY_NTFY_SERVER = "ntfy_server"
KEY_NTFY_TOPIC = "ntfy_topic"
KEY_NTFY_TOKEN = "ntfy_token"
# AI 服务密钥
KEY_OPENAI_API_KEY = "openai_api_key"
# Embedding 服务密钥（与 LLM 解耦：DeepSeek 等不支持 /embeddings 时需独立配置）
KEY_EMBEDDING_API_KEY = "embedding_api_key"
COOKIE_PREFIX = "cookie_"


def is_available() -> bool:
    """检查 keyring 在当前系统是否可用"""
    return KEYRING_AVAILABLE


def set_secret(key: str, value: str) -> None:
    """存储一个密钥到 keyring"""
    if not KEYRING_AVAILABLE:
        logger.warning("keyring 不可用，回退到 .env 文件")
        _fallback_set(key, value)
        return
    try:
        keyring.set_password(SERVICE_NAME, key, value)
        logger.debug(f"已加密存储 {key}")
    except Exception as e:
        logger.exception(f"keyring 存储失败 {key}: ，回退到 .env")
        _fallback_set(key, value)


def get_secret(key: str) -> str | None:
    """读取密钥"""
    if not KEYRING_AVAILABLE:
        return _fallback_get(key)
    try:
        return keyring.get_password(SERVICE_NAME, key)
    except Exception as e:
        logger.exception(f"keyring 读取失败 {key}")
        return _fallback_get(key)


def delete_secret(key: str) -> None:
    """删除一个密钥"""
    if KEYRING_AVAILABLE:
        try:
            keyring.delete_password(SERVICE_NAME, key)
            return
        except Exception:
            pass
    _fallback_delete(key)


def list_keys() -> list[str]:
    """列出所有已存密钥（仅名字）"""
    if KEYRING_AVAILABLE:
        try:
            # keyring 没有 list 接口，遍历预定义键
            keys = [
                KEY_SERVERCHAN, KEY_PUSHPLUS, KEY_BARK_SERVER, KEY_BARK_KEY,
                KEY_TELEGRAM_TOKEN, KEY_TELEGRAM_CHAT,
                KEY_WECOM_WEBHOOK, KEY_DINGTALK_WEBHOOK, KEY_DINGTALK_SECRET,
                KEY_WEBHOOK_URL, KEY_WEBHOOK_TOKEN,
                KEY_NTFY_SERVER, KEY_NTFY_TOPIC, KEY_NTFY_TOKEN,
                KEY_OPENAI_API_KEY, KEY_EMBEDDING_API_KEY,
            ]
            return [k for k in keys if get_secret(k) is not None]
        except Exception:
            return []
    return list(_fallback_all().keys())


# ============== .env 迁移助手 ==============

def migrate_from_env(env_path: str = ".env") -> int:
    """从 .env 文件读取敏感 Key 并迁移到 keyring，成功后从 .env 删除

    Returns: 迁移的 Key 数量
    """
    env_file = Path(env_path)
    if not env_file.exists():
        return 0
    count = 0
    mapping = {
        "SERVERCHAN_KEY": KEY_SERVERCHAN,
        "PUSHPLUS_TOKEN": KEY_PUSHPLUS,
        "BARK_KEY": KEY_BARK_KEY,
        "OPENAI_API_KEY": KEY_OPENAI_API_KEY,
        "EMBEDDING_API_KEY": KEY_EMBEDDING_API_KEY,
    }
    new_lines = []
    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            new_lines.append(line)
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key in mapping and value:
            set_secret(mapping[key], value)
            count += 1
            # 替换为占位符（保留结构）
            new_lines.append(f"{key}=__MIGRATED_TO_KEYRING__")
            logger.info(f"已迁移 {key} → keyring")
        else:
            new_lines.append(line)
    env_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return count


# ============== 回退实现（keyring 不可用时） ==============

_FALLBACK_FILE = Path("data/.secrets.json")
_FALLBACK_WARNED = False


def _warn_fallback() -> None:
    """首次使用 fallback 时打印一次性警告"""
    global _FALLBACK_WARNED
    if not _FALLBACK_WARNED:
        _FALLBACK_WARNED = True
        logger.warning(
            "⚠ keyring 不可用，密钥以 base64 编码存储在 "
            f"{_FALLBACK_FILE}（弱保护）。建议安装 keyring 后运行 "
            "migrate_from_env() 迁移到系统密钥库。"
        )


def _obfuscate(value: str) -> str:
    """base64 编码：不是加密，仅防止肉眼直接看到明文

    为什么不用 Fernet 等真加密：密钥本身需要另一个密钥来加密，
    对本地单用户工具来说，密钥管理复杂度远超安全收益。
    keyring 才是正确方案，fallback 只是兜底。
    """
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def _deobfuscate(value: str) -> str:
    """base64 解码"""
    return base64.b64decode(value.encode("ascii")).decode("utf-8")


def _set_file_permissions(path: Path) -> None:
    """限制文件权限为仅当前用户可读写（Unix: 600, Windows: best-effort）"""
    try:
        if os.name != "nt":
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def _fallback_set(key: str, value: str) -> None:
    _warn_fallback()
    _FALLBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = _fallback_all()
    data[key] = _obfuscate(value)
    _FALLBACK_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _set_file_permissions(_FALLBACK_FILE)


def _fallback_get(key: str) -> str | None:
    raw = _fallback_all().get(key)
    if raw is None:
        return None
    try:
        return _deobfuscate(raw)
    except Exception:
        # 兼容旧版明文存储的值
        return raw


def _fallback_delete(key: str) -> None:
    data = _fallback_all()
    if key in data:
        del data[key]
        _FALLBACK_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def _fallback_all() -> dict[str, str]:
    if not _FALLBACK_FILE.exists():
        return {}
    try:
        return json.loads(_FALLBACK_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
