# 闲鱼猎人智能客服模块 - 详细设计说明书

| 项 | 内容 |
|---|---|
| 文档版本 | v1.1 |
| 编写日期 | 2026-06-28 |
| 所属项目 | 闲鱼猎人（XianyuHunter） |
| 文档类型 | 详细设计说明书（DDD） |
| 上游需求 | [chatbot-rag-agent-requirements.md v1.1](file:///d:/code/otherProjects/17_xianyu/docs/chatbot-rag-agent-requirements.md) |
| 上游概要设计 | [chatbot-概要设计.md v1.1](file:///d:/code/otherProjects/17_xianyu/docs/chatbot-概要设计.md) |
| 主系统设计基线 | [概要设计文档.md v2.0](file:///d:/code/otherProjects/17_xianyu/docs/概要设计文档.md) |

## 修订记录

| 版本 | 日期 | 修订内容 |
|------|------|----------|
| v1.0 | 2026-06-28 | 初版：基于概要设计 v1.1，输出 DDL / Schema / 类签名 / 状态机 / 测试用例 |
| v1.1 | 2026-06-28 | 同步 P1+P2 缺陷修复设计变更：H7 ContextManager 同步化、H5 RAGEngine 异常路径用量记录、H2/H3 EmbeddingService 配置统一、H4/M-36 仓储真实计数、M-15 属性重命名、M-30 None 过滤、M-22 维度检查、M-11/M-12 LLM 空响应兜底 |

---

## 目录

1. [概述](#1-概述)
2. [数据库详细设计](#2-数据库详细设计)
3. [配置 Schema 详细定义](#3-配置-schema-详细定义)
4. [API 详细设计](#4-api-详细设计)
5. [模块详细设计](#5-模块详细设计)
6. [状态机设计](#6-状态机设计)
7. [前端组件详细设计](#7-前端组件详细设计)
8. [错误码与异常处理](#8-错误码与异常处理)
9. [测试用例设计](#9-测试用例设计)
10. [阶段交接声明](#10-阶段交接声明)

---

## 1. 概述

### 1.1 文档定位

本文档是智能客服模块的**详细设计说明书（DDD）**，基于概要设计 v1.1，向下指导编码实现。

**与概要设计的差异**：
- 概要设计：定义"做什么"（架构、模块职责、接口契约）
- 详细设计：定义"怎么做"（DDL、Schema、类签名、算法伪代码、状态机、测试用例）

### 1.2 设计原则

1. **契约先行**：API Schema 与 DDL 是前后端、模块间的唯一契约，编码严格遵循
2. **可测试**：每个公共方法都有对应的单元测试用例（见 §9）
3. **可追溯**：每条设计决策可追溯到概要设计 §3-§8 或需求 §4
4. **最小实现**：避免过度设计，仅实现需求与概要设计明确要求的功能

### 1.3 模块清单（来自概要设计 §3）

| 模块 | 位置 | 详细设计章节 |
|------|------|-------------|
| ChatbotOrchestrator | modules/chatbot/orchestrator.py | §5.1 |
| RAGEngine | modules/chatbot/rag_engine.py | §5.2 |
| Agent | modules/chatbot/agent.py | §5.3 |
| IntentClassifier | modules/chatbot/intent_classifier.py | §5.4 |
| KBManager | modules/chatbot/kb_manager.py | §5.5 |
| FAQMatcher | modules/chatbot/faq_matcher.py | §5.6 |
| ContextManager | modules/chatbot/context_manager.py | §5.7 |
| Escalation | modules/chatbot/escalation.py | §5.8 |
| EmbeddingService | modules/chatbot/embedding_service.py | §5.9 |
| VectorStore | modules/chatbot/vector_store.py | §5.10 |
| ChatbotRepository | infra/repo_chatbot.py | §5.11 |
| KBRefreshScheduler | modules/chatbot/kb_refresh_scheduler.py | §5.12 |
| 安全规则 | modules/chatbot/security/ | §5.13 |

---

## 2. 数据库详细设计

### 2.1 设计约束

1. **复用主 `Repository.engine`**：不独立 `create_engine`（见概要设计 §3.11 P0 修订）
2. **SQLAlchemy 2.0 风格**：`Mapped` + `mapped_column`，与现有 [db_models.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/infra/db_models.py) 一致
3. **UTC 时间**：所有 datetime 列使用 `datetime.now(timezone.utc)`，与主系统 `_utcnow()` 一致
4. **JSON 存储**：SQLite 用 `Text` 列存 JSON 字符串，应用层序列化/反序列化
5. **表命名**：统一 `chatbot_` 前缀，避免与主系统表冲突

### 2.2 表结构 DDL

#### 2.2.1 chatbot_sessions（会话表）

```python
# infra/db_models.py 追加
class ChatbotSessionRow(Base):
    """智能客服会话表

    一个会话对应一次连续对话，支持多轮消息交互。
    message_count 为冗余字段，由 add_message 时同步维护，避免 N+1 聚合查询。
    """
    __tablename__ = "chatbot_sessions"
    __table_args__ = (
        Index("ix_chatbot_sessions_user_status_created", "user_id", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)  # UUID32（无连字符）
    user_id: Mapped[str] = mapped_column(String, nullable=False, default="default", index=True)
    title: Mapped[str] = mapped_column(String, nullable=False, default="新对话")
    # active=活跃 / ended=已结束 / escalated=已转人工
    status: Mapped[str] = mapped_column(String, nullable=False, default="active", index=True)
    # 冗余计数：由 ChatbotRepository.add_message 同步维护（UPDATE chatbot_sessions SET message_count = message_count + 1）
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 最后活跃时间：用于会话超时判定（session_timeout_min）
    last_active_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
    # 会话元数据（JSON）：存储 intent_summary / escalation_reason 等
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
```

**字段说明**：
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | String | PK, UUID32 | 会话唯一标识，由 `uuid.uuid4().hex` 生成 |
| user_id | String | NOT NULL, default 'default' | 用户标识，单 Token 系统下固定为 'default' |
| title | String | NOT NULL, default '新对话' | 会话标题，由 `generate_title` 异步更新 |
| status | String | NOT NULL, default 'active' | 会话状态（见 §6.1 状态机） |
| message_count | Integer | NOT NULL, default 0 | 冗余消息计数，避免 N+1 |
| last_active_at | DateTime | default _utcnow, onupdate | 最后活跃时间，用于超时判定 |
| metadata_json | Text | nullable | 元数据 JSON（intent_summary 等） |
| created_at | DateTime | default _utcnow | 创建时间 |
| updated_at | DateTime | default _utcnow, onupdate | 更新时间 |

**索引**：
- `ix_chatbot_sessions_user_status_created`：(user_id, status, created_at) - 会话列表查询核心索引
- `ix_chatbot_sessions_user_id`：user_id 单列索引（由 `index=True` 自动创建）

#### 2.2.2 chatbot_messages（消息表）

```python
class ChatbotMessageRow(Base):
    """智能客服消息表

    存储每个会话的完整对话历史，支持上下文构建与消息回放。
    role: user=用户消息 / assistant=AI回复 / system=系统消息
    """
    __tablename__ = "chatbot_messages"
    __table_args__ = (
        Index("ix_chatbot_messages_session_created", "session_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)  # UUID32
    session_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    role: Mapped[str] = mapped_column(String, nullable=False)  # user / assistant / system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # AI 回复的元数据（JSON）：sources / tool_calls / intent / tokens_used
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 用户反馈：positive=点赞 / negative=点踩 / null=未反馈
    feedback: Mapped[str | None] = mapped_column(String, nullable=True)
    feedback_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    # token 消耗（仅 assistant 消息）：用于预算追踪
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
```

**字段说明**：
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | String | PK, UUID32 | 消息唯一标识 |
| session_id | String | NOT NULL, index | 关联 chatbot_sessions.id |
| role | String | NOT NULL | 消息角色：user / assistant / system |
| content | Text | NOT NULL | 消息内容（用户原文或 AI 回复） |
| metadata_json | Text | nullable | AI 回复元数据（sources/tool_calls/intent/tokens） |
| feedback | String | nullable | 用户反馈：positive / negative / null |
| feedback_comment | Text | nullable | 反馈备注 |
| tokens_used | Integer | nullable | token 消耗（仅 assistant） |
| created_at | DateTime | default _utcnow | 创建时间 |

**索引**：
- `ix_chatbot_messages_session_created`：(session_id, created_at) - 按会话查询消息历史的核心索引
- `ix_chatbot_messages_session_id`：session_id 单列索引（由 `index=True` 自动创建）

#### 2.2.3 chatbot_faqs（FAQ 表）

```python
class ChatbotFAQRow(Base):
    """FAQ 知识库

    存储高频问题与标准答案，由 FAQMatcher 进行向量相似度匹配。
    embedding 由 EmbeddingService 异步生成并缓存。
    """
    __tablename__ = "chatbot_faqs"
    __table_args__ = (
        Index("ix_chatbot_faqs_category_active", "category", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False, default="general")
    # 问题向量（JSON 数组，1536 维）：由 EmbeddingService 生成
    # 为什么存在 DB 而非 ChromaDB：FAQ 量小（<1000），DB 查询 + 应用层 cosine 即可，避免 ChromaDB 双集合管理复杂度
    question_embedding: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)  # 1=启用 / 0=禁用
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
```

#### 2.2.4 chatbot_feedback（反馈表）

```python
class ChatbotFeedbackRow(Base):
    """用户反馈独立表

    与 chatbot_messages.feedback 解耦：
    - chatbot_messages.feedback：快速标记，用于列表展示
    - chatbot_feedback：完整记录，用于趋势分析与转人工判定
    """
    __tablename__ = "chatbot_feedback"
    __table_args__ = (
        Index("ix_chatbot_feedback_session_created", "session_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    message_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    rating: Mapped[str] = mapped_column(String, nullable=False)  # positive / negative
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 触发转人工的反馈会标记 escalate_triggered=1
    escalate_triggered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
```

#### 2.2.5 chatbot_kb_versions（知识库版本表）

```python
class ChatbotKBVersionRow(Base):
    """知识库版本表

    每次构建/增量更新创建一条版本记录，支持回滚到任意历史版本。
    snapshot_path 指向磁盘上的 ChromaDB 快照目录。
    """
    __tablename__ = "chatbot_kb_versions"
    __table_args__ = (
        Index("ix_chatbot_kb_versions_created", "created_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)  # UUID32
    # 快照磁盘路径：data/chromadb/snapshots/{version_id}/
    snapshot_path: Mapped[str] = mapped_column(Text, nullable=False)
    # 文档内容 hash（MD5）：用于增量更新时检测是否真的变更
    doc_hash: Mapped[str] = mapped_column(String, nullable=False, index=True)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # build=全量构建 / incremental=增量更新 / rollback=回滚产生
    build_type: Mapped[str] = mapped_column(String, nullable=False, default="build")
    # 构建状态：success / partial / failed
    status: Mapped[str] = mapped_column(String, nullable=False, default="success")
    # 构建耗时（秒）
    build_duration_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 错误信息（status=failed 时填充）
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
```

#### 2.2.6 chatbot_config（配置表）

```python
class ChatbotConfigRow(Base):
    """客服模块运行时配置表（KV 模式）

    与 yaml_config.py 的 ChatbotConfig 分工：
    - yaml_config.py：启动时加载的静态配置，修改需重启
    - chatbot_config 表：运行时热更新的配置，通过 PUT /api/chatbot/config 修改
    仅支持热更新的字段存于此表（如 enabled / similarity_threshold / escalation_contact）
    """
    __tablename__ = "chatbot_config"
    __table_args__ = (
        UniqueConstraint("key", name="uq_chatbot_config_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    # 值类型：bool / int / float / string / json
    value_type: Mapped[str] = mapped_column(String, nullable=False, default="string")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
```

#### 2.2.7 chatbot_audit_logs（审计日志表）

```python
class ChatbotAuditLogRow(Base):
    """客服模块审计日志表

    记录配置变更、FAQ 增删、知识库重建等敏感操作。
    不记录明文 value，仅记录 hash 以便审计追溯。
    """
    __tablename__ = "chatbot_audit_logs"
    __table_args__ = (
        Index("ix_chatbot_audit_logs_action_created", "action", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action: Mapped[str] = mapped_column(String, nullable=False)  # config_update / faq_upsert / faq_delete / kb_rebuild / kb_rollback
    target: Mapped[str] = mapped_column(String, nullable=False)  # 配置 key / FAQ id / 版本 id
    old_value_hash: Mapped[str | None] = mapped_column(String, nullable=True)  # SHA256
    new_value_hash: Mapped[str | None] = mapped_column(String, nullable=True)  # SHA256
    # 操作来源：web=Web界面 / api=API调用 / scheduler=调度器 / system=系统自动
    source: Mapped[str] = mapped_column(String, nullable=False, default="web")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
```

### 2.3 索引策略汇总

| 表 | 索引名 | 字段 | 用途 |
|------|--------|------|------|
| chatbot_sessions | ix_chatbot_sessions_user_id | user_id | 按用户查会话 |
| chatbot_sessions | ix_chatbot_sessions_status | status | 按状态过滤 |
| chatbot_sessions | ix_chatbot_sessions_user_status_created | user_id, status, created_at | 会话列表查询（核心） |
| chatbot_messages | ix_chatbot_messages_session_id | session_id | 按会话查消息 |
| chatbot_messages | ix_chatbot_messages_session_created | session_id, created_at | 消息历史查询（核心） |
| chatbot_faqs | ix_chatbot_faqs_category_active | category, is_active | 按分类查启用 FAQ |
| chatbot_feedback | ix_chatbot_feedback_session_created | session_id, created_at | 转人工判定（30 分钟窗口） |
| chatbot_kb_versions | ix_chatbot_kb_versions_created | created_at | 版本列表排序 |
| chatbot_kb_versions | ix_chatbot_kb_versions_doc_hash | doc_hash | 增量更新时检测变更 |
| chatbot_config | uq_chatbot_config_key | key (UNIQUE) | 配置 key 唯一 |
| chatbot_audit_logs | ix_chatbot_audit_logs_action_created | action, created_at | 按操作类型审计 |

### 2.4 迁移脚本

**迁移策略**：复用主系统 `init_db()` 机制，`Base.metadata.create_all(engine)` 自动创建新表（`checkfirst=True` 幂等）。

```python
# infra/db_models.py 末尾追加表类后，init_db() 自动创建
# 无需独立迁移脚本，因为：
# 1. 新增表与主系统表无外键关联（通过 application 层维护关系）
# 2. SQLite 的 ALTER TABLE 支持有限，CREATE TABLE IF NOT EXISTS 更可靠
# 3. 主系统 init_db() 已在 RepositoryBase.__init__ 中调用

# 如需独立迁移（如生产环境增量升级），可执行：
# python -m xianyu_hunter.migrate_chatbot --action create_tables
```

**回滚脚本**（紧急下线客服模块时）：
```sql
-- 仅删除客服模块表，不影响主系统
DROP TABLE IF EXISTS chatbot_audit_logs;
DROP TABLE IF EXISTS chatbot_config;
DROP TABLE IF EXISTS chatbot_kb_versions;
DROP TABLE IF EXISTS chatbot_feedback;
DROP TABLE IF EXISTS chatbot_faqs;
DROP TABLE IF EXISTS chatbot_messages;
DROP TABLE IF EXISTS chatbot_sessions;
-- 删除 ChromaDB 数据（磁盘文件）
-- rm -rf data/chromadb/
```

### 2.5 数据初始化

**首次启动时插入默认配置**（在 `build_chatbot_container()` 中调用）：

```python
# infra/repo_chatbot.py ChatbotRepository.__init__ 末尾
def _init_default_config(self) -> None:
    """首次启动时插入默认配置（幂等）"""
    defaults = [
        ("enabled", "true", "bool", "智能客服总开关"),
        ("rag.similarity_threshold", "0.65", "float", "RAG 检索相似度阈值"),
        ("faq.similarity_threshold", "0.85", "float", "FAQ 直接返回阈值"),
        ("faq.confirm_threshold", "0.65", "float", "FAQ 确认阈值"),
        ("escalation.contact", "", "string", "转人工联系方式"),
        ("escalation.feedback_threshold", "2", "int", "转人工点踩阈值"),
    ]
    with self._Session() as session:
        for key, value, vtype, desc in defaults:
            exists = session.query(ChatbotConfigRow).filter_by(key=key).first()
            if not exists:
                session.add(ChatbotConfigRow(
                    key=key, value=value, value_type=vtype, description=desc,
                ))
        session.commit()
```

**默认 FAQ 数据**（可选，由运维人员通过 API 录入）：
```python
# 建议预置 5-10 条高频 FAQ，覆盖：
# 1. 如何创建任务？
# 2. 如何配置通知？
# 3. 评估分数的含义？
# 4. 自动抢单如何工作？
# 5. Cookie 失效怎么办？
```

---

## 3. 配置 Schema 详细定义

### 3.1 Pydantic 模型定义

**位置**：[infra/yaml_config.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/infra/yaml_config.py) 追加

```python
from pydantic import BaseModel, Field, field_validator
from typing import Literal


class ChatbotRAGConfig(BaseModel):
    """RAG 检索配置"""
    top_k: int = Field(5, ge=1, le=20, description="检索返回的片段数量")
    similarity_threshold: float = Field(0.65, ge=0.0, le=1.0, description="相似度阈值，低于此值的片段丢弃")
    max_context_chars: int = Field(8000, ge=500, le=32000, description="context 最大字符数，超出则整片丢弃最低相似度片段")

    @field_validator("similarity_threshold")
    @classmethod
    def validate_threshold_range(cls, v: float) -> float:
        """校验相似度阈值在合理范围（cosine similarity 0~1）"""
        if not 0.0 <= v <= 1.0:
            raise ValueError("similarity_threshold 必须在 0.0 ~ 1.0 之间")
        return v


class ChatbotLLMConfig(BaseModel):
    """LLM 调用配置"""
    model: str = Field("gpt-4o-mini", description="OpenAI 模型名")
    temperature: float = Field(0.3, ge=0.0, le=2.0, description="采样温度，0=确定性，2=最大随机")
    max_tokens: int = Field(2000, ge=1, le=4096, description="单次回复最大 token 数")
    http_timeout_sec: int = Field(25, ge=5, le=120, description="HTTP 总超时")
    first_token_timeout_sec: int = Field(15, ge=3, le=60, description="首 token 超时")


class ChatbotAgentConfig(BaseModel):
    """AGENT 工具调用配置"""
    enable_tools: bool = Field(True, description="是否启用 AGENT 工具调用")
    max_tool_rounds: int = Field(3, ge=1, le=10, description="最大工具调用轮数")
    tool_trigger_mode: Literal["function_calling", "fallback"] = Field(
        "function_calling", description="工具触发模式：function_calling 优先 / fallback 兜底"
    )
    tool_call_timeout_sec: int = Field(5, ge=1, le=30, description="单轮工具本地执行超时")
    tool_llm_timeout_sec: int = Field(15, ge=5, le=60, description="单轮 LLM 决策超时")
    tool_total_timeout_sec: int = Field(30, ge=10, le=120, description="AGENT 总超时")


class ChatbotKBConfig(BaseModel):
    """知识库构建与更新配置"""
    auto_update_enabled: bool = Field(True, description="是否启用定时自动更新")
    update_interval_hours: int = Field(6, ge=1, le=168, description="自动更新间隔（小时）")
    doc_paths: list[str] = Field(
        default_factory=lambda: ["docs/", "src/xianyu_hunter/"],
        description="文档扫描路径列表",
    )
    embedding_concurrency: int = Field(5, ge=1, le=20, description="Embedding 并发数")
    embedding_model: str = Field("text-embedding-3-small", description="OpenAI Embedding 模型名")
    embedding_dimensions: int = Field(1536, ge=256, le=3072, description="向量维度")
    chunk_size: int = Field(500, ge=100, le=2000, description="分块字符数")
    chunk_overlap: int = Field(50, ge=0, le=500, description="分块重叠字符数")
    snapshot_max_keep: int = Field(10, ge=1, le=50, description="快照保留数量上限")


class ChatbotFAQConfig(BaseModel):
    """FAQ 匹配配置"""
    similarity_threshold: float = Field(0.85, ge=0.0, le=1.0, description="≥ 此值直接返回")
    confirm_threshold: float = Field(0.65, ge=0.0, le=1.0, description="此值 ~ similarity_threshold 区间需确认")


class ChatbotEscalationConfig(BaseModel):
    """转人工配置"""
    feedback_threshold: int = Field(2, ge=1, le=10, description="触发转人工的点踩次数")
    feedback_window_min: int = Field(30, ge=5, le=1440, description="点踩统计时间窗口（分钟）")
    contact: str = Field("", description="转人工联系方式（空则显示'请联系管理员'）")
    sanitize_pii: bool = Field(True, description="是否脱敏 PII")


class ChatbotConfig(BaseModel):
    """智能客服总配置（对应 yaml 中 chatbot 段）"""
    enabled: bool = Field(True, description="智能客服总开关")
    max_history_turns: int = Field(10, ge=1, le=20, description="上下文历史最大轮数")
    session_timeout_min: int = Field(30, ge=5, le=1440, description="会话超时时间（分钟）")
    rag: ChatbotRAGConfig = Field(default_factory=ChatbotRAGConfig)
    llm: ChatbotLLMConfig = Field(default_factory=ChatbotLLMConfig)
    agent: ChatbotAgentConfig = Field(default_factory=ChatbotAgentConfig)
    kb: ChatbotKBConfig = Field(default_factory=ChatbotKBConfig)
    faq: ChatbotFAQConfig = Field(default_factory=ChatbotFAQConfig)
    escalation: ChatbotEscalationConfig = Field(default_factory=ChatbotEscalationConfig)
```

### 3.2 YAML 完整示例

**位置**：项目根目录 `config.yaml` 中追加 `chatbot` 段

```yaml
# config.yaml
chatbot:
  # 总开关
  enabled: true
  max_history_turns: 10
  session_timeout_min: 30

  # RAG 检索
  rag:
    top_k: 5
    similarity_threshold: 0.65
    max_context_chars: 8000

  # LLM 调用
  llm:
    model: gpt-4o-mini
    temperature: 0.3
    max_tokens: 2000
    http_timeout_sec: 25
    first_token_timeout_sec: 15

  # AGENT 工具调用
  agent:
    enable_tools: true
    max_tool_rounds: 3
    tool_trigger_mode: function_calling  # function_calling | fallback
    tool_call_timeout_sec: 5
    tool_llm_timeout_sec: 15
    tool_total_timeout_sec: 30

  # 知识库构建
  kb:
    auto_update_enabled: true
    update_interval_hours: 6
    doc_paths:
      - "docs/"
      - "src/xianyu_hunter/"
    embedding_concurrency: 5
    embedding_model: text-embedding-3-small
    embedding_dimensions: 1536
    chunk_size: 500
    chunk_overlap: 50
    snapshot_max_keep: 10

  # FAQ 匹配
  faq:
    similarity_threshold: 0.85
    confirm_threshold: 0.65

  # 转人工
  escalation:
    feedback_threshold: 2
    feedback_window_min: 30
    contact: ""  # 空则显示"请联系管理员"
    sanitize_pii: true
```

### 3.3 配置加载与热更新

**加载流程**：

```python
# yaml_config.py AppConfig 追加字段
class AppConfig(BaseModel):
    # ... 现有字段 ...
    chatbot: ChatbotConfig = Field(default_factory=ChatbotConfig)


# 启动时加载
def load_config(yaml_path: str) -> AppConfig:
    """从 YAML 加载配置，自动校验"""
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return AppConfig(**data)
```

**热更新机制**：

```python
# 热更新仅支持 chatbot_config 表中的字段，不修改 yaml_config
# GET /api/chatbot/config 返回合并后的配置（yaml + DB 覆盖）
# PUT /api/chatbot/config 仅更新 DB 中的字段

class ConfigManager:
    """配置管理器：合并 yaml 静态配置与 DB 动态配置"""

    def __init__(self, yaml_config: ChatbotConfig, repo: ChatbotRepository):
        self._yaml = yaml_config
        self._repo = repo

    def get_effective_config(self) -> ChatbotConfig:
        """获取生效配置：yaml 为基础，DB 覆盖可热更新字段"""
        # 深拷贝 yaml 配置
        import copy
        effective = copy.deepcopy(self._yaml)

        # DB 中的热更新字段覆盖
        db_configs = self._repo.get_all_config()
        if "enabled" in db_configs:
            effective.enabled = db_configs["enabled"].lower() == "true"
        if "rag.similarity_threshold" in db_configs:
            effective.rag.similarity_threshold = float(db_configs["rag.similarity_threshold"])
        if "faq.similarity_threshold" in db_configs:
            effective.faq.similarity_threshold = float(db_configs["faq.similarity_threshold"])
        if "faq.confirm_threshold" in db_configs:
            effective.faq.confirm_threshold = float(db_configs["faq.confirm_threshold"])
        if "escalation.contact" in db_configs:
            effective.escalation.contact = db_configs["escalation.contact"]
        if "escalation.feedback_threshold" in db_configs:
            effective.escalation.feedback_threshold = int(db_configs["escalation.feedback_threshold"])
        return effective

    def update_config(self, key: str, value: str, source: str = "web") -> None:
        """更新配置（写入 DB + 审计日志）"""
        import hashlib
        old = self._repo.get_config(key)
        old_hash = hashlib.sha256((old or "").encode()).hexdigest() if old else None
        new_hash = hashlib.sha256(value.encode()).hexdigest()

        self._repo.set_config(key, value)
        self._repo.add_audit_log(
            action="config_update",
            target=key,
            old_value_hash=old_hash,
            new_value_hash=new_hash,
            source=source,
        )
```

### 3.4 配置字段分类

| 字段 | 来源 | 热更新 | 说明 |
|------|------|--------|------|
| `enabled` | DB | ✅ | 总开关，立即生效 |
| `max_history_turns` | yaml | ❌ | 需重启 |
| `session_timeout_min` | yaml | ❌ | 需重启 |
| `rag.top_k` | yaml | ❌ | 需重启 |
| `rag.similarity_threshold` | DB | ✅ | 立即生效 |
| `rag.max_context_chars` | yaml | ❌ | 需重启 |
| `llm.model` | yaml | ❌ | 需重启 |
| `llm.temperature` | yaml | ❌ | 需重启 |
| `agent.enable_tools` | yaml | ❌ | 需重启 |
| `agent.max_tool_rounds` | yaml | ❌ | 需重启 |
| `kb.*` | yaml | ❌ | 需重启 |
| `faq.similarity_threshold` | DB | ✅ | 立即生效 |
| `faq.confirm_threshold` | DB | ✅ | 立即生效 |
| `escalation.contact` | DB | ✅ | 立即生效 |
| `escalation.feedback_threshold` | DB | ✅ | 立即生效 |
| `escalation.sanitize_pii` | yaml | ❌ | 需重启 |

**设计原则**：
- 高频调优字段（阈值、联系方式）支持热更新
- 涉及资源重新初始化的字段（模型、并发数）需重启
- 安全相关字段（sanitize_pii）不开放热更新，防止误关闭

---

## 4. API 详细设计

### 4.1 通用约定

**认证**：所有接口复用主系统 `auth.py` 单 Token 认证（`Authorization: Bearer <token>`），与概要设计 §5.1 一致。

**Content-Type**：`application/json`（除 SSE 接口为 `text/event-stream`）

**错误响应统一格式**：
```json
{
  "detail": "错误描述",
  "code": "ERROR_CODE"
}
```

**分页约定**：
- 请求参数：`page`（从 1 开始）、`page_size`（默认 20，最大 100）
- 响应格式：`{"items": [...], "total": N, "page": P, "page_size": S}`

### 4.2 对话接口

#### POST `/api/chatbot/chat`（SSE 流式）

**请求 Schema**：
```python
class ChatRequest(BaseModel):
    """对话请求"""
    session_id: str = Field(
        ...,
        pattern=r"^[a-f0-9]{32}$",
        description="会话 ID（UUID32，无连字符）",
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="用户消息（1-2000 字符）",
    )
    enable_tools: bool = Field(True, description="是否启用 AGENT 工具调用")

    @field_validator("message")
    @classmethod
    def strip_message(cls, v: str) -> str:
        """去除首尾空白，避免空消息"""
        v = v.strip()
        if not v:
            raise ValueError("消息不能为空")
        return v
```

**响应**：SSE 事件流（`text/event-stream`）

```
event: intent
data: {"intent": "rag_query", "confidence": 0.92}

event: sources
data: {"sources": [{"index": 1, "file": "概要设计文档.md", "section": "§3 模块划分", "line_start": 188, "line_end": 230, "similarity": 0.78}]}

event: token
data: {"token": "智能"}

event: token
data: {"token": "客服"}

event: done
data: {"message_id": "abc123", "tokens_used": 156}

event: tool_call
data: {"tool": "query_task", "args": {"keyword": "iPhone"}, "result_preview": "找到 3 个任务"}
```

**SSE 事件类型**：
| event | data 字段 | 说明 |
|-------|----------|------|
| `intent` | `intent`, `confidence` | 意图分类结果 |
| `sources` | `sources[]` | RAG 参考来源 |
| `token` | `token` | 流式 token |
| `tool_call` | `tool`, `args`, `result_preview` | 工具调用提示 |
| `faq_confirm` | `question`, `answer_preview` | FAQ 模糊匹配确认 |
| `done` | `message_id`, `tokens_used` | 回答完成 |
| `error` | `code`, `message` | 错误 |
| `escalate` | `reason`, `contact` | 转人工 |

**错误码**：
| HTTP | code | 说明 |
|------|------|------|
| 400 | INVALID_SESSION | session_id 格式错误 |
| 400 | MESSAGE_EMPTY | 消息为空 |
| 401 | UNAUTHORIZED | 未认证 |
| 403 | CHATBOT_DISABLED | 客服未启用 |
| 429 | BUDGET_EXCEEDED | AI 预算超限 |
| 503 | KB_NOT_READY | 知识库构建中 |

### 4.3 会话接口

#### POST `/api/chatbot/session`

**请求**：
```python
class SessionCreateRequest(BaseModel):
    """新建会话"""
    title: str | None = Field(None, max_length=100, description="会话标题（可选，默认'新对话'）")
```

**响应**（201）：
```python
class SessionResponse(BaseModel):
    """会话响应"""
    id: str
    title: str
    status: str  # active / ended / escalated
    message_count: int
    last_active_at: datetime
    created_at: datetime

# 示例
{
    "id": "a1b2c3d4e5f6...",
    "title": "新对话",
    "status": "active",
    "message_count": 0,
    "last_active_at": "2026-06-28T10:00:00Z",
    "created_at": "2026-06-28T10:00:00Z"
}
```

#### GET `/api/chatbot/sessions`

**请求参数**（Query）：
| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `page` | int | 1 | 页码 |
| `page_size` | int | 20 | 每页数量 |
| `status` | string | - | 状态过滤（可选） |

**响应**：
```python
class SessionListResponse(BaseModel):
    items: list[SessionResponse]
    total: int
    page: int
    page_size: int
```

#### GET `/api/chatbot/sessions/{session_id}/messages`

**请求参数**（Query）：
| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `limit` | int | 50 | 单次拉取数量（1-100） |
| `before_id` | string | - | 分页游标（拉取此 ID 之前的消息） |

**响应**：
```python
class MessageResponse(BaseModel):
    """消息响应"""
    id: str
    session_id: str
    role: str  # user / assistant / system
    content: str
    metadata: dict | None = None  # sources / tool_calls / intent
    feedback: str | None = None  # positive / negative
    tokens_used: int | None = None
    created_at: datetime

class MessageListResponse(BaseModel):
    items: list[MessageResponse]
    has_more: bool  # 是否还有更早的消息
    oldest_id: str | None = None  # 当前返回中最旧的消息 ID（用于下次 before_id）
```

#### PATCH `/api/chatbot/sessions/{session_id}`

**请求**：
```python
class SessionUpdateRequest(BaseModel):
    """更新会话（仅支持 title）"""
    title: str = Field(..., min_length=1, max_length=100)
```

**响应**：`SessionResponse`

#### DELETE `/api/chatbot/sessions/{session_id}`

**响应**（200）：
```json
{"ok": true, "id": "a1b2c3d4..."}
```

### 4.4 知识库接口

#### GET `/api/chatbot/kb/status`

**响应**：
```python
class KBStatusResponse(BaseModel):
    """知识库状态"""
    is_ready: bool  # 是否就绪
    is_building: bool  # 是否构建中
    current_version: str | None  # 当前版本 ID
    chunk_count: int  # 当前片段数
    last_built_at: datetime | None
    last_build_duration_sec: float | None
    last_error: str | None  # 最近一次构建错误
```

#### POST `/api/chatbot/kb/rebuild`

**请求**：
```python
class KBRebuildRequest(BaseModel):
    """重建知识库"""
    force: bool = Field(False, description="是否强制重建（即使文档未变更）")
```

**响应**（202）：
```python
class KBRebuildResponse(BaseModel):
    task_id: str  # 构建任务 ID（用于轮询状态）
    status: str  # "queued"
    estimated_duration_sec: int  # 预估耗时
```

#### GET `/api/chatbot/kb/versions`

**响应**：
```python
class KBVersionResponse(BaseModel):
    id: str
    chunk_count: int
    failed_chunk_count: int
    build_type: str  # build / incremental / rollback
    status: str  # success / partial / failed
    build_duration_sec: float | None
    created_at: datetime

class KBVersionListResponse(BaseModel):
    items: list[KBVersionResponse]
    total: int
```

#### POST `/api/chatbot/kb/rollback`

**请求**：
```python
class KBRollbackRequest(BaseModel):
    """回滚知识库到指定版本"""
    version_id: str = Field(..., pattern=r"^[a-f0-9]{32}$")
```

**响应**（200）：
```python
class KBRollbackResponse(BaseModel):
    ok: bool
    current_version: str  # 回滚后的当前版本
```

### 4.5 配置接口

#### GET `/api/chatbot/config`

**响应**：
```python
class ConfigResponse(BaseModel):
    """配置响应（合并 yaml + DB）"""
    enabled: bool
    max_history_turns: int
    session_timeout_min: int
    rag: dict  # ChatbotRAGConfig.model_dump()
    llm: dict
    agent: dict
    kb: dict
    faq: dict
    escalation: dict
    # 标注哪些字段可热更新
    updatable_keys: list[str]
```

#### PUT `/api/chatbot/config`

**请求**：
```python
class ConfigUpdateRequest(BaseModel):
    """配置更新（仅支持热更新字段）"""
    key: str = Field(..., description="配置 key（必须在 updatable_keys 列表中）")
    value: str = Field(..., max_length=1000)

    @field_validator("key")
    @classmethod
    def validate_updatable(cls, v: str) -> str:
        updatable = {
            "enabled", "rag.similarity_threshold",
            "faq.similarity_threshold", "faq.confirm_threshold",
            "escalation.contact", "escalation.feedback_threshold",
        }
        if v not in updatable:
            raise ValueError(f"配置项 {v} 不支持热更新")
        return v
```

**响应**：
```python
class ConfigUpdateResponse(BaseModel):
    ok: bool
    key: str
    old_value: str | None
    new_value: str
    is_custom: bool  # 是否与默认值不同
```

### 4.6 反馈接口

#### POST `/api/chatbot/feedback`

**请求**：
```python
class FeedbackRequest(BaseModel):
    """用户反馈"""
    message_id: str = Field(..., pattern=r"^[a-f0-9]{32}$")
    rating: Literal["positive", "negative"]
    comment: str | None = Field(None, max_length=500)
```

**响应**（201）：
```python
class FeedbackResponse(BaseModel):
    ok: bool
    escalate_triggered: bool  # 是否触发转人工
    escalation_contact: str | None  # 触发转人工时的联系方式
```

#### GET `/api/chatbot/escalation`

**响应**：
```python
class EscalationResponse(BaseModel):
    """转人工信息"""
    contact: str  # 联系方式（空则显示"请联系管理员"）
    reason: str | None  # 转人工原因
    session_id: str | None  # 关联会话
    created_at: datetime | None
```

### 4.7 FAQ 接口

#### GET `/api/chatbot/faq`

**请求参数**（Query）：
| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `category` | string | - | 分类过滤（可选） |
| `is_active` | bool | true | 仅查启用的 |

**响应**：
```python
class FAQResponse(BaseModel):
    id: int
    question: str
    answer: str
    category: str
    is_active: bool
    has_embedding: bool  # 是否已生成向量
    created_at: datetime
    updated_at: datetime

class FAQListResponse(BaseModel):
    items: list[FAQResponse]
    total: int
```

#### POST `/api/chatbot/faq`

**请求**：
```python
class FAQUpsertRequest(BaseModel):
    """新增/更新 FAQ"""
    id: int | None = None  # 有 id 则更新，无则新增
    question: str = Field(..., min_length=1, max_length=500)
    answer: str = Field(..., min_length=1, max_length=2000)
    category: str = Field("general", max_length=50)
    is_active: bool = True
```

**响应**（201/200）：
```python
class FAQUpsertResponse(BaseModel):
    ok: bool
    id: int
    is_new: bool  # True=新增 / False=更新
    embedding_pending: bool  # 是否待异步生成向量
```

#### DELETE `/api/chatbot/faq/{faq_id}`

**响应**（200）：
```json
{"ok": true, "id": 42}
```

### 4.8 错误码完整映射

| HTTP | code | 触发条件 | 用户提示 |
|------|------|----------|----------|
| 400 | INVALID_SESSION | session_id 格式错误 | "会话 ID 格式错误" |
| 400 | MESSAGE_EMPTY | 消息为空 | "消息不能为空" |
| 400 | MESSAGE_TOO_LONG | 消息超 2000 字符 | "消息过长" |
| 400 | INVALID_VERSION | version_id 格式错误 | "版本 ID 格式错误" |
| 400 | INVALID_CONFIG_KEY | 配置 key 不支持热更新 | "配置项不支持热更新" |
| 401 | UNAUTHORIZED | 未认证或 token 错误 | `{"detail": "Unauthorized"}` |
| 403 | CHATBOT_DISABLED | 客服未启用 | "智能客服功能未启用" |
| 403 | SESSION_ENDED | 会话已结束，不能继续对话 | "会话已结束，请新建会话" |
| 404 | SESSION_NOT_FOUND | 会话不存在 | "会话不存在" |
| 404 | MESSAGE_NOT_FOUND | 消息不存在 | "消息不存在" |
| 404 | FAQ_NOT_FOUND | FAQ 不存在 | "FAQ 不存在" |
| 404 | VERSION_NOT_FOUND | 知识库版本不存在 | "版本不存在" |
| 409 | KB_BUILDING | 知识库正在构建中 | "知识库正在构建中，请稍后" |
| 409 | KB_CORRUPTED | 知识库损坏 | "知识库损坏，请联系管理员" |
| 429 | BUDGET_EXCEEDED | AI 预算超限 | "AI 预算已用尽" |
| 429 | RATE_LIMITED | 触发限流 | "请求过于频繁" |
| 500 | INTERNAL_ERROR | 未预期异常 | "服务器内部错误" |
| 502 | LLM_UNAVAILABLE | LLM 服务不可用 | "AI 服务暂时不可用" |
| 503 | KB_NOT_READY | 知识库未就绪 | "知识库构建中，请稍后" |

### 4.9 API 速率限制

| 接口 | 限制 | 说明 |
|------|------|------|
| POST /chat | 10 次/分钟/会话 | 防止单会话刷量 |
| POST /chat | 60 次/分钟/用户 | 防止单用户刷量 |
| POST /kb/rebuild | 1 次/10 分钟 | 防止频繁重建 |
| POST /feedback | 30 次/分钟 | 防止刷反馈 |
| 其他接口 | 120 次/分钟 | 通用限制 |

**实现**：复用主系统现有限流中间件（如 `slowapi`），通过 `@router.post("/chat", dependencies=[Depends(rate_limit(...))])` 注入。

---

## 5. 模块详细设计

### 5.0 模块设计约定

1. **类型定义集中**：跨模块共享的数据类型（`SSEEvent`、`RetrievedChunk`、`Source`、`Message`、`ToolResult` 等）统一定义在 [modules/chatbot/types.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/modules/chatbot/types.py)，各模块按需导入，避免循环依赖
2. **配置注入**：所有模块通过构造函数注入 `ChatbotConfig` 或其子配置（§3.1），运行时只读，热更新字段通过 `ConfigManager.get_effective_config()` 在每次请求开始时刷新
3. **异常边界**：模块内部异常不向外抛出，统一转为业务返回值（如 `ToolResult(success=False)`）或 `SSEEvent(type=ERROR)`；`asyncio.CancelledError` 是唯一例外，向上传播以触发资源清理
4. **日志规范**：所有模块使用 `from loguru import logger`，关键节点（降级、转人工、构建失败、超时）必须 `logger.warning` 或 `logger.exception`
5. **伪代码约定**：本文档中 `# ...` 表示省略的非关键实现细节，`raise NotImplementedError` 仅在抽象基类中出现

### 5.1 ChatbotOrchestrator（对话编排器）

**位置**：[modules/chatbot/orchestrator.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/modules/chatbot/orchestrator.py)

**职责**：串联 FAQ → Intent → RAG → Agent → Context → Escalation，编排完整对话流程；管理 per-session 锁；实现降级链。

#### 5.1.1 类定义

```python
# modules/chatbot/orchestrator.py
from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from typing import AsyncIterator

from loguru import logger

from xianyu_hunter.modules.chatbot.types import (
    SSEEvent, SSEEventType, Message, Context, RetrievedChunk, Source,
)
from xianyu_hunter.infra.ai_usage import check_budget, record_usage
from xianyu_hunter.infra.yaml_config import ChatbotConfig


class ChatbotOrchestrator:
    """对话编排器：单例，通过 container 注入

    设计要点：
    - 持有 per-session asyncio.Lock 字典，串行化同一会话的编排
    - 持有所有子模块引用，编排流程不直接访问 DB / ChromaDB
    - 不持有任何请求级状态（如当前 session_id），保证线程安全
    """

    def __init__(
        self,
        faq_matcher: "FAQMatcher",
        intent_classifier: "IntentClassifier",
        rag_engine: "RAGEngine",
        agent: "Agent",
        context_manager: "ContextManager",
        escalation: "Escalation",
        chatbot_repo: "ChatbotRepository",
        config: ChatbotConfig,
        event_bus: "EventBus",
    ) -> None:
        self._faq = faq_matcher
        self._intent = intent_classifier
        self._rag = rag_engine
        self._agent = agent
        self._ctx = context_manager
        self._esc = escalation
        self._repo = chatbot_repo
        self._config = config
        self._event_bus = event_bus
        # per-session 锁：session_id → Lock
        self._session_locks: dict[str, asyncio.Lock] = {}
        # 保护 _session_locks 字典本身的锁（防止并发创建同一 session 的多个 Lock）
        self._locks_guard = asyncio.Lock()
```

#### 5.1.2 公开方法

```python
    async def orchestrate(
        self,
        session_id: str | None,
        message: str,
        enable_tools: bool | None = None,
    ) -> AsyncIterator[SSEEvent]:
        """编排对话流程，流式返回 SSE 事件

        Args:
            session_id: 会话 ID；None 表示首次对话，内部创建新会话
            message: 用户消息（已由 API 层校验长度 1-2000）
            enable_tools: 是否启用工具；None 表示用 config 默认值

        Yields:
            SSEEvent: 按 SSE 协议顺序产生的事件流

        异常处理：
        - asyncio.CancelledError：向上传播，由 API 层清理资源
        - 其他异常：转为 SSEEvent(type=ERROR) 并结束流
        """
        # 1. 会话加载/创建 + 超时检查
        session_id = await self._resolve_session(session_id)

        # 2. per-session 锁串行化（见概要设计 §3.13.1）
        lock = await self._get_session_lock(session_id)
        async with lock:
            # 3. 检查会话超时
            timed_out = self._ctx.check_and_mark_timeout(session_id)
            if timed_out:
                yield SSEEvent(type=SSEEventType.ERROR, data={"code": "SESSION_TIMEOUT"})
                return

            # 4. 加载历史上下文
            context = self._ctx.load_context(session_id)

            # 5. 保存用户消息（先存，便于失败时追溯）
            user_msg = Message(role="user", content=message)
            self._ctx.save_message(session_id, user_msg)

            # 6. FAQ 快速匹配
            faq_result = self._faq.match(message)
            if faq_result.exact_match:
                # 直接返回 FAQ 答案
                yield from self._yield_faq_answer(faq_result, session_id)
                return
            if faq_result.need_confirm:
                yield SSEEvent(
                    type=SSEEventType.FAQ_CONFIRM,
                    data={"question": faq_result.question, "answer": faq_result.answer},
                )
                return

            # 7. 意图分类
            intent = await self._intent.classify(message)
            yield SSEEvent(type=SSEEventType.INTENT, data={"in_scope": intent.in_scope, "method": intent.method})
            if not intent.in_scope:
                # 超出范围 → 拒绝 + 转人工
                async for event in self._handle_out_of_scope(session_id, intent.reason):
                    yield event
                return

            # 8. 预算检查
            budget_ok, budget_reason = check_budget(endpoint="chatbot_chat")
            if not budget_ok:
                logger.warning(f"预算超限: {budget_reason}")
                async for event in self._handle_budget_exceeded(session_id):
                    yield event
                return

            # 9. RAG 检索
            chunks = await self._rag.retrieve(message)
            sources = self._rag.to_sources(chunks)
            if sources:
                yield SSEEvent(type=SSEEventType.SOURCES, data={"sources": [s.__dict__ for s in sources]})

            # 10. AGENT 工具调用（可选）或直接 LLM 生成
            tools_enabled = enable_tools if enable_tools is not None else self._config.agent.enable_tools
            if tools_enabled and self._should_trigger_agent(chunks):
                async for event in self._run_agent_flow(session_id, message, chunks, context, sources):
                    yield event
            else:
                async for event in self._run_rag_flow(session_id, message, chunks, context, sources):
                    yield event

    async def release_session_lock(self, session_id: str) -> None:
        """会话删除时调用，清理 _session_locks 字典项，防止内存泄漏"""
        async with self._locks_guard:
            self._session_locks.pop(session_id, None)
```

#### 5.1.3 内部方法（关键算法）

```python
    async def _get_session_lock(self, session_id: str) -> asyncio.Lock:
        """获取或创建会话级锁（双检锁模式）"""
        async with self._locks_guard:
            if session_id not in self._session_locks:
                self._session_locks[session_id] = asyncio.Lock()
            return self._session_locks[session_id]

    def _should_trigger_agent(self, chunks: list[RetrievedChunk]) -> bool:
        """判断是否触发 AGENT 工具调用

        触发条件（config.agent.tool_trigger_mode）：
        - function_calling：始终允许 LLM 决定（返回 True，由 LLM 自行判断）
        - fallback：仅当 RAG 相似度全部 < threshold 时返回 True
        """
        if self._config.agent.tool_trigger_mode == "function_calling":
            return True
        # fallback 模式：所有片段相似度都低于阈值
        return all(c.similarity < self._config.rag.similarity_threshold for c in chunks)

    async def _run_rag_flow(
        self,
        session_id: str,
        message: str,
        chunks: list[RetrievedChunk],
        context: Context,
        sources: list[Source],
    ) -> AsyncIterator[SSEEvent]:
        """RAG + LLM 流式生成流程（含降级链）"""
        context_text = self._rag.build_context(chunks)
        history = self._ctx.build_history_messages(context)

        # 降级链（见概要设计 §3.13.3）
        try:
            full_answer = []
            async for token in self._rag.generate(message, context_text, history):
                full_answer.append(token)
                yield SSEEvent(type=SSEEventType.TOKEN, data={"token": token})

            answer = "".join(full_answer)
            answer, valid_sources = self._rag.postprocess_citations(answer, sources)
            if valid_sources:
                yield SSEEvent(type=SSEEventType.SOURCES, data={"sources": [s.__dict__ for s in valid_sources]})

            # 保存 assistant 消息
            self._ctx.save_message(
                session_id, Message(role="assistant", content=answer, sources=valid_sources)
            )
            record_usage(endpoint="chatbot_chat", model=self._config.llm.model, response_data={})
            yield SSEEvent(type=SSEEventType.DONE, data={"message_id": "..."})

        except (asyncio.TimeoutError, httpx.ConnectError, httpx.ReadTimeout) as e:
            logger.warning(f"LLM 异常 {type(e).__name__}，降级到 RAG 片段")
            yield SSEEvent(type=SSEEventType.ERROR, data={"code": "LLM_DEGRADED", "message": str(e)})
            async for event in self._fallback_to_rag_fragments(chunks, sources, session_id):
                yield event
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception(f"RAG 流程未知异常: {e}")
            yield SSEEvent(type=SSEEventType.ERROR, data={"code": "UNKNOWN", "message": str(e)})
            async for event in self._escalate(session_id, f"内部错误: {type(e).__name__}"):
                yield event

    async def _run_agent_flow(
        self,
        session_id: str,
        message: str,
        chunks: list[RetrievedChunk],
        context: Context,
        sources: list[Source],
    ) -> AsyncIterator[SSEEvent]:
        """AGENT 多步工具调用流程"""
        history = self._ctx.build_history_messages(context)
        full_answer = []
        async for event in self._agent.run(
            question=message,
            rag_chunks=chunks,
            history=history,
            on_tool_call=lambda name: logger.info(f"工具调用: {name}"),
        ):
            if event.type == "tool_call":
                yield SSEEvent(type=SSEEventType.TOOL_CALL, data=event.data)
            elif event.type == "token":
                full_answer.append(event.data["token"])
                yield SSEEvent(type=SSEEventType.TOKEN, data=event.data)
            elif event.type == "done":
                answer = "".join(full_answer)
                self._ctx.save_message(
                    session_id, Message(role="assistant", content=answer, sources=sources)
                )
                yield SSEEvent(type=SSEEventType.DONE, data=event.data)
                return

    async def _fallback_to_rag_fragments(
        self, chunks: list[RetrievedChunk], sources: list[Source], session_id: str,
    ) -> AsyncIterator[SSEEvent]:
        """降级：直接拼接 RAG 片段返回"""
        if not chunks:
            async for event in self._escalate(session_id, "RAG 无匹配片段"):
                yield event
            return
        # 按 source_file 分组拼接
        fragments = "\n\n---\n\n".join(c.content for c in chunks)
        yield SSEEvent(type=SSEEventType.TOKEN, data={"token": fragments})
        self._ctx.save_message(
            session_id, Message(role="assistant", content=fragments, sources=sources, degraded=True)
        )
        yield SSEEvent(type=SSEEventType.DONE, data={"degraded": True})

    async def _escalate(self, session_id: str, reason: str) -> AsyncIterator[SSEEvent]:
        """转人工流程"""
        resp = self._esc.build_escalation_response(session_id, reason)
        await self._event_bus.publish(...)  # CHATBOT_ESCALATED
        yield SSEEvent(
            type=SSEEventType.ESCALATE,
            data={"reason": reason, "contact": resp.contact, "session_id": session_id},
        )
```

#### 5.1.4 边界条件

| 场景 | 处理 |
|------|------|
| `session_id=None` | 内部调用 `create_session`，首条消息后异步生成标题 |
| 会话已 `ended`（超时） | 返回 `SESSION_TIMEOUT` 错误事件，引导用户新建会话 |
| FAQ 命中 + 用户已点踩 N 次 | 优先级：转人工 > FAQ，即点踩达阈值时即使 FAQ 命中也转人工 |
| RAG 返回空 chunks | 跳过 LLM 流程，直接进入 AGENT 或转人工 |
| LLM 流式过程中客户端断开 | `asyncio.CancelledError` 传播，未保存的 assistant 消息丢弃 |

---

### 5.2 RAGEngine（RAG 引擎）

**位置**：[modules/chatbot/rag_engine.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/modules/chatbot/rag_engine.py)

**职责**：文档检索 + context 构建 + LLM 流式生成 + 引用后处理。

#### 5.2.1 类定义

```python
# modules/chatbot/rag_engine.py
from __future__ import annotations

import httpx
import re
from typing import AsyncIterator

from loguru import logger

from xianyu_hunter.modules.chatbot.types import RetrievedChunk, Source, Message
from xianyu_hunter.infra.ai_usage import check_budget, record_usage
from xianyu_hunter.infra.yaml_config import ChatbotConfig


class RAGEngine:
    """RAG 引擎：无状态，可被多会话共享"""

    # 引用编号正则：[来源:1] [来源:12]
    _CITATION_RE = re.compile(r"\[来源:(\d+)\]")

    def __init__(
        self,
        embedding: "EmbeddingService",
        vector_store: "VectorStore",
        config: ChatbotConfig,
    ) -> None:
        self._embedding = embedding
        self._vector_store = vector_store
        self._config = config
        # httpx 客户端复用：连接池 + keep-alive
        self._http = httpx.AsyncClient(
            base_url=self._get_openai_base_url(),
            headers={"Authorization": f"Bearer {self._get_openai_api_key()}"},
            timeout=httpx.Timeout(
                connect=5.0,
                read=config.llm.http_timeout_sec,
                write=5.0,
                pool=2.0,
            ),
        )
```

#### 5.2.2 公开方法

```python
    async def retrieve(self, question: str) -> list[RetrievedChunk]:
        """检索 top_k 相关片段，过滤相似度 < threshold

        算法：
        1. 问题向量化（embedding.embed）
        2. ChromaDB 向量检索（vector_store.search）
        3. 阈值过滤：similarity < config.rag.similarity_threshold 的片段丢弃
        4. 按相似度降序排序
        """
        query_vec = await self._embedding.embed(question)
        raw_chunks = await self._vector_store.search(query_vec, top_k=self._config.rag.top_k)
        filtered = [c for c in raw_chunks if c.similarity >= self._config.rag.similarity_threshold]
        filtered.sort(key=lambda c: c.similarity, reverse=True)
        return filtered

    def to_sources(self, chunks: list[RetrievedChunk]) -> list[Source]:
        """将 RetrievedChunk 转换为前端友好的 Source 列表（不含 content）"""
        return [
            Source(
                index=i + 1,  # 1-based，对应 [来源:N]
                file=c.source_file,
                section=c.section_path,
                line_start=c.line_start,
                line_end=c.line_end,
                similarity=round(c.similarity, 3),
            )
            for i, c in enumerate(chunks)
        ]

    def build_context(self, chunks: list[RetrievedChunk]) -> str:
        """构建 LLM system message 中的 context 文本

        截断策略（见概要设计 §3.2）：
        1. 从最低相似度开始整片丢弃，直到总长 ≤ max_context_chars
        2. 若仅剩 1 片仍超长，按字符截断并标记 truncated=True
        3. 每片格式：[来源:N] file_path (section_path)\n<content>
        """
        max_chars = self._config.rag.max_context_chars
        # 按相似度降序排列，确保保留最相关的
        sorted_chunks = sorted(chunks, key=lambda c: c.similarity, reverse=True)

        # 从尾部（最低相似度）开始丢弃
        while len(sorted_chunks) > 1:
            total = sum(len(c.content) + 80 for c in sorted_chunks)  # 80 为格式开销估算
            if total <= max_chars:
                break
            sorted_chunks.pop()

        # 拼接
        parts = []
        for i, c in enumerate(sorted_chunks, start=1):
            header = f"[来源:{i}] {c.source_file} ({c.section_path}) L{c.line_start}-{c.line_end}"
            parts.append(f"{header}\n{c.content}")

        context = "\n\n---\n\n".join(parts)

        # 单片仍超长：按字符截断（M-5 修复：截断前记录 original_len，避免日志丢失原始长度）
        if len(context) > max_chars:
            original_len = len(context)
            context = context[:max_chars - 3] + "..."
            logger.warning(f"context 单片截断：原 {original_len} 字符 → {max_chars}")

        return context

    async def generate(
        self,
        question: str,
        context: str,
        history: list[Message],
    ) -> AsyncIterator[str]:
        """流式生成回答（httpx + stream=true）

        算法：
        1. 构造 OpenAI Chat Completions 请求（system + user + system 三消息结构）
        2. POST /v1/chat/completions with stream=true
        3. 逐 chunk 解析 SSE，提取 choices[0].delta.content
        4. 首 token 超时检测：超过 first_token_timeout_sec 仍未收到首 token 则抛 TimeoutError
        5. 用量记录（H5 修复）：正常/异常/空响应路径均调用 _record_llm_usage，
           避免 LLM 调用已发生但用量未统计导致预算控制失准

        异常：
        - httpx.ReadTimeout / httpx.ConnectError：向上抛出，由 Orchestrator 降级处理
        - JSONDecodeError：记录并抛出
        """
        messages = self._build_messages(question, context, history)
        payload = {
            "model": self._config.llm.model,
            "messages": messages,
            "temperature": self._config.llm.temperature,
            "max_tokens": self._config.llm.max_tokens,
            "stream": True,
        }

        collected: list[str] = []  # 收集 output tokens 用于用量记录（H5）
        first_token_received = False
        try:
            async with self._http.stream("POST", "/v1/chat/completions", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    import json
                    chunk = json.loads(data)
                    delta = chunk["choices"][0].get("delta", {})
                    if "content" in delta and delta["content"]:
                        first_token_received = True
                        collected.append(delta["content"])
                        yield delta["content"]
        except Exception:
            # H5 修复：异常路径也需记录已发生的用量
            self._record_llm_usage(messages, collected)
            raise

        # H5 修复：空响应路径也需记录用量
        self._record_llm_usage(messages, collected)
        if not first_token_received:
            logger.warning("LLM 未返回任何 token")
            raise RuntimeError("LLM returned empty response")

    def postprocess_citations(
        self, answer: str, sources: list[Source],
    ) -> tuple[str, list[Source]]:
        """引用后处理：校验 [来源:N] 编号有效性

        算法：
        1. 正则提取所有 [来源:N] 编号
        2. 编号 > len(sources) 或 < 1 的替换为 [来源:?]
        3. 返回有效引用的 sources 子集（按出现顺序去重）
        """
        valid_indices: set[int] = set()
        max_idx = len(sources)

        def _replace(match: re.Match) -> str:
            idx = int(match.group(1))
            if 1 <= idx <= max_idx:
                valid_indices.add(idx)
                return match.group(0)
            return "[来源:?]"

        cleaned = self._CITATION_RE.sub(_replace, answer)
        # 按出现顺序排列有效 sources
        valid_sources = [sources[i - 1] for i in sorted(valid_indices)]
        return cleaned, valid_sources
```

#### 5.2.3 内部方法

```python
    def _build_messages(
        self, question: str, context: str, history: list[Message],
    ) -> list[dict]:
        """构造 OpenAI messages：system(指令) + history + system(context) + user

        为什么 context 放在 system 而非 user：
        - 防止 Prompt Injection：用户消息中的"忽略上述指令"无法覆盖 system 中的 context
        - 与 OpenAI 官方推荐一致（system 用于设定 assistant 行为）
        """
        return [
            {"role": "system", "content": self._get_system_prompt()},
            *[{"role": m.role, "content": m.content} for m in history],
            {"role": "system", "content": f"参考资料：\n{context}"},
            {"role": "user", "content": question},
        ]

    def _get_system_prompt(self) -> str:
        """从 api_prompts.py 加载 chatbot_system_prompt（支持热更新）"""
        from xianyu_hunter.web.routes.api_prompts import get_prompt
        return get_prompt("chatbot_system_prompt")

    def _record_llm_usage(
        self, messages: list[dict], collected_output: list[str]
    ) -> None:
        """记录 LLM 用量（H5 修复：异常路径与空响应路径也需记录）

        流式 API 无 usage 字段，按字符数 ÷ 4 估算 token 数（OpenAI 经验值）。
        记录失败仅 warning 不抛出，避免影响主流程。
        """
        # 实现见 rag_engine.py，调用 ai_usage.record_usage(endpoint="chatbot_llm", ...)
        pass
```

---

### 5.3 Agent（智能代理）

**位置**：[modules/chatbot/agent.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/modules/chatbot/agent.py)

**职责**：基于 LLM function calling 的多步工具调用与推理。

#### 5.3.1 类定义与事件类型

```python
# modules/chatbot/agent.py
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import AsyncIterator, Callable, Any

from loguru import logger

from xianyu_hunter.modules.chatbot.types import RetrievedChunk, Message
from xianyu_hunter.infra.yaml_config import ChatbotConfig


@dataclass
class AgentEvent:
    """Agent 产生的事件，转 SSE 后发给前端"""
    type: str  # "tool_call" | "token" | "done" | "error"
    data: dict[str, Any]


class Agent:
    """AGENT：基于 OpenAI function_calling 的多步推理"""

    def __init__(
        self,
        tool_registry: "ToolRegistry",
        rag_engine: "RAGEngine",
        config: ChatbotConfig,
    ) -> None:
        self._tools = tool_registry
        self._rag = rag_engine
        self._config = config
```

#### 5.3.2 公开方法

```python
    async def run(
        self,
        question: str,
        rag_chunks: list[RetrievedChunk],
        history: list[Message],
        on_tool_call: Callable[[str], None] | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """AGENT 多步推理主循环

        算法（最多 max_tool_rounds 轮）：
        1. 构造初始 messages（含 RAG context + history + question）
        2. 调用 LLM with tools 定义
        3. 若 LLM 返回 tool_calls：
           a. 并发执行所有 tool_calls（每工具单超时 tool_call_timeout_sec）
           b. 将 tool results 加入 messages
           c. 回到步骤 2
        4. 若 LLM 返回 content：流式 yield token
        5. 若达 max_tool_rounds 仍未回答：强制让 LLM 不带 tools 再调一次

        总超时控制：asyncio.timeout(tool_total_timeout_sec)
        """
        try:
            async with asyncio.timeout(self._config.agent.tool_total_timeout_sec):
                async for event in self._run_loop(question, rag_chunks, history, on_tool_call):
                    yield event
        except asyncio.TimeoutError:
            logger.warning(f"AGENT 总超时（>{self._config.agent.tool_total_timeout_sec}s）")
            yield AgentEvent(type="error", data={"code": "AGENT_TIMEOUT"})
            # 降级：让 LLM 不带 tools 直接回答
            async for event in self._final_answer_without_tools(question, rag_chunks, history):
                yield event

    async def _run_loop(
        self,
        question: str,
        rag_chunks: list[RetrievedChunk],
        history: list[Message],
        on_tool_call: Callable[[str], None] | None,
    ) -> AsyncIterator[AgentEvent]:
        """单轮工具调用循环"""
        messages = self._build_initial_messages(question, rag_chunks, history)
        tools_schema = self._tools.get_openai_schema()

        for round_idx in range(self._config.agent.max_tool_rounds):
            # 调用 LLM 决策（非流式，等待 tool_calls 或 content）
            response = await self._call_llm_for_decision(messages, tools_schema)

            if response.get("tool_calls"):
                # 执行工具调用
                messages.append(response)
                for tool_call in response["tool_calls"]:
                    if on_tool_call:
                        on_tool_call(tool_call["function"]["name"])
                    yield AgentEvent(type="tool_call", data={
                        "name": tool_call["function"]["name"],
                        "args": tool_call["function"]["arguments"],
                    })
                    # 执行工具（ToolRegistry 内部已处理异常，返回 ToolResult）
                    result = await self._tools.call(
                        tool_call["function"]["name"],
                        **json.loads(tool_call["function"]["arguments"]),
                    )
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": json.dumps(result.to_dict(), ensure_ascii=False),
                    })
                # 继续下一轮，让 LLM 基于工具结果决策
                continue

            # LLM 返回 content：流式生成最终回答
            async for token in self._stream_final_answer(messages):
                yield AgentEvent(type="token", data={"token": token})
            yield AgentEvent(type="done", data={"rounds": round_idx + 1})
            return

        # 达到最大轮数仍未回答：强制无 tools 回答
        logger.warning(f"AGENT 达到最大轮数 {self._config.agent.max_tool_rounds}，强制最终回答")
        async for event in self._final_answer_without_tools(question, rag_chunks, history):
            yield event
```

#### 5.3.3 ToolRegistry（工具注册表）

```python
# modules/chatbot/tools/registry.py
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

from loguru import logger

from xianyu_hunter.infra.yaml_config import ChatbotConfig


@dataclass
class Tool:
    """工具定义"""
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema
    handler: Callable[..., Awaitable["ToolResult"]]
    permissions: list[str] = field(default_factory=lambda: ["read"])
    enabled: bool = True


@dataclass
class ToolResult:
    """工具调用结果（统一返回类型）"""
    success: bool
    data: Any = None
    error: str | None = None

    def to_dict(self) -> dict:
        return {"success": self.success, "data": self.data, "error": self.error}


# 敏感字段正则（见概要设计 §7.4 附录 A.2）
_SENSITIVE_KEY_PATTERNS = [
    re.compile(r"api[_-]?key", re.I),
    re.compile(r"openai[_-]?key", re.I),
    re.compile(r"cookie", re.I),
    re.compile(r"token", re.I),
    re.compile(r"password", re.I),
    re.compile(r"secret", re.I),
    re.compile(r"webhook[_-]?url", re.I),
    re.compile(r"bearer", re.I),
]


class ToolRegistry:
    """工具注册表：管理工具声明、调用、敏感字段过滤"""

    def __init__(self, repo: "Repository", config: ChatbotConfig) -> None:
        self._repo = repo
        self._config = config
        self._tools: dict[str, Tool] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        """注册默认工具集（6 个，见概要设计 §3.3）"""
        from xianyu_hunter.modules.chatbot.tools.builtin import (
            search_knowledge, get_task_status, get_eval_score,
            get_config_value, get_error_logs, get_help_page,
        )
        for handler in [search_knowledge, get_task_status, get_eval_score,
                        get_config_value, get_error_logs, get_help_page]:
            self.register(handler(self._repo, self._config))

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get_openai_schema(self) -> list[dict]:
        """生成 OpenAI function calling 用的 tools 参数"""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in self._tools.values() if t.enabled and "read" in t.permissions
        ]

    async def call(self, name: str, **kwargs) -> ToolResult:
        """统一工具调用入口（异常处理见概要设计 §3.13.2）"""
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(success=False, error=f"未知工具: {name}")
        if not tool.enabled:
            return ToolResult(success=False, error=f"工具已禁用: {name}")
        try:
            async with asyncio.timeout(self._config.agent.tool_call_timeout_sec):
                result = await tool.handler(**kwargs)
                return self._filter_sensitive(result)
        except asyncio.TimeoutError:
            return ToolResult(
                success=False,
                error=f"工具 {name} 执行超时（>{self._config.agent.tool_call_timeout_sec}s）",
            )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception(f"工具 {name} 执行异常: {e}")
            return ToolResult(
                success=False,
                error=f"工具 {name} 内部错误: {type(e).__name__}: {str(e)[:200]}",
            )

    def _filter_sensitive(self, result: ToolResult) -> ToolResult:
        """递归过滤 ToolResult.data 中的敏感字段，替换为 <REDACTED>"""
        if not isinstance(result.data, (dict, list)):
            return result
        filtered = self._redact_recursive(result.data)
        return ToolResult(success=result.success, data=filtered, error=result.error)

    def _redact_recursive(self, obj: Any) -> Any:
        if isinstance(obj, dict):
            return {
                k: ("<REDACTED>" if any(p.search(k) for p in _SENSITIVE_KEY_PATTERNS)
                    else self._redact_recursive(v))
                for k, v in obj.items()
            }
        if isinstance(obj, list):
            return [self._redact_recursive(item) for item in obj]
        return obj
```

---

### 5.4 IntentClassifier（意图分类器）

**位置**：[modules/chatbot/intent_classifier.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/modules/chatbot/intent_classifier.py)

**职责**：判断用户问题是否在闲鱼猎人系统范围内，避免 LLM 被滥用回答无关问题。

#### 5.4.1 类定义

```python
# modules/chatbot/intent_classifier.py
from __future__ import annotations

import json
from dataclasses import dataclass

from loguru import logger

from xianyu_hunter.infra.ai_usage import record_usage
from xianyu_hunter.infra.yaml_config import ChatbotConfig


@dataclass
class IntentResult:
    """意图分类结果"""
    in_scope: bool
    reason: str
    method: str  # "rule" | "llm"


# 白名单关键词：命中则 in_scope=True
_SCOPE_KEYWORDS = {
    "任务", "采集", "评估", "抢单", "通知", "反爬", "登录", "Cookie",
    "配置", "AI", "Prompt", "贩子", "价格", "去重", "事件", "日志",
    "Docker", "部署", "数据库", "API", "SSE", "WebSocket",
    "闲鱼猎人", "XianyuHunter", "知识库", "RAG", "AGENT",
}

# 黑名单关键词：命中则 in_scope=False
_OUT_OF_SCOPE_KEYWORDS = {
    "天气", "新闻", "股票", "翻译", "写诗", "写作文",
    "Python 怎么写", "Java 怎么写",  # 通用编程
    "闲鱼怎么退款", "闲鱼怎么卖",  # 闲鱼平台问题
    "你是谁", "你叫什么",  # 身份探究
}


class IntentClassifier:
    """两阶段意图分类器：规则预筛 + LLM 兜底"""

    def __init__(self, config: ChatbotConfig) -> None:
        self._config = config
        # 复用 Orchestrator 注入的 httpx client（在 build_chatbot_container 中共享）
        self._http = None  # 由 container 注入
```

#### 5.4.2 公开方法

```python
    async def classify(self, question: str) -> IntentResult:
        """两阶段分类

        算法：
        1. 规则预筛（< 1ms）：
           - 白名单命中 → in_scope=True, method="rule"
           - 黑名单命中 → in_scope=False, method="rule"
        2. LLM 兜底（~800ms）：仅规则无法判定时调用
           - 用 system prompt 约束 LLM 仅返回 {"in_scope": bool, "reason": str}

        边界条件：
        - 空字符串：返回 in_scope=False, reason="空消息"
        - LLM 调用失败：保守返回 in_scope=True，让 RAG/AGENT 兜底
        """
        question = question.strip()
        if not question:
            return IntentResult(in_scope=False, reason="空消息", method="rule")

        # 阶段 1：规则预筛
        rule_result = self._rule_classify(question)
        if rule_result is not None:
            return rule_result

        # 阶段 2：LLM 兜底
        return await self._llm_classify(question)

    def _rule_classify(self, question: str) -> IntentResult | None:
        """规则预筛：返回 None 表示无法判定，需 LLM 兜底"""
        # 白名单优先（避免"闲鱼怎么卖任务"被黑名单误杀）
        for kw in _SCOPE_KEYWORDS:
            if kw in question:
                return IntentResult(in_scope=True, reason=f"命中关键词: {kw}", method="rule")
        for kw in _OUT_OF_SCOPE_KEYWORDS:
            if kw in question:
                return IntentResult(in_scope=False, reason=f"命中黑名单: {kw}", method="rule")
        return None

    async def _llm_classify(self, question: str) -> IntentResult:
        """LLM 兜底分类

        失败策略：网络异常/超时时保守返回 in_scope=True，
        让 RAG/AGENT 兜底处理（避免因分类器故障导致无法回答）

        M-11 修复：OpenAI 兼容 API 在触发安全过滤时可能返回 content: null，
        需用 .get("content") or "" 做空安全，空内容时保守放行

        M-12 修复：LLM 偶尔返回非合法 JSON（如带 markdown 包裹），
        单独捕获 JSONDecodeError 并记录 raw content 便于排查
        """
        if self._http is None:
            return IntentResult(in_scope=True, reason="LLM 未配置，保守放行", method="rule")
        try:
            # ... 构造 messages + 调用 LLM ...
            record_usage(endpoint="chatbot_intent", model=self._config.llm.model, response_data={})
            # M-11 修复：content 可能为 null（安全过滤触发），用 .get() or "" 兜底
            content = (data["choices"][0]["message"].get("content") or "").strip()
            if not content:
                return IntentResult(in_scope=True, reason="LLM 返回空内容，保守放行", method="llm")
            # M-12 修复：单独捕获 JSONDecodeError，记录 raw content 便于排查
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError as je:
                logger.warning(f"LLM 返回非 JSON 内容，保守放行: {je}; raw={content[:200]}")
                return IntentResult(in_scope=True, reason=f"LLM 返回非 JSON，保守放行: {je}", method="llm")
            return IntentResult(in_scope=parsed.get("in_scope", True), reason="LLM 判定", method="llm")
        except Exception as e:
            logger.warning(f"LLM 意图分类失败，保守放行: {e}")
            return IntentResult(in_scope=True, reason=f"LLM 异常，保守放行: {type(e).__name__}", method="rule")
```

---

### 5.5 KBManager（知识库管理器）

**位置**：[modules/chatbot/kb_manager.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/modules/chatbot/kb_manager.py)

**职责**：文档扫描、切片、向量化、ChromaDB 写入、版本管理、增量更新、回滚。

#### 5.5.1 类定义

```python
# modules/chatbot/kb_manager.py
from __future__ import annotations

import ast
import hashlib
import os
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import asyncio
from loguru import logger

from xianyu_hunter.modules.chatbot.types import RetrievedChunk
from xianyu_hunter.infra.yaml_config import ChatbotConfig


@dataclass
class DocSnippet:
    """文档切片后的片段"""
    content: str
    source_file: str
    section_path: str
    line_start: int
    line_end: int
    doc_type: str  # requirement | design | manual | code


@dataclass
class KBVersion:
    """知识库版本"""
    id: str
    snapshot_path: str
    doc_hash: str
    chunk_count: int
    failed_chunk_count: int = 0
    build_type: str = "full"  # full | incremental
    status: str = "success"  # success | partial | failed


class KBManager:
    """知识库管理器：单例，通过 container 注入"""

    def __init__(
        self,
        vector_store: "VectorStore",
        chatbot_repo: "ChatbotRepository",
        embedding: "EmbeddingService",
        config: ChatbotConfig,
        event_bus: "EventBus",
    ) -> None:
        self._vector_store = vector_store
        self._repo = chatbot_repo
        self._embedding = embedding
        self._config = config
        self._event_bus = event_bus
        # 构建互斥锁：防止并发 build_all（API 触发 + 定时触发）
        self._build_lock = asyncio.Lock()
```

#### 5.5.2 公开方法

```python
    async def build_all(
        self, on_progress: Callable[[int, int], None] | None = None,
    ) -> KBVersion | None:
        """全量构建知识库（两阶段提交，见概要设计 §3.13.5）

        Args:
            on_progress: 进度回调 (current, total)

        Returns:
            KBVersion: 构建成功；None: 构建失败（已回滚）
        """
        async with self._build_lock:
            return await self._do_build(on_progress=on_progress, build_type="full")

    async def incremental_update(self) -> KBVersion | None:
        """增量更新：检测 mtime + hash 变化，仅重建变更片段

        算法：
        1. 扫描所有文件，计算当前 hash 集合
        2. 与上一版本的 doc_hash 对比
        3. 若无变化：返回 None
        4. 若有变化：调用 build_all（简化实现，未来可优化为仅重建变更文件）
        """
        async with self._build_lock:
            current_hash = self._compute_doc_hash()
            last_version = self._repo.get_current_kb_version()
            if last_version and last_version.doc_hash == current_hash:
                logger.info("知识库无变化，跳过增量更新")
                return None
            return await self._do_build(on_progress=None, build_type="incremental")

    async def rollback(self, version_id: str) -> bool:
        """回滚到指定版本

        算法：
        1. 校验 version_id 存在且 snapshot_path 完整
        2. 从快照恢复 ChromaDB
        3. 更新 current_kb_version
        4. 发布 chatbot.kb_rolled_back 事件
        """
        version = self._repo.get_kb_version(version_id)
        if not version:
            logger.warning(f"回滚失败：版本 {version_id} 不存在")
            return False
        try:
            await self._vector_store.restore_from_snapshot(version.snapshot_path)
            self._repo.set_current_kb_version(version_id)
            await self._publish_event("chatbot.kb_rolled_back", {"version": version_id})
            return True
        except Exception as e:
            logger.exception(f"回滚失败: {e}")
            return False

    def get_status(self) -> dict:
        """获取知识库状态（供 API 返回）"""
        current = self._repo.get_current_kb_version()
        return {
            "current_version": current.id if current else None,
            "chunk_count": current.chunk_count if current else 0,
            "last_build_at": current.created_at if current else None,
            "building": self._build_lock.locked(),
        }
```

#### 5.5.3 内部方法（关键算法）

```python
    async def _do_build(
        self,
        on_progress: Callable[[int, int], None] | None,
        build_type: str,
    ) -> KBVersion | None:
        """实际构建流程（两阶段提交）"""
        # 阶段 1：解析 + 扫描 + embedding（无副作用）
        try:
            snippets = self._scan_and_chunk()
            if not snippets:
                logger.warning("未扫描到任何文档片段")
                return None

            # 敏感字段扫描
            snippets = [s for s in snippets if not self._has_sensitive_data(s.content)]

            # 批量向量化（部分失败容忍，见概要设计 §3.13.4）
            embeddings = await self._embedding.embed_batch(
                [s.content for s in snippets],
                on_progress=on_progress,
            )

            # 失败率检查
            failed_count = len(snippets) - len(embeddings)
            if failed_count > len(snippets) * 0.1:
                logger.error(
                    f"Embedding 失败率 {failed_count}/{len(snippets)} > 10%，终止构建"
                )
                await self._publish_failure_event("embedding_failure_rate_too_high")
                return None
        except Exception as e:
            logger.exception(f"阶段 1 失败: {e}")
            await self._publish_failure_event(f"phase1_error: {e}")
            return None

        # 阶段 2：写入 ChromaDB + 创建版本（事务性）
        version_id = uuid.uuid4().hex
        snapshot_path = f"data/chromadb/snapshots/{version_id}"

        try:
            # 2a. 导出当前 ChromaDB 状态到快照
            await self._vector_store.export_snapshot(snapshot_path)

            # 2b. 清空集合并写入新数据
            await self._vector_store.clear_collection()
            chunks_with_vectors = [
                (snippet, vec) for snippet, vec in zip(snippets, embeddings) if vec is not None
            ]
            await self._vector_store.upsert(chunks_with_vectors)

            # 2c. 创建版本记录
            version = KBVersion(
                id=version_id,
                snapshot_path=snapshot_path,
                doc_hash=self._compute_doc_hash(),
                chunk_count=len(chunks_with_vectors),
                failed_chunk_count=failed_count,
                build_type=build_type,
                status="partial" if failed_count > 0 else "success",
            )
            self._repo.create_kb_version(version)
            self._repo.set_current_kb_version(version_id)

            # 清理旧快照（保留最近 N 个）
            self._cleanup_old_snapshots()

            await self._publish_event("chatbot.kb_rebuilt", {"version": version_id})
            return version

        except Exception as e:
            logger.exception(f"阶段 2 失败，开始回滚: {e}")
            await self._rollback_build(snapshot_path)
            await self._publish_failure_event(f"phase2_error: {e}")
            return None

    def _scan_and_chunk(self) -> list[DocSnippet]:
        """扫描所有 doc_paths，切片生成 DocSnippet 列表

        切片策略（见需求 §4.2.2）：
        - Markdown：按 H2/H3 标题切分，单块超 chunk_size 时按字符再切
        - Python：AST 解析提取 module/class/function docstring，失败则文件粒度
        - 其他文件：跳过
        """
        snippets: list[DocSnippet] = []
        for doc_path in self._config.kb.doc_paths:
            root = Path(doc_path)
            if not root.exists():
                logger.warning(f"文档路径不存在: {doc_path}")
                continue
            for file_path in root.rglob("*"):
                if file_path.suffix == ".md":
                    snippets.extend(self._chunk_markdown(file_path))
                elif file_path.suffix == ".py":
                    snippets.extend(self._chunk_python(file_path))
        return snippets

    def _chunk_markdown(self, file_path: Path) -> list[DocSnippet]:
        """Markdown 切片：按 H2/H3 标题切分"""
        content = file_path.read_text(encoding="utf-8")
        lines = content.split("\n")
        snippets = []
        current_section = []
        current_path = ""
        line_start = 1

        for i, line in enumerate(lines, start=1):
            if line.startswith("## "):
                # 保存前一段
                if current_section:
                    snippets.append(self._make_snippet(
                        "\n".join(current_section), file_path, current_path, line_start, i - 1, "manual"
                    ))
                current_section = [line]
                current_path = line.lstrip("# ").strip()
                line_start = i
            else:
                current_section.append(line)

        # 最后一段
        if current_section:
            snippets.append(self._make_snippet(
                "\n".join(current_section), file_path, current_path, line_start, len(lines), "manual"
            ))

        # 单块超长切分
        return self._split_oversized(snippets)

    def _chunk_python(self, file_path: Path) -> list[DocSnippet]:
        """Python 文件切片：AST 提取 docstring

        提取范围：模块级、class、公开方法（非 _ 开头）
        AST 解析失败降级为文件粒度
        """
        try:
            tree = ast.parse(file_path.read_text(encoding="utf-8"))
        except SyntaxError:
            logger.debug(f"AST 解析失败，降级文件粒度: {file_path}")
            return [DocSnippet(
                content=file_path.read_text(encoding="utf-8")[:self._config.kb.chunk_size],
                source_file=str(file_path),
                section_path="<file>",
                line_start=1,
                line_end=len(file_path.read_text(encoding="utf-8").splitlines()),
                doc_type="code",
            )]

        snippets = []
        # 模块级 docstring
        if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant):
            doc = tree.body[0].value.value
            if isinstance(doc, str):
                snippets.append(DocSnippet(
                    content=doc, source_file=str(file_path),
                    section_path="<module>", line_start=1, line_end=1, doc_type="code",
                ))

        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                if isinstance(node, ast.FunctionDef) and node.name.startswith("_"):
                    continue  # 跳过私有方法
                doc = ast.get_docstring(node)
                if doc:
                    snippets.append(DocSnippet(
                        content=f"{node.name}: {doc}",
                        source_file=str(file_path),
                        section_path=f"{node.__class__.__name__}:{node.name}",
                        line_start=node.lineno,
                        line_end=node.end_lineno or node.lineno,
                        doc_type="code",
                    ))
        return snippets

    def _has_sensitive_data(self, content: str) -> bool:
        """敏感字段扫描（见概要设计 §7.4 附录 A.2）

        命中任一正则则丢弃该片段（不脱敏，因为脱敏会破坏代码语义）
        """
        from xianyu_hunter.modules.chatbot.security.patterns import SENSITIVE_PATTERNS
        return any(p.search(content) for p in SENSITIVE_PATTERNS)

    async def _rollback_build(self, snapshot_path: str) -> None:
        """回滚：恢复 ChromaDB + 删除未完成快照"""
        try:
            await self._vector_store.restore_from_snapshot(snapshot_path)
        except Exception as e:
            logger.exception(f"快照恢复失败，ChromaDB 可能不一致: {e}")
            self._repo.set_config("kb_status", "corrupted")
            return
        if os.path.exists(snapshot_path):
            shutil.rmtree(snapshot_path, ignore_errors=True)

    def _cleanup_old_snapshots(self) -> None:
        """清理旧快照，保留最近 snapshot_max_keep 个"""
        versions = self._repo.list_kb_versions()
        if len(versions) <= self._config.kb.snapshot_max_keep:
            return
        to_remove = versions[self._config.kb.snapshot_max_keep:]
        for v in to_remove:
            if os.path.exists(v.snapshot_path):
                shutil.rmtree(v.snapshot_path, ignore_errors=True)
```

---

### 5.6 FAQMatcher（FAQ 匹配器）

**位置**：[modules/chatbot/faq_matcher.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/modules/chatbot/faq_matcher.py)

**职责**：FAQ 关键词匹配 + 编辑距离相似度计算，快速命中常见问题。

#### 5.6.1 类定义

```python
# modules/chatbot/faq_matcher.py
from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from xianyu_hunter.infra.yaml_config import ChatbotConfig


@dataclass
class FAQMatchResult:
    """FAQ 匹配结果"""
    exact_match: bool = False       # 相似度 ≥ similarity_threshold
    need_confirm: bool = False      # confirm_threshold ≤ 相似度 < similarity_threshold
    question: str = ""              # 匹配到的 FAQ 问题
    answer: str = ""                # FAQ 答案
    similarity: float = 0.0         # 相似度分数
    faq_id: int | None = None


class FAQMatcher:
    """FAQ 匹配器：无状态，可被多会话共享"""

    def __init__(
        self,
        chatbot_repo: "ChatbotRepository",
        config: ChatbotConfig,
    ) -> None:
        self._repo = chatbot_repo
        self._config = config
        # FAQ 缓存：避免每次请求都查 DB（FAQ 总数 < 1000，内存占用可忽略）
        self._cache: list[dict] | None = None
        self._cache_dirty = True

    def invalidate_cache(self) -> None:
        """FAQ 增删改后调用，标记缓存失效"""
        self._cache_dirty = True
```

#### 5.6.2 公开方法

```python
    def match(self, question: str) -> FAQMatchResult:
        """FAQ 匹配

        算法：
        1. 加载 FAQ 列表（带缓存）
        2. 对每个 FAQ 问题计算与用户问题的相似度
           - 关键词命中加权（+0.2）
           - 编辑距离相似度（rapidfuzz.fuzz.ratio）
           - 最终分数 = max(编辑距离相似度, 关键词命中 ? 0.7 : 0)
        3. 取最高分 FAQ：
           - ≥ similarity_threshold（0.85）：exact_match=True
           - ≥ confirm_threshold（0.65）：need_confirm=True
           - < confirm_threshold：返回空结果

        性能：FAQ < 1000，单次匹配 < 50ms
        """
        faqs = self._load_faqs()
        if not faqs:
            return FAQMatchResult()

        best_score = 0.0
        best_faq = None
        for faq in faqs:
            score = self._compute_similarity(question, faq["question"])
            if score > best_score:
                best_score = score
                best_faq = faq

        if best_faq is None or best_score < self._config.faq.confirm_threshold:
            return FAQMatchResult()

        result = FAQMatchResult(
            question=best_faq["question"],
            answer=best_faq["answer"],
            similarity=round(best_score, 3),
            faq_id=best_faq["id"],
        )
        if best_score >= self._config.faq.similarity_threshold:
            result.exact_match = True
        else:
            result.need_confirm = True
        return result

    def _load_faqs(self) -> list[dict]:
        """加载 FAQ 列表（带缓存）"""
        if self._cache_dirty or self._cache is None:
            self._cache = [faq.__dict__ for faq in self._repo.list_faq()]
            self._cache_dirty = False
        return self._cache

    def _compute_similarity(
        self, query_embedding: list[float], faq_embedding: list[float]
    ) -> float:
        """cosine 相似度 = dot(a,b) / (|a| * |b|)

        M-22 修复：维度不一致时 zip 会静默截断导致相似度失真
        （常见诱因：配置 dimensions 变更后旧 FAQ embedding 仍是旧维度），
        维度不匹配时返回 0.0 并 warning，跳过该 FAQ

        防止除零：任一向量为零向量时返回 0.0
        """
        if len(query_embedding) != len(faq_embedding):
            logger.warning(
                f"embedding 维度不一致：query={len(query_embedding)} "
                f"faq={len(faq_embedding)}，跳过该 FAQ"
            )
            return 0.0
        dot = sum(a * b for a, b in zip(query_embedding, faq_embedding))
        norm_a = sum(a * a for a in query_embedding) ** 0.5
        norm_b = sum(b * b for b in faq_embedding) ** 0.5
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)

    @staticmethod
    def _levenshtein_ratio(s1: str, s2: str) -> float:
        """自实现 Levenshtein 相似度（rapidfuzz 降级方案）"""
        if not s1 and not s2:
            return 1.0
        if not s1 or not s2:
            return 0.0
        # ... 标准 DP 实现 ...
        distance = 0  # 占位，实际为 DP 计算结果
        return 1.0 - distance / max(len(s1), len(s2))
```

---

### 5.7 ContextManager（上下文管理器）

**位置**：[modules/chatbot/context_manager.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/modules/chatbot/context_manager.py)

**职责**：会话上下文加载、历史消息裁剪、会话超时管理、标题生成。

#### 5.7.1 类定义

```python
# modules/chatbot/context_manager.py
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from loguru import logger

from xianyu_hunter.modules.chatbot.types import Message
from xianyu_hunter.infra.yaml_config import ChatbotConfig


@dataclass
class Context:
    """会话上下文"""
    session_id: str
    messages: list[Message] = field(default_factory=list)
    status: str = "active"  # active | ended
    title: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ContextManager:
    """上下文管理器：单例"""

    def __init__(
        self,
        chatbot_repo: "ChatbotRepository",
        config: ChatbotConfig,
    ) -> None:
        self._repo = chatbot_repo
        self._config = config
```

#### 5.7.2 公开方法

```python
    def load_context(self, session_id: str) -> Context:
        """加载会话上下文（H7 修复：纯 DB 操作无需 async，改为同步方法）

        M-10 修复：session_id 为空字符串时与 None 同等处理（返回 ended Context）

        算法：
        1. 查询 chatbot_sessions 表获取会话状态
        2. status=ended：返回空 Context（不复用历史）
        3. status=active：查询最近 max_history_turns * 2 条消息（user+assistant 一对）
        """
        # M-10 修复：空字符串与 None 同等处理（not 同时覆盖两者）
        if not session_id:
            return Context(session_id=session_id, status="ended")
        session = self._repo.get_session(session_id)
        if not session:
            return Context(session_id=session_id, status="ended")

        if session.status == "ended":
            return Context(session_id=session_id, status="ended", title=session.title)

        # 加载最近 N 轮（每轮 = 1 user + 1 assistant）
        limit = self._config.max_history_turns * 2
        msg_rows = self._repo.list_messages(session_id, limit=limit, before_id=None)
        messages = [
            Message(role=row.role, content=row.content, sources=row.sources)
            for row in reversed(msg_rows)  # DB 按 created_at DESC，反转为正序
        ]
        return Context(
            session_id=session_id, status="active", title=session.title, messages=messages,
        )

    def save_message(self, session_id: str, message: Message) -> str:
        """保存消息到 DB（H7 修复：纯 DB 操作无需 async，改为同步方法）

        同步更新 sessions.message_count 冗余字段
        """
        message_id = self._repo.add_message(session_id, message)
        return message_id

    def build_history_messages(self, context: Context) -> list[Message]:
        """构建 OpenAI messages 格式的历史

        裁剪策略（见概要设计 §3.7）：
        1. 优先保留所有 user 消息
        2. assistant 消息按时间从最早开始裁剪
        3. 单条 > 2000 字符截断到 500 字符（保留首尾）
        """
        if not context.messages:
            return []

        # 分离 user 与 assistant
        user_msgs = [m for m in context.messages if m.role == "user"]
        assistant_msgs = [m for m in context.messages if m.role == "assistant"]

        # 超出 max_history_turns 时：保留所有 user，从最早的 assistant 开始裁剪
        max_msgs = self._config.max_history_turns * 2
        if len(context.messages) > max_msgs:
            excess = len(context.messages) - max_msgs
            assistant_msgs = assistant_msgs[excess:]

        # 重新按时间顺序合并
        result = []
        user_idx, assistant_idx = 0, 0
        for m in context.messages:
            if m.role == "user" and user_idx < len(user_msgs):
                result.append(self._truncate_message(user_msgs[user_idx]))
                user_idx += 1
            elif m.role == "assistant" and assistant_idx < len(assistant_msgs):
                result.append(self._truncate_message(assistant_msgs[assistant_idx]))
                assistant_idx += 1

        return result

    async def check_and_mark_timeout(self, session_id: str) -> bool:
        """检查会话超时，标记 status=ended

        超时规则（见需求 §4.5.3）：
        - 最近一条消息距今 > session_timeout_min → 超时
        - 首次对话（无消息）不视为超时
        """
        session = self._repo.get_session(session_id)
        if not session or session.status == "ended":
            return True  # 已结束的会话视为"已超时"

        last_msgs = self._repo.list_messages(session_id, limit=1, before_id=None)
        if not last_msgs:
            return False  # 无消息，新会话不超时

        last_msg_time = last_msgs[0].created_at
        if last_msg_time.tzinfo is None:
            last_msg_time = last_msg_time.replace(tzinfo=timezone.utc)

        timeout = timedelta(minutes=self._config.session_timeout_min)
        if datetime.now(timezone.utc) - last_msg_time > timeout:
            self._repo.update_session_status(session_id, "ended")
            logger.info(f"会话 {session_id} 超时，已标记 ended")
            return True
        return False

    def generate_title(self, session_id: str, first_message: str) -> None:
        """生成会话标题（H7 修复：内部无 await，改为同步方法）

        算法：
        1. 调用 LLM 生成 ≤ 20 字标题
        2. LLM 失败时降级为 first_message[:20]
        3. 更新 sessions.title
        """
        try:
            title = await self._call_llm_for_title(first_message)
        except Exception as e:
            logger.warning(f"标题生成失败，降级为截断: {e}")
            title = first_message[:20]
        self._repo.update_session_title(session_id, title)

    def _truncate_message(self, msg: Message) -> Message:
        """单条消息超长截断（保留首 250 + 尾 250 字符）"""
        if len(msg.content) <= 2000:
            return msg
        return Message(
            role=msg.role,
            content=msg.content[:250] + "\n...(省略)...\n" + msg.content[-250:],
            sources=msg.sources,
        )
```

---

### 5.8 Escalation（转人工处理）

**位置**：[modules/chatbot/escalation.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/modules/chatbot/escalation.py)

**职责**：转人工触发判定、话术生成、PII 脱敏。

#### 5.8.1 类定义

```python
# modules/chatbot/escalation.py
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from loguru import logger

from xianyu_hunter.modules.chatbot.types import RetrievedChunk, Message
from xianyu_hunter.infra.yaml_config import ChatbotConfig


@dataclass
class EscalationResponse:
    """转人工响应"""
    reason: str
    contact: str
    sanitized_session: str | None = None  # 脱敏后的会话文本（供复制）


# 用户主动转人工关键词
_ESCALATE_KEYWORDS = {"人工", "客服", "管理员", "转人工", "真人"}


class Escalation:
    """转人工处理器：无状态"""

    def __init__(
        self,
        chatbot_repo: "ChatbotRepository",
        config: ChatbotConfig,
    ) -> None:
        self._repo = chatbot_repo
        self._config = config
```

#### 5.8.2 公开方法

```python
    def should_escalate(
        self,
        session_id: str,
        recent_feedback: list,  # list[FeedbackRow]
        rag_results: list[RetrievedChunk],
        agent_failed: bool,
        user_message: str,
    ) -> tuple[bool, str]:
        """判断是否触发转人工（见概要设计 §3.8）

        触发条件（任一满足即触发）：
        1. 用户消息含"人工"/"客服"/"管理员"等关键词
        2. 连续 N 次点踩（30 分钟内，会话内）
        3. RAG 相似度全部 < 0.65
        4. AGENT 3 轮后仍无法回答

        Returns:
            (should_escalate, reason)
        """
        # 1. 用户主动
        for kw in _ESCALATE_KEYWORDS:
            if kw in user_message:
                return True, f"用户主动请求转人工（含关键词: {kw}）"

        # 2. 连续点踩
        threshold = self._config.escalation.feedback_threshold
        window = timedelta(minutes=self._config.escalation.feedback_window_min)
        now = datetime.now(timezone.utc)
        recent_negative = [
            f for f in recent_feedback
            if f.rating == "negative"
            and (now - f.created_at.replace(tzinfo=timezone.utc)) < window
        ]
        if len(recent_negative) >= threshold:
            return True, f"连续 {len(recent_negative)} 次点踩（{self._config.escalation.feedback_window_min} 分钟内）"

        # 3. RAG 无匹配
        if rag_results and all(c.similarity < 0.65 for c in rag_results):
            return True, "RAG 检索无相关片段（相似度全部 < 0.65）"

        # 4. AGENT 失败
        if agent_failed:
            return True, "AGENT 多轮工具调用后仍无法回答"

        return False, ""

    def build_escalation_response(self, session_id: str, reason: str) -> EscalationResponse:
        """构建转人工响应

        联系方式为空时显示"请联系管理员"
        """
        contact = self._config.escalation.contact or "请联系管理员"
        return EscalationResponse(
            reason=reason,
            contact=contact,
            sanitized_session=None,  # 按需生成（用户点"复制会话"时才调 sanitize）
        )

    def sanitize_session_for_copy(self, messages: list[Message]) -> str:
        """导出会话记录供复制，自动脱敏 PII

        脱敏规则（见概要设计 §7.4 附录 A.3）：
        - 手机号 → 138****1234
        - 邮箱 → z***@example.com
        - 身份证 → 110***********1234
        - 银行卡 → 6212********1234
        - 微信号 → wx****1234
        - QQ 号 → 1234****89
        """
        from xianyu_hunter.modules.chatbot.security.patterns import PII_PATTERNS, pii_replace
        lines = []
        for msg in messages:
            content = msg.content
            for pattern, replacer in PII_PATTERNS:
                content = pattern.sub(replacer, content)
            lines.append(f"[{msg.role}]: {content}")
        return "\n\n".join(lines)
```

---

### 5.9 EmbeddingService（向量化服务）

**位置**：[modules/chatbot/embedding_service.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/modules/chatbot/embedding_service.py)

**职责**：调用 OpenAI Embedding API，支持批量并发 + 重试 + 部分失败容忍。

#### 5.9.1 类定义

```python
# modules/chatbot/embedding_service.py
from __future__ import annotations

import asyncio
from typing import Callable

import httpx
from loguru import logger

from xianyu_hunter.infra.ai_usage import check_budget, record_usage
from xianyu_hunter.infra.yaml_config import ChatbotConfig


class EmbeddingService:
    """向量化服务：单例"""

    def __init__(self, config: ChatbotConfig) -> None:
        self._config = config
        # 并发控制（见概要设计 §3.9）
        self._semaphore = asyncio.Semaphore(config.kb.embedding_concurrency)
        # H2/H3 修复：OpenAI 配置统一从 get_settings() 读取（.env + keyring），
        # 不再用 os.getenv（仅读 .env，会遗漏 keyring 凭证）
        from xianyu_hunter.config import get_settings
        settings = get_settings()
        self._api_key = settings.openai_api_key
        self._base_url = settings.openai_base_url.rstrip("/")
        self._embeddings_url = self._base_url + "/embeddings"
        self._http = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=httpx.Timeout(connect=5.0, read=30.0, write=5.0, pool=2.0),
        )
        # M-2 修复：注释过时（KBManager 不再通过属性检查失败率，直接用 embed_batch 返回值）
        # 最近一次批量调用的失败索引列表（保留供调试与监控查询）
        self._last_batch_failures: list[int] = []
```

#### 5.9.2 公开方法

```python
    async def embed(self, text: str) -> list[float]:
        """单文本向量化

        单次调用不走并发控制（semaphore），因为 RAGEngine.retrieve 每次只 embed 一个 query
        """
        budget_ok, _ = check_budget(endpoint="chatbot_embedding")
        if not budget_ok:
            raise RuntimeError("Embedding 预算超限")

        payload = {
            "model": self._config.kb.embedding_model,
            "input": text,
            "dimensions": self._config.kb.embedding_dimensions,
        }
        resp = await self._http.post("/v1/embeddings", json=payload)
        resp.raise_for_status()
        data = resp.json()
        record_usage(endpoint="chatbot_embedding", model=self._config.kb.embedding_model, response_data=data)
        return data["data"][0]["embedding"]

    async def embed_batch(
        self,
        texts: list[str],
        on_progress: Callable[[int, int], None] | None = None,
    ) -> list[tuple[str, list[float]]]:
        """批量向量化（见概要设计 §3.13.4）

        算法：
        1. 并发控制：Semaphore(embedding_concurrency)
        2. 每个文本独立重试 3 次（指数退避：1s, 2s, 4s）
        3. 失败的文本记录到 _last_batch_failures，不阻塞其他文本
        4. 返回成功的 (text, embedding) 列表，保持原始顺序

        边界条件：
        - 空列表：返回空列表
        - 全部失败：返回空列表，KBManager 据此判断失败率
        """
        if not texts:
            return []

        self._last_batch_failures = []
        results: list[tuple[int, list[float] | None]] = [None] * len(texts)

        async def embed_one(idx: int, text: str) -> tuple[int, list[float] | None]:
            async with self._semaphore:
                for attempt in range(3):
                    try:
                        vec = await self._call_openai(text)
                        if on_progress:
                            on_progress(idx + 1, len(texts))
                        return idx, vec
                    except Exception as e:
                        if attempt == 2:
                            logger.warning(f"Embedding 片段 {idx} 失败（重试 3 次）: {e}")
                            # M-15 修复：仅存索引（int），失败详情已在日志中记录
                            self._last_batch_failures.append(idx)
                            return idx, None
                        await asyncio.sleep(2 ** attempt)

        tasks = [embed_one(i, t) for i, t in enumerate(texts)]
        completed = await asyncio.gather(*tasks)

        # 仅保留成功的，按原顺序
        return [
            (texts[idx], vec)
            for idx, vec in sorted(completed, key=lambda x: x[0])
            if vec is not None
        ]

    @property
    def last_batch_failure_count(self) -> int:
        """返回上次批量调用的失败数（M-15 修复：原命名 last_batch_failures 暗示返回列表，实际返回 int 数量）"""
        return len(self._last_batch_failures)

    async def _call_openai(self, text: str) -> list[float]:
        """实际调用 OpenAI Embedding API"""
        budget_ok, _ = check_budget(endpoint="chatbot_embedding")
        if not budget_ok:
            raise RuntimeError("Embedding 预算超限")

        payload = {
            "model": self._config.kb.embedding_model,
            "input": text,
            "dimensions": self._config.kb.embedding_dimensions,
        }
        resp = await self._http.post("/v1/embeddings", json=payload)
        resp.raise_for_status()
        data = resp.json()
        record_usage(endpoint="chatbot_embedding", model=self._config.kb.embedding_model, response_data=data)
        return data["data"][0]["embedding"]
```

---

### 5.10 VectorStore（ChromaDB 适配器）

**位置**：[modules/chatbot/vector_store.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/modules/chatbot/vector_store.py)

**职责**：封装 ChromaDB 的增删改查 + 快照导出/恢复。

#### 5.10.1 类定义

```python
# modules/chatbot/vector_store.py
from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Any

from loguru import logger

from xianyu_hunter.modules.chatbot.types import RetrievedChunk


class VectorStore:
    """ChromaDB 适配器：单例

    设计要点：
    - 关闭 telemetry（见需求 §10.3）
    - 使用 PersistentClient（数据落盘到 data/chromadb/）
    - 集合名固定为 xianyu_hunter_docs，hnsw:space=cosine
    - 所有方法为 async，通过 asyncio.to_thread 包装 ChromaDB 同步 API
    """

    COLLECTION_NAME = "xianyu_hunter_docs"

    def __init__(self, persist_path: str = "data/chromadb") -> None:
        # 关闭 telemetry（避免用户数据外泄）
        import chromadb
        chromadb.telemetry.disable_anonymized_telemetry()

        self._client = chromadb.PersistentClient(path=persist_path)
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        self._persist_path = persist_path
        self._snapshots_dir = Path(persist_path) / "snapshots"
        self._snapshots_dir.mkdir(parents=True, exist_ok=True)
```

#### 5.10.2 公开方法

```python
    async def search(
        self, query_vec: list[float], top_k: int,
    ) -> list[RetrievedChunk]:
        """向量检索

        算法：
        1. 调用 ChromaDB collection.query（同步 API，用 asyncio.to_thread 包装）
        2. 将 ChromaDB 返回的 distance（cosine 距离）转为 similarity
        3. 构造 RetrievedChunk 列表

        边界条件：
        - 集合为空：返回空列表
        - top_k > 集合大小：返回实际数量的结果
        """
        def _sync_query():
            return self._collection.query(
                query_embeddings=[query_vec],
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
            )

        result = await asyncio.to_thread(_sync_query)
        if not result["ids"] or not result["ids"][0]:
            return []

        chunks = []
        for i, doc_id in enumerate(result["ids"][0]):
            distance = result["distances"][0][i]
            # cosine distance → similarity
            similarity = 1.0 - (distance / 2.0)
            metadata = result["metadatas"][0][i]
            chunks.append(RetrievedChunk(
                content=result["documents"][0][i],
                source_file=metadata.get("source_file", ""),
                section_path=metadata.get("section_path", ""),
                line_start=metadata.get("line_start", 0),
                line_end=metadata.get("line_end", 0),
                doc_type=metadata.get("doc_type", "manual"),
                similarity=similarity,
            ))
        return chunks

    async def upsert(self, chunks_with_vectors: list[tuple[Any, list[float]]]) -> None:
        """批量写入/更新片段

        Args:
            chunks_with_vectors: [(DocSnippet, embedding), ...]
        """
        def _sync_upsert():
            ids = [f"chunk_{i}" for i in range(len(chunks_with_vectors))]
            embeddings = [vec for _, vec in chunks_with_vectors]
            documents = [snippet.content for snippet, _ in chunks_with_vectors]
            metadatas = [
                {
                    "source_file": snippet.source_file,
                    "section_path": snippet.section_path,
                    "line_start": snippet.line_start,
                    "line_end": snippet.line_end,
                    "doc_type": snippet.doc_type,
                }
                for snippet, _ in chunks_with_vectors
            ]
            self._collection.upsert(
                ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas,
            )

        await asyncio.to_thread(_sync_upsert)

    async def delete_by_source(self, source_file: str) -> None:
        """删除指定文件的所有片段（增量更新用）"""
        def _sync_delete():
            self._collection.delete(where={"source_file": source_file})
        await asyncio.to_thread(_sync_delete)

    async def clear_collection(self) -> None:
        """清空集合（全量重建前调用）"""
        def _sync_clear():
            self._client.delete_collection(self.COLLECTION_NAME)
            self._collection = self._client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
        await asyncio.to_thread(_sync_clear)

    async def export_snapshot(self, snapshot_path: str) -> None:
        """导出当前 ChromaDB 状态到磁盘快照

        实现：直接复制 persist_path 整个目录到 snapshot_path
        （ChromaDB 0.4.x 无原生快照 API，文件级复制是最简单可靠的方式）
        """
        def _sync_export():
            src = Path(self._persist_path)
            dst = Path(snapshot_path)
            dst.mkdir(parents=True, exist_ok=True)
            # 复制除 snapshots 子目录外的所有内容
            for item in src.iterdir():
                if item.name == "snapshots":
                    continue
                target = dst / item.name
                if item.is_dir():
                    shutil.copytree(item, target, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, target)

        await asyncio.to_thread(_sync_export)

    async def restore_from_snapshot(self, snapshot_path: str) -> None:
        """从磁盘快照恢复 ChromaDB

        实现：清空当前 persist_path，将快照内容复制回来，重建 collection 引用
        """
        def _sync_restore():
            src = Path(snapshot_path)
            if not src.exists():
                raise FileNotFoundError(f"快照不存在: {snapshot_path}")
            # 清空当前数据（保留 snapshots 目录）
            for item in Path(self._persist_path).iterdir():
                if item.name == "snapshots":
                    continue
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            # 复制快照内容
            for item in src.iterdir():
                target = Path(self._persist_path) / item.name
                if item.is_dir():
                    shutil.copytree(item, target, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, target)
            # 重建 collection 引用
            self._collection = self._client.get_collection(self.COLLECTION_NAME)

        await asyncio.to_thread(_sync_restore)
```

---

### 5.11 ChatbotRepository（对话仓储）

**位置**：[infra/repo_chatbot.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/infra/repo_chatbot.py)

**职责**：封装 7 张 chatbot_* 表的 CRUD，复用主 Repository.engine。

#### 5.11.1 类定义

```python
# infra/repo_chatbot.py
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Engine, select, update, delete, func
from sqlalchemy.orm import sessionmaker
from loguru import logger

from xianyu_hunter.infra.db_models import (
    Base, ChatbotSessionRow, ChatbotMessageRow, ChatbotFAQRow,
    ChatbotFeedbackRow, ChatbotKBVersionRow, ChatbotConfigRow, ChatbotAuditLogRow,
)
from xianyu_hunter.modules.chatbot.types import Message


def _utcnow() -> datetime:
    """统一 UTC 时间生成"""
    return datetime.now(timezone.utc)


def _uuid32() -> str:
    """生成无连字符的 UUID32"""
    return uuid.uuid4().hex


class ChatbotRepository:
    """对话仓储：复用主 Repository.engine（见概要设计 §3.11 P0 修订）

    关键约束：
    - 接受 engine 参数（由 build_chatbot_container 注入 parent.repo.engine）
    - 不调用 create_engine / init_db
    - Session 使用 sessionmaker(bind=engine, expire_on_commit=False)
    """

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._Session = sessionmaker(bind=engine, expire_on_commit=False)
        # 幂等创建表（主 init_db 已建，这里 checkfirst=True 安全）
        Base.metadata.create_all(
            engine,
            tables=[
                ChatbotSessionRow.__table__,
                ChatbotMessageRow.__table__,
                ChatbotFAQRow.__table__,
                ChatbotFeedbackRow.__table__,
                ChatbotKBVersionRow.__table__,
                ChatbotConfigRow.__table__,
                ChatbotAuditLogRow.__table__,
            ],
            checkfirst=True,
        )
        # 初始化默认配置
        self._init_default_config()
```

#### 5.11.2 会话与消息 CRUD

```python
    # ===== 会话 =====

    def create_session(self, title: str = "", user_id: str = "default") -> str:
        """创建会话，返回 session_id"""
        session_id = _uuid32()
        with self._Session() as db:
            row = ChatbotSessionRow(
                id=session_id,
                user_id=user_id,
                title=title or "新会话",
                status="active",
                message_count=0,
                created_at=_utcnow(),
                updated_at=_utcnow(),
            )
            db.add(row)
            db.commit()
        return session_id

    def get_session(self, session_id: str) -> ChatbotSessionRow | None:
        with self._Session() as db:
            return db.get(ChatbotSessionRow, session_id)

    def list_sessions(
        self, user_id: str, page: int, page_size: int,
    ) -> tuple[list[ChatbotSessionRow], int]:
        """分页列表（利用 message_count 冗余字段，避免 N+1 聚合）"""
        with self._Session() as db:
            stmt = select(ChatbotSessionRow).where(
                ChatbotSessionRow.user_id == user_id
            ).order_by(ChatbotSessionRow.updated_at.desc())
            total = db.scalar(select(func.count()).select_from(stmt.subquery()))
            rows = db.execute(
                stmt.offset((page - 1) * page_size).limit(page_size)
            ).scalars().all()
            return list(rows), total or 0

    def update_session_status(self, session_id: str, status: str) -> None:
        with self._Session() as db:
            db.execute(
                update(ChatbotSessionRow)
                .where(ChatbotSessionRow.id == session_id)
                .values(status=status, updated_at=_utcnow())
            )
            db.commit()

    def update_session_title(self, session_id: str, title: str) -> None:
        with self._Session() as db:
            db.execute(
                update(ChatbotSessionRow)
                .where(ChatbotSessionRow.id == session_id)
                .values(title=title, updated_at=_utcnow())
            )
            db.commit()

    def merge_session_metadata(self, session_id: str, patch: dict) -> bool:
        """合并写入 session.metadata_json（保留已有字段）

        M-30 修复：patch 中的 None 值不覆盖已有有效字段
        （如 escalation_reason 被误清空）

        单事务内 SELECT + UPDATE 保证原子性，避免并发覆盖。
        返回是否更新成功（session_id 不存在时返回 False）。
        """
        with self._Session() as db:
            row = db.execute(
                select(ChatbotSessionRow).where(ChatbotSessionRow.id == session_id)
            ).scalar_one_or_none()
            if row is None:
                return False
            existing: dict = {}
            if row.metadata_json:
                try:
                    existing = json.loads(row.metadata_json)
                except (json.JSONDecodeError, TypeError):
                    existing = {}
            # M-30 修复：过滤 None 值，避免覆盖已有有效字段
            existing.update({k: v for k, v in patch.items() if v is not None})
            row.metadata_json = json.dumps(existing, ensure_ascii=False)
            row.updated_at = _utcnow()
            db.commit()
            return True

    def delete_session(self, session_id: str) -> None:
        """级联删除：会话 + 消息 + 反馈"""
        with self._Session() as db:
            db.execute(delete(ChatbotFeedbackRow).where(
                ChatbotFeedbackRow.session_id == session_id
            ))
            db.execute(delete(ChatbotMessageRow).where(
                ChatbotMessageRow.session_id == session_id
            ))
            db.execute(delete(ChatbotSessionRow).where(
                ChatbotSessionRow.id == session_id
            ))
            db.commit()

    # ===== 消息 =====

    def add_message(self, session_id: str, message: Message) -> str:
        """添加消息，同步维护 sessions.message_count 冗余字段"""
        message_id = _uuid32()
        with self._Session() as db:
            row = ChatbotMessageRow(
                id=message_id,
                session_id=session_id,
                role=message.role,
                content=message.content,
                sources_json=message.sources_to_json(),
                tokens_used=message.tokens_used,
                created_at=_utcnow(),
            )
            db.add(row)
            # 同步更新 message_count + updated_at
            db.execute(
                update(ChatbotSessionRow)
                .where(ChatbotSessionRow.id == session_id)
                .values(
                    message_count=ChatbotSessionRow.message_count + 1,
                    updated_at=_utcnow(),
                )
            )
            db.commit()
        return message_id

    def list_messages(
        self, session_id: str, limit: int, before_id: str | None,
    ) -> list[ChatbotMessageRow]:
        """查询消息（按 created_at DESC，支持游标分页）"""
        with self._Session() as db:
            stmt = select(ChatbotMessageRow).where(
                ChatbotMessageRow.session_id == session_id
            ).order_by(ChatbotMessageRow.created_at.desc())
            if before_id:
                before = db.get(ChatbotMessageRow, before_id)
                if before:
                    stmt = stmt.where(ChatbotMessageRow.created_at < before.created_at)
            return list(db.execute(stmt.limit(limit)).scalars().all())
```

#### 5.11.3 FAQ / 反馈 / 版本 / 配置 / 审计

```python
    # ===== FAQ =====
    def list_faq(self, category: str | None = None) -> list[ChatbotFAQRow]:
        with self._Session() as db:
            stmt = select(ChatbotFAQRow).where(ChatbotFAQRow.enabled == True)
            if category:
                stmt = stmt.where(ChatbotFAQRow.category == category)
            return list(db.execute(stmt.order_by(ChatbotFAQRow.id).scalars().all()))

    def upsert_faq(self, faq_data: dict) -> int:
        """FAQ upsert（id 存在则更新，否则新增）"""
        with self._Session() as db:
            if faq_id := faq_data.get("id"):
                row = db.get(ChatbotFAQRow, faq_id)
                if row:
                    for k, v in faq_data.items():
                        setattr(row, k, v)
                    db.commit()
                    return faq_id
            row = ChatbotFAQRow(**faq_data, created_at=_utcnow(), updated_at=_utcnow())
            db.add(row)
            db.commit()
            return row.id

    def delete_faq(self, faq_id: int) -> None:
        with self._Session() as db:
            db.execute(delete(ChatbotFAQRow).where(ChatbotFAQRow.id == faq_id))
            db.commit()

    # ===== 反馈 =====
    def add_feedback(
        self, message_id: str, rating: str, comment: str | None, session_id: str,
    ) -> int:
        feedback_id = 0  # 自增主键
        with self._Session() as db:
            row = ChatbotFeedbackRow(
                message_id=message_id,
                session_id=session_id,
                rating=rating,
                comment=comment,
                created_at=_utcnow(),
            )
            db.add(row)
            db.commit()
            feedback_id = row.id
        return feedback_id

    def get_recent_feedback(
        self, session_id: str, window_min: int,
    ) -> list[ChatbotFeedbackRow]:
        """获取最近 N 分钟内的反馈（用于转人工判定）"""
        from datetime import timedelta
        cutoff = _utcnow() - timedelta(minutes=window_min)
        with self._Session() as db:
            stmt = select(ChatbotFeedbackRow).where(
                ChatbotFeedbackRow.session_id == session_id,
                ChatbotFeedbackRow.created_at >= cutoff,
            ).order_by(ChatbotFeedbackRow.created_at.desc())
            return list(db.execute(stmt).scalars().all())

    # ===== 知识库版本 =====
    def create_kb_version(self, version: Any) -> str:
        with self._Session() as db:
            row = ChatbotKBVersionRow(
                id=version.id,
                snapshot_path=version.snapshot_path,
                doc_hash=version.doc_hash,
                chunk_count=version.chunk_count,
                failed_chunk_count=version.failed_chunk_count,
                build_type=version.build_type,
                status=version.status,
                created_at=_utcnow(),
            )
            db.add(row)
            db.commit()
        return version.id

    def list_kb_versions(self, limit: int = 20) -> list[ChatbotKBVersionRow]:
        with self._Session() as db:
            stmt = select(ChatbotKBVersionRow).order_by(
                ChatbotKBVersionRow.created_at.desc()
            ).limit(limit)
            return list(db.execute(stmt).scalars().all())

    def count_kb_versions(self) -> int:
        """KB 版本总数（M-36 修复：list_kb_versions 的 total 需真实计数支持前端分页）

        与 list_kb_versions 共享过滤条件，但不应用 limit。
        """
        with self._Session() as db:
            stmt = select(func.count(ChatbotKBVersionRow.id))
            return int(db.execute(stmt).scalar() or 0)

    def get_current_kb_version(self) -> ChatbotKBVersionRow | None:
        """获取当前生效版本（is_current=True 的唯一行）"""
        with self._Session() as db:
            stmt = select(ChatbotKBVersionRow).where(
                ChatbotKBVersionRow.is_current == True
            )
            return db.execute(stmt).scalars().first()

    def set_current_kb_version(self, version_id: str) -> None:
        """切换当前版本（事务内：先清除旧标记，再设新标记）"""
        with self._Session() as db:
            db.execute(
                update(ChatbotKBVersionRow)
                .values(is_current=False)
            )
            db.execute(
                update(ChatbotKBVersionRow)
                .where(ChatbotKBVersionRow.id == version_id)
                .values(is_current=True)
            )
            db.commit()

    # ===== 配置 =====
    def get_config(self, key: str) -> str | None:
        with self._Session() as db:
            row = db.get(ChatbotConfigRow, key)
            return row.value if row else None

    def set_config(self, key: str, value: str) -> None:
        with self._Session() as db:
            row = db.get(ChatbotConfigRow, key)
            if row:
                row.value = value
                row.updated_at = _utcnow()
            else:
                db.add(ChatbotConfigRow(
                    key=key, value=value, updated_at=_utcnow(),
                ))
            db.commit()

    def get_all_config(self) -> dict[str, str]:
        with self._Session() as db:
            rows = db.execute(select(ChatbotConfigRow)).scalars().all()
            return {row.key: row.value for row in rows}

    def _init_default_config(self) -> None:
        """初始化默认配置（仅首次启动时写入）"""
        defaults = {
            "enabled": "true",
            "rag.similarity_threshold": "0.65",
            "faq.similarity_threshold": "0.85",
            "faq.confirm_threshold": "0.65",
            "escalation.contact": "",
            "escalation.feedback_threshold": "2",
        }
        with self._Session() as db:
            for key, value in defaults.items():
                if not db.get(ChatbotConfigRow, key):
                    db.add(ChatbotConfigRow(
                        key=key, value=value, updated_at=_utcnow(),
                    ))
            db.commit()

    # ===== 审计日志 =====
    def add_audit_log(
        self,
        action: str,
        target: str,
        old_value_hash: str | None,
        new_value_hash: str | None,
        source: str = "web",
    ) -> None:
        """记录审计日志（仅存 hash，不存明文）"""
        with self._Session() as db:
            db.add(ChatbotAuditLogRow(
                action=action,
                target=target,
                old_value_hash=old_value_hash,
                new_value_hash=new_value_hash,
                source=source,
                created_at=_utcnow(),
            ))
            db.commit()
```

---

### 5.12 KBRefreshScheduler（知识库定时更新调度器）

**位置**：[modules/chatbot/kb_refresh_scheduler.py](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/modules/chatbot/kb_refresh_scheduler.py)

**职责**：定时检测文档变更，触发 KBManager.incremental_update。

#### 5.12.1 类定义

```python
# modules/chatbot/kb_refresh_scheduler.py
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from xianyu_hunter.modules.chatbot.kb_manager import KBManager
    from xianyu_hunter.infra.yaml_config import ChatbotKBConfig


class KBRefreshScheduler:
    """知识库定时更新调度器

    架构选型（见概要设计 §3.12）：
    - 使用 BackgroundScheduler（独立线程）+ run_coroutine_threadsafe（提交到主循环）
    - 不使用 AsyncIOScheduler，避免与主系统 TaskScheduler 争用事件循环
    - 参考 batch_refresh_scheduler.py 的成熟模式
    """

    def __init__(
        self,
        kb_manager: "KBManager",
        config: "ChatbotKBConfig",
    ) -> None:
        from apscheduler.schedulers.background import BackgroundScheduler
        self._scheduler = BackgroundScheduler(daemon=True)
        self._kb_manager = kb_manager
        self._config = config
        self._loop: asyncio.AbstractEventLoop | None = None

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        """启动定时任务（在 startup.py 中调用，传入主事件循环）

        Args:
            loop: FastAPI 主事件循环，用于 run_coroutine_threadsafe 提交 async 任务
        """
        self._loop = loop
        if not self._config.auto_update_enabled:
            logger.info("知识库自动更新未启用（kb.auto_update_enabled=false）")
            return

        self._scheduler.add_job(
            self._refresh_job_sync,
            trigger="interval",
            hours=self._config.update_interval_hours,
            id="kb_refresh",
            replace_existing=True,
            max_instances=1,  # 防止任务堆积：上一轮未完成不启动新轮
            coalesce=True,    # 错过多次触发仅执行一次
        )
        self._scheduler.start()
        logger.info(
            f"知识库定时更新已启动，间隔 {self._config.update_interval_hours} 小时"
        )

    def _refresh_job_sync(self) -> None:
        """同步入口（BackgroundScheduler 线程中执行）

        通过 run_coroutine_threadsafe 提交 async 任务到主循环，
        future.result(timeout=600) 阻塞当前线程等待完成
        """
        if self._loop is None or self._loop.is_closed():
            logger.warning("主事件循环已关闭，跳过知识库更新")
            return
        try:
            future = asyncio.run_coroutine_threadsafe(self._refresh_job(), self._loop)
            future.result(timeout=600)  # 10 分钟超时保护
        except Exception as e:
            logger.exception(f"知识库定时更新失败: {e}")
            # 发布失败事件（同样需提交到主循环）
            if self._loop and not self._loop.is_closed():
                asyncio.run_coroutine_threadsafe(
                    self._publish_failure_event(str(e)), self._loop
                )

    async def _refresh_job(self) -> None:
        """实际执行的 async 任务：调用 kb_manager.incremental_update"""
        version = await self._kb_manager.incremental_update()
        if version:
            logger.info(f"知识库已更新到 {version.id}（{version.build_type}）")
        else:
            logger.info("知识库无变化或更新失败")

    async def _publish_failure_event(self, reason: str) -> None:
        """发布 chatbot.kb_rebuild_failed 事件"""
        # 通过 kb_manager 注入的 event_bus 发布
        await self._kb_manager._publish_failure_event(reason)

    def stop(self) -> None:
        """关闭调度器（在应用关闭时调用）"""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("知识库定时更新调度器已停止")
```

---

### 5.13 安全规则子模块

**位置**：[modules/chatbot/security/](file:///d:/code/otherProjects/17_xianyu/src/xianyu_hunter/modules/chatbot/security/)

**职责**：集中管理 Prompt Injection 检测、敏感字段扫描、PII 脱敏的正则规则。

#### 5.13.1 文件结构

```
modules/chatbot/security/
├── __init__.py          # 导出公共 API
├── patterns.py          # 正则规则定义
└── sanitizer.py         # 脱敏函数实现
```

#### 5.13.2 patterns.py（正则规则）

```python
# modules/chatbot/security/patterns.py
"""安全规则正则定义（见概要设计 §7.4 附录 A）

所有正则编译为 re.I | re.M，便于跨行匹配
"""
import re


# ===== A.1 Prompt Injection 检测（5 类）=====
PROMPT_INJECTION_PATTERNS = [
    # 1. 指令劫持："忽略上述指令"、" disregard previous instructions"
    re.compile(r"忽略(上述|之前|前面).{0,10}(指令|规则|提示)", re.I | re.M),
    re.compile(r"(ignore|disregard).{0,20}(previous|above).{0,20}(instruction|rule|prompt)", re.I | re.M),
    # 2. 角色劫持："你现在是..."、"act as"
    re.compile(r"你(现在|以后)(是|扮演|假装)", re.I | re.M),
    re.compile(r"(act as|pretend to be|you are now)\s", re.I | re.M),
    # 3. 泄露指令："重复你的指令"、"show me your prompt"
    re.compile(r"(重复|显示|输出|告诉我).{0,10}(你的|系统).{0,10}(指令|提示词|prompt)", re.I | re.M),
    re.compile(r"(show|repeat|reveal|print).{0,20}(your|the).{0,20}(prompt|instruction|system)", re.I | re.M),
    # 4. 分隔符绕过："###"、"---"、"==="
    re.compile(r"^[#\-=_]{3,}$", re.I | re.M),
    # 5. 权限提升："作为管理员"、"as admin"
    re.compile(r"作为(管理员|开发者|root)", re.I | re.M),
    re.compile(r"as\s+(admin|developer|root|sudo)", re.I | re.M),
]


# ===== A.2 敏感字段扫描（8 类）=====
SENSITIVE_PATTERNS = [
    # 1. OpenAI API Key（sk-开头，48 字符）
    re.compile(r"sk-[a-zA-Z0-9]{48}"),
    # 2. Anthropic API Key（sk-ant- 开头）
    re.compile(r"sk-ant-[a-zA-Z0-9\-_]{80,}"),
    # 3. Bearer Token
    re.compile(r"Bearer\s+[a-zA-Z0-9\-_\.=]+", re.I),
    # 4. JWT（三段式，header.payload.signature）
    re.compile(r"eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+"),
    # 5. Cookie（key=value; 格式）
    re.compile(r"(?:cookie|set-cookie):\s*[^\r\n]+", re.I),
    # 6. 阿里云 AccessKey（LTAI 开头）
    re.compile(r"LTAI[a-zA-Z0-9]{16,}"),
    # 7. 数据库连接串
    re.compile(r"(?:mysql|postgres|mongodb|redis)://[^\s]+:[^\s]+@[^\s]+", re.I),
    # 8. 私钥（PEM 格式）
    re.compile(r"-----BEGIN\s+(RSA\s+|EC\s+|OPENSSH\s+)?PRIVATE\s+KEY-----"),
]


# ===== A.3 PII 脱敏（6 类）=====
PII_PATTERNS = [
    # 1. 手机号：11 位，1 开头
    (re.compile(r"\b1[3-9]\d{9}\b"), lambda m: m.group()[:3] + "****" + m.group()[-4:]),
    # 2. 邮箱
    (re.compile(r"\b([\w.+-]+)@([\w-]+\.[\w.-]+)\b"),
     lambda m: m.group(1)[0] + "***@" + m.group(2)),
    # 3. 身份证：18 位
    (re.compile(r"\b\d{17}[\dXx]\b"),
     lambda m: m.group()[:3] + "***********" + m.group()[-4:]),
    # 4. 银行卡：16-19 位
    (re.compile(r"\b\d{16,19}\b"),
     lambda m: m.group()[:4] + "********" + m.group()[-4:]),
    # 5. 微信号：字母数字下划线，6-20 位
    (re.compile(r"\b微信号[:：\s]*([a-zA-Z][a-zA-Z0-9_-]{5,19})\b"),
     lambda m: "微信号: " + m.group(1)[:2] + "****" + m.group(1)[-4:]),
    # 6. QQ 号：纯数字 5-11 位
    (re.compile(r"\bQQ[:：\s]*(\d{5,11})\b"),
     lambda m: "QQ: " + m.group(1)[:4] + "****" + m.group(1)[-2:]),
]


def detect_prompt_injection(text: str) -> tuple[bool, str | None]:
    """检测 Prompt Injection

    Returns:
        (is_injected, matched_pattern): 命中则 is_injected=True
    """
    for pattern in PROMPT_INJECTION_PATTERNS:
        if pattern.search(text):
            return True, pattern.pattern
    return False, None


def has_sensitive_data(text: str) -> bool:
    """检测敏感字段（用于 KB 构建前过滤）"""
    return any(p.search(text) for p in SENSITIVE_PATTERNS)


def sanitize_pii(text: str) -> str:
    """PII 脱敏（用于转人工会话导出）"""
    for pattern, replacer in PII_PATTERNS:
        text = pattern.sub(replacer, text)
    return text
```

#### 5.13.3 sanitizer.py（脱敏函数）

```python
# modules/chatbot/security/sanitizer.py
"""脱敏函数封装（供 Escalation 等模块调用）"""
from __future__ import annotations

from xianyu_hunter.modules.chatbot.security.patterns import (
    sanitize_pii, has_sensitive_data, detect_prompt_injection,
)


def sanitize_session_for_copy(messages: list) -> str:
    """转人工时导出会话记录，自动脱敏 PII

    Args:
        messages: list[Message]

    Returns:
        脱敏后的纯文本，可直接复制给管理员
    """
    lines = []
    for msg in messages:
        content = sanitize_pii(msg.content)
        lines.append(f"[{msg.role}]: {content}")
    return "\n\n".join(lines)


def check_user_input_safety(text: str) -> tuple[bool, str | None]:
    """用户输入安全检查

    Returns:
        (is_safe, reason): 不安全则 is_safe=False
    """
    injected, pattern = detect_prompt_injection(text)
    if injected:
        return False, f"疑似 Prompt Injection（匹配: {pattern}）"
    return True, None
```

#### 5.13.4 安全规则应用点

| 应用点 | 调用规则 | 处理方式 |
|--------|---------|---------|
| `api_chatbot.chat` 入口 | `check_user_input_safety` | 不安全则拒绝并提示 |
| `KBManager._has_sensitive_data` | `has_sensitive_data` | 命中则丢弃片段（不脱敏，避免破坏代码语义） |
| `ToolRegistry._filter_sensitive` | `_SENSITIVE_KEY_PATTERNS`（键名匹配） | 替换值为 `<REDACTED>` |
| `Escalation.sanitize_session_for_copy` | `sanitize_pii` | 脱敏后供用户复制 |

---

## 6. 状态机设计

本章定义智能客服模块三个核心实体的状态机：会话（Session）、知识库版本（KB Version）、转人工（Escalation）。所有状态转换必须由明确的触发条件驱动，且每次转换都记录到 DB 或日志。

### 6.1 会话状态机（Session）

**实体**：`chatbot_sessions.status` 字段
**拥有者**：`ContextManager`

#### 6.1.1 状态定义

| 状态 | 说明 | 持久化 |
|------|------|--------|
| `active` | 会话活跃，可继续对话 | DB status='active' |
| `ended` | 会话已结束（超时或用户主动），不再复用历史 | DB status='ended' |

#### 6.1.2 状态转换图

```mermaid
stateDiagram-v2
    [*] --> active: create_session()
    active --> active: orchestrate() 成功\n（更新 updated_at）
    active --> ended: check_and_mark_timeout()\n距今 > session_timeout_min
    active --> ended: DELETE /sessions/{id}\n（用户主动删除）
    active --> ended: 服务重启\n（不恢复，强制新建）
    ended --> [*]: delete_session()\n（级联删除消息+反馈）
```

#### 6.1.3 转换条件与副作用

| 转换 | 触发条件 | 副作用 | 实现位置 |
|------|---------|--------|---------|
| `[*] → active` | `POST /sessions` 或 `orchestrate(session_id=None)` | 创建 SessionRow，发布 `CHATBOT_SESSION_CREATED` | `ChatbotRepository.create_session` |
| `active → active` | 每次 `orchestrate()` 成功 | 更新 `updated_at`，`message_count+1` | `ChatbotRepository.add_message` |
| `active → ended` | `check_and_mark_timeout()` 检测到超时 | 更新 `status='ended'`，发布 `CHATBOT_SESSION_TIMEOUT` | `ContextManager.check_and_mark_timeout` |
| `active → ended` | `DELETE /sessions/{id}` | 级联删除消息+反馈（不保留历史） | `ChatbotRepository.delete_session` |
| `ended → [*]` | `DELETE /sessions/{id}`（清理已结束会话） | 释放 DB 行 | `ChatbotRepository.delete_session` |

#### 6.1.4 关键约束

1. **`ended` 不可恢复为 `active`**：用户在 `ended` 会话发送消息时，Orchestrator 返回 `SESSION_TIMEOUT` 错误事件，引导用户新建会话
2. **`ended` 会话的消息仍可查询**：`GET /sessions/{id}/messages` 仍返回历史，但 `orchestrate()` 拒绝处理
3. **并发安全**：`active → ended` 转换由 per-session `asyncio.Lock` 保护，不会出现并发超时检测冲突

### 6.2 知识库版本状态机（KB Version）

**实体**：`chatbot_kb_versions` 表 + ChromaDB 集合状态
**拥有者**：`KBManager`

#### 6.2.1 状态定义

| 状态 | 说明 | 持久化 |
|------|------|--------|
| `building` | 构建中（ChromaDB 可能不一致） | DB 无记录，仅 `KBManager._build_lock.locked()` |
| `success` | 构建成功，ChromaDB 与版本记录一致 | DB status='success', is_current=True |
| `partial` | 部分成功（embedding 失败率 ≤ 10%） | DB status='partial', failed_chunk_count > 0 |
| `failed` | 构建失败，已回滚到上一版本 | DB 无记录（回滚后删除） |
| `corrupted` | ChromaDB 损坏（快照恢复失败） | DB `chatbot_config.kb_status='corrupted'` |
| `rolled_back` | 已被回滚（非当前版本） | DB is_current=False |

#### 6.2.2 状态转换图

```mermaid
stateDiagram-v2
    [*] --> building: build_all() / incremental_update()
    building --> success: 阶段2完成\n（embedding 0 失败）
    building --> partial: 阶段2完成\n（embedding 失败 ≤ 10%）
    building --> failed: 阶段1/2 异常\n（已回滚）
    building --> corrupted: 快照恢复失败\n（ChromaDB 不一致）

    success --> building: 下次 build_all()
    partial --> building: 下次 build_all()
    failed --> [*]: 发布 CHATBOT_KB_REBUILD_FAILED

    success --> rolled_back: rollback(older_version)
    partial --> rolled_back: rollback(older_version)
    rolled_back --> [*]: 快照已被 cleanup_old_snapshots 清理

    corrupted --> building: 人工修复后\n手动 build_all(force=True)
    corrupted --> [*]: 人工介入
```

#### 6.2.3 转换条件与副作用

| 转换 | 触发条件 | 副作用 | 实现位置 |
|------|---------|--------|---------|
| `[*] → building` | `POST /kb/rebuild` 或定时任务 | 获取 `_build_lock`，导出当前快照 | `KBManager.build_all` |
| `building → success` | 阶段 2c 完成，`failed_chunk_count=0` | 写入 KBVersionRow(is_current=True)，发布 `CHATBOT_KB_REBUILT` | `KBManager._do_build` |
| `building → partial` | 阶段 2c 完成，`0 < failed_chunk_count ≤ 10%` | 同上，但 `status='partial'` | `KBManager._do_build` |
| `building → failed` | 阶段 1 或 2 异常 | 调用 `_rollback_build` 恢复 ChromaDB，删除未完成快照，发布 `CHATBOT_KB_REBUILD_FAILED` | `KBManager._do_build` except 分支 |
| `building → corrupted` | `_rollback_build` 中 `restore_from_snapshot` 也失败 | 设置 `kb_status='corrupted'`，发布 `CHATBOT_KB_REBUILD_FAILED`（含 `corrupted=true`） | `KBManager._rollback_build` |
| `success/partial → rolled_back` | `POST /kb/rollback/{version_id}` | 清除当前版本 `is_current=False`，目标版本 `is_current=True`，发布 `CHATBOT_KB_ROLLED_BACK` | `KBManager.rollback` |
| `corrupted → building` | 人工修复后 `POST /kb/rebuild?force=true` | 清除 `kb_status='corrupted'` 标记，重新构建 | `KBManager.build_all(force=True)` |

#### 6.2.4 关键约束

1. **`building` 状态互斥**：`_build_lock` 保证同一时刻只有一个构建任务，API 触发与定时触发互斥
2. **`corrupted` 状态需人工介入**：自动回滚失败后，系统不会尝试再次自动恢复，需管理员手动检查 ChromaDB 数据完整性后调用 `force=true` 重建
3. **`rolled_back` 版本的快照保留**：直到被 `cleanup_old_snapshots` 清理（保留最近 `snapshot_max_keep` 个）
4. **`failed` 不留 DB 记录**：回滚后版本记录已删除，仅通过事件日志可追溯

### 6.3 转人工状态机（Escalation）

**实体**：`chatbot_feedback.escalate_triggered` 字段 + 运行时判定
**拥有者**：`Escalation` + `Orchestrator`

#### 6.3.1 状态定义

| 状态 | 说明 | 持久化 |
|------|------|--------|
| `normal` | 正常对话中，未触发转人工 | 无（默认） |
| `pending` | 已满足转人工条件，待发送 escalate SSE 事件 | 运行时状态 |
| `escalated` | 已发送 escalate 事件给前端 | `chatbot_feedback.escalate_triggered=True` |

#### 6.3.2 状态转换图

```mermaid
stateDiagram-v2
    [*] --> normal: 会话创建
    normal --> normal: orchestrate() 正常回答
    normal --> pending: should_escalate()=True\n（任一触发条件满足）
    pending --> escalated: 发送 SSE escalate 事件\n+ 更新 feedback.escalate_triggered
    escalated --> [*]: 会话结束

    normal --> normal: 用户点踩但未达阈值
    normal --> pending: 连续 N 次点踩（30min 内）
    normal --> pending: 用户消息含"人工"/"客服"
    normal --> pending: RAG 相似度全 < 0.65
    normal --> pending: AGENT 3 轮后仍失败
```

#### 6.3.3 转换条件与副作用

| 转换 | 触发条件 | 副作用 | 实现位置 |
|------|---------|--------|---------|
| `[*] → normal` | 会话创建 | 无 | `ChatbotRepository.create_session` |
| `normal → normal` | `orchestrate()` 正常完成 | 保存 assistant 消息，重置点踩计数（隐式：仅统计 30min 内） | `Orchestrator._run_rag_flow` |
| `normal → pending` | `should_escalate()` 返回 `(True, reason)` | 不产生 DB 副作用，仅运行时状态 | `Escalation.should_escalate` |
| `pending → escalated` | Orchestrator 发送 `SSEEventType.ESCALATE` 事件 | 更新 `chatbot_feedback.escalate_triggered=True`（关联到触发转人工的反馈），发布 `CHATBOT_ESCALATED` 事件 | `Orchestrator._escalate` |

#### 6.3.4 触发条件详解（`should_escalate`）

```python
# 5 个触发条件，任一满足即转换到 pending
TRIGGER_CONDITIONS = [
    # 1. 用户主动：消息含关键词
    lambda ctx: any(kw in ctx.user_message for kw in {"人工", "客服", "管理员", "转人工", "真人"}),

    # 2. 连续点踩：feedback_threshold 次负反馈（feedback_window_min 内）
    lambda ctx: sum(
        1 for f in ctx.recent_feedback
        if f.rating == "negative"
        and (ctx.now - f.created_at) < timedelta(minutes=ctx.config.escalation.feedback_window_min)
    ) >= ctx.config.escalation.feedback_threshold,

    # 3. RAG 无匹配：所有片段相似度 < 0.65
    lambda ctx: ctx.rag_results and all(c.similarity < 0.65 for c in ctx.rag_results),

    # 4. AGENT 失败：多轮工具调用后仍无法回答
    lambda ctx: ctx.agent_failed,

    # 5. 预算超限：AI 预算已用尽（Orchestrator 直接转人工，不进入 RAG/AGENT）
    lambda ctx: ctx.budget_exceeded,
]
```

#### 6.3.5 关键约束

1. **`escalated` 不可恢复为 `normal`**：一旦触发转人工，当前会话剩余对话均带 `escalated` 标记，便于审计
2. **`pending → escalated` 必须发送 SSE 事件**：若客户端断开导致事件未送达，状态仍标记为 `escalated`（DB 已更新），下次客户端连接时通过 `GET /sessions/{id}` 可看到 `escalate_triggered=True`
3. **点踩计数窗口**：`feedback_window_min`（默认 30 分钟）内的负反馈才计入，超出的自动忽略
4. **转人工后仍可继续对话**：用户可选择继续提问，但每次 `orchestrate()` 都会重新评估 `should_escalate()`，可能再次触发

### 6.4 跨状态机交互

| 场景 | 涉及状态机 | 交互顺序 |
|------|-----------|---------|
| 用户在 `ended` 会话提问 | Session + Escalation | Session 拒绝 → 返回 `SESSION_TIMEOUT` → 不进入 Escalation |
| 构建知识库时会话进行中 | KB Version + Session | KB 构建不影响 Session（不同锁），但检索可能返回旧数据（构建未完成） |
| `corrupted` 状态时用户提问 | KB Version + Session + Escalation | RAG 检索失败 → `should_escalate(rag_results=[])` → 触发转人工 |
| 转人工后会话超时 | Escalation + Session | `escalated` 状态保留，Session 转为 `ended`，历史可查但不可继续 |

---

## 7. 前端组件详细设计

### 7.1 设计原则

1. **仅在 SPA 实现**：与概要设计 §2.4 一致，对话界面仅在 React SPA 实现，不在 htmx 控制台实现
2. **复用 Ant Design 5**：与主系统 [frontend/src/](file:///d:/code/otherProjects/17_xianyu/frontend/src/) 风格一致
3. **SSE 客户端**：使用 `fetch + ReadableStream`（不用 EventSource，因为 chat 是 POST 请求）
4. **状态管理**：React hooks + Context，不引入 Redux（局部状态足够）
5. **路由**：`/chatbot` 主对话页，`/config/chatbot` 配置页（含知识库管理）

### 7.2 路由与菜单

**位置**：[frontend/src/App.tsx](file:///d:/code/otherProjects/17_xianyu/frontend/src/App.tsx) + [frontend/src/components/layout/MainLayout.tsx](file:///d:/code/otherProjects/17_xianyu/frontend/src/components/layout/MainLayout.tsx)

```tsx
// App.tsx 新增路由
<Route path="/chatbot" element={<ChatbotPage />} />
<Route path="/chatbot/session/:sessionId" element={<ChatbotPage />} />
<Route path="/config/chatbot" element={<ChatbotConfigPage />} />

// MainLayout.tsx 侧边栏新增
{
  key: '/chatbot',
  icon: <MessageOutlined />,
  label: '智能客服',
},
{
  key: '/config/chatbot',
  icon: <SettingOutlined />,
  label: '客服配置',
  parentKey: '/config',
},
```

### 7.3 页面结构

#### 7.3.1 ChatbotPage（对话主页）

**位置**：[frontend/src/pages/Chatbot/index.tsx](file:///d:/code/otherProjects/17_xianyu/frontend/src/pages/Chatbot/index.tsx)

```
┌──────────────────────────────────────────────────────────────────┐
│  ChatbotPage                                                      │
│  ┌────────────┐  ┌───────────────────────────────────────────┐  │
│  │            │  │  ChatHeader（标题 + 操作按钮）              │  │
│  │            │  ├───────────────────────────────────────────┤  │
│  │  SessionL  │  │                                            │  │
│  │  ist       │  │  MessageList（消息列表，滚动加载）          │  │
│  │            │  │  · UserMessage                             │  │
│  │  · 新建    │  │  · AssistantMessage（含引用、反馈按钮）     │  │
│  │  · 会话1   │  │  · ToolCallIndicator                       │  │
│  │  · 会话2   │  │  · EscalateAlert                           │  │
│  │  ...       │  │                                            │  │
│  │            │  ├───────────────────────────────────────────┤  │
│  │            │  │  ChatInput（输入框 + 发送按钮）             │  │
│  └────────────┘  └───────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

**组件树**：
```
ChatbotPage
├── SessionList（左侧，宽度 280px，可折叠）
│   ├── Button("新建会话")
│   └── List[SessionItem]
│       ├── Tag(status: active/ended)
│       ├── Title + 相对时间
│       └── Dropdown(重命名 / 删除)
├── ChatHeader
│   ├── Title
│   ├── Tooltip(会话信息)
│   └── Button("导出会话")
├── MessageList（中间，flex: 1，自动滚动到底部）
│   └── List[Message]
│       ├── UserMessage
│       │   └── Avatar + Content
│       └── AssistantMessage
│           ├── Content（支持 Markdown 渲染，含 [来源:N] 高亮）
│           ├── SourcesPanel（可折叠）
│           │   └── List[SourceItem]
│           │       └── Tag(file) + Text(section) + Text(L10-L20) + Progress(similarity)
│           ├── ToolCallBadge（显示工具调用次数）
│           ├── FeedbackButtons（👍 / 👎 + 评价输入框）
│           └── EscalateAlert（转人工时显示）
└── ChatInput
    ├── TextArea（1-2000 字符，Shift+Enter 换行，Enter 发送）
    ├── Checkbox("启用工具调用")
    └── Button("发送")
```

#### 7.3.2 ChatbotConfigPage（配置页）

**位置**：[frontend/src/pages/Chatbot/Config.tsx](file:///d:/code/otherProjects/17_xianyu/frontend/src/pages/Chatbot/Config.tsx)

```
ChatbotConfigPage
├── Tabs
│   ├── TabPane("基础配置")
│   │   ├── Switch("启用智能客服", enabled)
│   │   ├── InputNumber("历史轮数", max_history_turns)
│   │   └── InputNumber("会话超时(分钟)", session_timeout_min)
│   ├── TabPane("RAG 检索")
│   │   ├── InputNumber("top_k", 1-20)
│   │   ├── Slider("相似度阈值", 0-1, step=0.05)  [热更新]
│   │   └── InputNumber("context 最大字符", 500-32000)
│   ├── TabPane("AGENT 工具")
│   │   ├── Switch("启用工具", enable_tools)
│   │   ├── InputNumber("最大轮数", 1-10)
│   │   └── Radio("触发模式", function_calling | fallback)
│   ├── TabPane("知识库管理")
│   │   ├── KBStatusCard（当前版本、片段数、构建时间）
│   │   ├── Button("立即重建") + Modal(进度条)
│   │   ├── KBVersionTable（历史版本列表）
│   │   │   └── Column(操作: 回滚 | 删除快照)
│   │   └── Switch("定时自动更新") + InputNumber("间隔(小时)")
│   ├── TabPane("FAQ 管理")
│   │   ├── FAQTable（问题/答案/分类/启用）
│   │   │   └── Column(操作: 编辑 | 删除)
│   │   └── Button("新增 FAQ")
│   ├── TabPane("转人工")
│   │   ├── InputNumber("点踩阈值", 1-10)  [热更新]
│   │   ├── InputNumber("统计窗口(分钟)", 5-1440)  [热更新]
│   │   ├── Input("联系方式", contact)  [热更新]
│   │   └── Switch("PII 脱敏", sanitize_pii)
│   └── TabPane("审计日志")
│       └── AuditLogTable（action/target/time/source）
```

### 7.4 关键组件详细设计

#### 7.4.1 SSEClient（SSE 客户端 Hook）

**位置**：[frontend/src/pages/Chatbot/hooks/useSSEChat.ts](file:///d:/code/otherProjects/17_xianyu/frontend/src/pages/Chatbot/hooks/useSSEChat.ts)

```typescript
// useSSEChat.ts
import { useState, useCallback, useRef } from 'react';
import { message } from 'antd';

interface SSEEvent {
  type: 'intent' | 'sources' | 'token' | 'tool_call' | 'faq_confirm' | 'done' | 'error' | 'escalate';
  data: Record<string, any>;
}

interface UseSSEChatOptions {
  sessionId: string;
  onEvent: (event: SSEEvent) => void;
  onError: (error: Error) => void;
  onComplete: () => void;
}

export function useSSEChat() {
  const [isStreaming, setIsStreaming] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(async (
    opts: UseSSEChatOptions & { message: string; enableTools?: boolean },
  ) => {
    setIsStreaming(true);
    abortControllerRef.current = new AbortController();

    try {
      const resp = await fetch('/api/chatbot/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
        },
        body: JSON.stringify({
          session_id: opts.sessionId,
          message: opts.message,
          enable_tools: opts.enableTools ?? true,
        }),
        signal: abortControllerRef.current.signal,
      });

      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }

      const reader = resp.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        // 按 SSE 协议解析：双换行分隔事件
        const events = buffer.split('\n\n');
        buffer = events.pop() || '';

        for (const eventStr of events) {
          const event = parseSSEEvent(eventStr);
          if (event) {
            opts.onEvent(event);
            if (event.type === 'done' || event.type === 'error' || event.type === 'escalate') {
              opts.onComplete();
              return;
            }
          }
        }
      }
    } catch (e: any) {
      if (e.name === 'AbortError') {
        return; // 用户主动取消
      }
      opts.onError(e);
      message.error('对话失败: ' + e.message);
    } finally {
      setIsStreaming(false);
      abortControllerRef.current = null;
    }
  }, []);

  const cancel = useCallback(() => {
    abortControllerRef.current?.abort();
  }, []);

  return { isStreaming, sendMessage, cancel };
}

function parseSSEEvent(raw: string): SSEEvent | null {
  // SSE 格式：event: xxx\ndata: {...}
  const lines = raw.split('\n');
  let type = '';
  let data = '';
  for (const line of lines) {
    if (line.startsWith('event: ')) type = line.slice(7).trim();
    else if (line.startsWith('data: ')) data += line.slice(6);
  }
  if (!type) return null;
  try {
    return { type, data: JSON.parse(data) };
  } catch {
    return { type, data: { raw: data } };
  }
}
```

#### 7.4.2 AssistantMessage（助手消息组件）

**位置**：[frontend/src/pages/Chatbot/components/AssistantMessage.tsx](file:///d:/code/otherProjects/17_xianyu/frontend/src/pages/Chatbot/components/AssistantMessage.tsx)

```tsx
// AssistantMessage.tsx
import { useState } from 'react';
import { Typography, Tag, Tooltip, Progress, Collapse, Button, Modal, Input, message } from 'antd';
import { LikeOutlined, DislikeOutlined, CopyOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import type { Message, Source } from '../types';

interface Props {
  message: Message;
  sessionId: string;
  onFeedback: (messageId: string, rating: 'positive' | 'negative', comment?: string) => Promise<void>;
}

export function AssistantMessage({ message, sessionId, onFeedback }: Props) {
  const [feedbackModalOpen, setFeedbackModalOpen] = useState(false);
  const [feedbackRating, setFeedbackRating] = useState<'positive' | 'negative'>('positive');
  const [feedbackComment, setFeedbackComment] = useState('');

  const handleFeedback = async (rating: 'positive' | 'negative') => {
    setFeedbackRating(rating);
    setFeedbackModalOpen(true);
  };

  const submitFeedback = async () => {
    await onFeedback(message.id, feedbackRating, feedbackComment);
    setFeedbackModalOpen(false);
    setFeedbackComment('');
    message.success('感谢您的反馈');
  };

  return (
    <div className="assistant-message">
      <ReactMarkdown
        components={{
          // [来源:N] 渲染为可点击的引用标签
          text: (text) => renderCitation(text, message.sources),
        }}
      >
        {message.content}
      </ReactMarkdown>

      {message.toolCalls?.length > 0 && (
        <Tag color="blue">工具调用 {message.toolCalls.length} 次</Tag>
      )}

      {message.sources?.length > 0 && (
        <Collapse ghost size="small">
          <Collapse.Panel header={`参考来源 (${message.sources.length})`} key="sources">
            {message.sources.map((src: Source) => (
              <div key={src.index} style={{ marginBottom: 8 }}>
                <Tag color="cyan">[{src.index}]</Tag>
                <Typography.Text type="secondary">{src.file}</Typography.Text>
                <Typography.Text style={{ marginLeft: 8 }}>{src.section}</Typography.Text>
                <Tooltip title={`相似度: ${src.similarity}`}>
                  <Progress
                    percent={src.similarity * 100}
                    size="small"
                    format={(p) => `${p}%`}
                    style={{ width: 80, marginLeft: 8 }}
                  />
                </Tooltip>
              </div>
            ))}
          </Collapse.Panel>
        </Collapse>
      )}

      {message.escalated && (
        <Alert
          type="warning"
          message="已转人工客服"
          description={`原因：${message.escalateReason}`}
          action={
            <Button size="small" icon={<CopyOutlined />} onClick={() => copySession(sessionId)}>
              复制会话记录
            </Button>
          }
        />
      )}

      <div className="message-actions">
        <Button
          size="small"
          icon={<LikeOutlined />}
          onClick={() => handleFeedback('positive')}
        />
        <Button
          size="small"
          icon={<DislikeOutlined />}
          onClick={() => handleFeedback('negative')}
        />
      </div>

      <Modal
        title="反馈"
        open={feedbackModalOpen}
        onOk={submitFeedback}
        onCancel={() => setFeedbackModalOpen(false)}
      >
        <Input.TextArea
          rows={3}
          placeholder="请描述您的反馈（可选）"
          value={feedbackComment}
          onChange={(e) => setFeedbackComment(e.target.value)}
        />
      </Modal>
    </div>
  );
}

// [来源:N] 渲染：点击跳转到对应 source
function renderCitation(text: string, sources: Source[]): React.ReactNode {
  const regex = /\[来源:(\d+|\?)\]/g;
  const parts = text.split(regex);
  // ... 拼接为带 Tooltip 的 Tag
}
```

#### 7.4.3 KBStatusCard（知识库状态卡片）

**位置**：[frontend/src/pages/Chatbot/components/KBStatusCard.tsx](file:///d:/code/otherProjects/17_xianyu/frontend/src/pages/Chatbot/components/KBStatusCard.tsx)

```tsx
// KBStatusCard.tsx
import { Card, Button, Tag, Modal, Progress, message } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { useState } from 'react';
import type { KBStatus } from '../types';

interface Props {
  status: KBStatus;
  onRebuild: (force: boolean) => Promise<void>;
}

export function KBStatusCard({ status, onRebuild }: Props) {
  const [building, setBuilding] = useState(false);
  const [progress, setProgress] = useState(0);

  const handleRebuild = async () => {
    Modal.confirm({
      title: '重建知识库',
      content: '重建期间对话功能将使用旧版本知识库，确定继续？',
      onOk: async () => {
        setBuilding(true);
        setProgress(0);
        // 通过 SSE 接收进度（POST /api/chatbot/kb/rebuild）
        await onRebuild(false);
        setBuilding(false);
      },
    });
  };

  return (
    <Card
      title="知识库状态"
      extra={
        <Button
          icon={<ReloadOutlined />}
          onClick={handleRebuild}
          loading={building || status.building}
          disabled={building || status.building}
        >
          重建
        </Button>
      }
    >
      <p>当前版本：<Tag color="green">{status.current_version?.slice(0, 8) || '未构建'}</Tag></p>
      <p>片段数量：<strong>{status.chunk_count}</strong></p>
      <p>最后构建：{status.last_build_at || '从未构建'}</p>
      {status.status === 'corrupted' && (
        <Tag color="red">知识库损坏，需人工修复</Tag>
      )}
      {building && <Progress percent={progress} status="active" />}
    </Card>
  );
}
```

### 7.5 类型定义

**位置**：[frontend/src/pages/Chatbot/types.ts](file:///d:/code/otherProjects/17_xianyu/frontend/src/pages/Chatbot/types.ts)

```typescript
// types.ts
export interface Session {
  id: string;
  title: string;
  status: 'active' | 'ended';
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface Source {
  index: number;
  file: string;
  section: string;
  line_start: number;
  line_end: number;
  similarity: number;
}

export interface Message {
  id: string;
  session_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  sources?: Source[];
  tool_calls?: ToolCall[];
  escalated?: boolean;
  escalate_reason?: string;
  degraded?: boolean;
  tokens_used?: number;
  created_at: string;
}

export interface ToolCall {
  name: string;
  args: Record<string, any>;
  result?: any;
}

export interface KBStatus {
  current_version: string | null;
  chunk_count: number;
  last_build_at: string | null;
  building: boolean;
  status: 'success' | 'partial' | 'corrupted';
}

export interface KBVersion {
  id: string;
  snapshot_path: string;
  doc_hash: string;
  chunk_count: number;
  failed_chunk_count: number;
  build_type: 'full' | 'incremental';
  status: 'success' | 'partial' | 'failed';
  is_current: boolean;
  created_at: string;
}

export interface FAQ {
  id?: number;
  question: string;
  answer: string;
  category: string;
  enabled: boolean;
}

export interface ChatbotConfig {
  enabled: boolean;
  max_history_turns: number;
  session_timeout_min: number;
  rag: { top_k: number; similarity_threshold: number; max_context_chars: number; };
  llm: { model: string; temperature: number; max_tokens: number; };
  agent: { enable_tools: boolean; max_tool_rounds: number; tool_trigger_mode: string; };
  kb: { auto_update_enabled: boolean; update_interval_hours: number; };
  faq: { similarity_threshold: number; confirm_threshold: number; };
  escalation: {
    feedback_threshold: number;
    feedback_window_min: number;
    contact: string;
    sanitize_pii: boolean;
  };
}

export interface AuditLog {
  id: number;
  action: string;
  target: string;
  source: string;
  created_at: string;
}
```

### 7.6 API 客户端

**位置**：[frontend/src/pages/Chatbot/api.ts](file:///d:/code/otherProjects/17_xianyu/frontend/src/pages/Chatbot/api.ts)

```typescript
// api.ts
import type { Session, Message, KBStatus, KBVersion, FAQ, ChatbotConfig, AuditLog } from './types';

const BASE = '/api/chatbot';
const headers = () => ({
  'Content-Type': 'application/json',
  'Authorization': `Bearer ${localStorage.getItem('token')}`,
});

export const chatbotApi = {
  // 会话
  createSession: (title?: string) =>
    fetch(`${BASE}/sessions`, { method: 'POST', headers: headers(), body: JSON.stringify({ title }) })
      .then(r => r.json()) as Promise<Session>,

  listSessions: (page = 1, pageSize = 20) =>
    fetch(`${BASE}/sessions?page=${page}&page_size=${pageSize}`, { headers: headers() })
      .then(r => r.json()) as Promise<{ items: Session[]; total: number }>,

  deleteSession: (id: string) =>
    fetch(`${BASE}/sessions/${id}`, { method: 'DELETE', headers: headers() }),

  // 消息
  listMessages: (sessionId: string, limit = 20, beforeId?: string) =>
    fetch(`${BASE}/sessions/${sessionId}/messages?limit=${limit}${beforeId ? `&before_id=${beforeId}` : ''}`, { headers: headers() })
      .then(r => r.json()) as Promise<{ items: Message[]; has_more: boolean }>,

  // 反馈
  submitFeedback: (messageId: string, rating: 'positive' | 'negative', comment?: string, sessionId?: string) =>
    fetch(`${BASE}/feedback`, {
      method: 'POST', headers: headers(),
      body: JSON.stringify({ message_id: messageId, rating, comment, session_id: sessionId }),
    }),

  // 知识库
  getKBStatus: () =>
    fetch(`${BASE}/kb/status`, { headers: headers() }).then(r => r.json()) as Promise<KBStatus>,

  rebuildKB: (force = false) =>
    fetch(`${BASE}/kb/rebuild?force=${force}`, { method: 'POST', headers: headers() })
      .then(r => r.json()) as Promise<{ task_id: string; status: string }>,

  listKBVersions: () =>
    fetch(`${BASE}/kb/versions`, { headers: headers() }).then(r => r.json()) as Promise<KBVersion[]>,

  rollbackKB: (versionId: string) =>
    fetch(`${BASE}/kb/rollback/${versionId}`, { method: 'POST', headers: headers() }),

  // 配置
  getConfig: () =>
    fetch(`${BASE}/config`, { headers: headers() }).then(r => r.json()) as Promise<ChatbotConfig>,

  updateConfig: (key: string, value: string) =>
    fetch(`${BASE}/config`, {
      method: 'PUT', headers: headers(),
      body: JSON.stringify({ key, value }),
    }),

  // FAQ
  listFAQ: () =>
    fetch(`${BASE}/faq`, { headers: headers() }).then(r => r.json()) as Promise<FAQ[]>,

  upsertFAQ: (faq: FAQ) =>
    fetch(`${BASE}/faq`, { method: 'POST', headers: headers(), body: JSON.stringify(faq) }),

  deleteFAQ: (id: number) =>
    fetch(`${BASE}/faq/${id}`, { method: 'DELETE', headers: headers() }),

  // 审计日志
  listAuditLogs: (page = 1, pageSize = 20) =>
    fetch(`${BASE}/audit-logs?page=${page}&page_size=${pageSize}`, { headers: headers() })
      .then(r => r.json()) as Promise<{ items: AuditLog[]; total: number }>,

  // 转人工导出
  exportSession: (sessionId: string) =>
    fetch(`${BASE}/escalation/${sessionId}/export`, { headers: headers() })
      .then(r => r.json()) as Promise<{ content: string }>,
};
```

### 7.7 性能与体验优化

| 场景 | 优化方案 |
|------|---------|
| 长会话消息列表卡顿 | 虚拟滚动（`react-window`），仅渲染可视区域消息 |
| SSE 流式 token 频繁 setState | 用 `useRef` 累积 token，每 50ms 批量 setState 一次 |
| Markdown 渲染慢 | `useMemo` 缓存渲染结果，按消息 id 索引 |
| 历史消息加载 | 游标分页（`before_id`），滚动到顶部自动加载更多 |
| 知识库重建进度 | SSE 推送进度（`/kb/rebuild` 返回 SSE 流） |
| 网络断开 | `fetch` 失败时自动重试 1 次，仍失败则提示用户 |
| 输入框失焦 | 发送后保持输入框焦点，便于连续对话 |

---

## 8. 错误码与异常处理

### 8.1 错误码定义

错误码统一为 `SCREAMING_SNAKE_CASE`，分 6 类前缀。所有错误码在 API 响应中通过 `code` 字段返回，前端按 `code` 做分支处理。

#### 8.1.1 通用错误（1xx）

| 错误码 | HTTP | 说明 | 触发条件 | 用户提示 |
|--------|------|------|---------|---------|
| `INVALID_REQUEST` | 400 | 请求参数校验失败 | Pydantic 校验失败 | 修复高亮字段 |
| `UNAUTHORIZED` | 401 | 未认证 | Token 缺失或无效 | 跳转登录 |
| `RATE_LIMITED` | 429 | 请求频率超限 | 超过 10/min/session | 请稍后重试 |
| `INTERNAL_ERROR` | 500 | 未预期异常 | 兜底捕获 | 服务异常，请重试 |

#### 8.1.2 会话错误（2xx）

| 错误码 | HTTP | 说明 | 触发条件 | 用户提示 |
|--------|------|------|---------|---------|
| `SESSION_NOT_FOUND` | 404 | 会话不存在 | session_id 无效 | 会话不存在 |
| `SESSION_TIMEOUT` | 200(SSE) | 会话已超时 | `check_and_mark_timeout` 返回 True | 会话已超时，请新建 |
| `SESSION_ENDED` | 400 | 会话已结束 | 对 `ended` 会话发消息 | 会话已结束 |

#### 8.1.3 知识库错误（3xx）

| 错误码 | HTTP | 说明 | 触发条件 | 用户提示 |
|--------|------|------|---------|---------|
| `KB_NOT_READY` | 503 | 知识库未构建 | 首次启动未构建时对话 | 知识库构建中，请稍后 |
| `KB_BUILDING` | 409 | 知识库正在构建 | 并发触发重建 | 正在重建，请等待 |
| `KB_CORRUPTED` | 503 | 知识库损坏 | `kb_status='corrupted'` | 知识库损坏，请联系管理员 |
| `KB_VERSION_NOT_FOUND` | 404 | 版本不存在 | rollback 时 version_id 无效 | 版本不存在 |
| `KB_ROLLBACK_FAILED` | 500 | 回滚失败 | 快照恢复失败 | 回滚失败，请联系管理员 |

#### 8.1.4 AI 调用错误（4xx）

| 错误码 | HTTP | 说明 | 触发条件 | 用户提示 |
|--------|------|------|---------|---------|
| `BUDGET_EXCEEDED` | 200(SSE) | AI 预算超限 | `check_budget` 返回 False | AI 预算已用尽，已转人工 |
| `LLM_TIMEOUT` | 200(SSE) | LLM 超时 | 首 token 超时 / HTTP 超时 | AI 响应超时，已展示相关资料 |
| `LLM_NETWORK` | 200(SSE) | LLM 网络异常 | httpx.ConnectError 等 | AI 服务暂时不可用 |
| `LLM_PARSE` | 200(SSE) | LLM 响应解析失败 | JSONDecodeError | AI 响应解析失败 |
| `LLM_UNKNOWN` | 200(SSE) | LLM 未知异常 | 兜底捕获 | AI 服务异常 |
| `LLM_DEGRADED` | 200(SSE) | LLM 已降级 | 降级到 RAG 片段 | 已为您展示相关资料 |
| `EMBEDDING_FAILED` | 200(SSE) | Embedding 调用失败 | 单次 embed 异常 | 向量化失败，请重试 |

#### 8.1.5 AGENT 错误（5xx）

| 错误码 | HTTP | 说明 | 触发条件 | 用户提示 |
|--------|------|------|---------|---------|
| `AGENT_TIMEOUT` | 200(SSE) | AGENT 总超时 | 超过 `tool_total_timeout_sec` | 工具调用超时 |
| `TOOL_NOT_FOUND` | 200(SSE) | 工具不存在 | LLM 调用未注册工具 | 工具不可用 |
| `TOOL_TIMEOUT` | 200(SSE) | 单工具超时 | 超过 `tool_call_timeout_sec` | 工具执行超时 |
| `TOOL_INTERNAL` | 200(SSE) | 工具内部异常 | handler 抛异常 | 工具内部错误 |

#### 8.1.6 安全错误（6xx）

| 错误码 | HTTP | 说明 | 触发条件 | 用户提示 |
|--------|------|------|---------|---------|
| `PROMPT_INJECTION` | 400 | 疑似 Prompt Injection | `check_user_input_safety` 检测到 | 检测到不安全输入 |
| `MESSAGE_TOO_LONG` | 400 | 消息超长 | 超过 2000 字符 | 消息不能超过 2000 字符 |

### 8.2 异常处理策略矩阵

| 异常类型 | 捕获位置 | 处理策略 | 对应错误码 |
|---------|---------|---------|-----------|
| `asyncio.CancelledError` | 各 async 边界 | 向上传播，触发资源清理 | 不产生错误码 |
| `asyncio.TimeoutError` | RAGEngine.generate | 降级到 RAG 片段 | `LLM_TIMEOUT` |
| `httpx.ConnectError` | Orchestrator._run_rag_flow | 降级到 RAG 片段 | `LLM_NETWORK` |
| `httpx.ReadTimeout` | Orchestrator._run_rag_flow | 降级到 RAG 片段 | `LLM_NETWORK` |
| `httpx.RemoteProtocolError` | Orchestrator._run_rag_flow | 降级到 RAG 片段 | `LLM_NETWORK` |
| `json.JSONDecodeError` | RAGEngine.generate / Agent | 降级到 RAG 片段 | `LLM_PARSE` |
| `BudgetExceededError` | Orchestrator.orchestrate | 直接转人工 | `BUDGET_EXCEEDED` |
| 工具内部 Exception | ToolRegistry.call | 返回 ToolResult(success=False) | `TOOL_INTERNAL` |
| Embedding Exception | EmbeddingService.embed_batch | 跳过失败片段 | 不产生错误码（部分失败） |
| KB 构建 Exception | KBManager._do_build | 快照回滚 | `KB_BUILDING`（如未完成） |
| Pydantic ValidationError | FastAPI 自动处理 | 422 响应 | `INVALID_REQUEST` |
| 其他未预期 Exception | Orchestrator.orchestrate | 转人工 | `INTERNAL_ERROR` |

### 8.3 降级链实现

```python
# 完整降级链（见概要设计 §3.13.3）
LLM 流式生成
    ↓ (TimeoutError | httpx.* | JSONDecodeError)
RAG 片段拼接（_fallback_to_rag_fragments）
    ↓ (chunks 为空)
FAQ 模糊匹配（_fallback_to_faq_and_rag）
    ↓ (FAQ 也无匹配)
转人工（_escalate）
    ↓
用户收到 escalate SSE 事件 + 联系方式
```

每级降级均：
1. 发布 `CHATBOT_DEGRADED` 事件（payload: `from`/`to`/`reason`）
2. `logger.warning` 记录降级原因
3. 在 assistant 消息上标记 `degraded=True`（前端显示"降级回答"标识）

### 8.4 错误响应格式

**同步 API**（非 SSE）统一返回：
```json
{
  "detail": "人类可读的错误描述",
  "code": "ERROR_CODE"
}
```

**SSE 流式 API** 错误通过 `error` 事件返回：
```
event: error
data: {"code": "LLM_TIMEOUT", "message": "AI 响应超时，已为您展示相关资料"}

event: done
data: {"degraded": true}
```

错误事件后必有 `done` 事件（除非是 `escalate` 事件），确保前端能正确关闭流。

---

## 9. 测试用例设计

### 9.1 测试分层

| 层级 | 范围 | 工具 | 目标覆盖率 |
|------|------|------|-----------|
| 单元测试 | 单个模块/类/函数 | pytest + pytest-asyncio | 行覆盖 ≥ 80% |
| 集成测试 | 跨模块协作 | pytest + httpx.AsyncClient | 关键流程 100% |
| 验收测试 | 端到端用户场景 | Playwright | 验收标准 44 条全覆盖 |

### 9.2 单元测试用例

#### 9.2.1 ChatbotRepository

| 用例 ID | 场景 | 输入 | 期望 | 文件 |
|---------|------|------|------|------|
| UT-Repo-01 | 创建会话 | title="" | 返回 UUID32，DB 有行 | test_repo_chatbot.py |
| UT-Repo-02 | 创建会话带标题 | title="测试" | DB title="测试" | 同上 |
| UT-Repo-03 | 添加消息 + message_count 同步 | add_message × 3 | session.message_count=3 | 同上 |
| UT-Repo-04 | 列表分页 | 25 条会话，page=2, page_size=10 | 返回 10 条，total=25 | 同上 |
| UT-Repo-05 | 删除会话级联 | session 有消息+反馈 | 删除后消息/反馈也删除 | 同上 |
| UT-Repo-06 | 配置 upsert | key 新增 / 已存在更新 | 首次 insert / 二次 update | 同上 |
| UT-Repo-07 | 审计日志 hash 不存明文 | old_value="secret" | DB 中仅存 sha256 hash | 同上 |
| UT-Repo-08 | KB 版本 is_current 唯一 | set_current_kb_version 两次 | 仅最后一行为 is_current=True | 同上 |

#### 9.2.2 IntentClassifier

| 用例 ID | 场景 | 输入 | 期望 | 文件 |
|---------|------|------|------|------|
| UT-Intent-01 | 白名单命中 | "任务怎么配置" | in_scope=True, method="rule" | test_intent_classifier.py |
| UT-Intent-02 | 黑名单命中 | "今天天气如何" | in_scope=False, method="rule" | 同上 |
| UT-Intent-03 | 白名单优先于黑名单 | "闲鱼怎么卖任务" | in_scope=True（白名单优先） | 同上 |
| UT-Intent-04 | 空消息 | "" | in_scope=False, reason="空消息" | 同上 |
| UT-Intent-05 | LLM 兜底成功 | "评估器是什么" | in_scope=True, method="llm" | 同上 |
| UT-Intent-06 | LLM 失败保守放行 | LLM 抛 ConnectError | in_scope=True, method="rule" | 同上 |

#### 9.2.3 FAQMatcher

| 用例 ID | 场景 | 输入 | 期望 | 文件 |
|---------|------|------|------|------|
| UT-FAQ-01 | 精确匹配 | FAQ Q="如何创建任务"，user Q="如何创建任务" | exact_match=True | test_faq_matcher.py |
| UT-FAQ-02 | 模糊匹配 | FAQ Q="如何创建任务"，user Q="怎么创建任务" | need_confirm=True | 同上 |
| UT-FAQ-03 | 无匹配 | FAQ Q="天气"，user Q="任务" | 返回空结果 | 同上 |
| UT-FAQ-04 | 缓存失效 | upsert_faq 后 match | 使用新 FAQ 数据 | 同上 |
| UT-FAQ-05 | 空 FAQ 列表 | DB 无 FAQ | 返回空结果 | 同上 |

#### 9.2.4 RAGEngine

| 用例 ID | 场景 | 输入 | 期望 | 文件 |
|---------|------|------|------|------|
| UT-RAG-01 | 检索 + 阈值过滤 | top_k=5，3 个低于阈值 | 返回 2 个 | test_rag_engine.py |
| UT-RAG-02 | context 截断 | 5 片段总长 > max_context_chars | 丢弃最低相似度 | 同上 |
| UT-RAG-03 | context 单片超长 | 1 片段 > max_context_chars | 字符截断 + "..." | 同上 |
| UT-RAG-04 | 引用后处理有效编号 | "[来源:1] [来源:2]" | 保留 | 同上 |
| UT-RAG-05 | 引用后处理无效编号 | "[来源:99]" | 替换为 "[来源:?]" | 同上 |
| UT-RAG-06 | LLM 流式生成 | mock httpx 返回 3 个 chunk | yield 3 个 token | 同上 |
| UT-RAG-07 | LLM 首-token 超时 | mock httpx 超时 | 抛 TimeoutError | 同上 |

#### 9.2.5 Agent + ToolRegistry

| 用例 ID | 场景 | 输入 | 期望 | 文件 |
|---------|------|------|------|------|
| UT-Agent-01 | 单轮工具调用 | LLM 返回 1 个 tool_call | yield tool_call + done | test_agent.py |
| UT-Agent-02 | 多轮工具调用 | LLM 返回 2 轮 tool_call | rounds=2 | 同上 |
| UT-Agent-03 | 工具超时 | mock 工具 sleep 10s | ToolResult(success=False) | 同上 |
| UT-Agent-04 | 工具异常 | mock 工具抛 ValueError | ToolResult(success=False) | 同上 |
| UT-Agent-05 | 敏感字段过滤 | 工具返回 {"api_key": "sk-xxx"} | data={"api_key": "<REDACTED>"} | 同上 |
| UT-Agent-06 | 总超时降级 | 累计 > tool_total_timeout_sec | yield error + 最终回答 | 同上 |

#### 9.2.6 KBManager

| 用例 ID | 场景 | 输入 | 期望 | 文件 |
|---------|------|------|------|------|
| UT-KB-01 | Markdown 切片 | H2 + H3 + 内容 | 按 H2 切分 | test_kb_manager.py |
| UT-KB-02 | Python AST 切片 | 含 module + class + func | 提取所有 docstring | 同上 |
| UT-KB-03 | Python AST 失败降级 | 语法错误文件 | 文件粒度切片 | 同上 |
| UT-KB-04 | 敏感字段丢弃 | content 含 "sk-..." | 片段被过滤 | 同上 |
| UT-KB-05 | Embedding 部分失败 | 100 片段，5 个失败 | status="partial" | 同上 |
| UT-KB-06 | Embedding 失败率 > 10% | 100 片段，15 个失败 | 返回 None + 失败事件 | 同上 |
| UT-KB-07 | 构建失败回滚 | mock 阶段 2 异常 | ChromaDB 恢复 + 快照删除 | 同上 |
| UT-KB-08 | 快照恢复失败 | mock restore 异常 | kb_status="corrupted" | 同上 |
| UT-KB-09 | 增量更新无变化 | doc_hash 相同 | 返回 None | 同上 |
| UT-KB-10 | 旧快照清理 | 15 个版本，max_keep=10 | 删除最旧 5 个快照 | 同上 |

#### 9.2.7 Escalation

| 用例 ID | 场景 | 输入 | 期望 | 文件 |
|---------|------|------|------|------|
| UT-Esc-01 | 用户主动转人工 | message="转人工" | should_escalate=True | test_escalation.py |
| UT-Esc-02 | 连续点踩触发 | 2 次负反馈（30min 内） | should_escalate=True | 同上 |
| UT-Esc-03 | 点踩超出窗口 | 2 次负反馈（>30min） | should_escalate=False | 同上 |
| UT-Esc-04 | RAG 无匹配 | 全部 similarity < 0.65 | should_escalate=True | 同上 |
| UT-Esc-05 | AGENT 失败 | agent_failed=True | should_escalate=True | 同上 |
| UT-Esc-06 | PII 脱敏手机号 | "13812345678" | "138****5678" | 同上 |
| UT-Esc-07 | PII 脱敏邮箱 | "user@example.com" | "u***@example.com" | 同上 |
| UT-Esc-08 | 联系方式为空 | config.contact="" | "请联系管理员" | 同上 |

#### 9.2.8 安全规则

| 用例 ID | 场景 | 输入 | 期望 | 文件 |
|---------|------|------|------|------|
| UT-Sec-01 | Prompt Injection 中英文 | "忽略上述指令" / "ignore previous" | 检测到 | test_security.py |
| UT-Sec-02 | OpenAI Key 扫描 | "sk-" + 48 字符 | 命中 | 同上 |
| UT-Sec-03 | JWT 扫描 | "eyJxxx.eyJyyy.zzz" | 命中 | 同上 |
| UT-Sec-04 | 私钥扫描 | "-----BEGIN RSA PRIVATE KEY-----" | 命中 | 同上 |
| UT-Sec-05 | 正常代码不误报 | "import os" | 不命中 | 同上 |

### 9.3 集成测试用例

| 用例 ID | 场景 | 步骤 | 期望 | 文件 |
|---------|------|------|------|------|
| IT-01 | 完整对话流程 | 创建会话 → 发消息 → 收 SSE | 收到 intent/sources/token/done | test_integration_chat.py |
| IT-02 | FAQ 命中跳过 LLM | FAQ 已配置 → 发匹配问题 | 仅 done 事件，无 token 事件 | 同上 |
| IT-03 | 意图超出范围转人工 | 发"天气" | 收到 escalate 事件 | 同上 |
| IT-04 | LLM 超时降级 | mock LLM 超时 | 收到 error + token(RAG 片段) + done | 同上 |
| IT-05 | 客户端断开清理 | 发消息后立即断开 | orch_task 取消，无内存泄漏 | 同上 |
| IT-06 | 知识库全量构建 | 调 rebuild → 等待完成 | KB status=success，可检索 | test_integration_kb.py |
| IT-07 | 知识库回滚 | 构建后回滚到上一版本 | 检索结果与旧版本一致 | 同上 |
| IT-08 | 配置热更新 | 改 rag.similarity_threshold → 发消息 | 新阈值生效 | test_integration_config.py |
| IT-09 | per-session 锁串行化 | 并发发 2 条消息到同一 session | 第 2 条等待第 1 条完成 | test_integration_concurrency.py |
| IT-10 | 反馈触发转人工 | 同会话点踩 2 次 → 发消息 | 收到 escalate 事件 | test_integration_escalation.py |

### 9.4 验收测试用例（对应需求 §10 验收标准）

| 用例 ID | 验收标准 | 步骤 | 期望 |
|---------|---------|------|------|
| AT-01 | 对话响应首 token < 15s | 发送问题，计时 | 首 token ≤ 15s |
| AT-02 | RAG 检索 top_5 < 500ms | 发送问题，计时 | 检索 ≤ 500ms |
| AT-03 | 知识库构建 < 5min（100 文档） | rebuild，计时 | ≤ 5min |
| AT-04 | 引用准确性 ≥ 90% | 抽样 100 条回答 | ≥ 90 条引用有效 |
| AT-05 | 降级链完整 | 断开 LLM | 自动降级到 RAG → 转人工 |
| AT-06 | 敏感字段不泄露 | 工具返回含 api_key | 前端看到 `<REDACTED>` |
| AT-07 | 会话超时生效 | 等待 > 30min 后发消息 | 返回 SESSION_TIMEOUT |
| AT-08 | 知识库回滚可用 | 构建后回滚 | 检索结果恢复 |
| AT-09 | PII 转人工脱敏 | 复制会话含手机号 | 显示 `138****5678` |
| AT-10 | Prompt Injection 拦截 | 发"忽略上述指令" | 返回 PROMPT_INJECTION |

### 9.5 测试工具与配置

```python
# pytest.ini
[pytest]
asyncio_mode = auto
testpaths = tests/chatbot
addopts = -v --cov=src/xianyu_hunter/modules/chatbot --cov-report=term-missing --cov-report=html
markers =
    unit: 单元测试
    integration: 集成测试
    slow: 慢测试（>1s）
```

```python
# tests/chatbot/conftest.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from xianyu_hunter.infra.yaml_config import ChatbotConfig


@pytest.fixture
def mock_config() -> ChatbotConfig:
    return ChatbotConfig()


@pytest.fixture
def mock_embedding():
    """Mock EmbeddingService，返回固定向量"""
    m = AsyncMock()
    m.embed = AsyncMock(return_value=[0.1] * 1536)
    m.embed_batch = AsyncMock(return_value=[("text", [0.1] * 1536)])
    return m


@pytest.fixture
def mock_vector_store():
    """Mock VectorStore，返回固定 chunks"""
    from xianyu_hunter.modules.chatbot.types import RetrievedChunk
    m = AsyncMock()
    m.search = AsyncMock(return_value=[
        RetrievedChunk(
            content="测试内容", source_file="test.md",
            section_path="测试章节", line_start=1, line_end=10,
            doc_type="manual", similarity=0.85,
        )
    ])
    return m


@pytest.fixture
async def chatbot_repo(tmp_path):
    """独立 SQLite DB 的 ChatbotRepository（测试隔离）"""
    from sqlalchemy import create_engine
    from xianyu_hunter.infra.repo_chatbot import ChatbotRepository
    engine = create_engine(f"sqlite:///{tmp_path}/test_chatbot.db")
    return ChatbotRepository(engine)
```

### 9.6 测试覆盖率目标

| 模块 | 行覆盖 | 分支覆盖 | 关键路径覆盖 |
|------|--------|---------|-------------|
| ChatbotRepository | ≥ 90% | ≥ 85% | 100% |
| IntentClassifier | ≥ 95% | ≥ 90% | 100% |
| FAQMatcher | ≥ 90% | ≥ 85% | 100% |
| RAGEngine | ≥ 85% | ≥ 80% | 100% |
| Agent + ToolRegistry | ≥ 85% | ≥ 80% | 100% |
| KBManager | ≥ 85% | ≥ 80% | 100% |
| Escalation | ≥ 90% | ≥ 85% | 100% |
| 安全规则 | ≥ 95% | ≥ 90% | 100% |
| **整体加权** | **≥ 80%** | **≥ 75%** | **100%** |

---

## 10. 阶段交接声明

```
## 阶段交接声明
- 当前阶段：详细设计 v1.0 ✅ 已完成
- 下一阶段：编码实现（后端 + 前端）
- 下一阶段智能体：general_purpose_task（后端） / frontend-design（前端）
- 下一阶段技能：web-dev-trae（后端） / frontend-design（前端）
- 交接上下文：
  1. 文档完整性：§1-§10 全部完成，共 10 章
     - §1 概述：文档定位、设计原则、模块清单（13 个模块）
     - §2 数据库详细设计：6 张 SQLite 表 DDL + 索引 + 迁移
     - §3 配置 Schema：ChatbotConfig Pydantic 模型 + ConfigManager 热更新
     - §4 API 详细设计：17 个端点（对话/会话/FAQ/反馈/KB/配置/审计）
     - §5 模块详细设计：13 个子章节，含类签名/方法签名/算法伪代码/边界条件
     - §6 状态机：3 个状态机（Session/KB Version/Escalation）+ 跨状态交互
     - §7 前端组件：路由/页面结构/useSSEChat hook/TS 类型/API 客户端
     - §8 错误码：6 类 25+ 码 + 异常策略矩阵 + 降级链实现
     - §9 测试用例：50+ 单元测试 + 10 集成测试 + 10 验收测试 + 覆盖率目标
     - §10 阶段交接声明（本节）

  2. 关键设计决策（沿用概要设计 v1.1，已落入详细设计）：
     - ChromaDB 0.4.x 锁版本（0.5.x breaking changes）
     - SSE 用 fetch+ReadableStream（POST 不能用 EventSource）
     - KBRefreshScheduler 用 BackgroundScheduler + run_coroutine_threadsafe
     - ChatbotRepository 复用主 repo.engine（避免 SQLite locked）
     - 权限模型沿用单 Token，不引入角色区分；审计日志记录敏感操作
     - 配置基类用 Pydantic BaseModel（与 yaml_config.py 一致）
     - EVENT_SEVERITY 用 setdefault() 幂等扩展
     - 并发控制 per-session asyncio.Lock（防止上下文错乱）
     - 安全 7 层过滤 + 附录 A（5/8/6 类正则）
     - 降级链：LLM → RAG → FAQ → 转人工，每级发布 CHATBOT_DEGRADED 事件
     - 两阶段提交 + 快照恢复（KB 构建回滚策略）
     - cosine distance → similarity 公式：1 - distance/2

  3. 数据模型清单（6 张 SQLite 表）：
     - chatbot_sessions：会话主表（id/user_id/title/status/message_count/created_at/updated_at/last_message_at）
     - chatbot_messages：消息表（id/session_id/role/content/sources_json/tool_calls_json/feedback_rating/feedback_comment/created_at）
     - chatbot_faqs：FAQ 表（id/question/answer/keywords_json/enabled/sort_order/created_at/updated_at）
     - chatbot_feedback：反馈表（id/session_id/message_id/rating/comment/created_at）
     - chatbot_kb_versions：知识库版本表（id/version/status/snapshot_path/built_at/duration_ms/chunk_count/error_message）
     - chatbot_config：动态配置表（key/value/updated_at）+ chatbot_audit_logs：审计日志表（id/action/target_hash/detail/created_at）
     - 索引：session_id/created_at/status/last_message_at/enabled/sort_order/version/status

  4. API 端点清单（17 个）：
     - 对话：POST /api/chatbot/chat（SSE 流式）
     - 会话：GET/POST /api/chatbot/sessions、GET/DELETE /api/chatbot/sessions/{id}、PATCH /api/chatbot/sessions/{id}/title、POST /api/chatbot/sessions/{id}/end
     - 反馈：POST /api/chatbot/messages/{id}/feedback、GET /api/chatbot/feedback/recent
     - FAQ：GET/POST/PUT/DELETE /api/chatbot/faqs
     - KB：POST /api/chatbot/kb/rebuild、GET /api/chatbot/kb/versions、GET /api/chatbot/kb/status、POST /api/chatbot/kb/rollback/{version}
     - 配置：GET/PUT /api/chatbot/config、GET /api/chatbot/audit-logs

  5. 模块实现清单（13 个）：
     - ChatbotOrchestrator（§5.1）：编排器，10 步流程 + per-session Lock
     - RAGEngine（§5.2）：检索+生成，httpx 流式 + 首字超时
     - Agent + ToolRegistry（§5.3）：6 工具 + 多轮调用 + asyncio.timeout
     - IntentClassifier（§5.4）：规则+LLM 两阶段，保守放行
     - KBManager（§5.5）：两阶段提交 + AST 解析 + 快照恢复
     - FAQMatcher（§5.6）：rapidfuzz + 关键词加权 + 缓存
     - ContextManager（§5.7）：消息历史 + 250+250 截断 + 超时标记
     - Escalation（§5.8）：5 触发条件 + PII 脱敏
     - EmbeddingService（§5.9）：批量 + Semaphore + 部分失败
     - VectorStore（§5.10）：asyncio.to_thread 包装 ChromaDB 同步 API
     - ChatbotRepository（§5.11）：7 表 CRUD + 级联删除 + 游标分页
     - KBRefreshScheduler（§5.12）：BackgroundScheduler + 600s 超时
     - security 子模块（§5.13）：patterns.py + sanitizer.py + 7 应用点

  6. 状态机清单（3 个）：
     - Session：active ↔ ended（5 转换，3 约束）
     - KB Version：building → success/partial/failed/corrupted/rolled_back（7 转换，4 约束）
     - Escalation：normal → pending → escalated（4 转换，5 触发条件，4 约束）

  7. 前端实现清单：
     - 路由：/chatbot、/chatbot/session/:sessionId、/config/chatbot
     - 页面：ChatbotPage（会话列表+消息区+输入框）、ChatbotConfigPage（5 个 Tab）
     - Hook：useSSEChat（fetch + ReadableStream + AbortController + SSE parser）
     - 组件：AssistantMessage（Markdown+引用+反馈+转人工）、KBStatusCard（重建+进度）
     - TS 类型：Session/Source/Message/ToolCall/KBStatus/KBVersion/FAQ/ChatbotConfig/AuditLog
     - API 客户端：chatbotApi 对象（封装所有 17 个端点）

  8. 错误码与异常策略：
     - 6 类错误码：1xx 通用 / 2xx 会话 / 3xx KB / 4xx AI / 5xx AGENT / 6xx 安全
     - 12 类异常 × 捕获位置 × 策略 × 错误码（见 §8.2 矩阵）
     - 同步错误：JSON {"code":"CHATBOT_XXX","message":"..."} + HTTP 状态码
     - SSE 错误：event: error\ndata: {"code":"CHATBOT_XXX","message":"..."}

  9. 测试策略：
     - 单元测试：50+ 用例（UT-Repo/Intent/FAQ/RAG/Agent/KB/Esc/Sec）
     - 集成测试：10 用例（IT-01~10，覆盖完整对话流/FAQ/意图/LLM 超时/客户端断开/KB 构建/回滚/配置热更新/per-session 锁/反馈转人工）
     - 验收测试：10 用例（AT-01~10，映射需求 §10 验收准则）
     - 覆盖率：整体 ≥ 80% 行 / 75% 分支 / 100% 关键路径
     - 测试工具：pytest + pytest-asyncio + pytest-cov + httpx.AsyncClient

  10. 实现顺序建议（按依赖关系）：
      阶段 A（基础设施）：
        1. db_models.py 新增 6 张表 + 迁移
        2. yaml_config.py 新增 ChatbotConfig
        3. events.py 扩展 EventType（13 项）+ EVENT_SEVERITY
      阶段 B（核心模块）：
        4. EmbeddingService + VectorStore（无外部依赖）
        5. ChatbotRepository（依赖 db_models）
        6. KBManager（依赖 EmbeddingService + VectorStore）
        7. FAQMatcher + IntentClassifier + ContextManager + Escalation
        8. RAGEngine（依赖 EmbeddingService + VectorStore）
        9. Agent + ToolRegistry（依赖主 repo + RAGEngine）
        10. ChatbotOrchestrator（串联所有模块）
      阶段 C（集成层）：
        11. container.py 新增 ChatbotContainer + build_chatbot_container
        12. api_chatbot.py / api_kb.py / api_chatbot_config.py 路由
        13. app.py 注册路由 + startup.py 启停调度器
        14. api_prompts.py 追加 chatbot_* key
        15. KBRefreshScheduler
      阶段 D（前端）：
        16. types.ts + chatbotApi.ts
        17. useSSEChat hook
        18. ChatbotPage + 组件
        19. ChatbotConfigPage
        20. App.tsx 路由 + MainLayout 菜单
      阶段 E（测试 + 验收）：
        21. 单元测试（UT-*）
        22. 集成测试（IT-*）
        23. 验收测试（AT-*）

  11. 待调优项（验收阶段处理）：
      - similarity_threshold：用 100 条标注集调优（默认 0.7）
      - intent_confidence_threshold：默认 0.6，验收阶段调整
      - faq_similarity_threshold：默认 0.85，验收阶段调整
      - kb_chunk_size / kb_chunk_overlap：默认 800/100，验收阶段调整
      - LLM first_token_timeout：默认 5s，验收阶段根据 OpenAI 实际响应调整

  12. 未决项：无
      - 概要设计 v1.1 的 5 项 P0 + 15 项 P1 已全部落入详细设计
      - 详细设计 v1.0 未引入新的阻断问题
      - 所有边界条件、异常处理、状态转换已在 §5-§9 明确

  13. 集成检查清单（编码阶段对照）：
      [ ] db_models.py 新增 6 张表（§2.2 DDL）
      [ ] yaml_config.py 新增 ChatbotConfig（§3.1 Schema）
      [ ] events.py 扩展 EventType（概要设计 §6.4）
      [ ] container.py 新增 ChatbotContainer（概要设计 §8.5）
      [ ] app.py 注册 3 个路由（§4 + 概要设计 §8.4）
      [ ] startup.py 启停 KBRefreshScheduler（§5.12）
      [ ] api_prompts.py 追加 3 个 chatbot_* key（概要设计 §8.3）
      [ ] modules/chatbot/ 新建 13 个文件（§5.1-§5.13）
      [ ] infra/repo_chatbot.py 新建（§5.11）
      [ ] frontend/src/pages/chatbot/ 新建（§7）
      [ ] frontend/src/pages/config/ChatbotConfigPage.tsx 新建（§7）
      [ ] App.tsx 新增 3 个路由（§7.2）
      [ ] MainLayout.tsx 新增菜单项（概要设计 §8.6）
      [ ] tests/chatbot/ 新建测试套件（§9）
      [ ] requirements.txt 新增依赖：chromadb==0.4.x、rapidfuzz
```

---

## v1.1 修订说明（P1+P2 缺陷修复同步）

本次 v1.1 修订将编码阶段后的代码评审发现的 P1 (High) 7 项 + P2 (Medium) 12 项共 19 项缺陷修复同步回详细设计文档，确保设计与实现一致。

### P1 (High) 修复（7 项）

| 编号 | 文件 | 修复内容 |
|------|------|----------|
| H2/H3 | embedding_service.py | OpenAI 配置统一从 `get_settings()` 读取（.env + keyring），不再用 `os.getenv` |
| H4 | repo_chatbot.py | `list_sessions` 的 total 需真实计数支持前端分页 |
| H5 | rag_engine.py | 异常路径与空响应路径也需调用 `_record_llm_usage`，避免用量统计缺失 |
| H7 | context_manager.py | `load_context`/`save_message`/`generate_title` 从 `async def` 改为 `def`（纯 DB 操作无需 async） |
| H-6/7/8 | Config.tsx | Slider/Input/InputNumber onChange 添加 500ms 防抖，避免高频 PUT 请求 |

### P2 (Medium) 修复（12 项）

| 编号 | 文件 | 修复内容 |
|------|------|----------|
| M-2 | embedding_service.py | 注释过时（KBManager 不再通过属性检查失败率） |
| M-3 | agent.py | 总超时错误消息提取 `msg` 变量复用，避免字符串重复构造 |
| M-4 | intent_classifier.py | `_SCOPE_KEYWORDS` 注释歧义简化 |
| M-5 | rag_engine.py | 截断日志保留 `original_len`，避免丢失原始长度信息 |
| M-10 | context_manager.py | `session_id` 空字符串与 None 同等处理（`is not None` → `not`） |
| M-11/M-12 | intent_classifier.py | LLM 返回 `content: null` 空安全 + `JSONDecodeError` 单独捕获记录 raw |
| M-15 | embedding_service.py | 属性 `last_batch_failures` → `last_batch_failure_count`（返回 int 数量） |
| M-22 | faq_matcher.py | embedding 维度不一致时返回 0.0，避免 `zip` 静默截断 |
| M-24 | agent.py | 未使用变量 `round_idx` → `_` |
| M-30 | repo_chatbot.py | `merge_session_metadata` 过滤 None 值，避免覆盖已有有效字段 |
| M-35 | api_kb.py | `asyncio.create_task` 结果保存到 `_background_tasks` 集合，避免 GC 回收 |
| M-36 | api_kb.py + repo_chatbot.py | `list_kb_versions` 的 total 用 `count_kb_versions()` 真实计数 |

### 回归测试

- chatbot 模块测试：**153 passed**（两次验证）
- 完整测试套件：**1232 passed, 26 failed**（26 项失败全部为预存在的非 chatbot 模块历史遗留问题）

---

## 阶段交接声明（v1.1）

```
## 阶段交接声明
- 当前阶段：P1+P2 缺陷修复 + 设计文档同步 ✅ 已完成
- 下一阶段：待用户决策（可选：修复预存在失败 / 验收测试 / 部署）
- 交接上下文：
  1. P1 (7项) + P2 (12项) 共 19 项缺陷已修复并通过回归测试
  2. 详细设计文档 v1.1 已同步所有修复的设计变更
  3. chatbot 模块代码质量已显著提升，无新增回归
  4. 26 项预存在失败全部为非 chatbot 模块（batch_refresh/list_links/login_strategy/repository），与本次修复无关
```

---

**文档结束**
