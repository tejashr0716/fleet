"""Positions hypertable model storing real-time telemetry."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Double, Float, ForeignKey, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column

from app.models.vehicle import Base


class Position(Base):
    """Core positions hypertable mapped for raw telemetry storage.

    Primary key (vehicle_id, time) ensures that duplicate messages replayed from
    Redis Streams or network retries are dropped via ON CONFLICT DO NOTHING.
    """

    __tablename__ = "positions"

    vehicle_id: Mapped[int] = mapped_column(
        ForeignKey("vehicles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        primary_key=True,
    )
    lat: Mapped[float] = mapped_column(Double, nullable=False)
    lon: Mapped[float] = mapped_column(Double, nullable=False)
    speed_kmh: Mapped[float] = mapped_column(Float, nullable=False)
    heading: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    accuracy_m: Mapped[float] = mapped_column(Float, nullable=False)
    h3_r8: Mapped[int] = mapped_column(BigInteger, nullable=False)
    h3_r7: Mapped[int] = mapped_column(BigInteger, nullable=False)
