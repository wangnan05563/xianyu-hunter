"""版本号管理脚本：按 semver 规则递增版本号并同步多个文件。

用法：
    python scripts/bump_version.py major        # 1.2.3 → 2.0.0
    python scripts/bump_version.py minor        # 1.2.3 → 1.3.0
    python scripts/bump_version.py patch        # 1.2.3 → 1.2.4
    python scripts/bump_version.py auto         # 根据 git log 自动判断
    python scripts/bump_version.py 1.5.0        # 直接指定版本号

同步范围：
1. src/xianyu_hunter/__init__.py（__version__ 字段，单一源头）
2. pyproject.toml（version 字段，从 __init__.py 同步）
3. CHANGELOG.md（[Unreleased] 段落改写为新版本号 + 日期）
4. src/xianyu_hunter/_build_info.py（重新生成）
5. git tag（可选，--tag 参数触发）

为什么不用 bumpversion / bump2version：
- 避免引入额外依赖
- 项目仅需同步 2 个文件 + CHANGELOG，标准库即可完成
- 集成 CHANGELOG 改写是 bumpversion 不支持的定制逻辑

退出码：
0 = 成功
1 = 参数错误 / 版本号格式无效
2 = 文件读写错误
3 = git 操作失败（非致命，仅警告）
"""
from __future__ import annotations

import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# 项目根目录（scripts/ 的上一级）
PROJECT_ROOT = Path(__file__).resolve().parents[1]
INIT_FILE = PROJECT_ROOT / "src" / "xianyu_hunter" / "__init__.py"
PYPROJECT_FILE = PROJECT_ROOT / "pyproject.toml"
CHANGELOG_FILE = PROJECT_ROOT / "CHANGELOG.md"
BUILD_INFO_FILE = PROJECT_ROOT / "src" / "xianyu_hunter" / "_build_info.py"
BUILD_INFO_SCRIPT = PROJECT_ROOT / "scripts" / "build_info.py"

# semver 正则：MAJOR.MINOR.PATCH，无预发布后缀（项目目前不使用预发布）
_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
# __init__.py 中 __version__ = "x.y.z" 的匹配模式
_INIT_VERSION_RE = re.compile(r'^(__version__\s*=\s*)["\']([^"\']+)["\']', re.MULTILINE)
# pyproject.toml 中 version = "x.y.z" 的匹配模式
_PYPROJECT_VERSION_RE = re.compile(r'^(version\s*=\s*)["\']([^"\']+)["\']', re.MULTILINE)


# ---------------------------------------------------------------------------
# 版本号解析与递增
# ---------------------------------------------------------------------------

def parse_version(raw: str) -> tuple[int, int, int]:
    """解析 semver 字符串为 (major, minor, patch) 元组。

    格式非法时抛 ValueError，调用方负责提示用户。
    """
    m = _SEMVER_RE.match(raw.strip())
    if not m:
        raise ValueError(
            f"版本号格式非法：'{raw}'，应为 MAJOR.MINOR.PATCH（如 1.2.3）"
        )
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def bump_version(current: str, kind: str) -> str:
    """按 semver 规则递增版本号。

    kind 取值：
    - 'major': X.Y.Z → (X+1).0.0（破坏性变更）
    - 'minor': X.Y.Z → X.(Y+1).0（新功能，向后兼容）
    - 'patch': X.Y.Z → X.Y.(Z+1)（bug 修复，向后兼容）
    """
    major, minor, patch = parse_version(current)
    if kind == "major":
        return f"{major + 1}.0.0"
    if kind == "minor":
        return f"{major}.{minor + 1}.0"
    if kind == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError(f"未知的 bump 类型：'{kind}'，应为 major/minor/patch")


def detect_bump_kind_from_git() -> str:
    """根据自上一个 tag 以来的 commit message 自动判断 bump 类型。

    判定规则（保守策略）：
    - 任一 commit 含 'BREAKING CHANGE' 或 '!' 标记 → major
    - 任一 commit 以 'feat' 开头 → minor
    - 默认 → patch

    为什么保守：自动检测无法覆盖所有 semver 场景，patch 是最安全的默认值，
    用户应通过显式参数覆盖自动判断结果。
    """
    try:
        # 获取自上一个 tag 以来的 commit messages
        result = subprocess.run(
            ["git", "log", "--pretty=format:%s", "HEAD...$(git describe --tags --abbrev=0 2>nul)"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
            shell=True,  # Windows 需要 shell=True 支持 $(...) 命令替换
        )
        messages = result.stdout.lower()
    except Exception:
        # git 不可用时默认 patch
        return "patch"

    if "breaking change" in messages or "!: " in messages:
        return "major"
    if messages.startswith("feat") or "\nfeat" in messages:
        return "minor"
    return "patch"


# ---------------------------------------------------------------------------
# 文件读写与同步
# ---------------------------------------------------------------------------

def read_current_version() -> str:
    """从 __init__.py 读取当前版本号（单一源头）。

    失败时抛 FileNotFoundError 或 ValueError，调用方负责提示。
    """
    text = INIT_FILE.read_text(encoding="utf-8")
    m = _INIT_VERSION_RE.search(text)
    if not m:
        raise ValueError(f"无法在 {INIT_FILE} 中找到 __version__ 字段")
    return m.group(2)


def update_init_file(new_version: str) -> None:
    """更新 __init__.py 的 __version__ 字段。"""
    text = INIT_FILE.read_text(encoding="utf-8")
    new_text = _INIT_VERSION_RE.sub(
        lambda m: f'{m.group(1)}"{new_version}"',
        text,
    )
    if new_text == text:
        raise ValueError(f"__init__.py 替换失败：未找到 __version__ 字段")
    INIT_FILE.write_text(new_text, encoding="utf-8")


def update_pyproject_file(new_version: str) -> None:
    """同步 pyproject.toml 的 version 字段。

    为什么需要同步：setuptools 在打包时读取 pyproject.toml 的 version，
    若与 __init__.py 不一致会导致 pip install 后 __version__ 与元数据不符。
    """
    text = PYPROJECT_FILE.read_text(encoding="utf-8")
    new_text = _PYPROJECT_VERSION_RE.sub(
        lambda m: f'{m.group(1)}"{new_version}"',
        text,
    )
    if new_text == text:
        raise ValueError(f"pyproject.toml 替换失败：未找到 version 字段")
    PYPROJECT_FILE.write_text(new_text, encoding="utf-8")


def update_changelog(new_version: str) -> None:
    """将 CHANGELOG.md 的 [Unreleased] 段落封版为新版本号 + 今日日期。

    行为（幂等）：
    1. 若 `## [{new_version}]` 段落已存在 → 跳过插入（避免重复）
    2. 否则在 `## [Unreleased]` 行后插入 `## [{new_version}] - YYYY-MM-DD`
    3. 更新 [Unreleased] 的 compare 链接指向 v{new_version}...HEAD
    4. 若 `[{new_version}]:` 链接已存在 → 跳过追加；否则在 [Unreleased] 链接后追加

    为什么幂等：CHANGELOG 可能由人工预先编写 release notes（如本次 0.2.0），
    脚本重复运行不应产生重复段落或链接。

    为什么不清空 [Unreleased] 内容：bump 脚本只负责「封版」标题与链接，
    [Unreleased] 段落的内容清理由用户在 bump 前手动完成（把已积累的变更
    移动到新版本段落）。这样避免脚本误删用户尚未归类的内容。
    """
    if not CHANGELOG_FILE.exists():
        print(f"[WARN] CHANGELOG.md 不存在，跳过 changelog 更新")
        return

    text = CHANGELOG_FILE.read_text(encoding="utf-8")
    today = datetime.now().strftime("%Y-%m-%d")
    changed = False

    # 1. 检查版本段落是否已存在（幂等）
    section_pattern = re.compile(
        rf"^## \[{re.escape(new_version)}\]\s*-",
        re.MULTILINE,
    )
    if not section_pattern.search(text):
        # 在 [Unreleased] 行后插入新版本标题
        unreleased_pattern = re.compile(
            r"(## \[Unreleased\][^\n]*\n)",
            re.MULTILINE,
        )
        if not unreleased_pattern.search(text):
            print(f"[WARN] CHANGELOG.md 中未找到 '## [Unreleased]' 段落，跳过插入")
        else:
            new_section = f"\n## [{new_version}] - {today}\n"
            text = unreleased_pattern.sub(r"\1" + new_section, text, count=1)
            changed = True
    else:
        print(f"  [SKIP] CHANGELOG.md 中 [{new_version}] 段落已存在，跳过插入")

    # 2. 更新 [Unreleased] 的 compare 链接（始终执行，确保指向最新版本）
    new_compare = f"[Unreleased]: https://github.com/wangnan05563/xianyu-hunter/compare/v{new_version}...HEAD"
    old_compare_pattern = re.compile(
        r"\[Unreleased\]: https://[^\n]+compare/v[^\n]+\.\.\.HEAD",
    )
    if old_compare_pattern.search(text):
        new_text = old_compare_pattern.sub(new_compare, text)
        if new_text != text:
            text = new_text
            changed = True
    else:
        # [Unreleased] 链接不存在，在文件末尾追加
        text = text.rstrip() + "\n" + new_compare + "\n"
        changed = True

    # 3. 追加新版本链接（若不存在）
    link_line = f"[{new_version}]: https://github.com/wangnan05563/xianyu-hunter/releases/tag/v{new_version}"
    link_pattern = re.compile(
        rf"^\[{re.escape(new_version)}\]:\s*https://",
        re.MULTILINE,
    )
    if not link_pattern.search(text):
        # 在 [Unreleased] 链接行后插入新版本链接
        text = re.sub(
            r"(\[Unreleased\]: [^\n]+\n)",
            r"\1" + link_line + "\n",
            text,
            count=1,
        )
        changed = True
    else:
        print(f"  [SKIP] CHANGELOG.md 中 [{new_version}] 链接已存在，跳过追加")

    if changed:
        CHANGELOG_FILE.write_text(text, encoding="utf-8")


def regenerate_build_info() -> None:
    """调用 build_info.py 重新生成 _build_info.py。

    为什么调用子进程而非内联：build_info.py 已封装 git_sha 读取等逻辑，
    内联会引入重复代码。子进程调用保证单一来源。
    """
    try:
        result = subprocess.run(
            [sys.executable, str(BUILD_INFO_SCRIPT)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            print(f"  [OK] _build_info.py 重新生成")
        else:
            print(f"  [WARN] build_info.py 退出码 {result.returncode}：{result.stderr}")
    except Exception as e:
        print(f"  [WARN] 调用 build_info.py 失败：{e}")


def create_git_tag(new_version: str) -> None:
    """创建 git tag（v前缀）。

    失败仅警告，不中断流程（用户可手动创建 tag）。
    为什么用 v 前缀：GitHub Releases 默认按 'v' 前缀识别 tag，
    也符合 About API 的 _parse_version 解析规则。
    """
    tag = f"v{new_version}"
    try:
        # 检查 tag 是否已存在
        check = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", f"refs/tags/{tag}"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            timeout=3,
        )
        if check.returncode == 0:
            print(f"  [WARN] git tag {tag} 已存在，跳过创建")
            return

        subprocess.run(
            ["git", "tag", "-a", tag, "-m", f"Release {new_version}"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            timeout=5,
        )
        print(f"  [OK] git tag {tag} 已创建（未推送，请手动 git push --tags）")
    except subprocess.CalledProcessError as e:
        print(f"  [WARN] git tag 创建失败：{e.stderr.decode(errors='replace')}")
    except Exception as e:
        print(f"  [WARN] git tag 创建异常：{e}")


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 1

    arg = argv[1].lower()

    # 读取当前版本
    try:
        current = read_current_version()
    except Exception as e:
        print(f"[ERROR] 读取当前版本号失败：{e}")
        return 2
    print(f"[INFO] 当前版本：{current}")

    # 确定新版本号
    if arg in ("major", "minor", "patch"):
        new_version = bump_version(current, arg)
    elif arg == "auto":
        kind = detect_bump_kind_from_git()
        new_version = bump_version(current, kind)
        print(f"[INFO] 自动检测 bump 类型：{kind}")
    elif _SEMVER_RE.match(arg):
        # 直接指定版本号
        new_version = arg
        # 校验新版本号必须大于当前版本号
        c = parse_version(current)
        n = parse_version(new_version)
        if n <= c:
            print(f"[ERROR] 新版本号 {new_version} 必须大于当前版本号 {current}")
            return 1
    else:
        print(f"[ERROR] 无效参数：'{argv[1]}'")
        print("用法：python scripts/bump_version.py [major|minor|patch|auto|x.y.z] [--tag]")
        return 1

    # 检查 --tag 标志
    create_tag = "--tag" in argv

    print(f"[INFO] 新版本号：{new_version}")
    print()

    # 1. 更新 __init__.py
    try:
        update_init_file(new_version)
        print(f"  [OK] {INIT_FILE.relative_to(PROJECT_ROOT)} 已更新")
    except Exception as e:
        print(f"  [ERROR] 更新 __init__.py 失败：{e}")
        return 2

    # 2. 同步 pyproject.toml
    try:
        update_pyproject_file(new_version)
        print(f"  [OK] {PYPROJECT_FILE.relative_to(PROJECT_ROOT)} 已同步")
    except Exception as e:
        print(f"  [ERROR] 同步 pyproject.toml 失败：{e}")
        return 2

    # 3. 更新 CHANGELOG.md
    try:
        update_changelog(new_version)
        print(f"  [OK] {CHANGELOG_FILE.relative_to(PROJECT_ROOT)} 已更新")
    except Exception as e:
        print(f"  [WARN] 更新 CHANGELOG.md 失败：{e}")

    # 4. 重新生成 _build_info.py
    regenerate_build_info()

    # 5. 创建 git tag（可选）
    if create_tag:
        create_git_tag(new_version)

    print()
    print(f"[DONE] 版本号已从 {current} 升级到 {new_version}")
    if not create_tag:
        print(f"[HINT] 如需创建 git tag，请运行：python scripts/bump_version.py {new_version} --tag")
    print(f"[HINT] 提交变更：git add -A && git commit -m \"chore(release): v{new_version}\"")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
