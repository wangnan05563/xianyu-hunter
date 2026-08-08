# 维度 21：架构与分层

> **编码规范引用**：coding-standards v1.3 §硬约束 / 项目分层架构
> **配置节点**：config.yaml#architecture_layering

## 触发条件
- 新增模块/目录/包
- 架构变更（分层结构调整）
- 跨层 import 新增
- 仓储/路由/模块文件新增或重构

## 检查规则

### 强制（P0 阻塞）
- 新模块必须遵循 `domain/ → infra/ → modules/ → web/` 分层结构，依赖方向严格单向
- `domain/` 禁止 import `infra/`、`modules/`、`web/`
- `infra/` 禁止 import `modules/`、`web/`
- `modules/` 禁止 import `web/`
- 路由层（`web/routes/`）不得直接操作 `async_session` 或执行业务逻辑

### 推荐（P1 严重）
- `libs/` 或 `infra/utils/` 目录下代码必须保持业务无关性，不 import `modules/` 或 `web/`
- 路由业务逻辑应剥离到 `modules/`，路由函数主体 ≤ 10 行
- 仓储返回 dataclass/Pydantic 模型，不直接返回 ORM 对象
- 跨层访问私有属性（`_` 前缀）应通过公共方法封装

### 禁止
- 在 `domain/` 中执行数据库查询
- 在 `infra/` 中实现业务状态机
- 路由函数直接调用 `session.execute()` 或 `session.commit()`

## Grep 扫描命令

```bash
# 层依赖方向违规检测
grep -rn "from xianyu_hunter\.infra import" src/xianyu_hunter/domain/ --include="*.py"
grep -rn "from xianyu_hunter\.modules import" src/xianyu_hunter/domain/ --include="*.py"
grep -rn "from xianyu_hunter\.web import" src/xianyu_hunter/domain/ --include="*.py"
grep -rn "from xianyu_hunter\.web import" src/xianyu_hunter/infra/ --include="*.py"
grep -rn "from xianyu_hunter\.web import" src/xianyu_hunter/modules/ --include="*.py"

# 公共工具库业务无关性
grep -rn "from xianyu_hunter\.modules\." src/xianyu_hunter/infra/utils/ --include="*.py"
grep -rn "from xianyu_hunter\.web\." src/xianyu_hunter/infra/utils/ --include="*.py"

# 路由层业务逻辑剥离
grep -rn "session\.execute" src/xianyu_hunter/web/routes/ --include="*.py"
grep -rn "session\.commit" src/xianyu_hunter/web/routes/ --include="*.py"

# 业务逻辑绕过仓储
grep -rn "session\.execute(select(" src/xianyu_hunter/modules/ --include="*.py"
grep -rn "session\.execute(update(" src/xianyu_hunter/modules/ --include="*.py"
```

## 判断标准
- `domain/` 中出现 infra/web 的 import → P0 阻塞
- `infra/` 中出现 modules/web 的 import → P1 严重
- `modules/` 中出现 web 的 import → P1 严重
- 路由函数 > 10 行且含业务逻辑 → P1 严重
- `infra/utils/` import modules → P1 严重

## 适用/不适用场景
- **适用**：所有 `src/xianyu_hunter/` 下的 Python 文件；架构变更或新模块创建时
- **不适用**：`tests/` 目录；`container.py`（依赖注入容器可依赖各层）；一次性脚本
