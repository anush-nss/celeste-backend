import os

from dotenv import load_dotenv

from src.shared.utils import get_logger

logger = get_logger(__name__)


load_dotenv()


class Settings:
    """Application configuration settings."""

    # Environment
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", None)
    DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
    DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    DB_POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))
    DB_POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "3600"))
    DB_COMMAND_TIMEOUT = int(os.getenv("DB_COMMAND_TIMEOUT", "60"))
    FIREBASE_SERVICE_ACCOUNT_PATH = os.getenv(
        "FIREBASE_SERVICE_ACCOUNT_PATH", "service-account.json"
    )

    # Security
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-here")
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRATION_TIME_HOURS = 24
    
    # Rate Limiting & Source Restriction
    MOBILE_APP_SECRET = os.getenv("MOBILE_APP_SECRET", None)
    ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "").split(",")
    # Clean up origins
    ALLOWED_ORIGINS = [o.strip() for o in ALLOWED_ORIGINS if o.strip()]
    
    RATE_LIMIT_EXEMPT_IPS = os.getenv("RATE_LIMIT_EXEMPT_IPS", "").split(",")
    # Clean up IPs
    RATE_LIMIT_EXEMPT_IPS = [ip.strip() for ip in RATE_LIMIT_EXEMPT_IPS if ip.strip()]

    # API
    API_V1_STR = "/api/v1"

    # Odoo ERP Integration
    ODOO_URL = os.getenv("ODOO_URL", None)
    ODOO_DB = os.getenv("ODOO_DB", None)
    ODOO_USERNAME = os.getenv("ODOO_USERNAME", None)
    ODOO_PASSWORD = os.getenv("ODOO_PASSWORD", None)


settings = Settings()
