# xianyu-hunter.spec
# PyInstaller 目录模式打包配置
#
# 构建：pyinstaller xianyu-hunter.spec --noconfirm
# 产物：dist/xianyu-hunter/xianyu-hunter.exe + dist/xianyu-hunter/_internal/
#
# 设计要点：
# - 目录模式（非 onefile）：启动快、对 Playwright/chromadb 兼容性好
# - chromadb/onnxruntime/duckdb 是 C 扩展依赖，必须 collect_submodules 显式收集
# - sentence_transformers 含模型权重等数据文件，需 collect_data_files
# - SPA 静态资源外置：不打入 _internal，由安装包单独分发到 spa/ 目录
# - UPX 压缩 DLL 会导致加载失败，必须 upx_exclude

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# ============== 收集 C 扩展与动态导入 ==============
hiddenimports = []

# chromadb 链：chromadb -> onnxruntime + duckdb
# chromadb 在 vector_store.py 中是 try/except 可选导入，收集失败不阻断打包
for mod in ('chromadb', 'onnxruntime', 'duckdb', 'sentence_transformers'):
    try:
        hiddenimports += collect_submodules(mod)
    except Exception:
        # 可选依赖未安装时静默跳过：主功能不依赖 chromadb
        pass

# uvicorn 动态导入：PyInstaller 静态分析无法识别
# 缺失会导致启动时报错 ModuleNotFoundError: No module named 'uvicorn.logging'
hiddenimports += [
    'uvicorn.logging',
    'uvicorn.loops.auto',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan.on',
    'uvicorn.protocols.utils',
]

# ============== 数据文件 ==============
datas = []

# sentence_transformers：模型权重、tokenizer 配置等
for mod in ('sentence_transformers', 'chromadb'):
    try:
        datas += collect_data_files(mod)
    except Exception:
        pass

# SPA 静态资源：外置目录模式
# 不打入 _internal，由构建脚本复制到 dist/xianyu-hunter/spa/
# 原因：_internal 打入会膨胀体积且每次版本变更需重新打包
# datas += collect_data_files('xianyu_hunter.web.static')

# ============== Analysis ==============
a = Analysis(
    ['scripts/launcher.py'],
    pathex=['src'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],  # 不排除任何模块：chromadb 等可选依赖需保留
    noarchive=False,
    cipher=None,  # 不加密字节码（加密会增加启动耗时且无明显保护效果）
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # 目录模式（非 onefile）：依赖由 COLLECT 收集到 _internal
    name='xianyu-hunter',
    console=True,  # 保留控制台便于查看日志，P2 阶段改为 False + GUI 加载窗口
    # icon 必须为 .ico 格式：SVG 需先用 Pillow/在线工具转换
    # 构建前请确保 assets/xianyu-hunter.ico 存在
    # icon='assets/xianyu-hunter.ico',
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,  # UPX 压缩减小体积
    # 避免压缩 DLL/SO 导致加载失败（Windows 上 UPX 压缩的 DLL 会被某些杀软误判）
    upx_exclude=[
        '*.dll',
        '*.so',
        'python3*.dll',
        'VCRUNTIME*.dll',
        'ucrtbase.dll',
        'libcrypto-*.dll',
        'libssl-*.dll',
    ],
    name='xianyu-hunter',
)
