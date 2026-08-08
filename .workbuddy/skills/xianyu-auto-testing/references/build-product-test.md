# 模式 Q：构建产物验证测试

> 配置节点：`config.yaml#mode_q_build_product_test`

### 触发关键词
- 验证构建产物 / 测试构建完整性 / 验证工具链版本
- 构建成功但页面异常 / 部署后白屏 / Vite 构建报语法错误 / Node.js 版本不匹配

### 步骤 0：加载配置
读取 `config.yaml` 的 `mode_q_build_product_test` 段。禁止硬编码。

### 步骤 1：工具链版本检查
1. 检查 Node.js 版本是否满足最低要求
2. 检查 npm/pnpm 版本
3. 验证 PATH 优先级（避免系统自带旧版本覆盖）

### 步骤 2：构建产物完整性验证
1. 执行 `build.command` 构建
2. 验证 `dist/` 目录下关键文件存在（index.html, assets/*.js, assets/*.css）
3. 验证 chunk 文件中的关键字符串（路由路径、API 端点）

### 步骤 3：功能冒烟验证
1. 部署构建产物
2. 导航到根路径验证页面可访问
3. 验证 SPA 路由跳转正常
