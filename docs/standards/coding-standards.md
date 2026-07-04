# XianyuHunter 编码规范（总入口）

> **版本**：v1.0
> **日期**：2026-07-04
> **维护者**：xianyu-hunter-dev 技能
> **适用范围**：`src/xianyu_hunter/`（Python）+ `frontend/src/`（TypeScript）
> **配套技能**：
> - `xianyu-hunter-dev`（增量开发）
> - `xianyu-frontend-code-review`（前端代码审查）
> - `xianyu-backend-code-review`（后端代码审查）

---

## 一、规范层级

| 层级 | 文档 | 何时查阅 |
|---|---|---|
| **总入口（本文档）** | `standards/coding-standards.md` | 任何编码前必读 |
| **通用规范** | `docs/skills/xianyu-hunter-dev/references/coding-standards.md` | 详细规则 |
| **专题** | `docs/skills/xianyu-hunter-dev/references/{yaml,error,frontend-state}.md` | 涉及专题时 |
| **目录结构** | `standards/directory-structure.md` | 添加新文件时 |
| **设计系统** | `standards/michelin-design-system.md` | UI 视觉调整时 |
| **审查清单** | `docs/skills/xianyu-{frontend,backend}-code-review/references/*.md` | 提交前自查 |

---

## 二、铁律（违反即不通过 Code Review）

### 2.1 通用铁律

| # | 铁律 | 错误示例 | 正确做法 |
|---|---|---|---|
| 1 | **编程前先思考** | 默默选择一种解释直接开始 | 不确定时 `AskUserQuestion` |
| 2 | **最小修改原则** | 顺手重构相邻代码 | 只改 bug 相关行 |
| 3 | **注释解释 why** | `# 加载配置` | `# 颠倒顺序避免覆盖` |
| 4 | **验证先于断言** | 只看"看起来对"就声称完成 | 必须有测试输出或实测截图 |
| 5 | **目标驱动** | 模糊指令默默展开 | 化为可验证目标 |

### 2.2 后端铁律

| # | 铁律 | 错误示例 | 正确做法 |
|---|---|---|---|
| B1 | **YAML 深度合并** | `data.update(yaml.load(f))` | `_deep_merge_yaml` |
| B2 | **配置加载顺序** | 主配置先 + 子配置后（覆盖） | **子配置先 + 主配置后** |
| B3 | **敏感字段 redact** | `return config.model_dump()` | `_redact(cfg)` |
| B4 | **错误用 Pydantic 校验** | `if x > 100: raise` | `@model_validator` |
| B5 | **路由不写业务** | 路由函数 50+ 行 | 路由 ≤ 10 行，业务在 modules |
| B6 | **仓储返回 DTO** | `return orm` | `return ItemDTO.model_validate(orm)` |
| B7 | **async 不阻塞** | `requests.get` 在 async 中 | `aiohttp` |
| B8 | **参数化 SQL** | `text(f"WHERE x = '{x}'")` | ORM / `text(..., :param)` |
| B9 | **统计查询对齐写入端** | 查询 `status in ('paid','confirmed')` 但写入端从未写入这两个值 | 新增统计查询前搜索所有写入位置，确认取值一致 |
| B10 | **分子分母口径一致** | 分子查 notify 事件，分母用全量事件数 | 分母统计范围必须与分子同类 |
| B11 | **数据采集闭环** | 统计查询依赖某表数据，但该表无写入代码 | 数据产生点必须写入对应记录 |
| B12 | **构造函数测试兼容** | 新增 `_repo` 属性，测试用 `__new__` 跳过构造导致 AttributeError | 新增属性用 `getattr(self, '_x', None)` 兼容 |
| B13 | **统计异常告警** | 分母为 0 时静默返回 0% | 分母为 0 时记录 WARNING 含原因提示 |

### 2.3 前端铁律

| # | 铁律 | 错误示例 | 正确做法 |
|---|---|---|---|
| F1 | **错误信息可读** | `catch { message.error('保存失败') }` | `catch (e) { message.error(extractApiError(e), 5) }` |
| F2 | **不订阅整个 store** | `const store = useStore()` | `const v = useStore(s => s.v)` |
| F3 | **snake_case 透传** | 前端转 camelCase | 严格 snake_case |
| F4 | **API 路径集中** | `fetch('/api/x')` 散落 | `api/x.ts` 模块化 |
| F5 | **禁止 `any`** | `e: any` | `Record<string, unknown>` / 泛型 |
| F6 | **空 catch 是反模式** | `catch {}` | 至少 message 提示或 rethrow |
| F7 | **保存后 reload** | 保存成功不刷 store | `await confirmSave()` 后 `loadConfig()` |
| F8 | **失败提示 ≥ 5 秒** | `message.error('失败')` 默认 3 秒 | `message.error(msg, 5)` |

### 2.4 配置铁律

| # | 铁律 | 说明 |
|---|---|---|
| C1 | **保存端与加载端合并逻辑一致** | 否则"保存成功但下次加载值不同" |
| C2 | **保存后 reload_config()** | 否则 lru_cache 仍返回旧值 |
| C3 | **新增字段同步 example.yaml** | 部署模板要更新 |
| C4 | **凭据走 .env / keyring** | 不写 YAML |
| C5 | **YAML 时间字符串加引号** | `start: "07:00"` |
| C6 | **业务约束用 `@model_validator`** | `pass_score <= auto_buy_score` |

---

## 三、复盘：从历史 Bug 提炼的模式

### 3.1 模式 1：YAML 浅合并导致参数重置

**Bug 现象**：
> 抢单策略页面修改 `auto_buy_score` → 保存成功 → 刷新后值回到默认

**根因**：`data.update(yaml)` 浅合并 + 子配置后加载整体覆盖主配置

**修复**：
- 颠倒加载顺序（子配置先）
- 改用深度合并

**预防**：
- 审查时必查 `dict.update(yaml_data)`
- 加载端 / 保存端都用深度合并
- 加回归测试 `test_main_config_overrides_eval_yaml`

详见 [`yaml-config-patterns.md`](../skills/xianyu-hunter-dev/references/yaml-config-patterns.md)

### 3.2 模式 2：catch 块笼统提示

**Bug 现象**：
> 抢单策略保存失败显示"预览失败"，用户不知道哪里错

**根因**：`catch { message.error('保存失败') }` 丢弃所有错误细节

**修复**：
- 提取 `extractApiError(e)` 工具
- 显示后端 `detail.message` + `detail.errors`
- 失败提示持续 5 秒

**预防**：
- 所有 catch 块必须用 `extractApiError`
- 审查时检查每个 catch 块

详见 [`error-handling.md`](../skills/xianyu-hunter-dev/references/error-handling.md)

### 3.3 模式 3：保存成功不 reload

**Bug 现象**：
> 保存 API 返回成功，但前端 store 还是旧值

**根因**：保存后没调用 `loadConfig()` 重新加载

**修复**：`await confirmSave()` 内部调用 `await loadConfig()`

**预防**：
- 审查保存流程：必须 reload 或乐观更新
- 检查 store action：异步 save 后是否 invalidate cache

详见 [`frontend-state-and-api.md`](../skills/xianyu-hunter-dev/references/frontend-state-and-api.md)

### 3.4 模式 4：async 中调用阻塞 I/O

**风险**：阻塞 event loop，整个 Web 服务卡顿

**预防**：
- 审查时查 `requests` / `time.sleep` / `open` 在 async 中
- 用 `aiohttp` / `httpx` / `aiofiles`

详见 [`async-and-concurrency.md`](../skills/xianyu-backend-code-review/references/async-and-concurrency.md)

### 3.5 模式 5：N+1 查询

**风险**：1000 个订单 = 1001 次查询

**预防**：
- `selectinload` / `joinedload` 预加载
- `IN (...)` 批量查
- 数据库聚合代替 Python 聚合

详见 [`sqlalchemy.md`](../skills/xianyu-backend-code-review/references/sqlalchemy.md)

### 3.6 模式 6：统计查询与写入端取值不对齐

**Bug 现象**：
> 仪表盘"抢单成功率"始终显示 0%，实际已有成功订单

**根因**：`business_kpi.py` 查询 `OrderRow.status in ('paid','confirmed')`，但生产代码实际写入的是 `'pending_pay'`（已拍下）和 `'succeeded'`（确认支付）。`'paid'` 和 `'confirmed'` 在整个代码库中从未被写入 orders 表。

**修复**：
- 查询条件改为 `OrderRow.status == 'succeeded'`，与 `stats_overview.py` 统计口径一致
- 新增统计查询前必须搜索所有写入位置，确认取值一致

**预防**：
- 审查统计查询时，反向追溯写入端实际取值
- 枚举值不硬编码在查询中，应引用 `OrderStatus` 等枚举类
- 加回归测试覆盖"有数据时查询能命中"场景

### 3.7 模式 7：数据采集环节缺失

**Bug 现象**：
> 仪表盘"推送失败率"始终显示 0%，实际推送有成功有失败

**根因**：`business_kpi.py` 查询 `EventRow.stage like '%notify%'`，但 `NotifierHub.send()` 推送时从不写入 EventRow，只写 `logger.info` 日志。查询永远命中 0 行。

**修复**：
- 在 `NotifierHub.send()` 末尾写入 EventRow：`stage='notify'`，`level='info'/'err'`
- 静默（quiet hours）和未配置渠道场景不写入，避免污染统计
- 分母改为单独查询 `stage like '%notify%'` 的事件总数，与分子口径一致

**预防**：
- 新增统计指标时，必须确认数据源有写入代码
- 数据产生点（推送/抢单/评估）必须写入对应的 EventRow/OrderRow
- 统计字段（stage/level/status）取值全代码库统一
- 分母为 0 时记录 WARNING 日志含原因提示

详见 [`coding-standards.md`](../skills/xianyu-hunter-dev/references/coding-standards.md) §2.10 统计查询规范

---

## 四、命名一致性（铁律）

**所有层 snake_case 透传，禁止大小写转换**：

| 层 | 字段名 |
|---|---|
| YAML | `auto_buy_score` |
| Pydantic | `auto_buy_score: int` |
| TS 接口 | `auto_buy_score: number` |
| React prop | `auto_buy_score` |
| HTTP body | `auto_buy_score` |
| DB 列 | `auto_buy_score` |
| URL 路径 | `/api/auto-buy` (kebab-case) |

---

## 五、目录速查

| 路径 | 用途 |
|---|---|
| `src/xianyu_hunter/domain/` | 纯数据模型 |
| `src/xianyu_hunter/infra/` | 基础设施 |
| `src/xianyu_hunter/modules/` | 业务模块 |
| `src/xianyu_hunter/web/routes/` | FastAPI 路由 |
| `frontend/src/api/` | API 客户端 |
| `frontend/src/stores/` | Zustand 状态 |
| `frontend/src/pages/Config/` | 配置管理页面 |
| `frontend/src/utils/` | 共享工具 |
| `config/` | YAML 配置 |
| `tests/` | 测试代码 |
| `docs/skills/` | 自定义技能仓库 |

完整规范见 [directory-structure.md](./directory-structure.md)

---

## 六、Code Review 触发时机

| 改动类型 | 触发技能 |
|---|---|
| Python 文件 | `xianyu-backend-code-review` |
| TypeScript 文件 | `xianyu-frontend-code-review` |
| YAML / 配置 | `xianyu-hunter-dev`（用 yaml-config-patterns） |
| 数据库迁移 | `xianyu-backend-code-review`（用 sqlalchemy.md） |
| 跨模块联动 | 两个 review 技能都跑 |

---

## 七、提交前自检清单

- [ ] 阅读了相关代码（不只是修改的）
- [ ] 跑过相关测试
- [ ] 端到端验证（不只是 API 返回）
- [ ] 没引入 hardcode（路径 / 凭据 / 阈值）
- [ ] 命名与后端一致（snake_case）
- [ ] catch 块用 `extractApiError`
- [ ] 注释解释 why
- [ ] 没顺手改无关代码
- [ ] 加了回归测试
- [ ] `git status` 无游离文件

---

## 八、复盘流程

每次修复 Bug 后，按以下流程复盘并更新规范：

```
1. 根因分析
   ↓
2. 提炼可抽象模式
   ↓
3. 写回归测试
   ↓
4. 更新规范文档
   ↓
5. 更新审查技能检查项
   ↓
6. Code Review 模板更新
```

---

## 九、参考

### 内部文档
- [directory-structure.md](./directory-structure.md) —— 目录结构规范
- [michelin-design-system.md](./michelin-design-system.md) —— UI 视觉规范
- [deployment.md](./deployment.md) —— 部署指南

### 技能仓库
- [xianyu-hunter-dev](../skills/xianyu-hunter-dev/SKILL.md) —— 增量开发技能
- [xianyu-frontend-code-review](../skills/xianyu-frontend-code-review/SKILL.md) —— 前端代码审查
- [xianyu-backend-code-review](../skills/xianyu-backend-code-review/SKILL.md) —— 后端代码审查

### 外部参考
- [PEP 8](https://peps.python.org/pep-0008/)
- [TypeScript 官方手册](https://www.typescriptlang.org/docs/handbook/intro.html)
- [React 最佳实践](https://react.dev/learn)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Clean Code](https://www.oreilly.com/library/view/clean-code-a/9780136083238/)
