# UPS Guard - 懒猫微服单容器 Dockerfile
# 将 NUT + Backend + Frontend 整合到一个容器中

# ==================== 阶段 1: 前端构建 ====================
FROM node:20.18-alpine3.21 AS frontend-builder

WORKDIR /app

ARG NPM_REGISTRY=https://registry.npmjs.org

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm config set registry ${NPM_REGISTRY} && \
    npm ci --no-audit --no-fund

COPY frontend/ ./
RUN npm run build

# ==================== 阶段 2: 后端依赖安装 ====================
FROM python:3.11.12-alpine3.21 AS backend-builder

WORKDIR /app

ARG PIP_INDEX_URL=https://pypi.org/simple
ARG PIP_TRUSTED_HOST=pypi.org

COPY backend/pyproject.toml ./
# 使用 uv 虚拟环境安装，减少最终镜像 COPY 体积
RUN pip install --no-cache-dir uv && \
    uv venv /app/.venv && \
    uv pip install --python /app/.venv/bin/python --no-cache \
        --index-url "${PIP_INDEX_URL}" -r pyproject.toml

# ==================== 阶段 3: 最终镜像 ====================
FROM python:3.11.12-alpine3.21

LABEL org.opencontainers.image.title="UPS Guard" \
      org.opencontainers.image.description="懒猫微服 UPS 智能监控与管理应用" \
      org.opencontainers.image.licenses="AGPL-3.0" \
      org.opencontainers.image.source="https://github.com/wtj-0527/ups-guard"

ARG APP_VERSION=0.0.0
ARG VCS_REF=""
LABEL org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}"

# 系统依赖安装（静态层，应该稳定命中缓存）
ARG APK_MIRROR=https://dl-cdn.alpinelinux.org/alpine
RUN sed -i "s|https://dl-cdn.alpinelinux.org/alpine|${APK_MIRROR}|g" /etc/apk/repositories && \
    apk add --no-cache \
        nut usbutils libusb-dev eudev \
        curl bash dos2unix procps && \
    mkdir -p /data /run/nut /etc/nut /var/state/ups /tmp/ups-info && \
    chown -R nut:nut /run/nut /etc/nut /var/state/ups && \
    mkdir -p /etc/udev/rules.d && \
    printf '%s\n' \
        'SUBSYSTEM=="usb", ATTR{idVendor}=="051d", MODE="0666"' \
        'SUBSYSTEM=="usb", ATTR{idVendor}=="0463", MODE="0666"' \
        'SUBSYSTEM=="usb", ATTR{idVendor}=="0665", MODE="0666"' \
        'SUBSYSTEM=="usb", ATTR{idVendor}=="06da", MODE="0666"' \
        'SUBSYSTEM=="usb", ATTR{idVendor}=="0764", MODE="0666"' \
        > /etc/udev/rules.d/99-nut-ups.rules

WORKDIR /app

# 从构建阶段复制 Python 虚拟环境（比复制 site-packages 更小更快）
COPY --from=backend-builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# 按变更频率从低到高排列，合并同目录的 COPY
# 不常变的：NUT 配置 + 入口脚本
COPY nut/ /app/nut/
COPY deploy/lazycat/entrypoint.sh /entrypoint.sh

# 从阶段 1 复制前端构建产物
COPY --from=frontend-builder /app/dist ./frontend/dist

# 常变的：后端代码（放最后，最大化缓存命中）
COPY backend/src ./backend/src
COPY backend/tools ./backend/tools

RUN chmod +x /entrypoint.sh /app/nut/entrypoint.sh && \
    dos2unix /entrypoint.sh /app/nut/entrypoint.sh 2>/dev/null || true

# 版本号通过 ARG 在构建时注入，然后设置为 ENV 供运行时使用
ARG APP_VERSION=0.0.0
ENV APP_VERSION=${APP_VERSION}

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
