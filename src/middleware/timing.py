import time

from fastapi import Request

from src.shared.utils import get_logger

logger = get_logger(__name__)


async def add_process_time_header(request: Request, call_next):
    """Middleware to add process time header and log request information."""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    logger.info(
        f"Request: {request.method} {request.url} - Status: {response.status_code} - Process Time: {process_time:.4f}s"
    )
    return response
