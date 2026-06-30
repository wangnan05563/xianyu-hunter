"""About API 单元测试：覆盖端点注册、字段契约、认证白名单、_build_info 兜底、
GitHub Releases API 集成、缓存、错误降级、版本比较。

为什么单独测试：About 端点返回系统元信息（版本/构建日期/Git SHA），
是 PWA 更新检查和用户诊断的关键依赖，需要保证字段稳定与异常容错。
"""
from __future__ import annotations

import sys
import time
import types
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from xianyu_hunter.config import get_settings
from xianyu_hunter.web.app import app
from xianyu_hunter.web.middleware.auth import PUBLIC_PREFIXES
from xianyu_hunter.web.routes import api_about


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def client(monkeypatch) -> TestClient:
    """构造 TestClient：注入测试 token，避免读取真实 .env。

    为什么 monkeypatch get_settings：auth 中间件内部调用 get_settings().web_token
    做 hmac 比较，未注入时会读到空字符串，导致非 PUBLIC 路径全部 401。
    """
    from xianyu_hunter.config import Settings
    test_settings = Settings(web_token="test-token-about-api")
    monkeypatch.setattr("xianyu_hunter.config.get_settings", lambda: test_settings)
    monkeypatch.setattr(
        "xianyu_hunter.web.app.get_settings",
        lambda: test_settings,
        raising=False,
    )
    yield TestClient(app, raise_server_exceptions=False)
    # 清理 LRU 缓存，避免污染后续测试
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def reset_cache():
    """每个测试前清空 check-update 缓存，避免测试间相互污染。

    为什么 autouse：缓存是进程级单例，上一个测试写入的结果会影响下一个测试的
    「缓存命中」分支，导致断言错乱。
    """
    api_about._reset_cache_for_test()
    yield
    api_about._reset_cache_for_test()


@pytest.fixture
def mock_build_info(monkeypatch):
    """注入 fake _build_info，让 current 版本可控。"""
    import xianyu_hunter
    fake = types.ModuleType("xianyu_hunter._build_info")
    fake.__version__ = "1.0.0"  # type: ignore[attr-defined]
    fake.build_date = "2026-06-28"  # type: ignore[attr-defined]
    fake.git_sha = "abc1234"  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "xianyu_hunter._build_info", fake)
    monkeypatch.setattr(xianyu_hunter, "_build_info", fake, raising=False)
    return fake


def _mock_github_response(
    *,
    status_code: int = 200,
    tag_name: str = "v1.0.0",
    html_url: str = "https://github.com/wangnan05563/xianyu-hunter/releases/tag/v1.0.0",
    published_at: str = "2026-06-01T00:00:00Z",
    name: str = "Release 1.0.0",
    rate_limit_remaining: str | None = None,
) -> MagicMock:
    """构造模拟的 httpx.Response。"""
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = {}
    if rate_limit_remaining is not None:
        resp.headers["X-RateLimit-Remaining"] = rate_limit_remaining
    if status_code == 200:
        resp.json.return_value = {
            "tag_name": tag_name,
            "html_url": html_url,
            "published_at": published_at,
            "name": name,
        }
    return resp


# ---------------------------------------------------------------------------
# 路由注册
# ---------------------------------------------------------------------------

def test_about_routes_registered() -> None:
    """两个端点应注册到 app.routes，且路径与契约一致。"""
    paths = {getattr(route, "path", "") for route in app.routes}
    assert "/api/about" in paths
    assert "/api/about/check-update" in paths


def test_about_router_prefix_correct() -> None:
    """router 前缀必须是 /api/about，单点入口覆盖两个端点。"""
    assert api_about.router.prefix == "/api/about"


# ---------------------------------------------------------------------------
# 认证白名单
# ---------------------------------------------------------------------------

def test_about_in_public_prefixes() -> None:
    """PUBLIC_PREFIXES 应包含 /api/about，使两个端点都免认证。

    为什么用前缀而非完整路径：/api/about 单条前缀同时覆盖
    /api/about 和 /api/about/check-update，避免重复维护。
    """
    assert "/api/about" in PUBLIC_PREFIXES


def test_about_endpoints_accessible_without_token(client: TestClient) -> None:
    """无 token 请求两个端点都应返回 200，验证白名单实际生效。"""
    r1 = client.get("/api/about")
    assert r1.status_code == 200
    r2 = client.get("/api/about/check-update")
    assert r2.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/about 字段契约
# ---------------------------------------------------------------------------

def test_get_about_returns_required_fields(client: TestClient) -> None:
    """/api/about 必须返回 6 个字段：product/version/build_date/git_sha/python/platform。"""
    r = client.get("/api/about")
    assert r.status_code == 200
    data = r.json()
    expected_keys = {"product", "version", "build_date", "git_sha", "python", "platform"}
    assert set(data.keys()) == expected_keys


def test_get_about_product_name_is_xianyu_hunter(client: TestClient) -> None:
    """product 字段固定为「闲鱼猎人」，与 Swagger UI 品牌一致。"""
    data = client.get("/api/about").json()
    assert data["product"] == "闲鱼猎人"


def test_get_about_python_version_format(client: TestClient) -> None:
    """python 字段应为「主.次.微」格式（来自 sys.version_info）。"""
    data = client.get("/api/about").json()
    expected = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    assert data["python"] == expected


def test_get_about_platform_is_lowercase(client: TestClient) -> None:
    """platform 字段应为小写系统名（Windows → windows），与 Swagger UI 顶栏判断一致。"""
    import platform as _platform
    data = client.get("/api/about").json()
    assert data["platform"] == _platform.system().lower()


# ---------------------------------------------------------------------------
# _build_info 兜底逻辑
# ---------------------------------------------------------------------------

def test_get_about_falls_back_to_unknown_when_build_info_missing(
    client: TestClient, monkeypatch
) -> None:
    """_build_info 模块缺失时，version/build_date/git_sha 应为 'unknown'。

    为什么测试这个：scripts/build_info.py 在开发环境可能未执行，
    直接 from xianyu_hunter import _build_info 会 ImportError。
    _safe_build_info 必须兜底，避免 500 影响前端 PWA 检查更新。

    为什么同时清理 sys.modules 和包属性：`from xianyu_hunter import _build_info`
    先查 xianyu_hunter.__dict__['_build_info']（包属性路径），未命中才走 import
    子模块路径。只 patch sys.modules 不够，必须同时删除包属性。
    """
    import xianyu_hunter
    # sys.modules 设为 None 触发 ImportError；包属性删除强制走 import 路径
    monkeypatch.setitem(sys.modules, "xianyu_hunter._build_info", None)
    monkeypatch.delattr(xianyu_hunter, "_build_info", raising=False)

    data = client.get("/api/about").json()
    assert data["version"] == "unknown"
    assert data["build_date"] == "unknown"
    assert data["git_sha"] == "unknown"


def test_get_about_reads_build_info_when_present(
    client: TestClient, monkeypatch
) -> None:
    """_build_info 存在时应正确读取 __version__/build_date/git_sha。"""
    import xianyu_hunter
    fake_module = types.ModuleType("xianyu_hunter._build_info")
    fake_module.__version__ = "9.9.9"  # type: ignore[attr-defined]
    fake_module.build_date = "2026-01-01"  # type: ignore[attr-defined]
    fake_module.git_sha = "deadbeef"  # type: ignore[attr-defined]
    # 同时 patch sys.modules 和包属性，确保 from ... import 拿到 fake_module
    monkeypatch.setitem(sys.modules, "xianyu_hunter._build_info", fake_module)
    monkeypatch.setattr(xianyu_hunter, "_build_info", fake_module, raising=False)

    data = client.get("/api/about").json()
    assert data["version"] == "9.9.9"
    assert data["build_date"] == "2026-01-01"
    assert data["git_sha"] == "deadbeef"


def test_get_about_partial_build_info_falls_back_per_field(
    client: TestClient, monkeypatch
) -> None:
    """_build_info 部分字段缺失时，缺失字段应为 'unknown'，其它字段正常返回。"""
    import xianyu_hunter
    fake_module = types.ModuleType("xianyu_hunter._build_info")
    fake_module.__version__ = "1.2.3"  # type: ignore[attr-defined]
    # 故意不设置 build_date 和 git_sha
    monkeypatch.setitem(sys.modules, "xianyu_hunter._build_info", fake_module)
    monkeypatch.setattr(xianyu_hunter, "_build_info", fake_module, raising=False)

    data = client.get("/api/about").json()
    assert data["version"] == "1.2.3"
    assert data["build_date"] == "unknown"
    assert data["git_sha"] == "unknown"


# ---------------------------------------------------------------------------
# 版本号比较（单元测试）
# ---------------------------------------------------------------------------

class TestVersionComparison:
    """_parse_version / _is_newer 单元测试。"""

    def test_parse_version_with_v_prefix(self) -> None:
        assert api_about._parse_version("v1.2.3") == (1, 2, 3)

    def test_parse_version_without_v_prefix(self) -> None:
        assert api_about._parse_version("1.2.3") == (1, 2, 3)

    def test_parse_version_with_prerelease_suffix(self) -> None:
        # 'v1.2.3-beta' 应解析为 (1, 2, 3)，后缀忽略
        assert api_about._parse_version("v1.2.3-beta") == (1, 2, 3)

    def test_parse_version_unknown_returns_none(self) -> None:
        assert api_about._parse_version("unknown") is None

    def test_parse_version_empty_returns_none(self) -> None:
        assert api_about._parse_version("") is None

    def test_parse_version_non_semver_returns_none(self) -> None:
        assert api_about._parse_version("main") is None

    def test_is_newer_true_when_latest_higher(self) -> None:
        assert api_about._is_newer("1.0.0", "1.0.1") is True
        assert api_about._is_newer("1.0.0", "1.1.0") is True
        assert api_about._is_newer("1.0.0", "2.0.0") is True

    def test_is_newer_false_when_same(self) -> None:
        assert api_about._is_newer("1.0.0", "1.0.0") is False
        assert api_about._is_newer("v1.0.0", "1.0.0") is False

    def test_is_newer_false_when_latest_lower(self) -> None:
        assert api_about._is_newer("1.2.0", "1.1.0") is False

    def test_is_newer_false_when_current_unparseable(self) -> None:
        # current='unknown' 时保守返回 False，避免误报
        assert api_about._is_newer("unknown", "9.9.9") is False

    def test_is_newer_false_when_latest_unparseable(self) -> None:
        # latest 无效时保守返回 False
        assert api_about._is_newer("1.0.0", "main") is False


# ---------------------------------------------------------------------------
# GET /api/about/check-update 字段契约（mock GitHub API）
# ---------------------------------------------------------------------------

def test_check_update_returns_required_fields(
    client: TestClient, mock_build_info
) -> None:
    """/api/about/check-update 必须返回 6 个核心字段（published_at 为可选附加）。"""
    with patch.object(
        api_about, "_fetch_latest_release",
        new=AsyncMock(return_value={
            "tag_name": "v1.0.0",
            "html_url": "https://github.com/wangnan05563/xianyu-hunter/releases/tag/v1.0.0",
            "published_at": "2026-06-01T00:00:00Z",
            "name": "Release 1.0.0",
        })
    ):
        r = client.get("/api/about/check-update")

    assert r.status_code == 200
    data = r.json()
    expected_keys = {"current", "latest", "has_update", "release_url", "checked_at", "source"}
    assert expected_keys.issubset(set(data.keys()))


def test_check_update_has_update_true_when_latest_newer(
    client: TestClient, mock_build_info
) -> None:
    """GitHub 返回的 tag_name 比 current 高时 has_update=True。"""
    with patch.object(
        api_about, "_fetch_latest_release",
        new=AsyncMock(return_value={
            "tag_name": "v1.2.0",
            "html_url": "https://github.com/wangnan05563/xianyu-hunter/releases/tag/v1.2.0",
            "published_at": "2026-06-15T00:00:00Z",
            "name": "Release 1.2.0",
        })
    ):
        data = client.get("/api/about/check-update").json()

    assert data["has_update"] is True
    assert data["latest"] == "v1.2.0"
    assert data["current"] == "1.0.0"
    assert data["source"] == "remote"
    # has_update=True 时 release_url 应指向具体 release 页面
    assert data["release_url"] == "https://github.com/wangnan05563/xianyu-hunter/releases/tag/v1.2.0"


def test_check_update_has_update_false_when_same_version(
    client: TestClient, mock_build_info
) -> None:
    """GitHub 返回的 tag_name 与 current 相同时 has_update=False。"""
    with patch.object(
        api_about, "_fetch_latest_release",
        new=AsyncMock(return_value={
            "tag_name": "v1.0.0",
            "html_url": "https://github.com/wangnan05563/xianyu-hunter/releases/tag/v1.0.0",
            "published_at": "2026-06-01T00:00:00Z",
            "name": "Release 1.0.0",
        })
    ):
        data = client.get("/api/about/check-update").json()

    assert data["has_update"] is False
    assert data["latest"] == "v1.0.0"
    assert data["source"] == "remote"
    # has_update=False 时 release_url 指向 releases 列表页（让用户浏览所有版本）
    assert data["release_url"] == "https://github.com/wangnan05563/xianyu-hunter/releases"


def test_check_update_release_url_not_empty(
    client: TestClient, mock_build_info
) -> None:
    """release_url 即使无更新也应非空，供 UI 在 has_update=True 时直接跳转。"""
    with patch.object(
        api_about, "_fetch_latest_release",
        new=AsyncMock(return_value={
            "tag_name": "v1.0.0",
            "html_url": "https://github.com/wangnan05563/xianyu-hunter/releases/tag/v1.0.0",
            "published_at": "",
            "name": "",
        })
    ):
        data = client.get("/api/about/check-update").json()

    assert data["release_url"]
    assert data["release_url"].startswith("http")


def test_check_update_checked_at_is_iso_format(
    client: TestClient, mock_build_info
) -> None:
    """checked_at 应为 ISO 8601 格式字符串，前端可 Date.parse 解析。"""
    from datetime import datetime
    with patch.object(
        api_about, "_fetch_latest_release",
        new=AsyncMock(return_value={
            "tag_name": "v1.0.0",
            "html_url": "https://example.com",
            "published_at": "",
            "name": "",
        })
    ):
        data = client.get("/api/about/check-update").json()
    # 应能被 fromisoformat 解析（Python 3.11+ 兼容带时区的 ISO 字符串）
    datetime.fromisoformat(data["checked_at"])


def test_check_update_includes_published_at_on_success(
    client: TestClient, mock_build_info
) -> None:
    """成功响应应包含 published_at 字段，供前端展示发布时间。"""
    with patch.object(
        api_about, "_fetch_latest_release",
        new=AsyncMock(return_value={
            "tag_name": "v1.0.0",
            "html_url": "https://example.com",
            "published_at": "2026-06-01T00:00:00Z",
            "name": "",
        })
    ):
        data = client.get("/api/about/check-update").json()

    assert data["published_at"] == "2026-06-01T00:00:00Z"


# ---------------------------------------------------------------------------
# 错误降级（mock GitHub API 各种失败场景）
# ---------------------------------------------------------------------------

def test_check_update_falls_back_on_404_no_release(
    client: TestClient, mock_build_info
) -> None:
    """GitHub 返回 404（仓库无 release）时降级 source='local'。"""
    with patch.object(
        api_about, "_fetch_latest_release", new=AsyncMock(return_value=None)
    ):
        data = client.get("/api/about/check-update").json()

    assert data["has_update"] is False
    assert data["source"] == "local"
    assert data["latest"] == data["current"]


def test_check_update_falls_back_on_rate_limit_403(
    client: TestClient, mock_build_info
) -> None:
    """GitHub 返回 403（限速）时降级，不抛 5xx。"""
    with patch.object(
        api_about, "_fetch_latest_release", new=AsyncMock(return_value=None)
    ):
        data = client.get("/api/about/check-update").json()

    assert data["has_update"] is False
    assert data["source"] == "local"


def test_check_update_falls_back_on_server_error(
    client: TestClient, mock_build_info
) -> None:
    """GitHub 返回 5xx 时降级。"""
    with patch.object(
        api_about, "_fetch_latest_release", new=AsyncMock(return_value=None)
    ):
        data = client.get("/api/about/check-update").json()

    assert data["has_update"] is False
    assert data["source"] == "local"


def test_check_update_falls_back_on_timeout(
    client: TestClient, mock_build_info
) -> None:
    """GitHub API 超时时降级返回本地版本。"""
    with patch.object(
        api_about, "_fetch_latest_release", new=AsyncMock(return_value=None)
    ):
        data = client.get("/api/about/check-update").json()

    assert data["has_update"] is False
    assert data["source"] == "local"


def test_check_update_falls_back_on_network_error(
    client: TestClient, mock_build_info
) -> None:
    """网络错误时降级返回本地版本。"""
    with patch.object(
        api_about, "_fetch_latest_release", new=AsyncMock(return_value=None)
    ):
        data = client.get("/api/about/check-update").json()

    assert data["has_update"] is False
    assert data["source"] == "local"


# ---------------------------------------------------------------------------
# _fetch_latest_release 实际行为测试（mock httpx）
# ---------------------------------------------------------------------------

def test_fetch_latest_release_success() -> None:
    """成功响应应正确解析 tag_name/html_url/published_at。"""
    mock_resp = _mock_github_response(
        tag_name="v1.5.0",
        html_url="https://github.com/wangnan05563/xianyu-hunter/releases/tag/v1.5.0",
        published_at="2026-06-20T00:00:00Z",
    )
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_client):
        import asyncio
        result = asyncio.run(api_about._fetch_latest_release())

    assert result is not None
    assert result["tag_name"] == "v1.5.0"
    assert result["html_url"] == "https://github.com/wangnan05563/xianyu-hunter/releases/tag/v1.5.0"
    assert result["published_at"] == "2026-06-20T00:00:00Z"


def test_fetch_latest_release_404_returns_none() -> None:
    """404（仓库无 release）应返回 None。"""
    mock_resp = _mock_github_response(status_code=404)
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_client):
        import asyncio
        result = asyncio.run(api_about._fetch_latest_release())

    assert result is None


def test_fetch_latest_release_403_returns_none() -> None:
    """403（限速）应返回 None。"""
    mock_resp = _mock_github_response(status_code=403, rate_limit_remaining="0")
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_client):
        import asyncio
        result = asyncio.run(api_about._fetch_latest_release())

    assert result is None


def test_fetch_latest_release_500_returns_none() -> None:
    """500 服务器错误应返回 None。"""
    mock_resp = _mock_github_response(status_code=500)
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_client):
        import asyncio
        result = asyncio.run(api_about._fetch_latest_release())

    assert result is None


def test_fetch_latest_release_timeout_returns_none() -> None:
    """超时应返回 None 而非抛异常。"""
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

    with patch("httpx.AsyncClient", return_value=mock_client):
        import asyncio
        result = asyncio.run(api_about._fetch_latest_release())

    assert result is None


def test_fetch_latest_release_network_error_returns_none() -> None:
    """网络错误应返回 None 而非抛异常。"""
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("connection refused"))

    with patch("httpx.AsyncClient", return_value=mock_client):
        import asyncio
        result = asyncio.run(api_about._fetch_latest_release())

    assert result is None


def test_fetch_latest_release_missing_tag_name_returns_none() -> None:
    """响应缺少 tag_name 字段应视为无效，返回 None。"""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {}
    mock_resp.json.return_value = {"html_url": "https://example.com"}  # 缺 tag_name
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_client):
        import asyncio
        result = asyncio.run(api_about._fetch_latest_release())

    assert result is None


# ---------------------------------------------------------------------------
# 缓存行为
# ---------------------------------------------------------------------------

def test_check_update_caches_successful_response(
    client: TestClient, mock_build_info
) -> None:
    """5 分钟内连续两次请求应只调用一次 _fetch_latest_release。"""
    mock_fetch = AsyncMock(return_value={
        "tag_name": "v1.0.0",
        "html_url": "https://example.com",
        "published_at": "",
        "name": "",
    })
    with patch.object(api_about, "_fetch_latest_release", new=mock_fetch):
        client.get("/api/about/check-update")
        client.get("/api/about/check-update")

    assert mock_fetch.call_count == 1, "缓存命中时不应重复调用 GitHub API"


def test_check_update_does_not_cache_failure(
    client: TestClient, mock_build_info
) -> None:
    """失败响应不应缓存，下次请求应重新调用 _fetch_latest_release。"""
    mock_fetch = AsyncMock(return_value=None)
    with patch.object(api_about, "_fetch_latest_release", new=mock_fetch):
        client.get("/api/about/check-update")
        client.get("/api/about/check-update")

    assert mock_fetch.call_count == 2, "失败不应缓存，每次都应重试"


def test_check_update_cache_invalidated_when_current_version_changes(
    client: TestClient, mock_build_info, monkeypatch
) -> None:
    """current 版本变化（构建后升级）时缓存应失效，重新发起 GitHub 请求。"""
    import xianyu_hunter
    mock_fetch = AsyncMock(return_value={
        "tag_name": "v1.0.0",
        "html_url": "https://example.com",
        "published_at": "",
        "name": "",
    })
    with patch.object(api_about, "_fetch_latest_release", new=mock_fetch):
        # 第一次请求：current=1.0.0
        client.get("/api/about/check-update")
        # 模拟版本升级到 1.5.0
        mock_build_info.__version__ = "1.5.0"
        # 强制 _safe_build_info 重新读取（fake_module 是同一个对象，属性已改）
        client.get("/api/about/check-update")

    assert mock_fetch.call_count == 2, "版本变化应使缓存失效"


def test_check_update_cache_expires_after_ttl(
    client: TestClient, mock_build_info, monkeypatch
) -> None:
    """超过 TTL 后缓存应过期，重新调用 GitHub API。"""
    mock_fetch = AsyncMock(return_value={
        "tag_name": "v1.0.0",
        "html_url": "https://example.com",
        "published_at": "",
        "name": "",
    })
    # 第一次调用后立即写入 _cache['fetched_at']
    with patch.object(api_about, "_fetch_latest_release", new=mock_fetch):
        client.get("/api/about/check-update")

    # 把 fetched_at 调到 10 分钟前，模拟 TTL 过期
    api_about._cache["fetched_at"] = time.monotonic() - 600

    with patch.object(api_about, "_fetch_latest_release", new=mock_fetch):
        client.get("/api/about/check-update")

    assert mock_fetch.call_count == 2, "TTL 过期后应重新调用"


# ---------------------------------------------------------------------------
# 隐私与安全
# ---------------------------------------------------------------------------

def test_fetch_latest_release_does_not_send_auth_token() -> None:
    """HTTP 请求头不应包含任何 Authorization 或 token，保护用户隐私。"""
    mock_resp = _mock_github_response()
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_client) as client_cls:
        import asyncio
        asyncio.run(api_about._fetch_latest_release())

    # 检查传给 AsyncClient 的 headers 不含敏感字段
    _, kwargs = client_cls.call_args
    headers = kwargs.get("headers", {})
    assert "Authorization" not in headers, "不应对 GitHub API 发送认证头"
    assert "token" not in str(headers).lower(), "headers 中不应包含任何 token"


def test_release_url_always_points_to_github() -> None:
    """release_url 应始终指向 GitHub 仓库，不指向任何第三方域名。"""
    # 此约束由 _RELEASE_URL 常量保证，UI 跳转链接可信
    assert api_about._RELEASE_URL.startswith("https://github.com/")
    assert api_about._RELEASES_API.startswith("https://api.github.com/")
