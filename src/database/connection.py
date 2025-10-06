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
        is_local = os.getenv("DEPLOYMENT", "cloud") == "local"

        if is_local:
            # Local dev: must use service account key
            service_account_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            if not service_account_path:
                raise ValueError(
                    "GOOGLE_APPLICATION_CREDENTIALS environment variable not set."
                )
            cred = credentials.Certificate(service_account_path)
            firebase_admin.initialize_app(cred)
        else:
            # Cloud Run (or any Google-managed environment): use ADC
            try:
                cred, project_id = google.auth.default()
            except Exception as e:
                raise RuntimeError(f"Failed to get default credentials: {e}")

            if not project_id:
                raise ValueError("Project ID could not be inferred from environment.")

            firebase_admin.initialize_app(
                credential=credentials.ApplicationDefault(),
                options={"projectId": project_id},
            )


engine = create_async_engine(DATABASE_URL, echo=LOG_LEVEL == "DEBUG")

AsyncSessionLocal = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
