# 修复前全链路根因扫描协议（meta-rule #34）

> **元规范编号**：#34（v4.32.0 新增）
> **适用场景**：修复任何非平凡 bug（≥2 个文件参与 / 涉及状态变更 / 跨前后端 / 复盘过 ≥1 次）
> **不适用**：纯样式 bug（颜色/间距/字号）、单行 typo、纯构建错误（依赖缺失/版本冲突）

---

## 一、问题背景

### 1.1 经典症状：单点修复 vs 系统性缺陷

> 用户反馈：「通知中心菜单点击无反应」
>
> 朴素做法：直接去 `App.tsx` 看一下有没有路由 → 没有 → 加一行 → 完成。
>
> **问题**：如果用户还报告"配置中心"、"操作手册"、"实时日志"等 5 个菜单都"点击无反应"，单点修复就只解决了 1/5。
>
> 朴素做法的根因：**"看到什么修什么"**——但 bug 的根因往往是"整条链路缺一环"。

### 1.2 同类失败模式（6 类来自历史复盘）

| 失败模式 | 现象 | 根因 | 预防 |
|---|---|---|---|
| F1 相似 bug 重复 | `repo_chatbot.py:478` 用 `datetime.now() - row.created_at` 触发 TypeError，2 周后又出现在 `api_orders.py:57` | 修复未全仓扫描相似用法 | 修复后必须 grep 模式 |
| F2 配置一致性盲区 | `HF_ENDPOINT` 镜像地址写死，部署时漏 | 配置盲区 - `.env.example` 没列必填项 | 修复后必须全链路检查 |
| F3 跨语言契约模糊 | 前端 `msg.includes('expired')` 判断错误 | 错误码契约散落 | 修复后必须全链路更新错误码表 |
| F4 熔断/重试副作用 | `BatchRefresh#95` 熔断时漏 `save_progress()` | 熔断分支未走完正常分支的清理逻辑 | 修复后必须反查"该分支是否漏了什么" |
| F5 资源生命周期泄漏 | `new Proxy()` 局部变量被 GC | 硬约束未检查实例属性持有 | 修复后必须 grep 资源持有模式 |
| F6 空 except 吞异常 | `run_migrations()` 用 `logger.warning(f"...{e}")` | 关键路径未用 `logger.exception()` | 修复后必须 grep `logger.warning` in critical_path |

---

## 二、5 步根因扫描协议

### 2.1 协议概览

```
┌─ Step 1: 列根因（≥3 个）
│  └─ 必须列出至少 3 个可能根因，覆盖"用户层/接口层/数据层/配置层/历史层"
│
├─ Step 2: 排根因（用 grep/工具逐一验证）
│  └─ 找到根因后，必须用代码扫描确认"这是唯一根因吗"
│
├─ Step 3: 修复（最小修改原则）
│  └─ 只修根因相关行，不顺手重构
│
├─ Step 4: 反查（修复后全链路反查）
│  └─ 必须用脚本/grep 验证"全链路是否还有类似缺口"
│
└─ Step 5: 防回归（写测试 + 加审查点）
   └─ 加 unit test + 写一条 B/F-REVIEW 检查点
```

### 2.2 详细说明

#### Step 1：列根因（≥3 个）

| 维度 | 提问 | 根因示例 |
|---|---|---|
| **用户层** | 用户操作路径上有哪些可能的拦截？ | 路由不存在、权限拦截、组件渲染失败、URL 错误 |
| **接口层** | API 端点是否能到达？ | endpoint 不存在、CORS 阻挡、认证失败、参数错误 |
| **数据层** | 数据是否能正常存取？ | DB 表缺失、列缺失、迁移失败、缓存污染 |
| **配置层** | 配置项是否正确？ | 菜单未注册、config.yaml 字段缺失、环境变量未设 |
| **历史层** | 是否是"修复后回退"或"双重修复未生效"？ | 代码回退、hot-reload 未触发、服务未重启、缓存未清 |

> **强制要求**：必须写出 ≥3 个**独立的**根因（不重复），并按"可能性 × 危害性"排序。

#### Step 2：排根因

对每个根因用 1-2 个工具命令验证：

| 根因 | 验证工具 | 命令 |
|---|---|---|
| 路由不存在 | Grep | `grep "path=\"/notifications\"" frontend/src/App.tsx` |
| 页面文件缺失 | Glob | `Glob "frontend/src/pages/Notifications/index.tsx"` |
| API wrapper 缺失 | Glob | `Glob "frontend/src/api/notifications.ts"` |
| 后端 endpoint 缺失 | Grep | `grep "@router.get.*notifications" src/xianyu_hunter/web/routes/` |
| 菜单未注册 | Grep | `grep "path: /notifications" config/menu_registry.yaml` |
| 服务未重启 | Bash | `curl http://localhost:<port>/api/about/version` |
| 缓存未清 | Bash | 重启 + 清 `webview_data_*` 目录 |

> **关键约束**：验证后必须记录"哪些根因被排除、哪些被确认"。这是 PR 描述的必备内容。

#### Step 3：修复

- 只修改根因相关行（精确编辑原则）
- 不顺手重构相邻代码
- 修复后立即用 `git diff` 检查改动范围

#### Step 4：反查（全链路反查）

修复完成后，**必须**问自己：
1. "这条修复是否覆盖了同类 bug 的所有变体？"（横向同类）
2. "用户操作路径上是否还有其他可能拦截点？"（纵向全链）
3. "这个根因是否在配置/文档/部署中也有体现？"（横向文档）

**反查动作清单**：
- [ ] grep 关键 pattern 至少 3 处全部更新
- [ ] 反向追写端：所有写入端是否一致
- [ ] 启动一遍 dev 服务走用户流程
- [ ] 检查 dev console 是否有 warning

#### Step 5：防回归

- [ ] 加 unit test 覆盖修复点
- [ ] 加 integration test 覆盖"该 bug 触发条件"
- [ ] 更新审查要点（F-REVIEW / B-REVIEW）
- [ ] 更新 `version-history.md`
- [ ] 必要时更新 `project_memory.md` 硬约束

---

## 三、配置节点

```yaml
# xianyu-backend-code-review/config.yaml 的 root_cause_protocol 节点
# 前后端共用相同 schema
root_cause_protocol:
  enabled: true
  # Step 1 列根因：最小数量
  min_root_causes: 3
  # Step 2 排根因：必须使用的工具
  required_verification_tools:
    - "Grep"
    - "Glob"
    - "Read"
    - "RunCommand"
  # Step 4 反查：必查维度
  required_chain_check_dimensions:
    - "menu_registry"        # L1
    - "router"               # L2
    - "page"                 # L3
    - "api_wrapper"          # L4
    - "backend_endpoint"     # L5
  # Step 5 防回归：必须产物
  required_regression_artifacts:
    - "unit_test"
    - "integration_test"
    - "review_checkpoint"
    - "memory_update"  # 必要时更新 project_memory.md
  # 不适用场景：白名单（纯样式/typo/构建错误可豁免）
  exemption_categories:
    - "pure_styling"
    - "single_line_typo"
    - "build_dependency_conflict"
```

---

## 四、判断信号（grep 优先）

| 信号 | 含义 | 违规判定 |
|---|---|---|
| PR 描述 "修复" 段不足 3 句 | 根因未充分展开 | SUGGESTION |
| 修复后没有"反查同类 bug" 段 | Step 4 缺失 | SUGGESTION |
| `git diff` 涉及 ≥3 个无关文件 | 违反最小修改原则 | WARNING |
| 新增逻辑但没加 unit test | Step 5 缺失 | WARNING |
| 没有更新 `version-history.md` | Step 5 文档缺失 | NIT |

---

## 五、不适用场景

| 场景 | 不适用原因 | 替代方案 |
|---|---|---|
| 纯样式 bug（颜色/间距/字号） | 无根因扫描价值 | 直接修 |
| 单行 typo（错别字/标点） | 无系统性 | 直接修 |
| 纯构建错误（依赖缺失/版本冲突） | 是 build pipeline 问题不是代码问题 | 走依赖管理流程 |
| 安全漏洞补丁 | 时间敏感，先修后复盘 | 1 周内补复盘 |
| 实验性 feature 试错 | 故意频繁失败 | 走"实验 → 验证 → 沉淀"流程 |

---

## 六、与元规范 #33 / #35 的关系

- **#33 注册式资源三件套契约**：纵向 5 层齐备性
- **#34 修复前全链路根因扫描协议**：横向 5 步根因扫描（本文档）
- **#35 前后端字段契约单一可信源**：跨层字段对齐

**修复 "通知中心菜单点击无反应" 的完整流程**：
1. 用 #34 Step 1 列 5+ 个根因（菜单/路由/页面/API/后端）
2. 用 #34 Step 2 逐一 grep 验证
3. 用 #33 的 5 层契约确认"缺哪一层"
4. 修复缺失层
5. 用 #34 Step 4 反查：是否还有类似"注册了但没接上"的情况
6. 用 #34 Step 5 加自动化校验脚本（#33 的 `check_registration.py`）

---

## 七、相关引用

- **元规范 #33**：注册式资源三件套契约（`registration-completeness.md`）
- **元规范 #35**：前后端字段契约单一可信源（`contract-single-source.md`）
- **审查要点**：
  - 前端：`F-REVIEW-118 ROOT-CAUSE-MIN-COUNT`（xianyu-frontend-code-review v4.36.0）
  - 后端：`B-REVIEW-160 CHAIN-CHECK-ON-FIX`（xianyu-backend-code-review v4.31.0）
- **方法论**：参见 `四维度复盘方法论.md`（docs/standards/）
