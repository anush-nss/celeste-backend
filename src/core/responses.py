from fastapi import Request, status, HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime
from typing import Any

def success_response(data: Any, message: str = "Success", status_code: int = status.HTTP_200_OK):
    return JSONResponse(
        status_code=status_code,
        content={
            "statusCode": status_code,
            "message": message,
            "data": data,
        }
    )

async def http_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "statusCode": exc.status_code,
                "timestamp": datetime.now().isoformat(),
                "path": request.url.path,
                "method": request.method,
                "message": exc.detail
            }
        )
    else:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "statusCode": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "timestamp": datetime.now().isoformat(),
                "path": request.url.path,
                "method": request.method,
                "message": "Internal Server Error"
            }
        )
