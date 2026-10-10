"""系统信息 API"""
import os
import sys
import re
import json
import platform
import asyncio
import logging
import subprocess
import zipfile
import tempfile
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from io import BytesIO
from enum import Enum
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from services.history import get_history_service
from services.monitor import get_monitor
from db.database import get_db
from config import settings, get_config_manager, APP_VERSION

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/bootstrap")
async def bootstrap_token(request: Request):
    """
    前端启动引导接口（免认证）。

    安全策略：
    - 仅返回 Token 供同域前端使用
    - 通过 Referer / Origin 检查限制跨域调用
    """
    # 可选：检查 Referer 来源（防止跨域滥用）
    referer = request.headers.get("referer", "")
    origin = request.headers.get("origin", "")
    host = request.headers.get("host", "")

    # 如果有 origin 且不匹配当前 host，拒绝请求
    if origin:
        # origin 格式如 "http://192.168.1.100:8000"，需要提取 host 部分
        origin_host = origin.replace("http://", "").replace("https://", "").split("/")[0]
        if host and origin_host != host:
            logger.warning(f"Bootstrap rejected: origin={origin}, host={host}")
            raise HTTPException(status_code=403, detail="Forbidden")

    token = settings.get_or_generate_api_token()
    return {"token": token}


def is_running_in_docker() -> bool:
    """
    检测当前进程是否在 Docker 容器内运行
    """
    # 方法1: 检查 /.dockerenv 文件
    if os.path.exists('/.dockerenv'):
        return True

    # 方法2: 检查 /proc/1/cgroup 是否包含 docker
    try:
        with open('/proc/1/cgroup', 'r') as f:
            content = f.read()
            if 'docker' in content or 'containerd' in content:
                return True
    except (FileNotFoundError, PermissionError):
        pass

    # 方法3: 检查环境变量（某些容器编排工具会设置）
    if os.environ.get('DOCKER_CONTAINER') or os.environ.get('container'):
        return True

    return False


# 缓存检测结果（启动时检测一次即可）
_IS_RUNNING_IN_DOCKER = is_running_in_docker()


# 用于防止重复记录诊断事件的状态追踪
_last_diagnostic_statuses = {
    "backend": None,
    "nut_server": None,
    "ups_driver": None
}
_last_diagnostic_time = {}
_DIAGNOSTIC_COOLDOWN = timedelta(minutes=5)  # 同一状态至少间隔5分钟才记录

# 事件类型映射
_EVENT_TYPE_MAP = {
    ("backend", "error"): "BACKEND_ERROR",
    ("backend", "ok"): "BACKEND_RESTORED",
    ("nut_server", "error"): "NUT_SERVER_DISCONNECTED",
    ("nut_server", "ok"): "NUT_SERVER_CONNECTED",
    ("ups_driver", "error"): "UPS_DRIVER_ERROR",
    ("ups_driver", "warning"): "UPS_DRIVER_DUMMY",
    ("ups_driver", "ok"): "UPS_DRIVER_CONNECTED",
}

# 事件消息映射
_EVENT_MESSAGE_MAP = {
    "BACKEND_ERROR": "后端服务异常",
    "BACKEND_RESTORED": "后端服务已恢复",
    "NUT_SERVER_DISCONNECTED": "NUT 服务器连接断开",
    "NUT_SERVER_CONNECTED": "NUT 服务器已连接",
    "UPS_DRIVER_ERROR": "UPS 驱动无法获取数据",
    "UPS_DRIVER_DUMMY": "UPS 驱动处于 dummy 模式（无真实设备）",
    "UPS_DRIVER_CONNECTED": "UPS 驱动已连接",
}


async def _record_diagnostic_event(
    overall_status: str,
    details: dict,
    db,
    nut_container_logs: list[str] = None
):
    """
    记录诊断事件到数据库（带防重复机制）
    细化到后端服务、NUT服务器、UPS驱动三个层级
    同时发送通知以便及时发现异常
    
    Args:
        overall_status: 整体状态
        details: 详细状态信息
        db: 数据库连接
        nut_container_logs: NUT 容器日志（持久化保存）
    """
    global _last_diagnostic_statuses, _last_diagnostic_time

    now = datetime.now()
    events_to_record = []

    # 检查每个组件的状态变化
    components = ["backend", "nut_server", "ups_driver"]

    for component in components:
        current_status = details.get(component, {}).get("status", "unknown")
        current_message = details.get(component, {}).get("message", "")
        last_status = _last_diagnostic_statuses.get(component)
        last_time = _last_diagnostic_time.get(component)

        should_record = False

        # 判断是否需要记录
        if current_status in ("error", "warning"):
            if last_status is None:
                # 首次检测到异常
                should_record = True
            elif last_status == "ok":
                # 从正常变成异常
                should_record = True
            elif last_status != current_status:
                # 异常类型变化（如 warning -> error）
                should_record = True
            elif last_time and (now - last_time) > _DIAGNOSTIC_COOLDOWN:
                # 超过冷却时间，再次记录
                should_record = True
        elif current_status == "ok" and last_status and last_status != "ok":
            # 从异常恢复正常
            should_record = True

        if should_record:
            # 确定事件类型
            event_type = _EVENT_TYPE_MAP.get((component, current_status))
            if not event_type:
                continue

            # 构建消息
            default_message = _EVENT_MESSAGE_MAP.get(event_type, "状态变化")
            message = current_message if current_message else default_message

            events_to_record.append({
                "component": component,
                "event_type": event_type,
                "message": message,
                "status": current_status
            })

            # 更新状态追踪
            _last_diagnostic_statuses[component] = current_status
            _last_diagnostic_time[component] = now

    # 批量记录事件并发送通知
    for event in events_to_record:
        try:
            # 构建元数据，包含详细的诊断信息和 NUT 容器日志
            metadata_dict = {
                "component": event["component"],
                "status": event["status"],
                "backend_status": details.get("backend", {}).get("status"),
                "nut_server_status": details.get("nut_server", {}).get("status"),
                "ups_driver_status": details.get("ups_driver", {}).get("status"),
                "overall_status": overall_status,
                "timestamp": now.isoformat(),
            }
            
            # 添加各组件的详细信息
            if details.get("backend", {}).get("message"):
                metadata_dict["backend_message"] = details["backend"]["message"]
            if details.get("nut_server", {}).get("message"):
                metadata_dict["nut_server_message"] = details["nut_server"]["message"]
            if details.get("ups_driver", {}).get("message"):
                metadata_dict["ups_driver_message"] = details["ups_driver"]["message"]

            # 如果是 NUT 相关事件，保存容器日志（完整日志用于故障排查）
            if event["component"] in ("nut_server", "ups_driver") and nut_container_logs:
                metadata_dict["nut_container_logs"] = nut_container_logs
                metadata_dict["nut_container_logs_count"] = len(nut_container_logs)

            metadata = json.dumps(metadata_dict, ensure_ascii=False)

            # 记录到数据库
            await db.execute(
                "INSERT INTO events (event_type, message, metadata, test_mode) VALUES (?, ?, ?, ?)",
                (event["event_type"], event["message"], metadata, "production")
            )
            logger.info(f"Recorded diagnostic event: {event['event_type']} - {event['message']}")
            
            # 对于异常事件，发送通知
            if event["status"] in ("error", "warning"):
                try:
                    from services.notifier import get_notifier_service
                    from models import EventType
                    
                    notifier_service = get_notifier_service()
                    event_type_enum = EventType[event["event_type"]]
                    
                    # 构建通知内容
                    notification_title = _EVENT_MESSAGE_MAP.get(event["event_type"], "系统诊断")
                    notification_content = event["message"]
                    
                    # 添加详细的诊断信息
                    diag_lines = []
                    diag_lines.append(f"组件: {event['component']}")
                    diag_lines.append(f"状态: {event['status']}")
                    diag_lines.append(f"检测时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
                    
                    # 添加相关组件状态
                    if metadata_dict.get("backend_status"):
                        diag_lines.append(f"后端服务: {metadata_dict['backend_status']}")
                    if metadata_dict.get("nut_server_status"):
                        diag_lines.append(f"NUT服务器: {metadata_dict['nut_server_status']}")
                    if metadata_dict.get("ups_driver_status"):
                        diag_lines.append(f"UPS驱动: {metadata_dict['ups_driver_status']}")
                    
                    # 如果有容器日志，添加最后几行
                    if nut_container_logs and len(nut_container_logs) > 0:
                        diag_lines.append(f"\n最近日志 (共{len(nut_container_logs)}行):")
                        # 只显示最后5行避免通知过长
                        for log_line in nut_container_logs[-5:]:
                            diag_lines.append(f"  {log_line}")
                    
                    notification_content += "\n\n📋 诊断信息:\n" + "\n".join(diag_lines)
                    
                    # 发送通知（带元数据用于记录完整信息）
                    await notifier_service.notify(
                        event_type_enum,
                        notification_title,
                        notification_content,
                        metadata=metadata_dict
                    )
                    logger.info(f"Sent notification for diagnostic event: {event['event_type']}")
                except Exception as notify_error:
                    logger.error(f"Failed to send notification for diagnostic event: {notify_error}")
            
        except Exception as e:
            logger.error(f"Failed to record diagnostic event: {e}", exc_info=True)

    if events_to_record:
        try:
            await db.commit()
        except Exception as e:
            logger.error(f"Failed to commit diagnostic events: {e}")



async def get_docker_logs(container_name: str, tail: int = 30) -> list[str]:
    """
    异步获取 Docker 容器日志
    支持 Windows 和 Linux

    当后端运行在 Docker 容器内时，无法调用宿主机的 docker 命令，
    此时通过 NUT 协议获取实时状态信息作为诊断日志。
    """
    # 如果在 Docker 容器内运行，通过 NUT 协议获取状态信息
    if _IS_RUNNING_IN_DOCKER:
        return await _get_nut_status_as_logs()

    # Windows 上使用同步方式（更稳定）
    if sys.platform == 'win32':
        return await _get_docker_logs_sync(container_name, tail)
    else:
        return await _get_docker_logs_async(container_name, tail)


async def _get_nut_status_as_logs() -> list[str]:
    """
    通过 NUT 协议获取实时状态信息，格式化为日志输出
    用于 Docker 环境中替代 docker logs 命令
    """
    logs = []
    timestamp = datetime.now().strftime('%H:%M:%S')

    try:
        # 获取 monitor 实例
        monitor = get_monitor()
        if not monitor:
            logs.append(f"[{timestamp}] ⚠️ 监控服务未初始化")
            return logs

        # 获取 NUT 客户端
        nut_client = getattr(monitor, 'nut_client', None)
        if not nut_client:
            logs.append(f"[{timestamp}] ⚠️ NUT 客户端未初始化")
            return logs

        logs.append(f"[{timestamp}] === NUT 服务实时状态 ===")

        # 检查连接状态
        if hasattr(nut_client, 'is_connected') and callable(nut_client.is_connected):
            if nut_client.is_connected():
                logs.append(f"[{timestamp}] ✅ NUT 服务器连接: 正常")
            else:
                logs.append(f"[{timestamp}] ❌ NUT 服务器连接: 断开")

        # 获取 UPS 名称
        ups_name = getattr(nut_client, 'ups_name', None)
        if ups_name:
            logs.append(f"[{timestamp}] 📍 UPS 名称: {ups_name}")

        # 获取连接详细状态
        if hasattr(nut_client, 'get_connection_status') and callable(nut_client.get_connection_status):
            conn_status = nut_client.get_connection_status()
            if isinstance(conn_status, dict):
                if conn_status.get('last_error'):
                    logs.append(f"[{timestamp}] ❌ 最后错误: {conn_status['last_error']}")
                if conn_status.get('reconnect_attempts', 0) > 0:
                    logs.append(f"[{timestamp}] 🔄 重连尝试: {conn_status['reconnect_attempts']} 次")

        # 获取 UPS 数据
        ups_data = monitor.get_current_data()
        if ups_data:
            logs.append(f"[{timestamp}] --- UPS 详细信息 ---")

            # 状态
            if ups_data.status:
                status_str = ups_data.status.value if hasattr(ups_data.status, 'value') else str(ups_data.status)
                status_emoji = "🟢" if status_str in ["ONLINE", "OL"] else "🟡" if "CHRG" in status_str else "🔴"
                logs.append(f"[{timestamp}] {status_emoji} 状态: {status_str}")

            # 型号和制造商
            if ups_data.ups_model:
                logs.append(f"[{timestamp}] 📦 型号: {ups_data.ups_model}")
            if ups_data.ups_manufacturer:
                logs.append(f"[{timestamp}] 🏭 制造商: {ups_data.ups_manufacturer}")

            # 电池信息
            if ups_data.battery_charge is not None:
                charge_emoji = "🔋" if ups_data.battery_charge > 50 else "🪫" if ups_data.battery_charge > 20 else "⚠️"
                logs.append(f"[{timestamp}] {charge_emoji} 电池电量: {ups_data.battery_charge}%")
            if ups_data.battery_runtime is not None:
                runtime_min = ups_data.battery_runtime // 60
                logs.append(f"[{timestamp}] ⏱️ 预计续航: {runtime_min} 分钟")

            # 电压信息
            if ups_data.input_voltage is not None:
                logs.append(f"[{timestamp}] ⚡ 输入电压: {ups_data.input_voltage}V")
            if ups_data.output_voltage is not None:
                logs.append(f"[{timestamp}] 🔌 输出电压: {ups_data.output_voltage}V")

            # 负载
            if ups_data.load_percent is not None:
                logs.append(f"[{timestamp}] 📊 负载: {ups_data.load_percent}%")

            # 最后更新时间
            if ups_data.last_update:
                logs.append(f"[{timestamp}] 🕐 数据更新: {ups_data.last_update.strftime('%H:%M:%S')}")
        else:
            logs.append(f"[{timestamp}] ⚠️ 暂无 UPS 数据")

        logs.append(f"[{timestamp}] === 状态获取完成 ===")

    except Exception as e:
        logs.append(f"[{timestamp}] ❌ 获取状态失败: {str(e)}")
        logger.error(f"Failed to get NUT status as logs: {e}", exc_info=True)

    return logs


async def _get_docker_logs_sync(container_name: str, tail: int) -> list[str]:
    """
    同步获取 Docker 日志（Windows 兼容）
    """
    try:
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: subprocess.run(
                ['docker', 'logs', container_name, '--tail', str(tail)],
                capture_output=True,
                timeout=5
            )
        )

        if result.returncode != 0:
            error_msg = result.stderr.decode('utf-8', errors='ignore').strip() if result.stderr else '未知错误'
            logger.warning(f"Docker logs command failed: {error_msg}")
            return [f"[获取日志失败: {error_msg}]"]

        if result.stdout:
            lines = result.stdout.decode('utf-8', errors='ignore').strip().split('\n')
            return lines
        return ["[容器日志为空]"]
    except subprocess.TimeoutExpired:
        logger.warning("Docker logs command timed out")
        return ["[获取日志超时]"]
    except FileNotFoundError:
        logger.warning("Docker command not found")
        return ["[Docker 命令不可用 - 请确保 Docker 已安装并在 PATH 中]"]
    except OSError as e:
        logger.warning(f"OS error getting docker logs: {e}")
        return [f"[系统错误: {e.strerror or str(e)}]"]
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e) or '无详细信息'
        logger.warning(f"Failed to get docker logs: {error_type}: {error_msg}")
        return [f"[获取日志失败: {error_type} - {error_msg}]"]


async def _get_docker_logs_async(container_name: str, tail: int) -> list[str]:
    """
    异步获取 Docker 日志（Linux/Mac）
    """
    try:
        process = await asyncio.create_subprocess_exec(
            'docker', 'logs', container_name, '--tail', str(tail),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=5.0)

        if process.returncode != 0:
            error_msg = stderr.decode('utf-8', errors='ignore').strip() if stderr else '未知错误'
            logger.warning(f"Docker logs command failed: {error_msg}")
            return [f"[获取日志失败: {error_msg}]"]

        if stdout:
            lines = stdout.decode('utf-8', errors='ignore').strip().split('\n')
            return lines
        return ["[容器日志为空]"]
    except asyncio.TimeoutError:
        logger.warning("Docker logs command timed out")
        return ["[获取日志超时]"]
    except FileNotFoundError:
        logger.warning("Docker command not found")
        return ["[Docker 命令不可用 - 请确保 Docker 已安装并在 PATH 中]"]
    except OSError as e:
        logger.warning(f"OS error getting docker logs: {e}")
        return [f"[系统错误: {e.strerror or str(e)}]"]
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e) or '无详细信息'
        logger.warning(f"Failed to get docker logs: {error_type}: {error_msg}")
        return [f"[获取日志失败: {error_type} - {error_msg}]"]


@router.get("/system/connection-status")
async def get_connection_status():
    """
    获取连接状态诊断信息（轻量级）

    用于前端快速检测后端-NUT-驱动的连接状态，
    当出现故障时显示诊断面板。

    包含：
    - 后端服务状态
    - NUT 服务器连接状态
    - UPS 驱动状态
    - NUT 容器最近日志（自动检测重连、设备发现等）
    """
    result = {
        "timestamp": datetime.now().isoformat(),
        "backend": {
            "status": "ok",
            "message": "后端服务运行正常"
        },
        "nut_server": {
            "status": "unknown",
            "message": "未知"
        },
        "ups_driver": {
            "status": "unknown",
            "message": "未知"
        },
        "overall_status": "unknown",
        "logs": [],
        "nut_container_logs": []
    }

    logs = []
    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 后端服务运行正常")

    # 初始化 ups_name 变量
    ups_name = None

    try:
        # 检查 NUT 服务器连接
        monitor = get_monitor()
        if monitor and monitor.nut_client:
            nut_client = monitor.nut_client

            # 检查连接状态
            if hasattr(nut_client, 'is_connected') and callable(nut_client.is_connected):
                if nut_client.is_connected():
                    result["nut_server"]["status"] = "ok"
                    result["nut_server"]["message"] = f"已连接到 NUT 服务器 ({settings.nut_host}:{settings.nut_port})"
                    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] NUT 服务器连接正常")
                else:
                    result["nut_server"]["status"] = "error"
                    result["nut_server"]["message"] = "NUT 服务器连接已断开"
                    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ NUT 服务器连接断开")

            # 获取连接详细状态
            if hasattr(nut_client, 'get_connection_status') and callable(nut_client.get_connection_status):
                conn_status = nut_client.get_connection_status()
                if conn_status.get('last_error'):
                    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ 连接错误: {conn_status['last_error']}")
                if conn_status.get('reconnect_attempts', 0) > 0:
                    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🔄 重连尝试次数: {conn_status['reconnect_attempts']}")

            # 获取 UPS 名称
            ups_name = getattr(nut_client, 'ups_name', None)
            if ups_name:
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 当前 UPS 名称: {ups_name}")
        else:
            result["nut_server"]["status"] = "error"
            result["nut_server"]["message"] = "监控服务未初始化"
            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ 监控服务未初始化")

        # 检查 UPS 数据
        if monitor:
            ups_data = monitor.get_current_data()
            if ups_data:
                # 检查是否是 OFFLINE 状态（dummy 等待模式）
                from models import UpsStatus
                is_offline = ups_data.status == UpsStatus.OFFLINE

                # 检查是否是设备断开等待模式
                ups_model = ups_data.ups_model or ''
                ups_mfr = ups_data.ups_manufacturer or ''

                # 更全面的断开检测 - 直接检查字符串内容
                is_device_disconnected = False
                is_dummy_mode = False

                model_lower = ups_model.lower() if ups_model else ''
                mfr_lower = ups_mfr.lower() if ups_mfr else ''

                # 检查型号名称中是否包含断开标志
                if 'disconnected' in model_lower:
                    is_device_disconnected = True
                    logger.info(f"Device disconnected detected via model: '{ups_model}'")

                # 检查制造商名称中是否包含等待标志（等待模式专用）
                if 'waiting' in mfr_lower:
                    is_device_disconnected = True
                    logger.info(f"Device disconnected detected via mfr: '{ups_mfr}'")

                # 检查是否是初始 Dummy 开发模式（没有真实设备连接）
                if 'dummy' in model_lower or (ups_name and ups_name.lower() == 'dummy'):
                    is_dummy_mode = True
                    logger.info(f"Dummy mode detected: model='{ups_model}', ups_name='{ups_name}'")

                # 添加调试日志（INFO 级别以便能看到）
                logger.info(f"UPS status check: model='{ups_model}', mfr='{ups_mfr}', ups_name='{ups_name}', status={ups_data.status}, is_offline={is_offline}, is_disconnected={is_device_disconnected}, is_dummy={is_dummy_mode}")

                if is_offline or is_device_disconnected:
                    result["ups_driver"]["status"] = "error"
                    result["ups_driver"]["message"] = "UPS 设备已断开，等待重新连接..."
                    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ UPS 设备已断开（型号: {ups_model}, 状态: {ups_data.status.value if ups_data.status else 'OFFLINE'}）")
                    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 💡 请检查 USB 连接或等待设备自动恢复")
                elif is_dummy_mode:
                    # Dummy 模式：保持 warning 状态，不要覆盖
                    result["ups_driver"]["status"] = "warning"
                    result["ups_driver"]["message"] = "UPS 驱动处于 dummy 模式（无真实 UPS 设备）"
                    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ UPS 处于 dummy 模式，等待真实设备连接")
                else:
                    result["ups_driver"]["status"] = "ok"
                    result["ups_driver"]["message"] = f"UPS 驱动正常 ({ups_model or '未知型号'})"
                    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] UPS 驱动正常，状态: {ups_data.status.value if ups_data.status else '未知'}")

                # 添加一些关键状态
                if ups_data.battery_charge is not None:
                    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 电池电量: {ups_data.battery_charge}%")
                if ups_data.input_voltage is not None:
                    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 输入电压: {ups_data.input_voltage}V")
            else:
                # 没有 UPS 数据
                if result["ups_driver"]["status"] != "warning":
                    result["ups_driver"]["status"] = "error"
                    result["ups_driver"]["message"] = "无法获取 UPS 数据"
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ 无法获取 UPS 数据")

        # 计算总体状态
        statuses = [
            result["backend"]["status"],
            result["nut_server"]["status"],
            result["ups_driver"]["status"]
        ]

        if all(s == "ok" for s in statuses):
            result["overall_status"] = "ok"
        elif any(s == "error" for s in statuses):
            result["overall_status"] = "error"
        elif any(s == "warning" for s in statuses):
            result["overall_status"] = "warning"
        else:
            result["overall_status"] = "unknown"

        # 获取 NUT 容器日志（如果状态不是 ok，或者是 dummy 模式）
        if result["overall_status"] != "ok" or result["ups_driver"]["status"] == "warning":
            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 正在获取 NUT 容器日志...")
            container_logs = await get_docker_logs("ups-guard-nut", tail=30)
            result["nut_container_logs"] = container_logs

            # 分析容器日志，提取关键信息
            for log_line in container_logs:
                if "✅ 发现 UPS 设备" in log_line:
                    logs.append(f"[NUT] {log_line}")
                elif "❌ 未发现 UPS 设备" in log_line:
                    logs.append(f"[NUT] {log_line}")
                elif "UPS 驱动重启成功" in log_line:
                    logs.append(f"[NUT] {log_line}")
                elif "dummy" in log_line.lower() and "driver" in log_line.lower():
                    logs.append(f"[NUT] {log_line}")
                elif "⚠️" in log_line or "🔄" in log_line or "🔍" in log_line:
                    logs.append(f"[NUT] {log_line}")

        result["logs"] = logs

        # 记录诊断事件到数据库（异步，不阻塞返回）
        try:
            db = await get_db()
            # 传入 NUT 容器日志以便持久化保存
            nut_logs = result.get("nut_container_logs", [])
            await _record_diagnostic_event(result["overall_status"], result, db, nut_logs)
        except Exception as e:
            logger.warning(f"Failed to record diagnostic event: {e}")

        return result

    except Exception as e:
        logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ 诊断异常: {str(e)}")
        result["overall_status"] = "error"
        result["logs"] = logs

        # 记录异常诊断事件（尝试获取容器日志）
        try:
            db = await get_db()
            # 尝试获取 NUT 容器日志
            try:
                container_logs = await get_docker_logs("ups-guard-nut", tail=30)
            except Exception:
                container_logs = []
            await _record_diagnostic_event(result["overall_status"], result, db, container_logs)
        except Exception as record_error:
            logger.warning(f"Failed to record diagnostic event: {record_error}")

        return result


class DiagnosticsJSONEncoder(json.JSONEncoder):
    """自定义 JSON 编码器，处理各种非标准类型"""
    
    def default(self, obj):
        # 处理 datetime 对象
        if isinstance(obj, datetime):
            return obj.isoformat()
        # 处理 Decimal 对象
        if isinstance(obj, Decimal):
            return float(obj)
        # 处理 Enum 对象
        if isinstance(obj, Enum):
            return obj.value
        # 处理 bytes 对象
        if isinstance(obj, bytes):
            return obj.decode('utf-8', errors='ignore')
        # 对于其他不可序列化的对象，返回字符串表示
        try:
            return super().default(obj)
        except TypeError:
            return str(obj)


@router.get("/system/storage")
async def get_storage_info():
    """获取存储信息"""
    try:
        history_service = await get_history_service()
        db_path = settings.database_path
        
        # 获取数据库文件大小
        db_size = 0
        if os.path.exists(db_path):
            db_size = os.path.getsize(db_path)
        
        # 获取事件和指标统计（直接从数据库查询）
        db = await get_db()
        
        # 统计事件数量
        row = await db.fetch_one("SELECT COUNT(*) FROM events")
        event_count = row[0] if row else 0
        
        # 获取最早事件时间
        row = await db.fetch_one("SELECT timestamp FROM events ORDER BY timestamp ASC LIMIT 1")
        earliest_event_time = row[0] if row else None
        
        # 统计指标数量
        row = await db.fetch_one("SELECT COUNT(*) FROM metrics")
        metric_count = row[0] if row else 0
        
        # 获取最早指标时间
        row = await db.fetch_one("SELECT timestamp FROM metrics ORDER BY timestamp ASC LIMIT 1")
        earliest_metric_time = row[0] if row else None
        
        # 确定最早记录时间
        earliest_time = None
        if earliest_event_time and earliest_metric_time:
            earliest_time = min(earliest_event_time, earliest_metric_time)
        elif earliest_event_time:
            earliest_time = earliest_event_time
        elif earliest_metric_time:
            earliest_time = earliest_metric_time
        
        return {
            "db_size_bytes": db_size,
            "db_size_mb": round(db_size / 1024 / 1024, 2),
            "event_count": event_count,
            "metric_count": metric_count,
            "earliest_record_time": earliest_time
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取存储信息失败: {str(e)}")


def mask_sensitive_data(obj, parent_key=''):
    """
    递归遮蔽敏感信息
    
    敏感字段列表：password, token, secret, key, api_key, api_secret, 
                 private_key, smtp_password, webhook_token, nut_password
    """
    sensitive_keywords = {
        'password', 'token', 'secret', 'key', 'api_key',
        'api_secret', 'private_key', 'smtp_password',
        'webhook_token', 'nut_password'
    }
    
    if isinstance(obj, dict):
        masked = {}
        for k, v in obj.items():
            # 检查键名是否包含敏感词
            is_sensitive = any(keyword in k.lower() for keyword in sensitive_keywords)
            if is_sensitive and v:
                masked[k] = "***"
            else:
                masked[k] = mask_sensitive_data(v, k)
        return masked
    elif isinstance(obj, list):
        return [mask_sensitive_data(item, parent_key) for item in obj]
    else:
        return obj


@router.get("/system/diagnostics")
async def get_diagnostics():
    """
    获取诊断报告（JSON 格式）
    
    包含系统信息、UPS 状态、配置摘要、最近事件、关机管理器状态、
    WebSocket 连接数、数据库信息、设备状态等
    
    注意：所有敏感信息（密码、token、密钥）均已脱敏
    """
    try:
        # 获取系统信息
        uptime_seconds = 0
        try:
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = int(float(f.read().split()[0]))
        except:
            pass
        
        system_info = {
            "version": APP_VERSION,
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "os": platform.platform(),
            "uptime_seconds": uptime_seconds
        }
        
        # 获取 UPS 状态
        monitor = get_monitor()
        ups_status = {}
        ups_raw_variables = {}
        ups_writable_vars = {}
        ups_supported_commands = []
        if monitor:
            ups_data = monitor.get_current_data()
            if ups_data:
                ups_status = {
                    "status": ups_data.status.value,
                    "status_raw": ups_data.status_raw,
                    "status_flags": ups_data.status_flags,
                    "battery_charge": ups_data.battery_charge,
                    "battery_runtime": ups_data.battery_runtime,
                    "input_voltage": ups_data.input_voltage,
                    "output_voltage": ups_data.output_voltage,
                    "load_percent": ups_data.load_percent,
                    "temperature": ups_data.temperature,
                    "model": ups_data.ups_model,
                    "manufacturer": ups_data.ups_manufacturer,
                    "serial": ups_data.ups_serial,
                    "battery_type": ups_data.battery_type,
                    "battery_voltage": ups_data.battery_voltage,
                    "battery_voltage_nominal": ups_data.battery_voltage_nominal,
                    "battery_charge_low": ups_data.battery_charge_low,
                    "battery_runtime_low": ups_data.battery_runtime_low,
                    "battery_charger_status": ups_data.battery_charger_status,
                    "battery_mfr_date": ups_data.battery_mfr_date,
                    "ups_realpower_nominal": ups_data.ups_realpower_nominal,
                    "input_voltage_nominal": ups_data.input_voltage_nominal,
                    "input_sensitivity": ups_data.input_sensitivity,
                    "input_transfer_low": ups_data.input_transfer_low,
                    "input_transfer_high": ups_data.input_transfer_high,
                    "input_transfer_reason": ups_data.input_transfer_reason,
                    "ups_beeper_status": ups_data.ups_beeper_status,
                    "ups_test_result": ups_data.ups_test_result,
                    "ups_delay_shutdown": ups_data.ups_delay_shutdown,
                    "runtime_estimated": ups_data.runtime_estimated,
                    "transfer_count": ups_data.transfer_count,
                    "time_on_battery": ups_data.time_on_battery,
                    "cumulative_on_battery": ups_data.cumulative_on_battery,
                    "ups_alarm_del": ups_data.ups_alarm_del,
                    "ups_backend": ups_data.ups_backend,
                    "ups_starttime": ups_data.ups_starttime,
                    "last_update": ups_data.last_update.isoformat() if ups_data.last_update else None,
                }

            # 获取原始 UPS 变量
            try:
                client = monitor.nut_client
                if hasattr(client, 'list_vars'):
                    ups_raw_variables = await client.list_vars()
            except Exception as e:
                ups_raw_variables = {"error": str(e)}

            # 获取可写变量
            try:
                client = monitor.nut_client
                if hasattr(client, 'list_rw'):
                    ups_writable_vars = await client.list_rw()
            except Exception:
                pass

            # 获取支持的命令
            try:
                client = monitor.nut_client
                if hasattr(client, 'list_commands'):
                    ups_supported_commands = await client.list_commands()
            except Exception:
                pass
        
        # 获取完整配置（脱敏）用于复现用户环境
        config_manager = await get_config_manager()
        config = await config_manager.get_config()
        config_dict = config.dict()
        
        # 添加 test_mode 到 system_info (从 Config 获取，而不是从 Settings)
        system_info["test_mode"] = config_dict.get("test_mode", "production")
        
        # 完整配置（脱敏处理）
        full_config_masked = mask_sensitive_data(config_dict)
        
        config_summary = {
            "shutdown_wait_minutes": config_dict.get("shutdown_wait_minutes"),
            "shutdown_battery_percent": config_dict.get("shutdown_battery_percent"),
            "notification_channels_count": len(config_dict.get("notify_channels", [])),
            "pre_shutdown_hooks_count": len(config_dict.get("pre_shutdown_hooks", [])),
            "test_mode": config_dict.get("test_mode"),
            "shutdown_method": config_dict.get("shutdown_method"),
            "wol_on_power_restore": config_dict.get("wol_on_power_restore")
        }
        
        # 获取最近事件（最近7天，最多取前50条）
        history_service = await get_history_service()
        recent_events_raw = await history_service.get_events(days=7)
        # 限制返回最多50条
        recent_events_raw = recent_events_raw[:50]
        recent_events = []
        for event in recent_events_raw:
            recent_events.append({
                "timestamp": event.timestamp.isoformat(),
                "event_type": event.event_type.value,
                "message": event.message
            })
        
        # 获取关机管理器状态
        shutdown_manager_status = {}
        if monitor and monitor.shutdown_manager:
            shutdown_manager_status = monitor.shutdown_manager.get_status()
        
        # 获取数据库信息
        db_path = settings.database_path
        db_size = 0
        if os.path.exists(db_path):
            db_size = os.path.getsize(db_path)
        
        db = await get_db()
        row = await db.fetch_one("SELECT COUNT(*) FROM events")
        events_count = row[0] if row else 0
        
        row = await db.fetch_one("SELECT COUNT(*) FROM metrics")
        metrics_count = row[0] if row else 0
        
        database_info = {
            "size_bytes": db_size,
            "events_count": events_count,
            "metrics_count": metrics_count
        }
        
        # 获取设备状态（脱敏）
        device_status = []
        if config_dict.get("pre_shutdown_hooks"):
            for hook in config_dict["pre_shutdown_hooks"]:
                device_info = {
                    "name": hook.get("name"),
                    "hook_id": hook.get("hook_id"),
                    "priority": hook.get("priority"),
                    "enabled": hook.get("enabled"),
                    # 配置信息脱敏
                    "config": mask_sensitive_data(hook.get("config", {}))
                }
                device_status.append(device_info)
        
        # WebSocket 连接数（如果可用）
        websocket_connections = 0
        try:
            from api.websocket import manager
            websocket_connections = len(manager.active_connections)
        except:
            pass
        
        # 组装诊断报告
        diagnostics = {
            "generated_at": datetime.now().isoformat(),
            "reproduction_instructions": "要复现此环境，请使用 Settings 页面的「导入配置」功能导入 full_config 字段的内容",
            "system_info": system_info,
            "ups_status": ups_status,
            "ups_raw_variables": ups_raw_variables,
            "ups_writable_variables": ups_writable_vars,
            "ups_supported_commands": ups_supported_commands,
            "backend_config": {
                "ups_backend": settings.ups_backend,
                "nut_host": settings.nut_host if settings.ups_backend == "nut" else None,
                "nut_port": settings.nut_port if settings.ups_backend == "nut" else None,
                "apcupsd_host": settings.apcupsd_host if settings.ups_backend == "apcupsd" else None,
                "apcupsd_port": settings.apcupsd_port if settings.ups_backend == "apcupsd" else None,
                "mock_mode": settings.mock_mode,
            },
            "config_summary": config_summary,
            "full_config": full_config_masked,
            "recent_events": recent_events,
            "shutdown_manager_status": shutdown_manager_status,
            "websocket_connections": websocket_connections,
            "database_info": database_info,
            "device_status": device_status
        }
        
        return diagnostics
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成诊断报告失败: {str(e)}")


def _generate_nut_parameters_report() -> str | None:
    """
    调用 test_nut_parameters.py 生成 NUT 参数测试报告

    注意：此函数包含阻塞 I/O 操作，应通过 asyncio.to_thread() 调用

    Returns:
        报告的 Markdown 文本内容，失败时返回 None
    """
    # 定位脚本路径
    # backend/src/api/system.py -> backend/tools/test_nut_parameters.py
    script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    script_path = os.path.join(script_dir, "tools", "test_nut_parameters.py")

    if not os.path.exists(script_path):
        logger.warning(f"NUT 参数测试脚本不存在: {script_path}")
        return None

    try:
        # 使用临时文件接收 Markdown 格式输出
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode='w') as tmp:
            tmp_path = tmp.name

        try:
            result = subprocess.run(
                [
                    sys.executable,  # 使用当前 Python 解释器
                    script_path,
                    "--test-all",
                    "--output", tmp_path,
                ],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=script_dir,  # 设置工作目录
            )

            if result.returncode == 0 and os.path.exists(tmp_path):
                with open(tmp_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                if content.strip():
                    logger.info("NUT 参数测试报告生成成功")
                    return content

            # 即使脚本失败，也记录 stderr 信息作为报告内容（有诊断价值）
            error_info = result.stderr.strip() if result.stderr else "未知错误"
            logger.warning(f"NUT 参数测试脚本执行异常 (returncode={result.returncode}): {error_info}")

            # 生成一个错误说明文件，也有诊断价值
            return (
                f"# NUT 参数测试报告\n\n"
                f"> ⚠️ 脚本执行未成功，以下是错误信息：\n\n"
                f"**返回码**: {result.returncode}\n\n"
                f"**标准输出**:\n```\n{result.stdout[:2000] if result.stdout else '(无)'}\n```\n\n"
                f"**标准错误**:\n```\n{error_info[:2000]}\n```\n"
            )

        finally:
            # 清理临时文件
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    except subprocess.TimeoutExpired:
        logger.warning("NUT 参数测试脚本执行超时 (30s)")
        return (
            "# NUT 参数测试报告\n\n"
            "> ⚠️ 脚本执行超时（30秒），可能 NUT 服务器无响应。\n"
        )
    except Exception as e:
        logger.error(f"生成 NUT 参数测试报告失败: {e}")
        return None


# ==================== 诊断报告日志收集 ====================

_CST = timezone(timedelta(hours=8))

# 匹配日志中常见的 UTC 时间戳格式
_UTC_TIMESTAMP_PATTERNS = [
    # Docker 时间戳: 2026-03-05T03:08:16.556240350Z
    re.compile(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\.\d+Z'),
    # Python 日志: 2026-03-05 03:08:16,556
    re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d{3}'),
]

_UTC_FORMATS = [
    '%Y-%m-%dT%H:%M:%S',
    '%Y-%m-%d %H:%M:%S',
]


def _convert_logs_to_cst(log_text: str) -> str:
    """
    将日志文本中的 UTC 时间戳批量转换为中国时间 (UTC+8)

    支持格式:
    - Docker: 2026-03-05T03:08:16.556240350Z → 2026-03-05 11:08:16
    - Python: 2026-03-05 03:08:16,556 → 2026-03-05 11:08:16,556
    """
    if not log_text:
        return log_text

    lines = log_text.split('\n')
    converted: list[str] = []

    for line in lines:
        for pattern, fmt in zip(_UTC_TIMESTAMP_PATTERNS, _UTC_FORMATS):
            match = pattern.search(line)
            if match:
                try:
                    utc_str = match.group(1)
                    utc_dt = datetime.strptime(utc_str, fmt).replace(
                        tzinfo=timezone.utc
                    )
                    cst_dt = utc_dt.astimezone(_CST)

                    # Docker 格式去掉纳秒和 Z，Python 格式保留毫秒
                    full_match = match.group(0)
                    if full_match.endswith('Z'):
                        cst_str = cst_dt.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        # 保留原始毫秒部分: ",556"
                        ms_part = full_match[19:]  # ",556"
                        cst_str = cst_dt.strftime('%Y-%m-%d %H:%M:%S') + ms_part

                    line = line[:match.start()] + cst_str + line[match.end():]
                except (ValueError, IndexError):
                    pass  # 解析失败则保留原文
                break  # 每行只处理第一个匹配的时间戳

        converted.append(line)

    return '\n'.join(converted)


async def _collect_container_logs(
    container_names: list[str], tail: int = 1000
) -> str | None:
    """
    从多个候选容器名中获取日志并转换为 CST 时区

    注意：直接使用 docker logs 命令，不经过 get_docker_logs()
    以避免 Docker 环境检测导致获取不到真实容器日志

    Args:
        container_names: 容器名候选列表（按优先级尝试）
        tail: 获取最近多少行

    Returns:
        转换后的日志文本，全部失败返回 None
    """
    for name in container_names:
        try:
            # 直接执行 docker logs，不经过 get_docker_logs 的 Docker 检测
            result = await _exec_command(
                ["docker", "logs", name, "--tail", str(tail), "--timestamps"],
                timeout=15.0,
            )
            # 排除错误提示信息
            if (
                result
                and not result.startswith("(命令不可用")
                and not result.startswith("(执行失败")
                and not result.startswith("(权限不足")
                and not result.startswith("(系统错误")
                and not result.startswith("(命令执行超时")
            ):
                header = (
                    f"# Container: {name}\n"
                    f"# Collected at (CST): "
                    f"{datetime.now(_CST).strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"# Tail: {tail} lines\n"
                    f"# Timezone: UTC+8 (CST)\n\n"
                )
                return header + _convert_logs_to_cst(result)
        except Exception as e:
            logger.debug(f"Failed to get logs from container {name}: {e}")
            continue

    return None


async def _exec_command(cmd: list[str], timeout: float = 10.0) -> str:
    """
    执行外部命令并返回输出文本

    所有异常均被捕获，返回可读的错误描述而不会抛出异常
    """
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=timeout
        )

        output = stdout.decode('utf-8', errors='ignore').strip()
        err_output = stderr.decode('utf-8', errors='ignore').strip()

        if output:
            return output
        if err_output:
            # 区分真正的错误和 stderr 输出的正常内容
            if "not found" in err_output.lower() or "permission" in err_output.lower():
                return f"(权限不足或命令不可用: {err_output})"
            return f"(stderr) {err_output}"
        return "(无输出)"

    except asyncio.TimeoutError:
        return f"(命令执行超时 {timeout:.0f}s)"
    except FileNotFoundError:
        return f"(命令不可用: {cmd[0]})"
    except OSError as e:
        return f"(系统错误: {e})"
    except Exception as e:
        return f"(执行失败: {e})"


async def _collect_usb_diagnostics() -> str | None:
    """
    收集 USB 设备诊断信息（用于排查 UPS USB 连接问题）

    - lsusb / USB 设备树: 在当前容器执行
    - dmesg: 通过 docker exec 在 NUT 容器执行（需要更高权限）
    """
    sections: list[str] = []
    collected_at = datetime.now(_CST).strftime('%Y-%m-%d %H:%M:%S')
    sections.append(
        f"# USB Diagnostics Report\n"
        f"# Collected at (CST): {collected_at}\n"
        f"# Timezone: UTC+8 (CST)\n"
    )

    # ---- 本地命令（后端容器内可执行） ----
    local_commands = [
        ("lsusb (全量 USB 设备)", ["lsusb"]),
        ("lsusb -t (USB 设备树)", ["lsusb", "-t"]),
        (
            "UPS 设备详情 (VID:0665)",
            ["lsusb", "-v", "-d", "0665:"],
        ),
        (
            "/dev/bus/usb 设备树",
            ["sh", "-c",
             "find /dev/bus/usb -type c 2>/dev/null || echo '(不可用)'"],
        ),
        (
            "/dev/hidraw* 设备",
            ["sh", "-c",
             "ls -la /dev/hidraw* 2>/dev/null || echo '(无 hidraw 设备)'"],
        ),
    ]

    for title, cmd in local_commands:
        sections.append(f"\n{'=' * 60}")
        sections.append(f"## {title}")
        sections.append(f"## Command: {' '.join(cmd)}")
        sections.append('=' * 60)
        output = await _exec_command(cmd)
        sections.append(output)

    # ---- 远程命令（通过 docker exec 在 NUT 容器内执行，获取 dmesg） ----
    nut_container_names = ["ups-guard-nut", "nut-server", "nut"]
    remote_commands = [
        (
            "dmesg USB 相关 (最近 50 条)",
            "dmesg | grep -i usb | tail -50",
        ),
        (
            "dmesg USB 错误/断开 (最近 20 条)",
            "dmesg | grep -iE 'usb.*(disconnect|error|reset|fail)' "
            "| tail -20",
        ),
    ]

    for title, cmd_str in remote_commands:
        sections.append(f"\n{'=' * 60}")
        sections.append(f"## {title}")
        sections.append('=' * 60)

        output = None
        for container_name in nut_container_names:
            docker_cmd = [
                "docker", "exec", container_name,
                "sh", "-c", cmd_str,
            ]
            result = await _exec_command(docker_cmd)
            if not result.startswith("(命令不可用") and not result.startswith("(执行失败"):
                output = result
                sections.append(f"## Via: docker exec {container_name}")
                break

        if output is None:
            # 所有 NUT 容器都失败，尝试在本地执行（也可能失败）
            fallback_cmd = ["sh", "-c", cmd_str]
            output = await _exec_command(fallback_cmd)
            sections.append("## Via: local (fallback)")

        sections.append(output)

    # dmesg 时间戳也转换为 CST
    result = '\n'.join(sections)
    return _convert_logs_to_cst(result)


@router.get("/system/diagnostics/download")
async def download_diagnostics():
    """
    下载诊断报告（ZIP 压缩包）

    包含：
    - diagnostics.json: 系统诊断报告
    - nut-parameters-report.md: NUT 参数测试报告（如果 NUT 服务可用）
    - logs/nut-container.log: NUT 容器最近日志（CST 时区）
    - logs/backend-container.log: 后端容器最近日志（CST 时区）
    - logs/usb-diagnostics.log: USB 设备诊断信息
    """
    try:
        # 1. 获取诊断报告 JSON
        diagnostics = await get_diagnostics()
        json_str = json.dumps(
            diagnostics,
            ensure_ascii=False,
            indent=2,
            cls=DiagnosticsJSONEncoder
        )

        # 2. 生成 NUT 参数测试报告（在线程池中执行，避免阻塞事件循环）
        nut_report_content = await asyncio.to_thread(
            _generate_nut_parameters_report
        )

        # 3. 收集容器日志（时间自动转 CST）
        nut_logs = await _collect_container_logs(
            ["ups-guard-nut", "nut-server", "nut"], tail=1000
        )
        backend_logs = await _collect_container_logs(
            ["ups-guard-backend", "ups-guard"], tail=1000
        )

        # 4. 收集 USB 诊断信息
        usb_diag = await _collect_usb_diagnostics()

        # 5. 打包为 ZIP
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            # 写入诊断报告 JSON
            zf.writestr("diagnostics.json", json_str)

            # 写入 NUT 参数报告（如果生成成功）
            if nut_report_content:
                zf.writestr("nut-parameters-report.md", nut_report_content)

            # 写入日志文件
            if nut_logs:
                zf.writestr("logs/nut-container.log", nut_logs)
            if backend_logs:
                zf.writestr("logs/backend-container.log", backend_logs)
            if usb_diag:
                zf.writestr("logs/usb-diagnostics.log", usb_diag)

        zip_buffer.seek(0)

        # 6. 返回 ZIP 文件
        timestamp = datetime.now(_CST).strftime('%Y%m%d-%H%M%S')
        filename = f"ups-guard-diagnostics-{timestamp}.zip"

        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )

    except Exception as e:
        import traceback
        error_detail = (
            f"下载诊断报告失败: {str(e)}\n{traceback.format_exc()}"
        )
        print(error_detail)
        raise HTTPException(
            status_code=500,
            detail=f"下载诊断报告失败: {str(e)}"
        )


@router.get("/system/monitoring-stats")
async def get_monitoring_stats():
    """获取监控统计信息（当前实时统计）"""
    from services.monitor import get_monitor
    from datetime import datetime
    
    monitor = get_monitor()
    if not monitor:
        return {
            "current_mode": "unknown",
            "config_mode": "unknown",
            "event_mode_active": False,
            "today_communications": 0,
            "last_update": None,
            "uptime_seconds": 0,
            "response_time": {
                "avg_ms": None,
                "min_ms": None,
                "max_ms": None,
                "samples": 0
            }
        }
    
    # 确定当前模式
    event_mode_active = getattr(monitor, '_event_mode_active', False)
    config_mode = "polling"
    if hasattr(monitor, 'config') and monitor.config:
        config_mode = monitor.config.monitoring_mode
    
    # 构建当前模式字符串
    # 格式：显示配置的模式 + 括号内显示实际运行状态
    if config_mode == "polling":
        current_mode = "轮询模式"
    elif config_mode == "event_driven":
        current_mode = "事件驱动" if event_mode_active else ("事件驱动 (事件链路未就绪)" if os.environ.get("NUT_EVENT_BRIDGE") == "true" and not monitor.config.event_driven_fallback else "事件驱动 (降级为轮询)")
    else:  # hybrid
        current_mode = "混合模式 (事件驱动)" if event_mode_active else "混合模式 (轮询中)"

    # 获取最后更新时间
    last_update_time = getattr(monitor, '_last_update_time', None)
    # _last_update_time 是本地 naive 时间，转换为带时区偏移的 ISO 字符串
    last_update_iso = last_update_time.astimezone().isoformat() if last_update_time else None
    
    # 获取响应时间统计
    response_times = getattr(monitor, '_response_times', [])
    response_time_stats = {
        "avg_ms": sum(response_times) / len(response_times) if response_times else None,
        "min_ms": min(response_times) if response_times else None,
        "max_ms": max(response_times) if response_times else None,
        "samples": len(response_times)
    }
    
    return {
        "current_mode": current_mode,
        "config_mode": config_mode,  # 原始配置模式（polling/event_driven/hybrid），用于前端 CSS class
        "event_mode_active": event_mode_active,
        "event_source": "native-driver-socket" if os.environ.get('NUT_EVENT_BRIDGE') == 'true' else "LISTEN",
        "driver_event_frames": getattr(monitor, '_driver_bridge_frames', 0),
        "driver_bridge_age_seconds": monitor.driver_bridge_age_seconds() if hasattr(monitor, 'driver_bridge_age_seconds') else None,
        "today_communications": getattr(monitor, '_communication_count_today', 0),
        "last_update": last_update_iso,
        "uptime_seconds": (datetime.now() - monitor._start_time).total_seconds() if hasattr(monitor, '_start_time') else 0,
        "response_time": response_time_stats
    }


@router.get("/system/monitoring-stats/history")
async def get_monitoring_stats_history(
    days: int = Query(30, ge=1, le=365, description="查询最近几天的统计")
):
    """获取监控统计历史数据"""
    from services.history import get_history_service
    
    try:
        history_service = await get_history_service()
        stats = await history_service.get_monitoring_stats(days=days)
        
        return {
            "stats": stats,
            "count": len(stats)
        }
    except Exception as e:
        logger.error(f"Failed to get monitoring stats history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve monitoring statistics")


@router.get("/system/api-token")
async def get_api_token():
    """
    获取当前 API Token。

    此接口本身受 Bearer Token 保护，只有已持有有效 Token 的用户才能调用。
    用于在 Web 界面展示 Token，方便用户复制给 Agent 客户端使用。
    """
    token = settings.get_or_generate_api_token()
    return {
        "token": token,
        "source": "environment" if settings.api_token else "auto_generated",
    }


@router.put("/system/api-token")
async def update_api_token(payload: dict):
    """
    修改或重置 API Token。

    请求体:
        - token: 新的 Token 字符串（可选，为空时自动生成）

    注意:
        - 修改后当前页面的 Token 立即失效，前端需使用新 Token 重新认证
        - 新 Token 会写入 .env 文件持久化
    """
    import secrets as _secrets
    from config import persist_api_token

    new_token = (payload.get("token") or "").strip()

    # 验证自定义 Token
    if new_token:
        if len(new_token) < 8:
            raise HTTPException(
                status_code=400,
                detail="Token 长度不能少于 8 个字符",
            )
        if len(new_token) > 128:
            raise HTTPException(
                status_code=400,
                detail="Token 长度不能超过 128 个字符",
            )
    else:
        # 自动生成
        new_token = _secrets.token_urlsafe(32)

    # 1. 持久化到 .env 并更新 settings
    persist_api_token(new_token)

    # 2. 热更新中间件中的 Token
    from middleware.auth import get_auth_middleware
    middleware = get_auth_middleware()
    if middleware:
        middleware.api_token = new_token
    else:
        logger.warning("Cannot hot-update auth middleware: instance not found")

    logger.info("API Token updated via Web UI")

    return {
        "token": new_token,
        "source": "environment",
        "message": "Token 已更新，请使用新 Token 重新认证",
    }


