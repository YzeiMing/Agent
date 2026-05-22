from sqlalchemy.ext.asyncio import create_async_engine,  AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker, declarative_base
from backend.app.core.config import settings

async_engine = create_async_engine(settings.DATABASE_URL, echo=False)

AsyncSessionLocal = async_sessionmaker(
    bind = async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# ??????????
Base = declarative_base()

async def get_session():
    async with AsyncSessionLocal() as session:
        yield session