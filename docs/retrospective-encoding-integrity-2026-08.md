# 复盘：源码文件编码完整性（中文→字面量 `?` / GBK 误读乱码）

> 复盘日期：2026-08-05
> 复盘驱动：闲鱼猎人项目登录页提示信息乱码问题（源码中文被替换为字面量 `?` 0x3F）+ 开发与测试过程复盘
> 配套产出：`xianyu-hunter-dev` step 280、前端 `F-REVIEW-246`、后端 `B-REVIEW-335`、`xianyu-auto-testing` 模式 AK
> 方法：Sequential Thinking（分步推理，见下文"Sequential Thinking 推理链"）

---

## 一、问题定性（为什么需要一条新规范）

历史上已沉淀的编码规范（`xianyu-hunter-dev/references/encoding-and-io.md`，ENC-01~08）与审查检查点（`B-REVIEW-WINDOWS-TERMINAL-ENCODING`、前端 `F-REVIEW` 编码系列）**全部聚焦"运行时编码"**：

- HTTP body 经 PowerShell `cp936/gbk` 编码 → 中文变 `?`
- 数据库 / 文件 I/O / JSON 序列化 的 UTF-8 一致性
- 终端 stdout 编码干扰诊断

而本次登录页乱码的根因是**另一类问题**：**源码文件在磁盘上的中文（非 ASCII 字符）被替换为字面量 `?`（0x3F），或 GBK 字节被误当作 UTF-8 解码产生 `鑱岃`/`、` 类乱码**。该类问题特征：

| 维度 | 运行时编码损坏（已有规范覆盖） | 源码文件编码完整性（本次新增） |
|---|---|---|
| 发生位置 | 进程间 / I/O 边界（HTTP/DB/终端） | 源码文件本身（磁盘） |
| 触发时机 | 运行期传输 / 读写 | 编辑、复制、跨工具保存、Git 提交前 |
| 表现 | 用户数据字段出现 `?` | 提示文案、注释、日志、甚至代码标识符出现 `?` 或乱码 |
| 编译/运行 | 通常仍正常（语法不受影响） | 编译/运行仍正常，但**用户可见内容**与**代码可读性**受损 |
| 现有覆盖 | ENC-01~08、B-REVIEW-WINDOWS-TERMINAL-ENCODING | **无** |

> 关键判断：**两类问题不可互相替代**。运行时规范保证"数据流过边界时不被损坏"；源码完整性规范保证"写进仓库的源代码本身不含损坏字符"。后者此前是盲区。

---

## 二、Sequential Thinking 推理链（分步复盘）

### Step 1 — 明确现象与边界
- 现象：登录页 `set_status` 提示信息、注释、stderr 中出现中文变 `?`。
- 边界：先确认是"用户数据被运行时损坏"（→ 走 ENC 规范 / 模式 K）还是"源码本身损坏"（→ 走本规范）。本次为**源码本身**。

### Step 2 — 定位损坏文件与行
- 用字节级 / 文本扫描定位：在 `scripts/` 与 `src/` 中 grep 连续 `?`（如 `grep -P '\?{3,}'` 或 `re.search(r'\?{3,}', line)`）。
- 确认首个污染点：`scripts/browser_login.py`（12 行：3 条用户可见 `set_status` + 9 条注释/stderr）。

### Step 3 — 区分"本地未提交"与"已提交（HEAD）"
- 关键不确定性：**损坏是只存在于工作区，还是已 `HEAD` 提交进历史？** 这决定修复范围。
- 判断：对工作区文件 `py_compile` 校验 → 对 `git show HEAD:<file>` 比对 → 发现 10 行已随某次 HEAD 提交进历史。
- 失败点：若只看工作区"已修好"就结束，历史版本仍携带损坏，后续 checkout / 分支合并会再次引入。

### Step 4 — 修复与全仓回扫
- 修复 12 行工作区；对 HEAD 已提交的 10 行，在本地分支修正并确保不再有 `???` 残留。
- 全仓扫描 `scripts/` + `src/`：`grep -rPn '\?{3,}'` 返回 0 → 确认无残留。

### Step 5 — 提炼可抽象的固定流程
- 该修复过程可抽象为通用协议（见第三部分"固定流程与判断逻辑"），并固化为开发规范（step 280）+ 审查检查点（F-REVIEW-246 / B-REVIEW-335）+ 测试模式（AK）。

### Step 6 — 收敛适用 / 不适用边界
- 明确本规范只管"源码文件本体"，不管"运行时数据"；明确阈值、扫描路径、严重级别全部配置化（无硬编码）。

---

## 三、四个维度复盘

### 维度 A：成功执行任务的完整步骤

1. **现象确认**：登录页提示乱码，截图定位到具体文案。
2. **根因分类**：判定为"源码文件本体损坏"而非"运行时编码损坏"（排除 ENC 规范覆盖范围）。
3. **定位污染文件**：字节/文本扫描 `scripts/browser_login.py` 等，识别 `?` 替换的中文。
4. **提交状态判定**：区分工作区未提交 vs `HEAD` 已提交，避免漏修历史版本。
5. **逐行修复**：还原被替换的中文（提示文案、注释、stderr 文案）。
6. **语法校验**：`python -m py_compile` 确认修复未引入语法错误。
7. **全仓回扫**：`grep -rPn '\?{3,}' scripts/ src/` → 0 命中，确认无残留。
8. **规范固化**：将流程沉淀为开发规范 + 审查检查点 + 测试模式（即本次交付物）。

### 维度 B：任务执行过程中的不确定性与失败点

| # | 不确定 / 失败点 | 影响 | 应对 |
|---|---|---|---|
| 1 | 损坏是仅工作区还是已 `HEAD` 提交？ | 只修工作区会漏掉历史版本，后续合并再次引入 | `git show HEAD:<file>` 比对，双路径修复 |
| 2 | 连续 `?` 是否一定是损坏？ | URL 模板、占位串、正则中合法的 `?` 会被误报 | 结合"非 ASCII 上下文"+ 阈值，且**人工确认**而非自动改写 |
| 3 | GBK 误读类乱码（`鑱岃`/`、`）无 `?` 特征 | 仅扫描 `?` 会漏掉此类损坏 | 增加 U+FFFD 与"GBK-as-UTF-8 字节特征"判断（可选规则） |
| 4 | 扫描范围（哪些目录/扩展名） | 范围过大误报多，过小漏报 | 路径/扩展名全部配置化（`scan_globs`/`scan_exclude`） |
| 5 | 自动修复是否会破坏字符串/正则语义 | 盲目替换 `?` 会损坏代码 | **仅告警 + 人工修复**，不做自动改写 |
| 6 | 阈值（连续几个 `?` 算违规） | 阈值低误报、高漏报 | 阈值配置化，默认 ≥3 |

### 维度 C：可抽象的固定流程与判断逻辑

**固定流程（源码编码完整性协议）**：

```
S1 分类：运行时损坏(ENC/模式K) 还是 源码本体损坏(本规范)？ → 源码本体才继续
S2 扫描：按 config.scan_globs 扫描源码文件
S3 匹配：连续 ≥ threshold 个 '?' 且处于非ASCII上下文（或命中 U+FFFD/GBK误读特征）
S4 定位：输出 file:line 证据（不自动改写）
S5 确认：人工核对是否为真实损坏（排除 URL/占位/正则合法 ?）
S6 修复：还原中文；py_compile / tsc 校验语法
S7 回扫：全仓复扫确认 0 命中
S8 提交门禁：pre-commit / CI 接入本扫描，阻断带 ? 损坏的提交
```

**判断逻辑（伪代码）**：

```python
import re, pathlib

CONF = load_config("config.yaml")["source_file_encoding_integrity"]
RX = re.compile(r'[\u4e00-\u9fff]\?{%d,}|(\?{%d,}[\u4e00-\u9fff])' %
                (CONF["min_consecutive"], CONF["min_consecutive"]))

def scan(paths: list[str]) -> list[tuple[str,int,str]]:
    hits = []
    for p in iter_source_files(paths, CONF["scan_globs"], CONF["scan_exclude"]):
        for i, line in enumerate(pathlib.Path(p).read_text(encoding="utf-8").splitlines(), 1):
            if RX.search(line) or "\ufffd" in line:
                hits.append((p, i, line.strip()))
    return hits   # 仅返回证据，交给人工确认与修复
```

> 核心原则：**扫描只读、判定靠上下文、修复靠人、参数靠配置**。

### 维度 D：适用场景与不适用场景

**适用场景**
- 任何包含中文/非 ASCII 字符的源码文件（`.py`/`.ts`/`.tsx`/`.ps1`/`.bat`/`.md` 等）
- 跨编辑器 / 跨操作系统 / 跨 Git 客户端保存后出现可疑 `?` 或乱码
- 复制粘贴、AI 生成后插入中文、合并冲突解决后的源码
- CI / pre-commit 阶段的源码健康度门禁
- 历史提交回溯（确认某次提交是否引入了编码损坏）

**不适用场景**
- 运行时数据字段乱码（→ ENC 规范 / 自动测试模式 K）
- 终端 stdout 显示乱码（→ `B-REVIEW-WINDOWS-TERMINAL-ENCODING`）
- 浏览器字体缺失导致的"方框/豆腐块"（非编码问题）
- 字符串/正则中**合法**的 `?`（如 `r"https?://"`、URL 模板、可选匹配）——靠"非 ASCII 上下文"规则排除，仍需人工确认
- 仅含 ASCII 的源码文件（无损坏可能）

---

## 四、开发与测试过程复盘（第二个复盘视角）

> 针对"开发与测试过程"本身，同样按四维度复盘，目标是让规范**可执行、可测试、可门禁**。

### A. 成功步骤
1. 开发阶段：新增/修改含中文文案的代码后，本地 `py_compile`/`tsc` 仅验证语法，未验证"字符完整性"。
2. 测试阶段：已有模式 K 验证 DB 脏值，但**无源码层字符完整性测试**。
3. 本次补齐：新增自动测试模式 AK（源码编码完整性），与开发规范 step 280、审查检查点联动。

### B. 不确定性与失败点
- 开发时缺少"写中文即自检"的即时反馈，损坏常在提交后才发现。
- 测试时缺少"源码静态扫描"类用例，依赖人工 code review 肉眼发现。
- 跨工具（编辑器/AI/终端）保存链路不可见，损坏源头难追溯。

### C. 可抽象流程
- 开发：编辑器保存即触发轻量扫描（或 pre-commit hook）。
- 测试：模式 AK 作为静态扫描用例，纳入回归与 Tier 分级。
- 审查：F-REVIEW-246 / B-REVIEW-335 作为 PR 审查必检项。

### D. 适用 / 不适用（开发测试视角）
- 适用：所有含非 ASCII 字符的源码仓库；CI 门禁；pre-commit。
- 不适用：纯 ASCII 项目；二进制资源；运行时数据校验（已由其他规范覆盖）。

---

## 五、配置化与泛化要求（贯穿所有交付物）

为满足"无硬编码、配置驱动、通用泛化"：

- 所有扫描路径 / 扩展名 / 阈值 / 严重级别 **不写死**在技能正文，统一放入各技能 `config.yaml`。
- 扫描逻辑用**通用正则 + 配置参数**，不依赖特定项目路径（如 `scripts/`、`src/` 由 `scan_globs` 决定）。
- 严重级别（P0~P3 或 CRITICAL/HIGH/...）由配置映射，可按业务场景调整。
- 新规范与既有 ENC 规范、模式 K、审查检查点**正交互补**，通过"问题分类"路由，避免重复。

---

## 六、交付物清单（本次）

| 交付物 | 位置 | 说明 |
|---|---|---|
| 开发规范 | `xianyu-hunter-dev/.../coding-rules/encoding-integrity.md` (step 280) | 源码文件编码完整性规范 |
| 前端审查 | `xianyu-frontend-code-review` F-REVIEW-246 + `references/source-file-encoding-integrity.md` | 前端源码编码完整性审查要点 |
| 后端审查 | `xianyu-backend-code-review` B-REVIEW-335 + `references/source-file-encoding-integrity.md` | 后端源码编码完整性审查要点 |
| 自动测试 | `xianyu-auto-testing` 模式 AK + `references/source-file-encoding-integrity-test.md` | 源码编码完整性测试模式 |
| 配置 | 三个技能 `config.yaml` #source_file_encoding_integrity / #mode_ak_* | 扫描参数配置化 |
| 呈现 | 两个审查技能 `templates/report-template.md` | 增强编码完整性结果呈现 |
