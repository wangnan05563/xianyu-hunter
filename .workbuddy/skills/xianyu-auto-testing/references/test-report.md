# 测试报告模板

本文档描述全面测试模式步骤 7（生成测试报告）的模板和格式。

## 报告格式

根据 `config.yaml` 的 `report.format`：
- `markdown`：内联 Markdown 格式输出到对话中（默认）
- `json`：结构化 JSON 数据

根据 `report.output`：
- `inline`：直接在对话中输出（默认）
- `file`：写入文件到 `report.output_dir`

## Markdown 报告模板

以下为报告模板，`{...}` 为占位符，执行时替换为实际值。

---

```markdown
## {项目名称}移动端功能测试报告

**测试日期**：{测试日期}
**测试环境**：{浏览器工具类型}（{设备预设}：{视口宽度}x{视口高度}, {移动端标记}, {触摸标记}, {缩放比例}x scale）
**测试地址**：http://{host}:{port}/xianyu/
**认证方式**：{认证类型}

---

### 一、测试范围

| 范围 | 数量 | 说明 |
|------|------|------|
| 移动端页面 | {总页面数} 个路由 | {TabBar核心数} 个 TabBar 核心 + {工具入口数} 个工具入口 + {配置系统数} 个配置系统 + {其他路由数} 个其他路由 |
| 实际测试页面 | {已测试页面数} 个 | {跳过页面数} 个需要具体 ID 的页面无法直接测试 |
| 按钮交互 | {已测试按钮数} 个关键按钮 | TabBar 导航 + Dashboard 入口 + 各页面功能按钮 |
| 决策树检查 | DT-01~DT-08 | {结果}（环境{正常/异常}） |

---

### 二、测试用例与结果

#### 2.1 页面加载测试

| # | 路径 | 页面名称 | 状态 | 关键内容 |
|---|------|---------|------|---------|
| 1 | {path} | {name} | {PASS/FAIL/SKIP} | {关键内容摘要} |
| 2 | {path} | {name} | {PASS/FAIL/SKIP} | {关键内容摘要} |
| ... | ... | ... | ... | ... |

**页面加载通过率：{通过数}/{总数} = {百分比}%**

#### 2.2 按钮交互测试

| # | 页面 | 按钮名称 | 状态 | 验证结果 |
|---|------|---------|------|---------|
| 1 | {页面} | {按钮名} | {PASS/FAIL/SKIP} | {toast/URL变化} |
| 2 | {页面} | {按钮名} | {PASS/FAIL/SKIP} | {toast/URL变化} |
| ... | ... | ... | ... | ... |

**按钮交互通过率：{通过数}/{总数} = {百分比}%**

---

### 三、发现的问题

| # | 问题描述 | 类型 | 严重程度 | 根因类别 | 复现步骤 | 预期结果 | 实际结果 |
|---|---------|------|---------|---------|---------|---------|---------|
| 1 | {问题描述} | {类型} | {严重程度} | {root_cause 或 "-"} | {复现步骤} | {预期结果} | {实际结果} |
| 2 | {问题描述} | {类型} | {严重程度} | {root_cause 或 "-"} | {复现步骤} | {预期结果} | {实际结果} |
| ... | ... | ... | ... | ... | ... | ... | ... |

问题类型取值：console error / 功能异常 / 代码残留 / 异步延迟 / 工具限制 / 测试用例失败
严重程度取值：高 / 中 / 低
根因类别取值（来自 `failure_classification.rules`）：`endpoint_signature_change` / `sync_async_mismatch` / `attribute_rename` / `business_logic` / `uncategorized` / `-`（非测试失败类问题）

#### 3.1 失败分类汇总

> 仅在触发 TR3 失败分类（失败用例数 > `failure_classification.trigger_threshold`）时输出此小节，否则跳过。

| 根因类别 | 中文描述 | 失败用例数 | 占比 | 分配子代理 | 修复结果 |
|---------|---------|-----------|------|-----------|---------|
| `endpoint_signature_change` | 端点签名变更类 | {N} | {%}% | {子代理标识} | {已修复 N / 未修复 M} |
| `sync_async_mismatch` | 同步/异步不匹配类 | {N} | {%}% | {子代理标识} | {已修复 N / 未修复 M} |
| `attribute_rename` | 属性名重构类 | {N} | {%}% | {子代理标识} | {已修复 N / 未修复 M} |
| `business_logic` | 业务逻辑类 | {N} | {%}% | {子代理标识} | {已修复 N / 未修复 M} |
| `uncategorized` | 未命中规则（单独处理） | {N} | {%}% | {子代理标识} | {已修复 N / 未修复 M} |
| **合计** |  | **{总失败数}** | **100%** | **{实际并行数}** | **已修复 {总修复数} / 未修复 {总未修复数}** |

#### 3.2 并行修复执行情况

| # | 子代理标识 | 根因类别 | 负责用例数 | 单模块验证（TR4） | 批量验证（TR4） | 耗时 | 备注 |
|---|-----------|---------|-----------|------------------|----------------|------|------|
| 1 | {agent-1} | {root_cause} | {N} | {PASS/FAIL} | {PASS/FAIL} | {耗时} | {备注} |
| 2 | {agent-2} | {root_cause} | {N} | {PASS/FAIL} | {PASS/FAIL} | {耗时} | {备注} |
| ... | ... | ... | ... | ... | ... | ... | ... |

- **触发阈值**：失败用例数 {实际失败数} {> / ≤} `failure_classification.trigger_threshold`（{阈值}）→ {触发并行修复 / 串行修复}
- **并行子代理数**：实际启动 {N} 个（上限 `parallel_agents`={上限}，桶数={桶数}）
- **单模块验证通过率**：{通过数}/{总数} = {%}%
- **批量验证**：{PASS/FAIL}（{通过数}/{总数}）

---

### 四、解决方案

#### 已修复问题

**问题 {N}：{问题描述}**

- **根因**：{根因分析}
- **修复文件**：
  - [{文件名}]({file:///绝对路径}) - {修复内容摘要}
- **验证方式**：
  1. {验证方式1} ✅
  2. {验证方式2} ✅
  3. {验证方式3} ✅

#### 未修复问题（非 Bug，无需修复）

- **问题 {N}**：{原因说明}

---

### 五、测试结果总结

| 测试项 | 通过 | 失败 | 跳过 | 通过率 |
|--------|------|------|------|--------|
| 页面加载 | {通过数} | {失败数} | {跳过数} | {百分比}% |
| 按钮交互 | {通过数} | {失败数} | {跳过数} | {百分比}% |
| 决策树检查 | {通过数} | {失败数} | {跳过数} | {百分比}% |
| 回归测试 | {通过数} | {失败数} | {跳过数} | {百分比}% |
| **总计** | **{总通过数}** | **{总失败数}** | **{总跳过数}** | **{百分比}%** |

**结论**：{总结性描述}
```

---

## JSON 报告模板

```json
{
  "project": "{项目名称}",
  "test_date": "{测试日期}",
  "environment": {
    "tool": "{浏览器工具类型}",
    "device": "{设备预设}",
    "viewport": "{宽度}x{高度}",
    "url": "http://{host}:{port}/xianyu/",
    "auth_type": "{认证类型}"
  },
  "scope": {
    "total_pages": {总页面数},
    "tested_pages": {已测试页面数},
    "skipped_pages": {跳过页面数},
    "tested_buttons": {已测试按钮数},
    "decision_tree_checks": "DT-01~DT-08"
  },
  "page_results": [
    {
      "id": 1,
      "path": "{路径}",
      "name": "{页面名称}",
      "status": "PASS|FAIL|SKIP",
      "key_content": "{关键内容摘要}",
      "console_errors": []
    }
  ],
  "button_results": [
    {
      "id": 1,
      "page": "{页面}",
      "button_name": "{按钮名}",
      "status": "PASS|FAIL|SKIP",
      "toast": "{toast内容}",
      "url_change": "{URL变化}"
    }
  ],
  "issues": [
    {
      "id": 1,
      "description": "{问题描述}",
      "type": "{类型}",
      "severity": "{严重程度}",
      "root_cause": "{根因类别标识符或 null}",
      "repro_steps": "{复现步骤}",
      "expected": "{预期结果}",
      "actual": "{实际结果}",
      "fixed": true|false,
      "fix_files": ["{文件路径}"],
      "fix_description": "{修复内容}",
      "verified": true|false
    }
  ],
  "failure_classification": {
    "triggered": true|false,
    "failure_count": {失败用例总数},
    "trigger_threshold": {failure_classification.trigger_threshold},
    "parallel_agents_used": {实际并行子代理数},
    "parallel_agents_limit": {failure_classification.parallel_agents},
    "buckets": [
      {
        "root_cause": "{根因类别}",
        "description": "{中文描述}",
        "failure_count": {N},
        "percentage": "{百分比}%",
        "agent_id": "{子代理标识}",
        "fixed_count": {已修复数},
        "unfixed_count": {未修复数},
        "per_module_verification": "PASS|FAIL|N/A",
        "batch_verification": "PASS|FAIL|N/A"
      }
    ],
    "verify_per_module": true|false,
    "verify_batch": true|false,
    "batch_verification_result": "PASS|FAIL"
  },
  "regression": {
    "sw_cleanup": "PASS|FAIL",
    "js_verify": "PASS|FAIL",
    "console_hook": "PASS|FAIL",
    "diagnostic_overlay": "PASS|FAIL",
    "tabbar_navigation": "PASS|FAIL",
    "console_errors": "PASS|FAIL",
    "page_content": "PASS|FAIL"
  },
  "summary": {
    "total_pass": {总通过数},
    "total_fail": {总失败数},
    "total_skip": {总跳过数},
    "pass_rate": "{百分比}%"
  }
}
```

## 报告生成注意事项

1. **所有数据从测试过程中收集**：页面遍历结果、按钮交互结果、问题记录、回归测试结果、失败分类与并行修复执行情况
2. **问题分类要准确**：区分真正的 Bug（需修复）和已知限制（无需修复）
3. **解决方案要具体**：列出修复的文件路径（使用 file:/// 协议可点击链接）、修复内容、验证方式
4. **通过率计算**：通过数 / (通过数 + 失败数)，跳过的不计入分母
5. **结论要简洁**：总结测试结果，说明是否通过、发现的问题是否已修复
6. **失败分类小节按需输出**：3.1 与 3.2 小节仅在触发 TR3（失败用例数 > `failure_classification.trigger_threshold`）时输出；未触发时跳过，根因类别列以 `-` 占位
7. **根因类别对齐配置**：报告中根因类别必须与 `config.yaml#failure_classification.rules` 的 `root_cause` 字段一致，未命中规则的归入 `uncategorized`
8. **并行修复统计要完整**：每个子代理的单模块验证与批量验证结果必须分别记录，便于追溯回归来源
