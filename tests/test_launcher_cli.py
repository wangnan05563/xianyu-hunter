"""T01676：打包版 launcher 命令行参数解析与端口清理防误杀

- launcher 主入口此前硬编码 host=127.0.0.1 / port=8001 并静默丢弃其余 argv；
  现接入 argparse，与开发模式 __main__.py web 命令对齐（--host/--port/--no-with-scheduler）。
- _cleanup_port 此前对监听进程一律 taskkill；现杀前核对进程映像名，
  仅强杀本应用相关进程，其余只告警跳过。
"""
from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_LAUNCHER_PATH = _PROJECT_ROOT / "scripts" / "launcher.py"

_spec = importlib.util.spec_from_file_location("launcher_under_test", _LAUNCHER_PATH)
assert _spec is not None and _spec.loader is not None
launcher = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("launcher_under_test", launcher)
_spec.loader.exec_module(launcher)


# ---------------------------------------------------------------------------
# 参数解析
# ---------------------------------------------------------------------------


class TestParseArgs:
    def test_defaults_match_legacy_behavior(self):
        """不传参数时保持旧行为：web / 127.0.0.1:8001 / 启用调度器"""
        args = launcher._parse_args([])
        assert args.command == "web"
        assert args.host == "127.0.0.1"
        assert args.port == 8001
        assert args.with_scheduler is True

    def test_web_port_no_scheduler(self):
        """T01676 验收命令：web --port 8124 --no-with-scheduler"""
        args = launcher._parse_args(["web", "--port", "8124", "--no-with-scheduler"])
        assert args.command == "web"
        assert args.port == 8124
        assert args.with_scheduler is False

    def test_host_and_port(self):
        args = launcher._parse_args(["--host", "0.0.0.0", "--port", "8124"])
        assert args.host == "0.0.0.0"
        assert args.port == 8124

    def test_explicit_with_scheduler(self):
        args = launcher._parse_args(["web", "--with-scheduler"])
        assert args.with_scheduler is True

    def test_unknown_argument_rejected(self):
        """未识别参数必须报错退出（告警而非静默丢弃）"""
        with pytest.raises(SystemExit) as exc_info:
            launcher._parse_args(["--totally-unknown"])
        assert exc_info.value.code == 2

    def test_invalid_port_type_rejected(self):
        with pytest.raises(SystemExit):
            launcher._parse_args(["--port", "not-a-number"])

    def test_unknown_subcommand_rejected(self):
        with pytest.raises(SystemExit):
            launcher._parse_args(["serve"])


# ---------------------------------------------------------------------------
# _cleanup_port 防误杀
# ---------------------------------------------------------------------------


def _netstat_result(lines: list[str]) -> MagicMock:
    fake = MagicMock(spec=subprocess.CompletedProcess)
    fake.stdout = "\n".join(lines)
    return fake


def _tasklist_result(csv_line: str) -> MagicMock:
    fake = MagicMock(spec=subprocess.CompletedProcess)
    fake.stdout = csv_line + "\r\n" if csv_line else ""
    return fake


class TestGetProcessImageName:
    def test_parses_csv_first_column(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _tasklist_result('"xianyu-hunter.exe","1234","Console","1","100 K"'),
        )
        assert launcher._get_process_image_name("1234") == "xianyu-hunter.exe"

    def test_lowercases_image_name(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _tasklist_result('"Chrome.EXE","999","Console","1","1 K"'),
        )
        assert launcher._get_process_image_name("999") == "chrome.exe"

    def test_empty_output_returns_empty(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run", lambda *a, **kw: _tasklist_result("")
        )
        assert launcher._get_process_image_name("1") == ""

    def test_subprocess_failure_returns_empty(self, monkeypatch):
        def _boom(*a, **kw):
            raise subprocess.SubprocessError("tasklist broken")

        monkeypatch.setattr(subprocess, "run", _boom)
        assert launcher._get_process_image_name("1") == ""


class TestCleanupPort:
    _NETSTAT_HIT = [
        "  TCP    127.0.0.1:8001       0.0.0.0:0    LISTENING    4242",
        "  TCP    127.0.0.1:8443       0.0.0.0:0    LISTENING    4242",
    ]

    def test_kills_own_process(self, monkeypatch):
        """本应用映像名 → 照旧 taskkill"""
        calls: list[list[str]] = []

        def fake_run(cmd, *a, **kw):
            if cmd[0] == "netstat":
                return _netstat_result(self._NETSTAT_HIT)
            if cmd[0] == "tasklist":
                return _tasklist_result('"xianyu-hunter.exe","4242","Console","1","1 K"')
            calls.append(list(cmd))
            return MagicMock(stdout="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        launcher._cleanup_port(8001)
        assert any(c[:2] == ["taskkill", "/F"] for c in calls)

    def test_kills_python_process(self, monkeypatch):
        """python.exe（开发模式残留）也属本应用范畴"""
        calls: list[list[str]] = []

        def fake_run(cmd, *a, **kw):
            if cmd[0] == "netstat":
                return _netstat_result(self._NETSTAT_HIT)
            if cmd[0] == "tasklist":
                return _tasklist_result('"python.exe","4242","Console","1","1 K"')
            calls.append(list(cmd))
            return MagicMock(stdout="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        launcher._cleanup_port(8001)
        assert any(c[0] == "taskkill" for c in calls)

    def test_skips_foreign_process(self, monkeypatch, capsys):
        """非本应用进程（如 chrome.exe）占端口 → 只告警不杀（T01676 防误杀核心）"""
        calls: list[list[str]] = []

        def fake_run(cmd, *a, **kw):
            if cmd[0] == "netstat":
                return _netstat_result(self._NETSTAT_HIT)
            if cmd[0] == "tasklist":
                return _tasklist_result('"chrome.exe","4242","Console","1","1 K"')
            calls.append(list(cmd))
            return MagicMock(stdout="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        launcher._cleanup_port(8001)
        assert not any(c[0] == "taskkill" for c in calls)
        out = capsys.readouterr().out
        assert "chrome.exe" in out
        assert "跳过清理" in out

    def test_kills_when_image_unknown(self, monkeypatch):
        """tasklist 异常查不到映像名 → 保持旧行为照杀（保证端口可用）"""
        calls: list[list[str]] = []

        def fake_run(cmd, *a, **kw):
            if cmd[0] == "netstat":
                return _netstat_result(self._NETSTAT_HIT)
            if cmd[0] == "tasklist":
                raise subprocess.SubprocessError("broken")
            calls.append(list(cmd))
            return MagicMock(stdout="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        launcher._cleanup_port(8001)
        assert any(c[0] == "taskkill" for c in calls)

    def test_other_port_untouched(self, monkeypatch):
        """其他端口的监听进程不被波及（正则只命中目标端口）"""
        calls: list[list[str]] = []

        def fake_run(cmd, *a, **kw):
            if cmd[0] == "netstat":
                return _netstat_result(["  TCP    0.0.0.0:8080    0.0.0.0:0    LISTENING    5555"])
            if cmd[0] == "tasklist":
                return _tasklist_result('"xianyu-hunter.exe","5555","Console","1","1 K"')
            calls.append(list(cmd))
            return MagicMock(stdout="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        launcher._cleanup_port(8001)
        assert not any(c[0] == "taskkill" for c in calls)


# ---------------------------------------------------------------------------
# 单实例锁按端口区分
# ---------------------------------------------------------------------------


class TestSingleInstanceMutex:
    def test_default_mutex_name(self, monkeypatch):
        created: list[str] = []

        class FakeKernel32:
            def CreateMutexW(self, attrs, initial, name):
                created.append(name)
                return 1

            def GetLastError(self):
                return 0

        monkeypatch.setattr(launcher.ctypes, "windll", MagicMock(kernel32=FakeKernel32()))
        assert launcher._acquire_single_instance("XianyuHunter-Mutex") is True
        assert created == ["XianyuHunter-Mutex"]

    def test_existing_mutex_fails(self, monkeypatch):
        class FakeKernel32:
            def CreateMutexW(self, attrs, initial, name):
                return 0

            def GetLastError(self):
                return 183  # ERROR_ALREADY_EXISTS

        monkeypatch.setattr(launcher.ctypes, "windll", MagicMock(kernel32=FakeKernel32()))
        assert launcher._acquire_single_instance("XianyuHunter-Mutex") is False

    def test_mutex_name_convention(self):
        """默认端口全局锁（防多开）；自定义端口独立锁（允许与默认实例共存）"""
        assert launcher._mutex_name_for_port(8001) == "XianyuHunter-Mutex"
        assert launcher._mutex_name_for_port(8124) == "XianyuHunter-Mutex-8124"
