"""Cookie 分层管理器（设计文档 §4.6）

核心问题：现有 Cookie 写入多域名但未处理 Cookie 之间的依赖关系
（如 _m_h5_tk 更新时 _m_h5_tk_enc 必须同步）。

解决方案：Cookie 分层管理 + 原子更新。

分层定义：
- identity（身份层）：最稳定，仅登录时变化
  cookies: unb, cookie2, sgcookie, t, _tb_token_
  depends_on: 无

- session（会话层）：中等频率更新
  cookies: _m_h5_tk, _m_h5_tk_enc
  depends_on: identity  # 身份失效时会话必然失效

- tracking（追踪层）：每次请求可能变化
  cookies: cna, tfstk, xlly_s, ali_aplus_v3
  depends_on: 无

原子更新规则：
1. 同一层的 Cookie 必须同时写入，不允许中间状态
2. 更新 session 层时必须验证 identity 层是否有效
3. identity 层失效时，session 层自动失效
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from xianyu_hunter.infra.logger import get_logger

logger = get_logger()


class CookieLayer(str, Enum):
    """Cookie 分层"""
    IDENTITY = "identity"    # 身份层：最稳定
    SESSION = "session"      # 会话层：中等频率
    TRACKING = "tracking"    # 追踪层：每次请求可能变化


@dataclass
class LayerDefinition:
    """层定义"""
    name: CookieLayer
    cookies: set[str]           # 该层包含的 Cookie 名称
    ttl: str                    # TTL 描述
    depends_on: CookieLayer | None = None  # 依赖的层


# 层定义注册表
LAYER_DEFINITIONS: dict[CookieLayer, LayerDefinition] = {
    CookieLayer.IDENTITY: LayerDefinition(
        name=CookieLayer.IDENTITY,
        cookies={"unb", "cookie2", "sgcookie", "t", "_tb_token_", "lg2"},
        ttl="session",
        depends_on=None,
    ),
    CookieLayer.SESSION: LayerDefinition(
        name=CookieLayer.SESSION,
        cookies={"_m_h5_tk", "_m_h5_tk_enc"},
        ttl="15-22min",
        depends_on=CookieLayer.IDENTITY,
    ),
    CookieLayer.TRACKING: LayerDefinition(
        name=CookieLayer.TRACKING,
        cookies={"cna", "tfstk", "xlly_s", "ali_aplus_v3", "utdid"},
        ttl="dynamic",
        depends_on=None,
    ),
}

# Cookie 名称到层的反向映射
_COOKIE_TO_LAYER: dict[str, CookieLayer] = {}
for layer_def in LAYER_DEFINITIONS.values():
    for name in layer_def.cookies:
        _COOKIE_TO_LAYER[name] = layer_def.name


class SessionExpiredError(Exception):
    """会话已失效异常"""
    pass


@dataclass
class LayerState:
    """层状态

    manual_invalidate 字段语义：
    - True: 用户通过 /cookies/invalidate 端点主动失效，自动同步应跳过此层
    - False: 系统失效（RGV587/续期失败等）或从未失效，自动同步可恢复
    为什么需要此字段：避免系统失效（cookie 实际有效但被 worker.py 标记失效）
    被永久锁定，同时保留用户主动失效的语义
    """
    valid: bool = False
    updated_at: float = 0.0
    cookie_count: int = 0
    manual_invalidate: bool = False


class CookieRotator:
    """Cookie 分层管理与原子更新

    使用方式：
        rotator = CookieRotator()
        rotator.set_writer(my_cookie_writer)  # 设置实际写入函数

        # 登录成功后，原子更新 identity 层
        rotator.atomic_update({
            "unb": "123456",
            "cookie2": "abc",
            "sgcookie": "def",
        })

        # token 续期后，原子更新 session 层
        rotator.atomic_update({
            "_m_h5_tk": "token_1700000000000",
            "_m_h5_tk_enc": "encrypted_value",
        })
    """

    # 闲鱼相关域名（Cookie 需写入这些域名）
    DOMAINS = [
        ".goofish.com", "goofish.com",
        ".taobao.com", "taobao.com",
        ".alipay.com", "alipay.com",
        "login.taobao.com", ".login.taobao.com",
    ]

    def __init__(self):
        self._lock = threading.Lock()
        self._writer: Any = None  # Callable[[list[dict]], int]
        self._layer_states: dict[CookieLayer, LayerState] = {
            layer: LayerState() for layer in CookieLayer
        }

    # ============== 配置 ==============

    def set_writer(self, writer: Any) -> None:
        """设置 Cookie 写入函数

        writer 签名：writer(cookies: list[dict]) -> int
        cookies 是 Playwright cookie 对象列表，返回写入数量
        """
        self._writer = writer

    # ============== 核心操作 ==============

    def atomic_update(self, cookies: dict[str, str]) -> int:
        """原子更新 Cookie

        同一层的 Cookie 必须同时写入，不允许中间状态。
        更新 session 层时验证 identity 层是否有效。

        Args:
            cookies: Cookie 名称到值的映射

        Returns:
            写入的 Cookie 数量

        Raises:
            SessionExpiredError: 依赖层已失效
            ValueError: Cookie 跨层混合
        """
        if not cookies:
            return 0

        # 1. 分类 Cookie 到各层
        layer_groups = self._classify_cookies(cookies)

        # 2. 验证不跨层混合（一次更新应只涉及一个层）
        if len(layer_groups) > 1:
            raise ValueError(
                f"原子更新不允许跨层混合，涉及层: "
                f"{[l.value for l in layer_groups.keys()]}"
            )

        layer = next(iter(layer_groups.keys()))
        layer_cookies = layer_groups[layer]

        with self._lock:
            # 3. 验证依赖层
            dep = LAYER_DEFINITIONS[layer].depends_on
            if dep and not self._layer_states[dep].valid:
                raise SessionExpiredError(
                    f"层 {layer.value} 依赖的 {dep.value} 层已失效"
                )

            # 4. 批量写入所有域名
            written = self._batch_write(layer_cookies)

            # 5. 更新层状态（写入成功或无 writer 时标记有效）
            # 为什么无 writer 也标记有效：测试/只读场景下，层状态仍需要更新
            self._layer_states[layer] = LayerState(
                valid=(written > 0 or self._writer is None),
                updated_at=time.time(),
                cookie_count=len(layer_cookies),
            )

            logger.info(
                "Cookie 层 {} 原子更新: {} 个 Cookie, 写入 {} 个域名",
                layer.value, len(layer_cookies), len(self.DOMAINS),
            )
            return written

    def invalidate_layer(self, layer: CookieLayer, manual: bool = False) -> None:
        """使某层失效

        identity 层失效时，依赖它的 session 层自动失效。

        Args:
            manual: 是否为用户主动失效。
                - True: /cookies/invalidate 端点调用，自动同步应跳过此层
                - False: 系统失效（RGV587/续期失败），自动同步可恢复
                为什么需要此参数：系统失效后即使 cookie 实际仍有效，
                也应能被 /cookies/layers 自动同步恢复，避免状态永久锁定
        """
        with self._lock:
            self._layer_states[layer].valid = False
            self._layer_states[layer].manual_invalidate = manual
            # 为什么用 {} 而非 %s：loguru 占位符是 {}，%s 会被原样输出导致日志难以排查
            logger.warning("Cookie 层 {} 已标记失效 (manual={})", layer.value, manual)

            # 级联失效：identity 失效 → session 失效
            # 级联失效继承 manual 语义：用户主动失效 identity 时，session 也应被视为主动失效
            if layer == CookieLayer.IDENTITY:
                self._layer_states[CookieLayer.SESSION].valid = False
                self._layer_states[CookieLayer.SESSION].manual_invalidate = manual
                logger.warning("Cookie 层 {} 级联失效 (manual={})", CookieLayer.SESSION.value, manual)

    def invalidate_all(self) -> None:
        """使所有层失效（如检测到登出）"""
        with self._lock:
            for layer in CookieLayer:
                self._layer_states[layer].valid = False
            logger.warning("所有 Cookie 层已标记失效")

    def sync_state_from_cookies(self, cookies: dict[str, str]) -> None:
        """根据实际 Cookie 内容同步层状态（不触发 writer）

        为什么需要此方法：browser_login / auth_helper / browser_import / cookie_inject
        等登录路径只调用 CookieStore.export_cookies 写入 JSON，未调用 on_login_success，
        导致 CookieRotator 层状态保持默认 False，引发健康检查误判 Cookie 无效。
        此方法根据 Cookie 实际内容更新层状态，修复状态不一致。

        Args:
            cookies: Cookie 名称到值的映射（通常从 JSON 文件读取）
        """
        with self._lock:
            for layer, layer_def in LAYER_DEFINITIONS.items():
                layer_cookie_names = layer_def.cookies & set(cookies.keys())
                if layer_cookie_names:
                    self._layer_states[layer] = LayerState(
                        valid=True,
                        updated_at=time.time(),
                        cookie_count=len(layer_cookie_names),
                    )
                    logger.info(
                        "Cookie 层 {} 状态已同步: {} 个 Cookie",
                        layer.value, len(layer_cookie_names),
                    )

    # ============== 状态查询 ==============

    def is_layer_valid(self, layer: CookieLayer) -> bool:
        """检查某层是否有效"""
        with self._lock:
            return self._layer_states[layer].valid

    def get_layer_state(self, layer: CookieLayer) -> LayerState:
        """获取某层状态"""
        with self._lock:
            return self._layer_states[layer]

    def get_all_states(self) -> dict[CookieLayer, LayerState]:
        """获取所有层状态"""
        with self._lock:
            return dict(self._layer_states)

    def classify_cookie(self, name: str) -> CookieLayer | None:
        """分类单个 Cookie 到对应层"""
        return _COOKIE_TO_LAYER.get(name)

    # ============== 内部方法 ==============

    def _classify_cookies(
        self, cookies: dict[str, str]
    ) -> dict[CookieLayer, dict[str, str]]:
        """将 Cookie 按层分类

        未知 Cookie 名称归入 tracking 层（保守策略）
        """
        groups: dict[CookieLayer, dict[str, str]] = {}
        for name, value in cookies.items():
            layer = _COOKIE_TO_LAYER.get(name, CookieLayer.TRACKING)
            if layer not in groups:
                groups[layer] = {}
            groups[layer][name] = value
        return groups

    def _batch_write(self, cookies: dict[str, str]) -> int:
        """批量写入 Cookie 到所有域名

        构造 Playwright cookie 对象列表，调用 writer 写入。
        """
        if not self._writer:
            logger.warning("未设置 writer，Cookie 未实际写入")
            return 0

        # 构造 cookie 对象列表（每个 Cookie 写入所有域名）
        cookie_objects: list[dict] = []
        for domain in self.DOMAINS:
            for name, value in cookies.items():
                cookie_objects.append({
                    "name": name,
                    "value": value,
                    "domain": domain,
                    "path": "/",
                    # 不硬编码 httpOnly/secure：identity 层 Cookie（如 unb）
                    # 是 JS 可读的，强制 httpOnly 会触发闲鱼检测异常
                    "sameSite": "Lax",
                })

        try:
            return self._writer(cookie_objects)
        except Exception as e:
            logger.error("Cookie 批量写入失败: {}", e)
            return 0


# ============== 辅助函数 ==============


def get_cookie_layer(name: str) -> CookieLayer | None:
    """获取 Cookie 所属层"""
    return _COOKIE_TO_LAYER.get(name)


def is_identity_cookie(name: str) -> bool:
    """是否为身份层 Cookie"""
    return name in LAYER_DEFINITIONS[CookieLayer.IDENTITY].cookies


def is_session_cookie(name: str) -> bool:
    """是否为会话层 Cookie"""
    return name in LAYER_DEFINITIONS[CookieLayer.SESSION].cookies


def get_required_cookies_for_layer(layer: CookieLayer) -> set[str]:
    """获取某层所有必需的 Cookie 名称"""
    return LAYER_DEFINITIONS[layer].cookies.copy()
