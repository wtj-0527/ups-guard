# ⚡ UPS Guard

通用 UPS 智能监控与管理应用，支持在任意 Docker 环境中部署，可同时纳管 Windows、Linux、macOS、群辉、威联通、懒猫微服等多种设备。

Universal UPS monitoring and management application that supports deployment on any device with Docker (Windows, Mac, Linux, Synology, QNAP, LazyCAT, etc.) with centralized management of multiple devices.

**开发者 / Developer**： 王.W

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](LICENSE)
[![GitHub release](https://img.shields.io/github/v/release/KingBoyAndGirl/ups-guard)](https://github.com/KingBoyAndGirl/ups-guard/releases)
[![Version](https://img.shields.io/badge/version-1.0.0-brightgreen.svg)](https://github.com/KingBoyAndGirl/ups-guard/releases)

> 📖 **Language / 语言**: [中文文档](docs/zh/README.md) | [English Documentation](docs/en/README.md) | [Documentation Index / 文档索引](docs/zh/INDEX.md)

## 🧪 测试环境 / Tested Environment

本项目已在以下环境验证 / This project has been tested in the following environment:
- **操作系统 / OS**：Windows 11
- **部署平台 / Platform**：懒猫微服 (LazyCAT Micro Services) - Docker
- **UPS型号 / UPS Model**：APC Back-UPS BK650M2-CH (650VA)
- **NUT版本 / NUT Version**：2.8.3

> ⚠️ **注意 / Note**：其他操作系统和UPS型号尚未测试 / Other OS and UPS models have not been tested yet. 欢迎反馈兼容性信息 / Compatibility feedback is welcome.

## ✨ 功能特性 / Features

### v1.0 正式版 / v1.0 Release 🎉
- 🔒 **安全加固 / Security Hardening** - API Token 认证、敏感数据加密、CORS 限制 / API Token authentication, sensitive data encryption, CORS restrictions
- 🌍 **国际化支持 / Internationalization** - 中英文双语界面和通知消息 / Bilingual UI and notifications (Chinese/English)
- 📈 **性能优化 / Performance Optimization** - SQLite WAL 模式、数据降采样、懒加载 / SQLite WAL mode, data downsampling, lazy loading
- 🛡️ **错误恢复 / Error Recovery** - gRPC/NUT 自动重连、事务保护、详细日志 / gRPC/NUT auto-reconnect, transaction protection, detailed logging
- 🐳 **优化部署 / Optimized Deployment** - 多阶段构建、健康检查、轻量镜像 / Multi-stage build, health checks, lightweight images
- 🌙 **深色模式 / Dark Mode** - 支持亮色/暗色/跟随系统三种主题 / Light/Dark/System theme support
- 📱 **移动端适配 / Mobile Responsive** - 完整的响应式设计，支持各种屏幕 / Full responsive design for all screen sizes
- 📊 **数据管理 / Data Management** - 可视化数据库统计，一键清理 / Visual database stats, one-click cleanup
- 🔔 **更多推送渠道 / More Notification Channels** - 钉钉、Telegram、邮件、Webhook / DingTalk, Telegram, Email, Webhook

### 核心功能 / Core Features
- 🔌 **实时监控 / Real-time Monitoring** - WebSocket 实时推送 UPS 状态 / WebSocket real-time UPS status push
- 🔋 **智能关机 / Smart Shutdown** - 停电后自动倒计时关机，市电恢复自动取消 / Auto countdown shutdown on power loss, auto cancel on power restore
- 📈 **数据可视化 / Data Visualization** - ECharts 实时曲线图 / ECharts real-time charts for battery, voltage, load
- 📱 **推送通知 / Push Notifications** - 6 种通知渠道 / 6 notification channels: ServerChan, PushPlus, DingTalk, Telegram, Email, Webhook
- 📝 **历史记录 / History Logs** - 完整的事件日志，最长保留 90 天 / Complete event logs, up to 90 days retention
- 🔧 **灵活配置 / Flexible Configuration** - 关机策略、通知渠道等均可自定义 / Customizable shutdown policy, notification channels
- 🔌 **插件系统 / Plugin System** - 支持自定义通知插件 / Custom notification plugin support
- 🎨 **现代界面 / Modern UI** - Vue 3 + TypeScript，简洁卡片风格 / Vue 3 + TypeScript, clean card-style design
- 🐳 **容器化部署 / Containerized Deployment** - 三服务架构，一键安装 / Three-service architecture, one-click install

## 📸 界面预览 / Screenshots

### 仪表盘 / Dashboard
- 实时状态监控（在线/电池供电/低电量）/ Real-time status monitoring (Online/On Battery/Low Battery)
- 电池电量仪表盘 / Battery level gauge
- 输入/输出电压、负载百分比、温度等关键指标 / Input/Output voltage, load percentage, temperature
- 实时数据曲线图 / Real-time data charts
- 最近事件列表 / Recent events list

<img width="2940" height="4458" alt="image" src="https://github.com/user-attachments/assets/368003c4-2278-48d2-87a5-2b242d44613c" />

<img width="2940" height="1604" alt="image" src="https://github.com/user-attachments/assets/9cb624a3-3cf9-4765-aed8-1b42a4e453b3" />


### 设置页面 / Settings Page
- 关机策略配置（等待时间、最低电量、最终等待）/ Shutdown policy configuration (wait time, minimum battery, final wait)
- 推送通知配置（多渠道支持）/ Push notification configuration (multi-channel support)
- 数据采样和保留设置 / Data sampling and retention settings

<img width="2940" height="5530" alt="image" src="https://github.com/user-attachments/assets/9398e9f8-4608-47b4-a10a-46db0cba9b72" />


### 历史记录 / History
- 长期趋势图表（24 小时）/ Long-term trend charts (24 hours)
- 事件时间线 / Event timeline

<img width="2940" height="2730" alt="image" src="https://github.com/user-attachments/assets/e5b13832-8392-4ac5-adc7-f5b0a1f42d49" />

## 🚀 快速开始 / Quick Start

### 部署方式 / Deployment Options

UPS Guard 支持在任意有 Docker 的设备上运行，可通过 USB 连接 UPS，并远程管理局域网内的其他设备：

UPS Guard can run on any device with Docker, connect to UPS via USB, and remotely manage other devices on the LAN:

| 设备类型 / Device Type | 部署方式 / Deployment Method | 配置文件位置 / Config Location |
|---------|---------|-------------|
| 懒猫微服 / LazyCAT | 原生应用安装 / Native App Install | [`deploy/lazycat/`](deploy/lazycat/) |
| 群晖 NAS / Synology NAS | Container Manager | [`deploy/synology/`](deploy/synology/) |
| 威联通 NAS / QNAP NAS | Container Station | [`deploy/qnap/`](deploy/qnap/) |
| Linux/Windows/Mac | Docker Compose | [`deploy/docker/`](deploy/docker/) |

> 📁 完整部署配置文件请查看 [`deploy/`](deploy/) 目录
> 
> 📁 See the [`deploy/`](deploy/) directory for complete deployment configurations

### Docker 部署（通用部署） / Docker Deployment (Universal)

支持在任何有 Docker 的设备上运行（Win11、Mac、Linux、群辉、威联通等）。

Supports running on any device with Docker (Win11, Mac, Linux, Synology, QNAP, etc.).

#### 快速开始 / Quick Start

```bash
# 1. 克隆仓库 / Clone repository
git clone https://github.com/KingBoyAndGirl/ups-guard.git
cd ups-guard/deploy/docker

# 2. 配置环境变量 / Configure environment variables
cp .env.example .env
# 编辑 .env 文件，根据实际情况修改配置
# Edit .env file and modify configuration as needed

# 3. 启动服务 / Start services
docker-compose up -d

# 4. 访问 Web 界面 / Access Web UI
# 浏览器打开 / Open in browser: http://localhost
```

详细 Docker 部署指南请查看 [Docker 部署文档](docs/zh/docker-deployment.md) ([English](docs/en/docker-deployment.md))。

For detailed Docker deployment guide, see [Docker Deployment Guide](docs/en/docker-deployment.md) ([中文](docs/zh/docker-deployment.md)).

### 懒猫微服部署 / LazyCAT Deployment

#### 系统要求 / System Requirements

- 懒猫微服 LZCOS 系统 / LazyCAT LZCOS system
- 支持 USB 的 UPS 设备 / USB-compatible UPS device
- 至少 1GB 可用存储空间 / At least 1GB available storage

#### 安装步骤 / Installation Steps

1. **下载应用包 / Download Application Package**
   ```bash
   # 从 GitHub Releases 下载最新版本
   # Download latest version from GitHub Releases
   wget https://github.com/KingBoyAndGirl/ups-guard/releases/latest/download/ups-guard.lpk
   ```

2. **安装应用 / Install Application**
   - 进入懒猫微服控制面板 / Go to LazyCAT control panel
   - 应用商店 → 本地安装 / App Store → Local Install
   - 选择 `ups-guard.lpk` 文件 / Select `ups-guard.lpk` file
   - 等待安装完成 / Wait for installation to complete

3. **连接 UPS / Connect UPS**
   - 通过 USB 连接 UPS 到懒猫微服主机 / Connect UPS to LazyCAT host via USB
   - 应用会自动检测设备 / Application will auto-detect device

4. **访问应用 / Access Application**
   ```
   http://your-lazycat-host/ups-guard/
   ```

5. **配置 API Token (v1.0+) / Configure API Token (v1.0+)**
   
   首次启动时，应用会自动生成 API Token 并在日志中打印。建议在懒猫控制面板中设置环境变量：
   
   On first startup, the application auto-generates an API Token and prints it in the logs. It's recommended to set environment variables in LazyCAT control panel:
   
   - 进入应用设置 / Go to application settings
   - 添加环境变量 / Add environment variable: `API_TOKEN=<your-token>`
   - 重启应用 / Restart application
   
   前端访问时会自动使用配置的 Token 进行认证。
   
   The frontend will automatically use the configured Token for authentication.

详细安装指南请查看 [安装文档](docs/zh/install.md) ([English](docs/en/install.md))。

For detailed installation guide, see [Installation Guide](docs/en/install.md) ([中文](docs/zh/install.md)).

## ⚙️ 配置说明 / Configuration

### 环境变量 / Environment Variables

**NUT 配置 / NUT Configuration**
- `NUT_HOST`: NUT 服务器地址 / NUT server address（默认 / Default: `nut-server`）
- `NUT_PORT`: NUT 服务器端口 / NUT server port（默认 / Default: `3493`）
- `NUT_USERNAME`: NUT 用户名 / NUT username（默认 / Default: `monuser`）
- `NUT_PASSWORD`: NUT 密码 / NUT password（默认 / Default: `secret`）
- `NUT_UPS_NAME`: UPS 设备名称 / UPS device name（默认 / Default: `ups`）

**安全配置 / Security Configuration**
- `API_TOKEN`: API 认证 Token / API authentication token（未设置则自动生成 / Auto-generated if not set）
- `ENCRYPTION_KEY`: 敏感数据加密密钥 / Sensitive data encryption key（未设置则自动生成并保存 / Auto-generated and saved if not set）
- `ALLOWED_ORIGINS`: CORS 允许的来源 / CORS allowed origins（逗号分隔，默认仅允许同域 / Comma-separated, same-origin only by default）

**数据库配置 / Database Configuration**
- `DATABASE_PATH`: 数据库文件路径 / Database file path（默认 / Default: `/data/ups_guard.db`）

**其他 / Others**
- `LOG_LEVEL`: 日志级别 / Log level（默认 / Default: `INFO`）
- `MOCK_MODE`: 开发模式 / Development mode（默认 / Default: `false`）

## 📚 文档 / Documentation

> 💡 **提示 / Tip**: 本项目提供中英文双语文档 / This project provides bilingual documentation in Chinese and English.

### 中文文档
- [完整文档索引](docs/index.md) - 所有文档导航页
- [项目介绍](docs/zh/README.md) - 详细的项目说明
- [安装指南](docs/zh/install.md) - 完整的安装和配置步骤
- [用户指南](docs/zh/user-guide.md) - 详细使用说明
- [Docker 部署指南](docs/zh/docker-deployment.md) - Docker 环境部署
- [支持的 UPS 设备](docs/zh/supported-ups.md) - 兼容设备列表
- [推送通知配置](docs/zh/push-setup.md) - 通知渠道配置教程
- [插件开发指南](docs/zh/development/plugin-dev.md) - 自定义通知插件开发
- [架构文档](docs/zh/architecture.md) - 系统架构和技术细节
- [常见问题](docs/zh/faq.md) - FAQ
- [更新日志](docs/zh/changelog.md) - 版本历史

### English Documentation
- [Documentation Index](docs/index.md) - All documentation navigation
- [Project Overview](docs/en/README.md) - Detailed project introduction
- [Installation Guide](docs/en/install.md) - Complete installation and configuration
- [User Guide](docs/en/user-guide.md) - Detailed usage instructions
- [Docker Deployment Guide](docs/en/docker-deployment.md) - Docker environment deployment
- [Supported UPS Devices](docs/en/supported-ups.md) - Compatible device list
- [Push Notification Setup](docs/en/push-setup.md) - Notification channel configuration
- [Plugin Development Guide](docs/en/development/plugin-dev.md) - Custom plugin development
- [Architecture](docs/en/architecture.md) - System architecture and technical details
- [FAQ](docs/en/faq.md) - Frequently asked questions
- [Changelog](docs/en/changelog.md) - Version history

## 🛠️ 技术栈 / Tech Stack

### 后端 / Backend
- **语言 / Language**: Python 3.11+
- **框架 / Framework**: FastAPI + Uvicorn
- **依赖管理 / Dependency Management**: uv
- **数据库 / Database**: SQLite + aiosqlite
- **UPS 通信 / UPS Communication**: Network UPS Tools (NUT)
- **系统集成 / System Integration**: gRPC (LZCOS API)

### 前端 / Frontend
- **框架 / Framework**: Vue 3 (Composition API)
- **语言 / Language**: TypeScript
- **构建工具 / Build Tool**: Vite
- **包管理器 / Package Manager**: pnpm
- **图表 / Charts**: ECharts
- **状态管理 / State Management**: Pinia
- **路由 / Router**: Vue Router

### 部署 / Deployment
- **容器化 / Containerization**: Docker + Docker Compose
- **打包格式 / Package Format**: 懒猫原生应用 lpk 格式 / LazyCAT native lpk format（懒猫微服专用 / LazyCAT exclusive）
- **反向代理 / Reverse Proxy**: Nginx

## 🏗️ 项目结构 / Project Structure

```
ups-guard/
├── backend/              # Python FastAPI 后端 / Python FastAPI Backend
│   ├── src/
│   │   ├── api/          # REST API 端点 / REST API Endpoints
│   │   ├── db/           # 数据库模型和 schema / Database models and schema
│   │   ├── models/       # Pydantic 数据模型 / Pydantic data models
│   │   ├── plugins/      # 通知插件 / Notification plugins
│   │   ├── services/     # 核心业务逻辑 / Core business logic
│   │   └── main.py       # 应用入口 / Application entry
│   ├── Dockerfile
│   └── pyproject.toml    # uv 依赖配置 / uv dependency config
├── frontend/             # Vue 3 前端 / Vue 3 Frontend
│   ├── src/
│   │   ├── components/   # UI 组件 / UI Components
│   │   ├── composables/  # 组合式函数 / Composables
│   │   ├── views/        # 页面视图 / Page Views
│   │   ├── router/       # 路由配置 / Router config
│   │   └── stores/       # 状态管理 / State management
│   ├── Dockerfile
│   └── package.json
├── nut/                  # NUT Server 容器 / NUT Server Container
│   ├── Dockerfile
│   └── entrypoint.sh
├── deploy/               # 部署配置文件 / Deployment configs
│   ├── docker/           # 通用 Docker 部署 / Universal Docker deployment
│   ├── lazycat/          # 懒猫微服部署 / LazyCAT deployment
│   ├── synology/         # 群晖 NAS 部署 / Synology NAS deployment
│   └── qnap/             # 威联通 NAS 部署 / QNAP NAS deployment
└── docs/                 # 文档 / Documentation
```

## 🔧 开发 / Development

### 本地开发环境 / Local Development Environment

```bash
# 克隆仓库 / Clone repository
git clone https://github.com/KingBoyAndGirl/ups-guard.git
cd ups-guard

# 启动后端（Mock 模式）/ Start backend (Mock mode)
cd backend
uv sync
MOCK_MODE=true uvicorn src.main:app --reload

# 启动前端 / Start frontend
cd frontend
pnpm install
pnpm dev
```

访问 `http://localhost:5173` 查看前端。

Visit `http://localhost:5173` to view the frontend.


### 构建应用 / Build Application

```bash
# 构建 Docker 镜像（通用）/ Build Docker images (universal)
docker-compose build

# 懒猫微服打包（需安装 lzc-cli）/ LazyCAT packaging (requires lzc-cli)
cd deploy/lazycat
lzc-cli package -m lzc-manifest.yml -o ups-guard.lpk
```

## 🤝 贡献 / Contributing

欢迎贡献代码、报告问题或提出建议！

Contributions, bug reports, and suggestions are welcome!

1. Fork 本仓库 / Fork the repository
2. 创建功能分支 / Create feature branch (`git checkout -b feature/AmazingFeature`)
3. 提交更改 / Commit changes (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 / Push to branch (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request / Open a Pull Request

请确保 / Please ensure:
- 遵循现有代码风格 / Follow existing code style
- 添加必要的测试 / Add necessary tests
- 更新相关文档 / Update relevant documentation
- 圈复杂度不超过 20 / Cyclomatic complexity not exceeding 20

## 📄 开源协议 / License

本项目采用 **AGPL-3.0 + 商业授权双协议**模式。

This project uses a **dual-licensing model: AGPL-3.0 + Commercial License**.

- **AGPL-3.0**: 个人使用和开源项目免费，需遵守开源协议 / Free for personal use and open source projects, must comply with open source license
- **商业授权 / Commercial License**: 闭源商业使用需获得商业授权 / Closed-source commercial use requires a commercial license

详见 / See:
- [AGPL-3.0 协议 / AGPL-3.0 License](LICENSE)
- [商业授权协议 / Commercial License](COMMERCIAL_LICENSE.md)

## 🙏 致谢 / Acknowledgments

- [Network UPS Tools](https://networkupstools.org/) - UPS 通信协议 / UPS communication protocol
- [FastAPI](https://fastapi.tiangolo.com/) - 现代 Python Web 框架 / Modern Python web framework
- [Vue.js](https://vuejs.org/) - 渐进式 JavaScript 框架 / Progressive JavaScript framework
- [ECharts](https://echarts.apache.org/) - 数据可视化图表库 / Data visualization chart library

## ☕ 赞助支持 / Sponsor & Support

如果这个项目对您有帮助，欢迎请作者喝杯咖啡 ☕

If this project is helpful to you, feel free to buy the author a coffee ☕

<img width="200" alt="支付宝收款码 / Alipay QR Code" src="https://github.com/user-attachments/assets/4650e388-2609-4361-bbab-b5d8137b6027" />
<img width="200" alt="微信收款码 / WeChat QR Code" src="https://github.com/user-attachments/assets/ee8f766c-e357-4e4e-8897-f2baff58867b" />

> 💖 您的支持是项目持续更新的动力！/ Your support keeps the project going!

## 📧 联系我们 / Contact Us

- GitHub: [@KingBoyAndGirl](https://github.com/KingBoyAndGirl)
- Issues: [提交问题 / Submit Issues](https://github.com/KingBoyAndGirl/ups-guard/issues)
- Discussions: [参与讨论 / Join Discussions](https://github.com/KingBoyAndGirl/ups-guard/discussions)

---

## ⭐ Star History

<a href="https://star-history.com/#KingBoyAndGirl/ups-guard&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=KingBoyAndGirl/ups-guard&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=KingBoyAndGirl/ups-guard&type=Date" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=KingBoyAndGirl/ups-guard&type=Date" />
 </picture>
</a>

---

如果这个项目对您有帮助，请给个 ⭐️ Star 支持一下！

If this project helps you, please give it a ⭐️ Star!

