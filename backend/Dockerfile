# Build stage
FROM ghcr.io/astral-sh/uv:0.6.6-python3.11-bookworm-slim AS builder

WORKDIR /app

# 1️⃣ 先只复制依赖声明文件（利用 Docker 缓存）
COPY pyproject.toml ./

# 构建时可切换 PyPI 镜像，并为较慢的网络增加超时和重试
ARG UV_INDEX_URL=https://pypi.org/simple
ARG UV_HTTP_TIMEOUT=120
ARG UV_HTTP_RETRIES=5

# 2️⃣ 使用 uv venv 安装依赖（代码没变时这一层会命中缓存）
RUN uv venv /app/.venv && \
    UV_HTTP_TIMEOUT="${UV_HTTP_TIMEOUT}" UV_HTTP_RETRIES="${UV_HTTP_RETRIES}" \
    uv pip install --python /app/.venv/bin/python --no-cache \
      --index-url "${UV_INDEX_URL}" -r pyproject.toml

# 3️⃣ 再复制源代码（代码变更不会触发重新安装依赖）
COPY src ./src

# Runtime stage
FROM python:3.11.12-slim-bookworm

WORKDIR /app

# 从 builder 阶段复制虚拟环境（比复制 site-packages 更小更快）
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# 复制应用代码
COPY src ./src
COPY tools ./tools

# 版本号通过 ARG 在构建时注入，然后设置为 ENV 供运行时使用
ARG APP_VERSION=0.0.0
ENV APP_VERSION=${APP_VERSION}

# 创建数据目录
RUN mkdir -p /data

# 设置非 root 用户
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app /data
USER appuser

# 暴露端口
EXPOSE 8000

# 健康检查（用 python 内置模块，无需安装 curl）
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# 启动应用
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
