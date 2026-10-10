"""UPS 状态监控引擎"""
import asyncio
import os
import time
import logging
from collections import deque
from datetime import datetime
from typing import Optional, Callable
from models import UpsStatus, UpsData, EventType, Metric
from services.nut_client import NutClientInterface
from services.shutdown_manager import ShutdownManager
from services.history import get_history_service
from services.notifier import get_notifier_service
from services.driver_event_source import read_driver_variables

logger = logging.getLogger(__name__)


class UpsMonitor:
    """UPS 监控器 - 状态机模式"""
    
    def __init__(
        self,
        nut_client: NutClientInterface,
        shutdown_manager: ShutdownManager,
        poll_interval: int = 5,
        sample_interval: int = 60,
        config = None
    ):
        """
        初始化监控器
        
        Args:
            nut_client: NUT 客户端
            shutdown_manager: 关机管理器
            poll_interval: 状态轮询间隔（秒）
            sample_interval: 指标采样间隔（秒）
            config: 系统配置对象
        """
        self.nut_client = nut_client
        self.shutdown_manager = shutdown_manager
        self.poll_interval = poll_interval
        self.sample_interval = sample_interval
        self.config = config
        
        self._current_status = UpsStatus.OFFLINE
        self._last_power_status = None  # Connectivity loss is not a power transition.
        self._current_data: Optional[UpsData] = None
        self._monitor_task: Optional[asyncio.Task] = None
        self._sample_task: Optional[asyncio.Task] = None
        self._running = False
        self._last_sample_time = datetime.now()
        self._connection_notified = False  # 跟踪是否已通知连接断开
        
        # 重连优化相关
        self._reconnect_count = 0  # 重连尝试次数
        self._last_reconnect_attempt = datetime.now()  # 上次重连尝试时间
        
        # 状态变化回调
        self._status_callbacks = []
        
        # 事件驱动相关
        self._event_driven_client = None
        self._event_mode_active = False
        self._driver_bridge_data = {}
        self._driver_bridge_seen = 0.0
        self._driver_bridge_frames = 0
        self._driver_bridge_seq = 0  # 每个非心跳帧递增
        self._driver_bridge_consumed_seq = 0  # 监控循环已处理到的帧序号
        self._driver_bridge_statuses = deque(maxlen=512)
        self._driver_bridge_wakeup = asyncio.Event()
        self._communication_count_today = 0
        self._last_persisted_count = -1  # 避免事件缓存重复读取时反复持久化同一计数
        self._last_update_time: Optional[datetime] = None
        self._start_time = datetime.now()
        
        # 响应时间统计
        self._response_times = []  # 今日所有响应时间（毫秒）
        self._stats_date = datetime.now().date()  # 统计日期

        # 电池电量平滑（断电前5分钟避免电压骤降导致的读数跳变）
        self._battery_on_battery_since: Optional[datetime] = None  # 开始电池供电的时间
        self._battery_initial_charge: Optional[float] = None  # 断电初始电量
        self._battery_charge_buffer: list = []  # 电量读数缓冲
        self._BATTERY_SMOOTH_WINDOW = 300  # 平滑窗口：5分钟（秒）

        # 智能采样间隔
        self._sample_interval_normal = 300  # 正常状态：5分钟
        self._sample_interval_active = 10   # 活跃状态（断电/变化）：10秒
    
    def add_status_callback(self, callback: Callable[[UpsData], None]):
        """添加状态变化回调"""
        self._status_callbacks.append(callback)
    
    async def start(self, max_initial_retries: int = 5):
        """启动监控，带初始连接重试
        
        Args:
            max_initial_retries: 启动时最大重试次数，默认 5 次
        """
        if self._running:
            logger.warning("Monitor already running")
            return
        
        self._running = True
        
        # 连接状态由 monitor 自身的 _monitor_loop 统一管理
        # 不再依赖 NUT 客户端的回调机制，避免重复通知

        # 启动时连接重试
        connected = False
        for attempt in range(max_initial_retries):
            try:
                await self.nut_client.connect()
                logger.info(f"Successfully connected to NUT server on attempt {attempt + 1}")
                connected = True
                break
            except Exception as e:
                if attempt < max_initial_retries - 1:
                    delay = min(2 ** attempt, 30)  # 指数退避，上限 30 秒
                    logger.warning(
                        f"Initial connection failed (attempt {attempt + 1}/{max_initial_retries}), "
                        f"retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"Failed to connect after {max_initial_retries} attempts: {e}. "
                        f"Monitor will continue running and retry in background."
                    )
                    self._current_status = UpsStatus.OFFLINE
        
        # 如果初始连接成功，检测当前状态
        if connected:
            await self._check_initial_status()
        
        # 即使初始连接失败，也启动监控循环（它会持续尝试重连）
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        

    async def _check_initial_status(self):
        """启动时检测初始状态，如果是异常状态则发送通知"""
        try:
            data = await self._read_ups_data()
            if not data:
                return

            self._current_data = data
            self._current_status = data.status
            if data.status in (UpsStatus.ONLINE, UpsStatus.ON_BATTERY, UpsStatus.LOW_BATTERY):
                self._last_power_status = data.status

            history_service = await get_history_service()
            notifier_service = get_notifier_service()

            # 如果启动时就是电池供电状态，发送通知
            if data.status == UpsStatus.ON_BATTERY:
                logger.warning(f"Startup detected: UPS is on battery power (charge: {data.battery_charge}%)")
                await history_service.add_event(
                    EventType.POWER_LOST,
                    f"启动时检测到 UPS 处于电池供电状态，电量：{data.battery_charge}%",
                    metadata={
                        "battery_charge": data.battery_charge,
                        "battery_runtime": data.battery_runtime,
                        "input_voltage": data.input_voltage,
                        "output_voltage": data.output_voltage,
                        "load_percent": data.load_percent,
                        "ups_status": data.status.value if data.status else None,
                        "trigger": "startup_detection"
                    }
                )
                await notifier_service.notify(
                    EventType.POWER_LOST,
                    "UPS 处于电池供电状态",
                    f"服务启动时检测到 UPS 正在使用电池供电，当前电量：{data.battery_charge}%",
                    metadata=self._build_notification_metadata(data, "启动检测到电池供电")
                )

            elif data.status == UpsStatus.LOW_BATTERY:
                logger.warning(f"Startup detected: UPS is on low battery (charge: {data.battery_charge}%)")
                await history_service.add_event(
                    EventType.LOW_BATTERY,
                    f"启动时检测到 UPS 电池电量过低：{data.battery_charge}%",
                    metadata={
                        "battery_charge": data.battery_charge,
                        "battery_runtime": data.battery_runtime,
                        "input_voltage": data.input_voltage,
                        "output_voltage": data.output_voltage,
                        "load_percent": data.load_percent,
                        "ups_status": data.status.value if data.status else None,
                        "trigger": "startup_detection"
                    }
                )
                await notifier_service.notify(
                    EventType.LOW_BATTERY,
                    "UPS 电池电量过低",
                    f"服务启动时检测到 UPS 电池电量过低：{data.battery_charge}%，请立即检查！",
                    metadata=self._build_notification_metadata(data, "启动检测到低电量")
                )

            elif data.status == UpsStatus.OFFLINE:
                logger.warning("Startup detected: UPS is offline")
                await history_service.add_event(
                    EventType.POWER_LOST,
                    "启动时检测到 UPS 离线，无法获取状态",
                    metadata={
                        "ups_status": "offline",
                        "trigger": "startup_detection"
                    }
                )
        except Exception as e:
            logger.error(f"Error checking initial status: {e}")
    
    async def _handle_connection_lost(self):
        """处理 NUT 连接丢失"""
        try:
            history_service = await get_history_service()
            notifier_service = get_notifier_service()
            
            logger.warning("NUT connection lost")
            
            # 收集详细的诊断信息
            metadata = {
                "trigger": "nut_connection_lost",
                "timestamp": datetime.now().isoformat(),
                "reconnect_count": self._reconnect_count if hasattr(self, '_reconnect_count') else 0,
            }
            
            # 尝试获取 NUT 客户端的连接状态
            if hasattr(self.nut_client, 'get_connection_status'):
                try:
                    conn_status = self.nut_client.get_connection_status()
                    metadata.update(conn_status)
                except Exception as e:
                    logger.debug(f"Failed to get connection status: {e}")
            
            await history_service.add_event(
                EventType.NUT_DISCONNECTED,
                "NUT 服务器连接断开，正在尝试重新连接...",
                metadata=metadata
            )
            await notifier_service.notify(
                EventType.NUT_DISCONNECTED,
                "NUT 连接断开",
                "UPS Guard 与 NUT 服务器的连接已断开，正在尝试自动重新连接。",
                metadata=metadata
            )

            # 通过 WebSocket 广播连接状态变化，让前端实时感知
            try:
                from api.websocket import broadcast_event, manager
                logger.info("Broadcasting NUT_DISCONNECTED event to WebSocket clients...")
                await broadcast_event(
                    "NUT_DISCONNECTED",
                    "NUT 服务器连接断开",
                    {"status": "disconnected", "reason": "connection_lost"}
                )
                logger.info("NUT_DISCONNECTED event broadcast completed")

                # 同时推送一个状态更新，将 status 设为 offline，确保前端 wsData 更新
                logger.info("Broadcasting offline status update...")
                await manager.broadcast({
                    "type": "status_update",
                    "data": {
                        "status": "offline",
                        "last_update": None,
                        "shutdown": self.shutdown_manager.get_status() if self.shutdown_manager else {}
                    }
                })
                logger.info("Offline status update broadcast completed")
            except Exception as e:
                logger.error(f"Failed to broadcast connection lost event: {e}")
        except Exception as e:
            logger.error(f"Error handling connection lost: {e}")
    
    async def _handle_connection_restored(self):
        """处理 NUT 连接恢复"""
        try:
            history_service = await get_history_service()
            notifier_service = get_notifier_service()
            
            logger.info("NUT connection restored")
            
            # 收集详细的诊断信息
            metadata = {
                "trigger": "nut_connection_restored",
                "timestamp": datetime.now().isoformat(),
                "reconnect_count": self._reconnect_count if hasattr(self, '_reconnect_count') else 0,
            }
            
            # 获取当前 UPS 数据快照
            if self._current_data:
                metadata.update({
                    "ups_status": self._current_data.status.value,
                    "battery_charge": self._current_data.battery_charge,
                    "input_voltage": self._current_data.input_voltage,
                })
            
            await history_service.add_event(
                EventType.NUT_RECONNECTED,
                "NUT 服务器连接已恢复",
                metadata=metadata
            )
            await notifier_service.notify(
                EventType.NUT_RECONNECTED,
                "NUT 连接恢复",
                "UPS Guard 已成功重新连接到 NUT 服务器。",
                metadata=metadata
            )

            # 通过 WebSocket 广播连接状态变化，让前端实时感知
            try:
                from api.websocket import broadcast_event
                logger.info("Broadcasting NUT_RECONNECTED event to WebSocket clients...")
                await broadcast_event(
                    "NUT_RECONNECTED",
                    "NUT 服务器连接已恢复",
                    {"status": "connected", "reason": "reconnection_successful"}
                )
                logger.info("NUT_RECONNECTED event broadcast completed")
            except Exception as e:
                logger.error(f"Failed to broadcast connection restored event: {e}")
        except Exception as e:
            logger.error(f"Error handling connection restored: {e}")


    async def stop(self):
        """停止监控"""
        self._running = False
        
        # 停止事件驱动模式
        await self._stop_event_driven_mode()
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        # 持久化最终统计
        await self._persist_daily_stats()
        
        await self.nut_client.disconnect()
        

    async def force_update(self):
        """强制立即更新状态并广播（用于 Mock API 调用后立即响应）"""
        try:
            data = await self._read_ups_data()

            if data:
                old_status = self._current_status
                self._current_data = data
                self._current_status = data.status

                # 检测状态变化
                if old_status != self._current_status:
                    await self._on_status_changed(old_status, self._current_status, data)

                # 根据状态执行相应操作
                await self._handle_status(data)

                # 触发回调（广播 WebSocket）
                for callback in self._status_callbacks:
                    try:
                        await callback(data)
                    except Exception as e:
                        logger.error(f"Error in status callback: {e}")

                logger.debug("Forced status update completed")
        except Exception as e:
            logger.error(f"Error in force_update: {e}")

    async def _monitor_loop(self):
        """监控循环"""
        try:
            # 尝试启动事件驱动模式
            if self.config and self.config.event_driven_enabled:
                if self.config.monitoring_mode in ("event_driven", "hybrid"):
                    await self._try_start_event_driven_mode()
            
            while self._running:
                try:
                    # 检查并重置每日统计
                    await self._check_and_reset_daily_stats()
                    
                    # 读取 UPS 状态
                    data = await self._read_ups_data()
                    
                    if data:
                        # 处理 UPS 数据
                        await self._process_ups_data(data)
                        
                        # 每60次通信持久化一次统计（约每5分钟）
                        if (self._communication_count_today % 60 == 0
                                and self._communication_count_today != self._last_persisted_count):
                            self._last_persisted_count = self._communication_count_today
                            await self._persist_daily_stats()
                        
                        # 根据模式调整轮询间隔
                        if not self._event_mode_active:
                            # 纯轮询模式或事件驱动失败
                            poll_interval = self.poll_interval
                        else:
                            # 事件驱动模式下，使用较长的轮询间隔作为备份
                            poll_interval = self.config.poll_interval_fallback if self.config else 60
                        
                        if self._bridge_active():
                            if self._driver_bridge_statuses:
                                continue
                            try:
                                await asyncio.wait_for(self._driver_bridge_wakeup.wait(), timeout=min(poll_interval, 15))
                            except asyncio.TimeoutError:
                                pass
                            self._driver_bridge_wakeup.clear()
                        else:
                            await asyncio.sleep(poll_interval)
                    else:
                        if self._bridge_active():
                            await asyncio.sleep(1)  # Let event ingress run while the stream is unavailable.
                        # 无法读取状态，标记为离线并主动重连
                        logger.warning(f"Lost connection to UPS, _connection_notified={self._connection_notified}, attempting reconnect...")
                        self._current_status = UpsStatus.OFFLINE

                        # 发送连接断开通知（仅一次，直到恢复后才能再次发送）
                        if not self._connection_notified:
                            logger.info("Sending NUT_DISCONNECTED notification...")
                            await self._handle_connection_lost()
                            self._connection_notified = True
                            logger.info("NUT_DISCONNECTED notification sent")

                        # 主动触发重连（如果是 RealNutClient）- 使用递增延迟
                        if not self._bridge_active() and hasattr(self.nut_client, '_reconnect'):
                            # 计算重连间隔：使用递增延迟避免频繁重连
                            # 前 5 次快速重试（5s, 10s, 15s, 20s, 25s）
                            # 之后使用固定间隔（60s）
                            if self._reconnect_count < 5:
                                reconnect_interval = (self._reconnect_count + 1) * 5
                            else:
                                reconnect_interval = 60
                            
                            # 检查是否到达重连时间
                            time_since_last_attempt = (datetime.now() - self._last_reconnect_attempt).total_seconds()
                            if time_since_last_attempt >= reconnect_interval:
                                self._last_reconnect_attempt = datetime.now()
                                self._reconnect_count += 1
                                
                                logger.info(f"Attempting reconnection #{self._reconnect_count} (interval: {reconnect_interval}s)...")
                                
                                try:
                                    reconnected = await self.nut_client._reconnect()
                                    if reconnected:
                                        # 验证连接：立即读取数据
                                        verify_data = await self._read_ups_data()
                                        if verify_data:
                                            logger.info(f"Connection restored and verified (reconnected on attempt #{self._reconnect_count})")
                                            self._reconnect_count = 0  # 重置计数器
                                            # 连接恢复通知会在下次循环时发送（通过 _connection_notified 标志）
                                        else:
                                            logger.warning("Reconnection succeeded but data read failed")
                                    else:
                                        logger.debug(f"Reconnection attempt #{self._reconnect_count} failed")
                                except Exception as reconnect_error:
                                    logger.debug(f"Reconnection attempt #{self._reconnect_count} failed: {reconnect_error}")
                                
                                # 通过 WebSocket 广播重连状态
                                try:
                                    from api.websocket import broadcast_status_update
                                    # 在下次数据更新时会包含 reconnect_count
                                    if self._current_data:
                                        await broadcast_status_update(self._current_data)
                                except Exception as e:
                                    logger.debug(f"Failed to broadcast reconnect status: {e}")
                            else:
                                # 还没到重连时间，记录调试信息
                                wait_time = reconnect_interval - time_since_last_attempt
                                logger.debug(
                                    f"Waiting {wait_time:.1f}s before next reconnection attempt "
                                    f"(#{self._reconnect_count + 1}, interval: {reconnect_interval}s)"
                                )
                
                except Exception as e:
                    logger.error(f"Error in monitor loop: {e}")
                    # 错误后也需要等待
                    await asyncio.sleep(5)
        
        except asyncio.CancelledError:
            pass
        finally:
            # 清理事件驱动模式
            await self._stop_event_driven_mode()

    async def _read_ups_data(self) -> Optional[UpsData]:
        """读取 UPS 数据"""
        start_time = datetime.now()
        
        try:
            source = 'poll'
            if self._bridge_active():
                vars_dict, source = await read_driver_variables(self)
            else:
                vars_dict = await self.nut_client.list_vars()
            
            if not vars_dict:
                logger.debug("_read_ups_data: vars_dict is empty, returning None")
                return None
            
            # 计算响应时间
            response_time_ms = (datetime.now() - start_time).total_seconds() * 1000
            # 只有真实的 NUT 查询计入响应时间；只有新数据（查询或新事件帧）
            # 计入通信次数和最后更新时间，避免重复读取事件缓存造成统计失真
            if source == 'poll':
                self._response_times.append(response_time_ms)
            if source != 'cache':
                self._communication_count_today += 1
                self._last_update_time = datetime.now()
            
            # 限制响应时间数组大小（保留最近100次）
            if len(self._response_times) > 100:
                self._response_times = self._response_times[-100:]
            
            logger.debug(f"_read_ups_data: got {len(vars_dict)} variables, response time: {response_time_ms:.2f}ms")

            # 解析状态
            status_str = vars_dict.get("ups.status", "")
            status = self._parse_status(status_str)
            # 解析状态标志位列表
            status_flags = status_str.split() if status_str else []

            # 获取原始告警信息
            raw_alarm = vars_dict.get("ups.alarm")

            # 过滤已知的固件误报告警
            # W120 (openUPS HID 0.5) 固件 bug: 电池正常但误报 "No battery installed!"
            filtered_alarm = self._filter_false_alarms(raw_alarm, vars_dict)

            # 过滤状态标志中因误报产生的 ALARM 标志
            filtered_status_flags = self._filter_alarm_status_flags(
                status_flags, raw_alarm, filtered_alarm
            )
            filtered_status_str = " ".join(filtered_status_flags) if filtered_status_flags else status_str

            # 解析输出电压（如果 UPS 不直接报告，则根据输入电压和状态推算）
            output_voltage = self._parse_float(vars_dict.get("output.voltage"))
            input_voltage = self._parse_float(vars_dict.get("input.voltage"))
            input_voltage_nominal = self._parse_float(vars_dict.get("input.voltage.nominal")) or 230.0
            output_voltage_estimated = False

            if output_voltage is None and input_voltage is not None:
                output_voltage = self._estimate_output_voltage(
                    input_voltage, input_voltage_nominal, filtered_status_flags
                )
                output_voltage_estimated = output_voltage is not None

            # 解析电池电量并应用平滑（避免断电初期电压骤降导致的读数跳变）
            raw_battery_charge = self._parse_float(vars_dict.get("battery.charge"))
            battery_charge = self._smooth_battery_charge(raw_battery_charge)

            # 解析其他数据
            data = UpsData(
                status=status,
                status_raw=filtered_status_str,  # 保留过滤后的状态字符串
                status_flags=filtered_status_flags,  # 过滤后的状态标志位列表
                battery_charge=battery_charge,
                battery_runtime=self._parse_int(vars_dict.get("battery.runtime")),
                input_voltage=input_voltage,
                output_voltage=output_voltage,
                output_voltage_estimated=output_voltage_estimated,
                load_percent=self._parse_float(vars_dict.get("ups.load")),
                temperature=self._parse_float(vars_dict.get("ups.temperature")),
                # UPS 型号和制造商：优先使用 device.* 字段，兼容 ups.* 字段
                ups_model=vars_dict.get("device.model") or vars_dict.get("ups.model"),
                ups_manufacturer=vars_dict.get("device.mfr") or vars_dict.get("ups.mfr"),
                # 新增字段
                ups_power_nominal=self._parse_float(vars_dict.get("ups.power.nominal")),
                ups_realpower=self._parse_float(vars_dict.get("ups.realpower")),
                battery_voltage=self._parse_float(vars_dict.get("battery.voltage")),
                battery_voltage_nominal=self._parse_float(vars_dict.get("battery.voltage.nominal")),
                battery_temperature=self._parse_float(vars_dict.get("battery.temperature")),
                # Phase 1 扩展字段
                input_frequency=self._parse_float(vars_dict.get("input.frequency")),
                output_frequency=self._parse_float(vars_dict.get("output.frequency")),
                output_current=self._parse_float(vars_dict.get("output.current")),
                output_current_nominal=self._parse_float(vars_dict.get("output.current.nominal")),
                ups_efficiency=self._parse_float(vars_dict.get("ups.efficiency")),
                battery_type=vars_dict.get("battery.type"),
                battery_date=vars_dict.get("battery.date"),
                battery_mfr_date=vars_dict.get("battery.mfr.date"),
                battery_packs=self._parse_int(vars_dict.get("battery.packs")),
                battery_packs_bad=self._parse_int(vars_dict.get("battery.packs.bad")),
                # Phase 2 扩展字段 - 电压质量
                input_voltage_min=self._parse_float(vars_dict.get("input.voltage.minimum")),
                input_voltage_max=self._parse_float(vars_dict.get("input.voltage.maximum")),
                input_transfer_low=self._parse_float(vars_dict.get("input.transfer.low")),
                input_transfer_high=self._parse_float(vars_dict.get("input.transfer.high")),
                # Phase 2 扩展字段 - 环境监控
                ambient_temperature=self._parse_float(vars_dict.get("ambient.temperature")),
                ambient_humidity=self._parse_float(vars_dict.get("ambient.humidity")),
                ambient_temperature_alarm=vars_dict.get("ambient.temperature.alarm"),
                ambient_humidity_alarm=vars_dict.get("ambient.humidity.alarm"),
                # Phase 3 扩展字段 - 自检和报警
                ups_test_result=vars_dict.get("ups.test.result"),
                ups_test_date=vars_dict.get("ups.test.date"),
                ups_alarm=filtered_alarm,  # 使用过滤后的告警信息
                ups_beeper_status=vars_dict.get("ups.beeper.status"),
                # Phase 4 扩展字段 - 基于真实 UPS 测试
                ups_realpower_nominal=self._parse_float(vars_dict.get("ups.realpower.nominal")),
                input_voltage_nominal=self._parse_float(vars_dict.get("input.voltage.nominal")),
                battery_charge_low=self._parse_float(vars_dict.get("battery.charge.low")),
                battery_runtime_low=self._parse_int(vars_dict.get("battery.runtime.low")),
                input_transfer_reason=vars_dict.get("input.transfer.reason"),
                input_sensitivity=vars_dict.get("input.sensitivity"),
                ups_delay_shutdown=self._parse_int(vars_dict.get("ups.delay.shutdown")),
                # 设备序列号：优先使用 device.serial，兼容 ups.serial
                ups_serial=vars_dict.get("device.serial") or vars_dict.get("ups.serial"),
                ups_mfr_date=vars_dict.get("ups.mfr.date"),
                ups_productid=vars_dict.get("ups.productid"),
                ups_vendorid=vars_dict.get("ups.vendorid"),
                # 电池充电器状态 (NUT 标准)
                battery_charger_status=vars_dict.get("battery.charger.status"),
                # 续航时间来源：检查 driver.parameter.runtimecal 是否存在
                # 存在 = 软件估算，不存在 = UPS 硬件直报
                runtime_estimated=vars_dict.get("driver.parameter.runtimecal") is not None,
                # 连接状态
                nut_reconnect_count=self._reconnect_count if self._reconnect_count > 0 else None,
                # apcupsd 特有参数
                transfer_count=self._parse_int(vars_dict.get("ups.transfer.count")),
                time_on_battery=self._parse_int(vars_dict.get("ups.time.on_battery")),
                cumulative_on_battery=self._parse_int(vars_dict.get("ups.cumulative.on_battery")),
                ups_alarm_del=vars_dict.get("ups.alarm.delay"),
                ups_starttime=vars_dict.get("ups.starttime"),
                ups_backend=self.config.ups_backend if self.config and hasattr(self.config, 'ups_backend') else "nut",
                last_update=datetime.now()
            )

            # 过滤无效的固件占位日期（如 "2001/09/25" 是 APC UPS 默认占位符）
            INVALID_DATES = {"2001/09/25", "2001-01-01", "1970/01/01"}
            if data.battery_mfr_date in INVALID_DATES:
                data.battery_mfr_date = None
            if data.ups_mfr_date in INVALID_DATES:
                data.ups_mfr_date = None
            if data.battery_date in INVALID_DATES:
                data.battery_date = None

            # 计算电压质量评分
            from services.voltage_quality import assess_voltage_quality
            vq = assess_voltage_quality(
                input_voltage=input_voltage,
                input_voltage_nominal=input_voltage_nominal,
                input_voltage_min=data.input_voltage_min,
                input_voltage_max=data.input_voltage_max,
                input_transfer_low=data.input_transfer_low,
                input_transfer_high=data.input_transfer_high,
                status_flags=filtered_status_flags,
            )
            if vq:
                data.voltage_quality_score = vq.score
                data.voltage_quality_grade = vq.grade

            return data
        
        except Exception as e:
            logger.error(f"Error reading UPS data: {e}")
            return None
    
    # 已知的固件误报告警列表
    # key: 告警文本（小写）, value: 验证函数名（返回 True 表示确认是误报）
    KNOWN_FALSE_ALARMS = {
        "no battery installed!": "_verify_battery_present",
    }

    def _filter_false_alarms(
        self, raw_alarm: Optional[str], vars_dict: dict
    ) -> Optional[str]:
        """过滤已知的固件误报告警

        某些 UPS 固件（如 W120 openUPS HID 0.5）会在电池正常时
        误报告警信息。通过检查实际电池数据来判断是否为误报。
        """
        if not raw_alarm:
            return None

        alarm_lower = raw_alarm.strip().lower()
        verify_method_name = self.KNOWN_FALSE_ALARMS.get(alarm_lower)

        if verify_method_name:
            verify_method = getattr(self, verify_method_name, None)
            if verify_method and verify_method(vars_dict):
                logger.info(
                    f"Filtered false alarm: '{raw_alarm}' "
                    f"(battery data confirms battery is present)"
                )
                return None

        return raw_alarm

    def _verify_battery_present(self, vars_dict: dict) -> bool:
        """验证电池是否实际存在（用于过滤 'No battery installed!' 误报）

        如果以下任一条件满足，认为电池存在，告警为误报:
        - battery.charge 有有效值且 > 0
        - battery.voltage 有有效值且 > 0
        - battery.runtime 有有效值且 > 0
        """
        try:
            charge = self._parse_float(vars_dict.get("battery.charge"))
            voltage = self._parse_float(vars_dict.get("battery.voltage"))
            runtime = self._parse_int(vars_dict.get("battery.runtime"))

            battery_present = (
                (charge is not None and charge > 0)
                or (voltage is not None and voltage > 0)
                or (runtime is not None and runtime > 0)
            )
            return battery_present
        except Exception:
            return False

    def _filter_alarm_status_flags(
        self,
        status_flags: list,
        raw_alarm: Optional[str],
        filtered_alarm: Optional[str],
    ) -> list:
        """如果告警被过滤掉了，同时从状态标志中移除 ALARM 标志"""
        if raw_alarm and not filtered_alarm and "ALARM" in status_flags:
            return [f for f in status_flags if f != "ALARM"]
        return status_flags

    def _parse_status(self, status_str: str) -> UpsStatus:
        """解析 UPS 状态字符串
        
        优先级：OL (市电供电) > OB (电池供电) > LB (低电量)
        只要有市电供电(OL)，无论电池电量如何，都不应该触发关机
        """
        status_str = status_str.upper()
        
        # 优先检查是否在线供电 - 只要有市电，就是 ONLINE 状态
        if "OL" in status_str:  # Online - 市电供电
            return UpsStatus.ONLINE
        # 其次检查是否使用电池供电
        elif "OB" in status_str:  # On Battery - 电池供电
            # 如果同时有 LB 标志，表示电池供电且电量低
            if "LB" in status_str:
                return UpsStatus.LOW_BATTERY
            else:
                return UpsStatus.ON_BATTERY
        # 单独的 LB 标志（不常见，但也处理）
        elif "LB" in status_str:
            return UpsStatus.LOW_BATTERY
        else:
            return UpsStatus.OFFLINE
    
    def _parse_float(self, value: Optional[str]) -> Optional[float]:
        """解析浮点数"""
        if value is None:
            return None
        try:
            return float(value)
        except ValueError:
            return None
    
    def _parse_int(self, value: Optional[str]) -> Optional[int]:
        """解析整数"""
        if value is None:
            return None
        try:
            return int(float(value))
        except ValueError:
            return None

    def _estimate_output_voltage(
        self,
        input_voltage: float,
        input_voltage_nominal: float,
        status_flags: list,
    ) -> Optional[float]:
        """
        根据输入电压和 UPS 状态推算输出电压

        适用于不直接报告 output.voltage 的 UPS（如 APC Back-UPS RS 系列）

        推算逻辑（基于线路交互式 UPS 工作原理）：
        - OL（市电直通）：输出 ≈ 输入，经过 AVR 微调
        - BOOST（升压）：输入过低时升压至接近额定值
        - TRIM（降压）：输入过高时降至接近额定值
        - OB（电池供电）：逆变器输出额定电压
        """
        if input_voltage is None:
            return None

        flags = [f.upper() for f in status_flags]

        # 电池供电模式：逆变器输出稳定的额定电压
        if "OB" in flags:
            return input_voltage_nominal

        # BOOST 模式：输入电压过低，UPS 升压
        # APC 典型升压幅度约 12-15%
        if "BOOST" in flags:
            return round(input_voltage * 1.12, 1)

        # TRIM 模式：输入电压过高，UPS 降压
        # APC 典型降压幅度约 12-15%
        if "TRIM" in flags:
            return round(input_voltage * 0.88, 1)

        # OL（在线）无 AVR 调节：输出 ≈ 输入
        # 线路交互式 UPS 在输入正常时直接旁路，压降可忽略
        if "OL" in flags:
            return round(input_voltage, 1)

        # 未知状态，返回 None
        return None

    def _smooth_battery_charge(self, raw_charge: Optional[float]) -> Optional[float]:
        """
        平滑电池电量读数（仅在断电前5分钟生效）

        铅酸电池特性：接入负载后电压骤降，导致 UPS 固件报告的电量快速下降
        （如 100% → 96% 在2分钟内），但这不代表真实电量消耗。

        平滑策略：
        - 断电前5分钟内：使用初始电量和当前读数的加权平均
        - 权重随时间递减：t=0 时 100% 使用初始值，t=5min 后完全使用实时值
        - 超过5分钟后：完全使用实时读数
        """
        if raw_charge is None:
            return None

        # 不在电池供电状态，直接返回原始值
        if self._battery_on_battery_since is None:
            return raw_charge

        # 初始电量为空，无法平滑
        if self._battery_initial_charge is None:
            return raw_charge

        # 计算已过时间
        elapsed = (datetime.now() - self._battery_on_battery_since).total_seconds()

        # 超过平滑窗口，使用实时值
        if elapsed >= self._BATTERY_SMOOTH_WINDOW:
            return round(raw_charge, 1)

        # 缓冲读数用于计算实际下降趋势
        self._battery_charge_buffer.append(raw_charge)

        # 线性插值：初始值权重随时间递减
        weight_initial = 1.0 - (elapsed / self._BATTERY_SMOOTH_WINDOW)

        # 平滑后的值 = 初始值 * 权重 + 当前值 * (1 - 权重)
        smoothed = self._battery_initial_charge * weight_initial + raw_charge * (1 - weight_initial)

        # 不低于当前读数（避免平滑后反而更低）
        smoothed = max(smoothed, raw_charge)

        logger.debug(
            f"Battery smoothing: raw={raw_charge}%, initial={self._battery_initial_charge}%, "
            f"elapsed={elapsed:.0f}s, weight={weight_initial:.2f}, smoothed={smoothed:.1f}%"
        )

        return round(smoothed, 1)

    def _get_dynamic_sample_interval(self) -> int:
        """
        根据 UPS 状态动态调整采样间隔

        - 电池供电/低电量：10秒（高频率）
        - 市电正常：5分钟（低频率）
        """
        if self._current_status in (UpsStatus.ON_BATTERY, UpsStatus.LOW_BATTERY):
            return self._sample_interval_active
        return self._sample_interval_normal

    def _build_notification_metadata(self, data: UpsData, trigger_reason: str = None, power_lost_duration: int = None) -> dict:
        """
        构建通知元数据
        
        Args:
            data: UPS 数据
            trigger_reason: 触发原因（可选）
            power_lost_duration: 断电持续时间（秒，可选）
            
        Returns:
            元数据字典
        """
        metadata = {
            "ups_status": data.status.value if data else None,
            "battery_charge": data.battery_charge if data else None,
            "battery_runtime": data.battery_runtime if data else None,
            "input_voltage": data.input_voltage if data else None,
            "load_percent": data.load_percent if data else None,
        }
        
        if trigger_reason:
            metadata["trigger_reason"] = trigger_reason
        
        if power_lost_duration is not None:
            metadata["power_lost_duration"] = power_lost_duration
        
        return metadata
    
    async def _on_status_changed(self, old_status: UpsStatus, new_status: UpsStatus, data: UpsData):
        """处理状态变化"""

        # Compare confirmed power states, preserving the last state across OFFLINE.
        if new_status in (UpsStatus.ONLINE, UpsStatus.ON_BATTERY, UpsStatus.LOW_BATTERY):
            old_status = self._last_power_status or old_status
            self._last_power_status = new_status

        # 跟踪电池供电状态（用于电量平滑）
        if new_status in (UpsStatus.ON_BATTERY, UpsStatus.LOW_BATTERY) and old_status == UpsStatus.ONLINE:
            # 刚切换到电池供电
            self._battery_on_battery_since = datetime.now()
            self._battery_initial_charge = data.battery_charge
            self._battery_charge_buffer = [data.battery_charge] if data.battery_charge else []
            logger.info(f"Battery smoothing activated: initial_charge={data.battery_charge}%")
        elif new_status == UpsStatus.ONLINE and old_status in (UpsStatus.ON_BATTERY, UpsStatus.LOW_BATTERY):
            # 市电恢复，重置平滑状态
            self._battery_on_battery_since = None
            self._battery_initial_charge = None
            self._battery_charge_buffer = []

        try:
            history_service = await get_history_service()
            notifier_service = get_notifier_service()
            
            # 构建通用的 UPS 状态元数据
            ups_metadata = {
                "battery_charge": data.battery_charge,
                "battery_runtime": data.battery_runtime,
                "input_voltage": data.input_voltage,
                "output_voltage": data.output_voltage,
                "load_percent": data.load_percent,
                "old_status": old_status.value if old_status else None,
                "new_status": new_status.value if new_status else None,
            }

            # 根据新状态发送通知和记录事件
            if new_status == UpsStatus.ON_BATTERY and old_status == UpsStatus.ONLINE:
                # 市电断电
                await history_service.add_event(
                    EventType.POWER_LOST,
                    "检测到市电断电，UPS 切换到电池供电",
                    metadata={**ups_metadata, "trigger": "status_change"}
                )
                await notifier_service.notify(
                    EventType.POWER_LOST,
                    "UPS 市电断电",
                    f"UPS 已切换到电池供电，当前电量：{data.battery_charge}%",
                    metadata=self._build_notification_metadata(data, "市电断电")
                )
            
            elif new_status == UpsStatus.ONLINE and old_status in [UpsStatus.ON_BATTERY, UpsStatus.LOW_BATTERY]:
                # 市电恢复
                await history_service.add_event(
                    EventType.POWER_RESTORED,
                    "市电已恢复",
                    metadata={**ups_metadata, "trigger": "status_change"}
                )
                await notifier_service.notify(
                    EventType.POWER_RESTORED,
                    "UPS 市电恢复",
                    "市电已恢复正常供电"
                )
                
                # 来电后自动发送 WOL（如果启用）
                try:
                    from config import get_config_manager
                    from services.wol import send_wol_to_devices
                    
                    config_manager = await get_config_manager()
                    config = await config_manager.get_config()
                    
                    if config.wol_on_power_restore:

                        # 异步启动 WOL 任务（不阻塞主流程）
                        # 传入 monitor 实例以便检查电压稳定性
                        asyncio.create_task(
                            send_wol_to_devices(
                                config.pre_shutdown_hooks,
                                delay_seconds=config.wol_delay_seconds,
                                monitor=monitor,  # 传入 monitor 实例
                                check_voltage_stability=True
                            )
                        )
                except Exception as e:
                    logger.error(f"Failed to send WOL after power restore: {e}")
            
            elif new_status == UpsStatus.LOW_BATTERY:
                # 低电量
                runtime_info = ""
                if data.battery_runtime:
                    runtime_min = data.battery_runtime / 60
                    runtime_info = f"，预计续航 {runtime_min:.0f} 分钟"
                
                await history_service.add_event(
                    EventType.LOW_BATTERY,
                    f"UPS 电池电量过低：{data.battery_charge}%{runtime_info}",
                    metadata={**ups_metadata, "trigger": "status_change"}
                )
                await notifier_service.notify(
                    EventType.LOW_BATTERY,
                    "UPS 电池电量过低",
                    f"当前电量：{data.battery_charge}%{runtime_info}",
                    metadata=self._build_notification_metadata(data, f"电池电量低于阈值 ({data.battery_charge}%)")
                )
        except Exception as e:
            logger.error(f"Error in _on_status_changed: {e}", exc_info=True)
    
    async def _handle_status(self, data: UpsData):
        """根据状态执行相应操作"""
        if data.status == UpsStatus.ONLINE:
            # 在线状态，如果之前有关机计划，取消它
            self.shutdown_manager.on_power_restored()
        
        elif data.status in [UpsStatus.ON_BATTERY, UpsStatus.LOW_BATTERY]:
            # 电池供电状态
            self.shutdown_manager.on_power_lost(data)
            
            # 检查电池电量和续航
            if data.battery_charge is not None:
                if self.shutdown_manager.check_battery_level(data.battery_charge):
                    logger.critical(f"Battery critically low: {data.battery_charge}%")
            
            if data.battery_runtime is not None:
                if self.shutdown_manager.check_runtime_threshold(data.battery_runtime):
                    logger.critical(f"Battery runtime critically low: {data.battery_runtime / 60:.1f} min")
    
    async def _sample_metrics(self, data: UpsData):
        """采样指标数据"""
        try:
            history_service = await get_history_service()
            
            # 计算实时功率 (W)
            power_watts = None
            if data.output_current and data.output_voltage:
                power_watts = data.output_voltage * data.output_current
            elif data.load_percent is not None:
                if data.ups_realpower_nominal:
                    power_watts = data.ups_realpower_nominal * data.load_percent / 100
                elif data.ups_power_nominal:
                    power_watts = data.ups_power_nominal * 0.6 * data.load_percent / 100

            metric = Metric(
                battery_charge=data.battery_charge,
                battery_runtime=data.battery_runtime,
                input_voltage=data.input_voltage,
                output_voltage=data.output_voltage,
                load_percent=data.load_percent,
                temperature=data.temperature,
                # Phase 1 扩展采样
                input_frequency=data.input_frequency,
                output_current=data.output_current,
                ups_efficiency=data.ups_efficiency,
                # Phase 2 扩展采样
                ambient_temperature=data.ambient_temperature,
                ambient_humidity=data.ambient_humidity,
                # 功率
                power_watts=power_watts
            )
            
            await history_service.add_metric(metric)
            logger.debug(f"Metric sample recorded: charge={data.battery_charge}%, runtime={data.battery_runtime}s")
        except Exception as e:
            logger.error(f"Failed to record metric sample: {e}", exc_info=True)
    
    def _bridge_active(self) -> bool:
        """原生驱动事件桥接是否启用（环境变量开启且配置为事件驱动/混合模式）"""
        return bool(
            os.environ.get('NUT_EVENT_BRIDGE') == 'true'
            and self.config
            and self.config.event_driven_enabled
            and self.config.monitoring_mode in ('event_driven', 'hybrid')
        )

    def ingest_driver_frame(self, variables: dict, healthy: bool, reason: str) -> bool:
        """接收桥接推送的驱动帧，返回事件模式是否处于激活状态"""
        self._driver_bridge_data = dict(variables) if healthy else {}
        if reason == 'STATUS' and healthy:
            self._driver_bridge_statuses.append((time.monotonic(), dict(variables)))
        elif not healthy:
            self._driver_bridge_statuses.clear()
        self._driver_bridge_seen = time.monotonic()
        self._driver_bridge_frames += 1
        if reason != 'HEARTBEAT':
            self._driver_bridge_seq += 1
        self._event_mode_active = bool(
            self._bridge_active() and healthy and variables.get('ups.status'))
        if reason != 'HEARTBEAT' or not healthy:
            self._driver_bridge_wakeup.set()
        return self._event_mode_active

    def driver_bridge_age_seconds(self) -> Optional[float]:
        """距最近一帧桥接数据的秒数；从未收到时返回 None"""
        if not self._driver_bridge_seen:
            return None
        return time.monotonic() - self._driver_bridge_seen

    async def _try_start_event_driven_mode(self):
        """尝试启动事件驱动模式"""
        if not self.config or not self.config.event_driven_enabled:
            return
        
        if self.config.monitoring_mode not in ("event_driven", "hybrid"):
            return
            
        if self._bridge_active():
            logger.info('Using native NUT driver event bridge; no LISTEN or network polling')
            return

        try:
            # 动态导入避免循环依赖
            from services.nut_client import EventDrivenNutClient
            
            self._event_driven_client = EventDrivenNutClient(
                host=self.nut_client.host,
                port=self.nut_client.port,
                username=self.nut_client.username,
                password=self.nut_client.password,
                ups_name=self.nut_client.ups_name
            )
            
            success = await self._event_driven_client.start_listen(
                self.nut_client.ups_name,
                self._on_event_data_changed
            )
            
            if success:
                self._event_mode_active = True
                logger.info("Event-driven monitoring mode activated")
            else:
                logger.info("Event-driven mode not available, falling back to polling")
                self._event_mode_active = False
                
        except Exception as e:
            logger.warning(f"Failed to start event-driven mode: {e}")
            self._event_mode_active = False
    
    async def _on_event_data_changed(self):
        """事件驱动模式下的数据变化回调"""
        try:
            ups_data = await self._read_ups_data()
            if ups_data:
                await self._process_ups_data(ups_data)
                self._last_update_time = datetime.now()
                self._communication_count_today += 1
        except Exception as e:
            logger.error(f"Error handling event data change: {e}")
    
    async def _process_ups_data(self, data: UpsData):
        """处理 UPS 数据（从 _monitor_loop 提取出来的通用处理逻辑）"""
        # 更新当前数据
        old_status = self._current_status
        self._current_data = data
        self._current_status = data.status
        
        # 如果之前是断开状态，现在恢复了，发送通知
        if self._connection_notified:
            await self._handle_connection_restored()
            self._connection_notified = False
        
        # 检测状态变化
        if old_status != self._current_status:
            await self._on_status_changed(old_status, self._current_status, data)
        
        # 根据状态执行相应操作
        await self._handle_status(data)
        
        # 定期采样指标（根据 UPS 状态动态调整间隔）
        now = datetime.now()
        dynamic_interval = self._get_dynamic_sample_interval()
        if (now - self._last_sample_time).total_seconds() >= dynamic_interval:
            await self._sample_metrics(data)
            self._last_sample_time = now
        
        # 触发回调
        for callback in self._status_callbacks:
            try:
                await callback(data)
            except Exception as e:
                logger.error(f"Error in status callback: {e}")
    
    async def _persist_daily_stats(self):
        """持久化每日统计到数据库"""
        try:
            from services.history import get_history_service
            
            today = datetime.now().date()
            
            # 计算统计数据
            avg_response_time = sum(self._response_times) / len(self._response_times) if self._response_times else None
            min_response_time = min(self._response_times) if self._response_times else None
            max_response_time = max(self._response_times) if self._response_times else None
            
            # 获取当前监控模式
            monitoring_mode = "polling"
            if self.config:
                monitoring_mode = self.config.monitoring_mode
            
            event_mode_active = self._event_mode_active
            uptime = int((datetime.now() - self._start_time).total_seconds())
            
            history_service = await get_history_service()
            
            # 插入或更新今日统计
            await history_service.upsert_monitoring_stats(
                date=today.isoformat(),
                monitoring_mode=monitoring_mode,
                event_mode_active=event_mode_active,
                communication_count=self._communication_count_today,
                avg_response_time_ms=avg_response_time,
                min_response_time_ms=min_response_time,
                max_response_time_ms=max_response_time,
                uptime_seconds=uptime
            )
            
            logger.debug(f"Persisted daily stats: {self._communication_count_today} comms, avg {avg_response_time:.2f}ms" if avg_response_time else f"Persisted daily stats: {self._communication_count_today} comms")
            
        except Exception as e:
            logger.error(f"Failed to persist daily stats: {e}", exc_info=True)

    async def _check_and_reset_daily_stats(self):
        """检查并重置每日统计"""
        today = datetime.now().date()
        
        if today != self._stats_date:
            # 新的一天，持久化昨天的数据并重置
            await self._persist_daily_stats()
            
            # 重置统计
            self._communication_count_today = 0
            self._response_times = []
            self._stats_date = today
            self._start_time = datetime.now()  # 重置启动时间
            logger.info(f"Reset daily stats for new day: {today}")
    
    async def _stop_event_driven_mode(self):
        """停止事件驱动模式"""
        if self._event_driven_client:
            await self._event_driven_client.stop_listen()
            self._event_driven_client = None
            self._event_mode_active = False
    
    def get_current_data(self) -> Optional[UpsData]:
        """获取当前 UPS 数据"""
        return self._current_data
    
    def get_current_status(self) -> UpsStatus:
        """获取当前状态"""
        return self._current_status


# 全局监控器实例
monitor: Optional[UpsMonitor] = None


def get_monitor() -> Optional[UpsMonitor]:
    """获取监控器实例"""
    return monitor


def set_monitor(m: UpsMonitor):
    """设置监控器实例"""
    global monitor
    monitor = m
