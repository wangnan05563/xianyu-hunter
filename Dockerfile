# XianyuHunter Dockerfile
# 多阶段构建：builder 阶段安装依赖，runtime 阶段仅复制必要文件
#
# 设计要点：
# - 基于 python:3.12-slim（3.14 在 Docker Hub 可能无 slim 变体）
# - Playwright 需要额外安装浏览器依赖（libnss3/libatk 等）
# - 数据持久化：/app/data 目录挂载为 volume
# - 健康检查：/healthz 端点

FROM python:3.12-slim AS builder

# 设置工作目录
WORKDIR /app

# 安装系统依赖（Playwright 浏览器运行时依赖）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖清单并安装（利用 Docker 缓存层）
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# 安装 Playwright 浏览器（Chromium）
RUN /root/.local/bin/playwright install chromium --with-deps

# ============== Runtime 阶段 ==============
FROM python:3.12-slim

WORKDIR /app

# 从 builder 复制已安装的依赖
COPY --from=builder /root/.local /root/.local
COPY --from=builder /root/.cache/ms-playwright /root/.cache/ms-playwright

# 确保可执行文件在 PATH 中
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 复制项目源码和构建配置
COPY src/ ./src/
COPY pyproject.toml requirements.txt ./

# 安装项目为可编辑模式（让 import xianyu_hunter 生效）
RUN pip install --no-cache-dir -e .

# 创建数据目录（SQLite + 日志 + prompts）
RUN mkdir -p /app/data/prompts

# 暴露 Web 端口
EXPOSE 8000

# 健康检查：每 30s 检查一次 /healthz
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

# 默认启动命令：Web + 调度器一键模式
# 通过环境变量 XH_WITH_SCHEDULER=1 启用调度器
CMD ["python", "-m", "xianyu_hunter", "web", "--port", "8000", "--host", "0.0.0.0", "--with-scheduler"]
