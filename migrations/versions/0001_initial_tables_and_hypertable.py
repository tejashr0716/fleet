"""Initial tables and hypertable setup.

Revision ID: 0001
Revises:
Create Date: 2026-09-30 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Enable TimescaleDB extension
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")

    # 2. Vehicles table
    op.create_table(
        "vehicles",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("plate", sa.String(32), nullable=False, unique=True),
        sa.Column("label", sa.String(64), nullable=False),
        sa.Column(
            "vehicle_type",
            sa.Enum("truck", "van", "bike", "car", name="vehicle_type"),
            nullable=False,
            server_default="car",
        ),
        sa.Column(
            "status",
            sa.Enum("active", "idle", "offline", "maintenance", name="vehicle_status"),
            nullable=False,
            server_default="offline",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_vehicles_plate", "vehicles", ["plate"], unique=True)
    op.create_index("ix_vehicles_status_type", "vehicles", ["status", "vehicle_type"])

    # 3. Positions table & Hypertable
    op.create_table(
        "positions",
        sa.Column("vehicle_id", sa.Integer(), nullable=False),
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lat", sa.Float(precision=53), nullable=False),
        sa.Column("lon", sa.Float(precision=53), nullable=False),
        sa.Column("speed_kmh", sa.Float(), nullable=False),
        sa.Column("heading", sa.SmallInteger(), nullable=False),
        sa.Column("accuracy_m", sa.Float(), nullable=False),
        sa.Column("h3_r8", sa.BigInteger(), nullable=False),
        sa.Column("h3_r7", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("vehicle_id", "time"),
    )

    # Convert positions to TimescaleDB Hypertable partitioned by time (1-day chunk interval)
    op.execute(
        "SELECT create_hypertable('positions', 'time', chunk_time_interval => INTERVAL '1 day');"
    )

    # Index: (vehicle_id, time DESC) - Serves single vehicle trajectory queries ordered descending
    op.execute("CREATE INDEX ix_positions_vehicle_time_desc ON positions (vehicle_id, time DESC);")

    # Index: (h3_r8, time DESC) - Serves spatial H3 cell density aggregation queries
    op.execute("CREATE INDEX ix_positions_h3_r8_time_desc ON positions (h3_r8, time DESC);")

    # 4. Geofences table
    op.create_table(
        "geofences",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "kind",
            sa.Enum("polygon", "circle", name="geofence_kind"),
            nullable=False,
            server_default="polygon",
        ),
        sa.Column("geojson", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("h3_resolution", sa.SmallInteger(), nullable=False, server_default="8"),
        sa.Column("h3_cells", sa.ARRAY(sa.BigInteger()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 5. Geofence events
    op.create_table(
        "geofence_events",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("vehicle_id", sa.Integer(), nullable=False),
        sa.Column("geofence_id", sa.Integer(), nullable=False),
        sa.Column(
            "event",
            sa.Enum("enter", "exit", name="geofence_event_kind"),
            nullable=False,
        ),
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["geofence_id"], ["geofences.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_geofence_events_vehicle_time",
        "geofence_events",
        ["vehicle_id", sa.text("time DESC")],
    )

    # 6. Trips table
    op.create_table(
        "trips",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("vehicle_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("distance_km", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("avg_speed_kmh", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("max_speed_kmh", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("position_count", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_trips_vehicle_id", "trips", ["vehicle_id"])

    # 7. Alerts table
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("vehicle_id", sa.Integer(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "speeding",
                "idle",
                "geofence_enter",
                "geofence_exit",
                "signal_lost",
                name="alert_kind",
            ),
            nullable=False,
        ),
        sa.Column(
            "severity",
            sa.Enum("info", "warning", "critical", name="alert_severity"),
            nullable=False,
        ),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged", sa.Boolean(), nullable=False, server_default="false"),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_alerts_kind_sev_ack", "alerts", ["kind", "severity", "acknowledged"])
    op.create_index("ix_alerts_vehicle_time", "alerts", ["vehicle_id", sa.text("time DESC")])


def downgrade() -> None:
    op.drop_table("alerts")
    op.drop_table("trips")
    op.drop_table("geofence_events")
    op.drop_table("geofences")
    op.drop_table("positions")
    op.drop_table("vehicles")
    op.execute("DROP TYPE IF EXISTS alert_severity CASCADE;")
    op.execute("DROP TYPE IF EXISTS alert_kind CASCADE;")
    op.execute("DROP TYPE IF EXISTS geofence_event_kind CASCADE;")
    op.execute("DROP TYPE IF EXISTS geofence_kind CASCADE;")
    op.execute("DROP TYPE IF EXISTS vehicle_status CASCADE;")
    op.execute("DROP TYPE IF EXISTS vehicle_type CASCADE;")
