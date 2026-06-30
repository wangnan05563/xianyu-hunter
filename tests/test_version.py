"""bump_version.py 单元测试

测试策略：
1. parse_version / bump_version 是纯函数，直接测试输入输出
2. update_init_file / update_pyproject_file / update_changelog 需要 monkeypatch
   模块级常量到 tmp_path，避免污染真实项目文件
3. update_changelog 的幂等性是重点测试项（避免重复运行产生重复段落）

为什么用 monkeypatch 而非直接修改模块常量：bump_version.py 的 INIT_FILE /
PYPROJECT_FILE / CHANGELOG_FILE 是模块级常量，测试时需指向 tmp_path 下的
临时文件。monkeypatch 在测试结束后自动恢复，无副作用。
"""
import sys
from pathlib import Path

import pytest

# 把 scripts/ 目录加入 sys.path 以便 import bump_version
# 为什么不放入 conftest.py：bump_version 是构建脚本而非运行时模块，
# 仅本测试需要 import，放入 conftest 会污染其他测试的 sys.path。
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import bump_version  # noqa: E402


# ---------------------------------------------------------------------------
# parse_version
# ---------------------------------------------------------------------------

class TestParseVersion:
    """parse_version 函数测试"""

    def test_valid_versions(self):
        assert bump_version.parse_version("0.2.0") == (0, 2, 0)
        assert bump_version.parse_version("1.2.3") == (1, 2, 3)
        assert bump_version.parse_version("10.20.30") == (10, 20, 30)

    def test_strips_whitespace(self):
        assert bump_version.parse_version("  0.2.0  ") == (0, 2, 0)

    def test_invalid_format_raises(self):
        for invalid in ["0.2", "0.2.0.1", "v0.2.0", "0.2.x", "", "abc"]:
            with pytest.raises(ValueError):
                bump_version.parse_version(invalid)

    def test_no_prerelease_suffix(self):
        # 项目当前不支持预发布版本，应拒绝
        for invalid in ["0.2.0-alpha.1", "0.2.0+build.1", "0.2.0-rc.1"]:
            with pytest.raises(ValueError):
                bump_version.parse_version(invalid)


# ---------------------------------------------------------------------------
# bump_version
# ---------------------------------------------------------------------------

class TestBumpVersion:
    """bump_version 函数测试"""

    def test_major_bump(self):
        assert bump_version.bump_version("0.2.0", "major") == "1.0.0"
        assert bump_version.bump_version("1.2.3", "major") == "2.0.0"

    def test_minor_bump(self):
        assert bump_version.bump_version("0.1.0", "minor") == "0.2.0"
        assert bump_version.bump_version("1.2.3", "minor") == "1.3.0"

    def test_patch_bump(self):
        assert bump_version.bump_version("0.2.0", "patch") == "0.2.1"
        assert bump_version.bump_version("1.2.3", "patch") == "1.2.4"

    def test_major_resets_minor_and_patch(self):
        assert bump_version.bump_version("1.9.9", "major") == "2.0.0"

    def test_minor_resets_patch(self):
        assert bump_version.bump_version("1.2.9", "minor") == "1.3.0"

    def test_invalid_kind_raises(self):
        for invalid in ["hotfix", "", "MINOR", "rc", None]:
            with pytest.raises((ValueError, TypeError)):
                bump_version.bump_version("0.2.0", invalid)

    def test_invalid_version_raises(self):
        with pytest.raises(ValueError):
            bump_version.bump_version("invalid", "minor")


# ---------------------------------------------------------------------------
# update_init_file
# ---------------------------------------------------------------------------

class TestUpdateInitFile:
    """update_init_file 函数测试"""

    def test_updates_version(self, tmp_path, monkeypatch):
        init_file = tmp_path / "__init__.py"
        init_file.write_text(
            '"""XianyuHunter - 闲鱼自动捡漏系统"""\n\n__version__ = "0.1.0"\n',
            encoding="utf-8",
        )
        monkeypatch.setattr(bump_version, "INIT_FILE", init_file)

        bump_version.update_init_file("0.2.0")

        text = init_file.read_text(encoding="utf-8")
        assert '__version__ = "0.2.0"' in text
        assert "0.1.0" not in text

    def test_preserves_other_content(self, tmp_path, monkeypatch):
        init_file = tmp_path / "__init__.py"
        original = (
            '"""XianyuHunter - 闲鱼自动捡漏系统"""\n'
            "\n"
            '__version__ = "0.1.0"\n'
            "\n"
            'APP_NAME = "XianyuHunter"\n'
        )
        init_file.write_text(original, encoding="utf-8")
        monkeypatch.setattr(bump_version, "INIT_FILE", init_file)

        bump_version.update_init_file("0.2.0")

        text = init_file.read_text(encoding="utf-8")
        assert 'APP_NAME = "XianyuHunter"' in text
        assert '__version__ = "0.2.0"' in text

    def test_single_quotes_normalized_to_double(self, tmp_path, monkeypatch):
        init_file = tmp_path / "__init__.py"
        init_file.write_text("__version__ = '0.1.0'\n", encoding="utf-8")
        monkeypatch.setattr(bump_version, "INIT_FILE", init_file)

        bump_version.update_init_file("0.2.0")

        text = init_file.read_text(encoding="utf-8")
        assert '__version__ = "0.2.0"' in text

    def test_no_version_field_raises(self, tmp_path, monkeypatch):
        init_file = tmp_path / "__init__.py"
        init_file.write_text('"""No version here"""\n', encoding="utf-8")
        monkeypatch.setattr(bump_version, "INIT_FILE", init_file)

        with pytest.raises(ValueError):
            bump_version.update_init_file("0.2.0")

    def test_file_not_found_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(bump_version, "INIT_FILE", tmp_path / "nonexistent.py")

        with pytest.raises(FileNotFoundError):
            bump_version.update_init_file("0.2.0")


# ---------------------------------------------------------------------------
# update_pyproject_file
# ---------------------------------------------------------------------------

class TestUpdatePyprojectFile:
    """update_pyproject_file 函数测试"""

    def test_updates_version(self, tmp_path, monkeypatch):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "xianyu-hunter"\nversion = "0.1.0"\n',
            encoding="utf-8",
        )
        monkeypatch.setattr(bump_version, "PYPROJECT_FILE", pyproject)

        bump_version.update_pyproject_file("0.2.0")

        text = pyproject.read_text(encoding="utf-8")
        assert 'version = "0.2.0"' in text
        assert 'version = "0.1.0"' not in text

    def test_preserves_other_fields(self, tmp_path, monkeypatch):
        pyproject = tmp_path / "pyproject.toml"
        original = (
            '[project]\n'
            'name = "xianyu-hunter"\n'
            'version = "0.1.0"\n'
            'description = "闲鱼自动捡漏"\n'
            'requires-python = ">=3.10"\n'
        )
        pyproject.write_text(original, encoding="utf-8")
        monkeypatch.setattr(bump_version, "PYPROJECT_FILE", pyproject)

        bump_version.update_pyproject_file("0.2.0")

        text = pyproject.read_text(encoding="utf-8")
        assert 'name = "xianyu-hunter"' in text
        assert 'description = "闲鱼自动捡漏"' in text
        assert 'requires-python = ">=3.10"' in text
        assert 'version = "0.2.0"' in text

    def test_no_version_field_raises(self, tmp_path, monkeypatch):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "xianyu-hunter"\n', encoding="utf-8")
        monkeypatch.setattr(bump_version, "PYPROJECT_FILE", pyproject)

        with pytest.raises(ValueError):
            bump_version.update_pyproject_file("0.2.0")


# ---------------------------------------------------------------------------
# update_changelog
# ---------------------------------------------------------------------------

class TestUpdateChangelog:
    """update_changelog 函数测试（含幂等性）"""

    @pytest.fixture
    def changelog_with_unreleased(self, tmp_path, monkeypatch):
        """创建一个带 [Unreleased] 段落的 CHANGELOG.md"""
        changelog = tmp_path / "CHANGELOG.md"
        content = (
            "# Changelog\n\n"
            "## [Unreleased]\n\n"
            "### Added\n"
            "- 新功能\n\n"
            "## [0.1.0] - 2026-06-06\n\n"
            "### Added\n"
            "- 初始版本\n\n"
            "[Unreleased]: https://github.com/wangnan05563/xianyu-hunter/compare/v0.1.0...HEAD\n"
            "[0.1.0]: https://github.com/wangnan05563/xianyu-hunter/releases/tag/v0.1.0\n"
        )
        changelog.write_text(content, encoding="utf-8")
        monkeypatch.setattr(bump_version, "CHANGELOG_FILE", changelog)
        return changelog

    def test_inserts_new_version_section(self, changelog_with_unreleased):
        bump_version.update_changelog("0.2.0")

        text = changelog_with_unreleased.read_text(encoding="utf-8")
        assert "## [0.2.0] - " in text
        assert "## [Unreleased]" in text  # 原段落保留
        assert "## [0.1.0] - 2026-06-06" in text

    def test_updates_unreleased_compare_link(self, changelog_with_unreleased):
        bump_version.update_changelog("0.2.0")

        text = changelog_with_unreleased.read_text(encoding="utf-8")
        assert "compare/v0.2.0...HEAD" in text
        assert "compare/v0.1.0...HEAD" not in text

    def test_appends_new_version_link(self, changelog_with_unreleased):
        bump_version.update_changelog("0.2.0")

        text = changelog_with_unreleased.read_text(encoding="utf-8")
        assert "[0.2.0]: https://github.com/wangnan05563/xianyu-hunter/releases/tag/v0.2.0" in text
        # 原链接保留
        assert "[0.1.0]: https://github.com/wangnan05563/xianyu-hunter/releases/tag/v0.1.0" in text

    def test_idempotent_no_duplicate_section(self, changelog_with_unreleased):
        """重复运行不产生重复段落"""
        bump_version.update_changelog("0.2.0")
        bump_version.update_changelog("0.2.0")

        text = changelog_with_unreleased.read_text(encoding="utf-8")
        assert text.count("## [0.2.0]") == 1

    def test_idempotent_no_duplicate_link(self, changelog_with_unreleased):
        """重复运行不产生重复链接"""
        bump_version.update_changelog("0.2.0")
        bump_version.update_changelog("0.2.0")

        text = changelog_with_unreleased.read_text(encoding="utf-8")
        assert text.count("[0.2.0]: https://") == 1

    def test_preserves_existing_section_content(self, tmp_path, monkeypatch):
        """已存在版本段落时，保留原有内容不覆盖（仅更新链接）"""
        changelog = tmp_path / "CHANGELOG.md"
        content = (
            "# Changelog\n\n"
            "## [Unreleased]\n\n"
            "_已封版_\n\n"
            "## [0.2.0] - 2026-06-28\n\n"
            "### Summary\n"
            "本次发布的完整说明\n\n"
            "[Unreleased]: https://github.com/wangnan05563/xianyu-hunter/compare/v0.1.0...HEAD\n"
            "[0.2.0]: https://github.com/wangnan05563/xianyu-hunter/releases/tag/v0.2.0\n"
            "[0.1.0]: https://github.com/wangnan05563/xianyu-hunter/releases/tag/v0.1.0\n"
        )
        changelog.write_text(content, encoding="utf-8")
        monkeypatch.setattr(bump_version, "CHANGELOG_FILE", changelog)

        bump_version.update_changelog("0.2.0")

        text = changelog.read_text(encoding="utf-8")
        # 原内容保留
        assert "本次发布的完整说明" in text
        assert "## [0.2.0] - 2026-06-28" in text  # 原日期不覆盖
        # 不产生重复段落
        assert text.count("## [0.2.0]") == 1
        # compare 链接更新为指向 0.2.0
        assert "compare/v0.2.0...HEAD" in text
        assert "compare/v0.1.0...HEAD" not in text

    def test_no_unreleased_section_skips_insert(self, tmp_path, monkeypatch, capsys):
        """CHANGELOG 无 [Unreleased] 段落时跳过插入"""
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text("# Changelog\n\n## [0.1.0] - 2026-06-06\n", encoding="utf-8")
        monkeypatch.setattr(bump_version, "CHANGELOG_FILE", changelog)

        bump_version.update_changelog("0.2.0")

        captured = capsys.readouterr()
        assert "未找到" in captured.out or "SKIP" in captured.out

    def test_nonexistent_changelog_warns(self, tmp_path, monkeypatch, capsys):
        """CHANGELOG 不存在时跳过"""
        monkeypatch.setattr(bump_version, "CHANGELOG_FILE", tmp_path / "nonexistent.md")

        bump_version.update_changelog("0.2.0")

        captured = capsys.readouterr()
        assert "WARN" in captured.out

    def test_multiple_bumps_in_sequence(self, changelog_with_unreleased):
        """连续 bump 多个版本，段落与链接按序追加"""
        bump_version.update_changelog("0.2.0")
        bump_version.update_changelog("0.3.0")

        text = changelog_with_unreleased.read_text(encoding="utf-8")
        assert "## [0.2.0]" in text
        assert "## [0.3.0]" in text
        assert "[0.2.0]: https://" in text
        assert "[0.3.0]: https://" in text
        # compare 链接指向最新版本
        assert "compare/v0.3.0...HEAD" in text


# ---------------------------------------------------------------------------
# read_current_version
# ---------------------------------------------------------------------------

class TestReadCurrentVersion:
    """read_current_version 函数测试"""

    def test_reads_version(self, tmp_path, monkeypatch):
        init_file = tmp_path / "__init__.py"
        init_file.write_text('__version__ = "0.2.0"\n', encoding="utf-8")
        monkeypatch.setattr(bump_version, "INIT_FILE", init_file)

        assert bump_version.read_current_version() == "0.2.0"

    def test_reads_version_with_other_content(self, tmp_path, monkeypatch):
        init_file = tmp_path / "__init__.py"
        init_file.write_text(
            '"""XianyuHunter"""\n\n__version__ = "1.2.3"\n\nAPP = "xh"\n',
            encoding="utf-8",
        )
        monkeypatch.setattr(bump_version, "INIT_FILE", init_file)

        assert bump_version.read_current_version() == "1.2.3"

    def test_file_not_found_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(bump_version, "INIT_FILE", tmp_path / "nonexistent.py")

        with pytest.raises(FileNotFoundError):
            bump_version.read_current_version()

    def test_no_version_field_raises(self, tmp_path, monkeypatch):
        init_file = tmp_path / "__init__.py"
        init_file.write_text('"""no version"""\n', encoding="utf-8")
        monkeypatch.setattr(bump_version, "INIT_FILE", init_file)

        with pytest.raises(ValueError):
            bump_version.read_current_version()
