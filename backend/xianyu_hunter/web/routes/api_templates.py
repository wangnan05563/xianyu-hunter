"""F-11 模板市场 API — 预置模板 + 私有模板 CRUD

设计：
- 预置模板：随代码发布的 YAML 文件，只读不可删
- 私有模板：用户从现有任务"另存为"的 JSON 文件，可增删
- 存储：JSON 文件（轻量方案，无需数据库表）
"""
from __future__ import annotations

import json
import os
import time
import uuid

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/templates", tags=["templates"])

# 数据目录：与 preset_templates.yaml 同级
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
PRESET_FILE = os.path.normpath(os.path.join(DATA_DIR, 'preset_templates.yaml'))
USER_FILE = os.path.normpath(os.path.join(DATA_DIR, 'user_templates.json'))


class TemplateCreate(BaseModel):
    """用户另存为模板时的入参"""
    name: str = Field(..., min_length=1, max_length=80)
    keyword: str = Field(..., min_length=1, max_length=80)
    min_price: float | None = None
    max_price: float | None = None
    mode: str = "notify"
    icon: str = "\U0001F4CB"
    category: str = "其他"


def _load_presets() -> list[dict]:
    """从 YAML 加载预置模板列表"""
    if not os.path.exists(PRESET_FILE):
        return []
    with open(PRESET_FILE, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or []


def _load_user() -> list[dict]:
    """从 JSON 加载用户私有模板列表"""
    if not os.path.exists(USER_FILE):
        return []
    try:
        with open(USER_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save_user(templates: list[dict]) -> None:
    """持久化用户私有模板到 JSON 文件"""
    os.makedirs(os.path.dirname(USER_FILE), exist_ok=True)
    with open(USER_FILE, 'w', encoding='utf-8') as f:
        json.dump(templates, f, ensure_ascii=False, indent=2)


@router.get("")
def list_templates(category: str | None = None):
    """列出所有模板（预置 + 私有），支持 category 过滤"""
    presets = _load_presets()
    users = _load_user()
    all_templates = presets + users
    if category:
        all_templates = [t for t in all_templates if t.get('category') == category]
    return {"items": all_templates, "total": len(all_templates)}


@router.post("")
def save_template(body: TemplateCreate):
    """保存为私有模板（从现有任务另存）"""
    if body.min_price is not None and body.max_price is not None and body.min_price > body.max_price:
        raise HTTPException(status_code=400, detail="min_price 不能大于 max_price")
    users = _load_user()
    # 用 uuid 生成唯一 ID，避免序号冲突
    tid = f"usr_{uuid.uuid4().hex[:6]}"
    tpl = {
        "id": tid,
        "name": body.name,
        "keyword": body.keyword,
        "min_price": body.min_price,
        "max_price": body.max_price,
        "mode": body.mode,
        "icon": body.icon,
        "category": body.category,
        "is_preset": False,
        "created_at": time.strftime('%Y-%m-%dT%H:%M:%S'),
    }
    users.append(tpl)
    _save_user(users)
    return {"ok": True, "id": tid, "template": tpl}


@router.delete("/{template_id}")
def delete_template(template_id: str):
    """删除私有模板（预置模板不可删）"""
    if template_id.startswith("preset_"):
        raise HTTPException(status_code=400, detail="预置模板不可删除")
    users = _load_user()
    before = len(users)
    users = [t for t in users if t['id'] != template_id]
    if len(users) == before:
        raise HTTPException(status_code=404, detail="模板不存在")
    _save_user(users)
    return {"ok": True}
