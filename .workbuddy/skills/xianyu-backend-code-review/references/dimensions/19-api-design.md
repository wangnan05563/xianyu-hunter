# 维度 19：API 设计规范

> **编码规范引用**：coding-standards v1.3 §硬约束
> **配置节点**：config.yaml#api_design
> **参考文档**：references/security.md §3 / §11

## 触发条件
- 新增/修改 REST API 端点时
- 定义请求/响应数据结构时
- 添加认证中间件时

## 检查规则

### 强制（P0 阻塞）
- RESTful 设计：资源名使用复数、URL 层级清晰（如 `GET /api/items`、`POST /api/items`、`GET /api/items/{id}`）
- 请求/响应模型必须使用 Pydantic BaseModel 明确定义
- 所有非白名单端点必须有 `Depends(get_current_user)` 认证
- 错误响应格式统一：`{"detail": "..."}` 或 `{"detail": {"message": "...", "errors": [...]}}`

### 推荐（P1 严重）
- 分页参数标准化：`page`(默认1) + `page_size`(默认20)，上限加 `min(page_size, 200)` 保护
- 排序参数走白名单校验（防止注入）：仅允许预定义字段
- 过滤参数用 `Query(None)` 可选，支持多值
- 支持游标分页替代 OFFSET 用于大数据量：`?cursor=xxx&limit=20`
- 响应包含 `total` 或 `has_more` 分页元信息

### 禁止
- URL 路径使用动词（如 `/getItem`、`/deleteUser`）：用 `GET /items/{id}`、`DELETE /users/{id}`
- 响应格式不一致（如部分接口返回数组，部分返回 `{"data": [...]}`）
- 敏感字段不经脱敏直接返回
- 无 limit 的列表 API
- 错误信息暴露内部堆栈/路径

## Grep 扫描命令
```bash
# 检测非 RESTful URL 动词
grep -rn "@router.*(get|post|put|delete|patch).*[\"'].*get[A-Z]|.*delete[A-Z]|.*create[A-Z]" src/xianyu_hunter/web/routes/

# 检测缺少认证的路由
grep -rn "@router\." src/xianyu_hunter/web/routes/ -A 5 | grep -v "Depends\|auth_whitelist"

# 检测无 limit 的列表 API
grep -rn "\.all()" src/xianyu_hunter/infra/repo_*.py
```

## 判断标准
- URL 使用动词：P0 阻塞
- 缺少认证：P0 阻塞（非白名单）
- 响应格式不一致：P0 阻塞
- 无 limit 列表：P1 严重
- 分页不标准化：P1 严重

## 适用场景
- `web/routes/api_*.py` 所有 API 端点
- 新增功能的路由设计阶段
- 前后端接口契约评审

## 不适用场景
- WebSocket 端点（`/api/events/stream`）
- 静态资源路由
- SSR 页面模板路由
