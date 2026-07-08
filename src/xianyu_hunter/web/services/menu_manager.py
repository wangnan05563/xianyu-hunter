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
import threading
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


def _utcnow_iso() -> str:
    """返回 ISO8601 格式的当前 UTC 时间"""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


class MenuManager:
    """菜单配置管理器：加载 registry + 用户级覆盖合并

    职责边界：
    - 只负责菜单可见性/排序的读写与合并，不感知前端分组结构；
    - registry 字段（key/label/icon/path/sort_order/default_visible/category）
      与 user_menu_configs 字段（visible/sort_order）通过 key 关联；
    - 合并后输出字段统一为 visible/sort_order（与 PUT API 入参对齐）。
    """

    def __init__(self, engine: Engine, registry_path: Path | str = _REGISTRY_PATH) -> None:
        self._engine = engine
        self._registry_path = Path(registry_path)
        # 内部锁：保护 update/reset 操作的读改写临界区
        # get_menus 为只读且无副作用，无需持锁，依赖 SQLite 自身的并发控制
        self._lock = threading.RLock()
        self._registry: list[dict[str, Any]] = []
        self._load_registry()

    # ---------- 内部加载 ----------

    def _load_registry(self) -> None:
        """从 config/menu_registry.yaml 加载默认菜单配置

        为什么在 __init__ 中加载而非延迟加载：YAML 文件小（<10KB），
        一次性加载避免每次 get_menus 都读文件 IO；启动时加载失败可立即暴露。
        """
        if not self._registry_path.exists():
            logger.warning("菜单注册表不存在: %s，使用空列表兜底", self._registry_path)
            self._registry = []
            return
        try:
            with open(self._registry_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError) as e:
            # YAML 解析失败不阻塞服务启动，使用空 registry 让前端展示空菜单
            logger.error("菜单注册表加载失败: %s", e, exc_info=True)
            self._registry = []
            return
        self._registry = list(data.get("menus", []))
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
        """
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
        return [m for m in merged if m["visible"]]

    def update_menu_config(self, user_id: str, menus: list[dict[str, Any]]) -> None:
        """更新用户菜单配置（UPSERT）

        入参：[{key, visible, sort_order}, ...]
        为什么逐条 UPSERT 而非批量 DELETE+INSERT：
        - DELETE+INSERT 在事务中需持锁更久，且会丢失未在本次请求中携带的菜单项配置；
        - UPSERT 仅更新本次显式提交的项，保留用户对其他项的既有配置。
        """
        if not menus:
            return

        with self._lock:
            now = _utcnow_iso()
            with self._engine.begin() as conn:
                for m in menus:
                    key = str(m.get("key", "")).strip()
                    if not key:
                        continue
                    visible = 1 if bool(m.get("visible", True)) else 0
                    sort_order = int(m.get("sort_order", 0))
                    # SQLite 的 INSERT OR REPLACE 会按主键冲突替换整行
                    # 主键 (user_id, menu_key) 已在 db_models.UserMenuConfigRow 定义
                    conn.execute(
                        sa_text(
                            "INSERT OR REPLACE INTO user_menu_configs "
                            "(user_id, menu_key, visible, sort_order, updated_at) "
                            "VALUES (:uid, :key, :vis, :sort, :now)"
                        ),
                        {
                            "uid": user_id,
                            "key": key,
                            "vis": visible,
                            "sort": sort_order,
                            "now": now,
                        },
                    )
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
        logger.info("用户菜单配置已重置: user_id=%s", user_id)


# 全局单例
_manager: MenuManager | None = None
_manager_lock = threading.Lock()


def get_menu_manager() -> MenuManager:
    """获取全局 MenuManager 单例

    延迟初始化：首次调用时创建 engine 并加载 registry，
    避免在 import 阶段触发文件 IO 影响模块加载速度。

    与 get_user_manager 共享 _DB_PATH，但独立创建 engine：
    MenuManager 的查询路径短（仅 user_menu_configs 单表），
    NullPool/QueuePool 每次连接开销可接受，无需复用 UserManager 的连接池。
    """
    global _manager
    with _manager_lock:
        if _manager is None:
            from xianyu_hunter.infra.db_models import create_sqlite_engine, init_db
            # 延迟调用 init_db 确保 user_menu_configs 表存在
            init_db(_DB_PATH)
            engine = create_sqlite_engine(_DB_PATH)
            _manager = MenuManager(engine)
        return _manager
