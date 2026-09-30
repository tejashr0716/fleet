"""Authenticated, bounded synthetic GPS sessions; never an always-on keepalive."""

import argparse
import asyncio
import logging
import math
import time
from collections import deque
from datetime import UTC, datetime, timedelta
from functools import partial

from fastapi import HTTPException

from simulator.run import run as run_simulator

logger = logging.getLogger("fleet.demo")


class SampleGPS:
    def __init__(self, local_url, sampler=None, settings=None):
        self.local_url = local_url
        self.sampler = sampler or partial(run_simulator, settings=settings)
        self.task = None
        self.lock = asyncio.Lock()
        self.starts = deque()
        self.phase = "idle"
        self.started_at = None
        self.expires_at = None
        self.ended_at = None
        self.error_type = None

    def status(self):
        return {
            "running": self.task is not None and not self.task.done(),
            "phase": self.phase,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "error_type": self.error_type,
            "sample_data": True,
        }

    async def start(self, duration_seconds, remaining_positions):
        if not 1 <= duration_seconds <= 600:
            raise HTTPException(422, "Use a duration between 1 and 600 seconds")
        async with self.lock:
            if self.status()["running"]:
                raise HTTPException(409, "A sample GPS session is already running")
            if remaining_positions < 12:
                raise HTTPException(
                    409, "Temporary demo sample budget reached; use the local setup"
                )
            now = time.monotonic()
            while self.starts and now - self.starts[0] >= 3600:
                self.starts.popleft()
            if len(self.starts) >= 3:
                raise HTTPException(
                    429,
                    "At most three sample GPS sessions per hour",
                    headers={"Retry-After": "3600"},
                )
            self.starts.append(now)
            self.started_at = datetime.now(UTC)
            self.expires_at = self.started_at + timedelta(seconds=duration_seconds)
            self.ended_at = None
            self.error_type = None
            self.phase = "running"
            args = argparse.Namespace(
                url=self.local_url,
                vehicles=12,
                interval=3,
                ticks=min(math.ceil(duration_seconds / 3), remaining_positions // 12),
                trigger_alerts=True,
            )
            self.task = asyncio.create_task(self._execute(args, duration_seconds))
            return self.status()

    async def _execute(self, args, duration_seconds):
        try:
            await asyncio.wait_for(self.sampler(args), timeout=duration_seconds)
            self.phase = "completed"
        except TimeoutError:
            self.phase = "completed"
        except asyncio.CancelledError:
            self.phase = "stopped"
            raise
        except Exception as exc:
            self.phase = "failed"
            self.error_type = type(exc).__name__
            logger.warning("Sample GPS stopped: %s", self.error_type)
        finally:
            self.ended_at = datetime.now(UTC)

    async def stop(self):
        async with self.lock:
            if self.task and not self.task.done():
                self.task.cancel()
                await asyncio.gather(self.task, return_exceptions=True)
                self.phase = "stopped"
                self.ended_at = datetime.now(UTC)
            return self.status()
