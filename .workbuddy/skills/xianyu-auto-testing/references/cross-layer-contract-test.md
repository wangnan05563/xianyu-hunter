# 模式 M：跨层数据契约一致性测试

> 对应 meta-rule #88（CROSS-LAYER-CONTRACT-SYNC）/ B-REVIEW-248 / F-REVIEW-200
> 配套 config 节点：`config.yaml#mode_m_cross_layer_contract_test`

### 何时触发

满足以下任一条件即触发：
- 用户要求"测试跨层数据一致性" / "验证字段覆盖策略" / "测试组件复用状态重置"
- 用户报告"采集后数据消失" / "图片 URL 被清空" / "切换商品图片显示错误占位图"
- 用户报告"官方采集后字段未更新" / "重采后旧值残留"
- `mode_m_cross_layer_contract_test.key_files` 的 backend 或 frontend 中任一文件被修改后需要回归验证
- `_ALWAYS_OVERWRITE` / `_coalesce` / `_NULL_SAFE` 集合定义修改后
- React 组件复用相关代码（ThumbCell / ImagePreview / 列表项组件）修改后
- 后端 ResponseModel 字段新增/删除/重命名后

### 步骤 0：加载配置

读取 `config.yaml`，重点关注以下配置段：
- `mode_m_cross_layer_contract_test.unit_test`：单元测试文件、pytest 命令模板
- `mode_m_cross_layer_contract_test.frontend_test`：前端测试命令、组件复用测试用例
- `mode_m_cross_layer_contract_test.integration_test`：集成测试日志、API 端点
- `mode_m_cross_layer_contract_test.key_files`：关键代码路径（backend + frontend）
- `mode_m_cross_layer_contract_test.overwrite_strategy`：覆盖策略集合定义与字段映射

**禁止在流程中编码任何字段名、集合名、API 端点、选择器**。所有参数从 `config.yaml` 读取。

### 步骤 1：后端覆盖策略验证

详细操作见 `references/cross-layer-contract-test.md` 的"后端覆盖策略"部分。

1. **扫描覆盖策略集合定义**：执行 `overwrite_strategy.scan_command`，找到 `_ALWAYS_OVERWRITE` / `_coalesce` / `_NULL_SAFE` 集合定义
2. **验证字段归类正确性**：对 `overwrite_strategy.field_classification` 中每个字段：
   - 检查是否在正确的集合中
   - `always_overwrite_fields` 中的字段必须是"每次采集必定获取到"
   - `coalesce_fields` 中的字段是"采集可能返回空"
   - `null_safe_fields` 中的字段是"空值不清空"
3. **空值语义验证**：对 `overwrite_strategy.empty_value_test_cases` 中每个用例：
   - 模拟外部 API 返回 `None`（显式空值）→ 验证是否覆盖旧值
   - 模拟外部 API 未返回该字段（字段缺失）→ 验证是否保留旧值
   - **禁止**把"字段缺失"当作"显式空值"处理

### 步骤 2：前端组件复用状态重置验证

详细操作见 `references/cross-layer-contract-test.md` 的"前端组件复用"部分。

1. **扫描含内部状态的组件**：执行 `frontend_test.component_scan_command`，找到含 `useState(errored/loaded/loading)` 的组件
2. **验证 useEffect 重置**：对 `frontend_test.component_reuse_test_cases` 中每个用例：
   - 检查组件是否在列表/展开行/Tab 面板中使用（`rowKey` 不变场景）
   - 检查 prop 变化时是否用 `useEffect` 重置内部状态
   - 验证重置字段覆盖 `frontend_test.reset_fields`（默认 `['errored', 'loaded', 'loading']`）
3. **前端构建验证**：执行 `frontend_test.build_command`，确保 TypeScript 编译零错误

### 步骤 3：集成测试验证

详细操作见 `references/cross-layer-contract-test.md` 的"集成测试"部分。

1. **环境准备**：复用诊断模式 DT-01 ~ DT-03，确保服务已用最新代码重启
2. **采集-更新-展示链路验证**：
   - 触发官方采集/重采（`integration_test.trigger_endpoint`）
   - 验证 DB 中字段值是否正确（`integration_test.db_check_query`）
   - 验证 API 返回值是否正确（`integration_test.api_check_endpoint`）
   - 验证前端展示是否正确（`integration_test.frontend_check_selector`）
3. **空值场景验证**：
   - 模拟采集未获取到图片（`integration_test.empty_value_scenario`）
   - 验证旧值是否保留（不应被 `None` 覆盖）
   - 验证前端展示是否仍显示旧图片（不应显示占位图）

### 步骤 4：诊断输出

报告包含：
1. **后端覆盖策略验证结果**：字段归类正确性、空值语义验证
2. **前端组件复用状态重置验证结果**：组件扫描、useEffect 重置、构建验证
3. **集成测试链路验证结果**：采集→DB→API→前端全链路一致性
4. **发现的问题**：问题描述、关联的 `key_files` 条目、发现步骤、建议修复方案
