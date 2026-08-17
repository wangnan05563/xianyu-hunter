# XianyuHunter

闲鱼（[goofish.com](https://www.goofish.com)）自动捡漏与抢单工具（个人辅助）。本仓库完整实现已通过 **148/148** 单元测试 + E2E 联通测试。

> ⚠️ **风险免责（必读）**：本工具通过浏览器自动化访问闲鱼，**可能违反平台用户协议并导致账号封禁/限制**。请仅用于个人研究学习、且对低频使用、单一账号、自用商品负责。开发者不对因使用本工具造成的任何损失（账号封禁、财产损失、纠纷等）承担责任。

## 文档

- [需求规格](docs/requirements.md) — 业务目标与功能清单
- [技术设计](docs/design.md) — 架构、模块依赖、关键决策

## 核心能力

- 关键词搜索 + 价格区间过滤
- 4 维卖家评估（职业度 / 信用 / 纠纷 / 价格异动）
- 增量去重（已抓过的商品不再评估）
- 自动点击"立即购买" + 价格容差校验
- 落单推送（Server酱 / PushPlus / Bark，3 渠道并发 + 指数退避重试）
- 多任务调度（按 `interval_seconds` 循环 + start/pause/resume/stop 控制）
- 风险感知（`Xianyu WAF` 检测到时主动暂停避免封号）

## 快速开始

### 1. 安装

```powershell
# 克隆仓库
git clone <this-repo> xianyu_hunter
cd xianyu_hunter

# 创建虚拟环境
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 安装依赖
pip install -r requirements.txt

# 安装 Playwright Chromium
playwright install chromium
```

### 2. 配置推送 Key

推送 Key 不会写入 `config.yaml`，而是加密存到系统 keyring（Windows DPAPI），运行时由 `secrets.get_secret()` 解密。

```powershell
# 复制环境变量模板
copy .env.example .env
# 编辑 .env 填入 SCT_KEY / PUSHPLUS_TOKEN / BARK_KEY（按需）
```

> 💡 实际使用中可通过 `secrets.set_secret(KEY_SERVERCHAN, "SCT...")` 在首次启动时交互式写入。

### 3. 编辑配置

`config/config.yaml` 是默认配置，可按需修改：

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

### 4. 首次登录

首次使用需要登录闲鱼。登录态会持久化到 `data/browser_data/`，下次启动自动恢复。

```powershell
python -m xianyu_hunter login
# 弹出 Chromium，手动扫码登录
```

### 5. CLI 命令

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
| `semi_auto` | 评估通过 → 推送通知 → 人工确认（**计划中**） |
| `confirm` | 评估通过 → 推送通知 → 不抢单（默认保守） |
| `notify` | 仅推送，不评估、不抢单 |

## 测试

```powershell
$env:PYTHONPATH = "backend"
python -m pytest tests/ -v
```

当前测试覆盖：148 个测试用例，含 4 个 E2E 联通测试，**全部通过**。

## 架构

```
CLI (__main__.py)
   └─→ Container (DI)
        ├─ BrowserManager          ← Playwright + stealth
        ├─ AntiDetect              ← QPS + 人类行为
        ├─ Repository              ← SQLite
        ├─ EventBus                ← asyncio.Queue
        ├─ Collector               ← 搜索/详情/卖家
        ├─ Dedup                   ← 增量去重
        ├─ PriceStrategy           ← 价格过滤
        ├─ Evaluator               ← 4 维评估
        ├─ Buyer                   ← 自动下单
        ├─ NotifierHub             ← 3 渠道推送
        └─ TaskScheduler           ← 多任务调度
             └─ TaskWorker (one per Task)
```

数据流：`搜索 → 去重 → 详情 → 价格 → 评估 → BUY_SUCCEEDED 事件 → NotifierHub 推送`

事件由 `EventBus` 解耦，Buyer 发布 `BUY_SUCCEEDED`，NotifierHub 订阅并消费。

## 目录结构

```
17_xianyu/
├── backend/xianyu_hunter/      # Python 后端源码（主包）
│   ├── domain/             # 领域模型（item/order/seller/task/events）
│   ├── infra/              # 基础设施（db/browser/logger/secrets/repository）
│   ├── modules/            # 业务模块（collector/notifier/buyer/evaluator/scheduler）
│   ├── web/                # FastAPI Web 层（routes/services/templates/static）
│   ├── __main__.py         # CLI 入口（typer）
│   ├── config.py           # .env 配置加载（pydantic-settings）
│   └── container.py        # 依赖注入容器
├── frontend/               # React + TypeScript 前端（Vite）
│   └── src/                # 前端源码（api/components/pages/stores）
├── config/                 # 配置文件目录
│   ├── config.yaml         # 主配置（运行时可被 Web UI 修改）
│   ├── eval.yaml           # 卖家评估配置
│   ├── *.example.yaml      # 配置模板（供新部署参考）
│   └── backups/            # 配置自动备份（gitignore）
├── tests/                  # 测试代码（148 个用例，含 E2E）
├── scripts/                # 启动/构建/部署脚本
│   ├── 启动服务.bat         # 启动 Web + 调度器
│   ├── 停止服务.bat         # 停止服务
│   ├── 重新构建.bat         # 前端构建
│   ├── 静默启动.vbs         # 静默启动（无黑框）
│   └── *.py                # 辅助脚本（cookie 提取等）
├── docs/                   # 项目文档（需求/设计/迭代记录）
├── data/                   # 运行时数据（gitignore，仅保留 .gitkeep）
│   ├── xianyu.db           # SQLite 数据库
│   ├── logs/               # loguru 日志（按日滚动）
│   └── prompts/            # AI Prompt 文件
├── browser-data/           # 浏览器用户数据（gitignore）
├── logs/                   # 启动脚本日志/PID（gitignore）
├── .env                    # 环境变量（gitignore，从 .env.example 复制）
├── .env.example            # 环境变量模板
├── 静默启动.vbs             # 根目录快捷入口（调用 scripts/静默启动.vbs）
├── pyproject.toml          # Python 项目配置
├── requirements.txt        # Python 依赖
├── Dockerfile              # Docker 镜像构建
└── docker-compose.yml      # Docker Compose 部署
```

详细规范见 [项目目录结构规范](docs/directory-structure.md)。

## 数据与日志

| 路径 | 说明 |
|------|------|
| `data/xianyu.db` | SQLite（任务/商品/卖家/评估/订单/事件） |
| `data/browser_data/` | 浏览器 user data dir（登录态） |
| `data/logs/*.log` | loguru 滚动日志 |
| `data/screenshots/` | 失败截图（如有） |

## 已知限制

1. **不支持云控验证码**：首次登录需人工，运行时若触发滑块会失败并通过 WAF 模块暂停
2. **单账号设计**：不支持多账号并发，账号策略为"1 账号 1 浏览器实例"
3. **WAF 响应延迟**：闲鱼侧风控更新后部分选择器可能失效，需更新 `infra/selectors.py`
4. **抢单窗口**：闲鱼详情页"立即购买"按钮出现后到消失通常 < 30 秒，对网络延迟敏感

## 风险与免责

1. **违反平台 ToS 风险**：本工具不伪装身份，但通过自动化访问行为可能违反闲鱼《用户协议》
2. **账号封禁风险**：高频访问/重复操作可能被识别并导致账号功能限制、封禁
3. **WAF/反爬升级**：闲鱼侧持续更新反爬策略，本工具可能随时失效
4. **财产风险**：抢单虽设价格容差校验，仍可能因页面/网络延迟导致错价，作者不对任何交易结果负责
5. **数据合规**：本工具仅在本地运行，不上传任何数据到第三方

**使用本工具即视为同意**：仅限个人学习/研究使用，自担一切风险。

## 许可

[MIT](LICENSE)


## 启动服务
```powershell
# 1. 停止旧进程（如果有）
$proc = Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue; if ($proc) { Stop-Process -Id $proc.OwningProcess -Force; Start-Sleep -Seconds 2 }

# 2. 启动新进程（Web + 调度器）
$env:PYTHONPATH = "d:\code\otherProjects\17_xianyu\src"; $env:PYTHONUNBUFFERED = "1"
$PY = "d:\code\otherProjects\17_xianyu\.venv\Scripts\python.exe"
$STDOUT = "d:\code\otherProjects\17_xianyu\logs\uvicorn.out.log"
$STDERR = "d:\code\otherProjects\17_xianyu\logs\uvicorn.err.log"
"" | Out-File -Encoding utf8 $STDOUT; "" | Out-File -Encoding utf8 $STDERR
Start-Process -FilePath $PY -ArgumentList "-u","-m","xianyu_hunter","web","--host","127.0.0.1","--port","8001","--with-scheduler" -WindowStyle Hidden -RedirectStandardOutput $STDOUT -RedirectStandardError $STDERR -WorkingDirectory "d:\code\otherProjects\17_xianyu"

# 3. 验证
Start-Sleep -Seconds 6; Get-NetTCPConnection -LocalPort 8001 -State Listen | Select-Object LocalAddress, LocalPort, OwningProcess
```