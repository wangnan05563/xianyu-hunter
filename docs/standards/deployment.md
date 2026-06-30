# XianyuHunter 部署指南

> 本文档覆盖三种部署场景：Docker 一键部署（推荐）、服务器原生部署、本地开发部署。
> 适用于 v0.1.0+ 版本（含 SPA 前端 + FastAPI 后端 + Playwright 浏览器自动化）。

---

## 1. 前置准备

### 1.1 必需资源

| 资源 | 最低配置 | 推荐配置 |
|---|---|---|
| CPU | 1 核 | 2 核+ |
| 内存 | 1 GB | 2 GB+ |
| 磁盘 | 2 GB | 10 GB+（含浏览器数据） |
| 网络 | 能访问 `goofish.com` | 同上 |
| 操作系统 | Linux x64 / macOS / Windows 10+ | Linux x64（Docker 部署） |

### 1.2 必需账号

- **闲鱼账号**：用于登录并执行监控/抢单（建议小号，避免主号风控）
- **推送渠道（可选）**：Server酱 / PushPlus / Bark / Telegram / 企业微信 / 钉钉 / Webhook 任选其一

### 1.3 配置文件准备

首次部署前，从示例文件复制并修改：

```bash
cp config/config.example.yaml config/config.yaml
cp config/eval.example.yaml config/eval.yaml
cp .env.example .env
```

编辑 `.env` 填入推送 Key 与 AI Key（可选），编辑 `config/config.yaml` 调整监控参数。

---

## 2. Docker 一键部署（推荐）

### 2.1 安装 Docker

- **Linux**：`curl -fsSL https://get.docker.com | sh`
- **macOS / Windows**：安装 [Docker Desktop](https://www.docker.com/products/docker-desktop)
- **NAS**：群晖/威联通等系统自带 Docker 套件

验证安装：

```bash
docker --version
docker compose version
```

### 2.2 默认部署（Web + 调度器一体）

适用于个人用户单机部署：

```bash
# 1. 克隆项目
git clone <your-repo-url> xianyu-hunter
cd xianyu-hunter

# 2. 准备配置（首次运行）
cp config/config.example.yaml config/config.yaml
cp .env.example .env
# 编辑 .env 与 config/config.yaml

# 3. 构建并启动（首次构建约 5-10 分钟，会下载 Playwright 浏览器）
docker compose up -d --build

# 4. 查看启动日志
docker compose logs -f

# 5. 健康检查
curl http://localhost:8000/healthz
# 预期返回：{"status":"ok"}
```

访问 `http://<服务器IP>:8000/app/` 进入 Web 控制台。

### 2.3 开发模式部署（仅 Web，无调度器）

适用于本机调试，调度器由 IDE 单独启动：

```bash
docker compose --profile dev up -d --build
```

### 2.4 分离模式部署（Web 与 Scheduler 分离）

适用于生产环境水平扩展：

```bash
docker compose --profile split up -d --build
```

Web 服务监听 8000 端口，Scheduler 服务独立运行不开放端口。两者共享 `./data` 与 `./config` 卷。

### 2.5 自定义端口

通过环境变量修改端口：

```bash
# 修改 .env 或直接命令行指定
XH_PORT=9000 docker compose up -d
```

### 2.6 升级

```bash
git pull
docker compose up -d --build
```

数据卷 `./data` 与 `./config` 不会受影响。

### 2.7 备份与恢复

```bash
# 备份
tar -czf xianyu-hunter-backup-$(date +%Y%m%d).tar.gz data/ config/ .env

# 恢复
tar -xzf xianyu-hunter-backup-YYYYMMDD.tar.gz
docker compose restart
```

---

## 3. 服务器原生部署（Linux）

适用于无 Docker 环境的 Linux 服务器。

### 3.1 安装依赖

```bash
# Ubuntu / Debian
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3-pip nodejs npm

# CentOS / RHEL
sudo dnf install -y python3.12 nodejs npm
```

### 3.2 部署步骤

```bash
# 1. 克隆项目
git clone <your-repo-url> xianyu-hunter
cd xianyu-hunter

# 2. 创建 Python 虚拟环境
python3.12 -m venv .venv
source .venv/bin/activate

# 3. 安装后端依赖
pip install -e .
playwright install chromium --with-deps

# 4. 构建前端
cd frontend
npm ci
npm run build
cd ..

# 5. 准备配置
cp config/config.example.yaml config/config.yaml
cp .env.example .env
# 编辑配置...

# 6. 启动
python -m xianyu_hunter web --port 8000 --host 0.0.0.0 --with-scheduler
```

### 3.3 systemd 服务（可选）

创建 `/etc/systemd/system/xianyu-hunter.service`：

```ini
[Unit]
Description=XianyuHunter
After=network.target

[Service]
Type=simple
User=<your-user>
WorkingDirectory=/path/to/xianyu-hunter
Environment=PATH=/path/to/xianyu-hunter/.venv/bin
ExecStart=/path/to/xianyu-hunter/.venv/bin/python -m xianyu_hunter web --port 8000 --host 0.0.0.0 --with-scheduler
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启用：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now xianyu-hunter
sudo systemctl status xianyu-hunter
```

---

## 4. 本地开发部署（Windows / macOS）

### 4.1 后端

```powershell
# Windows PowerShell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
playwright install chromium --with-deps
```

### 4.2 前端（开发模式，热更新）

```powershell
cd frontend
npm install
npm run dev
# 访问 http://localhost:5173/app/，API 自动代理到 http://127.0.0.1:8000
```

### 4.3 启动后端 Web 服务

```powershell
python -m xianyu_hunter web --port 8000 --with-scheduler
```

---

## 5. 配置说明

### 5.1 环境变量（.env）

| 变量名 | 必填 | 说明 |
|---|---|---|
| `SERVERCHAN_KEY` | 否 | Server酱推送 Key |
| `PUSHPLUS_TOKEN` | 否 | PushPlus 推送 Token |
| `BARK_SERVER` | 否 | Bark 服务器地址（默认 `https://api.day.app`） |
| `BARK_KEY` | 否 | Bark 推送 Key |
| `OPENAI_API_KEY` | 否 | OpenAI API Key（启用 AI 评估必填） |
| `OPENAI_BASE_URL` | 否 | OpenAI API Base URL（默认 `https://api.openai.com/v1`） |
| `LOG_LEVEL` | 否 | 日志级别：DEBUG / INFO / WARN / ERROR（默认 INFO） |

至少配置一个推送渠道，否则只能通过 Web 控制台查看告警。

### 5.2 主配置（config/config.yaml）

详见 [config.example.yaml](file:///d:/code/otherProjects/17_xianyu/config/config.example.yaml) 中的注释。关键配置项：

| 配置项 | 默认值 | 说明 |
|---|---|---|
| `search.qps` | 20 | 搜索 QPS 上限（过高可能触发风控） |
| `search.interval_seconds` | 60 | 搜索间隔（秒） |
| `eval.pass_score` | 70 | 4 维评估通过分（0-100） |
| `eval.auto_buy_score` | 75 | 自动下单触发分（≥ pass_score） |
| `buyer.price_tolerance` | 0.05 | 价格容差（5% 内可接受） |
| `notifier.quiet_hours` | - | 免打扰时段 |

### 5.3 配置热更新

通过 Web 控制台 `/app/config/*` 修改的配置会实时写入 `config/config.yaml`，无需重启。
环境变量（.env）修改后需重启容器：`docker compose restart`。

---

## 6. 首次使用流程

1. **访问控制台**：浏览器打开 `http://<服务器IP>:8000/app/`
2. **登录闲鱼**：进入"登录"页面，选择"浏览器登录"（推荐），扫码登录
3. **添加任务**：进入"任务"页面，点击"新建任务"，填写关键词、价格范围、调度策略
4. **启动任务**：任务列表点击"启动"按钮
5. **查看进度**：Dashboard 实时显示发现/评估/拍下/成交数据
6. **接收通知**：当有商品通过评估或拍下时，推送渠道会收到通知

---

## 7. 故障排查

### 7.1 容器启动失败

```bash
# 查看启动日志
docker compose logs xianyu-hunter

# 常见错误：
# 1. "playwright install failed" → 网络问题，配置 npm/pip 镜像源
# 2. "address already in use" → 8000 端口被占用，修改 XH_PORT
# 3. "permission denied" → ./data 或 ./config 目录权限不足
```

### 7.2 健康检查失败

```bash
# 进入容器排查
docker compose exec xianyu-hunter bash

# 检查 Web 服务
curl -v http://localhost:8000/healthz

# 检查 Playwright
python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); b = p.chromium.launch(); print('OK'); b.close(); p.stop()"
```

### 7.3 闲鱼登录失效

症状：日志出现 `RGV587_ERROR` 或 `403 Unauthorized`。

处理：
1. Web 控制台进入"反爬管理"页面
2. 查看三层 Cookie 状态（identity/session/tracking）
3. 若 identity 失效，点击"更新 Cookie"重新登录
4. 若 session 失效，等待 TokenRenewer 自动续期（30 秒内）
5. 若 tracking 失效，重启容器：`docker compose restart`

### 7.4 数据丢失

**重要**：`./data` 目录包含 SQLite 数据库与 cookies.json，请定期备份。

```bash
# 自动备份（crontab）
0 3 * * * cd /path/to/xianyu-hunter && tar -czf backups/backup-$(date +\%Y\%m\%d).tar.gz data/ config/ .env
```

### 7.5 SPA 未构建

症状：访问 `/app/` 返回 `{"detail":"SPA 未构建，请运行 cd frontend && npm run build"}`。

处理（Docker 部署）：重新构建镜像 `docker compose up -d --build`
处理（原生部署）：`cd frontend && npm run build`

---

## 8. 性能调优

### 8.1 内存不足

- 增加 `shm_size: "2gb"`（docker-compose.yml）
- 减少 `search.qps` 与并发任务数

### 8.2 浏览器崩溃

- 检查 `./data/browser_data/` 目录权限
- 启用 `anti_detect.stealth_v2: true`
- 降低 `search.qps`

### 8.3 推送延迟

- 检查 `notifier.quiet_hours` 是否启用
- 切换到延迟更低的渠道（Bark < Server酱 < 邮件）

---

## 9. 安全建议

1. **不要将 8000 端口直接暴露到公网**：使用 Nginx 反向代理 + HTTPS + Basic Auth
2. **`.env` 文件权限设为 600**：`chmod 600 .env`
3. **定期更换闲鱼账号**：避免长期使用同一账号触发风控
4. **使用小号**：避免主号因自动化操作被封禁
5. **配置防火墙**：仅允许信任 IP 访问 8000 端口

### 9.1 Nginx 反向代理示例

```nginx
server {
    listen 443 ssl http2;
    server_name xianyu.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    # Basic Auth
    auth_basic "XianyuHunter";
    auth_basic_user_file /etc/nginx/.htpasswd;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE 长连接支持
        proxy_buffering off;
        proxy_read_timeout 86400s;
    }
}
```

---

## 10. 相关文档

- [README.md](file:///d:/code/otherProjects/17_xianyu/README.md) — 项目概览
- [requirements.md](file:///d:/code/otherProjects/17_xianyu/docs/requirements.md) — 业务需求规格
- [optimization-requirements-2026-06-27.md](file:///d:/code/otherProjects/17_xianyu/docs/optimization-requirements-2026-06-27.md) — 优化需求文档
- [config.example.yaml](file:///d:/code/otherProjects/17_xianyu/config/config.example.yaml) — 配置示例
