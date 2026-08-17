"""菜单配置管理器：合并 registry 默认值 + 用户级覆盖。

设计：
- menu_registry.yaml 是菜单元数据单一事实源（默认值）；
- user_menu_configs 表存用户级覆盖（visible/sort_order）；
- 查询时合并两者，用户配置优先；
- 单例模式（get_menu_manager），全局唯一实例，复用 UserManager 的 engine
  避免独立连接池造成 SQLite 多连接开销。

设计文档：docs/07-权限模块/2026-07-01-登录模块优化概要设计.md §3.2.4 / §5.4
"""
from __future__ import annotations

import logging
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import text as sa_text
from sqlalchemy.engine import Engine

# menu_registry.yaml 是只读资源（随安装包分发），应从安装目录读取
# 为什么不用 get_config_dir()：那是可写目录（%APPDATA%），registry 不应运行时修改
# 为什么不用 Path("config/menu_registry.yaml")：打包后 CWD 不确定，相对路径找不到文件
from xianyu_hunter.paths import get_app_dir, get_data_dir

logger = logging.getLogger(__name__)

# 默认 SQLite 数据库路径：与 user_manager 共用同一实例
_DB_PATH = str(get_data_dir() / "xianyu.db")

# 菜单注册表路径：从安装目录读取（只读资源，随安装包分发）
_REGISTRY_PATH = get_app_dir() / "config" / "menu_registry.yaml"

# get_menus 缓存 TTL：60 秒内重复查询命中缓存，避免高频菜单拉取打 DB
# 为什么 60s：菜单变更频率极低（用户主动调整），60s 足以覆盖一次会话的连续刷新
_CACHE_TTL = 60.0


def _utcnow() -> datetime:
    """返回当前 UTC 时间（datetime 对象）

    为什么返回 datetime 而非 ISO 字符串：
    ORM 的 UserMenuConfigRow.updated_at default=_utcnow 返回 datetime，
    raw SQL 也传 datetime 才能保证存储格式一致（避免混合存储导致排序/比较异常）。
    SQLAlchemy 的 DateTime 类型会自动将 datetime 序列化为 SQLite 兼容格式。
    """
    return datetime.now(timezone.utc)


def _resolve_registry_path() -> Path:
    """解析 menu_registry.yaml 的实际路径，兼容开发/打包两种模式

    为什么需要 fallback：PyInstaller 打包后 _REGISTRY_PATH（基于 get_app_dir）
    指向 exe 所在目录，但实际资源被解压到 sys._MEIPASS 临时目录下。
    没有此 fallback 时打包版会找不到 yaml 而使用空 registry，前端菜单为空。
    """
    candidate = _REGISTRY_PATH
    if candidate.exists():
        return candidate
    # PyInstaller 打包模式：资源在 _MEIPASS 临时解压目录下
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        packaged = Path(meipass) / "config" / "menu_registry.yaml"
        if packaged.exists():
            return packaged
    return candidate


class MenuManager:
    """菜单配置管理器：加载 registry + 用户级覆盖合并

    职责边界：
    - 只负责菜单可见性/排序的读写与合并，不感知前端分组结构；
    - registry 字段（key/label/icon/path/sort_order/default_visible/category）
      与 user_menu_configs 字段（visible/sort_order）通过 key 关联；
    - 合并后输出字段统一为 visible/sort_order（与 PUT API 入参对齐）。
    """

    def __init__(self, engine: Engine, registry_path: Path | str | None = None) -> None:
        self._engine = engine
        # registry_path 仅用于测试注入；生产路径由 _resolve_registry_path 解析
        self._registry_path = Path(registry_path) if registry_path is not None else None
        # 内部锁：保护 update/reset 操作的读改写临界区 + 缓存失效
        # get_menus 为只读且无副作用，无需持锁，依赖 SQLite 自身的并发控制
        self._lock = threading.RLock()
        self._registry: list[dict[str, Any]] = []
        # get_menus 结果缓存：user_id → (timestamp, merged_list)
        # 为什么用 dict 而非 lru_cache：需要按 user_id 精细失效，lru_cache 不支持
        self._cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
        self._load_registry()

    # ---------- 内部加载 ----------

    def _load_registry(self) -> None:
        """从 config/menu_registry.yaml 加载默认菜单配置

        为什么在 __init__ 中加载而非延迟加载：YAML 文件小（<10KB），
        一次性加载避免每次 get_menus 都读文件 IO；启动时加载失败可立即暴露。
        """
        # 路径解析：优先用测试注入路径，否则走 _resolve_registry_path 兼容打包模式
        if self._registry_path is not None:
            path = self._registry_path
        else:
            path = _resolve_registry_path()

        if not path.exists():
            logger.warning("菜单注册表不存在: %s，使用空列表兜底", path)
            self._registry = []
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError) as e:
            # YAML 解析失败不阻塞服务启动，使用空 registry 让前端展示空菜单
            logger.error("菜单注册表加载失败: %s", e, exc_info=True)
            self._registry = []
            return
        # 类型校验：menus 字段必须是 list，否则 list("string") 会拆成字符列表，
        # 后续 item.get() 调用会抛 AttributeError 中断启动
        menus = data.get("menus", [])
        if not isinstance(menus, list):
            logger.error(
                "menu_registry.yaml 的 menus 字段必须是列表，实际: %s，使用空列表兜底",
                type(menus).__name__,
            )
            self._registry = []
            return
        self._registry = menus
        logger.info("已加载菜单注册表: %d 项", len(self._registry))

    def _load_user_configs(self, user_id: str) -> dict[str, dict[str, Any]]:
        """读取用户级菜单覆盖

        返回 {menu_key: {visible, sort_order}} 字典，便于 O(1) 查找合并。
        """
        result: dict[str, dict[str, Any]] = {}
        with self._engine.connect() as conn:
            rows = conn.execute(
                sa_text(
                    "SELECT menu_key, visible, sort_order FROM user_menu_configs WHERE user_id = :uid"
                ),
                {"uid": user_id},
            ).all()
            for row in rows:
                result[row[0]] = {
                    "visible": bool(row[1]),
                    "sort_order": int(row[2]),
                }
        return result

    # ---------- 公共 API ----------

    def get_menus(self, user_id: str) -> list[dict[str, Any]]:
        """获取用户菜单（合并 registry 默认值 + 用户级覆盖）

        合并规则：
        1. 以 registry 默认值为基底；
        2. 用户配置覆盖 visible / sort_order；
        3. 按 sort_order 升序排列；
        4. 仅返回 visible=True 的项；
        5. 用户无配置时返回 registry 默认值（default_visible=True 的项）。

        缓存：60 秒 TTL，update_menu_config / reset_menu_config 主动失效。
        为什么不在缓存命中时返回拷贝：调用方只读消费，未观察到外部 mutate 行为，
        避免深拷贝开销；如未来需要外部修改，再调整为返回 copy.deepcopy。
        """
        cached = self._cache.get(user_id)
        if cached and (time.time() - cached[0]) < _CACHE_TTL:
            return cached[1]

        user_configs = self._load_user_configs(user_id)

        merged: list[dict[str, Any]] = []
        for item in self._registry:
            key = item.get("key", "")
            default_visible = bool(item.get("default_visible", True))
            default_sort = int(item.get("sort_order", 0))
            # 输出字段与 PUT API 入参对齐：visible / sort_order
            # 同时保留 registry 的展示字段（label/icon/path/category）供前端直接渲染
            merged_item: dict[str, Any] = {
                "key": key,
                "label": item.get("label", ""),
                "icon": item.get("icon", ""),
                "path": item.get("path", ""),
                "category": item.get("category", ""),
                "visible": default_visible,
                "sort_order": default_sort,
            }
            uc = user_configs.get(key)
            if uc is not None:
                # 用户级覆盖优先：仅覆盖 visible/sort_order 两个字段
                merged_item["visible"] = uc["visible"]
                merged_item["sort_order"] = uc["sort_order"]
            merged.append(merged_item)

        # 排序在过滤前完成，保证 hidden 项不影响可见项的相对顺序
        merged.sort(key=lambda x: x["sort_order"])
        merged = [m for m in merged if m["visible"]]

        # 写入缓存：dict 读写原子性由 GIL 保证，无需持锁
        self._cache[user_id] = (time.time(), merged)
        return merged

    def update_menu_config(self, user_id: str, menus: list[dict[str, Any]]) -> None:
        """更新用户菜单配置（UPSERT）

        入参：[{key, visible, sort_order}, ...]
        为什么逐条 UPSERT 而非批量 DELETE+INSERT：
        - DELETE+INSERT 在事务中需持锁更久，且会丢失未在本次请求中携带的菜单项配置；
        - UPSERT 仅更新本次显式提交的项，保留用户对其他项的既有配置。
        """
        if not menus:
            return

        # menu_key 白名单校验：阻止未在 registry 中定义的 key 写入 DB
        # 为什么校验：registry 是菜单元数据单一事实源，写入未定义 key 会留下
        # 孤儿记录（前端永远拿不到对应菜单项），且增加 DB 体积无业务价值
        valid_keys = {item.get("key") for item in self._registry if item.get("key")}

        with self._lock:
            now = _utcnow()
            with self._engine.begin() as conn:
                for m in menus:
                    key = str(m.get("key", "")).strip()
                    if not key or key not in valid_keys:
                        logger.warning("跳过未知 menu_key: %s", key)
                        continue
                    visible = 1 if bool(m.get("visible", True)) else 0
                    sort_order = int(m.get("sort_order", 0))
                    # 使用 ON CONFLICT 而非 INSERT OR REPLACE：
                    # INSERT OR REPLACE 在 UNIQUE 冲突时会先删除整行再插入新行，
                    # 导致未在 SQL 中指定的 group_name/custom_label 被重置为默认值（空串）。
                    # ON CONFLICT DO UPDATE 仅更新指定列，保留 group_name/custom_label 既有值。
                    # 主键 (user_id, menu_key) 已在 db_models.UserMenuConfigRow 定义
                    conn.execute(
                        sa_text(
                            "INSERT INTO user_menu_configs "
                            "(user_id, menu_key, visible, sort_order, updated_at) "
                            "VALUES (:uid, :key, :vis, :sort, :now) "
                            "ON CONFLICT(user_id, menu_key) DO UPDATE SET "
                            "visible=:vis, sort_order=:sort, updated_at=:now"
                        ),
                        {
                            "uid": user_id,
                            "key": key,
                            "vis": visible,
                            "sort": sort_order,
                            "now": now,
                        },
                    )
            # 写操作完成后失效该用户的缓存，下次 get_menus 重新从 DB 读取
            # 为什么在锁内失效：避免与并发 update/reset 产生缓存与 DB 不一致窗口
            self._cache.pop(user_id, None)
        logger.info("用户菜单配置已更新: user_id=%s, 项数=%d", user_id, len(menus))

    def reset_menu_config(self, user_id: str) -> None:
        """重置用户菜单为默认配置

        删除 user_menu_configs 中该用户的所有记录，
        下次 get_menus 会回退到 registry 默认值。
        """
        with self._lock:
            with self._engine.begin() as conn:
                conn.execute(
                    sa_text("DELETE FROM user_menu_configs WHERE user_id = :uid"),
                    {"uid": user_id},
                )
            # 失效缓存：reset 后下次 get_menus 应回退到 registry 默认值
            self._cache.pop(user_id, None)
        logger.info("用户菜单配置已重置: user_id=%s", user_id)


# 全局单例
_manager: MenuManager | None = None
_manager_lock = threading.Lock()


def get_menu_manager() -> MenuManager:
    """获取全局 MenuManager 单例

    延迟初始化：首次调用时复用 UserManager 的 engine 并加载 registry，
    避免在 import 阶段触发文件 IO 影响模块加载速度。

    为什么复用 UserManager 的 engine：
    - SQLite 多连接模式下，独立 engine 会创建独立连接池，WAL 模式下虽不会死锁，
      但连接池各自维护 PRAGMA 和生命周期，增加内存与文件描述符开销；
    - 复用 engine 让 user_manager / menu_manager / preferences 共享同一连接池，
      单连接开销摊薄到所有模块，符合 SQLite 单写多读模型。
    """
    global _manager
    with _manager_lock:
        if _manager is None:
            from xianyu_hunter.infra.db_models import init_db
            from xianyu_hunter.web.services.user_manager import get_user_manager
            # 延迟调用 init_db 确保 user_menu_configs 表存在
            # 为什么仍要 init_db：get_user_manager 内部已调用，但显式调用确保
            # 即使 get_user_manager 实现变化（移除内部 init_db），MenuManager 仍可用
            init_db(_DB_PATH)
            _manager = MenuManager(get_user_manager().engine)
        return _manager
