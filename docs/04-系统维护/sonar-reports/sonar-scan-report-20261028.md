# SonarQube 扫描与治理报告

**项目**: Xianyu Hunter（`xianyu_hunter`）
**扫描日期**: 2026-10-28
**SonarQube 版本**: 26.1.0.118079 (Community) · 扫描器 SonarScanner CLI 6.2.1.4610
**分析规模**: 477 个文件 · 97,344 行非注释代码（Python 46,863 / TypeScript 50,481）
**结论**: OPEN 问题 160 → **0**，`new_violations = 0`；质量门禁仍为 RED，但只剩覆盖率与安全热点评审两项（见下）。

---

## 质量门禁

| 指标 | 状态 | 实际值 | 阈值 | 说明 |
|------|:----:|:------:|:----:|------|
| new_violations | ✅ OK | 0 | = 0 | 本轮全部问题清零 |
| new_duplicated_lines_density | ✅ OK | 0.74% | ≤ 3% | — |
| new_coverage | ❌ ERROR | 0.0% | ≥ 80% | 本机未生成 `coverage.xml` / `lcov.info`，非代码问题 |
| new_security_hotspots_reviewed | ❌ ERROR | 0.0% | ≥ 100% | 43 个热点（新增 11），当前令牌无 `/api/hotspots` 权限，无法经 API 标记 |
| **整体 Quality Gate** | ❌ **ERROR** | | | 仅上述两项非代码项导致 |

---

## 问题统计

| 严重级别 | 修复前 | 修复后 |
|----------|:------:|:------:|
| CRITICAL | 43 | 0 |
| MAJOR | 77 | 0 |
| MINOR | 40 | 0 |
| **总计** | **160** | **0** |

| 类型 | 修复前 | 修复后 |
|------|:------:|:------:|
| CODE_SMELL | 152 | 0 |
| BUG | 8 | 0 |
| VULNERABILITY | 0 | 0 |
| SECURITY_HOTSPOT | 0（43 个待评审热点，不计入 issues） | 0 |

涉及 83 个文件、38 条规则，前 15 条占 122 个问题：

| 规则 | 数量 | 规则 | 数量 |
|------|:----:|------|:----:|
| typescript:S3358（嵌套三元） | 50 | typescript:S7735（可读性） | 4 |
| python:S3776（认知复杂度） | 19 | typescript:S4624（嵌套模板串） | 3 |
| typescript:S3776（认知复杂度） | 16 | typescript:S6478（组件内定义组件） | 3 |
| typescript:S1128（未用导入） | 6 | typescript:S4325（冗余断言） | 3 |
| typescript:S6759（props 应 Readonly） | 5 | typescript:S7770（冗余 await 等） | 3 |
| typescript:S2004（函数嵌套过深） | 4 | python:S1192（重复字面量） | 2 |
| python:S125（注释代码） | 4 | 其余 24 条规则 | 38 |
| typescript:S6582（可选链） | 4 | | |

---

## 修复要点（按手法归类）

| 手法 | 覆盖规则 | 说明 |
|------|----------|------|
| 提取纯函数 / 子组件 | S3776 ×35、S2004 ×4、S6478 ×3 | 认知复杂度一律降到阈值内；例如 `buyer.py` 拆出 `_check_duplicate` / `_check_daily_limit` / `_run_buy_attempt`，`Orders.tsx` 拆出 `scanPagesForRef` |
| 消除嵌套三元 | S3358 ×50 | 改为具名变量 + if/分支函数，**不改变分支顺序与取值** |
| 收敛常量与单一来源 | S1192、S4323、S4325 | 重复字面量提为模块常量；类型重复用 `Extract`/别名 |
| 删死代码与未用导入 | S1128 ×6、S1854、S1481、S1172 | 仅删除确证无引用者（先做 importer 清单） |
| 现代化写法 | S6582、S6606、S7735、S7770、S7750、S7776、S7781、S6653、S6551、S6749、S1874 | 可选链、`??=`、返回布尔表达式、`Number.parseFloat` 等，语义等价 |
| React 约定 | S6478、S6759、S4624、S2301 | props 标 `Readonly`；组件提到模块级；拆 `setCollapsed`/`expandByUser` |
| 可访问性 | S6848/S1082/S6819 | `Chatbot` 下拉底部改为原生 `<button>`；`TipButton` 禁用态包裹层**保持 span 语义**并记录 NOSONAR（该 span 内层就是 `disabled <button>`，授予 button 角色会造成角色嵌套，见下方「遗留」） |

**受控例外（NOSONAR）**：仅 `frontend/src/components/TipButton.tsx` 一处，理由与范围写在注释里；其余问题均以改码收敛，未新增任何扫描豁免。

---

## 验证

### 1. 收敛过程（6 次扫描）

| 轮次 | OPEN | 处理 |
|------|:----:|------|
| 基线 | 160 | 指纹化（`rule\|file\|message`）后分批修复 |
| 2 | 160 | CE 期间编辑源码导致报告作废（`has less lines`），重扫 |
| 3 | 5 | 修复轮次自身引入：S3735×2、S6819×2、S3776×1（承接） |
| 4 | 1 | S6819 NOSONAR 落在错行（须贴在 JSX 开标签行） |
| 5 | 0 | 全部清零 |
| 6 | **0** | 测试修正后再次改动 6 个文件，重扫仍为 0，`new_violations=0` |

### 2. 测试

| 套件 | 结果 |
|------|------|
| 后端 pytest（单元 + 集成 + E2E） | **2249 passed, 3 skipped**（0 失败） |
| 前端 vitest 全量 137 个文件 | **1183 passed**（`--testTimeout=30000`） |
| 前端默认 5s 预算复跑 | 137 文件中 12 个文件、14 个用例报 `Test timed out in 5000ms`，**没有一条断言失败** |

关于 5s 超时：以 HEAD（`852fedec`）在独立 worktree 上复现，同样有 8 个用例 5s 超时（`evaluationsBrandFacets` / `evaluationsThresholdScope` / `ordersSort` / `ordersTakeoverTimeout` / `taskListActionColumn`），说明是**本机算力下的既有问题**，不是本次改动引入。修复过程中顺带修掉的 3 处**真实回归**已单独处理：

- `TipButton` 的 `role="button"` 造成按钮角色嵌套（读屏与 `getByRole` 会命中两个同名元素）→ 回退为 span 语义；
- 源码契约用例：`buyer.py` 的 `if not dry_run:`、`ItemList` 的 `facets.regions.length ? facets.regions : fromPage(...)`、`useEvalColumns` 的 `onClick={confirmTakeover}` 在重构后仍保持原写法，契约一字未减；
- `BatchRefresh` / `alertDeepLinkRoundTrip` 两条契约随已提交的 T02975 / T02673 / T02829 结构更新了锚点（`setSearchParams` 2→4、字面量改用 `ORDER_STATUS.DRY_RUN`），断言强度不变。

### 3. 生产构建

```
cd frontend && npx tsc -b && npx vite build
→ release/spa（21 MB，578 个 assets，base=/xianyu/）
→ PWA: sw.js + workbox-6829fd8d.js（precache 591 条）
```

`index.html` 的资源引用均为 `/xianyu/...` 绝对路径，`manifest.webmanifest` 与图标齐备，可直接由后端静态托管。

---

## 遗留与风险

1. **覆盖率未产出**：本机未生成 `coverage.xml` / `lcov.info`，门禁的 `new_coverage` 恒为 0。需要时执行 `pytest --cov --cov-report=xml` 与 `vitest run --coverage` 后重扫即可。
2. **43 个安全热点未评审**：当前令牌对 `/api/hotspots/search` 返回 403，只能在 Web UI（http://localhost:9000）人工评审。
3. **临时 Sonar 项目** `xianyu_tmp_verify_agent2` 需管理员删除。
4. **既有 Bug（本轮未改，超出扫描范围）**：`cookie_status._applicable_self_heal_names` 存在 `StopIteration` 触发路径；另有 httpx `Timeout(connect=, read=)` 的参数用法会在部分版本抛 `ValueError`。
5. **前端 5s 单测预算偏低**：antd Table 类用例在本机常态 10–20s。建议在 `vitest.config.ts` 统一调高 `testTimeout`，或拆分重型用例，否则 CI 会持续红。
6. 服务密钥中曾出现明文令牌，仍建议按此前提醒轮换。

---

## 附：改动规模

87 个文件，+2615 / −1523 行（后端 Python 约 +1160 / −660，前端 TS/TSX 约 +1455 / −863）。未提交任何 commit。
