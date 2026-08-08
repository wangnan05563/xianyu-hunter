# 源码文件编码完整性规范（Source File Encoding Integrity）

> 本文件归档 xianyu-hunter-dev skill 中与「源码文件编码完整性」主题相关的编码规范（step 280）。
> 主索引见 [_step-index.md](_step-index.md)，元规范见 [meta-rules.md](../../../references/meta-rules.md)。
> 配套审查：前端 `F-REVIEW-246`、后端 `B-REVIEW-337`；配套测试：`xianyu-auto-testing` 模式 AK。
> 与运行时编码规范（[encoding-and-io.md](../../../references/encoding-and-io.md) ENC-01~08）**正交互补**，不重复。

---

### step 280：源码文件编码完整性规范【强制】🆕v4.70.0

280. **源码文件编码完整性规范（SOURCE-FILE-ENCODING-INTEGRITY-01）【强制】🆕v4.70.0**
    - **问题定义**：源码文件**在磁盘上**的非 ASCII 字符（中文等）被替换为字面量 `?`（0x3F），或被 GBK 字节误当作 UTF-8 解码产生 `鑱岃`/`、` 类乱码。后果：编译/运行通常仍正常，但**用户可见文案、注释、日志、甚至代码标识符**出现损坏，且污染 Git 历史。
    - **与 ENC 规范的区别（关键边界）**：`encoding-and-io.md`（ENC-01~08）与 `B-REVIEW-WINDOWS-TERMINAL-ENCODING` 只覆盖**运行时**编码（HTTP/DB/文件 I/O/终端）；本规范只覆盖**源码文件本体**是否被损坏。两类问题不可互相替代，按"问题分类"路由：运行时数据损坏 → ENC/测试模式 K；源码本体损坏 → 本规范。
    - **判定信号（配置驱动，不硬编码）**：按 `config.yaml#source_file_encoding_integrity.scan_globs` 扫描源码文件，匹配下列任一特征：
        - 连续 ≥ `min_consecutive` 个 `?` 且处于非 ASCII 上下文（前后有 CJK）：正则 `[\u4e00-\u9fff]\?{N,}|\?{N,}[\u4e00-\u9fff]`
        - 行内含 Unicode 替换字符 `U+FFFD`（`\ufffd`）
        - （可选）命中 GBK-as-UTF-8 字节特征（如 `鑱`、`、` 等非预期字符簇）
    - **扫描只读、不自动改写**：扫描仅输出 `file:line` 证据，交由人工确认与修复；**禁止**自动替换 `?`（字符串/正则中合法的 `?`（如 `https?://`、URL 模板、可选匹配）必须排除，靠"非 ASCII 上下文"规则 + 人工确认）。
    - **修复协议（8 步）**：
        - S1 分类：运行时损坏还是源码本体损坏？→ 源码本体才继续本规范
        - S2 扫描：按 `scan_globs` / `scan_exclude` 扫描
        - S3 匹配：连续 `?` / U+FFFD / GBK 误读特征
        - S4 定位：输出 `file:line` 证据（不自动改写）
        - S5 确认：人工核对是否为真实损坏（排除合法 `?`）
        - S6 修复：还原中文；`py_compile`（Python）/ `tsc --noEmit`（TS）校验语法
        - S7 回扫：全仓复扫确认 0 命中
        - S8 门禁：pre-commit / CI 接入本扫描，阻断带 `?` 损坏的提交
    - **提交状态判定（易漏点）**：必须区分"工作区未提交"与"`HEAD` 已提交"。仅修工作区会漏掉历史版本，后续 checkout / 合并会再次引入损坏。修复后需对受影响文件做 `git show HEAD:<file>` 比对，必要时在本地分支修正已提交版本并全仓回扫。
    - **配置参数（全部配置化，禁止硬编码路径/阈值/严重级）**：项目 `config/config.yaml#source_file_encoding_integrity` 节点管理：
        - `scan_globs`：扫描的文件 glob 列表（如 `scripts/**/*.py`、`src/**/*.py`、`frontend/src/**/*.{ts,tsx}`）
        - `scan_exclude`：排除路径/文件（如 `dist/`、`node_modules/`、生成文件）
        - `min_consecutive`：判定违规的连续 `?` 最小个数（默认 3）
        - `check_fffd`：是否检测 U+FFFD（默认 true）
        - `check_gbk_misdecode`：是否检测 GBK-as-UTF-8 误读特征（默认 false，按需开启）
        - `severity`：违规严重级别（默认 `high`，可由业务场景调整）
    - **测试用例**：
        - TC-01：源码含连续 `?` 的中文文案 → 扫描命中 `file:line`
        - TC-02：源码含合法 `?`（正则/URL）→ 扫描不误报
        - TC-03：修复后 `py_compile` / `tsc` 通过且全仓复扫 0 命中
    - **反模式（Anti-Pattern）**：
        - AP-01：把中文直接敲进文件后不回扫，损坏随提交进历史
        - AP-02：仅修复工作区，忽略 `HEAD` 已提交版本
        - AP-03：自动脚本盲目替换源码中的 `?`（破坏正则/字符串语义）
        - AP-04：硬编码扫描路径/阈值到技能或脚本（应通过 `config.yaml`）
        - AP-05：把源码本体损坏误判为运行时编码问题，只查 HTTP/DB 而漏查文件
    - **适用**：任何含中文/非 ASCII 字符的源码文件（`.py`/`.ts`/`.tsx`/`.ps1`/`.bat`/`.md` 等）；跨编辑器/OS/Git 保存后出现可疑 `?` 或乱码；复制粘贴 / AI 生成后插入中文；合并冲突解决后的源码；CI/pre-commit 门禁；历史提交回溯。
    - **不适用**：运行时数据字段乱码（→ ENC 规范 / 测试模式 K）；终端 stdout 显示乱码（→ `B-REVIEW-WINDOWS-TERMINAL-ENCODING`）；浏览器字体缺失导致的"方框/豆腐块"；字符串/正则中合法的 `?`；仅含 ASCII 的源码文件。

---

## 协作映射（固定路由）

| 问题表象 | 归类 | 路由目标 |
|---|---|---|
| 用户数据字段出现 `?` / 方块（DB/API 返回值） | 运行时编码损坏 | ENC-01~08 / 测试模式 K |
| 终端打印中文变 `?` | 终端编码 | `B-REVIEW-WINDOWS-TERMINAL-ENCODING`（dim 28） |
| **源码文件本身**中文变 `?` / 乱码 | 源码本体损坏 | **本规范 step 280** → F-REVIEW-246 / B-REVIEW-337 / 模式 AK |
