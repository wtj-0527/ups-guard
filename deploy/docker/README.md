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

### USB 转串口 UPS 被识别成模拟设备

对于已在 NUT 中验证可用的串口 UPS，请使用原来可用的驱动和协议。例如 Visench C3K 的用户已验证配置：

```dotenv
UPS_NAME=ups
UPS_DRIVER=nutdrv_qx
UPS_PORT=/dev/ttyUSB0
UPS_AUTO_DETECT=false
UPS_PROTOCOL=ablerex
```

`UPS_AUTO_DETECT=false` 会保留手动配置，跳过 USB 扫描；`UPS_PORT` 为 `/dev/...` 路径时也会自动采用手动模式。驱动通信中断后仍按原驱动、端口和协议重试，不会切换到 `dummy-ups`。协议变量必须使用 `UPS_PROTOCOL`，单独添加 `protocol` 或 `PROTOCOL` 不会传入容器。

确认串口节点在容器内可见：

```bash
sudo docker exec ups-guard-nut ls -l /dev/ttyUSB0
```

如果不存在，需先在 Compose 的 `nut-server` 服务下增加对应的设备映射（按实际设备路径调整）：

```yaml
devices:
  - /dev/ttyUSB0:/dev/ttyUSB0
```

更新后重新构建 NUT 和前端镜像，再重新创建容器，使 `.env` 中的配置生效；仅执行 `docker restart` 不会更新容器环境：

```bash
sudo docker compose --progress plain build nut-server frontend
sudo docker compose up -d --force-recreate nut-server backend frontend
sudo docker exec ups-guard-nut cat /etc/nut/ups.conf
sudo docker compose logs --tail 100 nut-server
sudo docker compose exec nut-server upsc ups@localhost
```

生成的配置应包含 `driver = nutdrv_qx`、`port = /dev/ttyUSB0` 和 `protocol = ablerex`。请以 `upsc` 返回的真实设备数据确认连通，不要用模拟设备显示的电量或在线状态判断。

### 厂家和型号显示为重复数字

如果真实电压和状态已读通，但 `device.mfr`、`device.model` 返回重复数字等异常标识，可在 `.env` 中设置：

```dotenv
UPS_MFR=VISENCH
UPS_MODEL=C3K
```

留空时使用驱动原始值。非空时生成 `override.device.mfr/model` 和兼容的 `override.ups.mfr/model`，仅覆盖标识，不修改电压、电量和状态，也不表示修复了底层协议解析。模拟和断线等待设备不应用标识覆盖，以保留故障提示。

```bash
sudo docker compose --env-file .env -f docker-compose.yml --progress plain build nut-server
sudo docker compose --env-file .env -f docker-compose.yml up -d --no-deps --force-recreate nut-server
sudo docker exec ups-guard-nut upsc ups@localhost
```

厂家、型号配置会在重建配置和驱动重连时保留。不要直接编辑容器内自动生成的 `ups.conf`，也不要仅重启旧容器期待新环境变量生效。

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

