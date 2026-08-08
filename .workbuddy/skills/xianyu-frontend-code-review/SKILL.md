---
name: "xianyu-frontend-code-review"
description: "闲鱼猎人前端代码（frontend/src/ React/TypeScript/Ant Design/Zustand .tsx/.ts）全面评审，覆盖 36 维度。当用户要求审查/走查/评估前端代码时触发。纯后端 .py 文件改用 xianyu-backend-code-review。"
version: "4.67.0"
updated: "2026-08-08"
config: "config.yaml"
scripts: "scripts/auto-scan.ps1"
template: "templates/report-template.md"
---

# 闲鱼猎人前端代码审查

对 `frontend/src/` 下 React/TypeScript/Ant Design/Zustand 文件进行代码评审。**所有审查维度的详细规则、示例、反例已拆分到 `references/dimensions/` 目录，按需读取。**

## 版本演进索引

> 完整版本复盘详情见 [references/version-changelog.md](references/version-changelog.md)

| 版本 | 新增检查点 | 维度 |
|------|-----------|------|
| v4.67.0 | F-REVIEW-244 | 41 SPA 子路径/域名模式部署前缀一致性（API_BASE 单一源/原始请求前缀/PWA 规则） |
| v4.63.0 | F-REVIEW-233~235 | 47 资源创建幂等性与前端状态闭环 |
| v4.62.0 | F-REVIEW-227~232 | 40 前端韧性 Review |
| v4.61.0 | F-REVIEW-220~226 | 重构安全性 7 项 |
| v4.60.0 | UI-PREVIEW-GATE / STATE-SELECTION / DEFENSIVE-RENDER / COMPONENT-REUSE-RESET | UI 变更门控/状态选型/防御性渲染/组件复用重置 |
| v2.0~v4.59 | F-REVIEW-001~219 | 1-39 历史版本详见 references/version-changelog.md |

## 配置驱动

**所有评审规则、硬约束、项目规范通过 `config.yaml` 管理。** 首次使用从同目录 `config.example.yaml` 复制。

| 配置类 | 职责 |
|--------|------|
| `scope` | 评审范围（include_paths / exclude_paths / file_extensions） |
| `priority` | 优先级排序（severity_order / category_order） |
| `hard_constraints` | 硬约束规则（name / pattern / message / severity / auto_fix） |
| `checklist` | 评审检查清单 28 大类开关 |
| `abstraction_thresholds` | 抽象建议阈值 |
| `report` | 报告配置 |
| `verify` | 验证配置 |
| `project_conventions` | 项目专属规范 |

## 审查模式

| 模式 | 扫描范围 | 触发 |
|------|---------|------|
| 快速自检 | 仅阻塞级 | `pwsh scripts/auto-scan.ps1` |
| 增量审查 | `git diff --name-only` 变更文件 | 粘贴变更文件列表 |
| 指定文件审查 | 用户明确列出的文件 | 用户指定路径 |
| 片段评审 | 用户粘贴代码片段 | 无文件路径时仅输出建议 |
| 全量审查 | `frontend/src/**/*.{tsx,ts,js}` | 默认 |

---

## 审查维度索引

审查时根据命中维度读取对应的 `references/dimensions/` 文件，按需加载。

| # | 维度 | 触发条件 | 文件 |
|---|------|---------|------|
| 1 | 目录结构 | 新增/移动目录 | references/dimensions/01-directory-structure.md |
| 2 | 命名规范 | 新增文件/组件/变量 | references/dimensions/02-naming-conventions.md |
| 3 | React 组件 | React .tsx 文件 | references/dimensions/03-react-component.md |
| 4 | TypeScript 严格 | .ts/.tsx 文件 | references/dimensions/04-typescript-strict.md |
| 5 | AntD 5 主题 | Ant Design 使用 | references/dimensions/05-antd-theme.md |
| 6 | Zustand 状态管理 | store 文件 | references/dimensions/06-zustand-state.md |
| 7 | API 调用 | fetch/axios 调用 | references/dimensions/07-api-calling.md |
| 8 | 路由懒加载 | 路由/页面文件 | references/dimensions/08-routing-lazy.md |
| 9 | SheetWorkspace | 多页签组件 | references/dimensions/09-sheet-workspace.md |
| 10 | Hooks 设计 | 自定义 Hook 文件 | references/dimensions/10-hooks-design.md |
| 11 | 类型安全 | 类型定义/types.ts | references/dimensions/11-type-safety.md |
| 12 | SonarQube 合规 | 全部文件 | references/dimensions/12-sonarqube.md |
| 13 | PWA 配置 | pwa/service-worker | references/dimensions/13-pwa-config.md |
| 14 | 三处映射同步 | UI/路由/状态联动 | references/dimensions/14-triple-mapping.md |
| 15 | SSE 重连 | EventSource/SSE | references/dimensions/15-sse-reconnect.md |
| 16 | 性能 | bundle/lazy/useMemo | references/dimensions/16-performance.md |
| 17 | 可访问性 | 交互元素/a11y | references/dimensions/17-accessibility.md |
| 18 | 闲鱼项目规范 | 任何前端文件 | references/dimensions/18-project-specific.md |
| 19 | 跨组件状态同步 | store/组件通信 | references/dimensions/19-cross-component-state.md |
| 20 | API 数据契约 | api/types.ts | references/dimensions/20-api-data-contract.md |
| 25 | 失败原因链前端同步 | 错误处理组件 | references/dimensions/25-error-chain-frontend.md |
| 27 | 业务关键字常量管理 | 业务文案/关键字 | references/dimensions/27-business-keywords.md |
| 28 | 多用户认证隔离 | stores/api/auth | references/dimensions/28-multi-user-isolation.md |
| 29 | 数据契约与时序 | 异步数据流 | references/dimensions/29-data-contract-timing.md |
| 30 | 状态恢复前置校验 | 状态初始化 | references/dimensions/30-state-recovery-precheck.md |
| 34 | 规范治理 | meta-rules #36-37 | references/dimensions/34-standards-governance.md |
| 35 | 跨层契约与测试同步 | meta-rules #43-47 | references/dimensions/35-cross-layer-contract.md |
| 36 | 调度器运行时治理 | scheduler 前端 | references/dimensions/36-scheduler-runtime.md |
| 41 | 子路径/域名模式部署前缀一致性 | SPA 子路径部署、fetch/EventSource 前缀、导航链接、PWA 规则 | references/dimensions/41-subpath-deployment.md |

额外维度（37-49）详见 [references/version-changelog.md](references/version-changelog.md) 的复盘索引。

---

## 快速自检

**先执行此步骤进行快速自检：**

1. TypeScript 编译：`tsc --noEmit` 无错误
2. ESLint：`eslint frontend/src --max-warnings 0` 无警告
3. 硬约束：所有前端文件 contain `credentials: 'include'` / `withCredentials: true`
4. 类型安全：`grep -rn "as any" frontend/src/ --include="*.tsx" --include="*.ts"` 返回 0
5. 最低平台兼容性：Node.js >= `project_conventions.min_node_version`、浏览器 >= `browser_targets`
6. Key sparseness：index 文件符合 `checklist.key_sparseness` 开关状态
7. Lazy route grouping：路由按页面粒度分组懒加载

## 审查流程（4 阶段流水线）

### 阶段 1：上下文加载

1. 加载 `config.yaml`（含 `coding_standards` 节点）
2. 识别任务类型（前端/后端/全栈）——前端任务加载 `frontend/src/` 文件；后端任务转 `xianyu-backend-code-review`
3. 加载对应 `coding-rules/` 主题文件（按需）
4. 确定评审范围：增量 (`git diff HEAD`) / 指定文件 / 片段 / 全量
5. 应用 `scope.include_paths` / `scope.exclude_paths` 过滤
6. 对每个文件：Read 完整内容 + Grep 关键依赖

### 阶段 2：分层扫描

按 `checklist` 配置的 28 大类逐层扫描，分为 7 个子阶段：

**2.1 常规规则匹配**：按审查维度索引逐项检查，读取对应 `references/dimensions/` 文件

**2.2 配置驱动检查**（v4.31）：业务关键字硬编码 → 事件类型前缀匹配 → 字段名大小写敏感 → 多用户上下文隔离 → 认证 cookie 处理 → coding_standards 节点驱动

**2.3 硬约束合规性**：遍历 `hard_constraints.rules` Grep 扫描 → 标记违规

**2.4 跨层影响评估**（v4.60）：前端 types.ts 变更 → 后端 Pydantic → DB 影响映射

**2.5 缓存守卫检查**（v4.60）：空结果不缓存 / TTL 非硬编码 / 守卫独立性

**2.6 UI 变更门控**（v4.60）：变更行数统计 → 门控阈值 → 豁免检测

**2.7 重构安全性**（v4.61）：常量配置化 5 步法 / Hooks 作用域契约 / 导入名变更 checklist 等 7 项（详见 references/refactoring-safety-checks.md）

### 阶段 3：优先级分类

| 等级 | 判定标准 |
|------|---------|
| P0 阻塞 | 硬约束违规（安全漏洞/数据丢失/崩溃/认证失效） |
| P1 严重 | 逻辑错误/性能问题/状态不一致/异常吞掉/stale closure |
| P2 改进 | 代码质量/可维护性/配置化/重复逻辑/类型注解缺失 |
| P3 微调 | 风格/注释/命名优化/魔法数字提取 |

### 阶段 4：结果呈现

按 [templates/report-template.md](templates/report-template.md) 模板输出结构化报告。

---

## 评审范围判断

- 增量：`git diff HEAD --name-only` + 过滤 `.tsx/.ts/.js`
- 指定文件：用户明确列出
- 片段：无文件路径仅输出建议
- **范围必须收紧**：不顺便审查旁边代码

## 失败恢复机制

1. 文件读取失败 → 记录跳过原因，继续
2. Grep 超时 → 缩小范围或跳过
3. 测试运行失败 → 输出错误，不阻止报告
4. 配置文件缺失 → 使用内置默认配置并提示创建 `config.yaml`
5. TypeScript 编译错误 → 记录但继续

## 审查判断标准

详细标准见 [references/judgment-criteria.md](references/judgment-criteria.md)。速查：
- P0 阻塞：硬约束违规
- P1 严重：逻辑/性能/一致性问题
- P2 改进：可维护性/配置化
- P3 微调：风格/注释/命名

## 安全注意事项

1. 报告中不含任何 token、密码等敏感信息
2. 检查 `dangerouslySetInnerHTML` 使用
3. 检查 token 是否避免写入 localStorage（优先 httpOnly cookie）
4. 检查所有 API 请求是否携带 credentials

## 与现有工具的关系

- **xianyu-hunter-dev**：开发技能，开发完成后用本技能审查
- **xianyu-backend-code-review**：前后端协同评审时配合使用
- **xianyu-sonarqube-mcp**：SonarQube 修复后的二次审查
- **systematic-debugging**：纯调试场景使用，不使用本技能

---

## 版本历史

- **v4.66.0** (2026-07-31)：文档结构重构，SKILL.md 精简为维度索引 + 流程骨架，36 维度详情拆分到 references/dimensions/ 按需加载
- v4.65.0：搜索 Hook 模式 (F-REVIEW-236~240) / UI 状态映射与外部链接安全 (F-REVIEW-241~243)
- v4.63.0：资源创建幂等性与前端状态闭环 (F-REVIEW-233~235)
- v4.62.0：前端韧性 Review (F-REVIEW-227~232)
- v4.61.0：重构安全性检查 7 项 (F-REVIEW-220~226)
