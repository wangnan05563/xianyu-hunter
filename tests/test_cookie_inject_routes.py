"""Cookie 注入路由（web/routes/cookie_inject.py）单元与端点测试

覆盖两块：
1. 纯函数：cookie 字符串/Netscape/JSON/Header 解析、域名过滤、Chrome Cookie DB 查询的
   候选构建/单库尝试/JSON 与 CDP 降级筛选。
2. 六个端点：POST /api/auth/cookie、/cookie/file、/cookie/path，
   GET /cookie/domains、/cookie/saved、/cookie/fetch-keys。

隔离策略：不触发真实浏览器注入、不写开发机 browser-data、不签发真实会话；
CookieStore JSON 由 tests/conftest.py 的 isolate_cookie_json 落到 tmp_path。
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from xianyu_hunter.web.routes import cookie_inject as ci

_NETSCAPE_LINE = "\t".join(
    [".goofish.com", "TRUE", "/", "TRUE", "1893456000", "unb", "952712345"]
)
_HEADER_COOKIE = "unb=952712345; cna=track123"


def _make_cookie_db(path: Path, rows: list[tuple[str, str, str, bytes | None]]) -> Path:
    """建一个最小 Chrome Cookies 库（字段够 _query_cookie_db 用）"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(path)) as conn:
        conn.execute(
            "CREATE TABLE cookies (host_key TEXT, name TEXT, value TEXT, "
            "encrypted_value BLOB, path TEXT, expires_utc INTEGER, is_secure INTEGER, "
            "is_httponly INTEGER, creation_utc INTEGER, last_access_utc INTEGER)"
        )
        conn.executemany(
            "INSERT INTO cookies (host_key, name, value, encrypted_value, path, "
            "expires_utc, is_secure, is_httponly, creation_utc, last_access_utc) "
            "VALUES (?, ?, ?, ?, '/', 0, 0, 0, 0, 0)",
            rows,
        )
    return path


def _async_return(value):
    async def _inner(*args, **kwargs):
        return value
    return _inner


async def _browser_ok(cookies):
    return len(cookies), [], "browser_context"


async def _browser_unavailable(cookies):
    raise RuntimeError("browser unavailable")


def _sqlite_unavailable(cookie_db, cookies):
    raise RuntimeError("sqlite unavailable")


async def _async_worker_inject(*args, **kwargs):
    return True


# ============== 纯函数 ==============


def test_parse_cookie_string_to_pairs_handles_newline_and_semicolon() -> None:
    text = "unb=952712345; cna=track123\ncookie2=abcdef;\n  ;;name=\n =value\nnoeq"
    assert ci._parse_cookie_string_to_pairs(text) == [
        ("unb", "952712345"), ("cna", "track123"), ("cookie2", "abcdef"),
    ]


def test_parse_netscape_cookies_skips_comments_and_short_lines() -> None:
    text = "\n".join([
        "# Netscape HTTP Cookie File",
        "",
        _NETSCAPE_LINE,
        "too\tfew\tfields",
        "\t".join([".goofish.com", "TRUE", "", "TRUE", "0", "cna", "v"]),
        "\t".join([".goofish.com", "TRUE", "/", "TRUE", "0", "empty", ""]),
    ])
    cookies = ci._parse_netscape_cookies(text)
    assert [c["name"] for c in cookies] == ["unb", "cna"]
    assert cookies[1]["path"] == "/"  # 空 path 补默认


def test_parse_json_cookies_supports_array_and_wrapped_object() -> None:
    arr = ci._parse_json_cookies(json.dumps([
        {"name": "unb", "value": "952712345", "domain": ".goofish.com"},
        {"name": "dot_only", "value": "v"},
        {"name": "no_value", "value": ""},
        "not-a-dict",
    ]))
    assert [c["name"] for c in arr] == ["unb", "dot_only"]
    assert arr[1]["domain"] == ci._DEFAULT_DOMAIN

    for key in ("cookies", "data", "items"):
        wrapped = ci._parse_json_cookies(json.dumps({key: [{"name": "unb", "value": "1"}]}))
        assert [c["name"] for c in wrapped] == ["unb"], key

    assert ci._parse_json_cookies("{not json") == []
    assert ci._parse_json_cookies(json.dumps({"foo": []})) == []
    assert ci._parse_json_cookies(json.dumps("scalar")) == []


def test_parse_header_cookies_skips_junk() -> None:
    cookies = ci._parse_header_cookies("a=1; broken; b = 2\n;c=3")
    assert [(c["name"], c["value"]) for c in cookies] == [("a", "1"), ("b", "2"), ("c", "3")]
    assert all(c["domain"] == ci._DEFAULT_DOMAIN for c in cookies)


def test_parse_cookie_file_priority_netscape_over_header() -> None:
    mixed = _NETSCAPE_LINE + "\n" + _HEADER_COOKIE
    assert [c["name"] for c in ci._parse_cookie_file(mixed)] == ["unb"]
    assert [c["name"] for c in ci._parse_cookie_file(_HEADER_COOKIE)] == ["unb", "cna"]
    assert ci._parse_cookie_file("啥也不是") == []


def test_filter_goofish_cookies_keeps_known_and_blank_domains() -> None:
    kept = ci._filter_goofish_cookies([
        {"name": "a", "domain": ".goofish.com"},
        {"name": "b", "domain": "h5api.m.taobao.com"},
        {"name": "c", "domain": ".alipay.com"},
        {"name": "d", "domain": ""},
        {"name": "e"},
        {"name": "f", "domain": ci._DEFAULT_DOMAIN},
        {"name": "x", "domain": "example.com"},
    ])
    assert [c["name"] for c in kept] == ["a", "b", "c", "d", "e", "f"]


def test_process_cookie_row_plaintext_v20_and_duplicates() -> None:
    result: dict[str, str] = {}
    assert ci._process_cookie_row("unb", "952712345", None, result) is False
    assert result == {"unb": "952712345"}
    # 同名已存在 → 直接跳过，即使新值不同
    assert ci._process_cookie_row("unb", "other", None, result) is False
    # 空值且无 encrypted_value
    assert ci._process_cookie_row("cna", "", None, result) is False
    # v20 加密 → 标记
    assert ci._process_cookie_row("cookie2", "", b"v20abc", result) is True
    # 旧格式（v10）→ 不标记
    assert ci._process_cookie_row("sgcookie", "", b"v10abc", result) is False


def test_cookies_table_exists_on_empty_and_corrupt_db(tmp_path: Path) -> None:
    with sqlite3.connect(str(tmp_path / "empty.db")) as conn:
        assert ci._cookies_table_exists(conn) is False
        conn.execute("CREATE TABLE cookies (name TEXT)")
        assert ci._cookies_table_exists(conn) is True

    # 文件损坏 → DatabaseError 由上层 _try_single_cookie_candidate 兜底转为用户提示，
    # 本函数只吞 OperationalError
    corrupt = tmp_path / "corrupt.db"
    corrupt.write_bytes(b"not a database at all")
    with sqlite3.connect(str(corrupt)) as conn:
        with pytest.raises(sqlite3.DatabaseError):
            ci._cookies_table_exists(conn)


def test_query_cookie_db_filters_host_and_detects_v20(tmp_path: Path) -> None:
    db = _make_cookie_db(tmp_path / "Cookies", [
        ("h5api.m.taobao.com", "unb", "952712345", None),
        (".goofish.com", "cna", "", b"v20xxx"),
        ("example.com", "unb", "should-be-filtered", None),
    ])
    result, v20 = ci._query_cookie_db(db, ["unb", "cna", "missing"])
    assert result == {"unb": "952712345"}
    assert v20 is True


def test_query_cookie_db_without_table_returns_empty(tmp_path: Path) -> None:
    db = tmp_path / "no_table.db"
    with sqlite3.connect(str(db)) as conn:
        conn.execute("CREATE TABLE other (x)")
    result, v20 = ci._query_cookie_db(db, ["unb"])
    assert result == {} and v20 is False


def test_try_single_cookie_candidate_missing_and_broken(tmp_path: Path) -> None:
    assert ci._try_single_cookie_candidate(tmp_path / "nope.db", False, ["unb"])[0] is None
    assert ci._try_single_cookie_candidate(tmp_path / "nope.db", False, ["unb"])[2] is ci._LAST_ERROR_NO_UPDATE

    broken = tmp_path / "broken.db"
    broken.write_bytes(b"garbage")
    result, v20, err = ci._try_single_cookie_candidate(broken, False, ["unb"])
    assert result is None and v20 is False and isinstance(err, str)


def test_try_single_cookie_candidate_no_such_table_is_silent(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "Cookies"
    with sqlite3.connect(str(db)) as conn:
        conn.execute("CREATE TABLE other (x)")
    # 强制认为有表，让查询抛 "no such table"，走静默分支（不向用户展示技术错误）
    monkeypatch.setattr(ci, "_cookies_table_exists", lambda conn: True)
    result, v20, err = ci._try_single_cookie_candidate(db, False, ["unb"])
    assert result is None and v20 is False and err is None


def test_try_single_cookie_candidate_operational_error_messages(tmp_path: Path, monkeypatch) -> None:
    db = _make_cookie_db(tmp_path / "Best Profile" / "Default" / "Network" / "Cookies", [])

    def raise_locked(conn_or_path, keys):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(ci, "_query_cookie_db", raise_locked)
    _, _, err = ci._try_single_cookie_candidate(db, False, ["unb"])
    assert "数据库被锁定" in err and "Default" in err

    def raise_unopenable(conn_or_path, keys):
        raise sqlite3.OperationalError("unable to open database file")

    monkeypatch.setattr(ci, "_query_cookie_db", raise_unopenable)
    _, _, err = ci._try_single_cookie_candidate(db, False, ["unb"])
    assert "数据库被锁定" in err

    def raise_permission(conn_or_path, keys):
        raise PermissionError("denied")

    monkeypatch.setattr(ci, "_query_cookie_db", raise_permission)
    _, _, err = ci._try_single_cookie_candidate(db, False, ["unb"])
    assert "文件被占用" in err

    def raise_other(conn_or_path, keys):
        raise ValueError("boom")

    monkeypatch.setattr(ci, "_query_cookie_db", raise_other)
    _, _, err = ci._try_single_cookie_candidate(db, False, ["unb"])
    assert err == "boom"


def test_try_single_cookie_candidate_with_copy(tmp_path: Path) -> None:
    db = _make_cookie_db(tmp_path / "Edge" / "Default" / "Network" / "Cookies", [
        (".goofish.com", "unb", "952712345", None),
    ])
    result, v20, err = ci._try_single_cookie_candidate(db, True, ["unb"])
    assert result == {"unb": "952712345"}
    assert v20 is False and err is ci._LAST_ERROR_NO_UPDATE


def test_copy_locked_cookie_file_copies_content(tmp_path: Path) -> None:
    src = tmp_path / "src.db"
    src.write_bytes(b"x" * 1000)
    dst = tmp_path / "dst.db"
    assert ci._copy_locked_cookie_file(str(src), str(dst)) is True
    assert dst.read_bytes() == b"x" * 1000
    # 源不存在 → CreateFileW 失败，回退 shutil 也失败
    assert ci._copy_locked_cookie_file(str(tmp_path / "missing.db"), str(tmp_path / "o.db")) is False


def test_cleanup_temp_db_copy(tmp_path: Path) -> None:
    f = tmp_path / "tmp.db"
    f.write_bytes(b"1")
    ci._cleanup_temp_db_copy(str(f))
    assert not f.exists()
    ci._cleanup_temp_db_copy(None)  # 不抛
    ci._cleanup_temp_db_copy(str(f))  # 已删除也不抛


def test_list_and_build_cookie_db_candidates(tmp_path: Path, monkeypatch) -> None:
    assert ci._list_chrome_profile_cookie_dbs("") == []
    # 无 Chrome 目录
    assert ci._list_chrome_profile_cookie_dbs(str(tmp_path / "none")) == []

    base = tmp_path / "lad" / "Google" / "Chrome" / "User Data"
    _make_cookie_db(base / "Default" / "Network" / "Cookies", [])
    _make_cookie_db(base / "Profile 1" / "Network" / "Cookies", [])
    (base / ".tmp" / "Network").mkdir(parents=True)   # 系统目录，跳过
    (base / "NoCookie" / "Network").mkdir(parents=True)

    profiles = ci._list_chrome_profile_cookie_dbs(str(tmp_path / "lad"))
    assert [(p.parent.parent.name, copy) for p, copy in profiles] == [("Default", False), ("Profile 1", False)]

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "lad"))
    monkeypatch.setattr(ci, "get_browser_data_dir", lambda udd: tmp_path / "bd")
    candidates = ci._build_cookie_db_candidates(SimpleNamespace(browser=SimpleNamespace(user_data_dir="u")))
    assert [copy for _, copy in candidates] == [False, False, True, False]
    assert candidates[-1][0] == tmp_path / "bd" / "Default" / "Network" / "Cookies"
    assert "Edge" in str(candidates[-2][0])


def test_build_cookie_db_candidates_without_localappdata(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(ci, "get_browser_data_dir", lambda udd: tmp_path / "bd")
    candidates = ci._build_cookie_db_candidates(SimpleNamespace(browser=SimpleNamespace(user_data_dir="u")))
    assert len(candidates) == 1  # 仅项目 browser-data


def test_try_sqlite_cookie_candidates_success_and_total_failure(tmp_path: Path) -> None:
    good = _make_cookie_db(tmp_path / "Cookies", [(".goofish.com", "unb", "952712345", None)])
    resp, last_error, v20 = ci._try_sqlite_cookie_candidates(
        [(tmp_path / "missing.db", False), (good, False)], ["unb", "cna"],
    )
    assert resp is not None and last_error is None and v20 is False
    data = json.loads(resp.body)
    assert data["ok"] is True and data["found"] == ["unb"] and data["missing"] == ["cna"]

    broken = tmp_path / "broken.db"
    broken.write_bytes(b"garbage")
    resp2, last_error2, v20b = ci._try_sqlite_cookie_candidates([(broken, False)], ["unb"])
    assert resp2 is None and isinstance(last_error2, str) and v20b is False


def test_filter_json_cookies_for_fetch() -> None:
    cookies = [
        {"name": "unb", "value": "952712345", "domain": ".goofish.com"},
        {"name": "unb", "value": "dup", "domain": ".goofish.com"},
        {"name": "cna", "value": "track123", "domain": ".taobao.com"},
        {"name": "unb", "value": "123456", "domain": ".goofish.com"},
        {"name": "other", "value": "x", "domain": ".goofish.com"},
        {"name": "unb", "value": "952712345", "domain": "example.com"},
        {"name": "sgcookie", "value": "abc", "domain": ".goofish.com"},
    ]
    assert ci._filter_json_cookies_for_fetch(cookies, ["unb", "cna", "sgcookie"]) == {
        "unb": "952712345", "cna": "track123",
    }


def test_filter_pw_cookies_for_cdp() -> None:
    pw = [
        {"name": "unb", "value": "952712345", "domain": ".goofish.com"},
        {"name": "unb", "value": "dup", "domain": ".goofish.com"},
        {"name": "cna", "value": "track123", "domain": "h5.m.taobao.com"},
        {"name": "unb", "value": "x", "domain": "example.com"},
    ]
    assert ci._filter_pw_cookies_for_cdp(pw, ["unb", "cna"]) == {
        "unb": "952712345", "cna": "track123",
    }


@pytest.mark.parametrize("browser, expected", [
    (None, "Web 进程未启动浏览器"),
    (SimpleNamespace(_context=None), "浏览器 context 未初始化"),
    (SimpleNamespace(_context=object()), "CDP 浏览器已连接"),
])
def test_build_fetch_keys_failure_response_browser_state(browser, expected) -> None:
    resp = ci._build_fetch_keys_failure_response(["unb"], True, "上一条错误", SimpleNamespace(browser=browser))
    data = json.loads(resp.body)
    assert data["ok"] is False and data["cookies"] == {}
    assert "v20" in data["hint"] and expected in data["hint"] and "上一条错误" in data["hint"]
    assert "unb" in data["error"]


# ============== 注入实现与降级分支 ==============


def test_inject_via_browser_success_and_verify_failure(monkeypatch) -> None:
    browser = MagicMock()
    browser._context = object()
    browser.add_cookies = AsyncMock(return_value=True)
    monkeypatch.setattr(
        "xianyu_hunter.web.deps.get_container",
        lambda: SimpleNamespace(browser=browser),
    )

    injected, errors, method = asyncio.run(ci._inject_via_browser([("unb", "1"), ("cna", "2")]))
    assert (injected, errors, method) == (2, [], "browser_context")
    sent = browser.add_cookies.call_args[0][0]
    assert len(sent) == 2 * len(ci._INJECT_DOMAINS)
    assert {c["domain"] for c in sent} == set(ci._INJECT_DOMAINS)

    browser.add_cookies = AsyncMock(return_value=False)
    injected, errors, method = asyncio.run(ci._inject_via_browser([("unb", "1")]))
    assert injected == 0 and method == "browser_context"
    assert errors and "验证未通过" in errors[0]


def test_inject_via_browser_without_context_raises(monkeypatch) -> None:
    monkeypatch.setattr(
        "xianyu_hunter.web.deps.get_container",
        lambda: SimpleNamespace(browser=None),
    )
    with pytest.raises(RuntimeError):
        asyncio.run(ci._inject_via_browser([("unb", "1")]))


def test_inject_to_sqlite_writes_all_inject_domains(tmp_path: Path) -> None:
    db = tmp_path / "Cookies"
    injected, errors = ci._inject_to_sqlite(db, [("unb", "952712345"), ("cna", "track123")])
    assert (injected, errors) == (2, [])
    with sqlite3.connect(str(db)) as conn:
        rows = conn.execute("SELECT host_key, name FROM cookies").fetchall()
    assert len(rows) == 2 * len(ci._INJECT_DOMAINS)
    assert {h for h, _ in rows} == set(ci._INJECT_DOMAINS)


def test_parse_cookie_file_recognizes_json_object() -> None:
    text = json.dumps({"cookies": [{"name": "unb", "value": "952712345"}]})
    assert [c["name"] for c in ci._parse_cookie_file(text)] == ["unb"]


def test_do_inject_cookies_rejects_empty_list() -> None:
    data = json.loads(asyncio.run(ci._do_inject_cookies([])).body)
    assert data == {"ok": False, "error": "未找到有效的闲鱼 Cookie"}


def test_do_inject_cookies_keeps_original_when_filter_empties(
    tmp_path: Path, monkeypatch,
) -> None:
    monkeypatch.setattr(ci, "get_browser_data_dir", lambda udd: tmp_path / "bd")
    monkeypatch.setattr(ci, "_inject_via_browser", _browser_ok)
    monkeypatch.setattr(ci, "_identify_user_from_cookies", lambda cookies: "user_a")
    cookies = [{"name": "unb", "value": "952712345", "domain": "example.com", "path": "/"}]
    data = json.loads(asyncio.run(ci._do_inject_cookies(cookies)).body)
    assert data["ok"] is True and data["injected"] == 1
    assert data["total_parsed"] == 1


def test_do_inject_cookies_total_failure(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(ci, "get_browser_data_dir", lambda udd: tmp_path / "bd")
    monkeypatch.setattr(ci, "_inject_via_browser", _browser_unavailable)
    monkeypatch.setattr(ci, "_inject_to_sqlite", _sqlite_unavailable)
    fake_store = MagicMock()
    fake_store.merge_cookies.return_value = False
    monkeypatch.setattr(ci, "get_cookie_store", lambda: fake_store)
    cookies = [{"name": "unb", "value": "952712345", "domain": ".goofish.com", "path": "/"}]
    data = json.loads(asyncio.run(ci._do_inject_cookies(cookies)).body)
    assert data["ok"] is False
    assert "browser unavailable" in data["error"]
    assert "浏览器已关闭" in data["hint"]


def test_import_file_without_filename(client: TestClient) -> None:
    # httpx 的 multipart 会把空文件名转成普通字段，这里直接调用端点函数构造无文件名上传
    import io

    from fastapi import UploadFile

    upload = UploadFile(file=io.BytesIO(b"x"), filename=None)
    resp = asyncio.run(ci.import_cookie_file(upload))
    assert json.loads(resp.body) == {"ok": False, "error": "未选择文件"}


def test_import_path_unrecognized_format(tmp_path: Path, client: TestClient, monkeypatch) -> None:
    class _Settings:
        project_root = tmp_path

    monkeypatch.setattr("xianyu_hunter.config.get_settings", lambda: _Settings)
    src = tmp_path / "garbage.txt"
    src.write_text("???", encoding="utf-8")
    resp = client.post("/api/auth/cookie/path", data={"file_path": str(src)})
    assert resp.json()["error"] == ci._UNRECOGNIZED_FORMAT_ERROR


def test_success_response_truncates_errors(client: TestClient, monkeypatch) -> None:
    async def _browser_with_errors(cookies):
        return len(cookies), [f"e{i}" for i in range(8)], "browser_context"

    monkeypatch.setattr(ci, "_inject_via_browser", _browser_with_errors)
    data = client.post("/api/auth/cookie", data={"cookie_string": _HEADER_COOKIE}).json()
    assert data["ok"] is True and len(data["errors"]) == 5

    data = client.post("/api/auth/cookie/file", files={
        "file": ("c.txt", _HEADER_COOKIE.encode(), "text/plain"),
    }).json()
    assert data["ok"] is True and len(data["errors"]) == 5


def test_copy_locked_cookie_file_falls_back_to_shutil(tmp_path: Path, monkeypatch) -> None:
    src = tmp_path / "src.db"
    src.write_bytes(b"payload")
    dst = tmp_path / "dst.db"

    def _no_winapi(*args, **kwargs):
        raise OSError("no winapi")

    # ctypes.WinDLL 不存在（非 Windows）或初始化失败 → 走 shutil 分支
    monkeypatch.setattr("ctypes.WinDLL", _no_winapi, raising=False)
    assert ci._copy_locked_cookie_file(str(src), str(dst)) is True
    assert dst.read_bytes() == b"payload"

    def _denied(*args, **kwargs):
        raise PermissionError("locked")

    monkeypatch.setattr("shutil.copy2", _denied)
    assert ci._copy_locked_cookie_file(str(src), str(tmp_path / "d2.db")) is False


def test_try_single_cookie_candidate_other_operational_error(tmp_path: Path, monkeypatch) -> None:
    db = _make_cookie_db(tmp_path / "Cookies", [])
    monkeypatch.setattr(
        ci, "_query_cookie_db",
        lambda *a: (_ for _ in ()).throw(sqlite3.OperationalError("disk I/O error")),
    )
    _, _, err = ci._try_single_cookie_candidate(db, False, ["unb"])
    assert err == "disk I/O error"


def test_cookies_table_exists_swallows_operational_error() -> None:
    class _Conn:
        def execute(self, *args, **kwargs):
            raise sqlite3.OperationalError("boom")

    assert ci._cookies_table_exists(_Conn()) is False


def test_fallback_to_cookie_store_json_handles_exceptions(monkeypatch) -> None:
    store = MagicMock()
    store._read_json.side_effect = RuntimeError("read failed")
    monkeypatch.setattr(ci, "get_cookie_store", lambda: store)
    assert ci._fallback_to_cookie_store_json(["unb"]) is None


def test_fallback_to_playwright_cdp_rejects_no_match_and_errors() -> None:
    browser = MagicMock()
    browser._context = object()
    browser.get_cookies = _async_return([{"name": "other", "value": "x", "domain": ".goofish.com"}])
    assert asyncio.run(ci._fallback_to_playwright_cdp(
        SimpleNamespace(browser=browser), ["unb"],
    )) is None

    browser.get_cookies = MagicMock(side_effect=RuntimeError("cdp down"))
    assert asyncio.run(ci._fallback_to_playwright_cdp(
        SimpleNamespace(browser=browser), ["unb"],
    )) is None

    assert asyncio.run(ci._fallback_to_playwright_cdp(
        SimpleNamespace(browser=None), ["unb"],
    )) is None


def test_fetch_keys_json_present_without_matching_key(client: TestClient) -> None:
    from xianyu_hunter.web.services.cookie_store import get_cookie_store

    assert get_cookie_store().merge_cookies(
        [{"name": "cna", "value": "track123", "domain": ".goofish.com"}],
        user_id="default",
    ) is True
    data = client.get("/api/auth/cookie/fetch-keys", params={"keys": "unb"}).json()
    assert data["ok"] is False
    assert "未找到闲鱼 Cookie（unb）" in data["error"]


# ============== 端点 ==============


@pytest.fixture
def container() -> SimpleNamespace:
    """默认无浏览器的容器；测试可按需替换 container.browser"""
    return SimpleNamespace(browser=None)


@pytest.fixture(scope="module")
def app():
    """create_app 初始化较慢，模块内复用同一实例（依赖覆盖按测试设置）"""
    from xianyu_hunter.web.app import create_app

    return create_app()


@pytest.fixture
def client(tmp_path: Path, monkeypatch, container: SimpleNamespace, app) -> TestClient:
    from xianyu_hunter.web.services import cookie_runtime_sync as crs
    from xianyu_hunter.web.services import cookie_store as cs
    from xianyu_hunter.web.services import session_starter, user_manager
    from xianyu_hunter.modules import login_orchestrator

    monkeypatch.setattr(ci, "get_browser_data_dir", lambda udd: tmp_path / "bd")
    monkeypatch.setattr(cs.CookieStore, "_sync_to_sqlite", lambda self, cookies: True)
    monkeypatch.setattr(crs, "inject_cookie_store_to_worker_browser", _async_worker_inject)
    monkeypatch.setattr(login_orchestrator, "sync_cookie_layers_from_json", lambda: None)
    monkeypatch.setattr(session_starter, "trigger_session_start", lambda: None)
    um = MagicMock()
    um.issue_session.return_value = "test-session-token"
    um.identify_or_create.return_value = "user_a"
    monkeypatch.setattr(user_manager, "get_user_manager", lambda: um)

    # 默认让浏览器与 SQLite 注入都不可用，本文件不触碰真实 browser-data
    monkeypatch.setattr(ci, "_inject_via_browser", _browser_unavailable)
    monkeypatch.setattr(ci, "_inject_to_sqlite", _sqlite_unavailable)

    app.dependency_overrides[ci.get_container] = lambda: container
    store = cs.get_cookie_store()
    store._cache = {}
    yield TestClient(app)
    app.dependency_overrides.pop(ci.get_container, None)


def test_manual_inject_rejects_blank_and_unparseable(client: TestClient) -> None:
    resp = client.post("/api/auth/cookie", data={"cookie_string": "   "})
    assert resp.json() == {"ok": False, "error": "Cookie 字符串为空"}

    resp = client.post("/api/auth/cookie", data={"cookie_string": "no-equals-here"})
    assert resp.json()["error"] == "未能解析出有效的 cookie 键值对"


def test_manual_inject_browser_success(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(ci, "_inject_via_browser", _browser_ok)
    resp = client.post("/api/auth/cookie", data={"cookie_string": _HEADER_COOKIE})
    data = resp.json()
    assert data["ok"] is True
    assert data["injected"] == 2 and data["total_parsed"] == 2
    assert data["method"] == "browser_context"
    assert "test-session-token" == resp.cookies.get("xh_token")


def test_manual_inject_falls_back_to_json(client: TestClient) -> None:
    resp = client.post("/api/auth/cookie", data={"cookie_string": _HEADER_COOKIE})
    data = resp.json()
    assert data["ok"] is True and data["injected"] == 2
    assert data["method"] == "json_fallback"


def test_manual_inject_all_paths_fail(client: TestClient, monkeypatch) -> None:
    fake_store = MagicMock()
    fake_store.merge_cookies.return_value = False
    monkeypatch.setattr(ci, "get_cookie_store", lambda: fake_store)
    resp = client.post("/api/auth/cookie", data={"cookie_string": _HEADER_COOKIE})
    data = resp.json()
    assert data["ok"] is False
    assert "browser unavailable" in data["error"]
    assert "扫码登录" in data["hint"]


def test_import_file_empty_and_unrecognized(client: TestClient) -> None:
    resp = client.post("/api/auth/cookie/file", files={"file": ("c.txt", b"  \n ", "text/plain")})
    assert resp.json()["error"] == "文件内容为空"

    resp = client.post("/api/auth/cookie/file", files={"file": ("c.txt", b"???", "text/plain")})
    assert "无法识别文件格式" in resp.json()["error"]


def test_import_file_netscape_success(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(ci, "_inject_via_browser", _browser_ok)
    resp = client.post("/api/auth/cookie/file", files={
        "file": ("cookies.txt", _NETSCAPE_LINE.encode(), "text/plain"),
    })
    data = resp.json()
    assert data["ok"] is True and data["injected"] == 1
    assert data["source"] == "file:cookies.txt"


def test_import_file_header_format_success(client: TestClient) -> None:
    resp = client.post("/api/auth/cookie/file", files={
        "file": ("copy.txt", _HEADER_COOKIE.encode(), "text/plain"),
    })
    data = resp.json()
    assert data["ok"] is True and data["injected"] == 2
    assert data["method"] == "json_fallback"


def test_import_path_validation_errors(tmp_path: Path, client: TestClient, monkeypatch) -> None:
    resp = client.post("/api/auth/cookie/path", data={"file_path": "  "})
    assert resp.json()["error"] == "文件路径为空"

    class _Settings:
        project_root = tmp_path

    monkeypatch.setattr("xianyu_hunter.config.get_settings", lambda: _Settings)

    outside = tmp_path.parent / "outside_cookies.txt"
    outside.write_text(_HEADER_COOKIE, encoding="utf-8")
    resp = client.post("/api/auth/cookie/path", data={"file_path": str(outside)})
    assert "路径不在允许范围内" in resp.json()["error"]

    resp = client.post("/api/auth/cookie/path", data={"file_path": str(tmp_path / "missing.txt")})
    assert "文件不存在" in resp.json()["error"]

    resp = client.post("/api/auth/cookie/path", data={"file_path": str(tmp_path)})
    assert "路径不是文件" in resp.json()["error"]

    big = tmp_path / "big.txt"
    with open(big, "wb") as f:
        f.truncate(10 * 1024 * 1024 + 1)
    resp = client.post("/api/auth/cookie/path", data={"file_path": str(big)})
    assert "文件过大" in resp.json()["error"]


def test_import_path_success(tmp_path: Path, client: TestClient, monkeypatch) -> None:
    class _Settings:
        project_root = tmp_path

    monkeypatch.setattr("xianyu_hunter.config.get_settings", lambda: _Settings)
    src = tmp_path / "from_path.txt"
    src.write_text(_NETSCAPE_LINE, encoding="utf-8")
    resp = client.post("/api/auth/cookie/path", data={"file_path": str(src)})
    data = resp.json()
    assert data["ok"] is True and data["injected"] == 1
    assert data["source"] == "path:from_path.txt"


def test_domains_endpoint_missing_and_present(tmp_path: Path, client: TestClient) -> None:
    resp = client.get("/api/auth/cookie/domains")
    assert resp.json() == {"exists": False, "domains": [], "key_names": []}

    db = tmp_path / "bd" / "Default" / "Network" / "Cookies"
    _make_cookie_db(db, [
        (".goofish.com", "unb", "952712345", None),
        ("taobao.com", "cna", "track123", None),
        ("example.com", "x", "y", None),
    ])
    data = client.get("/api/auth/cookie/domains").json()
    assert data["exists"] is True
    assert set(data["domains"]) == {".goofish.com", "taobao.com", "example.com"}
    assert set(data["key_names"]) == {"unb", "cna"}


def test_domains_endpoint_corrupt_db(tmp_path: Path, client: TestClient) -> None:
    db = tmp_path / "bd" / "Default" / "Network" / "Cookies"
    db.parent.mkdir(parents=True)
    db.write_bytes(b"not a database")
    data = client.get("/api/auth/cookie/domains").json()
    assert data["exists"] is True and data["domains"] == [] and data["error"]


def test_saved_cookie_info_empty_then_populated(client: TestClient) -> None:
    assert client.get("/api/auth/cookie/saved").json() == {"has_cookies": False, "logged_in": False}

    from xianyu_hunter.web.services.cookie_store import get_cookie_store

    store = get_cookie_store()
    assert store.merge_cookies([
        {"name": "unb", "value": "952712345", "domain": ".goofish.com", "path": "/"},
        {"name": "cna", "value": "track123", "domain": ".goofish.com", "path": "/"},
    ], method="cookie", user_id="default") is True

    data = client.get("/api/auth/cookie/saved").json()
    assert data["has_cookies"] is True and data["logged_in"] is True
    assert data["cookie_count"] == 2
    assert data["key_cookies_found"] == ["unb"]
    assert data["method"] == "cookie"
    assert data["exported_at"] > 0
    assert data["all_names"] == ["cna", "unb"]


def test_fetch_keys_requires_keys(client: TestClient) -> None:
    resp = client.get("/api/auth/cookie/fetch-keys", params={"keys": " , "})
    assert resp.json()["error"] == "未指定要查询的 cookie key"


def test_fetch_keys_reads_system_chrome_db(tmp_path: Path, client: TestClient, monkeypatch) -> None:
    _make_cookie_db(
        tmp_path / "lad" / "Google" / "Chrome" / "User Data" / "Default" / "Network" / "Cookies",
        [(".goofish.com", "unb", "952712345", None)],
    )
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "lad"))
    data = client.get("/api/auth/cookie/fetch-keys", params={"keys": "unb,cna"}).json()
    assert data["ok"] is True
    assert data["cookies"] == {"unb": "952712345"}
    assert data["missing"] == ["cna"]
    assert "Default" in data["source"]


def test_fetch_keys_falls_back_to_cookie_store_json(client: TestClient) -> None:
    from xianyu_hunter.web.services.cookie_store import get_cookie_store

    assert get_cookie_store().merge_cookies(
        [{"name": "unb", "value": "952712345", "domain": ".goofish.com"}],
        user_id="default",
    ) is True
    data = client.get("/api/auth/cookie/fetch-keys", params={"keys": "unb"}).json()
    assert data["ok"] is True and data["cookies"] == {"unb": "952712345"}
    assert data["source"] == "cookie_store_json_fallback"
    assert "hint" in data


def test_fetch_keys_falls_back_to_playwright_cdp(client: TestClient, container: SimpleNamespace) -> None:
    browser = MagicMock()
    browser._context = object()
    browser.get_cookies = _async_return([
        {"name": "unb", "value": "952712345", "domain": ".goofish.com"},
        {"name": "unb", "value": "x", "domain": "example.com"},
    ])
    container.browser = browser
    data = client.get("/api/auth/cookie/fetch-keys", params={"keys": "unb"}).json()
    assert data["ok"] is True and data["cookies"] == {"unb": "952712345"}
    assert data["source"] == "playwright_cdp"


def test_fetch_keys_v20_encrypted_reports_hint(tmp_path: Path, client: TestClient, monkeypatch) -> None:
    _make_cookie_db(
        tmp_path / "lad" / "Google" / "Chrome" / "User Data" / "Default" / "Network" / "Cookies",
        [(".goofish.com", "unb", "", b"v20encryptedblob")],
    )
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "lad"))
    data = client.get("/api/auth/cookie/fetch-keys", params={"keys": "unb"}).json()
    assert data["ok"] is False and data["cookies"] == {}
    assert "v20" in data["hint"]
    assert "未找到闲鱼 Cookie（unb）" in data["error"]
