---
name: xianyu-hunter-dev
description: "闲鱼猎人项目（XianyuHunter）增量开发与 Bug 修复技能。覆盖项目内 Python 后端（FastAPI + SQLAlchemy + asyncio）、React 前端（TypeScript + Vite + Ant Design + Zustand）、YAML 配置层等多模块协同开发。Use when (1) 在 `d:\code\otherProjects\17_xianyu` 项目内进行任何增量功能开发、Bug 修复、重构、迁移；(2) 需要理解项目分层架构（domain / infra / modules / web）后开始工作；(3) 需要查询项目编码规范、目录结构、关键约定；(4) 涉及配置加载链（config.yaml + eval.yaml + .env）的修改。"
---

# xianyu-hunter-dev

> **项目**：XianyuHunter（闲鱼猎人）
> **技术栈**：Python 3.11 + FastAPI + SQLAlchemy 2.0(async) + Playwright / React 18 + TypeScript + Vite + Ant Design 5 + Zustand / Pydantic v2
> **核心特点**：基于 YAML 的运行时可热更配置 + 实时从 `get_config()` 读取的抢单决策链
> **本技能定位**：项目级编码规范入口 + 增量开发工作流

---

## When to use this skill

- ✅ 在项目内**新增模块 / 页面 / API 端点 / 配置项**
- ✅ 修复配置持久化、参数重置、保存失败类 Bug
- ✅ 涉及前后端**联动**的修改（如 UI 改字段 + 后端 schema 同步）
- ✅ 重构（提取工具函数、统一错误处理、合并相似页面）
- ❌ 不适用于：纯文档撰写、需求评审、UI 视觉设计（非编码）

---

## How to use this skill

按以下顺序展开工作。每步对应下文的"固定流程"或"判断逻辑"小节：

1. **【必读】查阅 §1 固定工作流**（读 → 查 → 改 → 验）—— 5 分钟防踩坑
2. **【必读】查阅 §2 核心编码规范** —— 项目级铁律
3. **【场景】按需查阅 references/ 下专题**：
   - `references/coding-standards.md` —— 统一编码规范（Python + TS）
   - `references/yaml-config-patterns.md` —— YAML 配置加载/合并的踩坑记录
   - `references/error-handling.md` —— 前后端错误处理统一规范
   - `references/frontend-state-and-api.md` —— Zustand + Axios + Ant Design 联动
4. **【场景】按需查阅 `docs/standards/`**：
   - `directory-structure.md` —— 文件放哪里
   - `michelin-design-system.md` —— 视觉规范
5. **【场景】跨模块改动**配套使用 `xianyu-frontend-code-review` / `xianyu-backend-code-review`

---

## §1 固定工作流（5 步法）

> **复盘来源**：从"抢单策略页面参数重置 Bug" + "保存预览失败"两个问题中提炼。

### Step 1: 读（Read）

- 用 `Read` 工具读**所有相关文件**，包括调用链上下游
- 不要只看报错文件，**读完整调用链**：UI → Store → API → 路由 → Service → 配置加载
- 后端 YAML 合并类问题：必须同时读 `config/*.yaml` 全部文件

### Step 2: 查（Check）

- 检查**项目级硬编码约定**（目录、命名、加载顺序）
- 检查**类似场景的现有实现**（其他页面怎么处理同类问题）
- 在 `docs/standards/` + `docs/skills/` 搜关键词
- **不要**默默选择一种解释就开始编码，**不确定时询问**

### Step 3: 改（Edit）

- **精确编辑**：只改必要部分，**不顺手改旁边代码**
- **最小修改原则**：避免引入额外抽象、配置项、错误处理
- 注释优先解释**为什么**，而不是**做什么**
- 修改后立即在文件内自检语法

### Step 4: 验（Verify）

- 跑相关测试：`pytest tests/test_<相关模块>.py -v`
- 端到端验证：
  - 后端改动 → 用 Python 脚本调 API 模拟完整流程（GET → 改 → POST dry_run → POST save）
  - 前端改动 → 重启 Vite HMR + 浏览器实测保存/刷新流程
- **严禁**只"看起来改对了"就声称完成

### Step 5: 报（Report）

- 给出**根因**（不是表象）+ **修复点**（文件:行）+ **验证结果**（实际测试输出）
- 如有破坏性变更 → 在"阶段交接声明"中明确标出

---

## §2 核心编码规范（速查）

> 完整版见 [references/coding-standards.md](references/coding-standards.md)。本节只列"必须遵守"的铁律。

### 2.1 后端 Python

| 铁律 | 错误示例 | 正确做法 |
|---|---|---|
| **不要默默选择解释** | 看到 bug 直接选一种修 | 先列 2-3 种可能根因，逐个验证 |
| **最小修改原则** | 顺手重构相邻代码 | 只改 bug 相关行 |
| **路径必须用 `Path()`** | `open("data/x.db")` 阻塞 | `Path("data/x.db")` + 异步上下文 |
| **YAML 合并必须深度合并** | `data.update(yaml.load(f))` | 递归 `_deep_merge_yaml` |
| **配置加载顺序** | 先主后子 → 子覆盖主 | **先子后主** + 深度合并，主配置最后覆盖 |
| **敏感字段 redact** | 直接返回带 cookie 的配置 | `_REDACT_KEYS` 列表 + 递归脱敏 |
| **错误用 Pydantic 校验** | `if x > 100: raise` | `@field_validator` / `@model_validator` |
| **注释解释 why** | `# 加载配置` | `# 颠倒加载顺序：避免 eval.yaml 整体覆盖 config.yaml` |

### 2.2 前端 React/TypeScript

| 铁律 | 错误示例 | 正确做法 |
|---|---|---|
| **错误信息必须可读** | `catch { message.error('预览失败') }` | `catch (e) { message.error(extractApiError(e)) }` |
| **共享工具提取到 utils/** | 每个页面写一遍错误解析 | 统一 `utils/apiError.ts` |
| **Zustand 状态不存整个配置** | `store.config = wholeCfg` | 拆分到独立 selector，按需订阅 |
| **API 路径常量** | `'/api/config/save'` 散落 | `api/config.ts` 集中管理 |
| **TS 严格模式** | `any` 类型滥用 | 用 `Record<string, unknown>` 替代 any |
| **空 catch 是反模式** | `catch {}` | 必须处理或 rethrow |
| **后端字段名要一致** | 前端 `autoBuyScore` 后端 `auto_buy_score` | 严格 snake_case 透传 |
| **新增页面三同步** | 只加组件不加路由/菜单 | 路由表+菜单项+页面组件必须同步添加 |
| **Menu onClick 路径守卫** | `onClick={({ key }) => navigate(key)}` | `if (key.startsWith('/')) navigate(key)`，过滤 SubMenu 父项 |
| **Modal 动态状态用 update** | `querySelector` 操作 DOM 改按钮 | `modal.update()` 动态更新 okButtonProps |
| **Edit 后 Read 验证** | 信任工具返回的"updated" | 关键修改后 Read 确认文件实际内容 |

### 2.3 配置（YAML + .env）

- **config/config.yaml** = 用户运行时可改的配置
- **config/eval.yaml** = 评估规则基线（含 thresholds / weights）
- **config/*.example.yaml** = 部署模板（**必须**随新字段一起提交）
- **.env** = 敏感凭据（cookie / API key），**禁止**写入 YAML
- **新增字段流程**：
  1. 在 `Pydantic AppConfig` 加字段 + 默认值
  2. 在 `config/*.example.yaml` 加注释示例
  3. 在前端 `api/types.ts` 加对应类型
  4. UI 控件可编辑该字段

### 2.4 错误处理（统一规范）

**后端**（FastAPI）：
```python
raise HTTPException(
    status_code=400,
    detail={"message": "配置校验失败，未保存", "errors": err.errors()}
)
```

**前端**（React + Ant Design）：
```typescript
import { extractApiError } from '@/utils/apiError'

try {
  await configApi.save(payload)
} catch (e) {
  message.error(extractApiError(e), 5)  // 5 秒持续时间
}
```

完整规范见 [references/error-handling.md](references/error-handling.md)。

---

## §3 项目结构速查

| 路径 | 用途 | 详细规范 |
|---|---|---|
| `src/xianyu_hunter/domain/` | 纯数据类，无副作用 | [standards/directory-structure.md](../../standards/directory-structure.md) |
| `src/xianyu_hunter/infra/` | 基础设施：DB / 浏览器 / 配置 / 仓储 | `repo_*.py` 命名 |
| `src/xianyu_hunter/modules/` | 业务模块：collector / buyer / evaluator | `snake_case.py` |
| `src/xianyu_hunter/web/routes/` | FastAPI 路由 | `api_*.py` |
| `src/xianyu_hunter/web/templates/` | 旧版 Jinja2 模板 | 仅维护，新页面走 React |
| `src/xianyu_hunter/web/static/spa/` | 前端构建产物（gitignore） | Vite 构建输出 |
| `frontend/src/api/` | 前端 API 客户端 + 类型 | `client.ts` + `config.ts` + `types.ts` |
| `frontend/src/stores/` | Zustand 状态 | 按业务模块切分 |
| `frontend/src/pages/Config/` | 配置管理页面 | BuyerStrategy / EvalRules / PriceStrategy 等 |
| `frontend/src/utils/` | 共享工具 | `apiError.ts` / `storage.ts` 等 |
| `config/` | YAML 配置 + 模板 | `*.yaml` 提交，`*.example.yaml` 模板 |
| `docs/standards/` | 项目规范 | 目录、设计系统、编码规范 |
| `docs/skills/` | 自定义技能仓库 | 本目录 |

---

## §4 关键约定（不踩坑）

### 4.1 抢单决策链

- **buyer.py → evaluator.py → worker.py** 是核心调用链
- 配置变更后**无需重启**：每次决策实时从 `get_config()` 读取
- 修复配置类 Bug 时必须验证：**保存 → 刷新 → 检查值仍正确**（不止看 API 返回）

### 4.2 配置加载的踩坑顺序

| 旧顺序（Bug） | 新顺序（修复） |
|---|---|
| 1. `config.yaml`（先） | 1. `eval.yaml`（默认基线） |
| 2. `eval.yaml`（后，整体覆盖） | 2. `notifier.yaml` / `browser.yaml` |
| | 3. `config.yaml`（最后，深度合并覆盖） |

**为什么颠倒**：之前 `data.update()` 浅合并，eval.yaml 顶层覆盖了用户在 config.yaml 修改的 eval 子字段。修复后**深度合并**让同名字段细分 key 也被正确覆盖。

### 4.3 前端错误处理三大铁律

1. ❌ 禁止 `catch { message.error('保存失败') }` 等笼统提示
2. ✅ 必须用 `extractApiError(e)` 提取后端 `detail.message` + `detail.errors`
3. ✅ message 持续时间 ≥ 3 秒（`message.error(msg, 5)`），错误信息允许长字符串换行

### 4.4 命名一致性

| 层 | 命名 | 示例 |
|---|---|---|
| YAML | `snake_case` | `auto_buy_score` |
| Pydantic | `snake_case` (Python) | `auto_buy_score: int` |
| 前端 TS | 透传 `snake_case` | `config.eval.auto_buy_score` |
| 数据库列 | `snake_case` | `auto_buy_score INTEGER` |
| 路由 | `kebab-case` (URL) | `/api/config/save` |

**禁止**在中间任何一层做大小写转换（如 `autoBuyScore`），避免后端校验通过但前端字段对不上。

### 4.5 数据库维护约定

| 约定 | 说明 |
|---|---|
| **白名单表** | 仅 `ALLOWED_TABLES` 列出的业务表可管理，禁止操作系统表 |
| **参数化 SQL** | 值用 `:param` 绑定，标识符（表名/列名）用白名单校验 `_IDENT_RE` |
| **二次确认 token** | 删除/批量删除/导入必须传 `confirm_token=CONFIRM_DELETE` |
| **级联策略** | `TABLE_RELATIONS` 定义关联关系，`cascade` 级联删除 / `set_null` 置空外键 |
| **级联预览** | 删除前调 `/cascade-preview` 让用户看到影响范围 |
| **事务原子性** | 级联操作与主表删除在同一 `engine.begin()` 事务中 |
| **字段语义标注** | `COLUMN_LABELS` 为每个字段提供中文业务含义标注 |
| **审计日志** | 所有 DML 写入 `events` 表（type=`db_admin.*`），可在审计日志抽屉查看 |
| **SQLite 类型兼容** | `text()` 查询 datetime 列返回字符串，序列化前需 `hasattr(obj, 'isoformat')` 兼容 |

---

## §5 与其他技能的关系

```
xianyu-hunter-dev（本技能）
    │
    ├── 编码规范 ──→ references/coding-standards.md
    │
    ├── 涉及前端代码 ──→ xianyu-frontend-code-review
    │                     ├── 代码质量
    │                     ├── 性能（React.memo / useMemo）
    │                     └── 业务逻辑正确性
    │
    ├── 涉及后端代码 ──→ xianyu-backend-code-review
    │                     ├── 分层架构（domain / infra / modules / web）
    │                     ├── 异步并发（asyncio）
    │                     ├── SQLAlchemy 用法
    │                     └── 安全 / 性能 / 可维护性
    │
    ├── 日志/性能问题 ──→ xianyu-logs-review
    │
    ├── 数据库维护模块 ──→ references/database-admin.md
    │
    └── 启动/部署/重启 ──→ xianyu-automation-startserver
```

---

## §6 阶段交接声明模板

完成任务后，使用以下格式声明（参考 user_rules 约定）：

```markdown
## 阶段交接声明
- 当前阶段：[阶段名称] ✅ 已完成
- 下一阶段：[阶段名称]
- 下一阶段智能体：[智能体名称]
- 下一阶段技能：[技能名称]
- 交接上下文：[传递给下一阶段的关键信息摘要]
```

---

## References

- [references/coding-standards.md](references/coding-standards.md) —— 统一编码规范（Python + TS）
- [references/yaml-config-patterns.md](references/yaml-config-patterns.md) —— YAML 配置加载踩坑模式
- [references/error-handling.md](references/error-handling.md) —— 前后端错误处理统一规范
- [references/frontend-state-and-api.md](references/frontend-state-and-api.md) —— Zustand + Axios 联动
- [references/database-admin.md](references/database-admin.md) —— 数据库维护模块专项规范

## 外部规范

- [docs/standards/directory-structure.md](../../standards/directory-structure.md) —— 目录结构
- [docs/standards/michelin-design-system.md](../../standards/michelin-design-system.md) —— UI 视觉规范
- [docs/standards/coding-standards.md](../../standards/coding-standards.md) —— 完整编码规范（总入口）
