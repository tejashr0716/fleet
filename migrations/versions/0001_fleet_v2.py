"""Plain PostgreSQL schema, separate from all prototype tables in public."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "fleet_v2_001"
down_revision = None
branch_labels = None
depends_on = None
S = "fleet_v2"


def upgrade():
    op.create_table(
        "vehicles",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(60), nullable=False, unique=True),
        sa.Column("registration", sa.String(30), nullable=False, unique=True),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        schema=S,
    )
    op.create_table(
        "positions",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("vehicle_id", sa.Integer, sa.ForeignKey(f"{S}.vehicles.id"), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lat", sa.Float, nullable=False),
        sa.Column("lon", sa.Float, nullable=False),
        sa.Column("speed_kmh", sa.Float, nullable=False),
        sa.Column("heading", sa.Float, nullable=False),
        sa.UniqueConstraint("vehicle_id", "recorded_at", name="uq_vehicle_time"),
        schema=S,
    )
    op.create_table(
        "geofences",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(60), nullable=False, unique=True),
        sa.Column("lat", sa.Float, nullable=False),
        sa.Column("lon", sa.Float, nullable=False),
        sa.Column("radius_m", sa.Float, nullable=False),
        schema=S,
    )
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("vehicle_id", sa.Integer, sa.ForeignKey(f"{S}.vehicles.id"), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("details", JSONB, nullable=False),
        schema=S,
    )
    op.create_index("ix_alerts_recorded_at", "alerts", ["recorded_at"], schema=S)
    op.create_table(
        "outbox",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        schema=S,
    )
    op.create_index("ix_outbox_delivery", "outbox", ["delivered_at", "id"], schema=S)


def downgrade():
    for table in ["outbox", "alerts", "geofences", "positions", "vehicles"]:
        op.drop_table(table, schema=S)
