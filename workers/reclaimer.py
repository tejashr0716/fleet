"""Optional housekeeping: delete successfully delivered outbox rows older than 7 days.
Undelivered events are never deleted. Historical positions are not deleted automatically.
"""

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete

from app.config import Settings
from app.db import Database
from app.models import OutboxEvent


async def cleanup(db, now=None):
    cutoff = (now or datetime.now(UTC)) - timedelta(days=7)
    async with db.sessions() as session:
        result = await session.execute(delete(OutboxEvent).where(OutboxEvent.delivered_at < cutoff))
        await session.commit()
        return result.rowcount


async def main():
    db = Database(Settings().database_url)
    try:
        print({"delivered_events_deleted": await cleanup(db)})
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
