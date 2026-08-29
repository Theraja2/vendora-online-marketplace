from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
)


@event.listens_for(engine.sync_engine, "connect")
def _enforce_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
    """SQLite ignores foreign keys unless asked not to.

    PostgreSQL always enforces them, so without this the test suite (which runs
    on SQLite) would silently skip every ON DELETE CASCADE and report passes for
    behaviour that only works in production. No effect on PostgreSQL.
    """
    if engine.dialect.name != "sqlite":
        return

    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session():
    async with AsyncSessionLocal() as session:
        yield session


async def init_models() -> None:
    """Create every table from the models.

    Schema changes in production go through Alembic (`alembic upgrade head`),
    because create_all only ever creates *missing* tables -- it never alters an
    existing one. This helper stays for the test suite, which builds a throwaway
    database from scratch on every run.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
