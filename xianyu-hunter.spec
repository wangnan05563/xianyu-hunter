# -*- mode: python ; coding: utf-8 -*-
#
# XianyuHunter PyInstaller spec（onedir 模式）
#
# 入口：scripts/launcher.py（启动 uvicorn + 自动开浏览器 + 单实例锁的打包入口）
# pathex：scripts（入口与子进程脚本所在目录）+ src（xianyu_hunter 包根）
#
# 关键 hiddenimports：
#   (a) Repository 动态 Mixin（repository_base.py 用 importlib.import_module 按字符串加载
#       10 个 repo_* 模块）。这些是字符串导入，PyInstaller 静态分析无法发现，必须显式声明，
#       否则运行到 Repository 组合时会 ModuleNotFoundError。
#   (b) uvicorn.* 的 loops/protocols/lifespan 子模块（uvicorn 运行时按配置动态导入，
#       PyInstaller 不一定能静态捕获）。
#   (c) chromadb / onnxruntime / sentence_transformers —— 含大量 C 扩展与动态子模块，
#       标准做法是用 collect_submodules 全量收集（见 docs/archive/评估项目打包EXE安装包可行性.md）。
#
# 关于 duckdb：chromadb 1.x 已不再将 duckdb 作为依赖引入（旧版 design doc 中的
#   collect_submodules('duckdb') 在当前依赖树下会因 ModuleNotFoundError 直接让 spec 崩溃），
#   因此本 spec 仅在 duckdb 实际可导入时才收集，缺失则安全跳过。
#
# 防御性收集：所有 collect_submodules 都包了 try/except，任一可选 C 扩展包缺失都不会阻断构建。
#
# 其余依赖（fastapi / torch / playwright / loguru 等）均为静态 import，由 PyInstaller
#   模块发现 + 各包 hook 自动收集（含约 5600 个包内 DATA 文件），无需在此显式列出。
#
# 运行时只读资源（static / scripts / models / playwright_browsers）由 build-exe.ps1
#   的"复制外置资源"步骤放入 dist/xianyu-hunter/，本 spec 不再重复打包，避免路径错乱。
#
# 配置 config/*.yaml 在冻结模式从 %APPDATA%/XianyuHunter/config 读取（运行时目录，
#   非打包内），本 spec 不打包配置。

import os

from PyInstaller.utils.hooks import collect_submodules

repo_root = os.path.dirname(os.path.abspath(SPEC))  # spec 所在目录 = 仓库根


def safe_collect_submodules(pkg_name):
    """收集子模块；若顶层包不可导入（缺失/可选依赖）则安全返回空列表，不阻断构建。"""
    try:
        return collect_submodules(pkg_name)
    except Exception:
        return []


# (c) 含 C 扩展的依赖全量子模块收集（缺失则跳过）
hiddenimports = []
hiddenimports += safe_collect_submodules('chromadb')
hiddenimports += safe_collect_submodules('onnxruntime')
hiddenimports += safe_collect_submodules('sentence_transformers')
hiddenimports += safe_collect_submodules('duckdb')  # chromadb 1.x 通常不再需要，缺失则跳过

# (b) uvicorn 动态子模块
hiddenimports += [
    'uvicorn.logging',
    'uvicorn.loops.auto',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan.on',
]

# (a) Repository 动态 Mixin（importlib.import_module 字符串加载，必须显式声明）
hiddenimports += [
    'xianyu_hunter.infra.repo_tasks',
    'xianyu_hunter.infra.repo_items',
    'xianyu_hunter.infra.repo_events',
    'xianyu_hunter.infra.repo_error_logs',
    'xianyu_hunter.infra.repo_deps',
    'xianyu_hunter.infra.repo_links',
    'xianyu_hunter.infra.repo_evaluations',
    'xianyu_hunter.infra.repo_orders',
    'xianyu_hunter.infra.repo_notifications',
    'xianyu_hunter.infra.repo_sellers',
]

a = Analysis(
    [os.path.join(repo_root, 'scripts', 'launcher.py')],
    pathex=[os.path.join(repo_root, 'scripts'), os.path.join(repo_root, 'src')],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='xianyu-hunter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(repo_root, 'assets', 'xianyu-hunter.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='xianyu-hunter',
)
