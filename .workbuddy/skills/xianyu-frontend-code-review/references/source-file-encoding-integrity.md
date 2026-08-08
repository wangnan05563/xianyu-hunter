# F-REVIEW-246 源码文件编码完整性（Source File Encoding Integrity）

> 检查点 ID：F-REVIEW-246
> 维度：编码规范（与后端 `B-REVIEW-337`、开发规范 `xianyu-hunter-dev` step 280、测试模式 AK 配套）
> 配套开发规范：xianyu-hunter-dev step 280（SOURCE-FILE-ENCODING-INTEGRITY-01）
> 配置节点：`config.yaml#coding_standards.source_file_encoding_integrity`
> 严重程度：默认 `high`（可由配置调整）

---

## 1. 检查目标

检测**前端源码文件本体**在磁盘上是否出现非 ASCII 字符（中文等）被替换为字面量 `?`（0x3F），或被 GBK 字节误当作 UTF-8 解码产生的 `鑱岃`/`、` 类乱码。

> **边界**：本检查点只管"源码文件本体"，**不**覆盖运行时编码（HTTP/API 响应、终端、构建产物运行期）。运行时乱码请路由到对应检查点或开发规范 ENC 系列。

## 2. 判定标准（配置驱动，禁止硬编码）

所有阈值/路径来自 `config.yaml#coding_standards.source_file_encoding_integrity`：

- `scan_globs`：扫描的文件 glob（默认 `frontend/src/**/*.{ts,tsx,js,jsx,json,md}`）
- `scan_exclude`：排除路径（默认 `frontend/src/**/dist/**`、`**/node_modules/**`、生成文件）
- `min_consecutive`：判定违规的连续 `?` 最小个数（默认 3）
- `check_fffd`：是否检测 U+FFFD 替换字符（默认 true）
- `check_gbk_misdecode`：是否检测 GBK-as-UTF-8 误读特征（默认 false，按需开启）
- `severity`：违规严重级别（默认 `high`）

**命中规则**（满足任一即标记，输出 `file:line` 证据，**不自动改写**）：

1. 行内存在连续 ≥ `min_consecutive` 个 `?` 且处于非 ASCII 上下文（前后有 CJK）：
   正则：`[\u4e00-\u9fff]\?{N,}|\?{N,}[\u4e00-\u9fff]`
2. 行内含 Unicode 替换字符 `U+FFFD`（`\ufffd`）
3. （`check_gbk_misdecode=true` 时）命中 GBK-as-UTF-8 误读特征字符簇

## 3. 证据采集（只读命令，参数来自配置）

```bash
# 连续 ? 且非 ASCII 上下文（N = min_consecutive）
grep -rPn '[\x{4e00}-\x{9fff}]\?{3,}|\?{3,}[\x{4e00}-\x{9fff}]' frontend/src

# U+FFFD 替换字符
grep -rPn '\x{fffd}' frontend/src

# 验证修复后全仓 0 命中
grep -rPn '\?{3,}' frontend/src && echo "仍有残留" || echo "OK"
```

## 4. 严重级别与处置

| 级别 | 判定 | 处置 |
|---|---|---|
| `high`（默认） | 用户可见文案/注释/日志含连续 `?` 或 U+FFFD | 必须修复后再合并 |
| `medium` | 仅 GBK 误读特征命中（误报风险较高） | 人工确认是否为真实损坏 |

> 合法 `?`（URL 模板 `https?://`、正则可选匹配、占位串）**不**计入——靠"非 ASCII 上下文"规则 + 人工确认排除。

## 5. 修复建议

1. 定位：`file:line` 证据 → 人工确认是否为真实损坏（排除合法 `?`）。
2. 还原：将 `?` 还原为正确的中文/原文。
3. 校验：`npx tsc --noEmit` 或项目类型检查确认语法无误。
4. 回扫：全仓复扫确认 0 命中。
5. 门禁：建议接入 pre-commit / CI，阻断带 `?` 损坏的提交。

## 6. 适用 / 不适用

- **适用**：含中文/非 ASCII 字符的前端源码（`.ts`/`.tsx`/`.js`/`.jsx`/`.json`/`.md`）；跨编辑器/OS 保存后可疑 `?` 或乱码；合并冲突解决后；CI 门禁；历史提交回溯。
- **不适用**：运行时 API 响应乱码（查 Content-Type charset / 后端）；终端 stdout 显示乱码；浏览器字体缺失"方框/豆腐块"；字符串/正则中合法 `?`；纯 ASCII 文件。

## 7. 与其他检查点协作

| 表象 | 路由 |
|---|---|
| 前端源码本体中文变 `?` / 乱码 | **本检查点 F-REVIEW-246** |
| 运行时 API 响应中文变 `?` | 后端 `B-REVIEW-WINDOWS-TERMINAL-ENCODING` + ENC 系列 |
| DB 字段脏值（问号/方块） | 测试模式 K（DB 脏值诊断） |
