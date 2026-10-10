import asyncio

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.models import Base

target_metadata = Base.metadata


def run_migrations_online() -> None:
    engine = create_async_engine(settings.database_url)

    async def run() -> None:
        async with engine.connect() as connection:
            await connection.run_sync(_do_run)
        await engine.dispose()

    def _do_run(connection):
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

    asyncio.run(run())


run_migrations_online()