# src/xianyu_hunter/web/routes/api_tunnel.py
"""内网穿透 Tunnel API 端点

提供一键开启/关闭远程访问的能力，返回公网 HTTPS 域名。
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/tunnel", tags=["tunnel"])

# 全局单例：整个应用共享一个隧道实例
_tunnel_service = None


def get_tunnel_service():
    """获取或创建全局 TunnelService 单例"""
    global _tunnel_service
    if _tunnel_service is None:
        from xianyu_hunter.web.services.tunnel_service import TunnelService
        _tunnel_service = TunnelService(local_port=8000)
    return _tunnel_service


@router.get("/status")
def tunnel_status() -> JSONResponse:
    """查询隧道状态"""
    svc = get_tunnel_service()
    return JSONResponse({
        "status": svc.status,
        "public_url": svc.public_url,
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
        })
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
    })
