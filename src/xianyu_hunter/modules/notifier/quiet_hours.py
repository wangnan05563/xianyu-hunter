"""P3-F-10 免打扰时段判定

判定当前是否处于 quiet hours 窗口内。
- 跨午夜支持（23:00-07:00 = 23:00 起算到次日 07:00）
- weekend_only 模式：仅周六/日启用
- 输入"now"：方便测试注入（避免 time.sleep）
"""
from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import TYPE_CHECKING

from xianyu_hunter.infra.db_models import _utcnow

if TYPE_CHECKING:
    from xianyu_hunter.infra.yaml_config import QuietHoursConfig


def _parse_hhmm(s: str) -> time:
    """'HH:MM' → time；解析失败抛 ValueError（config 校验负责）"""
    h, m = s.split(":", 1)
    return time(int(h), int(m))


def is_quiet_now(cfg: "QuietHoursConfig", now: datetime | None = None) -> bool:
    """当前是否处于免打扰时段

    判定逻辑：
    1. cfg.enabled == False → False（不启用）
    2. cfg.weekend_only == True 且当前非周末 → False
    3. 当前时间在 [start, end) 窗口内 → True
       跨午夜：start > end 表示次日才结束（如 23:00-07:00 = 23:00~24:00 OR 0:00~7:00）
    4. 否则 False
    """
    if not cfg.enabled:
        return False
    now = now or _utcnow()
    # 周末模式：周一是 0，周六是 5，周日是 6
    if cfg.weekend_only and now.weekday() not in (5, 6):
        return False
    start_t = _parse_hhmm(cfg.start)
    end_t = _parse_hhmm(cfg.end)
    now_t = now.time()
    if start_t == end_t:
        # 边界：start == end 视为未启用（避免歧义）
        return False
    if start_t < end_t:
        # 同日窗口（如 09:00-12:00）
        return start_t <= now_t < end_t
    # 跨午夜（如 23:00-07:00）：now >= start OR now < end
    return now_t >= start_t or now_t < end_t


def next_quiet_end(cfg: "QuietHoursConfig", now: datetime | None = None) -> datetime | None:
    """下一次免打扰结束的 datetime；不在 quiet 窗口或未启用 → None

    用于 UI 提示"勿扰剩余 N 分钟"——前端不重复实现时区/跨午夜计算。
    """
    if not cfg.enabled or not is_quiet_now(cfg, now):
        return None
    now = now or _utcnow()
    end_t = _parse_hhmm(cfg.end)
    end_dt = now.replace(hour=end_t.hour, minute=end_t.minute, second=0, microsecond=0)
    if end_dt <= now:
        # 跨午夜：end 在明日
        end_dt = end_dt + timedelta(days=1)
    return end_dt
