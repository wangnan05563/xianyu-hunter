# 维度 20：测试建议

> **编码规范引用**：coding-standards v1.3 §测试覆盖
> **配置节点**：config.yaml#testing
> **参考文档**：references/maintainability.md §7

## 触发条件
- 新增/修改功能代码时
- 重构已有逻辑时
- 新增数据校验规则时
- 修改常量或配置时

## 检查规则

### 强制（P0 阻塞）
- 改动点必须有对应测试：每个新功能/修改必须有至少一个测试用例
- 正常路径测试：验证核心功能的 happy path
- 边界值测试：空值、零值、极大极小值、刚好等于阈值

### 推荐（P1 严重）
- 异常路径测试：错误输入、外部依赖失败、超时
- 向后兼容验证：已有测试用例仍然通过
- 常量变更生效验证：配置修改后测试确认新值生效
- 新增守卫边界测试：如 `pass_score <= auto_buy_score` 越界应抛异常
- 使用 pytest-asyncio 测试异步代码
- 通过构造函数注入 mock 依赖（不走 container），优先 mock 公共方法而非私有属性

### 禁止
- 只测试 happy path 不测边界和异常
- 测试依赖外部服务（数据库/HTTP API）不 mock
- 测试中直接访问被测类的 `_` 前缀私有属性（应 mock 公共方法）
- 测试之间有共享状态（必须隔离）

## Grep 扫描命令
```bash
# 检测修改文件是否有对应测试
# 手动对比：diff 中的 .py 文件 vs tests/ 目录

# 检测异常路径覆盖
grep -rn "pytest\.raises" tests/

# 检测异步测试标记
grep -rn "pytest\.mark\.asyncio" tests/

# 检测 mock 使用
grep -rn "Mock\|MagicMock\|AsyncMock" tests/
```

## 判断标准
- 改动点无对应测试：P0 阻塞
- 无边界值测试：P1 严重
- 无异常路径测试：P1 严重
- 测试依赖外部服务未 mock：P1 严重

## 适用场景
- 所有 `src/xianyu_hunter/` 下的功能代码改动
- 新增 API 端点
- 新增/修改业务逻辑
- 配置校验规则变动

## 不适用场景
- 纯文档/注释修改
- 第三方库版本升级（无功能变更）
- 格式化/import 排序等纯样式变更
- `.gitignore`/`.env.example` 等非代码文件
