"""About 更新下载/安装 API 单元测试。

覆盖：
- _extract_setup_download_url：从 release assets 提取安装包下载地址
- _validate_download_url：下载 URL 归属白名单（防 SSRF）
- _sanitize_filename：文件名防路径穿越
- GET /api/about/update/download：发起/查询下载（mock httpx 流）
- POST /api/about/update/install：安装包就绪校验与启动安装
- check-update 返回 download_url 字段契约
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from xianyu_hunter.web.routes import api_about


# ---------------------------------------------------------------------------
# 资产提取
# ---------------------------------------------------------------------------

class TestExtractSetupDownloadUrl:
    def test_matches_windows_setup_exe(self) -> None:
        assets = [{"name": "XianyuHunter-Setup-v1.2.0.exe", "browser_download_url": "https://github.com/wangnan05563/xianyu-hunter/releases/download/v1.2.0/XianyuHunter-Setup-v1.2.0.exe"}]
        assert api_about._extract_setup_download_url(assets) == "https://github.com/wangnan05563/xianyu-hunter/releases/download/v1.2.0/XianyuHunter-Setup-v1.2.0.exe"

    def test_ignores_source_zip_and_other_assets(self) -> None:
        assets = [
            {"name": "Source-code.zip", "browser_download_url": "https://github.com/wangnan05563/xianyu-hunter/releases/download/v1.2.0/Source-code.zip"},
            {"name": "linux.tar.gz", "browser_download_url": "https://github.com/wangnan05563/xianyu-hunter/releases/download/v1.2.0/linux.tar.gz"},
        ]
        assert api_about._extract_setup_download_url(assets) == ""

    def test_not_assets_type_returns_empty(self) -> None:
        assert api_about._extract_setup_download_url(None) == ""
        assert api_about._extract_setup_download_url("not-a-list") == ""

    def test_missing_browser_download_url_returns_empty(self) -> None:
        assets = [{"name": "XianyuHunter-Setup-v1.2.0.exe"}]  # 无 download url
        assert api_about._extract_setup_download_url(assets) == ""


# ---------------------------------------------------------------------------
# URL 校验（防 SSRF）
# ---------------------------------------------------------------------------

class TestValidateDownloadUrl:
    def test_accepts_github_com(self) -> None:
        url = "https://github.com/wangnan05563/xianyu-hunter/releases/download/v1.0.0/app.exe"
        assert api_about._validate_download_url(url) == url

    def test_accepts_objects_githubusercontent_cdn(self) -> None:
        url = "https://objects.githubusercontent.com/github-production-release-asset-2e65be/123/app.exe"
        assert api_about._validate_download_url(url) == url

    def test_rejects_arbitrary_domain(self) -> None:
        with pytest.raises(ValueError):
            api_about._validate_download_url("https://evil.example.com/payload.exe")

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError):
            api_about._validate_download_url("")


# ---------------------------------------------------------------------------
# 文件名安全
# ---------------------------------------------------------------------------

class TestSanitizeFilename:
    def test_extracts_basename(self) -> None:
        url = "https://github.com/wangnan05563/xianyu-hunter/releases/download/v1.0.0/XianyuHunter-Setup-v1.0.0.exe"
        assert api_about._sanitize_filename(url, "fallback.exe") == "XianyuHunter-Setup-v1.0.0.exe"

    def test_rejects_non_exe_returns_fallback(self) -> None:
        # 非 .exe 后缀（源码包/脚本）应回退，保证下载的一定是安装包
        url = "https://github.com/wangnan05563/xianyu-hunter/releases/download/v1/package.zip"
        assert api_about._sanitize_filename(url, "XianyuHunter-Setup.exe") == "XianyuHunter-Setup.exe"

    def test_rejects_path_traversal_name(self) -> None:
        # 文件名含 ..（编码成 ..%2F 解出）应回退，防路径穿越
        url = "https://github.com/x/releases/download/v1/..%2F..exe"
        assert api_about._sanitize_filename(url, "XianyuHunter-Setup.exe") == "XianyuHunter-Setup.exe"

    def test_empty_path_uses_fallback(self) -> None:
        url = "https://github.com/x/releases/download/v1/"
        assert api_about._sanitize_filename(url, "XianyuHunter-Setup.exe") == "XianyuHunter-Setup.exe"


# ---------------------------------------------------------------------------
# check-update 返回 download_url 字段契约
# ---------------------------------------------------------------------------

def test_check_update_includes_download_url_when_available(monkeypatch):
    """有安装包资产时 check-update 应返回 download_url。"""
    from unittest.mock import AsyncMock, patch
    import types, sys
    import xianyu_hunter

    api_about._reset_cache_for_test()
    fake = types.ModuleType("xianyu_hunter._build_info")
    fake.__version__ = "1.0.0"  # type: ignore[attr-defined]
    fake.build_date = "2026-06-28"  # type: ignore[attr-defined]
    fake.git_sha = "abc1234"  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "xianyu_hunter._build_info", fake)
    monkeypatch.setattr(xianyu_hunter, "_build_info", fake, raising=False)

    from xianyu_hunter.config import get_settings
    from xianyu_hunter.config import Settings
    test_settings = Settings(web_token="test-token-about-api")
    monkeypatch.setattr("xianyu_hunter.config.get_settings", lambda: test_settings)
    monkeypatch.setattr("xianyu_hunter.web.app.get_settings", lambda: test_settings, raising=False)

    dl_url = "https://github.com/wangnan05563/xianyu-hunter/releases/download/v1.2.0/XianyuHunter-Setup-v1.2.0.exe"
    with patch.object(
        api_about, "_fetch_latest_release",
        new=AsyncMock(return_value={
            "tag_name": "v1.2.0",
            "html_url": "https://github.com/wangnan05563/xianyu-hunter/releases/tag/v1.2.0",
            "published_at": "2026-06-15T00:00:00Z",
            "name": "Release 1.2.0",
            "download_url": dl_url,
        })
    ):
        from xianyu_hunter.web.app import app
        client = TestClient(app, raise_server_exceptions=False)
        data = client.get("/api/about/check-update").json()

    assert data["has_update"] is True
    assert data["download_url"] == dl_url
    get_settings.cache_clear()
    api_about._reset_cache_for_test()


def test_check_update_download_url_empty_when_no_update(monkeypatch):
    """无更新时 download_url 应为空串。"""
    from unittest.mock import AsyncMock, patch
    import types, sys
    import xianyu_hunter
    from xianyu_hunter.config import get_settings
    from xianyu_hunter.config import Settings
    from xianyu_hunter.web.app import app

    api_about._reset_cache_for_test()
    fake = types.ModuleType("xianyu_hunter._build_info")
    fake.__version__ = "1.0.0"  # type: ignore[attr-defined]
    fake.build_date = "2026-06-28"  # type: ignore[attr-defined]
    fake.git_sha = "abc1234"  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "xianyu_hunter._build_info", fake)
    monkeypatch.setattr(xianyu_hunter, "_build_info", fake, raising=False)

    test_settings = Settings(web_token="test-token-about-api")
    monkeypatch.setattr("xianyu_hunter.config.get_settings", lambda: test_settings)
    monkeypatch.setattr("xianyu_hunter.web.app.get_settings", lambda: test_settings, raising=False)

    with patch.object(
        api_about, "_fetch_latest_release",
        new=AsyncMock(return_value={
            "tag_name": "v1.0.0",
            "html_url": "https://github.com/wangnan05563/xianyu-hunter/releases/tag/v1.0.0",
            "published_at": "2026-06-01T00:00:00Z",
            "name": "",
        })
    ):
        client = TestClient(app, raise_server_exceptions=False)
        data = client.get("/api/about/check-update").json()

    assert data["has_update"] is False
    assert data["download_url"] == ""
    get_settings.cache_clear()
    api_about._reset_cache_for_test()


# ---------------------------------------------------------------------------
# GET /api/about/update/download
# ---------------------------------------------------------------------------

def test_download_rejects_non_github_url() -> None:
    """SSRF 防护：非 GitHub 域名的下载地址应被拒绝。"""
    url = "https://evil.example.com/payload.exe"
    with pytest.raises(ValueError):  # 直接测校验函数
        api_about._validate_download_url(url)


def test_download_endpoint_returns_progress_schema(monkeypatch) -> None:
    """下载端点应返回进度字段契约（mock 掉实际下载逻辑）。"""
    from unittest.mock import patch
    from fastapi.testclient import TestClient
    from xianyu_hunter.web.app import app

    test_id = object()
    api_about._download_tasks.clear()
    url = "https://github.com/wangnan05563/xianyu-hunter/releases/download/v1.2.0/XianyuHunter-Setup-v1.2.0.exe"
    api_about._download_tasks[url] = {
        "status": "done", "total": 1000, "bytes_downloaded": 1000, "latest": "v1.2.0",
        "path": str(test_id),  # 非真实路径，仅测返回结构
    }
    try:
        # 注入测试 client 需要的 settings
        from xianyu_hunter.config import get_settings, Settings
        test_settings = Settings(web_token="t")
        monkeypatch.setattr("xianyu_hunter.config.get_settings", lambda: test_settings)
        monkeypatch.setattr("xianyu_hunter.web.app.get_settings", lambda: test_settings, raising=False)
        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/api/about/update/download", params={"download_url": url, "latest": "v1.2.0"})
        get_settings.cache_clear()
    finally:
        api_about._download_tasks.clear()

    assert r.status_code == 200
    assert r.json() == {
        "ok": True,
        "status": "done",
        "latest": "v1.2.0",
        "total": 1000,
        "bytes_downloaded": 1000,
        "error": "",
        "progress": 0,
    }


# ---------------------------------------------------------------------------
# POST /api/about/update/install
# ---------------------------------------------------------------------------

def test_install_rejects_when_not_ready() -> None:
    """安装包未下载完成时 install 应拒绝。"""
    api_about._download_tasks.clear()
    url = "https://github.com/wangnan05563/xianyu-hunter/releases/download/v1.2.0/XianyuHunter-Setup-v1.2.0.exe"
    # 无任务 → 未就绪
    assert api_about._validate_download_url(url) == url  # URL 本身合法
    # 用临时任务但 status=downloading
    api_about._download_tasks[url] = {"status": "downloading", "path": "/nonexistent"}
    try:
        import asyncio
        result = asyncio.run(api_about.update_install(url))
    finally:
        api_about._download_tasks.clear()
    assert result["ok"] is False
    assert "未就绪" in result["error"]


def test_install_launches_setup_when_ready(monkeypatch) -> None:
    """安装包就绪时 install 应启动安装程序并返回 ok。"""
    import asyncio
    from unittest.mock import patch
    import tempfile, os, pathlib

    url = "https://github.com/wangnan05563/xianyu-hunter/releases/download/v1.2.0/XianyuHunter-Setup-v1.2.0.exe"
    # 创建临时安装包文件
    tmpdir = tempfile.mkdtemp()
    setup_path = os.path.join(tmpdir, "XianyuHunter-Setup-v1.2.0.exe")
    pathlib.Path(setup_path).write_bytes(b"MZ")

    api_about._download_tasks[url] = {"status": "done", "path": setup_path}
    try:
        with patch("xianyu_hunter.web.routes.api_about.subprocess.Popen") as mock_popen:
            mock_popen.return_value = None
            result = asyncio.run(api_about.update_install(url))
        assert result["ok"] is True
        assert "安装程序已启动" in result["message"]
        # 校验静默安装参数
        args = mock_popen.call_args[0][0]
        assert setup_path in args[0]
        assert "/VERYSILENT" in args
        assert "/SP-" in args
    finally:
        api_about._download_tasks.clear()
        # 先删文件再删目录（否则目录非空抛 WinError 145）
        if os.path.exists(setup_path):
            os.remove(setup_path)
        os.rmdir(tmpdir)