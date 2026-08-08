# 维度 33：修复前全链路扫描

> **编码规范引用**：coding-standards v1.3 §跨层影响评估 / 配置化重构 5 步法
> **配置节点**：config.yaml#refactoring_safety.refactor_5step

## 触发条件
- Bug 修复前
- 常量改名/重构
- 字段重命名/废弃
- 函数签名变更

## 检查规则

### 强制（P0 阻塞）
- Bug 修复前必须 Grep 所有调用点：扫描全代码库中对该函数/常量/字段的引用，列出完整的调用链
- 识别跨层影响：修复代码变更必须评估对 `domain/` → `infra/` → `modules/` → `web/` 各层的影响
- 确认所有引用点已同步更新（含 import 语句、文档字符串、注释中的旧名）

### 推荐（P1 严重）
- 修复前记录"当前调用链清单"作为核对清单
- 修复后 Grep 旧名确认无残留引用
- 跨文件引用同步：变更类属性名/模块级常量名时，必须同步更新所有 `import` 和调用点
- 前端 types.ts 同步：后端字段重命名/新增/废弃时，前端类型定义必须同步

### 禁止
- 仅修改定义处不检查调用点（常见反模式：改名后 `from xxx import OLD_NAME` 处报 `ImportError`）
- 常量改函数时调用方遗漏 `()`（如 `_get_timeout` 写成 `_get_timeout` 而非 `_get_timeout()`）
- 修复后无验证日志（无法确认修复生效）

## Grep 扫描命令

```bash
# 步骤 1：列出所有调用点
grep -rn "<OLD_NAME>\|<OLD_CONSTANT>" src/xianyu_hunter/ --include="*.py"

# 步骤 2：检查跨层影响
grep -rn "<CHANGED_NAME>" src/xianyu_hunter/ --include="*.py"

# 步骤 3：修复后确认无残留
grep -rn "<OLD_NAME>" src/xianyu_hunter/ --include="*.py"

# 前端 types.ts 同步
grep -rn "interface.*Result\|type.*Status\|export.*enum" frontend/src/ --include="*.ts" --include="*.tsx"
```

## 判断标准
- 修复后旧名仍有残留引用 → P0 阻塞
- 跨层影响未评估（如只改了 infra 层，web 层调用点未变）→ P0 阻塞
- 常量改函数后调用方缺少 `()` → P0 阻塞
- 修复后无验证日志 → P1 严重
- 前端 types.ts 未同步 → P1 严重

## 适用/不适用场景
- **适用**：所有 Bug 修复；常量/函数/字段重命名；重构操作
- **不适用**：纯新增代码（无旧引用）；测试代码 mock 对象；局部变量重命名
