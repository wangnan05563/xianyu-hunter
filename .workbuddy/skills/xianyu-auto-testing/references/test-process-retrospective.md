# 测试过程复盘：2026-08 三起构建/运行时问题的验证路径

> **复盘方法**：Sequential Thinking 四维度复盘（聚焦"测试/验证过程"，与 `xianyu-hunter-dev/references/retrospective-2026-08-12.md` 的"修复过程"互补）
> **触发来源**：用户要求基于最近历史对话（图标复用、打包构建报错、实时搜索 TargetClosedError）梳理测试过程并优化 `wiki-auto-testing`（即本技能）
> **关联**：模式 AN（构建与运行时韧性回归）、测试验证三档机制（B1/B2/C3/D1/D2）、修复回归测试生成（模式 AN 步骤 5）

---

## T.1 维度一：成功执行测试任务的完整步骤

三起修复的验证路径分三层，按"成本/保真度"递进：

1. **语法/静态校验层（必做，零依赖）**
   - `python -m py_compile <file>` 确认改动无语法错误（案例 C `_search.py` 已验证）
   - `grep` 确认指令落地：`grep "SetupIconFile" installer.iss scripts/build-exe.ps1`（案例 A）、读 `.venv-build/pyvenv.cfg` 的 `home`（案例 B）

2. **最小 mock 单元测试层（核心防回归）**
   - 案例 C：用 `MagicMock` 模拟 Playwright `Page`（仅暴露 `is_closed`/`unroute`/`context`/`browser`），`SearchMixin.__new__()` 跳过 `__init__` 避免业务依赖；5 用例覆盖关闭态短路 / 正常完成 / shield 防取消 / 并发关闭兜底。
   - 测试仅依赖模块级 `logger`，无需真实浏览器。

3. **独立 probe 实测层（验证运行时语义）**
   - 案例 C：写独立 `tests/_probe_unroute.py`，直接测量方法耗时（`ELAPSED 2.508`）、`SLOW_CANCELLED=False`（shield 生效）、`UNROUTE_CALLED=True`，证明无 hang 且 shield 正确。

4. **产物时间线核对层（验证修复已进产物）**
   - 案例 A/B：比对源码 mtime（08-09）与产物构建 mtime（08-11），确认修复晚于源码改动 → 已进入 `dist` 产物。

---

## T.2 维度二：测试过程中的不确定性与失败点

| 编号 | 不确定性与失败点 | 教训 |
|------|------------------|------|
| TU1 | 构建 venv（`.venv-build`）未装 pytest，首次跑测试报 `pytest: command not found` | 测试前置需先装测试依赖（pytest/pytest-asyncio），或复用已装依赖的运行时 |
| TU2 | 单用例耗时 75s 异常长，误判方法 hang；实为测试 cleanup 中 `await slow` 抛 `CancelledError`（BaseException 不被 `except Exception` 捕获）冒泡致测试失败，与方法正确性无关 | 测试清理须区分 `CancelledError` 与业务异常；方法本身用 probe 独立测耗时 |
| TU3 | PowerShell 5.1 不回显 stdout、不支持三元运算符；`od` 在 Git Bash 不可用 → 多轮才读到 BOM/ICO 校验结果 | 校验脚本必须落盘文件再 `Read`，不依赖终端回显 |
| TU4 | 安全过滤器拦截 `Add-Type`（运行时编译 .NET）、`%PATH%` cmd 风格、`Remove-Item -Recurse` → 原"提取安装包图标"验证方案被阻断 | 验证尽量走纯 Python（`ExtractIconEx` 不可用时改 `py_compile`/时间线核对）；破坏式操作走 `.NET` 直调 |
| TU5 | 大 SKILL.md（0.5MB+）含旧条目 mojibake，Read/Edit 匹配的 CJK 串易失配 | 对大文件优先用 ASCII 锚点匹配；新增内容用 UTF-8 写入保证新段落编码正确 |
| TU6 | 运行时端到端验证（真实启动服务触发 `/api/tasks/<id>/links` 看日志）环境重、需登录态，未做 | 代码层+单测层已闭环，端到端列为可选后续，不阻塞交付 |

---

## T.3 维度三：可抽象的固定流程与判断逻辑

### 测试流程 1：修复回归测试生成（通用，配置驱动）
```
1. 定位修复点所属 meta-rule / B/F-REVIEW 与对应配置节点
2. 提取"核心不变量"作为断言（shield 不取消内部 task / 关闭态短路 / 钉选运行时健康）
3. 构造最小 mock，不启动真实浏览器/服务
4. 仅依赖模块级 logger，跳过 __init__ 避免业务依赖
5. 超时/路径/选择器全部从 config.yaml 读取，禁止硬编码
6. 落盘 tests/test_<fix>.py 并在模式 AN 索引登记
```

**判断逻辑**：
```
对任意已修复 bug：
  是否破坏了既有测试？ → 先跑全量 pytest 确认无回归
  修复是否有"核心不变量"可断言？ → 是则生成最小 mock 回归测试
  是否需真实环境才能验证？ → 否（优先 mock）；是则标记为端到端可选
```

### 测试流程 2：分层验证档位选择（既有三档机制强化）
```
Tier 1（refactor）：pytest tests/ + tsc --noEmit 全量
Tier 2（bugfix）：改动文件核心功能 import/语法验证 + 新增回归测试
Tier 3（feature）：改动文件语法+导入链路验证（5/5）
```
本三起均属 bugfix → 走 Tier 2：语法校验 + 新增最小 mock 回归测试 + 产物时间线核对。

### 测试流程 3：结果可读化（绕过终端回显失效）
```
所有 PowerShell/长任务输出 → Out-File -Encoding UTF8 落盘 → Read 文件
禁止依赖 stdout 回显（PS 5.1 常不回显）
```

---

## T.4 维度四：适用场景与不适用场景

### 测试流程 1（修复回归测试生成）
**适用**：任何已修复且有"核心不变量"可断言的 bug；跨模块/需避免真实依赖的回归守护；CI 门禁前的最小验证。
**不适用**：纯 UI 视觉变更（需截图比对，非 mock 可覆盖）；依赖真实外部服务且无法 mock 的端到端链路；一次性探索性调试。

### 测试流程 2（分层验证档位）
**适用**：所有代码改动后的验证分级；资源受限环境降级。
**不适用**：安全/数据丢失类必须全量验证（不适用 Tier 3 降级）；纯文档变更。

### 测试流程 3（结果可读化）
**适用**：PowerShell 5.1 / 长任务 / 安全过滤器可能拦截原生命令的场景。
**不适用**：简单短命令且 stdout 可靠回显的场景（直接读即可）。

---

## T.5 与整体工作流的衔接
- **配置驱动**：本复盘所有验证参数（pytest 路径、超时秒数、mock 构造方式）下沉到 `config.yaml#mode_an_build_runtime_resilience` 与三档机制节点，技能本身不含硬编码。
- **跨技能一致**：测试覆盖点对应 `xianyu-hunter-dev` meta-rules #112~#115、`xianyu-backend-code-review` B-REVIEW-291~295、`xianyu-frontend-code-review` F-REVIEW-227~228，形成"规范→审查→测试"闭环。
- **SOP 合规**：新增回归测试（如 `tests/test_unroute_search_api.py`）登记到模式 AN 索引；同类根因再发 ≥ 2 次触发规范升正（与 meta-rule #36/#37 沉淀 SOP 一致）。
