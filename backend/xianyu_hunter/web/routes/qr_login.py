"""扫码登录 API - QR 码登录流程管理

端点：
- POST /api/auth/login/start     启动扫码流程
- GET  /api/auth/login/status    轮询扫码状态（含二维码 base64）
- POST /api/auth/login/cancel    取消扫码
"""
from __future__ import annotations

from fastapi import APIRouter

from xianyu_hunter.web.services.auth_manager import get_auth_manager

router = APIRouter(prefix="/api/auth", tags=["qr-login"])


@router.post("/login/start")
def login_start(timeout: int = 180) -> dict:
    """启动扫码登录流程，返回二维码信息"""
    am = get_auth_manager()
    return am.start_qr_login(timeout=timeout)


@router.get("/login/status")
def login_status() -> dict:
    """轮询扫码状态（含二维码 base64、过期时间、扫描状态）"""
    am = get_auth_manager()
    return am.poll_qr_status()


@router.post("/login/cancel")
def login_cancel() -> dict:
    """取消当前扫码流程"""
    am = get_auth_manager()
    return am.cancel_qr_login()
