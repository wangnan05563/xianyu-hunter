"""pytest 配置：让 tests/ 目录能 import src/xianyu_hunter，并隔离生产数据

为什么需要 Cookie JSON 隔离：tests/test_cookie_layers_sync_repro.py 和
tests/test_api_anticrawl.py 通过 client.post('/api/anticrawl/cookies/update')
调用真实端点，会写入 d:/code/otherProjects/17_xianyu/data/cookies.json。
teardown_method 在 KeyboardInterrupt/IDE 停止/setup 自身失败时不执行，
留下污染数据导致生产环境 Cookie 被测试 fixture 覆盖。

防护策略（三重保险）：
1. patch cookie_store 模块的 _COOKIE_JSON_FILE 到 tmp_path（影响 CookieStore 类）
2. patch sys.modules 中所有持有 _COOKIE_JSON 常量的测试模块（影响测试代码直接写文件）
3. fixture teardown 无条件恢复备份：即使测试绕过 patch，最终也会恢复生产 JSON

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
    """自动隔离 CookieStore JSON 路径，避免测试污染生产 data/cookies.json

    防护范围：cookie_store 模块级常量 + sys.modules 中所有持有 _COOKIE_JSON
    常量的模块 + fixture teardown 无条件恢复备份（最终防线）
    """
    from xianyu_hunter.web.services import cookie_store as cs_module

    fake_path = tmp_path / "cookies.json"

    # 备份生产 JSON 到内存（最终防线，无论 patch 是否生效都会恢复）
    real_path = cs_module._COOKIE_JSON_FILE
    backup_data = None
    if real_path.exists():
        try:
            backup_data = real_path.read_bytes()
        except OSError:
            backup_data = None

    # 清空 CookieStore 单例缓存
    store = cs_module.get_cookie_store()
    store._cache = None
    store._cache_ts = 0.0

    # patch 进入：cookie_store 模块 + sys.modules 中所有持有 _COOKIE_JSON 的模块
    patches = [patch.object(cs_module, "_COOKIE_JSON_FILE", fake_path)]

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

        # 最终防线：无条件恢复生产 JSON（即使测试绕过 patch 直接写文件）
        if backup_data is not None:
            try:
                real_path.parent.mkdir(parents=True, exist_ok=True)
                real_path.write_bytes(backup_data)
            except OSError:
                pass
        elif real_path.exists():
            # 测试前生产 JSON 不存在，删除测试可能创建的文件
            try:
                real_path.unlink()
            except OSError:
                pass

        # 清空单例缓存，避免下一个测试读到旧的缓存
        store._cache = None
        store._cache_ts = 0.0
