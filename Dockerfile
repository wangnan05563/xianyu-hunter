# XianyuHunter Dockerfile
# 三阶段构建：frontend (Vite SPA) → builder (Python 依赖) → runtime (精简运行时)
#
# 设计要点：
# - frontend 阶段独立构建 React SPA，避免 runtime 阶段携带 node_modules
# - builder 阶段基于 pyproject.toml 安装依赖（不使用 requirements.txt，避免 Windows 专用包污染）
# - runtime 阶段合并 frontend 产物 + Python 依赖，体积最小化
# - 数据持久化：/app/data 与 /app/config 双卷挂载
# - 健康检查：/healthz 端点
# - 非 root 运行：Playwright 浏览器路径迁移到 /app/.cache，避免容器内特权提升攻击面

# ============== Stage 1: Frontend 构建 ==============
FROM node:20-alpine AS frontend

# WORKDIR 设为 /app/frontend，使 vite outDir 的相对路径 ../src/... 解析到 /app/src/...
# 与后续 builder/runtime 阶段的 /app/src 对齐，便于 COPY --from=frontend 直接取用
WORKDIR /app/frontend

# 先复制 package 元数据，利用 Docker 缓存层加速依赖安装
COPY frontend/package.json frontend/package-lock.json* ./
# 没有 package-lock.json 时降级到 npm install
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

# 复制源码并构建
# vite.config.ts 中 outDir 指向 ../src/xianyu_hunter/web/static/spa
# 构建产物会落到 /app/src/xianyu_hunter/web/static/spa
COPY frontend/ ./
RUN npm run build

# ============== Stage 2: Python 依赖构建 ==============
FROM python:3.12-slim AS builder

WORKDIR /app

# 安装系统依赖（Playwright 浏览器运行时依赖 + curl 用于健康检查）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制 pyproject.toml 并安装项目依赖到 --user 目录
# 不使用 requirements.txt：其中包含 pythonnet/pywin32 等 Windows 专用包会在 Linux 失败
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir --user -e .

# 安装 Playwright Chromium 浏览器及其系统依赖
RUN /root/.local/bin/playwright install chromium --with-deps

# ============== Stage 3: Runtime 运行时 ==============
FROM python:3.12-slim

WORKDIR /app

# 从 builder 复制 Python 依赖与 Playwright 浏览器
# 路径迁到 /app 下，便于后续切换非 root 用户后仍可访问（避免 /root 目录权限问题）
COPY --from=builder /root/.local /app/.local
COPY --from=builder /root/.cache/ms-playwright /app/.cache/ms-playwright

# 从 frontend 复制 SPA 构建产物到后端 static 目录
# 路径需与 vite.config.ts 的 outDir 保持一致
COPY --from=frontend /app/src/xianyu_hunter/web/static/spa ./src/xianyu_hunter/web/static/spa

# 复制项目源码与构建配置
COPY src/ ./src/
COPY pyproject.toml ./

# 环境变量：PATH 指向 /app/.local/bin；Playwright 浏览器路径迁到 /app/.cache
# PYTHONUNBUFFERED 让日志实时可见；PYTHONDONTWRITEBYTECODE 避免生成 .pyc
ENV PATH=/app/.local/bin:$PATH
ENV PLAYWRIGHT_BROWSERS_PATH=/app/.cache/ms-playwright
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 创建数据与配置目录（SQLite + 日志 + prompts + cookies + config.yaml）
RUN mkdir -p /app/data/prompts /app/config

# 暴露 Web 端口
EXPOSE 8000

# 健康检查：每 30s 检查一次 /healthz
# start-period=20s 给 Playwright 首次启动留出时间
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/healthz || exit 1

# 默认启动命令：Web + 调度器一键模式
# 通过环境变量 XH_WITH_SCHEDULER=1 显式启用调度器（与 docker-compose.yml 对齐）
ENV XH_WITH_SCHEDULER=1

# 创建非 root 用户运行应用，避免容器内特权提升攻击面
# chown 覆盖 /app 全部内容：Python 依赖、Playwright 浏览器、data/config 写入目录
RUN groupadd -r xhapp && useradd -r -g xhapp -d /app -s /sbin/nologin xhapp \
    && chown -R xhapp:xhapp /app
USER xhapp

CMD ["python", "-m", "xianyu_hunter", "web", "--port", "8000", "--host", "0.0.0.0", "--with-scheduler"]
