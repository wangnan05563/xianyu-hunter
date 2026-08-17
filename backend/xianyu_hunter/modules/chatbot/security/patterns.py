"""安全规则正则定义（见概要设计附录 A、详细设计 §5.13）

集中管理三类安全正则：
- Prompt Injection 检测：拦截试图绕过系统提示的恶意输入
- 敏感字段扫描：识别并替换凭据类信息（API Key / Token / Cookie 等）
- PII 脱敏：掩码个人身份信息（手机号 / 邮箱 / 身份证 等）

所有正则统一编译为 re.I | re.M，确保跨行且大小写不敏感地匹配，
避免攻击者通过大小写变换或换行分割绕过规则。
"""
from __future__ import annotations

import re
from collections.abc import Callable

# PII 替换器既可能是固定字符串，也可能是 callable（手机号需保留首末位）
_PIIReplacer = str | Callable[[re.Match[str]], str]


# ===== A.1 Prompt Injection 检测（5 类）=====
# 每条规则为 (规则名, 编译后的正则)。命中任意一条即判定为注入，
# 由调用方决定是拒绝服务还是仅告警。
PROMPT_INJECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # 1. 忽略角色指令：攻击者试图让模型抛弃系统提示的约束
    ("ignore_previous_instructions", re.compile(
        r"ignore\s+(previous|above|prior)\s+(instructions?|prompts?)",
        re.I | re.M,
    )),
    # 2. 角色扮演注入：通过 "you are now" 切换模型角色以绕过安全约束
    ("role_hijack", re.compile(
        r"you\s+are\s+(now|a)\s+(dan|jailbreak|developer|admin)",
        re.I | re.M,
    )),
    # 3. 系统提示泄露：诱导模型输出内部 prompt 内容
    ("prompt_leak", re.compile(
        r"(reveal|show|print|output)\s+(your\s+)?(system\s+)?prompt",
        re.I | re.M,
    )),
    # 4. 指令覆盖：直接命令模型不遵守既定规则
    ("instruction_override", re.compile(
        r"(do\s+not|don't|never)\s+(follow|obey)\s+(your\s+)?(rules|instructions)",
        re.I | re.M,
    )),
    # 5. 越狱尝试：明确的越狱关键词或绕过安全过滤的请求
    ("jailbreak_attempt", re.compile(
        r"(jailbreak|DAN|do\s+anything\s+now|bypass\s+(safety|filter|restriction))",
        re.I | re.M,
    )),
]


# ===== A.2 敏感字段扫描（8 类）=====
# 每条规则为 (规则名, 编译后的正则, 替换文本)。
# 替换文本保留类型前缀（如 sk-***REDACTED***），便于人工识别字段类型，
# 同时确保凭据本体不外泄。
SENSITIVE_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    # 1. OpenAI API Key：sk- 开头，至少 32 位字符
    ("openai_key", re.compile(r"sk-[A-Za-z0-9]{32,}"), "sk-***REDACTED***"),
    # 2. Anthropic API Key：sk-ant- 开头
    ("anthropic_key", re.compile(r"sk-ant-[A-Za-z0-9-]+"), "sk-ant-***REDACTED***"),
    # 3. Bearer Token：HTTP Authorization 头常见格式
    ("bearer_token", re.compile(r"Bearer\s+[A-Za-z0-9._-]+"), "Bearer ***REDACTED***"),
    # 4. JWT：三段式 header.payload.signature，均以 eyJ 开头
    ("jwt", re.compile(
        r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"),
        "***JWT_REDACTED***",
    ),
    # 5. Cookie：HTTP Cookie / Set-Cookie 头，大小写不敏感
    ("cookie", re.compile(r"(cookie|set-cookie)[:\s=]+[^\s;]+", re.I),
     "cookie=***REDACTED***"),
    # 6. 阿里云 AccessKey：LTAI 开头，至少 12 位
    ("aliyun_ak", re.compile(r"LTAI[A-Za-z0-9]{12,}"), "LTAI***REDACTED***"),
    # 7. 数据库连接串：含凭据的 URL，避免账号密码泄露
    ("db_url", re.compile(r"(mongodb|postgres|mysql|redis)://[^\s]+", re.I),
     "***DB_URL_REDACTED***"),
    # 8. 私钥：PEM 格式头部，命中即替换为占位符
    ("private_key", re.compile(r"-----BEGIN\s+(RSA|EC|OPENSSH|PRIVATE)\s+KEY-----"),
     "***PRIVATE_KEY_REDACTED***"),
]


# ===== A.3 PII 脱敏（6 类）=====
# 每条规则为 (规则名, 编译后的正则, 替换器)。
# 替换器统一通过 re.sub 调用，故 str 与 callable 均可。
PII_PATTERNS: list[tuple[str, re.Pattern[str], _PIIReplacer]] = [
    # 1. 手机号：保留前 1 后 4，中间用 4 个 * 填充，兼顾可识别性与隐私
    ("phone", re.compile(r"1[3-9]\d{9}"),
     lambda m: m.group()[0] + "****" + m.group()[-4:]),
    # 2. 邮箱：本地名与域名均脱敏，防止社工攻击与撞库
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
     "***@***.***"),
    # 3. 身份证：18 位统一替换为星号，避免校验位泄露地区信息
    ("id_card", re.compile(r"\d{17}[\dXx]"),
     "******************"),
    # 4. 银行卡：16-19 位，统一掩码为 4 段格式
    ("bank_card", re.compile(r"\d{16,19}"),
     "**** **** **** ****"),
    # 5. 微信号：保留前缀便于识别字段类型，账号本体脱敏
    ("wechat", re.compile(r"[Ww]echat[:\s]*[A-Za-z0-9_-]{6,}"),
     "WeChat: ***REDACTED***"),
    # 6. QQ号：保留前缀便于识别字段类型，号码本体脱敏
    ("qq", re.compile(r"[Qq][Qq][:\s]*\d{5,}"),
     "QQ: ***REDACTED***"),
]
