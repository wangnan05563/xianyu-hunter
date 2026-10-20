"""三期 UX 优化 · §2.2 成功指标回归（T02581 / 6.1）

把 PRD-UX优化-20261018 §2.2 的五条「发布后验证」指标钉成可重复执行的断言，
而不是留在文档里的口头承诺。逐条对应关系：

1. **可见菜单项点击后落到实现页**：`config/menu_registry.yaml` 里每个带 path 的菜单项，
   必须在 `frontend/src/App.tsx` 的路由表里有对应实现路由（原症状是「价格行情 / 数据导出」
   被 `*` 兜底送回首页）。
2. **「待处理」订单卡数值 = 真实 `pending_pay` 行数**：走前端实际调用的
   `GET /api/orders`，把 `stats.pending` 与直接 SQL `COUNT(*)` 对齐，并验证翻页/筛选
   两侧同口径（原症状是恒 0）。
3. **导出行数 = 筛选预期行数，0 行不弹成功**：`GET /api/export/{dataset}` 的
   `X-Export-Rows` 与同一筛选条件的真实行数一致；0 行时 CSV 只有表头，且前端提示函数
   走 warning 而非 success（另见 `frontend/src/utils/__tests__/exportFeedback.test.ts`）。
4. **UI 展示的、后端无实现的能力项 = 0**：`buyer.max_orders_per_day` 必须同时存在于
   配置模型、执行守卫与 UI；引导文案里不得再出现未被实现支撑的「拖拽排序」「自动滚动」。
5. **前端请求体与后端 schema 不匹配端点 = 0**：按前端逐字构造的载荷打真实端点
   （`PUT /api/menu`、`POST /api/config/save` dry_run、`GET /api/export/orders`、
   `GET /api/orders`），断言不再 422；并断言 dry_run 落盘配置一字未动。

按仓库既有口径打真实 FastAPI 应用（`create_app` + 依赖覆盖），只把数据库换成临时 SQLite，
不使用 Mock 替身；配置文件一律以 `dry_run=True` 或 sha256 前后比对来保证零写入。
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "config" / "menu_registry.yaml"
APP_TSX = ROOT / "frontend" / "src" / "App.tsx"
MENU_GUIDES = ROOT / "frontend" / "src" / "guides" / "menuGuides.ts"
CONFIG_YAML = ROOT / "config" / "config.yaml"


class _ContainerShim:
    """只提供路由实际用到的 `.repo` / `.engine`，其余容器资源与本测试无关"""

    def __init__(self, repo):
        self.repo = repo


@pytest.fixture
def api(tmp_path):
    from fastapi.testclient import TestClient

    from xianyu_hunter.config import get_settings
    from xianyu_hunter.infra.repository import Repository
    from xianyu_hunter.web.app import create_app
    from xianyu_hunter.web.deps import get_container

    db = tmp_path / "ux61.db"
    repo = Repository(db_path=str(db))
    app = create_app()
    app.dependency_overrides[get_container] = lambda: _ContainerShim(repo)

    client = TestClient(app)
    client.cookies.set("xh_token", get_settings().web_token)
    return client, repo, db


def _mk_order(repo, oid: str, status: str, *, task_id: str = "t1") -> None:
    repo.upsert_order({
        "id": oid,
        "task_id": task_id,
        "item_id": f"i_{oid}",
        "price": 100.0,
        "status": status,
    })


def _sql_count(db: Path, status: str | None = None) -> int:
    """独立于 Repository 的原始 SQL 计数：证明卡片数字来自真实行，而不是同一个查询的自我循环"""
    conn = sqlite3.connect(db)
    try:
        if status is None:
            row = conn.execute("SELECT COUNT(*) FROM orders").fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) FROM orders WHERE status = ?", (status,)
            ).fetchone()
        return int(row[0])
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 指标 1：可见菜单项 → 实现路由
# ---------------------------------------------------------------------------

def _menu_paths_from_registry() -> list[str]:
    """解析 registry：取带 path 的条目（visible:false 的项不在「可见菜单」分母里）"""
    text = REGISTRY.read_text(encoding="utf-8")
    paths: list[str] = []
    visible_false = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- key:"):
            visible_false = False  # 新条目：默认可见（registry 未写 visible 即沿用默认）
        m = re.match(r"^path:\s*(\S+)\s*$", stripped)
        if m:
            if not visible_false:
                paths.append(m.group(1))
        v = re.match(r"^visible:\s*(false|true)\b", stripped)
        if v:
            visible_false = v.group(1) == "false"
    return paths


def _implemented_routes() -> set[str]:
    """App.tsx 里的路由全集：顶级绝对路径 + MainLayout 子路由（相对名补 '/' 前缀）"""
    src = APP_TSX.read_text(encoding="utf-8")
    routes: set[str] = set()
    for raw in re.findall(r'<Route\s+path="([^"]+)"', src):
        if raw == "*":
            continue
        routes.add(raw if raw.startswith("/") else "/" + raw)
    return routes


def test_every_visible_menu_path_has_an_implemented_route() -> None:
    paths = _menu_paths_from_registry()
    routes = _implemented_routes()
    assert len(paths) >= 29, f"registry 解析异常：只取到 {len(paths)} 条带 path 的菜单"
    missing = sorted({p for p in paths if p not in routes})
    # 原症状专项：这两条曾被 `*` 兜底送回首页
    assert "/price-dashboard" in routes and "/export" in routes
    assert missing == [], f"菜单下发但无实现路由的路径：{missing}"


def test_menu_paths_are_unique() -> None:
    paths = _menu_paths_from_registry()
    dupes = sorted({p for p in paths if paths.count(p) > 1})
    assert dupes == [], f"registry 中重复 path 会让侧栏出现两个同名入口：{dupes}"


# ---------------------------------------------------------------------------
# 指标 2：「待处理」卡 = 真实 pending_pay 行数
# ---------------------------------------------------------------------------

def test_pending_card_equals_real_pending_pay_rows(api) -> None:
    client, repo, db = api
    for oid, st in [
        ("o1", "pending_pay"), ("o2", "pending_pay"), ("o3", "pending_pay"),
        ("o4", "takeover_pending"), ("o5", "succeeded"),
        ("o6", "failed"), ("o7", "cancelled"), ("o8", "dry_run"),
    ]:
        _mk_order(repo, oid, st)

    real_pending = _sql_count(db, "pending_pay")
    assert real_pending == 3

    body = client.get("/api/orders", params={"page_num": 1, "page_size": 2}).json()
    assert body["stats"]["pending"] == real_pending, (
        f"待处理卡 {body['stats']['pending']} ≠ 真实 pending_pay 行数 {real_pending}"
    )
    # 恒 0 的老症状：卡片为 0 而库里确实有待处理行
    assert body["stats"]["pending"] > 0

    # 筛选侧同口径：筛「待处理」命中的行数必须与卡片一致
    filtered = client.get("/api/orders", params={"status": "pending_pay"}).json()
    assert filtered["total"] == real_pending

    # 翻页不改分母
    p2 = client.get("/api/orders", params={"page_num": 2, "page_size": 2}).json()
    assert p2["stats"]["pending"] == real_pending


def test_takeover_pending_is_not_counted_as_pending(api) -> None:
    """pending_pay 与 takeover_pending 是两个桶：合并计数会让「待处理」虚高"""
    client, repo, db = api
    _mk_order(repo, "a1", "pending_pay")
    for i in range(3):
        _mk_order(repo, f"b{i}", "takeover_pending")

    body = client.get("/api/orders").json()
    assert body["stats"]["pending"] == _sql_count(db, "pending_pay") == 1
    assert body["stats"]["takeover"] == _sql_count(db, "takeover_pending") == 3


# ---------------------------------------------------------------------------
# 指标 3：导出行数 = 筛选预期行数；0 行不谎报
# ---------------------------------------------------------------------------

def _csv_data_rows(text: str) -> int:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return max(len(lines) - 1, 0)  # 去掉表头


def test_export_row_count_matches_filter(api) -> None:
    client, repo, db = api
    for oid, st in [("x1", "pending_pay"), ("x2", "pending_pay"), ("x3", "succeeded")]:
        _mk_order(repo, oid, st)

    r = client.get("/api/export/orders", params={"status": "pending_pay"})
    assert r.status_code == 200
    assert int(r.headers["x-export-rows"]) == _sql_count(db, "pending_pay") == 2
    assert _csv_data_rows(r.text) == int(r.headers["x-export-rows"]), (
        "X-Export-Rows 与 CSV 实际数据行数不一致：回带给用户的条数不可信"
    )


def test_export_zero_rows_returns_header_only_and_reports_zero(api) -> None:
    client, repo, db = api
    _mk_order(repo, "y1", "succeeded")

    r = client.get("/api/export/orders", params={"status": "not_a_real_status"})
    assert r.status_code == 200
    assert int(r.headers["x-export-rows"]) == 0
    assert _csv_data_rows(r.text) == 0, "0 行导出必须只有表头"
    assert r.headers.get("content-disposition"), "0 行也必须给出真实文件名，前端据此提示"


def test_export_unknown_dataset_is_400_not_silent_success(api) -> None:
    client, _, _ = api
    r = client.get("/api/export/nope")
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# 指标 4：UI 不得展示后端没有实现的能力
# ---------------------------------------------------------------------------

def test_daily_grab_limit_is_backed_by_schema_and_guard() -> None:
    """「单日抢单上限」原是一句假护栏（字段与执行逻辑都不存在，T02589 才做成真的）"""
    from xianyu_hunter.infra.yaml_config import get_config

    cfg = get_config()
    assert hasattr(cfg.buyer, "max_orders_per_day"), "配置模型里没有这个字段，UI 输入框即假承诺"
    assert int(cfg.buyer.max_orders_per_day) >= 0

    buyer_src = (ROOT / "backend" / "xianyu_hunter" / "modules" / "buyer.py").read_text(
        encoding="utf-8"
    )
    assert "max_orders_per_day" in buyer_src, "执行侧没有读取该字段 = 设了也不生效"

    ui_src = (ROOT / "frontend" / "src" / "pages" / "Config" / "BuyerStrategy.tsx").read_text(
        encoding="utf-8"
    )
    assert "max_orders_per_day" in ui_src, "UI 未接入该字段"
    # 只检用户可见文案：源码注释里允许留档「原文案曾是假承诺」的说明（T02589 的修复记录）
    visible = re.sub(r"\{/\*.*?\*/\}", "", ui_src, flags=re.S)
    assert "待 UI 化" not in visible, "可见文案里不得再留着「后端待实现」的假承诺"
    assert "单日抢单数量上限" in visible and "未设置（不限制）" in visible, (
        "上限卡必须回显真实开关状态，而不是固定话术"
    )


def _guide_step(route: str) -> str:
    """取某个路由的引导文案全文（menuGuides.ts 是 step 数组，逐路由取 description）"""
    src = MENU_GUIDES.read_text(encoding="utf-8")
    block = re.search(
        r"route:\s*'" + re.escape(route) + r"'(.*?)(?=\n\s*\{\s*route:|\n\])", src, re.S
    )
    assert block, f"menuGuides.ts 里找不到路由 {route} 的引导配置"
    return block.group(1)


def test_guide_claims_are_backed_by_implementation() -> None:
    """引导文案宣称的能力，页面源码里必须有对应实现证据（PRD §4 风险 3：假承诺一律实现或删除）"""
    checks = [
        ("/menu-admin", "拖拽排序", ["onDragEnd", "dnd", "DndContext", "draggable"],
         "frontend/src/pages/MenuAdmin/index.tsx"),
        ("/logs", "自动滚动", ["scrollTop", "scrollIntoView"],
         "frontend/src/pages/Logs/Logs.tsx"),
    ]
    for route, claim, evidence, page_path in checks:
        step = _guide_step(route)
        if claim not in step:
            continue  # 文案已改掉这个说法，无需实现
        page_src = (ROOT / page_path).read_text(encoding="utf-8")
        assert any(e in page_src for e in evidence), (
            f"{route} 引导文案宣称「{claim}」，但 {page_path} 里没有对应实现 = 假承诺"
        )


def test_menu_admin_and_logs_copy_state_what_actually_happens() -> None:
    """T02581 实测两处假承诺的修复态：菜单管理是数值排序输入框，实时日志不自动跟随"""
    assert "拖拽排序" not in _guide_step("/menu-admin")
    assert "自动滚动" not in _guide_step("/logs")


# ---------------------------------------------------------------------------
# 指标 5：前端请求体与后端 schema 逐字对齐
# ---------------------------------------------------------------------------

def _resolve(schema: dict, spec: dict) -> dict:
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        return spec["components"]["schemas"].get(name, {})
    return schema


def _body_props(method: str, path: str) -> tuple[set[str], set[str]]:
    from xianyu_hunter.web.app import create_app

    spec = create_app().openapi()
    op = spec["paths"].get(path, {}).get(method.lower())
    assert op, f"后端没有注册 {method} {path}"
    body = _resolve(
        op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {}),
        spec,
    )
    return set(body.get("properties", {})), set(body.get("required", []))


def _query_params(method: str, path: str) -> set[str]:
    from xianyu_hunter.web.app import create_app

    spec = create_app().openapi()
    op = spec["paths"].get(path, {}).get(method.lower())
    assert op, f"后端没有注册 {method} {path}"
    return {p["name"] for p in op.get("parameters", [])}


def test_menu_update_body_matches_frontend_client() -> None:
    """前端 menuApi.update 发的外层键必须是 menus，项内键只能是 key/visible/sort_order"""
    props, required = _body_props("PUT", "/api/menu")
    assert props == {"menus"}, f"PUT /api/menu 顶层字段变了：{props}"
    assert "menus" in required

    src = (ROOT / "frontend" / "src" / "api" / "menu.ts").read_text(encoding="utf-8")
    assert re.search(r"client\.put<[^>]*>\('/api/menu',\s*\{\s*menus:\s*items\s*\}\)", src), (
        "前端 PUT /api/menu 的载荷不再是 {menus: items}，与本契约断言失配"
    )


def test_config_save_body_matches_frontend_client(api) -> None:
    """前端发 {payload, dry_run}；后端 schema 必须接纳这两个键，且 dry_run 不落盘"""
    props, _required = _body_props("POST", "/api/config/save")
    assert {"payload", "dry_run"} <= props, f"POST /api/config/save 字段失配：{props}"

    src = (ROOT / "frontend" / "src" / "api" / "config.ts").read_text(encoding="utf-8")
    assert "client.post('/api/config/save'" in src, "前端 config.save 调用点变了，本契约断言需同步"
    assert "{ payload, dry_run: dryRun }" in src, "前端发出的外层键不再是 payload + dry_run"

    client = api[0]
    before = CONFIG_YAML.read_bytes()
    r = client.post("/api/config/save", json={"payload": {}, "dry_run": True})
    assert r.status_code != 422, (
        f"请求体形状仍被 Pydantic 拒（422）：{r.text[:200]}"
    )
    assert CONFIG_YAML.read_bytes() == before, "dry_run 保存不得改动仓库配置文件"


def test_export_and_orders_query_params_match_frontend() -> None:
    """前端在用的筛选参数，后端必须声明；声明外的键会被静默丢弃＝导出与筛选不一致的根因"""
    export_params = _query_params("GET", "/api/export/{dataset}")
    used = {"task_id", "start", "end", "status", "level", "limit"}
    assert used <= export_params, f"导出缺参：{sorted(used - export_params)}"

    orders_params = _query_params("GET", "/api/orders")
    assert {"page_num", "page_size", "status"} <= orders_params

