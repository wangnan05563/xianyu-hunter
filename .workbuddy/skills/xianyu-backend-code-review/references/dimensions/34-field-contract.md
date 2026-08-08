# 维度 34：前后端字段契约

> **编码规范引用**：coding-standards v1.3 §字段定义单一可信源 / 跨边界访问契约
> **配置节点**：config.yaml#frontend_state_refresh_closed_loop

## 触发条件
- 后端 Pydantic 模型字段增删改
- DB Schema 变更影响 API 响应字段
- 前端 API 类型定义（`types.ts`）变更
- 字段重命名或废弃

## 检查规则

### 强制（P0 阻塞）
- 字段定义必须有单一可信源：后端 Pydantic 模型（或 DB schema）为权威定义，前端 `types.ts` 为镜像消费
- 后端响应新增字段时，前端 `types.ts` 必须同步声明
- 后端字段重命名时，前端必须同步更新（禁止后端已改名但前端仍用旧字段名访问）

### 推荐（P1 严重）
- 前端 `types.ts` ↔ 后端 Pydantic ↔ DB schema 三方对齐：每次 API 变更同步检查三端
- 字段废弃时不直接删除，先标记 `deprecated` 并保留一个版本
- API 函数返回类型与后端响应模型 1:1 对齐（`client.get<ActualResponseType>` 而非 `client.get<any>`）
- 后端 `JSONResponse` 的字段集合必须可验证（用 `OperationResult` 统一模型或专用 DTO）

### 禁止
- 后端响应包含前端未声明的字段（类型漂移）
- 字段定义多源存在且不一致（如 Pydantic 定义为 `item_id: str` 但 DB 为 `itemId`）
- 前端 `types.ts` 用 `any` 类型绕过字段定义
- 字段废弃后直接删除（导致前端消费点 `Property 'xxx' does not exist`）

## Grep 扫描命令

```bash
# 后端响应字段
grep -rn "JSONResponse\|content=\{" src/xianyu_hunter/ --include="*.py"

# 前端 types.ts
grep -rn "interface.*Result\|type.*Response\|export.*type" frontend/src/api/ --include="*.ts"

# Pydantic 模型字段
grep -rn "class.*\(BaseModel\)" src/xianyu_hunter/ --include="*.py" -A 10

# DB schema 字段
grep -rn "sa\.Column\|mapped_column" src/xianyu_hunter/ --include="*.py"

# 字段对齐检查（前后端字段名对比）
grep -rn "item_id\|itemId\|seller_id\|sellerId" src/xianyu_hunter/ --include="*.py" frontend/src/api/ --include="*.ts"
```

## 判断标准
- 后端新增字段前端未声明 → P0 阻塞
- 后端字段重命名前端未同步 → P0 阻塞
- 前端用 `any` 绕过类型 → P1 严重
- 字段定义多源不一致 → P1 严重
- 字段废弃直接删除 → P1 严重

## 适用/不适用场景
- **适用**：所有 API 响应字段变更；新增 API 端点；字段重命名/废弃
- **不适用**：前端内部状态类型（无后端对应）；第三方 SDK 类型
