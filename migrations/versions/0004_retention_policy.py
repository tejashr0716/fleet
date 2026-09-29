"""Data retention policy configuration.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-30 00:03:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        # Retention policy: drop raw hypertable chunks older than 30 days
        op.execute("""
            SELECT add_retention_policy('positions', INTERVAL '30 days');
        """)

        # Retention policy: retain 1-minute continuous aggregate for 1 year (365 days)
        op.execute("""
            SELECT add_retention_policy('positions_1min', INTERVAL '365 days');
        """)


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("SELECT remove_retention_policy('positions', if_exists => true);")
        op.execute("SELECT remove_retention_policy('positions_1min', if_exists => true);")
