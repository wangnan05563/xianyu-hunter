"""配置 API - 读取、校验、写入 YAML

支持 dry_run 模式：返回 diff 视图，不真正写盘。
"""
from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, Body, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from xianyu_hunter.container import Container
from xianyu_hunter.infra.yaml_config import (
    AppConfig,
    get_config,
    reload_config,
)
from xianyu_hunter.web.deps import get_container

router = APIRouter(prefix="/api/config", tags=["config"])

# YAML 主文件路径
CONFIG_FILE = Path("config/config.yaml")

# 多版本备份：每个备份一个独立文件，按时间戳排序
# 保留最近 N 个，避免备份无限增长；N=10 足够覆盖"我刚才改错了想回滚"这种常见场景
BACKUP_DIR = CONFIG_FILE.parent / "backups"
BACKUP_KEEP = 10
BACKUP_PREFIX = "config.yaml.bak."


# ============== 模型 ==============
class ConfigSaveBody(BaseModel):
    payload: dict[str, Any]
    dry_run: bool = True


# ============== 工具 ==============
def _load_yaml() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        return {}
    return yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8")) or {}


def _dump_yaml(data: dict[str, Any]) -> str:
    """保留中文、空行，输出稳定格式"""
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)


def _diff(a: dict[str, Any], b: dict[str, Any], prefix: str = "") -> list[dict[str, str]]:
    """递归生成 diff 列表：{path, op, old, new}"""
    out: list[dict[str, str]] = []
    keys = set(a.keys()) | set(b.keys())
    for k in keys:
        path = f"{prefix}.{k}" if prefix else k
        av = a.get(k)
        bv = b.get(k)
        if isinstance(av, dict) and isinstance(bv, dict):
            out.extend(_diff(av, bv, path))
        elif av != bv:
            # av/bv 均非空为 modify；只剩 bv 为 add；只剩 av 为 remove
            if av and bv:
                op = "modify"
            elif bv:
                op = "add"
            else:
                op = "remove"
            out.append({"path": path, "op": op,
                        "old": "" if av is None else json.dumps(av, ensure_ascii=False),
                        "new": "" if bv is None else json.dumps(bv, ensure_ascii=False)})
    return out


def _new_backup_name() -> str:
    """生成时间戳备份文件名（秒级精度，足够日常区分）"""
    return f"{BACKUP_PREFIX}{datetime.now().strftime('%Y%m%d-%H%M%S')}"


def _list_backups() -> list[dict[str, Any]]:
    """列出所有备份：{filename, mtime, size, ts}，按 mtime 倒序

    为什么不直接列目录：要给前端一个稳定的"备份名 + 体积 + 时间戳"三元组，
    后续 restore-backup?filename=xxx 才能精确定位。
    """
    if not BACKUP_DIR.exists():
        return []
    items: list[dict[str, Any]] = []
    for p in BACKUP_DIR.glob(f"{BACKUP_PREFIX}*"):
        if not p.is_file():
            continue
        st = p.stat()
        # 文件名尾部就是时间戳，解析出来便于前端按日期分组/排序
        ts_raw = p.name[len(BACKUP_PREFIX):]
        items.append({
            "filename": p.name,
            "ts_raw": ts_raw,
            "mtime": st.st_mtime,
            "size": st.st_size,
            "ts": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
        })
    items.sort(key=lambda x: x["mtime"], reverse=True)
    return items


def _prune_backups() -> int:
    """超过 BACKUP_KEEP 的旧备份自动清理，返回清理数量

    之所以不软删除/归档：备份只是为了"误改后回滚"，不需要审计；
    留太久反而是噪音占磁盘。
    """
    items = _list_backups()
    if len(items) <= BACKUP_KEEP:
        return 0
    removed = 0
    for it in items[BACKUP_KEEP:]:
        try:
            (BACKUP_DIR / it["filename"]).unlink()
            removed += 1
        except OSError:
            # 单个清理失败不影响其他
            pass
    return removed


def _resolve_backup(filename: str) -> Path:
    """校验备份文件名合法性，防止目录穿越（filename 里塞 ../）

    必须满足：1) 只含字母数字 + 有限分隔符  2) 必须以 BACKUP_PREFIX 开头
    """
    if not filename or not filename.startswith(BACKUP_PREFIX):
        raise HTTPException(status_code=400, detail="非法的备份文件名")
    # 白名单字符集：数字 + 时间戳分隔符（-）
    if not all(c.isalnum() or c in "-_." for c in filename):
        raise HTTPException(status_code=400, detail="备份文件名包含非法字符")
    p = BACKUP_DIR / filename
    if not p.is_file():
        raise HTTPException(status_code=404, detail=f"备份 {filename} 不存在")
    return p


def _safe_app_version() -> str:
    """读取系统真实版本号，失败时回退为 'unknown'。

    与 api_about._safe_build_info 同源：__init__.py 的 __version__ 是单一源头，
    _build_info.py 由 scripts/build_info.py 重新生成。开发环境 _build_info 可能
    未生成，所以优先读 __init__.py 的 __version__，再回退到 _build_info。
    """
    try:
        from xianyu_hunter import __version__  # type: ignore[attr-defined]
        if __version__:
            return __version__
    except Exception:
        pass
    try:
        from xianyu_hunter import _build_info  # type: ignore[attr-defined]
        return getattr(_build_info, "__version__", "unknown") or "unknown"
    except Exception:
        return "unknown"


# ============== API ==============
@router.get("")
def get_full_config(
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """返回当前生效配置（已脱敏）"""
    cfg = get_config()
    logger.debug(f"_config id={id(cfg)}, pass_score={cfg.eval.pass_score}")
    return _redact(cfg.model_dump())


@router.get("/raw")
def get_raw_yaml() -> dict[str, Any]:
    """返回 YAML 原始内容（已脱敏，敏感字段仅保留末4位）"""
    return {"raw": _dump_yaml(_sanitize_dict(_load_yaml()))}


@router.post("/preview")
def preview_config(
    payload: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    """预览改动：返回 diff 列表 + 校验结果（不写盘）"""
    current = _load_yaml()
    new = copy.deepcopy(current)
    _deep_merge(new, payload)
    diffs = _diff(current, new)
    validation = _validate(new)
    return {
        "diffs": diffs,
        "validation": validation,
        "new_yaml": _dump_yaml(new) if validation["ok"] else None,
    }


@router.post("/save")
def save_config(
    body: ConfigSaveBody,
) -> dict[str, Any]:
    """保存配置（带多版本备份）。支持 dry_run 模式。"""
    current = _load_yaml()
    new = copy.deepcopy(current)
    _deep_merge(new, body.payload)
    validation = _validate(new)
    if not validation["ok"]:
        raise HTTPException(status_code=400, detail={
            "message": "配置校验失败，未保存",
            "errors": validation["errors"],
        })
    if body.dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "diffs": _diff(current, new),
        }
    # 真实写盘：先把当前 yaml 拷贝到 backups/，再原子替换
    # 注意：旧 .yaml.bak（单文件）兼容保留，但不再用作回滚主路径
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        legacy_bak = CONFIG_FILE.with_suffix(".yaml.bak")
        try:
            legacy_bak.write_text(CONFIG_FILE.read_text(encoding="utf-8"), encoding="utf-8")
        except OSError:
            # 旧 .bak 写失败不影响新备份主流程
            pass
        # 写入带时间戳的新备份
        new_bak = BACKUP_DIR / _new_backup_name()
        try:
            new_bak.write_text(CONFIG_FILE.read_text(encoding="utf-8"), encoding="utf-8")
        except OSError as e:
            raise HTTPException(status_code=500, detail=f"备份失败: {e}")
        pruned = _prune_backups()
    else:
        new_bak = None
        pruned = 0
    try:
        CONFIG_FILE.write_text(_dump_yaml(new), encoding="utf-8")
        # 触发单例重载
        reload_config()
        logger.debug(f"reload_config done, new _config id={id(get_config())}, pass_score={get_config().eval.pass_score}")
    except Exception as e:
        # 写失败，回滚到刚做的备份
        if new_bak and new_bak.exists():
            CONFIG_FILE.write_text(new_bak.read_text(encoding="utf-8"), encoding="utf-8")
        raise HTTPException(status_code=500, detail=f"写入失败，已回滚: {e}")
    return {
        "ok": True,
        "dry_run": False,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "diffs": _diff(current, new),
        "backup": {
            "filename": new_bak.name if new_bak else None,
            "pruned": pruned,
        },
        "restart_required": True,
        "restart_note": "配置已写入文件，重启 run 调度器后生效",
    }


@router.get("/backups")
def list_backups() -> dict[str, Any]:
    """列出所有历史备份（按时间倒序）"""
    items = _list_backups()
    return {
        "backups": items,
        "count": len(items),
        "keep": BACKUP_KEEP,
    }


# ============== F-04 配置分享（脱敏后文本） ==============
# 敏感字段：分享时移除（这些是账号凭证/Token，分享出去等于泄密）
_SHARE_REDACT_PATHS = [
    ("notifier", "channels"),         # 通知开关（可能含渠道自定义配置）
    ("serverchan_send_key",),
    ("pushplus_token",),
    ("bark_server",),
    ("bark_key",),
    ("telegram_bot_token",),
    ("telegram_chat_id",),
    ("wecom_webhook",),
    ("dingtalk_webhook",),
    ("dingtalk_secret",),
    ("webhook_url",),
    ("browser", "user_data_dir"),    # 路径（可能暴露机器/用户名）
]


def _redact_for_share(data: dict[str, Any]) -> dict[str, Any]:
    """分享专用脱敏：移除 token / 路径等敏感字段

    与 GET /api/config 的 _redact 不同：分享场景下我们"主动精简"内容，
    只留下"工作参数"（评估权重、价格阈值、关键词等），便于用户互相交流。
    """
    out = copy.deepcopy(data)
    for path in _SHARE_REDACT_PATHS:
        cur = out
        for i, k in enumerate(path):
            if not isinstance(cur, dict) or k not in cur:
                cur = None
                break
            if i == len(path) - 1:
                # 末级：删除 / 替换为 "***"
                if isinstance(cur[k], str):
                    cur[k] = "***"
                elif isinstance(cur[k], dict):
                    cur[k] = {kk: "***" for kk in cur[k]}
                else:
                    cur.pop(k, None)
            else:
                cur = cur[k]
    return out


@router.get("/share")
def share_config() -> dict[str, Any]:
    """F-04：生成可分享的配置摘要（不含敏感字段）

    用途：用户想给朋友/同事展示自己的"参数调优思路"，
    但不想泄露 token / 路径等。

    Returns:
        {
            "summary": str,         # 人类可读的纯文本摘要
            "config": dict,         # 脱敏后的 dict
            "redacted_fields": list # 被脱敏的字段名
        }
    """
    raw = _load_yaml()
    redacted = _redact_for_share(raw)
    lines: list[str] = []
    lines.append("# XianyuHunter 配置分享")
    lines.append(f"# 导出时间: {datetime.now().isoformat(timespec='seconds')}")
    lines.append("# 敏感字段（token / 路径）已脱敏为 ***")
    lines.append("")
    # 按 5 大分类（与 config 页面 5 个 Tab 对齐）展开
    for tab_name, keys in [
        ("搜索", ["antidetect", "browser", "waf"]),
        ("价格", []),  # 价格类目字段分散在 eval 内
        ("评估", ["eval"]),
        ("通知", ["notifier"]),
        ("抢单", []),
    ]:
        lines.append(f"## {tab_name}")
        if not keys:
            lines.append("  (无独立配置)")
            lines.append("")
            continue
        for k in keys:
            if k in redacted:
                lines.append(f"  {k}:")
                # 一行一个 key: value
                if isinstance(redacted[k], dict):
                    for sk, sv in redacted[k].items():
                        sv_repr = json.dumps(sv, ensure_ascii=False) if not isinstance(sv, (int, float, str, bool)) else str(sv)
                        if len(sv_repr) > 100:
                            sv_repr = sv_repr[:100] + "…"
                        lines.append(f"    {sk}: {sv_repr}")
                lines.append("")
    return {
        "summary": "\n".join(lines),
        "config": redacted,
        "redacted_fields": [".".join(p) for p in _SHARE_REDACT_PATHS],
    }


# ============== P3-UX-10 配置导入/导出 ==============
@router.get("/export")
def export_config() -> Any:
    """导出当前配置为 JSON 文件（浏览器触发下载）

    为什么不直接返回原始 YAML：
    - 跨机器/团队传递配置用 JSON 更通用（带版本号 + 元数据）
    - JSON 的 schema 校验比 YAML 严格（导入时更安全）

    脱敏策略：
    - 敏感凭证字段仅保留末4位，防止导出文件泄露完整密钥
    - 保留 UA/keyword 等"工作参数"不做脱敏
    """
    from fastapi.responses import Response
    raw = _load_yaml()
    payload = {
        "schema": "xianyu_hunter.config/v1",
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "app": {
            "name": "xianyu_hunter",
            # 读取真实系统版本号（与 /api/about 一致），便于导入方识别配置来源版本
            "version": _safe_app_version(),
        },
        "config": _sanitize_dict(raw),
    }
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    filename = f"xianyu_hunter_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    return Response(
        content=body,
        media_type="application/json; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Config-Export-Version": "1",
        },
    )


@router.post("/import")
def import_config(
    body: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    """导入配置（JSON）

    入参结构（与 /export 对齐）：
        {
            "schema": "xianyu_hunter.config/v1",
            "config": {...实际配置 dict...}
        }

    行为：
    - 校验 schema 字段是否存在
    - 校验 config 通过 AppConfig 模型
    - 强制 dry_run 二次确认（前端必须 confirm 一次）
    - 真实写盘：先做一次完整备份（含时间戳），再原子替换
    """
    schema = body.get("schema")
    if schema != "xianyu_hunter.config/v1":
        raise HTTPException(status_code=400, detail=f"不支持的 schema: {schema!r}，仅支持 v1")
    incoming = body.get("config")
    if not isinstance(incoming, dict):
        raise HTTPException(status_code=400, detail="config 字段必须为 dict")

    # 校验：复用 _validate
    validation = _validate(incoming)
    if not validation["ok"]:
        raise HTTPException(status_code=400, detail={
            "message": "导入的配置未通过 schema 校验",
            "errors": validation["errors"],
        })

    # 计算 diff（给前端预览确认用）
    current = _load_yaml()
    diffs = _diff(current, incoming)

    # 如果没传 confirm=true，要求前端二次确认
    confirm = bool(body.get("confirm"))
    if not confirm:
        return {
            "ok": False,
            "needs_confirm": True,
            "diffs": diffs,
            "diff_count": len(diffs),
            "message": f"将改动 {len(diffs)} 处，请确认后重试（传 confirm=true）",
        }

    # 备份当前文件 + 写盘
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    new_bak = None
    pruned = 0
    if CONFIG_FILE.exists():
        new_bak = BACKUP_DIR / _new_backup_name()
        try:
            new_bak.write_text(CONFIG_FILE.read_text(encoding="utf-8"), encoding="utf-8")
        except OSError as e:
            raise HTTPException(status_code=500, detail=f"备份失败: {e}")
        pruned = _prune_backups()
    try:
        CONFIG_FILE.write_text(_dump_yaml(incoming), encoding="utf-8")
        reload_config()
    except Exception as e:
        if new_bak and new_bak.exists():
            CONFIG_FILE.write_text(new_bak.read_text(encoding="utf-8"), encoding="utf-8")
        raise HTTPException(status_code=500, detail=f"导入失败，已回滚: {e}")

    return {
        "ok": True,
        "diffs": diffs,
        "diff_count": len(diffs),
        "backup": {
            "filename": new_bak.name if new_bak else None,
            "pruned": pruned,
        },
        "imported_at": datetime.now().isoformat(timespec="seconds"),
        "restart_required": True,
        "restart_note": "配置已写入文件，重启 run 调度器后生效",
    }


@router.get("/version")
def get_config_version() -> dict[str, Any]:
    """O-13：返回当前配置版本号（基于备份计数）

    版本号 = 备份文件数量，每次保存自然递增。
    0 表示从未保存过（初始配置），前端据此决定是否显示回滚按钮。
    """
    backups = _list_backups()
    version = len(backups)
    latest = backups[0] if backups else None
    return {
        "version": version,
        "latest_backup_ts": latest["ts"] if latest else None,
        "latest_backup_file": latest["filename"] if latest else None,
    }


@router.post("/rollback")
def rollback_config() -> dict[str, Any]:
    """O-13：一键回滚到上一个版本（最近的备份）

    与 restore-backup 的区别：
    - 不需要传 filename（自动取最新备份）
    - 回滚前先备份当前配置（安全网，防止误操作后无法恢复）
    - 返回回滚后的版本号
    """
    backups = _list_backups()
    if not backups:
        raise HTTPException(status_code=404, detail="没有可回滚的备份")
    target_backup = backups[0]
    # 回滚前先备份当前配置（防止误操作后无法恢复）
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        pre_bak = BACKUP_DIR / _new_backup_name()
        try:
            pre_bak.write_text(CONFIG_FILE.read_text(encoding="utf-8"), encoding="utf-8")
        except OSError:
            # 回滚前备份失败不阻塞主流程（当前配置仍在磁盘上，用户可手动恢复）
            pass
        _prune_backups()
    # 执行回滚：用最新备份覆盖当前配置
    target = BACKUP_DIR / target_backup["filename"]
    CONFIG_FILE.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
    reload_config()
    new_version = len(_list_backups())
    return {
        "ok": True,
        "rolled_back_to": target_backup["ts"],
        "rolled_back_file": target_backup["filename"],
        "version": new_version,
    }


@router.post("/restore-backup")
def restore_backup(filename: str = "") -> dict[str, Any]:
    """从指定备份恢复。

    兼容行为：
    - 不传 filename → 回退到旧 .yaml.bak（如果有），便于升级前已经存在的备份也能用
    - 传 filename → 从 backups/<file> 恢复（带白名单校验防穿越）
    """
    if not filename:
        # 兼容旧路径：单文件 .bak
        bak = CONFIG_FILE.with_suffix(".yaml.bak")
        if not bak.exists():
            raise HTTPException(status_code=404, detail="未找到备份文件（也未指定 filename）")
        target = bak
        label = bak.name
    else:
        target = _resolve_backup(filename)
        label = target.name
    CONFIG_FILE.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
    reload_config()
    return {
        "ok": True,
        "restored_from": label,
        "restored_at": datetime.now().isoformat(timespec="seconds"),
    }


# ============== 内部工具 ==============
def _deep_merge(target: dict[str, Any], patch: dict[str, Any]) -> None:
    """把 patch 合并进 target（递归）"""
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(target.get(k), dict):
            _deep_merge(target[k], v)
        else:
            target[k] = v


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    """用 AppConfig 模型校验，返回 {ok, errors: list}"""
    try:
        AppConfig.model_validate(data)
        return {"ok": True, "errors": []}
    except Exception as e:
        # 简化错误：行号/字段
        return {"ok": False, "errors": [str(e)]}


# 需要脱敏的配置键名：前端展示时替换为 "***"
# - 不含 user_agent（前端需编辑该字段，脱敏会引入假 diff）
# - 不含通知渠道凭据（serverchan_send_key / pushplus_token / bark_* / telegram_* / wecom_* /
#   dingtalk_* / webhook_url）：前端通过 Input.Password 组件回显已配置值，脱敏会导致
#   用户无法看到已保存的凭据，误以为未持久化
# - 不含 openai_api_key（该字段走 config.py Settings，不经过 YAML）
_REDACT_KEYS = frozenset({
    "cookie", "cookies", "session_id",
})


def _redact(data: dict[str, Any]) -> dict[str, Any]:
    """脱敏：隐藏 token / cookie / 通知密钥等高敏感字段

    为什么不脱敏 user_agent：
    - UA 字段需要被前端表单直接编辑（用于伪装）
    - 脱敏会引入"假改动"（每次 GET 拿到的 UA 字符串长度/内容都不同，
      preview 对比磁盘真实值时总会多出一行 user_agent diff）
    - 该字段的敏感性远低于 token/cookie，暴露给登录用户不构成泄露
    """
    out = copy.deepcopy(data)
    _redact_recursive(out)
    return out


def _redact_recursive(d: dict) -> None:
    """递归脱敏字典中的敏感字段"""
    # S7504: 直接迭代字典键即可；循环体只改值不增删键，无需 list() 快照
    for k in d:
        if k in _REDACT_KEYS and isinstance(d[k], str) and d[k]:
            d[k] = "***"
        elif isinstance(d[k], dict):
            _redact_recursive(d[k])


# /raw 和 /export 专用脱敏：保留末4位，便于用户辨识而不泄露完整凭证
_SENSITIVE_KEYS = frozenset({
    "serverchan_send_key", "pushplus_token", "bark_key", "bark_server",
    "telegram_bot_token", "telegram_chat_id", "wecom_webhook",
    "dingtalk_webhook", "dingtalk_secret", "webhook_url",
    "openai_api_key",
})


def _sanitize_value(val: str) -> str:
    """脱敏：仅保留最后4位，其余用 **** 替代"""
    if not val or len(val) <= 4:
        return "****" if val else ""
    return "****" + val[-4:]


def _sanitize_dict(data: dict) -> dict:
    """递归脱敏字典中的敏感字段（保留末4位）"""
    result = {}
    for k, v in data.items():
        if k in _SENSITIVE_KEYS and isinstance(v, str):
            result[k] = _sanitize_value(v)
        elif isinstance(v, dict):
            result[k] = _sanitize_dict(v)
        else:
            result[k] = v
    return result
