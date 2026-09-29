"""Trip repository managing segmented movement summaries."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trip import Trip


class TripRepository:
    """Repository handling SQL queries for Vehicle Trip entities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_by_vehicle(self, vehicle_id: int, limit: int = 20) -> list[Trip]:
        """Fetch segmented trips for a specific vehicle.

        Relies on index ix_trips_vehicle_id.

        Args:
            vehicle_id: Vehicle foreign key ID.
            limit: Maximum trips to fetch.

        Returns:
            list[Trip]: Most recent completed trips.
        """
        stmt = (
            select(Trip)
            .where(Trip.vehicle_id == vehicle_id)
            .order_by(Trip.ended_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
