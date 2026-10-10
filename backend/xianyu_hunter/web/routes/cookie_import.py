"""登录态 JSON 导入 API - 多通道导入（PRD C2+F2，REQ-016/017）

端点：
- POST /api/auth/cookies/import   导入 Cookie JSON（数组或整档 JSON），返回逐条校验回执

与 /api/auth/cookie（手动注入 name=value 字符串）的分工：
- 本端点面向「从浏览器 DevTools / 扩展导出的 JSON」整档导入场景
- 校验更严格：身份 Cookie（cookie2/sgcookie/unb）齐全性 + 过期条目过滤 + 测试数据拦截
- 校验通过后的归档写入与 Worker 注入由多用户导入归档（T01774）扩展
"""
from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from xianyu_hunter.infra.browser import is_expired_cookie
from xianyu_hunter.web.services.cookie_store import is_test_cookie

logger = logging.getLogger(__name__)

router = APIRouter(tags=["cookie-import"])

# 身份 Cookie 白名单（PRD FR-F2-1）：闲鱼登录态的身份凭证三件套
# 为什么单独定义而不复用 key_cookies：key_cookies 还包含 _m_h5_tk 等会话层
# cookie，会话层可以靠 MTOP 刷新重建，身份层缺失则登录态不可恢复，必须整条拒绝
_IDENTITY_COOKIES: tuple[str, ...] = ("cookie2", "sgcookie", "unb")

# 无效身份 Cookie 时的引导文案：与 PRD FR-C1-4 的修复动作对齐，
# 用户看到的是「下一步做什么」而不是裸错误码
_IDENTITY_MISSING_HINT = (
    "导入内容缺少有效身份 Cookie（cookie2/sgcookie/unb）。"
    "请在已登录闲鱼的浏览器中按 F12 → Application → Cookies 导出后重试，"
    "或改用扫码登录。"
)


def _parse_import_payload(data: object) -> tuple[list[dict], str | None]:
    """解析导入 payload，支持 Cookie JSON 数组与整档 JSON 两种格式

    整档 JSON 指 CookieStore 导出的 {"cookies": [...], "exported_at": ...}
    或扩展导出的 {"cookies": [...]} 包装格式。

    Returns:
        (cookie 列表, 错误文案)。解析失败时列表为空且错误文案非 None。
    """
    if isinstance(data, list):
        entries = data
    elif isinstance(data, dict):
        # 只认 cookies 字段的整档格式：不做 data/items 猜测，
        # 整档导入的语义必须明确，静默猜字段会让用户误以为导入成功
        entries = data.get("cookies")
        if not isinstance(entries, list):
            return [], '无法识别导入格式：请提供 Cookie JSON 数组或含 "cookies" 字段的整档 JSON'
    else:
        return [], "导入格式不支持：body 须为 JSON 数组或 JSON 对象"

    return [e for e in entries if isinstance(e, dict)], None


def _classify_cookie_entry(entry: dict, now: float) -> tuple[str, str]:
    """对单条 Cookie 做校验分类

    Returns:
        (status, reason)：status ∈ accepted / expired_skipped / rejected
    """
    name = str(entry.get("name") or "").strip()
    value = entry.get("value")
    # 残缺判定：name 或 value 缺失/空。value 可能是数字等非字符串，
    # 统一转字符串后再判空，避免 0/False 被误判为残缺
    value_str = str(value) if value is not None else ""
    if not name or not value_str:
        return "rejected", "残缺条目（缺少 name 或 value）"

    if is_test_cookie(name, value_str):
        return "rejected", "测试数据（不符合真实 Cookie 格式）"

    # 过期判定复用既有语义（与 CookieStore._check_key_cookies_expiry 同口径）：
    # - unb / _m_h5_tk_enc 的 expires 字段不可信（unb 导出时常写历史时间戳但登录态仍有效），
    #   跳过过期判定，否则正常导出会被整条拒绝
    # - _m_h5_tk 用内嵌 timestamp 判断，而非 expires 字段
    # - 其余 Cookie 用通用 is_expired_cookie
    if name not in ("unb", "_m_h5_tk_enc"):
        expires = entry.get("expires", -1)
        if name == "_m_h5_tk":
            # 延迟导入避免 routes → modules 的启动期循环依赖
            from xianyu_hunter.modules.cookie_rotator import is_m5tk_expired

            if value_str and is_m5tk_expired(value_str):
                return "expired_skipped", "已过期（_m_h5_tk 内嵌时间戳超时）"
        elif is_expired_cookie({"expires": expires}, now):
            return "expired_skipped", "已过期（expires 早于当前时间）"

    return "accepted", ""


@router.post("/cookies/import")
async def import_cookies(request: Request) -> JSONResponse:
    """导入 Cookie JSON 并返回逐条校验回执

    body 支持两种格式：
    1. Cookie JSON 数组：[{"name": "...", "value": "...", "expires": ...}, ...]
    2. 整档 JSON：{"cookies": [...], "exported_at": ...}

    校验规则（REQ-016/017）：
    - 残缺条目（缺 name/value）→ 拒绝
    - 测试数据条目 → 拒绝
    - 已过期条目 → 跳过（回执中说明）
    - 身份 Cookie（cookie2/sgcookie/unb）全缺失 → 400 + 明确文案
    """
    try:
        data = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={
            "ok": False,
            "error": "请求体不是合法 JSON",
        })

    entries, parse_error = _parse_import_payload(data)
    if parse_error:
        return JSONResponse(status_code=400, content={"ok": False, "error": parse_error})
    if not entries:
        return JSONResponse(status_code=400, content={
            "ok": False,
            "error": "导入内容为空：未解析到任何 Cookie 条目",
        })

    now = time.time()
    results: list[dict] = []
    accepted_names: list[str] = []
    for entry in entries:
        name = str(entry.get("name") or "").strip()
        status, reason = _classify_cookie_entry(entry, now)
        results.append({"name": name, "status": status, "reason": reason})
        if status == "accepted":
            accepted_names.append(name)

    accepted_set = set(accepted_names)
    identity_found = [c for c in _IDENTITY_COOKIES if c in accepted_set]
    identity_missing = [c for c in _IDENTITY_COOKIES if c not in accepted_set]

    # 身份 Cookie 全缺失 → 400：导入的内容无法构成登录态，
    # 提前拒绝比静默接受再让健康检查报「失效」体验更好
    if not identity_found:
        return JSONResponse(status_code=400, content={
            "ok": False,
            "error": _IDENTITY_MISSING_HINT,
            "results": results,
            "identity_missing": identity_missing,
        })

    accepted_count = len(accepted_names)
    return JSONResponse(content={
        "ok": True,
        "total": len(entries),
        "accepted": accepted_names,
        "accepted_count": accepted_count,
        "identity_found": identity_found,
        "identity_missing": identity_missing,
        "results": results,
        "message": f"校验通过：接受 {accepted_count} 条"
                   f"（身份 Cookie: {', '.join(identity_found)}），"
                   f"跳过/拒绝 {len(entries) - accepted_count} 条",
    })
