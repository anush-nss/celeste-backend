from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from src.routers.auth_router import auth_router
from src.routers.users_router import users_router
from src.routers.categories_router import categories_router
from src.routers.products_router import products_router
from src.routers.discounts_router import discounts_router
from src.routers.orders_router import orders_router
from src.routers.inventory_router import inventory_router
from src.routers.stores_router import stores_router
from src.routers.promotions_router import promotions_router
from src.core.responses import http_exception_handler
from src.core.logger import get_logger
import time

logger = get_logger(__name__)

app = FastAPI(title="Celeste API", description="API documentation for the Celeste e-commerce platform.", version="1.0.0")

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(categories_router)
app.include_router(products_router)
app.include_router(discounts_router)
app.include_router(orders_router)
app.include_router(inventory_router)
app.include_router(stores_router)
app.include_router(promotions_router)

app.add_exception_handler(HTTPException, http_exception_handler)

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    logger.info(f"Request: {request.method} {request.url} - Status: {response.status_code} - Process Time: {process_time:.4f}s")
    return response

@app.get("/", tags=["App"])
async def read_root():
    return "Hello World!"
