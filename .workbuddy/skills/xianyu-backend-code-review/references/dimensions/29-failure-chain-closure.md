# 维度 29：失败原因链与闭环

> **编码规范引用**：coding-standards v1.3 §异常消息脱敏 / 分层错误处理
> **配置节点**：config.yaml#consistency_and_state_checks.error_sanitize

## 触发条件
- 异常处理代码（try/except）
- 错误消息透传（infra → modules → web → 前端）
- 自愈/重试最终放弃分支
- 多级错误包装

## 检查规则

### 强制（P0 阻塞）
- 错误原因必须从底层传递到前端展示：每一层 except 块不能吞掉原始异常信息
- 每层错误包装必须保留原始原因：`raise NewError(...) from original_exc` 方式链接异常链
- 失败原因链不可断裂：中间层不能将详细错误替换为模糊描述（如将 `"Cookie 过期：token=_m_h5_tk"` 替换为 `"请求失败"`）

### 推荐（P1 严重）
- 异常消息写入日志/DB/响应前必须脱敏（过滤 token / cookie / webhook URL 等敏感字段）
- 自愈/重试最终放弃时记录诊断日志（关键状态变量：存在性、过期时间、一致性）
- 数据完整性闭环：写入操作异常后验证数据一致性（如 `SELECT COUNT(*)` 确认写入结果）
- 前端展示的错误消息应对用户可操作（给出下一步建议，而非原始技术异常）

### 禁止
- `except: pass` 静默吞异常
- 中间层将底层异常替换为无意义通用消息
- 异常消息直接 `str(e)[:N]` 未脱敏写入日志
- 自愈均失败后无诊断日志直接 `return None`

## Grep 扫描命令

```bash
# 静默吞异常
grep -rn "except.*:\s*$" src/xianyu_hunter/ --include="*.py" -A 1 | grep "pass\|return None"

# 异常脱敏
grep -rn "str\(e\)\|str\(exc\)\|repr\(e\)" src/xianyu_hunter/ --include="*.py" | grep -v "_sanitize_error"

# 异常链断裂
grep -rn "raise\s+\w+Error" src/xianyu_hunter/ --include="*.py" | grep -v " from "

# 诊断日志
grep -rn "_log_.*_diagnostics\|logger\.warning.*give_up\|logger\.error.*exhausted" src/xianyu_hunter/ --include="*.py"

# 数据完整性闭环
grep -rn "SELECT COUNT\|\.count()" src/xianyu_hunter/ --include="*.py" | grep -i "after\|verify\|check"
```

## 判断标准
- `except: pass` 吞异常 → P0 阻塞
- 中间层替换原始异常为模糊描述 → P0 阻塞
- `str(e)` 未脱敏 → P1 严重
- 自愈失败无诊断日志 → P1 严重
- 写入后未验证数据完整性 → P1 严重

## 适用/不适用场景
- **适用**：所有异常处理代码；自愈/重试机制；多层级 API 调用链
- **不适用**：仅在内存中处理的异常（不持久化/不传输）；`__main__` 入口的顶层异常捕获
