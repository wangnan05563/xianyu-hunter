# 优化 xianyu-backend-code-review SKILL.md 脚本
# 策略：读取整个文件 → 章节级替换 → 写回文件
# 保留原始换行符（CRLF/LF 混合）和 UTF-8 编码

param(
    [Parameter(Mandatory=$true)]
    [string]$FilePath
)

# 读取整个文件（保留原始字节和换行符）
$content = [System.IO.File]::ReadAllText($FilePath, [System.Text.Encoding]::UTF8)
$originalLength = $content.Length

# === 章节替换辅助函数 ===
function Replace-Section {
    param(
        [string]$content,
        [string]$startMarker,
        [string]$endMarker,
        [string]$replacement
    )

    $startIdx = $content.IndexOf($startMarker)
    if ($startIdx -lt 0) {
        Write-Warning "未找到章节起始标记: $startMarker"
        return $content
    }

    $endIdx = $content.IndexOf($endMarker, $startIdx + $startMarker.Length)
    if ($endIdx -lt 0) {
        Write-Warning "未找到章节结束标记: $endMarker"
        return $content
    }

    $beforeSection = $content.Substring(0, $startIdx)
    $afterSection = $content.Substring($endIdx)
    return $beforeSection + $replacement + $afterSection
}

# === 1. 精简版本演进索引（L16-77 → ~8 行）===
$versionSection = @"
## 版本演进索引

> 完整版本复盘详情详见 [references/version-changelog.md](file:///d:/code/otherProjects/17_xianyu/.trae/skills/xianyu-backend-code-review/references/version-changelog.md)。本表仅列最近 3 个版本，历史版本（v2.0.0 ~ v4.59.0）请查阅该文件。

| 版本 | 新增检查点 | 扫描范围 | 核心变化 |
|---|---|---|---|
| v4.62.0 | B-REVIEW-291~294 | 290->294 | LLM 附加调用预算/超时/结构化解析/多调用一致性（coding-standards v1.3 §2.21-2.24） |
| v4.61.0 | B-REVIEW-281~290 | 280->290 | 重构安全性审查 10 项（配置化重构5步法/作用域契约/导入名称checklist/PowerShell长任务/资源过载容错/SonarQube闭环/弹性恢复/测试三档/跨文件同步/配置统一入口） |
| v4.60.0 | B-REVIEW-275~280 | 274->280 | 缓存守卫三原则/数据写入策略字段级决策/状态机返回值语义/回调注入默认值/跨层闭环验证/Windows编码规范 |
| v2.0.0 ~ v4.59.0 | B-REVIEW-001~274 + 历史 | 0->274 | 历史版本（含 v4.50/4.55/4.57/4.58/4.49/4.48/4.40~4.45/4.38/4.37/4.35/4.34/4.31/4.30/4.29/4.28/4.27~4.0/v3.0/v2.x），详见 references/version-changelog.md |

"@

# 用 "## 配置驱动" 作为结束标记
$content = Replace-Section -content $content -startMarker "## 版本演进索引" -endMarker "## 配置驱动" -replacement $versionSection

# === 2. 精简配置驱动表（L80-101 → ~10 行）===
$configSection = @"
## 配置驱动

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

"@

$content = Replace-Section -content $content -startMarker "## 配置驱动" -endMarker "## 审查模式" -replacement $configSection

# === 3. 精简简介（L15）===
$content = $content -replace '对闲鱼猎人项目后端代码（`backend/xianyu_hunter/` 下的 Python/FastAPI/SQLAlchemy 文件）进行全面的代码评审及逻辑审查。评审涵、\*36 个维、\*，包括[^。]*等、', '对闲鱼猎人项目后端代码（`backend/xianyu_hunter/` 下的 Python/FastAPI/SQLAlchemy 文件）进行全面的代码评审及逻辑审查，覆盖 36 个维度（分层架构/异步并发/数据库规约/安全/性能/错误处理/日志规约/配置管理/智能客服/Git 规范/跨字段一致性/LLM 治理/多用户隔离/跨层契约与测试同步等）。详细规则分布在本文件与 `references/` 下的 16 个主题文件中，按需加载。'

# 写回文件
[System.IO.File]::WriteAllText($FilePath, $content, [System.Text.Encoding]::UTF8)

$newLength = $content.Length
$reduction = $originalLength - $newLength
$reductionPercent = [math]::Round(($reduction / $originalLength) * 100, 2)
Write-Host "优化完成"
Write-Host "原始长度: $originalLength 字符"
Write-Host "优化后长度: $newLength 字符"
Write-Host "减少: $reduction 字符 ($reductionPercent%)"
