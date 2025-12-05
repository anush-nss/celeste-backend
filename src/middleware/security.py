from typing import List

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from src.config.settings import settings
from src.shared.exceptions import ForbiddenException
from src.shared.utils import get_logger

logger = get_logger(__name__)


class TrustedSourceMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.mobile_secret = settings.MOBILE_APP_SECRET
        self.allowed_origins = self._get_allowed_origins()

    def _get_allowed_origins(self) -> List[str]:
        # Settings already parsed list, just extend it
        active_origins = list(settings.ALLOWED_ORIGINS)
        
        # Always allow localhost for development as per requirements
        active_origins.extend([
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8000", # Sometimes used for testing
            "http://127.0.0.1:8000"
        ])
        return active_origins

    async def dispatch(self, request: Request, call_next):
        # Allow health checks or public assets if needed (simplification: check all API routes)
        # Assuming all API routes start with /api or similar, but for now applying to everything
        # except maybe docs? 
        
        path = request.url.path
        client_ip = request.client.host if request.client else "unknown"
        
        # allow documentation access usually? Or should we restrict that too?
        if path.startswith("/docs") or path.startswith("/openapi.json") or path.startswith("/redoc"):
             # allow if development 
             if settings.ENVIRONMENT == "development":
                 logger.info(f"Access ALLOWED: Documentation (IP: {client_ip})")
                 return await call_next(request)
             else:
                 logger.warning(f"Access DENIED: Documentation (IP: {client_ip})")
                 return Response(content="Forbidden: Documentation access not allowed", status_code=403)

        # 1. Check for Mobile App Secret
        client_secret = request.headers.get("X-Client-Secret")
        if client_secret and self.mobile_secret:
            if client_secret == self.mobile_secret:
                logger.info(f"Access ALLOWED: Mobile App (IP: {client_ip})")
                return await call_next(request)
            else:
                logger.warning(f"Access DENIED: Invalid Mobile Secret (IP: {client_ip})")
                
        # 2. Check for Web Origin / Localhost
        origin = request.headers.get("Origin")
        if origin:
            # Check if strictly in allowed list
            if origin in self.allowed_origins:
                logger.info(f"Access ALLOWED: Web Origin {origin} (IP: {client_ip})")
                return await call_next(request)
            else:
                logger.warning(f"Access DENIED: Unauthorized Origin {origin} (IP: {client_ip})")
            
            # Check for loose localhost matches handled by exact list above
            pass
            
        # 3. Check for Direct Local Access (e.g. Curl from server itself)
        # If client.host is 127.0.0.1, allow?
        if client_ip in ["127.0.0.1", "::1", "localhost"]:
             logger.info(f"Access ALLOWED: Localhost Direct Access (IP: {client_ip})")
             return await call_next(request)

        # If we get here, the request is not from a trusted source
        logger.warning(f"Access BLOCKED: Untrusted Source (IP: {client_ip}, Origin: {origin})")
        return Response(content="Forbidden: Untrusted Source", status_code=403)
