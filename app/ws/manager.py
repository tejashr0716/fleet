import asyncio
import json
import logging
from dataclasses import dataclass, field

from app.services.live_state import TOPIC

logger = logging.getLogger("fleet")


@dataclass(eq=False)
class Client:
    expires_at: float
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=64))
    dropped: int = 0


class Hub:
    def __init__(self):
        self.clients = set()
        self.connected = False

    def broadcast(self, event):
        for client in tuple(self.clients):
            self.enqueue(client, event)

    def enqueue(self, client, event):
        if client.queue.full():
            client.queue.get_nowait()
            client.dropped += 1
        client.queue.put_nowait(event)

    async def listen(self, redis):
        while True:
            try:
                async with redis.pubsub() as pubsub:
                    await pubsub.subscribe(TOPIC)
                    self.connected = True
                    self.broadcast({"type": "status", "data": {"realtime": "connected"}})
                    async for message in pubsub.listen():
                        if message["type"] == "message":
                            self.broadcast(json.loads(message["data"]))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.connected = False
                self.broadcast({"type": "status", "data": {"realtime": "unavailable"}})
                logger.warning("Pubsub disconnected: %s", type(exc).__name__)
                await asyncio.sleep(1)
