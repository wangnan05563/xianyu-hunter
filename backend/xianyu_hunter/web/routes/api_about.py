"""About API：暴露系统元信息 + 检查更新 + 一键下载安装更新。

实现：
- GET /api/about 返回 _build_info.py 写入的版本/日期/SHA
- GET /api/about/check-update 调用 GitHub Releases API 查询最新版本
  - 失败安全降级：网络/限速/解析错误时返回 has_update=False, source='local'
  - 缓存：5 分钟内复用上次结果，避免触发 GitHub 限速（60/小时/IP）
- GET /api/about/update/download?latest=... 流式下载指定版本安装包到 data/updates/
  - 下载在后台任务进行，返回当前进度（bytes_downloaded/total），前端轮询
  - 下载 URL 白名单校验：仅允许指向 github.com 的安装包地址，防 SSRF
- POST /api/about/update/install 静默运行已下载的安装包（Inno Setup /VERYSILENT）
  - 静默安装会触发 Windows UAC 提权，由 Inno Setup 安装程序自身弹窗请求
  - 安装完成后新版本自动覆盖旧程序目录

隐私与安全：
- 仅查询公开仓库的 release 元信息，不携带任何认证 token
- 不发送用户身份、cookie、设备指纹等任何信息给 GitHub
- release_url 仅作为跳转链接返回前端，由用户主动打开
- 下载安装包前校验 URL 域名归属（防恶意重定向/SSRF）
"""
from __future__ import annotations

import asyncio
import os
import platform as _platform
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, Body
from loguru import logger

from xianyu_hunter.paths import get_data_dir

router = APIRouter(prefix="/api/about", tags=["meta"])

# 目标 GitHub 仓库（用户指定）
_REPO_OWNER = "wangnan05563"
_REPO_NAME = "xianyu-hunter"
_REPO_URL = f"https://github.com/{_REPO_OWNER}/{_REPO_NAME}"
_RELEASES_API = f"https://api.github.com/repos/{_REPO_OWNER}/{_REPO_NAME}/releases/latest"
# release_url 始终指向 releases 页面（即使无 latest release 也可让用户浏览所有版本）
_RELEASE_URL = f"{_REPO_URL}/releases"
_PRODUCT_NAME = "闲鱼猎人"

# UTC+8 时区（构建日期/检查时间统一使用）
_CST = timezone(timedelta(hours=8))

# 缓存窗口：5 分钟内复用上次成功结果，避免每次轮询都打 GitHub API 触发限速
# GitHub 公共 API 未认证限速为 60 次/小时/IP，5 分钟缓存可将上限压到 12 次/小时
_CACHE_TTL_SECONDS = 300
# HTTP 请求超时：连接 3s + 读取 5s，避免 GitHub API 偶发慢响应阻塞 check-update
_HTTP_TIMEOUT = httpx.Timeout(connect=3.0, read=5.0, write=1.0, pool=1.0)
# 请求头：GitHub API 要求 User-Agent 标识客户端；不携带任何 token
_HTTP_HEADERS = {
    "User-Agent": "XianyuHunter-UpdateChecker/1.0",
    "Accept": "application/vnd.github+json",
}

# 内存缓存：进程级单例，所有请求共享
# 为什么不用 functools.lru_cache：lru_cache 无法缓存异常分支，且这里需要存储 _cached_at 时间戳
_cache: dict[str, Any] = {"data": None, "fetched_at": 0.0}


def _safe_build_info() -> dict[str, str]:
    """读取 _build_info.py，缺字段兜底为 'unknown'。"""
    try:
        from xianyu_hunter import _build_info  # type: ignore[attr-defined]
    except Exception:
        return {"version": "unknown", "build_date": "unknown", "git_sha": "unknown"}
    return {
        "version": getattr(_build_info, "__version__", "unknown"),
        "build_date": getattr(_build_info, "build_date", "unknown"),
        "git_sha": getattr(_build_info, "git_sha", "unknown"),
    }


def _now_iso() -> str:
    return datetime.now(_CST).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# 版本号比较：语义化版本 (semver) 简化实现
# ---------------------------------------------------------------------------
# 为什么不引入 semver 库：仅需要主.次.微三元组比较，标准库 re 即可完成，
# 避免为单点功能增加依赖。
_SEMVER_RE = re.compile(r"^[vV]?(\d+)\.(\d+)\.(\d+)")


def _parse_version(raw: str) -> tuple[int, int, int] | None:
    """解析 'v1.2.3' / '1.2.3' / 'v1.2.3-beta' 为 (1, 2, 3)。

    非语义化版本（如 'unknown'、'main'、空串）返回 None，
    比较时按 (0, 0, 0) 处理，保证 has_update 永远不会误判为 True。
    """
    if not raw or raw == "unknown":
        return None
    m = _SEMVER_RE.match(raw.strip())
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def _is_newer(current: str, latest: str) -> bool:
    """latest 是否严格大于 current。

    任一端无法解析时返回 False（保守策略，避免误报让用户徒劳升级）。
    为什么不 fallback 到 (0,0,0)：current='unknown' 时若按 (0,0,0) 比较，
    任何 GitHub 上的 release 都会被判为「有更新」，让用户徒劳升级。
    """
    c = _parse_version(current)
    l = _parse_version(latest)
    if c is None or l is None:
        return False
    return l > c


# ---------------------------------------------------------------------------
# GitHub Releases API 调用
# ---------------------------------------------------------------------------

def _build_local_response(current: str, *, error: str | None = None) -> dict[str, Any]:
    """构造降级响应：网络失败或缓存未命中时使用，UI 显示「已是最新」或异常提示。

    为什么失败时仍返回 has_update=False 而非 5xx：
    /api/about/check-update 是元信息端点，500 会污染前端 PWA 检查逻辑，
    返回 200 + source='local' + error 字段让前端按需提示。
    """
    resp: dict[str, Any] = {
        "current": current,
        "latest": current,
        "has_update": False,
        "release_url": _RELEASE_URL,
        "checked_at": _now_iso(),
        "source": "local",
    }
    if error:
        # error 字段仅供前端在「长时间无更新」时给出诊断提示，不强制展示
        resp["error"] = error
    return resp


async def _fetch_latest_release() -> dict[str, Any] | None:
    """调用 GitHub Releases API 获取最新 release。

    返回 dict（含 tag_name/html_url/published_at/name）或 None（任何失败）。
    任何异常都吞掉并记录日志，调用方降级处理。
    """
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT, headers=_HTTP_HEADERS) as client:
            resp = await client.get(_RELEASES_API)
        # 404：仓库无任何 release（仅 tag 或预发布），不是错误，正常降级
        if resp.status_code == 404:
            logger.info("[about] GitHub 返回 404：仓库暂无正式 release")
            return None
        # 403 通常为限速触发（GitHub 未认证 60/小时/IP）
        if resp.status_code == 403:
            remaining = resp.headers.get("X-RateLimit-Remaining", "?")
            logger.warning(
                f"[about] GitHub API 限速或拒绝访问 (403)，剩余配额={remaining}"
            )
            return None
        if resp.status_code != 200:
            logger.warning(f"[about] GitHub API 非预期状态码: {resp.status_code}")
            return None
        data = resp.json()
        # 必要字段缺失视为无效响应
        if not isinstance(data, dict) or "tag_name" not in data:
            logger.warning("[about] GitHub API 响应缺少 tag_name 字段")
            return None
        return {
            "tag_name": str(data.get("tag_name", "")).strip(),
            "html_url": str(data.get("html_url", _RELEASE_URL)),
            "published_at": str(data.get("published_at", "")),
            "name": str(data.get("name", "")),
            # 提取安装包下载地址：从 release assets 中匹配 XianyuHunter-Setup-*.exe
            # 为什么只取 Windows 安装包：本项目唯一分发包形态是 Inno Setup 安装程序
            # （installer.iss 产物 XianyuHunter-Setup-v<version>.exe）
            "download_url": _extract_setup_download_url(data.get("assets", [])),
        }
    except httpx.TimeoutException:
        logger.warning("[about] GitHub API 请求超时，降级返回本地版本")
        return None
    except httpx.HTTPError as e:
        logger.warning(f"[about] GitHub API 网络错误: {e}")
        return None
    except Exception as e:
        # JSON 解析、未知异常等：吞掉防止 check-update 端点 500
        logger.warning(f"[about] GitHub API 未知异常: {e}")
        return None


def _extract_setup_download_url(assets: list[Any]) -> str:
    """从 GitHub release assets 中匹配 Windows 安装包下载地址

    匹配规则：name 匹配 XianyuHunter-Setup-v*.exe（防止误配源码 zip / Linux 包），
    且 browser_download_url 存在。未找到返回空串（前端据此隐藏「一键更新」按钮，
    仅保留跳转 GitHub 的手动下载入口）。

    Args:
        assets: GitHub Releases API 的 assets 数组（含 name/browser_download_url）
    """
    if not isinstance(assets, list):
        return ""
    for a in assets:
        if not isinstance(a, dict):
            continue
        name = str(a.get("name", "") or "")
        if re.match(r"^XianyuHunter-Setup-v.+\.exe$", name):
            url = str(a.get("browser_download_url", "") or "")
            if url:
                return url
    return ""


@router.get("", include_in_schema=False)
async def get_about() -> dict[str, Any]:
    """系统元信息：版本、构建日期、Git SHA、Python 版本、平台。"""
    info = _safe_build_info()
    return {
        "product": _PRODUCT_NAME,
        "version": info["version"],
        "build_date": info["build_date"],
        "git_sha": info["git_sha"],
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "platform": _platform.system().lower(),
    }


@router.get("/check-update", include_in_schema=False)
async def check_update() -> dict[str, Any]:
    """检查更新：调用 GitHub Releases API 比对版本。

    流程：
    1. 缓存命中（< 5 分钟）直接返回缓存结果
    2. 缓存过期则发起 GitHub API 请求
    3. 请求成功：与 current 比较版本，缓存结果
    4. 请求失败：降级返回 has_update=False, source='local'（不缓存失败，便于下次重试）
    """
    info = _safe_build_info()
    current = info["version"]

    # 缓存命中：5 分钟内直接复用上次结果
    now = time.monotonic()
    cached = _cache["data"]
    if cached is not None and (now - _cache["fetched_at"]) < _CACHE_TTL_SECONDS:
        # 缓存内容基于同一 current 版本构造，可直接返回
        # 若 current 变化（构建后版本升级），缓存自动失效由下次轮询刷新
        if cached.get("current") == current:
            return cached

    # 缓存过期或 current 变化，发起 GitHub API 请求
    release = await _fetch_latest_release()
    if release is None:
        # 降级：不写缓存，便于下次请求立即重试
        return _build_local_response(current)

    latest = release["tag_name"]
    has_update = _is_newer(current, latest)
    # has_update=True 时 release_url 指向具体 release 页面，否则指向 releases 列表
    release_url = release["html_url"] if has_update else _RELEASE_URL

    result: dict[str, Any] = {
        "current": current,
        "latest": latest,
        "has_update": has_update,
        "release_url": release_url,
        "checked_at": _now_iso(),
        "source": "remote",
        # 额外元信息（可选，前端用于展示发布时间）
        "published_at": release["published_at"],
        # 安装包直接下载地址（仅 has_update 且有安装包资产时非空）。
        # 前端据此渲染「一键更新」按钮；为空则降级为跳转 GitHub 手动下载
        "download_url": release.get("download_url", "") if has_update else "",
    }

    # 写入缓存：仅缓存成功响应
    _cache["data"] = result
    _cache["fetched_at"] = now
    return result


def _reset_cache_for_test() -> None:
    """测试专用：清空缓存。生产代码不要调用。"""
    _cache["data"] = None
    _cache["fetched_at"] = 0.0


# ---------------------------------------------------------------------------
# 一键下载安装更新
# ---------------------------------------------------------------------------
# 下载状态存放目录：data/updates/ （与上一版构建产物目录一致）
_UPDATES_DIR = get_data_dir() / "updates"

# 内存下载任务表：{download_url: DownloadTask}
# 为什么用内存表而非 DB：下载是短生命周期后台任务，进程内记录足够；
# 进程重启后未完成的下载丢弃，由前端重新发起（断点续传非首版目标）
_download_tasks: dict[str, dict[str, Any]] = {}


def _updates_dir() -> Path:
    """确保下载目录存在并返回其 Path（并发调用安全，mkdir exist_ok 幂等）"""
    _UPDATES_DIR.mkdir(parents=True, exist_ok=True)
    return _UPDATES_DIR


def _validate_download_url(url: str) -> str:
    """校验下载 URL 归属，防 SSRF。

    仅允许 github.com（含 objects.githubusercontent.com 重定向资产 CDN）——这是
    GitHub releases 安装包的实际下载域名。校验不通过抛 ValueError，调用方转为 400。
    """
    if not url:
        raise ValueError("缺少下载地址")
    try:
        from urllib.parse import urlparse
        host = urlparse(url).netloc.lower()
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"非法下载地址: {e}") from e
    allowed_suffix = (".github.com", "github.com", ".githubusercontent.com", "githubusercontent.com")
    if not any(host == s or host.endswith("." + s.lstrip(".")) for s in allowed_suffix):
        raise ValueError(f"下载地址域名不受信任: {host}")
    return url


def _sanitize_filename(url: str, fallback: str) -> str:
    """从下载 URL 提取安全的文件名，防路径穿越与无关文件名。

    下载对象必定是 Inno Setup 安装包（.exe），故仅接受以 .exe 结尾的 basename；
    同时拒绝含分隔符/上级目录/盘符的名称。未通过任一条件则回退 fallback。
    """
    from urllib.parse import urlparse, unquote
    path = unquote(urlparse(url).path)
    name = os.path.basename(path.rstrip("/"))
    if (
        not name
        or not name.lower().endswith(".exe")
        or not re.match(r"^[A-Za-z0-9._-]+$", name)
        or ".." in name  # 防路径穿越（..%2F 解出后 basename 可能是 ..）
    ):
        return fallback
    return name


async def _run_download(url: str, task: dict[str, Any]) -> None:
    """后台流式下载安装包到 data/updates/，实时更新进度。

    为什么流式：安装包约 100-300MB，一次性读入内存会撑爆 Web 进程；
    用 httpx 的 iter_bytes 边下边写并累计进度，供前端轮询展示进度条。
    """
    try:
        task["status"] = "downloading"
        task["error"] = ""
        dest_dir = _updates_dir()
        filename = _sanitize_filename(url, "XianyuHunter-Setup.exe")
        dest = dest_dir / filename

        headers = {**_HTTP_HEADERS}
        # 残留文件处理：存在旧安装包则覆盖重下（首版不做真正断点续传——那需要校验
        # 服务端 206 状态与 ETag 一致性，复杂度高；下载失败重下成本可接受）
        if os.path.exists(dest) and dest.stat().st_size > 0:
            dest.unlink()

        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=10.0, read=30.0)) as client:
            async with client.stream("GET", url, headers=headers) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("content-length", "0") or 0)
                task["total"] = total
                done = 0
                with open(dest, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=64 * 1024):
                        f.write(chunk)
                        done += len(chunk)
                        task["bytes_downloaded"] = done
        task["status"] = "done"
        task["bytes_downloaded"] = done
        task["path"] = str(dest)
        logger.info("[about] 更新包下载完成: {} ({} bytes)", filename, done)
    except Exception as e:  # noqa: BLE001
        task["status"] = "error"
        task["error"] = f"下载失败: {e}"
        logger.warning("[about] 更新包下载失败: {}", e)


@router.get("/update/download", include_in_schema=False)
async def update_download(download_url: str = "", latest: str = "") -> dict[str, Any]:
    """发起/查询安装包下载。

    幂等设计：同一 download_url 已有进行中任务则直接返回其进度，不重复发起。
    下载在后台执行，立即返回当前状态，前端轮询本端点获取进度。

    Args:
        download_url: 安装包直接下载地址（来自 check-update 的 download_url）
        latest: 目标版本号（用于日志/提示，不参与下载逻辑）
    """
    try:
        url = _validate_download_url(download_url)
    except ValueError as e:
        return {"ok": False, "status": "error", "error": str(e)}

    task = _download_tasks.get(url)
    if task is None:
        task = {"status": "pending", "total": 0, "bytes_downloaded": 0, "latest": latest}
        _download_tasks[url] = task
        asyncio.create_task(_run_download(url, task))

    return {
        "ok": True,
        "status": task["status"],
        "latest": task.get("latest", latest),
        "total": task.get("total", 0),
        "bytes_downloaded": task.get("bytes_downloaded", 0),
        "error": task.get("error", ""),
        "progress": task.get("progress", 0),
    }


@router.post("/update/install", include_in_schema=False)
async def update_install(download_url: str = Body(default="", embed=True)) -> dict[str, Any]:
    """静默运行已下载的安装包完成安装。

    触发策略：找到该 URL 对应已下载的安装包，用 subprocess.Popen 以静默参数
    （/VERYSILENT /SP- /NORESTART）启动。Inno Setup 安装程序自身带
    requireAdministrator manifest，启动时会弹 UAC 提权确认框，
    用户确认后后台静默安装，过程中本项目进程应退出以避免文件占用冲突。
    """
    try:
        url = _validate_download_url(download_url)
    except ValueError as e:
        return {"ok": False, "error": str(e)}

    task = _download_tasks.get(url)
    if task is None or task.get("status") != "done" or not task.get("path"):
        return {"ok": False, "error": "安装包未就绪，请先完成下载"}

    setup_path = task["path"]
    if not os.path.exists(setup_path):
        return {"ok": False, "error": f"安装包不存在: {setup_path}"}

    try:
        # Inno Setup 静默安装参数：
        #   /VERYSILENT        完全静默（无进度条窗口）
        #   /SP-               跳过"是否确认安装"提示
        #   /NORESTART         安装完成后不强制重启系统
        # 安装程序自身会触发 UAC 提权弹窗，无需本进程提前提权
        subprocess.Popen(
            [setup_path, "/VERYSILENT", "/SP-", "/NORESTART", "/SUPPRESSMSGBOXES"],
            close_fds=True,
        )
        logger.info("[about] 已启动安装程序: {}", os.path.basename(setup_path))
        return {
            "ok": True,
            "message": "安装程序已启动，请在弹出的 UAC 授权后等待安装完成",
            "path": setup_path,
        }
    except OSError as e:
        logger.warning("[about] 启动安装程序失败: {}", e)
        return {"ok": False, "error": f"启动安装程序失败: {e}"}


def _reset_download_tasks_for_test() -> None:
    """测试专用：清空下载任务表与已下载文件。生产代码不要调用。"""
    _download_tasks.clear()
    if _UPDATES_DIR.exists():
        for f in _UPDATES_DIR.iterdir():
            if f.is_file():
                try:
                    f.unlink()
                except OSError:
                    pass
