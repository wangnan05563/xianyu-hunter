# 维度 18：Web 层规范

> **编码规范引用**：coding-standards v1.3 §跨边界访问契约
> **配置节点**：config.yaml#web_layer
> **参考文档**：references/architecture.md

## 触发条件
- 新增/修改路由文件时
- 路由函数中出现业务逻辑时
- 新增中间件时

## 检查规则

### 强制（P0 阻塞）
- 路由文件命名：`web/routes/api_*.py`（如 `api_buyer.py`、`api_config.py`）
- HTTP 解析与响应组装在 `web/routes/`，业务逻辑下沉到 `modules/` 或 `web/services/`
- 路由层禁止直接 `session.execute()` / `session.commit()`（B-REVIEW-318）
- 路由通过 `Depends(get_xxx)` 从 container 获取依赖
- 路由层捕获业务异常转为 HTTPException（404/400/500）

### 推荐（P1 严重）
- 路由函数控制在 ≤15 行：只做参数解析、调用 service、错误转换、返回响应
- API 端点必须显式声明 `response_model`
- 统一异常处理中间件覆盖全局（ValidationError → 400、ItemNotFoundError → 404）
- 白名单路由认证检查：白名单端点不拦截
- 向前端错误契约（如 `detail.message` + `detail.errors`）

### 禁止
- 路由文件中写复杂业务逻辑（如评估算法、抢单策略）
- 路由直接 import `async_session` 或手动管理 session
- 路由返回 ORM 对象（应返回 Pydantic 模型）
- 路由函数超过 30 行

## Grep 扫描命令
```bash
# 检测路由直接操作 DB
grep -rn "session\.execute" src/xianyu_hunter/web/routes/
grep -rn "session\.commit" src/xianyu_hunter/web/routes/

# 检测路由文件命名违规
grep -rn "from.*web\.routes\." src/xianyu_hunter/ | grep -v "api_"

# 检测路由缺少 response_model
grep -rn "@router\.(get|post|put|delete|patch)" src/xianyu_hunter/web/routes/ -A 3 | grep -v "response_model"
```

## 判断标准
- 路由直接操作 DB：P0 阻塞
- 路由包含复杂业务逻辑：P0 阻塞
- 缺少 response_model：P0 阻塞
- 路由函数超过 30 行：P1 严重

## 适用场景
- `web/routes/api_*.py` 所有路由文件
- `web/middleware/` 中间件
- 新增 API 端点时

## 不适用场景
- `web/static/` 静态资源（不由 FastAPI 路由管理）
- `web/templates/` Jinja2 模板
- SSR 页面路由（可以稍微放宽行数限制）
