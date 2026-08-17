"""P1-4 AI 深度多模态分析增强 API

在 F-06 基础上增加 4 项深度分析能力：
1. 商品图片盗图检测（图片哈希比对 + 来源域名分析）
2. 图片划痕/损坏识别（LLM Vision 物理损坏检测）
3. 描述与图片一致性校验（LLM 跨模态匹配）
4. 卖家文案模板化检测（贩子识别，基于卖家多商品描述相似度）

端点：
- POST /api/ai/deep-analyze          单商品深度分析
- POST /api/ai/seller-template-check 卖家文案模板化检测
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger
from pydantic import BaseModel, Field

from xianyu_hunter.config import get_settings
from xianyu_hunter.container import Container
from xianyu_hunter.infra.ai_usage import check_budget, record_usage
from xianyu_hunter.web.deps import get_container
from xianyu_hunter.web.routes.api_ai import _check_ai_enabled, _is_vision_capable

router = APIRouter(prefix="/api/ai", tags=["ai-deep"])

# 深度分析超时：多图 Vision 推理较慢
DEEP_ANALYZE_TIMEOUT_SEC = 90.0
# S1192: 提取重复的规则模拟前缀为常量
_RULE_DETAIL_PREFIX = "规则模拟：基于"


# ============== 请求模型 ==============
class DeepAnalyzeRequest(BaseModel):
    """P1-4 深度分析请求"""
    item_id: str = Field(..., description="闲鱼商品 ID")
    checks: list[str] = Field(
        default=["stolen_image", "damage", "consistency", "template"],
        description="要执行的检查项：stolen_image/damage/consistency/template",
    )


class SellerTemplateCheckRequest(BaseModel):
    """卖家文案模板化检测请求"""
    seller_id: str = Field(..., description="卖家 ID")
    sample_size: int = Field(default=20, ge=3, le=50, description="采样商品数")


# ============== 深度分析 Prompt ==============
_DEEP_ANALYZE_PROMPT = """你是一个闲鱼二手商品深度鉴伪专家。
用户会提供商品的标题、描述、价格和图片。请执行以下深度分析：

## 分析维度

### 1. 盗图检测（stolen_image）
- 图片是否含水印（其他平台 logo、店铺名）
- 图片风格是否一致（不同图来源混杂可能是盗图）
- 图片清晰度/分辨率是否差异过大

### 2. 物理损坏识别（damage）
- 图片中是否有可见划痕、磕碰、裂纹、变色
- 屏幕是否有坏点、亮点、色差
- 接口/按键是否有磨损痕迹

### 3. 描述与图片一致性（consistency）
- 标题声称的型号与图片展示是否一致
- 描述的成色与图片实际成色是否一致
- 描述的配件与图片展示是否一致

### 4. 文案模板化检测（template）
- 描述是否像模板化文案（"99新仅拆封"等套话堆砌）
- 是否缺少个性化细节（具体使用时长、购买凭证等）
- 是否存在"贩子特征"（多商品共用文案模板）

请输出以下 JSON（不要 Markdown 代码块包裹，不要解释）：
{
  "stolen_image": {
    "score": number,           // 1-10，10=原创图片，1=明显盗图
    "risk_level": "low"|"medium"|"high",
    "signals": string[],       // 检测到的风险信号
    "detail": string           // 详细分析（≤150字）
  },
  "damage": {
    "score": number,           // 1-10，10=无损坏，1=严重损坏
    "risk_level": "low"|"medium"|"high",
    "damages": string[],       // 检测到的损坏类型
    "detail": string
  },
  "consistency": {
    "score": number,           // 1-10，10=完全一致，1=严重不符
    "risk_level": "low"|"medium"|"high",
    "inconsistencies": string[],
    "detail": string
  },
  "template": {
    "score": number,           // 1-10，10=个性化文案，1=明显模板
    "risk_level": "low"|"medium"|"high",
    "signals": string[],
    "detail": string
  },
  "overall_verdict": "recommend"|"caution"|"reject",
  "overall_score": number,     // 1-10 综合评分
  "summary": string            // 一句话总结（≤50字）
}

判定规则：
- overall_verdict="recommend"：所有维度 score >= 7 且无 high 风险
- overall_verdict="caution"：存在 medium 风险或任一维度 score 4-6
- overall_verdict="reject"：存在 high 风险或任一维度 score <= 3
- 如果图片无法加载，仅基于文字分析，对应维度 risk_level="medium"

只输出 JSON，不要其它任何内容。
"""


# ============== LLM 调用 ==============
def _build_deep_system_prompt(vision_capable: bool) -> str:
    """构建深度分析 system prompt

    纯文本模型时追加"无图评估"说明，避免 LLM 强行编造"我看了图片"
    导致盗图/损坏/一致性维度失真。
    """
    system_prompt = _DEEP_ANALYZE_PROMPT
    if not vision_capable:
        system_prompt = (
            system_prompt
            + "\n\n【特别说明】当前模型不支持图片分析，请仅基于标题、描述、价格和"
              "卖家其他商品描述样本进行评估。盗图/损坏/一致性维度因无图无法判断，"
              "对应 score 取默认值 5、risk_level='medium'，signals 中加入'无图片参考'。"
        )
    return system_prompt


def _build_deep_text_content(
    title: str, description: str, price: float, seller_items: list[dict[str, Any]] | None
) -> str:
    """构建深度分析文本内容，注入卖家其他商品描述样本用于模板化检测对比"""
    text_parts = [
        f"商品标题：{title}",
        f"商品描述：{description}",
        f"商品价格：¥{price}",
    ]
    # 卖家其他商品文案样本（用于模板化检测）
    if seller_items:
        sample_descs = [s.get("description", "")[:100] for s in seller_items[:5] if s.get("description")]
        if sample_descs:
            text_parts.append("该卖家其他商品描述样本：")
            for i, d in enumerate(sample_descs, 1):
                text_parts.append(f"  样本{i}：{d}")
    return "\n".join(text_parts)


def _build_deep_user_content(
    text_content: str, image_urls: list[str], vision_capable: bool
) -> list[dict[str, Any]]:
    """构建 user_content 列表：文本 + 最多 6 张图片

    闲鱼图片 URL 常为协议相对路径（//img.alicdn.com/...），LLM 端无法解析，
    需补全为 https://，否则会被 vision 服务报 400 失败并降级规则模拟。
    纯文本模型直接跳过图片，避免 400 + 用量浪费。
    """
    user_content: list[dict[str, Any]] = [
        {"type": "text", "text": text_content},
    ]
    for img_url in image_urls[:6]:
        if not vision_capable:
            break
        normalized = img_url
        if normalized.startswith("//"):
            normalized = "https:" + normalized
        user_content.append({
            "type": "image_url",
            "image_url": {"url": normalized},
        })
    return user_content


async def _call_llm_deep_analyze(
    title: str,
    description: str,
    price: float,
    image_urls: list[str],
    seller_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """调 LLM Vision 执行深度多模态分析

    seller_items 用于文案模板化检测（提供卖家其他商品的描述作为对比样本）。
    """
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("未配置 OPENAI_API_KEY，无法使用 AI 深度分析")

    # 预算检查
    allowed, reason = check_budget()
    if not allowed:
        raise RuntimeError(f"AI 调用受限：{reason}，已自动降级到规则分析")

    url = settings.openai_base_url.rstrip("/") + "/chat/completions"

    # 检测当前 vision_model 是否具备多模态能力（统一在 api_ai._is_vision_capable
    # 维护关键字白名单，避免模型升级时散落修改）。
    vision_capable = _is_vision_capable(settings.openai_vision_model)

    system_prompt = _build_deep_system_prompt(vision_capable)
    text_content = _build_deep_text_content(title, description, price, seller_items)
    user_content = _build_deep_user_content(text_content, image_urls, vision_capable)

    payload = {
        "model": settings.openai_vision_model,  # 可配置：Vision 模型
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.2,
        "max_tokens": 1500,
    }
    headers = {
        "Authorization": "Bearer " + settings.openai_api_key,
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=DEEP_ANALYZE_TIMEOUT_SEC) as client:
            r = await client.post(url, json=payload, headers=headers)
    except httpx.TimeoutException:
        raise RuntimeError("AI 深度分析超时（>90s），多图分析较慢请稍后重试") from None
    except httpx.HTTPError as e:
        raise RuntimeError("AI 深度分析网络错误: " + str(e)) from None
    if r.status_code != 200:
        snippet = r.text[:300]
        raise RuntimeError(f"AI 服务返回 {r.status_code}: {snippet}")

    # 记录用量
    try:
        resp_data = r.json()
        record_usage("deep_analyze", settings.openai_vision_model, resp_data)
    except Exception:
        record_usage("deep_analyze", settings.openai_vision_model)

    return _parse_llm_response(r)


def _parse_llm_response(r: httpx.Response) -> dict[str, Any]:
    """从 LLM 响应中提取 JSON dict（与 api_ai.py 逻辑一致）"""
    try:
        data = r.json()
        content = data["choices"][0]["message"]["content"]
    except (KeyError, ValueError, IndexError) as e:
        raise RuntimeError(f"AI 返回结构异常: {e}") from None
    content = content.strip()
    if content.startswith("```"):
        # S5850: 保留外层分组让 | 优先级明确；S6395: 移除各分支内部多余分组
        content = re.sub(r"(?:^```(?:json)?\s*|\s*```$)", "", content, flags=re.MULTILINE).strip()  # NOSONAR
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        raise RuntimeError(f"AI 返回非 JSON: {content[:200]}") from None
    if not isinstance(parsed, dict):
        raise RuntimeError("AI 返回非 dict 结构")
    return parsed


# ============== 规则模拟（fallback） ==============
def _rule_risk_level(score: int) -> str:
    """规则模拟专用：将评分映射为 risk_level

    阈值与 LLM 输出保持一致：<=3=high、<7=medium、>=7=low，
    保证前端无论拿到 LLM 还是规则结果都能用同一套颜色/文案渲染。
    """
    if score <= 3:
        return "high"
    if score < 7:
        return "medium"
    return "low"


def _rule_check_stolen_image(image_urls: list[str]) -> tuple[int, list[str]]:
    """规则模拟-盗图检测：基于图片 URL 域名和数量

    闲鱼官方图床域名（xianyu/taobao/alicdn）以外的图片来源视为可疑，
    无图片则风险等级直接降到 3 分。
    """
    stolen_signals: list[str] = []
    stolen_score = 8
    if not image_urls:
        stolen_signals.append("无商品图片")
        stolen_score = 3
    else:
        # 检查图片来源域名（闲鱼官方图床 vs 第三方）
        non_official = [u for u in image_urls if "xianyu" not in u and "taobao" not in u and "alicdn" not in u]
        if non_official:
            stolen_signals.append(f"含非官方图床图片({len(non_official)}张)")
            stolen_score = max(3, stolen_score - 3)
    return stolen_score, stolen_signals


def _rule_check_damage(title: str, description: str) -> tuple[int, list[str]]:
    """规则模拟-物理损坏识别：基于描述关键词

    每个损坏关键词累计减分（不 break），多个故障信号意味着成色更差。
    """
    damage_signals: list[str] = []
    damage_score = 8
    damage_keywords = ["划痕", "磕碰", "裂纹", "碎屏", "变形", "磨损", "掉漆", "开胶", "进水", "维修", "修过", "故障"]
    desc_combined = f"{title} {description}"
    for kw in damage_keywords:
        if kw in desc_combined:
            damage_signals.append(f"描述提及'{kw}'")
            damage_score = max(1, damage_score - 2)
    return damage_score, damage_signals


def _rule_check_consistency(
    title: str, description: str, image_urls: list[str]
) -> tuple[int, list[str]]:
    """规则模拟-描述与图片一致性：基于标题关键词与描述匹配度

    标题核心词在描述中提及率 <30% 视为不一致；无图片无法校验。
    """
    consistency_signals: list[str] = []
    consistency_score = 7
    # 标题中的核心型号词是否在描述中出现
    title_words = re.findall(r"[\u4e00-\u9fa5a-zA-Z0-9]+", title)
    if title_words and description:
        desc_lower = description.lower()
        matched = sum(1 for w in title_words if w.lower() in desc_lower)
        if matched < len(title_words) * 0.3:
            consistency_signals.append("标题核心词在描述中提及率低")
            consistency_score = max(3, consistency_score - 3)
    if not image_urls:
        consistency_signals.append("无图片无法校验一致性")
        consistency_score = max(3, consistency_score - 2)
    return consistency_score, consistency_signals


def _eval_template_keyword_hits(
    desc_combined: str, template_keywords: list[str]
) -> tuple[int, list[str]]:
    """评估模板词命中：>=3个堆砌减4分(最低2)，1-2个减1分(最低4)，0个不减分

    贩子常堆砌"99新/仅拆封/正品"等套话，命中数量越多越可疑。
    """
    template_hits = [kw for kw in template_keywords if kw in desc_combined]
    if len(template_hits) >= 3:
        return max(2, 7 - 4), [f"堆砌模板词({len(template_hits)}个): {'/'.join(template_hits[:3])}"]
    if len(template_hits) >= 1:
        return max(4, 7 - 1), [f"含模板词: {'/'.join(template_hits)}"]
    return 7, []


def _eval_seller_template_similarity(
    seller_items: list[dict[str, Any]] | None,
    template_keywords: list[str],
    current_score: int,
) -> tuple[int, list[str]]:
    """评估卖家多商品相似度：>=3商品且共用>=2模板词时减3分(最低1)

    多商品共用模板词是贩子批量发帖的典型特征，在单商品模板词扣分基础上再叠加。
    """
    if seller_items and len(seller_items) >= 3:
        descs = [s.get("description", "") for s in seller_items if s.get("description")]
        if len(descs) >= 3:
            # 简化相似度：统计在半数以上商品中出现的模板词数量
            common_template_count = sum(
                1 for kw in template_keywords
                if sum(1 for d in descs if kw in d) >= len(descs) * 0.5
            )
            if common_template_count >= 2:
                return max(1, current_score - 3), [f"卖家多商品共用模板词({common_template_count}个)，疑似贩子"]
    return current_score, []


def _rule_check_template(
    title: str, description: str, seller_items: list[dict[str, Any]] | None
) -> tuple[int, list[str]]:
    """规则模拟-文案模板化检测：基于模板关键词 + 卖家多商品相似度

    模板词命中阈值减分；卖家多商品共用模板词时疑似贩子再叠加扣分。
    """
    template_keywords = ["99新", "98新", "仅拆封", "未使用", "自用", "国行", "全新", "正品", "专柜", "代购"]
    desc_combined = f"{title} {description}"

    template_score, signals = _eval_template_keyword_hits(desc_combined, template_keywords)
    template_score, seller_signals = _eval_seller_template_similarity(
        seller_items, template_keywords, template_score
    )
    signals.extend(seller_signals)
    return template_score, signals


def _compute_overall_verdict(
    scores: list[int],
) -> tuple[str, str, float]:
    """综合判定：根据各维度评分推断 overall_verdict

    存在 high 风险（任一维度 score<=3）→ reject；
    否则存在 medium 风险（3<score<7）→ caution；
    全部 low（score>=7）→ recommend。
    """
    overall_score = round(sum(scores) / len(scores), 1)
    has_high = any(s <= 3 for s in scores)
    has_medium = any(3 < s < 7 for s in scores)
    if has_high:
        return "reject", "拒绝", overall_score
    if has_medium:
        return "caution", "谨慎", overall_score
    return "recommend", "购买", overall_score


def _rule_deep_analyze(
    title: str,
    description: str,
    image_urls: list[str],
    seller_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """无 LLM Key 时的规则模拟深度分析

    基于关键词和元数据特征做启发式判断，精度低于 LLM 但保证开箱可用。
    各维度检测逻辑独立提取为子函数，便于单测与阈值调整。
    """
    stolen_score, stolen_signals = _rule_check_stolen_image(image_urls)
    damage_score, damage_signals = _rule_check_damage(title, description)
    consistency_score, consistency_signals = _rule_check_consistency(title, description, image_urls)
    template_score, template_signals = _rule_check_template(title, description, seller_items)

    # 综合判定
    scores = [stolen_score, damage_score, consistency_score, template_score]
    overall_verdict, verdict_text, overall_score = _compute_overall_verdict(scores)

    return {
        "stolen_image": {
            "score": stolen_score,
            "risk_level": _rule_risk_level(stolen_score),
            "signals": stolen_signals,
            "detail": "规则模拟：基于图片来源域名和数量判断" + ("；".join(stolen_signals) if stolen_signals else "未发现盗图风险"),
        },
        "damage": {
            "score": damage_score,
            "risk_level": _rule_risk_level(damage_score),
            "damages": damage_signals,
            "detail": "规则模拟：基于描述关键词检测损坏" + ("；".join(damage_signals) if damage_signals else "未发现损坏描述"),
        },
        "consistency": {
            "score": consistency_score,
            "risk_level": _rule_risk_level(consistency_score),
            "inconsistencies": consistency_signals,
            "detail": "规则模拟：基于标题描述匹配度判断" + ("；".join(consistency_signals) if consistency_signals else "标题描述基本一致"),
        },
        "template": {
            "score": template_score,
            "risk_level": _rule_risk_level(template_score),
            "signals": template_signals,
            "detail": f"{_RULE_DETAIL_PREFIX}模板词频率和卖家多商品相似度" + ("；".join(template_signals) if template_signals else "文案较个性化"),
        },
        "overall_verdict": overall_verdict,
        "overall_score": overall_score,
        "summary": f"规则模拟综合评分 {overall_score}/10，建议{verdict_text}",
    }


def _norm_dimension(d: Any) -> dict[str, Any]:
    """归一化单个维度结果：score 限定 1-10，risk_level 兜底推断

    LLM 偶尔会返回非标准 risk_level（如 "warn"），需根据 score 重新推断；
    统一 signals/damages/inconsistencies 字段为 signals 便于前端统一渲染。
    """
    if not isinstance(d, dict):
        return {"score": 5, "risk_level": "medium", "signals": [], "detail": ""}
    score = d.get("score", 5)
    try:
        score = max(1, min(10, int(score)))
    except (TypeError, ValueError):
        score = 5
    risk = str(d.get("risk_level") or "").strip().lower()
    if risk not in ("low", "medium", "high"):
        # 非标准 risk_level 时按 score 兜底推断（阈值与 _rule_risk_level 一致，
        # 复用避免阈值漂移：规则模拟与 LLM 归一化必须用同一套阈值）
        risk = _rule_risk_level(score)
    # 统一 signals/damages/inconsistencies 字段为 signals
    signals = d.get("signals") or d.get("damages") or d.get("inconsistencies") or []
    return {
        "score": score,
        "risk_level": risk,
        "signals": [str(s) for s in signals if str(s).strip()],
        "detail": str(d.get("detail") or "").strip()[:200],
    }


def _normalize_verdict(raw: dict[str, Any]) -> str:
    """归一化 overall_verdict：非标准值时根据 overall_score 兜底推断

    verdict 必须为 recommend/caution/reject 之一；LLM 偶尔返回空或非标准值时，
    按 score 阈值（<=3 reject、<7 caution、>=7 recommend）回退。
    """
    verdict = str(raw.get("overall_verdict") or "").strip().lower()
    if verdict in ("recommend", "caution", "reject"):
        return verdict
    score = raw.get("overall_score", 5)
    # 根据 score 兜底推断 verdict
    if score <= 3:
        return "reject"
    if score < 7:
        return "caution"
    return "recommend"


def _normalize_overall_score(raw: dict[str, Any]) -> float:
    """归一化 overall_score：限定 1-10 范围，非数字回退 5.0"""
    try:
        return max(1, min(10, float(raw.get("overall_score", 5))))
    except (TypeError, ValueError):
        return 5.0


def _normalize_deep_result(raw: dict[str, Any], source: str) -> dict[str, Any]:
    """归一化深度分析结果

    各维度独立归一化（_norm_dimension），全局字段 verdict/score 分别提取子函数处理。
    """
    verdict = _normalize_verdict(raw)
    overall_score = _normalize_overall_score(raw)

    return {
        "stolen_image": _norm_dimension(raw.get("stolen_image")),
        "damage": _norm_dimension(raw.get("damage")),
        "consistency": _norm_dimension(raw.get("consistency")),
        "template": _norm_dimension(raw.get("template")),
        "overall_verdict": verdict,
        "overall_score": round(overall_score, 1),
        "summary": str(raw.get("summary") or "").strip()[:100],
        "source": source,
    }


# ============== 图片哈希工具 ==============
def _compute_image_url_hash(image_urls: list[str]) -> list[dict]:
    """计算图片 URL 的 MD5 哈希，用于盗图比对

    返回 [{url, hash}, ...] 列表（与 image_urls 一一对应）。
    同时保留原 URL，便于前端展示 url → hash 的对应关系。
    实际盗图检测需要下载图片计算感知哈希，这里用 URL 哈希作为轻量级替代。
    """
    return [{"url": url, "hash": hashlib.md5(url.encode()).hexdigest()[:12]} for url in image_urls]


# ============== 端点 ==============
def _parse_image_urls_deep(image_urls_raw: Any) -> list:
    """解析 image_urls 字段：items 表中可能是 JSON 字符串或列表

    SQLite 无原生数组类型，image_urls 以 TEXT 存 JSON 字符串；
    解析失败回退为空列表避免阻断分析。
    """
    if isinstance(image_urls_raw, str):
        try:
            return json.loads(image_urls_raw)
        except (json.JSONDecodeError, TypeError):
            return []
    return image_urls_raw


def _get_seller_items(
    container: Container, seller_id: str | None, checks: list[str]
) -> list[dict[str, Any]]:
    """获取卖家其他商品（用于模板化检测）

    仅当 checks 含 'template' 且有 seller_id 时才查询，避免无谓 DB 调用。
    查询失败不阻断分析（返回空列表）。
    """
    if not seller_id or "template" not in checks:
        return []
    try:
        # 通过 repo 获取该卖家的其他商品
        return container.repo.list_items_by_seller(seller_id, limit=10)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[P1-4] 获取卖家商品失败（不影响分析）: {e}")
        return []


async def _run_deep_analyze(
    title: str,
    description: str,
    price: float,
    image_urls: list,
    seller_items: list[dict[str, Any]],
    item_id: str,
) -> tuple[dict[str, Any], str]:
    """执行深度分析：有 Key 走 LLM Vision，无 Key 或失败降级规则模拟

    返回 (raw_result, source)：source 标识 'llm' 或 'rule' 供归一化区分。
    """
    settings = get_settings()
    used_source = "llm"
    raw_result: dict[str, Any] | None = None

    if settings.openai_api_key:
        try:
            raw_result = await _call_llm_deep_analyze(
                title, description, price, image_urls, seller_items
            )
            logger.info(f"[P1-4] LLM 深度分析完成: item_id={item_id}")
        except RuntimeError as e:
            logger.warning(f"[P1-4] LLM 深度分析失败，降级规则模拟: {e}")
            raw_result = None
    else:
        used_source = "rule"

    if raw_result is None:
        raw_result = _rule_deep_analyze(
            title, description, image_urls, seller_items
        )
        used_source = "rule"
        logger.info(f"[P1-4] 规则模拟深度分析完成: item_id={item_id}")

    return raw_result, used_source


def _filter_unrequested_checks(
    result: dict[str, Any], checks: list[str]
) -> dict[str, Any]:
    """过滤未请求的检查项，保留全局字段

    用户可能只请求部分检查项（如只查 stolen_image），需移除未请求的维度结果；
    全局字段（verdict/score/summary 等）始终保留供前端展示概览。
    """
    filtered: dict[str, Any] = {}
    for check in checks:
        if check in result:
            filtered[check] = result[check]
    # 保留全局字段
    for key in ("overall_verdict", "overall_score", "summary", "source", "image_hashes", "item_id", "checks_performed"):
        filtered[key] = result[key]
    return filtered


@router.post("/deep-analyze")
async def deep_analyze(
    body: DeepAnalyzeRequest,
    request: Request,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """P1-4 单商品深度多模态分析

    执行 4 项深度检查：
    1. stolen_image: 盗图检测
    2. damage: 物理损坏识别
    3. consistency: 描述与图片一致性
    4. template: 文案模板化检测

    有 LLM Key 走 Vision 深度分析，无 Key 走规则模拟。
    """
    _check_ai_enabled()
    # 1. 获取商品信息
    user_id = getattr(request.state, "user_id", None)
    item = container.repo.get_item(body.item_id, user_id=user_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"商品 {body.item_id} 不存在")

    title = item.get("title", "")
    description = item.get("description", "")
    price = float(item.get("price", 0))
    image_urls = _parse_image_urls_deep(item.get("image_urls") or [])

    # 2. 获取卖家其他商品（用于模板化检测）
    seller_items = _get_seller_items(container, item.get("seller_id"), body.checks)

    # 3. 调用 LLM 或规则模拟
    raw_result, used_source = await _run_deep_analyze(
        title, description, price, image_urls, seller_items, body.item_id
    )

    # 4. 归一化结果
    result = _normalize_deep_result(raw_result, used_source)

    # 5. 补充图片哈希信息（用于前端展示盗图比对）
    result["image_hashes"] = _compute_image_url_hash(image_urls)
    result["item_id"] = body.item_id
    result["checks_performed"] = body.checks

    # 6. 过滤未请求的检查项
    return _filter_unrequested_checks(result, body.checks)


def _count_template_keywords(descriptions: list[str]) -> dict[str, int]:
    """统计模板词在所有描述中的出现频率

    闲鱼贩子常用模板词（99新/仅拆封/支持验货等），高频出现暗示文案模板化。
    返回 {keyword: total_count} 供后续高频词判定。
    """
    template_keywords = [
        "99新", "98新", "95新", "仅拆封", "未使用", "自用", "国行",
        "全新", "正品", "专柜", "代购", "支持验货", "假一赔十",
        "闲置", "回血", "出国", "搬家", "清仓",
    ]
    desc_combined = " ".join(descriptions)
    return {kw: desc_combined.count(kw) for kw in template_keywords}


def _compute_desc_length_variance(descriptions: list[str]) -> tuple[float, list[int]]:
    """计算描述长度方差（贩子文案长度通常很接近）

    返回 (variance, desc_lens)：
    - 样本数 <3 时方差为 0（样本不足无统计意义）
    - desc_lens 用于后续"高度一致"判定需 >=5 的阈值检查
    """
    desc_lens = [len(d) for d in descriptions if d]
    if len(desc_lens) < 3:
        return 0, desc_lens
    avg_len = sum(desc_lens) / len(desc_lens)
    variance = sum((l - avg_len) ** 2 for l in desc_lens) / len(desc_lens)
    return variance, desc_lens


def _find_shared_sentences(descriptions: list[str]) -> list[str]:
    """检测多商品共用的句子（贩子文案模板化特征）

    简化 N-gram：按标点分句，统计句子在多个描述中出现的次数，
    出现 >=3 次视为共用句子。只统计长度 >=8 的句子避免短词干扰。
    """
    common_phrases: dict[str, int] = Counter()
    for desc in descriptions:
        # 简化：按标点分句，统计句子在多个描述中出现的次数
        sentences = re.split(r"[。！!？?；;\n]", desc)
        for s in sentences:
            s = s.strip()
            if len(s) >= 8:  # 只统计较长的句子
                common_phrases[s] += 1
    return [s for s, cnt in common_phrases.items() if cnt >= 3]


def _compute_template_score(
    high_freq_keywords: list[str],
    len_variance: float,
    desc_lens: list[int],
    shared_sentences: list[str],
) -> tuple[int, list[str]]:
    """综合评分：高频模板词 + 长度方差 + 共用句子三项叠加扣分

    返回 (template_score, signals)：每项命中都生成对应信号说明，
    template_score 最低不低于 1。
    """
    template_score = 10
    signals: list[str] = []

    if high_freq_keywords:
        signals.append(f"高频模板词({len(high_freq_keywords)}个): {'/'.join(high_freq_keywords[:3])}")
        template_score = max(1, template_score - len(high_freq_keywords) * 2)

    # 长度方差 <50 且样本 >=5 才判定（样本少时方差无统计意义）
    if len_variance < 50 and len(desc_lens) >= 5:
        signals.append(f"描述长度高度一致(方差={len_variance:.0f})，疑似模板")
        template_score = max(1, template_score - 3)

    if shared_sentences:
        signals.append(f"多商品共用文案({len(shared_sentences)}句)")
        template_score = max(1, template_score - len(shared_sentences))

    return template_score, signals


def _infer_template_risk_level(score: int) -> str:
    """根据 template_score 推断风险等级

    阈值与 _rule_risk_level 保持一致：<=3 high、<7 medium、>=7 low。
    """
    if score <= 3:
        return "high"
    if score < 7:
        return "medium"
    return "low"


@router.post("/seller-template-check")
def seller_template_check(
    body: SellerTemplateCheckRequest,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """P1-4 卖家文案模板化检测（贩子识别）

    分析卖家多个商品的描述相似度，识别是否为贩子（批量发帖、共用模板文案）。
    """
    _check_ai_enabled()
    # 1. 获取卖家商品列表
    try:
        items = container.repo.list_items_by_seller(body.seller_id, limit=body.sample_size)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"获取卖家商品失败: {e}")

    if not items or len(items) < 3:
        return {
            "seller_id": body.seller_id,
            "sample_count": len(items) if items else 0,
            "template_score": 10,
            "is_dealer": False,
            "signals": ["样本不足（<3），无法判断"],
            "detail": "卖家商品数量过少，无法进行模板化检测",
        }

    # 2. 提取描述
    descriptions = [it.get("description", "") for it in items if it.get("description")]

    # 3. 模板词频率统计
    keyword_freq = _count_template_keywords(descriptions)

    # 4. 计算模板化得分
    # 4.1 高频模板词数量（出现次数 >= 描述数 * 0.4 视为高频）
    high_freq_keywords = [kw for kw, cnt in keyword_freq.items() if cnt >= len(descriptions) * 0.4]
    # 4.2 描述长度方差
    len_variance, desc_lens = _compute_desc_length_variance(descriptions)
    # 4.3 共同短语检测
    shared_sentences = _find_shared_sentences(descriptions)

    # 5. 综合评分
    template_score, signals = _compute_template_score(
        high_freq_keywords, len_variance, desc_lens, shared_sentences
    )

    # 6. 判定
    is_dealer = template_score <= 4
    risk_level = _infer_template_risk_level(template_score)

    return {
        "seller_id": body.seller_id,
        "sample_count": len(items),
        "template_score": template_score,
        "is_dealer": is_dealer,
        "risk_level": risk_level,
        "signals": signals,
        "keyword_freq": keyword_freq,
        "shared_sentences_count": len(shared_sentences),
        "desc_length_variance": round(len_variance, 1),
        "detail": "；".join(signals) if signals else "文案较个性化，未发现模板化特征",
    }
