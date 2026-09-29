"""Positions repository handling TimescaleDB hypertable and continuous aggregates."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.position import DownsampleMode, PositionReadSchema


class PositionRepository:
    """Repository managing telemetry queries against hypertables and continuous aggregates."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_history(
        self,
        vehicle_id: int,
        from_time: datetime,
        to_time: datetime,
        mode: DownsampleMode,
    ) -> tuple[str, list[PositionReadSchema]]:
        """Fetch trajectory history from raw hypertable or continuous aggregates.

        - raw uses index ix_positions_vehicle_time_desc
        - 1min uses positions_1min continuous aggregate
        - 1hour uses positions_1hour hierarchical continuous aggregate

        Args:
            vehicle_id: Target vehicle ID.
            from_time: Start timestamp (UTC).
            to_time: End timestamp (UTC).
            mode: DownsampleMode enum (raw, 1min, 1hour, auto).

        Returns:
            tuple[str, list[PositionReadSchema]]: Source description string and points.
        """
        chosen_mode = mode
        if chosen_mode == DownsampleMode.AUTO:
            span = to_time - from_time
            if span.total_seconds() <= 6 * 3600:
                chosen_mode = DownsampleMode.RAW
            elif span.total_seconds() <= 7 * 86400:
                chosen_mode = DownsampleMode.ONE_MIN
            else:
                chosen_mode = DownsampleMode.ONE_HOUR

        if chosen_mode == DownsampleMode.RAW:
            query = text("""
                SELECT
                    vehicle_id,
                    time,
                    lat,
                    lon,
                    speed_kmh,
                    heading,
                    accuracy_m,
                    1 AS point_count
                FROM positions
                WHERE vehicle_id = :vehicle_id
                  AND time >= :from_time
                  AND time <= :to_time
                ORDER BY time ASC
            """)
            source = "positions (raw hypertable)"
        elif chosen_mode == DownsampleMode.ONE_MIN:
            query = text("""
                SELECT
                    vehicle_id,
                    bucket AS time,
                    lat,
                    lon,
                    avg_speed_kmh AS speed_kmh,
                    0 AS heading,
                    0.0 AS accuracy_m,
                    point_count
                FROM positions_1min
                WHERE vehicle_id = :vehicle_id
                  AND bucket >= :from_time
                  AND bucket <= :to_time
                ORDER BY bucket ASC
            """)
            source = "positions_1min (continuous aggregate)"
        else:
            query = text("""
                SELECT
                    vehicle_id,
                    bucket AS time,
                    lat,
                    lon,
                    avg_speed_kmh AS speed_kmh,
                    0 AS heading,
                    0.0 AS accuracy_m,
                    point_count
                FROM positions_1hour
                WHERE vehicle_id = :vehicle_id
                  AND bucket >= :from_time
                  AND bucket <= :to_time
                ORDER BY bucket ASC
            """)
            source = "positions_1hour (hierarchical continuous aggregate)"

        result = await self.session.execute(
            query,
            {"vehicle_id": vehicle_id, "from_time": from_time, "to_time": to_time},
        )
        rows = result.mappings().all()
        return source, [PositionReadSchema.model_validate(dict(r)) for r in rows]

    async def get_fleet_stats(self) -> dict[str, Any]:
        """Compute aggregated statistics strictly using continuous aggregate positions_1min.

        Relies on the materialized continuous aggregate positions_1min, avoiding
        expensive full-scans on the raw positions hypertable.

        Returns:
            dict[str, Any]: Aggregated fleet metrics over the last 1 hour.
        """
        query = text("""
            SELECT
                COALESCE(AVG(avg_speed_kmh), 0)::real AS avg_speed_kmh,
                COALESCE(MAX(max_speed_kmh), 0)::real AS max_speed_kmh,
                COALESCE(SUM(point_count), 0)::integer AS total_points,
                COUNT(DISTINCT vehicle_id)::integer AS active_vehicles
            FROM positions_1min
            WHERE bucket >= NOW() - INTERVAL '1 hour';
        """)
        result = await self.session.execute(query)
        row = result.mappings().one()
        return dict(row)

    async def get_h3_density(self, resolution: int = 8) -> list[dict[str, Any]]:
        """Return H3 cell activity density over the last 15 minutes for the live heatmap.

        Relies on index ix_positions_h3_r8_time_desc on positions.

        Args:
            resolution: H3 resolution level (7 or 8).

        Returns:
            list[dict[str, Any]]: Hexadecimal cell indices with occurrence counts.
        """
        col = "h3_r8" if resolution == 8 else "h3_r7"
        query = text(f"""
            SELECT
                {col} AS h3_index,
                COUNT(*)::integer AS count
            FROM positions
            WHERE time >= NOW() - INTERVAL '15 minutes'
            GROUP BY {col}
            ORDER BY count DESC
            LIMIT 500;
        """)
        result = await self.session.execute(query)
        return [
            {"cell": hex(r["h3_index"])[2:], "count": r["count"]} for r in result.mappings().all()
        ]
