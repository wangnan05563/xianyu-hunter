"""脱敏清单覆盖审计（T02589 / PRD FR-A-6 + FR-D-1）

FR-A-6：`ntfy_server`/`ntfy_topic`/`ntfy_token` 原本不在 `_SENSITIVE_KEYS`，
`/api/config/raw` 与 `/api/config/export` 会把它们明文输出。
FR-D-1：这类「新增凭据键忘记进清单」的缺陷靠人记必然复发，
故用本测试把「配置模型里的凭据字段 ⊆ 脱敏清单」变成 CI 门禁。
同一轮审计还发现整份导出面漏了一个接口——`/api/config/preview` 的 `new_yaml`，
本文件末尾用「行为 + 源码」两道门禁锁住它。

口径说明：只比对**字符串类型**字段——`notifier.channels.webhook: bool`、
`require_config_key: bool` 这类开关命中名字但不是凭据，纳入会产生假阳性。
"""
from __future__ import annotations

import re
from typing import get_args

from pydantic import BaseModel

from xianyu_hunter.infra import secrets
from xianyu_hunter.infra.yaml_config import AppConfig
from xianyu_hunter.web.routes.api_config import _SENSITIVE_KEYS, _sanitize_dict

# 名字以这些后缀结尾的字符串字段视为凭据（与清单里既有的 11 键命名一致）
_CREDENTIAL_SUFFIX = re.compile(r"(token|key|secret|webhook|password)$", re.IGNORECASE)

# FR-A-6 点名的三个 ntfy 键：ntfy_server 是地址、ntfy_topic 是订阅主题，
# 名字不含 token/key 后缀，靠后缀规则抓不到，必须显式钉住
FR_A6_NTFY_KEYS = {"ntfy_server", "ntfy_topic", "ntfy_token"}


def _string_credential_fields(model: type[BaseModel], found: set[str]) -> None:
    """递归收集配置模型树中「字符串 + 名字像凭据」的字段名"""
    for name, field in model.model_fields.items():
        annotation = field.annotation
        if annotation is str and _CREDENTIAL_SUFFIX.search(name):
            found.add(name)
        for arg in (annotation, *get_args(annotation)):
            if isinstance(arg, type) and issubclass(arg, BaseModel):
                _string_credential_fields(arg, found)


def test_ntfy_keys_are_covered():
    """FR-A-6 验收：ntfy 三键进入清单"""
    assert FR_A6_NTFY_KEYS <= set(_SENSITIVE_KEYS)


def test_every_string_credential_field_is_covered():
    """FR-D-1 门禁：配置模型里任何字符串凭据字段都必须在脱敏清单中"""
    found: set[str] = set()
    _string_credential_fields(AppConfig, found)
    assert found, "扫描逻辑失效：AppConfig 里至少应有 serverchan_send_key 等凭据字段"
    missing = sorted(found - set(_SENSITIVE_KEYS))
    assert not missing, (
        f"以下凭据字段未进 _SENSITIVE_KEYS，/raw 与 /export 会明文泄露：{missing}"
    )


def test_every_secrets_module_key_is_covered():
    """keyring 侧登记的凭据键名（secrets.KEY_*）同样必须被清单覆盖"""
    declared = {
        v for k, v in vars(secrets).items()
        if k.startswith("KEY_") and isinstance(v, str) and _CREDENTIAL_SUFFIX.search(v)
    }
    assert declared
    missing = sorted(declared - set(_SENSITIVE_KEYS))
    assert not missing, f"secrets.py 里的凭据键未进脱敏清单：{missing}"


def test_sanitizer_masks_ntfy_values():
    """行为验证：脱敏后只保留末 4 位，不再是明文"""
    raw = {
        "ntfy_server": "https://ntfy.sh/my-private-topic",
        "ntfy_topic": "abcdef123456",
        "ntfy_token": "tk_0123456789abcd",
        "non_secret": "keep-me",
    }
    out = _sanitize_dict(raw)
    assert out["non_secret"] == "keep-me"
    for key in FR_A6_NTFY_KEYS:
        assert out[key] != raw[key], f"{key} 未被脱敏"
        assert out[key].startswith("****")
        assert out[key][-4:] == raw[key][-4:]
        assert raw[key][:-4] not in out[key]


def test_sanitizer_masks_cpolar_authtoken():
    """覆盖审计跑出的同类泄露：cpolar 账号令牌原本也不在清单"""
    out = _sanitize_dict({"tunnel": {"cpolar_authtoken": "cp_0123456789abcd"}})
    assert out["tunnel"]["cpolar_authtoken"] == "****abcd"


# ---------------------------------------------------------------- 整份导出面
# /raw、/export、/preview(new_yaml) 三个接口都会把「整份配置」交给调用方，
# 泄露性质相同；T02589 排查时发现 /preview 只脱敏了 /raw 与 /export，
# 空 payload 也能通过 new_yaml 拿到磁盘上的全部凭据。

_ON_DISK_SENTINEL = {"serverchan_send_key": "SCT_sc_0123456789wxyz"}


def test_preview_new_yaml_does_not_leak_whole_config(monkeypatch):
    """空 payload 预览也不得回吐磁盘凭据明文"""
    from xianyu_hunter.web.routes import api_config

    monkeypatch.setattr(api_config, "_load_yaml", lambda: dict(_ON_DISK_SENTINEL))
    # 校验逻辑与本次断言无关（真实 yaml 才能过 _validate），直接放行
    monkeypatch.setattr(api_config, "_validate", lambda _d: {"ok": True, "errors": []})

    out = api_config.preview_config({})
    assert out["new_yaml"] is not None
    assert "SCT_sc_0123456789wxyz" not in out["new_yaml"]
    assert "****wxyz" in out["new_yaml"]
    # diffs 仍保留逐字段真实旧值——预览弹窗要让用户看见自己正在覆盖什么
    assert out["diffs"] == []


def test_no_unsanitized_whole_config_dump():
    """源码门禁：任何「把整份配置 dump 给调用方」的返回值都必须过 _sanitize_dict

    写盘（CONFIG_FILE.write_text）与被测函数定义本身除外——它们不是对外响应。
    """
    import inspect

    src = inspect.getsource(api_config_source_module())
    offenders = []
    for no, line in enumerate(src.splitlines(), start=1):
        stripped = line.strip()
        if "_dump_yaml(" not in stripped or stripped.startswith("def _dump_yaml"):
            continue
        if "write_text" in stripped:  # 落盘路径，必须写明文
            continue
        if "_sanitize_dict" not in stripped:
            offenders.append(f"{no}: {stripped}")
    assert not offenders, "以下响应把未脱敏的整份配置返回给调用方：\n" + "\n".join(offenders)


def api_config_source_module():
    """单独抽出，避免测试函数里混入 import 语句"""
    from xianyu_hunter.web.routes import api_config as module

    return module

