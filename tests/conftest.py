"""pytest 配置：让 tests/ 目录能 import src/xianyu_hunter，并隔离生产数据

为什么需要 Cookie JSON 隔离：tests/test_cookie_layers_sync_repro.py 和
tests/test_api_anticrawl.py 通过 client.post('/api/anticrawl/cookies/update')
调用真实端点，会写入 d:/code/otherProjects/17_xianyu/data/cookies_*.json。
teardown_method 在 KeyboardInterrupt/IDE 停止/setup 自身失败时不执行，
留下污染数据导致生产环境 Cookie 被测试 fixture 覆盖。

防护策略（三重保险）：
1. patch sys.modules 中所有持有 _COOKIE_JSON 常量的测试模块（影响测试代码直接写文件）
2. fixture teardown 无条件恢复备份：即使测试绕过 patch，最终也会恢复生产 JSON
3. MU2 改造后 CookieStore 按 user_id 隔离，备份范围扩大到 data/cookies_*.json 全部文件

为什么 fixture 比 setup_method/teardown_method 更可靠：yield fixture 的
teardown 部分在 KeyboardInterrupt/Exception 时也会执行（pytest 标准行为），
而 setup_method/teardown_method 在这些场景下不会执行。

为什么遍历 sys.modules 而非硬编码模块名列表：pytest 的 rootdir import 机制
会把 tests/ 下的测试模块 import 为 "test_xxx"（无包前缀），而 conftest.py
import 时可能用 "tests.test_xxx"（带包前缀）。两个名字指向不同的模块对象，
硬编码列表难以覆盖所有情况。遍历 sys.modules 找所有有 _COOKIE_JSON 属性的
模块是最稳健的方式。
"""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# 把项目根加入 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture(autouse=True)
def isolate_cookie_json(tmp_path):
    """自动隔离 CookieStore JSON 路径，避免测试污染生产 data/cookies_*.json

    防护范围：patch _cookie_json_path 函数 + sys.modules 中所有持有 _COOKIE_JSON
    常量的模块 + fixture teardown 无条件恢复备份（最终防线）

    MU2 改造：CookieStore 不再有模块级 _COOKIE_JSON_FILE 常量，
    改为按 user_id 生成路径（cookies_{uid}.json）。
    备份逻辑改为备份 data 目录下所有 cookies_*.json 文件。
    """
    from xianyu_hunter.web.services import cookie_store as cs_module

    # MU2 改造：patch _cookie_json_path 函数，让所有 user_id 的文件落到 tmp_path
    # 为什么 patch 函数而非 Path 构造：_cookie_json_path 是模块级函数，
    # 模块加载时 _COOKIE_JSON_DIR 已固定为 Path("data")，patch Path 无法影响它
    def fake_cookie_json_path(user_id: str = "default") -> Path:
        return tmp_path / f"cookies_{user_id}.json"

    # 旧测试模块的 _COOKIE_JSON 常量统一指向 default 用户的文件
    fake_path = tmp_path / "cookies_default.json"

    # MU2 改造：备份 data 目录下所有 cookies_*.json（多用户隔离）
    # 为什么改为备份多个文件：MU2 按 user_id 隔离，每个用户一个 cookies_{uid}.json
    data_dir = cs_module._COOKIE_JSON_DIR
    backups: dict = {}
    if data_dir.exists():
        for f in data_dir.glob("cookies_*.json"):
            try:
                backups[f] = f.read_bytes()
            except OSError:
                pass

    # 清空 CookieStore 单例缓存
    # MU2 改造：_cache 是 dict[str, tuple]，直接 clear() 而非赋 None
    store = cs_module.get_cookie_store()
    store._cache = {}

    # patch 进入：_cookie_json_path 函数 + sys.modules 中所有持有 _COOKIE_JSON 的模块
    patches = [patch.object(cs_module, "_cookie_json_path", fake_cookie_json_path)]

    # 遍历 sys.modules，找所有有 _COOKIE_JSON 属性的模块
    # 为什么遍历而非硬编码：pytest 可能以 test_xxx 或 tests.test_xxx 两种名字
    # import 同一测试文件，生成两个不同的模块对象。硬编码列表难以覆盖全部。
    for mod_name, mod in list(sys.modules.items()):
        if mod is None:
            continue
        # 仅处理测试模块（避免误伤生产代码）
        if not mod_name.startswith("test_") and not mod_name.startswith("tests."):
            continue
        if hasattr(mod, "_COOKIE_JSON"):
            patches.append(patch.object(mod, "_COOKIE_JSON", fake_path))

    for p in patches:
        p.start()

    try:
        yield
    finally:
        # 清除 patch
        for p in patches:
            try:
                p.stop()
            except RuntimeError:
                pass

        # 最终防线：无条件恢复生产 cookies_*.json
        for path, data in backups.items():
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            except OSError:
                pass

        # 清空单例缓存，避免下一个测试读到旧的缓存
        store._cache = {}
