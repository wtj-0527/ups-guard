# UPS Guard - User Guide

Welcome to **UPS Guard**! This is an intelligent UPS power management system that automatically monitors UPS status and safely shuts down managed devices during power outages.

---

## 📚 Table of Contents

- [Quick Start](#quick-start)
- [Deployment Methods](#deployment-methods)
- [UPS Connection Configuration](#ups-connection-configuration)
- [Managed Devices Configuration](#managed-devices-configuration)
- [Notification Channel Configuration](#notification-channel-configuration)
- [WOL Wake Configuration](#wol-wake-configuration)
- [Typical Use Cases](#typical-use-cases)
- [Test Mode Explanation](#test-mode-explanation)
- [Troubleshooting FAQ](#troubleshooting-faq)
- [Developer Guide](#developer-guide)

---

## 🚀 Quick Start

### 5 Steps to Get Started

1. **Deploy System**
   ```bash
   # Docker Compose deployment (Recommended)
   docker-compose up -d
   ```

2. **Access Interface**
   - Open browser and visit: `http://YOUR_IP` (default port 80, configurable via `HTTP_PORT` in `.env`)
   - API Token required on first access (check container logs after first startup)

3. **Configure UPS**
   - Go to "Settings" page
   - Configure NUT server connection information
   - Set shutdown policy (wait time, battery threshold, etc.)

4. **Add Managed Devices**
   - In "Settings → Pre-shutdown Tasks" add devices
   - Configure SSH connection information
   - Test connection

5. **Test Shutdown Process**
   - Use "Dry-run Mode" to test complete flow
   - Confirm all devices can connect properly
   - Switch to "Production Mode" for actual use

---

## 🔧 Deployment Methods

### Method 1: Docker Compose (Recommended)

**Use Case**: Any device with Docker (standalone server, NAS, VM, Windows, Linux, macOS, Synology, QNAP, etc.)

```bash
# Clone project
git clone https://github.com/KingBoyAndGirl/ups-guard.git
cd ups-guard/deploy/docker

# Start services
docker-compose up -d

# View logs
docker-compose logs -f backend
```

**Service Description**:
- `nut-server`: NUT server (requires USB access permissions)
- `backend`: Python FastAPI backend
- `frontend`: Nginx frontend

**Port Mapping**:
- `80`: Web interface (default, configurable via `HTTP_PORT` environment variable)
- `3493`: NUT server (for other devices to connect)

### Method 2: LazyCAT Deployment

**Use Case**: LazyCAT environment

1. Package project as LazyCAT application
2. Build image using `deploy/lazycat/lzc-build.yml`
3. Install via LazyCAT App Store

**Advantages**:
- Automatic container lifecycle management
- Supports gRPC shutdown (LazyCAT exclusive feature)
- Integrated with LazyCAT notification system

### Method 3: Direct Execution

**Use Case**: Development testing, lightweight deployment

```bash
# Install dependencies (using uv)
cd backend
uv sync

# Start backend
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000

# Start frontend (another terminal)
cd frontend
pnpm install
pnpm dev
```

---

## 🔌 UPS Connection Configuration

### NUT (Network UPS Tools) Configuration

UPS Guard uses NUT protocol to communicate with UPS.

#### 1. Confirm UPS Connection

```bash
# Check USB connection
lsusb

# Should see similar output:
# Bus 001 Device 003: ID 051d:0002 American Power Conversion Uninterruptible Power Supply
```

#### 2. Configure NUT Server

Edit `nut/ups.conf`:

```ini
[ups]
    driver = usbhid-ups
    port = auto
    desc = "My UPS"
```

Edit `nut/upsd.users`:

```ini
[monuser]
    password = secret
    upsmon master
```

#### 3. Web Interface Configuration

Go to "Settings" page and configure:

- **NUT Server Address**: `nut-server` (Docker) or `localhost` (direct execution)
- **Port**: `3493` (default)
- **Username**: `monuser`
- **Password**: Password set in config file
- **UPS Name**: `ups` (corresponds to name in ups.conf)

#### 4. Test Connection

- View UPS status in dashboard
- Should see battery charge, input voltage, etc.

---

## 💻 Managed Devices Configuration

### Supported Device Types

| Type | Icon | Protocol | Description |
|------|------|------|------|
| Linux/macOS | 🖥️ | SSH | Execute shutdown via SSH |
| Windows | 💻 | SSH/WinRM | PowerShell remote shutdown |
| Synology | 📦 | SSH/API | Synology NAS |
| QNAP | 📦 | SSH/API | QNAP NAS |
| HTTP API | 🌐 | HTTP | Custom HTTP interface |
| Custom Script | 📜 | Shell | Execute local script |
| LazyCAT | 🐱 | SSH/gRPC | LazyCAT system shutdown (supports dedicated gRPC interface) |

### SSH Remote Shutdown (Linux/macOS)

#### Configuration Steps

1. **Go to Settings → Pre-shutdown Tasks → Add Device**

2. **Select "SSH Remote Shutdown (Linux/macOS)"**

3. **Fill in Connection Info**:
   - **Device Name**: `Ubuntu Server`
   - **Host Address**: `192.168.1.100`
   - **SSH Port**: `22`
   - **Username**: `root`
   - **Authentication**: Password or private key
   - **Shutdown Command**: `sudo shutdown -h now`

4. **Advanced Options**:
   - **Pre-shutdown Command**: Command to execute before shutdown (e.g., stop Docker containers)
   ```bash
   docker stop $(docker ps -q)
   systemctl stop nginx
   ```
   - **MAC Address**: For Wake On LAN (optional)
   - **Priority**: Lower numbers shutdown first

5. **Test Connection**

#### Permission Configuration

If using non-root user, configure passwordless sudo:

```bash
# Edit sudoers
sudo visudo

# Add following line (assuming username is upsmgr)
upsmgr ALL=(ALL) NOPASSWD: /sbin/shutdown
```

### Windows Remote Shutdown

#### Prerequisites

1. **Enable OpenSSH Server** (Windows 10/11/Server 2019+)
   ```powershell
   # Run as administrator
   Add-WindowsCapability -Online -Name OpenSSH.Server
   Start-Service sshd
   Set-Service -Name sshd -StartupType 'Automatic'
   ```

2. **Configure PowerShell as Default Shell**
   ```powershell
   New-ItemProperty -Path "HKLM:\SOFTWARE\OpenSSH" -Name DefaultShell -Value "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" -PropertyType String -Force
   ```

#### UPS Guard Configuration

- **Device Type**: Windows Remote Shutdown
- **Host Address**: `192.168.1.101`
- **Username**: `Administrator`
- **Authentication**: Password
- **Shutdown Command**: `shutdown /s /t 0 /f`

### Synology NAS

#### SSH Configuration

1. **Enable SSH**:
   - Control Panel → Terminal & SNMP → Enable SSH service

2. **UPS Guard Configuration**:
   - **Device Type**: Synology NAS
   - **Host Address**: NAS IP
   - **Username**: `admin`
   - **Authentication**: Password
   - **Shutdown Command**: `sudo poweroff`

#### API Configuration (Optional)

Use Synology DSM API:

- **Device Type**: HTTP API
- **Request Method**: `POST`
- **URL**: `https://YOUR_NAS:5001/webapi/entry.cgi`
- **Request Body**:
  ```json
  {
    "api": "SYNO.Core.System",
    "method": "shutdown",
    "version": 1
  }
  ```

### QNAP NAS

Configuration similar to Synology:

- **Enable SSH**: System Administration → Network Services → Telnet/SSH
- **Shutdown Command**: `poweroff`

### HTTP API

For devices with HTTP shutdown interface:

```json
{
  "method": "POST",
  "url": "http://192.168.1.200:8080/api/shutdown",
  "headers": {
    "Authorization": "Bearer YOUR_TOKEN"
  },
  "body": {
    "action": "shutdown"
  }
}
```

### Custom Script

Execute local Shell script:

```bash
#!/bin/bash
# /opt/scripts/shutdown-device.sh

# Send MQTT message
mosquitto_pub -h mqtt.local -t device/shutdown -m '{"id": "device1"}'

# Call custom API
curl -X POST http://device.local/shutdown
```

---

## 🔔 Notification Channel Configuration

Supports multiple notification methods, can configure multiple channels simultaneously.

### ServerChan

- **Get SendKey**: https://sct.ftqq.com/
- **Configuration**:
  - SendKey: `SCTxxx...`

### PushPlus

- **Get Token**: http://www.pushplus.plus/
- **Configuration**:
  - Token: `xxx...`

### DingTalk Group Bot

1. Create DingTalk group bot
2. Get Webhook URL
3. Configure keyword: `UPS`

### Telegram Bot

1. Create Bot: https://t.me/BotFather
2. Get Bot Token
3. Get Chat ID
4. Configure:
   - Bot Token: `123456:ABC-DEF...`
   - Chat ID: `123456789`

### Email

- **SMTP Server**: `smtp.gmail.com`
- **Port**: `587` (TLS)
- **Username**: Email address
- **Password**: App-specific password
- **Recipient**: Email to receive notifications

### Custom Webhook

Send JSON POST request to custom URL:

```json
{
  "event": "POWER_LOST",
  "message": "Power outage, UPS switched to battery power",
  "timestamp": "2026-02-11T12:00:00Z",
  "ups_status": {
    "battery_charge": 100,
    "battery_runtime": 3600
  }
}
```

---

## ⚡ WOL Wake Configuration

### Configuration Steps

#### 1. Ensure UPS Supports Auto Power-On After Restoration

Most UPS have two modes:
- **Auto power-on after power restoration**: Recommended setting
- **Stay off after power restoration**: Requires manual power-on

Setting method:
- APC UPS: LCD panel → Configuration → Auto Startup
- Other brands: Refer to UPS manual

#### 2. Enable WOL in Target Device BIOS

Enter BIOS settings:

**Desktop/Server**:
- Find Power Management or Advanced menu
- Enable "Wake On LAN", "Power On By PCI-E Device" options
- Save and restart

**Laptop**:
- Some laptops don't support WOL
- Need power adapter connected

#### 3. Operating System Configuration

**Windows**:
```powershell
# Enable NIC WOL
# Device Manager → Network Adapters → Properties → Advanced → Enable "Magic Packet Wake"
# Power Management → Allow this device to wake the computer
```

**Linux**:
```bash
# Install ethtool
sudo apt install ethtool

# Enable WOL
sudo ethtool -s eth0 wol g

# Permanently enable (add to /etc/network/interfaces or systemd)
```

**macOS**:
```bash
# System Preferences → Energy Saver → Wake for network access
```

#### 4. Get MAC Address

**Windows**:
```cmd
ipconfig /all
# or
getmac
```

**Linux/macOS**:
```bash
ip link show
# or
ifconfig
```

**Synology**:
- Control Panel → Network → Network Interface → Properties

**QNAP**:
- System Administration → Network → Interface

#### 5. UPS Guard Configuration

In "Settings → Auto Wake on Power Restoration" configure:

- **Enable WOL**: On
- **WOL Delay**: 60 seconds (wait for network devices to start first)

Fill in each device's configuration:

- **MAC Address**: `AA:BB:CC:DD:EE:FF` (required)
- **Broadcast Address**: `255.255.255.255` (default)

**Advanced Configuration**:

If UPS Guard and target device are on different subnets, configure directed broadcast:
- Target device IP: `192.168.2.100`
- Subnet mask: `255.255.255.0`
- Broadcast address: `192.168.2.255`

#### 6. Test WOL

**Method 1: Manual Wake-Up (Recommended for Testing)**

1. Manually shutdown target device (complete shutdown, not sleep or hibernate)
2. In UPS Guard dashboard, locate the offline device card
3. Click the **"⏻ Wake"** button on the device card
4. Wait 10-30 seconds, device should auto power-on
5. Once device is online, WOL function is working correctly

**Method 2: Simulate Auto Wake After Power Restoration**

1. Ensure WOL settings are configured (Enable WOL + MAC address configured)
2. Shutdown target device
3. Simulate power restoration in UPS Guard:
   - If UPS is on battery power, wait for power restoration
   - Or use test mode to trigger power restoration event
4. System will automatically send WOL wake packets after specified delay
5. Confirm device auto powers on

**Notes**:
- Manual wake-up requires MAC address to be configured
- Device must be completely shutdown, sleep/hibernate may not respond to WOL
- If wake fails, check BIOS WOL settings and network connection
- Auto wake-up checks voltage stability first (3 consecutive checks, 5-second interval)
- Voltage stability check auto-adapts to AC/DC UPS: AC UPS checks 190V-250V, DC UPS (e.g., Wali W120) checks 10V-30V

#### 7. WOL Test Communication Flow Detailed Guide

**Applicable Scenario**: Mixed network environment (Wired + Wireless)

This section explains how to test WOL in a mixed network using a typical configuration:
- **LazyCAT Microservice** (running UPS Guard): Wired connection to router
- **Target PC**: Wireless connection to router
- **H3C Router**: Connecting UPS Guard and target device

**Network Topology**:
```
UPS ─────┐
         │
    [LazyCAT]──Wired──┐
                      │
                  [H3C Router]
                      │
                      └──Wireless──[Target PC]
```

**Test Steps**:

**Step 1: Confirm Network Configuration**

1. Log into LazyCAT, confirm IP address:
   ```bash
   ip addr show
   # or
   ifconfig
   ```
   Record LazyCAT's IP, e.g.: `192.168.1.100`

2. With target PC powered on, confirm its IP and MAC address:
   
   Windows:
   ```cmd
   ipconfig /all
   ```
   
   Linux/Mac:
   ```bash
   ip addr show
   # or
   ifconfig
   ```
   
   Record **wireless adapter's** MAC address, e.g.: `AA:BB:CC:DD:EE:FF`
   Record PC's IP, e.g.: `192.168.1.101`

3. Confirm both devices are on the same subnet:
   ```bash
   # From LazyCAT, ping target PC
   ping 192.168.1.101
   ```
   
   If ping succeeds, network connectivity is OK.

**Step 2: Router Settings**

1. Log into H3C router management interface (usually `192.168.1.1`)

2. Confirm the following settings:
   - **Wireless Network**: Ensure AP Isolation is disabled
   - **Firewall**: Allow UDP port 9 (used by WOL)
   - **DHCP**: Recommend setting static IP binding for target PC (based on MAC address)

3. If router supports it, enable "LAN Wake-up" or "WOL Pass-through" feature

**Step 3: Configure Target PC's WOL**

Refer to previous sections "Enable WOL in Target Device BIOS" and "Operating System Configuration".

Special notes:
- Windows wireless adapter: Ensure "Allow this device to wake the computer" is enabled in Device Manager
- Some wireless adapters may not support WOL; recommend using wired adapter or check adapter specs

**Step 4: Configure in UPS Guard**

1. Go to "Settings → Pre-Shutdown Hooks"
2. Add or edit target PC configuration
3. Fill in **MAC Address**: `AA:BB:CC:DD:EE:FF` (wireless adapter's MAC)
4. Fill in **Broadcast Address**:
   - If same subnet (e.g., both 192.168.1.x/24): Use `192.168.1.255`
   - Or use global broadcast: `255.255.255.255` (recommended to start with this)

**Step 5: Test WOL Wake-up**

1. **Manual Test** (Recommended):
   
   a. Completely shutdown target PC (not sleep or hibernate)
   
   b. Locate device in UPS Guard dashboard
   
   c. Click **"⏻ Wake"** button
   
   d. Check logs: View logs on LazyCAT
      ```bash
      docker logs ups-guard-backend | grep -i wol
      ```
   
   e. Wait 10-30 seconds, check if PC powers on

2. **Command Line Test** (Verify network connectivity):
   
   Install and use `wakeonlan` tool on LazyCAT:
   ```bash
   # Install (if not already installed)
   apt-get install wakeonlan
   
   # Send WOL packet
   wakeonlan AA:BB:CC:DD:EE:FF
   
   # Or specify broadcast address
   wakeonlan -i 192.168.1.255 AA:BB:CC:DD:EE:FF
   ```
   
   If command line can wake the device, network configuration is correct; check UPS Guard settings.

**Step 6: Troubleshooting**

If WOL doesn't work, check in this order:

1. **Check PC BIOS Settings**
   - Restart PC, enter BIOS
   - Confirm "Wake On LAN" or "Power On by PCI-E" is enabled
   - Save and exit

2. **Check MAC Address is Correct**
   - MAC address must be the **wireless adapter's** address
   - Confirm format is correct (can use colons or hyphens as separators)

3. **Check Router Settings**
   - Some routers block communication between wireless devices by default
   - Confirm "Wireless Isolation" or "AP Isolation" is disabled
   - Check firewall rules aren't blocking UDP port 9

4. **Check Network Card Driver**
   - Windows: Update wireless adapter driver to latest version
   - Some wireless adapters may not support WOL (especially USB wireless adapters)
   - Recommend checking adapter specs to confirm WOL support

5. **Try Wired Connection**
   - If wireless WOL always fails
   - Try connecting PC with ethernet cable for testing
   - Wired connection WOL support is more reliable

6. **Check UPS Guard Logs**
   ```bash
   # View backend logs
   docker logs ups-guard-backend -f
   
   # When triggering WOL, should see messages like:
   # "WOL magic packet sent to AA:BB:CC:DD:EE:FF via 192.168.1.255:9"
   # "Voltage stability confirmed: 3 consecutive checks passed"
   ```

**Success Indicators**:
- ✅ UPS Guard logs show "WOL magic packet sent"
- ✅ PC powers on automatically within 10-30 seconds
- ✅ PC connects to network normally after boot
- ✅ Dashboard shows device change from offline to online

**Common Questions**:

Q: Why is wireless WOL harder than wired?
A: Some wireless adapters don't listen to network when powered off, or router's wireless isolation blocks broadcast packets.

Q: LazyCAT uses wired, PC uses wireless, can it wake?
A: Yes, as long as:
   1. Router doesn't have wireless isolation enabled
   2. PC's wireless adapter supports WOL
   3. Correct broadcast address is used

Q: Do I need port forwarding on router?
A: No. WOL uses LAN broadcast, doesn't need port forwarding.

Q: How to confirm wireless adapter supports WOL?
A: 
- Windows: Device Manager → Network Adapters → Properties → Advanced → Look for "Wake on Magic Packet"
- Linux: `ethtool <interface>` → Check "Supports Wake-on" field
- Check adapter specification manual

---

## 📋 Typical Use Cases

### Scenario 1: Home NAS + PC (1 UPS Managing 2-3 Devices)

**Device List**:
- 1 Synology NAS
- 1 Windows PC
- 1 Linux server

**Configuration Recommendations**:

1. **Deploy UPS Guard on**: Synology NAS (Docker) or any device

2. **Shutdown Priority**:
   - Priority 1: Windows PC
   - Priority 2: Linux server
   - Priority 3: Synology NAS (if UPS Guard runs on NAS, shutdown last)

3. **Shutdown Policy**:
   - Wait time: 3 minutes
   - Battery threshold: 30%
   - Runtime threshold: 5 minutes

4. **WOL Configuration**: Configure MAC address for all devices, auto wake on power restoration

### Scenario 2: Small Office (1 UPS Managing 10+ Devices)

**Device List**:
- 2 Linux servers
- 8 Windows PCs
- 1 Synology NAS
- Router, switch (unmanaged, independent UPS)

**Configuration Recommendations**:

1. **Deploy UPS Guard on**: Independent Linux server or NAS

2. **Shutdown Priority**:
   - Priority 1-2: Linux application servers (sorted by dependency)
   - Priority 3-10: Windows PCs (parallel shutdown)
   - Priority 11: Synology NAS
   - Priority 12: UPS Guard host

3. **Shutdown Policy**:
   - Wait time: 2 minutes (office UPS has shorter runtime)
   - Battery threshold: 25%
   - Runtime threshold: 3 minutes

4. **Notification Configuration**:
   - DingTalk group notification
   - Email notification to IT admin

### Scenario 3: Mixed Environment (Windows + Linux + NAS + Other Devices)

**Device List**:
- 1 Windows Server
- 1 Linux server
- 1 Synology NAS
- 1 QNAP NAS

**Configuration Recommendations**:

1. **Deploy UPS Guard on**: Any device (e.g., Linux server or Synology NAS)

2. **Shutdown Method**:
   - All devices: Use SSH shutdown (universal method)
   - If deployed on LazyCAT, LazyCAT can use gRPC shutdown (LazyCAT exclusive feature)

3. **Shutdown Priority**:
   - Priority 1: Windows Server
   - Priority 2: Linux server
   - Priority 3: QNAP NAS
   - Priority 4: Synology NAS (if UPS Guard runs on this device, shutdown last)

4. **Special Configuration**:
   - Use "host" marker to identify device currently running UPS Guard (can be any device)
   - Set host device to shutdown last

### Scenario 4: Pure Docker Environment

**Device List**:
- 1 Docker host (running UPS Guard)
- Multiple Docker containers as "virtual devices"

**Configuration Recommendations**:

1. **Deploy UPS Guard on**: Docker Compose

2. **Managed "Devices" are Actually Containers**:
   - Use "Custom Script" Hook
   - Script content: `docker stop container_name`

3. **Shutdown Order**:
   - Sort by container dependencies
   - Finally shutdown Docker daemon
   - Finally shutdown host

---

## 🧪 Test Mode Explanation

### Three Modes

| Mode | Description | UPS Connection | Execute Shutdown | Use Case |
|------|------|----------|----------|----------|
| **Production** | Normal operation | ✅ | ✅ | Production environment |
| **Dry-Run** | Connect real UPS | ✅ | ❌ | Test flow, no actual shutdown |
| **Mock** | Simulate all operations | ❌ | ❌ | Development testing |

### Dry-Run Mode

**Purpose**: Test shutdown flow without actual shutdown

**Behavior**:
- ✅ Connect to real UPS
- ✅ Execute device connectivity tests
- ✅ Send notifications
- ❌ Don't execute actual shutdown commands
- ❌ Don't send WOL

**How to Enable**:
- Settings → System Configuration → Test Mode → Select "Dry-Run Mode"

**Usage Recommendations**:
1. Use dry-run mode for first deployment test
2. Click "Shutdown Now" in dashboard
3. Observe shutdown flow (device connection, notifications, etc.)
4. Switch to production mode after confirming everything is correct

### Mock Mode (Complete Simulation)

**Purpose**: Don't connect to real UPS, for development testing

**Behavior**:
- ❌ Don't connect to UPS (use simulated data)
- ❌ Don't execute device operations
- ✅ Frontend interface displays normally

**How to Enable**:
- Environment variable: `MOCK_MODE=true`

---

## ❓ Troubleshooting FAQ

### Q1: UPS Status Shows "Offline"

**Possible Causes**:
1. NUT configuration error
2. UPS not connected or USB permission issue
3. Docker container not mounting USB device

**Solutions**:
```bash
# Check USB device
lsusb

# Check NUT service logs
docker-compose logs nut-server

# Manually test NUT connection (list discovered UPS first, then query details)
upsc -l localhost
upsc <discovered_ups_name>@localhost
```

### Q2: Device Connection Test Failed

**Possible Causes**:
1. SSH port not open
2. Incorrect username/password
3. Firewall blocking
4. SSH key format error

**Solutions**:
```bash
# Manually test SSH connection
ssh user@host -p 22

# Check firewall
sudo ufw status

# Test network connectivity
ping host
telnet host 22
```

### Q3: Device Not Waking After Shutdown

**Possible Causes**:
1. BIOS WOL not enabled
2. Incorrect MAC address
3. Network devices not restored
4. NIC driver doesn't support WOL

**Solutions**:
1. Confirm BIOS settings
2. Manually test WOL:
   ```bash
   # Linux
   sudo apt install wakeonlan
   wakeonlan AA:BB:CC:DD:EE:FF
   
   # Windows
   # Use WakeMeOnLan tool
   ```
3. Increase WOL delay time

### Q4: LazyCAT gRPC Shutdown Failed

**Possible Causes**:
1. gRPC Socket permission issue
2. LazyCAT version incompatibility

**Solutions**:
```bash
# Check Socket file
ls -la /lzcapp/run/sys/lzc-apis.socket

# Check container mount
docker inspect ups-guard-backend | grep Mounts
```

### Q5: Notifications Not Sent

**Possible Causes**:
1. Notification channel configuration error
2. Token/Key expired
3. Network issue

**Solutions**:
1. Use "Test Notification" function
2. Check backend logs
3. Confirm API Token validity

---

## 🛠️ Developer Guide

### Plugin Development

#### Create New Hook Plugin

```python
# backend/src/hooks/my_device.py

from hooks.base import PreShutdownHook
from hooks.registry import registry

class MyDeviceHook(PreShutdownHook):
    """Custom device Hook"""
    
    hook_id = "my_device"
    hook_name = "My Device"
    hook_description = "Custom device shutdown plugin"
    
    @classmethod
    def get_config_schema(cls):
        return [
            {
                "key": "host",
                "label": "Host Address",
                "type": "text",
                "required": True
            }
        ]
    
    def validate_config(self):
        if not self.config.get("host"):
            raise ValueError("Host address cannot be empty")
    
    async def test_connection(self) -> bool:
        # Test connection logic
        return True
    
    async def execute(self) -> bool:
        # Execute shutdown logic
        return True

# Auto register
registry.register_hook(MyDeviceHook)
```

#### Create Notification Plugin

```python
# backend/src/plugins/notifiers/my_notifier.py

from plugins.base import NotifierPlugin
from plugins.registry import registry

class MyNotifier(NotifierPlugin):
    """Custom notification plugin"""
    
    plugin_id = "my_notifier"
    plugin_name = "My Notifier"
    plugin_description = "Custom notification channel"
    
    @classmethod
    def get_config_schema(cls):
        return [
            {
                "key": "api_key",
                "label": "API Key",
                "type": "password",
                "required": True
            }
        ]
    
    async def send_notification(self, event_type: str, message: str) -> bool:
        # Send notification logic
        return True

registry.register_notifier(MyNotifier)
```

### API List

The business HTTP APIs below require the `Authorization: Bearer YOUR_TOKEN` header;
`GET /health` is public. WebSocket connections authenticate with the `token` query
parameter; use `wss://` for HTTPS deployments. HTTP endpoints are also listed in
`/docs` and `/openapi.json`.

#### Configuration API

```bash
# Get configuration
GET /api/config

# Update configuration
PUT /api/config

# Test notification
POST /api/config/test-notify
```

#### UPS Status API

```bash
# Get UPS status (HTTP)
GET /api/status

# Get UPS status (WebSocket)
ws://localhost:8000/api/ws?token=YOUR_TOKEN

# List UPS devices in NUT (not real-time status)
GET /api/ups/list

# Immediate shutdown
POST /api/actions/shutdown

# Cancel shutdown
POST /api/actions/cancel-shutdown
```

`GET /api/ups` is not a registered status endpoint and returns HTTP 404 after
authentication. `GET /api/status` returns HTTP 503 if the monitor is not initialized
or UPS data is unavailable. WebSocket status messages have type `status_update`
and carry the status in the `data` field.

#### Device Management API

```bash
# Get device list
GET /api/devices

# Get device status
GET /api/devices/status

# Device shutdown
POST /api/devices/{index}/shutdown

# Send WOL
POST /api/devices/{index}/wake

# View device logs
POST /api/devices/{index}/logs
```

#### Hook API

```bash
# List available plugins
GET /api/hooks/plugins

# Test single Hook
POST /api/hooks/test

# Batch get Hook status
GET /api/hooks/status
```

---

## 📞 Support & Feedback

- **GitHub Issues**: https://github.com/KingBoyAndGirl/ups-guard/issues
- **Documentation**: https://github.com/KingBoyAndGirl/ups-guard/blob/main/README.md

---

## 📄 License

This project uses AGPL-3.0 license. Contact us for commercial licensing.

---

**Thank you for using UPS Guard!** 🎉
