"""内网穿透保存回执的诚实性（T02590 / PRD 4.6-1、FR-F-1）

`POST /api/tunnel/config` 在实现上会**重建 service 单例并停掉旧隧道**（异步线程，
因为 Tailscale 之类的慢命令同步 stop 会让前端超时）。也就是说：隧道正在运行时点「保存」，
等于当场断线、公网地址立刻失效。

旧回执无论运行与否都写「配置已保存，下次启动隧道时生效」，是本页最直接的假话
（前端 T02573 已按运行态分叉文案，但后端这句话还在，任何直连 API 的用户照旧被误导）。
本文件把后端侧钉死：运行态必须说「已断开」，空闲态必须带上「当前无运行中的隧道」限定。
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from xianyu_hunter.web.routes import api_tunnel


class _StubService:
    def __init__(self, status_value="running", raise_on_status=False) -> None:
        self._status_value = status_value
        self._raise = raise_on_status
        self.stopped = threading.Event()

    def status(self) -> str:
        if self._raise:
            raise RuntimeError("provider 未就绪")
        return self._status_value

    def stop(self) -> None:
        self.stopped.set()


def _patch_io(monkeypatch, tmp_path: Path):
    """把写 yaml 与热重载替换成空操作，只测回执逻辑"""
    monkeypatch.setattr(api_tunnel, "_load_yaml_raw", lambda: {"tunnel": {"provider": "cloudflare"}})
    target = tmp_path / "config.yaml"
    monkeypatch.setattr(api_tunnel, "_config_yaml_path", lambda: target)
    monkeypatch.setattr(api_tunnel, "reload_config", lambda: None)
    return target


def _body(resp) -> dict:
    assert resp.status_code == 200
    return json.loads(resp.body)


def test_save_while_running_reports_tunnel_dropped(monkeypatch, tmp_path):
    _patch_io(monkeypatch, tmp_path)
    stub = _StubService("running")
    monkeypatch.setattr(api_tunnel, "_tunnel_service", stub, raising=False)

    data = _body(api_tunnel.tunnel_config_save(api_tunnel.TunnelConfigBody()))

    assert data["ok"] is True
    assert data["tunnel_was_running"] is True
    # 真实后果必须写在回执里，而不是留给前端猜
    assert "当前隧道已断开" in data["message"]
    assert "公网地址失效" in data["message"]
    # 旧假话：运行态绝不能再说「下次启动生效」
    assert "下次启动隧道时生效" not in data["message"]


def test_save_while_idle_keeps_next_start_wording_with_qualifier(monkeypatch, tmp_path):
    _patch_io(monkeypatch, tmp_path)
    monkeypatch.setattr(api_tunnel, "_tunnel_service", None, raising=False)

    data = _body(api_tunnel.tunnel_config_save(api_tunnel.TunnelConfigBody()))

    assert data["tunnel_was_running"] is False
    assert "下次启动隧道时生效" in data["message"]
    # 必须自带限定语，不能退回到裸的「配置已保存，下次启动隧道时生效」
    assert "当前无运行中的隧道" in data["message"]
    assert data["message"] != "配置已保存，下次启动隧道时生效"


def test_save_stops_previous_service_instance(monkeypatch, tmp_path):
    """回执说「已断开」的前提是真的执行了断开"""
    _patch_io(monkeypatch, tmp_path)
    stub = _StubService("running")
    monkeypatch.setattr(api_tunnel, "_tunnel_service", stub, raising=False)

    api_tunnel.tunnel_config_save(api_tunnel.TunnelConfigBody())

    assert stub.stopped.wait(5), "旧 service 未被 stop，回执内容与实际行为不符"
    assert api_tunnel._tunnel_service is None


def test_status_probe_failure_is_treated_as_running(monkeypatch, tmp_path):
    """探测状态失败时按「可能正在运行」处理——宁可提示断线，也不谎报不影响当前隧道"""
    _patch_io(monkeypatch, tmp_path)
    stub = _StubService(raise_on_status=True)
    monkeypatch.setattr(api_tunnel, "_tunnel_service", stub, raising=False)

    data = _body(api_tunnel.tunnel_config_save(api_tunnel.TunnelConfigBody()))

    assert data["tunnel_was_running"] is True
    assert "当前隧道已断开" in data["message"]
    assert stub.stopped.wait(5)


def test_old_misleading_message_string_is_gone(monkeypatch, tmp_path):
    """全模块不应再有无条件的那句裸文案（防止后续改动把它挪回返回值）"""
    target = _patch_io(monkeypatch, tmp_path)
    source = Path(api_tunnel.__file__).read_text(encoding="utf-8")
    assert '"配置已保存，下次启动隧道时生效"' not in source

    monkeypatch.setattr(api_tunnel, "_tunnel_service", _StubService("stopped"), raising=False)
    idle = _body(api_tunnel.tunnel_config_save(api_tunnel.TunnelConfigBody()))
    time.sleep(0.05)
    assert idle["tunnel_was_running"] is False
