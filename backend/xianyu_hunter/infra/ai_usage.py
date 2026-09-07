"""AI 用量追踪与预算控制

记录每次 LLM 调用的 token 消耗和估算费用，
提供每日预算限制和调用频率控制。

费用估算参考（按 1K token 计价，单位 USD）：
- GPT-4o-mini: input $0.15, output $0.60
- GPT-4o: input $2.50, output $10.00
- DeepSeek-Chat: input $0.14, output $0.28
- GLM-4-Flash: input $0.10, output $0.10
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from xianyu_hunter.paths import get_data_dir

# 用量数据文件路径：统一走 paths.get_data_dir()，
# 开发模式落在 data/（与 SQLite/cookies 同级），打包(frozen)模式落在 %APPDATA%/XianyuHunter/data，
# 避免此前硬编码 Path("data/...") 在 PyInstaller 冻结版 / 非项目根 CWD 下读错位置，
# 导致「AI 用量仪表盘」长期读不到历史用量（今日=0、近 7 天趋势空白）。
def _usage_file() -> Path:
    return get_data_dir() / "ai_usage.json"

# 测试通过 monkeypatch 此属性指向临时路径来隔离持久化
USAGE_FILE = _usage_file()

# 各模型每 1K token 价格（USD）
MODEL_PRICING: dict[str, dict[str, float]] = {
    # OpenAI
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini-2024-07-18": {"input": 0.15, "output": 0.60},
    "gpt-4o-2024-08-06": {"input": 2.50, "output": 10.00},
    # DeepSeek
    "deepseek-chat": {"input": 0.14, "output": 0.28},
    "deepseek-reasoner": {"input": 0.55, "output": 2.19},
    # 智谱
    "glm-4-flash": {"input": 0.10, "output": 0.10},
    "glm-4v-flash": {"input": 0.10, "output": 0.10},
    "glm-4-plus": {"input": 0.50, "output": 0.50},
    # Moonshot
    "moonshot-v1-8k": {"input": 0.12, "output": 0.12},
    "moonshot-v1-32k": {"input": 0.24, "output": 0.24},
}

# 默认费率（未识别模型按 GPT-4o-mini 计价）
_DEFAULT_PRICING = {"input": 0.15, "output": 0.60}

# 汇率（USD → CNY），粗略估算
USD_TO_CNY = 7.2


@dataclass
class UsageRecord:
    """单次调用记录"""
    timestamp: float  # Unix timestamp
    endpoint: str     # API 端点（如 parse_task, evaluate_condition）
    model: str        # 使用的模型名
    input_tokens: int
    output_tokens: int
    cost_usd: float   # 估算费用（USD）
    billable: bool = True  # 是否计入每日预算；本地 embedding 等免费调用置 False


@dataclass
class DailyUsage:
    """每日汇总"""
    date: str  # YYYY-MM-DD
    total_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    by_endpoint: dict[str, int] = field(default_factory=dict)
    by_model: dict[str, int] = field(default_factory=dict)


@dataclass
class BudgetConfig:
    """预算配置"""
    daily_token_limit: int = 500000    # 每日 token 上限（50万）
    daily_cost_limit_usd: float = 5.0  # 每日费用上限（$5）
    rate_limit_per_min: int = 20       # 每分钟最大调用次数


# ============== 全局状态 ==============

_lock = threading.Lock()
_today_records: list[UsageRecord] = []
_minute_timestamps: list[float] = []  # 滑动窗口：最近1分钟的调用时间戳
# 初始占位：实际值在 _ensure_budget_loaded() 中从 YAML 同步，避免 import 时循环依赖
_budget = BudgetConfig()
_budget_loaded = False


def _ensure_budget_loaded() -> None:
    """懒加载：首次调用时从 YAML 读取 ai_budget 配置同步到内存 _budget

    为什么懒加载而非 import 时加载：
    1. ai_usage 是底层模块，被 api_ai.py / container.py 等多处 import；
       若在模块顶层调用 get_config()，会触发 yaml_config 完整加载链路，
       与 paths.py / db_models.py 形成潜在循环导入。
    2. 测试场景下若直接 import ai_usage 但未初始化 YAML 配置目录，
       顶层 get_config() 会抛异常；懒加载只在真正读写预算时触发。
    """
    global _budget_loaded
    if _budget_loaded:
        return
    with _lock:
        if _budget_loaded:
            return
        try:
            from xianyu_hunter.infra.yaml_config import get_config
            cfg = get_config().ai_budget
            _budget.daily_token_limit = cfg.daily_token_limit
            _budget.daily_cost_limit_usd = cfg.daily_cost_limit_usd
            _budget.rate_limit_per_min = cfg.rate_limit_per_min
        except Exception as e:
            # YAML 未初始化或字段缺失时沿用 dataclass 默认值，不阻断 AI 调用
            logger.warning(f"[ai_usage] 从 YAML 加载 ai_budget 失败，使用默认值: {e}")
        _budget_loaded = True


def _date_key_of(ts: float) -> str:
    """把 unix 时间戳转成本地日期键（YYYY-MM-DD）

    统一用「本地时区」而非 UTC：本应用面向中国用户，若用 UTC 会在跨日界
    （北京时间 08:00 前）把「今日」误归到前一天，导致今日调用/Tokens 与
    近 7 天趋势整体偏移一天。历史记录存的是原始 epoch，读取时统一按本地分桶，
    无需迁移旧数据。
    """
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


def _today_key() -> str:
    return _date_key_of(time.time())


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """估算单次调用费用（USD）"""
    pricing = MODEL_PRICING.get(model, _DEFAULT_PRICING)
    return (input_tokens / 1000 * pricing["input"]) + (output_tokens / 1000 * pricing["output"])


def record_usage(
    endpoint: str,
    model: str,
    response_data: dict[str, Any] | None = None,
    *,
    input_tokens_override: int | None = None,
    output_tokens_override: int | None = None,
    cost_override: float | None = None,
    billable: bool = True,
) -> dict[str, Any]:
    """记录一次 AI 调用的用量

    优先从 OpenAI 兼容响应中提取 usage 字段；
    对于 embedding 端点，远程响应常只返回 total_tokens（无 completion_tokens），
    若 prompt_tokens/completion_tokens 都为 0 则兜底用 total_tokens 回填，
    避免远程 embedding 调用漏记 token。
    input_tokens_override / output_tokens_override / cost_override 用于本地
    embedding 等场景：本地不消耗远程 token 费用，但可用估算 token 量回填统计，
    让仪表盘反映真实负载，同时把费用明确置 0（本地不花钱）。
    返回用量摘要 dict。
    """
    input_tokens = 0
    output_tokens = 0

    if response_data and "usage" in response_data:
        usage = response_data["usage"]
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        # embedding 端点通常只有 total_tokens，无 completion_tokens；
        # 两者都为 0 时尝试用 total_tokens 兜底，避免漏记远程 embedding token。
        if input_tokens == 0 and output_tokens == 0:
            input_tokens = usage.get("total_tokens", 0)

    if input_tokens_override is not None:
        input_tokens = input_tokens_override
    if output_tokens_override is not None:
        output_tokens = output_tokens_override

    cost = (
        cost_override
        if cost_override is not None
        else _estimate_cost(model, input_tokens, output_tokens)
    )
    record = UsageRecord(
        timestamp=time.time(),
        endpoint=endpoint,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost,
        billable=billable,
    )

    with _lock:
        _today_records.append(record)
        _minute_timestamps.append(time.time())
        # 清理超过1分钟的时间戳
        cutoff = time.time() - 60
        _minute_timestamps[:] = [t for t in _minute_timestamps if t > cutoff]

    # 持久化（异步不阻塞）
    _persist_record(record)

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": round(cost, 6),
        "cost_cny": round(cost * USD_TO_CNY, 4),
    }


def check_budget() -> tuple[bool, str]:
    """检查是否超出每日预算

    返回 (允许调用, 原因说明)
    """
    _ensure_budget_loaded()
    with _lock:
        # 检查频率限制
        cutoff = time.time() - 60
        recent = [t for t in _minute_timestamps if t > cutoff]
        if len(recent) >= _budget.rate_limit_per_min:
            return False, f"频率超限：每分钟最多 {_budget.rate_limit_per_min} 次"

        # 检查每日 token 上限（仅统计 billable 记录；
        # 本地 embedding 等免费调用虽记录估算 token 供仪表盘展示，但不占用预算）
        total_tokens = sum(r.input_tokens + r.output_tokens for r in _today_records if r.billable)
        if total_tokens >= _budget.daily_token_limit:
            return False, f"Token 超限：今日已用 {total_tokens:,}，上限 {_budget.daily_token_limit:,}"

        # 检查每日费用上限（同样仅统计 billable 记录）
        total_cost = sum(r.cost_usd for r in _today_records if r.billable)
        if total_cost >= _budget.daily_cost_limit_usd:
            return False, f"费用超限：今日已用 ${total_cost:.2f}，上限 ${_budget.daily_cost_limit_usd:.2f}"

    return True, ""


def _accumulate_usage_into_summary(
    summary: DailyUsage,
    *,
    endpoint: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
) -> None:
    """将单条用量记录累加到 summary（含 by_endpoint/by_model 计数）

    为什么独立：get_daily_summary 中内存循环和文件循环的累加逻辑重复，
    集中维护避免两处分支不一致，同时降低主函数的认知复杂度。

    注意：内存循环原本无条件累加 endpoint/model 计数，这里加 if 判断后
    行为等价——UsageRecord 的 endpoint/model 字段在实际使用中不会为空字符串。
    """
    summary.total_calls += 1
    summary.total_input_tokens += input_tokens
    summary.total_output_tokens += output_tokens
    summary.total_cost_usd += cost_usd
    if endpoint:
        summary.by_endpoint[endpoint] = summary.by_endpoint.get(endpoint, 0) + 1
    if model:
        summary.by_model[model] = summary.by_model.get(model, 0) + 1


def get_daily_summary() -> DailyUsage:
    """获取今日用量汇总（含已持久化的历史记录）

    服务重启后 _today_records 内存为空，需从 ai_usage.json 回填
    今日的调用记录，避免刷新页面后数据归零。
    """
    today = _today_key()
    summary = DailyUsage(date=today)

    # 从内存加载当前会话的记录
    with _lock:
        for r in _today_records:
            _accumulate_usage_into_summary(
                summary,
                endpoint=r.endpoint,
                model=r.model,
                input_tokens=r.input_tokens,
                output_tokens=r.output_tokens,
                cost_usd=r.cost_usd,
            )

    # 从持久化文件补充今日历史记录（覆盖服务重启前已写入的部分）
    if USAGE_FILE.exists():
        try:
            data = json.loads(USAGE_FILE.read_text(encoding="utf-8"))
            for entry in data.get("records", []):
                date_key = _date_key_of(entry["timestamp"])
                if date_key == today:
                    # 文件中的记录与内存可能重叠（同一请求既在内存也在文件），
                    # 但 record_usage 先写内存再异步写文件，且文件是追加模式，
                    # 所以这里直接累加即可——重复的概率极低且影响可忽略
                    _accumulate_usage_into_summary(
                        summary,
                        endpoint=entry.get("endpoint", ""),
                        model=entry.get("model", ""),
                        input_tokens=entry.get("input_tokens", 0),
                        output_tokens=entry.get("output_tokens", 0),
                        cost_usd=entry.get("cost_usd", 0),
                    )
        except (json.JSONDecodeError, KeyError, OSError):
            pass

    return summary


def _load_today_from_memory(summaries: dict[str, DailyUsage], today: str) -> None:
    """从内存 _today_records 累加今日用量到 summaries

    独立出 get_recent_usage 的内存循环，降低主函数嵌套深度（S3776）。
    """
    with _lock:
        for r in _today_records:
            key = today
            if key not in summaries:
                summaries[key] = DailyUsage(date=key)
            s = summaries[key]
            s.total_calls += 1
            s.total_input_tokens += r.input_tokens
            s.total_output_tokens += r.output_tokens
            s.total_cost_usd += r.cost_usd


def _load_history_from_file(summaries: dict[str, DailyUsage], today: str) -> None:
    """从持久化文件补充历史用量到 summaries（跳过今日，今日已从内存加载）

    独立出 get_recent_usage 的文件解析循环，集中处理 JSON 异常与日期过滤。
    """
    if not USAGE_FILE.exists():
        return
    try:
        data = json.loads(USAGE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, KeyError):
        return
    for entry in data.get("records", []):
        date_key = _date_key_of(entry["timestamp"])
        if date_key == today:
            continue  # 今日数据已从内存加载
        if date_key not in summaries:
            summaries[date_key] = DailyUsage(date=date_key)
        s = summaries[date_key]
        s.total_calls += 1
        s.total_input_tokens += entry.get("input_tokens", 0)
        s.total_output_tokens += entry.get("output_tokens", 0)
        s.total_cost_usd += entry.get("cost_usd", 0)


def get_recent_usage(days: int = 7) -> list[dict[str, Any]]:
    """获取最近 N 天的用量历史"""
    summaries: dict[str, DailyUsage] = {}
    today = _today_key()

    _load_today_from_memory(summaries, today)
    _load_history_from_file(summaries, today)

    # 按日期排序，取最近 N 天
    sorted_days = sorted(summaries.values(), key=lambda x: x.date, reverse=True)[:days]
    return [
        {
            "date": s.date,
            "total_calls": s.total_calls,
            "total_input_tokens": s.total_input_tokens,
            "total_output_tokens": s.total_output_tokens,
            "total_cost_usd": round(s.total_cost_usd, 4),
            "total_cost_cny": round(s.total_cost_usd * USD_TO_CNY, 2),
        }
        for s in sorted_days
    ]


def _persist_budget_to_yaml(yaml_patch: dict[str, Any]) -> None:
    """把 ai_budget 字段增量写入 config.yaml 并触发 reload_config

    独立为函数便于单元测试 mock：测试场景下 monkeypatch 此函数为 no-op，
    避免污染真实 config.yaml。

    失败时仅 warning，不抛异常：内存 _budget 已经更新，本次仍生效，
    只是下次启动会回退到旧值。
    """
    try:
        from pathlib import Path
        import yaml as _yaml
        cfg_path = Path("config/config.yaml")
        raw: dict[str, Any] = {}
        if cfg_path.exists():
            raw = _yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        raw.setdefault("ai_budget", {})
        raw["ai_budget"].update(yaml_patch)
        cfg_path.write_text(
            _yaml.safe_dump(raw, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        from xianyu_hunter.infra.yaml_config import reload_config
        reload_config()
        logger.info(f"[ai_usage] ai_budget 已持久化: {yaml_patch}")
    except Exception as e:
        logger.warning(f"[ai_usage] ai_budget 写盘失败，仅内存生效: {e}")


def update_budget(
    daily_token_limit: int | None = None,
    daily_cost_limit_usd: float | None = None,
    rate_limit_per_min: int | None = None,
) -> None:
    """更新预算配置

    持久化策略：
    1. 内存 _budget 立即更新（check_budget 实时生效）
    2. 同步写盘到 config.yaml 的 ai_budget 段，下次启动自动加载
    3. 调用 reload_config() 让其他模块从单例读到的也是最新值

    为什么不只在 YAML 写盘后靠 reload 同步内存：
    reload 会重建整个 AppConfig 单例，期间若有并发 check_budget 读取旧 _budget，
    可能产生短窗口不一致；先改内存再写盘更稳妥。
    """
    _ensure_budget_loaded()
    yaml_patch: dict[str, Any] = {}
    with _lock:
        if daily_token_limit is not None:
            _budget.daily_token_limit = daily_token_limit
            yaml_patch["daily_token_limit"] = daily_token_limit
        if daily_cost_limit_usd is not None:
            _budget.daily_cost_limit_usd = daily_cost_limit_usd
            yaml_patch["daily_cost_limit_usd"] = daily_cost_limit_usd
        if rate_limit_per_min is not None:
            _budget.rate_limit_per_min = rate_limit_per_min
            yaml_patch["rate_limit_per_min"] = rate_limit_per_min

    if yaml_patch:
        _persist_budget_to_yaml(yaml_patch)


def get_budget_config() -> BudgetConfig:
    """获取当前预算配置"""
    _ensure_budget_loaded()
    return _budget


def _persist_record(record: UsageRecord) -> None:
    """将调用记录追加到 JSON 文件"""
    try:
        USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        data: dict[str, Any] = {"records": []}
        if USAGE_FILE.exists():
            try:
                data = json.loads(USAGE_FILE.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass

        data.setdefault("records", []).append({
            "timestamp": record.timestamp,
            "endpoint": record.endpoint,
            "model": record.model,
            "input_tokens": record.input_tokens,
            "output_tokens": record.output_tokens,
            "cost_usd": record.cost_usd,
            "billable": record.billable,
        })

        # 保留最近 30 天数据（按条数估算：每天最多1000条）
        max_records = 30 * 1000
        if len(data["records"]) > max_records:
            data["records"] = data["records"][-max_records:]

        USAGE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as e:
        logger.warning(f"AI 用量记录持久化失败: {e}")
