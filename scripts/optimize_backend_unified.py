"""
优化 xianyu-backend-code-review SKILL.md 统一脚本
从备份一次性完成所有优化，避免多次执行出错
"""
import sys
from pathlib import Path


def replace_section(content: str, start_marker: str, end_marker: str, replacement: str, label: str = "") -> str:
    """章节级替换：替换从 start_marker 到 end_marker 之间的内容（不含 end_marker）"""
    start_idx = content.find(start_marker)
    if start_idx < 0:
        print(f"  [WARN] {label}: 未找到章节起始标记: {start_marker[:50]}")
        return content
    end_idx = content.find(end_marker, start_idx + len(start_marker))
    if end_idx < 0:
        print(f"  [WARN] {label}: 未找到章节结束标记: {end_marker[:50]}")
        return content
    before = content[:start_idx]
    after = content[end_idx:]
    print(f"  [OK] {label}: 替换 {end_idx - start_idx} 字符 → {len(replacement)} 字符")
    return before + replacement + after


def optimize_backend(file_path: str) -> None:
    """优化 backend SKILL.md - 统一执行所有优化"""
    path = Path(file_path)
    content = path.read_text(encoding='utf-8')
    original_len = len(content)
    print(f"原始长度: {original_len} 字符")

    # === 1. 精简 frontmatter description ===
    old_desc = 'description: "对闲鱼猎人项目后端代码（src/xianyu_hunter/ Python/FastAPI/SQLAlchemy 文件）进行全面评审与逻辑审查，覆盖分层架构、异步并发、数据库规约、安全、性能、错误处理、日志规范、配置驱动、注册式资源 endpoint 契约、编码规范防御性复盘、跨层契约与测试同步、LLM 多调用治理，37 个维度。当用户要求\'审查/检、走查/把关/review/评估/看看对不对、规范不规范、后端 Python 代码的 .py 文件修改\'、迭代发布前后端走，或提到\'后端评审/backend review/Python 代码审查/FastAPI 评审/SQLAlchemy 评审\'时调用。仅审查后端 .py 文件；纯前端 .tsx/.ts 文件审查请改用 xianyu-frontend-code-review"'
    new_desc = 'description: "闲鱼猎人项目后端代码（src/xianyu_hunter/ Python/FastAPI/SQLAlchemy .py 文件）全面评审，覆盖分层架构、异步并发、数据库规约、安全、性能、错误处理、日志规范、配置驱动、跨层契约、LLM 治理等 37 个维度。当用户要求\'审查/走查/把关/review/评估/看看对不对、规范不规范、后端 Python 代码的 .py 文件修改\'、迭代发布前后端走查，或提到\'后端评审/backend review/Python 代码审查/FastAPI 评审/SQLAlchemy 评审\'时调用。仅审查后端 .py 文件；纯前端 .tsx/.ts 文件审查请改用 xianyu-frontend-code-review"'
    if old_desc in content:
        content = content.replace(old_desc, new_desc)
        print("  [OK] frontmatter description 精简完成")
    else:
        print("  [WARN] frontmatter description 未找到精确匹配")

    # === 2. 精简简介段落（L15）===
    old_intro_prefix = "对闲鱼猎人项目后端代码（`src/xianyu_hunter/` 下的 Python/FastAPI/SQLAlchemy 文件）进行全面的代码评审及逻辑审查。"
    if old_intro_prefix in content:
        intro_start = content.find(old_intro_prefix)
        intro_end = content.find("\n## ", intro_start)
        if intro_end > 0:
            new_intro = "对闲鱼猎人项目后端代码（`src/xianyu_hunter/` 下的 Python/FastAPI/SQLAlchemy 文件）进行全面的代码评审及逻辑审查，覆盖 36 个维度（分层架构/异步并发/数据库规约/安全/性能/错误处理/日志规约/配置管理/智能客服/Git 规范/跨字段一致性/LLM 治理/多用户隔离/跨层契约与测试同步等）。详细规则分布在本文件与 `references/` 下 16 个主题文件中，按需加载。\n\n"
            content = content[:intro_start] + new_intro + content[intro_end:]
            print("  [OK] 简介段落精简完成")

    # === 3. 精简版本演进索引 ===
    version_section = """## 版本演进索引

> 完整版本复盘详情详见 [references/version-changelog.md](file:///d:/code/otherProjects/17_xianyu/.trae/skills/xianyu-backend-code-review/references/version-changelog.md)。本表仅列最近 3 个版本，历史版本（v2.0.0 ~ v4.59.0）请查阅该文件。

| 版本 | 新增检查点 | 扫描范围 | 核心变化 |
|---|---|---|---|
| v4.62.0 | B-REVIEW-291~294 | 290->294 | LLM 附加调用预算/超时/结构化解析/多调用一致性（coding-standards v1.3 §2.21-2.24） |
| v4.61.0 | B-REVIEW-281~290 | 280->290 | 重构安全性审查 10 项（配置化重构5步法/作用域契约/导入名称checklist/PowerShell长任务/资源过载容错/SonarQube闭环/弹性恢复/测试三档/跨文件同步/配置统一入口） |
| v4.60.0 | B-REVIEW-275~280 | 274->280 | 缓存守卫三原则/数据写入策略字段级决策/状态机返回值语义/回调注入默认值/跨层闭环验证/Windows编码规范 |
| v2.0.0 ~ v4.59.0 | B-REVIEW-001~274 + 历史 | 0->274 | 历史版本（含 v4.50/4.55/4.57/4.58/4.49/4.48/4.40~4.45/4.38/4.37/4.35/4.34/4.31/4.30/4.29/4.28/4.27~4.0/v3.0/v2.x），详见 references/version-changelog.md |

"""
    content = replace_section(content, "## 版本演进索引", "## 配置驱动", version_section, "版本演进索引")

    # === 4. 精简配置驱动表 ===
    config_section = """## 配置驱动

**核心原则**：所有评审规则、硬约束、项目规范均通过 `config.yaml` 管理，技能本身不含任何业务参数或硬编码值。新增规则只需修改配置文件，无需改动技能本身。

配置文件位置：`.trae/skills/xianyu-backend-code-review/config.yaml`（首次使用从 `config.example.yaml` 复制）。

核心配置节点速查（完整说明详见 config.yaml）：

| 配置节点 | 职责 |
|---|---|
| `scope` | 评审范围（include/exclude_paths, file_extensions, max_files_per_run） |
| `hard_constraints` | 硬约束规则（P0 阻塞级，含 name/pattern/message/severity/auto_fix） |
| `checklist` | 评审检查清单（35+ 大类开启/关闭） |
| `project_conventions` | 项目专属规范（auth_whitelist, required_indexes, webview2_config, kb_index, hf_endpoint） |
| `meta_rules_*` | meta-rules 配置节点（#25-51 落地，含 33_35/38_42/43_47/48_51/governance 等子节点） |
| `refactoring_safety` | 重构安全性配置（v4.61，含 refactor_5step/scope_contract/import_name 等 10 子节点） |
| 其他 | `priority` / `report` / `verify` 详见 config.yaml |

"""
    content = replace_section(content, "## 配置驱动", "## 审查模式", config_section, "配置驱动表")

    # === 5. 精简维度 23-35（使用正确的边界标记）===
    # 维度 23 起始：### 23. Git 操作规范
    # 维度 36 起始：## 维度 36：跨层契约与测试同步（注意是 ## 不是 ###）
    dimensions_23_35 = """### 23. Git 操作规范 🆕v2.1

- 【强制】禁止 `git reset --hard` / `git push --force` / `git branch -D` 等危险操作（除非用户明确要求）
- 【强制】禁止 `git add -A` / `git add .`（应按文件名添加，避免误提交敏感文件）
- 【强制】禁止 `--no-verify` 跳过 hooks
- 【强制】禁止 `git rebase -i`（需要交互输入）
- 【推荐】使用 `git cherry-pick` 时注意冲突解决策略
- 详细规则详见 [references/maintainability.md](file:///d:/code/otherProjects/17_xianyu/.trae/skills/xianyu-backend-code-review/references/maintainability.md)

### 24. 跨字段一致性与硬编码属性禁用 🆕v4.2

核心检查点（详细规则详见 [references/checkpoints-index.md](file:///d:/code/otherProjects/17_xianyu/.trae/skills/xianyu-backend-code-review/references/checkpoints-index.md)）：
- **B-REVIEW-CROSS-FIELD**：跨字段一致性校验（gpu_vendor+gpu_renderer / valid+written_count / layer+cookies）
- **B-REVIEW-NO-HARDCODED-PROPS**：硬编码属性禁用（Cookie httpOnly/secure/sameSite 动态判断）
- **B-REVIEW-NO-CROSS-THREAD-ASYNC**：跨线程异步调用禁用（run_coroutine_threadsafe + future.result 死锁）
- **B-REVIEW-TRY-FINALLY-INIT**：try/finally 变量初始化（finally 引用的变量必须 try 前初始化为 None）
- **B-REVIEW-CROSS-COMPONENT-STATE**：跨组件状态同步（会话有效性多组件判断）
- **B-REVIEW-ERROR-HINT-ROUTABLE**：错误提示端点可操作（引用的 API 端点必须存在）
- **B-REVIEW-FIELD-NORMALIZE-DOC**：字段归一化文档化（v4.16）

### 25. 状态管理与日志治理 🆕v4.8

核心检查点（详见 [references/checkpoints-index.md](file:///d:/code/otherProjects/17_xianyu/.trae/skills/xianyu-backend-code-review/references/checkpoints-index.md)）：
- **B-REVIEW-STATE-FLAG-PRECHECK**：状态标志前置检查（设置后必须有前置检查）
- **B-REVIEW-LOG-DOWNGRADE-STABILITY**：日志降级判断用魔法字符串禁用
- **B-REVIEW-EDIT-VERIFY**：修改后未验证生效
- **B-REVIEW-FREQ-STATS-POLLING**：频率伪装孤岛模块（v4.8）
- **B-REVIEW-TIME-SENSITIVE-SEPARATION**：时间敏感分离
- **B-REVIEW-AUX-LOG-LEVEL**：辅助日志级别

### 26. 缓存/状态判断，Schema 演进规约 🆕v4.15

核心检查点（详见 [references/cache-state-migration-patterns.md](file:///d:/code/otherProjects/17_xianyu/.trae/skills/xianyu-backend-code-review/references/cache-state-migration-patterns.md)）：
- **B-REVIEW-COOKIE-LAYER-STATE**：Cookie 层状态管理
- **B-REVIEW-STATE-CHECK-CATEGORY**：状态检查分类
- **B-REVIEW-BOOTSTRAP-MIGRATION-TXN**：bootstrap/迁移事务

### 27. 多路径数据源一致性与统计聚合校准 🆕v4.17

核心检查点（详见 [references/consistency-and-state-checks.md](file:///d:/code/otherProjects/17_xianyu/.trae/skills/xianyu-backend-code-review/references/consistency-and-state-checks.md)）：
- **B-REVIEW-MULTI-SOURCE-CONSISTENCY**：多源数据一致性
- **B-REVIEW-STATS-AGGREGATION-CALIBRATE**：统计聚合校准
- **B-REVIEW-COUNTER-SEMANTICS**：计数器语义

### 28. LLM 端点能力派发与共享工具函数 🆕v4.23

核心检查点（详见 [references/llm-governance-checks.md](file:///d:/code/otherProjects/17_xianyu/.trae/skills/xianyu-backend-code-review/references/llm-governance-checks.md)）：
- **B-REVIEW-LLM-CAPABILITY-DISPATCH**：LLM 能力驱动派发
- **B-REVIEW-SHARED-TOOL-FUNC**：共享工具函数
- **B-REVIEW-SILENT-DEGRADATION-PRECHECK**：静默降级预检

### 29. 端到端失败原因链与数据完整性闭环 🆕v4.27

核心检查点（详见 [references/consistency-and-state-checks.md](file:///d:/code/otherProjects/17_xianyu/.trae/skills/xianyu-backend-code-review/references/consistency-and-state-checks.md)）：
- **B-REVIEW-FAILURE-CAUSE-CHAIN**：失败原因链完整性
- **B-REVIEW-DATA-INTEGRITY-CLOSED-LOOP**：数据完整性闭环
- **B-REVIEW-ERROR-CODE-BRANCH**：错误码分支处理
- **B-REVIEW-PRECHECK-API-DELEGATION**：precheck API 委托
- **B-REVIEW-MOCK-FIELD-SET-SYNC**：mock 字段集同步

### 30. 数据契约与时序（meta-rules #25-30 落地）🆕v4.29

核心检查点（详见 [references/checkpoints-index.md](file:///d:/code/otherProjects/17_xianyu/.trae/skills/xianyu-backend-code-review/references/checkpoints-index.md)）：
- **B-REVIEW-151~156**：断路器/traceback/datetime 状态同步/error_code/关键字
- 配置参数在 `config.yaml` `meta_rules_25_30` 节点管理

### 31. 业务关键字常量集中管理与跨端契约对齐 🆕v4.31

核心检查点（详见 [references/checkpoints-index.md](file:///d:/code/otherProjects/17_xianyu/.trae/skills/xianyu-backend-code-review/references/checkpoints-index.md)）：
- **B-REVIEW-BUSINESS-KEYWORD-CENTRALIZATION**：业务关键字集中管理
- **B-REVIEW-EVENT-TYPE-EXACT-MATCH**：事件精确匹配
- **B-REVIEW-FIELD-NAME-CASE-SENSITIVE**：字段名大小写敏感
- **B-REVIEW-RESTART-VERIFY**：重启验证
- **B-REVIEW-WINDOWS-ENCODING**：Windows 编码

### 32. 状态恢复与日志规范 🆕v4.30

核心检查点（详见 [references/checkpoints-index.md](file:///d:/code/otherProjects/17_xianyu/.trae/skills/xianyu-backend-code-review/references/checkpoints-index.md)）：
- **B-REVIEW-157 RESUME-PRECHECK**：状态恢复前置校验
- **B-REVIEW-158 DEGRADATION-LOG-MERGE**：降级链日志合并

### 33. 修复前全链路根因扫描协议 🆕v4.31

核心检查点（详见 [references/checkpoints-index.md](file:///d:/code/otherProjects/17_xianyu/.trae/skills/xianyu-backend-code-review/references/checkpoints-index.md)）：
- **B-REVIEW-159 ROOT-CAUSE-SCAN**：修复前全链路根因扫描（覆盖用户层/接口层/数据层/配置层/历史层）

### 34. 前后端字段契约单一可信源 🆕v4.31

核心检查点（详见 [references/checkpoints-index.md](file:///d:/code/otherProjects/17_xianyu/.trae/skills/xianyu-backend-code-review/references/checkpoints-index.md)）：
- **B-REVIEW-160 CONTRACT-SINGLE-SOURCE**：前后端字段契约单一可信源（后端 Pydantic/DB Row 为权威源，前端 types.ts 标注派生来源）

### 35. 列表聚合与状态联动 🆕v4.34

核心检查点（详见 [references/checkpoints-index.md](file:///d:/code/otherProjects/17_xianyu/.trae/skills/xianyu-backend-code-review/references/checkpoints-index.md)）：
- **B-REVIEW-164~168**：列表聚合与状态联动（meta-rules #38-42 落地）
- 配置参数在 `config.yaml` `meta_rules_38_42` 节点管理

"""
    # 使用 "## 维度 36" 作为结束标记（注意是 ## 不是 ###）
    content = replace_section(content, "### 23. Git 操作规范", "## 维度 36", dimensions_23_35, "维度 23-35")

    # === 6. 外移审查判断标准表 ===
    judgment_section = """## 审查判断标准

详细判断标准（阻塞/严重/警告三级表格，含 60+ 条规则）已外部化到 [references/judgment-criteria.md](file:///d:/code/otherProjects/17_xianyu/.trae/skills/xianyu-backend-code-review/references/judgment-criteria.md)。

分类规则速查：
- **P0 阻塞**：硬约束违规（安全漏洞/数据丢失/崩溃）
- **P1 严重**：逻辑错误/性能问题/状态不一致/异常吞掉
- **P2 改进**：代码质量/可维护性/配置化/重复逻辑
- **P3 微调**：风格/注释/命名优化

---
"""
    content = replace_section(content, "## 审查判断标准", "## 与现有工具的关系", judgment_section, "审查判断标准")

    # === 7. 精简快速自检章节 ===
    quick_check_section = """## 快速自检

执行 `pwsh .trae/skills/xianyu-backend-code-review/scripts/auto-scan.ps1` 自动检查以下阻塞项：

1. Token 比较是否使用 `hmac.compare_digest()`（非 `==`）
2. 是否存在硬编码凭据（password/secret/token/api_key）
3. WebView2 子进程是否重定向到 `DEVNULL`
4. WebView2/Playwright 子进程是否使用 `CREATE_NO_WINDOW`（应用 `CREATE_NEW_CONSOLE`）
5. `re`/`threading`/`logging` 是否在模块级导入
6. 是否存在 `except:` + `pass`
7. 是否存在已弃用的 `datetime.utcnow()`（应用 `_utcnow = lambda: datetime.now(timezone.utc)`）
8. SQLite 引擎是否使用 `StaticPool`（应用 `NullPool`）
9. `local_embedding.py` 是否设置 `HF_ENDPOINT` 镜像
10. 是否存在 `e.printStackTrace()` 等价（`print(traceback.format_exc())` 替代日志）

> 完整 B-REVIEW 检查点列表（B-REVIEW-001~312+）详见 [references/checkpoints-index.md](file:///d:/code/otherProjects/17_xianyu/.trae/skills/xianyu-backend-code-review/references/checkpoints-index.md)，按 ID 检索。

"""
    content = replace_section(content, "## 快速自检", "## 审查流程", quick_check_section, "快速自检")

    # === 8. 精简示例用法章节 ===
    example_section = """## 示例用法

### 场景1：迭代发布前评审
```
用户：审查本次迭代的全部后端代码变更
技能：读取 git diff HEAD --name-only 过滤 .py 文件 → 按 36 维度扫描 → 输出 P0/P1/P2/P3 报告
```

### 场景2：指定文件审查
```
用户：审查 src/xianyu_hunter/web/routes/api_accounts.py
技能：读取指定文件 → 加载相关 references（architecture/security/sqlalchemy）→ 输出问题清单
```

### 场景3：仅评审安全问题
```
用户：只看安全相关的后端问题
技能：聚焦维度 7（安全性评审）+ B-REVIEW 硬约束 → 输出安全专项报告
```

> 完整输出模板详见 [templates/report-template.md](file:///d:/code/otherProjects/17_xianyu/.trae/skills/xianyu-backend-code-review/templates/report-template.md)。

"""
    content = replace_section(content, "## 示例用法", "## 输出模板", example_section, "示例用法")

    # === 9. 精简输出模板章节 ===
    output_template_section = """## 输出模板

完整报告模板（含 Critical/Suggestions/Nits/Config Node Missing/What's Good 等章节结构）详见 [templates/report-template.md](file:///d:/code/otherProjects/17_xianyu/.trae/skills/xianyu-backend-code-review/templates/report-template.md)。

报告核心结构速查：
- 审查概览（范围/维度/问题统计/规范版本）
- 问题详情（P0 阻塞 / P1 严重 / P2 改进 / P3 微调）
- 与上次审查对比（新增/已修复/仍存在）
- 好的实践（正面反馈）
- 审查结论与修复验证指引

"""
    content = replace_section(content, "## 输出模板", "## 重要提醒", output_template_section, "输出模板")

    # 写回文件
    path.write_text(content, encoding='utf-8')
    new_len = len(content)
    reduction = original_len - new_len
    reduction_percent = round((reduction / original_len) * 100, 2)
    print(f"\n优化完成: {original_len} → {new_len} 字符（减少 {reduction} 字符，{reduction_percent}%）")


if __name__ == "__main__":
    backend_path = r"d:\code\otherProjects\17_xianyu\.trae\skills\xianyu-backend-code-review\SKILL.md"
    print(f"\n=== 优化 Backend SKILL.md（统一脚本）===")
    optimize_backend(backend_path)
