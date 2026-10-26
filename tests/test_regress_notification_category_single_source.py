"""T02619 回归：通知分类的唯一事实源与跨语言一致性

盯盘降价通知一直写 `category="price"`，但该字面值既不在 API 白名单
`api_notifications._ALLOWED_CATEGORIES` 里，也不在前端两张中文标签表里，于是：
- 从 `/api/notifications` 创建同类通知会被 400 拒掉；
- 绕过 API 直写仓储能落库，但通知中心那条的 Tag 取到 undefined → 显示空白；
- 桌面端把 auth 写成「登录」、移动端写成「认证」，同一含义两套文案。

本文件把「分类只有 domain/notification.py 一处定义」钉成断言：
白名单来源、写侧不许裸写字面量、API 冒烟、以及跨语言读取前端 TS 源比对键与文案。
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend" / "xianyu_hunter"
API_NOTIFICATIONS = BACKEND / "web" / "routes" / "api_notifications.py"
DOMAIN_NOTIFICATION = BACKEND / "domain" / "notification.py"
FRONTEND_API_TS = ROOT / "frontend" / "src" / "api" / "notifications.ts"
FRONTEND_DESKTOP = ROOT / "frontend" / "src" / "pages" / "Notifications" / "index.tsx"
FRONTEND_MOBILE = ROOT / "frontend" / "src" / "mobile" / "pages" / "Notifications" / "index.tsx"

# 直接调用 repo.add_notification 的业务写侧（T02619 涉及的两个模块）
WRITER_FILES = (
    BACKEND / "modules" / "price_watch.py",
    BACKEND / "web" / "services" / "notification_engine.py",
)


class _ContainerShim:
    """只提供通知路由实际用到的 `.repo`"""

    def __init__(self, repo):
        self.repo = repo


@pytest.fixture
def api(tmp_path):
    from fastapi.testclient import TestClient

    from xianyu_hunter.config import get_settings
    from xianyu_hunter.infra.repository import Repository
    from xianyu_hunter.web.app import create_app
    from xianyu_hunter.web.deps import get_container

    repo = Repository(db_path=str(tmp_path / "notif_cat.db"))
    app = create_app()
    app.dependency_overrides[get_container] = lambda: _ContainerShim(repo)
    client = TestClient(app)
    client.cookies.set("xh_token", get_settings().web_token)
    return client, repo


# ============== 白名单来源 ==============
def test_allowed_categories_come_from_domain_module():
    """白名单必须是 domain 模块的派生值，而不是路由里再手写一份枚举"""
    from xianyu_hunter.domain.notification import NOTIFICATION_CATEGORY_VALUES
    from xianyu_hunter.web.routes import api_notifications

    assert api_notifications._ALLOWED_CATEGORIES == NOTIFICATION_CATEGORY_VALUES
    assert api_notifications._ALLOWED_LEVELS == frozenset({"info", "warn", "err"})


def test_price_category_is_registered():
    """T02619 的核心断言：price_watch 真实写入的 price 必须在白名单里

    修复前这里是 `assert "price" not in ...`（5 个分类的硬编码集合），
    盯盘通知因此「API 建不出来、前端标签空白」。
    """
    from xianyu_hunter.domain.notification import NotificationCategory
    from xianyu_hunter.web.routes import api_notifications

    assert "price" in api_notifications._ALLOWED_CATEGORIES
    assert NotificationCategory.PRICE.label == "盯盘"
    # auth 的中文文案只有一个版本（修复前桌面「登录」/ 移动「认证」并存）
    assert NotificationCategory.AUTH.label == "登录"


def test_category_label_falls_back_for_unknown():
    """未知/空值不抛错、不返回空白：历史行里可能出现已下线分类，宁可露出原始 key 也不要 500"""
    from xianyu_hunter.domain.notification import category_label

    assert category_label("legacy_box") == "legacy_box"
    assert category_label(None) == ""
    assert category_label("price") == "盯盘"


# ============== 写侧不许裸写字面量 ==============
def _category_keyword_nodes(path: Path) -> list[tuple[ast.AST, str]]:
    """返回 (node, 所属调用名) —— 仅取 add_notification(...) 调用里的 category= 实参"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[tuple[ast.AST, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = getattr(func, "attr", None) or getattr(func, "id", None)
        if name != "add_notification":
            continue
        for kw in node.keywords:
            if kw.arg == "category":
                found.append((kw.value, path.name))
    return found


def test_writer_categories_are_all_registered():
    """写侧 category= 的取值必须都在白名单内（防止再出现未注册分类）"""
    from xianyu_hunter.domain.notification import NOTIFICATION_CATEGORY_VALUES

    offenders: list[str] = []
    written: set[str] = set()
    for path in WRITER_FILES:
        for node, fname in _category_keyword_nodes(path):
            value = _resolve_category_value(node)
            if value is None:
                offenders.append(f"{fname}@L{getattr(node, 'lineno', 0)} 无法识别的 category 写法")
            elif value not in NOTIFICATION_CATEGORY_VALUES:
                offenders.append(f"{fname}@L{getattr(node, 'lineno', 0)}={value!r}")
            else:
                written.add(value)
    assert offenders == [], "存在未注册/非法写法的 category: " + "; ".join(offenders)
    # order / auth / price 确实被代码写入（price 正是 T02619 漏注册的那一个），
    # 而不是只存在于文档或测试里
    assert {"order", "auth", "price"} <= written


def test_writers_use_domain_enum_not_bare_strings():
    """写侧统一引用 domain 枚举：字面值只有一处定义，新增分类时不会出现漏改"""
    bare = [
        f"{fname}@L{getattr(node, 'lineno', 0)}"
        for path in WRITER_FILES
        for node, fname in _category_keyword_nodes(path)
        if isinstance(node, ast.Constant)
    ]
    assert bare == [], "add_notification 的 category 仍在裸写字符串：" + ", ".join(bare)


def _is_enum_member_ref(node: ast.AST) -> bool:
    """识别 `NotificationCategory.X.value` 这一种写法"""
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "value"
        and isinstance(node.value, ast.Attribute)
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "NotificationCategory"
    )


def _resolve_category_value(node: ast.AST) -> str | None:
    """把 category 实参解析成最终落库的字面值；解析不出来的写法返回 None"""
    from xianyu_hunter.domain.notification import NotificationCategory

    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if _is_enum_member_ref(node):
        member = getattr(NotificationCategory, node.value.attr, None)  # type: ignore[attr-defined]
        return None if member is None else member.value
    return None


def test_domain_enum_members_match_whitelist():
    """枚举成员、标签表、白名单三者必须同源同集合（防「加了成员忘了标签」这类半截改动）"""
    src = DOMAIN_NOTIFICATION.read_text(encoding="utf-8")
    tree = ast.parse(src)
    members: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "NotificationCategory":
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    members.append(stmt.target.id)
                elif isinstance(stmt, ast.Assign) and isinstance(stmt.targets[0], ast.Name):
                    members.append(stmt.targets[0].id)
    from xianyu_hunter.domain.notification import NOTIFICATION_CATEGORY_VALUES, NotificationCategory

    assert len(members) == len(NOTIFICATION_CATEGORY_VALUES) == len(list(NotificationCategory))
    # 每个成员都有中文标签（_CATEGORY_LABELS 覆盖完整，否则 category_label 会 KeyError）
    for member in members:
        assert getattr(NotificationCategory, member).label


DOC_SRS = ROOT / "docs" / "02-数据查看" / "通知中心-需求规格.md"
DOC_DESIGN = ROOT / "docs" / "02-数据查看" / "通知中心-详细设计.md"


def test_reserved_categories_have_no_writer_in_backend():
    """T02812 裁决 A：task/config/system 保留为白名单分类，且后端确无生产者

    真有人给它们加了写入点，这条会红——届时按 domain/notification.py 的流程同步：
    枚举注释、api_notifications 白名单说明、两份文档的分类表与「内置写入方」列。
    """
    writer_files = [
        path for path in BACKEND.rglob("*.py")
        if "add_notification(" in path.read_text(encoding="utf-8")
    ]
    written: set[str] = set()
    for path in writer_files:
        for node, _fname in _category_keyword_nodes(path):
            value = _resolve_category_value(node)
            if value is not None:  # api_notifications 的透传写法 category=category 解不出来，属预期
                written.add(value)
    assert written == {"order", "auth", "price"}, (
        f"通知写入方集合变了：{sorted(written)}；"
        "新增/删除分类请同步 domain 注释、白名单说明与两份文档"
    )


def _doc_category_table(path: Path, heading: str) -> list[str]:
    """截取文档里某个标题到下一个同级标题之间的分类表行"""
    import re

    src = path.read_text(encoding="utf-8")
    start = src.find(heading)
    assert start > -1, f"{path.name} 找不到章节：{heading}"
    rest = src[start + len(heading):]
    end = rest.find("\n### ")
    block = rest if end == -1 else rest[:end]
    return [ln for ln in block.splitlines() if re.match(r"^\|\s*`[a-z]+`", ln)]


def test_docs_list_every_category_and_mark_the_reserved_ones():
    """文档曾长期停在「5 分类」且漏掉真实写入的 price（T02812 裁决 A 要求写明用途）"""
    import re

    from xianyu_hunter.domain.notification import NOTIFICATION_CATEGORY_VALUES

    for path, heading in ((DOC_SRS, "**FR-5.1**"), (DOC_DESIGN, "### 6.3")):
        rows = _doc_category_table(path, heading)
        values = {re.match(r"^\|\s*`([a-z]+)`", ln).group(1) for ln in rows}
        assert values == set(NOTIFICATION_CATEGORY_VALUES), (
            f"{path.name} 的分类表与枚举不一致：表内 {sorted(values)} / 枚举 {sorted(NOTIFICATION_CATEGORY_VALUES)}"
        )
        for reserved in ("task", "config", "system"):
            row = next(ln for ln in rows if ln.startswith(f"| `{reserved}`"))
            assert "无" in row, f"{path.name} 未标明 {reserved} 没有内置写入方"


# ============== API 冒烟 ==============
def test_post_price_category_accepted_and_persisted(api):
    """修复前：category=price 走 API 会被 400 拒掉。现在应当创建成功并原样落库"""
    client, repo = api
    resp = client.post("/api/notifications", json={
        "level": "warn",
        "category": "price",
        "title": "降价提醒：测试商品",
        "message": "现价 ¥99.00（历史最低 ¥120.00）",
        "dedup_key": "price_drop:test-item:99.00",
        "link": "/m/items/",
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["item"]["category"] == "price"
    rows = repo.list_notifications(status=None, limit=10)
    assert [r["category"] for r in rows] == ["price"]


def test_post_uppercase_category_is_normalized(api):
    """入参归一化：category 大小写混用应被 lower 后按白名单校验，不产生 'Price' 这类第二字面值"""
    client, repo = api
    resp = client.post("/api/notifications", json={
        "level": "info",
        "category": "PRICE",
        "title": "大写分类",
        "message": "应被归一化为 price",
        "dedup_key": "price_drop:uppercase",
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["item"]["category"] == "price"
    assert repo.list_notifications(status=None, limit=10)[0]["category"] == "price"


def test_post_unknown_category_rejected_with_stable_detail(api):
    """未注册分类仍要 400，且报错文案可读、顺序稳定（frozenset 的 repr 每次可能不同）"""
    from xianyu_hunter.domain.notification import NOTIFICATION_CATEGORY_ORDER

    client, _repo = api
    details = set()
    for _ in range(5):
        resp = client.post("/api/notifications", json={
            "level": "info",
            "category": "not_a_real_category",
            "title": "脏数据",
            "message": "应被拒绝",
            "dedup_key": "dirty:1",
        })
        assert resp.status_code == 400
        details.add(resp.json()["detail"])
    assert len(details) == 1, "同一错误的文案不稳定：" + repr(details)
    detail = details.pop()
    # 文案 = 声明序全量清单：无花括号/引号的集合调试输出，且 price 在列（修复前不在）
    assert detail == "category 必须是 " + "/".join(NOTIFICATION_CATEGORY_ORDER) + " 之一"
    assert "price" in detail and "{" not in detail and "'" not in detail


def test_post_unknown_level_rejected(api):
    client, _repo = api
    resp = client.post("/api/notifications", json={
        "level": "critical",
        "category": "system",
        "title": "非法等级",
        "message": "应被拒绝",
        "dedup_key": "dirty:2",
    })
    assert resp.status_code == 400
    # 按严重度声明序（info/warn/err），不是字母序的 err/info/warn
    assert resp.json()["detail"] == "level 必须是 info/warn/err 之一"


# ============== 跨语言守卫（前端 TS 与后端 domain 同源） ==============
def _parse_frontend_categories() -> dict[str, str]:
    """从 api/notifications.ts 抽取 key → 中文标签

    这里用轻量正则而不是 TS 解析器：本断言只关心 `NOTIFICATION_CATEGORY_LABEL`
    这一段对象字面量，形状稳定（`key: '标签',`），正则足够且不需要前端构建链。
    """
    import re

    src = FRONTEND_API_TS.read_text(encoding="utf-8")
    block = re.search(
        r"NOTIFICATION_CATEGORY_LABEL[^=]*=\s*\{(.*?)\}", src, re.S
    )
    assert block, "前端未找到 NOTIFICATION_CATEGORY_LABEL（单一事实源被拆走了？）"
    pairs = re.findall(r"^\s*(\w+)\s*:\s*'([^']+)'", block.group(1), re.M)
    return dict(pairs)


def _parse_frontend_union_keys() -> set[str]:
    import re

    src = FRONTEND_API_TS.read_text(encoding="utf-8")
    m = re.search(r"type NotificationCategory\s*=\s*([^\n]+)", src)
    assert m, "前端未找到 NotificationCategory 联合类型"
    return set(re.findall(r"'([a-z_]+)'", m.group(1)))


def test_frontend_label_map_matches_backend():
    """前端标签表的 key 集合与中文文案，必须与后端 domain 逐字一致"""
    from xianyu_hunter.domain.notification import NOTIFICATION_CATEGORY_VALUES, category_label

    labels = _parse_frontend_categories()
    assert set(labels) == set(NOTIFICATION_CATEGORY_VALUES)
    mismatched = {k: (v, category_label(k)) for k, v in labels.items() if v != category_label(k)}
    assert mismatched == {}, f"前后端中文标签不一致：{mismatched}"


def test_frontend_union_type_covers_price():
    """联合类型也必须含 price：否则 TS 里 CATEGORY_LABEL['price'] 仍是非法访问，
    而运行时取到 undefined 只会表现为空白标签，没有任何报错。"""
    assert "price" in _parse_frontend_union_keys()
    assert _parse_frontend_categories()["auth"] == "登录"


def test_pages_consume_the_shared_map_and_define_no_local_copies():
    """桌面/移动两页都消费共享常量，且不再自带一张标签表（防止两处文案再度分叉）"""
    for path in (FRONTEND_DESKTOP, FRONTEND_MOBILE):
        src = path.read_text(encoding="utf-8")
        assert "NOTIFICATION_CATEGORY_LABEL" in src, f"{path.name} 未引用共享标签表"
        assert "Record<NotificationItem['category'], string>" not in src, \
            f"{path.name} 仍自带一张 category 标签表"
