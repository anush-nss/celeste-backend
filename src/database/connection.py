import json
import os

import firebase_admin
import google.auth
from firebase_admin import credentials
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config.settings import settings
from src.shared.utils import LOG_LEVEL

DATABASE_URL = settings.DATABASE_URL

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in environment variables.")


def initialize_firebase():
    """Initialize Firebase Admin SDK"""
    if not firebase_admin._apps:
        # 1. Try to load from environment variable JSON string first (Best for Vercel/CI)
        service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
        if service_account_json:
            try:
                cert_dict = json.loads(service_account_json)
                cred = credentials.Certificate(cert_dict)
                firebase_admin.initialize_app(cred)
                return
            except Exception as e:
                # Log but potentially fall back
                print(f"Failed to initialize Firebase from JSON string: {e}")

        # 2. Fall back to existing logic (Local File or ADC)
        is_local = os.getenv("DEPLOYMENT", "cloud") == "local"

        if is_local:
            # Local dev: must use service account key file
            service_account_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            if not service_account_path:
                print("Warning: GOOGLE_APPLICATION_CREDENTIALS not set and no JSON string found.")
                return
            
            cred = credentials.Certificate(service_account_path)
            firebase_admin.initialize_app(cred)
        else:
            # Cloud Run (or any Google-managed environment): use ADC
            try:
                # Attempt to use Application Default Credentials
                firebase_admin.initialize_app(
                    credential=credentials.ApplicationDefault(),
                )
            except Exception as e:
                print(f"Failed to initialize Firebase from ADC: {e}. You may need to set FIREBASE_SERVICE_ACCOUNT_JSON.")


engine = create_async_engine(
    DATABASE_URL,
    echo=LOG_LEVEL == "DEBUG",
    # Connection pool settings
    pool_size=settings.DB_POOL_SIZE,  # Number of permanent connections
    max_overflow=settings.DB_MAX_OVERFLOW,  # Additional connections that can be created
    pool_timeout=settings.DB_POOL_TIMEOUT,  # Seconds to wait for connection from pool
    pool_recycle=settings.DB_POOL_RECYCLE,  # Recycle connections after N seconds (important for Cloud SQL)
    pool_pre_ping=True,  # Validate connections before using them (prevents "connection is closed")
    # asyncpg-specific settings
    connect_args={
        "command_timeout": settings.DB_COMMAND_TIMEOUT,  # Query timeout in seconds
        "server_settings": {
            "jit": "off",  # Disable JIT for better performance on short queries
            "application_name": "celeste_api",  # For monitoring
        },
    },
)

AsyncSessionLocal = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
