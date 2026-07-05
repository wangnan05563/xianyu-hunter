# SonarQube 接入与优化过程四维度复盘

> **复盘对象**：`xianyu-sonarqube-mcp` 技能从硬编码版本到通用化分层架构的完整演进
> **复盘方法论**：四维度框架（成功步骤 / 不确定性与失败点 / 可抽象流程 / 适用与不适用边界），见 [`四维度复盘方法论.md`](./四维度复盘方法论.md)
> **本文不重复**：方法论本体、7 个工作流模板、SonarQube 规则详细说明、CHANGELOG 完整记录（均见对应源文档）

---

## 一、背景与适用范围

### 1.1 为什么需要这份复盘

`xianyu-sonarqube-mcp` 在两个月内经历了从"Xianyu 项目专用工具"到"通用代码质量闭环技能"的完整重构。这期间踩了 6+ 个非典型坑（API 参数单复数、Export-ModuleMember 误用、硬编码工具列表等），做了 4 个版本决策（配置分层、降级方案、跨平台、修复策略扩展）。

**本文不记录"做了什么"（CHANGELOG 已覆盖），只回答：**
1. 哪些动作是"重复 5 次以上都成功"的稳定模式？
2. 哪些坑是"换种形式又复发"的反复出现？
3. 接入 SonarQube 类工具的固定流程是否可以抽象为 SOP？
4. 这套 SOP 在什么场景下不适用？

### 1.2 适用读者

| 角色 | 关心什么 |
|---|---|
| 未来要重构 `xianyu-sonarqube-mcp` 的人 | 哪些坑不要重踩、哪些架构决策可保留 |
| 引入其他代码质量工具（CodeQL/Semgrep/Trivy）的团队 | 通用化分层、降级方案、修复策略扩展的思路 |
| 项目维护者 | v2.0 的 6 个文件如何支撑完整 SOP，未来扩展路径 |
| 临时使用者 | 直接看「维度 3」的 SOP 流程图，跳过历史 |

---

## 二、维度 1：成功执行任务的完整步骤

### 2.1 成功路径：6 个阶段，14 步动作

| 阶段 | 步骤 | 关键产出 | 复用建议 |
|---|---|---|---|
| **0. 触发与目标** | 1. 明确"为什么扫" | 修复目标文档（213 issues 修复报告） | 任何"扫+修"任务都必须先定目标 |
| **1. 服务就绪** | 2. 编写 `start-sonarqube.ps1` 跨平台启动脚本 | 自动检测端口 + 自动启动 + 健康检查 | **固化**：任何外部服务依赖都应"先看本地再启动" |
| | 3. 编写 `verify-connection.ps1` 连接验证 | 健康检查 + 环境变量检查 + MCP 工具探测 | **固化**：连接验证独立成脚本，避免"扫失败时不知道是配置还是服务问题" |
| **2. 扫描与分类** | 4. 编写 `invoke-api.ps1` API 抽象层 | 统一封装 7 个 HTTP API 端点 | **固化**：MCP 不稳定时一定有 HTTP 降级 |
| | 5. 编写 `framework_patterns.json` 多框架模式库 | FastAPI/React/Vue/Django/Spring/Express 6 框架 | **固化**：每个新框架必须先建模式库再扫 |
| | 6. 编写 `fix_strategies.json` 修复策略表 | 覆盖 30+ 高频规则（v1.0 仅 7 条） | **固化**：修复策略要"按规则"而非"按文件"配置 |
| **3. 业务硬约束** | 7. 拆分硬约束为通用（`core.json`）+ 业务（`business/xianyu.json`） | 14 条通用安全 + 8 条 Xianyu 业务 | **固化**：硬约束必须分层，否则其他项目无法复用 |
| **4. 修复执行** | 8. 编写 `subagent-task-template.md` 子代理任务模板 | 5 段式：上下文→规则→文件→验证→报告 | **固化**：子代理任务模板必须含"验证步骤" |
| | 9. 按文件分组启动子代理并行修复 | 4 个 BLOCKER + 168 MAJOR + 39 MINOR 全部修复 | **固化**：并行只跨文件，文件内串行（避免 Edit 冲突） |
| **5. 验证闭环** | 10. 重新扫描对比 issue 数 | 736 → 523（-28.9%） | **固化**：必须用同一套 API 参数重扫 |
| | 11. 运行项目测试 | pytest + npm test | **固化**：测试命令分模块配置（`verify.test_commands`） |
| | 12. 硬约束合规性检查 | core.json + business/*.json 双重扫描 | **固化**：硬约束是阻塞门禁，违规不通过 |
| **6. 文档化** | 13. 撰写 `sonar-fix-report.md` 详细修复报告 | 必读：含根因 + 修复方法 + 回归测试 | **固化**：报告必须含"修复前/后对比"与"未修复项说明" |
| | 14. 维护 `references/issue-classification.md` + `xianyu-rule-overrides.md` | 误报识别 → 豁免清单 → 修复策略 | **固化**：误报清单要分"豁免"和"不可豁免"两类 |

### 2.2 重复 5+ 次都成功的稳定模式

1. **"先验证服务、再执行任务"**：`start-sonarqube.ps1 -StatusOnly` 退出码 0/1 直接判定可执行性
2. **"API 抽象层 + 端点配置化"**：所有 SonarQube HTTP API 调用通过 `invoke-api.ps1` 的 `Invoke-SonarApi` 函数，端点路径从 `core_config.json` 的 `api_endpoints` 节点读取
3. **"配置文件分层"**：通用（core）+ 项目（project）+ 业务（business/xianyu）+ 修复（fix_strategies）+ 框架（framework_patterns）五层
4. **"修复策略表"**：以 `rule_id` 为键，`auto_fix/manual_review/skip` 为值，让子代理直接按表执行
5. **"误报清单分类管理"**：`xianyu-rule-overrides.md` 分"豁免清单"（按 FastAPI/React 模式判断）与"不可豁免清单"（安全/资源/注入）

### 2.3 显著提升效率的工具/脚本

| 工具 | 提升效率 | 建议固化位置 |
|---|---|---|
| `start-sonarqube.ps1` | 手工启动 5 分钟 → 自动 30 秒 | 任何外部服务都该有 |
| `invoke-api.ps1` + 端点配置 | MCP 不可用时不至于完全停摆 | 通用基础设施层 |
| `framework_patterns.json` | 自动识别 FastAPI 装饰器误报，省 50% 人工分类 | 任何多框架项目必备 |
| 共享库 `scripts/lib/` | 5 个脚本共用 `Resolve-EnvPlaceholder`/`Load-SonarConfig`/`Write-Step` | 任何跨多个 PS1 脚本的技能 |

---

## 三、维度 2：任务执行过程中的不确定性与失败点

### 2.1 不确定性（卡住超过 30 分钟的情况）

| 现象 | 根因 | 解决方式 | 启示 |
|---|---|---|---|
| `Search-SonarIssues` 返回 0 结果但 dashboard 显示有 issues | API 参数 `status`（单数）应为 `statuses`（复数）| 改为 `statuses=OPEN,CONFIRMED,REOPENED` | 任何外部 API 必须先看完整 OpenAPI 文档再调 |
| `search_sonar_issues_in_projects` 报"Insufficient privileges" | 旧版 token 仅有"项目浏览"权限，缺"安全热点"权限 | 在 SonarQube Web 重新生成 Global Analysis Token | token 权限最小化是反模式，应全局可用 |
| `scope` 参数报"Invalid scope" | 传值带了换行符 `\nMAIN` 而非纯 `MAIN` | 强制 trim 后传 | API 参数白名单校验缺失是普遍问题 |
| `verify-connection.ps1` 启动报"无法连接远程服务器" | 用了 2 个 `Get-SonarConfig` 函数定义冲突 | 共享库 lib.ps1 统一加载 | dot-source 加载顺序必须按依赖关系 |
| `dotnet-script` 报"`Cannot find type [System.Net.Sockets...]`" | 跨平台 PowerShell 缺失部分 .NET 类型 | 优先用 `Get-NetTCPConnection`，回退 `netstat` | 跨平台脚本必须有 fallback |

### 2.2 反复出现的同类失败（6 类）

#### 失败模式 1：API 参数名单复数错误（出现 3 次）

- **症状**：调 `Search-SonarIssues` 时 `status` 参数报"参数错误"
- **根因**：SonarQube API 用 `statuses`（复数）+ `issueStatuses`，但工具描述里的示例用了 `status`
- **修复**：在 `scan-workflow.md` 明确"API参数只接受以下值"，并把搜索参数速查表独立成段落

#### 失败模式 2：PowerShell dot-source 与 Export-ModuleMember 混用（出现 2 次）

- **症状**：`Export-ModuleMember : The script 'logging.ps1' is not a module script`
- **根因**：dot-source 加载的脚本（`. $path`）不支持 `Export-ModuleMember`，仅 `.psm1` 模块支持
- **修复**：移除 `Export-ModuleMember`，所有函数 dot-source 时自动注入调用方作用域
- **预防**：在 `lib.ps1` 头部加注释说明

#### 失败模式 3：硬编码工具列表与项目数据耦合（出现 2 次）

- **症状 1**：`detect-platform.ps1` 内置 `("java", "sonar-scanner", "git", ...)` 写死，无法适应新项目
- **症状 2**：`fix_strategies.json` 的 `data_source` 字段写"xianyu_hunter 项目 523 个 issues 分布"，换项目就失效
- **修复**：`platform_tools` 节点从 `core_config.json` 读取；`data_source` 迁移到 `project_config.json -> fix_strategies_overrides`
- **预防**：所有"数据源描述"必须可配置，不嵌入通用配置

#### 失败模式 4：framework_extensions 与 framework_patterns 重复定义（出现 1 次但发现得晚）

- **症状**：`project_config.json` 与 `framework_patterns.json` 都定义了 `fastapi_decorators`，改一处忘改另一处
- **修复**：标记 `framework_extensions` 为 `deprecated`，统一从 `framework_patterns.json` 加载
- **预防**：通用基线在 core，项目特有在 project，但**禁止同一个语义存在两份定义**

#### 失败模式 5：旧配置 `scan_config.json` 与新配置 `core_config.json` 冲突（出现 1 次）

- **症状**：用户用 v1.0 升级到 v2.0 时两个文件共存，技能不知道读哪个
- **修复**：`Load-SonarConfig` 函数优先 v2，v1 存在时打 warning 提示升级但仍 fallback
- **预防**：所有"配置演进"必须有兼容层 + 警告，不能直接 break change

#### 失败模式 6：硬约束业务规则与项目耦合（出现 1 次）

- **症状**：`hard_constraints.json` 内嵌 8 条 Xianyu 业务规则（WebView2/HF_ENDPOINT/HMAC），其他项目无法复用
- **修复**：拆为 `hard_constraints/core.json`（14 条通用安全）+ `hard_constraints/business/{project}.json`（项目特有）
- **预防**：通用配置和项目配置**永远分离**，业务规则**永远可禁用**

### 2.3 临时方案（未清理的妥协）

| 妥协 | 状态 | 清理计划 |
|---|---|---|
| `data_source` 字段写在通用 fix_strategies.json | 已迁移到 project_config.json，但旧字段仍保留 deprecated 注释 | 下一版本 v2.1 移除 |
| 工具列表默认 fallback 写死 `["java", "sonar-scanner", ...]` | 已有配置优先，但 fallback 仍是硬编码 | 下一版本拆到 `defaults/platform_tools.json` |
| `issue-classification.md` 与 `xianyu-rule-overrides.md` 存在内容重叠 | 未清理 | 下一版本合并到 `issue-classification.md` |
| `framework_patterns.json` 未覆盖 Angular/Next.js | 未完成 | 社区需求驱动 |

---

## 四、维度 3：可抽象的固定流程与判断逻辑（SOP）

### 4.1 SOP：SonarQube 类工具接入 6 阶段法

> **适用范围**：任何引入 SonarQube / CodeQL / Semgrep / Trivy 等代码质量工具的团队
> **不适用**：临时一次性扫描（用 sonar-scanner 命令行即可，无需技能化）

```
阶段 0：目标定义
├─ 问 1：扫什么语言？什么框架？
├─ 问 2：要识别哪些误报？（FastAPI 装饰器、React Hook 等）
├─ 问 3：修复目标是"清零"还是"达到阈值"？
└─ 输出：项目特定配置 project_config.json + 目标 issue 数

阶段 1：服务就绪（服务依赖类工具必做）
├─ 1.1 编写 start-xxx.ps1 跨平台启动脚本
├─ 1.2 编写 verify-connection.ps1 连接验证
├─ 1.3 探测工具能力：MCP/CLI/HTTP 至少 1 条
└─ 输出：服务可启停、连接可验证

阶段 2：API 抽象层（MCP 不稳定时必做）
├─ 2.1 封装 invoke-api.ps1 统一 HTTP 调用
├─ 2.2 端点路径、参数名从 config 读取（api_endpoints 节点）
├─ 2.3 实现"自动分页"（ps + hasNextPage 循环）
└─ 输出：MCP 不可用时通过 HTTP 降级

阶段 3：配置分层（4 层）
├─ 3.1 core_config.json：通用（服务/扫描/优先级/过滤/验证/报告）
├─ 3.2 project_config.json：项目特定（项目信息/模块/测试命令/规则覆盖）
├─ 3.3 hard_constraints/core.json：通用安全规则
├─ 3.4 hard_constraints/business/*.json：业务硬约束
├─ 3.5 fix_strategies.json：修复策略表（按 rule_id）
├─ 3.6 framework_patterns.json：多框架模式库
└─ 输出：5 类配置分层，互不耦合

阶段 4：修复执行
├─ 4.1 编写 subagent-task-template.md 子代理模板（5 段式）
├─ 4.2 按文件分组启动子代理（文件间并行，文件内串行）
├─ 4.3 子代理必须输出：根因 + 修复 + 验证 + 报告
└─ 输出：分文件修复报告 + 整体汇总

阶段 5：验证闭环
├─ 5.1 重新扫描对比 issue 数（前/后）
├─ 5.2 运行项目测试（pytest + npm test）
├─ 5.3 硬约束合规性检查（违规即阻塞）
├─ 5.4 撰写 sonar-fix-report.md
└─ 输出：可复现的修复证据链

阶段 6：维护迭代
├─ 6.1 更新 issue-classification.md 误报分类
├─ 6.2 扩充 fix_strategies.json 覆盖更多规则
├─ 6.3 按社区需求扩展 framework_patterns.json
└─ 输出：每月一次的"误报率/修复率"指标
```

### 4.2 关键判断信号（grep 优先）

| 信号 | 含义 |
|---|---|
| `grep "Export-ModuleMember" *.ps1` | dot-source 误用，需删除（仅 .psm1 支持） |
| `grep "status:" scripts/invoke-api.ps1` | API 参数单数/复数错（应 statuses/issueStatuses） |
| `grep "framework_extensions" project_config.json` | 与 framework_patterns.json 重复，需废弃 |
| `grep "data_source.*xianyu\|data_source.*hunyuan" fix_strategies.json` | 通用配置耦合项目数据 |
| `grep "magic\|hardcoded" config/*.json` | 配置硬编码未参数化 |
| `grep "FROM config WHERE project_key" scan-workflow.md` | 配置文件分层缺失 |

### 4.3 决策表：MCP / HTTP / CLI 选择

| 场景 | 首选 | 降级 | 不适用 |
|---|---|---|---|
| 实时扫描（CI/CD） | MCP 工具 | HTTP API | CLI 启动慢 |
| 批量历史回扫 | HTTP API（自动分页） | CLI sonar-scanner | MCP 一次只拉 1 页 |
| 代码片段分析 | MCP `analyze_code_snippet` | 无降级 | 不支持 |
| 跨项目通用扫描 | HTTP API（统一） | CLI | MCP 按项目绑 |
| Windows-only 环境 | CLI（PowerShell 直接调） | 无需降级 | - |

### 4.4 项目实际 SonarQube 配置参考

实际项目的 `sonar-project.properties` 关键配置：

| 配置项 | 值 | 说明 |
|---|---|---|
| `sonar.projectKey` | `xianyu_hunter` | 项目唯一标识 |
| `sonar.projectName` | `Xianyu Hunter` | 项目展示名 |
| `sonar.sources` | `src/xianyu_hunter,frontend/src` | 后端 + 前端源码 |
| `sonar.tests` | `tests` | 测试目录 |
| `sonar.test.inclusions` | `**/*.test.ts,**/*.test.tsx,**/__tests__/**,**/test_*.py,**/*_test.py` | 测试文件匹配模式 |
| `sonar.exclusions` | `**/node_modules/**,**/__pycache__/**,...` | 排除依赖、缓存、构建产物 |
| `sonar.python.version` | `3.10` | Python 版本 |
| `sonar.typescript.tsconfigPath` | `frontend/tsconfig.json` | TS 配置路径 |
| `sonar.sourceEncoding` | `UTF-8` | 源码编码 |

---

## 五、维度 4：适用场景与不适用场景

### 5.1 适用场景

| 场景 | 适用程度 | 关键配置 |
|---|---|---|
| **多项目复用**：1 个技能服务 N 个项目 | ✅ 完全适用 | 配置分层（5 类文件）+ examples 模板 |
| **多框架混合**：FastAPI + React + Vue + Django | ✅ 完全适用 | framework_patterns.json 多框架 |
| **跨平台团队**：Windows 开发 + Linux 部署 | ✅ 完全适用 | detect-platform.ps1 + 路径回退 |
| **MCP 不可用环境**：CI/CD 或受限网络 | ✅ 完全适用 | invoke-api.ps1 降级 + run-sonar-scanner.ps1 |
| **大型项目（10万+ LOC）**：分模块扫描 | ✅ 完全适用 | parallel_agents + files_per_agent |
| **长期维护（> 6 个月）**：规则持续扩充 | ✅ 完全适用 | fix_strategies.json 按需扩展 |

### 5.2 不适用场景

| 场景 | 不适用原因 | 替代方案 |
|---|---|---|
| **< 500 LOC 脚本** | 配置分层是过度设计 | 直接用 sonar-scanner CLI + sonar-project.properties |
| **一次性 MVP** | 不需要可复用的技能 | sonar-scanner 单次执行 |
| **紧急热修复** | 全量扫描太慢（30+ 分钟） | 直接针对性 grep + 手动修 |
| **强生成代码（OpenAPI 生成的 controller）** | 误报率 80%+，修复成本>价值 | sonar.exclusions 排除 generated/ 目录 |
| **未部署 SonarQube 且无法本地启服务** | 服务依赖是硬性前置 | 用 Semgrep（纯 CLI，无需服务） |
| **AI 代码占比 > 70%** | 模式库不识别 AI 风格 | 需扩展 framework_patterns.json（未做） |
| **对延迟敏感（< 100ms）** | API 抽象层 + 分层配置带来 10-20ms 开销 | 直连 HTTP API，去除抽象层 |

### 5.3 边界判定的反模式

> **不要做**：
> 1. **为了"通用"而过度抽象**：v1.0 是项目专用，足够用就先用，等有第二个项目再重构
> 2. **为了"降级"而做 3 套**：MCP + HTTP 已经够，CLI 留给 MCP 不可用 + HTTP 受限场景
> 3. **把硬约束写死在代码里**：必须 config-driven，否则 1 个新项目就要改代码
> 4. **把误报清单藏在 skill prompt 里**：必须独立成 `xianyu-rule-overrides.md` 文件，便于维护

---

## 六、v2.0 现状：6 个文件如何支撑 SOP

| SOP 阶段 | 支撑文件 | 关键能力 |
|---|---|---|
| 0. 目标定义 | `examples/{xianyu-hunter,basic-python,react-frontend}/` | 3 个模板覆盖典型场景 |
| 1. 服务就绪 | `scripts/start-sonarqube.ps1` + `verify-connection.ps1` | 跨平台自动启停 + 健康检查 |
| 2. API 抽象层 | `scripts/invoke-api.ps1` + `lib/invoke-api.ps1` | 7 个 HTTP API 端点封装 |
| 3. 配置分层 | `config/{core,project,fix_strategies,framework_patterns}.json` + `hard_constraints/{core,business/*}.json` | 5+2 类配置分离 |
| 4. 修复执行 | `assets/subagent-task-template.md` + `config/scan.parallel_agents` | 子代理并行 + 串行约束 |
| 5. 验证闭环 | `assets/report-template.md` + `config/verify.{rescan_after_fix,test_command,fail_on_new_issues}` | 报告模板 + 三项验证开关 |
| 6. 维护迭代 | `references/issue-classification.md` + `references/xianyu-rule-overrides.md` | 误报分类 + 豁免清单 |

---

## 七、风险与未解决项

### 7.1 已识别风险

1. **MCP 工具版本依赖**：MCP SonarQube 工具命名可能变更（如 `search_my_sonarqube_projects` → `sonarqube_projects_search`），需关注官方更新
2. **SonarQube 规则库演进**：SonarQube Community 25.x → 26.x 规则 ID 体系微调，需定期校准 `fix_strategies.json`
3. **跨平台 PowerShell 兼容性**：macOS PowerShell Core 与 Windows PowerShell 5.1 行为差异，`.NET` 类型可用性需持续测试
4. **硬约束规则的可执行性**：当前硬约束仅在配置层描述（grep + decision tree），未集成到 SonarQube 自定义规则，CI 阻断靠外部脚本

### 7.2 未解决项

| # | 事项 | 优先级 | 计划 |
|---|---|---|---|
| 1 | `framework_patterns.json` 覆盖 Angular/Next.js/Svelte | 中 | 社区需求驱动 |
| 2 | `issue-classification.md` 与 `xianyu-rule-overrides.md` 内容重叠 | 中 | v2.1 合并 |
| 3 | 工具列表默认 fallback 硬编码 | 低 | 拆到 `defaults/platform_tools.json` |
| 4 | 硬约束规则未集成到 SonarQube 自定义规则 API | 低 | 需研究 SonarQube Custom Rules 机制 |

### 7.3 反馈循环

- **下次优化时必查**：本文「维度 3 SOP」每个阶段是否被新需求绕过
- **下次踩坑时必查**：本文「维度 2 失败模式 6 类」是否新增类似类型
- **下次扩展时必查**：本文「维度 4 不适用场景」是否变化

---

## 八、与其他复盘的关系

| 复盘文档 | 类型 | 关系 |
|---|---|---|
| `编码规范复盘.md` | 工程规范类 | **横向对比**：SOP 阶段划分思路一致（6 阶段 vs 5 阶段），但工程规范类关注"现象归类+模板沉淀"，工具接入类关注"配置分层+降级方案" |
| `四维度复盘方法论.md` | 方法论本体 | **纵向依赖**：本文是方法论在"SonarQube 接入"领域的应用案例 |
| `project_memory.md` | 跨会话硬约束 | **产物落地**：本文 SOP 阶段 4 的"硬约束进项目记忆" |
