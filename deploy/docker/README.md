# Docker 通用部署

适用于任何支持 Docker 的 Linux 服务器、Windows、macOS 等平台。

## 系统要求

- Docker Engine 20.10+
- Docker Compose 2.0+
- 至少 512MB RAM
- USB 接口（连接 UPS）

## 快速部署

### 1. 准备配置文件

```bash
# 复制环境变量配置
cp .env.example .env

# 编辑配置（根据实际情况修改）
nano .env
```

### 2. 关键配置项

```bash
# UPS 驱动（根据品牌选择）
UPS_DRIVER=usbhid-ups    # APC、CyberPower、Eaton
# UPS_DRIVER=blazer_usb  # 山特 SANTAK
# UPS_DRIVER=nutdrv_qx   # 其他 Megatec 协议

# 安全配置（建议修改默认密码）
UPSD_PASSWORD=your_secure_password
UPSMON_PASSWORD=your_secure_password
API_TOKEN=your_random_token

# Web 端口
HTTP_PORT=80
```

### 3. 启动服务

```bash
docker-compose up -d
```

### 4. 查看状态

```bash
# 检查服务状态
docker-compose ps

# 查看日志
docker-compose logs -f

# 检查 UPS 连接（先列出发现的 UPS，再查询详情）
docker-compose exec nut-server upsc -l localhost
docker-compose exec nut-server upsc <发现的UPS名称>@localhost
```

## 访问 Web 界面

打开浏览器访问：`http://localhost` 或 `http://<服务器IP>`

## 常见问题

### 后端构建下载依赖超时

如果 `uv pip install` 报 `Failed to fetch`、`operation timed out`，在本目录的 `.env` 中设置：

```dotenv
UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
UV_HTTP_TIMEOUT=120
UV_HTTP_RETRIES=5
```

这些配置会作为构建参数传入后端 Dockerfile，无需修改源码。默认仍使用官方 PyPI，可按网络情况切换下载源。

```bash
sudo docker compose --progress plain build backend
sudo docker compose up -d
sudo docker compose ps
```

### Web 端口被占用

如果报 `failed to bind host port 0.0.0.0:80/tcp: address already in use`，在 `.env` 中将 `HTTP_PORT` 改为一个空闲端口（例如 `8088`），然后执行：

```bash
sudo docker compose up -d frontend
```

通过 `http://<服务器IP>:8088` 访问，启用防火墙时需放行对应端口。

### UPS 未识别

1. 检查 USB 连接：`lsusb`
2. 查看 NUT 日志：`docker-compose logs nut-server`
3. 尝试更换驱动配置

### 权限问题

确保 docker-compose.yml 中 nut-server 服务有 `privileged: true`

## 文件说明

- `docker-compose.yml` - 主编排文件
- `.env.example` - 环境变量模板

