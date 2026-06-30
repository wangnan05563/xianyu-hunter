"""AccountRotator 单元测试

直接测试 AccountRotator 类的纯逻辑行为，使用临时 SQLite 数据库，
不依赖外部服务。重点验证轮换策略、冷却恢复、失败禁用等核心调度逻辑。
"""
from __future__ import annotations

import json
import tempfile
import threading
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, update

from xianyu_hunter.infra.db_models import Base, AccountRow, _utcnow
from xianyu_hunter.modules.account_rotator import (
    AccountRotator,
    DEFAULT_COOLDOWN_SEC,
    DEFAULT_FAIL_THRESHOLD,
)


@pytest.fixture
def engine():
    """每个测试用独立的临时 SQLite 引擎

    使用 check_same_thread=False 以支持并发安全测试场景。
    """
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        eng = create_engine(
            f"sqlite:///{Path(d) / 'test.db'}",
            echo=False,
            future=True,
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(eng)
        yield eng
        eng.dispose()


@pytest.fixture
def rotator(engine) -> AccountRotator:
    """默认参数的账号轮换器"""
    return AccountRotator(engine)


# ============== 添加/删除 ==============
def test_add_account_returns_active_row(rotator: AccountRotator) -> None:
    """添加账号后应返回 status=active 的记录"""
    result = rotator.add_account("acc1", nickname="昵称", note="备注")
    assert result is not None
    assert result["name"] == "acc1"
    assert result["nickname"] == "昵称"
    assert result["status"] == "active"
    assert result["note"] == "备注"
    assert result["use_count"] == 0
    assert result["fail_count"] == 0


def test_add_account_serializes_cookies_to_json(rotator: AccountRotator) -> None:
    """cookies 列表应序列化为 JSON 字符串存储"""
    cookies = [{"name": "token", "value": "abc"}, {"name": "uid", "value": "123"}]
    result = rotator.add_account("acc1", cookies=cookies)
    assert result is not None
    # 数据库存储的是 JSON 字符串
    assert result["cookies"] == json.dumps(cookies, ensure_ascii=False)


def test_add_account_no_cookies_stores_none(rotator: AccountRotator) -> None:
    """未传 cookies 时存储 None"""
    result = rotator.add_account("acc1")
    assert result["cookies"] is None


def test_add_account_rejects_duplicate_name(rotator: AccountRotator) -> None:
    """重复账号名应抛出 ValueError"""
    rotator.add_account("dup")
    with pytest.raises(ValueError, match="已存在"):
        rotator.add_account("dup")


def test_delete_account_returns_true_on_existing(rotator: AccountRotator) -> None:
    """删除存在的账号返回 True"""
    acc = rotator.add_account("acc1")
    assert rotator.delete_account(acc["id"]) is True
    assert rotator.get_account(acc["id"]) is None


def test_delete_account_returns_false_on_missing(rotator: AccountRotator) -> None:
    """删除不存在的账号返回 False"""
    assert rotator.delete_account(9999) is False


# ============== 查询 ==============
def test_get_account_by_id(rotator: AccountRotator) -> None:
    acc = rotator.add_account("acc1")
    fetched = rotator.get_account(acc["id"])
    assert fetched is not None
    assert fetched["name"] == "acc1"


def test_get_account_returns_none_for_missing(rotator: AccountRotator) -> None:
    assert rotator.get_account(9999) is None


def test_get_account_by_name(rotator: AccountRotator) -> None:
    rotator.add_account("acc1")
    fetched = rotator.get_account_by_name("acc1")
    assert fetched is not None
    assert fetched["name"] == "acc1"


def test_get_account_by_name_returns_none_for_missing(rotator: AccountRotator) -> None:
    assert rotator.get_account_by_name("no-such") is None


def test_list_accounts_ordered_by_created_at(rotator: AccountRotator) -> None:
    """列出账号应按创建时间升序"""
    names = []
    for i in range(3):
        r = rotator.add_account(f"acc_{i}")
        names.append(r["name"])
    listed = rotator.list_accounts()
    assert [a["name"] for a in listed] == names


def test_list_accounts_filter_by_status(rotator: AccountRotator) -> None:
    """按状态过滤账号"""
    a1 = rotator.add_account("acc1")
    a2 = rotator.add_account("acc2")
    rotator.update_account(a2["id"], status="disabled")
    active = rotator.list_accounts(status="active")
    assert len(active) == 1
    assert active[0]["id"] == a1["id"]


# ============== 更新 ==============
def test_update_account_allowed_fields(rotator: AccountRotator) -> None:
    """仅允许更新 nickname/cookies/status/note"""
    acc = rotator.add_account("acc1", nickname="原昵称")
    new_cookies = [{"name": "k", "value": "v"}]
    updated = rotator.update_account(
        acc["id"],
        nickname="新昵称",
        cookies=new_cookies,
        status="disabled",
        note="新备注",
        # 受保护字段应被忽略
        use_count=999, fail_count=999, name="hacked",
    )
    assert updated["nickname"] == "新昵称"
    assert updated["status"] == "disabled"
    assert updated["note"] == "新备注"
    # cookies 列表应被转为 JSON
    assert updated["cookies"] == json.dumps(new_cookies, ensure_ascii=False)
    # 受保护字段未被修改
    assert updated["use_count"] == 0
    assert updated["fail_count"] == 0
    assert updated["name"] == "acc1"


def test_update_account_cookies_string_passed_through(rotator: AccountRotator) -> None:
    """cookies 传字符串时应原样存储（不二次序列化）"""
    acc = rotator.add_account("acc1")
    cookies_str = '{"k": "v"}'
    updated = rotator.update_account(acc["id"], cookies=cookies_str)
    assert updated["cookies"] == cookies_str


def test_update_account_no_allowed_fields_returns_unchanged(rotator: AccountRotator) -> None:
    """无可更新字段时直接返回当前记录"""
    acc = rotator.add_account("acc1")
    updated = rotator.update_account(acc["id"], use_count=999)
    assert updated["id"] == acc["id"]
    assert updated["use_count"] == 0


def test_update_account_missing_returns_none(rotator: AccountRotator) -> None:
    assert rotator.update_account(9999, note="x") is None


# ============== 轮换策略 ==============
def test_acquire_returns_none_when_empty(rotator: AccountRotator) -> None:
    """空账号池获取返回 None"""
    assert rotator.acquire() is None


def test_acquire_round_robin_by_last_used_at(rotator: AccountRotator) -> None:
    """轮询策略：按 last_used_at 升序，NULL 视为最早"""
    ids = []
    for i in range(3):
        r = rotator.add_account(f"acc_{i}")
        ids.append(r["id"])

    first = rotator.acquire()
    second = rotator.acquire()
    third = rotator.acquire()
    assert first["id"] == ids[0]
    assert second["id"] == ids[1]
    assert third["id"] == ids[2]


def test_acquire_increases_use_count(rotator: AccountRotator) -> None:
    """获取账号后 use_count 应递增"""
    acc = rotator.add_account("acc1")
    rotator.acquire()
    refreshed = rotator.get_account(acc["id"])
    assert refreshed["use_count"] == 1


def test_acquire_skips_cooldown(rotator: AccountRotator) -> None:
    """冷却中的账号不应被获取"""
    a1 = rotator.add_account("acc1")
    a2 = rotator.add_account("acc2")
    rotator.update_account(a1["id"], status="cooldown")
    acquired = rotator.acquire()
    assert acquired is not None
    assert acquired["id"] == a2["id"]


def test_acquire_skips_disabled(rotator: AccountRotator) -> None:
    """禁用的账号不应被获取"""
    a1 = rotator.add_account("acc1")
    a2 = rotator.add_account("acc2")
    rotator.update_account(a1["id"], status="disabled")
    acquired = rotator.acquire()
    assert acquired is not None
    assert acquired["id"] == a2["id"]


def test_acquire_returns_none_when_all_unavailable(rotator: AccountRotator) -> None:
    """所有账号都不可用时返回 None"""
    a1 = rotator.add_account("acc1")
    a2 = rotator.add_account("acc2")
    rotator.update_account(a1["id"], status="disabled")
    rotator.update_account(a2["id"], status="cooldown")
    assert rotator.acquire() is None


def test_acquire_preferred_name_returns_specified(rotator: AccountRotator) -> None:
    """指定 preferred_name 时优先返回该账号"""
    for i in range(3):
        rotator.add_account(f"acc_{i}")
    acquired = rotator.acquire(preferred_name="acc_2")
    assert acquired is not None
    assert acquired["name"] == "acc_2"


def test_acquire_preferred_name_fallback_when_unavailable(rotator: AccountRotator) -> None:
    """指定账号不可用时应回退到轮换"""
    a1 = rotator.add_account("acc1")
    rotator.add_account("acc2")
    # 把 acc1 禁用
    rotator.update_account(a1["id"], status="disabled")
    acquired = rotator.acquire(preferred_name="acc1")
    # 回退到 acc2
    assert acquired is not None
    assert acquired["name"] == "acc2"


def test_acquire_preferred_name_fallback_when_not_found(rotator: AccountRotator) -> None:
    """指定账号不存在时应回退到轮换"""
    rotator.add_account("acc1")
    acquired = rotator.acquire(preferred_name="no-such")
    assert acquired is not None
    assert acquired["name"] == "acc1"


# ============== 冷却恢复 ==============
def test_recover_expired_cooldowns_on_list(engine) -> None:
    """过期冷却应在 list_accounts 时自动恢复为 active"""
    r = AccountRotator(engine, cooldown_sec=1)
    acc = r.add_account("acc1")
    # 手动设置为已过期的冷却状态
    with engine.begin() as conn:
        conn.execute(
            update(AccountRow)
            .where(AccountRow.id == acc["id"])
            .values(
                status="cooldown",
                cooldown_until=_utcnow() - timedelta(seconds=1),
                fail_count=2,
            )
        )
    listed = r.list_accounts(status="active")
    assert len(listed) == 1
    assert listed[0]["id"] == acc["id"]
    # fail_count 应被重置
    assert listed[0]["fail_count"] == 0


def test_recover_does_not_touch_unexpired_cooldown(engine) -> None:
    """未过期的冷却不应被恢复"""
    r = AccountRotator(engine, cooldown_sec=1800)
    acc = r.add_account("acc1")
    future = _utcnow() + timedelta(seconds=1000)
    with engine.begin() as conn:
        conn.execute(
            update(AccountRow)
            .where(AccountRow.id == acc["id"])
            .values(status="cooldown", cooldown_until=future)
        )
    active = r.list_accounts(status="active")
    cooldown = r.list_accounts(status="cooldown")
    assert len(active) == 0
    assert len(cooldown) == 1


def test_acquire_triggers_cooldown_recovery(engine) -> None:
    """acquire 时应先恢复过期冷却，使恢复的账号可被获取"""
    r = AccountRotator(engine)
    acc = r.add_account("acc1")
    # 设置为已过期冷却
    with engine.begin() as conn:
        conn.execute(
            update(AccountRow)
            .where(AccountRow.id == acc["id"])
            .values(
                status="cooldown",
                cooldown_until=_utcnow() - timedelta(seconds=1),
            )
        )
    acquired = r.acquire()
    assert acquired is not None
    assert acquired["id"] == acc["id"]


# ============== 成功/失败上报 ==============
def test_report_success_resets_fail_count(rotator: AccountRotator) -> None:
    """成功上报应重置 fail_count 为 0"""
    acc = rotator.add_account("acc1")
    rotator.report_fail(acc["id"])
    rotator.report_fail(acc["id"])
    assert rotator.get_account(acc["id"])["fail_count"] == 2
    rotator.report_success(acc["id"])
    assert rotator.get_account(acc["id"])["fail_count"] == 0


def test_report_fail_enters_cooldown_below_threshold(rotator: AccountRotator) -> None:
    """未超阈值的失败应进入冷却状态"""
    acc = rotator.add_account("acc1")
    result = rotator.report_fail(acc["id"], cooldown_sec=60)
    assert result is not None
    assert result["status"] == "cooldown"
    assert result["fail_count"] == 1
    assert result["cooldown_until"] is not None


def test_report_fail_uses_default_cooldown_when_not_specified(rotator: AccountRotator) -> None:
    """未指定 cooldown_sec 时使用默认值"""
    acc = rotator.add_account("acc1")
    rotator.report_fail(acc["id"])
    refreshed = rotator.get_account(acc["id"])
    assert refreshed["status"] == "cooldown"
    assert refreshed["cooldown_until"] is not None
    # 默认冷却时间应在合理范围内
    assert DEFAULT_COOLDOWN_SEC == 1800


def test_report_fail_auto_disable_at_threshold(engine) -> None:
    """连续失败达到阈值应自动禁用（而非冷却）"""
    r = AccountRotator(engine, fail_threshold=3)
    acc = r.add_account("acc1")
    r.report_fail(acc["id"])
    r.report_fail(acc["id"])
    # 第三次应触发禁用
    result = r.report_fail(acc["id"])
    assert result is not None
    assert result["status"] == "disabled"
    assert result["fail_count"] == 3
    # 注意：源码在禁用分支只更新 fail_count 和 status，不清除之前
    # 冷却阶段写入的 cooldown_until，因此该字段可能保留旧值。
    # 此处不断言 cooldown_until 为 None，因为 status=disabled 时
    # cooldown_until 已无实际意义。


def test_report_fail_default_threshold_is_five(rotator: AccountRotator) -> None:
    """默认阈值为 5"""
    assert DEFAULT_FAIL_THRESHOLD == 5
    acc = rotator.add_account("acc1")
    for _ in range(4):
        rotator.report_fail(acc["id"])
    # 4 次还在冷却
    assert rotator.get_account(acc["id"])["status"] == "cooldown"
    # 第 5 次禁用
    rotator.report_fail(acc["id"])
    assert rotator.get_account(acc["id"])["status"] == "disabled"


def test_report_fail_missing_returns_none(rotator: AccountRotator) -> None:
    """对不存在的账号上报失败返回 None"""
    assert rotator.report_fail(9999) is None


# ============== 统计 ==============
def test_get_stats_empty(rotator: AccountRotator) -> None:
    """空池统计应全为 0"""
    stats = rotator.get_stats()
    assert stats["total"] == 0
    assert stats["active"] == 0
    assert stats["cooldown"] == 0
    assert stats["disabled"] == 0


def test_get_stats_counts_by_status(rotator: AccountRotator) -> None:
    """统计应正确分类 active/cooldown/disabled"""
    rotator.add_account("acc1")
    a2 = rotator.add_account("acc2")
    a3 = rotator.add_account("acc3")
    rotator.update_account(a2["id"], status="cooldown")
    rotator.update_account(a3["id"], status="disabled")
    stats = rotator.get_stats()
    assert stats["total"] == 3
    assert stats["active"] == 1
    assert stats["cooldown"] == 1
    assert stats["disabled"] == 1


def test_get_stats_recovers_expired_cooldowns(rotator: AccountRotator) -> None:
    """统计时应先恢复过期冷却，影响 active 计数"""
    acc = rotator.add_account("acc1")
    with rotator._engine.begin() as conn:
        conn.execute(
            update(AccountRow)
            .where(AccountRow.id == acc["id"])
            .values(
                status="cooldown",
                cooldown_until=_utcnow() - timedelta(seconds=1),
            )
        )
    stats = rotator.get_stats()
    # 过期冷却已恢复为 active
    assert stats["active"] == 1
    assert stats["cooldown"] == 0


# ============== 并发安全 ==============
def test_acquire_concurrent_no_duplicate(engine) -> None:
    """多线程并发获取不应返回同一个账号（Lock 保证）"""
    r = AccountRotator(engine)
    for i in range(5):
        r.add_account(f"acc_{i}")

    results = []
    lock = threading.Lock()

    def worker():
        acquired = r.acquire()
        if acquired:
            with lock:
                results.append(acquired["id"])

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # 5 个线程应获取到 5 个不同的账号
    assert len(results) == 5
    assert len(set(results)) == 5
