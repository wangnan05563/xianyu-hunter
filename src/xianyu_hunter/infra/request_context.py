"""全局请求流水号（request_id）生成与上下文传递

设计要点：
- 流水号格式：req-{YYYYMMDDHHMMSSfff}-{6位hex随机}
  · 时间戳毫秒级保证有序性，便于人工按时间排序定位
  · 6 位 hex 随机（16^6=16.7M）确保同毫秒内多请求的唯一性
  · 单进程内使用 threading.Lock 防止时间戳回拨导致的碰撞
- 使用 contextvars.ContextVar 异步安全传递，兼容 asyncio / 任意线程
- loguru 通过 patcher 钩子读取 ContextVar，自动注入到每条日志的 extra 字段
- 中间件负责生成/透传，业务代码通过 get_request_id() 读取
"""
from __future__ import annotations

import secrets
import threading
from contextvars import ContextVar
from datetime import datetime, timezone

# ContextVar：协程/线程安全的请求上下文
# 默认 None 表示不在任何请求作用域内（如启动期日志）
_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

# 单进程内的生成器锁：防止并发请求在同一毫秒拿到相同时间戳
# 跨进程依赖 6 位 hex 随机碰撞概率极低（16^6=16.7M 分之一）
_gen_lock = threading.Lock()

# 流水号前缀，便于日志中肉眼识别与正则提取
_REQUEST_ID_PREFIX = "req"


def generate_request_id() -> str:
    """生成新的全局流水号

    格式：req-{YYYYMMDDHHMMSSfff}-{6位hex}
    示例：req-20260701120000537-a3b2c1

    线程安全：使用 Lock 保护时间戳读取，避免并发下时间戳回拨导致同号。
    跨进程唯一性：6 位 hex 随机数提供 16.7M 分之一的碰撞概率，配合毫秒时间戳足够。
    """
    with _gen_lock:
        # UTC 时间保证跨时区一致性，与数据库 _utcnow() 对齐
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")[:-3]
        rand = secrets.token_hex(3)  # 3 字节 = 6 hex 字符
        return f"{_REQUEST_ID_PREFIX}-{ts}-{rand}"


def get_request_id() -> str | None:
    """获取当前上下文的 request_id（无上下文时返回 None）

    业务代码、Repository Mixin、EventBus 等通过此函数读取当前请求的流水号，
    写入数据库或传递到子调用。在 asyncio.Task 派生场景下 ContextVar 自动传播。
    """
    return _request_id_var.get()


def set_request_id(request_id: str | None) -> None:
    """设置当前上下文的 request_id

    中间件在请求入口调用此函数注入流水号；
    后台任务在恢复执行上下文时调用此函数恢复关联的流水号。
    """
    _request_id_var.set(request_id)


def clear_request_id() -> None:
    """清除当前上下文的 request_id（请求结束时调用）"""
    _request_id_var.set(None)


def new_request_scope(request_id: str | None = None):
    """生成并设置新的 request_id 到当前上下文，返回可重置 token

    用于后台任务、调度器等非 HTTP 请求场景显式开启追踪作用域：

        token = new_request_scope()
        try:
            do_work()
        finally:
            reset_request_scope(token)

    request_id 为 None 时自动生成新的流水号。
    """
    rid = request_id or generate_request_id()
    token = _request_id_var.set(rid)
    return token


def reset_request_scope(token) -> None:
    """恢复 request_id 上下文到 new_request_scope 之前的状态"""
    _request_id_var.reset(token)


def is_valid_request_id(rid: str | None) -> bool:
    """校验 request_id 格式合法性

    用于防止客户端伪造任意字符串通过 X-Request-Id 头注入日志。
    合法格式：req-<17位数字>-<6位hex>
    """
    if not rid or not isinstance(rid, str):
        return False
    parts = rid.split("-")
    if len(parts) != 3 or parts[0] != _REQUEST_ID_PREFIX:
        return False
    ts, rand = parts[1], parts[2]
    if len(ts) != 17 or not ts.isdigit():
        return False
    if len(rand) != 6:
        return False
    try:
        int(rand, 16)
    except ValueError:
        return False
    return True
