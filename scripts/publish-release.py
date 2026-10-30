#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用 GitHub Release 发布脚本（零依赖，仅 Python 标准库）【模板，去硬编码】

把「创建 Release + 附带说明（读 Markdown 文件）+ 上传资产」三步原子化做完。
所有项目相关参数（仓库坐标 / 标签 / 资产路径 / 说明文件 / token 来源）全部来自
配置文件或命令行参数，脚本本身不硬编码任何项目名 / 路径 / 版本 / token。

两种用法：
  1) 直接传资产与说明（最通用）：
     python publish-release.py <资产路径> <说明md路径> [显示名] [repo] [tag]

  2) 读配置（推荐，去硬编码）：
     python publish-release.py --config config.json [--key github_release]
     脚本从 config 的 github_release 块解析 repo / tag / 资产(glob) / 说明(<VER>模板)，
     并自动定位最新资产、按版本推导说明文件路径、缺失时从 git log 生成。

token 读取优先级（见 github_release.token 配置）：
  环境变量 GH_TOKEN  >  本地 .env（gitignored，绝不入库）  >  git credential fill 兜底
说明文件读取：utf-8 -> gbk -> 系统默认 编码回退（兼容中文 Windows 记事本 GBK 保存）。

幂等：Release 已存在则复用；资产已存在则跳过上传。网络抖动自动重试。

完整规则：SKILL.md 规则 16 + references/retrospective.md 维度 16 + config/traps.md 陷阱 62-66。
"""
import argparse
import json
import locale
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API_BASE = os.environ.get("GH_API_BASE", "https://api.github.com").rstrip("/")
REPO = (os.environ.get("GH_REPO") or "").strip()
TAG = (os.environ.get("GH_TAG") or "").strip()
TOKEN = (os.environ.get("GH_TOKEN") or "").strip()
TARGET = (os.environ.get("GH_TARGET") or "").strip()
DRAFT = os.environ.get("GH_DRAFT", "0") == "1"
PRERELEASE = os.environ.get("GH_PRERELEASE", "0") == "1"
DRY_RUN = os.environ.get("GH_DRY_RUN", "0") == "1"


def _load_dotenv():
    """从本地 .env 读取配置（GitHub Token 等），不覆盖已存在的环境变量。

    查找顺序：当前工作目录（仓库根）-> 脚本所在目录。.env 必须被 .gitignore 忽略，
    不会入库；入库模板请用 .env.example（占位符）。配套陷阱 66。
    """
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = []
    for d in (os.getcwd(), here):
        p = os.path.join(d, ".env")
        if p not in candidates:
            candidates.append(p)
    for p in candidates:
        if not os.path.isfile(p):
            continue
        try:
            with open(p, encoding="utf-8") as f:
                for raw in f:
                    line = raw.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip()
                    if len(v) >= 2 and v[0] in ("'", '"') and v[-1] == v[0]:
                        v = v[1:-1]
                    if k and k not in os.environ:
                        os.environ[k] = v
        except Exception:
            pass


def _read_text(path):
    """读取文本文件，编码回退：utf-8 -> gbk -> 系统默认。

    兼容中文 Windows 下记事本以 GBK 保存的 .md / .env 等文件（陷阱 65）。
    """
    for enc in ("utf-8", "gbk", None):
        try:
            with open(path, encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    with open(path, encoding=locale.getpreferredencoding(False)) as f:
        return f.read()


_load_dotenv()


def sh(cmd):
    """跑一条 shell 命令，返回 stdout（失败返回空串，不抛）。"""
    try:
        out = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return (out.stdout or "").strip()
    except Exception:
        return ""


def detect_repo():
    url = sh("git remote get-url origin")
    url = url.replace("git@github.com:", "https://github.com/").replace(".git", "")
    if "github.com/" in url:
        return url.split("github.com/", 1)[1].strip("/")
    return ""


def detect_tag():
    return sh("git describe --tags --abbrev=0")


def detect_branch():
    b = sh("git rev-parse --abbrev-ref HEAD")
    return b or "master"


def fetch_token():
    """复用 git 凭据库里的 github.com 密码（即 PAT/凭证）。

    必须用 Python 子进程直接喂 stdin，不能依赖 shell 的 `printf | git credential
    fill`（Windows 原生 CMD 没有 printf，.bat 环境下会失败，陷阱 64）。
    """
    try:
        proc = subprocess.run(
            ["git", "credential", "fill"],
            input="protocol=https\nhost=github.com\n\n",
            capture_output=True, text=True, timeout=30,
        )
        for line in (proc.stdout or "").splitlines():
            if line.startswith("password="):
                return line[len("password="):].strip()
    except Exception:
        pass
    return ""


def api(path, data=None, method=None, base=None):
    base = base or API_BASE
    body = json.dumps(data).encode("utf-8") if data is not None else None
    last = None
    for attempt in range(5):
        try:
            req = urllib.request.Request(
                base + path, data=body,
                method=method or ("POST" if body else "GET"),
                headers={
                    "Authorization": "Bearer " + TOKEN,
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "publish-release",
                    "Content-Type": "application/json",
                })
            with urllib.request.urlopen(req, timeout=90) as r:
                txt = r.read().decode("utf-8")
                return r.status, (json.loads(txt) if txt else None)
        except urllib.error.HTTPError as e:
            payload = e.read().decode("utf-8", "replace")
            try:
                parsed = json.loads(payload) if payload else None
            except Exception:
                parsed = None
            last = (e.code, parsed or payload)
            if e.code in (409, 422):
                return e.code, parsed
            if e.code in (403, 429, 500, 502, 503):
                time.sleep(10)
                continue
            return last
        except Exception as e:
            last = ("EXC", str(e))
            time.sleep(10)
    return last


def get_existing_release_by_tag(tag):
    st, resp = api(f"/repos/{REPO}/releases/tags/{tag}")
    if st == 200 and isinstance(resp, dict):
        return resp
    return None


def resolve_from_config(cfg, key, repo_root):
    """从 config 的 github_release 块解析 repo/tag/asset/notes（去硬编码核心）。"""
    gh = cfg.get(key) or {}
    repo = gh.get("repo") or REPO or detect_repo()
    tag_source = gh.get("tag_source", "auto_git_describe")
    tag_value = gh.get("tag_value") or TAG
    if tag_source == "auto_git_describe":
        tag = tag_value or detect_tag()
    elif tag_source == "package_json":
        pj = os.path.join(repo_root, "package.json")
        tag = tag_value
        if os.path.isfile(pj):
            try:
                tag = json.load(open(pj, encoding="utf-8")).get("version", tag_value)
            except Exception:
                pass
    elif tag_source in ("config_field", "custom"):
        tag = tag_value
    else:
        tag = tag_value or detect_tag()

    # 资产定位：dir + glob，newest-first，排除 exclude_patterns
    asset = None
    adir = gh.get("asset", {})
    if adir.get("dir") and adir.get("glob"):
        full = os.path.join(repo_root, adir["dir"])
        try:
            files = [os.path.join(full, f) for f in os.listdir(full)
                     if os.path.isfile(os.path.join(full, f))]
        except Exception:
            files = []
        matches = []
        import fnmatch
        for fp in files:
            name = os.path.basename(fp)
            if fnmatch.fnmatch(name, adir["glob"]):
                excl = adir.get("exclude_patterns") or []
                if not any(x in name for x in excl):
                    matches.append(fp)
        matches.sort(key=os.path.getmtime, reverse=True)
        if matches:
            asset = matches[0]

    # 说明文件：<VER> 模板替换；缺失且 auto_generate 则 git log 生成
    notes = None
    ncfg = gh.get("notes") or {}
    pt = ncfg.get("path_template")
    if pt and tag:
        notes = os.path.join(repo_root, pt.replace("<VER>", tag))
        if not os.path.isfile(notes) and ncfg.get("auto_generate", True):
            gen = os.path.join(repo_root, pt.replace("<VER>", tag).replace(".md", ".auto.md"))
            log_args = ncfg.get("auto_generate_git_log", "--no-merges --oneline -20")
            try:
                with open(gen, "w", encoding="utf-8") as f:
                    f.write(f"# Release {tag}\n\n")
                    f.write("（自动生成的发布说明，来自 git 提交记录；正式发布前请替换为正式说明。）\n\n")
                    f.write(sh(f'git -C "{repo_root}" log {log_args}'))
                notes = gen
            except Exception:
                pass

    display = os.path.basename(asset) if asset else (gh.get("publish_script") or "asset")
    return repo, tag, asset, notes, display


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("asset", nargs="?")
    ap.add_argument("notes", nargs="?")
    ap.add_argument("display_name", nargs="?")
    ap.add_argument("repo", nargs="?")
    ap.add_argument("tag", nargs="?")
    ap.add_argument("--config", help="配置文件路径（JSON）")
    ap.add_argument("--key", default="github_release", help="config 中发布配置所在 key")
    args = ap.parse_args()

    global REPO, TAG, TOKEN, TARGET
    repo_root = os.getcwd()

    # 配置模式：从 config.github_release 解析全部参数（去硬编码）
    if args.config:
        cfg = json.load(open(args.config, encoding="utf-8"))
        repo_root = os.path.dirname(os.path.abspath(args.config)) or repo_root
        r, t, asset, notes, display = resolve_from_config(cfg, args.key, repo_root)
        REPO = r
        TAG = t
        if args.asset:
            asset = os.path.abspath(args.asset)
        if args.notes:
            notes = os.path.abspath(args.notes)
        if args.display_name:
            display = args.display_name
    else:
        if not args.asset or not args.notes:
            sys.exit("用法: python publish-release.py <资产路径> <说明md路径> [显示名] [repo] [tag]  |  或 --config <config.json>")
        asset = os.path.abspath(args.asset)
        notes = os.path.abspath(args.notes)
        display = args.display_name or os.path.basename(asset)

    if not REPO:
        REPO = args.repo or detect_repo()
    if not TAG:
        TAG = args.tag or detect_tag()
    if not TOKEN:
        TOKEN = fetch_token()
    if not TARGET:
        TARGET = detect_branch()

    if not REPO:
        sys.exit("无法确定仓库（GH_REPO 未设且 git remote 无 github.com origin）")
    if not TAG:
        sys.exit("无法确定标签（GH_TAG 未设且无 git tag）")
    if not asset or not os.path.isfile(asset):
        sys.exit(f"资产不存在: {asset}")
    if not notes or not os.path.isfile(notes):
        sys.exit(f"说明文件不存在: {notes}")

    print(f"仓库={REPO}  标签={TAG}  目标={TARGET}  draft={DRAFT} prerelease={PRERELEASE}")
    print(f"资产={asset}\n说明={notes}")

    body = _read_text(notes)

    if DRY_RUN:
        size = os.path.getsize(asset)
        print("\n[DRY-RUN] 以下动作【不会】真正执行：")
        print(f"  POST /repos/{REPO}/releases")
        print(f"    tag_name   = {TAG}")
        print(f"    target     = {TARGET}")
        print(f"    name       = {display}")
        print(f"    draft      = {DRAFT}  prerelease = {PRERELEASE}")
        print(f"    body 长度  = {len(body)} 字符")
        print(f"  UPLOAD 资产  = {display}  ({size} bytes)")
        print("  （设置 GH_DRY_RUN=0 或清除该变量后重跑即可真正发布）")
        return

    if len(TOKEN) < int(os.environ.get("GH_TOKEN_MIN_LEN", "20")):
        sys.exit("GH_TOKEN 缺失（环境变量 / .env / git 凭据库均无 github.com 凭证）")

    st, resp = api(f"/repos/{REPO}/releases", {
        "tag_name": TAG,
        "target_commitish": TARGET,
        "name": display,
        "body": body,
        "draft": DRAFT,
        "prerelease": PRERELEASE,
    })
    if st not in (200, 201) and st not in (409, 422):
        print("create release 失败:", st, json.dumps(resp, ensure_ascii=False)[:800])
        sys.exit(1)

    if isinstance(resp, dict) and "upload_url" in resp:
        release = resp
    else:
        release = get_existing_release_by_tag(TAG)
        if not release:
            print("无法获取已有 Release，退出。", json.dumps(resp, ensure_ascii=False)[:400])
            sys.exit(1)
    print("release id:", release.get("id"), "html:", release.get("html_url"))

    assets = release.get("assets") or []
    already = {a.get("name") for a in assets}
    if display in already:
        print("资产已存在，跳过上传:", display)
        return

    upload_url = release["upload_url"].split("{")[0] + "?name=" + urllib.parse.quote(display)
    size = os.path.getsize(asset)
    data = open(asset, "rb").read()
    print("上传中", display, f"{size} bytes ...")
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(
                upload_url, data=data, method="POST",
                headers={
                    "Authorization": "Bearer " + TOKEN,
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "publish-release",
                    "Content-Type": "application/octet-stream",
                    "Content-Length": str(size),
                })
            with urllib.request.urlopen(req, timeout=1800) as r:
                j = json.loads(r.read().decode("utf-8"))
                print("资产上传完成:", r.status, j.get("name"), j.get("size"), j.get("browser_download_url"))
            return
        except Exception as e:
            last = e
            print(f"  上传第 {attempt + 1} 次失败: {str(e)[:200]}")
            time.sleep(15)
    sys.exit(f"资产上传失败: {last}")


if __name__ == "__main__":
    main()
