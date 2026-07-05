"""路径集中管理

打包模式（PyInstaller）下数据写入 %APPDATA%\\XianyuHunter\\，
开发模式下保持 CWD 相对路径（向后兼容现有 1394 个测试的 monkeypatch.chdir 隔离机制）。

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
    # 开发模式：CWD（pytest 通过 chdir 切换，启动器从项目根启动）
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
