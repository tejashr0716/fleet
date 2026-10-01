"""Add explicit trips without deleting legacy vehicle, position, alert or outbox data."""

import sqlalchemy as sa
from alembic import op

revision = "fleet_v3_002"
down_revision = "fleet_v2_001"
branch_labels = None
depends_on = None
S = "fleet_v2"


def upgrade():
    op.add_column(
        "vehicles",
        sa.Column("is_sample", sa.Boolean(), nullable=False, server_default=sa.false()),
        schema=S,
    )
    op.execute("UPDATE fleet_v2.vehicles SET is_sample = true WHERE registration LIKE 'DEMO-%'")
    op.create_table(
        "trips",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("vehicle_id", sa.Integer(), sa.ForeignKey(f"{S}.vehicles.id"), nullable=False),
        sa.Column("route_key", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("include_speeding", sa.Boolean(), nullable=False),
        sa.Column("end_reason", sa.String(30), nullable=True),
        sa.CheckConstraint(
            "status IN ('active', 'completed', 'interrupted')", name="ck_trip_status"
        ),
        sa.CheckConstraint("duration_seconds BETWEEN 5 AND 600", name="ck_trip_duration"),
        sa.CheckConstraint("ended_at IS NULL OR ended_at >= started_at", name="ck_trip_time"),
        schema=S,
    )
    op.create_index(
        "uq_active_trip_vehicle",
        "trips",
        ["vehicle_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
        schema=S,
    )
    op.create_index("ix_trip_vehicle_started", "trips", ["vehicle_id", "started_at"], schema=S)
    for table in ["positions", "alerts"]:
        op.add_column(
            table,
            sa.Column("trip_id", sa.Integer(), sa.ForeignKey(f"{S}.trips.id"), nullable=True),
            schema=S,
        )
        op.create_index(f"ix_{table}_trip_id", table, ["trip_id"], schema=S)


def downgrade():
    for table in ["alerts", "positions"]:
        op.drop_index(f"ix_{table}_trip_id", table_name=table, schema=S)
        op.drop_column(table, "trip_id", schema=S)
    op.drop_table("trips", schema=S)
    op.drop_column("vehicles", "is_sample", schema=S)
