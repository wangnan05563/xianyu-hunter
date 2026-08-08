# 维度 1：分层架构

> **编码规范引用**：coding-standards v1.3 §2.14 跨边界访问契约
> **配置节点**：config.yaml#architecture_layering
> **参考文档**：references/architecture.md

## 触发条件
- 新增/修改 `src/xianyu_hunter/` 下任意 Python 文件的 import 语句
- 新增模块或调整模块职责时
- 出现循环导入（ImportError/CircularImport）时

## 检查规则

### 强制（P0 阻塞）
- 依赖方向严格单向：`web/ → modules/ → infra/ → domain/`，domain 不依赖任何层
- `domain/` 禁止 import `infra/`、`modules/`、`web/`（B-REVIEW-316）
- `infra/` 禁止 import `modules/`、`web/`（B-REVIEW-316）
- `modules/` 禁止 import `web/`（B-REVIEW-316）
- `container.py` 是唯一 Composition Root，各层通过 container 获取依赖
- 路由层 `web/routes/api_*.py` 禁止直接 `session.execute()` / `session.commit()`（B-REVIEW-318）
- 业务逻辑必须在 `modules/` 或 `web/services/` 中，路由函数只做编排（B-REVIEW-318）

### 推荐（P1 严重）
- 路由函数控制在 ≤15 行，只做参数解析、调用 service、错误转换
- 仓储抽象复用：`modules/` 中禁止绕过仓储直接 `session.execute(select(...))`（B-REVIEW-319）
- `infra/utils/` 等公共工具库保持业务无关，禁止 import `modules/`（B-REVIEW-317）
- 领域模型使用 `@dataclass`，Web 层使用 `pydantic.BaseModel`

### 禁止
- 跨层调用（如 `web/` 直接 import `infra/async_session` 绕过 container）
- 循环依赖（`A` import `B` 且 `B` import `A`）
- 路由函数包含 DB 查询或复杂业务逻辑

## Grep 扫描命令
```bash
# 检测 domain 层依赖 infra/modules/web
grep -rn "from xianyu_hunter\.infra import" src/xianyu_hunter/domain/
grep -rn "from xianyu_hunter\.modules import" src/xianyu_hunter/domain/

# 检测 infra/utils 依赖业务模块
grep -rn "from xianyu_hunter\.modules\." src/xianyu_hunter/infra/utils/

# 检测路由层直接操作 DB
grep -rn "session\.execute" src/xianyu_hunter/web/routes/
grep -rn "session\.commit" src/xianyu_hunter/web/routes/

# 检测 modules 层绕过仓储
grep -rn "session\.execute(select(" src/xianyu_hunter/modules/
```

## 判断标准
- 域层依赖上层：P0 阻塞
- infra/utils 依赖业务模块：P0 阻塞
- 路由直接操作 DB：P0 阻塞
- modules 绕过仓储：P1 严重

## 适用场景
- 所有 `src/xianyu_hunter/` 下的 Python 文件
- 新增业务模块时的分层决策
- 重构时验证依赖方向

## 不适用场景
- `tests/` 目录（无分层约束）
- `container.py`（合法依赖所有层）
- 第三方库/标准库导入
