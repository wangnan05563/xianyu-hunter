"""前端 SKILL.md 统一优化脚本.

设计目标：
- 精简版本演进索引（保留最近 3 个版本，历史版本引用 version-changelog.md）
- 移除内嵌的 v4.36/v4.38 复盘段落（已外移至 version-changelog.md）
- 外移审查判断标准表格（保留分类规则速查，详细表格引用 judgment-criteria.md）
- 外移维度 37-45 的版本复盘段落（保留简短索引，详细复盘引用 version-changelog.md）
- 追加维度 37-45 复盘内容到 version-changelog.md

边界保护：
- 不修改 frontmatter（L1-L11）
- 不修改正文审查规则（L122-L3047，核心维度 1-36）
- 不修改维度 40 前端韧性 Review（L4618+，核心审查规则）
- 替换时使用唯一边界标记避免误删
"""

from __future__ import annotations

import sys
from pathlib import Path

SKILL_PATH = Path(
    r"d:\code\otherProjects\17_xianyu\.trae\skills\xianyu-frontend-code-review\SKILL.md"
)
CHANGELOG_PATH = SKILL_PATH.parent / "references" / "version-changelog.md"


def replace_section(
    content: str,
    start_marker: str,
    end_marker: str,
    replacement: str,
    label: str = "",
) -> str:
    """按唯一边界标记替换章节，避免误删邻近内容."""
    start_idx = content.find(start_marker)
    if start_idx < 0:
        print(f"  [WARN] {label}: 未找到章节起始标记: {start_marker[:60]}")
        return content
    end_idx = content.find(end_marker, start_idx + len(start_marker))
    if end_idx < 0:
        print(f"  [WARN] {label}: 未找到章节结束标记: {end_marker[:60]}")
        return content
    before = content[:start_idx]
    after = content[end_idx:]
    print(
        f"  [OK] {label}: 替换 {end_idx - start_idx} 字符 → {len(replacement)} 字符"
    )
    return before + replacement + after


def extract_section(
    content: str, start_marker: str, end_marker: str, label: str = ""
) -> tuple[str, str]:
    """提取章节内容用于追加到 changelog，返回 (剩余内容, 提取内容)."""
    start_idx = content.find(start_marker)
    if start_idx < 0:
        print(f"  [WARN] {label}: 未找到章节起始标记: {start_marker[:60]}")
        return content, ""
    end_idx = content.find(end_marker, start_idx + len(start_marker))
    if end_idx < 0:
        print(f"  [WARN] {label}: 未找到章节结束标记: {end_marker[:60]}")
        return content, ""
    extracted = content[start_idx:end_idx]
    remaining = content[:start_idx] + content[end_idx:]
    print(
        f"  [OK] {label}: 提取 {len(extracted)} 字符用于追加到 changelog"
    )
    return remaining, extracted


def main() -> int:
    if not SKILL_PATH.exists():
        print(f"[ERROR] SKILL.md 不存在: {SKILL_PATH}")
        return 1

    content = SKILL_PATH.read_text(encoding="utf-8")
    original_size = len(content)
    print(f"[INFO] 原始大小: {original_size} 字符 ({original_size / 1024:.2f} KB)")

    changelog_extra: list[str] = []

    # ===== 步骤 1: 精简版本演进索引 =====
    print("\n[STEP 1] 精简版本演进索引")
    new_version_index = """## 版本演进索引

> 完整版本复盘详情（Sequential Thinking 复盘法、根因分析、检查点详情、对应后端规范）已外部化到 [references/version-changelog.md](file:///d:/code/otherProjects/17_xianyu/.trae/skills/xianyu-frontend-code-review/references/version-changelog.md)。本表仅列最近 3 个版本，历史版本（v2.0.0 ~ v4.59.0）请查阅该文件。

| 版本 | 新增检查点 | 维度 | 扫描范围 | 核心变化 |
|---|---|---|---|---|
| v4.62.0 | F-REVIEW-227~232 | 40 | 132->138 | 前端韧性 Review（Markdown 预处理/React render 副作用/SSE 类型校验/定时器清理/可访问性/流式数据完整性，coding-standards v1.3 §3.10-3.15） |
| v4.61.0 | F-REVIEW-220~226 | 11/4,3/10,11/2,12,12/16,11/6,6/10 | 125->132 | 重构安全性 7 项（常量配置化 5 步法/Hooks 作用域契约/导入名变更 checklist/长任务日志输出/资源过载容错/跨文件契约同步/状态持久化统一入口） |
| v4.60.0 | F-REVIEW-UI-PREVIEW-GATE / STATE-SELECTION / DEFENSIVE-RENDER / COMPONENT-REUSE-RESET | 3,10,7,3 | 125->129 | UI 变更门控/状态选型/防御性渲染/组件复用重置（2026-07-23 12 项历史问题复盘提炼） |
| v2.0.0 ~ v4.59.0 | F-REVIEW-001~219 + 历史 | 1-39 | 0->125 | 历史版本（含 v4.59/v4.58/v4.57/v4.55/v4.52/v4.51/v4.50/v4.49/v4.48/v4.47/v4.46/v4.45/v4.44/v4.43/v4.42/v4.39/v4.38/v4.36/v4.35/v4.34/v4.33/v4.32/v4.31/v4.30/v4.28/v4.27/v4.26/v4.25/v4.24/v4.23/v4.22/v4.20/v4.19/v4.16/v4.15/v4.14/v4.13/v4.12/v4.11/v4.10/v4.9/v4.8/v4.7/v4.6/v4.5/v4.4/v4.3/v4.2/v4.1/v4.0/v3.0/v2.x），详见 references/version-changelog.md |

"""
    content = replace_section(
        content,
        "## 版本演进索引",
        "## 配置驱动",
        new_version_index,
        "版本演进索引",
    )

    # ===== 步骤 2: 移除内嵌的 v4.36/v4.38 复盘段落 =====
    print("\n[STEP 2] 移除内嵌复盘段落（v4.36/v4.38，已外移到 changelog）")
    # v4.36 复盘段落
    v36_start = content.find("> **v4.36.0 注册式资源三件套契约")
    if v36_start >= 0:
        v36_end = content.find("\n---\n", v36_start)
        if v36_end >= 0:
            v36_section = content[v36_start : v36_end + len("\n---\n")]
            changelog_extra.append(
                "\n\n## v4.36.0 注册式资源三件套契约复盘（从 SKILL.md 内嵌段落外移）\n\n"
                + v36_section
            )
            content = content.replace(v36_section, "")
            print(
                f"  [OK] v4.36 内嵌段落: 移除 {len(v36_section)} 字符，追加到 changelog"
            )

    # v4.38 复盘段落
    v38_start = content.find("> **v4.38.0 列表聚合与状态联动复盘")
    if v38_start >= 0:
        v38_end = content.find("\n---\n", v38_start)
        if v38_end >= 0:
            v38_section = content[v38_start : v38_end + len("\n---\n")]
            changelog_extra.append(
                "\n\n## v4.38.0 列表聚合与状态联动复盘（从 SKILL.md 内嵌段落外移）\n\n"
                + v38_section
            )
            content = content.replace(v38_section, "")
            print(
                f"  [OK] v4.38 内嵌段落: 移除 {len(v38_section)} 字符，追加到 changelog"
            )

    # ===== 步骤 3: 外移审查判断标准表格 =====
    print("\n[STEP 3] 外移审查判断标准表格")
    new_judgment_section = """## 审查判断标准

详细判断标准（阻塞/严重/警告三级表格，含 60+ 条规则）已外部化到 [references/judgment-criteria.md](file:///d:/code/otherProjects/17_xianyu/.trae/skills/xianyu-frontend-code-review/references/judgment-criteria.md)。

分类规则速查：
- **P0 阻塞**：硬约束违规（安全漏洞/数据丢失/崩溃/认证失效）
- **P1 严重**：逻辑错误/性能问题/状态不一致/异常吞掉/stale closure
- **P2 改进**：代码质量/可维护性/配置化/重复逻辑/类型注解缺失
- **P3 微调**：风格/注释/命名优化/魔法数字提取

---

"""
    content = replace_section(
        content,
        "## 审查判断标准\n",
        "## 与现有工具的关系",
        new_judgment_section,
        "审查判断标准",
    )

    # ===== 步骤 4: 外移维度 37-45 版本复盘段落 =====
    print("\n[STEP 4] 外移维度 37-45 版本复盘段落")
    # 维度 37-45 的边界：从 "## 37. Provider" 到 "## 40. 前端韧性 Review v4.62.0"
    # 注意：维度 40 重复出现，需保留最后一个（前端韧性 Review）
    dim37_start = content.find("## 37. Provider")
    frontend_resilience_marker = "## 40. 前端韧性 Review v4.62.0"
    dim37_end = content.find(frontend_resilience_marker)
    if dim37_start >= 0 and dim37_end >= 0 and dim37_end > dim37_start:
        dim37_45_section = content[dim37_start:dim37_end]
        changelog_extra.append(
            "\n\n## v4.44~v4.51 维度 37-45 版本复盘段落（从 SKILL.md 外移）\n\n"
            + dim37_45_section
        )
        # 替换为简短索引
        replacement = """## 维度 37-45 版本复盘索引

> 各版本复盘详情（Provider UI/Per-Preset Credential/Model Name Case-Sensitivity/Config Persistence/Multi-User Cookie Isolation/Backend Logic Visibility/Static Build Artifact/Polling Timeout Display 等 9 个维度的详细检查点描述）已外部化到 [references/version-changelog.md](file:///d:/code/otherProjects/17_xianyu/.trae/skills/xianyu-frontend-code-review/references/version-changelog.md)。

| 维度 | 版本 | 核心主题 | 关键 F-REVIEW |
|---|---|---|---|
| 37 | v4.46 | Provider UI 状态管理 | F-REVIEW-162~166 |
| 38 | v4.47 | Per-Preset Credential Management | F-REVIEW-167~169 |
| 39 | v4.44 | Per-Preset Credential Frontend Contract | F-REVIEW-170~172 |
| 40 | v4.48 | Model Name Case-Sensitivity | F-REVIEW-173~174 |
| 41 | v4.48 | Config Persistence and Reflection | F-REVIEW-175~177 |
| 42 | v4.45 | Multi-User Cookie Isolation Frontend | F-REVIEW-178~181 |
| 43 | v4.49 | Backend Logic Visibility Sync | F-REVIEW-182~184 |
| 44 | v4.49 | Static Build Artifact Awareness | F-REVIEW-185~187 |
| 45 | v4.51 | Polling Timeout Display | F-REVIEW-191 |

> 维度 37-45 中关于复盘段落 A/B/C/D（2026-07-22 评估页/快照职责分离/cookie 自愈等）的详细描述也已在 version-changelog.md 中。

"""
        content = content[:dim37_start] + replacement + content[dim37_end:]
        print(
            f"  [OK] 维度 37-45 复盘段落: 移除 {len(dim37_45_section)} 字符，替换为索引 {len(replacement)} 字符"
        )
    else:
        print(
            f"  [WARN] 维度 37-45 边界未找到 (start={dim37_start}, end={dim37_end})"
        )

    # ===== 步骤 5: 写回 SKILL.md =====
    print("\n[STEP 5] 写回 SKILL.md")
    SKILL_PATH.write_text(content, encoding="utf-8")
    new_size = len(content)
    reduction = (1 - new_size / original_size) * 100
    print(
        f"  [OK] SKILL.md: {original_size} → {new_size} 字符 "
        f"({original_size / 1024:.2f} KB → {new_size / 1024:.2f} KB, "
        f"减少 {reduction:.2f}%)"
    )

    # ===== 步骤 6: 追加版本复盘内容到 version-changelog.md =====
    print("\n[STEP 6] 追加版本复盘内容到 version-changelog.md")
    if changelog_extra:
        existing = CHANGELOG_PATH.read_text(encoding="utf-8") if CHANGELOG_PATH.exists() else ""
        append_text = "\n".join(changelog_extra)
        # 在文件开头插入（按时间倒序，最近的 v4.44~v4.51 + v4.38 + v4.36 在前）
        new_changelog = append_text + "\n\n" + existing
        CHANGELOG_PATH.write_text(new_changelog, encoding="utf-8")
        print(
            f"  [OK] version-changelog.md: 追加 {len(append_text)} 字符，"
            f"新大小 {len(new_changelog)} 字符 ({len(new_changelog) / 1024:.2f} KB)"
        )
    else:
        print("  [SKIP] 无需追加内容")

    print("\n[DONE] 优化完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
