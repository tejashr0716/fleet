"""Message reclaimer service executing XAUTOCLAIM and forwarding to DLQ."""

from __future__ import annotations

import asyncio
import logging

from redis.asyncio import Redis

from app.config import settings
from app.redis_client import get_redis_client

logger = logging.getLogger("fleet.reclaimer")

MAX_RETRIES = 5
DEAD_LETTER_STREAM = "stream:positions:dlq"


async def run_reclaimer() -> None:
    """Periodically execute XAUTOCLAIM for pending messages and route to DLQ on max retries."""
    redis: Redis = get_redis_client()
    logger.info("Reclaimer service active. Scanning for stalled messages every 30s...")
    start_id = "0-0"

    while True:
        try:
            await asyncio.sleep(30)
            # Reclaim messages pending > 60000ms (60 seconds)
            res = await redis.xautoclaim(
                name=settings.stream_name,
                groupname=settings.consumer_group,
                consumername="reclaimer",
                min_idle_time=60000,
                start_id=start_id,
                count=100,
            )

            next_start_id, messages = res[0], res[1]
            start_id = next_start_id

            if not messages:
                continue

            for msg_id, fields in messages:
                retry_key = f"fleet:retry:{msg_id}"
                retries = await redis.incr(retry_key)
                await redis.expire(retry_key, 3600)

                if retries > MAX_RETRIES:
                    logger.warning(
                        "Message %s exceeded %d attempts. Moving to Dead Letter Queue: %s",
                        msg_id,
                        MAX_RETRIES,
                        DEAD_LETTER_STREAM,
                    )
                    await redis.xadd(DEAD_LETTER_STREAM, fields)
                    await redis.xack(settings.stream_name, settings.consumer_group, msg_id)
                    await redis.xdel(settings.stream_name, msg_id)
                else:
                    logger.info(
                        "Message %s reclaimed (Attempt %d/%d)", msg_id, retries, MAX_RETRIES
                    )

        except Exception as exc:
            logger.error("Exception during XAUTOCLAIM run: %s", exc)
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(run_reclaimer())
