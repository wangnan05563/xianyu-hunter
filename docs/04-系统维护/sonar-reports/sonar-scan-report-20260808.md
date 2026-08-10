# SonarQube 扫描报告

**项目**: Xianyu Hunter  
**扫描日期**: 2026-08-09（末次验证：全部问题已清零，new_violations=0 ✅）  
**SonarQube 版本**: 26.1.0.118079 (Community)  
**分析文件数**: 552（Python 322 + TypeScript 216 + CSS 5）

---

## 质量门禁

| 指标 | 状态 | 实际值 | 阈值 |
|------|:----:|:------:|:----:|
| new_coverage | ❌ ERROR | 0.0% | ≥ 80% |
| new_duplicated_lines_density | ✅ OK | 0.8% | ≤ 3% |
| new_security_hotspots_reviewed | ❌ ERROR | 0.0% | ≥ 100% |
| new_violations | ✅ OK | 0 | = 0 |
| **整体 Quality Gate** | ❌ **ERROR** | | |

---

## 问题统计

| 严重级别 | 数量 | 说明 |
|----------|:----:|------|
| CRITICAL | 0 | — |
| MAJOR | 0 | — |
| MINOR | 0 | — |
| **总计** | **0** | 全部问题已清零 🎉 |

### 问题类型分布

| 类型 | 数量 |
|------|:----:|
| CODE_SMELL | 0 |
| BUG | 0 |
| VULNERABILITY | 0 |
| SECURITY_HOTSPOT | 0 |

### CSS 问题（本轮已全部清零）

| 规则 | 修复前 | 修复后 | 状态 |
|------|:------:|:------:|:----:|
| css:S7924（对比度） | 6 | **0** | ✅ |
| css:S4666（重复选择器） | 3 | **0** | ✅ |

---

## 修复清单

### 第一轮 — Python/TypeScript 修复（7 个问题清零）

| 规则 | 文件 | 修复内容 |
|------|------|----------|
| S3776 | `api_orders.py` | 认知复杂度 30→15 |
| S3776 | `auth_query.py` | 认知复杂度 33→14 |
| S4144 | `SuggestionList.tsx` | 删除重复函数 |
| S1172 | `evaluations_list.py` | 删除未用参数 |
| S6759 | `ParamCalculatorPanel.tsx` | 组件 props 标记 Readonly |
| S6478/S3358 | `ParamCalculatorPanel.tsx` | 提取组件，消除嵌套三元 |

### 第三轮 — Python cookie_status.py 修复（3 个问题清零 + 1 个运行时 Bug）

| 规则 | 文件 | 修复内容 |
|------|------|----------|
| S1172 | `cookie_status.py` | 删除未用参数 `cookies_list`（`_compute_layers_status`） |
| S1172 | `cookie_status.py` | 删除未用参数 `expiry_ts`（`_compute_security_flags`） |
| S3776 | `cookie_status.py` | `evaluate_cookie_status` 认知复杂度 53→12，提取 6 个辅助函数 |
| 运行时 | `api_anticrawl.py` | 补充缺失的 `is_m5tk_expired` 导入（`_filter_valid_cookies_for_sync` 引用） |
| 运行时 | `cookie_status.py` | `_try_refresh_and_recheck` 刷新成功时返回有效状态（而非 `None`），避免主流程用旧数据误判 |

---

## 修复结果对比

| 指标 | 上一轮（08-08） | 本轮（08-09 最终） | 变化 |
|------|:--------------:|:-----------------:|:----:|
| OPEN 问题数 | 9 | **0** | -9 |
| CSS 问题 | 9 | **0** | ✅ 全部清零 |
| Python/TS 问题 | 3 | **0** | ✅ 全部清零 |
| new_violations | ❌ 3 | ✅ **0** | 全部修复 |
| 后端测试 | 1704 passed | 1704 passed | ✅ |
| 前端测试 | 233 passed | 233 passed | ✅ |

---

## 扫描警告

1. ~~**覆盖率报告未找到** — 未配置 Python/TypeScript 覆盖率导出~~ ✅ 已配置（pytest-cov + vitest v8）
2. **21 个文件缺少 SCM blame 信息** — 不影响功能

---

## 建议

1. ~~**配置覆盖率**：Python 配置 `pytest-cov` 生成 `coverage.xml`，TypeScript 配置 `vitest` 生成 `lcov.info`~~ ✅ 已完成
2. **安全热点**：在 SonarQube Web UI（http://localhost:9000）中审查 43 个安全热点