"""安全清洗器：封装 Prompt Injection 检测与脱敏操作

供 API 入口、转人工模块、LLM 调用前置处理等场景调用，
确保不同应用点使用一致的安全规则（详见详细设计 §5.13.4 应用点表）。

职责边界：
- 本模块仅做正则匹配与替换，不涉及业务逻辑判定
- 拒绝服务还是仅告警由调用方根据返回值决定
"""
from __future__ import annotations

import copy

from xianyu_hunter.modules.chatbot.security.patterns import (
    PII_PATTERNS,
    PROMPT_INJECTION_PATTERNS,
    SENSITIVE_PATTERNS,
)


def detect_prompt_injection(text: str) -> tuple[bool, str | None]:
    """检测文本是否包含 Prompt Injection 攻击。

    遍历所有规则，命中任意一条即返回，避免不必要的全量扫描。

    Returns:
        (是否检测到注入, 命中的规则名)；未命中则返回 (False, None)
    """
    for rule_name, pattern in PROMPT_INJECTION_PATTERNS:
        if pattern.search(text):
            return True, rule_name
    return False, None


def redact_sensitive(text: str) -> str:
    """脱敏敏感字段（API Key / Token / Cookie / 私钥 等）。

    按规则顺序逐条替换，确保所有已知敏感模式都被覆盖。
    替换文本保留类型前缀，便于人工识别脱敏位置。
    """
    for _name, pattern, replacement in SENSITIVE_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def redact_pii(text: str) -> str:
    """脱敏 PII（手机号 / 邮箱 / 身份证 / 银行卡 等）。

    替换器统一通过 re.sub 调用，str 与 callable 均可正常工作。
    """
    for _name, pattern, replacement in PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def sanitize_session_for_copy(session_data: dict) -> dict:
    """对会话数据做完整脱敏，用于转人工时复制到剪贴板。

    仅对 messages 中每条消息的 content 应用敏感字段 + PII 脱敏，
    保留 sources / tool_calls 等元数据以便人工排查上下文。
    返回深拷贝以避免污染原始会话状态（调用方可能继续使用原数据）。
    """
    sanitized = copy.deepcopy(session_data)
    messages = sanitized.get("messages")
    # 仅在 messages 为列表时处理，避免空会话或异常数据结构报错
    if isinstance(messages, list):
        for msg in messages:
            # 仅对 dict 型消息且 content 为字符串时脱敏，跳过 tool/function 等结构化消息
            if isinstance(msg, dict) and isinstance(msg.get("content"), str):
                content = msg["content"]
                content = redact_sensitive(content)
                content = redact_pii(content)
                msg["content"] = content
    return sanitized


def check_user_input_safety(text: str) -> tuple[bool, str | None]:
    """检查用户输入是否安全（Prompt Injection 检测）。

    安全语义与 detect_prompt_injection 相反：未检测到注入即为安全。

    Returns:
        (是否安全, 不安全的规则名)；安全则返回 (True, None)
    """
    injected, rule_name = detect_prompt_injection(text)
    if injected:
        return False, rule_name
    return True, None


def sanitize_for_llm(text: str) -> str:
    """对送入 LLM 的文本做敏感字段脱敏。

    仅脱敏凭据类敏感字段，不脱敏 PII——
    因为 LLM 需要理解用户问题中的联系方式等信息以正确响应（如转人工场景）。
    """
    return redact_sensitive(text)
