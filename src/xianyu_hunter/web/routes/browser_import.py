"""浏览器 Cookie 导入 API - 方案C：从系统浏览器自动导入

端点：
- POST /api/auth/import-from-browser             从 Edge/Chrome 导入 Cookie
- POST /api/auth/import-from-browser/open        打开系统浏览器到闲鱼
- POST /api/auth/import-from-browser/auto        自动尝试 Edge+Chrome 导入
- GET  /api/auth/import-from-browser/status      检测可导入的浏览器

流程：
1. 定位系统浏览器的 Cookies SQLite 文件
2. 提取 goofish / taobao / alipay 域名下的关键 cookie
3. 解密加密值（支持 DPAPI / AES-256-GCM / 明文三种格式）
4. 写入项目的 browser-data/Cookies 数据库 + cookies.json
"""
from __future__ import annotations

import asyncio
import base64
import ctypes
import ctypes.wintypes
import json
import logging
import os
import shutil
import sqlite3
import subprocess
import tempfile
import time
import webbrowser
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from xianyu_hunter.domain.urls import get_base_url
from xianyu_hunter.infra.yaml_config import get_config
from xianyu_hunter.paths import get_browser_data_dir
from xianyu_hunter.web.routes.auth_helpers import make_auth_response
from xianyu_hunter.web.services.cookie_db import init_cookie_table, upsert_cookie
from xianyu_hunter.web.services.cookie_store import get_cookie_store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["browser-import"])

# SQLite backup API 的 immutable 模式 URI 参数：在多个降级策略中作为策略名和 SQL 参数重复使用，
# 提取为常量避免字面量散落（S1192），且便于统一调整
_SQLITE_IMMUTABLE_URI = "immutable=1"


# ============== Windows 系统级辅助函数 ==============

def copy_file_with_share(src: str, dst: str) -> bool:
    """复制可能被锁定的文件（Edge/Chrome 运行时的 Cookie DB）

    优先使用 robocopy（Windows 内置，专门支持复制锁定的文件），
    如果 robocopy 不可用则回退到 CreateFileW 共享模式。
    同时复制 WAL/SHM 辅助文件以确保数据完整性。
    """
    os.makedirs(os.path.dirname(dst), exist_ok=True)

    # 方案1：robocopy（最可靠，专为复制锁定文件设计）
    try:
        rc = subprocess.run(
            ["robocopy", os.path.dirname(src), os.path.dirname(dst),
             os.path.basename(src), "/R:1", "/W:1", "/NJH", "/NJS", "/NDL", "/NC"],
            capture_output=True, timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
        )
        # S1066: 合并嵌套 if，"robocopy 成功且目标文件有效"是同一返回判断
        if rc.returncode <= 1 and os.path.exists(dst) and os.path.getsize(dst) > 0:
            _copy_wal_shm_files(src, dst)
            return True
        if os.path.exists(dst) and os.path.getsize(dst) > 0:
            _copy_wal_shm_files(src, dst)
            return True
    except Exception:
        pass

    # 方案2：CreateFileW 共享模式回退
    GENERIC_READ = 0x80000000
    FILE_SHARE_READ = 0x1
    FILE_SHARE_WRITE = 0x2
    OPEN_EXISTING = 3
    INVALID_HANDLE_VALUE = ctypes.wintypes.HANDLE(-1).value

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    h_src = kernel32.CreateFileW(
        src, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
        None, OPEN_EXISTING, 0, None,
    )
    if h_src == INVALID_HANDLE_VALUE:
        return False

    try:
        BUF_SIZE = 256 * 1024
        with open(dst, "wb") as f_out:
            buf = ctypes.create_string_buffer(BUF_SIZE)
            bytes_read = ctypes.wintypes.DWORD()
            while True:
                success = kernel32.ReadFile(h_src, buf, BUF_SIZE, ctypes.byref(bytes_read), None)
                if not success or bytes_read.value == 0:
                    break
                f_out.write(buf.raw[:bytes_read.value])
        _copy_wal_shm_files(src, dst)
        return True
    finally:
        kernel32.CloseHandle(h_src)


def _copy_wal_shm_files(src_db: str, dst_db: str) -> None:
    """复制 SQLite 的 WAL 和 SHM 辅助文件

    Edge/Chrome 的 Cookie 数据库使用 WAL 模式，运行时最新的 Cookie 可能
    还在 WAL 文件中未提交到主数据库。只复制主文件会导致数据不完整，
    因此需要同时复制 -wal 和 -shm 文件。
    """
    for suffix in ("-wal", "-shm"):
        src_aux = src_db + suffix
        dst_aux = dst_db + suffix
        if os.path.exists(src_aux):
            try:
                # WAL/SHM 文件同样可能被锁定，使用 robocopy 复制
                rc = subprocess.run(
                    ["robocopy", os.path.dirname(src_aux), os.path.dirname(dst_aux),
                     os.path.basename(src_aux), "/R:0", "/W:0", "/NJH", "/NJS", "/NDL", "/NC"],
                    capture_output=True, timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                )
                # robocopy 返回码 <= 1 表示成功（0=有文件复制，1=文件已存在）
                if rc.returncode > 1 and not os.path.exists(dst_aux):
                    # robocopy 失败时尝试普通复制
                    shutil.copy2(src_aux, dst_aux)
            except Exception:
                pass


def decrypt_dpapi(encrypted_bytes: bytes) -> bytes | None:
    """使用 Windows DPAPI 解密数据（CryptUnprotectData）

    用于：
    - Chrome < v80 的旧版 cookie 直接 DPAPI 加密
    - 解密 Local State 中的 AES 密钥（去掉 "DPAPI" 前缀后）
    """
    class DataBlob(ctypes.Structure):
        _fields_ = [
            ("cbData", ctypes.wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_char)),
        ]

    try:
        dll = ctypes.WinDLL("crypt32.dll", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        blob_in = DataBlob(len(encrypted_bytes), ctypes.create_string_buffer(encrypted_bytes, len(encrypted_bytes)))
        blob_out = DataBlob()

        if dll.CryptUnprotectData(
            ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
        ):
            result = ctypes.string_at(blob_out.pbData, blob_out.cbData)
            kernel32.LocalFree(blob_out.pbData)
            return result
        return None
    except Exception:
        return None


def _get_browser_aes_key(browser_user_data_dir: Path) -> bytes | None:
    """从浏览器的 Local State 文件读取并解密 AES-256-GCM 密钥

    Chrome v80+ / Edge 的 cookie 加密流程：
    1. Local State 中 os_crypt.encrypted_key 存储了 base64 编码的加密密钥
    2. base64 解码后前 5 字节是 "DPAPI" 前缀，去掉后用 DPAPI 解密得到 AES 密钥
    3. cookie 的 encrypted_value 以 "v10" 前缀标识，用此密钥做 AES-256-GCM 解密
    """
    local_state_path = browser_user_data_dir / "Local State"
    if not local_state_path.exists():
        return None

    try:
        local_state = json.loads(local_state_path.read_text(encoding="utf-8"))
        encrypted_key_b64 = local_state.get("os_crypt", {}).get("encrypted_key", "")
        if not encrypted_key_b64:
            return None

        encrypted_key = base64.b64decode(encrypted_key_b64)
        # 前 5 字节是 "DPAPI" 前缀，去掉后才是 DPAPI 加密的 AES 密钥
        if encrypted_key[:5] != b"DPAPI":
            logger.warning("Local State encrypted_key 格式异常（缺少 DPAPI 前缀）")
            return None

        aes_key = decrypt_dpapi(encrypted_key[5:])
        if aes_key and len(aes_key) == 32:
            return aes_key
        if aes_key:
            logger.debug("DPAPI 解密得到的密钥长度=%d（期望32）", len(aes_key))
        return None
    except Exception as e:
        logger.debug("读取 Local State AES 密钥失败: %s", e)
        return None


def _decrypt_aes_gcm(aes_key: bytes, encrypted_bytes: bytes) -> str | None:
    """使用 AES-256-GCM 解密 Chrome v80+ 的 cookie 值

    格式：v10/v20 (3 bytes) + nonce (12 bytes) + ciphertext + GCM tag (16 bytes)
    """
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        # 去掉 "v10" / "v20" 前缀
        payload = encrypted_bytes[3:]
        nonce = payload[:12]
        ciphertext_with_tag = payload[12:]
        aesgcm = AESGCM(aes_key)
        plaintext = aesgcm.decrypt(nonce, ciphertext_with_tag, None)
        return plaintext.decode("utf-8", errors="replace")
    except ImportError:
        logger.warning("cryptography 库未安装，无法解密 Chrome v80+ 加密 Cookie")
        return None
    except Exception as e:
        logger.debug("AES-GCM 解密失败: %s", e)
        return None


def decrypt_cookie_value(enc_val: bytes, plain_val: str | None, aes_key: bytes | None) -> str | None:
    """统一解密浏览器 cookie 值，支持三种加密格式

    1. 明文：plain_val 非空直接使用
    2. v10/v20 前缀：Chrome v80+ AES-256-GCM 加密
    3. 无前缀：旧版 Chrome DPAPI 直接加密
    """
    if plain_val:
        return plain_val

    if not enc_val or len(enc_val) == 0:
        return None

    enc_bytes = bytes(enc_val)

    # Chrome v80+ / Edge: "v10" 或 "v20" 前缀标识 AES-256-GCM 加密
    if enc_bytes[:3] in (b"v10", b"v20"):
        if aes_key:
            return _decrypt_aes_gcm(aes_key, enc_bytes)
        # 没有 AES 密钥时无法解密
        return None

    # 旧版 Chrome (< v80): 直接 DPAPI 加密，无前缀
    decrypted = decrypt_dpapi(enc_bytes)
    if decrypted:
        return decrypted.decode("utf-8", errors="replace")

    return None


# ============== API 端点 ==============

# 浏览器用户数据目录名：路径映射与状态检测共享，提取为常量避免散落修改
USER_DATA_DIR_NAME = "User Data"

# 浏览器 Cookie 数据库路径映射（同时包含 Cookies DB 和 User Data 目录用于读取 Local State）
_BROWSER_PATHS = {
    "edge": lambda lad: Path(lad) / "Microsoft" / "Edge" / USER_DATA_DIR_NAME / "Default" / "Network" / "Cookies",
    "chrome": lambda lad: Path(lad) / "Google" / "Chrome" / USER_DATA_DIR_NAME / "Default" / "Network" / "Cookies",
}
_BROWSER_USER_DATA = {
    "edge": lambda lad: Path(lad) / "Microsoft" / "Edge" / USER_DATA_DIR_NAME,
    "chrome": lambda lad: Path(lad) / "Google" / "Chrome" / USER_DATA_DIR_NAME,
}

_TARGET_DOMAINS = ("%goofish%", "%taobao%", "%alipay%")
# 关键 Cookie 名单（用于非全量导入模式的过滤 + 导入结果统计）
# 配置化（cookie_management.key_cookies）：与 cookie_store / _search 等模块共享同一份名单
# 为什么不再硬编码 tracknick：原硬编码包含 tracknick 但不在 key_cookies 中，
# 全量导入模式下不需要白名单，非全量模式按配置 key_cookies 过滤即可
_TARGET_COOKIE_NAMES = set(get_config().cookie_management.key_cookies)
# 是否全量导入：true=保留所有 75+ cookie（推荐），false=仅导入 key_cookies 白名单
# 用户反馈"75 个 cookie 齐全时各类问题大幅度减少"，全量导入是保留 cookie 的关键
_IMPORT_FULL = get_config().cookie_management.import_full


def _build_no_profile_error(browser: str, local_app_data: str) -> dict:
    """构建未找到浏览器 Profile 的错误响应"""
    available = []
    for k, v in _BROWSER_PATHS.items():
        if v(local_app_data).exists():
            available.append(k)
    return {
        "ok": False,
        "error": f"{browser} 浏览器的 Cookie 文件不存在",
        "hint": f"可用浏览器: {available}" if available else "未检测到已安装的 Edge 或 Chrome",
    }


def _try_sqlite_backup(source_db: Path, db_copy: Path, uri_params: str) -> bool:
    """尝试用 SQLite backup API 复制数据库，成功返回 True

    为什么提取：原函数中多次重复相同的 backup 代码块，提取后减少重复并降低嵌套层级。
    """
    try:
        _src = sqlite3.connect(f"file:{source_db}?{uri_params}", uri=True)
        _dst = sqlite3.connect(str(db_copy))
        _src.backup(_dst)
        _dst.close()
        _src.close()
        return db_copy.exists() and db_copy.stat().st_size > 0
    except Exception:
        return False


def _copy_browser_cookie_db_with_fallback(
    source_db: Path, db_copy: Path, browser: str, auto_close: bool,
) -> tuple[bool, str]:
    """4级降级策略复制浏览器 Cookie DB

    顺序：immutable=1 → mode=ro&nolock=1 → copy_file_with_share → 关闭浏览器重试。
    完全绕过文件锁是首要目标，因为 Edge/Chrome 运行时会锁定 Cookie DB。

    重构说明：使用策略列表 + 循环替代多层 if-else，将认知复杂度从 20 降到 10 以下。
    """
    copy_error = ""

    # 前三级策略：SQLite backup API 的两种模式 + 文件级复制
    strategies = [
        (_SQLITE_IMMUTABLE_URI, lambda: _try_sqlite_backup(source_db, db_copy, _SQLITE_IMMUTABLE_URI)),
        ("mode=ro&nolock=1", lambda: _try_sqlite_backup(source_db, db_copy, "mode=ro&nolock=1")),
        ("copy_file_with_share", lambda: copy_file_with_share(str(source_db), str(db_copy))),
    ]

    for name, strategy_fn in strategies:
        if strategy_fn():
            return True, ""
        copy_error = f"策略 {name} 失败"

    # 策略4：检测到锁定时自动关闭浏览器并重试（即使 auto_close=False 也尝试一次）
    if auto_close or not _is_file_locked(source_db):
        return False, copy_error

    exe_name = "msedge.exe" if browser == "edge" else "chrome.exe"
    killed_pids = _kill_browser(exe_name)
    if not killed_pids:
        return False, copy_error

    logger.info("检测到 %s 文件锁定，已自动关闭 %s 进程重试", browser, exe_name)
    time.sleep(2)

    # 关闭后重新尝试复制（优先 immutable，其次文件级复制）
    if _try_sqlite_backup(source_db, db_copy, _SQLITE_IMMUTABLE_URI):
        return True, ""
    if copy_file_with_share(str(source_db), str(db_copy)):
        return True, ""

    return False, copy_error


def _build_copy_failed_error(browser: str, source_db: Path, copy_error: str) -> dict:
    """构建 DB 复制失败的错误响应，含针对性解决方案"""
    is_locked = _is_file_locked(source_db)
    return {
        "ok": False,
        "error": f"无法读取 {browser} 的 Cookie 文件"
                 + (f"（{browser} 正在运行时文件被锁定）" if is_locked else "（文件读取失败）"),
        "hint": (
            f"请尝试以下解决方案：\n"
            f"1. 完全关闭 {browser} 浏览器（包括后台进程）后重试\n"
            f"2. 使用「自动关闭浏览器并导入」按钮\n"
            f"3. 改用「Cookie 注入」标签页手动粘贴 Cookie\n"
            f"4. 改用「浏览器登录」标签页启动独立窗口登录"
        ) if is_locked else f"请检查 {browser} 是否正常安装，或改用手动粘贴 Cookie 方式",
        "error_detail": copy_error if copy_error else None,
    }


def _process_single_cookie_row(
    row: tuple, aes_key: bytes | None, dst_conn: sqlite3.Connection, now_utc: int,
) -> tuple[dict | None, str | None, str | None, bool]:
    """处理单条 cookie 行：解密、写入 DB、返回结果

    Args:
        row: (host_key, name, enc_val, plain_val, path, expires, secure, httponly)
        dst_conn: 目标数据库连接
        now_utc: 当前 UTC 时间戳

    Returns:
        (cookie_dict, name_at_domain, error_msg, has_v20)
        - 成功：cookie_dict 和 name_at_domain 非空，error_msg 为 None
        - 失败：error_msg 非空，cookie_dict 和 name_at_domain 为 None
        - has_v20: 是否检测到 v20 加密格式

    为什么提取：原函数 for 循环内部多层 if-else 和异常处理是复杂度主要来源，
    提取为单条处理函数后，循环体变为简单的结果聚合，复杂度大幅降低。
    """
    host_key, name, enc_val, plain_val, path, expires, secure, httponly = row
    cookie_value = decrypt_cookie_value(enc_val, plain_val, aes_key)

    if not cookie_value:
        enc_bytes = bytes(enc_val) if enc_val else b""
        is_v20 = enc_bytes[:3] == b"v20"
        error_msg = f"{name}@{host_key}: v20加密不支持" if is_v20 else f"{name}@{host_key}: 无法解密"
        return None, None, error_msg, is_v20

    upsert_cookie(dst_conn, {
        "host_key": host_key,
        "name": name,
        "value": cookie_value,
        "path": path or "/",
        "expires_utc": expires or now_utc + 86400 * 365,
        "is_secure": secure or 1,
        "is_httponly": httponly or 1,
        "creation_utc": now_utc,
        "last_access_utc": now_utc,
    })

    cookie_dict = {
        "name": name,
        "value": cookie_value,
        "domain": host_key,
        "path": path or "/",
    }
    return cookie_dict, f"{name}@{host_key}", None, False


def _decrypt_and_upsert_browser_cookies(
    rows: list, aes_key: bytes | None, target_db: Path, now_utc: int,
) -> tuple[list[dict], list[str], list[str], bool]:
    """解密浏览器 cookie 并写入目标 DB

    Returns:
        (imported_cookies, imported_names, errors, has_v20)

    重构说明：将单条 cookie 处理逻辑提取为 _process_single_cookie_row，
    循环体只做结果聚合，认知复杂度从 17 降到 8 以下。
    """
    imported_cookies: list[dict] = []
    imported_names: list[str] = []
    errors: list[str] = []
    has_v20 = False

    with sqlite3.connect(str(target_db)) as dst_conn:
        init_cookie_table(dst_conn)

        for row in rows:
            try:
                cookie_dict, name_at_domain, error_msg, row_has_v20 = _process_single_cookie_row(
                    row, aes_key, dst_conn, now_utc,
                )
                if row_has_v20:
                    has_v20 = True
                if error_msg:
                    errors.append(error_msg)
                    continue
                imported_names.append(name_at_domain)
                imported_cookies.append(cookie_dict)
            except Exception as e:
                name = row[1] if len(row) > 1 else "unknown"
                host_key = row[0] if len(row) > 0 else "unknown"
                errors.append(f"{name}@{host_key}: {e}")

        dst_conn.commit()

    return imported_cookies, imported_names, errors, has_v20


def _build_base_result(imported_names: list[str], browser: str) -> dict:
    """构建导入结果的基础字段（不含副作用和条件分支）

    为什么提取：基础字段构建与副作用逻辑分离，降低主函数复杂度。
    """
    return {
        "ok": len(imported_names) > 0,
        "imported_count": len(imported_names),
        "imported_cookies": imported_names,
        "source_browser": browser,
    }


def _add_v20_hint(result: dict) -> None:
    """向结果中添加 v20 加密提示信息"""
    result["has_v20"] = True
    result["v20_hint"] = (
        "检测到 Chrome/Edge v127+ 的 App-Bound Encryption (v20)，"
        "无法离线解密。请改用 CDP 方式：先运行 scripts/start_edge_debug.ps1 "
        "启动调试浏览器，然后调用 /api/auth/import-from-browser/cdp"
    )


def _handle_dry_run_mode(result: dict, imported_cookies: list[dict]) -> None:
    """处理 dry_run 模式：只返回 cookies 字典，不做持久化"""
    cookies_map = {c["name"]: c["value"] for c in imported_cookies if c.get("name")}
    result["cookies"] = cookies_map
    result["dry_run"] = True


def _handle_persist_mode(imported_cookies: list[dict], user_id: str) -> None:
    """处理持久化模式：写入 JSON、同步层状态、启动会话

    为什么提取：将所有副作用逻辑从主函数中分离，主函数只做流程编排。
    每个副作用都有独立的 try-except，互不影响。
    """
    json_written = get_cookie_store().export_cookies(
        imported_cookies, method="import", user_id=user_id,
    )
    if not json_written:
        return

    try:
        from xianyu_hunter.modules.login_orchestrator import sync_cookie_layers_from_json
        sync_cookie_layers_from_json()
    except Exception as e:
        logger.debug("浏览器导入后同步层状态失败: %s", e)

    try:
        from xianyu_hunter.web.services.session_starter import trigger_session_start
        trigger_session_start()
    except Exception as e:
        logger.debug("自动启动会话失败: %s", e)


def _build_import_result(
    imported_names: list[str],
    imported_cookies: list[dict],
    errors: list[str],
    has_v20: bool,
    browser: str,
    dry_run: bool,
    user_id: str = "default",
) -> dict:
    """构建导入结果，处理 dry_run 预览和实际写入两种模式

    多用户隔离：user_id 决定 cookie 写入到哪个 cookies_{user_id}.json。

    重构说明：将条件分支和副作用拆分为独立函数，主函数只做流程编排，
    认知复杂度从 17 降到 8 以下。
    """
    result = _build_base_result(imported_names, browser)

    if has_v20:
        _add_v20_hint(result)

    if errors:
        result["errors"] = errors[:10]

    if not imported_names:
        result["message"] = "未能导入任何 Cookie（可能解密失败）"
        result["ok"] = False
        return result

    result["message"] = f"成功从 {browser} 导入 {len(imported_names)} 个 Cookie"

    if dry_run:
        _handle_dry_run_mode(result, imported_cookies)
    else:
        _handle_persist_mode(imported_cookies, user_id)

    return result


def _fetch_cookie_rows_from_src(src_conn: sqlite3.Connection) -> list | None:
    """从源 DB 查询闲鱼相关 cookie 行

    全量导入 vs 白名单导入由 _IMPORT_FULL 配置决定：
    - 全量：保留所有闲鱼相关域名下的 cookie（75+ 个）
    - 白名单：仅导入 key_cookies（会丢失 68 个 cookie，不推荐）

    为什么优先全量：用户反馈 75 个 cookie 齐全时各类问题大幅度减少，
    白名单过滤会丢失 tracking 层 cookie（cna/tfstk 等）导致反爬风险升高。
    返回 None 表示数据库无 cookies 表（格式异常）。
    """
    table_check = src_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='cookies'"
    ).fetchone()
    if not table_check:
        return None

    if _IMPORT_FULL:
        return src_conn.execute(
            """SELECT host_key, name, encrypted_value, value, path,
                      expires_utc, is_secure, is_httponly
               FROM cookies
               WHERE host_key LIKE ? OR host_key LIKE ? OR host_key LIKE ?""",
            _TARGET_DOMAINS,
        ).fetchall()

    name_placeholders = ",".join("?" for _ in _TARGET_COOKIE_NAMES)
    return src_conn.execute(
        f"""SELECT host_key, name, encrypted_value, value, path,
                  expires_utc, is_secure, is_httponly
           FROM cookies
           WHERE (host_key LIKE ? OR host_key LIKE ? OR host_key LIKE ?)
             AND name IN ({name_placeholders})""",
        (*_TARGET_DOMAINS, *_TARGET_COOKIE_NAMES),
    ).fetchall()


def _is_db_copy_usable(db_copy: Path) -> bool:
    """检查 DB 副本是否可用（存在且非空）

    为什么独立：原 _do_import_from_browser 中 `not copy_ok or not db_copy.exists()
    or db_copy.stat().st_size == 0` 三重 or 条件贡献认知复杂度。
    """
    return db_copy.exists() and db_copy.stat().st_size > 0


def _decode_cookies_from_db_copy(
    db_copy: Path, aes_key: bytes | None, target_db: Path, browser: str,
) -> tuple[list[dict], list[str], list[str], bool] | dict:
    """从 DB 副本查询并解密 cookie 行

    返回 dict 表示失败响应（无表/无 cookie），返回 tuple 表示解密结果。
    为什么独立：原 _do_import_from_browser 中 with 块内两个嵌套 if 早返回
    是认知复杂度主要来源。
    """
    with sqlite3.connect(f"file:{db_copy}?mode=ro", uri=True) as src_conn:
        rows = _fetch_cookie_rows_from_src(src_conn)
        if rows is None:
            return {
                "ok": False,
                "error": f"{browser} Cookie 数据库格式异常：未找到 cookies 表",
                "hint": "可能需要关闭浏览器后重试，或改用手动粘贴 Cookie 方式",
            }
        if not rows:
            return {
                "ok": False,
                "error": f"未在 {browser} 中找到闲鱼相关 Cookie",
                "hint": f"请先在 {browser} 中访问 {get_base_url()} 并登录",
            }
        now_utc = int(time.time()) + 11644473600
        return _decrypt_and_upsert_browser_cookies(rows, aes_key, target_db, now_utc)


def _do_import_from_browser(browser: str, auto_close: bool = False, dry_run: bool = False, user_id: str = "default") -> dict:
    """从系统浏览器导入 Cookie 的核心逻辑（返回 dict，由端点包装为 JSONResponse）

    Args:
        browser: 浏览器类型（edge/chrome）
        auto_close: 文件被锁定时是否自动关闭浏览器
        dry_run: True 时只解密读取、不写入 CookieStore，并在结果中返回 cookies 字典
                 供前端"从浏览器导入预览"使用
        user_id: 多用户隔离，决定 cookie 写入到哪个 cookies_{user_id}.json
    """
    from xianyu_hunter.web.services.browser_profile import discover_profiles

    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if not local_app_data:
        return {"ok": False, "error": "无法确定 %LOCALAPPDATA% 路径"}

    # 多 Profile 支持：遍历所有 Profile，优先使用含闲鱼 Cookie 的
    profiles = discover_profiles(browser)
    if not profiles:
        return _build_no_profile_error(browser, local_app_data)

    # 选取第一个（已按优先级排序：含闲鱼 Cookie 的在前）
    selected_profile = profiles[0]
    source_db = selected_profile.cookies_db
    user_data_dir = selected_profile.user_data_dir
    logger.info(
        "选择 Profile: %s (含闲鱼Cookie: %s)",
        selected_profile.name, selected_profile.has_xianyu_cookie
    )

    # 从 Local State 获取 AES 密钥（Chrome v80+ / Edge 加密所需）
    aes_key = _get_browser_aes_key(user_data_dir) if user_data_dir else None
    if aes_key:
        logger.info("成功获取 %s AES 密钥（Chrome v80+ 加密格式）", browser)
    else:
        logger.info("未获取到 %s AES 密钥（将尝试旧版 DPAPI 解密）", browser)

    if auto_close and _is_file_locked(source_db):
        exe_name = "msedge.exe" if browser == "edge" else "chrome.exe"
        _kill_browser(exe_name)
        time.sleep(2)

    cfg = get_config()
    target_db = get_browser_data_dir(cfg.browser.user_data_dir) / "Default" / "Network" / "Cookies"
    target_db.parent.mkdir(parents=True, exist_ok=True)

    tmp_dir = None
    try:
        tmp_dir = Path(tempfile.mkdtemp(prefix="xh_cookie_"))
        db_copy = tmp_dir / "Cookies_copy"

        # 文件复制策略（4级降级）：完全绕过文件锁是首要目标
        copy_ok, copy_error = _copy_browser_cookie_db_with_fallback(
            source_db, db_copy, browser, auto_close,
        )

        if not copy_ok or not _is_db_copy_usable(db_copy):
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return _build_copy_failed_error(browser, source_db, copy_error)

        decode_result = _decode_cookies_from_db_copy(db_copy, aes_key, target_db, browser)
        if isinstance(decode_result, dict):
            # 解码失败（无表/无 cookie）：先清理临时目录再返回错误响应
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return decode_result

        imported_cookies, imported_names, errors, has_v20 = decode_result
        result = _build_import_result(
            imported_names, imported_cookies, errors, has_v20, browser, dry_run, user_id,
        )

        shutil.rmtree(tmp_dir, ignore_errors=True)
        return result

    except Exception as e:
        if tmp_dir is not None:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        return {"ok": False, "error": f"导入失败: {e}", "imported_count": 0}


@router.post("/import-from-browser")
async def import_from_browser(request: Request, browser: str = "edge", auto_close: bool = False) -> JSONResponse:
    """从系统已登录的浏览器中自动提取闲鱼/淘宝 Cookie 并注入到项目 browser-data

    多用户隔离：从 request.state.user_id 获取当前登录用户，按 user_id 写入
    cookies_{user_id}.json。
    """
    cookie_user_id = getattr(request.state, "user_id", None) or "default"
    result = await asyncio.to_thread(_do_import_from_browser, browser, auto_close, False, cookie_user_id)
    if result.get("ok"):
        try:
            from xianyu_hunter.web.services.cookie_runtime_sync import inject_cookie_store_to_worker_browser

            await inject_cookie_store_to_worker_browser("浏览器离线导入")
        except Exception as e:
            logger.debug("浏览器离线导入后同步 Worker 浏览器失败: %s", e)
        return make_auth_response(result)
    return JSONResponse(content=result)


@router.post("/import-from-browser/open")
def open_browser_login() -> JSONResponse:
    """打开系统默认浏览器到闲鱼首页，用户登录后可通过导入功能获取 Cookie
    
    与 Playwright 启动的浏览器不同，此方法使用系统原生浏览器，
    不会被闲鱼反爬系统检测到自动化标志。
    """
    try:
        # 使用 webbrowser.open 打开系统默认浏览器
        # 优先尝试用 Edge 打开（Windows 默认），失败则用默认浏览器
        edge_path = None
        for candidate in [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ]:
            if os.path.exists(candidate):
                edge_path = candidate
                break
        
        if edge_path:
            webbrowser.register("edge", None, webbrowser.BackgroundBrowser(edge_path))
            webbrowser.get("edge").open(get_base_url())
        else:
            webbrowser.open(get_base_url())
        
        return JSONResponse(content={
            "ok": True,
            "message": "已在系统浏览器中打开闲鱼，请登录后返回此页面点击「导入登录状态」",
        })
    except Exception as e:
        return JSONResponse(content={"ok": False, "error": f"无法打开浏览器: {e}"})


@router.post("/import-from-browser/auto")
async def auto_import() -> JSONResponse:
    """自动尝试从 Edge 和 Chrome 导入 Cookie（优先 Edge，失败则尝试 Chrome）"""
    all_errors: list[str] = []
    for browser in ["edge", "chrome"]:
        result = await asyncio.to_thread(_do_import_from_browser, browser, False)
        if result.get("ok") and result.get("imported_count", 0) > 0:
            try:
                from xianyu_hunter.web.services.cookie_runtime_sync import inject_cookie_store_to_worker_browser

                await inject_cookie_store_to_worker_browser("浏览器自动导入")
            except Exception as e:
                logger.debug("浏览器自动导入后同步 Worker 浏览器失败: %s", e)
            return make_auth_response(result)
        all_errors.extend(result.get("errors", []))

    # 检测是否因 v20 加密导致失败
    has_v20 = any("v20加密" in e for e in all_errors)
    if has_v20:
        return JSONResponse(content={
            "ok": False,
            "error": "Chrome/Edge 使用 v20 应用绑定加密，无法离线导入 Cookie",
            "hint": "请改用「浏览器登录」功能（弹出 Playwright 窗口扫码登录），或手动粘贴 Cookie",
        })

    # 两个浏览器都失败了，返回详细的错误信息
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    available = [k for k, v in _BROWSER_PATHS.items() if v(local_app_data).exists()] if local_app_data else []
    return JSONResponse(content={
        "ok": False,
        "error": "未在 Edge 或 Chrome 中找到闲鱼登录 Cookie",
        "hint": "请先在浏览器中访问 {base_url} 并登录，然后重试".format(base_url=get_base_url()) + (
            f"（检测到: {', '.join(available)}）" if available else "（未检测到 Edge 或 Chrome）"
        ),
    })


@router.get("/import-from-browser/status")
def import_status() -> dict:
    """检测系统浏览器是否包含可导入的闲鱼 Cookie（供前端判断是否显示「一键导入」按钮）"""
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    browsers = {}
    for name, rel_path in [
        ("edge", rf"Microsoft\Edge\{USER_DATA_DIR_NAME}\Default\Network\Cookies"),
        ("chrome", rf"Google\Chrome\{USER_DATA_DIR_NAME}\Default\Network\Cookies"),
    ]:
        db_path = Path(local_app_data) / rel_path
        info = {"exists": db_path.exists(), "path": str(db_path), "has_goofish_cookie": False}
        if db_path.exists():
            try:
                with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
                    # 检查 cookies 表是否存在（新版 Chrome/Edge 可能格式不同）
                    table_exists = conn.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='cookies'"
                    ).fetchone()
                    if not table_exists:
                        info["has_goofish_cookie"] = False
                        continue
                    count = conn.execute(
                        "SELECT COUNT(*) FROM cookies WHERE (host_key LIKE '%goofish%' OR host_key LIKE '%taobao%') AND name='_m_h5_tk'"
                    ).fetchone()[0]
                    info["has_goofish_cookie"] = count > 0
                    info["_m_h5_tk_count"] = count
            except Exception:
                pass
        browsers[name] = info
    return browsers


# ============== 浏览器进程管理辅助函数 ==============

def _is_file_locked(filepath: Path) -> bool:
    """检测文件是否被其他进程锁定（无法以共享读取模式打开）"""
    if not filepath.exists():
        return False
    GENERIC_READ = 0x80000000
    FILE_SHARE_READ = 0x1
    FILE_SHARE_WRITE = 0x2
    OPEN_EXISTING = 3
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    h = kernel32.CreateFileW(
        str(filepath), GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None, OPEN_EXISTING, 0, None,
    )
    if h == -1:  # INVALID_HANDLE_VALUE
        return True
    kernel32.CloseHandle(h)
    return False


def _kill_browser(exe_name: str) -> list[int]:
    """关闭指定浏览器进程，返回被关闭的 PID 列表

    注意：只关闭主窗口进程（不含 Edge 的辅助进程如 gpu/render），
    这样用户重新打开时可以恢复之前的标签页。
    """
    killed = []
    try:
        import psutil
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['name'] and proc.info['name'].lower() == exe_name.lower():
                    # 只杀主进程（有窗口标题的），跳过子进程
                    cmdline = proc.info.get('cmdline') or []
                    is_helper = any(
                        x in ' '.join(cmdline).lower()
                        for x in ['--type=gpu-process', '--type=renderer',
                                   '--type=utility', '--type=broker',
                                   '--crashpad-handler']
                    )
                    if not is_helper:
                        proc.terminate()
                        killed.append(proc.info['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except ImportError:
        # psutil 不可用时回退到 taskkill
        subprocess.run(
            ["taskkill", "/f", "/im", exe_name],
            capture_output=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
        )
        killed = [-1]  # 标记为"已尝试"
    except Exception:
        pass
    return killed
