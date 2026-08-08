# 维度 12：日志规约

> **编码规范引用**：coding-standards v1.3 hard constraints §敏感字段日志
> **配置节点**：config.yaml#logging
> **参考文档**：references/maintainability.md §8

## 触发条件
- 新增/修改日志输出时
- 涉及敏感字段（token/cookie/密钥）的记录时
- 配置日志级别时

## 检查规则

### 强制（P0 阻塞）
- 使用 `loguru` 而非标准 `logging` 模块：`from loguru import logger`
- 日志格式使用 `{}` 占位符而非 `%s`：`logger.info("用户 {} 登录", user_id)`
- 敏感信息不记录：token 长度/内容、cookie 内容、密码、密钥
- Token 写入失败必须 `logger.warning()` 告警（不可静默）
- 敏感字段比较只记录布尔结果（匹配/不匹配），不记录原始值

### 推荐（P1 严重）
- 日志级别合理：DEBUG（调试）、INFO（业务关键节点）、WARNING（可恢复异常）、ERROR（需人工介入）、EXCEPTION（带堆栈）
- 关键路径必须 INFO：任务开始/结束、抢单结果、评估完成
- 使用占位符而非 f-string（loguru 可延迟求值）：`logger.info("score={}", score)` 而非 `logger.info(f"score={score}")`
- 脱敏函数统一使用 `mask(s, n=4) -> f"{s[:n]}***{s[-n:]}"`

### 禁止
- `print()` 用于生产代码（用 logger）
- `logging.getLogger()` 而非 `loguru`
- 日志中暴露完整 cookie/密码/密钥
- INFO 级别记录高频循环内部日志
- 日志格式使用 `%s` 占位符

## Grep 扫描命令
```bash
# 检测标准 logging 模块使用
grep -rn "import logging" src/xianyu_hunter/
grep -rn "logging\." src/xianyu_hunter/

# 检测敏感字段日志
grep -rn "logger.*cookie\|logger.*token\|logger.*password\|logger.*secret" src/xianyu_hunter/

# 检测 print 用于生产
grep -rn "^[^#]*print(" src/xianyu_hunter/

# 检测 Token 写入静默失败
grep -rn "token.*write\|save.*token\|dump.*token" src/xianyu_hunter/ -A 5 | grep -v "warning\|exception"
```

## 判断标准
- 使用标准 logging 而非 loguru：P0 阻塞
- 敏感字段记录到日志：P0 阻塞
- Token 写入失败无 warning：P0 阻塞
- 关键路径缺少 INFO：P1 严重
- 高频循环内 INFO：P1 严重

## 适用场景
- 所有业务日志输出
- 错误/异常记录
- Cookie/Token 持久化操作

## 不适用场景
- 单元测试中的 print 调试（不提交到生产）
- 第三方库自身的日志（由库配置控制）
- CLI 工具的用户输出（`click.echo` 等）
