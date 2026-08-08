# 维度 7：安全性评审

> **编码规范引用**：coding-standards v1.3 hard constraints §认证安全
> **配置节点**：config.yaml#security
> **参考文档**：references/security.md

## 触发条件
- 新增/修改 API 端点时
- 处理用户输入或外部数据时
- 涉及 token/cookie/密钥管理时
- 新增数据库查询（含 `text()` SQL）时

## 检查规则

### 强制（P0 阻塞）
- Token 比较必须使用 `hmac.compare_digest()` 防时序攻击
- 401 响应必须返回 JSON 格式 `{"detail": "Unauthorized"}` 而非纯文本
- 认证白名单路由必须包含：`/api/auth/cookie`、`/api/auth/me`、`/api/auth/import-from-browser`、`/import-from-browser/status`、`/api/events/stream`、`/api/notifications`、`/api/notifier/`、`/api/about`、`/api/about/check-update`
- 敏感字段（token/cookie/密钥）不记录到日志
- SQL 注入防护：LIKE 用 `_escape_like()`、表名列名白名单、用户输入绝不拼接到标识符位

### 推荐（P1 严重）
- 所有非白名单 API 端点必须有 `Depends(get_current_user)` 认证
- 资源所有权校验：用户只能访问自己的数据
- 外部 API 响应用 Pydantic 校验后再使用
- 危险操作（删除/批量）需 `confirm_token` 二次确认
- `_REDACT_KEYS` 新增敏感字段时同步更新

### 禁止
- 硬编码凭据（token/密码/密钥）在代码中
- 返回堆栈信息给客户端（`HTTPException(500, detail=str(e))`）
- `os.system(f"cmd {user_input}")` 命令注入风险
- 文件路径直接拼接用户输入（路径穿越）
- `except: pass` 静默吞安全相关异常

## Grep 扫描命令
```bash
# 检测不安全的 token 比较
grep -rn "== token\|!= token\|if token ==" src/xianyu_hunter/

# 检测日志中的敏感字段
grep -rn "logger.*cookie\|logger.*token\|logger.*password\|print.*token" src/xianyu_hunter/

# 检测硬编码凭据
grep -rn "= ['\"][a-zA-Z0-9_-]{20,}['\"]" src/xianyu_hunter/

# 检测命令注入风险
grep -rn "os\.system\|subprocess.*shell=True" src/xianyu_hunter/

# 检测路径穿越风险
grep -rn "open(f['\"]" src/xianyu_hunter/
```

## 判断标准
- 无 hmac.compare_digest()：P0 阻塞
- 敏感信息记录到日志：P0 阻塞
- 缺少认证依赖：P0 阻塞
- 硬编码凭据：P0 阻塞
- 暴露内部错误细节：P1 严重

## 适用场景
- `web/routes/api_*.py` 所有 API 端点
- `web/middleware/auth.py` 认证中间件
- `infra/` 中涉及文件路径、外部输入的处理
- 日志记录代码

## 不适用场景
- 内部工具脚本（不暴露 HTTP 接口）
- 开发/测试环境的调试日志（前提是环境隔离）
- 公开的静态资源端点
