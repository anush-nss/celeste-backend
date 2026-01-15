import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.database.connection import initialize_firebase
from src.api.auth.routes import auth_router
from src.api.categories.routes import categories_router
from src.api.ecommerce_categories.routes import ecommerce_categories_router
from src.api.inventory.routes import inventory_router
from src.api.orders.routes import orders_router
from src.api.pricing.routes import pricing_router
from src.api.products.routes import products_router
from src.api.promotions.routes import promotions_router
from src.api.search.routes import search_router
from src.api.search.service import SearchService
from src.api.stores.routes import stores_router
from src.api.tags.routes import tags_router
from src.api.riders.routes import riders_router
from src.api.tiers.routes import router as tiers_router
from src.api.users.routes import users_router
from src.middleware.error import http_exception_handler
from src.middleware.rate_limit import limiter
from src.middleware.security import TrustedSourceMiddleware
from src.middleware.timing import add_process_time_header
from src.shared.utils import get_logger
from fastapi.openapi.utils import get_openapi
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

initialize_firebase()

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan events.
    Runs on startup and shutdown to manage resources.
    """
    # Startup: Warm up search service
    logger.info("Starting application startup tasks...")
    try:
        search_service = SearchService()
        search_service.warmup()
        logger.info("Application startup complete!")
    except Exception as e:
        logger.error(f"Error during startup warmup: {e}", exc_info=True)
        # Don't crash the app if warmup fails, model will lazy-load on first search

    yield

    # Shutdown: Cleanup (if needed in future)
    logger.info("Application shutdown")


app = FastAPI(
    title="Celeste API",
    description="API documentation for the Celeste e-commerce platform.",
    version="1.0.0",
    lifespan=lifespan,
)

# Register SlowAPI Limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore
app.add_middleware(SlowAPIMiddleware)

# Register Security Middleware
app.add_middleware(TrustedSourceMiddleware)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(categories_router)
app.include_router(ecommerce_categories_router)
# IMPORTANT: Register search_router BEFORE products_router
# to prevent /products/{id} from catching /products/search
app.include_router(search_router)
app.include_router(products_router)
app.include_router(promotions_router)
app.include_router(orders_router)
app.include_router(inventory_router)
app.include_router(stores_router)
app.include_router(pricing_router)
app.include_router(tiers_router)
app.include_router(tags_router)
app.include_router(riders_router)

# Include dev router only in development environment
if os.getenv("ENVIRONMENT") == "development":
    from src.api.admin.routes import dev_router

    app.include_router(dev_router)

app.add_exception_handler(Exception, http_exception_handler)


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
