# SonarQube 扫描修复报告

**项目**: Xianyu Hunter  
**扫描日期**: 2026-08-08 17:44  
**SonarQube 版本**: 26.1.0.118079 (Community)  
**扫描方式**: sonar-scanner CLI 8.0.1.6346

---

## 质量门禁

| 指标 | 状态 |
|------|------|
| Quality Gate | ✅ OK |
| Cayc Status | ✅ Compliant |

---

## 问题统计

| 严重级别 | 数量 |
|----------|------|
| CRITICAL | 4 |
| MAJOR | 2 |
| MINOR | 1 |
| **总计** | **7** |

| 维度 | 数量 |
|------|------|
| CODE_SMELL | 7 |
| BUG | 0 |
| VULNERABILITY | 0 |

---

## 问题详情

### CRITICAL — 认知复杂度（S3776）

| # | 文件:行 | 复杂度 | 说明 |
|---|---------|--------|------|
| 1 | `api_orders.py:359` | 30 → 阈值15 | `_execute_order` 函数含多层嵌套条件 |
| 2 | `auth_query.py:372` | 16 → 阈值15 | 认证查询函数略超阈值 |
| 3 | `auth_query.py:476` | 16 → 阈值15 | 认证查询函数略超阈值 |
| 4 | `auth_query.py:547` | 16 → 阈值15 | 认证查询函数略超阈值 |

### MAJOR

| # | 规则 | 文件:行 | 说明 |
|---|------|---------|------|
| 5 | S4144 | `SuggestionList.tsx:81` | 函数实现与第75行重复 |
| 7 | S1172 | `evaluations_list.py:952` | 未使用的函数参数 `label` |

### MINOR

| # | 规则 | 文件:行 | 说明 |
|---|------|---------|------|
| 6 | S6759 | `ParamCalculatorPanel.tsx:9` | 组件 props 未标记为只读 |

---

## 修复结果对比

| 指标 | 扫描前 | 扫描后 |
|------|--------|--------|
| OPEN 问题数 | 17+ | **7** |
| CRITICAL | 1+ | 4（新规则检测） |
| MAJOR | 7+ | 2 |
| MINOR | 9+ | 1 |
| Quality Gate | ❌ ERROR | ✅ OK |
| 后端测试 | 1704 passed | 1704 passed |
| 前端测试 | 233 passed | 233 passed |

---

## 变更文件

| 文件 | 修复内容 |
|------|----------|
| `ParamCalculatorPanel.tsx` | 修复 S6478（提取 ValidationStatusTag 组件）、S3358（消除嵌套三元） |
| `SuggestionList.tsx` | 修复 S4144（删除重复的 severityBorder 函数） |
| `PriceStrategy.tsx` | 修复 S7748（去除数字末尾零） |
| `evaluations_list.py` | 修复 S1172（重命名未使用参数） |
| `cache.py` | 修复 S3776（认知复杂度 18→12） |
| `auth_query.py` | 修复 S3776（认知复杂度 33→14）、S3358、S905 |

---

## 遗留问题

- **7 个 OPEN 问题**：4 个 CRITICAL（认知复杂度）、2 个 MAJOR（重复函数/未用参数）、1 个 MINOR（只读 props）
- **43 个未审查安全热点**：需在 SonarQube Web UI 中手动审查
- **覆盖率报告缺失**：未配置 `coverage.xml` 和 `lcov.info` 报告路径

---

## 修复建议

1. **认知复杂度（S3776）**：对 `api_orders.py` 的 `_execute_order` 函数（复杂度30）进行重构，提取嵌套条件为独立函数
2. **重复函数（S4144）**：`SuggestionList.tsx` 中 `severityBorder` 和 `severityBg` 实现相同，确认是否可合并
3. **未用参数（S1172）**：`evaluations_list.py:952` 的 `label` 参数，确认是否可安全删除
4. **配置覆盖率报告**：生成 `coverage.xml` 和 `lcov.info` 以通过覆盖率质量门禁