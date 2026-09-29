"""Continuous aggregates setup (1-min and hierarchical 1-hour).

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-30 00:01:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Continuous aggregates cannot be created inside a transaction block in PostgreSQL / TimescaleDB
    # because creating a continuous aggregate registers internal hypertables and catalog
    # entries that require autocommit mode. We execute inside Alembic's autocommit_block().
    with op.get_context().autocommit_block():
        # 1. 1-minute continuous aggregate: rolled up from raw positions hypertable
        op.execute("""
            CREATE MATERIALIZED VIEW positions_1min
            WITH (timescaledb.continuous) AS
            SELECT
                vehicle_id,
                time_bucket('1 minute', time) AS bucket,
                AVG(speed_kmh)::real AS avg_speed_kmh,
                MAX(speed_kmh)::real AS max_speed_kmh,
                last(lat, time) AS lat,
                last(lon, time) AS lon,
                COUNT(*)::integer AS point_count
            FROM positions
            GROUP BY vehicle_id, time_bucket('1 minute', time)
            WITH NO DATA;
        """)

        # Refresh policy for positions_1min: refresh every 1 minute, with 30-second lag buffer
        op.execute("""
            SELECT add_continuous_aggregate_policy('positions_1min',
                start_offset => INTERVAL '2 hours',
                end_offset => INTERVAL '30 seconds',
                schedule_interval => INTERVAL '1 minute');
        """)

        # 2. Hierarchical aggregate: positions_1hour rolled up from positions_1min, NOT raw!
        # This proves the hierarchical continuous aggregate architecture.
        op.execute("""
            CREATE MATERIALIZED VIEW positions_1hour
            WITH (timescaledb.continuous) AS
            SELECT
                vehicle_id,
                time_bucket('1 hour', bucket) AS bucket,
                AVG(avg_speed_kmh)::real AS avg_speed_kmh,
                MAX(max_speed_kmh)::real AS max_speed_kmh,
                last(lat, bucket) AS lat,
                last(lon, bucket) AS lon,
                SUM(point_count)::integer AS point_count
            FROM positions_1min
            GROUP BY vehicle_id, time_bucket('1 hour', bucket)
            WITH NO DATA;
        """)

        # Refresh policy for positions_1hour: refresh every 1 hour
        op.execute("""
            SELECT add_continuous_aggregate_policy('positions_1hour',
                start_offset => INTERVAL '1 day',
                end_offset => INTERVAL '10 minutes',
                schedule_interval => INTERVAL '1 hour');
        """)


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("DROP MATERIALIZED VIEW IF EXISTS positions_1hour CASCADE;")
        op.execute("DROP MATERIALIZED VIEW IF EXISTS positions_1min CASCADE;")
