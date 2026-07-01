# 项目目录结构规范

本文档定义 XianyuHunter 项目的目录组织规范，指导团队成员正确存放文件。

## 一、目录结构总览

```
17_xianyu/
├── src/xianyu_hunter/   # Python 后端源码（主包，不可移动）
├── frontend/            # React 前端源码（不可移动）
├── config/              # 配置文件（不可移动，代码硬编码引用）
├── tests/               # 测试代码（不可移动，pyproject.toml 配置）
├── scripts/             # 启动/构建/部署脚本
├── docs/                # 项目文档
├── data/                # 运行时数据（gitignore）
├── browser-data/        # 浏览器用户数据（gitignore）
├── logs/                # 启动脚本日志/PID（gitignore）
├── .env / .env.example  # 环境变量
├── 静默启动.vbs          # 根目录快捷启动入口
├── pyproject.toml       # Python 项目配置
├── requirements.txt     # Python 依赖
├── Dockerfile           # Docker 镜像构建
└── docker-compose.yml   # Docker Compose 部署
```

## 二、各目录用途与规则

### 2.1 `src/xianyu_hunter/` — 后端源码

Python 主包，通过 `pyproject.toml` 的 `[tool.setuptools.packages.find]` 发现。

| 子目录 | 用途 | 命名规范 |
|--------|------|----------|
| `domain/` | 领域模型（纯数据类，无副作用） | `snake_case.py` |
| `infra/` | 基础设施（DB、浏览器、日志、密钥、仓储） | `snake_case.py`，仓储以 `repo_` 前缀 |
| `modules/` | 业务模块（采集器、通知器、买家、评估器等） | `snake_case.py` |
| `web/routes/` | FastAPI 路由 | `api_*.py` |
| `web/services/` | Web 服务层 | `snake_case.py` |
| `web/templates/` | Jinja2 模板 | `snake_case.html` |
| `web/static/` | 静态资源 | 按类型分子目录 |

**规则：**
- 不可移动此目录，代码中 `import xianyu_hunter` 依赖此路径
- 新增模块按职责归入 `domain/`、`infra/`、`modules/`、`web/` 之一
- 目录嵌套不超过 4 层

### 2.2 `frontend/` — 前端源码

React + TypeScript + Vite 项目。

| 子目录 | 用途 |
|--------|------|
| `src/api/` | API 客户端 |
| `src/components/` | 通用组件（按类型分子目录） |
| `src/pages/` | 页面组件（按业务模块分子目录） |
| `src/stores/` | 状态管理 |
| `src/constants/` | 常量定义 |

**规则：**
- 构建产物输出到 `src/xianyu_hunter/web/static/spa/`（由 `vite.config.ts` 配置）
- 不可移动此目录，`重新构建.bat` 依赖此路径

### 2.3 `config/` — 配置文件

YAML 配置文件目录，代码中 `Path("config")` 硬编码引用。

| 文件 | 用途 |
|------|------|
| `config.yaml` | 主配置（运行时可被 Web UI 修改） |
| `eval.yaml` | 卖家评估配置 |
| `config.example.yaml` | 主配置模板（供新部署参考） |
| `eval.example.yaml` | 评估配置模板 |
| `backups/` | 配置自动备份（gitignore，保留 10 个） |

**规则：**
- 不可移动此目录，`yaml_config.py` 和 `api_config.py` 硬编码引用
- 新增配置文件需同步提供 `.example.yaml` 模板
- 敏感字段（推送 Key）通过 `.env` 或 keyring 配置，不写入 YAML

### 2.4 `tests/` — 测试代码

| 文件模式 | 用途 |
|----------|------|
| `test_*.py` | 单元测试 / 集成测试 |
| `test_e2e.py` | 端到端测试 |
| `conftest.py` | pytest 公共 fixture |

**规则：**
- 不可移动此目录，`pyproject.toml` 的 `testpaths = ["tests"]` 配置
- 测试文件命名：`test_<被测模块名>.py`
- 运行：`$env:PYTHONPATH = "src"; python -m pytest tests/ -v`

### 2.5 `scripts/` — 脚本目录

启动、构建、部署相关脚本集中管理。

| 文件 | 用途 |
|------|------|
| `启动服务.bat` | 启动 Web + 调度器 |
| `停止服务.bat` | 停止服务 |
| `重新构建.bat` | 前端构建 |
| `静默启动.vbs` | 静默启动（无黑框，含健康检查） |
| `auth_helper.py` | 认证辅助 |
| `browser_login.py` | 浏览器登录 |
| `extract_xianyu_cookie.py` | Cookie 提取 |

**规则：**
- `.bat` 脚本首行使用 `cd /d "%~dp0.."` 回到项目根目录
- 根目录保留 `静默启动.vbs` 作为快捷入口，调用 `scripts/静默启动.vbs`
- 临时调试脚本以 `_` 开头放根目录（会被 gitignore）

### 2.6 `docs/` — 项目文档

| 文件 | 用途 |
|------|------|
| `requirements.md` | 需求规格 |
| `design.md` | 技术设计 |
| `directory-structure.md` | 本文档 |
| `sprint-*.md` | 迭代记录 |
| `plans/` | 计划文档 |

### 2.7 `data/` — 运行时数据（gitignore）

| 子路径 | 用途 |
|--------|------|
| `xianyu.db` | SQLite 数据库 |
| `logs/` | loguru 日志（按日滚动，保留 14 天） |
| `prompts/` | AI Prompt 文件 |
| `cookies.json` | Cookie 存储 |
| `.gitkeep` | 占位文件（唯一被版本控制的文件） |

**规则：**
- 不可移动此目录，代码中 `Path("data/...")` 硬编码引用
- Docker 部署时挂载为 volume（`./data:/app/data`）

### 2.8 `browser-data/` — 浏览器数据（gitignore）

Playwright 用户数据目录，存储登录态和 Cookie。

**规则：**
- 不可移动，`config.yaml` 中 `user_data_dir: ./browser-data` 引用
- 首次登录后生成，删除后需重新登录

### 2.9 `logs/` — 启动脚本日志（gitignore）

| 文件 | 用途 |
|------|------|
| `web.pid` | Web 服务器 PID（停止服务用） |
| `startup.log` | VBS 启动日志 |
| `web.log` / `web.err` | 提示性日志文件名 |

**规则：**
- 与 `data/logs/` 不同：此目录存放启动脚本相关文件
- 应用日志在 `data/logs/`（loguru），SSE 日志流在根目录 `run.stdout.log`

## 三、文件命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| Python 文件 | `snake_case.py` | `price_strategy.py` |
| Python 测试 | `test_*.py` | `test_collector.py` |
| TypeScript 文件 | `camelCase.ts` / `PascalCase.tsx` | `itemList.ts` / `MainLayout.tsx` |
| 配置文件 | `kebab-case.yaml` | `config.yaml` |
| 配置模板 | `*.example.yaml` | `config.example.yaml` |
| 路由文件 | `api_*.py` | `api_items.py` |
| 仓储文件 | `repo_*.py` | `repo_items.py` |
| 文档文件 | `kebab-case.md` | `directory-structure.md` |

## 四、版本控制规则

### 4.1 纳入版本控制

- 所有源码（`src/`、`frontend/src/`）
- 测试代码（`tests/`）
- 配置模板（`*.example.yaml`、`.env.example`）
- 文档（`docs/`）
- 脚本（`scripts/`）
- 项目配置（`pyproject.toml`、`Dockerfile` 等）
- `data/.gitkeep`（占位）

### 4.2 排除版本控制

- 运行时数据（`data/`、`browser-data/`、`logs/`）
- 数据库文件（`*.db`、`*.db-*`）
- 日志文件（`*.log`、`*.out`、`*.err`）
- 敏感配置（`.env`）
- 依赖目录（`.venv/`、`node_modules/`）
- 构建产物（`src/xianyu_hunter/web/static/spa/`）
- 配置备份（`config/backups/`）
- IDE 配置（`.idea/`、`.vscode/`）

## 五、目录变更流程

1. **评估影响**：检查代码中是否有硬编码路径引用（`Path("...")`）
2. **更新引用**：修改所有引用旧路径的代码
3. **更新配置**：修改 `pyproject.toml`、`vite.config.ts`、`Dockerfile` 等
4. **运行测试**：`python -m pytest tests/ -v` 确保全部通过
5. **更新文档**：同步更新本规范和 README

## 六、本次结构变更记录（2026-06-23）

### 变更内容

| 变更 | 说明 |
|------|------|
| 清理根目录临时文件 | 删除 `verify_*.py`、`test_pw*.py`、`_test_delete.py` 等临时调试文件 |
| 集中启动脚本 | `启动服务.bat`、`停止服务.bat`、`重新构建.bat`、`静默启动.vbs` 移至 `scripts/` |
| 根目录快捷入口 | 根目录 `静默启动.vbs` 改为快捷入口，调用 `scripts/静默启动.vbs` |
| 配置模板化 | 新增 `config/config.example.yaml`、`config/eval.example.yaml` |
| .gitignore 优化 | 按类别分组，添加显式运行时日志规则 |

### 路径变更对照

| 旧路径 | 新路径 |
|--------|--------|
| `启动服务.bat` | `scripts/启动服务.bat` |
| `停止服务.bat` | `scripts/停止服务.bat` |
| `重新构建.bat` | `scripts/重新构建.bat` |
| `静默启动.vbs`（完整版） | `scripts/静默启动.vbs` |
| `静默启动.vbs`（快捷入口） | `静默启动.vbs`（根目录，调用 scripts 版） |

### 未变更的目录（硬编码引用，不可移动）

- `src/xianyu_hunter/` — `pyproject.toml` packages.find
- `config/` — `yaml_config.py` `Path("config")`
- `data/` — `container.py`、`logger.py`、`api_maintenance.py` 等多处 `Path("data/...")`
- `browser-data/` — `browser.py`、`config.yaml` `./browser-data`
- `frontend/` — `重新构建.bat`、`vite.config.ts`
- `tests/` — `pyproject.toml` testpaths

---

## 七、文件分类判断标准（2026-06-30 补充）

本节明确"什么样的文件该放在哪里"，作为添加新文件时的判定依据。

### 7.1 根目录仅允许以下文件

| 类别 | 文件 | 说明 |
|---|---|---|
| 工具配置 | `.gitignore` / `.dockerignore` / `.env.example` / `.pre-commit-config.yaml` | 工具链相关 |
| 构建/依赖 | `Dockerfile` / `docker-compose.yml` / `pyproject.toml` / `requirements.txt` | 项目构建 |
| 元文档 | `README.md` / `CHANGELOG.md` / `VERSIONING.md` | 仓库根级文档 |
| 启动入口 | `静默启动.vbs` | **唯一**根目录脚本，作为包装器跳转至 `scripts/静默启动.vbs` |

### 7.2 脚本类文件（必须放 `scripts/`）

凡是 `.py` / `.sh` / `.js` / `.ps1` / `.bat` / `.vbs` 后缀的可执行脚本，
**必须** 位于 `scripts/` 下。命名风格：

- **Python 工具脚本**：`snake_case.py`（如 `auth_helper.py`）
- **Shell / 批处理**：中文命名更友好（如 `启动服务.bat`），便于双击启动
- **PowerShell**：`snake_case.ps1`（如 `setup-env.ps1`）
- **VBS 启动器**：`静默启动.vbs`（被根目录包装器调用）

子目录：

- `scripts/tests/`：用于 `scripts/` 下脚本的单元/集成测试（镜像 pytest 模式）

### 7.3 文档归档（`.md`）

| 位置 | 用途 |
|---|---|
| 根目录 `*.md` | 仅 README / CHANGELOG / VERSIONING |
| `docs/README.md` | 文档目录索引 |
| `docs/01-仪表盘/` ~ `docs/07-移动端/` | 各功能模块的详细设计 |
| `docs/archive/` | 过期文档（sprint 报告、已废弃设计） |
| `docs/requirements/` | 需求规格、评审报告 |
| `docs/standards/` | 规范文档（部署、设计系统、目录结构） |
| `docs/04-系统维护/sonar-reports/` | SonarQube 报告存档 |

**禁止** 在 `docs/` 存放脚本文件、临时分析报告、截图。

### 7.4 配置文件（`.yaml` / `.yml` / `.env`）

| 类型 | 位置 | 版本控制 |
|---|---|---|
| 应用配置 | `config/config.yaml`、`config/eval.yaml` | ✅ 提交 |
| 配置模板 | `config/*.example.yaml` | ✅ 提交 |
| 环境变量 | `.env` | ❌ gitignore |
| 环境变量示例 | `.env.example` | ✅ 提交 |
| 数据库 / 向量库 | `data/*.db`、`data/chromadb/` | ❌ gitignore |
| 浏览器登录态 | `browser-data/` | ❌ gitignore |

### 7.5 日志与运行产物

| 类型 | 位置 | `.gitignore` |
|---|---|---|
| 应用运行日志 | `data/logs/`、`logs/` | ✅ |
| 服务标准输出 | 根目录 `run.stdout.log`、`run.stderr.log` | ✅ |
| pytest 缓存 | `.pytest_cache/`、`__pycache__/`、`*.pyc` | ✅ |
| SonarQube 缓存 | `.scannerwork/`、`sonar-results/`、`sonar-scan.log` | ✅ |
| 浏览器缓存 | `browser-data/Default/Cache/` | 运行时数据，清理时删除 |
| 前端构建 | `src/xianyu_hunter/web/static/spa/` | ✅ |
| 截图 | `tests/screenshots/`、`scripts/.screenshots/` | ✅ |

### 7.6 重定向误产物（必须拦截）

PowerShell 中 `command > filename` 会创建 `filename` 文件。常见误用：

```powershell
Get-Help less > 17_xianyu    # ❌ 创建了 less 帮助文本的垃圾文件
```

已在 `.gitignore` + `.pre-commit-config.yaml` 拦截：

```
/0
/17_xianyu
/17_xianyufrontend
/_r.json
/.tmp_diff.txt
/.s3358_lines.txt
/*.txtcd      # 异常命名后缀（如 test_result_*.txtcd 是错误输入）
```

### 7.7 添加新文件时的检查清单

在 `git add` 之前自检：

- [ ] 该文件是否应放根目录？（仅配置/构建/元文档/启动入口）
- [ ] 若是脚本，是否放在 `scripts/`？
- [ ] 若是运行时数据，是否已被 `.gitignore` 覆盖？
- [ ] 若是日志，是否输出到 `data/logs/` 或 `logs/`？
- [ ] 是否运行了 `pre-commit run --all-files`？
- [ ] 是否避开了常见的命名陷阱（如 `0`、`17_xianyu`、`_r.json`）？

---

## 八、第三轮整理变更记录（2026-06-30）

### 8.1 变更背景

第二轮清理后根目录又被运行时产物重建（Web 服务持续运行，定期生成日志、重定向产物）。
本次主动停止服务后系统化整理，识别了根目录的"游离文件"，并建立长期防复发机制。

### 8.2 清理动作

| 类别 | 数量 | 处理 |
|---|---|---|
| SonarQube 调试 PS1 脚本 | 11 | 删除（`check-scan*.ps1` / `diagnose-api.ps1` / `query-*.ps1` / `run-scan.ps1`） |
| 临时调试 Python 脚本 | 2 | 删除（`_debug_orders.py` / `_tmp_check_title.py`） |
| 根目录测试输出 | 5 | 删除（`pytest_output.txt` 等 4 个 + 异常名 `test_result_task_editor.txtcd`） |
| 误重定向产物 | 2 | 删除（`17_xianyu` / `17_xianyufrontend`，含 less 帮助文本） |
| 运行日志 | 1 | 删除（`run.stdout.log` 2.37 MB） |
| SonarQube 报告 | 2 | 移动至 `docs/04-系统维护/sonar-reports/` |
| SonarQube 缓存 | 2 目录 | 删除（`.scannerwork/` 6.80 MB + `sonar-results/` 16.25 MB） |
| pytest 缓存 | 1 目录 | 删除（`.pytest_cache/`） |

### 8.3 新增内容

| 路径 | 用途 |
|---|---|
| `scripts/静默启动.vbs` | 真实启动器，被根目录包装器调用 |
| `docs/standards/directory-structure.md` 第七、八章 | 文件分类标准 + 本轮变更记录 |
| `.gitignore` 增补 | `sonar-results/` / `test-screenshots/` / `.uploads/` / `*.txtcd` |
| `.pre-commit-config.yaml` 增补 | 拦截 `sonar-results/` 等 |

### 8.4 根目录最终状态

清理后根目录仅剩 14 个核心文件，全部符合 7.1 节规范：

| 类别 | 文件 |
|---|---|
| 工具配置 | `.dockerignore` / `.env` / `.env.example` / `.gitignore` / `.pre-commit-config.yaml` |
| 构建/依赖 | `docker-compose.yml` / `Dockerfile` / `pyproject.toml` / `requirements.txt` / `sonar-project.properties` |
| 元文档 | `README.md` / `CHANGELOG.md` / `VERSIONING.md` |
| 启动入口 | `静默启动.vbs`（根目录唯一脚本，调用 `scripts/静默启动.vbs`） |

无任何游离的功能性文件。`scripts/` 目录下 16 个文件（`tests/test-setup-env.ps1` + 15 个脚本）全部为脚本类（.py / .ps1 / .bat / .vbs）。

---

## 九、第四轮整理变更记录（2026-06-30 续）

### 9.1 变更背景

第三轮清理后服务又运行了一段时间，根目录再次被运行产物污染。
本次主动检查时发现 18 个游离文件，集中清理后验证应用完整性。

### 9.2 本轮清理动作

| 类别 | 数量 | 处理 |
|---|---|---|
| SonarQube 调试 PS1 脚本 | 11 | 删除（`check-scan*.ps1` / `diagnose-api.ps1` / `query-*.ps1` / `run-scan.ps1`） |
| 临时调试 PS1 脚本 | 1 | 移动至 `scripts/check-tmp.ps1`（保留以备复现 Sonar 临时目录权限问题） |
| 测试输出 txt | 4 | 删除（`pytest_output.txt` / `pytest_result.txt` / `test_debug_output.txt` / `test_result.txt`） |
| 误重定向产物 | 2 | 删除（`17_xianyu` / `17_xianyufrontend`） |
| SonarQube 报告副本 | 2 | 删除（与 `docs/04-系统维护/sonar-reports/` 下的副本 hash 相同，根目录副本冗余） |
| 异常名后缀 | 1 | 删除（`test_result_task_editor.txtcd`，`.txtcd` 是错误输入后缀） |
| 临时 diff 文件 | 1 | 删除（`.tmp_diff.txt` / `.s3358_lines.txt`） |

### 9.3 验证结果

- ✅ 核心模块全部可导入：`xianyu_hunter` / `config` / `container` / `web.app`
- ✅ 根目录严格 14 个核心文件，无游离功能文件
- ✅ `scripts/` 目录仅含脚本类文件（.py / .ps1 / .bat / .vbs）
- ✅ `docs/standards/directory-structure.md` 持续更新本轮变更记录
