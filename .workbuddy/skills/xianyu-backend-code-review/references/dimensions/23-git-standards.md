# 维度 23：Git 操作规范

> **编码规范引用**：coding-standards v1.3 §项目记忆 Hard Constraints
> **配置节点**：config.yaml#git_standards

## 触发条件
- `.gitignore` 文件变更
- 新增敏感配置文件（`.env`/credentials/keyring 相关）
- 提交信息审查

## 检查规则

### 强制（P0 阻塞）
- `.gitignore` 必须包含 `.env`、`credentials.*`、`*.key`、`keyring_*`、`.uploads/`、`browser-data/`、`logs/`、`temp/`、`test_results/`
- 不得提交任何含 token / cookie / API key / webhook URL 的文件
- 不得提交 `.uploads/` 目录下的用户上传文件
- 不得提交 `browser-data/` 目录下的浏览器状态文件

### 推荐（P1 严重）
- commit message 遵循 "type: summary" 格式（如 `fix:`、`feat:`、`refactor:`、`docs:`、`chore:`）
- commit message 描述为什么这么做，而非做什么
- 一次 commit 聚焦单一变更目的
- 新增 `.env.example` 或 `config.example.yaml` 时必须同步更新 `.gitignore`（如有新增敏感字段）

### 禁止
- 提交包含绝对路径（如 `D:\code\...`）的代码
- 提交调试用的 `print()` / `pdb.set_trace()` / `breakpoint()`
- 提交注释掉的旧代码块（应直接删除）
- 提交大二进制文件（> 1MB）到仓库（应使用 Git LFS 或外部存储）

## Grep 扫描命令

```bash
# .gitignore 完整性
grep -E "\.env|credentials|\.key|keyring|\.uploads|browser-data|logs|temp|test_results" .gitignore

# 敏感文件检查
ls -la .env credentials.* *.key keyring_* 2>/dev/null

# 调试代码残留
grep -rn "pdb\.set_trace\|breakpoint()\|print(" src/xianyu_hunter/ --include="*.py" | grep -v "logger\|logging\|__main__"

# 注释掉的旧代码
grep -rn "#.*def \|#.*class \|#.*async def " src/xianyu_hunter/ --include="*.py"
```

## 判断标准
- `.gitignore` 缺少 `.env` / `credentials.*` → P0 阻塞
- 提交了含 token 的文件 → P0 阻塞
- commit message 用 "update" / "fix bug" 等无意义描述 → P1 严重
- 代码中有调试 breakpoint → P1 严重

## 适用/不适用场景
- **适用**：任何代码审查中的 Git 相关检查
- **不适用**：本地开发环境变量文件（如 `.env` 本身不属于审查范围）
