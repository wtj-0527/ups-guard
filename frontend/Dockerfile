# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

# 构建参数
ARG VITE_API_TOKEN=dev-token-123

# 设置环境变量（供 Vite 构建时使用）
ENV VITE_API_TOKEN=$VITE_API_TOKEN

# 固定 pnpm 版本，与 CI 保持一致，避免新版构建脚本审批策略导致安装失败
RUN npm install -g pnpm@8.15.9

# 复制依赖文件
COPY package.json ./

# 安装依赖
RUN pnpm install

# 复制源代码
COPY . .

# 构建
RUN pnpm run build

# Production stage - 使用 nginx alpine
FROM nginx:alpine

# 复制构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制 nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost/ || exit 1

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
