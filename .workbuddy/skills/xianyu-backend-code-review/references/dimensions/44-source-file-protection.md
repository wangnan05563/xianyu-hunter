# 维度 44：源码受保护（清理脚本禁删/截断 tracked 源）🆕v4.71.0

> **编码规范引用**：xianyu-hunter-dev `references/coding-standards.md` §3.16.1 / meta-rule #116
> **配置节点**：config.yaml#coding_standards.source_file_protection
> **测试关联**：xianyu-auto-testing（cleanup 类脚本通用）

## 触发条件
- 任何「清理临时文件 / 清理构建产物 / 一键清理」脚本（`.bat`/`.ps1`/`.py`）的新增或修改
- 涉及 `rm -rf` / `Remove-Item` / `del` 等删除命令的 CI 步骤或本地脚本
- 项目内 `scripts/`、`src/` 目录下的清理类文件变更

## 检查规则

### 强制（P0 阻塞）
- 清理脚本**不得**匹配 `src/`、`scripts/`、`*.py`、`*.css`、`*.ts(x)` 等 tracked 源文件（以 config.yaml#source_file_protection.protected_patterns 为准）。
- 删除动作**禁止** `rm -rf` 整目录式覆盖；必须走「枚举清单 + 分片 + 备份清单」。

### 推荐（P1 严重）
- 清理脚本执行前必须有 `git status --short` 守卫（config.yaml#source_file_protection.require_git_status_guard=true），确认不会误伤 tracked 源。
- 清理白名单只含 `build/`、`node_modules/`、`.cache/`、`__pycache__/`、`dist/`、`logs/`、临时日志（config.yaml#source_file_protection.allowed_cleanup_targets），不在白名单内的路径拒绝清理。

### 推荐（P2 改进）
- 清理目标从配置清单读取，避免把路径硬编码进脚本体（满足 meta-rule #1 配置驱动）。

## Grep 扫描命令
```powershell
# 检测清理脚本中的删除命令
grep -rn "rm -rf|Remove-Item|del " scripts/ --include="*.bat" --include="*.ps1" --include="*.py"

# 检测删除命令是否匹配受保护的源文件模式（命中即 P0）
grep -rn "rm -rf|Remove-Item" scripts/ | grep -E "src/|scripts/|\*\.py|\*\.css|\*\.tsx"

# 检测是否有 git status 守卫
grep -rn "git status" scripts/ --include="*.bat" --include="*.ps1"
```

## 判断标准
- 删除命令匹配 `protected_patterns` 任一 → P0 阻塞
- 清理脚本无 `git status` 守卫 / 无白名单排除 `src/` → P1 严重
- 清理路径硬编码、无法参数化 → P2 改进

## 适用场景
- 本地一键清理脚本（bat/ps1/py）
- CI temporary artifact cleanup 步骤
- 构建前后的临时目录清理

## 不适用场景
- 路径写死且明确只含单文件临时产物（如 `rm build/output.zip`，且路径不含 `src/`）
- 纯内存数据清理（不涉及文件系统删除）
- 第三方库内部清理逻辑（不在本仓库源码控制范围）
