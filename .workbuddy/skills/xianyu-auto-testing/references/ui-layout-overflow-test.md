# UI 布局溢出回归测试

本文档描述模式 F（UI 布局溢出回归测试模式）的详细操作步骤。

模式 F 用于回归验证「操作项分级保留」「多视图一致性」「横向滚动 fallback」「接口字段与 UI 操作集合对齐」四类规则，防止 TaskList 按钮溢出类问题复现。所有参数从 `config.yaml` 的 `ui_layout_overflow_test` 段读取，**禁止在文档中硬编码阈值、正则、文件路径、按钮数量**。

## 1. 操作列按钮数量扫描（F-01）

### 1.1 视图识别

扫描 `scan_glob` 下所有 .tsx 文件（排除 `scan_exclude`），按 `table_view_matchers` 与 `card_view_matchers` 识别表格视图与卡片视图。

```powershell
# {glob}      ← ui_layout_overflow_test.scan_glob
# {exclude}   ← ui_layout_overflow_test.scan_exclude（转为 Select-String -Exclude 模式）
# {table_pat} ← ui_layout_overflow_test.table_view_matchers（join 为 |）
# {card_pat}  ← ui_layout_overflow_test.card_view_matchers（join 为 |）
$files = Get-ChildItem -Path {glob} -Recurse -File | Where-Object {
    $rel = $_.FullName.Replace((Get-Location).Path + "\", "")
    -not ({exclude} | Where-Object { $rel -like $_ })
}
$tableHits = $files | Select-String -Pattern '{table_pat}' -Encoding UTF8
$cardHits  = $files | Select-String -Pattern '{card_pat}'  -Encoding UTF8
```

**输出**：两份文件列表（表格视图文件、卡片视图文件），用于后续按钮计数。

### 1.2 按钮计数

对每个识别出的视图文件，统计操作列内的按钮节点数量。按钮节点识别正则由 `scenarios[F-01].grep_pattern` 提供。

```powershell
# {pattern} ← scenarios[F-01].grep_pattern
# {file}    ← 1.1 输出的文件路径
$buttonCount = (Select-String -Path {file} -Pattern '{pattern}' -Encoding UTF8).Count
```

### 1.3 分级保留判定

按 `action_button_visible_threshold` 与 `collapse_container_strategy` 判定：

| 按钮数 | 判定 | 收起容器策略 |
|--------|------|--------------|
| ≤ `action_button_visible_threshold` | 平铺允许，仍需 F-03 校验 scroll | 无 |
| > `action_button_visible_threshold` 且低频按钮数 ≥1 | 必须分级保留 | 按 `collapse_container_strategy` 选择 |

**低频按钮识别**：根据 `low_frequency_threshold_per_month` 阈值，结合埋点数据或代码注释中的使用频次标注，识别月使用频次 < 阈值的按钮。若无埋点数据，按以下启发式规则识别低频按钮：
- 按钮文本含「另存为」「导出」「模板」「批量」等管理类关键词
- 按钮 `onClick` 中调用的是非主流程 API（非 CRUD）
- 按钮在 `disabled` 状态下大部分时间（如 `disabled={!record.can_export}`）

### 1.4 失败输出格式

```
[F-01 FAIL] {file_path}
  视图类型: table | card
  当前按钮数: {count}
  阈值: {action_button_visible_threshold}
  低频按钮候选: {button_text_list}
  建议收起容器: {collapse_container_strategy.gt6}（按 collapse_container_strategy 选择）
  修复指引: 参见 fix_guidance.button_overflow → step 236 / meta-rule #83 / F-REVIEW-197
```

## 2. 多视图模式一致性验证（F-02）

### 2.1 多视图组件识别

扫描 `multi_view_sync_scan_glob` 下同时声明 `<Table` 与 `<Card` 的组件文件。

```powershell
# {glob}      ← ui_layout_overflow_test.multi_view_sync_scan_glob
# {table_pat} ← table_view_matchers（join 为 |）
# {card_pat}  ← card_view_matchers（join 为 |）
$multiViewFiles = Get-ChildItem -Path {glob} -Recurse -File | Where-Object {
    $content = Get-Content $_.FullName -Raw -Encoding UTF8
    ($content -match '{table_pat}') -and ($content -match '{card_pat}')
}
```

### 2.2 操作集合抽取

对每个多视图组件，抽取两视图的操作集合：

- **表格视图操作集合**：从 `columns=` 附近的 `render` 函数中抽取所有 `<Button`/`<a>`/`<Typography.Link` 的 `key` 属性
- **卡片视图操作集合**：从 `actions=` 数组中抽取相同属性

```powershell
# {file}    ← 2.1 输出的文件路径
# {pattern} ← scenarios[F-02].grep_pattern
$content = Get-Content {file} -Raw -Encoding UTF8
# 用正则抽取 key 属性
$tableKeys = [regex]::Matches($content, 'columns=.*?render.*?key=["\']([^"\']+)["\']') |
    ForEach-Object { $_.Groups[1].Value }
$cardKeys  = [regex]::Matches($content, 'actions=\[.*?key=["\']([^"\']+)["\']') |
    ForEach-Object { $_.Groups[1].Value }
```

### 2.3 一致性比较

若 `multi_view_sync_required = true`，两个集合必须按 `key` 严格一致（顺序允许不同）：

```powershell
$missingInCard  = $tableKeys | Where-Object { $_ -notin $cardKeys }
$missingInTable = $cardKeys  | Where-Object { $_ -notin $tableKeys }
if ($missingInCard -or $missingInTable) {
    # F-02 FAIL
}
```

### 2.4 Hook 同步检查

识别 `useTaskActionHandlers` 等 action handler Hook，验证表格视图与卡片视图调用同一 Hook 实例：

```powershell
# 抽取 Hook 调用语句
$hookCalls = [regex]::Matches($content, 'useTaskActionHandlers\([^)]*\)') |
    ForEach-Object { $_.Value }
if ($hookCalls.Count -gt 1) {
    # 警告：Hook 被多次实例化，应抽取到组件顶层共享
}
```

### 2.5 失败输出格式

```
[F-02 FAIL] {file_path}
  表格视图操作集合: {table_keys}
  卡片视图操作集合: {card_keys}
  缺失于卡片视图: {missing_in_card}
  缺失于表格视图: {missing_in_table}
  Hook 实例数: {hook_count}（应为 1，抽取到组件顶层）
  修复指引: 参见 fix_guidance.multi_view_inconsistency → step 237 / meta-rule #83 / F-REVIEW-198
```

## 3. 横向滚动 fallback 验证（F-03）

### 3.1 scroll 属性检查

对每个识别出的表格视图（来自 1.1），验证 `<Table` 是否声明 `scroll=` 属性：

```powershell
# {file}    ← 1.1 输出的表格视图文件路径
# {pattern} ← scenarios[F-03].grep_pattern
$tableMatches = Select-String -Path {file} -Pattern '{pattern}' -Encoding UTF8
foreach ($m in $tableMatches) {
    if ($m.Line -notmatch 'scroll=') {
        # F-03 FAIL: 未声明 scroll
    }
}
```

### 3.2 scroll 值校验

`scroll` 值必须为 `{ x: '{scroll_fallback}' }` 或显式像素值：

```powershell
# {fallback} ← ui_layout_overflow_test.scroll_fallback
if ($m.Line -notmatch "scroll=\{\{.*x:\s*['""]?{fallback}['""]?.*\}\}" -and
    $m.Line -notmatch 'scroll=\{\{.*x:\s*\d+\.*\}.*\}\}') {
    # F-03 FAIL: scroll 值不符合规范
}
```

### 3.3 卡片视图豁免

卡片视图使用 flex/grid 布局，天然支持换行，不强制 scroll fallback。F-03 仅校验表格视图。

### 3.4 失败输出格式

```
[F-03 FAIL] {file_path}
  <Table 行号: {line_number}
  当前 scroll 值: {current_value}（或 "未声明"）
  期望值: scroll={{{ x: '{scroll_fallback}' }}} 或显式像素值
  修复指引: 参见 fix_guidance.missing_scroll_fallback → step 238 / meta-rule #83 / F-REVIEW-197
```

## 4. 接口字段与 UI 操作集合对齐验证（F-04）

### 4.1 接口契约识别

扫描前端代码识别列表接口与详情接口调用：

```powershell
# {list_pattern}    ← api_field_alignment.list_response_pattern
# {detail_pattern}  ← api_field_alignment.detail_response_pattern
# {scan_glob}       ← ui_layout_overflow_test.scan_glob
$listCalls   = Select-String -Path {scan_glob} -Pattern '{list_pattern}' -Encoding UTF8
$detailCalls = Select-String -Path {scan_glob} -Pattern '{detail_pattern}' -Encoding UTF8
```

### 4.2 返回字段集合抽取

从后端 ResponseModel 中抽取返回字段：

```powershell
# {model_paths}    ← api_field_alignment.backend_response_model_paths
# {model_patterns} ← api_field_alignment.response_model_patterns（join 为 |）
foreach ($path in {model_paths}) {
    $content = Get-Content $path -Raw -Encoding UTF8
    $models = [regex]::Matches($content, '{model_patterns}')
    foreach ($m in $models) {
        # 抽取 BaseModel 子类的字段声明
        $fields = [regex]::Matches($content, '^\s+(\w+):\s', [System.Text.RegularExpressions.RegexOptions]::Multiline)
    }
}
```

### 4.3 UI 操作字段抽取

从视图组件的操作按钮 `onClick` 中抽取依赖的字段：

```powershell
# {scan_glob} ← ui_layout_overflow_test.scan_glob
# 抽取 record.{field} 模式
$uiFields = Select-String -Path {scan_glob} -Pattern 'record\.(\w+)' -Encoding UTF8 |
    ForEach-Object { $_.Matches[0].Groups[1].Value } | Sort-Object -Unique
```

### 4.4 对齐校验

按三类异常校验：

**over-fetching**：返回字段数 > `max_fields_per_list_response`（列表）或 `max_fields_per_detail_response`（详情）

**under-fetching**：UI 操作依赖的字段未在接口返回中声明

```powershell
$underFetching = $uiFields | Where-Object { $_ -notin $responseFields }
```

**action 字段缺失**：`required_status_fields_for_action_buttons` 中声明的字段必须全部存在

```powershell
$missingActionFields = {required_status_fields_for_action_buttons} |
    Where-Object { $_ -notin $responseFields }
```

### 4.5 后端联动

若 F-04 失败，同步触发 `xianyu-backend-code-review` B-REVIEW-237 复查后端 ResponseModel。在测试报告中明确标注联动关系，避免前端单独修复导致契约再次偏离。

### 4.6 失败输出格式

```
[F-04 FAIL] {file_path} ↔ {backend_model_path}
  接口类型: list | detail
  返回字段数: {count}（阈值 {max_fields}）
  UI 依赖字段: {ui_fields}
  ResponseModel 字段: {response_fields}
  over-fetching 字段: {over_fetching_fields}
  under-fetching 字段: {under_fetching_fields}
  缺失 action 字段: {missing_action_fields}
  修复指引: 参见 fix_guidance.field_misalignment → meta-rule #83 / B-REVIEW-237
  联动: 同步触发 xianyu-backend-code-review B-REVIEW-237
```

## 5. 报告生成

测试完成后，按以下结构生成报告（追加到 `references/test-report.md` 模板的「UI 布局溢出回归测试」小节）：

### 5.1 测试范围

- 扫描文件数：{scanned_files}
- 识别表格视图数：{table_views}
- 识别卡片视图数：{card_views}
- 多视图组件数：{multi_view_components}
- 接口契约数：{api_contracts}

### 5.2 测试用例与结果

按 F-01 ~ F-04 分组，列出每个文件的通过/失败/跳过状态：

| 场景 | 文件 | 视图类型 | 按钮数 | 结果 | 详情 |
|------|------|----------|--------|------|------|
| F-01 | TaskList.tsx | table | 6 | FAIL | 超出阈值 5，建议收入 Dropdown |
| F-02 | TaskList.tsx | multi | - | PASS | 两视图操作集合一致 |
| F-03 | TaskList.tsx | table | - | PASS | scroll={{ x: 'max-content' }} |
| F-04 | TaskList.tsx ↔ task.py | list | - | PASS | 字段对齐 |

### 5.3 发现的问题

按场景分类列出问题，每类包含：
- 问题描述
- 涉及文件
- 当前状态（按钮数 / 字段数 / 集合差异）
- 建议修复方向

### 5.4 修复建议

针对每类问题给出具体修复指引，引用 `fix_guidance` 中的 `ref_step` / `ref_meta_rule` / `ref_review`。

### 5.5 关联审查点

列出本次测试触发的所有审查点：
- F-REVIEW-197（操作项分级保留与横向滚动 fallback）
- F-REVIEW-198（多视图模式一致性）
- B-REVIEW-237（接口返回字段与 UI 操作集合对齐）

## 6. 适用与不适用场景

### 6.1 适用场景

参见 `config.yaml#ui_layout_overflow_test.applicable`：
- Ant Design Table + Card 双视图组件
- 操作列含多按钮（≥3 个）的列表页
- 使用 useQuery / useMutation 的数据驱动组件
- 前后端 ResponseModel 契约明确的接口

### 6.2 不适用场景

参见 `config.yaml#ui_layout_overflow_test.not_applicable`：
- 纯展示型组件（无操作列）
- 表单页（无列表/卡片视图）
- 无后端契约的纯前端组件（如配置面板）
- 使用非 Ant Design UI 库的组件（需扩展 `table_view_matchers` / `card_view_matchers`）
