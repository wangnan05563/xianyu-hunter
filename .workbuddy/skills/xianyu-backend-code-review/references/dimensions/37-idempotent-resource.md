# 维度 37：资源创建幂等性

> **编码规范引用**：coding-standards v1.3 §coding-standards §规范 31
> **配置节点**：config.yaml#idempotent_resource_creation
> **对应 references**：idempotent-resource-creation-checks.md（B-REVIEW-313~315）

## 触发条件
- 资源创建/启动/注册接口（`POST /xxx/start`、`/xxx/create`、`/xxx/register`、`/xxx/launch`）
- 网络重试场景的写操作
- 前端"启动/恢复"按钮对应的后端接口

## 检查规则

### 强制（P0 阻塞）
- **创建接口必须幂等**（B-REVIEW-313）：重复调用返回当前状态 + `already_active` / `already_exists` 标志，不重复创建资源
- **禁止用失败表达已存在**：禁止用 `ok: False` + error 消息表达"资源已存在"语义——这是前端状态矛盾的根因
- **响应结构契约**（B-REVIEW-314）：所有写操作必须用 `OperationResult` 模型（`ok` + `already_active` + `message`），缺少 `ok` 字段视为 P0

### 推荐（P1 严重）
- **前端状态闭环**（B-REVIEW-315）：后端响应新增标志位（如 `already_active`）时，前端 `types.ts` 必须同步声明；API 函数返回类型必须与后端 1:1 对齐
- 单元测试必须覆盖"首次创建 + 重复创建"两个场景
- 资源已存在时返回 `already_active: True`，前端根据此字段显示 `info` 级别提示而非错误提示

### 禁止
- 返回 `{"ok": False, "error": "资源已存在"}` 表达已存在
- 接口无 `already_active` / `already_exists` 字段区分"首次创建"与"已存在"
- 单元测试缺少 `test_xxx_already_active` 或等价用例

## Grep 扫描命令

```bash
# 创建类接口
grep -rn "@router\.post.*start\|@router\.post.*create\|@router\.post.*register\|@router\.post.*launch" src/xianyu_hunter/ --include="*.py"

# ok:False 表达已存在
grep -rn "\"ok\".*False.*已存在\|already.*active.*ok.*False\|ok.*False.*already" src/xianyu_hunter/ --include="*.py"

# OperationResult 模型
grep -rn "OperationResult\|ok.*already_active\|already_active.*ok" src/xianyu_hunter/ --include="*.py"

# 前端 types.ts 对齐
grep -rn "interface.*Result\|already_active\|already_exists" frontend/src/api/ --include="*.ts"
```

## 判断标准
- 创建接口非幂等 → P0 阻塞
- `ok: False` 表达已存在 → P0 阻塞
- 缺少 `ok` 字段 → P0 阻塞
- 缺少 `already_active` / `already_exists` → P0 阻塞
- 单元测试缺少幂等用例 → P1 严重
- 前端 types.ts 缺少新增标志位 → P1 严重

## 适用/不适用场景
- **适用**：所有资源创建/启动/注册接口；网络重试场景；前端启动/恢复按钮后端
- **不适用**：纯查询接口（天然幂等）；计数器递增接口；一次性副作用（如发短信验证码，需用 token 防重）
