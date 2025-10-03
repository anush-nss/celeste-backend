from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from src.shared.utils import get_logger

logger = get_logger(__name__)


async def http_exception_handler(request: Request, exc: Exception):
    """Global exception handler for HTTP errors."""
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})

    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(status_code=500, content={"error": "Internal server error"})
