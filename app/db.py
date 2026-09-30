from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


# A separate schema preserves any old prototype's public-schema tables.
class Base(DeclarativeBase):
    metadata = MetaData(schema="fleet_v2")


class Database:
    def __init__(self, url: str):
        self.engine = create_async_engine(url, pool_pre_ping=True, pool_size=10, max_overflow=10)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def close(self):
        await self.engine.dispose()


async def get_session(request):
    async with request.app.state.db.sessions() as session:
        yield session
