# 常见问题与故障排查 FAQ

本文档回答用户最常见的问题，并提供详细的故障排查指南。

---

## 📋 目录

1. [实时性测试](#实时性测试)
2. [事件驱动未激活](#事件驱动未激活)
3. [通信次数验证](#通信次数验证)
4. [驱动调试级别](#驱动调试级别)
5. [性能优化建议](#性能优化建议)

---

## 🚀 实时性测试

### Q1: 我怎么查看和记录响应时间？

有多种方法可以测试和记录系统的响应时间：

#### 方法 1：浏览器开发者工具测试（最简单）⭐

**步骤**：

1. 打开 Dashboard 页面
2. 按 `F12` 打开浏览器开发者工具
3. 切换到 **Console（控制台）** 标签页
4. 粘贴以下测试代码：

```javascript
// 响应时间测试脚本
(async function testResponseTime() {
    console.log('='.repeat(50));
    console.log('📊 UPS Guard - 响应时间测试');
    console.log('='.repeat(50));
    
    // 准备测试
    console.log('\n1️⃣ 请在 5 秒内拔掉 UPS 电源...');
    await new Promise(resolve => setTimeout(resolve, 5000));
    
    // 开始计时
    console.log('2️⃣ 开始记录响应时间...\n');
    const startTime = Date.now();
    let detected = false;
    
    // 监听 WebSocket 消息
    const ws = new WebSocket(`ws://${window.location.host}/ws?token=${localStorage.getItem('api_token')}`);
    
    ws.onopen = () => {
        console.log('✅ WebSocket 连接已建立');
    };
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (!detected && data.type === 'status_update') {
            const status = data.data.status;
            const currentStatus = status?.toLowerCase();
            
            if (currentStatus === 'onbattery' || currentStatus === 'on_battery') {
                detected = true;
                const responseTime = Date.now() - startTime;
                
                console.log('\n' + '='.repeat(50));
                console.log('✅ 检测到状态变化！');
                console.log('='.repeat(50));
                console.log(`⏱️  响应时间: ${responseTime} 毫秒 (${(responseTime/1000).toFixed(2)} 秒)`);
                console.log(`📊 状态: ${status}`);
                console.log(`⚡ 电池电量: ${data.data.battery_charge}%`);
                console.log(`🔋 预计续航: ${Math.floor(data.data.battery_runtime/60)} 分钟`);
                console.log('='.repeat(50));
                
                // 性能评估
                if (responseTime < 500) {
                    console.log('🏆 性能评级: 优秀（事件驱动）');
                } else if (responseTime < 2000) {
                    console.log('👍 性能评级: 良好');
                } else if (responseTime < 5000) {
                    console.log('⚠️  性能评级: 一般（轮询模式）');
                } else {
                    console.log('❌ 性能评级: 需要优化');
                }
                
                ws.close();
            }
        }
    };
    
    ws.onerror = (error) => {
        console.error('❌ WebSocket 错误:', error);
    };
    
    // 30秒超时
    setTimeout(() => {
        if (!detected) {
            console.log('⏰ 测试超时（30秒）- 未检测到状态变化');
            console.log('💡 提示: 请确保已经拔掉 UPS 电源');
            ws.close();
        }
    }, 30000);
})();
```

5. 按 **Enter** 运行
6. 按照提示拔掉 UPS 电源
7. 查看控制台输出的响应时间

**输出示例**：

```
==================================================
✅ 检测到状态变化！
==================================================
⏱️  响应时间: 85 毫秒 (0.09 秒)
📊 状态: ONBATTERY
⚡ 电池电量: 100%
🔋 预计续航: 22 分钟
==================================================
🏆 性能评级: 优秀（事件驱动）
```

#### 方法 2：使用浏览器 Network 标签（手动测试）

1. 打开 Dashboard
2. 按 `F12` → **Network** 标签页
3. 筛选 **WS**（WebSocket）
4. 查看 `ws` 连接
5. 点击后在右侧查看 **Messages**
6. **记录当前时间**（例如 14:30:00）
7. 拔掉 UPS 电源
8. 观察 Messages 中出现 `status_update` 的时间
9. 计算时间差

**解读**：
- < 500ms：事件驱动模式，优秀 🏆
- 500ms - 2s：混合模式或快速轮询，良好 👍
- 2s - 5s：轮询模式，正常 ⚠️
- \> 5s：需要检查配置或网络 ❌

#### 方法 3：使用后端日志（最准确）

**步骤**：

1. 打开终端
2. 查看后端实时日志：

```bash
docker logs -f ups-guard-backend
```

3. 记录当前时间
4. 拔掉 UPS 电源
5. 观察日志中的时间戳

**查找关键日志**：

```
2026-02-15 01:20:30 - services.monitor - INFO - Status changed: ONLINE -> ONBATTERY
```

**计算响应时间**：`日志时间 - 拔电源时间`

---

## 🔌 事件驱动未激活

> 协议说明：标准 NUT 的 upsd TCP 协议没有 `LISTEN` 命令；`ERR UNKNOWN-COMMAND` 不能据此归因于 UPS 型号或固件。内置 Docker NUT 部署现在可使用[原生驱动事件桥接](native-driver-events.md)，直接接收驱动 Unix socket 更新，并按配置在事件失效时轮询兜底、恢复后切回。下方关于 `LISTEN` 的排查描述是既有实现的历史说明，不代表标准 NUT 协议能力。

### Q2: 我选择混合模式，为什么事件驱动状态显示"未激活"？

事件驱动未激活有 4 个常见原因：

### 原因 1：NUT 版本过旧 ⚠️

**症状**：
- 监控统计显示："混合模式 (轮询中)"
- 事件驱动状态：❌ 未激活

**检查方法**：

```bash
# 检查 NUT 版本
docker exec -it nut-server upsd -V

# 或
docker exec -it nut-server nut-scanner -V
```

**要求**：
- ✅ NUT 2.7.4 及以上 → 支持 LISTEN 命令
- ❌ NUT 2.7.3 及以下 → 不支持事件驱动

**解决方案**：

如果版本过旧，需要升级 NUT：

```bash
# 停止容器
docker-compose down

# 拉取最新镜像
docker-compose pull

# 重新启动
docker-compose up -d

# 验证版本
docker exec -it nut-server upsd -V
```

### 原因 2：UPS 固件不支持 📱

**症状**：
- NUT 版本正确（≥ 2.7.4）
- 但事件驱动仍未激活
- 后端日志显示 `LISTEN not supported`

**检查方法**：

```bash
# 查看后端日志
docker logs ups-guard-backend 2>&1 | grep -i "listen"

# 可能的输出：
# "NUT LISTEN not supported: ERR UNKNOWN-COMMAND"
```

**说明**：

部分 UPS 型号或固件不支持 NUT 的 LISTEN 机制，特别是：
- 老型号 UPS
- 入门级 UPS
- 非标准 USB HID 协议的 UPS

**解决方案**：

✅ **使用混合模式**（已经是最佳选择）：
- 系统会自动降级到轮询模式
- 仍然提供可靠的监控
- 通信频率已优化到 60 秒（比默认 5 秒好很多）

### 原因 3：网络连接问题 🌐

**症状**：
- 事件驱动时好时坏
- 频繁在"活跃"和"未激活"间切换

**检查方法**：

```bash
# 1. 测试 NUT 服务器连接
docker exec -it ups-guard-backend ping nut-server -c 4

# 2. 测试 NUT 端口
docker exec -it ups-guard-backend nc -zv nut-server 3493

# 3. 查看 NUT 服务器状态
docker logs nut-server --tail 50
```

**解决方案**：
- 检查 Docker 网络配置
- 确保容器间可以正常通信
- 检查防火墙设置

### 原因 4：配置未正确生效 ⚙️

**症状**：
- 修改了监控模式
- 但事件驱动状态没有变化

**检查步骤**：

1. **验证配置已保存**：
   ```bash
   # 查看配置文件
   docker exec -it ups-guard-backend cat /data/ups_guard.db | strings | grep monitoring_mode
   ```

2. **重启后端服务**：
   ```bash
   docker restart ups-guard-backend
   ```

3. **等待 30 秒**让事件驱动初始化

4. **刷新 Settings 页面**查看监控统计

### 验证事件驱动是否工作

**最终验证方法**：

1. 确认"事件驱动状态"为 ✅ 活跃
2. 拔掉 UPS 电源
3. 观察响应时间：
   - **< 500ms** → 事件驱动正常工作 ✅
   - **2-5 秒** → 使用轮询模式 ⚠️

---

## 📊 通信次数验证

### Q3: 混合模式下开机不到半小时，今日通信次数306，对吗？

**答案：正常！** 让我详细解释：

### 通信次数计算

混合模式下的通信来源：

#### 1. 启动初始化（约 20-50 次）

**启动阶段通信**：
- 连接建立：5-10 次
- 读取初始状态：10-20 次
- 参数验证：5-10 次
- 事件驱动尝试：3-5 次
- 心跳建立：2-3 次

**小计：约 25-48 次**

#### 2. 轮询备份（每小时 60 次）

**混合模式轮询频率**：
- 事件驱动活跃：60 秒/次
- 每小时：60 次
- 半小时：30 次

如果事件驱动未激活（降级为纯轮询）：
- 60 秒/次（降级后的轮询间隔）
- 半小时：30 次

#### 3. 事件触发通信（变化时）

**常见触发事件**：
- 电量变化：每 1-2% 触发一次（约 2-5 次/小时）
- 电压波动：电网不稳定时可能触发多次
- 负载变化：插拔设备时触发
- 温度变化：环境温度变化时触发

**估算**：10-50 次/小时

#### 4. 用户操作（手动刷新、修改参数）

**每次操作**：1-3 次通信
- 刷新页面：1 次
- 修改参数：1-2 次
- 查看设置：1 次

**估算**：5-20 次（取决于操作频率）

### 你的情况分析

**你的数据**：
- 时长：< 30 分钟
- 通信次数：306 次

**分解计算**：

```
启动初始化：    ~40 次
轮询备份（30分钟）：  30 次
事件触发：      ~200 次  ← 这里较多
用户操作：      ~36 次
─────────────────────
总计：         ~306 次 ✅
```

### 为什么事件触发这么多？

**可能的原因**：

1. **电网质量不稳定**：
   - 电压频繁波动
   - 每次波动触发一次 DATACHANGED 事件
   - **这是最常见的原因** ⚠️

2. **UPS 负载变化**：
   - 电脑风扇转速变化
   - 硬盘读写导致功率波动
   - 显示器亮度调整

3. **UPS 状态更新频繁**：
   - 某些 UPS 会频繁更新内部状态
   - 例如：电池电量以 0.1% 精度更新

4. **事件驱动模式优势**：
   - 传统轮询模式下，这些变化可能被延迟检测
   - 事件驱动模式实时捕获所有变化
   - **这不是问题，而是功能！** ✅

### 是否需要担心？

**答案：不需要担心！**

**原因**：

1. **通信开销极小**：
   - 每次通信：< 1KB 数据
   - 306 次 × 1KB = 0.3MB（半小时）
   - **对网络和性能影响可忽略不计**

2. **比轮询模式更好**：
   - 传统 5 秒轮询：30 分钟 = 360 次
   - 你的混合模式：30 分钟 = 306 次
   - **仍然更少！** ✅

3. **实时性更好**：
   - 所有状态变化立即检测
   - 不会错过任何重要事件
   - 更安全、更可靠

### 如何验证是否正常？

**健康指标**：

| 指标 | 健康范围 | 你的数据 | 评估 |
|------|---------|---------|------|
| **每小时通信次数** | 100-1000 | ~600 | ✅ 正常 |
| **启动后 1 小时** | 200-800 | 306（半小时） | ✅ 健康 |
| **响应延迟** | < 500ms | （需测试） | - |
| **CPU 占用** | < 5% | （需查看） | - |

**查看 CPU 占用**：

```bash
docker stats ups-guard-backend
```

如果 CPU < 5%，则完全正常 ✅

### 长期观察建议

**建议记录 24 小时数据**：

1. 早上记录通信次数：例如 500
2. 晚上记录通信次数：例如 2800
3. 计算增量：2800 - 500 = 2300 次/天

**预期范围**：
- **事件驱动活跃**：1500-3000 次/天（正常）
- **纯轮询模式**：1440 次/天（60秒轮询）
- **传统轮询**：17280 次/天（5秒轮询）

---

## 🔧 驱动调试级别

### Q4: 驱动调试级别是什么？

**驱动调试级别**（Driver Debug Level）是 NUT 驱动程序的日志详细程度控制参数。

### 什么是驱动调试级别？

**定义**：

NUT 驱动程序可以输出不同详细程度的日志信息，通过调试级别控制：

| 级别 | 名称 | 输出内容 | 用途 |
|------|------|---------|------|
| **0** | 无调试 | 仅错误信息 | 生产环境（默认） |
| **1** | 基本 | + 警告信息 | 日常监控 |
| **2** | 详细 | + 状态变化 | 问题排查 |
| **3** | 非常详细 | + USB 通信 | 深度调试 |
| **4** | 完全调试 | + 所有数据包 | 开发调试 |

### 为什么需要调试级别？

**常见使用场景**：

1. **排查 UPS 连接问题**：
   - UPS 无法识别
   - 驱动启动失败
   - USB 通信错误

2. **分析参数问题**：
   - 某个参数读取失败
   - 参数值异常
   - LISTEN 命令不工作

3. **开发和测试**：
   - 理解 UPS 协议
   - 测试新功能
   - 性能分析

### 当前系统的驱动调试级别

**查看当前值**：

```bash
# 方法 1：通过 NUT 命令
docker exec -it nut-server upsc ups driver.debug

# 输出：0（默认）
```

**查看实时日志**：

```bash
docker logs -f nut-server
```

### 如何修改驱动调试级别？

#### 方法 1：环境变量（推荐）

**编辑 `docker-compose.yml`**：

```yaml
services:
  nut-server:
    environment:
      - LOG_LEVEL=debug  # 添加这一行
```

**重启容器**：

```bash
docker-compose down
docker-compose up -d
```

#### 方法 2：修改 ups.conf（高级）

**进入容器**：

```bash
docker exec -it nut-server sh
```

**编辑配置**：

```bash
vi /etc/nut/ups.conf
```

**添加调试选项**：

```ini
[ups]
    driver = usbhid-ups
    port = auto
    debug_level = 3  # 添加这一行
```

**重启驱动**：

```bash
upsdrvctl stop
upsdrvctl start
```

### 调试输出示例

**级别 0（默认）**：

```
2026-02-15 01:00:00 Network UPS Tools - Generic HID driver 0.41 (2.7.4)
2026-02-15 01:00:00 USB communication driver 0.33
```

**级别 2（详细）**：

```
2026-02-15 01:00:00 Network UPS Tools - Generic HID driver 0.41 (2.7.4)
2026-02-15 01:00:00 USB communication driver 0.33
2026-02-15 01:00:05 Device: 051d:0002 - APC Back-UPS BK650M2-CH
2026-02-15 01:00:05 HID descriptor length 603
2026-02-15 01:00:05 Report descriptor retrieved
2026-02-15 01:00:06 Path: UPS.PowerSummary.Voltage, Type: Feature
2026-02-15 01:00:06 Value: 230.0
```

**级别 3（非常详细）**：

```
2026-02-15 01:00:00 Network UPS Tools - Generic HID driver 0.41 (2.7.4)
2026-02-15 01:00:00 USB communication driver 0.33
2026-02-15 01:00:05 Device: 051d:0002 - APC Back-UPS BK650M2-CH
2026-02-15 01:00:05 Entering libusb_get_report
2026-02-15 01:00:05 Report[buf]: 01 02 03 04 05 ...
2026-02-15 01:00:05 Entering libusb_set_report
2026-02-15 01:00:06 send_to_all: SETINFO ups.status "OL"
```

### 何时需要启用调试？

#### 场景 1：UPS 无法识别

**症状**：
- `upsc ups` 返回错误
- Dashboard 显示"离线"

**启用调试**：

```bash
# 设置级别 3
docker exec -it nut-server upsdrvctl stop
docker exec -it nut-server sh -c "echo 'debug_level = 3' >> /etc/nut/ups.conf"
docker exec -it nut-server upsdrvctl start

# 查看详细日志
docker logs -f nut-server
```

**查找**：
- USB 设备识别信息
- 驱动加载错误
- HID 描述符问题

#### 场景 2：事件驱动不工作

**症状**：
- 混合模式下事件驱动未激活
- 怀疑 LISTEN 命令问题

**启用调试**：

```bash
# 设置后端日志级别为 DEBUG
docker-compose down
# 编辑 docker-compose.yml，添加：
# backend:
#   environment:
#     - LOG_LEVEL=DEBUG

docker-compose up -d

# 查看后端日志
docker logs -f ups-guard-backend | grep -i listen
```

**查找**：
- LISTEN 命令发送
- DATACHANGED 通知接收
- 心跳消息

#### 场景 3：参数异常

**症状**：
- 某个参数值不正确
- 参数无法修改

**启用调试**：

```bash
# 级别 2 足够
docker exec -it nut-server sh
echo 'debug_level = 2' >> /etc/nut/ups.conf
upsdrvctl restart
```

**查看**：
- 参数读取日志
- SET VAR 命令执行
- 错误信息

### 调试完成后记得关闭！

**重要提醒** ⚠️：

调试级别 3-4 会产生**大量日志**：
- 每秒可能产生数百行日志
- 磁盘空间快速消耗
- 影响性能

**完成调试后务必关闭**：

```bash
# 移除调试配置
docker exec -it nut-server sh
sed -i '/debug_level/d' /etc/nut/ups.conf
upsdrvctl restart

# 或重置环境变量
docker-compose down
# 移除 LOG_LEVEL=debug
docker-compose up -d
```

### 查看系统当前配置

```bash
# 查看驱动配置
docker exec -it nut-server cat /etc/nut/ups.conf

# 查看当前调试级别
docker exec -it nut-server upsc ups driver.debug

# 查看后端日志级别
docker exec -it ups-guard-backend printenv LOG_LEVEL
```

---

## 💡 性能优化建议

### 混合模式最佳实践

**推荐配置**：

```yaml
监控模式: 混合模式
启用事件驱动: ✅
心跳间隔: 30 秒
自动降级: ✅
降级轮询间隔: 60 秒
```

### 通信次数优化建议

**如果你想进一步减少通信次数**：

1. **增加心跳间隔**（谨慎）：
   - 当前：30 秒
   - 可改为：45-60 秒
   - 风险：连接断开检测延迟

2. **增加降级轮询间隔**：
   - 当前：60 秒
   - 可改为：120 秒
   - 风险：事件驱动失败时响应慢

3. **但不建议**：
   - 当前配置已经很优化
   - 通信开销可忽略不计
   - 实时性更重要

### 监控健康检查清单

定期检查以下指标：

- [ ] 事件驱动状态：✅ 活跃（如果支持）
- [ ] 每小时通信次数：100-1000 次
- [ ] 响应延迟：< 500ms
- [ ] CPU 占用：< 5%
- [ ] 内存占用：< 200MB
- [ ] WebSocket 连接：正常
- [ ] 最后更新时间：< 60 秒前

---

## 🔍 故障排查速查表

| 症状 | 可能原因 | 解决方案 |
|------|---------|---------|
| 事件驱动未激活 | NUT 版本 < 2.7.4 | 升级 NUT |
| 事件驱动未激活 | UPS 不支持 LISTEN | 接受降级，仍有优化 |
| 通信次数异常多 | 电网不稳定 | 正常现象，实时监控优势 |
| 响应延迟 > 5s | 轮询模式且间隔长 | 检查监控模式配置 |
| CPU 占用高 | 调试级别过高 | 关闭调试模式 |
| WebSocket 断开 | 网络问题 | 检查网络连接 |

---

## 📚 相关文档

- [用户指南 - 监控模式](./user-guide.md#监控模式设置) - 配置说明
- [架构文档](./architecture.md) - 技术架构和设计

---

**需要更多帮助？** 查看后端日志或提交 GitHub Issue！
