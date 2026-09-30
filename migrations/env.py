import asyncio

from alembic import context
from sqlalchemy import text

import app.models  # noqa: F401
from app.config import Settings
from app.db import Base, Database


def run_sync(connection):
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        version_table="alembic_version",
        version_table_schema="fleet_v2",
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def online():
    db = Database(Settings().database_url)
    try:
        async with db.engine.connect() as connection:
            await connection.execute(text("CREATE SCHEMA IF NOT EXISTS fleet_v2"))
            await connection.commit()
            await connection.run_sync(run_sync)
    finally:
        await db.close()


if context.is_offline_mode():
    context.configure(
        url=Settings().database_url,
        target_metadata=Base.metadata,
        literal_binds=True,
        version_table_schema="fleet_v2",
    )
    context.execute("CREATE SCHEMA IF NOT EXISTS fleet_v2")
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(online())
