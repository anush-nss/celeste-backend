from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from src.config.settings import settings
from src.shared.utils import LOG_LEVEL

DATABASE_URL = settings.DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=LOG_LEVEL=="DEBUG")

AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession
)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session