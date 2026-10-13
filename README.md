# XianyuHunter

![backend tests](https://img.shields.io/badge/backend%20tests-1864%20passed-brightgreen)
![frontend tests](https://img.shields.io/badge/frontend%20tests-286%20passed-brightgreen)
![python](https://img.shields.io/badge/python-3.10%2B-blue)
![fastapi](https://img.shields.io/badge/FastAPI-0.110%2B-009485)
![react](https://img.shields.io/badge/React-18.3-61dafb)
![platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![license](https://img.shields.io/badge/license-MIT-green)

闲鱼（[goofish.com](https://www.goofish.com)）自动捡漏与抢单系统（个人辅助）。

通过浏览器自动化监控关键词商品，经过增量去重与多维卖家评估后，按策略自动下单或推送通知；
配套一套 React 单页控制台，可在浏览器中管理任务、查看商品与订单、调整配置，并内置基于
RAG 的智能客服。

> ⚠️ **风险免责（必读）**：本工具通过浏览器自动化访问闲鱼，**可能违反平台用户协议并导致账号封禁/限制**。
> 请仅用于个人研究学习，保持低频使用、单一账号、对自己经手的商品负责。
> 开发者不对因使用本工具造成的任何损失（账号封禁、财产损失、纠纷等）承担责任。

## 特性

**核心链路**

- 关键词搜索 + 价格区间过滤
- 增量去重（已抓取过的商品不再重复评估）
- 卖方多维评估（职业度 / 信用 / 纠纷 / 价格异动）
- 自动下单，带价格容差校验
- 多任务调度：按 `interval_seconds` 循环，支持 start / pause / resume / stop
- 四种执行模式：`auto` / `semi_auto` / `confirm` / `notify`

**风控与稳定性**

- 反爬对抗：QPS 限速、类人操作间隔、浏览器指纹伪装、请求频率伪装、代理池
- 风控（WAF）感知：检测到拦截后主动暂停，避免账号进一步受限
- Cookie 分层轮换与健康管理：登录态自动续期、运行时令牌刷新、健康状态评估

**多账号**

- 多账号管理、账号切换与轮换
- 每账号独立的浏览器档案（profile）与登录态

**通知**

- 三渠道推送：Server酱 / PushPlus / Bark
- 多渠道并发推送 + 指数退避重试

**Web 控制台（React SPA，支持 PWA 安装）**

- 仪表盘、商品查看、订单、评估明细、时间线、价格行情、日志
- 任务管理、配置管理、系统维护、菜单管理、导出、帮助、关于
- 实时搜索 / 批量采集（依赖后端浏览器实例）
- 智能客服：基于 RAG 的知识库问答（本地向量库 + 中文 Embedding）

**远程访问与交付**

- 内网穿透隧道集成（cloudflared / cpolar），便于外网访问本地控制台
- Windows 桌面打包：PyInstaller 生成单目录 EXE + Inno Setup 安装包 + 系统托盘

## 技术栈

| 层次 | 技术 |
|------|------|
| 后端 | Python 3.10+ · FastAPI · Uvicorn · Typer · Pydantic v2 · SQLAlchemy 2.0 / SQLite · APScheduler · loguru |
| 浏览器自动化 | Playwright（Chromium） |
| 数据 / 安全 | Keyring（Windows DPAPI）· cryptography（Chrome Cookie 解密）· tenacity（重试） |
| 智能客服 | ChromaDB + sentence-transformers（本地中文 Embedding） |
| 前端 | React 18 · TypeScript · Vite 5 · Ant Design 5 · ECharts · Zustand · React Router 6 · PWA |

## 安装

```powershell
# 克隆仓库
git clone <this-repo> xianyu_hunter
cd xianyu_hunter

# 创建并激活虚拟环境
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 安装依赖
pip install -r requirements.txt

# 安装 Playwright Chromium
playwright install chromium
```

前端（仅在需要自行构建控制台界面时）：

```powershell
cd frontend
npm install
npm run build
```

## 快速开始

### 1. 配置推送 Key

推送 Key 不写入 `config.yaml`，而是加密保存到系统 keyring（Windows DPAPI），
运行时由 `secrets.get_secret()` 解密。

```powershell
# 复制环境变量模板
copy .env.example .env
# 编辑 .env 填入 SCT_KEY / PUSHPLUS_TOKEN / BARK_KEY（按需）
```

> 💡 也可在 Web 控制台设置页交互式写入。

### 2. 编辑配置

`config/config.yaml` 是默认配置（运行时也可在 Web 控制台修改）：

```yaml
antidetect:
  qps: 1.5                # 限速：每秒最多 1.5 个请求
  min_delay_ms: 1500      # 页面操作最小间隔
  max_delay_ms: 5000
  fail_pause_threshold: 5 # 连续失败 N 次暂停 5 分钟
  fail_window_sec: 300

notifier:
  channels:
    serverchan: true
    pushplus: false
    bark: false
  default_channels: [serverchan]
```

`config/eval.yaml` 控制卖家评估阈值与权重。

### 3. 首次登录

首次使用需登录闲鱼，登录态持久化到 `data/browser-data/`，下次启动自动恢复。

```powershell
python -m xianyu_hunter login
# 弹出 Chromium，手动扫码登录
```

### 4. CLI 命令

```powershell
# 新增监控任务
python -m xianyu_hunter add --keyword "iPhone 13" --min-price 1500 --max-price 2500 --mode auto

# 列出所有任务
python -m xianyu_hunter list

# 启动调度器（启动所有 RUNNING 任务）
python -m xianyu_hunter run

# 启动单个任务
python -m xianyu_hunter run t1

# 任务控制
python -m xianyu_hunter pause t1
python -m xianyu_hunter resume t1
python -m xianyu_hunter stop t1

# 查看任务状态
python -m xianyu_hunter status            # 全部
python -m xianyu_hunter status t1         # 单个

# 查看当前配置
python -m xianyu_hunter config-show
```

执行模式（`--mode`）：

| 模式 | 行为 |
|------|------|
| `auto` | 评估通过 → 立即自动抢单 |
| `semi_auto` | 评估通过 → 推送通知 → 人工确认后下单 |
| `confirm` | 评估通过 → 推送通知 → 不自动抢单（默认，保守） |
| `notify` | 仅推送，不评估、不抢单 |

### 5. 启动 Web 控制台

```powershell
# 方式一：项目自带脚本（Web + 调度器，含浏览器实例）
scripts\启动服务.bat

# 方式二：直接调用 CLI
python -m xianyu_hunter web
```

启动后访问：

- 控制台：`http://127.0.0.1:8001/xianyu`
- API 文档：`http://127.0.0.1:8001/api/docs`

`web` 常用参数：`--host`（默认 `127.0.0.1`）、`--port`（默认 `8001`）、
`--reload`（开发模式热重载）、`--with-scheduler`、`--workers`。

> ⚠️ 控制台入口固定为 `/xianyu` 子路径。直接访问 `/` 会返回页面但路由无法匹配，导致空白页。

## 配置

| 文件 | 说明 |
|------|------|
| `config/config.yaml` | 主配置（反爬限速 / 推送渠道等，运行时可被控制台修改） |
| `config/eval.yaml` | 卖家评估阈值与权重 |
| `config/menu_registry.yaml` | 控制台菜单注册表 |
| `config/param_rules.yaml` | 参数校验规则 |
| `config/*.example.yaml` | 配置模板（供新部署参考） |
| `.env` | 环境变量（推送 Key 等，从 `.env.example` 复制） |

## 架构

```
CLI / Web (FastAPI)
   └─→ Container (DI)
        ├─ BrowserManager          ← Playwright + stealth
        ├─ AntiDetect              ← QPS + 类人行为 + 指纹/频率伪装
        ├─ Repository              ← SQLite
        ├─ EventBus                ← asyncio.Queue
        ├─ Collector               ← 搜索 / 详情 / 卖家
        ├─ Dedup                   ← 增量去重
        ├─ PriceStrategy           ← 价格过滤
        ├─ Evaluator               ← 多维评估
        ├─ Buyer                   ← 自动下单
        ├─ NotifierHub             ← 多渠道推送
        ├─ CookieRotator           ← 登录态分层轮换 / 健康管理
        ├─ AccountRotator          ← 多账号轮换
        ├─ Chatbot                 ← 知识库问答（RAG）
        ├─ TunnelService           ← 内网穿透（cloudflared / cpolar）
        └─ TaskScheduler           ← 多任务调度
             └─ TaskWorker (one per Task)
```

数据流：`搜索 → 去重 → 详情 → 价格 → 评估 → 下单 / 通知`。

事件由 `EventBus` 解耦：Buyer 发布 `BUY_SUCCEEDED`，NotifierHub 订阅并消费。

## 目录结构

```
17_xianyu/
├── backend/xianyu_hunter/      # Python 后端源码（主包）
│   ├── domain/                 # 领域模型（item / order / seller / task / events）
│   ├── infra/                  # 基础设施（db / browser / logger / secrets / repository）
│   ├── modules/                # 业务模块（collector / evaluator / buyer / notifier /
│   │                           #   scheduler / anti_detect / cookie_rotator / chatbot / …）
│   ├── web/                    # FastAPI Web 层（routes / services / static）
│   ├── __main__.py             # CLI 入口（typer）
│   ├── config.py               # 配置加载（pydantic-settings）
│   └── container.py            # 依赖注入容器
├── frontend/                   # React + TypeScript 前端（Vite）
│   ├── src/                    # 前端源码（api / components / pages / stores）
│   └── public/                 # 静态资源与 PWA 图标
├── config/                     # 配置文件（config / eval / menu_registry / param_rules）
├── tests/                      # 后端测试（pytest）
├── scripts/                    # 启动 / 构建 / 部署脚本（.bat / .ps1 / .py）
├── docs/                       # 项目文档（需求 / 设计 / 迭代记录）
├── assets/                     # 品牌资源（应用图标 / GitHub 社交预览图）
├── data/                       # 运行时数据（SQLite / 浏览器档案 / 日志，gitignore）
├── pyproject.toml              # Python 项目配置
├── requirements.txt            # Python 依赖
└── installer.iss               # Inno Setup 安装包脚本
```

## 测试

后端：

```powershell
$env:PYTHONPATH = "backend"
python -m pytest tests/ -v
```

当前后端测试：**1864** 个用例，全部通过（约 8–9 分钟，含覆盖率统计）。

前端：

```powershell
cd frontend
npm run test      # vitest run
```

当前前端测试：**286** 个用例（30 个测试文件）。

## 数据与日志

| 路径 | 说明 |
|------|------|
| `data/xianyu.db` | SQLite（任务 / 商品 / 卖家 / 评估 / 订单 / 事件） |
| `data/browser-data/` | 浏览器 user data dir（登录态） |
| `data/logs/*.log` | loguru 滚动日志 |
| `data/screenshots/` | 失败截图（如有） |

## 桌面应用打包

```powershell
# 前端构建 → PyInstaller 打包 → Inno Setup 安装包
scripts\构建打包.bat
```

产物为 Windows 单目录 EXE（`release/xianyu-hunter/`）与 Inno Setup 安装包。
安装包可选启用系统托盘（依赖 `pystray` + `pillow`）。

## 已知限制

1. **不支持云控验证码**：首次登录需人工；运行时若触发滑块会失败，并由风控模块暂停
2. **抢单窗口短**：详情页"立即购买"按钮从出现到消失通常 < 30 秒，对网络延迟敏感
3. **选择器需维护**：闲鱼侧风控更新后部分选择器可能失效，需更新 `infra/selectors.py`
4. **平台为 Windows**：登录态加密（DPAPI）、启动脚本与安装包均面向 Windows

## 风险与免责

1. **违反平台 ToS 风险**：本工具不伪装身份，但自动化访问行为可能违反闲鱼《用户协议》
2. **账号封禁风险**：高频访问 / 重复操作可能被识别并导致账号功能受限或封禁
3. **风控升级风险**：闲鱼侧持续更新反爬策略，本工具可能随时失效
4. **财产风险**：抢单虽设价格容差校验，仍可能因页面 / 网络延迟导致错价，作者不对任何交易结果负责
5. **数据合规**：本工具仅在本地运行，不上传任何数据到第三方

**使用本工具即视为同意**：仅限个人学习 / 研究使用，自担一切风险。

## 贡献

欢迎提交 Issue 与 Pull Request。提交前请确保：

1. 后端测试通过：`python -m pytest tests/`
2. 前端测试通过：`cd frontend && npm run test`
3. 前端类型检查与构建无错误：`cd frontend && npm run build`

## 许可证

[MIT](LICENSE)

## 致谢

感谢 [Playwright](https://playwright.dev/)、[FastAPI](https://fastapi.tiangolo.com/)、
[React](https://react.dev/)、[Ant Design](https://ant.design/)、
[ChromaDB](https://www.trychroma.com/) 等开源项目。
