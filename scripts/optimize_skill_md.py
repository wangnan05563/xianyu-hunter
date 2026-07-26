"""
优化 xianyu-backend-code-review SKILL.md 脚本（第二轮）
处理：审查判断标准、快速自检、示例用法、输出模板等大章节
"""
import sys
from pathlib import Path


def replace_section(content: str, start_marker: str, end_marker: str, replacement: str) -> str:
    """章节级替换：替换从 start_marker 到 end_marker 之间的内容（不含 end_marker）"""
    start_idx = content.find(start_marker)
    if start_idx < 0:
        print(f"  [WARN] 未找到章节起始标记: {start_marker[:50]}")
        return content
    end_idx = content.find(end_marker, start_idx + len(start_marker))
    if end_idx < 0:
        print(f"  [WARN] 未找到章节结束标记: {end_marker[:50]}")
        return content
    before = content[:start_idx]
    after = content[end_idx:]
    return before + replacement + after


def optimize_backend_round2(file_path: str) -> None:
    """优化 backend SKILL.md 第二轮：处理大章节外移"""
    path = Path(file_path)
    content = path.read_text(encoding='utf-8')
    original_len = len(content)

    # === 1. 外移审查判断标准表（替换为引用链接）===
    judgment_section = """## 审查判断标准

详细判断标准（阻塞/严重/警告三级表格，含 60+ 条规则）已外部化到 [references/judgment-criteria.md](file:///d:/code/otherProjects/17_xianyu/.trae/skills/xianyu-backend-code-review/references/judgment-criteria.md)。

分类规则速查：
- **P0 阻塞**：硬约束违规（安全漏洞/数据丢失/崩溃）
- **P1 严重**：逻辑错误/性能问题/状态不一致/异常吞掉
- **P2 改进**：代码质量/可维护性/配置化/重复逻辑
- **P3 微调**：风格/注释/命名优化

---
"""
    content = replace_section(content, "## 审查判断标准", "## 与现有工具的关系", judgment_section)
    print("  [OK] 审查判断标准外移完成")

    # === 2. 精简快速自检章节（保留前 10 行核心检查项，移除详细 B-REVIEW 列表）===
    # 快速自检章节从 "## 快速自检" 到 "## 审查流程"
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
    content = replace_section(content, "## 快速自检", "## 审查流程", quick_check_section)
    print("  [OK] 快速自检章节精简完成")

    # === 3. 精简示例用法章节 ===
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
    content = replace_section(content, "## 示例用法", "## 输出模板", example_section)
    print("  [OK] 示例用法章节精简完成")

    # === 4. 精简输出模板章节（整体替换为引用）===
    output_template_section = """## 输出模板

完整报告模板（含 Critical/Suggestions/Nits/Config Node Missing/What's Good 等章节结构）详见 [templates/report-template.md](file:///d:/code/otherProjects/17_xianyu/.trae/skills/xianyu-backend-code-review/templates/report-template.md)。

报告核心结构速查：
- 审查概览（范围/维度/问题统计/规范版本）
- 问题详情（P0 阻塞 / P1 严重 / P2 改进 / P3 微调）
- 与上次审查对比（新增/已修复/仍存在）
- 好的实践（正面反馈）
- 审查结论与修复验证指引

"""
    # 找到输出模板章节的结束位置（下一个 ## 级标题）
    # 输出模板后面跟着 "## 🔴 Critical (Must Fix)" 等模板内容，一直到 "## 重要提醒"
    content = replace_section(content, "## 输出模板", "## 重要提醒", output_template_section)
    print("  [OK] 输出模板章节精简完成")

    # 写回文件
    path.write_text(content, encoding='utf-8')
    new_len = len(content)
    reduction = original_len - new_len
    reduction_percent = round((reduction / original_len) * 100, 2)
    print(f"  优化完成: {original_len} → {new_len} 字符（减少 {reduction} 字符，{reduction_percent}%）")


if __name__ == "__main__":
    backend_path = r"d:\code\otherProjects\17_xianyu\.trae\skills\xianyu-backend-code-review\SKILL.md"
    print(f"\n=== 优化 Backend SKILL.md 第二轮 ===")
    optimize_backend_round2(backend_path)
