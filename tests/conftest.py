"""pytest 配置：让 tests/ 目录能 import src/xianyu_hunter"""
import sys
from pathlib import Path

# 把项目根加入 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
