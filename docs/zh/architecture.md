# UPS Guard - 架构文档

## 系统概览

UPS Guard是一个基于容器的分布式应用，由三个主要服务组成：

```
┌─────────────────────────────────────────────┐
│  Docker 宿主机（支持 Windows/Linux/macOS/  │
│    懒猫微服/群辉/威联通等）                  │
├─────────────────────────────────────────────┤
│                                             │
│  ┌──────────────┐  ┌──────────────────┐   │
│  │  NUT Server  │  │    Frontend      │   │
│  │              │  │   (Vue 3 + NG)   │   │
│  │  ┌────────┐  │  └──────────────────┘   │
│  │  │ upsd   │  │           │              │
│  │  └────────┘  │           │              │
│  │  ┌────────┐  │           ↓              │
│  │  │usbhid  │  │  ┌──────────────────┐   │
│  │  │  ups   │  │  │    Backend       │   │
│  │  └────────┘  │  │  (FastAPI + WS)  │   │
│  │      ↕       │  │                  │   │
│  │  USB UPS     │←─┤  ┌────────────┐  │   │
│  └──────────────┘  │  │NUT Client  │  │   │
│                    │  └────────────┘  │   │
│                    │  ┌────────────┐  │   │
│                    │  │ Monitor    │  │   │
│                    │  └────────────┘  │   │
│                    │  ┌────────────┐  │   │
│                    │  │Shutdown Mgr│  │   │
│                    │  └────────────┘  │   │
│                    │  ┌────────────┐  │   │
│                    │  │  Notifier  │  │   │
│                    │  └────────────┘  │   │
│                    │  ┌────────────┐  │   │
│                    │  │  Database  │  │   │
│                    │  └────────────┘  │   │
│                    └──────────────────┘   │
│                            │               │
│                    ┌───────┴────────┐      │
│                    │ gRPC Shutdown  │      │
│                    │   (LZCOS API)  │      │
│                    └────────────────┘      │
└─────────────────────────────────────────────┘
```

## 核心组件

### 1. NUT Server 容器

**职责：**
- 通过 USB 与 UPS 设备通信
- 运行 NUT 守护进程 (upsd)
- 提供 NUT 协议接口

**技术栈：**
- Alpine Linux
- NUT (Network UPS Tools)
- usbhid-ups 驱动

**配置：**
- 动态生成 NUT 配置文件
- 环境变量驱动配置
- USB 设备直通 (`usb_accel: true`)

### 2. Backend 容器

**职责：**
- 监控 UPS 状态
- 管理关机策略
- 提供 REST API 和 WebSocket
- 处理通知推送
- 记录历史数据

**技术栈：**
- Python 3.11+
- FastAPI + Uvicorn
- aiosqlite
- grpcio

**核心模块：**

#### NUT 客户端 (`services/nut_client.py`)
```python
RealNutClient    # 生产环境，连接 NUT Server
MockNutClient    # 开发环境，模拟数据
```

功能：
- 异步 TCP 连接
- NUT 文本协议实现
- 变量查询 (GET VAR, LIST VAR)

#### 监控引擎 (`services/monitor.py`)
```python
UpsMonitor       # 状态机模式
```

状态流转：
```
OFFLINE → ONLINE → ON_BATTERY → LOW_BATTERY → SHUTTING_DOWN
                     ↑               ↑
                     └───────────────┘
                    (市电恢复)
```

功能：
- 5 秒轮询 UPS 状态
- 状态变化检测
- 事件记录
- 指标采样
- WebSocket 广播

#### 关机管理器 (`services/shutdown_manager.py`)
```python
ShutdownManager  # 安全关机策略
```

流程：
1. 停电检测 → 启动倒计时
2. 等待 N 分钟（可配置）
3. 电量检查（低于阈值立即关机）
4. 最终等待窗口（30秒）
5. 执行关机

特性：
- 任何时刻市电恢复可取消
- 多重确认机制
- 手动取消支持

#### LZCOS gRPC 客户端 (`services/lzc_shutdown.py`)（懒猫微服专有特性）
```python
LzcApiGatewayShutdown  # 生产环境（通过 API Gateway）
MockShutdown           # 开发环境
```

实现：
- 手动编码 protobuf 消息
- 通过 API Gateway 连接（insecure gRPC）
- 不依赖 proto 文件编译
- **注意**：此特性仅适用于懒猫微服系统

#### 通知系统 (`services/notifier.py`, `plugins/`)
```python
NotifierPlugin   # 插件基类
PluginRegistry   # 注册表
```

内置插件：
- Server酱
- PushPlus

扩展机制：
- 配置 Schema 自动渲染表单
- 自动发现和注册
- 独立配置和测试

#### 历史服务 (`services/history.py`)
```python
HistoryService   # 事件和指标存储
```

数据表：
- `events` - 事件记录（断电、恢复、关机等）
- `metrics` - 指标采样（电量、电压、负载等）
- `config` - 配置存储

### 3. Frontend 容器

**职责：**
- 用户界面
- 实时数据展示
- 配置管理
- 历史查询

**技术栈：**
- Vue 3 (Composition API)
- TypeScript
- Vite
- ECharts
- Nginx

**页面结构：**
```
Dashboard.vue    # 仪表盘 - 实时状态
├─ StatusCard    # 状态卡片
├─ BatteryGauge  # 电池仪表
├─ PowerChart    # 实时图表
└─ EventList     # 最近事件

Settings.vue     # 设置 - 配置管理
├─ Shutdown      # 关机策略
├─ Notifier      # 推送通知
└─ Advanced      # 高级设置

History.vue      # 历史 - 长期趋势
└─ MetricChart   # 历史图表

Events.vue       # 日志 - 事件列表
└─ EventTable    # 事件表格
```

## 数据流

### 实时状态流

```
UPS 设备
  ↓ USB
NUT Server (upsd)
  ↓ TCP :3493
Backend (NUT Client)
  ↓ 5秒轮询
Monitor (状态机)
  ↓ 状态变化
WebSocket
  ↓ 实时推送
Frontend (Vue)
  ↓ 渲染
用户界面
```

### 关机流程

```
断电检测
  ↓
Monitor 触发
  ↓
Shutdown Manager
  ├─ 等待计时器
  ├─ 电量检查
  └─ 市电监控
  ↓
最终等待窗口
  ↓
LZCOS gRPC
  ↓
系统关机
```

### 通知流程

```
事件发生
  ↓
History Service (记录)
  ↓
Notifier Service
  ├─ Server酱 → 微信
  ├─ PushPlus → 微信/群组
  └─ 自定义插件 → ...
```

## 配置管理

### 环境变量配置

```bash
# NUT 配置
NUT_HOST=nut-server
NUT_PORT=3493
NUT_USERNAME=monuser
NUT_PASSWORD=secret
NUT_UPS_NAME=ups

# 数据库
DATABASE_PATH=/data/ups_guard.db

# 模式
MOCK_MODE=false

# 懒猫 API Gateway
LZC_API_GATEWAY_ADDRESS=app.cloud.lazycat.app.ups-guard.lzcapp:81
```

### 数据库配置

存储在 SQLite `config` 表：
- 关机策略参数
- 通知渠道配置
- 采样和保留参数

可通过 API 动态修改。

## 安全机制

### 1. 关机安全

- ✅ 多重确认（时间 + 电量）
- ✅ 最终等待窗口
- ✅ 市电恢复自动取消
- ✅ 手动取消支持
- ✅ Mock 模式不执行真实关机

### 2. 敏感信息

- ⚠️ 通知 Token 使用 `password` 类型
- ⚠️ 日志不打印敏感信息
- ⚠️ 配置数据库文件权限保护

### 3. 权限控制

- 🔒 NUT Server 需要 `privileged` 访问 USB
- 🔒 gRPC socket 需要只读挂载
- 🔒 数据目录独立持久化

## 性能特性

### 轮询间隔

- UPS 状态：5 秒
- 指标采样：60 秒（可配置）
- WebSocket 心跳：25 秒

### 数据保留

- 历史事件：30 天（可配置）
- 指标采样：30 天（可配置）
- 自动清理过期数据

### 资源占用

预期资源消耗：
- CPU：< 5%（空闲时）
- 内存：< 200MB
- 存储：< 100MB（30天数据）

## 扩展性

### 插件系统

- 📦 通知插件动态加载
- 📦 配置 Schema 驱动表单
- 📦 自动注册和发现

### API 扩展

- 🔌 RESTful API
- 🔌 WebSocket 实时推送
- 🔌 支持跨域 CORS

### 容器化

- 🐳 三服务独立部署
- 🐳 环境变量配置
- 🐳 数据卷持久化
- 🐳 支持水平扩展（Frontend）

## 开发模式

### Mock 模式

设置 `MOCK_MODE=true` 启用：
- 使用 `MockNutClient` 模拟 UPS 数据
- 使用 `MockShutdown` 避免真实关机
- 提供 Mock API 控制状态

Mock API：
```
POST /api/dev/mock/power-lost      # 模拟断电
POST /api/dev/mock/power-restored  # 模拟恢复
POST /api/dev/mock/low-battery     # 模拟低电量
```

### 本地开发

```bash
# 后端
cd backend
uv sync
uvicorn src.main:app --reload

# 前端
cd frontend
pnpm install
pnpm dev
```

## 监控和调试

### 日志

```bash
# 查看 NUT Server 日志
docker logs ups-guard-nut-server

# 查看 Backend 日志
docker logs ups-guard-backend

# 查看 Frontend 日志
docker logs ups-guard-frontend
```

### 健康检查

```bash
# 检查后端健康
curl http://localhost:8000/health

# 检查 NUT 连接
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/api/ups/list
```

### WebSocket 测试

```bash
# 使用 websocat
websocat 'ws://localhost:8000/api/ws?token=YOUR_TOKEN'
```

HTTPS 入口使用 `wss://`；Token 含特殊字符时需进行 URL 编码。

## 部署架构

### Docker 部署（通用）

适用于任意 Docker 环境（Windows、Linux、macOS、群辉、威联通、懒猫微服等）。

```yaml
services:
  nut-server:    ports: 3493
  backend:       ports: 8000
  frontend:      ports: 80 (主入口)
```

访问：`http://your-host-ip/`

**懒猫微服专有特性**：
- 在懒猫微服环境中，可通过 `http://ups-guard.your-host/` 访问（子域名访问）
- 支持 gRPC 关机（通过 `/lzcapp/run/sys/lzc-apis.socket`）
- 支持 `deploy/lazycat/lzc-manifest.yml` 和 `deploy/lazycat/lzc-build.yml` 进行应用打包

### 开发环境

```yaml
services:
  backend:       ports: 8000 → localhost:8000
  frontend:      ports: 5173 → localhost:5173
```

前端代理 `/api` → `http://localhost:8000`

## 故障恢复

### 容器重启

所有容器配置 `restart: always`，异常退出自动重启。

### 数据恢复

数据存储在 Docker Volume `ups-data`：
- 数据库：`/data/ups_guard.db`
- 定期备份建议

### 状态恢复

应用重启后：
- 自动连接 NUT Server
- 加载配置
- 恢复监控
- 记录启动事件

## 参考资料

- [NUT 文档](https://networkupstools.org/docs/)
- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [Vue 3 文档](https://cn.vuejs.org/)
- [ECharts 文档](https://echarts.apache.org/)
