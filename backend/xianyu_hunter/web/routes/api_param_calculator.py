"""参数计算器 API 路由

提供参数校验端点，供前端在任务创建/编辑、配置提交前调用。

端点设计：
- POST /api/param-calculator/validate-task: 校验任务参数
- POST /api/param-calculator/validate-config: 校验系统配置
- GET  /api/param-calculator/rules: 获取规则列表（前端展示用）
- POST /api/param-calculator/reload: 重新加载规则（管理员）

性能要求：单次校验响应 < 300ms（含网络往返）。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from xianyu_hunter.domain.param_calculator import Scenario
from xianyu_hunter.infra.yaml_config import get_config
from xianyu_hunter.web.services.param_validator import ParamValidatorService

router = APIRouter(prefix="/api/param-calculator", tags=["param-calculator"])

# 服务单例：与 Container 中其他服务对齐，避免每次请求重建
_service: ParamValidatorService | None = None


def _get_service() -> ParamValidatorService:
    """懒加载服务单例

    为什么不用 Depends：此服务无状态，单例即可；
    Depends 会在每次请求注入，但服务内部已缓存引擎实例，复用更高效。
    """
    global _service
    if _service is None:
        _service = ParamValidatorService()
    return _service


def _config_to_dict() -> dict[str, Any]:
    """将当前 AppConfig 转换为 dict 快照

    用于任务校验时的跨段交叉验证（如任务间隔 vs 全局 QPS）。
    为什么用 model_dump：Pydantic v2 推荐方式，保留嵌套结构。
    """
    try:
        config = get_config()
        return config.model_dump()
    except Exception:
        # 配置加载失败时不阻断校验：规则会回退到阈值默认值
        return {}


# ===== 请求/响应模型 =====


class ValidateTaskBody(BaseModel):
    """任务参数校验请求体

    fields 为扁平化的任务字段，前端从表单收集后传入。
    场景由 scenario 字段指定，默认为创建场景。
    """
    scenario: str = Field(
        default="task_create",
        description="校验场景：task_create / task_edit",
    )
    # 任务字段：前端按需传入，缺失字段由规则自行处理
    fields: dict[str, Any] = Field(
        default_factory=dict,
        description="任务参数，如 keyword/min_price/max_price/interval_seconds 等",
    )


class ValidateConfigBody(BaseModel):
    """系统配置校验请求体

    fields 为扁平化的配置字段，可包含跨段字段。
    前端在配置保存前的预览阶段调用此端点。
    """
    fields: dict[str, Any] = Field(
        default_factory=dict,
        description="配置参数，如 live_search_ttl/default_interval_seconds/page_size 等",
    )


# ===== 端点 =====


@router.post("/validate-task")
def validate_task(body: ValidateTaskBody) -> dict[str, Any]:
    """校验任务参数

    返回 ValidationReport 的序列化结果：
    - ok: 是否无阻断性问题
    - suggestions: 建议列表（按 severity 降序）
    - elapsed_ms: 引擎耗时（毫秒）
    """
    scenario = _parse_scenario(body.scenario, Scenario.TASK_CREATE)
    service = _get_service()
    # 传入全局配置快照，用于跨段校验（如任务间隔 vs 全局调度间隔）
    report = service.validate_task(
        task_fields=body.fields,
        scenario=scenario,
        global_config=_config_to_dict(),
    )
    return _report_to_dict(report)


@router.post("/validate-config")
def validate_config(body: ValidateConfigBody) -> dict[str, Any]:
    """校验系统配置参数

    用于配置提交前的预览确认环节。
    """
    service = _get_service()
    report = service.validate_config(body.fields, Scenario.CONFIG_UPDATE)
    return _report_to_dict(report)


@router.get("/rules")
def list_rules() -> dict[str, Any]:
    """获取所有规则元数据

    前端用于：
    1. 规则文档展示
    2. 配置界面阈值提示
    3. 调试与诊断
    """
    service = _get_service()
    return {"rules": service.list_rules()}


@router.post("/reload")
def reload_rules() -> dict[str, Any]:
    """重新加载规则配置（管理员）

    场景：param_rules.yaml 修改后，无需重启服务即可生效。
    """
    service = _get_service()
    service.reload()
    return {"ok": True, "message": "规则已重新加载"}


# ===== 工具函数 =====


def _parse_scenario(value: str, default: Scenario) -> Scenario:
    """解析场景字符串，无效时回退到默认值"""
    try:
        return Scenario(value)
    except ValueError:
        return default


def _report_to_dict(report: Any) -> dict[str, Any]:
    """将 ValidationReport 序列化为 JSON 响应

    为什么手写序列化：dataclass 不支持自动 JSON 序列化，
    且需要按 severity 排序输出。
    """
    return {
        "scenario": report.scenario.value,
        "ok": report.ok,
        "has_blocking": report.has_blocking,
        "warning_count": report.warning_count,
        "info_count": report.info_count,
        "elapsed_ms": report.elapsed_ms,
        "suggestions": [
            {
                "code": s.code,
                "severity": s.severity.value,
                "category": s.category.value,
                "message": s.message,
                "fix_hint": s.fix_hint,
                "affected_fields": s.affected_fields,
            }
            for s in report.suggestions
        ],
    }
