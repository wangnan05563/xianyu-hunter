# 维度 38：架构层依赖强化

> **编码规范引用**：coding-standards v1.3 §硬约束 + architecture.md
> **配置节点**：config.yaml#architecture_layering（4 个子节点）
> **对应 B-REVIEW**：316~319

## 触发条件
- `libs/` 或 `infra/utils/` 目录代码变更
- 路由层（`web/routes/`）代码变更
- 仓储层（`infra/repo_*.py`）代码变更
- 新增模块/包导入

## 检查规则

### 强制（P0 阻塞）
- **层依赖方向铁律**（B-REVIEW-316）：`domain/` → `infra/` → `modules/` → `web/` 严格单向，禁止反向依赖
- **公共工具库业务无关**（B-REVIEW-317）：`infra/utils/`、`infra/helper/`、`infra/common/` 等公共工具目录不得 import `modules/` 或 `web/`
- **路由业务剥离**（B-REVIEW-318）：`web/routes/api_*.py` 不得直接操作 `session.execute()` 或 `session.commit()`，路由函数主体 ≤ 10 行

### 推荐（P1 严重）
- **仓储抽象复用**（B-REVIEW-319）：`modules/` 不得绕过仓储直接执行 SQL（`session.execute(select(...))` 或 `session.execute(update(...))`），必须通过 `repo_*.py` 封装
- 跨层访问 `_` 前缀私有属性通过公共方法封装，不直接引用
- `container.py`（依赖注入容器）可依赖各层，不受上述限制

### 禁止
- `domain/` 出现 infra/web 的 import
- `infra/utils/` 出现 modules/web 的 import
- 路由函数内嵌 ORM 操作（`session.execute` / `session.commit`）
- 业务模块绕过仓储直接操作数据库

## Grep 扫描命令

```bash
# B-REVIEW-316 层依赖方向
grep -rn "from xianyu_hunter\.infra import" src/xianyu_hunter/domain/ --include="*.py"
grep -rn "from xianyu_hunter\.modules import" src/xianyu_hunter/domain/ --include="*.py"
grep -rn "from xianyu_hunter\.web import" src/xianyu_hunter/domain/ --include="*.py"
grep -rn "from xianyu_hunter\.web import" src/xianyu_hunter/infra/ --include="*.py"
grep -rn "from xianyu_hunter\.web import" src/xianyu_hunter/modules/ --include="*.py"

# B-REVIEW-317 公共工具库业务无关
grep -rn "from xianyu_hunter\.modules\." src/xianyu_hunter/infra/utils/ --include="*.py"
grep -rn "from xianyu_hunter\.web\." src/xianyu_hunter/infra/utils/ --include="*.py"

# B-REVIEW-318 路由业务剥离
grep -rn "session\.execute\|session\.commit" src/xianyu_hunter/web/routes/ --include="*.py"

# B-REVIEW-319 仓储抽象复用
grep -rn "session\.execute(select(" src/xianyu_hunter/modules/ --include="*.py"
grep -rn "session\.execute(update(" src/xianyu_hunter/modules/ --include="*.py"
```

## 判断标准
- `domain/` 出现 infra/web import → P0 阻塞
- `infra/utils/` 出现 modules/web import → P0 阻塞
- 路由层直接 ORM 操作 → P0 阻塞
- `modules/` 绕过仓储直接执行 SQL → P1 严重
- 跨层直接访问私有属性 → P2 改进

## 适用/不适用场景
- **适用**：所有 `src/xianyu_hunter/` 下的 Python 文件
- **不适用**：`tests/` 目录；`infra/container.py` 受容器角色限制不适用 B-REVIEW-317；一次性脚本
