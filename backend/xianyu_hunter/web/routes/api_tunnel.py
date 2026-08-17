# backend/xianyu_hunter/web/routes/api_tunnel.py
"""内网穿透 Tunnel API 端点

提供一键开启/关闭远程访问的能力，返回公网 HTTPS 域名。
- status/start/stop 免认证（远程访问引导场景：未登录时需先建隧道才能访问登录页）
- config 端点需认证（防止未授权修改 provider/authtoken）
- cloudflare setup 端点需认证（一次性配置操作，涉及账号授权）
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
from xianyu_hunter.web.services.tunnel_providers import (
    BinaryDownloadError,
    CloudflareProvider,
    TailscaleFunnelAuthError,
)
from xianyu_hunter.web.services.tunnel_notifications import notify_tunnel_started

router = APIRouter(prefix="/api/tunnel", tags=["tunnel"])

# 全局单例：整个应用共享一个隧道实例
_tunnel_service = None

# 全局 setup provider：login 是两阶段操作（POST start + GET poll），
# 必须在同一个 provider 实例上调用，否则 _login_process / _login_output 状态会丢失
_setup_provider: CloudflareProvider | None = None


def get_tunnel_service():
    """获取或创建全局 TunnelService 单例"""
    global _tunnel_service
    if _tunnel_service is None:
        from xianyu_hunter.web.services.tunnel_service import TunnelService
        # 端口由 TunnelService._resolve_port() 从配置链解析，此处不再硬编码
        _tunnel_service = TunnelService(on_started=notify_tunnel_started)
    return _tunnel_service


# ---------- 配置模型 ----------

class TunnelConfigBody(BaseModel):
    """隧道配置保存请求体"""
    provider: str = "cloudflare"
    local_port: int = 0
    cpolar_authtoken: str = ""
    binary_path: str = ""
    auto_start: bool = False
    tunnel_mode: str = "quick"
    tunnel_name: str = ""
    tunnel_id: str = ""
    credentials_file: str = ""
    hostname: str = ""
    cert_file: str = ""


class CloudflareCreateBody(BaseModel):
    """创建命名隧道请求体"""
    tunnel_name: str
    cert_file: str = ""


class CloudflareRouteDnsBody(BaseModel):
    """配置 DNS 路由请求体"""
    tunnel_name_or_id: str
    hostname: str
    cert_file: str = ""


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


def _create_cloudflare_provider_for_setup() -> CloudflareProvider:
    """创建用于 setup 的 CloudflareProvider 实例（不启动隧道，仅执行一次性配置命令）

    setup 阶段不需要 local_port（只是 provider 初始化需要），用 0 占位即可。
    create / route-dns 等独立阻塞命令每次新建实例即可。
    """
    cfg = get_config().tunnel
    return CloudflareProvider(
        local_port=0,
        binary_path=cfg.binary_path,
        cert_file=cfg.cert_file,
    )


def _get_setup_provider() -> CloudflareProvider:
    """获取全局 setup provider 单例

    login 两阶段流程要求 start_login 和 check_login_status 在同一实例上调用，
    因为 _login_process / _login_output / _login_auth_url 都保存在实例上。
    """
    global _setup_provider
    if _setup_provider is None:
        _setup_provider = _create_cloudflare_provider_for_setup()
    return _setup_provider


def _reset_setup_provider() -> None:
    """重置 setup provider（login 成功或失败后清理，允许后续重试）"""
    global _setup_provider
    if _setup_provider is not None:
        _setup_provider._cleanup_login_process()
        _setup_provider = None


def _save_tunnel_field(field: str, value: str) -> None:
    """将单个 tunnel 配置字段增量写入 config.yaml 并热重载

    用于 setup 向导：每步执行成功后立即持久化结果，避免后续步骤失败时丢失前序成果。
    """
    raw = _load_yaml_raw()
    tunnel_section = raw.get("tunnel", {})
    tunnel_section[field] = value
    raw["tunnel"] = tunnel_section
    _config_yaml_path().write_text(_dump_yaml_raw(raw), encoding="utf-8")
    reload_config()


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
    except TailscaleFunnelAuthError as e:
        # Tailscale 首次启用 Funnel 需用户在浏览器完成授权
        # 返回授权链接，前端渲染可点击的超链接指引用户完成授权
        return JSONResponse(
            status_code=500,
            content={
                "detail": str(e),
                "error_type": "tailscale_funnel_auth",
                "auth_url": e.auth_url,
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
        "tunnel_mode": cfg.tunnel_mode,
        "tunnel_name": cfg.tunnel_name,
        "tunnel_id": cfg.tunnel_id,
        "credentials_file": cfg.credentials_file,
        "hostname": cfg.hostname,
        "cert_file": cfg.cert_file,
        "cert_file_configured": bool(cfg.cert_file),
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
        "tunnel_mode": body.tunnel_mode,
        "tunnel_name": body.tunnel_name,
        "tunnel_id": body.tunnel_id,
        "credentials_file": body.credentials_file,
        "hostname": body.hostname,
        "cert_file": body.cert_file,
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
    # 异步 stop 旧 service：Tailscale 等慢命令可能阻塞 10-30s，
    # 同步 stop 会导致前端 axios 超时报"配置保存失败"
    global _tunnel_service
    if _tunnel_service is not None:
        old_service = _tunnel_service
        _tunnel_service = None
        import threading
        def _async_stop():
            try:
                old_service.stop()
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"配置保存后停止旧隧道失败（忽略）: {e}")
        threading.Thread(target=_async_stop, daemon=True, name="tunnel-stop-on-config").start()

    return JSONResponse({"ok": True, "message": "配置已保存，下次启动隧道时生效"})


# ---------- Cloudflare Named Tunnel 配置向导端点（需认证） ----------

@router.post("/cloudflare/login")
def cloudflare_login() -> JSONResponse:
    """启动 cloudflared tunnel login（非阻塞）

    login 是交互式命令：cloudflared 会打开浏览器让用户授权。
    此端点用 Popen 启动子进程后立即返回授权 URL，不等待用户完成浏览器操作。
    前端通过 GET /cloudflare/login/status 轮询 cert.pem 是否生成。

    返回:
        {"status": "waiting", "auth_url": "...", "message": "..."}
        或 {"status": "failed", "message": "...", "output": "..."}
    """
    provider = _get_setup_provider()
    try:
        result = provider.start_login()
    except Exception as e:
        _reset_setup_provider()
        return JSONResponse(
            status_code=500,
            content={"detail": f"login 启动失败: {e}"},
        )
    # failed 时清理 provider 允许重试；waiting 时保留 provider 供 status 轮询
    if result.get("status") == "failed":
        _reset_setup_provider()
    return JSONResponse(result)


@router.get("/cloudflare/login/status")
def cloudflare_login_status() -> JSONResponse:
    """轮询 cloudflared login 状态

    前端每 2-3 秒调用一次，直到 status 变为 success 或 failed。
    - success: cert.pem 已生成，自动持久化 cert_file 路径并清理 provider
    - failed:  清理 provider 允许重试
    - waiting: 继续轮询
    - idle:    login 未启动（provider 被重置或从未调用 POST /login）
    """
    provider = _get_setup_provider()
    result = provider.check_login_status()

    if result["status"] == "success":
        # 持久化 cert_file，后续 create/route-dns 自动读取
        _save_tunnel_field("cert_file", result["cert_file"])
        _reset_setup_provider()
    elif result["status"] == "failed":
        _reset_setup_provider()

    return JSONResponse(result)


@router.post("/cloudflare/create")
def cloudflare_create(body: CloudflareCreateBody) -> JSONResponse:
    """执行 cloudflared tunnel create <name>（创建命名隧道）

    需要 cert.pem（login 步骤生成）。成功后自动将 tunnel_id 和 credentials_file 持久化。
    """
    cfg = get_config().tunnel
    # 请求体 cert_file 优先于配置中的 cert_file
    cert_file = body.cert_file or cfg.cert_file
    if not cert_file:
        return JSONResponse(
            status_code=400,
            content={"detail": "请先执行 login 步骤获取 cert.pem，或手动指定 cert_file 路径"},
        )

    provider = _create_cloudflare_provider_for_setup()
    try:
        result = provider.setup_create(body.tunnel_name, cert_file=cert_file)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": f"创建隧道失败: {e}"},
        )

    # 持久化 tunnel_id、credentials_file、tunnel_name
    _save_tunnel_field("tunnel_id", result["tunnel_id"])
    _save_tunnel_field("credentials_file", result["credentials_file"])
    _save_tunnel_field("tunnel_name", result["tunnel_name"])
    return JSONResponse({
        "ok": True,
        "tunnel_id": result["tunnel_id"],
        "credentials_file": result["credentials_file"],
        "tunnel_name": result["tunnel_name"],
        "message": "隧道创建成功，可以继续配置 DNS 路由",
    })


@router.post("/cloudflare/route-dns")
def cloudflare_route_dns(body: CloudflareRouteDnsBody) -> JSONResponse:
    """执行 cloudflared tunnel route dns <name> <hostname>（创建 CNAME 记录）

    成功后自动将 hostname 持久化，并切换 tunnel_mode 为 named。
    """
    cfg = get_config().tunnel
    cert_file = body.cert_file or cfg.cert_file
    if not cert_file:
        return JSONResponse(
            status_code=400,
            content={"detail": "请先执行 login 步骤获取 cert.pem，或手动指定 cert_file 路径"},
        )

    provider = _create_cloudflare_provider_for_setup()
    try:
        url = provider.setup_route_dns(body.tunnel_name_or_id, body.hostname, cert_file=cert_file)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": f"DNS 路由配置失败: {e}"},
        )

    # 持久化 hostname，并自动切换到 named 模式
    _save_tunnel_field("hostname", body.hostname)
    _save_tunnel_field("tunnel_mode", "named")
    return JSONResponse({
        "ok": True,
        "public_url": url,
        "message": "DNS 路由配置成功，已自动切换到固定域名模式",
    })
