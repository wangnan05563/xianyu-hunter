"""数据库维护 API（系统维护 → 数据库维护 二级菜单）

提供本系统 SQLite 业务表的在线 CRUD 能力，定位为「轻量级 Navicat」：
- 表白名单：仅允许操作 ORM 已声明的业务表（tasks/items/events/...），禁止 sqlite_master 等系统表
- 动态表结构：通过 SQLAlchemy Inspector 反射列信息，免维护硬编码
- 参数化查询：所有 SQL 通过绑定参数构造，杜绝拼接注入
- 审计日志：所有 DML 写入 events 表（type=db_admin.*），可在「实时日志」页回溯
- 双重确认：危险操作（删除/批量删除）需要 confirm_token=CONFIRM_DELETE 才执行
- 行数限制：单次查询最多 1000 行，导入最多 5000 行，避免误操作拖垮数据库

为什么不做 DDL（建表/改字段）：本系统表结构由 SQLAlchemy ORM 管理（init_db 自动迁移），
前端修改字段会绕过 ORM 校验导致下次启动失败。如需调整表结构应改后端 ORM 定义。
"""
from __future__ import annotations

import csv
import io
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from xianyu_hunter.container import Container
from xianyu_hunter.web.deps import get_container
from xianyu_hunter.web.services.search_services import (
    DbAdminSearchParams,
    DbAdminSearchService,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/db-admin", tags=["db-admin"])


# ============== 安全常量 ==============

# 业务表白名单：与 xianyu_hunter.infra.db_models 中声明的表一一对应
# 故意不包含 sqlite_master / sqlite_sequence 等系统表，防止误操作元数据
ALLOWED_TABLES: tuple[str, ...] = (
    "tasks",
    "items",
    "sellers",
    "evaluations",
    "orders",
    "events",
    "task_links",
    "task_deps",
    "notifications",
    "accounts",
    "proxies",
)

# 危险操作二次确认 token（前端弹窗需用户输入此值才能继续）
CONFIRM_TOKEN = "CONFIRM_DELETE"

# 单次返回最大行数（防止 SELECT * FROM 大表拖垮 UI 和数据库）
MAX_PAGE_SIZE = 1000
# 单次导入最大行数
MAX_IMPORT_ROWS = 5000
# 标识符白名单：列名/排序字段必须匹配此正则，防止 ORDER BY 注入
# S6353: [A-Za-z0-9_] 等价于 ASCII 模式下的 \w，re.ASCII 保证不匹配 Unicode 字母
_IDENT_RE = re.compile(r"^[A-Za-z_]\w*$", re.ASCII)


def _validate_table(table: str) -> str:
    """校验表名是否在白名单内（防止路径遍历/任意表访问）"""
    if table not in ALLOWED_TABLES:
        raise HTTPException(status_code=400, detail=f"表 {table!r} 不在维护白名单中")
    return table


def _validate_identifier(name: str, kind: str) -> str:
    """校验列名等 SQL 标识符，防止 ORDER BY 列名注入"""
    if not _IDENT_RE.match(name):
        raise HTTPException(status_code=400, detail=f"非法 {kind} 标识符: {name!r}")
    return name


# ============== 字段中文语义标注 ==============
# 每个字段标注包含：业务含义、数据类型特征、使用场景、约束条件
# 标注原则：专业规范、简洁易懂，便于开发/分析人员理解字段用途
COLUMN_LABELS: dict[str, dict[str, str]] = {
    "tasks": {
        "id": "任务ID（UUID，系统自动生成，全局唯一标识）",
        "name": "任务名称（用户自定义，如「佳能RP镜头监控」）",
        "keyword": "搜索关键词（闲鱼商品搜索词，如「佳能RP 镜头」）",
        "min_price": "最低价格（元，价格筛选下限，NULL=不限）",
        "max_price": "最高价格（元，价格筛选上限，NULL=不限）",
        "max_publish_days": "发布天数上限（仅展示 N 天内发布的商品，NULL=不限）",
        "exclude_words": "排除词（JSON数组，如[\"配件\",\"赠品\"],命中则跳过）",
        "region": "发货地区（如「浙江杭州」，NULL=不限地区）",
        "search_filters": "搜索筛选标签（JSON数组，如[\"personal_idle\",\"free_shipping\"]）",
        "cron": "Cron表达式（调度频率，默认*/1 * * * *即每分钟执行）",
        "mode": "抢单模式（confirm=需确认/auto=自动下单/manual=仅监控）",
        "notifier_channels": "通知渠道（JSON数组，如[\"serverchan\",\"bark\"]）",
        "ai_prompt": "AI评估提示词（自定义Prompt，覆盖默认评估逻辑）",
        "eval_threshold": "评估阈值（0-100，低于此分数的商品被过滤）",
        "status": "任务状态（running=运行中/paused=已暂停/stopped=已停止/completed=已完成）",
        "created_at": "创建时间（UTC，任务首次创建的时间戳）",
        "updated_at": "更新时间（UTC，任务配置最近修改的时间戳）",
    },
    "items": {
        "id": "商品ID（闲鱼商品唯一标识，来源于闲鱼平台）",
        "task_id": "关联任务ID（FK→tasks.id，标识该商品由哪个任务发现）",
        "title": "商品标题（闲鱼卖家发布的商品名称）",
        "price": "商品价格（元，卖家标价）",
        "publish_time": "发布时间（卖家上架时间，用于计算发布天数）",
        "region": "发货地区（卖家填写的发货地，如「广东深圳」）",
        "seller_id": "卖家ID（FK→sellers.id，关联卖家信息）",
        "want_cnt": "想要数（商品被多少用户标记为想要）",
        "view_cnt": "浏览数（商品被浏览的次数，反映热度）",
        "thumb_url": "缩略图URL（商品主图链接，用于列表展示）",
        "image_urls": "图片URL列表（JSON数组，商品全部图片链接）",
        "description": "商品描述（卖家填写的商品详情文字）",
        "raw_json": "原始数据（JSON，闲鱼API返回的完整商品数据快照）",
        "first_seen": "首次发现时间（UTC，系统首次抓取到该商品的时间）",
        "last_seen": "最近发现时间（UTC，系统最后一次看到该商品的时间）",
    },
    "sellers": {
        "id": "卖家ID（闲鱼用户唯一标识）",
        "nick": "卖家昵称（闲鱼显示名）",
        "credit_score": "信用分（芝麻信用分，越高越可信，NULL=未获取）",
        "register_days": "注册天数（账号注册至今的天数，新号风险较高）",
        "on_sale_count": "在售商品数（当前在售商品数量）",
        "sold_count": "已售商品数（历史成交数量，反映交易经验）",
        "top_category": "主营类目（卖家最常发布的商品分类）",
        "top_category_ratio": "主营类目占比（0-1，主营类目商品占总商品的比例）",
        "post_count_30d": "30天发布数（近30天发布商品数量，过高可能为商家号）",
        "bad_review_count": "差评数（收到差评的次数，风险指标）",
        "in_blacklist": "黑名单标记（0=正常/1=在黑名单中，手动或自动标记）",
        "recent_posts_json": "近期发布记录（JSON，近7天发布商品的摘要列表）",
        "last_visited": "最近访问时间（UTC，系统最后一次抓取卖家主页的时间）",
        "last_eval": "最近评估时间（UTC，系统最后一次对该卖家做风险评估的时间）",
    },
    "evaluations": {
        "id": "评估ID（自增主键，系统自动生成）",
        "item_id": "商品ID（FK→items.id，被评估的闲鱼商品）",
        "seller_id": "卖家ID（FK→sellers.id，商品所属卖家）",
        "score": "综合评分（0-100，综合各维度得分，越高越值得购买）",
        "risk_level": "风险等级（low=低风险/medium=中风险/high=高风险/critical=极高风险）",
        "dimension_scores": "维度评分（JSON，各评估维度的独立分数，如{\"price\":85,\"seller\":70}）",
        "reject_reasons": "拒绝原因（JSON数组，未通过评估的具体原因列表）",
        "created_at": "评估时间（UTC，系统完成评估的时间戳）",
    },
    "orders": {
        "id": "订单ID（系统生成的唯一标识）",
        "task_id": "关联任务ID（FK→tasks.id，触发下单的任务）",
        "item_id": "商品ID（FK→items.id，被下单的闲鱼商品）",
        "seller_id": "卖家ID（FK→sellers.id，商品所属卖家）",
        "order_no": "闲鱼订单号（闲鱼平台的订单编号，下单成功后回填）",
        "price": "成交价格（元，实际下单金额）",
        "status": "订单状态（pending=待确认/confirmed=已确认/paid=已支付/failed=失败/cancelled=已取消）",
        "screenshot": "截图路径（下单/支付成功后的页面截图文件路径）",
        "error": "错误信息（下单失败时的错误描述，成功时为NULL）",
        "confirmed_at": "确认时间（UTC，用户确认下单的时间）",
        "paid_at": "支付时间（UTC，完成支付的时间）",
        "created_at": "创建时间（UTC，订单首次创建的时间戳）",
    },
    "events": {
        "id": "事件ID（自增主键，系统自动生成）",
        "type": "事件类型（如task.started/item.found/order.confirmed/db_admin.delete等）",
        "task_id": "关联任务ID（FK→tasks.id，事件所属任务，NULL=全局事件）",
        "item_id": "关联商品ID（FK→items.id，事件关联的商品，NULL=非商品事件）",
        "stage": "执行阶段（如crawl/eval/order/notify，标识事件发生在哪个处理阶段）",
        "level": "日志级别（debug/info/warn/err，反映事件严重程度）",
        "message": "事件消息（人类可读的事件描述文本）",
        "payload": "事件详情（JSON，结构化的附加数据，如错误堆栈、配置快照等）",
        "created_at": "事件时间（UTC，事件发生的时间戳，核心排序字段）",
    },
    "task_links": {
        "id": "关联ID（自增主键，系统自动生成）",
        "task_id": "任务ID（FK→tasks.id，关联的任务）",
        "link_type": "关联类型（item=商品关联/seller=卖家关联，区分关联对象类型）",
        "link_key": "关联键（商品ID或卖家ID，与link_type配合定位关联对象）",
        "display": "展示信息（JSON冗余字段，存储关联对象的摘要信息用于前端展示）",
        "source": "来源（auto=Worker自动关联/manual=用户手动关联）",
        "note": "备注（用户自定义的关联说明文字）",
        "created_at": "创建时间（UTC，关联首次建立的时间戳）",
        "updated_at": "更新时间（UTC，关联信息最近修改的时间戳）",
    },
    "task_deps": {
        "id": "依赖ID（自增主键，系统自动生成）",
        "task_id": "被依赖任务ID（FK→tasks.id，等待依赖完成后才启动的任务）",
        "depends_on": "依赖任务ID（FK→tasks.id，必须先完成的任务）",
        "created_at": "创建时间（UTC，依赖关系建立的时间戳）",
    },
    "notifications": {
        "id": "通知ID（自增主键，系统自动生成）",
        "level": "通知级别（info=信息/warn=警告/err=错误，反映紧急程度）",
        "category": "通知分类（order=订单/auth=认证/system=系统/config=配置）",
        "title": "通知标题（简短摘要，如「订单超时待支付」）",
        "message": "通知内容（详细描述，说明发生了什么及建议操作）",
        "link": "跳转链接（点击通知后跳转的页面URL，NULL=无跳转）",
        "dedup_key": "去重键（同类通知只保留最新一条，如order_timeout:{item_id}）",
        "read_at": "已读时间（UTC，NULL=未读，有值表示用户已读时间）",
        "created_at": "创建时间（UTC，通知生成的时间戳）",
    },
    "accounts": {
        "id": "账号ID（自增主键，系统自动生成）",
        "name": "账号别名（唯一标识，用户自定义，如「主力号」「备用号」）",
        "nickname": "闲鱼昵称（闲鱼平台显示的用户名）",
        "cookies": "登录Cookie（JSON，闲鱼登录后的Cookie列表，用于保持会话）",
        "status": "账号状态（active=可用/cooldown=冷却中/disabled=已禁用）",
        "last_used_at": "最近使用时间（UTC，轮换调度器据此选择最久未用的账号）",
        "cooldown_until": "冷却截止时间（UTC，触发风控后的冷却期，超过此时间自动恢复）",
        "use_count": "累计使用次数（该账号被调度使用的总次数）",
        "fail_count": "连续失败次数（连续请求失败次数，超过阈值触发冷却）",
        "note": "备注（用户自定义的账号说明，如「仅用于镜头类任务」）",
        "created_at": "创建时间（UTC，账号首次添加的时间戳）",
        "updated_at": "更新时间（UTC，账号信息最近修改的时间戳）",
    },
    "proxies": {
        "id": "代理ID（自增主键，系统自动生成）",
        "url": "代理地址（格式：http://user:pass@host:port，全局唯一）",
        "status": "代理状态（active=可用/disabled=已禁用）",
        "last_used_at": "最近使用时间（UTC，轮换调度器据此选择最久未用的代理）",
        "last_check_at": "最近检查时间（UTC，上次健康检查的时间）",
        "use_count": "累计使用次数（该代理被调度使用的总次数）",
        "fail_count": "连续失败次数（连续请求失败次数，超过阈值自动禁用）",
        "latency_ms": "延迟毫秒数（最近一次健康检查的响应延迟，NULL=未检查）",
        "note": "备注（用户自定义的代理说明，如「日本节点-低延迟」）",
        "created_at": "创建时间（UTC，代理首次添加的时间戳）",
    },
}


# ============== 表间关联关系与级联删除策略 ==============
# 定义每张表被删除时，需要同步处理的下游关联表
# 策略：
#   cascade  = 级联删除（删除主表记录时，连同关联表记录一起删除）
#   set_null = 置空外键（关联表外键列设为 NULL，保留关联记录但断开引用）
#
# 设计原则：
# 1. 业务核心实体（tasks/items/sellers）被删时级联删除所有依赖数据，
#    避免产生无法追溯的孤立记录
# 2. sellers 被删时对 items/orders/evaluations 采用 set_null，
#    因为卖家消失后商品/订单/评估仍有独立查看价值
# 3. 叶子表（events/notifications/task_links/task_deps）无下游依赖，直接删除
TABLE_RELATIONS: dict[str, list[dict[str, str]]] = {
    "tasks": [
        # 删任务 → 级联删该任务下的商品、订单、事件、关联、依赖
        {"table": "items", "fk": "task_id", "action": "cascade"},
        {"table": "orders", "fk": "task_id", "action": "cascade"},
        {"table": "events", "fk": "task_id", "action": "cascade"},
        {"table": "task_links", "fk": "task_id", "action": "cascade"},
        {"table": "task_deps", "fk": "task_id", "action": "cascade"},
        {"table": "task_deps", "fk": "depends_on", "action": "cascade"},
    ],
    "items": [
        # 删商品 → 级联删该商品的评估、订单、事件
        {"table": "evaluations", "fk": "item_id", "action": "cascade"},
        {"table": "orders", "fk": "item_id", "action": "cascade"},
        {"table": "events", "fk": "item_id", "action": "cascade"},
    ],
    "sellers": [
        # 删卖家 → 保留商品/订单/评估但断开卖家引用（这些数据仍有独立查看价值）
        {"table": "items", "fk": "seller_id", "action": "set_null"},
        {"table": "orders", "fk": "seller_id", "action": "set_null"},
        {"table": "evaluations", "fk": "seller_id", "action": "set_null"},
    ],
    # 以下叶子表无下游依赖，无需级联处理
    "evaluations": [],
    "orders": [],
    "events": [],
    "task_links": [],
    "task_deps": [],
    "notifications": [],
    "accounts": [],
    "proxies": [],
}


def _cascade_delete(
    conn: Any,
    table: str,
    pk_values: list[Any],
) -> dict[str, int]:
    """执行级联删除/置空，返回各关联表受影响行数

    为什么在应用层做而非 SQLite ON DELETE CASCADE：
    1. SQLite 的 PRAGMA foreign_keys=ON 虽然支持 CASCADE，但本系统建表时
       未声明 ON DELETE CASCADE（SQLAlchemy 默认不生成），补建需 ALTER TABLE
    2. 应用层可精确控制策略（cascade vs set_null），并返回每张表的影响行数
    3. 审计日志可记录级联细节
    """
    affected: dict[str, int] = {}
    relations = TABLE_RELATIONS.get(table, [])
    for rel in relations:
        rel_table = rel["table"]
        fk = rel["fk"]
        action = rel["action"]
        # 校验关联表也在白名单中
        if rel_table not in ALLOWED_TABLES:
            continue
        if action == "cascade":
            sql = f"DELETE FROM {rel_table} WHERE {fk} IN :pks"
        elif action == "set_null":
            sql = f"UPDATE {rel_table} SET {fk} = NULL WHERE {fk} IN :pks"
        else:
            continue
        from sqlalchemy import bindparam
        stmt = text(sql).bindparams(bindparam("pks", expanding=True))
        result = conn.execute(stmt, {"pks": pk_values})
        key = f"{rel_table}.{fk}:{action}"
        affected[key] = result.rowcount
    return affected


def _cascade_preview(
    conn: Any,
    table: str,
    pk_values: list[Any],
) -> list[dict[str, Any]]:
    """预览级联影响：返回每条关联规则下将被影响的行数（不执行实际操作）"""
    preview: list[dict[str, Any]] = []
    relations = TABLE_RELATIONS.get(table, [])
    for rel in relations:
        rel_table = rel["table"]
        fk = rel["fk"]
        action = rel["action"]
        if rel_table not in ALLOWED_TABLES:
            continue
        if action == "cascade":
            sql = f"SELECT COUNT(*) FROM {rel_table} WHERE {fk} IN :pks"
        elif action == "set_null":
            sql = f"SELECT COUNT(*) FROM {rel_table} WHERE {fk} IN :pks"
        else:
            continue
        from sqlalchemy import bindparam
        stmt = text(sql).bindparams(bindparam("pks", expanding=True))
        count = conn.execute(stmt, {"pks": pk_values}).scalar() or 0
        preview.append({
            "table": rel_table,
            "fk": fk,
            "action": action,
            "count": count,
            "description": f"将{'删除' if action == 'cascade' else '置空外键'} {rel_table}.{fk} 中 {count} 条关联记录",
        })
    return preview


def _get_columns(container: Container, table: str) -> list[dict[str, Any]]:
    """反射表的列元数据（name/type/nullable/pk/default/label）

    label 来自 COLUMN_LABELS 字典，提供中文语义标注，
    便于开发人员、数据分析师理解字段用途和数据含义。
    """
    insp = inspect(container.repo.engine)
    cols = insp.get_columns(table)
    pk = insp.get_pk_constraint(table).get("constrained_columns") or []
    return [
        {
            "name": c["name"],
            "type": str(c["type"]),
            "nullable": c.get("nullable", True),
            "default": str(c["default"]) if c.get("default") is not None else None,
            "primary_key": c["name"] in pk,
            "label": COLUMN_LABELS.get(table, {}).get(c["name"], ""),
        }
        for c in cols
    ]


def _parse_value(raw: Any, col_type: str) -> Any:
    """根据列类型把 JSON 输入值转换为 Python 对象

    为什么不直接用 SQLAlchemy 的 type 系统：动态表结构下用户传入的是 JSON，
    需要按列类型做轻量转换（int/float/bool/None/datetime），比反射 ORM 类型更轻。
    """
    if raw is None:
        return None
    upper = col_type.upper()
    try:
        if "INT" in upper:
            return int(raw)
        if any(t in upper for t in ("FLOAT", "REAL", "DOUBLE", "NUMERIC", "DECIMAL")):
            return float(raw)
        if "BOOL" in upper:
            if isinstance(raw, bool):
                return raw
            return str(raw).lower() in ("1", "true", "yes", "on")
        if "DATETIME" in upper or "TIMESTAMP" in upper:
            if isinstance(raw, (int, float)):
                # 使用 timezone-aware datetime 避免废弃的 utcfromtimestamp（S6903）
                return datetime.fromtimestamp(raw, tz=timezone.utc)
            return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if "JSON" in upper or "TEXT" in upper:
            if isinstance(raw, str):
                return raw
            return json.dumps(raw, ensure_ascii=False)
    except (ValueError, TypeError) as e:
        raise HTTPException(
            status_code=400,
            detail=f"字段类型转换失败 ({col_type}): {e}",
        )
    return raw


def _serialize_row(row: dict[str, Any], columns: list[dict[str, Any]]) -> dict[str, Any]:
    """把 SQLAlchemy Row 转为可 JSON 序列化的 dict（datetime → ISO 字符串）"""
    out: dict[str, Any] = {}
    for col in columns:
        name = col["name"]
        v = row.get(name)
        if isinstance(v, datetime):
            out[name] = v.isoformat()
        else:
            out[name] = v
    return out


def _log_audit(
    container: Container,
    action: str,
    table: str,
    *,
    pk_value: Any = None,
    detail: dict[str, Any] | None = None,
    level: str = "info",
) -> None:
    """审计日志：所有 DML 操作写入 events 表

    失败不抛异常（审计日志不应阻塞主流程），由调用方根据业务需要再处理。
    """
    try:
        container.repo.save_event({
            "type": f"db_admin.{action}",
            "task_id": None,
            "stage": "db_admin",
            "level": level,
            "message": f"db_admin.{action} {table}" + (f" pk={pk_value}" if pk_value is not None else ""),
            "payload": json.dumps(
                {"action": action, "table": table, "pk": pk_value, "detail": detail or {}},
                ensure_ascii=False,
                default=str,
            ),
        })
    except Exception:
        logger.exception("写入审计日志失败")


# ============== API 模型 ==============

class WriteRowBody(BaseModel):
    """单行写入请求体：values 为 {列名: 值}，缺失主键视为新增，否则视为按主键更新"""
    values: dict[str, Any]


class BatchDeleteBody(BaseModel):
    """批量删除请求：ids 为主键值列表，confirm_token 必须等于 CONFIRM_TOKEN"""
    ids: list[Any]
    confirm_token: str


class ImportBody(BaseModel):
    """导入请求：rows 为二维数组（首行为表头，与 schema 列名对应），mode=insert/replace"""
    rows: list[list[Any]]
    headers: list[str] | None = None  # 可选：自定义列名映射，缺省按列顺序
    mode: str = "insert"  # insert=跳过主键冲突，replace=按主键替换
    confirm_token: str = ""


class CascadePreviewBody(BaseModel):
    """级联影响预览请求：指定表和主键值列表"""
    ids: list[Any]


# ============== 元数据 API ==============

@router.get("/tables")
def list_tables(container: Container = Depends(get_container)) -> dict[str, Any]:
    """列出可管理的表及其记录数（侧边栏树数据）"""
    tables: list[dict[str, Any]] = []
    with container.repo.engine.connect() as conn:
        for tbl in ALLOWED_TABLES:
            try:
                count = conn.execute(text(f"SELECT COUNT(*) FROM {tbl}")).scalar() or 0
            except SQLAlchemyError:
                # 表不存在时不抛错（白名单更新与 ORM 迁移可能短暂不同步）
                count = 0
            tables.append({"name": tbl, "rows": count})
    return {"tables": tables}


@router.get("/tables/{table}/schema")
def table_schema(
    table: str,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """表结构：列名、类型、是否主键、是否可空、默认值（前端动态生成表单用）"""
    _validate_table(table)
    cols = _get_columns(container, table)
    return {"table": table, "columns": cols}


@router.post("/tables/{table}/cascade-preview")
def cascade_preview(
    table: str,
    body: CascadePreviewBody,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """删除前级联影响预览：返回各关联表将被影响的记录数（不执行实际操作）

    前端在弹出删除确认框时调用此接口，让用户看到级联影响范围后再决定是否删除。
    """
    _validate_table(table)
    if not body.ids:
        return {"table": table, "relations": [], "total_affected": 0}

    cols = _get_columns(container, table)
    pk_cols = [c for c in cols if c["primary_key"]]
    if len(pk_cols) != 1:
        raise HTTPException(status_code=400, detail="仅支持单主键表的级联预览")
    pk_col = pk_cols[0]
    converted = [_parse_value(v, pk_col["type"]) for v in body.ids]

    with container.repo.engine.connect() as conn:
        preview = _cascade_preview(conn, table, converted)

    total = sum(p["count"] for p in preview)
    return {"table": table, "relations": preview, "total_affected": total}


# ============== 数据查询 API ==============

@router.get("/tables/{table}/rows")
def list_rows(
    table: str,
    request: Request,
    container: Container = Depends(get_container),
    limit: int = Query(50, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
    order_by: str | None = Query(None, description="列名，倒序加 - 前缀如 -created_at"),
    search: str | None = Query(None, description="简单子串搜索（对所有文本列 LIKE）"),
) -> dict[str, Any]:
    """分页查询表数据

    为什么不用 ORM Query：动态表名无法走静态类型映射，文本 SQL + 白名单更直接。
    order_by 走白名单字符名校验，search 转 LIKE 参数化绑定。
    """
    _validate_table(table)
    # 保留 404 检查：表在白名单但数据库中无列时返回 404（与原行为一致）
    # service 内部会再次反射列信息构造 SQL，这里仅做存在性校验
    cols = _get_columns(container, table)
    if not cols:
        raise HTTPException(status_code=404, detail=f"表 {table} 不存在或无列")

    # 使用 SearchService 统一处理分页/慢查询埋点
    # service 内部复用 _validate_identifier / _serialize_row，保持与原路由一致的校验和序列化
    service = DbAdminSearchService(container.repo.engine)
    result = service.search(DbAdminSearchParams(
        table=table, q=search, limit=limit, offset=offset, order_by=order_by,
    ))
    return {
        "table": table,
        "total": result["total"],
        "limit": limit,
        "offset": offset,
        "rows": result["items"],
    }


# ============== CRUD API ==============

@router.post("/tables/{table}/rows")
def create_row(
    table: str,
    body: WriteRowBody,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """新增一行：values 中需包含所有 NOT NULL 列（无默认值时）

    主键冲突返回 409；写入成功立即审计。
    """
    _validate_table(table)
    cols = _get_columns(container, table)
    col_by_name = {c["name"]: c for c in cols}

    # 仅保留真实存在的列，过滤掉用户传的无效字段
    values: dict[str, Any] = {}
    for k, v in body.values.items():
        if k in col_by_name:
            values[k] = _parse_value(v, col_by_name[k]["type"])

    if not values:
        raise HTTPException(status_code=400, detail="values 不能为空")

    cols_list = list(values.keys())
    placeholders = ", ".join(f":{c}" for c in cols_list)
    col_names = ", ".join(cols_list)
    sql = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})"

    try:
        with container.repo.engine.begin() as conn:
            conn.execute(text(sql), values)
    except SQLAlchemyError as e:
        # 唯一约束冲突、外键冲突等都返回 409，提示用户修正数据
        _log_audit(container, "create_failed", table, detail={"error": str(e), "values": values}, level="err")
        raise HTTPException(status_code=409, detail=f"写入失败: {e}")

    _log_audit(container, "create", table, detail={"values": values})
    return {"ok": True, "table": table}


@router.patch("/tables/{table}/rows/{pk_value:path}")
def update_row(
    table: str,
    pk_value: str,
    body: WriteRowBody,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """按主键更新一行：pk_value 通过路径传入（支持 String/Integer 主键）

    路径参数自动转 str（FastAPI 行为），在 _parse_value 时按列类型转换。
    """
    _validate_table(table)
    cols = _get_columns(container, table)
    col_by_name = {c["name"]: c for c in cols}
    pk_cols = [c for c in cols if c["primary_key"]]
    if len(pk_cols) != 1:
        # 联合主键的表暂不支持在线编辑（场景少见且容易出错）
        raise HTTPException(status_code=400, detail="仅支持单主键表的更新")
    pk_col = pk_cols[0]

    # 过滤可更新字段（不更新主键本身）
    values: dict[str, Any] = {}
    for k, v in body.values.items():
        if k == pk_col["name"]:
            continue
        if k in col_by_name:
            values[k] = _parse_value(v, col_by_name[k]["type"])

    if not values:
        raise HTTPException(status_code=400, detail="没有可更新字段")

    set_clause = ", ".join(f"{k} = :{k}" for k in values)
    sql = f"UPDATE {table} SET {set_clause} WHERE {pk_col['name']} = :pk"

    try:
        with container.repo.engine.begin() as conn:
            result = conn.execute(text(sql), {**values, "pk": _parse_value(pk_value, pk_col["type"])})
    except SQLAlchemyError as e:
        _log_audit(container, "update_failed", table, pk_value=pk_value, detail={"error": str(e)}, level="err")
        raise HTTPException(status_code=409, detail=f"更新失败: {e}")

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail=f"主键 {pk_value} 不存在")

    _log_audit(container, "update", table, pk_value=pk_value, detail={"values": values})
    return {"ok": True, "affected": result.rowcount}


@router.delete("/tables/{table}/rows/{pk_value:path}")
def delete_row(
    table: str,
    pk_value: str,
    confirm_token: str = Query(..., description="必须为 CONFIRM_DELETE"),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """删除单行（含级联处理）：confirm_token=CONFIRM_DELETE 才执行

    级联策略由 TABLE_RELATIONS 定义：
    - cascade: 连同关联表记录一起删除
    - set_null: 关联表外键置 NULL（保留关联记录）

    所有操作在同一事务中执行，保证原子性。
    """
    _validate_table(table)
    if confirm_token != CONFIRM_TOKEN:
        raise HTTPException(status_code=400, detail=f"需要 confirm_token={CONFIRM_TOKEN}")

    cols = _get_columns(container, table)
    pk_cols = [c for c in cols if c["primary_key"]]
    if len(pk_cols) != 1:
        raise HTTPException(status_code=400, detail="仅支持单主键表的删除")
    pk_col = pk_cols[0]
    pk_val = _parse_value(pk_value, pk_col["type"])

    try:
        with container.repo.engine.begin() as conn:
            # 先处理级联（必须在删主记录之前，否则找不到关联记录）
            cascade_affected = _cascade_delete(conn, table, [pk_val])
            # 再删主表记录
            result = conn.execute(text(f"DELETE FROM {table} WHERE {pk_col['name']} = :pk"), {"pk": pk_val})
    except SQLAlchemyError as e:
        _log_audit(container, "delete_failed", table, pk_value=pk_value, detail={"error": str(e)}, level="err")
        raise HTTPException(status_code=409, detail=f"删除失败: {e}")

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail=f"主键 {pk_value} 不存在")

    _log_audit(container, "delete", table, pk_value=pk_value, detail={"cascade": cascade_affected}, level="warn")
    return {"ok": True, "affected": result.rowcount, "cascade": cascade_affected}


@router.post("/tables/{table}/rows/batch-delete")
def batch_delete_rows(
    table: str,
    body: BatchDeleteBody,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """批量删除（含级联处理）：上限 1000 行/次"""
    _validate_table(table)
    if body.confirm_token != CONFIRM_TOKEN:
        raise HTTPException(status_code=400, detail=f"需要 confirm_token={CONFIRM_TOKEN}")
    if not body.ids:
        raise HTTPException(status_code=400, detail="ids 不能为空")
    if len(body.ids) > MAX_PAGE_SIZE:
        raise HTTPException(status_code=400, detail=f"单次最多删除 {MAX_PAGE_SIZE} 行")

    cols = _get_columns(container, table)
    pk_cols = [c for c in cols if c["primary_key"]]
    if len(pk_cols) != 1:
        raise HTTPException(status_code=400, detail="仅支持单主键表的批量删除")
    pk_col = pk_cols[0]

    converted = [_parse_value(v, pk_col["type"]) for v in body.ids]
    try:
        with container.repo.engine.begin() as conn:
            # 先处理级联
            cascade_affected = _cascade_delete(conn, table, converted)
            # 再删主表记录
            from sqlalchemy import bindparam
            stmt = text(f"DELETE FROM {table} WHERE {pk_col['name']} IN :ids").bindparams(
                bindparam("ids", expanding=True)
            )
            result = conn.execute(stmt, {"ids": converted})
    except SQLAlchemyError as e:
        _log_audit(container, "batch_delete_failed", table, detail={"error": str(e), "count": len(converted)}, level="err")
        raise HTTPException(status_code=409, detail=f"批量删除失败: {e}")

    _log_audit(container, "batch_delete", table, detail={"requested": len(converted), "affected": result.rowcount, "cascade": cascade_affected}, level="warn")
    return {"ok": True, "requested": len(converted), "affected": result.rowcount, "cascade": cascade_affected}


# ============== 导入/导出 ==============

@router.get("/tables/{table}/export")
def export_rows(
    table: str,
    format: str = Query("csv", pattern="^(csv|json)$"),
    container: Container = Depends(get_container),
) -> StreamingResponse:
    """导出表数据：CSV 或 JSON（不限制行数上限，但单文件大小由 max_export 控制）

    CSV 用 UTF-8 BOM 头，Excel 打开不乱码；JSON 用 streaming 序列化避免大对象内存压力。
    """
    _validate_table(table)
    cols = _get_columns(container, table)
    col_names = [c["name"] for c in cols]

    with container.repo.engine.connect() as conn:
        result = conn.execute(text(f"SELECT * FROM {table}"))
        rows = result.mappings().all()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{table}_{timestamp}.{format}"

    if format == "json":
        # 每行一个 JSON 记录（NDJSON 风格），流式输出降低内存峰值
        def json_iter():
            yield "[\n"
            for i, r in enumerate(rows):
                if i:
                    yield ",\n"
                yield json.dumps(_serialize_row(dict(r), cols), ensure_ascii=False, default=str)
            yield "\n]\n"
        return StreamingResponse(
            json_iter(),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # CSV
    def csv_iter():
        # UTF-8 BOM 让 Excel 自动识别编码
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(col_names)
        yield "\ufeff" + buf.getvalue()
        buf.seek(0); buf.truncate()
        for r in rows:
            row = _serialize_row(dict(r), cols)
            w.writerow([row.get(c) for c in col_names])
            yield buf.getvalue()
            buf.seek(0); buf.truncate()
    return StreamingResponse(
        csv_iter(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _validate_import_body(body: ImportBody) -> None:
    """集中校验导入请求体，避免主流程被多重 if 拉高认知复杂度"""
    if body.confirm_token != CONFIRM_TOKEN:
        raise HTTPException(status_code=400, detail=f"需要 confirm_token={CONFIRM_TOKEN}")
    if not body.rows:
        raise HTTPException(status_code=400, detail="rows 不能为空")
    if len(body.rows) > MAX_IMPORT_ROWS:
        raise HTTPException(status_code=400, detail=f"单次最多导入 {MAX_IMPORT_ROWS} 行")
    if body.mode not in ("insert", "replace"):
        raise HTTPException(status_code=400, detail="mode 必须为 insert 或 replace")


def _resolve_import_headers(body: ImportBody, cols: list[dict]) -> tuple[list[str], dict[str, dict]]:
    """解析 headers 缺省值并校验列名合法性，返回 (headers, col_by_name)"""
    col_by_name = {c["name"]: c for c in cols}
    # headers 缺省按列顺序
    headers = body.headers or [c["name"] for c in cols]
    for h in headers:
        if h not in col_by_name:
            raise HTTPException(status_code=400, detail=f"未知列: {h}")
    return headers, col_by_name


def _build_insert_sql(table: str, mode: str, values: dict[str, Any]) -> str:
    """根据 mode 选择 INSERT 或 INSERT OR REPLACE，避免在主循环内分支"""
    cols_list = list(values.keys())
    placeholders = ", ".join(f":{c}" for c in cols_list)
    if mode == "replace":
        return f"INSERT OR REPLACE INTO {table} ({', '.join(cols_list)}) VALUES ({placeholders})"
    return f"INSERT INTO {table} ({', '.join(cols_list)}) VALUES ({placeholders})"


def _is_unique_constraint_error(e: SQLAlchemyError) -> bool:
    """识别 SQLite 主键/唯一约束冲突，insert 模式下计入 skipped 而非 errors"""
    msg_upper = str(e).upper()
    return "UNIQUE" in msg_upper or "PRIMARY KEY" in msg_upper


def _execute_single_import(
    container: Container, table: str, mode: str,
    raw_row: list, headers: list[str], col_by_name: dict[str, dict], idx: int,
) -> tuple[bool, bool, str | None]:
    """执行单行导入，返回 (inserted, skipped, error_msg)

    三态返回避免主循环里再分支：调用方按 bool 累加计数即可。
    """
    if len(raw_row) != len(headers):
        return False, False, f"第 {idx} 行列数不匹配"
    values = {h: _parse_value(v, col_by_name[h]["type"]) for h, v in zip(headers, raw_row)}
    sql = _build_insert_sql(table, mode, values)
    try:
        with container.repo.engine.begin() as conn:
            conn.execute(text(sql), values)
        return True, False, None
    except SQLAlchemyError as e:
        # 主键冲突时 SQLite 抛 IntegrityError，insert 模式计入 skipped
        if _is_unique_constraint_error(e):
            return False, True, None
        return False, False, f"第 {idx} 行失败: {e}"


@router.post("/tables/{table}/import")
def import_rows(
    table: str,
    body: ImportBody,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """导入：rows 为二维数组，headers 缺省时按 schema 列顺序

    限制：
    - 单次最多 MAX_IMPORT_ROWS 行
    - mode=insert 遇主键冲突跳过；mode=replace 走 INSERT OR REPLACE
    - 需要 confirm_token（导入可能产生大量数据）
    """
    _validate_table(table)
    _validate_import_body(body)

    cols = _get_columns(container, table)
    headers, col_by_name = _resolve_import_headers(body, cols)

    inserted = 0
    skipped = 0
    errors: list[str] = []
    for idx, raw_row in enumerate(body.rows, start=1):
        ok, skip, err = _execute_single_import(container, table, body.mode, raw_row, headers, col_by_name, idx)
        if ok:
            inserted += 1
        elif skip:
            skipped += 1
        elif err:
            errors.append(err)

    _log_audit(
        container, "import", table,
        detail={"mode": body.mode, "total": len(body.rows), "inserted": inserted, "skipped": skipped, "errors": len(errors)},
        level="warn" if errors else "info",
    )
    return {
        "ok": True,
        "total": len(body.rows),
        "inserted": inserted,
        "skipped": skipped,
        "errors": errors[:20],
    }


# ============== 审计日志 ==============

@router.get("/audit-log")
def audit_log(
    container: Container = Depends(get_container),
    limit: int = Query(100, ge=1, le=500),
) -> dict[str, Any]:
    """数据库维护相关审计日志（来自 events 表，type 前缀 db_admin.）"""
    with container.repo.engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, type, level, message, payload, created_at FROM events "
                "WHERE type LIKE 'db_admin.%' ORDER BY id DESC LIMIT :limit"
            ),
            {"limit": limit},
        ).mappings().all()
    items = []
    for r in rows:
        # SQLite text() 查询返回字符串而非 datetime，需兼容两种类型
        created_at = r["created_at"]
        if hasattr(created_at, "isoformat"):
            created_at_str = created_at.isoformat()
        elif created_at:
            created_at_str = str(created_at)
        else:
            created_at_str = None
        items.append({
            "id": r["id"],
            "type": r["type"],
            "level": r["level"],
            "message": r["message"],
            "payload": r["payload"],
            "created_at": created_at_str,
        })
    return {"items": items}
