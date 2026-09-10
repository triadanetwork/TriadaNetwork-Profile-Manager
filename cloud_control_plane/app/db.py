from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine, AsyncSession
from .config import settings

engine: AsyncEngine = create_async_engine(
    settings().database_url,
    pool_pre_ping=True,
    pool_size=settings().db_pool_size,
    max_overflow=settings().db_max_overflow,
    pool_recycle=settings().db_pool_recycle_seconds,
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db():
    async with SessionLocal() as session:
        yield session
