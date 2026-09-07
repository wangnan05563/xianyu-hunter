# 模式 AP：沙箱安全删除范式测试

> 配置节点：`config.yaml#mode_ap_sandbox_safe_deletion`
> 对应：`xianyu-hunter-dev` 规范 32；与 `xianyu-backend-code-review` B-REVIEW-342（沙箱安全删除条款）跨技能一致。

### 触发关键词
- 删除被拦截 / safe-delete / SAFE_DELETE_FAIL_CLOSED
- 删除中断构建 / 回收站删除 / 批量删除失败 / 清理脚本删除

### 步骤 0：加载配置
读取 `config.yaml#mode_ap_sandbox_safe_deletion` 段。禁止硬编码任何命令/阈值/严重级。

### 步骤 1：删除实现绕过 safe-delete 守卫验证（规范 32）
1. 构建/清理脚本（`.ps1`/`.bat`/`.py`）中的删除必须用 `allowed_delete_impls` 列出的实现：
   - PowerShell：`[System.IO.Directory]::Delete($p, $true)` / `[System.IO.File]::Delete($p)`（.NET 直接调用，不经被劫持的 `rm`/`del`/`Remove-Item`）。
   - Python：`ctypes.windll.kernel32.RemoveDirectoryW` / `DeleteFileW`。
2. 命中 `forbidden_delete_cmds`（`rm`/`del`/`Remove-Item`）→ WARNING（沙箱 safe-delete 为 fail-closed，会中断脚本）。

### 步骤 2：大目录批量删除策略验证（规范 32）
1. 文件数超过 `bulk_delete.max_batch_per_process` 的删除，必须走 `bulk_delete.use_same_volume_rename_escape`（同卷 `os.rename` 逃逸到项目树外 O(1)）或分片批量（每批 ≤ `max_batch_per_process`，批间 `min_sleep_seconds` 暂停）。
2. 禁止在单进程内一次性删除超大目录（沙箱内核级限速会 kill 整进程）。

### 步骤 3：扫描范围
按 `scan_globs`（`scripts/**/*.ps1` / `*.bat` / `*.py`）grep 删除调用，输出 file:line 证据。

### 跨技能校验
- `xianyu-hunter-dev` 规范 32
- `xianyu-backend-code-review` B-REVIEW-342（维度 49 沙箱安全删除条款）
