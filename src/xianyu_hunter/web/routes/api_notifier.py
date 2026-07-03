"""通知渠道 API

提供：
- GET  /api/notifier/quiet-hours：读取当前配置 + 运行时状态
- PUT  /api/notifier/quiet-hours：更新配置（热生效，不需重启）
- POST /api/notifier/quiet-hours/reset：清空累计静默计数
- POST /api/notifier/test：向指定渠道发送测试消息（前端"发送测试"按钮调用）
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel, Field, field_validator

from xianyu_hunter.container import Container
from xianyu_hunter.domain.events import Event, EventType
from xianyu_hunter.infra.logger import get_logger
from xianyu_hunter.infra.yaml_config import get_config, reload_config
from xianyu_hunter.modules.notifier.quiet_hours import is_quiet_now, next_quiet_end
from xianyu_hunter.modules.notifier.registry import NotifierRegistry
from xianyu_hunter.web.deps import get_container

logger = get_logger()

router = APIRouter(prefix="/api/notifier", tags=["notifier"])

# 支持测试的渠道及其所需参数映射
_CHANNEL_CREATION_PARAMS: dict[str, list[str]] = {
    "serverchan": ["serverchan_send_key"],
    "pushplus": ["pushplus_token"],
    "bark": ["bark_server", "bark_key"],
    "telegram": ["telegram_bot_token", "telegram_chat_id"],
    "wecom": ["wecom_webhook"],
    "dingtalk": ["dingtalk_webhook", "dingtalk_secret"],
    "webhook": ["webhook_url"],
    "ntfy": ["server", "topic", "token"],
}


class QuietHoursBody(BaseModel):
    """PUT 请求体：quiet hours 完整配置"""
    enabled: bool = False
    start: str = "23:00"
    end: str = "07:00"
    critical_only: bool = True
    weekend_only: bool = False

    @field_validator("start", "end")
    @classmethod
    def _check_hhmm(cls, v: str) -> str:
        """HH:MM 格式校验；非法值直接 422"""
        parts = v.split(":")
        if len(parts) != 2:
            raise ValueError(f"时间格式必须为 HH:MM，收到: {v!r}")
        h, m = parts
        if not (h.isdigit() and m.isdigit()):
            raise ValueError(f"时间必须为数字，收到: {v!r}")
        h_i, m_i = int(h), int(m)
        if not (0 <= h_i < 24 and 0 <= m_i < 60):
            raise ValueError(f"时间越界 00:00-23:59，收到: {v!r}")
        return f"{h_i:02d}:{m_i:02d}"


@router.get("/quiet-hours")
def get_quiet_hours(container: Container = Depends(get_container)) -> dict[str, Any]:
    """读取 quiet hours 配置 + 运行时状态

    返回字段：
    - config: 当前配置（前端表单预填）
    - is_quiet_now: 当前是否处于静默窗口
    - next_end_iso: 静默窗口下次结束的 ISO 时间（null = 当前不在静默中）
    - suppressed_count: 进程内累计被静默的事件数
    - suppressed_last_at: 最近一次静默的 ISO 时间（null = 尚未发生）
    """
    hub = container.notifier_hub
    cfg = hub.quiet_hours_config
    if cfg is None:
        # 容器未注入（测试场景），回退到 YAML
        cfg = get_config().notifier.quiet_hours
    return {
        "config": cfg.model_dump(),
        "is_quiet_now": is_quiet_now(cfg),
        "next_end_iso": next_quiet_end(cfg).isoformat() if next_quiet_end(cfg) else None,
        "suppressed_count": hub.suppressed_count(),
        "suppressed_last_at": (
            hub.suppressed_last_at().isoformat()
            if hub.suppressed_last_at() else None
        ),
    }


@router.put("/quiet-hours")
def update_quiet_hours(
    body: QuietHoursBody = Body(...),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """更新 quiet hours 配置（热生效）

    行为：
    1. 用新 body 覆盖 YAML 中 notifier.quiet_hours
    2. 重新加载全局 config
    3. 调用 hub.set_quiet_hours() 立即生效
    """
    # 1. 读取当前 config + patch notifier.quiet_hours
    from pathlib import Path
    import yaml

    cfg_path = Path("config/config.yaml")
    raw = {}
    if cfg_path.exists():
        raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    raw.setdefault("notifier", {})
    raw["notifier"]["quiet_hours"] = body.model_dump()
    cfg_path.write_text(
        yaml.safe_dump(raw, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    # 2. 热重载 + 注入到 hub
    new_cfg = reload_config()
    container.notifier_hub.set_quiet_hours(new_cfg.notifier.quiet_hours)
    return {
        "ok": True,
        "config": new_cfg.notifier.quiet_hours.model_dump(),
        "is_quiet_now": is_quiet_now(new_cfg.notifier.quiet_hours),
    }


@router.post("/quiet-hours/reset")
def reset_suppressed(container: Container = Depends(get_container)) -> dict[str, Any]:
    """清空累计静默计数（用户进入勿扰结束时段后可手动重置）"""
    container.notifier_hub.reset_suppressed()
    return {"ok": True, "suppressed_count": 0}


# ============== 测试推送端点 ==============

class TestNotifyBody(BaseModel):
    """POST /api/notifier/test 请求体"""
    channel: str = Field(..., description="渠道名称: serverchan/pushplus/bark/telegram/wecom/dingtalk/webhook/ntfy")
    credentials: dict[str, str] = Field(default_factory=dict, description="渠道凭据（key-value）")


@router.post("/test")
async def test_notify(body: TestNotifyBody) -> dict[str, Any]:
    """向指定渠道发送一条测试消息

    前端「发送测试」按钮调用此接口。
    使用前端传入的凭据创建 Notifier 实例，发送后立即返回结果。
    """
    channel = body.channel.lower()
    if channel not in _CHANNEL_CREATION_PARAMS:
        return {
            "ok": False,
            "error": f"未知渠道 '{channel}'",
            "available_channels": list(_CHANNEL_CREATION_PARAMS.keys()),
        }

    # 构造测试事件（使用通用模板）
    test_event = Event(
        type=EventType.TASK_STARTED,
        task_id="__test__",
        payload={"message": "这是一条来自 XianyuHunter 的测试消息"},
    )

    try:
        registry = NotifierRegistry.default()
        # 用前端传来的凭据创建 Notifier（而非 keyring 中的值，
        # 因为用户可能正在修改配置，需要验证新值是否有效）
        notifier = registry.create(channel, **body.credentials)
        result = await notifier.send(test_event)

        return {
            "ok": result.success,
            "channel": result.channel,
            "attempts": result.attempts,
            "response": result.response[:200] if result.response else None,
            "error": result.error if not result.success else None,
        }
    except KeyError as e:
        return {"ok": False, "error": f"缺少必要参数: {e}"}
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        logger.exception(f"[notifier/test] {channel} 测试推送异常: {e}")
        return {"ok": False, "error": f"推送异常: {type(e).__name__}: {e}"}
