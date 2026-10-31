<template>
  <div id="app">
    <!-- 全局关机警告弹窗 -->
    <div v-if="upsData?.shutdown?.shutting_down" class="shutdown-overlay">
      <div class="shutdown-modal">
        <div class="shutdown-header">
          <div class="shutdown-icon-wrapper">
            <span class="shutdown-icon">⚠️</span>
          </div>
          <h2>系统即将关机</h2>
        </div>

        <div class="shutdown-body">
          <div class="countdown-ring">
            <svg viewBox="0 0 100 100">
              <circle class="countdown-bg" cx="50" cy="50" r="45"></circle>
              <circle class="countdown-progress" cx="50" cy="50" r="45"
                :style="{ strokeDashoffset: countdownOffset }"></circle>
            </svg>
            <div class="countdown-value">
              <span class="countdown-number">{{ formatTime(upsData.shutdown.remaining_seconds || 0) }}</span>
              <span class="countdown-label">剩余时间</span>
            </div>
          </div>

          <div class="shutdown-info">
            <p class="shutdown-reason">市电中断，UPS 正在使用电池供电</p>
            <p class="shutdown-hint">如市电恢复，系统将自动取消关机</p>
          </div>
        </div>

        <div class="shutdown-footer">
          <button class="btn-cancel-shutdown" @click="showCancelConfirm = true">
            <span class="btn-icon">✋</span>
            <span>取消关机</span>
          </button>
        </div>
      </div>
    </div>

    <!-- 取消关机确认对话框 -->
    <div v-if="showCancelConfirm" class="modal-overlay" @click.self="!isCancelling && (showCancelConfirm = false)">
      <div class="modal-dialog modal-confirm">
        <div class="modal-icon">🛑</div>
        <h3>确认取消关机？</h3>
        <p>取消后系统将继续运行，但如果市电未恢复，电池耗尽后可能导致数据丢失。</p>
        <div class="modal-actions">
          <button
            class="btn btn-secondary"
            @click="showCancelConfirm = false"
            :disabled="isCancelling"
          >返回</button>
          <button
            class="btn btn-primary"
            @click="confirmCancelShutdown"
            :disabled="isCancelling"
            :class="{ 'btn-loading': isCancelling }"
          >
            <span v-if="isCancelling">取消中...</span>
            <span v-else>确认取消</span>
          </button>
        </div>
      </div>
    </div>

    <!-- 顶部导航 -->
    <nav class="navbar">
      <!-- Test Mode Banner -->
      <div v-if="isTestMode" class="test-mode-banner">
        <span>🧪 测试模式</span>
        <span class="test-mode-label">{{ testModeLabel }}</span>
      </div>
      
      <div class="navbar-inner">
        <router-link to="/" class="navbar-brand">
          <img src="/logo.png" alt="UPS Guard" class="navbar-logo" />
          <h1>UPS Guard</h1>
          <span v-if="systemVersion" class="version-tag">{{ systemVersion }}</span>
        </router-link>

        <div class="navbar-menu">
          <router-link to="/" class="nav-item" active-class="active" exact>仪表盘</router-link>
          <router-link to="/history" class="nav-item" active-class="active">历史记录</router-link>
          <router-link to="/events" class="nav-item" active-class="active">事件日志</router-link>
          <router-link to="/settings" class="nav-item" active-class="active">设置</router-link>

          <div class="navbar-divider"></div>

          <!-- 电池状态（带格子显示） -->
          <div class="battery-indicator" :class="batteryClass" v-if="upsData">
            <div class="battery-gauge">
              <div class="battery-gauge-body">
                <div class="battery-gauge-segments">
                  <div
                    v-for="i in 5"
                    :key="i"
                    class="battery-gauge-segment"
                    :class="{ 'active': batteryLevel >= (i * 20) }"
                    :style="{ backgroundColor: batteryLevel >= (i * 20) ? getBatteryColor(batteryLevel) : 'transparent' }"
                  ></div>
                </div>
              </div>
              <div class="battery-gauge-tip"></div>
            </div>
            <span class="battery-text">{{ batteryLevel }}%</span>
          </div>

          <!-- UPS 状态指示 -->
          <div class="ups-status-badge" :class="statusClass" v-if="upsData">
            {{ statusText }}
          </div>

          <!-- 全局按钮：根据设备状态动态显示 -->
          <!-- 所有设备都离线时显示绿色全部开机按钮 -->
          <button
            v-if="devices.length > 0 && allDevicesOffline && !upsData?.shutdown?.shutting_down"
            class="btn-power-on-nav"
            @click="wakeAllDevices"
            title="全部开机"
          >
            ⏻
          </button>
          <!-- 低电量时显示红色关机按钮 -->
          <button
            v-else-if="upsData && upsData.status === 'LOW_BATTERY' && !upsData.shutdown?.shutting_down"
            class="btn-shutdown-nav"
            @click="showShutdownConfirm = true"
            title="立即关机（低电量）"
          >
            ⏻
          </button>

          <!-- 文档链接 -->
          <a
            href="https://github.com/KingBoyAndGirl/ups-guard/blob/master/docs/index.md"
            target="_blank"
            rel="noopener noreferrer"
            class="nav-icon-link"
            title="文档 / Documentation"
          >
            📚
          </a>

          <!-- GitHub 仓库链接 -->
          <a
            href="https://github.com/KingBoyAndGirl/ups-guard"
            target="_blank"
            rel="noopener noreferrer"
            class="nav-icon-link"
            title="GitHub Repository"
          >
            <svg width="20" height="20" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
              <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>
            </svg>
          </a>

          <button class="theme-toggle" @click="toggleTheme" :title="themeName">
            {{ themeIcon }}
          </button>
        </div>
      </div>
    </nav>

    <!-- 手动关机确认对话框 -->
    <div v-if="showShutdownConfirm" class="modal-overlay" @click.self="!isShuttingDown && (showShutdownConfirm = false)">
      <div class="modal-dialog modal-confirm">
        <div class="modal-icon">⚠️</div>
        <h3>确认立即关机？</h3>
        <p class="shutdown-scope-notice"><strong>关机范围：本机（UPS Guard所在系统）</strong></p>
        <p>系统将执行完整的关机流程：</p>
        <ol class="shutdown-steps">
          <li>执行所有纳管设备的关机前置任务（pre-shutdown hooks）</li>
          <li>关闭所有纳管设备（按优先级顺序）</li>
          <li>关闭本机（UPS Guard宿主机）</li>
        </ol>
        <p class="warning-text">请确保已保存所有工作！</p>
        <div class="modal-actions">
          <button
            class="btn btn-secondary"
            @click="showShutdownConfirm = false"
            :disabled="isShuttingDown"
          >取消</button>
          <button
            class="btn btn-danger"
            @click="confirmManualShutdown"
            :disabled="isShuttingDown"
            :class="{ 'btn-loading': isShuttingDown }"
          >
            <span v-if="isShuttingDown">关机中...</span>
            <span v-else>确认关机本机</span>
          </button>
        </div>
      </div>
    </div>

    <!-- 全局连接诊断面板（显示时替换页面内容，但保留顶部导航） -->
    <div v-if="showGlobalDiagnostics" class="global-diagnostics-overlay">
      <div class="global-diagnostics-container">
        <div class="diagnostics-card">
          <div class="diagnostics-header">
            <div class="diagnostics-icon">🔧</div>
            <h2>连接诊断</h2>
            <div class="diagnostics-actions">
              <span v-if="diagnosticsCountdown > 0" class="auto-refresh-hint">
                ⏱️ {{ diagnosticsCountdown }}s 后自动刷新
              </span>
              <button
                class="btn btn-sm btn-primary"
                @click="fetchGlobalDiagnostics"
                :disabled="globalDiagnosticsLoading"
              >
                {{ globalDiagnosticsLoading ? '检测中...' : '🔄 重新检测' }}
              </button>
            </div>
          </div>

          <div class="diagnostics-status-grid">
            <!-- 后端状态 -->
            <div class="status-item" :class="getStatusClass(globalDiagnosticsData?.backend?.status)">
              <div class="status-icon">{{ getStatusIcon(globalDiagnosticsData?.backend?.status) }}</div>
              <div class="status-info">
                <div class="status-label">后端服务</div>
                <div class="status-message">{{ globalDiagnosticsData?.backend?.message || '检测中...' }}</div>
              </div>
            </div>

            <!-- NUT 服务器状态 -->
            <div class="status-item" :class="getStatusClass(globalDiagnosticsData?.nut_server?.status)">
              <div class="status-icon">{{ getStatusIcon(globalDiagnosticsData?.nut_server?.status) }}</div>
              <div class="status-info">
                <div class="status-label">NUT 服务器</div>
                <div class="status-message">{{ globalDiagnosticsData?.nut_server?.message || '检测中...' }}</div>
              </div>
            </div>

            <!-- UPS 驱动状态 -->
            <div class="status-item" :class="getStatusClass(globalDiagnosticsData?.ups_driver?.status)">
              <div class="status-icon">{{ getStatusIcon(globalDiagnosticsData?.ups_driver?.status) }}</div>
              <div class="status-info">
                <div class="status-label">UPS 驱动</div>
                <div class="status-message">{{ globalDiagnosticsData?.ups_driver?.message || '检测中...' }}</div>
              </div>
            </div>
          </div>

          <!-- 诊断日志 -->
          <div class="diagnostics-logs" v-if="globalDiagnosticsData?.logs?.length">
            <div class="logs-header">
              <span>📋 诊断日志</span>
              <button class="btn-text" @click="copyDiagnosticsLogs" title="复制日志">
                📋 复制
              </button>
            </div>
            <div class="logs-content">
              <div v-for="(log, index) in globalDiagnosticsData.logs" :key="index"
                   class="log-line"
                   :class="getLogClass(log)">
                {{ log }}
              </div>
            </div>
          </div>


          <!-- 故障排查建议 -->
          <div class="diagnostics-tips">
            <h4>💡 故障排查建议</h4>
            <ul>
              <li v-if="globalDiagnosticsData?.nut_server?.status === 'error'">
                <strong>NUT 服务器连接失败：</strong>
                <ul>
                  <li>检查 NUT 容器是否正在运行：<code>docker ps | grep nut</code></li>
                  <li>检查 NUT 容器日志：<code>docker logs ups-guard-nut --tail 50</code></li>
                  <li>确认端口 3493 是否可访问</li>
                </ul>
              </li>
              <li v-if="globalDiagnosticsData?.ups_driver?.status === 'warning'">
                <strong>UPS 驱动异常：</strong>
                <ul>
                  <li>检查 UPS USB 线是否连接</li>
                  <li>如果使用 WSL2/Docker Desktop，需要将 USB 设备 attach 到 WSL2：
                    <code>usbipd attach --wsl --busid &lt;BUSID&gt;</code>
                  </li>
                  <li>NUT 容器会自动检测并重新配置，无需手动重启</li>
                </ul>
              </li>
              <li v-if="globalDiagnosticsData?.ups_driver?.status === 'error'">
                <strong>无法获取 UPS 数据：</strong>
                <ul>
                  <li>UPS 驱动可能正在重新配置中，请稍等</li>
                  <li>检查 NUT 容器日志查看驱动状态</li>
                </ul>
              </li>
              <li v-if="globalDiagnosticsData?.backend?.status === 'error'">
                <strong>后端服务异常：</strong>
                <ul>
                  <li>检查后端服务是否正常运行</li>
                  <li>检查网络连接是否正常</li>
                  <li>尝试刷新页面</li>
                </ul>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>

    <!-- 正常页面内容（诊断面板不显示时） -->
    <router-view v-if="!showGlobalDiagnostics" />

    <!-- Toast 通知组件 -->
    <Toast />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'
import { useTheme } from '@/composables/useTheme'
import { useWebSocket } from '@/composables/useWebSocket'
import { useToast } from '@/composables/useToast'
import { useConfigStore } from '@/stores/config'
import Toast from '@/components/Toast.vue'

// 初始化主题系统
const { toggleTheme, themeName, themeIcon } = useTheme()

// 路由（用于判断当前页面）
const route = useRoute()

// 全局 Toast 通知
const toast = useToast()

// 系统版本号
const systemVersion = ref('')

// 全局 WebSocket 连接
const { connected: wsConnected, data: wsData, connectionEvent, lastReceivedAt } = useWebSocket()
const upsData = computed(() => wsData.value)

// 全局诊断面板状态
const showGlobalDiagnostics = ref(false)
const globalDiagnosticsData = ref<{
  backend?: { status: string; message: string }
  nut_server?: { status: string; message: string }
  ups_driver?: { status: string; message: string }
  overall_status?: string
  logs?: string[]
} | null>(null)
const globalDiagnosticsLoading = ref(false)
const diagnosticsCountdown = ref(0)
const DIAGNOSTICS_REFRESH_INTERVAL = 5 // 5秒刷新一次
let diagnosticsRefreshTimer: number | null = null
let diagnosticsCountdownTimer: number | null = null

// 判断是否需要显示全局诊断面板
const needsGlobalDiagnostics = computed(() => {
  // 初始加载时（还未收到过任何数据），不认为需要诊断
  // 等 WebSocket 连接成功并收到第一次数据后再判断
  if (lastReceivedAt.value === 0) {
    console.log('[App.vue] needsGlobalDiagnostics: initial loading, waiting for first data...')
    return false
  }

  // WebSocket 断开（已经连接过但现在断开了）
  if (!wsConnected.value && lastReceivedAt.value > 0) {
    console.log('[App.vue] needsGlobalDiagnostics: WebSocket disconnected after receiving data')
    return true
  }

  // wsData 为空（已经连接过但数据丢失）
  if (!wsData.value && lastReceivedAt.value > 0) {
    console.log('[App.vue] needsGlobalDiagnostics: wsData is null after receiving data')
    return true
  }

  // UPS 状态是 offline（支持大小写）
  const status = wsData.value?.status?.toUpperCase()
  if (status === 'OFFLINE' || status === 'OFF') {
    console.log('[App.vue] needsGlobalDiagnostics: UPS status is offline, actual:', wsData.value?.status)
    return true
  }

  // 检测设备断开等待模式（Dummy 等待模式）
  // 后端会在设备断开时将 ups_model 设置为 "USB Device Disconnected"，ups_manufacturer 设置为 "Waiting"
  const upsModel = wsData.value?.ups_model?.toLowerCase() || ''
  const upsMfr = wsData.value?.ups_manufacturer?.toLowerCase() || ''
  if (upsModel.includes('disconnected') || upsMfr.includes('waiting')) {
    console.log('[App.vue] needsGlobalDiagnostics: device disconnected waiting mode, model:', wsData.value?.ups_model, 'mfr:', wsData.value?.ups_manufacturer)
    return true
  }

  // 检测初始 Dummy 开发模式（没有真实设备）
  // ups_model 和 ups_manufacturer 都是 "Dummy" 时表示处于 Dummy 开发模式
  if (upsModel === 'dummy ups' && upsMfr === 'dummy') {
    console.log('[App.vue] needsGlobalDiagnostics: dummy development mode')
    return true
  }

  // 检查数据是否超时（30秒未收到新数据）
  // 使用客户端记录的 lastReceivedAt，避免服务端/客户端时区不一致问题
  if (lastReceivedAt.value > 0) {
    const now = Date.now()
    const staleThreshold = 30 * 1000 // 30秒
    if (now - lastReceivedAt.value > staleThreshold) {
      console.log('[App.vue] needsGlobalDiagnostics: data is stale, lastReceivedAt:', new Date(lastReceivedAt.value).toISOString(), 'now:', new Date(now).toISOString())
      return true
    }
  }

  return false
})

// 设备状态（用于显示全局开机按钮）
interface Device {
  index: number
  name: string
  online: boolean
  config?: {
    mac_address?: string
  }
}
const devices = ref<Device[]>([])

// 检查是否所有设备都已离线
const allDevicesOffline = computed(() => {
  const result = devices.value.length > 0 && devices.value.every(device => !device.online)
  return result
})

// 获取设备状态
const fetchDevicesStatus = async () => {
  try {
    const response = await axios.get('/api/devices/status')
    devices.value = response.data.devices || []
  } catch (error) {
    console.error('[App.vue] ❌ Failed to fetch devices status:', error)
  }
}

// 唤醒所有设备
const wakeAllDevices = async () => {
  // 确保设备列表已加载
  if (devices.value.length === 0) {
    // 如果设备列表为空，先刷新
    await fetchDevicesStatus()
  }
  
  const devicesWithMAC = devices.value.filter(d => d.config?.mac_address)
  
  if (devicesWithMAC.length === 0) {
    toast.error('没有配置 MAC 地址的设备可以唤醒')
    return
  }

  let successCount = 0
  let failCount = 0

  for (const device of devicesWithMAC) {
    try {
      await axios.post(`/api/devices/${device.index}/wake`)
      successCount++
    } catch (error) {
      console.error(`Failed to wake device ${device.name}:`, error)
      failCount++
    }
  }

  if (successCount > 0) {
    toast.success(`✅ 成功发送 WOL 到 ${successCount} 台设备`)
    
    // 立即刷新设备状态，然后持续刷新几次以检测设备上线
    fetchDevicesStatus()
    setTimeout(fetchDevicesStatus, 3000)
    setTimeout(fetchDevicesStatus, 6000)
    setTimeout(fetchDevicesStatus, 10000)
  }
  if (failCount > 0) {
    toast.error(`❌ ${failCount} 台设备唤醒失败`)
  }
}

// 使用配置 store 管理测试模式状态
const configStore = useConfigStore()
const isTestMode = computed(() => configStore.isTestMode)
const testModeLabel = computed(() => configStore.testModeLabel)

// 关机相关状态
const showCancelConfirm = ref(false)
const showShutdownConfirm = ref(false)

// 加载状态（防止重复点击）
const isCancelling = ref(false)
const isShuttingDown = ref(false)

// 电池电量
const batteryLevel = computed(() => {
  return upsData.value?.battery_charge ?? 0
})

// 电池状态样式
const batteryClass = computed(() => {
  const level = batteryLevel.value
  if (level <= 20) return 'battery-critical'
  if (level <= 50) return 'battery-low'
  return 'battery-normal'
})

// 根据电池电量返回颜色
const getBatteryColor = (charge: number): string => {
  if (charge <= 20) return '#EF4444'  // 红色 - 危险
  if (charge <= 50) return '#F59E0B'  // 黄色 - 警告
  return '#10B981'  // 绿色 - 正常
}


// UPS 状态文本
const statusText = computed(() => {
  const status = upsData.value?.status
  const map: Record<string, string> = {
    'ONLINE': '在线',
    'ON_BATTERY': '电池供电',
    'LOW_BATTERY': '低电量',
    'OFFLINE': '离线'
  }
  return map[status || ''] || status || '未知'
})

// UPS 状态样式
const statusClass = computed(() => {
  const status = upsData.value?.status
  if (status === 'ONLINE') return 'status-online'
  if (status === 'ON_BATTERY') return 'status-battery'
  if (status === 'LOW_BATTERY') return 'status-critical'
  return 'status-offline'
})


// 倒计时圆环进度
const countdownOffset = computed(() => {
  if (!upsData.value?.shutdown?.remaining_seconds) return 283
  // 如果在最终倒计时阶段，使用 30 秒作为总时间
  const inFinalCountdown = upsData.value.shutdown.in_final_countdown
  const total = inFinalCountdown ? 30 : 330  // 最终阶段30秒，否则5分30秒
  const remaining = upsData.value.shutdown.remaining_seconds
  const progress = remaining / total
  return 283 * (1 - progress)
})

const formatTime = (seconds: number): string => {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

// 获取系统版本号
const fetchSystemVersion = async () => {
  try {
    const response = await axios.get('/health')
    systemVersion.value = response.data.version ? `v${response.data.version}` : ''
  } catch {
    systemVersion.value = ''
  }
}

const confirmCancelShutdown = async () => {
  if (isCancelling.value) return  // 防止重复点击

  isCancelling.value = true
  try {
    await axios.post('/api/actions/cancel-shutdown')
    showCancelConfirm.value = false
    toast.success('关机已取消')
  } catch (error) {
    console.error('Failed to cancel shutdown:', error)
    toast.error('取消关机失败')
  } finally {
    isCancelling.value = false
  }
}

const confirmManualShutdown = async () => {
  if (isShuttingDown.value) return  // 防止重复点击

  isShuttingDown.value = true
  try {
    await axios.post('/api/actions/shutdown')
    showShutdownConfirm.value = false
    toast.success('关机命令已发送')
    
    // 立即更新前端状态，显示关机倒计时
    if (wsData.value) {
      wsData.value = {
        ...wsData.value,
        shutdown: {
          shutting_down: true,
          remaining_seconds: 0,
          in_final_countdown: false
        }
      }
    }
    
    // 立即标记所有设备为离线状态，以便按钮切换
    devices.value = devices.value.map(device => ({
      ...device,
      online: false,
      last_check: new Date().toISOString()
    }))

    // 通知Dashboard立即刷新设备状态
    window.dispatchEvent(new CustomEvent('device-state-changed'))
    
    // 延迟刷新已移除 - 在Mock模式下后端不会真正关闭设备，任何fetch都会返回online状态
    // 依赖60秒定期刷新和事件驱动的刷新即可
    // setTimeout(fetchDevicesStatus, 2000) // 已移除
  } catch (error) {
    console.error('[App.vue] ❌ Failed to trigger shutdown:', error)
    toast.error('触发关机失败')
  } finally {
    isShuttingDown.value = false
  }
}

onMounted(() => {
  configStore.init()
  fetchDevicesStatus()
  fetchSystemVersion()

  // 定期刷新设备状态（每分钟）
  setInterval(fetchDevicesStatus, 60000)
  
  // 监听设备状态变化事件（由Dashboard或其他页面触发）
  const handleDeviceStateChange = () => {
    // 如果正在关机中，不要立即刷新设备状态（等待关机完成后由wsData watcher处理）
    if (wsData.value?.shutdown?.shutting_down) {
      return
    }
    fetchDevicesStatus()
  }
  window.addEventListener('device-state-changed', handleDeviceStateChange)
  
  // 清理事件监听器
  onUnmounted(() => {
    window.removeEventListener('device-state-changed', handleDeviceStateChange)
  })
})

// 全局诊断函数
const fetchGlobalDiagnostics = async () => {
  globalDiagnosticsLoading.value = true
  try {
    const response = await axios.get('/api/system/connection-status')
    globalDiagnosticsData.value = response.data

    // 检查是否应该关闭诊断面板
    // 条件：后端 overall_status 是 ok（表示连接正常）
    // 不再需要检查 needsGlobalDiagnostics，因为后端已确认状态正常
    const shouldClose = response.data.overall_status === 'ok'

    if (shouldClose) {
      console.log('[App.vue] Connection status ok, closing panel immediately...')
      // 检测正常，立即关闭面板并停止定时刷新
      stopDiagnosticsRefresh()
      showGlobalDiagnostics.value = false
    } else {
      console.log('[App.vue] Keeping diagnostics panel open, overall_status:', response.data.overall_status)
    }
  } catch (error: any) {
    globalDiagnosticsData.value = {
      backend: {
        status: 'error',
        message: `后端服务无法访问: ${error.message || '网络错误'}`
      },
      nut_server: { status: 'unknown', message: '无法检测' },
      ups_driver: { status: 'unknown', message: '无法检测' },
      overall_status: 'error',
      logs: [`❌ 无法连接后端服务: ${error.message || '网络错误'}`]
    }
  } finally {
    globalDiagnosticsLoading.value = false
  }
}

const getStatusIcon = (status?: string): string => {
  switch (status) {
    case 'ok': return '✅'
    case 'warning': return '⚠️'
    case 'error': return '❌'
    default: return '❓'
  }
}

const getStatusClass = (status?: string): string => {
  switch (status) {
    case 'ok': return 'status-ok'
    case 'warning': return 'status-warning'
    case 'error': return 'status-error'
    default: return 'status-unknown'
  }
}

const getLogClass = (log: string): string => {
  if (log.includes('❌') || log.includes('错误') || log.includes('失败')) return 'log-error'
  if (log.includes('⚠️') || log.includes('警告')) return 'log-warning'
  if (log.includes('✅') || log.includes('成功') || log.includes('正常')) return 'log-success'
  return ''
}


// 启动诊断定时刷新
const startDiagnosticsRefresh = () => {
  if (diagnosticsRefreshTimer) return // 已经在运行

  console.log('[App.vue] Starting diagnostics refresh timer...')
  diagnosticsCountdown.value = DIAGNOSTICS_REFRESH_INTERVAL

  // 倒计时更新（独立定时器）
  diagnosticsCountdownTimer = window.setInterval(() => {
    if (diagnosticsCountdown.value > 0) {
      diagnosticsCountdown.value--
    }
  }, 1000)

  // 主刷新定时器
  diagnosticsRefreshTimer = window.setInterval(async () => {
    await fetchGlobalDiagnostics()
    diagnosticsCountdown.value = DIAGNOSTICS_REFRESH_INTERVAL
  }, DIAGNOSTICS_REFRESH_INTERVAL * 1000)
}

// 停止诊断定时刷新
const stopDiagnosticsRefresh = () => {
  console.log('[App.vue] Stopping diagnostics refresh timer...')
  if (diagnosticsRefreshTimer) {
    clearInterval(diagnosticsRefreshTimer)
    diagnosticsRefreshTimer = null
  }
  if (diagnosticsCountdownTimer) {
    clearInterval(diagnosticsCountdownTimer)
    diagnosticsCountdownTimer = null
  }
  diagnosticsCountdown.value = 0
}

// 复制诊断日志
const copyDiagnosticsLogs = () => {
  const logs = globalDiagnosticsData.value?.logs?.join('\n') || ''

  if (logs) {
    navigator.clipboard.writeText(logs)
    toast.success('日志已复制到剪贴板')
  }
}

// 设置和事件页面必须在连接异常时仍可访问，便于排查和修改配置。
const isDiagnosticsBypassPage = computed(() =>
  route.path === '/events' || route.path === '/settings'
)

// 监听路由变化
watch(() => route.path, (newPath, oldPath) => {
  console.log('[App.vue] Route changed:', oldPath, '->', newPath)

  if (newPath === '/events' || newPath === '/settings') {
    // 跳转到故障排查页面，关闭诊断面板
    if (showGlobalDiagnostics.value) {
      console.log('[App.vue] Navigated to events page, closing diagnostics panel')
      showGlobalDiagnostics.value = false
      stopDiagnosticsRefresh()
    }
  } else if (oldPath === '/events' || oldPath === '/settings') {
    // 返回监控页面时，如果仍有异常则重新显示诊断面板
    if (needsGlobalDiagnostics.value && !showGlobalDiagnostics.value) {
      console.log('[App.vue] Left events page with active issues, showing diagnostics panel')
      showGlobalDiagnostics.value = true
      fetchGlobalDiagnostics()
      startDiagnosticsRefresh()
    }
  }
})

// 监听 WebSocket 推送的 NUT 连接状态事件
watch(connectionEvent, (event, oldEvent) => {
  console.log('[App.vue] connectionEvent changed:', event, 'old:', oldEvent, 'isDiagnosticsBypassPage:', isDiagnosticsBypassPage.value)
  if (!event) return

  if (event.type === 'NUT_DISCONNECTED') {
    // NUT 连接断开
    console.log('[App.vue] NUT disconnected, isDiagnosticsBypassPage:', isDiagnosticsBypassPage.value, 'showGlobalDiagnostics:', showGlobalDiagnostics.value)
    // 设置和事件页面不弹出诊断面板。
    if (!isDiagnosticsBypassPage.value) {
      console.log('[App.vue] Showing diagnostics panel...')
      showGlobalDiagnostics.value = true
      fetchGlobalDiagnostics()
      startDiagnosticsRefresh()
    } else {
      console.log('[App.vue] On events page, not showing diagnostics panel')
    }
  } else if (event.type === 'NUT_RECONNECTED') {
    // NUT 连接恢复，刷新诊断状态
    console.log('[App.vue] NUT reconnected, refreshing diagnostics...')
    fetchGlobalDiagnostics()
    // fetchGlobalDiagnostics 会在状态恢复正常时自动关闭面板
  }
}, { deep: true })

// 监听 needsGlobalDiagnostics 变化
watch(needsGlobalDiagnostics, (needsDiag, wasDiag) => {
  console.log('[App.vue] needsGlobalDiagnostics changed:', needsDiag, 'was:', wasDiag, 'isDiagnosticsBypassPage:', isDiagnosticsBypassPage.value, 'lastReceivedAt:', lastReceivedAt.value)

  // 初始化时 wasDiag 为 undefined，需要特殊处理
  const wasNormal = wasDiag === false
  const isInitial = wasDiag === undefined

  // 只有在确实从正常变成异常时才显示诊断面板
  // 初始加载时（isInitial），需要确认 lastReceivedAt > 0（已经收到过数据）才显示
  // 这样避免了刚刷新页面时因为数据还在加载就显示诊断面板
  if (needsDiag && wasNormal) {
    // 从正常变成异常
    console.log('[App.vue] Connection issue detected (was normal), isDiagnosticsBypassPage:', isDiagnosticsBypassPage.value)
    if (!isDiagnosticsBypassPage.value) {
      console.log('[App.vue] Showing diagnostics panel from needsGlobalDiagnostics...')
      showGlobalDiagnostics.value = true
      fetchGlobalDiagnostics()
      startDiagnosticsRefresh()
    }
  } else if (needsDiag && isInitial && lastReceivedAt.value > 0) {
    // 初始状态且已经收到过数据，说明是真正的问题
    console.log('[App.vue] Connection issue detected on init (already received data), isDiagnosticsBypassPage:', isDiagnosticsBypassPage.value)
    if (!isDiagnosticsBypassPage.value) {
      console.log('[App.vue] Showing diagnostics panel from needsGlobalDiagnostics (initial)...')
      showGlobalDiagnostics.value = true
      fetchGlobalDiagnostics()
      startDiagnosticsRefresh()
    }
  } else if (!needsDiag && wasDiag) {
    // 从异常恢复正常，关闭诊断面板
    console.log('[App.vue] Connection restored, hiding diagnostics...')
    stopDiagnosticsRefresh()
    // 延迟关闭，让用户看到恢复状态
    setTimeout(() => {
      if (!needsGlobalDiagnostics.value) {
        showGlobalDiagnostics.value = false
      }
    }, 2000)
  }
}, { immediate: true })  // immediate: true 确保初始时也执行检查

// 监听 WebSocket 数据变化，实时更新设备状态
watch(wsData, (newData, oldData) => {
  if (!newData) return
  
  // 关机状态变化时，立即更新设备状态
  const shutdownStateChanged = newData.shutdown?.shutting_down !== oldData?.shutdown?.shutting_down
  if (shutdownStateChanged) {
    if (newData.shutdown?.shutting_down) {
      // 关机开始时，将所有设备标记为离线
      devices.value = devices.value.map(device => ({
        ...device,
        online: false
      }))
    }
    // 关机取消或完成时，不立即刷新（由延迟刷新处理）
    // 不要立即fetch，因为在Mock模式下后端还未更新设备状态
    // 延迟2秒的fetch会在正确的时机同步状态
  }
  
  // UPS 状态变化时也刷新设备状态（例如从电池切换到市电）
  const statusChanged = newData.status !== oldData?.status
  if (statusChanged) {
    // 延迟刷新，避免频繁请求
    setTimeout(() => {
      fetchDevicesStatus()
    }, 1000)
  }
}, { deep: true })
</script>

<style>
@import '@/styles/theme.css';
@import '@/styles/variables.css';
@import '@/styles/global.css';
@import '@/styles/responsive.css';
</style>

<style scoped>
/* 全局关机警告弹窗 */
.shutdown-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.85);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.shutdown-modal {
  background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
  border-radius: 20px;
  padding: 2.5rem;
  max-width: 420px;
  width: 90%;
  text-align: center;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5),
              0 0 0 1px rgba(255, 255, 255, 0.1);
  animation: slideUp 0.4s ease;
}

@keyframes slideUp {
  from { transform: translateY(30px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

.shutdown-header {
  margin-bottom: 1.5rem;
}

.shutdown-icon-wrapper {
  margin-bottom: 1rem;
}

.shutdown-icon {
  font-size: 4rem;
  animation: pulse-icon 1.5s ease-in-out infinite;
}

@keyframes pulse-icon {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.1); }
}

.shutdown-header h2 {
  margin: 0;
  font-size: 1.75rem;
  font-weight: 700;
  color: #f87171;
}

.shutdown-body {
  margin-bottom: 2rem;
}

.countdown-ring {
  position: relative;
  width: 160px;
  height: 160px;
  margin: 0 auto 1.5rem;
}

.countdown-ring svg {
  transform: rotate(-90deg);
  width: 100%;
  height: 100%;
}

.countdown-bg {
  fill: none;
  stroke: #374151;
  stroke-width: 8;
}

.countdown-progress {
  fill: none;
  stroke: #ef4444;
  stroke-width: 8;
  stroke-linecap: round;
  stroke-dasharray: 283;
  transition: stroke-dashoffset 1s linear;
}

.countdown-value {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
}

.countdown-number {
  display: block;
  font-size: 2.5rem;
  font-weight: 700;
  font-family: 'Courier New', monospace;
  color: white;
}

.countdown-label {
  display: block;
  font-size: 0.875rem;
  color: #9ca3af;
  margin-top: 0.25rem;
}

.shutdown-info {
  color: #d1d5db;
}

.shutdown-reason {
  font-size: 1rem;
  margin: 0 0 0.5rem 0;
}

.shutdown-hint {
  font-size: 0.875rem;
  color: #9ca3af;
  margin: 0;
}

.shutdown-footer {
  margin-top: 1rem;
}

.btn-cancel-shutdown {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 1rem 2rem;
  font-size: 1.125rem;
  font-weight: 600;
  color: white;
  background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%);
  border: none;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 4px 14px rgba(220, 38, 38, 0.4);
}

.btn-cancel-shutdown:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(220, 38, 38, 0.5);
}

.btn-cancel-shutdown:active {
  transform: translateY(0);
}

.btn-icon {
  font-size: 1.25rem;
}

/* 确认对话框 */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
}

.modal-dialog {
  background: var(--bg-primary);
  border-radius: var(--radius-lg);
  padding: var(--spacing-lg);
  max-width: 400px;
  width: 90%;
  box-shadow: var(--shadow-lg);
}

.modal-confirm {
  text-align: center;
}

.modal-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
}

.modal-confirm h3 {
  margin: 0 0 0.75rem 0;
  color: var(--text-primary);
}

.modal-confirm p {
  margin: 0 0 1.5rem 0;
  color: var(--text-secondary);
  font-size: 0.9375rem;
  line-height: 1.5;
}

.shutdown-steps {
  text-align: left;
  margin: 0 0 1rem 0;
  padding-left: 1.5rem;
  color: var(--text-primary);
  font-size: 0.875rem;
}

.shutdown-steps li {
  margin-bottom: 0.5rem;
}

.shutdown-scope-notice {
  color: #3b82f6;
  font-weight: 600;
  margin-bottom: 1rem !important;
  padding: 0.5rem 1rem;
  background: rgba(59, 130, 246, 0.1);
  border-radius: var(--radius-md);
  border: 1px solid rgba(59, 130, 246, 0.3);
  font-size: 0.9375rem;
}

.warning-text {
  color: #dc2626;
  font-weight: 500;
  font-size: 0.875rem;
  margin: 0 0 1.5rem 0;
}

.modal-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: center;
}

.modal-actions .btn {
  flex: 1;
  padding: 0.75rem 1.25rem;
  border: none;
  border-radius: var(--radius-md);
  font-size: 1rem;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-secondary {
  background: var(--bg-secondary);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
}

.btn-secondary:hover {
  background: var(--bg-tertiary);
}

.btn-primary {
  background: var(--color-primary);
  color: white;
}

.btn-primary:hover {
  opacity: 0.9;
}

.btn-danger {
  background: #dc2626;
  color: white;
}

.btn-danger:hover {
  opacity: 0.9;
}

/* 按钮禁用和加载状态 */
.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  pointer-events: none;
}

.btn-loading {
  position: relative;
}

.btn-loading::after {
  content: '';
  position: absolute;
  width: 14px;
  height: 14px;
  border: 2px solid transparent;
  border-top-color: currentColor;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-left: 8px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 导航栏样式 */
.navbar {
  background: var(--bg-primary);
  padding: 0;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  margin: var(--spacing-lg);
  margin-bottom: 0;
  overflow: hidden;
}

/* Test Mode Banner */
.test-mode-banner {
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
  color: white;
  padding: 0.5rem var(--spacing-lg);
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  font-weight: 600;
  animation: pulse-banner 2s ease-in-out infinite;
}

@keyframes pulse-banner {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.85; }
}

.test-mode-label {
  background: rgba(255, 255, 255, 0.2);
  padding: 0.125rem 0.5rem;
  border-radius: var(--radius-sm);
  font-size: 0.8125rem;
}

.navbar-inner {
  max-width: 1400px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-md) var(--spacing-lg);
}

.navbar-brand {
  text-decoration: none;
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.navbar-logo {
  width: 36px;
  height: 36px;
  object-fit: contain;
}

.navbar-brand h1 {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
  transition: opacity 0.2s;
}

.navbar-brand .version-tag {
  font-size: 0.7rem;
  font-weight: 500;
  color: var(--text-secondary);
  background: var(--bg-secondary);
  padding: 2px 6px;
  border-radius: 4px;
  margin-left: 4px;
  opacity: 0.8;
}

.navbar-brand:hover h1 {
  opacity: 0.8;
}

.navbar-menu {
  display: flex;
  gap: var(--spacing-sm);
  align-items: center;
}

.navbar-divider {
  width: 1px;
  height: 24px;
  background: var(--border-color);
  margin: 0 var(--spacing-xs);
}

.nav-item {
  padding: 0.5rem 1rem;
  text-decoration: none;
  color: var(--text-secondary);
  border-radius: var(--radius-md);
  transition: all 0.2s;
}

.nav-item:hover {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.nav-item.active {
  background: var(--color-primary);
  color: white;
}

.nav-icon-link {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.5rem 0.75rem;
  text-decoration: none;
  color: var(--text-secondary);
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: 1.2rem;
  transition: all 0.2s;
}

.nav-icon-link:hover {
  background: var(--bg-tertiary);
  border-color: var(--border-hover);
  color: var(--text-primary);
  transform: scale(1.05);
}

.nav-icon-link:active {
  transform: scale(0.95);
}

.nav-icon-link svg {
  display: block;
}

.theme-toggle {
  padding: 0.5rem 0.75rem;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: 1.2rem;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.theme-toggle:hover {
  background: var(--bg-tertiary);
  border-color: var(--border-hover);
  transform: scale(1.05);
}

.theme-toggle:active {
  transform: scale(0.95);
}

/* 电池指示器 */
.battery-indicator {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.25rem 0.5rem;
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  font-size: 0.8125rem;
}

/* 电池格子显示 */
.battery-gauge {
  display: flex;
  align-items: center;
}

.battery-gauge-body {
  width: 28px;
  height: 14px;
  border: 1.5px solid currentColor;
  border-radius: 2px;
  padding: 1px;
  display: flex;
  gap: 1px;
}

.battery-gauge-segments {
  display: flex;
  gap: 1px;
  width: 100%;
  height: 100%;
}

.battery-gauge-segment {
  flex: 1;
  border-radius: 1px;
  background: var(--bg-tertiary);
  transition: background-color 0.3s ease;
}

.battery-gauge-segment.active {
  opacity: 1;
}

.battery-gauge-tip {
  width: 3px;
  height: 6px;
  background: currentColor;
  border-radius: 0 2px 2px 0;
  margin-left: 1px;
}

.battery-text {
  font-weight: 600;
  font-size: 0.75rem;
}

.battery-normal {
  color: #10b981;
}

.battery-low {
  color: #f59e0b;
}

.battery-critical {
  color: #ef4444;
  animation: blink 1s infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* UPS 状态徽章 */
.ups-status-badge {
  padding: 0.1875rem 0.5rem;
  border-radius: 9999px;
  font-size: 0.6875rem;
  font-weight: 600;
}

.status-online {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
}

.status-battery {
  background: rgba(245, 158, 11, 0.15);
  color: #f59e0b;
}

.status-critical {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
  animation: blink 1s infinite;
}

.status-offline {
  background: rgba(107, 114, 128, 0.15);
  color: #6b7280;
}

/* 导航栏关机按钮（红色） */
.btn-shutdown-nav {
  width: 32px;
  height: 32px;
  background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: 1rem;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-shutdown-nav:hover {
  transform: scale(1.05);
  box-shadow: 0 4px 12px rgba(220, 38, 38, 0.4);
}

.btn-shutdown-nav:active {
  transform: scale(0.95);
}

/* 导航栏开机按钮（绿色） */
.btn-power-on-nav {
  width: 32px;
  height: 32px;
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: 1rem;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-power-on-nav:hover {
  transform: scale(1.05);
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.4);
}

.btn-power-on-nav:active {
  transform: scale(0.95);
}

/* 全局诊断面板样式（流式布局，不覆盖导航） */
.global-diagnostics-overlay {
  background: var(--bg-primary);
  min-height: calc(100vh - 100px); /* 减去导航栏和边距 */
  padding: var(--spacing-lg);
}

.global-diagnostics-container {
  max-width: 800px;
  margin: 0 auto;
}

.global-diagnostics-overlay .diagnostics-card {
  background: var(--bg-secondary);
  border-radius: var(--radius-lg);
  padding: var(--spacing-xl);
  box-shadow: var(--shadow-lg);
}

.global-diagnostics-overlay .diagnostics-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
  padding-bottom: var(--spacing-md);
  border-bottom: 1px solid var(--border-color);
}

.global-diagnostics-overlay .diagnostics-header .diagnostics-icon {
  font-size: 2rem;
}

.global-diagnostics-overlay .diagnostics-header h2 {
  flex: 1;
  margin: 0;
  font-size: 1.5rem;
  color: var(--text-primary);
}

.global-diagnostics-overlay .diagnostics-actions {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.global-diagnostics-overlay .auto-refresh-hint {
  font-size: 0.75rem;
  color: var(--text-secondary);
  padding: 4px 8px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-sm);
}

.global-diagnostics-overlay .diagnostics-status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
}

.global-diagnostics-overlay .status-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-md);
  background: var(--bg-primary);
  border-radius: var(--radius-md);
  border-left: 4px solid var(--border-color);
}

.global-diagnostics-overlay .status-item.status-ok {
  border-left-color: #10b981;
}

.global-diagnostics-overlay .status-item.status-warning {
  border-left-color: #f59e0b;
}

.global-diagnostics-overlay .status-item.status-error {
  border-left-color: #ef4444;
}

.global-diagnostics-overlay .status-item.status-unknown {
  border-left-color: #6b7280;
}

.global-diagnostics-overlay .status-item .status-icon {
  font-size: 1.5rem;
}

.global-diagnostics-overlay .status-item .status-info {
  flex: 1;
  min-width: 0;
}

.global-diagnostics-overlay .status-item .status-label {
  font-size: 0.875rem;
  color: var(--text-secondary);
  margin-bottom: 0.25rem;
}

.global-diagnostics-overlay .status-item .status-message {
  font-size: 0.9375rem;
  color: var(--text-primary);
  word-break: break-word;
}

/* 诊断日志 */
.global-diagnostics-overlay .diagnostics-logs {
  margin-bottom: var(--spacing-lg);
  background: var(--bg-primary);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.global-diagnostics-overlay .logs-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--bg-tertiary);
  border-bottom: 1px solid var(--border-color);
  font-weight: 600;
  font-size: 0.875rem;
}

.global-diagnostics-overlay .logs-header .btn-text {
  padding: 4px 8px;
  font-size: 0.75rem;
  color: var(--text-secondary);
  background: transparent;
  border: none;
  cursor: pointer;
  border-radius: var(--radius-sm);
  transition: all 0.2s;
}

.global-diagnostics-overlay .logs-header .btn-text:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.global-diagnostics-overlay .diagnostics-logs.nut-logs {
  margin-top: var(--spacing-md);
}

.global-diagnostics-overlay .diagnostics-logs.nut-logs .logs-header {
  background: rgba(59, 130, 246, 0.1);
}

.global-diagnostics-overlay .logs-content {
  max-height: 200px;
  overflow-y: auto;
  padding: var(--spacing-md);
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 0.8125rem;
  line-height: 1.6;
}

.global-diagnostics-overlay .log-line {
  padding: 0.25rem 0;
  color: var(--text-secondary);
}

.global-diagnostics-overlay .log-line.log-error {
  color: #ef4444;
}

.global-diagnostics-overlay .log-line.log-warning {
  color: #f59e0b;
}

.global-diagnostics-overlay .log-line.log-success {
  color: #10b981;
}

/* 故障排查建议 */
.global-diagnostics-overlay .diagnostics-tips {
  background: var(--bg-primary);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
}

.global-diagnostics-overlay .diagnostics-tips h4 {
  margin: 0 0 var(--spacing-sm) 0;
  font-size: 1rem;
  color: var(--text-primary);
}

.global-diagnostics-overlay .diagnostics-tips ul {
  margin: 0;
  padding-left: var(--spacing-lg);
  color: var(--text-secondary);
  font-size: 0.875rem;
  line-height: 1.8;
}

.global-diagnostics-overlay .diagnostics-tips ul ul {
  margin-top: 0.5rem;
}

.global-diagnostics-overlay .diagnostics-tips li {
  margin-bottom: 0.5rem;
}

.global-diagnostics-overlay .diagnostics-tips code {
  background: var(--bg-tertiary);
  padding: 0.125rem 0.375rem;
  border-radius: var(--radius-sm);
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 0.8125rem;
}

.global-diagnostics-overlay .diagnostics-tips strong {
  color: var(--text-primary);
}

/* 响应式 */
@media (max-width: 640px) {
  .global-diagnostics-container {
    padding: var(--spacing-md);
  }

  .global-diagnostics-overlay .diagnostics-card {
    padding: var(--spacing-md);
  }

  .global-diagnostics-overlay .diagnostics-header {
    flex-wrap: wrap;
  }

  .global-diagnostics-overlay .diagnostics-actions {
    width: 100%;
    margin-top: var(--spacing-sm);
  }

  .global-diagnostics-overlay .diagnostics-actions .btn {
    flex: 1;
  }
}
</style>

