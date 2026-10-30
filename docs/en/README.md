# ⚡ UPS Guard

Universal UPS monitoring and management application that supports deployment in any Docker environment. Manage multiple devices including Windows, Linux, macOS, LazyCAT Microservices, Synology, QNAP, and more.

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](LICENSE)
[![GitHub release](https://img.shields.io/github/v/release/KingBoyAndGirl/ups-guard)](https://github.com/KingBoyAndGirl/ups-guard/releases)
[![Version](https://img.shields.io/badge/version-1.0.0-brightgreen.svg)](https://github.com/KingBoyAndGirl/ups-guard/releases/tag/v1.0.0)

## ✨ Features

### v1.0 Official Release 🎉
- 🔒 **Security Hardening** - API Token authentication, sensitive data encryption, CORS restrictions
- 🌍 **Internationalization** - Bilingual interface and notifications (English/Chinese)
- 📈 **Performance Optimization** - SQLite WAL mode, data downsampling, lazy loading
- 🛡️ **Error Recovery** - gRPC/NUT auto-reconnect, transaction protection, detailed logging
- 🐳 **Deployment Optimization** - Multi-stage builds, health checks, lightweight images
- 🌙 **Dark Mode** - Light/Dark/Auto themes with full component support
- 📱 **Mobile Responsive** - Complete responsive design for phones, tablets, and desktops
- 📊 **Data Management** - Visualize database size and records, one-click history cleanup
- 🔔 **More Notification Channels** - Added DingTalk, Telegram, Email SMTP, and generic Webhook support

### Core Features
- 🔌 **Real-time Monitoring** - WebSocket real-time UPS status updates, no refresh needed
- 🔋 **Smart Shutdown** - Auto countdown shutdown on power loss, cancels on power restoration
- 📈 **Data Visualization** - ECharts real-time charts for battery, voltage, load, and more
- 📱 **Push Notifications** - 6 notification channels: ServerChan, PushPlus, DingTalk, Telegram, Email, Webhook
- 📝 **Historical Records** - Complete event logs and metrics sampling, up to 90 days retention
- 🔧 **Flexible Configuration** - Customizable shutdown policies, notification channels, sampling intervals
- 🔌 **Plugin System** - Custom notification plugins, easily extend notification channels
- 🎨 **Modern Interface** - Vue 3 + TypeScript, clean card design, dark mode, responsive
- 🐳 **Container Deployment** - Three-service architecture, one-click install, ready to use

## 📸 Interface Preview

### Dashboard
- Real-time status monitoring (Online/Battery/Low Battery)
- Battery charge gauge
- Input/Output voltage, load percentage, temperature, and other key metrics
- Real-time data charts
- Recent events list

### Settings Page
- Shutdown policy configuration (wait time, minimum battery, final wait)
- Push notification configuration (multi-channel support)
- Data sampling and retention settings

### History
- Long-term trend charts (24 hours)
- Event timeline

## 🚀 Quick Start

### Deployment Options

UPS Guard can run on any device with Docker, connect to UPS via USB, and remotely manage other devices on the LAN:

1. **Docker Deployment** (Recommended) - Supports any device with Docker (Win11, Mac, Linux, Synology, QNAP, etc.)
2. **LazyCAT Deployment** - LazyCAT users can deploy using native application packages

### Docker Deployment (Universal)

Runs on any device with Docker (Win11, Mac, Linux, Synology, QNAP, etc.).

#### Quick Start

```bash
# 1. Clone repository
git clone https://github.com/KingBoyAndGirl/ups-guard.git
cd ups-guard/deploy/docker

# 2. Configure environment variables
cp .env.example .env
# Edit .env file, modify configuration as needed

# 3. Start services
docker-compose up -d

# 4. Access Web UI
# Open http://localhost in browser
```

For detailed Docker deployment guide, see [Docker Deployment Documentation](./docker-deployment.md).

### LazyCAT Deployment

#### System Requirements

- LazyCAT LZCOS system
- USB-capable UPS device
- At least 1GB available storage space

#### Installation Steps

1. **Download Application Package**
   ```bash
   # Download latest version from GitHub Releases
   wget https://github.com/KingBoyAndGirl/ups-guard/releases/latest/download/ups-guard.lpk
   ```

2. **Install Application**
   - Access LazyCAT control panel
   - App Store → Local Install
   - Select `ups-guard.lpk` file
   - Wait for installation to complete

3. **Connect UPS**
   - Connect UPS to LazyCAT host via USB
   - Application will auto-detect device

4. **Access Application**
   ```
   http://your-lazycat-host/ups-guard/
   ```

5. **Configure API Token (v1.0+)**
   
   On first startup, the application auto-generates an API Token and prints it in the logs. It's recommended to set the environment variable in LazyCAT control panel:
   
   - Go to application settings
   - Add environment variable `API_TOKEN=<your-token>`
   - Restart application
   
   The frontend will automatically use the configured Token for authentication.

For detailed installation guide, see [Installation Documentation](./install.md).

## ⚙️ Configuration

### Environment Variables

**NUT Configuration**
- `NUT_HOST`: NUT server address (default: `nut-server`)
- `NUT_PORT`: NUT server port (default: `3493`)
- `NUT_USERNAME`: NUT username (default: `monuser`)
- `NUT_PASSWORD`: NUT password (default: `secret`)
- `NUT_UPS_NAME`: UPS device name (default: `ups`)

**Security Configuration**
- `API_TOKEN`: API authentication token (auto-generated if not set)
- `ENCRYPTION_KEY`: Sensitive data encryption key (auto-generated and saved if not set)
- `ALLOWED_ORIGINS`: CORS allowed origins (comma-separated, default: same-origin only)

**Database Configuration**
- `DATABASE_PATH`: Database file path (default: `/data/ups_guard.db`)

**Other**
- `LOG_LEVEL`: Log level (default: `INFO`)
- `MOCK_MODE`: Development mode (default: `false`)

## 📚 Documentation

- [Installation Guide](./install.md) - Complete installation and configuration steps
- [Supported UPS Devices](./supported-ups.md) - Compatible device list
- [Push Notification Setup](./push-setup.md) - ServerChan, PushPlus configuration tutorials
- [Plugin Development Guide](./development/plugin-dev.md) - Custom notification plugin development
- [Architecture Documentation](./architecture.md) - System architecture and technical details
- [FAQ](./faq.md) - Frequently Asked Questions

## 🛠️ Tech Stack

### Backend
- **Language**: Python 3.11+
- **Framework**: FastAPI + Uvicorn
- **Dependency Management**: uv
- **Database**: SQLite + aiosqlite
- **UPS Communication**: Network UPS Tools (NUT)
- **System Integration**: gRPC (LZCOS API)

### Frontend
- **Framework**: Vue 3 (Composition API)
- **Language**: TypeScript
- **Build Tool**: Vite
- **Package Manager**: pnpm
- **Charts**: ECharts
- **State Management**: Pinia
- **Routing**: Vue Router

### Deployment
- **Containerization**: Docker + Docker Compose
- **Package Format**: LazyCAT native lpk format (LazyCAT specific)
- **Reverse Proxy**: Nginx

## 🏗️ Project Structure

```
ups-guard/
├── backend/              # Python FastAPI backend
│   ├── src/
│   │   ├── api/          # REST API endpoints
│   │   ├── db/           # Database models and schema
│   │   ├── models/       # Pydantic data models
│   │   ├── plugins/      # Notification plugins
│   │   ├── services/     # Core business logic
│   │   └── main.py       # Application entry point
│   ├── Dockerfile
│   └── pyproject.toml    # uv dependency configuration
├── frontend/             # Vue 3 frontend
│   ├── src/
│   │   ├── components/   # UI components
│   │   ├── composables/  # Composition functions
│   │   ├── views/        # Page views
│   │   ├── router/       # Router configuration
│   │   └── stores/       # State management
│   ├── Dockerfile
│   └── package.json
├── nut/                  # NUT Server container
│   ├── Dockerfile
│   └── entrypoint.sh
├── docs/                 # Documentation
├── deploy/               # Deployment configuration files
│   ├── docker/           # Universal Docker deployment
│   ├── lazycat/          # LazyCAT deployment
│   │   ├── lzc-manifest.yml  # LazyCAT application manifest
│   │   └── lzc-build.yml     # Build configuration
│   ├── synology/         # Synology NAS deployment
│   └── qnap/             # QNAP NAS deployment
```

## 🔧 Development

### Local Development Environment

```bash
# Clone repository
git clone https://github.com/KingBoyAndGirl/ups-guard.git
cd ups-guard

# Start backend (Mock mode)
cd backend
uv sync
MOCK_MODE=true uvicorn src.main:app --reload

# Start frontend
cd frontend
pnpm install
pnpm dev
```

Visit `http://localhost:5173` to view the frontend.

### Build Application

```bash
# Build Docker images (universal)
docker-compose build

# LazyCAT packaging (requires lzc-cli installation)
cd deploy/lazycat
lzc-cli package -m lzc-manifest.yml -o ups-guard.lpk
```

## 🤝 Contributing

We welcome code contributions, issue reports, and suggestions!

1. Fork this repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request

Please ensure:
- Follow existing code style
- Add necessary tests
- Update relevant documentation
- Cyclomatic complexity not exceeding 20

## 📄 License

This project uses **AGPL-3.0 + Commercial License dual licensing**.

- **AGPL-3.0**: Free for personal use and open source projects, must comply with open source license
- **Commercial License**: Required for closed-source commercial use

See:
- [AGPL-3.0 License](LICENSE)
- [Commercial License Agreement](COMMERCIAL_LICENSE.md)

## 🙏 Acknowledgments

- [Network UPS Tools](https://networkupstools.org/) - UPS communication protocol
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [Vue.js](https://vuejs.org/) - Progressive JavaScript framework
- [ECharts](https://echarts.apache.org/) - Data visualization library

## 💬 WeChat Community

Join the **UPS WeChat group** to share UPS tips, discuss deployment questions, and suggest features. Scan the QR code below with WeChat to join.

<img width="300" alt="UPS WeChat group QR code" src="../images/wechat-group.png" />

> QR code valid **before November 6, 2026**. If it has expired, please request an updated code via Issues or Discussions below.

## 📧 Contact Us

- GitHub: [@KingBoyAndGirl](https://github.com/KingBoyAndGirl)
- Issues: [Submit Issue](https://github.com/KingBoyAndGirl/ups-guard/issues)
- Discussions: [Join Discussion](https://github.com/KingBoyAndGirl/ups-guard/discussions)

---

If this project helps you, please give it a ⭐️ Star to show your support!
