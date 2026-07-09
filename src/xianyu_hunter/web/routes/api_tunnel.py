# src/xianyu_hunter/web/routes/api_tunnel.py
"""内网穿透 Tunnel API 端点

提供一键开启/关闭远程访问的能力，返回公网 HTTPS 域名。
- status/start/stop 免认证（远程访问引导场景：未登录时需先建隧道才能访问登录页）
- config 端点需认证（防止未授权修改 provider/authtoken）
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from xianyu_hunter.infra.yaml_config import get_config, reload_config
from xianyu_hunter.paths import get_config_dir
from xianyu_hunter.web.services.tunnel_providers import BinaryDownloadError

router = APIRouter(prefix="/api/tunnel", tags=["tunnel"])

# 全局单例：整个应用共享一个隧道实例
_tunnel_service = None


def get_tunnel_service():
    """获取或创建全局 TunnelService 单例"""
    global _tunnel_service
    if _tunnel_service is None:
        from xianyu_hunter.web.services.tunnel_service import TunnelService
        # 端口由 TunnelService._resolve_port() 从配置链解析，此处不再硬编码
        _tunnel_service = TunnelService()
    return _tunnel_service


# ---------- 配置模型 ----------

class TunnelConfigBody(BaseModel):
    """隧道配置保存请求体"""
    provider: str = "cloudflare"
    local_port: int = 0
    cpolar_authtoken: str = ""
    binary_path: str = ""
    auto_start: bool = False


def _config_yaml_path() -> Path:
    """config.yaml 路径（与 api_config.py 一致）"""
    return get_config_dir() / "config.yaml"


def _load_yaml_raw() -> dict[str, Any]:
    p = _config_yaml_path()
    if not p.exists():
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def _dump_yaml_raw(data: dict[str, Any]) -> str:
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)


# ---------- 状态控制端点（免认证） ----------

@router.get("/status")
def tunnel_status() -> JSONResponse:
    """查询隧道状态"""
    svc = get_tunnel_service()
    return JSONResponse({
        "status": svc.status,
        "public_url": svc.public_url,
        "provider": svc.provider_name or get_config().tunnel.provider,
    })


@router.post("/start")
def tunnel_start() -> JSONResponse:
    """启动隧道，返回公网 URL"""
    svc = get_tunnel_service()
    try:
        url = svc.start()
        return JSONResponse({
            "status": svc.status,
            "public_url": url,
            "provider": svc.provider_name,
        })
    except BinaryDownloadError as e:
        # 下载失败：返回手动放置指引，前端渲染下载链接和路径
        return JSONResponse(
            status_code=500,
            content={
                "detail": str(e),
                "error_type": "binary_download_failed",
                "manual_path": e.manual_path,
                "download_urls": e.download_urls,
            },
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": f"隧道启动失败: {e}"},
        )


@router.post("/stop")
def tunnel_stop() -> JSONResponse:
    """停止隧道"""
    svc = get_tunnel_service()
    svc.stop()
    return JSONResponse({
        "status": svc.status,
        "public_url": svc.public_url,
        "provider": svc.provider_name,
    })


# ---------- 配置端点（需认证，不在白名单中） ----------

@router.get("/config")
def tunnel_config_get() -> JSONResponse:
    """获取当前隧道配置（authtoken 脱敏：仅保留末4位）"""
    cfg = get_config().tunnel
    token = cfg.cpolar_authtoken
    # 脱敏：空值返回空串，非空仅显示末4位
    masked_token = token[-4:].rjust(len(token), "•") if token else ""
    return JSONResponse({
        "provider": cfg.provider,
        "local_port": cfg.local_port,
        "cpolar_authtoken_masked": masked_token,
        "cpolar_authtoken_configured": bool(token),
        "binary_path": cfg.binary_path,
        "auto_start": cfg.auto_start,
    })


@router.post("/config")
def tunnel_config_save(body: TunnelConfigBody) -> JSONResponse:
    """保存隧道配置到 config.yaml 并热重载"""
    # 读取现有 yaml（保留其他配置段不动）
    raw = _load_yaml_raw()
    new_raw = copy.deepcopy(raw)

    # 保留已有 authtoken：前端传空串表示"不修改"，只有非空才覆盖
    existing_token = raw.get("tunnel", {}).get("cpolar_authtoken", "")
    new_token = body.cpolar_authtoken if body.cpolar_authtoken else existing_token

    new_raw["tunnel"] = {
        "provider": body.provider,
        "local_port": body.local_port,
        "cpolar_authtoken": new_token,
        "binary_path": body.binary_path,
        "auto_start": body.auto_start,
    }

    try:
        _config_yaml_path().write_text(_dump_yaml_raw(new_raw), encoding="utf-8")
        reload_config()
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": f"配置保存失败: {e}"},
        )

    # 配置变更后重置 service 单例，下次 start 时按新配置创建 provider
    global _tunnel_service
    if _tunnel_service is not None:
        _tunnel_service.stop()
        _tunnel_service = None

    return JSONResponse({"ok": True, "message": "配置已保存，下次启动隧道时生效"})
