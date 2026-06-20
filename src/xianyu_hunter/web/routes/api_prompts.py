"""P1-8 Prompt 在线编辑器 API

支持在 Web 界面直接编辑和保存 AI 分析的 Prompt 文件，
无需改代码即可调优 AI 判断逻辑。

设计要点：
- Prompt 文件存放在 data/prompts/ 目录，纯文本便于版本管理
- 读取时带 fallback：文件不存在则返回代码内置默认值
- 保存时自动备份上一版（.bak），防止误操作
- 支持"重置为默认"功能
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field

from xianyu_hunter.container import Container
from xianyu_hunter.web.deps import get_container

router = APIRouter(prefix="/api/prompts", tags=["prompts"])

# Prompt 文件目录
_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "prompts"

# Prompt 元信息：key → (文件名, 描述, 代码内置默认值)
# 默认值从 api_ai.py 导入，保证"重置为默认"能恢复原始行为
from xianyu_hunter.web.routes.api_ai import _SYSTEM_PROMPT, _CONDITION_SYSTEM_PROMPT

_PROMPTS_META: dict[str, dict[str, Any]] = {
    "parse_task": {
        "filename": "parse_task.txt",
        "description": "自然语言解析为结构化任务字段（F-01 建任务）",
        "default": _SYSTEM_PROMPT,
    },
    "evaluate_condition": {
        "filename": "evaluate_condition.txt",
        "description": "AI 多模态成色评估（F-06 Vision 评估）",
        "default": _CONDITION_SYSTEM_PROMPT,
    },
}


class PromptUpdateBody(BaseModel):
    """更新 Prompt 请求体"""
    content: str = Field(..., min_length=1, max_length=20000, description="Prompt 内容")


def _ensure_prompts_dir() -> None:
    """确保 prompt 目录存在"""
    _PROMPTS_DIR.mkdir(parents=True, exist_ok=True)


def _prompt_path(key: str) -> Path:
    """获取指定 prompt 的文件路径"""
    meta = _PROMPTS_META.get(key)
    if not meta:
        raise HTTPException(status_code=404, detail=f"未知 Prompt: {key}")
    return _PROMPTS_DIR / meta["filename"]


def _read_prompt(key: str) -> str:
    """读取 prompt 内容：文件存在读文件，否则返回默认值"""
    path = _prompt_path(key)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return _PROMPTS_META[key]["default"]


def _write_prompt(key: str, content: str) -> None:
    """写入 prompt 内容，自动备份上一版"""
    _ensure_prompts_dir()
    path = _prompt_path(key)
    # 备份上一版（仅当文件存在且内容不同时）
    if path.exists() and path.read_text(encoding="utf-8") != content:
        bak_path = path.with_suffix(".txt.bak")
        shutil.copy2(path, bak_path)
    path.write_text(content, encoding="utf-8")


@router.get("")
def list_prompts() -> dict[str, Any]:
    """列出所有可编辑的 Prompt

    返回每个 prompt 的 key、描述、当前内容、是否自定义（vs 默认）
    """
    result: list[dict[str, Any]] = []
    for key, meta in _PROMPTS_META.items():
        path = _PROMPTS_DIR / meta["filename"]
        current = _read_prompt(key)
        is_custom = path.exists() and current != meta["default"]
        result.append({
            "key": key,
            "filename": meta["filename"],
            "description": meta["description"],
            "content": current,
            "is_custom": is_custom,
            "has_backup": path.with_suffix(".txt.bak").exists(),
        })
    return {"prompts": result}


@router.get("/{key}")
def get_prompt(key: str) -> dict[str, Any]:
    """获取单个 Prompt 内容"""
    if key not in _PROMPTS_META:
        raise HTTPException(status_code=404, detail=f"未知 Prompt: {key}")
    current = _read_prompt(key)
    path = _PROMPTS_DIR / _PROMPTS_META[key]["filename"]
    return {
        "key": key,
        "filename": _PROMPTS_META[key]["filename"],
        "description": _PROMPTS_META[key]["description"],
        "content": current,
        "is_custom": path.exists() and current != _PROMPTS_META[key]["default"],
        "has_backup": path.with_suffix(".txt.bak").exists(),
        "default": _PROMPTS_META[key]["default"],
    }


@router.put("/{key}")
def update_prompt(key: str, body: PromptUpdateBody) -> dict[str, Any]:
    """更新 Prompt 内容

    - 自动备份上一版到 .bak 文件
    - 下次 LLM 调用立即生效（无需重启）
    """
    if key not in _PROMPTS_META:
        raise HTTPException(status_code=404, detail=f"未知 Prompt: {key}")
    _write_prompt(key, body.content)
    # 重新加载到内存中的 prompt 变量
    _reload_prompt_to_memory(key, body.content)
    path = _PROMPTS_DIR / _PROMPTS_META[key]["filename"]
    return {
        "ok": True,
        "key": key,
        "is_custom": body.content != _PROMPTS_META[key]["default"],
        "has_backup": path.with_suffix(".txt.bak").exists(),
    }


@router.post("/{key}/reset")
def reset_prompt(key: str) -> dict[str, Any]:
    """重置 Prompt 为代码内置默认值

    - 删除自定义文件（保留 .bak 备份）
    - 恢复内存中的 prompt 变量
    """
    if key not in _PROMPTS_META:
        raise HTTPException(status_code=404, detail=f"未知 Prompt: {key}")
    path = _PROMPTS_DIR / _PROMPTS_META[key]["filename"]
    if path.exists():
        # 删除自定义文件（.bak 保留作为历史备份）
        path.unlink()
    default = _PROMPTS_META[key]["default"]
    _reload_prompt_to_memory(key, default)
    return {"ok": True, "key": key, "is_custom": False}


def _reload_prompt_to_memory(key: str, content: str) -> None:
    """将新 prompt 内容同步到 api_ai 模块的全局变量

    为什么需要这步：api_ai.py 中的 _call_llm / _call_llm_vision
    直接引用模块级 _SYSTEM_PROMPT / _CONDITION_SYSTEM_PROMPT 变量，
    修改文件后需同步内存变量才能立即生效（无需重启进程）。
    """
    from xianyu_hunter.web.routes import api_ai
    if key == "parse_task":
        api_ai._SYSTEM_PROMPT = content
    elif key == "evaluate_condition":
        api_ai._CONDITION_SYSTEM_PROMPT = content


def get_active_prompt(key: str) -> str:
    """供 api_ai.py 调用：获取当前生效的 prompt

    优先读文件（用户自定义），文件不存在则返回代码内置默认值。
    api_ai.py 的 _call_llm / _call_llm_vision 应改用此函数，
    而非直接引用模块级常量，以支持热更新。
    """
    return _read_prompt(key)
