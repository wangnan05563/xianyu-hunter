"""T-PERF: 搭建隔离压测沙箱（独立端口 + 独立 data 副本 + 关闭调度器/穿透），并导出全量端点清单。

只在沙箱目录写入，绝不修改仓库 config/config.yaml 与 data/。
"""
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(r"D:\code\otherProjects\17_xianyu")
SANDBOX = Path(r"D:\tmp\xh-perf\sandbox")
OUT = Path(r"D:\tmp\xh-perf\output")


def build_sandbox() -> None:
    SANDBOX.mkdir(parents=True, exist_ok=True)
    (SANDBOX / "config").mkdir(exist_ok=True)
    (SANDBOX / "data").mkdir(exist_ok=True)

    # 配置：复制真实配置，仅沙箱副本内关掉穿透自启与调度相关开关
    src_cfg = (REPO / "config" / "config.yaml").read_text(encoding="utf-8")
    patched = re.sub(r"(?m)^(\s*)auto_start:\s*true\s*$", r"\1auto_start: false", src_cfg)
    (SANDBOX / "config" / "config.yaml").write_text(patched, encoding="utf-8")
    for extra in ("menu_registry.yaml", "eval.yaml", "param_rules.yaml"):
        f = REPO / "config" / extra
        if f.exists():
            shutil.copy2(f, SANDBOX / "config" / extra)

    # .env：原样复制（含令牌，仅落本机临时目录，压测后随沙箱删除）
    shutil.copy2(REPO / ".env", SANDBOX / ".env")

    # 数据库：一次性副本
    dst_db = SANDBOX / "data" / "xianyu.db"
    if not dst_db.exists():
        src = REPO / "data" / "xianyu.db"
        tmp = Path(tempfile.mkdtemp(prefix="xh-db-snap-")) / "xianyu.db"
        # 用 sqlite backup API 得到一致性快照，避免复制到半写状态
        with sqlite3.connect(str(src)) as s, sqlite3.connect(str(tmp)) as d:
            s.backup(d)
        shutil.copy2(tmp, dst_db)
        shutil.rmtree(tmp.parent, ignore_errors=True)
    size_mb = dst_db.stat().st_size / 1024 / 1024
    print(f"[sandbox] db copy: {size_mb:.1f} MB")
    print(f"[sandbox] root: {SANDBOX}")


def dump_openapi() -> list[dict]:
    sys.path.insert(0, str(REPO / "backend"))
    os.chdir(SANDBOX)
    from xianyu_hunter.web.app import create_app

    app = create_app()
    spec = app.openapi()
    endpoints = []
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            if method not in ("get", "post", "put", "delete", "patch"):
                continue
            endpoints.append({
                "method": method.upper(),
                "path": path,
                "summary": (op.get("summary") or "").strip(),
                "tag": (op.get("tags") or [""])[0],
                "has_body": bool(op.get("requestBody")),
                "params": [p["name"] for p in op.get("parameters", [])],
            })
    endpoints.sort(key=lambda e: (e["path"], e["method"]))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "endpoints.json").write_text(
        json.dumps(endpoints, ensure_ascii=False, indent=1), encoding="utf-8")
    api = [e for e in endpoints if e["path"].startswith("/api/")]
    print(f"[openapi] total={len(endpoints)} api={len(api)}")
    from collections import Counter
    print("[openapi] by tag:", dict(Counter(e['tag'] for e in api)))
    return endpoints


if __name__ == "__main__":
    build_sandbox()
    dump_openapi()
