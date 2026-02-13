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
    if DATABASE_URL:
        DATABASE_URL = DATABASE_URL.strip()

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
    _odoo_url = os.getenv("ODOO_URL", None)
    ODOO_URL = _odoo_url.strip() if _odoo_url else None
    ODOO_DB = os.getenv("ODOO_DB", None)
    ODOO_USERNAME = os.getenv("ODOO_USERNAME", None)
    ODOO_PASSWORD = os.getenv("ODOO_PASSWORD", None)

    # Payment Gateway
    _api_base_url = os.getenv(
        "API_BASE_URL", "https://celeste-api-846811285865.asia-south1.run.app"
    )
    API_BASE_URL = _api_base_url.strip()
    MPGS_MERCHANT_ID = os.getenv("MPGS_MERCHANT_ID", None)
    MPGS_API_USERNAME = os.getenv("MPGS_API_USERNAME", None)
    MPGS_API_PASSWORD = os.getenv("MPGS_API_PASSWORD", None)
    _mpgs_gateway_url = os.getenv(
        "MPGS_GATEWAY_URL",
        "https://cbcmpgs.gateway.mastercard.com/api/rest/version/100",
    )
    MPGS_GATEWAY_URL = _mpgs_gateway_url.strip()
    MPGS_WEBHOOK_SECRET = os.getenv("MPGS_WEBHOOK_SECRET", None)


settings = Settings()
