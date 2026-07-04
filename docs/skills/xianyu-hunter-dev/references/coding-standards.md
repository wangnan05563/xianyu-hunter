# XianyuHunter 统一编码规范

> **版本**：v1.0
> **日期**：2026-07-04
> **来源**：从多次 Bug 修复对话 + 项目实践提炼
> **适用范围**：`src/xianyu_hunter/`（Python）+ `frontend/src/`（TypeScript）
> **配套技能**：`xianyu-hunter-dev`（增量开发）、`xianyu-frontend-code-review`、`xianyu-backend-code-review`

---

## 一、通用原则（前后端通用）

| # | 原则 | 落地手段 |
|---|---|---|
| 1 | **编程前先思考** | 不确定时用 `AskUserQuestion` 询问，不要默默选择解释 |
| 2 | **简约至上** | 任何过度设计都一目了然，避免提前抽象 |
| 3 | **精确编辑** | 只修改必要的部分，不要顺便修改旁边代码 |
| 4 | **目标驱动** | 在开始前将模糊指令转化为可验证的目标 |
| 5 | **注释解释 why，不是 what** | `# 颠倒加载顺序：避免 eval.yaml 整体覆盖` 而不是 `# 加载配置` |
| 6 | **验证先于断言** | 任何"完成"声明前必须有测试输出或实测截图佐证 |

---

## 二、Python 后端规范

### 2.1 类型与数据结构

| 规则 | 说明 |
|---|---|
| **使用 Pydantic v2** | 配置 / API 请求 / 响应统一用 `BaseModel` |
| **避免 raw dict** | 业务层禁止传 `dict[str, Any]`，必须用模型 |
| **Optional 用 `X \| None`** | Python 3.10+ 风格，不用 `Optional[X]` |
| **枚举用 `StrEnum`** | 不要用 `Enum`（与 JSON 序列化更友好） |
| **路径用 `pathlib.Path`** | 不用 `os.path` |

### 2.2 异步与并发

| 规则 | 说明 |
|---|---|
| **I/O 必须 async** | `asyncio.sleep` / `await` / `aiohttp` |
| **禁止阻塞调用** | `requests.get` / `time.sleep` / `open(file).read()` 阻塞循环 |
| **并发任务用 `asyncio.gather`** | 不用裸 `for` 串行 await |
| **信号量限流** | 涉及外部 API 时用 `asyncio.Semaphore` 控制 QPS |

### 2.3 YAML / 配置加载（重要）

**铁律：深度合并 + 主配置最后加载**

```python
def _load_all() -> AppConfig:
    base = Path("config")
    data: dict[str, Any] = {}

    # 1) 先加载子配置（默认值基线）
    for name in ("eval.yaml", "notifier.yaml", "browser.yaml"):
        section_data = load_yaml(base / name)
        if section_data:
            _deep_merge_yaml(data, section_data)

    # 2) 主配置最后加载（用户修改覆盖子配置）
    main_data = load_yaml(base / "config.yaml")
    if main_data:
        _deep_merge_yaml(data, main_data)

    return AppConfig.model_validate(data)


def _deep_merge_yaml(target: dict, source: dict) -> None:
    """深度合并：source 的细分字段覆盖 target 同名字段。"""
    for k, v in source.items():
        if isinstance(v, dict) and isinstance(target.get(k), dict):
            _deep_merge_yaml(target[k], v)
        else:
            target[k] = v
```

**为什么这样**：浅合并 `data.update(eval_yaml)` 会让 eval.yaml 顶层整体覆盖 config.yaml，导致用户在 config.yaml 修改的 `eval.auto_buy_score` 丢失。

### 2.4 错误处理

| 场景 | 做法 |
|---|---|
| API 参数校验 | Pydantic `@field_validator` / `@model_validator` |
| 业务校验失败 | `raise HTTPException(400, detail={"message": "...", "errors": [...]})` |
| 文件 / 资源缺失 | `raise FileNotFoundError(f"配置文件缺失: {path}")` |
| 外部 API 失败 | 记录 loguru warning + 上抛（让上层决定重试） |
| 内部异常 | 通用 `except Exception` 必须有 `logger.exception` |

### 2.5 仓储层

- 命名 `repo_<实体>.py`（如 `repo_items.py`）
- 方法名 `list_xxx` / `get_xxx` / `upsert_xxx` / `delete_xxx`
- 禁止返回 ORM 对象，**必须**返回 dataclass / Pydantic 模型
- 复杂 SQL 放 `infra/`，不放业务模块

### 2.6 日志

- 用 `loguru.logger` 而不是 `logging`
- 业务关键路径：`logger.info("触发自动抢单 task_id={} score={}", task_id, score)`
- 异常：`logger.exception("抢购失败")`（自动带堆栈）
- WARNING：可恢复异常 / 降级 / 重试
- ERROR：需人工介入的失败

### 2.7 SQLite 原始 SQL 查询类型兼容

| 规则 | 说明 |
|---|---|
| **text() 查询 datetime 列返回字符串** | SQLAlchemy 的 `text()` 不走 ORM 类型转换，SQLite 驱动返回 str |
| **序列化前检查类型** | 用 `hasattr(obj, 'isoformat')` 区分 datetime 和字符串 |
| **json 列同理** | SQLite 的 JSON 列通过 text() 查询可能返回 str 而非 dict |

```python
# ✅ 正确：兼容 datetime 对象和字符串
"created_at": r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else str(r["created_at"]) if r["created_at"] else None,

# ❌ 错误：假设 text() 返回 datetime 对象
"created_at": r["created_at"].isoformat() if r["created_at"] else None,  # AttributeError!
```

**适用场景**：所有通过 `text()` 原始 SQL 查询 datetime / json 列的场景。
**不适用**：ORM 查询（`session.query(Model)` 自动类型转换）。

### 2.8 数据删除完整性

| 规则 | 说明 |
|---|---|
| **删除前检查关联** | 有外键引用的表删除前必须处理关联数据 |
| **定义级联策略** | `TABLE_RELATIONS` 字典：`cascade`（级联删除）/ `set_null`（置空外键） |
| **级联预览 API** | 提供只读预览接口，让用户确认影响范围 |
| **事务原子性** | 级联操作与主表删除在同一个 `engine.begin()` 事务中 |
| **审计日志** | 删除操作（含级联详情）写入 events 表 |

```python
# 级联策略定义示例
TABLE_RELATIONS = {
    "tasks": [
        {"table": "items", "fk": "task_id", "action": "cascade"},    # 删任务 → 级联删商品
        {"table": "orders", "fk": "task_id", "action": "cascade"},   # 删任务 → 级联删订单
    ],
    "sellers": [
        {"table": "items", "fk": "seller_id", "action": "set_null"}, # 删卖家 → 保留商品但断开引用
    ],
}
```

**设计原则**：
1. 核心实体（tasks/items）被删时级联删除所有依赖数据，避免孤立记录
2. 辅助实体（sellers）被删时用 `set_null`，保留关联数据的独立查看价值
3. 叶子表（events/notifications）无下游依赖，直接删除

### 2.9 数据库字段语义标注

| 规则 | 说明 |
|---|---|
| **每个字段必须有中文标注** | `COLUMN_LABELS` 字典提供业务含义+类型特征+使用场景+约束条件 |
| **标注内容规范** | 格式：`业务名称（数据类型特征，使用场景，约束说明）` |
| **前端三处展示** | 数据表表头 tooltip + 表结构抽屉 + 编辑表单 label |
| **标注来源为代码** | 与数据库 schema 紧耦合，放代码中比配置文件更合理 |

```python
COLUMN_LABELS = {
    "tasks": {
        "status": "任务状态（running=运行中/paused=已暂停/stopped=已停止/completed=已完成）",
        "cron": "Cron表达式（调度频率，默认*/1 * * * *即每分钟执行）",
    },
}
```

**前端展示规则**：
- 表头：取 `label.split('（')[0]` 显示中文简称，hover 显示完整标注
- 表结构：独立"中文标注"列
- 编辑表单：label 显示中文简称 + 类型标签，hover 显示完整标注

---

## 三、TypeScript 前端规范

### 3.1 类型系统

| 规则 | 说明 |
|---|---|
| **TS 严格模式开启** | `tsconfig.json` 启用 `strict: true` |
| **禁用 `any`** | 用 `Record<string, unknown>` 替代 |
| **API 响应必须有类型** | `api/types.ts` 集中定义，禁止页面内联 |
| **字段命名透传后端** | `snake_case` 直接传，不做大小写转换 |
| **可选字段用 `?`** | `field?: string` 而非 `field: string \| null` |

### 3.2 React 组件

| 规则 | 说明 |
|---|---|
| **函数组件 + Hooks** | 不用 class 组件 |
| **Props 接口命名 `XxxProps`** | `interface ButtonProps` |
| **避免大组件** | 超过 200 行拆子组件 |
| **状态就近** | 不在父组件存所有子组件状态 |
| **副作用 useEffect 最小化** | 优先用 `useMemo` / `useCallback` 替代 |
| **Key 稳定** | 列表 `key` 用业务 ID，不用 index |

### 3.3 Zustand 状态

- **按业务拆 store**：`configStore` / `taskStore` / `userStore`
- **Selector 订阅**：`useStore(s => s.field)` 而非 `useStore()`
- **Action 命名 `xxxSave` / `xxxUpdate`**：动词开头
- **不存整个大对象**：拆分到独立字段

```typescript
// ✅ 推荐
const autoBuyScore = useConfigStore(s => s.config.eval?.auto_buy_score)
const updateConfig = useConfigStore(s => s.updateConfig)

// ❌ 反例
const config = useConfigStore()  // 整个 store 订阅，任何字段变都重渲染
```

### 3.4 错误处理（重要）

**铁律：禁止空 catch 笼统提示**

```typescript
// ❌ 反例
try { await api.save() } catch { message.error('保存失败') }

// ✅ 正例
import { extractApiError } from '@/utils/apiError'

try {
  await api.save()
  message.success('保存成功')
} catch (e) {
  message.error(extractApiError(e), 5)
}
```

`extractApiError` 统一处理：
- 400 校验失败：`{detail: {message, errors: [...]}}` → 拼接展示
- 401：`"认证已过期，请重新登录"`
- 500：`"服务器内部错误，请稍后重试"`
- 网络失败：`e.message`

### 3.5 样式

- **用 Ant Design 5 组件**：Button / Form / Table / Modal
- **设计系统遵循米其林规范**：色彩 / 圆角 / 间距
- **避免 inline style**：用 CSS class / styled
- **暗 / 亮主题双适配**

### 3.6 新增页面三同步检查清单

| 检查项 | 文件 | 说明 |
|---|---|---|
| ① 路由表 | `App.tsx` | `<Route path="xxx" element={...} />` 必须添加 |
| ② 菜单项 | `MainLayout.tsx` | Menu items 中添加对应 key（以 `/` 开头的路径） |
| ③ 页面组件 | `pages/` | 创建对应页面组件 |
| ④ 构建验证 | 终端 | `tsc` + `vite build` 确认无报错 |

**常见遗漏**：只创建了组件和菜单，忘记添加路由 → 点击菜单跳转到 fallback 页面。

**验证方法**：点击菜单项后 URL 正确且页面内容正确显示，无 404 或重定向。

### 3.7 antd Modal 动态状态管理

| 规则 | 说明 |
|---|---|
| **禁止 DOM 操作** | `querySelector` 在 antd 5 Modal.confirm 中不可靠（DOM 结构不稳定） |
| **用 `modal.update()`** | 动态更新 Modal 的 `okButtonProps` / `title` / `content` |
| **初始状态设 `disabled: true`** | 防止用户未确认就点击 |

```typescript
// ✅ 正确：用 modal.update() 动态切换
const modal = Modal.confirm({
  okButtonProps: { danger: true, disabled: true },
  content: (
    <Input.Password onChange={(e) => {
      tokenValue = e.target.value
      modal.update((prev) => ({
        ...prev,
        okButtonProps: { danger: true, disabled: tokenValue !== CONFIRM_TOKEN },
      }))
    }} />
  ),
})

// ❌ 错误：用 querySelector 操作 DOM
setTimeout(() => {
  const okBtn = document.querySelector('.ant-btn-primary')
  if (okBtn) okBtn.removeAttribute('disabled')  // 不可靠！
}, 100)
```

### 3.8 antd Menu 防御性编程

| 规则 | 说明 |
|---|---|
| **onClick 校验路径 key** | SubMenu 父项的 key 不以 `/` 开头，navigate 会跳到非法 URL |
| **只对路径 key 调 navigate** | `if (key.startsWith('/')) navigate(key)` |

```typescript
// ✅ 正确：过滤非路径 key
<Menu
  onClick={({ key }) => {
    if (typeof key === 'string' && key.startsWith('/')) {
      navigate(key)
    }
  }}
/>

// ❌ 错误：所有 key 都 navigate
<Menu onClick={({ key }) => navigate(key)} />  // SubMenu key='sub-data' 也会触发
```

---

## 四、配置规范

### 4.1 文件职责

| 文件 | 职责 | 版本控制 |
|---|---|---|
| `config/config.yaml` | 用户可改运行时配置 | ✅ |
| `config/eval.yaml` | 评估规则基线 | ✅ |
| `config/*.example.yaml` | 部署模板 | ✅ |
| `.env` | 敏感凭据 | ❌ gitignore |
| `.env.example` | 环境变量示例 | ✅ |

### 4.2 新增配置字段流程

1. **Pydantic 模型加字段** + 默认值（`src/xianyu_hunter/infra/yaml_config.py`）
2. **example.yaml 加注释**：`# 含义 + 合法值范围 + 默认值`
3. **前端 types.ts 加类型**
4. **UI 控件接入**（如 `BuyerStrategy.tsx` 的 `<InputNumber>`）
5. **测试覆盖**：单元测试 + 手动 E2E

### 4.3 敏感字段

| 字段 | 处理 |
|---|---|
| `cookie` / `cookies` / `session_id` | 写入 .env 或 keyring |
| `serverchan_key` / `pushplus_token` / `bark_key` | 写入 .env |
| **API 返回前必须 redact** | 见 `api_config.py` `_REDACT_KEYS` |

---

## 五、命名规范速查

| 类别 | 规范 | 示例 |
|---|---|---|
| Python 文件 | `snake_case.py` | `buyer_config.py` |
| Python 测试 | `test_*.py` | `test_yaml_config.py` |
| Python 类 | `PascalCase` | `EvalConfig` |
| Python 函数 | `snake_case()` | `load_all_yaml()` |
| Python 常量 | `UPPER_SNAKE` | `_REDACT_KEYS` |
| TS 文件 | `camelCase.ts` / `PascalCase.tsx` | `configApi.ts` / `BuyerStrategy.tsx` |
| TS 接口 | `PascalCase` | `AppConfig` / `DiffChange` |
| TS 函数 | `camelCase` | `extractApiError()` |
| YAML 字段 | `snake_case` | `auto_buy_score` |
| URL 路径 | `kebab-case` | `/api/config/save` |
| 数据库表 | `snake_case` 复数 | `task_records` |
| 数据库列 | `snake_case` | `created_at` |
| 文档 | `kebab-case.md` | `coding-standards.md` |

---

## 六、测试规范

| 规则 | 说明 |
|---|---|
| **测试文件命名** | `test_<被测模块>.py` |
| **测试函数命名** | `test_<场景>_<期望>`（如 `test_pass_score_gt_auto_buy_score_should_fail`） |
| **隔离 cwd** | 用 `monkeypatch.chdir(tmp_path)` 避免污染真实配置 |
| **覆盖正常 + 边界 + 异常** | 三个用例 |
| **回归测试** | 修复 Bug 时必须添加对应回归测试 |
| **运行** | `pytest tests/<file>.py -v` |

---

## 七、提交规范

- **commit message**：`type(scope): description`（如 `fix(yaml-config): use deep merge to fix parameter reset bug`）
- **修改前先读**：`Read` 工具读取完整文件，不直接 Edit
- **不要混合多个修改**：Bug 修复和功能重构分开 commit
- **敏感文件**（.env / .db / browser-data）必须 gitignore

---

## 八、不做什么（Anti-Pattern）

- ❌ 默默选择一种解释就直接开始编码
- ❌ 顺手修改旁边代码
- ❌ 硬编码路径 / 凭据 / 阈值（必须走配置）
- ❌ 命名不一致（`auto_buy_score` vs `autoBuyScore`）
- ❌ 浅合并多层配置
- ❌ catch 块写空 / 笼统提示
- ❌ 前端订阅整个 Zustand store
- ❌ 跳过测试就声称完成
- ❌ 提交时附带临时调试文件

---

## 九、参考

- [directory-structure.md](../../standards/directory-structure.md) —— 文件该放哪
- [michelin-design-system.md](../../standards/michelin-design-system.md) —— UI 视觉
- [xianyu-frontend-code-review](../xianyu-frontend-code-review/SKILL.md) —— 前端审查要点
- [xianyu-backend-code-review](../xianyu-backend-code-review/SKILL.md) —— 后端审查要点
