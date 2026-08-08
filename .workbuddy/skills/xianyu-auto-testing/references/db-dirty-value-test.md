# 模式 K：DB 脏值诊断测试

**对应 meta-rule**：#86（配置字段全链路覆盖检查）、#87（空值=恢复默认语义）
**复盘来源**：2026-07-11 智能客服新建会话乱码 Bug（DB welcome_message 被写入占位串 '??????????!'）

### 适用场景
- 用户报告"显示乱码/问号/方块/不可读字符"
- 用户新建会话/记录后显示异常字符
- 配置项值显示为问号或方块
- 前端渲染出现未预期字符

### 不适用场景
- 前端渲染乱码但 DB 值正常 → 改用模式 F 或浏览器 console 检查
- API 返回乱码但 DB 值正常 → 检查后端响应头 Content-Type charset

### 诊断流程（4 步）

1. **K-01 定位脏值字段**：根据功能模块映射表定位 DB 表和字段
2. **K-02 hex 字节检查**：使用 SQLite hex() 函数检查字节序列，区分：
   - 字面占位串（如 0x3F3F3F = '???'）
   - UTF-8 编码乱码（如 0xEFBFBD = U+FFFD 替换字符）
   - GBK 误读为 UTF-8（如 0xCED2C3C7 = "我们" 的 GBK）
3. **K-03 脏值清理**：根据字段类型选择 DELETE（配置覆盖行）/ UPDATE NULL / UPDATE 默认值
4. **K-04 全链路覆盖回归**：grep 验证 5 层链路（DB schema / get_config / update_config / types.ts / Config.tsx）

### 测试用例
- K-TC-01：字面占位串诊断
- K-TC-02：UTF-8 编码乱码诊断
- K-TC-03：配置字段全链路覆盖回归

### 配置参数
所有参数通过 `config.yaml#mode_k_db_dirty_value_diagnosis_test` 管理，包括：
- 触发关键词（user_report_keywords）
- 功能模块→字段映射（module_field_map）
- hex 字节判断规则（byte_analysis_rules）
- 清理策略（cleanup_strategies）
- 5 层链路检查模板（full_chain_check.layers）

### 与其他模式协作
- 诊断完成后触发模式 C（单元测试回归）+ 模式 J（关键路径测试）
- 不适用场景自动重定向到模式 F 或浏览器 console 检查
