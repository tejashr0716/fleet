"""Alert repository managing incident notifications."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert
from app.schemas.alert import AlertFilters


class AlertRepository:
    """Repository handling SQL persistence and queries for fleet alerts."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_alerts(self, f: AlertFilters) -> list[Alert]:
        """Fetch alerts matching filters.

        Relies on index ix_alerts_kind_sev_ack for composite filter criteria.

        Args:
            f: Validated alert filtering parameters.

        Returns:
            list[Alert]: Filtered alert records.
        """
        stmt = select(Alert)
        if f.kind:
            stmt = stmt.where(Alert.kind == f.kind)
        if f.severity:
            stmt = stmt.where(Alert.severity == f.severity)
        if f.acknowledged is not None:
            stmt = stmt.where(Alert.acknowledged == f.acknowledged)
        stmt = stmt.order_by(Alert.time.desc()).limit(f.limit).offset(f.offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def acknowledge(self, alert_id: int) -> Alert | None:
        """Mark an alert as acknowledged.

        Relies on the primary key index on alerts.id.

        Args:
            alert_id: Unique alert ID.

        Returns:
            Alert | None: The updated alert or None if not found.
        """
        stmt = update(Alert).where(Alert.id == alert_id).values(acknowledged=True).returning(Alert)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.scalar_one_or_none()
