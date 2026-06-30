# 版本控制流程

本项目遵循 [Semantic Versioning 2.0.0](https://semver.org/lang/zh-CN/) 与 [Keep a Changelog 1.1.0](https://keepachangelog.com/zh-CN/1.1.0/) 规范。本文档定义版本号的递增规则、变更记录规范与发布流程。

## 1. 版本号规则

版本号格式：`MAJOR.MINOR.PATCH`（如 `0.2.0`）。

| 位 | 递增条件 | 示例 |
|---|---|---|
| MAJOR | 破坏性变更（不兼容旧 API） | `0.2.0` → `1.0.0` |
| MINOR | 新功能，向后兼容 | `0.2.0` → `0.3.0` |
| PATCH | Bug 修复，向后兼容 | `0.2.0` → `0.2.1` |

**预发布版本**（如 `0.3.0-alpha.1`）当前不使用，所有发布均为正式版。

**0.x.x 阶段说明**：项目处于 0.x.x 阶段时，MINOR 位递增可包含破坏性变更（按 semver 规范，0.x.x 不保证向后兼容）。MAJOR 位递增留待 1.0.0 稳定版发布时使用。

## 2. 版本号源头

**单一源头**：`src/xianyu_hunter/__init__.py` 的 `__version__` 字段。

所有其他位置的版本号必须从此源头同步，不得独立修改：

| 文件 | 用途 | 同步方式 |
|---|---|---|
| `src/xianyu_hunter/__init__.py` | **源头** | 手动或 `bump_version.py` |
| `pyproject.toml` | setuptools 打包元数据 | `bump_version.py` 自动同步 |
| `src/xianyu_hunter/_build_info.py` | About API 读取 | `build_info.py` 自动生成 |
| `CHANGELOG.md` | 变更记录 | `bump_version.py` 封版 |

**禁止**：在 `pyproject.toml` 中使用 `dynamic = ["version"]` 动态读取，因为 About API 需要静态字符串便于运行时反射。

## 3. 何时 bump

### 必须 bump 的场景

- 合并新功能到 `main` 分支（MINOR）
- 合并 Bug 修复到 `main` 分支（PATCH）
- 合并破坏性变更到 `main` 分支（MAJOR）
- 发布前（确保 `__version__` 与 CHANGELOG 一致）

### 不需要 bump 的场景

- 文档更新（README、注释）
- 测试用例补充
- 开发分支日常提交
- 重构不改变行为

### 何时使用哪种 bump

| 场景 | bump 类型 | 示例 |
|---|---|---|
| 新增 API 端点 | MINOR | `/api/about/check-update` |
| 新增前端页面 | MINOR | About 菜单 |
| 新增配置项（向后兼容） | MINOR | 任务级覆盖 |
| 修复 Bug | PATCH | `_is_newer` 保守策略 |
| 性能优化 | PATCH | COUNT 查询合并 |
| 删除 API 端点 | MAJOR | 移除 `/api/old` |
| 修改 API 响应结构 | MAJOR | `{"detail"}` → `{"message"}` |
| 升级 Python 最低版本 | MAJOR | `>=3.10` → `>=3.12` |

## 4. bump_version.py 用法

```powershell
# 自动判断（根据 git log，保守策略，默认 patch）
python scripts/bump_version.py auto

# 显式指定
python scripts/bump_version.py minor       # 0.2.0 → 0.3.0
python scripts/bump_version.py patch       # 0.2.0 → 0.2.1
python scripts/bump_version.py major       # 0.2.0 → 1.0.0

# 直接指定版本号（必须大于当前版本）
python scripts/bump_version.py 1.0.0

# 同时创建 git tag
python scripts/bump_version.py minor --tag
```

**脚本行为**：
1. 读取当前版本（`__init__.py`）
2. 计算新版本号
3. 更新 `__init__.py`、`pyproject.toml`、`CHANGELOG.md`
4. 重新生成 `_build_info.py`
5. 可选创建 git tag（`--tag`）

**幂等性**：重复运行相同版本号不会产生重复段落或链接。

**退出码**：
- `0` 成功
- `1` 参数错误 / 版本号格式无效
- `2` 文件读写错误
- `3` git 操作失败（非致命，仅警告）

## 5. CHANGELOG 维护规范

### 日常积累（开发阶段）

每次合并 PR 或提交重要变更时，在 `CHANGELOG.md` 的 `[Unreleased]` 段落下记录：

```markdown
## [Unreleased]

### Added
- **新功能名称**：简短描述。

### Changed
- **变更名称**：简短描述。

### Fixed
- **修复名称**：简短描述。

### Security
- **安全修复**：简短描述。
```

### 封版（发布阶段）

运行 `bump_version.py` 时，脚本会：
1. 把 `[Unreleased]` 段落"封版"为 `[新版本] - 日期`
2. 更新链接区

**封版前**：开发者应确保 `[Unreleased]` 的内容已归类到对应版本段落。如果 `[Unreleased]` 仍有未发布的内容，应在封版前清空或移动到新版本段落。

### 段落分类

| 段落 | 用途 |
|---|---|
| `Added` | 新功能 |
| `Changed` | 已有功能的变更（非破坏性） |
| `Deprecated` | 即将移除的功能 |
| `Removed` | 已移除的功能（破坏性） |
| `Fixed` | Bug 修复 |
| `Security` | 安全修复 |
| `Compatibility` | 兼容性信息（Python/Node/浏览器版本要求） |

## 6. Git Tag 工作流

### 创建 tag

```powershell
# 方式 1：bump_version.py 自动创建
python scripts/bump_version.py minor --tag

# 方式 2：手动创建
git tag -a v0.2.0 -m "Release 0.2.0"
```

**tag 格式**：`v` 前缀 + 版本号（如 `v0.2.0`）。GitHub Releases 按 `v` 前缀识别 tag。

### 推送 tag

```powershell
git push origin v0.2.0
# 或推送所有 tag
git push origin --tags
```

### 发布 GitHub Release

1. 推送 tag 后，访问 https://github.com/wangnan05563/xianyu-hunter/releases/new
2. 选择刚推送的 tag
3. 标题填 `v0.2.0`
4. 描述从 `CHANGELOG.md` 的 `[0.2.0]` 段落复制
5. 发布

发布后，`/api/about/check-update` 会在 5 分钟内检测到新版本（缓存 TTL）。

## 7. 发布流程

### 标准发布流程

1. **准备**：确保所有变更已合并到 `main` 分支，测试通过
2. **更新 CHANGELOG**：把 `[Unreleased]` 的内容归类，确保完整
3. **bump 版本号**：
   ```powershell
   python scripts/bump_version.py minor --tag
   ```
4. **提交变更**：
   ```powershell
   git add src/xianyu_hunter/__init__.py pyproject.toml CHANGELOG.md src/xianyu_hunter/_build_info.py
   git commit -m "chore(release): v0.2.0"
   ```
5. **推送 commit 与 tag**：
   ```powershell
   git push origin main
   git push origin v0.2.0
   ```
6. **发布 GitHub Release**：在 GitHub 网页创建 Release，描述从 CHANGELOG 复制
7. **验证**：About 页面检查更新，确认新版本可被检测到

### 紧急修复发布流程（hotfix）

1. 从 `main` 创建 hotfix 分支：`git checkout -b hotfix/0.2.1 main`
2. 修复 Bug
3. 更新 CHANGELOG（`[Unreleased]` 或新建 `[0.2.1]` 段落）
4. bump patch：`python scripts/bump_version.py patch --tag`
5. 提交、推送、发布 Release

## 8. 自动化集成（可选）

未来可考虑通过 GitHub Actions 实现：

- **PR 合并时**：自动在 `[Unreleased]` 追加条目（根据 commit message 解析）
- **tag 推送时**：自动创建 GitHub Release（从 CHANGELOG 提取描述）
- **定时检查**：提醒 `[Unreleased]` 积累过多条目，建议发布

当前阶段为手动流程，避免过度自动化引入复杂度。

## 9. 相关文件

| 文件 | 作用 |
|---|---|
| `src/xianyu_hunter/__init__.py` | 版本号源头（`__version__`） |
| `pyproject.toml` | 打包元数据（`version` 字段同步） |
| `src/xianyu_hunter/_build_info.py` | 构建信息（自动生成，About API 读取） |
| `scripts/build_info.py` | 生成 `_build_info.py` 的脚本 |
| `scripts/bump_version.py` | 版本号递增与同步脚本 |
| `CHANGELOG.md` | 变更记录 |
| `VERSIONING.md` | 本文档 |

## 10. 常见问题

**Q: 为什么 `pyproject.toml` 不用 `dynamic = ["version"]`？**
A: About API 需要在运行时反射读取 `__version__`，动态读取会增加复杂度且不利于离线构建。静态字符串更简单可靠。

**Q: 为什么不用 `bumpversion` / `bump2version`？**
A: 项目仅需同步 2 个文件 + CHANGELOG，标准库即可完成。引入额外依赖会增加安装负担，且 `bumpversion` 不支持 CHANGELOG 改写的定制逻辑。

**Q: `auto` 模式可靠吗？**
A: `auto` 模式根据 git commit message 判断 bump 类型，采用保守策略（默认 patch）。建议在重要发布时显式指定 `minor` 或 `patch`，避免误判。

**Q: 忘记 bump 版本号怎么办？**
A: About 页面的检查更新功能会对比 GitHub Releases 与本地 `__version__`。如果忘记 bump，本地版本会显示为旧版本，用户会看到"有更新"提示（即使本地已是最新代码）。补救方法：立即运行 `bump_version.py` 并发布 Release。
