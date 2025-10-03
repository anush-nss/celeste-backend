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
    FIREBASE_SERVICE_ACCOUNT_PATH = os.getenv(
        "FIREBASE_SERVICE_ACCOUNT_PATH", "service-account.json"
    )

    # Security
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-here")
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRATION_TIME_HOURS = 24

    # API
    API_V1_STR = "/api/v1"


settings = Settings()
