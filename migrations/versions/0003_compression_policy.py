"""Compression policy configuration.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-30 00:02:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # TimescaleDB hypertable compression configuration
    with op.get_context().autocommit_block():
        # Enable compression with segmentby vehicle_id and orderby time DESC
        op.execute("""
            ALTER TABLE positions SET (
                timescaledb.compress,
                timescaledb.compress_segmentby = 'vehicle_id',
                timescaledb.compress_orderby = 'time DESC'
            );
        """)

        # Add automated compression policy for chunks older than 7 days
        op.execute("""
            SELECT add_compression_policy('positions', INTERVAL '7 days');
        """)


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("SELECT remove_compression_policy('positions', if_exists => true);")
        op.execute("ALTER TABLE positions SET (timescaledb.compress = false);")
