"""Geofence repository handling boundaries and transition events."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.geofence import Geofence, GeofenceEvent


class GeofenceRepository:
    """Repository handling SQL persistence for Geofence definitions and event logs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, geofence: Geofence) -> Geofence:
        """Create and commit a new geofence entity.

        Args:
            geofence: The geofence model with pre-computed H3 cells.

        Returns:
            Geofence: The persisted geofence entity with generated ID.
        """
        self.session.add(geofence)
        await self.session.commit()
        await self.session.refresh(geofence)
        return geofence

    async def list_all(self) -> list[Geofence]:
        """Fetch all registered geofences ordered by ID.

        Returns:
            list[Geofence]: All geofence records.
        """
        result = await self.session.execute(select(Geofence).order_by(Geofence.id.asc()))
        return list(result.scalars().all())

    async def get_by_id(self, geofence_id: int) -> Geofence | None:
        """Fetch a single geofence by ID.

        Relies on the primary key index on geofences.id.

        Args:
            geofence_id: Target geofence ID.

        Returns:
            Geofence | None: Matched entity or None.
        """
        result = await self.session.execute(select(Geofence).where(Geofence.id == geofence_id))
        return result.scalar_one_or_none()

    async def delete(self, geofence: Geofence) -> None:
        """Delete an existing geofence.

        Args:
            geofence: Geofence model instance to delete.
        """
        await self.session.delete(geofence)
        await self.session.commit()

    async def get_events(self, geofence_id: int, limit: int = 50) -> list[GeofenceEvent]:
        """Retrieve recent entry/exit events for a geofence.

        Args:
            geofence_id: Target geofence ID.
            limit: Maximum events to return.

        Returns:
            list[GeofenceEvent]: Chronological transition events.
        """
        stmt = (
            select(GeofenceEvent)
            .where(GeofenceEvent.geofence_id == geofence_id)
            .order_by(GeofenceEvent.time.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
