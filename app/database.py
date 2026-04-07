from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# Pool sized for concurrent demo / early-production load.
# Render free Postgres allows ~97 max connections; staying well under that.
# pool_size = baseline persistent connections kept warm.
# max_overflow = extra connections opened on demand under burst load.
# pool_pre_ping = drop dead connections silently (defends against stale
#   sockets after Render Postgres restarts / idle timeouts).
# pool_recycle = recycle connections every 30 min so they don't go stale.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=1800,
)

async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
