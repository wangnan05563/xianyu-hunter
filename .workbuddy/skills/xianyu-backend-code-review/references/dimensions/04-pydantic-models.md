# 维度 4：Pydantic 2.x 模型

> **编码规范引用**：coding-standards v1.3 §CFG-09 / §CFG-10
> **配置节点**：config.yaml#pydantic_models

## 触发条件
- 新增/修改 Pydantic BaseModel 子类时
- 使用 `.dict()` / `.json()` 等 Pydantic v1 方法时
- 定义请求/响应模型时
- 区分"未传"与"传 null"语义时

## 检查规则

### 强制（P0 阻塞）
- Pydantic 2.x 写法：使用 `model_dump()` 替代 `.dict()`，`model_validate()` 替代 `.parse_obj()`，禁止使用 `.json()`
- 请求/响应模型必须继承 `pydantic.BaseModel`
- API 端点必须显式声明 `response_model`
- 字段约束用 `Field(..., min_length=N, max_length=N, ge=N, le=N)` 标注
- 业务约束用 `@model_validator(mode="after")` 实现

### 推荐（P1 严重）
- 区分"未传" vs "null"时使用 `model_dump(exclude_unset=True)`
- 领域模型使用 `@dataclass`，禁止 Pydantic 渗透到 domain 层
- 配置模型使用 `extra="ignore"` 保证向后兼容
- 字段级自定义校验用 `@field_validator`
- 错误信息中文且不暴露内部字段名

### 禁止
- Pydantic v1 残余写法：`.dict()`、`.parse_obj()`、`.parse_raw()`、`.json()`、`.copy()`
- 领域模型（`domain/`）中使用 Pydantic（应用 `@dataclass`）
- `extra="forbid"` 未经充分测试就用（可能破坏前端兼容性）
- 校验错误暴露敏感内部路径

## Grep 扫描命令
```bash
# 检测 Pydantic v1 残余 API
grep -rn "\.dict()" src/xianyu_hunter/
grep -rn "\.parse_obj(" src/xianyu_hunter/
grep -rn "\.parse_raw(" src/xianyu_hunter/
grep -rn "\.json()" src/xianyu_hunter/

# 检测 domain 层使用 Pydantic
grep -rn "from pydantic import" src/xianyu_hunter/domain/
grep -rn "BaseModel" src/xianyu_hunter/domain/

# 检测 API 端点缺少 response_model
grep -rn "@router\.(get|post|put|delete|patch)" src/xianyu_hunter/web/routes/ -A 3 | grep -v "response_model"
```

## 判断标准
- Pydantic v1 残余 API：P0 阻塞
- domain 层使用 Pydantic：P0 阻塞
- API 端点缺少 response_model：P0 阻塞
- 缺少字段约束：P1 严重
- 校验错误信息不清晰：P1 严重

## 适用场景
- `web/routes/api_*.py` 中的请求/响应模型定义
- `infra/yaml_config.py` 中的配置模型
- 任何 `pydantic.BaseModel` 子类

## 不适用场景
- `domain/` 层（应使用 `@dataclass`）
- 非序列化/校验场景的普通类
- 第三方库的模型定义
