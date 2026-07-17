import os
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/exceptionloop")
# Neon/Render/Heroku supply postgresql:// — rewrite to asyncpg driver
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
# asyncpg doesn't accept sslmode/channel_binding as query params — strip them
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
_parsed = urlparse(DATABASE_URL)
_qs = {k: v for k, v in parse_qs(_parsed.query).items() if k not in ("sslmode", "channel_binding")}
DATABASE_URL = urlunparse(_parsed._replace(query=urlencode(_qs, doseq=True)))
APP_ENV = os.getenv("APP_ENV", "development")
IS_PROD = APP_ENV == "production"

_connect_args = {"ssl": "require"} if IS_PROD else {}

engine = create_async_engine(
    DATABASE_URL,
    echo=not IS_PROD,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args=_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
