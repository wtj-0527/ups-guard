"""UPS Guard Backend 主程序"""
import logging
import asyncio
import sys
import os
import time
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# 确保 src 目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import settings, get_config_manager, APP_VERSION
from db.database import init_db, close_db
from services.apcupsd_client import create_ups_client
from services.lzc_shutdown import create_shutdown_client
from services.shutdown_manager import ShutdownManager
from services.monitor import UpsMonitor, set_monitor
from services.notifier import get_notifier_service
from services.history import get_history_service
from api.router import router
from api.websocket import broadcast_status_update
from models import EventType, NotifierConfig
from middleware.auth import AuthMiddleware
from utils.crypto import init_crypto_manager

# 导入插件（自动注册）
import plugins.serverchan  # noqa: F401
import plugins.pushplus  # noqa: F401
import plugins.dingtalk  # noqa: F401
import plugins.telegram  # noqa: F401
import plugins.email_smtp  # noqa: F401
import plugins.webhook  # noqa: F401

# 导入 Hook 插件（自动注册）
import hooks.ssh_shutdown  # noqa: F401
import hooks.windows_shutdown  # noqa: F401
import hooks.synology_shutdown  # noqa: F401
import hooks.qnap_shutdown  # noqa: F401
import hooks.http_api  # noqa: F401
import hooks.custom_script  # noqa: F401
import hooks.agent_shutdown  # noqa: F401
from hooks.registry import get_registry


# ========== 日志时区配置（中国标准时间 UTC+8）==========
class _CSTFormatter(logging.Formatter):
    """使用中国标准时间 (UTC+8) 的日志格式化器"""

    @staticmethod
    def converter(timestamp: float) -> time.struct_time:
        return time.gmtime(timestamp + 8 * 3600)


# 配置日志（使用 CST 时区）
_cst_handler = logging.StreamHandler()
_cst_handler.setFormatter(
    _CSTFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
)
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    handlers=[_cst_handler],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""

    # 设置 Hook Registry Mock 模式
    hook_registry = get_registry()
    hook_registry.set_mock_mode(settings.mock_mode)
    
    # 初始化加密管理器
    init_crypto_manager(
        encryption_key=settings.encryption_key if settings.encryption_key else None
    )

    # 初始化数据库
    await init_db(settings.database_path)

    # 加载配置
    config_manager = await get_config_manager()
    config = await config_manager.get_config()

    # 配置通知服务
    notifier_service = get_notifier_service()
    notify_channels = [NotifierConfig(**ch) for ch in config.notify_channels]
    notifier_service.configure(notify_channels, config.notify_events, config.notification_enabled)

    # 创建 UPS 客户端（根据配置选择后端）
    ups_client = create_ups_client(
        backend=settings.ups_backend,
        host=settings.apcupsd_host if settings.ups_backend == "apcupsd" else settings.nut_host,
        port=settings.apcupsd_port if settings.ups_backend == "apcupsd" else settings.nut_port,
        username=settings.nut_username,
        password=settings.nut_password,
        ups_name=settings.nut_ups_name,
        mock_mode=settings.mock_mode,
    )
    
    # 创建关机客户端
    shutdown_client = create_shutdown_client(
        mock_mode=settings.mock_mode,
        shutdown_method=config.shutdown_method,
        gateway_address=settings.lzc_api_gateway_address,
    )
    
    # 创建关机管理器
    shutdown_manager = ShutdownManager(
        shutdown_client,
        config.shutdown_wait_minutes,
        config.shutdown_battery_percent,
        config.shutdown_final_wait_seconds,
        config.estimated_runtime_threshold,
        config.test_mode
    )
    
    # 创建监控器
    monitor = UpsMonitor(
        ups_client,
        shutdown_manager,
        poll_interval=config.poll_interval_seconds,
        sample_interval=config.sample_interval_seconds,
        config=config
    )
    set_monitor(monitor)
    
    # 添加 WebSocket 广播回调
    monitor.add_status_callback(broadcast_status_update)
    
    # 启动监控
    await monitor.start()

    # 记录启动事件
    history_service = await get_history_service()
    await history_service.add_event(
        EventType.STARTUP,
        "UPS Guard 服务已启动"
    )
    
    # 启动定时清理任务
    async def cleanup_task():
        """定时清理历史数据"""
        while True:
            try:
                # 先休眠，再清理（避免启动时立即执行）
                config = await config_manager.get_config()
                sleep_seconds = config.cleanup_interval_hours * 3600
                await asyncio.sleep(sleep_seconds)
                
                # 再次获取配置以使用最新的保留天数
                config = await config_manager.get_config()
                result = await history_service.cleanup_old_data(config.history_retention_days)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
    
    cleanup_task_handle = asyncio.create_task(cleanup_task())

    # 启动设备调度器
    from services.scheduler import get_scheduler
    scheduler = get_scheduler()
    await scheduler.start()

    # 运行期间
    try:
        yield
    except asyncio.CancelledError:
        logger.info("Received shutdown signal, cleaning up...")
    finally:
        # 关闭时清理
        cleanup_task_handle.cancel()
        try:
            await cleanup_task_handle
        except asyncio.CancelledError:
            pass
        await scheduler.stop()
        await monitor.stop()
        await close_db()
        logger.info("Shutdown complete")


# 创建 FastAPI 应用
app = FastAPI(
    title="UPS Guard API",
    description="通用 UPS 智能监控与管理应用，支持多平台部署与多设备纳管",
    version=APP_VERSION,
    lifespan=lifespan
)


# 自定义 OpenAPI schema，添加 Bearer Token 认证支持
def custom_openapi():
    """为 Swagger UI 添加 Authorize 按钮"""
    if app.openapi_schema:
        return app.openapi_schema

    from fastapi.openapi.utils import get_openapi

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    # 添加 Bearer Token 安全方案
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "description": "输入你的 API Token（不需要加 Bearer 前缀）"
        }
    }
    # 全局应用安全方案
    openapi_schema["security"] = [{"BearerAuth": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


# 配置 CORS - 仅允许同域和配置的子域名
allowed_origins = []
if settings.allowed_origins:
    # 从环境变量读取自定义 origins
    allowed_origins = [origin.strip() for origin in settings.allowed_origins.split(",")]
else:
    # 默认允许同域和 lzc-manifest.yml 中的 subdomain
    allowed_origins = [
        "http://localhost",
        "http://localhost:80",
        "http://localhost:5173",  # Vite dev server
        "http://ups-guard",  # subdomain from lzc-manifest.yml
        "https://ups-guard",
    ]


app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加认证中间件（保存引用以便运行时更新 Token）
api_token = settings.get_or_generate_api_token()
auth_middleware = AuthMiddleware(app, api_token)
app.middleware("http")(auth_middleware)

# 注册路由
app.include_router(router)

from api.agent_ws import router as agent_ws_router  # noqa: E402
app.include_router(agent_ws_router)

# 静态文件服务配置
# 查找前端 dist 目录的可能位置
STATIC_DIR_CANDIDATES = [
    Path("/app/frontend/dist"),           # Docker 容器内
    Path(__file__).parent.parent.parent / "frontend" / "dist",  # 开发环境（相对于 backend/src）
    Path.cwd() / "frontend" / "dist",     # 从项目根目录运行
]

STATIC_DIR = None
for candidate in STATIC_DIR_CANDIDATES:
    if candidate.exists() and (candidate / "index.html").exists():
        STATIC_DIR = candidate
        logger.info(f"静态文件目录: {STATIC_DIR}")
        break

if STATIC_DIR:
    # 挂载静态资源目录（CSS、JS、图片等）
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    # 挂载其他静态文件（如 logo.png）
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/health")
async def health():
    """健康检查"""
    from services.monitor import get_monitor
    
    monitor = get_monitor()
    monitor_running = monitor is not None and monitor._running if monitor else False
    
    # Get NUT client connection status
    nut_status = {"connected": False, "error": "Monitor not initialized"}
    if monitor and hasattr(monitor, 'nut_client'):
        nut_client = monitor.nut_client
        if hasattr(nut_client, 'get_connection_status'):
            nut_status = nut_client.get_connection_status()
        elif hasattr(nut_client, 'is_connected'):
            nut_status = {"connected": nut_client.is_connected()}
        elif hasattr(nut_client, '_connected'):
            nut_status = {"connected": nut_client._connected}
    
    return {
        "status": "healthy",
        "version": APP_VERSION,
        "monitor_running": monitor_running,
        "nut_connection": nut_status,
        "mock_mode": settings.mock_mode
    }


# SPA 路由处理 - 所有非 API 路由返回 index.html
@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(request: Request, full_path: str):
    """处理 SPA 路由，返回 index.html"""
    # 跳过 API 路由
    if full_path == "api" or full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not Found")

    if STATIC_DIR:
        # 尝试返回静态文件
        file_path = STATIC_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))

        # 返回 index.html（SPA 路由）
        index_path = STATIC_DIR / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))

    # 如果没有静态文件目录，返回 API 信息
    return {
        "name": "UPS Guard API",
        "version": APP_VERSION,
        "status": "running",
        "message": "Frontend not found. API is available at /api/"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level=settings.log_level.lower()
    )
