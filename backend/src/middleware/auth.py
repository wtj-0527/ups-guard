"""API Token Authentication Middleware"""
import logging
import os
from typing import Callable
from fastapi import Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# 全局中间件实例引用（供热更新 Token 使用）
_middleware_instance = None


def get_auth_middleware():
    """获取全局认证中间件实例"""
    return _middleware_instance


class AuthMiddleware:
    """Bearer Token Authentication Middleware（支持 Token 热更新）"""

    def __init__(self, app, api_token: str):
        global _middleware_instance
        self.app = app
        self._api_token = api_token
        _middleware_instance = self  # 注册全局引用
        # SKIP_AUTH 独立控制，与 MOCK_MODE 解耦
        # MOCK_MODE 只模拟 UPS 数据，不影响认证安全
        self.skip_auth = os.environ.get("SKIP_AUTH", "").lower() in ("true", "1", "yes")
        if self.skip_auth:
            logger.warning("SKIP_AUTH enabled: API authentication is disabled (development only!)")
        # Paths that don't require authentication
        # /api/system/driver-event uses its own NUT_EVENT_SECRET check
        # (see api/driver_events.py) instead of the full-privilege API token.
        self.exclude_paths = {"/health", "/", "/docs", "/openapi.json", "/redoc",
                              "/api/system/driver-event"}
        self.exclude_prefixes = ["/ws", "/api/bootstrap"]

    @property
    def api_token(self) -> str:
        return self._api_token

    @api_token.setter
    def api_token(self, value: str):
        self._api_token = value
        logger.info("AuthMiddleware: api_token updated at runtime")

    async def __call__(self, request: Request, call_next: Callable):
        """Process request with authentication check"""
        path = request.url.path
        
        # SKIP_AUTH 模式跳过所有认证
        if self.skip_auth:
            return await call_next(request)

        # Check if path is excluded from authentication
        if path in self.exclude_paths:
            return await call_next(request)
        
        # Check if path starts with excluded prefix
        for prefix in self.exclude_prefixes:
            if path.startswith(prefix):
                return await call_next(request)
        
        # All /api/ routes require authentication
        if path.startswith("/api/"):
            # Get Authorization header
            auth_header = request.headers.get("Authorization")
            
            if not auth_header:
                logger.warning(f"Unauthorized access attempt to {path}: No Authorization header")
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Missing Authorization header"},
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            # Validate Bearer token
            parts = auth_header.split()
            if len(parts) != 2 or parts[0].lower() != "bearer":
                logger.warning(f"Unauthorized access attempt to {path}: Invalid Authorization format")
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Invalid Authorization header format. Expected: Bearer <token>"},
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            token = parts[1]
            if token != self._api_token:
                logger.warning(f"Unauthorized access attempt to {path}: Invalid token")
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Invalid API token"},
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            logger.debug(f"Authenticated access to {path}")
        
        return await call_next(request)
