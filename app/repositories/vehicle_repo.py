"""Vehicle repository managing database interactions for fleet assets."""

from __future__ import annotations

from sqlalchemy import ColumnElement, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vehicle import Vehicle
from app.schemas.vehicle import VehicleFilters


class VehicleRepository:
    """Repository handling SQL persistence and queries for Vehicle entities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def build_conditions(f: VehicleFilters) -> list[ColumnElement[bool]]:
        """Collect WHERE conditions for the supplied filters.

        Only conditions for parameters that were actually provided are added, so the
        planner sees the narrowest predicate set possible. Relies on ix_vehicles_status_type
        for the status/type combination, and ix_vehicles_plate for ILIKE search.

        Args:
            f: Validated vehicle filtering model.

        Returns:
            list[ColumnElement[bool]]: List of SQLAlchemy binary expression conditions.
        """
        conditions: list[ColumnElement[bool]] = []
        if f.status:
            conditions.append(Vehicle.status.in_(f.status))
        if f.vehicle_type:
            conditions.append(Vehicle.vehicle_type.in_(f.vehicle_type))
        if f.q:
            conditions.append(Vehicle.plate.ilike(f"%{f.q}%"))
        return conditions

    async def list_vehicles(self, f: VehicleFilters) -> list[Vehicle]:
        """Fetch paginated vehicles matching the provided filters.

        Relies on ix_vehicles_status_type and PK for ordering.

        Args:
            f: Filter and pagination criteria.

        Returns:
            list[Vehicle]: Resulting vehicle records.
        """
        stmt = select(Vehicle)
        conditions = self.build_conditions(f)
        if conditions:
            stmt = stmt.where(*conditions)
        stmt = stmt.order_by(Vehicle.id.asc()).limit(f.limit).offset(f.offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, vehicle_id: int) -> Vehicle | None:
        """Retrieve a single vehicle asset by its primary key.

        Relies on the primary key index on vehicles.id.

        Args:
            vehicle_id: Integer primary key.

        Returns:
            Vehicle | None: The matched vehicle or None.
        """
        stmt = select(Vehicle).where(Vehicle.id == vehicle_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
