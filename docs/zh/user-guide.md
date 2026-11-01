# UPS Guard - 用户指南

欢迎使用 **UPS Guard**！这是一个智能 UPS 电源管理系统，可以自动监控 UPS 状态，并在市电中断时安全关闭纳管设备。

---

## 📚 目录

- [快速开始](#快速开始)
- [部署方式](#部署方式)
- [UPS 连接配置](#ups-连接配置)
- [UPS 参数配置](#ups-参数配置)
- [纳管设备配置](#纳管设备配置)
- [通知渠道配置](#通知渠道配置)
- [WOL 唤醒配置](#wol-唤醒配置)
- [监控模式设置](#监控模式设置)
- [典型使用场景](#典型使用场景)
- [测试模式说明](#测试模式说明)
- [故障排除 FAQ](#故障排除-faq)
- [开发者指南](#开发者指南)

---

## 🚀 快速开始

### 5 步上手

1. **部署系统**
   ```bash
   # Docker Compose 部署（推荐）
   docker-compose up -d
   ```

2. **访问界面**
   - 打开浏览器访问：`http://YOUR_IP`（默认端口 80，可在 `.env` 中修改 `HTTP_PORT`）
   - 首次访问需要 API Token（首次启动后查看容器日志获取）

3. **配置 UPS**
   - 进入"设置"页面
   - 配置 NUT 服务器连接信息
   - 设置关机策略（等待时间、电量阈值等）

4. **添加纳管设备**
   - 在"设置 → 关机前置任务"中添加设备
   - 配置 SSH 连接信息
   - 测试连接是否正常

5. **测试关机流程**
   - 使用"演练模式"测试完整流程
   - 确认所有设备能正常连接
   - 切换到"生产模式"投入使用

---

## 🔧 部署方式

### 方式一：Docker Compose（推荐）

**适用场景**：任意有 Docker 的设备（独立服务器、NAS、虚拟机、Windows、Linux、macOS、群辉、威联通等）

```bash
# 克隆项目
git clone https://github.com/KingBoyAndGirl/ups-guard.git
cd ups-guard/deploy/docker

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f backend
```

**服务说明**：
- `nut-server`：NUT 服务器（需要 USB 访问权限）
- `backend`：Python FastAPI 后端
- `frontend`：Nginx 前端

**端口映射**：
- `80`：Web 界面（默认，可通过 `HTTP_PORT` 环境变量修改）
- `3493`：NUT 服务器（供其他设备连接）

### 方式二：懒猫微服部署

**适用场景**：懒猫微服（LazyCAT）环境

1. 将项目打包为懒猫应用
2. 使用 `deploy/lazycat/lzc-build.yml` 构建镜像
3. 通过懒猫应用商店安装

**优势**：
- 自动管理容器生命周期
- 支持 gRPC 关机（懒猫微服专有特性）
- 集成懒猫通知系统

### 方式三：直接运行

**适用场景**：开发测试、轻量级部署

```bash
# 安装依赖（使用 uv）
cd backend
uv sync

# 启动后端
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000

# 启动前端（另一个终端）
cd frontend
pnpm install
pnpm dev
```

---

## 🔌 UPS 连接配置

### NUT (Network UPS Tools) 配置

UPS Guard使用 NUT 协议与 UPS 通信。

#### 1. 确认 UPS 连接

```bash
# 检查 USB 连接
lsusb

# 应该能看到类似输出：
# Bus 001 Device 003: ID 051d:0002 American Power Conversion Uninterruptible Power Supply
```

#### 2. 配置 NUT 服务器

编辑 `nut/ups.conf`：

```ini
[ups]
    driver = usbhid-ups
    port = auto
    desc = "My UPS"
```

编辑 `nut/upsd.users`：

```ini
[monuser]
    password = secret
    upsmon master
```

#### 3. Web 界面配置

进入"设置"页面，配置：

- **NUT 服务器地址**：`nut-server`（Docker）或 `localhost`（直接运行）
- **端口**：`3493`（默认）
- **用户名**：`monuser`
- **密码**：配置文件中设置的密码
- **UPS 名称**：`ups`（对应 ups.conf 中的名称）

#### 4. 测试连接

- 在仪表盘查看 UPS 状态
- 应该能看到电池电量、输入电压等信息

---

## ⚙️ UPS 参数配置

### 功能说明

UPS Guard支持直接修改 UPS 硬件参数，无需使用厂商提供的专用软件。这些参数会直接写入 UPS 内部存储，断电后仍然保留。

**支持的参数**：
- **电压保护阈值**：设置高压/低压切换点，决定何时启用电池供电
- **输入灵敏度**：调节对电压波动的敏感程度
- **关机延迟**：设置 UPS 执行关机命令后的延迟时间

### 修改方式

#### 方式一：仪表盘快速修改

在仪表盘中，相关卡片支持内联编辑：

1. **电压质量卡片**
   - 点击"安全区间"旁的编辑图标 ✏️
   - 修改高压/低压阈值
   - 确认修改

2. **保护状态总览卡片**
   - 点击"输入灵敏度"旁的编辑图标 ✏️
   - 选择低/中/高三个等级
   - 确认修改

3. **关机时间线卡片**
   - 点击"UPS 关机延迟"旁的编辑图标 ✏️
   - 输入新的延迟时间（秒）
   - 确认修改

#### 方式二：设置页面统一配置

进入"设置 → UPS 高级配置"：

1. **电压保护配置**
   - 高压切换阈值：220-300V（推荐 278V）
   - 低压切换阈值：100-200V（推荐 160V）
   - 当输入电压超出此范围时，UPS 切换到电池供电

2. **灵敏度配置**
   - **低灵敏度**：适合电网质量较差的地区，容忍更大波动
   - **中灵敏度**：适合一般情况，平衡保护和稳定性
   - **高灵敏度**：适合电网稳定地区，提供最严格保护

3. **关机延迟配置**
   - 设置 0-600 秒
   - UPS 收到关机命令后等待此时间再实际关机
   - 给设备充足时间完成关机流程

### 安全机制

所有参数修改都经过严格验证：

- ✅ **白名单验证**：只允许修改安全参数
- ✅ **范围验证**：参数值必须在合理范围内
- ✅ **二次确认**：修改前显示确认对话框
- ✅ **事件记录**：所有修改都记录到事件历史
- ✅ **智能排序**：同时修改多个参数时自动优化顺序

### 操作审计

每次参数修改都会：
- 记录到事件历史（事件类型：参数修改 🔧）
- 保存修改前后的值对比
- 包含时间戳和变量名
- 可在"事件"页面查看完整历史

---

## 💻 纳管设备配置

### 支持的设备类型

| 类型 | 图标 | 协议 | 说明 |
|------|------|------|------|
| Linux/macOS | 🖥️ | SSH | 通过 SSH 执行关机命令 |
| Windows | 💻 | SSH/WinRM | PowerShell 远程关机 |
| Synology | 📦 | SSH/API | 群晖 NAS |
| QNAP | 📦 | SSH/API | 威联通 NAS |
| HTTP API | 🌐 | HTTP | 自定义 HTTP 接口 |
| 自定义脚本 | 📜 | Shell | 执行本地脚本 |
| 懒猫微服 | 🐱 | SSH/gRPC | 懒猫系统关机（支持专用 gRPC 接口） |

### SSH 远程关机 (Linux/macOS)

#### 配置步骤

1. **进入设置 → 关机前置任务 → 添加设备**

2. **选择"SSH 远程关机 (Linux/macOS)"**

3. **填写连接信息**：
   - **设备名称**：`Ubuntu Server`
   - **主机地址**：`192.168.1.100`
   - **SSH 端口**：`22`
   - **用户名**：`root`
   - **认证方式**：密码或私钥
   - **关机命令**：`sudo shutdown -h now`

4. **高级选项**：
   - **预关机命令**：关机前执行的命令（如停止 Docker 容器）
   ```bash
   docker stop $(docker ps -q)
   systemctl stop nginx
   ```
   - **MAC 地址**：用于 Wake On LAN（可选）
   - **优先级**：数字越小越优先关机

5. **测试连接**

#### 权限配置

如果使用非 root 用户，需要配置 sudo 免密：

```bash
# 编辑 sudoers
sudo visudo

# 添加以下行（假设用户名为 upsmgr）
upsmgr ALL=(ALL) NOPASSWD: /sbin/shutdown
```

### Windows 远程关机

#### 前提条件

1. **启用 OpenSSH 服务器**（Windows 10/11/Server 2019+）
   ```powershell
   # 以管理员身份运行
   Add-WindowsCapability -Online -Name OpenSSH.Server
   Start-Service sshd
   Set-Service -Name sshd -StartupType 'Automatic'
   ```

2. **配置 PowerShell 为默认 Shell**
   ```powershell
   New-ItemProperty -Path "HKLM:\SOFTWARE\OpenSSH" -Name DefaultShell -Value "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" -PropertyType String -Force
   ```

#### UPS Guard配置

- **设备类型**：Windows 远程关机
- **主机地址**：`192.168.1.101`
- **用户名**：`Administrator`
- **认证方式**：密码
- **关机命令**：`shutdown /s /t 0 /f`

### Synology NAS

#### SSH 配置

1. **启用 SSH**：
   - 控制面板 → 终端机和 SNMP → 启用 SSH 服务

2. **UPS Guard配置**：
   - **设备类型**：Synology NAS
   - **主机地址**：NAS IP
   - **用户名**：`admin`
   - **认证方式**：密码
   - **关机命令**：`sudo poweroff`

#### API 配置（可选）

使用 Synology DSM API：

- **设备类型**：HTTP API
- **请求方法**：`POST`
- **URL**：`https://YOUR_NAS:5001/webapi/entry.cgi`
- **请求体**：
  ```json
  {
    "api": "SYNO.Core.System",
    "method": "shutdown",
    "version": 1
  }
  ```

### QNAP NAS

配置方式类似 Synology：

- **启用 SSH**：系统管理 → 网络服务 → Telnet/SSH
- **关机命令**：`poweroff`

### HTTP API

适用于有 HTTP 关机接口的设备：

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

### 自定义脚本

执行本地 Shell 脚本：

```bash
#!/bin/bash
# /opt/scripts/shutdown-device.sh

# 发送 MQTT 消息
mosquitto_pub -h mqtt.local -t device/shutdown -m '{"id": "device1"}'

# 调用自定义 API
curl -X POST http://device.local/shutdown
```

---

## 🔔 通知渠道配置

支持多种通知方式，可同时配置多个渠道。

### Server酱

- **获取 SendKey**：https://sct.ftqq.com/
- **配置**：
  - SendKey：`SCTxxx...`

### PushPlus

- **获取 Token**：http://www.pushplus.plus/
- **配置**：
  - Token：`xxx...`

### 钉钉群机器人

1. 创建钉钉群机器人
2. 获取 Webhook URL
3. 配置关键词：`UPS`

### Telegram Bot

1. 创建 Bot：https://t.me/BotFather
2. 获取 Bot Token
3. 获取 Chat ID
4. 配置：
   - Bot Token：`123456:ABC-DEF...`
   - Chat ID：`123456789`

### Email

- **SMTP 服务器**：`smtp.gmail.com`
- **端口**：`587`（TLS）
- **用户名**：邮箱地址
- **密码**：应用专用密码
- **收件人**：接收通知的邮箱

### 自定义 Webhook

发送 JSON POST 请求到自定义 URL：

```json
{
  "event": "POWER_LOST",
  "message": "市电中断，UPS 切换到电池供电",
  "timestamp": "2026-02-11T12:00:00Z",
  "ups_status": {
    "battery_charge": 100,
    "battery_runtime": 3600
  }
}
```

---

## ⚡ WOL 唤醒配置

### 配置步骤

#### 1. 确保 UPS 支持来电后自动开机

大多数 UPS 有两种模式：
- **市电恢复后自动开机**：推荐设置
- **市电恢复后保持关闭**：需要手动开机

设置方法：
- APC UPS：LCD 面板 → Configuration → Auto Startup
- 其他品牌：查阅 UPS 说明书

#### 2. 启用目标设备 BIOS 中的 WOL

进入 BIOS 设置：

**台式机/服务器**：
- 找到 Power Management 或 Advanced 菜单
- 启用 "Wake On LAN"、"Power On By PCI-E Device" 等选项
- 保存并重启

**笔记本**：
- 部分笔记本不支持 WOL
- 需要连接电源适配器

#### 3. 操作系统配置

**Windows**：
```powershell
# 启用网卡 WOL
# 设备管理器 → 网络适配器 → 属性 → 高级 → 启用"魔术包唤醒"
# 电源管理 → 允许此设备唤醒计算机
```

**Linux**：
```bash
# 安装 ethtool
sudo apt install ethtool

# 启用 WOL
sudo ethtool -s eth0 wol g

# 永久启用（添加到 /etc/network/interfaces 或 systemd）
```

**macOS**：
```bash
# 系统偏好设置 → 节能 → 唤醒以供网络访问
```

#### 4. 获取 MAC 地址

**Windows**：
```cmd
ipconfig /all
# 或
getmac
```

**Linux/macOS**：
```bash
ip link show
# 或
ifconfig
```

**Synology**：
- 控制面板 → 网络 → 网络接口 → 属性

**QNAP**：
- 系统管理 → 网络 → 接口

#### 5. UPS Guard配置

在"设置 → 来电自动唤醒"中配置：

- **启用 WOL**：开启
- **WOL 延迟**：60 秒（等待网络设备先启动）

在每个设备的配置中填写：

- **MAC 地址**：`AA:BB:CC:DD:EE:FF`（必填）
- **广播地址**：`255.255.255.255`（默认）

**高级配置**：

如果 UPS Guard与目标设备在不同子网，需要配置定向广播：
- 目标设备 IP：`192.168.2.100`
- 子网掩码：`255.255.255.0`
- 广播地址：`192.168.2.255`

#### 6. 测试 WOL

**方式一：手动唤醒（推荐用于测试）**

1. 手动关闭目标设备（完全关机，不是睡眠或休眠）
2. 在 UPS Guard仪表盘中，找到离线的设备卡片
3. 点击设备卡片上的 **"⏻ 唤醒"** 按钮
4. 等待 10-30 秒，设备应该会自动开机
5. 确认设备在线后，WOL 功能正常

**方式二：模拟市电恢复自动唤醒**

1. 确保已配置 WOL 设置（启用 WOL + 配置 MAC 地址）
2. 关闭目标设备
3. 在 UPS Guard中模拟市电恢复：
   - 如果 UPS 处于电池供电状态，等待市电恢复
   - 或使用测试模式触发电源恢复事件
4. 系统会自动在指定延迟后发送 WOL 唤醒包
5. 确认设备自动开机

**注意事项**：
- 手动唤醒要求设备已配置 MAC 地址
- 设备必须完全关机，睡眠/休眠状态可能不响应 WOL
- 如果唤醒失败，检查 BIOS WOL 设置和网络连接
- 自动唤醒会先检查电压稳定性（连续 3 次检查，间隔 5 秒）
- 电压稳定性检查自动适配 AC/DC UPS：AC UPS 检查 190V-250V，DC UPS（如瓦力 W120）检查 10V-30V

#### 7. WOL 测试通信流程详解

**适用场景**：混合网络环境（有线 + 无线）

本节以实际案例说明如何在混合网络中测试 WOL，以下是典型配置：
- **懒猫微服**（运行 UPS Guard）：有线连接到路由器
- **目标 PC**：无线连接到路由器
- **H3C 路由器**：连接 UPS Guard和目标设备

**网络拓扑**：
```
UPS ─────┐
         │
    [懒猫微服]──有线──┐
                    │
                [H3C 路由器]
                    │
                    └──无线──[目标 PC]
```

**测试步骤**：

**第 1 步：确认网络配置**

1. 登录懒猫微服，确认 IP 地址：
   ```bash
   ip addr show
   # 或
   ifconfig
   ```
   记录懒猫微服的 IP，例如：`192.168.1.100`

2. 在目标 PC 开机状态下，确认其 IP 和 MAC 地址：
   
   Windows：
   ```cmd
   ipconfig /all
   ```
   
   Linux/Mac：
   ```bash
   ip addr show
   # 或
   ifconfig
   ```
   
   记录 **无线网卡** 的 MAC 地址，例如：`AA:BB:CC:DD:EE:FF`
   记录 PC 的 IP，例如：`192.168.1.101`

3. 确认两台设备在同一子网：
   ```bash
   # 在懒猫微服上 ping 目标 PC
   ping 192.168.1.101
   ```
   
   如果能 ping 通，说明网络连通性正常。

**第 2 步：路由器设置**

1. 登录 H3C 路由器管理界面（通常是 `192.168.1.1`）

2. 确认以下设置：
   - **无线网络**：确保无线隔离（AP Isolation）已关闭
   - **防火墙**：允许 UDP 9 端口（WOL 使用端口）
   - **DHCP**：建议为目标 PC 设置静态 IP 绑定（根据 MAC 地址）

3. 如果路由器支持，启用 "局域网唤醒" 或 "WOL 穿透" 功能

**第 3 步：配置目标 PC 的 WOL**

参考前面的"启用目标设备 BIOS 中的 WOL"和"操作系统配置"部分。

特别注意：
- Windows 无线网卡：确保在设备管理器中启用"允许此设备唤醒计算机"
- 某些无线网卡可能不支持 WOL，建议使用有线网卡或检查网卡规格

**第 4 步：在 UPS Guard中配置**

1. 进入"设置 → 关机前置任务"
2. 添加或编辑目标 PC 的配置
3. 填写 **MAC 地址**：`AA:BB:CC:DD:EE:FF`（无线网卡的 MAC）
4. 填写 **广播地址**：
   - 如果同子网（例如都是 192.168.1.x/24）：使用 `192.168.1.255`
   - 或使用全局广播：`255.255.255.255`（推荐从这个开始测试）

**第 5 步：测试 WOL 唤醒**

1. **手动测试**（推荐）：
   
   a. 在目标 PC 上完全关机（不是睡眠或休眠）
   
   b. 在 UPS Guard仪表盘中找到该设备
   
   c. 点击 **"⏻ 唤醒"** 按钮
   
   d. 观察日志：在懒猫微服中查看日志
      ```bash
      docker logs ups-guard-backend | grep -i wol
      ```
   
   e. 等待 10-30 秒，检查 PC 是否开机

2. **命令行测试**（验证网络连通性）：
   
   在懒猫微服上安装并使用 `wakeonlan` 工具：
   ```bash
   # 安装（如果尚未安装）
   apt-get install wakeonlan
   
   # 发送 WOL 包
   wakeonlan AA:BB:CC:DD:EE:FF
   
   # 或指定广播地址
   wakeonlan -i 192.168.1.255 AA:BB:CC:DD:EE:FF
   ```
   
   如果命令行能唤醒，说明网络配置正确，UPS Guard配置有问题。

**第 6 步：故障排查**

如果 WOL 不工作，按以下顺序检查：

1. **检查 PC BIOS 设置**
   - 重启 PC，进入 BIOS
   - 确认 "Wake On LAN" 或 "Power On by PCI-E" 已启用
   - 保存并退出

2. **检查 MAC 地址是否正确**
   - MAC 地址必须是 **无线网卡** 的地址
   - 确认格式正确（可以用冒号或短横线分隔）

3. **检查路由器设置**
   - 某些路由器默认阻止无线设备之间的通信
   - 确认"无线隔离"或"AP Isolation"已关闭
   - 检查防火墙规则是否阻止 UDP 9 端口

4. **检查网卡驱动**
   - Windows：更新无线网卡驱动到最新版本
   - 某些无线网卡可能不支持 WOL（特别是 USB 无线网卡）
   - 建议查看网卡规格确认是否支持 WOL

5. **尝试有线连接**
   - 如果无线 WOL 始终不工作
   - 可以尝试给 PC 插上网线进行测试
   - 有线连接的 WOL 支持更加可靠

6. **检查 UPS Guard日志**
   ```bash
   # 查看后端日志
   docker logs ups-guard-backend -f
   
   # 触发 WOL 时应该看到类似信息：
   # "WOL magic packet sent to AA:BB:CC:DD:EE:FF via 192.168.1.255:9"
   # "Voltage stability confirmed: 3 consecutive checks passed"
   ```

**成功标志**：
- ✅ UPS Guard日志显示 "WOL magic packet sent"
- ✅ PC 在 10-30 秒内自动开机
- ✅ PC 开机后能正常连接网络
- ✅ Dashboard 显示设备从离线变为在线

**常见问题**：

Q: 为什么无线 WOL 比有线难？
A: 某些无线网卡在关机状态下不监听网络，或者路由器的无线隔离功能阻止了广播包。

Q: 懒猫微服用有线，PC 用无线，能唤醒吗？
A: 可以，只要：
   1. 路由器没有启用无线隔离
   2. PC 的无线网卡支持 WOL
   3. 使用正确的广播地址

Q: 需要在路由器上配置端口转发吗？
A: 不需要。WOL 使用局域网广播，不需要端口转发。

Q: 如何确认无线网卡支持 WOL？
A: 
- Windows：设备管理器 → 网络适配器 → 属性 → 高级 → 查找 "Wake on Magic Packet"
- Linux：`ethtool <interface>` → 查看 "Supports Wake-on" 字段
- 查看网卡规格说明书

---

## 📡 监控模式设置

ups-guard 支持三种 UPS 状态监控模式，可根据需求选择最适合的方式。

### 监控模式说明

#### 1. 轮询模式 (Polling) 

**特点**：
- 定期主动查询 UPS 状态
- 默认间隔：5 秒
- 兼容性最好，所有 NUT 版本均支持

**优点**：
- 稳定可靠
- 兼容性强
- 配置简单

**缺点**：
- 响应延迟（最多 5 秒）
- 通信频繁（每天 17,280 次）
- 略微增加电池消耗

**适用场景**：
- NUT 版本较旧（< 2.7.4）
- 对实时性要求不高
- 需要最大兼容性

#### 2. 事件驱动模式 (Event Driven)

**特点**：
- 使用 NUT LISTEN 命令
- UPS 状态变化时主动推送
- 实时响应（毫秒级）

**优点**：
- 响应速度快（毫秒级）
- 通信次数少（仅状态变化时）
- 节省电池电量

**缺点**：
- 需要 NUT 2.7.4+ 版本
- 部分 UPS 可能不支持
- 网络故障可能导致失联

**适用场景**：
- NUT 版本较新（>= 2.7.4）
- 对实时性要求高
- 希望最大化电池续航

#### 3. 混合模式 (Hybrid) ⭐ **推荐**

**特点**：
- 事件驱动为主，轮询为辅
- 自动降级和故障恢复
- 兼具实时性和稳定性

**优点**：
- 实时响应（事件驱动）
- 稳定可靠（轮询备份）
- 通信频率低（降低 88%）
- 自动适应环境

**缺点**：
- 配置稍复杂

**适用场景**：
- **大多数用户的最佳选择**
- 追求性能和稳定性的平衡
- 不确定 NUT 版本或 UPS 支持情况

### 配置方法

1. 进入"设置"页面
2. 找到"监控参数"卡片
3. 向下滚动到"监控模式"部分

#### 基本配置

**监控模式选择**：
```
轮询模式（传统）   ← 最稳定，兼容性好
事件驱动（实时）   ← 最快速，需要新版 NUT
混合模式（推荐）   ← 平衡之选 ⭐
```

**启用事件驱动**：
- ✅ 勾选：尝试使用事件驱动
- ❌ 不勾选：仅使用轮询

#### 高级参数

**心跳间隔（秒）**：
- 作用：保持事件驱动连接活跃
- 推荐值：30-60 秒
- 说明：太短浪费资源，太长可能断连

**自动降级**：
- ✅ 推荐启用
- 作用：事件驱动失败时自动切换到轮询
- 保证监控不会中断

**降级轮询间隔（秒）**：
- 作用：降级后的轮询频率
- 推荐值：60-120 秒
- 说明：比正常轮询频率低，减少通信

### 监控统计

配置界面下方显示实时监控统计：

| 指标 | 说明 |
|------|------|
| **当前模式** | 实际运行的监控模式 |
| **今日通信次数** | 自启动以来的 NUT 通信次数 |
| **事件驱动状态** | 是否成功激活事件驱动 |
| **最后更新** | 上次收到 UPS 数据的时间 |

### 性能对比

| 模式 | 通信频率 | 响应延迟 | 日通信次数 | 电池影响 |
|------|---------|---------|-----------|---------|
| **轮询** | 5 秒/次 | 0-5 秒 | 17,280 次 | 基线 |
| **事件驱动** | 按需 | < 100ms | < 100 次 | -90% |
| **混合** | 60 秒/次 + 事件 | < 100ms | ~2,000 次 | -88% |

### 常见问题

#### Q: 如何知道我的 NUT 是否支持事件驱动？

A: 
1. 选择"混合模式"并启用事件驱动
2. 保存配置后查看"监控统计"
3. 如果"事件驱动状态"显示"✅ 活跃"，则支持
4. 如果显示"⚠️ 未激活"，则不支持或配置有误

#### Q: 混合模式下，实际使用哪种方式？

A:
- 如果事件驱动激活成功 → 主要使用事件驱动，60 秒轮询一次作为备份
- 如果事件驱动失败 → 自动降级为 60 秒轮询一次

#### Q: 通信次数会影响 UPS 电池吗？

A:
- USB 通信的功耗极低（< 0.3W）
- 对电池续航影响微乎其微（< 2%）
- 但减少通信仍然有益：降低 CPU 占用、减少日志量

#### Q: 什么时候应该使用纯轮询模式？

A:
- NUT 版本 < 2.7.4
- UPS 固件不支持 LISTEN 命令
- 网络环境不稳定
- 追求最大兼容性

#### Q: 事件驱动断连后会怎样？

A:
- 混合模式：自动切换到轮询，继续监控
- 纯事件驱动：重试 5 次，失败后停止监控（需重启服务）

### 推荐配置

#### 标准配置（推荐）
```
监控模式：混合模式
启用事件驱动：✅
心跳间隔：30 秒
自动降级：✅
降级轮询间隔：60 秒
```

#### 保守配置（兼容性优先）
```
监控模式：轮询模式
NUT 轮询间隔：5 秒
```

#### 激进配置（性能优先）
```
监控模式：事件驱动
启用事件驱动：✅
心跳间隔：60 秒
```

---

## 📋 典型使用场景

### 场景 1：家庭 NAS + PC（1 台 UPS 管 2-3 台设备）

**设备清单**：
- 1 台 Synology NAS
- 1 台 Windows PC
- 1 台 Linux 服务器

**配置建议**：

1. **UPS Guard部署在**：Synology NAS（Docker）或任意一台设备上

2. **关机优先级**：
   - 优先级 1：Windows PC
   - 优先级 2：Linux 服务器
   - 优先级 3：Synology NAS（如果 UPS Guard运行在 NAS 上，则最后关机）

3. **关机策略**：
   - 等待时间：3 分钟
   - 电量阈值：30%
   - 续航阈值：5 分钟

4. **WOL 配置**：全部设备配置 MAC 地址，来电后自动唤醒

### 场景 2：小型办公室（1 台 UPS 管 10+ 设备）

**设备清单**：
- 2 台 Linux 服务器
- 8 台 Windows PC
- 1 台 Synology NAS
- 路由器、交换机（不受控，独立 UPS）

**配置建议**：

1. **UPS Guard部署在**：独立 Linux 服务器或 NAS

2. **关机优先级**：
   - 优先级 1-2：Linux 应用服务器（按依赖关系排序）
   - 优先级 3-10：Windows PC（并行关机）
   - 优先级 11：Synology NAS
   - 优先级 12：UPS Guard宿主机

3. **关机策略**：
   - 等待时间：2 分钟（办公室 UPS 续航较短）
   - 电量阈值：25%
   - 续航阈值：3 分钟

4. **通知配置**：
   - 钉钉群通知
   - Email 通知给 IT 管理员

### 场景 3：混合环境（Windows + Linux + NAS + 其他设备）

**设备清单**：
- 1 台 Windows Server
- 1 台 Linux 服务器
- 1 台 Synology NAS
- 1 台 QNAP NAS

**配置建议**：

1. **UPS Guard部署在**：任意一台设备上（如 Linux 服务器或 Synology NAS）

2. **关机方式**：
   - 所有设备：使用 SSH 关机（通用方式）
   - 如部署在懒猫微服上，懒猫微服可使用 gRPC 关机（懒猫微服专有特性）

3. **关机优先级**：
   - 优先级 1：Windows Server
   - 优先级 2：Linux 服务器
   - 优先级 3：QNAP NAS
   - 优先级 4：Synology NAS（如果 UPS Guard运行在此设备上，则最后关机）

4. **特殊配置**：
   - 使用"宿主机"标记标识当前运行 UPS Guard 的设备（可以是任意设备）
   - 宿主机设备设置为最后关机

### 场景 4：纯 Docker 环境

**设备清单**：
- 1 台 Docker 宿主机（运行 UPS Guard）
- 多个 Docker 容器作为"虚拟设备"

**配置建议**：

1. **UPS Guard部署在**：Docker Compose

2. **纳管"设备"实际上是容器**：
   - 使用"自定义脚本" Hook
   - 脚本内容：`docker stop container_name`

3. **关机顺序**：
   - 按容器依赖关系排序
   - 最后关闭 Docker 守护进程
   - 最后关闭宿主机

---

## 🧪 测试模式说明

### 三种模式

| 模式 | 说明 | UPS 连接 | 执行关机 | 适用场景 |
|------|------|----------|----------|----------|
| **Production**（生产） | 正常运行 | ✅ | ✅ | 生产环境 |
| **Dry-Run**（演练） | 连接真实 UPS | ✅ | ❌ | 测试流程，不实际关机 |
| **Mock**（模拟） | 模拟所有操作 | ❌ | ❌ | 开发测试 |

### 演练模式（Dry-Run）

**用途**：测试关机流程，但不实际关机

**行为**：
- ✅ 连接真实 UPS
- ✅ 执行设备连通性测试
- ✅ 发送通知
- ❌ 不执行实际关机命令
- ❌ 不发送 WOL

**启用方式**：
- 设置 → 系统配置 → 测试模式 → 选择"演练模式"

**使用建议**：
1. 首次部署时，使用演练模式测试
2. 在仪表盘点击"立即关机"
3. 观察关机流程是否正常（设备连接、通知等）
4. 确认无误后切换到生产模式

### Mock 模式（完全模拟）

**用途**：不连接真实 UPS，用于开发测试

**行为**：
- ❌ 不连接 UPS（使用模拟数据）
- ❌ 不执行设备操作
- ✅ 前端界面正常显示

**启用方式**：
- 环境变量：`MOCK_MODE=true`

---

## ❓ 故障排除 FAQ

### Q1: UPS 状态显示"离线"

**可能原因**：
1. NUT 配置错误
2. UPS 未连接或 USB 权限问题
3. Docker 容器未挂载 USB 设备

**解决方法**：
```bash
# 检查 USB 设备
lsusb

# 检查 NUT 服务日志
docker-compose logs nut-server

# 手动测试 NUT 连接（先列出发现的 UPS，再查询详情）
upsc -l localhost
upsc <发现的UPS名称>@localhost
```

### Q2: 设备连接测试失败

**可能原因**：
1. SSH 端口未开放
2. 用户名密码错误
3. 防火墙阻止
4. SSH 密钥格式错误

**解决方法**：
```bash
# 手动测试 SSH 连接
ssh user@host -p 22

# 检查防火墙
sudo ufw status

# 测试网络连通性
ping host
telnet host 22
```

### Q3: 关机后设备未唤醒

**可能原因**：
1. BIOS 未启用 WOL
2. MAC 地址错误
3. 网络设备未恢复
4. 网卡驱动不支持 WOL

**解决方法**：
1. 确认 BIOS 设置
2. 手动测试 WOL：
   ```bash
   # Linux
   sudo apt install wakeonlan
   wakeonlan AA:BB:CC:DD:EE:FF
   
   # Windows
   # 使用 WakeMeOnLan 工具
   ```
3. 增加 WOL 延迟时间

### Q4: 懒猫微服 gRPC 关机失败

**可能原因**：
1. gRPC Socket 权限问题
2. 懒猫版本不兼容

**解决方法**：
```bash
# 检查 Socket 文件
ls -la /lzcapp/run/sys/lzc-apis.socket

# 检查容器挂载
docker inspect ups-guard-backend | grep Mounts
```

### Q5: 通知未发送

**可能原因**：
1. 通知渠道配置错误
2. Token/Key 过期
3. 网络问题

**解决方法**：
1. 使用"测试通知"功能
2. 检查后端日志
3. 确认 API Token 有效性

---

## 🛠️ 开发者指南

### 插件开发

#### 创建新的 Hook 插件

```python
# backend/src/hooks/my_device.py

from hooks.base import PreShutdownHook
from hooks.registry import registry

class MyDeviceHook(PreShutdownHook):
    """自定义设备 Hook"""
    
    hook_id = "my_device"
    hook_name = "我的设备"
    hook_description = "自定义设备关机插件"
    
    @classmethod
    def get_config_schema(cls):
        return [
            {
                "key": "host",
                "label": "主机地址",
                "type": "text",
                "required": True
            }
        ]
    
    def validate_config(self):
        if not self.config.get("host"):
            raise ValueError("主机地址不能为空")
    
    async def test_connection(self) -> bool:
        # 测试连接逻辑
        return True
    
    async def execute(self) -> bool:
        # 执行关机逻辑
        return True

# 自动注册
registry.register_hook(MyDeviceHook)
```

#### 创建通知插件

```python
# backend/src/plugins/notifiers/my_notifier.py

from plugins.base import NotifierPlugin
from plugins.registry import registry

class MyNotifier(NotifierPlugin):
    """自定义通知插件"""
    
    plugin_id = "my_notifier"
    plugin_name = "我的通知"
    plugin_description = "自定义通知渠道"
    
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
        # 发送通知逻辑
        return True

registry.register_notifier(MyNotifier)
```

### API 列表

以下业务 HTTP API 需要请求头 `Authorization: Bearer YOUR_TOKEN`；`GET /health` 免认证。
WebSocket 使用查询参数 `token` 认证，HTTPS 入口应使用 `wss://`。
HTTP 接口也可在 `/docs` 或 `/openapi.json` 中查看。

#### 配置 API

```bash
# 获取配置
GET /api/config

# 更新配置
PUT /api/config

# 测试通知
POST /api/config/test-notify
```

#### UPS 状态 API

```bash
# 获取 UPS 状态（HTTP）
GET /api/status

# 获取 UPS 状态（WebSocket）
ws://localhost:8000/api/ws?token=YOUR_TOKEN

# 列出 NUT 中的 UPS 设备（不是实时状态）
GET /api/ups/list

# 立即关机
POST /api/actions/shutdown

# 取消关机
POST /api/actions/cancel-shutdown
```

`GET /api/ups` 不是已注册的状态接口，认证通过后返回 HTTP 404。
`GET /api/status` 在监控尚未初始化或 UPS 数据暂不可用时返回 HTTP 503。
WebSocket 状态消息类型为 `status_update`，状态数据位于 `data` 字段中。

#### UPS 控制 API

```bash
# 执行 UPS 命令（蜂鸣器、电池测试等）
POST /api/ups/command
{
  "command": "beeper.enable"  # 或 beeper.disable, test.battery.start.quick 等
}

# 蜂鸣器控制便捷端点
POST /api/ups/beeper/{action}  # action: enable | disable | mute

# 电池测试便捷端点
POST /api/ups/test-battery/{test_type}  # test_type: quick | deep | stop
```

#### UPS 参数配置 API

```bash
# 列出所有可写变量
GET /api/ups/writable-vars

# 设置 UPS 参数（需白名单验证）
POST /api/ups/set-var
{
  "var_name": "input.transfer.high",
  "value": "260"
}

# 支持的可写参数：
# - input.transfer.high: 高压切换阈值 (220-300V)
# - input.transfer.low: 低压切换阈值 (100-200V)
# - input.sensitivity: 输入灵敏度 (low/medium/high)
# - ups.delay.shutdown: 关机延迟时间 (0-600秒)
```

#### 设备管理 API

```bash
# 获取设备列表
GET /api/devices

# 获取设备状态
GET /api/devices/status

# 设备关机
POST /api/devices/{index}/shutdown

# 发送 WOL
POST /api/devices/{index}/wake

# 查看设备日志
POST /api/devices/{index}/logs
```

#### Hook API

```bash
# 列出可用插件
GET /api/hooks/plugins

# 测试单个 Hook
POST /api/hooks/test

# 批量获取 Hook 状态
GET /api/hooks/status
```

---

## 📞 支持与反馈

- **GitHub Issues**：https://github.com/KingBoyAndGirl/ups-guard/issues
- **文档**：https://github.com/KingBoyAndGirl/ups-guard/blob/main/README.md

---

## 📄 许可证

本项目采用 AGPL-3.0 许可证。商业使用请联系获取商业许可。

---

**感谢使用 UPS Guard！** 🎉
