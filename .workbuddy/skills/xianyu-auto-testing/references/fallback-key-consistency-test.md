# 模式 O：回退构造关联键一致性测试

**触发场景**：回退构造逻辑修改后、关联键注入改动后、时间窗口查询修改后
**配置节点**：`config.yaml#mode_o`
**参考文档**：`references/fallback-key-consistency-test.md`

### 步骤 0：加载配置
读取 `config.yaml`，重点关注以下配置段：
- `mode_o.steps`：各测试步骤的配置（o1~o4 子步骤的 test_file、test_cases、pass_condition）
- `mode_o.key_files`：关键代码路径（用于代码变更后回归测试范围判定）
- `mode_o.refs`：引用的后端/前端审查规范和元规则编号

**禁止在流程中编码任何路径、命令、关联键名**。所有参数从 `config.yaml` 读取。

### 步骤 1：回退构造关联键完整性验证
1. **扫描所有回退构造点**：执行 Select-String 命令扫描 `required_keys` 中的关联键在 `key_files` 中的使用
2. **验证关联键注入**：对每个回退构造点，验证是否同时查询并注入了所有 `required_keys` 中的关联键
3. **验证下游条件判断**：对每个使用关联键的下游条件判断（如 `if task_id:`），验证上游回退构造是否注入了该键

### 步骤 2：时间窗口回退验证
1. **扫描所有时间窗口查询**：执行 Select-String 命令扫描 `range_days` 在 `key_files` 中的使用
2. **验证全量回退**：对每个时间窗口查询，验证窗口无数据时是否有全量回退逻辑
3. **验证 source 标注**：验证回退查询的结果是否标注了数据来源

### 步骤 3：PowerShell 外部命令验证
1. **扫描所有 PowerShell 脚本**：执行 Select-String 命令扫描 `conflicting_aliases` 中的命令在 `scan_globs` 中的使用
2. **验证 .exe 后缀**：验证 curl/wget 等命令是否使用了 .exe 后缀
3. **验证 JSON body 传递**：验证 JSON body 是否通过文件传递而非行内引号转义

### 步骤 4：生成测试报告
输出诊断报告，包含：
1. **回退构造关联键完整性**：每个回退构造点的关联键注入状态
2. **时间窗口回退状态**：每个时间窗口查询的回退逻辑状态
3. **PowerShell 外部命令状态**：每个外部命令的后缀使用状态
4. **发现的问题**：问题描述、关联的 key_files 条目、建议修复方案
