# 评估项目打包EXE安装包可行性

> **Workspace:** d:\code\otherProjects\17_xianyu
>
> **文档状态**：可行性评估 + 概要设计（已修订）
> **修订记录**：
> - v1.1 补充数据路径改造清单、Edge 浏览器依赖、依赖锁定、体积估算修正、数据迁移方案、概要设计章节
> - v1.2 P0 第 2 步 PyInstaller 实际打包验证完成：总体积 855.81 MB，补充实测体积对照表与 P1 体积优化清单

---

**User**

评估项目是否可实现打包成exe的安装包，用户可双击安装整套程序

**Assistant**

# 闲鱼项目打包为 EXE 安装包可行性评估

## 一、总体结论

**可行，但不是「双击 exe 直接运行」，而是「双击 exe 安装程序 → 安装到本机 → 桌面快捷方式启动」** 的标准 Windows 软件分发模式。技术风险中等，主要难点在 **Playwright 浏览器与系统 Edge 依赖、chromadb C 扩展、数据路径迁移** 三方面，预估完整工作量 **8–15 个工作日**（含数据迁移与端到端验证）。

---

## 二、项目技术栈分析

| 层级 | 技术 | 打包友好度 | 备注 |
|---|---|---|---|
| 后端框架 | FastAPI + uvicorn | ✅ 友好 | 纯 Python |
| 前端 SPA | React + Vite（已构建产物） | ✅ 友好 | 静态文件，外置即可 |
| 数据库 | SQLite | ✅ 友好 | 文件型，无需独立服务 |
| 浏览器自动化 | Playwright + Chromium | ⚠️ 难点 | 浏览器二进制 ~150-200 MB |
| **系统 Edge 依赖** | CDP 模式连接系统 Edge | ⚠️ 难点 | [browser.py:30](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/infra/browser.py#L30) 硬编码 Edge 路径，未安装时需降级 |
| 向量库 | chromadb 1.x | ⚠️ 难点 | **可选依赖**（[vector_store.py:23](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/modules/chatbot/vector_store.py#L23) try/except），含 onnxruntime/duckdb C 扩展 |
| Embedding 模型 | sentence-transformers + BAAI/bge-small-zh-v1.5 | ⚠️ 难点 | 模型权重 ~100 MB，首次运行自动下载 |
| 加密 | cryptography | ✅ 友好 | 已有预编译 wheel |
| 密钥存储 | keyring（Windows DPAPI） | ✅ 友好 | 依赖 Windows 凭据管理器 |
| Windows 专用 | pythonnet、pywin32-ctypes、win32_setctime | ✅ 友好 | 仅 Windows 打包，无跨平台问题 |

---

## 三、关键挑战与应对

### 1. Playwright 浏览器打包
- **问题**：PyInstaller 默认不收集 Chromium 二进制，需手动 `--add-data`
- **方案**：将浏览器安装到固定子目录，安装包内置；启动时设置 `PLAYWRIGHT_BROWSERS_PATH` 环境变量指向该目录

### 2. 系统 Edge 浏览器依赖（CDP 模式）
- **问题**：[browser.py:30](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/infra/browser.py#L30) 在 CDP 模式下连接系统 Edge（`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`），用户机器未安装 Edge 时登录功能不可用
- **方案**：
  1. 安装程序检测 Edge 是否存在，缺失时引导安装（Windows 10/11 默认预装，覆盖率 >99%）
  2. 在 [browser.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/infra/browser.py) 中增加 Edge 路径检测与降级逻辑：找不到系统 Edge 时回退到 Playwright Chromium launch 模式
  3. 启动器首次运行时打印 Edge 检测结果，便于用户排查

### 3. chromadb C 扩展（可选依赖）
- **问题**：onnxruntime、duckdb 等动态链接库需要 PyInstaller 的 `collect_all('chromadb')` 钩子显式收集，否则运行时 `ImportError`
- **方案**：
  1. 在 `.spec` 文件中显式添加 `collect_submodules('chromadb')`、`collect_submodules('onnxruntime')`、`collect_submodules('duckdb')`
  2. Embedding 模型 `BAAI/bge-small-zh-v1.5`（约 100 MB）预置到安装目录 `models/` 下，启动时通过 `SENTENCE_TRANSFORMERS_HOME` 指向该目录，避免首次运行联网下载
  3. chromadb 在 [vector_store.py:23](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/modules/chatbot/vector_store.py#L23) 是 try/except 可选导入，打包时即使收集失败也不影响主功能

### 4. 运行时数据持久化（路径改造）
- **问题**：单 exe 内部只读，SQLite/cookies/logs/config 无法写入 exe 内部
- **现状**：项目中存在 **至少 8 处硬编码相对路径**（详见下方清单），PyInstaller 打包后 `Path("data")` 会指向临时解压目录 `_MEIPASS`，导致数据丢失
- **方案**：新增 `paths.py` 模块集中管理路径（详见「概要设计 §1」），所有路径基于 `%APPDATA%\XianyuHunter\` 派生

**硬编码路径清单（必须改造）**：

| 文件 | 行号 | 硬编码 | 用途 |
|---|---|---|---|
| [config.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/config.py#L67) | 67 | `project_root = Path(__file__).resolve().parent.parent.parent.parent` | 项目根，PyInstaller 下指向 `_MEIPASS` |
| [config.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/config.py#L159) | 159, 191 | `Path(".env")` | 环境变量读写 |
| [yaml_config.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/infra/yaml_config.py#L578) | 578 | `base = Path("config")` | YAML 配置加载 |
| [cookie_store.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/web/services/cookie_store.py#L30) | 30, 47 | `Path("data")` | Cookie JSON 存储 |
| [user_manager.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/web/services/user_manager.py#L476) | 476-477 | `Path("data") / "cookies.json"` | 用户 Cookie 迁移 |
| [notification_engine.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/web/services/notification_engine.py#L92) | 92 | `Path("data") / "userinfo.json"` | 通知用户信息 |
| [auth_manager.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/web/services/auth_manager.py#L29) | 29 | `_REPO / "data" / "auth_cache"` | 认证缓存 |
| [tunnel_service.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/web/services/tunnel_service.py#L54) | 54 | `Path(__file__).resolve().parents[3] / "data"` | 隧道数据 |
| [api_maintenance.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/web/routes/api_maintenance.py#L31) | 31, 36 | `Path("data")`, `Path("data/logs")` | 维护接口数据/日志 |
| [yaml_config.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/infra/yaml_config.py#L285) | 285 | `persist_path: str = "data/chromadb"` | chromadb 持久化 |
| [kb_manager.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/modules/chatbot/kb_manager.py#L911) | 911 | `f"data/chromadb/snapshots/{version_id}"` | 快照路径 |

### 5. 前端 SPA 资源
- **问题**：Docker 构建时已将 SPA 输出到 `src/xianyu_hunter/web/static/spa/`，但单 exe 不应内置大量静态资源到 `_internal`
- **方案**：作为外置资源目录随安装包分发（与 exe 同级 `spa/` 目录）

### 6. 体积估算（修正）

> **v1.2 实测数据**：
> - 首次打包（无 excludes）：855.81 MB（EXE 81.26 MB + `_internal/` 774.55 MB）
> - 优化打包（excludes pytest/sklearn/IPython/jupyter 等）：839.10 MB（EXE 77.20 MB）
> - 减少 16.71 MB（约 2%），主要体积仍来自 torch (359.74 MB)
> - 超出原估算 70%：torch/scipy/sklearn 链体积被低估
> - 下表保留原估算供对照，优化策略见后文「P1 体积优化清单」

| 组件 | 原估算 | 实测 |
|---|---|---|
| Python 解释器 + 依赖 | ~120 MB | ~210 MB（EXE 81 + 公共依赖 129） |
| Playwright Chromium | ~150–200 MB | 102.28 MB（playwright Python 包，未含 Chromium 二进制） |
| SPA 静态资源 | ~5–10 MB | 待复制（外置） |
| chromadb + onnxruntime + duckdb | ~100–150 MB | 128.14 MB（chromadb_rust_bindings 60.46 + onnxruntime 33.68 + 其他） |
| sentence-transformers 模型权重 | ~100 MB | 待复制（外置） |
| torch + scipy + sklearn + transformers | 未单独估算 | 478.68 MB（torch 359.74 + scipy 70.32 + transformers 35.61 + sklearn 12.03） |
| **安装包总体积** | **~500–600 MB** | **~856 MB**（未含 SPA + Chromium + 模型，最终预计 ~1.2 GB） |

**P1 体积优化清单**（按收益排序）：
1. `excludes=['pytest', '_pytest', 'pluggy', 'iniconfig']` — pytest 是测试框架，不应打入生产包，预计节省 ~15 MB
2. 尝试 `excludes=['sklearn', 'sklearn.externals']` — sklearn 未在业务代码直接使用，transformers 仅在 import 时尝试加载，预计节省 ~12 MB；需先验证 transformers 不强制依赖 sklearn
3. scipy 子模块精简 — 业务仅用 `scipy.sparse`（chromadb 间接依赖），可在 excludes 中列出未使用的 `scipy.linalg`、`scipy.spatial`、`scipy.stats`、`scipy.io.matlab`，预计节省 ~30 MB
4. torch CPU 专用版替代 — `pip install torch --index-url https://download.pytorch.org/whl/cpu` 可去除 CUDA 运行时（约 50 MB），但需重新创建 venv
5. UPX 已启用但 `*.dll` 被排除（避免杀软误报），可考虑用 7z 压缩安装包分发，最终用户体积预计可压至 ~400 MB

### 7. 依赖锁定不完整
- **问题**：[requirements.txt](file:///d:/code/otherProjects/17_xianyu/requirements.txt) 由 `pip freeze` 生成，但未包含 chromadb、onnxruntime、duckdb、sentence-transformers、torch 等（虽然 [pyproject.toml:38](file:///d:/code/otherProjects/17_xianyu/pyproject.toml#L38) 声明了 `chromadb>=1.0.0`），导致 PyInstaller 收集时缺少 hidden imports 依据
- **方案**：打包前在干净 venv 中 `pip install -e .` 后 `pip freeze > requirements.txt`，确保传递依赖完整锁定

---

## 四、推荐打包方案

**不采用「单 exe 文件」**（PyInstaller `--onefile` 模式启动慢、体积大、Playwright 不友好），而是采用**「目录结构 + Inno Setup 安装程序」**模式：

```
C:\Program Files\XianyuHunter\
  ├── xianyu-hunter.exe           # PyInstaller 目录模式产物（启动器）
  ├── _internal\                   # PyInstaller 收集的所有依赖
  │   ├── chromadb\
  │   ├── onnxruntime\
  │   ├── duckdb\
  │   └── ...
  ├── spa\                          # 前端构建产物
  ├── playwright_browsers\          # Chromium 二进制
  └── models\                       # sentence-transformers 预置模型

%APPDATA%\XianyuHunter\              # 用户可写数据
  ├── data\                         # SQLite、cookies、browser_data、chromadb
  ├── config\                       # YAML 配置
  ├── logs\                         # 日志
  └── .env                          # 环境变量

桌面快捷方式 → 启动 web 服务 + 自动打开默认浏览器到 http://127.0.0.1:8001/app/
```

### 工具选型
| 工具 | 用途 | 理由 |
|---|---|---|
| PyInstaller（目录模式） | Python → exe 启动器 | 成熟稳定，对 FastAPI/Playwright 兼容性最好 |
| Inno Setup | 安装程序制作 | 中文支持好、免费、可注册表/快捷方式/卸载完整 |
| pystray（可选） | 系统托盘管理 | **注意**：项目当前未使用 pywebview/WebView2 作为桌面 UI（[browser_login.py:10](file:///d:/code/otherProjects/17_xianyu/scripts/browser_login.py#L10) 注释明确「比 WebView2 更可靠」），pystray 与现有 bat 脚本启动方式兼容，无冲突 |

---

## 五、需要做的代码改造

1. **新增 `paths.py` 模块**：集中管理路径，所有路径基于 `%APPDATA%\XianyuHunter\` 派生，提供 `get_data_dir() / get_config_dir() / get_log_dir() / get_models_dir() / get_app_dir()` 单一入口
2. **替换 8 处硬编码路径**：见 §三-4 清单，全部改为调用 `paths.py`
3. **[browser.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/infra/browser.py) Edge 检测**：增加系统 Edge 路径检测与降级到 Playwright Chromium 的回退逻辑
4. **PyInstaller spec 文件**：配置 `hiddenimports`、`datas`、`collect_submodules('chromadb')`、`collect_submodules('onnxruntime')`、`collect_submodules('duckdb')`
5. **启动器 `launcher.py`**：启动 uvicorn 后调用 `webbrowser.open()` 打开默认浏览器
6. **单实例锁**：用 `win32event.CreateMutex` 防止多开（与现有 [启动服务.bat:14-19](file:///d:/code/otherProjects/17_xianyu/scripts/启动服务.bat#L14) PID 文件机制互斥，二选一）
7. **Playwright 路径**：启动时设置 `PLAYWRIGHT_BROWSERS_PATH` 指向安装目录
8. **sentence-transformers 模型预置**：设置 `SENTENCE_TRANSFORMERS_HOME` 指向 `models/`，避免首次运行联网下载
9. **数据迁移脚本**：Inno Setup 安装时检测旧版相对路径数据，迁移到 `%APPDATA%\XianyuHunter\`（详见「概要设计 §6」）

---

## 六、推荐实施阶段

| 阶段 | 内容 | 价值 |
|---|---|---|
| P0 | PyInstaller 目录打包 + 启动器 exe + paths.py 路径改造（仅本机测试） | 验证 Playwright/chromadb 可正常打包运行 |
| P1 | Inno Setup 安装程序（含快捷方式、卸载、数据目录初始化、Edge 检测） | 可分发 |
| P2 | 系统托盘 + 开机自启 + 自动检查更新 + 数据迁移 | 提升用户体验 |

---

## 七、与现有 Docker 部署的关系

项目已有完整的 [Dockerfile](file:///d:/code/otherProjects/17_xianyu/Dockerfile) 与 [部署指南](file:///d:/code/otherProjects/17_xianyu/docs/standards/部署指南.md)，Docker 部署仍应作为**服务器场景的首选**。EXE 安装包面向**桌面小白用户单机使用**场景，两者互补：

- **服务器/VPS 部署** → Docker（已成熟）
- **个人电脑单机使用** → EXE 安装包（待开发）

### 与现有 bat 脚本的兼容
现有 [scripts/启动服务.bat](file:///d:/code/otherProjects/17_xianyu/scripts/启动服务.bat) 已实现端口清理、PID 管理、健康检查、自动开浏览器。EXE 启动器应**复用这些逻辑**（端口清理、健康轮询、自动开浏览器），并替换原有的 `.venv\Scripts\python.exe` 调用为 `xianyu-hunter.exe` 直接启动。打包后 bat 脚本不再需要（开发者模式仍保留）。

---

## 八、风险提示

1. **杀毒软件误报**：PyInstaller 产物常被 Defender/360 误判，需数字签名证书（约 ¥500–2000/年）或引导用户加白名单
2. **闲鱼风控**：自动化操作风险与部署方式无关，仍需用户自行承担账号封禁风险
3. **维护成本**：每次版本升级需重新打包并发布，建议配套 CI/CD（GitHub Actions 可自动跑 PyInstaller + Inno Setup）
4. **Edge 版本兼容**：CDP 模式依赖系统 Edge，Edge 大版本升级可能导致 CDP 协议变更，需兼容性测试
5. **首次启动耗时**：chromadb 初始化 + 模型加载需 10-30 秒，启动器需显示加载进度，避免用户误判卡死

---

# 概要设计

## §1 路径层设计（`paths.py`）

### 设计目标
将所有运行时路径集中到单一模块，支持开发模式（项目根）与打包模式（`%APPDATA%`）双形态。

### 模块设计

```python
# src/xianyu_hunter/paths.py
"""路径集中管理

打包模式（PyInstaller）下数据写入 %APPDATA%\\XianyuHunter\\，
开发模式下保持 CWD 相对路径（向后兼容现有测试的 monkeypatch.chdir 隔离机制）。

判定逻辑：sys.frozen 存在即为打包模式

设计权衡：
- 开发模式保留 Path("data") / Path("config") 等相对路径，
  pytest 通过 monkeypatch.chdir(tmp_path) 切换 CWD 实现测试隔离
- 打包模式切换到 %APPDATA%/XianyuHunter/ 绝对路径，
  避免 PyInstaller _MEIPASS 临时解压目录的只读限制
"""
import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    """PyInstaller 打包后 sys.frozen = True"""
    return getattr(sys, "frozen", False)


def get_app_dir() -> Path:
    """程序安装目录（只读资源：spa/、models/、playwright_browsers/）

    打包模式：exe 所在目录
    开发模式：CWD（项目根）
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(".")


def get_data_dir() -> Path:
    """用户数据目录（可写：SQLite、cookies、chromadb）

    打包模式：%APPDATA%/XianyuHunter/data
    开发模式：data（相对路径，依赖 CWD）
    """
    if is_frozen():
        base = Path(os.environ.get("APPDATA", "")) / "XianyuHunter" / "data"
    else:
        base = Path("data")
    base.mkdir(parents=True, exist_ok=True)
    return base


def get_config_dir() -> Path:
    """配置目录（可写：YAML 配置）

    打包模式：%APPDATA%/XianyuHunter/config
    开发模式：config（相对路径，依赖 CWD）
    """
    if is_frozen():
        base = Path(os.environ.get("APPDATA", "")) / "XianyuHunter" / "config"
    else:
        base = Path("config")
    base.mkdir(parents=True, exist_ok=True)
    return base


def get_log_dir() -> Path:
    """日志目录（可写，位于 data 目录下）

    设计依据：logger.py 将日志写入 data/logs/，与 SQLite、cookies 同级。
    打包模式下 data 目录在 %APPDATA%/XianyuHunter/data，logs 跟随迁移。

    打包模式：%APPDATA%/XianyuHunter/data/logs
    开发模式：data/logs（相对路径，依赖 CWD）
    """
    return get_data_dir() / "logs"


def get_env_file() -> Path:
    """环境变量文件路径

    打包模式：%APPDATA%/XianyuHunter/.env
    开发模式：.env（相对路径，依赖 CWD）
    """
    if is_frozen():
        return Path(os.environ.get("APPDATA", "")) / "XianyuHunter" / ".env"
    return Path(".env")


def get_chromadb_path() -> Path:
    """chromadb 持久化目录（位于 data 目录下）"""
    return get_data_dir() / "chromadb"


def get_models_dir() -> Path:
    """sentence-transformers 模型目录（只读，随安装包分发）

    位于程序安装目录下，不在用户数据目录
    """
    return get_app_dir() / "models"
```

### 改造原则
- 所有 `Path("data")` → `get_data_dir()`
- 所有 `Path("config")` → `get_config_dir()`
- 所有 `Path("data/logs")` → `get_log_dir()`
- 所有 `Path(".env")` → `get_env_file()`
- 所有 `Path(__file__).resolve().parents[N] / "data"` → `get_data_dir()`

### 设计权衡说明
开发模式保留 CWD 相对路径而非基于 `__file__` 推算绝对路径，理由：
1. 项目现有 1394 个测试通过 `monkeypatch.chdir(tmp_path)` 切换 CWD 实现配置隔离
2. 改造测试代码超出 P0 第 1 步范围
3. 开发模式下 CWD 默认就是项目根，相对路径工作良好
4. 打包模式下 `is_frozen()` 切换到 `%APPDATA%` 已解决核心问题

---

## §2 启动器设计（`launcher.py`）

### 职责
1. 设置环境变量（`PLAYWRIGHT_BROWSERS_PATH`、`SENTENCE_TRANSFORMERS_HOME`）
2. 单实例锁（`win32event.CreateMutex`）
3. 启动 uvicorn + 自动开浏览器
4. 显示启动进度（控制台输出，P2 阶段升级为 GUI 加载窗口）

### 设计骨架

```python
# scripts/launcher.py
"""PyInstaller 打包入口

复用现有 scripts/启动服务.bat 的端口清理逻辑，
但用 Python 实现以便 PyInstaller 收集。
"""
import os
import sys
import webbrowser
from pathlib import Path

def _setup_env() -> None:
    """设置运行时环境变量"""
    from xianyu_hunter.paths import get_app_dir
    app_dir = get_app_dir()
    # Playwright 浏览器路径
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(app_dir / "playwright_browsers")
    # sentence-transformers 模型路径
    os.environ["SENTENCE_TRANSFORMERS_HOME"] = str(app_dir / "models")
    # 启用调度器
    os.environ["XH_WITH_SCHEDULER"] = "1"

def _acquire_single_instance() -> bool:
    """单实例锁：防止多开

    CreateMutex 返回句柄，GetLastError == 183 表示已存在同名 Mutex
    """
    import win32event
    import win32api
    win32event.CreateMutex(None, False, "XianyuHunter-Mutex")
    # ERROR_ALREADY_EXISTS = 183
    return win32api.GetLastError() != 183

def _cleanup_port(port: int = 8001) -> None:
    """端口清理（复用 bat 逻辑）

    netstat 输出形如：TCP    127.0.0.1:8001      0.0.0.0:0    LISTENING    1234
    需同时匹配端口号与 LISTENING 状态，避免误杀其他端口的进程
    """
    import re
    import subprocess
    result = subprocess.run(
        ["netstat", "-aon"], capture_output=True, text=True
    )
    # 正则匹配：:PORT 任意空白 LISTENING 任意空白 PID
    pattern = re.compile(rf":{port}\s+\S+\s+\S+\s+LISTENING\s+(\d+)")
    for line in result.stdout.splitlines():
        m = pattern.search(line)
        if m:
            pid = m.group(1)
            subprocess.run(["taskkill", "/F", "/T", "/PID", pid],
                         capture_output=True)

def _wait_for_port(host: str, port: int, timeout: int = 30) -> bool:
    """轮询等待端口就绪"""
    import time
    import socket
    for _ in range(timeout * 2):
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.5)
    return False

def main() -> int:
    _setup_env()
    if not _acquire_single_instance():
        print("已在运行，请勿重复启动")
        return 1
    _cleanup_port()
    # 在子线程启动 uvicorn，主线程等待端口就绪后开浏览器
    # 主线程不能直接 server.run()，否则无法执行 webbrowser.open
    import threading
    import uvicorn
    from xianyu_hunter.web.app import app
    config = uvicorn.Config(app, host="127.0.0.1", port=8001, log_level="info")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    if _wait_for_port("127.0.0.1", 8001):
        webbrowser.open("http://127.0.0.1:8001/app/")
    # 阻塞主线程：uvicorn 在子线程运行，主线程 join 等待
    thread.join()
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

---

## §3 PyInstaller spec 设计

### `xianyu-hunter.spec`

```python
# xianyu-hunter.spec
# PyInstaller 目录模式打包配置
# 构建：pyinstaller xianyu-hunter.spec
# 产物：dist/xianyu-hunter/xianyu-hunter.exe + dist/xianyu-hunter/_internal/

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# 收集 C 扩展依赖（chromadb 是可选依赖，收集失败不阻断）
hiddenimports = []
hiddenimports += collect_submodules('chromadb')
hiddenimports += collect_submodules('onnxruntime')
hiddenimports += collect_submodules('duckdb')
hiddenimports += collect_submodules('sentence_transformers')

# 显式声明 PyInstaller 无法静态分析的动态导入
hiddenimports += [
    'uvicorn.logging',
    'uvicorn.loops.auto',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan.on',
]

datas = []
# SPA 静态资源（外置目录模式：不打入 _internal，由安装包单独分发）
# datas += collect_data_files('xianyu_hunter.web.static')

a = Analysis(
    ['scripts/launcher.py'],
    pathex=['src'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],  # 不排除任何模块（chromadb 等可选）
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # 目录模式（非 onefile）
    name='xianyu-hunter',
    console=True,  # 保留控制台便于查看日志，P2 阶段改为 False + GUI
    # icon 必须为 .ico 格式：SVG 需先用 Pillow/在线工具转换为 .ico
    # icon='assets/xianyu-hunter.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,  # UPX 压缩减小体积
    upx_exclude=['*.dll', '*.so'],  # 避免压缩 DLL 导致加载失败
    name='xianyu-hunter',
)
```

### 构建脚本（PowerShell）

```powershell
# scripts/build-exe.ps1
# 在干净 venv 中构建 EXE 安装包
# 用法：powershell -File scripts/build-exe.ps1

$ErrorActionPreference = "Stop"

# 1. 创建干净构建环境
python -m venv .venv-build
& .venv-build\Scripts\pip install -e .
& .venv-build\Scripts\pip install pyinstaller

# 2. 重建依赖锁定
& .venv-build\Scripts\pip freeze > requirements-lock.txt
Write-Host "依赖已锁定到 requirements-lock.txt"

# 3. 构建 SPA（如未构建）
if (-not (Test-Path "src\xianyu_hunter\web\static\spa\index.html")) {
    Push-Location frontend
    npm ci
    npm run build
    Pop-Location
}

# 4. PyInstaller 打包
& .venv-build\Scripts\pyinstaller xianyu-hunter.spec --noconfirm

# 5. 复制外置资源到 dist
Copy-Item -Recurse "src\xianyu_hunter\web\static\spa" "dist\xianyu-hunter\spa"
# Playwright 浏览器
& .venv-build\Scripts\playwright install chromium
$pwPath = "$env:USERPROFILE\AppData\Local\ms-playwright"
Copy-Item -Recurse $pwPath "dist\xianyu-hunter\playwright_browsers"

# 6. 预置 sentence-transformers 模型
$modelDir = "dist\xianyu-hunter\models\bge-small-zh-v1.5"
New-Item -ItemType Directory -Force $modelDir
# 首次运行触发下载，再复制到 models/
& .venv-build\Scripts\python -c "from sentence_transformers import SentenceTransformer; m = SentenceTransformer('BAAI/bge-small-zh-v1.5'); m.save('$modelDir')"

Write-Host "构建完成：dist\xianyu-hunter\"
```

---

## §4 Inno Setup 脚本设计

### `installer.iss`

```pascal
; Inno Setup 脚本
; 构建：iscc installer.iss
; 产物：dist/XianyuHunter-Setup-v0.3.0.exe

#define MyAppName "闲鱼猎人"
#define MyAppVersion "0.3.0"
#define MyAppPublisher "XianyuHunter"
#define MyAppExeName "xianyu-hunter.exe"
#define MyAppURL "https://github.com/..."

[Setup]
AppId={{8F7B2D3E-1234-5678-9ABC-DEF012345678}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={pf}\XianyuHunter
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=XianyuHunter-Setup-v{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
; 卸载时保留用户数据（data/、config/、logs/、.env）
Uninstallable=yes
CreateUninstallRegKey=yes

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加选项:"; Flags: checked

[Files]
; 主程序 + 依赖
Source: "dist\xianyu-hunter\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; 启动应用
Filename: "{app}\{#MyAppExeName}"; Description: "立即启动"; Flags: nowait postinstall skipifsilent

[Code]
// 前向声明：CurStepChanged 调用 MigrateOldData，需先声明
procedure MigrateOldData(NewAppDataDir: String); forward;

function InitializeSetup(): Boolean;
var
  EdgePath: String;
begin
  // 检测系统 Edge（CDP 模式依赖）
  if RegQueryStringValue(HKLM, 'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe', '', EdgePath) then
    Result := True
  else if FileExists('C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe') or
          FileExists('C:\Program Files\Microsoft\Edge\Application\msedge.exe') then
    Result := True
  else begin
    if MsgBox('未检测到 Microsoft Edge 浏览器，登录功能将不可用（CDP 模式依赖 Edge）。' + #13#10 +
               '是否继续安装？', mbConfirmation, MB_YESNO) = IDYES then
      Result := True
    else
      Result := False;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  AppDataDir: String;
begin
  if CurStep = ssPostInstall then begin
    AppDataDir := ExpandConstant('{userappdata}\XianyuHunter');
    // 创建数据目录
    if not DirExists(AppDataDir) then
      CreateDir(AppDataDir);
    if not DirExists(AppDataDir + '\data') then
      CreateDir(AppDataDir + '\data');
    if not DirExists(AppDataDir + '\config') then
      CreateDir(AppDataDir + '\config');
    if not DirExists(AppDataDir + '\logs') then
      CreateDir(AppDataDir + '\logs');
    // 数据迁移：检测旧版相对路径数据（详见 §6）
    MigrateOldData(AppDataDir);
  end;
end;
```

---

## §5 Edge 检测与降级设计

### [browser.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/infra/browser.py) 改造

```python
# src/xianyu_hunter/infra/browser.py 增量改造

def _detect_edge_path() -> str | None:
    """检测系统 Edge 路径，未安装返回 None"""
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for p in candidates:
        if Path(p).exists():
            return p
    return None

# 在 BrowserManager 启动时
if self.use_cdp:
    edge_path = _detect_edge_path()
    if edge_path is None:
        logger.warning("未检测到系统 Edge，CDP 模式降级为 Playwright Chromium launch 模式")
        self.use_cdp = False  # 自动降级
    # ... 原有 CDP 启动逻辑
```

---

## §6 数据迁移设计

### 迁移场景
用户从开发版（项目根 `data/`、`config/`、`logs/`、`.env`）升级到 EXE 安装版（`%APPDATA%\XianyuHunter\`）。

### 迁移逻辑（Inno Setup Pascal 脚本）

```pascal
// 递归复制目录：Inno Setup 无内置 CopyTree，需自定义实现
procedure CopyDirRecursive(const SrcDir, DstDir: String);
var
  FindRec: TFindRec;
  SrcPath, DstPath: String;
begin
  if not DirExists(DstDir) then
    CreateDir(DstDir);
  if FindFirst(SrcDir + '\*', FindRec) then begin
    repeat
      if (FindRec.Name <> '.') and (FindRec.Name <> '..') then begin
        SrcPath := SrcDir + '\' + FindRec.Name;
        DstPath := DstDir + '\' + FindRec.Name;
        if FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY <> 0 then
          CopyDirRecursive(SrcPath, DstPath)
        else
          FileCopy(SrcPath, DstPath, False);
      end;
    until not FindNext(FindRec);
    FindClose(FindRec);
  end;
end;

procedure MigrateOldData(NewAppDataDir: String);
var
  OldInstallDir: String;
  SrcDir: String;
  DstDir: String;
  ConfirmResult: Boolean;
begin
  // 旧版安装目录：优先从注册表读取，回退到用户主目录下的常见位置
  OldInstallDir := ExpandConstant('{reg:HKCU\Software\XianyuHunter,InstallPath|}');
  if OldInstallDir = '' then
    OldInstallDir := ExpandConstant('{userdocs}\XianyuHunter');  // 默认猜测用户文档目录
  if not DirExists(OldInstallDir + '\data') then Exit;

  // 询问用户是否迁移（仅询问一次，对 data/ 迁移弹窗，其他静默）
  ConfirmResult := MsgBox(
    '检测到旧版数据：' + OldInstallDir + #13#10 +
    '是否迁移到新安装目录 ' + NewAppDataDir + '？' + #13#10 +
    '(注意：chromadb 向量库较大时迁移可能耗时数分钟)',
    mbConfirmation, MB_YESNO
  ) = IDYES;
  if not ConfirmResult then Exit;

  // 迁移 data/（递归复制）
  SrcDir := OldInstallDir + '\data';
  DstDir := NewAppDataDir + '\data';
  if DirExists(SrcDir) and not FileExists(DstDir + '\xianyu.db') then begin
    CopyDirRecursive(SrcDir, DstDir);
    Log('数据已迁移：' + SrcDir + ' -> ' + DstDir);
  end;

  // 迁移 config/
  SrcDir := OldInstallDir + '\config';
  DstDir := NewAppDataDir + '\config';
  if DirExists(SrcDir) then
    CopyDirRecursive(SrcDir, DstDir);

  // 迁移 .env
  if FileExists(OldInstallDir + '\.env') and not FileExists(NewAppDataDir + '\.env') then
    FileCopy(OldInstallDir + '\.env', NewAppDataDir + '\.env', False);

  // logs/ 不迁移：体积大且无价值，新版本自动重建
end;
```

### 迁移策略
- **复制而非移动**：避免迁移失败导致数据丢失
- **目标存在则跳过**：避免覆盖已有数据（用 `xianyu.db` 存在性判断）
- **用户确认**：仅一次弹窗，避免反复打扰
- **递归复制**：Inno Setup 无内置 `CopyTree`，使用 `FindFirst/FindNext` 递归实现
- **日志记录**：迁移过程写入 Inno Setup 日志（`Log()` 函数）
- **大目录处理**：chromadb 向量库可能 GB 级，安装界面会暂时无响应（P2 阶段可改为外部 robocopy 异步执行 + 进度条）

---

## §7 端到端验证清单

### P0 阶段验证项
- [ ] 干净 Windows 10 虚拟机上安装 EXE，无报错
- [ ] 启动后 uvicorn 监听 8001 端口
- [ ] 自动打开浏览器访问 `/app/`
- [ ] 配置写入 `%APPDATA%\XianyuHunter\config\config.yaml` 生效
- [ ] SQLite 数据写入 `%APPDATA%\XianyuHunter\data\xianyu.db`
- [ ] Cookie 持久化到 `%APPDATA%\XianyuHunter\data\cookies_*.json`
- [ ] chromadb 向量库写入 `%APPDATA%\XianyuHunter\data\chromadb\`
- [ ] Playwright Chromium 从安装目录加载（不依赖系统 Playwright）
- [ ] 系统 Edge 检测正确，CDP 模式可用
- [ ] 系统 Edge 缺失时降级到 Playwright Chromium（无崩溃）

### P1 阶段验证项
- [ ] Inno Setup 安装程序双击运行无报错
- [ ] 桌面快捷方式创建成功
- [ ] 卸载后用户数据保留（`%APPDATA%\XianyuHunter\`）
- [ ] 旧版数据迁移到新版路径
- [ ] 安装包体积 < 300 MB（7z 压缩后）

---

## 八、实施建议

如确认推进，建议从 **P0 阶段** 开始，先在本机跑通最小可行版本：

1. **第 1 步**：实现 `paths.py` + 改造 8 处硬编码路径（开发模式下行为不变，可通过现有测试验证）
2. **第 2 步**：编写 `launcher.py` + `xianyu-hunter.spec`，本机 PyInstaller 打包
3. **第 3 步**：在干净 Windows 虚拟机验证 P0 清单

完成 P0 后再决定是否投入 P1/P2。需要我开始实施 P0 的第 1 步（paths.py 改造）吗？

---
