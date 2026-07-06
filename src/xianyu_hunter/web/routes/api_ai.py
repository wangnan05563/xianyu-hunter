"""AI 辅助 API - 自然语言解析为结构化任务字段 + F-06 多模态成色评估

设计原则：
- **零新增依赖**：用 httpx（已装）直接调 OpenAI 兼容 chat completions，base_url 兼容 OpenAI / DeepSeek / 智谱 等
- **有 Key 走 LLM，没 Key 走规则**：规则解析覆盖 80% 常见场景（中文价格描述 + 关键词抽取），保证"开箱可用"
- **30s 超时**：和前端约定一致，避免 LLM 抽风时用户傻等
- **错误信息对用户友好**：把上游 HTTP 错/JSON 解析错/超时映射到一句话

F-06 AI 多模态成色评估：
- 评估通过的商品（4维评分 ≥ 60）→ 拉取商品图 + 描述 → 调用 LLM Vision 二次确认成色真实性
- 有 Key 走 LLM Vision，没 Key 走规则模拟（基于价格/描述关键词判断）
- 评估结果缓存到 evaluations 表的 dimension_scores 字段，避免重复调用 LLM
"""
from __future__ import annotations

import json
import re
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from xianyu_hunter.config import get_settings, update_ai_config
from xianyu_hunter.container import Container
from xianyu_hunter.infra.ai_usage import check_budget, record_usage
from xianyu_hunter.infra.db_models import _utcnow
from xianyu_hunter.web.deps import get_container

router = APIRouter(prefix="/api/ai", tags=["ai"])

# 超时：与前端 AbortController 30s 对齐（前端 30s 触发 abort，后端不能让它跑更久）
HTTP_TIMEOUT_SEC = 25.0

# LLM 调用共享常量：多处 endpoint 共用同一组 HTTP 头/路径，提取为常量避免散落修改
CHAT_COMPLETIONS_PATH = "/chat/completions"
AUTH_BEARER_PREFIX = "Bearer "
CONTENT_TYPE_JSON = "application/json"

# Vision 能力关键字白名单：模型名包含任一关键字即视为支持多模态。
# 升级模型时只需在此处追加（如新增 "gemini-2.0-flash"），所有调用点自动生效。
# 注：纯文本模型（deepseek-chat / moonshot-v1-8k 等）服务端 schema 不支持 image_url
# content block，强行传图会被报 400（unknown variant `image_url`）导致降级。
_VISION_CAPABLE_KEYWORDS: tuple[str, ...] = (
    "vision",
    "gpt-4o",
    "gpt-4-vision",
    "qvq",
    "qwen-vl",
    "glm-4v",
    "claude-3",
    "opus",
    "sonnet",
    "haiku",
)


def _is_vision_capable(model_name: str | None) -> bool:
    """判断指定模型是否支持多模态（Vision）输入。

    api_ai 成色评估 / api_ai_deep 深度分析 共用此判断，避免散落关键字导致漏改。
    """
    if not model_name:
        return False
    name = model_name.lower()
    return any(kw in name for kw in _VISION_CAPABLE_KEYWORDS)


def _check_ai_enabled() -> None:
    """AI 全局开关检查：关闭时抛出 403，阻止所有 AI 调用"""
    settings = get_settings()
    if not settings.ai_enabled:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=403,
            detail="AI 功能已关闭，请在「AI 服务」配置页面开启",
        )


# ============== 模型 ==============
class ParseTaskBody(BaseModel):
    """用户自然语言输入"""
    text: str = Field(..., min_length=1, max_length=2000)


# ============== LLM Prompt ==============
_SYSTEM_PROMPT = """你是一个闲鱼监控任务的字段提取助手。
用户会用一句话描述"我想买什么 / 卖什么 / 关注什么"。
请从这段描述中提取出以下结构化字段，并仅以 JSON 输出（不要 Markdown 代码块包裹，不要解释）：

{
  "keyword": string,            // 必填，监控的核心关键词；如 "索尼 A7M4"、"iPhone 13 128G"
  "name": string,               // 任务名（可读），默认 = keyword
  "min_price": number|null,     // 价格下限（人民币元），无 → null
  "max_price": number|null,     // 价格上限（人民币元），无 → null
  "mode": "notify"|"confirm"|"auto",  // 执行模式：notify=仅通知 / confirm=通知+确认 / auto=全自动抢单
  "exclude_words": string[],    // 排除词（如 "二手"→用户明确不要的）；无 → []
  "notes": string,              // 备注：地域偏好、版本偏好、新旧度偏好等用户没结构化说出的信息
  "reason": string              // 一句话说明：为什么这么解析（让用户一眼看懂 max_price 怎么来的）
}

提取规则：
1. 价格中文写法：1k=1000, 1.2w=12000, 1万=10000, 9k5=9500, 1.2w 以内 → max_price=12000
2. 模式默认 notify；用户说"全自动/自动抢单/秒拍/立刻下单"→auto；说"通知我/帮我看"→notify；说"我先看再决定"→confirm
3. 排除词：用户明确说"不要 X / 排除 X"时提取；"9 成新"不算排除词（属于商品成色）
4. keyword 优先保留用户原话中的"商品 + 型号 + 容量 + 关键配置"，去掉修饰语
5. reason 必须简短（≤30 字），写"基于'xxx'提取"

只输出 JSON，不要其它任何内容。
"""


def _parse_llm_response(r: httpx.Response) -> dict[str, Any]:
    """从 LLM chat completions 响应中提取并解析 JSON dict

    _call_llm 和 _call_llm_vision 共享此逻辑，避免重复的
    JSON 解析 / ```json 剥离 / 类型校验代码。
    """
    try:
        data = r.json()
        content = data["choices"][0]["message"]["content"]
    except (KeyError, ValueError, IndexError) as e:
        raise RuntimeError("AI 返回结构异常: " + str(e)) from None
    # LLM 偶尔会包 ```json ... ```，剥掉
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"(?:^```(?:json)?\s*|\s*```$)", "", content, flags=re.MULTILINE).strip()
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        raise RuntimeError(f"AI 返回非 JSON: {content[:200]}") from None
    if not isinstance(parsed, dict):
        raise RuntimeError("AI 返回非 dict 结构")
    return parsed


# ============== LLM 调用 ==============
def _call_llm(text: str) -> dict[str, Any]:
    """调 OpenAI 兼容 chat completions，返回解析后的 dict

    失败抛 RuntimeError，错误信息对用户友好。
    """
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError(
            "未配置 OPENAI_API_KEY（请在 .env 设置 openai_api_key 后重启服务）；"
            "当前已自动切换到本地规则解析"
        )
    # 预算检查：超出每日限制则拒绝调用
    allowed, reason = check_budget()
    if not allowed:
        raise RuntimeError(f"AI 调用受限：{reason}，已自动降级到规则解析")

    url = settings.openai_base_url.rstrip("/") + CHAT_COMPLETIONS_PATH
    # P1-8：从 Prompt 编辑器读取最新内容（支持热更新，无需重启）
    from xianyu_hunter.web.routes.api_prompts import get_active_prompt
    system_prompt = get_active_prompt("parse_task")
    payload = {
        "model": settings.openai_model,  # 可配置：支持 DeepSeek/智谱等
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "max_tokens": 600,
    }
    headers = {
        "Authorization": AUTH_BEARER_PREFIX + settings.openai_api_key,
        "Content-Type": CONTENT_TYPE_JSON,
    }
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT_SEC) as client:
            r = client.post(url, json=payload, headers=headers)
    except httpx.TimeoutException:
        raise RuntimeError("AI 解析超时（>25s）") from None
    except httpx.HTTPError as e:
        raise RuntimeError("AI 解析网络错误: " + str(e)) from None
    if r.status_code != 200:
        # 把上游错误信息截短（OpenAI 经常返回长篇错误体）
        snippet = r.text[:300]
        raise RuntimeError(f"AI 服务返回 {r.status_code}: {snippet}")

    # 记录用量
    try:
        resp_data = r.json()
        record_usage("parse_task", settings.openai_model, resp_data)
    except Exception:
        record_usage("parse_task", settings.openai_model)

    return _parse_llm_response(r)


# ============== 规则解析（fallback） ==============
_PRICE_PATTERN = re.compile(
    r"(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>w|万|k|千)\b|"
    r"(?P<yuan>\d{2,7})\s*(?:元|块|RMB|rmb|¥|￥)\b|"
    r"(?:预算|价格|价位)\s*(?P<low>\d+(?:\.\d+)?)\s*[-~到至]\s*(?P<high>\d+(?:\.\d+)?)\b",
    re.IGNORECASE,
)
# 中文数字（简版）：百/千/万
_CN_NUM = {"百": 100, "千": 1000, "k": 1000, "K": 1000, "w": 10000, "W": 10000, "万": 10000}


def _to_number(raw: str) -> float | None:
    """把 '1.2w' / '9k5' / '12k' / '1万' / '5000' 转成数字"""
    if not raw:
        return None
    s = raw.strip()
    # 1.2w / 9k5 / 1万
    m = re.match(r"^(\d+(?:\.\d+)?)([wWkK万千])(?:(\d{1,2}))?$", s)
    if m:
        n = float(m.group(1)) * _CN_NUM[m.group(2).lower()]
        # 9k5 这种 "k 之后接一位数" 视作 9500（闲鱼黑话）
        if m.group(3):
            n += float("0." + m.group(3)) * 1000
        return n
    # 纯数字
    try:
        return float(s)
    except ValueError:
        return None


def _parse_price_range(t: str) -> tuple[float | None, float | None, re.Match | None]:
    """规则解析-价格区间：识别 '预算 1000-3000' / '1k~2k' / '1.2w 以内' 等写法

    返回 (min_price, max_price, range_match)：
    - range_match 用于后续关键词提取时移除价格片段
    - 区间写法优先于单值写法（互斥）
    - 100 以内数字（如"9 成新"）不算价格
    """
    min_price: float | None = None
    max_price: float | None = None
    # 区间写法（"-" "～" "到" "至"）
    range_m = re.search(
        r"(\d+(?:\.\d+)?\s*[wWkK万千]?)\s*[-~～到至]\s*(\d+(?:\.\d+)?\s*[wWkK万千]?)", t
    )
    if range_m:
        min_price = _to_number(range_m.group(1).replace(" ", ""))
        max_price = _to_number(range_m.group(2).replace(" ", ""))
        return min_price, max_price, range_m
    # 单值："预算 1.2w" / "1.2w 以内" / "1.2w 左右"
    single_m = re.search(
        r"(\d+(?:\.\d+)?\s*[wWkK万千])(?:\s*(?:以内|以下|左右|上下|上下左右))?", t
    )
    if single_m:
        max_price = _to_number(single_m.group(1).replace(" ", ""))
    # "1k5" "1k" "5000" 等纯数字
    if max_price is None:
        num_m = re.search(r"(\d{2,7})", t)
        if num_m:
            v = float(num_m.group(1))
            # 100 以内（如"9 成新"）不算价格
            if v >= 100:
                max_price = v
    return min_price, max_price, None


def _parse_mode(t: str) -> str:
    """规则解析-执行模式：从描述关键词推断 notify/confirm/auto

    默认 notify；auto 关键词优先级高于 confirm（auto 更激进，命中即覆盖默认）。
    """
    if re.search(r"(全自动|自动抢|秒拍|秒抢|自动拍|立刻下单|自动下单)", t):
        return "auto"
    if re.search(r"(通知.{0,3}确认|我先看|先确认|半自动)", t):
        return "confirm"
    return "notify"


def _parse_exclude_words(t: str) -> tuple[list[str], re.Match | None]:
    """规则解析-排除词：用户明确说"不要 / 排除"时提取后续词列表

    返回 (words, excl_match)：excl_match 用于关键词提取时移除排除词片段。
    """
    excl_m = re.search(r"(?:不要|排除|不想要|避开)\s*([^\s,，。；;]+(?:[\s,，。；;]+[^\s,，。；;]+)*)", t)
    if not excl_m:
        return [], None
    words = [w.strip() for w in re.split(r"[\s,，。；;]+", excl_m.group(1)) if w.strip()]
    return words, excl_m


def _extract_keyword(t: str, range_m: re.Match | None, excl_m: re.Match | None) -> str:
    """规则解析-关键词：剥掉价格/模式/排除词等"元数据"，剩下的核心商品描述

    多轮 re.sub 移除各类元信息后，若结果为空则保底用原文（避免空关键词）。
    """
    kw = t
    # 移除价格相关
    if range_m:
        kw = kw.replace(range_m.group(0), "")
    kw = re.sub(r"\d+(?:\.\d+)?\s*[wWkK万千](?:\s*(?:以内|以下|左右|上下|上下左右))?", "", kw)
    kw = re.sub(r"(预算|价格|价位)\s*\d+", "", kw)
    kw = re.sub(r"\d{2,7}\s*(?:元|块|RMB|rmb|¥|￥)?", "", kw)
    # 移除模式相关
    kw = re.sub(r"(全自动|自动抢|秒拍|秒抢|自动拍|立刻下单|自动下单|通知.{0,3}确认|我先看|先确认|半自动)", "", kw)
    # 移除排除词相关
    if excl_m:
        kw = kw.replace(excl_m.group(0), "")
    # 移除常用连接词
    kw = re.sub(r"(想买|想找|关注|捡漏|找一下|帮我|一个|一只|一台|一款)", "", kw)
    kw = re.sub(r"[\s,，。；;]+", " ", kw).strip()
    if not kw:
        kw = t  # 兜底：拿不到关键词就保底用原文
    return kw


def _parse_notes(t: str) -> str:
    """规则解析-备注：提取地域/版本/新旧等"元信息"

    地域词（本地/同城/包邮/顺丰）和成新（如"9 成新"）是用户未结构化的偏好，
    单独拼到 notes 字段供前端展示。
    """
    note_m = re.search(r"([\u4e00-\u9fa5]{2,15}(本地|同城|包邮|顺丰))", t)
    notes = note_m.group(1) if note_m else ""
    if re.search(r"\d+\s*成新", t):
        cn_match = re.search(r"(\d+)\s*成新", t)
        if cn_match:
            notes = (notes + " · " + cn_match.group(0)).strip(" ·")
    return notes


def _build_parse_reason(min_price: float | None, max_price: float | None, mode: str) -> str:
    """规则解析-构建 reason：简短说明解析依据，让用户看懂字段来源"""
    reason_parts: list[str] = []
    if max_price is not None:
        reason_parts.append(f"max_price={int(max_price)}")
    if min_price is not None:
        reason_parts.append(f"min_price={int(min_price)}")
    if mode != "notify":
        reason_parts.append(f"mode={mode}")
    return "规则解析: " + (", ".join(reason_parts) if reason_parts else "仅提取关键词")


def _rule_parse(text: str) -> dict[str, Any]:
    """规则解析：覆盖基础场景（价格 + 关键词），不依赖外部 LLM

    输出格式与 LLM 输出一致，保证前端能无差别使用。
    各解析维度独立提取为子函数，range_m/excl_m 通过参数传递以供关键词提取复用。
    """
    t = text.strip()
    # 1. 价格区间
    min_price, max_price, range_m = _parse_price_range(t)
    # 2. 模式
    mode = _parse_mode(t)
    # 3. 排除词
    exclude_words, excl_m = _parse_exclude_words(t)
    # 4. 关键词
    kw = _extract_keyword(t, range_m, excl_m)
    # 5. 备注
    notes = _parse_notes(t)
    # 6. 任务名
    name = kw[:30]
    # 7. reason
    reason = _build_parse_reason(min_price, max_price, mode)

    return {
        "keyword": kw,
        "name": name,
        "min_price": int(min_price) if min_price is not None else None,
        "max_price": int(max_price) if max_price is not None else None,
        "mode": mode,
        "exclude_words": exclude_words,
        "notes": notes,
        "reason": reason,
        "_source": "rule",  # 给前端用：标识是 fallback 结果
    }


def _try_parse_with_llm(text: str, settings: Any) -> tuple[dict[str, Any] | None, str]:
    """尝试 LLM 解析，失败时返回 (None, source) 触发降级

    返回 (parsed, used_source)：used_source 为 'llm' 或 'rule'，
    parsed 为 None 时调用方应走规则解析兜底。
    """
    if not settings.openai_api_key:
        return None, "rule"
    try:
        return _call_llm(text), "llm"
    except RuntimeError as e:
        # LLM 失败不直接挂，降级到规则解析
        logger.warning(f"[ai/parse-task] LLM 失败，降级规则解析: {e}")
        return None, "llm"


def _normalize_parse_result(parsed: dict[str, Any], text: str, used_source: str) -> dict[str, Any]:
    """强制字段归一化：保证前端拿到的字段都在白名单内

    LLM/规则解析输出可能字段缺失或类型不一致，统一转换避免前端崩溃。
    """
    return {
        "keyword": str(parsed.get("keyword") or "").strip() or text,
        "name": str(parsed.get("name") or parsed.get("keyword") or text).strip(),
        "min_price": _coerce_int(parsed.get("min_price")),
        "max_price": _coerce_int(parsed.get("max_price")),
        "mode": parsed.get("mode") if parsed.get("mode") in ("notify", "confirm", "auto") else "notify",
        "exclude_words": [str(x).strip() for x in (parsed.get("exclude_words") or []) if str(x).strip()],
        "notes": str(parsed.get("notes") or "").strip(),
        "reason": str(parsed.get("reason") or "").strip(),
        "source": used_source,
    }


# ============== 端点 ==============
@router.post("/parse-task")
def parse_task(body: ParseTaskBody) -> dict[str, Any]:
    """自然语言 → 结构化任务字段

    流程：
    1) 优先调 LLM（OpenAI 兼容 chat completions）
    2) 没配 Key 或 LLM 失败 → 规则解析
    3) 返回统一结构 + source 标记
    """
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="文本不能为空")
    _check_ai_enabled()

    # 1. 试 LLM，失败则降级
    settings = get_settings()
    parsed, used_source = _try_parse_with_llm(text, settings)
    if parsed is None:
        parsed = _rule_parse(text)
        used_source = "rule"

    # 2. 字段归一化 + 关键词校验
    norm = _normalize_parse_result(parsed, text, used_source)
    if not norm["keyword"]:
        raise HTTPException(status_code=422, detail="无法从描述中提取关键词，请说得更具体一些（例如'iPhone 13 128G 银色'）")
    return norm


def _coerce_int(v: Any) -> int | None:
    """把 LLM 输出的 number / str / null 统一为 int 或 None"""
    if v is None or v == "":
        return None
    try:
        f = float(v)
        if f != f:  # NaN
            return None
        return int(f)
    except (TypeError, ValueError):
        return None


# ============== F-06 AI 多模态成色评估 ==============

# 图片分析超时更长（需要下载图片 + Vision 推理）
VISION_TIMEOUT_SEC = 60.0


class ConditionEvalRequest(BaseModel):
    """F-06 成色评估请求"""
    item_id: str = Field(..., description="闲鱼商品 ID")
    evaluation_id: str | None = Field(None, description="关联已有评估记录 ID")


# 成色评估的 LLM Prompt
_CONDITION_SYSTEM_PROMPT = """你是一个闲鱼二手商品成色鉴定专家。
用户会提供商品的标题、描述、价格和图片。请根据这些信息判断商品的真实成色。

评估维度：
1. **外观成色**：从图片判断商品是否有明显划痕、磕碰、变色、磨损
2. **描述一致性**：卖家描述的成色与图片展示是否一致（如描述"99新"但图片有明显磨损 → 不一致）
3. **价格合理性**：价格是否与声称的成色匹配（如声称"全新"但价格远低于市场价 → 可疑）
4. **风险信号**：图片模糊/过少、描述含糊、价格异常低等

评分标准（condition_score 1-10）：
- 9-10：全新/未拆封，图片清晰多角度，描述详细可信
- 7-8：95新-99新，轻微使用痕迹，描述与图片一致
- 5-6：正常使用磨损，功能正常，价格与成色匹配
- 3-4：明显磨损/划痕，可能影响使用，价格偏低
- 1-2：严重损坏/维修过/描述与图片严重不符

判定规则：
- verdict="recommend"：condition_score >= 7 且无重大风险信号
- verdict="caution"：condition_score < 7 或存在重大风险信号
- 如果图片无法加载或不存在，仅基于文字描述评估，risk_signals 加入"无图片参考"

示例：
输入：标题="iPhone 13 99新 自用" 描述="无划痕无磕碰，电池健康92%" 价格=2800 图片=[清晰多角度]
输出：{"verdict":"recommend","condition_score":8,"appearance_score":8,"consistency_score":9,"price_reasonability":8,"risk_signals":[],"reason":"99新自用，描述详细，图片清晰","detail":"商品成色良好，描述与图片一致，价格合理"}

输入：标题="iPhone 13 便宜卖" 描述="" 价格=800 图片=[模糊1张]
输出：{"verdict":"caution","condition_score":3,"appearance_score":3,"consistency_score":2,"price_reasonability":2,"risk_signals":["图片模糊","价格异常低","描述过于简略"],"reason":"价格远低于市场价，图片模糊，描述缺失","detail":"多个风险信号叠加，价格仅为市场价30%，疑似有问题"}

请输出以下 JSON（不要 Markdown 代码块包裹，不要解释）：
{
  "verdict": "recommend" | "caution",
  "condition_score": number,       // 1-10 整数，10=全新/完美，1=严重损坏
  "appearance_score": number,      // 外观成色 1-10
  "consistency_score": number,     // 描述一致性 1-10
  "price_reasonability": number,   // 价格合理性 1-10
  "risk_signals": string[],        // 风险信号列表
  "reason": string,                // 一句话总结（≤50字）
  "detail": string                 // 详细分析（≤200字）
}

只输出 JSON，不要其它任何内容。
"""


def _build_vision_condition_prompt(vision_capable: bool) -> str:
    """构建成色评估的 system prompt

    纯文本模型时追加"无图评估"说明，避免 LLM 强行编造"我看了图片"导致评估失真。
    """
    # P1-8：从 Prompt 编辑器读取最新内容（支持热更新，无需重启）
    from xianyu_hunter.web.routes.api_prompts import get_active_prompt
    condition_prompt = get_active_prompt("evaluate_condition")
    if not vision_capable:
        condition_prompt = (
            condition_prompt
            + "\n\n【特别说明】当前模型不支持图片分析，请仅基于标题、描述、价格"
              "和同类物品价格区间进行评估，risk_signals 中加入'无图片参考'。"
        )
    return condition_prompt


def _build_vision_text_content(
    title: str, description: str, price: float, price_range: dict[str, Any] | None
) -> str:
    """构建 Vision 请求的文本内容（商品信息 + 同类价格区间参考）"""
    text_content = f"商品标题：{title}\n商品描述：{description}\n商品价格：¥{price}"
    # 注入同类物品价格区间，让 LLM 判断当前价格是否合理可拾
    if price_range and price_range.get("sample_size", 0) > 0:
        text_content += (
            f"\n\n同类物品近期成交价格参考："
            f"\n- 最低价（捡漏价格）：¥{price_range.get('bargain_price')}"
            f"\n- 最高价：¥{price_range.get('max_price')}"
            f"\n- 中位数：¥{price_range.get('median_price')}"
            f"\n- 样本数：{price_range.get('sample_size')}"
            f"\n- 数据来源：{price_range.get('source_label', price_range.get('source', ''))}"
            f"\n请结合此价格区间判断当前商品价格是否处于合理可拾区间。"
        )
    return text_content


def _build_vision_user_content(
    text_content: str, image_urls: list[str], vision_capable: bool
) -> list[dict[str, Any]]:
    """构建 Vision 请求的 user_content（文本 + 图片 URL 列表）

    最多传入 4 张图片（避免 token 过多 + 超时）。
    闲鱼图片 URL 常为协议相对路径（//img.alicdn.com/...），LLM 端无法解析，
    需补全为 https://，否则会被 vision 服务报 400 失败并降级规则模拟。
    """
    user_content: list[dict[str, Any]] = [
        {"type": "text", "text": text_content},
    ]
    for img_url in image_urls[:4]:
        # 纯文本模型不接图，避免 400 报错 + 用量浪费
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


async def _call_llm_vision(
    title: str,
    description: str,
    price: float,
    image_urls: list[str],
    price_range: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """调 OpenAI 兼容 Vision API 分析商品图片 + 描述

    使用 httpx.AsyncClient 避免阻塞事件循环（Vision 调用最长 60s）。
    price_range 为同类物品已售价格区间，注入 prompt 增强 price_reasonability 判定。
    失败抛 RuntimeError，错误信息对用户友好。
    """
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("未配置 OPENAI_API_KEY，无法使用 AI 成色评估")

    # 预算检查
    allowed, reason = check_budget()
    if not allowed:
        raise RuntimeError(f"AI 调用受限：{reason}，已自动降级到规则评估")

    url = settings.openai_base_url.rstrip("/") + CHAT_COMPLETIONS_PATH
    # 检测当前 vision_model 是否支持多模态（统一在 _is_vision_capable 维护关键字白名单）
    vision_capable = _is_vision_capable(settings.openai_vision_model)

    condition_prompt = _build_vision_condition_prompt(vision_capable)
    text_content = _build_vision_text_content(title, description, price, price_range)
    user_content = _build_vision_user_content(text_content, image_urls, vision_capable)

    payload = {
        "model": settings.openai_vision_model,  # 可配置：Vision 模型
        "messages": [
            {"role": "system", "content": condition_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.3,
        "max_tokens": 800,
    }
    headers = {
        "Authorization": AUTH_BEARER_PREFIX + settings.openai_api_key,
        "Content-Type": CONTENT_TYPE_JSON,
    }
    try:
        async with httpx.AsyncClient(timeout=VISION_TIMEOUT_SEC) as client:
            r = await client.post(url, json=payload, headers=headers)
    except httpx.TimeoutException:
        raise RuntimeError("AI 成色评估超时（>60s），图片分析较慢请稍后重试") from None
    except httpx.HTTPError as e:
        raise RuntimeError(f"AI 成色评估网络错误: {e}") from None
    if r.status_code != 200:
        snippet = r.text[:300]
        raise RuntimeError(f"AI 服务返回 {r.status_code}: {snippet}")

    # 记录用量
    try:
        resp_data = r.json()
        record_usage("evaluate_condition", settings.openai_vision_model, resp_data)
    except Exception:
        record_usage("evaluate_condition", settings.openai_vision_model)

    return _parse_llm_response(r)


def _eval_good_keywords(
    title: str, description: str, condition_score: int, detail_parts: list[str]
) -> int:
    """规则评估-加分关键词：命中即停，避免近义词过度加分

    "全新/未拆封/仅拆封/99新/98新/未使用/自用/国行" 是闲鱼正向成色信号，
    但一个商品可能同时含多个（如"99新自用国行"），不应叠加加分。
    """
    good_keywords = ["全新", "未拆封", "仅拆封", "99新", "98新", "未使用", "自用", "国行"]
    for kw in good_keywords:
        if kw in title or kw in (description or ""):
            condition_score = min(10, condition_score + 1)
            detail_parts.append(f"描述含'{kw}'")
            break
    return condition_score


def _eval_bad_keywords(
    title: str,
    description: str,
    condition_score: int,
    risk_signals: list[str],
    detail_parts: list[str],
) -> int:
    """规则评估-减分关键词：每个故障词累计减分

    不 break：多个故障信号（如"划痕+维修"）意味着成色更差，需累计扣分。
    """
    bad_keywords = ["划痕", "磕碰", "维修", "进水", "碎屏", "开胶", "变形", "故障", "修过", "换过"]
    for kw in bad_keywords:
        if kw in title or kw in (description or ""):
            condition_score = max(1, condition_score - 2)
            risk_signals.append(f"描述含'{kw}'")
            detail_parts.append(f"描述含'{kw}'")
    return condition_score


def _eval_no_images(
    image_urls: list[str],
    condition_score: int,
    risk_signals: list[str],
    detail_parts: list[str],
) -> int:
    """规则评估-无图片：风险信号 + 减分

    无图商品无法人工核验成色，规则评估也无法做图片分析，需扣分提示风险。
    """
    if not image_urls:
        risk_signals.append("无图片参考")
        condition_score = max(1, condition_score - 1)
        detail_parts.append("无商品图片")
    return condition_score


def _eval_low_price(
    price: float,
    title: str,
    condition_score: int,
    risk_signals: list[str],
    detail_parts: list[str],
) -> int:
    """规则评估-价格异常低：低于100元且非配件类视为可疑

    配件类（壳/膜/线/充/支架/贴）本身低价合理，排除避免误判。
    """
    if price < 100 and not any(kw in title for kw in ["壳", "膜", "线", "充", "支架", "贴"]):
        risk_signals.append("价格异常低")
        condition_score = max(1, condition_score - 1)
        detail_parts.append("价格低于100元")
    return condition_score


def _extract_price_range_stats(price_range: dict[str, Any] | None) -> dict[str, Any] | None:
    """提取并验证同类物品价格区间数据

    返回 None 表示数据无效（无区间或 bargain/median 关键字段缺失），
    让调用方跳过价格区间评估，避免在数据不足时误判。
    """
    if not price_range or price_range.get("sample_size", 0) <= 0:
        return None
    bargain_price = price_range.get("bargain_price") or 0
    median_price = price_range.get("median_price") or 0
    # bargain/median 为 0 时无法判断捡漏/性价比，视为数据无效
    if bargain_price <= 0 or median_price <= 0:
        return None
    return {
        "bargain_price": bargain_price,
        "median_price": median_price,
        "max_price": price_range.get("max_price") or 0,
        "sample_size": price_range.get("sample_size", 0),
        "source_label": price_range.get("source_label", price_range.get("source", "")),
    }


def _apply_price_range_eval(
    price: float,
    stats: dict[str, Any],
    condition_score: int,
    risk_signals: list[str],
    detail_parts: list[str],
) -> int:
    """根据价格区间统计判断当前价格合理性并更新评分/信号

    三档判断：低于捡漏价（提示机会，不加减分避免误判假货）/低于中位数85%（性价比良好）/高于最高价（减分）。
    """
    bargain_price = stats["bargain_price"]
    median_price = stats["median_price"]
    max_price = stats["max_price"]

    if price < bargain_price:
        # 低于最低价可能是真捡漏也可能是假货/问题机，不加减分让用户综合判断
        detail_parts.append(
            f"价格¥{price}低于同类最低价¥{bargain_price}（捡漏机会，样本{stats['sample_size']}）"
        )
    elif price < median_price * 0.85:
        detail_parts.append(
            f"价格¥{price}低于同类中位数¥{median_price}的85%（性价比良好）"
        )
    elif max_price > 0 and price > max_price:
        risk_signals.append(f"价格¥{price}高于同类最高价¥{max_price}")
        condition_score = max(1, condition_score - 1)
        detail_parts.append("价格高于同类最高价")
    detail_parts.append(f"价格参考来源：{stats['source_label']}")
    return condition_score


def _eval_price_range(
    price: float,
    price_range: dict[str, Any] | None,
    condition_score: int,
    risk_signals: list[str],
    detail_parts: list[str],
) -> int:
    """规则评估-基于同类物品价格区间判断价格合理性（捡漏价格参考）

    当有价格区间数据时，判断当前商品是否处于"捡漏"区间：
    - 低于捡漏价：可能是真捡漏也可能是假货，不加分不减分让用户综合判断
    - 中位数以下85%：性价比良好
    - 高于最高价：价格偏高，减分
    """
    stats = _extract_price_range_stats(price_range)
    if stats is None:
        return condition_score
    return _apply_price_range_eval(price, stats, condition_score, risk_signals, detail_parts)


def _rule_eval_condition(
    title: str,
    description: str,
    price: float,
    image_urls: list[str],
    price_range: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """规则模拟评估：无 LLM Key 时基于规则判断成色

    逻辑：
    - 价格低于市场价 70% → 谨慎（可能成色差或有风险）
    - 描述含"全新/未拆/仅拆"等 → 成色加分
    - 描述含"划痕/磕碰/维修/进水"等 → 成色减分
    - 无图片 → 风险信号
    - price_range 提供同类物品价格区间时，判断当前价格是否处于合理可拾区间

    各评估维度独立提取为子函数，condition_score 通过返回值传递（int 不可变），
    risk_signals / detail_parts 通过引用修改（list 可变）。
    """
    # 成色评分基准
    condition_score = 7  # 默认 7 分（闲鱼商品普遍 7 成新）
    risk_signals: list[str] = []
    detail_parts: list[str] = []

    condition_score = _eval_good_keywords(title, description, condition_score, detail_parts)
    condition_score = _eval_bad_keywords(title, description, condition_score, risk_signals, detail_parts)
    condition_score = _eval_no_images(image_urls, condition_score, risk_signals, detail_parts)
    condition_score = _eval_low_price(price, title, condition_score, risk_signals, detail_parts)
    condition_score = _eval_price_range(price, price_range, condition_score, risk_signals, detail_parts)

    # 判定
    verdict = "recommend" if condition_score >= 7 else "caution"
    reason = "规则模拟：成色良好" if verdict == "recommend" else "规则模拟：存在风险信号"

    return {
        "verdict": verdict,
        "condition_score": condition_score,
        "appearance_score": condition_score,  # 规则模式无法区分外观
        "consistency_score": 7,  # 规则模式默认一致性
        "price_reasonability": 7,
        "risk_signals": risk_signals,
        "reason": reason,
        "detail": "；".join(detail_parts) if detail_parts else "基于规则模拟评估，建议配置 LLM Key 获取更精准的 AI 成色分析",
    }


def _normalize_condition_result(raw: dict[str, Any], source: str) -> dict[str, Any]:
    """归一化成色评估结果，保证前端拿到的字段稳定"""
    verdict = str(raw.get("verdict") or "").strip().lower()
    if verdict not in ("recommend", "caution"):
        # 尝试从 condition_score 推断（处理 None 情况，避免 int(None) 报错）
        score = raw.get("condition_score")
        if score is None:
            score = 5
        verdict = "recommend" if int(score) >= 7 else "caution"

    condition_score = raw.get("condition_score")
    try:
        condition_score = max(1, min(10, int(condition_score)))
    except (TypeError, ValueError):
        condition_score = 5

    return {
        "verdict": verdict,
        "condition_score": condition_score,
        "appearance_score": _clamp_score(raw.get("appearance_score")),
        "consistency_score": _clamp_score(raw.get("consistency_score")),
        "price_reasonability": _clamp_score(raw.get("price_reasonability")),
        "risk_signals": [str(s) for s in (raw.get("risk_signals") or []) if str(s).strip()],
        "reason": str(raw.get("reason") or "").strip()[:100],
        "detail": str(raw.get("detail") or "").strip()[:300],
        "source": source,
    }


def _clamp_score(v: Any) -> int:
    """将评分限制在 1-10 范围内"""
    try:
        return max(1, min(10, int(v)))
    except (TypeError, ValueError):
        return 5


def _parse_image_urls(image_urls_raw: Any) -> list:
    """解析 image_urls 字段：items 表中可能是 JSON 字符串或列表

    闲鱼图片 URL 列表在 items 表存储为 JSON 字符串（SQLite 无原生数组类型），
    需统一转换为 list 供后续逻辑使用；解析失败回退为空列表避免阻断评估。
    """
    if isinstance(image_urls_raw, str):
        try:
            return json.loads(image_urls_raw)
        except (json.JSONDecodeError, TypeError):
            return []
    return image_urls_raw


def _parse_dim_scores(dim_scores_raw: Any) -> dict[str, Any]:
    """解析 dimension_scores 字段：可能为 JSON 字符串或 dict

    evaluations 表中 dimension_scores 列以 TEXT 存储 JSON 字符串，
    读取时需转换为 dict 才能进一步访问 ai_condition_eval 等子字段。
    """
    if isinstance(dim_scores_raw, str):
        try:
            return json.loads(dim_scores_raw)
        except (json.JSONDecodeError, TypeError):
            return {}
    return dim_scores_raw or {}


def _get_item_with_payload_fallback(
    container: Container, item_id: str
) -> dict[str, Any] | None:
    """获取商品信息：优先 items 表，无记录时从 eval 事件 payload 回退

    场景：实时搜索(live_links)或轻量评估生成的 eval.scored 事件
    商品未写入 items 表，但 payload 中有 item_title / item_price，
    需用 payload 字段构造伪 item dict，字段名对齐 items 表结构。
    """
    # 策略1：优先从 items 表查询（数据最完整，含 description 和 image_urls）
    item = container.repo.get_item(item_id)
    if not item:
        # 策略2：items 表无记录时，从评估事件 payload 回退
        payload = container.repo.get_eval_payload_by_item(item_id)
        if payload:
            # payload 不含 description/image_urls，LLM 仅基于标题+价格评估、无图走规则模拟
            item = {
                "id": item_id,
                "title": payload.get("item_title") or payload.get("title") or "",
                "price": payload.get("item_price") or payload.get("price") or 0,
                "description": "",
                "image_urls": [],
                "task_id": payload.get("task_id"),  # 从事件 payload 回退提取 task_id
            }
            logger.info(f"[F-06] items 表无记录，从 eval 事件 payload 回退: item_id={item_id}")
    return item


def _get_cached_ai_eval(
    existing_eval: dict[str, Any] | None, item_id: str
) -> dict[str, Any] | None:
    """从已有评估记录中提取缓存的 AI 成色评估结果

    缓存 key 存在 evaluations 表的 dimension_scores JSON 中的 ai_condition_eval 字段，
    命中时直接返回，避免重复调用 LLM。
    """
    if not existing_eval:
        return None
    dim_scores = _parse_dim_scores(existing_eval.get("dimension_scores"))
    cached_ai_eval = dim_scores.get("ai_condition_eval")
    if cached_ai_eval:
        logger.info(f"[F-06] 命中缓存: item_id={item_id}")
        return cached_ai_eval
    return None


def _query_price_range(
    task_id: str | None, item_id: str, container: Container
) -> dict[str, Any] | None:
    """查询同类物品已售价格区间（捡漏价格参考）

    价格区间作为 AI 评估 price_reasonability 维度的重要参考依据。
    策略：优先查近30天数据；若为空则回退到全部历史数据，确保有数据时总能提供参考。
    查询失败不阻断 AI 评估主流程（捕获所有异常并返回 None）。
    """
    if not task_id:
        return None
    try:
        from xianyu_hunter.web.routes.price_dashboard import sold_range as _sold_range
        price_range = _sold_range(
            task_id=task_id, range_days=30, container=container
        )
        # 近30天无数据时回退到全部历史数据，避免价格参考缺失
        if price_range.get("source") == "empty":
            price_range = _sold_range(
                task_id=task_id, range_days=0, container=container
            )
        logger.info(
            f"[F-06] 价格区间查询完成: item_id={item_id}, "
            f"task_id={task_id}, source={price_range.get('source')}, "
            f"sample_size={price_range.get('sample_size')}"
        )
        return price_range
    except Exception as e:  # noqa: BLE001
        # 价格区间查询失败不阻断 AI 评估主流程
        logger.warning(f"[F-06] 价格区间查询失败（不影响评估）: {e}")
        return None


async def _run_condition_eval(
    title: str,
    description: str,
    price: float,
    image_urls: list,
    price_range: dict[str, Any] | None,
    item_id: str,
) -> tuple[dict[str, Any], str]:
    """执行成色评估：有 Key 走 LLM Vision，无 Key 或失败降级规则模拟

    返回 (raw_result, source)：source 标识是 'llm' 还是 'rule'，
    供后续归一化和缓存区分数据来源。
    """
    settings = get_settings()
    used_source = "llm"
    raw_result: dict[str, Any] | None = None

    if settings.openai_api_key:
        try:
            raw_result = await _call_llm_vision(
                title, description, price, image_urls, price_range
            )
            logger.info(f"[F-06] LLM Vision 评估完成: item_id={item_id}")
        except RuntimeError as e:
            logger.warning(f"[F-06] LLM Vision 失败，降级规则模拟: {e}")
            raw_result = None
    else:
        used_source = "rule"

    # 降级到规则模拟
    if raw_result is None:
        raw_result = _rule_eval_condition(
            title, description, price, image_urls, price_range
        )
        used_source = "rule"
        logger.info(f"[F-06] 规则模拟评估完成: item_id={item_id}")

    return raw_result, used_source


def _cache_eval_result(
    existing_eval: dict[str, Any] | None,
    item_id: str,
    item: dict[str, Any],
    result: dict[str, Any],
    container: Container,
) -> None:
    """缓存评估结果到 evaluations 表

    已有记录则更新 dimension_scores（保留其他维度数据）；
    无记录则创建新评估（score 用 condition_score * 10 映射到 0-100）。
    缓存失败不影响返回结果（仅捕获可预期的数据/IO异常）。
    """
    try:
        if existing_eval:
            # 更新已有评估记录的 dimension_scores
            dim_scores = _parse_dim_scores(existing_eval.get("dimension_scores"))
            dim_scores["ai_condition_eval"] = result
            # 通过 Repository 方法更新 dimension_scores 字段
            container.repo.update_evaluation_dimension_scores(
                existing_eval["id"], dim_scores
            )
        else:
            # 创建新的评估记录（仅 AI 成色评估，score 用 condition_score * 10 映射到 0-100）
            eval_data = {
                "item_id": item_id,
                "seller_id": item.get("seller_id"),
                "score": result["condition_score"] * 10,
                "risk_level": "low" if result["verdict"] == "recommend" else "medium",
                "dimension_scores": json.dumps(
                    {"ai_condition_eval": result}, ensure_ascii=False
                ),
                "reject_reasons": json.dumps(
                    result["risk_signals"], ensure_ascii=False
                ) if result["risk_signals"] else None,
                "created_at": _utcnow(),
            }
            container.repo.save_evaluation(eval_data)
        logger.info(f"[F-06] 评估结果已缓存: item_id={item_id}")
    except (RuntimeError, ValueError, KeyError, OSError) as e:
        # 缓存失败不影响返回结果（仅捕获可预期的数据/IO异常）
        logger.warning(f"[F-06] 缓存评估结果失败（不影响返回）: {e}")


@router.post("/evaluate-condition")
async def evaluate_condition(
    body: ConditionEvalRequest,
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    """F-06 AI 多模态成色评估

    流程：
    1. 从 items 表获取商品信息（标题/描述/价格/图片URL）
    2. 检查是否有缓存的评估结果
    3. 调用 LLM Vision API 分析商品图片 + 描述（有 Key 时）
       或走规则模拟评估（无 Key 时）
    4. 缓存评估结果到 evaluations 表
    5. 返回评估结果：推荐/不推荐 + 理由 + 成色评分
    """
    _check_ai_enabled()
    # 1. 获取商品信息（含 payload 回退）
    item = _get_item_with_payload_fallback(container, body.item_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"商品 {body.item_id} 不存在")

    title = item.get("title", "")
    description = item.get("description", "")
    price = float(item.get("price", 0))
    image_urls = _parse_image_urls(item.get("image_urls") or [])

    # 2. 检查缓存：命中则直接返回，避免重复 LLM 调用
    existing_eval = container.repo.get_latest_evaluation(body.item_id)
    cached_eval = _get_cached_ai_eval(existing_eval, body.item_id)
    if cached_eval:
        return {**cached_eval, "cached": True}

    # 2.5 查询同类物品已售价格区间（捡漏价格参考）
    price_range = _query_price_range(item.get("task_id"), body.item_id, container)

    # 3. 调用 LLM Vision 或规则模拟
    raw_result, used_source = await _run_condition_eval(
        title, description, price, image_urls, price_range, body.item_id
    )

    # 4. 归一化结果
    result = _normalize_condition_result(raw_result, used_source)

    # 附带价格区间信息到返回结果（供前端展示捡漏价格参考）
    if price_range and price_range.get("sample_size", 0) > 0:
        result["price_range"] = price_range

    # 5. 缓存到 evaluations 表
    _cache_eval_result(existing_eval, body.item_id, item, result, container)

    return {**result, "cached": False}


# ============== AI 配置 API ==============

class AIConfigBody(BaseModel):
    """AI 配置更新请求"""
    ai_enabled: bool | None = None
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    vision_model: str | None = None
    # Embedding 配置（独立于 LLM，DeepSeek 等厂商不支持 /embeddings 时需单独配置）
    embedding_base_url: str | None = None
    embedding_api_key: str | None = None
    embedding_model: str | None = None
    embedding_dimensions: int | None = None


def _mask_key(key: str) -> str:
    """API Key 脱敏：仅保留末 4 位"""
    if not key:
        return ""
    return "****" + key[-4:] if len(key) > 4 else "****"


@router.get("/config")
def get_ai_config() -> dict[str, Any]:
    """获取当前 AI 配置（API Key 脱敏显示）

    返回 LLM 和 Embedding 两组配置。Embedding 留空时前端应提示
    "未配置则复用 LLM 设置"，避免用户误以为配置丢失。
    """
    settings = get_settings()
    return {
        "ai_enabled": settings.ai_enabled,
        "base_url": settings.openai_base_url,
        "api_key": _mask_key(settings.openai_api_key),
        "model": settings.openai_model,
        "vision_model": settings.openai_vision_model,
        "has_key": bool(settings.openai_api_key),
        # Embedding 配置：留空表示 fallback 到 LLM（向后兼容）
        "embedding_base_url": settings.embedding_base_url,
        "embedding_api_key": _mask_key(settings.embedding_api_key),
        "embedding_model": settings.embedding_model,
        "embedding_dimensions": settings.embedding_dimensions,
        "embedding_has_key": bool(settings.embedding_api_key),
    }


@router.put("/config")
def save_ai_config(body: AIConfigBody) -> dict[str, Any]:
    """保存 AI 配置（热更新，无需重启服务）

    API Key 通过 keyring 安全存储，其余配置写入 .env。
    embedding_* 字段全为 None 时跳过更新（前端只改 LLM 部分时不影响 embedding）。
    """
    # API Key 特殊处理：空字符串表示清除，"****xxxx" 表示未修改
    api_key = body.api_key
    if api_key is not None:
        # 前端回传的脱敏值（****开头）表示未修改，跳过
        if api_key.startswith("****"):
            api_key = None
        elif api_key == "":
            # 清除 API Key
            from xianyu_hunter.infra import secrets as sec
            sec.delete_secret(sec.KEY_OPENAI_API_KEY)
            api_key = ""  # 写入 .env 为空

    # Embedding API Key 同样处理：脱敏值跳过，空字符串清除
    emb_api_key = body.embedding_api_key
    if emb_api_key is not None:
        if emb_api_key.startswith("****"):
            emb_api_key = None
        elif emb_api_key == "":
            from xianyu_hunter.infra import secrets as sec
            sec.delete_secret(sec.KEY_EMBEDDING_API_KEY)
            emb_api_key = ""

    update_ai_config(
        ai_enabled=body.ai_enabled,
        base_url=body.base_url,
        api_key=api_key,
        model=body.model,
        vision_model=body.vision_model,
        embedding_base_url=body.embedding_base_url,
        embedding_api_key=emb_api_key,
        embedding_model=body.embedding_model,
        embedding_dimensions=body.embedding_dimensions,
    )

    logger.info("[AI Config] 配置已更新（热更新，无需重启）")
    return {"ok": True, "message": "AI 配置已保存并即时生效"}


@router.post("/test-connection")
def test_ai_connection() -> dict[str, Any]:
    """测试 AI 服务连接

    发送一个最小化请求验证 API Key 和端点是否可用。
    """
    _check_ai_enabled()
    settings = get_settings()
    if not settings.openai_api_key:
        return {"ok": False, "detail": "未配置 API Key"}

    url = settings.openai_base_url.rstrip("/") + CHAT_COMPLETIONS_PATH
    payload = {
        "model": settings.openai_model,
        "messages": [{"role": "user", "content": "Hi"}],
        "max_tokens": 5,
    }
    headers = {
        "Authorization": AUTH_BEARER_PREFIX + settings.openai_api_key,
        "Content-Type": CONTENT_TYPE_JSON,
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.post(url, json=payload, headers=headers)
    except httpx.TimeoutException:
        return {"ok": False, "detail": "连接超时（>15s），请检查网络或 API 地址"}
    except httpx.HTTPError as e:
        return {"ok": False, "detail": f"网络错误: {e}"}

    if r.status_code == 200:
        try:
            data = r.json()
            model_used = data.get("model", settings.openai_model)
            # 记录测试连接的用量
            record_usage("test_connection", settings.openai_model, data)
            return {"ok": True, "model": model_used}
        except Exception:
            record_usage("test_connection", settings.openai_model)
            return {"ok": True, "model": settings.openai_model}
    else:
        snippet = r.text[:200]
        return {"ok": False, "detail": f"API 返回 {r.status_code}: {snippet}"}


def _test_local_embedding(model: str) -> dict[str, Any]:
    """本地模式 embedding 连接测试：调用 sentence-transformers

    首次调用会触发模型下载（约 95MB for bge-small-zh-v1.5），可能耗时较久。
    ImportError 单独捕获：sentence-transformers 未装时给出明确的安装提示，
    而非笼统的"加载失败"。
    """
    try:
        from xianyu_hunter.modules.chatbot.local_embedding import LocalEmbeddingBackend
        backend = LocalEmbeddingBackend(model)
        vec = backend.embed("test")
        return {
            "ok": True,
            "model": model,
            "dimensions": len(vec),
        }
    except ImportError as e:
        return {
            "ok": False,
            "detail": f"sentence-transformers 未安装: {e}",
        }
    except Exception as e:
        return {
            "ok": False,
            "detail": f"本地 embedding 加载失败: {type(e).__name__}: {e}",
        }


def _test_remote_embedding(
    settings: Any, base_url: str, model: str
) -> dict[str, Any]:
    """远程模式 embedding 连接测试：OpenAI 兼容 /v1/embeddings 协议

    embedding 端点可能与 LLM 端点完全不同（如本地 Ollama），
    API Key 缺失时先兜底用 openai_api_key，两者都空才报错。
    dimensions=0 时不传该参数：Ollama 等本地模型不接受 dimensions 字段。
    """
    api_key = settings.embedding_api_key or settings.openai_api_key
    if not api_key:
        return {"ok": False, "detail": "未配置 API Key（embedding 与 LLM 均为空）"}

    url = base_url.rstrip("/") + "/embeddings"
    payload: dict[str, Any] = {"model": model, "input": "test"}
    # dimensions=0 表示由模型决定（Ollama 等本地模型不接受该参数）
    if settings.embedding_dimensions > 0:
        payload["dimensions"] = settings.embedding_dimensions
    headers = {
        "Authorization": AUTH_BEARER_PREFIX + api_key,
        "Content-Type": CONTENT_TYPE_JSON,
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.post(url, json=payload, headers=headers)
    except httpx.TimeoutException:
        return {"ok": False, "detail": "连接超时（>15s），请检查 embedding 服务是否运行"}
    except httpx.HTTPError as e:
        return {"ok": False, "detail": f"网络错误: {e}"}

    if r.status_code == 200:
        try:
            data = r.json()
            vec = data["data"][0]["embedding"]
            return {
                "ok": True,
                "model": data.get("model", model),
                "dimensions": len(vec),
            }
        except (KeyError, IndexError) as e:
            return {"ok": False, "detail": f"响应格式异常: {e}"}
    else:
        snippet = r.text[:200]
        return {"ok": False, "detail": f"API 返回 {r.status_code}: {snippet}"}


@router.post("/test-embedding")
def test_embedding_connection() -> dict[str, Any]:
    """测试 Embedding 服务连接

    发送一个最小化 embedding 请求验证端点和模型是否可用。
    与 LLM 测试分离：embedding 端点可能完全不同（如本地 Ollama）。

    支持两种 backend：
    - 本地：EMBEDDING_BASE_URL 为空或 "local"，调用 sentence-transformers
    - 远程：OpenAI 兼容 /v1/embeddings 协议
    """
    settings = get_settings()
    base_url = (settings.embedding_base_url or "").strip()
    # 与 container.py 的 fallback 逻辑保持一致：settings 优先，空时读 cfg.kb
    # 避免硬编码 "text-embedding-3-small" 导致本地模式加载错误模型
    from xianyu_hunter.infra.yaml_config import get_config
    cfg = get_config()
    model = settings.embedding_model or cfg.kb.embedding_model
    # 本地模式：直接调用 LocalEmbeddingBackend
    if not base_url or base_url.lower() == "local":
        return _test_local_embedding(model)
    # 远程模式：OpenAI 兼容 /v1/embeddings 协议
    return _test_remote_embedding(settings, base_url, model)


# ============== 用量统计 API ==============

class BudgetBody(BaseModel):
    daily_token_limit: int | None = None
    daily_cost_limit_usd: float | None = None
    rate_limit_per_min: int | None = None


@router.get("/usage")
def get_ai_usage() -> dict[str, Any]:
    """获取今日 AI 用量汇总 + 最近 7 天趋势"""
    from xianyu_hunter.infra.ai_usage import get_budget_config, get_daily_summary, get_recent_usage

    summary = get_daily_summary()
    budget = get_budget_config()
    history = get_recent_usage(7)

    return {
        "today": {
            "date": summary.date,
            "total_calls": summary.total_calls,
            "total_input_tokens": summary.total_input_tokens,
            "total_output_tokens": summary.total_output_tokens,
            "total_tokens": summary.total_input_tokens + summary.total_output_tokens,
            "total_cost_usd": round(summary.total_cost_usd, 4),
            "total_cost_cny": round(summary.total_cost_usd * 7.2, 2),
            "by_endpoint": summary.by_endpoint,
            "by_model": summary.by_model,
        },
        "budget": {
            "daily_token_limit": budget.daily_token_limit,
            "daily_cost_limit_usd": budget.daily_cost_limit_usd,
            "rate_limit_per_min": budget.rate_limit_per_min,
            "token_usage_pct": round(
                (summary.total_input_tokens + summary.total_output_tokens)
                / budget.daily_token_limit * 100, 1
            ) if budget.daily_token_limit > 0 else 0,
            "cost_usage_pct": round(
                summary.total_cost_usd / budget.daily_cost_limit_usd * 100, 1
            ) if budget.daily_cost_limit_usd > 0 else 0,
        },
        "history": history,
    }


@router.put("/budget")
def update_ai_budget(body: BudgetBody) -> dict[str, Any]:
    """更新 AI 预算配置"""
    from xianyu_hunter.infra.ai_usage import update_budget as _update_budget

    _update_budget(
        daily_token_limit=body.daily_token_limit,
        daily_cost_limit_usd=body.daily_cost_limit_usd,
        rate_limit_per_min=body.rate_limit_per_min,
    )
    logger.info("[AI Budget] 预算配置已更新")
    return {"ok": True, "message": "预算配置已更新"}
