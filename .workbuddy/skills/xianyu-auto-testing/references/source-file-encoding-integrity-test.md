# 模式 AK：源码文件编码完整性测试

**对应 meta-rule**：#113（跨进程状态同步衍生）/ 配套 xianyu-hunter-dev step 280（SOURCE-FILE-ENCODING-INTEGRITY-01）
**复盘来源**：2026-08-05 登录页提示信息乱码复盘（源码中文被替换为字面量 `?` 0x3F，及 GBK 误读为 UTF-8 乱码 `鑱岃`/`、`）
**配套审查**：前端 `F-REVIEW-246`、后端 `B-REVIEW-337`

> 本模式与"运行时编码损坏"（测试模式 K：DB 脏值诊断）**正交互补**：模式 K 查运行时数据字段，本模式 AK 查**源码文件本体**是否被损坏。按"问题分类"路由，不重复。

### 适用场景
- 用户/开发者报告"源码中文变问号 / 乱码 / 不可读字符"
- 跨编辑器 / 跨操作系统 / 跨 Git 客户端保存后出现可疑 `?` 或乱码
- 复制粘贴 / AI 生成后插入中文 / 合并冲突解决后的源码
- CI / pre-commit 阶段的源码健康度门禁
- 历史提交回溯（确认某次提交是否引入了编码损坏）

### 不适用场景
- 运行时 DB / API 返回值乱码（→ 模式 K：DB 脏值诊断）
- 终端 stdout 显示乱码（→ 后端 `B-REVIEW-WINDOWS-TERMINAL-ENCODING`）
- 浏览器字体缺失导致的"方框 / 豆腐块"（非编码问题）
- 字符串 / 正则 / SQL 中**合法**的 `?`（如 `https?://`、URL 模板、可选匹配、`?` 参数占位）——靠"非 ASCII 上下文"规则排除，仍需人工确认
- 仅含 ASCII 的源码文件（无损坏可能）

### 诊断流程（4 步）

1. **AK-01 定位可疑文件**：按 `config.yaml#mode_ak_source_file_encoding_integrity.scan_globs` 扫描源码文件，输出命中 `file:line`（**只读，不自动改写**）。
2. **AK-02 特征判定**：区分三类损坏信号：
   - 连续 `?` 且处于非 ASCII 上下文（前后有 CJK）：正则 `[\u4e00-\u9fff]\?{N,}|\?{N,}[\u4e00-\u9fff]`（N=`min_consecutive`）
   - Unicode 替换字符 `U+FFFD`（`\ufffd`）
   - （`check_gbk_misdecode=true` 时）GBK-as-UTF-8 误读特征（`鑱`/`、` 等非预期字符簇）
3. **AK-03 人工确认与修复**：排除合法 `?` → 还原中文 → `py_compile`（Python）/ `tsc --noEmit`（TS）校验语法 → 若损坏已 `HEAD` 提交，在本地分支修正并复扫。
4. **AK-04 全仓回扫回归**：全仓复扫确认 0 命中，必要时接入 pre-commit / CI 门禁。

### 测试用例
- AK-TC-01：源码含连续 `?` 的中文文案 → 扫描命中 `file:line`
- AK-TC-02：源码含合法 `?`（正则 / URL）→ 扫描不误报
- AK-TC-03：含 U+FFFD 替换字符 → 扫描命中（当 `check_fffd=true`）
- AK-TC-04：修复后 `py_compile` / `tsc` 通过且全仓复扫 0 命中

### 配置参数
所有参数通过 `config.yaml#mode_ak_source_file_encoding_integrity` 管理，**禁止硬编码**路径/阈值/严重级，包括：
- `scan_globs`：扫描的文件 glob 列表（如 `src/**/*.py`、`scripts/**/*.py`、`frontend/src/**/*.{ts,tsx}`）
- `scan_exclude`：排除路径（如 `dist/`、`node_modules/`、`*.pyc`、生成文件）
- `min_consecutive`：判定违规的连续 `?` 最小个数（默认 3）
- `check_fffd`：是否检测 U+FFFD（默认 true）
- `check_gbk_misdecode`：是否检测 GBK-as-UTF-8 误读特征（默认 false，按需开启）
- `severity`：违规严重级别（默认 `high`）
- `gate`：是否作为 pre-commit / CI 门禁阻断（默认 true）

### 与其他模式协作
- 诊断完成后触发模式 K（DB 脏值诊断，确认运行时数据未被同源损坏）+ 模式 C（单元测试回归）。
- 不适用场景自动重定向：运行时 DB/API 乱码 → 模式 K；终端显示乱码 → 后端终端编码检查。
- 与开发规范 step 280、审查检查点 F-REVIEW-246 / B-REVIEW-337 形成"开发-审查-测试"闭环。
