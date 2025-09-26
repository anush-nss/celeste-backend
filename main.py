from src.database.connection import initialize_firebase

initialize_firebase()

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer
from src.api.auth.routes import auth_router
from src.api.users.routes import users_router
from src.api.categories.routes import categories_router
from src.api.ecommerce_categories.routes import ecommerce_categories_router
from src.api.products.routes import products_router
from src.api.orders.routes import orders_router
from src.api.inventory.routes import inventory_router
from src.api.stores.routes import stores_router
from src.api.pricing.routes import pricing_router
from src.api.tiers.routes import router as tiers_router
from src.api.tags.routes import tags_router
from src.middleware.error import http_exception_handler
from src.shared.utils import get_logger
from src.middleware.timing import add_process_time_header
import time
import os

logger = get_logger(__name__)

app = FastAPI(
    title="Celeste API",
    description="API documentation for the Celeste e-commerce platform.",
    version="1.0.0",
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(categories_router)
app.include_router(ecommerce_categories_router)
app.include_router(products_router)
app.include_router(orders_router)
app.include_router(inventory_router)
app.include_router(stores_router)
app.include_router(pricing_router)
app.include_router(tiers_router)
app.include_router(tags_router)

# Include dev router only in development environment
if os.getenv("ENVIRONMENT") == "development":
    from src.api.admin.routes import dev_router

    app.include_router(dev_router)

app.add_exception_handler(Exception, http_exception_handler)

from fastapi.openapi.utils import get_openapi


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="Celeste API",
        version="1.0.0",
        description="API documentation for the Celeste e-commerce platform.",
        routes=app.routes,
    )
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }
    app.openapi_schema = openapi_schema
    # Add global security requirement
    openapi_schema["security"] = [{"BearerAuth": []}]
    return app.openapi_schema


app.openapi = custom_openapi


app.middleware("http")(add_process_time_header)


@app.get("/", tags=["App"])
async def read_root():
    return "Hello World!"
