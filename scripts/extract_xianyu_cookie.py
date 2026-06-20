#!/usr/bin/env python3
"""闲鱼 Cookie 快速提取工具

独立脚本，直接从系统浏览器（Edge/Chrome）提取闲鱼登录所需的关键 Cookie：
- _m_h5_tk：淘宝H5令牌（签名验证必需）
- cookie2：会话标识
- sgcookie：安全网关 Cookie
- unb：用户 ID 标识

使用方式：
    python extract_xianyu_cookie.py              # 自动检测浏览器并提取
    python extract_xianyu_cookie.py --browser edge  # 指定浏览器
    python extract_xianyu_cookie.py --json         # JSON 格式输出（方便程序调用）

依赖：
    - Windows 系统（使用 DPAPI 解密）
    - cryptography 库（用于 Chrome v80+ AES-GCM 解密）：pip install cryptography

作者：XianyuHunter 项目
日期：2026-06-19
"""

from __future__ import annotations

import argparse
import base64
import ctypes
import ctypes.wintypes
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional


# ============== 目标 Cookie 名称 ==============
TARGET_COOKIES = {"_m_h5_tk", "cookie2", "sgcookie", "unb"}
TARGET_DOMAINS = ("%goofish%", "%taobao%", "%alipay%")  # 闲鱼/淘宝/支付宝域名


# ============== DPAPI 解密 ==============
def decrypt_dpapi(encrypted_bytes: bytes) -> Optional[bytes]:
    """使用 Windows DPAPI 解密数据"""
    class DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", ctypes.wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_char)),
        ]

    try:
        dll = ctypes.WinDLL("crypt32.dll", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        blob_in = DATA_BLOB(
            len(encrypted_bytes),
            ctypes.create_string_buffer(encrypted_bytes, len(encrypted_bytes))
        )
        blob_out = DATA_BLOB()

        if dll.CryptUnprotectData(
            ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
        ):
            result = ctypes.string_at(blob_out.pbData, blob_out.cbData)
            kernel32.LocalFree(blob_out.pbData)
            return result
        return None
    except Exception:
        return None


# ============== AES-256-GCM 解密（Chrome v80+） ==============
def get_browser_aes_key(browser_user_data_dir: Path) -> Optional[bytes]:
    """从浏览器的 Local State 文件读取 AES 密钥"""
    local_state_path = browser_user_data_dir / "Local State"
    if not local_state_path.exists():
        return None

    try:
        local_state = json.loads(local_state_path.read_text(encoding="utf-8"))
        encrypted_key_b64 = local_state.get("os_crypt", {}).get("encrypted_key", "")
        if not encrypted_key_b64:
            return None

        encrypted_key = base64.b64decode(encrypted_key_b64)
        # 前 5 字节是 "DPAPI" 前缀
        if encrypted_key[:5] != b"DPAPI":
            print(f"[警告] Local State 加密密钥格式异常")
            return None

        aes_key = decrypt_dpapi(encrypted_key[5:])
        if aes_key and len(aes_key) == 32:
            return aes_key
        return None
    except Exception as e:
        print(f"[调试] 读取 AES 密钥失败: {e}")
        return None


def decrypt_aes_gcm(aes_key: bytes, encrypted_bytes: bytes) -> Optional[str]:
    """AES-256-GCM 解密 Chrome v80+ cookie"""
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        # 去掉 "v10"/"v20" 前缀
        payload = encrypted_bytes[3:]
        nonce = payload[:12]
        ciphertext_with_tag = payload[12:]
        aesgcm = AESGCM(aes_key)
        plaintext = aesgcm.decrypt(nonce, ciphertext_with_tag, None)
        return plaintext.decode("utf-8", errors="replace")
    except ImportError:
        print("[警告] cryptography 库未安装，无法解密新版 Chrome Cookie")
        print("       安装命令: pip install cryptography")
        return None
    except Exception as e:
        print(f"[调试] AES-GCM 解密失败: {e}")
        return None


def decrypt_cookie_value(enc_val: bytes, plain_val: Optional[str], aes_key: Optional[bytes]) -> Optional[str]:
    """统一解密 cookie 值（支持明文/AES-GCM/DPAPI 三种格式）"""
    if plain_val:
        return plain_val

    if not enc_val or len(enc_val) == 0:
        return None

    enc_bytes = bytes(enc_val)

    # Chrome v80+: "v10"/"v20" 前缀 → AES-256-GCM
    if enc_bytes[:3] in (b"v10", b"v20"):
        if aes_key:
            return decrypt_aes_gcm(aes_key, enc_bytes)
        return None

    # 旧版 Chrome: 直接 DPAPI
    decrypted = decrypt_dpapi(enc_bytes)
    if decrypted:
        return decrypted.decode("utf-8", errors="replace")

    return None


# ============== 文件操作 ==============
def copy_locked_file(src: str, dst: str) -> bool:
    """复制可能被浏览器锁定的 Cookie 数据库"""
    os.makedirs(os.path.dirname(dst), exist_ok=True)

    # 方案1：robocopy（Windows 内置，专门处理锁定文件）
    try:
        rc = os.system(
            f'robocopy "{os.path.dirname(src)}" "{os.path.dirname(dst)}" '
            f'"{os.path.basename(src)}" /R:1 /W:1 /NJH /NJS /NDL /NC >nul 2>&1'
        )
        if rc <= 1 and os.path.exists(dst) and os.path.getsize(dst) > 0:
            return True
    except Exception:
        pass

    # 方案2：SQLite backup API（推荐）
    try:
        src_conn = sqlite3.connect(f"file:{src}?mode=ro&nolock=1", uri=True)
        dst_conn = sqlite3.connect(dst)
        src_conn.backup(dst_conn)
        dst_conn.close()
        src_conn.close()
        return True
    except Exception:
        pass

    # 方案3：CreateFileW 共享模式
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
        return True
    finally:
        kernel32.CloseHandle(h_src)


# ============== 浏览器路径配置 ==============
BROWSER_CONFIGS = {
    "edge": {
        "name": "Microsoft Edge",
        "cookies_db": lambda lad: Path(lad) / "Microsoft" / "Edge" / "User Data" / "Default" / "Network" / "Cookies",
        "user_data": lambda lad: Path(lad) / "Microsoft" / "Edge" / "User Data",
    },
    "chrome": {
        "name": "Google Chrome",
        "cookies_db": lambda lad: Path(lad) / "Google" / "Chrome" / "User Data" / "Default" / "Network" / "Cookies",
        "user_data": lambda lad: Path(lad) / "Google" / "Chrome" / "User Data",
    },
}


# ============== 核心：提取 Cookie ==============
def extract_cookies(browser: str = "auto", output_json: bool = False) -> dict:
    """
    从指定浏览器提取闲鱼关键 Cookie

    返回字典格式：
    {
        "success": bool,
        "browser": str,
        "cookies": {
            "_m_h5_tk": "...",
            "cookie2": "...",
            "sgcookie": "...",
            "unb": "..."
        },
        "missing": ["..."],   # 未找到的 cookie 名称
        "message": str
    }
    """
    result = {
        "success": False,
        "browser": browser,
        "cookies": {},
        "missing": list(TARGET_COOKIES),
        "message": "",
    }

    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if not local_app_data:
        result["message"] = "错误：无法确定 %LOCALAPPDATA% 环境变量"
        return result

    # 确定要使用的浏览器
    browsers_to_try = []
    if browser == "auto":
        # 自动检测：优先 Edge，其次 Chrome
        for b_name, b_cfg in BROWSER_CONFIGS.items():
            db_path = b_cfg["cookies_db"](local_app_data)
            if db_path.exists():
                browsers_to_try.append(b_name)
                break  # 找到一个就停止
        if not browsers_to_try:
            result["message"] = "错误：未检测到已安装的 Edge 或 Chrome 浏览器"
            return result
    else:
        if browser not in BROWSER_CONFIGS:
            result["message"] = f"错误：不支持的浏览器 '{browser}'，可选: {list(BROWSER_CONFIGS.keys())}"
            return result
        browsers_to_try.append(browser)

    # 尝试提取
    for b_name in browsers_to_try:
        b_cfg = BROWSER_CONFIGS[b_name]
        source_db = b_cfg["cookies_db"](local_app_data)

        if not source_db.exists():
            result["message"] = f"错误：{b_cfg['name']} 的 Cookie 文件不存在\n路径: {source_db}"
            continue

        # 获取 AES 密钥
        user_data_dir = b_cfg["user_data"](local_app_data)
        aes_key = get_browser_aes_key(user_data_dir) if user_data_dir else None

        # 复制数据库（避免锁定问题）
        tmp_dir = Path(tempfile.mkdtemp(prefix="xh_cookie_extract_"))
        db_copy = tmp_dir / "Cookies_copy"

        try:
            if not copy_locked_file(str(source_db), str(db_copy)):
                result["message"] = (
                    f"错误：无法读取 {b_cfg['name']} 的 Cookie 文件\n"
                    f"原因：文件被锁定（浏览器正在运行？）\n"
                    f"建议：关闭 {b_cfg['name']} 后重试"
                )
                continue

            if not db_copy.exists() or db_copy.stat().st_size == 0:
                result["message"] = f"错误：复制 Cookie 文件失败（文件可能为空）"
                continue

            # 查询目标 Cookie
            extracted = {}
            name_placeholders = ",".join("?" for _ in TARGET_COOKIES)

            with sqlite3.connect(f"file:{db_copy}?mode=ro", uri=True) as conn:
                rows = conn.execute(
                    f"""SELECT host_key, name, encrypted_value, value
                       FROM cookies
                       WHERE (host_key LIKE ? OR host_key LIKE ? OR host_key LIKE ?)
                         AND name IN ({name_placeholders})""",
                    (*TARGET_DOMAINS, *TARGET_COOKIES),
                ).fetchall()

                for host_key, name, enc_val, plain_val in rows:
                    # 同名 cookie 可能存在于多个子域名，优先取 .goofish.com
                    if name in extracted:
                        continue

                    cookie_value = decrypt_cookie_value(enc_val, plain_val, aes_key)
                    if cookie_value:
                        extracted[name] = cookie_value
                        print(f"  [✓] {name} = {cookie_value[:30]}..." if len(cookie_value) > 30 else f"  [✓] {name} = {cookie_value}")
                    else:
                        print(f"  [✗] {name}@{host_key}: 解密失败")

            # 整理结果
            result["browser"] = b_cfg["name"]
            result["cookies"] = extracted
            result["missing"] = [c for c in TARGET_COOKIES if c not in extracted]

            if extracted:
                result["success"] = True
                found_count = len(extracted)
                total_count = len(TARGET_COOKIES)
                if found_count == total_count:
                    result["message"] = f"成功！从 {b_cfg['name']} 提取到全部 {total_count} 个关键 Cookie"
                else:
                    result["message"] = (
                        f"部分成功：从 {b_cfg['name']} 提取到 {found_count}/{total_count} 个 Cookie\n"
                        f"缺失: {', '.join(result['missing'])}\n"
                        f"提示：请确保已在浏览器中登录 https://www.goofish.com"
                    )
            else:
                result["message"] = (
                    f"失败：未在 {b_cfg['name']} 中找到可解密的闲鱼 Cookie\n"
                    f"提示：请先访问 https://www.goofish.com 并登录"
                )

            break  # 成功或明确失败后停止尝试

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    return result


# ============== 输出格式化 ==============
def format_output(result: dict, output_json: bool = False) -> None:
    """格式化输出结果"""
    if output_json:
        # JSON 格式（方便程序调用）
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        # 人性化格式
        print("\n" + "=" * 60)
        print("  闲鱼 Cookie 快速提取工具")
        print("=" * 60)
        print(f"\n浏览器来源: {result.get('browser', '未知')}")
        print(f"状态: {'✅ 成功' if result['success'] else '❌ 失败'}")
        print(f"\n{result.get('message', '')}")

        if result["cookies"]:
            print("\n" + "-" * 40)
            print("  提取结果（可直接复制使用）：")
            print("-" * 40)

            for name in TARGET_COOKIES:
                value = result["cookies"].get(name)
                if value:
                    print(f"\n【{name}】")
                    print(f"  {value}")
                else:
                    print(f"\n【{name}】<未找到>")

            # 输出一键复制版本（紧凑格式）
            print("\n" + "-" * 40)
            print("  一键复制版本（JSON 格式）：")
            print("-" * 40)
            print(json.dumps(result["cookies"], ensure_ascii=False, indent=2))

        if result.get("missing"):
            print("\n" + "-" * 40)
            print("  使用提示：")
            print("-" * 40)
            print("  1. 将上述 Cookie 值填入系统的「Cookie 快速登录」表单")
            print("  2. 如果有缺失项，请先在浏览器访问 https://www.goofish.com 并登录")
            print("  3. 确保登录后刷新页面再重新运行此脚本")

        print("\n" + "=" * 60 + "\n")


# ============== 主入口 ==============
def main():
    parser = argparse.ArgumentParser(
        description="闲鱼 Cookie 快速提取工具 - 从系统浏览器提取登录所需的 4 个关键 Cookie",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s                  # 自动检测浏览器并提取
  %(prog)s --browser edge   # 仅从 Edge 提取
  %(prog)s --json           # JSON 格式输出（适合程序调用）
  %(prog)s --browser chrome --json  # 从 Chrome 提取并以 JSON 输出
        """,
    )
    parser.add_argument(
        "--browser", "-b",
        choices=["auto", "edge", "chrome"],
        default="auto",
        help="指定浏览器（默认: auto 自动检测）",
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="以 JSON 格式输出（方便其他程序调用）",
    )

    args = parser.parse_args()

    # 平台检查
    if os.name != "nt":
        print("错误：此工具仅支持 Windows 系统（需要 DPAPI 解密）")
        sys.exit(1)

    # 执行提取
    result = extract_cookies(browser=args.browser, output_json=args.json)

    # 输出结果
    format_output(result, output_json=args.json)

    # 返回退出码
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
