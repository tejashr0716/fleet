"""Drain the PostgreSQL transactional outbox; Redis is a disposable live-state layer."""

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select

from app.config import Settings
from app.db import Database
from app.models import OutboxEvent
from app.redis_client import make_redis
from app.services.live_state import publish_event

logger = logging.getLogger("fleet")


async def drain_once(db, redis, ttl=30, limit=100):
    async with db.sessions() as session:
        async with session.begin():
            events = list(
                (
                    await session.scalars(
                        select(OutboxEvent)
                        .where(OutboxEvent.delivered_at.is_(None))
                        .order_by(OutboxEvent.id)
                        .with_for_update(skip_locked=True)
                        .limit(limit)
                    )
                ).all()
            )
            for row in events:
                event = dict(row.payload, event_id=row.id)
                await publish_event(redis, event, ttl)
                row.delivered_at = datetime.now(UTC)
            # If publishing fails the transaction rolls back; committed data is never discarded.
            return len(events)


async def run():
    settings = Settings()
    db, redis = Database(settings.database_url), make_redis(settings.redis_url)
    try:
        while True:
            try:
                size = await drain_once(db, redis, settings.live_ttl_seconds)
                if not size:
                    await asyncio.sleep(settings.outbox_poll_seconds)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Outbox handoff paused: %s", type(exc).__name__)
                await asyncio.sleep(2)
    finally:
        await db.close()
        await redis.aclose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
