"""
优化 xianyu-backend-code-review SKILL.md 第三轮
重点处理：维度 23-35（meta-rules 落地章节）精简为索引
策略：保留维度名 + 核心规则速查 + 检查点 ID 列表 + references 链接
"""
import re
from pathlib import Path


def optimize_backend_round3(file_path: str) -> None:
    """优化 backend SKILL.md 第三轮：精简维度 23-35"""
    path = Path(file_path)
    content = path.read_text(encoding='utf-8')
    original_len = len(content)

    # 维度 23-35 的精简版本（保留核心规则速查 + 检查点 ID 索引）
    # 这些维度的详细内容已在 references/checkpoints-index.md 中
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

    # 替换维度 23-35（从 "### 23." 到 "### 36."）
    start_marker = "### 23. Git 操作规范"
    end_marker = "### 36."

    start_idx = content.find(start_marker)
    if start_idx < 0:
        print("  [WARN] 未找到维度 23 起始位置")
        return

    end_idx = content.find(end_marker, start_idx)
    if end_idx < 0:
        print("  [WARN] 未找到维度 36 起始位置")
        return

    content = content[:start_idx] + dimensions_23_35 + content[end_idx:]
    print("  [OK] 维度 23-35 精简完成")

    # 写回文件
    path.write_text(content, encoding='utf-8')
    new_len = len(content)
    reduction = original_len - new_len
    reduction_percent = round((reduction / original_len) * 100, 2)
    print(f"  优化完成: {original_len} → {new_len} 字符（减少 {reduction} 字符，{reduction_percent}%）")


if __name__ == "__main__":
    backend_path = r"d:\code\otherProjects\17_xianyu\.trae\skills\xianyu-backend-code-review\SKILL.md"
    print(f"\n=== 优化 Backend SKILL.md 第三轮 ===")
    optimize_backend_round3(backend_path)
